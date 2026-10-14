"""Casos de borda de `dados.conexao` e `dados.migrar` (Windows: arquivos
precisam ficar livres para apagar depois de fechar a conexão)."""

import os
import sqlite3

import pytest

from dados.conexao import abrir, conectar
from dados.migrar import migrar, versao_do_banco


def test_abrir_sem_criar_arquivo_inexistente_falha_e_nao_cria(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        with abrir(caminho, criar=False):
            pass  # pragma: no cover
    assert not caminho.exists()


def test_abrir_somente_leitura_inexistente_nao_cria(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        with abrir(caminho, somente_leitura=True):
            pass  # pragma: no cover
    assert not caminho.exists()


def test_somente_leitura_ignora_criar_true(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        conectar(caminho, criar=True, somente_leitura=True)
    assert not caminho.exists()


def test_somente_leitura_bloqueia_insert_e_libera_arquivo(tmp_path):
    caminho = tmp_path / "ro.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with abrir(caminho, somente_leitura=True) as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO t (x) VALUES (1)")
    os.remove(caminho)
    assert not caminho.exists()


def test_excecao_dentro_de_with_conn_desfaz_e_libera_arquivo(tmp_path):
    caminho = tmp_path / "rollback.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with pytest.raises(ValueError):
        with abrir(caminho) as conn:
            with conn:
                conn.execute("INSERT INTO t (x) VALUES (1)")
                raise ValueError("expulso")
    with abrir(caminho, criar=False) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    os.remove(caminho)


def test_excecao_com_transacao_aberta_sem_commit_libera_arquivo(tmp_path):
    caminho = tmp_path / "pendente.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with pytest.raises(KeyboardInterrupt):
        with abrir(caminho) as conn:
            conn.execute("INSERT INTO t (x) VALUES (1)")
            assert conn.in_transaction
            raise KeyboardInterrupt
    # Nada foi commitado e o arquivo (e o journal) ficam livres.
    with abrir(caminho, criar=False) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
    os.remove(caminho)
    assert not list(tmp_path.iterdir())


def test_migracao_quebrada_em_arquivo_libera_para_apagar(tmp_path):
    pasta = tmp_path / "mig"
    pasta.mkdir()
    (pasta / "001_ruim.sql").write_text("CREATE TABLE a (x);\nXYZ;\n", encoding="utf-8")
    caminho = tmp_path / "save.db"
    with pytest.raises(sqlite3.Error):
        with abrir(caminho) as conn:
            migrar(conn, pasta)
    os.remove(caminho)
    assert not caminho.exists()


def test_migrar_com_pasta_inexistente_nao_faz_nada(tmp_path):
    conn = conectar(":memory:")
    try:
        migrar(conn, tmp_path / "nao_existe")
        assert versao_do_banco(conn) == 0
    finally:
        conn.close()


def test_migrar_pasta_inexistente_com_banco_versionado_da_value_error(tmp_path):
    conn = conectar(":memory:")
    try:
        conn.execute("PRAGMA user_version = 1")
        with pytest.raises(ValueError):
            migrar(conn, tmp_path / "nao_existe")
    finally:
        conn.close()


def test_migracao_vazia_ou_so_comentario_avanca_versao(tmp_path):
    pasta = tmp_path / "mig"
    pasta.mkdir()
    (pasta / "001_vazia.sql").write_text("", encoding="utf-8")
    (pasta / "002_comentario.sql").write_text("-- só comentário", encoding="utf-8")
    conn = conectar(":memory:")
    try:
        migrar(conn, pasta)
        assert versao_do_banco(conn) == 2
    finally:
        conn.close()


def test_migrar_commita_pendencia_e_nao_deixa_transacao(tmp_path):
    """`executescript` faz COMMIT do que estava pendente antes de rodar."""
    pasta = tmp_path / "mig"
    pasta.mkdir()
    (pasta / "001_a.sql").write_text("CREATE TABLE a (x INTEGER);", encoding="utf-8")
    caminho = tmp_path / "save.db"
    with abrir(caminho) as conn:
        migrar(conn, pasta)
        assert not conn.in_transaction
    with abrir(caminho, criar=False) as conn:
        assert versao_do_banco(conn) == 1
    os.remove(caminho)


def test_migracao_com_utf8_e_acento(tmp_path):
    pasta = tmp_path / "mig"
    pasta.mkdir()
    (pasta / "001_a.sql").write_text(
        "CREATE TABLE t (nome TEXT);\nINSERT INTO t VALUES ('São Paulo');",
        encoding="utf-8",
    )
    conn = conectar(":memory:")
    try:
        migrar(conn, pasta)
        assert conn.execute("SELECT nome FROM t").fetchone()["nome"] == "São Paulo"
    finally:
        conn.close()
