"""E-019-T4: esqueleto do dashboard da carreira (`GET /carreira`).

Cobre o bloco "Próximo jogo" em todos os estados (fase ainda não montada,
confronto pendente, fase decidida sem seguir, bye, eliminado, campeão
coroado), a ficha do time, os botões e a garantia de que o GET não muda
estado nem grava. `DIR_SAVES` fica em `tmp_path` (fixture `saves_isolados`
do `tests/conftest.py`).
"""

import json
import os
import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from campeonato import nome_da_fase
from equipe import Equipe
from web.main import app

client = TestClient(app)

NOMES_COPA = [f"Copa {letra}" for letra in "EFGHIJKL"]
IDS_COPA = list(range(905, 913))


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """`equipes.json` de teste ("Copa Teste" com 8 times, ids sem catálogo)
    e nenhum jogo em memória."""
    dados = {
        "Copa Teste": [
            {"id": id_time, "nome": nome, "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50}
            for id_time, nome in zip(IDS_COPA, NOMES_COPA)
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


# --- auxiliares ---------------------------------------------------------


def _times(quantidade):
    return [Equipe(nome, id=id_time) for id_time, nome in zip(IDS_COPA[:quantidade], NOMES_COPA[:quantidade])]


def _novo_jogo(time=IDS_COPA[0]):
    """Novo jogo pela web, sem seguir o 303 para `/fase` (fase não montada)."""
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": "Copa Teste", "time": str(time)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    return estado.obter_jogo()


def _resolver_disputa(canto="1"):
    """Cobra até a disputa do jogador terminar (volta para `/fase`)."""
    client.get("/fase/penaltis")
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return


def _novo_jogo_com_fase_decidida(jogador_vence):
    """Novo jogo pela web com a 1ª fase decidida (sem seguir), tentando
    sementes de `random` até o jogador vencer (ou perder) a disputa."""
    for semente in range(200):
        estado.encerrar_jogo()
        random.seed(semente)
        jogo = _novo_jogo()
        client.get("/fase", follow_redirects=False)
        _resolver_disputa()
        if (jogo.time_escolhido in jogo.fase_atual["proximos"]) == jogador_vence:
            return jogo
    pytest.fail("nenhuma semente produziu o resultado desejado")


def _par_pendente_do_jogador(jogo):
    time_a, time_b = jogo.fase_atual["confronto_pendente"]
    return time_b if time_a == jogo.time_escolhido else time_a


def _assert_mostra_so_o_adversario(html, jogo, adversario):
    """O "Próximo jogo" cita o seu time e o adversário — e nenhum outro
    time do campeonato (a ficha não lista nomes)."""
    assert adversario.nome in html
    assert jogo.time_escolhido.nome in html
    for time in jogo.times_do_campeonato or jogo.classificados:
        if time != adversario and time != jogo.time_escolhido:
            assert time.nome not in html


# --- 404 e conteúdo básico ----------------------------------------------


def test_carreira_sem_jogo_retorna_404_com_mensagem():
    resposta = client.get("/carreira")

    assert resposta.status_code == 404
    assert resposta.json()["detail"] == (
        'Nenhuma carreira em andamento. Continue uma em "Carreiras salvas" ou comece um novo jogo.'
    )


def test_carreira_abre_com_200_e_sem_javascript():
    _novo_jogo()

    resposta = client.get("/carreira")

    assert resposta.status_code == 200
    assert "<script" not in resposta.text.lower()
    assert "Copa Teste" in resposta.text
    assert "Temporada 2026" in resposta.text


# --- Próximo jogo --------------------------------------------------------


def test_jogo_novo_mostra_o_mesmo_adversario_que_a_fase_monta():
    random.seed(7)
    jogo = _novo_jogo()
    assert jogo.fase_atual is None

    html = client.get("/carreira").text
    client.get("/fase", follow_redirects=False)
    adversario = _par_pendente_do_jogador(jogo)

    assert nome_da_fase(4) in html
    assert "escudo-clip-" in html
    _assert_mostra_so_o_adversario(html, jogo, adversario)


def test_confronto_pendente_mostra_o_adversario_do_par_pendente():
    random.seed(3)
    jogo = _novo_jogo()
    client.get("/fase", follow_redirects=False)
    adversario = _par_pendente_do_jogador(jogo)

    html = client.get("/carreira").text

    _assert_mostra_so_o_adversario(html, jogo, adversario)


def test_fase_decidida_sem_seguir_calcula_sobre_os_proximos():
    jogo = _novo_jogo_com_fase_decidida(jogador_vence=True)
    # Na web o vencedor do jogador vai para o fim de `proximos`.
    assert jogo.fase_atual["proximos"][-1] == jogo.time_escolhido
    adversario = jogo.fase_atual["proximos"][-2]

    html = client.get("/carreira").text

    assert nome_da_fase(2) in html
    _assert_mostra_so_o_adversario(html, jogo, adversario)


def test_depois_de_avancar_mostra_o_par_real_da_proxima_fase():
    jogo = _novo_jogo_com_fase_decidida(jogador_vence=True)
    client.post("/fase/avancar", follow_redirects=False)

    html = client.get("/carreira").text
    client.get("/fase", follow_redirects=False)
    adversario = _par_pendente_do_jogador(jogo)

    assert nome_da_fase(2) in html
    _assert_mostra_so_o_adversario(html, jogo, adversario)


def test_bye_mostra_que_o_time_avanca_direto():
    times = _times(3)
    estado.iniciar_jogo("Copa Teste", times[2], 2026, times)

    html = client.get("/carreira").text

    assert f"{nome_da_fase(1)}: seu time avança direto." in html


def test_eliminado_mostra_a_fase_da_derrota():
    _novo_jogo_com_fase_decidida(jogador_vence=False)

    html = client.get("/carreira").text

    assert f"Eliminado na {nome_da_fase(4)}." in html
    assert "A temporada segue sem o seu time." in html
    assert "Copa Teste" in html  # sufixo do campeonato não vai no rótulo
    assert f"{nome_da_fase(4)} - Copa Teste" not in html


def test_eliminado_depois_de_avancar_continua_mostrando_a_fase_e_o_link():
    _novo_jogo_com_fase_decidida(jogador_vence=False)
    client.post("/fase/avancar", follow_redirects=False)

    html = client.get("/carreira").text

    assert f"Eliminado na {nome_da_fase(4)}." in html
    assert "Jogar próxima fase" in html


def test_eliminado_sem_fases_registradas_mostra_eliminado_nesta_temporada():
    times = _times(4)
    # Carregou no meio: o jogador já não está nos classificados e
    # `fases_da_temporada` começa vazia (ID-014).
    estado.iniciar_jogo("Copa Teste", times[0], 2026, times[1:3])

    html = client.get("/carreira").text

    assert "Eliminado nesta temporada." in html
    assert "A temporada segue sem o seu time." in html


# --- Campeão coroado -------------------------------------------------------


def test_campeao_coroado_mostra_temporada_encerrada_e_form_para_continuar():
    times = _times(4)
    jogo = estado.iniciar_jogo("Copa Teste", times[0], 2026, [times[1]])
    jogo.campeao = times[1]

    html = client.get("/carreira").text

    assert "Temporada 2026 encerrada." in html
    assert times[1].nome in html
    assert "Você foi campeão!" not in html
    assert re.search(r'<form method="post" action="[^"]*/campeao/continuar">', html)
    assert "Ir para a temporada 2027" in html
    assert "Jogar próxima fase" not in html


def test_campeao_coroado_sendo_o_jogador_mostra_parabens():
    times = _times(2)
    jogo = estado.iniciar_jogo("Copa Teste", times[0], 2026, [times[0]])
    jogo.campeao = times[0]

    html = client.get("/carreira").text

    assert "Você foi campeão!" in html


# --- Ficha, botões e nome do save -----------------------------------------


def test_ficha_mostra_os_dados_do_time_escolhido():
    jogador = Equipe("Copa E", financas=1_234_567, fas=89_012, forca=77, titulos=3, id=905)
    estado.iniciar_jogo("Copa Teste", jogador, 2026, [jogador, Equipe("Copa F", id=906)])

    html = client.get("/carreira").text

    assert "R$ 1,234,567" in html
    assert "89,012" in html
    assert "77/100" in html
    assert "<th>Títulos</th><td>3</td>" in html
    assert "Torcedores" in html


def test_botoes_jogar_proxima_fase_e_voltar_ao_menu():
    times = _times(4)
    estado.iniciar_jogo("Copa Teste", times[0], 2026, times)

    html = client.get("/carreira").text

    assert re.search(r'<a class="botao" href="[^"]*/fase">Jogar próxima fase</a>', html)
    assert re.search(r'<a class="botao" href="http://testserver/">Voltar ao menu</a>', html)


def test_nome_do_save_aparece_so_quando_existe():
    times = _times(4)
    estado.iniciar_jogo("Copa Teste", times[0], 2026, times)
    assert "Carreira: <strong>" not in client.get("/carreira").text

    estado.iniciar_jogo("Copa Teste", times[0], 2026, times, nome_save="7_14_10_2026")
    html = client.get("/carreira").text

    assert "Carreira: <strong>7_14_10_2026</strong>" in html


# --- Só leitura -----------------------------------------------------------


def test_get_carreira_nao_altera_estado_nem_grava():
    jogo = _novo_jogo()
    caminho = Path(persistencia._caminho_save(jogo.nome_save))
    bytes_antes = caminho.read_bytes()
    arquivos_antes = sorted(os.listdir(persistencia.DIR_SAVES))
    classificados_antes = list(jogo.classificados)

    client.get("/carreira")
    client.get("/carreira")

    assert jogo.fase_atual is None
    assert jogo.disputa_penaltis is None
    assert jogo.classificados == classificados_antes
    assert jogo.fases_da_temporada == []
    assert caminho.read_bytes() == bytes_antes
    assert sorted(os.listdir(persistencia.DIR_SAVES)) == arquivos_antes


def test_get_carreira_com_campeao_nao_avanca_a_temporada():
    jogo = _novo_jogo()
    jogo.campeao = jogo.time_escolhido
    caminho = Path(persistencia._caminho_save(jogo.nome_save))
    bytes_antes = caminho.read_bytes()

    client.get("/carreira")

    assert jogo.temporada == 2026
    assert jogo.campeao == jogo.time_escolhido
    assert caminho.read_bytes() == bytes_antes
