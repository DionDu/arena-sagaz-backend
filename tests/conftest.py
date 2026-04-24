import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def cliente_http():
    from api.main import app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        yield cliente
