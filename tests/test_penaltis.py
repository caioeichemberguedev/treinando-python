import random

from penaltis import disputa_penaltis


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
