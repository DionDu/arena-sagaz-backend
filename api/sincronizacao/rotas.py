"""Rotas de sincronização (spec 006 / US1). Prefixo ``/v1/sincronizacao`` é
aplicado no ``main.py``.

Todas exigem token válido + cabeçalhos + conta provisionada (dependência
``usuario_autenticado``, que resolve o ``id_usuario`` interno pelo token). A
transação é confirmada na rota (``await servico.sessao.commit()``), deixando a
ingestão atômica — tudo do evento entra junto ou nada entra.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias_conta_nuvem import (
    UsuarioAutenticado,
    usuario_autenticado,
)
from api.sincronizacao.repositorio import RepositorioSincronizacao
from api.sincronizacao.servico import ServicoSincronizacao

router = APIRouter(tags=["sincronizacao"])


def obter_servico_sync(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoSincronizacao:
    """Monta o serviço com o repositório real e a sessão da requisição.
    Nos testes, é substituído (`dependency_overrides`) por um serviço com
    repositório/sessão falsos."""
    return ServicoSincronizacao(RepositorioSincronizacao(sessao), sessao)


@router.post("/eventos")
async def ingerir_eventos(
    corpo: dict[str, Any],
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    servico: ServicoSincronizacao = Depends(obter_servico_sync),
) -> dict[str, Any]:
    """`POST /v1/sincronizacao/eventos` — ingere um lote de eventos da outbox."""
    resposta = await servico.ingerir_eventos(usuario, corpo)
    await servico.sessao.commit()
    return resposta


@router.post("/merge-convidado")
async def merge_convidado(
    corpo: dict[str, Any],
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    servico: ServicoSincronizacao = Depends(obter_servico_sync),
) -> dict[str, Any]:
    """`POST /v1/sincronizacao/merge-convidado` — funde convidado→conta."""
    resposta = await servico.merge_convidado(usuario, corpo)
    await servico.sessao.commit()
    return resposta


@router.get("/estado")
async def estado(
    usuario: UsuarioAutenticado = Depends(usuario_autenticado),
    servico: ServicoSincronizacao = Depends(obter_servico_sync),
) -> dict[str, Any]:
    """`GET /v1/sincronizacao/estado` — progressão atual do usuário."""
    return await servico.estado(usuario)
