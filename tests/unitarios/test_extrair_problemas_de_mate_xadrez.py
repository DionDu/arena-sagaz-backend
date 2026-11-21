"""🔒 O extrator dos problemas de mate do Lichess (T074 da spec 012).

Tres linhas do CSV escritas a mao, no formato do `lichess_db_puzzle.csv`:

  1. um "mate em 2" que fica - e ⚠️ **a posicao gravada e a de DEPOIS do 1o
     lance** (o do adversario, a armadilha do R-22): a vez passa ao outro
     lado, e a peca que andou esta na casa nova;
  2. um "mate em 1", que fica de fora pelo tema (o tipo pede de 2 a 5);
  3. um cujo 1o lance ja da o mate (o "mate do tolo"): a posicao de depois
     tem fim, e o motor a recusa.

⚠️ Os lances do caso 1 nao formam um mate de verdade, e nao precisam: o
extrator confia no tema do Lichess e confere so o que e dele (o lance e legal,
a posicao nao tem fim). Quem prova o mate e a regua (RF-XDR-186).
"""

from __future__ import annotations

import csv
import io
import json

import pytest

from job import posicoes_xadrez as px
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorDartIndisponivel
from scripts import extrair_problemas_de_mate_xadrez as ex

CABECALHO = "PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags"

#: A posicao inicial, com as brancas a jogar: o 1o lance (do "adversario") e e2e4.
FEN_INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

#: O "mate do tolo" uma jogada antes: d8h4 da o mate na hora.
FEN_DO_TOLO = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq g3 0 2"

LINHAS = [
    f"aaa01,{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,95,2000,mate mateIn2 short,https://lichess.org/x,",
    f"aaa02,{FEN_INICIAL},e2e4 e7e5,1200,80,95,2000,mate mateIn1 oneMove,https://lichess.org/y,",
    f"aaa03,{FEN_DO_TOLO},d8h4 a2a3 a7a6 b2b3,1300,80,95,2000,mate mateIn2,https://lichess.org/z,",
]


def _linhas(*textos: str) -> list[dict[str, str]]:
    """As linhas como o `csv.DictReader` as entrega."""
    return list(csv.DictReader(io.StringIO("\n".join([CABECALHO, *textos]))))


@pytest.fixture(scope="module")
def motor():
    try:
        with JogadorXadrez() as jogador:
            yield jogador
    except MotorDartIndisponivel as erro:
        pytest.skip(f"sem o executavel do xadrez compilado: {erro}")


def test_so_o_mate_em_2_fica_e_a_posicao_e_a_de_DEPOIS(motor) -> None:
    problemas, resumo = ex.extrair(_linhas(*LINHAS), motor, maximo_por_tema=10)
    assert [p["id"] for p in problemas] == ["aaa01"]
    problema = problemas[0]
    # ⚠️ A de DEPOIS do e2e4: a vez e das pretas, e o peao esta em e4.
    assert problema["cor_da_pessoa"] == "preta"
    assert px.cor_da_vez(problema["fen"]) == "preta"
    pecas = px.pecas_do_fen(problema["fen"])
    assert pecas["e4"] == px.PecaNaCasa("e4", "branca", "peao")
    assert "e2" not in pecas
    assert problema["fen"] != FEN_INICIAL
    # A solucao e o resto dos lances, sem o do adversario.
    assert problema["solucao"] == ["e7e5", "g1f3", "b8c6"]
    assert problema["mate_em"] == 2
    # Os contadores zerados, como na base equilibrada.
    assert problema["fen"].split()[-2:] == ["0", "1"]
    # O "mate do tolo" foi recusado pelo motor (o 1o lance ja da o mate).
    assert resumo["mateIn2"] == {"ficaram": 1, "recusados_pelo_motor": 1}


def test_o_lance_ilegal_e_recusado(motor) -> None:
    ilegal = f"aaa04,{FEN_INICIAL},e2e5 e7e5 g1f3 b8c6,1500,80,95,2000,mateIn2,u,"
    problemas, resumo = ex.extrair(_linhas(ilegal), motor, maximo_por_tema=10)
    assert problemas == []
    assert resumo["mateIn2"]["recusados_pelo_motor"] == 1


@pytest.mark.parametrize(
    "linha",
    [
        # mate em 1: fora do tipo
        f"b1,{FEN_INICIAL},e2e4 e7e5,1500,80,95,2000,mateIn1,u,",
        # mate em 6: alem do tipo
        f"b2,{FEN_INICIAL},e2e4 e7e5,1500,80,95,2000,mateIn6,u,",
        # mate em 2 com 3 lances: o numero nao bate com 2N
        f"b3,{FEN_INICIAL},e2e4 e7e5 g1f3,1500,80,95,2000,mateIn2,u,",
        # pouco popular
        f"b4,{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,10,2000,mateIn2,u,",
        # pouco jogado
        f"b5,{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,95,3,mateIn2,u,",
        # sem tema de mate
        f"b6,{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,95,2000,fork,u,",
        # rating torto
        f"b7,{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,x,80,95,2000,mateIn2,u,",
    ],
)
def test_os_filtros_de_texto(linha: str) -> None:
    assert ex.candidato_da_linha(_linhas(linha)[0]) is None


def test_a_amostra_e_a_de_menor_SHA256_e_nao_depende_da_ordem() -> None:
    linhas = [
        f"p{i:03d},{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,95,2000,mateIn2,u,"
        for i in range(50)
    ]
    ida = ex.amostra_por_tema(_linhas(*linhas), reserva_por_tema=5)[2]
    volta = ex.amostra_por_tema(_linhas(*reversed(linhas)), reserva_por_tema=5)[2]
    assert [c.id for c in ida] == [c.id for c in volta]
    esperados = sorted((f"p{i:03d}" for i in range(50)), key=ex._ordem)[:5]
    assert [c.id for c in ida] == esperados


def test_a_cota_por_tema(motor) -> None:
    linhas = [
        f"q{i:03d},{FEN_INICIAL},e2e4 e7e5 g1f3 b8c6,1500,80,95,2000,mateIn2,u,"
        for i in range(8)
    ]
    problemas, resumo = ex.extrair(_linhas(*linhas), motor, maximo_por_tema=3)
    assert len(problemas) == 3
    assert resumo["mateIn2"]["ficaram"] == 3
    # Ordenados pelo id: bytes estaveis.
    assert [p["id"] for p in problemas] == sorted(p["id"] for p in problemas)


def test_o_main_grava_o_arquivo(tmp_path, motor) -> None:
    csv_ = tmp_path / "lichess_db_puzzle.csv"
    csv_.write_text("\n".join([CABECALHO, *LINHAS]) + "\n", encoding="utf-8")
    saida = tmp_path / "problemas.json"
    assert ex.main(["--csv", str(csv_), "--saida", str(saida)]) == 0
    dado = json.loads(saida.read_text(encoding="utf-8"))
    assert dado["versao"] == ex.VERSAO
    assert dado["origem"] == "lichess_db_puzzle (CC0)"
    assert [p["id"] for p in dado["problemas"]] == ["aaa01"]
    # Rodar de novo da os mesmos bytes.
    primeira = saida.read_bytes()
    ex.main(["--csv", str(csv_), "--saida", str(saida)])
    assert saida.read_bytes() == primeira
