"""Fixtures compartilhadas por toda a suíte."""

import pytest

import catalogo


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
