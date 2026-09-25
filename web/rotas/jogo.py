"""Rotas do fluxo de uma carreira: escolher campeonato/time, jogar fase a
fase e ver o campeão no final.

O confronto do jogador é resolvido passo a passo em `/fase/penaltis`
(uma cobrança por requisição, com escolha de canto pelo jogador) — os
demais confrontos da fase continuam resolvidos automaticamente
(`interativo=False`, dentro de `montar_confrontos_fase`).
"""

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from campeonato import montar_confrontos_fase, sortear_classificados
from penaltis import CANTOS, cobranca_time_a, cobranca_time_b, criar_disputa
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

    O confronto do jogador (`confronto_pendente`) fica guardado sem vencedor
    — quem resolve é o fluxo passo a passo de `/fase/penaltis`.
    """
    nome_fase, confrontos, confronto_pendente, proximos = montar_confrontos_fase(
        jogo.classificados, jogo.time_escolhido, jogo.campeonato
    )

    jogo.fase_atual = {
        "nome_fase": nome_fase,
        "confrontos": confrontos,
        "confronto_pendente": confronto_pendente,
        "proximos": proximos,
    }


@router.get("/fase")
def tela_fase(request: Request):
    """Mostra a fase atual da temporada: nome da fase e confrontos já
    decididos. Calcula a fase na primeira visita; visitas seguintes (sem
    passar por `POST /fase/avancar`) reexibem o mesmo resultado já guardado.

    Se a fase ainda tiver o confronto do jogador pendente, redireciona pra
    `/fase/penaltis` em vez de exibir — essa tela só mostra fases já
    totalmente decididas.
    """
    jogo = obter_jogo()
    if jogo is None:
        raise HTTPException(status_code=404, detail="Nenhum jogo em andamento. Comece um novo jogo.")

    if jogo.fase_atual is None:
        _resolver_fase_atual(jogo)

    if jogo.fase_atual["confronto_pendente"] is not None:
        return RedirectResponse(url="/fase/penaltis", status_code=303)

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


def _turno_atual(estado_disputa: dict) -> str:
    """Indica de quem é a vez de cobrar: "a" (jogador chuta) ou "b"
    (adversário chuta, jogador escolhe o lado do goleiro).

    Mesma alternância usada dentro do laço de `disputa_penaltis`: `time_a`
    sempre cobra primeiro em cada rodada, então as sequências só ficam do
    mesmo tamanho quando é a vez de `time_a` cobrar de novo.
    """
    if len(estado_disputa["sequencia_a"]) == len(estado_disputa["sequencia_b"]):
        return "a"
    return "b"


def _iniciar_disputa_penaltis(jogo: EstadoJogo, confronto_pendente: tuple) -> None:
    """Cria a disputa de pênaltis do confronto pendente, sempre guardando o
    time do jogador como "time_a" do estado (`criar_disputa`) — é essa
    posição que faz `cobranca_time_a` representar o chute do jogador e
    `cobranca_time_b` representar a escolha do goleiro dele, igual ao que
    `disputa_penaltis(interativo=True)` já fazia no terminal (que também
    sempre chamava com o time do jogador em primeiro, invertendo os
    argumentos quando ele era o segundo do confronto).
    """
    time_a_original, time_b_original = confronto_pendente
    jogador_e_time_a_original = jogo.time_escolhido == time_a_original
    jogador, adversario = (
        (time_a_original, time_b_original) if jogador_e_time_a_original else (time_b_original, time_a_original)
    )

    jogo.disputa_penaltis = {
        "estado": criar_disputa(jogador, adversario),
        "time_a_original": time_a_original,
        "time_b_original": time_b_original,
        "jogador_e_time_a_original": jogador_e_time_a_original,
        "adversario": adversario,
    }


def _concluir_disputa_penaltis(jogo: EstadoJogo) -> None:
    """Fecha a disputa de pênaltis em andamento: registra vitória/eliminação,
    soma o confronto decidido em `jogo.fase_atual` (mesmo formato usado
    pelos confrontos resolvidos automaticamente) e limpa
    `jogo.disputa_penaltis`.
    """
    disputa = jogo.disputa_penaltis
    estado_disputa = disputa["estado"]
    time_a_original = disputa["time_a_original"]
    time_b_original = disputa["time_b_original"]
    vencedor = estado_disputa["vencedor"]

    if disputa["jogador_e_time_a_original"]:
        gols_a, gols_b = estado_disputa["gols_a"], estado_disputa["gols_b"]
    else:
        gols_a, gols_b = estado_disputa["gols_b"], estado_disputa["gols_a"]

    perdedor = time_b_original if vencedor == time_a_original else time_a_original
    vencedor.registrar_vitoria()
    perdedor.registrar_eliminacao()

    jogo.fase_atual["confrontos"] = jogo.fase_atual["confrontos"] + [
        (time_a_original, time_b_original, vencedor, gols_a, gols_b)
    ]
    jogo.fase_atual["proximos"] = jogo.fase_atual["proximos"] + [vencedor]
    jogo.fase_atual["confronto_pendente"] = None
    jogo.disputa_penaltis = None


@router.get("/fase/penaltis")
def tela_penaltis(request: Request):
    """Mostra o placar atual da disputa de pênaltis do confronto do jogador
    e pede a próxima decisão (canto do chute ou lado do goleiro), uma
    cobrança por vez.
    """
    jogo = obter_jogo()
    if jogo is None or jogo.fase_atual is None:
        raise HTTPException(status_code=404, detail="Nenhuma fase em andamento.")

    confronto_pendente = jogo.fase_atual["confronto_pendente"]
    if confronto_pendente is None:
        return RedirectResponse(url="/fase", status_code=303)

    if jogo.disputa_penaltis is None:
        _iniciar_disputa_penaltis(jogo, confronto_pendente)

    estado_disputa = jogo.disputa_penaltis["estado"]

    return templates.TemplateResponse(
        request,
        "penaltis.html",
        {
            "campeonato": jogo.campeonato,
            "temporada": jogo.temporada,
            "time_escolhido": jogo.time_escolhido,
            "adversario": jogo.disputa_penaltis["adversario"],
            "gols_jogador": estado_disputa["gols_a"],
            "gols_adversario": estado_disputa["gols_b"],
            "sequencia_jogador": estado_disputa["sequencia_a"],
            "sequencia_adversario": estado_disputa["sequencia_b"],
            "vez_do_jogador_chutar": _turno_atual(estado_disputa) == "a",
            "cantos": CANTOS,
        },
    )


@router.post("/fase/penaltis")
def cobrar_penalti(canto: Annotated[str, Form()] = ""):
    """Aplica UMA cobrança da disputa de pênaltis em andamento (chute do
    jogador ou lado do goleiro dele, conforme a vez) e redireciona de volta
    pra `GET /fase/penaltis` — até a disputa terminar, quando o confronto é
    fechado e o redirecionamento volta pra `GET /fase`.

    `canto` vazio sorteia (mesmo comportamento de "nulo" no terminal).
    """
    jogo = obter_jogo()
    if jogo is None or jogo.fase_atual is None or jogo.disputa_penaltis is None:
        raise HTTPException(status_code=404, detail="Nenhuma disputa de pênaltis em andamento.")

    if canto and canto not in {"1", "2", "3"}:
        raise HTTPException(status_code=400, detail="Canto inválido.")
    canto_escolhido = int(canto) if canto else None

    estado_disputa = jogo.disputa_penaltis["estado"]
    if _turno_atual(estado_disputa) == "a":
        cobranca_time_a(estado_disputa, canto=canto_escolhido)
    else:
        cobranca_time_b(estado_disputa, canto=canto_escolhido)

    if not estado_disputa["terminada"]:
        return RedirectResponse(url="/fase/penaltis", status_code=303)

    _concluir_disputa_penaltis(jogo)
    return RedirectResponse(url="/fase", status_code=303)


@router.post("/fase/avancar")
def avancar_fase():
    """Fecha a fase atual e monta a próxima: se sobrar 1 classificado, marca
    o campeão da temporada e segue pra `GET /campeao`; senão, volta pra
    `GET /fase` já com os novos classificados.
    """
    jogo = obter_jogo()
    if jogo is None or jogo.fase_atual is None:
        raise HTTPException(status_code=404, detail="Nenhuma fase em andamento pra avançar.")

    if jogo.fase_atual["confronto_pendente"] is not None:
        raise HTTPException(
            status_code=400, detail="Ainda falta decidir a disputa de pênaltis do seu time nesta fase."
        )

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
