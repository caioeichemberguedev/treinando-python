import random
import os
import json

class COR_TXT:
    ERRO = "\033[91m"
    ATENCAO = "\033[33m"
    NORMAL = '\033[0m'
    SUCESSO = '\033[92m'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EQUIPES = os.path.join(BASE_DIR, "equipes.json")
ARQUIVO_SALVO = os.path.join(BASE_DIR, "jogo_salvo.json")

CANTOS = {1: "canto esquerdo", 2: "meio", 3: "canto direito"}

EQUIPES_PADRAO = {
    "Copa do Brasil": [
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
        "Coritiba",
    ],
    "Copa do Mundo 2026": [
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
        "Suíça",
    ],
}


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
    1: "Final",
    2: "Semifinal",
    4: "Quartas de Final",
    8: "Oitavas de Final",
    16: "16-avos de Final",
    32: "32-avos de Final",
}


def nome_da_fase(num_confrontos):
    return NOMES_FASE.get(num_confrontos, f"Rodada de {num_confrontos * 2}")


def gerar_rodadas(classificados, time_escolhido=None, campeonato=""):
    """Gera as rodadas eliminatórias uma a uma (lazy), até sobrar um campeão.

    `classificados` já deve estar na ordem do chaveamento (embaralhada para um
    jogo novo, ou como estava salva para retomar um jogo em andamento).
    Cada rodada produzida é uma tupla (nome_fase, confrontos, proximos), em que
    `confrontos` é uma lista de tuplas (time_a, time_b, vencedor, gols_a, gols_b)
    e `proximos` é a lista de times que avançam para a próxima fase (usada para
    salvar o progresso do jogo).
    Confrontos com `time_escolhido` são decididos por pênaltis interativos; os
    demais (sem jogador humano) são simulados automaticamente pelo mesmo modelo.
    """
    classificados = list(classificados)

    while len(classificados) > 1:
        proxima_fase = []
        confrontos = []

        # Se o número de times for ímpar, o último avança direto (bye).
        avanca_direto = None
        if len(classificados) % 2 != 0:
            avanca_direto = classificados[-1]
            classificados = classificados[:-1]

        nome_fase = nome_da_fase(len(classificados) // 2)
        if campeonato:
            nome_fase = f"{nome_fase} - {campeonato}"

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

        yield nome_fase, confrontos, list(proxima_fase)
        classificados = proxima_fase


def exibir_rodada(nome_fase, confrontos):
    print(f"\n--- {nome_fase} ---")

    largura_a = max(len(time_a) for time_a, _, _, _, _ in confrontos)
    largura_b = max(len(time_b) for _, time_b, _, _, _ in confrontos)

    for time_a, time_b, vencedor, gols_a, gols_b in confrontos:
        print(f"{time_a:<{largura_a}} {gols_a} x {gols_b} {time_b:<{largura_b}} -> {vencedor}")


def carregar_equipes():
    if os.path.exists(ARQUIVO_EQUIPES):
        with open(ARQUIVO_EQUIPES, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    equipes = {campeonato: list(times) for campeonato, times in EQUIPES_PADRAO.items()}
    salvar_equipes(equipes)
    return equipes


def salvar_equipes(equipes):
    with open(ARQUIVO_EQUIPES, "w", encoding="utf-8") as arquivo:
        json.dump(equipes, arquivo, ensure_ascii=False, indent=2)


def salvar_jogo(campeonato, time_escolhido, temporada, classificados, historico=None):
    dados = {
        "campeonato": campeonato,
        "time_escolhido": time_escolhido,
        "temporada": temporada,
        "classificados": classificados,  # None = temporada nova, ainda não sorteada
        "historico": historico or [],  # temporadas já concluídas nesta carreira
    }
    with open(ARQUIVO_SALVO, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)


def carregar_jogo_salvo():
    if not os.path.exists(ARQUIVO_SALVO):
        return None
    with open(ARQUIVO_SALVO, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def escolher_numero(mensagem, minimo, maximo):
    while True:
        entrada = input(mensagem)
        if entrada.isdigit() and minimo <= int(entrada) <= maximo:
            return int(entrada)
        print(COR_TXT.ERRO, f"Escolha um número entre {minimo} e {maximo}.", COR_TXT.NORMAL)


def escolher_campeonato(equipes):
    nomes = list(equipes.keys())
    print("\nEscolha o campeonato:")
    for indice, nome in enumerate(nomes, start=1):
        print(f"{indice} - {nome}")
    escolha = escolher_numero("> ", 1, len(nomes))
    return nomes[escolha - 1]


def escolher_time(times):
    print("\nEscolha seu time:")
    for indice, nome in enumerate(times, start=1):
        print(f"{indice} - {nome}")
    escolha = escolher_numero("> ", 1, len(times))
    return times[escolha - 1]


def montar_classificacao(fases):
    """Reconstrói, a partir das fases de uma temporada, em que rodada cada
    time foi eliminado (campeão e vice tratados à parte, na final).
    Retorna uma lista de (rótulo, [times]) da melhor para a pior colocação.
    """
    grupos = []

    for indice in range(len(fases) - 1, -1, -1):
        nome_fase = fases[indice]["nome_fase"].split(" - ")[0]
        confrontos = fases[indice]["confrontos"]

        if indice == len(fases) - 1:
            time_a, time_b, vencedor, _, _ = confrontos[0]
            perdedor = time_b if vencedor == time_a else time_a
            grupos.append(("Campeão", [vencedor]))
            grupos.append(("Vice-campeão", [perdedor]))
        else:
            eliminados = []
            for time_a, time_b, vencedor, _, _ in confrontos:
                eliminados.append(time_b if vencedor == time_a else time_a)
            grupos.append((nome_fase, eliminados))

    return grupos


def exibir_historico_jogos(historico):
    if not historico:
        print(COR_TXT.ATENCAO, "Nenhuma temporada concluída ainda.", COR_TXT.NORMAL)
        return

    print("\nTemporadas disputadas:")
    for indice, temporada_info in enumerate(historico, start=1):
        print(f"{indice} - Temporada {temporada_info['temporada']} (Campeão: {temporada_info['campeao']})")

    indice = escolher_numero("Escolha uma temporada para ver os jogos: ", 1, len(historico))
    for fase in historico[indice - 1]["fases"]:
        exibir_rodada(fase["nome_fase"], fase["confrontos"])


def exibir_campeoes(historico):
    if not historico:
        print(COR_TXT.ATENCAO, "Nenhum campeão ainda.", COR_TXT.NORMAL)
        return

    print("\n--- Campeões por temporada ---")
    contagem = {}
    for temporada_info in historico:
        print(f"{temporada_info['temporada']}: {temporada_info['campeao']}")
        contagem[temporada_info["campeao"]] = contagem.get(temporada_info["campeao"], 0) + 1

    print("\n--- Títulos por time ---")
    for time, titulos in sorted(contagem.items(), key=lambda item: -item[1]):
        print(f"{time}: {titulos} título(s)")


def exibir_classificacao(historico):
    if not historico:
        print(COR_TXT.ATENCAO, "Nenhuma temporada concluída ainda.", COR_TXT.NORMAL)
        return

    print("\nTemporadas disponíveis:")
    for indice, temporada_info in enumerate(historico, start=1):
        print(f"{indice} - Temporada {temporada_info['temporada']}")

    indice = escolher_numero("Escolha uma temporada: ", 1, len(historico))
    temporada_info = historico[indice - 1]

    print(f"\n--- Classificação final: Temporada {temporada_info['temporada']} ---")
    for rotulo, integrantes in montar_classificacao(temporada_info["fases"]):
        print(f"{rotulo}: {', '.join(integrantes)}")


def menu_pos_temporada(campeonato, temporada, campeao, historico):
    """Mostrado ao fim de cada temporada. Retorna True se o jogador quiser
    seguir direto para a próxima temporada, False para voltar ao menu principal.
    """
    while True:
        print(f"\n=== Temporada {temporada} encerrada - {campeonato} ===")
        print("Campeão:", campeao)
        print("1 - Ver histórico de jogos")
        print("2 - Ver times campeões")
        print("3 - Ver classificação por temporada")
        print("4 - Seguir para a próxima temporada")
        print("5 - Voltar ao menu principal")
        opcao = input("> ").strip()

        if opcao == "1":
            exibir_historico_jogos(historico)
        elif opcao == "2":
            exibir_campeoes(historico)
        elif opcao == "3":
            exibir_classificacao(historico)
        elif opcao == "4":
            return True
        elif opcao == "5":
            return False
        else:
            print(COR_TXT.ERRO, "Opção inválida.", COR_TXT.NORMAL)


def rodar_temporada(campeonato, time_escolhido, temporada, classificados, times, historico=None):
    historico = historico or []

    if classificados is None:
        if len(times) < 2:
            print(COR_TXT.ERRO, "Esse campeonato não tem equipes suficientes para a nova temporada.", COR_TXT.NORMAL)
            return
        classificados = list(times)
        random.shuffle(classificados)
        salvar_jogo(campeonato, time_escolhido, temporada, classificados, historico)

    os.system('cls')
    print("Campeonato:", campeonato)
    print("Temporada:", temporada)
    print("Seu time:", time_escolhido)

    fases_da_temporada = []

    for nome_fase, confrontos, proximos in gerar_rodadas(classificados, time_escolhido, campeonato):
        exibir_rodada(nome_fase, confrontos)
        fases_da_temporada.append({"nome_fase": nome_fase, "confrontos": confrontos})

        if len(proximos) == 1:
            campeao = proximos[0]
            print(f"\n🏆 Campeão da {campeonato} {temporada}:", campeao)
            if time_escolhido == campeao:
                print(COR_TXT.SUCESSO, "🎉 PARABÉNS! Você foi campeão!", COR_TXT.NORMAL)
            else:
                print(COR_TXT.ATENCAO, "😢 Você não foi campeão.", COR_TXT.NORMAL)

            historico = historico + [{
                "temporada": temporada,
                "campeao": campeao,
                "fases": fases_da_temporada,
            }]

            proxima_temporada = temporada + 1
            salvar_jogo(campeonato, time_escolhido, proxima_temporada, None, historico)

            if menu_pos_temporada(campeonato, temporada, campeao, historico):
                rodar_temporada(campeonato, time_escolhido, proxima_temporada, None, times, historico)
            return

        salvar_jogo(campeonato, time_escolhido, temporada, proximos, historico)

        escolha = input("\nENTER para a próxima fase, ou digite 'sair' para voltar ao menu: ").strip().lower()
        if escolha == "sair":
            print("\nProgresso salvo! Use 'Carregar jogo' no menu para continuar depois.")
            return


def novo_jogo(equipes):
    if os.path.exists(ARQUIVO_SALVO):
        confirmacao = input(
            "Já existe uma carreira salva. Iniciar um novo jogo vai substituí-la. Confirmar? (s/n): "
        ).strip().lower()
        if confirmacao != "s":
            print("Novo jogo cancelado.")
            return

    campeonato = escolher_campeonato(equipes)
    times = equipes[campeonato]

    if len(times) < 2:
        print(COR_TXT.ERRO, "Esse campeonato precisa de pelo menos 2 equipes.", COR_TXT.NORMAL)
        return

    time_escolhido = escolher_time(times)
    temporada = 2026
    classificados = list(times)
    random.shuffle(classificados)
    salvar_jogo(campeonato, time_escolhido, temporada, classificados)
    rodar_temporada(campeonato, time_escolhido, temporada, classificados, times)


def carregar_jogo(equipes):
    dados = carregar_jogo_salvo()
    if dados is None:
        print(COR_TXT.ATENCAO, "Nenhum jogo salvo encontrado.", COR_TXT.NORMAL)
        return

    campeonato = dados["campeonato"]
    times = equipes.get(campeonato, [])
    historico = dados.get("historico", [])
    rodar_temporada(
        campeonato, dados["time_escolhido"], dados["temporada"], dados["classificados"], times, historico
    )


def editar_equipes(equipes):
    while True:
        campeonato = escolher_campeonato(equipes)
        times = equipes[campeonato]

        while True:
            print(f"\n--- Equipes: {campeonato} ---")
            for indice, nome in enumerate(times, start=1):
                print(f"{indice} - {nome}")
            print("\na - Adicionar equipe")
            print("r - Remover equipe")
            print("n - Renomear equipe")
            print("v - Voltar")
            opcao = input("> ").strip().lower()

            if opcao == "a":
                nome_novo = input("Nome da nova equipe: ").strip()
                if not nome_novo:
                    print(COR_TXT.ERRO, "Nome vazio não é permitido.", COR_TXT.NORMAL)
                elif nome_novo in times:
                    print(COR_TXT.ERRO, "Essa equipe já existe.", COR_TXT.NORMAL)
                else:
                    times.append(nome_novo)
                    salvar_equipes(equipes)
            elif opcao == "r":
                if not times:
                    print(COR_TXT.ERRO, "Não há equipes para remover.", COR_TXT.NORMAL)
                else:
                    indice = escolher_numero("Número da equipe a remover: ", 1, len(times))
                    removida = times.pop(indice - 1)
                    salvar_equipes(equipes)
                    print(f"Equipe '{removida}' removida.")
            elif opcao == "n":
                if not times:
                    print(COR_TXT.ERRO, "Não há equipes para renomear.", COR_TXT.NORMAL)
                else:
                    indice = escolher_numero("Número da equipe a renomear: ", 1, len(times))
                    nome_novo = input("Novo nome: ").strip()
                    if nome_novo:
                        times[indice - 1] = nome_novo
                        salvar_equipes(equipes)
                    else:
                        print(COR_TXT.ERRO, "Nome vazio não é permitido.", COR_TXT.NORMAL)
            elif opcao == "v":
                break
            else:
                print(COR_TXT.ERRO, "Opção inválida.", COR_TXT.NORMAL)

        continuar = input("\nEditar outro campeonato? (s/n): ").strip().lower()
        if continuar != "s":
            break


def menu_principal():
    equipes = carregar_equipes()

    while True:
        dados_salvos = carregar_jogo_salvo()
        if dados_salvos:
            print(
                f"\nCarreira atual: {dados_salvos['time_escolhido']} — "
                f"{dados_salvos['campeonato']} — Temporada {dados_salvos['temporada']}"
            )

        print("\n=== Simulador de Copa ===")
        print("1 - Novo jogo")
        print("2 - Carregar jogo")
        print("3 - Editar equipes")
        print("4 - Sair")
        opcao = input("> ").strip()

        if opcao == "1":
            novo_jogo(equipes)
        elif opcao == "2":
            carregar_jogo(equipes)
        elif opcao == "3":
            editar_equipes(equipes)
        elif opcao == "4":
            print("Até a próxima!")
            break
        else:
            print(COR_TXT.ERRO, "Opção inválida.", COR_TXT.NORMAL)


if __name__ == '__main__':
    menu_principal()
