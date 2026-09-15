import random
import sys

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
        print(COR_TXT.ERRO, "Escolha inválida! Digite 1, 2 ou 3.", COR_TXT.NORMAL)


def disputa_penaltis(time_usuario, time_adversario):
    """Decide o confronto do time do usuário na cobrança de pênaltis."""
    print(f"\n⚽ Vai para os pênaltis: {time_usuario} x {time_adversario}!")

    gols_usuario = 0
    gols_adversario = 0
    cobranca = 0

    while True:
        cobranca += 1
        print(f"\n-- Cobrança {cobranca} --")

        # Seu time cobra, o goleiro adversário tenta adivinhar o canto.
        chute = escolher_canto(
            "Escolha o canto do seu pênalti (1-esquerdo, 2-meio, 3-direito): "
        )
        defesa_adversario = random.randint(1, 3)
        if chute == defesa_adversario:
            print(f"🧤 O goleiro do {time_adversario} pegou no {CANTOS[chute]}!")
        else:
            gols_usuario += 1
            print(f"⚽ GOL do {time_usuario} no {CANTOS[chute]}!")

        # O adversário cobra, você escolhe o canto que seu goleiro vai pular.
        chute_adversario = random.randint(1, 3)
        defesa = escolher_canto(
            "Para qual canto seu goleiro vai pular (1-esquerdo, 2-meio, 3-direito): "
        )
        if chute_adversario == defesa:
            print(f"🧤 Seu goleiro pegou no {CANTOS[chute_adversario]}!")
        else:
            gols_adversario += 1
            print(f"⚽ GOL do {time_adversario} no {CANTOS[chute_adversario]}!")

        print(f"Placar: {time_usuario} {gols_usuario} x {gols_adversario} {time_adversario}")

        if cobranca >= 5 and gols_usuario != gols_adversario:
            break

    vencedor = time_usuario if gols_usuario > gols_adversario else time_adversario
    print(f"🏆 {vencedor} venceu a disputa de pênaltis!")
    return vencedor


def gerar_rodadas(times, time_escolhido=None):
    """Gera as rodadas eliminatórias uma a uma (lazy), até sobrar um campeão.

    Cada rodada produzida é uma lista de tuplas (time_a, time_b, vencedor).
    A última rodada gerada tem sempre um único confronto: a final.
    Confrontos com `time_escolhido` são decididos por pênaltis; os demais
    (sem jogador humano) saem direto no sorteio.
    """
    classificados = list(times)
    random.shuffle(classificados)
    numero = 0

    while len(classificados) > 1:
        numero += 1
        input("\nPressione ENTER para disputar a próxima fase...")

        proxima_fase = []
        confrontos = []

        # Se o número de times for ímpar, o último avança direto (bye).
        avanca_direto = None
        if len(classificados) % 2 != 0:
            avanca_direto = classificados[-1]
            classificados = classificados[:-1]

        for i in range(0, len(classificados), 2):
            time_a, time_b = classificados[i], classificados[i + 1]

            if time_escolhido in (time_a, time_b):
                adversario = time_b if time_a == time_escolhido else time_a
                vencedor = disputa_penaltis(time_escolhido, adversario)
            else:
                vencedor = random.choice([time_a, time_b])

            confrontos.append((time_a, time_b, vencedor))
            proxima_fase.append(vencedor)

        if avanca_direto is not None:
            proxima_fase.append(avanca_direto)

        yield numero, confrontos
        classificados = proxima_fase


def exibir_rodada(numero, confrontos):
    nome_fase = "Final" if len(confrontos) == 1 else f"Rodada {numero}"
    print(f"\n--- {nome_fase} ---")
    for time_a, time_b, vencedor in confrontos:
        print(f"{time_a} x {time_b} -> {vencedor}")


if __name__ == '__main__':

    times = [
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

    if len(sys.argv) < 2:
        ajuda()
    else:
        escolha = int(sys.argv[1])

        if escolha < 1 or escolha > len(times):
            print(COR_TXT.ERRO, "Time inválido!", COR_TXT.NORMAL)
        else:
            time_escolhido = times[escolha - 1]

            print("Seu time:", time_escolhido)

            campeao = None
            for numero, confrontos in gerar_rodadas(times, time_escolhido):
                exibir_rodada(numero, confrontos)
                if len(confrontos) == 1:
                    campeao = confrontos[0][2]

            print("\n🏆 Campeão da Copa do Brasil:", campeao)

            if time_escolhido == campeao:
                print(COR_TXT.SUCESSO, "🎉 PARABÉNS! Você foi campeão!",
                      COR_TXT.NORMAL)
            else:
                print(COR_TXT.ATENCAO, "😢 Você não foi campeão.",
                      COR_TXT.NORMAL)