"""Damas: qual MOTOR jogou cada lance, e o fim do 9999 no lance forcado.

Revision ID: 0013_motor_e_lance_unico_damas
Revises: 0012_schema_jogo_damas
Create Date: 2026-08-25

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

Duas coisas, decididas pelo dono em 2026-08-25, e as duas nascem do mesmo
lugar: **o log estava afirmando coisas que nao sabia**.

── 1. `co_motor_busca` — qual motor escolheu o lance ──────────────────────

O app passa a ter DOIS motores de damas: o de Dart, que roda em qualquer
aparelho, e o de Rust, que roda o Magno onde ha biblioteca nativa. Sem uma
coluna que diga qual deles jogou, e impossivel fazer gestao de resultados ou
de defeitos: "o Magno esta errando mais" nao tem resposta se nao se souber
quem estava jogando.

⚠️ **A coluna vai na JOGADA, nao na PARTIDA**, e isso nao e capricho. A ponte
do app cai para o motor Dart quando o Rust nao responde — e ela cai **por
lance**, nao por partida. Uma coluna na partida gravaria `'rust'` numa partida
que teve tres lances em Dart, e o caso que mais interessa investigar (o Rust
falhou no meio? em qual posicao?) seria exatamente o que o dado esconderia.

`NULL` significa "nao se aplica": o lance foi do HUMANO, e nao houve motor
nenhum. Mesma logica das outras colunas de telemetria desta tabela.

── 2. O motivo `5 = lance_unico` — o fim do sentinela indevido ────────────

Quando ha um unico lance legal, o app nao pergunta ao motor: quem nao tem
escolha nao precisa de busca. So que ate agora esse caso gravava
`co_motivo_parada_busca = 'lance_unico'`, uma string que **nao existe na
dimensao** — e caia no sentinela `9999 = desconhecido`, com o texto cru
despejado no `js_extra`. Foi o que a partida jogada no Galaxy J7 registrou,
em 6 dos 30 lances.

O sentinela 9999 = 'desconhecido' **continua existindo e nao e tocado**: ele e
a rede para um app MAIS NOVO que o backend, que mande um codigo que a dimensao
ainda nao conhece. Sem ele a FK estoura, o evento toma 500 e fica preso para
sempre na fila daquele aparelho. O que muda e que `lance_unico` **deixa de cair
nele**, porque e um caso previsto e legitimo, nao um desconhecido.

⚠️ **E os campos de busca passam a ir a NULL, nao a zero.** O log gravava
`nu_avaliacao_brancas = 0` nesses lances, e zero nessa coluna nao e "sem
informacao": significa **posicao equilibrada**. Era uma afirmacao falsa sobre
uma posicao que ninguem olhou, e ela chegou a induzir a erro a leitura do log
do J7. Ausencia registrada como ausencia.

⚠️ Nada disto muda o que ja esta gravado. Os dados do DES sao de teste e o dono
autorizou descarta-los; esta migracao nao os apaga (nada e apagado no projeto),
apenas para de produzir o defeito daqui para a frente.

═══════════════════════════════════════════════════════════════════════════
⚠️ A ARMADILHA DO `SELECT j.*` NUMA VIEW
═══════════════════════════════════════════════════════════════════════════

`vw002_jogada` foi criada como `SELECT j.*, ...`. **O PostgreSQL expande o `*`
no momento da criacao** e guarda a lista de colunas resolvida — a view NAO
"enxerga" colunas acrescentadas depois. Deixa-la como esta faria a coluna nova
existir na tabela e ser invisivel para todo mundo que le pela view, que e como
o projeto manda ler.

O sintoma seria o pior possivel: nenhum erro, nenhuma falha — so a coluna nunca
aparecendo, e alguem concluindo meses depois que "o app nao esta gravando o
motor".

⚠️ **E o conserto NAO pode ser `DROP VIEW` + `CREATE VIEW`.** Migracao a partir
da 0011 e puramente aditiva, por decisao do dono de 2026-08-06, porque ha
usuarios reais em `prd` — e `tests/unitarios/test_migracoes_aditivas.py` recusa
qualquer `DROP` no `upgrade()`. O cadeado pegou a primeira versao deste arquivo.

A saida e melhor do que o que ele barrou: a view passa a listar as colunas
**explicitamente**, na mesma ordem de antes, com `co_motor_busca` **no fim**. E
exatamente a forma que o `CREATE OR REPLACE VIEW` aceita (ele permite acrescentar
colunas ao final, nunca mexer nas existentes) — e, de quebra, o `SELECT j.*` sai
de cena, que era a armadilha em primeiro lugar.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0013_motor_e_lance_unico_damas"
down_revision: Union[str, None] = "0012_schema_jogo_damas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. O motivo novo entra na dimensao ──────────────────────────────────
    #
    # `5` e o proximo livre: 1..4 sao os motivos de parada de uma busca que
    # aconteceu, e o 9999 e o sentinela. O nome segue o padrao dos outros —
    # minusculo, sem acento, igual a palavra que o motor usa.
    op.execute(
        """
        INSERT INTO jogo_damas.tb902_motivo_parada_busca
            (nu_motivo_parada_busca, co_motivo_parada_busca, no_motivo_parada_busca)
        VALUES
            (5, 'lance_unico', 'Havia um lance legal so - nao houve busca')
        ON CONFLICT (nu_motivo_parada_busca) DO NOTHING
        """
    )

    # ── 2. A coluna do motor ────────────────────────────────────────────────
    #
    # `VARCHAR(10)` com CHECK, e nao uma tabela de dimensao: sao dois valores,
    # nao se espera um terceiro, e uma dimensao de duas linhas custaria um JOIN
    # em toda consulta para nao entregar nada. Se um dia houver um terceiro
    # motor, o CHECK vira dimensao — e ai o JOIN se paga.
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD COLUMN co_motor_busca VARCHAR(10)
        """
    )
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD CONSTRAINT ck_damas_motor_busca
            CHECK (co_motor_busca IS NULL OR co_motor_busca IN ('dart', 'rust'))
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN jogo_damas.tb002_jogada.co_motor_busca IS
        'Qual motor escolheu este lance: dart (roda em qualquer aparelho) ou '
        'rust (o nativo). NULL = lance do humano, ou lance unico sem busca. '
        'Fica na JOGADA e nao na partida porque o app cai de rust para dart '
        'por lance, quando a biblioteca nativa nao responde.'
        """
    )

    # ── 3. A view precisa ser refeita ───────────────────────────────────────
    #
    # Ver a armadilha do `SELECT j.*` no cabecalho. O corpo e identico ao da
    # 0012: so o momento da expansao muda, e agora ele inclui `co_motor_busca`.
    # ⚠️ A ORDEM DAS COLUNAS ABAIXO NAO E LIVRE. As quinze primeiras estao na
    # ordem exata em que a 0012 as criou, seguidas das duas do JOIN — que e a
    # ordem em que o `j.*` as expandiu na view original. `co_motor_busca` vem
    # DEPOIS de todas. Trocar qualquer uma de lugar faz o `CREATE OR REPLACE`
    # falhar com "cannot change name of view column".
    op.execute(
        """
        CREATE OR REPLACE VIEW jogo_damas.vw002_jogada AS
        SELECT j.id_jogada,
               j.co_jogador,
               j.co_lance,
               j.co_fen_antes,
               j.qt_captura_pedra,
               j.qt_captura_dama,
               j.ic_promoveu,
               j.co_tipo_peca_inicio,
               j.qt_nos_visitados,
               j.nu_profundidade_atingida,
               j.nu_motivo_parada_busca,
               j.nu_tempo_busca_ms,
               j.nu_avaliacao_brancas,
               j.nu_semente,
               j.js_extra,
               m.co_motivo_parada_busca,
               m.no_motivo_parada_busca,
               -- A coluna nova, e ela vem por ultimo de proposito.
               j.co_motor_busca
          FROM jogo_damas.tb002_jogada j
          LEFT JOIN jogo_damas.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )


def downgrade() -> None:
    # A ordem e a inversa da subida, e a view sai primeiro: ela depende da
    # coluna, e o Postgres recusaria o DROP COLUMN com ela de pe.
    #
    # ⚠️ `DROP` aqui e legitimo: o `downgrade()` nunca roda em producao (existe
    # para o ambiente local), e o cadeado de migracao aditiva o ignora de
    # proposito. No `upgrade()` seria proibido — ver o cabecalho.
    op.execute("DROP VIEW jogo_damas.vw002_jogada")
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            DROP CONSTRAINT IF EXISTS ck_damas_motor_busca
        """
    )
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            DROP COLUMN IF EXISTS co_motor_busca
        """
    )
    op.execute(
        """
        CREATE VIEW jogo_damas.vw002_jogada AS
        SELECT j.*,
               m.co_motivo_parada_busca,
               m.no_motivo_parada_busca
          FROM jogo_damas.tb002_jogada j
          LEFT JOIN jogo_damas.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )

    # ⚠️ O motivo `5` sai por ULTIMO, e so se nenhuma linha o estiver usando.
    # Um DELETE cego violaria a FK e derrubaria o downgrade no meio, deixando o
    # banco num estado que nao e nem o de antes nem o de depois.
    op.execute(
        """
        DELETE FROM jogo_damas.tb902_motivo_parada_busca
         WHERE nu_motivo_parada_busca = 5
           AND NOT EXISTS (
               SELECT 1 FROM jogo_damas.tb002_jogada
                WHERE nu_motivo_parada_busca = 5
           )
        """
    )
