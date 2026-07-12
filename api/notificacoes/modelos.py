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
    FCM do aparelho (UPSERT por `co_token_fcm`).

    [co_fuso] e [nu_offset_minuto] são **OPCIONAIS de propósito**: os apps já
    publicados não os enviam, e um campo obrigatório novo quebraria todos eles de
    uma vez (o app fica congelado no aparelho até o usuário atualizar).

    **Para que servem:** preparar o terreno do futuro módulo de campanha, que vai
    mandar push **no idioma e no horário local** de cada um. Hoje o broadcast vai
    por tópico FCM — um texto, na hora, para todo mundo: quem está no Japão recebe
    às 4h da manhã. O FCM **não** tem "entregar no horário local"; só o modelo
    token + worker resolve, e ele precisa destes dados. Como o aparelho só reporta
    quando abre o app, eles **não podem ser preenchidos retroativamente** — daí
    coletarmos agora, mesmo sem a campanha existir. *Coletar cedo, usar depois.*
    """

    co_token_fcm: str = Field(min_length=1, max_length=4096)
    sg_plataforma: PlataformaNotif
    co_idioma: str = Field(min_length=2, max_length=2)

    # Nome IANA do fuso (ex.: 'America/Sao_Paulo'). É o IANA — e não o offset — que
    # o agendamento futuro precisa, porque ele **resolve horário de verão sozinho**.
    co_fuso: Optional[str] = Field(default=None, max_length=64)

    # Offset UTC em MINUTOS (ex.: -180 = BRT). Snapshot para consulta rápida e
    # fallback caso o IANA não venha. Faixa: UTC-14 (-840) a UTC+14 (+840).
    nu_offset_minuto: Optional[int] = Field(default=None, ge=-840, le=840)


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
