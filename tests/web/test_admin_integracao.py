"""Teste ponta a ponta da área adm (ID-008-T9): o adm loga em `/admin`,
renomeia o São Paulo (id 1) e troca as faixas do escudo pela tela, e o nome
e as cores novos valem em todo lugar — telas web de jogo, histórico,
equipes e saves, carreira salva carregada, terminal — e "Restaurar equipes
padrão" não desfaz a edição.

Isolamento: o catálogo do adm já vai para `tmp_path` pelo
`tests/conftest.py`; aqui `equipes.json` e `saves/` também apontam para
`tmp_path` e o "jogo em andamento" em memória é zerado a cada teste.
"""

import json
import re

import pytest
from fastapi.testclient import TestClient

import catalogo
import menu
import persistencia
import web.estado as estado
from equipe import Equipe
from web.main import app

SENHA = "senha-do-adm-integracao"
CAMPEONATO = "Copa do Brasil"
NOME_SAVE = "1_01_01_2026"

ID_EDITADO = 1
NOME_ANTIGO = "São Paulo"
NOME_NOVO = "Nome Adm"
CORES_ENVIADAS = ["#12ab34", "#fedcba"]  # como o <input type="color"> envia
CORES_NOVAS = ["#12AB34", "#FEDCBA"]     # como o catálogo grava

# Histórico de 2 temporadas com o id 1: campeão em 2026, vice em 2027.
HISTORICO = [
    {
        "temporada": 2026,
        "campeao": 1,
        "fases": [
            {"nome_fase": "Semifinal - Copa do Brasil",
             "confrontos": [[1, 2, 1, 4, 2], [3, 4, 4, 3, 5]]},
            {"nome_fase": "Final - Copa do Brasil",
             "confrontos": [[1, 4, 1, 5, 4]]},
        ],
    },
    {
        "temporada": 2027,
        "campeao": 3,
        "fases": [
            {"nome_fase": "Semifinal - Copa do Brasil",
             "confrontos": [[1, 2, 1, 5, 3], [3, 4, 3, 4, 2]]},
            {"nome_fase": "Final - Copa do Brasil",
             "confrontos": [[1, 3, 3, 2, 4]]},
        ],
    },
]


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """`equipes.json` (elenco padrão, com o nome antigo) e `saves/` em
    pasta temporária, área adm ligada com senha de teste e nenhum jogo em
    andamento. Os arquivos reais do projeto nunca são tocados.
    """
    monkeypatch.setattr(
        persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json")
    )
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(estado, "_jogo_atual", None)
    monkeypatch.setenv("ADMIN_SENHA", SENHA)
    persistencia.restaurar_equipes_padrao()
    yield


@pytest.fixture
def cliente():
    """Cliente novo por teste: o cookie do adm não vaza entre testes."""
    with TestClient(app) as cliente_teste:
        yield cliente_teste


def _times_antigos(*ids):
    """Equipes com o nome/cores do retrato antigo (antes da edição)."""
    return [
        Equipe(time["nome"], cores=time["cores"], id=time["id"])
        for time in catalogo.TIMES_PADRAO
        if time["id"] in ids
    ]


def _criar_save_em_disco():
    """Carreira salva com o time 1 ainda gravado como "São Paulo"."""
    time_escolhido, *_ = classificados = _times_antigos(1, 2, 3, 4)
    persistencia.salvar_jogo(
        NOME_SAVE, CAMPEONATO, time_escolhido, 2028, classificados, HISTORICO
    )


def _iniciar_jogo_web(cliente):
    """Começa um jogo pela web com o id 1 (ainda com o nome antigo) e
    coloca o histórico no jogo em andamento."""
    resposta = cliente.post(
        "/novo-jogo/time",
        data={"campeonato": CAMPEONATO, "time": str(ID_EDITADO)},
        follow_redirects=False,
    )
    assert resposta.status_code == 303
    jogo = estado.obter_jogo()
    assert jogo.time_escolhido.nome == NOME_ANTIGO
    jogo.historico = list(HISTORICO)
    return jogo


def _editar_pelo_adm(cliente, padrao=None):
    """Login + formulário do adm: renomeia o id 1 e deixa 2 faixas. Sem
    `padrao`, o POST vai sem o rádio (formulário antigo → verticais)."""
    login = cliente.post(
        "/admin/login", data={"senha": SENHA}, follow_redirects=False
    )
    assert login.status_code == 303

    formulario = cliente.get(f"/admin/times/{ID_EDITADO}")
    assert formulario.status_code == 200
    assert NOME_ANTIGO in formulario.text

    dados = {
        "nome": NOME_NOVO,
        "faixas": "2",
        "cor_1": CORES_ENVIADAS[0],
        "cor_2": CORES_ENVIADAS[1],
        "cor_3": "#000000",  # ignoradas com 2 faixas
        "cor_4": "#000000",
        "acao": "salvar",
    }
    if padrao is not None:
        dados["padrao"] = padrao
    resposta = cliente.post(
        f"/admin/times/{ID_EDITADO}", data=dados, follow_redirects=False
    )
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin"
    assert catalogo.nome_do_time(ID_EDITADO) == NOME_NOVO
    assert catalogo.cores_do_time(ID_EDITADO) == CORES_NOVAS
    if padrao is not None:
        assert catalogo.padrao_do_time(ID_EDITADO) == padrao


def _assert_nome_e_cores_novos(html):
    assert NOME_NOVO in html
    assert NOME_ANTIGO not in html
    assert f'aria-label="Escudo do {NOME_NOVO}"' in html
    for cor in CORES_NOVAS:
        assert cor in html


@pytest.fixture
def editado(cliente):
    """Cenário completo: save em disco + jogo web em andamento (ambos
    criados ANTES da edição) e depois a edição feita pela tela do adm."""
    _criar_save_em_disco()
    jogo = _iniciar_jogo_web(cliente)
    _editar_pelo_adm(cliente)
    return jogo


# --- Área adm -----------------------------------------------------------------

def test_lista_do_adm_e_formulario_mostram_o_nome_novo(cliente, editado):
    lista = cliente.get("/admin")
    formulario = cliente.get(f"/admin/times/{ID_EDITADO}")

    assert lista.status_code == 200
    _assert_nome_e_cores_novos(lista.text)
    assert formulario.status_code == 200
    assert f'value="{NOME_NOVO}"' in formulario.text


def test_so_o_time_editado_vai_para_o_arquivo_do_catalogo(editado):
    with open(catalogo.ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
        gravado = json.load(arquivo)

    assert gravado == {"1": {"nome": NOME_NOVO, "cores": CORES_NOVAS, "padrao": "verticais"}}
    assert catalogo.nome_do_time(2) == "Palmeiras"


# --- Telas de jogo --------------------------------------------------------------

def test_escolher_time_mostra_o_nome_novo(cliente, editado):
    resposta = cliente.post("/novo-jogo", data={"campeonato": CAMPEONATO})

    assert resposta.status_code == 200
    _assert_nome_e_cores_novos(resposta.text)


def test_penaltis_e_fase_do_jogo_em_andamento_mostram_o_nome_novo(cliente, editado):
    penaltis = cliente.get("/fase")  # monta a fase e vai para os pênaltis

    assert penaltis.status_code == 200
    _assert_nome_e_cores_novos(penaltis.text)

    while True:
        cobranca = cliente.post(
            "/fase/penaltis", data={"canto": "1"}, follow_redirects=False
        )
        assert cobranca.status_code == 303
        if cobranca.headers["location"] == "/fase":
            break
    fase = cliente.get("/fase")

    assert fase.status_code == 200
    _assert_nome_e_cores_novos(fase.text)


def test_campeao_com_objeto_antigo_mostra_o_nome_novo(cliente, editado):
    """O objeto `Equipe` do jogo foi montado antes da edição (nome antigo);
    a tela resolve pelo id no catálogo."""
    editado.campeao = editado.time_escolhido
    assert editado.campeao.nome == NOME_ANTIGO

    resposta = cliente.get("/campeao")

    assert resposta.status_code == 200
    _assert_nome_e_cores_novos(resposta.text)


# --- Histórico ------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "/historico",
        "/historico/1/jogos",
        "/historico/1/classificacao",
        "/historico/2/jogos",
        "/historico/2/classificacao",
        "/campeoes",
    ],
)
def test_telas_de_historico_mostram_o_nome_novo(cliente, editado, url):
    resposta = cliente.get(url)

    assert resposta.status_code == 200
    _assert_nome_e_cores_novos(resposta.text)


# --- Equipes e saves ------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        f"/equipes/{CAMPEONATO}",
        f"/equipes/{CAMPEONATO}/{ID_EDITADO}/editar",
        "/saves",
    ],
)
def test_telas_de_equipes_e_saves_mostram_o_nome_novo(cliente, editado, url):
    resposta = cliente.get(url)

    assert resposta.status_code == 200
    _assert_nome_e_cores_novos(resposta.text)


def test_arquivos_do_jogador_continuam_com_o_retrato_antigo(editado):
    """A edição do adm só vale em memória: `equipes.json` e o save em disco
    não são regravados."""
    with open(persistencia.ARQUIVO_EQUIPES, encoding="utf-8") as arquivo:
        equipes = json.load(arquivo)
    with open(persistencia._caminho_save(NOME_SAVE), encoding="utf-8") as arquivo:
        save = json.load(arquivo)

    assert equipes[CAMPEONATO][0]["nome"] == NOME_ANTIGO
    assert save["time_escolhido"]["nome"] == NOME_ANTIGO


# --- Carreira salva carregada ---------------------------------------------------

def test_carregar_jogo_salvo_devolve_o_nome_novo(editado):
    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)

    assert dados["time_escolhido"].nome == NOME_NOVO
    assert dados["time_escolhido"].cores == CORES_NOVAS
    sp = next(time for time in dados["classificados"] if time.id == ID_EDITADO)
    assert sp.nome == NOME_NOVO
    assert sp.cores == CORES_NOVAS


def test_carregar_save_pela_web_mostra_o_nome_novo(cliente, editado):
    resposta = cliente.post(
        f"/saves/{NOME_SAVE}/carregar", follow_redirects=False
    )

    assert resposta.status_code == 303
    assert estado.obter_jogo().time_escolhido.nome == NOME_NOVO
    penaltis = cliente.get("/fase")  # monta a fase e vai para os pênaltis
    assert penaltis.status_code == 200
    _assert_nome_e_cores_novos(penaltis.text)
    campeoes = cliente.get("/campeoes")
    _assert_nome_e_cores_novos(campeoes.text)


# --- Restaurar equipes padrão ---------------------------------------------------

def test_restaurar_equipes_padrao_nao_desfaz_a_edicao_do_adm(cliente, editado):
    resposta = cliente.post("/equipes/restaurar", follow_redirects=False)

    assert resposta.status_code == 303
    assert catalogo.nome_do_time(ID_EDITADO) == NOME_NOVO
    assert catalogo.cores_do_time(ID_EDITADO) == CORES_NOVAS
    sp = persistencia.carregar_equipes()[CAMPEONATO][0]
    assert (sp.nome, sp.cores) == (NOME_NOVO, CORES_NOVAS)
    tela = cliente.get(f"/equipes/{CAMPEONATO}")
    _assert_nome_e_cores_novos(tela.text)
    admin = cliente.get("/admin")
    _assert_nome_e_cores_novos(admin.text)


# --- Terminal -------------------------------------------------------------------

def _responder_input(monkeypatch, *respostas):
    fila = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(fila))


def _assert_terminal_com_nome_novo(saida):
    assert NOME_NOVO in saida
    assert NOME_ANTIGO not in saida


def test_terminal_exibir_campeoes_mostra_o_nome_novo(editado, capsys):
    menu.exibir_campeoes(HISTORICO)

    saida = capsys.readouterr().out
    _assert_terminal_com_nome_novo(saida)
    assert f"2026: {NOME_NOVO}" in saida
    assert f"{NOME_NOVO}: 1 título(s)" in saida


def test_terminal_historico_e_classificacao_mostram_o_nome_novo(
    editado, capsys, monkeypatch
):
    _responder_input(monkeypatch, "1", "2")

    menu.exibir_historico_jogos(HISTORICO)
    menu.exibir_classificacao(HISTORICO)

    _assert_terminal_com_nome_novo(capsys.readouterr().out)


def test_terminal_escolher_time_e_escolher_save_mostram_o_nome_novo(
    editado, capsys, monkeypatch
):
    _responder_input(monkeypatch, "1", "1")

    escolhido = menu.escolher_time(persistencia.carregar_equipes()[CAMPEONATO])
    nome_save = menu.escolher_save("carregar")

    assert escolhido.nome == NOME_NOVO
    assert nome_save == NOME_SAVE
    _assert_terminal_com_nome_novo(capsys.readouterr().out)


# --- Padrão do escudo (E-012-T6) ------------------------------------------------
#
# Mesmo cenário do `editado`, mas o adm salva o id 1 com a diagonal ↗. O
# Vasco (id 6) também é diagonal ↗ no cadastro padrão, então os asserts
# olham só o(s) SVG(s) do time editado, achados pelo aria-label.

PADRAO_DIAGONAL = "diagonal_sobe"
ROTACAO_DIAGONAL_SOBE = 'transform="rotate(-45 30 30)"'


@pytest.fixture
def editado_diagonal(cliente):
    """Save em disco + jogo web em andamento (criados ANTES da edição) e
    depois o adm salva o id 1 com `padrao=diagonal_sobe` e 2 cores."""
    _criar_save_em_disco()
    jogo = _iniciar_jogo_web(cliente)
    _editar_pelo_adm(cliente, padrao=PADRAO_DIAGONAL)
    return jogo


def _escudos_do_time_editado(html):
    """Todos os SVGs de escudo do time editado presentes no HTML."""
    rotulo = re.escape(f'aria-label="Escudo do {NOME_NOVO}"')
    return re.findall(rf"<svg[^>]*{rotulo}.*?</svg>", html, flags=re.DOTALL)


def _assert_escudo_diagonal(html):
    escudos = _escudos_do_time_editado(html)
    assert escudos, "escudo do time editado não encontrado na tela"
    for svg in escudos:
        assert 'class="escudo-diagonal"' in svg
        assert ROTACAO_DIAGONAL_SOBE in svg
        # cor 1 = fundo, cor 2 = faixa
        assert f'fill="{CORES_NOVAS[0]}"' in svg
        assert f'fill="{CORES_NOVAS[1]}"' in svg


def test_diagonal_vai_para_o_arquivo_do_catalogo(editado_diagonal):
    with open(catalogo.ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
        gravado = json.load(arquivo)

    assert gravado == {
        "1": {"nome": NOME_NOVO, "cores": CORES_NOVAS, "padrao": PADRAO_DIAGONAL}
    }


def test_formulario_do_adm_volta_com_a_diagonal_marcada(cliente, editado_diagonal):
    formulario = cliente.get(f"/admin/times/{ID_EDITADO}")

    assert formulario.status_code == 200
    radio = re.search(
        rf'<input[^>]*value="{PADRAO_DIAGONAL}"[^>]*>', formulario.text
    )
    assert radio is not None
    assert "checked" in radio.group(0)
    _assert_escudo_diagonal(cliente.get("/admin").text)


def test_fase_e_penaltis_mostram_o_escudo_diagonal(cliente, editado_diagonal):
    penaltis = cliente.get("/fase")  # monta a fase e vai para os pênaltis

    assert penaltis.status_code == 200
    _assert_escudo_diagonal(penaltis.text)

    while True:
        cobranca = cliente.post(
            "/fase/penaltis", data={"canto": "1"}, follow_redirects=False
        )
        assert cobranca.status_code == 303
        if cobranca.headers["location"] == "/fase":
            break
    fase = cliente.get("/fase")

    assert fase.status_code == 200
    _assert_escudo_diagonal(fase.text)


@pytest.mark.parametrize(
    "url",
    [
        "/historico/1/jogos",
        "/historico/1/classificacao",
        "/campeoes",
        "/saves",
        f"/equipes/{CAMPEONATO}",
        f"/equipes/{CAMPEONATO}/{ID_EDITADO}/editar",
    ],
)
def test_telas_mostram_o_escudo_diagonal(cliente, editado_diagonal, url):
    resposta = cliente.get(url)

    assert resposta.status_code == 200
    _assert_escudo_diagonal(resposta.text)


def test_carregar_save_pela_web_mostra_o_escudo_diagonal(cliente, editado_diagonal):
    resposta = cliente.post(
        f"/saves/{NOME_SAVE}/carregar", follow_redirects=False
    )

    assert resposta.status_code == 303
    penaltis = cliente.get("/fase")
    assert penaltis.status_code == 200
    _assert_escudo_diagonal(penaltis.text)


def test_restaurar_equipes_padrao_nao_desfaz_a_diagonal(cliente, editado_diagonal):
    resposta = cliente.post("/equipes/restaurar", follow_redirects=False)

    assert resposta.status_code == 303
    assert catalogo.padrao_do_time(ID_EDITADO) == PADRAO_DIAGONAL
    _assert_escudo_diagonal(cliente.get(f"/equipes/{CAMPEONATO}").text)
    _assert_escudo_diagonal(cliente.get("/historico/1/jogos").text)


def _tem_chave(dados, chave):
    """True se `chave` aparece em algum dict dentro de `dados` (recursivo)."""
    if isinstance(dados, dict):
        return chave in dados or any(_tem_chave(v, chave) for v in dados.values())
    if isinstance(dados, list):
        return any(_tem_chave(item, chave) for item in dados)
    return False


@pytest.mark.parametrize("restaurar", [False, True])
def test_save_e_equipes_json_nao_ganham_campo_padrao(
    cliente, editado_diagonal, restaurar
):
    """Decisão 1: o padrão é resolvido só pelo catálogo, via id — nem o
    `equipes.json` (mesmo regravado pelo restaurar) nem o save guardam."""
    if restaurar:
        cliente.post("/equipes/restaurar", follow_redirects=False)
    with open(persistencia.ARQUIVO_EQUIPES, encoding="utf-8") as arquivo:
        equipes = json.load(arquivo)
    with open(persistencia._caminho_save(NOME_SAVE), encoding="utf-8") as arquivo:
        save = json.load(arquivo)

    assert not _tem_chave(equipes, "padrao")
    assert not _tem_chave(save, "padrao")
