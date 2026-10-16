"""Instância única de `Jinja2Templates`, compartilhada por `web/main.py` e
pelas rotas em `web/rotas/`.

Fica num módulo à parte (em vez de dentro de `web/main.py`) pra evitar
import circular: as rotas precisam de `templates` para renderizar suas
páginas, e `web/main.py` precisa importar as rotas para registrar os
routers.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

import catalogo
import persistencia

from web.escudo import escudo_svg
from web.estado import obter_jogo

BASE = Path(__file__).parent

templates = Jinja2Templates(directory=BASE / "templates")

# `{{ escudo(time) }}` / `{{ escudo(time, 96) }}` nos templates.
templates.env.globals["escudo"] = escudo_svg

# `{{ nome_time(time) }}` nos templates: resolve o nome de exibição a partir
# do id (histórico), de uma `Equipe` ou de uma string.
templates.env.globals["nome_time"] = catalogo.nome_para_exibir


def save_pendente() -> bool:
    """True se há jogo em andamento com um retrato que não foi gravado
    porque o save estava travado (E-015). Lido a cada render, então o aviso
    some assim que uma gravação der certo."""
    jogo = obter_jogo()
    return jogo is not None and jogo.save_pendente is not None


def jogo_em_andamento():
    """O `EstadoJogo` em andamento, ou `None` sem jogo (M-021). Lido a cada
    render, sem guardar nada: decide se o link "Histórico" aparece no menu
    do topo e se a home mostra o bloco "Continuar carreira"."""
    return obter_jogo()


templates.env.globals["jogo_em_andamento"] = jogo_em_andamento

# Aviso de save travado no topo de todas as páginas (`base.html`, E-015).
templates.env.globals["save_pendente"] = save_pendente
templates.env.globals["mensagem_save_travado"] = persistencia.MENSAGEM_SAVE_TRAVADO
