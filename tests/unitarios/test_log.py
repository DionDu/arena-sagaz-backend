"""Testes do logging estruturado (T013) — garantia de que NÃO vaza PII."""
import json
import logging

from api.nucleo.log import LogHandlerJSON


def test_log_inclui_campos_seguros_e_ignora_pii(capsys):
    """O handler só emite campos da lista branca; token/e-mail são descartados."""
    handler = LogHandlerJSON()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="api.teste",
        level=logging.INFO,
        pathname="f.py",
        lineno=1,
        msg="GET /v1/x 200",
        args=None,
        exc_info=None,
    )
    # Campos seguros (devem aparecer):
    record.plataforma = "android"
    record.versao_app = "1.0.0"
    record.rota = "/v1/x"
    # Campos sensíveis (NÃO devem aparecer — não estão na lista branca):
    record.authorization = "Bearer token-secreto"
    record.email = "pessoa@exemplo.com"

    handler.emit(record)
    saida = capsys.readouterr().out
    dados = json.loads(saida)

    assert dados["plataforma"] == "android"
    assert dados["versao_app"] == "1.0.0"
    assert dados["rota"] == "/v1/x"
    # Garantias de privacidade:
    assert "authorization" not in dados
    assert "email" not in dados
    assert "token-secreto" not in saida
    assert "pessoa@exemplo.com" not in saida


def test_log_omite_campos_none(capsys):
    """Campos seguros ausentes (None) não poluem o JSON."""
    handler = LogHandlerJSON()
    handler.setFormatter(logging.Formatter("%(message)s"))
    record = logging.LogRecord(
        name="api.teste",
        level=logging.INFO,
        pathname="f.py",
        lineno=1,
        msg="x",
        args=None,
        exc_info=None,
    )
    record.plataforma = None  # não veio o cabeçalho
    handler.emit(record)
    dados = json.loads(capsys.readouterr().out)
    assert "plataforma" not in dados
