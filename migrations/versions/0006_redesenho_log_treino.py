"""Redesenho do schema do log de partidas/treino (economia de disco no Railway)

Contrato completo (com os PORQUÊS de cada decisão):
``docs/redesenho_schema_log_treino.md`` — validado pelo dono em 2026-07-12.

O QUE MUDA, em uma frase: paramos de guardar o que sabemos RECALCULAR (as matrizes
do tabuleiro) e trocamos códigos textuais repetidos por códigos NUMÉRICOS com
tabela de dimensão. Resultado: ~24 KB → ~11 KB por partida (a 5.000 partidas/dia,
~3,6 GB/mês → ~1,7 GB/mês).

Quatro mudanças:

1. **Fuso do jogador** (`nu_offset_minuto_j1/j2` em `partida.tb001_partida`):
   `timestamptz` guarda o INSTANTE, não o fuso de ORIGEM. Sem o offset não há como
   saber que a partida foi jogada "às 21h da noite do jogador".

2. **Fim das matrizes** (`ar_tabuleiro_antes`/`ar_tabuleiro_apos`): são 100%
   reconstruíveis da sequência de arestas (`co_aresta` + `co_jogador` + `nu_ordem`)
   via ``gerador_dados/jogo_pontinhos/reconstrutor_partida_pontinhos.py``. É o maior
   corte de espaço. O contrato da CNN NÃO muda — só deixamos de PERSISTIR o
   derivável.

3. **Códigos → dimensões**: `co_acao`, `co_situacao`, `co_origem_decisao` e
   `co_tipo_xp` viram `nu_*` SMALLINT com FK. Cada dimensão guarda três colunas:
   `nu_` (a chave), `co_` (a string canônica que o APP envia — é a tabela de
   TRADUÇÃO usada na ingestão) e `no_` (o nome legível, para relatório).
   O app continua enviando as STRINGS; quem traduz é o backend.

4. **Idioma + fuso do dispositivo** (`co_fuso`/`nu_offset_minuto` em
   `conta.tb005_dispositivo_notificacao`): prepara o terreno para o futuro módulo de
   campanha (push no idioma e no horário local). NÃO pode ser preenchido
   retroativamente — o aparelho só reporta quando abre o app. "Coletar cedo, usar
   depois."

⚠️ DESTRUTIVA: dropa e recria `partida.*` e `jogo_pontinhos.*` e trunca
`progressao.*`. Autorizado pelo dono — des e prd só têm dados de TESTE. O schema
`conta` só recebe ALTER (as contas SOBREVIVEM).

⚠️ Pegadinha do Postgres tratada aqui: uma VIEW criada com `SELECT *` CONGELA a
lista de colunas no momento da criação. Toda view sobre tabela alterada precisa ser
derrubada e recriada — senão as colunas novas simplesmente não aparecem.

Revision ID: 0006_redesenho_log_treino
Revises: 0005_log_evento_sync_rejeitado
Create Date: 2026-07-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006_redesenho_log_treino"
down_revision: Union[str, None] = "0005_log_evento_sync_rejeitado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Código sentinela para "não sei o que é isto" — ver §6 do doc. Um app mais NOVO
# que este backend pode mandar uma estratégia de IA que ainda não cadastramos; sem
# um destino válido, a FK estoura 500 e o evento fica preso PARA SEMPRE na fila de
# sincronização do aparelho. 9999 deixa a faixa 1..N livre para os códigos reais e
# salta aos olhos num relatório.
NU_DESCONHECIDO = 9999


def upgrade() -> None:
    # ════════════════════════════════════════════════════════════════════════
    # 1) DIMENSÕES (faixa 900). A chave tem o MESMO NOME na dimensão (PK) e no
    #    fato (FK). `co_` é a string que o app manda — é por ela que a ingestão
    #    traduz; por isso é UNIQUE.
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE TABLE partida.tb901_jogada_origem_decisao (
            nu_origem_decisao SMALLINT    PRIMARY KEY,
            co_origem_decisao VARCHAR(15) NOT NULL UNIQUE,
            no_origem_decisao VARCHAR(30) NOT NULL
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO partida.tb901_jogada_origem_decisao VALUES
            (1, 'humano',       'Humano'),
            (2, 'cpu',          'CPU'),
            (3, 'timeout_auto', 'Tempo esgotado (automático)'),
            ({NU_DESCONHECIDO}, 'desconhecido', 'Desconhecido')
        """
    )

    op.execute(
        """
        CREATE TABLE partida.tb902_tipo_xp (
            nu_tipo_xp SMALLINT    PRIMARY KEY,
            co_tipo_xp VARCHAR(20) NOT NULL UNIQUE,
            no_tipo_xp VARCHAR(30) NOT NULL
        )
        """
    )
    # 6 valores (não 4): `primeira_vitoria` e `conquista` também são enviados pelo
    # app (partida_screen.dart) e estavam no CHECK da tabela antiga.
    op.execute(
        f"""
        INSERT INTO partida.tb902_tipo_xp VALUES
            (1, 'resultado',        'Resultado da partida'),
            (2, 'caixas',           'Bônus de caixas'),
            (3, 'dificuldade',      'Bônus de dificuldade'),
            (4, 'primeira_vitoria', 'Primeira vitória'),
            (5, 'conquista',        'Conquista'),
            (6, 'ajuste',           'Ajuste (teto diário de XP)'),
            ({NU_DESCONHECIDO}, 'desconhecido', 'Desconhecido')
        """
    )

    op.execute(
        """
        CREATE TABLE jogo_pontinhos.tb901_jogada_acao (
            nu_acao SMALLINT    PRIMARY KEY,
            co_acao VARCHAR(30) NOT NULL UNIQUE,
            no_acao VARCHAR(40) NOT NULL
        )
        """
    )
    # 5 valores reais (oraculo.dart:43) — e TRÊS deles são CNN distintas. Colapsar
    # as três num código só apagaria a diferença entre o núcleo top-p (Pita/Cacau)
    # e o argmax (Magno), que é justamente o que se quer analisar no treino.
    op.execute(
        f"""
        INSERT INTO jogo_pontinhos.tb901_jogada_acao VALUES
            (1, 'captura_gulosa',         'Captura gulosa'),
            (2, 'cnn_nucleo_top_p',       'CNN — núcleo top-p'),
            (3, 'cnn_argmax_absoluto',    'CNN — argmax absoluto'),
            (4, 'cnn_argmax_desempatado', 'CNN — argmax desempatado'),
            (5, 'heuristica_gulosa',      'Heurística gulosa (reserva)'),
            ({NU_DESCONHECIDO}, 'desconhecido', 'Desconhecido')
        """
    )

    op.execute(
        """
        CREATE TABLE jogo_pontinhos.tb902_jogada_situacao (
            nu_situacao SMALLINT    PRIMARY KEY,
            co_situacao VARCHAR(20) NOT NULL UNIQUE,
            no_situacao VARCHAR(30) NOT NULL
        )
        """
    )
    op.execute(
        f"""
        INSERT INTO jogo_pontinhos.tb902_jogada_situacao VALUES
            (1, 'tatica',  'Tática (não fechou caixa)'),
            (2, 'captura', 'Captura (fechou caixa)'),
            ({NU_DESCONHECIDO}, 'desconhecido', 'Desconhecido')
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # 2) FATOS: dropar e recriar. Os dados de des/prd são de TESTE (autorizado).
    #    A ordem importa: as views primeiro, depois as tabelas filhas, depois as
    #    pais (senão a FK reclama).
    # ════════════════════════════════════════════════════════════════════════
    for view in (
        "jogo_pontinhos.vw002_jogada",
        "partida.vw003_xp_partida",
        "partida.vw002_jogada",
        "partida.vw001_partida",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view}")

    for tabela in (
        "jogo_pontinhos.tb002_jogada",
        "partida.tb003_xp_partida",
        "partida.tb002_jogada",
        "partida.tb001_partida",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")

    # ── partida.tb001_partida ────────────────────────────────────────────────
    # Idêntica à 0003, MAIS o offset de fuso dos dois jogadores. Os códigos desta
    # tabela (co_jogo/co_variante/co_modo/co_dificuldade/co_status) seguem TEXTUAIS
    # de propósito: é 1 linha por partida (~3 MB/mês), então a legibilidade vence.
    op.execute(
        """
        CREATE TABLE partida.tb001_partida (
            id_partida          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            co_evento           UUID        NOT NULL UNIQUE,
            co_jogo             VARCHAR(30) NOT NULL,
            co_variante         VARCHAR(30) NOT NULL,
            co_modo             VARCHAR(20) NOT NULL,
            id_usuario          UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            co_anonimo          UUID,
            id_usuario_j2       UUID
                REFERENCES conta.tb001_usuario(id_usuario),
            co_dificuldade      VARCHAR(10),
            nu_placar_j1        INT         NOT NULL,
            nu_placar_j2        INT         NOT NULL,
            ic_pontua           BOOLEAN     NOT NULL,
            co_status           VARCHAR(15) NOT NULL,
            co_lote_migracao    UUID,
            dh_inicio           TIMESTAMPTZ NOT NULL,
            dh_fim              TIMESTAMPTZ,
            nu_offset_minuto_j1 SMALLINT,
            nu_offset_minuto_j2 SMALLINT,
            CONSTRAINT ck_partida_modo
                CHECK (co_modo IN ('vs_cpu', 'pvp_local', 'pvp_online')),
            CONSTRAINT ck_partida_status
                CHECK (co_status IN ('concluida', 'abandonada', 'em_andamento')),
            CONSTRAINT ck_partida_dificuldade
                CHECK (co_dificuldade IS NULL OR co_dificuldade IN
                       ('facil', 'normal', 'dificil', 'sagaz')),
            -- UTC-14 .. UTC+14 (os extremos que existem de verdade no mundo).
            CONSTRAINT ck_partida_offset_j1
                CHECK (nu_offset_minuto_j1 IS NULL
                       OR nu_offset_minuto_j1 BETWEEN -840 AND 840),
            CONSTRAINT ck_partida_offset_j2
                CHECK (nu_offset_minuto_j2 IS NULL
                       OR nu_offset_minuto_j2 BETWEEN -840 AND 840)
        )
        """
    )
    op.execute("CREATE INDEX ix_partida_usuario ON partida.tb001_partida (id_usuario)")
    op.execute(
        "CREATE INDEX ix_partida_lote ON partida.tb001_partida (co_lote_migracao) "
        "WHERE co_lote_migracao IS NOT NULL"
    )

    # ── partida.tb002_jogada ─────────────────────────────────────────────────
    # co_origem_decisao VARCHAR(15) + CHECK  →  nu_origem_decisao SMALLINT + FK.
    # 31 linhas por partida: é a tabela mais quente do banco.
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
            nu_origem_decisao   SMALLINT    NOT NULL
                REFERENCES partida.tb901_jogada_origem_decisao(nu_origem_decisao),
            CONSTRAINT uq_jogada_ordem UNIQUE (id_partida, nu_ordem),
            CONSTRAINT ck_jogada_jogador CHECK (nu_jogador IN (1, 2))
        )
        """
    )

    # ── partida.tb003_xp_partida ─────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE partida.tb003_xp_partida (
            id_xp_partida UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            id_partida    UUID        NOT NULL
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            id_usuario    UUID        NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),
            co_anonimo    UUID,
            nu_tipo_xp    SMALLINT    NOT NULL
                REFERENCES partida.tb902_tipo_xp(nu_tipo_xp),
            nu_xp         INT         NOT NULL,
            co_referencia VARCHAR(40),
            dh_registro   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_xp_partida ON partida.tb003_xp_partida (id_partida)")
    op.execute("CREATE INDEX ix_xp_usuario ON partida.tb003_xp_partida (id_usuario)")

    # ── jogo_pontinhos.tb002_jogada ──────────────────────────────────────────
    # SEM ar_tabuleiro_antes/apos: o tabuleiro é RECONSTRUÍDO das arestas.
    # Isto faz de `co_aresta` o dado MAIS CRÍTICO da tabela — por isso ele segue
    # TEXTO (`H_0_1`), autodescritivo e válido para qualquer variante. Um índice
    # numérico seria ambíguo entre tabuleiros de tamanhos diferentes.
    op.execute(
        """
        CREATE TABLE jogo_pontinhos.tb002_jogada (
            id_jogada            UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador           SMALLINT    NOT NULL,
            co_aresta            VARCHAR(15) NOT NULL,
            nu_caixas_fechadas   SMALLINT    NOT NULL,
            nu_acao              SMALLINT
                REFERENCES jogo_pontinhos.tb901_jogada_acao(nu_acao),
            nu_situacao          SMALLINT
                REFERENCES jogo_pontinhos.tb902_jogada_situacao(nu_situacao),
            ar_probabilidade_cnn REAL[],
            ar_score_busca       REAL[],
            nu_profundidade      INT,
            js_extra             JSONB
        )
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # 3) VIEWs recriadas (mesma semântica da 0003, colunas novas incluídas)
    # ════════════════════════════════════════════════════════════════════════
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
    op.execute(
        """
        CREATE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )
    op.execute(
        "CREATE VIEW partida.vw003_xp_partida AS "
        "SELECT * FROM partida.tb003_xp_partida"
    )
    op.execute(
        "CREATE VIEW jogo_pontinhos.vw002_jogada AS "
        "SELECT * FROM jogo_pontinhos.tb002_jogada"
    )
    # Views das dimensões (regra do projeto: ler sempre pela VIEW).
    op.execute(
        "CREATE VIEW partida.vw901_jogada_origem_decisao AS "
        "SELECT * FROM partida.tb901_jogada_origem_decisao"
    )
    op.execute(
        "CREATE VIEW partida.vw902_tipo_xp AS "
        "SELECT * FROM partida.tb902_tipo_xp"
    )
    op.execute(
        "CREATE VIEW jogo_pontinhos.vw901_jogada_acao AS "
        "SELECT * FROM jogo_pontinhos.tb901_jogada_acao"
    )
    op.execute(
        "CREATE VIEW jogo_pontinhos.vw902_jogada_situacao AS "
        "SELECT * FROM jogo_pontinhos.tb902_jogada_situacao"
    )

    # ════════════════════════════════════════════════════════════════════════
    # 4) PROGRESSÃO: zerar. O XP acumulado é DERIVADO do log de partidas — se o
    #    log zera e a progressão não, o ranking passa a mostrar XP sem partida que
    #    o justifique (inconsistência permanente). As CONTAS não são tocadas.
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        "TRUNCATE progressao.tb001_progressao_usuario, "
        "progressao.tb002_conquista_usuario, "
        "progressao.tb003_lote_migracao"
    )

    # ════════════════════════════════════════════════════════════════════════
    # 5) DISPOSITIVO: idioma + fuso. NULLABLE de propósito — os apps já em campo
    #    não mandam estes campos, e eles NÃO podem ser preenchidos retroativamente
    #    (o aparelho só reporta quando abre o app).
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        """
        ALTER TABLE conta.tb005_dispositivo_notificacao
            ADD COLUMN co_fuso          VARCHAR(64),
            ADD COLUMN nu_offset_minuto SMALLINT
        """
    )
    # A view foi criada com `SELECT *`, que o Postgres CONGELA: sem recriar, as
    # duas colunas novas não apareceriam nela.
    op.execute("DROP VIEW IF EXISTS conta.vw005_dispositivo_notificacao")
    op.execute(
        "CREATE VIEW conta.vw005_dispositivo_notificacao AS "
        "SELECT * FROM conta.tb005_dispositivo_notificacao"
    )


def downgrade() -> None:
    """Volta ao schema da 0003 (com as matrizes e os códigos textuais).

    ⚠️ Os DADOS não voltam — o upgrade os descartou (autorizado: eram de teste).
    """
    # Dispositivo: tira as colunas e recria a view.
    op.execute("DROP VIEW IF EXISTS conta.vw005_dispositivo_notificacao")
    op.execute(
        "ALTER TABLE conta.tb005_dispositivo_notificacao "
        "DROP COLUMN IF EXISTS co_fuso, "
        "DROP COLUMN IF EXISTS nu_offset_minuto"
    )
    op.execute(
        "CREATE VIEW conta.vw005_dispositivo_notificacao AS "
        "SELECT * FROM conta.tb005_dispositivo_notificacao"
    )

    for view in (
        "jogo_pontinhos.vw902_jogada_situacao",
        "jogo_pontinhos.vw901_jogada_acao",
        "partida.vw902_tipo_xp",
        "partida.vw901_jogada_origem_decisao",
        "jogo_pontinhos.vw002_jogada",
        "partida.vw003_xp_partida",
        "partida.vw002_jogada",
        "partida.vw001_partida",
    ):
        op.execute(f"DROP VIEW IF EXISTS {view}")

    for tabela in (
        "jogo_pontinhos.tb002_jogada",
        "partida.tb003_xp_partida",
        "partida.tb002_jogada",
        "partida.tb001_partida",
        "jogo_pontinhos.tb902_jogada_situacao",
        "jogo_pontinhos.tb901_jogada_acao",
        "partida.tb902_tipo_xp",
        "partida.tb901_jogada_origem_decisao",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")

    # Recria o desenho ANTIGO (0003): códigos textuais + matrizes do tabuleiro.
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
    op.execute("CREATE INDEX ix_partida_usuario ON partida.tb001_partida (id_usuario)")
    op.execute(
        "CREATE INDEX ix_partida_lote ON partida.tb001_partida (co_lote_migracao) "
        "WHERE co_lote_migracao IS NOT NULL"
    )
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
    op.execute(
        """
        CREATE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )
    op.execute(
        "CREATE VIEW partida.vw003_xp_partida AS "
        "SELECT * FROM partida.tb003_xp_partida"
    )
    op.execute(
        "CREATE VIEW jogo_pontinhos.vw002_jogada AS "
        "SELECT * FROM jogo_pontinhos.tb002_jogada"
    )
