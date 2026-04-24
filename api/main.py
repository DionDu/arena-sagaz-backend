import time

from fastapi import FastAPI, Request

from api.nucleo.excecoes import registrar_handlers
from api.nucleo.log import obter_logger
from api.nucleo import rotas as rotas_nucleo

log = obter_logger("api.main")

app = FastAPI(title="Arena Sagaz API", version="1.0.0")

registrar_handlers(app)
app.include_router(rotas_nucleo.router, prefix="/v1")


@app.middleware("http")
async def middleware_logging(request: Request, call_next):
    inicio = time.perf_counter()
    resposta = await call_next(request)
    duracao_ms = round((time.perf_counter() - inicio) * 1000, 2)
    log.info(
        f"{request.method} {request.url.path} {resposta.status_code}",
        extra={"rota": request.url.path, "duracao_ms": duracao_ms},
    )
    return resposta
