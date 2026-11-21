"""T074 (spec 012) - EXTRAI OS PROBLEMAS DE MATE DO LICHESS para o `xadrez_dar_mate`.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

O `xadrez_dar_mate` ("De xeque-mate em Tex em ate N lances") nao sai da base
equilibrada: uma posicao calma e equilibrada quase nunca tem mate em ate 5. As
posicoes dele vem do **banco de problemas do Lichess** (`lichess_db_puzzle.csv`,
licenca CC0), que marca cada problema com o tema `mateInN` (RF-XDR-186, R-22).

═══════════════════════════════════════════════════════════════════════════
⚠️ A ARMADILHA DO FORMATO (R-22)
═══════════════════════════════════════════════════════════════════════════

No banco, o FEN e a posicao **ANTES** do lance do adversario, e o 1o lance da
coluna `Moves` e DELE (o lance que cria o problema). A posicao que a pessoa
recebe e a de **DEPOIS** desse lance. Gravar o FEN da coluna daria a vez ao
lado errado, e a pessoa jogaria o problema do adversario.

Por isso cada problema passa pelo executavel do motor: o 1o lance e aplicado
(`aplicar`), o que confere que ele e legal, e a posicao gravada e a
`fen_depois` da resposta, que nao pode ter fim (`fatos.fim` nulo). ⛔ Nenhuma
regra de xadrez aqui: quem diz que o lance e legal e onde as pecas foram parar
e o motor.

═══════════════════════════════════════════════════════════════════════════
O QUE FICA, E QUANTOS
═══════════════════════════════════════════════════════════════════════════

- **So `mateIn2` a `mateIn5`** (o tipo pede mate em ate 5; o mate em 1 seria
  um lance so). A coluna `Moves` tem de ter `2N` lances (o do adversario, os N
  da pessoa e os N - 1 dele no meio); linha que nao bate e defeito do dado, e
  fica de fora.
- **Qualidade** (palpite de partida, sem medida): popularidade de pelo menos
  [POPULARIDADE_MINIMA] e pelo menos [PARTIDAS_MINIMAS] tentativas no Lichess,
  para fugir de problema mal resolvido ou nunca jogado.
- **Uma amostra estavel por tema**: os [MAXIMO_POR_TEMA] de menor SHA-256 do
  `PuzzleId`, e nao os primeiros do arquivo. Assim a amostra nao depende da
  ordem das linhas (o Lichess republica o banco), e o mesmo banco da o mesmo
  arquivo. Os de reserva (o dobro da cota) cobrem os que o motor recusar.
- **Quem decide se o problema serve ao desafio e a regua** ("a Pita resolve, a
  Cacau nao", RF-XDR-186): este arquivo so garante que a posicao e jogavel.

O CSV inteiro e lido uma vez, em fluxo (tem milhoes de linhas), mas o motor so
confere a amostra: o processo leva minutos, e nao horas.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (T075, o dono)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\extrair_problemas_de_mate_xadrez.py --csv ..\\ia\\dados\\lichess\\lichess_db_puzzle.csv

Saida: `dados/jogo_xadrez/problemas_de_mate.json`, ordenado pelo `PuzzleId`
(bytes estaveis). `--maximo-de-linhas N` le so as N primeiras linhas (para
medir quanto o arquivo inteiro vai demorar).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from motores.xadrez import contrato_xadrez  # noqa: E402
from motores.xadrez.jogador_xadrez import (  # noqa: E402
    JogadorXadrez,
    MotorXadrezRecusou,
)

#: A saida, ao lado dos outros dados do job.
SAIDA = RAIZ / "dados" / "jogo_xadrez" / "problemas_de_mate.json"

#: A versao do documento. Sobe quando o FORMATO muda.
VERSAO = 1

#: Os temas que ficam: mate em 2 a mate em 5 (o tipo pede ate 5).
TEMAS: dict[str, int] = {"mateIn2": 2, "mateIn3": 3, "mateIn4": 4, "mateIn5": 5}

#: Quantos problemas ficam por tema (palpite: 2 500 por tema, 10 000 ao todo,
#: ~1,5 MB de texto - cabe no Git e sobra para a regua escolher).
MAXIMO_POR_TEMA = 2500

#: A popularidade minima no Lichess (de -100 a 100; palpite de partida).
POPULARIDADE_MINIMA = 80

#: O minimo de tentativas no Lichess (palpite de partida).
PARTIDAS_MINIMAS = 100

#: A modalidade do xadrez, LIDA do contrato (RF-XDR-013).
MODALIDADE = contrato_xadrez.modalidades_declaradas()[0]

#: A vez no 2o campo do FEN -> a cor de regra (a mesma de `job/posicoes_xadrez.py`).
COR_DA_VEZ = {"w": "branca", "b": "preta"}


@dataclass(frozen=True, slots=True)
class Candidato:
    """Uma linha do CSV que passou nos filtros de texto (tema e qualidade)."""

    id: str
    fen_antes: str
    lances: tuple[str, ...]
    mate_em: int
    rating: int
    popularidade: int
    partidas: int


def _ordem(id_do_problema: str) -> str:
    """A chave da amostra estavel: o SHA-256 do `PuzzleId`."""
    return hashlib.sha256(id_do_problema.encode("utf-8")).hexdigest()


def candidato_da_linha(
    linha: dict[str, str],
    *,
    popularidade_minima: int = POPULARIDADE_MINIMA,
    partidas_minimas: int = PARTIDAS_MINIMAS,
) -> Candidato | None:
    """A linha do CSV como [Candidato], ou `None` quando ela fica de fora.

    Fica de fora: sem tema `mateIn2` a `mateIn5`; numero de lances que nao e
    `2N`; abaixo da qualidade minima; campo numerico torto.
    """
    temas = linha.get("Themes", "").split()
    mates = [TEMAS[t] for t in temas if t in TEMAS]
    if len(mates) != 1:
        return None
    mate_em = mates[0]
    lances = tuple(linha.get("Moves", "").split())
    # O do adversario + os N da pessoa + os N - 1 dele no meio = 2N.
    if len(lances) != 2 * mate_em:
        return None
    try:
        rating = int(linha["Rating"])
        popularidade = int(linha["Popularity"])
        partidas = int(linha["NbPlays"])
    except (KeyError, ValueError):
        return None
    if popularidade < popularidade_minima or partidas < partidas_minimas:
        return None
    return Candidato(
        id=linha["PuzzleId"],
        fen_antes=linha["FEN"],
        lances=lances,
        mate_em=mate_em,
        rating=rating,
        popularidade=popularidade,
        partidas=partidas,
    )


def amostra_por_tema(
    linhas: Iterable[dict[str, str]],
    *,
    reserva_por_tema: int,
    popularidade_minima: int = POPULARIDADE_MINIMA,
    partidas_minimas: int = PARTIDAS_MINIMAS,
) -> dict[int, list[Candidato]]:
    """Os [reserva_por_tema] candidatos de menor SHA-256 de cada tema, em ordem.

    ⚠️ Um monte (`heapq`) por tema, com o tamanho da reserva: o CSV tem
    milhoes de linhas, e guardar todas para ordenar no fim pediria gigabytes.
    O `heapq` deixa no topo o MENOR item; guardando o SHA-256 como numero
    NEGATIVO, o topo e o pior da amostra (o maior SHA-256), que sai quando
    chega um melhor.
    """
    montes: dict[int, list[tuple[int, str, Candidato]]] = {n: [] for n in TEMAS.values()}
    for linha in linhas:
        candidato = candidato_da_linha(
            linha, popularidade_minima=popularidade_minima, partidas_minimas=partidas_minimas
        )
        if candidato is None:
            continue
        # `int(..., 16)` le o SHA-256 hexadecimal como numero.
        item = (-int(_ordem(candidato.id), 16), candidato.id, candidato)
        monte = montes[candidato.mate_em]
        if len(monte) < reserva_por_tema:
            heapq.heappush(monte, item)
        elif item > monte[0]:
            # O novo tem SHA-256 menor que o pior guardado: troca os dois.
            heapq.heapreplace(monte, item)
    # Do menor SHA-256 ao maior (o negativo, do maior ao menor).
    return {
        n: [c for _, _, c in sorted(monte, reverse=True)]
        for n, monte in montes.items()
    }


def _fen_com_contadores_zerados(fen: str) -> str:
    """O FEN com o contador dos 50 lances em 0 e o numero do lance em 1.

    ⚠️ E so texto (os dois ultimos campos), como na base equilibrada (R-22): a
    partida de desafio comeca ali, com historico vazio (R-03).
    """
    campos = fen.split()
    return " ".join([*campos[:4], "0", "1"])


def conferir_no_motor(motor: JogadorXadrez, candidato: Candidato) -> dict[str, Any] | None:
    """O problema como sai no arquivo, ou `None` quando o motor o recusa.

    Aplica o 1o lance (do adversario) e fica com a posicao de DEPOIS. Recusa:
    o lance nao e legal, ou a posicao de depois ja tem fim.
    """
    try:
        resposta = motor.aplicar(
            modalidade=MODALIDADE,
            fen_inicial=candidato.fen_antes,
            lances=[],
            lance=candidato.lances[0],
        )
    except MotorXadrezRecusou:
        return None
    if resposta["fatos"]["fim"] is not None:
        return None
    fen = _fen_com_contadores_zerados(resposta["fen_depois"])
    return {
        "id": candidato.id,
        "fen": fen,
        "cor_da_pessoa": COR_DA_VEZ[fen.split()[1]],
        "mate_em": candidato.mate_em,
        "solucao": list(candidato.lances[1:]),
        "rating": candidato.rating,
        "popularidade": candidato.popularidade,
        "partidas": candidato.partidas,
    }


def extrair(
    linhas: Iterable[dict[str, str]],
    motor: JogadorXadrez,
    *,
    maximo_por_tema: int = MAXIMO_POR_TEMA,
    popularidade_minima: int = POPULARIDADE_MINIMA,
    partidas_minimas: int = PARTIDAS_MINIMAS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Os problemas que ficam (ordenados pelo id) e o resumo por tema."""
    amostras = amostra_por_tema(
        linhas,
        reserva_por_tema=2 * maximo_por_tema,
        popularidade_minima=popularidade_minima,
        partidas_minimas=partidas_minimas,
    )
    problemas: list[dict[str, Any]] = []
    resumo: dict[str, Any] = {}
    for n, candidatos in sorted(amostras.items()):
        ficaram = 0
        recusados = 0
        for candidato in candidatos:
            if ficaram >= maximo_por_tema:
                break
            problema = conferir_no_motor(motor, candidato)
            if problema is None:
                recusados += 1
                continue
            problemas.append(problema)
            ficaram += 1
        resumo[f"mateIn{n}"] = {"ficaram": ficaram, "recusados_pelo_motor": recusados}
    problemas.sort(key=lambda p: p["id"])
    return problemas, resumo


def ler_csv(caminho: Path, maximo_de_linhas: int | None = None) -> Iterator[dict[str, str]]:
    """As linhas do CSV do Lichess, em fluxo."""
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        for indice, linha in enumerate(csv.DictReader(arquivo)):
            if maximo_de_linhas is not None and indice >= maximo_de_linhas:
                return
            yield linha


def documento(problemas: list[dict[str, Any]], resumo: dict[str, Any]) -> dict[str, Any]:
    """O arquivo de saida."""
    return {
        "de_documento": (
            "Problemas de mate em 2 a 5 do banco de problemas do Lichess "
            "(lichess_db_puzzle.csv, CC0), para o xadrez_dar_mate. A posicao e "
            "a de DEPOIS do 1o lance do problema (que e do adversario), conferida "
            "pelo motor. Gerado por scripts/extrair_problemas_de_mate_xadrez.py - "
            "NAO edite a mao."
        ),
        "versao": VERSAO,
        "origem": "lichess_db_puzzle (CC0)",
        "resumo": resumo,
        "problemas": problemas,
    }


def main(argv: list[str] | None = None) -> int:
    """Le o CSV, confere a amostra no motor e grava a saida."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, required=True, help="o lichess_db_puzzle.csv")
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument("--maximo-por-tema", type=int, default=MAXIMO_POR_TEMA)
    parser.add_argument("--maximo-de-linhas", type=int, default=None)
    argumentos = parser.parse_args(argv)

    inicio = time.monotonic()
    with JogadorXadrez() as motor:
        problemas, resumo = extrair(
            ler_csv(argumentos.csv, argumentos.maximo_de_linhas),
            motor,
            maximo_por_tema=argumentos.maximo_por_tema,
        )
    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(documento(problemas, resumo), ensure_ascii=False, indent=1) + "\n"
    argumentos.saida.write_text(texto, encoding="utf-8", newline="\n")
    print(f"escrito: {argumentos.saida} ({len(texto.encode('utf-8'))} bytes)")
    for tema, contagem in resumo.items():
        print(f"  {tema}: {contagem['ficaram']} ficaram, {contagem['recusados_pelo_motor']} recusados pelo motor")
    print(f"tempo: {time.monotonic() - inicio:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
