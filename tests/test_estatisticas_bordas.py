"""Casos de borda de `estatisticas.py` (E-019-T2), com o histórico no
formato real: montado por `campeonato.registro_da_fase` e lido de volta por
`persistencia.carregar_jogo_salvo`.
"""

import random

import pytest

import persistencia
from campeonato import montar_classificacao, montar_confrontos_fase, registro_da_fase
from equipe import Equipe
from estatisticas import confrontos_do_time, nome_fase_curto, resumo_da_carreira

NOME_SAVE = "1_01_01_2026"


@pytest.fixture
def dir_saves(tmp_path, monkeypatch):
    """Aponta a pasta `saves/` para um diretório de teste (nunca o real)."""
    pasta = tmp_path / "saves"
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(pasta))
    return pasta


def _times(quantidade):
    return [Equipe(f"Time {i}", id=900 + i) for i in range(1, quantidade + 1)]


def _jogar_temporada(times, ano, campeonato="Copa X"):
    """Joga uma temporada inteira (sem time do jogador) pelo fluxo da web e
    devolve o registro dela no formato do histórico.
    """
    classificados = list(times)
    fases = []
    while len(classificados) > 1:
        nome_fase, confrontos, pendente, proximos = montar_confrontos_fase(
            classificados, None, campeonato
        )
        assert pendente is None
        fases.append(registro_da_fase(nome_fase, confrontos))
        classificados = proximos
    return {"temporada": ano, "campeao": classificados[0].id, "fases": fases}


def _contagem_independente(historico, id_time):
    jogos = vitorias = pro = contra = 0
    for temporada in historico:
        for fase in temporada["fases"]:
            for id_a, id_b, id_venc, gols_a, gols_b in fase["confrontos"]:
                if id_time not in (id_a, id_b):
                    continue
                jogos += 1
                vitorias += id_venc == id_time
                pro += gols_a if id_a == id_time else gols_b
                contra += gols_b if id_a == id_time else gols_a
    return jogos, vitorias, pro, contra


@pytest.mark.parametrize("quantidade", [2, 3, 5, 7, 8])
def test_resumo_bate_com_historico_real_salvo_e_carregado(dir_saves, quantidade):
    """Histórico gerado pelo fluxo real (com bye quando ímpar), gravado e
    relido do save: o resumo de cada time bate com uma contagem feita à mão.
    """
    random.seed(1234 + quantidade)
    times = _times(quantidade)
    historico = [_jogar_temporada(times, 2026), _jogar_temporada(times, 2027)]

    persistencia.salvar_jogo(NOME_SAVE, "Copa X", times[0], 2028, None, historico)
    carregado = persistencia.carregar_jogo_salvo(NOME_SAVE)["historico"]
    assert carregado == historico

    for time in times:
        jogos, vitorias, pro, contra = _contagem_independente(carregado, time.id)
        resumo = resumo_da_carreira(carregado, time.id)
        assert resumo["jogos"] == jogos
        assert resumo["vitorias"] == vitorias
        assert resumo["derrotas"] == jogos - vitorias
        assert resumo["gols_marcados"] == pro
        assert resumo["gols_sofridos"] == contra
        assert resumo["titulos"] == sum(t["campeao"] == time.id for t in carregado)
        assert len(list(confrontos_do_time(carregado, time.id))) == jogos


def test_time_com_bye_nao_ganha_jogo_fantasma():
    """3 times: quem fica com o bye na semifinal joga só a final."""
    a, b, c = _times(3)
    historico = [{
        "temporada": 2026,
        "campeao": c.id,
        "fases": [
            registro_da_fase("Semifinal - Copa X", [(a, b, a, 5, 4)]),
            registro_da_fase("Final - Copa X", [(a, c, c, 2, 4)]),
        ],
    }]

    assert list(confrontos_do_time(historico, c.id)) == [
        (2026, "Final", a.id, True, 4, 2),
    ]
    resumo = resumo_da_carreira(historico, c.id)
    assert (resumo["jogos"], resumo["vitorias"], resumo["titulos"]) == (1, 1, 1)
    assert resumo["aproveitamento"] == 100.0


def test_fase_sem_confrontos_e_temporada_sem_chave_fases():
    """Fase com lista de confrontos vazia e temporada sem `fases` não
    quebram nem contam jogo.
    """
    historico = [
        {"temporada": 2026, "campeao": None,
         "fases": [{"nome_fase": "Final - Copa X", "confrontos": []}]},
        {"temporada": 2027, "campeao": 1},
    ]

    assert list(confrontos_do_time(historico, 1)) == []
    resumo = resumo_da_carreira(historico, 1)
    assert resumo["jogos"] == 0
    assert resumo["aproveitamento"] is None
    assert resumo["titulos"] == 1


def test_temporada_em_andamento_montada_como_na_rota():
    """Temporada em andamento montada com `registro_da_fase` sobre objetos
    `Equipe` (como `_temporadas_da_carreira` fará) conta jogos e não título.
    """
    a, b, c, d = _times(4)
    em_andamento = {
        "temporada": 2026,
        "campeao": None,
        "fases": [registro_da_fase("Semifinal - Copa X", [(c, a, a, 3, 5), (b, d, b, 1, 0)])],
    }

    resumo = resumo_da_carreira([em_andamento], a.id)
    assert resumo == {
        "jogos": 1, "vitorias": 1, "derrotas": 0, "aproveitamento": 100.0,
        "gols_marcados": 5, "gols_sofridos": 3, "titulos": 0,
    }


def test_placar_zerado_e_derrota_unica():
    """Derrota por 0 x 0 (decidida no sorteio) conta como jogo e derrota."""
    historico = [{"temporada": 2026, "campeao": 2,
                  "fases": [{"nome_fase": "Final", "confrontos": [[1, 2, 2, 0, 0]]}]}]

    resumo = resumo_da_carreira(historico, 1)
    assert resumo["jogos"] == 1
    assert resumo["derrotas"] == 1
    assert resumo["aproveitamento"] == 0.0
    assert (resumo["gols_marcados"], resumo["gols_sofridos"]) == (0, 0)


@pytest.mark.parametrize("nome", [
    "Final - Copa do Brasil",
    "Oitavas de final - Copa do Mundo 2026",
    "Semifinal",
    "Final - Copa - Edição especial",
    "",
])
def test_nome_fase_curto_igual_a_regra_de_montar_classificacao(nome):
    """Mesma regra de corte usada em `montar_classificacao`."""
    assert nome_fase_curto(nome) == nome.split(" - ")[0]


def test_nome_fase_curto_bate_com_rotulo_da_classificacao():
    """Rótulos de `montar_classificacao` e fases do generator coincidem."""
    a, b, c, d = _times(4)
    fases = [
        registro_da_fase("Semifinal - Copa X", [(a, b, a, 3, 1), (c, d, d, 2, 4)]),
        registro_da_fase("Final - Copa X", [(a, d, a, 5, 4)]),
    ]
    rotulos = [rotulo for rotulo, _ in montar_classificacao(fases)]
    historico = [{"temporada": 2026, "campeao": a.id, "fases": fases}]

    fase_de_b = [fase for _, fase, *_ in confrontos_do_time(historico, b.id)]
    assert fase_de_b == ["Semifinal"]
    assert "Semifinal" in rotulos
