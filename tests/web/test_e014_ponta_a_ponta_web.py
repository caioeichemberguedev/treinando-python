"""E-014-T5: ponta a ponta só pela web (o teste "manual" do critério).

Jogar as oitavas na web, "Voltar ao menu", reiniciar o servidor (estado em
memória zerado + `TestClient` novo), continuar a carreira em `/saves` e ver
as oitavas no histórico ao fim da temporada. Variantes: sair mais de uma vez
na mesma temporada e sair sem clicar em "Seguir".
"""

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

CAMPEONATO = "Copa do Brasil"
TIME_DO_JOGADOR = 1


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    persistencia.restaurar_equipes_padrao()


def _decidir_fase_atual(cliente):
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


def _seguir(cliente):
    resposta = cliente.post("/fase/seguir", follow_redirects=False)
    assert resposta.status_code == 303
    return resposta.headers["location"]


def _reiniciar_servidor_e_continuar(nome_save):
    """Zera o jogo em memória, abre um cliente novo e clica em "Continuar"."""
    estado._jogo_atual = None
    cliente = TestClient(app)
    assert nome_save in cliente.get("/saves").text
    resposta = cliente.post(f"/saves/{nome_save}/carregar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    tela = cliente.get("/carreira")
    assert tela.status_code == 200
    assert "Algumas fases não foram registradas" not in tela.text
    return cliente


def _jogar_ate_o_campeao(cliente):
    while True:
        _decidir_fase_atual(cliente)
        if _seguir(cliente) == "/campeao":
            assert cliente.get("/campeao").status_code == 200
            return


def _tamanhos_das_fases(nome_save):
    historico = persistencia.carregar_jogo_salvo(nome_save)["historico"]
    assert len(historico) == 1
    return [len(fase["confrontos"]) for fase in historico[0]["fases"]]


def _novo_jogo(cliente):
    resposta = cliente.post(
        "/novo-jogo/time", data={"campeonato": CAMPEONATO, "time": str(TIME_DO_JOGADOR)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return estado.obter_jogo().nome_save


def _conferir_fim_da_temporada(cliente, nome_save):
    assert _tamanhos_das_fases(nome_save) == [8, 4, 2, 1]
    jogos = cliente.get("/historico/1/jogos")
    assert jogos.status_code == 200
    assert "Oitavas" in jogos.text
    carreira_salva = persistencia.carregar_jogo_salvo(nome_save)
    assert carreira_salva["fases_da_temporada"] == []
    assert carreira_salva["historico"][0]["campeao"] is not None
    tela = cliente.get("/carreira")
    assert "Algumas fases não foram registradas" not in tela.text


def test_oitavas_menu_reinicio_continuar_e_terminar_guarda_as_quatro_fases():
    cliente = TestClient(app)
    nome_save = _novo_jogo(cliente)
    _decidir_fase_atual(cliente)
    assert _seguir(cliente) == "/carreira"
    assert cliente.get("/").status_code == 200  # "Voltar ao menu"
    assert len(persistencia.carregar_jogo_salvo(nome_save)["fases_da_temporada"]) == 1

    cliente = _reiniciar_servidor_e_continuar(nome_save)
    assert [len(f["confrontos"]) for f in estado.obter_jogo().fases_da_temporada] == [8]
    _jogar_ate_o_campeao(cliente)

    _conferir_fim_da_temporada(cliente, nome_save)


def test_sair_duas_vezes_na_mesma_temporada_guarda_as_quatro_fases():
    cliente = TestClient(app)
    nome_save = _novo_jogo(cliente)
    _decidir_fase_atual(cliente)
    _seguir(cliente)

    cliente = _reiniciar_servidor_e_continuar(nome_save)
    _decidir_fase_atual(cliente)
    _seguir(cliente)
    assert len(persistencia.carregar_jogo_salvo(nome_save)["fases_da_temporada"]) == 2

    cliente = _reiniciar_servidor_e_continuar(nome_save)
    assert [len(f["confrontos"]) for f in estado.obter_jogo().fases_da_temporada] == [8, 4]
    _jogar_ate_o_campeao(cliente)

    _conferir_fim_da_temporada(cliente, nome_save)


def test_sair_sem_clicar_em_seguir_tambem_guarda_a_fase_decidida():
    cliente = TestClient(app)
    nome_save = _novo_jogo(cliente)
    _decidir_fase_atual(cliente)  # oitavas decididas, sem "Seguir"

    cliente = _reiniciar_servidor_e_continuar(nome_save)
    _jogar_ate_o_campeao(cliente)

    _conferir_fim_da_temporada(cliente, nome_save)


def test_segunda_temporada_comeca_sem_fases_e_tambem_fecha_completa():
    cliente = TestClient(app)
    nome_save = _novo_jogo(cliente)
    _jogar_ate_o_campeao(cliente)
    assert cliente.post("/campeao/continuar", follow_redirects=False).status_code == 303
    assert estado.obter_jogo().fases_da_temporada == []
    assert persistencia.carregar_jogo_salvo(nome_save)["fases_da_temporada"] == []

    _decidir_fase_atual(cliente)
    _seguir(cliente)
    cliente = _reiniciar_servidor_e_continuar(nome_save)
    _jogar_ate_o_campeao(cliente)

    historico = persistencia.carregar_jogo_salvo(nome_save)["historico"]
    assert [[len(f["confrontos"]) for f in t["fases"]] for t in historico] == [[8, 4, 2, 1], [8, 4, 2, 1]]
