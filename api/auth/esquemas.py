from datetime import datetime

from pydantic import BaseModel, EmailStr


class LoginEntrada(BaseModel):
    email: EmailStr
    senha: str


class TokenSaida(BaseModel):
    acesso_token: str
    refresh_token: str
    tipo_token: str = "bearer"
    expira_em: datetime


class RefreshEntrada(BaseModel):
    refresh_token: str


class TokenAcessoSaida(BaseModel):
    acesso_token: str
    tipo_token: str = "bearer"
    expira_em: datetime


class LogoutEntrada(BaseModel):
    refresh_token: str
