import json
import random

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)


def _resolver_disputa_penaltis_ate_o_fim(canto="1"):
    """Sequência de `POST /fase/penaltis` com o mesmo `canto` a cada
    cobrança, até a disputa terminar e o fluxo redirecionar de volta pra
    `/fase`. Usado quando o teste só precisa que a disputa termine (vitória
    ou derrota do time do jogador não importam), sem controlar o resultado.
    """
    client.get("/fase/penaltis")  # garante que a disputa foi criada
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return resposta
        assert resposta.headers["location"] == "/fase/penaltis"


def _passar_pela_fase_atual():
    """Segue o fluxo padrão de uma fase: `GET /fase`; se tiver o confronto do
    jogador pendente, resolve a disputa de pênaltis antes de reexibir a
    fase. Retorna a resposta final de `GET /fase` (200).
    """
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        assert resposta.headers["location"] == "/fase/penaltis"
        _resolver_disputa_penaltis_ate_o_fim()
        resposta = client.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200
    return resposta


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


def test_fase_com_confronto_do_jogador_redireciona_para_penaltis():
    """Enquanto o confronto do jogador não foi decidido, GET /fase não
    exibe a fase — redireciona pra /fase/penaltis.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"


def test_tela_penaltis_mostra_o_placar_e_pede_a_escolha_do_jogador():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = client.get("/fase/penaltis")

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "canto" in resposta.text.lower()


def test_penaltis_sem_disputa_em_andamento_retorna_404():
    resposta = client.post("/fase/penaltis", data={"canto": "1"})

    assert resposta.status_code == 404


def test_avancar_fase_com_confronto_pendente_retorna_400():
    """Não dá pra avançar de fase com o confronto do jogador ainda em
    aberto — precisa passar pela disputa de pênaltis primeiro.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    client.get("/fase")  # monta a fase (confronto_pendente ainda não decidido)

    resposta = client.post("/fase/avancar")

    assert resposta.status_code == 400


def test_fase_mostra_o_nome_da_fase_e_os_confrontos():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = _passar_pela_fase_atual()

    assert "Final" in resposta.text
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text


def test_fase_repetida_nao_recalcula_o_resultado():
    """GET /fase repetido (sem passar por /fase/avancar), depois do
    confronto do jogador decidido, tem que mostrar sempre o mesmo resultado
    já fechado, sem sortear de novo a cada request.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()

    primeira = client.get("/fase")
    segunda = client.get("/fase")

    assert primeira.text == segunda.text


def test_penaltis_corte_antecipado_decide_o_confronto_do_jogador(monkeypatch):
    """Mesmo cenário de corte antecipado de
    `tests/test_penaltis.py::test_disputa_encerra_antecipadamente_quando_alcance_e_impossivel`,
    dirigido via `/fase/penaltis`: o time do jogador abre 3x0 (sempre acerta
    o chute, o goleiro adversário nunca defende; o goleiro do jogador
    sempre defende o adversário) e a disputa termina sem completar as 5
    rodadas, sem depender de qual lado do par o jogador caiu.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    client.get("/fase/penaltis")  # garante que a disputa foi criada antes do monkeypatch

    valores = iter([1, 2, 1, 1] * 3)
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    resposta = None
    for _ in range(6):
        resposta = client.post("/fase/penaltis", data={"canto": ""}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            break
        assert resposta.headers["location"] == "/fase/penaltis"

    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    time_a, time_b, vencedor, gols_a, gols_b = jogo.fase_atual["confrontos"][0]
    assert vencedor == "Time A"
    assert vencedor.titulos == 0  # título só é contado no campeão da temporada
    if time_a == "Time A":
        assert (gols_a, gols_b) == (3, 0)
    else:
        assert (gols_a, gols_b) == (0, 3)


def test_fluxo_completo_ate_o_campeao_com_dois_times():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta_fase = _passar_pela_fase_atual()
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
        resposta_fase = _passar_pela_fase_atual()
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
