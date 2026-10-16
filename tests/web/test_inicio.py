import pytest
from fastapi.testclient import TestClient

import catalogo
import web.estado as estado
from equipe import Equipe
from web.main import app

client = TestClient(app)

SAO_PAULO = 1


@pytest.fixture(autouse=True)
def sem_jogo_em_andamento(monkeypatch):
    """Reseta o "jogo em andamento" em memória entre os testes."""
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _iniciar_jogo(temporada=2028):
    escolhido = Equipe("Nome antigo", id=SAO_PAULO)
    rival = Equipe("Rival", id=2)
    estado.iniciar_jogo("Copa do Brasil", escolhido, temporada, [escolhido, rival])


def test_tela_inicial_abre():
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "Simulador de Copa" in resposta.text


def test_inicio_sem_jogo_mostra_blocos_sem_continuar_carreira():
    texto = client.get("/").text

    assert 'class="blocos"' in texto
    for url in ("/novo-jogo", "/saves", "/equipes"):
        assert f'{url}"' in texto
    assert '/carreira"' not in texto
    assert "Continuar carreira" not in texto


def test_inicio_com_jogo_mostra_continuar_carreira_primeiro():
    _iniciar_jogo(temporada=2028)

    texto = client.get("/").text

    assert "Continuar carreira" in texto
    assert '/carreira"' in texto
    assert catalogo.nome_do_time(SAO_PAULO) == "São Paulo"
    assert "São Paulo" in texto
    assert "Nome antigo" not in texto
    assert "Temporada 2028" in texto
    assert texto.index("Continuar carreira") < texto.index("Novo jogo")


def test_inicio_nao_altera_jogo_em_andamento():
    _iniciar_jogo()
    antes = estado.obter_jogo()

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert estado.obter_jogo() is antes


# --- Casos de borda (game-tester, M-021) ---

@pytest.mark.parametrize("com_jogo", [False, True])
def test_inicio_nao_tem_link_para_admin(com_jogo):
    if com_jogo:
        _iniciar_jogo()

    texto = client.get("/").text

    assert "/admin" not in texto


def test_inicio_com_jogo_mostra_escudo_no_bloco_continuar():
    _iniciar_jogo()

    texto = client.get("/").text
    inicio = texto.index("bloco-destaque")
    fim = texto.index("Novo jogo")

    assert '<svg class="escudo"' in texto[inicio:fim]


def test_inicio_com_time_fora_do_catalogo_nao_quebra_e_escapa_nome():
    escolhido = Equipe("<b>Time X</b>", id=999)
    estado.iniciar_jogo("Copa do Brasil", escolhido, 2026, [escolhido])

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert "Continuar carreira" in resposta.text
    assert "<b>Time X</b>" not in resposta.text


def test_inicio_volta_sem_continuar_depois_de_encerrar_jogo():
    _iniciar_jogo()
    assert "Continuar carreira" in client.get("/").text

    estado.encerrar_jogo()

    texto = client.get("/").text
    assert "Continuar carreira" not in texto
    assert '/historico"' not in texto


def test_inicio_nao_usa_javascript():
    _iniciar_jogo()

    texto = client.get("/").text

    assert "<script" not in texto.lower()
    assert "onclick" not in texto.lower()
