import copy
import inspect

from estatisticas import confrontos_do_time, resumo_da_carreira

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
