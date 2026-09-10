"""O dia em que o desafio NAO COUBE no aplicativo da pessoa (RF-DES-024/028).

Revision ID: 0021_desafio_impedido
Revises: 0020_partida_modo_desafio
Create Date: 2026-09-10

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA TABELA EXISTE
═══════════════════════════════════════════════════════════════════════════

RF-DES-024: *"nao podia participar"* quer dizer **uma** coisa — ela abriu o
aplicativo e o desafio do dia exigia versao que ela nao tem. Nesse caso o dia
⛔ **nao conta contra ela**, e quem precisa ser protegida e a **chama**.

⚠️ **E a chama e DERIVADA, nao incrementada.** A correcao de 08/2026 parou de
guardar contador justamente porque a segunda copia da verdade era a origem do
defeito. Entao nao ha como *"somar um dia"*: o que existe e um conjunto de dias,
lido do historico. Esta tabela e mais uma **fonte de dias** para esse conjunto —
`recalcular_chama` passa a unir as partidas concluidas com as linhas daqui.

═══════════════════════════════════════════════════════════════════════════
O NOME — decidido pelo dono em 10/09/2026
═══════════════════════════════════════════════════════════════════════════

O rascunho a chamava `tb007_visita`, e o dono recusou: *"fica parecendo que
registrara a visita de todos os usuarios, mesmo os que jogarao o desafio"*.

Eu propus `tb007_visita_impedida`; ele preferiu **`tb007_desafio_impedido`**, e
o argumento e dele:

    "Como id_desafio e unico e teremos apenas 1 desafio por dia, esse
     dt_dia_local corresponde na pratica a 1 id_desafio que o usuario perdeu.
     Visita impedida me remete ao App ter rejeitado o usuario a abrir a Home."

⚠️ E ele esta certo sobre o que o nome sugere: o que foi impedido nao foi a
pessoa de entrar — foi **o desafio de chegar ate ela**.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE OS MOTORES VAO EM JSON, E NAO EM COLUNAS
═══════════════════════════════════════════════════════════════════════════

O dono pediu que a tabela guardasse *"versao do App, motores do usuario etc,
para sabermos o que o usuario tinha naquele momento contra o que o backend
exigir"*, e observou que **os motores sao varios e por jogo**: as damas tem hoje
`dart_1.4.0|rust_0.4.0`, e um jogo novo pode trazer outro par.

⛔ **A forma composta plana nao escala, e o projeto ja tem a cicatriz.** A coluna
`partida.tb001_partida.co_versao_motor` guarda `dart_X|rust_Y` porque uma partida
e de **um** jogo com **dois** motores conhecidos — e mesmo assim
`_versoes_do_motor()` (em `api/sincronizacao/repositorio.py`) existe so para
impedir que duas formas convivam na mesma coluna, com todo `split_part` tendo de
adivinhar qual esta lendo. Estender aquilo para varios jogos daria
`damas:dart_1.4.0|rust_0.4.0;pontinhos:tflite_2.2.0` — uma mini-linguagem que
ninguem valida, e a mesma armadilha elevada ao quadrado.

⛔ **Uma coluna por motor tambem nao serve:** jogo novo passaria a exigir
migracao, que e exatamente o acoplamento que a decisao *"modalidade e DADO, nao
`enum`"* das damas ensinou a evitar.

✅ **Entao `js_motores JSONB`, com uma LISTA de registros** — e nao um dicionario
aninhado por jogo:

    {
      "versao": 1,
      "motores": [
        {"co_jogo": "damas",     "co_motor": "dart",   "co_versao": "1.4.0"},
        {"co_jogo": "damas",     "co_motor": "rust",   "co_versao": "0.4.0"},
        {"co_jogo": "pontinhos", "co_motor": "tflite", "co_versao": "2.2.0"}
      ]
    }

⚠️ **A lista, e nao o dicionario, porque ela e a mesma forma que uma tabela
filha teria** — `jsonb_to_recordset` a abre em linhas e devolve o relacional de
graca quando a pergunta for agregada (*"quantos barrados tinham rust abaixo de
0.4.0?"*). Um dicionario `{"damas": {"rust": "0.4.0"}}` poe o nome do jogo na
POSICAO DE CHAVE, e toda consulta passa a ter de saber os jogos de antemao.

⚠️ **O `"versao": 1` e obrigatorio**, na mesma convencao de `js_chegada`: e ele
que permite mudar a forma sem adivinhacao.

⛔ **E NAO ha `CHECK` sobre `co_motor`.** E o preco do JSON, e aqui ele e o lado
certo da troca: um aplicativo **mais novo** que este servidor vai reportar motor
que ele nunca ouviu falar, e recusar a linha perderia o diagnostico exatamente
quando ele e mais interessante. O servidor guarda o que veio.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE MIGRACAO NOVA, E NAO EDICAO DA 0019
═══════════════════════════════════════════════════════════════════════════

A tabela e do schema `desafio_dia`, e a regra §8b (*nao se remenda: dropa e
recria*) sugeriria escreve-la dentro da `0019`. ⛔ **O dono decidiu o contrario
em 10/09/2026:** *"Nao quero que voce modifique migracao ja aplicada como a 0019.
Crie outra."*

⚠️ E nao ha contradicao com a §8b: aquela regra e contra **remendar modelagem
defeituosa com `ALTER`**. Aqui nao ha defeito a remendar — e uma tabela **nova**,
aditiva por natureza, que nao toca nenhuma coluna existente.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0021_desafio_impedido"
down_revision: Union[str, None] = "0020_partida_modo_desafio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria `desafio_dia.tb007_desafio_impedido` e a VIEW de leitura."""
    op.execute(
        """
        CREATE TABLE desafio_dia.tb007_desafio_impedido (
            id_desafio_impedido  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            id_usuario           UUID NOT NULL
                REFERENCES conta.tb001_usuario(id_usuario),

            -- ⚠️ O dia do RELOGIO DA PESSOA, e nao o dia UTC. Sem ele, uma
            -- visita as 21h no Brasil cairia no dia SEGUINTE em UTC — que e
            -- literalmente o defeito que a chama ja teve uma vez.
            dt_dia_local         DATE NOT NULL,
            dh_visita            TIMESTAMPTZ NOT NULL,
            nu_offset_minuto     SMALLINT,

            -- ⚠️ ANULAVEL de proposito: quem cai aqui pode nao ter conseguido
            -- nem ler a resposta do desafio (chave desconhecida, versao minima
            -- maior). Exigi-lo faria falhar justamente o caso coberto.
            id_desafio_dia       UUID
                REFERENCES desafio_dia.tb001_desafio_dia(id_desafio_dia),

            co_motivo            VARCHAR(30) NOT NULL,

            -- ⚠️ O VALOR que o aplicativo nao reconheceu (o jogo, a modalidade,
            -- a forma ou a chave de i18n). Sem ele, `co_motivo` diz a
            -- CATEGORIA e nunca QUAL — e a linha prova que alguem foi barrado
            -- sem dizer por que de forma acionavel.
            co_desconhecido      VARCHAR(60),

            -- O par do diagnostico: o que ela TINHA x o que se EXIGIA.
            co_versao_app        VARCHAR(20),
            co_plataforma        VARCHAR(10),
            co_versao_minima_exigida VARCHAR(20),

            -- Os motores do aparelho. Ver o cabecalho: lista, e nao dicionario.
            js_motores           JSONB,

            dh_registro          TIMESTAMPTZ NOT NULL DEFAULT now(),

            -- ⚠️ Torna a rota idempotente DE GRACA: abrir o aplicativo cinco
            -- vezes no mesmo dia grava uma linha.
            CONSTRAINT un001_dia_impedido UNIQUE (id_usuario, dt_dia_local),

            CONSTRAINT ck001_motivo CHECK (co_motivo IN
                ('jogo_desconhecido', 'modalidade_desconhecida',
                 'forma_desconhecida', 'chave_desconhecida',
                 'versao_insuficiente')),

            -- ⚠️ Os TRES valores de `PLATAFORMAS_VALIDAS`, e nao dois.
            -- Um CHECK mais estreito que o cabecalho transforma requisicao
            -- VALIDA em erro de banco — e `web` continua no vocabulario do
            -- `exigir_cabecalhos`, mesmo tendo deixado de ser alvo do produto.
            -- `test_desafio_impedido.py` falha se os dois discordarem.
            CONSTRAINT ck002_plataforma CHECK (co_plataforma IS NULL
                OR co_plataforma IN ('android', 'ios', 'web')),

            -- ⚠️ Guarda ESTRUTURAL, e nao de vocabulario: exige que
            -- `js_motores.motores` seja uma LISTA. Nao diz nada sobre QUAIS
            -- motores existem — e de proposito (ver o cabecalho).
            CONSTRAINT ck003_motores CHECK (js_motores IS NULL
                OR jsonb_typeof(js_motores -> 'motores') = 'array')
        )
        """
    )

    # ⚠️ Indice pela data: a pergunta operacional e *"quem foi barrado nos
    # ultimos dias, e por que?"* — e ela varre por dia, nao por usuario.
    op.execute(
        "CREATE INDEX ix001_impedido_dia "
        "ON desafio_dia.tb007_desafio_impedido (dt_dia_local, co_motivo)"
    )

    # ⚠️ Colunas nomeadas UMA A UMA, e nao `SELECT *`: uma VIEW criada com `*`
    # NAO enxerga coluna adicionada depois (licao da `0017`).
    op.execute(
        """
        CREATE VIEW desafio_dia.vw007_desafio_impedido AS
        SELECT id_desafio_impedido, id_usuario, dt_dia_local, dh_visita,
               nu_offset_minuto, id_desafio_dia, co_motivo, co_desconhecido,
               co_versao_app, co_plataforma, co_versao_minima_exigida,
               js_motores, dh_registro
          FROM desafio_dia.tb007_desafio_impedido
        """
    )

    op.execute(
        "COMMENT ON TABLE desafio_dia.tb007_desafio_impedido IS "
        "'Um dia em que o desafio nao coube na versao do aplicativo da pessoa "
        "(RF-DES-024). Alimenta a chama junto com as partidas concluidas.'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio_dia.tb007_desafio_impedido.js_motores IS "
        "'Lista de registros (co_jogo, co_motor, co_versao) sob a chave "
        "motores, com versao do formato — feita para jsonb_to_recordset. Sem "
        "CHECK de vocabulario: aplicativo mais novo reporta motor que o "
        "servidor nao conhece, e recusar perderia o diagnostico.'"
    )


def downgrade() -> None:
    """Derruba a tabela e a VIEW.

    ⚠️ **So para o ambiente local**, como no resto do projeto — o teste de
    migracao aditiva ignora o `downgrade()`.
    """
    op.execute("DROP VIEW IF EXISTS desafio_dia.vw007_desafio_impedido")
    op.execute(
        "DROP TABLE IF EXISTS desafio_dia.tb007_desafio_impedido CASCADE"
    )
