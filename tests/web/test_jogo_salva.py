"""E-018-T3: a web grava a carreira em `saves/` nos mesmos momentos do
terminal — novo jogo, fase decidida (antes do "Seguir"), final (temporada
+ 1, sem classificados) e "seguir para a próxima temporada".

E-019-T6: o "Seguir" da fase decidida (`POST /fase/seguir`) só navega até o
dashboard (`/carreira`) ou `/campeao`, sem gravar; "Salvar e sair" não
existe mais (as bordas que valiam para ele foram trazidas para o "Seguir").

`DIR_SAVES` fica em `tmp_path` pela fixture `saves_isolados` do
`tests/conftest.py`; o nome do save vem de `date.today()`, então os testes
usam `estado.obter_jogo().nome_save`.
"""

import json
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)


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


def _novo_jogo(campeonato, time):
    client.post("/novo-jogo/time", data={"campeonato": campeonato, "time": str(time)})
    return estado.obter_jogo()


def _save(jogo):
    return persistencia.carregar_jogo_salvo(jogo.nome_save)


def _bytes_do_save(jogo):
    return Path(persistencia._caminho_save(jogo.nome_save)).read_bytes()


def _ids(times):
    return [time.id for time in times]


def _resolver_disputa(canto="1"):
    """Cobra até a disputa do jogador terminar (volta para `/fase`)."""
    client.get("/fase/penaltis")
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
        if resposta.headers["location"] == "/campeao":
            return


def test_novo_jogo_cria_o_save_da_carreira():
    jogo = _novo_jogo("Copa Teste", 905)

    assert jogo.nome_save is not None
    assert persistencia.listar_saves() == [jogo.nome_save]
    dados = _save(jogo)
    assert dados["campeonato"] == "Copa Teste"
    assert dados["time_escolhido"].id == 905
    assert dados["temporada"] == 2026
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)
    assert dados["historico"] == []


def test_fase_decidida_grava_os_classificados_que_avancam_antes_do_seguir():
    jogo = _novo_jogo("Copa Teste", 905)

    _decidir_fase_atual()

    assert jogo.campeao is None
    dados = _save(jogo)
    assert dados["temporada"] == 2026
    assert _ids(dados["classificados"]) == _ids(jogo.fase_atual["proximos"])
    assert len(dados["classificados"]) == 2

    bytes_antes = _bytes_do_save(jogo)
    client.get("/fase")
    client.get("/fase")
    assert _bytes_do_save(jogo) == bytes_antes


def test_final_decidida_coroa_o_campeao_e_grava_a_proxima_temporada():
    jogo = _novo_jogo("Campeonato Teste", 901)

    _decidir_fase_atual()

    assert jogo.campeao is not None
    assert jogo.campeao.titulos == 1
    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == jogo.historico
    assert len(dados["historico"]) == 1
    assert dados["historico"][0]["temporada"] == 2026
    assert dados["historico"][0]["campeao"] == jogo.campeao.id
    assert len(dados["historico"][0]["fases"]) == 1

    bytes_antes = _bytes_do_save(jogo)
    resposta = client.post("/fase/seguir", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/campeao"
    assert _bytes_do_save(jogo) == bytes_antes
    assert jogo.campeao.titulos == 1  # o "Seguir" não coroa de novo


def test_final_com_quatro_times_grava_historico_com_duas_fases():
    jogo = _novo_jogo("Copa Teste", 905)

    _jogar_temporada_ate_o_campeao()

    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == jogo.historico
    assert len(dados["historico"][0]["fases"]) == 2


def _perder_disputa_do_jogador(monkeypatch):
    """Jogador erra todos os chutes (`randint` sempre 1 = goleiro no canto
    1, chute no 1) e o adversário marca todos (chute 1, goleiro do jogador
    no 2): eliminado por corte antecipado."""
    client.get("/fase/penaltis")
    with monkeypatch.context() as m:
        m.setattr(random, "randint", lambda a, b: 1)
        while True:
            disputa = estado.obter_jogo().disputa_penaltis["estado"]
            vez_do_jogador = len(disputa["sequencia_a"]) == len(disputa["sequencia_b"])
            canto = "1" if vez_do_jogador else "2"
            resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
            if resposta.headers["location"] == "/fase":
                return


def test_jogador_eliminado_a_fase_seguinte_e_decidida_e_gravada_no_get(monkeypatch):
    jogo = _novo_jogo("Copa Teste", 905)
    _perder_disputa_do_jogador(monkeypatch)

    assert 905 not in _ids(jogo.fase_atual["proximos"])
    assert _ids(_save(jogo)["classificados"]) == _ids(jogo.fase_atual["proximos"])

    client.post("/fase/seguir")
    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 200  # nada pendente: decidida no GET
    assert jogo.campeao is not None
    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == jogo.historico
    assert len(dados["historico"][0]["fases"]) == 2


def test_continuar_para_a_proxima_temporada_grava_o_novo_sorteio():
    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()
    historico_2026 = list(jogo.historico)

    client.post("/campeao/continuar")

    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)
    assert dados["historico"] == historico_2026
    assert persistencia.listar_saves() == [jogo.nome_save]


def test_duas_temporadas_seguidas_acumulam_no_historico_do_save():
    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()
    client.post("/campeao/continuar")
    _jogar_temporada_ate_o_campeao()

    dados = _save(jogo)
    assert dados["temporada"] == 2028
    assert [registro["temporada"] for registro in dados["historico"]] == [2026, 2027]
    assert dados["historico"] == jogo.historico
    assert persistencia.listar_saves() == [jogo.nome_save]


def test_estado_sem_nome_save_nao_grava_nada():
    """Estado montado à mão (sem `nome_save`) joga só em memória."""
    elenco = persistencia.carregar_equipes()["Campeonato Teste"]
    estado.iniciar_jogo("Campeonato Teste", elenco[0], 2026, list(elenco), times_do_campeonato=elenco)

    _decidir_fase_atual()

    assert estado.obter_jogo().campeao is not None
    assert persistencia.listar_saves() == []


# --- Regressão: GET /fase depois da final + "Seguir" (título em dobro) ---


@pytest.mark.parametrize(("campeonato", "time"), [("Campeonato Teste", 901), ("Copa Teste", 905)])
def test_get_fase_depois_de_seguir_da_final_nao_coroa_de_novo(campeonato, time):
    """Voltar/recarregar `/fase` depois de "Seguir" da final redireciona
    para `/campeao` sem fechar uma "fase de 1 time": título conta uma vez só,
    o histórico tem uma temporada e o save segue em 2027."""
    jogo = _novo_jogo(campeonato, time)
    _jogar_temporada_ate_o_campeao()
    campeao = jogo.campeao
    bytes_antes = _bytes_do_save(jogo)

    for _ in range(2):
        resposta = client.get("/fase", follow_redirects=False)
        assert resposta.status_code == 303
        assert resposta.headers["location"] == "/campeao"
    assert client.get("/fase").status_code == 200  # segue até /campeao

    assert jogo.campeao is campeao
    assert campeao.titulos == 1
    assert len(jogo.historico) == 1
    assert _bytes_do_save(jogo) == bytes_antes
    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == jogo.historico


def test_fechar_fase_com_campeao_ja_coroado_nao_faz_nada():
    """Proteção dentro do próprio `_fechar_fase`, independente da rota."""
    from web.rotas.jogo import _resolver_fase_atual

    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()
    bytes_antes = _bytes_do_save(jogo)

    _resolver_fase_atual(jogo)  # classificados == [campeao]: fase de 1 time

    assert jogo.campeao.titulos == 1
    assert len(jogo.historico) == 1
    assert len(jogo.fases_da_temporada) == 1
    assert _bytes_do_save(jogo) == bytes_antes


# --- E-019-T6: "Seguir" (substitui "Avançar fase" e "Salvar e sair") ---


MENSAGEM_PENDENTE = "Ainda falta decidir a disputa de pênaltis do seu time nesta fase."


def test_tela_da_fase_tem_um_unico_botao_seguir_e_o_nome_da_carreira():
    jogo = _novo_jogo("Campeonato Teste", 901)

    resposta = _decidir_fase_atual()

    assert resposta.text.count("<form") == 1
    assert '<form method="post" action="http://testserver/fase/seguir">' in resposta.text
    assert ">Seguir</button>" in resposta.text
    assert "Avançar fase" not in resposta.text
    assert "Salvar e sair" not in resposta.text
    assert f"Carreira: <strong>{jogo.nome_save}</strong>" in resposta.text


def test_tela_da_fase_sem_nome_save_nao_mostra_a_carreira():
    elenco = persistencia.carregar_equipes()["Campeonato Teste"]
    estado.iniciar_jogo("Campeonato Teste", elenco[0], 2026, list(elenco), times_do_campeonato=elenco)

    resposta = _decidir_fase_atual()

    assert "Carreira:" not in resposta.text
    assert ">Seguir</button>" in resposta.text


def test_seguir_fase_nao_final_vai_para_o_dashboard_sem_gravar():
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()
    proximos = list(jogo.fase_atual["proximos"])
    bytes_antes = _bytes_do_save(jogo)

    resposta = client.post("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert _ids(jogo.classificados) == _ids(proximos)  # mesma ordem
    assert jogo.fase_atual is None
    assert _bytes_do_save(jogo) == bytes_antes
    assert client.get("/carreira").status_code == 200


def test_campeao_tem_botao_seguir_que_leva_ao_dashboard_da_nova_temporada():
    jogo = _novo_jogo("Campeonato Teste", 901)
    _jogar_temporada_ate_o_campeao()

    tela = client.get("/campeao")
    assert '<form method="post" action="http://testserver/campeao/continuar">' in tela.text
    assert ">Seguir</button>" in tela.text
    assert "Seguir para a próxima temporada" not in tela.text

    resposta = client.post("/campeao/continuar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    assert jogo.temporada == 2027
    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert _ids(dados["classificados"]) == _ids(jogo.classificados)


def test_seguir_fase_sem_jogo_responde_404():
    resposta = client.post("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 404


def test_seguir_fase_com_confronto_pendente_responde_400_e_nao_mexe_no_save():
    jogo = _novo_jogo("Copa Teste", 905)
    client.get("/fase", follow_redirects=False)  # monta a fase; disputa pendente
    bytes_antes = _bytes_do_save(jogo)

    resposta = client.post("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_PENDENTE
    assert estado.obter_jogo() is jogo
    assert jogo.fase_atual is not None
    assert _bytes_do_save(jogo) == bytes_antes


def test_seguir_fase_no_meio_da_disputa_responde_400_e_a_disputa_continua():
    jogo = _novo_jogo("Copa Teste", 905)
    assert client.get("/fase", follow_redirects=False).headers["location"] == "/fase/penaltis"
    client.get("/fase/penaltis")
    client.post("/fase/penaltis", data={"canto": "2"}, follow_redirects=False)
    client.post("/fase/penaltis", data={"canto": "3"}, follow_redirects=False)
    sequencias_antes = (
        list(jogo.disputa_penaltis["estado"]["sequencia_a"]),
        list(jogo.disputa_penaltis["estado"]["sequencia_b"]),
    )
    bytes_antes = _bytes_do_save(jogo)

    resposta = client.post("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 400
    assert _bytes_do_save(jogo) == bytes_antes
    assert (
        jogo.disputa_penaltis["estado"]["sequencia_a"],
        jogo.disputa_penaltis["estado"]["sequencia_b"],
    ) == sequencias_antes
    _decidir_fase_atual()  # a disputa segue normalmente depois do 400
    assert jogo.fase_atual["confronto_pendente"] is None


def test_seguir_fase_duas_vezes_segunda_responde_404_sem_gravar():
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()
    assert client.post("/fase/seguir", follow_redirects=False).status_code == 303
    ids_classificados = _ids(jogo.classificados)
    bytes_antes = _bytes_do_save(jogo)

    resposta = client.post("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 404
    assert _ids(jogo.classificados) == ids_classificados
    assert _bytes_do_save(jogo) == bytes_antes


def test_seguir_fase_por_get_nao_e_permitido():
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()

    resposta = client.get("/fase/seguir", follow_redirects=False)

    assert resposta.status_code == 405
    assert jogo.fase_atual is not None


@pytest.mark.parametrize("rota", ["/fase/avancar", "/fase/salvar-e-sair"])
def test_rotas_antigas_da_fase_nao_existem_mais(rota):
    _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()

    resposta = client.post(rota, follow_redirects=False)

    assert resposta.status_code == 404
    assert estado.obter_jogo() is not None


def test_tela_saves_com_salvo_na_url_nao_mostra_progresso_salvo():
    _novo_jogo("Copa Teste", 905)

    resposta = client.get("/saves?salvo=1")

    assert resposta.status_code == 200
    assert "Progresso salvo!" not in resposta.text


def test_fluxo_completo_seguir_passa_pelo_dashboard_ate_a_nova_temporada():
    """Novo jogo → fase → Seguir → dashboard → GET /fase → ... → campeão →
    Seguir → dashboard já em 2027, tudo num save só."""
    jogo = _novo_jogo("Copa Teste", 905)

    for _ in range(5):
        _decidir_fase_atual()
        resposta = client.post("/fase/seguir", follow_redirects=False)
        if resposta.headers["location"] == "/campeao":
            break
        assert resposta.headers["location"] == "/carreira"
        assert client.get("/carreira").status_code == 200
    else:
        pytest.fail("A temporada com 4 times deveria terminar em 2 fases.")

    assert client.get("/campeao").status_code == 200
    resposta = client.post("/campeao/continuar", follow_redirects=False)
    assert resposta.headers["location"] == "/carreira"

    dashboard = client.get("/carreira")
    assert dashboard.status_code == 200
    assert "2027" in dashboard.text
    assert jogo.temporada == 2027
    assert persistencia.listar_saves() == [jogo.nome_save]


def test_continuar_depois_de_fechar_o_jogo_segue_no_mesmo_arquivo():
    """Sem "Salvar e sair": o save já está gravado ao decidir a fase, então
    fechar o jogo em memória e continuar em "Carreiras salvas" retoma dali."""
    jogo = _novo_jogo("Copa Teste", 905)
    _decidir_fase_atual()
    nome_save = jogo.nome_save
    ids_proximos = _ids(jogo.fase_atual["proximos"])
    estado.encerrar_jogo()

    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    continuado = estado.obter_jogo()
    assert continuado.nome_save == nome_save
    assert continuado.temporada == 2026
    assert _ids(continuado.classificados) == ids_proximos

    _decidir_fase_atual()  # a final

    assert continuado.campeao is not None
    assert persistencia.listar_saves() == [nome_save]
    dados = _save(continuado)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None


def test_fechar_o_jogo_depois_da_final_e_carregar_sorteia_a_proxima_temporada():
    jogo = _novo_jogo("Campeonato Teste", 901)
    _decidir_fase_atual()
    nome_save = jogo.nome_save
    estado.encerrar_jogo()

    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert len(dados["historico"]) == 1

    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)

    assert resposta.headers["location"] == "/carreira"
    continuado = estado.obter_jogo()
    assert continuado.temporada == 2027
    assert sorted(_ids(continuado.classificados)) == [901, 902]
    assert _ids(persistencia.carregar_jogo_salvo(nome_save)["classificados"]) == _ids(continuado.classificados)
    assert persistencia.listar_saves() == [nome_save]


def test_tela_da_fase_escapa_o_nome_da_carreira():
    """Nome da carreira passa pelo autoescape do Jinja (sem HTML injetado)."""
    elenco = persistencia.carregar_equipes()["Campeonato Teste"]
    estado.iniciar_jogo("Campeonato Teste", elenco[0], 2026, list(elenco), times_do_campeonato=elenco)
    _decidir_fase_atual()  # sem nome_save: não grava no fechar_fase
    estado.obter_jogo().nome_save = "<b>x</b>"

    resposta = client.get("/fase")

    assert "Carreira: <strong>&lt;b&gt;x&lt;/b&gt;</strong>" in resposta.text


def test_fechar_e_continuar_a_cada_fase_ate_o_campeao_guarda_todas_as_fases():
    """Seguir + fechar o jogo + continuar a cada fase: tudo no mesmo arquivo
    e a temporada fecha em 2027 com o histórico igual ao da memória — com
    todas as fases, inclusive as jogadas antes de fechar (E-014)."""
    jogo = _novo_jogo("Copa Teste", 905)
    nome_save = jogo.nome_save

    for _ in range(3):
        _decidir_fase_atual()
        ids_proximos = _ids(jogo.fase_atual["proximos"])
        bytes_antes = _bytes_do_save(jogo)
        resposta = client.post("/fase/seguir", follow_redirects=False)
        assert _bytes_do_save(jogo) == bytes_antes  # o "Seguir" não grava
        if resposta.headers["location"] == "/campeao":
            break
        assert resposta.headers["location"] == "/carreira"
        estado.encerrar_jogo()
        assert persistencia.listar_saves() == [nome_save]
        client.post(f"/saves/{nome_save}/carregar")
        jogo = estado.obter_jogo()
        assert jogo.nome_save == nome_save
        assert _ids(jogo.classificados) == ids_proximos
    else:
        pytest.fail("A temporada com 4 times deveria terminar em 2 fases.")

    assert jogo.campeao.titulos == 1
    dados = _save(jogo)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert len(dados["historico"]) == 1
    assert [len(f["confrontos"]) for f in dados["historico"][0]["fases"]] == [2, 1]
    assert dados["historico"] == jogo.historico
    assert persistencia.listar_saves() == [nome_save]
