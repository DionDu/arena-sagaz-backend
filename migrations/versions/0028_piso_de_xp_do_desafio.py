"""O piso da pontuacao do desafio desce de 18 para 12 (DECISOES-do-dono §8zs).

Revision ID: 0028_piso_de_xp_do_desafio
Revises: 0027_retrato_da_resolucao
Create Date: 2026-10-04

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

A pontuacao de uma resolucao era `18 + 12 x Q`: so 12 XP moviam, e deles, os
3 da dica e os 2,4 do tempo saiam cheios para quase todos. Quem nao pedia dica
caia sempre entre 26 e 30, e o quadro do dia empatava no topo. O dono, em
04/10/2026:

    "Concordo inclusive com o piso de 12XP, que seria a nota de quem faz
     inumeras tentativas, demora muito, usa muitas dicas."

A conta passou a `12 + 18 x Q` (app e servidor), e o `ck001_xp` da
`tb003_resolucao` precisa aceitar de 12 em diante - senao o banco recusaria a
resolucao de quem jogou pior, que e justamente quem a regua nova passa a
separar.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE DERRUBAR E RECRIAR, E POR QUE ISSO E ADITIVO
═══════════════════════════════════════════════════════════════════════════

O Postgres nao tem `ALTER CONSTRAINT ... CHECK`: trocar a regra de um `CHECK` e
sempre derrubar e criar outro com o mesmo nome (o caminho da `0020`). A troca
acontece numa transacao so, e a regra nova **contem** a antiga (12..30 inclui
18..30): nenhuma linha gravada deixa de valer, e o `ADD` revalida a tabela
inteira. `test_migracoes_aditivas.py` aceita o par pelo mesmo nome, e
`test_modelos_desafio.py` confere que a faixa nova contem a antiga.

⚠️ **Migracao nova, e nao a `0019` editada**: a regra do dono de 10/09/2026
(*"migracao ja aplicada NAO se edita. Crie outra"*) - a `0019` esta aplicada no
`des`.

⚠️ **Antes do deploy do backend**: o Railway publica a cada push. Com o codigo
novo no ar e o `CHECK` antigo no banco, toda resolucao abaixo de 18 seria
recusada com erro 500.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0028_piso_de_xp_do_desafio"
down_revision: Union[str, None] = "0027_retrato_da_resolucao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Troca o `ck001_xp` de 18..30 para 12..30.

    ⚠️ **O SQL e literal**: os cadeados leem o que a migracao executa com `ast`
    (`tests/unitarios/leitura_de_migracao.py`), e so enxergam string literal e
    f-string.
    """
    op.execute(
        "ALTER TABLE desafio_dia.tb003_resolucao DROP CONSTRAINT ck001_xp"
    )
    op.execute(
        "ALTER TABLE desafio_dia.tb003_resolucao ADD CONSTRAINT ck001_xp "
        "CHECK (nu_xp BETWEEN 12 AND 30)"
    )


def downgrade() -> None:
    """Volta o `ck001_xp` para 18..30.

    ⚠️ **Falha se houver resolucao gravada entre 12 e 17** - e e o certo: o
    `ADD` revalida a tabela, e voltar a regra antiga com essas linhas la deixaria
    dado que a propria regra recusa. Quem precisar descer apaga antes, sabendo
    o que apaga (so no ambiente local).
    """
    op.execute(
        "ALTER TABLE desafio_dia.tb003_resolucao DROP CONSTRAINT ck001_xp"
    )
    op.execute(
        "ALTER TABLE desafio_dia.tb003_resolucao ADD CONSTRAINT ck001_xp "
        "CHECK (nu_xp BETWEEN 18 AND 30)"
    )
