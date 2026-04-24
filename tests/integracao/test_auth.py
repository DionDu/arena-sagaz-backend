"""Testes de integração para /v1/auth."""
import pytest


@pytest.mark.asyncio
async def test_login_credenciais_corretas(cliente_http):
    await cliente_http.post("/v1/usuarios", json={
        "apelido": "logintest",
        "email": "login@test.com",
        "senha": "senha12345",
    })
    resp = await cliente_http.post("/v1/auth/login", json={
        "email": "login@test.com",
        "senha": "senha12345",
    })
    assert resp.status_code == 200
    dados = resp.json()
    assert "acesso_token" in dados
    assert "refresh_token" in dados
    assert dados["tipo_token"] == "bearer"


@pytest.mark.asyncio
async def test_login_credenciais_erradas(cliente_http):
    resp = await cliente_http.post("/v1/auth/login", json={
        "email": "naoexiste@test.com",
        "senha": "qualquercoisa",
    })
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "CREDENCIAIS_INVALIDAS"


@pytest.mark.asyncio
async def test_refresh_token_valido(cliente_http):
    criacao = await cliente_http.post("/v1/usuarios", json={
        "apelido": "refreshtest",
        "email": "refresh@test.com",
        "senha": "senha12345",
    })
    refresh = criacao.json()["refresh_token"]
    resp = await cliente_http.post("/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert "acesso_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_token_invalido(cliente_http):
    resp = await cliente_http.post("/v1/auth/refresh", json={"refresh_token": "token_invalido"})
    assert resp.status_code == 401
    assert resp.json()["codigo"] == "REFRESH_TOKEN_INVALIDO"


@pytest.mark.asyncio
async def test_logout_e_token_revogado(cliente_http):
    criacao = await cliente_http.post("/v1/usuarios", json={
        "apelido": "logouttest",
        "email": "logout@test.com",
        "senha": "senha12345",
    })
    dados = criacao.json()
    token = dados["acesso_token"]
    refresh = dados["refresh_token"]

    resp_logout = await cliente_http.post(
        "/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_logout.status_code == 200

    resp_refresh = await cliente_http.post(
        "/v1/auth/refresh", json={"refresh_token": refresh}
    )
    assert resp_refresh.status_code == 401
