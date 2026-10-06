"""Autoriza o backup a escrever no Google Drive do dono - roda UMA vez, no PC dele.

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -m backup.autorizar_drive --id-cliente <ID DO CLIENTE OAUTH>

O que acontece:

1. pede o *segredo do cliente* OAuth sem mostrá-lo na tela (`getpass`);
2. abre o navegador na página de consentimento do Google - entre com
   **`santiagodata.tech@gmail.com`** e aceite;
3. o Google devolve o navegador para um servidorzinho que este script abriu em
   `127.0.0.1`, numa porta qualquer, só durante esse instante;
4. o script troca o código recebido pelo **refresh token** e **cria a pasta** dos
   backups no Drive (com a permissão `drive.file`, o serviço só enxerga a pasta
   que este programa criou - uma pasta criada à mão no navegador seria invisível);
5. imprime o refresh token e o id da pasta, para **colar direto nas variáveis do
   serviço no Railway** (`GOOGLE_OAUTH_REFRESH_TOKEN` e `BACKUP_ID_PASTA_DRIVE`).

⛔ **O refresh token é segredo**: não vai para o Git, para arquivo nem para
conversa. Ele vale até ser revogado - e é revogável a qualquer momento em
https://myaccount.google.com/permissions.

⚠️ **Pré-requisito no Google Cloud** (o passo a passo está no plano, B2): a tela de
consentimento **Externa e "Em produção"** - no modo "Teste" este token morre em 7
dias - e uma credencial OAuth do tipo **"App para computador"**.

⚠️ **Reautorizar** (token revogado, senha do Google trocada): rode de novo com
`--sem-criar-pasta`, e troque só o `GOOGLE_OAUTH_REFRESH_TOKEN` no Railway. A pasta
antiga continua visível, porque foi criada pelo mesmo cliente OAuth.

**PKCE** (a dupla `code_verifier` / `code_challenge`): o script sorteia um segredo
de uso único, manda ao Google só o resumo SHA-256 dele, e apresenta o original na
troca do código. Quem interceptasse o código no caminho não conseguiria trocá-lo.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import http.server
import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser

from backup import drive as drive_mod

URL_CONSENTIMENTO = "https://accounts.google.com/o/oauth2/v2/auth"

#: O nome da pasta que o script cria no Drive.
NOME_DA_PASTA = "Arena Sagaz - backups do banco prd"


def _base64_url(dados: bytes) -> str:
    """Base64 na variante de URL (`-` e `_` no lugar de `+` e `/`), sem o `=` do fim.

    É a forma que o PKCE exige para o `code_challenge`.
    """
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def _esperar_o_retorno(porta_livre: int = 0) -> tuple[http.server.HTTPServer, dict]:
    """Abre o servidorzinho local que recebe o navegador de volta do Google.

    `porta_livre = 0` pede ao sistema operacional uma porta livre qualquer. O
    dicionário devolvido é preenchido pelo tratador quando o Google chamar.
    """
    recebido: dict = {}

    class Tratador(http.server.BaseHTTPRequestHandler):
        """Responde à ÚNICA visita que importa: o retorno do Google."""

        def do_GET(self):  # noqa: N802 - o nome é imposto pela biblioteca padrão
            consulta = urllib.parse.urlparse(self.path).query
            # `parse_qs` devolve listas (`{'code': ['abc']}`); fica o 1º de cada.
            recebido.update({k: v[0] for k, v in urllib.parse.parse_qs(consulta).items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<p>Pronto. Pode fechar esta aba e voltar ao PowerShell.</p>".encode()
            )

        def log_message(self, *args):
            """Cala o log de cada visita - ele imprimiria o código de autorização."""

    servidor = http.server.HTTPServer(("127.0.0.1", porta_livre), Tratador)
    return servidor, recebido


def main(argumentos: list[str] | None = None) -> int:
    """Conduz a autorização inteira. Devolve 0 se deu certo."""
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--id-cliente", required=True, help="o ID do cliente OAuth")
    leitor.add_argument(
        "--sem-criar-pasta",
        action="store_true",
        help="só reautorizar: não cria uma pasta nova",
    )
    args = leitor.parse_args(argumentos)
    segredo_cliente = getpass.getpass("Segredo do cliente OAuth (não aparece na tela): ")

    servidor, recebido = _esperar_o_retorno()
    endereco_de_retorno = f"http://127.0.0.1:{servidor.server_address[1]}"
    verificador = _base64_url(secrets.token_bytes(32))
    estado = secrets.token_urlsafe(16)
    parametros = {
        "client_id": args.id_cliente,
        "redirect_uri": endereco_de_retorno,
        "response_type": "code",
        "scope": drive_mod.ESCOPO,
        # `offline` é o que faz o Google devolver o refresh token; `consent` força
        # a pergunta mesmo para quem já autorizou, senão o token não vem de novo.
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": _base64_url(hashlib.sha256(verificador.encode()).digest()),
        "code_challenge_method": "S256",
        # O `state` volta igual do Google; se não voltar, o retorno não é nosso.
        "state": estado,
    }
    url = f"{URL_CONSENTIMENTO}?{urllib.parse.urlencode(parametros)}"
    print("Abrindo o navegador. Entre com santiagodata.tech@gmail.com e aceite.")
    print(f"Se ele não abrir, copie este endereço:\n{url}\n")
    webbrowser.open(url)
    # Atende uma visita só e segue. O tempo limite evita esperar para sempre.
    servidor.timeout = 300
    servidor.handle_request()
    servidor.server_close()

    if recebido.get("state") != estado or "code" not in recebido:
        print(f"Autorização não concluída: {recebido.get('error', 'sem resposta do Google')}")
        return 1

    corpo = urllib.parse.urlencode(
        {
            "client_id": args.id_cliente,
            "client_secret": segredo_cliente,
            "code": recebido["code"],
            "code_verifier": verificador,
            "grant_type": "authorization_code",
            "redirect_uri": endereco_de_retorno,
        }
    ).encode()
    pedido = urllib.request.Request(drive_mod.URL_TOKEN, data=corpo, method="POST")
    pedido.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(pedido, timeout=60) as resposta:
        tokens = json.loads(resposta.read())
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("O Google não devolveu refresh token. Confira a tela de consentimento.")
        return 1

    print("\n=== Cole no serviço de backup do Railway (ambiente prd) ===")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN = {refresh_token}")
    if not args.sem_criar_pasta:
        cliente = drive_mod.ClienteDrive(tokens["access_token"])
        id_pasta = cliente.criar_pasta(NOME_DA_PASTA)
        print(f"BACKUP_ID_PASTA_DRIVE      = {id_pasta}")
        print(f'(a pasta "{NOME_DA_PASTA}" foi criada na raiz do Drive)')
    print("\nNão salve o token em arquivo nem no Git.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
