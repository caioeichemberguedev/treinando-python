"""Testes de `dados.conexao` (conectar/abrir)."""

import os
import sqlite3

import pytest

from dados import conexao
from dados.conexao import abrir, conectar


def test_conectar_liga_chaves_estrangeiras_e_linhas_por_nome():
    conn = conectar(":memory:")
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        linha = conn.execute("SELECT 7 AS numero").fetchone()
        assert isinstance(linha, sqlite3.Row)
        assert linha["numero"] == 7
    finally:
        conn.close()


def test_conectar_cria_arquivo_por_padrao(tmp_path):
    caminho = tmp_path / "novo.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    assert caminho.exists()


def test_conectar_sem_criar_falha_e_nao_cria_arquivo(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        conectar(caminho, criar=False)
    assert not caminho.exists()


def test_conectar_sem_criar_abre_arquivo_existente_para_gravar(tmp_path):
    caminho = tmp_path / "existe.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with abrir(caminho, criar=False) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with conn:
            conn.execute("INSERT INTO t (x) VALUES (?)", (1,))
        assert conn.execute("SELECT x FROM t").fetchone()["x"] == 1


def test_somente_leitura_nao_deixa_gravar(tmp_path):
    caminho = tmp_path / "leitura.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with abrir(caminho, somente_leitura=True) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE outra (y INTEGER)")


def test_somente_leitura_nao_cria_arquivo(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    with pytest.raises(sqlite3.OperationalError):
        conectar(caminho, somente_leitura=True)
    assert not caminho.exists()


def test_caminho_com_espaco_e_acento(tmp_path):
    pasta = tmp_path / "pasta com espaço é"
    pasta.mkdir()
    caminho = pasta / "carreira ção #1.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            conn.execute("INSERT INTO t (x) VALUES (?)", (3,))
    with abrir(caminho, criar=False) as conn:
        assert conn.execute("SELECT x FROM t").fetchone()["x"] == 3
    with abrir(caminho, somente_leitura=True) as conn:
        assert conn.execute("SELECT x FROM t").fetchone()["x"] == 3
    with pytest.raises(sqlite3.OperationalError):
        conectar(pasta / "outro.db", criar=False)
    assert not (pasta / "outro.db").exists()


def test_abrir_fecha_a_conexao_e_libera_o_arquivo(tmp_path):
    caminho = tmp_path / "fecha.db"
    with abrir(caminho) as conn:
        with conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    os.remove(caminho)
    assert not caminho.exists()


def test_abrir_fecha_a_conexao_mesmo_com_excecao(tmp_path):
    caminho = tmp_path / "erro.db"
    with pytest.raises(RuntimeError, match="falhou"):
        with abrir(caminho) as conn:
            conn.execute("CREATE TABLE t (x INTEGER)")
            raise RuntimeError("falhou")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    os.remove(caminho)
    assert not caminho.exists()


def test_timeout_padrao():
    assert conexao.TIMEOUT_SEGUNDOS == 5
