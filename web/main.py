"""Ponto de entrada da interface web do jogo (FastAPI + Jinja2).

Rodar com: uvicorn web.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from web.rotas import jogo
from web.templates_config import templates

BASE = Path(__file__).parent

app = FastAPI(title="Jogo de Futebol")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.include_router(jogo.router)


@app.get("/")
def inicio(request: Request):
    """Tela inicial do jogo."""
    return templates.TemplateResponse(request, "inicio.html")
