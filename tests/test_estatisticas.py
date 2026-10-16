import copy
import inspect

from estatisticas import (
    campanha_na_temporada,
    confronto_da_final,
    confrontos_do_time,
    melhor_campanha,
    resumo_da_carreira,
    temporada_completa,
)

# Histórico escrito à mão: 4 times (ids 1 a 4), 2 temporadas concluídas.
# Confronto = [id_a, id_b, id_vencedor, gols_a, gols_b] (gols de pênalti).
HISTORICO = [
    {
        "temporada": 2026,
        "campeao": 1,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa X",
                "confrontos": [[1, 2, 1, 5, 3], [3, 4, 4, 2, 4]],
            },
            {
                "nome_fase": "Final - Copa X",
                "confrontos": [[4, 1, 1, 3, 4]],
            },
        ],
    },
    {
        "temporada": 2027,
        "campeao": 3,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa X",
                "confrontos": [[2, 1, 1, 4, 5], [4, 3, 3, 1, 3]],
            },
            {
                "nome_fase": "Final - Copa X",
                "confrontos": [[1, 3, 3, 2, 4]],
            },
        ],
    },
]


def test_confrontos_do_time_e_um_generator():
    """`confrontos_do_time` produz um confronto por vez (generator)."""
    assert inspect.isgenerator(confrontos_do_time(HISTORICO, 1))


def test_confrontos_do_time_na_ordem_com_gols_do_ponto_de_vista_do_time():
    """Os confrontos saem na ordem (temporada, fase), com os gols do time
    primeiro — inclusive quando ele é o `id_b` — e a fase sem o sufixo do
    campeonato.
    """
    confrontos = list(confrontos_do_time(HISTORICO, 1))

    assert confrontos == [
        (2026, "Semifinal", 2, True, 5, 3),   # time é id_a
        (2026, "Final", 4, True, 4, 3),       # time é id_b
        (2027, "Semifinal", 2, True, 5, 4),   # time é id_b
        (2027, "Final", 3, False, 2, 4),      # time é id_a
    ]


def test_confrontos_do_time_ignora_confrontos_de_outros_times():
    """Só os jogos do time pedido aparecem."""
    confrontos = list(confrontos_do_time(HISTORICO, 2))

    assert confrontos == [
        (2026, "Semifinal", 1, False, 3, 5),
        (2027, "Semifinal", 1, False, 4, 5),
    ]


def test_resumo_da_carreira_conta_jogos_vitorias_gols_e_titulos():
    """3 vitórias em 4 jogos → aproveitamento 75.0; 1 título (2026)."""
    resumo = resumo_da_carreira(HISTORICO, 1)

    assert resumo == {
        "jogos": 4,
        "vitorias": 3,
        "derrotas": 1,
        "aproveitamento": 75.0,
        "gols_marcados": 16,
        "gols_sofridos": 14,
        "titulos": 1,
    }


def test_resumo_da_carreira_arredonda_aproveitamento_em_uma_casa():
    """1 vitória em 3 jogos → 33.3."""
    resumo = resumo_da_carreira(HISTORICO, 4)

    assert resumo["jogos"] == 3
    assert resumo["vitorias"] == 1
    assert resumo["derrotas"] == 2
    assert resumo["aproveitamento"] == 33.3
    assert resumo["titulos"] == 0


def test_resumo_da_carreira_lista_vazia_da_zeros_e_aproveitamento_none():
    """Sem temporadas, tudo zero e aproveitamento `None` (sem dividir por
    zero).
    """
    assert resumo_da_carreira([], 1) == {
        "jogos": 0,
        "vitorias": 0,
        "derrotas": 0,
        "aproveitamento": None,
        "gols_marcados": 0,
        "gols_sofridos": 0,
        "titulos": 0,
    }


def test_resumo_da_carreira_time_que_nunca_jogou():
    """Time fora do histórico → zeros e aproveitamento `None`."""
    resumo = resumo_da_carreira(HISTORICO, 99)

    assert resumo["jogos"] == 0
    assert resumo["vitorias"] == 0
    assert resumo["derrotas"] == 0
    assert resumo["aproveitamento"] is None
    assert resumo["gols_marcados"] == 0
    assert resumo["gols_sofridos"] == 0
    assert resumo["titulos"] == 0


def test_resumo_da_carreira_temporada_em_andamento_conta_jogos_sem_titulo():
    """Temporada com `"campeao": None` entra nos jogos, mas não em
    títulos.
    """
    em_andamento = {
        "temporada": 2028,
        "campeao": None,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa X",
                "confrontos": [[1, 4, 1, 3, 1]],
            },
        ],
    }

    resumo = resumo_da_carreira(HISTORICO + [em_andamento], 1)

    assert resumo["jogos"] == 5
    assert resumo["vitorias"] == 4
    assert resumo["gols_marcados"] == 19
    assert resumo["gols_sofridos"] == 15
    assert resumo["aproveitamento"] == 80.0
    assert resumo["titulos"] == 1


def test_temporada_sem_fases_registradas_nao_quebra():
    """Temporada concluída sem fases (ID-014) só conta o título."""
    temporadas = [{"temporada": 2026, "campeao": 1, "fases": []}]

    resumo = resumo_da_carreira(temporadas, 1)

    assert resumo["jogos"] == 0
    assert resumo["aproveitamento"] is None
    assert resumo["titulos"] == 1


def test_funcoes_nao_alteram_a_lista_recebida():
    """Nem o generator nem o resumo mexem no histórico recebido."""
    historico = copy.deepcopy(HISTORICO)

    list(confrontos_do_time(historico, 1))
    resumo_da_carreira(historico, 1)

    assert historico == HISTORICO


# --- E-019-T3: campanha, melhor campanha e temporada completa ---


def _campanha(temporada, rotulo, profundidade):
    """Campanha mínima para `melhor_campanha` (só os campos usados)."""
    return {"temporada": temporada, "rotulo": rotulo, "profundidade": profundidade}


def test_campanha_do_campeao():
    """Campeão → "Campeão", profundidade 0."""
    assert campanha_na_temporada(HISTORICO[0], 1) == {
        "temporada": 2026,
        "rotulo": "Campeão",
        "campeao": 1,
        "profundidade": 0,
    }


def test_campanha_de_quem_perdeu_a_final_e_vice():
    """Perdeu a final de temporada concluída → "Vice-campeão", 1."""
    campanha = campanha_na_temporada(HISTORICO[0], 4)

    assert campanha["rotulo"] == "Vice-campeão"
    assert campanha["profundidade"] == 1
    assert campanha["campeao"] == 1


def test_campanha_de_quem_perdeu_a_semifinal_sem_sufixo_do_campeonato():
    """Perdeu a semi de 4 times → "Eliminado na Semifinal", 2."""
    campanha = campanha_na_temporada(HISTORICO[0], 2)

    assert campanha["rotulo"] == "Eliminado na Semifinal"
    assert campanha["profundidade"] == 2


def test_campanha_em_andamento_com_time_vivo():
    """Temporada sem campeão e sem derrota do time → "Em andamento"."""
    em_andamento = {
        "temporada": 2028,
        "campeao": None,
        "fases": [
            {"nome_fase": "Semifinal - Copa X", "confrontos": [[1, 2, 1, 5, 4]]},
        ],
    }

    campanha = campanha_na_temporada(em_andamento, 1)

    assert campanha["rotulo"] == "Em andamento"
    assert campanha["profundidade"] is None
    assert campanha["campeao"] is None


def test_campanha_em_andamento_sem_fases_registradas():
    """Temporada recém sorteada (sem fases) → "Em andamento"."""
    recem_sorteada = {"temporada": 2028, "campeao": None, "fases": []}

    campanha = campanha_na_temporada(recem_sorteada, 1)

    assert campanha["rotulo"] == "Em andamento"
    assert campanha["profundidade"] is None


def test_campanha_em_andamento_ja_eliminado():
    """Temporada sem campeão, mas o time já perdeu → "Eliminado na <fase>"
    com a profundidade da fase (nunca "Vice", mesmo sendo a última fase
    registrada).
    """
    em_andamento = {
        "temporada": 2028,
        "campeao": None,
        "fases": [
            {
                "nome_fase": "Quartas de Final - Copa X",
                "confrontos": [[1, 2, 2, 3, 4], [3, 4, 3, 5, 3],
                               [5, 6, 5, 4, 2], [7, 8, 8, 1, 3]],
            },
        ],
    }

    campanha = campanha_na_temporada(em_andamento, 1)

    assert campanha["rotulo"] == "Eliminado na Quartas de Final"
    assert campanha["profundidade"] == 4


def test_campanha_concluida_sem_o_time_registrado():
    """Concluída sem o time em nenhuma fase registrada (ID-014: só a
    final ficou gravada) → "Não registrada".
    """
    so_a_final = {
        "temporada": 2026,
        "campeao": 3,
        "fases": [
            {"nome_fase": "Final - Copa X", "confrontos": [[3, 4, 3, 5, 4]]},
        ],
    }

    campanha = campanha_na_temporada(so_a_final, 1)

    assert campanha["rotulo"] == "Não registrada"
    assert campanha["profundidade"] is None
    assert campanha["campeao"] == 3


def test_campanha_concluida_com_o_time_so_vencendo_fases_registradas():
    """Venceu tudo o que foi registrado mas não é o campeão (fases
    seguintes perdidas) → "Não registrada", nunca "Em andamento".
    """
    incompleta = {
        "temporada": 2026,
        "campeao": 3,
        "fases": [
            {"nome_fase": "Semifinal - Copa X",
             "confrontos": [[1, 2, 1, 5, 4], [3, 4, 3, 5, 3]]},
        ],
    }

    campanha = campanha_na_temporada(incompleta, 1)

    assert campanha["rotulo"] == "Não registrada"
    assert campanha["profundidade"] is None


def test_campanha_titulo_sem_nenhum_jogo_registrado():
    """Campeão com 0 jogos registrados (carreira retomada perto do fim,
    ID-014) continua "Campeão", profundidade 0, e conta como melhor
    campanha.
    """
    sem_fases = {"temporada": 2026, "campeao": 1, "fases": []}

    campanha = campanha_na_temporada(sem_fases, 1)

    assert campanha["rotulo"] == "Campeão"
    assert campanha["profundidade"] == 0
    assert melhor_campanha([campanha]) == {
        "rotulo": "Campeão",
        "temporadas": [2026],
    }


def test_campanha_na_unica_fase_registrada_que_e_a_final_e_vice():
    """Só a final registrada (ID-014) e o time perdeu nela → "Vice-campeão"."""
    so_a_final = {
        "temporada": 2026,
        "campeao": 3,
        "fases": [
            {"nome_fase": "Final - Copa X", "confrontos": [[1, 3, 3, 2, 4]]},
        ],
    }

    campanha = campanha_na_temporada(so_a_final, 1)

    assert campanha["rotulo"] == "Vice-campeão"
    assert campanha["profundidade"] == 1


def test_melhor_campanha_escolhe_a_menor_profundidade():
    """A campanha que foi mais longe (menor profundidade) vence."""
    campanhas = [
        _campanha(2026, "Eliminado na Quartas de Final", 4),
        _campanha(2027, "Vice-campeão", 1),
        _campanha(2028, "Eliminado na Semifinal", 2),
    ]

    assert melhor_campanha(campanhas) == {
        "rotulo": "Vice-campeão",
        "temporadas": [2027],
    }


def test_melhor_campanha_empate_junta_temporadas_em_ordem():
    """Empate na melhor profundidade junta as temporadas, em ordem."""
    campanhas = [
        _campanha(2026, "Campeão", 0),
        _campanha(2027, "Eliminado na Semifinal", 2),
        _campanha(2028, "Campeão", 0),
    ]

    assert melhor_campanha(campanhas) == {
        "rotulo": "Campeão",
        "temporadas": [2026, 2028],
    }


def test_melhor_campanha_ignora_em_andamento_e_nao_registrada():
    """Campanhas com profundidade `None` não entram na escolha."""
    campanhas = [
        _campanha(2026, "Não registrada", None),
        _campanha(2027, "Eliminado na Semifinal", 2),
        _campanha(2028, "Em andamento", None),
    ]

    assert melhor_campanha(campanhas) == {
        "rotulo": "Eliminado na Semifinal",
        "temporadas": [2027],
    }


def test_melhor_campanha_so_nones_ou_vazia_da_none():
    """Sem nenhuma campanha julgável → `None`."""
    assert melhor_campanha([]) is None
    assert melhor_campanha([
        _campanha(2026, "Não registrada", None),
        _campanha(2027, "Em andamento", None),
    ]) is None


def test_melhor_campanha_a_partir_do_historico():
    """Integração: campanhas do histórico de exemplo → melhor é o título
    de 2026 para o time 1 e o vice de 2026 para o time 4.
    """
    campanhas_1 = [campanha_na_temporada(t, 1) for t in HISTORICO]
    campanhas_4 = [campanha_na_temporada(t, 4) for t in HISTORICO]

    assert [c["rotulo"] for c in campanhas_1] == ["Campeão", "Vice-campeão"]
    assert melhor_campanha(campanhas_1) == {
        "rotulo": "Campeão",
        "temporadas": [2026],
    }
    assert melhor_campanha(campanhas_4) == {
        "rotulo": "Vice-campeão",
        "temporadas": [2026],
    }


def _temporada_com_primeira_fase(num_confrontos):
    """Temporada cuja 1ª fase registrada tem `num_confrontos` confrontos."""
    confrontos = [[i, i + 100, i, 5, 4] for i in range(num_confrontos)]
    return {
        "temporada": 2026,
        "campeao": None,
        "fases": [{"nome_fase": "Fase - Copa X", "confrontos": confrontos}],
    }


def test_temporada_completa_16_times_com_8_confrontos():
    """16 times e 8 confrontos na 1ª fase → completa."""
    assert temporada_completa(_temporada_com_primeira_fase(8), 16) is True


def test_temporada_incompleta_16_times_comecando_nas_quartas():
    """16 times e só 4 confrontos (começou nas quartas, ID-014) → False."""
    assert temporada_completa(_temporada_com_primeira_fase(4), 16) is False


def test_temporada_completa_sem_fases():
    """Sem fases não há o que julgar → True."""
    sem_fases = {"temporada": 2026, "campeao": None, "fases": []}

    assert temporada_completa(sem_fases, 16) is True


def test_temporada_completa_total_impar_com_bye():
    """5 times: 2 confrontos na 1ª fase (um avança direto) → True."""
    assert temporada_completa(_temporada_com_primeira_fase(2), 5) is True


def test_temporada_completa_com_ate_um_time():
    """Total de times 0 ou 1 (estado de teste) → True."""
    assert temporada_completa(_temporada_com_primeira_fase(4), 0) is True
    assert temporada_completa(_temporada_com_primeira_fase(4), 1) is True


def test_funcoes_de_campanha_nao_alteram_o_que_recebem():
    """`campanha_na_temporada`, `melhor_campanha` e `temporada_completa`
    não mexem no que recebem.
    """
    historico = copy.deepcopy(HISTORICO)

    campanhas = [campanha_na_temporada(t, 1) for t in historico]
    copia_campanhas = copy.deepcopy(campanhas)
    melhor_campanha(campanhas)
    for temporada in historico:
        temporada_completa(temporada, 4)

    assert historico == HISTORICO
    assert campanhas == copia_campanhas


# --- Placar da final (E-022-T2) ---


def test_confronto_da_final_temporada_concluida():
    """Temporada normal → os 5 campos da única partida da última fase."""
    assert confronto_da_final(HISTORICO[0]) == {
        "id_a": 4,
        "id_b": 1,
        "id_vencedor": 1,
        "gols_a": 3,
        "gols_b": 4,
    }


def test_confronto_da_final_sem_campeao_devolve_none():
    """Temporada em andamento (campeão None) não tem final para mostrar."""
    temporada = copy.deepcopy(HISTORICO[0])
    temporada["campeao"] = None

    assert confronto_da_final(temporada) is None


def test_confronto_da_final_sem_fases_devolve_none():
    """Temporada concluída sem nenhuma fase registrada → None."""
    assert confronto_da_final({"temporada": 2026, "campeao": 1, "fases": []}) is None
    assert confronto_da_final({"temporada": 2026, "campeao": 1}) is None


def test_confronto_da_final_ultima_fase_com_dois_confrontos_devolve_none():
    """Se a última fase registrada não é uma final (2 jogos) → None."""
    temporada = {
        "temporada": 2026,
        "campeao": 1,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa X",
                "confrontos": [[1, 2, 1, 5, 3], [3, 4, 4, 2, 4]],
            },
        ],
    }

    assert confronto_da_final(temporada) is None


def test_confronto_da_final_vencedor_diferente_do_campeao_devolve_none():
    """Histórico inconsistente (vencedor da final ≠ campeão) → None."""
    temporada = copy.deepcopy(HISTORICO[0])
    temporada["campeao"] = 4

    assert confronto_da_final(temporada) is None


def test_confronto_da_final_nao_altera_a_temporada():
    """A função é pura: o dict recebido continua igual."""
    temporada = copy.deepcopy(HISTORICO[0])
    original = copy.deepcopy(temporada)

    confronto_da_final(temporada)

    assert temporada == original


# --- Bordas do placar da final (tester, E-022-T2) ---


def test_confronto_da_final_empate_decidido_nos_penaltis_mantem_gols():
    """Final 'empatada' não existe no mata-mata por pênaltis, mas o placar
    é repassado como está (gols do lado a e do lado b, sem reordenar)."""
    temporada = {
        "temporada": 2027,
        "campeao": 7,
        "fases": [{"nome_fase": "Final - Copa X", "confrontos": [[3, 7, 7, 4, 5]]}],
    }

    assert confronto_da_final(temporada) == {
        "id_a": 3, "id_b": 7, "id_vencedor": 7, "gols_a": 4, "gols_b": 5,
    }


def test_confronto_da_final_ultima_fase_vazia_devolve_none():
    """Última fase sem confronto nenhum (dado corrompido) → None, sem exceção."""
    temporada = {"temporada": 2026, "campeao": 1, "fases": [{"nome_fase": "Final", "confrontos": []}]}

    assert confronto_da_final(temporada) is None


def test_confronto_da_final_aceita_tupla_do_jogo_em_andamento():
    """Confronto em tupla (como na memória da web) funciona igual à lista."""
    temporada = {"temporada": 2026, "campeao": 2, "fases": [{"nome_fase": "Final", "confrontos": [(1, 2, 2, 0, 3)]}]}

    assert confronto_da_final(temporada)["id_vencedor"] == 2
