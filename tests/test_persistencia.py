import json
import os
import re

import pytest

import persistencia
from equipe import Equipe

PADRAO_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@pytest.fixture
def arquivo_equipes(tmp_path, monkeypatch):
    """Aponta o `equipes.json` para um arquivo de teste (nunca o real)."""
    arquivo = tmp_path / "equipes.json"
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    return arquivo


def test_todo_time_do_padrao_tem_3_cores_hex_validas():
    for times in persistencia.EQUIPES_PADRAO.values():
        for nome, cores in times.items():
            assert len(cores) == 3, nome
            for cor in cores:
                assert PADRAO_HEX.match(cor), f"{nome}: {cor}"


def test_padrao_tem_16_times_por_campeonato_e_32_nomes_distintos():
    nomes = []
    for times in persistencia.EQUIPES_PADRAO.values():
        assert len(times) == 16
        nomes.extend(times)

    assert len(set(nomes)) == 32


def test_cores_do_time_por_nome():
    assert persistencia.cores_do_time("São Paulo") == ["#E30613", "#FFFFFF", "#000000"]


def test_cores_do_time_aceita_equipe():
    assert persistencia.cores_do_time(Equipe("Brasil")) == ["#009C3B", "#FFDF00", "#002776"]


def test_cores_do_time_desconhecido_retorna_none():
    assert persistencia.cores_do_time("Time Fantasma") is None


def test_alterar_lista_devolvida_nao_altera_o_padrao():
    cores = persistencia.cores_do_time("São Paulo")
    cores[0] = "#123456"

    assert persistencia.EQUIPES_PADRAO["Copa do Brasil"]["São Paulo"][0] == "#E30613"


def test_restaurar_padrao_grava_cores_e_carregar_devolve_as_mesmas(arquivo_equipes):
    persistencia.restaurar_equipes_padrao()

    dados = json.loads(arquivo_equipes.read_text(encoding="utf-8"))
    for campeonato, times in persistencia.EQUIPES_PADRAO.items():
        assert {time["nome"]: time["cores"] for time in dados[campeonato]} == times

    equipes = persistencia.carregar_equipes()
    for campeonato, times in persistencia.EQUIPES_PADRAO.items():
        assert {equipe.nome: equipe.cores for equipe in equipes[campeonato]} == times


@pytest.mark.parametrize(
    "times_antigos",
    [
        ["São Paulo", "Time Fantasma"],
        [
            {"nome": "São Paulo", "financas": 1, "fas": 2, "titulos": 0, "forca": 50},
            {"nome": "Time Fantasma", "financas": 1, "fas": 2, "titulos": 0, "forca": 50},
        ],
    ],
)
def test_carregar_json_antigo_sem_cores_preenche_com_catalogo(arquivo_equipes, times_antigos):
    conteudo = json.dumps({"Copa do Brasil": times_antigos}, ensure_ascii=False)
    arquivo_equipes.write_text(conteudo, encoding="utf-8")

    equipes = persistencia.carregar_equipes()

    sao_paulo, fantasma = equipes["Copa do Brasil"]
    assert sao_paulo.cores == ["#E30613", "#FFFFFF", "#000000"]
    assert fantasma.cores is None
    # Só completa em memória: o arquivo não é regravado.
    assert arquivo_equipes.read_text(encoding="utf-8") == conteudo


def test_equipes_json_do_repositorio_igual_ao_padrao_restaurado(arquivo_equipes):
    caminho_real = os.path.join(persistencia.BASE_DIR, "equipes.json")
    with open(caminho_real, encoding="utf-8") as arquivo:
        dados_repositorio = json.load(arquivo)

    persistencia.restaurar_equipes_padrao()
    dados_padrao = json.loads(arquivo_equipes.read_text(encoding="utf-8"))

    assert dados_repositorio == dados_padrao
