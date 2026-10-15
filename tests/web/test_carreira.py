"""E-019-T4/T5: dashboard da carreira (`GET /carreira`).

Cobre o bloco "Próximo jogo" em todos os estados (fase ainda não montada,
confronto pendente, fase decidida sem seguir, bye, eliminado, campeão
coroado), a ficha do time, os botões, as seções "Estatísticas da carreira"
e "Histórico da carreira" (T5, inclusive o aviso de histórico incompleto,
ID-014) e a garantia de que o GET não muda estado nem grava. `DIR_SAVES` e
`catalogo_times.json` ficam em `tmp_path` (fixtures `saves_isolados` e
`catalogo_isolado` do `tests/conftest.py`).
"""

import json
import os
import random
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import catalogo
import persistencia
import web.estado as estado
from campeonato import nome_da_fase
from equipe import Equipe
from estatisticas import resumo_da_carreira
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
    client.post("/fase/seguir", follow_redirects=False)

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
    client.post("/fase/seguir", follow_redirects=False)

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


# --- E-019-T5: estatísticas e histórico da carreira --------------------------
# Ids do catálogo real (1 a 4) para o nome do campeão vir do catálogo efetivo.

ID_JOGADOR, ID_B, ID_C, ID_D = 1, 2, 3, 4

HISTORICO_DUAS_TEMPORADAS = [
    {
        "temporada": 2026,
        "campeao": ID_JOGADOR,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa Teste",
                "confrontos": [[ID_JOGADOR, ID_B, ID_JOGADOR, 3, 1], [ID_C, ID_D, ID_D, 4, 2]],
            },
            {"nome_fase": "Final - Copa Teste", "confrontos": [[ID_JOGADOR, ID_D, ID_JOGADOR, 5, 4]]},
        ],
    },
    {
        "temporada": 2027,
        "campeao": ID_C,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa Teste",
                "confrontos": [[ID_B, ID_JOGADOR, ID_B, 2, 0], [ID_C, ID_D, ID_C, 3, 2]],
            },
            {"nome_fase": "Final - Copa Teste", "confrontos": [[ID_B, ID_C, ID_C, 1, 0]]},
        ],
    },
]

AVISO_INCOMPLETO = "Algumas fases não foram registradas"


def _celula(rotulo, valor):
    return f"<tr><th>{rotulo}</th><td>{valor}</td></tr>"


def _jogo_com_historico(historico=HISTORICO_DUAS_TEMPORADAS, temporada=2028, **kwargs):
    """Jogo em memória com `historico` (cópia profunda) e os times de ids 1 a
    4 com nomes "Antigo <id>" (o catálogo efetivo é que dá o nome na tela)."""
    times = [Equipe(f"Antigo {i}", id=i) for i in (ID_JOGADOR, ID_B, ID_C, ID_D)]
    copia = json.loads(json.dumps(historico))
    return estado.iniciar_jogo("Copa Teste", times[0], temporada, times, historico=copia, **kwargs)


def _temporada_com_primeira_fase(confrontos_na_primeira_fase):
    return {
        "temporada": 2026,
        "campeao": ID_B,
        "fases": [
            {
                "nome_fase": "Fase - Copa Teste",
                "confrontos": [[ID_B, ID_C, ID_B, 1, 0]] * confrontos_na_primeira_fase,
            }
        ],
    }


def _dezesseis_times():
    return [Equipe(f"T{i}", id=i) for i in range(1, 17)]


def test_estatisticas_batem_com_resumo_da_carreira():
    _jogo_com_historico()
    esperado = resumo_da_carreira(HISTORICO_DUAS_TEMPORADAS, ID_JOGADOR)
    assert esperado["jogos"] == 3  # conferência do exemplo escrito à mão

    html = client.get("/carreira").text

    assert "Estatísticas da carreira" in html
    assert _celula("Jogos", esperado["jogos"]) in html
    assert _celula("Vitórias", esperado["vitorias"]) in html
    assert _celula("Derrotas", esperado["derrotas"]) in html
    assert _celula("Aproveitamento", f"{esperado['aproveitamento']}%") in html
    assert _celula("Gols de pênalti marcados", esperado["gols_marcados"]) in html
    assert _celula("Gols de pênalti sofridos", esperado["gols_sofridos"]) in html
    assert _celula("Títulos na carreira", esperado["titulos"]) in html
    assert _celula("Melhor campanha", "Campeão (2026)") in html


def test_historico_da_carreira_tem_uma_linha_por_temporada_com_link():
    _jogo_com_historico()

    html = client.get("/carreira").text

    assert "Histórico da carreira" in html
    assert re.search(r'<a href="[^"]*/historico/1/jogos">2026</a>', html)
    assert re.search(r'<a href="[^"]*/historico/2/jogos">2027</a>', html)
    assert "<td>Campeão</td>" in html
    assert "<td>Eliminado na Semifinal</td>" in html
    assert catalogo.nome_do_time(ID_JOGADOR) in html
    assert catalogo.nome_do_time(ID_C) in html
    # Temporada em andamento: sem link e campeão "—".
    assert "<td>2028</td>" in html
    assert "<td>Em andamento</td>" in html
    assert "<td>—</td>" in html
    assert "/historico/3/jogos" not in html


def test_temporada_em_andamento_entra_nas_estatisticas():
    jogo = _jogo_com_historico()
    a, b, c, d = jogo.classificados
    jogo.fases_da_temporada = [
        {"nome_fase": "Semifinal - Copa Teste", "confrontos": [(a, b, a, 4, 3), (c, d, d, 1, 0)]},
    ]

    html = client.get("/carreira").text

    # 3 jogos do histórico + a semifinal de 2028 (vitória por 4x3).
    assert _celula("Jogos", 4) in html
    assert _celula("Vitórias", 3) in html
    assert _celula("Gols de pênalti marcados", 12) in html
    assert "<td>Em andamento</td>" in html


def test_eliminado_na_temporada_em_andamento_usa_a_campanha():
    jogo = _jogo_com_historico()
    a, b, c, d = jogo.classificados
    jogo.fases_da_temporada = [
        {"nome_fase": "Semifinal - Copa Teste", "confrontos": [(a, b, b, 1, 3), (c, d, d, 1, 0)]},
    ]
    jogo.classificados = [b, d]

    html = client.get("/carreira").text

    assert "<p>Eliminado na Semifinal.</p>" in html
    assert "<td>Eliminado na Semifinal</td>" in html
    assert "Semifinal - Copa Teste" not in html


def test_campeao_coroado_nao_conta_a_temporada_em_dobro():
    temporada_2028 = {
        "temporada": 2028,
        "campeao": ID_JOGADOR,
        "fases": [
            {
                "nome_fase": "Semifinal - Copa Teste",
                "confrontos": [[ID_JOGADOR, ID_B, ID_JOGADOR, 3, 0], [ID_C, ID_D, ID_C, 2, 1]],
            },
            {"nome_fase": "Final - Copa Teste", "confrontos": [[ID_JOGADOR, ID_C, ID_JOGADOR, 4, 2]]},
        ],
    }
    historico = HISTORICO_DUAS_TEMPORADAS + [temporada_2028]
    jogo = _jogo_com_historico(historico=historico)
    a, b, c, d = jogo.classificados
    # Antes de `/campeao/continuar`: a temporada já está no histórico E ainda
    # em `fases_da_temporada`.
    jogo.fases_da_temporada = [
        {"nome_fase": "Semifinal - Copa Teste", "confrontos": [(a, b, a, 3, 0), (c, d, c, 2, 1)]},
        {"nome_fase": "Final - Copa Teste", "confrontos": [(a, c, a, 4, 2)]},
    ]
    jogo.campeao = a
    esperado = resumo_da_carreira(historico, ID_JOGADOR)
    assert esperado["jogos"] == 5

    html = client.get("/carreira").text

    assert _celula("Jogos", 5) in html
    assert _celula("Títulos na carreira", 2) in html
    assert _celula("Melhor campanha", "Campeão (2026, 2028)") in html
    assert html.count(">2028</a>") == 1
    assert "<td>2028</td>" not in html
    assert "Em andamento" not in html


def test_sem_jogos_mostra_aproveitamento_traco_e_nenhuma_temporada():
    times = _times(4)
    estado.iniciar_jogo("Copa Teste", times[0], 2026, times)

    html = client.get("/carreira").text

    assert _celula("Jogos", 0) in html
    assert _celula("Aproveitamento", "—") in html
    assert _celula("Melhor campanha", "Nenhuma temporada concluída ainda") in html
    assert _celula("Títulos na carreira", 0) in html


def test_temporada_que_comeca_nas_quartas_mostra_aviso_de_historico_incompleto():
    _jogo_com_historico(
        historico=[_temporada_com_primeira_fase(4)], temporada=2027, times_do_campeonato=_dezesseis_times()
    )

    assert AVISO_INCOMPLETO in client.get("/carreira").text


def test_temporada_completa_nao_mostra_aviso():
    _jogo_com_historico(
        historico=[_temporada_com_primeira_fase(8)], temporada=2027, times_do_campeonato=_dezesseis_times()
    )

    assert AVISO_INCOMPLETO not in client.get("/carreira").text


def test_sem_times_do_campeonato_nao_mostra_aviso():
    _jogo_com_historico(historico=[_temporada_com_primeira_fase(4)], temporada=2027)

    assert AVISO_INCOMPLETO not in client.get("/carreira").text


def test_campeao_do_historico_usa_o_nome_editado_pelo_adm():
    _jogo_com_historico()
    catalogo.salvar_time_no_catalogo(ID_C, "Campeão Editado Adm", ["#112233"])
    catalogo.limpar_cache()

    html = client.get("/carreira").text

    assert "Campeão Editado Adm" in html
    assert "Antigo 3" not in html


def test_get_carreira_com_estatisticas_nao_altera_historico_nem_fases():
    jogo = _jogo_com_historico()
    a, b, c, d = jogo.classificados
    jogo.fases_da_temporada = [
        {"nome_fase": "Semifinal - Copa Teste", "confrontos": [(a, b, a, 4, 3), (c, d, d, 1, 0)]},
    ]
    historico_antes = json.dumps(jogo.historico)
    fases_antes = [dict(fase, confrontos=list(fase["confrontos"])) for fase in jogo.fases_da_temporada]

    client.get("/carreira")

    assert json.dumps(jogo.historico) == historico_antes
    assert jogo.fases_da_temporada == fases_antes
