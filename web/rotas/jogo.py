"""Rotas do fluxo de novo jogo: escolher campeonato, escolher time e iniciar
o "jogo em andamento" guardado em `web/estado.py`.

A tela da fase da temporada (`GET /fase`) ainda não existe de verdade —
chega em ID-001-T5. Por enquanto é só um placeholder, destino do
redirecionamento de `POST /novo-jogo/time`.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from campeonato import sortear_classificados
from persistencia import carregar_equipes
from web.estado import iniciar_jogo
from web.templates_config import templates

router = APIRouter(tags=["jogo"])


@router.get("/novo-jogo")
def tela_novo_jogo(request: Request):
    """Primeira tela do fluxo de novo jogo: escolher o campeonato."""
    equipes = carregar_equipes()
    return templates.TemplateResponse(request, "novo_jogo.html", {"campeonatos": list(equipes.keys())})


@router.post("/novo-jogo")
def escolher_campeonato(request: Request, campeonato: Annotated[str, Form()]):
    """Recebe o campeonato escolhido e mostra os times disponíveis nele."""
    equipes = carregar_equipes()
    times = equipes.get(campeonato)
    if times is None:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")

    return templates.TemplateResponse(request, "escolher_time.html", {"campeonato": campeonato, "times": times})


@router.post("/novo-jogo/time")
def escolher_time(campeonato: Annotated[str, Form()], time: Annotated[str, Form()]):
    """Recebe o time escolhido, inicializa o jogo em memória (temporada 2026,
    classificados embaralhados) e segue pra fase atual.
    """
    equipes = carregar_equipes()
    times = equipes.get(campeonato)
    if times is None:
        raise HTTPException(status_code=404, detail="Campeonato não encontrado.")

    time_escolhido = next((equipe for equipe in times if equipe == time), None)
    if time_escolhido is None:
        raise HTTPException(status_code=404, detail="Time não encontrado nesse campeonato.")

    classificados = sortear_classificados(times)
    iniciar_jogo(campeonato, time_escolhido, 2026, classificados)

    return RedirectResponse(url="/fase", status_code=303)


@router.get("/fase")
def fase_placeholder():
    """Placeholder até a tela real da fase da temporada existir (ID-001-T5)."""
    raise HTTPException(status_code=404, detail="Tela da fase da temporada ainda não implementada.")
