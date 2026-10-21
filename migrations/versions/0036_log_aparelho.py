"""O aparelho e o uso de cada dia: a amostra de versoes da adocao gradual.

Revision ID: 0036_log_aparelho
Revises: 0035_desafio_quatro
Create Date: 2026-10-20

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO FAZ
═══════════════════════════════════════════════════════════════════════════

Cria, no schema `log`, as duas tabelas do `data-model.md` §4 da spec 010,
validado pelo dono na folha de aval da T003 (13/10/2026, §8zzz):

- `log.tb003_aparelho`: uma linha por INSTALACAO do app, com o que quase nao
  muda (fabricante, modelo, processador, memoria, tela);
- `log.tb004_aparelho_dia`: uma linha por aparelho por DIA LOCAL, com a maior
  versao do app vista naquele dia, o sistema, o idioma e o espaco ocupado.

Mais os dois indices e as duas views, com as colunas LISTADAS (a licao da
0017: uma view com `SELECT *` congela as colunas do dia em que nasceu, e a
coluna acrescentada depois nao aparece nela).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTAS TABELAS EXISTEM
═══════════════════════════════════════════════════════════════════════════

A adocao gradual do jogo novo (RF-DES-025/026, RF-QTR-164a) decide quantos
dias o Quatro em Linha aparece no Desafio do Dia pela fracao dos aparelhos que
ja tem a versao que o joga. E essa amostra NAO existia (research R-23): a
versao do app viajava no cabecalho `X-App-Version` de todo pedido e nao era
gravada em lugar nenhum que servisse de amostra.

O dono a quis como o PRIMEIRO PASSO DE ANALYTICS, no schema `log` e em duas
tabelas, e nao como coluna do `desafio_dia`: o dado e do aparelho, e nao do
desafio (§8zzz).

═══════════════════════════════════════════════════════════════════════════
⚠️ "APARELHO" E A INSTALACAO, E NAO O HARDWARE
═══════════════════════════════════════════════════════════════════════════

O `id_aparelho` e gerado pelo proprio app na 1a abertura (UUID v4) e guardado
no aparelho. Nenhum identificador de hardware e lido (nem IMEI, nem
`androidId`, nem `identifierForVendor`): quem desinstala e instala de novo vira
um aparelho novo. E a mesma natureza dos ids do Firebase, e e o que as duas
lojas aceitam sem atrito.

⚠️ **A LINHA LEGADA.** O app 1.3 em campo nao manda codigo nenhum, mas TEM de
entrar na conta: se a amostra viesse so da 1.4, as versoes antigas nunca
apareceriam e a adocao leria 100% no dia do lancamento. Para ele o servidor
sintetiza o `id_aparelho` a partir da conta e da plataforma (uuid5), com
`ic_legado = TRUE` e os detalhes nulos. O convidado do 1.3 nao tem conta e fica
de fora. Quem faz isso e `api/aparelhos/regras.py`.

═══════════════════════════════════════════════════════════════════════════
SEM FK PARA `conta`, DE PROPOSITO (o precedente da 0016)
═══════════════════════════════════════════════════════════════════════════

O aparelho nao e de uma pessoa: o convidado tem aparelho, e uma familia divide
um tablet. Por isso a `tb003` nao tem `id_usuario`, e a `tb004` o tem sem FK
(`NULL` = convidado). ⚠️ A consequencia: a exclusao de conta nao zera esse
vinculo sozinha, em cascata nenhuma. Quem o zera e
`api/conta/repositorio.py::remover_dados_vinculados`.

A unica FK e a da `tb004` para a `tb003`, com `ON DELETE CASCADE`: o dia nao
existe sem o aparelho.

═══════════════════════════════════════════════════════════════════════════
ADITIVA, COMO MANDA A REGRA DESDE A 0011
═══════════════════════════════════════════════════════════════════════════

`CREATE TABLE`, `CREATE INDEX` e `CREATE VIEW` novos. Nenhum `DROP`, nenhum
`ALTER` em coisa existente, nenhuma linha tocada.
`tests/unitarios/test_migracoes_aditivas.py` recusa qualquer `DROP` no
`upgrade()`, e `tests/unitarios/test_migracao_aparelho_bate_com_data_model.py`
confere cada coluna contra o documento que o dono validou.

⚠️ **Aplicada pelo dono** (escrita no banco e comando dele): no `des` antes do
push que leva a API que grava nestas tabelas; no `prd` na virada, depois do
backup, antes do deploy do backend (`data-model.md` §7).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0036_log_aparelho"
down_revision: Union[str, None] = "0035_desafio_quatro"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as duas tabelas do aparelho, os indices e as views."""
    # O schema `log` ja existe desde a 0005. O `IF NOT EXISTS` esta aqui para a
    # migracao nao depender da ordem - nao para criar.
    op.execute("CREATE SCHEMA IF NOT EXISTS log")

    op.execute(
        """
        CREATE TABLE log.tb003_aparelho (
            -- A CHAVE. Gerada pelo app (v4) ou, na linha legada, sintetizada
            -- pelo servidor (v5, deterministica: o mesmo app 1.3 cai sempre na
            -- mesma linha, e o registro e idempotente).
            id_aparelho             UUID         PRIMARY KEY,
            -- TRUE = linha sintetizada para um app sem o codigo (ate a 1.3).
            ic_legado               BOOLEAN      NOT NULL DEFAULT FALSE,
            -- `web` existe porque o `X-Platform` o aceita (ambiente de
            -- desenvolvimento); um valor fora da lista seria 500 no meio da
            -- noite, e o CHECK abaixo o recusa antes.
            co_plataforma           VARCHAR(10)  NOT NULL,

            -- O QUE QUASE NAO MUDA. Todos nulos na linha legada, e todos
            -- opcionais no envio: aparelho que nao informa um campo nao perde
            -- os outros.
            no_fabricante           VARCHAR(40),
            -- A mesma largura de `log.tb002.no_modelo_aparelho` e de `co_abi`
            -- de la: larguras diferentes para a mesma coisa sao a primeira
            -- rachadura de um JOIN que um dia trunca.
            no_modelo               VARCHAR(80),
            co_abi                  VARCHAR(20),
            -- O SoC, no Android 12 em diante; no iOS o modelo ja diz o chip.
            no_processador          VARCHAR(60),
            qt_nucleos              SMALLINT,
            -- A memoria TOTAL. A disponivel nao entra: muda a cada segundo.
            nu_ram_mb               INTEGER,
            -- A tela em pontos logicos, como o layout a ve, e a densidade
            -- (pixels por ponto). NUMERIC(4,2) vai ate 99,99, e a maior
            -- densidade de tela em campo passa pouco de 4.
            nu_tela_largura_dp      SMALLINT,
            nu_tela_altura_dp       SMALLINT,
            nu_densidade_tela       NUMERIC(4,2),
            -- O `appInstanceId` do Firebase Analytics, para cruzar as duas
            -- fontes. ⚠️ NUNCA e chave: quem recusa o consentimento nao o tem.
            co_instancia_analytics  VARCHAR(64),
            -- A 1a vez que o SERVIDOR o viu (`now()` daqui, e nao o relogio do
            -- aparelho: um telefone com a data errada envenenaria a serie).
            dh_registro             TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT ck001_plataforma
                CHECK (co_plataforma IN ('android', 'ios', 'web'))
        )
        """
    )

    op.execute(
        """
        CREATE TABLE log.tb004_aparelho_dia (
            -- O dia nao existe sem o aparelho: apagar o aparelho leva os dias.
            id_aparelho        UUID         NOT NULL
                REFERENCES log.tb003_aparelho(id_aparelho) ON DELETE CASCADE,
            -- O dia LOCAL da pessoa (o instante do servidor mais o fuso dela),
            -- e nao o dia UTC: e o mesmo relogio da chama.
            dt_dia_local       DATE         NOT NULL,
            -- Quem estava logado. NULL = convidado. Sem FK (precedente 0016),
            -- e por isso a exclusao de conta o zera a mao.
            id_usuario         UUID,
            -- A MAIOR versao vista no dia. Abrir o app cinco vezes da uma
            -- linha; atualizar no meio do dia sobe a versao, e nunca a desce.
            co_versao_app      VARCHAR(20)  NOT NULL,
            -- A largura de `log.tb002.co_versao_so`.
            co_versao_so       VARCHAR(40),
            -- O idioma do app, do `Accept-Language` (pt, en, es).
            co_idioma          VARCHAR(5),
            -- Quanto o app ocupa no aparelho, no total. Vai todo dia.
            nu_espaco_app_kb   INTEGER,
            -- O detalhe por pasta, SO quando o total passa do limite da
            -- plataforma (`ESPACO_APP_DETALHE_MB_ANDROID`/`_IOS`). Abaixo dele
            -- fica NULL e nao custa nada. Quem decide e o servidor.
            js_espaco_app      JSONB,
            dh_registro        TIMESTAMPTZ  NOT NULL DEFAULT now(),

            -- ⚠️ A GARANTIA de "uma linha por aparelho por dia": o registro e
            -- um UPSERT nesta chave, e nao um INSERT que confia no app.
            CONSTRAINT pk_aparelho_dia PRIMARY KEY (id_aparelho, dt_dia_local)
        )
        """
    )

    # ── Os indices, e cada um responde a uma pergunta que se vai fazer ───────
    #
    # 1. "quais aparelhos foram vistos nos ultimos 7 dias?" - a leitura do job
    #    da adocao. A PK comeca pelo aparelho e nao serve a um filtro por data.
    op.execute(
        "CREATE INDEX ix_aparelho_dia_data "
        "ON log.tb004_aparelho_dia (dt_dia_local)"
    )
    # 2. "as linhas desta pessoa" - a exclusao de conta e as consultas por
    #    pessoa. Sem ele, zerar o vinculo de uma conta varreria a tabela.
    op.execute(
        "CREATE INDEX ix_aparelho_dia_usuario "
        "ON log.tb004_aparelho_dia (id_usuario)"
    )

    # Convencao do projeto: servicos LEEM pela VIEW e ESCREVEM na tabela.
    # ⚠️ Colunas LISTADAS, e nao `SELECT *` (a licao da 0017): quem acrescentar
    # uma coluna depois acrescenta tambem aqui, e o cadeado do data-model
    # confere que a view tem todas.
    op.execute(
        """
        CREATE VIEW log.vw003_aparelho AS
        SELECT a.id_aparelho,
               a.ic_legado,
               a.co_plataforma,
               a.no_fabricante,
               a.no_modelo,
               a.co_abi,
               a.no_processador,
               a.qt_nucleos,
               a.nu_ram_mb,
               a.nu_tela_largura_dp,
               a.nu_tela_altura_dp,
               a.nu_densidade_tela,
               a.co_instancia_analytics,
               a.dh_registro
          FROM log.tb003_aparelho a
        """
    )
    op.execute(
        """
        CREATE VIEW log.vw004_aparelho_dia AS
        SELECT d.id_aparelho,
               d.dt_dia_local,
               d.id_usuario,
               d.co_versao_app,
               d.co_versao_so,
               d.co_idioma,
               d.nu_espaco_app_kb,
               d.js_espaco_app,
               d.dh_registro
          FROM log.tb004_aparelho_dia d
        """
    )

    op.execute(
        """
        COMMENT ON TABLE log.tb003_aparelho IS
        'Uma linha por INSTALACAO do app (o codigo e gerado pelo app, e nao lido '
        'do hardware). ic_legado = linha sintetizada pelo servidor para um app '
        'sem o codigo (ate a 1.3), a partir da conta e da plataforma. Sem '
        'id_usuario: o aparelho nao e de uma pessoa.'
        """
    )
    op.execute(
        """
        COMMENT ON TABLE log.tb004_aparelho_dia IS
        'Uma linha por aparelho por DIA LOCAL, com a MAIOR versao do app vista '
        'no dia. E a amostra da adocao gradual do Desafio do Dia (job/adocao.py). '
        'id_usuario sem FK; a exclusao de conta o zera.'
        """
    )


def downgrade() -> None:
    # ⚠️ `DROP` aqui e legitimo: o `downgrade()` nunca roda em producao (existe
    # para o ambiente local) e o cadeado de migracao aditiva o ignora de
    # proposito. No `upgrade()` seria proibido.
    #
    # ⚠️ O schema `log` NAO sai: ele e da 0005, e a `tb001` e a `tb002` vivem
    # nele. A ordem e a inversa da criacao: a view antes da tabela, e o dia
    # antes do aparelho (a FK).
    op.execute("DROP VIEW IF EXISTS log.vw004_aparelho_dia")
    op.execute("DROP VIEW IF EXISTS log.vw003_aparelho")
    op.execute("DROP TABLE IF EXISTS log.tb004_aparelho_dia")
    op.execute("DROP TABLE IF EXISTS log.tb003_aparelho")
