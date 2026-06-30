"""Modelos (Pydantic) das notificações — request/response do broadcast.

Pydantic valida e serializa o JSON da API. Aqui modelamos o corpo do disparo de
**broadcast** (envio para todos os usuários, via tópico FCM) e a resposta.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Categorias válidas de preferência (espelham o data-model e o app). `Literal`
# faz o Pydantic recusar (422) qualquer valor fora desta lista.
CategoriaNotif = Literal["transacional", "lembrete", "novidades", "marketing"]

# Plataformas aceitas no registro de dispositivo.
PlataformaNotif = Literal["android", "ios", "web"]


class DispositivoRequest(BaseModel):
    """Corpo do `POST /v1/notificacoes/dispositivo` — registra/atualiza o token
    FCM do aparelho (UPSERT por `co_token_fcm`)."""

    co_token_fcm: str = Field(min_length=1, max_length=4096)
    sg_plataforma: PlataformaNotif
    co_idioma: str = Field(min_length=2, max_length=2)


class PreferenciaItem(BaseModel):
    """Uma preferência: a categoria e se está ligada."""

    co_categoria: CategoriaNotif
    ic_ativo: bool


class PreferenciasRequest(BaseModel):
    """Corpo do `PUT /v1/notificacoes/preferencias` — lista de categorias."""

    preferencias: list[PreferenciaItem] = Field(min_length=1, max_length=10)


class PreferenciasResposta(BaseModel):
    """Estado atual das preferências do usuário."""

    preferencias: list[PreferenciaItem]


class BroadcastRequest(BaseModel):
    """Corpo do `POST /v1/notificacoes/broadcast`.

    - [titulo]/[corpo]: o texto que aparece na notificação (já no idioma desejado
      por quem dispara — o broadcast é uma mensagem única para todos).
    - [dados]: pares chave→valor opcionais entregues junto (ex.: uma rota/deep
      link para o app abrir ao tocar). Tudo vira string no FCM.
    """

    titulo: str = Field(min_length=1, max_length=120)
    corpo: str = Field(min_length=1, max_length=500)
    dados: Optional[dict[str, str]] = None


class BroadcastResposta(BaseModel):
    """Resposta do broadcast: o id da mensagem no FCM e o tópico atingido."""

    id_mensagem: str
    topico: str
