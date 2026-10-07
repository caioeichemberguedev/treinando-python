import json

from campeonato import (
    montar_classificacao,
    montar_confrontos_fase,
    registro_da_fase,
    sortear_classificados,
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
