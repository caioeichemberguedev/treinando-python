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
        "Copa Teste": [
            {"nome": "Copa E", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa F", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa G", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa H", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
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


def test_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.get("/fase")

    assert resposta.status_code == 404


def test_avancar_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.post("/fase/avancar")

    assert resposta.status_code == 404


def test_campeao_sem_jogo_definido_retorna_404():
    resposta = client.get("/campeao")

    assert resposta.status_code == 404


def test_fase_mostra_o_nome_da_fase_e_os_confrontos():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = client.get("/fase")

    assert resposta.status_code == 200
    assert "Final" in resposta.text
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text


def test_fase_repetida_nao_recalcula_o_resultado():
    """GET /fase repetido (sem passar por /fase/avancar) tem que mostrar
    sempre o mesmo resultado já decidido, sem sortear de novo a cada request.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    primeira = client.get("/fase")
    segunda = client.get("/fase")

    assert primeira.text == segunda.text


def test_fluxo_completo_ate_o_campeao_com_dois_times():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta_fase = client.get("/fase")
    assert resposta_fase.status_code == 200

    resposta_avancar = client.post("/fase/avancar", follow_redirects=False)
    assert resposta_avancar.status_code == 303
    assert resposta_avancar.headers["location"] == "/campeao"

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text
    assert "Time A" in resposta_campeao.text or "Time B" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao in ("Time A", "Time B")
    assert jogo.campeao.titulos == 1


def test_fluxo_completo_ate_o_campeao_com_quatro_times():
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "Copa E"})

    times_esperados = {"Copa E", "Copa F", "Copa G", "Copa H"}
    rodadas = 0

    while True:
        resposta_fase = client.get("/fase")
        assert resposta_fase.status_code == 200

        resposta_avancar = client.post("/fase/avancar", follow_redirects=False)
        assert resposta_avancar.status_code == 303
        rodadas += 1

        if resposta_avancar.headers["location"] == "/campeao":
            break

        assert resposta_avancar.headers["location"] == "/fase"
        assert rodadas < 5, "Temporada com 4 times não deveria levar mais de 2 fases pra terminar."

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao in times_esperados
    assert rodadas == 2
