"""Repositório de sincronização FALSO (em memória) para os testes de contrato.

Simula a idempotência (por ``co_evento`` e por ``co_lote_migracao``) e o efeito
no XP/contadores, sem tocar em banco. Não tem prefixo ``test_`` de propósito.
"""
from __future__ import annotations

from typing import Any


def _zerado() -> dict[str, Any]:
    return {
        "nu_xp_total": 0,
        "nu_partidas": 0,
        "nu_vitorias": 0,
        "nu_derrotas": 0,
        "nu_empates": 0,
        "nu_sequencia_atual": 0,
        "conquistas": set(),
    }


class FakeRepoSincronizacao:
    """Espelha, em memória, o comportamento que o repositório real garante."""

    def __init__(self) -> None:
        self.eventos_vistos: set[str] = set()
        self.lotes_aplicados: set[str] = set()
        self._progressao: dict[str, dict[str, Any]] = {}

    async def gravar_evento(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_evento: str,
        payload: dict[str, Any],
    ) -> bool:
        if co_evento in self.eventos_vistos:
            return False  # idempotência: retry não aplica de novo
        self.eventos_vistos.add(co_evento)

        prog = self._progressao.setdefault(id_usuario, _zerado())
        partida = payload.get("partida") or {}
        if partida.get("ic_pontua"):
            xp = sum(int(x.get("nu_xp", 0)) for x in payload.get("xp", []))
            j1 = int(partida.get("nu_placar_j1", 0))
            j2 = int(partida.get("nu_placar_j2", 0))
            prog["nu_xp_total"] += xp
            prog["nu_partidas"] += 1
            prog["nu_vitorias"] += 1 if j1 > j2 else 0
            prog["nu_derrotas"] += 1 if j1 < j2 else 0
            prog["nu_empates"] += 1 if j1 == j2 else 0
        return True

    async def aplicar_merge_se_novo(
        self,
        *,
        id_usuario: str,
        co_anonimo: str | None,
        co_lote_migracao: str,
        progressao_convidado: dict[str, Any],
    ) -> bool:
        if co_lote_migracao in self.lotes_aplicados:
            return False  # idempotência por lote
        self.lotes_aplicados.add(co_lote_migracao)

        prog = self._progressao.setdefault(id_usuario, _zerado())
        r = progressao_convidado
        prog["nu_xp_total"] += int(r.get("nu_xp_total", 0))
        prog["nu_partidas"] += int(r.get("nu_partidas", 0))
        prog["nu_vitorias"] += int(r.get("nu_vitorias", 0))
        prog["nu_derrotas"] += int(r.get("nu_derrotas", 0))
        prog["nu_empates"] += int(r.get("nu_empates", 0))
        prog["nu_sequencia_atual"] = max(
            prog["nu_sequencia_atual"], int(r.get("nu_sequencia_atual", 0))
        )
        prog["conquistas"].update(r.get("conquistas", []) or [])
        return True

    async def obter_progressao(self, id_usuario: str) -> dict[str, Any]:
        prog = self._progressao.get(id_usuario, _zerado())
        saida = dict(prog)
        # Devolve conquistas como lista ordenada (JSON não tem set).
        saida["conquistas"] = sorted(prog["conquistas"])
        return saida
