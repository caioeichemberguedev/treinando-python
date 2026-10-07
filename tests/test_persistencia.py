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


def test_persistencia_nao_expoe_mais_cores_do_time_por_nome():
    """As cores vêm só do catálogo, pelo id (`catalogo.cores_do_time`)."""
    assert not hasattr(persistencia, "cores_do_time")


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


@pytest.fixture
def dir_saves(tmp_path, monkeypatch):
    """Aponta a pasta `saves/` para um diretório de teste (nunca o real)."""
    pasta = tmp_path / "saves"
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(pasta))
    return pasta


def test_salvar_jogo_grava_a_versao_atual(dir_saves):
    persistencia.salvar_jogo("1_01_01_2026", "Campeonato Teste", Equipe("Time A", id=901), 2026, None)

    dados = json.loads((dir_saves / "1_01_01_2026.json").read_text(encoding="utf-8"))

    assert persistencia.VERSAO_SAVE == 2
    assert dados["versao"] == 2


def test_listar_saves_ignora_save_antigo_e_json_corrompido(dir_saves):
    time = Equipe("Time A", id=901)
    persistencia.salvar_jogo("1_01_01_2026", "Campeonato Teste", time, 2026, [time])
    antigo = {"campeonato": "Campeonato Teste", "time_escolhido": time.to_dict(), "temporada": 2026,
              "classificados": None, "historico": []}
    (dir_saves / "2_01_01_2026.json").write_text(json.dumps(antigo), encoding="utf-8")
    (dir_saves / "3_01_01_2026.json").write_text("{isso não é json", encoding="utf-8")

    assert persistencia.listar_saves() == ["1_01_01_2026"]
    # Nada é apagado: os arquivos ignorados continuam no disco.
    assert os.path.exists(dir_saves / "2_01_01_2026.json")
    assert os.path.exists(dir_saves / "3_01_01_2026.json")
