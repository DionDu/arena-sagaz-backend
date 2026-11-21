"""🔒 A MIGRACAO 0040 CORRESPONDE AO `data-model.md` §3 DA SPEC 012 (T067).

POR QUE ESTE CADEADO EXISTE
---------------------------
O dono valida o `data-model.md`, e nao o codigo do Alembic (a folha de aval da
spec 012, 14/11/2026, §8zzzz17). A garantia de que a migracao diz o que o
documento prometeu precisa ser MECANICA: um numero trocado, um codigo com uma
letra a mais ou uma direcao invertida chegariam ao banco sem nada acusar - e um
`nu_feito` nunca muda de significado depois de gravado.

O irmao `test_migracao_quatro_bate_com_data_model.py` faz o mesmo para o schema
do Quatro. Este le as duas tabelas da §3 do documento do xadrez:

  · §3.1, os tipos: `| 60 | `xadrez_espia_comer` | Coma com a espia | `xadrez` |`
    (numero, codigo, nome e jogo, linha a linha);
  · §3.2, as medidas: as linhas agrupadas (`| 60-64 | `pecas_comidas_peao` ·
    `_cavalo` · ... |`) sao abertas uma a uma, e cada medida e comparada em
    numero, codigo, unidade e direcao. A procedencia e o jogo sao os que o
    documento declara para todas (`tabuleiro`, `xadrez`).

⛔ Nunca "ajuste o teste para passar": se ele falhar, ou a migracao divergiu do
que o dono validou (conserta-se a migracao), ou o modelo precisa mudar - e isso
e decisao do dono, com o `data-model.md` mudando primeiro.

⚠️ Pula com motivo quando o frontend nao esta no disco ao lado (o documento
mora la). Os cadeados que nao dependem dele (o 4, que compara a migracao com o
manifesto, e os de migracao aditiva) continuam rodando.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unitarios.leitura_de_migracao import sql_do_upgrade

RAIZ = Path(__file__).resolve().parents[2]
DATA_MODEL = (
    RAIZ.parent / "arena-sagaz-frontend" / "specs" / "012-jogo-xadrez" / "data-model.md"
)
MIGRACAO = RAIZ / "migrations" / "versions" / "0040_desafio_xadrez.py"


@pytest.fixture(scope="module")
def secao_3() -> str:
    """So a §3 do documento (as dimensoes do Desafio do Dia), ate a §4."""
    if not DATA_MODEL.is_file():
        pytest.skip(f"o data-model da spec 012 nao esta no disco: {DATA_MODEL}")
    texto = DATA_MODEL.read_text(encoding="utf-8")
    inicio = texto.index("## 3. Dimens")
    return texto[inicio : texto.index("## 4. ", inicio)]


def _linhas_de_tabela(trecho: str) -> list[list[str]]:
    """As celulas de cada linha de tabela Markdown que comeca por um numero.

    `| 60-64 | `a` · `_b` | `contagem` |` -> `['60-64', '`a` · `_b`', '`contagem`']`.
    O cabecalho e o separador (`|---|`) nao comecam por numero e ficam de fora.
    """
    linhas = []
    for linha in trecho.splitlines():
        if re.match(r"^\|\s*\d", linha):
            # `strip("|")` tira as barras das pontas; o `split` separa as celulas.
            linhas.append([c.strip() for c in linha.strip().strip("|").split("|")])
    return linhas


def _codigos(celula: str) -> list[str]:
    """Os codigos entre crases de uma celula, abrindo os sufixos.

    `pecas_comidas_peao` · `_cavalo` vira `pecas_comidas_peao`,
    `pecas_comidas_cavalo`: o sufixo troca a ULTIMA parte do codigo anterior.
    """
    codigos: list[str] = []
    for bruto in re.findall(r"`([a-z_]+)`", celula):
        if bruto.startswith("_"):
            base = codigos[-1].rsplit("_", 1)[0]
            codigos.append(base + bruto)
        else:
            codigos.append(bruto)
    return codigos


def tipos_do_documento(secao: str) -> dict[int, tuple[str, str, str]]:
    """`{numero: (codigo, nome, jogo)}` da tabela da §3.1."""
    trecho = secao[secao.index("### 3.1") : secao.index("### 3.2")]
    return {
        int(c[0]): (_codigos(c[1])[0], c[2], _codigos(c[3])[0])
        for c in _linhas_de_tabela(trecho)
    }


def medidas_do_documento(secao: str) -> dict[int, tuple[str, str, str]]:
    """`{numero: (codigo, unidade, direcao)}` da tabela da §3.2, aberta."""
    trecho = secao[secao.index("### 3.2") : secao.index("### 3.3")]
    medidas: dict[int, tuple[str, str, str]] = {}
    for celulas in _linhas_de_tabela(trecho):
        # "60-64" ou "70": o primeiro e o ultimo numero da linha.
        primeiro, _, ultimo = celulas[0].partition("-")
        numeros = range(int(primeiro), int(ultimo or primeiro) + 1)
        codigos = _codigos(celulas[1])
        assert len(codigos) == len(numeros), f"a linha {celulas[0]} nao fecha: {codigos}"
        unidade, direcao = _codigos(celulas[2])[0], _codigos(celulas[3])[0]
        for numero, codigo in zip(numeros, codigos):
            medidas[numero] = (codigo, unidade, direcao)
    return medidas


def _tuplas_do_insert(tabela: str) -> list[tuple[str, ...]]:
    """As tuplas do `VALUES` do INSERT da [tabela] na 0040, como texto."""
    sql = sql_do_upgrade(MIGRACAO)
    inicio = sql.index(f"INSERT INTO desafio.{tabela}")
    fim = sql.find("INSERT INTO", inicio + 1)
    trecho = sql[inicio : fim if fim != -1 else len(sql)]
    trecho = trecho[trecho.index("VALUES") :]
    # Cada tupla: `(60, 'codigo', 'Nome', ...)`; os textos vem sem as aspas.
    return [
        tuple(v.strip().strip("'") for v in re.split(r",\s*", corpo))
        for corpo in re.findall(r"\(([^()]*)\)", trecho)
    ]


def test_os_tipos_da_migracao_sao_os_do_documento(secao_3):
    da_migracao = {
        int(n): (codigo, nome, jogo) for n, codigo, nome, jogo in _tuplas_do_insert(
            "tb901_tipo_desafio"
        )
    }
    do_documento = tipos_do_documento(secao_3)
    assert len(do_documento) == 11, do_documento
    assert da_migracao == do_documento


def test_as_medidas_da_migracao_sao_as_do_documento(secao_3):
    da_migracao = {}
    for n, codigo, _nome, unidade, direcao, procedencia, jogo in _tuplas_do_insert(
        "tb902_catalogo_feito"
    ):
        # O documento declara as duas para todas (o paragrafo abaixo da tabela).
        assert (procedencia, jogo) == ("tabuleiro", "xadrez"), codigo
        da_migracao[int(n)] = (codigo, unidade, direcao)
    do_documento = medidas_do_documento(secao_3)
    assert len(do_documento) == 19, do_documento
    assert da_migracao == do_documento


def test_a_leitura_do_documento_abre_os_sufixos():
    """O controle da leitura: sem ele, um `_codigos` que nao abrisse os
    sufixos faria os dois lados vazios e o caso de cima verde."""
    assert _codigos("`pecas_comidas_peao` · `_cavalo` · `_dama`") == [
        "pecas_comidas_peao",
        "pecas_comidas_cavalo",
        "pecas_comidas_dama",
    ]


def test_a_migracao_segue_a_0039_e_tem_id_curto():
    texto = MIGRACAO.read_text(encoding="utf-8")
    assert 'revision: str = "0040_desafio_xadrez"' in texto
    assert 'down_revision: Union[str, None] = "0039_schema_jogo_xadrez"' in texto
    # O Alembic guarda o id numa coluna de 32 caracteres (memoria do projeto).
    assert len("0040_desafio_xadrez") <= 32
