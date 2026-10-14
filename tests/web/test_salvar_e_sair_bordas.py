"""E-018-T5: casos de borda do "Salvar e sair" (tester).

Complementa `test_jogo_salva.py`: sair no meio dos pênaltis, depois do
"Avançar", clique duplo, método errado, query `salvo` com outros valores e
o fluxo completo de várias fases com saídas intercaladas.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    dados = {
        "Campeonato Teste": [
            {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 902, "nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Copa Oito": [
            {"id": 910 + i, "nome": f"Oito {i}", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50}
            for i in range(8)
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _novo_jogo(campeonato, time):
    client.post("/novo-jogo/time", data={"campeonato": campeonato, "time": str(time)})
    return estado.obter_jogo()


def _bytes(nome_save):
    return Path(persistencia._caminho_save(nome_save)).read_bytes()


def _ids(times):
    return [t.id for t in times]


def _decidir_fase_atual():
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        client.get("/fase/penaltis")
        while True:
            r = client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
            if r.headers["location"] == "/fase":
                break
        resposta = client.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200
    return resposta


def test_salvar_e_sair_no_meio_da_disputa_responde_400_e_nao_mexe_no_save():
    jogo = _novo_jogo("Copa Oito", 910)
    assert client.get("/fase", follow_redirects=False).headers["location"] == "/fase/penaltis"
    client.get("/fase/penaltis")
    client.post("/fase/penaltis", data={"canto": "2"}, follow_redirects=False)
    client.post("/fase/penaltis", data={"canto": "3"}, follow_redirects=False)
    assert jogo.disputa_penaltis is not None
    sequencias_antes = (
        list(jogo.disputa_penaltis["estado"]["sequencia_a"]),
        list(jogo.disputa_penaltis["estado"]["sequencia_b"]),
    )
    bytes_antes = _bytes(jogo.nome_save)

    resposta = client.post("/fase/salvar-e-sair", follow_redirects=False)

    assert resposta.status_code == 400
    assert estado.obter_jogo() is jogo
    assert _bytes(jogo.nome_save) == bytes_antes
    assert (
        jogo.disputa_penaltis["estado"]["sequencia_a"],
        jogo.disputa_penaltis["estado"]["sequencia_b"],
    ) == sequencias_antes
    # a disputa segue normalmente depois do 400
    _decidir_fase_atual()
    assert jogo.fase_atual["confronto_pendente"] is None


def test_salvar_e_sair_depois_do_avancar_responde_404_sem_gravar():
    jogo = _novo_jogo("Copa Oito", 910)
    _decidir_fase_atual()
    client.post("/fase/avancar", follow_redirects=False)
    assert jogo.fase_atual is None
    bytes_antes = _bytes(jogo.nome_save)

    resposta = client.post("/fase/salvar-e-sair", follow_redirects=False)

    assert resposta.status_code == 404
    assert estado.obter_jogo() is jogo
    assert _bytes(jogo.nome_save) == bytes_antes


def test_salvar_e_sair_duas_vezes_segunda_responde_404():
    jogo = _novo_jogo("Copa Oito", 910)
    _decidir_fase_atual()
    assert client.post("/fase/salvar-e-sair", follow_redirects=False).status_code == 303
    bytes_depois = _bytes(jogo.nome_save)

    resposta = client.post("/fase/salvar-e-sair", follow_redirects=False)

    assert resposta.status_code == 404
    assert _bytes(jogo.nome_save) == bytes_depois


def test_salvar_e_sair_e_idempotente_com_a_gravacao_automatica():
    """Conteúdo igual ao da gravação automática (os bytes do .db podem mudar
    ao regravar, mas o retrato é o mesmo)."""
    jogo = _novo_jogo("Copa Oito", 910)
    _decidir_fase_atual()

    def retrato():
        d = persistencia.carregar_jogo_salvo(jogo.nome_save)
        return (d["campeonato"], d["time_escolhido"].id, d["temporada"], _ids(d["classificados"]), d["historico"])

    antes = retrato()
    client.post("/fase/salvar-e-sair", follow_redirects=False)

    assert retrato() == antes


def test_salvar_e_sair_por_get_nao_e_permitido():
    _novo_jogo("Copa Oito", 910)
    _decidir_fase_atual()

    resposta = client.get("/fase/salvar-e-sair", follow_redirects=False)

    assert resposta.status_code == 405
    assert estado.obter_jogo() is not None


@pytest.mark.parametrize("valor", ["0", "false"])
def test_tela_saves_com_salvo_falso_nao_mostra_mensagem(valor):
    resposta = client.get(f"/saves?salvo={valor}")

    assert resposta.status_code == 200
    assert "Progresso salvo!" not in resposta.text


def test_tela_saves_com_salvo_sem_carreiras_ainda_mostra_mensagem():
    resposta = client.get("/saves?salvo=1")

    assert resposta.status_code == 200
    assert "Progresso salvo!" in resposta.text
    assert "Nenhuma carreira salva encontrada." in resposta.text


def test_fluxo_completo_salvar_e_sair_a_cada_fase_ate_o_campeao():
    """8 times: sai e continua a cada fase; tudo no mesmo arquivo, temporada
    fecha em 2027 com o histórico igual ao da memória.

    Limitação conhecida (ID-014, fora do escopo do E-018): sair no meio da
    temporada perde as fases anteriores no histórico — só a final entra."""
    jogo = _novo_jogo("Copa Oito", 910)
    nome_save = jogo.nome_save

    for _ in range(3):
        _decidir_fase_atual()
        ids_proximos = _ids(jogo.fase_atual["proximos"])
        campeao = jogo.campeao
        r = client.post("/fase/salvar-e-sair", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/saves?salvo=1"
        tela = client.get(r.headers["location"])
        assert "Progresso salvo!" in tela.text and nome_save in tela.text
        assert persistencia.listar_saves() == [nome_save]
        if campeao is not None:
            break
        client.post(f"/saves/{nome_save}/carregar")
        jogo = estado.obter_jogo()
        assert jogo.nome_save == nome_save
        assert _ids(jogo.classificados) == ids_proximos

    dados = persistencia.carregar_jogo_salvo(nome_save)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert len(dados["historico"]) == 1
    assert len(dados["historico"][0]["fases"]) == 1  # ID-014: muda para 3 quando for feito
    assert dados["historico"] == jogo.historico


def test_tela_da_fase_nao_mostra_time_cru_nem_carreira_escapada():
    """Nome da carreira passa pelo autoescape do Jinja (sem HTML injetado)."""
    elenco = persistencia.carregar_equipes()["Campeonato Teste"]
    estado.iniciar_jogo(
        "Campeonato Teste", elenco[0], 2026, list(elenco), times_do_campeonato=elenco, nome_save="<b>x</b>"
    )
    estado.obter_jogo().nome_save = None  # não grava no fechar_fase
    resposta = _decidir_fase_atual()
    estado.obter_jogo().nome_save = "<b>x</b>"
    resposta = client.get("/fase")

    assert "Carreira: <strong>&lt;b&gt;x&lt;/b&gt;</strong>" in resposta.text
