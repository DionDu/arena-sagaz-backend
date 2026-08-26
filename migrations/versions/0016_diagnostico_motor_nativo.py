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
ninguem que escondeu — e a queda para o motor Dart continua sendo silenciosa,
que era o defeito original.

⚠️ **A queda em si e uma virtude, e nao se mexe nela.** E o que faz o app rodar
em qualquer aparelho. O que se conserta aqui e o **silencio**.

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

`co_jogo` e **coluna**, nao schema. E por isso que ela existe.

═══════════════════════════════════════════════════════════════════════════
AS CINCO REGRAS QUE O ENDPOINT RESPEITA — cada uma um modo de falha real
═══════════════════════════════════════════════════════════════════════════

1. **Deduplicar no APP.** Um aparelho cujo `.so` nunca carrega relataria a cada
   abertura, para sempre. O app guarda a assinatura do que ja relatou
   (jogo + motivo + versao do app + versao do binario) e so volta a falar quando
   a assinatura muda — o que e exatamente quando ha noticia nova.
   ⚠️ **Isto e o que dimensiona a tabela.** Sem dedupe, ela cresceria com o
   numero de ABERTURAS; com dedupe, cresce com o numero de aparelhos-versao
   quebrados, que e o numero que se quer conhecer.

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

⚠️ **`co_motivo` NAO e uma dimensao (`tb9xx`) — e um VARCHAR com CHECK.** Mesma
escolha, e pelo mesmo motivo, do `co_motor_busca` na `0013`: sao poucos valores
fechados, e uma dimensao custaria um JOIN em toda consulta para nao entregar
nada. Se um dia a lista crescer ou passar a precisar de rotulo traduzido, o CHECK
vira dimensao — e ai o JOIN se paga.

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

            -- QUEM (opcional, e sem FK — ver a regra 2 do cabecalho).
            -- NULL = convidado, ou pessoa deslogada. Nao e falta de dado: e o
            -- caso mais provavel de todos.
            id_usuario           UUID,

            -- O QUE FALHOU
            -- `co_jogo` e coluna e nao schema: a tabela serve a qualquer jogo
            -- que venha a ter binario nativo (ver o cabecalho).
            co_jogo              VARCHAR(20)  NOT NULL,
            co_motor             VARCHAR(10)  NOT NULL,

            -- POR QUE — a categoria para contar, o texto cru para investigar.
            co_motivo            VARCHAR(30)  NOT NULL,
            de_motivo            VARCHAR(300),

            -- AS DUAS VERSOES DO BINARIO.
            -- `co_versao_binario_esperada` e o minimo que o app exige
            -- (`versaoMinimaDoBinarioParaAQualidade`).
            -- `co_versao_binario_encontrada` e o que o binario declarou — e ela
            -- e NULA no caso mais comum, que e o binario nao ter carregado de
            -- jeito nenhum. Nulo aqui significa "nao havia o que perguntar", e
            -- e essa a diferenca entre "faltou o arquivo" e "o arquivo e velho".
            co_versao_binario_esperada    VARCHAR(20),
            co_versao_binario_encontrada  VARCHAR(20),

            -- ONDE — o suficiente para consertar, e nada que siga uma pessoa
            -- (regra 5). Modelo e ABI dizem qual build refazer.
            co_plataforma        VARCHAR(10)  NOT NULL,
            co_versao_so         VARCHAR(40),
            no_modelo_aparelho   VARCHAR(80),
            co_abi               VARCHAR(20),

            -- QUAL BUILD DO APP — sem isto, "quantos aparelhos quebrados" nao
            -- se separa de "quantos aparelhos quebrados que ainda nao
            -- atualizaram".
            co_versao_app        VARCHAR(20),
            co_flavor            VARCHAR(10),
            co_modo_build        VARCHAR(10),

            -- QUANDO. `now()` do SERVIDOR, e nao o relogio do aparelho: um
            -- telefone com a data errada envenenaria toda serie temporal, e
            -- aqui nao ha nada que dependa da hora local de ninguem.
            dh_registro          TIMESTAMPTZ  NOT NULL DEFAULT now(),

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
                       OR co_modo_build IN ('debug', 'profile', 'release'))
        )
        """
    )

    # ── Os indices, e cada um responde a uma pergunta que se vai fazer ───────
    #
    # 1. "isto esta piorando?" — a categoria ao longo do tempo. E a consulta que
    #    se roda depois de publicar uma versao.
    op.execute(
        "CREATE INDEX ix_diag_motor_nativo_motivo_data "
        "ON log.tb002_diagnostico_motor_nativo (co_motivo, dh_registro)"
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
        "ON log.tb002_diagnostico_motor_nativo (co_versao_app, dh_registro)"
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
        'Um relato por aparelho-versao em que o motor NATIVO nao carregou. O app '
        'deduplica antes de enviar: a mesma assinatura (jogo + motivo + versao do '
        'app + versao do binario) so e relatada uma vez. Sem identificador estavel '
        'de aparelho, de proposito.'
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
