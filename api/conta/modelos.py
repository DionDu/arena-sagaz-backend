"""Modelos Pydantic da conta (request/response) — tarefa T034.

Pydantic valida e serializa os dados que entram e saem da API. O app **não**
manda uid/e-mail/provedor no corpo: isso vem do **token verificado** (mais
seguro). O corpo carrega só dados de perfil que a pessoa preenche.
"""
from __future__ import annotations

from datetime import date
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
