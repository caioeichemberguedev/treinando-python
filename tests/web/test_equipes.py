import json

import pytest
from fastapi.testclient import TestClient

import persistencia
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """Isola os testes de um `equipes.json` de teste (nunca o real do
    projeto).
    """
    dados = {
        "Campeonato Teste": [
            {"nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Outro Campeonato": [
            {"nome": "Time C", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    yield arquivo


def _ler_equipes_salvas(arquivo):
    return json.loads(arquivo.read_text(encoding="utf-8"))


def test_tela_equipes_lista_campeonatos():
    resposta = client.get("/equipes")

    assert resposta.status_code == 200
    assert "Campeonato Teste" in resposta.text
    assert "Outro Campeonato" in resposta.text


def test_tela_equipes_campeonato_lista_os_times_certos():
    resposta = client.get("/equipes/Campeonato Teste")

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "Time C" not in resposta.text


def test_tela_equipes_campeonato_inexistente_retorna_404():
    resposta = client.get("/equipes/Campeonato Fantasma")

    assert resposta.status_code == 404


def test_adicionar_equipe_valida_aparece_na_lista_e_persiste(equipes_de_teste):
    resposta = client.post(
        "/equipes/Campeonato Teste/adicionar", data={"nome": "Time Novo"}, follow_redirects=False
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"].endswith("/equipes/Campeonato%20Teste")

    resposta_lista = client.get("/equipes/Campeonato Teste")
    assert "Time Novo" in resposta_lista.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    nomes = [time["nome"] for time in dados["Campeonato Teste"]]
    assert "Time Novo" in nomes


def test_adicionar_equipe_com_nome_vazio_nao_altera_a_lista(equipes_de_teste):
    resposta = client.post("/equipes/Campeonato Teste/adicionar", data={"nome": "   "})

    assert resposta.status_code == 400
    assert "Nome vazio" in resposta.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    assert len(dados["Campeonato Teste"]) == 2


def test_adicionar_equipe_duplicada_nao_altera_a_lista_e_mostra_erro(equipes_de_teste):
    resposta = client.post("/equipes/Campeonato Teste/adicionar", data={"nome": "Time A"})

    assert resposta.status_code == 400
    assert "já existe" in resposta.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    assert len(dados["Campeonato Teste"]) == 2


def test_confirmar_remocao_mostra_tela_de_confirmacao_sem_remover(equipes_de_teste):
    resposta = client.get("/equipes/Campeonato Teste/Time A/remover")

    assert resposta.status_code == 200
    assert "certeza" in resposta.text.lower()
    assert "Time A" in resposta.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    nomes = [time["nome"] for time in dados["Campeonato Teste"]]
    assert "Time A" in nomes


def test_remover_equipe_existente_reduz_a_lista_e_persiste(equipes_de_teste):
    resposta = client.post("/equipes/Campeonato Teste/Time A/remover", follow_redirects=False)

    assert resposta.status_code == 303

    resposta_lista = client.get("/equipes/Campeonato Teste")
    assert "Time A" not in resposta_lista.text
    assert "Time B" in resposta_lista.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    nomes = [time["nome"] for time in dados["Campeonato Teste"]]
    assert nomes == ["Time B"]


def test_remover_equipe_inexistente_retorna_404():
    resposta = client.post("/equipes/Campeonato Teste/Time Fantasma/remover")

    assert resposta.status_code == 404


def test_renomear_equipe_muda_o_nome_e_persiste(equipes_de_teste):
    resposta = client.post(
        "/equipes/Campeonato Teste/Time A/renomear", data={"nome_novo": "Time Renomeado"}, follow_redirects=False
    )

    assert resposta.status_code == 303

    resposta_lista = client.get("/equipes/Campeonato Teste")
    assert "Time Renomeado" in resposta_lista.text
    assert "Time A" not in resposta_lista.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    nomes = [time["nome"] for time in dados["Campeonato Teste"]]
    assert "Time Renomeado" in nomes


def test_renomear_equipe_com_nome_vazio_nao_altera_a_lista(equipes_de_teste):
    resposta = client.post("/equipes/Campeonato Teste/Time A/renomear", data={"nome_novo": "   "})

    assert resposta.status_code == 400
    assert "Nome vazio" in resposta.text

    dados = _ler_equipes_salvas(equipes_de_teste)
    nomes = [time["nome"] for time in dados["Campeonato Teste"]]
    assert "Time A" in nomes


def test_renomear_equipe_inexistente_retorna_404():
    resposta = client.post("/equipes/Campeonato Teste/Time Fantasma/renomear", data={"nome_novo": "Qualquer"})

    assert resposta.status_code == 404
