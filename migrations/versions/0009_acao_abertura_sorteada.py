"""Cadastra a acao `cnn_abertura_aleatoria` na dimensao de acoes da jogada.

CONTEXTO
--------
O Magno (nivel Sagaz) do Jogo dos Pontinhos joga com `epsilon == 0`: argmax puro
da CNN, sem erro de proposito. Isso tem um efeito colateral na ABERTURA: num
tabuleiro virgem a rede e determinista -- mesma entrada (matriz vazia), mesma
softmax, mesmo argmax --, entao o Magno abria TODAS as partidas com exatamente a
mesma aresta. Previsivel e repetitivo para quem joga.

**Agora**, quando e o Magno quem abre a partida, o PRIMEIRO lance (e apenas ele) e
sorteado uniformemente entre os tracos disponiveis. No tabuleiro vazio os 31
tracos sao equivalentes por simetria, entao sortear nao enfraquece o Magno --
so da variedade. Se quem abre e o oponente, o Magno segue CNN + argmax como
sempre. Os outros personagens (Cacau/Pita/Tex) nao passam por essa fase: o
`epsilon` deles (0.70/0.50/0.20) ja da variedade na abertura.

Implementacao no app: Fase 0 de `escolherLance`, em
`lib/modulos/jogos/pontinhos/logica/oraculo.dart`.

O QUE MUDA NO BANCO
-------------------
Uma linha nova em `jogo_pontinhos.tb901_jogada_acao`:

    (7, 'cnn_abertura_aleatoria', 'CNN - abertura sorteada (1o lance)')

Codigo NOVO em vez de reaproveitar um existente: um numero de codigo nunca muda
de significado, senao o historico ja gravado vira mentira (mesmo motivo pelo qual
`cnn_nucleo_top_p` (2) continua na tabela mesmo aposentado).

Vale notar que o lance NAO consultou a rede -- e sorteio puro. Ele fica na familia
`cnn_*` porque so acontece com a CNN carregada e so para o personagem que decide
tudo por ela; sem CNN (oraculo de reserva) o app grava `heuristica_gulosa`. No
treino, esta e a acao que se deve EXCLUIR ao aprender politica de abertura: ela
nao carrega sinal nenhum sobre qualidade de lance.

POR QUE ESTA MIGRACAO PRECISA IR ANTES DO APP
---------------------------------------------
`jogo_pontinhos.tb002_jogada.nu_acao` e FK para esta tabela. Sem a linha nova, a
traducao em `api/sincronizacao/dimensoes.py` nao acha o codigo, cai no sentinela
`9999` ('desconhecido') e grava a string crua em `js_extra`. Nada quebra (foi
desenhado assim de proposito), mas a telemetria perderia a distincao entre "a CPU
abriu no sorteio" e "nao sei o que a CPU fez".

NAO destrutiva: so INSERT numa tabela de dimensao.

Revision ID: 0009_acao_abertura_sorteada
Revises: 0008_acao_epsilon_greedy
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op

# Maximo 32 caracteres: `alembic_version.version_num` e VARCHAR(32).
revision: str = "0009_acao_abertura_sorteada"
down_revision: Union[str, None] = "0008_acao_epsilon_greedy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# O codigo textual que o app envia (oraculo.dart -> AcaoCpu.cnnAberturaAleatoria) e
# a chave numerica que o guarda no banco. Cabe folgado no VARCHAR(30) da coluna.
NU_ACAO = 7
CO_ACAO = "cnn_abertura_aleatoria"
NO_ACAO = "CNN - abertura sorteada (1o lance)"


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
    # condicional.
    op.execute(
        f"""
        DELETE FROM jogo_pontinhos.tb901_jogada_acao
        WHERE nu_acao = {NU_ACAO}
          AND NOT EXISTS (
              SELECT 1 FROM jogo_pontinhos.tb002_jogada WHERE nu_acao = {NU_ACAO}
          )
        """
    )
