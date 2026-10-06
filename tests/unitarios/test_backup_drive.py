"""O cliente do Google Drive do backup (`backup/drive.py`), sem internet.

`AbridorFalso` faz o papel do `urllib.request.urlopen`: anota cada pedido
(método, endereço, cabeçalhos, corpo) e devolve a próxima resposta da fila. É o
pedido que se confere - o mesmo que o Google receberia.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from backup import drive


class _Resposta:
    """Uma resposta HTTP mínima: cabeçalhos, corpo e o `with` do urlopen."""

    def __init__(self, corpo: bytes = b"{}", cabecalhos: dict | None = None):
        self._corpo = corpo
        self.headers = cabecalhos or {}

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class AbridorFalso:
    def __init__(self, respostas: list):
        self.respostas = list(respostas)
        self.pedidos = []

    def __call__(self, pedido, timeout=None):
        self.pedidos.append(pedido)
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def _json(dados) -> _Resposta:
    return _Resposta(json.dumps(dados).encode())


def _cabecalho(pedido, nome):
    """`Request` guarda os cabeçalhos com a 1ª letra maiúscula; lê sem depender disso."""
    return {k.lower(): v for k, v in pedido.header_items()}.get(nome.lower())


class TestToken:
    def test_troca_o_refresh_token_por_um_de_acesso(self):
        abrir = AbridorFalso([_json({"access_token": "TOKEN_1H"})])
        assert drive.obter_token_de_acesso("cid", "csec", "rtok", abrir) == "TOKEN_1H"
        pedido = abrir.pedidos[0]
        assert pedido.get_method() == "POST" and pedido.full_url == drive.URL_TOKEN
        corpo = urllib.parse.parse_qs(pedido.data.decode())
        assert corpo == {
            "client_id": ["cid"],
            "client_secret": ["csec"],
            "refresh_token": ["rtok"],
            "grant_type": ["refresh_token"],
        }

    def test_resposta_sem_token_e_erro(self):
        with pytest.raises(drive.ErroDoDrive):
            drive.obter_token_de_acesso("c", "s", "r", AbridorFalso([_json({})]))

    def test_erro_http_vira_erro_do_drive_sem_repetir_o_que_enviamos(self):
        recusa = urllib.error.HTTPError(
            drive.URL_TOKEN, 400, "Bad Request", {}, io.BytesIO(b'{"error": "invalid_grant"}')
        )
        with pytest.raises(drive.ErroDoDrive) as erro:
            drive.obter_token_de_acesso("c", "SEGREDO", "REFRESH", AbridorFalso([recusa]))
        texto = str(erro.value)
        assert "400" in texto and "invalid_grant" in texto
        assert "SEGREDO" not in texto and "REFRESH" not in texto


class TestEnvio:
    def test_envio_resumable_em_dois_passos(self, tmp_path: Path):
        arquivo = tmp_path / "x.dump.gpg"
        arquivo.write_bytes(b"z" * 7_000_000)  # acima dos 5 MB do multipart
        abrir = AbridorFalso(
            [
                _Resposta(cabecalhos={"Location": "https://sessao.exemplo/abc"}),
                _json({"id": "id-novo", "name": "x.dump.gpg", "size": "7000000"}),
            ]
        )
        enviado = drive.ClienteDrive("TOK", abrir).enviar(arquivo, "x.dump.gpg", "pasta-1")

        assert enviado == drive.ArquivoNoDrive("id-novo", "x.dump.gpg", 7_000_000)
        sessao, bytes_ = abrir.pedidos
        assert sessao.get_method() == "POST"
        assert sessao.full_url.startswith(drive.URL_ENVIO + "?uploadType=resumable")
        assert "size" in sessao.full_url  # sem `fields`, o Drive não devolve o tamanho
        assert json.loads(sessao.data) == {"name": "x.dump.gpg", "parents": ["pasta-1"]}
        assert _cabecalho(sessao, "X-Upload-Content-Length") == "7000000"
        assert _cabecalho(sessao, "Authorization") == "Bearer TOK"
        assert bytes_.get_method() == "PUT" and bytes_.full_url == "https://sessao.exemplo/abc"
        assert bytes_.data == arquivo.read_bytes()
        assert _cabecalho(bytes_, "Authorization") == "Bearer TOK"

    def test_sem_endereco_de_sessao_e_erro(self, tmp_path: Path):
        arquivo = tmp_path / "x"
        arquivo.write_bytes(b"1")
        with pytest.raises(drive.ErroDoDrive, match="sessão"):
            drive.ClienteDrive("T", AbridorFalso([_Resposta()])).enviar(arquivo, "x", "p")


class TestListar:
    def test_le_todas_as_paginas(self):
        abrir = AbridorFalso(
            [
                _json({"files": [{"id": "1", "name": "a", "size": "10"}], "nextPageToken": "P2"}),
                _json({"files": [{"id": "2", "name": "b", "size": "20"}]}),
            ]
        )
        arquivos = drive.ClienteDrive("T", abrir).listar("pasta-1")
        assert [a.id for a in arquivos] == ["1", "2"]
        primeira, segunda = (urllib.parse.parse_qs(urllib.parse.urlparse(p.full_url).query) for p in abrir.pedidos)
        assert primeira["q"] == ["'pasta-1' in parents and trashed = false"]
        assert "pageToken" not in primeira
        assert segunda["pageToken"] == ["P2"]

    def test_arquivo_sem_tamanho_fica_com_menos_um(self):
        abrir = AbridorFalso([_json({"files": [{"id": "1", "name": "pasta"}]})])
        assert drive.ClienteDrive("T", abrir).listar("p")[0].tamanho == -1


class TestLixeira:
    def test_manda_para_a_lixeira_e_nao_apaga_de_vez(self):
        abrir = AbridorFalso([_json({})])
        drive.ClienteDrive("T", abrir).mandar_para_lixeira("id-1")
        pedido = abrir.pedidos[0]
        assert pedido.get_method() == "PATCH"  # e não DELETE
        assert pedido.full_url == f"{drive.URL_ARQUIVOS}/id-1"
        assert json.loads(pedido.data) == {"trashed": True}


class TestPasta:
    def test_cria_a_pasta_com_o_tipo_de_pasta(self):
        abrir = AbridorFalso([_json({"id": "pasta-nova"})])
        assert drive.ClienteDrive("T", abrir).criar_pasta("Backups") == "pasta-nova"
        assert json.loads(abrir.pedidos[0].data) == {"name": "Backups", "mimeType": drive.TIPO_PASTA}

    def test_a_permissao_pedida_e_a_minima(self):
        assert drive.ESCOPO == "https://www.googleapis.com/auth/drive.file"
