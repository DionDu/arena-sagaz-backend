"""O Quatro em Linha: os dois tipos de desafio que fecham no meio da partida.

Revision ID: 0037_tipos_quatro_meio
Revises: 0036_log_aparelho
Create Date: 2026-10-22

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO FAZ
═══════════════════════════════════════════════════════════════════════════

So INSERT numa dimensao que ja existe, `desafio.tb901_tipo_desafio`
(`data-model.md` §3.1 da spec 010; aprovado pelo dono em 22/10/2026,
`DECISOES-do-dono.md` §8zzzr item 9):

- 50 `quatro_encoste`: *"Encoste N pecas em ate M lances"*. A medida
  `pecas_encostadas` (nu_feito 50) ja existe desde a 0035; o que muda e a
  janela, curta, e a falta da `vitoria` na chegada - e isso que faz o desafio
  fechar no meio da partida.
- 51 `quatro_figura`: *"Forme a figura"*. A figura chega como dado no desafio
  publicado, e nao como tipo por figura: figura nova nao pede linha nova aqui.

⚠️ **Por que 50, e nao a faixa 40-49 do Quatro**: a faixa esta cheia (os dez da
0035). O 50 e o proximo numero livre (os outros jogos param no 22, da 0023). A
coincidencia com o `nu_feito` 50 da `tb902_catalogo_feito` nao importa: sao
tabelas diferentes, cada uma com a sua numeracao.

⚠️ **Tipo no banco nao e tipo no ar.** As receitas nascem em
`job/tipos_de_desafio.RECEITAS_FORA_DO_AR` e so sobem depois da regua
(T143 a T150 da spec 010). Ate la nenhum desafio aponta para estas linhas.

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele): no `des` antes do
push que leva um destes tipos ao ar; no `prd` na virada (T138).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0037_tipos_quatro_meio"
down_revision: Union[str, None] = "0036_log_aparelho"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta os dois tipos do Quatro que fecham no meio da partida."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  50, 'quatro_encoste',         'Encoste N em ate M',     'quatro'),
            (  51, 'quatro_figura',          'Forme a figura',         'quatro')
        """
    )


def downgrade() -> None:
    """Tira as duas linhas.

    ⚠️ Um desafio publicado aponta para o tipo (chave estrangeira): o `DELETE`
    recusaria. O downgrade so cabe antes de o job gerar o primeiro desafio de um
    destes tipos.
    """
    op.execute(
        "DELETE FROM desafio.tb901_tipo_desafio WHERE nu_tipo_desafio IN (50, 51)"
    )
