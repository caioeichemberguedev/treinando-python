import pytest
from fastapi.testclient import TestClient

import web.estado as estado
from equipe import Equipe
from web.main import app
from web.rotas import equipes, historico, jogo, saves

client = TestClient(app)


@pytest.fixture(autouse=True)
def sem_jogo_em_andamento(monkeypatch):
    """Reseta o "jogo em andamento" em memória entre os testes."""
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _iniciar_jogo_com_historico(historico):
    times = [Equipe("Time A"), Equipe("Time B")]
    estado.iniciar_jogo("Campeonato Teste", times[0], 2026 + len(historico), times, historico=historico)


def test_historico_sem_jogo_em_andamento_retorna_404():
    resposta = client.get("/historico")

    assert resposta.status_code == 404


def test_historico_vazio_mostra_mensagem():
    _iniciar_jogo_com_historico([])

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "Nenhuma temporada concluída ainda" in resposta.text


def test_historico_lista_todas_as_temporadas_com_campeao():
    historico = [
        {"temporada": 2026, "campeao": "Time A", "fases": []},
        {"temporada": 2027, "campeao": "Time B", "fases": []},
        {"temporada": 2028, "campeao": "Time Campeao Final", "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "Nenhuma temporada concluída ainda" not in resposta.text
    for temporada_info in historico:
        assert str(temporada_info["temporada"]) in resposta.text
        assert temporada_info["campeao"] in resposta.text


def test_navegacao_tem_link_para_historico():
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert 'href="http://testserver/historico"' in resposta.text or 'href="/historico"' in resposta.text


def test_nomes_de_rota_sao_unicos_na_app():
    """`url_for` do Jinja resolve pelo nome da função de rota, então nenhum
    nome pode se repetir entre os routers registrados em `web/main.py`."""
    routers = [equipes.router, historico.router, jogo.router, saves.router]
    nomes = [rota.name for router in routers for rota in router.routes] + ["inicio"]

    assert len(nomes) == len(set(nomes))


def test_historico_aceita_campeao_como_objeto_equipe():
    """A T2 grava `campeao` como `Equipe` (não string) no fluxo web — a tela
    precisa exibir o nome do mesmo jeito."""
    historico = [{"temporada": 2026, "campeao": Equipe("Time Objeto"), "fases": []}]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "Time Objeto" in resposta.text
    assert "Equipe(" not in resposta.text and "object at" not in resposta.text


def test_historico_escapa_html_no_nome_do_campeao():
    historico = [{"temporada": 2026, "campeao": "<script>alert(1)</script>", "fases": []}]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text


def test_historico_mantem_a_ordem_das_temporadas():
    historico = [
        {"temporada": 2026, "campeao": "Primeiro Campeao", "fases": []},
        {"temporada": 2027, "campeao": "Segundo Campeao", "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    texto = client.get("/historico").text

    assert texto.index("Primeiro Campeao") < texto.index("Segundo Campeao")


def test_historico_nao_e_alterado_pela_leitura():
    historico = [{"temporada": 2026, "campeao": "Time A", "fases": []}]
    _iniciar_jogo_com_historico(historico)

    client.get("/historico")
    client.get("/historico")

    assert len(estado.obter_jogo().historico) == 1
