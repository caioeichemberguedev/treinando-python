"""Testes do esquema da migração 001 (E-013-T2).

O script é aplicado direto com `executescript` numa conexão em memória,
sem passar por `dados.migrar` — assim estes testes valem só para o SQL.
"""

import sqlite3
from pathlib import Path

import pytest

ARQUIVO_001 = (
    Path(__file__).resolve().parents[2] / "dados" / "migracoes" / "001_inicial.sql"
)

TABELAS_ESPERADAS = {
    "times", "carreira", "classificados", "temporadas", "fases", "confrontos",
}
INDICES_ESPERADOS = {"idx_fases_temporada", "idx_confrontos_fase"}


@pytest.fixture
def banco():
    """Conexão em memória com chaves estrangeiras ligadas e a 001 aplicada."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(ARQUIVO_001.read_text(encoding="utf-8"))
    yield conn
    conn.close()


def _inserir_time(conn, id_time, *, financas=100, fas=50, titulos=0,
                  forca=70, cores='["#FF0000", "#FFFFFF"]'):
    conn.execute(
        "INSERT INTO times (id, nome, financas, fas, titulos, forca, cores) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (id_time, f"Time {id_time}", financas, fas, titulos, forca, cores),
    )


def _inserir_carreira(conn, *, id_carreira=1, sorteado=1, time_id=1):
    conn.execute(
        "INSERT INTO carreira (id, campeonato, temporada, time_escolhido_id, "
        "chaveamento_sorteado) VALUES (?, ?, ?, ?, ?)",
        (id_carreira, "Copa do Brasil", 2026, time_id, sorteado),
    )


def _inserir_temporada(conn, ano=2026, campeao_id=1):
    cursor = conn.execute(
        "INSERT INTO temporadas (ano, campeao_id) VALUES (?, ?)",
        (ano, campeao_id),
    )
    return cursor.lastrowid


def _inserir_fase(conn, temporada_id, ordem=1, nome="Final"):
    cursor = conn.execute(
        "INSERT INTO fases (temporada_id, ordem, nome) VALUES (?, ?, ?)",
        (temporada_id, ordem, nome),
    )
    return cursor.lastrowid


def _inserir_confronto(conn, fase_id, *, ordem=1, time_a=1, time_b=2,
                       vencedor=1, gols_a=5, gols_b=4):
    conn.execute(
        "INSERT INTO confrontos (fase_id, ordem, time_a_id, time_b_id, "
        "vencedor_id, gols_a, gols_b) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fase_id, ordem, time_a, time_b, vencedor, gols_a, gols_b),
    )


def _contar(conn, tabela):
    # `tabela` vem sempre de constantes do próprio teste, nunca de entrada.
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


# --- estrutura ---------------------------------------------------------------

def test_cria_exatamente_as_seis_tabelas(banco):
    nomes = {
        linha[0] for linha in banco.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert nomes == TABELAS_ESPERADAS


def test_cria_os_dois_indices(banco):
    nomes = {
        linha[0] for linha in banco.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert nomes == INDICES_ESPERADOS


def test_arquivo_nao_controla_transacao_nem_versao():
    texto = ARQUIVO_001.read_text(encoding="utf-8").upper()
    for proibido in ("BEGIN", "COMMIT", "USER_VERSION"):
        assert proibido not in texto


def test_script_nao_mexe_no_user_version(banco):
    assert banco.execute("PRAGMA user_version").fetchone()[0] == 0


# --- linhas válidas ------------------------------------------------------------

def test_aceita_uma_linha_valida_de_cada_tabela(banco):
    _inserir_time(banco, 1)
    _inserir_time(banco, 2, cores=None)
    _inserir_carreira(banco)
    banco.execute(
        "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)", (1, 1)
    )
    temporada_id = _inserir_temporada(banco)
    fase_id = _inserir_fase(banco, temporada_id)
    _inserir_confronto(banco, fase_id)

    for tabela in TABELAS_ESPERADAS:
        assert _contar(banco, tabela) >= 1


def test_cores_aceita_null(banco):
    _inserir_time(banco, 1, cores=None)
    cores = banco.execute("SELECT cores FROM times WHERE id = ?", (1,)).fetchone()[0]
    assert cores is None


def test_titulos_tem_default_zero(banco):
    banco.execute(
        "INSERT INTO times (id, nome, financas, fas, forca) VALUES (?, ?, ?, ?, ?)",
        (1, "Sem títulos", 10, 10, 50),
    )
    titulos = banco.execute(
        "SELECT titulos FROM times WHERE id = ?", (1,)
    ).fetchone()[0]
    assert titulos == 0


def test_aceita_limites_de_forca(banco):
    _inserir_time(banco, 1, forca=0)
    _inserir_time(banco, 2, forca=100)
    assert _contar(banco, "times") == 2


def test_aceita_carreira_sem_chaveamento_sorteado(banco):
    _inserir_time(banco, 1)
    _inserir_carreira(banco, sorteado=0)
    assert _contar(banco, "carreira") == 1


def test_historico_aceita_time_fora_da_tabela_times(banco):
    # Os ids de time do histórico não têm chave estrangeira: times eliminados
    # em temporadas antigas não estão na tabela times.
    temporada_id = _inserir_temporada(banco, campeao_id=31)
    fase_id = _inserir_fase(banco, temporada_id)
    _inserir_confronto(banco, fase_id, time_a=31, time_b=32, vencedor=31)
    assert _contar(banco, "confrontos") == 1


# --- restrições ----------------------------------------------------------------

def test_rejeita_forca_acima_de_100(banco):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_time(banco, 1, forca=101)


def test_rejeita_fas_negativo(banco):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_time(banco, 1, fas=-1)


def test_rejeita_segunda_linha_de_carreira(banco):
    _inserir_time(banco, 1)
    _inserir_carreira(banco)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_carreira(banco, id_carreira=2)


def test_rejeita_chaveamento_sorteado_fora_de_0_e_1(banco):
    _inserir_time(banco, 1)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_carreira(banco, sorteado=2)


def test_rejeita_carreira_com_time_escolhido_inexistente(banco):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_carreira(banco, time_id=999)


def test_rejeita_classificado_com_time_inexistente(banco):
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)",
            (1, 999),
        )


def test_rejeita_mesmo_time_duas_vezes_nos_classificados(banco):
    _inserir_time(banco, 1)
    banco.execute(
        "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)", (1, 1)
    )
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)",
            (2, 1),
        )


def test_rejeita_confronto_com_gols_negativos(banco):
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, gols_a=-1)


def test_rejeita_time_contra_ele_mesmo(banco):
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, time_a=1, time_b=1, vencedor=1)


def test_rejeita_vencedor_que_nao_jogou(banco):
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, time_a=1, time_b=2, vencedor=3)


def test_rejeita_duas_temporadas_com_o_mesmo_ano(banco):
    _inserir_temporada(banco, ano=2026)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_temporada(banco, ano=2026)


def test_rejeita_fase_de_temporada_inexistente(banco):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(banco, temporada_id=999)


def test_rejeita_confronto_de_fase_inexistente(banco):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id=999)


# --- cascata -------------------------------------------------------------------

def test_apagar_temporadas_apaga_fases_e_confrontos(banco):
    for ano in (2026, 2027):
        temporada_id = _inserir_temporada(banco, ano=ano)
        for ordem in (1, 2):
            fase_id = _inserir_fase(banco, temporada_id, ordem=ordem)
            _inserir_confronto(banco, fase_id, ordem=1)
            _inserir_confronto(banco, fase_id, ordem=2, time_a=3, time_b=4,
                               vencedor=4)
    assert _contar(banco, "fases") == 4
    assert _contar(banco, "confrontos") == 8

    banco.execute("DELETE FROM temporadas")

    assert _contar(banco, "temporadas") == 0
    assert _contar(banco, "fases") == 0
    assert _contar(banco, "confrontos") == 0


# --- casos de borda (game-tester) ----------------------------------------------

@pytest.mark.parametrize("campo, valor", [
    ("financas", -1),
    ("titulos", -1),
    ("forca", -1),
])
def test_rejeita_valores_negativos_em_times(banco, campo, valor):
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_time(banco, 1, **{campo: valor})


def test_aceita_valores_zerados_em_times(banco):
    _inserir_time(banco, 1, financas=0, fas=0, titulos=0, forca=0)
    assert _contar(banco, "times") == 1


def test_rejeita_temporada_zero_na_carreira(banco):
    _inserir_time(banco, 1)
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO carreira (id, campeonato, temporada, time_escolhido_id, "
            "chaveamento_sorteado) VALUES (?, ?, ?, ?, ?)",
            (1, "Copa do Brasil", 0, 1, 1),
        )


def test_rejeita_classificado_na_posicao_zero(banco):
    _inserir_time(banco, 1)
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)", (0, 1)
        )


def test_rejeita_fase_com_ordem_zero_ou_repetida(banco):
    temporada_id = _inserir_temporada(banco)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(banco, temporada_id, ordem=0)
    _inserir_fase(banco, temporada_id, ordem=1)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_fase(banco, temporada_id, ordem=1, nome="Outra")


def test_mesma_ordem_de_fase_em_temporadas_diferentes(banco):
    _inserir_fase(banco, _inserir_temporada(banco, ano=2026), ordem=1)
    _inserir_fase(banco, _inserir_temporada(banco, ano=2027), ordem=1)
    assert _contar(banco, "fases") == 2


def test_rejeita_confronto_com_ordem_zero_ou_repetida(banco):
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, ordem=0)
    _inserir_confronto(banco, fase_id, ordem=1)
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, ordem=1, time_a=3, time_b=4,
                           vencedor=3)


def test_aceita_placar_empatado_e_zerado(banco):
    # Empate no tempo normal decidido nos pênaltis: o vencedor vem à parte.
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    _inserir_confronto(banco, fase_id, gols_a=0, gols_b=0, vencedor=2)
    assert _contar(banco, "confrontos") == 1


def test_rejeita_gols_b_negativo(banco):
    fase_id = _inserir_fase(banco, _inserir_temporada(banco))
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_confronto(banco, fase_id, gols_b=-1)


def test_temporada_sem_fases_e_aceita(banco):
    _inserir_temporada(banco)
    assert _contar(banco, "temporadas") == 1
    assert _contar(banco, "fases") == 0


def test_apagar_time_usado_na_carreira_e_bloqueado(banco):
    _inserir_time(banco, 1)
    _inserir_carreira(banco)
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute("DELETE FROM times WHERE id = ?", (1,))
