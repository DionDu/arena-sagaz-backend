from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.configuracao import configuracoes
from api.nucleo.excecoes import ErroNaoAutorizado
from api.nucleo.seguranca import (
    criar_hash_token,
    criar_token_acesso,
    gerar_refresh_token,
    verificar_senha,
)
from api.usuarios.modelo import TokenRefresh, Usuario
from api.auth.esquemas import TokenAcessoSaida, TokenSaida
from api.nucleo.log import obter_logger

log = obter_logger("api.auth.servico")


async def autenticar(sessao: AsyncSession, email: str, senha: str) -> TokenSaida:
    resultado = await sessao.execute(
        select(Usuario).where(Usuario.email == email)
    )
    usuario = resultado.scalar_one_or_none()

    if not usuario or not verificar_senha(senha, usuario.senha_hash):
        log.warning("Tentativa de login com credenciais inválidas: %s", email)
        raise ErroNaoAutorizado("E-mail ou senha incorretos.", "CREDENCIAIS_INVALIDAS")

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
    log.info("Login bem-sucedido: %s (%s)", usuario.apelido, usuario.id)

    return TokenSaida(
        acesso_token=token_acesso,
        refresh_token=refresh,
        expira_em=expira_em,
    )


async def renovar_token(sessao: AsyncSession, refresh_token: str) -> TokenAcessoSaida:
    token_hash = criar_hash_token(refresh_token)
    resultado = await sessao.execute(
        select(TokenRefresh).where(TokenRefresh.token_hash == token_hash)
    )
    token = resultado.scalar_one_or_none()

    if not token or token.revogado or token.expira_em < datetime.now(timezone.utc):
        log.warning("Tentativa de refresh com token inválido/expirado/revogado")
        raise ErroNaoAutorizado(
            "Token de renovação inválido ou expirado.", "REFRESH_TOKEN_INVALIDO"
        )

    novo_token, expira_em = criar_token_acesso({"sub": token.usuario_id})
    return TokenAcessoSaida(acesso_token=novo_token, expira_em=expira_em)


async def revogar_token(sessao: AsyncSession, refresh_token: str) -> None:
    token_hash = criar_hash_token(refresh_token)
    resultado = await sessao.execute(
        select(TokenRefresh).where(TokenRefresh.token_hash == token_hash)
    )
    token = resultado.scalar_one_or_none()
    if token:
        token.revogado = True
        await sessao.commit()
