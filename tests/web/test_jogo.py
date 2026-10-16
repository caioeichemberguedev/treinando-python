import json
import random
import re

import pytest
from fastapi.testclient import TestClient

import catalogo
import persistencia
import web.estado as estado
from web.main import app

client = TestClient(app)


def _resolver_disputa_penaltis_ate_o_fim(canto="1"):
    """Sequência de `POST /fase/penaltis` com o mesmo `canto` a cada
    cobrança, até a disputa terminar e o fluxo redirecionar de volta pra
    `/fase`. Usado quando o teste só precisa que a disputa termine (vitória
    ou derrota do time do jogador não importam), sem controlar o resultado.
    """
    client.get("/fase/penaltis")  # garante que a disputa foi criada
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return resposta
        assert resposta.headers["location"] == "/fase/penaltis"


def _passar_pela_fase_atual():
    """Segue o fluxo padrão de uma fase: `GET /fase`; se tiver o confronto do
    jogador pendente, resolve a disputa de pênaltis antes de reexibir a
    fase. Retorna a resposta final de `GET /fase` (200).
    """
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        assert resposta.headers["location"] == "/fase/penaltis"
        _resolver_disputa_penaltis_ate_o_fim()
        resposta = client.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200
    return resposta


@pytest.fixture(autouse=True)
def equipes_de_teste(tmp_path, monkeypatch):
    """Isola os testes de um `equipes.json` de teste (nunca o real do
    projeto) e reseta o "jogo em andamento" em memória entre os testes.
    """
    dados = {
        "Campeonato Teste": [
            {"id": 901, "nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 902, "nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Outro Campeonato": [
            {"id": 903, "nome": "Time C", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"id": 904, "nome": "Time D", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
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


def test_tela_novo_jogo_lista_campeonatos():
    resposta = client.get("/novo-jogo")

    assert resposta.status_code == 200
    assert "Campeonato Teste" in resposta.text
    assert "Outro Campeonato" in resposta.text


def test_escolher_campeonato_valido_mostra_os_times_certos():
    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"}, follow_redirects=False)

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "Time C" not in resposta.text


def test_escolher_campeonato_inexistente_retorna_404():
    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Fantasma"})

    assert resposta.status_code == 404


def test_escolher_time_valido_redireciona_e_preenche_o_estado():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "901"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.campeonato == "Campeonato Teste"
    assert jogo.time_escolhido.id == 901
    assert jogo.time_escolhido.nome == "Time A"
    assert jogo.temporada == 2026
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}


def test_escolher_time_inexistente_retorna_404():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "999"},
    )

    assert resposta.status_code == 404


def test_escolher_time_de_outro_campeonato_retorna_404():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "903"},
    )

    assert resposta.status_code == 404


@pytest.mark.parametrize("valor", ["abc", "Time A", ""])
def test_escolher_time_com_id_nao_numerico_nunca_da_500(valor):
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": valor},
    )

    assert resposta.status_code in (404, 422)
    assert estado.obter_jogo() is None


def test_escolher_campeonato_usa_o_id_como_valor_do_radio():
    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"})

    assert 'value="901"' in resposta.text
    assert 'value="902"' in resposta.text
    assert 'value="Time A"' not in resposta.text


def test_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.get("/fase")

    assert resposta.status_code == 404


def test_seguir_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.post("/fase/seguir")

    assert resposta.status_code == 404


def test_campeao_sem_jogo_definido_retorna_404():
    resposta = client.get("/campeao")

    assert resposta.status_code == 404


def test_fase_com_confronto_do_jogador_redireciona_para_penaltis():
    """Enquanto o confronto do jogador não foi decidido, GET /fase não
    exibe a fase — redireciona pra /fase/penaltis.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"


def test_tela_penaltis_mostra_o_placar_e_pede_a_escolha_do_jogador():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    resposta = client.get("/fase/penaltis")

    assert resposta.status_code == 200
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text
    assert "canto" in resposta.text.lower()


def test_penaltis_sem_disputa_em_andamento_retorna_404():
    resposta = client.post("/fase/penaltis", data={"canto": "1"})

    assert resposta.status_code == 404


def _iniciar_disputa_de_teste():
    """Começa um jogo com 2 times e abre a disputa de pênaltis do jogador.
    Retorna o estado da disputa (`jogo.disputa_penaltis["estado"]`).
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    client.get("/fase/penaltis")
    return estado.obter_jogo().disputa_penaltis["estado"]


def _placar_da_disputa(estado_disputa):
    return (
        estado_disputa["gols_a"],
        estado_disputa["gols_b"],
        list(estado_disputa["sequencia_a"]),
        list(estado_disputa["sequencia_b"]),
    )


def test_penaltis_sem_escolha_volta_com_aleatorio_marcado_sem_cobrar():
    estado_disputa = _iniciar_disputa_de_teste()
    antes = _placar_da_disputa(estado_disputa)

    resposta = client.post("/fase/penaltis", data={}, follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis?aleatorio=1"
    assert _placar_da_disputa(estado_disputa) == antes


def test_tela_penaltis_com_param_aleatorio_marca_a_opcao():
    _iniciar_disputa_de_teste()

    com_param = client.get("/fase/penaltis?aleatorio=1")
    sem_param = client.get("/fase/penaltis")

    assert com_param.status_code == 200
    assert _radios_marcados(com_param.text) == ["aleatorio"]
    assert sem_param.status_code == 200
    assert _radios_marcados(sem_param.text) == []


def _radios_de_canto(html):
    """Lista as tags `<input type="radio" name="canto" ...>` do HTML."""
    return re.findall(r'<input\b[^>]*type="radio"[^>]*name="canto"[^>]*>', html)


def _radios_marcados(html):
    """Valores dos radios de canto que vêm com o atributo `checked`."""
    marcados = []
    for tag in _radios_de_canto(html):
        if re.search(r"\schecked\b", tag):
            marcados.append(re.search(r'value="([^"]*)"', tag).group(1))
    return marcados


def test_tela_penaltis_lista_os_quatro_radios_de_canto():
    _iniciar_disputa_de_teste()

    resposta = client.get("/fase/penaltis")

    valores = [re.search(r'value="([^"]*)"', tag).group(1) for tag in _radios_de_canto(resposta.text)]
    assert valores == ["1", "2", "3", "aleatorio"]


def test_tela_penaltis_nao_tem_radios_obrigatorios():
    _iniciar_disputa_de_teste()

    resposta = client.get("/fase/penaltis")

    radios = _radios_de_canto(resposta.text)
    assert radios
    assert all("required" not in tag for tag in radios)
    assert "required" not in resposta.text


def test_penaltis_canto_vazio_equivale_a_nao_escolher():
    """`canto=""` é tratado igual ao campo ausente: volta com Aleatório marcado."""
    estado_disputa = _iniciar_disputa_de_teste()

    resposta = client.post("/fase/penaltis", data={"canto": ""}, follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis?aleatorio=1"
    assert estado_disputa["sequencia_a"] == []
    assert estado_disputa["sequencia_b"] == []
    assert estado_disputa["gols_a"] == 0
    assert estado_disputa["gols_b"] == 0


@pytest.mark.parametrize("canto", ["1", "2", "3"])
def test_penaltis_canto_escolhido_e_usado_no_chute(monkeypatch, canto):
    estado_disputa = _iniciar_disputa_de_teste()
    monkeypatch.setattr(random, "randint", lambda a, b: int(canto))  # goleiro adivinha

    resposta = client.post("/fase/penaltis", data={"canto": canto}, follow_redirects=False)

    assert resposta.status_code == 303
    assert estado_disputa["sequencia_a"] == ["🔴"]
    assert estado_disputa["gols_a"] == 0


def test_penaltis_aleatorio_na_vez_do_goleiro_aplica_cobranca_do_adversario(monkeypatch):
    estado_disputa = _iniciar_disputa_de_teste()
    client.post("/fase/penaltis", data={"canto": "1"})
    assert len(estado_disputa["sequencia_a"]) == 1  # agora é a vez do goleiro
    antes_a = list(estado_disputa["sequencia_a"])
    valores = iter([2, 2])  # chute do adversário no 2, goleiro sorteado no 2 → defesa
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    resposta = client.post("/fase/penaltis", data={"canto": "aleatorio"}, follow_redirects=False)

    assert resposta.status_code == 303
    assert estado_disputa["sequencia_a"] == antes_a
    assert estado_disputa["sequencia_b"] == ["🔴"]
    assert estado_disputa["gols_b"] == 0


def test_penaltis_sem_escolha_na_vez_do_goleiro_nao_aplica_cobranca():
    estado_disputa = _iniciar_disputa_de_teste()
    client.post("/fase/penaltis", data={"canto": "1"})
    antes = _placar_da_disputa(estado_disputa)

    resposta = client.post("/fase/penaltis", data={}, follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis?aleatorio=1"
    assert _placar_da_disputa(estado_disputa) == antes
    tela = client.get("/fase/penaltis?aleatorio=1")
    assert _radios_marcados(tela.text) == ["aleatorio"]
    assert "Defender" in tela.text


def test_penaltis_aleatorio_sorteia_e_aplica_uma_cobranca(monkeypatch):
    estado_disputa = _iniciar_disputa_de_teste()
    valores = iter([1, 2])  # chute no 1, goleiro pula no 2 → gol
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    resposta = client.post("/fase/penaltis", data={"canto": "aleatorio"}, follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"
    assert len(estado_disputa["sequencia_a"]) == 1
    assert len(estado_disputa["sequencia_b"]) == 0
    assert estado_disputa["gols_a"] == 1


@pytest.mark.parametrize("canto", ["4", "x"])
def test_penaltis_canto_invalido_retorna_400(canto):
    _iniciar_disputa_de_teste()

    resposta = client.post("/fase/penaltis", data={"canto": canto})

    assert resposta.status_code == 400


def test_penaltis_sem_escolha_e_sem_disputa_retorna_404():
    resposta = client.post("/fase/penaltis", data={}, follow_redirects=False)

    assert resposta.status_code == 404


def test_botao_da_tela_de_penaltis_conforme_a_vez():
    estado_disputa = _iniciar_disputa_de_teste()

    vez_do_chute = client.get("/fase/penaltis")
    assert len(estado_disputa["sequencia_a"]) == len(estado_disputa["sequencia_b"])  # vez do jogador chutar
    assert "Cobrar" in vez_do_chute.text
    assert "Defender" not in vez_do_chute.text

    client.post("/fase/penaltis", data={"canto": "1"})
    vez_do_goleiro = client.get("/fase/penaltis")
    assert len(estado_disputa["sequencia_a"]) > len(estado_disputa["sequencia_b"])  # vez do goleiro
    assert "Defender" in vez_do_goleiro.text


def test_seguir_fase_com_confronto_pendente_retorna_400():
    """Não dá pra seguir de fase com o confronto do jogador ainda em
    aberto — precisa passar pela disputa de pênaltis primeiro.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    client.get("/fase")  # monta a fase (confronto_pendente ainda não decidido)

    resposta = client.post("/fase/seguir")

    assert resposta.status_code == 400


def test_fase_mostra_o_nome_da_fase_e_os_confrontos():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    resposta = _passar_pela_fase_atual()

    assert "Final" in resposta.text
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text


def test_fase_repetida_nao_recalcula_o_resultado():
    """GET /fase repetido (sem passar por /fase/seguir), depois do
    confronto do jogador decidido, tem que mostrar sempre o mesmo resultado
    já fechado, sem sortear de novo a cada request.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()

    primeira = client.get("/fase")
    segunda = client.get("/fase")

    # O id do clipPath de cada escudo é único por render (contador em
    # web/escudo.py), então é normalizado antes de comparar.
    def sem_ids_de_escudo(html):
        return re.sub(r"escudo-clip-\d+", "escudo-clip-N", html)

    assert sem_ids_de_escudo(primeira.text) == sem_ids_de_escudo(segunda.text)


def test_penaltis_corte_antecipado_decide_o_confronto_do_jogador(monkeypatch):
    """Mesmo cenário de corte antecipado de
    `tests/test_penaltis.py::test_disputa_encerra_antecipadamente_quando_alcance_e_impossivel`,
    dirigido via `/fase/penaltis`: o time do jogador abre 3x0 (sempre acerta
    o chute, o goleiro adversário nunca defende; o goleiro do jogador
    sempre defende o adversário) e a disputa termina sem completar as 5
    rodadas, sem depender de qual lado do par o jogador caiu.

    Usa a "Copa Teste" (4 times): a 1ª fase não é a final, então vencer nos
    pênaltis não pode contar título (desde o E-018 a final coroa o campeão
    assim que fica decidida).
    """
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})
    client.get("/fase/penaltis")  # garante que a disputa foi criada antes do monkeypatch

    valores = iter([1, 2, 1, 1] * 3)
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    resposta = None
    for _ in range(6):
        resposta = client.post("/fase/penaltis", data={"canto": "aleatorio"}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            break
        assert resposta.headers["location"] == "/fase/penaltis"

    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    # O confronto do jogador entra por último (depois do resolvido sozinho).
    time_a, time_b, vencedor, gols_a, gols_b = jogo.fase_atual["confrontos"][-1]
    assert vencedor.id == 905
    assert vencedor.titulos == 0  # título só é contado no campeão da temporada
    assert jogo.campeao is None
    if time_a.id == 905:
        assert (gols_a, gols_b) == (3, 0)
    else:
        assert (gols_a, gols_b) == (0, 3)


def test_fluxo_completo_ate_o_campeao_com_dois_times():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    resposta_fase = _passar_pela_fase_atual()
    assert resposta_fase.status_code == 200

    resposta_seguir = client.post("/fase/seguir", follow_redirects=False)
    assert resposta_seguir.status_code == 303
    assert resposta_seguir.headers["location"] == "/campeao"

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text
    assert "Time A" in resposta_campeao.text or "Time B" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao.id in (901, 902)
    assert jogo.campeao.titulos == 1


def test_fluxo_completo_ate_o_campeao_com_quatro_times():
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})

    ids_esperados = {905, 906, 907, 908}
    rodadas = 0

    while True:
        resposta_fase = _passar_pela_fase_atual()
        assert resposta_fase.status_code == 200

        resposta_seguir = client.post("/fase/seguir", follow_redirects=False)
        assert resposta_seguir.status_code == 303
        rodadas += 1

        if resposta_seguir.headers["location"] == "/campeao":
            break

        assert resposta_seguir.headers["location"] == "/carreira"
        assert rodadas < 5, "Temporada com 4 times não deveria levar mais de 2 fases pra terminar."

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao.id in ids_esperados
    assert rodadas == 2


def test_campeao_acumula_a_temporada_concluida_no_historico():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    jogo = estado.obter_jogo()
    assert len(jogo.historico) == 1
    assert jogo.historico[0]["temporada"] == 2026
    assert jogo.historico[0]["campeao"] == jogo.campeao.id


def test_historico_da_temporada_guarda_ids_e_nao_objetos_equipe():
    """Com 4 times (2 fases), o histórico gravado ao chegar em /campeao usa
    o formato de ids do save: campeão `int` e confrontos `[int, int, int,
    int, int]`. `fases_da_temporada` já guarda esse mesmo formato (E-014),
    então o histórico recebe uma cópia idêntica, sem converter de novo.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})
    while True:
        _passar_pela_fase_atual()
        resposta = client.post("/fase/seguir", follow_redirects=False)
        if resposta.headers["location"] == "/campeao":
            break

    jogo = estado.obter_jogo()
    registro = jogo.historico[-1]
    assert type(registro["campeao"]) is int
    assert registro["campeao"] == jogo.campeao.id
    assert len(registro["fases"]) == 2
    ids_validos = {905, 906, 907, 908}
    assert registro["fases"] == jogo.fases_da_temporada
    assert registro["fases"] is not jogo.fases_da_temporada
    for fase in registro["fases"]:
        for confronto in fase["confrontos"]:
            assert isinstance(confronto, list)
            assert len(confronto) == 5
            assert all(type(valor) is int for valor in confronto)
            assert set(confronto[:3]) <= ids_validos
    assert json.loads(json.dumps(jogo.historico)) == jogo.historico
    assert json.loads(json.dumps(jogo.fases_da_temporada)) == jogo.fases_da_temporada


def test_fase_decidida_nos_penaltis_entra_em_ids_com_o_placar_da_disputa():
    """E-014: o confronto do jogador, decidido nos pênaltis, entra em
    `fases_da_temporada` já em ids, por último, com o placar da disputa."""
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})
    client.get("/fase", follow_redirects=False)
    jogo = estado.obter_jogo()
    pendente = jogo.fase_atual["confronto_pendente"]
    assert pendente is not None
    ids_pendente = {pendente[0].id, pendente[1].id}

    _resolver_disputa_penaltis_ate_o_fim()

    assert len(jogo.fases_da_temporada) == 1
    fase = jogo.fases_da_temporada[0]
    assert fase["nome_fase"] == jogo.fase_atual["nome_fase"]
    assert len(fase["confrontos"]) == 2
    for confronto in fase["confrontos"]:
        assert type(confronto) is list
        assert all(type(valor) is int for valor in confronto)
        assert confronto[2] in confronto[:2]
        assert confronto[3] != confronto[4]
    ultimo = fase["confrontos"][-1]
    assert set(ultimo[:2]) == ids_pendente
    vencedor = ultimo[0] if ultimo[3] > ultimo[4] else ultimo[1]
    assert ultimo[2] == vencedor
    assert vencedor in {time.id for time in jogo.fase_atual["proximos"]}


def test_historico_coroado_nao_muda_ao_comecar_a_proxima_temporada():
    """A cópia das fases que vai para o histórico não pode depender da lista
    `fases_da_temporada`: limpar/encher a lista na temporada seguinte não
    altera o registro da temporada já coroada."""
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})
    while True:
        _passar_pela_fase_atual()
        resposta = client.post("/fase/seguir", follow_redirects=False)
        if resposta.headers["location"] == "/campeao":
            break
    jogo = estado.obter_jogo()
    registro_antes = json.dumps(jogo.historico)

    jogo.fases_da_temporada.append({"nome_fase": "Intrusa", "confrontos": []})
    assert json.dumps(jogo.historico) == registro_antes
    jogo.fases_da_temporada.pop()

    client.post("/campeao/continuar")
    assert jogo.fases_da_temporada == []
    _passar_pela_fase_atual()

    assert json.dumps(jogo.historico[:1]) == registro_antes
    assert len(jogo.historico[0]["fases"]) == 2
    assert len(jogo.fases_da_temporada) == 1


def test_continuar_para_proxima_temporada_sem_campeao_definido_retorna_404():
    resposta = client.post("/campeao/continuar")

    assert resposta.status_code == 404


def test_continuar_para_proxima_temporada_reinicia_o_ciclo():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    resposta = client.post("/campeao/continuar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"

    jogo = estado.obter_jogo()
    assert jogo.temporada == 2027
    assert jogo.campeao is None
    assert jogo.fase_atual is None
    assert jogo.fases_da_temporada == []
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}

    # A nova temporada segue o fluxo normal (inclusive pênaltis do jogador de novo).
    resposta_fase = _passar_pela_fase_atual()
    assert resposta_fase.status_code == 200


def test_continuar_para_proxima_temporada_preserva_a_progressao_das_equipes():
    """Finanças/fãs/títulos ganhos durante a temporada não podem se perder ao
    continuar pra próxima: o roster completo do campeonato
    (`jogo.times_do_campeonato`) precisa ser reaproveitado por identidade, e
    não recarregado do zero a partir de `equipes.json`.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    jogo = estado.obter_jogo()
    campeao = jogo.campeao
    financas_apos_titulo = campeao.financas
    assert financas_apos_titulo > 1_000_000  # prêmio de vitória + prêmio de título, somados ao valor inicial

    client.post("/campeao/continuar")

    jogo = estado.obter_jogo()
    equipe_na_nova_temporada = next(time for time in jogo.classificados if time == campeao)
    assert equipe_na_nova_temporada is campeao  # mesmo objeto, progressão preservada
    assert equipe_na_nova_temporada.financas == financas_apos_titulo


def test_completar_duas_temporadas_acumula_dois_itens_no_historico():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()
    client.post("/fase/seguir")
    client.post("/campeao/continuar")

    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    jogo = estado.obter_jogo()
    assert len(jogo.historico) == 2
    assert jogo.historico[0]["temporada"] == 2026
    assert jogo.historico[1]["temporada"] == 2027


# --- Escudos nas telas de jogo (ID-005-T4) ---

CORES_TIME_A = ["#123456", "#ABCDEF", "#0F0F0F"]
CORES_TIME_B = ["#FEDCBA", "#654321", "#F0F0F0"]


def _contar_escudos(html):
    return html.count('class="escudo"')


def _dar_cores_aos_times_de_teste():
    """Regrava o `equipes.json` de teste com cores em Time A/Time B, para
    conferir que o hex de cada time chega no HTML.
    """
    caminho = persistencia.ARQUIVO_EQUIPES
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    dados["Campeonato Teste"][0]["cores"] = CORES_TIME_A
    dados["Campeonato Teste"][1]["cores"] = CORES_TIME_B
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo)


def test_escolher_time_mostra_um_escudo_grande_por_time():
    resposta = client.post("/novo-jogo", data={"campeonato": "Copa Teste"})

    assert resposta.status_code == 200
    assert _contar_escudos(resposta.text) == 4
    assert resposta.text.count('height="40"') == 4


def test_escolher_time_mostra_as_cores_do_time():
    _dar_cores_aos_times_de_teste()

    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"})

    for cor in CORES_TIME_A + CORES_TIME_B:
        assert cor in resposta.text


def test_fase_mostra_escudos_do_seu_time_e_de_cada_confronto():
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "905"})

    resposta = _passar_pela_fase_atual()

    confrontos = estado.obter_jogo().fase_atual["confrontos"]
    assert len(confrontos) == 2
    assert _contar_escudos(resposta.text) >= 3 * len(confrontos) + 1
    assert 'aria-label="Escudo do Copa E"' in resposta.text


def test_fase_mostra_as_cores_dos_times():
    _dar_cores_aos_times_de_teste()
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    resposta = _passar_pela_fase_atual()

    for cor in CORES_TIME_A + CORES_TIME_B:
        assert cor in resposta.text


def test_penaltis_mostra_escudo_do_jogador_e_do_adversario():
    _dar_cores_aos_times_de_teste()
    _iniciar_disputa_de_teste()

    resposta = client.get("/fase/penaltis")

    assert resposta.status_code == 200
    assert 'aria-label="Escudo do Time A"' in resposta.text
    assert 'aria-label="Escudo do Time B"' in resposta.text
    assert _contar_escudos(resposta.text) == 4  # 2 no topo (40) + 2 no placar (20)
    for cor in CORES_TIME_A + CORES_TIME_B:
        assert cor in resposta.text


def test_campeao_mostra_escudo_em_destaque():
    _dar_cores_aos_times_de_teste()
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})
    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    assert 'height="96"' in resposta.text
    campeao = estado.obter_jogo().campeao
    assert f'aria-label="Escudo do {campeao}"' in resposta.text
    for cor in campeao.cores:
        assert cor in resposta.text


# --- Nome e cores do catálogo do adm nas telas de jogo (ID-008-T8) ---

NOME_NOVO_ID_1 = "Tricolor Editado"
CORES_NOVAS_ID_1 = ["#112233", "#445566"]
NOME_NOVO_ID_2 = "Alviverde Editado"
CORES_NOVAS_ID_2 = ["#778899", "#AABBCC", "#DDEEFF", "#012345"]


def _adicionar_campeonato_com_ids_do_catalogo():
    """Acrescenta ao `equipes.json` de teste um campeonato com os ids 1 e 2
    do catálogo (São Paulo e Palmeiras), para o jogo depender do catálogo.
    """
    caminho = persistencia.ARQUIVO_EQUIPES
    with open(caminho, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    dados["Campeonato Catálogo"] = [
        {"id": 1, "nome": "São Paulo", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        {"id": 2, "nome": "Palmeiras", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
    ]
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo)


def _iniciar_jogo_e_editar_catalogo():
    """Começa o jogo com o id 1 e só DEPOIS edita os ids 1 e 2 no catálogo
    (o jogo em andamento foi montado com os nomes/cores antigos).
    """
    _adicionar_campeonato_com_ids_do_catalogo()
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Catálogo", "time": "1"})
    catalogo.salvar_time_no_catalogo(1, NOME_NOVO_ID_1, CORES_NOVAS_ID_1)
    catalogo.salvar_time_no_catalogo(2, NOME_NOVO_ID_2, CORES_NOVAS_ID_2)


def _assert_mostra_nomes_e_cores_novos(html):
    assert NOME_NOVO_ID_1 in html
    assert NOME_NOVO_ID_2 in html
    assert "São Paulo" not in html
    assert "Palmeiras" not in html
    for cor in CORES_NOVAS_ID_1 + CORES_NOVAS_ID_2:
        assert cor in html


def test_escolher_time_mostra_o_nome_editado_no_catalogo():
    _adicionar_campeonato_com_ids_do_catalogo()
    catalogo.salvar_time_no_catalogo(1, NOME_NOVO_ID_1, CORES_NOVAS_ID_1)

    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Catálogo"})

    assert resposta.status_code == 200
    assert NOME_NOVO_ID_1 in resposta.text
    assert "São Paulo" not in resposta.text
    assert "Palmeiras" in resposta.text


def test_penaltis_mostra_nome_e_cores_editados_com_jogo_em_andamento():
    _iniciar_jogo_e_editar_catalogo()

    resposta = client.get("/fase/penaltis")

    assert resposta.status_code == 200
    _assert_mostra_nomes_e_cores_novos(resposta.text)


def test_fase_mostra_nome_e_cores_editados_com_jogo_em_andamento():
    _iniciar_jogo_e_editar_catalogo()

    resposta = _passar_pela_fase_atual()

    assert "Seu time: <strong class=\"time\">" in resposta.text
    _assert_mostra_nomes_e_cores_novos(resposta.text)


def test_campeao_mostra_nome_e_cores_editados_com_jogo_em_andamento():
    _iniciar_jogo_e_editar_catalogo()
    _passar_pela_fase_atual()
    client.post("/fase/seguir")

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    campeao = estado.obter_jogo().campeao
    nome_novo, cores_novas = {
        1: (NOME_NOVO_ID_1, CORES_NOVAS_ID_1),
        2: (NOME_NOVO_ID_2, CORES_NOVAS_ID_2),
    }[campeao.id]
    destaque = resposta.text.split('class="destaque"')[1].split("</p>")[0]
    assert nome_novo in destaque
    assert f'aria-label="Escudo do {nome_novo}"' in destaque
    for cor in cores_novas:
        assert cor in destaque
    assert "São Paulo" not in resposta.text
    assert "Palmeiras" not in resposta.text


def test_telas_de_jogo_com_times_de_teste_seguem_com_o_nome_do_equipes_json():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "901"})

    penaltis = client.get("/fase/penaltis")
    _resolver_disputa_penaltis_ate_o_fim()
    fase = client.get("/fase")
    client.post("/fase/seguir")
    campeao = client.get("/campeao")

    for html in (penaltis.text, fase.text):
        assert ">Time A</span>" in html
        assert ">Time B</span>" in html
    assert re.search(r">Time [AB]</span>", campeao.text)


# --- Novo jogo e escolha de time em cards (E-022-T11) ----------------------------

def test_t11_novo_jogo_usa_opcoes_com_um_radio_por_campeonato():
    texto = client.get("/novo-jogo").text

    assert 'class="opcoes' in texto
    assert texto.count('name="campeonato"') == 3
    for nome in ("Campeonato Teste", "Outro Campeonato", "Copa Teste"):
        assert f'value="{nome}"' in texto
    assert "lista-escolha" not in texto
    assert 'class="acoes-centro"' in texto
    assert ">Continuar</button>" in texto


def test_t11_novo_jogo_passa_times_e_fases_de_cada_campeonato():
    resposta = client.get("/novo-jogo")

    resumo = {c["nome"]: (c["total_times"], c["total_fases"]) for c in resposta.context["campeonatos"]}
    assert resumo == {
        "Campeonato Teste": (2, 1),
        "Outro Campeonato": (2, 1),
        "Copa Teste": (4, 2),
    }


def test_t11_novo_jogo_mostra_chips_de_times_e_fases():
    texto = client.get("/novo-jogo").text

    assert '<span class="chip">4 times</span>' in texto
    assert '<span class="chip">2 fases</span>' in texto
    assert '<span class="chip">1 fase</span>' in texto
    assert "1 fases" not in texto


def test_t11_escolher_time_tem_metricas_sem_emojis():
    texto = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"}).text

    for emoji in ("💰", "👥", "⚡", "🏆"):
        assert emoji not in texto
    for rotulo in ("Finanças", "Torcedores", "Força", "Títulos"):
        assert f'<span class="metrica-rotulo">{rotulo}</span>' in texto
    assert '<span class="metrica-valor">R$ 1,000,000</span>' in texto
    assert '<span class="metrica-valor">50/100</span>' in texto
    assert 'class="metricas-compactas"' in texto


def test_t11_escolher_time_sem_dl_dentro_do_label():
    texto = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"}).text

    for tag in ("<dl", "<dt", "<dd"):
        assert tag not in texto


def test_t11_radio_do_time_nomeado_pelo_nome_e_descrito_pelas_metricas():
    texto = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"}).text

    assert 'aria-labelledby="time-901-nome"' in texto
    assert 'aria-describedby="time-901-metricas"' in texto
    assert 'id="time-901-nome"' in texto
    assert 'id="time-901-metricas"' in texto


def test_t11_escolher_time_usa_opcoes_e_nao_lista_escolha():
    texto = client.post("/novo-jogo", data={"campeonato": "Copa Teste"}).text

    assert 'class="opcoes' in texto
    assert texto.count('class="opcao ') == 4
    assert texto.count('name="time"') == 4
    assert "lista-escolha" not in texto
    assert 'class="acoes-centro"' in texto
    assert ">Começar carreira</button>" in texto


def _equipes_extra(monkeypatch, tmp_path, dados):
    arquivo = tmp_path / "equipes_extra.json"
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))


def _time(id_time, nome, financas=1_000_000):
    return {"id": id_time, "nome": nome, "financas": financas, "fas": 1_000, "titulos": 0, "forca": 50}


def test_t11_borda_campeonato_impar_conta_fase_do_bye(monkeypatch, tmp_path):
    _equipes_extra(monkeypatch, tmp_path, {"Impar": [_time(921, "I1"), _time(922, "I2"), _time(923, "I3")]})

    resposta = client.get("/novo-jogo")

    assert resposta.context["campeonatos"] == [{"nome": "Impar", "total_times": 3, "total_fases": 2}]
    assert '<span class="chip">3 times</span>' in resposta.text
    assert '<span class="chip">2 fases</span>' in resposta.text


def test_t11_borda_campeonato_de_um_time_usa_singular_e_zero_fases(monkeypatch, tmp_path):
    _equipes_extra(monkeypatch, tmp_path, {"Solo": [_time(931, "S1")]})

    texto = client.get("/novo-jogo").text

    assert '<span class="chip">1 time</span>' in texto
    assert '<span class="chip">0 fases</span>' in texto


def test_t11_borda_nome_de_campeonato_com_caracteres_especiais_e_escapado_e_aceito(monkeypatch, tmp_path):
    nome = 'Copa "A" & <B>'
    _equipes_extra(monkeypatch, tmp_path, {nome: [_time(941, "E1"), _time(942, "E2")]})

    texto = client.get("/novo-jogo").text
    assert 'value="Copa &#34;A&#34; &amp; &lt;B&gt;"' in texto
    assert "<B>" not in texto

    escolha = client.post("/novo-jogo", data={"campeonato": nome})
    assert escolha.status_code == 200
    assert texto.count('name="campeonato"') == 1
    assert 'id="time-941-nome"' in escolha.text and 'id="time-942-metricas"' in escolha.text


def test_t11_borda_ids_aria_do_card_existem_para_cada_time():
    texto = client.post("/novo-jogo", data={"campeonato": "Copa Teste"}).text

    referencias = re.findall(r'aria-(?:labelledby|describedby)="([^"]+)"', texto)
    assert len(referencias) == 8
    for ref in referencias:
        assert texto.count(f'id="{ref}"') == 1


def test_t11_borda_financas_zeradas_aparecem_no_card(monkeypatch, tmp_path):
    _equipes_extra(monkeypatch, tmp_path, {"Pobre": [_time(951, "P1", financas=0), _time(952, "P2")]})

    texto = client.post("/novo-jogo", data={"campeonato": "Pobre"}).text

    assert '<span class="metrica-valor">R$ 0</span>' in texto


def test_t11_borda_fluxo_completo_pelos_cards_cria_o_jogo():
    client.get("/novo-jogo")
    client.post("/novo-jogo", data={"campeonato": "Copa Teste"})
    resposta = client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "906"}, follow_redirects=False)

    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.time_escolhido.id == 906
