import os
import json
from datetime import date

import catalogo
from equipe import Equipe

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
DIR_SAVES = os.path.join(BASE_DIR, "saves")

# Versão do formato do save. A 2 guarda o histórico com ids dos times (não
# nomes); saves sem essa versão são ignorados por `listar_saves()`.
VERSAO_SAVE = 2


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
    return os.path.join(DIR_SAVES, f"{nome_save}.json")


def gerar_nome_save():
    """Gera um nome único para uma nova carreira, no formato
    "numero_dia_mes_ano" (ex.: "1_23_09_2026"), permitindo que várias
    carreiras existam salvas ao mesmo tempo e sejam distinguidas facilmente.
    """
    maior_numero = 0
    if os.path.isdir(DIR_SAVES):
        for nome_arquivo in os.listdir(DIR_SAVES):
            prefixo = nome_arquivo.split("_", 1)[0]
            if prefixo.isdigit():
                maior_numero = max(maior_numero, int(prefixo))

    hoje = date.today()
    return f"{maior_numero + 1}_{hoje.day:02d}_{hoje.month:02d}_{hoje.year}"


def _save_na_versao_atual(nome_save):
    """True se o arquivo do save é um JSON válido gravado com `VERSAO_SAVE`.
    Saves antigos (sem versão) ou corrompidos não são apagados — só ficam
    fora da lista.
    """
    try:
        with open(_caminho_save(nome_save), "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        return False
    return isinstance(dados, dict) and dados.get("versao") == VERSAO_SAVE


def listar_saves():
    """Lista os nomes das carreiras salvas, da mais antiga para a mais nova.
    Só entram saves na versão atual do formato (`VERSAO_SAVE`).
    """
    if not os.path.isdir(DIR_SAVES):
        return []

    nomes = [
        nome_arquivo[:-5]
        for nome_arquivo in os.listdir(DIR_SAVES)
        if nome_arquivo.endswith(".json") and _save_na_versao_atual(nome_arquivo[:-5])
    ]

    def numero_do_save(nome):
        prefixo = nome.split("_", 1)[0]
        return int(prefixo) if prefixo.isdigit() else 0

    return sorted(nomes, key=numero_do_save)


def salvar_jogo(nome_save, campeonato, time_escolhido, temporada, classificados, historico=None):
    dados = {
        "versao": VERSAO_SAVE,
        "campeonato": campeonato,
        "time_escolhido": time_escolhido.to_dict(),
        "temporada": temporada,
        # None = temporada nova, ainda não sorteada
        "classificados": [equipe.to_dict() for equipe in classificados] if classificados is not None else None,
        "historico": historico or [],  # temporadas já concluídas nesta carreira
    }
    os.makedirs(DIR_SAVES, exist_ok=True)
    with open(_caminho_save(nome_save), "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_jogo_salvo(nome_save):
    """Lê uma carreira salva específica e já reconstrói `time_escolhido`/
    `classificados` como objetos `Equipe`, com nome/cores do catálogo
    efetivo (edições do adm valem também para carreiras em andamento).
    Retorna None se não existir.
    """
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return None

    with open(caminho, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    dados["time_escolhido"] = _aplicar_catalogo(Equipe.from_dict(dados["time_escolhido"]))
    if dados["classificados"] is not None:
        dados["classificados"] = [
            _aplicar_catalogo(Equipe.from_dict(item)) for item in dados["classificados"]
        ]

    return dados


def excluir_jogo_salvo(nome_save):
    """Apaga uma carreira salva específica. Retorna True se ela existia."""
    caminho = _caminho_save(nome_save)
    if not os.path.exists(caminho):
        return False
    os.remove(caminho)
    return True
