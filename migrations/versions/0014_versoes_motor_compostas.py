"""`co_versao_motor` passa a carregar as DUAS versoes: `dart_1.1.0|rust_0.2.0`.

═══════════════════════════════════════════════════════════════════════════
O PROBLEMA
═══════════════════════════════════════════════════════════════════════════

Desde 26/08/2026 os lances de damas podem ser escolhidos por **dois motores
diferentes**: o Dart, que roda em qualquer aparelho, e o Rust nativo, que roda
onde o binario existe. `jogo_damas.tb002_jogada.co_motor_busca` ja diz **qual**
motor escolheu cada lance.

O que ninguem gravava era a **versao do motor nativo**. `co_versao_motor` dizia
`1.1.0` — a versao do motor **Dart** —, e a partida do dia 25/08 no emulador foi
jogada inteira pelo Rust **0.2.0**, sem que uma linha do banco registrasse esse
numero.

Isso derruba exatamente a garantia pela qual a extensao de partida existe: um
replay rodado com um motor diferente do original reconstroi uma partida que
**nunca aconteceu**, e o dado nao denuncia (RF-DAM-115g). Com dois motores em
campo, uma versao so nao carimba mais a partida.

═══════════════════════════════════════════════════════════════════════════
A FORMA, E POR QUE COMPOR EM VEZ DE ACRESCENTAR COLUNA
═══════════════════════════════════════════════════════════════════════════

    co_versao_motor = 'dart_1.1.0|rust_0.2.0'   binario nativo presente
    co_versao_motor = 'dart_1.1.0'              binario nativo ausente

Decomper e um `split_part(co_versao_motor, '|', 1|2)`, e cada pedaco e
`motor_versao`.

A alternativa era uma coluna nova (`co_versao_motor_nativo`), que seria uma
migracao aditiva pura e nao exigiria nada do que vem abaixo. **O dono escolheu
compor**, e a razao e boa: toda consulta ja escrita le `co_versao_motor`, e
consulta que le uma coluna e nao sabe da outra **continua mentindo em silencio**
— que e o modo de falha que este projeto ja pagou caro varias vezes. Compondo,
quem le a coluna de sempre recebe a verdade inteira sem mudar uma linha.

(!) `VARCHAR(20)` nao cabe: `dart_1.1.0|rust_0.2.0` tem **21** caracteres, e com
versoes de dois digitos passa de 23. Dai o `ALTER COLUMN` abaixo.

═══════════════════════════════════════════════════════════════════════════
(!) POR QUE ESTA MIGRACAO TEM UM `DROP VIEW` NO `upgrade()`
═══════════════════════════════════════════════════════════════════════════

Porque o Postgres nao deixa fazer de outro jeito. Medido em 25/08/2026, numa
transacao revertida contra o DES:

    ALTER TABLE t ALTER COLUMN c TYPE VARCHAR(60)
    -> ERROR: cannot alter type of a column used by a view or rule
       DETAIL: rule _RETURN on view v depends on column "c"

Vale mesmo **alargando** um `varchar`, e mesmo com a view sendo um `SELECT *`.
Nao ha `CREATE OR REPLACE` que resolva: o tipo da coluna esta congelado na
arvore da view, e a unica saida e derrubar a view, alterar, e recria-la.

**Por que isso e seguro, ao contrario do que a regra geral pressupoe:**

  · uma VIEW nao guarda dado nenhum. Derruba-la e recria-la nao perde uma
    linha — e o que se perderia num `DROP TABLE`, que continua proibido;
  · o DDL do Postgres e **transacional**: os tres comandos abaixo sobem juntos
    ou nao sobem. Nao existe instante em que a view esteja faltando;
  · a view e recriada **com o mesmo corpo** com que a 0012 a criou.

`tests/unitarios/test_migracoes_aditivas.py` foi ajustado para reconhecer esse
caso — e **so** esse: um `DROP VIEW` sem o `CREATE VIEW` correspondente na mesma
migracao continua sendo recusado, e `DROP TABLE`, `DROP COLUMN`, `DROP SCHEMA`,
`DELETE` e `TRUNCATE` continuam proibidos sem excecao. O `ALTER COLUMN ... TYPE`
so passa quando **alarga**; estreitar continua recusado, porque estreitar perde
dado.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTA MIGRACAO **NAO** FAZ, DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

Ela **nao** prefixa com `dart_` as partidas ja gravadas (`1.0.0`, `1.0.3`,
`1.1.0`). A tentacao era um `UPDATE`, e a conta nao fecha:

  · em `prd` o `UPDATE` seria um no-op — o schema `jogo_damas` **ainda nao tem
    uma partida**, porque as damas nao foram publicadas;
  · em `des` ele arrumaria ~25 linhas, **todas de teste**;
  · e o preco seria por `UPDATE` na lista de comandos permitidos do cadeado. Um
    `UPDATE` mal escrito destroi dado tao bem quanto um `DELETE`, e abrir essa
    porta para consertar 25 linhas de teste seria um mau negocio.

Quem quiser arrumar o `des` roda a mao — esta em
`ferramentas/consultas_sql/damas_prefixar_versao_antiga_des.sql`.

(!) **Nao ha app velho gravando damas em campo.** A versao publicada (1.1.0+8)
tem Pontinhos e Velha; as damas nascem ja com o formato novo. Mesmo assim o
ingestor normaliza o que chegar sem prefixo
(`api/sincronizacao/repositorio.py`), para que a invariante *"toda linha e
`dart_X` ou `dart_X|rust_Y`"* valha sem depender de qual build sincronizou.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0014_versoes_motor_compostas"
down_revision: Union[str, None] = "0013_motor_e_lance_unico_damas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. A view sai de cima da coluna ─────────────────────────────────────
    #
    # (!) Este e o unico `DROP` do `upgrade()` de toda migracao a partir da
    # 0011, e ele so existe porque o Postgres nao oferece alternativa. Ver o
    # cabecalho: view nao guarda dado, e o DDL e transacional.
    op.execute("DROP VIEW jogo_damas.vw001_partida")

    # ── 2. A coluna cresce ──────────────────────────────────────────────────
    #
    # 60, e nao 21: `dart_10.10.10|rust_10.10.10` ja pede 27, e um terceiro
    # motor um dia pediria mais. Em Postgres `varchar(n)` e de tamanho variavel
    # — o `n` e um limite, nao uma reserva —, entao um teto folgado nao custa um
    # byte a mais no disco. Ja um teto apertado custa uma migracao.
    op.execute(
        """
        ALTER TABLE jogo_damas.tb001_partida
            ALTER COLUMN co_versao_motor TYPE VARCHAR(60)
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN jogo_damas.tb001_partida.co_versao_motor IS
        'As versoes dos motores que a partida tinha disponiveis, compostas: '
        '"dart_1.1.0|rust_0.2.0", ou "dart_1.1.0" quando o aparelho nao tinha '
        'o binario nativo. Decompoe-se por split_part no separador barra '
        'vertical, e cada pedaco e motor_versao. QUAL motor escolheu cada '
        'lance esta em jogo_damas.tb002_jogada.co_motor_busca, lance a lance.'
        """
    )

    # ── 3. A view volta, com o mesmo corpo da 0012 ──────────────────────────
    #
    # `SELECT *` era o corpo original, e ele e mantido de proposito: esta view
    # nao tem JOIN nenhum, entao a armadilha do `j.*` que a 0013 desfez em
    # `vw002_jogada` nao existe aqui. Trocar por lista explicita agora seria uma
    # mudanca a mais numa migracao que ja mexe onde nao se costuma mexer.
    op.execute(
        "CREATE VIEW jogo_damas.vw001_partida AS "
        "SELECT * FROM jogo_damas.tb001_partida"
    )


def downgrade() -> None:
    """Volta a `VARCHAR(20)`. **So para o ambiente local.**

    (!) O caminho de volta **perde dado**, e nao ha como nao perder: uma string
    de 21 caracteres nao entra numa coluna de 20. Por isso o `UPDATE` de baixo
    corta a parte do Rust ANTES de estreitar — sem ele, o `ALTER` falharia com
    `value too long`, e falhar num `downgrade` deixa o schema no meio do
    caminho.

    O cadeado de migracao aditiva ignora o `downgrade()` de proposito: ele
    existe para o ambiente local e nunca roda em producao.
    """
    op.execute("DROP VIEW jogo_damas.vw001_partida")

    # Fica so a parte do Dart, e sem o prefixo — a forma que a 0013 conhecia.
    op.execute(
        """
        UPDATE jogo_damas.tb001_partida
           SET co_versao_motor =
               replace(split_part(co_versao_motor, '|', 1), 'dart_', '')
        """
    )
    op.execute(
        """
        ALTER TABLE jogo_damas.tb001_partida
            ALTER COLUMN co_versao_motor TYPE VARCHAR(20)
        """
    )
    op.execute(
        "CREATE VIEW jogo_damas.vw001_partida AS "
        "SELECT * FROM jogo_damas.tb001_partida"
    )
