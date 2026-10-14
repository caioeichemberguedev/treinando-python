"""Estado do "jogo em andamento" na versão web, guardado em memória.

Um único jogo em andamento por vez no servidor (ID-001), sem login nem
múltiplos jogadores. Desde o E-018, a carreira também é gravada em `saves/`
como no terminal: o `EstadoJogo` guarda o `nome_save` do arquivo e
`salvar_jogo_em_andamento` é o único ponto da web que grava (as rotas nunca
chamam `persistencia.salvar_jogo` direto). Se o servidor reiniciar, o jogo
em memória se perde, mas a carreira continua em `saves/` até a última
gravação.
"""

from dataclasses import dataclass, field

import persistencia
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

    `nome_save` é o nome do arquivo da carreira em `saves/` (sem extensão):
    gerado por `persistencia.gerar_nome_save()` num jogo novo, ou o do save
    carregado. `None` só em estado montado à mão (testes) — jogo só em
    memória, que `salvar_jogo_em_andamento` nunca grava.
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
    nome_save: str | None = None


_jogo_atual: EstadoJogo | None = None


def iniciar_jogo(
    campeonato: str,
    time_escolhido: Equipe,
    temporada: int,
    classificados: list[Equipe],
    historico: list | None = None,
    times_do_campeonato: list[Equipe] | None = None,
    nome_save: str | None = None,
) -> EstadoJogo:
    """Cria um novo jogo em andamento, substituindo o anterior (se houver).

    `historico` e `times_do_campeonato` são copiados (nunca guardados por
    referência) — a lista em si nunca é a mesma recebida pelo chamador,
    embora os objetos `Equipe` dentro de `times_do_campeonato` continuem
    sendo os mesmos (por identidade) que os de `classificados`, de propósito.
    `nome_save` amarra o jogo ao arquivo da carreira em `saves/`.
    """
    global _jogo_atual
    _jogo_atual = EstadoJogo(
        campeonato=campeonato,
        time_escolhido=time_escolhido,
        temporada=temporada,
        classificados=classificados,
        historico=list(historico) if historico is not None else [],
        times_do_campeonato=list(times_do_campeonato) if times_do_campeonato is not None else [],
        nome_save=nome_save,
    )
    return _jogo_atual


def obter_jogo() -> EstadoJogo | None:
    """Retorna o jogo em andamento atual, ou `None` se nenhum foi iniciado."""
    return _jogo_atual


def encerrar_jogo() -> None:
    """Encerra o jogo em andamento (ex.: "Salvar e sair"): depois disso,
    `obter_jogo()` devolve `None`. Não grava nada em `saves/`."""
    global _jogo_atual
    _jogo_atual = None


def salvar_jogo_em_andamento(
    jogo: EstadoJogo,
    temporada: int,
    classificados: list[Equipe] | None,
) -> None:
    """Grava a carreira de `jogo` em `saves/<jogo.nome_save>.db`.

    `temporada` e `classificados` vêm por parâmetro (e não de `jogo`) porque,
    com a fase decidida, o retrato gravado é o "depois" — a próxima
    temporada, ou os classificados que avançam —, enquanto o `jogo` ainda
    guarda os da tela atual, igual ao terminal. `classificados=None` =
    temporada nova, ainda não sorteada. Campeonato, time escolhido e
    histórico vêm do `jogo`.

    Não faz nada se `jogo.nome_save` for `None` (jogo só em memória).
    """
    if jogo.nome_save is None:
        return
    persistencia.salvar_jogo(
        jogo.nome_save,
        jogo.campeonato,
        jogo.time_escolhido,
        temporada,
        classificados,
        jogo.historico,
    )
