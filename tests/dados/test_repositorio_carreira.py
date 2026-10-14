"""Testes do repositório da carreira (`dados/repositorios/carreira.py`)."""

import inspect
import re
import sqlite3

import pytest

from dados.repositorios import carreira as repo
from dados.repositorios.carreira import gravar_carreira, ler_carreira
from equipe import Equipe


def _campos(time):
    return (time.id, time.nome, time.financas, time.fas, time.titulos, time.forca, time.cores)


def _time(id_time, nome, financas=1_000, fas=200, titulos=0, forca=50, cores=None):
    return Equipe(nome, financas, fas, titulos, forca, cores, id=id_time)


_CONTAGENS = {
    "times": "SELECT COUNT(*) FROM times",
    "carreira": "SELECT COUNT(*) FROM carreira",
    "classificados": "SELECT COUNT(*) FROM classificados",
}


def _contar(conn, tabela):
    return conn.execute(_CONTAGENS[tabela]).fetchone()[0]


def test_ida_e_volta_preserva_campos_e_ordem(conn):
    escolhido = _time(1, "São Paulo", 5_000, 300, 2, 80, ["#FF0000", "#FFFFFF", "#000000"])
    classificados = [
        _time(3, "Grêmio", 3_000, 100, 1, 70, ["#0000FF"]),
        _time(1, "São Paulo", 5_000, 300, 2, 80, ["#FF0000", "#FFFFFF", "#000000"]),
        _time(2, "D'Alessandro FC", 2_000, 50, 0, 40, None),
    ]
    gravar_carreira(conn, "Copa do Brasil", 2027, escolhido, classificados)

    lido = ler_carreira(conn)

    assert lido["campeonato"] == "Copa do Brasil"
    assert lido["temporada"] == 2027
    assert _campos(lido["time_escolhido"]) == _campos(escolhido)
    assert [t.id for t in lido["classificados"]] == [3, 1, 2]
    assert [_campos(t) for t in lido["classificados"]] == [_campos(t) for t in classificados]
    assert all(isinstance(t, Equipe) for t in lido["classificados"])


def test_classificados_none_e_cores_none_voltam_none(conn):
    gravar_carreira(conn, "Copa do Mundo 2026", 2026, _time(17, "Brasil", cores=None), None)

    lido = ler_carreira(conn)

    assert lido["classificados"] is None
    assert lido["time_escolhido"].cores is None
    assert conn.execute("SELECT chaveamento_sorteado FROM carreira").fetchone()[0] == 0


def test_lista_vazia_de_classificados_volta_lista_vazia(conn):
    gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), [])

    assert ler_carreira(conn)["classificados"] == []


def test_escolhido_eliminado_volta_com_o_proprio_retrato(conn):
    escolhido = _time(1, "São Paulo", financas=777, fas=11)
    gravar_carreira(conn, "Copa do Brasil", 2026, escolhido, [_time(2, "Santos"), _time(3, "Grêmio")])

    lido = ler_carreira(conn)

    assert _campos(lido["time_escolhido"]) == _campos(escolhido)
    assert [t.id for t in lido["classificados"]] == [2, 3]


def test_escolhido_classificado_vale_o_retrato_do_classificado(conn):
    escolhido = _time(1, "São Paulo", financas=1_000)
    classificado = _time(1, "São Paulo", financas=9_999)
    gravar_carreira(conn, "Copa do Brasil", 2026, escolhido, [_time(2, "Santos"), classificado])

    lido = ler_carreira(conn)
    escolhido_lido = lido["time_escolhido"]
    classificado_lido = lido["classificados"][1]

    assert escolhido_lido.financas == 9_999
    assert classificado_lido.financas == 9_999
    assert escolhido_lido is not classificado_lido
    assert escolhido_lido == classificado_lido
    assert _contar(conn, "times") == 2


def test_gravar_de_novo_com_menos_classificados_nao_deixa_sobra(conn):
    gravar_carreira(
        conn, "Copa do Brasil", 2026, _time(1, "São Paulo"),
        [_time(i, f"Time {i}") for i in range(1, 9)],
    )
    gravar_carreira(
        conn, "Copa do Brasil", 2026, _time(1, "São Paulo"),
        [_time(5, "Time 5"), _time(1, "São Paulo")],
    )

    assert _contar(conn, "carreira") == 1
    assert _contar(conn, "classificados") == 2
    assert _contar(conn, "times") == 2
    ids_times = [linha[0] for linha in conn.execute("SELECT id FROM times ORDER BY id")]
    assert ids_times == [1, 5]
    assert [t.id for t in ler_carreira(conn)["classificados"]] == [5, 1]


def test_sem_linha_de_carreira_devolve_none(conn):
    assert ler_carreira(conn) is None


def test_time_sem_id_levanta_value_error_e_nao_grava_nada(conn):
    gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), [_time(2, "Santos")])
    conn.commit()

    with pytest.raises(ValueError, match="Time sem id não pode ser salvo na carreira: Sem Id"):
        with conn:
            gravar_carreira(conn, "Copa do Mundo 2026", 2030, _time(1, "São Paulo"), [Equipe("Sem Id")])

    lido = ler_carreira(conn)
    assert lido["campeonato"] == "Copa do Brasil"
    assert lido["temporada"] == 2026
    assert [t.id for t in lido["classificados"]] == [2]


def test_escolhido_sem_id_levanta_value_error(conn):
    with pytest.raises(ValueError):
        with conn:
            gravar_carreira(conn, "Copa do Brasil", 2026, Equipe("Sem Id"), None)

    assert ler_carreira(conn) is None
    assert _contar(conn, "times") == 0


def test_erro_no_meio_da_gravacao_faz_rollback_dentro_de_with_conn(conn):
    with conn:
        gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), [_time(2, "Santos")])

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            # forca 101 viola o CHECK depois dos DELETEs.
            gravar_carreira(conn, "Copa do Brasil", 2027, _time(1, "São Paulo", forca=101), None)

    lido = ler_carreira(conn)
    assert lido["temporada"] == 2026
    assert [t.id for t in lido["classificados"]] == [2]


def test_repositorio_nao_faz_commit(conn):
    gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), None)

    assert conn.in_transaction
    conn.rollback()
    assert ler_carreira(conn) is None


def test_codigo_sem_select_asterisco_nem_sql_montado_com_valor():
    fonte = inspect.getsource(repo)

    assert "SELECT *" not in fonte.upper()
    assert not re.search(r'f"[^"]*(SELECT|INSERT|DELETE|UPDATE)', fonte, re.IGNORECASE)
    assert not re.search(r'(SELECT|INSERT|DELETE|UPDATE)[^"]*"\s*(%|\+)', fonte, re.IGNORECASE)


def test_mesmo_objeto_como_escolhido_e_classificado_volta_em_objetos_separados(conn):
    sao_paulo = _time(1, "São Paulo", financas=4_321)
    gravar_carreira(conn, "Copa do Brasil", 2026, sao_paulo, [sao_paulo, _time(2, "Santos")])

    lido = ler_carreira(conn)

    assert lido["time_escolhido"] is not lido["classificados"][0]
    assert lido["time_escolhido"] == lido["classificados"][0]
    assert lido["time_escolhido"].financas == 4_321
    assert _contar(conn, "times") == 2


def test_valores_nos_limites_zero_e_cem_e_lista_de_cores_vazia(conn):
    escolhido = _time(1, "São Paulo", financas=0, fas=0, titulos=0, forca=0, cores=[])
    classificado = _time(2, "Santos", forca=100, cores=["#000000", "#111111", "#222222", "#333333"])
    gravar_carreira(conn, "Copa do Brasil", 2026, escolhido, [classificado])

    lido = ler_carreira(conn)

    assert _campos(lido["time_escolhido"]) == _campos(escolhido)
    assert _campos(lido["classificados"][0]) == _campos(classificado)


def test_valor_negativo_levanta_integrity_error_e_preserva_save_anterior(conn):
    with conn:
        gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), None)

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_carreira(conn, "Copa do Brasil", 2027, _time(1, "São Paulo"), [_time(2, "Santos", fas=-1)])

    lido = ler_carreira(conn)
    assert lido["temporada"] == 2026
    assert lido["classificados"] is None


def test_classificado_repetido_levanta_integrity_error_e_preserva_save_anterior(conn):
    with conn:
        gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), [_time(2, "Santos")])

    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            gravar_carreira(
                conn, "Copa do Brasil", 2027, _time(1, "São Paulo"),
                [_time(3, "Grêmio"), _time(3, "Grêmio")],
            )

    lido = ler_carreira(conn)
    assert lido["temporada"] == 2026
    assert [t.id for t in lido["classificados"]] == [2]


def test_sem_id_no_meio_dos_classificados_nao_executa_sql(conn):
    gravar_carreira(conn, "Copa do Brasil", 2026, _time(1, "São Paulo"), [_time(2, "Santos")])

    with pytest.raises(ValueError):
        gravar_carreira(conn, "Copa do Brasil", 2027, _time(1, "São Paulo"), [_time(3, "Grêmio"), Equipe("X")])

    # Sem rollback: se algum DELETE tivesse rodado, a carreira já teria sumido.
    lido = ler_carreira(conn)
    assert lido["temporada"] == 2026
    assert [t.id for t in lido["classificados"]] == [2]
