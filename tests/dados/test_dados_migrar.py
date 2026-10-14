"""Testes de `dados.migrar` com migrações falsas numa pasta temporária."""

import sqlite3

import pytest

from dados.conexao import conectar
from dados.migrar import migrar, versao_atual, versao_do_banco


def _tabelas(conn):
    linhas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [linha["name"] for linha in linhas]


@pytest.fixture
def pasta_migracoes(tmp_path):
    """Três migrações falsas; a 010 depende da 002, que depende da 001."""
    pasta = tmp_path / "migracoes"
    pasta.mkdir()
    (pasta / "001_a.sql").write_text(
        "-- primeira\nCREATE TABLE a (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )
    (pasta / "002_b.sql").write_text(
        "CREATE TABLE b (id INTEGER PRIMARY KEY,\n"
        "    a_id INTEGER REFERENCES a(id));\n"
        "INSERT INTO a (id) VALUES (1);\n",
        encoding="utf-8",
    )
    # Sem ";" no último comando e com comentário no fim, sem quebra de linha.
    (pasta / "010_c.sql").write_text(
        "INSERT INTO b (id, a_id) VALUES (1, 1);\n"
        "CREATE TABLE c (nome TEXT NOT NULL) -- ação",
        encoding="utf-8",
    )
    # Não seguem NNN_nome.sql: ignorados.
    (pasta / "leia-me.txt").write_text("nada", encoding="utf-8")
    (pasta / "099_rascunho.sql.bak").write_text("LIXO;", encoding="utf-8")
    (pasta / "sem_numero.sql").write_text("LIXO;", encoding="utf-8")
    (pasta / "050-hifen.sql").write_text("LIXO;", encoding="utf-8")
    return pasta


@pytest.fixture
def banco():
    conn = conectar(":memory:")
    yield conn
    conn.close()


def test_versao_atual_e_o_maior_numero(pasta_migracoes):
    assert versao_atual(pasta_migracoes) == 10


def test_versao_atual_de_pasta_vazia_ou_inexistente(tmp_path):
    assert versao_atual(tmp_path) == 0
    assert versao_atual(tmp_path / "nao_existe") == 0


def test_migrar_do_zero_aplica_todas_em_ordem(banco, pasta_migracoes):
    assert versao_do_banco(banco) == 0
    migrar(banco, pasta_migracoes)
    assert versao_do_banco(banco) == 10
    assert _tabelas(banco) == ["a", "b", "c"]
    assert banco.execute("SELECT a_id FROM b").fetchone()["a_id"] == 1
    assert not banco.in_transaction


def test_migrar_de_novo_nao_faz_nada(banco, pasta_migracoes):
    migrar(banco, pasta_migracoes)
    with banco:
        banco.execute("INSERT INTO c (nome) VALUES (?)", ("x",))
    migrar(banco, pasta_migracoes)
    assert versao_do_banco(banco) == 10
    assert banco.execute("SELECT COUNT(*) FROM c").fetchone()[0] == 1
    assert banco.execute("SELECT COUNT(*) FROM b").fetchone()[0] == 1


def test_banco_na_versao_2_so_aplica_a_10(banco, pasta_migracoes, tmp_path):
    parcial = tmp_path / "parcial"
    parcial.mkdir()
    for nome in ("001_a.sql", "002_b.sql"):
        (parcial / nome).write_bytes((pasta_migracoes / nome).read_bytes())
    migrar(banco, parcial)
    assert versao_do_banco(banco) == 2

    # Se a 001/002 rodassem de novo, o CREATE TABLE falharia.
    migrar(banco, pasta_migracoes)
    assert versao_do_banco(banco) == 10
    assert _tabelas(banco) == ["a", "b", "c"]
    assert banco.execute("SELECT COUNT(*) FROM a").fetchone()[0] == 1


def test_migracao_invalida_desfaz_tudo_daquele_arquivo(banco, tmp_path):
    pasta = tmp_path / "com_erro"
    pasta.mkdir()
    (pasta / "001_ok.sql").write_text(
        "CREATE TABLE ok (id INTEGER PRIMARY KEY);", encoding="utf-8"
    )
    (pasta / "002_quebrada.sql").write_text(
        "CREATE TABLE parcial (id INTEGER PRIMARY KEY);\n"
        "INSERT INTO ok (id) VALUES (1);\n"
        "ISSO NAO E SQL;\n",
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.Error):
        migrar(banco, pasta)
    assert versao_do_banco(banco) == 1
    assert _tabelas(banco) == ["ok"]
    assert banco.execute("SELECT COUNT(*) FROM ok").fetchone()[0] == 0
    assert not banco.in_transaction


def test_migracao_invalida_em_arquivo_nao_deixa_rastro(tmp_path):
    pasta = tmp_path / "com_erro"
    pasta.mkdir()
    (pasta / "001_quebrada.sql").write_text(
        "CREATE TABLE parcial (id INTEGER);\nSELEC 1;\n", encoding="utf-8"
    )
    caminho = tmp_path / "save.db"
    conn = conectar(caminho)
    try:
        with pytest.raises(sqlite3.Error):
            migrar(conn, pasta)
    finally:
        conn.close()
    conn = conectar(caminho, criar=False)
    try:
        assert versao_do_banco(conn) == 0
        assert _tabelas(conn) == []
    finally:
        conn.close()


def test_banco_mais_novo_que_o_jogo_da_value_error(banco, pasta_migracoes):
    banco.execute("PRAGMA user_version = 11")
    with pytest.raises(ValueError):
        migrar(banco, pasta_migracoes)
    assert versao_do_banco(banco) == 11
    assert _tabelas(banco) == []


def test_fixture_conn_esta_migrada_ate_a_versao_atual(conn):
    assert versao_do_banco(conn) == versao_atual()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
