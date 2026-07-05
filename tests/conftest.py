import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _desliga_rate_limit(monkeypatch):
    """Desliga o rate limiting (SEG-04) na maioria dos testes: eles disparam muitas
    requisições do MESMO IP (TestClient) e tripariam o limite. O teste dedicado
    `test_rate_limit.py` liga explicitamente para validar o 429."""
    from api.configuracao import configuracoes

    monkeypatch.setattr(configuracoes, "RATE_LIMIT_ENABLED", False)
