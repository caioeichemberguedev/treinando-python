"""E-015-T2: save travado na web.

Com `persistencia.salvar_jogo` trocado por um falso que levanta
`SaveTravado`, nenhuma rota quebra com 500: o jogo segue em memória, o
retrato não gravado fica em `EstadoJogo.save_pendente`, todas as páginas
mostram o aviso com o botão "Tentar salvar de novo" e `POST
/carreira/salvar` grava o pendente quando a trava some.

`DIR_SAVES` fica em `tmp_path` pela fixture `saves_isolados` do
`tests/conftest.py`; o nome do save vem de `date.today()`, então os testes
usam `estado.obter_jogo().nome_save`.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)

TEXTO_BOTAO = "Tentar salvar de novo"
TEXTO_MEMORIA = "Seu progresso continua na memória do servidor"

SALVAR_REAL = persistencia.salvar_jogo


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """`equipes.json` de teste (2 e 4 times) e nenhum jogo em memória."""
    dados = {
        "Campeonato Teste": [
            {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 902, "nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Copa Teste": [
            {"id": 905, "nome": "Copa E", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 906, "nome": "Copa F", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 907, "nome": "Copa G", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 908, "nome": "Copa H", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


class SalvarTravado:
    """Falso de `persistencia.salvar_jogo`: sempre levanta `SaveTravado` e
    conta as tentativas."""

    def __init__(self):
        self.tentativas = 0

    def __call__(self, *args, **kwargs):
        self.tentativas += 1
        raise persistencia.SaveTravado(persistencia.MENSAGEM_SAVE_TRAVADO)


@pytest.fixture
def travado(monkeypatch):
    """Deixa o save travado até o teste chamar `destravar()`."""
    falso = SalvarTravado()
    monkeypatch.setattr(persistencia, "salvar_jogo", falso)
    return falso


def destravar(monkeypatch):
    monkeypatch.setattr(persistencia, "salvar_jogo", SALVAR_REAL)


# --- helpers ----------------------------------------------------------------

def _ids(times):
    return [time.id for time in times]


def _novo_jogo(campeonato, time):
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": campeonato, "time": str(time)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return estado.obter_jogo()


def _caminho_save(jogo):
    return Path(persistencia._caminho_save(jogo.nome_save))


def _resolver_disputa(canto="1"):
    """Cobra até a disputa do jogador terminar (a última cobrança fecha a
    fase e grava). Toda resposta tem que ser 303, nunca 500."""
    assert client.get("/fase/penaltis").status_code == 200
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return


def _decidir_fase_atual():
    """Deixa a fase atual decidida (sem clicar em "Seguir")."""
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        _resolver_disputa()
        resposta = client.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200
    return resposta


def _jogar_temporada_ate_o_campeao():
    while True:
        _decidir_fase_atual()
        resposta = client.post("/fase/seguir", follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/campeao":
            return


def _mostra_aviso(html):
    return persistencia.MENSAGEM_SAVE_TRAVADO in html and TEXTO_BOTAO in html


# --- estado.salvar_jogo_em_andamento ------------------------------------------

def test_salvar_em_andamento_devolve_false_e_guarda_o_retrato_pendente(travado):
    jogo = _novo_jogo("Copa Teste", 905)
    classificados = list(jogo.classificados)

    assert estado.salvar_jogo_em_andamento(jogo, 2030, classificados) is False

    temporada, pendentes, fases = jogo.save_pendente
    assert temporada == 2030
    assert _ids(pendentes) == _ids(classificados)
    assert pendentes is not classificados  # cópia: o retrato não muda junto
    assert fases == jogo.fases_da_temporada == []
    assert fases is not jogo.fases_da_temporada


def test_salvar_em_andamento_com_sucesso_limpa_o_pendente(travado, monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)
    assert jogo.save_pendente is not None

    destravar(monkeypatch)

    assert estado.salvar_jogo_em_andamento(jogo, jogo.temporada, jogo.classificados) is True
    assert jogo.save_pendente is None


def test_salvar_em_andamento_sem_nome_save_nao_grava_e_devolve_true(travado):
    jogo = estado.iniciar_jogo("Copa Teste", None, 2026, [], nome_save=None)

    assert estado.salvar_jogo_em_andamento(jogo, 2026, []) is True
    assert travado.tentativas == 0
    assert jogo.save_pendente is None


# --- rotas não quebram com o save travado --------------------------------------

def test_novo_jogo_com_save_travado_segue_em_memoria(travado):
    jogo = _novo_jogo("Copa Teste", 905)

    assert travado.tentativas == 1
    assert jogo is not None
    assert jogo.save_pendente == (2026, jogo.classificados, [])
    assert not _caminho_save(jogo).exists()


def test_fase_decidida_pela_ultima_cobranca_com_save_travado(travado):
    jogo = _novo_jogo("Copa Teste", 905)

    _decidir_fase_atual()

    assert jogo.fase_atual["confronto_pendente"] is None
    temporada, pendentes, fases = jogo.save_pendente
    assert temporada == 2026
    assert _ids(pendentes) == _ids(jogo.fase_atual["proximos"])
    assert len(pendentes) == 2
    assert fases == jogo.fases_da_temporada  # inclui a fase que acabou de fechar
    assert len(fases) == 1


def test_final_e_proxima_temporada_com_save_travado(travado):
    jogo = _novo_jogo("Campeonato Teste", 901)

    _jogar_temporada_ate_o_campeao()

    assert jogo.campeao is not None
    assert jogo.save_pendente == (2027, None, [])
    assert len(jogo.historico) == 1

    resposta = client.post("/campeao/continuar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert jogo.temporada == 2027
    assert jogo.campeao is None
    temporada, pendentes, fases = jogo.save_pendente
    assert temporada == 2027
    assert _ids(pendentes) == _ids(jogo.classificados)
    assert fases == []
    assert client.get("/carreira").status_code == 200


# --- aviso nas páginas --------------------------------------------------------

def test_aviso_aparece_em_todas_as_paginas_depois_da_falha(travado):
    _novo_jogo("Copa Teste", 905)

    for url in ("/carreira", "/fase", "/", "/saves", "/historico"):
        resposta = client.get(url)
        assert resposta.status_code == 200, url
        assert _mostra_aviso(resposta.text), url
        assert TEXTO_MEMORIA in resposta.text, url
        assert '/carreira/salvar"' in resposta.text, url


def test_sem_falha_nenhuma_pagina_mostra_o_aviso():
    _novo_jogo("Copa Teste", 905)

    for url in ("/carreira", "/fase", "/", "/saves", "/historico"):
        resposta = client.get(url)
        assert resposta.status_code == 200, url
        assert TEXTO_BOTAO not in resposta.text, url
        assert persistencia.MENSAGEM_SAVE_TRAVADO not in resposta.text, url


def test_sem_jogo_nenhuma_pagina_mostra_o_aviso():
    resposta = client.get("/")

    assert resposta.status_code == 200
    assert TEXTO_BOTAO not in resposta.text


# --- POST /carreira/salvar ----------------------------------------------------

def test_tentar_de_novo_grava_o_retrato_pendente_e_o_aviso_some(travado, monkeypatch):
    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()
    client.post("/campeao/continuar")
    assert jogo.save_pendente is not None

    destravar(monkeypatch)
    resposta = client.post("/carreira/salvar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert jogo.save_pendente is None
    dados = persistencia.carregar_jogo_salvo(jogo.nome_save)
    assert dados["campeonato"] == "Campeonato Teste"
    assert dados["time_escolhido"].id == 901
    assert dados["temporada"] == jogo.temporada == 2027
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)
    assert dados["historico"] == jogo.historico
    assert not _mostra_aviso(client.get("/carreira").text)


def test_tentar_de_novo_com_a_trava_mantida_continua_pendente(travado):
    jogo = _novo_jogo("Copa Teste", 905)
    pendente_antes = jogo.save_pendente

    resposta = client.post("/carreira/salvar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert travado.tentativas == 2
    assert jogo.save_pendente == pendente_antes
    assert not _caminho_save(jogo).exists()
    assert _mostra_aviso(client.get("/carreira").text)


def test_tentar_de_novo_sem_jogo_responde_404():
    resposta = client.post("/carreira/salvar", follow_redirects=False)

    assert resposta.status_code == 404


def test_tentar_de_novo_sem_pendente_nao_grava(monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)
    bytes_antes = _caminho_save(jogo).read_bytes()
    falso = SalvarTravado()
    monkeypatch.setattr(persistencia, "salvar_jogo", falso)

    resposta = client.post("/carreira/salvar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert falso.tentativas == 0
    assert jogo.save_pendente is None
    assert _caminho_save(jogo).read_bytes() == bytes_antes


def test_get_carreira_com_pendente_nao_tenta_gravar(travado):
    jogo = _novo_jogo("Copa Teste", 905)
    pendente = jogo.save_pendente

    client.get("/carreira")
    client.get("/carreira")

    assert travado.tentativas == 1
    assert jogo.save_pendente == pendente


# --- casos de borda (game-tester) ----------------------------------------------

def test_carregar_save_entre_temporadas_com_save_travado(monkeypatch):
    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()  # grava (2027, None) com o save real
    nome_save = jogo.nome_save
    bytes_antes = _caminho_save(jogo).read_bytes()
    monkeypatch.setattr(estado, "_jogo_atual", None)
    falso = SalvarTravado()
    monkeypatch.setattr(persistencia, "salvar_jogo", falso)

    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    carregado = estado.obter_jogo()
    assert falso.tentativas == 1
    temporada, pendentes, fases = carregado.save_pendente
    assert temporada == 2027
    assert fases == []
    assert _ids(pendentes) == _ids(carregado.classificados)
    assert _caminho_save(carregado).read_bytes() == bytes_antes
    assert _mostra_aviso(client.get("/carreira").text)


def test_aviso_em_campeao_penaltis_equipes_e_campeoes(travado):
    _novo_jogo("Campeonato Teste", 901)
    client.get("/fase", follow_redirects=False)  # monta a fase (2 times = disputa do jogador)
    resposta = client.get("/fase/penaltis")
    assert resposta.status_code == 200
    assert _mostra_aviso(resposta.text)
    for url in ("/equipes", "/campeoes", "/novo-jogo"):
        resposta = client.get(url)
        assert resposta.status_code == 200, url
        assert _mostra_aviso(resposta.text), url

    _jogar_temporada_ate_o_campeao()
    resposta = client.get("/campeao")
    assert resposta.status_code == 200
    assert _mostra_aviso(resposta.text)


def test_segunda_falha_substitui_o_pendente_pelo_retrato_mais_novo(travado):
    jogo = _novo_jogo("Copa Teste", 905)
    assert jogo.save_pendente[1] is not None and len(jogo.save_pendente[1]) == 4

    _decidir_fase_atual()

    assert travado.tentativas == 2
    assert len(jogo.save_pendente[1]) == 2


def test_pendente_e_retrato_congelado_mesmo_se_a_lista_original_mudar(travado):
    jogo = _novo_jogo("Copa Teste", 905)
    lista = list(jogo.classificados)
    estado.salvar_jogo_em_andamento(jogo, 2026, lista)
    ids_antes = _ids(jogo.save_pendente[1])

    lista.clear()

    assert _ids(jogo.save_pendente[1]) == ids_antes


def test_novo_jogo_sem_trava_depois_de_pendente_tira_o_aviso(travado, monkeypatch):
    _novo_jogo("Copa Teste", 905)
    assert _mostra_aviso(client.get("/carreira").text)

    destravar(monkeypatch)
    novo = _novo_jogo("Campeonato Teste", 901)

    assert novo.save_pendente is None
    assert not _mostra_aviso(client.get("/carreira").text)


def test_erro_que_nao_e_trava_nao_vira_pendente(monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)

    def explode(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(persistencia, "salvar_jogo", explode)

    with pytest.raises(OSError):
        estado.salvar_jogo_em_andamento(jogo, 2026, jogo.classificados)
    assert jogo.save_pendente is None


def test_aviso_usa_form_post_sem_javascript(travado):
    _novo_jogo("Copa Teste", 905)

    html = client.get("/carreira").text

    assert '<form method="post" action="' in html
    assert '/carreira/salvar"' in html
    assert "<script" not in html.lower()


# --- E-014-T5: o retrato pendente inclui as fases da temporada ----------------

def test_tentar_de_novo_grava_as_fases_do_momento_da_falha(travado, monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()  # semifinal fechada, gravação falha
    fases_da_falha = json.loads(json.dumps(jogo.fases_da_temporada))
    assert len(fases_da_falha) == 1
    assert jogo.save_pendente[2] == fases_da_falha
    assert jogo.save_pendente[2] is not jogo.fases_da_temporada

    # A memória segue mudando depois da falha: o retrato pendente não muda.
    jogo.fases_da_temporada.append({"nome_fase": "Fase fantasma", "confrontos": []})
    assert jogo.save_pendente[2] == fases_da_falha

    destravar(monkeypatch)
    resposta = client.post("/carreira/salvar", follow_redirects=False)

    assert resposta.status_code == 303
    assert jogo.save_pendente is None
    dados = persistencia.carregar_jogo_salvo(jogo.nome_save)
    assert dados["temporada"] == 2026
    assert len(dados["classificados"]) == 2
    assert dados["fases_da_temporada"] == fases_da_falha


def test_tentar_de_novo_nao_muta_as_fases_ja_fechadas(travado, monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()
    fase_fechada = jogo.fases_da_temporada[0]
    antes = json.dumps(fase_fechada)

    destravar(monkeypatch)
    client.post("/carreira/salvar", follow_redirects=False)

    assert jogo.fases_da_temporada[0] is fase_fechada
    assert json.dumps(fase_fechada) == antes
