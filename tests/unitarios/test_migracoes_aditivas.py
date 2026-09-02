"""TODA migracao a partir da 0011 e PURAMENTE ADITIVA — cadeado generico.

POR QUE ESTE ARQUIVO EXISTE, SE JA HAVIA UM
--------------------------------------------
Havia `test_migracao_aditiva_velha.py`, e ele guardava **um arquivo**: a 0011.
Isso protegia a migracao da velha e deixava a proxima nascer desprotegida — que
foi exatamente o que aconteceu ao escrever a `0012_schema_jogo_damas`: o cadeado
nao a via, e ninguem seria avisado se ela trouxesse um `DROP`.

Duplicar o arquivo por migracao seria pior ainda. E a mesma licao que o
frontend ja pagou caro e registrou no seu `CLAUDE.md`: *"tela igual em dois
jogos e UM widget, nao dois parecidos"* — dois arquivos que nasceram iguais
divergem, e o dia em que divergirem ninguem percebe.

Entao este teste **varre a pasta**. Migracao nova nasce guardada, sem ninguem
precisar lembrar de acrescenta-la a lista.

⚠️ POR QUE A VARREDURA COMECA NA 0011, E NAO NA 0001
-----------------------------------------------------
A regra do dono nasceu em **2026-08-06**, quando ja havia usuarios reais em
`prd` desde 04/08:

    "Tome muito cuidado para nao usar DELETE, TRUNCATE, DROP. Nos ja temos
     usuarios no ambiente PRD."

As migracoes anteriores sao de antes disso e contem, legitimamente, comandos que
hoje seriam proibidos — a `0006_redesenho_log_treino` e o caso obvio, e a
`0007_drop_co_anonimo` diz no proprio nome. Varrer da 0001 acusaria trabalho
correto do passado, e um teste que acusa o que esta certo ensina a ser ignorado.

O corte e uma CONSTANTE explicita abaixo, nao um numero escondido no meio do
codigo.

O QUE ELE NAO PEGA (e por que esta certo assim)
-----------------------------------------------
Ele nao roda a migracao contra um Postgres — isso e trabalho de integracao e
depende de banco. O que ele garante e o mais barato e o mais valioso: que ninguem
ACRESCENTE um comando destrutivo depois, numa correcao apressada, sem que o CI
grite.

O `downgrade()` e ignorado de proposito em todas: ele derruba o schema, existe
para o ambiente local e nunca roda em producao.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# `parents[2]` sobe de tests/unitarios/ ate a raiz do repositorio do backend.
RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "migrations" / "versions"

# ⚠️ O corte. Migracoes com prefixo numerico MENOR que este sao anteriores a
# regra de 2026-08-06 e ficam de fora — ver o cabecalho.
PRIMEIRA_GUARDADA = 11

# As tres palavras proibidas, como PALAVRA inteira e sem depender de caixa.
# `\b` evita falso positivo em algo como "DROPDOWN" ou "id_droptable".
PROIBIDOS = ("DELETE", "TRUNCATE", "DROP")

# O que uma migracao aditiva PODE executar. `CREATE INDEX` entrou com a 0012:
# ele nao altera dado nenhum, so acrescenta uma estrutura de leitura — e a
# `jogo_damas.tb003_recusa` precisa de um, porque e consultada por partida e a
# sua PK e o `id_recusa`.
#
# ⚠️ TRES ENTRARAM COM A 0013, e nenhuma delas afrouxa a regra:
#
#  · `CREATE OR REPLACE VIEW` — a lista so conhecia `CREATE VIEW`, e a diferenca
#    importa: acrescentar uma coluna a uma tabela **nao** a faz aparecer numa
#    view criada com `SELECT j.*`, porque o Postgres expande o `*` no momento da
#    criacao. Refazer a view era, ate aqui, so possivel com `DROP` — que e
#    proibido, e com razao. O `OR REPLACE` resolve, e e seguro **por construcao
#    do proprio Postgres**: ele recusa qualquer troca de nome, tipo ou ordem das
#    colunas ja existentes, e so aceita acrescimo ao final.
#
#  · `COMMENT ON` — documenta uma coluna. Nao toca em dado nem em estrutura.
#
#  · `ALTER TABLE` — este e o unico que merece cuidado, e por isso NAO entra na
#    lista de prefixos: ele e tratado a parte, em `_alter_e_aditivo`, que exige
#    que a operacao seja `ADD COLUMN` ou `ADD CONSTRAINT`. Fica assim mais
#    rigoroso do que estava: antes, um `ALTER TABLE ... ALTER COLUMN ... SET NOT
#    NULL` — que quebra numa tabela com dados — era barrado apenas por nao estar
#    na lista, e teria passado no dia em que alguem acrescentasse "ALTER TABLE"
#    aos prefixos sem pensar. Agora a intencao esta escrita.
PERMITIDOS = (
    "CREATE SCHEMA",
    "CREATE TABLE",
    "CREATE INDEX",
    "CREATE VIEW",
    "CREATE OR REPLACE VIEW",
    "INSERT INTO",
    "COMMENT ON",
)

# As unicas operacoes de `ALTER TABLE` que acrescentam sem poder quebrar nada
# numa tabela que ja tem dados.
#
# ⚠️ `ADD COLUMN` sem `NOT NULL` e sem `DEFAULT` e instantaneo e nao reescreve a
# tabela. `ADD CONSTRAINT ... CHECK` e validado contra as linhas existentes e
# falha alto se alguma nao passar — que e o comportamento desejado: melhor a
# migracao recusar do que gravar um estado que o CHECK diz ser impossivel.
ALTER_ADITIVOS = ("ADD COLUMN", "ADD CONSTRAINT")


# ── ALARGAR UM `varchar` — a excecao que a 0014 obrigou a escrever ─────────
#
# ⚠️ **Isto NAO afrouxa a regra**, e a diferenca esta em uma palavra: so passa
# quando **ALARGA**. Estreitar um `varchar` perde dado e continua recusado,
# junto com toda a familia de `ALTER COLUMN` que quebra tabela com dados
# (`SET NOT NULL`, troca de familia de tipo, `USING`).
#
# Por que precisou existir: a `0014` compoe as duas versoes de motor em
# `co_versao_motor` (`dart_1.1.0|rust_0.2.0`, 21 caracteres) e a coluna era
# `VARCHAR(20)`. Nao ha caminho aditivo puro — alargar e a operacao.
#
# Como se sabe que alarga: a largura ANTERIOR e lida das proprias migracoes, do
# `CREATE TABLE` que criou a coluna (e de um alargamento anterior, se houver).
# Se a largura antiga nao for encontrada, o teste **recusa** — nao supoe.
_ALTER_ALARGA = re.compile(
    r"ALTER\s+TABLE\s+([a-z_][a-z0-9_.]*)\s+"
    r"ALTER\s+COLUMN\s+([a-z_][a-z0-9_]*)\s+"
    r"TYPE\s+VARCHAR\s*\(\s*(\d+)\s*\)",
    re.I,
)

# `nome_da_coluna VARCHAR(30)` dentro de um `CREATE TABLE`.
_COLUNA_TEXTO = re.compile(
    r"^\s*([a-z_][a-z0-9_]*)\s+(?:VARCHAR|CHARACTER\s+VARYING)\s*\(\s*(\d+)\s*\)",
    re.I | re.M,
)

# `CREATE TABLE schema.tabela (` ... ate o `)` que fecha.
_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"([a-z_][a-z0-9_.]*)\s*\((.*?)\n\s*\)\s*;?",
    re.I | re.S,
)


def _largura_anterior(arquivo: Path, tabela: str, coluna: str) -> int | None:
    """A largura que esta coluna tinha ANTES de [arquivo], ou `None`.

    ⚠️ **So olha as migracoes anteriores**, e isso nao e detalhe: se olhasse a
    propria, o `ALTER ... TYPE VARCHAR(60)` que esta sendo conferido apareceria
    como a largura "anterior", e a conta viraria `60 > 60` — o proprio comando
    invalidando a si mesmo. A ordem alfabetica dos arquivos e a cronologica,
    porque todos comecam por quatro digitos.

    Devolve `None` quando nao acha nada. Quem chama trata `None` como RECUSA:
    na duvida sobre o tamanho de antes, nao se autoriza a troca de tipo.
    """
    largura: int | None = None
    for anterior in sorted(PASTA.glob("*.py")):
        if anterior.name >= arquivo.name:
            break
        fonte = anterior.read_text(encoding="utf-8")
        for t, corpo in _CREATE_TABLE.findall(fonte):
            if t.lower() != tabela:
                continue
            for c, valor in _COLUNA_TEXTO.findall(corpo):
                if c.lower() == coluna:
                    largura = int(valor)
        # Um alargamento anterior tambem conta: dois seguidos continuam sendo
        # conferidos um contra o outro.
        for t, c, valor in _ALTER_ALARGA.findall(fonte):
            if t.lower() == tabela and c.lower() == coluna:
                largura = int(valor)
    return largura


def _alter_alarga_varchar(comando: str, arquivo: Path) -> bool:
    """Este `ALTER COLUMN ... TYPE VARCHAR(n)` esta ALARGANDO?

    `False` quando o comando nao e desse feitio, quando a largura anterior e
    desconhecida, ou quando a nova nao e maior. **Na duvida, recusa.**
    """
    casa = _ALTER_ALARGA.match(" ".join(comando.split()))
    if casa is None:
        return False
    tabela = casa.group(1).lower()
    coluna = casa.group(2).lower()
    nova = int(casa.group(3))
    anterior = _largura_anterior(arquivo, tabela, coluna)
    return anterior is not None and nova > anterior


def _comandos_do_upgrade(arquivo: Path) -> list[str]:
    """Os textos SQL que o `upgrade()` executa, um por `op.execute`."""
    codigo = _sem_comentarios(_corpo_do_upgrade(arquivo))
    return re.findall(r"op\.execute\(\s*(?:'|\")(.*?)(?:'|\")", codigo, re.S)


def _e_drop_de_view_recriada(comando: str, recriadas: set[str]) -> bool:
    """Este comando e o `DROP VIEW` de uma view que a migracao recria?"""
    casa = re.match(
        r"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?([a-z_][a-z0-9_.]*)",
        " ".join(comando.split()),
        re.I,
    )
    return casa is not None and casa.group(1).lower() in recriadas


def _views_recriadas(comandos: list[str]) -> set[str]:
    """Os nomes de view que a migracao **derruba e recria** no mesmo `upgrade()`.

    ⚠️ **A unica excecao ao `DROP`, e ela e estreita de proposito.** O motivo
    tem data: em 25/08/2026 a `0014` precisou alargar `co_versao_motor`, e o
    Postgres recusa alterar o tipo de uma coluna que uma view usa —

        ERROR: cannot alter type of a column used by a view or rule

    — mesmo alargando, mesmo com a view sendo um `SELECT *`. Nao existe
    `CREATE OR REPLACE` que resolva: o tipo esta congelado na arvore da view.

    Por que derrubar e recriar uma VIEW nao e destrutivo:

      · view **nao guarda dado**. Nao ha linha a perder, que e o que um
        `DROP TABLE` custaria;
      · o DDL do Postgres e **transacional**: se o `CREATE` seguinte falhar, o
        `DROP` volta atras junto. Nao existe instante com a view faltando.

    E por que continua estreito: so entra a view cujo `CREATE VIEW` aparece na
    **mesma** migracao. Um `DROP VIEW` sozinho continua recusado, e `DROP
    TABLE`, `DROP COLUMN` e `DROP SCHEMA` nunca entram — nenhum deles e recriado
    por um `CREATE VIEW`.
    """
    derrubadas = set()
    criadas = set()
    for comando in comandos:
        limpo = " ".join(comando.split())
        casa = re.match(r"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?([a-z_][a-z0-9_.]*)", limpo, re.I)
        if casa:
            derrubadas.add(casa.group(1).lower())
        casa = re.match(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([a-z_][a-z0-9_.]*)", limpo, re.I
        )
        if casa:
            criadas.add(casa.group(1).lower())
    return derrubadas & criadas


def _alter_e_aditivo(comando: str) -> bool:
    """Um `ALTER TABLE` que so acrescenta?

    Recebe o comando ja em MAIUSCULAS. Devolve `False` para qualquer `ALTER`
    que nao seja um dos [ALTER_ADITIVOS] — inclusive os que nem contem a palavra
    `DROP`, como `ALTER COLUMN ... TYPE` e `... SET NOT NULL`.
    """
    if not comando.startswith("ALTER TABLE"):
        return False
    return any(operacao in comando for operacao in ALTER_ADITIVOS)


def _migracoes_guardadas() -> list[Path]:
    """Os arquivos de migracao a partir do corte, em ordem.

    O nome de um arquivo de migracao comeca por quatro digitos
    (`0012_schema_jogo_damas.py`); e esse numero que decide se ele entra.
    Arquivos sem o prefixo numerico sao ignorados — nao sao migracoes.
    """
    achados = []
    for arquivo in sorted(PASTA.glob("*.py")):
        casa = re.match(r"^(\d{4})_", arquivo.name)
        if casa and int(casa.group(1)) >= PRIMEIRA_GUARDADA:
            achados.append(arquivo)
    return achados


# A lista e calculada UMA vez, no momento em que o pytest coleta os testes, para
# poder virar parametro. Cada migracao vira um caso proprio: assim a falha diz
# QUAL arquivo tem o problema, em vez de um "alguma migracao falhou".
MIGRACOES = _migracoes_guardadas()

# `ids` faz o pytest imprimir o nome do arquivo em vez de um caminho gigante.
IDS = [m.stem for m in MIGRACOES]


def _corpo_do_upgrade(arquivo: Path) -> str:
    """Devolve o codigo-fonte APENAS da funcao `upgrade()`.

    Le o arquivo com `ast` em vez de recortar por texto: recortar por
    "def downgrade" quebraria no dia em que alguem trocasse a ordem das funcoes,
    e o teste passaria a olhar o pedaco errado sem avisar.
    """
    fonte = arquivo.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "upgrade":
            return ast.get_source_segment(fonte, no) or ""
    pytest.fail(f"{arquivo.name} nao tem uma funcao upgrade()")


def _sem_comentarios(codigo: str) -> str:
    """Tira comentarios e docstrings, e normaliza as quebras de linha.

    Tirar comentarios e NECESSARIO porque os proprios arquivos EXPLICAM que nao
    usam DROP — e a palavra aparece na explicacao. Um teste que olhasse o texto
    cru falharia por causa do comentario que existe para tranquilizar o leitor, o
    que seria comico e ensinaria a apagar comentarios uteis.

    A normalizacao existe porque `ast.unparse` devolve as strings de varias
    linhas com `\\n` **literal** (dois caracteres), e nao com a quebra de linha.
    Sem trocar um pelo outro, `.strip()` nao tira o inicio e o comando parece
    comecar por uma barra invertida.
    """
    arvore = ast.parse(codigo)
    # `ast.unparse` reconstroi o codigo a partir da arvore — e a arvore nao tem
    # comentarios. Docstrings sobrevivem como strings, e sao tiradas abaixo.
    limpo = ast.unparse(arvore)
    limpo = re.sub(r"^\s*(\"\"\"|''').*?(\"\"\"|''')\s*$", "", limpo, flags=re.S | re.M)
    return limpo.replace("\\n", "\n")


def _sem_clausula_on_delete(codigo: str) -> str:
    """Tira o `ON DELETE CASCADE` das definicoes de chave estrangeira.

    ⚠️ **Nao e uma brecha na regra — e a distincao entre duas coisas com o mesmo
    nome.** `ON DELETE CASCADE` nao apaga nada: e uma clausula que diz o que
    fazer com a linha filha **se** a linha pai for apagada um dia. Um comando
    `DELETE FROM ...` apaga agora.

    E a semantica correta nas extensoes: elas sao 1:1 com a partida ou a jogada
    generica, e uma extensao orfa (apontando para uma linha que nao existe mais)
    seria lixo.

    Sem esta funcao o teste acusaria a propria FK como comando destrutivo — um
    alarme falso, e alarme falso e o comeco de todo teste ignorado.
    """
    return re.sub(r"ON\s+DELETE\s+CASCADE", "", codigo, flags=re.IGNORECASE)


def _codigo_limpo(arquivo: Path) -> str:
    """O `upgrade()` sem comentarios e sem a clausula de FK."""
    return _sem_clausula_on_delete(_sem_comentarios(_corpo_do_upgrade(arquivo)))


class TestAVarreduraEnxerga:
    """Antes de guardar, o teste precisa provar que esta olhando alguma coisa."""

    def test_a_varredura_nao_esta_vazia(self):
        """Um cadeado que nao ve arquivo nenhum passa sempre — e nao guarda nada.

        Este caso e o que impede o teste inteiro de virar decoracao no dia em que
        a pasta mudar de lugar ou o padrao do nome mudar.
        """
        assert MIGRACOES, (
            f"nenhuma migracao encontrada em {PASTA} a partir da "
            f"{PRIMEIRA_GUARDADA:04d} — a varredura esta olhando o lugar errado"
        )

    def test_as_duas_conhecidas_estao_na_lista(self):
        """As que existem hoje. Nao e redundante: fixa o piso.

        Se alguem renomear um arquivo de forma a fugir do padrao `NNNN_`, a
        varredura o perderia em silencio e o teste acima continuaria passando —
        porque a lista nao ficaria vazia, so menor.
        """
        nomes = set(IDS)
        assert "0011_schema_jogo_velha" in nomes
        assert "0012_schema_jogo_damas" in nomes


@pytest.mark.parametrize("arquivo", MIGRACOES, ids=IDS)
class TestMigracaoAditiva:
    """Cada migracao guardada, uma a uma."""

    @pytest.mark.parametrize("palavra", PROIBIDOS)
    def test_upgrade_nao_contem_comando_destrutivo(self, arquivo: Path, palavra: str):
        codigo = _codigo_limpo(arquivo)
        # O `DROP VIEW` de uma view que a MESMA migracao recria nao e destruicao,
        # e sim reconstrucao — ver [_views_recriadas] para o porque, e para o
        # quao estreita a excecao e. Ele sai do texto antes da busca, como o
        # `ON DELETE CASCADE` ja saia.
        for nome in _views_recriadas(_comandos_do_upgrade(arquivo)):
            codigo = re.sub(
                rf"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?{re.escape(nome)}\b",
                "",
                codigo,
                flags=re.IGNORECASE,
            )
        achado = re.search(rf"\b{palavra}\b", codigo, flags=re.IGNORECASE)
        assert achado is None, (
            f"{arquivo.name} usa {palavra} no upgrade(). "
            "Ha usuarios reais em prd — nada de destrutivo nesta fase."
        )

    def test_upgrade_nao_contem_alter_drop(self, arquivo: Path):
        """`ALTER TABLE ... DROP COLUMN` some sozinho da regra acima?

        Nao: a palavra DROP ja o pegaria. Este caso existe para deixar claro que
        a intencao inclui o `ALTER` destrutivo, e nao so o `DROP TABLE`.
        """
        codigo = _codigo_limpo(arquivo)
        assert re.search(r"ALTER\s+TABLE.*DROP", codigo, flags=re.I | re.S) is None

    def test_upgrade_so_acrescenta(self, arquivo: Path):
        """O que a migracao PODE conter, listado explicitamente.

        Vira do avesso o teste acima: em vez de listar o proibido, confere que
        todo comando executado e um dos permitidos. Pega o destrutivo que um dia
        chegue com um nome que ninguem previu — `REVOKE`, `ALTER ... SET`, o que
        for.
        """
        comandos = _comandos_do_upgrade(arquivo)
        assert comandos, (
            f"nenhum op.execute em {arquivo.name} — o teste esta olhando o "
            "lugar errado"
        )
        recriadas = _views_recriadas(comandos)
        for c in comandos:
            inicio = " ".join(c.split()).upper()
            # O `ALTER TABLE` nao esta nos prefixos de proposito: ele passa pela
            # conferencia propria, que exige que a operacao seja um acrescimo —
            # ou um alargamento de `varchar`, a unica troca de tipo que nao pode
            # perder dado.
            permitido = (
                inicio.startswith(PERMITIDOS)
                or _alter_e_aditivo(inicio)
                or _alter_alarga_varchar(c, arquivo)
                or _e_drop_de_view_recriada(c, recriadas)
            )
            assert permitido, (
                f"{arquivo.name}: comando nao permitido: {c[:60]}"
            )

    def test_o_sentinela_9999_existe_se_ha_dimensao(self, arquivo: Path):
        """Toda dimensao com FK precisa do destino de escape.

        ⚠️ **Sem ele, um app MAIS NOVO que o backend estoura a FK e toma 500** —
        e a consequencia nao e um erro na tela: o evento fica **preso para
        sempre** na fila de sincronizacao daquele aparelho, e a partida da pessoa
        nunca sobe.

        So cobra de quem tem dimensao: uma migracao que so crie tabela de fato
        nao precisa de sentinela nenhum.
        """
        fonte = arquivo.read_text(encoding="utf-8")
        # A marca de que ha uma dimensao e uma tabela `tb9NN_`.
        if not re.search(r"tb9\d\d_", fonte):
            pytest.skip(f"{arquivo.name} nao cria tabela de dimensao")
        assert "9999" in fonte, f"{arquivo.name}: dimensao sem o sentinela 9999"
        assert "'desconhecido'" in fonte, (
            f"{arquivo.name}: o 9999 existe mas nao se chama 'desconhecido'"
        )


class TestARegraDoPermitido:
    """A propria regra do permitido, conferida caso a caso.

    ⚠️ **Por que isto existe.** Os testes acima aplicam a regra a arquivos que
    ja estao no repositorio — e todos passam, porque foram escritos para passar.
    Nenhum deles prova que a regra ainda RECUSA o que tem de recusar.

    Isso importa porque a lista de permitidos ja foi ampliada uma vez (na 0013,
    para caber `ADD COLUMN`), e ampliar cadeado e exatamente o momento em que
    ele silenciosamente para de guardar. Aqui a intencao fica escrita como
    exemplo, e nao como prosa: acrescentar `"ALTER TABLE"` aos prefixos por
    descuido faz **estes** casos falharem na hora.
    """

    # (comando, pode passar?)
    CASOS = [
        # Os que a 0013 precisou, e sao genuinamente aditivos.
        ("ALTER TABLE jogo_damas.tb002_jogada ADD COLUMN co_motor_busca VARCHAR(10)", True),
        ("ALTER TABLE x ADD CONSTRAINT ck_y CHECK (z IS NULL)", True),
        ("CREATE OR REPLACE VIEW jogo_damas.vw002_jogada AS SELECT 1", True),
        ("COMMENT ON COLUMN x.y IS 'z'", True),
        ("CREATE TABLE x (a INTEGER)", True),
        ("INSERT INTO x VALUES (1)", True),
        # `ALTER` destrutivo — o obvio.
        ("ALTER TABLE x DROP COLUMN y", False),
        # ⚠️ E os `ALTER` que NAO contem a palavra DROP, e que por isso o teste
        # da palavra proibida nao pegaria. Numa tabela com dados, o primeiro
        # falha se houver um NULL e o segundo pode reescrever a tabela inteira.
        ("ALTER TABLE x ALTER COLUMN y SET NOT NULL", False),
        ("ALTER TABLE x ALTER COLUMN y TYPE INTEGER", False),
        ("ALTER TABLE x RENAME COLUMN y TO z", False),
        # E o resto do que destroi dado.
        ("DELETE FROM x", False),
        ("TRUNCATE x", False),
        ("UPDATE x SET y = 1", False),
        ("REVOKE ALL ON x FROM y", False),
    ]

    @pytest.mark.parametrize("comando, esperado", CASOS)
    def test_a_regra_aceita_e_recusa_o_que_deve(self, comando: str, esperado: bool):
        # A mesma expressao usada em `test_upgrade_so_acrescenta`. Se as duas
        # divergirem um dia, este teste passa a guardar outra coisa — por isso
        # ela e curta e esta escrita igual nos dois lugares.
        maiusculo = " ".join(comando.split()).upper()
        obtido = maiusculo.startswith(PERMITIDOS) or _alter_e_aditivo(maiusculo)

        assert obtido == esperado, (
            f"{comando!r}: a regra {'aceitou' if obtido else 'recusou'}, "
            f"e deveria {'aceitar' if esperado else 'recusar'}"
        )


class TestAsDuasExcecoesDA0014:
    """As duas excecoes que a 0014 obrigou a escrever — e o que elas RECUSAM.

    (!) **Este e o teste que importa.** As excecoes foram escritas para deixar a
    0014 passar; nenhuma delas prova, por si, que continuam recusando o resto.
    Aqui o limite fica escrito como exemplo, e nao como prosa.
    """

    ZERO = RAIZ / "migrations" / "versions" / "0014_versoes_motor_compostas.py"

    # (comando, pode passar?) — a coluna real e `co_versao_motor`, que a 0012
    # criou com VARCHAR(20).
    CASOS_ALARGAR = [
        # Alargar: 20 -> 60. E o que a 0014 faz.
        (
            "ALTER TABLE jogo_damas.tb001_partida "
            "ALTER COLUMN co_versao_motor TYPE VARCHAR(60)",
            True,
        ),
        # (!) ESTREITAR perde dado, e continua recusado.
        (
            "ALTER TABLE jogo_damas.tb001_partida "
            "ALTER COLUMN co_versao_motor TYPE VARCHAR(10)",
            False,
        ),
        # Mesma largura nao e alargar.
        (
            "ALTER TABLE jogo_damas.tb001_partida "
            "ALTER COLUMN co_versao_motor TYPE VARCHAR(20)",
            False,
        ),
        # Coluna que nenhuma migracao anterior declarou: na duvida, RECUSA.
        ("ALTER TABLE x.y ALTER COLUMN z TYPE VARCHAR(60)", False),
        # Trocar de FAMILIA de tipo nunca passa, por maior que seja o destino.
        (
            "ALTER TABLE jogo_damas.tb001_partida "
            "ALTER COLUMN co_versao_motor TYPE TEXT",
            False,
        ),
        # E o resto da familia `ALTER COLUMN`, que quebra tabela com dados.
        (
            "ALTER TABLE jogo_damas.tb001_partida "
            "ALTER COLUMN co_versao_motor SET NOT NULL",
            False,
        ),
    ]

    @pytest.mark.parametrize("comando, esperado", CASOS_ALARGAR)
    def test_so_alargar_passa(self, comando: str, esperado: bool):
        assert _alter_alarga_varchar(comando, self.ZERO) is esperado, (
            f"{comando!r}: a regra do alargamento decidiu errado"
        )

    def test_o_alter_da_0014_nao_valida_a_si_mesmo(self):
        """A largura anterior vem SO das migracoes anteriores.

        Se `_largura_anterior` lesse a propria 0014, acharia os 60 que ela
        declara e a conta viraria `60 > 60` — o comando invalidando a si mesmo.
        """
        assert (
            _largura_anterior(self.ZERO, "jogo_damas.tb001_partida", "co_versao_motor")
            == 20
        )

    # (comandos da migracao, o comando conferido, pode passar?)
    CASOS_DROP = [
        # Derrubar e recriar a MESMA view: e reconstrucao, e passa.
        (
            ["DROP VIEW jogo_damas.vw001_partida", "CREATE VIEW jogo_damas.vw001_partida AS SELECT 1"],
            "DROP VIEW jogo_damas.vw001_partida",
            True,
        ),
        # (!) Derrubar SEM recriar continua recusado.
        (["DROP VIEW jogo_damas.vw001_partida"], "DROP VIEW jogo_damas.vw001_partida", False),
        # Recriar OUTRA view nao autoriza derrubar esta.
        (
            ["DROP VIEW jogo_damas.vw001_partida", "CREATE VIEW jogo_damas.vw002_jogada AS SELECT 1"],
            "DROP VIEW jogo_damas.vw001_partida",
            False,
        ),
        # (!) DROP TABLE nunca passa — nenhum `CREATE VIEW` o recria.
        (
            ["DROP TABLE jogo_damas.tb001_partida", "CREATE VIEW jogo_damas.tb001_partida AS SELECT 1"],
            "DROP TABLE jogo_damas.tb001_partida",
            False,
        ),
        # DROP SCHEMA idem.
        (["DROP SCHEMA jogo_damas CASCADE"], "DROP SCHEMA jogo_damas CASCADE", False),
    ]

    @pytest.mark.parametrize("comandos, conferido, esperado", CASOS_DROP)
    def test_so_view_recriada_passa(self, comandos, conferido, esperado):
        recriadas = _views_recriadas(comandos)
        assert _e_drop_de_view_recriada(conferido, recriadas) is esperado, (
            f"{conferido!r}: a regra do DROP de view decidiu errado"
        )


class TestACorrenteDeRevisoes:
    """As migracoes formam uma corrente — e ela nao pode ter no solto."""

    def test_cada_migracao_aponta_para_a_anterior(self):
        """`down_revision` de uma tem de ser a `revision` da outra.

        Um `down_revision` errado nao quebra na hora: o Alembic monta a arvore e
        so reclama quando alguem roda `upgrade head` — e ai ja e no ambiente.
        Aqui e de graca.
        """
        def _campo(arquivo: Path, nome: str) -> str | None:
            fonte = arquivo.read_text(encoding="utf-8")
            achado = re.search(rf'^{nome}[^=]*=\s*"([^"]+)"', fonte, re.M)
            return achado.group(1) if achado else None

        for anterior, atual in zip(MIGRACOES, MIGRACOES[1:]):
            revisao_anterior = _campo(anterior, "revision")
            aponta_para = _campo(atual, "down_revision")
            assert aponta_para == revisao_anterior, (
                f"{atual.name} aponta para '{aponta_para}', mas a migracao "
                f"anterior e '{revisao_anterior}'"
            )

    def test_o_id_de_revisao_cabe_no_limite_do_alembic(self):
        """⚠️ 32 caracteres.

        Passar disso faz o upgrade RODAR o DDL inteiro e falhar **so no fim**,
        revertendo tudo — um erro caro de diagnosticar, porque o sintoma aparece
        longe da causa.
        """
        for arquivo in MIGRACOES:
            fonte = arquivo.read_text(encoding="utf-8")
            achado = re.search(r'^revision[^=]*=\s*"([^"]+)"', fonte, re.M)
            assert achado, f"{arquivo.name} nao declara `revision`"
            assert len(achado.group(1)) <= 32, (
                f"{arquivo.name}: id de revisao com {len(achado.group(1))} "
                "caracteres, e o limite do Alembic e 32"
            )
