"""Repositório de ranking (spec 006 / US3 — T044).

Leitura pelas VIEWs ``progressao.vw101_ranking_global_geral`` (leaderboard, com a
coluna ``ic_publico`` que já aplica opt-out + idade <13) e
``progressao.vw001_progressao_usuario`` (perfil, com nível/patente). Escrita da
visibilidade na tabela ``progressao.tb001_progressao_usuario``.

⚠️ TESTES DE INTEGRAÇÃO PENDENTES (precisa da migração 0003 aplicada). Os testes
de contrato (T041) usam repositório FALSO.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class RepositorioRanking:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def top_publico(self, limite: int) -> list[dict[str, Any]]:
        """Top-N PÚBLICO: só quem pode aparecer (ic_publico), por posição. O
        desempate de exibição segue o XP e (na VIEW) a antiguidade."""
        resultado = await self.sessao.execute(
            text(
                """
                SELECT co_usuario, no_exibicao, nu_xp_total, nu_posicao
                FROM progressao.vw101_ranking_global_geral
                WHERE ic_publico = TRUE
                ORDER BY nu_posicao, nu_xp_total DESC
                LIMIT :limite
                """
            ),
            {"limite": limite},
        )
        return [dict(l) for l in resultado.mappings().all()]

    async def entrada_do_usuario(
        self, id_usuario: str
    ) -> dict[str, Any] | None:
        """A linha do próprio jogador no ranking (posição real), mesmo se
        oculto. `None` se ele ainda não pontuou (não está na VIEW)."""
        resultado = await self.sessao.execute(
            text(
                """
                SELECT co_usuario, no_exibicao, nu_xp_total, nu_posicao,
                       ic_publico
                FROM progressao.vw101_ranking_global_geral
                WHERE id_usuario = :id
                """
            ),
            {"id": id_usuario},
        )
        linha = resultado.mappings().first()
        return dict(linha) if linha else None

    async def definir_visibilidade(
        self, id_usuario: str, visivel: bool
    ) -> None:
        await self.sessao.execute(
            text(
                """
                UPDATE progressao.tb001_progressao_usuario
                SET ic_visivel_placar = :v, dh_atualizacao = now()
                WHERE id_usuario = :id
                """
            ),
            {"v": visivel, "id": id_usuario},
        )

    async def obter_perfil(self, id_usuario: str) -> dict[str, Any]:
        resultado = await self.sessao.execute(
            text(
                "SELECT * FROM progressao.vw001_progressao_usuario "
                "WHERE id_usuario = :id"
            ),
            {"id": id_usuario},
        )
        linha = resultado.mappings().first()
        if linha is None:
            return {"nu_xp_total": 0, "nu_nivel": 1, "co_patente": "aprendiz"}
        return dict(linha)
