"""E-019-T5 (bordas, tester): estatísticas e histórico do dashboard pelo
fluxo real da web — temporadas jogadas de verdade, campeão coroado antes e
depois de `/campeao/continuar`, carreira retomada no meio da temporada
(aviso de histórico incompleto, ID-014) e links do histórico apontando para
a temporada certa. `DIR_SAVES` e o catálogo ficam em `tmp_path` (fixtures
do `tests/conftest.py`).
"""

import json
import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from estatisticas import campanha_na_temporada, resumo_da_carreira
from web.main import app

client = TestClient(app)

NOMES = [f"Clube {letra}" for letra in "ABCDEFGH"]
IDS = list(range(941, 949))
AVISO_INCOMPLETO = "Algumas fases não foram registradas"


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    dados = {
        "Copa Teste": [
            {"id": i, "nome": n, "financas": 1_000, "fas": 10, "titulos": 0, "forca": 50}
            for i, n in zip(IDS, NOMES)
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


# --- auxiliares ---------------------------------------------------------


def _novo_jogo(semente, time=IDS[0]):
    random.seed(semente)
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": "Copa Teste", "time": str(time)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return estado.obter_jogo()


def _resolver_disputa():
    client.get("/fase/penaltis")
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return


def _jogar_fase():
    """Joga a fase atual (resolvendo a disputa do jogador, se houver), sem
    seguir."""
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303 and resposta.headers["location"].endswith("/fase/penaltis"):
        _resolver_disputa()
    else:
        assert resposta.status_code == 200


def _jogar_e_seguir():
    _jogar_fase()
    resposta = client.post("/fase/seguir", follow_redirects=False)
    assert resposta.status_code == 303


def _jogar_ate_campeao(jogo):
    while jogo.campeao is None:
        _jogar_e_seguir()


def _celulas(html):
    return dict(re.findall(r"<tr><th>([^<]+)</th><td>(.*?)</td></tr>", html))


def _assert_estatisticas(html, temporadas, id_time):
    esperado = resumo_da_carreira(temporadas, id_time)
    celulas = _celulas(html)
    assert celulas["Jogos"] == str(esperado["jogos"])
    assert celulas["Vitórias"] == str(esperado["vitorias"])
    assert celulas["Derrotas"] == str(esperado["derrotas"])
    aproveitamento = "—" if esperado["aproveitamento"] is None else f"{esperado['aproveitamento']:.1f}%"
    assert celulas["Aproveitamento"] == aproveitamento
    assert celulas["Gols de pênalti marcados"] == str(esperado["gols_marcados"])
    assert celulas["Gols de pênalti sofridos"] == str(esperado["gols_sofridos"])
    assert celulas["Títulos na carreira"] == str(esperado["titulos"])


def _links_do_historico(html):
    return [(int(n), int(ano)) for n, ano in re.findall(r'href="[^"]*/historico/(\d+)/jogos">(\d+)</a>', html)]


def _retrato_saves():
    pasta = Path(persistencia.DIR_SAVES)
    if not pasta.exists():
        return {}
    return {p.name: p.read_bytes() for p in sorted(pasta.iterdir())}


# --- testes -------------------------------------------------------------


@pytest.mark.parametrize("semente", [0, 1, 7, 42])
def test_campeao_coroado_pelo_fluxo_real_nao_conta_em_dobro(semente):
    jogo = _novo_jogo(semente)
    _jogar_ate_campeao(jogo)
    assert len(jogo.historico) == 1
    assert jogo.fases_da_temporada  # temporada também ainda em memória

    html = client.get("/carreira").text

    _assert_estatisticas(html, jogo.historico, jogo.time_escolhido.id)
    # Cada time joga no máximo 3 jogos numa copa de 8 (quartas, semi, final).
    assert int(_celulas(html)["Jogos"]) <= 3
    assert _links_do_historico(html) == [(1, 2026)]
    assert "Em andamento" not in html
    assert html.count(">2026<") == 1


@pytest.mark.parametrize("semente", [0, 3])
def test_depois_de_continuar_estatisticas_seguem_iguais_e_temporada_nova_em_andamento(semente):
    jogo = _novo_jogo(semente)
    _jogar_ate_campeao(jogo)
    html_coroado = client.get("/carreira").text

    client.post("/campeao/continuar", follow_redirects=False)
    assert jogo.campeao is None and jogo.temporada == 2027
    html = client.get("/carreira").text

    _assert_estatisticas(html, jogo.historico, jogo.time_escolhido.id)
    for chave in ("Jogos", "Vitórias", "Derrotas", "Títulos na carreira"):
        assert _celulas(html)[chave] == _celulas(html_coroado)[chave]
    assert _links_do_historico(html) == [(1, 2026)]
    assert "<td>2027</td>" in html
    assert "<td>Em andamento</td>" in html


def test_varias_temporadas_links_apontam_para_a_temporada_certa():
    jogo = _novo_jogo(5)
    for _ in range(3):
        _jogar_ate_campeao(jogo)
        client.post("/campeao/continuar", follow_redirects=False)
    _jogar_e_seguir()  # uma fase de 2029 em andamento

    html = client.get("/carreira").text

    temporadas = jogo.historico + [
        {
            "temporada": 2029,
            "campeao": None,
            "fases": [
                {
                    "nome_fase": f["nome_fase"],
                    "confrontos": [[a.id, b.id, v.id, ga, gb] for a, b, v, ga, gb in f["confrontos"]],
                }
                for f in jogo.fases_da_temporada
            ],
        }
    ]
    _assert_estatisticas(html, temporadas, jogo.time_escolhido.id)
    assert _links_do_historico(html) == [(1, 2026), (2, 2027), (3, 2028)]
    for indice, ano in _links_do_historico(html):
        pagina = client.get(f"/historico/{indice}/jogos")
        assert pagina.status_code == 200
        assert str(ano) in pagina.text
        campanha = campanha_na_temporada(jogo.historico[indice - 1], jogo.time_escolhido.id)
        assert f"<td>{campanha['rotulo']}</td>" in html
    titulos_historico = sum(1 for t in jogo.historico if t["campeao"] == jogo.time_escolhido.id)
    assert _celulas(html)["Títulos na carreira"] == str(titulos_historico)
    assert "<td>2029</td>" in html
    assert AVISO_INCOMPLETO not in html


def test_carreira_retomada_no_meio_mostra_aviso_so_depois_de_uma_fase_parcial():
    jogo = _novo_jogo(11)
    _jogar_e_seguir()  # quartas decididas e gravadas
    nome_save = jogo.nome_save
    assert nome_save
    html_completo = client.get("/carreira").text
    assert AVISO_INCOMPLETO not in html_completo

    estado.encerrar_jogo()
    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)
    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    assert jogo.fases_da_temporada == []

    # Logo após carregar: nada registrado da temporada → nada a julgar.
    html = client.get("/carreira").text
    assert AVISO_INCOMPLETO not in html
    _assert_estatisticas(html, [], jogo.time_escolhido.id)

    # Joga a semifinal: a primeira fase registrada não é a primeira do torneio.
    _jogar_e_seguir()
    html = client.get("/carreira").text
    assert AVISO_INCOMPLETO in html

    # Continua aparecendo depois que a temporada parcial vai para o histórico.
    _jogar_ate_campeao(jogo)
    client.post("/campeao/continuar", follow_redirects=False)
    html = client.get("/carreira").text
    assert AVISO_INCOMPLETO in html


def test_get_carreira_com_historico_real_nao_grava_nem_muda_historico():
    jogo = _novo_jogo(2)
    _jogar_ate_campeao(jogo)
    client.post("/campeao/continuar", follow_redirects=False)
    _jogar_fase()
    saves_antes = _retrato_saves()
    historico_antes = json.dumps(jogo.historico)
    fases_antes = len(jogo.fases_da_temporada)

    for _ in range(2):
        resposta = client.get("/carreira")
        assert resposta.status_code == 200
        assert "<script" not in resposta.text.lower()

    assert _retrato_saves() == saves_antes
    assert json.dumps(jogo.historico) == historico_antes
    assert len(jogo.fases_da_temporada) == fases_antes


def test_html_do_dashboard_nao_mostra_repr_de_equipe():
    jogo = _novo_jogo(4)
    _jogar_ate_campeao(jogo)

    html = client.get("/carreira").text

    assert "<Equipe" not in html and "&lt;equipe" not in html.lower()
    assert "escudo-clip-" in html
