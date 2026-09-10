"""O QUADRO DO DIA E O REPLAY (T044) — `contracts/quadro-do-dia.md`.

═══════════════════════════════════════════════════════════════════════════
AS QUATRO REGRAS QUE A TELA NAO PODE CONTORNAR
═══════════════════════════════════════════════════════════════════════════

1. ⛔ **Zero nunca aparece** (RF-DES-064). Sem tentativas, `texto_vazio: true` e
   a tela mostra um convite — nunca um `0`.
2. ⛔ **Fracao abaixo de 20 tentativas nao e servida** (RF-DES-063). O campo vem
   `null`. *"2 de 3 resolveram"* grita que o aplicativo tem 3 usuarios.
3. ⛔ **So quem resolveu aparece** (RF-DES-062). Falhar e privado — a tentativa
   sem sucesso existe no banco e **nunca** no quadro.
4. ⛔ **`ic_publico` desligado some do quadro** (RF-DES-077), inclusive no meio
   do dia. O XP ja ganho fica.

⚠️ **As quatro moram AQUI, e nao na tela.** Uma delas na tela seria uma regra a
um `curl` de distancia — e as duas primeiras existem justamente porque o numero
que elas escondem conta sobre o **tamanho da base**, e nao sobre a partida.

═══════════════════════════════════════════════════════════════════════════
⚠️ `minha_linha` VEM SEMPRE
═══════════════════════════════════════════════════════════════════════════

Mesmo fora do topo N (RF-DES-069). Um quadro que corta justamente quem esta
lendo desmotiva pelo mecanismo que o PRD §8 passa o documento inteiro
combatendo.

═══════════════════════════════════════════════════════════════════════════
⚠️ A TRAVA DE SPOILER E DO SERVIDOR
═══════════════════════════════════════════════════════════════════════════

Com `replays_liberados: false` a rota de replay responde **403**. Esconder so na
tela deixaria o dado a um `curl` de distancia, e o quadro viraria gabarito.

| quem | ve o quadro | ve os replays |
|---|---|---|
| ainda nao resolveu hoje | sim (nomes, XP) | ⛔ **nao**, por caminho nenhum |
| ja resolveu hoje | sim | sim, todos, na hora |
| qualquer um, dia encerrado | sim | sim, **com o gabarito** |

⚠️ **Efeito desejado:** resolver **desbloqueia** o conteudo social do dia. Nao se
compra o acesso — joga-se por ele (RF-DES-076).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    VW_DESAFIO_DIA,
    VW_REACAO,
    VW_RESOLUCAO,
    VW_TENTATIVA,
)
from api.desafios.modelos_producao import VW_DESAFIO, VW_MEDICAO_REGUA

#: Quantas linhas de gente o topo do quadro traz, **alem** da propria.
TOPO = 50

#: Abaixo disto a fracao nao e servida (RF-DES-063).
MINIMO_PARA_FRACAO = 20

#: O dia e o desafio, com a regua de tempo que a encenacao dos mascotes precisa.
SQL_DIA_DO_DESAFIO = f"""
SELECT dia.id_desafio_dia,
       dia.dt_dia,
       dia.dh_encerramento,
       d.id_desafio,
       d.nu_tempo_piso_ms,
       d.nu_tempo_teto_ms,
       d.co_personagem
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
 WHERE d.id_desafio = :id_desafio
"""

#: A regua medida daquele desafio — o unico numero real da encenacao.
SQL_MEDICOES = f"""
SELECT co_personagem, nu_execucoes, nu_resolveu
  FROM {VW_MEDICAO_REGUA}
 WHERE id_desafio = :id_desafio
"""

#: As linhas de gente. ⛔ **So quem resolveu, e so quem e publico.**
#:
#: ⚠️ `ic_publico` e a MESMA regra do ranking global
#: (`ic_visivel_placar AND ic_idade_minima_declarada`), e nao uma regra nova: duas
#: definicoes de "aparece em publico" divergiriam, e a mais frouxa mandaria.
#:
#: ⚠️ **O nome vem de `no_exibicao`, e pode ser `NULL`** — quem nunca escolheu um
#: nao tem. A tela usa `co_usuario` nesse caso, e por isso os dois viajam.
#:
#: ⚠️ **`LEFT JOIN` na progressao, com `COALESCE(..., TRUE)`**, e nao `JOIN`:
#: partida de desafio tem `ic_pontua = FALSE`, entao quem so jogou desafios pode
#: nao ter linha de progressao nenhuma. Um `JOIN` a tiraria do quadro **em
#: silencio** — a pessoa resolveria, ganharia XP e simplesmente nao apareceria.
#: O padrao e aparecer; some quem **desligou** a visibilidade.
SQL_LINHAS_DE_GENTE = f"""
SELECT r.id_resolucao,
       r.id_usuario,
       u.co_usuario,
       u.no_exibicao,
       r.nu_xp,
       r.nu_tempo_ms,
       r.dh_resolucao
  FROM {VW_RESOLUCAO} r
  JOIN conta.tb001_usuario u
    ON u.id_usuario = r.id_usuario
  LEFT JOIN progressao.tb001_progressao_usuario g
    ON g.id_usuario = r.id_usuario
 WHERE r.id_desafio_dia = :id_desafio_dia
   AND (COALESCE(g.ic_visivel_placar, TRUE) AND u.ic_idade_minima_declarada)
 ORDER BY r.nu_xp DESC, r.nu_tempo_ms ASC, r.dh_resolucao ASC
"""

#: A minha linha — ⚠️ **sem o filtro de `ic_publico`**.
#:
#: Quem se escondeu do quadro continua vendo a **propria** posicao: `ic_publico`
#: e sobre os outros verem, e nao sobre a pessoa se ver. Filtrar aqui faria quem
#: desligou a visibilidade concluir que perdeu o XP.
SQL_MINHA_LINHA = f"""
SELECT r.id_resolucao, r.nu_xp, r.nu_tempo_ms, r.dh_resolucao
  FROM {VW_RESOLUCAO} r
 WHERE r.id_desafio_dia = :id_desafio_dia
   AND r.id_usuario = :id_usuario
"""

#: O denominador da fracao: quantas **pessoas** tentaram, e quantas resolveram.
#:
#: ⛔ **Mascote nao entra no denominador** (RF-DES-060c) — e nem poderia: ele nao
#: tem tentativa. A fracao e sobre gente.
#:
#: ⚠️ `COUNT(DISTINCT id_usuario)`, e nao `COUNT(*)`: tentar e ilimitado no dia, e
#: contar tentativas faria *"3 de 40"* onde ha 3 de 12 pessoas.
SQL_FRACAO = f"""
SELECT COUNT(DISTINCT id_usuario)                                AS qt_pessoas,
       COUNT(DISTINCT id_usuario) FILTER (WHERE ic_resolveu)     AS qt_resolveram
  FROM {VW_TENTATIVA}
 WHERE id_desafio_dia = :id_desafio_dia
"""

#: As reacoes de cada linha do quadro. ⛔ **Zero nao e servido** (RF-DES-073): a
#: linha simplesmente nao aparece no resultado, e a resposta manda `null`.
SQL_REACOES = f"""
SELECT id_resolucao, co_tipo_reacao, COUNT(*) AS qt
  FROM {VW_REACAO}
 WHERE id_resolucao = ANY(:ids)
 GROUP BY id_resolucao, co_tipo_reacao
"""

#: A partida por tras de um sujeito do quadro — o replay e o de uma PARTIDA.
#:
#: ⚠️ `co_status` vem junto porque **partida em andamento nao tem replay**
#: (RF-DES-187): sem desfecho nao ha o que servir, e e por isso que o job de
#: expiracao (T046) existe.
SQL_PARTIDA_DO_SUJEITO = f"""
SELECT r.id_resolucao, r.id_usuario, r.id_partida, p.co_status, p.co_jogo
  FROM {VW_RESOLUCAO} r
  JOIN partida.vw001_partida p
    ON p.id_partida = r.id_partida
 WHERE r.id_desafio_dia = :id_desafio_dia
   AND r.id_usuario = :id_usuario
"""

#: Os lances de um replay, no vocabulario do log. Mesma forma da auditoria.
SQL_LANCES = """
SELECT j.nu_ordem,
       j.nu_jogador,
       COALESCE(p.co_aresta, dm.co_lance) AS co_lance,
       j.nu_tempo_decisao_ms
  FROM partida.tb002_jogada j
  LEFT JOIN jogo_pontinhos.tb002_jogada p ON p.id_jogada = j.id_jogada
  LEFT JOIN jogo_damas.tb002_jogada dm    ON dm.id_jogada = j.id_jogada
 WHERE j.id_partida = :id_partida
 ORDER BY j.nu_ordem ASC
"""

#: O extrato de XP de uma resolucao — o Raio-X, parcela a parcela.
#:
#: ⚠️ **Vem INTEIRO aqui**, e so as linhas que pontuaram na tela de resultado
#: (RF-DES-177): e o **mesmo dado** nos dois lugares, e nao uma segunda lista
#: escrita para a tela.
SQL_EXTRATO = """
SELECT co_tipo_xp, co_feito, co_unidade, co_direcao,
       vr_medida, vr_normalizado, vr_peso, vr_xp
  FROM desafio_dia.vw004_xp_desafio
 WHERE id_resolucao = :id_resolucao
 ORDER BY nu_tipo_xp, nu_feito NULLS FIRST
"""

#: A solucao de referencia — ⚠️ **so depois que a trava de spoiler abre**.
SQL_GABARITO = f"""
SELECT js_solucao, nu_lances_solucao
  FROM {VW_DESAFIO}
 WHERE id_desafio = :id_desafio
"""


@dataclass(frozen=True, slots=True)
class ContextoDoQuadro:
    """O que o servidor precisa saber antes de montar o quadro."""

    id_desafio_dia: UUID
    id_desafio: UUID
    dh_encerramento: datetime
    nu_tempo_piso_ms: int
    nu_tempo_teto_ms: int
    #: O adversario daquele desafio. ⛔ **Ele nao entra na escada do quadro**
    #: (RF-DES-203): nao joga contra si mesmo, logo nao e regua naquele dia.
    co_personagem_do_dia: str


class RepositorioQuadro:
    """Leitura do quadro e do replay. ⛔ Nao escreve nada."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def contexto(self, id_desafio: UUID) -> Optional[ContextoDoQuadro]:
        """O dia, o desafio e a regua de tempo."""
        resultado = await self.sessao.execute(
            text(SQL_DIA_DO_DESAFIO), {"id_desafio": id_desafio}
        )
        linhas = resultado.mappings().all()
        if not linhas:
            return None
        linha = linhas[0]
        return ContextoDoQuadro(
            id_desafio_dia=linha["id_desafio_dia"],
            id_desafio=linha["id_desafio"],
            dh_encerramento=linha["dh_encerramento"],
            nu_tempo_piso_ms=linha["nu_tempo_piso_ms"],
            nu_tempo_teto_ms=linha["nu_tempo_teto_ms"],
            co_personagem_do_dia=linha["co_personagem"],
        )

    async def medicoes(self, id_desafio: UUID) -> list[dict[str, Any]]:
        """A regua medida daquele desafio."""
        resultado = await self.sessao.execute(
            text(SQL_MEDICOES), {"id_desafio": id_desafio}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def linhas_de_gente(self, id_desafio_dia: UUID) -> list[dict[str, Any]]:
        """Quem resolveu e e publico, do melhor para o pior."""
        resultado = await self.sessao.execute(
            text(SQL_LINHAS_DE_GENTE), {"id_desafio_dia": id_desafio_dia}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def minha_linha(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> Optional[dict[str, Any]]:
        """A propria resolucao — ⚠️ sem o filtro de `ic_publico`."""
        resultado = await self.sessao.execute(
            text(SQL_MINHA_LINHA),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None

    async def fracao(self, id_desafio_dia: UUID) -> tuple[int, int]:
        """`(pessoas_que_tentaram, pessoas_que_resolveram)`."""
        resultado = await self.sessao.execute(
            text(SQL_FRACAO), {"id_desafio_dia": id_desafio_dia}
        )
        linhas = resultado.mappings().all()
        if not linhas:
            return (0, 0)
        return (int(linhas[0]["qt_pessoas"]), int(linhas[0]["qt_resolveram"]))

    async def reacoes(self, ids: list[UUID]) -> dict[UUID, dict[str, int]]:
        """`{id_resolucao: {tipo: quantas}}` — ⛔ sem as que tem zero."""
        if not ids:
            return {}
        resultado = await self.sessao.execute(text(SQL_REACOES), {"ids": ids})
        por_resolucao: dict[UUID, dict[str, int]] = {}
        for linha in resultado.mappings().all():
            por_resolucao.setdefault(linha["id_resolucao"], {})[
                linha["co_tipo_reacao"]
            ] = int(linha["qt"])
        return por_resolucao

    async def partida_do_sujeito(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> Optional[dict[str, Any]]:
        """A partida de quem resolveu — a base do replay."""
        resultado = await self.sessao.execute(
            text(SQL_PARTIDA_DO_SUJEITO),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None

    async def lances(self, id_partida: UUID) -> list[dict[str, Any]]:
        """Os lances da partida, na ordem."""
        resultado = await self.sessao.execute(
            text(SQL_LANCES), {"id_partida": id_partida}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def extrato(self, id_resolucao: UUID) -> list[dict[str, Any]]:
        """O extrato de XP, parcela a parcela."""
        resultado = await self.sessao.execute(
            text(SQL_EXTRATO), {"id_resolucao": id_resolucao}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def gabarito(self, id_desafio: UUID) -> Optional[dict[str, Any]]:
        """A solucao de referencia. ⛔ So depois que a trava abre."""
        resultado = await self.sessao.execute(
            text(SQL_GABARITO), {"id_desafio": id_desafio}
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None


def replays_liberados(
    *,
    resolveu_hoje: bool,
    dh_encerramento: datetime,
    agora: Optional[datetime] = None,
) -> bool:
    """A trava de spoiler, resolvida **no servidor**.

    Args:
        resolveu_hoje: a pessoa ja resolveu este desafio?
        dh_encerramento: quando o dia fecha.
        agora: o instante do servidor.

    Returns:
        `True` quando os replays podem ser servidos.

    ⚠️ **Duas portas, e qualquer uma basta**: resolver, ou o dia acabar. A
    primeira e o efeito desejado — resolver **desbloqueia** o conteudo social; a
    segunda existe porque, encerrado o dia, nao ha mais o que estragar.

    ⛔ Esconder so na tela deixaria o dado a um `curl` de distancia, e o quadro
    viraria gabarito.
    """
    agora = agora or datetime.now(timezone.utc)
    return resolveu_hoje or agora >= dh_encerramento


def fracao_servivel(
    *, qt_pessoas: int, qt_resolveram: int
) -> Optional[dict[str, int]]:
    """A fracao, ou `None` quando o denominador e pequeno demais.

    ⛔ RF-DES-063: abaixo de 20 tentativas ela **nao e servida**. *"2 de 3
    resolveram"* nao fala sobre o desafio — fala sobre quantos usuarios o
    aplicativo tem, e isso nao e informacao que a tela deva dar.
    """
    if qt_pessoas < MINIMO_PARA_FRACAO:
        return None
    return {"tentaram": qt_pessoas, "resolveram": qt_resolveram}
