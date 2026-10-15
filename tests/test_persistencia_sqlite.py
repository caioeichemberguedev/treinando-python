"""Ponta a ponta e robustez do save em SQLite (E-013-T6).

Temporadas jogadas pelo terminal (`menu.rodar_temporada` com `input`
simulado) gravando no `.db`, e duas conexões no mesmo arquivo ao mesmo
tempo (terminal + web). O cenário web (listar/carregar/excluir uma carreira
criada pelo terminal) está em `tests/web/test_saves_sqlite_integracao.py`.

Tudo em `tmp_path` (DIR_SAVES/ARQUIVO_EQUIPES via monkeypatch): o `saves/`
real e o `equipes.json` real nunca são tocados.
"""

import os
import sqlite3

import pytest

from dados import conexao
import menu
import persistencia
from dados.conexao import abrir

CAMPEONATO = "Copa do Brasil"  # 16 times: oitavas, quartas, semi e final


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(persistencia, "ARQUIVO_EQUIPES", str(tmp_path / "equipes.json"))
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    persistencia.restaurar_equipes_padrao()  # grava no equipes.json de teste


@pytest.fixture
def times():
    return persistencia.carregar_equipes()[CAMPEONATO]


def _ids(equipes):
    return [equipe.id for equipe in equipes]


def _espionar_salvar_jogo(monkeypatch):
    """Envolve o `salvar_jogo` real usado pelo menu e guarda os argumentos
    de cada chamada (os classificados como lista de ids, no momento da
    chamada, e as fases da temporada em andamento, E-014).
    """
    chamadas = []
    salvar_real = persistencia.salvar_jogo

    def salvar_e_registrar(
        nome_save, campeonato, time_escolhido, temporada, classificados, historico=None, fases_da_temporada=None
    ):
        chamadas.append({
            "temporada": temporada,
            "classificados": None if classificados is None else _ids(classificados),
            "fases_da_temporada": list(fases_da_temporada or []),
        })
        salvar_real(nome_save, campeonato, time_escolhido, temporada, classificados, historico, fases_da_temporada)

    monkeypatch.setattr(menu, "salvar_jogo", salvar_e_registrar)
    return chamadas


# --- 2. Temporadas inteiras pelo terminal --------------------------------


def test_temporadas_inteiras_pelo_terminal_acumulam_no_historico(monkeypatch, times):
    """Joga a 2026 inteira sem sair, segue para a 2027 e para no fim dela."""
    nome = persistencia.gerar_nome_save()
    time_escolhido = times[0]
    monkeypatch.setattr("builtins.input", lambda mensagem="": "1")

    retratos_no_fim_da_temporada = []

    def fim_de_temporada(campeonato, temporada, campeao, historico):
        retratos_no_fim_da_temporada.append(persistencia.carregar_jogo_salvo(nome))
        return temporada == 2026  # segue só depois da primeira

    monkeypatch.setattr(menu, "menu_pos_temporada", fim_de_temporada)

    menu.rodar_temporada(nome, CAMPEONATO, time_escolhido, 2026, None, times)

    assert len(retratos_no_fim_da_temporada) == 2
    depois_da_2026, depois_da_2027 = retratos_no_fim_da_temporada

    assert depois_da_2026["campeonato"] == CAMPEONATO
    assert depois_da_2026["time_escolhido"].id == time_escolhido.id
    assert depois_da_2026["temporada"] == 2027
    assert depois_da_2026["classificados"] is None
    assert [t["temporada"] for t in depois_da_2026["historico"]] == [2026]
    fases = depois_da_2026["historico"][0]["fases"]
    assert [len(fase["confrontos"]) for fase in fases] == [8, 4, 2, 1]
    final = fases[-1]["confrontos"][0]
    assert depois_da_2026["historico"][0]["campeao"] == final[2]

    assert depois_da_2027["temporada"] == 2028
    assert depois_da_2027["classificados"] is None
    assert [t["temporada"] for t in depois_da_2027["historico"]] == [2026, 2027]
    # A 2026 continua idêntica depois de a 2027 ser gravada por cima.
    assert depois_da_2027["historico"][0] == depois_da_2026["historico"][0]
    for temporada in depois_da_2027["historico"]:
        assert sum(len(fase["confrontos"]) for fase in temporada["fases"]) == 15

    assert persistencia.listar_saves() == [nome]
    assert os.listdir(persistencia.DIR_SAVES) == [f"{nome}.db"]


# --- 3. Sair no meio e carregar --------------------------------------------


def test_sair_no_meio_e_carregar_devolve_os_mesmos_classificados_na_ordem(monkeypatch, times):
    chamadas = _espionar_salvar_jogo(monkeypatch)
    monkeypatch.setattr(
        "builtins.input", lambda mensagem="": "sair" if "sair" in mensagem else "1"
    )
    nome = persistencia.gerar_nome_save()
    time_escolhido = times[3]

    menu.rodar_temporada(nome, CAMPEONATO, time_escolhido, 2026, None, times)

    # 1ª gravação: chaveamento sorteado (16); 2ª: quem passou das oitavas.
    assert [len(c["classificados"]) for c in chamadas] == [16, 8]
    sorteio, depois_das_oitavas = (c["classificados"] for c in chamadas)
    # A ordem sorteada vem de random.shuffle: o teste não depende dela,
    # só de ela ser preservada. Os 8 que avançaram saem de pares do sorteio.
    for posicao, id_time in enumerate(depois_das_oitavas):
        assert id_time in sorteio[2 * posicao:2 * posicao + 2]

    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2026
    assert dados["historico"] == []
    assert dados["time_escolhido"].id == time_escolhido.id
    assert _ids(dados["classificados"]) == depois_das_oitavas

    # Carregar de novo devolve a mesma coisa (nada foi regravado).
    assert _ids(persistencia.carregar_jogo_salvo(nome)["classificados"]) == depois_das_oitavas


def _teclado_que_sai(monkeypatch, saidas):
    """`input` que responde 'sair' nas `saidas` primeiras perguntas de
    "próxima fase" e "1" em todo o resto (pênaltis, menus).
    """
    restantes = [saidas]

    def responder(mensagem=""):
        if "sair" in mensagem and restantes[0] > 0:
            restantes[0] -= 1
            return "sair"
        return "1"

    monkeypatch.setattr("builtins.input", responder)


def _terminar_carregando(monkeypatch, nome, times, vezes=1):
    """Carrega a carreira pelo menu `vezes` vezes e devolve os históricos
    vistos no fim da temporada (o jogo para ali, sem seguir para a próxima).
    """
    historicos = []

    def fim_de_temporada(campeonato, temporada, campeao, historico):
        historicos.append(historico)
        return False

    monkeypatch.setattr(menu, "menu_pos_temporada", fim_de_temporada)
    monkeypatch.setattr(menu, "escolher_save", lambda acao: nome)
    for _ in range(vezes):
        menu.carregar_jogo({CAMPEONATO: times})
    return historicos


def test_save_no_meio_guarda_as_fases_ja_jogadas(monkeypatch, times):
    """E-014: cada gravação no meio da temporada leva as fases já fechadas."""
    chamadas = _espionar_salvar_jogo(monkeypatch)
    _teclado_que_sai(monkeypatch, 1)
    nome = persistencia.gerar_nome_save()

    menu.rodar_temporada(nome, CAMPEONATO, times[3], 2026, None, times)

    assert [len(c["fases_da_temporada"]) for c in chamadas] == [0, 1]
    dados = persistencia.carregar_jogo_salvo(nome)
    assert [len(f["confrontos"]) for f in dados["fases_da_temporada"]] == [8]
    assert dados["fases_da_temporada"] == chamadas[-1]["fases_da_temporada"]


def test_sair_depois_das_oitavas_carregar_e_terminar_fecha_com_4_fases(monkeypatch, times):
    """Critério do E-014: sair depois das oitavas, carregar e terminar →
    histórico da temporada com 8, 4, 2 e 1 confrontos."""
    _teclado_que_sai(monkeypatch, 1)
    nome = persistencia.gerar_nome_save()
    menu.rodar_temporada(nome, CAMPEONATO, times[3], 2026, None, times)
    oitavas = persistencia.carregar_jogo_salvo(nome)["fases_da_temporada"]

    historicos = _terminar_carregando(monkeypatch, nome, times)

    assert len(historicos) == 1
    fases = historicos[0][-1]["fases"]
    assert [len(fase["confrontos"]) for fase in fases] == [8, 4, 2, 1]
    assert fases[0] == oitavas[0]
    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["fases_da_temporada"] == []
    temporada = dados["historico"][-1]
    assert [len(fase["confrontos"]) for fase in temporada["fases"]] == [8, 4, 2, 1]
    assert temporada["campeao"] == temporada["fases"][-1]["confrontos"][0][2]


def test_sair_duas_vezes_tambem_fecha_com_4_fases(monkeypatch, times):
    """Sai depois das oitavas, carrega, sai depois das quartas, carrega e
    termina: a temporada continua com as 4 fases."""
    _teclado_que_sai(monkeypatch, 2)
    nome = persistencia.gerar_nome_save()
    menu.rodar_temporada(nome, CAMPEONATO, times[3], 2026, None, times)
    assert len(persistencia.carregar_jogo_salvo(nome)["fases_da_temporada"]) == 1

    historicos = _terminar_carregando(monkeypatch, nome, times, vezes=2)

    assert len(historicos) == 1
    dados = persistencia.carregar_jogo_salvo(nome)
    temporada = dados["historico"][-1]
    assert [len(fase["confrontos"]) for fase in temporada["fases"]] == [8, 4, 2, 1]
    assert temporada["campeao"] == temporada["fases"][-1]["confrontos"][0][2]
    assert dados["fases_da_temporada"] == []


def test_carregar_entre_temporadas_soma_o_titulo_no_time_do_jogador(monkeypatch, times):
    """B-020: carreira salva entre temporadas com o jogador já bicampeão.
    Ao carregar pelo terminal, o sorteio usa o `time_escolhido` carregado
    (e não o objeto do elenco base), então um título novo soma nos 2 da
    carreira e vai para o save — sem depender de quem vence."""
    nome = persistencia.gerar_nome_save()
    escolhido = persistencia.carregar_equipes()[CAMPEONATO][0]
    escolhido.titulos = 2
    persistencia.salvar_jogo(nome, CAMPEONATO, escolhido, 2027, None, [])
    monkeypatch.setattr("builtins.input", lambda mensagem="": "1")
    campeoes = []

    def fim_de_temporada(campeonato, temporada, campeao, historico):
        campeoes.append(historico[-1]["campeao"])
        return False

    monkeypatch.setattr(menu, "menu_pos_temporada", fim_de_temporada)

    menu.carregar_jogo({CAMPEONATO: times})

    assert len(campeoes) == 1
    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2028
    assert dados["time_escolhido"].id == escolhido.id
    assert dados["time_escolhido"].titulos == 2 + (1 if campeoes[0] == escolhido.id else 0)


def test_carregar_entre_temporadas_jogador_campeao_soma_o_titulo_deterministico(monkeypatch, times):
    """B-020, versão determinística: os pênaltis são forçados para o
    `time_a` vencer, e o jogador é sempre o `time_a` nos seus jogos
    (interativo), então ele é campeão sempre. Sem a unificação, o título
    cairia no objeto do elenco base e o save ficaria com 2."""
    import campeonato

    def penaltis_jogador_sempre_vence(time_a, time_b, interativo=False):
        return time_a, 5, 4

    monkeypatch.setattr(campeonato, "disputa_penaltis", penaltis_jogador_sempre_vence)
    nome = persistencia.gerar_nome_save()
    escolhido = persistencia.carregar_equipes()[CAMPEONATO][0]
    escolhido.titulos = 2
    persistencia.salvar_jogo(nome, CAMPEONATO, escolhido, 2027, None, [])
    monkeypatch.setattr("builtins.input", lambda mensagem="": "1")
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: False)

    menu.carregar_jogo({CAMPEONATO: times})

    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["historico"][-1]["campeao"] == escolhido.id
    assert dados["time_escolhido"].titulos == 3
    # O elenco base recebido não foi alterado (unificar devolve lista nova).
    assert next(t for t in times if t.id == escolhido.id).titulos == 0


def test_carregar_entre_temporadas_sorteia_com_o_objeto_do_jogador(monkeypatch, times):
    """B-020: o sorteio do terminal recebe o próprio `time_escolhido`
    carregado (identidade), independente de quem vence."""
    sorteios = []
    sortear_real = menu.sortear_classificados

    def sortear_e_espiar(lista):
        sorteios.append(lista)
        return sortear_real(lista)

    escolhidos = []
    rodadas_real = menu.gerar_rodadas

    def rodadas_e_espiar(classificados, time_escolhido=None, campeonato=""):
        escolhidos.append(time_escolhido)
        return rodadas_real(classificados, time_escolhido, campeonato)

    monkeypatch.setattr(menu, "sortear_classificados", sortear_e_espiar)
    monkeypatch.setattr(menu, "gerar_rodadas", rodadas_e_espiar)
    nome = persistencia.gerar_nome_save()
    escolhido = persistencia.carregar_equipes()[CAMPEONATO][0]
    escolhido.titulos = 2
    persistencia.salvar_jogo(nome, CAMPEONATO, escolhido, 2027, None, [])
    monkeypatch.setattr("builtins.input", lambda mensagem="": "1")
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: False)

    menu.carregar_jogo({CAMPEONATO: times})

    assert len(sorteios) == 1 and len(escolhidos) == 1
    assert escolhidos[0].titulos >= 2
    assert any(time is escolhidos[0] for time in sorteios[0])


# --- 4. Concorrência: duas conexões no mesmo .db ---------------------------


def _salvar_carreira_inicial(times):
    nome = persistencia.gerar_nome_save()
    persistencia.salvar_jogo(nome, CAMPEONATO, times[0], 2026, times[:4])
    return nome


def test_salvar_jogo_funciona_com_outra_conexao_aberta_lendo(times):
    nome = _salvar_carreira_inicial(times)
    caminho = persistencia._caminho_save(nome)

    with abrir(caminho, somente_leitura=True) as leitor:
        antes = leitor.execute("SELECT temporada FROM carreira").fetchone()["temporada"]
        assert antes == 2026

        persistencia.salvar_jogo(nome, CAMPEONATO, times[0], 2026, times[:2])

        # O leitor (fora de transação) já enxerga o retrato novo.
        posicoes = leitor.execute(
            "SELECT time_id FROM classificados ORDER BY posicao"
        ).fetchall()
        assert [linha["time_id"] for linha in posicoes] == _ids(times[:2])

    assert _ids(persistencia.carregar_jogo_salvo(nome)["classificados"]) == _ids(times[:2])
    assert persistencia.excluir_jogo_salvo(nome) is True


def test_carregar_le_o_retrato_anterior_enquanto_outra_conexao_escreve(monkeypatch, times):
    """Outra conexão com `BEGIN IMMEDIATE` (escrita em andamento, sem
    commit): `carregar_jogo_salvo` não trava nem vê o que não foi gravado.
    """
    monkeypatch.setattr(conexao, "TIMEOUT_SEGUNDOS", 0.2)
    nome = _salvar_carreira_inicial(times)
    caminho = persistencia._caminho_save(nome)

    with abrir(caminho, criar=False) as escritor:
        escritor.execute("BEGIN IMMEDIATE")
        escritor.execute("UPDATE carreira SET temporada = ? WHERE id = 1", (9999,))
        escritor.execute("DELETE FROM classificados WHERE posicao > ?", (1,))

        dados = persistencia.carregar_jogo_salvo(nome)
        assert dados is not None
        assert dados["temporada"] == 2026
        assert _ids(dados["classificados"]) == _ids(times[:4])
        assert persistencia.listar_saves() == [nome]

        escritor.rollback()

    assert persistencia.carregar_jogo_salvo(nome)["temporada"] == 2026
    assert persistencia.excluir_jogo_salvo(nome) is True
    assert not os.path.exists(caminho)


def test_salvar_com_leitura_presa_falha_por_timeout_e_mantem_o_save(monkeypatch, times):
    """Robustez: se outra conexão segura uma leitura (transação aberta)
    além do `TIMEOUT_SEGUNDOS`, `salvar_jogo` desiste com `SaveTravado`
    (causa: "database is locked", E-015) e o save anterior fica inteiro
    (rollback).
    """
    monkeypatch.setattr(conexao, "TIMEOUT_SEGUNDOS", 0.2)
    nome = _salvar_carreira_inicial(times)
    caminho = persistencia._caminho_save(nome)
    historico = [{"temporada": 2026, "campeao": times[0].id, "fases": []}]

    with abrir(caminho, somente_leitura=True) as leitor:
        leitor.execute("BEGIN")
        leitor.execute("SELECT temporada FROM carreira").fetchone()

        with pytest.raises(persistencia.SaveTravado) as erro:
            persistencia.salvar_jogo(nome, CAMPEONATO, times[0], 2027, None, historico)
        assert isinstance(erro.value.__cause__, sqlite3.OperationalError)
        assert "locked" in str(erro.value.__cause__)

        leitor.rollback()

    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2026
    assert _ids(dados["classificados"]) == _ids(times[:4])
    assert dados["historico"] == []

    # Sem a leitura presa, a mesma gravação passa.
    persistencia.salvar_jogo(nome, CAMPEONATO, times[0], 2027, None, historico)
    dados = persistencia.carregar_jogo_salvo(nome)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == historico
    assert persistencia.excluir_jogo_salvo(nome) is True
