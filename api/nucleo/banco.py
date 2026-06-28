"""Camada de acesso ao banco de dados (PostgreSQL) — engine e sessão assíncronas.

A API fala com o banco por aqui. Usa SQLAlchemy no modo *async* com o driver
`asyncpg`. Por convenção do projeto, a LEITURA é feita pelas VIEWs
`conta.vwNNN_*` e a ESCRITA nas tabelas `conta.tbNNN_*`.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.configuracao import configuracoes


def _url_async(url: str) -> str:
    """Garante o driver async no esquema da URL.

    O Railway entrega `postgresql://...`; o SQLAlchemy async precisa de
    `postgresql+asyncpg://...`. Esta função normaliza ambos os formatos antigos.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):  # forma legada
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# Engine assíncrona: o "motor" com o pool de conexões. `create_async_engine`
# NÃO conecta na hora (conexão preguiçosa) — só ao executar a primeira consulta.
# `pool_pre_ping` testa a conexão antes de usar, evitando conexões mortas.
engine = create_async_engine(
    _url_async(configuracoes.DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
)

# Fábrica de sessões assíncronas. `expire_on_commit=False` mantém os objetos
# utilizáveis após o commit (padrão recomendado em apps web async).
SessaoLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def obter_sessao() -> AsyncGenerator[AsyncSession, None]:
    """Dependência do FastAPI: entrega uma sessão por requisição e a fecha ao fim.

    Uso numa rota:
        `async def rota(sessao: AsyncSession = Depends(obter_sessao)): ...`
    """
    async with SessaoLocal() as sessao:
        yield sessao
