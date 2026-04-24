from fastapi import APIRouter

router = APIRouter()

_VERSAO = "1.0.0"


@router.get("/health")
async def health_check():
    return {"status": "ok", "versao": _VERSAO}
