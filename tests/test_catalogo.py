import json
import os
import re

import pytest

import catalogo
import persistencia
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


def test_todo_time_tem_de_1_a_4_cores_hex_validas():
    for time in catalogo.TIMES_PADRAO:
        assert 1 <= len(time["cores"]) <= 4, time["nome"]
        for cor in time["cores"]:
            assert PADRAO_HEX.match(cor), f"{time['nome']}: {cor}"
        assert catalogo.cores_validas(time["cores"]), time["nome"]


def test_corinthians_padrao_e_preto_e_branco_em_2_faixas():
    assert catalogo.cores_do_time(3) == ["#000000", "#FFFFFF"]


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


# --- Catálogo editável do adm (ID-008) ---------------------------------------


def _padrao_por_id():
    return {
        time["id"]: {
            "campeonato": time["campeonato"],
            "nome": time["nome"],
            "cores": time["cores"],
        }
        for time in catalogo.TIMES_PADRAO
    }


def _ler_arquivo_catalogo():
    with open(catalogo.ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_sem_arquivo_do_adm_catalogo_efetivo_e_o_padrao():
    assert not os.path.exists(catalogo.ARQUIVO_CATALOGO)
    assert catalogo.carregar_catalogo() == _padrao_por_id()


def test_salvar_time_no_catalogo_vale_por_cima_do_padrao():
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])

    assert catalogo.nome_do_time(1) == "SPFC"
    assert catalogo.cores_do_time(1) == ["#FF0000"]
    assert catalogo.nome_para_exibir(Equipe("São Paulo", id=1)) == "SPFC"
    assert catalogo.nome_para_exibir(1) == "SPFC"
    assert list(_ler_arquivo_catalogo()) == ["1"]

    efetivo = catalogo.carregar_catalogo()
    padrao = _padrao_por_id()
    for id_time in range(2, 33):
        assert efetivo[id_time] == padrao[id_time]


def test_salvar_normaliza_nome_e_cores():
    catalogo.salvar_time_no_catalogo(1, "  SPFC  ", ["#ff00aa", "#ffffff"])

    assert _ler_arquivo_catalogo() == {
        "1": {"nome": "SPFC", "cores": ["#FF00AA", "#FFFFFF"]}
    }


def test_salvar_dois_times_mantem_os_dois_no_arquivo():
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])
    catalogo.salvar_time_no_catalogo(17, "Seleção", ["#009C3B", "#FFDF00"])

    assert set(_ler_arquivo_catalogo()) == {"1", "17"}
    assert catalogo.nome_do_time(1) == "SPFC"
    assert catalogo.nome_do_time(17) == "Seleção"


@pytest.mark.parametrize(
    ("id_time", "nome", "cores"),
    [
        (1, "", ["#FF0000"]),
        (1, "   ", ["#FF0000"]),
        (1, "A" * 41, ["#FF0000"]),
        (1, "palmeiras", ["#FF0000"]),
        (1, "SPFC", []),
        (1, "SPFC", ["#FF0000"] * 5),
        (1, "SPFC", ["red"]),
        (1, "SPFC", ["#FFF"]),
        (1, "SPFC", "#FF0000"),
        (999, "Time Novo", ["#FF0000"]),
    ],
)
def test_salvar_time_invalido_levanta_value_error_e_nao_grava(id_time, nome, cores):
    assert catalogo.validar_time(id_time, nome, cores) != []

    with pytest.raises(ValueError):
        catalogo.salvar_time_no_catalogo(id_time, nome, cores)

    assert not os.path.exists(catalogo.ARQUIVO_CATALOGO)
    assert catalogo.carregar_catalogo() == _padrao_por_id()


def test_nome_duplicado_compara_com_nome_editado_de_outro_time():
    catalogo.salvar_time_no_catalogo(2, "Verdão", ["#006437"])

    assert catalogo.validar_time(1, "VERDÃO", ["#FF0000"]) != []
    assert catalogo.validar_time(1, "Palmeiras", ["#FF0000"]) == []


def test_mensagens_de_erro_em_portugues():
    erros = catalogo.validar_time(1, "", ["red"])

    assert erros == [
        "O nome do time não pode ficar vazio.",
        "Escolha de 1 a 4 cores no formato #RRGGBB.",
    ]
    assert catalogo.validar_time(1, "Palmeiras", ["#FF0000"]) == [
        "Já existe um time chamado Palmeiras."
    ]


@pytest.mark.parametrize("nome", ["São Paulo", "SÃO PAULO", "são paulo"])
def test_aceita_renomear_para_o_proprio_nome(nome):
    catalogo.salvar_time_no_catalogo(1, nome, ["#E30613"])

    assert catalogo.nome_do_time(1) == nome


def test_aceita_nome_com_40_caracteres_e_4_cores():
    nome = "A" * 40
    cores = ["#000000", "#111111", "#222222", "#333333"]

    catalogo.salvar_time_no_catalogo(1, nome, cores)

    assert catalogo.nome_do_time(1) == nome
    assert catalogo.cores_do_time(1) == cores


@pytest.mark.parametrize(
    ("cores", "valido"),
    [
        (["#000000"], True),
        (("#000000", "#ffffff"), True),
        (["#000000"] * 4, True),
        ([], False),
        (["#000000"] * 5, False),
        (["red"], False),
        (["#FFF"], False),
        (["#GGGGGG"], False),
        ([None], False),
        (None, False),
        ("#000000", False),
    ],
)
def test_cores_validas(cores, valido):
    assert catalogo.cores_validas(cores) is valido


def test_restaurar_equipes_padrao_nao_desfaz_o_catalogo_do_adm(tmp_path, monkeypatch):
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])
    with open(catalogo.ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
        conteudo_antes = arquivo.read()

    persistencia.restaurar_equipes_padrao()

    with open(catalogo.ARQUIVO_CATALOGO, encoding="utf-8") as arquivo:
        assert arquivo.read() == conteudo_antes
    assert catalogo.nome_do_time(1) == "SPFC"
    assert catalogo.cores_do_time(1) == ["#FF0000"]


def _contar_leituras(monkeypatch):
    chamadas = []
    original = catalogo._ler_edicoes_adm

    def contando():
        chamadas.append(1)
        return original()

    monkeypatch.setattr(catalogo, "_ler_edicoes_adm", contando)
    return chamadas


def test_cache_nao_rele_o_arquivo_em_leituras_seguidas(monkeypatch):
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])
    chamadas = _contar_leituras(monkeypatch)

    catalogo.nome_do_time(1)
    catalogo.cores_do_time(1)
    catalogo.nome_para_exibir(5)

    assert len(chamadas) == 1


def test_cache_ve_o_valor_novo_depois_de_salvar(monkeypatch):
    chamadas = _contar_leituras(monkeypatch)
    assert catalogo.nome_do_time(1) == "São Paulo"

    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])

    assert catalogo.nome_do_time(1) == "SPFC"
    assert catalogo.nome_do_time(1) == "SPFC"
    # 1ª leitura + leitura do arquivo ao salvar + releitura após salvar.
    assert len(chamadas) == 3


def test_cache_rele_quando_o_arquivo_muda_por_fora():
    assert catalogo.nome_do_time(1) == "São Paulo"

    with open(catalogo.ARQUIVO_CATALOGO, "w", encoding="utf-8") as arquivo:
        json.dump({"1": {"nome": "Editado Fora", "cores": ["#123456"]}}, arquivo)

    assert catalogo.nome_do_time(1) == "Editado Fora"


def test_cache_rele_quando_o_caminho_do_arquivo_muda(tmp_path, monkeypatch):
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000"])
    assert catalogo.nome_do_time(1) == "SPFC"

    monkeypatch.setattr(catalogo, "ARQUIVO_CATALOGO", str(tmp_path / "outro.json"))

    assert catalogo.nome_do_time(1) == "São Paulo"
