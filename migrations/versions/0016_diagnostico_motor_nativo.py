"""O motor nativo nao carregou neste aparelho — a telemetria da indisponibilidade.

Revision ID: 0016_diagnostico_motor_nativo
Revises: 0015_motivo_base_finais_damas
Create Date: 2026-08-27

═══════════════════════════════════════════════════════════════════════════
O PEDIDO QUE ORIGINOU ESTA TABELA
═══════════════════════════════════════════════════════════════════════════

Do dono, em 25/08/2026, depois de o Release do iOS ter jogado semanas em Dart
sem que nada denunciasse:

    "devemos colocar uma trava no App: se o motor Rust nao esta carregado, nao
     exibe o nivel de dificuldade `Sagaz` para o Jogo da Dama; no entanto neste
     caso o App precisa nos enviar algum LOG para o servidor, com detalhes."

A trava e a T199, ja em campo (`logica/oferta_do_sagaz_damas.dart`). Esta
migracao e a **outra metade**: sem ela a trava esconde o nivel e nao conta a
ninguem que escondeu.

⚠️ **A queda em si e uma virtude, e nao se mexe nela.** E o que faz o app rodar
em qualquer aparelho. O que se conserta aqui e o **silencio**.

═══════════════════════════════════════════════════════════════════════════
⚠️ UMA LINHA POR CONFIGURACAO QUEBRADA, E NAO UMA POR RELATO
═══════════════════════════════════════════════════════════════════════════

**Esta e a decisao central da tabela, e ela nasceu de uma pergunta do dono em
27/08/2026:**

    "O que vai garantir ai que um mesmo telefone de 1 usuario nao vai ficar
     alimentando essa tabela indefinidamente com o mesmo registro?"

O desenho anterior respondia "o dedupe do app", e **essa resposta era fraca**. O
dedupe do app vive no `shared_preferences`, que some quando a pessoa reinstala o
app ou usa "limpar dados" — e some tambem quando o envio falha e o app,
corretamente, nao marca como relatado. Cada um desses casos gerava uma **linha
nova** dizendo exatamente o que a anterior ja dizia.

⚠️ **O problema nao era volume; era leitura.** Com uma linha por relato, a
consulta *"quantas configuracoes estao quebradas?"* passa a responder *"quantas
vezes alguem reinstalou o app num aparelho quebrado"* — outra pergunta, sem que
nada denuncie a troca.

**A solucao: `co_assinatura UNIQUE` + `ON CONFLICT DO UPDATE`.** A tabela guarda
uma linha por **combinacao** (jogo · motor · motivo · plataforma · SO · modelo ·
ABI · versao do app · versao do binario · flavor · modo de build), com
`qt_ocorrencias`, `dh_primeiro` e `dh_ultimo`. Um telefone em laco **incrementa
um contador**; nao cria linha.

⚠️ **A assinatura e calculada NO SERVIDOR**, a partir das colunas que ele mesmo
gravou. Se viesse do app, uma build com defeito poderia mandar assinaturas
aleatorias e derrubar a garantia inteira — e a regra passaria a existir em duas
versoes, uma por versao do app em campo.

⚠️ **E ela NAO contem `id_usuario` nem `de_motivo`.** O usuario de fora porque a
tabela conta **configuracoes quebradas**, e nao pessoas: dois irmaos com o mesmo
celular tem o mesmo problema uma vez, nao duas. O `de_motivo` de fora porque
carrega a mensagem do sistema, que varia entre execucoes — inclui-lo faria a
assinatura mudar sozinha, e a garantia sumiria em silencio.

**O que se perde, e e honesto dizer:** nao se sabe quantos aparelhos
**distintos** sofreram. Mas isso ja era verdade — sem identificador estavel de
aparelho (regra 5, abaixo) nao ha como contar aparelhos distintos de jeito
nenhum. O que se ganha e a pergunta certa passar a ter resposta certa.

═══════════════════════════════════════════════════════════════════════════
POR QUE UMA TABELA NOVA, E NAO O `js_extra` DO LOG DE PARTIDA
═══════════════════════════════════════════════════════════════════════════

Decisao do dono, 25/08/2026:

    "Nao vejo sentido em mandar logs de erros no `js_extra` de outras partidas
     que nao tem nada a ver com isso. Vamos criar esse novo endpoint."

⚠️ A recomendacao anterior era o contrario — aproveitar o `js_extra`, por ser
aditivo e nao pedir migracao. Fica registrada so para nao ser reproposta. O
argumento que a derrubou e bom: **com a trava da T199 ligada, ninguem joga no
Sagaz naquele aparelho**. O aviso viajaria pendurado em partidas de outros
niveis — dado de diagnostico misturado a dado de jogo, e num lugar onde ninguem
o procuraria.

═══════════════════════════════════════════════════════════════════════════
POR QUE O SCHEMA E `log`, E NAO `jogo_damas`
═══════════════════════════════════════════════════════════════════════════

"O motor nativo nao carregou" e problema **do app**, nao do jogo. Hoje so as
damas tem motor nativo; amanha o Pontinhos pode ter (a inferencia TFLite ja e
nativa, e a mesma pergunta — "carregou?" — se aplica a ela). Uma tabela em
`jogo_damas` obrigaria a copiar a estrutura por jogo, que e a armadilha que o
frontend ja pagou caro: *"tela igual em dois jogos e UM widget, nao dois
parecidos"*.

`co_jogo` e **coluna**, nao schema. E por isso que ela existe — e por isso ela e
`VARCHAR(30)`, a mesma largura que `partida.tb001_partida` usa. Nasceu `(20)` e o
dono pegou em 27/08: *"Precisa manter um padrao de dados nos campos
correlatos."* Larguras diferentes para a mesma coisa sao a primeira rachadura de
um `JOIN` que um dia vai truncar.

═══════════════════════════════════════════════════════════════════════════
AS CINCO REGRAS QUE O ENDPOINT RESPEITA — cada uma um modo de falha real
═══════════════════════════════════════════════════════════════════════════

1. **Deduplicar em DOIS lugares, e nao em um.** No **app**, para nao gastar rede
   a cada abertura; no **servidor**, com `co_assinatura UNIQUE`, para a tabela
   continuar contando configuracoes mesmo quando o dedupe do app for perdido
   (reinstalacao, "limpar dados", envio que falhou). O do app e economia; o do
   servidor e a **garantia**.

2. **Funcionar sem login.** A falha pode ser de convidado — e o convidado e
   justamente quem esta experimentando o app pela primeira vez. Por isso
   `id_usuario` e NULO-avel e **nao tem FK**: uma FK obrigaria login para
   relatar, e o relato mais valioso seria o unico impossivel.

3. **Nunca lancar nem bloquear.** Do lado do app; aqui a consequencia e que o
   endpoint responde `202` a qualquer coisa que ele consiga registrar, e nunca
   devolve erro que o app precise tratar.

4. **Tolerar servidor antigo.** `404`/`501` e silencio, pela diretriz de
   versionamento da API: uma build do app mais nova que o backend nao pode
   quebrar. Consequencia aqui: nada nesta tabela pode ser obrigatorio para o
   resto funcionar.

5. **Nada de identificador estavel de aparelho.** Nao ha IMEI, nao ha
   `androidId`, nao ha `identifierForVendor`. **Modelo e ABI bastam** para saber
   onde consertar, e nao permitem seguir uma pessoa. Diagnostico nao precisa de
   identidade; precisa de padrao.

═══════════════════════════════════════════════════════════════════════════
O MOTIVO E GRAVADO DUAS VEZES, DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

`co_motivo` e a **categoria** (o app classifica antes de mandar) e `de_motivo` e
o **texto cru** que a ponte produziu.

Nao e redundancia. A categoria e o que se agrupa numa consulta ("quantos
aparelhos com `biblioteca_ausente` esta semana?"); o texto cru e o que diz **onde
olhar** quando a categoria nao basta — ele carrega o nome do simbolo que faltou,
o caminho, a mensagem do `dlopen`. Guardar so a categoria perderia o diagnostico;
guardar so o texto tornaria impossivel contar.

⚠️ **`de_motivo` e `TEXT`, e nao `VARCHAR(300)`.** Ele nasceu `(300)` e o dono
perguntou em 27/08 se aquilo comportaria um stacktrace. **Nao comportava** — um
stacktrace de Dart tem alguns milhares de caracteres. No Postgres, `TEXT` e
`VARCHAR(n)` tem o mesmo desempenho e o mesmo armazenamento; o `(n)` so
acrescenta uma verificacao. Tirar o teto custa nada e remove a pergunta.
O corte continua existindo **no app** (2000 caracteres), que e onde ele serve
para alguma coisa: evitar a viagem, e nao a gravacao.

⚠️ **`co_motivo` NAO e uma dimensao (`tb9xx`) — e um VARCHAR com CHECK.** Mesma
escolha, e pelo mesmo motivo, do `co_motor_busca` na `0013`: sao poucos valores
fechados, e uma dimensao custaria um JOIN em toda consulta para nao entregar
nada. Se um dia a lista crescer ou passar a precisar de rotulo traduzido, o CHECK
vira dimensao — e ai o JOIN se paga.

═══════════════════════════════════════════════════════════════════════════
AS TRES VERSOES, E ELAS SAO MESMO TRES
═══════════════════════════════════════════════════════════════════════════

O dono perguntou em 27/08: *"Tem `co_motor`. E a versao do motor? E isso mesmo?
O codigo do App tem uma versao esperada e podemos ter outra compilada no App?"*

Sim, e sao **tres numeros diferentes**, que se movem separados:

| coluna | o que e | exemplo |
|---|---|---|
| `co_versao_motor` | o motor **logico**, em Dart — a mesma string do `co_versao_motor` do log de partida | `dart_1.3.0` |
| `co_versao_binario_esperada` | o **minimo** que aquele codigo Dart exige do binario | `0.3.0` |
| `co_versao_binario_encontrada` | o que o binario **declarou**, ou nulo se ele nem carregou | `0.2.0` |

⚠️ **E o caso que o dono descreveu e real e ja aconteceu.** O `.so`/`.a` e
compilado por script a parte (`build_ios.sh`, `build_android.sh`), entao da para
construir o app com **Dart novo e binario velho** — foi exatamente o estado do
iOS entre 26 e 27/08/2026, com o codigo em 1.3.0 e o `.a` ainda em 0.2.0. Sem as
tres colunas, esse estado apareceria como "motor indisponivel" sem dizer que a
causa era um binario desatualizado, que e a unica informacao que resolve.

⚠️ **`co_versao_motor` e derivavel de `co_versao_app`** — as duas sobem juntas no
mesmo commit. Grava-se assim mesmo: derivar exigiria manter uma tabela de-para
app→motor a mao, e essa tabela e exatamente o tipo de coisa que envelhece calada.

═══════════════════════════════════════════════════════════════════════════
ADITIVA, COMO MANDA A REGRA DESDE A 0011
═══════════════════════════════════════════════════════════════════════════

`CREATE SCHEMA IF NOT EXISTS` (o `log` ja existe desde a 0005), `CREATE TABLE`
nova, `CREATE INDEX` e `CREATE VIEW` nova. **Nenhum `DROP`, nenhum `ALTER` em
coisa existente, nenhuma linha tocada.** Ha usuarios reais em `prd` desde
04/08/2026, e `tests/unitarios/test_migracoes_aditivas.py` recusa qualquer
`DROP` no `upgrade()`.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0016_diagnostico_motor_nativo"
down_revision: Union[str, None] = "0015_motivo_base_finais_damas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # O schema `log` ja existe desde a 0005. O `IF NOT EXISTS` esta aqui para a
    # migracao ser reexecutavel e para nao depender da ordem — nao para criar.
    op.execute("CREATE SCHEMA IF NOT EXISTS log")

    op.execute(
        """
        CREATE TABLE log.tb002_diagnostico_motor_nativo (
            id_diagnostico       UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            -- ⚠️ A CHAVE DA GARANTIA. SHA-256 (64 hex) das colunas que definem
            -- a CONFIGURACAO, calculado no servidor. O `UNIQUE` e o que faz um
            -- telefone em laco incrementar `qt_ocorrencias` em vez de criar
            -- linha. Ver o cabecalho.
            co_assinatura        CHAR(64)     NOT NULL UNIQUE,

            -- QUEM (opcional, e sem FK — ver a regra 2 do cabecalho).
            -- NULL = convidado, ou pessoa deslogada. Nao e falta de dado: e o
            -- caso mais provavel de todos.
            -- ⚠️ Guarda o ULTIMO que relatou, e nao entra na assinatura: a
            -- tabela conta configuracoes quebradas, nao pessoas.
            id_usuario           UUID,

            -- O QUE FALHOU
            -- ⚠️ `VARCHAR(30)` como em `partida.tb001_partida.co_jogo`. Larguras
            -- diferentes para a mesma coisa sao a primeira rachadura de um JOIN
            -- que um dia trunca.
            co_jogo              VARCHAR(30)  NOT NULL,
            co_motor             VARCHAR(10)  NOT NULL,

            -- POR QUE — a categoria para contar, o texto cru para investigar.
            -- ⚠️ `TEXT` e nao `VARCHAR(300)`: um stacktrace nao cabia em 300.
            co_motivo            VARCHAR(30)  NOT NULL,
            de_motivo            TEXT,

            -- AS TRES VERSOES — ver a secao propria no cabecalho.
            -- `co_versao_motor` e o motor LOGICO (Dart), na mesma forma do log
            -- de partida. As outras duas sao do BINARIO, e a "encontrada" e nula
            -- no caso mais comum: o binario nao carregou, entao nao houve a quem
            -- perguntar. E essa a diferenca entre "faltou o arquivo" e "o
            -- arquivo e velho".
            co_versao_motor               VARCHAR(40),
            co_versao_binario_esperada    VARCHAR(20),
            co_versao_binario_encontrada  VARCHAR(20),

            -- ONDE — o suficiente para consertar, e nada que siga uma pessoa
            -- (regra 5). Modelo e ABI dizem qual build refazer.
            co_plataforma        VARCHAR(10)  NOT NULL,
            co_versao_so         VARCHAR(40),
            no_modelo_aparelho   VARCHAR(80),
            co_abi               VARCHAR(20),

            -- QUAL BUILD DO APP — sem isto, "quantas configuracoes quebradas"
            -- nao se separa de "quantas quebradas que ainda nao atualizaram".
            co_versao_app        VARCHAR(20),
            co_flavor            VARCHAR(10),
            co_modo_build        VARCHAR(10),

            -- QUANTAS VEZES, E ENTRE QUANDO E QUANDO.
            -- ⚠️ `dh_ultimo` e o que responde "isto ainda esta acontecendo?".
            -- Sem ele, uma configuracao consertada ha meses continuaria parecendo
            -- ativa, porque a linha nao sai da tabela — nada e apagado aqui.
            -- Os tres usam `now()` do SERVIDOR, e nao o relogio do aparelho: um
            -- telefone com a data errada envenenaria toda serie temporal.
            qt_ocorrencias       INTEGER      NOT NULL DEFAULT 1,
            dh_primeiro          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            dh_ultimo            TIMESTAMPTZ  NOT NULL DEFAULT now(),

            -- Os CHECKs sao a versao barata da dimensao (ver o cabecalho).
            -- ⚠️ `plataforma_sem_motor` NAO e defeito: e o que a VM do
            -- `flutter test` e qualquer desktop respondem, e existe na lista
            -- para nao virar `falha_desconhecida` e poluir a contagem do que
            -- importa.
            CONSTRAINT ck_diag_motor CHECK (co_motor IN ('rust', 'tflite')),
            CONSTRAINT ck_diag_plataforma
                CHECK (co_plataforma IN ('android', 'ios', 'outra')),
            CONSTRAINT ck_diag_motivo CHECK (co_motivo IN (
                'biblioteca_ausente',
                'simbolo_ausente',
                'plataforma_sem_motor',
                'versao_insuficiente',
                'falha_desconhecida'
            )),
            CONSTRAINT ck_diag_flavor
                CHECK (co_flavor IS NULL OR co_flavor IN ('des', 'prd')),
            CONSTRAINT ck_diag_modo_build
                CHECK (co_modo_build IS NULL
                       OR co_modo_build IN ('debug', 'profile', 'release')),
            -- Um contador que zerasse ou ficasse negativo seria um defeito
            -- silencioso na conta do UPSERT.
            CONSTRAINT ck_diag_ocorrencias CHECK (qt_ocorrencias >= 1)
        )
        """
    )

    # ── Os indices, e cada um responde a uma pergunta que se vai fazer ───────
    #
    # ⚠️ O `UNIQUE` de `co_assinatura` ja cria o indice de que o UPSERT precisa —
    # nao ha um `CREATE INDEX` para ele aqui, e nao e esquecimento.
    #
    # 1. "isto ainda esta acontecendo?" — a categoria pela ULTIMA ocorrencia. Com
    #    uma linha por configuracao, `dh_registro` nao existe mais: quem responde
    #    "esta piorando?" e o `dh_ultimo`.
    op.execute(
        "CREATE INDEX ix_diag_motor_nativo_motivo_data "
        "ON log.tb002_diagnostico_motor_nativo (co_motivo, dh_ultimo)"
    )
    # 2. "quais APARELHOS?" — plataforma + ABI e o par que diz qual build
    #    refazer. Sem ele, achar "todos os armeabi-v7a" e varredura completa.
    op.execute(
        "CREATE INDEX ix_diag_motor_nativo_aparelho "
        "ON log.tb002_diagnostico_motor_nativo (co_plataforma, co_abi)"
    )
    # 3. "a versao nova consertou?" — sem isto nao se compara antes e depois de
    #    um envio a loja, que e a unica forma de saber se o conserto funcionou.
    op.execute(
        "CREATE INDEX ix_diag_motor_nativo_versao_app "
        "ON log.tb002_diagnostico_motor_nativo (co_versao_app, dh_ultimo)"
    )

    # Convencao do projeto: servicos LEEM pela VIEW e ESCREVEM na tabela.
    #
    # ⚠️ `SELECT *` aqui e seguro **porque a view e nova e nao ha nada a
    # preservar**, mas ele carrega a armadilha que a 0013 documentou: o Postgres
    # expande o `*` na criacao e a view nao enxerga coluna acrescentada depois.
    # Quem vier acrescentar coluna a esta tabela tem de refazer a view no mesmo
    # `upgrade()`, listando as colunas explicitamente e pondo a nova no FIM —
    # e a 0013 e o molde de como fazer isso sem `DROP`.
    op.execute(
        "CREATE VIEW log.vw002_diagnostico_motor_nativo AS "
        "SELECT * FROM log.tb002_diagnostico_motor_nativo"
    )

    op.execute(
        """
        COMMENT ON TABLE log.tb002_diagnostico_motor_nativo IS
        'Uma linha por CONFIGURACAO em que o motor nativo nao carregou - nao uma '
        'por relato. `co_assinatura` e UNIQUE e o endpoint faz UPSERT, entao um '
        'aparelho que relate mil vezes incrementa `qt_ocorrencias` sem criar '
        'linha. Sem identificador estavel de aparelho, de proposito: conta '
        'configuracoes quebradas, nao pessoas.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN log.tb002_diagnostico_motor_nativo.co_assinatura IS
        'SHA-256 das colunas que definem a configuracao (jogo, motor, motivo, '
        'plataforma, SO, modelo, ABI, versao do app, versao do binario '
        'encontrada, flavor, modo de build). Calculado no SERVIDOR: vindo do app, '
        'uma build com defeito poderia mandar assinaturas aleatorias e derrubar a '
        'garantia. NAO inclui id_usuario nem de_motivo.'
        """
    )


def downgrade() -> None:
    # ⚠️ `DROP` aqui e legitimo: o `downgrade()` nunca roda em producao (existe
    # para o ambiente local) e o cadeado de migracao aditiva o ignora de
    # proposito. No `upgrade()` seria proibido — ver o cabecalho.
    #
    # ⚠️ O schema `log` NAO sai: ele e da 0005 e a `tb001` vive nele.
    op.execute("DROP VIEW IF EXISTS log.vw002_diagnostico_motor_nativo")
    op.execute("DROP TABLE IF EXISTS log.tb002_diagnostico_motor_nativo CASCADE")
