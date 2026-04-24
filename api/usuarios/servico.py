from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.nucleo.excecoes import ErroConflito
from api.nucleo.seguranca import (
    criar_hash_token,
    criar_token_acesso,
    gerar_hash_senha,
    gerar_refresh_token,
)
from api.configuracao import configuracoes
from api.usuarios.modelo import TokenRefresh, Usuario
from api.usuarios.esquemas import CriarUsuarioEntrada, UsuarioComTokenSaida
from api.nucleo.log import obter_logger

log = obter_logger("api.usuarios.servico")


async def criar_usuario(sessao: AsyncSession, dados: CriarUsuarioEntrada) -> UsuarioComTokenSaida:
    resultado_email = await sessao.execute(
        select(Usuario).where(Usuario.email == dados.email)
    )
    if resultado_email.scalar_one_or_none():
        log.warning("Tentativa de cadastro com e-mail duplicado: %s", dados.email)
        raise ErroConflito("E-mail já cadastrado.", "EMAIL_DUPLICADO")

    resultado_apelido = await sessao.execute(
        select(Usuario).where(Usuario.apelido == dados.apelido)
    )
    if resultado_apelido.scalar_one_or_none():
        log.warning("Tentativa de cadastro com apelido duplicado: %s", dados.apelido)
        raise ErroConflito("Apelido já em uso.", "APELIDO_DUPLICADO")

    usuario = Usuario(
        apelido=dados.apelido,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
    )
    sessao.add(usuario)
    await sessao.flush()

    # Criar entrada de ranking inicial
    from api.ranking.modelo import Ranking
    ranking = Ranking(usuario_id=usuario.id)
    sessao.add(ranking)

    token_acesso, expira_em = criar_token_acesso({"sub": usuario.id})
    refresh = gerar_refresh_token()
    refresh_hash = criar_hash_token(refresh)
    expira_refresh = datetime.now(timezone.utc) + timedelta(
        days=configuracoes.REFRESH_TOKEN_EXPIRACAO_DIAS
    )
    token_refresh = TokenRefresh(
        usuario_id=usuario.id,
        token_hash=refresh_hash,
        expira_em=expira_refresh,
    )
    sessao.add(token_refresh)
    await sessao.commit()
    await sessao.refresh(usuario)
    log.info("Usuário criado: %s (%s)", usuario.apelido, usuario.id)

    return UsuarioComTokenSaida(
        id=usuario.id,
        apelido=usuario.apelido,
        email=usuario.email,
        nivel=usuario.nivel,
        xp_total=usuario.xp_total,
        criado_em=usuario.criado_em,
        acesso_token=token_acesso,
        refresh_token=refresh,
        expira_em=expira_em,
    )
