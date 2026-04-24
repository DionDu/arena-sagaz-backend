"""Criar tabelas partidas, ranking, trofeus, usuario_trofeus

Revision ID: 002
Revises: 001
Create Date: 2026-04-19 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trofeus",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("codigo", sa.String(50), nullable=False, unique=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("descricao", sa.Text, nullable=False),
        sa.Column("criterio", sa.String(255), nullable=False),
    )

    op.create_table(
        "ranking",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("usuario_id", sa.String(36), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pontuacao_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("partidas_jogadas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("vitorias", sa.Integer, nullable=False, server_default="0"),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ranking_pontuacao_total", "ranking", [sa.text("pontuacao_total DESC")])
    op.create_index("ix_ranking_usuario_id", "ranking", ["usuario_id"], unique=True)

    op.create_table(
        "partidas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("usuario_id", sa.String(36), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("modo_jogo", sa.String(20), nullable=False),
        sa.Column("tamanho_tabuleiro", sa.String(10), nullable=False),
        sa.Column("dificuldade", sa.String(10), nullable=True),
        sa.Column("caixas_jogador", sa.Integer, nullable=False),
        sa.Column("caixas_adversario", sa.Integer, nullable=False),
        sa.Column("resultado", sa.String(10), nullable=False),
        sa.Column("xp_obtido", sa.Integer, nullable=False),
        sa.Column("pontuacao_obtida", sa.Integer, nullable=False),
        sa.Column("jogado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("modo_jogo IN ('vs_cpu', 'vs_humano_local')", name="ck_partidas_modo_jogo"),
        sa.CheckConstraint("tamanho_tabuleiro IN ('pequeno', 'medio', 'grande')", name="ck_partidas_tamanho"),
        sa.CheckConstraint("dificuldade IN ('facil', 'normal', 'sagaz') OR dificuldade IS NULL", name="ck_partidas_dificuldade"),
        sa.CheckConstraint("resultado IN ('vitoria', 'derrota', 'empate')", name="ck_partidas_resultado"),
    )
    op.create_index("ix_partidas_usuario_id", "partidas", ["usuario_id"])
    op.create_index("ix_partidas_jogado_em", "partidas", ["jogado_em"])

    op.create_table(
        "usuario_trofeus",
        sa.Column("usuario_id", sa.String(36), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trofeu_id", sa.String(36), sa.ForeignKey("trofeus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conquistado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("usuario_id", "trofeu_id"),
    )


def downgrade() -> None:
    op.drop_table("usuario_trofeus")
    op.drop_table("partidas")
    op.drop_table("ranking")
    op.drop_table("trofeus")
