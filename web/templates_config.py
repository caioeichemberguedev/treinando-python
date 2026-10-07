"""Instância única de `Jinja2Templates`, compartilhada por `web/main.py` e
pelas rotas em `web/rotas/`.

Fica num módulo à parte (em vez de dentro de `web/main.py`) pra evitar
import circular: as rotas precisam de `templates` para renderizar suas
páginas, e `web/main.py` precisa importar as rotas para registrar os
routers.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from web.escudo import escudo_svg

BASE = Path(__file__).parent

templates = Jinja2Templates(directory=BASE / "templates")

# `{{ escudo(time) }}` / `{{ escudo(time, 96) }}` nos templates.
templates.env.globals["escudo"] = escudo_svg
