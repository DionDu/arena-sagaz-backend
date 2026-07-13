"""Cadastra a acao `cnn_epsilon_aleatorio` na dimensao de acoes da jogada.

CONTEXTO
--------
O app trocou a POLITICA DE DIFICULDADE da CPU do Jogo dos Pontinhos.

**Antes (nucleo top-p).** Cacau/Pita sorteavam o lance dentro do "nucleo": os
tracos de maior probabilidade cujo somatorio alcancava um alvo `p` (0,90 e 0,55).
O problema e que esse nucleo e **adaptativo a confianca da rede**: quando a CNN
concentra ~99% num unico traco -- o que acontece justamente no fim de jogo, com as
cadeias formadas --, o primeiro lance sozinho ja estoura qualquer `p`, o nucleo
colapsa para UM lance e ate a Cacau (facil) passa a jogar perfeito **exatamente no
lance que decide a partida**. Quanto mais decisivo o momento, menos aleatoria a CPU
ficava: o inverso do desejado.

**Agora (epsilon-greedy).** Cada personagem tem uma probabilidade FIXA de jogar de
proposito fora do melhor lance: Cacau 70%, Pita 50%, Tex 30%, Magno 0%. Como o
epsilon nao olha para a confianca da rede, o facil continua errando no fim de jogo --
que e onde ele precisa errar. A captura gulosa (fechar caixa de graca sem consultar
a rede) continua valendo para todos, menos o Magno.

O QUE MUDA NO BANCO
-------------------
Uma linha nova em `jogo_pontinhos.tb901_jogada_acao`:

    (6, 'cnn_epsilon_aleatorio', 'CNN - erro epsilon (fora do argmax)')

E o codigo que marca a "burrice controlada" que define a dificuldade -- o dado que
queremos poder isolar depois, no treino e na analise.

**`cnn_nucleo_top_p` (2) NAO e removido.** Ele continua sendo a verdade historica das
partidas ja gravadas com a politica antiga; remove-lo quebraria a FK dessas jogadas.
Pelo mesmo motivo o codigo 6 e NOVO, em vez de reaproveitar o 2: um numero de codigo
nunca muda de significado, senao o historico vira mentira.

POR QUE ESTA MIGRACAO PRECISA IR ANTES DO APP
---------------------------------------------
`jogo_pontinhos.tb002_jogada.nu_acao` e FK para esta tabela. Sem a linha nova, a
traducao em `api/sincronizacao/dimensoes.py` nao acha o codigo, cai no sentinela
`9999` ('desconhecido') e grava a string crua em `js_extra`. Nada quebra (foi
desenhado assim de proposito: um app mais novo que o backend nao pode travar a fila
de sincronizacao do aparelho) -- mas a telemetria perderia a distincao entre "a CPU
errou de proposito" e "nao sei o que a CPU fez", que e exatamente o que se quer medir.

NAO destrutiva: so INSERT numa tabela de dimensao.

Revision ID: 0008_acao_epsilon_greedy
Revises: 0007_drop_co_anonimo
Create Date: 2026-07-13
"""
from typing import Sequence, Union

from alembic import op

# Maximo 32 caracteres: `alembic_version.version_num` e VARCHAR(32).
revision: str = "0008_acao_epsilon_greedy"
down_revision: Union[str, None] = "0007_drop_co_anonimo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# O codigo textual que o app envia (oraculo.dart -> AcaoCpu.cnnEpsilonAleatorio) e a
# chave numerica que o guarda no banco. Cabe folgado no VARCHAR(30) da coluna.
NU_ACAO = 6
CO_ACAO = "cnn_epsilon_aleatorio"
NO_ACAO = "CNN - erro epsilon (fora do argmax)"


def upgrade() -> None:
    # `ON CONFLICT DO NOTHING` deixa a migracao idempotente: se a linha ja tiver sido
    # inserida a mao em algum ambiente, rodar isto nao estoura.
    op.execute(
        f"""
        INSERT INTO jogo_pontinhos.tb901_jogada_acao (nu_acao, co_acao, no_acao)
        VALUES ({NU_ACAO}, '{CO_ACAO}', '{NO_ACAO}')
        ON CONFLICT (nu_acao) DO NOTHING
        """
    )


def downgrade() -> None:
    # So remove se NENHUMA jogada ja tiver usado o codigo -- senao a FK impediria de
    # qualquer forma, e o erro de FK seria bem mais obscuro que este DELETE
    # condicional. Voltar a politica antiga NAO exige apagar o codigo: ele
    # simplesmente para de ser usado (mesmo caso do `cnn_nucleo_top_p`).
    op.execute(
        f"""
        DELETE FROM jogo_pontinhos.tb901_jogada_acao
        WHERE nu_acao = {NU_ACAO}
          AND NOT EXISTS (
              SELECT 1 FROM jogo_pontinhos.tb002_jogada WHERE nu_acao = {NU_ACAO}
          )
        """
    )
