"""🔒 O manifesto das figuras do Quatro no ar (T152 da spec 010, §8zzzw).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE CADEADO GUARDA
═══════════════════════════════════════════════════════════════════════════

A frase do "Forme a figura" diz qual e a figura (*"Forme um Z..."*): o job
publica o CODIGO no enunciado, e o app o traduz. O app exige o nome de cada
figura no ar nos tres `.arb`, lendo uma copia deste manifesto. Sao tres pontas:

    o editorial    `job/editorial.py` - QUAIS figuras vao ao ar
    ESTE ARQUIVO   o manifesto bate com o editorial, a copia do app e igual, e o
                   enunciado de toda figura leva o codigo dela
    o aplicativo   `nome_da_figura_do_quatro_test.dart` - o nome de cada uma nos
                   tres idiomas (⛔ o cadeado do nome NAO mora aqui: travar o job
                   impediria publicar a figura antes da versao nova)
"""

from __future__ import annotations

import json

import pytest

from job import editorial as editorial_mod
from job import figuras_quatro as fq
from job.tipos_de_desafio import RECEITAS
from scripts.gerar_figuras_quatro_no_ar import (
    COPIA_DO_APP,
    MANIFESTO,
    conteudo_do_manifesto,
)


def test_o_manifesto_BATE_com_o_editorial() -> None:
    """🔒 Figura promovida ou retirada sem regerar o manifesto reprova aqui.

    ⚠️ A correcao e rodar `scripts/gerar_figuras_quatro_no_ar.py`, que grava o
    manifesto e a copia do app - ⛔ e nao editar o JSON a mao.
    """
    assert MANIFESTO.is_file(), f"o manifesto sumiu: {MANIFESTO}"
    assert MANIFESTO.read_bytes() == conteudo_do_manifesto().encode("utf-8"), (
        "o manifesto envelheceu: rode scripts/gerar_figuras_quatro_no_ar.py"
    )


def test_a_copia_do_app_e_IGUAL_ao_manifesto() -> None:
    """🔒 Os bytes, como os outros contratos copiados."""
    if not COPIA_DO_APP.is_file():
        pytest.skip("o aplicativo nao esta ao lado (CI isolado)")
    assert COPIA_DO_APP.read_bytes() == MANIFESTO.read_bytes(), (
        "as duas copias divergiram - rode scripts/gerar_figuras_quatro_no_ar.py"
    )


def test_as_figuras_no_ar_sao_as_do_EDITORIAL_e_do_catalogo() -> None:
    """As oito de 27/10/2026, todas do catalogo. ⚠️ Nada do que ficou fora do
    ar (o T, o "+", a exclamacao) entra: o app nao precisa nomea-las ainda."""
    no_ar = json.loads(MANIFESTO.read_text(encoding="utf-8"))["co_figuras"]
    assert no_ar == [
        "i", "i_longo", "igual", "igual_sanduiche", "losango", "quadrado", "xis", "z",
    ]
    assert set(no_ar) <= set(fq.FIGURAS_QUATRO)
    assert not {"t", "mais", "exclamacao"} & set(no_ar)
    # 🔒 E a lista sai das variantes, e nao do catalogo inteiro.
    assert list(editorial_mod.codigos_das_figuras_no_ar()) == no_ar


@pytest.mark.parametrize("nome", sorted(fq.FIGURAS_QUATRO))
def test_o_enunciado_leva_o_CODIGO_da_figura(nome: str) -> None:
    """🔒 O app traduz o `codigo_figura` para o nome. ⛔ O codigo, e nao o nome
    pronto: o nome muda com o idioma.

    O codigo e o nome do catalogo, o mesmo da chegada e do desenho - divergindo,
    a frase nomearia uma figura e o desenho mostraria outra.
    """
    parametros = editorial_mod.parametros_efetivos(
        {fq.CHAVE_FIGURA: nome, fq.CHAVE_FOLGA_DA_FIGURA: 1}, encostadas=0, distancia=3
    )
    valores = RECEITAS["quatro_figura"].valores_da_frase(parametros, "tex")
    assert valores[fq.CHAVE_CODIGO_DA_FIGURA] == nome
    assert valores["figura"] == list(fq.FIGURAS_QUATRO[nome].desenho)


def test_o_CODIGO_e_um_identificador_que_vira_nome_de_chave() -> None:
    """O app procura o nome em `desafioNomeFiguraQuatro<Codigo>`: o codigo tem
    de ser minusculas, digitos e `_` (o que vira chave de `.arb` sem surpresa)."""
    import re

    for nome in fq.FIGURAS_QUATRO:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", nome), nome
