"""Os descuidos do personagem do Quatro em Linha: tres codigos novos de acao.

Revision ID: 0034_acoes_de_descuido_quatro
Revises: 0033_schema_jogo_quatro
Create Date: 2026-10-14

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate 14/10/2026 cada personagem do Quatro em Linha tinha uma lista "nunca erra"
(vencer quando tem quatro na mao, tapar a vitoria do outro, nao jogar na casa
logo abaixo de uma vitoria do outro), tudo ou nada. O dono trocou a lista pela
CHANCE de o personagem perceber cada situacao (`arena-sagaz-frontend/docs/
DECISOES-do-dono.md` §8zzzf), e com isso o personagem passa a ter DESCUIDOS: a
Pita, por exemplo, deixa de tapar a vitoria da pessoa em 25% das vezes.

Cada descuido e um motivo novo de lance, e o motor (`politica_dificuldade_
quatro.dart`, versao 1.1.0) os devolve com estes codigos. Sem as linhas, o
ingestor grava o sentinela 9999 (`desconhecido`), e a consulta "quantas vezes a
Pita deixou de bloquear" fica impossivel - que e justamente a medida que
acerta a dificuldade. O dono aprovou os tres codigos na mesma conversa.

    7  vitoria_perdida   - nao percebeu a propria vitoria, e jogou outro lance
    8  bloqueio_perdido  - nao percebeu a vitoria do outro, e nao tapou
    9  jogou_sob_ameaca  - nao percebeu o perigo, e jogou na casa de baixo

⚠️ **E uma migracao NOVA, e nao a 0033 editada**: a 0033 ja esta aplicada no
`des` (T078), e migracao aplicada nao se edita. Ela so ACRESCENTA linhas a uma
dimensao: nenhuma tabela e nenhuma coluna mudam (o "dropa e recria" da §8b e
para defeito de modelagem, e isto nao e um).

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele), no `des` e, na
virada, no `prd`, junto da 0033. A ordem com o app nao importa: o app antigo
nunca manda estes codigos, e o novo, sem as linhas, grava o sentinela.
"""

from typing import Sequence, Union

from alembic import op

# Identificadores usados pelo Alembic para encadear as migracoes.
revision: str = "0034_acoes_de_descuido_quatro"
down_revision: Union[str, None] = "0033_schema_jogo_quatro"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta os tres descuidos a `jogo_quatro.tb901_jogada_acao`."""
    # Os numeros seguem os da 0033 (1 a 6); o sentinela 9999 fica onde esta.
    op.execute(
        """
        INSERT INTO jogo_quatro.tb901_jogada_acao (nu_acao, co_acao, no_acao) VALUES
            (7, 'vitoria_perdida',  'Descuido: nao viu a propria vitoria'),
            (8, 'bloqueio_perdido', 'Descuido: nao tapou a vitoria do outro'),
            (9, 'jogou_sob_ameaca', 'Descuido: jogou sob a ameaca do outro')
        """
    )


def downgrade() -> None:
    """Tira as tres linhas.

    ⚠️ Uma jogada gravada com um destes codigos aponta para a linha (chave
    estrangeira), e o `DELETE` recusaria: o downgrade so cabe antes de o app
    novo gravar alguma.
    """
    op.execute(
        """
        DELETE FROM jogo_quatro.tb901_jogada_acao WHERE nu_acao IN (7, 8, 9)
        """
    )
