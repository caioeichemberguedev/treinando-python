import json
import random
import re

import pytest
from fastapi.testclient import TestClient

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
            {"nome": "Time A", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Time B", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Outro Campeonato": [
            {"nome": "Time C", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Time D", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
        ],
        "Copa Teste": [
            {"nome": "Copa E", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa F", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa G", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
            {"nome": "Copa H", "financas": 1_000_000, "fas": 1_000, "titulos": 0, "forca": 50},
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
        data={"campeonato": "Campeonato Teste", "time": "Time A"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"

    jogo = estado.obter_jogo()
    assert jogo is not None
    assert jogo.campeonato == "Campeonato Teste"
    assert jogo.time_escolhido == "Time A"
    assert jogo.temporada == 2026
    assert {str(time) for time in jogo.classificados} == {"Time A", "Time B"}


def test_escolher_time_inexistente_retorna_404():
    resposta = client.post(
        "/novo-jogo/time",
        data={"campeonato": "Campeonato Teste", "time": "Time Fantasma"},
    )

    assert resposta.status_code == 404


def test_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.get("/fase")

    assert resposta.status_code == 404


def test_avancar_fase_sem_jogo_em_andamento_retorna_404():
    resposta = client.post("/fase/avancar")

    assert resposta.status_code == 404


def test_campeao_sem_jogo_definido_retorna_404():
    resposta = client.get("/campeao")

    assert resposta.status_code == 404


def test_fase_com_confronto_do_jogador_redireciona_para_penaltis():
    """Enquanto o confronto do jogador não foi decidido, GET /fase não
    exibe a fase — redireciona pra /fase/penaltis.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = client.get("/fase", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase/penaltis"


def test_tela_penaltis_mostra_o_placar_e_pede_a_escolha_do_jogador():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

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
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
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


def test_avancar_fase_com_confronto_pendente_retorna_400():
    """Não dá pra avançar de fase com o confronto do jogador ainda em
    aberto — precisa passar pela disputa de pênaltis primeiro.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    client.get("/fase")  # monta a fase (confronto_pendente ainda não decidido)

    resposta = client.post("/fase/avancar")

    assert resposta.status_code == 400


def test_fase_mostra_o_nome_da_fase_e_os_confrontos():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta = _passar_pela_fase_atual()

    assert "Final" in resposta.text
    assert "Time A" in resposta.text
    assert "Time B" in resposta.text


def test_fase_repetida_nao_recalcula_o_resultado():
    """GET /fase repetido (sem passar por /fase/avancar), depois do
    confronto do jogador decidido, tem que mostrar sempre o mesmo resultado
    já fechado, sem sortear de novo a cada request.
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
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
    """
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
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
    time_a, time_b, vencedor, gols_a, gols_b = jogo.fase_atual["confrontos"][0]
    assert vencedor == "Time A"
    assert vencedor.titulos == 0  # título só é contado no campeão da temporada
    if time_a == "Time A":
        assert (gols_a, gols_b) == (3, 0)
    else:
        assert (gols_a, gols_b) == (0, 3)


def test_fluxo_completo_ate_o_campeao_com_dois_times():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

    resposta_fase = _passar_pela_fase_atual()
    assert resposta_fase.status_code == 200

    resposta_avancar = client.post("/fase/avancar", follow_redirects=False)
    assert resposta_avancar.status_code == 303
    assert resposta_avancar.headers["location"] == "/campeao"

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text
    assert "Time A" in resposta_campeao.text or "Time B" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao in ("Time A", "Time B")
    assert jogo.campeao.titulos == 1


def test_fluxo_completo_ate_o_campeao_com_quatro_times():
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "Copa E"})

    times_esperados = {"Copa E", "Copa F", "Copa G", "Copa H"}
    rodadas = 0

    while True:
        resposta_fase = _passar_pela_fase_atual()
        assert resposta_fase.status_code == 200

        resposta_avancar = client.post("/fase/avancar", follow_redirects=False)
        assert resposta_avancar.status_code == 303
        rodadas += 1

        if resposta_avancar.headers["location"] == "/campeao":
            break

        assert resposta_avancar.headers["location"] == "/fase"
        assert rodadas < 5, "Temporada com 4 times não deveria levar mais de 2 fases pra terminar."

    resposta_campeao = client.get("/campeao")
    assert resposta_campeao.status_code == 200
    assert "Campeão" in resposta_campeao.text

    jogo = estado.obter_jogo()
    assert jogo.campeao in times_esperados
    assert rodadas == 2


def test_campeao_acumula_a_temporada_concluida_no_historico():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()
    client.post("/fase/avancar")

    jogo = estado.obter_jogo()
    assert len(jogo.historico) == 1
    assert jogo.historico[0]["temporada"] == 2026
    assert jogo.historico[0]["campeao"] == jogo.campeao


def test_continuar_para_proxima_temporada_sem_campeao_definido_retorna_404():
    resposta = client.post("/campeao/continuar")

    assert resposta.status_code == 404


def test_continuar_para_proxima_temporada_reinicia_o_ciclo():
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()
    client.post("/fase/avancar")

    resposta = client.post("/campeao/continuar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/fase"

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
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()
    client.post("/fase/avancar")

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
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()
    client.post("/fase/avancar")
    client.post("/campeao/continuar")

    _passar_pela_fase_atual()
    client.post("/fase/avancar")

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
    assert resposta.text.count('width="40"') == 4


def test_escolher_time_mostra_as_cores_do_time():
    _dar_cores_aos_times_de_teste()

    resposta = client.post("/novo-jogo", data={"campeonato": "Campeonato Teste"})

    for cor in CORES_TIME_A + CORES_TIME_B:
        assert cor in resposta.text


def test_fase_mostra_escudos_do_seu_time_e_de_cada_confronto():
    client.post("/novo-jogo/time", data={"campeonato": "Copa Teste", "time": "Copa E"})

    resposta = _passar_pela_fase_atual()

    confrontos = estado.obter_jogo().fase_atual["confrontos"]
    assert len(confrontos) == 2
    assert _contar_escudos(resposta.text) >= 3 * len(confrontos) + 1
    assert 'aria-label="Escudo do Copa E"' in resposta.text


def test_fase_mostra_as_cores_dos_times():
    _dar_cores_aos_times_de_teste()
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})

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
    client.post("/novo-jogo/time", data={"campeonato": "Campeonato Teste", "time": "Time A"})
    _passar_pela_fase_atual()
    client.post("/fase/avancar")

    resposta = client.get("/campeao")

    assert resposta.status_code == 200
    assert 'width="96"' in resposta.text
    campeao = estado.obter_jogo().campeao
    assert f'aria-label="Escudo do {campeao}"' in resposta.text
    for cor in campeao.cores:
        assert cor in resposta.text
