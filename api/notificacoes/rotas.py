"""Rotas de notificações — `POST /v1/notificacoes/broadcast`.

Endpoint **administrativo** (não é chamado pelo app comum): dispara uma
notificação para **todos os usuários** via tópico FCM. Como ainda não há um
sistema de papéis (admin), protegemos com um **segredo compartilhado**: o
chamador precisa enviar o cabeçalho `X-Admin-Token` igual ao
`ADMIN_BROADCAST_TOKEN` configurado no ambiente. Se o segredo não estiver
definido, o endpoint fica **desabilitado** (default seguro).

O prefixo `/v1/notificacoes` é aplicado no `main.py`.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from api.configuracao import configuracoes
from api.notificacoes.modelos import (
    BroadcastRequest,
    BroadcastResposta,
    DispositivoRequest,
    PreferenciasRequest,
    PreferenciasResposta,
)
from api.notificacoes.repositorio import RepositorioNotificacao
from api.notificacoes.servico import ServicoNotificacoes, enviar_fcm_topico
from api.notificacoes.servico_preferencias import ServicoPreferenciasNotificacao
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import usuario_atual
from api.nucleo.excecoes import ErroNaoAutorizado
from api.nucleo.seguranca_firebase import IdentidadeFirebase, obter_verificador

router = APIRouter()


async def usuario_atual_opcional(
    authorization: Optional[str] = Header(default=None),
) -> Optional[IdentidadeFirebase]:
    """Como [usuario_atual], mas **não obriga** login: devolve a identidade se
    houver um token válido, ou `None` (sessão de convidado). Usado no registro de
    dispositivo, que aceita convidado (token sem dono)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        return await obter_verificador().verificar(token)
    except ErroNaoAutorizado:
        return None  # token inválido → trata como convidado


def obter_servico_preferencias(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoPreferenciasNotificacao:
    """Monta o serviço de dispositivos/preferências ligado à sessão da requisição.
    Dependência própria para os testes a trocarem por um fake (sem banco)."""
    return ServicoPreferenciasNotificacao(
        repo=RepositorioNotificacao(sessao), sessao=sessao
    )


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
    # `compare_digest` compara em tempo constante (não vaza, pelo tempo de resposta,
    # quantos caracteres do segredo acertaram) — endurece contra timing attack (MEL-02).
    if not x_admin_token or not secrets.compare_digest(x_admin_token.strip(), segredo):
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


@router.post("/dispositivo", status_code=200)
async def registrar_dispositivo(
    corpo: DispositivoRequest,
    identidade: Optional[IdentidadeFirebase] = Depends(usuario_atual_opcional),
    servico: ServicoPreferenciasNotificacao = Depends(obter_servico_preferencias),
) -> dict:
    """Registra/atualiza o token FCM do aparelho (UPSERT por token). Aceita
    convidado (sem login) — aí o token fica sem dono."""
    await servico.registrar_dispositivo(
        uid=identidade.uid if identidade else None,
        co_token_fcm=corpo.co_token_fcm,
        sg_plataforma=corpo.sg_plataforma,
        co_idioma=corpo.co_idioma,
    )
    return {"ok": True}


@router.delete("/dispositivo/{co_token_fcm}", status_code=200)
async def remover_dispositivo(
    co_token_fcm: str,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    servico: ServicoPreferenciasNotificacao = Depends(obter_servico_preferencias),
) -> dict:
    """Remove o token (logout/expiração). Idempotente.

    A remoção é **amarrada ao dono** (resolvido pelo token): só apaga um token que
    pertença ao usuário autenticado. Sem isso, qualquer usuário poderia apagar o
    token de outro se soubesse o valor (IDOR / DoS direcionado — SEG-08)."""
    await servico.remover_dispositivo(identidade.uid, co_token_fcm)
    return {"ok": True}


@router.put("/preferencias", response_model=PreferenciasResposta)
async def definir_preferencias(
    corpo: PreferenciasRequest,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    servico: ServicoPreferenciasNotificacao = Depends(obter_servico_preferencias),
) -> PreferenciasResposta:
    """Define as preferências por categoria e devolve o estado atual."""
    atuais = await servico.definir_preferencias(identidade.uid, corpo.preferencias)
    return PreferenciasResposta(preferencias=atuais)


@router.get("/preferencias", response_model=PreferenciasResposta)
async def obter_preferencias(
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    servico: ServicoPreferenciasNotificacao = Depends(obter_servico_preferencias),
) -> PreferenciasResposta:
    """Devolve as preferências por categoria do usuário."""
    atuais = await servico.listar_preferencias(identidade.uid)
    return PreferenciasResposta(preferencias=atuais)
