"""A `ic_cpu` da `partida.vw002_jogada` passa a reconhecer a CPU do desafio.

Revision ID: 0029_ic_cpu_no_desafio
Revises: 0028_piso_de_xp_do_desafio
Create Date: 2026-10-09

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

A coluna derivada `ic_cpu` ("este lance foi da CPU?") nasceu quando so havia
dois modos de partida: `vs_cpu` e `pvp_local`. A regra era

    co_modo = 'vs_cpu' AND nu_jogador = 2

A `0020` criou o modo `desafio` - em que a pessoa tambem joga contra a CPU, e a
CPU tambem e o jogador 2 - e nao atualizou esta view. Resultado, achado na
conferencia do `prd` de 09/10/2026 (a 1.3.0 no TestFlight): os 19 lances da CPU
no desafio do dono sairam com `ic_cpu = false`.

⚠️ **Nenhum dado estava errado.** A origem de cada lance (`nu_origem_decisao =
cpu`) foi gravada certa; so a leitura derivada mentia. E nenhum codigo le a
`ic_cpu` (app, API, job, painel e laboratorio conferidos): o estrago se limitava
a quem consulta a view a mao.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE `CREATE OR REPLACE`, E POR QUE ISSO E ADITIVO
═══════════════════════════════════════════════════════════════════════════

So muda a EXPRESSAO de uma coluna que ja existe: mesmo nome, mesmo tipo
(`boolean`), mesma posicao. E exatamente o que o `CREATE OR REPLACE VIEW` do
Postgres aceita - sem `DROP`, sem tocar em tabela, sem reescrever linha. A
`0017` precisou de `DROP` + `CREATE` porque acrescentava colunas ANTES da
derivada; aqui nao entra coluna nenhuma.

⚠️ `j.*` e expandido na hora da criacao. A `partida.tb002_jogada` tem hoje as
mesmas colunas de quando a `0017` criou a view, entao a lista sai identica - e
se nao saisse, o proprio `CREATE OR REPLACE` recusaria, em vez de passar.

⚠️ **Migracao nova, e nao a `0020` editada**: migracao ja aplicada nao se edita
(regra do dono de 10/09/2026).
"""

from __future__ import annotations

from alembic import op

# Identificadores que o Alembic usa para encadear as migracoes. O `revision`
# tem de caber em 32 caracteres (a coluna `alembic_version.version_num`).
revision = "0029_ic_cpu_no_desafio"
down_revision = "0028_piso_de_xp_do_desafio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Refaz a view com o `desafio` contado como partida contra a CPU."""
    op.execute(
        """
        CREATE OR REPLACE VIEW partida.vw002_jogada AS
        SELECT j.*,
               -- A CPU e sempre o jogador 2 quando ha CPU na partida: contra a
               -- CPU e no desafio. No `pvp_local` o jogador 2 e uma pessoa.
               (p.co_modo IN ('vs_cpu', 'desafio') AND j.nu_jogador = 2) AS ic_cpu,
               -- ⚠️ A leitura correta de `nu_lance`, ja pronta. Nos jogos sem
               -- poder ele e NULO, e o lance E a ordem — quem consultar a
               -- coluna crua diretamente vai achar que o dado esta faltando.
               COALESCE(j.nu_lance, j.nu_ordem) AS nu_lance_efetivo
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )


def downgrade() -> None:
    """Volta a regra antiga, em que so o `vs_cpu` tinha CPU."""
    op.execute(
        """
        CREATE OR REPLACE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu,
               COALESCE(j.nu_lance, j.nu_ordem) AS nu_lance_efetivo
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )
