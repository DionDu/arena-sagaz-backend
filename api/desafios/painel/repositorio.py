"""O SQL DO PAINEL — e nada alem dele (T039).

═══════════════════════════════════════════════════════════════════════════
AS DUAS REGRAS DE BANCO QUE ESTE ARQUIVO OBEDECE
═══════════════════════════════════════════════════════════════════════════

1. ⚠️ **Leitura sempre pela VIEW.** Nenhuma consulta daqui toca `tb001_desafio`
   direto — as constantes de `modelos_producao.py` e `modelos_evento.py` guardam
   os nomes, e usa-las e o que torna o desvio **visivel** quando alguem digitar
   uma tabela por engano.
2. ⚠️ **Escrita sempre na tabela.** As tres acoes de curadoria escrevem em
   `desafio.tb001_desafio` e `desafio_dia.tb001_desafio_dia` — VIEW com `JOIN`
   nao e atualizavel, e tentar seria descobrir isso em producao.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE O REPOSITORIO NAO DA `commit`
═══════════════════════════════════════════════════════════════════════════

E a convencao ja estabelecida em `api/sincronizacao/repositorio.py`: quem
orquestra a transacao e a **rota**, para que uma acao que toca duas tabelas
(aprovar **e** agendar, por exemplo) seja atomica. Um `commit` escondido no meio
do repositorio deixaria metade do trabalho gravada quando a outra metade
falhasse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    VW_DESAFIO_DIA,
    VW_RESOLUCAO,
    VW_TENTATIVA,
    encerramento_do_dia,
)
from api.desafios.janela_baixada import ler_fim_da_janela_baixada
from api.desafios.modelos_producao import VW_DESAFIO, VW_MEDICAO_REGUA

#: A tabela do desafio. ⚠️ **So a escrita a usa** — toda leitura passa por
#: `VW_DESAFIO`.
TB_DESAFIO = "desafio.tb001_desafio"

#: A tabela do vinculo dia↔desafio. Idem: so escrita.
TB_DESAFIO_DIA = "desafio_dia.tb001_desafio_dia"

#: ⚠️ `encerramento_do_dia` **nao** e definida aqui: ela mora em
#: `api/desafios/modelos_evento.py`, junto do schema `desafio_dia`, porque o
#: **job** tambem precisa dela (a reprise publica um dia, T041). Se ela
#: morasse no painel, o job importaria de dentro da API — e a fronteira entre
#: os dois e justamente o que RF-DES-011a protege. Reexportada aqui para quem
#: ja a importava deste modulo.
__all__ = [
    "DesafioNoPainel",
    "DiaNoCalendario",
    "DesafioSemDia",
    "MedicaoNoPainel",
    "RepositorioPainel",
    "encerramento_do_dia",
]


@dataclass(frozen=True, slots=True)
class MedicaoNoPainel:
    """A medicao da regua de **um** mascote, como o painel a mostra.

    ⚠️ A taxa e **calculada**, e nao lida de uma coluna: guardar a divisao criaria
    um terceiro numero que pode discordar dos dois que a originaram — e ai nao ha
    como saber qual esta certo. Mesma decisao de `MedicaoDaRegua.taxa`.
    """

    co_personagem: str
    nu_execucoes: int
    nu_resolveu: int
    co_versao_perfil: str
    co_versao_motor: str

    @property
    def taxa(self) -> float:
        """A fracao de execucoes em que aquele mascote resolveu."""
        return self.nu_resolveu / self.nu_execucoes if self.nu_execucoes else 0.0


@dataclass(frozen=True, slots=True)
class DesafioNoPainel:
    """Uma linha da fila de curadoria, com tudo o que RF-DES-012b exige na tela.

    Os campos existem para responder as cinco perguntas do requisito, nesta
    ordem: **que posicao e esta** (`js_posicao_inicial` + `co_formato_posicao`),
    **de que jogo** (`co_jogo`/`co_modalidade`), **qual e o objetivo**
    (`co_chave_objetivo` + `js_objetivo`), **como se resolve** (`js_solucao`) e
    **quao dificil e** (`medicoes`).

    ⚠️ `dt_dia` e `Optional` porque **aprovar e agendar sao atos separados**
    (RF-DES-153): um candidato aprovado que ainda nao tem dia e o estado normal
    da fila, e nao um defeito.
    """

    id_desafio: UUID
    co_jogo: str
    co_modalidade: Optional[str]
    co_variante: str
    co_formato_posicao: str
    js_posicao_inicial: dict[str, Any]
    co_tipo_desafio: str
    no_tipo_desafio: str
    co_chave_objetivo: str
    js_objetivo: dict[str, Any]
    js_solucao: dict[str, Any]
    nu_lances_solucao: int
    co_personagem: str
    nu_semente: int
    co_curadoria: str
    de_motivo_descarte: Optional[str]
    ic_reprise: bool
    id_desafio_origem: Optional[UUID]
    dh_geracao: datetime
    dt_dia: Optional[date]
    medicoes: tuple[MedicaoNoPainel, ...] = ()
    #: O vinculo com o dia — e por ele que as estatisticas do dia sao lidas.
    #: `None` quando o desafio esta sem data.
    id_desafio_dia: Optional[UUID] = None


@dataclass(frozen=True, slots=True)
class DiaNoCalendario:
    """Um dia do calendario do painel de gestao (02/10/2026).

    ⚠️ **Leve de proposito**: o calendario mostra tres meses, e carregar o
    gabarito e a posicao de noventa desafios para pintar noventa quadradinhos
    seria ler do banco o que a tela nao usa. O detalhe de um dia vem por
    `desafio_do_dia`, quando o dono clica nele.

    Atributos:
        qt_pessoas, qt_resolveram: quantas pessoas tentaram e quantas resolveram
            — o calendario mostra o dia que ja foi jogado, e nao so o agendado.
    """

    dt_dia: date
    id_desafio: UUID
    co_curadoria: str
    co_jogo: str
    co_modalidade: Optional[str]
    co_personagem: str
    no_tipo_desafio: str
    ic_reprise: bool
    qt_pessoas: int = 0
    qt_resolveram: int = 0


@dataclass(frozen=True, slots=True)
class DesafioSemDia:
    """Um desafio que nao mora em dia nenhum: aprovado em reserva, candidato
    antigo ou descartado — as tres listas da lateral do painel."""

    id_desafio: UUID
    co_jogo: str
    co_modalidade: Optional[str]
    co_personagem: str
    no_tipo_desafio: str
    co_curadoria: str
    de_motivo_descarte: Optional[str]
    dh_geracao: datetime


#: A fila de curadoria: o que ainda espera decisao, mais o que ja foi decidido
#: recentemente.
#:
#: ⚠️ **O `LEFT JOIN` com o dia e o que permite ver "aprovado mas sem data"** —
#: exatamente o estado que a fila curta produz, e que o dono precisa enxergar
#: antes de a fila acabar (RF-DES-012f).
#:
#: ⚠️ A ordem coloca **candidato primeiro**: e o que exige acao. Dentro dele,
#: pela data agendada e depois pela geracao — o que vai ao ar antes aparece
#: antes. `NULLS LAST` porque um candidato sem data nao e mais urgente que um
#: agendado para amanha.
#: As colunas que montam um `DesafioNoPainel` — escritas uma vez para as tres
#: consultas que o devolvem (a fila, o dia e o identificador).
_COLUNAS_DO_DESAFIO = """
       d.id_desafio,
       d.co_jogo,
       d.co_modalidade,
       d.co_variante,
       d.co_formato_posicao,
       d.js_posicao_inicial,
       d.co_tipo_desafio,
       d.no_tipo_desafio,
       d.co_chave_objetivo,
       d.js_objetivo,
       d.js_solucao,
       d.nu_lances_solucao,
       d.co_personagem,
       d.nu_semente,
       d.co_curadoria,
       d.de_motivo_descarte,
       d.ic_reprise,
       d.id_desafio_origem,
       d.dh_geracao,
       dia.dt_dia,
       dia.id_desafio_dia
"""

_SQL_FILA = f"""
SELECT {_COLUNAS_DO_DESAFIO}
  FROM {VW_DESAFIO} d
  LEFT JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio = d.id_desafio
 WHERE d.co_curadoria = ANY(:estados)
 ORDER BY CASE d.co_curadoria WHEN 'candidato' THEN 0
                              WHEN 'aprovado'  THEN 1
                              ELSE 2 END,
          dia.dt_dia ASC NULLS LAST,
          d.dh_geracao ASC
 LIMIT :limite
"""

#: O desafio que mora num dia — o detalhe que o painel abre ao clicar no
#: calendario (02/10/2026). ⚠️ Qualquer estado de curadoria: um descartado que
#: ainda tenha vinculo (anterior a regra que o desagenda) tambem precisa ser
#: visto, senao o dia pareceria vazio com uma linha la dentro.
_SQL_DESAFIO_DO_DIA = f"""
SELECT {_COLUNAS_DO_DESAFIO}
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE dia.dt_dia = :dt_dia
"""

#: Um desafio pelo identificador — para abrir o que esta SEM dia (reserva,
#: candidato antigo, descartado) no mesmo detalhe.
_SQL_DESAFIO_POR_ID = f"""
SELECT {_COLUNAS_DO_DESAFIO}
  FROM {VW_DESAFIO} d
  LEFT JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio = d.id_desafio
 WHERE d.id_desafio = :id_desafio
"""

#: Os dias de uma janela, com o minimo para pintar o calendario.
#:
#: ⚠️ **As contagens vem por subconsulta correlacionada**, e nao por `JOIN` +
#: `GROUP BY`: o `GROUP BY` teria de repetir as colunas do desafio, e a janela
#: e de noventa dias — a subconsulta usa o indice de `id_desafio_dia` e custa o
#: mesmo.
_SQL_CALENDARIO = f"""
SELECT dia.dt_dia,
       d.id_desafio,
       d.co_curadoria,
       d.co_jogo,
       d.co_modalidade,
       d.co_personagem,
       d.no_tipo_desafio,
       d.ic_reprise,
       (SELECT COUNT(DISTINCT t.id_usuario)
          FROM {VW_TENTATIVA} t
         WHERE t.id_desafio_dia = dia.id_desafio_dia) AS qt_pessoas,
       (SELECT COUNT(DISTINCT r.id_usuario)
          FROM {VW_RESOLUCAO} r
         WHERE r.id_desafio_dia = dia.id_desafio_dia) AS qt_resolveram
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE dia.dt_dia BETWEEN :dt_de AND :dt_ate
 ORDER BY dia.dt_dia
"""

#: Os desafios SEM dia num estado de curadoria, mais recentes primeiro.
_SQL_SEM_DIA = f"""
SELECT d.id_desafio,
       d.co_jogo,
       d.co_modalidade,
       d.co_personagem,
       d.no_tipo_desafio,
       d.co_curadoria,
       d.de_motivo_descarte,
       d.dh_geracao
  FROM {VW_DESAFIO} d
  LEFT JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio = d.id_desafio
 WHERE d.co_curadoria = :co_curadoria
   AND dia.id_desafio IS NULL
 ORDER BY d.dh_geracao DESC
 LIMIT :limite
"""

#: Em que dia o desafio mora e quantas tentativas ja recebeu — a guarda do
#: descarte (`servico.descartar`): dia jogado nao se desagenda.
_SQL_SITUACAO_NO_CALENDARIO = f"""
SELECT dia.dt_dia,
       (SELECT COUNT(*)
          FROM {VW_TENTATIVA} t
         WHERE t.id_desafio_dia = dia.id_desafio_dia) AS qt_tentativas
  FROM {VW_DESAFIO_DIA} dia
 WHERE dia.id_desafio = :id_desafio
"""

#: Aprova de uma vez todo `candidato` que sobrou de antes de 02/10/2026.
#:
#: ⚠️ **Existe para a transicao**: desde aquele dia nada nasce candidato, e os
#: que ja estavam na fila continuariam ocupando dias sem ir ao ar — o aviso de
#: "fila critica" que o dono viu com cinco desafios prontos na fila.
_SQL_APROVAR_CANDIDATOS = f"""
UPDATE {TB_DESAFIO}
   SET co_curadoria = 'aprovado',
       de_motivo_descarte = NULL
 WHERE co_curadoria = 'candidato'
RETURNING id_desafio
"""

#: As medicoes da regua dos desafios que a fila trouxe.
#:
#: ⚠️ **Uma consulta so para todos eles**, e nao uma por desafio: a fila tem
#: dezenas de linhas, e um `SELECT` por linha e o padrao N+1 — funciona no teste
#: com tres desafios e derruba o painel com trinta.
_SQL_MEDICOES = f"""
SELECT id_desafio,
       co_personagem,
       nu_execucoes,
       nu_resolveu,
       co_versao_perfil,
       co_versao_motor
  FROM {VW_MEDICAO_REGUA}
 WHERE id_desafio = ANY(:ids)
 ORDER BY CASE co_personagem WHEN 'cacau' THEN 0 WHEN 'pita' THEN 1
                             WHEN 'tex'   THEN 2 ELSE 3 END
"""

#: Aprovar. ⚠️ **So sai de `candidato`**, e a condicao esta no `WHERE`, nao numa
#: leitura anterior: duas abas do painel abertas na mesma linha passariam as duas
#: por uma checagem em Python, e so o banco as separa.
#:
#: ⚠️ `de_motivo_descarte` volta a `NULL` porque `ck004_motivo` amarra os dois: um
#: desafio antes descartado que o dono reconsidere nao pode carregar o motivo do
#: descarte anterior como se ainda valesse.
_SQL_APROVAR = f"""
UPDATE {TB_DESAFIO}
   SET co_curadoria = 'aprovado',
       de_motivo_descarte = NULL
 WHERE id_desafio = :id_desafio
   AND co_curadoria <> 'aprovado'
RETURNING id_desafio
"""

#: Descartar — **nao apaga** (RF-DES-012c). O motivo e obrigatorio, e o `CHECK`
#: `ck004_motivo` da migracao o exige tambem no banco: e ele que ensina o gerador
#: a nao repetir a familia de posicao que saiu ruim.
_SQL_DESCARTAR = f"""
UPDATE {TB_DESAFIO}
   SET co_curadoria = 'descartado',
       de_motivo_descarte = :de_motivo
 WHERE id_desafio = :id_desafio
RETURNING id_desafio
"""

#: Agendar, ou trocar a data. `ON CONFLICT (id_desafio)` usa `un002_desafio` — *um
#: desafio e publicado uma vez so* (RF-DES-152) —, e por isso trocar a data e um
#: `UPDATE` do vinculo que ja existe, nunca uma segunda linha.
#:
#: ⛔ **Se o dia de destino ja tiver dono, o `INSERT` falha** por `un001_dia`, e
#: falhar e o certo: dois desafios no mesmo dia nao e um estado que o produto
#: saiba servir, e escolher um deles em silencio seria pior.
_SQL_AGENDAR = f"""
INSERT INTO {TB_DESAFIO_DIA} (dt_dia, id_desafio, dh_encerramento)
VALUES (:dt_dia, :id_desafio, :dh_encerramento)
ON CONFLICT (id_desafio) DO UPDATE
   SET dt_dia = EXCLUDED.dt_dia,
       dh_encerramento = EXCLUDED.dh_encerramento
RETURNING id_desafio_dia
"""

#: Tirar do calendario, sem tocar na aprovacao. E o passo que "trocar a data"
#: precisa quando o destino ja esta ocupado — e o unico jeito de liberar um dia.
_SQL_DESAGENDAR = f"""
DELETE FROM {TB_DESAFIO_DIA}
 WHERE id_desafio = :id_desafio
RETURNING id_desafio_dia
"""

#: Quem ja mora em cada dia daqui para a frente. Alimenta o aviso de fila curta
#: (T040) e o aviso de conflito ao trocar a data.
_SQL_DIAS_OCUPADOS = f"""
SELECT dia.dt_dia,
       dia.id_desafio,
       d.co_curadoria,
       d.co_jogo,
       d.ic_reprise
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE dia.dt_dia >= :dt_de
 ORDER BY dia.dt_dia
"""

#: Quantos desafios **aprovados e ainda sem dia** existem — a folga real da fila.
_SQL_APROVADOS_SEM_DIA = f"""
SELECT COUNT(*) AS qt
  FROM {VW_DESAFIO} d
  LEFT JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio = d.id_desafio
 WHERE d.co_curadoria = 'aprovado'
   AND dia.id_desafio IS NULL
"""


class RepositorioPainel:
    """Acesso ao banco para o painel de curadoria.

    Recebe a `AsyncSession` da requisicao e **nao** faz `commit` — ver a nota no
    topo do modulo.
    """

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Leitura ───────────────────────────────────────────────────────────────

    async def fila(
        self,
        *,
        estados: tuple[str, ...] = ("candidato", "aprovado"),
        limite: int = 60,
    ) -> list[DesafioNoPainel]:
        """A fila de curadoria, ja com as medicoes da regua penduradas.

        Args:
            estados: que estados de curadoria trazer. O padrao deixa os
                descartados de fora — eles nao pedem acao, e enche-los na tela
                afogaria o que pede.
            limite: teto de linhas.

        Returns:
            As linhas, candidatos primeiro.
        """
        resultado = await self.sessao.execute(
            text(_SQL_FILA), {"estados": list(estados), "limite": limite}
        )
        # `.mappings()` entrega cada linha como dicionario coluna→valor, em vez
        # de uma tupla posicional — o codigo abaixo fica legivel e nao quebra se
        # alguem reordenar o `SELECT`.
        linhas = [dict(m) for m in resultado.mappings().all()]
        if not linhas:
            return []

        return await self._com_medicoes(linhas)

    async def _com_medicoes(
        self, linhas: list[dict[str, Any]]
    ) -> list[DesafioNoPainel]:
        """Pendura as medicoes da regua nas linhas — uma consulta para todas."""
        if not linhas:
            return []
        medicoes = await self._medicoes([linha["id_desafio"] for linha in linhas])
        return [
            DesafioNoPainel(
                **linha,
                medicoes=tuple(medicoes.get(linha["id_desafio"], ())),
            )
            for linha in linhas
        ]

    async def desafio_do_dia(self, dt_dia: date) -> Optional[DesafioNoPainel]:
        """O desafio que mora naquele dia, com a regua; `None` se o dia esta vazio."""
        resultado = await self.sessao.execute(
            text(_SQL_DESAFIO_DO_DIA), {"dt_dia": dt_dia}
        )
        linhas = [dict(m) for m in resultado.mappings().all()]
        desafios = await self._com_medicoes(linhas)
        return desafios[0] if desafios else None

    async def desafio_por_id(self, id_desafio: UUID) -> Optional[DesafioNoPainel]:
        """Um desafio qualquer, com ou sem dia."""
        resultado = await self.sessao.execute(
            text(_SQL_DESAFIO_POR_ID), {"id_desafio": id_desafio}
        )
        linhas = [dict(m) for m in resultado.mappings().all()]
        desafios = await self._com_medicoes(linhas)
        return desafios[0] if desafios else None

    async def calendario(self, *, dt_de: date, dt_ate: date) -> list[DiaNoCalendario]:
        """Os dias com desafio na janela, para pintar o calendario."""
        resultado = await self.sessao.execute(
            text(_SQL_CALENDARIO), {"dt_de": dt_de, "dt_ate": dt_ate}
        )
        return [
            DiaNoCalendario(
                dt_dia=m["dt_dia"],
                id_desafio=m["id_desafio"],
                co_curadoria=m["co_curadoria"],
                co_jogo=m["co_jogo"],
                co_modalidade=m["co_modalidade"],
                co_personagem=m["co_personagem"],
                no_tipo_desafio=m["no_tipo_desafio"],
                ic_reprise=bool(m["ic_reprise"]),
                qt_pessoas=int(m.get("qt_pessoas") or 0),
                qt_resolveram=int(m.get("qt_resolveram") or 0),
            )
            for m in resultado.mappings().all()
        ]

    async def sem_dia(
        self, co_curadoria: str, *, limite: int = 30
    ) -> list[DesafioSemDia]:
        """Os desafios sem data num estado (reserva, candidatos, descartados)."""
        resultado = await self.sessao.execute(
            text(_SQL_SEM_DIA), {"co_curadoria": co_curadoria, "limite": limite}
        )
        return [DesafioSemDia(**dict(m)) for m in resultado.mappings().all()]

    async def _medicoes(
        self, ids: list[UUID]
    ) -> dict[UUID, list[MedicaoNoPainel]]:
        """As medicoes da regua, agrupadas por desafio.

        ⚠️ **Uma consulta so** para toda a fila — ver a nota de `_SQL_MEDICOES`.
        """
        resultado = await self.sessao.execute(text(_SQL_MEDICOES), {"ids": ids})
        por_desafio: dict[UUID, list[MedicaoNoPainel]] = {}
        for linha in resultado.mappings().all():
            por_desafio.setdefault(linha["id_desafio"], []).append(
                MedicaoNoPainel(
                    co_personagem=linha["co_personagem"],
                    nu_execucoes=linha["nu_execucoes"],
                    nu_resolveu=linha["nu_resolveu"],
                    co_versao_perfil=linha["co_versao_perfil"],
                    co_versao_motor=linha["co_versao_motor"],
                )
            )
        return por_desafio

    async def dias_ocupados(self, *, dt_de: date) -> list[dict[str, Any]]:
        """Que dias, de `dt_de` em diante, ja tem desafio vinculado."""
        resultado = await self.sessao.execute(
            text(_SQL_DIAS_OCUPADOS), {"dt_de": dt_de}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def quantos_aprovados_sem_dia(self) -> int:
        """Quantos desafios aprovados esperam data.

        ⚠️ E **este** numero, e nao o de dias cobertos, que diz se ha do que
        publicar amanha: um calendario cheio ate sexta com a reserva zerada esta
        a um dia de acabar.
        """
        resultado = await self.sessao.execute(text(_SQL_APROVADOS_SEM_DIA))
        return int(resultado.scalar_one())

    # ── Escrita ───────────────────────────────────────────────────────────────

    async def aprovar(self, id_desafio: UUID) -> bool:
        """Aprova o desafio. Devolve `False` se ele ja estava aprovado."""
        resultado = await self.sessao.execute(
            text(_SQL_APROVAR), {"id_desafio": id_desafio}
        )
        return resultado.first() is not None

    async def situacao_no_calendario(
        self, id_desafio: UUID
    ) -> Optional[tuple[date, int]]:
        """`(dia, tentativas)` do desafio; `None` quando ele nao tem dia."""
        resultado = await self.sessao.execute(
            text(_SQL_SITUACAO_NO_CALENDARIO), {"id_desafio": id_desafio}
        )
        linha = resultado.mappings().first()
        if linha is None:
            return None
        return linha["dt_dia"], int(linha["qt_tentativas"] or 0)

    async def fim_da_janela_baixada(self, dt_hoje: date) -> date:
        """O ultimo dia cujo desafio pode estar num aparelho (07/10/2026).

        ⚠️ A regra mora em `api/desafios/janela_baixada.py`, que o job tambem usa:
        o painel e a compactacao da fila tem de concordar sobre onde a trava
        termina.
        """
        return await ler_fim_da_janela_baixada(self.sessao, dt_hoje)

    async def aprovar_candidatos(self) -> int:
        """Aprova todo candidato que restou. Devolve quantos mudaram."""
        resultado = await self.sessao.execute(text(_SQL_APROVAR_CANDIDATOS))
        return len(resultado.all())

    async def descartar(self, id_desafio: UUID, *, de_motivo: str) -> bool:
        """Descarta com motivo. Devolve `False` se o desafio nao existe."""
        resultado = await self.sessao.execute(
            text(_SQL_DESCARTAR),
            {"id_desafio": id_desafio, "de_motivo": de_motivo},
        )
        return resultado.first() is not None

    async def agendar(self, id_desafio: UUID, *, dt_dia: date) -> bool:
        """Poe (ou move) o desafio num dia. Devolve `False` se nada mudou."""
        resultado = await self.sessao.execute(
            text(_SQL_AGENDAR),
            {
                "id_desafio": id_desafio,
                "dt_dia": dt_dia,
                "dh_encerramento": encerramento_do_dia(dt_dia),
            },
        )
        return resultado.first() is not None

    async def desagendar(self, id_desafio: UUID) -> bool:
        """Tira o desafio do calendario. Devolve `False` se ele nao tinha dia."""
        resultado = await self.sessao.execute(
            text(_SQL_DESAGENDAR), {"id_desafio": id_desafio}
        )
        return resultado.first() is not None

    async def confirmar(self) -> None:
        """Fecha a transacao da acao.

        ⚠️ Existe para que a **rota** decida quando fechar — o repositorio nunca
        chama isto sozinho.
        """
        await self.sessao.commit()
