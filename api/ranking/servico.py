"""Serviço de ranking e progressão na nuvem (spec 006 / US3 — T044).

Casos de uso:
 • leaderboard: Top-N global geral (público) + a posição do PRÓPRIO jogador
   (sempre presente, mesmo fora do Top-N ou com placar oculto);
 • visibilidade: opt-out do placar público (ic_visivel_placar);
 • perfil: progressão do usuário (nível/patente/XP calculados pela VIEW).

A privacidade (opt-out + menores de 13) é aplicada na VIEW ``vw101`` (coluna
``ic_publico``); aqui só orquestramos. O ``id_usuario`` vem do token.
"""
from __future__ import annotations

from typing import Any, Protocol

from api.nucleo.dependencias_conta_nuvem import UsuarioAutenticado


class RepositorioRankingProtocolo(Protocol):
    async def top_publico(self, limite: int) -> list[dict[str, Any]]: ...
    async def entrada_do_usuario(
        self, id_usuario: str
    ) -> dict[str, Any] | None: ...
    async def definir_visibilidade(
        self, id_usuario: str, visivel: bool
    ) -> None: ...
    async def obter_perfil(self, id_usuario: str) -> dict[str, Any]: ...


class ServicoRanking:
    """Casos de uso de ranking. Recebe o repositório (real ou fake) e a sessão."""

    def __init__(
        self, repo: RepositorioRankingProtocolo, sessao: Any = None
    ) -> None:
        self.repo = repo
        self.sessao = sessao

    async def leaderboard(
        self, usuario: UsuarioAutenticado, limite: int = 100
    ) -> dict[str, Any]:
        """Top-N público + a linha do próprio jogador ('eu'), que é SEMPRE
        retornada ao dono — mesmo se ele optou por ocultar o placar ou está fora
        do Top-N. Assim ele vê a própria posição real (FR-029/SC-010a)."""
        limite = max(1, min(limite, 500))  # trava defensiva
        top = await self.repo.top_publico(limite)
        eu = await self.repo.entrada_do_usuario(usuario.id_usuario)
        return {"top": top, "eu": eu}

    async def definir_visibilidade(
        self, usuario: UsuarioAutenticado, visivel: bool
    ) -> dict[str, Any]:
        """Liga/desliga a aparição no placar PÚBLICO (opt-out — FR-029a)."""
        await self.repo.definir_visibilidade(usuario.id_usuario, visivel)
        return {"ic_visivel_placar": visivel}

    async def perfil(self, usuario: UsuarioAutenticado) -> dict[str, Any]:
        """Progressão do usuário (nível/patente/XP)."""
        return {"progressao": await self.repo.obter_perfil(usuario.id_usuario)}
