from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.banco.conexao import get_sessao
from api.nucleo.dependencias import usuario_atual
from api.auth.esquemas import (
    LoginEntrada,
    LogoutEntrada,
    RefreshEntrada,
    TokenAcessoSaida,
    TokenSaida,
)
from api.auth import servico
from api.usuarios.modelo import Usuario

router = APIRouter()


@router.post("/login", response_model=TokenSaida)
async def login(
    dados: LoginEntrada,
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    return await servico.autenticar(sessao, dados.email, dados.senha)


@router.post("/refresh", response_model=TokenAcessoSaida)
async def refresh(
    dados: RefreshEntrada,
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    return await servico.renovar_token(sessao, dados.refresh_token)


@router.post("/logout")
async def logout(
    dados: LogoutEntrada,
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    await servico.revogar_token(sessao, dados.refresh_token)
    return {"mensagem": "Sessão encerrada com sucesso."}
