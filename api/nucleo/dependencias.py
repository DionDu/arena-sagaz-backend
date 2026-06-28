"""Dependências do FastAPI usadas pelas rotas — tarefa T012.

Uma "dependência" do FastAPI é uma função que ele roda **antes** da rota e cujo
retorno é injetado como argumento. Aqui ficam duas:

- [usuario_atual]: lê o `Authorization: Bearer <token>`, verifica no Firebase e
  entrega a identidade (rotas protegidas dependem disto).
- [exigir_cabecalhos]: garante os cabeçalhos obrigatórios da nossa política de
  versionamento (`X-App-Version`, `X-Platform`, idioma) e devolve um contexto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header

from api.nucleo.excecoes import ErroNegocio, ErroNaoAutorizado
from api.nucleo.seguranca_firebase import IdentidadeFirebase, obter_verificador

# Plataformas aceitas no cabeçalho `X-Platform` (a diretriz de versionamento da
# API exige android/ios; aceitamos "web" para o ambiente de desenvolvimento).
PLATAFORMAS_VALIDAS = {"android", "ios", "web"}

# Idiomas suportados pelo app (o resto cai no padrão pt).
IDIOMAS_SUPORTADOS = {"pt", "en", "es"}


async def usuario_atual(
    authorization: Optional[str] = Header(default=None),
) -> IdentidadeFirebase:
    """Identidade do usuário autenticado, a partir do token Bearer.

    Lança 401 se o cabeçalho estiver ausente/malformado ou se o token não passar
    na verificação do Firebase.
    """
    # Espera "Bearer <token>" (o esquema é *case-insensitive* por padrão).
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ErroNaoAutorizado("Credenciais ausentes.", "sem_token")

    token = authorization[7:].strip()  # tudo depois de "Bearer "
    if not token:
        raise ErroNaoAutorizado("Credenciais ausentes.", "sem_token")

    verificador = obter_verificador()
    return await verificador.verificar(token)


@dataclass(frozen=True)
class ContextoRequisicao:
    """Dados de contexto extraídos dos cabeçalhos obrigatórios da requisição."""

    versao_app: str
    plataforma: str  # android | ios | web
    idioma: str  # pt | en | es


def _idioma_principal(accept_language: Optional[str]) -> str:
    """Extrai o idioma principal de um `Accept-Language` (ex.: 'pt-BR,pt;q=0.9').

    Pega o 1º item, descarta o peso (`;q=...`) e a região (`-BR`), e só aceita um
    idioma suportado; senão, devolve 'pt'.
    """
    if not accept_language:
        return "pt"
    # 1º idioma da lista, antes da vírgula e do ';'.
    primeiro = accept_language.split(",")[0].split(";")[0].strip().lower()
    # Tira a região: "pt-br" → "pt".
    base = primeiro.split("-")[0]
    return base if base in IDIOMAS_SUPORTADOS else "pt"


def exigir_cabecalhos(
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    x_platform: Optional[str] = Header(default=None, alias="X-Platform"),
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
) -> ContextoRequisicao:
    """Valida os cabeçalhos obrigatórios e devolve o [ContextoRequisicao].

    Lança 400 se `X-App-Version` ou `X-Platform` faltarem, ou se a plataforma for
    inválida. O idioma é opcional (default 'pt').
    """
    faltando = []
    if not x_app_version:
        faltando.append("X-App-Version")
    if not x_platform:
        faltando.append("X-Platform")
    if faltando:
        raise ErroNegocio(
            f"Cabeçalhos obrigatórios ausentes: {', '.join(faltando)}.",
            "cabecalhos_ausentes",
            status_http=400,
        )

    plataforma = x_platform.lower()  # type: ignore[union-attr]
    if plataforma not in PLATAFORMAS_VALIDAS:
        raise ErroNegocio(
            "Plataforma inválida (use android, ios ou web).",
            "plataforma_invalida",
            status_http=400,
        )

    return ContextoRequisicao(
        versao_app=x_app_version,  # type: ignore[arg-type]
        plataforma=plataforma,
        idioma=_idioma_principal(accept_language),
    )
