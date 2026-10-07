import re

import pytest
from fastapi.testclient import TestClient

import catalogo
import web.estado as estado
from equipe import Equipe
from web.escudo import CORES_ESCUDO_PADRAO
from web.main import app
from web.rotas import equipes, historico, jogo, saves

client = TestClient(app)

_SVG_OU_SPAN_TIME = re.compile(r'<svg class="escudo".*?</svg>|<span class="time">|</span>', re.S)

# Ids reais do catálogo usados nos históricos de teste.
SAO_PAULO, PALMEIRAS, CORINTHIANS, SANTOS, FLAMENGO = 1, 2, 3, 4, 5
BRASIL, HOLANDA = 17, 26
ID_FORA_DO_CATALOGO = 999
ID_MALICIOSO = 950
NOME_MALICIOSO = "<script>alert(1)</script>"

# Linha "time | títulos" da tabela de `/campeoes` (o nome não começa com
# dígito, para não casar com a tabela "temporada | campeão").
_TITULOS_POR_TIME = re.compile(r"<td>([^<\d][^<]*)</td>\s*<td>(\d+)</td>")


def _sem_escudo(texto):
    """Remove os SVGs de escudo e o `<span class="time">` em volta do nome,
    para os testes de conteúdo continuarem comparando só os nomes."""
    return _SVG_OU_SPAN_TIME.sub("", texto)


@pytest.fixture(autouse=True)
def sem_jogo_em_andamento(monkeypatch):
    """Reseta o "jogo em andamento" em memória entre os testes."""
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


@pytest.fixture
def catalogo_com_nome_malicioso(monkeypatch):
    """Acrescenta ao catálogo um time (id 950) com HTML no nome."""
    malicioso = {
        "id": ID_MALICIOSO,
        "campeonato": "Campeonato Teste",
        "nome": NOME_MALICIOSO,
        "cores": ["#111111", "#222222", "#333333"],
    }
    monkeypatch.setattr(
        catalogo, "TIMES_PADRAO", catalogo.TIMES_PADRAO + [malicioso]
    )


def _iniciar_jogo_com_historico(historico):
    times = [Equipe("Time A", id=901), Equipe("Time B", id=902)]
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
        {"temporada": 2026, "campeao": SAO_PAULO, "fases": []},
        {"temporada": 2027, "campeao": PALMEIRAS, "fases": []},
        {"temporada": 2028, "campeao": BRASIL, "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "Nenhuma temporada concluída ainda" not in resposta.text
    texto = _sem_escudo(resposta.text)
    for temporada, nome in [(2026, "São Paulo"), (2027, "Palmeiras"),
                            (2028, "Brasil")]:
        assert re.search(rf"<td>{temporada}</td>\s*<td>{nome}</td>", texto)


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


def test_historico_resolve_nome_do_campeao_pelo_id():
    """O histórico guarda o id do campeão; a tela mostra o nome do
    catálogo, nunca o número cru."""
    historico = [{"temporada": 2026, "campeao": FLAMENGO, "fases": []}]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert re.search(r"<td>2026</td>\s*<td>Flamengo</td>",
                     _sem_escudo(resposta.text))
    assert "Time #" not in resposta.text


def test_historico_escapa_html_no_nome_do_campeao(catalogo_com_nome_malicioso):
    historico = [{"temporada": 2026, "campeao": ID_MALICIOSO, "fases": []}]
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico")

    assert resposta.status_code == 200
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text


def test_historico_mantem_a_ordem_das_temporadas():
    historico = [
        {"temporada": 2026, "campeao": PALMEIRAS, "fases": []},
        {"temporada": 2027, "campeao": SAO_PAULO, "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    texto = _sem_escudo(client.get("/historico").text)

    assert texto.index("Palmeiras") < texto.index("São Paulo")


def test_historico_nao_e_alterado_pela_leitura():
    historico = [{"temporada": 2026, "campeao": SAO_PAULO, "fases": []}]
    _iniciar_jogo_com_historico(historico)

    client.get("/historico")
    client.get("/historico")

    assert len(estado.obter_jogo().historico) == 1


# --- ID-002-T5b: jogos, classificação e campeões --------------------------


def _historico_com_titulos_repetidos():
    """Três temporadas de 4 times (semifinal + final), no formato do save:
    ids do catálogo e confrontos como listas. São Paulo (1) é campeão duas
    vezes; Corinthians (3) uma vez."""
    sp, pal, cor, san = SAO_PAULO, PALMEIRAS, CORINTHIANS, SANTOS
    temporada_1 = {
        "temporada": 2026,
        "campeao": sp,
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [[sp, pal, sp, 4, 2], [cor, san, san, 3, 5]]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [[sp, san, sp, 5, 4]]},
        ],
    }
    temporada_2 = {
        "temporada": 2027,
        "campeao": cor,
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [[sp, cor, cor, 1, 3], [pal, san, pal, 4, 3]]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [[cor, pal, cor, 5, 3]]},
        ],
    }
    temporada_3 = {
        "temporada": 2028,
        "campeao": sp,
        "fases": [
            {"nome_fase": "Semifinal - Campeonato Teste",
             "confrontos": [[sp, cor, sp, 3, 2], [pal, san, san, 2, 4]]},
            {"nome_fase": "Final - Campeonato Teste",
             "confrontos": [[san, sp, sp, 4, 5]]},
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


def test_jogos_resolvem_nomes_dos_confrontos_pelo_id():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get("/historico/3/jogos")

    assert resposta.status_code == 200
    texto = _sem_escudo(resposta.text)
    assert re.search(
        r"<td>Santos</td>\s*<td>4 x 5</td>\s*<td>São Paulo</td>\s*"
        r"<td>São Paulo</td>",
        texto,
    )
    assert 'Campeão: <strong class="time">São Paulo</strong>' in texto


def test_classificacao_mostra_grupos_de_montar_classificacao():
    historico = _historico_com_titulos_repetidos()
    _iniciar_jogo_com_historico(historico)

    resposta = client.get("/historico/1/classificacao")

    assert resposta.status_code == 200
    texto = _sem_escudo(resposta.text)
    assert "2026" in texto
    assert re.search(r"<td>Campeão</td>\s*<td>São Paulo</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Santos</td>", texto)
    assert re.search(r"<td>Semifinal</td>\s*<td>Palmeiras, Corinthians</td>", texto)


def test_classificacao_respeita_o_indice_escolhido():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = _sem_escudo(client.get("/historico/2/classificacao").text)

    assert re.search(r"<td>Campeão</td>\s*<td>Corinthians</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Palmeiras</td>", texto)


def test_campeoes_lista_campeao_de_cada_temporada():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get("/campeoes")

    assert resposta.status_code == 200
    texto = _sem_escudo(resposta.text)
    assert re.search(r"<td>2026</td>\s*<td>São Paulo</td>", texto)
    assert re.search(r"<td>2027</td>\s*<td>Corinthians</td>", texto)
    assert re.search(r"<td>2028</td>\s*<td>São Paulo</td>", texto)


def test_campeoes_conta_titulos_por_id():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = _sem_escudo(client.get("/campeoes").text)

    assert _TITULOS_POR_TIME.findall(texto) == [
        ("São Paulo", "2"), ("Corinthians", "1"),
    ]


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
    return [{
        "temporada": 2026,
        "campeao": ID_MALICIOSO,
        "fases": [{"nome_fase": "Final - <b>Copa</b>",
                   "confrontos": [[ID_MALICIOSO, SAO_PAULO, ID_MALICIOSO, 5, 4]]}],
    }]


@pytest.mark.parametrize(
    "url", ["/historico/1/jogos", "/historico/1/classificacao", "/campeoes"]
)
def test_telas_novas_escapam_html_nos_nomes(url, catalogo_com_nome_malicioso):
    _iniciar_jogo_com_historico(_historico_com_nome_malicioso())

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert "<script>alert(1)</script>" not in resposta.text
    assert "&lt;script&gt;" in resposta.text
    assert "<b>Copa</b>" not in resposta.text


@pytest.mark.parametrize("tela", ["jogos", "classificacao"])
def test_temporada_sem_fases_nao_gera_500(tela):
    _iniciar_jogo_com_historico([{"temporada": 2026, "campeao": SAO_PAULO, "fases": []}])

    resposta = client.get(f"/historico/1/{tela}")

    assert resposta.status_code == 200


def test_campeoes_empate_mantem_ordem_da_primeira_conquista():
    historico = [
        {"temporada": 2026, "campeao": HOLANDA, "fases": []},
        {"temporada": 2027, "campeao": SAO_PAULO, "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    texto = _sem_escudo(client.get("/campeoes").text)

    assert _TITULOS_POR_TIME.findall(texto) == [
        ("Holanda", "1"), ("São Paulo", "1"),
    ]


def test_classificacao_da_terceira_temporada():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = _sem_escudo(client.get("/historico/3/classificacao").text)

    assert re.search(r"<td>Campeão</td>\s*<td>São Paulo</td>", texto)
    assert re.search(r"<td>Vice-campeão</td>\s*<td>Santos</td>", texto)
    assert re.search(r"<td>Semifinal</td>\s*<td>Corinthians, Palmeiras</td>", texto)


def test_leitura_das_telas_novas_nao_altera_historico():
    historico = _historico_com_titulos_repetidos()
    _iniciar_jogo_com_historico(historico)

    for url in ["/historico/1/jogos", "/historico/1/classificacao", "/campeoes"]:
        client.get(url)

    assert len(estado.obter_jogo().historico) == 3
    assert estado.obter_jogo().historico[0]["campeao"] == SAO_PAULO


# --- ID-005-T6 / ID-007-T7: escudo e nome pelo id nas telas de histórico --


def _contar_escudos(texto):
    return texto.count('class="escudo"')


@pytest.mark.parametrize(
    "url, esperado",
    [
        ("/historico", 3),                 # um campeão por temporada
        ("/historico/1/jogos", 10),        # campeão + 3 confrontos x 3 times
        ("/historico/3/jogos", 10),
        ("/historico/1/classificacao", 4),  # 4 times
        ("/historico/3/classificacao", 4),
        ("/campeoes", 5),                  # 3 temporadas + 2 times com título
    ],
)
def test_telas_de_historico_mostram_escudo_e_nomes_do_catalogo(url, esperado):
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert _contar_escudos(resposta.text) == esperado
    assert "São Paulo" in _sem_escudo(resposta.text)
    assert "Time #" not in resposta.text


def _historico_com_time_fora_do_catalogo():
    """Final entre Flamengo (id 5) e um id que não existe no catálogo."""
    return [{
        "temporada": 2026,
        "campeao": FLAMENGO,
        "fases": [{"nome_fase": "Final - Campeonato Teste",
                   "confrontos": [[FLAMENGO, ID_FORA_DO_CATALOGO,
                                   FLAMENGO, 5, 3]]}],
    }]


@pytest.mark.parametrize(
    "url",
    ["/historico", "/historico/1/jogos", "/historico/1/classificacao",
     "/campeoes"],
)
def test_historico_em_ids_usa_cores_do_catalogo(url):
    _iniciar_jogo_com_historico(_historico_com_time_fora_do_catalogo())

    resposta = client.get(url)

    assert resposta.status_code == 200
    assert "#C4161C" in resposta.text  # vermelho do Flamengo no catálogo
    assert "Flamengo" in _sem_escudo(resposta.text)


@pytest.mark.parametrize("url", ["/historico/1/jogos", "/historico/1/classificacao"])
def test_id_fora_do_catalogo_usa_escudo_cinza(url):
    _iniciar_jogo_com_historico(_historico_com_time_fora_do_catalogo())

    texto = client.get(url).text

    assert "Escudo do Time #999" in texto
    assert "Time #999" in _sem_escudo(texto)
    for cor in CORES_ESCUDO_PADRAO:
        assert cor in texto


def test_classificacao_com_escudo_mostra_todos_os_nomes_do_grupo():
    _iniciar_jogo_com_historico(_historico_com_titulos_repetidos())

    texto = client.get("/historico/1/classificacao").text
    linha_semifinal = re.search(r"<td>Semifinal</td>\s*<td>(.*?)</td>", texto, re.S).group(1)

    assert _contar_escudos(linha_semifinal) == 2
    assert _sem_escudo(linha_semifinal) == "Palmeiras, Corinthians"


def test_nome_visivel_continua_fora_do_svg():
    """O nome também aparece no `aria-label`/`<title>` do escudo — garante
    que ele continua visível como texto, e não só dentro do SVG."""
    historico = [
        {"temporada": 2026, "campeao": SAO_PAULO, "fases": []},
        {"temporada": 2027, "campeao": BRASIL, "fases": []},
    ]
    _iniciar_jogo_com_historico(historico)

    texto = _sem_escudo(client.get("/historico").text)

    assert re.search(r"<td>2026</td>\s*<td>São Paulo</td>", texto)
    assert re.search(r"<td>2027</td>\s*<td>Brasil</td>", texto)


@pytest.mark.parametrize(
    "url", ["/historico", "/historico/1/jogos", "/historico/1/classificacao",
            "/campeoes"],
)
def test_nome_com_html_e_escapado_no_texto_e_no_escudo(
    url, catalogo_com_nome_malicioso
):
    historico = [{
        "temporada": 2026,
        "campeao": ID_MALICIOSO,
        "fases": [{"nome_fase": "Final - Campeonato Teste",
                   "confrontos": [[ID_MALICIOSO, SAO_PAULO, ID_MALICIOSO, 2, 1]]}],
    }]
    _iniciar_jogo_com_historico(historico)

    texto = client.get(url).text

    assert NOME_MALICIOSO not in texto
    assert "Escudo do &lt;script&gt;" in texto
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in _sem_escudo(texto)
