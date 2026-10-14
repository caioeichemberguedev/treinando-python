"""Repositório da carreira: linha da `carreira`, `times` e `classificados`.

A tabela `times` guarda o "retrato" do time escolhido e dos classificados
da temporada em andamento (uma linha por time, pelo id fixo do catálogo).
`gravar_carreira` regrava tudo a cada chamada (retrato completo) e
`ler_carreira` devolve objetos `Equipe`. O catálogo efetivo do adm NÃO é
aplicado aqui — isso é trabalho de quem chama (`persistencia.py`).

Nenhuma função faz commit: a transação é de quem orquestra (`with conn:`).
"""

import json
import sqlite3

from equipe import Equipe

_INSERIR_TIME = (
    "INSERT INTO times (id, nome, financas, fas, titulos, forca, cores) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)

# Se o escolhido também está no chaveamento, vale o retrato do classificado
# (é o objeto que ganha finanças/fãs nas partidas).
_INSERIR_OU_ATUALIZAR_TIME = (
    "INSERT INTO times (id, nome, financas, fas, titulos, forca, cores) "
    "VALUES (?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT(id) DO UPDATE SET "
    "nome = excluded.nome, financas = excluded.financas, fas = excluded.fas, "
    "titulos = excluded.titulos, forca = excluded.forca, cores = excluded.cores"
)


def _conferir_ids(times):
    """Levanta ValueError se algum time não tiver id (antes de qualquer SQL)."""
    for time in times:
        if time.id is None:
            raise ValueError(f"Time sem id não pode ser salvo na carreira: {time.nome}")


def _time_para_linha(time):
    """Converte uma `Equipe` na tupla de parâmetros de `times`."""
    cores = json.dumps(time.cores) if time.cores is not None else None
    return (time.id, time.nome, time.financas, time.fas, time.titulos, time.forca, cores)


def _linha_para_time(linha):
    """Converte uma linha de `times` (sqlite3.Row) numa `Equipe` nova."""
    cores = json.loads(linha["cores"]) if linha["cores"] is not None else None
    return Equipe(
        linha["nome"],
        financas=linha["financas"],
        fas=linha["fas"],
        titulos=linha["titulos"],
        forca=linha["forca"],
        cores=cores,
        id=linha["id"],
    )


def gravar_carreira(
    conn: sqlite3.Connection,
    campeonato: str,
    temporada: int,
    time_escolhido: Equipe,
    classificados: list[Equipe] | None,
) -> None:
    """Regrava a carreira inteira (retrato completo). Não faz commit.

    `classificados=None` = temporada nova, chaveamento ainda não sorteado.
    Time sem id → ValueError antes de qualquer SQL.
    """
    lista_classificados = list(classificados) if classificados is not None else []
    _conferir_ids([time_escolhido, *lista_classificados])

    # Ordem por causa das chaves estrangeiras: quem aponta para `times`
    # (classificados, carreira) sai antes.
    conn.execute("DELETE FROM classificados")
    conn.execute("DELETE FROM carreira")
    conn.execute("DELETE FROM times")

    conn.execute(_INSERIR_TIME, _time_para_linha(time_escolhido))
    conn.executemany(
        _INSERIR_OU_ATUALIZAR_TIME,
        [_time_para_linha(time) for time in lista_classificados],
    )
    conn.execute(
        "INSERT INTO carreira (id, campeonato, temporada, time_escolhido_id, chaveamento_sorteado) "
        "VALUES (1, ?, ?, ?, ?)",
        (campeonato, temporada, time_escolhido.id, 0 if classificados is None else 1),
    )
    conn.executemany(
        "INSERT INTO classificados (posicao, time_id) VALUES (?, ?)",
        [(posicao, time.id) for posicao, time in enumerate(lista_classificados, start=1)],
    )


def ler_carreira(conn: sqlite3.Connection) -> dict | None:
    """Lê a carreira gravada, ou None se não houver linha em `carreira`.

    Devolve {"campeonato", "temporada", "time_escolhido": Equipe,
    "classificados": list[Equipe] | None}. O escolhido e cada classificado
    são objetos `Equipe` separados (iguais por id quando for o mesmo time).
    """
    carreira = conn.execute(
        "SELECT campeonato, temporada, time_escolhido_id, chaveamento_sorteado "
        "FROM carreira WHERE id = 1"
    ).fetchone()
    if carreira is None:
        return None

    linha_escolhido = conn.execute(
        "SELECT id, nome, financas, fas, titulos, forca, cores "
        "FROM times WHERE id = ?",
        (carreira["time_escolhido_id"],),
    ).fetchone()

    classificados = None
    if carreira["chaveamento_sorteado"]:
        linhas = conn.execute(
            "SELECT times.id, times.nome, times.financas, times.fas, "
            "times.titulos, times.forca, times.cores "
            "FROM classificados JOIN times ON times.id = classificados.time_id "
            "ORDER BY classificados.posicao"
        ).fetchall()
        classificados = [_linha_para_time(linha) for linha in linhas]

    return {
        "campeonato": carreira["campeonato"],
        "temporada": carreira["temporada"],
        "time_escolhido": _linha_para_time(linha_escolhido),
        "classificados": classificados,
    }
