from campeonato import montar_confrontos_fase, sortear_classificados
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

    pares_resolvidos = {(time_a, time_b) for time_a, time_b, _, _, _ in confrontos_resolvidos}
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
        montar_confrontos_fase(classificados, time_escolhido="B")
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
