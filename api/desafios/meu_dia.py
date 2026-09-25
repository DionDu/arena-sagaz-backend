"""O MEU DIA - o que a pessoa ja fez no desafio de hoje, para QUALQUER aparelho (T085za).

`GET /v1/desafios/{id_desafio}/meu-dia` — `contracts/meu-dia.md` (no app).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA ROTA EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate a T085za o aparelho era a unica memoria do dia: quantas tentativas, quantas
dicas, se resolveu e com que numeros. O dono, em 24/09/2026:

    "Eu nao gosto destes dados que ficam sendo salvos apenas localmente no
     celular. Sempre da esses problema quando temos 2 contas no mesmo celular.
     [...] Quando o usuario se loga em outro aparelho precisa visualizar no
     outro aparelho o mesmo que via no primeiro."

O aplicativo le esta rota ao abrir o dia (com conta) e JUNTA o que ela diz com o
que o aparelho sabe - o aparelho pode estar a frente (a fila ainda ⛔ subiu), e o
servidor pode estar a frente (a pessoa jogou em outro aparelho).

═══════════════════════════════════════════════════════════════════════════
⚠️ AS TENTATIVAS: ⛔ TODA LINHA DE `tb002` E UMA TENTATIVA FECHADA
═══════════════════════════════════════════════════════════════════════════

A **dica** cria a linha da tentativa DURANTE a partida (`registrar_dica`: ela
nasce `ic_resolveu = FALSE`, `nu_tempo_ms = 0`), antes de o envio da tentativa
chegar. Se a pessoa larga a partida no meio, a linha fica - e a partida largada
⛔ entra no `1/n` (`DECISOES-do-dono.md` §8q). Contar a linha crua faria o
aparelho novo achar uma tentativa a mais, e a nota da proxima resolucao cairia.

Por isso a contagem tira a linha que **so a dica criou**: ⛔ resolvida, tempo
zero, e com dica pendurada. O envio da tentativa (resolvida ou nao) sobrescreve
`nu_tempo_ms` com o tempo de verdade, e a linha passa a contar.

⚠️ **E o "resolveu na N-a tentativa" ⛔ sai de `nu_sequencia`**, pelo mesmo
motivo: a linha de uma dica largada ocupa um numero. Sai da parcela
`tentativas` do extrato, que guarda o `n` que o proprio aplicativo mandou - o
mesmo que entrou na nota.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    VW_DESAFIO_DIA,
    VW_PODER_CONSUMIDO,
    VW_RESOLUCAO,
    VW_TENTATIVA,
    VW_XP_DESAFIO,
)
from api.desafios.repositorio_envio import SQL_DICAS_DO_DESAFIO
from api.nucleo.excecoes import ErroNaoEncontrado

#: O dia em que o desafio foi publicado. ⚠️ Um desafio e publicado UMA vez so
#: (a reprise e copia, com identificador proprio) - entao e uma linha, ou nada.
SQL_DIA_DO_DESAFIO = f"""
SELECT id_desafio_dia
  FROM {VW_DESAFIO_DIA}
 WHERE id_desafio = :id_desafio
"""

#: As tentativas FECHADAS da pessoa no dia - ver o cabecalho.
#:
#: ⚠️ `NOT (...)` em vez de tres condicoes soltas: a linha que sai e a que tem
#: as TRES marcas juntas. Uma tentativa que falhou de verdade tem tempo; a que
#: resolveu tem `ic_resolveu`; a que ⛔ teve dica ⛔ foi criada pela dica.
SQL_TENTATIVAS_FECHADAS = f"""
SELECT COUNT(*) AS qt
  FROM {VW_TENTATIVA} t
 WHERE t.id_desafio_dia = :id_desafio_dia
   AND t.id_usuario = :id_usuario
   AND NOT (
         NOT t.ic_resolveu
     AND t.nu_tempo_ms = 0
     AND EXISTS (SELECT 1
                   FROM {VW_PODER_CONSUMIDO} p
                  WHERE p.id_tentativa = t.id_tentativa)
   )
"""

#: A resolucao da pessoa no dia, com o retrato e o `n` que entrou na nota.
#:
#: ⚠️ O `n` vem da parcela `tentativas` do extrato (`co_tipo_xp`), e
#: `nu_sequencia` fica de reserva para uma resolucao sem extrato - que ⛔ deve
#: existir, mas um `NULL` aqui apagaria o "na 3a tentativa" da tela.
SQL_RESOLUCAO_DO_DIA = f"""
SELECT r.nu_xp,
       r.nu_tempo_ms,
       r.js_feito,
       t.nu_sequencia,
       (SELECT x.vr_medida
          FROM {VW_XP_DESAFIO} x
         WHERE x.id_resolucao = r.id_resolucao
           AND x.co_tipo_xp = 'tentativas') AS vr_tentativas
  FROM {VW_RESOLUCAO} r
  JOIN {VW_TENTATIVA} t
    ON t.id_tentativa = r.id_tentativa
 WHERE r.id_desafio_dia = :id_desafio_dia
   AND r.id_usuario = :id_usuario
"""


class RepositorioMeuDia:
    """Leitura do dia de uma pessoa. ⛔ Nao escreve nada."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def dia_do_desafio(self, *, id_desafio: UUID) -> Optional[UUID]:
        """O `id_desafio_dia` do desafio, ou `None` se ele ⛔ foi publicado."""
        resultado = await self.sessao.execute(
            text(SQL_DIA_DO_DESAFIO), {"id_desafio": id_desafio}
        )
        linha = resultado.mappings().first()
        return None if linha is None else linha["id_desafio_dia"]

    async def tentativas_fechadas(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> int:
        resultado = await self.sessao.execute(
            text(SQL_TENTATIVAS_FECHADAS),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        return int(resultado.scalar_one())

    async def dicas(self, *, id_desafio_dia: UUID, id_usuario: str) -> int:
        """⚠️ A mesma conta do teto do envio (`SQL_DICAS_DO_DESAFIO`): uma so,
        para o aparelho e o servidor ⛔ discordarem sobre quantas restam."""
        resultado = await self.sessao.execute(
            text(SQL_DICAS_DO_DESAFIO),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        return int(resultado.scalar_one())

    async def resolucao(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> Optional[dict[str, Any]]:
        resultado = await self.sessao.execute(
            text(SQL_RESOLUCAO_DO_DIA),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        linha = resultado.mappings().first()
        return None if linha is None else dict(linha)


def _json(valor: Any) -> Optional[dict[str, Any]]:
    """O JSONB como `dict`. O driver ja o decodifica (como faz com
    `js_objetivo` em `publicacao.py`); o texto e aceito para o dia em que um
    driver ⛔ o fizer - a tela receberia uma string no lugar do retrato."""
    if valor is None or isinstance(valor, dict):
        return valor
    return json.loads(valor)


class ServicoMeuDia:
    """Monta o corpo de `GET /v1/desafios/{id}/meu-dia`."""

    def __init__(self, repo: RepositorioMeuDia) -> None:
        self.repo = repo

    async def montar(self, *, id_desafio: UUID, id_usuario: str) -> dict[str, Any]:
        """O dia da pessoa no desafio [id_desafio].

        Raises:
            ErroNaoEncontrado: o desafio ⛔ foi publicado - 404, e o aplicativo
                fica com o que o aparelho sabe.
        """
        id_desafio_dia = await self.repo.dia_do_desafio(id_desafio=id_desafio)
        if id_desafio_dia is None:
            raise ErroNaoEncontrado("Desafio nao publicado.", "desafio_inexistente")

        tentativas = await self.repo.tentativas_fechadas(
            id_desafio_dia=id_desafio_dia, id_usuario=id_usuario
        )
        dicas = await self.repo.dicas(
            id_desafio_dia=id_desafio_dia, id_usuario=id_usuario
        )
        resolucao = await self.repo.resolucao(
            id_desafio_dia=id_desafio_dia, id_usuario=id_usuario
        )

        primeira = None
        if resolucao is not None:
            n = resolucao["vr_tentativas"]
            primeira = {
                "na_tentativa": int(n) if n is not None else resolucao["nu_sequencia"],
                "pontuacao": resolucao["nu_xp"],
                "tempo_ms": resolucao["nu_tempo_ms"],
                # ⚠️ `None` e a resolucao anterior a `0027` - o aplicativo cai
                # em "Objetivo cumprido", que continua verdadeiro.
                "feito": _json(resolucao["js_feito"]),
            }

        return {
            "id_desafio_dia": id_desafio_dia,
            "tentativas": tentativas,
            "dicas": dicas,
            "resolveu": primeira is not None,
            "primeira": primeira,
        }
