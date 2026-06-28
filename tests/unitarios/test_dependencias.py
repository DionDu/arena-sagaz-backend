"""Testes das dependências do FastAPI (T012): usuário atual + cabeçalhos."""
import asyncio

import pytest

from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.excecoes import ErroNegocio, ErroNaoAutorizado
from api.nucleo.seguranca_firebase import (
    IdentidadeFirebase,
    VerificadorTokenFake,
    definir_verificador,
)


@pytest.fixture(autouse=True)
def _resetar_verificador():
    """Garante um verificador limpo por teste e reseta no fim."""
    yield
    definir_verificador(None)


# ── usuario_atual ───────────────────────────────────────────────────────────


def test_usuario_atual_sem_header_responde_401():
    with pytest.raises(ErroNaoAutorizado) as exc:
        asyncio.run(usuario_atual(authorization=None))
    assert exc.value.codigo == "sem_token"


def test_usuario_atual_header_malformado_responde_401():
    with pytest.raises(ErroNaoAutorizado):
        asyncio.run(usuario_atual(authorization="Token xyz"))


def test_usuario_atual_token_valido_devolve_identidade():
    ident = IdentidadeFirebase(uid="u1", email="a@b.com", provedor="google.com")
    definir_verificador(VerificadorTokenFake({"bom": ident}))
    resultado = asyncio.run(usuario_atual(authorization="Bearer bom"))
    assert resultado.uid == "u1"


def test_usuario_atual_token_invalido_responde_401():
    definir_verificador(VerificadorTokenFake())  # nenhum token válido
    with pytest.raises(ErroNaoAutorizado):
        asyncio.run(usuario_atual(authorization="Bearer ruim"))


# ── exigir_cabecalhos ────────────────────────────────────────────────────────


def test_cabecalhos_completos_montam_contexto():
    ctx = exigir_cabecalhos(
        x_app_version="1.2.3",
        x_platform="Android",
        accept_language="pt-BR,pt;q=0.9,en;q=0.8",
    )
    assert isinstance(ctx, ContextoRequisicao)
    assert ctx.versao_app == "1.2.3"
    assert ctx.plataforma == "android"  # normalizado para minúsculas
    assert ctx.idioma == "pt"  # região removida


def test_cabecalhos_faltando_versao_e_plataforma():
    with pytest.raises(ErroNegocio) as exc:
        exigir_cabecalhos(
            x_app_version=None, x_platform=None, accept_language="en"
        )
    assert exc.value.codigo == "cabecalhos_ausentes"
    assert exc.value.status_http == 400


def test_cabecalhos_plataforma_invalida():
    with pytest.raises(ErroNegocio) as exc:
        exigir_cabecalhos(
            x_app_version="1.0.0", x_platform="windows", accept_language="es"
        )
    assert exc.value.codigo == "plataforma_invalida"


def test_idioma_default_e_nao_suportado_caem_em_pt():
    # Sem Accept-Language → pt
    ctx1 = exigir_cabecalhos(
        x_app_version="1", x_platform="ios", accept_language=None
    )
    assert ctx1.idioma == "pt"
    # Idioma não suportado (de) → pt
    ctx2 = exigir_cabecalhos(
        x_app_version="1", x_platform="ios", accept_language="de-DE"
    )
    assert ctx2.idioma == "pt"
    # Espanhol é suportado
    ctx3 = exigir_cabecalhos(
        x_app_version="1", x_platform="ios", accept_language="es"
    )
    assert ctx3.idioma == "es"
