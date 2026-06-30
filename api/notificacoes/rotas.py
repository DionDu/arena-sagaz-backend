"""Rotas de notificações — `POST /v1/notificacoes/broadcast`.

Endpoint **administrativo** (não é chamado pelo app comum): dispara uma
notificação para **todos os usuários** via tópico FCM. Como ainda não há um
sistema de papéis (admin), protegemos com um **segredo compartilhado**: o
chamador precisa enviar o cabeçalho `X-Admin-Token` igual ao
`ADMIN_BROADCAST_TOKEN` configurado no ambiente. Se o segredo não estiver
definido, o endpoint fica **desabilitado** (default seguro).

O prefixo `/v1/notificacoes` é aplicado no `main.py`.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header

from api.configuracao import configuracoes
from api.notificacoes.modelos import BroadcastRequest, BroadcastResposta
from api.notificacoes.servico import ServicoNotificacoes, enviar_fcm_topico
from api.nucleo.excecoes import ErroNaoAutorizado

router = APIRouter()


def exigir_admin(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Autoriza só quem envia o `X-Admin-Token` correto.

    Lança 401 se o segredo não estiver configurado (endpoint desabilitado) ou se
    o token enviado não bater. NÃO logamos o token (é segredo).
    """
    segredo = (configuracoes.ADMIN_BROADCAST_TOKEN or "").strip()
    if not segredo:
        raise ErroNaoAutorizado(
            "Broadcast desabilitado (sem ADMIN_BROADCAST_TOKEN).",
            "broadcast_desabilitado",
        )
    if not x_admin_token or x_admin_token.strip() != segredo:
        raise ErroNaoAutorizado(
            "Token administrativo inválido.", "admin_token_invalido"
        )


def obter_servico_notificacoes() -> ServicoNotificacoes:
    """Monta o serviço com o enviador REAL (firebase). É uma dependência própria
    para os testes a trocarem por um enviador fake (sem firebase)."""
    return ServicoNotificacoes(enviador=enviar_fcm_topico)


@router.post("/broadcast", response_model=BroadcastResposta)
async def broadcast(
    corpo: BroadcastRequest,
    _admin: None = Depends(exigir_admin),
    servico: ServicoNotificacoes = Depends(obter_servico_notificacoes),
) -> BroadcastResposta:
    """Dispara a notificação para TODOS (tópico `todos`) e devolve o id da msg."""
    return servico.enviar_broadcast(
        titulo=corpo.titulo, corpo=corpo.corpo, dados=corpo.dados
    )
