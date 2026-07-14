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
from api.ranking.cache import cache_eu, cache_top, limpar_tudo

# Marcador de "consultei e não achou" — ver o comentário em `leaderboard`.
_AUSENTE = object()


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
        self, usuario: UsuarioAutenticado | None, limite: int = 100
    ) -> dict[str, Any]:
        """Top-N público + a linha do próprio jogador ('eu').

        O Top-N é **público**: quem joga como convidado (``usuario is None``) o
        recebe igual. O que ele não tem é a linha "eu" — vem ``None``, e a tela
        troca a barra "VOCÊ" por um convite a criar conta.

        Para quem tem conta, "eu" vem SEMPRE — mesmo se optou por ocultar o placar
        ou está fora do Top-N. Assim ele vê a própria posição real (FR-029/SC-010a).

        As duas partes passam por um cache de 30 s (ver ``cache.py``): a consulta
        do ranking varre e ordena a tabela inteira e **não é indexável**, então o
        que nos protege de um pico de acessos é não repeti-la.
        """
        limite = max(1, min(limite, 500))  # trava defensiva

        top = cache_top.obter(limite)
        if top is None:
            top = await self.repo.top_publico(limite)
            cache_top.guardar(limite, top)

        if usuario is None:
            return {"top": top, "eu": None}

        # `_AUSENTE`: um `None` guardado no cache significa "consultei e este
        # usuário não tem linha" — que é diferente de "ainda não consultei".
        # Sem essa distinção, quem ainda não pontuou refaria a consulta cara a
        # cada abertura da tela, justamente o caso mais comum de quem chegou agora.
        eu = cache_eu.obter(usuario.id_usuario)
        if eu is None:
            eu = await self.repo.entrada_do_usuario(usuario.id_usuario)
            cache_eu.guardar(usuario.id_usuario, eu if eu is not None else _AUSENTE)
        return {"top": top, "eu": None if eu is _AUSENTE else eu}

    async def definir_visibilidade(
        self, usuario: UsuarioAutenticado, visivel: bool
    ) -> dict[str, Any]:
        """Liga/desliga a aparição no placar PÚBLICO (opt-out — FR-029a)."""
        await self.repo.definir_visibilidade(usuario.id_usuario, visivel)
        # INVALIDA o cache. Esta é a única escrita que muda o ranking na hora, e é
        # feita pelo próprio usuário olhando para a tela: ele espera ver o efeito
        # imediatamente, não daqui a 30 s. O Top-N inteiro cai junto, porque
        # entrar ou sair do placar reposiciona todo mundo abaixo de mim.
        limpar_tudo()
        return {"ic_visivel_placar": visivel}

    async def perfil(self, usuario: UsuarioAutenticado) -> dict[str, Any]:
        """Progressão do usuário (nível/patente/XP)."""
        return {"progressao": await self.repo.obter_perfil(usuario.id_usuario)}
