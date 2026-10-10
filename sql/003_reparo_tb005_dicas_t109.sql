-- ═══════════════════════════════════════════════════════════════════════════
-- REPARO: as dicas antigas na desafio_dia.tb005_poder_consumido (T109)
-- ═══════════════════════════════════════════════════════════════════════════
--
-- ⚠️ ESCRITA NO BANCO: quem roda e o DONO (no `prd` so ele escreve). O
-- assistente entrega o script e nao o executa.
--
-- POR QUE EXISTE
--   Ate o app 1.3.0 a dica do desafio era enviada no meio da partida com o
--   `co_evento` dela, que so nasce na 1a leva da gravacao: o envio desistia em
--   silencio, e a `tb005` chegou a 10/10/2026 com ZERO linhas no `prd`
--   (docs/DECISOES-do-dono.md §8zzo, no frontend). Desde a T109 o servidor
--   grava as linhas sozinho, a partir de `qt_usos_poder` da partida, ao gravar
--   a tentativa. Este script aplica A MESMA REGRA as tentativas que chegaram
--   antes dela.
--
-- A REGRA (a mesma de SQL_GRAVAR_DICAS_DA_PARTIDA, api/desafios/repositorio_envio.py)
--   · uma linha por dica: nu_grau de 1 ate qt_usos_poder, no maximo 2
--     (o ck001_grau so aceita 1 e 2; o teto e de 2 por TENTATIVA);
--   · nu_tipo_poder = 1 ('dica' na dimensao tb902_tipo_poder);
--   · dh_consumo = o INICIO da tentativa (aproximacao: o instante real de cada
--     dica nao chegou ao servidor);
--   · ON CONFLICT DO NOTHING: rodar duas vezes nao duplica nada.
--
-- O QUE ELE NAO FAZ, DE PROPOSITO
--   ⚠️ Lido no `prd` em 10/10/2026: 4 partidas de desafio com dica, e 3 delas
--   viraram tentativa. A 4a (21:00 UTC, 1 dica) foi ABANDONADA, e a 1.3.0 nao
--   transforma partida abandonada em tentativa - nao ha linha em
--   tb002_tentativa onde pendurar a dica. Criar a tentativa agora mudaria a
--   contagem de tentativas de um dia ja pontuado; nao e reparo, e outra regra
--   (a abandonada vira tentativa so a partida do app 1.4, T110).
--   ⛔ Nenhum XP e recalculado: o extrato e a resolucao gravados ficam como estao.
--
-- COMO RODAR
--   1. Rode o bloco inteiro. Ele abre a transacao, mostra o ANTES, insere e
--      mostra o DEPOIS - e PARA, sem COMMIT.
--   2. Confira: o DEPOIS deve ter 3 linhas a mais que o ANTES (no `prd` de
--      10/10/2026: 0 -> 3), todas com nu_grau = 1.
--   3. Se bater, rode COMMIT; se nao, ROLLBACK e me mande a saida.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ANTES: quantas dicas a tb005 tem, e quantas a partida diz que houve.
SELECT
  (SELECT count(*) FROM desafio_dia.vw005_poder_consumido
    WHERE co_tipo_poder = 'dica')                              AS linhas_na_tb005,
  (SELECT COALESCE(sum(LEAST(p.qt_usos_poder, 2)), 0)
     FROM desafio_dia.vw002_tentativa t
     JOIN partida.vw001_partida p ON p.id_partida = t.id_partida
    WHERE p.qt_usos_poder > 0)                                 AS dicas_nas_tentativas;

-- O REPARO. `CROSS JOIN LATERAL generate_series(...)` gera, para CADA
-- tentativa, a sequencia 1, 2, ... ate a quantidade de dicas dela - uma linha
-- por grau.
INSERT INTO desafio_dia.tb005_poder_consumido
       (id_tentativa, nu_tipo_poder, nu_grau, dh_consumo)
SELECT t.id_tentativa, 1, g.nu_grau, t.dh_inicio
  FROM desafio_dia.vw002_tentativa t
  JOIN partida.vw001_partida p ON p.id_partida = t.id_partida
 CROSS JOIN LATERAL generate_series(1, LEAST(p.qt_usos_poder, 2)) AS g(nu_grau)
 WHERE p.qt_usos_poder > 0
ON CONFLICT (id_tentativa, nu_tipo_poder, nu_grau) DO NOTHING;

-- DEPOIS: as linhas, uma a uma, para conferir.
SELECT t.dh_inicio, t.ic_resolveu, c.nu_grau, c.dh_consumo
  FROM desafio_dia.vw005_poder_consumido c
  JOIN desafio_dia.vw002_tentativa t ON t.id_tentativa = c.id_tentativa
 WHERE c.co_tipo_poder = 'dica'
 ORDER BY t.dh_inicio, c.nu_grau;

-- ⚠️ A transacao continua ABERTA. Confira e rode COMMIT (ou ROLLBACK).
