import pytest


@pytest.mark.asyncio
async def test_health(cliente_http):
    resp = await cliente_http.get("/v1/health")
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["status"] == "ok"
    assert dados["versao"] == "1.0.0"
