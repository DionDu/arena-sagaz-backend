"""PESCA posicoes do Jogo dos Pontinhos em PARTIDAS REAIS, no formato do acervo.

═══════════════════════════════════════════════════════════════════════════
⚠️ NO PONTINHOS, A POSICAO **E** A SEQUENCIA DE LANCES
═══════════════════════════════════════════════════════════════════════════

Nas damas foi preciso guardar a FEN de cada posicao (`co_fen_antes`) porque um
tabuleiro de damas nao se deduz da lista de lances sem reproduzi-los. No
Pontinhos nao ha esse problema: **o tabuleiro e o conjunto de tracos marcados**,
e nada mais. Marcar `H_0_1` nunca desmarca nada.

⚠️ **Consequencia: todo PREFIXO de uma partida real e uma posicao real.** Uma
partida de 24 lances entrega 24 posicoes, sem motor, sem busca e sem custo. E por
isso que pescar Pontinhos e uma conversao, enquanto pescar damas custou horas de
Sagaz (`scripts/pescar_moldes_de_partidas.py`).

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ISTO **NAO** CONSERTA — E PRECISA ESTAR DITO
═══════════════════════════════════════════════════════════════════════════

O dono relatou: *"Os desafios dos pontinhos selecionado sao quase sempre baseados
em uma jogada errada do personagem."*

⚠️ **Trocar a fonte das posicoes nao resolve isso sozinho.** Quem escolhe qual
posicao vira desafio e o gerador, e ele escolhe pela pergunta *"o objetivo cai
aqui?"*. Como o objetivo de hoje e *"feche N caixas"*, e como no Jogo dos
Pontinhos **fechar uma cadeia exige que o adversario a abra**, a selecao continua
concentrada no instante seguinte a uma abertura — venha a posicao de onde vier.

⚠️ **E a abertura nao e um erro**: medida nas 167 partidas do `des`, 253 turnos
fecharam 3 ou mais caixas e 69 fecharam 6 ou mais. Abrir cadeia e como o jogo
termina — alguem e obrigado. O que pescar muda e a **distribuicao**: o acervo de
hoje vem de autoplay (CNN contra CNN, 897 mil posicoes), e as partidas reais tem
uma pessoa de um dos lados.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\pescar_posicoes_pontinhos.py lances_pontinhos.csv ^
        --saida dados\\jogo_pontinhos\\posicoes_reais_pequeno.npz

O CSV precisa de `id_partida`, `nu_ordem`, `co_aresta` e `co_variante` —
⚠️ **`nu_ordem` nao e opcional**: sem ela nao ha prefixo, so um saco de tracos.
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

import numpy as np

# O script mora em `scripts/`, e importa `job/`, que e irmao dele.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows e cp1252; sem isto um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from job.posicoes_de_autoplay_pontinhos import (  # noqa: E402
    TRACOS_DO_TABULEIRO,
    carregar,
)

#: So o tabuleiro pequeno (4x3, 31 tracos) tem acervo e tem desafio hoje.
VARIANTE = "pequeno"


def ordem_canonica_dos_rotulos() -> tuple[str, ...]:
    """Os 31 rotulos na ordem do acervo de autoplay.

    ⛔ **Nao inventa uma ordem propria, e isto e a decisao mais importante do
    arquivo.** A posicao viaja como **bitmask**: o bit `i` e o traco
    `co_rotulo[i]`. Duas ordens diferentes produzem mascaras que parecem iguais e
    significam tabuleiros diferentes — e nada denunciaria, porque os dois arquivos
    seriam NPZ bem formados com numeros plausiveis dentro.

    ⚠️ Por isso a ordem e **lida do acervo que ja existe**, e nao derivada de
    `H`/`V` mais coordenada: o dia em que alguem mudar a derivacao, este arquivo
    acompanha sozinho.
    """
    return carregar().co_rotulo


def ler_partidas(caminho: Path) -> dict[str, list[str]]:
    """Agrupa os lances por partida, em ordem.

    ⚠️ **Ordena por `nu_ordem` aqui, e nao confia no `ORDER BY` da consulta.** O
    CSV pode ter sido gerado por outra mao, aberto no Excel e salvo de volta; a
    ordem e a unica coisa que este script nao consegue recuperar se vier errada,
    entao ela e reimposta.

    Returns:
        `{id_partida: [rotulo, rotulo, ...]}`, so do tabuleiro pequeno.
    """
    # ⚠️ `utf-8-sig`: o export do Postgres no Windows escreve BOM, e sem isto a
    # primeira coluna se chamaria `﻿id_partida` — parece certo na tela e falha.
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = [
            linha
            for linha in csv.DictReader(arquivo)
            if linha.get("co_variante", VARIANTE) == VARIANTE
        ]

    por_partida: dict[str, list[tuple[int, str]]] = collections.defaultdict(list)
    for linha in linhas:
        por_partida[linha["id_partida"]].append(
            (int(linha["nu_ordem"]), linha["co_aresta"])
        )

    return {
        id_partida: [rotulo for _ordem, rotulo in sorted(lances)]
        for id_partida, lances in por_partida.items()
    }


def mascaras_dos_prefixos(
    partidas: dict[str, list[str]], rotulos: tuple[str, ...]
) -> tuple[set[int], collections.Counter]:
    """Todo prefixo de toda partida, como bitmask.

    ⚠️ **A posicao VAZIA nao entra.** O prefixo de zero lances e o tabuleiro
    inicial, igual para todo mundo: ele nao e uma posicao pescada, e incluí-lo
    faria o acervo prometer variedade que nao tem na fase 0.

    ⚠️ **Um traco repetido interrompe a partida**, em vez de ser ignorado. Marcar
    duas vezes o mesmo traco e impossivel no jogo; se aparecer no CSV, a linha
    esta corrompida ou a ordem veio errada — e dali para a frente **todos** os
    prefixos daquela partida estariam errados, nao so aquele.

    Returns:
        O conjunto de mascaras distintas e um contador dos motivos de descarte.
    """
    indice = {rotulo: bit for bit, rotulo in enumerate(rotulos)}
    vistas: set[int] = set()
    motivos: collections.Counter = collections.Counter()

    for id_partida, lances in partidas.items():
        mascara = 0
        for rotulo in lances:
            bit = indice.get(rotulo)
            if bit is None:
                motivos[f"rotulo_fora_do_tabuleiro:{rotulo}"] += 1
                break
            if mascara >> bit & 1:
                motivos["traco_repetido"] += 1
                break
            mascara |= 1 << bit
            vistas.add(mascara)
        else:
            motivos["partida_inteira"] += 1
            continue
        motivos["partida_interrompida"] += 1

    return vistas, motivos


def gravar(mascaras: set[int], rotulos: tuple[str, ...], saida: Path) -> None:
    """Grava o NPZ no formato que `posicoes_de_autoplay_pontinhos.carregar` espera.

    ⚠️ **A ordenacao e parte do contrato, e nao enfeite:** o acervo indexa por
    quantidade de tracos (`Acervo.com_tracos`) assumindo que as posicoes com `n`
    tracos formam uma **fatia contigua**. Ordenar por `(popcount, valor)` e o que
    torna isso verdade. Um arquivo desordenado carregaria sem erro e devolveria
    posicoes da fase errada.
    """
    ordenadas = sorted(mascaras, key=lambda m: (int(m).bit_count(), m))
    saida.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        saida,
        nu_mascara=np.array(ordenadas, dtype=np.uint32),
        co_rotulo=np.array(rotulos),
    )


def main() -> int:
    """Le, converte, grava e mostra o retrato por fase da partida."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivo", type=Path, help="CSV com os lances (id_partida, nu_ordem, co_aresta)")
    ap.add_argument(
        "--saida",
        type=Path,
        default=RAIZ / "dados" / "jogo_pontinhos" / "posicoes_reais_pequeno.npz",
    )
    args = ap.parse_args()

    rotulos = ordem_canonica_dos_rotulos()
    if len(rotulos) != TRACOS_DO_TABULEIRO:
        raise SystemExit(f"⛔ o acervo de referencia tem {len(rotulos)} rotulos")

    partidas = ler_partidas(args.arquivo)
    print(f"partidas ({VARIANTE}): {len(partidas)}")
    print(f"lances: {sum(len(l) for l in partidas.values())}")

    mascaras, motivos = mascaras_dos_prefixos(partidas, rotulos)
    print(f"posicoes distintas: {len(mascaras)}")
    for motivo, quantas in motivos.most_common():
        print(f"    {motivo}: {quantas}")

    # O retrato por fase: e por fase que o gerador consulta o acervo, entao e
    # aqui que se ve se ha posicao para o `nu_lances_de_preparo` do editorial.
    por_fase: collections.Counter = collections.Counter(
        int(m).bit_count() for m in mascaras
    )
    print("posicoes por quantidade de tracos:")
    for fase in sorted(por_fase):
        print(f"    {fase:2d} tracos: {por_fase[fase]}")

    gravar(mascaras, rotulos, args.saida)
    print(f"gravado: {args.saida} ({args.saida.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
