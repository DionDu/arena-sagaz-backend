"""O jogador do xadrez: o executável Rust, com as três travas (spec 012, T063).

O que se confere:
  - o executável saiu do crate do espelho (o carimbo), leu o contrato do espelho
    (o SHA-256) e é da versão do `Cargo.toml` espelhado;
  - o carimbo divergente, o `"sem_carimbo"`, o contrato divergente e a versão
    divergente são RECUSADOS na abertura;
  - as sete operações respondem pelo executável, e a recusa vira
    `MotorXadrezRecusou` com o código;
  - o Sagaz é recusado ANTES do pedido num build sem o Magno.

⚠️ Os casos com o executável PULAM com motivo quando ele não está compilado
(`scripts/compilar_motor_xadrez.py`). Na imagem do job ele é compilado no build
(T061), e o portão do build (`scripts/conferir_motor_xadrez.py`) confere.

⚠️ A modalidade não é escrita aqui: vem do contrato (aviso 4 da spec).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from motores.nucleo.carimbo import JOGOS_CONHECIDOS
from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import contrato_xadrez as cx
from motores.xadrez import jogador_xadrez as jx

MODALIDADE = cx.modalidades_declaradas()[0]
INICIAL = cx.fen_inicial(MODALIDADE)

#: Mate em um para as brancas: a torre de a1 vai a a8 (os peões prendem o rei).
MATE_EM_UM = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"

#: O executável compilado à mão no laboratório (`cargo build`, sem o carimbo),
#: quando existe: é a prova de que o `"sem_carimbo"` é recusado.
SEM_CARIMBO = (
    Path(__file__).resolve().parents[3]
    / "ia" / "jogos" / "jogo_xadrez" / "motor_rust" / "target" / "release"
    / "servidor_de_lances_xadrez.exe"
)


def _ou_pula() -> Path:
    try:
        return jx.caminho_do_executavel()
    except jx.MotorDartIndisponivel as erro:
        pytest.skip(f"o executável do xadrez não está compilado: {erro}")


@pytest.fixture(scope="module")
def jogador():
    _ou_pula()
    with jx.JogadorXadrez() as motor:
        yield motor


def test_o_executavel_saiu_do_crate_do_contrato_e_da_versao_do_espelho(jogador):
    assert jogador.resumo_do_motor == jx.resumo_dos_fontes()
    assert jogador.abertura["sha256_do_contrato"] == cx.sha256_do_contrato()
    assert jogador.abertura["versao"] == cx.versao_do_crate()
    assert MODALIDADE in jogador.abertura["modalidades"]


def test_o_buscar_joga_um_lance_legal_em_cada_nivel(jogador):
    legais = jogador.estado(modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[])["lances_legais"]
    # `lances_legais` agrupa por origem: {"e2": ["e3", "e4"], ...}.
    todos = {origem + destino for origem, destinos in legais.items() for destino in destinos}
    for nivel in cx.niveis_disponiveis(MODALIDADE):
        resposta = jogador.buscar(
            modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], nivel=nivel, semente=12345
        )
        assert resposta["lance"] in todos, nivel
        teto = cx.parametros_do_nivel(MODALIDADE, nivel).teto_de_nos
        assert resposta["nos"] <= teto, nivel


def test_a_mesma_semente_da_o_mesmo_lance_e_os_mesmos_nos(jogador):
    pedido = dict(
        modalidade=MODALIDADE, fen_inicial=INICIAL, lances=["e2e4", "e7e5"],
        nivel=NivelDeMotor.PITA, semente=99,
    )
    a = jogador.buscar(**pedido)
    b = jogador.buscar(**pedido)
    assert (a["lance"], a["acao"], a["nos"]) == (b["lance"], b["acao"], b["nos"])


def test_o_mate_em_um_sai_antes_de_tudo(jogador):
    resposta = jogador.buscar(
        modalidade=MODALIDADE, fen_inicial=MATE_EM_UM, lances=[], nivel=NivelDeMotor.CACAU, semente=1
    )
    assert resposta["lance"] == "a1a8"
    assert resposta["acao"] == "mate_em_um"
    assert resposta["fatos"]["fim"]["motivo"] == "xeque_mate"


def test_o_aplicar_traz_os_fatos_e_recusa_o_lance_ilegal_com_o_codigo(jogador):
    fatos = jogador.aplicar(modalidade=MODALIDADE, fen_inicial=MATE_EM_UM, lances=[], lance="a1a8")
    assert fatos["fatos"]["fim"] == {"motivo": "xeque_mate", "vencedor": "branca"}
    with pytest.raises(jx.MotorXadrezRecusou) as recusa:
        jogador.aplicar(modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], lance="e2e5")
    assert recusa.value.codigo == "lance_ilegal"
    # E depois do mate não se joga mais.
    with pytest.raises(jx.MotorXadrezRecusou) as terminada:
        jogador.buscar(
            modalidade=MODALIDADE, fen_inicial=MATE_EM_UM, lances=["a1a8"],
            nivel=NivelDeMotor.TEX, semente=1,
        )
    assert terminada.value.codigo == "partida_terminada"


def test_a_recusa_diz_a_regra_e_o_lance_legal_e_recusado(jogador):
    # O roque com as peças no caminho, na posição inicial.
    regra = jogador.recusa(modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], de="e1", para="g1")
    assert isinstance(regra, str) and regra
    with pytest.raises(jx.MotorXadrezRecusou) as legal:
        jogador.recusa(modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], de="e2", para="e4")
    assert legal.value.codigo == "lance_legal"


def test_a_jogada_ideal_o_radar_e_o_perft(jogador):
    ideal = jogador.jogada_ideal(modalidade=MODALIDADE, fen_inicial=MATE_EM_UM, lances=[])
    assert ideal["lance"] == "a1a8"
    # Depois de 1.e4 d5, o peão de e4 está ameaçado pelo de d5 (e o de d5 pelo de e4).
    assert jogador.radar(
        modalidade=MODALIDADE, fen_inicial=INICIAL, lances=["e2e4", "d7d5"], lado="branca"
    ) == ["e4"]
    # O perft da posição inicial a 3 meios-lances: 8 902 (o número de sempre).
    assert jogador.perft(modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], profundidade=3) == 8902


def test_o_sagaz_e_recusado_antes_do_pedido_num_build_sem_o_magno(jogador, monkeypatch):
    original = cx.carregar_contrato()
    original["magno_no_build"] = False
    monkeypatch.setattr(cx, "carregar_contrato", lambda: original)
    with pytest.raises(cx.ContratoXadrezInvalido, match="magno_no_build"):
        jogador.buscar(
            modalidade=MODALIDADE, fen_inicial=INICIAL, lances=[], nivel=NivelDeMotor.SAGAZ, semente=1
        )


def test_o_carimbo_divergente_e_recusado(tmp_path):
    _ou_pula()
    # Uma cópia do crate com um fonte mudado: o mesmo executável deixa de ser
    # o motor "destes" fontes.
    copia = tmp_path / "motor_rust"
    shutil.copytree(jx.FONTES_DO_MOTOR, copia)
    radar = copia / "src" / "radar.rs"
    radar.write_bytes(radar.read_bytes() + b"\n// outro motor\n")
    with pytest.raises(jx.MotorDartDivergente, match="radar.rs|recebido"):
        jx.JogadorXadrez(fontes=copia)


@pytest.mark.skipif(not SEM_CARIMBO.is_file(), reason="nao ha um executavel sem carimbo no laboratorio")
def test_o_executavel_sem_carimbo_e_recusado():
    with pytest.raises(jx.MotorDartDivergente, match="sem_carimbo"):
        jx.JogadorXadrez(caminho=SEM_CARIMBO)


def test_o_contrato_divergente_e_recusado(monkeypatch):
    _ou_pula()
    monkeypatch.setattr(cx, "sha256_do_contrato", lambda: "0" * 64)
    with pytest.raises(jx.MotorDartDivergente, match="outro contrato"):
        jx.JogadorXadrez()


def test_a_versao_divergente_e_recusada(monkeypatch):
    _ou_pula()
    monkeypatch.setattr(cx, "versao_do_crate", lambda: "9.9.9")
    with pytest.raises(jx.MotorDartDivergente, match="9.9.9"):
        jx.JogadorXadrez()


def test_xadrez_e_um_jogo_conhecido_do_carimbo():
    assert "xadrez" in JOGOS_CONHECIDOS


def test_o_script_de_compilar_usa_os_caminhos_do_jogador():
    # Uma cópia dos caminhos no script poderia compilar num lugar e o jogador
    # procurar em outro.
    from scripts import compilar_motor_xadrez as cmx

    assert cmx.CRATE_NO_ESPELHO == jx.FONTES_DO_MOTOR
    assert cmx.PASTA_DA_COMPILACAO == jx.PASTA_DA_COMPILACAO
    assert cmx.carimbo() == jx.resumo_dos_fontes()
