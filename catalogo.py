"""Catálogo de identidade dos times: id fixo, campeonato, nome e cores.

É a fonte da verdade do elenco padrão (o `equipes.json` é regenerado a
partir daqui por `persistencia.restaurar_equipes_padrao()`). O id é a chave
que identifica o time; o nome é só o que aparece na tela.

O adm pode editar nome e cores de cada time. Essas edições ficam em
`ARQUIVO_CATALOGO` (só os times alterados) e valem por cima de
`TIMES_PADRAO`: o resultado é o "catálogo efetivo" (`carregar_catalogo()`),
que é o que `nome_do_time`, `cores_do_time` e `nome_para_exibir` consultam.
"""

import json
import os
import re

from equipe import Equipe

# Edições do adm: {"<id>": {"nome": "...", "cores": ["#RRGGBB", ...]}}.
# Caminho absoluto na pasta do projeto (a de `catalogo.py`), para valer o
# mesmo arquivo qualquer que seja o diretório de onde o jogo é iniciado.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CATALOGO = os.path.join(BASE_DIR, "catalogo_times.json")

TAMANHO_MAXIMO_NOME = 40
MINIMO_CORES = 1
MAXIMO_CORES = 4

_PADRAO_HEX = re.compile(r"#[0-9A-Fa-f]{6}")

# Cache do catálogo efetivo: (chave, catálogo). A chave muda quando o
# arquivo muda (mtime/tamanho), quando o caminho é trocado (testes) ou
# quando `TIMES_PADRAO` é substituído (monkeypatch nos testes).
_cache = None

# Copa do Brasil = ids 1-16, Copa do Mundo 2026 = ids 17-32. As cores são as
# faixas do escudo (hex, de 1 a 4, da esquerda para a direita).
TIMES_PADRAO = [
    {"id": 1, "campeonato": "Copa do Brasil", "nome": "São Paulo", "cores": ["#E30613", "#FFFFFF", "#000000"]},
    {"id": 2, "campeonato": "Copa do Brasil", "nome": "Palmeiras", "cores": ["#006437", "#FFFFFF", "#006437"]},
    {"id": 3, "campeonato": "Copa do Brasil", "nome": "Corinthians", "cores": ["#000000", "#FFFFFF"]},
    {"id": 4, "campeonato": "Copa do Brasil", "nome": "Santos", "cores": ["#FFFFFF", "#000000", "#FFFFFF"]},
    {"id": 5, "campeonato": "Copa do Brasil", "nome": "Flamengo", "cores": ["#C4161C", "#000000", "#C4161C"]},
    {"id": 6, "campeonato": "Copa do Brasil", "nome": "Vasco", "cores": ["#000000", "#FFFFFF", "#E30613"]},
    {"id": 7, "campeonato": "Copa do Brasil", "nome": "Botafogo", "cores": ["#000000", "#FFFFFF", "#000000"]},
    {"id": 8, "campeonato": "Copa do Brasil", "nome": "Fluminense", "cores": ["#870A28", "#FFFFFF", "#00613C"]},
    {"id": 9, "campeonato": "Copa do Brasil", "nome": "Grêmio", "cores": ["#0D80BF", "#000000", "#FFFFFF"]},
    {"id": 10, "campeonato": "Copa do Brasil", "nome": "Internacional", "cores": ["#E5050F", "#FFFFFF", "#E5050F"]},
    {"id": 11, "campeonato": "Copa do Brasil", "nome": "Cruzeiro", "cores": ["#2F529E", "#FFFFFF", "#2F529E"]},
    {"id": 12, "campeonato": "Copa do Brasil", "nome": "Atlético-MG", "cores": ["#000000", "#FFFFFF", "#F5C400"]},
    {"id": 13, "campeonato": "Copa do Brasil", "nome": "Bahia", "cores": ["#006CB5", "#FFFFFF", "#ED3237"]},
    {"id": 14, "campeonato": "Copa do Brasil", "nome": "Vitória", "cores": ["#E30613", "#000000", "#FFFFFF"]},
    {"id": 15, "campeonato": "Copa do Brasil", "nome": "Athletico-PR", "cores": ["#000000", "#C8102E", "#000000"]},
    {"id": 16, "campeonato": "Copa do Brasil", "nome": "Coritiba", "cores": ["#00573F", "#FFFFFF", "#00573F"]},
    {"id": 17, "campeonato": "Copa do Mundo 2026", "nome": "Brasil", "cores": ["#009C3B", "#FFDF00", "#002776"]},
    {"id": 18, "campeonato": "Copa do Mundo 2026", "nome": "Argentina", "cores": ["#75AADB", "#FFFFFF", "#75AADB"]},
    {"id": 19, "campeonato": "Copa do Mundo 2026", "nome": "Uruguai", "cores": ["#55B5E5", "#FFFFFF", "#000000"]},
    {"id": 20, "campeonato": "Copa do Mundo 2026", "nome": "Paraguai", "cores": ["#D52B1E", "#FFFFFF", "#0038A8"]},
    {"id": 21, "campeonato": "Copa do Mundo 2026", "nome": "França", "cores": ["#002395", "#FFFFFF", "#ED2939"]},
    {"id": 22, "campeonato": "Copa do Mundo 2026", "nome": "Espanha", "cores": ["#AA151B", "#F1BF00", "#AA151B"]},
    {"id": 23, "campeonato": "Copa do Mundo 2026", "nome": "Alemanha", "cores": ["#000000", "#DD0000", "#FFCE00"]},
    {"id": 24, "campeonato": "Copa do Mundo 2026", "nome": "Inglaterra", "cores": ["#FFFFFF", "#CE1124", "#FFFFFF"]},
    {"id": 25, "campeonato": "Copa do Mundo 2026", "nome": "Itália", "cores": ["#009246", "#FFFFFF", "#CE2B37"]},
    {"id": 26, "campeonato": "Copa do Mundo 2026", "nome": "Holanda", "cores": ["#F36C21", "#FFFFFF", "#21468B"]},
    {"id": 27, "campeonato": "Copa do Mundo 2026", "nome": "Portugal", "cores": ["#006600", "#DA291C", "#FFCC00"]},
    {"id": 28, "campeonato": "Copa do Mundo 2026", "nome": "Croácia", "cores": ["#FFFFFF", "#FF0000", "#171796"]},
    {"id": 29, "campeonato": "Copa do Mundo 2026", "nome": "Marrocos", "cores": ["#C1272D", "#006233", "#C1272D"]},
    {"id": 30, "campeonato": "Copa do Mundo 2026", "nome": "Bélgica", "cores": ["#000000", "#FDDA24", "#EF3340"]},
    {"id": 31, "campeonato": "Copa do Mundo 2026", "nome": "Noruega", "cores": ["#BA0C2F", "#00205B", "#BA0C2F"]},
    {"id": 32, "campeonato": "Copa do Mundo 2026", "nome": "Suíça", "cores": ["#DA291C", "#FFFFFF", "#DA291C"]},
]


def limpar_cache():
    """Esquece o catálogo efetivo em memória (a próxima leitura relê)."""
    global _cache
    _cache = None


def _chave_cache():
    """Identifica a versão atual das fontes do catálogo efetivo."""
    try:
        info = os.stat(ARQUIVO_CATALOGO)
        versao_arquivo = (info.st_mtime_ns, info.st_size)
    except FileNotFoundError:
        versao_arquivo = None
    return (ARQUIVO_CATALOGO, versao_arquivo, id(TIMES_PADRAO), len(TIMES_PADRAO))


def _ler_edicoes_adm():
    """Lê `ARQUIVO_CATALOGO` → {id (int): {"nome", "cores"}}.

    Arquivo ausente → {}. Entradas com chave não numérica são ignoradas.
    """
    try:
        with open(ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        return {}
    edicoes = {}
    for chave, valores in dados.items():
        try:
            edicoes[int(chave)] = valores
        except ValueError:
            continue
    return edicoes


def _montar_catalogo():
    """`TIMES_PADRAO` com as edições do adm por cima."""
    edicoes = _ler_edicoes_adm()
    catalogo_efetivo = {}
    for time in TIMES_PADRAO:
        edicao = edicoes.get(time["id"], {})
        catalogo_efetivo[time["id"]] = {
            "campeonato": time["campeonato"],
            "nome": edicao.get("nome", time["nome"]),
            "cores": list(edicao.get("cores", time["cores"])),
        }
    return catalogo_efetivo


def carregar_catalogo():
    """Catálogo efetivo: {id: {"campeonato", "nome", "cores"}}.

    Usa cache em memória e só relê o arquivo do adm quando ele muda. Não
    altere o dict devolvido: ele é o próprio cache (as funções públicas de
    consulta devolvem cópias).
    """
    global _cache
    chave = _chave_cache()
    if _cache is None or _cache[0] != chave:
        _cache = (chave, _montar_catalogo())
    return _cache[1]


def _time_por_id(id_time):
    """Devolve o dict do time no catálogo efetivo com esse id, ou None."""
    try:
        return carregar_catalogo().get(id_time)
    except TypeError:  # id não hashable (ex.: lista)
        return None


def nome_do_time(id_time):
    """Nome do time com esse id no catálogo, ou None se o id não existir."""
    time = _time_por_id(id_time)
    return time["nome"] if time is not None else None


def cores_do_time(id_time):
    """Cópia das cores (1 a 4) do time com esse id, ou None se não existir.

    Devolve uma lista nova: alterar o resultado não muda o catálogo.
    """
    time = _time_por_id(id_time)
    return list(time["cores"]) if time is not None else None


def cores_validas(cores):
    """True se `cores` é uma lista/tupla de 1 a 4 hex no formato `#RRGGBB`."""
    if not isinstance(cores, (list, tuple)):
        return False
    if not MINIMO_CORES <= len(cores) <= MAXIMO_CORES:
        return False
    return all(
        isinstance(cor, str) and _PADRAO_HEX.fullmatch(cor) for cor in cores
    )


def validar_time(id_time, nome, cores):
    """Valida uma edição do adm. Devolve a lista de mensagens de erro
    (vazia se estiver tudo certo).
    """
    catalogo_efetivo = carregar_catalogo()
    erros = []
    if not isinstance(id_time, int) or id_time not in catalogo_efetivo:
        erros.append("Time não encontrado no catálogo.")

    nome_limpo = nome.strip() if isinstance(nome, str) else ""
    if not nome_limpo:
        erros.append("O nome do time não pode ficar vazio.")
    elif len(nome_limpo) > TAMANHO_MAXIMO_NOME:
        erros.append(
            f"O nome do time pode ter no máximo {TAMANHO_MAXIMO_NOME} caracteres."
        )
    else:
        comparar = nome_limpo.casefold()
        for outro_id, time in catalogo_efetivo.items():
            if outro_id != id_time and time["nome"].casefold() == comparar:
                erros.append(f"Já existe um time chamado {time['nome']}.")
                break

    if not cores_validas(cores):
        erros.append(
            f"Escolha de {MINIMO_CORES} a {MAXIMO_CORES} cores no formato "
            "#RRGGBB."
        )
    return erros


def salvar_time_no_catalogo(id_time, nome, cores):
    """Grava a edição do adm (nome sem espaços nas pontas e cores em
    maiúsculas) em `ARQUIVO_CATALOGO`.

    Inválido → `ValueError` com as mensagens de erro, sem gravar nada.
    """
    erros = validar_time(id_time, nome, cores)
    if erros:
        raise ValueError(" ".join(erros))

    edicoes = {
        str(chave): valores for chave, valores in _ler_edicoes_adm().items()
    }
    edicoes[str(id_time)] = {
        "nome": nome.strip(),
        "cores": [cor.upper() for cor in cores],
    }
    with open(ARQUIVO_CATALOGO, "w", encoding="utf-8") as arquivo:
        json.dump(edicoes, arquivo, ensure_ascii=False, indent=2)
    limpar_cache()


def id_do_time_por_nome(nome):
    """Id do time do catálogo com esse nome, ou None se não houver.

    Serve só para completar `equipes.json` antigo (sem `id`); no resto do
    jogo o time é identificado pelo id.
    """
    for time in TIMES_PADRAO:
        if time["nome"] == nome:
            return time["id"]
    return None


def nome_para_exibir(time):
    """Nome que deve aparecer na tela para `time`.

    Aceita `Equipe`, id (`int`), `None` ou texto:
    - id conhecido (direto ou de uma `Equipe`) → nome do catálogo;
    - `Equipe` com id desconhecido/None → `equipe.nome`;
    - `int` desconhecido → "Time #<id>";
    - `None` → "";
    - `str` → ela mesma.
    """
    if time is None:
        return ""
    if isinstance(time, Equipe):
        return nome_do_time(time.id) or time.nome
    if isinstance(time, str):
        return time
    nome = nome_do_time(time)
    return nome if nome is not None else f"Time #{time}"
