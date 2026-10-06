"""O Google Drive pela API REST, só com a biblioteca padrão do Python.

São quatro coisas, e só elas: trocar a autorização guardada por um token de
acesso, enviar um arquivo, listar a pasta e mandar um arquivo para a lixeira.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE A CONTA DO DONO, E NÃO UMA "CONTA DE SERVIÇO" DO GOOGLE
═══════════════════════════════════════════════════════════════════════════

Conta de serviço (o robô do Google Cloud) **não tem espaço no Drive**: um envio
dela para uma pasta de uma conta pessoal falha com `storageQuotaExceeded`, porque
o arquivo seria dela. O caminho é o **OAuth**: o dono autoriza este programa uma
vez (`autorizar_drive.py`), e o Google devolve um *refresh token* - uma
autorização de longa duração que o serviço troca, a cada execução, por um token de
acesso que vale uma hora.

⚠️ **A permissão pedida é a mínima, `drive.file`**: o programa só enxerga os
arquivos e pastas que **ele mesmo** criou. Ele não lê o resto do Drive, e é por
isso que a pasta dos backups é criada pelo `autorizar_drive.py`, e não à mão - uma
pasta criada no navegador seria invisível para ele.

⚠️ **E a tela de consentimento do projeto no Google Cloud tem de estar "Em
produção"**: no modo "Teste" o Google derruba o refresh token a cada 7 dias, e o
backup para sozinho na segunda semana.

═══════════════════════════════════════════════════════════════════════════
COMO SE TESTA SEM INTERNET
═══════════════════════════════════════════════════════════════════════════

Toda função recebe `abrir`, que por padrão é `urllib.request.urlopen`. O teste
passa um falso, que anota o pedido e devolve uma resposta pronta - e confere
método, endereço, cabeçalhos e corpo de cada chamada.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

#: Onde o Google troca o refresh token por um token de acesso.
URL_TOKEN = "https://oauth2.googleapis.com/token"
#: A API do Drive para metadados (listar, mudar, criar pasta).
URL_ARQUIVOS = "https://www.googleapis.com/drive/v3/files"
#: A API do Drive para conteúdo (o envio do arquivo em si).
URL_ENVIO = "https://www.googleapis.com/upload/drive/v3/files"

#: A permissão mínima: só os arquivos que este programa criou.
ESCOPO = "https://www.googleapis.com/auth/drive.file"

#: O tipo que o Drive dá a uma pasta - ela é um "arquivo" com este mimeType.
TIPO_PASTA = "application/vnd.google-apps.folder"

#: Quanto esperar por uma resposta do Google antes de desistir (segundos). Um
#: envio de ~15 MB leva poucos segundos; 5 minutos dá folga para rede ruim sem
#: deixar a execução pendurada para sempre.
TEMPO_LIMITE_S = 300

# `Callable[..., object]` é o tipo de "qualquer função": aqui, algo que se chama
# como o `urlopen` (recebe um pedido e um tempo limite, devolve uma resposta).
Abridor = Callable[..., object]


class ErroDoDrive(RuntimeError):
    """Algo falhou na conversa com o Google. A mensagem nunca leva credencial."""


@dataclass(frozen=True)
class ArquivoNoDrive:
    """Um arquivo da pasta, como o Drive o descreve.

    `frozen=True` torna o objeto imutável: depois de criado, nenhum campo muda -
    é um retrato do que o Drive respondeu naquele instante.
    """

    id: str
    nome: str
    # O Drive devolve o tamanho como TEXTO (`"12345"`); aqui já vira número.
    tamanho: int


def _pedir(
    abrir: Abridor,
    pedido: urllib.request.Request,
) -> tuple[dict[str, str], bytes]:
    """Faz um pedido HTTP e devolve `(cabeçalhos, corpo)`.

    Erro HTTP (4xx, 5xx) vira `ErroDoDrive` com o código e o começo da resposta
    do Google - que explica o que houve (`storageQuotaExceeded`, `invalid_grant`)
    sem repetir o que **nós** enviamos, onde estariam os segredos.
    """
    try:
        # `with` garante que a conexão é fechada ao sair do bloco, mesmo com erro.
        with abrir(pedido, timeout=TEMPO_LIMITE_S) as resposta:
            cabecalhos = {k.lower(): v for k, v in resposta.headers.items()}
            return cabecalhos, resposta.read()
    except urllib.error.HTTPError as erro:
        detalhe = erro.read()[:500].decode("utf-8", errors="replace")
        raise ErroDoDrive(
            f"o Google respondeu {erro.code} em {pedido.get_method()} "
            f"{_sem_consulta(pedido.full_url)}: {detalhe}"
        ) from None
    except urllib.error.URLError as erro:
        raise ErroDoDrive(
            f"sem conexão com {_sem_consulta(pedido.full_url)}: {erro.reason}"
        ) from None


def _sem_consulta(url: str) -> str:
    """O endereço sem a parte depois do `?`, para a mensagem de erro.

    O endereço de envio do Drive leva um identificador de sessão na consulta; ele
    não é segredo de longa duração, mas também não ajuda ninguém a entender o erro.
    """
    return url.split("?", 1)[0]


def obter_token_de_acesso(
    id_cliente: str,
    segredo_cliente: str,
    refresh_token: str,
    abrir: Abridor = urllib.request.urlopen,
) -> str:
    """Troca a autorização guardada (refresh token) por um token de acesso.

    O token de acesso vale cerca de uma hora - sobra para uma execução inteira.
    `invalid_grant` na resposta quer dizer que a autorização foi revogada ou
    expirou: o caminho é rodar o `autorizar_drive.py` de novo.
    """
    # `urlencode` monta o corpo de formulário `a=1&b=2`, que é o que o endpoint
    # de token do Google espera; `.encode()` transforma o texto em bytes.
    corpo = urllib.parse.urlencode(
        {
            "client_id": id_cliente,
            "client_secret": segredo_cliente,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    pedido = urllib.request.Request(URL_TOKEN, data=corpo, method="POST")
    pedido.add_header("Content-Type", "application/x-www-form-urlencoded")
    _, resposta = _pedir(abrir, pedido)
    dados = json.loads(resposta)
    token = dados.get("access_token")
    if not token:
        raise ErroDoDrive("o Google não devolveu access_token na troca do refresh token")
    return token


class ClienteDrive:
    """As três operações do backup sobre uma pasta do Drive."""

    def __init__(self, token_de_acesso: str, abrir: Abridor = urllib.request.urlopen):
        self._token = token_de_acesso
        self._abrir = abrir

    def _pedido(
        self, url: str, metodo: str, corpo: bytes | None = None
    ) -> urllib.request.Request:
        """Um pedido já com o cabeçalho de autorização."""
        pedido = urllib.request.Request(url, data=corpo, method=metodo)
        pedido.add_header("Authorization", f"Bearer {self._token}")
        return pedido

    def enviar(self, caminho: Path, nome: str, id_pasta: str) -> ArquivoNoDrive:
        """Envia `caminho` para a pasta, com o nome `nome`.

        ⚠️ **Envio "resumable", em dois passos**, e não o "multipart" de um passo só:
        o multipart do Drive é para arquivos de até 5 MB, e o backup tem mais que
        isso. Passo 1: um POST com só os metadados (nome, pasta, tamanho) abre uma
        sessão, e o Google devolve o endereço dela no cabeçalho `Location`. Passo 2:
        um PUT com os bytes nesse endereço. A resposta do passo 2 descreve o arquivo
        criado - inclusive o tamanho que **chegou**, que o fluxo compara com o
        enviado.
        """
        conteudo = caminho.read_bytes()
        metadados = json.dumps({"name": nome, "parents": [id_pasta]}).encode()
        # `fields` diz ao Drive quais campos devolver; sem ele, `size` não vem.
        abrir_sessao = self._pedido(
            f"{URL_ENVIO}?uploadType=resumable&fields=id,name,size",
            "POST",
            metadados,
        )
        abrir_sessao.add_header("Content-Type", "application/json; charset=UTF-8")
        abrir_sessao.add_header("X-Upload-Content-Type", "application/octet-stream")
        abrir_sessao.add_header("X-Upload-Content-Length", str(len(conteudo)))
        cabecalhos, _ = _pedir(self._abrir, abrir_sessao)
        endereco_da_sessao = cabecalhos.get("location")
        if not endereco_da_sessao:
            raise ErroDoDrive("o Drive não devolveu o endereço da sessão de envio")

        mandar_bytes = self._pedido(endereco_da_sessao, "PUT", conteudo)
        mandar_bytes.add_header("Content-Type", "application/octet-stream")
        _, resposta = _pedir(self._abrir, mandar_bytes)
        return _arquivo(json.loads(resposta))

    def listar(self, id_pasta: str) -> list[ArquivoNoDrive]:
        """Todos os arquivos da pasta que não estão na lixeira.

        O Drive responde em páginas: enquanto vier `nextPageToken`, há mais. Com
        ~15 arquivos uma página basta, mas um laço que só lê a primeira página
        ficaria cego no dia em que a pasta crescesse - e uma faxina cega deixa de
        apagar sem avisar.
        """
        # A consulta, na linguagem de busca do Drive: "está nesta pasta e não está
        # na lixeira". As aspas simples cercam o id dentro da expressão.
        consulta = f"'{id_pasta}' in parents and trashed = false"
        arquivos: list[ArquivoNoDrive] = []
        pagina: str | None = None
        while True:
            parametros = {
                "q": consulta,
                "fields": "nextPageToken,files(id,name,size)",
                "pageSize": "1000",
            }
            if pagina:
                parametros["pageToken"] = pagina
            url = f"{URL_ARQUIVOS}?{urllib.parse.urlencode(parametros)}"
            _, resposta = _pedir(self._abrir, self._pedido(url, "GET"))
            dados = json.loads(resposta)
            arquivos.extend(_arquivo(f) for f in dados.get("files", []))
            pagina = dados.get("nextPageToken")
            if not pagina:
                return arquivos

    def mandar_para_lixeira(self, id_arquivo: str) -> None:
        """Manda o arquivo para a lixeira do Drive, em vez de apagá-lo de vez.

        ⚠️ **De propósito.** A lixeira guarda o arquivo por 30 dias: se a faxina um
        dia apagar o que não devia (um defeito nosso na regra), o arquivo ainda
        volta com um clique. O custo é o espaço desses 30 dias - centenas de MB
        numa conta de 15 GB.
        """
        url = f"{URL_ARQUIVOS}/{urllib.parse.quote(id_arquivo)}"
        pedido = self._pedido(url, "PATCH", json.dumps({"trashed": True}).encode())
        pedido.add_header("Content-Type", "application/json; charset=UTF-8")
        _pedir(self._abrir, pedido)

    def criar_pasta(self, nome: str) -> str:
        """Cria uma pasta na raiz do Drive e devolve o id dela.

        Só o `autorizar_drive.py` chama isto, uma vez: com a permissão
        `drive.file`, a pasta precisa ter sido criada **por este programa** para
        que ele a enxergue.
        """
        corpo = json.dumps({"name": nome, "mimeType": TIPO_PASTA}).encode()
        pedido = self._pedido(f"{URL_ARQUIVOS}?fields=id", "POST", corpo)
        pedido.add_header("Content-Type", "application/json; charset=UTF-8")
        _, resposta = _pedir(self._abrir, pedido)
        return json.loads(resposta)["id"]


def _arquivo(dados: dict) -> ArquivoNoDrive:
    """Converte a descrição do Drive (um dicionário JSON) em `ArquivoNoDrive`.

    `size` falta em arquivos que não têm conteúdo binário (uma pasta, um Google
    Docs); nesses casos o tamanho fica -1, que nunca coincide com um backup.
    """
    return ArquivoNoDrive(
        id=dados["id"],
        nome=dados["name"],
        tamanho=int(dados.get("size", -1)),
    )
