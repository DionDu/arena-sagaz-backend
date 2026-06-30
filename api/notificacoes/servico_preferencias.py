"""Serviço de **dispositivos e preferências** de notificação.

Faz a ponte entre as rotas e o [RepositorioNotificacao], resolvendo o
`id_usuario` interno a partir da identidade do Firebase e orquestrando a
transação (dá `commit` ao final de cada escrita).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.notificacoes.modelos import PreferenciaItem
from api.notificacoes.repositorio import RepositorioNotificacao
from api.nucleo.excecoes import ErroNaoEncontrado


class ServicoPreferenciasNotificacao:
    """Regra de negócio de tokens FCM e preferências por categoria."""

    def __init__(self, repo: RepositorioNotificacao, sessao: AsyncSession) -> None:
        self.repo = repo
        self.sessao = sessao

    async def registrar_dispositivo(
        self,
        uid: Optional[str],
        co_token_fcm: str,
        sg_plataforma: str,
        co_idioma: str,
    ) -> None:
        """Registra/atualiza o token FCM. O dono (`id_usuario`) é resolvido do
        `uid` do Firebase quando há login; em sessão de convidado fica nulo."""
        id_usuario = (
            await self.repo.id_usuario_por_identidade(uid) if uid else None
        )
        await self.repo.upsert_dispositivo(
            id_usuario, co_token_fcm, sg_plataforma, co_idioma
        )
        await self.sessao.commit()

    async def remover_dispositivo(self, co_token_fcm: str) -> None:
        """Remove o token (logout/expiração). Idempotente (não erra se não havia)."""
        await self.repo.remover_dispositivo(co_token_fcm)
        await self.sessao.commit()

    async def definir_preferencias(
        self, uid: str, preferencias: list[PreferenciaItem]
    ) -> list[PreferenciaItem]:
        """Grava as preferências por categoria e devolve o estado atual."""
        id_usuario = await self._exigir_id_usuario(uid)
        for p in preferencias:
            if p.co_categoria == "marketing":
                # Marketing = consentimento LGPD: grava na tb004 (fonte única).
                # A vw006 lê o marketing de lá, então o app continua coerente.
                await self.repo.upsert_marketing_consentimento(id_usuario, p.ic_ativo)
            else:
                await self.repo.upsert_preferencia(
                    id_usuario, p.co_categoria, p.ic_ativo
                )
        await self.sessao.commit()
        return await self._ler(id_usuario)

    async def listar_preferencias(self, uid: str) -> list[PreferenciaItem]:
        """Devolve as preferências atuais do usuário."""
        id_usuario = await self._exigir_id_usuario(uid)
        return await self._ler(id_usuario)

    # ── auxiliares ──────────────────────────────────────────────────────────

    async def _exigir_id_usuario(self, uid: str):
        """Resolve o `id_usuario` ou lança 404 (conta ainda não existe na base)."""
        id_usuario = await self.repo.id_usuario_por_identidade(uid)
        if id_usuario is None:
            raise ErroNaoEncontrado(
                "Conta não encontrada.", "usuario_nao_encontrado"
            )
        return id_usuario

    async def _ler(self, id_usuario) -> list[PreferenciaItem]:
        linhas = await self.repo.listar_preferencias(id_usuario)
        return [
            PreferenciaItem(co_categoria=l["co_categoria"], ic_ativo=l["ic_ativo"])
            for l in linhas
        ]
