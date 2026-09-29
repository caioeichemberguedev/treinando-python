from equipe import Equipe
from web.estado import iniciar_jogo, obter_jogo


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
