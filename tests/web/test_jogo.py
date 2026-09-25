import json

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """Isola os testes de um `equipes.json` de teste (nunca o real do
    projeto) e reseta o "jogo em andamento" em memória entre os testes.
    """
    dados = {
        "Campeonato Teste": [
            {"nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Outro Campeonato": [
            {"nome": "Time C", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Time D", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def test_tela_novo_jogo_lista_campeonatos():
    resposta = client.get("/novo-jogo")

    assert resposta.status_code == 200
    assert "Campeonato Teste" in resposta.text
    assert "Outro Campeonato" in resposta.text


def test_escolher_campeonato_valido_mostra_os_times_certos():
    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"}, follow_redirects=False)

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "Time C" not in resposta.text


def test_escolher_campeonato_inexistente_retorna_404():
    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Fantasma"})

    assert resposta.status_code == 404


def test_escolher_time_valido_redireciona_e_preenche_o_estado():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "Time A"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.campeonato == "Campeonato Teste"
    assert jogo.time_escolhido == "Time A"
    assert jogo.temporada == 2026
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}


def test_escolher_time_inexistente_retorna_404():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "Time Fantasma"},
    )

    assert resposta.status_code == 404


def test_fase_placeholder_ainda_nao_implementada():
    resposta = client.get("/fase")

    assert resposta.status_code == 404
