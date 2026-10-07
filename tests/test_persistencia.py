import json
import os
import re

import pytest

import catalogo
import persistencia
from equipe import Equipe

PADRAO_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@pytest.fixture
def arquivo_equipes(tmp_path, monkeypatch):
    """Aponta o `equipes.json` para um arquivo de teste (nunca o real)."""
    arquivo = tmp_path / "equipes.json"
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(arquivo))
    return arquivo


def test_cores_do_time_por_nome():
    assert persistencia.cores_do_time("São Paulo") == ["#E30613", "#FFFFFF", "#000000"]


def test_cores_do_time_aceita_equipe():
    assert persistencia.cores_do_time(Equipe("Brasil")) == ["#009C3B", "#FFDF00", "#002776"]


def test_cores_do_time_desconhecido_retorna_none():
    assert persistencia.cores_do_time("Time Fantasma") is None


def test_alterar_lista_devolvida_nao_altera_o_padrao():
    cores = persistencia.cores_do_time("São Paulo")
    cores[0] = "#123456"

    assert catalogo.cores_do_time(1)[0] == "#E30613"


def _padrao_por_campeonato():
    """{campeonato: [(id, nome, cores), ...]} na ordem de `TIMES_PADRAO`."""
    esperado = {}
    for time in catalogo.TIMES_PADRAO:
        esperado.setdefault(time["campeonato"], []).append((time["id"], time["nome"], time["cores"]))
    return esperado


def test_restaurar_padrao_grava_ids_e_cores_e_carregar_devolve_os_mesmos(arquivo_equipes):
    persistencia.restaurar_equipes_padrao()

    dados = json.loads(arquivo_equipes.read_text(encoding="utf-8"))
    gravado = {
        campeonato: [(time["id"], time["nome"], time["cores"]) for time in times]
        for campeonato, times in dados.items()
    }
    assert gravado == _padrao_por_campeonato()

    equipes = persistencia.carregar_equipes()
    carregado = {
        campeonato: [(equipe.id, equipe.nome, equipe.cores) for equipe in times]
        for campeonato, times in equipes.items()
    }
    assert carregado == _padrao_por_campeonato()


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
def test_carregar_json_antigo_sem_id_e_cores_preenche_com_catalogo(arquivo_equipes, times_antigos):
    conteudo = json.dumps({"Copa do Brasil": times_antigos}, ensure_ascii=False)
    arquivo_equipes.write_text(conteudo, encoding="utf-8")

    equipes = persistencia.carregar_equipes()

    sao_paulo, fantasma = equipes["Copa do Brasil"]
    assert sao_paulo.id == 1
    assert sao_paulo.cores == ["#E30613", "#FFFFFF", "#000000"]
    assert fantasma.id is None
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


def test_carregar_json_antigo_sem_id_preserva_os_demais_campos(arquivo_equipes):
    conteudo = json.dumps(
        {"Copa do Mundo 2026": [{"nome": "Brasil", "financas": 7, "fas": 8, "titulos": 3, "forca": 90}]},
        ensure_ascii=False,
    )
    arquivo_equipes.write_text(conteudo, encoding="utf-8")

    (brasil,) = persistencia.carregar_equipes()["Copa do Mundo 2026"]

    assert brasil.id == 17
    assert (brasil.financas, brasil.fas, brasil.titulos, brasil.forca) == (7, 8, 3, 90)


def test_carregar_mantem_id_e_cores_gravados_no_arquivo(arquivo_equipes):
    conteudo = json.dumps(
        {"Copa do Brasil": [{"id": 905, "nome": "São Paulo", "cores": ["#111111", "#222222", "#333333"]}]},
        ensure_ascii=False,
    )
    arquivo_equipes.write_text(conteudo, encoding="utf-8")

    (time,) = persistencia.carregar_equipes()["Copa do Brasil"]

    assert time.id == 905
    assert time.cores == ["#111111", "#222222", "#333333"]
