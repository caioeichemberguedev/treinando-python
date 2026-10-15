import os

import pytest

import persistencia
from equipe import Equipe
from web.estado import encerrar_jogo, iniciar_jogo, obter_jogo, salvar_jogo_em_andamento

NOME_SAVE = "3_01_01_2026"


def _time_escolhido():
    return Equipe("Time A")


def _classificados():
    return [Equipe("Time A"), Equipe("Time B")]


def test_iniciar_jogo_sem_historico_comeca_com_lista_vazia():
    iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados())

    assert obter_jogo().historico == []


def test_iniciar_jogo_com_historico_usa_os_dados_recebidos():
    historico = [{"temporada": 2026, "campeao": "Time A", "fases": []}]

    iniciar_jogo("Campeonato Teste", _time_escolhido(), 2027, _classificados(), historico=historico)

    assert obter_jogo().historico == historico


def test_iniciar_jogo_copia_o_historico_recebido_em_vez_de_guardar_a_referencia():
    historico = [{"temporada": 2026, "campeao": "Time A", "fases": []}]

    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2027, _classificados(), historico=historico)

    assert jogo.historico is not historico

    historico.append({"temporada": 2027, "campeao": "Time B", "fases": []})
    assert len(jogo.historico) == 1

    jogo.historico.append({"temporada": 2028, "campeao": "Time C", "fases": []})
    assert len(historico) == 2


def test_iniciar_jogo_sem_times_do_campeonato_comeca_com_lista_vazia():
    iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados())

    assert obter_jogo().times_do_campeonato == []


def test_iniciar_jogo_guarda_times_do_campeonato_por_identidade_mas_copia_a_lista():
    time_a = Equipe("Time A")
    time_b = Equipe("Time B")
    times = [time_a, time_b]

    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, list(times), times_do_campeonato=times)

    assert jogo.times_do_campeonato == times
    assert jogo.times_do_campeonato is not times
    assert jogo.times_do_campeonato[0] is time_a  # mesmo objeto, não uma cópia

    times.append(Equipe("Time C"))
    assert len(jogo.times_do_campeonato) == 2


@pytest.fixture
def dir_saves(tmp_path, monkeypatch):
    """Aponta `saves/` para uma pasta de teste (nunca o `saves/` real)."""
    pasta = tmp_path / "saves"
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(pasta))
    return pasta


def _times_com_id():
    return [Equipe("Time A", id=901), Equipe("Time B", id=902), Equipe("Time C", id=903)]


def test_iniciar_jogo_guarda_o_nome_save():
    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados(), nome_save=NOME_SAVE)

    assert jogo.nome_save == NOME_SAVE
    assert obter_jogo().nome_save == NOME_SAVE


def test_iniciar_jogo_sem_nome_save_fica_none():
    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados())

    assert jogo.nome_save is None


def test_encerrar_jogo_zera_o_jogo_em_andamento():
    iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados(), nome_save=NOME_SAVE)

    encerrar_jogo()

    assert obter_jogo() is None


def test_salvar_jogo_em_andamento_grava_temporada_e_classificados_recebidos(dir_saves):
    time_a, time_b, time_c = _times_com_id()
    historico = [{"temporada": 2025, "campeao": 902, "fases": [
        {"nome_fase": "Final", "confrontos": [[901, 902, 902, 1, 2]]},
    ]}]
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b, time_c],
                        historico=historico, nome_save=NOME_SAVE)

    salvar_jogo_em_andamento(jogo, 2027, [time_c, time_a])

    assert (dir_saves / f"{NOME_SAVE}.db").exists()
    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert dados["campeonato"] == "Campeonato Teste"
    assert dados["time_escolhido"] == time_a
    # Retrato do "depois": vem dos parâmetros, não de jogo.temporada/classificados.
    assert dados["temporada"] == 2027
    assert [time.id for time in dados["classificados"]] == [903, 901]
    assert dados["historico"] == jogo.historico == historico
    # Nada muda no jogo em memória.
    assert jogo.temporada == 2026
    assert [time.id for time in jogo.classificados] == [901, 902, 903]


def test_salvar_jogo_em_andamento_com_classificados_none_grava_temporada_nova(dir_saves):
    time_a, time_b, _ = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b], nome_save=NOME_SAVE)

    salvar_jogo_em_andamento(jogo, 2027, None)

    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert dados["temporada"] == 2027
    assert dados["classificados"] is None
    assert dados["historico"] == []


def test_salvar_jogo_em_andamento_sem_nome_save_nao_grava_nada(dir_saves):
    time_a, time_b, _ = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b])

    salvar_jogo_em_andamento(jogo, 2026, [time_a, time_b])

    assert not dir_saves.exists() or os.listdir(dir_saves) == []
    assert persistencia.listar_saves() == []


def test_salvar_jogo_em_andamento_historico_no_formato_do_terminal(dir_saves):
    # Histórico montado com `registro_da_fase` + `campeao.id`, como o terminal faz.
    from campeonato import registro_da_fase

    time_a, time_b, time_c = _times_com_id()
    fase = registro_da_fase("Final", [(time_a, time_b, time_b, 3, 4)])
    historico = [{"temporada": 2026, "campeao": time_b.id, "fases": [fase]}]
    jogo = iniciar_jogo("Campeonato Teste", time_c, 2026, [time_a, time_b, time_c],
                        historico=historico, nome_save=NOME_SAVE)

    salvar_jogo_em_andamento(jogo, 2027, None)

    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert dados["historico"] == jogo.historico
    assert dados["historico"][0]["fases"][0]["confrontos"] == [[901, 902, 902, 3, 4]]


def test_salvar_jogo_em_andamento_duas_vezes_regrava_o_mesmo_arquivo(dir_saves):
    time_a, time_b, time_c = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b, time_c], nome_save=NOME_SAVE)

    salvar_jogo_em_andamento(jogo, 2026, [time_a, time_b, time_c])
    salvar_jogo_em_andamento(jogo, 2026, [time_a])

    assert sorted(os.listdir(dir_saves)) == [f"{NOME_SAVE}.db"]
    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert [time.id for time in dados["classificados"]] == [901]


def test_novo_iniciar_jogo_sem_nome_save_nao_herda_o_nome_anterior():
    iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados(), nome_save=NOME_SAVE)

    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados())

    assert jogo.nome_save is None


def test_encerrar_jogo_sem_jogo_em_andamento_nao_quebra():
    encerrar_jogo()
    encerrar_jogo()

    assert obter_jogo() is None


# --- E-014-T5: fases da temporada em andamento ---------------------------------

FASES_EM_ANDAMENTO = [
    {"nome_fase": "Semifinal - Campeonato Teste", "confrontos": [[901, 902, 901, 2, 1], [903, 904, 903, 1, 0]]},
]


def test_iniciar_jogo_sem_fases_da_temporada_comeca_com_lista_vazia():
    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados())

    assert jogo.fases_da_temporada == []


def test_iniciar_jogo_copia_as_fases_da_temporada_recebidas():
    fases = list(FASES_EM_ANDAMENTO)

    jogo = iniciar_jogo("Campeonato Teste", _time_escolhido(), 2026, _classificados(), fases_da_temporada=fases)

    assert jogo.fases_da_temporada == FASES_EM_ANDAMENTO
    assert jogo.fases_da_temporada is not fases
    fases.append({"nome_fase": "Final", "confrontos": []})
    assert len(jogo.fases_da_temporada) == 1


def test_salvar_jogo_em_andamento_no_meio_grava_as_fases_da_temporada(dir_saves):
    time_a, time_b, _ = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b], nome_save=NOME_SAVE,
                        fases_da_temporada=FASES_EM_ANDAMENTO)

    salvar_jogo_em_andamento(jogo, 2026, [time_a, time_b])

    assert persistencia.carregar_jogo_salvo(NOME_SAVE)["fases_da_temporada"] == FASES_EM_ANDAMENTO


def test_salvar_jogo_em_andamento_com_classificados_none_grava_fases_vazias(dir_saves):
    time_a, time_b, _ = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b], nome_save=NOME_SAVE,
                        fases_da_temporada=FASES_EM_ANDAMENTO)
    salvar_jogo_em_andamento(jogo, 2026, [time_a, time_b])

    salvar_jogo_em_andamento(jogo, 2027, None)

    dados = persistencia.carregar_jogo_salvo(NOME_SAVE)
    assert dados["classificados"] is None
    assert dados["fases_da_temporada"] == []
    assert jogo.fases_da_temporada == FASES_EM_ANDAMENTO  # a memória não muda


def test_salvar_jogo_em_andamento_com_fases_explicitas_usa_as_recebidas(dir_saves):
    """A nova tentativa do save pendente (E-015) grava as fases do momento
    da falha, não as da memória atual."""
    time_a, time_b, _ = _times_com_id()
    jogo = iniciar_jogo("Campeonato Teste", time_a, 2026, [time_a, time_b], nome_save=NOME_SAVE,
                        fases_da_temporada=FASES_EM_ANDAMENTO)

    salvar_jogo_em_andamento(jogo, 2026, [time_a, time_b], [])

    assert persistencia.carregar_jogo_salvo(NOME_SAVE)["fases_da_temporada"] == []
