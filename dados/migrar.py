"""Migrações do esquema: arquivos `NNN_nome.sql` em `dados/migracoes/`.

A versão do banco fica em `PRAGMA user_version`. `migrar()` aplica, em
ordem numérica, as migrações com número maior que essa versão, uma por
transação. Os arquivos `.sql` não têm `BEGIN`/`COMMIT`/`PRAGMA
user_version` — isso é trabalho daqui. Migração já aplicada nunca é
editada: errou, crie outra.
"""

import re
import sqlite3
from pathlib import Path

PASTA_MIGRACOES = Path(__file__).resolve().parent / "migracoes"

# "001_inicial.sql" -> 1. Outros nomes são ignorados.
_PADRAO_ARQUIVO = re.compile(r"^(\d+)_\w+\.sql$")


def _listar_migracoes(pasta: Path | str) -> list[tuple[int, Path]]:
    """Devolve `(numero, caminho)` das migrações da pasta, em ordem
    numérica. Pasta inexistente = nenhuma migração.
    """
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    migracoes = []
    for arquivo in pasta.iterdir():
        encontrado = _PADRAO_ARQUIVO.match(arquivo.name)
        if encontrado and arquivo.is_file():
            migracoes.append((int(encontrado.group(1)), arquivo))
    migracoes.sort(key=lambda item: item[0])
    return migracoes


def versao_atual(pasta: Path | str = PASTA_MIGRACOES) -> int:
    """Versão mais nova do esquema = maior número de migração da pasta
    (0 se não houver nenhuma).
    """
    migracoes = _listar_migracoes(pasta)
    return migracoes[-1][0] if migracoes else 0


def versao_do_banco(conn: sqlite3.Connection) -> int:
    """Lê o `PRAGMA user_version` do banco."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrar(conn: sqlite3.Connection, pasta: Path | str = PASTA_MIGRACOES) -> None:
    """Leva o banco até `versao_atual(pasta)`.

    Cada migração pendente roda numa transação própria junto com a troca
    do `user_version`: se der erro, nada daquele arquivo fica no banco e a
    exceção sobe. Banco mais novo que o jogo → `ValueError`.
    """
    migracoes = _listar_migracoes(pasta)
    mais_nova = migracoes[-1][0] if migracoes else 0
    versao = versao_do_banco(conn)
    if versao > mais_nova:
        raise ValueError(
            f"O banco está na versão {versao}, mais nova que a do jogo "
            f"({mais_nova})."
        )

    for numero, arquivo in migracoes:
        if numero <= versao:
            continue
        script = arquivo.read_text(encoding="utf-8")
        # As quebras de linha isolam um comentário "--" no fim do arquivo,
        # e o ";" extra fecha um último comando sem ponto e vírgula.
        # `numero` vem do nome do arquivo (int), não de entrada do usuário.
        completo = (
            f"BEGIN;\n{script}\n;\n"
            f"PRAGMA user_version = {numero};\n"
            "COMMIT;"
        )
        try:
            conn.executescript(completo)
        except BaseException:
            if conn.in_transaction:
                conn.rollback()
            raise
