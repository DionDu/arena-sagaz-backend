"""Apaga do banco os tokens FCM MORTOS (dispositivos que já não existem).

    $env:DATABASE_URL = "<url-publica>"
    .venv\\Scripts\\python scripts/faxina_tokens_fcm.py --projeto des          # só lista
    .venv\\Scripts\\python scripts/faxina_tokens_fcm.py --projeto des --apagar

**Por que tokens morrem:** reinstalar o app, limpar os dados ou desinstalar gira o
token do FCM. A linha antiga fica em `conta.tb005_dispositivo_notificacao` como órfã.
Medido em 2026-07-12: um único aparelho, duas reinstalações, dois tokens — um vivo e
um morto.

**Por que isso importa:** o *broadcast* vai por **tópico**, e o tópico não olha a
nossa tabela — por isso ele funciona mesmo com token morto. Quem sofre é o push
**DIRECIONADO** (por usuário), que lê o token daqui: ele tentaria entregar num
aparelho que não existe mais.

⚠️ **Desde 22/09/2026 o envio direcionado EXISTE** — a notificação de reações do
Desafio do Dia (T079, `api/notificacoes/reacoes_do_desafio.py`), que é push por
token. E ela já faz a faxina **sozinha, no instante em que descobre**: o token que
responde `UNREGISTERED` (ou `SENDER_ID_MISMATCH`) sai da `tb005` na mesma passada,
que é exatamente o que este cabeçalho dizia ser "o certo quando fizer".

**Então para que este script continua servindo:** ele varre a tabela **inteira**, e
a faxina automática só toca nos tokens de quem recebeu reação ontem. Token morto de
quem nunca apareceu no quadro fica na base até alguém varrer — e é isso aqui.

**Como sabemos que um token morreu:** `dry_run=True` faz o FCM **validar** o token sem
entregar nada ao aparelho. Token morto → `UnregisteredError`.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import urlsplit

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def faxinar(url: str, app, apagar: bool) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as con:
        linhas = (
            await con.execute(
                text(
                    "SELECT co_token_fcm, sg_plataforma, id_usuario, dh_atualizacao "
                    "FROM conta.vw005_dispositivo_notificacao "
                    "ORDER BY dh_atualizacao DESC"
                )
            )
        ).all()

        mortos: list[str] = []
        print(f"\n{len(linhas)} dispositivo(s):\n")
        for token, plataforma, id_usuario, atualizado in linhas:
            try:
                # `dry_run`: o FCM valida o token e NÃO entrega nada ao aparelho.
                messaging.send(messaging.Message(token=token), app=app, dry_run=True)
                estado = "VIVO "
            except messaging.UnregisteredError:
                estado = "MORTO"
                mortos.append(token)
            except Exception as erro:  # noqa: BLE001 — qualquer outra falha: não apaga
                estado = f"?? ({type(erro).__name__})"
            dono = "logado" if id_usuario else "convidado"
            print(f"  [{estado}] {plataforma:7} {dono:9} {atualizado}  {token[:28]}...")

        if not mortos:
            print("\nNenhum token morto. Nada a fazer.")
            return

        print(f"\n{len(mortos)} token(s) morto(s).")
        if not apagar:
            print("Rode de novo com --apagar para removê-los.")
            return

        await con.execute(
            text(
                "DELETE FROM conta.tb005_dispositivo_notificacao "
                "WHERE co_token_fcm = ANY(:tokens)"
            ),
            {"tokens": mortos},
        )
        print(f"✅ {len(mortos)} linha(s) removida(s).")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projeto", choices=["des", "prd"], required=True)
    parser.add_argument("--apagar", action="store_true", help="remove de fato")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        sys.exit(
            "DATABASE_URL não está definida.\n"
            'No PowerShell:  $env:DATABASE_URL = "postgresql://..."\n'
            "(`set VAR=valor` NÃO funciona no PowerShell.)"
        )
    partes = urlsplit(url)
    print(f"Banco alvo: {partes.hostname}:{partes.port}  ·  Firebase: arena-sagaz-{args.projeto}")

    cred = credentials.Certificate(
        os.path.join(BASE, f"arena-sagaz-{args.projeto}-firebase-adminsdk.json")
    )
    app = firebase_admin.initialize_app(cred)

    asyncio.run(
        faxinar(url.replace("postgresql://", "postgresql+asyncpg://"), app, args.apagar)
    )


if __name__ == "__main__":
    main()
