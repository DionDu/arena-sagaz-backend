"""Schema `jogo_xadrez` - a extensao de PARTIDA, de JOGADA e de RECUSA do 5o jogo.

CONTEXTO
--------
O Xadrez (spec 012 do frontend, versao 1.6.0) e o quinto jogo da Arena Sagaz.
Como os anteriores, ele grava a partida e a jogada GENERICAS em
`partida.tb001_partida` / `partida.tb002_jogada`, e o que e so dele num schema
proprio. Esta migracao cria esse schema, no molde do `jogo_damas` (0012, mais o
`co_motor_busca` da 0013 e o formato composto da 0014), exatamente como
`specs/012-jogo-xadrez/data-model.md` §2 (validado pelo dono em 14/11/2026,
DECISOES §8zzzz17).

NOTA DE ACENTUACAO: este arquivo nao usa acentos, seguindo a convencao local das
migracoes (0009 em diante). O resto do projeto e acentuado normalmente.

O QUE ELA FAZ, E SO ISSO
------------------------
`CREATE SCHEMA`, `CREATE TABLE`, `INSERT` nas dimensoes, `CREATE INDEX` e
`CREATE VIEW`. Nenhuma tabela, coluna ou view existente e tocada (RF-XDR-233): a
1.5.0 em campo nao ve nada disto.

AS SEIS DIMENSOES
-----------------
O mesmo numero diz a mesma coisa que no `jogo_damas`: `tb901` e a regra da
recusa, `tb902` o motivo de parada da busca, `tb903` a regra x modalidade. As
tres novas seguem a partir da `tb904`: o inicio da partida, o motivo do fim e a
acao da CPU. Todas com o sentinela `9999` (a licao da 0011: sem ele, um app
MAIS NOVO que o backend estoura a FK e o evento fica preso na fila do aparelho
para sempre).

O QUE NAO TEM
-------------
- Sem base de finais: o `6 base_finais` das damas (0015) nao entra na `tb902`, e o
  numero 6 fica RESERVADO com o mesmo sentido, para nunca dizer outra coisa aqui.
- Sem colunas da espia do desafio: as marcas seguem pela fita de fatos, e o
  desafio grava a posicao publicada, de onde tudo se reconstroi.
"""

from typing import Sequence, Union

from alembic import op

# A revisao tem 23 caracteres; o limite do `alembic_version.version_num` e 32.
# ⚠️ O numero e o proximo livre na `main` do dia em que foi escrito (17/11/2026,
# depois da 0038). Se outra migracao entrar antes do merge, ele anda, e a T129
# da spec 012 confere isso contra o `head` da `main` no dia.
revision: str = "0039_schema_jogo_xadrez"
down_revision: Union[str, None] = "0038_resultado_da_partida"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `jogo_xadrez`: seis dimensoes, tres fatos, um indice, dez views."""
    op.execute("CREATE SCHEMA IF NOT EXISTS jogo_xadrez")

    # ══ DIMENSOES ══════════════════════════════════════════════════════════

    # ── tb901: por que o gesto nao virou lance ──────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb901_regra_recusa (
            nu_regra SMALLINT    PRIMARY KEY,
            co_regra VARCHAR(30) NOT NULL UNIQUE,
            no_regra VARCHAR(60) NOT NULL
        )
        """
    )

    # Os 11 codigos que o MOTOR emite (`src/recusa.rs`, `codigos()`), mais o
    # sentinela. ⚠️ A lista e a do motor, e nao a de um documento: o teste
    # `test_regras_recusa_xadrez.py` pede cada recusa ao executavel e confere
    # que o codigo existe aqui (a licao da 0012: eram oito codigos no papel e sete
    # no motor).
    #
    # ⚠️ Um `nu_regra` NUNCA muda de significado depois de gravado. Acrescentar e
    # migracao nova; reescrever o sentido de um existente falsifica o historico.
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb901_regra_recusa (nu_regra, co_regra, no_regra) VALUES
            (1,    'nao_e_sua_peca',               'A peca e do adversario'),
            (2,    'peca_nao_anda_assim',          'A peca nao anda desse jeito'),
            (3,    'caminho_bloqueado',            'Ha uma peca no caminho'),
            (4,    'casa_ocupada_por_peca_sua',    'A casa ja tem uma peca sua'),
            (5,    'rei_em_xeque',                 'O lance nao tira o rei do xeque'),
            (6,    'rei_ficaria_em_xeque',         'O rei ficaria em xeque'),
            (7,    'roque_sem_direito',            'O rei ou a torre ja se moveram'),
            (8,    'roque_com_rei_em_xeque',       'Roque com o rei em xeque'),
            (9,    'roque_atravessa_casa_atacada', 'O rei passaria por casa atacada'),
            (10,   'roque_caminho_ocupado',        'Ha pecas entre o rei e a torre'),
            (11,   'peca_sem_lance',               'A peca nao tem lance agora'),
            (9999, 'desconhecido',                 'Desconhecido')
        """
    )

    # ── tb902: por que a busca parou (os MESMOS numeros das damas) ──────────
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb902_motivo_parada_busca (
            nu_motivo_parada_busca SMALLINT    PRIMARY KEY,
            co_motivo_parada_busca VARCHAR(20) NOT NULL UNIQUE,
            no_motivo_parada_busca VARCHAR(60) NOT NULL
        )
        """
    )

    # ⚠️ O `3` e o numero que mais importa (RF-XDR-081, SC-006): e a rede de
    # seguranca mordendo, o Magno jogando mais fraco que ele mesmo e fora da
    # paridade com o servidor. A `vw004_parada_por_tempo` existe para ele.
    #
    # O 6 (`base_finais`, nas damas) fica RESERVADO: o xadrez nao tem base de
    # finais (RF-XDR-027), e o numero nunca dira outra coisa neste schema.
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb902_motivo_parada_busca
            (nu_motivo_parada_busca, co_motivo_parada_busca, no_motivo_parada_busca) VALUES
            (1,    'profundidade', 'Terminou a profundidade'),
            (2,    'nos',          'Esgotou o teto de nos'),
            (3,    'tempo',        'Esgotou o tempo'),
            (4,    'decidido',     'Vitoria ou derrota forcada'),
            (5,    'lance_unico',  'Lance unico: nao houve busca'),
            (9999, 'desconhecido', 'Desconhecido')
        """
    )

    # ── tb903: em quais modalidades cada regra recusa ───────────────────────
    #
    # A modalidade numa tabela de relacionamento, e nunca como sufixo do codigo
    # (V-9 das damas). Hoje sao as onze regras x a unica modalidade. Quando o 960
    # chegar, o roque dele recusa por outros motivos, e o custo e `INSERT`.
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb903_regra_modalidade (
            nu_regra      SMALLINT    NOT NULL
                REFERENCES jogo_xadrez.tb901_regra_recusa(nu_regra),
            co_modalidade VARCHAR(30) NOT NULL,
            PRIMARY KEY (nu_regra, co_modalidade)
        )
        """
    )
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb903_regra_modalidade (nu_regra, co_modalidade) VALUES
            (1,  'tradicional'),
            (2,  'tradicional'),
            (3,  'tradicional'),
            (4,  'tradicional'),
            (5,  'tradicional'),
            (6,  'tradicional'),
            (7,  'tradicional'),
            (8,  'tradicional'),
            (9,  'tradicional'),
            (10, 'tradicional'),
            (11, 'tradicional')
        """
    )

    # ── tb904: de onde a partida comecou ────────────────────────────────────
    #
    # O inicio NAO e modalidade (a regra e a mesma, pergunta C da spec), e por
    # isso nao vai em `co_variante`. E dimensao, e nao `CHECK`, porque a 2a leva
    # ja preve outro inicio, e um `CHECK` viraria `ALTER` numa tabela com dados.
    #
    # ⚠️ O `tradicional` DAQUI (o tabuleiro cheio) e o `tradicional` da `tb903`
    # (a modalidade) sao palavras iguais para coisas diferentes. O cadeado do
    # literal da modalidade (R-24) olha o codigo do app, do motor e do job; isto
    # e dado do banco.
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb904_inicio_partida (
            nu_inicio SMALLINT    PRIMARY KEY,
            co_inicio VARCHAR(20) NOT NULL UNIQUE,
            no_inicio VARCHAR(60) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb904_inicio_partida (nu_inicio, co_inicio, no_inicio) VALUES
            (1,    'tradicional',  'Tabuleiro cheio'),
            (2,    'adiantado',    'Posicao adiantada sorteada'),
            (3,    'desafio',      'Posicao publicada do desafio'),
            (9999, 'desconhecido', 'Desconhecido')
        """
    )

    # ── tb905: como a partida terminou ──────────────────────────────────────
    #
    # As damas terminam de dois jeitos; o xadrez tem quatro causas so de empate
    # (RF-XDR-002), e a tela diz a causa em palavras. Sem ela no banco, "quantas
    # partidas empataram por repeticao" seria impossivel de responder.
    # `NULL` na partida = nao terminou pelo tabuleiro (abandonada ou expirada).
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb905_motivo_fim (
            nu_motivo_fim SMALLINT    PRIMARY KEY,
            co_motivo_fim VARCHAR(30) NOT NULL UNIQUE,
            no_motivo_fim VARCHAR(60) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb905_motivo_fim (nu_motivo_fim, co_motivo_fim, no_motivo_fim) VALUES
            (1,    'xeque_mate',            'Xeque-mate'),
            (2,    'afogamento',            'Empate por afogamento'),
            (3,    'repeticao_tripla',      'Empate por repeticao'),
            (4,    'cinquenta_lances',      'Empate pelos 50 lances'),
            (5,    'material_insuficiente', 'Empate por material insuficiente'),
            (9999, 'desconhecido',          'Desconhecido')
        """
    )

    # ── tb906: por que a CPU escolheu aquele lance ──────────────────────────
    #
    # Molde: `jogo_quatro.tb901_jogada_acao`. As damas nao tem, e e o unico ponto
    # em que o xadrez sai do molde delas: o ruido e sorteio dentro do Rust, com
    # tres causas, e e contando as causas que a calibracao acerta a dificuldade.
    # `NULL` na jogada = lance do humano.
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb906_jogada_acao (
            nu_acao SMALLINT    PRIMARY KEY,
            co_acao VARCHAR(30) NOT NULL UNIQUE,
            no_acao VARCHAR(60) NOT NULL
        )
        """
    )
    op.execute(
        """
        INSERT INTO jogo_xadrez.tb906_jogada_acao (nu_acao, co_acao, no_acao) VALUES
            (1,    'busca_melhor',  'Busca - melhor lance'),
            (2,    'erro_sorteado', 'Erro sorteado entre os plausiveis'),
            (3,    'cegueira',      'Nao viu a ameaca (cegueira)'),
            (4,    'mate_em_um',    'Filtro: deu o mate em um'),
            (5,    'lance_unico',   'So havia um lance'),
            (9999, 'desconhecido',  'Desconhecido')
        """
    )

    # ══ FATOS ══════════════════════════════════════════════════════════════

    # ── tb001: a extensao 1:1 da partida ────────────────────────────────────
    #
    # · `co_versao_motor` no formato composto da 0014: `rust_0.5.0` hoje (um
    #   motor so); com um 2o, `rust_X|<outro>_Y`. A versao da `cozy-chess` NAO
    #   entra: ela e travada no `Cargo.lock`, e toda troca dela sobe a versao do
    #   nosso motor.
    # · `co_fen_inicial`: a posicao inicial (tradicional), a sorteada (adiantado)
    #   ou a publicada (desafio). Com os lances da `partida.tb002_jogada`, em
    #   ordem, reconstroi a partida inteira (R-03).
    # · `co_cor_j1` aqui VARIA de verdade: o J1 e branco quando comeca e preto
    #   quando o adversario comeca (RF-XDR-004). O banco fala o vocabulario do
    #   xadrez; azul e vermelho sao tema, e a ponte e feita no app.
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb001_partida (
            id_partida         UUID PRIMARY KEY
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            co_versao_motor    VARCHAR(60)  NOT NULL,
            co_versao_contrato VARCHAR(20)  NOT NULL,
            nu_inicio          SMALLINT     NOT NULL
                REFERENCES jogo_xadrez.tb904_inicio_partida(nu_inicio),
            co_fen_inicial     VARCHAR(255) NOT NULL,
            co_cor_j1          VARCHAR(6)   NOT NULL,
            nu_motivo_fim      SMALLINT
                REFERENCES jogo_xadrez.tb905_motivo_fim(nu_motivo_fim),
            nu_semente_partida BIGINT,
            js_extra           JSONB,
            CONSTRAINT ck_xadrez_cor_j1 CHECK (co_cor_j1 IN ('branca', 'preta'))
        )
        """
    )

    # ── tb002: a extensao 1:1 da jogada ─────────────────────────────────────
    #
    # · `co_fen_antes` em TODA jogada (V-3 das damas), e aqui com um motivo a
    #   mais: nao ha arbitro em Python (RF-XDR-043). Sem o FEN, nenhuma consulta
    #   nem o painel de replay saberia a posicao sem subir o executavel Rust.
    # · `co_peca_comida` (o TIPO) em vez das duas contagens das damas: no xadrez
    #   um lance come no maximo uma peca, e o tipo e o que a qualidade do XP
    #   pondera.
    # · `co_promocao` com a peca, e nao um booleano: a promocao a cavalo existe.
    # · `ic_xeque` porque "de 3 xeques seguidos" e um desafio, e o FEN de ANTES
    #   nao diz se o lance deu xeque.
    # · Telemetria anulavel: `NULL` = lance do humano.
    # · `nu_avaliacao_brancas`: a nota da busca em centipeoes, no referencial das
    #   brancas (V-11 das damas).
    # · `co_motor_busca` desde o dia 1 (hoje sempre 'rust'): nas damas ela entrou
    #   depois, por `ALTER` numa tabela com dados (0013).
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb002_jogada (
            id_jogada                UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador               SMALLINT     NOT NULL,
            co_lance                 VARCHAR(10)  NOT NULL,
            co_fen_antes             VARCHAR(255) NOT NULL,
            co_peca_movida           VARCHAR(10)  NOT NULL,
            co_peca_comida           VARCHAR(10),
            co_promocao              VARCHAR(10),
            co_lance_especial        VARCHAR(12),
            ic_xeque                 BOOLEAN      NOT NULL DEFAULT FALSE,
            nu_acao                  SMALLINT
                REFERENCES jogo_xadrez.tb906_jogada_acao(nu_acao),
            qt_nos_visitados         INTEGER,
            nu_profundidade_atingida SMALLINT,
            nu_motivo_parada_busca   SMALLINT
                REFERENCES jogo_xadrez.tb902_motivo_parada_busca(nu_motivo_parada_busca),
            nu_tempo_busca_ms        INTEGER,
            nu_avaliacao_brancas     INTEGER,
            nu_semente               BIGINT,
            co_motor_busca           VARCHAR(10),
            js_extra                 JSONB,
            CONSTRAINT ck_xadrez_jogador CHECK (co_jogador IN (1, -1)),
            -- O mesmo CHECK das damas (0013). Hoje sempre 'rust'.
            CONSTRAINT ck_xadrez_motor_busca
                CHECK (co_motor_busca IS NULL OR co_motor_busca IN ('dart', 'rust')),
            CONSTRAINT ck_xadrez_peca_movida
                CHECK (co_peca_movida IN ('peao', 'cavalo', 'bispo', 'torre', 'dama', 'rei')),
            -- O rei nunca e comido: o jogo acaba antes (xeque-mate).
            CONSTRAINT ck_xadrez_peca_comida
                CHECK (co_peca_comida IS NULL
                       OR co_peca_comida IN ('peao', 'cavalo', 'bispo', 'torre', 'dama')),
            -- So peao promove, e nunca a peao nem a rei.
            CONSTRAINT ck_xadrez_promocao
                CHECK (co_promocao IS NULL
                       OR (co_peca_movida = 'peao'
                           AND co_promocao IN ('dama', 'torre', 'bispo', 'cavalo'))),
            CONSTRAINT ck_xadrez_lance_especial
                CHECK (co_lance_especial IS NULL
                       OR (co_lance_especial IN ('roque_curto', 'roque_longo')
                           AND co_peca_movida = 'rei')
                       OR (co_lance_especial = 'en_passant'
                           AND co_peca_movida = 'peao' AND co_peca_comida = 'peao')),
            -- Lance da CPU (com nos) tem de trazer a semente: sem ela, o lance
            -- nao se reproduz no replay nem no servidor.
            CONSTRAINT ck_xadrez_semente_da_cpu
                CHECK (qt_nos_visitados IS NULL OR nu_semente IS NOT NULL)
        )
        """
    )

    # ── tb003: as tentativas que a regra barrou ─────────────────────────────
    #
    # A casa e o nome padrao do xadrez ('e1', 'g1'), em texto (decisao do dono,
    # 14/11/2026, §8zzzz17): a mesma notacao do `co_lance` e do FEN. Por isso o
    # prefixo e `co_`, e nao `nu_` como nas damas (la a casa e um numero de 1 a 32).
    #
    # ⚠️ A ARMADILHA DE LEITURA e a mesma das damas: `nu_ordem` aqui e o lance que
    # ESTAVA SENDO TENTADO, e que pode nunca acontecer (a pessoa abandona depois
    # da recusa). Por isso nao ha FK para a jogada, a FK aponta para a PARTIDA, e
    # a `vw003_recusa` usa `LEFT JOIN`. Teto de 50 recusas por partida, contado
    # pelo app.
    #
    # `co_casa_destino` ACEITA NULL (decisao do dono, 19/11/2026, §8zzzz41 do
    # `DECISOES-do-dono.md` do app): o toque numa peca SEM lance nenhum
    # (`peca_sem_lance`, a regra 11) nao tem destino - o motor so a emite no
    # `recusa` sem "para". NULL quer dizer "a pessoa so tocou a peca". O CHECK da
    # casa continua valendo quando ha valor (no Postgres, um CHECK que da NULL
    # passa; o `IS NULL OR` esta escrito para quem le nao precisar saber disso).
    # Mudou aqui, e nao por ALTER, porque a 0039 ainda nao tinha sido aplicada em
    # banco nenhum (§8b: ate o 1o upgrade, defeito de modelagem se refaz).
    op.execute(
        """
        CREATE TABLE jogo_xadrez.tb003_recusa (
            id_recusa       UUID PRIMARY KEY,
            id_partida      UUID NOT NULL
                REFERENCES partida.tb001_partida(id_partida) ON DELETE CASCADE,
            nu_ordem        SMALLINT   NOT NULL,
            nu_sequencia    SMALLINT   NOT NULL,
            co_casa_origem  VARCHAR(2) NOT NULL,
            co_casa_destino VARCHAR(2),
            nu_regra        SMALLINT   NOT NULL
                REFERENCES jogo_xadrez.tb901_regra_recusa(nu_regra),
            dh_recusa       TIMESTAMPTZ NOT NULL,
            CONSTRAINT ck_xadrez_casa_origem CHECK (co_casa_origem ~ '^[a-h][1-8]$'),
            CONSTRAINT ck_xadrez_casa_destino
                CHECK (co_casa_destino IS NULL OR co_casa_destino ~ '^[a-h][1-8]$'),
            CONSTRAINT uq_xadrez_recusa UNIQUE (id_partida, nu_ordem, nu_sequencia)
        )
        """
    )

    # ══ INDICE ═════════════════════════════════════════════════════════════
    #
    # As tabelas 1:1 nao precisam (a PK e a coluna do JOIN). A recusa e
    # consultada POR PARTIDA, e a PK dela e o `id_recusa`.
    op.execute(
        "CREATE INDEX ix_xadrez_recusa_partida "
        "ON jogo_xadrez.tb003_recusa (id_partida)"
    )

    # ══ VIEWs - le-se SEMPRE pela VIEW (regra do ecossistema) ══════════════
    #
    # As das dimensoes sao `SELECT *`: dimensao nao ganha coluna. ⚠️ As de FATO
    # listam as colunas uma a uma (a licao da 0017: uma VIEW com `SELECT *`
    # congela a lista de colunas na criacao, e uma coluna nova some calada dela).
    for dimensao in (
        "tb901_regra_recusa",
        "tb902_motivo_parada_busca",
        "tb903_regra_modalidade",
        "tb904_inicio_partida",
        "tb905_motivo_fim",
        "tb906_jogada_acao",
    ):
        # `tb901_...` -> `vw901_...`: o mesmo numero e o mesmo nome.
        visao = "vw" + dimensao[2:]
        op.execute(
            f"CREATE VIEW jogo_xadrez.{visao} AS SELECT * FROM jogo_xadrez.{dimensao}"
        )

    # A partida com o inicio e o motivo do fim POR EXTENSO.
    op.execute(
        """
        CREATE VIEW jogo_xadrez.vw001_partida AS
        SELECT p.id_partida,
               p.co_versao_motor,
               p.co_versao_contrato,
               p.nu_inicio,
               i.co_inicio,
               p.co_fen_inicial,
               p.co_cor_j1,
               p.nu_motivo_fim,
               f.co_motivo_fim,
               p.nu_semente_partida,
               p.js_extra
          FROM jogo_xadrez.tb001_partida p
          LEFT JOIN jogo_xadrez.tb904_inicio_partida i ON i.nu_inicio = p.nu_inicio
          LEFT JOIN jogo_xadrez.tb905_motivo_fim f ON f.nu_motivo_fim = p.nu_motivo_fim
        """
    )

    # A jogada com o motivo de parada e a acao POR EXTENSO: quem le um log no
    # suporte quer ver 'tempo' e 'cegueira', e nao os numeros.
    op.execute(
        """
        CREATE VIEW jogo_xadrez.vw002_jogada AS
        SELECT j.id_jogada,
               j.co_jogador,
               j.co_lance,
               j.co_fen_antes,
               j.co_peca_movida,
               j.co_peca_comida,
               j.co_promocao,
               j.co_lance_especial,
               j.ic_xeque,
               j.nu_acao,
               a.co_acao,
               j.qt_nos_visitados,
               j.nu_profundidade_atingida,
               j.nu_motivo_parada_busca,
               m.co_motivo_parada_busca,
               j.nu_tempo_busca_ms,
               j.nu_avaliacao_brancas,
               j.nu_semente,
               j.co_motor_busca,
               j.js_extra
          FROM jogo_xadrez.tb002_jogada j
          LEFT JOIN jogo_xadrez.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
          LEFT JOIN jogo_xadrez.tb906_jogada_acao a ON a.nu_acao = j.nu_acao
        """
    )

    # A recusa com a regra por extenso, a modalidade, e a jogada que aconteceu no
    # mesmo `nu_ordem` (se aconteceu).
    #
    # ⚠️ `LEFT JOIN` em TODOS os lados: na regra, por defesa (um INNER faria uma
    # inconsistencia futura sumir com recusas, o pior modo de falha numa tabela de
    # auditoria); na jogada, porque a recusa PODE SER ORFA por construcao (ver a
    # armadilha acima), e um INNER apagaria exatamente as que mais interessam.
    op.execute(
        """
        CREATE VIEW jogo_xadrez.vw003_recusa AS
        SELECT r.id_recusa,
               r.id_partida,
               r.nu_ordem,
               r.nu_sequencia,
               r.co_casa_origem,
               r.co_casa_destino,
               r.nu_regra,
               g.co_regra,
               g.no_regra,
               r.dh_recusa,
               p.co_variante AS co_modalidade,
               j.id_jogada,
               -- A recusa aconteceu numa modalidade onde a regra NEM EXISTE?
               -- Se vier `true`, e defeito de tela, e nao comportamento do jogo.
               NOT EXISTS (
                   SELECT 1
                     FROM jogo_xadrez.tb903_regra_modalidade m
                    WHERE m.nu_regra = r.nu_regra
                      AND m.co_modalidade = p.co_variante
               ) AS ic_regra_impossivel_na_modalidade
          FROM jogo_xadrez.tb003_recusa r
          LEFT JOIN jogo_xadrez.tb901_regra_recusa g ON g.nu_regra = r.nu_regra
          LEFT JOIN partida.tb001_partida p ON p.id_partida = r.id_partida
          LEFT JOIN partida.tb002_jogada j
                 ON j.id_partida = r.id_partida AND j.nu_ordem = r.nu_ordem
        """
    )

    # A leitura do RF-XDR-081 (SC-006): os lances em que a REDE DE TEMPO mordeu
    # (`nu_motivo_parada_busca = 3`), com quem jogava e quando. Tem de ficar em
    # praticamente zero no `prd`; cada linha aqui e um Magno jogando mais fraco
    # que ele mesmo, num aparelho lento.
    op.execute(
        """
        CREATE VIEW jogo_xadrez.vw004_parada_por_tempo AS
        SELECT x.id_jogada,
               g.id_partida,
               g.nu_ordem,
               g.dh_jogada,
               p.id_usuario,
               p.co_dificuldade,
               p.dh_inicio,
               x.qt_nos_visitados,
               x.nu_profundidade_atingida,
               x.nu_tempo_busca_ms,
               x.co_motor_busca
          FROM jogo_xadrez.tb002_jogada x
          JOIN partida.tb002_jogada g ON g.id_jogada = x.id_jogada
          JOIN partida.tb001_partida p ON p.id_partida = g.id_partida
         WHERE x.nu_motivo_parada_busca = 3
        """
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** Nunca rodar em `prd` - ha usuarios reais, e
    o `CASCADE` levaria junto as partidas de xadrez ja gravadas. E o unico lugar
    deste arquivo onde um `DROP` aparece, e o teste de migracao aditiva ignora o
    `downgrade()` exatamente por isso.
    """
    op.execute("DROP SCHEMA IF EXISTS jogo_xadrez CASCADE")
