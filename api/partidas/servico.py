from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.configuracao import configuracoes
from api.partidas.esquemas import PartidaSaida, SincronizarPartidaEntrada
from api.partidas.modelo import Partida
from api.ranking.modelo import Ranking
from api.usuarios.modelo import Usuario
from api.nucleo.log import obter_logger

log = obter_logger("api.partidas.servico")

_MULTIPLICADORES = {"facil": 1.0, "normal": 1.5, "sagaz": 2.0}


def _calcular_xp(
    caixas_jogador: int,
    resultado: str,
    dificuldade: str | None,
    xp_bonus_vitoria: int,
) -> int:
    xp_base = caixas_jogador
    bonus = xp_bonus_vitoria if resultado == "vitoria" else 0
    mult = _MULTIPLICADORES.get(dificuldade or "", 1.0)
    return int((xp_base + bonus) * mult)


async def sincronizar_partida(
    sessao: AsyncSession,
    usuario: Usuario,
    dados: SincronizarPartidaEntrada,
) -> PartidaSaida:
    xp_obtido = _calcular_xp(
        dados.caixas_jogador,
        dados.resultado,
        dados.dificuldade,
        configuracoes.XP_BONUS_VITORIA,
    )
    pontuacao_obtida = xp_obtido
    nivel_anterior = usuario.nivel

    partida = Partida(
        usuario_id=usuario.id,
        modo_jogo=dados.modo_jogo,
        tamanho_tabuleiro=dados.tamanho_tabuleiro,
        dificuldade=dados.dificuldade,
        caixas_jogador=dados.caixas_jogador,
        caixas_adversario=dados.caixas_adversario,
        resultado=dados.resultado,
        xp_obtido=xp_obtido,
        pontuacao_obtida=pontuacao_obtida,
    )
    sessao.add(partida)

    usuario.xp_total += xp_obtido
    usuario.nivel = usuario.xp_total // 100 + 1

    resultado_ranking = await sessao.execute(
        select(Ranking).where(Ranking.usuario_id == usuario.id)
    )
    ranking = resultado_ranking.scalar_one_or_none()
    if ranking is None:
        ranking = Ranking(usuario_id=usuario.id)
        sessao.add(ranking)

    ranking.pontuacao_total += pontuacao_obtida
    ranking.partidas_jogadas += 1
    if dados.resultado == "vitoria":
        ranking.vitorias += 1

    await sessao.commit()
    await sessao.refresh(partida)

    resultado_pos = await sessao.execute(
        select(Ranking).where(Ranking.pontuacao_total > ranking.pontuacao_total)
    )
    posicao = len(resultado_pos.scalars().all()) + 1

    log.info(
        "Partida sincronizada: usuario=%s xp=%d nivel=%d->%d posicao=%d",
        usuario.id, xp_obtido, nivel_anterior, usuario.nivel, posicao,
    )
    return PartidaSaida(
        id=partida.id,
        xp_obtido=xp_obtido,
        pontuacao_obtida=pontuacao_obtida,
        nivel_anterior=nivel_anterior,
        nivel_atual=usuario.nivel,
        xp_total=usuario.xp_total,
        posicao_ranking=posicao,
        trofeus_conquistados=[],
    )
