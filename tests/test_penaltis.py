import random

from penaltis import cobranca_time_a, cobranca_time_b, criar_disputa, disputa_penaltis


def test_disputa_nunca_termina_empatada():
    """Não existe empate em pênaltis: a disputa segue em morte súbita até
    haver um vencedor, então gols_a e gols_b nunca podem ser iguais no final.
    """
    for _ in range(200):
        _, gols_a, gols_b = disputa_penaltis("Time A", "Time B", interativo=False)
        assert gols_a != gols_b


def test_disputa_encerra_antecipadamente_quando_alcance_e_impossivel(monkeypatch):
    """Se um time abre 3x0 logo nas 3 primeiras cobranças, o adversário só
    tem 2 cobranças restantes (no máximo 2 gols) e não alcança mais a
    diferença de 3 — a disputa deve terminar aí, sem completar as 5 rodadas.
    """
    # Cada rodada faz 4 sorteios (chute e defesa de cada time). Time A sempre
    # acerta (chute != defesa do goleiro) e Time B sempre é defendido
    # (chute == defesa do goleiro).
    valores = iter([1, 2, 1, 1] * 3)
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    vencedor, gols_a, gols_b = disputa_penaltis("Time A", "Time B", interativo=False)

    assert vencedor == "Time A"
    assert (gols_a, gols_b) == (3, 0)


def test_disputa_retorna_um_dos_times_como_vencedor():
    vencedor, _, _ = disputa_penaltis("Time A", "Time B", interativo=False)
    assert vencedor in ("Time A", "Time B")


def test_criar_disputa_estado_inicial():
    estado = criar_disputa("Time A", "Time B")

    assert estado == {
        "time_a": "Time A",
        "time_b": "Time B",
        "gols_a": 0,
        "gols_b": 0,
        "cobranca": 0,
        "sequencia_a": [],
        "sequencia_b": [],
        "terminada": False,
        "vencedor": None,
    }


def test_cobranca_time_a_aceita_canto_explicito_e_sorteia_so_a_defesa(monkeypatch):
    estado = criar_disputa("Time A", "Time B")
    monkeypatch.setattr(random, "randint", lambda a, b: 2)  # defesa do goleiro do Time B

    resultado = cobranca_time_a(estado, canto=1)

    assert resultado == {"chute": 1, "defesa": 2, "gol": True}
    assert estado["cobranca"] == 1
    assert estado["gols_a"] == 1
    assert estado["sequencia_a"] == ["🟢"]
    assert estado["sequencia_b"] == []
    assert estado["terminada"] is False


def test_cobranca_time_a_registra_defesa_quando_goleiro_acerta_o_canto(monkeypatch):
    estado = criar_disputa("Time A", "Time B")
    monkeypatch.setattr(random, "randint", lambda a, b: 1)  # defesa no mesmo canto do chute

    resultado = cobranca_time_a(estado, canto=1)

    assert resultado == {"chute": 1, "defesa": 1, "gol": False}
    assert estado["gols_a"] == 0
    assert estado["sequencia_a"] == ["🔴"]


def test_cobranca_time_b_aceita_canto_explicito_para_a_defesa_do_goleiro(monkeypatch):
    estado = criar_disputa("Time A", "Time B")
    monkeypatch.setattr(random, "randint", lambda a, b: 1)  # chute do Time B

    resultado = cobranca_time_b(estado, canto=1)  # goleiro pula pro mesmo canto

    assert resultado == {"chute": 1, "defesa": 1, "gol": False}
    assert estado["cobranca"] == 0  # só cobranca_time_a incrementa a rodada
    assert estado["gols_b"] == 0
    assert estado["sequencia_b"] == ["🔴"]
    assert estado["sequencia_a"] == []


def test_cobranca_time_b_marca_gol_quando_goleiro_erra_o_canto(monkeypatch):
    estado = criar_disputa("Time A", "Time B")
    monkeypatch.setattr(random, "randint", lambda a, b: 1)  # chute do Time B

    resultado = cobranca_time_b(estado, canto=2)  # goleiro pula pro canto errado

    assert resultado == {"chute": 1, "defesa": 2, "gol": True}
    assert estado["gols_b"] == 1
    assert estado["sequencia_b"] == ["🟢"]


def test_corte_antecipado_com_cobranca_time_a_e_time_b(monkeypatch):
    """Mesmo cenário do teste de corte antecipado de `disputa_penaltis`, mas
    dirigindo a disputa diretamente pelas funções passo a passo.
    """
    valores = iter([1, 2, 1, 1] * 3)
    monkeypatch.setattr(random, "randint", lambda a, b: next(valores))

    estado = criar_disputa("Time A", "Time B")
    while not estado["terminada"]:
        cobranca_time_a(estado)
        if estado["terminada"]:
            break
        cobranca_time_b(estado)

    assert estado["vencedor"] == "Time A"
    assert (estado["gols_a"], estado["gols_b"]) == (3, 0)
    assert estado["cobranca"] == 3


def test_disputa_via_funcoes_passo_a_passo_nunca_termina_empatada():
    for _ in range(200):
        estado = criar_disputa("Time A", "Time B")
        while not estado["terminada"]:
            cobranca_time_a(estado)
            if estado["terminada"]:
                break
            cobranca_time_b(estado)

        assert estado["gols_a"] != estado["gols_b"]
        assert estado["vencedor"] in ("Time A", "Time B")
