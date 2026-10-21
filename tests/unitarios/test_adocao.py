"""A adoção de uma versão e a frequência do jogo novo (`job/adocao.py`, T119 da spec 010).

O que este arquivo trava:

  1. **os limiares exatos** ratificados pelo dono na T003 (40 / 60 / 80%), cada
     um dos dois lados - um aparelho abaixo e o limiar cravado -, com amostras
     que não fecham em número redondo (715 aparelhos, e não 100 nem 1000);
  2. **os números da tabela**, escritos aqui por extenso, e não lidos das
     constantes do módulo (um teste que lê a constante que devia conferir passa
     com qualquer valor);
  3. **a conta**: o aparelho entra uma vez, com a MAIOR versão da janela; a
     versão se compara por números; a linha ilegível conta no denominador e
     nunca apaga a legível; as linhas legadas (uuid5) contam como as outras;
  4. **a janela**: os 7 dias fechados antes de hoje.
"""

from __future__ import annotations

import uuid
from datetime import date
from fractions import Fraction

import pytest

from api.aparelhos.regras import id_aparelho_legado
from job.adocao import (
    JANELA_DA_ADOCAO_DIAS,
    LIMIAR_RODIZIO_PLENO,
    LIMIAR_UM_EM_QUATRO,
    LIMIAR_UM_EM_TRES,
    UM_DIA_EM_ABAIXO_DE_40,
    UM_DIA_EM_DE_40_A_60,
    UM_DIA_EM_DE_60_A_80,
    Adocao,
    Frequencia,
    frequencia_do_jogo_novo,
    janela_da_adocao,
    medir_adocao,
)

#: A versão mínima dos casos (a do Quatro em Linha).
MINIMA = "1.4.0"

#: O tamanho da amostra dos limiares: 715 = 5 × 11 × 13. É múltiplo de 5, então
#: 40%, 60% e 80% caem num número inteiro de aparelhos (286, 429, 572), e um
#: aparelho a menos dá 39,86%, 59,86% e 79,86% - os "39,9 / 59,9 / 79,9" da
#: tarefa, sem fechar redondo.
TOTAL = 715


def _amostra(adotaram: int, total: int) -> list[tuple[uuid.UUID, str]]:
    """Uma amostra como a leitura de `tb004` a entregaria, com [adotaram] de [total].

    Para que os limiares não passem por acaso numa amostra ingênua, ela tem as
    três coisas que a de verdade tem:

      * **linhas legadas**: um terço dos aparelhos é `uuid5` (app 1.3, sem o
        código de instalação), e a outra parte é `uuid4`;
      * **várias linhas por aparelho**: cada aparelho aparece em mais de um dia;
      * **a versão subindo no meio da janela**: quem adotou foi visto ANTES com
        a 1.3.1, e quem não adotou foi visto com versões abaixo da mínima.
    """
    linhas: list[tuple[uuid.UUID, str]] = []
    for i in range(total):
        # Um em cada três aparelhos é a linha legada de uma conta Android.
        if i % 3 == 0:
            aparelho = id_aparelho_legado(str(uuid.UUID(int=i + 1)), "android")
        else:
            aparelho = uuid.UUID(int=(1 << 120) + i, version=4)
        if i < adotaram:
            # Viu a 1.3.1 num dia e a 1.4.0+N noutro: conta como adotou.
            linhas.append((aparelho, "1.3.1"))
            linhas.append((aparelho, f"1.4.0+{17 + i % 5}"))
        else:
            # Ficou abaixo da mínima a janela inteira, em dois dias.
            linhas.append((aparelho, "1.3.1"))
            linhas.append((aparelho, "1.3.1+16"))
    return linhas


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os limiares exatos
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("adotaram", "um_dia_em"),
    [
        (0, 6),  # ninguém
        (285, 6),  # 39,86% - um aparelho abaixo dos 40
        (286, 4),  # 40% cravados: o limite inferior entra na faixa
        (428, 4),  # 59,86%
        (429, 3),  # 60%
        (571, 3),  # 79,86%
        (572, None),  # 80%: rodízio pleno
        (715, None),  # todos
    ],
)
def test_cada_limiar_dos_dois_lados(adotaram, um_dia_em):
    adocao = medir_adocao(_amostra(adotaram, TOTAL), MINIMA)

    # Os dois números, e não só a fração: é o que vai para o log da execução.
    assert adocao.aparelhos == TOTAL
    assert adocao.adotaram == adotaram
    assert adocao.fracao == Fraction(adotaram, TOTAL)
    assert frequencia_do_jogo_novo(adocao) == Frequencia(um_dia_em=um_dia_em)


@pytest.mark.parametrize(
    ("adotaram", "total", "um_dia_em"),
    [
        # 39,9% e 40% numa amostra de outro tamanho, para o limiar não depender
        # do 715: 399 de 1.000 e 2 de 5.
        (399, 1000, 6),
        (2, 5, 4),
        (599, 1000, 4),
        (3, 5, 3),
        (799, 1000, 3),
        (4, 5, None),
    ],
)
def test_os_limiares_valem_em_qualquer_tamanho_de_amostra(adotaram, total, um_dia_em):
    adocao = Adocao(versao_minima=MINIMA, aparelhos=total, adotaram=adotaram)
    assert frequencia_do_jogo_novo(adocao).um_dia_em == um_dia_em


def test_os_numeros_da_tabela_sao_os_ratificados_na_t003():
    """Escritos por extenso: mudar a tabela é decisão do dono, e não passa calado."""
    assert LIMIAR_UM_EM_QUATRO == Fraction(2, 5)
    assert LIMIAR_UM_EM_TRES == Fraction(3, 5)
    assert LIMIAR_RODIZIO_PLENO == Fraction(4, 5)
    assert UM_DIA_EM_ABAIXO_DE_40 == 6
    assert UM_DIA_EM_DE_40_A_60 == 4
    assert UM_DIA_EM_DE_60_A_80 == 3


def test_o_rodizio_pleno_e_none_e_nao_um_numero():
    assert Frequencia(um_dia_em=None).rodizio_pleno is True
    assert Frequencia(um_dia_em=3).rodizio_pleno is False


# ═══════════════════════════════════════════════════════════════════════════
# 2. A conta
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_amostra_a_adocao_e_zero_e_o_jogo_novo_fica_raro():
    adocao = medir_adocao([], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (0, 0)
    assert adocao.fracao == 0
    assert frequencia_do_jogo_novo(adocao).um_dia_em == 6


@pytest.mark.parametrize(
    "linhas",
    [
        [("a", "1.3.1"), ("a", "1.4.0")],  # atualizou no meio da janela
        [("a", "1.4.0"), ("a", "1.3.1")],  # a ordem das linhas não importa
    ],
)
def test_o_aparelho_entra_uma_vez_com_a_maior_versao_da_janela(linhas):
    adocao = medir_adocao(linhas, MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (1, 1)


@pytest.mark.parametrize(
    ("minima", "versao", "alcanca"),
    [
        ("1.4.0", "1.4.0", True),  # igual alcança
        ("1.4.0", "1.4", True),  # o que falta vale zero
        ("1.4.0", "1.4.0+17", True),  # o build não atrapalha
        ("1.4.0", "1.3.99", False),
        ("1.9.0", "1.10.0", True),  # ⚠️ o texto diria que não
        ("1.10.0", "1.9.5", False),  # ⚠️ o texto diria que sim
        ("1.4.0", "2.0.0", True),
    ],
)
def test_a_versao_se_compara_por_numeros(minima, versao, alcanca):
    adocao = medir_adocao([("a", versao)], minima)
    assert adocao.adotaram == (1 if alcanca else 0)


def test_versao_ilegivel_conta_no_denominador_e_nao_alcanca():
    adocao = medir_adocao([("a", "dev"), ("b", None), ("c", "1.4.0")], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (3, 1)


@pytest.mark.parametrize(
    "linhas",
    [
        [("a", "1.4.0"), ("a", "dev")],  # a ilegível depois não apaga a legível
        [("a", "dev"), ("a", "1.4.0")],  # e a legível depois vence a ilegível
        [("a", None), ("a", "1.4.0"), ("a", "1.3.1")],
    ],
)
def test_a_linha_ilegivel_nunca_rebaixa_o_aparelho(linhas):
    adocao = medir_adocao(linhas, MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (1, 1)


def test_as_linhas_legadas_contam_como_as_outras():
    """O app 1.3 é a parte da amostra que segura o jogo novo; sem ela, 100% no dia 1."""
    legado = id_aparelho_legado(str(uuid.uuid4()), "ios")
    novo = uuid.uuid4()
    adocao = medir_adocao([(legado, "1.3.1"), (novo, "1.4.0")], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (2, 1)
    assert adocao.fracao == Fraction(1, 2)


def test_dois_aparelhos_da_mesma_pessoa_contam_duas_vezes():
    """Um Android e um iPad: o desafio abre (ou não) em cada um."""
    pessoa = str(uuid.uuid4())
    android = id_aparelho_legado(pessoa, "android")
    ipad = id_aparelho_legado(pessoa, "ios")
    adocao = medir_adocao([(android, "1.4.0"), (ipad, "1.3.1")], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (2, 1)


@pytest.mark.parametrize("minima", ["", "dev", "1.4.0-beta", None])
def test_versao_minima_ilegivel_e_defeito_do_catalogo(minima):
    with pytest.raises(ValueError):
        medir_adocao([("a", "1.4.0")], minima)


def test_a_adocao_guarda_a_versao_pedida():
    assert medir_adocao([], "1.4.0").versao_minima == "1.4.0"


# ═══════════════════════════════════════════════════════════════════════════
# 3. A janela
# ═══════════════════════════════════════════════════════════════════════════


def test_a_janela_sao_os_sete_dias_fechados_antes_de_hoje():
    assert JANELA_DA_ADOCAO_DIAS == 7
    assert janela_da_adocao(date(2026, 10, 21)) == (date(2026, 10, 14), date(2026, 10, 20))


def test_a_janela_atravessa_a_virada_do_ano():
    assert janela_da_adocao(date(2027, 1, 3)) == (date(2026, 12, 27), date(2027, 1, 2))
