"""Rate limiting simples, **sem dependência externa** (SEG-04).

Por que caseiro: adotar `slowapi`/Redis agora traria dependência nova e infra a
mais. Este limitador em memória (janela deslizante por IP) resolve o caso comum —
barrar abuso de volume de um mesmo cliente — sem nada disso.

Limitação conhecida (documentar no deploy): o estado é **por processo**. Com
várias instâncias no Railway, cada uma conta o seu próprio balde; o efeito é um
limite ~N× maior. Para limite global exato, migrar para um backend compartilhado
(Redis) — registrado como evolução futura. Para um app single-instance, já cumpre
o papel.

Chave = IP do cliente (respeita o 1º salto de `X-Forwarded-For`, que o proxy do
Railway preenche). Escritas (POST/PUT/PATCH/DELETE) usam um teto mais apertado que
leituras. `OPTIONS` (preflight CORS) e o health-check são isentos.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.configuracao import configuracoes

# Métodos considerados "escrita" (teto mais apertado).
_METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}

# Caminhos isentos (preflight é tratado à parte, pelo método).
#
# - `/v1/health`, `/health` → probe de infra do Railway.
# - `/app-ads.txt` → ⚠️ CRÍTICO. O rastreador do AdMob busca este arquivo na raiz
#   do domínio para autorizar quem pode vender o nosso inventário. Se ele levar um
#   `429`, a validação falha **em silêncio** e a receita de anúncios despenca —
#   sem nenhum erro visível. É o pior tipo de falha: some sozinha, semanas depois,
#   e ninguém liga uma coisa à outra. Isentar custa uma linha.
# - `/` → a landing. Um `429` na página inicial é péssimo cartão de visita, e
#   robôs de busca/prévia (Google, WhatsApp, LinkedIn) batem nela com frequência.
#   Ela é servida da MEMÓRIA (o HTML é lido no import), então não custa I/O.
_ISENTOS = {"/v1/health", "/health", "/app-ads.txt", "/"}

_JANELA_SEGUNDOS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Conta requisições por IP numa janela deslizante de 60s e responde **429**
    quando o cliente passa do teto. Lê os limites/flag da configuração **a cada
    requisição**, então dá para ligar/desligar (testes) sem recriar o app."""

    def __init__(self, app) -> None:
        super().__init__(app)
        # Um deque de timestamps por chave (IP + classe read/write). `defaultdict`
        # cria o deque vazio na 1ª vez que a chave aparece.
        self._acessos: dict[str, Deque[float]] = defaultdict(deque)

    def _ip_cliente(self, request: Request) -> str:
        """IP do cliente. Atrás do proxy do Railway, o IP real é o 1º item de
        `X-Forwarded-For` (o `request.client.host` seria o do proxy)."""
        encaminhado = request.headers.get("x-forwarded-for")
        if encaminhado:
            return encaminhado.split(",")[0].strip()
        return request.client.host if request.client else "desconhecido"

    async def dispatch(self, request: Request, call_next):
        # Desligado (ex.: testes) ou preflight/health → passa direto.
        if not configuracoes.RATE_LIMIT_ENABLED:
            return await call_next(request)
        if request.method == "OPTIONS" or request.url.path in _ISENTOS:
            return await call_next(request)

        escrita = request.method in _METODOS_ESCRITA
        limite = (
            configuracoes.RATE_LIMIT_ESCRITA_POR_MINUTO
            if escrita
            else configuracoes.RATE_LIMIT_POR_MINUTO
        )
        # Chave separada por classe (uma escrita não consome a cota de leitura).
        chave = f"{self._ip_cliente(request)}:{'w' if escrita else 'r'}"

        agora = time.monotonic()
        janela = self._acessos[chave]
        # Remove os timestamps que já saíram da janela de 60s (borda esquerda).
        limite_inferior = agora - _JANELA_SEGUNDOS
        while janela and janela[0] < limite_inferior:
            janela.popleft()

        if len(janela) >= limite:
            # Estourou: responde 429 no formato de erro da API. `Retry-After` diz
            # quantos segundos faltam para o item mais antigo sair da janela.
            retry = max(1, int(_JANELA_SEGUNDOS - (agora - janela[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detalhe": "Muitas requisições. Tente novamente em instantes.",
                    "codigo": "rate_limit_excedido",
                },
                headers={"Retry-After": str(retry)},
            )

        janela.append(agora)
        return await call_next(request)
