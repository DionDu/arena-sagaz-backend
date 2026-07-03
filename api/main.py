import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.configuracao import configuracoes
from api.conta import rotas as rotas_conta
from api.legal import rotas as rotas_legal
from api.notificacoes import rotas as rotas_notif
from api.nucleo.excecoes import registrar_handlers
from api.nucleo.log import obter_logger
from api.nucleo import rotas as rotas_nucleo
from api.ranking import rotas as rotas_ranking
from api.sincronizacao import rotas as rotas_sync

log = obter_logger("api.main")

app = FastAPI(title="Arena Sagaz API", version="1.0.0")

# ── CORS ─────────────────────────────────────────────────────────────────────
# O app **mobile** (Android/iOS) usa HTTP nativo e NÃO sofre CORS. Mas durante o
# desenvolvimento rodamos o Flutter **Web no Chrome** (origem `localhost:<porta>`,
# porta aleatória a cada `flutter run`) chamando a API em outro domínio — aí o
# navegador exige CORS, inclusive o *preflight* `OPTIONS` para métodos como PATCH
# e DELETE. Sem isto, editar perfil/excluir conta no Chrome falha com 405.
#
# Liberamos: qualquer `localhost`/`127.0.0.1` (qualquer porta, dev) por regex, os
# domínios da marca, e o que vier em `CORS_ORIGINS`. Como a autenticação é por
# **Bearer token** (cabeçalho), e não cookie, não precisamos de `allow_credentials`
# — então não há risco de uma página maliciosa reusar sessão do usuário.
_origens_extras = [
    o.strip() for o in configuracoes.CORS_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://arenasagaz.santiagodata.com",
        "https://api-dev.arenasagaz.santiagodata.com",
        "https://api.arenasagaz.santiagodata.com",
        *_origens_extras,
    ],
    # Qualquer localhost/127.0.0.1 com qualquer porta (Flutter Web em dev).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],  # inclui OPTIONS, PATCH, DELETE
    allow_headers=["*"],  # inclui Authorization, X-App-Version, X-Platform, ...
    allow_credentials=False,
)

registrar_handlers(app)
app.include_router(rotas_nucleo.router, prefix="/v1")
# Rotas de conta (login/cadastro/perfil) sob /v1/conta (US2).
app.include_router(rotas_conta.router, prefix="/v1/conta")
# Notificações: broadcast administrativo para todos os usuários (tópico FCM).
app.include_router(rotas_notif.router, prefix="/v1/notificacoes")
# Sincronização offline↔servidor: eventos da outbox, merge convidado→conta (006).
app.include_router(rotas_sync.router, prefix="/v1/sincronizacao")
# Ranking + progressão na nuvem: leaderboard, visibilidade (opt-out), perfil (006).
app.include_router(rotas_ranking.router, prefix="/v1/ranking")
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
