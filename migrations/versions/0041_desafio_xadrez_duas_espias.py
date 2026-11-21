"""O 12o tipo do xadrez no banco: as duas espias, no lugar da troca.

Revision ID: 0041_desafio_xadrez_duas_espias
Revises: 0040_desafio_xadrez
Create Date: 2026-11-21

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO FAZ
═══════════════════════════════════════════════════════════════════════════

Um INSERT so, na dimensao que ja existe: `desafio.tb901_tipo_desafio` ganha o
tipo 71, `xadrez_duas_espias` ("Coma com as duas espias"). A linha foi aprovada
pelo dono em 21/11/2026 (`arena-sagaz-frontend/docs/DECISOES-do-dono.md`
§8zzzz64), depois de seis reguas em que a troca (69) nao separou os niveis. O
`data-model.md` §3.1 da spec 012 tem a linha, e o cadeado
`tests/unitarios/test_migracao_desafio_xadrez_bate_com_data_model.py` le esta
migracao junto com a 0040.

⚠️ **Nenhuma medida nova.** O desafio usa as que a 0040 ja gravou:
`capturas_da_espia` (70) soma as capturas das duas espias, e `espia_comida`
(72) vale para qualquer uma delas. Com uma espia so (os outros cinco tipos da
espia), o resultado e o de antes; quem conta e `motores/xadrez/feitos_xadrez.py`
(e o medidor do app, com os mesmos vetores do juiz).

⚠️ **A troca NAO sai do banco.** Um tipo do banco nao e um tipo no ar: o 69 fica
na dimensao, sem receita no ar, como os tipos 7 e 10 das damas. Nada se apaga.

⚠️ **O 71 esta livre**: a faixa do xadrez na `tb901` vai de 60 a 79 (a 0040 usou
60 a 70), e o proximo jogo comeca no 80. Conferido em 21/11/2026 contra a 0040,
que e o head desta branch.

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele): no `des` antes do
push que leva o job a gerar o tipo 71; no `prd` na virada (fase 6), junto com a
0039 e a 0040.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0041_desafio_xadrez_duas_espias"
down_revision: Union[str, None] = "0040_desafio_xadrez"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta o tipo 71, as duas espias."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  71, 'xadrez_duas_espias',      'Coma com as duas espias',    'xadrez')
        """
    )


def downgrade() -> None:
    """Tira a linha.

    ⚠️ Um desafio publicado aponta para o tipo (chave estrangeira): o `DELETE`
    recusaria. O downgrade so cabe antes de o job gerar o primeiro desafio de
    duas espias.
    """
    op.execute("DELETE FROM desafio.tb901_tipo_desafio WHERE nu_tipo_desafio = 71")
