import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional


class LogHandlerJSON(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        entrada: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": record.levelname,
            "modulo": record.name,
            "mensagem": self.format(record),
        }
        for campo in ("usuario_id", "rota", "duracao_ms"):
            valor = getattr(record, campo, None)
            if valor is not None:
                entrada[campo] = valor
        print(json.dumps(entrada, ensure_ascii=False))


def obter_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    if not logger.handlers:
        handler = LogHandlerJSON()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
