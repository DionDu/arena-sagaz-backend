import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from api.configuracao import configuracoes

_ALGORITMO = "HS256"


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, hash: str) -> bool:
    return bcrypt.checkpw(senha.encode(), hash.encode())


def criar_token_acesso(dados: dict[str, Any]) -> tuple[str, datetime]:
    expira_em = datetime.now(timezone.utc) + timedelta(
        minutes=configuracoes.JWT_EXPIRACAO_MINUTOS
    )
    payload = {**dados, "exp": expira_em}
    token = jwt.encode(payload, configuracoes.JWT_SECRET, algorithm=_ALGORITMO)
    return token, expira_em


def verificar_token_acesso(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, configuracoes.JWT_SECRET, algorithms=[_ALGORITMO])
    except JWTError as e:
        raise ValueError(f"Token inválido: {e}") from e


def gerar_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def criar_hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
