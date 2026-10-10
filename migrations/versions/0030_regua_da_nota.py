"""A regua da nota do desafio, versionada por vigencia (T102, DECISOES-do-dono §8zzo).

Revision ID: 0030_regua_da_nota
Revises: 0029_ic_cpu_no_desafio
Create Date: 2026-10-10

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

Ate aqui os pesos da nota (`Q`) e o formato de cada parcela eram constantes no
codigo, escritas duas vezes (`api/desafios/extrato_xp.py` e
`lib/core/desafios/qualidade.dart`). Mudar um numero exigia versao nova do app,
e quem ficava na versao antiga calculava com a regua antiga. Em 10/10/2026 o dono
decidiu (§8zzo):

    "Os pesos e as constantes das curvas podem vir do desafio publicado."

e, ao aprovar esta modelagem, pediu **uma linha por parcela**:

    "Isso permitiria no futuro termos mais ou menos parcelas envolvidas no
     calculo dos XP."

═══════════════════════════════════════════════════════════════════════════
O CONCEITO: UMA REGUA COM DATA DE VIGENCIA
═══════════════════════════════════════════════════════════════════════════

`tb904_regua_nota` e o CABECALHO: uma linha por versao, com o dia a partir do
qual ela vale. `tb905_parcela_regua_nota` e o DETALHE: uma linha por parcela de
cada versao (tentativas, tempo, dica, merito), com o peso, a forma da curva e as
duas constantes.

O desafio de um dia e pontuado pela versao de **maior `dt_inicio_vigencia` que
ainda seja <= `dt_dia`**. ⚠️ Ninguem aponta o desafio para uma regua: a data
decide. E por isso esta migracao **nao toca** nenhum desafio publicado - apontar
os existentes seria `UPDATE`, e `test_migracoes_aditivas.py` proibe.

═══════════════════════════════════════════════════════════════════════════
AS DUAS CURVAS, COM AS MESMAS COLUNAS
═══════════════════════════════════════════════════════════════════════════

    linear:       q = 1 - (x - x0) / escala      (presa entre 0 e 1)
    hiperbolica:  q = 1 / (1 + (x - x0) / escala)

`x` e a MEDIDA da pessoa (tentativas, dicas, tempo em multiplos do piso), e nao
mora aqui. Abaixo de `x0`, nota cheia. A `escala` e "quanto e preciso piorar
para perder METADE da parcela" na hiperbolica, e "para zerar" na linear.

⚠️ **Escala, e nao `k = 1/escala`**: a versao 1 precisa de `k = 1/3`, e 0,333
gravado erraria o XP antigo na terceira casa. Com a escala, todo numero e exato.

O merito nao tem curva aqui: cada medida dele ja tem a regua propria em
`desafio.tb003_feito_desafio`. A linha dele so leva o peso.

═══════════════════════════════════════════════════════════════════════════
AS DUAS VERSOES QUE ENTRAM
═══════════════════════════════════════════════════════════════════════════

    versao 1 - a regua de 04/10/2026 (§8zs): linear, 30/30/15/25
    versao 2 - a regua de 10/10/2026 (§8zzo): hiperbolica, 50/15/20/15

⚠️ **A versao 1 vale desde 01/09/2026**, antes do primeiro desafio de qualquer
ambiente (des 29/09, prd 06/10). No `des`, os dias de antes de 04/10 foram
pontuados por uma regua anterior que nunca foi versionada; o XP gravado deles
**nao e recalculado** (nenhum e), e a versao 1 so serviria a um reenvio atrasado
de um daqueles dias.

⚠️ **A versao 2 vale a partir do DIA SEGUINTE ao da aplicacao desta migracao**,
em UTC - o dia do desafio e UTC (`api/desafios/repositorio.py`). A data e
calculada aqui, e nao escrita a mao, porque a decisao do dono (§8zzq) e uma
entrega so: a migracao roda imediatamente antes do deploy do backend, e "o dia
seguinte ao deploy" e o que impede que um mesmo dia tenha duas reguas no quadro.
⛔ `CURRENT_DATE` nao serve: ele depende do fuso da sessao do Postgres. ⚠️ Nao
aplicar no prd entre 20h30 e 21h de Brasilia (23h30-00h UTC): o deploy cairia no
dia seguinte, e alguns minutos dele seriam pontuados pelo codigo antigo.

═══════════════════════════════════════════════════════════════════════════
QUEM ESCREVE: SO MIGRACAO
═══════════════════════════════════════════════════════════════════════════

Nem o job nem o app escrevem aqui - como as dimensoes `tb901` a `tb903`. Mudar um
peso ou uma constante e uma versao nova, num `INSERT` de outra migracao. O schema
e `desafio_dia` porque converter feitos em XP e coisa da COLECAO (Bloco T: o teto
de 30/dia e do Desafio do Dia), e o job continua igual.

⚠️ **A soma dos pesos (1,000) atravessa linhas, e nao cabe num `CHECK`.** Quem a
garante e o teste da migracao (`test_regua_da_nota.py`) e o codigo que le a
regua, que recusa a versao cuja soma nao feche - sem valor padrao (RF-DES-223).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0030_regua_da_nota"
down_revision: Union[str, None] = "0029_ic_cpu_no_desafio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as duas tabelas, as duas VIEWs e insere as versoes 1 e 2."""
    # ── O cabecalho: uma linha por versao ───────────────────────────────────
    op.execute(
        """
        CREATE TABLE desafio_dia.tb904_regua_nota (
            nu_versao_regua    SMALLINT     PRIMARY KEY,
            dt_inicio_vigencia DATE         NOT NULL,
            de_motivo          VARCHAR(200) NOT NULL,
            dh_registro        TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT un001_inicio_vigencia UNIQUE (dt_inicio_vigencia),
            CONSTRAINT ck001_versao CHECK (nu_versao_regua > 0)
        )
        """
    )

    # ── O detalhe: uma linha por parcela de cada versao ─────────────────────
    #
    # ⚠️ A parcela e o `nu_tipo_xp` da dimensao que JA existe
    # (`tb901_tipo_xp_desafio`): e o mesmo codigo que cada linha do extrato
    # (`tb004_xp_desafio`) grava, entao a regua e o extrato falam o mesmo
    # vocabulario. Na VIEW ele aparece em texto (`co_tipo_xp`).
    op.execute(
        """
        CREATE TABLE desafio_dia.tb905_parcela_regua_nota (
            nu_versao_regua SMALLINT     NOT NULL
                REFERENCES desafio_dia.tb904_regua_nota(nu_versao_regua),
            nu_tipo_xp      SMALLINT     NOT NULL
                REFERENCES desafio_dia.tb901_tipo_xp_desafio(nu_tipo_xp),
            vr_peso         NUMERIC(4,3) NOT NULL,
            co_forma        VARCHAR(20)  NOT NULL,
            vr_x0           NUMERIC(6,3),
            vr_escala       NUMERIC(6,3),
            dh_registro     TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT pk001_parcela_regua PRIMARY KEY (nu_versao_regua,
                                                        nu_tipo_xp),
            CONSTRAINT ck001_peso CHECK (vr_peso > 0 AND vr_peso <= 1),
            CONSTRAINT ck002_forma CHECK (co_forma IN
                ('linear', 'hiperbolica', 'merito')),
            CONSTRAINT ck003_parcela CHECK (nu_tipo_xp IN (2, 3, 4, 5)),
            CONSTRAINT ck004_merito CHECK ((co_forma = 'merito') =
                                           (nu_tipo_xp = 5)),
            CONSTRAINT ck005_curva CHECK (
                (co_forma = 'merito'
                    AND vr_x0 IS NULL AND vr_escala IS NULL)
                OR (co_forma = 'hiperbolica'
                    AND vr_x0 IS NOT NULL AND vr_escala > 0)
                OR (co_forma = 'linear'
                    AND vr_x0 IS NOT NULL
                    AND (vr_escala > 0
                         OR (vr_escala IS NULL AND nu_tipo_xp = 3))))
        )
        """
    )

    # ⚠️ Colunas nomeadas UMA A UMA, e nao `SELECT *`: uma VIEW criada com `*`
    # NAO enxerga coluna acrescentada depois (licao da `0017`).
    op.execute(
        """
        CREATE VIEW desafio_dia.vw904_regua_nota AS
        SELECT nu_versao_regua, dt_inicio_vigencia, de_motivo, dh_registro
          FROM desafio_dia.tb904_regua_nota
        """
    )
    op.execute(
        """
        CREATE VIEW desafio_dia.vw905_parcela_regua_nota AS
        SELECT p.nu_versao_regua, r.dt_inicio_vigencia, p.nu_tipo_xp,
               t.co_tipo_xp, p.vr_peso, p.co_forma, p.vr_x0, p.vr_escala,
               p.dh_registro
          FROM desafio_dia.tb905_parcela_regua_nota p
          JOIN desafio_dia.tb904_regua_nota r
            ON r.nu_versao_regua = p.nu_versao_regua
          JOIN desafio_dia.tb901_tipo_xp_desafio t
            ON t.nu_tipo_xp = p.nu_tipo_xp
        """
    )

    # ── As versoes ──────────────────────────────────────────────────────────
    #
    # ⚠️ A data da versao 2 e CALCULADA: o dia seguinte ao da aplicacao, em
    # UTC. Ver o cabecalho.
    op.execute(
        """
        INSERT INTO desafio_dia.tb904_regua_nota
            (nu_versao_regua, dt_inicio_vigencia, de_motivo) VALUES
            (1, DATE '2026-09-01',
             'Regua de 04/10/2026 (DECISOES-do-dono 8zs): linear com teto, '
             'pesos 30/30/15/25'),
            (2, CAST((now() AT TIME ZONE 'UTC') AS DATE) + 1,
             'Regua de 10/10/2026 (DECISOES-do-dono 8zzo): hiperbolica sem teto, '
             'pesos 50/15/20/15; vale do dia seguinte a esta migracao')
        """
    )
    # Os `nu_tipo_xp`: 2 = tentativas, 3 = tempo, 4 = dica, 5 = merito
    # (`tb901_tipo_xp_desafio`, migracao 0019).
    #
    # Versao 1, linear: tentativas `1 - (n-1)/3` (zera na 4a); tempo ate o
    # `nu_tempo_teto_ms` do desafio (escala vazia); dica `1 - d/2`.
    # Versao 2, hiperbolica: tentativas `1/n`; tempo `2/(1 + t/piso)`; dica
    # `2/(2 + d)`.
    op.execute(
        """
        INSERT INTO desafio_dia.tb905_parcela_regua_nota
            (nu_versao_regua, nu_tipo_xp, vr_peso, co_forma, vr_x0, vr_escala)
        VALUES
            (1, 2, 0.300, 'linear',      1, 3),
            (1, 3, 0.300, 'linear',      1, NULL),
            (1, 4, 0.150, 'linear',      0, 2),
            (1, 5, 0.250, 'merito',      NULL, NULL),
            (2, 2, 0.500, 'hiperbolica', 1, 1),
            (2, 3, 0.150, 'hiperbolica', 1, 2),
            (2, 4, 0.200, 'hiperbolica', 0, 2),
            (2, 5, 0.150, 'merito',      NULL, NULL)
        """
    )

    op.execute(
        "COMMENT ON TABLE desafio_dia.tb904_regua_nota IS "
        "'Versoes da regua da nota do desafio. Vale para um dia a de maior "
        "dt_inicio_vigencia <= dt_dia. Escrita so por migracao (T102, 8zzo).'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio_dia.tb905_parcela_regua_nota.vr_x0 IS "
        "'Ate onde a medida nao perde nada: 1a tentativa, 0 dica, o piso de "
        "tempo (em multiplos do piso).'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio_dia.tb905_parcela_regua_nota.vr_escala IS "
        "'Quanto a medida precisa piorar para perder metade da parcela "
        "(hiperbolica) ou para zera-la (linear). Vazia so no tempo linear: "
        "ai a regua vai ate o nu_tempo_teto_ms do desafio.'"
    )


def downgrade() -> None:
    """Derruba as VIEWs e as tabelas.

    ⚠️ **So para o ambiente local**, como no resto do projeto - o teste de
    migracao aditiva ignora o `downgrade()`.
    """
    op.execute("DROP VIEW IF EXISTS desafio_dia.vw905_parcela_regua_nota")
    op.execute("DROP VIEW IF EXISTS desafio_dia.vw904_regua_nota")
    op.execute("DROP TABLE IF EXISTS desafio_dia.tb905_parcela_regua_nota")
    op.execute("DROP TABLE IF EXISTS desafio_dia.tb904_regua_nota")
