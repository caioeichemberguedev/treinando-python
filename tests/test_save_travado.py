"""Save travado (E-015-T1): `persistencia.SaveTravado` e a nova tentativa
no terminal (`menu._salvar_com_retentativa`).
"""

import ast
import sqlite3
from pathlib import Path

import pytest

import menu
import persistencia
from dados import conexao
from dados.conexao import abrir
from equipe import Equipe

CAMPEONATO = "Campeonato Teste"
NOME_SAVE = "1_01_01_2026"


@pytest.fixture
def times():
    return [Equipe(f"Time {numero}", id=900 + numero) for numero in range(1, 5)]


def _ler_bytes(caminho):
    return Path(caminho).read_bytes()


# --- persistencia.salvar_jogo ----------------------------------------------


def test_save_travado_por_outra_conexao_levanta_save_travado(monkeypatch, times):
    monkeypatch.setattr(conexao, "TIMEOUT_SEGUNDOS", 0.1)
    persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2026, times)
    caminho = persistencia._caminho_save(NOME_SAVE)
    antes = _ler_bytes(caminho)

    with abrir(caminho, criar=False) as outra:
        outra.execute("BEGIN EXCLUSIVE")
        with pytest.raises(persistencia.SaveTravado) as erro:
            persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2027, None)
        outra.rollback()

    assert isinstance(erro.value.__cause__, sqlite3.OperationalError)
    assert str(erro.value) == persistencia.MENSAGEM_SAVE_TRAVADO
    assert _ler_bytes(caminho) == antes


def test_liberada_a_trava_salvar_volta_a_funcionar(monkeypatch, times):
    monkeypatch.setattr(conexao, "TIMEOUT_SEGUNDOS", 0.1)
    persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2026, times)
    caminho = persistencia._caminho_save(NOME_SAVE)

    with abrir(caminho, criar=False) as outra:
        outra.execute("BEGIN EXCLUSIVE")
        with pytest.raises(persistencia.SaveTravado):
            persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2027, None)
        outra.rollback()

    persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2027, None)
    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None


def test_operational_error_que_nao_e_trava_sobe_intacto(monkeypatch, times):
    def gravar_com_erro_de_disco(*args, **kwargs):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(persistencia, "gravar_carreira", gravar_com_erro_de_disco)

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error") as erro:
        persistencia.salvar_jogo(NOME_SAVE, CAMPEONATO, times[0], 2026, times)
    assert not isinstance(erro.value, persistencia.SaveTravado)


def test_mensagem_com_locked_sem_codigo_conta_como_trava():
    assert persistencia._erro_de_trava(sqlite3.OperationalError("database is locked"))
    assert not persistencia._erro_de_trava(sqlite3.OperationalError("no such table: x"))


# --- terminal (menu.py) ------------------------------------------------------


def _salvar_que_falha(vezes_falhando, chamadas):
    """`salvar_jogo` falso: levanta `SaveTravado` nas primeiras
    `vezes_falhando` chamadas (None = sempre) e registra todas.
    """
    def salvar(*args):
        chamadas.append(args)
        if vezes_falhando is None or len(chamadas) <= vezes_falhando:
            raise persistencia.SaveTravado(persistencia.MENSAGEM_SAVE_TRAVADO)

    return salvar


def test_terminal_enter_tenta_de_novo_ate_gravar(monkeypatch, capsys, times):
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(1, chamadas))
    entradas = iter([""])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))

    gravou = menu._salvar_com_retentativa(NOME_SAVE, CAMPEONATO, times[0], 2026, times)

    assert gravou is True
    assert len(chamadas) == 2
    assert persistencia.MENSAGEM_SAVE_TRAVADO in capsys.readouterr().out


def test_terminal_sair_volta_sem_jogar_a_fase_seguinte(monkeypatch, capsys, times):
    chamadas = []
    fases_exibidas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(None, chamadas))
    monkeypatch.setattr(menu, "exibir_rodada", lambda nome, confrontos: fases_exibidas.append(nome))
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    entradas = iter(["sair"])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))
    # Time do jogador fora do chaveamento: todos os jogos são automáticos.
    fora = Equipe("Time de fora", id=999)

    menu.rodar_temporada(NOME_SAVE, CAMPEONATO, fora, 2026, times, times)

    saida = capsys.readouterr().out
    assert len(fases_exibidas) == 1  # a semifinal; a final não foi jogada
    assert len(chamadas) == 1  # nenhuma gravação depois de desistir
    assert persistencia.MENSAGEM_SAVE_TRAVADO in saida
    assert "O último progresso salvo continua valendo." in saida


def test_novo_jogo_com_save_travado_e_sair_nao_comeca_a_temporada(monkeypatch, times):
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(None, chamadas))
    monkeypatch.setattr(menu, "escolher_campeonato", lambda equipes: CAMPEONATO)
    monkeypatch.setattr(menu, "escolher_time", lambda lista: lista[0])
    monkeypatch.setattr(menu, "gerar_nome_save", lambda: NOME_SAVE)
    temporadas = []
    monkeypatch.setattr(menu, "rodar_temporada", lambda *args: temporadas.append(args))
    entradas = iter(["sair"])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))

    menu.novo_jogo({CAMPEONATO: times})

    assert len(chamadas) == 1
    assert temporadas == []


def test_menu_nao_importa_sqlite3():
    arvore = ast.parse(Path(menu.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
    assert "sqlite3" not in importados


# --- casos de borda (game-tester) -------------------------------------------


def test_codigo_estendido_de_busy_conta_como_trava():
    """`SQLITE_BUSY_SNAPSHOT` (estendido) vira o primário `SQLITE_BUSY`."""
    erro = sqlite3.OperationalError("qualquer texto")
    erro.sqlite_errorcode = sqlite3.SQLITE_BUSY_SNAPSHOT
    assert persistencia._erro_de_trava(erro)
    erro.sqlite_errorcode = sqlite3.SQLITE_LOCKED
    assert persistencia._erro_de_trava(erro)


def test_codigo_que_nao_e_trava_vence_o_texto_locked():
    """Com código do SQLite presente, ele decide (o texto é só reserva)."""
    erro = sqlite3.OperationalError("locked, mas não é trava")
    erro.sqlite_errorcode = sqlite3.SQLITE_IOERR
    assert not persistencia._erro_de_trava(erro)


def test_terminal_varios_enter_ate_gravar_sem_limite(monkeypatch, capsys, times):
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(3, chamadas))
    entradas = iter(["", "", ""])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))

    assert menu._salvar_com_retentativa(NOME_SAVE, CAMPEONATO, times[0], 2026, times) is True
    assert len(chamadas) == 4
    assert capsys.readouterr().out.count(persistencia.MENSAGEM_SAVE_TRAVADO) == 3


def test_terminal_sair_aceita_maiusculas_e_espacos(monkeypatch, capsys, times):
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(None, chamadas))
    entradas = iter(["  SAIR  "])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))

    assert menu._salvar_com_retentativa(NOME_SAVE, CAMPEONATO, times[0], 2026, times) is False
    assert len(chamadas) == 1
    assert "O último progresso salvo continua valendo." in capsys.readouterr().out


def test_terminal_sem_trava_grava_de_primeira_sem_perguntar(monkeypatch, capsys, times):
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(0, chamadas))

    def input_proibido(_mensagem=""):
        raise AssertionError("não deveria perguntar nada")

    monkeypatch.setattr("builtins.input", input_proibido)

    assert menu._salvar_com_retentativa(NOME_SAVE, CAMPEONATO, times[0], 2026, times) is True
    assert len(chamadas) == 1
    assert persistencia.MENSAGEM_SAVE_TRAVADO not in capsys.readouterr().out


def test_terminal_outro_erro_nao_e_engolido_pela_retentativa(monkeypatch, times):
    def salvar_com_outro_erro(*args):
        raise OSError("disco cheio")

    monkeypatch.setattr(menu, "salvar_jogo", salvar_com_outro_erro)
    with pytest.raises(OSError, match="disco cheio"):
        menu._salvar_com_retentativa(NOME_SAVE, CAMPEONATO, times[0], 2026, times)


def test_temporada_nova_com_save_travado_e_sair_nao_joga_nenhuma_fase(monkeypatch, times):
    chamadas = []
    fases_exibidas = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(None, chamadas))
    monkeypatch.setattr(menu, "exibir_rodada", lambda nome, confrontos: fases_exibidas.append(nome))
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    entradas = iter(["sair"])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))
    fora = Equipe("Time de fora", id=999)

    menu.rodar_temporada(NOME_SAVE, CAMPEONATO, fora, 2027, None, times)

    assert fases_exibidas == []
    assert len(chamadas) == 1


def test_final_com_save_travado_e_sair_nao_abre_menu_pos_temporada(monkeypatch, capsys, times):
    chamadas = []
    pos_temporada = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(None, chamadas))
    monkeypatch.setattr(menu, "exibir_rodada", lambda nome, confrontos: None)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: pos_temporada.append(args) or True)
    entradas = iter(["sair"])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))
    fora = Equipe("Time de fora", id=999)

    # Só dois times: a primeira fase já é a final.
    menu.rodar_temporada(NOME_SAVE, CAMPEONATO, fora, 2026, times[:2], times)

    assert len(chamadas) == 1
    assert chamadas[0][3] == 2027 and chamadas[0][4] is None  # retrato da próxima temporada
    assert pos_temporada == []
    assert "O último progresso salvo continua valendo." in capsys.readouterr().out


def test_final_com_save_travado_e_enter_segue_para_o_menu_pos_temporada(monkeypatch, times):
    chamadas = []
    pos_temporada = []
    monkeypatch.setattr(menu, "salvar_jogo", _salvar_que_falha(1, chamadas))
    monkeypatch.setattr(menu, "exibir_rodada", lambda nome, confrontos: None)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: pos_temporada.append(args) or False)
    entradas = iter([""])
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))
    fora = Equipe("Time de fora", id=999)

    menu.rodar_temporada(NOME_SAVE, CAMPEONATO, fora, 2026, times[:2], times)

    assert len(chamadas) == 2
    assert chamadas[0] == chamadas[1]  # tentou de novo com o mesmo retrato
    assert len(pos_temporada) == 1
