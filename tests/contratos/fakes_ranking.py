"""Repositório de ranking FALSO (em memória) para os testes de contrato.

Reproduz o comportamento que a VIEW ``vw101`` garante: DENSE_RANK por XP (só quem
pontuou), e a coluna ``ic_publico`` = visível E idade ≥ 13.
"""
from __future__ import annotations

from typing import Any


class FakeRepoRanking:
    def __init__(self, usuarios: list[dict[str, Any]]) -> None:
        # Cada usuário: id_usuario, co_usuario, no_exibicao, nu_xp_total,
        # ic_visivel_placar, idade.
        self.usuarios = usuarios
        self.visibilidade_alterada: dict[str, bool] = {}
        # Contadores de acesso — é assim que o teste do CACHE prova que a consulta
        # cara não foi refeita. Sem eles não haveria como distinguir "respondeu do
        # cache" de "consultou de novo e deu o mesmo resultado".
        self.chamadas_top = 0
        self.chamadas_eu = 0

    def _posicoes(self) -> dict[str, int]:
        """DENSE_RANK por XP desc, só para quem tem XP > 0."""
        com_xp = sorted(
            (u for u in self.usuarios if u["nu_xp_total"] > 0),
            key=lambda u: -u["nu_xp_total"],
        )
        pos: dict[str, int] = {}
        rank = 0
        ultimo_xp = None
        for u in com_xp:
            if u["nu_xp_total"] != ultimo_xp:
                rank += 1
                ultimo_xp = u["nu_xp_total"]
            pos[u["id_usuario"]] = rank
        return pos

    @staticmethod
    def _publico(u: dict[str, Any]) -> bool:
        return u.get("ic_visivel_placar", True) and u.get("idade", 99) >= 13

    def _linha(self, u: dict[str, Any], pos: dict[str, int]) -> dict[str, Any]:
        return {
            "co_usuario": u["co_usuario"],
            "no_exibicao": u["no_exibicao"],
            "nu_xp_total": u["nu_xp_total"],
            "nu_posicao": pos[u["id_usuario"]],
        }

    async def top_publico(self, limite: int) -> list[dict[str, Any]]:
        self.chamadas_top += 1
        pos = self._posicoes()
        pubs = [
            u for u in self.usuarios
            if u["id_usuario"] in pos and self._publico(u)
        ]
        pubs.sort(key=lambda u: (pos[u["id_usuario"]], -u["nu_xp_total"]))
        return [self._linha(u, pos) for u in pubs[:limite]]

    async def entrada_do_usuario(self, id_usuario: str):
        self.chamadas_eu += 1
        pos = self._posicoes()
        for u in self.usuarios:
            if u["id_usuario"] == id_usuario:
                if id_usuario not in pos:
                    return None
                linha = self._linha(u, pos)
                linha["ic_publico"] = self._publico(u)
                return linha
        return None

    async def definir_visibilidade(self, id_usuario: str, visivel: bool) -> None:
        self.visibilidade_alterada[id_usuario] = visivel
        for u in self.usuarios:
            if u["id_usuario"] == id_usuario:
                u["ic_visivel_placar"] = visivel

    async def obter_perfil(self, id_usuario: str) -> dict[str, Any]:
        for u in self.usuarios:
            if u["id_usuario"] == id_usuario:
                return {
                    "nu_xp_total": u["nu_xp_total"],
                    "nu_nivel": 1,
                    "co_patente": "aprendiz",
                }
        return {"nu_xp_total": 0, "nu_nivel": 1, "co_patente": "aprendiz"}
