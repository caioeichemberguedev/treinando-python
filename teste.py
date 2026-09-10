import random
import sys


def ajuda():
    print("Escolha um time pelo número.")
    print("Exemplo: python futebol.py 2")


def sortear_campeao(times):
    return random.choice(times)


if __name__ == '__main__':

    times = [
        "Corinthians",
        "Palmeiras",
        "São Paulo",
        "Santos",
        "Flamengo",
        "Vasco",
        "Grêmio",
        "Internacional"
    ]

    if len(sys.argv) < 2:
        ajuda()
    else:
        escolha = int(sys.argv[1])

        if escolha < 1 or escolha > len(times):
            print("Time inválido!")
        else:
            time_escolhido = times[escolha - 1]

            print("Seu time:", time_escolhido)

            campeao = sortear_campeao(times)

            print("🏆 Campeão da Copa do Brasil:", campeao)

            if time_escolhido == campeao:
                print("🎉 PARABÉNS! Você foi campeão!")
            else:
                print("😢 Você não foi campeão.")