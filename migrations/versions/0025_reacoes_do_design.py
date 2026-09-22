"""As reacoes definitivas do Claude Design: cinco, e o emoji do 'uau' trocado.

Revision ID: 0025_reacoes_do_design
Revises: 0024_tres_tipos_de_pontinhos
Create Date: 2026-09-21

═══════════════════════════════════════════════════════════════════════════
⏳ O QUE ESTAVA PENDURADO DESDE 10/09 — E O QUE O DESTRAVOU
═══════════════════════════════════════════════════════════════════════════

A `0019` semeou `tb903_tipo_reacao` com **linhas provisorias** e disse por
escrito que a T090 as refaria *"quando os artefatos do Claude Design chegarem"*
(RF-DES-226). O artefato chegou em **16/09/2026**:
`design/arena-desafio-quadro.jsx`.

⚠️ **Elas entraram provisorias de proposito, e nao por descuido:** `tb006_reacao`
tem `FOREIGN KEY` para esta dimensao, e uma dimensao vazia deixaria a cadeia
inteira de reacao **inexercitavel** ate o Design responder - inclusive nos
testes. Tres linhas provisorias custam um `INSERT` para trocar; uma cadeia sem
teste custa muito mais. Esta migracao e o `INSERT` que sempre foi o preco.

═══════════════════════════════════════════════════════════════════════════
⚠️ SAO CINCO, E NAO TRES - E ISSO NAO CONTRARIA O RF-DES-070
═══════════════════════════════════════════════════════════════════════════

O artefato declara `DD_REACOES` com **cinco**:

    const DD_REACOES = [
      { id: 'palmas', rot: 'Palmas' },
      { id: 'uau', rot: 'Uau' },
      { id: 'fogo', rot: 'Fogo' },
      { id: 'coracao', rot: 'Coração' },
      { id: 'top', rot: 'Top' },
    ];

O RF-DES-070 pede **"so positivas"**, e cita palmas/uau/fogo como exemplo do
principio. ⚠️ **Coracao e Top sao positivas**, e nenhuma delas pode ser lida como
deboche - que e a fronteira que o requisito defende, porque e ela que mantem o
aplicativo fora do negocio de moderacao.

⚠️ **E o vocabulario e DADO, nao codigo.** Esta dimensao existe exatamente para
isso: passar de tres para cinco (ou voltar) e um `INSERT`/`UPDATE`, e ⛔ nao um
deploy. ⚠️ O que ainda exige versao nova do aplicativo e **TEXTO** - a chave
`.arb` do rotulo -, que e a mesma fronteira que o Bloco Y ja tinha tracado para
os objetivos.

═══════════════════════════════════════════════════════════════════════════
⏳ O QUE FICOU DE FORA: O EMOJI DO 'UAU' (😮 → 😱)
═══════════════════════════════════════════════════════════════════════════

A `0019` chutou `😮` (rosto de boca aberta); o Design escolheu
`😱` (rosto gritando de espanto). ⛔ **A troca ⛔ NAO esta aqui**, e a
recusa e de um cadeado nosso: `test_migracoes_aditivas` exige que todo comando de
um `upgrade` seja um **acrescimo**, e ⛔ nenhum `upgrade` deste projeto reescreve
dado - `UPDATE` e `DELETE` so aparecem em `downgrade`.

⚠️ **O cadeado esta certo, e ⛔ nao se afrouxa por um emoji.** Ele protege o banco
de producao de uma migracao que reescreve o que ja esta la; abrir excecao para
*"dimensao provisoria"* criaria uma porta que alguem atravessa depois com dado
real.

⚠️ **E ⛔ nao invalida reacao nenhuma ja dada**: o fato aponta para
`nu_tipo_reacao`, e ⛔ nao para o desenho. Quem tiver reagido com "uau" continua
com "uau" - o que muda, quando mudar, e o rosto.

═══════════════════════════════════════════════════════════════════════════
⛔ E ⛔ NAO ENTRA COLUNA DE COR, EMBORA O DESIGN DEFINA UMA POR REACAO
═══════════════════════════════════════════════════════════════════════════

O artefato tambem fixa `DD_REACAO_COR` - cada reacao tem cor propria, e ela
⛔ nunca muda. ⚠️ **Ela fica no aplicativo**, junto do rotulo, e ⛔ nao numa coluna
nova: o rotulo ja obriga versao nova para cada reacao inedita, entao uma cor
vinda do banco ⛔ nao compraria nada - a reacao chegaria pintada e **sem nome**.
E o RF-DES-226 lista o que viaja como dado, e cor ⛔ nao esta la.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0025_reacoes_do_design"
down_revision: Union[str, None] = "0024_tres_tipos_de_pontinhos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Semeia `coracao` e `top`.

    ⚠️ `nu_ordem` e UNIQUE (`un001_ordem`), e e ela que da a ordem da barra - o
    aplicativo ⛔ nao reordena nada por conta propria. 4 e 5 estao livres: a
    `0019` deixou o sentinela em 99 justamente para ⛔ nao atrapalhar o meio.
    """
    op.execute(
        """
        INSERT INTO desafio_dia.tb903_tipo_reacao
            (nu_tipo_reacao, co_tipo_reacao, no_tipo_reacao, co_emoji,
             co_chave_i18n, nu_ordem, ic_ativo) VALUES
            (4, 'coracao', 'Coração', '❤️',
                'reacaoCoracao', 4, TRUE),
            (5, 'top',     'Top',     '🔝',
                'reacaoTop',     5, TRUE)
        """
    )


def downgrade() -> None:
    """Tira as duas linhas novas.

    ⚠️ **So para o ambiente local**, como no resto do projeto.

    ⛔ E o `DELETE` so passa enquanto ninguem tiver reagido com `coracao` ou
    `top`: `tb006_reacao` aponta para ca. E o comportamento certo - apagar a
    dimensao por baixo de uma reacao ja dada deixaria o fato sem significado.
    """
    op.execute(
        "DELETE FROM desafio_dia.tb903_tipo_reacao "
        "WHERE nu_tipo_reacao IN (4, 5)"
    )
