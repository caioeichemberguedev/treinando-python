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
    chamada).
    """
    chamadas = []
    salvar_real = persistencia.salvar_jogo

    def salvar_e_registrar(nome_save, campeonato, time_escolhido, temporada, classificados, historico=None):
        chamadas.append({
            "temporada": temporada,
            "classificados": None if classificados is None else _ids(classificados),
        })
        salvar_real(nome_save, campeonato, time_escolhido, temporada, classificados, historico)

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
    além do `TIMEOUT_SEGUNDOS`, `salvar_jogo` desiste com "database is
    locked" e o save anterior fica inteiro (rollback).
    """
    monkeypatch.setattr(conexao, "TIMEOUT_SEGUNDOS", 0.2)
    nome = _salvar_carreira_inicial(times)
    caminho = persistencia._caminho_save(nome)
    historico = [{"temporada": 2026, "campeao": times[0].id, "fases": []}]

    with abrir(caminho, somente_leitura=True) as leitor:
        leitor.execute("BEGIN")
        leitor.execute("SELECT temporada FROM carreira").fetchone()

        with pytest.raises(sqlite3.OperationalError, match="locked"):
            persistencia.salvar_jogo(nome, CAMPEONATO, times[0], 2027, None, historico)

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
