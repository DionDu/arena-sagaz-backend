"""AS LEITURAS DO DESAFIO PUBLICADO (T042) — e so as leituras.

═══════════════════════════════════════════════════════════════════════════
⛔ A CLAUSULA QUE APARECE EM TODAS AS CONSULTAS DAQUI
═══════════════════════════════════════════════════════════════════════════

    d.co_curadoria = 'aprovado'

**So o aprovado e servido ao aplicativo, nunca o candidato** (RF-DES-012a). Ela
esta escrita em cada consulta, e nao numa funcao que "aplica o filtro", porque
uma consulta nova que esquecesse de chamar a funcao serviria conteudo nao
revisado **sem erro nenhum** — e a primeira vez que isso acontecesse seria com um
desafio impossivel no ar.

⚠️ Ha teste que le o texto das consultas e falha se alguma perder a clausula.

═══════════════════════════════════════════════════════════════════════════
⚠️ O DIA E UTC, E A COMPARACAO E POR INSTANTE
═══════════════════════════════════════════════════════════════════════════

"Hoje" e a linha cujo `dh_encerramento` ainda esta a frente e cujo `dt_dia` ja
chegou. Comparar por `dt_dia = CURRENT_DATE` daria o mesmo resultado **quase**
sempre, e o "quase" e o problema: `CURRENT_DATE` depende do fuso da sessao do
Postgres, e uma mudanca de configuracao do Railway trocaria o desafio do dia sem
que nenhuma linha de codigo tivesse mudado.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import VW_DESAFIO_DIA
from api.desafios.modelos_producao import VW_DESAFIO

#: As colunas que a resposta usa. ⛔ **`js_solucao` NAO esta aqui**, e essa e a
#: ausencia mais importante deste arquivo: e o gabarito (RF-DES-076).
#:
#: ⚠️ Escritas uma vez e reusadas nas tres consultas — tres listas iguais em tres
#: lugares divergiriam, e a que divergisse serviria um campo a menos para uma das
#: rotas, sem erro.
_COLUNAS = """
       dia.id_desafio_dia,
       dia.dt_dia,
       dia.dh_encerramento,
       d.id_desafio,
       d.co_jogo,
       d.co_modalidade,
       d.co_variante,
       d.co_formato_posicao,
       d.js_posicao_inicial,
       d.co_tipo_desafio,
       d.js_chegada,
       d.co_chave_objetivo,
       d.js_objetivo,
       d.co_personagem,
       d.nu_semente,
       d.co_versao_minima,
       d.co_versao_perfil,
       d.nu_teto_log,
       d.ic_reprise
"""

_DE = f"""
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d
    ON d.id_desafio = dia.id_desafio
"""

#: O desafio de hoje. ⚠️ **Por instante, e nao por `CURRENT_DATE`** — ver o topo.
SQL_HOJE = f"""
SELECT {_COLUNAS}
{_DE}
 WHERE d.co_curadoria = 'aprovado'
   AND dia.dh_encerramento > :agora
   AND dia.dt_dia <= :dt_hoje
 ORDER BY dia.dt_dia DESC
 LIMIT 1
"""

#: O cache invisivel: os proximos dias, **depois** do de hoje (RF-DES-120).
#:
#: ⚠️ **A lista e curta de proposito.** O servidor nao consegue impedir a tela de
#: exibir o que ela ja baixou — a garantia de RF-DES-009 mora no aplicativo —,
#: mas pode nao dar mais do que o necessario para atravessar um fim de semana sem
#: rede.
SQL_PROXIMOS = f"""
SELECT {_COLUNAS}
{_DE}
 WHERE d.co_curadoria = 'aprovado'
   AND dia.dt_dia > :dt_hoje
 ORDER BY dia.dt_dia ASC
 LIMIT :limite
"""

#: Um desafio pelo identificador — e o caminho do **historico** (aba Historico).
#:
#: ⚠️ Aceita dia passado, ao contrario de `SQL_HOJE`: e para isso que ele existe.
#: ⛔ Continua sem `js_solucao`: o gabarito de um dia encerrado sai pela rota de
#: replay (T044), que sabe conferir a trava de spoiler.
SQL_POR_ID = f"""
SELECT {_COLUNAS}
{_DE}
 WHERE d.co_curadoria = 'aprovado'
   AND d.id_desafio = :id_desafio
 LIMIT 1
"""

#: As tres, para o cadeado que confere o filtro de curadoria.
CONSULTAS_PUBLICAS = {
    "hoje": SQL_HOJE,
    "proximos": SQL_PROXIMOS,
    "por_id": SQL_POR_ID,
}

#: Quantos dias de cache o `/proximos` entrega.
#:
#: ⚠️ Tres, e nao os 7 a 30 que o job mantem: o cache serve para atravessar uma
#: viagem sem rede, e nao para o aparelho guardar o mes inteiro. Quanto menos
#: futuro no aparelho, menos superficie para RF-DES-009 ser violada por engano.
DIAS_DE_CACHE = 3


class RepositorioDesafio:
    """Leitura do desafio publicado. ⛔ Nao escreve nada."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def de_hoje(
        self, *, agora: Optional[datetime] = None
    ) -> Optional[dict[str, Any]]:
        """O desafio do dia corrente, ou `None` se nao ha nenhum aprovado.

        ⚠️ **`None` e um estado legitimo**, e nao um erro: e o pior caso
        operacional (fila vazia e sem reprise), e a rota precisa devolver algo
        honesto para a tela em vez de um 500.
        """
        agora = agora or datetime.now(timezone.utc)
        resultado = await self.sessao.execute(
            text(SQL_HOJE), {"agora": agora, "dt_hoje": agora.date()}
        )
        linha = resultado.mappings().all()
        return dict(linha[0]) if linha else None

    async def proximos(
        self, *, dt_hoje: date, limite: int = DIAS_DE_CACHE
    ) -> list[dict[str, Any]]:
        """Os desafios dos proximos dias — o cache invisivel."""
        resultado = await self.sessao.execute(
            text(SQL_PROXIMOS), {"dt_hoje": dt_hoje, "limite": limite}
        )
        return [dict(m) for m in resultado.mappings().all()]

    async def por_id(self, id_desafio: UUID) -> Optional[dict[str, Any]]:
        """Um desafio publicado, pelo identificador."""
        resultado = await self.sessao.execute(
            text(SQL_POR_ID), {"id_desafio": id_desafio}
        )
        linha = resultado.mappings().all()
        return dict(linha[0]) if linha else None
