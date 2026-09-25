"""Ponto de entrada da interface web do jogo (FastAPI + Jinja2).

Rodar com: uvicorn web.main:app --reload
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).parent

app = FastAPI(title="Jogo de Futebol")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

templates = Jinja2Templates(directory=BASE / "templates")


@app.get("/")
def inicio(request: Request):
    """Tela inicial do jogo."""
    return templates.TemplateResponse(request, "inicio.html")
