import random

from cores import COR_TXT

CANTOS = {1: "canto esquerdo", 2: "meio", 3: "canto direito"}


def escolher_canto(mensagem):
    while True:
        entrada = input(mensagem)
        if entrada in ("1", "2", "3"):
            return int(entrada)
        if not entrada:
            return random.randint(1, 3)
        print(COR_TXT.ERRO, "Escolha inválida! Digite 1, 2, 3 ou nulo para tentar a sorte.", COR_TXT.NORMAL)


def criar_disputa(time_a, time_b):
    """Cria o estado inicial de uma disputa de pênaltis entre `time_a` e `time_b`.

    O estado é um dict simples, consumido uma cobrança por vez por
    `cobranca_time_a`/`cobranca_time_b`, até `estado["terminada"]` ficar
    `True` (aí `estado["vencedor"]` já está preenchido).
    """
    return {
        "time_a": time_a,
        "time_b": time_b,
        "gols_a": 0,
        "gols_b": 0,
        "cobranca": 0,
        "sequencia_a": [],
        "sequencia_b": [],
        "terminada": False,
        "vencedor": None,
    }


def _verifica_corte_antecipado(estado, falta_time_b_cobrar):
    """Verifica se a disputa já está decidida (corte antecipado ou morte
    súbita) e, se estiver, marca `estado["terminada"]`/`estado["vencedor"]`.

    `falta_time_b_cobrar` indica se a checagem acontece logo depois da
    cobrança de `time_a`, antes de `time_b` cobrar nessa mesma rodada
    (`True`), ou depois que os dois já cobraram na rodada (`False`). É a
    mesma lógica usada nos dois pontos em que a checagem acontecia antes da
    extração (mantida sem alterações de comportamento).
    """
    cobranca = estado["cobranca"]
    gols_a = estado["gols_a"]
    gols_b = estado["gols_b"]
    gols_diferenca = abs(gols_a - gols_b)

    if cobranca > 5:
        terminou = not falta_time_b_cobrar and gols_diferenca > 0
    elif cobranca > 2:
        if falta_time_b_cobrar:
            gols_a_possiveis = gols_a + (5 - cobranca)
            gols_b_possiveis = gols_b + (5 - cobranca) + 1
            terminou = (5 - cobranca < gols_diferenca) and (
                gols_a_possiveis < gols_b_possiveis or gols_a > gols_b_possiveis
            )
        else:
            terminou = (5 - cobranca) < gols_diferenca
    else:
        terminou = False

    if terminou:
        estado["terminada"] = True
        estado["vencedor"] = estado["time_a"] if gols_a > gols_b else estado["time_b"]
    return terminou


def cobranca_time_a(estado, canto=None):
    """Resolve UMA cobrança de `time_a`, com o goleiro de `time_b` tentando
    defender.

    `canto` é o canto do chute (1, 2 ou 3); se não for informado, é
    sorteado. Atualiza `estado` (gols, sequência, número da cobrança e,
    se a disputa já estiver decidida, `terminada`/`vencedor`) e retorna um
    dict com `chute`, `defesa` e `gol` dessa cobrança.
    """
    estado["cobranca"] += 1
    chute = canto if canto is not None else random.randint(1, 3)
    defesa = random.randint(1, 3)
    gol = chute != defesa
    if gol:
        estado["gols_a"] += 1
        estado["sequencia_a"].append("🟢")
    else:
        estado["sequencia_a"].append("🔴")

    _verifica_corte_antecipado(estado, falta_time_b_cobrar=True)
    return {"chute": chute, "defesa": defesa, "gol": gol}


def cobranca_time_b(estado, canto=None):
    """Resolve UMA cobrança de `time_b`, com o goleiro de `time_a` tentando
    defender.

    `canto` é o canto escolhido pelo goleiro de `time_a` (1, 2 ou 3); se não
    for informado, é sorteado. O chute de `time_b` é sempre sorteado.
    Atualiza `estado` do mesmo jeito que `cobranca_time_a` e retorna um
    dict com `chute`, `defesa` e `gol` dessa cobrança.
    """
    chute = random.randint(1, 3)
    defesa = canto if canto is not None else random.randint(1, 3)
    gol = chute != defesa
    if gol:
        estado["gols_b"] += 1
        estado["sequencia_b"].append("🟢")
    else:
        estado["sequencia_b"].append("🔴")

    _verifica_corte_antecipado(estado, falta_time_b_cobrar=False)
    return {"chute": chute, "defesa": defesa, "gol": gol}


def _imprime_placar(estado):
    time_a, time_b = estado["time_a"], estado["time_b"]
    gols_a, gols_b = estado["gols_a"], estado["gols_b"]
    largura_nome = max(len(time_a), len(time_b))
    largura_gols = max(len(str(gols_a)), len(str(gols_b)))
    print(
        f"Placar: {time_a:<{largura_nome}} {gols_a:>{largura_gols}} {''.join(estado['sequencia_a'])}\n"
        f"        {time_b:<{largura_nome}} {gols_b:>{largura_gols}} {''.join(estado['sequencia_b'])}"
    )


def disputa_penaltis(time_a, time_b, interativo=False):
    """Decide um confronto na cobrança de pênaltis.

    Se `interativo` for True, o chute e a defesa do goleiro de `time_a` são
    escolhidos pelo usuário; caso contrário, tudo é sorteado automaticamente
    (usado para simular, com o mesmo modelo, os confrontos sem jogador humano).
    Retorna (vencedor, gols_a, gols_b).
    """
    estado = criar_disputa(time_a, time_b)

    while not estado["terminada"]:
        if interativo:
            proxima_cobranca = estado["cobranca"] + 1
            if proxima_cobranca <= 5:
                print(f"\n-- Cobrança {proxima_cobranca}/5 --")
            else:
                print(f"\n-- Cobrança {proxima_cobranca} - alternadas --")

        # time_a cobra, o goleiro de time_b tenta adivinhar o canto.
        canto_a = (
            escolher_canto(
                "Escolha o canto do seu chute (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
            )
            if interativo
            else None
        )
        resultado_a = cobranca_time_a(estado, canto=canto_a)
        if interativo:
            if resultado_a["gol"]:
                print(
                    f"⚽ GOL do {time_a} no {CANTOS[resultado_a['chute']]}, "
                    f"o goleiro adversário tentou pegar no {CANTOS[resultado_a['defesa']]}! "
                )
            else:
                print(f"🧤 O goleiro do {time_b} pegou no {CANTOS[resultado_a['chute']]}!")
            _imprime_placar(estado)

        if estado["terminada"]:
            break

        # time_b cobra, o goleiro de time_a tenta adivinhar o canto.
        canto_b = (
            escolher_canto(
                "Para qual canto seu goleiro vai pular (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
            )
            if interativo
            else None
        )
        resultado_b = cobranca_time_b(estado, canto=canto_b)
        if interativo:
            if resultado_b["gol"]:
                print(
                    f"⚽ GOL do {time_b} no {CANTOS[resultado_b['chute']]}, "
                    f"seu goleiro tentou pegar no {CANTOS[resultado_b['defesa']]}!"
                )
            else:
                print(f"🧤 Seu goleiro pegou no {CANTOS[resultado_b['chute']]}!")
            _imprime_placar(estado)

    if interativo:
        print(f"\n {estado['vencedor']} venceu a disputa de pênaltis! pressione para continuar...")
    return estado["vencedor"], estado["gols_a"], estado["gols_b"]
