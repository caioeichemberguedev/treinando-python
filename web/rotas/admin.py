"""Rotas da área adm (`/admin`): login, logout e lista dos times.

Decisões 6 e 7 do ID-008 (ver `docs/backlog.md`):

- Sem `ADMIN_SENHA` definida, a área fica desligada: TODAS as rotas
  `/admin...` respondem 404, como se não existissem.
- A sessão é um cookie assinado (`web/sessao_admin.py`), com `HttpOnly`
  (JavaScript não lê), `SameSite=Strict` (o navegador não envia o cookie
  em POSTs vindos de outro site — proteção contra CSRF) e `Path=/admin`
  (o cookie só viaja nas rotas da área adm). `Secure` só em `https`.
- A senha digitada nunca volta para o template, para o log ou para o
  cookie.
- Não há link para `/admin` no menu do jogador: o adm digita a URL.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import catalogo
from web import sessao_admin
from web.templates_config import templates

router = APIRouter(prefix="/admin", tags=["admin"])

URL_LOGIN = "/admin/login"
URL_ADMIN = "/admin"
CAMINHO_COOKIE = "/admin"


def _exigir_area_ativa():
    """404 quando a área adm está desligada (sem `ADMIN_SENHA`)."""
    if not sessao_admin.area_admin_ativa():
        raise HTTPException(status_code=404)


def _exigir_admin(request: Request):
    """Libera só o adm logado: área desligada → 404; sem token válido →
    303 para a tela de login.
    """
    _exigir_area_ativa()
    token = request.cookies.get(sessao_admin.COOKIE_SESSAO)
    if not sessao_admin.token_sessao_valido(token):
        raise HTTPException(status_code=303, headers={"Location": URL_LOGIN})


def _times_por_campeonato() -> dict[str, list[int]]:
    """Ids do catálogo efetivo agrupados por campeonato, na ordem do id."""
    agrupados = {}
    for id_time, time in sorted(catalogo.carregar_catalogo().items()):
        agrupados.setdefault(time["campeonato"], []).append(id_time)
    return agrupados


@router.get("", dependencies=[Depends(_exigir_admin)])
def tela_admin(request: Request):
    """Lista os times de cada campeonato com escudo e nome efetivos."""
    return templates.TemplateResponse(
        request, "admin.html", {"campeonatos": _times_por_campeonato()}
    )


@router.get("/login", dependencies=[Depends(_exigir_area_ativa)])
def tela_login_admin(request: Request):
    """Formulário de senha da área adm."""
    return templates.TemplateResponse(request, "admin_login.html", {"erro": None})


@router.post("/login", dependencies=[Depends(_exigir_area_ativa)])
def entrar_admin(request: Request, senha: Annotated[str, Form()] = ""):
    """Confere a senha: certa → cria o cookie de sessão e vai para `/admin`;
    errada → 401 com a tela de login (sem repetir o que foi digitado).
    """
    if not sessao_admin.senha_confere(senha):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"erro": "Senha incorreta."},
            status_code=401,
        )

    resposta = RedirectResponse(url=URL_ADMIN, status_code=303)
    resposta.set_cookie(
        sessao_admin.COOKIE_SESSAO,
        sessao_admin.criar_token_sessao(),
        max_age=sessao_admin.DURACAO_SESSAO,
        path=CAMINHO_COOKIE,
        secure=request.url.scheme == "https",
        httponly=True,
        samesite="strict",
    )
    return resposta


@router.post("/sair", dependencies=[Depends(_exigir_area_ativa)])
def sair_admin(request: Request):
    """Apaga o cookie de sessão e volta para a tela de login."""
    resposta = RedirectResponse(url=URL_LOGIN, status_code=303)
    resposta.delete_cookie(
        sessao_admin.COOKIE_SESSAO,
        path=CAMINHO_COOKIE,
        secure=request.url.scheme == "https",
        httponly=True,
        samesite="strict",
    )
    return resposta
