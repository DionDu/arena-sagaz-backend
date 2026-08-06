"""Schema `jogo_velha` — a extensao de jogada do 2o jogo do hub.

CONTEXTO
--------
O Jogo da Velha (spec 007) e o segundo jogo da Arena Sagaz. Como o Pontinhos, ele
grava a jogada GENERICA em `partida.tb002_jogada` e uma EXTENSAO especifica num
schema proprio. Esta migracao cria esse schema.

POR QUE A EXTENSAO EXISTE, SE A VELHA NAO TEM TREINO
----------------------------------------------------
A do Pontinhos existe para alimentar a CNN. Esta nao — **nao ha treino**
(RF-VLH-007), e e por isso que ela e tao menor: sem matriz, sem softmax, sem
score de busca, sem profundidade. Ela existe por duas razoes de AUDITORIA:

1. **o XP passa a depender de `ic_otimo`** (RF-VLH-045/046). Um numero que decide
   recompensa e nao e verificavel no servidor e a palavra do aparelho;
2. **reconstruir a partida para suporte** — com a celula e a ordem, a partida
   inteira se remonta.

⚠️ ESTA MIGRACAO E PURAMENTE ADITIVA — E ISSO E VERIFICADO, NAO PROMETIDO
-------------------------------------------------------------------------
**Ha usuarios reais em `prd` desde 04/08/2026.** O dono cravou a regra em
2026-08-06: nada de `DELETE`, `TRUNCATE` ou `DROP`. O `upgrade()` abaixo contem
APENAS `CREATE SCHEMA`, `CREATE TABLE` x2, `INSERT` na dimensao e `CREATE VIEW`
x2. Nenhuma tabela, coluna ou view existente e tocada.

E "aditiva" deixou de ser palavra do autor: `tests/unitarios/
test_migracao_aditiva_velha.py` **le este arquivo** e falha se encontrar
qualquer uma das tres no `upgrade()`.

O `downgrade()` derruba o schema, e e a unica excecao — ele existe para o
ambiente local e **nunca roda em producao**.

COMPATIBILIDADE COM QUEM NAO VAI ATUALIZAR O APP
------------------------------------------------
Nada aqui afeta o app antigo. Ele nao conhece o schema `jogo_velha`, nunca envia
`jogada["velha"]` e continua lendo e escrevendo exatamente as mesmas tabelas de
antes. Um schema novo e invisivel para quem nao o consulta.

V-1..V-5 (o portao do dono) foram respondidas em 2026-08-06 — ver
`specs/007-jogo-da-velha/data-model.md` §6. Em especial, a **V-1**: `co_celula` e
`VARCHAR(15)`, e nao o `VARCHAR(3)` que o PRD §7.2 escrevia. Com 3, todo `INSERT`
seria rejeitado: `'C_1_2'` tem 5 caracteres.
"""

from typing import Sequence, Union

from alembic import op

# ⚠️ O id de revisao do Alembic tem limite de 32 caracteres. Passar disso faz o
# upgrade RODAR o DDL inteiro e falhar so no fim, revertendo tudo — um erro caro
# de diagnosticar. "0011_schema_jogo_velha" tem 22.
revision: str = "0011_schema_jogo_velha"
down_revision: Union[str, None] = "0010_declaracao_idade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria o schema `jogo_velha` inteiro. So acrescenta."""
    op.execute("CREATE SCHEMA IF NOT EXISTS jogo_velha")

    # ── Dimensao da acao ────────────────────────────────────────────────────
    #
    # Vem ANTES da tabela de jogada porque esta tem FK para ela.
    op.execute(
        """
        CREATE TABLE jogo_velha.tb901_jogada_acao (
            nu_acao SMALLINT    PRIMARY KEY,
            co_acao VARCHAR(30) NOT NULL UNIQUE,
            no_acao VARCHAR(40) NOT NULL
        )
        """
    )

    # Os 6 codigos do jogo + o sentinela.
    #
    # ⚠️ A numeracao comeca em 1 e NAO continua a do Pontinhos: sao dimensoes de
    # schemas diferentes, e a chave e (schema, nu_acao), nao um contador global.
    #
    # ⚠️ Um `nu_acao` NUNCA muda de significado depois de gravado. Acrescentar e
    # migracao nova; reescrever o sentido de um existente falsifica todo o
    # historico ja gravado — e o historico e o motivo de esta tabela existir.
    #
    # ⚠️ O `9999` e INEGOCIAVEL. Sem um destino valido, um app MAIS NOVO que o
    # backend estoura a FK, toma 500, e o evento fica preso PARA SEMPRE na fila
    # de sincronizacao do aparelho — a partida daquela pessoa nunca sobe. Com o
    # sentinela, o evento entra e a string crua vai para `js_extra`.
    op.execute(
        """
        INSERT INTO jogo_velha.tb901_jogada_acao (nu_acao, co_acao, no_acao) VALUES
            (1,    'minimax_otimo',     'Minimax - lance otimo'),
            (2,    'minimax_deslize',   'Minimax - deslize unico do Magno'),
            (3,    'epsilon_aleatorio', 'Erro epsilon (fora do otimo)'),
            (4,    'abertura_sorteada', 'Abertura sorteada no conjunto otimo'),
            (5,    'bloqueio_forcado',  'Bloqueio/fechamento forcado'),
            (6,    'timeout_auto',      'Jogada automatica por tempo esgotado'),
            (9999, 'desconhecido',      'Desconhecido')
        """
    )

    # ── Extensao 1:1 da jogada ──────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE jogo_velha.tb002_jogada (
            id_jogada  UUID PRIMARY KEY
                REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
            co_jogador SMALLINT     NOT NULL,
            co_celula  VARCHAR(15)  NOT NULL,
            ic_otimo   BOOLEAN,
            nu_acao    SMALLINT
                REFERENCES jogo_velha.tb901_jogada_acao(nu_acao),
            js_extra   JSONB,
            -- +1 (J1) / -1 (J2): o SINAL, como no Pontinhos. O generico usa
            -- nu_jogador 1/2; a extensao usa o sinal. Sao convencoes diferentes
            -- de proposito, e o CHECK impede que uma vire a outra por descuido.
            CONSTRAINT ck_velha_jogador CHECK (co_jogador IN (1, -1)),
            -- 'C_<linha>_<coluna>', com linha e coluna de 1 a 3. O CHECK e o que
            -- impede uma celula invalida de entrar e so ser descoberta meses
            -- depois, quando alguem tentar reconstruir a partida.
            CONSTRAINT ck_velha_celula CHECK (co_celula ~ '^C_[1-3]_[1-3]$')
        )
        """
    )

    # ⚠️ Sobre `ic_otimo` ser ANULAVEL (V-4): `NULL` = lance da CPU. Nao faz
    # sentido medir a CPU pela regua da propria CPU, e um `false` gravado para
    # toda jogada da maquina falsearia qualquer analise de qualidade sobre esta
    # tabela. `NULL` significa "nao se aplica", que e a verdade.

    # ── VIEWs — le-se SEMPRE pela VIEW (regra do projeto, RF-VLH-058) ───────
    op.execute(
        "CREATE VIEW jogo_velha.vw901_jogada_acao AS "
        "SELECT * FROM jogo_velha.tb901_jogada_acao"
    )
    op.execute(
        "CREATE VIEW jogo_velha.vw002_jogada AS "
        "SELECT * FROM jogo_velha.tb002_jogada"
    )


def downgrade() -> None:
    """Derruba o schema inteiro.

    ⚠️ **So para o ambiente local.** Nunca rodar em `prd` — ha usuarios reais, e
    o `CASCADE` levaria junto as jogadas de velha ja gravadas. E o unico lugar
    deste arquivo onde um `DROP` aparece, e o teste de migracao aditiva ignora o
    `downgrade()` exatamente por isso.
    """
    op.execute("DROP SCHEMA IF EXISTS jogo_velha CASCADE")
