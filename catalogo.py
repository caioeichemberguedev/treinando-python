"""Catálogo de identidade dos times: id fixo, campeonato, nome e cores.

É a fonte da verdade do elenco padrão (o `equipes.json` é regenerado a
partir daqui por `persistencia.restaurar_equipes_padrao()`). O id é a chave
que identifica o time; o nome é só o que aparece na tela.
"""

from equipe import Equipe

# Copa do Brasil = ids 1-16, Copa do Mundo 2026 = ids 17-32. As 3 cores são
# as do escudo (hex); times de 2 cores repetem uma.
TIMES_PADRAO = [
    {"id": 1, "campeonato": "Copa do Brasil", "nome": "São Paulo", "cores": ["#E30613", "#FFFFFF", "#000000"]},
    {"id": 2, "campeonato": "Copa do Brasil", "nome": "Palmeiras", "cores": ["#006437", "#FFFFFF", "#006437"]},
    {"id": 3, "campeonato": "Copa do Brasil", "nome": "Corinthians", "cores": ["#FFFFFF", "#000000", "#E30613"]},
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


def _time_por_id(id_time):
    """Devolve o dict do time em `TIMES_PADRAO` com esse id, ou None."""
    for time in TIMES_PADRAO:
        if time["id"] == id_time:
            return time
    return None


def nome_do_time(id_time):
    """Nome do time com esse id no catálogo, ou None se o id não existir."""
    time = _time_por_id(id_time)
    return time["nome"] if time is not None else None


def cores_do_time(id_time):
    """Cópia das 3 cores do time com esse id, ou None se o id não existir.

    Devolve uma lista nova: alterar o resultado não muda o catálogo.
    """
    time = _time_por_id(id_time)
    return list(time["cores"]) if time is not None else None


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
