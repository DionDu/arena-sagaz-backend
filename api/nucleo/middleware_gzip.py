"""Middleware que DESCOMPRIME o corpo de requisições ``Content-Encoding: gzip``.

Por que existe: o Starlette/FastAPI têm ``GZipMiddleware`` que comprime as
**RESPOSTAS**, mas NÃO existe nada nativo que descomprima as **REQUISIÇÕES**. O
app (spec 006 / US1) envia o lote de sincronização **comprimido com gzip**
(``ClienteSync._postComprimido`` no frontend, com o cabeçalho
``Content-Encoding: gzip``) para poupar banda em conexões móveis ruins.

Sem este middleware, o servidor recebe os BYTES gzip crus e tenta lê-los como
JSON — o que falha (o app fica com o evento "pendente" na outbox, reenviando
para sempre). Aqui interceptamos a requisição no nível ASGI, lemos o corpo
inteiro, descomprimimos e o repassamos para a rota como JSON normal.

É um middleware ASGI "puro" (não usa ``BaseHTTPMiddleware``) para poder reescrever
o ``receive`` — a forma correta de trocar o corpo de uma requisição em Starlette.
"""
from __future__ import annotations

import json
import zlib
from typing import Any, Awaitable, Callable

# Tipos ASGI (aliases só para legibilidade — são dicts/callables comuns).
Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# ── Limites contra "bomba gzip" (SEG-03) ─────────────────────────────────────
# Gzip comprime até ~1000:1, então um corpo pequeno pode expandir para GBs e
# esgotar a memória do servidor (DoS). Um lote de sincronização real tem poucos
# KB; estes tetos deixam folga enorme e ainda assim barram um abuso.
#   • MAX_CORPO_COMPRIMIDO: teto dos BYTES recebidos (antes de descomprimir).
#   • MAX_CORPO_DESCOMPRIMIDO: teto do resultado DESCOMPRIMIDO.
MAX_CORPO_COMPRIMIDO = 2 * 1024 * 1024      # 2 MB
MAX_CORPO_DESCOMPRIMIDO = 20 * 1024 * 1024  # 20 MB


async def _responder_413(send: Send) -> None:
    """Responde ``413 Payload Too Large`` no nível ASGI, no mesmo formato de erro
    da API (``{"detalhe", "codigo"}``), sem repassar a requisição adiante."""
    corpo = json.dumps(
        {"detalhe": "Corpo comprimido grande demais.", "codigo": "corpo_grande_demais"}
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": corpo})


class GzipRequestMiddleware:
    """Descomprime o corpo das requisições HTTP com ``Content-Encoding: gzip``.

    Requisições SEM esse cabeçalho passam intactas (custo zero). Só quando o
    cabeçalho está presente é que lemos e descomprimimos o corpo.
    """

    def __init__(self, app: Callable) -> None:
        # `app` é a próxima camada ASGI (o resto da aplicação). Guardamos para
        # encadear a chamada.
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Só mexemos em requisições HTTP (ignora websockets, lifespan, etc.).
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Os cabeçalhos vêm como lista de tuplas de bytes: [(b"content-encoding", b"gzip"), ...].
        headers = dict(scope["headers"])
        encoding = headers.get(b"content-encoding", b"")
        if b"gzip" not in encoding.lower():
            # Sem gzip → não toca em nada (caminho comum, sem custo).
            await self.app(scope, receive, send)
            return

        # Lê o corpo INTEIRO (pode vir em vários "chunks" via more_body),
        # abortando com 413 se passar do teto de bytes COMPRIMIDOS (SEG-03).
        corpo = b""
        while True:
            mensagem = await receive()
            corpo += mensagem.get("body", b"")
            if len(corpo) > MAX_CORPO_COMPRIMIDO:
                await _responder_413(send)
                return
            if not mensagem.get("more_body", False):
                break

        # Descomprime com TETO no resultado (streaming): `decompressobj` para no
        # limite passado e devolve o excedente em `unconsumed_tail`; se sobrou
        # cauda, o conteúdo expandido passou do teto → 413 (bomba gzip barrada).
        # Se não for gzip válido, deixamos o corpo como está — a rota então
        # responde o erro de parsing normalmente (não é papel do middleware
        # "esconder" um corpo malformado).
        try:
            # wbits = 16 + MAX_WBITS seleciona o formato gzip (cabeçalho/checksum).
            descompressor = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
            expandido = descompressor.decompress(corpo, MAX_CORPO_DESCOMPRIMIDO)
            if descompressor.unconsumed_tail:
                await _responder_413(send)
                return
            corpo = expandido
        except zlib.error:
            pass

        # Reescreve os cabeçalhos: remove `content-encoding` (já descomprimimos) e
        # corrige `content-length` para o tamanho DESCOMPRIMIDO (senão o servidor
        # pode truncar/rejeitar o corpo).
        novos_cabecalhos = [
            (k, v)
            for (k, v) in scope["headers"]
            if k.lower() not in (b"content-encoding", b"content-length")
        ]
        novos_cabecalhos.append((b"content-length", str(len(corpo)).encode()))
        # `scope` é reutilizado pelo Starlette; copiamos antes de alterar.
        novo_scope = dict(scope)
        novo_scope["headers"] = novos_cabecalhos

        # `receive` "falso" que entrega o corpo já descomprimido, de uma vez.
        entregue = False

        async def receive_descomprimido() -> Message:
            nonlocal entregue
            if not entregue:
                entregue = True
                return {
                    "type": "http.request",
                    "body": corpo,
                    "more_body": False,
                }
            # Depois do corpo, sinaliza desconexão (padrão ASGI).
            return {"type": "http.disconnect"}

        await self.app(novo_scope, receive_descomprimido, send)
