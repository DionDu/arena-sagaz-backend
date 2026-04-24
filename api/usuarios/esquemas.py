from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class CriarUsuarioEntrada(BaseModel):
    apelido: str = Field(min_length=3, max_length=50)
    email: EmailStr
    senha: str = Field(min_length=8)

    @field_validator("apelido")
    @classmethod
    def validar_apelido(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Apelido deve conter apenas letras, números e _.")
        return v


class UsuarioSaida(BaseModel):
    id: str
    apelido: str
    email: str
    nivel: int
    xp_total: int
    criado_em: datetime

    model_config = {"from_attributes": True}


class UsuarioComTokenSaida(UsuarioSaida):
    acesso_token: str
    refresh_token: str
    expira_em: datetime
