import random
import sys
import os

class COR_TXT:
    ERRO = "\033[91m"
    ATENCAO = "\033[33m"
    NORMAL = '\033[0m'
    SUCESSO = '\033[92m'

def ajuda():
    print("Escolha um time pelo número.")
    print("Exemplo: python futebol.py 2")

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


NOMES_FASE = {
    1: "Final - Copa do Mundo 2026",
    2: "Semifinal - Copa do Mundo 2026",
    4: "Quartas de Final - Copa do Mundo 2026",
    8: "Oitavas de Final - Copa do Mundo 2026",
    16: "16-avos de Final",
    32: "32-avos de Final",
}


def nome_da_fase(num_confrontos):
    return NOMES_FASE.get(num_confrontos, f"Rodada de {num_confrontos * 2}")


def gerar_rodadas(times, time_escolhido=None):
    """Gera as rodadas eliminatórias uma a uma (lazy), até sobrar um campeão.

    Cada rodada produzida é uma tupla (nome_fase, confrontos), em que
    `confrontos` é uma lista de tuplas (time_a, time_b, vencedor).
    A última rodada gerada tem sempre um único confronto: a final.
    Confrontos com `time_escolhido` são decididos por pênaltis; os demais
    (sem jogador humano) saem direto no sorteio.
    """
    classificados = list(times)
    random.shuffle(classificados)

    while len(classificados) > 1:
        proxima_fase = []
        confrontos = []

        # Se o número de times for ímpar, o último avança direto (bye).
        avanca_direto = None
        if len(classificados) % 2 != 0:
            avanca_direto = classificados[-1]
            classificados = classificados[:-1]

        nome_fase = nome_da_fase(len(classificados) // 2)

        for i in range(0, len(classificados), 2):
            time_a, time_b = classificados[i], classificados[i + 1]

            if time_escolhido in (time_a, time_b):
                adversario = time_b if time_a == time_escolhido else time_a
                print(f"\n=== {nome_fase} ===")
                print(f" {time_escolhido}  x  {adversario}")
                if time_a == time_escolhido:
                    vencedor, gols_a, gols_b = disputa_penaltis(time_a, time_b, interativo=True)
                else:
                    vencedor, gols_b, gols_a = disputa_penaltis(time_b, time_a, interativo=True)
            else:
                vencedor, gols_a, gols_b = disputa_penaltis(time_a, time_b, interativo=False)

            confrontos.append((time_a, time_b, vencedor, gols_a, gols_b))
            proxima_fase.append(vencedor)

        if avanca_direto is not None:
            proxima_fase.append(avanca_direto)

        yield nome_fase, confrontos
        classificados = proxima_fase


def exibir_rodada(nome_fase, confrontos):
    print(f"\n--- {nome_fase} ---")

    largura_a = max(len(time_a) for time_a, _, _, _, _ in confrontos)
    largura_b = max(len(time_b) for _, time_b, _, _, _ in confrontos)

    for time_a, time_b, vencedor, gols_a, gols_b in confrontos:
        print(f"{time_a:<{largura_a}} {gols_a} x {gols_b} {time_b:<{largura_b}} -> {vencedor}")


if __name__ == '__main__':

    times1 = [
        "São Paulo",
        "Palmeiras",
        "Corinthians",
        "Santos",
        "Flamengo",
        "Vasco",
        "Botafogo",
        "Fluminense",
        "Grêmio",
        "Internacional",
        "Cruzeiro",
        "Atlético-MG",
        "Bahia",
        "Vitória",
        "Athletico-PR",
        "Coritiba"
    ]

    times = [
    "Brasil",
    "Argentina",
    "Uruguai",
    "Paraguai",
    "França",
    "Espanha",
    "Alemanha",
    "Inglaterra",
    "Itália",
    "Holanda",
    "Portugal",
    "Croácia",
    "Marrocos",
    "Bélgica",
    "Noruega",
    "Suíça"
    ]

    if len(sys.argv) < 2:
        ajuda()
    else:
        escolha = int(sys.argv[1])

        if escolha < 1 or escolha > len(times):
            print(COR_TXT.ERRO, "Time inválido!", COR_TXT.NORMAL)
        else:
            time_escolhido = times[escolha - 1]
            os.system('cls')
            print("Seu time:", time_escolhido)

            campeao = None
            for nome_fase, confrontos in gerar_rodadas(times, time_escolhido):
                exibir_rodada(nome_fase, confrontos)
                if len(confrontos) == 1:
                    campeao = confrontos[0][2]

            print("\n🏆 Campeão da Copa do Brasil:", campeao)

            if time_escolhido == campeao:
                print(COR_TXT.SUCESSO, "🎉 PARABÉNS! Você foi campeão!",
                      COR_TXT.NORMAL)
            else:
                print(COR_TXT.ATENCAO, "😢 Você não foi campeão.",
                      COR_TXT.NORMAL)