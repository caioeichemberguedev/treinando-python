"""Testes da migração 002 — fases da temporada em andamento (E-014-T2)."""

import shutil
import sqlite3

import pytest

from dados.conexao import conectar
from dados.migrar import PASTA_MIGRACOES, migrar, versao_atual, versao_do_banco
from dados.repositorios.carreira import gravar_carreira, ler_carreira
from dados.repositorios.historico import (
    gravar_historico,
    ler_fases_em_andamento,
    ler_historico,
)
from equipe import Equipe

ARQUIVO_002 = PASTA_MIGRACOES / "002_fases_em_andamento.sql"

TABELAS_V2 = {
    "times", "carreira", "classificados", "temporadas", "fases", "confrontos",
    "fases_em_andamento", "confrontos_em_andamento",
}

HISTORICO = [{
    "temporada": 2026,
    "campeao": 1,
    "fases": [
        {"nome_fase": "Semifinal - Copa do Brasil",
         "confrontos": [[1, 2, 1, 4, 2], [3, 4, 4, 3, 5]]},
        {"nome_fase": "Final - Copa do Brasil",
         "confrontos": [[1, 4, 1, 5, 4]]},
    ],
}]


def _tabelas(conn):
    return {
        linha[0] for linha in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _contar(conn, tabela):
    # `tabela` é sempre um nome fixo do próprio teste, nunca valor de fora.
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


@pytest.fixture
def pasta_so_001(tmp_path):
    """Pasta de migrações só com a 001 real — monta um banco na versão 1."""
    pasta = tmp_path / "migracoes_v1"
    pasta.mkdir()
    shutil.copy(PASTA_MIGRACOES / "001_inicial.sql", pasta / "001_inicial.sql")
    return pasta


@pytest.fixture
def banco():
    conn = conectar(":memory:")
    yield conn
    conn.close()


def _inserir_fase(conn, ordem=1, nome="Oitavas de final"):
    cursor = conn.execute(
        "INSERT INTO fases_em_andamento (ordem, nome) VALUES (?, ?)",
        (ordem, nome),
    )
    return cursor.lastrowid


def _inserir_confronto(conn, fase_id, *, ordem=1, time_a=1, time_b=2,
                       vencedor=1, gols_a=5, gols_b=4):
    conn.execute(
        "INSERT INTO confrontos_em_andamento (fase_id, ordem, time_a_id, "
        "time_b_id, vencedor_id, gols_a, gols_b) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fase_id, ordem, time_a, time_b, vencedor, gols_a, gols_b),
    )


# --- estrutura ---------------------------------------------------------------

def test_do_zero_ate_a_2_cria_as_oito_tabelas(banco):
    migrar(banco)

    assert versao_atual() == 2
    assert versao_do_banco(banco) == 2
    assert _tabelas(banco) == TABELAS_V2


def test_cria_o_indice_dos_confrontos_em_andamento(conn):
    indices = {
        linha[0] for linha in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'confrontos_em_andamento' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert indices == {"idx_confrontos_em_andamento_fase"}


def test_arquivo_nao_controla_transacao_nem_versao():
    texto = ARQUIVO_002.read_text(encoding="utf-8").upper()
    for proibido in ("BEGIN", "COMMIT", "USER_VERSION"):
        assert proibido not in texto


# --- banco v1 migrando para v2 -----------------------------------------------

def test_banco_v1_com_carreira_e_historico_migra_sem_perder_nada(banco, pasta_so_001):
    migrar(banco, pasta_so_001)
    assert versao_do_banco(banco) == 1
    assert "fases_em_andamento" not in _tabelas(banco)
    escolhido = Equipe("Time 1", 100, 50, 0, forca=70, cores=["#FF0000"], id=1)
    outros = [Equipe(f"Time {i}", 80, 40, 1, forca=60, id=i) for i in (2, 3, 4)]
    with banco:
        gravar_carreira(banco, "Copa do Brasil", 2027, escolhido,
                        [escolhido, *outros])
        gravar_historico(banco, HISTORICO)
    carreira_antes = ler_carreira(banco)

    migrar(banco)

    assert versao_do_banco(banco) == 2
    assert _tabelas(banco) == TABELAS_V2
    assert ler_historico(banco) == HISTORICO
    carreira_depois = ler_carreira(banco)
    assert carreira_depois["campeonato"] == carreira_antes["campeonato"]
    assert carreira_depois["temporada"] == carreira_antes["temporada"]
    assert carreira_depois["time_escolhido"].to_dict() == escolhido.to_dict()
    assert [t.to_dict() for t in carreira_depois["classificados"]] == [
        t.to_dict() for t in carreira_antes["classificados"]
    ]
    assert _contar(banco, "fases_em_andamento") == 0
    assert _contar(banco, "confrontos_em_andamento") == 0
    assert ler_fases_em_andamento(banco) == []


# --- regras (CHECK / UNIQUE / cascata) ---------------------------------------

def test_aceita_fase_e_confronto_validos(conn):
    fase_id = _inserir_fase(conn)
    _inserir_confronto(conn, fase_id)
    _inserir_confronto(conn, fase_id, ordem=2, time_a=3, time_b=4,
                       vencedor=4, gols_a=0, gols_b=0)

    assert _contar(conn, "confrontos_em_andamento") == 2


@pytest.mark.parametrize("campos", [
    {"vencedor": 9},              # vencedor fora do par
    {"time_b": 1},                # time contra si mesmo
    {"gols_a": -1},               # gols negativos
    {"gols_b": -2},
    {"vencedor": None},           # sem vencedor
])
def test_confronto_invalido_da_integrity_error(conn, campos):
    fase_id = _inserir_fase(conn)

    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(conn, fase_id, **campos)


def test_confronto_de_fase_inexistente_da_integrity_error(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(conn, 999)


def test_ordem_de_confronto_repetida_na_mesma_fase_da_integrity_error(conn):
    fase_id = _inserir_fase(conn)
    _inserir_confronto(conn, fase_id)

    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(conn, fase_id, time_a=3, time_b=4, vencedor=3)


@pytest.mark.parametrize("ordem", [0, -1])
def test_ordem_de_fase_menor_que_1_da_integrity_error(conn, ordem):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(conn, ordem=ordem)


def test_ordem_de_fase_repetida_da_integrity_error(conn):
    _inserir_fase(conn, ordem=1)

    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(conn, ordem=1, nome="Quartas de final")


def test_fase_sem_nome_da_integrity_error(conn):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(conn, nome=None)


def test_apagar_fase_apaga_os_confrontos_em_cascata(conn):
    fase_1 = _inserir_fase(conn, ordem=1)
    fase_2 = _inserir_fase(conn, ordem=2, nome="Quartas de final")
    _inserir_confronto(conn, fase_1)
    _inserir_confronto(conn, fase_1, ordem=2, time_a=3, time_b=4, vencedor=3)
    _inserir_confronto(conn, fase_2, time_a=1, time_b=3, vencedor=1)

    conn.execute("DELETE FROM fases_em_andamento WHERE id = ?", (fase_1,))

    assert _contar(conn, "fases_em_andamento") == 1
    assert _contar(conn, "confrontos_em_andamento") == 1


def test_tabelas_novas_nao_mexem_no_historico(conn):
    with conn:
        gravar_historico(conn, HISTORICO)
    fase_id = _inserir_fase(conn)
    _inserir_confronto(conn, fase_id)

    conn.execute("DELETE FROM fases_em_andamento")

    assert ler_historico(conn) == HISTORICO
