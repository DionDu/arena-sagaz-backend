"""A notificacao do dia seguinte saiu - UMA por desafio (RF-DES-074a/074b).

Revision ID: 0026_notificacao_de_reacao
Revises: 0025_reacoes_do_design
Create Date: 2026-09-22

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA TABELA EXISTE
═══════════════════════════════════════════════════════════════════════════

RF-DES-074b tem uma frase curta que **obriga memoria**:

    "Reacao que chegar depois do envio NAO gera uma segunda notificacao - e o
     que garante o teto de UMA por desafio, por mais popular que a pessoa seja."

⚠️ **Sem guardar que ela saiu, esse teto ⛔ nao existe.** O disparo roda de hora
em hora (RF-DES-074c: o meio-dia e o de **quem recebe**), e a tolerancia de 30
minutos de `fusos_na_hora_local` faz dois relogios de meia hora caberem na mesma
janela. Qualquer reexecucao - uma reimplantacao no Railway, um `restart`, o dono
rodando o disparo na maquina dele - reenviaria tudo. E o unico lugar que sobrevive
a um processo que morre no meio e o banco.

⛔ **E ⛔ nao serve contar reacoes**: *"notifiquei quando eram 3, agora sao 5"*
produziria uma segunda notificacao a cada pessoa nova, que e exatamente o que o
requisito proibe. O que se guarda ⛔ nao e um numero a comparar - e o **fato** de
ter saido.

═══════════════════════════════════════════════════════════════════════════
⚠️ UMA LINHA POR RESOLUCAO - E ELE E QUEM APLICA O TETO, ⛔ NAO O CODIGO
═══════════════════════════════════════════════════════════════════════════

`un001_notificacao_reacao UNIQUE (id_resolucao)` e o teto, e ⛔ nao um `if` no
Python:

    · a resolucao ja e unica por (desafio, pessoa) - `un001_resolucao` da `0019`;
      logo **uma linha por resolucao == uma notificacao por desafio por pessoa**;
    · o disparo reserva com `INSERT ... ON CONFLICT DO NOTHING` e ⛔ so envia se a
      linha foi dele. Duas execucoes ao mesmo tempo - o cron e o dono na maquina
      dele - passariam juntas por qualquer checagem em memoria; so o banco as
      separa.

⚠️ **A reserva vem ANTES do envio**, e essa ordem e uma escolha com preco. Se o
FCM estiver fora do ar naquela hora, a pessoa perde a notificacao daquele dia -
⛔ ⛔ nao ha reenvio. O contrario (enviar e depois marcar) arriscaria **duas**
notificacoes, e *"uma por desafio"* e requisito escrito; *"chega sempre"* ⛔ nao e.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ELA ⛔ NAO GUARDA: O DONO DA RESOLUCAO
═══════════════════════════════════════════════════════════════════════════

⛔ ⛔ Nao ha `id_usuario` aqui, e a ausencia e deliberada. O dono da notificacao e
o dono da resolucao, e ele se le por `JOIN`. Guardar a copia criaria duas
verdades que podem divergir - a mesma armadilha que a `0021` descreve no
paragrafo da chama (*"a segunda copia da verdade era a origem do defeito"*).

⚠️ **O que ela guarda, por outro lado, ⛔ nao e derivavel:** quantas pessoas a
frase anunciou (`qt_pessoa`), em que fuso a conta do meio-dia caiu
(`nu_offset_minuto`) e para quantos aparelhos saiu (`qt_dispositivo`). Sao o
**retrato** do instante do envio, e e por eles que se explica a pergunta que vai
chegar: *"a notificacao disse 3 e o quadro mostra 7"* - a diferenca sao as
reacoes tardias, que o requisito manda ignorar.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE `desafio_dia`, E ⛔ NAO `conta`
═══════════════════════════════════════════════════════════════════════════

A fronteira do Bloco X e **quem escreve**: `desafio` e a linha de producao (so o
job em batch); `desafio_dia` e o **evento**. Quem escreve aqui e o servidor, ⛔ nao
o aplicativo - mas isso ⛔ nao e novidade nem excecao aberta agora: `job/auditoria.py`
ja escreve `co_auditoria` em `tb003_resolucao` desde a T043a.

⚠️ O que decide o schema e **de que a linha fala**: ela fala de uma resolucao de
um dia, pende dela por FK e morre com ela (`ON DELETE CASCADE`). Em `conta` ela
precisaria de uma FK atravessando schema para achar o assunto - e a pergunta
operacional (*"a notificacao do desafio de ontem saiu?"*) ⛔ nao e sobre a conta.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE MIGRACAO NOVA, E ⛔ NAO EDICAO DA 0019
═══════════════════════════════════════════════════════════════════════════

A mesma razao da `0021`, e ela e ordem do dono (10/09/2026): *"Nao quero que voce
modifique migracao ja aplicada como a 0019. Crie outra."* A regra §8b (*dropa e
recria*) e contra **remendar modelagem defeituosa com `ALTER`**; aqui ⛔ nao ha
defeito a remendar - e tabela nova, aditiva por natureza, que ⛔ nao toca uma
coluna existente.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0026_notificacao_de_reacao"
down_revision: Union[str, None] = "0025_reacoes_do_design"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria `desafio_dia.tb008_notificacao_reacao` e a VIEW de leitura."""
    op.execute(
        """
        CREATE TABLE desafio_dia.tb008_notificacao_reacao (
            id_notificacao_reacao UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            -- ⚠️ O ASSUNTO, e a chave do teto. A resolucao ja e unica por
            -- (desafio, pessoa), entao uma linha por resolucao e uma
            -- notificacao por desafio por pessoa. `CASCADE` porque a linha
            -- ⛔ nao tem sentido sem a resolucao de que ela fala.
            id_resolucao          UUID NOT NULL
                REFERENCES desafio_dia.tb003_resolucao(id_resolucao)
                ON DELETE CASCADE,

            -- ⚠️ Quantas PESSOAS a frase anunciou - e ⛔ nao quantos toques.
            -- `un001_reacao` ja garante uma reacao por pessoa por linha, e a
            -- troca e um `UPDATE`: contar linhas e contar gente.
            --
            -- ⚠️ Ele e o retrato do instante do envio, e e o que explica
            -- *"a notificacao disse 3 e o quadro mostra 7"*.
            qt_pessoa             SMALLINT NOT NULL,

            -- ⚠️ O fuso em que a conta do meio-dia caiu. Sem ele ⛔ nao ha como
            -- reconferir a unica regra que a pessoa percebe se estiver errada
            -- (RF-DES-074c) - e o disparo de madrugada apareceria no log como
            -- um envio igual aos outros.
            nu_offset_minuto      SMALLINT NOT NULL,

            -- Para quantos aparelhos a mensagem foi **enderecada** naquela
            -- janela (e ⛔ nao quantos a receberam de fato: a reserva e escrita
            -- antes do envio, e e ela que impede o envio dobrado).
            --
            -- ⚠️ Sao os aparelhos **na janela do meio-dia**, e ⛔ nao todos os da
            -- pessoa: quem esta noutro fuso seria acordado de madrugada.
            qt_dispositivo        SMALLINT NOT NULL,

            -- ⚠️ O instante em que o disparo RESERVOU o direito de enviar (ver o
            -- cabecalho: a reserva vem antes do envio). Separado de
            -- `dh_registro` porque uma reexecucao manual pode gravar linhas de
            -- um envio anterior, e `now()` mentiria sobre a hora do meio-dia.
            dh_envio              TIMESTAMPTZ NOT NULL,

            dh_registro           TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- ⚠️ **ESTE e o teto de uma por desafio** (RF-DES-074b), e ⛔ nao uma
            -- checagem no Python: duas execucoes simultaneas passariam juntas
            -- por qualquer `if`, e so o banco as separa.
            CONSTRAINT un001_notificacao_reacao UNIQUE (id_resolucao),

            -- ⛔ Notificacao de zero reacao ⛔ nao existe: quem ⛔ nao recebeu
            -- nada ⛔ nao e notificado, e uma linha com zero seria a prova de um
            -- envio que ⛔ nao devia ter saido.
            CONSTRAINT ck001_pessoa CHECK (qt_pessoa > 0),

            -- ⛔ E ⛔ nao se reserva para quem ⛔ nao tem aparelho na janela: a
            -- linha queimaria a unica chance daquele dia sem ninguem receber.
            -- ⚠️ E quando **nenhum** dos aparelhos enderecados aceitou (todos os
            -- tokens mortos), o disparo **apaga** a linha - ver `0026` no
            -- cabecalho de `api/notificacoes/reacoes_do_desafio.py`.
            CONSTRAINT ck002_dispositivo CHECK (qt_dispositivo > 0)
        )
        """
    )

    # ⚠️ Indice pelo instante do envio: a pergunta operacional e *"quantas
    # sairam nesta hora, e em que fusos?"* - ela varre por tempo, ⛔ nao por
    # resolucao (essa ja tem o indice do `UNIQUE`).
    op.execute(
        "CREATE INDEX ix001_notificacao_reacao_envio "
        "ON desafio_dia.tb008_notificacao_reacao (dh_envio)"
    )

    # ⚠️ Colunas nomeadas UMA A UMA, e ⛔ nao `SELECT *`: uma VIEW criada com `*`
    # ⛔ NAO enxerga coluna acrescentada depois (licao da `0017`).
    op.execute(
        """
        CREATE VIEW desafio_dia.vw008_notificacao_reacao AS
        SELECT id_notificacao_reacao, id_resolucao, qt_pessoa,
               nu_offset_minuto, qt_dispositivo, dh_envio, dh_registro
          FROM desafio_dia.tb008_notificacao_reacao
        """
    )

    op.execute(
        "COMMENT ON TABLE desafio_dia.tb008_notificacao_reacao IS "
        "'A notificacao das reacoes do desafio de ontem SAIU (RF-DES-074a). "
        "Uma linha por resolucao, e o UNIQUE e o teto de uma por desafio: "
        "reacao tardia nao gera uma segunda.'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio_dia.tb008_notificacao_reacao.qt_pessoa IS "
        "'Quantas pessoas a frase anunciou, no instante do envio. Explica a "
        "diferenca entre o numero da notificacao e o do quadro, que sao as "
        "reacoes tardias.'"
    )


def downgrade() -> None:
    """Derruba a tabela e a VIEW.

    ⚠️ **So para o ambiente local**, como no resto do projeto - o teste de
    migracao aditiva ignora o `downgrade()`.
    """
    op.execute("DROP VIEW IF EXISTS desafio_dia.vw008_notificacao_reacao")
    op.execute(
        "DROP TABLE IF EXISTS desafio_dia.tb008_notificacao_reacao CASCADE"
    )
