from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.banco.conexao import get_sessao
from api.ranking.esquemas import RankingSaida
from api.ranking import servico

router = APIRouter()


@router.get("", response_model=RankingSaida)
async def consultar_ranking(
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
    pagina: int = Query(default=1, ge=1),
    tamanho: int = Query(default=20, ge=1, le=100),
):
    return await servico.consultar_ranking(sessao, pagina, tamanho)
