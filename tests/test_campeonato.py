import json
import random

from campeonato import (
    adversario_na_proxima_fase,
    montar_classificacao,
    montar_confrontos_fase,
    registro_da_fase,
    sortear_classificados,
    unificar_time_escolhido,
)
from equipe import Equipe


def test_sortear_classificados_retorna_os_mesmos_times():
    """O sorteio só reordena os times recebidos — não perde nem inventa
    nenhum.
    """
    times = [Equipe("A"), Equipe("B"), Equipe("C"), Equipe("D")]

    classificados = sortear_classificados(times)

    assert sorted(str(time) for time in classificados) == ["A", "B", "C", "D"]


def test_sortear_classificados_nao_altera_lista_original():
    """A função devolve uma cópia embaralhada — a lista recebida continua na
    ordem original.
    """
    times = [Equipe("A"), Equipe("B"), Equipe("C"), Equipe("D")]
    original = list(times)

    sortear_classificados(times)

    assert times == original


def test_montar_confrontos_fase_sem_time_escolhido_resolve_tudo():
    """Fase sem o time do jogador: todos os confrontos voltam resolvidos e
    não há confronto pendente.
    """
    classificados = [Equipe("A"), Equipe("B"), Equipe("C"), Equipe("D")]

    nome_fase, confrontos_resolvidos, confronto_pendente, proximos_parciais = (
        montar_confrontos_fase(classificados, time_escolhido=None, campeonato="Liga X")
    )

    assert nome_fase == "Semifinal - Liga X"
    assert confronto_pendente is None
    assert len(confrontos_resolvidos) == 2
    assert len(proximos_parciais) == 2

    pares_resolvidos = {
        (time_a.nome, time_b.nome) for time_a, time_b, _, _, _ in confrontos_resolvidos
    }
    assert pares_resolvidos == {("A", "B"), ("C", "D")}

    for time_a, time_b, vencedor, gols_a, gols_b in confrontos_resolvidos:
        assert vencedor in (time_a, time_b)
        assert vencedor in proximos_parciais


def test_montar_confrontos_fase_com_time_escolhido_deixa_so_seu_par_pendente():
    """Só o confronto do time do jogador fica pendente; os demais são
    resolvidos automaticamente.
    """
    time_a, time_b, time_c, time_d = Equipe("A"), Equipe("B"), Equipe("C"), Equipe("D")
    classificados = [time_a, time_b, time_c, time_d]

    nome_fase, confrontos_resolvidos, confronto_pendente, proximos_parciais = (
        montar_confrontos_fase(classificados, time_escolhido=time_b)
    )

    assert nome_fase == "Semifinal"
    assert confronto_pendente == (time_a, time_b)
    assert len(confrontos_resolvidos) == 1
    assert confrontos_resolvidos[0][0] == time_c
    assert confrontos_resolvidos[0][1] == time_d
    assert len(proximos_parciais) == 1
    assert proximos_parciais[0] in (time_c, time_d)


def test_montar_confrontos_fase_numero_impar_da_bye_para_ultimo_classificado():
    """Com número ímpar de classificados, o último time avança direto (bye)
    para a próxima fase, igual ao que `gerar_rodadas` já faz.
    """
    time_a, time_b, time_c = Equipe("A"), Equipe("B"), Equipe("C")
    classificados = [time_a, time_b, time_c]

    nome_fase, confrontos_resolvidos, confronto_pendente, proximos_parciais = (
        montar_confrontos_fase(classificados, time_escolhido=None)
    )

    assert confronto_pendente is None
    assert len(confrontos_resolvidos) == 1
    assert confrontos_resolvidos[0][0] == time_a
    assert confrontos_resolvidos[0][1] == time_b
    assert len(proximos_parciais) == 2
    assert time_c in proximos_parciais


def test_montar_confrontos_fase_bye_nao_afeta_lista_original_de_classificados():
    """A função não deve alterar a lista `classificados` recebida (trabalha
    sobre uma cópia interna).
    """
    classificados = [Equipe("A"), Equipe("B"), Equipe("C")]
    original = list(classificados)

    montar_confrontos_fase(classificados, time_escolhido=None)

    assert classificados == original


def _confrontos_de_semifinal():
    """Dois confrontos já resolvidos entre times de teste (ids 901-904),
    no formato de `gerar_rodadas`: (time_a, time_b, vencedor, gols_a, gols_b).
    """
    time_a = Equipe("Time A", id=901)
    time_b = Equipe("Time B", id=902)
    time_c = Equipe("Time C", id=903)
    time_d = Equipe("Time D", id=904)
    return [
        (time_a, time_b, time_a, 4, 2),
        (time_c, time_d, time_d, 3, 5),
    ]


def test_registro_da_fase_troca_equipes_por_ids():
    """Cada confronto vira uma lista [id_a, id_b, id_vencedor, gols_a, gols_b]."""
    confrontos = _confrontos_de_semifinal()

    registro = registro_da_fase("Semifinal - Liga X", confrontos)

    assert registro == {
        "nome_fase": "Semifinal - Liga X",
        "confrontos": [
            [901, 902, 901, 4, 2],
            [903, 904, 904, 3, 5],
        ],
    }


def test_registro_da_fase_sobrevive_ida_e_volta_pelo_json():
    """O registro já sai no formato do JSON (listas, não tuplas): gravar e
    ler de volta não muda nada.
    """
    registro = registro_da_fase("Semifinal", _confrontos_de_semifinal())

    assert json.loads(json.dumps(registro)) == registro


def test_registro_da_fase_nao_altera_confrontos_recebidos():
    """A lista de confrontos recebida continua igual (mesmos objetos)."""
    confrontos = _confrontos_de_semifinal()
    original = list(confrontos)

    registro_da_fase("Semifinal", confrontos)

    assert len(confrontos) == len(original)
    for recebido, esperado in zip(confrontos, original):
        assert recebido is esperado


def test_montar_classificacao_funciona_com_registro_em_ids():
    """`montar_classificacao` aceita o histórico gravado com ids."""
    time_a = Equipe("Time A", id=901)
    time_b = Equipe("Time B", id=902)
    time_c = Equipe("Time C", id=903)
    time_d = Equipe("Time D", id=904)
    semifinal = [(time_a, time_b, time_a, 4, 2), (time_c, time_d, time_d, 3, 5)]
    final = [(time_a, time_d, time_d, 2, 4)]

    fases = [
        registro_da_fase("Semifinal - Liga X", semifinal),
        registro_da_fase("Final - Liga X", final),
    ]

    assert montar_classificacao(fases) == [
        ("Campeão", [904]),
        ("Vice-campeão", [901]),
        ("Semifinal", [902, 903]),
    ]


def _times(*nomes):
    """Cria uma `Equipe` por nome, com ids 1, 2, 3... na ordem recebida."""
    return [Equipe(nome, id=indice) for indice, nome in enumerate(nomes, start=1)]


def test_adversario_na_proxima_fase_quatro_times_pares_consecutivos():
    """Com 4 times, C enfrenta D e D enfrenta C, na Semifinal."""
    time_a, time_b, time_c, time_d = _times("A", "B", "C", "D")
    classificados = [time_a, time_b, time_c, time_d]

    assert adversario_na_proxima_fase(classificados, time_c) == ("Semifinal", time_d)
    assert adversario_na_proxima_fase(classificados, time_d) == ("Semifinal", time_c)


def test_adversario_na_proxima_fase_acrescenta_sufixo_do_campeonato():
    """O nome da fase ganha o sufixo " - <campeonato>", como no histórico."""
    time_a, time_b, time_c, time_d = _times("A", "B", "C", "D")

    resultado = adversario_na_proxima_fase(
        [time_a, time_b, time_c, time_d], time_c, campeonato="Copa X"
    )

    assert resultado == ("Semifinal - Copa X", time_d)


def test_adversario_na_proxima_fase_tres_times_ultimo_ganha_bye():
    """Com 3 times, o último avança direto (adversário `None`) e os outros
    dois se enfrentam na Final.
    """
    time_a, time_b, time_c = _times("A", "B", "C")
    classificados = [time_a, time_b, time_c]

    assert adversario_na_proxima_fase(classificados, time_c) == ("Final", None)
    assert adversario_na_proxima_fase(classificados, time_a) == ("Final", time_b)


def test_adversario_na_proxima_fase_time_fora_da_lista_devolve_none():
    """Time que não está nos classificados (ex.: eliminado) não tem próximo
    adversário.
    """
    time_a, time_b, time_c, time_d = _times("A", "B", "C", "D")

    assert adversario_na_proxima_fase([time_a, time_b, time_c], time_d) is None


def test_adversario_na_proxima_fase_lista_com_um_time_ou_vazia_devolve_none():
    """Sem pelo menos 2 times não há fase a jogar."""
    (time_a,) = _times("A")

    assert adversario_na_proxima_fase([time_a], time_a) is None
    assert adversario_na_proxima_fase([], time_a) is None


def test_adversario_na_proxima_fase_nao_altera_lista_recebida():
    """A função trabalha sobre uma cópia — nem o bye mexe na lista original."""
    classificados = _times("A", "B", "C")
    original = list(classificados)

    adversario_na_proxima_fase(classificados, classificados[0])
    adversario_na_proxima_fase(classificados, classificados[-1])

    assert classificados == original
    assert all(antes is depois for antes, depois in zip(original, classificados))


def test_adversario_na_proxima_fase_compara_equipes_pelo_id():
    """O time do jogador pode ser outro objeto `Equipe` com o mesmo id (ex.:
    depois de carregar um save) — continua sendo encontrado.
    """
    time_a, time_b, time_c, time_d = _times("A", "B", "C", "D")
    copia_de_c = Equipe("C renomeado", id=time_c.id)

    resultado = adversario_na_proxima_fase([time_a, time_b, time_c, time_d], copia_de_c)

    assert resultado == ("Semifinal", time_d)


def test_adversario_na_proxima_fase_bate_com_confronto_pendente_real():
    """Para listas de 2 a 9 times e o jogador em cada posição, o adversário
    previsto é o outro time do `confronto_pendente` de
    `montar_confrontos_fase`, com o mesmo nome de fase; e adversário `None`
    corresponde a não haver pendente (jogador no bye).
    """
    random.seed(19)

    for total in range(2, 10):
        for posicao in range(total):
            classificados = sortear_classificados(
                _times(*(f"T{numero}" for numero in range(1, total + 1)))
            )
            jogador = classificados[posicao]

            previsto = adversario_na_proxima_fase(classificados, jogador, campeonato="Copa X")
            nome_fase, _, confronto_pendente, _ = montar_confrontos_fase(
                classificados, time_escolhido=jogador, campeonato="Copa X"
            )

            nome_previsto, adversario = previsto
            assert nome_previsto == nome_fase
            if confronto_pendente is None:
                assert adversario is None
                assert jogador == classificados[-1]
            else:
                time_a, time_b = confronto_pendente
                assert jogador in (time_a, time_b)
                esperado = time_b if time_a == jogador else time_a
                assert adversario == esperado


def test_adversario_na_proxima_fase_bate_com_fluxo_web_jogador_no_fim_de_proximos():
    """Reproduz a ordem do fluxo web: os confrontos resolvidos entram em
    `proximos` na ordem do chaveamento, depois o bye, e só por último o
    vencedor do confronto do jogador (`_concluir_disputa_penaltis`). Prevendo
    sobre essa lista `proximos`, o adversário/fase previstos são os que a
    fase seguinte (`montar_confrontos_fase(proximos, ...)`) de fato monta,
    fase após fase, até o fim da temporada ou a eliminação do jogador.
    """
    for semente in range(40):
        random.seed(semente)
        for total in range(2, 17):
            classificados = sortear_classificados(
                _times(*(f"T{numero}" for numero in range(1, total + 1)))
            )
            jogador = random.choice(classificados)

            while len(classificados) >= 2:
                previsto = adversario_na_proxima_fase(classificados, jogador, campeonato="Copa X")
                nome_fase, _, pendente, proximos = montar_confrontos_fase(
                    classificados, time_escolhido=jogador, campeonato="Copa X"
                )

                if jogador not in classificados:
                    assert previsto is None
                    assert pendente is None
                else:
                    assert previsto is not None
                    assert previsto[0] == nome_fase
                    if pendente is None:
                        assert previsto[1] is None
                    else:
                        time_a, time_b = pendente
                        esperado = time_b if time_a == jogador else time_a
                        assert previsto[1] == esperado
                        # Web: vencedor do confronto do jogador vai para o FIM.
                        proximos = proximos + [random.choice(pendente)]

                classificados = proximos


def test_unificar_time_escolhido_troca_pelo_proprio_objeto_escolhido():
    """O elemento de mesmo id vira o próprio `time_escolhido` (identidade,
    não só igualdade), e os demais seguem os mesmos objetos."""
    time_a, time_b, time_c = _times("A", "B", "C")
    escolhido = Equipe("B (retrato da carreira)", id=2, titulos=2)

    unificada = unificar_time_escolhido(escolhido, [time_a, time_b, time_c])

    assert unificada[1] is escolhido
    assert unificada[1] is not time_b
    assert unificada[0] is time_a
    assert unificada[2] is time_c


def test_unificar_time_escolhido_mantem_a_ordem():
    time_a, time_b, time_c, time_d = _times("A", "B", "C", "D")
    escolhido = Equipe("C", id=3)

    unificada = unificar_time_escolhido(escolhido, [time_d, time_c, time_b, time_a])

    assert [time.id for time in unificada] == [4, 3, 2, 1]
    assert unificada[1] is escolhido


def test_unificar_time_escolhido_nao_altera_lista_recebida():
    time_a, time_b = _times("A", "B")
    times = [time_a, time_b]
    escolhido = Equipe("A", id=1)

    unificada = unificar_time_escolhido(escolhido, times)

    assert unificada is not times
    assert times[0] is time_a
    assert times[1] is time_b


def test_unificar_time_escolhido_com_none_devolve_none():
    assert unificar_time_escolhido(Equipe("A", id=1), None) is None


def test_unificar_time_escolhido_sem_o_time_devolve_copia_igual():
    time_a, time_b = _times("A", "B")
    times = [time_a, time_b]

    unificada = unificar_time_escolhido(Equipe("Z", id=99), times)

    assert unificada is not times
    assert all(novo is antigo for novo, antigo in zip(unificada, times))
    assert len(unificada) == 2
