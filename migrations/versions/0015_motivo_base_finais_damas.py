"""Damas: o motivo `6 = base_finais` — o lance que ninguem buscou porque ja estava sabido.

Revision ID: 0015_motivo_base_finais_damas
Revises: 0014_versoes_motor_compostas
Create Date: 2026-08-27

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

Desde 26/08/2026 o Magno consulta uma **base de finais** antes de pensar: em
toda posicao de ate 4 pecas a resposta ja esta gravada no asset, com veredito
exato (vitoria, empate ou derrota) e distancia ate o fim. Nesses lances nao ha
arvore, nao ha nos e nao ha avaliacao — ha uma consulta.

O app grava esses lances com `co_motivo_parada_busca = 'base_finais'`, um valor
que **ainda nao existe na dimensao** `jogo_damas.tb902_motivo_parada_busca`.

⚠️ **Isto nunca quebrou nada, e a rede ja estava desenhada.** O catalogo tem o
sentinela `9999 = desconhecido` justamente para o caso de um app **mais novo**
que o backend: o valor cai nele e o texto cru vai para o `js_extra`. Foi assim
que o `lance_unico` viveu ate a `0013`, e foi por isso que ele nao derrubou a
sincronizacao de ninguem. O que se perde enquanto o codigo nao existe nao e
integridade — e legibilidade: os lances da base ficam contados junto com
"desconhecido", e ninguem consegue perguntar quantos foram.

── Por que `6`, e por que so isso ─────────────────────────────────────────

`1..4` sao os motivos de uma busca que **aconteceu** (profundidade, nos, tempo,
decidido). O `5` e o `lance_unico`, criado pela `0013`. O `6` e o proximo livre,
e ele e irmao do `5`, nao dos quatro primeiros: os dois dizem **"nao houve
busca"**, e sao os dois unicos em que a telemetria inteira e nula de proposito.

⚠️ **Esta migracao NAO acrescenta coluna e NAO mexe em view.** A `0013` precisou
refazer `vw002_jogada` porque acrescentava `co_motor_busca` a tabela, e o
`SELECT j.*` da view nao enxerga coluna criada depois. Aqui nao ha coluna nova:
o motivo entra na **dimensao**, e a view ja le `m.co_motivo_parada_busca` e
`m.no_motivo_parada_busca` pelo JOIN. Nada a refazer.

⚠️ **E os campos de busca continuam indo a NULL, nao a zero.** O mapeador do app
(`TelemetriaDaBuscaDamas.baseDeFinais`) deixa `qt_nos_visitados`,
`nu_profundidade_atingida`, `nu_tempo_busca_ms`, `nu_avaliacao_brancas` e
`co_motor_busca` **nulos**, exatamente como o `lance_unico`. Zero em
`nu_avaliacao_brancas` nao seria "sem informacao": significaria **posicao
equilibrada** — uma afirmacao falsa sobre uma posicao que nenhuma avaliacao
olhou. Foi o defeito que a `0013` corrigiu, e ele nao volta por esta porta.

⚠️ **`co_motor_busca` NULO tambem, e este e o ponto sutil.** `dart` e `rust`
respondem *"quem escolheu o lance"*. Na base ninguem escolheu: a resposta estava
gravada. Marcar um dos dois inflaria toda contagem "lances por motor" justamente
nos **finais**, que e onde os dois motores mais divergem — e num levantamento
que existe para compara-los.

── Como reconhecer os lances da base numa consulta ────────────────────────

Depois desta migracao, direto:

    WHERE co_motivo_parada_busca = 'base_finais'

Antes dela (nos dados ja gravados no DES), eles sao os que tem
`co_motivo_parada_busca = 'desconhecido'` **e** `js_extra` com o texto cru
`base_finais`. Nada os converte retroativamente, e isso e de proposito: o
projeto nao reescreve historico de log.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0015_motivo_base_finais_damas"
down_revision: Union[str, None] = "0014_versoes_motor_compostas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ⚠️ Os dois textos cabem, e isto ja custou uma migracao derrubada no DES em
    # 25/08 — por UM caractere. `co_motivo_parada_busca` e VARCHAR(20) e
    # `no_motivo_parada_busca` e VARCHAR(40):
    #
    #   'base_finais'                      = 11 de 20  ✓
    #   'Base de finais: ja estava sabido'  = 32 de 40  ✓
    #
    # O cadeado que passou a pegar isso e
    # `tests/unitarios/test_migracoes_cabem_nas_colunas.py`.
    #
    # `ON CONFLICT DO NOTHING` para a migracao ser reexecutavel sem erro — o
    # mesmo cuidado da `0013`.
    op.execute(
        """
        INSERT INTO jogo_damas.tb902_motivo_parada_busca
            (nu_motivo_parada_busca, co_motivo_parada_busca, no_motivo_parada_busca)
        VALUES
            (6, 'base_finais', 'Base de finais: ja estava sabido')
        ON CONFLICT (nu_motivo_parada_busca) DO NOTHING
        """
    )


def downgrade() -> None:
    # ⚠️ So sai se ninguem o estiver usando. Um DELETE cego violaria a FK de
    # `tb002_jogada.nu_motivo_parada_busca` e derrubaria o downgrade no meio,
    # deixando o banco num estado que nao e nem o de antes nem o de depois.
    # Mesma forma da `0013`.
    op.execute(
        """
        DELETE FROM jogo_damas.tb902_motivo_parada_busca
         WHERE nu_motivo_parada_busca = 6
           AND NOT EXISTS (
               SELECT 1 FROM jogo_damas.tb002_jogada
                WHERE nu_motivo_parada_busca = 6
           )
        """
    )
