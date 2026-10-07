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


def _sem_saves(monkeypatch):
    monkeypatch.setattr(menu, "listar_saves", lambda: [])


def test_opcoes_antigas_de_elenco_caem_em_opcao_invalida(monkeypatch, capsys, equipes, chamadas_salvar):
    """`a`/`r`/`n` (adicionar/remover/renomear) não existem mais: cada uma
    mostra "Opção inválida." e o elenco não muda.
    """
    _sem_saves(monkeypatch)
    _simular_teclado(monkeypatch, ["1", "a", "r", "n", "v", "n"])
    nomes_antes = [time.nome for time in equipes["Campeonato Teste"]]

    menu.editar_equipes(equipes)

    assert [time.nome for time in equipes["Campeonato Teste"]] == nomes_antes
    assert chamadas_salvar == []
    assert capsys.readouterr().out.count("Opção inválida.") == 3


def test_listagem_mostra_so_editar_e_voltar(monkeypatch, capsys, equipes, chamadas_salvar):
    """O menu de equipes não oferece mais adicionar/remover/renomear."""
    _sem_saves(monkeypatch)
    _simular_teclado(monkeypatch, ["1", "v", "n"])

    menu.editar_equipes(equipes)

    saida = capsys.readouterr().out
    assert "Adicionar equipe" not in saida
    assert "Remover equipe" not in saida
    assert "Renomear equipe" not in saida
    assert "Editar finanças/fãs/força" in saida


def test_editar_forca_sem_saves_continua_funcionando(monkeypatch, equipes, chamadas_salvar):
    """Sem carreira salva, a opção `e` edita a força e salva o elenco."""
    _sem_saves(monkeypatch)
    _simular_teclado(monkeypatch, ["1", "e", "1", "3", "77", "v", "v", "n"])

    menu.editar_equipes(equipes)

    assert equipes["Campeonato Teste"][0].forca == 77
    assert len(chamadas_salvar) == 1


def test_editar_com_saves_mostra_bloqueio_e_nao_altera(monkeypatch, capsys, equipes, chamadas_salvar):
    """Com carreira salva, a opção `e` é bloqueada e nada é alterado."""
    monkeypatch.setattr(menu, "listar_saves", lambda: ["x"])
    _simular_teclado(monkeypatch, ["1", "e", "v", "n"])
    forcas_antes = [time.forca for time in equipes["Campeonato Teste"]]

    menu.editar_equipes(equipes)

    assert [time.forca for time in equipes["Campeonato Teste"]] == forcas_antes
    assert chamadas_salvar == []
    assert "Não é possível editar finanças/fãs/força" in capsys.readouterr().out
