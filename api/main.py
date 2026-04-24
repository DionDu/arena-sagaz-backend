import time

from fastapi import FastAPI, Request

from api.nucleo.excecoes import registrar_handlers
from api.nucleo.log import obter_logger

log = obter_logger("api.main")

app = FastAPI(title="Arena Sagaz API", version="1.0.0")

registrar_handlers(app)


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


# Importações tardias para evitar ciclos ao registrar routers
from api.nucleo import rotas as rotas_nucleo  # noqa: E402
from api.auth import rotas as rotas_auth  # noqa: E402
from api.usuarios import rotas as rotas_usuarios  # noqa: E402
from api.partidas import rotas as rotas_partidas  # noqa: E402
from api.ranking import rotas as rotas_ranking  # noqa: E402

app.include_router(rotas_nucleo.router, prefix="/v1")
app.include_router(rotas_auth.router, prefix="/v1/auth")
app.include_router(rotas_usuarios.router, prefix="/v1/usuarios")
app.include_router(rotas_partidas.router, prefix="/v1/partidas")
app.include_router(rotas_ranking.router, prefix="/v1/ranking")
