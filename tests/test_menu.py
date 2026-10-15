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


def _rodar_com_espiao(monkeypatch, *args):
    """Roda `menu.rodar_temporada(*args)` com `salvar_jogo` trocado por um
    espião (`*args`, como no teste acima) e o `input` sempre "1". Devolve
    as chamadas de gravação e os históricos vistos no fim da temporada.
    """
    chamadas = []
    historicos = []

    def fim_de_temporada(campeonato, temporada, campeao, historico):
        historicos.append(historico)
        return False

    monkeypatch.setattr(menu, "salvar_jogo", lambda *a: chamadas.append(a))
    monkeypatch.setattr(menu, "menu_pos_temporada", fim_de_temporada)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    monkeypatch.setattr("builtins.input", lambda _mensagem="": "1")
    menu.rodar_temporada(*args)
    return chamadas, historicos


def _quatro_times():
    return [Equipe(f"Time {letra}", id=900 + n) for n, letra in enumerate("ABCD", start=1)]


def test_rodar_temporada_grava_as_fases_no_meio_e_nao_no_fim(monkeypatch):
    """E-014: a gravação depois da semifinal leva as fases (7º argumento,
    posicional); a do campeão coroado `(temporada+1, None)` vai sem fases.
    """
    times = _quatro_times()
    chamadas, historicos = _rodar_com_espiao(
        monkeypatch, "1_01_01_2026", "Campeonato Teste", times[0], 2026, list(times), times
    )

    meio, fim = chamadas
    assert len(meio[4]) == 2
    assert [len(fase["confrontos"]) for fase in meio[6]] == [2]
    assert fim[3] == 2027 and fim[4] is None
    assert len(fim) == 6  # sem fases_da_temporada
    fases = historicos[0][-1]["fases"]
    assert [len(fase["confrontos"]) for fase in fases] == [2, 1]
    assert fases[0] == meio[6][0]


def test_rodar_temporada_soma_as_fases_carregadas(monkeypatch):
    """Retomada no meio: as fases recebidas vêm antes das jogadas agora, e
    a lista do chamador não é alterada.
    """
    times = _quatro_times()
    semi = {
        "nome_fase": "Semifinal - Campeonato Teste",
        "confrontos": [[901, 902, 901, 1, 0], [903, 904, 903, 2, 1]],
    }
    recebidas = [semi]
    chamadas, historicos = _rodar_com_espiao(
        monkeypatch, "1_01_01_2026", "Campeonato Teste", times[0], 2026, [times[0], times[2]], times, [], recebidas
    )

    fases = historicos[0][-1]["fases"]
    assert [len(fase["confrontos"]) for fase in fases] == [2, 1]
    assert fases[0] == semi
    assert recebidas == [semi]
    assert chamadas[-1][4] is None and len(chamadas[-1]) == 6


def test_rodar_temporada_sorteada_ignora_fases_recebidas(monkeypatch):
    """Com `classificados=None` a temporada é sorteada agora: começa sem
    fases, mesmo que alguma venha por engano.
    """
    times = _quatro_times()
    lixo = [{"nome_fase": "Final - X", "confrontos": [[901, 902, 901, 1, 0]]}]
    chamadas, historicos = _rodar_com_espiao(
        monkeypatch, "1_01_01_2026", "Campeonato Teste", times[0], 2026, None, times, [], lixo
    )

    assert len(chamadas[0]) == 6  # gravação do sorteio, sem fases
    assert [len(fase["confrontos"]) for fase in historicos[0][-1]["fases"]] == [2, 1]


def test_carregar_jogo_repassa_as_fases_do_save(monkeypatch):
    times = _quatro_times()
    fases = [{"nome_fase": "Semifinal - Campeonato Teste", "confrontos": [[901, 902, 901, 1, 0]]}]
    dados = {
        "campeonato": "Campeonato Teste",
        "time_escolhido": times[0],
        "temporada": 2026,
        "classificados": [times[0], times[2]],
        "historico": [],
        "fases_da_temporada": fases,
    }
    chamadas = []
    monkeypatch.setattr(menu, "escolher_save", lambda acao: "1_01_01_2026")
    monkeypatch.setattr(menu, "carregar_jogo_salvo", lambda nome: dados)
    monkeypatch.setattr(menu, "rodar_temporada", lambda *args: chamadas.append(args))

    menu.carregar_jogo({"Campeonato Teste": times})

    assert len(chamadas) == 1
    assert chamadas[0][0] == "1_01_01_2026"
    assert chamadas[0][7] is fases


def test_carregar_jogo_save_sem_chave_de_fases_repassa_lista_vazia(monkeypatch):
    """Borda: dict de save sem `fases_da_temporada` (formato antigo) não quebra."""
    times = _quatro_times()
    dados = {
        "campeonato": "Campeonato Teste",
        "time_escolhido": times[0],
        "temporada": 2026,
        "classificados": [times[0], times[2]],
        "historico": [],
    }
    chamadas = []
    monkeypatch.setattr(menu, "escolher_save", lambda acao: "1_01_01_2026")
    monkeypatch.setattr(menu, "carregar_jogo_salvo", lambda nome: dados)
    monkeypatch.setattr(menu, "rodar_temporada", lambda *args: chamadas.append(args))

    menu.carregar_jogo({"Campeonato Teste": times})

    assert chamadas[0][7] == []


def test_save_travado_no_meio_repete_a_gravacao_com_as_fases(monkeypatch):
    """Borda: save travado na gravação do meio → a nova tentativa leva as
    mesmas fases (E-015-T1 + E-014-T4)."""
    times = _quatro_times()
    chamadas = []
    falhas = [1]

    def salvar_travando_uma_vez(*args):
        chamadas.append(args)
        if len(args) == 7 and falhas[0] > 0:
            falhas[0] -= 1
            raise menu.SaveTravado("travado")

    monkeypatch.setattr(menu, "salvar_jogo", salvar_travando_uma_vez)
    monkeypatch.setattr(menu, "menu_pos_temporada", lambda *a: False)
    monkeypatch.setattr(menu.os, "system", lambda comando: 0)
    monkeypatch.setattr("builtins.input", lambda _mensagem="": "1")

    menu.rodar_temporada("1_01_01_2026", "Campeonato Teste", times[0], 2026, list(times), times)

    meio = [c for c in chamadas if len(c) == 7]
    assert len(meio) == 2
    assert meio[0][6] == meio[1][6]
    assert [len(f["confrontos"]) for f in meio[1][6]] == [2]


def test_rodar_temporada_com_bye_registra_todas_as_fases(monkeypatch):
    """Borda: total ímpar (3 times, um bye) — gravação do meio leva a 1ª
    fase e o histórico termina com todas as fases jogadas."""
    times = _quatro_times()[:3]
    chamadas, historicos = _rodar_com_espiao(
        monkeypatch, "1_01_01_2026", "Campeonato Teste", times[0], 2026, list(times), times
    )

    meio = [c for c in chamadas if len(c) == 7]
    fases = historicos[0][-1]["fases"]
    assert len(fases) == len(meio) + 1
    assert meio[-1][6] == fases[:-1]
    assert chamadas[-1][4] is None and len(chamadas[-1]) == 6


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
