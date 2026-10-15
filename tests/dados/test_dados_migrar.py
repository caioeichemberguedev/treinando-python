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


@pytest.fixture(params=[("001_a.sql", "01_b.sql"), ("001_a.sql", "001_b.sql")])
def pasta_repetida(request, tmp_path):
    """Pasta com dois arquivos de mesmo número (M-016) e uma 002 válida."""
    pasta = tmp_path / "repetida"
    pasta.mkdir()
    for nome in request.param:
        (pasta / nome).write_text(
            f"CREATE TABLE t_{nome[:-4].replace('_', '')} (id INTEGER);",
            encoding="utf-8",
        )
    (pasta / "002_c.sql").write_text("CREATE TABLE c (id INTEGER);", encoding="utf-8")
    return pasta, request.param


def test_numero_repetido_da_value_error_em_versao_atual(pasta_repetida):
    pasta, (nome_1, nome_2) = pasta_repetida
    with pytest.raises(ValueError, match="repetido") as erro:
        versao_atual(pasta)
    mensagem = str(erro.value)
    assert "(1)" in mensagem
    assert f"{nome_1}, {nome_2}" in mensagem  # ordem alfabética


def test_numero_repetido_em_migrar_nao_toca_o_banco(banco, pasta_repetida):
    pasta, (nome_1, nome_2) = pasta_repetida
    with pytest.raises(ValueError) as erro:
        migrar(banco, pasta)
    assert nome_1 in str(erro.value)
    assert nome_2 in str(erro.value)
    assert versao_do_banco(banco) == 0
    assert _tabelas(banco) == []
    assert not banco.in_transaction


def test_mensagem_de_repetido_e_estavel_em_ordem_alfabetica(tmp_path):
    pasta = tmp_path / "ordem"
    pasta.mkdir()
    # Criados fora de ordem: a mensagem não depende do iterdir().
    for nome in ("003_z.sql", "3_b.sql", "003_a.sql"):
        (pasta / nome).write_text("SELECT 1;", encoding="utf-8")
    with pytest.raises(ValueError) as erro:
        versao_atual(pasta)
    assert "(3): 003_a.sql, 003_z.sql, 3_b.sql." in str(erro.value)


def test_fixture_conn_esta_migrada_ate_a_versao_atual(conn):
    assert versao_do_banco(conn) == versao_atual()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_migrar_real_do_zero_cria_as_oito_tabelas_ate_a_002(banco):
    """Com a pasta real `dados/migracoes/`: do zero até a versão 2 (E-013 +
    fases em andamento do E-014)."""
    assert versao_atual() == 2
    migrar(banco)
    assert versao_do_banco(banco) == versao_atual() == 2
    assert _tabelas(banco) == [
        "carreira", "classificados", "confrontos", "confrontos_em_andamento",
        "fases", "fases_em_andamento", "temporadas", "times",
    ]


def test_repetido_so_conta_arquivos_validos(tmp_path):
    """Pasta e arquivo fora do padrão com o mesmo número não contam (M-016)."""
    pasta = tmp_path / "quase_repetida"
    pasta.mkdir()
    (pasta / "001_a.sql").write_text("CREATE TABLE a (id INTEGER);", encoding="utf-8")
    (pasta / "001_pasta.sql").mkdir()
    (pasta / "001_b.sql.bak").write_text("SELECT 1;", encoding="utf-8")
    (pasta / "001-c.sql").write_text("SELECT 1;", encoding="utf-8")
    assert versao_atual(pasta) == 1


def test_pasta_real_de_migracoes_nao_tem_numero_repetido():
    assert versao_atual() >= 1
