"""🔒 A MIGRACAO CORRESPONDE AO `data-model.md` QUE O DONO PRE-VALIDOU.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE CADEADO EXISTE — E A DATA IMPORTA
═══════════════════════════════════════════════════════════════════════════

Em 09/09/2026 o dono disse, com todas as letras:

    "Eu nao vou conferir codigo de Alembic. Eu ja pre validei o data-model.md."

E a decisao certa, e ela **transfere o peso da prova**. Ate aqui, a garantia de
que a migracao dizia o que o modelo prometia era *"alguem le os dois"*. A partir
daqui, ninguem le — entao a correspondencia precisa ser **mecanica**.

    o dono validou   →  specs/009-desafio-do-dia/data-model.md
    o job vai rodar  →  migrations/versions/0018 e 0019
    este teste       →  prova que os dois dizem a MESMA coisa

⚠️ **Sem isto, a pre-validacao viraria um cheque em branco.** Eu poderia escrever
uma coluna a mais, esquecer uma constraint ou trocar um tipo, e o que o dono
aprovou nao seria o que o banco receberia — sem que nada acusasse, porque os
outros cadeados conferem a migracao contra **si mesma** (o `CHECK` contra o
`Literal`, o `INSERT` contra o `VARCHAR`), e nunca contra o documento.

═══════════════════════════════════════════════════════════════════════════
O QUE ELE COMPARA
═══════════════════════════════════════════════════════════════════════════

Tabela a tabela, e dentro de cada uma:

  · **as colunas**, com nome, tipo e ordem — ⚠️ **a ordem entra de proposito**:
    a regra §8b diz que campo importante nao fica no fim da tabela, e ordem e
    exatamente o que uma comparacao de conjuntos perderia;
  · **as constraints nomeadas** (`un00N_`, `ck00N_`, `fk00N_`);
  · **os indices** (`ix00N_`).

⛔ **O que ele NAO compara** e o texto dos `CHECK`: o `data-model.md` os escreve
com quebras de linha e alinhamento diferentes, e comparar texto formatado geraria
alarme falso a cada reindentacao. Quem guarda o **conteudo** dos `CHECK` e
`test_modelos_desafio.py`, que le os valores e os compara com os `Literal` do
codigo. Dois cadeados, duas metades.

═══════════════════════════════════════════════════════════════════════════
COMO SE CONSERTA UMA FALHA DAQUI
═══════════════════════════════════════════════════════════════════════════

⚠️ **Depende de qual dos dois esta errado, e essa pergunta e do DONO, nao minha.**

  · a migracao divergiu do que ele validou  → conserta-se a migracao;
  · o modelo e que precisa mudar            → ⛔ **e decisao dele**, e o
    `data-model.md` muda primeiro, com o registro em `DECISOES-do-dono.md`.

⛔ **Nunca "ajuste o teste para passar".** Este e o unico teste do projeto cuja
falha significa *"o que foi aprovado nao e o que vai rodar"*.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# ⚠️ O extrator de SQL mora em modulo proprio: tres cadeados o usam, e tres
# implementacoes acabariam discordando — ver a docstring de la.
from tests.unitarios.leitura_de_migracao import sql_da_migracao

RAIZ = Path(__file__).resolve().parents[2]
DATA_MODEL = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "data-model.md"
)
MIGRACOES = {
    "desafio": RAIZ / "migrations" / "versions" / "0018_schema_desafio.py",
    "desafio_dia": RAIZ / "migrations" / "versions" / "0019_schema_desafio_dia.py",
}


# ═══════════════════════════════════════════════════════════════════════════
# A leitura do DDL
# ═══════════════════════════════════════════════════════════════════════════


def _sem_comentarios_sql(texto: str) -> str:
    """Tira os comentarios `--` do SQL, preservando as linhas.

    O `data-model.md` documenta cada coluna com um `--` ao lado; a migracao usa
    comentarios de Python acima do bloco. Comparar com eles dentro produziria
    divergencia em toda linha comentada de um lado so.
    """
    return "\n".join(linha.split("--")[0] for linha in texto.splitlines())


def _dividir_no_topo(corpo: str) -> list[str]:
    """Divide por virgulas do NIVEL MAIS ALTO dos parenteses.

    ⚠️ Um `split(",")` simples quebraria `VARCHAR(30)` e
    `CHECK (co_modo IN ('a', 'b'))` no meio — e o resultado seria um monte de
    pedacos que nao sao nem coluna nem constraint.
    """
    partes: list[str] = []
    atual: list[str] = []
    profundidade = 0
    for caractere in corpo:
        if caractere == "(":
            profundidade += 1
        elif caractere == ")":
            profundidade -= 1
        if caractere == "," and profundidade == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(caractere)
    if "".join(atual).strip():
        partes.append("".join(atual))
    return [p.strip() for p in partes if p.strip()]


def _corpo_da_tabela(texto: str, inicio: int) -> str:
    """O conteudo entre os parenteses do `CREATE TABLE`, casando o fechamento."""
    abre = texto.index("(", inicio)
    profundidade = 0
    for posicao in range(abre, len(texto)):
        if texto[posicao] == "(":
            profundidade += 1
        elif texto[posicao] == ")":
            profundidade -= 1
            if profundidade == 0:
                return texto[abre + 1 : posicao]
    raise AssertionError("CREATE TABLE sem parentese de fechamento")


def _tabelas(texto: str) -> dict[str, dict[str, object]]:
    """Extrai `{tabela: {colunas: [(nome, tipo)], constraints: {nome: tipo}}}`.

    O `tipo` de coluna e normalizado: maiusculas, espacos colapsados, e sem a
    clausula `REFERENCES` — a FK inline e comparada como constraint, e o
    `data-model.md` a escreve quebrada em varias linhas.
    """
    limpo = _sem_comentarios_sql(texto)
    achadas: dict[str, dict[str, object]] = {}

    for casa in re.finditer(
        r"CREATE TABLE\s+([a-z_][a-z0-9_.]*)\s*\(", limpo, re.I
    ):
        nome = casa.group(1).lower()
        corpo = _corpo_da_tabela(limpo, casa.start())

        colunas: list[tuple[str, str]] = []
        constraints: dict[str, str] = {}

        for parte in _dividir_no_topo(corpo):
            normalizada = " ".join(parte.split())
            if normalizada.upper().startswith("CONSTRAINT "):
                nome_da_constraint = normalizada.split()[1].lower()
                # A ESPECIE da constraint (UNIQUE, CHECK, FOREIGN KEY), e nao o
                # texto dela — ver a docstring do modulo.
                especie = "outra"
                for candidata in ("UNIQUE", "CHECK", "FOREIGN KEY", "PRIMARY KEY"):
                    if candidata in normalizada.upper():
                        especie = candidata
                        break
                constraints[nome_da_constraint] = especie
                continue

            campos = normalizada.split(None, 1)
            if len(campos) != 2:
                continue
            nome_da_coluna, resto = campos[0].lower(), campos[1]
            # Tira a FK inline: ela vira constraint anonima, e o que importa
            # dela (para onde aponta) o proprio banco guarda.
            resto = re.split(r"\bREFERENCES\b", resto, flags=re.I)[0]
            colunas.append((nome_da_coluna, " ".join(resto.upper().split())))

        achadas[nome] = {"colunas": colunas, "constraints": constraints}

    return achadas


def _indices(texto: str) -> set[tuple[str, str]]:
    """`{(nome_do_indice, tabela)}` de todos os `CREATE INDEX`."""
    limpo = _sem_comentarios_sql(texto)
    return {
        (nome.lower(), tabela.lower())
        for nome, tabela in re.findall(
            r"CREATE INDEX\s+([a-z_][a-z0-9_]*)\s+ON\s+([a-z_][a-z0-9_.]*)",
            limpo,
            re.I,
        )
    }


@pytest.fixture(scope="module")
def do_documento() -> dict[str, dict[str, object]]:
    """As tabelas declaradas no `data-model.md`.

    ⛔ Ausencia do documento e FALHA. Sem ele nao ha contra o que comparar, e um
    `skip` aqui apagaria justamente a garantia que o dono comprou ao dizer que
    nao leria o codigo.
    """
    assert DATA_MODEL.is_file(), (
        f"o data-model.md nao esta em {DATA_MODEL}. ⛔ Este cadeado FALHA em vez "
        "de pular: sem o documento, a pre-validacao do dono vira cheque em branco."
    )
    return _tabelas(DATA_MODEL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def da_migracao() -> dict[str, dict[str, object]]:
    """As tabelas criadas pelas migracoes `0018` e `0019`."""
    juntas: dict[str, dict[str, object]] = {}
    for schema, caminho in MIGRACOES.items():
        assert caminho.is_file(), f"a migracao de {schema} nao esta em {caminho}"
        juntas.update(_tabelas(sql_da_migracao(caminho)))
    return juntas


# ═══════════════════════════════════════════════════════════════════════════
# Os casos
# ═══════════════════════════════════════════════════════════════════════════


def test_a_varredura_enxerga_os_dois_lados(do_documento, da_migracao) -> None:
    """Antes de comparar, provar que ha o que comparar.

    Um cadeado que compara dois dicionarios vazios passa sempre — e este e o
    unico teste do projeto cuja falha significa "o que foi aprovado nao e o que
    vai rodar". Ele nao pode virar decoracao.
    """
    assert len(do_documento) >= 12, f"o documento rendeu {len(do_documento)} tabelas"
    assert len(da_migracao) >= 12, f"as migracoes renderam {len(da_migracao)} tabelas"


def test_as_MESMAS_tabelas_dos_dois_lados(do_documento, da_migracao) -> None:
    """🔒 Nenhuma tabela a mais, nenhuma a menos.

    ⚠️ Tabela que so existe na migracao e estrutura que o dono nao aprovou.
    Tabela que so existe no documento e promessa que o banco nao vai cumprir — e
    a segunda e pior, porque o codigo que a consultar vai falhar em producao.
    """
    so_na_migracao = sorted(set(da_migracao) - set(do_documento))
    so_no_documento = sorted(set(do_documento) - set(da_migracao))
    assert not so_na_migracao and not so_no_documento, (
        "as tabelas divergiram entre o data-model.md e as migracoes.\n"
        f"  so na migracao: {so_na_migracao}\n"
        f"  so no documento: {so_no_documento}"
    )


@pytest.mark.parametrize(
    "tabela",
    sorted(_tabelas(DATA_MODEL.read_text(encoding="utf-8"))) if DATA_MODEL.is_file() else [],
)
def test_as_colunas_batem_NA_ORDEM(tabela: str, do_documento, da_migracao) -> None:
    """🔒 Nome, tipo e **ordem** de cada coluna.

    ⚠️ **A ordem entra de proposito.** A regra §8b do dono diz que campo
    importante nao fica no fim da tabela — e ordem e exatamente o que uma
    comparacao de conjuntos perderia. Uma coluna que escorregasse para o fim
    passaria por qualquer teste que so olhasse "quais colunas existem".
    """
    esperadas = do_documento[tabela]["colunas"]
    obtidas = da_migracao.get(tabela, {}).get("colunas", [])

    nomes_esperados = [c[0] for c in esperadas]
    nomes_obtidos = [c[0] for c in obtidas]
    assert nomes_obtidos == nomes_esperados, (
        f"{tabela}: as colunas divergiram (o documento manda).\n"
        f"  documento: {nomes_esperados}\n"
        f"  migracao : {nomes_obtidos}"
    )

    divergentes = {
        nome: (tipo_esperado, tipo_obtido)
        for (nome, tipo_esperado), (_, tipo_obtido) in zip(esperadas, obtidas)
        if tipo_esperado != tipo_obtido
    }
    assert not divergentes, (
        f"{tabela}: tipos divergentes (documento x migracao): {divergentes}"
    )


@pytest.mark.parametrize(
    "tabela",
    sorted(_tabelas(DATA_MODEL.read_text(encoding="utf-8"))) if DATA_MODEL.is_file() else [],
)
def test_as_constraints_NOMEADAS_batem(tabela: str, do_documento, da_migracao) -> None:
    """🔒 Cada `un00N_`, `ck00N_` e `fk00N_` do documento existe na migracao.

    ⚠️ Uma constraint esquecida **nao da erro**: ela simplesmente deixa entrar o
    que deveria recusar. `un001_resolucao` faltando permitiria duas resolucoes da
    mesma pessoa no mesmo dia; `ck004_motivo` faltando deixaria um desafio
    descartado sem motivo, que ninguem consegue interpretar meses depois.
    """
    esperadas = do_documento[tabela]["constraints"]
    obtidas = da_migracao.get(tabela, {}).get("constraints", {})

    faltando = {n: e for n, e in esperadas.items() if n not in obtidas}
    sobrando = {n: e for n, e in obtidas.items() if n not in esperadas}
    assert not faltando and not sobrando, (
        f"{tabela}: constraints divergentes.\n"
        f"  no documento e nao na migracao: {faltando}\n"
        f"  na migracao e nao no documento: {sobrando}"
    )

    especie_trocada = {
        nome: (esperadas[nome], obtidas[nome])
        for nome in esperadas
        if nome in obtidas and esperadas[nome] != obtidas[nome]
    }
    assert not especie_trocada, (
        f"{tabela}: constraints com especie trocada: {especie_trocada}"
    )


def test_os_indices_batem() -> None:
    """Os `CREATE INDEX` do documento existem nas migracoes.

    ⚠️ Indice faltando nao quebra nada — deixa lento. E "lento" e o defeito que
    ninguem investiga ate a curadoria comecar a demorar, meses depois, sem que
    ninguem ligue as duas coisas.
    """
    do_doc = {
        (nome, tabela)
        for nome, tabela in _indices(DATA_MODEL.read_text(encoding="utf-8"))
        if tabela.startswith(("desafio.", "desafio_dia."))
    }
    da_mig: set[tuple[str, str]] = set()
    for caminho in MIGRACOES.values():
        da_mig |= _indices(sql_da_migracao(caminho))

    faltando = sorted(do_doc - da_mig)
    assert not faltando, f"indices do documento ausentes das migracoes: {faltando}"


def test_este_cadeado_nao_tem_saida_de_emergencia() -> None:
    """⛔ Sem `skip`, sem `xfail`, sem condicional.

    ⚠️ E o unico teste do projeto cuja falha significa **"o que o dono aprovou nao
    e o que vai rodar"**. Um `skipif` aqui — mesmo com o melhor dos motivos —
    devolveria a pre-validacao ao estado de cheque em branco.
    """
    import ast

    fonte = Path(__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    proibidos: list[str] = []
    for no in ast.walk(arvore):
        # Decoradores `@pytest.mark.skip` / `skipif` / `xfail`.
        if isinstance(no, ast.Attribute) and no.attr in {"skip", "skipif", "xfail"}:
            proibidos.append(no.attr)
        # Chamadas `pytest.skip(...)`.
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "skip"
        ):
            proibidos.append("pytest.skip()")

    assert not proibidos, (
        f"este cadeado ganhou saida de emergencia: {proibidos}. ⛔ Ele nao pode "
        "ter uma: a pre-validacao do dono depende de ele rodar sempre."
    )
