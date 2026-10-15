"""E-019-T7: ponta a ponta do dashboard da carreira (`GET /carreira`) com a
Copa do Brasil de verdade (16 times do elenco padrão, gerado por
`restaurar_equipes_padrao()` em `tmp_path`).

Cenários:
1. Temporada inteira pela web passando pelo dashboard entre todas as fases:
   a cada visita o "Próximo jogo" bate com o confronto que `GET /fase` monta
   logo depois.
2. Jogador eliminado na 1ª fase: "Eliminado na Oitavas de Final" em todas
   as visitas e o fluxo fase a fase segue até o campeão.
3. Duas temporadas completas: estatísticas do dashboard iguais a
   `resumo_da_carreira` do histórico lido do save.
4. Carreira criada no terminal, saída depois das oitavas, carregada na web:
   cai no dashboard; ao concluir a temporada aparece o aviso de histórico
   incompleto (ID-014) e a campanha da temporada não quebra.
5. "Voltar ao menu" (`GET /`) + "Continuar" em `/saves` → dashboard com os
   mesmos números.

Já cobertos em outros arquivos (não se repetem aqui): estados isolados do
"Próximo jogo", ficha e botões (`test_carreira.py`); previsão x fase com
"Copa Teste" de 8 e totais ímpares (bye), GET sem efeito colateral
(`test_carreira_bordas.py`); estatísticas pelo fluxo real com o histórico em
memória, links do histórico e aviso após retomar uma carreira da web
(`test_carreira_estatisticas_bordas.py`); fluxo "Seguir" → dashboard até
2027 e fechar/continuar a cada fase (`test_jogo_salva.py`); terminal → web
até o campeão sem olhar o dashboard (`test_saves_web_integracao.py`).

Nada fora de `tmp_path` é tocado: a fixture confere no fim que o `saves/` e
o `equipes.json` reais ficaram intactos.
"""

import os
import random
import re

import pytest
from fastapi.testclient import TestClient

import catalogo
import menu
import persistencia
import web.estado as estado
from campeonato import nome_da_fase
from estatisticas import campanha_na_temporada, resumo_da_carreira
from web.main import app

# Valores reais, lidos na importação (antes de qualquer fixture).
DIR_SAVES_REAL = persistencia.DIR_SAVES
ARQUIVO_EQUIPES_REAL = persistencia.ARQUIVO_EQUIPES

CAMPEONATO = "Copa do Brasil"
TIME_DO_JOGADOR = 1  # São Paulo
AVISO_INCOMPLETO = "Algumas fases não foram registradas"
OITAVAS = nome_da_fase(8)

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
    """Copa do Brasil padrão em `tmp_path`, nenhum jogo em memória, `cls` do
    terminal desligado; no fim, `saves/` e `equipes.json` reais intactos."""
    retrato_antes = _retrato_do_disco_real()
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    persistencia.restaurar_equipes_padrao()
    yield
    assert _retrato_do_disco_real() == retrato_antes
    assert os.path.commonpath([persistencia.DIR_SAVES, str(tmp_path)]) == str(tmp_path)


# --- auxiliares: leitura do dashboard --------------------------------------


def _dashboard():
    resposta = client.get("/carreira")
    assert resposta.status_code == 200
    return resposta.text


def _secao(html, titulo):
    return html.split(f"<h2>{titulo}</h2>", 1)[1].split("</section>", 1)[0]


def _times_do_proximo_jogo(html):
    """Nomes exibidos (depois do escudo) no bloco "Próximo jogo"."""
    return re.findall(r"</svg>([^<]+)</span>", _secao(html, "Próximo jogo"))


def _celulas(html):
    return dict(re.findall(r"<tr><th>([^<]+)</th><td>(.*?)</td></tr>", html))


def _linhas_do_historico(html):
    """(temporada, campanha) de cada linha da tabela "Histórico da carreira"."""
    return re.findall(
        r"<tr>\s*<td>(?:<a [^>]*>)?(\d+)(?:</a>)?</td>\s*<td>([^<]+)</td>",
        _secao(html, "Histórico da carreira"),
    )


def _normalizar(html):
    return re.sub(r"escudo-clip-\d+", "escudo-clip-N", html)


def _assert_estatisticas(html, temporadas, id_time):
    esperado = resumo_da_carreira(temporadas, id_time)
    celulas = _celulas(html)
    assert celulas["Jogos"] == str(esperado["jogos"])
    assert celulas["Vitórias"] == str(esperado["vitorias"])
    assert celulas["Derrotas"] == str(esperado["derrotas"])
    aproveitamento = "—" if esperado["aproveitamento"] is None else f"{esperado['aproveitamento']:.1f}%"
    assert celulas["Aproveitamento"] == aproveitamento
    assert celulas["Gols de pênalti marcados"] == str(esperado["gols_marcados"])
    assert celulas["Gols de pênalti sofridos"] == str(esperado["gols_sofridos"])
    assert celulas["Títulos na carreira"] == str(esperado["titulos"])


# --- auxiliares: jogar pela web ---------------------------------------------


def _novo_jogo_web(semente):
    random.seed(semente)
    resposta = client.post(
        "/novo-jogo/time", data={"campeonato": CAMPEONATO, "time": str(TIME_DO_JOGADOR)}, follow_redirects=False
    )
    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    assert len(jogo.classificados) == 16
    return jogo


def _adversario_pendente(jogo):
    time_a, time_b = jogo.fase_atual["confronto_pendente"]
    return time_b if time_a == jogo.time_escolhido else time_a


def _disputar(monkeypatch, vencer):
    """Joga a disputa do jogador até o fim com `randint` fixo em 1: chutar
    no 2 é gol e defender no 1 pega tudo (vencer); o contrário perde."""
    client.get("/fase/penaltis")
    chute, defesa = ("2", "1") if vencer else ("1", "2")
    with monkeypatch.context() as m:
        m.setattr(random, "randint", lambda a, b: 1)
        while True:
            disputa = estado.obter_jogo().disputa_penaltis["estado"]
            vez_de_chutar = len(disputa["sequencia_a"]) == len(disputa["sequencia_b"])
            resposta = client.post(
                "/fase/penaltis", data={"canto": chute if vez_de_chutar else defesa}, follow_redirects=False
            )
            assert resposta.status_code == 303
            if resposta.headers["location"] == "/fase":
                return


def _disputar_no_canto_1():
    """Disputa com o `random` do jogo (resultado varia com a semente)."""
    client.get("/fase/penaltis")
    while True:
        resposta = client.post("/fase/penaltis", data={"canto": "1"}, follow_redirects=False)
        assert resposta.status_code == 303
        if resposta.headers["location"] == "/fase":
            return


def _jogar_fase(disputar):
    """"Jogar próxima fase" (`GET /fase`), resolve a disputa do jogador (se
    houver) e clica em "Seguir". Devolve o destino do "Seguir"."""
    resposta = client.get("/fase", follow_redirects=False)
    if resposta.status_code == 303:
        assert resposta.headers["location"] == "/fase/penaltis"
        disputar()
        resposta = client.get("/fase", follow_redirects=False)
    assert resposta.status_code == 200
    seguir = client.post("/fase/seguir", follow_redirects=False)
    assert seguir.status_code == 303
    assert seguir.headers["location"] in ("/carreira", "/campeao")
    return seguir.headers["location"]


def _jogar_temporada_pelo_dashboard(disputar):
    """Dashboard → fase → Seguir → dashboard ... até a tela do campeão."""
    for _ in range(6):
        _dashboard()
        if _jogar_fase(disputar) == "/campeao":
            assert client.get("/campeao").status_code == 200
            return
    pytest.fail("A Copa do Brasil (16 times) deveria terminar em 4 fases.")


# --- cenário 1 -----------------------------------------------------------------


@pytest.mark.parametrize("semente", [0, 1, 2])
def test_temporada_inteira_pelo_dashboard_proximo_jogo_bate_com_a_fase(semente, monkeypatch):
    jogo = _novo_jogo_web(semente)
    fases_previstas = []

    for _ in range(6):
        html = _dashboard()
        if jogo.campeao is not None:
            break
        assert jogo.fase_atual is None  # o dashboard não monta a fase
        nomes = _times_do_proximo_jogo(html)

        resposta = client.get("/fase", follow_redirects=False)
        assert resposta.status_code == 303  # o jogador vence sempre: tem disputa
        adversario = _adversario_pendente(jogo)
        fase = jogo.fase_atual["nome_fase"].split(" - ")[0]
        assert nomes == [catalogo.nome_para_exibir(jogo.time_escolhido), catalogo.nome_para_exibir(adversario)]
        assert f"{fase}:" in _secao(html, "Próximo jogo")
        fases_previstas.append(fase)

        _disputar(monkeypatch, vencer=True)
        assert client.post("/fase/seguir", follow_redirects=False).status_code == 303
        if jogo.campeao is not None:
            assert client.get("/campeao").status_code == 200
            assert client.post("/campeao/continuar", follow_redirects=False).headers["location"] == "/carreira"
            break
    else:
        pytest.fail("A temporada deveria terminar em 4 fases.")

    assert fases_previstas == [nome_da_fase(n) for n in (8, 4, 2, 1)]
    html = _dashboard()
    assert "Temporada 2027" in html
    assert ("2026", "Campeão") in _linhas_do_historico(html)
    assert persistencia.listar_saves() == [jogo.nome_save]


# --- cenário 2 -----------------------------------------------------------------


def test_eliminado_nas_oitavas_dashboard_mostra_a_fase_ate_o_campeao(monkeypatch):
    jogo = _novo_jogo_web(5)

    client.get("/fase", follow_redirects=False)
    _disputar(monkeypatch, vencer=False)
    assert jogo.time_escolhido not in jogo.fase_atual["proximos"]
    assert client.post("/fase/seguir", follow_redirects=False).headers["location"] == "/carreira"

    fases_sem_o_jogador = 0
    while jogo.campeao is None:
        html = _dashboard()
        assert f"<p>Eliminado na {OITAVAS}.</p>" in html
        assert "A temporada segue sem o seu time." in html
        assert "Jogar próxima fase" in html
        assert _times_do_proximo_jogo(html) == []
        resposta = client.get("/fase", follow_redirects=False)
        assert resposta.status_code == 200  # nada pendente: decidida no GET
        client.post("/fase/seguir", follow_redirects=False)
        fases_sem_o_jogador += 1

    assert fases_sem_o_jogador == 3  # quartas, semifinal e final
    assert client.get("/campeao").status_code == 200
    assert client.post("/campeao/continuar", follow_redirects=False).headers["location"] == "/carreira"
    html = _dashboard()
    assert ("2026", f"Eliminado na {OITAVAS}") in _linhas_do_historico(html)
    assert _celulas(html)["Jogos"] == "1"
    assert _celulas(html)["Derrotas"] == "1"
    assert _celulas(html)["Melhor campanha"] == f"Eliminado na {OITAVAS} (2026)"


# --- cenário 3 -----------------------------------------------------------------


@pytest.mark.parametrize("semente", [3, 8])
def test_duas_temporadas_estatisticas_batem_com_o_historico_do_save(semente):
    jogo = _novo_jogo_web(semente)
    id_time = jogo.time_escolhido.id

    _jogar_temporada_pelo_dashboard(_disputar_no_canto_1)
    client.post("/campeao/continuar", follow_redirects=False)
    _jogar_temporada_pelo_dashboard(_disputar_no_canto_1)

    # Campeão de 2027 coroado (antes de continuar): 2027 já está no save.
    historico_do_save = persistencia.carregar_jogo_salvo(jogo.nome_save)["historico"]
    assert [t["temporada"] for t in historico_do_save] == [2026, 2027]
    assert [len(t["fases"]) for t in historico_do_save] == [4, 4]
    html = _dashboard()
    _assert_estatisticas(html, historico_do_save, id_time)
    assert AVISO_INCOMPLETO not in html

    client.post("/campeao/continuar", follow_redirects=False)
    html = _dashboard()
    historico_do_save = persistencia.carregar_jogo_salvo(jogo.nome_save)["historico"]
    _assert_estatisticas(html, historico_do_save, id_time)
    linhas = _linhas_do_historico(html)
    assert linhas == [
        ("2026", campanha_na_temporada(historico_do_save[0], id_time)["rotulo"]),
        ("2027", campanha_na_temporada(historico_do_save[1], id_time)["rotulo"]),
        ("2028", "Em andamento"),
    ]


# --- cenário 4 -----------------------------------------------------------------


def _criar_carreira_pelo_terminal_e_sair_depois_das_oitavas(monkeypatch, semente):
    """Novo jogo no terminal ("1" para tudo) e "sair" depois das oitavas."""
    random.seed(semente)
    monkeypatch.setattr("builtins.input", lambda mensagem="": "sair" if "sair" in mensagem else "1")
    menu.novo_jogo(persistencia.carregar_equipes())
    saves = persistencia.listar_saves()
    assert len(saves) == 1
    return saves[0]


# Sementes do terminal: na 3 o São Paulo passa das oitavas; na 1 cai nelas.
@pytest.mark.parametrize(("semente", "passou_das_oitavas"), [(3, True), (1, False)])
def test_carreira_do_terminal_carregada_na_web_abre_o_dashboard_e_avisa_historico_incompleto(
    monkeypatch, semente, passou_das_oitavas
):
    nome_save = _criar_carreira_pelo_terminal_e_sair_depois_das_oitavas(monkeypatch, semente)
    ids_quartas = [t.id for t in persistencia.carregar_jogo_salvo(nome_save)["classificados"]]
    assert len(ids_quartas) == 8
    assert (TIME_DO_JOGADOR in ids_quartas) == passou_das_oitavas

    assert nome_save in client.get("/saves").text
    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/carreira"
    jogo = estado.obter_jogo()

    html = _dashboard()
    assert "Temporada 2026" in html
    assert f"Carreira: <strong>{nome_save}</strong>" in html
    assert AVISO_INCOMPLETO not in html  # nada registrado ainda: nada a julgar
    if passou_das_oitavas:
        assert len(_times_do_proximo_jogo(html)) == 2
        assert f"{nome_da_fase(4)}:" in _secao(html, "Próximo jogo")
    else:
        assert "<p>Eliminado nesta temporada.</p>" in html  # oitavas perdidas (ID-014)

    _jogar_temporada_pelo_dashboard(_disputar_no_canto_1)

    html = _dashboard()
    assert AVISO_INCOMPLETO in html
    historico = persistencia.carregar_jogo_salvo(nome_save)["historico"]
    assert [len(fase["confrontos"]) for fase in historico[0]["fases"]] == [4, 2, 1]
    campanha = campanha_na_temporada(historico[0], TIME_DO_JOGADOR)
    if not passou_das_oitavas:
        assert campanha["rotulo"] == "Não registrada"
    else:
        assert campanha["rotulo"] != "Não registrada"
    assert _linhas_do_historico(html) == [("2026", campanha["rotulo"])]
    _assert_estatisticas(html, historico, TIME_DO_JOGADOR)

    # Na temporada seguinte o aviso continua (a de 2026 segue incompleta).
    client.post("/campeao/continuar", follow_redirects=False)
    html = _dashboard()
    assert AVISO_INCOMPLETO in html
    assert _linhas_do_historico(html) == [("2026", campanha["rotulo"]), ("2027", "Em andamento")]
    assert persistencia.listar_saves() == [nome_save]
    assert jogo is estado.obter_jogo()


# --- cenário 5 -----------------------------------------------------------------


def test_voltar_ao_menu_e_continuar_mostra_o_mesmo_dashboard():
    jogo = _novo_jogo_web(4)
    nome_save = jogo.nome_save
    _jogar_temporada_pelo_dashboard(_disputar_no_canto_1)
    client.post("/campeao/continuar", follow_redirects=False)
    html_antes = _dashboard()

    # "Voltar ao menu" só navega: o jogo segue em memória, nada muda.
    menu_inicial = client.get("/")
    assert menu_inicial.status_code == 200
    assert estado.obter_jogo() is jogo
    assert _normalizar(_dashboard()) == _normalizar(html_antes)

    # "Continuar" em "Carreiras salvas" recarrega do disco.
    assert nome_save in client.get("/saves").text
    resposta = client.post(f"/saves/{nome_save}/carregar", follow_redirects=False)
    assert resposta.headers["location"] == "/carreira"
    assert estado.obter_jogo() is not jogo

    html_depois = _dashboard()
    assert _celulas(html_depois) == _celulas(html_antes)
    assert _linhas_do_historico(html_depois) == _linhas_do_historico(html_antes)
    assert _times_do_proximo_jogo(html_depois) == _times_do_proximo_jogo(html_antes)
    assert _normalizar(html_depois) == _normalizar(html_antes)
    assert persistencia.listar_saves() == [nome_save]
