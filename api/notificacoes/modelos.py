"""Modelos (Pydantic) das notificações — request/response do broadcast.

Pydantic valida e serializa o JSON da API. Aqui modelamos o corpo do disparo de
**broadcast** (envio para todos os usuários, via tópico FCM) e a resposta.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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
