from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.banco.conexao import get_sessao
from api.nucleo.seguranca import verificar_token_acesso

_bearer = HTTPBearer()


async def usuario_atual(
    credenciais: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    from api.usuarios.modelo import Usuario

    try:
        payload = verificar_token_acesso(credenciais.credentials)
        usuario_id: str = payload.get("sub")
        if not usuario_id:
            raise ValueError("sub ausente no token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    resultado = await sessao.execute(
        select(Usuario).where(Usuario.id == usuario_id)
    )
    usuario = resultado.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    return usuario
