"""E-019-T4 (bordas, tester): `GET /carreira` nunca muda estado nem grava, em
todos os estados do jogo, e o adversário previsto bate com o que a fase
seguinte monta de fato, fase após fase, inclusive com total ímpar (bye).
"""

import json
import os
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import catalogo
import persistencia
import web.estado as estado
import web.rotas.jogo as rotas_jogo
from equipe import Equipe
from web.main import app

client = TestClient(app)

NOMES = [f"Time {letra}" for letra in "ABCDEFGHI"]
IDS = list(range(921, 930))


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    dados = {
        "Copa Teste": [
            {"id": i, "nome": n, "financas": 1_000, "fas": 10, "titulos": 0, "forca": 50}
            for i, n in zip(IDS[:8], NOMES[:8])
        ],
    }
    arquivo = tmp_path / "equipes.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    yield


def _eq(time):
    return None if time is None else (id(time), json.dumps(time.to_dict(), sort_keys=True))


def _retrato(obj):
    """Retrato profundo do estado (inclui identidade e atributos das
    `Equipe`s, que `==` por id não enxergaria)."""
    if isinstance(obj, Equipe):
        return ("Equipe", _eq(obj))
    if isinstance(obj, dict):
        return {k: _retrato(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [type(obj).__name__] + [_retrato(v) for v in obj]
    return obj


def _retrato_jogo(jogo):
    return {campo: _retrato(getattr(jogo, campo)) for campo in jogo.__dataclass_fields__}


def _retrato_saves():
    pasta = Path(persistencia.DIR_SAVES)
    if not pasta.exists():
        return {}
    return {p.name: p.read_bytes() for p in sorted(pasta.iterdir())}


def _get_carreira_sem_efeito(jogo):
    antes, saves_antes = _retrato_jogo(jogo), _retrato_saves()
    resposta = client.get("/carreira")
    assert resposta.status_code == 200
    assert estado.obter_jogo() is jogo
    assert _retrato_jogo(jogo) == antes
    assert _retrato_saves() == saves_antes
    assert "<script" not in resposta.text.lower()
    return resposta.text


def _par(jogo):
    a, b = jogo.fase_atual["confronto_pendente"]
    return b if a == jogo.time_escolhido else a


def _resolver_disputa():
    client.get("/fase/penaltis")
    while True:
        r = client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
        assert r.status_code == 303
        if r.headers["location"] == "/fase":
            return


def test_get_carreira_nao_chama_resolver_fase_atual(monkeypatch):
    times = [Equipe(n, id=i) for i, n in zip(IDS[:4], NOMES[:4])]
    jogo = estado.iniciar_jogo("Copa Teste", times[0], 2026, times)

    def proibido(_jogo):
        raise AssertionError("GET /carreira não pode montar a fase")

    monkeypatch.setattr(rotas_jogo, "_resolver_fase_atual", proibido)
    _get_carreira_sem_efeito(jogo)
    assert jogo.fase_atual is None


@pytest.mark.parametrize("semente", range(6))
def test_carreira_inteira_pela_web_adversario_bate_e_get_nao_muda_nada(semente):
    """Joga uma temporada inteira pela web; antes de cada fase, o dashboard
    (sem efeito colateral) prevê o adversário que `GET /fase` monta."""
    random.seed(semente)
    r = client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": str(IDS[semente])},
                    follow_redirects=False)
    assert r.status_code == 303
    jogo = estado.obter_jogo()

    for _ in range(10):
        html = _get_carreira_sem_efeito(jogo)
        if jogo.campeao is not None:
            assert f"Temporada {jogo.temporada} encerrada." in html
            assert "Jogar próxima fase" not in html
            break
        vivo = jogo.time_escolhido in jogo.classificados
        if jogo.fase_atual is None:
            client.get("/fase", follow_redirects=False)
        if vivo:
            adversario = _par(jogo)
            assert adversario.nome in html
            assert adversario.nome in _get_carreira_sem_efeito(jogo)
            # no meio da disputa também não muda nada
            client.get("/fase/penaltis")
            client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
            if jogo.disputa_penaltis is not None:
                _get_carreira_sem_efeito(jogo)
                _resolver_disputa()
        else:
            assert jogo.fase_atual["confronto_pendente"] is None
            assert "Eliminado na " in html
            assert "A temporada segue sem o seu time." in html
        # decidida, sem seguir: a previsão sobre `proximos` bate com a fase seguinte
        html_decidida = _get_carreira_sem_efeito(jogo)
        segue_vivo = jogo.campeao is None and jogo.time_escolhido in jogo.fase_atual["proximos"]
        client.post("/fase/avancar", follow_redirects=False)
        if segue_vivo:
            client.get("/fase", follow_redirects=False)
            assert _par(jogo).nome in html_decidida
    else:
        pytest.fail("temporada não terminou")


@pytest.mark.parametrize("total", [3, 5, 6, 7, 9])
def test_total_impar_ou_irregular_previsao_bate_com_fase(total):
    times = [Equipe(n, id=i) for i, n in zip(IDS[:total], NOMES[:total])]
    for jogador in times:
        lista = [Equipe(t.nome, id=t.id) for t in times]
        escolhido = next(t for t in lista if t == jogador)
        jogo = estado.iniciar_jogo("Copa Teste", escolhido, 2026, lista)
        html = _get_carreira_sem_efeito(jogo)
        client.get("/fase", follow_redirects=False)
        pendente = jogo.fase_atual["confronto_pendente"]
        if pendente is None:
            assert "seu time avança direto." in html
        else:
            adversario = _par(jogo)
            assert adversario.nome in html
            outros = [t for t in lista if t != adversario and t != escolhido]
            assert not any(f">{t.nome}<" in html for t in outros)


def test_nome_editado_pelo_adm_aparece_no_dashboard(tmp_path, monkeypatch):
    """Time do catálogo real (id 1) com `Equipe` antiga em memória: o
    dashboard resolve o nome pelo catálogo efetivo (`nome_time`)."""
    arquivo = tmp_path / "catalogo_times.json"
    monkeypatch.setattr(catalogo, "ARQUIVO_CATALOGO", str(arquivo))
    catalogo.limpar_cache()
    a = Equipe("Nome Antigo A", id=1)
    b = Equipe("Nome Antigo B", id=2)
    jogo = estado.iniciar_jogo("Copa Teste", a, 2026, [a, b])
    catalogo.salvar_time_no_catalogo(1, "Novo Nome Adm", ["#112233"])
    catalogo.limpar_cache()
    try:
        html = _get_carreira_sem_efeito(jogo)
    finally:
        catalogo.limpar_cache()
    assert "Novo Nome Adm" in html
    assert "Nome Antigo A" not in html
    assert os.path.exists(arquivo)
