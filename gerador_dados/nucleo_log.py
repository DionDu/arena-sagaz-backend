"""Logger JSON simples para os módulos da Fase Zero."""
import json
import logging
from datetime import datetime, timezone
from typing import Any


class _HandlerJSON(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        entrada: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": record.levelname,
            "modulo": record.name,
            "mensagem": record.getMessage(),
        }
        print(json.dumps(entrada, ensure_ascii=False))


def obter_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    if not logger.handlers:
        handler = _HandlerJSON()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
