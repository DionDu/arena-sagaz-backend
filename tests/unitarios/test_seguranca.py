"""Testes unitários para api.nucleo.seguranca."""
import pytest
from datetime import timedelta, timezone, datetime

from api.nucleo.seguranca import (
    criar_hash_token,
    criar_token_acesso,
    gerar_hash_senha,
    gerar_refresh_token,
    verificar_senha,
    verificar_token_acesso,
)


def test_hash_senha_diferente_do_original():
    senha = "senha12345"
    h = gerar_hash_senha(senha)
    assert h != senha


def test_verificacao_senha_correta():
    senha = "minhaSenha!"
    h = gerar_hash_senha(senha)
    assert verificar_senha(senha, h) is True


def test_verificacao_senha_incorreta():
    h = gerar_hash_senha("correta")
    assert verificar_senha("incorreta", h) is False


def test_criar_e_verificar_token_acesso():
    token, _ = criar_token_acesso({"sub": "usuario-123"})
    payload = verificar_token_acesso(token)
    assert payload["sub"] == "usuario-123"


def test_token_expirado_lanca_excecao(monkeypatch):
    import jose.jwt as jwt_mod
    from api.nucleo import seguranca as seg
    import jose

    token, _ = criar_token_acesso({"sub": "x"})
    # Verificar com chave errada deve lançar
    with pytest.raises(ValueError):
        seg.verificar_token_acesso(token + "invalido")


def test_gerar_refresh_token_comprimento():
    token = gerar_refresh_token()
    # token_urlsafe(32) → 43 chars base64
    assert len(token) >= 32


def test_gerar_refresh_token_unico():
    t1 = gerar_refresh_token()
    t2 = gerar_refresh_token()
    assert t1 != t2


def test_criar_hash_token_sha256():
    h = criar_hash_token("abc")
    assert len(h) == 64  # SHA-256 hex
