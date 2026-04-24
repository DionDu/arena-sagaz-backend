"""Carga inicial de troféus e selos

Revision ID: 003
Revises: 002
Create Date: 2026-04-19 00:02:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TROFEUS = [
    ("primeira_vitoria", "Primeira Vitória", "Vença sua primeira partida.", "vitorias >= 1"),
    ("dez_vitorias", "Dez Vitórias", "Acumule 10 vitórias.", "vitorias >= 10"),
    ("cem_vitorias", "Centurião", "Acumule 100 vitórias.", "vitorias >= 100"),
    ("sagaz_master", "Sagaz Master", "Vença uma partida no modo Sagaz.", "vitoria em modo sagaz"),
    ("primeiro_login", "Bem-vindo!", "Crie sua conta e faça o primeiro login.", "conta criada"),
    ("partidas_50", "Dedicado", "Jogue 50 partidas.", "partidas_jogadas >= 50"),
    ("partidas_200", "Veterano", "Jogue 200 partidas.", "partidas_jogadas >= 200"),
    ("nivel_5", "Nível 5", "Alcance o nível 5.", "nivel >= 5"),
    ("nivel_10", "Nível 10", "Alcance o nível 10.", "nivel >= 10"),
    ("nivel_25", "Nível 25", "Alcance o nível 25.", "nivel >= 25"),
    ("nivel_50", "Meio Centenário", "Alcance o nível 50.", "nivel >= 50"),
    ("nivel_100", "Lendário", "Alcance o nível 100.", "nivel >= 100"),
]


def upgrade() -> None:
    trofeus_table = sa.table(
        "trofeus",
        sa.column("id", sa.String),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
        sa.column("criterio", sa.String),
    )
    import uuid
    for codigo, nome, descricao, criterio in _TROFEUS:
        op.execute(
            trofeus_table.insert().values(
                id=str(uuid.uuid4()),
                codigo=codigo,
                nome=nome,
                descricao=descricao,
                criterio=criterio,
            ).prefix_with("OR IGNORE")  # SQLite; PostgreSQL usa ON CONFLICT
        )


def downgrade() -> None:
    codigos = [t[0] for t in _TROFEUS]
    op.execute(
        sa.text("DELETE FROM trofeus WHERE codigo IN :codigos").bindparams(
            codigos=tuple(codigos)
        )
    )
