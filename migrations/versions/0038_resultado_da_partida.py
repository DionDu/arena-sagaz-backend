"""O resultado explícito da partida em `partida.tb001_partida` (T168 da spec 010).

Revision ID: 0038_resultado_da_partida
Revises: 0037_tipos_quatro_meio
Create Date: 2026-10-30

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRAÇÃO EXISTE
═══════════════════════════════════════════════════════════════════════════

Até a 1.3.1 o servidor deduzia o resultado da partida apenas do placar
(`nu_placar_j1` x `nu_placar_j2`), tanto ao somar vitórias/derrotas/empates em
`progressao.tb001_progressao_usuario` quanto na coluna derivada `co_resultado`
de `partida.vw001_partida`.

Nas damas, porém, o placar gravado é a quantidade de PEÇAS RESTANTES no
tabuleiro ao fim da partida. Um empate por acordo, repetição ou regra de lances
sem captura com 5 peças contra 3 era contado como `empate` no aparelho e como
vitória/derrota no servidor. Quando a adoção campo a campo por `GREATEST`
juntava os contadores dos dois lados, `nu_vitorias + nu_derrotas + nu_empates`
ultrapassava `nu_partidas` e a reconciliação passava a ser recusada com 422
(`progressao_inconsistente`).

Folha de aval assinada pelo dono em 30/10/2026 (`docs/DECISOES-do-dono.md`
§8zzzz10 do app; `specs/010-jogo-quatro-em-linha/PASSAGEM-correcao-progressao-30-10.md`
§4):

1. `partida.tb001_partida.co_resultado VARCHAR(10)` anulável, sem `DEFAULT`, no
   fim da tabela:
   - `NULL` significa "o app não informou o resultado (versão antiga ou partida
     ainda em andamento); vale a dedução pelo placar";
   - não reescreve a tabela no PostgreSQL (instantâneo em produção);
2. `CHECK ck_partida_resultado` restringindo os valores não nulos aos três do
   ponto de vista do Jogador 1 (`'venceu_j1'`, `'venceu_j2'`, `'empate'`);
3. `CREATE OR REPLACE VIEW partida.vw001_partida`:
   - mantém as 20 colunas existentes com os mesmos nomes, tipos e posições, para
     não exigir `DROP VIEW` na subida e não quebrar nenhuma leitura em voo;
   - a coluna 19 (`co_resultado`, tipo `text`) passa a ser
     `COALESCE(p.co_resultado, CASE ... placar ... END)::text` (o cast explícito
     `::text` preserva o tipo exato da VIEW atual, pois `COALESCE` entre dois
     `varchar`/literais produziria `character varying` e o Postgres recusaria o
     `OR REPLACE`);
   - acrescenta ao FIM a coluna 21 `ic_resultado_informado`
     (`p.co_resultado IS NOT NULL`), que distingue dado informado pelo app de
     dado deduzido pelo placar;
   - ⚠️ `p.co_resultado` NÃO aparece solto na lista de colunas do `SELECT`, pois
     o nome `co_resultado` já pertence à coluna 19 da VIEW.

═══════════════════════════════════════════════════════════════════════════
COMPATIBILIDADE COM QUEM NÃO ATUALIZAR (1.3.1 EM CAMPO) E DEPLOY EM DUAS ETAPAS
═══════════════════════════════════════════════════════════════════════════

- **Entre a migração e o deploy do código novo do servidor:** o `INSERT` do
  código antigo lista as colunas por nome e não conhece `co_resultado`; a coluna
  nasce `NULL` e a VIEW continua calculando pelo placar como antes.
- **Depois do deploy, com app 1.3.1:** o payload antigo não traz `co_resultado`,
  o repositório grava `NULL`, `ic_resultado_informado` fica `FALSE` e tanto a
  VIEW quanto a progressão usam o placar, dando exatamente os números de hoje.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0038_resultado_da_partida"
down_revision: Union[str, None] = "0037_tipos_quatro_meio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona `co_resultado` na partida e atualiza `partida.vw001_partida`."""
    # 1) Coluna anulável e sem DEFAULT: no PostgreSQL isto apenas registra a
    #    coluna no catálogo, sem reescrever linhas nem segurar lock longo.
    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            ADD COLUMN IF NOT EXISTS co_resultado VARCHAR(10)
        """
    )

    # 2) Domínio fechado do ponto de vista do Jogador 1 (azul / humano contra a
    #    CPU). As linhas existentes são todas NULL e passam na hora.
    #    ⚠️ O repositório sanitiza valores fora deste trio para NULL antes do
    #    SQL, para que um payload estragado nunca estoure o CHECK nem vire
    #    `falha_processamento` (o que faria o app apagar a partida da fila).
    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            ADD CONSTRAINT ck_partida_resultado
            CHECK (
                co_resultado IS NULL
                OR co_resultado IN ('venceu_j1', 'venceu_j2', 'empate')
            )
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN partida.tb001_partida.co_resultado IS
            'Resultado informado pelo app do ponto de vista do J1 (venceu_j1, venceu_j2, empate); nulo quando o app nao informou (vale o placar na vw001_partida).'
        """
    )

    # 3) `CREATE OR REPLACE VIEW` preserva os nomes, tipos e posições das 20
    #    colunas já existentes (conferidas no `des` e no `prd` na revisão 0037)
    #    e acrescenta `ic_resultado_informado` na 21ª posição (ao fim, única
    #    posição em que o PostgreSQL aceita coluna nova sem `DROP VIEW`).
    op.execute(
        """
        CREATE OR REPLACE VIEW partida.vw001_partida AS
        SELECT p.id_partida,
               p.co_evento,
               p.co_jogo,
               p.co_variante,
               p.co_modo,
               p.id_usuario,
               p.id_usuario_j2,
               p.co_dificuldade,
               p.nu_placar_j1,
               p.nu_placar_j2,
               p.ic_pontua,
               p.co_status,
               p.co_lote_migracao,
               p.dh_inicio,
               p.dh_fim,
               p.nu_offset_minuto_j1,
               p.nu_offset_minuto_j2,
               p.qt_usos_poder,
               COALESCE(
                   p.co_resultado,
                   CASE
                       WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'
                       WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'
                       ELSE 'empate'
                   END
               )::text AS co_resultado,
               (p.qt_usos_poder > 0) AS ic_com_poder,
               (p.co_resultado IS NOT NULL) AS ic_resultado_informado
          FROM partida.tb001_partida p
        """
    )


def downgrade() -> None:
    """Desfaz a coluna e devolve `partida.vw001_partida` ao formato da 0017/0037.

    ⚠️ **Só para ambiente local.** `CREATE OR REPLACE VIEW` não remove colunas,
    por isso a descida derruba a VIEW antes do `DROP COLUMN` e a recria em
    seguida com as 20 colunas originais. Conferido via `pg_depend` no `des` e no
    `prd` (30/10/2026) que nenhuma outra VIEW depende de `partida.vw001_partida`
    (`jogo_damas.vw003_recusa` faz JOIN direto com `partida.tb001_partida`).
    """
    op.execute("DROP VIEW IF EXISTS partida.vw001_partida")

    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            DROP CONSTRAINT IF EXISTS ck_partida_resultado,
            DROP COLUMN IF EXISTS co_resultado
        """
    )

    op.execute(
        """
        CREATE VIEW partida.vw001_partida AS
        SELECT p.id_partida,
               p.co_evento,
               p.co_jogo,
               p.co_variante,
               p.co_modo,
               p.id_usuario,
               p.id_usuario_j2,
               p.co_dificuldade,
               p.nu_placar_j1,
               p.nu_placar_j2,
               p.ic_pontua,
               p.co_status,
               p.co_lote_migracao,
               p.dh_inicio,
               p.dh_fim,
               p.nu_offset_minuto_j1,
               p.nu_offset_minuto_j2,
               p.qt_usos_poder,
               CASE
                   WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'::text
                   WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'::text
                   ELSE 'empate'::text
               END AS co_resultado,
               (p.qt_usos_poder > 0) AS ic_com_poder
          FROM partida.tb001_partida p
        """
    )
