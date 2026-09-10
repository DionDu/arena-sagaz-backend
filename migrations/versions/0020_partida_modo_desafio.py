"""`partida.co_modo` passa a aceitar `'desafio'` (RF-DES-179/184/186).

Revision ID: 0020_partida_modo_desafio
Revises: 0019_schema_desafio_dia
Create Date: 2026-09-09

✅ **APLICADA NO `des` em 10/09/2026** (revisao `0020`), e conferida por
`scripts/conferir_migracao_desafio.py`: 15 tabelas, 15 VIEWs, as dimensoes
populadas e a `tb903_perfil_dificuldade` vazia — que e o correto, quem a
preenche e o job.

⛔ **NO `prd` ainda NAO**, e nao vai antes do portao T050.

⚠️ **E ela NAO espera leitura de ninguem.** Decisao do dono, 09/09/2026:

    "Eu nao vou conferir codigo de Alembic. Eu ja pre validei o data-model.md."

O que foi aprovado e o **modelo**, e nao este arquivo. O que garante que os dois
dizem a mesma coisa e um cadeado, e nao a atencao de quem escreveu:
`tests/unitarios/test_migracao_bate_com_data_model.py` compara tabela a tabela,
coluna a coluna **na ordem**, constraint a constraint e indice a indice. Ele nao
tem `skip` nem `xfail`, e ha um teste que prova que nunca ganhara um.

⚠️ **O que continua valendo e a conferencia de AMBIENTE**, que e outra coisa:
antes de qualquer `alembic upgrade`, rodar `scripts/identificar_banco.py` — o
`AMBIENTE` do `.env` **nao e prova** de para onde a conexao aponta, e confundir
`des` com `prd` nao tem volta.

    DES = hopper.proxy.rlwy.net:21165
    PRD = hayabusa.proxy.rlwy.net:42857

═══════════════════════════════════════════════════════════════════════════
⚠️ AQUI A REGRA DO DROPA-E-RECRIA **NAO VALE**
═══════════════════════════════════════════════════════════════════════════

As migracoes `0018` e `0019` criam schemas novos, vazios, e por isso podem ser
refeitas a vontade enquanto o PRD nao subir (`DECISOES-do-dono.md` §8b).

**`partida` e outra coisa.** Ela esta em producao, com partidas de gente de
verdade gravadas desde 2026-07. Nada aqui pode perder uma linha, e por isso esta
migracao e **estritamente aditiva**: ela alarga um vocabulario, e nada mais.

═══════════════════════════════════════════════════════════════════════════
O QUE ENTRA, E POR QUE E TAO POUCO
═══════════════════════════════════════════════════════════════════════════

**A RESOLUCAO DE UM DESAFIO E UMA PARTIDA** (determinacao do dono, 04/09/2026):
ela usa o log que ja existe, com `co_modo = 'desafio'` e `ic_pontua = FALSE` — a
coluna `ic_pontua` ja existe e ja e o anti-farm do `pvp_local`.

⛔ **Nao ha log de lances proprio do desafio**, e nao ha tabela nova aqui. O
replay do desafio e o replay de uma partida. A unica coisa que faltava era o
`CHECK` aceitar a palavra.

═══════════════════════════════════════════════════════════════════════════
⚠️ `co_status` NAO GANHA VALOR NOVO — e isso foi conferido, nao presumido
═══════════════════════════════════════════════════════════════════════════

A `0006` ja tem os tres estados de que o desafio precisa:

    CHECK (co_status IN ('concluida', 'abandonada', 'em_andamento'))

E sao exatamente os tres caminhos de saida que o dono desenhou em 08/09/2026 para
quem para no objetivo e deixa a partida sem fim: fim natural (`concluida`), sair
da tela (`abandonada`) e o job de expiracao de 7 dias (`abandonada`).

⚠️ **O problema real nao esta no `CHECK` — esta uma camada acima, no INGESTOR**,
e por isso ele **nao se conserta com migracao**. `api/sincronizacao/repositorio.py`
grava com `ON CONFLICT (co_evento) DO NOTHING`: o segundo envio, o que completaria
a partida, seria descartado **em silencio**, e ela ficaria `em_andamento` para
sempre sem erro nenhum no log. A correcao (um `DO UPDATE` com
`WHERE co_status = 'em_andamento'`) e codigo, e tem tarefa propria.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE A VIEW `partida.vw001_partida` **NAO** E RECRIADA AQUI
═══════════════════════════════════════════════════════════════════════════

O `data-model.md` previa recria-la, com a justificativa de que ela e `SELECT *` e
congela colunas. A justificativa esta certa **para outro caso**: o que exige
recriar view e alterar o **tipo** de uma coluna que ela usa (foi o que a `0014`
enfrentou, e o Postgres recusa com *"cannot alter type of a column used by a view
or rule"*), ou acrescentar coluna que se queira ver na view.

Trocar um `CHECK` nao faz nem uma coisa nem outra: nenhuma coluna muda de tipo,
nenhuma coluna nasce, e a arvore da view continua valida. Recriar a view aqui
seria trabalho com risco e sem ganho — e um `DROP VIEW` a mais no historico, que
e justamente o que a disciplina de migracao aditiva tenta manter raro.

Registrado no `data-model.md` na mesma resposta.
"""

from typing import Sequence, Union

from alembic import op

# "0020_partida_modo_desafio" tem 25 caracteres — dentro do limite de 32.
revision: str = "0020_partida_modo_desafio"
down_revision: Union[str, None] = "0019_schema_desafio_dia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Os modos que ja existiam desde a `0003`, escritos aqui uma vez so para que o
# `upgrade` e o `downgrade` nao possam divergir por digitacao.
MODOS_ANTIGOS = ("vs_cpu", "pvp_local", "pvp_online")

# ⚠️ O modo novo, e o UNICO acrescimo desta migracao.
MODO_NOVO = "desafio"


def _lista_sql(valores: Sequence[str]) -> str:
    """Formata uma lista de textos para dentro de um `IN (...)` do SQL."""
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    """Alarga o vocabulario de `co_modo` para incluir `'desafio'`.

    ⚠️ **Trocar um `CHECK` exige derrubar e recriar a constraint** — o Postgres
    nao tem `ALTER CONSTRAINT ... CHECK`. Os dois comandos vao na mesma migracao
    e, como todo DDL do Postgres e transacional, **nao existe instante em que a
    tabela fique sem a regra**: ou os dois valem, ou nenhum vale.

    ⚠️ E a constraint nova e um **superconjunto** da antiga: ela aceita tudo o
    que a anterior aceitava, mais uma palavra. Nenhuma linha ja gravada pode
    deixar de passar — se pudesse, o proprio `ADD CONSTRAINT` falharia ao
    revalidar a tabela, e a migracao inteira voltaria atras.
    """
    op.execute(
        "ALTER TABLE partida.tb001_partida DROP CONSTRAINT ck_partida_modo"
    )
    op.execute(
        "ALTER TABLE partida.tb001_partida ADD CONSTRAINT ck_partida_modo "
        f"CHECK (co_modo IN ({_lista_sql((*MODOS_ANTIGOS, MODO_NOVO))}))"
    )


def downgrade() -> None:
    """Volta o `CHECK` ao vocabulario de tres modos.

    ⚠️ **Este `downgrade` FALHA se ja houver partida de desafio gravada**, e isso
    e correto: o `ADD CONSTRAINT` revalida a tabela inteira e recusa as linhas com
    `co_modo = 'desafio'`.

    Falhar alto e melhor que a alternativa. Um `downgrade` que apagasse essas
    linhas para "poder" voltar destruiria partidas de gente real — e este e o
    unico schema desta entrega onde isso seria possivel.
    """
    op.execute(
        "ALTER TABLE partida.tb001_partida DROP CONSTRAINT ck_partida_modo"
    )
    op.execute(
        "ALTER TABLE partida.tb001_partida ADD CONSTRAINT ck_partida_modo "
        f"CHECK (co_modo IN ({_lista_sql(MODOS_ANTIGOS)}))"
    )
