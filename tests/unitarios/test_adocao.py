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
    UM_DIA_EM_NO_RODIZIO_PLENO,
    NAO_APARECE,
    PASSO_DOS_DIAS,
    Adocao,
    Frequencia,
    dia_do_jogo_novo,
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
        (0, None),  # ninguém: o jogo novo não aparece (T120)
        (1, 6),  # basta um aparelho para a faixa de baixo valer
        (285, 6),  # 39,86% - um aparelho abaixo dos 40
        (286, 4),  # 40% cravados: o limite inferior entra na faixa
        (428, 4),  # 59,86%
        (429, 3),  # 60%
        (571, 3),  # 79,86%
        (572, 3),  # 80%: rodízio pleno, 1 em 3
        (715, 3),  # todos
    ],
)
def test_cada_limiar_dos_dois_lados(adotaram, um_dia_em):
    adocao = medir_adocao(_amostra(adotaram, TOTAL), MINIMA)

    # Os dois números, e não só a fração: é o que vai para o log da execução.
    assert adocao.aparelhos == TOTAL
    assert adocao.adotaram == adotaram
    assert adocao.fracao == Fraction(adotaram, TOTAL)
    frequencia = frequencia_do_jogo_novo(adocao)
    assert frequencia.um_dia_em == um_dia_em
    # O pleno é a faixa de cima, e só ela: 571 (79,86%) ainda não é.
    assert frequencia.rodizio_pleno is (adotaram >= 572)


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
        (4, 5, 3),
    ],
)
def test_os_limiares_valem_em_qualquer_tamanho_de_amostra(adotaram, total, um_dia_em):
    adocao = Adocao(versao_minima=MINIMA, aparelhos=total, adotaram=adotaram)
    assert frequencia_do_jogo_novo(adocao).um_dia_em == um_dia_em
    assert frequencia_do_jogo_novo(adocao).rodizio_pleno is (adotaram * 5 >= total * 4)


def test_os_numeros_da_tabela_sao_os_ratificados_na_t003():
    """Escritos por extenso: mudar a tabela é decisão do dono, e não passa calado."""
    assert LIMIAR_UM_EM_QUATRO == Fraction(2, 5)
    assert LIMIAR_UM_EM_TRES == Fraction(3, 5)
    assert LIMIAR_RODIZIO_PLENO == Fraction(4, 5)
    assert UM_DIA_EM_ABAIXO_DE_40 == 6
    assert UM_DIA_EM_DE_40_A_60 == 4
    assert UM_DIA_EM_DE_60_A_80 == 3
    assert UM_DIA_EM_NO_RODIZIO_PLENO == 3


def test_none_quer_dizer_que_o_jogo_novo_nao_aparece():
    assert NAO_APARECE == Frequencia(um_dia_em=None)
    assert NAO_APARECE.aparece is False
    assert NAO_APARECE.rodizio_pleno is False
    assert Frequencia(um_dia_em=6).aparece is True


def test_a_faixa_em_palavras_para_o_log():
    assert NAO_APARECE.descrever() == "não aparece"
    assert Frequencia(um_dia_em=6).descrever() == "1 dia em 6"
    assert (
        Frequencia(um_dia_em=3, rodizio_pleno=True).descrever()
        == "rodízio pleno (1 dia em 3)"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2. A conta
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_amostra_a_adocao_e_zero_e_o_jogo_novo_nao_aparece():
    adocao = medir_adocao([], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (0, 0)
    assert adocao.fracao == 0
    assert frequencia_do_jogo_novo(adocao) == NAO_APARECE


def test_com_aparelhos_e_nenhum_na_versao_o_jogo_novo_nao_aparece():
    """O dia em que o backend vai ao ar antes do app chegar às lojas."""
    adocao = medir_adocao([("a", "1.3.1"), ("b", "1.3.1+16")], MINIMA)
    assert (adocao.aparelhos, adocao.adotaram) == (2, 0)
    assert frequencia_do_jogo_novo(adocao) == NAO_APARECE


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


# ═══════════════════════════════════════════════════════════════════════════
# 4. Quais dias são do jogo novo (T120)
# ═══════════════════════════════════════════════════════════════════════════

#: Dez anos de dias, para as contagens.
DEZ_ANOS = range(3650)


def _dias(frequencia: Frequencia, *, deslocamento: float = 0.0) -> list[int]:
    return [d for d in DEZ_ANOS if dia_do_jogo_novo(d, frequencia, deslocamento=deslocamento)]


def test_o_passo_e_a_parte_fracionaria_da_razao_aurea():
    import math

    assert PASSO_DOS_DIAS == (math.sqrt(5) - 1) / 2


@pytest.mark.parametrize("n", [6, 4, 3])
def test_um_dia_em_n_e_um_dia_em_n(n):
    """Em dez anos, a fração dos dias fica a menos de 0,2 ponto de 1/N."""
    dias = _dias(Frequencia(um_dia_em=n))
    assert abs(len(dias) / len(DEZ_ANOS) - 1 / n) < 0.002


@pytest.mark.parametrize("n", [6, 4, 3])
def test_dois_dias_seguidos_nunca_saem(n):
    dias = _dias(Frequencia(um_dia_em=n))
    assert min(b - a for a, b in zip(dias, dias[1:])) >= 2


@pytest.mark.parametrize("n", [6, 4, 3])
def test_o_jogo_novo_toma_dias_pares_e_impares_por_igual(n):
    """⚠️ Com `dias % N == 0` (N par) ele tomaria SÓ os dias de um jogo antigo."""
    dias = _dias(Frequencia(um_dia_em=n))
    pares = sum(1 for d in dias if d % 2 == 0)
    assert abs(pares / len(dias) - 0.5) < 0.02


@pytest.mark.parametrize("n", [6, 4, 3])
@pytest.mark.parametrize(("paridade", "tipos"), [(0, 7), (1, 4), (1, 16)])
def test_nenhuma_vez_do_rodizio_de_tipos_fica_de_fora(n, paridade, tipos):
    """O travamento em fase de 10/09/2026, pelo caminho do jogo novo.

    O tipo de um jogo antigo é `(dias // 2) % tipos`; se os dias tomados caíssem
    sempre no mesmo resto, aquele tipo perderia todas as vezes. 7 é o Pontinhos,
    4 os tipos das damas e 16 os tipos × modalidades delas. Nenhum resto pode
    perder mais que o dobro de outro.
    """
    from collections import Counter

    tomados = Counter(
        (d // 2) % tipos for d in _dias(Frequencia(um_dia_em=n)) if d % 2 == paridade
    )
    assert len(tomados) == tipos
    assert max(tomados.values()) < 2 * min(tomados.values())


def test_quem_nao_aparece_nunca_toma_dia():
    assert _dias(NAO_APARECE) == []


def test_a_regra_e_so_da_data_e_da_faixa():
    frequencia = Frequencia(um_dia_em=4)
    assert _dias(frequencia) == _dias(Frequencia(um_dia_em=4))


def test_o_deslocamento_separa_dois_jogos_novos():
    um = set(_dias(Frequencia(um_dia_em=6)))
    outro = set(_dias(Frequencia(um_dia_em=6), deslocamento=0.5))
    assert um and outro
    assert not um & outro
