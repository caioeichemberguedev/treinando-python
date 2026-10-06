"""Rotas de leitura do histórico da carreira em andamento.

Espelha as telas de histórico do terminal (`menu.exibir_historico_jogos`,
`menu.exibir_classificacao`, `menu.exibir_campeoes`), lendo
`jogo.historico` do estado em memória (`web/estado.py`). Todas as rotas
daqui dependem de um jogo em andamento e retornam 404 sem ele.
"""

from collections import Counter

from fastapi import APIRouter, HTTPException, Request

from campeonato import montar_classificacao
from web.estado import EstadoJogo, obter_jogo
from web.templates_config import templates

router = APIRouter(tags=["historico"])


def _jogo_em_andamento() -> EstadoJogo:
    """Retorna o jogo em andamento ou levanta 404 — compartilhado por todas
    as rotas de histórico."""
    jogo = obter_jogo()
    if jogo is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhum jogo em andamento. Comece um novo jogo.",
        )
    return jogo


def _temporada_do_historico(historico: list, indice: int) -> dict:
    """Retorna a temporada de número `indice` (1-based, igual aos menus do
    terminal) ou levanta 404 se ele estiver fora do intervalo."""
    if not 1 <= indice <= len(historico):
        raise HTTPException(
            status_code=404, detail="Temporada não encontrada."
        )
    return historico[indice - 1]


def _contar_titulos(historico: list) -> list[tuple[str, int]]:
    """Conta os títulos de cada time, do maior para o menor (empates mantêm
    a ordem de primeira conquista, igual a `exibir_campeoes`).

    Normaliza pelo nome: no fluxo web `campeao` é um objeto `Equipe`; em
    saves carregados do JSON é uma string crua.
    """
    contagem = Counter(str(info["campeao"]) for info in historico)
    return sorted(contagem.items(), key=lambda item: -item[1])


@router.get("/historico")
def tela_historico(request: Request):
    """Lista as temporadas concluídas (número e campeão de cada uma), igual
    ao topo de `exibir_historico_jogos` no terminal."""
    jogo = _jogo_em_andamento()
    return templates.TemplateResponse(
        request, "historico.html", {"historico": jogo.historico}
    )


@router.get("/historico/{indice}/jogos")
def tela_historico_jogos(request: Request, indice: int):
    """Mostra, fase a fase, os confrontos de uma temporada concluída (igual
    `exibir_historico_jogos`)."""
    jogo = _jogo_em_andamento()
    temporada_info = _temporada_do_historico(jogo.historico, indice)
    return templates.TemplateResponse(
        request,
        "historico_jogos.html",
        {
            "temporada": temporada_info["temporada"],
            "campeao": temporada_info["campeao"],
            "fases": temporada_info["fases"],
        },
    )


@router.get("/historico/{indice}/classificacao")
def tela_historico_classificacao(request: Request, indice: int):
    """Mostra a classificação final de uma temporada concluída, reconstruída
    por `campeonato.montar_classificacao` (igual `exibir_classificacao`)."""
    jogo = _jogo_em_andamento()
    temporada_info = _temporada_do_historico(jogo.historico, indice)
    classificacao = montar_classificacao(temporada_info["fases"])
    grupos = [
        (rotulo, [str(time) for time in integrantes])
        for rotulo, integrantes in classificacao
    ]
    return templates.TemplateResponse(
        request,
        "classificacao.html",
        {"temporada": temporada_info["temporada"], "grupos": grupos},
    )


@router.get("/campeoes")
def tela_campeoes(request: Request):
    """Mostra o campeão de cada temporada e a contagem de títulos por time
    (igual `exibir_campeoes`)."""
    jogo = _jogo_em_andamento()
    return templates.TemplateResponse(
        request,
        "campeoes.html",
        {
            "historico": jogo.historico,
            "titulos_por_time": _contar_titulos(jogo.historico),
        },
    )
