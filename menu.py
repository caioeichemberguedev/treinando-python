import os
import random

from cores import COR_TXT
from equipe import Equipe
from campeonato import gerar_rodadas, exibir_rodada, montar_classificacao
from persistencia import (
    ARQUIVO_SALVO,
    carregar_equipes,
    salvar_equipes,
    salvar_jogo,
    carregar_jogo_salvo,
    restaurar_equipes_padrao,
)


def escolher_valor(mensagem, minimo, maximo=None):
    while True:
        entrada = input(mensagem)
        if entrada.isdigit():
            valor = int(entrada)
            if valor >= minimo and (maximo is None or valor <= maximo):
                return valor
        limite = f" e {maximo}" if maximo is not None else " ou mais"
        print(COR_TXT.ERRO, f"Digite um número inteiro entre {minimo}{limite}.", COR_TXT.NORMAL)


def escolher_numero(mensagem, minimo, maximo):
    return escolher_valor(mensagem, minimo, maximo)


def escolher_campeonato(equipes):
    nomes = list(equipes.keys())
    print("\nEscolha o campeonato:")
    for indice, nome in enumerate(nomes, start=1):
        print(f"{indice} - {nome}")
    escolha = escolher_numero("> ", 1, len(nomes))
    return nomes[escolha - 1]


def escolher_time(times):
    print("\nEscolha seu time:")
    for indice, equipe in enumerate(times, start=1):
        print(
            f"{indice} - {equipe.nome} "
            f"(💰 R$ {equipe.financas:,} | 👥 {equipe.fas:,} fãs | ⚡ {equipe.forca}/100 | 🏆 {equipe.titulos})"
        )
    escolha = escolher_numero("> ", 1, len(times))
    return times[escolha - 1]


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
        fases_da_temporada.append({
            "nome_fase": nome_fase,
            "confrontos": [
                [time_a.nome, time_b.nome, vencedor.nome, gols_a, gols_b]
                for time_a, time_b, vencedor, gols_a, gols_b in confrontos
            ],
        })

        if len(proximos) == 1:
            campeao = proximos[0]
            campeao.sagrar_campea()
            print(f"\n🏆 Campeão da {campeonato} {temporada}:", campeao)
            if time_escolhido == campeao:
                print(COR_TXT.SUCESSO, "🎉 PARABÉNS! Você foi campeão!", COR_TXT.NORMAL)
            else:
                print(COR_TXT.ATENCAO, "😢 Você não foi campeão.", COR_TXT.NORMAL)

            historico = historico + [{
                "temporada": temporada,
                "campeao": campeao.nome,
                "fases": fases_da_temporada,
            }]

            proxima_temporada = temporada + 1
            salvar_jogo(campeonato, time_escolhido, proxima_temporada, None, historico)

            if menu_pos_temporada(campeonato, temporada, campeao.nome, historico):
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


def editar_valores_equipe(equipe):
    while True:
        print(f"\n--- Editar {equipe.nome} ---")
        print(f"1 - Finanças (atual: R$ {equipe.financas:,})")
        print(f"2 - Fãs (atual: {equipe.fas:,})")
        print(f"3 - Força (atual: {equipe.forca}/100)")
        print("v - Voltar")
        opcao = input("> ").strip().lower()

        if opcao == "1":
            equipe.financas = escolher_valor("Novo valor de finanças (R$): ", 0)
        elif opcao == "2":
            equipe.fas = escolher_valor("Novo valor de fãs: ", 0)
        elif opcao == "3":
            equipe.forca = escolher_valor("Nova força (0 a 100): ", 0, 100)
        elif opcao == "v":
            return
        else:
            print(COR_TXT.ERRO, "Opção inválida.", COR_TXT.NORMAL)


def editar_equipes(equipes):
    while True:
        campeonato = escolher_campeonato(equipes)
        times = equipes[campeonato]

        while True:
            print(f"\n--- Equipes: {campeonato} ---")
            for indice, equipe in enumerate(times, start=1):
                print(
                    f"{indice} - {equipe.nome} "
                    f"(💰 R$ {equipe.financas:,} | 👥 {equipe.fas:,} fãs | ⚡ {equipe.forca}/100 | 🏆 {equipe.titulos})"
                )
            print("\na - Adicionar equipe")
            print("r - Remover equipe")
            print("n - Renomear equipe")
            print("e - Editar finanças/fãs/força")
            print("v - Voltar")
            opcao = input("> ").strip().lower()

            if opcao == "a":
                nome_novo = input("Nome da nova equipe: ").strip()
                if not nome_novo:
                    print(COR_TXT.ERRO, "Nome vazio não é permitido.", COR_TXT.NORMAL)
                elif nome_novo in times:
                    print(COR_TXT.ERRO, "Essa equipe já existe.", COR_TXT.NORMAL)
                else:
                    times.append(Equipe(nome_novo))
                    salvar_equipes(equipes)
            elif opcao == "r":
                if not times:
                    print(COR_TXT.ERRO, "Não há equipes para remover.", COR_TXT.NORMAL)
                else:
                    indice = escolher_numero("Número da equipe a remover: ", 1, len(times))
                    removida = times.pop(indice - 1)
                    salvar_equipes(equipes)
                    print(f"Equipe '{removida.nome}' removida.")
            elif opcao == "n":
                if not times:
                    print(COR_TXT.ERRO, "Não há equipes para renomear.", COR_TXT.NORMAL)
                else:
                    indice = escolher_numero("Número da equipe a renomear: ", 1, len(times))
                    nome_novo = input("Novo nome: ").strip()
                    if nome_novo:
                        times[indice - 1].nome = nome_novo
                        salvar_equipes(equipes)
                    else:
                        print(COR_TXT.ERRO, "Nome vazio não é permitido.", COR_TXT.NORMAL)
            elif opcao == "e":
                if carregar_jogo_salvo() is not None:
                    print(
                        COR_TXT.ERRO,
                        "Não é possível editar finanças/fãs/força com uma carreira em andamento. "
                        "Esses valores só mudam automaticamente conforme o jogador avança na carreira salva.",
                        COR_TXT.NORMAL,
                    )
                elif not times:
                    print(COR_TXT.ERRO, "Não há equipes para editar.", COR_TXT.NORMAL)
                else:
                    indice = escolher_numero("Número da equipe a editar: ", 1, len(times))
                    editar_valores_equipe(times[indice - 1])
                    salvar_equipes(equipes)
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
        print("4 - Restaurar equipes para os valores padrão")
        print("5 - Sair")
        opcao = input("> ").strip()

        if opcao == "1":
            novo_jogo(equipes)
        elif opcao == "2":
            carregar_jogo(equipes)
        elif opcao == "3":
            editar_equipes(equipes)
        elif opcao == "4":
            confirmacao = input(
                "Isso vai apagar todas as edições de elenco, finanças, fãs e força feitas até agora "
                "(o jogo salvo em andamento não é afetado). Confirmar? (s/n): "
            ).strip().lower()
            if confirmacao == "s":
                equipes = restaurar_equipes_padrao()
                print(COR_TXT.SUCESSO, "Equipes restauradas para os valores padrão.", COR_TXT.NORMAL)
            else:
                print("Restauração cancelada.")
        elif opcao == "5":
            print("Até a próxima!")
            break
        else:
            print(COR_TXT.ERRO, "Opção inválida.", COR_TXT.NORMAL)
