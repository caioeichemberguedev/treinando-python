"""Integração E-013-T5: carreira criada pelo terminal (save em SQLite),
interrompida no meio da temporada, listada/carregada/excluída pela web.

Tudo em `tmp_path` (DIR_SAVES/ARQUIVO_EQUIPES via monkeypatch): o `saves/`
real e o `equipes.json` real nunca são tocados.
"""

import os

import pytest
from fastapi.testclient import TestClient

import menu
import persistencia
import web.estado as estado
from dados.conexao import abrir
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    persistencia.restaurar_equipes_padrao()  # grava no equipes.json de teste
    yield


def _teclado_sai_depois_da_primeira_fase(monkeypatch):
    """"1" para campeonato/time/pênaltis; "sair" no prompt entre fases."""
    perguntas = []

    def responder(mensagem=""):
        perguntas.append(mensagem)
        return "sair" if "sair" in mensagem else "1"

    monkeypatch.setattr("builtins.input", responder)
    return perguntas


def _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch):
    perguntas = _teclado_sai_depois_da_primeira_fase(monkeypatch)
    menu.novo_jogo(persistencia.carregar_equipes())
    assert any("sair" in p for p in perguntas)
    saves = persistencia.listar_saves()
    assert len(saves) == 1
    return saves[0]


def test_carreira_do_terminal_salva_no_meio_e_carregada_pela_web(monkeypatch):
    nome = _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch)
    caminho = persistencia._caminho_save(nome)
    assert caminho.endswith(".db") and os.path.exists(caminho)

    dados = persistencia.carregar_jogo_salvo(nome)
    # 16 times no 1º campeonato → depois das oitavas sobram 8.
    assert len(dados["classificados"]) == 8
    assert dados["temporada"] == 2026
    assert dados["historico"] == []
    with abrir(caminho, somente_leitura=True) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    bytes_antes = open(caminho, "rb").read()

    resposta = client.get("/saves")
    assert resposta.status_code == 200
    assert nome in resposta.text

    resposta = client.post(f"/saves/{nome}/carregar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"
    jogo = estado.obter_jogo()
    assert jogo is not None
    assert [t.id for t in jogo.classificados] == [t.id for t in dados["classificados"]]

    fase = client.get("/fase")
    assert fase.status_code == 200

    # Listar/carregar pela web não regrava o save.
    assert open(caminho, "rb").read() == bytes_antes


def test_excluir_pela_web_apaga_o_arquivo_sem_conexao_presa(monkeypatch):
    nome = _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch)
    caminho = persistencia._caminho_save(nome)

    # Exercita todas as leituras antes de excluir (listar, carregar, confirmar).
    assert client.get("/saves").status_code == 200
    assert client.post(f"/saves/{nome}/carregar", follow_redirects=False).status_code == 303
    assert client.get(f"/saves/{nome}/excluir").status_code == 200

    resposta = client.post(f"/saves/{nome}/excluir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/saves"

    assert not os.path.exists(caminho)
    assert os.listdir(persistencia.DIR_SAVES) == []
    assert nome not in client.get("/saves").text
    assert client.post(f"/saves/{nome}/excluir", follow_redirects=False).status_code == 404
    assert client.post(f"/saves/{nome}/carregar", follow_redirects=False).status_code == 404
    # Carregar inexistente não recria o arquivo.
    assert not os.path.exists(caminho)


def test_terminal_continua_carreira_salva_e_conclui_temporada(monkeypatch):
    """Carregar pelo menu (`carregar_jogo`) e jogar até o fim: o save passa
    para a próxima temporada com o histórico da temporada jogada."""
    nome = _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch)
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: False)
    monkeypatch.setattr("builtins.input", lambda mensagem="": "1")

    menu.carregar_jogo(persistencia.carregar_equipes())

    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert len(dados["historico"]) == 1
    nomes_fases = [fase["nome_fase"] for fase in dados["historico"][0]["fases"]]
    assert len(nomes_fases) == 3  # quartas, semi, final (as oitavas foram antes do "sair")
    assert persistencia.excluir_jogo_salvo(nome) is True
    assert not os.path.exists(persistencia._caminho_save(nome))
