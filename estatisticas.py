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
ROTULO_CAMPEAO = "Campeão"
ROTULO_VICE = "Vice-campeão"
ROTULO_EM_ANDAMENTO = "Em andamento"
ROTULO_NAO_REGISTRADA = "Não registrada"
PROFUNDIDADE_CAMPEAO = 0


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


def _campanha(
    temporada: dict, rotulo: str, profundidade: int | None
) -> dict:
    """Monta o dict de retorno de `campanha_na_temporada`."""
    return {
        "temporada": temporada["temporada"],
        "rotulo": rotulo,
        "campeao": temporada.get("campeao"),
        "profundidade": profundidade,
    }


def campanha_na_temporada(temporada: dict, id_time: int) -> dict:
    """Diz até onde `id_time` chegou numa temporada.

    Devolve `{"temporada", "rotulo", "campeao", "profundidade"}`.
    `profundidade` é o número de confrontos da fase em que o time caiu
    (menor = foi mais longe; 0 = campeão) ou `None` quando não dá para
    julgar: temporada em andamento com o time ainda vivo ("Em andamento")
    ou concluída sem nenhuma derrota registrada do time ("Não registrada",
    fases perdidas ao retomar no meio — ID-014). O campeão vale mesmo sem
    nenhum jogo registrado.
    """
    if temporada.get("campeao") == id_time and id_time is not None:
        return _campanha(temporada, ROTULO_CAMPEAO, PROFUNDIDADE_CAMPEAO)

    fases = temporada.get("fases", [])
    concluida = temporada.get("campeao") is not None
    for indice, fase in enumerate(fases):
        for id_a, id_b, id_vencedor, _, _ in fase["confrontos"]:
            if id_time in (id_a, id_b) and id_vencedor != id_time:
                profundidade = len(fase["confrontos"])
                if concluida and indice == len(fases) - 1:
                    return _campanha(temporada, ROTULO_VICE, profundidade)
                rotulo = f"Eliminado na {nome_fase_curto(fase['nome_fase'])}"
                return _campanha(temporada, rotulo, profundidade)

    rotulo = ROTULO_NAO_REGISTRADA if concluida else ROTULO_EM_ANDAMENTO
    return _campanha(temporada, rotulo, None)


def melhor_campanha(campanhas: list[dict]) -> dict | None:
    """Escolhe a campanha de menor `profundidade` (a que foi mais longe).

    Devolve `{"rotulo", "temporadas"}`; empates juntam as temporadas na
    ordem recebida (o rótulo é o da primeira). Campanhas com `profundidade`
    `None` ("Em andamento", "Não registrada") são ignoradas; sem nenhuma
    julgável, devolve `None`.
    """
    julgaveis = [c for c in campanhas if c["profundidade"] is not None]
    if not julgaveis:
        return None
    melhor = min(julgaveis, key=lambda campanha: campanha["profundidade"])
    return {
        "rotulo": melhor["rotulo"],
        "temporadas": [
            c["temporada"]
            for c in julgaveis
            if c["profundidade"] == melhor["profundidade"]
        ],
    }


def confronto_da_final(temporada: dict) -> dict | None:
    """Devolve a partida da final de uma temporada concluída (E-022).

    Formato: `{"id_a", "id_b", "id_vencedor", "gols_a", "gols_b"}`. Só
    devolve quando a temporada tem campeão, a última fase tem exatamente 1
    confronto e o vencedor dele é o campeão; senão (sem fases, em andamento,
    histórico incompleto) devolve `None`. Não altera o dict recebido.
    """
    campeao = temporada.get("campeao")
    fases = temporada.get("fases", [])
    if campeao is None or not fases:
        return None
    confrontos = fases[-1]["confrontos"]
    if len(confrontos) != 1:
        return None
    id_a, id_b, id_vencedor, gols_a, gols_b = confrontos[0]
    if id_vencedor != campeao:
        return None
    return {
        "id_a": id_a,
        "id_b": id_b,
        "id_vencedor": id_vencedor,
        "gols_a": gols_a,
        "gols_b": gols_b,
    }


def temporada_completa(temporada: dict, total_times: int) -> bool:
    """Diz se a primeira fase registrada é mesmo a primeira do torneio.

    Com `total_times` times, a primeira fase tem `total_times // 2`
    confrontos (o ímpar avança direto). Menos que isso = fases perdidas ao
    retomar a carreira no meio (ID-014). Sem fases ou com até 1 time não há
    o que julgar → `True`.
    """
    fases = temporada.get("fases", [])
    if total_times <= 1 or not fases:
        return True
    return len(fases[0]["confrontos"]) == total_times // 2
