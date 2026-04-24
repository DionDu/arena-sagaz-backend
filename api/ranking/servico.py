from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.ranking.esquemas import EntradaRankingSaida, RankingSaida
from api.ranking.modelo import Ranking
from api.usuarios.modelo import Usuario


async def consultar_ranking(
    sessao: AsyncSession, pagina: int = 1, tamanho: int = 20
) -> RankingSaida:
    if tamanho > 100:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Tamanho máximo permitido é 100.")

    total_resultado = await sessao.execute(select(func.count()).select_from(Ranking))
    total = total_resultado.scalar_one()

    offset = (pagina - 1) * tamanho
    resultado = await sessao.execute(
        select(Ranking, Usuario)
        .join(Usuario, Ranking.usuario_id == Usuario.id)
        .order_by(Ranking.pontuacao_total.desc())
        .offset(offset)
        .limit(tamanho)
    )
    jogadores = []
    for i, (ranking, usuario) in enumerate(resultado.all()):
        jogadores.append(
            EntradaRankingSaida(
                posicao=offset + i + 1,
                apelido=usuario.apelido,
                nivel=usuario.nivel,
                pontuacao_total=ranking.pontuacao_total,
                vitorias=ranking.vitorias,
                partidas_jogadas=ranking.partidas_jogadas,
            )
        )

    return RankingSaida(total=total, pagina=pagina, tamanho=tamanho, jogadores=jogadores)
