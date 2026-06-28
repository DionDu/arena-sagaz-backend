"""Ambiente de execução do Alembic (modo assíncrono, com asyncpg).

A URL do banco é lida da variável de ambiente ``DATABASE_URL`` (nunca do
arquivo .ini), e normalizada para o driver async. As migrações são escritas
à mão (sem autogenerate), então não há ``target_metadata``.
"""
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Objeto de configuração do Alembic (lê o alembic.ini).
config = context.config

# Configura o logging conforme o .ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrações manuais → sem metadata para autogenerate.
target_metadata = None


def _url() -> str:
    """URL do banco a partir de DATABASE_URL, com o driver async garantido."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """Modo offline: gera o SQL sem conectar (útil para revisar)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Modo online: conecta de fato e aplica as migrações."""
    configuracao = config.get_section(config.config_ini_section, {})
    configuracao["sqlalchemy.url"] = _url()
    connectable = async_engine_from_config(
        configuracao,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
