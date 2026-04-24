from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.banco.conexao import get_sessao
from api.nucleo.dependencias import usuario_atual
from api.partidas.esquemas import PartidaSaida, SincronizarPartidaEntrada
from api.partidas import servico
from api.usuarios.modelo import Usuario

router = APIRouter()


@router.post("", status_code=201, response_model=PartidaSaida)
async def sincronizar_partida(
    dados: SincronizarPartidaEntrada,
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    return await servico.sincronizar_partida(sessao, usuario, dados)
