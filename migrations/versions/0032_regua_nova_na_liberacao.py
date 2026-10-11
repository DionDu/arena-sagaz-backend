"""A regua nova vale a partir da liberacao da 1.3.1 (versao 4; DECISOES-do-dono §8zzr).

Revision ID: 0032_regua_nova_na_liberacao
Revises: 0031_regua_antiga_ate_liberar
Create Date: 2026-10-11

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

E a segunda metade do conserto da `0031`. Aquela devolveu os numeros da versao 1
a partir de 13/10/2026; esta poe os numeros da versao 2 (a regua da §8zzo:
hiperbolica, 50/15/20/15) valendo a partir do **dia seguinte ao da aplicacao**,
como versao 4. O dono decidiu QUANDO (§8zzr):

    "o melhor e aplicarmos a migracao apenas na hora que estiver disponivel
     pra mim liberar o App nas lojas apos a revisao."

⚠️ **No `prd` ela e aplicada pelo dono, depois que as DUAS lojas aprovarem a
1.3.1, imediatamente antes do clique de liberacao.** As lojas seguram a
publicacao ate la (App Store Connect: "liberar esta versao manualmente"; Google
Play: publicacao gerenciada). ⛔ Nao aplicar entre 20h30 e 21h de Brasilia
(23h30-00h UTC): o "dia seguinte" em UTC comecaria minutos depois, e a regua
nova passaria a valer antes de a 1.3.1 chegar a alguem.

═══════════════════════════════════════════════════════════════════════════
A DATA: O DIA SEGUINTE, MAS NUNCA ANTES DE 14/10/2026
═══════════════════════════════════════════════════════════════════════════

    GREATEST(<hoje em UTC> + 1, DATE '2026-10-14')

`CAST((now() AT TIME ZONE 'UTC') AS DATE) + 1` e a mesma conta da `0030`: o dia
do desafio e UTC (`api/desafios/repositorio.py`), e ⛔ `CURRENT_DATE` nao serve,
porque depende do fuso da sessao do Postgres.

⚠️ **O piso de 14/10 e o que impede dois defeitos calados**, ambos possiveis se
a migracao rodar antes de 13/10 - o que acontece no `des`, onde ela entra junto
com a `0031`:

  · aplicada em 11/10, a data sairia 12/10, ANTES da versao 3 (13/10). Pela
    regra (vale a de maior vigencia <= o dia), a versao 3 venceria de 13/10 em
    diante PARA SEMPRE, e a regua nova nunca valeria - sem erro nenhum;
  · aplicada em 12/10, a data sairia 13/10, a mesma da versao 3, e a
    `un001_inicio_vigencia` recusaria o `INSERT` (esse ao menos grita).

`GREATEST` devolve o maior dos dois valores. No `prd` a liberacao vem depois de
dias de revisao, e o piso nunca decide; ele esta aqui pelo caso que ninguem
planejou.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0032_regua_nova_na_liberacao"
down_revision: Union[str, None] = "0031_regua_antiga_ate_liberar"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insere a versao 4 (os numeros da versao 2), do dia seguinte em diante."""
    # ── O cabecalho da versao 4 ─────────────────────────────────────────────
    #
    # ⚠️ A data e CALCULADA, com o piso de 14/10: ver o cabecalho do arquivo.
    op.execute(
        """
        INSERT INTO desafio_dia.tb904_regua_nota
            (nu_versao_regua, dt_inicio_vigencia, de_motivo) VALUES
            (4, GREATEST(CAST((now() AT TIME ZONE 'UTC') AS DATE) + 1,
                         DATE '2026-10-14'),
             'Os numeros da versao 2 (DECISOES-do-dono 8zzo e 8zzr): vale do '
             'dia seguinte a liberacao da 1.3.1 nas lojas')
        """
    )
    # ── As parcelas: as MESMAS quatro linhas da versao 2 da `0030` ──────────
    #
    # Os `nu_tipo_xp`: 2 = tentativas, 3 = tempo, 4 = dica, 5 = merito.
    #
    # Hiperbolica, `1 / (1 + (x - x0) / escala)`: tentativas `1/n`; tempo
    # `2/(1 + t/piso)` (o tempo em multiplos do piso); dica `2/(2 + d)`.
    op.execute(
        """
        INSERT INTO desafio_dia.tb905_parcela_regua_nota
            (nu_versao_regua, nu_tipo_xp, vr_peso, co_forma, vr_x0, vr_escala)
        VALUES
            (4, 2, 0.500, 'hiperbolica', 1, 1),
            (4, 3, 0.150, 'hiperbolica', 1, 2),
            (4, 4, 0.200, 'hiperbolica', 0, 2),
            (4, 5, 0.150, 'merito',      NULL, NULL)
        """
    )


def downgrade() -> None:
    """Tira a versao 4.

    ⚠️ **So para o ambiente local**, como no resto do projeto - o teste de
    migracao aditiva ignora o `downgrade()`, e no `des`/`prd` apagar e comando
    do dono. As parcelas saem antes do cabecalho, por causa da FK.
    """
    op.execute("DELETE FROM desafio_dia.tb905_parcela_regua_nota WHERE nu_versao_regua = 4")
    op.execute("DELETE FROM desafio_dia.tb904_regua_nota WHERE nu_versao_regua = 4")
