import re

import pytest

import catalogo
from equipe import Equipe

PADRAO_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_catalogo_tem_32_times_com_ids_1_a_32_unicos_e_consecutivos():
    ids = [time["id"] for time in catalogo.TIMES_PADRAO]

    assert ids == list(range(1, 33))


def test_catalogo_tem_16_times_por_campeonato_e_32_nomes_distintos():
    por_campeonato = {}
    for time in catalogo.TIMES_PADRAO:
        por_campeonato.setdefault(time["campeonato"], []).append(time["nome"])

    assert {campeonato: len(nomes) for campeonato, nomes in por_campeonato.items()} == {
        "Copa do Brasil": 16,
        "Copa do Mundo 2026": 16,
    }
    assert len({time["nome"] for time in catalogo.TIMES_PADRAO}) == 32


def test_copa_do_brasil_ids_1_a_16_e_copa_do_mundo_17_a_32():
    for time in catalogo.TIMES_PADRAO:
        esperado = "Copa do Brasil" if time["id"] <= 16 else "Copa do Mundo 2026"
        assert time["campeonato"] == esperado, time["nome"]


def test_todo_time_tem_3_cores_hex_validas():
    for time in catalogo.TIMES_PADRAO:
        assert len(time["cores"]) == 3, time["nome"]
        for cor in time["cores"]:
            assert PADRAO_HEX.match(cor), f"{time['nome']}: {cor}"


@pytest.mark.parametrize(
    ("id_time", "nome"),
    [(1, "São Paulo"), (17, "Brasil"), (32, "Suíça"), (999, None), (None, None)],
)
def test_nome_do_time(id_time, nome):
    assert catalogo.nome_do_time(id_time) == nome


def test_cores_do_time_por_id():
    assert catalogo.cores_do_time(1) == ["#E30613", "#FFFFFF", "#000000"]
    assert catalogo.cores_do_time(17) == ["#009C3B", "#FFDF00", "#002776"]


def test_cores_do_time_id_desconhecido_retorna_none():
    assert catalogo.cores_do_time(999) is None
    assert catalogo.cores_do_time(None) is None


def test_cores_do_time_devolve_copia():
    cores = catalogo.cores_do_time(1)
    cores[0] = "#123456"

    assert catalogo.cores_do_time(1)[0] == "#E30613"
    assert catalogo.TIMES_PADRAO[0]["cores"][0] == "#E30613"


@pytest.mark.parametrize(
    ("nome", "id_time"),
    [("Brasil", 17), ("São Paulo", 1), ("Coritiba", 16), ("Time Fantasma", None)],
)
def test_id_do_time_por_nome(nome, id_time):
    assert catalogo.id_do_time_por_nome(nome) == id_time


@pytest.mark.parametrize(
    ("time", "esperado"),
    [
        (Equipe("Qualquer", id=1), "São Paulo"),
        (Equipe("Time A", id=901), "Time A"),
        (Equipe("Time Sem Id"), "Time Sem Id"),
        (5, "Flamengo"),
        (999, "Time #999"),
        (None, ""),
        ("Texto", "Texto"),
    ],
)
def test_nome_para_exibir(time, esperado):
    assert catalogo.nome_para_exibir(time) == esperado
