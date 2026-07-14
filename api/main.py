import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.configuracao import configuracoes
from api.conta import rotas as rotas_conta
from api.legal import rotas as rotas_legal
from api.notificacoes import rotas as rotas_notif
from api.nucleo.excecoes import registrar_handlers
from api.nucleo.log import obter_logger
from api.nucleo.middleware_gzip import GzipRequestMiddleware
from api.nucleo.rate_limit import RateLimitMiddleware
from api.nucleo import rotas as rotas_nucleo
from api.ranking import rotas as rotas_ranking
from api.sincronizacao import rotas as rotas_sync
from api.site import rotas as rotas_site

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
# Liberar qualquer `localhost`/`127.0.0.1` (porta aleatória do Flutter Web) só faz
# sentido em DEV. Em produção não há front web em localhost, então NÃO abrimos essa
# superfície (SEG-02). `None` desativa o regex no CORSMiddleware.
_regex_localhost = (
    None
    if configuracoes.eh_producao
    else r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://arenasagaz.santiagodata.com",
        "https://api-dev.arenasagaz.santiagodata.com",
        "https://api.arenasagaz.santiagodata.com",
        *_origens_extras,
    ],
    allow_origin_regex=_regex_localhost,
    allow_methods=["*"],  # inclui OPTIONS, PATCH, DELETE
    allow_headers=["*"],  # inclui Authorization, X-App-Version, X-Platform, ...
    allow_credentials=False,
)

# Descomprime o corpo das requisições com `Content-Encoding: gzip` (o app envia o
# lote de sincronização comprimido — spec 006/US1). Sem isto, o servidor recebe
# bytes gzip crus e falha ao ler o JSON, e o evento fica "pendente" para sempre no
# app. Adicionado DEPOIS do CORS para rodar POR DENTRO dele (o preflight OPTIONS,
# sem corpo/gzip, passa intacto).
app.add_middleware(GzipRequestMiddleware)

# Rate limiting por IP (SEG-04). Adicionado por ÚLTIMO → é a camada mais externa
# (roda ANTES das outras): barra o excesso cedo, sem gastar trabalho de gzip/rota.
app.add_middleware(RateLimitMiddleware)

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
# Os MESMOS documentos, em JSON (markdown cru + versão), para o APP. É o que
# permite trocar os termos sem publicar uma build nova: o texto do app deixa de
# ser um asset congelado e passa a ser baixado e cacheado.
app.include_router(rotas_legal.router_api, prefix="/v1/legal")
# Site de apresentação (landing + app-ads.txt), na RAIZ. Registrado por ÚLTIMO,
# depois de todas as rotas da API — assim ele nunca sombreia nada.
# ⚠️ São rotas EXPLÍCITAS ("/" e "/app-ads.txt"), não um `StaticFiles` montado em
# "/": um mount na raiz engoliria qualquer caminho não casado (ex.: um
# `/v1/rota-inexistente`) e trocaria o 404 JSON da API pelo 404 do servidor de
# arquivos. Ver a explicação completa em `api/site/rotas.py`.
app.include_router(rotas_site.router)


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
