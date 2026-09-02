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

    - [titulo]/[corpo]: o texto que aparece na notificação, já escrito no idioma
      de quem vai receber.
    - [dados]: pares chave→valor opcionais entregues junto (ex.: uma rota/deep
      link para o app abrir ao tocar). Tudo vira string no FCM.

    **Os critérios de público, todos opcionais e todos combináveis:**

    - [idioma]: `pt`, `en` ou `es` — quem lê o app naquele idioma;
    - [fuso]: o offset UTC **em minutos** (`-180` = UTC-3, `330` = UTC+5:30) —
      quem está naquele fuso;
    - [plataforma]: `android` ou `ios` — o aviso que só vale numa loja;
    - [topicos]: tópicos avulsos para cruzar com os de cima (`novidades`,
      `promocoes`).

    Sem nenhum deles, vai para `todos` — o app inteiro, como sempre foi. Com um,
    vai para aquele tópico. Com dois ou mais, o FCM recebe uma **condição** e só
    entrega a quem está em **todos** eles.

    ⚠️ Avisar nos três idiomas são TRÊS chamadas, uma por idioma, cada uma com o
    seu texto. Não há envio "em três idiomas de uma vez": o FCM entrega o texto
    que recebe, e é o remetente quem sabe traduzi-lo.

    ⚠️ **O fuso é em MINUTOS, e não em horas**, porque é assim que o aparelho o
    reporta (`DateTime.now().timeZoneOffset.inMinutes`) e assim que o job de
    campanha vai iterá-lo — sem parser no meio, e sem a ambiguidade de `5.5`
    para UTC+5:30. A resposta devolve o nome do tópico (`fuso_utc_menos_3`) para
    conferência.
    """

    titulo: str = Field(min_length=1, max_length=120)
    corpo: str = Field(min_length=1, max_length=500)
    # `Literal` em vez de `str`: um valor errado vira 422 com a lista dos
    # aceitos, em vez de um envio bem-sucedido para um tópico sem ninguém.
    idioma: Optional[Literal["pt", "en", "es"]] = None
    # Faixa real dos fusos do mundo (UTC-12 a UTC+14), em passos de 15 minutos —
    # o menor passo que existe em fuso oficial. A validação é por FAIXA, e não
    # por lista fechada: quem manda o offset é o relógio do aparelho, e uma lista
    # aqui só criaria divergência com o que o app assinou.
    fuso: Optional[int] = Field(default=None, ge=-720, le=840, multiple_of=15)
    plataforma: Optional[Literal["android", "ios"]] = None
    # Tópicos avulsos. Fechado numa lista de propósito: `str` livre aceitaria um
    # nome digitado errado, e o FCM devolve SUCESSO para tópico sem inscritos.
    topicos: Optional[list[Literal["todos", "novidades", "promocoes"]]] = Field(
        default=None, max_length=3
    )
    dados: Optional[dict[str, str]] = None


class BroadcastResposta(BaseModel):
    """Resposta do broadcast: o id da mensagem no FCM e **o destino usado**.

    Vem exatamente um dos dois preenchidos: [topico] quando o envio foi para um
    tópico só, [condicao] quando foi para uma combinação. É por aqui que quem
    dispara confere para onde a mensagem realmente foi — o FCM não conta.

    ⚠️ **Id de mensagem não é prova de entrega.** O FCM aceita e numera um envio
    para tópico sem nenhum inscrito. A resposta diz o destino; quem sabe se ele
    tem gente é quem dispara.
    """

    id_mensagem: str
    topico: Optional[str] = None
    condicao: Optional[str] = None
