"""T007 — o carimbo de tudo o que o motor produz (RF-DES-164/146).

O que estes testes travam: que o carimbo **descreva o produtor** e nada mais, que
recuse valores que o banco não aceitaria, e que a lição de 26/08/2026 fique
impossível de desfazer por descuido — a versão do motor e a do perfil são
obrigatórias, não opcionais com default.
"""

import dataclasses
import json

import pytest

from motores.nucleo.carimbo import Carimbo
from motores.nucleo.papeis import NivelDeMotor


def carimbo_de_damas(**trocas) -> Carimbo:
    """Um carimbo válido de damas, com o que o teste quiser trocar."""
    base = dict(
        co_jogo="damas",
        co_nivel=NivelDeMotor.SAGAZ,
        co_versao_motor="damas-py-1.4.0",
        co_versao_perfil="perfil-2026-09",
        co_modalidade="brasileiras",
    )
    base.update(trocas)
    return Carimbo(**base)  # type: ignore[arg-type]


# ── O que ele carrega ───────────────────────────────────────────────────────


def test_carimbo_vira_exatamente_as_colunas_do_banco():
    colunas = carimbo_de_damas().para_colunas()
    assert colunas == {
        "co_jogo": "damas",
        "co_modalidade": "brasileiras",
        "co_nivel": "sagaz",
        "co_versao_motor": "damas-py-1.4.0",
        "co_versao_perfil": "perfil-2026-09",
    }


def test_o_nivel_sai_como_texto_e_nao_como_enum():
    """Quem grava a linha não deve precisar conhecer o tipo Python da camada."""
    valor = carimbo_de_damas().para_colunas()["co_nivel"]
    assert isinstance(valor, str)


def test_as_colunas_passam_por_json():
    """O carimbo viaja para o banco e para o painel — precisa serializar."""
    json.dumps(carimbo_de_damas().para_colunas())  # não levanta


def test_pontinhos_nao_tem_modalidade_e_ela_sai_nula():
    """`None` é diferente de string vazia: 'não se aplica' não é 'não informado'."""
    carimbo = Carimbo(
        co_jogo="pontinhos",
        co_nivel=NivelDeMotor.TEX,
        co_versao_motor="pontinhos-py-2.1.0",
        co_versao_perfil="perfil-2026-09",
    )
    assert carimbo.para_colunas()["co_modalidade"] is None


# ── A lição de 26/08/2026: versão é obrigatória ────────────────────────────


@pytest.mark.parametrize("campo", ["co_versao_motor", "co_versao_perfil"])
def test_versao_nao_tem_valor_padrao(campo):
    """Se um dia ganhar default, uma chamada esquecida grava a versão errada em
    silêncio — que é exatamente o defeito que este campo existe para impedir.

    `dataclasses.fields` deixa isso verificável: o campo tem de continuar sem
    `default` e sem `default_factory`.
    """
    campos = {f.name: f for f in dataclasses.fields(Carimbo)}
    alvo = campos[campo]
    assert alvo.default is dataclasses.MISSING, f"{campo} ganhou um default"
    assert alvo.default_factory is dataclasses.MISSING, f"{campo} ganhou uma factory"


@pytest.mark.parametrize("campo", ["co_versao_motor", "co_versao_perfil"])
def test_versao_vazia_e_recusada(campo):
    with pytest.raises(ValueError, match=campo):
        carimbo_de_damas(**{campo: ""})


@pytest.mark.parametrize("campo", ["co_versao_motor", "co_versao_perfil"])
def test_versao_longa_demais_para_a_coluna_e_recusada(campo):
    """41 caracteres numa coluna VARCHAR(40): dói aqui, e não no INSERT."""
    with pytest.raises(ValueError, match="caracteres"):
        carimbo_de_damas(**{campo: "a" * 41})


def test_versao_com_maiuscula_e_recusada():
    """`Damas-PY-1.4.0` e `damas-py-1.4.0` conviveriam como se fossem duas."""
    with pytest.raises(ValueError, match="forma esperada"):
        carimbo_de_damas(co_versao_motor="Damas-PY-1.4.0")


def test_versao_com_espaco_e_recusada():
    with pytest.raises(ValueError, match="forma esperada"):
        carimbo_de_damas(co_versao_perfil="perfil 2026 09")


# ── Jogo e nível ────────────────────────────────────────────────────────────


def test_jogo_desconhecido_e_recusado_com_a_lista_na_mensagem():
    with pytest.raises(ValueError) as erro:
        carimbo_de_damas(co_jogo="xadrez")
    assert "pontinhos" in str(erro.value)  # a mensagem diz quais valem


def test_nivel_como_texto_solto_e_recusado():
    """Texto solto deixaria 'sagas' passar por 'sagaz' e ninguém notaria."""
    with pytest.raises(TypeError, match="NivelDeMotor"):
        carimbo_de_damas(co_nivel="sagaz")


# ── Imutabilidade e derivação ──────────────────────────────────────────────


def test_carimbo_e_imutavel():
    """Um carimbo alterável depois de emitido não provaria nada."""
    carimbo = carimbo_de_damas()
    with pytest.raises(Exception):
        carimbo.co_versao_motor = "damas-py-9.9.9"  # type: ignore[misc]


def test_com_nivel_devolve_outro_carimbo_e_preserva_o_resto():
    """A régua mede o mesmo candidato nos quatro níveis (Bloco D)."""
    original = carimbo_de_damas()
    cacau = original.com_nivel(NivelDeMotor.CACAU)

    assert cacau.co_nivel is NivelDeMotor.CACAU
    assert cacau.co_versao_motor == original.co_versao_motor
    assert cacau.co_versao_perfil == original.co_versao_perfil
    assert cacau.co_modalidade == original.co_modalidade
    assert original.co_nivel is NivelDeMotor.SAGAZ  # o de origem não mudou


# ── O que ele NÃO sabe (RF-DES-165) ────────────────────────────────────────


def test_o_carimbo_nao_conhece_desafio():
    """Ele descreve o PRODUTOR, não o produto: nada de dia, coleção ou desafio.

    Um `id_desafio` aqui dentro faria a camada de motores conhecer o schema
    `desafio` pela porta dos fundos — sem nenhum import proibido para o cadeado 2
    pegar.
    """
    proibidos = ("desafio", "dia", "colecao", "resolucao", "xp", "quadro")
    nomes = {f.name.lower() for f in dataclasses.fields(Carimbo)}
    for nome in nomes:
        for palavra in proibidos:
            assert palavra not in nome, (
                f"o carimbo ganhou o campo '{nome}' — a camada de motores não "
                "conhece desafio (RF-DES-165)."
            )


def test_representacao_legivel_para_log():
    assert str(carimbo_de_damas()) == (
        "damas/brasileiras nível=sagaz motor=damas-py-1.4.0 perfil=perfil-2026-09"
    )


def test_representacao_legivel_omite_modalidade_quando_nao_ha():
    carimbo = Carimbo(
        co_jogo="pontinhos",
        co_nivel=NivelDeMotor.CACAU,
        co_versao_motor="pontinhos-py-2.1.0",
        co_versao_perfil="perfil-2026-09",
    )
    assert "/" not in str(carimbo)
