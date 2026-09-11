"""`desafio.tb904_motor`: decifrar o `co_versao_motor` (RF-DES-164, T049e).

Revision ID: 0022_motor_decifravel
Revises: 0021_desafio_impedido
Create Date: 2026-09-11

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA TABELA EXISTE — decisao do dono, 10/09/2026 (§8f)
═══════════════════════════════════════════════════════════════════════════

`desafio.tb001_desafio.co_versao_motor` guarda `damas-py-2f8e15cd`. Os oito
digitos sao o comeco de um SHA-256 da lista de hashes dos arquivos do motor
dentro do espelho do laboratorio — ⛔ **eles nao se invertem, e nada no banco diz
de que arquivos sairam.**

⚠️ **A comparacao com a irma `tb903_perfil_dificuldade` E o argumento**, e foi
ela que o dono usou. O perfil e decifravel **sem o Git**: `js_perfil` traz os
numeros, `co_arquivo` e `co_sha256` dizem de onde vieram. O motor — que decide o
lance, produz o gabarito e calibra a regua — nao e decifravel de jeito nenhum.

⚠️ **E ha uma fragilidade pior que a inconveniencia.** Enquanto a unica forma de
decifrar for *"refazer a conta"*, a decifracao depende de a formula continuar a
mesma: no dia em que alguem mudar a funcao que deriva o resumo, **toda string
antiga fica irresolvivel para sempre**. Com o `co_sha256` do manifesto e a lista
de arquivos na propria linha, decifrar deixa de depender da formula de hoje.

═══════════════════════════════════════════════════════════════════════════
⚠️ O FORMATO NAO E LIVRE: ELE FECHA O PAR DE DIAGNOSTICO
═══════════════════════════════════════════════════════════════════════════

Existem duas metades da mesma informacao, e ate hoje elas nao se cruzavam:

    o aparelho reporta  →  `dart_1.4.0|rust_0.4.0`  (`partida.tb001_partida` e
                                                     `tb007_desafio_impedido`)
    o servidor guarda   →  `damas-py-2f8e15cd`      (`desafio.tb001_desafio`)

Uma e versao semantica de dois motores; a outra e um hash de um terceiro. A
pergunta *"por que este desafio nao coube no aparelho desta pessoa?"* precisa das
duas, e ficava sem resposta exatamente quando alguem a fazia.

Por isso `js_motores` tem a **mesma forma de lista** de
`desafio_dia.tb007_desafio_impedido` — `[{co_jogo, co_motor, co_versao}]` sob a
chave `motores`, com `"versao": 1`:

    {
      "versao": 1,
      "motores": [
        {"co_jogo": "damas", "co_motor": "python",   "co_versao": "damas-py-2f8e15cd"},
        {"co_jogo": "damas", "co_motor": "contrato", "co_versao": "1.0.0"}
      ]
    }

As duas colunas se abrem com o mesmo `jsonb_to_recordset` e se comparam sem
tradutor no meio. ⚠️ **A lista, e nao um dicionario aninhado por jogo** — a
mesma razao escrita na `0021`: o dicionario poe o nome do jogo na posicao de
chave, e toda consulta passa a ter de saber os jogos de antemao.

⚠️ **`js_arquivos` e a lista que produziu o resumo**, no mesmo desenho
(`{"versao": 1, "arquivos": [{caminho, sha256}]}`). E ela que permite refazer a
conta — e um cadeado em `tests/unitarios/test_motor_decifravel.py` faz isso: parte
da linha, recalcula, e exige chegar de volta ao `co_versao_motor`.

⛔ **Sem `CHECK` de vocabulario sobre `co_motor`**, pelo mesmo motivo da `0021`:
jogo novo traz motor novo, e recusar a linha perderia o diagnostico justamente
quando ele e mais interessante. Os `CHECK` daqui sao **estruturais** — exigem que
as duas listas sejam listas.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS DUAS `fk002_motor`, E POR QUE ELAS SAO `NOT VALID`
═══════════════════════════════════════════════════════════════════════════

**Por que ha FK.** *"Um catalogo que ninguem referencia nao e catalogo"* — o
argumento e do dono, de 08/09/2026, quando ele desfez o `js_feitos_medidos` em
favor de `tb003_feito_desafio`. Uma dimensao do motor sem FK seria uma tabela que
alguem *pode* consultar, e que nada obriga a existir; a `fk002_motor` e o que
transforma *"o job deveria gravar"* em *"o banco recusa se nao gravar"*.

⚠️ **E ela repete a licao da `fk001_perfil`:** quem grava a dimensao e o **job**,
no comeco da execucao, e nunca a migracao. Se ela gravasse, estaria publicando
por `INSERT` um fato sobre arquivos que ela nao tem como conferir.

**Por que `NOT VALID`.** A clausula diz ao Postgres: *"confira todas as linhas
NOVAS, e nao revarra as antigas"*. Ela e necessaria porque o `des` ja tem
desafios publicados, gerados **antes** de esta dimensao existir — e ⛔ a unica
forma de valida-los agora seria inventar para eles uma linha de dimensao, com um
`co_sha256` de manifesto que ninguem conferiu. ⚠️ **Isso e o oposto do que a
tabela existe para fazer:** ela nasceu para que a linha do banco nao precise de
fe, e a primeira coisa gravada nela seria um ato de fe.

⚠️ **O que `NOT VALID` NAO afrouxa:** toda linha inserida ou atualizada a partir
daqui e conferida normalmente. E no `prd` a diferenca nem existe — la a tabela
nasce vazia (o primeiro `upgrade` do schema `desafio` ainda nao aconteceu), e a
primeira execucao do job grava a dimensao antes do primeiro desafio.

⚠️ **A reprise e o caso a vigiar, e ele tem aviso proprio no job.** Uma reprise
copia o `co_versao_motor` da origem — se a origem for anterior a esta migracao, o
`INSERT` da copia bate na FK, e isso aconteceria no **pior dia operacional**
(fila de aprovados vazia). Por isso `job/__main__.py` pergunta, no comeco de cada
execucao, se ha versao publicada fora da dimensao, e **avisa alto** em vez de
esperar a falha. ⛔ Aviso, e nao codigo de saida 1: sinal que dispara sempre
ninguem le — a mesma licao de `fora_da_banda`.

═══════════════════════════════════════════════════════════════════════════
⚠️ MIGRACAO NOVA, E NAO EDICAO DA 0018
═══════════════════════════════════════════════════════════════════════════

A tabela pertence ao schema `desafio`, criado pela `0018` — e a regra §8b
(*nao se remenda: dropa e recria*) sugeriria escreve-la la dentro. ⛔ **O dono
decidiu o contrario em 10/09/2026:** *"Nao quero que voce modifique migracao ja
aplicada como a 0019. Crie outra."* A `0021` ja seguiu esta regra.

E nao ha contradicao com a §8b: aquela regra e contra **remendar modelagem
defeituosa com `ALTER`**. Aqui nao ha defeito a remendar — e uma tabela **nova**,
mais duas constraints que so acrescentam.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0022_motor_decifravel"
down_revision: Union[str, None] = "0021_desafio_impedido"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria `desafio.tb904_motor`, a VIEW de leitura e as duas FKs."""
    op.execute(
        """
        CREATE TABLE desafio.tb904_motor (
            id_motor         UUID PRIMARY KEY DEFAULT gen_random_uuid(),

            -- O carimbo como ele aparece em tb001_desafio: 'damas-py-2f8e15cd'.
            -- ⚠️ VARCHAR(40) porque e a largura da coluna que ele decifra —
            -- uma dimensao mais estreita que o fato recusaria carimbo valido.
            co_versao_motor  VARCHAR(40)  NOT NULL,
            co_jogo          VARCHAR(30)  NOT NULL,

            -- Os motores do SERVIDOR, na mesma forma de lista da tb007 do
            -- aplicativo. Ver o cabecalho: e isso que fecha o par.
            js_motores       JSONB        NOT NULL,

            -- O SHA-256 do MANIFESTO_HASHES.json que declarava os arquivos.
            -- ⚠️ E ele que liberta a decifracao da formula de hoje.
            co_sha256        CHAR(64)     NOT NULL,

            -- Os arquivos que entraram no resumo, com o hash de cada um.
            js_arquivos      JSONB        NOT NULL,

            dh_vigencia      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            -- ⚠️ O par (versao, jogo) e a identidade: um mesmo espelho produz um
            -- resumo por jogo, e os dois convivem. E o destino das FKs abaixo.
            CONSTRAINT un001_motor    UNIQUE (co_versao_motor, co_jogo),

            -- Guardas ESTRUTURAIS, e nao de vocabulario: exigem que as duas
            -- listas sejam listas. ⛔ Nada sobre QUAIS motores existem — jogo
            -- novo traz motor novo, e recusar perderia o diagnostico.
            CONSTRAINT ck001_motores  CHECK (jsonb_typeof(js_motores -> 'motores')
                                             = 'array'),
            CONSTRAINT ck002_arquivos CHECK (jsonb_typeof(js_arquivos -> 'arquivos')
                                             = 'array')
        )
        """
    )

    # ⚠️ Colunas nomeadas UMA A UMA, e nao `SELECT *`: uma VIEW criada com `*`
    # NAO enxerga coluna acrescentada depois (licao da `0017`).
    op.execute(
        """
        CREATE VIEW desafio.vw904_motor AS
        SELECT id_motor, co_versao_motor, co_jogo, js_motores,
               co_sha256, js_arquivos, dh_vigencia
          FROM desafio.tb904_motor
        """
    )

    # ── As duas FKs, `NOT VALID` — o porque esta no cabecalho ────────────────
    op.execute(
        """
        ALTER TABLE desafio.tb001_desafio
            ADD CONSTRAINT fk002_motor FOREIGN KEY (co_versao_motor, co_jogo)
            REFERENCES desafio.tb904_motor (co_versao_motor, co_jogo)
            NOT VALID
        """
    )
    op.execute(
        """
        ALTER TABLE desafio.tb002_medicao_regua
            ADD CONSTRAINT fk002_motor FOREIGN KEY (co_versao_motor, co_jogo)
            REFERENCES desafio.tb904_motor (co_versao_motor, co_jogo)
            NOT VALID
        """
    )

    op.execute(
        "COMMENT ON TABLE desafio.tb904_motor IS "
        "'Decifra o co_versao_motor: de que arquivos, com que hashes e sob que "
        "manifesto saiu o resumo de 8 digitos. Escrita SO pelo job, no comeco de "
        "cada execucao, como a tb903_perfil_dificuldade (RF-DES-164).'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio.tb904_motor.js_motores IS "
        "'Lista de registros (co_jogo, co_motor, co_versao) sob a chave motores, "
        "com versao do formato — a MESMA forma de tb007_desafio_impedido, para "
        "que o que o servidor rodou e o que o aparelho tinha se comparem com um "
        "jsonb_to_recordset de cada lado.'"
    )
    op.execute(
        "COMMENT ON COLUMN desafio.tb904_motor.js_arquivos IS "
        "'Os arquivos do espelho que entraram no resumo, com o SHA-256 de cada "
        "um. Refazer a conta a partir desta lista devolve o co_versao_motor — e "
        "e isso que torna a decifracao independente da formula de hoje.'"
    )


def downgrade() -> None:
    """Derruba as FKs, a VIEW e a tabela.

    ⚠️ **So para o ambiente local**, como no resto do projeto — o cadeado de
    migracao aditiva ignora o `downgrade()`.
    """
    op.execute(
        "ALTER TABLE desafio.tb002_medicao_regua DROP CONSTRAINT IF EXISTS fk002_motor"
    )
    op.execute(
        "ALTER TABLE desafio.tb001_desafio DROP CONSTRAINT IF EXISTS fk002_motor"
    )
    op.execute("DROP VIEW IF EXISTS desafio.vw904_motor")
    op.execute("DROP TABLE IF EXISTS desafio.tb904_motor CASCADE")
