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

import gzip
from typing import Any, Awaitable, Callable

# Tipos ASGI (aliases só para legibilidade — são dicts/callables comuns).
Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


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

        # Lê o corpo INTEIRO (pode vir em vários "chunks" via more_body).
        corpo = b""
        while True:
            mensagem = await receive()
            corpo += mensagem.get("body", b"")
            if not mensagem.get("more_body", False):
                break

        # Descomprime. Se por algum motivo não for gzip válido, deixamos o corpo
        # como está — a rota então responde o erro de parsing normalmente (não
        # é papel do middleware "esconder" um corpo malformado).
        try:
            corpo = gzip.decompress(corpo)
        except (OSError, EOFError):
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
