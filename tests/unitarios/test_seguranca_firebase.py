"""Testes da verificação de ID token do Firebase (T011) — com fake, sem rede."""
import asyncio

import pytest

from api.nucleo.excecoes import ErroNaoAutorizado
from api.nucleo.seguranca_firebase import (
    IdentidadeFirebase,
    VerificadorTokenFake,
    VerificadorTokenFirebase,
    _identidade_de_claims,
)


def test_identidade_de_claims_mapeia_campos():
    """Os claims do Firebase viram uma IdentidadeFirebase coerente."""
    claims = {
        "uid": "abc123",
        "email": "x@y.com",
        "email_verified": True,
        "name": "Fulano",
        "firebase": {"sign_in_provider": "google.com"},
    }
    ident = _identidade_de_claims(claims)
    assert ident.uid == "abc123"
    assert ident.email == "x@y.com"
    assert ident.email_verificado is True
    assert ident.provedor == "google.com"
    assert ident.nome == "Fulano"
    # O payload completo fica disponível em `claims`.
    assert ident.claims is claims


def test_identidade_aceita_uid_alternativo():
    """Quando não há 'uid', cai para 'user_id' e depois 'sub'."""
    assert _identidade_de_claims({"user_id": "u1"}).uid == "u1"
    assert _identidade_de_claims({"sub": "s1"}).uid == "s1"
    assert _identidade_de_claims({}).uid == ""


def test_fake_devolve_identidade_registrada():
    """O fake devolve exatamente a identidade associada ao token."""
    ident = IdentidadeFirebase(uid="u1", email="a@b.com", provedor="password")
    fake = VerificadorTokenFake({"token-bom": ident})
    resultado = asyncio.run(fake.verificar("token-bom"))
    assert resultado is ident


def test_fake_rejeita_token_desconhecido():
    """Token não registrado → 401 (ErroNaoAutorizado)."""
    fake = VerificadorTokenFake()
    with pytest.raises(ErroNaoAutorizado) as exc:
        asyncio.run(fake.verificar("token-ruim"))
    assert exc.value.codigo == "token_invalido"
    assert exc.value.status_http == 401


def test_real_sem_credencial_responde_401():
    """Sem FIREBASE_CREDENTIALS configurado, o verificador real recusa com 401
    (em vez de explodir com erro interno) — protege o /health e os testes."""
    verificador = VerificadorTokenFirebase()
    with pytest.raises(ErroNaoAutorizado) as exc:
        asyncio.run(verificador.verificar("qualquer"))
    assert exc.value.codigo == "firebase_nao_configurado"
