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

import json
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
    VW_XP_DESAFIO,
)
from api.desafios.extrato_xp import (
    FEITO_DICAS,
    FEITO_TEMPO,
    FEITO_TENTATIVAS,
)
from api.desafios.modelos_producao import (
    VW_CATALOGO_FEITO,
    VW_DESAFIO,
    VW_FEITO_DESAFIO,
)

#: A partida que o log ja trouxe, pelo `co_evento` do aplicativo.
#:
#: ⚠️ **`id_usuario` entra na condicao.** Sem isso, alguem poderia amarrar a
#: resolucao dele a uma partida de outra pessoa — e o replay do quadro passaria a
#: mostrar a partida errada.
#:
#: ⚠️ **`qt_usos_poder` vem junto desde 10/10/2026** (T109, `DECISOES-do-dono.md`
#: §8zzo): e dele que o servidor tira as dicas da tentativa para a
#: `tb005_poder_consumido` - ver [SQL_GRAVAR_DICAS_DA_PARTIDA].
SQL_PARTIDA_POR_EVENTO = """
SELECT id_partida, co_status, co_modo, dh_inicio, dh_fim, qt_usos_poder
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

#: A regua de tempo daquele desafio, para a parcela `q_tempo` da auditoria.
#:
#: ⚠️ **Sao do DESAFIO, e nao constantes do servidor** (RF-DES-223): o piso e o
#: gabarito jogado direto, o teto e onde a parcela zera. Um final de 3 lances e
#: uma abertura de 12 nao pedem a mesma pressa.
SQL_REGUA_DE_TEMPO = f"""
SELECT nu_tempo_piso_ms, nu_tempo_teto_ms
  FROM {VW_DESAFIO}
 WHERE id_desafio = :id_desafio
"""

#: A direcao das tres chaves de sessao, lida da dimensao.
#:
#: ⛔ **Lida, e nunca escrita no codigo.** Mais tentativas, mais tempo e mais
#: dicas reduzem o XP porque `tb902_catalogo_feito.co_direcao` diz `menor_melhor`
#: - e uma parcela na direcao errada **nao daria erro nenhum**, so pagaria mais a
#: quem jogou pior. Escrever a direcao aqui seria escreve-la uma segunda vez.
SQL_DIRECOES_DE_SESSAO = f"""
SELECT co_feito, co_direcao
  FROM {VW_CATALOGO_FEITO}
 WHERE co_feito = ANY(:chaves)
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
        nu_xp, nu_versao_catalogo, dh_resolucao, js_feito)
VALUES (:id_desafio_dia, :id_usuario, :id_tentativa, :nu_lance,
        :nu_xp, :nu_versao_catalogo, :dh_resolucao,
        CAST(:js_feito AS JSONB))
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

#: As dicas da partida, gravadas pelo SERVIDOR (T109, `DECISOES-do-dono.md`
#: §8zzo, 10/10/2026).
#:
#: ⚠️ **Por que o servidor, e nao o aplicativo.** O app mandava cada dica no meio
#: da partida com o `co_evento` dela, e esse `co_evento` so nasce na 1a leva da
#: gravacao (no instante do objetivo, ou no fim). Durante a partida ele era
#: sempre nulo, e o envio desistia em silencio: a `tb005` chegou a 10/10/2026 com
#: ZERO linhas no `prd`, com 4 dicas gastas. A partida, essa sim, chega com
#: `qt_usos_poder` - entao o servidor reconstroi as linhas a partir dela, no
#: unico ponto em que ele liga partida, tentativa e dia: a gravacao da tentativa.
#: Vale para toda versao do app, inclusive a 1.3.0.
#:
#: Uma linha por dica: `nu_grau` de 1 ate a quantidade (`generate_series` gera a
#: sequencia 1, 2, ... dentro do proprio SQL). ⚠️ **`LEAST(..., 2)`** porque o
#: teto e de 2 por TENTATIVA (o `ck001_grau` so aceita 1 e 2): um numero podre
#: do cliente gravaria as duas e pararia, em vez de derrubar a tentativa inteira
#: com erro 500.
#:
#: ⚠️ **`dh_consumo` = o INICIO da partida, e e uma aproximacao**: o instante
#: real de cada dica nao chega ao servidor. Para a unica conta que o usa (as
#: dicas "ate a resolucao", em [SQL_SESSAO_NO_SERVIDOR]) a aproximacao da o
#: mesmo resultado: a dica de uma tentativa conta para a resolucao que veio
#: depois do inicio dela.
#:
#: ⚠️ **Os `CAST` sao necessarios**: num `INSERT ... SELECT`, o parametro na
#: lista do `SELECT` chega ao Postgres sem tipo, e o driver (asyncpg) recusa o
#: que nao sabe tipar.
#:
#: `ON CONFLICT DO NOTHING`: o reenvio da mesma tentativa, ou a dica que a rota
#: antiga ja tinha gravado com o mesmo grau, nao duplica nada.
SQL_GRAVAR_DICAS_DA_PARTIDA = f"""
INSERT INTO {TB_PODER_CONSUMIDO}
       (id_tentativa, nu_tipo_poder, nu_grau, dh_consumo)
SELECT CAST(:id_tentativa AS UUID), 1, g.nu_grau,
       CAST(:dh_consumo AS TIMESTAMPTZ)
  FROM generate_series(1, LEAST(CAST(:qt_usos_poder AS INT), 2)) AS g(nu_grau)
ON CONFLICT (id_tentativa, nu_tipo_poder, nu_grau) DO NOTHING
"""

#: Quantas dicas ja foram gastas **nesta tentativa** (T108).
#:
#: ⚠️ **O teto passou a ser por TENTATIVA em 10/10/2026** (`DECISOES-do-dono.md`
#: §8zzo, decisao 1): cada tentativa recomeca com as duas. Ate ali a conta somava
#: o dia, e quem errava depois de gastar as duas ficava obrigado a lembrar o que
#: o app tinha sugerido. O "dicas infinitas a quem reabrisse" que a regra antiga
#: temia agora e cobrado na NOTA: todas as dicas de todas as tentativas contam.
SQL_DICAS_DA_TENTATIVA = """
SELECT COUNT(*) AS qt
  FROM desafio_dia.vw005_poder_consumido p
 WHERE p.id_tentativa = :id_tentativa
   AND p.co_tipo_poder = 'dica'
"""

#: Quantas dicas a pessoa gastou **no dia**, somando as tentativas.
#:
#: ⚠️ **Desde 10/10/2026 este total NAO e mais o teto do botao** (esse e por
#: tentativa, [SQL_DICAS_DA_TENTATIVA]): e o que entra na NOTA (`DECISOES-do-dono.md`
#: §8zzo, decisao 2 - todas as dicas de todas as tentativas). Quem o le e o
#: `meu-dia`, para o aparelho que chega sem historico (outro aparelho, login
#: novo) saber quantas dicas o dia ja custou.
SQL_DICAS_DO_DESAFIO = f"""
SELECT COUNT(*) AS qt
  FROM desafio_dia.vw005_poder_consumido p
  JOIN {VW_TENTATIVA} t
    ON t.id_tentativa = p.id_tentativa
 WHERE t.id_desafio_dia = :id_desafio_dia
   AND t.id_usuario = :id_usuario
   AND p.co_tipo_poder = 'dica'
"""


#: O que o SERVIDOR sabe da sessao ate esta tentativa: quantas tentativas e
#: quantas dicas (T085zf, `DECISOES-do-dono.md` §8zf).
#:
#: E a contagem que corrige a do aplicativo quando ela veio MENOR - o convidado
#: que comeca o dia do zero no aparelho, ou dois aparelhos sem rede.
#:
#: ⚠️ **Tentativas pela hora de INICIO da partida, e ⛔ pela ordem de chegada**
#: (`nu_sequencia`): a falha jogada DEPOIS da resolucao, num aparelho que subiu a
#: fila antes, chega primeiro e ⛔ foi tentativa antes dela.
#:
#: ⚠️ **E a linha que so a DICA criou nao conta, se nada a fechou**: a dica cria
#: a tentativa no meio da partida, com tempo ZERO (`registrar_dica`); quem larga
#: a partida depois ⛔ manda envio nenhum, e o aplicativo ⛔ conta a largada no
#: parcela de tentativas (`registrarAPartidaLargada`). Contar essa linha puniria quem jogou
#: honesto. A tentativa fechada por envio tem o tempo da partida (> 0), ou
#: resolveu; e a desta resolucao conta sempre.
#:
#: ⚠️ **Dicas ate o instante da resolucao** (`dh_consumo <= :ate`): a dica paga
#: numa tentativa de depois ⛔ ajudou esta. E a mesma regra do aplicativo (o
#: total do DESAFIO ate ali).
SQL_SESSAO_NO_SERVIDOR = f"""
SELECT
  (SELECT COUNT(*)
     FROM {VW_TENTATIVA} t
    WHERE t.id_desafio_dia = :id_desafio_dia
      AND t.id_usuario = :id_usuario
      AND t.dh_inicio <= (SELECT a.dh_inicio
                            FROM {VW_TENTATIVA} a
                           WHERE a.id_tentativa = :id_tentativa)
      AND (t.ic_resolveu OR t.nu_tempo_ms > 0
           OR t.id_tentativa = :id_tentativa)) AS tentativas,
  (SELECT COUNT(*)
     FROM desafio_dia.vw005_poder_consumido p
     JOIN {VW_TENTATIVA} t
       ON t.id_tentativa = p.id_tentativa
    WHERE t.id_desafio_dia = :id_desafio_dia
      AND t.id_usuario = :id_usuario
      AND p.co_tipo_poder = 'dica'
      AND p.dh_consumo <= :ate) AS dicas
"""

#: A chave de feito existe na dimensao? Usada so quando ela nao pesa no desafio.
SQL_FEITO_NO_CATALOGO = f"""
SELECT 1
  FROM {VW_CATALOGO_FEITO}
 WHERE co_feito = :co_feito
"""

#: O que o Desafio do Dia ja pos na conta da pessoa **neste dia** (T082).
#:
#: ⚠️ **A resolucao entra pelo `nu_xp` dela, e ⛔ nao pela soma das parcelas**:
#: as parcelas tem casas decimais (`26,896`), e o que o aplicativo mostrou e o
#: que a conta recebeu e o inteiro arredondado uma vez (`27`). Consolo e ajuste
#: ja sao inteiros, gravados como `10,000` e `-7,000`.
#:
#: ⚠️ **Pelas VIEWs**, como toda leitura do projeto: `vw004_xp_desafio` ja traz o
#: `co_tipo_xp` resolvido, e o filtro fica pelo nome e ⛔ por um numero solto.
SQL_CREDITADO_NO_DIA = f"""
SELECT
  COALESCE((SELECT SUM(x.vr_xp)
              FROM {VW_XP_DESAFIO} x
             WHERE x.id_desafio_dia = :id_desafio_dia
               AND x.id_usuario = :id_usuario
               AND x.co_tipo_xp IN ('consolo', 'ajuste')), 0)
  + COALESCE((SELECT r.nu_xp
                FROM {VW_RESOLUCAO} r
               WHERE r.id_desafio_dia = :id_desafio_dia
                 AND r.id_usuario = :id_usuario), 0)
    AS ja_creditado,
  EXISTS (SELECT 1
            FROM {VW_XP_DESAFIO} x
           WHERE x.id_desafio_dia = :id_desafio_dia
             AND x.id_usuario = :id_usuario
             AND x.co_tipo_xp = 'consolo')
    AS tem_consolo
"""

#: Soma o credito do dia ao XP da conta — o numero que o ranking ordena (T082).
#:
#: ⚠️ **Escreve em `progressao`, fora do schema do desafio, e de proposito**: e a
#: mesma tabela que o ingestor de partidas incrementa (`_incrementar_progressao`,
#: na sincronizacao), e e a unica forma de o XP do desafio chegar ao ranking.
#: Sem isto a pessoa via *"+27 XP"* na tela e o ranking nunca mudava.
#:
#: ⚠️ **Soma, e ⛔ `GREATEST`**: este e um EVENTO, como a partida. A reconciliacao
#: por `GREATEST` do aplicativo so roda com a fila vazia - quando este credito ja
#: entrou -, entao ela encontra o mesmo numero e nao soma de novo.
#:
#: ⚠️ **O `INSERT` cria a linha de quem nunca pontuou numa partida**: quem so
#: joga o desafio ⛔ tem linha de progressao nenhuma, e um `UPDATE` sozinho
#: perderia o XP dele em silencio. So o XP e os carimbos mudam; ⛔ partidas,
#: vitorias e derrotas nao: o desafio ⛔ e uma partida (RF-DES-045).
SQL_CREDITAR_NA_CONTA = """
INSERT INTO progressao.tb001_progressao_usuario AS prog
  (id_progressao, id_usuario, nu_xp_total,
   nu_partidas, nu_vitorias, nu_derrotas, nu_empates, dh_atualizacao)
VALUES
  (gen_random_uuid(), :id_usuario, :xp, 0, 0, 0, 0, now())
ON CONFLICT (id_usuario) DO UPDATE SET
  nu_xp_total = prog.nu_xp_total + EXCLUDED.nu_xp_total,
  dh_atualizacao = now()
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

    async def regua_de_tempo(self, id_desafio: UUID) -> Optional[dict[str, Any]]:
        """`{nu_tempo_piso_ms, nu_tempo_teto_ms}` daquele desafio, ou `None`.

        ⚠️ **`None` nao e "use o padrao"** - e desafio inexistente. Quem chama
        trata, e ⛔ nao arbitra 30 s/180 s: um padrao plausivel faria a auditoria
        conferir contra uma regua inventada e acusar divergencia onde nao ha.
        """
        resultado = await self.sessao.execute(
            text(SQL_REGUA_DE_TEMPO), {"id_desafio": id_desafio}
        )
        linhas = resultado.mappings().all()
        return dict(linhas[0]) if linhas else None

    async def direcoes_de_sessao(self) -> dict[str, str]:
        """A direcao das tres chaves de sessao, lida da dimensao.

        Returns:
            `{co_feito: co_direcao}`. ⚠️ Chave que faltar simplesmente nao vem,
            e quem monta o extrato estoura ao procura-la - que e o certo: sem a
            direcao nao ha como saber para que lado a parcela corre.
        """
        resultado = await self.sessao.execute(
            text(SQL_DIRECOES_DE_SESSAO),
            {"chaves": [FEITO_TENTATIVAS, FEITO_TEMPO, FEITO_DICAS]},
        )
        return {m["co_feito"]: m["co_direcao"] for m in resultado.mappings().all()}

    async def dicas_da_tentativa(self, *, id_tentativa: UUID) -> int:
        """Quantas dicas a pessoa ja gastou **nesta tentativa** (T108)."""
        resultado = await self.sessao.execute(
            text(SQL_DICAS_DA_TENTATIVA), {"id_tentativa": id_tentativa}
        )
        return int(resultado.scalar_one())

    async def sessao_no_servidor(
        self,
        *,
        id_desafio_dia: UUID,
        id_usuario: str,
        id_tentativa: UUID,
        ate: datetime,
    ) -> tuple[int, int]:
        """`(tentativas, dicas)` que o servidor conta ate esta tentativa.

        ⚠️ Lida **depois** de gravar a tentativa: ela entra na propria conta.
        A regra de o que conta esta em [SQL_SESSAO_NO_SERVIDOR].
        """
        resultado = await self.sessao.execute(
            text(SQL_SESSAO_NO_SERVIDOR),
            {
                "id_desafio_dia": id_desafio_dia,
                "id_usuario": id_usuario,
                "id_tentativa": id_tentativa,
                "ate": ate,
            },
        )
        linha = resultado.mappings().one()
        return int(linha["tentativas"]), int(linha["dicas"])

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
        js_feito: dict[str, Any],
    ) -> tuple[UUID, bool]:
        """Grava a resolucao, ou devolve a que ja existia.

        - [js_feito]: o retrato do instante do objetivo (T085za) - ver
          `api/desafios/retrato.py`. ⚠️ Vai como texto e o `CAST` o faz JSONB:
          o driver ⛔ converte `dict` sozinho.

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
                "js_feito": json.dumps(js_feito, ensure_ascii=False),
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

    async def creditado_no_dia(
        self, *, id_desafio_dia: UUID, id_usuario: str
    ) -> tuple[int, bool]:
        """O que o Desafio do Dia ja creditou hoje, e se o consolo ja entrou.

        Returns:
            `(ja_creditado, tem_consolo)`. ⚠️ `ja_creditado` e inteiro por
            construcao (ver [SQL_CREDITADO_NO_DIA]); o `int()` so desfaz o
            `Decimal` que o `NUMERIC` devolve.
        """
        resultado = await self.sessao.execute(
            text(SQL_CREDITADO_NO_DIA),
            {"id_desafio_dia": id_desafio_dia, "id_usuario": id_usuario},
        )
        linha = resultado.mappings().one()
        return int(linha["ja_creditado"]), bool(linha["tem_consolo"])

    async def creditar_na_conta(self, *, id_usuario: str, xp: int) -> None:
        """Soma [xp] ao `nu_xp_total` da conta. ⚠️ Zero nao chega a ir ao banco."""
        if xp <= 0:
            return
        await self.sessao.execute(
            text(SQL_CREDITAR_NA_CONTA), {"id_usuario": id_usuario, "xp": xp}
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

    async def gravar_dicas_da_partida(
        self, *, id_tentativa: UUID, qt_usos_poder: int, dh_consumo: datetime
    ) -> None:
        """Grava na `tb005` as dicas que a partida diz ter usado (T109).

        A regra (e as aproximacoes dela) esta em [SQL_GRAVAR_DICAS_DA_PARTIDA].
        ⚠️ Zero nao chega a ir ao banco: `generate_series(1, 0)` nao gera linha
        nenhuma, mas a viagem seria gasta a toa na maioria das tentativas.
        """
        if qt_usos_poder <= 0:
            return
        await self.sessao.execute(
            text(SQL_GRAVAR_DICAS_DA_PARTIDA),
            {
                "id_tentativa": id_tentativa,
                "qt_usos_poder": qt_usos_poder,
                "dh_consumo": dh_consumo,
            },
        )

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
