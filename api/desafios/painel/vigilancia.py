"""AS DUAS SECOES DE VIGILANCIA DO PAINEL (RF-DES-012f, RF-DES-034a — T040).

═══════════════════════════════════════════════════════════════════════════
POR QUE ELAS MORAM NO PAINEL, E NAO NUM CANAL PROPRIO
═══════════════════════════════════════════════════════════════════════════

A pergunta foi decidida em 02/09/2026, quando o SDK de telemetria saiu de
escopo: **o backend nao tem canal de alerta**. Sem um lugar que o dono ja abre
por outro motivo, *"alerta"* vira linha de log que ninguem le, e a divergencia
passa tao despercebida quanto passaria sem alerta nenhum.

⛔ **Nada de e-mail nem push para isto** (RF-DES-034a, textual). O painel de
curadoria e a **mesma visita** em que os candidatos do dia sao aprovados, e e
por isso que as duas secoes aparecem ali, e nao noutra pagina.

═══════════════════════════════════════════════════════════════════════════
⚠️ A SECAO DE DIVERGENCIAS NASCE VAZIA — E ISSO NAO E DEFEITO
═══════════════════════════════════════════════════════════════════════════

Quem **produz** divergencia e o avaliador de resolucoes (T043a): ele le a
resolucao que chegou do aplicativo, re-executa os lances com o arbitro e escreve
`co_auditoria`. Enquanto ele nao roda, toda resolucao fica em `'pendente'` — que
e o `DEFAULT` da coluna — e esta secao abre sem uma linha.

E por isso que a tela mostra **os tres numeros** (pendente · confere ·
divergente), e nao so o ultimo: "0 divergencias" e uma frase que significa duas
coisas opostas — *"esta tudo certo"* e *"ninguem conferiu nada"* —, e o contador
de pendentes e o que as separa.

═══════════════════════════════════════════════════════════════════════════
⚠️ E A SECAO DA FILA AVISA **ANTES**, NAO QUANDO ACABOU
═══════════════════════════════════════════════════════════════════════════

E o texto de RF-DES-012f, e ele descreve um defeito conhecido de painel: um
aviso que so acende quando o estoque zera chega no dia em que ja nao ha o que
fazer. O limiar aqui e a **folga de sobrevivencia do job** (7 dias, o
`DIAS_MINIMOS` de `job/gravacao.py`) — o mesmo numero, de proposito: se a
cobertura cai abaixo do que uma execucao do job cobre, uma unica falha noturna
ja vira dia sem produto.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import VW_DESAFIO_DIA, VW_RESOLUCAO
from api.desafios.modelos_producao import VW_DESAFIO
from api.desafios.painel.repositorio import RepositorioPainel

#: A partir de quantos dias de cobertura o painel para de reclamar.
#:
#: ⚠️ **E o mesmo `DIAS_MINIMOS` de `job/gravacao.py`**, e nao um numero escolhido
#: para a tela. Se os dois divergirem, o painel passa a chamar de "confortavel"
#: uma fila que o job considera curta — e um deles estaria mentindo.
DIAS_DE_FOLGA_CONFORTAVEL = 7

#: Abaixo disto o aviso deixa de ser amarelo e vira vermelho.
DIAS_DE_FOLGA_CRITICA = 3

#: Teto de linhas de divergencia na tela. Ver `_SQL_DIVERGENCIAS`.
LIMITE_DIVERGENCIAS = 50


@dataclass(frozen=True, slots=True)
class ContagemDeAuditoria:
    """Quantas resolucoes em cada estado de auditoria.

    ⚠️ Os tres numeros juntos, sempre. `divergente=0` sozinho nao distingue
    *"conferimos tudo e esta certo"* de *"ninguem conferiu nada"* — e sao
    situacoes que pedem acoes opostas.
    """

    pendente: int = 0
    confere: int = 0
    divergente: int = 0

    @property
    def total(self) -> int:
        """Todas as resolucoes ja recebidas."""
        return self.pendente + self.confere + self.divergente

    @property
    def avaliador_nunca_rodou(self) -> bool:
        """Ha resolucoes, e **nenhuma** foi conferida ainda.

        E o sinal de que T043a nao esta rodando — em producao, isso significa que
        a auditoria inteira esta parada, e nada mais no sistema acusaria.
        """
        return self.total > 0 and self.confere == 0 and self.divergente == 0


@dataclass(frozen=True, slots=True)
class Divergencia:
    """Uma resolucao em que o servidor discordou do aplicativo (RF-DES-034).

    ⛔ **Ela nao corrige nada, e nao tira XP de ninguem** (RF-DES-032, D-05):
    vale o aplicativo, a pessoa continua no quadro. Esta linha existe para ser
    **investigada** — um recalculo pode ter bug proprio, e punir com base nele
    tiraria XP de gente honesta na primeira versao errada do arbitro.
    """

    id_resolucao: Any
    dt_dia: Optional[date]
    co_jogo: str
    co_tipo_desafio: str
    nu_xp: int
    de_auditoria: Optional[str]
    dh_resolucao: Any


@dataclass(frozen=True, slots=True)
class EstadoDaFila:
    """A folga da fila, vista pelos dois numeros que importam.

    Atributos:
        dias_cobertos: quantos dias **consecutivos**, a partir de hoje, ja tem
            desafio agendado. ⚠️ Consecutivos e o que conta: um calendario com
            hoje e o dia 20 preenchidos tem **um** dia de folga, nao dois.
        reserva: quantos desafios estao aprovados e ainda **sem data** — o que da
            para agendar agora, sem esperar o job.
        buracos: os dias descobertos dentro da janela olhada, para a tela poder
            nomea-los em vez de dizer so "esta curta".
    """

    dias_cobertos: int
    reserva: int
    buracos: tuple[date, ...]

    @property
    def gravidade(self) -> str:
        """`ok` · `atencao` · `critico` — o que a tela usa para escolher a cor."""
        if self.dias_cobertos >= DIAS_DE_FOLGA_CONFORTAVEL:
            return "ok"
        if self.dias_cobertos > DIAS_DE_FOLGA_CRITICA:
            return "atencao"
        return "critico"

    @property
    def precisa_avisar(self) -> bool:
        """O painel deve mostrar o aviso?

        ⚠️ **Avisa ANTES de acabar** (RF-DES-012f): o gatilho e a cobertura cair
        abaixo da folga que uma execucao do job repoe, e nao a fila zerar.
        """
        return self.gravidade != "ok"


#: As contagens por estado de auditoria. Uma consulta so, agrupada — tres
#: `SELECT COUNT(*)` dariam o mesmo numero por tres viagens ao banco.
_SQL_CONTAGEM_AUDITORIA = f"""
SELECT co_auditoria, COUNT(*) AS qt
  FROM {VW_RESOLUCAO}
 GROUP BY co_auditoria
"""

#: As divergencias, mais recentes primeiro.
#:
#: ⚠️ **Ha limite de propósito.** A secao e um alerta, e nao um relatorio: se
#: houver duzentas divergencias, o problema nao esta na ducentesima — esta na
#: primeira, e o contador ao lado ja diz que sao muitas.
_SQL_DIVERGENCIAS = f"""
SELECT r.id_resolucao,
       dia.dt_dia,
       d.co_jogo,
       d.co_tipo_desafio,
       r.nu_xp,
       r.de_auditoria,
       r.dh_resolucao
  FROM {VW_RESOLUCAO} r
  JOIN {VW_DESAFIO_DIA} dia
    ON dia.id_desafio_dia = r.id_desafio_dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE r.co_auditoria = 'divergente'
 ORDER BY r.dh_resolucao DESC
 LIMIT :limite
"""


class Vigilancia:
    """As duas secoes de alerta, lidas na mesma visita da fila de curadoria."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.repo = RepositorioPainel(sessao)

    async def contagem_de_auditoria(self) -> ContagemDeAuditoria:
        """Quantas resolucoes em cada estado."""
        resultado = await self.sessao.execute(text(_SQL_CONTAGEM_AUDITORIA))
        por_estado = {
            linha["co_auditoria"]: int(linha["qt"])
            for linha in resultado.mappings().all()
        }
        return ContagemDeAuditoria(
            pendente=por_estado.get("pendente", 0),
            confere=por_estado.get("confere", 0),
            divergente=por_estado.get("divergente", 0),
        )

    async def divergencias(
        self, *, limite: int = LIMITE_DIVERGENCIAS
    ) -> list[Divergencia]:
        """As resolucoes marcadas como divergentes, mais recentes primeiro."""
        resultado = await self.sessao.execute(
            text(_SQL_DIVERGENCIAS), {"limite": limite}
        )
        return [Divergencia(**dict(m)) for m in resultado.mappings().all()]

    async def estado_da_fila(self, *, dt_hoje: date) -> EstadoDaFila:
        """Quantos dias de folga a fila tem, e o que ha de reserva.

        Args:
            dt_hoje: o dia corrente em UTC — parametro, e nao lido daqui de
                dentro, para o teste poder fixa-lo.

        ⚠️ **A conta e de dias CONSECUTIVOS a partir de hoje**, e a razao esta na
        docstring de `EstadoDaFila.dias_cobertos`: e a sequencia sem buraco que
        diz quando o aplicativo abre vazio pela primeira vez.
        """
        ocupados = await self.repo.dias_ocupados(dt_de=dt_hoje)
        # ⛔ So o **aprovado** cobre um dia. Um candidato agendado ocupa a data e
        # nao e servido — a rota filtra por `aprovado` —, entao contar essa data
        # como coberta seria contar um dia em branco como dia cheio.
        com_dono = {
            linha["dt_dia"] for linha in ocupados if linha["co_curadoria"] == "aprovado"
        }

        dias_cobertos = 0
        while dt_hoje + timedelta(days=dias_cobertos) in com_dono:
            dias_cobertos += 1

        # Os buracos dentro da janela confortavel — para a tela poder nomear os
        # dias em vez de dizer so "a fila esta curta".
        buracos = tuple(
            dt_hoje + timedelta(days=n)
            for n in range(DIAS_DE_FOLGA_CONFORTAVEL)
            if dt_hoje + timedelta(days=n) not in com_dono
        )

        return EstadoDaFila(
            dias_cobertos=dias_cobertos,
            reserva=await self.repo.quantos_aprovados_sem_dia(),
            buracos=buracos,
        )
