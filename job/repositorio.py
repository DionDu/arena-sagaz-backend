"""A ESCRITA DO JOB no schema `desafio` (RF-DES-011a, T049b).

═══════════════════════════════════════════════════════════════════════════
QUEM ESCREVE AQUI E SO ELE
═══════════════════════════════════════════════════════════════════════════

O schema `desafio` e a **linha de producao**: posicao inicial, linha de chegada,
calibracao, gabarito e as medidas de saida do XP. ⛔ **A API nunca insere neste
schema** — e por isso `api/desafios/modelos_producao.py` declara so as VIEWs, sem
uma constante sequer com o nome de uma tabela. O `INSERT` mora aqui.

⚠️ **Leitura pela VIEW, escrita na tabela** — a convencao do projeto desde a
`0001`, e ela vale nos dois sentidos: os `SELECT` daqui vao a `vw…`, os `INSERT`
vao a `tb…`.

═══════════════════════════════════════════════════════════════════════════
⛔ A ORDEM DAS ESCRITAS NAO E LIVRE, E CADA PASSO TEM UM MOTIVO DIFERENTE
═══════════════════════════════════════════════════════════════════════════

    1. `tb903_perfil_dificuldade` e `tb904_motor`   ← **antes de tudo**
    2. `tb001_desafio`
    3. `tb002_medicao_regua` · `tb003_feito_desafio`
    4. `desafio_dia.tb001_desafio_dia`  ← **por ultimo**

**Por que o perfil vem primeiro.** `tb001_desafio` tem `fk001_perfil`, uma chave
estrangeira **composta** para `(co_versao_perfil, co_jogo, co_personagem)`.
Enquanto as oito linhas do perfil vigente nao existirem, ⛔ **o primeiro
`INSERT` de desafio falha** — depois de o job ter gerado e medido o candidato,
que e a parte cara. Gravar o perfil custa milissegundos e roda no comeco.

**E o motor vem junto, pelo mesmo motivo.** Desde a migracao `0022` (T049e) ha a
`fk002_motor`, composta para `(co_versao_motor, co_jogo)` em `tb904_motor` — a
dimensao que torna `damas-py-2f8e15cd` decifravel. Sao duas linhas, uma por jogo,
e elas custam a leitura de um manifesto.

**Por que o dia vem por ultimo.** Publicar o dia antes de copiar os feitos de
saida abriria uma janela em que o aplicativo baixaria um desafio **sem medidas**,
e ele pagaria so o piso de XP. ⚠️ Nada daria erro: o `INSERT` passa, a resposta
sai, e a diferenca so apareceria no extrato de quem jogou. E a mesma licao que
`job/reprise.py` ja registra sobre `SQL_COPIAR_FEITOS`.

═══════════════════════════════════════════════════════════════════════════
⚠️ `co_feito` E TEXTO AQUI DENTRO E `nu_feito` NO BANCO
═══════════════════════════════════════════════════════════════════════════

`job/medidas_de_saida.py` monta as linhas com a **chave** (`"caixas_fechadas"`),
que e o vocabulario compartilhado com o aplicativo. A coluna
`tb003_feito_desafio.nu_feito` e `SMALLINT` e referencia `tb902_catalogo_feito`.

A traducao acontece **no proprio `INSERT`**, por subconsulta na VIEW do catalogo.
⚠️ E isso e melhor que traduzir em Python antes: uma chave que nao existe faz a
subconsulta devolver `NULL`, e a coluna e `NOT NULL` — o banco recusa. Traduzir
antes exigiria carregar o catalogo inteiro so para descobrir o mesmo.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Optional, Sequence
from uuid import UUID

from sqlalchemy import text

from api.desafios.modelos_evento import VW_DESAFIO_DIA, encerramento_do_dia
from api.desafios.modelos_producao import (
    VW_CATALOGO_FEITO,
    VW_DESAFIO,
    VW_MOTOR,
    VW_TIPO_DESAFIO,
)

from .gravacao import SQL_PUBLICAR_O_DIA, LinhaDeDesafio
from .regua import Medicao

# ═══════════════════════════════════════════════════════════════════════════
# 1. O perfil de dificuldade — a dimensao que o JOB popula
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠️ **E o job que grava esta dimensao, nunca a migracao.** Uma migracao que
#: soubesse a taxa de erro da Cacau estaria publicando calibracao por `INSERT`, e
#: `data-model.md` diz isso com todas as letras. E por isso que
#: `scripts/conferir_migracao_desafio.py` conta **zero linhas** em
#: `tb903_perfil_dificuldade` num banco recem-migrado, e isso e o estado correto.
#:
#: ⚠️ `ON CONFLICT DO NOTHING` sobre `un001_perfil`: rodar o job duas vezes com o
#: mesmo perfil nao duplica nada, e — o que importa mais — **nao reescreve** a
#: linha existente. O `co_versao_perfil` deriva dos hashes dos contratos: se os
#: numeros mudaram, a versao mudou junto, e a linha e outra. Duas versoes convivem
#: de proposito, para que uma medicao antiga continue explicavel.
SQL_GRAVAR_PERFIL = """
INSERT INTO desafio.tb903_perfil_dificuldade
       (co_versao_perfil, co_jogo, co_personagem, js_perfil,
        co_arquivo, co_sha256)
VALUES (:co_versao_perfil, :co_jogo, :co_personagem,
        CAST(:js_perfil AS JSONB), :co_arquivo, :co_sha256)
ON CONFLICT (co_versao_perfil, co_jogo, co_personagem) DO NOTHING
RETURNING id_perfil
"""


# ═══════════════════════════════════════════════════════════════════════════
# 1b. O motor — a dimensao irma, e pelo mesmo motivo (T049e)
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠️ **Tambem e o job que grava, nunca a migracao**: uma migracao que soubesse o
#: hash do motor estaria afirmando, por `INSERT`, um fato sobre arquivos que ela
#: nao tem como conferir.
#:
#: ⚠️ `ON CONFLICT DO NOTHING` sobre `un001_motor`, e **nao** `DO UPDATE`: o
#: `co_versao_motor` deriva dos hashes do espelho, entao motor diferente e chave
#: diferente, e a linha existente descreve uma versao que ainda explica desafios
#: publicados. Reescreve-la apagaria a procedencia de tudo o que foi medido com
#: ela — e sem erro nenhum.
SQL_GRAVAR_MOTOR = """
INSERT INTO desafio.tb904_motor
       (co_versao_motor, co_jogo, js_motores, co_sha256, js_arquivos)
VALUES (:co_versao_motor, :co_jogo, CAST(:js_motores AS JSONB),
        :co_sha256, CAST(:js_arquivos AS JSONB))
ON CONFLICT (co_versao_motor, co_jogo) DO NOTHING
RETURNING id_motor
"""

#: As versoes de motor que ja estao em desafios publicados e ⛔ **nao existem na
#: dimensao**.
#:
#: ⚠️ **Isto existe para transformar uma falha futura em aviso de hoje.** A
#: `fk002_motor` nasceu `NOT VALID` — as linhas anteriores a `0022` ficaram como
#: estavam, porque inventar dimensao para elas seria o oposto do que a tabela
#: existe para fazer. So que a **reprise** copia o `co_versao_motor` da origem, e
#: uma copia e linha nova: se a origem for de antes da dimensao, o `INSERT` da
#: reprise bate na FK — no **pior dia operacional**, que e justamente aquele em
#: que a fila de aprovados secou e a reprise e o unico caminho.
#:
#: ⛔ **Le da VIEW**, como toda leitura do job.
SQL_MOTORES_ORFAOS = f"""
SELECT DISTINCT d.co_versao_motor, d.co_jogo
  FROM {VW_DESAFIO} d
 WHERE NOT EXISTS (
           SELECT 1
             FROM {VW_MOTOR} m
            WHERE m.co_versao_motor = d.co_versao_motor
              AND m.co_jogo         = d.co_jogo
       )
"""


# ═══════════════════════════════════════════════════════════════════════════
# 2. O desafio, a regua e as medidas de saida
# ═══════════════════════════════════════════════════════════════════════════

#: A linha de producao inteira, numa insercao so.
#:
#: ⚠️ **As colunas sao nomeadas uma a uma**, e nunca por posicao: a ordem das
#: colunas de uma tabela e coisa do banco, e um `INSERT` posicional passaria a
#: gravar no lugar errado no dia em que alguem acrescentasse coluna no meio —
#: calado, se os tipos combinarem.
#:
#: ⛔ **`co_curadoria` vem do parametro e nasce `candidato`** (RF-DES-012a). Nao
#: ha `DEFAULT 'candidato'` na tabela de proposito: um padrao faria a curadoria
#: virar opcional por acidente, e o primeiro esquecimento poria conteudo no ar
#: sem ninguem ter visto.
SQL_INSERIR_DESAFIO = """
INSERT INTO desafio.tb001_desafio
       (co_jogo, co_modalidade, co_variante,
        co_formato_posicao, js_posicao_inicial,
        nu_tipo_desafio, js_chegada, ic_chegada_encerra_partida,
        co_chave_objetivo, js_objetivo,
        co_personagem, nu_semente,
        js_solucao, nu_lances_solucao,
        nu_tempo_piso_ms, nu_tempo_teto_ms,
        nu_versao_catalogo,
        co_versao_minima, co_versao_perfil, co_versao_motor,
        nu_teto_log, co_curadoria)
VALUES (:co_jogo, :co_modalidade, :co_variante,
        :co_formato_posicao, CAST(:js_posicao_inicial AS JSONB),
        :nu_tipo_desafio, CAST(:js_chegada AS JSONB), :ic_chegada_encerra_partida,
        :co_chave_objetivo, CAST(:js_objetivo AS JSONB),
        :co_personagem, :nu_semente,
        CAST(:js_solucao AS JSONB), :nu_lances_solucao,
        :nu_tempo_piso_ms, :nu_tempo_teto_ms,
        :nu_versao_catalogo,
        :co_versao_minima, :co_versao_perfil, :co_versao_motor,
        :nu_teto_log, :co_curadoria)
RETURNING id_desafio
"""

#: Uma linha por mascote que tentou.
#:
#: ⚠️ `co_jogo` e `co_personagem` sao repetidos do desafio **de proposito**: e o
#: que fecha a `fk001_perfil` composta sem um `JOIN`. Eles saem da mesma linha que
#: acabou de ser gravada, e nao de um parametro solto — repetir o valor a mao aqui
#: abriria a chance de a medicao dizer que mediu um jogo e o desafio ser de outro.
SQL_INSERIR_MEDICAO = """
INSERT INTO desafio.tb002_medicao_regua
       (id_desafio, co_jogo, co_personagem, nu_execucoes, nu_resolveu,
        co_versao_perfil, co_versao_motor)
VALUES (:id_desafio, :co_jogo, :co_personagem, :nu_execucoes, :nu_resolveu,
        :co_versao_perfil, :co_versao_motor)
ON CONFLICT (id_desafio, co_personagem, co_versao_perfil) DO NOTHING
RETURNING id_medicao
"""

#: As medidas que este desafio produz, com peso e normalizacao.
#:
#: ⚠️ **A chave textual vira `nu_feito` por subconsulta.** Chave que nao existe no
#: catalogo devolve `NULL`, e `nu_feito` e `NOT NULL`: o banco recusa a linha. Uma
#: traducao feita em Python antes teria de reimplementar a mesma recusa, e a
#: primeira versao esquecida dela gravaria uma medida que nenhum jogo produz — a
#: parcela pagaria zero para sempre, sem erro nenhum.
SQL_INSERIR_FEITO = f"""
INSERT INTO desafio.tb003_feito_desafio
       (id_desafio, nu_feito, nu_ordem, vr_peso,
        co_normalizacao, vr_min, vr_max, co_sobre)
VALUES (:id_desafio,
        (SELECT c.nu_feito FROM {VW_CATALOGO_FEITO} c
          WHERE c.co_feito = :co_feito),
        :nu_ordem, :vr_peso,
        :co_normalizacao, :vr_min, :vr_max, :co_sobre)
RETURNING id_feito_desafio
"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. As leituras de que o planejamento precisa
# ═══════════════════════════════════════════════════════════════════════════

#: Que dias da janela ja tem desafio publicado.
#:
#: ⚠️ **Uma consulta so para a janela inteira**, e nao uma por dia: sao ate 30
#: dias, e trinta idas ao banco para responder *"a fila esta cheia?"* seria o
#: padrao N+1 no primeiro passo do job.
SQL_DIAS_PUBLICADOS = f"""
SELECT dt_dia
  FROM {VW_DESAFIO_DIA}
 WHERE dt_dia BETWEEN :dt_inicio AND :dt_fim
 ORDER BY dt_dia
"""

#: Os tipos publicados recentemente naquele jogo — o insumo do rodizio.
#:
#: ⚠️ **Olha para tras a partir de HOJE, e nao para a fila inteira.** O rodizio
#: existe para o dia nao parecer o de ontem; o que foi publicado ha tres meses nao
#: atrapalha ninguem, e considera-lo esgotaria a lista de tipos depressa demais —
#: com quatro tipos publicaveis, o rodizio deixaria de rodar.
#:
#: ⛔ E ele conta os dias **ja gravados**, inclusive os futuros: a fila cobre ate
#: 30 dias a frente, e ignorar o que ja esta agendado publicaria o mesmo tipo duas
#: vezes na mesma semana.
SQL_TIPOS_RECENTES = f"""
SELECT t.co_tipo_desafio
  FROM {VW_DESAFIO_DIA} dia
  JOIN {VW_DESAFIO} d      ON d.id_desafio      = dia.id_desafio
  JOIN {VW_TIPO_DESAFIO} t ON t.nu_tipo_desafio = d.nu_tipo_desafio
 WHERE d.co_jogo = :co_jogo
   AND dia.dt_dia BETWEEN :dt_inicio AND :dt_fim
 ORDER BY dia.dt_dia DESC
"""


#: ⛔ **A ASSINATURA DE UM DESAFIO — o cadeado contra repetir (T049i).**
#:
#: > *"Nao podemos ter desafios repetidos, a nao ser como fallback de reprise."*
#: > — o dono, 11/09/2026 (`DECISOES-do-dono.md` §8h)
#:
#: ⚠️ **Hoje nada impedia a repeticao, e ela ja aconteceu:** `SQL_TIPOS_RECENTES`
#: evita repetir o **tipo**, nao a **posicao** — e a mesma FEN
#: `B:W25,26,29:B2,13,17,21` saiu duas vezes em sete dias no `des`, com sementes
#: diferentes.
#:
#: ⚠️ **Mede-se contra o HISTORICO INTEIRO, e nao contra os 7 dias da fila.** Um
#: desafio e publicado **uma vez so** (determinacao do dono, 04/09/2026), e
#: repetir o de tres meses atras e exatamente o que a regra proibe. Por isso esta
#: consulta ⛔ **nao tem `BETWEEN`** — e a diferenca dela para as duas de cima.
#:
#: ⚠️ **Sem indice novo, e isso e conta e nao descuido:** `tb001_desafio` cresce
#: uma linha por dia, e em dez anos sao 3.650. Uma coluna de hash com `UNIQUE`
#: seria migracao para resolver problema que nao existe.
#:
#: ⛔ **`IS NOT DISTINCT FROM` e nao `=` no `co_modalidade`.** A coluna e nula no
#: Pontinhos, e em SQL `NULL = NULL` da `NULL`, nao `TRUE`: com `=`, **todo**
#: desafio de Pontinhos pareceria inedito, para sempre, e o cadeado protegeria
#: so as damas — calado, que e o pior jeito de falhar.
#:
#: ⚠️ **As reprises contam, e nao ha por que exclui-las.** Uma reprise tem a mesma
#: assinatura da origem, que ja esta aqui; encontrar uma ou outra da a mesma
#: resposta. ⛔ E o caminho da reprise nao passa por esta consulta: ele e
#: `job/reprise.py`, e continua permitido de proposito — a reprise e **copia com
#: identificador proprio**, e nao um desafio novo.
SQL_ASSINATURA_JA_PUBLICADA = f"""
SELECT d.id_desafio
  FROM {VW_DESAFIO} d
 WHERE d.co_tipo_desafio = :co_tipo_desafio
   AND d.co_modalidade IS NOT DISTINCT FROM :co_modalidade
   AND d.js_posicao_inicial = CAST(:js_posicao_inicial AS JSONB)
   AND d.js_chegada = CAST(:js_chegada AS JSONB)
 LIMIT 1
"""


class GravacaoDoJobFalhou(RuntimeError):
    """Uma escrita que deveria ter acontecido nao aconteceu.

    ⚠️ **Nao e o mesmo que "o dia ja estava publicado"**, que e resultado normal
    e devolve `None`. Isto aqui e o `INSERT` que voltou sem `RETURNING` quando
    deveria ter gravado — e seguir adiante deixaria um desafio pela metade.
    """


class RepositorioDoJob:
    """A escrita do job, com a ordem das operacoes embutida.

    ⛔ **Nao fecha a transacao sozinho** em nenhum metodo de escrita de desafio: e
    [publicar_desafio] que faz o `commit`, uma vez, depois de o conjunto inteiro
    estar gravado. Um `commit` por `INSERT` deixaria desafio sem medida no banco
    se a maquina caisse no meio — e ele iria ao ar pagando so o piso.
    """

    def __init__(self, sessao: Any) -> None:
        """Recebe uma `AsyncSession` (ou um duble com `execute`/`commit`)."""
        self.sessao = sessao

    # ── O perfil ────────────────────────────────────────────────────────────

    async def garantir_perfil(self, linhas: Sequence[Mapping[str, Any]]) -> int:
        """Grava as linhas do perfil vigente. Devolve quantas eram novas.

        Args:
            linhas: o que `job.perfil.linhas_da_dimensao()` produziu.

        Returns:
            Quantas linhas foram inseridas agora — ⚠️ **zero e o caso comum e
            saudavel**: o perfil so muda quando os contratos de dificuldade
            mudam, e ai a versao muda junto.

        ⛔ **Este e o primeiro passo do job, e nao um detalhe de arrumacao.** Sem
        estas linhas a `fk001_perfil` recusa o primeiro desafio — depois de toda
        a geracao e toda a medicao terem sido feitas.
        """
        import json

        novas = 0
        for linha in linhas:
            resultado = await self.sessao.execute(
                text(SQL_GRAVAR_PERFIL),
                {
                    "co_versao_perfil": linha["co_versao_perfil"],
                    "co_jogo": linha["co_jogo"],
                    "co_personagem": linha["co_personagem"],
                    # `default=str` porque o `js_perfil` traz numeros extraidos
                    # dos contratos, e um deles pode ser `Decimal` ou `Enum` —
                    # tipos que o `json` nao serializa sozinho. Virar texto e
                    # melhor que estourar: a coluna existe para **explicar**.
                    "js_perfil": json.dumps(
                        linha["js_perfil"], ensure_ascii=False, default=str
                    ),
                    "co_arquivo": linha["co_arquivo"],
                    "co_sha256": linha["co_sha256"],
                },
            )
            if resultado.first() is not None:
                novas += 1

        await self.sessao.commit()
        return novas

    # ── O motor ─────────────────────────────────────────────────────────────

    async def garantir_motor(self, linhas: Sequence[Mapping[str, Any]]) -> int:
        """Grava as linhas dos motores vigentes. Devolve quantas eram novas.

        Args:
            linhas: o que `job.motor.linhas_da_dimensao()` produziu — uma por
                jogo.

        Returns:
            Quantas foram inseridas agora. ⚠️ **Zero e o caso comum e saudavel**:
            a versao so muda quando o espelho do laboratorio muda.

        ⛔ **Roda no comeco, junto com o perfil, e nao e arrumacao.** Com a
        `fk002_motor` no lugar, sem estas linhas o primeiro `INSERT` de desafio
        falha — depois de toda a geracao e toda a medicao.
        """
        import json

        novas = 0
        for linha in linhas:
            resultado = await self.sessao.execute(
                text(SQL_GRAVAR_MOTOR),
                {
                    "co_versao_motor": linha["co_versao_motor"],
                    "co_jogo": linha["co_jogo"],
                    "js_motores": json.dumps(
                        linha["js_motores"], ensure_ascii=False
                    ),
                    "co_sha256": linha["co_sha256"],
                    # ⚠️ Sem `default=str` aqui, ao contrario do perfil: estes
                    # valores sao caminhos e hashes, todos texto. Um tipo
                    # inesperado neste JSON seria defeito de quem montou a lista,
                    # e converte-lo em silencio esconderia isso.
                    "js_arquivos": json.dumps(
                        linha["js_arquivos"], ensure_ascii=False
                    ),
                },
            )
            if resultado.first() is not None:
                novas += 1

        await self.sessao.commit()
        return novas

    async def motores_orfaos(self) -> list[str]:
        """As versoes de motor publicadas que a dimensao **nao** conhece.

        Returns:
            Uma lista de `"<co_jogo>/<co_versao_motor>"`, vazia no caso saudavel.

        ⚠️ **Existe para adiantar uma falha que so apareceria na reprise**, e no
        pior dia — ver a nota de [SQL_MOTORES_ORFAOS]. Quem chama **avisa**, e
        ⛔ nao muda o codigo de saida: sinal que dispara sempre ninguem le, e a
        licao ja custou caro em `fora_da_banda`.
        """
        resultado = await self.sessao.execute(text(SQL_MOTORES_ORFAOS))
        return [
            f"{linha['co_jogo']}/{linha['co_versao_motor']}"
            for linha in resultado.mappings().all()
        ]

    # ── As leituras ─────────────────────────────────────────────────────────

    async def dias_publicados(self, *, dt_inicio: date, dt_fim: date) -> list[date]:
        """Que dias da janela ja tem desafio."""
        resultado = await self.sessao.execute(
            text(SQL_DIAS_PUBLICADOS), {"dt_inicio": dt_inicio, "dt_fim": dt_fim}
        )
        return [linha["dt_dia"] for linha in resultado.mappings().all()]

    async def tipos_recentes(
        self, *, co_jogo: str, dt_inicio: date, dt_fim: date
    ) -> list[str]:
        """Os tipos daquele jogo publicados na janela, do mais recente ao mais
        antigo.

        ⚠️ Devolve **lista com repeticao**, e nao conjunto: quem chama pode querer
        saber que um tipo apareceu tres vezes, e transformar em conjunto e barato
        do outro lado. O contrario nao e verdade.
        """
        resultado = await self.sessao.execute(
            text(SQL_TIPOS_RECENTES),
            {"co_jogo": co_jogo, "dt_inicio": dt_inicio, "dt_fim": dt_fim},
        )
        return [linha["co_tipo_desafio"] for linha in resultado.mappings().all()]

    async def assinatura_ja_publicada(
        self,
        *,
        co_tipo_desafio: str,
        co_modalidade: Optional[str],
        js_posicao_inicial: Mapping[str, Any],
        js_chegada: Mapping[str, Any],
    ) -> Optional[UUID]:
        """Este desafio ja foi publicado alguma vez? (T049i)

        Args:
            co_tipo_desafio: a chave textual do tipo, e nao o `nu_tipo_desafio` —
                a VIEW ja traz as duas, e a textual e a que quem le o log entende.
            co_modalidade: `None` no Pontinhos. ⚠️ A consulta usa
                `IS NOT DISTINCT FROM` justamente para que o nulo case com o nulo.
            js_posicao_inicial, js_chegada: os dois JSON do candidato.

        Returns:
            O `id_desafio` do desafio anterior com a mesma assinatura, ou `None`
            se ele e inedito.

        ⚠️ **A comparacao e de JSONB, e nao de texto.** O Postgres normaliza
        `jsonb` — ordem de chave e espaco em branco nao contam —, entao dois
        candidatos iguais casam mesmo que o `json.dumps` os tenha escrito
        diferente. Comparar `::text` daria "inedito" para o mesmo tabuleiro com
        as chaves em outra ordem, e ⛔ nada denunciaria.
        """
        import json

        resultado = await self.sessao.execute(
            text(SQL_ASSINATURA_JA_PUBLICADA),
            {
                "co_tipo_desafio": co_tipo_desafio,
                "co_modalidade": co_modalidade,
                # `ensure_ascii=False` pelo mesmo motivo do `INSERT`: manter a
                # serializacao identica a que gravou a linha com que se compara.
                "js_posicao_inicial": json.dumps(
                    js_posicao_inicial, ensure_ascii=False
                ),
                "js_chegada": json.dumps(js_chegada, ensure_ascii=False),
            },
        )
        linha = resultado.mappings().first()
        return linha["id_desafio"] if linha else None

    async def taxa_observada(
        self, *, dt_inicio: date, dt_fim: date
    ) -> tuple[int, int]:
        """Quantas pessoas TENTARAM e quantas RESOLVERAM, na janela.

        Returns:
            `(nu_tentaram, nu_resolveram)`, somados sobre os dias da janela.

        ⚠️ **É o insumo do alvo móvel da régua** (`job/alvo_observado.py`): a
        banda de dificuldade começa fixa em 70–80% e passa a seguir a taxa real
        quando houver volume. Sem esta leitura, aquele módulo é código morto — e
        foi exatamente o que ele era até 10/09/2026.

        ⚠️ **Zero é a resposta esperada por muito tempo.** O alvo observado só
        entra com 200 tentativas; abaixo disso vale o fixo, e isso não é
        limitação temporária escondida: a taxa de 12 pessoas não diz nada sobre a
        dificuldade de um desafio.
        """
        from .alvo_observado import SQL_TAXA_OBSERVADA

        resultado = await self.sessao.execute(
            text(SQL_TAXA_OBSERVADA), {"dt_inicio": dt_inicio, "dt_fim": dt_fim}
        )
        linhas = resultado.mappings().all()
        return (
            sum(int(linha["nu_tentaram"]) for linha in linhas),
            sum(int(linha["nu_resolveram"]) for linha in linhas),
        )

    # ── A gravacao de um desafio inteiro ────────────────────────────────────

    async def publicar_desafio(
        self,
        *,
        dt_dia: date,
        linha: LinhaDeDesafio,
        medicoes: Sequence[Medicao],
        medidas: Sequence[Mapping[str, Any]],
    ) -> Optional[UUID]:
        """Grava o desafio, a regua, as medidas e **so entao** publica o dia.

        Args:
            dt_dia: o dia que este desafio cobre.
            linha: o que `job.gravacao.montar_linha(...)` produziu.
            medicoes: as linhas da regua, uma por mascote.
            medidas: as linhas de `job.medidas_de_saida`, ja conferidas.

        Returns:
            O `id_desafio` gravado, ou `None` quando o dia **ja estava
            publicado** — ⚠️ e isso nao e erro: e a idempotencia de RF-DES-013
            funcionando, e ela mora no `un001_dia` do banco, nunca numa checagem
            daqui.

        Raises:
            GravacaoDoJobFalhou: quando o `INSERT` do desafio nao devolveu id.

        ⛔ **Um `commit` so, no fim.** Ver o cabecalho da classe: commitar a cada
        passo deixaria, se a maquina caisse no meio, um desafio sem medidas de
        saida no banco — e a curadoria o aprovaria sem que nada aparentasse estar
        errado.

        ⚠️ **O dia e o ULTIMO `INSERT`.** Enquanto ele nao acontece, o desafio
        existe mas nao esta ligado a data nenhuma, e o aplicativo nao tem como
        chegar ate ele. E exatamente essa a propriedade que se quer: nada
        publicado pela metade.
        """
        import json

        resultado = await self.sessao.execute(
            text(SQL_INSERIR_DESAFIO),
            {
                "co_jogo": linha.co_jogo,
                "co_modalidade": linha.co_modalidade,
                "co_variante": linha.co_variante,
                "co_formato_posicao": linha.co_formato_posicao,
                "js_posicao_inicial": json.dumps(
                    linha.js_posicao_inicial, ensure_ascii=False
                ),
                "nu_tipo_desafio": linha.nu_tipo_desafio,
                "js_chegada": json.dumps(linha.js_chegada, ensure_ascii=False),
                "ic_chegada_encerra_partida": linha.ic_chegada_encerra_partida,
                "co_chave_objetivo": linha.co_chave_objetivo,
                "js_objetivo": json.dumps(linha.js_objetivo, ensure_ascii=False),
                "co_personagem": linha.co_personagem,
                "nu_semente": linha.nu_semente,
                "js_solucao": json.dumps(linha.js_solucao, ensure_ascii=False),
                "nu_lances_solucao": linha.nu_lances_solucao,
                "nu_tempo_piso_ms": linha.nu_tempo_piso_ms,
                "nu_tempo_teto_ms": linha.nu_tempo_teto_ms,
                "nu_versao_catalogo": linha.nu_versao_catalogo,
                "co_versao_minima": linha.co_versao_minima,
                "co_versao_perfil": linha.co_versao_perfil,
                "co_versao_motor": linha.co_versao_motor,
                "nu_teto_log": linha.nu_teto_log,
                "co_curadoria": linha.co_curadoria,
            },
        )
        gravado = resultado.first()
        if gravado is None:
            raise GravacaoDoJobFalhou(
                f"o INSERT do desafio de {dt_dia} nao devolveu id_desafio. ⛔ "
                "Seguir adiante publicaria um dia apontando para nada."
            )
        id_desafio = gravado["id_desafio"] if isinstance(gravado, Mapping) else gravado[0]

        for medicao in medicoes:
            await self.sessao.execute(
                text(SQL_INSERIR_MEDICAO),
                {
                    "id_desafio": id_desafio,
                    # ⚠️ Do DESAFIO, e nao de um parametro solto: a medicao nao
                    # pode dizer que mediu um jogo diferente do que foi medido.
                    "co_jogo": linha.co_jogo,
                    "co_personagem": medicao.co_personagem,
                    "nu_execucoes": medicao.nu_execucoes,
                    "nu_resolveu": medicao.nu_resolveu,
                    "co_versao_perfil": medicao.co_versao_perfil,
                    "co_versao_motor": medicao.co_versao_motor,
                },
            )

        for medida in medidas:
            await self.sessao.execute(
                text(SQL_INSERIR_FEITO),
                {
                    "id_desafio": id_desafio,
                    "co_feito": medida["co_feito"],
                    "nu_ordem": medida["nu_ordem"],
                    "vr_peso": medida["vr_peso"],
                    "co_normalizacao": medida["co_normalizacao"],
                    "vr_min": medida["vr_min"],
                    "vr_max": medida["vr_max"],
                    "co_sobre": medida["co_sobre"],
                },
            )

        publicacao = await self.sessao.execute(
            text(SQL_PUBLICAR_O_DIA),
            {
                "dt_dia": dt_dia,
                "id_desafio": id_desafio,
                "dh_encerramento": encerramento_do_dia(dt_dia),
            },
        )
        if publicacao.first() is None:
            # ⚠️ Outra execucao publicou este dia enquanto esta gerava. O
            # `ON CONFLICT (dt_dia) DO NOTHING` absorveu, e o desafio recem
            # gravado fica no banco como **candidato sem dia** — que e inofensivo
            # (ninguem chega a ele) e util (a curadoria o ve, e ele serve de
            # reserva). Desfazer tudo seria jogar fora minutos de CPU por causa
            # de uma corrida que o banco ja resolveu.
            await self.sessao.commit()
            return None

        await self.sessao.commit()
        return id_desafio


__all__ = [
    "SQL_DIAS_PUBLICADOS",
    "SQL_GRAVAR_PERFIL",
    "SQL_INSERIR_DESAFIO",
    "SQL_INSERIR_FEITO",
    "SQL_INSERIR_MEDICAO",
    "SQL_TIPOS_RECENTES",
    "GravacaoDoJobFalhou",
    "RepositorioDoJob",
]
