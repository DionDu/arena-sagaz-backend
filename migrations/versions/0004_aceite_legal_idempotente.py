"""Aceite legal idempotente por (usuário, documento, versão) — NEG-05

Antes, `POST /v1/conta/aceite-legal` inseria uma linha NOVA a cada chamada, sem
teto: o mesmo usuário podia registrar o mesmo aceite (mesmo documento, mesma
versão) infinitas vezes, inflando `conta.tb003_aceite_legal` sem valor de
auditoria. Esta migração adiciona uma constraint UNIQUE em
(id_usuario, co_documento, co_versao) para o repositório poder fazer UPSERT
idempotente (re-aceitar a MESMA versão vira no-op; versões novas seguem gerando
linhas).

Antes de criar a constraint, removemos as duplicatas já existentes mantendo a
linha de aceite MAIS ANTIGA de cada (usuário, documento, versão) — é a que tem
valor de auditoria (o primeiro aceite daquela versão).

Revision ID: 0004_aceite_legal_idempotente
Revises: 0003_conta_nuvem
Create Date: 2026-07-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_aceite_legal_idempotente"
down_revision: Union[str, None] = "0003_conta_nuvem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Desduplica: mantém a linha mais antiga (menor dh_aceite; empate pelo id)
    #    de cada trio (id_usuario, co_documento, co_versao).
    op.execute(
        """
        DELETE FROM conta.tb003_aceite_legal a
        USING conta.tb003_aceite_legal b
        WHERE a.id_usuario   = b.id_usuario
          AND a.co_documento = b.co_documento
          AND a.co_versao    = b.co_versao
          AND (a.dh_aceite, a.id_aceite_legal) > (b.dh_aceite, b.id_aceite_legal)
        """
    )

    # 2) Constraint que habilita o ON CONFLICT idempotente no repositório.
    op.execute(
        """
        ALTER TABLE conta.tb003_aceite_legal
        ADD CONSTRAINT uq_aceite_usuario_documento_versao
        UNIQUE (id_usuario, co_documento, co_versao)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE conta.tb003_aceite_legal "
        "DROP CONSTRAINT IF EXISTS uq_aceite_usuario_documento_versao"
    )
