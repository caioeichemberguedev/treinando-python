"""Abertura de conexões SQLite com as configurações do projeto.

Toda conexão do jogo sai de `conectar()` (ou de `abrir()`, que também
fecha). Atenção: `with sqlite3.connect(...)` NÃO fecha a conexão — só faz
commit/rollback. No Windows, uma conexão esquecida aberta impede excluir o
arquivo do save, então fora dos testes em memória use sempre `abrir()`.
"""

import contextlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path

# Quanto tempo uma conexão espera outra liberar o banco antes de desistir
# com "database is locked" (ex.: web lendo enquanto o terminal grava).
TIMEOUT_SEGUNDOS = 5

MEMORIA = ":memory:"


def conectar(
    caminho: Path | str,
    criar: bool = True,
    somente_leitura: bool = False,
) -> sqlite3.Connection:
    """Abre o banco em `caminho` com `row_factory = sqlite3.Row` e
    `PRAGMA foreign_keys = ON`.

    - `criar=True` (padrão): cria o arquivo se ele não existir.
    - `criar=False`: o arquivo precisa existir; senão,
      `sqlite3.OperationalError` (e nada é criado no disco).
    - `somente_leitura=True`: abre sem permissão de escrita (nunca cria).
    """
    if str(caminho) == MEMORIA:
        conn = sqlite3.connect(MEMORIA, timeout=TIMEOUT_SEGUNDOS)
    elif somente_leitura or not criar:
        modo = "ro" if somente_leitura else "rw"
        uri = f"{Path(caminho).resolve().as_uri()}?mode={modo}"
        conn = sqlite3.connect(uri, uri=True, timeout=TIMEOUT_SEGUNDOS)
    else:
        conn = sqlite3.connect(caminho, timeout=TIMEOUT_SEGUNDOS)

    try:
        conn.row_factory = sqlite3.Row
        # O SQLite vem com as chaves estrangeiras DESLIGADAS por padrão.
        conn.execute("PRAGMA foreign_keys = ON")
    except BaseException:
        conn.close()
        raise
    return conn


@contextlib.contextmanager
def abrir(
    caminho: Path | str,
    criar: bool = True,
    somente_leitura: bool = False,
) -> Iterator[sqlite3.Connection]:
    """Gerenciador de contexto: entrega a conexão de `conectar()` e fecha
    no fim do `with`, mesmo se uma exceção sair de dentro dele.

    Não faz commit: para gravar, use `with conn:` dentro do bloco.
    """
    conn = conectar(caminho, criar=criar, somente_leitura=somente_leitura)
    try:
        yield conn
    finally:
        conn.close()
