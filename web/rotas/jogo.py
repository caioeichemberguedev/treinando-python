"""Rotas do fluxo de uma carreira: escolher campeonato/time, jogar fase a
fase e ver o campeão no final.

O confronto do jogador ainda é resolvido automaticamente (`interativo=False`),
igual aos demais confrontos da fase — a tela de pênaltis de verdade
(passo-a-passo, com escolha de canto) chega em ID-001-T6.
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from campeonato import montar_confrontos_fase, sortear_classificados
from penaltis import disputa_penaltis
from persistencia import carregar_equipes
from web.estado import EstadoJogo, iniciar_jogo, obter_jogo
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


def _resolver_fase_atual(jogo: EstadoJogo) -> None:
    """Monta os confrontos da fase atual (a partir de `jogo.classificados`) e
    guarda o resultado em `jogo.fase_atual`, pra `GET /fase` só exibir sem
    recalcular a cada requisição.

    O confronto do jogador (`confronto_pendente`) ainda é resolvido aqui
    automaticamente, do mesmo jeito que os demais — a tela de pênaltis de
    verdade chega em ID-001-T6.
    """
    nome_fase, confrontos, confronto_pendente, proximos = montar_confrontos_fase(
        jogo.classificados, jogo.time_escolhido, jogo.campeonato
    )

    if confronto_pendente is not None:
        time_a, time_b = confronto_pendente
        vencedor, gols_a, gols_b = disputa_penaltis(time_a, time_b, interativo=False)
        perdedor = time_b if vencedor == time_a else time_a
        vencedor.registrar_vitoria()
        perdedor.registrar_eliminacao()
        confrontos = confrontos + [(time_a, time_b, vencedor, gols_a, gols_b)]
        proximos = proximos + [vencedor]

    jogo.fase_atual = {"nome_fase": nome_fase, "confrontos": confrontos, "proximos": proximos}


@router.get("/fase")
def tela_fase(request: Request):
    """Mostra a fase atual da temporada: nome da fase e confrontos já
    decididos. Calcula a fase na primeira visita; visitas seguintes (sem
    passar por `POST /fase/avancar`) reexibem o mesmo resultado já guardado.
    """
    jogo = obter_jogo()
    if jogo is None:
        raise HTTPException(status_code=404, detail="Nenhum jogo em andamento. Comece um novo jogo.")

    if jogo.fase_atual is None:
        _resolver_fase_atual(jogo)

    return templates.TemplateResponse(
        request,
        "fase.html",
        {
            "campeonato": jogo.campeonato,
            "temporada": jogo.temporada,
            "time_escolhido": jogo.time_escolhido,
            "nome_fase": jogo.fase_atual["nome_fase"],
            "confrontos": jogo.fase_atual["confrontos"],
        },
    )


@router.post("/fase/avancar")
def avancar_fase():
    """Fecha a fase atual e monta a próxima: se sobrar 1 classificado, marca
    o campeão da temporada e segue pra `GET /campeao`; senão, volta pra
    `GET /fase` já com os novos classificados.
    """
    jogo = obter_jogo()
    if jogo is None or jogo.fase_atual is None:
        raise HTTPException(status_code=404, detail="Nenhuma fase em andamento pra avançar.")

    jogo.fases_da_temporada.append(
        {"nome_fase": jogo.fase_atual["nome_fase"], "confrontos": jogo.fase_atual["confrontos"]}
    )
    proximos = jogo.fase_atual["proximos"]
    jogo.fase_atual = None
    jogo.classificados = proximos

    if len(proximos) == 1:
        campeao = proximos[0]
        campeao.sagrar_campea()
        jogo.campeao = campeao
        return RedirectResponse(url="/campeao", status_code=303)

    return RedirectResponse(url="/fase", status_code=303)


@router.get("/campeao")
def tela_campeao(request: Request):
    """Mostra o campeão da temporada, indicando se foi o time do jogador."""
    jogo = obter_jogo()
    if jogo is None or jogo.campeao is None:
        raise HTTPException(status_code=404, detail="Nenhum campeão definido ainda.")

    return templates.TemplateResponse(
        request,
        "campeao.html",
        {
            "campeonato": jogo.campeonato,
            "temporada": jogo.temporada,
            "campeao": jogo.campeao,
            "jogador_foi_campeao": jogo.time_escolhido == jogo.campeao,
        },
    )
