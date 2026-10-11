"""A regua 1 volta a valer ate a liberacao da 1.3.1 (versao 3; DECISOES-do-dono §8zzr).

Revision ID: 0031_regua_antiga_ate_liberar
Revises: 0030_regua_da_nota
Create Date: 2026-10-11

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA MIGRACAO EXISTE
═══════════════════════════════════════════════════════════════════════════

A `0030` entrou no `prd` em 11/10/2026, as 01h03 UTC, antes do codigo que a le.
Ela calcula a vigencia da versao 2 como "o dia seguinte a aplicacao", e por isso
pos a regua NOVA valendo desde 12/10/2026 - quando a ideia era que ela valesse a
partir do deploy do backend. Ao saber disso, o dono decidiu mais (§8zzr):

    "o melhor e aplicarmos a migracao apenas na hora que estiver disponivel
     pra mim liberar o App nas lojas apos a revisao."

Ou seja: a regua nova comeca quando a 1.3.1 chega as pessoas, e nao quando o
servidor muda. Entre o deploy e essa liberacao, a 1.3.0 continua em campo, e ela
estima a nota com os numeros da versao 1 (constantes no app). Se o servidor
pontuasse pela versao 2 nesses dias, a pessoa veria um XP e receberia outro.

═══════════════════════════════════════════════════════════════════════════
O CONSERTO: UMA VERSAO NOVA COM OS NUMEROS ANTIGOS
═══════════════════════════════════════════════════════════════════════════

Esta migracao insere a **versao 3**, com os numeros EXATOS da versao 1 (linear,
30/30/15/25), valendo a partir de **13/10/2026**. Pela regra da vigencia (vale a
versao de MAIOR `dt_inicio_vigencia` que ainda seja <= `dt_dia`), fica assim:

    ate 11/10      versao 1  (linear)
    12/10          versao 2  (hiperbolica) - so nominalmente, ver abaixo
    13/10 em diante versao 3  (linear, = versao 1)
    da liberacao   versao 4  (hiperbolica, = versao 2) - migracao `0032`

⚠️ **Por que nao um `UPDATE` na data da versao 2**: o projeto so aceita migracao
aditiva (`tests/unitarios/test_migracoes_aditivas.py`), porque ha usuarios reais
no `prd`. E reescrever a vigencia de uma versao ja aplicada esconderia a historia
do proprio banco. Uma versao nova conta o que aconteceu.

⚠️ **Por que 13/10, e nao "o dia seguinte", como a `0030`**: a versao 2 ja
ocupa 12/10, e a `un001_inicio_vigencia` nao deixa duas versoes no mesmo dia.
Uma data FIXA tambem tira a pressa da aplicacao: esta migracao entra
imediatamente antes do deploy, e o deploy vem antes de mandar a 1.3.1 a revisao
(sem ele o revisor veria a aba do desafio vazia). Ate 12/10 o servidor que esta
no ar ainda e o antigo, que grava a nota do aparelho; a versao 2 so pontuaria
uma resolucao de 12/10 que chegasse DEPOIS do deploy.

⚠️ **E se for aplicada depois de 13/10?** Nada muda no que ela faz: os dias
13/10 em diante ja foram pontuados pelo servidor antigo (a nota do aparelho,
pelos numeros da versao 1), e a versao 3 e a mesma conta. Um reenvio atrasado
de um desses dias sai igual aos outros.

═══════════════════════════════════════════════════════════════════════════
COMO APLICAR (o detalhe esta em docs/runbook-migracoes-desafio.md)
═══════════════════════════════════════════════════════════════════════════

⚠️ **No `prd`, PELO NOME DA REVISAO, nunca com `upgrade head`.** O arquivo da
`0032` ja esta no repositorio, e o `head` aplicaria as duas de uma vez - a regua
nova valeria durante a revisao inteira das lojas:

    .venv\\Scripts\\python -m alembic upgrade 0031_regua_antiga_ate_liberar

No `des` as duas entram juntas (`upgrade head`).

Nem o job nem o app escrevem nestas tabelas: elas sao dimensao, e mudar a regua
e sempre uma migracao nova (`0030`, cabecalho "QUEM ESCREVE").
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0031_regua_antiga_ate_liberar"
down_revision: Union[str, None] = "0030_regua_da_nota"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Insere a versao 3 (os numeros da versao 1), valendo desde 13/10/2026."""
    # ── O cabecalho da versao 3 ─────────────────────────────────────────────
    #
    # ⚠️ Data FIXA (`DATE '2026-10-13'`), e nao calculada: ver o cabecalho do
    # arquivo. `DATE '...'` e o literal de data do SQL padrao, que o Postgres
    # le sem depender do fuso da sessao.
    op.execute(
        """
        INSERT INTO desafio_dia.tb904_regua_nota
            (nu_versao_regua, dt_inicio_vigencia, de_motivo) VALUES
            (3, DATE '2026-10-13',
             'Os numeros da versao 1 de novo (DECISOES-do-dono 8zzr): a regua '
             'nova so vale da liberacao da 1.3.1 nas lojas (migracao 0032)')
        """
    )
    # ── As parcelas: as MESMAS quatro linhas da versao 1 da `0030` ──────────
    #
    # Os `nu_tipo_xp`: 2 = tentativas, 3 = tempo, 4 = dica, 5 = merito
    # (`tb901_tipo_xp_desafio`, migracao 0019).
    #
    # Linear: tentativas `1 - (n-1)/3` (zera na 4a); tempo ate o
    # `nu_tempo_teto_ms` de cada desafio (por isso a escala vazia); dica
    # `1 - d/2` (zera na 2a); o merito so leva o peso.
    op.execute(
        """
        INSERT INTO desafio_dia.tb905_parcela_regua_nota
            (nu_versao_regua, nu_tipo_xp, vr_peso, co_forma, vr_x0, vr_escala)
        VALUES
            (3, 2, 0.300, 'linear',      1, 3),
            (3, 3, 0.300, 'linear',      1, NULL),
            (3, 4, 0.150, 'linear',      0, 2),
            (3, 5, 0.250, 'merito',      NULL, NULL)
        """
    )


def downgrade() -> None:
    """Tira a versao 3.

    ⚠️ **So para o ambiente local**, como no resto do projeto - o teste de
    migracao aditiva ignora o `downgrade()`, e no `des`/`prd` apagar e comando
    do dono. As parcelas saem antes do cabecalho, por causa da FK.
    """
    op.execute("DELETE FROM desafio_dia.tb905_parcela_regua_nota WHERE nu_versao_regua = 3")
    op.execute("DELETE FROM desafio_dia.tb904_regua_nota WHERE nu_versao_regua = 3")
