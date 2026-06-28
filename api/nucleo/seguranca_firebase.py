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

import base64
import binascii
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from api.configuracao import configuracoes
from api.nucleo.excecoes import ErroNaoAutorizado
from api.nucleo.log import obter_logger

log = obter_logger("api.seguranca")


def _tentar_json(texto: str) -> Optional[dict[str, Any]]:
    """Tenta ler `texto` como um **objeto** JSON; devolve o dict ou `None`."""
    if not texto:
        return None
    try:
        valor = json.loads(texto)
    except json.JSONDecodeError:
        return None
    # Só aceitamos um objeto (a chave Admin é um `{...}`), não lista/número.
    return valor if isinstance(valor, dict) else None


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
        """Inicializa (uma vez) o app Firebase a partir das configurações.

        Delega para [garantir_app_firebase] (função de módulo, compartilhada com
        as operações administrativas), guardando o resultado em cache local.
        """
        if self._app is None:
            self._app = garantir_app_firebase()
        return self._app

    @staticmethod
    def _carregar_credencial(bruto: str):
        """Cria a credencial do Firebase aceitando TRÊS formatos de
        `FIREBASE_CREDENTIALS`, do mais comum ao menos:

        1. **JSON** (o conteúdo do arquivo de chave) — uso típico no Railway;
        2. **base64** de um JSON — evita problemas de quebra de linha ao colar;
        3. **caminho** de um arquivo `.json` no disco — conveniente localmente.

        Se nenhum funcionar, lança um **401 claro** (`firebase_credencial_invalida`)
        em vez de explodir com 500 e um traceback de `json.loads`.
        """
        from firebase_admin import credentials

        # (3) É um caminho de arquivo existente?
        if os.path.exists(bruto):
            return credentials.Certificate(bruto)

        # (1) É o JSON direto?
        dados = _tentar_json(bruto)
        if dados is not None:
            return credentials.Certificate(dados)

        # (2) É base64 de um JSON?
        try:
            decodificado = base64.b64decode(bruto, validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            decodificado = ""
        dados = _tentar_json(decodificado)
        if dados is not None:
            return credentials.Certificate(dados)

        # Nada funcionou: configuração inválida (sem vazar o conteúdo no log).
        log.info("FIREBASE_CREDENTIALS não é JSON, base64 de JSON nem caminho válido")
        raise ErroNaoAutorizado(
            "Credencial do Firebase mal configurada no servidor.",
            "firebase_credencial_invalida",
        )

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


def garantir_app_firebase():
    """Inicializa (ou reusa) o app do Firebase Admin SDK a partir das
    configurações. É **idempotente**: o `firebase_admin` registra apps por nome,
    então chamar várias vezes devolve sempre o mesmo app.

    Compartilhada pela verificação de token e pelas operações administrativas
    (ex.: excluir usuário na exclusão de conta — US4).
    """
    # Import local: só carrega a lib pesada quando realmente formos usá-la.
    import firebase_admin

    bruto = (configuracoes.FIREBASE_CREDENTIALS or "").strip()
    if not bruto:
        # Sem credencial não há como operar — erro de configuração, não do
        # usuário; mas respondemos 401 para não vazar detalhe de infra.
        raise ErroNaoAutorizado(
            "Verificação de identidade indisponível.",
            "firebase_nao_configurado",
        )

    cred = VerificadorTokenFirebase._carregar_credencial(bruto)

    nome_app = "arena-sagaz"
    try:
        # Se já existe um app com esse nome (recarga/teste), reusa.
        return firebase_admin.get_app(nome_app)
    except ValueError:
        return firebase_admin.initialize_app(cred, name=nome_app)


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


# ── Operações administrativas sobre usuários do Firebase (US4) ───────────────
# Usadas na **exclusão de conta**: além de anonimizar nossa base, apagamos a
# identidade no provedor (Firebase) com o Admin SDK — que NÃO exige
# reautenticação recente (diferente do `user.delete()` no cliente).


class AdminUsuariosFirebase(Protocol):
    """Contrato de administração de usuários do Firebase. `Protocol` = qualquer
    objeto com este método assíncrono serve (real ou fake)."""

    async def excluir_usuario(self, uid: str) -> None: ...


class AdminUsuariosFirebaseReal:
    """Implementação real: apaga o usuário via Firebase Admin SDK."""

    async def excluir_usuario(self, uid: str) -> None:
        from anyio import to_thread
        from firebase_admin import auth

        app = garantir_app_firebase()
        try:
            # `delete_user` é síncrona e faz I/O — roda em thread para não travar
            # o event loop. Apagar um uid já inexistente é tratado como sucesso
            # (idempotência: o objetivo "esse usuário não existe mais" já vale).
            await to_thread.run_sync(lambda: auth.delete_user(uid, app=app))
        except auth.UserNotFoundError:
            log.info("Usuário do Firebase já não existia ao excluir")


class AdminUsuariosFake:
    """Implementação falsa para testes: só registra os uids excluídos."""

    def __init__(self) -> None:
        self.excluidos: list[str] = []
        # Se `falhar` for True, simula erro do provedor (para testar best-effort).
        self.falhar = False

    async def excluir_usuario(self, uid: str) -> None:
        if self.falhar:
            raise RuntimeError("falha simulada ao excluir no Firebase")
        self.excluidos.append(uid)


_admin_usuarios_padrao: Optional[AdminUsuariosFirebase] = None


def obter_admin_usuarios() -> AdminUsuariosFirebase:
    """Devolve o administrador de usuários atual (cria o real na 1ª vez)."""
    global _admin_usuarios_padrao
    if _admin_usuarios_padrao is None:
        _admin_usuarios_padrao = AdminUsuariosFirebaseReal()
    return _admin_usuarios_padrao


def definir_admin_usuarios(admin: Optional[AdminUsuariosFirebase]) -> None:
    """Troca o administrador global (usado nos testes; `None` reseta para o real)."""
    global _admin_usuarios_padrao
    _admin_usuarios_padrao = admin
