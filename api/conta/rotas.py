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

from api.conta.modelos import (
    AceiteLegalRequest,
    AceiteLegalResposta,
    AtualizarPerfilRequest,
    ConsentimentoRequest,
    ConsentimentoResposta,
    ExclusaoContaResposta,
    PerfilUsuario,
    SessaoRequest,
)
from api.conta.repositorio import RepositorioUsuario
from api.conta.servico import ServicoConta
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.seguranca_firebase import IdentidadeFirebase, obter_admin_usuarios

router = APIRouter()


def obter_servico_conta(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoConta:
    """Monta o serviço com o repositório ligado à sessão da requisição.

    É uma **dependência** própria para os testes poderem trocá-la por uma versão
    com repositório/sessão falsos (sem banco). Injeta o administrador de usuários
    do Firebase (usado na exclusão de conta — US4).
    """
    return ServicoConta(
        repo=RepositorioUsuario(sessao),
        sessao=sessao,
        admin=obter_admin_usuarios(),
    )


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


@router.post("/aceite-legal", response_model=AceiteLegalResposta)
async def registrar_aceite(
    corpo: AceiteLegalRequest,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> AceiteLegalResposta:
    """Registra o aceite de um documento legal (termos/privacidade) — US3."""
    resposta = await servico.registrar_aceite(identidade, corpo)
    await servico.sessao.commit()
    return resposta


@router.put("/consentimento", response_model=ConsentimentoResposta)
async def definir_consentimento(
    corpo: ConsentimentoRequest,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> ConsentimentoResposta:
    """Define o consentimento de rastreamento/marketing — US3 (upsert)."""
    resposta = await servico.definir_consentimento(identidade, corpo)
    await servico.sessao.commit()
    return resposta


@router.patch("/perfil", response_model=PerfilUsuario)
async def atualizar_perfil(
    corpo: AtualizarPerfilRequest,
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> PerfilUsuario:
    """Edita nome de exibição e/ou idioma do usuário atual — US4."""
    perfil = await servico.atualizar_perfil_usuario(identidade, corpo)
    await servico.sessao.commit()
    return perfil


@router.delete("", response_model=ExclusaoContaResposta)
async def excluir_conta(
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    servico: ServicoConta = Depends(obter_servico_conta),
) -> ExclusaoContaResposta:
    """Exclui (anonimiza) a conta do usuário atual — US4.

    Remove os dados pessoais da nossa base e apaga o usuário no Firebase
    (best-effort). O caminho é o próprio prefixo `/v1/conta` (path vazio aqui).
    """
    resposta = await servico.excluir_conta(identidade)
    await servico.sessao.commit()
    return resposta
