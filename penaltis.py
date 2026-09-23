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


def disputa_penaltis(time_a, time_b, interativo=False):
    """Decide um confronto na cobrança de pênaltis.

    Se `interativo` for True, o chute e a defesa do goleiro de `time_a` são
    escolhidos pelo usuário; caso contrário, tudo é sorteado automaticamente
    (usado para simular, com o mesmo modelo, os confrontos sem jogador humano).
    Retorna (vencedor, gols_a, gols_b).
    """
    gols_a = 0
    gols_a_possiveis = 0
    gols_b = 0
    gols_b_possiveis = 0
    gols_diferenca = 0
    cobranca = 0
    sequencia_a = []
    sequencia_b = []


    while True:
        cobranca += 1
        if interativo:
            if cobranca <= 5:
                print(f"\n-- Cobrança {cobranca}/5 --")
            else:
                print(f"\n-- Cobrança {cobranca} - alternadas --")

        # time_a cobra, o goleiro de time_b tenta adivinhar o canto.
        chute = (
            escolher_canto(
                "Escolha o canto do seu chute (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
            )
            if interativo
            else random.randint(1, 3)
        )
        defesa_b = random.randint(1, 3)
        if chute == defesa_b:
            if interativo:
                print(f"🧤 O goleiro do {time_b} pegou no {CANTOS[chute]}!")
            sequencia_a.append("🔴")
        else:
            gols_a += 1
            if interativo:
                print(f"⚽ GOL do {time_a} no {CANTOS[chute]}, o goleiro adversário tentou pegar no {CANTOS[defesa_b]}! ")
            sequencia_a.append("🟢")

        if interativo:
            largura_nome = max(len(time_a), len(time_b))
            largura_gols = max(len(str(gols_a)), len(str(gols_b)))
            print(
                f"Placar: {time_a:<{largura_nome}} {gols_a:>{largura_gols}} {''.join(sequencia_a)}\n"
                f"        {time_b:<{largura_nome}} {gols_b:>{largura_gols}} {''.join(sequencia_b)}"
            )

        # Verifica se é necessária cobrança do time b ou se disputa terminou.
        if (cobranca >2 and cobranca <= 5):
            gols_diferenca = abs(gols_a - gols_b)
            gols_a_possiveis = gols_a + (5 - cobranca)
            gols_b_possiveis = (gols_b + (5 - cobranca) + 1)
            if (5 - cobranca < gols_diferenca) and gols_a_possiveis < gols_b_possiveis:
                #vc n tem mais chance de alcancar o adv.
                break
            if (5 - cobranca < gols_diferenca) and gols_a > gols_b_possiveis:
                #vc ganhou, o adv n te alcanca mais
                break

        # time_b cobra, o goleiro de time_a tenta adivinhar o canto.
        chute_b = random.randint(1, 3)
        defesa_a = (
            escolher_canto(
                "Para qual canto seu goleiro vai pular (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
            )
            if interativo
            else random.randint(1, 3)
        )
        if chute_b == defesa_a:
            if interativo:
                print(f"🧤 Seu goleiro pegou no {CANTOS[chute_b]}!")
            sequencia_b.append("🔴")
        else:
            gols_b += 1
            if interativo:
                print(f"⚽ GOL do {time_b} no {CANTOS[chute_b]}, seu goleiro tentou pegar no {CANTOS[defesa_a]}!")
            sequencia_b.append("🟢")

        if interativo:
            largura_nome = max(len(time_a), len(time_b))
            largura_gols = max(len(str(gols_a)), len(str(gols_b)))
            print(
                f"Placar: {time_a:<{largura_nome}} {gols_a:>{largura_gols}} {''.join(sequencia_a)}\n"
                f"        {time_b:<{largura_nome}} {gols_b:>{largura_gols}} {''.join(sequencia_b)}"
            )

        gols_diferenca = abs(gols_a - gols_b)
        if (cobranca >2 and cobranca <= 5) and (5 - cobranca < gols_diferenca):
            break
        if cobranca > 5 and gols_diferenca > 0:
            break

    vencedor = time_a if gols_a > gols_b else time_b
    if interativo:
        print(f"\n {vencedor} venceu a disputa de pênaltis! pressione para continuar...")
    return vencedor, gols_a, gols_b
