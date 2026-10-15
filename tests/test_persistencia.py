import json
import os
import re
import sqlite3

import pytest

import catalogo
import persistencia
from dados.migrar import versao_atual
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


NOME = "1_01_01_2026"


def _versao_do_arquivo(caminho):
    conn = sqlite3.connect(caminho)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _criar_db_com_versao(caminho, versao):
    conn = sqlite3.connect(caminho)
    try:
        conn.execute(f"PRAGMA user_version = {int(versao)}")
    finally:
        conn.close()


def test_persistencia_nao_tem_mais_versao_save():
    """A versão do save agora é o `PRAGMA user_version` do banco."""
    assert not hasattr(persistencia, "VERSAO_SAVE")


def test_salvar_jogo_cria_db_na_versao_atual_do_esquema(dir_saves):
    persistencia.salvar_jogo(NOME, "Campeonato Teste", Equipe("Time A", id=901), 2026, None)

    caminho = dir_saves / f"{NOME}.db"
    assert caminho.exists()
    assert not (dir_saves / f"{NOME}.json").exists()
    assert _versao_do_arquivo(caminho) == 1 == versao_atual()


def test_salvar_e_carregar_devolve_o_mesmo_retrato(dir_saves):
    escolhido = Equipe("Time A", financas=10, fas=20, titulos=1, forca=70, cores=["#111111"], id=901)
    no_chaveamento = Equipe("Time A", financas=99, fas=88, titulos=1, forca=70, cores=["#111111"], id=901)
    outro = Equipe("Time B", financas=5, fas=6, titulos=0, forca=40, cores=None, id=902)
    historico = [
        {"temporada": 2026, "campeao": 901, "fases": [
            {"nome_fase": "Semifinal", "confrontos": [[901, 903, 901, 2, 1], [902, 904, 902, 0, 0]]},
            {"nome_fase": "Final", "confrontos": [[901, 902, 901, 3, 2]]},
        ]},
        {"temporada": 2027, "campeao": 902, "fases": []},
    ]

    persistencia.salvar_jogo(NOME, "Campeonato Teste", escolhido, 2028, [outro, no_chaveamento], historico)
    dados = persistencia.carregar_jogo_salvo(NOME)

    assert set(dados) == {"campeonato", "time_escolhido", "temporada", "classificados", "historico"}
    assert dados["campeonato"] == "Campeonato Teste"
    assert dados["temporada"] == 2028
    assert dados["historico"] == historico
    assert [time.id for time in dados["classificados"]] == [902, 901]
    time_b, time_a = dados["classificados"]
    assert (time_b.nome, time_b.financas, time_b.fas, time_b.forca, time_b.cores) == ("Time B", 5, 6, 40, None)
    assert (time_a.financas, time_a.fas) == (99, 88)
    # Escolhido e classificado: o mesmo objeto (B-020).
    assert dados["time_escolhido"] is time_a


def test_salvar_jogo_de_novo_substitui_o_retrato(dir_saves):
    time = Equipe("Time A", id=901)
    persistencia.salvar_jogo(NOME, "Campeonato Teste", time, 2026, [time, Equipe("Time B", id=902)],
                             [{"temporada": 2025, "campeao": 902, "fases": []}])

    persistencia.salvar_jogo(NOME, "Campeonato Teste", time, 2027, None)

    dados = persistencia.carregar_jogo_salvo(NOME)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == []


def test_listar_saves_ignora_invalidos_sem_apagar(dir_saves):
    time = Equipe("Time A", id=901)
    persistencia.salvar_jogo("10_01_01_2026", "Campeonato Teste", time, 2026, [time])
    persistencia.salvar_jogo("2_01_01_2026", "Campeonato Teste", time, 2026, None)
    antigo = {"versao": 2, "campeonato": "Campeonato Teste", "time_escolhido": time.to_dict(),
              "temporada": 2026, "classificados": None, "historico": []}
    ignorados = {
        "3_01_01_2026.json": json.dumps(antigo).encode("utf-8"),
        "4_01_01_2026.json": "{isso não é json".encode("utf-8"),
        "5_01_01_2026.db": b"isto nao e um banco sqlite" * 50,
        "6_01_01_2026.db": b"",
    }
    for nome, conteudo in ignorados.items():
        (dir_saves / nome).write_bytes(conteudo)
    _criar_db_com_versao(dir_saves / "7_01_01_2026.db", 99)
    _criar_db_com_versao(dir_saves / "8_01_01_2026.db", 0)
    bytes_versao_99 = (dir_saves / "7_01_01_2026.db").read_bytes()
    bytes_versao_0 = (dir_saves / "8_01_01_2026.db").read_bytes()

    assert persistencia.listar_saves() == ["2_01_01_2026", "10_01_01_2026"]

    # Nada é apagado nem alterado: os arquivos ignorados continuam no disco.
    for nome, conteudo in ignorados.items():
        assert (dir_saves / nome).read_bytes() == conteudo
    assert (dir_saves / "7_01_01_2026.db").read_bytes() == bytes_versao_99
    assert (dir_saves / "8_01_01_2026.db").read_bytes() == bytes_versao_0
    assert not any(nome.endswith("-journal") for nome in os.listdir(dir_saves))


def test_listar_saves_sem_pasta_devolve_lista_vazia(dir_saves):
    assert persistencia.listar_saves() == []
    assert not dir_saves.exists()


def test_carregar_save_inexistente_devolve_none_sem_criar_arquivo(dir_saves):
    dir_saves.mkdir()

    assert persistencia.carregar_jogo_salvo("nao_existe") is None

    assert os.listdir(dir_saves) == []


@pytest.mark.parametrize("versao", [None, 0, 99])
def test_carregar_db_invalido_devolve_none_sem_alterar(dir_saves, versao):
    """`None` = bytes que não são SQLite; 0 = banco vazio; 99 = versão futura."""
    dir_saves.mkdir()
    caminho = dir_saves / f"{NOME}.db"
    if versao is None:
        caminho.write_bytes(b"lixo" * 300)
    else:
        _criar_db_com_versao(caminho, versao)
    conteudo = caminho.read_bytes()

    assert persistencia.carregar_jogo_salvo(NOME) is None

    assert caminho.read_bytes() == conteudo
    assert os.listdir(dir_saves) == [f"{NOME}.db"]


def test_gerar_nome_save_considera_json_antigo_e_db(dir_saves):
    dir_saves.mkdir()
    (dir_saves / "5_01_01_2026.json").write_text("{}", encoding="utf-8")
    persistencia.salvar_jogo("3_01_01_2026", "Campeonato Teste", Equipe("Time A", id=901), 2026, None)

    assert persistencia.gerar_nome_save().startswith("6_")


def test_excluir_logo_depois_de_listar_e_carregar(dir_saves):
    """Prova que nenhuma conexão ficou aberta (no Windows, impediria o
    `os.remove`)."""
    time = Equipe("Time A", id=901)
    persistencia.salvar_jogo(NOME, "Campeonato Teste", time, 2026, [time])
    assert persistencia.listar_saves() == [NOME]
    assert persistencia.carregar_jogo_salvo(NOME) is not None

    assert persistencia.excluir_jogo_salvo(NOME) is True
    assert not (dir_saves / f"{NOME}.db").exists()
    assert persistencia.excluir_jogo_salvo(NOME) is False


def test_excluir_remove_journal_que_sobrou(dir_saves):
    persistencia.salvar_jogo(NOME, "Campeonato Teste", Equipe("Time A", id=901), 2026, None)
    (dir_saves / f"{NOME}.db-journal").write_bytes(b"")

    assert persistencia.excluir_jogo_salvo(NOME) is True
    assert os.listdir(dir_saves) == []


def test_salvar_com_time_sem_id_nao_altera_save_anterior(dir_saves):
    time = Equipe("Time A", id=901)
    persistencia.salvar_jogo(NOME, "Campeonato Teste", time, 2026, None)

    with pytest.raises(ValueError):
        persistencia.salvar_jogo(NOME, "Campeonato Teste", time, 2027, [Equipe("Sem Id")])

    assert persistencia.carregar_jogo_salvo(NOME)["temporada"] == 2026


# --- Catálogo do adm aplicado ao carregar (ID-008-T3) ---------------------


def _renomear_sao_paulo():
    catalogo.salvar_time_no_catalogo(1, "SPFC", ["#FF0000", "#000000"])


def test_carregar_equipes_aplica_nome_e_cores_do_adm_sem_regravar(arquivo_equipes):
    persistencia.restaurar_equipes_padrao()
    conteudo_antes = arquivo_equipes.read_text(encoding="utf-8")
    _renomear_sao_paulo()

    equipes = persistencia.carregar_equipes()

    sao_paulo = next(equipe for equipe in equipes["Copa do Brasil"] if equipe.id == 1)
    assert sao_paulo.nome == "SPFC"
    assert sao_paulo.cores == ["#FF0000", "#000000"]
    palmeiras = next(equipe for equipe in equipes["Copa do Brasil"] if equipe.id == 2)
    assert palmeiras.nome == "Palmeiras"
    # Só em memória: o equipes.json continua com o nome antigo.
    assert arquivo_equipes.read_text(encoding="utf-8") == conteudo_antes
    nomes_no_arquivo = [time["nome"] for time in json.loads(conteudo_antes)["Copa do Brasil"]]
    assert "São Paulo" in nomes_no_arquivo


def test_carregar_equipes_mantem_time_com_id_desconhecido(arquivo_equipes):
    conteudo = json.dumps(
        {"Copa do Brasil": [{"id": 901, "nome": "Time Fantasma", "cores": ["#111111"]}]},
        ensure_ascii=False,
    )
    arquivo_equipes.write_text(conteudo, encoding="utf-8")
    _renomear_sao_paulo()

    (time,) = persistencia.carregar_equipes()["Copa do Brasil"]

    assert (time.id, time.nome, time.cores) == (901, "Time Fantasma", ["#111111"])


def test_carregar_jogo_salvo_aplica_catalogo_do_adm(dir_saves):
    sao_paulo = Equipe("São Paulo", financas=123, cores=["#E30613", "#FFFFFF", "#000000"], id=1)
    fantasma = Equipe("Time Fantasma", cores=["#111111"], id=901)
    persistencia.salvar_jogo("1_01_01_2026", "Copa do Brasil", sao_paulo, 2026, [sao_paulo, fantasma])
    caminho = dir_saves / "1_01_01_2026.db"
    conteudo_antes = caminho.read_bytes()
    _renomear_sao_paulo()

    dados = persistencia.carregar_jogo_salvo("1_01_01_2026")

    escolhido = dados["time_escolhido"]
    assert (escolhido.id, escolhido.nome, escolhido.cores) == (1, "SPFC", ["#FF0000", "#000000"])
    assert escolhido.financas == 123  # os demais campos vêm do save
    classificado_sp, classificado_fantasma = dados["classificados"]
    assert (classificado_sp.nome, classificado_sp.cores) == ("SPFC", ["#FF0000", "#000000"])
    assert (classificado_fantasma.id, classificado_fantasma.nome, classificado_fantasma.cores) == (
        901, "Time Fantasma", ["#111111"],
    )
    # Só em memória: o save não é regravado (nem ao listar).
    assert persistencia.listar_saves() == ["1_01_01_2026"]
    assert caminho.read_bytes() == conteudo_antes


def test_carregar_jogo_salvo_com_classificados_none(dir_saves):
    persistencia.salvar_jogo("1_01_01_2026", "Copa do Brasil", Equipe("São Paulo", id=1), 2026, None)
    _renomear_sao_paulo()

    dados = persistencia.carregar_jogo_salvo("1_01_01_2026")

    assert dados["time_escolhido"].nome == "SPFC"
    assert dados["classificados"] is None


def test_carregar_com_jogador_eliminado_nao_poe_ele_nos_classificados(dir_saves):
    """B-020 (borda): jogador já eliminado no meio da temporada — o
    `time_escolhido` volta sozinho e os classificados seguem sem ele."""
    escolhido = Equipe("Time A", titulos=2, id=901)
    restantes = [Equipe("Time B", id=902), Equipe("Time C", id=903)]
    persistencia.salvar_jogo(NOME, "Campeonato Teste", escolhido, 2026, restantes)

    dados = persistencia.carregar_jogo_salvo(NOME)

    assert dados["time_escolhido"].titulos == 2
    assert [time.id for time in dados["classificados"]] == [902, 903]
    assert all(time is not dados["time_escolhido"] for time in dados["classificados"])


def test_carregar_unificado_aplica_catalogo_no_objeto_unico(dir_saves):
    """B-020 (borda): o objeto único do jogador já vem com o nome do adm."""
    persistencia.salvar_jogo(
        NOME, "Copa do Brasil", Equipe("São Paulo", id=1, titulos=3), 2026,
        [Equipe("Palmeiras", id=2), Equipe("São Paulo", id=1, titulos=3)],
    )
    _renomear_sao_paulo()

    dados = persistencia.carregar_jogo_salvo(NOME)

    assert dados["classificados"][1] is dados["time_escolhido"]
    assert dados["time_escolhido"].nome == "SPFC"
    assert dados["time_escolhido"].titulos == 3
