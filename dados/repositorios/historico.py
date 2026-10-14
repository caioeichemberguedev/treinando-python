"""Repositório do histórico da carreira: temporadas → fases → confrontos.

O histórico em memória (terminal e web) tem o formato:

    [{"temporada": 2026, "campeao": 1,
      "fases": [{"nome_fase": "Final - Copa do Brasil",
                 "confrontos": [[id_a, id_b, id_vencedor, gols_a, gols_b]]}]}]

Aqui ele vira três tabelas ligadas por chave estrangeira. As funções não
fazem commit: quem chama decide a transação (`with conn:`).
"""

import sqlite3


def gravar_historico(conn: sqlite3.Connection, historico: list[dict]) -> None:
    """Substitui o histórico gravado pelo `historico` recebido (retrato
    completo).

    Apaga todas as temporadas — o `ON DELETE CASCADE` leva junto as fases e
    os confrontos — e reinsere tudo na ordem da lista. Fases e confrontos
    ganham `ordem` 1..N na ordem em que aparecem.
    """
    conn.execute("DELETE FROM temporadas")
    for temporada in historico:
        cursor = conn.execute(
            "INSERT INTO temporadas (ano, campeao_id) VALUES (?, ?)",
            (temporada["temporada"], temporada["campeao"]),
        )
        temporada_id = cursor.lastrowid
        for ordem_fase, fase in enumerate(temporada["fases"], start=1):
            cursor = conn.execute(
                "INSERT INTO fases (temporada_id, ordem, nome) VALUES (?, ?, ?)",
                (temporada_id, ordem_fase, fase["nome_fase"]),
            )
            fase_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO confrontos "
                "(fase_id, ordem, time_a_id, time_b_id, vencedor_id, gols_a, gols_b) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (fase_id, ordem_confronto, *confronto)
                    for ordem_confronto, confronto in enumerate(fase["confrontos"], start=1)
                ],
            )


def ler_historico(conn: sqlite3.Connection) -> list[dict]:
    """Lê o histórico no mesmo formato da memória (confrontos como listas).

    Temporadas na ordem em que foram gravadas; fases e confrontos pela
    coluna `ordem`. Uma consulta por nível: fácil de ler, e o volume é
    pequeno (~31 confrontos por temporada).
    """
    historico = []
    temporadas = conn.execute(
        "SELECT id, ano, campeao_id FROM temporadas ORDER BY id"
    ).fetchall()
    for linha_temporada in temporadas:
        fases = []
        linhas_fases = conn.execute(
            "SELECT id, nome FROM fases WHERE temporada_id = ? ORDER BY ordem",
            (linha_temporada["id"],),
        ).fetchall()
        for linha_fase in linhas_fases:
            linhas_confrontos = conn.execute(
                "SELECT time_a_id, time_b_id, vencedor_id, gols_a, gols_b "
                "FROM confrontos WHERE fase_id = ? ORDER BY ordem",
                (linha_fase["id"],),
            ).fetchall()
            fases.append({
                "nome_fase": linha_fase["nome"],
                "confrontos": [list(linha) for linha in linhas_confrontos],
            })
        historico.append({
            "temporada": linha_temporada["ano"],
            "campeao": linha_temporada["campeao_id"],
            "fases": fases,
        })
    return historico
