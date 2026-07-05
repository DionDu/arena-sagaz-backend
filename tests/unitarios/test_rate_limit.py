"""Testa o rate limiting por IP (SEG-04).

Liga explicitamente o limitador (o autouse do conftest o desliga nos demais
testes) e usa um `X-Forwarded-For` DIFERENTE por teste para o balde daquele IP
começar zerado — sem depender de reset do estado em memória do middleware.
"""
from fastapi.testclient import TestClient

from api.configuracao import configuracoes
from api.main import app


def _ligar(monkeypatch, *, leitura=3, escrita=2):
    monkeypatch.setattr(configuracoes, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(configuracoes, "RATE_LIMIT_POR_MINUTO", leitura)
    monkeypatch.setattr(configuracoes, "RATE_LIMIT_ESCRITA_POR_MINUTO", escrita)


def test_leitura_excede_limite_responde_429(monkeypatch):
    _ligar(monkeypatch, leitura=3)
    c = TestClient(app)
    ip = {"X-Forwarded-For": "203.0.113.10"}
    # Caminho inexistente: passa pelo middleware (que roda antes do roteamento) e
    # responde 404 — o que importa é que CONTA para o limite.
    for _ in range(3):
        r = c.get("/v1/naoexiste", headers=ip)
        assert r.status_code != 429
    # 4ª leitura no mesmo minuto → barrada.
    r = c.get("/v1/naoexiste", headers=ip)
    assert r.status_code == 429
    assert r.json()["codigo"] == "rate_limit_excedido"
    assert "Retry-After" in r.headers


def test_escrita_tem_limite_proprio(monkeypatch):
    _ligar(monkeypatch, leitura=100, escrita=2)
    c = TestClient(app)
    ip = {"X-Forwarded-For": "203.0.113.20"}
    for _ in range(2):
        r = c.post("/v1/naoexiste", headers=ip)
        assert r.status_code != 429
    r = c.post("/v1/naoexiste", headers=ip)
    assert r.status_code == 429


def test_health_e_isento(monkeypatch):
    _ligar(monkeypatch, leitura=1)
    c = TestClient(app)
    ip = {"X-Forwarded-For": "203.0.113.30"}
    # Várias chamadas ao health NÃO tripam (probe de infra é isento).
    for _ in range(5):
        r = c.get("/v1/health", headers=ip)
        assert r.status_code == 200


def test_ips_diferentes_nao_compartilham_balde(monkeypatch):
    _ligar(monkeypatch, leitura=2)
    c = TestClient(app)
    for _ in range(2):
        assert c.get("/v1/naoexiste", headers={"X-Forwarded-For": "203.0.113.40"}).status_code != 429
    # Outro IP começa do zero.
    assert c.get("/v1/naoexiste", headers={"X-Forwarded-For": "203.0.113.41"}).status_code != 429
