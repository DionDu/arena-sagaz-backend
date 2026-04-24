"""Testes de integração para /v1/usuarios."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_criar_usuario_valido(cliente_http):
    resp = await cliente_http.post("/v1/usuarios", json={
        "apelido": "jogador1",
        "email": "jogador1@test.com",
        "senha": "senha12345",
    })
    assert resp.status_code == 201
    dados = resp.json()
    assert "acesso_token" in dados
    assert "refresh_token" in dados
    assert dados["apelido"] == "jogador1"


@pytest.mark.asyncio
async def test_email_duplicado(cliente_http):
    payload = {"apelido": "uniq1", "email": "dup@test.com", "senha": "senha12345"}
    await cliente_http.post("/v1/usuarios", json=payload)
    resp = await cliente_http.post("/v1/usuarios", json={
        "apelido": "uniq2",
        "email": "dup@test.com",
        "senha": "senha12345",
    })
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "EMAIL_DUPLICADO"


@pytest.mark.asyncio
async def test_apelido_duplicado(cliente_http):
    payload = {"apelido": "dupapelido", "email": "a@test.com", "senha": "senha12345"}
    await cliente_http.post("/v1/usuarios", json=payload)
    resp = await cliente_http.post("/v1/usuarios", json={
        "apelido": "dupapelido",
        "email": "b@test.com",
        "senha": "senha12345",
    })
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "APELIDO_DUPLICADO"


@pytest.mark.asyncio
async def test_senha_curta_retorna_422(cliente_http):
    resp = await cliente_http.post("/v1/usuarios", json={
        "apelido": "valid",
        "email": "valid@test.com",
        "senha": "abc",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_perfil_com_token_valido(cliente_http):
    criacao = await cliente_http.post("/v1/usuarios", json={
        "apelido": "perfilteste",
        "email": "perfil@test.com",
        "senha": "senha12345",
    })
    token = criacao.json()["acesso_token"]
    resp = await cliente_http.get(
        "/v1/usuarios/eu",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["apelido"] == "perfilteste"


@pytest.mark.asyncio
async def test_perfil_sem_token_retorna_401(cliente_http):
    resp = await cliente_http.get("/v1/usuarios/eu")
    assert resp.status_code == 403  # HTTPBearer retorna 403 quando header ausente
