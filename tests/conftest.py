"""Fixtures compartilhadas por toda a suíte."""

import pytest

import catalogo
import persistencia


@pytest.fixture(autouse=True)
def catalogo_isolado(tmp_path, monkeypatch):
    """Aponta o catálogo do adm para um arquivo temporário (inexistente no
    início) e limpa o cache: nenhum teste lê ou grava o `catalogo_times.json`
    real, então edições feitas pelo adm não quebram a suíte.
    """
    monkeypatch.setattr(
        catalogo, "ARQUIVO_CATALOGO", str(tmp_path / "catalogo_times.json")
    )
    catalogo.limpar_cache()
    yield
    catalogo.limpar_cache()


@pytest.fixture(autouse=True)
def saves_isolados(tmp_path, monkeypatch):
    """Aponta `persistencia.DIR_SAVES` para `tmp_path / "saves"` (inexistente
    no início) em todos os testes.

    A web passa a gravar a carreira a cada fase (E-018), então qualquer teste
    que jogue pelo navegador (`/novo-jogo/time`, `/fase`...) criaria arquivos
    no `saves/` real do jogador. Com esta fixture, nenhum teste lê ou grava
    carreiras de verdade. Fixtures de módulo que já fazem o mesmo
    `monkeypatch` continuam valendo (rodam depois e usam o mesmo `tmp_path`).
    """
    monkeypatch.setattr(persistencia, "DIR_SAVES", str(tmp_path / "saves"))
