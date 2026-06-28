import time

from fastapi import FastAPI, Request

from api.conta import rotas as rotas_conta
from api.legal import rotas as rotas_legal
from api.nucleo.excecoes import registrar_handlers
from api.nucleo.log import obter_logger
from api.nucleo import rotas as rotas_nucleo

log = obter_logger("api.main")

app = FastAPI(title="Arena Sagaz API", version="1.0.0")

registrar_handlers(app)
app.include_router(rotas_nucleo.router, prefix="/v1")
# Rotas de conta (login/cadastro/perfil) sob /v1/conta (US2).
app.include_router(rotas_conta.router, prefix="/v1/conta")
# Documentos legais como páginas HTML públicas (G3) — fora de /v1, é conteúdo web
# (URLs de privacidade/exclusão exigidas pelas lojas).
app.include_router(rotas_legal.router, prefix="/legal")


@app.middleware("http")
async def middleware_logging(request: Request, call_next):
    """Registra cada requisição com contexto de diagnóstico — **sem PII** (T013).

    A obrigatoriedade dos cabeçalhos (`X-App-Version`/`X-Platform`) é validada
    **por rota** (dependência `exigir_cabecalhos`, T012), não aqui — assim rotas
    públicas como `/health` não exigem cabeçalho de app. Este middleware só
    **observa** e loga.

    Logamos apenas dados seguros: método, rota, status, duração, plataforma e
    versão do app. NUNCA o `Authorization` (token), e-mail ou qualquer dado
    pessoal (Constituição, Princípio IV).
    """
    inicio = time.perf_counter()
    resposta = await call_next(request)
    duracao_ms = round((time.perf_counter() - inicio) * 1000, 2)
    log.info(
        f"{request.method} {request.url.path} {resposta.status_code}",
        extra={
            "rota": request.url.path,
            "duracao_ms": duracao_ms,
            # `.get` devolve None se o cabeçalho não veio — o handler de log
            # ignora campos None (não polui o JSON).
            "plataforma": request.headers.get("x-platform"),
            "versao_app": request.headers.get("x-app-version"),
        },
    )
    return resposta
