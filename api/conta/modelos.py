"""Modelos Pydantic da conta (request/response) — tarefa T034.

Pydantic valida e serializa os dados que entram e saem da API. O app **não**
manda uid/e-mail/provedor no corpo: isso vem do **token verificado** (mais
seguro). O corpo carrega só dados de perfil que a pessoa preenche.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Idiomas suportados pelo app (espelha IDIOMAS_SUPORTADOS em nucleo/dependencias).
# `Literal` faz o Pydantic recusar (422) qualquer valor fora desta lista, em vez
# de gravar lixo como "xx"/"zz" (NEG-04).
IdiomaSuportado = Literal["pt", "en", "es"]
# Documentos legais que aceitam registro de aceite (NEG-04).
DocumentoLegal = Literal["termos", "privacidade"]


class SessaoRequest(BaseModel):
    """Corpo do `POST /v1/conta/sessao`.

    Todos os campos são **opcionais**: numa reentrada, o app pode não mandar nada
    (só o token). No **primeiro** login é preciso comprovar a idade mínima — mas
    essa regra é validada no serviço (para devolver 422 com mensagem clara), não
    aqui.

    ## Duas formas de comprovar a idade — de propósito

    - `ic_idade_minima_declarada` — **a forma atual**. A pessoa marca "tenho 13
      anos ou mais". É só o que precisamos saber, e foi o que a App Review exigiu
      (diretriz 5.1.1(v): não peça dado pessoal que a funcionalidade não usa).
    - `dt_nascimento` — **legado**, mantido só por compatibilidade. As builds
      1.0 (2) e anteriores, que estão instaladas em campo, só sabem enviar isto.
      Continua funcionando até o force-update retirá-las (`CLAUDE.md`: nunca
      quebre um cliente ainda em campo). O valor **não é mais persistido** —
      serve apenas para derivar a declaração.
    """

    no_exibicao: Optional[str] = Field(default=None, max_length=40)
    dt_nascimento: Optional[date] = None
    ic_idade_minima_declarada: Optional[bool] = None
    co_idioma_preferido: Optional[IdiomaSuportado] = None


class PerfilUsuario(BaseModel):
    """Resposta de perfil (de `POST /v1/conta/sessao` e `GET /v1/conta/perfil`).

    ⚠️ Campo só se **acrescenta** aqui, nunca se remove nem se renomeia: várias
    versões do app convivem em campo lendo esta resposta (`CLAUDE.md` — mudança
    aditiva não sobe a versão da API; quebradora exigiria `/v2`).
    """

    co_usuario: str
    no_exibicao: Optional[str] = None
    no_email: Optional[str] = None
    # LEGADO: hoje sempre `None` (a migração 0010 zerou a coluna e nada mais a
    # grava). Continua na resposta porque o app 1.0 (2) em campo lê este campo;
    # sumir com ele seria mudança quebradora.
    dt_nascimento: Optional[date] = None
    # A pessoa declarou ter a idade mínima (13+). Substituiu a data de nascimento.
    ic_idade_minima_declarada: bool = False
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
            ic_idade_minima_declarada=linha.get("ic_idade_minima_declarada", False),
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

    co_documento: DocumentoLegal  # "termos" | "privacidade" (NEG-04)
    co_versao: str = Field(max_length=20)  # ex.: "1.0"
    co_idioma: IdiomaSuportado  # "pt" | "en" | "es" (NEG-04)


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


# ── US4: editar perfil e excluir conta ───────────────────────────────────────


class AtualizarPerfilRequest(BaseModel):
    """Corpo do `PATCH /v1/conta/perfil` — edição do perfil pela tela de Conta.

    Permite editar **nome de exibição** e **idioma**. Campos ausentes = "não mexa
    neste campo".

    `dt_nascimento` continua aceito **só por compatibilidade**: a tela de Conta do
    app novo já não oferece edição de data, mas a build 1.0 (2) em campo oferece.
    O serviço ainda revalida a idade mínima ao recebê-la (NEG-02: não dá para
    burlar a trava mandando uma data de criança depois de a conta existir) — a
    diferença é que agora o valor **não é gravado**, só liga a declaração."""

    no_exibicao: Optional[str] = Field(default=None, max_length=40)
    co_idioma_preferido: Optional[IdiomaSuportado] = None
    dt_nascimento: Optional[date] = None


class ExclusaoContaResposta(BaseModel):
    """Resposta do `DELETE /v1/conta` — confirma a anonimização da conta."""

    ic_anonimizado: bool = True
