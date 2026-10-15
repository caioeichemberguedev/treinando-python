"""Testes de `dados.repositorios.historico` (E-013-T4; fases em andamento E-014-T2)."""

import copy
import inspect
import re
import sqlite3

import pytest

from dados.repositorios import historico as repo_historico
from dados.repositorios.historico import (
    gravar_fases_em_andamento,
    gravar_historico,
    ler_fases_em_andamento,
    ler_historico,
)

# Mesmo histórico de 2 temporadas de tests/web/test_admin_integracao.py.
HISTORICO = [
    {
        "temporada": 2026,
        "campeao": 1,
        "fases": [
            {"nome_fase": "Semifinal - Copa do Brasil",
             "confrontos": [[1, 2, 1, 4, 2], [3, 4, 4, 3, 5]]},
            {"nome_fase": "Final - Copa do Brasil",
             "confrontos": [[1, 4, 1, 5, 4]]},
        ],
    },
    {
        "temporada": 2027,
        "campeao": 3,
        "fases": [
            {"nome_fase": "Semifinal - Copa do Brasil",
             "confrontos": [[1, 2, 1, 5, 3], [3, 4, 3, 4, 2]]},
            {"nome_fase": "Final - Copa do Brasil",
             "confrontos": [[1, 3, 3, 2, 4]]},
        ],
    },
]

TEMPORADA_2028 = {
    "temporada": 2028,
    "campeao": 2,
    "fases": [
        {"nome_fase": "Final - Copa do Brasil",
         "confrontos": [[2, 4, 2, 1, 0]]},
    ],
}


def _contar(conn, tabela):
    # `tabela` é sempre um nome fixo do próprio teste, nunca valor de fora.
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def test_ida_e_volta_devolve_exatamente_o_mesmo_historico(conn):
    gravar_historico(conn, HISTORICO)

    lido = ler_historico(conn)

    assert lido == HISTORICO
    # Confrontos voltam como listas (não tuplas nem sqlite3.Row).
    for temporada in lido:
        for fase in temporada["fases"]:
            assert type(fase["confrontos"]) is list
            assert all(type(confronto) is list for confronto in fase["confrontos"])


def test_ordem_das_temporadas_e_a_de_insercao_nao_a_do_ano(conn):
    fora_de_ordem = [copy.deepcopy(HISTORICO[1]), copy.deepcopy(HISTORICO[0])]

    gravar_historico(conn, fora_de_ordem)

    assert ler_historico(conn) == fora_de_ordem


def test_historico_vazio_volta_vazio(conn):
    gravar_historico(conn, [])

    assert ler_historico(conn) == []


def test_banco_sem_historico_le_lista_vazia(conn):
    assert ler_historico(conn) == []


def test_temporada_sem_fases_volta_igual(conn):
    sem_fases = [{"temporada": 2026, "campeao": 901, "fases": []}]

    gravar_historico(conn, sem_fases)

    assert ler_historico(conn) == sem_fases


def test_gravar_de_novo_substitui_sem_duplicar(conn):
    gravar_historico(conn, HISTORICO)
    com_mais_uma = copy.deepcopy(HISTORICO) + [copy.deepcopy(TEMPORADA_2028)]

    gravar_historico(conn, com_mais_uma)

    assert _contar(conn, "temporadas") == 3
    assert _contar(conn, "fases") == 5
    assert _contar(conn, "confrontos") == 7
    assert ler_historico(conn) == com_mais_uma


def test_gravar_menos_temporadas_nao_deixa_sobra(conn):
    gravar_historico(conn, HISTORICO)

    gravar_historico(conn, [copy.deepcopy(TEMPORADA_2028)])

    assert _contar(conn, "temporadas") == 1
    assert _contar(conn, "fases") == 1
    assert _contar(conn, "confrontos") == 1
    assert ler_historico(conn) == [TEMPORADA_2028]


def test_nome_de_fase_com_aspas_e_acento(conn):
    historico = [{
        "temporada": 2026,
        "campeao": 1,
        "fases": [{"nome_fase": "Final 'D'Alessandro' — Copa \"çã\"",
                   "confrontos": [[1, 2, 1, 1, 0]]}],
    }]

    gravar_historico(conn, historico)

    assert ler_historico(conn) == historico


def test_confronto_invalido_falha_e_mantem_historico_anterior(conn):
    with conn:
        gravar_historico(conn, HISTORICO)
    invalido = copy.deepcopy(HISTORICO) + [{
        "temporada": 2028,
        "campeao": 2,
        "fases": [{"nome_fase": "Final - Copa do Brasil",
                   # Vencedor 9 não é nenhum dos dois times.
                   "confrontos": [[2, 4, 9, 1, 0]]}],
    }]

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_historico(conn, invalido)

    assert ler_historico(conn) == HISTORICO
    assert _contar(conn, "temporadas") == 2
    assert _contar(conn, "fases") == 4
    assert _contar(conn, "confrontos") == 6


def test_gravar_historico_nao_faz_commit(conn):
    gravar_historico(conn, HISTORICO)

    assert conn.in_transaction
    conn.rollback()
    assert ler_historico(conn) == []


def test_codigo_sem_select_asterisco_nem_sql_montado_com_valor():
    codigo = inspect.getsource(repo_historico)

    assert not re.search(r"SELECT\s+\*", codigo, re.IGNORECASE)
    # Nenhuma f-string nem formatação com % no módulo.
    assert not re.search(r"\bf[\"']", codigo)
    assert not re.search(r"[\"']\s*%\s*\(", codigo)


# --- Casos de borda adicionados pelo game-tester (E-013-T4) ---


@pytest.mark.parametrize("confronto", [
    [1, 2, 1, -1, 0],   # gols negativos
    [1, 2, 1, 0, -3],
    [1, 1, 1, 2, 0],    # time contra ele mesmo
    [1, 2, None, 1, 0],  # sem vencedor
])
def test_confronto_com_valor_invalido_falha_e_mantem_anterior(conn, confronto):
    with conn:
        gravar_historico(conn, HISTORICO)
    invalido = [{"temporada": 2030, "campeao": 1,
                 "fases": [{"nome_fase": "Final", "confrontos": [confronto]}]}]

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_historico(conn, invalido)

    assert ler_historico(conn) == HISTORICO


def test_mesmo_ano_duas_vezes_falha_e_mantem_anterior(conn):
    with conn:
        gravar_historico(conn, HISTORICO)
    repetido = copy.deepcopy(HISTORICO) + [copy.deepcopy(HISTORICO[0])]

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_historico(conn, repetido)

    assert ler_historico(conn) == HISTORICO


@pytest.mark.parametrize("confronto", [[1, 2, 1, 0], [1, 2, 1, 0, 0, 9]])
def test_confronto_com_numero_errado_de_campos_falha_e_mantem_anterior(conn, confronto):
    with conn:
        gravar_historico(conn, HISTORICO)
    invalido = [{"temporada": 2030, "campeao": 1,
                 "fases": [{"nome_fase": "Final", "confrontos": [confronto]}]}]

    with pytest.raises(sqlite3.ProgrammingError):
        with conn:
            gravar_historico(conn, invalido)

    assert ler_historico(conn) == HISTORICO


def test_placar_empatado_com_penaltis_e_zero_a_zero(conn):
    # Empate no tempo normal decidido nos pênaltis: placar guardado é o
    # da disputa, mas o banco não proíbe gols iguais (0x0 é válido).
    historico = [{"temporada": 2026, "campeao": 2,
                  "fases": [{"nome_fase": "Final",
                             "confrontos": [[1, 2, 2, 0, 0]]}]}]

    gravar_historico(conn, historico)

    assert ler_historico(conn) == historico


def test_copa_completa_de_16_times_preserva_ordem_e_tipos(conn):
    # 8 + 4 + 2 + 1 confrontos, ids fora de ordem e mais de 9 confrontos
    # por temporada (garante ORDER BY numérico, não textual).
    oitavas = [[16 - i, i + 1, 16 - i, i, 15 - i] for i in range(8)]
    quartas = [[16, 2, 2, 3, 4], [14, 4, 14, 1, 0], [12, 6, 6, 2, 3], [10, 8, 10, 5, 4]]
    semi = [[2, 14, 14, 0, 1], [6, 10, 6, 7, 6]]
    final = [[14, 6, 6, 4, 5]]
    historico = [{"temporada": 2026 + n, "campeao": 6, "fases": [
        {"nome_fase": "Oitavas de final", "confrontos": oitavas},
        {"nome_fase": "Quartas de final", "confrontos": quartas},
        {"nome_fase": "Semifinal", "confrontos": semi},
        {"nome_fase": "Final", "confrontos": final},
    ]} for n in range(12)]

    gravar_historico(conn, copy.deepcopy(historico))
    lido = ler_historico(conn)

    assert lido == historico
    assert all(type(v) is int
               for t in lido for f in t["fases"] for c in f["confrontos"] for v in c)
    assert all(type(t["temporada"]) is int and type(t["campeao"]) is int for t in lido)


def test_gravar_nao_altera_o_historico_recebido(conn):
    original = copy.deepcopy(HISTORICO)

    gravar_historico(conn, HISTORICO)

    assert HISTORICO == original


def test_ler_historico_nao_abre_transacao(conn):
    with conn:
        gravar_historico(conn, HISTORICO)

    ler_historico(conn)

    assert not conn.in_transaction


# --- Fases da temporada em andamento (E-014-T2) ---

FASES_EM_ANDAMENTO = [
    {"nome_fase": "Oitavas de final - Copa do Brasil",
     "confrontos": [[16 - i, i + 1, 16 - i, i, 15 - i] for i in range(8)]},
    {"nome_fase": "Quartas de final - Copa do Brasil",
     "confrontos": [[16, 2, 2, 3, 4], [14, 4, 14, 1, 0],
                    [12, 6, 6, 2, 3], [10, 8, 10, 5, 4]]},
]


def test_fases_em_andamento_ida_e_volta(conn):
    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    lido = ler_fases_em_andamento(conn)

    assert lido == FASES_EM_ANDAMENTO
    for fase in lido:
        assert type(fase["confrontos"]) is list
        assert all(type(confronto) is list for confronto in fase["confrontos"])
        assert all(type(v) is int for confronto in fase["confrontos"] for v in confronto)


def test_fases_em_andamento_banco_sem_fases_le_lista_vazia(conn):
    assert ler_fases_em_andamento(conn) == []


def test_fases_em_andamento_regravar_substitui_sem_duplicar(conn):
    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO[:1])
    semi = {"nome_fase": "Semifinal - Copa do Brasil",
            "confrontos": [[2, 14, 14, 0, 1], [6, 10, 6, 7, 6]]}
    novas = copy.deepcopy(FASES_EM_ANDAMENTO) + [semi]

    gravar_fases_em_andamento(conn, novas)

    assert _contar(conn, "fases_em_andamento") == 3
    assert _contar(conn, "confrontos_em_andamento") == 14
    assert ler_fases_em_andamento(conn) == novas


def test_fases_em_andamento_lista_vazia_apaga_tudo(conn):
    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    gravar_fases_em_andamento(conn, [])

    assert _contar(conn, "fases_em_andamento") == 0
    assert _contar(conn, "confrontos_em_andamento") == 0
    assert ler_fases_em_andamento(conn) == []


def test_fases_em_andamento_ordem_e_a_da_lista(conn):
    invertidas = list(reversed(copy.deepcopy(FASES_EM_ANDAMENTO)))

    gravar_fases_em_andamento(conn, invertidas)

    assert ler_fases_em_andamento(conn) == invertidas


def test_fases_em_andamento_fase_sem_confrontos_volta_igual(conn):
    fases = [{"nome_fase": "Oitavas de final", "confrontos": []}]

    gravar_fases_em_andamento(conn, fases)

    assert ler_fases_em_andamento(conn) == fases


def test_fases_em_andamento_e_historico_sao_independentes(conn):
    gravar_historico(conn, HISTORICO)
    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    gravar_fases_em_andamento(conn, [])
    assert ler_historico(conn) == HISTORICO

    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)
    gravar_historico(conn, [])
    assert ler_fases_em_andamento(conn) == FASES_EM_ANDAMENTO


def test_fases_em_andamento_confronto_invalido_falha_e_mantem_anterior(conn):
    with conn:
        gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)
    invalidas = [{"nome_fase": "Semifinal", "confrontos": [[2, 14, 9, 0, 1]]}]

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_fases_em_andamento(conn, invalidas)

    assert ler_fases_em_andamento(conn) == FASES_EM_ANDAMENTO


def test_gravar_fases_em_andamento_nao_faz_commit(conn):
    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    assert conn.in_transaction
    conn.rollback()
    assert ler_fases_em_andamento(conn) == []


def test_gravar_fases_em_andamento_nao_altera_a_lista_recebida(conn):
    original = copy.deepcopy(FASES_EM_ANDAMENTO)

    gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    assert FASES_EM_ANDAMENTO == original


def test_ler_fases_em_andamento_nao_abre_transacao(conn):
    with conn:
        gravar_fases_em_andamento(conn, FASES_EM_ANDAMENTO)

    ler_fases_em_andamento(conn)

    assert not conn.in_transaction
