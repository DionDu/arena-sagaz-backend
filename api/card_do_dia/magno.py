"""Os números do Magno para o card D: dias sem perder, recorde e o placar do período.

Duas partes, separadas de propósito:

- `ler_partidas_do_magno` - a consulta (só leitura, nada de usuário: só
  jogo, datas e resultado);
- `calcular_escopos` - a conta, **pura**, testável sem banco.

═══════════════════════════════════════════════════════════════════════════
O QUE CONTA COMO "PARTIDA CONTRA O MAGNO" E COMO "DERROTA DELE"
═══════════════════════════════════════════════════════════════════════════

Os mesmos critérios de `ferramentas/consultas_sql/partidas_por_nivel_dificuldade.sql`
(na raiz), que já custaram um número errado quando faltaram (o Magno das damas
apareceu com 22% de derrotas quando o real era 1 em 125):

- só **contra a CPU** (`co_modo = 'vs_cpu'`): o Desafio do Dia começa de uma
  posição com vantagem e tem outro objetivo; o 2 jogadores não tem CPU;
- só no nível **sagaz** (o Magno);
- só **concluída**: a abandonada não tem vencedor;
- derrota dele = `co_resultado = 'venceu_j1'` (contra a CPU o humano é sempre o J1).

⚠️ A partida em que a pessoa usou o poder "voltar jogada" **conta**, inclusive
como derrota do Magno. O card fala do Magno ao público; esconder uma derrota
porque veio com ajuda tornaria o número desonesto.

As datas viram **dias de Brasília** (UTC-3, sem horário de verão desde 2019):
o card diz "há 12 dias", e a pessoa conta os dias no calendário dela.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.card_do_dia.agenda import NumerosDoMagno

#: Brasília. Um fuso fixo, e não `zoneinfo("America/Sao_Paulo")`: a imagem da
#: API é enxuta e não garante a base de fusos do sistema, e o Brasil está sem
#: horário de verão desde 2019.
BRASILIA = timezone(timedelta(hours=-3))

#: Os quatro jogos do hub, como `partida.tb001_partida.co_jogo` os escreve.
JOGOS = ("pontinhos", "velha", "damas", "quatro")

#: Cada partida contra o Magno que terminou: o jogo, quando começou, quando
#: acabou e se ele perdeu. ⛔ Nenhuma coluna de usuário.
SQL_PARTIDAS_DO_MAGNO = """
SELECT p.co_jogo,
       p.dh_inicio,
       COALESCE(p.dh_fim, p.dh_inicio) AS dh_fim,
       (p.co_resultado = 'venceu_j1') AS ic_derrota_do_magno
  FROM partida.vw001_partida AS p
 WHERE p.co_modo = 'vs_cpu'
   AND p.co_dificuldade = 'sagaz'
   AND p.co_status = 'concluida'
"""


@dataclass(frozen=True)
class PartidaDoMagno:
    """Uma partida contra o Magno, já em dias de Brasília."""

    jogo: str
    dia_inicio: date
    dia_fim: date
    derrota_do_magno: bool


def para_dia_de_brasilia(instante: datetime) -> date:
    """O dia do calendário de Brasília de um instante (com ou sem fuso).

    Um `datetime` sem fuso, vindo do banco, é tratado como UTC: é como a API
    grava todos os instantes.
    """
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(BRASILIA).date()


async def ler_partidas_do_magno(sessao: AsyncSession) -> list[PartidaDoMagno]:
    """Lê do banco as partidas contra o Magno que terminaram.

    São poucas (o Magno é o nível mais difícil, e só ele entra), e a página que
    as usa é aberta por uma pessoa, quatro vezes por semana: não compensa
    agregar no SQL o que a conta em Python faz de forma legível.
    """
    resultado = await sessao.execute(text(SQL_PARTIDAS_DO_MAGNO))
    return [
        PartidaDoMagno(
            jogo=linha["co_jogo"],
            dia_inicio=para_dia_de_brasilia(linha["dh_inicio"]),
            dia_fim=para_dia_de_brasilia(linha["dh_fim"]),
            derrota_do_magno=bool(linha["ic_derrota_do_magno"]),
        )
        for linha in resultado.mappings().all()
    ]


def periodo_do_placar(dia: date) -> tuple[date, date, str]:
    """O período do placar (D2): `(primeiro dia, último dia, rótulo)`.

    O mês corrente até o dia de publicação. Na primeira quinzena o mês ainda tem
    poucas partidas, e o placar sairia pequeno: aí vale o **mês anterior
    inteiro**. O rótulo é o que o card escreve ("Em novembro").
    """
    meses = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
        "agosto", "setembro", "outubro", "novembro", "dezembro",
    )
    if dia.day >= 15:
        inicio = dia.replace(day=1)
        return inicio, dia, f"Em {meses[dia.month - 1]}"
    # O último dia do mês anterior é a véspera do dia 1º deste mês.
    fim = dia.replace(day=1) - timedelta(days=1)
    return fim.replace(day=1), fim, f"Em {meses[fim.month - 1]}"


def _numeros(
    partidas: list[PartidaDoMagno], jogo: Optional[str], dia: date, inicio: date, fim: date
) -> Optional[NumerosDoMagno]:
    """Os números de um escopo, ou `None` se o Magno nunca jogou nele.

    - **dias sem perder**: do dia da última derrota (ou, se ele nunca perdeu, do
      dia da primeira partida) até o dia de publicação;
    - **recorde**: o maior intervalo, em dias, entre duas derrotas seguidas,
      contando também o trecho da primeira partida até a primeira derrota e o
      trecho atual (o recorde nunca é menor que a sequência de agora);
    - **placar do período**: partidas e derrotas que TERMINARAM no período.
    """
    # Só o que aconteceu até o dia de publicação: um número "do futuro" (uma
    # partida das 22h, depois do post das 21h) mudaria o card de um dia passado.
    doescopo = [
        p for p in partidas if (jogo is None or p.jogo == jogo) and p.dia_fim <= dia
    ]
    if not doescopo:
        return None
    primeira = min(p.dia_inicio for p in doescopo)
    derrotas = sorted(p.dia_fim for p in doescopo if p.derrota_do_magno)

    # Os marcos são: a primeira partida, cada derrota, e o dia de publicação. O
    # recorde é o maior salto entre dois marcos vizinhos. `zip(a, a[1:])` forma os
    # pares vizinhos: (m0, m1), (m1, m2)...
    marcos = [primeira, *derrotas, dia]
    recorde = max((b - a).days for a, b in zip(marcos, marcos[1:]))
    sem_perder = (dia - (derrotas[-1] if derrotas else primeira)).days

    no_periodo = [p for p in doescopo if inicio <= p.dia_fim <= fim]
    return NumerosDoMagno(
        jogo=jogo,
        dias_sem_perder=sem_perder,
        recorde_dias=recorde,
        partidas_no_periodo=len(no_periodo),
        derrotas_no_periodo=sum(1 for p in no_periodo if p.derrota_do_magno),
    )


def calcular_escopos(
    partidas: list[PartidaDoMagno], dia: date
) -> tuple[list[NumerosDoMagno], str]:
    """Os números dos quatro jogos juntos e de cada jogo, e o rótulo do período.

    Um jogo em que o Magno nunca jogou fica de fora (não há o que contar).
    """
    inicio, fim, rotulo = periodo_do_placar(dia)
    escopos = [_numeros(partidas, jogo, dia, inicio, fim) for jogo in (None, *JOGOS)]
    return [n for n in escopos if n is not None], rotulo
