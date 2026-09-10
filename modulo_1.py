import random
import sys

COR_TXT_ERRO = "\033[91m"
COR_TXT_ATENCAO = "\033[33m"
COR_TXT_NORMAL = '\033[0m'
COR_TXT_SUCESSO = '\033[92m'

def ajuda():
    print("Escolha um time pelo número.")
    print("Exemplo: python futebol.py 2")


def sortear_campeao(times):
    return random.choice(times)


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
        "Atlético-MG"
    ]

    if len(sys.argv) < 2:
        ajuda()
    else:
        escolha = int(sys.argv[1])

        if escolha < 1 or escolha > len(times):
            print(COR_TXT_ERRO, "Time inválido!", COR_TXT_NORMAL)
        else:
            time_escolhido = times[escolha - 1]

            print("Seu time:", time_escolhido)

            campeao = sortear_campeao(times)

            print("🏆 Campeão da Copa do Brasil:", campeao)

            if time_escolhido == campeao:
                print(COR_TXT_SUCESSO, "🎉 PARABÉNS! Você foi campeão!", COR_TXT_NORMAL)
            else:
                print(COR_TXT_ATENCAO, "😢 Você não foi campeão.", COR_TXT_NORMAL)