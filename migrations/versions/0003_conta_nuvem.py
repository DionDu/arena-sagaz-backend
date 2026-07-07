"""Conta na Nuvem: schemas partida, jogo_pontinhos e progressao (spec 006)

Cria os schemas do log de partidas (núcleo genérico `partida` + extensão
`jogo_pontinhos`) e da progressão/ranking (`progressao`), conforme o
`data-model.md` APROVADO em `arena-sagaz-frontend/specs/006-conta-nuvem/`
(portão G2). FKs referenciam a fundação 005 (`conta.tb001_usuario`) sem
redefini-la.

Convenção do projeto: a app/serviços LEEM da VIEW `vwNNN_*` e ESCREVEM na
tabela `tbNNN_*`. Por isso toda tabela ganha uma VIEW — 4 delas são SEMÂNTICAS
(derivam/calculam colunas) e as demais são "pass-through" (SELECT *), mantendo a
regra de acesso uniforme (mesmo padrão da 005).

Revision ID: 0003_conta_nuvem
Revises: 0002_vw006_marketing
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op

# Identificadores da revisão (encadeia no head atual, 0002).
revision: str = "0003_conta_nuvem"
down_revision: Union[str, None] = "0002_vw006_marketing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Schemas novos ───────────────────────────────────────────────────────
    op.execute("CREATE SCHEMA IF NOT EXISTS partida")
    op.execute("CREATE SCHEMA IF NOT EXISTS jogo_pontinhos")
    op.execute("CREATE SCHEMA IF NOT EXISTS progressao")

    # ════════════════════════════════════════════════════════════════════════
    # Schema `partida` — núcleo genérico do log (cross-jogos)
    # ════════════════════════════════════════════════════════════════════════

    # tb001_partida — a partida (raiz do evento de upload; dono = J1).
    # `co_evento` UNIQUE é a chave de idempotência do evento inteiro: o
    # `INSERT ... ON CONFLICT (co_evento) DO NOTHING` faz o retry ser no-op.
    op.execute(
        """
        CREATE TABLE partida.tb001_partida (
            id_partida       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            co_evento        UUID        NOT NULL UNIQUE,
            co_jogo          VARCHAR(30) NOT NULL,
            co_variante      VARCHAR(30) NOT NULL,
            co_modo          VARCHAR(20) NOT NULL,
            id_usuario       UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            co_anonimo       UUID,
            id_usuario_j2    UUID
                REFERENCES conta.tb001_usuario(id_usuario),
            co_dificuldade   VARCHAR(10),
            nu_placar_j1     INT         NOT NULL,
            nu_placar_j2     INT         NOT NULL,
            ic_pontua        BOOLEAN     NOT NULL,
            co_status        VARCHAR(15) NOT NULL,
            co_lote_migracao UUID,
            dh_inicio        TIMESTAMPTZ NOT NULL,
            dh_fim           TIMESTAMPTZ,
            CONSTRAINT ck_partida_modo
                CHECK (co_modo IN ('vs_cpu', 'pvp_local', 'pvp_online')),
            CONSTRAINT ck_partida_status
                CHECK (co_status IN ('concluida', 'abandonada', 'em_andamento')),
            CONSTRAINT ck_partida_dificuldade
                CHECK (co_dificuldade IS NULL OR co_dificuldade IN
                       ('facil', 'normal', 'dificil', 'sagaz'))
        )
        """
    )
    # Índices de consulta mais comuns (dono e lote de migração).
    op.execute("CREATE INDEX ix_partida_usuario ON partida.tb001_partida (id_usuario)")
    op.execute(
        "CREATE INDEX ix_partida_lote ON partida.tb001_partida (co_lote_migracao) "
        "WHERE co_lote_migracao IS NOT NULL"
    )

    # tb002_jogada — cada lance da partida (append-only). A ordem é única por
    # partida (uq garante e ainda serve de índice para reconstruir o jogo).
    op.execute(
        """
        CREATE TABLE partida.tb002_jogada (
            id_jogada           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_partida          UUID        NOT NULL
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            nu_ordem            INT         NOT NULL,
            nu_jogador          SMALLINT    NOT NULL,
            dh_jogada           TIMESTAMPTZ NOT NULL,
            nu_timer_ms         INT,
            nu_tempo_decisao_ms INT         NOT NULL,
            co_origem_decisao   VARCHAR(15) NOT NULL,
            CONSTRAINT uq_jogada_ordem UNIQUE (id_partida, nu_ordem),
            CONSTRAINT ck_jogada_jogador CHECK (nu_jogador IN (1, 2)),
            CONSTRAINT ck_jogada_origem
                CHECK (co_origem_decisao IN ('humano', 'cpu', 'timeout_auto'))
        )
        """
    )

    # tb003_xp_partida — XP segmentado por partida (1 partida → N parcelas).
    op.execute(
        """
        CREATE TABLE partida.tb003_xp_partida (
            id_xp_partida UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_partida    UUID        NOT NULL
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            id_usuario    UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            co_anonimo    UUID,
            co_tipo_xp    VARCHAR(20) NOT NULL,
            nu_xp         INT         NOT NULL,
            co_referencia VARCHAR(40),
            dh_registro   TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_xp_tipo CHECK (co_tipo_xp IN
                ('resultado', 'caixas', 'dificuldade',
                 'primeira_vitoria', 'conquista', 'ajuste'))
        )
        """
    )
    op.execute("CREATE INDEX ix_xp_partida ON partida.tb003_xp_partida (id_partida)")
    op.execute("CREATE INDEX ix_xp_usuario ON partida.tb003_xp_partida (id_usuario)")

    # ════════════════════════════════════════════════════════════════════════
    # Schema `jogo_pontinhos` — extensão 1:1 da jogada (telemetria do jogo)
    # ════════════════════════════════════════════════════════════════════════
    # A PK é também FK para a jogada genérica (relação 1:1). Matrizes cruas em
    # arrays nativos do Postgres (INT2[]/REAL[]) — prefixo `ar_` honesto.
    op.execute(
        """
        CREATE TABLE jogo_pontinhos.tb002_jogada (
            id_jogada            UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador           SMALLINT   NOT NULL,
            co_aresta            VARCHAR(15) NOT NULL,
            ar_tabuleiro_antes   SMALLINT[] NOT NULL,
            ar_tabuleiro_apos    SMALLINT[] NOT NULL,
            nu_caixas_fechadas   SMALLINT   NOT NULL,
            co_acao              VARCHAR(30),
            co_situacao          VARCHAR(20),
            ar_probabilidade_cnn REAL[],
            ar_score_busca       REAL[],
            nu_profundidade      INT,
            js_extra             JSONB
        )
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # Schema `progressao` — XP acumulado / ranking (cross-jogos)
    # ════════════════════════════════════════════════════════════════════════

    # tb001_progressao_usuario — 1 linha por usuário (nível/patente são VIEW).
    op.execute(
        """
        CREATE TABLE progressao.tb001_progressao_usuario (
            id_progressao        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario           UUID    NOT NULL UNIQUE
                REFERENCES conta.tb001_usuario(id_usuario),
            co_anonimo           UUID,
            nu_xp_total          BIGINT  NOT NULL DEFAULT 0,
            nu_partidas          INT     NOT NULL DEFAULT 0,
            nu_vitorias          INT     NOT NULL DEFAULT 0,
            nu_derrotas          INT     NOT NULL DEFAULT 0,
            nu_empates           INT     NOT NULL DEFAULT 0,
            nu_sequencia_atual   INT     NOT NULL DEFAULT 0,
            dt_ultimo_dia_jogado DATE,
            ic_visivel_placar    BOOLEAN NOT NULL DEFAULT TRUE,
            dh_atualizacao       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Índice para a ordenação do ranking (XP decrescente).
    op.execute(
        "CREATE INDEX ix_progressao_xp "
        "ON progressao.tb001_progressao_usuario (nu_xp_total DESC)"
    )

    # tb002_conquista_usuario — união idempotente no merge (uq garante).
    op.execute(
        """
        CREATE TABLE progressao.tb002_conquista_usuario (
            id_conquista_usuario UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_usuario     UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            co_conquista   VARCHAR(40) NOT NULL,
            dh_desbloqueio TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_conquista_usuario UNIQUE (id_usuario, co_conquista)
        )
        """
    )

    # tb003_lote_migracao — idempotência do merge convidado→conta (por lote).
    op.execute(
        """
        CREATE TABLE progressao.tb003_lote_migracao (
            co_lote_migracao UUID PRIMARY KEY,
            id_usuario  UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            dh_aplicado TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # VIEWs SEMÂNTICAS (derivam/calculam colunas)
    # ════════════════════════════════════════════════════════════════════════

    # vw001_partida — co_resultado derivado do placar (FR-016).
    op.execute(
        """
        CREATE VIEW partida.vw001_partida AS
        SELECT p.*,
               CASE
                 WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'
                 WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'
                 ELSE 'empate'
               END AS co_resultado
        FROM partida.tb001_partida p
        """
    )

    # vw002_jogada — ic_cpu derivado via JOIN: no vs_cpu, o J2 é a CPU (FR-018).
    op.execute(
        """
        CREATE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )

    # vw001_progressao_usuario — nu_nivel/co_patente calculados de nu_xp_total,
    # espelhando `regras_xp.dart` (FR-025). A curva de custo acumulado é
    #   xpParaAlcancarNivel(n) = 15*(n-1)*(n+6)
    # cuja inversa dá  nivel = floor((-5 + sqrt(49 + 4*xp/15)) / 2), mínimo 1.
    # (nu_nivel é computado no subselect e reaproveitado no CASE das patentes.)
    op.execute(
        """
        CREATE VIEW progressao.vw001_progressao_usuario AS
        SELECT sub.*,
               CASE
                 WHEN sub.nu_nivel >= 80 THEN 'lendario'
                 WHEN sub.nu_nivel >= 55 THEN 'sagaz'
                 WHEN sub.nu_nivel >= 35 THEN 'sabio'
                 WHEN sub.nu_nivel >= 20 THEN 'mestre'
                 WHEN sub.nu_nivel >= 10 THEN 'tatico'
                 WHEN sub.nu_nivel >= 5  THEN 'estrategista'
                 ELSE 'aprendiz'
               END AS co_patente
        FROM (
            SELECT g.*,
                   GREATEST(1, FLOOR(
                       (-5 + sqrt(49 + (4.0 * g.nu_xp_total / 15.0))) / 2.0
                   ))::int AS nu_nivel
            FROM progressao.tb001_progressao_usuario g
        ) sub
        """
    )

    # vw101_ranking_global_geral — ranking sem tabela física (por isso vw101).
    # nu_posicao = DENSE_RANK (empatados dividem a posição, sem buracos) sobre
    # TODOS que pontuaram (posição própria sempre real). ic_publico marca quem
    # pode aparecer na lista PÚBLICA: visível (opt-out=false) E idade >= 13
    # (derivada de dt_nascimento; sem data => não é público, family-safe).
    op.execute(
        """
        CREATE VIEW progressao.vw101_ranking_global_geral AS
        SELECT g.id_usuario,
               u.co_usuario,
               u.no_exibicao,
               g.nu_xp_total,
               DENSE_RANK() OVER (ORDER BY g.nu_xp_total DESC) AS nu_posicao,
               (g.ic_visivel_placar
                AND u.dt_nascimento IS NOT NULL
                AND u.dt_nascimento <= (current_date - INTERVAL '13 years')
               ) AS ic_publico
        FROM progressao.tb001_progressao_usuario g
        JOIN conta.tb001_usuario u ON u.id_usuario = g.id_usuario
        WHERE g.nu_xp_total > 0
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # VIEWs PASS-THROUGH (SELECT *) — honram a regra "ler sempre via VIEW"
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        "CREATE VIEW partida.vw003_xp_partida AS "
        "SELECT * FROM partida.tb003_xp_partida"
    )
    op.execute(
        "CREATE VIEW jogo_pontinhos.vw002_jogada AS "
        "SELECT * FROM jogo_pontinhos.tb002_jogada"
    )
    op.execute(
        "CREATE VIEW progressao.vw002_conquista_usuario AS "
        "SELECT * FROM progressao.tb002_conquista_usuario"
    )
    op.execute(
        "CREATE VIEW progressao.vw003_lote_migracao AS "
        "SELECT * FROM progressao.tb003_lote_migracao"
    )


def downgrade() -> None:
    # Derruba VIEWs (semânticas + pass-through), depois tabelas, depois schemas.
    for view in (
        "progressao.vw003_lote_migracao",
        "progressao.vw002_conquista_usuario",
        "progressao.vw101_ranking_global_geral",
        "progressao.vw001_progressao_usuario",
        "jogo_pontinhos.vw002_jogada",
        "partida.vw003_xp_partida",
        "partida.vw002_jogada",
        "partida.vw001_partida",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view}")

    for table in (
        "progressao.tb003_lote_migracao",
        "progressao.tb002_conquista_usuario",
        "progressao.tb001_progressao_usuario",
        "jogo_pontinhos.tb002_jogada",
        "partida.tb003_xp_partida",
        "partida.tb002_jogada",
        "partida.tb001_partida",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.execute("DROP SCHEMA IF EXISTS progressao CASCADE")
    op.execute("DROP SCHEMA IF EXISTS jogo_pontinhos CASCADE")
    op.execute("DROP SCHEMA IF EXISTS partida CASCADE")
