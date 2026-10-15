"""Estatísticas da carreira (E-019).

Funções puras sobre o formato de ids do histórico — sem `Equipe`, sem I/O e
sem nada da web. Cada "temporada" é um dict no formato gravado em
`historico`:

    {"temporada": 2026, "campeao": id_campeao_ou_None,
     "fases": [{"nome_fase": "Final - Copa X",
                "confrontos": [[id_a, id_b, id_vencedor, gols_a, gols_b]]}]}

A temporada em andamento entra como mais um item, com `"campeao": None`.
"""

from collections.abc import Iterator

SEPARADOR_CAMPEONATO = " - "
CASAS_DECIMAIS_APROVEITAMENTO = 1


def nome_fase_curto(nome_fase: str) -> str:
    """Tira o sufixo `" - <campeonato>"` do nome da fase gravado."""
    return nome_fase.split(SEPARADOR_CAMPEONATO)[0]


def confrontos_do_time(
    temporadas: list[dict], id_time: int
) -> Iterator[tuple[int, str, int, bool, int, int]]:
    """Produz cada confronto de `id_time`, na ordem (temporada, fase).

    Cada item é `(temporada, nome_fase_curto, id_adversario, venceu,
    gols_pro, gols_contra)`, com os gols do ponto de vista do time (trocados
    quando ele é o `id_b` do confronto).
    """
    for temporada in temporadas:
        for fase in temporada.get("fases", []):
            nome_fase = nome_fase_curto(fase["nome_fase"])
            for id_a, id_b, id_vencedor, gols_a, gols_b in fase["confrontos"]:
                if id_a == id_time:
                    id_adversario, gols_pro, gols_contra = id_b, gols_a, gols_b
                elif id_b == id_time:
                    id_adversario, gols_pro, gols_contra = id_a, gols_b, gols_a
                else:
                    continue
                yield (
                    temporada["temporada"],
                    nome_fase,
                    id_adversario,
                    id_vencedor == id_time,
                    gols_pro,
                    gols_contra,
                )


def resumo_da_carreira(temporadas: list[dict], id_time: int) -> dict:
    """Resume a carreira de `id_time` nas `temporadas` recebidas.

    Devolve `{"jogos", "vitorias", "derrotas", "aproveitamento",
    "gols_marcados", "gols_sofridos", "titulos"}`. `aproveitamento` é
    `vitorias / jogos * 100` com 1 casa decimal, ou `None` sem jogos.
    `titulos` conta as temporadas com `campeao == id_time` (temporada em
    andamento, com `campeao` `None`, nunca conta).
    """
    jogos = vitorias = gols_marcados = gols_sofridos = 0
    for _, _, _, venceu, gols_pro, gols_contra in confrontos_do_time(
        temporadas, id_time
    ):
        jogos += 1
        if venceu:
            vitorias += 1
        gols_marcados += gols_pro
        gols_sofridos += gols_contra

    aproveitamento = (
        round(vitorias / jogos * 100, CASAS_DECIMAIS_APROVEITAMENTO)
        if jogos
        else None
    )
    titulos = sum(
        1 for temporada in temporadas if temporada.get("campeao") == id_time
    )
    return {
        "jogos": jogos,
        "vitorias": vitorias,
        "derrotas": jogos - vitorias,
        "aproveitamento": aproveitamento,
        "gols_marcados": gols_marcados,
        "gols_sofridos": gols_sofridos,
        "titulos": titulos,
    }
