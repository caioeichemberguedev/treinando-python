import pytest

import menu
from equipe import Equipe


def _simular_teclado(monkeypatch, respostas):
    """Faz `input()` devolver, em ordem, cada item de `respostas` — como se o
    jogador tivesse digitado essas linhas no terminal.
    """
    entradas = iter(respostas)
    monkeypatch.setattr("builtins.input", lambda _mensagem="": next(entradas))


@pytest.fixture
def chamadas_salvar(monkeypatch):
    """Troca `menu.salvar_equipes` por um registrador — os testes nunca
    gravam no `equipes.json` real. Devolve a lista de chamadas feitas.
    """
    chamadas = []
    monkeypatch.setattr(menu, "salvar_equipes", lambda equipes: chamadas.append(equipes))
    return chamadas


@pytest.fixture
def equipes():
    return {
        "Campeonato Teste": [
            Equipe("Time A", forca=50),
            Equipe("Time B", forca=60),
            Equipe("Time C", forca=70),
        ],
    }


def test_opcoes_antigas_de_elenco_caem_em_opcao_invalida(monkeypatch, capsys, equipes, chamadas_salvar):
    """`a`/`r`/`n` (adicionar/remover/renomear) não existem mais: cada uma
    mostra "Opção inválida." e o elenco não muda.
    """
    _simular_teclado(monkeypatch, ["1", "a", "r", "n", "v", "n"])
    nomes_antes = [time.nome for time in equipes["Campeonato Teste"]]

    menu.editar_equipes(equipes)

    assert [time.nome for time in equipes["Campeonato Teste"]] == nomes_antes
    assert chamadas_salvar == []
    assert capsys.readouterr().out.count("Opção inválida.") == 3


def test_listagem_mostra_so_editar_e_voltar(monkeypatch, capsys, equipes, chamadas_salvar):
    """O menu de equipes não oferece mais adicionar/remover/renomear."""
    _simular_teclado(monkeypatch, ["1", "v", "n"])

    menu.editar_equipes(equipes)

    saida = capsys.readouterr().out
    assert "Adicionar equipe" not in saida
    assert "Remover equipe" not in saida
    assert "Renomear equipe" not in saida
    assert "Editar finanças/fãs/força" in saida


def test_editar_forca_sem_saves_continua_funcionando(monkeypatch, equipes, chamadas_salvar):
    """Sem carreira salva, a opção `e` edita a força e salva o elenco."""
    monkeypatch.setattr(menu, "listar_saves", lambda: [])
    _simular_teclado(monkeypatch, ["1", "e", "1", "3", "77", "v", "v", "n"])

    menu.editar_equipes(equipes)

    assert equipes["Campeonato Teste"][0].forca == 77
    assert len(chamadas_salvar) == 1


def test_editar_com_saves_edita_e_salva_normalmente(monkeypatch, capsys, equipes, chamadas_salvar):
    """Com carreira salva, a opção `e` também edita e salva o elenco base —
    cada carreira já guarda sua própria cópia dos times.
    """
    monkeypatch.setattr(menu, "listar_saves", lambda: ["x"])
    _simular_teclado(monkeypatch, ["1", "e", "1", "3", "77", "v", "v", "n"])

    menu.editar_equipes(equipes)

    assert equipes["Campeonato Teste"][0].forca == 77
    assert len(chamadas_salvar) == 1
    assert "Não é possível editar" not in capsys.readouterr().out


def test_listagem_mostra_aviso_de_carreiras_novas(monkeypatch, capsys, equipes, chamadas_salvar):
    """A tela de equipes avisa que a edição só vale para carreiras novas."""
    _simular_teclado(monkeypatch, ["1", "v", "n"])

    menu.editar_equipes(equipes)

    assert "carreiras novas" in capsys.readouterr().out


def test_rodar_temporada_grava_historico_com_ids(monkeypatch):
    """O histórico passado ao último `salvar_jogo` guarda o campeão e os
    times de cada confronto pelo `id` (int), não pelo nome.
    """
    chamadas = []
    monkeypatch.setattr(menu, "salvar_jogo", lambda *args: chamadas.append(args))
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *args: False)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    monkeypatch.setattr("builtins.input", lambda _mensagem="": "1")
    time_a = Equipe("Time A", id=901)
    time_b = Equipe("Time B", id=902)

    menu.rodar_temporada("1_01_01_2026", "Campeonato Teste", time_a, 2026, [time_a, time_b], [time_a, time_b])

    historico = chamadas[-1][5]
    assert len(historico) == 1
    temporada_info = historico[0]
    assert type(temporada_info["campeao"]) is int
    assert temporada_info["campeao"] in (901, 902)
    for fase in temporada_info["fases"]:
        for confronto in fase["confrontos"]:
            assert len(confronto) == 5
            assert all(type(valor) is int for valor in confronto)
    assert temporada_info["fases"][-1]["confrontos"][0][:2] == [901, 902]


@pytest.fixture
def historico_em_ids():
    """Uma temporada com semifinais e final entre os ids 1-4 do catálogo
    (São Paulo, Palmeiras, Corinthians, Santos), campeão São Paulo.
    """
    return [{
        "temporada": 2026,
        "campeao": 1,
        "fases": [
            {"nome_fase": "Semifinal - Copa do Brasil", "confrontos": [[1, 2, 1, 5, 4], [3, 4, 3, 3, 2]]},
            {"nome_fase": "Final - Copa do Brasil", "confrontos": [[1, 3, 1, 4, 3]]},
        ],
    }]


def test_exibir_historico_jogos_mostra_nomes_do_catalogo(monkeypatch, capsys, historico_em_ids):
    _simular_teclado(monkeypatch, ["1"])

    menu.exibir_historico_jogos(historico_em_ids)

    saida = capsys.readouterr().out
    for nome in ("São Paulo", "Palmeiras", "Corinthians", "Santos"):
        assert nome in saida
    assert "Campeão: São Paulo" in saida
    assert "[1," not in saida
    assert "-> 1" not in saida


def test_exibir_campeoes_conta_por_id_e_mostra_nome(capsys, historico_em_ids):
    historico = historico_em_ids + [
        {"temporada": 2027, "campeao": 1, "fases": []},
        {"temporada": 2028, "campeao": 3, "fases": []},
    ]

    menu.exibir_campeoes(historico)

    saida = capsys.readouterr().out
    assert "2026: São Paulo" in saida
    assert "2028: Corinthians" in saida
    assert "São Paulo: 2 título(s)" in saida
    assert "Corinthians: 1 título(s)" in saida


def test_exibir_classificacao_mostra_nomes_do_catalogo(monkeypatch, capsys, historico_em_ids):
    _simular_teclado(monkeypatch, ["1"])

    menu.exibir_classificacao(historico_em_ids)

    saida = capsys.readouterr().out
    assert "Campeão: São Paulo" in saida
    assert "Vice-campeão: Corinthians" in saida
    assert "Semifinal: Palmeiras, Santos" in saida


def test_exibicoes_com_id_desconhecido_mostram_time_numerado(monkeypatch, capsys):
    historico = [{
        "temporada": 2026,
        "campeao": 999,
        "fases": [{"nome_fase": "Final", "confrontos": [[999, 1, 999, 5, 4]]}],
    }]
    _simular_teclado(monkeypatch, ["1", "1"])

    menu.exibir_historico_jogos(historico)
    menu.exibir_campeoes(historico)
    menu.exibir_classificacao(historico)

    saida = capsys.readouterr().out
    assert "Campeão: Time #999" in saida
    assert "2026: Time #999" in saida
    assert "Time #999: 1 título(s)" in saida
    assert "Vice-campeão: São Paulo" in saida
