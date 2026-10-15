"""Dashboard da carreira em andamento (E-019): a "central do clube" entre
as fases.

`GET /carreira` só lê o estado em memória (`web/estado.py`) e mostra o
próximo jogo, a ficha do time, as estatísticas e o histórico da carreira
(calculados por `estatisticas.py`) e os botões para continuar ou voltar ao
menu — nunca muda o estado nem grava em `saves/` (a carreira já é gravada
quando cada fase fica decidida, desde o E-018).
"""

from fastapi import APIRouter, HTTPException, Request

from campeonato import adversario_na_proxima_fase
from estatisticas import (
    campanha_na_temporada,
    melhor_campanha,
    nome_fase_curto,
    resumo_da_carreira,
    temporada_completa,
)
from web.estado import EstadoJogo, obter_jogo
from web.templates_config import templates

router = APIRouter(tags=["carreira"])


def _temporada_em_andamento(jogo: EstadoJogo) -> dict:
    """Temporada atual no formato de ids do histórico (`"campeao": None`),
    com uma cópia das fases já jogadas (`jogo.fases_da_temporada`, que já
    estão no formato de ids). Ao retomar no meio da temporada as fases
    anteriores não existem mais (ID-014) — a lista começa vazia."""
    return {
        "temporada": jogo.temporada,
        "campeao": None,
        "fases": list(jogo.fases_da_temporada),
    }


def _temporadas_da_carreira(jogo: EstadoJogo) -> list[dict]:
    """Todas as temporadas da carreira, no formato de ids do histórico: as
    concluídas (`jogo.historico`) e, se o campeão ainda não foi coroado, a
    temporada em andamento.

    Com o campeão coroado (antes de `/campeao/continuar`) a temporada atual
    já está no `historico` e ainda está em `fases_da_temporada` — por isso
    ela não entra de novo (os jogos não podem contar em dobro).
    """
    temporadas = list(jogo.historico)
    if jogo.campeao is None:
        temporadas.append(_temporada_em_andamento(jogo))
    return temporadas


def _rotulo_da_eliminacao(jogo: EstadoJogo) -> str | None:
    """Rótulo "Eliminado na <fase>" da temporada em andamento, vindo de
    `campanha_na_temporada`. `None` quando a derrota não está registrada
    (carreira carregada no meio da temporada, ID-014)."""
    campanha = campanha_na_temporada(_temporada_em_andamento(jogo), jogo.time_escolhido.id)
    if campanha["profundidade"] is None:
        return None
    return campanha["rotulo"]


def _linhas_do_historico(jogo: EstadoJogo, temporadas: list[dict]) -> list[dict]:
    """Uma linha por temporada para a tabela "Histórico da carreira":
    `campanha` (de `campanha_na_temporada`), `campeao` (id ou `None` na
    temporada em andamento) e `indice` (1-based, para o link de
    `tela_historico_jogos`; `None` na temporada em andamento, que ainda não
    está no `historico`)."""
    total_concluidas = len(jogo.historico)
    return [
        {
            "campanha": campanha_na_temporada(temporada, jogo.time_escolhido.id),
            "campeao": temporada.get("campeao"),
            "indice": posicao + 1 if posicao < total_concluidas else None,
        }
        for posicao, temporada in enumerate(temporadas)
    ]


def _estatisticas(jogo: EstadoJogo) -> dict:
    """Dados das seções "Estatísticas da carreira" e "Histórico da carreira"
    do dashboard: `resumo` (`resumo_da_carreira`), `melhor` (`melhor_campanha`,
    ou `None`), `linhas` da tabela e `incompleto` (alguma temporada sem as
    primeiras fases, ID-014; nunca com `times_do_campeonato` vazio)."""
    temporadas = _temporadas_da_carreira(jogo)
    linhas = _linhas_do_historico(jogo, temporadas)
    total_times = len(jogo.times_do_campeonato)
    incompleto = total_times > 0 and not all(
        temporada_completa(temporada, total_times) for temporada in temporadas
    )
    return {
        "resumo": resumo_da_carreira(temporadas, jogo.time_escolhido.id),
        "melhor": melhor_campanha([linha["campanha"] for linha in linhas]),
        "linhas": linhas,
        "incompleto": incompleto,
    }


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
            "nome_fase": nome_fase_curto(fase_atual["nome_fase"]),
            "adversario": adversario,
        }

    lista = fase_atual["proximos"] if fase_atual is not None else jogo.classificados
    previsao = adversario_na_proxima_fase(lista, jogo.time_escolhido, jogo.campeonato)
    if previsao is None:
        return {"situacao": "eliminado", "rotulo_eliminacao": _rotulo_da_eliminacao(jogo)}

    nome_fase, adversario = previsao
    nome_fase = nome_fase_curto(nome_fase)
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
            "estatisticas": _estatisticas(jogo),
        },
    )
