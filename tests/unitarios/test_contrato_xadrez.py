"""T062 da spec 012 - o contrato do xadrez lido do espelho.

O que se trava: que o módulo leia o que o contrato diz (sem número escrito à
mão), que o SHA-256 seja o dos bytes do arquivo, que o Magno só exista com
`magno_no_build: true`, e que o que não serve para jogar seja recusado alto.

⚠️ Nenhum caso escreve o nome da modalidade: ela vem do próprio contrato
(`modalidades_declaradas()`), como em todo o pacote (aviso 4 da spec).
"""

from __future__ import annotations

import copy
import hashlib
import json
import tomllib

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import contrato_xadrez as cx


@pytest.fixture
def modalidade() -> str:
    """A única modalidade do contrato de hoje (o teste não a escreve)."""
    declaradas = cx.modalidades_declaradas()
    assert len(declaradas) >= 1
    return declaradas[0]


@pytest.fixture
def contrato_trocado(monkeypatch):
    """Devolve uma função que troca o contrato lido por uma versão alterada.

    `monkeypatch.setattr` troca a função do módulo só durante o teste: as outras
    funções a chamam pelo nome do módulo, e por isso enxergam a troca.
    """

    def trocar(alterar) -> None:
        dados = copy.deepcopy(json.loads(cx.CAMINHO_DO_CONTRATO.read_text("utf-8")))
        alterar(dados)
        monkeypatch.setattr(cx, "carregar_contrato", lambda: copy.deepcopy(dados))

    return trocar


def test_o_sha256_e_o_dos_bytes_do_arquivo_do_espelho():
    esperado = hashlib.sha256(cx.CAMINHO_DO_CONTRATO.read_bytes()).hexdigest()
    assert cx.sha256_do_contrato() == esperado


def test_as_modalidades_e_a_versao_vem_do_arquivo():
    dados = json.loads(cx.CAMINHO_DO_CONTRATO.read_text("utf-8"))
    assert cx.modalidades_declaradas() == tuple(dados["por_modalidade"])
    assert cx.versao_do_contrato() == dados["versao"]


def test_a_versao_do_motor_e_a_do_cargo_no_formato_composto():
    with cx.CAMINHO_DO_CARGO.open("rb") as arquivo:
        versao = tomllib.load(arquivo)["package"]["version"]
    assert cx.versao_do_crate() == versao
    assert cx.versao_do_motor() == f"rust_{versao}"
    # Cabe na coluna `co_versao_motor` (VARCHAR(60) desde a 0014).
    assert len(cx.versao_do_motor()) <= 60


def test_a_posicao_inicial_e_a_do_contrato(modalidade):
    dados = json.loads(cx.CAMINHO_DO_CONTRATO.read_text("utf-8"))
    assert cx.fen_inicial(modalidade) == dados["por_modalidade"][modalidade]["fen_inicial"]


def test_cada_nivel_traz_os_numeros_do_contrato(modalidade):
    dados = json.loads(cx.CAMINHO_DO_CONTRATO.read_text("utf-8"))
    for nivel in cx.niveis_disponiveis(modalidade):
        p = cx.parametros_do_nivel(modalidade, nivel)
        bruto = dados["por_modalidade"][modalidade]["niveis"][p.personagem]
        for campo in cx.CAMPOS_DO_NIVEL:
            assert getattr(p, campo) == bruto[campo], f"{p.personagem}.{campo}"


def test_os_niveis_vao_do_mais_fraco_ao_mais_forte_e_o_ideal_nao_e_personagem(
    modalidade, contrato_trocado
):
    contrato_trocado(lambda d: d.__setitem__("magno_no_build", True))
    assert cx.niveis_disponiveis(modalidade) == (
        NivelDeMotor.CACAU,
        NivelDeMotor.PITA,
        NivelDeMotor.TEX,
        NivelDeMotor.SAGAZ,
    )


def test_sem_o_magno_no_build_o_sagaz_some_e_e_recusado(modalidade, contrato_trocado):
    contrato_trocado(lambda d: d.__setitem__("magno_no_build", False))
    assert NivelDeMotor.SAGAZ not in cx.niveis_disponiveis(modalidade)
    assert len(cx.niveis_disponiveis(modalidade)) == 3
    with pytest.raises(cx.ContratoXadrezInvalido, match="magno_no_build"):
        cx.parametros_do_nivel(modalidade, NivelDeMotor.SAGAZ)
    # Os outros três continuam jogando.
    assert cx.parametros_do_nivel(modalidade, NivelDeMotor.TEX).personagem == "tex"


def test_magno_no_build_em_texto_e_recusado(contrato_trocado):
    # `"false"` é verdadeiro em Python: aceitá-lo poria um Magno que o app não tem.
    contrato_trocado(lambda d: d.__setitem__("magno_no_build", "false"))
    with pytest.raises(cx.ContratoXadrezInvalido, match="magno_no_build"):
        cx.magno_no_build()


def test_modalidade_desconhecida_e_recusada_com_a_lista():
    with pytest.raises(cx.ModalidadeDesconhecida, match="Declara"):
        cx.fen_inicial("modalidade_que_nao_existe")
    with pytest.raises(cx.ModalidadeDesconhecida):
        cx.parametros_do_nivel("modalidade_que_nao_existe", NivelDeMotor.TEX)


@pytest.mark.parametrize(
    ("campo", "valor", "trecho"),
    [
        ("teto_de_nos", 0, "teto_de_nos = 0"),
        ("teto_de_nos", -5, "teto_de_nos"),
        ("teto_de_nos", True, "teto_de_nos"),
        ("chance_do_erro_milesimos", 1001, "acima de 1000"),
        ("relogio_s", "45", "relogio_s"),
    ],
)
def test_numero_fora_do_lugar_e_recusado(modalidade, contrato_trocado, campo, valor, trecho):
    def alterar(d):
        d["por_modalidade"][modalidade]["niveis"]["tex"][campo] = valor

    contrato_trocado(alterar)
    with pytest.raises(cx.ContratoXadrezInvalido, match=trecho):
        cx.parametros_do_nivel(modalidade, NivelDeMotor.TEX)


def test_campo_que_falta_e_recusado_pelo_nome(modalidade, contrato_trocado):
    contrato_trocado(lambda d: d["por_modalidade"][modalidade]["niveis"]["pita"].pop("relogio_s"))
    with pytest.raises(cx.ContratoXadrezInvalido, match="relogio_s"):
        cx.parametros_do_nivel(modalidade, NivelDeMotor.PITA)


def test_o_relogio_nulo_e_a_rede_nula_viram_none(modalidade, contrato_trocado):
    def alterar(d):
        d["por_modalidade"][modalidade]["niveis"]["tex"]["relogio_s"] = None
        d["por_modalidade"][modalidade]["niveis"]["tex"]["rede_de_tempo_s"] = None

    contrato_trocado(alterar)
    p = cx.parametros_do_nivel(modalidade, NivelDeMotor.TEX)
    assert p.relogio_s is None and p.rede_de_tempo_s is None
