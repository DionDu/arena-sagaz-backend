"""T148 (spec 010), passo 1 - a distância de cada figura nas posições do acervo.

═══════════════════════════════════════════════════════════════════════════
A PERGUNTA
═══════════════════════════════════════════════════════════════════════════

O "Forme a figura" (tipo 51) tira o prazo da posição: `M = distância + folga`
(histórico do backend, "2026-10-23 (2)"). A prova da geração aceita só a
distância de 2 a 6, uma faixa **provisória** escrita antes de saber o que o
acervo tem. A proposta (`PROPOSTA-revisao-catalogo-quatro.md` §2, "Como medir",
passo 3) manda medir antes da pescaria: *"figura que quase nunca tem lugar sai
antes de gastar a pescaria"*.

Este script responde, para cada figura do catálogo, em quantas posições do
acervo (as que o gerador sorteia: de `preparo` a `preparo + 6` lances jogados)
a distância é 0, 1, 2, ..., e em quantas a figura não cabe sem conflito em
lugar nenhum (`sem lugar`). É conta pura (a mesma `figuras_quatro.distancia`
que o gerador e a prova usam), sem busca e sem motor: segundos.

═══════════════════════════════════════════════════════════════════════════
O CONTROLE, ANTES DA MEDIÇÃO
═══════════════════════════════════════════════════════════════════════════

No tabuleiro VAZIO a distância de cada figura é conhecida de cabeça: as peças
dela mais os apoios desde o chão (`pecas` + `apoios_desde_o_chao`, a tabela da
proposta, que o `test_figuras_quatro.py` já confere por extenso). Se a conta
deste script não der isso no vazio, ele para: a tabela mediria o script.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\sondar_distancia_das_figuras_quatro.py

Opções: `--preparo 10` (o `nu_lances_de_preparo` das variantes da figura).

═══════════════════════════════════════════════════════════════════════════
O QUE OLHAR PRIMEIRO NA SAÍDA
═══════════════════════════════════════════════════════════════════════════

1. a linha do CONTROLE (tem de ser "11 de 11");
2. a coluna `na faixa`: a fração das posições em que a prova de hoje (2 a 6)
   aceitaria a figura. Figura com fração baixa quase não gera candidato;
3. as colunas `0` e `1`: a figura já formada ou formável num lance (recusada);
   e `sem lugar` (descartada no gerador).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# Um script em `scripts/` não é pacote: sem isto, `from job import ...` falha.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# O console do Windows é cp1252; sem isto o primeiro `×` derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from job import figuras_quatro as figuras_mod  # noqa: E402
from job import posicoes_de_autoplay_quatro as acervo_mod  # noqa: E402
from job.gerador import JANELA_DO_PREPARO_QUATRO  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro  # noqa: E402

#: A modalidade do único acervo do Quatro.
MODALIDADE = "tradicional"

#: A maior distância que a tabela mostra numa coluna própria; daí para cima, "7+".
MAIOR_COLUNA = 7


def posicoes_distintas(preparo: int) -> list[tuple[str, ...]]:
    """Os prefixos DIFERENTES do acervo, com o comprimento que o gerador sorteia.

    ⚠️ Distintos, e não um por partida: aberturas iguais repetiriam a mesma
    posição, e a fração pesaria a abertura mais comum do autoplay.
    """
    acervo = acervo_mod.carregar(MODALIDADE)
    vistas: set[tuple[str, ...]] = set()
    for partida in acervo.partidas:
        # O mesmo corte do `sortear`: de `preparo` até `preparo + janela`, e no
        # máximo um lance antes do fim da partida.
        teto = min(preparo + JANELA_DO_PREPARO_QUATRO, len(partida.lances) - 1)
        for comprimento in range(preparo, teto + 1):
            vistas.add(partida.lances[:comprimento])
    return sorted(vistas)


def conferir_controle(arbitro: MotorQuatro, dimensoes) -> None:
    """No tabuleiro vazio, a distância é peças + apoios desde o chão."""
    vazio = arbitro.tabuleiro(EstadoQuatro(MODALIDADE, ()))
    certos = 0
    for figura in figuras_mod.FIGURAS_QUATRO.values():
        x, o = figuras_mod.pecas(figura.desenho)
        esperado = x + o + figuras_mod.apoios_desde_o_chao(figura.desenho)
        medido = figuras_mod.distancia(figura, vazio, dimensoes)
        certos += medido == esperado
        if medido != esperado:
            print(f"  ⚠️ {figura.nome}: esperado {esperado}, medido {medido}")
    total = len(figuras_mod.FIGURAS_QUATRO)
    print(f"CONTROLE (tabuleiro vazio): {certos} de {total}")
    if certos != total:
        sys.exit("O controle falhou: a tabela abaixo mediria o script.")


def principal() -> None:
    """Imprime a distribuição da distância de cada figura no acervo."""
    leitor = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    leitor.add_argument("--preparo", type=int, default=10)
    args = leitor.parse_args()

    arbitro = MotorQuatro(MODALIDADE)
    dimensoes = contrato_quatro.dimensoes(MODALIDADE)
    conferir_controle(arbitro, dimensoes)

    prefixos = posicoes_distintas(args.preparo)
    # Os tabuleiros uma vez só: são os mesmos para as onze figuras.
    tabuleiros = [arbitro.tabuleiro(EstadoQuatro(MODALIDADE, p)) for p in prefixos]
    print(
        f"\n{len(tabuleiros)} posições distintas, com {args.preparo} a "
        f"{args.preparo + JANELA_DO_PREPARO_QUATRO} lances jogados.\n"
    )

    faixa = range(
        figuras_mod.DISTANCIA_MINIMA_DA_FIGURA, figuras_mod.DISTANCIA_MAXIMA_DA_FIGURA + 1
    )
    colunas = [str(d) for d in range(MAIOR_COLUNA)] + [f"{MAIOR_COLUNA}+", "sem lugar"]
    print(f"{'figura':<10} {'família':<9} " + " ".join(f"{c:>6}" for c in colunas)
          + f" {'na faixa':>9}")
    for figura in figuras_mod.FIGURAS_QUATRO.values():
        contagem: Counter = Counter()
        for tabuleiro in tabuleiros:
            d = figuras_mod.distancia(figura, tabuleiro, dimensoes)
            if d is None:
                contagem["sem lugar"] += 1
            elif d >= MAIOR_COLUNA:
                contagem[f"{MAIOR_COLUNA}+"] += 1
            else:
                contagem[str(d)] += 1
        na_faixa = sum(contagem[str(d)] for d in faixa if d < MAIOR_COLUNA)
        print(
            f"{figura.nome:<10} {figura.familia:<9} "
            + " ".join(f"{contagem[c]:>6}" for c in colunas)
            + f" {na_faixa / len(tabuleiros):>8.0%}"
        )


if __name__ == "__main__":
    principal()
