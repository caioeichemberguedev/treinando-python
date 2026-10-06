import re

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


# --- ID-002-T5b: jogos, classificação e campeões --------------------------


def _historico_com_titulos_repetidos():
    """Três temporadas de 4 times (semifinal + final). "Time A" é campeão
    duas vezes (uma como `Equipe`, outra como string, igual a misturar
    fluxo web e save carregado do JSON); "Time C" uma vez."""
    a, b, c, d = Equipe("Time A"), Equipe("Time B"), Equipe("Time C"), Equipe("Time D")
    temporada_1 = {
        "temporada": 2026,
        "campeao": a,
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [(a, b, a, 4, 2), (c, d, d, 3, 5)]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [(a, d, a, 5, 4)]},
        ],
    }
    temporada_2 = {
        "temporada": 2027,
        "campeao": c,
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [(a, c, c, 1, 3), (b, d, b, 4, 3)]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [(c, b, c, 5, 3)]},
        ],
    }
    temporada_3 = {
        "temporada": 2028,
        "campeao": "Time A",
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [["Time A", "Time C", "Time A", 3, 2],
                            ["Time B", "Time D", "Time D", 2, 4]]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [["Time D", "Time A", "Time A", 4, 5]]},
        ],
    }
    return [temporada_1, temporada_2, temporada_3]


@pytest.mark.parametrize(
    "url", ["/historico/1/jogos", "/historico/1/classificacao", "/campeoes"]
)
def test_rotas_de_historico_sem_jogo_retornam_404(url):
    resposta = client.get(url)

    assert resposta.status_code == 404


@pytest.mark.parametrize("indice", [0, 4, -1])
@pytest.mark.parametrize("tela", ["jogos", "classificacao"])
def test_indice_fora_do_intervalo_retorna_404(tela, indice):
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get(f"/historico/{indice}/{tela}")

    assert resposta.status_code == 404


def test_jogos_da_temporada_mostram_confrontos_fase_a_fase():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get("/historico/1/jogos")

    assert resposta.status_code == 200
    texto = resposta.text
    assert "2026" in texto
    assert texto.index("Semifinal") < texto.index("Final - Campeonato Teste")
    for placar in ["4 x 2", "3 x 5", "5 x 4"]:
        assert placar in texto
    # placares da temporada 2 não podem aparecer na tela da temporada 1
    assert "1 x 3" not in texto
    assert "Equipe(" not in texto and "object at" not in texto


def test_jogos_aceitam_confrontos_vindos_do_json_como_lista():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get("/historico/3/jogos")

    assert resposta.status_code == 200
    assert "4 x 5" in resposta.text


def test_classificacao_mostra_grupos_de_montar_classificacao():
    historico = _historico_com_titulos_repetidos()
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico/1/classificacao")

    assert resposta.status_code == 200
    texto = resposta.text
    assert "2026" in texto
    assert re.search(r"<td>Campeão</td>\s*<td>Time A</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Time D</td>", texto)
    assert re.search(r"<td>Semifinal</td>\s*<td>Time B, Time C</td>", texto)


def test_classificacao_respeita_o_indice_escolhido():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = client.get("/historico/2/classificacao").text

    assert re.search(r"<td>Campeão</td>\s*<td>Time C</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Time B</td>", texto)


def test_campeoes_lista_campeao_de_cada_temporada():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get("/campeoes")

    assert resposta.status_code == 200
    texto = resposta.text
    assert re.search(r"<td>2026</td>\s*<td>Time A</td>", texto)
    assert re.search(r"<td>2027</td>\s*<td>Time C</td>", texto)
    assert re.search(r"<td>2028</td>\s*<td>Time A</td>", texto)


def test_campeoes_conta_titulos_por_time_normalizando_pelo_nome():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = client.get("/campeoes").text
    contagem = re.findall(r"<td>(Time \w)</td>\s*<td>(\d+)</td>", texto)

    assert contagem == [("Time A", "2"), ("Time C", "1")]


def test_campeoes_sem_temporadas_mostra_mensagem():
    _iniciar_jogo_com_historico([])

    resposta = client.get("/campeoes")

    assert resposta.status_code == 200
    assert "Nenhum campeão ainda" in resposta.text


def test_historico_tem_links_para_jogos_classificacao_e_campeoes():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = client.get("/historico").text

    for caminho in ["/historico/1/jogos", "/historico/3/classificacao",
                    "/campeoes"]:
        assert f'href="http://testserver{caminho}"' in texto


# --- ID-002-T5b: casos de borda (game-tester) -----------------------------


@pytest.mark.parametrize("indice", ["abc", "1.5", "", "%20"])
@pytest.mark.parametrize("tela", ["jogos", "classificacao"])
def test_indice_nao_inteiro_nao_gera_500(tela, indice):
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get(f"/historico/{indice}/{tela}")

    assert resposta.status_code in (404, 422)


@pytest.mark.parametrize("tela", ["jogos", "classificacao"])
def test_indice_gigante_retorna_404(tela):
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get(f"/historico/99999999999999999999/{tela}")

    assert resposta.status_code == 404


def _historico_com_nome_malicioso():
    mau = "<script>alert(1)</script>"
    return [{
        "temporada": 2026,
        "campeao": Equipe(mau),
        "fases": [{"nome_fase": "Final - <b>Copa</b>",
                   "confrontos": [(Equipe(mau), Equipe("Time B"), Equipe(mau), 5, 4)]}],
    }]


@pytest.mark.parametrize(
    "url", ["/historico/1/jogos", "/historico/1/classificacao", "/campeoes"]
)
def test_telas_novas_escapam_html_nos_nomes(url):
    _iniciar_jogo_com_historico(_historico_com_nome_malicioso())

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text
    assert "<b>Copa</b>" not in resposta.text


@pytest.mark.parametrize("tela", ["jogos", "classificacao"])
def test_temporada_sem_fases_nao_gera_500(tela):
    _iniciar_jogo_com_historico([{"temporada": 2026, "campeao": "Time A", "fases": []}])

    resposta = client.get(f"/historico/1/{tela}")

    assert resposta.status_code == 200


def test_campeoes_empate_mantem_ordem_da_primeira_conquista():
    historico = [
        {"temporada": 2026, "campeao": "Time Z", "fases": []},
        {"temporada": 2027, "campeao": Equipe("Time A"), "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    texto = client.get("/campeoes").text
    contagem = re.findall(r"<td>(Time \w)</td>\s*<td>(\d+)</td>", texto)

    assert contagem == [("Time Z", "1"), ("Time A", "1")]


def test_classificacao_com_campeao_vindo_do_json_como_lista():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = client.get("/historico/3/classificacao").text

    assert re.search(r"<td>Campeão</td>\s*<td>Time A</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Time D</td>", texto)
    assert re.search(r"<td>Semifinal</td>\s*<td>Time C, Time B</td>", texto)


def test_leitura_das_telas_novas_nao_altera_historico():
    historico = _historico_com_titulos_repetidos()
    _iniciar_jogo_com_historico(historico)

    for url in ["/historico/1/jogos", "/historico/1/classificacao", "/campeoes"]:
        client.get(url)

    assert len(estado.obter_jogo().historico) == 3
    assert estado.obter_jogo().historico[0]["campeao"] == "Time A"
