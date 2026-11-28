"""Push do LANÇAMENTO DO XADREZ (1.6.0): um aviso por idioma, para todo o app.
═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT FAZ
═══════════════════════════════════════════════════════════════════════════
Chama o `POST /v1/notificacoes/broadcast` **três vezes** - uma por idioma
(`pt`, `en`, `es`), cada uma com o seu texto. É o único jeito de avisar cada
pessoa no idioma dela: o FCM entrega o texto que recebe, e quem sabe traduzir é
o remetente (ver `api/notificacoes/modelos.py`, `BroadcastRequest`).

Cada chamada vai para a COMBINAÇÃO de dois tópicos:

* `todos_<idioma>` - o aparelho que lê o app naquele idioma (o app assina sozinho
  desde a 1.2.0; em 28/11/2026 todos os aparelhos ativos do prd estavam na 1.3.0
  ou acima);
* `novidades` - quem **não desligou** "Novidades" nos ajustes de notificação.
  Lançamento de jogo é exatamente essa categoria; mandar para quem a desligou
  seria passar por cima da escolha da pessoa.

O FCM só entrega a quem está **nos dois** (`'todos_pt' in topics && 'novidades'
in topics`). Quem tocar na notificação cai na Home (`rota=/home`), que é onde o
aviso de "versão nova disponível" aparece para quem ainda está numa versão antiga.

═══════════════════════════════════════════════════════════════════════════
POR QUE UM SCRIPT, E NÃO UM `curl`
═══════════════════════════════════════════════════════════════════════════
No Windows, texto com acento passado como ARGUMENTO de linha de comando chega
destruído (latin-1 em vez de UTF-8) e a API responde *"There was an error parsing
the body"*. Aqui o texto mora no próprio arquivo `.py` (UTF-8) e vai como bytes
UTF-8 no corpo da requisição - o problema não tem por onde entrar.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR (a partir de `arena-sagaz-backend/`)
═══════════════════════════════════════════════════════════════════════════
    # 1) ENSAIO - só mostra o que seria enviado, não fala com ninguém:
    .venv\\Scripts\\python scripts\\push_lancamento_xadrez.py

    # 2) Ensaio de verdade no DES (chega só nos aparelhos de teste):
    .venv\\Scripts\\python scripts\\push_lancamento_xadrez.py --ambiente des --enviar

    # 3) PRODUÇÃO - chega em todos os usuários:
    .venv\\Scripts\\python scripts\\push_lancamento_xadrez.py --ambiente prd --enviar

    # Só um idioma, ou só uma loja (ex.: a Apple ainda não aprovou):
    ... --idiomas pt --plataforma android

O `X-Admin-Token` é pedido na tela (não aparece enquanto digita). Para não
digitar, defina antes `$env:ADMIN_BROADCAST_TOKEN = "..."`. O valor real é o
`ADMIN_BROADCAST_TOKEN` do serviço da API no Railway - e é **diferente** entre `des` e
`prd` (inventário dos segredos em `segredos/LEIA-ME.md`, na raiz).

⚠️ **Push enviado não se desfaz.** Rodar o `--enviar` duas vezes manda o aviso
duas vezes para todo mundo. Por isso o padrão é o ensaio.
"""
from __future__ import annotations

# `argparse` lê as opções da linha de comando; `getpass` pede o token sem eco;
# `urllib` faz a chamada HTTP sem dependência externa (vem com o Python).
import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# `Path(__file__).parents[1]` é a pasta `arena-sagaz-backend/` (o pai de
# `scripts/`). Entra no `sys.path` para o `import api...` abaixo funcionar quando
# o script é chamado pelo caminho, sem instalar nada.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.notificacoes.modelos import BroadcastRequest  # noqa: E402

# ── Endereços da API por ambiente ─────────────────────────────────────────
# Os mesmos do app: `config/dev.json` e `config/prod.json` do frontend.
URL_DA_API = {
    "des": "https://api-dev.arenasagaz.santiagodata.com",
    "prd": "https://api.arenasagaz.santiagodata.com",
}

# Para onde o toque na notificação leva. A Home está nas duas listas brancas do
# app (`kRotasPushPermitidas` e `rotasNotificacaoPermitidas`). ⚠️ Não use uma
# rota do xadrez: as versões antigas (1.3/1.4) não a conhecem e ignorariam o
# toque - e são justamente elas que precisam ver o aviso de atualização na Home.
ROTA_DO_TOQUE = "/home"

# Tópico da categoria "Novidades" (espelha `topicoNovidades` do app).
TOPICO_NOVIDADES = "novidades"

# ── Os textos, um por idioma ──────────────────────────────────────────────
# Limites da API: título até 120 caracteres, corpo até 500 (`BroadcastRequest`).
# Na bandeja do celular cabe bem menos: título curto, corpo em uma ou duas linhas.
# O nome do jogo é o genérico de cada idioma (Xadrez / Chess / Ajedrez).
TEXTOS = {
    "pt": {
        "titulo": "♟️ O Xadrez chegou na Arena Sagaz!",
        "corpo": "Jogue Xadrez contra o Cacau, a Pita, o Tex e o Magno. "
                 "Atualize o app e venha desafiá-los!",
    },
    "en": {
        "titulo": "♟️ Chess has arrived at Arena Sagaz!",
        "corpo": "Play Chess against Cacau, Pita, Tex and Magno. "
                 "Update the app and come challenge them!",
    },
    "es": {
        "titulo": "♟️ ¡El Ajedrez llegó a Arena Sagaz!",
        "corpo": "Juega al Ajedrez contra Cacau, Pita, Tex y Magno. "
                 "¡Actualiza la app y ven a desafiarlos!",
    },
}


def montar_corpo(idioma: str, plataforma: str | None = None) -> dict:
    """Monta o JSON de UMA chamada do broadcast, para o [idioma] pedido.

    Passa o resultado pelo próprio `BroadcastRequest` da API antes de devolver:
    um texto longo demais, um idioma ou tópico fora da lista viram erro AQUI, no
    ensaio, e não um 422 no meio do envio de produção (com um idioma já enviado
    e os outros não).

    [plataforma] (`android`/`ios`) restringe a uma loja - útil se uma delas
    ainda não tiver aprovado a versão.
    """
    corpo = {
        "titulo": TEXTOS[idioma]["titulo"],
        "corpo": TEXTOS[idioma]["corpo"],
        "idioma": idioma,
        "topicos": [TOPICO_NOVIDADES],
        "dados": {"rota": ROTA_DO_TOQUE},
    }
    if plataforma:
        corpo["plataforma"] = plataforma
    # `model_validate` levanta `ValidationError` se algo não passar; o
    # `model_dump(exclude_none=True)` devolve só os campos preenchidos.
    return BroadcastRequest.model_validate(corpo).model_dump(exclude_none=True)


def enviar(url_base: str, token: str, corpo: dict) -> dict:
    """Faz o `POST` e devolve a resposta da API (o id da mensagem e o destino).

    O corpo vai como **bytes UTF-8** (`ensure_ascii=False` mantém o acento como
    acento no JSON; o `.encode` o converte em UTF-8) - ver o cabeçalho do arquivo.
    """
    dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
    requisicao = urllib.request.Request(
        f"{url_base}/v1/notificacoes/broadcast",
        data=dados,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Admin-Token": token,
        },
    )
    with urllib.request.urlopen(requisicao, timeout=30) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def main() -> int:
    """Lê as opções, mostra o plano e (só com `--enviar`) dispara."""
    # O terminal do Windows pode estar numa codepage antiga (cp1252), que não
    # tem o ♟️ dos títulos: o `print` quebraria com `UnicodeEncodeError` antes
    # do envio. `reconfigure` passa a saída para UTF-8, e `errors="replace"`
    # troca por `?` o que o terminal ainda assim não souber desenhar.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--ambiente", choices=sorted(URL_DA_API), default="prd")
    analisador.add_argument(
        "--idiomas", nargs="+", choices=sorted(TEXTOS), default=["pt", "en", "es"]
    )
    analisador.add_argument("--plataforma", choices=["android", "ios"], default=None)
    analisador.add_argument(
        "--enviar", action="store_true",
        help="dispara de verdade; sem isto, é só ensaio",
    )
    opcoes = analisador.parse_args()

    # Monta (e valida) TODOS os corpos antes de enviar o primeiro: ou vão os
    # três, ou nenhum.
    corpos = {idioma: montar_corpo(idioma, opcoes.plataforma) for idioma in opcoes.idiomas}

    url_base = URL_DA_API[opcoes.ambiente]
    print(f"Ambiente: {opcoes.ambiente.upper()}  ({url_base})")
    for idioma, corpo in corpos.items():
        print(f"\n[{idioma}] {json.dumps(corpo, ensure_ascii=False, indent=2)}")

    if not opcoes.enviar:
        print("\nENSAIO: nada foi enviado. Para disparar, repita com --enviar.")
        return 0

    token = os.environ.get("ADMIN_BROADCAST_TOKEN") or getpass.getpass(
        f"X-Admin-Token do {opcoes.ambiente.upper()}: "
    )
    token = token.strip()
    if not token:
        print("Sem token, nada foi enviado.")
        return 1

    for idioma, corpo in corpos.items():
        try:
            resposta = enviar(url_base, token, corpo)
        except urllib.error.HTTPError as erro:
            # A API devolve o motivo em JSON (`admin_token_invalido`, 422...).
            # Para aqui: os idiomas anteriores JÁ foram; rode depois só os que
            # faltam com `--idiomas`.
            print(f"[{idioma}] FALHOU - HTTP {erro.code}: {erro.read().decode('utf-8', 'replace')}")
            print("Os idiomas acima deste já foram enviados; reenvie só os que faltam com --idiomas.")
            return 1
        # O destino que a API devolve é a conferência: tem de ser a condição com
        # `todos_<idioma>` e `novidades`.
        destino = resposta.get("condicao") or resposta.get("topico")
        print(f"[{idioma}] enviado - id {resposta.get('id_mensagem')} - destino: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
