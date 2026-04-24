from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.banco.conexao import get_sessao
from api.nucleo.dependencias import usuario_atual
from api.usuarios.esquemas import CriarUsuarioEntrada, UsuarioComTokenSaida
from api.usuarios.modelo import Usuario
from api.usuarios import servico

router = APIRouter()


@router.post("", status_code=201, response_model=UsuarioComTokenSaida)
async def criar_usuario(
    dados: CriarUsuarioEntrada,
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    return await servico.criar_usuario(sessao, dados)


@router.get("/eu")
async def perfil_atual(
    usuario: Annotated[Usuario, Depends(usuario_atual)],
    sessao: Annotated[AsyncSession, Depends(get_sessao)],
):
    from api.ranking.modelo import Ranking
    from api.trofeus.modelo import UsuarioTrofeu, Trofeu

    resultado_ranking = await sessao.execute(
        select(Ranking).where(Ranking.usuario_id == usuario.id)
    )
    ranking = resultado_ranking.scalar_one_or_none()

    resultado_trofeus = await sessao.execute(
        select(UsuarioTrofeu, Trofeu)
        .join(Trofeu, UsuarioTrofeu.trofeu_id == Trofeu.id)
        .where(UsuarioTrofeu.usuario_id == usuario.id)
    )
    trofeus = [
        {
            "codigo": trofeu.codigo,
            "nome": trofeu.nome,
            "conquistado_em": ut.conquistado_em,
        }
        for ut, trofeu in resultado_trofeus.all()
    ]

    # Calcular posição de ranking
    posicao = None
    if ranking:
        resultado_pos = await sessao.execute(
            select(Ranking).where(Ranking.pontuacao_total > ranking.pontuacao_total)
        )
        posicao = len(resultado_pos.scalars().all()) + 1

    return {
        "id": usuario.id,
        "apelido": usuario.apelido,
        "email": usuario.email,
        "nivel": usuario.nivel,
        "xp_total": usuario.xp_total,
        "email_verificado": usuario.email_verificado,
        "criado_em": usuario.criado_em,
        "ranking": {
            "posicao": posicao,
            "pontuacao_total": ranking.pontuacao_total if ranking else 0,
            "partidas_jogadas": ranking.partidas_jogadas if ranking else 0,
            "vitorias": ranking.vitorias if ranking else 0,
        },
        "trofeus": trofeus,
    }
