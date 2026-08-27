"""O poder VOLTAR JOGADA no log, e o probing da base de finais.

Revision ID: 0017_poder_e_probing_base
Revises: 0016_diagnostico_motor_nativo
Create Date: 2026-08-27

⛔⛔⛔ **PROPOSTA — NAO FOI APLICADA EM NENHUM BANCO.** ⛔⛔⛔

Este arquivo existe para ser **lido e aprovado** pelo dono antes de rodar, pela
regra permanente do projeto: nada de banco sem o OK dele. Antes de qualquer
`alembic upgrade`, rodar `scripts/identificar_banco.py` — o `AMBIENTE` do `.env`
**nao e prova** de para onde a conexao aponta.

    DES = hopper.proxy.rlwy.net:21165
    PRD = hayabusa.proxy.rlwy.net:42857

═══════════════════════════════════════════════════════════════════════════
O QUE ENTRA, E POR QUE TUDO NUMA MIGRACAO SO
═══════════════════════════════════════════════════════════════════════════

Duas coisas que nasceram separadas e chegam juntas por pedido explicito do dono
em 27/08/2026: *"Lembre-se que aqueles 2 campos de quantidade de busca de base
devem entrar juntos nestas tarefas."*

**(A) O poder "voltar jogada"** (T203 e T204). A pessoa assiste a um anuncio
premiado e desfaz o proprio lance e a resposta do personagem. O log precisa
dizer que isso aconteceu — se nao disser, a partida sobe como se ela tivesse
acertado de primeira.

**(B) O probing da base de finais** (motor Dart 1.4.0 / Rust 0.4.0). Os dois
numeros ja chegam a tela desde 27/08; ate agora nao havia onde grava-los.

Uma migracao, e nao duas: as duas mexem no mesmo caminho de gravacao, e duas
migracoes seguidas dobrariam a janela em que `des` e `prd` estao em versoes
diferentes por nada.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE O PODER FICA EM `partida`, E NAO EM `jogo_damas`
═══════════════════════════════════════════════════════════════════════════

O poder **estreia** nas damas, mas nasceu compartilhado: no app ele mora em
`lib/core/poderes/`, e a tela de qualquer jogo do hub pode chama-lo. Uma jogada
desfeita e uma jogada desfeita em qualquer jogo.

Por-lo em `jogo_damas.tb002_jogada` significaria copiar as mesmas quatro colunas
para `jogo_velha` e `jogo_pontinhos` no dia em que o dono ligar o poder neles —
e, pior, escrever a consulta de reputacao tres vezes. E a armadilha que o
frontend ja pagou caro tres vezes (*"tela igual em dois jogos e UM widget, nao
dois parecidos"*), aparecendo agora no banco.

═══════════════════════════════════════════════════════════════════════════
⚠️ `nu_ordem` E `nu_lance` SAO DOIS NUMEROS — e e a decisao central daqui
═══════════════════════════════════════════════════════════════════════════

**Decisao do dono, 27/08/2026:** a numeracao e **sequencia continua de eventos**.

    A pessoa joga os lances 1..8. Usa o poder: os lances 7 e 8 saem do
    tabuleiro. Ela joga de novo.

    nu_ordem  |  1 2 3 4 5 6   7    8    9  10
    nu_lance  |  1 2 3 4 5 6   7    8    7   8
    cancelada |  . . . . . .   X    X    .   .

`nu_ordem` **nunca recua e nunca se repete**: `partida.tb002_jogada` tem
`CONSTRAINT uq_jogada_ordem UNIQUE (id_partida, nu_ordem)` desde a 0003, e duas
linhas com `nu_ordem = 7` quebram a chave. Mexer nessa constraint seria alterar
uma tabela **ja publicada**, contra a regra de migracao aditiva que vale desde a
0011.

`nu_lance` e o numero do lance **no tabuleiro**, e ele recua junto com o
desfazer. Sem ele, *"quantos lances teve esta partida?"* responderia 10 numa
partida de 8 lances, e todo replay que percorresse `nu_ordem` rejogaria as
jogadas canceladas.

⚠️ **`nu_lance` e ANULAVEL, e nao ha backfill.** O Pontinhos e a velha nao o
informam (nao tem poder, entao la `nu_lance` **e** `nu_ordem`), e o app so o
envia quando o jogo o preenche — e isso mantem o payload dos dois jogos
publicados byte a byte identico ao que ja esta em campo, que e o portao de
`test/core/partidas/payload_inalterado_test.dart` no frontend.

A leitura correta e **`COALESCE(nu_lance, nu_ordem)`**, e a view ja a entrega
pronta na coluna derivada `nu_lance_efetivo` — para ninguem precisar lembrar.

    A alternativa considerada e descartada: um `UPDATE tb002_jogada SET
    nu_lance = nu_ordem` para preencher o passado. Ela funcionaria (toda partida
    ja gravada e sem poder, por construcao), mas custaria por `UPDATE` na lista
    de comandos permitidos do cadeado de migracoes — o mesmo argumento com que a
    0014 recusou consertar 25 linhas de teste no `des`.

═══════════════════════════════════════════════════════════════════════════
⚠️ A LINHA CANCELADA NAO E APAGADA, E ISSO E O PONTO
═══════════════════════════════════════════════════════════════════════════

A jogada desfeita **aconteceu**: a pessoa a viu no tabuleiro, o personagem
respondeu a ela, o relogio andou. O log e append-only.

Apagar esconderia justamente o que a reputacao do Magno precisa enxergar, e
tornaria impossivel saber se o poder esta sendo usado para consertar um deslize
ou para procurar o lance certo por tentativa e erro — que e a diferenca entre um
recurso de acessibilidade e um jeito de trapacear com a propria paciencia.

**Consequencia para toda consulta ja escrita:** contar lances passa a ser
`WHERE NOT ic_cancelada`. A coluna nasce `NOT NULL DEFAULT FALSE`, entao nenhuma
consulta antiga muda de resultado — mas as novas precisam do filtro.

═══════════════════════════════════════════════════════════════════════════
⚠️ `qt_usos_poder` NA PARTIDA — a T208 depende dela
═══════════════════════════════════════════════════════════════════════════

**Nas palavras do dono, 27/08/2026:** *"Conta como vitoria. Mas nao leva a
conquista SEM USO DE PODER. A reputacao do Magno passa a ser contada pelas
vitorias sem uso de poder pelo humano."*

Ou seja: *"ninguem derrotou o Magno"* passa a significar **vitorias com
`qt_usos_poder = 0`**. Sem isso a reputacao se dissolve — com poder bastante,
qualquer pessoa o derrota.

Derivar de `EXISTS (SELECT 1 FROM tb002_jogada WHERE ic_cancelada)` funcionaria,
e roda uma subconsulta por partida em todo levantamento de reputacao. A coluna
torna o filtro um predicado indexavel.

⚠️ **Conta USOS, e nao jogadas canceladas.** Um uso de "voltar jogada" desfaz
**duas** jogadas; um poder futuro (uma dica, por exemplo) pode nao desfazer
nenhuma. Contar linhas canceladas responderia outra pergunta, e responderia
errado no dia em que o segundo poder chegar.

⚠️ **Uma coluna, e nao duas.** Um `ic_com_poder` ao lado seria `qt_usos_poder >
0` escrito de novo. Duas verdades sobre o mesmo fato divergem no dia em que
alguem atualizar so uma — e a view ja entrega o booleano derivado, de graca.

═══════════════════════════════════════════════════════════════════════════
⚠️ `co_poder` E VARCHAR COM CHECK, E NAO UMA DIMENSAO `tb9xx`
═══════════════════════════════════════════════════════════════════════════

Mesma escolha, e pelo mesmo motivo, do `co_motor_busca` na 0013 e do
`co_motivo` na 0016: sao pouquissimos valores fechados, e uma dimensao custaria
um JOIN em toda consulta para nao entregar nada. Se um dia a lista crescer ou
precisar de rotulo traduzido, o CHECK vira dimensao — e ai o JOIN se paga.

⚠️ **O codigo gravado nunca muda de significado** (invariante I-8 do contrato de
log). Renomear `voltar_jogada` falsificaria todas as linhas ja gravadas.

═══════════════════════════════════════════════════════════════════════════
OS DOIS CONTADORES DA BASE — e por que sao DOIS
═══════════════════════════════════════════════════════════════════════════

`qt_consultas_base` = quantas vezes a busca **perguntou** a base de finais neste
lance. `qt_acertos_base` = quantas dessas perguntas **tiveram resposta**.

E a **razao** entre eles que diz se o probing se paga: muitas consultas com
poucos acertos significa que a arvore quase nunca alcanca finais de 4 pecas
naquele tipo de partida, e ai o esforco de consultar (um acesso a disco no meio
da arvore) custa mais do que rende. Com um numero so, esse diagnostico nao
existe.

⚠️ **Anulaveis, e `NULL` nao e `0`.** `NULL` = *"nao houve busca"* (lance do
humano, lance unico, lance que veio pronto da base); `0` = *"houve busca e ela
nao consultou uma vez sequer"* — que e o estado normal com o probing desligado, e
o sintoma a investigar com ele ligado. Colapsar os dois repetiria, numa coluna
nova, o defeito que custou caro na T197: a telemetria que responde `0` onde a
verdade e "nao sei".

⚠️ **`ck_damas_acertos_nao_passam_consultas`**: a base nao pode responder mais
vezes do que foi perguntada. Se o par sair invertido, a razao passa de 100% e o
diagnostico vira ruido, sem que nada denuncie.

⚠️ **NAO ha motivo de parada novo.** O `tasks.md` falava em `7 =
decidido_por_base`; conferido no motor, ele nao existe. O probing acontece
DENTRO da arvore e nao encerra a busca — quem encerra e o `6 = base_finais`, que
a 0015 ja criou, e que vale para o lance respondido na RAIZ.

═══════════════════════════════════════════════════════════════════════════
NENHUMA DIMENSAO NASCE AQUI — e por que isso e uma decisao, e nao um esquecimento
═══════════════════════════════════════════════════════════════════════════

`co_poder` e VARCHAR com CHECK, e nao uma `tb9NN_`. A unica dimensao que este
arquivo toca e a `jogo_damas.tb902_motivo_parada_busca`, e apenas para **ler**
no JOIN da view — nenhum valor novo entra nela.

Consequencia: o sentinela **`9999 = 'desconhecido'`** continua sendo o que a
0012 criou, e nao ha um novo a criar. Ele existe para o caso de um app **mais
novo** que o backend enviar um codigo que a dimensao ainda nao conhece: sem o
destino de escape a FK estoura, o endpoint devolve 500, e o evento fica **preso
para sempre** na fila daquele aparelho — a partida da pessoa nunca sobe. Com
`co_poder` sendo um CHECK, esse risco simplesmente nao se aplica: um valor
desconhecido e recusado na hora da gravacao, e o ingestor o trata como campo
ignorado (decisao V-5), sem prender nada.

═══════════════════════════════════════════════════════════════════════════
COMPATIBILIDADE — o que acontece com cada lado desatualizado
═══════════════════════════════════════════════════════════════════════════

| Cenario | O que acontece | Aceitavel? |
|---|---|---|
| App **antigo** x banco novo | ele nao envia as chaves; os `DEFAULT` cobrem, e `nu_lance` fica `NULL` (que e `nu_ordem`, pela view) | **sim** |
| App novo x backend **antigo** | o ingestor ignora as chaves que nao conhece (decisao V-5); a partida entra sem a marca do poder | **sim, por desenho** — e o motivo de a ordem de deploy ser banco → backend → lojas |
| Consulta antiga sobre `tb002_jogada` | conta a jogada cancelada como se fosse um lance | ⚠️ **e o unico ponto de atencao real** — ver a secao seguinte |

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTA MIGRACAO **NAO** FAZ, E FICA PARA A T208
═══════════════════════════════════════════════════════════════════════════

Ela **nao** reescreve as consultas de gestao de `ferramentas/consultas_sql/`.
Toda consulta que hoje conta lances ou apura vitorias contra o Magno passa a
precisar de `WHERE NOT ic_cancelada` e de `qt_usos_poder = 0`, respectivamente.
Enquanto as damas nao estiverem publicadas isso nao muda numero nenhum — nao ha
partida com poder em campo —, mas e divida, e ela tem dono: **T208**.

═══════════════════════════════════════════════════════════════════════════
ADITIVA, COMO MANDA A REGRA DESDE A 0011
═══════════════════════════════════════════════════════════════════════════

`ADD COLUMN` (todas anulaveis ou com `DEFAULT`), `ADD CONSTRAINT` (todos
satisfeitos pelas linhas existentes, porque as colunas nascem vazias ou no
default) e `DROP VIEW` **com o `CREATE VIEW` correspondente na mesma migracao**
— a excecao que a 0014 abriu e que `tests/unitarios/test_migracoes_aditivas.py`
reconhece. Nenhum `DROP TABLE`, `DROP COLUMN`, `UPDATE`, `DELETE` ou `TRUNCATE`.

⚠️ **Por que as views precisam ser recriadas.** `partida.vw001_partida` e
`partida.vw002_jogada` foram criadas com `SELECT p.*` — e o PostgreSQL expande o
`*` no momento da criacao e guarda a lista resolvida. Elas **nao enxergam**
colunas acrescentadas depois. Deixa-las como estao faria as colunas novas
existirem na tabela e serem invisiveis para quem le pela view, que e como o
projeto manda ler. O sintoma seria o pior possivel: nenhum erro, so a coluna
nunca aparecendo — exatamente o que a 0013 descreve.

Aqui o conserto e `DROP VIEW` + `CREATE VIEW`, e nao `CREATE OR REPLACE`, porque
as duas terminam numa coluna **derivada** (`co_resultado`, `ic_cpu`): as colunas
novas do `p.*` entrariam ANTES dela, e `CREATE OR REPLACE VIEW` so aceita
acrescentar ao **fim**. Ha usuarios reais em `prd` desde 04/08/2026 — e uma VIEW
nao guarda dado nenhum, o DDL do Postgres e transacional, e as duas voltam com o
mesmo corpo com que a 0006 as criou.

`jogo_damas.vw002_jogada` ja lista as colunas explicitamente (a 0013 a
reescreveu), entao ela aceita `CREATE OR REPLACE` com as novas no fim.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0017_poder_e_probing_base"
down_revision: Union[str, None] = "0016_diagnostico_motor_nativo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ════════════════════════════════════════════════════════════════════════
    # 1) AS VIEWS SAEM PRIMEIRO — e a ordem NAO e estetica
    # ════════════════════════════════════════════════════════════════════════
    #
    # ⚠️ **Sem elas, as colunas novas seriam invisiveis.**
    # `partida.vw001_partida` e `partida.vw002_jogada` foram criadas com
    # `SELECT p.*`, e o PostgreSQL expande o `*` no momento da criacao e guarda
    # a lista resolvida: elas **nao enxergam** colunas acrescentadas depois.
    # Deixa-las como estao faria as colunas existirem na tabela e nao aparecerem
    # para quem le pela view, que e como o projeto manda ler. Nenhum erro, so a
    # coluna nunca aparecendo — exatamente o que a 0013 descreve.
    #
    # ⚠️ **E `DROP VIEW` + `CREATE VIEW`, e nao `CREATE OR REPLACE`**, porque as
    # duas terminam numa coluna **derivada** (`co_resultado`, `ic_cpu`): as
    # colunas novas do `p.*` entrariam ANTES dela, e `CREATE OR REPLACE VIEW` so
    # aceita acrescentar ao **fim**. E a excecao que a 0014 abriu, e ela e segura
    # — uma view nao guarda dado nenhum, o DDL do Postgres e transacional (os
    # comandos sobem juntos ou nao sobem), e as duas voltam com o mesmo corpo
    # com que a 0006 as criou, mais a coluna derivada nova.
    #
    # ⚠️ **E elas saem ANTES dos `ALTER TABLE`, e nao depois.** E a mesma ordem
    # da 0014, e ha um motivo pratico alem do estilo:
    # `tests/unitarios/test_migracoes_aditivas.py` procura `ALTER TABLE …DROP`
    # com `re.DOTALL`, entao qualquer `DROP` que apareca **depois** de um `ALTER
    # TABLE` no mesmo `upgrade()` e recusado — mesmo sendo um `DROP VIEW`
    # legitimo. O cadeado pegou a primeira versao deste arquivo.
    op.execute("DROP VIEW IF EXISTS partida.vw002_jogada")
    op.execute("DROP VIEW IF EXISTS partida.vw001_partida")

    # ════════════════════════════════════════════════════════════════════════
    # 2) O PODER, na jogada generica
    # ════════════════════════════════════════════════════════════════════════
    #
    # `IF NOT EXISTS` em todas: a migracao tem de ser reexecutavel sem erro, o
    # mesmo cuidado do `ON CONFLICT DO NOTHING` da 0013 e da 0015.
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            ADD COLUMN IF NOT EXISTS nu_lance        INT,
            ADD COLUMN IF NOT EXISTS ic_cancelada    BOOLEAN     NOT NULL
                                                     DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS co_poder        VARCHAR(30),
            ADD COLUMN IF NOT EXISTS dh_cancelamento TIMESTAMPTZ
        """
    )

    # ── Os dois lados do cancelamento andam JUNTOS ──────────────────────────
    #
    # Uma linha que diz "cancelada" sem dizer por qual poder e quando e uma
    # linha que ninguem consegue interpretar meses depois; e um `co_poder` numa
    # jogada que nao foi cancelada e telemetria inventada. Os dois erros sao
    # faceis de cometer no app e invisiveis num relatorio.
    #
    # ⚠️ O CHECK e satisfeito por toda linha existente: elas tem
    # `ic_cancelada = FALSE` (o default) e os dois campos nulos.
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            ADD CONSTRAINT ck_jogada_cancelamento_completo
            CHECK (
                (ic_cancelada AND co_poder IS NOT NULL
                             AND dh_cancelamento IS NOT NULL)
                OR
                (NOT ic_cancelada AND co_poder IS NULL
                                 AND dh_cancelamento IS NULL)
            )
        """
    )

    # ⚠️ VARCHAR com CHECK, e nao dimensao — ver o cabecalho. Um poder novo
    # entra por migracao propria, que e o momento certo para alguem perguntar
    # se o app tambem sabe grava-lo.
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            ADD CONSTRAINT ck_jogada_poder
            CHECK (co_poder IS NULL OR co_poder IN ('voltar_jogada'))
        """
    )

    # O cancelamento vem DEPOIS da jogada — sempre. Uma linha que dissesse o
    # contrario seria relogio do aparelho andando para tras, e o dado que dela
    # se extrai ("quanto tempo a pessoa levou para se arrepender") sairia
    # negativo.
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            ADD CONSTRAINT ck_jogada_cancelamento_depois
            CHECK (dh_cancelamento IS NULL OR dh_cancelamento >= dh_jogada)
        """
    )

    # `nu_lance` e positivo quando existe. Nao ha lance zero.
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            ADD CONSTRAINT ck_jogada_lance_positivo
            CHECK (nu_lance IS NULL OR nu_lance >= 1)
        """
    )

    # Consulta de gestao mais frequente que a coluna cria: "as jogadas vivas
    # desta partida". Parcial, porque as canceladas sao a minoria absoluta — o
    # indice fica pequeno e serve exatamente ao filtro que a T208 vai usar.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_jogada_cancelada
            ON partida.tb002_jogada (id_partida)
         WHERE ic_cancelada
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # 3) O PODER, no nivel da PARTIDA (T204)
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            ADD COLUMN IF NOT EXISTS qt_usos_poder SMALLINT NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            ADD CONSTRAINT ck_partida_usos_poder CHECK (qt_usos_poder >= 0)
        """
    )

    # ⚠️ O indice da REPUTACAO DO MAGNO (T208). Parcial em `qt_usos_poder = 0`
    # porque a pergunta e sempre essa: as vitorias **sem** poder, no nivel
    # sagaz. Um indice cheio guardaria tambem as partidas com poder, que essa
    # consulta nunca le.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_partida_sem_poder
            ON partida.tb001_partida (co_jogo, co_dificuldade)
         WHERE qt_usos_poder = 0
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # 4) O PROBING DA BASE DE FINAIS, na extensao das damas
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD COLUMN IF NOT EXISTS qt_consultas_base INTEGER,
            ADD COLUMN IF NOT EXISTS qt_acertos_base   INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD CONSTRAINT ck_damas_acertos_nao_passam_consultas
            CHECK (
                qt_consultas_base IS NULL
                OR qt_acertos_base IS NULL
                OR qt_acertos_base <= qt_consultas_base
            )
        """
    )
    # Os dois andam juntos: ou houve busca (e os dois existem) ou nao houve (e
    # nenhum existe). Um par meio-preenchido e bug de mapeamento no app, e a
    # razao acertos/consultas nao se calcula sobre ele.
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD CONSTRAINT ck_damas_probing_completo
            CHECK ((qt_consultas_base IS NULL) = (qt_acertos_base IS NULL))
        """
    )
    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            ADD CONSTRAINT ck_damas_consultas_nao_negativas
            CHECK (qt_consultas_base IS NULL OR qt_consultas_base >= 0)
        """
    )

    # ════════════════════════════════════════════════════════════════════════
    # 5) AS VIEWS VOLTAM, ja enxergando as colunas novas
    # ════════════════════════════════════════════════════════════════════════
    op.execute(
        """
        CREATE VIEW partida.vw001_partida AS
        SELECT p.*,
               CASE
                 WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'
                 WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'
                 ELSE 'empate'
               END AS co_resultado,
               -- Derivado, para ninguem precisar lembrar da regra: houve poder
               -- nesta partida? E o filtro da reputacao do Magno (T208).
               (p.qt_usos_poder > 0) AS ic_com_poder
        FROM partida.tb001_partida p
        """
    )

    op.execute(
        """
        CREATE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu,
               -- ⚠️ A leitura correta de `nu_lance`, ja pronta. Nos jogos sem
               -- poder ele e NULO, e o lance E a ordem — quem consultar a
               -- coluna crua diretamente vai achar que o dado esta faltando.
               COALESCE(j.nu_lance, j.nu_ordem) AS nu_lance_efetivo
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )

    # A das damas ja lista as colunas explicitamente (a 0013 a reescreveu por
    # este mesmo motivo), entao aqui `CREATE OR REPLACE` basta: as duas novas
    # entram no fim, que e o unico lugar que ele aceita.
    op.execute(
        """
        CREATE OR REPLACE VIEW jogo_damas.vw002_jogada AS
        SELECT j.id_jogada,
               j.co_jogador,
               j.co_lance,
               j.co_fen_antes,
               j.qt_captura_pedra,
               j.qt_captura_dama,
               j.ic_promoveu,
               j.co_tipo_peca_inicio,
               j.qt_nos_visitados,
               j.nu_profundidade_atingida,
               j.nu_motivo_parada_busca,
               j.nu_tempo_busca_ms,
               j.nu_avaliacao_brancas,
               j.nu_semente,
               j.js_extra,
               m.co_motivo_parada_busca,
               m.no_motivo_parada_busca,
               j.co_motor_busca,
               -- As duas novas, por ultimo de proposito.
               j.qt_consultas_base,
               j.qt_acertos_base
          FROM jogo_damas.tb002_jogada j
          LEFT JOIN jogo_damas.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )

def downgrade() -> None:
    # A ordem e a inversa da subida, e as views saem primeiro: elas dependem das
    # colunas, e o Postgres recusaria o `DROP COLUMN` com elas de pe.
    op.execute("DROP VIEW IF EXISTS jogo_damas.vw002_jogada")
    op.execute("DROP VIEW IF EXISTS partida.vw002_jogada")
    op.execute("DROP VIEW IF EXISTS partida.vw001_partida")

    op.execute("DROP INDEX IF EXISTS partida.ix_partida_sem_poder")
    op.execute("DROP INDEX IF EXISTS partida.ix_jogada_cancelada")

    op.execute(
        """
        ALTER TABLE jogo_damas.tb002_jogada
            DROP CONSTRAINT IF EXISTS ck_damas_consultas_nao_negativas,
            DROP CONSTRAINT IF EXISTS ck_damas_probing_completo,
            DROP CONSTRAINT IF EXISTS ck_damas_acertos_nao_passam_consultas,
            DROP COLUMN IF EXISTS qt_acertos_base,
            DROP COLUMN IF EXISTS qt_consultas_base
        """
    )
    op.execute(
        """
        ALTER TABLE partida.tb001_partida
            DROP CONSTRAINT IF EXISTS ck_partida_usos_poder,
            DROP COLUMN IF EXISTS qt_usos_poder
        """
    )
    op.execute(
        """
        ALTER TABLE partida.tb002_jogada
            DROP CONSTRAINT IF EXISTS ck_jogada_lance_positivo,
            DROP CONSTRAINT IF EXISTS ck_jogada_cancelamento_depois,
            DROP CONSTRAINT IF EXISTS ck_jogada_poder,
            DROP CONSTRAINT IF EXISTS ck_jogada_cancelamento_completo,
            DROP COLUMN IF EXISTS dh_cancelamento,
            DROP COLUMN IF EXISTS co_poder,
            DROP COLUMN IF EXISTS ic_cancelada,
            DROP COLUMN IF EXISTS nu_lance
        """
    )

    # As duas views de `partida` voltam ao corpo com que a 0006 as criou.
    op.execute(
        """
        CREATE VIEW partida.vw001_partida AS
        SELECT p.*,
               CASE
                 WHEN p.nu_placar_j1 > p.nu_placar_j2 THEN 'venceu_j1'
                 WHEN p.nu_placar_j2 > p.nu_placar_j1 THEN 'venceu_j2'
                 ELSE 'empate'
               END AS co_resultado
        FROM partida.tb001_partida p
        """
    )
    op.execute(
        """
        CREATE VIEW partida.vw002_jogada AS
        SELECT j.*,
               (p.co_modo = 'vs_cpu' AND j.nu_jogador = 2) AS ic_cpu
        FROM partida.tb002_jogada j
        JOIN partida.tb001_partida p ON p.id_partida = j.id_partida
        """
    )
    # E a das damas volta ao corpo da 0013.
    op.execute(
        """
        CREATE OR REPLACE VIEW jogo_damas.vw002_jogada AS
        SELECT j.id_jogada,
               j.co_jogador,
               j.co_lance,
               j.co_fen_antes,
               j.qt_captura_pedra,
               j.qt_captura_dama,
               j.ic_promoveu,
               j.co_tipo_peca_inicio,
               j.qt_nos_visitados,
               j.nu_profundidade_atingida,
               j.nu_motivo_parada_busca,
               j.nu_tempo_busca_ms,
               j.nu_avaliacao_brancas,
               j.nu_semente,
               j.js_extra,
               m.co_motivo_parada_busca,
               m.no_motivo_parada_busca,
               j.co_motor_busca
          FROM jogo_damas.tb002_jogada j
          LEFT JOIN jogo_damas.tb902_motivo_parada_busca m
                 ON m.nu_motivo_parada_busca = j.nu_motivo_parada_busca
        """
    )
