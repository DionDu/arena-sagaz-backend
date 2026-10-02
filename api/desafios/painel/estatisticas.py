"""COMO FOI O DIA: o engajamento, a dificuldade real, o quadro e o raio-x (02/10/2026).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Pedido do dono, ao transformar a curadoria em painel de GESTAO:

> *"Seria interessante mostrar tambem dados do desafio ja cumprido (quadro de
> usuarios, seus raio-x tambem, etc), alem de estatisticas gerenciaveis que me
> permitam saber o engajamento dos usuarios naquele desafio, dificuldade,
> tentativas etc."*

⚠️ **A regua mede a dificuldade ANTES** (os mascotes jogando); estas contas
medem **DEPOIS**, com gente. E a comparacao das duas que diz se a calibracao
acerta — um desafio que a regua chamou de 75% e que 20% das pessoas resolveram
e informacao que nenhuma outra tela do sistema da.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE MODULO REAPROVEITA, E O QUE NAO
═══════════════════════════════════════════════════════════════════════════

  · **Reaproveita** de `api/desafios/quadro.py` as consultas de lances
    (`SQL_LANCES`) e do extrato de XP (`SQL_EXTRATO`): sao as mesmas que montam
    o Raio-X no aplicativo, e uma segunda versao aqui divergiria dela em
    silencio na primeira mudanca.
  · ⛔ **Nao reaproveita** a ordem publica do quadro (`SQL_LINHAS_DE_GENTE`):
    aquela esconde quem pediu para nao aparecer no placar, e o painel de gestao
    precisa ver todo mundo — com a marca de quem esta oculto, para o dono nao
    confundir o que ele ve com o que o aplicativo mostra.

⛔ **Nenhum numero de XP e calculado aqui.** O painel le o que foi gravado
(`nu_xp`, `vr_xp`); a regra de credito mora em `api/desafios/credito_do_dia.py`
e esta sendo revista noutra frente — recalcular aqui seria criar uma segunda
regra justamente quando a primeira muda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    VW_DESAFIO_DIA,
    VW_PODER_CONSUMIDO,
    VW_REACAO,
    VW_RESOLUCAO,
    VW_TENTATIVA,
)
from api.desafios.modelos_producao import VW_DESAFIO
from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO, SQL_EXTRATO, SQL_LANCES

#: A VIEW das partidas — para contar quem jogou QUALQUER coisa naquele dia.
VW_PARTIDA = "partida.vw001_partida"


# ═══════════════════════════════════════════════════════════════════════════
# Os retratos
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class FatiaDeTentativas:
    """Quantas pessoas fizeram N tentativas, separadas por terem resolvido ou nao."""

    qt_tentativas: int
    resolveu: bool
    qt_pessoas: int


@dataclass(frozen=True, slots=True)
class UsoDePoder:
    """Quanto um poder (a dica, hoje) foi usado no dia."""

    co_tipo_poder: str
    qt_usos: int
    qt_pessoas: int


@dataclass(frozen=True, slots=True)
class ContagemDeReacao:
    """Quantas reacoes de um tipo o quadro do dia recebeu."""

    co_tipo_reacao: str
    co_emoji: str
    qt: int


@dataclass(frozen=True, slots=True)
class ResumoDoDia:
    """Os numeros de gestao de um dia jogado.

    ⚠️ **Toda taxa sai com o denominador ao lado na tela** (licao registrada no
    projeto: *"numero cru nao e relatorio"*). "50% resolveram" de duas pessoas e
    de duzentas sao noticias diferentes.
    """

    qt_tentativas: int = 0
    qt_pessoas: int = 0
    qt_resolveram: int = 0
    #: Mediana, e nao media: uma pessoa que largou o aparelho aberto por uma
    #: hora puxaria a media para um numero que nao descreve ninguem.
    md_tempo_resolucao_ms: Optional[float] = None
    md_tempo_tentativa_ms: Optional[float] = None
    #: Em que tentativa, em media, quem resolveu resolveu (1 = de primeira).
    md_tentativa_que_resolveu: Optional[float] = None
    xp_medio: Optional[float] = None
    xp_maximo: Optional[int] = None
    xp_minimo: Optional[int] = None
    #: Quem jogou QUALQUER partida no dia (UTC) — a base do engajamento.
    qt_ativos_no_dia: int = 0
    distribuicao: tuple[FatiaDeTentativas, ...] = ()
    poderes: tuple[UsoDePoder, ...] = ()
    reacoes: tuple[ContagemDeReacao, ...] = ()
    auditoria: dict[str, int] = field(default_factory=dict)

    @property
    def taxa_de_resolucao(self) -> Optional[float]:
        """Das pessoas que tentaram, quantas resolveram."""
        return self.qt_resolveram / self.qt_pessoas if self.qt_pessoas else None

    @property
    def engajamento(self) -> Optional[float]:
        """De quem jogou alguma coisa no dia, quantos tentaram o desafio.

        ⚠️ E a pergunta *"o desafio esta chamando gente?"*. Ele mede o convite
        (card na Home, notificacao), e nao a dificuldade.
        """
        return self.qt_pessoas / self.qt_ativos_no_dia if self.qt_ativos_no_dia else None

    @property
    def qt_desistiram(self) -> int:
        """Tentaram e nao resolveram."""
        return self.qt_pessoas - self.qt_resolveram

    @property
    def tentativas_por_pessoa(self) -> Optional[float]:
        """Media de tentativas por pessoa que tentou."""
        return self.qt_tentativas / self.qt_pessoas if self.qt_pessoas else None


@dataclass(frozen=True, slots=True)
class LinhaDoQuadro:
    """Uma pessoa que resolveu, com o que o painel precisa para comparar."""

    posicao: int
    id_resolucao: UUID
    id_tentativa: UUID
    id_usuario: UUID
    co_usuario: Optional[str]
    no_exibicao: Optional[str]
    nu_xp: int
    nu_tempo_ms: int
    dh_resolucao: datetime
    co_auditoria: str
    nu_sequencia: int
    qt_tentativas: int
    qt_dicas: int
    qt_reacoes: int
    #: ⚠️ `False` = a pessoa nao aparece no quadro do APLICATIVO (pediu para
    #: sair do placar, ou nao declarou idade). O painel a mostra, marcada.
    ic_publico: bool


@dataclass(frozen=True, slots=True)
class QuemNaoResolveu:
    """Uma pessoa que tentou e nao resolveu — o outro lado da taxa."""

    id_usuario: UUID
    co_usuario: Optional[str]
    no_exibicao: Optional[str]
    qt_tentativas: int
    nu_tempo_total_ms: int
    qt_dicas: int
    id_ultima_tentativa: UUID


@dataclass(frozen=True, slots=True)
class RaioX:
    """Uma tentativa de uma pessoa, inteira: lances, dicas e (se resolveu) o XP.

    ⚠️ **Por tentativa, e nao por resolucao**: assim o painel abre tambem a
    partida de quem NAO resolveu — que e onde se ve se o desafio confunde.
    """

    id_tentativa: UUID
    id_usuario: UUID
    co_usuario: Optional[str]
    no_exibicao: Optional[str]
    nu_sequencia: int
    ic_resolveu: bool
    nu_tempo_ms: int
    dh_inicio: Optional[datetime]
    co_formato_posicao: str
    js_posicao_inicial: dict[str, Any]
    #: A variante do desafio: no Pontinhos, o TAMANHO do tabuleiro, sem o qual
    #: o desenho deduziria o tamanho dos tracos e podia cortar uma fileira.
    co_variante: Optional[str] = None
    id_resolucao: Optional[UUID] = None
    nu_xp: Optional[int] = None
    nu_lance_cumpre_desafio: Optional[int] = None
    co_auditoria: Optional[str] = None
    de_auditoria: Optional[str] = None
    lances: tuple[dict[str, Any], ...] = ()
    extrato: tuple[dict[str, Any], ...] = ()
    poderes: tuple[dict[str, Any], ...] = ()


# ═══════════════════════════════════════════════════════════════════════════
# O SQL — sempre pelas VIEWs
# ═══════════════════════════════════════════════════════════════════════════

#: As tentativas do dia, num agregado so.
_SQL_RESUMO_TENTATIVAS = f"""
SELECT COUNT(*)                                              AS qt_tentativas,
       COUNT(DISTINCT id_usuario)                            AS qt_pessoas,
       COUNT(DISTINCT id_usuario) FILTER (WHERE ic_resolveu) AS qt_resolveram,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY nu_tempo_ms)
                                                             AS md_tempo_tentativa_ms
  FROM {VW_TENTATIVA}
 WHERE id_desafio_dia = :id_desafio_dia
"""

#: As resolucoes do dia: tempo, XP, em que tentativa e a auditoria.
#:
#: ⚠️ A tentativa que resolveu vem pelo `JOIN` com a tentativa da propria
#: resolucao (`id_tentativa`), e nao por `ic_resolveu`: quem resolve e continua
#: jogando outra vez teria duas tentativas "resolvidas", e a media contaria a
#: segunda.
_SQL_RESUMO_RESOLUCOES = f"""
SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY r.nu_tempo_ms) AS md_tempo_resolucao_ms,
       AVG(t.nu_sequencia)                                         AS md_tentativa_que_resolveu,
       AVG(r.nu_xp)                                                AS xp_medio,
       MAX(r.nu_xp)                                                AS xp_maximo,
       MIN(r.nu_xp)                                                AS xp_minimo
  FROM {VW_RESOLUCAO} r
  JOIN {VW_TENTATIVA} t ON t.id_tentativa = r.id_tentativa
 WHERE r.id_desafio_dia = :id_desafio_dia
"""

#: A auditoria das resolucoes do dia (pendente · confere · divergente).
_SQL_AUDITORIA_DO_DIA = f"""
SELECT co_auditoria, COUNT(*) AS qt
  FROM {VW_RESOLUCAO}
 WHERE id_desafio_dia = :id_desafio_dia
 GROUP BY co_auditoria
"""

#: Quantas pessoas fizeram 1, 2, 3... tentativas, e se resolveram.
_SQL_DISTRIBUICAO = f"""
SELECT qt_tentativas, resolveu, COUNT(*) AS qt_pessoas
  FROM (SELECT id_usuario,
               COUNT(*)          AS qt_tentativas,
               bool_or(ic_resolveu) AS resolveu
          FROM {VW_TENTATIVA}
         WHERE id_desafio_dia = :id_desafio_dia
         GROUP BY id_usuario) por_pessoa
 GROUP BY qt_tentativas, resolveu
 ORDER BY qt_tentativas, resolveu DESC
"""

#: Os poderes (a dica) usados no dia.
_SQL_PODERES_DO_DIA = f"""
SELECT p.co_tipo_poder,
       COUNT(*)                   AS qt_usos,
       COUNT(DISTINCT t.id_usuario) AS qt_pessoas
  FROM {VW_PODER_CONSUMIDO} p
  JOIN {VW_TENTATIVA} t ON t.id_tentativa = p.id_tentativa
 WHERE t.id_desafio_dia = :id_desafio_dia
 GROUP BY p.co_tipo_poder
 ORDER BY qt_usos DESC
"""

#: As reacoes que o quadro do dia recebeu, por tipo.
_SQL_REACOES_DO_DIA = f"""
SELECT re.co_tipo_reacao, re.co_emoji, COUNT(*) AS qt
  FROM {VW_REACAO} re
  JOIN {VW_RESOLUCAO} r ON r.id_resolucao = re.id_resolucao
 WHERE r.id_desafio_dia = :id_desafio_dia
 GROUP BY re.co_tipo_reacao, re.co_emoji
 ORDER BY qt DESC
"""

#: Quem jogou qualquer partida naquele dia (UTC) — a base do engajamento.
#:
#: ⚠️ **Intervalo semiaberto `[inicio, fim)`**, e nao `dh_inicio::date = :dia`:
#: o cast impede o uso do indice e, pior, converte no fuso da SESSAO do banco —
#: que nao e garantidamente UTC.
_SQL_ATIVOS_NO_DIA = f"""
SELECT COUNT(DISTINCT id_usuario) AS qt
  FROM {VW_PARTIDA}
 WHERE dh_inicio >= :dh_inicio
   AND dh_inicio <  :dh_fim
"""

#: O quadro do dia, com TODO mundo (inclusive quem esta oculto no aplicativo).
#:
#: ⚠️ A ORDEM e a do aplicativo (`quadro.SQL_LINHAS_DE_GENTE`): mais XP, depois
#: menos tempo, depois quem chegou primeiro. Ordem diferente faria o dono ver
#: um primeiro lugar que nao e o da tela de ninguem.
_SQL_QUADRO_COMPLETO = f"""
SELECT r.id_resolucao,
       r.id_tentativa,
       r.id_usuario,
       u.co_usuario,
       u.no_exibicao,
       r.nu_xp,
       r.nu_tempo_ms,
       r.dh_resolucao,
       r.co_auditoria,
       t.nu_sequencia,
       (SELECT COUNT(*)
          FROM {VW_TENTATIVA} t2
         WHERE t2.id_desafio_dia = r.id_desafio_dia
           AND t2.id_usuario = r.id_usuario)              AS qt_tentativas,
       (SELECT COUNT(*)
          FROM {VW_PODER_CONSUMIDO} p
          JOIN {VW_TENTATIVA} t3 ON t3.id_tentativa = p.id_tentativa
         WHERE t3.id_desafio_dia = r.id_desafio_dia
           AND t3.id_usuario = r.id_usuario)              AS qt_dicas,
       (SELECT COUNT(*)
          FROM {VW_REACAO} re
         WHERE re.id_resolucao = r.id_resolucao)          AS qt_reacoes,
       {CLAUSULA_APARECE_EM_PUBLICO}                      AS ic_publico
  FROM {VW_RESOLUCAO} r
  JOIN {VW_TENTATIVA} t
    ON t.id_tentativa = r.id_tentativa
  JOIN conta.tb001_usuario u
    ON u.id_usuario = r.id_usuario
  LEFT JOIN progressao.tb001_progressao_usuario g
    ON g.id_usuario = r.id_usuario
 WHERE r.id_desafio_dia = :id_desafio_dia
 ORDER BY r.nu_xp DESC, r.nu_tempo_ms ASC, r.dh_resolucao ASC
"""

#: Quem tentou e nao resolveu, com a ultima tentativa para abrir o raio-x.
#:
#: ⚠️ `(array_agg(... ORDER BY ...))[1]` pega o primeiro elemento de um vetor
#: ordenado: e o jeito do Postgres de dizer "a tentativa de maior sequencia"
#: dentro de um `GROUP BY`, sem uma segunda consulta por pessoa.
_SQL_NAO_RESOLVERAM = f"""
SELECT t.id_usuario,
       u.co_usuario,
       u.no_exibicao,
       COUNT(*)                                             AS qt_tentativas,
       COALESCE(SUM(t.nu_tempo_ms), 0)                       AS nu_tempo_total_ms,
       (SELECT COUNT(*)
          FROM {VW_PODER_CONSUMIDO} p
          JOIN {VW_TENTATIVA} t2 ON t2.id_tentativa = p.id_tentativa
         WHERE t2.id_desafio_dia = :id_desafio_dia
           AND t2.id_usuario = t.id_usuario)                AS qt_dicas,
       (array_agg(t.id_tentativa ORDER BY t.nu_sequencia DESC))[1]
                                                            AS id_ultima_tentativa
  FROM {VW_TENTATIVA} t
  JOIN conta.tb001_usuario u
    ON u.id_usuario = t.id_usuario
 WHERE t.id_desafio_dia = :id_desafio_dia
 GROUP BY t.id_usuario, u.co_usuario, u.no_exibicao
HAVING NOT bool_or(t.ic_resolveu)
 ORDER BY qt_tentativas DESC
"""

#: O cabecalho do raio-x: a tentativa, a resolucao (se houve) e o desafio.
_SQL_RAIO_X = f"""
SELECT t.id_tentativa,
       t.id_usuario,
       t.id_partida,
       t.id_desafio_dia,
       t.nu_sequencia,
       t.ic_resolveu,
       t.nu_tempo_ms,
       t.dh_inicio,
       r.id_resolucao,
       r.nu_xp,
       r.nu_lance_cumpre_desafio,
       r.co_auditoria,
       r.de_auditoria,
       u.co_usuario,
       u.no_exibicao,
       d.co_formato_posicao,
       d.js_posicao_inicial,
       d.co_variante
  FROM {VW_TENTATIVA} t
  LEFT JOIN {VW_RESOLUCAO} r
    ON r.id_tentativa = t.id_tentativa
  JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio_dia = t.id_desafio_dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
  JOIN conta.tb001_usuario u
    ON u.id_usuario = t.id_usuario
 WHERE t.id_tentativa = :id_tentativa
"""

#: Os poderes usados numa tentativa, na ordem em que foram usados.
_SQL_PODERES_DA_TENTATIVA = f"""
SELECT co_tipo_poder, nu_grau, dh_consumo
  FROM {VW_PODER_CONSUMIDO}
 WHERE id_tentativa = :id_tentativa
 ORDER BY dh_consumo
"""


def _limites_do_dia_utc(dt_dia: date) -> tuple[datetime, datetime]:
    """`[00:00 UTC do dia, 00:00 UTC do dia seguinte)`."""
    inicio = datetime.combine(dt_dia, time.min, tzinfo=timezone.utc)
    return inicio, inicio + timedelta(days=1)


def _numero(valor: Any) -> Optional[float]:
    """`Decimal`/`int`/`None` do driver → `float` ou `None`."""
    return float(valor) if valor is not None else None


class EstatisticasDoDia:
    """As leituras de gestao de um dia. Somente leitura — nao ha `commit` aqui."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def _linhas(self, sql: str, parametros: dict[str, Any]) -> list[dict[str, Any]]:
        resultado = await self.sessao.execute(text(sql), parametros)
        return [dict(m) for m in resultado.mappings().all()]

    async def resumo(self, *, id_desafio_dia: UUID, dt_dia: date) -> ResumoDoDia:
        """Os numeros do dia, em sete consultas pequenas e agregadas."""
        chave = {"id_desafio_dia": id_desafio_dia}
        tent = (await self._linhas(_SQL_RESUMO_TENTATIVAS, chave) or [{}])[0]
        res = (await self._linhas(_SQL_RESUMO_RESOLUCOES, chave) or [{}])[0]
        inicio, fim = _limites_do_dia_utc(dt_dia)
        ativos = (
            await self._linhas(_SQL_ATIVOS_NO_DIA, {"dh_inicio": inicio, "dh_fim": fim})
            or [{}]
        )[0]
        auditoria = {
            linha["co_auditoria"]: int(linha["qt"])
            for linha in await self._linhas(_SQL_AUDITORIA_DO_DIA, chave)
        }
        return ResumoDoDia(
            qt_tentativas=int(tent.get("qt_tentativas") or 0),
            qt_pessoas=int(tent.get("qt_pessoas") or 0),
            qt_resolveram=int(tent.get("qt_resolveram") or 0),
            md_tempo_tentativa_ms=_numero(tent.get("md_tempo_tentativa_ms")),
            md_tempo_resolucao_ms=_numero(res.get("md_tempo_resolucao_ms")),
            md_tentativa_que_resolveu=_numero(res.get("md_tentativa_que_resolveu")),
            xp_medio=_numero(res.get("xp_medio")),
            xp_maximo=res.get("xp_maximo"),
            xp_minimo=res.get("xp_minimo"),
            qt_ativos_no_dia=int(ativos.get("qt") or 0),
            distribuicao=tuple(
                FatiaDeTentativas(
                    qt_tentativas=int(l["qt_tentativas"]),
                    resolveu=bool(l["resolveu"]),
                    qt_pessoas=int(l["qt_pessoas"]),
                )
                for l in await self._linhas(_SQL_DISTRIBUICAO, chave)
            ),
            poderes=tuple(
                UsoDePoder(
                    co_tipo_poder=l["co_tipo_poder"],
                    qt_usos=int(l["qt_usos"]),
                    qt_pessoas=int(l["qt_pessoas"]),
                )
                for l in await self._linhas(_SQL_PODERES_DO_DIA, chave)
            ),
            reacoes=tuple(
                ContagemDeReacao(
                    co_tipo_reacao=l["co_tipo_reacao"],
                    co_emoji=l["co_emoji"],
                    qt=int(l["qt"]),
                )
                for l in await self._linhas(_SQL_REACOES_DO_DIA, chave)
            ),
            auditoria=auditoria,
        )

    async def quadro(self, id_desafio_dia: UUID) -> list[LinhaDoQuadro]:
        """Todo mundo que resolveu, na ordem do aplicativo, numerado."""
        linhas = await self._linhas(
            _SQL_QUADRO_COMPLETO, {"id_desafio_dia": id_desafio_dia}
        )
        return [
            LinhaDoQuadro(
                posicao=posicao,
                id_resolucao=l["id_resolucao"],
                id_tentativa=l["id_tentativa"],
                id_usuario=l["id_usuario"],
                co_usuario=l.get("co_usuario"),
                no_exibicao=l.get("no_exibicao"),
                nu_xp=int(l["nu_xp"]),
                nu_tempo_ms=int(l["nu_tempo_ms"]),
                dh_resolucao=l["dh_resolucao"],
                co_auditoria=l["co_auditoria"],
                nu_sequencia=int(l.get("nu_sequencia") or 1),
                qt_tentativas=int(l.get("qt_tentativas") or 1),
                qt_dicas=int(l.get("qt_dicas") or 0),
                qt_reacoes=int(l.get("qt_reacoes") or 0),
                ic_publico=bool(l.get("ic_publico", True)),
            )
            for posicao, l in enumerate(linhas, start=1)
        ]

    async def nao_resolveram(self, id_desafio_dia: UUID) -> list[QuemNaoResolveu]:
        """Quem tentou e nao resolveu, mais tentativas primeiro."""
        linhas = await self._linhas(
            _SQL_NAO_RESOLVERAM, {"id_desafio_dia": id_desafio_dia}
        )
        return [
            QuemNaoResolveu(
                id_usuario=l["id_usuario"],
                co_usuario=l.get("co_usuario"),
                no_exibicao=l.get("no_exibicao"),
                qt_tentativas=int(l["qt_tentativas"]),
                nu_tempo_total_ms=int(l.get("nu_tempo_total_ms") or 0),
                qt_dicas=int(l.get("qt_dicas") or 0),
                id_ultima_tentativa=l["id_ultima_tentativa"],
            )
            for l in linhas
        ]

    async def raio_x(self, id_tentativa: UUID) -> Optional[RaioX]:
        """Uma tentativa inteira; `None` se ela nao existe."""
        cabecalho = await self._linhas(_SQL_RAIO_X, {"id_tentativa": id_tentativa})
        if not cabecalho:
            return None
        c = cabecalho[0]
        lances = await self._linhas(SQL_LANCES, {"id_partida": c["id_partida"]})
        extrato: list[dict[str, Any]] = []
        if c.get("id_resolucao") is not None:
            extrato = await self._linhas(
                SQL_EXTRATO, {"id_resolucao": c["id_resolucao"]}
            )
        poderes = await self._linhas(
            _SQL_PODERES_DA_TENTATIVA, {"id_tentativa": id_tentativa}
        )
        return RaioX(
            id_tentativa=c["id_tentativa"],
            id_usuario=c["id_usuario"],
            co_usuario=c.get("co_usuario"),
            no_exibicao=c.get("no_exibicao"),
            nu_sequencia=int(c.get("nu_sequencia") or 1),
            ic_resolveu=bool(c.get("ic_resolveu")),
            nu_tempo_ms=int(c.get("nu_tempo_ms") or 0),
            dh_inicio=c.get("dh_inicio"),
            co_formato_posicao=c["co_formato_posicao"],
            js_posicao_inicial=c.get("js_posicao_inicial") or {},
            co_variante=c.get("co_variante"),
            id_resolucao=c.get("id_resolucao"),
            nu_xp=c.get("nu_xp"),
            nu_lance_cumpre_desafio=c.get("nu_lance_cumpre_desafio"),
            co_auditoria=c.get("co_auditoria"),
            de_auditoria=c.get("de_auditoria"),
            lances=tuple(lances),
            extrato=tuple(extrato),
            poderes=tuple(poderes),
        )
