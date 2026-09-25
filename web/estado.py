"""Estado do "jogo em andamento" na versão web, guardado em memória.

Diferente do terminal (uma carreira por arquivo em `saves/`), esta fatia da
web ainda não persiste em disco — decisão do Caio registrada no backlog
(ID-001): um único jogo em andamento por vez no servidor, perdido se ele
reiniciar. É suficiente pra rodar local, sem login nem múltiplos jogadores.
"""

from dataclasses import dataclass, field

from equipe import Equipe


@dataclass
class EstadoJogo:
    """Um jogo em andamento: campeonato, time escolhido, temporada atual,
    ordem de classificados no chaveamento e fases já jogadas na temporada.
    """

    campeonato: str
    time_escolhido: Equipe
    temporada: int
    classificados: list[Equipe]
    fases_da_temporada: list = field(default_factory=list)


_jogo_atual: EstadoJogo | None = None


def iniciar_jogo(campeonato: str, time_escolhido: Equipe, temporada: int, classificados: list[Equipe]) -> EstadoJogo:
    """Cria um novo jogo em andamento, substituindo o anterior (se houver)."""
    global _jogo_atual
    _jogo_atual = EstadoJogo(
        campeonato=campeonato,
        time_escolhido=time_escolhido,
        temporada=temporada,
        classificados=classificados,
    )
    return _jogo_atual


def obter_jogo() -> EstadoJogo | None:
    """Retorna o jogo em andamento atual, ou `None` se nenhum foi iniciado."""
    return _jogo_atual
