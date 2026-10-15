-- Migração 002 — fases da temporada em andamento (E-014).
--
-- Guarda as fases já jogadas da temporada que ainda não terminou, para que
-- sair no meio e carregar depois não perca as fases jogadas antes de sair.
-- Espelha fases/confrontos da 001, mas sem temporada: em andamento só
-- existe uma por carreira (a da tabela carreira). Não reaproveita
-- temporadas/fases porque temporadas.campeao_id é NOT NULL e porque
-- "temporada concluída" e "temporada em andamento" ficam bem separadas.
--
-- Saves da versão 1 migram sozinhos: as tabelas novas nascem vazias, ou
-- seja, nenhuma fase em andamento (o comportamento de antes).
-- A transação e o número da versão ficam a cargo do dados/migrar.py.


-- Fases da temporada em andamento, na ordem 1..N em que foram jogadas.
CREATE TABLE fases_em_andamento (
    id INTEGER PRIMARY KEY,
    ordem INTEGER NOT NULL UNIQUE CHECK (ordem >= 1),
    nome TEXT NOT NULL
);

-- Confrontos de cada fase em andamento, com as mesmas regras de
-- confrontos (vencedor é um dos dois times, ninguém enfrenta a si mesmo,
-- gols não negativos). Apagar a fase apaga os confrontos dela (cascata).
-- Os ids de time não apontam para times: a identidade vem do catálogo, e
-- os eliminados da temporada não estão em times.
CREATE TABLE confrontos_em_andamento (
    id INTEGER PRIMARY KEY,
    fase_id INTEGER NOT NULL REFERENCES fases_em_andamento(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL CHECK (ordem >= 1),
    time_a_id INTEGER NOT NULL,
    time_b_id INTEGER NOT NULL,
    vencedor_id INTEGER NOT NULL,
    gols_a INTEGER NOT NULL CHECK (gols_a >= 0),
    gols_b INTEGER NOT NULL CHECK (gols_b >= 0),
    CHECK (time_a_id <> time_b_id),
    CHECK (vencedor_id IN (time_a_id, time_b_id)),
    UNIQUE (fase_id, ordem)
);

-- Busca "confrontos de uma fase" e cascata sem varrer a tabela inteira.
CREATE INDEX idx_confrontos_em_andamento_fase ON confrontos_em_andamento(fase_id);
