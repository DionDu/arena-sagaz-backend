"""Modelos Pydantic da conta (request/response) — tarefa T034.

Pydantic valida e serializa os dados que entram e saem da API. O app **não**
manda uid/e-mail/provedor no corpo: isso vem do **token verificado** (mais
seguro). O corpo carrega só dados de perfil que a pessoa preenche.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SessaoRequest(BaseModel):
    """Corpo do `POST /v1/conta/sessao`.

    Todos os campos são **opcionais**: numa reentrada, o app pode não mandar nada
    (só o token). No **primeiro** login, `dt_nascimento` é obrigatória — mas essa
    regra é validada no serviço (para devolver 422 `idade_minima`/`data_obrigatoria`
    com mensagem clara), não aqui.
    """

    no_exibicao: Optional[str] = Field(default=None, max_length=40)
    dt_nascimento: Optional[date] = None
    co_idioma_preferido: Optional[str] = Field(default=None, max_length=2)


class PerfilUsuario(BaseModel):
    """Resposta de perfil (de `POST /v1/conta/sessao` e `GET /v1/conta/perfil`)."""

    co_usuario: str
    no_exibicao: Optional[str] = None
    no_email: Optional[str] = None
    dt_nascimento: Optional[date] = None
    co_provedor_principal: str
    co_idioma_preferido: str
    ic_convidado: bool = False
    # Lista de códigos de provedor vinculados (ex.: ["google", "email"]).
    provedores: list[str] = Field(default_factory=list)

    @classmethod
    def de_linha(
        cls,
        linha: dict[str, Any],
        provedores: Optional[list[str]] = None,
    ) -> "PerfilUsuario":
        """Monta o perfil a partir de uma linha da VIEW `vw001_usuario` (dict) e
        da lista de códigos de provedor."""
        return cls(
            co_usuario=linha["co_usuario"],
            no_exibicao=linha.get("no_exibicao"),
            no_email=linha.get("no_email"),
            dt_nascimento=linha.get("dt_nascimento"),
            co_provedor_principal=linha["co_provedor_principal"],
            co_idioma_preferido=linha.get("co_idioma_preferido", "pt"),
            ic_convidado=linha.get("ic_convidado", False),
            provedores=provedores or [],
        )


# ── US3: aceite legal e consentimento ────────────────────────────────────────


class AceiteLegalRequest(BaseModel):
    """Corpo do `POST /v1/conta/aceite-legal` — registra o aceite de UM documento.

    O app envia um aceite por documento (ex.: termos, depois privacidade), com a
    **versão** e o **idioma** do texto que a pessoa viu (auditável)."""

    co_documento: str = Field(max_length=20)  # "termos" | "privacidade"
    co_versao: str = Field(max_length=20)  # ex.: "1.0"
    co_idioma: str = Field(max_length=2)  # "pt" | "en" | "es"


class AceiteLegalResposta(BaseModel):
    co_documento: str
    co_versao: str
    co_idioma: str
    dh_aceite: datetime

    @classmethod
    def de_linha(cls, linha: dict[str, Any]) -> "AceiteLegalResposta":
        return cls(
            co_documento=linha["co_documento"],
            co_versao=linha["co_versao"],
            co_idioma=linha["co_idioma"],
            dh_aceite=linha["dh_aceite"],
        )


class ConsentimentoRequest(BaseModel):
    """Corpo do `PUT /v1/conta/consentimento` — rastreamento (ads) e marketing.

    Ambos começam **desligados** por padrão (opt-in explícito)."""

    ic_rastreamento: bool = False
    ic_marketing: bool = False


class ConsentimentoResposta(BaseModel):
    ic_rastreamento: bool
    ic_marketing: bool
    dh_atualizacao: datetime

    @classmethod
    def de_linha(cls, linha: dict[str, Any]) -> "ConsentimentoResposta":
        return cls(
            ic_rastreamento=linha["ic_rastreamento"],
            ic_marketing=linha["ic_marketing"],
            dh_atualizacao=linha["dh_atualizacao"],
        )
