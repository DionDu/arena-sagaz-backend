"""O tipo `pontinhos_cadeia_longa` e a medida que o julga.

Revision ID: 0023_cadeia_longa
Revises: 0022_motor_decifravel
Create Date: 2026-09-12

═══════════════════════════════════════════════════════════════════════════
A IDEIA E DO DONO, 12/09/2026
═══════════════════════════════════════════════════════════════════════════

> *"Capturar uma sequencia longa de cadeias. Deixa o usuario conectar tracos de
> tal forma que consiga montar uma cadeia extremamente longa, e depois captura-la,
> ao inves do adversario."*

E a frase publicada, decidida por ele no mesmo dia: *"Capture N ou mais caixas em
sequencia"*, com N grande — cinco, e de preferencia seis.

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE UMA MIGRACAO NOVA, E NAO UM `ALTER` NA 0018
═══════════════════════════════════════════════════════════════════════════

A `0018` semeou as duas dimensoes e **ja foi aplicada no `des`** (10/09/2026).
Migracao aplicada nao se edita: quem ja rodou nao roda de novo, e o ambiente
seguinte receberia um historico diferente do primeiro. Duas linhas novas entram
por uma migracao nova — que e o que este arquivo e.

═══════════════════════════════════════════════════════════════════════════
AS DUAS LINHAS
═══════════════════════════════════════════════════════════════════════════

**`tb901_tipo_desafio` (22)** — o tipo. A lista da `0018` sempre foi *piso, e nao
teto*; este e o primeiro a entrar depois dela.

⚠️ **O numero 22 e o primeiro LIVRE, e nao o proximo da `0018`.** Os numeros de
11 a 21 ja estao tomados pelas onze propostas de `job/tipos_propostos.py`, que
nao estao no banco mas estao escritas — reaproveitar um deles faria duas coisas
diferentes responderem pelo mesmo `nu_tipo_desafio` no dia em que a proposta
fosse aprovada.

**`tb902_catalogo_feito` (12)** — a medida `maior_cadeia_capturada`.

⚠️ **A medida nao existia porque as de hoje leem o ESTADO, e esta le o CAMINHO.**
`caixas_fechadas` e a diferenca de placar entre o inicio e o fim; *"em sequencia"*
e uma pergunta sobre a **ordem** dos lances, e duas partidas que terminam na
mesma posicao podem ter uma cadeia de sete e outra de duas.

⚠️ **O numero 12 nao e escolha desta migracao** — ele vem de
`tool/gerar_manifesto_feitos.dart`, no repositorio do aplicativo, que e quem
numera o catalogo e escreve as duas copias do manifesto. O cadeado
`tests/unitarios/test_catalogo_feito_paridade.py` compara o manifesto com o que
as migracoes dizem, e falha se alguem mexer num lado so.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0023_cadeia_longa"
down_revision: Union[str, None] = "0022_motor_decifravel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Semeia o tipo 22 e o feito 12."""
    op.execute(
        """
        INSERT INTO desafio.tb901_tipo_desafio
            (nu_tipo_desafio, co_tipo_desafio, no_tipo_desafio, co_jogo) VALUES
            (  22, 'pontinhos_cadeia_longa', 'Cadeia longa', 'pontinhos')
        """
    )
    op.execute(
        """
        INSERT INTO desafio.tb902_catalogo_feito
            (nu_feito, co_feito, no_feito, co_unidade, co_direcao,
             co_procedencia, co_jogo) VALUES
            (  12, 'maior_cadeia_capturada', 'Maior cadeia capturada',
                'contagem',     'maior_melhor',   'tabuleiro', 'pontinhos')
        """
    )


def downgrade() -> None:
    """Tira as duas linhas.

    ⚠️ **So para o ambiente local**, como no resto do projeto — o teste de
    migracao aditiva ignora o `downgrade()`.

    ⛔ E ele so funciona enquanto ninguem tiver apontado para elas: a `0018` pos
    `FOREIGN KEY` nas duas dimensoes, entao um desafio ja publicado deste tipo
    faz este `DELETE` falhar. E o comportamento certo — apagar a dimensao por
    baixo de um desafio publicado deixaria a linha dele sem significado.
    """
    op.execute("DELETE FROM desafio.tb902_catalogo_feito WHERE nu_feito = 12")
    op.execute("DELETE FROM desafio.tb901_tipo_desafio WHERE nu_tipo_desafio = 22")
