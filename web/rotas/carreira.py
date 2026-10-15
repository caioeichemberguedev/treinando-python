"""Dashboard da carreira em andamento (E-019): a "central do clube" entre
as fases.

`GET /carreira` só lê o estado em memória (`web/estado.py`) e mostra o
próximo jogo, a ficha do time e os botões para continuar ou voltar ao
menu — nunca muda o estado nem grava em `saves/` (a carreira já é gravada
quando cada fase fica decidida, desde o E-018).
"""

from fastapi import APIRouter, HTTPException, Request

from campeonato import adversario_na_proxima_fase
from web.estado import EstadoJogo, obter_jogo
from web.templates_config import templates

router = APIRouter(tags=["carreira"])


def _nome_curto_da_fase(nome_fase: str) -> str:
    """Tira o sufixo `" - <campeonato>"` do nome da fase (mesma regra de
    `campeonato.montar_classificacao`)."""
    return nome_fase.split(" - ")[0]


def _fase_da_eliminacao(jogo: EstadoJogo) -> str | None:
    """Nome curto da fase em que o time do jogador perdeu, procurando só nas
    fases já jogadas desta temporada (`jogo.fases_da_temporada`).

    `None` quando a derrota não está registrada (carreira carregada no meio
    da temporada — as fases anteriores não ficam guardadas, ID-014).
    """
    for fase in jogo.fases_da_temporada:
        for time_a, time_b, vencedor, _gols_a, _gols_b in fase["confrontos"]:
            jogou = jogo.time_escolhido in (time_a, time_b)
            if jogou and vencedor != jogo.time_escolhido:
                return _nome_curto_da_fase(fase["nome_fase"])
    return None


def _proximo_jogo(jogo: EstadoJogo) -> dict:
    """Situação do bloco "Próximo jogo" do dashboard, como um dict para o
    template. `situacao` é uma de: `"encerrada"`, `"jogo"`, `"bye"` ou
    `"eliminado"`.

    Ordem das verificações (decisão 8 do E-019):
    1. campeão coroado → temporada encerrada;
    2. fase com o confronto do jogador pendente → adversário do par
       pendente;
    3. senão calcula com `adversario_na_proxima_fase` sobre a lista que vai
       ser jogada: os `proximos` da fase atual (decidida, mas sem ter
       seguido) ou `jogo.classificados` (fase ainda não montada). Na web o
       vencedor do confronto do jogador vai para o fim de `proximos`, então
       nunca se supõe a posição no chaveamento.
    """
    if jogo.campeao is not None:
        return {
            "situacao": "encerrada",
            "campeao": jogo.campeao,
            "jogador_foi_campeao": jogo.time_escolhido == jogo.campeao,
        }

    fase_atual = jogo.fase_atual
    if fase_atual is not None and fase_atual["confronto_pendente"] is not None:
        time_a, time_b = fase_atual["confronto_pendente"]
        adversario = time_b if time_a == jogo.time_escolhido else time_a
        return {
            "situacao": "jogo",
            "nome_fase": _nome_curto_da_fase(fase_atual["nome_fase"]),
            "adversario": adversario,
        }

    lista = fase_atual["proximos"] if fase_atual is not None else jogo.classificados
    previsao = adversario_na_proxima_fase(lista, jogo.time_escolhido, jogo.campeonato)
    if previsao is None:
        return {"situacao": "eliminado", "fase_eliminacao": _fase_da_eliminacao(jogo)}

    nome_fase, adversario = previsao
    nome_fase = _nome_curto_da_fase(nome_fase)
    if adversario is None:
        return {"situacao": "bye", "nome_fase": nome_fase}
    return {"situacao": "jogo", "nome_fase": nome_fase, "adversario": adversario}


@router.get("/carreira")
def tela_carreira(request: Request):
    """Dashboard da carreira em andamento. Sem jogo → 404. Só leitura."""
    jogo = obter_jogo()
    if jogo is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Nenhuma carreira em andamento. Continue uma em "
                '"Carreiras salvas" ou comece um novo jogo.'
            ),
        )

    return templates.TemplateResponse(
        request,
        "carreira.html",
        {
            "campeonato": jogo.campeonato,
            "temporada": jogo.temporada,
            "time_escolhido": jogo.time_escolhido,
            "nome_save": jogo.nome_save,
            "proximo_jogo": _proximo_jogo(jogo),
        },
    )
