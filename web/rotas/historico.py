"""Rotas de leitura do histórico da carreira em andamento.

Espelha as telas de histórico do terminal (`menu.exibir_historico_jogos`,
`menu.exibir_classificacao`, `menu.exibir_campeoes`), lendo
`jogo.historico` do estado em memória (`web/estado.py`). Todas as rotas
daqui dependem de um jogo em andamento e retornam 404 sem ele.
"""

from fastapi import APIRouter, HTTPException, Request

from web.estado import EstadoJogo, obter_jogo
from web.templates_config import templates

router = APIRouter(tags=["historico"])


def _jogo_em_andamento() -> EstadoJogo:
    """Retorna o jogo em andamento ou levanta 404 — compartilhado por todas
    as rotas de histórico."""
    jogo = obter_jogo()
    if jogo is None:
        raise HTTPException(status_code=404, detail="Nenhum jogo em andamento. Comece um novo jogo.")
    return jogo


@router.get("/historico")
def tela_historico(request: Request):
    """Lista as temporadas concluídas (número e campeão de cada uma), igual
    ao topo de `exibir_historico_jogos` no terminal."""
    jogo = _jogo_em_andamento()
    return templates.TemplateResponse(request, "historico.html", {"historico": jogo.historico})
