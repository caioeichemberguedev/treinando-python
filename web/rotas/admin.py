"""Rotas da área adm (`/admin`): login, logout, lista dos times e edição
do nome/cores de cada time.

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
- Edição do time (decisões 4 e 8): o formulário sempre manda os 4
  seletores de cor; só as `faixas` primeiras valem, o resto é ignorado.
  "Pré-visualizar" só redesenha o escudo (sem JavaScript); "Salvar" grava
  no catálogo do adm (`catalogo.salvar_time_no_catalogo`).
- Padrão do escudo (E-012, decisão 7): grupo de rádios `padrao` com os
  valores de `catalogo.PADROES`; campo ausente no POST → verticais. A
  prévia sempre desenha o padrão do formulário.
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

# Valor inicial dos seletores de cor excedentes (ou enviados vazios).
COR_SELETOR_PADRAO = "#FFFFFF"

# Rótulos dos rádios do padrão do escudo, na ordem de `catalogo.PADROES`.
ROTULOS_PADRAO = {
    catalogo.PADRAO_VERTICAIS: "Faixas verticais",
    catalogo.PADRAO_HORIZONTAIS: "Faixas horizontais",
    catalogo.PADRAO_DIAGONAL_SOBE: "Diagonal ↗",
    catalogo.PADRAO_DIAGONAL_DESCE: "Diagonal ↘",
}


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


def _id_time_existente(id_time: int) -> int:
    """404 se o id não existir no catálogo efetivo."""
    if catalogo.nome_do_time(id_time) is None:
        raise HTTPException(status_code=404, detail="Time não encontrado.")
    return id_time


def _completar_cores(cores: list[str]) -> list[str]:
    """Estende `cores` até `MAXIMO_CORES` (os seletores excedentes do
    formulário precisam de um valor inicial)."""
    faltam = catalogo.MAXIMO_CORES - len(cores)
    return list(cores[:catalogo.MAXIMO_CORES]) + [COR_SELETOR_PADRAO] * faltam


def _contexto_time(id_time, nome, faixas, cores, cores_previa, padrao, erros):
    """Contexto do `admin_time.html`.

    `cores` são os 4 valores dos seletores (em minúsculas, o formato que o
    `<input type="color">` usa); `cores_previa` vai para `escudo(...,
    cores=...)` — None desenha as cores atuais do catálogo. `padrao` marca
    o rádio e vai sempre para a prévia (`escudo(..., padrao=...)`); valor
    fora de `catalogo.PADROES` vira verticais.
    """
    if padrao not in catalogo.PADROES:
        padrao = catalogo.PADRAO_VERTICAIS
    return {
        "id_time": id_time,
        "nome": nome,
        "faixas": faixas,
        "opcoes_faixas": range(catalogo.MINIMO_CORES, catalogo.MAXIMO_CORES + 1),
        "cores": [cor.lower() for cor in _completar_cores(cores)],
        "cores_previa": cores_previa,
        "padrao": padrao,
        "opcoes_padrao": [
            (valor, ROTULOS_PADRAO[valor]) for valor in catalogo.PADROES
        ],
        "erros": erros,
    }


def _ler_faixas(faixas: str) -> int | None:
    """Converte o campo `faixas` em int de 1 a 4; inválido → None."""
    try:
        valor = int(faixas.strip())
    except ValueError:
        return None
    if not catalogo.MINIMO_CORES <= valor <= catalogo.MAXIMO_CORES:
        return None
    return valor


@router.get("/times/{id_time}", dependencies=[Depends(_exigir_admin)])
def tela_editar_time_admin(request: Request, id_time: int):
    """Formulário de edição já preenchido com o catálogo efetivo (nome,
    cores e padrão do escudo)."""
    _id_time_existente(id_time)
    cores = catalogo.cores_do_time(id_time)
    contexto = _contexto_time(
        id_time, catalogo.nome_do_time(id_time), len(cores), cores, None,
        catalogo.padrao_do_time(id_time), [],
    )
    return templates.TemplateResponse(request, "admin_time.html", contexto)


@router.post("/times/{id_time}", dependencies=[Depends(_exigir_admin)])
def salvar_time_admin(
    request: Request,
    id_time: int,
    nome: Annotated[str, Form()] = "",
    faixas: Annotated[str, Form()] = "",
    cor_1: Annotated[str, Form()] = "",
    cor_2: Annotated[str, Form()] = "",
    cor_3: Annotated[str, Form()] = "",
    cor_4: Annotated[str, Form()] = "",
    padrao: Annotated[str, Form()] = catalogo.PADRAO_VERTICAIS,
    acao: Annotated[str, Form()] = "previa",
):
    """Valida o formulário. `acao=salvar` válido → grava e volta para
    `/admin` (303); qualquer outra ação só mostra a prévia (200), sem
    gravar. Inválido → 400 com as mensagens e o catálogo intacto.

    Os campos têm default vazio para que um campo faltando caia numa
    mensagem em português em vez de um 422 genérico. Exceção: `padrao`
    ausente vale verticais (formulários antigos sem o rádio); valor fora de
    `catalogo.PADROES` ou diagonal com 1 cor → 400.
    """
    _id_time_existente(id_time)
    padrao = padrao.strip()
    enviadas = [cor.strip() for cor in (cor_1, cor_2, cor_3, cor_4)]

    erros = []
    quantidade = _ler_faixas(faixas)
    if quantidade is None:
        erros.append(
            f"A quantidade de faixas deve ser um número de "
            f"{catalogo.MINIMO_CORES} a {catalogo.MAXIMO_CORES}."
        )
        cores = []
    else:
        cores = enviadas[:quantidade]
        for posicao, cor in enumerate(cores, start=1):
            if not cor:
                erros.append(f"Escolha a cor da faixa {posicao}.")

    if not erros:
        erros = catalogo.validar_time(id_time, nome, cores, padrao)

    # Os seletores voltam com o que foi enviado (ou a cor padrão, se vazio).
    cores_formulario = [cor or COR_SELETOR_PADRAO for cor in enviadas]
    if erros:
        contexto = _contexto_time(
            id_time, nome, quantidade, cores_formulario, None, padrao, erros
        )
        return templates.TemplateResponse(
            request, "admin_time.html", contexto, status_code=400
        )

    cores = [cor.upper() for cor in cores]
    if acao == "salvar":
        try:
            catalogo.salvar_time_no_catalogo(id_time, nome, cores, padrao)
        except ValueError as erro:
            contexto = _contexto_time(
                id_time, nome, quantidade, cores_formulario, None, padrao,
                [str(erro)],
            )
            return templates.TemplateResponse(
                request, "admin_time.html", contexto, status_code=400
            )
        return RedirectResponse(url=URL_ADMIN, status_code=303)

    contexto = _contexto_time(
        id_time, nome.strip(), quantidade, cores_formulario, cores, padrao, []
    )
    return templates.TemplateResponse(request, "admin_time.html", contexto)
