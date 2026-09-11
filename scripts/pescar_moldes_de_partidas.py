"""PESCA moldes de damas nas posicoes de PARTIDAS REAIS, em vez de sortea-las.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE SCRIPT EXISTE — A IDEIA E DO DONO, E O BANCO DEU RAZAO A ELA
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026, depois de curar a primeira fila de verdade, o dono escreveu:

> *"Os desafios de coroar damas tem muitos lances agora, no entanto estao
> absurdamente faceis. E basicamente so seguir em linha reta com a peca ate o
> final, nao tem desafio algum."*

> *"Sera que nao deveriamos voltar aquela minha ideia? Voce olhar o banco de
> dados das partidas de pontinhos jogadas por humanos no App real e pescar de la
> desafios possiveis?"*

**A medida que fecha o caso**, tirada do `des` no mesmo dia:

    material medio da posicao        | nos MOLDES sorteados | em PARTIDAS REAIS
    ---------------------------------+----------------------+------------------
    posicao de coroar                |  6,0 pecas (sempre!) | 12,3 pecas
    posicao de captura de 3+ pecas    |  7,0 pecas (sempre!) | 17,6 pecas

⛔ **Os 330 moldes de `damas_coroar` tem EXATAMENTE 3 brancas e 3 pretas — todos
eles.** Nao e uma tendencia: e um parametro escrito a mao em
`cacar_moldes_damas.candidatas_para_coroar`, que sorteia a ponta de lanca em
5..12 e as pretas em 13..24. ⚠️ **As pretas ficam ATRAS da branca que vai coroar**
— elas andam para numeros maiores, e a coroacao branca e em 1..4. Nada podia
interceptar, em molde nenhum. O dono descreveu com precisao o que o codigo
construia.

**O que este script faz de diferente:** nao inventa posicao. Le posicoes que
**aconteceram** — `jogo_damas.tb002_jogada.co_fen_antes` guarda a FEN antes de
cada lance de cada partida — e as entrega a **mesma** peneira e a **mesma**
medicao da cacada. ⚠️ **A troca e so da FONTE**: `cacar_moldes_damas` ja separa
"de onde vem a candidata" (`CANDIDATAS`) de "ela presta?" (`_peneirar_uma` /
`_medir_uma`), e e por isso que pescar custa um arquivo novo em vez de uma
reescrita.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ISTO **NAO** RESOLVE
═══════════════════════════════════════════════════════════════════════════

Pescar entrega **posicao plausivel**, e nao **posicao dificil**. Quem diz se um
desafio e dificil continua sendo a regua (`job/regua.py`), medindo os mascotes.
⛔ A licao de 11/09 foi exatamente essa: trocar um criterio errado (distancia ate
o objetivo) por outro criterio errado nao conserta nada. Material alto e uma
**hipotese** de que a posicao tem oposicao — quem confirma e a medicao.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

1. Tirar as posicoes do banco (somente leitura, ⛔ **sempre o `des`**):

    .venv\\Scripts\\python scripts\\consultar_des.py --json "SELECT d.co_fen_antes AS fen
      FROM jogo_damas.tb002_jogada d" > fens_reais.json

2. Pescar:

    .venv\\Scripts\\python -u scripts\\pescar_moldes_de_partidas.py fens_reais.json ^
        --tipo damas_coroar --minimo-pecas 10 --processos 14

⚠️ **`-u` importa**: sem ele o Windows segura a saida num buffer e a execucao
parece travada.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

# O script mora em `scripts/`, e importa `job/` e `motores/`, que sao irmaos dele.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows e cp1252; sem isto um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from job.espelho_de_damas import com_as_brancas_a_jogar  # noqa: E402

# ⚠️ **Importar da cacada, e nao copiar dela.** A peneira, a medicao, os
# orcamentos e o teto de lances tem de ser os MESMOS — um molde pescado com
# criterio diferente do sorteado produziria uma fila com duas qualidades, e
# ninguem saberia qual desafio veio de onde.
from scripts.cacar_moldes_damas import (  # noqa: E402
    MINIMO_DE_MODALIDADES,
    TIPOS,
    _mapear,
    _medir_uma,
    _peneirar_uma,
    processos_padrao,
)


def pecas_da_fen(fen: str) -> tuple[int, int]:
    """Quantas brancas e quantas pretas ha na posicao.

    A FEN de damas tem tres campos separados por `:` — de quem e a vez, as
    brancas e as pretas: `W:W7,11,14:B2,5,10`. O `[1:]` de cada campo pula a
    letra da cor; o `K` de uma dama fica colado na casa (`K31`) e nao atrapalha
    a contagem, porque aqui so se conta quantos itens ha.
    """
    campos = fen.split(":")
    brancas = [c for c in campos[1][1:].split(",") if c]
    pretas = [c for c in campos[2][1:].split(",") if c]
    return len(brancas), len(pretas)


def fileiras_ate_coroar(fen: str) -> int:
    """A quantos PASSOS de fileira esta a pedra branca mais adiantada.

    As 32 casas escuras sao numeradas de 1 a 32, quatro por fileira: a casa `c`
    esta na fileira `(c - 1) // 4`. As brancas coroam na fileira 0 (casas 1..4),
    e uma pedra anda **uma fileira por lance**. Entao este numero e o **piso
    absoluto** de lances para coroar — nenhuma posicao coroa em menos do que ele,
    por mais livre que o caminho esteja.

    ⚠️ **As damas (`K`) sao ignoradas de proposito:** peca ja coroada nao coroa de
    novo, e contar a dama como "a mais adiantada" faria uma posicao sem nenhuma
    pedra promovivel parecer a um passo do objetivo.

    ⚠️ **Isto NAO e um criterio de dificuldade — e aritmetica**, e a distincao
    importa: foi confundir as duas coisas que produziu os 330 moldes faceis de
    11/09/2026. Aqui o numero so serve para nao gastar dois minutos de Sagaz
    provando que uma peca a sete fileiras nao chega em seis lances.

    Returns:
        A menor distancia em fileiras, ou `99` se nao ha pedra branca alguma.
    """
    campo_branco = fen.split(":")[1][1:]
    distancias = [
        (int(casa) - 1) // 4
        for casa in campo_branco.split(",")
        if casa and not casa.startswith("K")
    ]
    return min(distancias) if distancias else 99


def carregar(caminho: Path) -> list[str]:
    """Le o JSON do `consultar_des.py` e devolve as FENs, normalizadas e sem repeticao.

    ⚠️ **Toda posicao sai com as BRANCAS a jogar.** Metade das posicoes reais tem
    a vez das pretas, e o acervo de moldes e de posicoes com as brancas na vez
    (`job/gerador.py` conta com isso). `com_as_brancas_a_jogar` espelha quando
    preciso — rotacao de 180 graus mais troca de cores —, o que preserva a
    posicao **e** o lado que resolve.

    ⚠️ **A deduplicacao vem DEPOIS do espelho**, de proposito: duas posicoes que
    so diferem pelo lado da vez viram a mesma candidata, e medir as duas seria
    pagar o dobro pela mesma resposta.
    """
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    vistas: dict[str, None] = {}  # dict e nao set: preserva a ordem de chegada
    for linha in dados:
        fen = linha["fen"] if isinstance(linha, dict) else linha
        if not fen:
            continue
        try:
            vistas.setdefault(com_as_brancas_a_jogar(fen), None)
        except Exception:  # noqa: BLE001 — FEN malformada no log nao derruba a pesca
            continue
    return list(vistas)


def main() -> int:
    """Pesca, peneira, mede e imprime — nesta ordem, com o tempo de cada fase."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivo", type=Path, help="JSON com as FENs (do consultar_des.py)")
    ap.add_argument("--tipo", default="damas_coroar", choices=sorted(TIPOS))
    ap.add_argument(
        "--minimo-pecas",
        type=int,
        default=0,
        help=(
            "descarta posicoes com menos pecas que isto. ⚠️ E uma HIPOTESE de "
            "oposicao, nao um criterio de dificuldade — quem decide e a medicao."
        ),
    )
    ap.add_argument(
        "--amostra",
        type=int,
        default=0,
        help="pesca so N posicoes (para uma sondagem rapida)",
    )
    ap.add_argument(
        "--alcancavel",
        type=int,
        default=0,
        help=(
            "so posicoes com uma pedra branca a ate N fileiras da coroacao. "
            "⚠️ Aritmetica, nao dificuldade: uma pedra a sete fileiras nao coroa "
            "em seis lances, e provar isso custa dois minutos de Sagaz por "
            "posicao. Use o numero de lances da janela do tipo."
        ),
    )
    ap.add_argument(
        "--embaralhar",
        action="store_true",
        help=(
            "sorteia a amostra em vez de pegar as N primeiras. ⚠️ As posicoes "
            "chegam na ordem das partidas, entao as primeiras sao todas ABERTURA "
            "— uma sondagem sem isto mede o comeco do jogo, e nao o acervo."
        ),
    )
    ap.add_argument("--processos", type=int, default=processos_padrao())
    ap.add_argument(
        "--bloco",
        action="store_true",
        help="imprime as aprovadas como um bloco Python, pronto para colar",
    )
    args = ap.parse_args()

    parametros = TIPOS[args.tipo]
    candidatas = carregar(args.arquivo)
    print(f"posicoes reais, sem repeticao: {len(candidatas)}")

    if args.minimo_pecas:
        antes = len(candidatas)
        candidatas = [f for f in candidatas if sum(pecas_da_fen(f)) >= args.minimo_pecas]
        print(f"com {args.minimo_pecas}+ pecas: {len(candidatas)} (de {antes})")

    if args.alcancavel:
        antes = len(candidatas)
        candidatas = [f for f in candidatas if fileiras_ate_coroar(f) <= args.alcancavel]
        print(
            f"com pedra branca a {args.alcancavel} fileira(s) ou menos da coroacao: "
            f"{len(candidatas)} (de {antes})"
        )

    if args.embaralhar:
        # ⚠️ Semente fixa: a sondagem de amanha tem de olhar a MESMA amostra da de
        # hoje, senao um rendimento que mudou pode ser o criterio ou pode ser o
        # sorteio, e nao ha como saber qual.
        random.Random(20260911).shuffle(candidatas)

    if args.amostra:
        candidatas = candidatas[: args.amostra]
        print(f"⚠️ AMOSTRA: {len(candidatas)} posicoes")

    print(
        f"[{args.tipo}] processos: {args.processos} "
        f"(a maquina tem {os.cpu_count()} nucleos logicos)",
        flush=True,
    )

    # ── Fase 1: a peneira ────────────────────────────────────────────────────
    relogio = time.monotonic()
    motivos: Counter[str] = Counter()
    aprovadas: list[str] = []
    for i, (fen, lance, causas) in enumerate(
        _mapear(_peneirar_uma, [(f, args.tipo, parametros) for f in candidatas], args.processos),
        start=1,
    ):
        motivos.update(causas)
        if lance is not None:
            aprovadas.append(fen)
        if i % 50 == 0:
            print(f"  peneira {i}/{len(candidatas)} — passaram {len(aprovadas)}", flush=True)
    print(
        f"peneira: {len(aprovadas)} de {len(candidatas)} "
        f"em {time.monotonic() - relogio:.0f}s"
    )
    for causa, quantas in motivos.most_common(8):
        print(f"    {causa}: {quantas}")

    if not aprovadas:
        print("⛔ nenhuma posicao real resolve este objetivo dentro da janela.")
        return 1

    # ── Fase 2: a medicao nas quatro modalidades ─────────────────────────────
    relogio = time.monotonic()
    bons: list[tuple[int, float, str]] = []
    for fen, lances, _causas in _mapear(
        _medir_uma, [(f, args.tipo, parametros) for f in aprovadas], args.processos
    ):
        validos = [n for n in lances if n is not None]
        if len(validos) >= MINIMO_DE_MODALIDADES:
            bons.append((len(validos), sum(validos) / len(validos), fen))
    bons.sort(key=lambda t: (-t[0], -t[1]))
    print(f"medicao: {len(bons)} moldes em {time.monotonic() - relogio:.0f}s")

    # ── O retrato: material e distancia, que e o que se quer comparar ────────
    if bons:
        material = [sum(pecas_da_fen(f)) for _, _, f in bons]
        print(
            f"material dos aprovados: media {sum(material) / len(material):.1f} "
            f"| min {min(material)} | max {max(material)}"
        )
        distancia: Counter[int] = Counter(round(m) for _, m, _ in bons)
        print("distancia ate o objetivo (lance medio):")
        for lance in sorted(distancia):
            print(f"    {lance} lances: {distancia[lance]}")

    if args.bloco:
        print("\n# ── colar em job/tipos_de_desafio.py ──")
        for _quantas, _media, fen in bons:
            print(f'    "{fen}",')
    return 0


if __name__ == "__main__":
    # ⚠️ Obrigatorio no Windows: `multiprocessing` usa `spawn`, e cada processo
    # filho **reimporta este modulo**. Sem a guarda, cada filho chamaria `main()`
    # de novo e a pesca se multiplicaria sozinha.
    raise SystemExit(main())
