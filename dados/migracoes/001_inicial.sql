-- Migração 001 — esquema inicial das carreiras salvas (E-013).
--
-- Cada carreira é um arquivo .db próprio em saves/. Este script só cria as
-- tabelas e os índices: a transação e o número da versão do banco ficam a
-- cargo do dados/migrar.py, que envolve este arquivo ao aplicá-lo.
--
-- Os ids de time são os ids fixos do catálogo (ID-007), não autoincremento.


-- Cópia própria dos times da carreira (o "retrato" do time escolhido e dos
-- classificados). O nome e as cores aqui são só retrato: na tela, o nome e
-- as cores saem sempre do catálogo efetivo, resolvidos pelo id.
CREATE TABLE times (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    financas INTEGER NOT NULL CHECK (financas >= 0),
    fas INTEGER NOT NULL CHECK (fas >= 0),
    titulos INTEGER NOT NULL DEFAULT 0 CHECK (titulos >= 0),
    forca INTEGER NOT NULL CHECK (forca BETWEEN 0 AND 100),
    cores TEXT  -- lista em JSON, ex.: '["#FF0000", "#FFFFFF"]', ou NULL
);

-- A carreira deste arquivo: sempre uma linha só (id = 1).
-- chaveamento_sorteado = 0 quer dizer "temporada nova, ainda sem
-- chaveamento" (classificados = None); 1 quer dizer que as linhas de
-- classificados valem, na ordem de posicao.
CREATE TABLE carreira (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    campeonato TEXT NOT NULL,
    temporada INTEGER NOT NULL CHECK (temporada > 0),
    time_escolhido_id INTEGER NOT NULL REFERENCES times(id),
    chaveamento_sorteado INTEGER NOT NULL CHECK (chaveamento_sorteado IN (0, 1))
);

-- Ordem do chaveamento da temporada em andamento (posicao 1..N).
-- Cada time aparece no máximo uma vez.
CREATE TABLE classificados (
    posicao INTEGER PRIMARY KEY CHECK (posicao >= 1),
    time_id INTEGER NOT NULL UNIQUE REFERENCES times(id)
);

-- Histórico: uma linha por temporada concluída, na ordem em que foi
-- jogada (ORDER BY id). campeao_id é coluna própria porque o histórico
-- aceita temporada sem fases. Os ids de time do histórico não apontam para
-- a tabela times: quem é dono da identidade dos times é o catálogo, e os
-- eliminados de temporadas antigas não estão em times.
CREATE TABLE temporadas (
    id INTEGER PRIMARY KEY,
    ano INTEGER NOT NULL UNIQUE,  -- o "temporada" do dicionário do save
    campeao_id INTEGER NOT NULL
);

-- Fases de cada temporada (oitavas, quartas, ...), na ordem 1..N.
-- Apagar a temporada apaga as fases dela (cascata).
CREATE TABLE fases (
    id INTEGER PRIMARY KEY,
    temporada_id INTEGER NOT NULL REFERENCES temporadas(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL CHECK (ordem >= 1),
    nome TEXT NOT NULL,
    UNIQUE (temporada_id, ordem)
);

-- Confrontos de cada fase, na ordem 1..N. O vencedor precisa ser um dos
-- dois times e um time não enfrenta a si mesmo. Apagar a fase apaga os
-- confrontos dela (cascata).
CREATE TABLE confrontos (
    id INTEGER PRIMARY KEY,
    fase_id INTEGER NOT NULL REFERENCES fases(id) ON DELETE CASCADE,
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

-- Índices para as buscas "fases de uma temporada" e "confrontos de uma
-- fase" (e para a cascata não varrer a tabela inteira).
CREATE INDEX idx_fases_temporada ON fases(temporada_id);
CREATE INDEX idx_confrontos_fase ON confrontos(fase_id);
