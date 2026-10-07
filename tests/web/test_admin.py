"""Testes das rotas de acesso da área adm (`/admin`): login, logout, lista
dos times e área desligada sem `ADMIN_SENHA` (ID-008-T5).
"""

import pytest
from fastapi.testclient import TestClient

import catalogo
from web import sessao_admin
from web.main import app
from web.rotas import admin, equipes, historico, jogo, saves

SENHA = "s3nha-Secreta-do-adm"


@pytest.fixture
def cliente():
    """Cliente novo por teste: cookies de um teste não vazam para outro."""
    with TestClient(app) as cliente_teste:
        yield cliente_teste


@pytest.fixture
def sem_senha(monkeypatch):
    monkeypatch.delenv("ADMIN_SENHA", raising=False)


@pytest.fixture
def com_senha(monkeypatch):
    monkeypatch.setenv("ADMIN_SENHA", SENHA)


def _logar(cliente):
    return cliente.post(
        "/admin/login", data={"senha": SENHA}, follow_redirects=False
    )


def _sem_senha_na_resposta(resposta):
    assert SENHA not in resposta.text
    for valor in resposta.headers.values():
        assert SENHA not in valor


# --- Área desligada ---------------------------------------------------------

@pytest.mark.parametrize(
    "metodo, url",
    [
        ("GET", "/admin"),
        ("GET", "/admin/login"),
        ("POST", "/admin/login"),
        ("POST", "/admin/sair"),
    ],
)
def test_sem_admin_senha_todas_as_rotas_dao_404(sem_senha, cliente, metodo, url):
    resposta = cliente.request(
        metodo, url, data={"senha": "qualquer"} if metodo == "POST" else None,
        follow_redirects=False,
    )

    assert resposta.status_code == 404


def test_admin_senha_vazia_desliga_a_area(monkeypatch, cliente):
    monkeypatch.setenv("ADMIN_SENHA", "")

    assert cliente.get("/admin/login").status_code == 404


def test_sem_admin_senha_cookie_valido_antigo_nao_libera(monkeypatch, cliente):
    monkeypatch.setenv("ADMIN_SENHA", SENHA)
    assert _logar(cliente).status_code == 303
    monkeypatch.delenv("ADMIN_SENHA")

    assert cliente.get("/admin", follow_redirects=False).status_code == 404


# --- Login --------------------------------------------------------------------

def test_admin_sem_cookie_redireciona_para_login(com_senha, cliente):
    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/login"


def test_tela_de_login_abre_com_campo_de_senha_sem_value(com_senha, cliente):
    resposta = cliente.get("/admin/login")

    assert resposta.status_code == 200
    assert 'type="password"' in resposta.text
    assert 'name="senha"' in resposta.text
    assert "value=" not in resposta.text
    _sem_senha_na_resposta(resposta)


def test_login_errado_da_401_sem_cookie_e_sem_ecoar_a_senha(com_senha, cliente):
    tentativa = "tentativa-errada-xyz"

    resposta = cliente.post(
        "/admin/login", data={"senha": tentativa}, follow_redirects=False
    )

    assert resposta.status_code == 401
    assert "Senha incorreta." in resposta.text
    assert "set-cookie" not in resposta.headers
    assert tentativa not in resposta.text
    _sem_senha_na_resposta(resposta)


def test_login_sem_campo_senha_da_401(com_senha, cliente):
    resposta = cliente.post("/admin/login", follow_redirects=False)

    assert resposta.status_code == 401
    assert "set-cookie" not in resposta.headers


def test_login_certo_cria_cookie_seguro_e_redireciona(com_senha, cliente):
    resposta = _logar(cliente)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin"
    cookie = resposta.headers["set-cookie"]
    assert cookie.startswith(f"{sessao_admin.COOKIE_SESSAO}=")
    assert "HttpOnly" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "Path=/admin" in cookie
    _sem_senha_na_resposta(resposta)


def test_depois_do_login_admin_lista_os_32_times(com_senha, cliente):
    _logar(cliente)

    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 200
    for time in catalogo.TIMES_PADRAO:
        assert f'href="/admin/times/{time["id"]}"' in resposta.text
    assert resposta.text.count('href="/admin/times/') == 32
    assert "Copa do Brasil" in resposta.text
    assert "Copa do Mundo 2026" in resposta.text
    assert "<svg" in resposta.text
    _sem_senha_na_resposta(resposta)


def test_lista_do_admin_usa_o_nome_efetivo_do_catalogo(com_senha, cliente):
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])
    _logar(cliente)

    resposta = cliente.get("/admin")

    assert resposta.status_code == 200
    assert "SPFC" in resposta.text
    assert "São Paulo" not in resposta.text


def test_cookie_adulterado_redireciona_para_login(com_senha, cliente):
    _logar(cliente)
    token = cliente.cookies.get(sessao_admin.COOKIE_SESSAO)
    ultimo = "0" if token[-1] != "0" else "1"
    cliente.cookies.clear()
    cliente.cookies.set(
        sessao_admin.COOKIE_SESSAO, token[:-1] + ultimo, path="/admin"
    )

    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/login"


# --- Logout -------------------------------------------------------------------

def test_sair_remove_o_cookie_e_admin_volta_a_redirecionar(com_senha, cliente):
    _logar(cliente)
    assert cliente.get("/admin", follow_redirects=False).status_code == 200

    resposta = cliente.post("/admin/sair", follow_redirects=False)

    assert resposta.status_code == 303
    cookie = resposta.headers["set-cookie"]
    assert cookie.startswith(f"{sessao_admin.COOKIE_SESSAO}=")
    assert "Path=/admin" in cookie
    assert "Max-Age=0" in cookie
    assert cliente.cookies.get(sessao_admin.COOKIE_SESSAO) is None
    segunda = cliente.get("/admin", follow_redirects=False)
    assert segunda.status_code == 303
    assert segunda.headers["location"] == "/admin/login"


# --- Navegação / app ----------------------------------------------------------

def test_menu_do_jogador_nao_tem_link_para_admin(com_senha, cliente):
    resposta = cliente.get("/")

    assert resposta.status_code == 200
    assert "/admin" not in resposta.text


def test_nomes_de_rota_continuam_unicos_com_o_router_admin():
    """Mesma checagem de `test_historico.test_nomes_de_rota_sao_unicos_na_app`,
    incluindo o router da área adm."""
    routers = [
        admin.router, equipes.router, historico.router, jogo.router,
        saves.router,
    ]
    nomes = [rota.name for router in routers for rota in router.routes]
    nomes.append("inicio")

    assert "tela_admin" in nomes
    assert len(nomes) == len(set(nomes))


# --- Casos de borda (game-tester) -------------------------------------------

@pytest.mark.parametrize("valor", ["", "   ", "\t\n"])
def test_admin_senha_vazia_ou_so_espacos_desliga_todas_as_rotas(
    monkeypatch, cliente, valor
):
    monkeypatch.setenv("ADMIN_SENHA", valor)

    assert cliente.get("/admin", follow_redirects=False).status_code == 404
    assert cliente.get("/admin/login").status_code == 404
    assert cliente.post(
        "/admin/login", data={"senha": valor}, follow_redirects=False
    ).status_code == 404
    sair = cliente.post("/admin/sair", follow_redirects=False)
    assert sair.status_code == 404


def test_senha_so_espacos_com_cookie_antigo_nao_libera(monkeypatch, cliente):
    monkeypatch.setenv("ADMIN_SENHA", SENHA)
    _logar(cliente)
    monkeypatch.setenv("ADMIN_SENHA", "   ")

    assert cliente.get("/admin", follow_redirects=False).status_code == 404


def test_login_certo_cookie_dura_8_horas(com_senha, cliente):
    cookie = _logar(cliente).headers["set-cookie"]

    assert "Max-Age=28800" in cookie


def test_cookie_expirado_redireciona_para_login(com_senha, cliente):
    vencido = sessao_admin.criar_token_sessao(
        agora=1_000_000 - sessao_admin.DURACAO_SESSAO
    )
    cliente.cookies.set(sessao_admin.COOKIE_SESSAO, vencido, path="/admin")

    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/login"


@pytest.mark.parametrize(
    "token",
    ["", "lixo", "1.2.3", "9" * 50 + ".abc", "abc.def", "%C3%A7.%C3%A7",
     "1.%FF"],
)
def test_cookie_malformado_redireciona_sem_500(com_senha, cliente, token):
    cliente.cookies.set(sessao_admin.COOKIE_SESSAO, token, path="/admin")

    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/login"


def test_trocar_admin_senha_invalida_cookie_antigo(monkeypatch, cliente):
    monkeypatch.setenv("ADMIN_SENHA", SENHA)
    _logar(cliente)
    monkeypatch.setenv("ADMIN_SENHA", "outra-senha-nova")

    resposta = cliente.get("/admin", follow_redirects=False)

    assert resposta.status_code == 303


@pytest.mark.parametrize(
    "dados",
    [None, {"senha": ""}, {"outro": "x"}, {"senha": "   "}],
)
def test_login_com_campo_ausente_ou_vazio_nao_da_500(
    com_senha, cliente, dados
):
    resposta = cliente.post("/admin/login", data=dados, follow_redirects=False)

    assert resposta.status_code == 401
    assert "set-cookie" not in resposta.headers


def test_login_com_corpo_json_nao_da_500(com_senha, cliente):
    resposta = cliente.post(
        "/admin/login", json={"senha": SENHA}, follow_redirects=False
    )

    assert resposta.status_code < 500
    assert "set-cookie" not in resposta.headers


def test_senha_quase_certa_e_recusada(com_senha, cliente):
    for tentativa in (SENHA + " ", SENHA[:-1], SENHA.upper()):
        resposta = cliente.post(
            "/admin/login", data={"senha": tentativa}, follow_redirects=False
        )
        assert resposta.status_code == 401


def test_senha_nao_aparece_em_logs(com_senha, cliente, caplog, capsys):
    caplog.set_level("DEBUG")
    _logar(cliente)
    cliente.get("/admin")
    cliente.post("/admin/login", data={"senha": "errada-123"})
    cliente.post("/admin/sair")

    capturado = capsys.readouterr()
    assert SENHA not in caplog.text
    assert SENHA not in capturado.out + capturado.err
    assert "errada-123" not in caplog.text


def test_sair_sem_estar_logado_so_redireciona(com_senha, cliente):
    resposta = cliente.post("/admin/sair", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/login"


def test_cookie_do_admin_nao_vai_para_rotas_do_jogo(com_senha, cliente):
    """`Path=/admin`: o cliente não envia o cookie para `/` (e o jogo segue
    respondendo normalmente depois do login)."""
    _logar(cliente)

    resposta = cliente.get("/")

    assert resposta.status_code == 200
    assert sessao_admin.COOKIE_SESSAO not in resposta.request.headers.get(
        "cookie", ""
    )
