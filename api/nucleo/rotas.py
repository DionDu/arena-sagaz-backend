from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.banco.conexao import engine

router = APIRouter()

_VERSAO = "1.0.0"


@router.get("/health")
async def health_check():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "banco_de_dados": "ok", "versao": _VERSAO}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degradado", "banco_de_dados": "indisponivel", "versao": _VERSAO},
        )
