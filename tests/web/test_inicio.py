from fastapi.testclient import TestClient

from web.main import app

client = TestClient(app)


def test_tela_inicial_abre():
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "Simulador de Copa" in resposta.text
