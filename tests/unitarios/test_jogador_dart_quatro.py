"""O jogador do Quatro em Linha: o executável Dart, com as duas travas (T109).

O que se confere:
  - o executável saiu dos fontes do espelho (o carimbo), e leu o contrato do
    espelho (o SHA-256);
  - o carimbo divergente e o contrato divergente são RECUSADOS na abertura;
  - o `decidir` joga um lance legal pelo árbitro, com os números do contrato, e
    a mesma semente dá o mesmo lance e os mesmos nós;
  - o `buscar` acha a vitória imediata;
  - o pedido recusado pelo motor vira `ValueError`.

⚠️ Os casos com o executável PULAM com motivo quando ele não está compilado
(`dart run bin/compilar_servidor_de_lances_quatro.dart`, no laboratório). Na
imagem do job ele é compilado no build (T110), e o portão do build confere.
"""

import pytest

from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import contrato_quatro as cq
from motores.quatro import jogador_dart_quatro as jdq
from motores.quatro.motor_quatro import MotorQuatro

MODALIDADE = cq.modalidades_declaradas()[0]


def _ou_pula():
    try:
        return jdq.caminho_do_executavel()
    except jdq.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do Quatro não está compilado: {erro}")


@pytest.fixture(scope="module")
def jogador():
    _ou_pula()
    with jdq.JogadorDartQuatro() as motor:
        yield motor


def test_o_executavel_saiu_dos_fontes_e_do_contrato_do_espelho(jogador):
    assert jogador.resumo_do_motor == jdq.resumo_dos_fontes()
    assert jogador.abertura["sha256_do_contrato"] == cq.sha256_do_contrato()
    assert MODALIDADE in jogador.abertura["modalidades"]


def test_o_decidir_joga_um_lance_legal_com_os_numeros_do_contrato(jogador):
    arbitro = MotorQuatro(MODALIDADE)
    for nivel in NivelDeMotor:
        resposta = jogador.decidir(
            lances="s4s4s3", co_modalidade=MODALIDADE, nivel=nivel, semente=12345
        )
        estado = arbitro.estado_de_sequencia("s4s4s3")
        assert resposta["lance"] in arbitro.lances_legais(estado), nivel
        teto = cq.parametros_do_personagem(MODALIDADE, nivel).teto_de_nos
        assert resposta["nosVisitados"] <= teto, nivel


def test_a_mesma_semente_da_o_mesmo_lance_e_os_mesmos_nos(jogador):
    pedido = dict(lances="s4s3", co_modalidade=MODALIDADE, nivel=NivelDeMotor.PITA, semente=99)
    a = jogador.decidir(**pedido)
    b = jogador.decidir(**pedido)
    assert (a["lance"], a["acao"], a["nosVisitados"]) == (b["lance"], b["acao"], b["nosVisitados"])


def test_o_buscar_acha_a_vitoria_imediata(jogador):
    # J1 tem três de pé na coluna 1, e é a vez dele.
    resposta = jogador.buscar(lances="s1s2s1s2s1s2", co_modalidade=MODALIDADE, teto_de_nos=1000)
    assert resposta["lance"] == "s1"
    assert resposta["acao"] == "busca_melhor"


def test_o_pedido_recusado_vira_value_error(jogador):
    with pytest.raises(ValueError, match="já acabou"):
        jogador.decidir(
            lances="s1s2s1s2s1s2s1", co_modalidade=MODALIDADE,
            nivel=NivelDeMotor.TEX, semente=1,
        )
    # E o processo continua respondendo depois da recusa.
    assert jogador.buscar(lances="", co_modalidade=MODALIDADE, teto_de_nos=200)["lance"]


def test_o_carimbo_divergente_e_recusado(tmp_path):
    _ou_pula()
    # Fontes de referência que não são as do executável.
    (tmp_path / "busca_quatro.dart").write_text("// outro motor\n", encoding="utf-8")
    with pytest.raises(jdq.MotorDartDivergente, match="busca_quatro.dart"):
        jdq.JogadorDartQuatro(fontes=tmp_path)


def test_o_contrato_divergente_e_recusado(monkeypatch):
    _ou_pula()
    # O executável lê o contrato do espelho; o backend passa a esperar outro.
    monkeypatch.setattr(cq, "sha256_do_contrato", lambda: "0" * 64)
    with pytest.raises(jdq.MotorDartDivergente, match="outro contrato"):
        jdq.JogadorDartQuatro()


def test_quatro_e_um_jogo_conhecido_do_carimbo():
    from motores.nucleo.carimbo import JOGOS_CONHECIDOS

    assert "quatro" in JOGOS_CONHECIDOS
