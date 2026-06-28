"""Verificação do ID token do Firebase (lado servidor) — tarefa T011.

O app faz login no Firebase e manda o **ID token** (um JWT) no cabeçalho
`Authorization: Bearer <token>`. Aqui o servidor **verifica** esse token com o
Firebase Admin SDK e extrai a identidade (uid, e-mail, provedor). Só então
confiamos em quem está chamando (FR-003/010).

Tudo é desenhado para ser **testável sem o Firebase real**: a verificação fica
atrás da interface [VerificadorToken], com uma implementação real
([VerificadorTokenFirebase]) e uma falsa ([VerificadorTokenFake]).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Protocol

from api.configuracao import configuracoes
from api.nucleo.excecoes import ErroNaoAutorizado
from api.nucleo.log import obter_logger

log = obter_logger("api.seguranca")


@dataclass(frozen=True)
class IdentidadeFirebase:
    """Identidade extraída de um ID token já verificado.

    `frozen=True` torna o objeto imutável (não muda depois de criado).
    `claims` guarda o payload completo do token, caso algo campo extra seja
    necessário no futuro — sem precisar mudar esta classe.
    """

    uid: str
    email: Optional[str] = None
    email_verificado: bool = False
    # Provedor do Firebase: "google.com", "apple.com", "password", "anonymous"...
    provedor: str = ""
    nome: Optional[str] = None
    claims: dict = field(default_factory=dict)


class VerificadorToken(Protocol):
    """Contrato de verificação de token. `Protocol` = *duck typing* tipado: qualquer
    classe com este método assíncrono serve, sem herança explícita."""

    async def verificar(self, id_token: str) -> IdentidadeFirebase: ...


def _identidade_de_claims(c: dict) -> IdentidadeFirebase:
    """Converte o dicionário de *claims* do Firebase numa [IdentidadeFirebase]."""
    info_firebase = c.get("firebase") or {}
    return IdentidadeFirebase(
        # O uid pode vir como "uid" (verify_id_token) ou "user_id"/"sub".
        uid=c.get("uid") or c.get("user_id") or c.get("sub") or "",
        email=c.get("email"),
        email_verificado=bool(c.get("email_verified", False)),
        provedor=info_firebase.get("sign_in_provider", ""),
        nome=c.get("name"),
        claims=c,
    )


class VerificadorTokenFirebase:
    """Implementação real: usa o Firebase Admin SDK.

    A inicialização do app Firebase é **preguiçosa** (só na 1ª verificação), para
    importar este módulo não exigir credenciais — importante para testes e para o
    `/health` subir mesmo sem o Firebase configurado.
    """

    def __init__(self) -> None:
        self._app = None  # cache do app Firebase inicializado

    def _garantir_app(self):
        """Inicializa (uma vez) o app Firebase a partir das configurações."""
        if self._app is not None:
            return self._app

        # Import local: só carrega a lib pesada quando realmente formos usá-la.
        import firebase_admin
        from firebase_admin import credentials

        bruto = (configuracoes.FIREBASE_CREDENTIALS or "").strip()
        if not bruto:
            # Sem credencial não há como verificar — erro de configuração, não
            # do usuário; mas respondemos 401 para não vazar detalhe de infra.
            raise ErroNaoAutorizado(
                "Verificação de identidade indisponível.",
                "firebase_nao_configurado",
            )

        # `FIREBASE_CREDENTIALS` carrega o **conteúdo JSON** da chave Admin (é
        # assim que vai nas Variables do Railway — sem arquivo no disco).
        dados = json.loads(bruto)
        cred = credentials.Certificate(dados)

        nome_app = "arena-sagaz"
        try:
            # Se já existe um app com esse nome (recarga/teste), reusa.
            self._app = firebase_admin.get_app(nome_app)
        except ValueError:
            self._app = firebase_admin.initialize_app(cred, name=nome_app)
        return self._app

    async def verificar(self, id_token: str) -> IdentidadeFirebase:
        from anyio import to_thread
        from firebase_admin import auth

        app = self._garantir_app()
        try:
            # `verify_id_token` é **síncrona** e faz I/O (busca chaves públicas,
            # com cache). Rodamos numa thread para não travar o *event loop*.
            decodificado = await to_thread.run_sync(
                lambda: auth.verify_id_token(id_token, app=app)
            )
        except ErroNaoAutorizado:
            raise
        except Exception as exc:  # token expirado, assinatura inválida, etc.
            # NUNCA logamos o token (é segredo). Só registramos que falhou.
            log.info("Falha ao verificar ID token", extra={"rota": "auth"})
            raise ErroNaoAutorizado(
                "Token inválido ou expirado.", "token_invalido"
            ) from exc

        return _identidade_de_claims(decodificado)


class VerificadorTokenFake:
    """Implementação falsa para testes: um mapa token→identidade em memória."""

    def __init__(self, identidades: Optional[dict[str, IdentidadeFirebase]] = None):
        self._identidades: dict[str, IdentidadeFirebase] = dict(identidades or {})

    def registrar(self, token: str, identidade: IdentidadeFirebase) -> None:
        """Adiciona um token "válido" e a identidade que ele deve devolver."""
        self._identidades[token] = identidade

    async def verificar(self, id_token: str) -> IdentidadeFirebase:
        identidade = self._identidades.get(id_token)
        if identidade is None:
            raise ErroNaoAutorizado(
                "Token inválido ou expirado.", "token_invalido"
            )
        return identidade


# ── Acesso ao verificador padrão (injetável) ────────────────────────────────
# Guardamos uma instância única do verificador real. Em testes, chamamos
# [definir_verificador] para trocar por um fake (sem subir o Firebase).
_verificador_padrao: Optional[VerificadorToken] = None


def obter_verificador() -> VerificadorToken:
    """Devolve o verificador atual (cria o real na 1ª vez)."""
    global _verificador_padrao
    if _verificador_padrao is None:
        _verificador_padrao = VerificadorTokenFirebase()
    return _verificador_padrao


def definir_verificador(verificador: Optional[VerificadorToken]) -> None:
    """Troca o verificador global (usado nos testes; `None` reseta para o real)."""
    global _verificador_padrao
    _verificador_padrao = verificador
