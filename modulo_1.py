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


def disputa_penaltis(time_usuario, time_adversario):
    """Decide o confronto do time do usuário na cobrança de pênaltis."""
    #print(f"\n🆚 Adversário nas penalidades: {time_adversario}!")

    gols_usuario = 0
    gols_user_possiveis = 0
    gols_adversario = 0
    gols_adv_possiveis = 0
    gols_diferenca = 0
    cobranca = 0
    sequencia_usuario = []
    sequencia_adversario = []


    while True:
        cobranca += 1
        if cobranca <= 5:
            print(f"\n-- Cobrança {cobranca}/5 --")
        else:
            print(f"\n-- Cobrança {cobranca} - alternadas --")

        # Seu time cobra, o goleiro adversário tenta adivinhar o canto.
        chute = escolher_canto(
            "Escolha o canto do seu chute (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
        )
        defesa_adversario = random.randint(1, 3)
        if chute == defesa_adversario:
            print(f"🧤 O goleiro do {time_adversario} pegou no {CANTOS[chute]}!")
            sequencia_usuario.append("🔴")
        else:
            gols_usuario += 1
            print(f"⚽ GOL do {time_usuario} no {CANTOS[chute]}, o goleiro adversário tentou pegar no {CANTOS[defesa_adversario]}! ")
            sequencia_usuario.append("🟢")

        # Verifica se é necessária cobrança do time b ou se disputa terminou.
        if (cobranca >2 and cobranca <= 5):
            gols_diferenca = abs(gols_usuario - gols_adversario)
            gols_user_possiveis = gols_usuario + (5 - cobranca)
            gols_adv_possiveis = (gols_adversario + (5 - cobranca) + 1)
            if (5 - cobranca < gols_diferenca) and gols_user_possiveis < gols_adv_possiveis:
                #vc n tem mais chance de alcancar o adv.
                break
            if (5 - cobranca < gols_diferenca) and gols_usuario > gols_adv_possiveis:
                #vc ganhou, o adv n te alcanca mais
                break

        largura_nome = max(len(time_usuario), len(time_adversario))
        largura_gols = max(len(str(gols_usuario)), len(str(gols_adversario)))
        print(
            f"Placar: {time_usuario:<{largura_nome}} {gols_usuario:>{largura_gols}} {''.join(sequencia_usuario)}\n"
            f"        {time_adversario:<{largura_nome}} {gols_adversario:>{largura_gols}} {''.join(sequencia_adversario)}"
        )

        # O adversário cobra, você escolhe o canto que seu goleiro vai pular.
        chute_adversario = random.randint(1, 3)
        defesa = escolher_canto(
            "Para qual canto seu goleiro vai pular (1-esquerdo, 2-meio, 3-direito, nulo-aleátório): "
        )
        if chute_adversario == defesa:
            print(f"🧤 Seu goleiro pegou no {CANTOS[chute_adversario]}!")
            sequencia_adversario.append("🔴")
        else:
            gols_adversario += 1
            print(f"⚽ GOL do {time_adversario} no {CANTOS[chute_adversario]}, seu goleiro tentou pegar no {CANTOS[defesa]}!")
            sequencia_adversario.append("🟢")

        largura_nome = max(len(time_usuario), len(time_adversario))
        largura_gols = max(len(str(gols_usuario)), len(str(gols_adversario)))
        print(
            f"Placar: {time_usuario:<{largura_nome}} {gols_usuario:>{largura_gols}} {''.join(sequencia_usuario)}\n"
            f"        {time_adversario:<{largura_nome}} {gols_adversario:>{largura_gols}} {''.join(sequencia_adversario)}"
        )

        gols_diferenca = abs(gols_usuario - gols_adversario)
        if (cobranca >2 and cobranca <= 5) and (5 - cobranca < gols_diferenca):
            break
        if cobranca > 5 and gols_diferenca > 0:
            break

    vencedor = time_usuario if gols_usuario > gols_adversario else time_adversario
    print(f"\n {vencedor} venceu a disputa de pênaltis! pressione para continuar...")
    return vencedor


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
                vencedor = disputa_penaltis(time_escolhido, adversario)
            else:
                vencedor = random.choice([time_a, time_b])

            confrontos.append((time_a, time_b, vencedor))
            proxima_fase.append(vencedor)

        if avanca_direto is not None:
            proxima_fase.append(avanca_direto)

        yield nome_fase, confrontos
        classificados = proxima_fase


def exibir_rodada(nome_fase, confrontos):
    print(f"\n--- {nome_fase} ---")

    largura_a = max(len(time_a) for time_a, _, _ in confrontos)
    largura_b = max(len(time_b) for _, time_b, _ in confrontos)

    for time_a, time_b, vencedor in confrontos:
        print(f"{time_a:<{largura_a}} x {time_b:<{largura_b}} -> {vencedor}")


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