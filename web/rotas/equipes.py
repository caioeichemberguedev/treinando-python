"""Rotas de edição do elenco base: listar campeonatos, adicionar, remover e
renomear equipes.

Espelha `menu.editar_equipes` (sem a edição de finanças/fãs/força nem o
"restaurar padrão" — isso fica para uma tarefa futura, ID-002-T4b). Remover
uma equipe é uma ação destrutiva, então passa por uma tela de confirmação
antes do POST que efetivamente remove, do mesmo jeito que o terminal pede
confirmação por texto ("s/n").
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from equipe import Equipe
from persistencia import carregar_equipes, salvar_equipes
from web.templates_config import templates

router = APIRouter(tags=["equipes"])


def _times_do_campeonato(equipes, campeonato):
    times = equipes.get(campeonato)
    if times is None:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")
    return times


def _equipe_do_campeonato(times, nome_equipe):
    equipe = next((time for time in times if time == nome_equipe), None)
    if equipe is None:
        raise HTTPException(status_code=404, detail="Equipe não encontrada nesse campeonato.")
    return equipe


@router.get("/equipes")
def tela_equipes(request: Request):
    """Lista os campeonatos disponíveis para editar o elenco."""
    equipes = carregar_equipes()
    return templates.TemplateResponse(request, "equipes.html", {"campeonatos": list(equipes.keys())})


@router.get("/equipes/{campeonato}")
def tela_equipes_campeonato(request: Request, campeonato: str):
    """Lista as equipes de um campeonato, com formulários de adicionar,
    remover e renomear.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    return templates.TemplateResponse(
        request, "equipes_campeonato.html", {"campeonato": campeonato, "times": times, "erro": None}
    )


@router.post("/equipes/{campeonato}/adicionar")
def adicionar_equipe(request: Request, campeonato: str, nome: Annotated[str, Form()]):
    """Adiciona uma equipe nova ao campeonato, validando nome vazio/duplicado
    igual ao terminal.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)

    nome = nome.strip()
    erro = None
    if not nome:
        erro = "Nome vazio não é permitido."
    elif nome in times:
        erro = "Essa equipe já existe."

    if erro:
        return templates.TemplateResponse(
            request,
            "equipes_campeonato.html",
            {"campeonato": campeonato, "times": times, "erro": erro},
            status_code=400,
        )

    times.append(Equipe(nome))
    salvar_equipes(equipes)
    return RedirectResponse(
        url=request.url_for("tela_equipes_campeonato", campeonato=campeonato), status_code=303
    )


@router.get("/equipes/{campeonato}/{nome_equipe}/remover")
def confirmar_remocao_equipe(request: Request, campeonato: str, nome_equipe: str):
    """Tela de confirmação exibida antes de remover uma equipe de verdade —
    ação destrutiva, espelhando a confirmação "s/n" que o terminal pede.
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    _equipe_do_campeonato(times, nome_equipe)
    return templates.TemplateResponse(
        request, "equipes_confirmar_remocao.html", {"campeonato": campeonato, "nome_equipe": nome_equipe}
    )


@router.post("/equipes/{campeonato}/{nome_equipe}/remover")
def remover_equipe(request: Request, campeonato: str, nome_equipe: str):
    """Remove a equipe definitivamente — chamado só a partir da tela de
    confirmação (`confirmar_remocao_equipe`).
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    equipe = _equipe_do_campeonato(times, nome_equipe)

    times.remove(equipe)
    salvar_equipes(equipes)
    return RedirectResponse(
        url=request.url_for("tela_equipes_campeonato", campeonato=campeonato), status_code=303
    )


@router.post("/equipes/{campeonato}/{nome_equipe}/renomear")
def renomear_equipe(request: Request, campeonato: str, nome_equipe: str, nome_novo: Annotated[str, Form()]):
    """Renomeia uma equipe existente, validando nome vazio igual ao
    terminal (sem checar duplicidade, igual `menu.editar_equipes` hoje).
    """
    equipes = carregar_equipes()
    times = _times_do_campeonato(equipes, campeonato)
    equipe = _equipe_do_campeonato(times, nome_equipe)

    nome_novo = nome_novo.strip()
    if not nome_novo:
        return templates.TemplateResponse(
            request,
            "equipes_campeonato.html",
            {"campeonato": campeonato, "times": times, "erro": "Nome vazio não é permitido."},
            status_code=400,
        )

    equipe.nome = nome_novo
    salvar_equipes(equipes)
    return RedirectResponse(
        url=request.url_for("tela_equipes_campeonato", campeonato=campeonato), status_code=303
    )
