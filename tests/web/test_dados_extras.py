"""Dados extras que as rotas passam aos templates (E-022-T4): progresso
"Fase N de M" na carreira e na fase, confronto do jogador separado dos
demais na fase e placar da final no campeão.

Os testes leem `resposta.context` (decisão 7 do E-022), sem depender do
HTML das telas.
"""

import json

import pytest
from fastapi.testclient import TestClient

import penaltis
import persistencia
import web.estado as estado
from equipe import Equipe
from web.main import app

client = TestClient(app)

ID_JOGADOR = 905


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """`equipes.json` de teste com um campeonato de 4 times (ids 905-908) e
    jogo em memória zerado entre os testes."""
    dados = {
        "Copa Teste": [
            {"id": id_time, "nome": nome, "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50}
            for id_time, nome in zip((905, 906, 907, 908), ("Copa E", "Copa F", "Copa G", "Copa H"))
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _novo_jogo():
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": "Copa Teste", "time": str(ID_JOGADOR)}, follow_redirects=False
    )
    assert resposta.status_code == 303


def _decidir_penaltis(monkeypatch, jogador_vence: bool):
    """Resolve a disputa pendente do jogador com resultado controlado: o
    sorteio do `penaltis` sempre dá 1, então chutar no 2 é gol e defender no
    1 é defesa (e o contrário para perder). Só a disputa do jogador usa o
    sorteio fixo — os confrontos automáticos já foram resolvidos no `/fase`.
    """
    resposta = client.get("/fase", follow_redirects=False)
    assert resposta.headers["location"] == "/fase/penaltis"
    client.get("/fase/penaltis")
    chute, defesa = ("2", "1") if jogador_vence else ("1", "2")
    with monkeypatch.context() as m:
        m.setattr(penaltis.random, "randint", lambda inicio, fim: 1)
        while True:
            estado_disputa = estado.obter_jogo().disputa_penaltis["estado"]
            vez_do_jogador = len(estado_disputa["sequencia_a"]) == len(estado_disputa["sequencia_b"])
            canto = chute if vez_do_jogador else defesa
            resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
            if resposta.headers["location"] == "/fase":
                break
    vencedor = estado.obter_jogo().fase_atual["confrontos"][-1][2]
    assert (vencedor.id == ID_JOGADOR) == jogador_vence


def _seguir():
    resposta = client.post("/fase/seguir", follow_redirects=False)
    assert resposta.status_code == 303
    return resposta.headers["location"]


# --- progresso "Fase N de M" -------------------------------------------------


def test_progresso_na_carreira_e_na_fase_ao_longo_da_temporada(monkeypatch):
    _novo_jogo()

    resposta = client.get("/carreira")
    assert resposta.context["proximo_jogo"]["situacao"] == "jogo"
    assert resposta.context["proximo_jogo"]["progresso"] == {"numero": 1, "total": 2}

    _decidir_penaltis(monkeypatch, jogador_vence=True)

    resposta = client.get("/carreira")
    assert resposta.context["proximo_jogo"]["situacao"] == "jogo"
    assert resposta.context["proximo_jogo"]["progresso"] == {"numero": 2, "total": 2}

    resposta = client.get("/fase")
    assert resposta.status_code == 200
    assert resposta.context["progresso"] == {"numero": 1, "total": 2}

    assert _seguir() == "/carreira"
    resposta = client.get("/carreira")
    assert resposta.context["proximo_jogo"]["progresso"] == {"numero": 2, "total": 2}


def test_progresso_com_confronto_pendente_usa_os_times_da_fase():
    _novo_jogo()
    resposta = client.get("/fase", follow_redirects=False)
    assert resposta.headers["location"] == "/fase/penaltis"

    resposta = client.get("/carreira")

    assert resposta.context["proximo_jogo"]["situacao"] == "jogo"
    assert resposta.context["proximo_jogo"]["progresso"] == {"numero": 1, "total": 2}


def test_progresso_none_sem_times_do_campeonato_na_carreira():
    jogador = Equipe("Copa E", id=ID_JOGADOR)
    estado.iniciar_jogo("Copa Teste", jogador, 2026, [jogador, Equipe("Copa F", id=906)])

    resposta = client.get("/carreira")

    assert resposta.status_code == 200
    assert resposta.context["proximo_jogo"]["situacao"] == "jogo"
    assert resposta.context["proximo_jogo"]["progresso"] is None


def test_progresso_none_sem_times_do_campeonato_na_fase():
    jogador = Equipe("Copa E", id=ID_JOGADOR)
    outros = [Equipe(nome, id=id_time) for id_time, nome in ((906, "Copa F"), (907, "Copa G"), (908, "Copa H"))]
    # Jogador fora dos classificados: a fase sai decidida direto (200).
    estado.iniciar_jogo("Copa Teste", jogador, 2026, outros)

    resposta = client.get("/fase")

    assert resposta.status_code == 200
    assert resposta.context["progresso"] is None


# --- confronto do jogador separado ------------------------------------------


def test_fase_separa_o_confronto_do_jogador(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=True)

    resposta = client.get("/fase")

    contexto = resposta.context
    confronto_jogador = contexto["confronto_jogador"]
    assert confronto_jogador is not None
    assert ID_JOGADOR in (confronto_jogador[0].id, confronto_jogador[1].id)
    assert confronto_jogador not in contexto["outros_confrontos"]
    assert len(contexto["outros_confrontos"]) == len(contexto["confrontos"]) - 1
    assert all(
        ID_JOGADOR not in (confronto[0].id, confronto[1].id) for confronto in contexto["outros_confrontos"]
    )


def test_fase_sem_o_jogador_eliminado_nao_tem_confronto_do_jogador(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=False)
    assert _seguir() == "/carreira"

    resposta = client.get("/fase")

    assert resposta.status_code == 200
    assert resposta.context["confronto_jogador"] is None
    assert resposta.context["outros_confrontos"] == resposta.context["confrontos"]


# --- placar da final ----------------------------------------------------------


def test_campeao_recebe_o_placar_da_final(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=True)
    assert _seguir() == "/carreira"
    _decidir_penaltis(monkeypatch, jogador_vence=True)
    assert _seguir() == "/campeao"

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    jogo = estado.obter_jogo()
    id_a, id_b, id_vencedor, gols_a, gols_b = jogo.historico[-1]["fases"][-1]["confrontos"][0]
    assert resposta.context["final"] == {
        "id_a": id_a,
        "id_b": id_b,
        "id_vencedor": id_vencedor,
        "gols_a": gols_a,
        "gols_b": gols_b,
    }
    assert id_vencedor == ID_JOGADOR


def test_campeao_sem_historico_tem_final_none():
    jogador = Equipe("Copa E", id=ID_JOGADOR)
    jogo = estado.iniciar_jogo("Copa Teste", jogador, 2026, [jogador, Equipe("Copa F", id=906)])
    jogo.campeao = jogador

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    assert resposta.context["final"] is None


# --- casos de borda (game-tester) ---------------------------------------------


def test_progresso_no_bye_com_numero_impar_de_times():
    """3 times: o último da lista avança direto (bye) na fase 1 de 2."""
    jogador = Equipe("Copa E", id=ID_JOGADOR)
    outros = [Equipe("Copa F", id=906), Equipe("Copa G", id=907)]
    times = outros + [jogador]
    estado.iniciar_jogo("Copa Teste", jogador, 2026, list(times), times_do_campeonato=times)

    resposta = client.get("/carreira")

    assert resposta.status_code == 200
    assert resposta.context["proximo_jogo"]["situacao"] == "bye"
    assert resposta.context["proximo_jogo"]["progresso"] == {"numero": 1, "total": 2}


def test_eliminado_na_carreira_nao_tem_progresso(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=False)

    resposta = client.get("/carreira")

    assert resposta.context["proximo_jogo"]["situacao"] == "eliminado"
    assert "progresso" not in resposta.context["proximo_jogo"]


def _retrato(jogo):
    return (
        jogo.temporada,
        list(jogo.classificados),
        json.dumps(jogo.historico, default=str),
        json.dumps(jogo.fases_da_temporada, default=str),
        repr(jogo.fase_atual),
        jogo.campeao,
    )


def _arquivos_de_save():
    import os

    return {
        nome: os.path.getmtime(os.path.join(persistencia.DIR_SAVES, nome))
        for nome in os.listdir(persistencia.DIR_SAVES)
    } if os.path.isdir(persistencia.DIR_SAVES) else {}


def test_gets_com_dados_extras_nao_mudam_estado_nem_gravam(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=True)
    jogo = estado.obter_jogo()
    antes, saves_antes = _retrato(jogo), _arquivos_de_save()

    for _ in range(2):
        assert client.get("/carreira").status_code == 200
        assert client.get("/fase").status_code == 200

    assert _retrato(estado.obter_jogo()) == antes
    assert _arquivos_de_save() == saves_antes


def test_get_campeao_repetido_nao_muda_estado_nem_grava(monkeypatch):
    _novo_jogo()
    _decidir_penaltis(monkeypatch, jogador_vence=True)
    assert _seguir() == "/carreira"
    _decidir_penaltis(monkeypatch, jogador_vence=True)
    assert _seguir() == "/campeao"
    jogo = estado.obter_jogo()
    antes, saves_antes = _retrato(jogo), _arquivos_de_save()

    finais = [client.get("/campeao").context["final"] for _ in range(2)]

    assert finais[0] == finais[1] is not None
    assert _retrato(estado.obter_jogo()) == antes
    assert _arquivos_de_save() == saves_antes


def test_campeao_com_historico_de_outra_temporada_tem_final_none():
    """Só a final da temporada atual vale: histórico antigo não aparece."""
    jogador = Equipe("Copa E", id=ID_JOGADOR)
    historico = [{
        "temporada": 2025,
        "campeao": ID_JOGADOR,
        "fases": [{"nome_fase": "Final - Copa Teste", "confrontos": [[ID_JOGADOR, 906, ID_JOGADOR, 3, 1]]}],
    }]
    jogo = estado.iniciar_jogo("Copa Teste", jogador, 2026, [jogador, Equipe("Copa F", id=906)], historico=historico)
    jogo.campeao = jogador

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    assert resposta.context["final"] is None
