"""Fixtures da camada de dados (`dados/`)."""

import pytest

from dados.conexao import conectar
from dados.migrar import migrar


@pytest.fixture
def conn():
    """Banco em memória já migrado até a versão atual; fecha no fim."""
    conexao = conectar(":memory:")
    migrar(conexao)
    yield conexao
    conexao.close()
