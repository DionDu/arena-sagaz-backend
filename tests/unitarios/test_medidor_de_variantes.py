"""T049f - cadeados do script que MEDE variantes antes de elas serem publicadas.

⚠️ **O script nao roda aqui, e nao pode rodar.** Uma rodada de damas custa **80
minutos** (medido em 12/09/2026); um cadeado que ninguem aguenta rodar nao e
cadeado, e vira o teste que todo mundo pula com `-k`.

O que estes casos guardam e o que o script tem de **barato e quebravel**:

1. **A tabela de candidatas.** Uma candidata com o parametro mal escrito
   (`{'peca': 3}` no lugar de `{'pecas': 3}`) hoje so falha **depois** de o
   gerador rodar dez minutos, e o erro sai no meio de um relatorio longo.
2. **A selecao pelo alvo da linha de comando**, que passou a aceitar um tipo em
   12/09/2026 - e um `or` na ordem errada faria `damas` medir tudo, ou
   `damas_coroar` medir os dois tipos de damas, sem erro nenhum.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from job import editorial as editorial_mod
from job.tipos_de_desafio import receita_de


def _carregar_o_script():
    """Importa `scripts/medir_variantes_do_editorial.py` como modulo.

    ⚠️ `scripts/` **nao e pacote** (nao tem `__init__.py`), entao `import` comum
    nao o acha. `spec_from_file_location` carrega um arquivo solto pelo caminho.

    ⛔ E o `sys.modules[nome] = modulo` **antes** do `exec_module` nao e zelo: um
    `@dataclass(slots=True)` procura a propria classe em `sys.modules` enquanto o
    modulo ainda esta sendo executado, e sem esta linha o carregamento estoura
    com `'NoneType' object has no attribute '__dict__'`.
    """
    caminho = Path(__file__).parents[2] / "scripts" / "medir_variantes_do_editorial.py"
    spec = importlib.util.spec_from_file_location("medir_variantes", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["medir_variantes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


MEDIDOR = _carregar_o_script()


# ═══════════════════════════════════════════════════════════════════════════
# 1. A tabela de candidatas
# ═══════════════════════════════════════════════════════════════════════════


def _todas_as_candidatas():
    """(tipo, candidata) de tudo o que esta em `A_MEDIR`, para parametrizar."""
    return [
        pytest.param(co_tipo, candidata, id=f"{co_tipo}-{dict(candidata.parametros)}")
        for co_tipo, candidatas in MEDIDOR.A_MEDIR.items()
        for candidata in candidatas
    ]


@pytest.mark.parametrize("co_tipo, candidata", _todas_as_candidatas())
def test_TODA_candidata_monta_chegada_e_frase(co_tipo, candidata):
    """Parametro mal escrito tem de estourar AQUI, e nao depois de 10 minutos.

    ⚠️ O `montar` da receita le as chaves pelo nome (`p["pecas"]`), entao um erro
    de digitacao vira `KeyError` - e hoje ele so aparece quando o gerador ja
    encontrou uma posicao, no meio de um relatorio de uma hora.
    """
    receita = receita_de(co_tipo)
    parametros = dict(candidata.parametros)

    # ⚠️ **`acima_do_guloso` nao monta sozinho, e nao e defeito:** o alvo dele sai
    # da POSICAO (decisao do dono, 11/09/2026), e so vira numero depois que o
    # gerador mede o guloso naquele tabuleiro. Aqui basta um valor qualquer - o
    # que se testa e se as chaves casam, nao quanto vale o alvo.
    if editorial_mod.alvo_sai_da_posicao(parametros):
        parametros = editorial_mod.parametros_efetivos(parametros, guloso=3)

    js_chegada = receita.montar(parametros)
    assert js_chegada["janela"], "a chegada saiu sem janela"
    assert js_chegada["clausulas"], "a chegada saiu sem clausula nenhuma"

    # A frase tem de montar tambem: e ela que vira o enunciado na tela.
    receita.valores_da_frase(parametros, "cacau")


def test_a_JANELA_da_candidata_cabe_no_TETO_com_que_ela_sera_medida():
    """⛔ Janela e teto sao o MESMO limite, e medir com eles em desacordo mente.

    ⚠️ As tres unidades ja se confundiram nesta feature, entao, de novo:
    `lances_do_jogador: n` conta os lances **da pessoa**; o teto conta
    **meios-lances** (os dois lados). Nas damas a alternancia e estrita, entao
    `n` lances do jogador sao `2n` meios-lances.

    ⛔ Uma candidata que peca 8 lances do jogador sendo medida com teto 12
    descreveria uma execucao impossivel: o gerador pararia de procurar em 12
    meios-lances (6 lances), e a janela de 8 nunca seria exercida.

    ⚠️ **E este cadeado ja mordeu no dia em que nasceu** (12/09/2026): a primeira
    versao de `{damas: 2, lances: 10, teto: 16}` pedia 20 meios-lances de janela
    com 16 de teto. A medicao teria rodado, saido bonita, e descrito uma execucao
    que o gerador nao faz.

    ⛔ **So cobra de quem escreve teto PROPRIO, e isso e deliberado.** As
    variantes que herdam o teto do tipo podem prometer janela maior do que o
    gerador alcanca - `{damas: 2, lances: 8}` esta no ar assim, com 16
    meios-lances de janela contra 12 de teto, e ⚠️ **e por isso que as janelas de
    8 e de 10 medem identico**: nenhuma das duas e exercida, a folga so esta
    escrita na frase. Quem acrescenta um teto proprio esta justamente
    investigando esse limite, e ai a conta tem de fechar.
    """
    for co_tipo, candidatas in MEDIDOR.A_MEDIR.items():
        receita = receita_de(co_tipo)
        if receita.co_jogo != "damas":
            continue  # so nas damas a alternancia e estrita
        publicacao = editorial_mod.publicacao_de(co_tipo, 0)
        for candidata in candidatas:
            n = candidata.parametros.get("lances")
            if n is None:
                continue
            teto = (
                candidata.nu_maximo_de_meios_lances
                or publicacao.nu_maximo_de_meios_lances
            )
            # ⚠️ O que interessa e a candidata **que pede mais do que o teto
            # alcanca**: ela seria medida por um limite que a frase nao usa.
            if n * 2 > teto:
                assert candidata.nu_maximo_de_meios_lances is None, (
                    f"{co_tipo} {dict(candidata.parametros)} pede {n} lances do "
                    f"jogador ({n * 2} meios-lances) com teto PROPRIO de {teto}: "
                    "quem escreve um teto proprio tem de escreve-lo suficiente"
                )


# ═══════════════════════════════════════════════════════════════════════════
# 2. A selecao pelo alvo da linha de comando
# ═══════════════════════════════════════════════════════════════════════════


def test_o_alvo_TODOS_mede_tudo():
    assert MEDIDOR.tipos_do_alvo("todos") == list(MEDIDOR.A_MEDIR)


def test_o_alvo_por_JOGO_mede_os_tipos_daquele_jogo():
    escolhidos = MEDIDOR.tipos_do_alvo("damas")

    assert escolhidos, "nenhum tipo de damas foi selecionado"
    assert all(receita_de(t).co_jogo == "damas" for t in escolhidos)
    # ⛔ E nao pode ter vazado o outro jogo - o `or` da selecao ja tem tres ramos.
    assert not any(receita_de(t).co_jogo == "pontinhos" for t in escolhidos)


def test_o_alvo_por_TIPO_mede_SO_aquele_tipo():
    """⚠️ Este e o caso novo de 12/09, e o que economiza 80 minutos por rodada."""
    assert MEDIDOR.tipos_do_alvo("damas_capturar_multipla") == [
        "damas_capturar_multipla"
    ]


def test_alvo_desconhecido_nao_mede_nada():
    """⛔ Lista vazia, e nao "mede tudo por garantia" - medir sem ter sido pedido
    e uma hora de maquina que ninguem autorizou."""
    assert MEDIDOR.tipos_do_alvo("damas_coroar_errado") == []
    assert MEDIDOR.principal(["damas_coroar_errado"]) == 2
