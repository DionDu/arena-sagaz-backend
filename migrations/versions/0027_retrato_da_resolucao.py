"""O retrato da resolucao: o que a pessoa FEZ no instante do objetivo (T085za).

Revision ID: 0027_retrato_da_resolucao
Revises: 0026_notificacao_de_reacao
Create Date: 2026-09-24

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA COLUNA EXISTE
═══════════════════════════════════════════════════════════════════════════

A aba "Hoje" de quem ja resolveu diz o FEITO da pessoa: *"4 caixas em 2
turnos"*, para um objetivo que pedia *"Feche 4 caixas em 3 turnos"*. Ate aqui
esses numeros viviam **so no celular** - e o dono, em 24/09/2026:

    "Eu nao gosto destes dados que ficam sendo salvos apenas localmente no
     celular. [...] Quando o usuario se loga em outro aparelho precisa
     visualizar no outro aparelho o mesmo que via no primeiro."

O servidor ja recebia as medidas (o `feitos` do envio), mas gravava em
`tb004_xp_desafio` **so as que pesam naquele desafio** - o resto era
descartado. E quanto da janela foi gasto (os "2 turnos") nem subia.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE JSON, E ⛔ LINHAS NA `tb004`
═══════════════════════════════════════════════════════════════════════════

Decisao do dono (`DECISOES-do-dono.md` §8z item 13): *"Esta otima a proposta
toda."* A `tb004` e o **livro do XP** - cada linha e uma parcela da conta, e o
Raio-X as lista. Medida que ⛔ pesa ali viraria linha de XP zero, e o Raio-X
passaria a mostrar o que hoje ⛔ mostra. O `js_feito` e o **retrato para a
frase**, e ⛔ entra em conta nenhuma:

    {"medidas": {"caixas_fechadas": 4, "caixas_do_adversario": 1, ...},
     "janela_gasta": 2}

⚠️ **Quem diz QUAIS medidas cada frase precisa ⛔ e esta coluna**: e o
manifesto `contratos/medidas_do_feito.json`, com cadeado nos dois repositorios
e no job. A coluna guarda tudo o que o medidor contou - a frase escolhe.

═══════════════════════════════════════════════════════════════════════════
⚠️ NULA DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

`NULL` quer dizer *"resolucao anterior ao retrato"* - as do `des` antes desta
migracao. Um `{}` de preenchimento diria *"a pessoa nao fez nada"*, que e
mentira; e o aplicativo, com `NULL`, cai em *"Objetivo cumprido"*, que continua
verdadeiro. ⚠️ **Toda resolucao gravada daqui em diante tem retrato**: quem a
monta e o servidor, a partir do proprio envio (`servico_envio.py`).

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE MIGRACAO NOVA, E POR QUE NO FIM DA TABELA
═══════════════════════════════════════════════════════════════════════════

Ordem do dono (10/09/2026): *"Nao quero que voce modifique migracao ja aplicada
como a 0019. Crie outra."* O `ALTER TABLE ... ADD COLUMN` poe a coluna no FIM -
e o Postgres ⛔ tem outro jeito sem recriar a tabela, que tem FK apontando para
ela (`tb004`, as reacoes, a notificacao). A VIEW ganha a coluna no fim pelo
mesmo motivo: `CREATE OR REPLACE VIEW` so aceita coluna nova **depois** das que
ja existem.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0027_retrato_da_resolucao"
down_revision: Union[str, None] = "0026_notificacao_de_reacao"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Acrescenta `js_feito` a `tb003_resolucao` e a `vw003_resolucao`.

    ⚠️ **O SQL e literal, e ⛔ montado com `+`**: os cadeados leem o que a
    migracao executa com `ast` (`tests/unitarios/leitura_de_migracao.py`), e so
    enxergam string literal e f-string. Uma concatenacao passaria por eles sem
    ser lida - inclusive um `DROP` no meio dela.
    """
    op.execute(
        "ALTER TABLE desafio_dia.tb003_resolucao ADD COLUMN js_feito JSONB"
    )
    # ⚠️ A VIEW e o unico caminho de leitura (convencao do banco): sem a coluna
    # nela, a rota "o meu dia" ⛔ teria de onde ler o retrato. As colunas de
    # antes vem inteiras e na mesma ordem - `CREATE OR REPLACE VIEW` exige.
    op.execute(
        """
        CREATE OR REPLACE VIEW desafio_dia.vw003_resolucao AS
        SELECT r.id_resolucao,
               r.id_desafio_dia,
               r.id_usuario,
               r.id_tentativa,
               t.id_partida,
               t.nu_tempo_ms,
               r.nu_lance_cumpre_desafio,
               r.nu_xp,
               r.nu_versao_catalogo,
               r.co_auditoria,
               r.de_auditoria,
               r.dh_resolucao,
               r.dh_registro,
               r.js_feito
          FROM desafio_dia.tb003_resolucao r
          JOIN desafio_dia.tb002_tentativa t
            ON t.id_tentativa = r.id_tentativa
        """
    )


def downgrade() -> None:
    """Volta a VIEW e a tabela ao que a `0019` criou.

    ⚠️ So para o ambiente local: `CREATE OR REPLACE` ⛔ tira coluna de VIEW, e
    por isso ela e derrubada e refeita.
    """
    op.execute("DROP VIEW desafio_dia.vw003_resolucao")
    op.execute(
        """
        CREATE VIEW desafio_dia.vw003_resolucao AS
        SELECT r.id_resolucao,
               r.id_desafio_dia,
               r.id_usuario,
               r.id_tentativa,
               t.id_partida,
               t.nu_tempo_ms,
               r.nu_lance_cumpre_desafio,
               r.nu_xp,
               r.nu_versao_catalogo,
               r.co_auditoria,
               r.de_auditoria,
               r.dh_resolucao,
               r.dh_registro
          FROM desafio_dia.tb003_resolucao r
          JOIN desafio_dia.tb002_tentativa t
            ON t.id_tentativa = r.id_tentativa
        """
    )
    op.execute("ALTER TABLE desafio_dia.tb003_resolucao DROP COLUMN js_feito")
