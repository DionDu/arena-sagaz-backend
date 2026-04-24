"""Testes de integração para /v1/partidas."""
import pytest


async def _criar_e_autenticar(cliente_http, apelido: str, email: str):
    resp = await cliente_http.post("/v1/usuarios", json={
        "apelido": apelido,
        "email": email,
        "senha": "senha12345",
    })
    dados = resp.json()
    return dados["acesso_token"]


@pytest.mark.asyncio
async def test_sincronizar_partida_valida(cliente_http):
    token = await _criar_e_autenticar(cliente_http, "pjogador1", "pj1@test.com")
    resp = await cliente_http.post(
        "/v1/partidas",
        json={
            "modo_jogo": "vs_cpu",
            "tamanho_tabuleiro": "pequeno",
            "dificuldade": "normal",
            "caixas_jogador": 7,
            "caixas_adversario": 5,
            "resultado": "vitoria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    dados = resp.json()
    assert dados["xp_obtido"] == int((7 + 20) * 1.5)


@pytest.mark.asyncio
async def test_dificuldade_ausente_em_vs_cpu(cliente_http):
    token = await _criar_e_autenticar(cliente_http, "pjogador2", "pj2@test.com")
    resp = await cliente_http.post(
        "/v1/partidas",
        json={
            "modo_jogo": "vs_cpu",
            "tamanho_tabuleiro": "pequeno",
            "caixas_jogador": 7,
            "caixas_adversario": 5,
            "resultado": "vitoria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_soma_caixas_invalida(cliente_http):
    token = await _criar_e_autenticar(cliente_http, "pjogador3", "pj3@test.com")
    resp = await cliente_http.post(
        "/v1/partidas",
        json={
            "modo_jogo": "vs_cpu",
            "tamanho_tabuleiro": "medio",
            "dificuldade": "normal",
            "caixas_jogador": 7,
            "caixas_adversario": 5,
            "resultado": "vitoria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sem_autenticacao_retorna_403(cliente_http):
    resp = await cliente_http.post(
        "/v1/partidas",
        json={
            "modo_jogo": "vs_cpu",
            "tamanho_tabuleiro": "pequeno",
            "dificuldade": "normal",
            "caixas_jogador": 7,
            "caixas_adversario": 5,
            "resultado": "vitoria",
        },
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_duas_sincronizacoes_acumulam(cliente_http):
    token = await _criar_e_autenticar(cliente_http, "pjogador4", "pj4@test.com")
    payload = {
        "modo_jogo": "vs_cpu",
        "tamanho_tabuleiro": "pequeno",
        "dificuldade": "facil",
        "caixas_jogador": 6,
        "caixas_adversario": 6,
        "resultado": "empate",
    }
    r1 = await cliente_http.post("/v1/partidas", json=payload, headers={"Authorization": f"Bearer {token}"})
    r2 = await cliente_http.post("/v1/partidas", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert r1.json()["xp_total"] < r2.json()["xp_total"]
