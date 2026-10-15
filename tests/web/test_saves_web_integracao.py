"""E-018-T6: ponta a ponta web <-> terminal com a mesma carreira em SQLite.

Cenários (o que já estava coberto em outros arquivos não se repete aqui):
1. Carreira criada na web, "Seguir" no meio e jogo fechado (E-019: não há
   mais "Salvar e sair" — a fase decidida já está gravada), continuada pelo
   terminal (`menu.carregar_jogo` com `input` simulado) até o fim da
   temporada.
2. Carreira criada no terminal, saída no meio, continuada pela web até o
   campeão (`test_saves_sqlite_integracao.py` só carrega e abre a fase).
3. Web: duas temporadas completas + "reinício do servidor" (estado em
   memória zerado e `TestClient` novo) e "Continuar" em `/saves`; e o mesmo
   reinício no meio de uma temporada, sem clicar em "Seguir".
4. Nenhum arquivo fora de `tmp_path` é tocado (o `saves/` real não muda).

Já cobertos em outros arquivos: "Seguir" e fechar/continuar na web
(`test_jogo_salva.py`), terminal -> terminal
(`test_saves_sqlite_integracao.py`), gravação a cada momento do fluxo web
(`test_jogo_salva.py`).
"""

import os

import pytest
from fastapi.testclient import TestClient

import menu
import persistencia
import web.estado as estado
from web.main import app

# Valor real, lido na importação (antes de qualquer fixture de isolamento).
DIR_SAVES_REAL = persistencia.DIR_SAVES
ARQUIVO_EQUIPES_REAL = persistencia.ARQUIVO_EQUIPES

CAMPEONATO = "Copa do Brasil"
TIME_DO_JOGADOR = 1  # São Paulo

client = TestClient(app)


def _retrato_do_disco_real():
    """Nomes, tamanhos e datas dos arquivos reais que os testes não podem tocar."""
    retrato = {}
    if os.path.isdir(DIR_SAVES_REAL):
        for nome in sorted(os.listdir(DIR_SAVES_REAL)):
            info = os.stat(os.path.join(DIR_SAVES_REAL, nome))
            retrato[nome] = (info.st_size, info.st_mtime_ns)
    if os.path.exists(ARQUIVO_EQUIPES_REAL):
        info = os.stat(ARQUIVO_EQUIPES_REAL)
        retrato["<equipes.json>"] = (info.st_size, info.st_mtime_ns)
    return retrato


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """16 times da Copa do Brasil (elenco padrão) em `tmp_path`; confere no
    fim que o `saves/` e o `equipes.json` reais ficaram intactos (cenário 4)."""
    retrato_antes = _retrato_do_disco_real()
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    persistencia.restaurar_equipes_padrao()
    yield
    assert _retrato_do_disco_real() == retrato_antes
    assert os.path.commonpath([persistencia.DIR_SAVES, str(tmp_path)]) == str(tmp_path)


# --- helpers: web -----------------------------------------------------------

def _ids(times):
    return [time.id for time in times]


def _novo_jogo_web():
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": CAMPEONATO, "time": str(TIME_DO_JOGADOR)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return estado.obter_jogo()


def _decidir_fase_atual(cliente=client):
    """Deixa a fase atual decidida (sem "Avançar"), cobrando no canto 1."""
    resposta = cliente.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        assert resposta.headers["location"] == "/fase/penaltis"
        cliente.get("/fase/penaltis")
        while True:
            r = cliente.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
            assert r.status_code == 303
            if r.headers["location"] == "/fase":
                break
        resposta = cliente.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200


def _jogar_ate_o_campeao(cliente=client):
    """Joga a temporada pela web até a tela do campeão; devolve as fases jogadas."""
    fases = 0
    while True:
        _decidir_fase_atual(cliente)
        fases += 1
        resposta = cliente.post("/fase/seguir", follow_redirects=False)
        assert resposta.status_code == 303
        assert resposta.headers["location"] in ("/carreira", "/campeao")
        if resposta.headers["location"] == "/campeao":
            assert cliente.get("/campeao").status_code == 200
            return fases


def _continuar_pela_tela_de_saves(cliente, nome_save):
    """Simula o jogador abrindo `/saves` e clicando em "Continuar"."""
    tela = cliente.get("/saves")
    assert tela.status_code == 200
    assert nome_save in tela.text
    resposta = cliente.post(f"/saves/{nome_save}/carregar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert cliente.get("/carreira").status_code == 200
    return estado.obter_jogo()


# --- helpers: terminal ------------------------------------------------------

def _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch):
    """Novo jogo no terminal ("1" para tudo) e "sair" depois das oitavas."""
    monkeypatch.setattr(
        "builtins.input", lambda mensagem="": "sair" if "sair" in mensagem else "1"
    )
    menu.novo_jogo(persistencia.carregar_equipes())
    saves = persistencia.listar_saves()
    assert len(saves) == 1
    return saves[0]


def _continuar_pelo_terminal_ate_o_fim(monkeypatch):
    """`carregar_jogo` escolhe o save 1, joga tudo com "1" e não segue para a
    próxima temporada no menu pós-temporada."""
    perguntas = []

    def responder(mensagem=""):
        perguntas.append(mensagem)
        return "1"

    monkeypatch.setattr("builtins.input", responder)
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: False)
    menu.carregar_jogo(persistencia.carregar_equipes())
    return perguntas


# --- cenário 1: web -> terminal ---------------------------------------------

def test_carreira_da_web_salva_no_meio_e_concluida_pelo_terminal(monkeypatch):
    jogo = _novo_jogo_web()
    nome_save = jogo.nome_save
    assert len(jogo.classificados) == 16

    _decidir_fase_atual()  # oitavas
    ids_quartas = _ids(jogo.fase_atual["proximos"])
    resposta = client.post("/fase/seguir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    estado.encerrar_jogo()  # o jogador fecha o jogo (tudo já está gravado)

    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2026
    assert _ids(dados["classificados"]) == ids_quartas

    perguntas = _continuar_pelo_terminal_ate_o_fim(monkeypatch)

    # O terminal ofereceu "ENTER / sair" entre quartas->semi e semi->final.
    assert sum("sair" in p for p in perguntas) == 2
    assert persistencia.listar_saves() == [nome_save]
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["campeonato"] == CAMPEONATO
    assert dados["time_escolhido"].id == TIME_DO_JOGADOR
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert len(dados["historico"]) == 1
    temporada = dados["historico"][0]
    assert temporada["temporada"] == 2026
    # ID-014: as oitavas (jogadas na web antes do "sair") não entram.
    assert [len(fase["confrontos"]) for fase in temporada["fases"]] == [4, 2, 1]
    assert temporada["campeao"] in ids_quartas


def test_carreira_da_web_concluida_pelo_terminal_volta_para_a_web(monkeypatch):
    """Depois do terminal fechar a temporada, a web carrega 2027 e sorteia."""
    jogo = _novo_jogo_web()
    nome_save = jogo.nome_save
    _decidir_fase_atual()
    client.post("/fase/seguir", follow_redirects=False)
    estado.encerrar_jogo()
    _continuar_pelo_terminal_ate_o_fim(monkeypatch)
    historico_do_terminal = persistencia.carregar_jogo_salvo(nome_save)["historico"]

    jogo = _continuar_pela_tela_de_saves(client, nome_save)

    assert jogo.nome_save == nome_save
    assert jogo.temporada == 2027
    assert len(jogo.classificados) == 16
    assert jogo.historico == historico_do_terminal
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2027
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)
    assert persistencia.listar_saves() == [nome_save]


# --- cenário 2: terminal -> web ---------------------------------------------

def test_carreira_do_terminal_continuada_pela_web_ate_o_campeao(monkeypatch):
    nome_save = _criar_carreira_pelo_terminal_e_sair_no_meio(monkeypatch)
    ids_quartas = _ids(persistencia.carregar_jogo_salvo(nome_save)["classificados"])
    assert len(ids_quartas) == 8

    jogo = _continuar_pela_tela_de_saves(client, nome_save)
    assert jogo.nome_save == nome_save
    assert _ids(jogo.classificados) == ids_quartas

    fases_jogadas = _jogar_ate_o_campeao()

    assert fases_jogadas == 3  # quartas, semi, final
    assert jogo.campeao is not None
    assert jogo.campeao.id in ids_quartas
    assert persistencia.listar_saves() == [nome_save]
    assert os.listdir(persistencia.DIR_SAVES) == [os.path.basename(persistencia._caminho_save(nome_save))]
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["time_escolhido"].id == TIME_DO_JOGADOR
    assert dados["historico"] == jogo.historico
    assert len(dados["historico"]) == 1
    assert dados["historico"][0]["campeao"] == jogo.campeao.id
    assert [len(fase["confrontos"]) for fase in dados["historico"][0]["fases"]] == [4, 2, 1]


# --- cenário 3: reinício do servidor ----------------------------------------

def _reiniciar_servidor(monkeypatch):
    """Perde o jogo em memória (como reiniciar o uvicorn) e abre um cliente novo."""
    monkeypatch.setattr(estado, "_jogo_atual", None)
    return TestClient(app)


def test_duas_temporadas_na_web_e_reinicio_do_servidor_continua_do_save(monkeypatch):
    jogo = _novo_jogo_web()
    nome_save = jogo.nome_save
    _jogar_ate_o_campeao()
    assert client.post("/campeao/continuar", follow_redirects=False).status_code == 303
    _jogar_ate_o_campeao()
    historico_antes = list(jogo.historico)
    assert [registro["temporada"] for registro in historico_antes] == [2026, 2027]
    assert [len(registro["fases"]) for registro in historico_antes] == [4, 4]

    novo_cliente = _reiniciar_servidor(monkeypatch)
    assert estado.obter_jogo() is None
    assert novo_cliente.get("/fase", follow_redirects=False).status_code != 200

    jogo = _continuar_pela_tela_de_saves(novo_cliente, nome_save)

    assert jogo.nome_save == nome_save
    assert jogo.temporada == 2028
    assert jogo.historico == historico_antes
    assert jogo.time_escolhido.id == TIME_DO_JOGADOR
    assert len(jogo.classificados) == 16
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2028
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)
    assert dados["historico"] == historico_antes
    assert persistencia.listar_saves() == [nome_save]

    # Segue jogando no mesmo arquivo depois do reinício.
    _jogar_ate_o_campeao(novo_cliente)
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert [registro["temporada"] for registro in dados["historico"]] == [2026, 2027, 2028]
    assert dados["historico"] == jogo.historico
    assert persistencia.listar_saves() == [nome_save]


def test_reinicio_no_meio_da_temporada_sem_seguir_continua_da_fase_decidida(monkeypatch):
    """A fase decidida já está no disco (gravação automática): reiniciar sem
    clicar em "Seguir" retoma na fase seguinte, não na mesma."""
    jogo = _novo_jogo_web()
    nome_save = jogo.nome_save
    _decidir_fase_atual()  # oitavas
    ids_quartas = _ids(jogo.fase_atual["proximos"])

    novo_cliente = _reiniciar_servidor(monkeypatch)
    jogo = _continuar_pela_tela_de_saves(novo_cliente, nome_save)

    assert jogo.nome_save == nome_save
    assert jogo.temporada == 2026
    assert _ids(jogo.classificados) == ids_quartas
    assert _jogar_ate_o_campeao(novo_cliente) == 3
    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2027
    assert dados["historico"] == jogo.historico
    assert persistencia.listar_saves() == [nome_save]


# --- cenário 4 ---------------------------------------------------------------

def test_saves_dos_testes_ficam_em_tmp_path(tmp_path):
    jogo = _novo_jogo_web()

    caminho = persistencia._caminho_save(jogo.nome_save)
    assert os.path.exists(caminho)
    assert os.path.commonpath([caminho, str(tmp_path)]) == str(tmp_path)
    assert os.path.abspath(persistencia.DIR_SAVES) != os.path.abspath(DIR_SAVES_REAL)
