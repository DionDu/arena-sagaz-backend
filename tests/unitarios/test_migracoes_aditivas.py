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
        codigo = _sem_comentarios(_corpo_do_upgrade(arquivo))
        comandos = re.findall(r"op\.execute\(\s*(?:'|\")(.*?)(?:'|\")", codigo, re.S)
        assert comandos, (
            f"nenhum op.execute em {arquivo.name} — o teste esta olhando o "
            "lugar errado"
        )
        for c in comandos:
            inicio = c.strip().upper()
            # O `ALTER TABLE` nao esta nos prefixos de proposito: ele passa pela
            # conferencia propria, que exige que a operacao seja um acrescimo.
            permitido = inicio.startswith(PERMITIDOS) or _alter_e_aditivo(inicio)
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
        maiusculo = comando.strip().upper()
        obtido = maiusculo.startswith(PERMITIDOS) or _alter_e_aditivo(maiusculo)

        assert obtido == esperado, (
            f"{comando!r}: a regra {'aceitou' if obtido else 'recusou'}, "
            f"e deveria {'aceitar' if esperado else 'recusar'}"
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
