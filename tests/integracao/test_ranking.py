"""Testes de integração para /v1/ranking."""
import pytest


@pytest.mark.asyncio
async def test_ranking_vazio(cliente_http):
    resp = await cliente_http.get("/v1/ranking")
    assert resp.status_code == 200
    dados = resp.json()
    assert "jogadores" in dados
    assert "total" in dados


@pytest.mark.asyncio
async def test_ranking_com_usuario(cliente_http):
    criacao = await cliente_http.post("/v1/usuarios", json={
        "apelido": "ranktest1",
        "email": "rank1@test.com",
        "senha": "senha12345",
    })
    token = criacao.json()["acesso_token"]
    await cliente_http.post(
        "/v1/partidas",
        json={
            "modo_jogo": "vs_cpu",
            "tamanho_tabuleiro": "pequeno",
            "dificuldade": "sagaz",
            "caixas_jogador": 12,
            "caixas_adversario": 0,
            "resultado": "vitoria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await cliente_http.get("/v1/ranking")
    assert resp.status_code == 200
    jogadores = resp.json()["jogadores"]
    apelidos = [j["apelido"] for j in jogadores]
    assert "ranktest1" in apelidos


@pytest.mark.asyncio
async def test_paginacao(cliente_http):
    resp_p1 = await cliente_http.get("/v1/ranking?pagina=1&tamanho=1")
    resp_p2 = await cliente_http.get("/v1/ranking?pagina=2&tamanho=1")
    assert resp_p1.status_code == 200
    assert resp_p2.status_code == 200


@pytest.mark.asyncio
async def test_tamanho_maximo_100(cliente_http):
    resp = await cliente_http.get("/v1/ranking?tamanho=101")
    assert resp.status_code == 422
