"""As regras puras do registro do aparelho (T118): versão, aparelho, fuso, espaço.

Funções sem banco nem HTTP, testadas com números escolhidos a dedo. Os casos de
limite usam valores que NÃO fecham redondo de propósito: um caso cujo número
cai exatamente no limite não separa `>` de `>=`.
"""
from __future__ import annotations

import uuid

import pytest

from api.aparelhos.regras import (
    ESPACO_DA_LINHA_LEGADA,
    LARGURA_DA_VERSAO,
    PASTAS_DO_ESPACO,
    chave_da_versao,
    detalhe_do_espaco_para_guardar,
    id_aparelho_do_cabecalho,
    id_aparelho_legado,
    offset_do_cabecalho,
    versao_maior,
)

# ═══════════════════════════════════════════════════════════════════════════
# A versão
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "texto, chave",
    [
        ("1.3.1", (1, 3, 1, 0)),
        ("1.4.0+17", (1, 4, 0, 17)),
        ("1.3", (1, 3, 0, 0)),
        ("2", (2, 0, 0, 0)),
        ("1.10.0", (1, 10, 0, 0)),
    ],
)
def test_a_versao_vira_quatro_numeros(texto, chave):
    assert chave_da_versao(texto) == chave


@pytest.mark.parametrize(
    "texto",
    [None, "", "dev", "1.4.0-beta", "v1.4.0", "1.2.3.4", "1..3", "1.3+", "1.3.1+16+2"],
)
def test_o_que_nao_tem_forma_de_versao_nao_se_le(texto):
    assert chave_da_versao(texto) is None


def test_a_versao_mais_larga_que_a_coluna_nao_se_le():
    """20 caracteres é a largura de `co_versao_app`; um a mais não se grava."""
    cabe = "123456.123456.1234+1"
    assert len(cabe) == LARGURA_DA_VERSAO and chave_da_versao(cabe) is not None
    assert chave_da_versao(cabe + "2") is None


@pytest.mark.parametrize(
    "nova, antiga, maior",
    [
        ("1.4.0", "1.3.1", True),
        ("1.3.1", "1.4.0", False),
        ("1.4.0", "1.4.0", False),  # igual não é maior: a linha não muda
        ("1.10.0", "1.9.0", True),  # o texto diria o contrário
        ("1.3.1+17", "1.3.1+16", True),
        ("1.3.1+16", "1.3.1", True),
        ("1.3.0", "1.3", False),  # a mesma versão, escrita de dois jeitos
        ("dev", "1.3.0", False),  # ilegível nunca é maior
        ("1.3.0", "dev", True),  # e perde para qualquer legível
    ],
)
def test_qual_versao_e_maior(nova, antiga, maior):
    assert versao_maior(nova, antiga) is maior


# ═══════════════════════════════════════════════════════════════════════════
# O aparelho
# ═══════════════════════════════════════════════════════════════════════════

PESSOA = "63385354-1e03-44bc-b2a3-82fdb8e34547"


def test_o_espaco_da_linha_legada_nao_muda():
    """⛔ Trocar este valor faria cada aparelho legado aparecer DUAS vezes na
    adoção. Ele é o que o comentário de `regras.py` diz que é."""
    assert ESPACO_DA_LINHA_LEGADA == uuid.uuid5(
        uuid.NAMESPACE_URL, "arena-sagaz:log.tb003_aparelho:legado"
    )
    assert str(ESPACO_DA_LINHA_LEGADA) == "9ff1ea6f-6540-556f-879f-7a48f54bc5c3"


def test_a_linha_legada_e_deterministica_e_versao_5():
    primeira = id_aparelho_legado(PESSOA, "android")
    assert primeira == id_aparelho_legado(PESSOA, "android")
    assert primeira.version == 5


def test_a_linha_legada_nao_depende_da_caixa_do_texto():
    assert id_aparelho_legado(PESSOA.upper(), "ANDROID") == id_aparelho_legado(PESSOA, "android")


def test_a_linha_legada_separa_plataforma_e_pessoa():
    android = id_aparelho_legado(PESSOA, "android")
    assert android != id_aparelho_legado(PESSOA, "ios")
    assert android != id_aparelho_legado("00000000-0000-0000-0000-000000000001", "android")


def test_o_codigo_do_app_e_um_uuid_versao_4():
    codigo = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
    assert id_aparelho_do_cabecalho(codigo) == uuid.UUID(codigo)
    assert id_aparelho_do_cabecalho(f"  {codigo}  ") == uuid.UUID(codigo)


@pytest.mark.parametrize("texto", [None, "", "nao-e-uuid", "3f2b8c1e"])
def test_o_que_nao_e_uuid_vale_como_ausente(texto):
    assert id_aparelho_do_cabecalho(texto) is None


def test_um_uuid_versao_5_nao_escreve_na_linha_legada_de_ninguem():
    """⚠️ Sem esta recusa, quem mandasse o uuid5 de outra pessoa no cabeçalho
    escreveria no aparelho legado dela."""
    legada = str(id_aparelho_legado(PESSOA, "android"))
    assert id_aparelho_do_cabecalho(legada) is None
    assert id_aparelho_do_cabecalho(str(uuid.uuid1())) is None


# ═══════════════════════════════════════════════════════════════════════════
# O fuso
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "texto, minutos",
    [("-180", -180), ("0", 0), (" 330 ", 330), ("840", 840), ("-840", -840)],
)
def test_o_fuso_do_cabecalho(texto, minutos):
    assert offset_do_cabecalho(texto) == minutos


@pytest.mark.parametrize("texto", [None, "", "x", "-180.5", "841", "-841"])
def test_o_fuso_que_nao_se_le_vale_como_ausente(texto):
    assert offset_do_cabecalho(texto) is None


def test_o_fuso_e_em_MINUTOS_e_nao_em_horas():
    """`-3` se lê, e são três minutos - não o Brasil. É o engano que um app
    escrito às pressas cometeria, e o servidor não tem como adivinhá-lo."""
    assert offset_do_cabecalho("-3") == -3


# ═══════════════════════════════════════════════════════════════════════════
# O espaço
# ═══════════════════════════════════════════════════════════════════════════

LIMITES = {"android": 150, "ios": 300}
DETALHE = {"cache": 509600, "tmp": 0, "suporte": 6900, "banco": 332, "base_damas": 0, "outros": 12}


def _decide(total_kb, plataforma="android", detalhe=DETALHE, limites=LIMITES):
    return detalhe_do_espaco_para_guardar(
        total_kb=total_kb, detalhe=detalhe, plataforma=plataforma, limites_mb=limites
    )


def test_um_kb_acima_do_limite_guarda_e_o_limite_exato_nao():
    """150 MB = 153.600 KB. O limite exato ainda é normal; um KB acima, não."""
    assert _decide(150 * 1024) is None
    assert _decide(150 * 1024 + 1) == DETALHE


def test_cada_plataforma_le_o_seu_limite():
    """Os mesmos 200,3 MB: acima no Android (150), abaixo no iOS (300)."""
    total = 205_107  # 200,3 MB em KB - um número que não fecha redondo
    assert _decide(total, "android") == DETALHE
    assert _decide(total, "ios") is None
    assert _decide(300 * 1024 + 1, "ios") == DETALHE


def test_plataforma_sem_limite_nunca_guarda():
    """O `web` do desenvolvimento não tem limite."""
    assert _decide(10**9, "web") is None


def test_sem_total_ou_sem_detalhe_nao_ha_o_que_guardar():
    assert _decide(None) is None
    assert _decide(10**9, detalhe=None) is None
    assert _decide(10**9, detalhe={}) is None


def test_a_pasta_desconhecida_e_descartada_e_nao_recusada():
    """Um app mais novo que meça uma pasta a mais não perde o dia inteiro."""
    detalhe = {"cache": 1, "pasta_nova": 2, "tmp": -5}
    assert _decide(10**9, detalhe=detalhe) == {"cache": 1}


def test_o_vocabulario_e_o_do_data_model():
    """As seis pastas de `data-model.md` §4.2."""
    assert PASTAS_DO_ESPACO == set(DETALHE)
