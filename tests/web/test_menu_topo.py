"""E-022-T6: menu do topo responsivo.

Marca "Simulador de Copa" (link para `/`), links fixos "Carreiras salvas" e
"Editar equipes", "Carreira" e "Histórico" só com jogo em andamento e a
página atual marcada com `aria-current="page"` a partir do caminho da URL.
"""

import re

import pytest
from fastapi.testclient import TestClient

import web.estado as estado
from equipe import Equipe
from web.main import app

client = TestClient(app)

SAO_PAULO = 1
FLAMENGO = 2


@pytest.fixture(autouse=True)
def sem_jogo_em_andamento(monkeypatch):
    """Nenhum jogo em memória no começo de cada teste."""
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _iniciar_jogo():
    escolhido = Equipe("São Paulo", id=SAO_PAULO)
    rival = Equipe("Flamengo", id=FLAMENGO)
    estado.iniciar_jogo("Copa do Brasil", escolhido, 2026, [escolhido, rival])


def _header(texto):
    return texto[texto.index("<header"):texto.index("</header>") + len("</header>")]


def _links_atuais(header):
    """Tags `<a ...>` do header que têm `aria-current="page"`."""
    return [tag for tag in re.findall(r"<a\b[^>]*>", header) if 'aria-current="page"' in tag]


@pytest.mark.parametrize("url", ["/", "/saves", "/equipes"])
def test_sem_jogo_menu_nao_tem_carreira_nem_historico(url):
    resposta = client.get(url)

    assert resposta.status_code == 200
    header = _header(resposta.text)
    assert '/carreira"' not in header
    assert '/historico"' not in header
    assert '/carreira"' not in resposta.text


@pytest.mark.parametrize("url", ["/", "/saves", "/equipes"])
def test_com_jogo_menu_tem_carreira_antes_de_historico(url):
    _iniciar_jogo()

    header = _header(client.get(url).text)

    assert '/carreira"' in header
    assert '/historico"' in header
    assert header.index(">Carreira</a>") < header.index(">Histórico</a>")


def test_menu_tem_marca_e_links_fixos():
    header = _header(client.get("/saves").text)

    assert "Simulador de Copa" in header
    assert "Jogo de Futebol" not in header
    assert '<nav aria-label="Principal">' in header
    assert '<ul class="menu-topo">' in header
    assert ">Carreiras salvas</a>" in header
    assert ">Editar equipes</a>" in header
    assert re.search(r'<span class="marca-ponto" aria-hidden="true"></span>', header)


@pytest.mark.parametrize(
    "url, href_esperado",
    [
        ("/", 'href="http://testserver/"'),
        ("/saves", 'href="http://testserver/saves"'),
        ("/equipes", 'href="http://testserver/equipes"'),
        ("/carreira", 'href="http://testserver/carreira"'),
        ("/historico", 'href="http://testserver/historico"'),
        ("/campeoes", 'href="http://testserver/historico"'),
    ],
)
def test_pagina_atual_marcada_no_link_certo(url, href_esperado):
    _iniciar_jogo()

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert resposta.text.count('aria-current="page"') == 1
    atuais = _links_atuais(_header(resposta.text))
    assert len(atuais) == 1
    assert href_esperado in atuais[0]


def test_marca_e_o_link_atual_na_home():
    atuais = _links_atuais(_header(client.get("/").text))

    assert len(atuais) == 1
    assert 'class="marca"' in atuais[0]


def test_subpagina_de_equipes_marca_editar_equipes():
    resposta = client.get("/equipes/restaurar")

    assert resposta.status_code == 200
    atuais = _links_atuais(_header(resposta.text))
    assert len(atuais) == 1
    assert 'href="http://testserver/equipes"' in atuais[0]


def test_novo_jogo_nao_marca_nenhum_link():
    resposta = client.get("/novo-jogo")

    assert resposta.status_code == 200
    assert 'aria-current="page"' not in resposta.text


def test_fase_nao_marca_nenhum_link():
    _iniciar_jogo()

    resposta = client.get("/fase")

    assert resposta.status_code == 200
    assert 'aria-current="page"' not in resposta.text


@pytest.mark.parametrize("com_jogo", [False, True])
@pytest.mark.parametrize("url", ["/", "/saves", "/equipes"])
def test_header_sem_novo_jogo_admin_value_nem_script(url, com_jogo):
    if com_jogo:
        _iniciar_jogo()

    header = _header(client.get(url).text)

    assert "Novo jogo" not in header
    assert "/admin" not in header
    assert "value=" not in header
    assert "<script" not in header


# --- Casos de borda (game-tester) ---------------------------------------


def _iniciar_jogo_com_historico():
    escolhido = Equipe("São Paulo", id=SAO_PAULO)
    rival = Equipe("Flamengo", id=FLAMENGO)
    historico = [
        {
            "temporada": 2026,
            "campeao": SAO_PAULO,
            "fases": [
                {
                    "nome_fase": "Final - Copa do Brasil",
                    "confrontos": [[SAO_PAULO, FLAMENGO, SAO_PAULO, 5, 4]],
                }
            ],
        }
    ]
    estado.iniciar_jogo("Copa do Brasil", escolhido, 2027, [escolhido, rival], historico=historico)


@pytest.mark.parametrize("url", ["/historico/1/jogos", "/historico/1/classificacao"])
def test_subpaginas_do_historico_marcam_historico(url):
    _iniciar_jogo_com_historico()

    resposta = client.get(url)

    assert resposta.status_code == 200
    atuais = _links_atuais(_header(resposta.text))
    assert len(atuais) == 1
    assert 'href="http://testserver/historico"' in atuais[0]
    assert resposta.text.count('aria-current="page"') == 1


@pytest.mark.parametrize("url", ["/equipes/Copa do Brasil", "/equipes/Copa do Brasil/1/editar"])
def test_subpaginas_de_equipes_marcam_editar_equipes(url):
    resposta = client.get(url)

    assert resposta.status_code == 200
    atuais = _links_atuais(_header(resposta.text))
    assert len(atuais) == 1
    assert 'href="http://testserver/equipes"' in atuais[0]


@pytest.mark.parametrize(
    "url, href_esperado",
    [("/?x=1", 'href="http://testserver/"'), ("/saves?x=1", 'href="http://testserver/saves"')],
)
def test_query_string_nao_atrapalha_a_marcacao(url, href_esperado):
    atuais = _links_atuais(_header(client.get(url).text))

    assert len(atuais) == 1
    assert href_esperado in atuais[0]


def test_login_do_admin_nao_marca_nada_nem_mostra_admin_no_menu(monkeypatch):
    monkeypatch.setenv("ADMIN_SENHA", "senha-de-teste")

    resposta = client.get("/admin/login")

    assert resposta.status_code == 200
    assert 'aria-current="page"' not in resposta.text
    header = _header(resposta.text)
    assert "/admin" not in header
    assert "value=" not in header


def test_header_com_jogo_tem_carreira_e_historico_uma_vez_cada():
    _iniciar_jogo()

    header = _header(client.get("/carreira").text)

    assert header.count('/carreira"') == 1
    assert header.count('/historico"') == 1
    assert header.count("<header") == 1
