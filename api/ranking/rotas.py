"""Rotas de ranking (spec 006 / US3). Prefixo ``/v1/ranking`` no ``main.py``.

Exigem token + cabeçalhos + conta provisionada (dependência ``usuario_autenticado``).
A escrita de visibilidade confirma a transação na rota.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
    usuario_opcional,
)
from api.ranking.repositorio import RepositorioRanking
from api.ranking.servico import ServicoRanking

router = APIRouter(tags=["ranking"])


def obter_servico_ranking(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoRanking:
    return ServicoRanking(RepositorioRanking(sessao), sessao)


class VisibilidadeRequest(BaseModel):
    """Corpo do PUT de visibilidade: liga/desliga o placar público."""

    ic_visivel_placar: bool


@router.get("/leaderboard")
async def leaderboard(
    limite: int = Query(default=100, ge=1, le=500),
    usuario: UsuarioAutenticado | None = Depends(usuario_opcional),
    servico: ServicoRanking = Depends(obter_servico_ranking),
) -> dict[str, Any]:
    """`GET /v1/ranking/leaderboard` — Top-N público + a minha posição ('eu').

    ⚠️ **Esta rota NÃO exige token** (`usuario_opcional`, e não
    `usuario_autenticado`, como as outras duas daqui). O Top-N é público — quem
    joga como convidado precisa vê-lo, e é o principal motivo para ele criar uma
    conta. Sem conta, `eu` volta `null`. Os cabeçalhos continuam obrigatórios.
    """
    return await servico.leaderboard(usuario, limite=limite)


@router.put("/visibilidade")
async def definir_visibilidade(
    corpo: VisibilidadeRequest,
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    servico: ServicoRanking = Depends(obter_servico_ranking),
) -> dict[str, Any]:
    """`PUT /v1/ranking/visibilidade` — opt-in/opt-out do placar público."""
    resposta = await servico.definir_visibilidade(
        usuario, corpo.ic_visivel_placar
    )
    await servico.sessao.commit()
    return resposta


@router.get("/perfil")
async def perfil(
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    servico: ServicoRanking = Depends(obter_servico_ranking),
) -> dict[str, Any]:
    """`GET /v1/ranking/perfil` — progressão (nível/patente/XP) do usuário."""
    return await servico.perfil(usuario)
