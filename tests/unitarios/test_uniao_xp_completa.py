"""🔒 CADEADO 7 — A UNIAO DE XP ESTA COMPLETA (RF-DES-182, T047).

═══════════════════════════════════════════════════════════════════════════
O QUE ELE PEGA
═══════════════════════════════════════════════════════════════════════════

Uma tabela de XP nova que nasca **sem entrar na uniao**. Hoje sao duas
(`partida.tb003_xp_partida` e `desafio_dia.tb004_xp_desafio`); a terceira, quando
vier, precisa entrar na soma **sem que ninguem se lembre** de que ela existe.

⚠️ **A VIEW de uniao nao e entrega desta spec, e o cadeado e assim mesmo.**
Escrito depois da terceira tabela, ele chega tarde por definicao — e a terceira
ja teria ficado de fora de uma soma que ninguem sabia estar incompleta.

═══════════════════════════════════════════════════════════════════════════
⚠️ **NADA A VARRER E FALHA, E NAO SUCESSO**
═══════════════════════════════════════════════════════════════════════════

E a correcao do defeito que este projeto ja pagou quatro vezes: um cadeado que
nao encontra o que conferir e **verde e cego**. Se a varredura das migracoes
voltar vazia, alguma coisa quebrou no leitor — e o teste falha dizendo isso, em
vez de aprovar o silencio.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE AS MIGRACOES, E NAO O CATALOGO DO POSTGRES
═══════════════════════════════════════════════════════════════════════════

O texto de T047 fala em consultar o catalogo. Ele **e** consultado — mas no
outro nivel: `scripts/conferir_migracao_desafio.py` roda contra o banco de
verdade, e o portao T050 o executa.

Este cadeado roda no **CI**, onde nao ha Postgres. Ele le as migracoes com `ast`
— a mesma peca que os outros tres cadeados usam —, e por isso pega a tabela nova
**no commit em que ela e escrita**, e nao no dia em que alguem lembrar de migrar.

E a "conferencia em dois niveis" do projeto: o CI pega cedo, o conferidor pega o
que so o banco sabe.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from api.nucleo.uniao_xp import FONTES, e_fonte_de_xp, faltantes
from tests.unitarios.leitura_de_migracao import sql_da_migracao

RAIZ = Path(__file__).resolve().parents[2]
MIGRACOES = RAIZ / "migrations" / "versions"


def _tabelas_criadas() -> set[str]:
    """Toda tabela que alguma migracao cria, `schema.tabela`.

    ⚠️ **Lido com `ast`**, e nao com um regex sobre o arquivo cru: o SQL das
    migracoes e escrito com f-strings e strings adjacentes, e um regex de texto
    ja perdeu comandos inteiros neste projeto — duas vezes, em 09/09/2026. O
    historico completo esta na docstring de `leitura_de_migracao.py`.
    """
    encontradas: set[str] = set()
    for arquivo in sorted(MIGRACOES.glob("0*.py")):
        sql = sql_da_migracao(arquivo)
        encontradas |= set(re.findall(r"CREATE TABLE\s+(\w+\.\w+)", sql))
    return encontradas


def test_a_varredura_encontra_alguma_coisa():
    """⚠️ **Nada a varrer e FALHA.**

    Um cadeado que nao encontra o que conferir fica verde e cego — e esse defeito
    ja custou quatro fluxos de fim de partida a este projeto. Se as migracoes
    pararem de ser lidas, este caso quebra **antes** dos outros, e a mensagem diz
    onde olhar.
    """
    tabelas = _tabelas_criadas()
    assert tabelas, (
        "a varredura das migracoes nao encontrou tabela NENHUMA. ⛔ Isso nao e "
        f"'esta tudo certo': e o leitor quebrado. Olhe {MIGRACOES} e "
        "`leitura_de_migracao.sql_da_migracao`."
    )
    # E ha, de fato, tabelas de XP entre elas — senao o cadeado abaixo passaria
    # varrendo uma lista vazia.
    assert any(e_fonte_de_xp(t) for t in tabelas), (
        "nenhuma tabela de XP foi encontrada nas migracoes. ⛔ O padrao de nome "
        "mudou, ou o leitor quebrou."
    )


def test_toda_tabela_de_xp_esta_na_uniao():
    """🔒 O cadeado.

    ⚠️ **Se este teste falhar, a resposta NAO e apagar a tabela da lista.** Uma
    tabela de XP que existe e nao esta na uniao significa XP que a pessoa ganhou
    e que a soma nao ve — e a decisao (entra ou nao entra) e consciente, com uma
    linha em `api/nucleo/uniao_xp.py` explicando o porque.
    """
    de_fora = faltantes(_tabelas_criadas())
    assert not de_fora, (
        f"tabela(s) de XP fora da uniao: {sorted(de_fora)}.\n"
        "⚠️ Cada uma delas guarda XP de alguem que a soma total nao enxerga. "
        "Entre em `api/nucleo/uniao_xp.py::FONTES` com o motivo, ou explique ali "
        "por que ela nao conta."
    )


def test_as_duas_fontes_de_hoje_estao_declaradas():
    """A segunda tabela e a razao de o cadeado nascer agora."""
    assert set(FONTES) == {
        "partida.tb003_xp_partida",
        "desafio_dia.tb004_xp_desafio",
    }


def test_as_fontes_declaradas_existem_de_verdade():
    """⚠️ O cadeado tem de valer **nos dois sentidos**.

    Uma fonte declarada que nao existe em migracao nenhuma seria uma linha morta
    — e uma uniao que consultasse uma tabela inexistente falharia em producao, na
    primeira leitura.
    """
    tabelas = _tabelas_criadas()
    inexistentes = set(FONTES) - tabelas
    assert not inexistentes, (
        f"fonte(s) declarada(s) que nenhuma migracao cria: {sorted(inexistentes)}"
    )


@pytest.mark.parametrize(
    "tabela,esperado",
    [
        ("partida.tb003_xp_partida", True),
        ("desafio_dia.tb004_xp_desafio", True),
        # ⚠️ Dimensao NAO e fonte: `tb902_tipo_xp` e a lista de tipos, e nao XP
        # de pessoa nenhuma. O prefixo `tb9` a separa, como no resto do projeto.
        ("partida.tb902_tipo_xp", False),
        ("desafio_dia.tb901_tipo_xp_desafio", False),
        ("conta.tb001_usuario", False),
    ],
)
def test_o_que_conta_como_fonte_de_xp(tabela: str, esperado: bool):
    """A regra do nome, caso a caso — inclusive as armadilhas."""
    assert e_fonte_de_xp(tabela) is esperado


def test_cada_fonte_diz_por_que_existe():
    """⚠️ Uma lista de nomes envelhece; uma lista com motivo, nao.

    Quem ler isto daqui a um ano precisa saber por que `vr_xp` e `NUMERIC` num
    lado e `nu_xp` e inteiro no outro — senao a primeira uniao escrita assumira
    o mesmo nome nos dois e falhara na primeira consulta.
    """
    for nome, fonte in FONTES.items():
        assert fonte.de_por_que.strip(), f"{nome} sem explicacao"
        assert fonte.coluna_xp and fonte.coluna_usuario
