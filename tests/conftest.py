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


@pytest_asyncio.fixture
async def cliente_http():
    """Cliente HTTP assíncrono falando **direto com o app**, sem subir servidor.

    `ASGITransport` entrega a requisição à aplicação em memória: não abre porta,
    não usa rede e não depende de o Railway estar no ar. É o mesmo app que roda
    em produção, só que chamado de dentro do processo de teste.

    ⚠️ **Esta fixture faltava desde algum ponto do histórico**, e o efeito foi
    silencioso do jeito ruim: `tests/integracao/test_health.py` não *falhava* —
    ele dava ERRO de coleta ("fixture 'cliente_http' not found"), o que o pytest
    reporta separado da contagem de falhas. A suíte mostrava "233 passed, 1
    error" e o erro virou paisagem, anotado em dois documentos como
    "pré-existente, sem relação". Um teste que nunca roda não protege nada — e
    este protege justamente a rota que o **Railway** usa como `healthcheckPath`
    (ver `railway.json`): se ela quebrar, o deploy não sobe.
    """
    from api.main import app

    transporte = ASGITransport(app=app)
    async with AsyncClient(transport=transporte, base_url="http://teste") as c:
        yield c
