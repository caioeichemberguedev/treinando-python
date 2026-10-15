"""Persistência do jogo.

- Elenco base por campeonato: `equipes.json` (JSON).
- Carreiras salvas: um banco SQLite por carreira em
  `saves/<numero>_<dia>_<mes>_<ano>.db`. Esta camada é a fachada: cuida do
  nome do arquivo, da transação e do catálogo efetivo; o SQL fica em
  `dados/` (conexão, migrações e repositórios). A versão do formato é o
  `PRAGMA user_version` do banco (`dados.migrar`). Saves `.json` antigos
  ficam no disco, mas fora da lista.
"""

import os
import json
import sqlite3
from datetime import date

import catalogo
from campeonato import unificar_time_escolhido
from dados.conexao import abrir
from dados.migrar import migrar, versao_atual, versao_do_banco
from dados.repositorios.carreira import gravar_carreira, ler_carreira
from dados.repositorios.historico import gravar_historico, ler_historico
from equipe import Equipe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
DIR_SAVES = os.path.join(BASE_DIR, "saves")

# Texto único (terminal e web) para quando o `.db` está em uso (E-015).
MENSAGEM_SAVE_TRAVADO = (
    "Não foi possível salvar: o arquivo da carreira está em uso por outro "
    "programa (por exemplo, o jogo aberto no terminal e no navegador ao "
    "mesmo tempo)."
)

# Códigos primários do SQLite que indicam banco travado por outra conexão.
_CODIGOS_DE_TRAVA = (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
# Máscara que tira o código estendido (ex.: SQLITE_BUSY_SNAPSHOT) e deixa o primário.
_MASCARA_CODIGO_PRIMARIO = 0xFF


class SaveTravado(Exception):
    """O save não foi gravado porque o arquivo da carreira está em uso por
    outra conexão. O save anterior fica intacto; dá para tentar de novo.
    """


def carregar_equipes():
    if os.path.exists(ARQUIVO_EQUIPES):
        with open(ARQUIVO_EQUIPES, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        return {
            campeonato: [
                _aplicar_catalogo(_completar_com_catalogo(Equipe.from_dict(time_dados)))
                for time_dados in times
            ]
            for campeonato, times in dados.items()
        }

    return restaurar_equipes_padrao()


def _completar_com_catalogo(equipe):
    """Completa só em memória um time de `equipes.json` antigo: `id`
    ausente vem do catálogo pelo nome; `cores` ausentes vêm do catálogo pelo
    id. O arquivo não é regravado.
    """
    if equipe.id is None:
        # `id` é somente leitura: recria a equipe com o id do catálogo.
        dados = equipe.to_dict()
        dados["id"] = catalogo.id_do_time_por_nome(equipe.nome)
        equipe = Equipe.from_dict(dados)
    if equipe.cores is None:
        equipe.cores = catalogo.cores_do_time(equipe.id)
    return equipe


def _aplicar_catalogo(equipe):
    """Troca `nome`/`cores` da equipe pelos do catálogo efetivo (com as
    edições do adm), se o id dela for conhecido. O catálogo é a fonte da
    verdade; o que está no arquivo é só um retrato salvo. Só em memória:
    nenhum arquivo é regravado. Id desconhecido/None → equipe intacta.
    """
    nome = catalogo.nome_do_time(equipe.id)
    if nome is not None:
        equipe.nome = nome
        equipe.cores = catalogo.cores_do_time(equipe.id)
    return equipe


def restaurar_equipes_padrao():
    """Recria o elenco (finanças, fãs, força, títulos e cores) com os valores
    iniciais padrão e sobrescreve o `equipes.json`. Não afeta um jogo salvo
    em andamento, que mantém sua própria cópia dos times.
    """
    equipes = {}
    for time in catalogo.TIMES_PADRAO:
        equipe = Equipe(time["nome"], cores=time["cores"], id=time["id"])
        equipes.setdefault(time["campeonato"], []).append(equipe)
    salvar_equipes(equipes)
    return equipes


def salvar_equipes(equipes):
    dados = {campeonato: [equipe.to_dict() for equipe in times] for campeonato, times in equipes.items()}
    with open(ARQUIVO_EQUIPES, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def _caminho_save(nome_save):
    return os.path.join(DIR_SAVES, f"{nome_save}.db")


def gerar_nome_save():
    """Gera um nome único para uma nova carreira, no formato
    "numero_dia_mes_ano" (ex.: "1_23_09_2026"), permitindo que várias
    carreiras existam salvas ao mesmo tempo e sejam distinguidas facilmente.
    Olha o prefixo numérico de qualquer arquivo em `saves/` (inclusive
    `.json` antigos), então nunca colide com eles.
    """
    maior_numero = 0
    if os.path.isdir(DIR_SAVES):
        for nome_arquivo in os.listdir(DIR_SAVES):
            prefixo = nome_arquivo.split("_", 1)[0]
            if prefixo.isdigit():
                maior_numero = max(maior_numero, int(prefixo))

    hoje = date.today()
    return f"{maior_numero + 1}_{hoje.day:02d}_{hoje.month:02d}_{hoje.year}"


def _banco_e_save_valido(conn):
    """True se o banco aberto é uma carreira que o jogo sabe ler: versão
    entre 1 e `versao_atual()` e com a linha da `carreira`. Não escreve
    nada. Pode levantar `sqlite3.Error` (ex.: arquivo que não é banco).
    """
    versao = versao_do_banco(conn)
    if not 1 <= versao <= versao_atual():
        return False
    return conn.execute("SELECT 1 FROM carreira WHERE id = 1").fetchone() is not None


def _save_valido(nome_save):
    """True se `saves/<nome>.db` é uma carreira válida. Abre só leitura:
    não cria nem altera o arquivo. Arquivo corrompido/inválido não é
    apagado — só fica fora da lista.
    """
    try:
        with abrir(_caminho_save(nome_save), somente_leitura=True) as conn:
            return _banco_e_save_valido(conn)
    except sqlite3.Error:
        return False


def listar_saves():
    """Lista os nomes das carreiras salvas, da mais antiga para a mais nova.
    Só entram arquivos `.db` válidos na versão atual (ou anterior) do
    esquema; `.json` antigos e arquivos inválidos ficam de fora.
    """
    if not os.path.isdir(DIR_SAVES):
        return []

    nomes = [
        nome_arquivo[:-3]
        for nome_arquivo in os.listdir(DIR_SAVES)
        if nome_arquivo.endswith(".db") and _save_valido(nome_arquivo[:-3])
    ]

    def numero_do_save(nome):
        prefixo = nome.split("_", 1)[0]
        return int(prefixo) if prefixo.isdigit() else 0

    return sorted(nomes, key=numero_do_save)


def salvar_jogo(nome_save, campeonato, time_escolhido, temporada, classificados, historico=None):
    """Grava o retrato completo da carreira em `saves/<nome>.db`, numa
    transação só: se der erro no meio, o save anterior fica intacto.

    `classificados=None` = temporada nova, ainda não sorteada; `historico`
    = temporadas já concluídas nesta carreira.

    Levanta `SaveTravado` (com o `sqlite3.OperationalError` original em
    `__cause__`) se o arquivo estiver em uso por outra conexão além do
    timeout; qualquer outro erro sobe intacto.
    """
    os.makedirs(DIR_SAVES, exist_ok=True)
    try:
        with abrir(_caminho_save(nome_save), criar=True) as conn:
            migrar(conn)
            with conn:
                gravar_carreira(conn, campeonato, temporada, time_escolhido, classificados)
                gravar_historico(conn, historico or [])
    except sqlite3.OperationalError as erro:
        if _erro_de_trava(erro):
            raise SaveTravado(MENSAGEM_SAVE_TRAVADO) from erro
        raise


def _erro_de_trava(erro: sqlite3.OperationalError) -> bool:
    """True se o erro é de banco travado (SQLITE_BUSY/SQLITE_LOCKED). Usa
    o código do SQLite e, na falta dele, "locked" na mensagem.
    """
    codigo = getattr(erro, "sqlite_errorcode", None)
    if codigo is not None:
        return codigo & _MASCARA_CODIGO_PRIMARIO in _CODIGOS_DE_TRAVA
    return "locked" in str(erro).lower()


def carregar_jogo_salvo(nome_save):
    """Lê uma carreira salva específica e já reconstrói `time_escolhido`/
    `classificados` como objetos `Equipe`, com nome/cores do catálogo
    efetivo (edições do adm valem também para carreiras em andamento; nada
    é regravado).

    Se o time do jogador está nos `classificados`, o `time_escolhido`
    devolvido é o MESMO objeto do classificado
    (`campeonato.unificar_time_escolhido`, B-020): vitórias e títulos da
    temporada caem na ficha do jogador. Os demais times continuam objetos
    próprios desta carreira.

    Devolve {"campeonato", "time_escolhido", "temporada", "classificados",
    "historico"}, ou None se o save não existir ou não for válido (o
    arquivo nunca é criado).
    """
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return None

    try:
        with abrir(caminho, criar=False) as conn:
            if not _banco_e_save_valido(conn):
                return None
            migrar(conn)  # save de versão antiga se atualiza sozinho
            carreira = ler_carreira(conn)
            historico = ler_historico(conn)
    except (sqlite3.Error, ValueError):
        return None

    if carreira is None:
        return None

    time_escolhido = _aplicar_catalogo(carreira["time_escolhido"])
    classificados = carreira["classificados"]
    if classificados is not None:
        classificados = [_aplicar_catalogo(equipe) for equipe in classificados]
    # B-020: o time do jogador vira um objeto só (escolhido = classificado).
    classificados = unificar_time_escolhido(time_escolhido, classificados)

    return {
        "campeonato": carreira["campeonato"],
        "time_escolhido": time_escolhido,
        "temporada": carreira["temporada"],
        "classificados": classificados,
        "historico": historico,
    }


def excluir_jogo_salvo(nome_save):
    """Apaga uma carreira salva específica (e um `-journal` que tenha
    sobrado). Retorna True se ela existia.
    """
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return False
    os.remove(caminho)
    journal = f"{caminho}-journal"
    if os.path.exists(journal):
        os.remove(journal)
    return True
