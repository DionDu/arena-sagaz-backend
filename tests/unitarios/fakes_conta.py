"""Fakes de conta para testes (repositório e sessão em memória) — sem banco.

Não tem prefixo `test_` de propósito: é um módulo de apoio, o pytest não o coleta
como arquivo de testes.
"""
from __future__ import annotations

from typing import Any, Optional


class FakeRepoUsuario:
    """Repositório falso: guarda contas num dict em memória (chave = uid)."""

    def __init__(self, existente: Optional[dict[str, Any]] = None) -> None:
        self._por_uid: dict[str, dict[str, Any]] = {}
        self._provedores: dict[str, list[dict[str, Any]]] = {}
        if existente is not None:
            self._por_uid[existente["co_identidade_externa"]] = existente
        # Histórico para asserts.
        self.criadas: list[dict[str, Any]] = []

    async def buscar_por_identidade_externa(self, uid: str):
        return self._por_uid.get(uid)

    async def buscar_por_email(self, no_email: str):
        for linha in self._por_uid.values():
            if linha.get("no_email") == no_email:
                return linha
        return None

    async def buscar_por_codigo(self, co_usuario: str):
        for linha in self._por_uid.values():
            if linha.get("co_usuario") == co_usuario:
                return linha
        return None

    async def atualizar_perfil(
        self, *, id_usuario, no_exibicao=None, dt_nascimento=None,
        co_idioma_preferido=None,
    ):
        for linha in self._por_uid.values():
            if linha["id_usuario"] == id_usuario:
                if no_exibicao is not None:
                    linha["no_exibicao"] = no_exibicao
                if dt_nascimento is not None:
                    linha["dt_nascimento"] = dt_nascimento
                if co_idioma_preferido is not None:
                    linha["co_idioma_preferido"] = co_idioma_preferido
                return dict(linha)
        return None

    async def registrar_ultimo_acesso(self, id_usuario):  # noqa: D401
        return None

    async def criar(
        self, *, co_usuario, co_identidade_externa, co_provedor_principal,
        co_idioma_preferido="pt", no_exibicao=None, no_email=None,
        dt_nascimento=None, ic_convidado=False,
    ):
        linha = {
            "id_usuario": f"id-{co_identidade_externa}",
            "co_usuario": co_usuario,
            "co_identidade_externa": co_identidade_externa,
            "no_exibicao": no_exibicao,
            "no_email": no_email,
            "dt_nascimento": dt_nascimento,
            "co_provedor_principal": co_provedor_principal,
            "co_idioma_preferido": co_idioma_preferido,
            "ic_convidado": ic_convidado,
        }
        self._por_uid[co_identidade_externa] = linha
        self.criadas.append(linha)
        return dict(linha)

    async def vincular_provedor(self, *, id_usuario, co_provedor, co_identidade_provedor):
        self._provedores.setdefault(id_usuario, []).append(
            {"co_provedor": co_provedor}
        )
        return {}

    async def listar_provedores(self, id_usuario):
        return list(self._provedores.get(id_usuario, []))


class FakeSession:
    """Sessão falsa: só conta commits/rollbacks (não toca banco)."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1
