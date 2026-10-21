"""🔒 A MIGRAÇÃO 0036 CORRESPONDE AO `data-model.md` §4 QUE O DONO VALIDOU (T118).

POR QUE ESTE CADEADO EXISTE
---------------------------
O dono valida o `data-model.md`, e não o código do Alembic (a decisão de
09/09/2026, repetida na T003 da spec 010 em 13/10/2026, §8zzz). Então a garantia
de que a migração diz o que o documento prometeu precisa ser MECÂNICA: sem isto,
a validação viraria um cheque em branco - uma coluna a mais, um tipo trocado ou
um `NOT NULL` esquecido chegariam ao banco sem nada acusar.

O irmão `test_migracao_quatro_bate_com_data_model.py` faz o mesmo para a §2 (o
schema `jogo_quatro`); este lê a §4 (o schema `log`), que escreve as tabelas em
MARKDOWN (`| coluna | tipo | restrição | o quê |`) e as constraints em SQL.

O QUE ELE COMPARA
-----------------
  · cada COLUNA de `log.tb003_aparelho` e `log.tb004_aparelho_dia`: nome, tipo,
    restrição e ORDEM (campo importante não fica no fim, §8b);
  · a FK do dia para o aparelho, com o `ON DELETE CASCADE`;
  · as CONSTRAINTS nomeadas (`ck001_plataforma`, `pk_aparelho_dia`), pelo nome e
    pela espécie;
  · os dois ÍNDICES, com as colunas;
  · as duas VIEWS, com TODAS as colunas da tabela, listadas e na ordem (a lição
    da 0017: `SELECT *` congela as colunas do dia em que a view nasceu);
  · o id da revisão, que o documento também escreve.

⛔ Nunca "ajuste o teste para passar": se ele falhar, ou a migração divergiu do
que o dono validou (conserta-se a migração), ou o modelo precisa mudar - e isso
é decisão do dono, com o `data-model.md` mudando primeiro.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unitarios.leitura_de_migracao import (
    sem_comentarios_sql,
    sql_do_upgrade,
    tabelas_do_sql,
)

RAIZ = Path(__file__).resolve().parents[2]
DATA_MODEL = (
    RAIZ.parent / "arena-sagaz-frontend" / "specs" / "010-jogo-quatro-em-linha" / "data-model.md"
)
MIGRACAO = RAIZ / "migrations" / "versions" / "0036_log_aparelho.py"

TABELAS = ("log.tb003_aparelho", "log.tb004_aparelho_dia")


# ═══════════════════════════════════════════════════════════════════════════
# A leitura do documento
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def secao_4() -> str:
    """Só a §4 do documento (o aparelho e o uso de cada dia), até a §5.

    ⛔ Sem o documento, FALHA (e não `skip`): sem ele não há contra o que
    comparar.
    """
    assert DATA_MODEL.is_file(), f"o data-model.md não está em {DATA_MODEL}"
    texto = DATA_MODEL.read_text(encoding="utf-8")
    inicio = texto.index("## 4. ")
    return texto[inicio : texto.index("\n## 5. ", inicio)]


def _bloco_da_tabela(secao: str, tabela: str) -> str:
    """O texto debaixo do título `### 4.n \\`<tabela>\\``, até o próximo `###`."""
    casou = re.search(rf"^### 4\.\d `{re.escape(tabela)}`.*?(?=^### |\Z)", secao, re.M | re.S)
    assert casou, f"o documento não tem a subseção de {tabela}"
    return casou.group(0)


def _colunas_do_documento(bloco: str) -> list[tuple[str, str]]:
    """`[(coluna, "TIPO RESTRIÇÃO")]` da tabela `| coluna | tipo | restrição |`.

    O tipo e a restrição saem juntos, em maiúsculas e com os espaços colapsados,
    e SEM a cláusula `REFERENCES` - é a mesma forma que `tabelas_do_sql` dá às
    colunas da migração (a FK é conferida em caso próprio).
    """
    linhas = bloco.splitlines()
    inicio = next(i for i, l in enumerate(linhas) if l.startswith("| coluna | tipo |"))
    colunas = []
    for linha in linhas[inicio + 2 :]:
        if not linha.startswith("|"):
            break
        celulas = [c.strip().strip("`") for c in linha.strip().strip("|").split("|")]
        nome, tipo, restricao = celulas[0], celulas[1], celulas[2].replace("`", "")
        restricao = re.split(r"\bREFERENCES\b", restricao)[0]
        colunas.append((nome, " ".join(f"{tipo} {restricao}".upper().split())))
    return colunas


# ═══════════════════════════════════════════════════════════════════════════
# A leitura da migração
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def sql() -> str:
    """O SQL do `upgrade()` da 0036, sem os comentários `--`."""
    assert MIGRACAO.is_file(), f"a migração não está em {MIGRACAO}"
    return sem_comentarios_sql(sql_do_upgrade(MIGRACAO))


@pytest.fixture(scope="module")
def tabelas(sql) -> dict[str, dict[str, object]]:
    return tabelas_do_sql(sql)


def _colunas_da_view(sql: str, view: str) -> list[str]:
    """As colunas do `SELECT` de [view], na ordem, sem o apelido da tabela."""
    casou = re.search(rf"CREATE VIEW {re.escape(view)} AS\s+SELECT(.*?)\bFROM\b", sql, re.S)
    assert casou, f"a migração não cria a view {view}"
    return [c.strip().split(".")[-1] for c in casou.group(1).split(",")]


# ═══════════════════════════════════════════════════════════════════════════
# Os casos
# ═══════════════════════════════════════════════════════════════════════════


def test_a_revisao_e_a_que_o_documento_escreve(secao_4) -> None:
    """O documento diz `0036_log_aparelho`; a migração, o arquivo e o id também.
    Até 32 caracteres, o teto da coluna `alembic_version.version_num`."""
    revisao = re.search(r"Revisão proposta: `([0-9a-z_]+)`", secao_4).group(1)
    fonte = MIGRACAO.read_text(encoding="utf-8")
    assert f'revision: str = "{revisao}"' in fonte
    assert MIGRACAO.stem == revisao and len(revisao) <= 32
    assert 'down_revision: Union[str, None] = "0035_desafio_quatro"' in fonte


@pytest.mark.parametrize("tabela", TABELAS)
def test_as_colunas_batem_NA_ORDEM_com_tipo_e_restricao(tabela, secao_4, tabelas) -> None:
    do_documento = _colunas_do_documento(_bloco_da_tabela(secao_4, tabela))
    assert do_documento, f"o documento não lista as colunas de {tabela}"
    assert tabelas[tabela]["colunas"] == do_documento


def test_a_fk_do_dia_aponta_para_o_aparelho_com_cascata(secao_4, sql) -> None:
    """A única FK da §4: o dia não existe sem o aparelho."""
    clausula = "REFERENCES log.tb003_aparelho(id_aparelho) ON DELETE CASCADE"
    assert clausula in _bloco_da_tabela(secao_4, "log.tb004_aparelho_dia")
    assert re.search(rf"id_aparelho\s+UUID\s+NOT NULL\s+{re.escape(clausula)}", sql)


def test_as_constraints_nomeadas_batem(secao_4, tabelas) -> None:
    """`ck001_plataforma` e `pk_aparelho_dia`: os nomes e as espécies do
    documento são os da migração, nem mais nem menos."""
    do_documento = {
        nome: especie
        for nome, especie in re.findall(r"CONSTRAINT (\w+) (CHECK|PRIMARY KEY)", secao_4)
    }
    da_migracao = {
        nome: especie
        for tabela in TABELAS
        for nome, especie in tabelas[tabela]["constraints"].items()
    }
    assert do_documento == {"ck001_plataforma": "CHECK", "pk_aparelho_dia": "PRIMARY KEY"}
    assert da_migracao == do_documento


def test_o_check_da_plataforma_tem_as_tres(sql) -> None:
    assert re.search(
        r"CONSTRAINT ck001_plataforma\s+CHECK \(co_plataforma IN \('android', 'ios', 'web'\)\)",
        sql,
    )


def test_a_chave_do_dia_e_aparelho_e_data(sql) -> None:
    assert "CONSTRAINT pk_aparelho_dia PRIMARY KEY (id_aparelho, dt_dia_local)" in sql


def test_os_indices_batem(secao_4, sql) -> None:
    """Os dois índices do documento, com as colunas, e nenhum a mais."""
    do_documento = dict(re.findall(r"`(ix_[a-z_]+) ON \(([^)]+)\)`", secao_4))
    da_migracao = dict(
        re.findall(r"CREATE INDEX (ix_[a-z_]+)\s+ON log\.tb004_aparelho_dia \(([^)]+)\)", sql)
    )
    assert do_documento == {
        "ix_aparelho_dia_data": "dt_dia_local",
        "ix_aparelho_dia_usuario": "id_usuario",
    }
    assert da_migracao == do_documento
    assert len(re.findall(r"CREATE INDEX", sql)) == len(do_documento)


@pytest.mark.parametrize(
    "view, tabela",
    [("log.vw003_aparelho", "log.tb003_aparelho"), ("log.vw004_aparelho_dia", "log.tb004_aparelho_dia")],
)
def test_as_views_LISTAM_todas_as_colunas_na_ordem(view, tabela, secao_4, sql, tabelas) -> None:
    """⚠️ A lição da 0017: view com `SELECT *` não enxerga coluna acrescentada
    depois. Aqui ela lista, e lista todas."""
    assert f"`{view}`" in secao_4, f"o documento não nomeia a view {view}"
    assert "SELECT *" not in sql
    assert _colunas_da_view(sql, view) == [c for c, _ in tabelas[tabela]["colunas"]]
