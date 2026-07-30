"""Troca a data de nascimento por uma DECLARACAO de idade minima (13+).

CONTEXTO — a recusa da Apple (30/07/2026)
-----------------------------------------
A App Review recusou a versao 1.0 (2) pela diretriz **5.1.1(v)**: "o app exige que
o usuario forneca informacao pessoal que nao e diretamente relevante para a
funcionalidade principal", apontando nominalmente a **Date of Birth**.

E procede. A data de nascimento tinha exatamente DOIS usos aqui:

1. a trava de idade minima (13+, FR-005a / COPPA / LGPD art. 14);
2. o `ic_publico` do ranking global (quem pode aparecer na lista publica).

Nenhum dos dois precisa da DATA — os dois precisam apenas da RESPOSTA "tem 13 anos
ou mais?". Guardar a data exata era coletar mais do que se usa. A propria Apple
admite mecanismo de idade **declarada** ("verified or declared age", diretrizes
1.2.1(a) e 4.7.5).

O QUE MUDA
----------
1. Coluna nova `conta.tb001_usuario.ic_idade_minima_declarada` (BOOLEAN NOT NULL
   DEFAULT FALSE): a pessoa declarou ter 13 anos ou mais.
2. **Backfill**: quem ja tem `dt_nascimento` com idade >= 13 nasce com TRUE. Na
   pratica e todo mundo, porque o servico nunca deixou criar conta abaixo disso.
3. **`dt_nascimento` e ZERADA em todas as linhas.** Decisao do dono: padronizar,
   ninguem fica com data. E minimizacao de dado pessoal, nao faxina.
4. VIEWs recriadas:
   - `conta.vw001_usuario` — e `SELECT *`, mas no Postgres o `*` e expandido na
     CRIACAO da view. Sem recriar, a coluna nova simplesmente **nao apareceria**
     para a API, que le tudo pela view.
   - `progressao.vw101_ranking_global_geral` — o `ic_publico` passa a olhar a
     flag. Se continuasse olhando `dt_nascimento`, o passo 3 tiraria **todo mundo**
     do ranking publico de uma vez.

A COLUNA `dt_nascimento` NAO E REMOVIDA — E DE PROPOSITO
--------------------------------------------------------
Ha ~20 testadores com a build 1.0 (2) instalada, e ela so sabe enviar
`dt_nascimento` em `POST /v1/conta/sessao`. O backend continua aceitando esse
formato (expand/contract: adiciona o novo, mantem o antigo funcionando, so remove
depois que o force-update tirar de campo as versoes que dependiam dele). Remover a
coluna agora quebraria o INSERT desses clientes.

Quando a build nova estiver em campo e as antigas retiradas, uma migracao futura
pode dropar a coluna.

⚠️ DOWNGRADE NAO RESTAURA AS DATAS
----------------------------------
O passo 3 e destrutivo por natureza: o dado apagado nao existe em lugar nenhum
para ser recuperado. O `downgrade` devolve o schema (dropa a coluna, restaura a
view antiga), mas `dt_nascimento` continuara NULL, e o `ic_publico` da view antiga
passaria a ser FALSE para todos. Rodar o downgrade em producao exigiria repovoar a
data por outro meio — nao ha esse meio. Esta escrito aqui para ninguem descobrir
depois.

Revision ID: 0010_declaracao_idade
Revises: 0009_acao_abertura_sorteada
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op

# Maximo 32 caracteres: `alembic_version.version_num` e VARCHAR(32).
revision: str = "0010_declaracao_idade"
down_revision: Union[str, None] = "0009_acao_abertura_sorteada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Espelha IDADE_MINIMA de `api/conta/servico.py`. Fica literal no SQL do backfill
# porque migracao e um retrato do passado: se a idade minima mudar amanha, esta
# migracao tem de continuar contando a historia de HOJE.
IDADE_MINIMA = 13


def upgrade() -> None:
    # 1. A coluna. DEFAULT FALSE para que qualquer linha nova sem declaracao
    #    explicita seja tratada como "nao declarou" (o servico e quem exige).
    op.execute(
        """
        ALTER TABLE conta.tb001_usuario
        ADD COLUMN IF NOT EXISTS ic_idade_minima_declarada
            BOOLEAN NOT NULL DEFAULT FALSE
        """
    )

    # 2. Backfill a partir da data que ja existe. `dt_nascimento IS NOT NULL`
    #    exclui as contas ja anonimizadas (exclusao de conta zera a data) — elas
    #    nao devem ganhar declaracao nenhuma.
    op.execute(
        f"""
        UPDATE conta.tb001_usuario
        SET ic_idade_minima_declarada = TRUE
        WHERE dt_nascimento IS NOT NULL
          AND dt_nascimento <= (current_date - INTERVAL '{IDADE_MINIMA} years')
        """
    )

    # 3. Zera a data em TODAS as linhas (a padronizacao pedida). O `WHERE` evita
    #    reescrever quem ja esta nulo e faz a contagem do NOTICE ser o numero de
    #    linhas que realmente perderam o dado.
    conexao = op.get_bind()
    resultado = conexao.exec_driver_sql(
        "UPDATE conta.tb001_usuario "
        "SET dt_nascimento = NULL, dh_atualizacao = now() "
        "WHERE dt_nascimento IS NOT NULL"
    )
    print(f"[0010] dt_nascimento zerada em {resultado.rowcount} linha(s).")

    # 4a. `conta.vw001_usuario` — recriada para o `SELECT *` reexpandir e passar a
    #     enxergar a coluna nova. Sem isto a API (que le tudo pela view) nunca
    #     receberia o campo, e o bug seria silencioso: nenhum erro, so um campo
    #     que "some" da resposta.
    op.execute("DROP VIEW IF EXISTS conta.vw001_usuario")
    op.execute(
        "CREATE VIEW conta.vw001_usuario AS SELECT * FROM conta.tb001_usuario"
    )

    # 4b. `progressao.vw101_ranking_global_geral` — o `ic_publico` passa a olhar a
    #     declaracao. Colunas explicitas (nao `SELECT *`), entao a definicao vai
    #     inteira aqui; o resto e identico ao da 0003.
    op.execute("DROP VIEW IF EXISTS progressao.vw101_ranking_global_geral")
    op.execute(
        """
        CREATE VIEW progressao.vw101_ranking_global_geral AS
        SELECT g.id_usuario,
               u.co_usuario,
               u.no_exibicao,
               g.nu_xp_total,
               DENSE_RANK() OVER (ORDER BY g.nu_xp_total DESC) AS nu_posicao,
               (g.ic_visivel_placar AND u.ic_idade_minima_declarada) AS ic_publico
        FROM progressao.tb001_progressao_usuario g
        JOIN conta.tb001_usuario u ON u.id_usuario = g.id_usuario
        WHERE g.nu_xp_total > 0
        """
    )


def downgrade() -> None:
    # Restaura a view do ranking na forma da 0003 (baseada em dt_nascimento).
    # ⚠️ Como as datas foram zeradas no upgrade e NAO ha como recupera-las, o
    # `ic_publico` voltara FALSE para todo mundo. Ver o aviso no cabecalho.
    op.execute("DROP VIEW IF EXISTS progressao.vw101_ranking_global_geral")
    op.execute(
        f"""
        CREATE VIEW progressao.vw101_ranking_global_geral AS
        SELECT g.id_usuario,
               u.co_usuario,
               u.no_exibicao,
               g.nu_xp_total,
               DENSE_RANK() OVER (ORDER BY g.nu_xp_total DESC) AS nu_posicao,
               (g.ic_visivel_placar
                AND u.dt_nascimento IS NOT NULL
                AND u.dt_nascimento <= (current_date - INTERVAL '{IDADE_MINIMA} years')
               ) AS ic_publico
        FROM progressao.tb001_progressao_usuario g
        JOIN conta.tb001_usuario u ON u.id_usuario = g.id_usuario
        WHERE g.nu_xp_total > 0
        """
    )

    # A view de usuario tem de ser derrubada ANTES do DROP COLUMN: ela depende da
    # coluna (o `SELECT *` virou lista explicita no catalogo do Postgres).
    op.execute("DROP VIEW IF EXISTS conta.vw001_usuario")
    op.execute(
        "ALTER TABLE conta.tb001_usuario DROP COLUMN IF EXISTS ic_idade_minima_declarada"
    )
    op.execute(
        "CREATE VIEW conta.vw001_usuario AS SELECT * FROM conta.tb001_usuario"
    )
