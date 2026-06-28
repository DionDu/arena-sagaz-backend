"""Rotas de conta — tarefa T036.

Expõe:
- `POST /v1/conta/sessao` — cria/atualiza a conta do dono do token e devolve o
  perfil (o app chama isto logo após o login no Firebase);
- `GET  /v1/conta/perfil` — devolve o perfil do usuário atual.

Todas exigem **token válido** (`usuario_atual`) e os **cabeçalhos obrigatórios**
(`exigir_cabecalhos`). O prefixo `/v1/conta` é aplicado no `main.py`.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.conta.modelos import PerfilUsuario, SessaoRequest
from api.conta.repositorio import RepositorioUsuario
from api.conta.servico import ServicoConta
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.seguranca_firebase import IdentidadeFirebase

router = APIRouter()


def obter_servico_conta(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoConta:
    """Monta o serviço com o repositório ligado à sessão da requisição.

    É uma **dependência** própria para os testes poderem trocá-la por uma versão
    com repositório/sessão falsos (sem banco).
    """
    return ServicoConta(repo=RepositorioUsuario(sessao), sessao=sessao)


@router.post("/sessao", response_model=PerfilUsuario)
async def upsert_sessao(
    corpo: SessaoRequest,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> PerfilUsuario:
    """Cria (1º login) ou atualiza (reentrada) a conta e devolve o perfil."""
    perfil = await servico.garantir_sessao(identidade, corpo)
    # Confirma a transação (as escritas do serviço viram permanentes aqui).
    await servico.sessao.commit()
    return perfil


@router.get("/perfil", response_model=PerfilUsuario)
async def obter_perfil(
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> PerfilUsuario:
    """Devolve o perfil do usuário atual (404 se ainda não há conta)."""
    return await servico.obter_perfil(identidade)
