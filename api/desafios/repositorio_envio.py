"""AS ESCRITAS DO EVENTO — tentativa, resolucao, extrato e dica (T043).

═══════════════════════════════════════════════════════════════════════════
A ORDEM DAS PECAS, QUE E A DECISAO CENTRAL DO SCHEMA
═══════════════════════════════════════════════════════════════════════════

    dia         → qual desafio e o de hoje
    tentativa   → uma partida jogada. Aponta para `partida.tb001_partida`
    resolucao   → a tentativa que DEU CERTO. Aponta para a tentativa
    xp          → as linhas do extrato, ancoradas na resolucao

⚠️ **A tentativa precede a resolucao**, e nao o contrario. Uma pessoa tenta
varias vezes, e cada tentativa e uma partida; quem sabe qual delas venceu e a
resolucao, e ela chega la **pela tentativa**.

═══════════════════════════════════════════════════════════════════════════
⚠️ A IDEMPOTENCIA MORA NO BANCO, EM TRES CONSTRAINTS
═══════════════════════════════════════════════════════════════════════════

  · `tb002_tentativa.id_partida UNIQUE`  — uma partida vira **uma** tentativa;
  · `un001_resolucao (id_desafio_dia, id_usuario)` — uma resolucao por pessoa
    por dia. E a chave natural do contrato: nao ha UUID de requisicao a
    inventar, porque um desafio e publicado **uma vez so** (RF-DES-152);
  · `un001_poder (id_tentativa, nu_tipo_poder, nu_grau)` — a mesma dica nao se
    consome duas vezes.

⛔ **Uma checagem "ja existe?" antes do `INSERT` NAO basta**: o outbox reenvia, e
dois reenvios simultaneos passariam os dois pela checagem. So o banco os separa.
A checagem em Python existe para **evitar trabalho**, nunca para garantir
unicidade.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE REPOSITORIO NAO DA `commit`
═══════════════════════════════════════════════════════════════════════════

Tentativa, resolucao e extrato sao **uma** transacao: um extrato gravado sem a
resolucao, ou uma resolucao sem extrato, e um estado que nada no sistema
consertaria depois. Quem fecha e a rota.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.extrato_xp import ParcelaDeXp
from api.desafios.modelos_evento import (
    TB_PODER_CONSUMIDO,
    TB_RESOLUCAO,
    TB_TENTATIVA,
    TB_XP_DESAFIO,
    VW_DESAFIO_DIA,
    VW_RESOLUCAO,
    VW_TENTATIVA,
)
from api.desafios.modelos_producao import VW_CATALOGO_FEITO, VW_FEITO_DESAFIO

#: A partida que o log ja trouxe, pelo `co_evento` do aplicativo.
#:
#: ⚠️ **`id_usuario` entra na condicao.** Sem isso, alguem poderia amarrar a
#: resolucao dele a uma partida de outra pessoa — e o replay do quadro passaria a
#: mostrar a partida errada.
SQL_PARTIDA_POR_EVENTO = """
SELECT id_partida, co_status, co_modo, dh_inicio, dh_fim
  FROM partida.vw001_partida
 WHERE co_evento = :co_evento
   AND id_usuario = :id_usuario
"""

#: O vinculo do dia, conferido **contra o desafio da URL**.
#:
#: ⚠️ E esta consulta que recusa *"resposta a um desafio de outro dia"*
#: (RF-DES-033). Sem ela, um `id_desafio_dia` de ontem com o `id_desafio` de hoje
#: gravaria a resolucao no evento errado — e a pessoa apareceria no quadro de um
#: dia que ela nao jogou.
SQL_DIA_DO_DESAFIO = f"""
SELECT id_desafio_dia, dt_dia, id_desafio, dh_encerramento
  FROM {VW_DESAFIO_DIA}
 WHERE id_desafio_dia = :id_desafio_dia
   AND id_desafio = :id_desafio
"""

#: Os pesos daquele desafio, com o catalogo ja resolvido.
SQL_PESOS_DO_DESAFIO = f"""
SELECT nu_feito, co_feito, co_direcao, nu_ordem,
       vr_peso, co_normalizacao, vr_min, vr_max, co_sobre
  FROM {VW_FEITO_DESAFIO}
 WHERE id_desafio = :id_desafio
 ORDER BY nu_ordem
"""

#: A tentativa. `nu_sequencia` sai de um `SELECT` na propria tabela, dentro do
#: mesmo comando.
#:
#: ⚠️ **A subconsulta, e nao um contador lido antes**: duas tentativas enviadas
#: juntas leriam o mesmo numero e a segunda quebraria `un001_tentativa`. Dentro do
#: `INSERT`, o banco serializa.
#:
#: ⚠️ **`DO UPDATE` com `WHERE NOT ic_resolveu`, e nao `DO NOTHING`** — e a mesma
#: forma do ingestor de partidas (T045), pelo mesmo motivo. A tentativa pode
#: **nascer pela dica**, no meio da partida, com `ic_resolveu = FALSE` e tempo
#: zero; quando a resolucao chegar depois, um `DO NOTHING` a deixaria marcada
#: como nao resolvida e com tempo zero, e ⛔ **nada daria erro**: a pessoa
#: sumiria do quadro e o `Q` dela seria calculado sobre um tempo que nunca
#: existiu.
#:
#: ⛔ **E o `WHERE` nao e detalhe.** Sem ele, isto viraria "o ultimo envio manda",
#: e um reenvio antigo do outbox desfaria uma resolucao ja gravada. Com ele a
#: mudanca e **de mao unica**: `FALSE → TRUE`, e nunca de volta.
SQL_GRAVAR_TENTATIVA = f"""
INSERT INTO {TB_TENTATIVA}
       (id_desafio_dia, id_usuario, id_partida, nu_sequencia,
        ic_resolveu, nu_tempo_ms, dh_inicio, dh_fim)
SELECT :id_desafio_dia, :id_usuario, :id_partida,
       COALESCE(MAX(nu_sequencia), 0) + 1,
       :ic_resolveu, :nu_tempo_ms, :dh_inicio, :dh_fim
  FROM {TB_TENTATIVA}
 WHERE id_desafio_dia = :id_desafio_dia
   AND id_usuario = :id_usuario
ON CONFLICT (id_partida) DO UPDATE
   SET ic_resolveu = EXCLUDED.ic_resolveu,
       nu_tempo_ms = EXCLUDED.nu_tempo_ms,
       dh_fim      = EXCLUDED.dh_fim
 WHERE NOT desafio_dia.tb002_tentativa.ic_resolveu
RETURNING id_tentativa
"""

#: A tentativa que ja existia — o caminho do reenvio.
SQL_TENTATIVA_DA_PARTIDA = f"""
SELECT id_tentativa, ic_resolveu
  FROM {VW_TENTATIVA}
 WHERE id_partida = :id_partida
"""

#: A resolucao. `ON CONFLICT DO NOTHING` na chave natural (RF-DES-004a: a
#: primeira resolucao e a que vale, e e definitiva).
SQL_GRAVAR_RESOLUCAO = f"""
INSERT INTO {TB_RESOLUCAO}
       (id_desafio_dia, id_usuario, id_tentativa, nu_lance_cumpre_desafio,
        nu_xp, nu_versao_catalogo, dh_resolucao)
VALUES (:id_desafio_dia, :id_usuario, :id_tentativa, :nu_lance,
        :nu_xp, :nu_versao_catalogo, :dh_resolucao)
ON CONFLICT (id_desafio_dia, id_usuario) DO NOTHING
RETURNING id_resolucao
"""

#: A resolucao que ja existia.
SQL_RESOLUCAO_DA_PESSOA = f"""
SELECT id_resolucao
  FROM {VW_RESOLUCAO}
 WHERE id_desafio_dia = :id_desafio_dia
   AND id_usuario = :id_usuario
"""

#: Uma linha do extrato.
SQL_GRAVAR_PARCELA = f"""
INSERT INTO {TB_XP_DESAFIO}
       (id_desafio_dia, id_usuario, id_resolucao, id_tentativa,
        nu_tipo_xp, nu_feito, vr_medida, vr_normalizado, vr_peso, vr_xp)
VALUES (:id_desafio_dia, :id_usuario, :id_resolucao, :id_tentativa,
        :nu_tipo_xp, :nu_feito, :vr_medida, :vr_normalizado, :vr_peso, :vr_xp)
"""

#: A dica consumida. `nu_tipo_poder = 1` e `'dica'` na dimensao `tb902`.
SQL_GRAVAR_DICA = f"""
INSERT INTO {TB_PODER_CONSUMIDO}
       (id_tentativa, nu_tipo_poder, nu_grau, dh_consumo)
VALUES (:id_tentativa, 1, :nu_grau, :dh_consumo)
ON CONFLICT (id_tentativa, nu_tipo_poder, nu_grau) DO NOTHING
RETURNING id_poder_consumido
"""

#: Quantas dicas ja foram gastas **neste desafio** (RF-DES-057).
#:
#: ⚠️ **A conta e sobre o DIA, somando as tentativas** — e nao sobre a tentativa
#: atual. Fechar o aplicativo encerra a tentativa, nao o dia, e um contador por
#: tentativa daria dicas infinitas a quem reabrisse.
SQL_DICAS_DO_DESAFIO = f"""
SELECT COUNT(*) AS qt
  FROM desafio_dia.vw005_poder_consumido p
  JOIN {VW_TENTATIVA} t
    ON t.id_tentativa = p.id_tentativa
 WHERE t.id_desafio_dia = :id_desafio_dia
   AND t.id_usuario = :id_usuario
   AND p.co_tipo_poder = 'dica'
"""


#: A chave de feito existe na dimensao? Usada so quando ela nao pesa no desafio.
SQL_FEITO_NO_CATALOGO = f"""
SELECT 1
  FROM {VW_CATALOGO_FEITO}
 WHERE co_feito = :co_feito
"""


class RepositorioEnvio:
    """As escritas do schema `desafio_dia`. ⛔ Nao fecha a transacao."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # ── Leituras de apoio ─────────────────────────────────────────────────────

    async def partida_por_evento(
        self, *, co_evento: str, id_usuario: str
    ) -> Optional[dict[str, Any]]:
        """A partida que o log ja trouxe, ou `None` se ela ainda nao chegou."""
        resultado = await self.sessao.execute(
            text(SQL_PARTIDA_POR_EVENTO),
            {"co_evento": co_evento, "id_usuario": id_usuario},
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None

    async def dia_do_desafio(
        self, *, id_desafio_dia: UUID, id_desafio: UUID
    ) -> Optional[dict[str, Any]]:
        """O vinculo, **conferido contra o desafio da URL**."""
        resultado = await self.sessao.execute(
            text(SQL_DIA_DO_DESAFIO),
            {"id_desafio_dia": id_desafio_dia, "id_desafio": id_desafio},
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None

    async def pesos_do_desafio(self, id_desafio: UUID) -> list[dict[str, Any]]:
        """As linhas de `tb003_feito_desafio` daquele desafio."""
        resultado = await self.sessao.execute(
            text(SQL_PESOS_DO_DESAFIO), {"id_desafio": id_desafio}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def dicas_ja_gastas(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> int:
        """Quantas dicas a pessoa ja gastou **neste desafio**."""
        resultado = await self.sessao.execute(
            text(SQL_DICAS_DO_DESAFIO),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        return int(resultado.scalar_one())

    # ── Escritas ──────────────────────────────────────────────────────────────

    async def gravar_tentativa(
        self,
        *,
        id_desafio_dia: UUID,
        id_usuario: str,
        id_partida: UUID,
        ic_resolveu: bool,
        nu_tempo_ms: int,
        dh_inicio: datetime,
        dh_fim: datetime,
    ) -> tuple[UUID, bool]:
        """Grava a tentativa, ou devolve a que ja existia.

        Returns:
            `(id_tentativa, escreveu)` — `escreveu` diz se o comando **gravou ou
            atualizou** a linha. ⚠️ Ele e `False` quando a tentativa ja estava
            resolvida, e nesse caso nada mudou de proposito.

        Raises:
            RuntimeError: quando o comando nao escreveu **e** a linha existente
                nao foi encontrada — estado impossivel que nao deve virar `None`
                silencioso la na frente.
        """
        resultado = await self.sessao.execute(
            text(SQL_GRAVAR_TENTATIVA),
            {
                "id_desafio_dia": id_desafio_dia,
                "id_usuario": id_usuario,
                "id_partida": id_partida,
                "ic_resolveu": ic_resolveu,
                "nu_tempo_ms": nu_tempo_ms,
                "dh_inicio": dh_inicio,
                "dh_fim": dh_fim,
            },
        )
        nova = resultado.first()
        if nova is not None:
            return _id(nova, "id_tentativa"), True

        # O `WHERE` do `DO UPDATE` barrou: a tentativa ja existe **e ja estava
        # resolvida**. Nada a mudar — so achar o identificador dela.
        existente = await self.sessao.execute(
            text(SQL_TENTATIVA_DA_PARTIDA), {"id_partida": id_partida}
        )
        linhas = existente.mappings().all()
        if not linhas:
            raise RuntimeError(
                f"a tentativa da partida {id_partida} nao gravou e nao existe. "
                "⛔ Estado impossivel: `ON CONFLICT` so dispara quando ha linha."
            )
        return linhas[0]["id_tentativa"], False

    async def gravar_resolucao(
        self,
        *,
        id_desafio_dia: UUID,
        id_usuario: str,
        id_tentativa: UUID,
        nu_lance: int,
        nu_xp: int,
        nu_versao_catalogo: int,
        dh_resolucao: datetime,
    ) -> tuple[UUID, bool]:
        """Grava a resolucao, ou devolve a que ja existia.

        Returns:
            `(id_resolucao, era_nova)`.

        ⚠️ **A primeira resolucao e a que vale, e e definitiva** (RF-DES-004a). O
        `DO NOTHING` nao e desleixo: e a regra de produto escrita como constraint.
        """
        resultado = await self.sessao.execute(
            text(SQL_GRAVAR_RESOLUCAO),
            {
                "id_desafio_dia": id_desafio_dia,
                "id_usuario": id_usuario,
                "id_tentativa": id_tentativa,
                "nu_lance": nu_lance,
                "nu_xp": nu_xp,
                "nu_versao_catalogo": nu_versao_catalogo,
                "dh_resolucao": dh_resolucao,
            },
        )
        nova = resultado.first()
        if nova is not None:
            return _id(nova, "id_resolucao"), True

        existente = await self.sessao.execute(
            text(SQL_RESOLUCAO_DA_PESSOA),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        linhas = existente.mappings().all()
        if not linhas:
            raise RuntimeError(
                "a resolucao nao gravou e nao existe. ⛔ Estado impossivel."
            )
        return linhas[0]["id_resolucao"], False

    async def gravar_extrato(
        self,
        parcelas: Sequence[ParcelaDeXp],
        *,
        id_desafio_dia: UUID,
        id_usuario: str,
        id_resolucao: Optional[UUID],
        id_tentativa: Optional[UUID],
    ) -> None:
        """Grava as linhas do extrato de XP.

        ⚠️ **So se chama quando a resolucao e NOVA.** Um reenvio que regravasse o
        extrato duplicaria cada parcela: `tb004_xp_desafio` nao tem chave natural
        (nem poderia ter — a linha de `ajuste` e do dia, sem ancora), e por isso a
        protecao contra duplicata mora **em quem chama**, e nao numa constraint.
        """
        for parcela in parcelas:
            await self.sessao.execute(
                text(SQL_GRAVAR_PARCELA),
                {
                    "id_desafio_dia": id_desafio_dia,
                    "id_usuario": id_usuario,
                    "id_resolucao": id_resolucao,
                    "id_tentativa": id_tentativa,
                    "nu_tipo_xp": parcela.nu_tipo_xp,
                    "nu_feito": parcela.nu_feito,
                    "vr_medida": parcela.vr_medida,
                    "vr_normalizado": _arredondar(parcela.vr_normalizado, 4),
                    "vr_peso": parcela.vr_peso,
                    "vr_xp": _arredondar(parcela.vr_xp, 3),
                },
            )

    async def gravar_dica(
        self, *, id_tentativa: UUID, nu_grau: int, dh_consumo: datetime
    ) -> bool:
        """Registra a dica consumida. `False` quando ela ja estava registrada."""
        resultado = await self.sessao.execute(
            text(SQL_GRAVAR_DICA),
            {
                "id_tentativa": id_tentativa,
                "nu_grau": nu_grau,
                "dh_consumo": dh_consumo,
            },
        )
        return resultado.first() is not None

    async def existe_no_catalogo(self, co_feito: str) -> bool:
        """A chave existe na dimensao `tb902_catalogo_feito`?

        ⚠️ Consulta separada, e chamada **so** para as chaves que nao pesam no
        desafio: o caso comum nao paga nada por ela.
        """
        resultado = await self.sessao.execute(
            text(SQL_FEITO_NO_CATALOGO), {"co_feito": co_feito}
        )
        return resultado.first() is not None

    async def confirmar(self) -> None:
        """Fecha a transacao — chamada pela rota, nunca daqui de dentro."""
        await self.sessao.commit()


def _id(linha: Any, coluna: str) -> UUID:
    """O identificador de um `RETURNING`, venha ele como mapping ou tupla."""
    try:
        return linha[coluna]
    except (TypeError, KeyError, IndexError):
        return linha[0]


def _arredondar(valor: Optional[Decimal], casas: int) -> Optional[Decimal]:
    """Arredonda para o que a coluna comporta.

    ⚠️ **`vr_normalizado` e `NUMERIC(5,4)` e `vr_xp` e `NUMERIC(6,3)`.** Um
    `Decimal` com mais casas nao e truncado em silencio pelo asyncpg — ele
    **falha**, e falhar depois de a resolucao ter sido gravada deixaria a linha
    sem extrato.
    """
    if valor is None:
        return None
    return valor.quantize(Decimal(1).scaleb(-casas))
