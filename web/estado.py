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

    `fase_atual` guarda a fase que está sendo exibida em `GET /fase` (nome,
    confrontos já resolvidos, o confronto pendente do jogador — se ainda não
    decidido — e os classificados que avançam dela), pra não
    recalcular/resortear os confrontos a cada requisição — só é recalculada
    quando `None` (fase nova) e é limpa quando o jogador avança pra próxima
    fase (`POST /fase/avancar`). `campeao` só é preenchido quando a
    temporada termina.

    `disputa_penaltis` guarda, entre requisições, o estado (formato de
    `penaltis.criar_disputa`) da disputa de pênaltis em andamento do
    confronto pendente do jogador — o mesmo papel que a variável local
    `estado` tinha dentro de `disputa_penaltis()` no terminal, só que
    persistido aqui porque cada cobrança é uma requisição HTTP separada.
    `None` quando não há disputa em andamento.

    `historico` guarda as temporadas já concluídas desta carreira, no mesmo
    formato usado por `persistencia`/`menu.py`: uma lista de dicts
    `{"temporada", "campeao", "fases"}` que identifica os times pelo `id`
    (`campeao` é o id do campeão; cada fase vem de
    `campeonato.registro_da_fase`, com confrontos `[id_a, id_b, id_vencedor,
    gols_a, gols_b]`). Nome/escudo são resolvidos só na exibição. Vazio num
    jogo novo; copiado do save quando uma carreira existente é carregada.

    `times_do_campeonato` guarda o roster completo do campeonato capturado no
    início da carreira — os MESMOS objetos `Equipe` (por identidade) usados em
    `classificados`, não cópias novas. É reaproveitado em `POST
    /campeao/continuar` pra sortear a próxima temporada sem perder a
    progressão (finanças/fãs/títulos) acumulada durante a carreira: recarregar
    o elenco do zero via `persistencia.carregar_equipes()` criaria objetos
    `Equipe` novos, com os valores base do arquivo, jogando fora tudo que foi
    ganho jogando. Vazio quando não informado (ex.: carreiras carregadas de um
    save cujo `classificados` já veio como objetos `Equipe` reconstruídos à
    parte — mesmo split de identidade que já existe hoje entre
    `dados["classificados"]` e `equipes[campeonato]` em `menu.carregar_jogo`).
    """

    campeonato: str
    time_escolhido: Equipe
    temporada: int
    classificados: list[Equipe]
    fases_da_temporada: list = field(default_factory=list)
    fase_atual: dict | None = None
    disputa_penaltis: dict | None = None
    campeao: Equipe | None = None
    historico: list = field(default_factory=list)
    times_do_campeonato: list[Equipe] = field(default_factory=list)


_jogo_atual: EstadoJogo | None = None


def iniciar_jogo(
    campeonato: str,
    time_escolhido: Equipe,
    temporada: int,
    classificados: list[Equipe],
    historico: list | None = None,
    times_do_campeonato: list[Equipe] | None = None,
) -> EstadoJogo:
    """Cria um novo jogo em andamento, substituindo o anterior (se houver).

    `historico` e `times_do_campeonato` são copiados (nunca guardados por
    referência) — a lista em si nunca é a mesma recebida pelo chamador,
    embora os objetos `Equipe` dentro de `times_do_campeonato` continuem
    sendo os mesmos (por identidade) que os de `classificados`, de propósito.
    """
    global _jogo_atual
    _jogo_atual = EstadoJogo(
        campeonato=campeonato,
        time_escolhido=time_escolhido,
        temporada=temporada,
        classificados=classificados,
        historico=list(historico) if historico is not None else [],
        times_do_campeonato=list(times_do_campeonato) if times_do_campeonato is not None else [],
    )
    return _jogo_atual


def obter_jogo() -> EstadoJogo | None:
    """Retorna o jogo em andamento atual, ou `None` se nenhum foi iniciado."""
    return _jogo_atual
