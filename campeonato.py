from penaltis import disputa_penaltis

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
    jogo novo, ou como estava salva para retomar um jogo em andamento), e seus
    itens são objetos `Equipe` — cada vitória/eliminação atualiza finanças e
    fãs da equipe envolvida.
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

            perdedor = time_b if vencedor == time_a else time_a
            vencedor.registrar_vitoria()
            perdedor.registrar_eliminacao()

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


def montar_classificacao(fases):
    """Reconstrói, a partir das fases de uma temporada, em que rodada cada
    time foi eliminado (campeão e vice tratados à parte, na final).
    Retorna uma lista de (rótulo, [nomes]) da melhor para a pior colocação.
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
