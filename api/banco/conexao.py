from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.configuracao import configuracoes

engine = create_async_engine(
    configuracoes.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    echo=configuracoes.AMBIENTE == "desenvolvimento",
)

_fabrica_sessao = async_sessionmaker(engine, expire_on_commit=False)


async def get_sessao() -> AsyncGenerator[AsyncSession, None]:
    async with _fabrica_sessao() as sessao:
        yield sessao
