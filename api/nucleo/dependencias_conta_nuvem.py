"""Dependência compartilhada da fase Conta na Nuvem (spec 006) — tarefa T017.

Os endpoints de sincronização, log de partidas e ranking precisam, além dos
cabeçalhos obrigatórios e do token válido (já cobertos pela fundação 005), do
``id_usuario`` INTERNO do dono — que o cliente NÃO conhece (o app só recebe o
``co_usuario`` público). Esta dependência fecha essa lacuna: resolve o usuário
do banco a partir do uid do Firebase (``co_identidade_externa``) e entrega tudo
o que as rotas da 006 costumam usar em um único objeto.

NOTA (desvio de caminho): a tarefa T017 sugeria ``api/comum/``, mas o pacote
compartilhado do backend já é ``api/nucleo/`` (banco, dependências, segurança).
Para não fragmentar o "comum" em duas pastas, colocamos aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.conta.repositorio import RepositorioUsuario
from api.nucleo.banco import obter_sessao
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual,
)
from api.nucleo.excecoes import ErroNaoEncontrado
from api.nucleo.seguranca_firebase import IdentidadeFirebase


@dataclass(frozen=True)
class UsuarioAutenticado:
    """Dono autenticado de uma requisição da 006, já resolvido no banco.

    Reúne o ``id_usuario`` interno (UUID) e o código público, além do contexto de
    cabeçalhos — o que as rotas de sync/partidas/ranking precisam para gravar o log
    e incrementar a progressão do usuário certo.

    NÃO existe aqui uma "âncora anônima": o ``id_usuario`` JÁ é o pseudônimo. A
    exclusão de conta **anonimiza** a linha (apaga a PII) em vez de deletá-la, então
    a chave continua válida e sem dado pessoal atrás dela. Ver a migração
    ``0007_drop_co_anonimo``.
    """

    id_usuario: str
    co_usuario: str
    dt_nascimento: Optional[date]
    contexto: ContextoRequisicao


async def usuario_autenticado(
    identidade: IdentidadeFirebase = Depends(usuario_atual),
    contexto: ContextoRequisicao = Depends(exigir_cabecalhos),
    sessao: AsyncSession = Depends(obter_sessao),
) -> UsuarioAutenticado:
    """Resolve o dono da requisição (id interno) a partir do token + cabeçalhos.

    Fluxo:
      1. ``usuario_atual`` já validou o token e nos deu o uid do Firebase.
      2. ``exigir_cabecalhos`` já validou ``X-App-Version``/``X-Platform``/idioma.
      3. Aqui buscamos a linha do usuário pelo ``co_identidade_externa`` (= uid).

    Lança 404 ``conta_nao_provisionada`` se o token é válido mas ainda não existe
    conta no nosso banco (o app precisa chamar ``POST /v1/conta/sessao`` antes).

    OBS: a MESMA sessão (``obter_sessao``) é reaproveitada pela rota (o FastAPI
    cacheia a dependência por requisição), então a rota pode gravar e dar commit.
    """
    repo = RepositorioUsuario(sessao)
    linha = await repo.buscar_por_identidade_externa(identidade.uid)
    if linha is None:
        raise ErroNaoEncontrado(
            "Conta ainda não provisionada. Faça a sessão primeiro.",
            "conta_nao_provisionada",
        )

    return UsuarioAutenticado(
        id_usuario=linha["id_usuario"],
        co_usuario=linha["co_usuario"],
        dt_nascimento=linha.get("dt_nascimento"),
        contexto=contexto,
    )
