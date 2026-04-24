import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.banco.base import Base
from api.nucleo.seguranca import criar_token_acesso, gerar_hash_senha

_DB_URL_TESTE = "sqlite+aiosqlite:///./test.db"


@pytest_asyncio.fixture(scope="session")
async def engine_teste():
    engine = create_async_engine(_DB_URL_TESTE, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def sessao_teste(engine_teste):
    fabrica = async_sessionmaker(engine_teste, expire_on_commit=False)
    async with fabrica() as sessao:
        yield sessao
        await sessao.rollback()


@pytest_asyncio.fixture
async def cliente_http(engine_teste):
    from api.main import app
    from api.banco.conexao import get_sessao
    from api.banco.base import Base

    fabrica = async_sessionmaker(engine_teste, expire_on_commit=False)

    async def _get_sessao_teste():
        async with fabrica() as sessao:
            yield sessao

    app.dependency_overrides[get_sessao] = _get_sessao_teste
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def usuario_autenticado(sessao_teste):
    from api.usuarios.modelo import Usuario
    import uuid

    usuario = Usuario(
        id=str(uuid.uuid4()),
        apelido="teste_user",
        email="teste@example.com",
        senha_hash=gerar_hash_senha("senha12345"),
    )
    sessao_teste.add(usuario)
    await sessao_teste.commit()
    token, _ = criar_token_acesso({"sub": usuario.id})
    return {"usuario": usuario, "token": token}
