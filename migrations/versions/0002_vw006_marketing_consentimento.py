"""vw006: marketing vem da tb004 (fonte única do consentimento) — LGPD

Unifica o "aceite de marketing": em vez de a categoria `marketing` viver na
`tb006_preferencia_notificacao` (duplicando o consentimento), a VIEW
`vw006_preferencia_notificacao` passa a **derivar** a linha `marketing` da
`tb004_consentimento.ic_marketing` — a fonte única (e o registro legal LGPD).

Assim o app continua lendo `vw006` normalmente e enxerga o marketing com o
estado correto, sem saber que ele mora na tb004. (A ESCRITA do marketing é
roteada para a tb004 no `servico_preferencias.py`.)

Revision ID: 0002_vw006_marketing
Revises: 0001_fundacao_conta
Create Date: 2026-06-30
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_vw006_marketing"
down_revision: Union[str, None] = "0001_fundacao_conta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recria a VIEW: categorias != marketing continuam vindo da tb006; o
    # `marketing` é projetado a partir da tb004 (uma linha por usuário que tem
    # consentimento). `id_consentimento` preenche a coluna `id_preferencia`
    # (o app não usa esse id; só precisa das mesmas colunas/tipos).
    op.execute("DROP VIEW IF EXISTS conta.vw006_preferencia_notificacao")
    op.execute(
        """
        CREATE VIEW conta.vw006_preferencia_notificacao AS
            SELECT id_preferencia, id_usuario, co_categoria, ic_ativo,
                   dh_atualizacao
              FROM conta.tb006_preferencia_notificacao
             WHERE co_categoria <> 'marketing'
            UNION ALL
            SELECT id_consentimento AS id_preferencia,
                   id_usuario,
                   'marketing'::varchar(20) AS co_categoria,
                   ic_marketing AS ic_ativo,
                   dh_atualizacao
              FROM conta.tb004_consentimento
        """
    )


def downgrade() -> None:
    # Volta à VIEW original (espelho simples da tabela).
    op.execute("DROP VIEW IF EXISTS conta.vw006_preferencia_notificacao")
    op.execute(
        "CREATE VIEW conta.vw006_preferencia_notificacao AS "
        "SELECT * FROM conta.tb006_preferencia_notificacao"
    )
