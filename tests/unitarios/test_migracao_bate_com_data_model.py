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
from tests.unitarios.leitura_de_migracao import (
    sem_comentarios_sql,
    sql_da_migracao,
    tabelas_do_sql,
)

# ⚠️ Os leitores de DDL subiram para o modulo compartilhado em 10/09/2026,
# quando o cadeado do `INSERT` do job passou a precisar dos mesmos. O alias
# mantem o nome curto que os casos daqui ja usavam.
_tabelas = tabelas_do_sql
_sem_comentarios_sql = sem_comentarios_sql

RAIZ = Path(__file__).resolve().parents[2]
DATA_MODEL = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "data-model.md"
)
VERSOES = RAIZ / "migrations" / "versions"

#: Os schemas que o `data-model.md` descreve — e so eles.
SCHEMAS = ("desafio", "desafio_dia")


def migracoes_dos_schemas() -> list[Path]:
    """Toda migracao que cria tabela em `desafio` ou `desafio_dia`.

    ⚠️ **DESCOBERTA, e nao lista escrita a mao.** Ate 10/09/2026 este modulo
    nomeava `0018` e `0019` em duas linhas fixas. No dia em que a `0021` trouxe
    `desafio_dia.tb007_desafio_impedido`, o cadeado passou **VERDE sem nunca ter
    olhado para a tabela nova** — e o unico teste do projeto cuja falha significa
    *"o que foi aprovado nao e o que vai rodar"* estava aprovando uma tabela que
    o dono nao tinha visto.

    ⚠️ E a **sexta** aparicao do mesmo defeito no projeto: cadeado que *acha*
    que sabe o que existe fica cego exatamente quando algo novo chega, que e
    quando ele precisava enxergar.
    """
    achadas = [
        caminho
        for caminho in sorted(VERSOES.glob("[0-9]*.py"))
        if any(
            f"CREATE TABLE {schema}." in sql_da_migracao(caminho)
            for schema in SCHEMAS
        )
    ]
    assert achadas, (
        "⛔ nenhuma migracao cria tabela em desafio/desafio_dia. **Nada a varrer "
        "e FALHA**, e nao sucesso: sem isso o cadeado compara dois vazios e passa."
    )
    return achadas


# ═══════════════════════════════════════════════════════════════════════════
# A leitura do DDL
# ═══════════════════════════════════════════════════════════════════════════


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
    """As tabelas de `desafio`/`desafio_dia` criadas por QUALQUER migracao."""
    juntas: dict[str, dict[str, object]] = {}
    for caminho in migracoes_dos_schemas():
        for nome, corpo in _tabelas(sql_da_migracao(caminho)).items():
            # ⛔ So os dois schemas que o documento descreve: uma migracao pode
            # criar tabela em `partida` ou `log` na mesma passada, e compara-la
            # com o `data-model.md` acusaria divergencia que nao existe.
            if nome.split(".")[0] in SCHEMAS:
                juntas[nome] = corpo
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


def test_a_varredura_NAO_e_uma_lista_escrita_a_mao() -> None:
    """🔒 O cadeado nao pode voltar a nomear as migracoes uma a uma.

    ⚠️ **Este caso existe por causa de um verde falso**, em 10/09/2026: o modulo
    nomeava `0018` e `0019`, a `0021` criou uma tabela nova, e a comparacao
    passou sem nunca te-la visto. Exigir que a varredura ache **alguma migracao
    alem daquelas duas** e o que impede a lista fixa de voltar disfarcada.
    """
    nomes = {caminho.name for caminho in migracoes_dos_schemas()}
    assert "0018_schema_desafio.py" in nomes
    assert "0019_schema_desafio_dia.py" in nomes
    assert nomes - {"0018_schema_desafio.py", "0019_schema_desafio_dia.py"}, (
        "⛔ a varredura achou APENAS as duas migracoes originais. Ou nenhuma "
        "migracao posterior criou tabela nestes schemas — e ai este caso deve "
        "ser reescrito com consciencia — ou a descoberta virou lista fixa de novo."
    )


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
    for caminho in migracoes_dos_schemas():
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
