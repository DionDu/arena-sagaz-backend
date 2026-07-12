"""Fakes de conta para testes (repositório e sessão em memória) — sem banco.

Não tem prefixo `test_` de propósito: é um módulo de apoio, o pytest não o coleta
como arquivo de testes.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
        self.aceites: list[dict[str, Any]] = []
        self.consentimento: Optional[dict[str, Any]] = None

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
        atuais = self._provedores.setdefault(id_usuario, [])
        # ⚠️ A unicidade da tabela real é o PAR (co_provedor, co_identidade_provedor)
        # — é o `ON CONFLICT` dela. Deduplicar só por `co_provedor` aqui ESCONDERIA
        # o bug da linha `email` duplicada (medido em 2026-07-12), que é exatamente
        # o que este fake precisa ser capaz de reproduzir.
        par = (co_provedor, co_identidade_provedor)
        if not any(
            (p["co_provedor"], p["co_identidade_provedor"]) == par for p in atuais
        ):
            atuais.append(
                {
                    "co_provedor": co_provedor,
                    "co_identidade_provedor": co_identidade_provedor,
                }
            )
        return {}

    async def reconciliar_provedores(self, id_usuario, provedores):
        """Substitui o conjunto — apaga quem o Firebase não lista mais.

        Espelha o repositório real: compara o PAR completo, não só o código do
        provedor."""
        atuais_esperados = {(p, i) for p, i in provedores}
        linhas = self._provedores.setdefault(id_usuario, [])
        linhas[:] = [
            p
            for p in linhas
            if (p["co_provedor"], p["co_identidade_provedor"]) in atuais_esperados
        ]
        for co_provedor, co_identidade in provedores:
            await self.vincular_provedor(
                id_usuario=id_usuario,
                co_provedor=co_provedor,
                co_identidade_provedor=co_identidade,
            )

    async def definir_provedor_principal(self, id_usuario, co_provedor):
        for linha in self._por_uid.values():
            if linha["id_usuario"] == id_usuario:
                linha["co_provedor_principal"] = co_provedor

    async def listar_provedores(self, id_usuario):
        return list(self._provedores.get(id_usuario, []))

    async def registrar_aceite_legal(
        self, *, id_usuario, co_documento, co_versao, co_idioma
    ):
        linha = {
            "id_aceite_legal": f"ac-{len(self.aceites) + 1}",
            "id_usuario": id_usuario,
            "co_documento": co_documento,
            "co_versao": co_versao,
            "co_idioma": co_idioma,
            "dh_aceite": datetime(2026, 6, 28, tzinfo=timezone.utc),
        }
        self.aceites.append(linha)
        return linha

    async def definir_consentimento(
        self, *, id_usuario, ic_rastreamento, ic_marketing
    ):
        self.consentimento = {
            "id_consentimento": "co-1",
            "id_usuario": id_usuario,
            "ic_rastreamento": ic_rastreamento,
            "ic_marketing": ic_marketing,
            "dh_atualizacao": datetime(2026, 6, 28, tzinfo=timezone.utc),
        }
        return self.consentimento

    async def anonimizar_usuario(self, id_usuario):
        for linha in self._por_uid.values():
            if linha["id_usuario"] == id_usuario:
                linha["no_exibicao"] = None
                linha["no_email"] = None
                linha["dt_nascimento"] = None
                linha["co_identidade_externa"] = None
                linha["ic_anonimizado"] = True
                return dict(linha)
        return None

    async def remover_dados_vinculados(self, id_usuario):
        # Registra a chamada e zera os provedores (espelha o DELETE real).
        self.dados_removidos = id_usuario
        self._provedores.pop(id_usuario, None)


class _SavepointFake:
    """Contexto assíncrono que imita um SAVEPOINT (``session.begin_nested()``):
    não faz nada no banco; se o bloco lançar, deixa a exceção propagar (retorna
    ``False`` no ``__aexit__``), como o savepoint real (que reverte e re-levanta)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Sessão falsa: só conta commits/rollbacks/savepoints (não toca banco)."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.savepoints = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    def begin_nested(self):
        """Imita o SAVEPOINT por evento. Não é ``async`` (o SQLAlchemy real
        devolve um gerenciador de contexto para ``async with``, não um awaitable)."""
        self.savepoints += 1
        return _SavepointFake()
