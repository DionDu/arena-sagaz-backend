"""ESCOLHE, na saida da cacada, os moldes que valem a pena guardar.

═══════════════════════════════════════════════════════════════════════════
POR QUE A ESCOLHA E UM PASSO SEPARADO DA CACADA
═══════════════════════════════════════════════════════════════════════════

A cacada aprova tudo o que serve a 3+ modalidades e nao e trivial — o piso dela
e `LANCE_MINIMO = 3`. ⚠️ **Isso e o certo para ela**: medir custa horas, e jogar
fora o resultado por um criterio que pode mudar seria pagar duas vezes.

⛔ **Mas nem todo molde aprovado deve ir para a fila.** Em 11/09/2026 o dono
olhou os desafios publicados e escreveu: *"todos sao resolviveis em 3 lances no
total. O usuario entra pra resolver um desafio e nao joga praticamente nada.
Consegue resolve-los em uns 10 segundos e sai do App?"*. Os moldes em uso tinham
sido cacados com o alvo *"objetivo no lance 3"*, e a fila refletia exatamente
isso.

⚠️ **A distancia ate o objetivo e a medida que separa os dois casos**, e a
cacada ja a anota molde a molde. Este script le aquela saida e corta por ela —
sem rodar motor nenhum, em segundos.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\selecionar_moldes_damas.py moldes1000.txt
    .venv\\Scripts\\python scripts\\selecionar_moldes_damas.py moldes1000.txt --corte 5
    .venv\\Scripts\\python scripts\\selecionar_moldes_damas.py moldes1000.txt --corte 5 --bloco

Sem `--bloco` ele so mostra a distribuicao e quantos sobram em cada corte — e e
assim que se **decide** o corte. Com `--bloco`, imprime as FENs prontas para
colar em `job/tipos_de_desafio.py`.

⚠️ **O arquivo da cacada e UTF-16**, porque o `>` do PowerShell grava assim. Ler
como UTF-8 da `UnicodeDecodeError` no primeiro byte, e o script trata isso — ja
custou uma investigacao.
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: Uma linha de medicao da cacada.
#:
#: `[damas_coroar] medicao 12/549: 4/4 modalidades, lance medio 5.5 (...) — FEN`
LINHA = re.compile(
    r"\[(?P<tipo>\w+)\] medicao \d+/\d+: (?P<modalidades>\d)/4 modalidades, "
    r"lance medio (?P<medio>[\d.]+) .*?([WB]:W[^\s]+)$"
)

#: Quantas modalidades um molde precisa servir para entrar.
#:
#: ⚠️ O mesmo numero da cacada (`MINIMO_DE_MODALIDADES`), repetido aqui porque
#: este script le **texto**, e nao importa o outro modulo — e o texto pode vir de
#: uma cacada antiga, com outro criterio. O corte explicito e o que torna a
#: selecao reproduzivel.
MINIMO_DE_MODALIDADES = 3


def ler(caminho: pathlib.Path) -> str:
    """O conteudo do arquivo, seja ele UTF-16 (PowerShell) ou UTF-8.

    ⚠️ **O BOM some no `lstrip`**: lido como UTF-16-LE sem BOM, o arquivo comeca
    com `\\ufeff`, que nao casa com nenhum padrao e faz a primeira linha
    desaparecer em silencio.
    """
    bruto = caminho.read_bytes()
    if bruto[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return bruto.decode("utf-16").lstrip("﻿")
    try:
        return bruto.decode("utf-8").lstrip("﻿")
    except UnicodeDecodeError:
        return bruto.decode("utf-16-le", errors="replace").lstrip("﻿")


def colher(texto: str) -> dict[str, list[tuple[float, int, str]]]:
    """As medicoes por tipo: `(lance_medio, modalidades, fen)`."""
    achados: dict[str, list[tuple[float, int, str]]] = {}
    for linha in texto.splitlines():
        casou = LINHA.search(linha.strip())
        if not casou:
            continue
        achados.setdefault(casou.group("tipo"), []).append(
            (
                float(casou.group("medio")),
                int(casou.group("modalidades")),
                casou.group(4),
            )
        )
    return achados


def main() -> int:
    """Mostra a distribuicao e, se pedido, o bloco pronto para colar."""
    argumentos = sys.argv[1:]
    if not argumentos:
        raise SystemExit(__doc__ or "")

    bloco = "--bloco" in argumentos
    argumentos = [a for a in argumentos if a != "--bloco"]

    corte = 0.0
    if "--corte" in argumentos:
        onde = argumentos.index("--corte")
        corte = float(argumentos[onde + 1])
        del argumentos[onde : onde + 2]

    texto = ler(pathlib.Path(argumentos[0]))
    por_tipo = colher(texto)
    if not por_tipo:
        raise SystemExit("⛔ nenhuma linha de medicao reconhecida no arquivo")

    for tipo, linhas in por_tipo.items():
        servem = [x for x in linhas if x[1] >= MINIMO_DE_MODALIDADES]
        # ⚠️ Duplicata e desperdicio: a mesma FEN dobra a chance daquela posicao
        # sair na fila, sem acrescentar variedade nenhuma.
        vistas: dict[str, tuple[float, int, str]] = {}
        for medio, modalidades, fen in servem:
            if fen not in vistas:
                vistas[fen] = (medio, modalidades, fen)
        servem = sorted(vistas.values(), reverse=True)

        print(f"\n{'=' * 72}\n{tipo}\n{'=' * 72}")
        print(f"medidos: {len(linhas)}  ·  servem a {MINIMO_DE_MODALIDADES}+: {len(servem)}")

        distribuicao = Counter(round(m) for m, _, _ in servem)
        print("\n  objetivo no lance  ->  moldes   (acumulado deste lance para cima)")
        acumulado = 0
        for lance in sorted(distribuicao, reverse=True):
            acumulado += distribuicao[lance]
            print(f"    {lance:>4}  ->  {distribuicao[lance]:>4}   ({acumulado:>4} com >= {lance})")

        escolhidos = [x for x in servem if x[0] >= corte]
        print(f"\n  com corte >= {corte}: {len(escolhidos)} moldes")

        if bloco:
            print(f"\n# ── {tipo}: {len(escolhidos)} moldes (objetivo no lance >= {corte}) ──")
            for medio, modalidades, fen in escolhidos:
                print(f'    "{fen}",   # {modalidades}/4 modalidades, lance {medio}')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
