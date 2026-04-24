"""Criar tabelas usuarios e tokens_refresh

Revision ID: 001
Revises:
Create Date: 2026-04-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "usuarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("apelido", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("nivel", sa.Integer, nullable=False, server_default="1"),
        sa.Column("xp_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("email_verificado", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)
    op.create_index("ix_usuarios_apelido", "usuarios", ["apelido"], unique=True)

    op.create_table(
        "tokens_refresh",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("usuario_id", sa.String(36), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tokens_refresh_token_hash", "tokens_refresh", ["token_hash"], unique=True)
    op.create_index("ix_tokens_refresh_usuario_id", "tokens_refresh", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("tokens_refresh")
    op.drop_table("usuarios")
