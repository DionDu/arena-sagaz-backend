"""Analisa os arquivos `.md` produzidos pelo avaliador (caixas perdidas pela CNN).

Para cada evento:
- Parseia a matriz crua (encoding de partida `{-1, 0, 1, 8}`).
- Normaliza para o encoding de dataset/treino (`{0, 1, 8, 9}` — qualquer
  caixa fechada vira 1, qualquer aresta preenchida vira 9).
- Reaproveita as primitivas do script `analisa_grau3_minimax.py` (grau,
  cadeia, sacrifício) para classificar a decisão errada da CNN.

Saída: tabela por fase do jogo + tabela por adversário + lista dos
"piores estados" (onde a jogada gulosa era trivialmente correta e a
CNN errou — ou seja: nem o Minimax(p=9) nem a heurística Berlekamp
justificam o que a CNN fez).
"""
from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Reaproveita as primitivas já validadas do script anterior.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analisa_grau3_minimax import (  # noqa: E402
    FASE_NOMES,
    LABEL_TO_IDX,
    LABELS_CANONICOS,
    POS_CAIXAS,
    arestas_que_fecham_grau3,
    fase_do_estado,
    grau,
    sacrificio_aplicavel,
    simular_captura_gulosa,
)

RX_MATRIZ = re.compile(
    r"## Matriz crua.*?```text\s*(.*?)\s*```", re.DOTALL
)
RX_TRACO = re.compile(r"Traço jogado pela CNN:\*\*\s*`([^`]+)`")
RX_CAIXAS = re.compile(r"Caixa\(s\) pronta\(s\)[^:]*:\*\*\s*([^\n]+)")
RX_ADVERSARIO = re.compile(r"\*\*Adversário:\*\*\s*`([^`]+)`")
RX_POSICAO = re.compile(r"\*\*Posição da CNN:\*\*\s*([^\n]+)")
RX_JOGADA_NUM = re.compile(r"jogada\s+(\d+)", re.IGNORECASE)


def parse_matriz(texto: str) -> np.ndarray:
    """Lê o bloco textual da matriz crua e retorna ndarray 9×7 int."""
    m = RX_MATRIZ.search(texto)
    if not m:
        raise ValueError("Não encontrei a matriz crua no MD")
    bloco = m.group(1)
    # Remove [, ] e separa por linhas com vírgula.
    bloco_limpo = bloco.replace("[", " ").replace("]", " ")
    linhas = [
        [int(x) for x in re.findall(r"-?\d+", l)]
        for l in bloco_limpo.strip().splitlines()
        if l.strip()
    ]
    arr = np.array(linhas, dtype=np.int16)
    return arr


def normalizar_para_encoding_treino(mat: np.ndarray) -> np.ndarray:
    """Encoding partida {-1,0,1,8} → encoding treino {0,1,8,9}.

    Caixa fechada = qualquer caixa em pos (ímpar, ímpar) com valor != 0.
    Aresta preenchida = pos de aresta com valor != 0 e != 8.
    """
    out = mat.copy()
    h, w = out.shape
    # Pontos fixos permanecem 8; resto vira 0/9 para arestas, 0/1 para caixas.
    for r in range(h):
        for c in range(w):
            v = out[r, c]
            if r % 2 == 0 and c % 2 == 0:
                # Ponto fixo
                out[r, c] = 8
                continue
            if r % 2 == 1 and c % 2 == 1:
                # Caixa: se ocupada por algum jogador (+1 ou -1), vira 1
                out[r, c] = 1 if v != 0 else 0
            else:
                # Aresta: se preenchida (+1 ou -1), vira 9
                out[r, c] = 9 if v != 0 else 0
    return out


def classificar_evento(mat_treino: np.ndarray, traco_cnn_idx: int) -> dict:
    """Classifica a natureza do erro da CNN para um único evento.

    Retorna dict com:
      - fase: 0..3
      - n_grau3: nº de caixas grau-3 disponíveis
      - cnn_jogou_em_grau3: True se a CNN escolheu uma aresta que fecha grau-3
                            (não deveria estar marcada como evento, mas valida)
      - cap_gulosa: tamanho da cadeia gulosa total
      - foi_ciclo: a cadeia gulosa fechou um ciclo?
      - sacrificio_aplicavel: bool — Berlekamp clássico aplicável
      - aresta_cnn: label da aresta jogada
      - tipo_erro: classificação textual
    """
    f = fase_do_estado(mat_treino)
    arestas_fecha = arestas_que_fecham_grau3(mat_treino)
    cap, ciclo = simular_captura_gulosa(mat_treino)
    sac = sacrificio_aplicavel(mat_treino)

    # Caixas grau-3 distintas no estado:
    n_grau3 = sum(
        1 for (r, c) in POS_CAIXAS
        if mat_treino[r, c] != 1 and grau(mat_treino, r, c) == 3
    )

    cnn_jogou_em_grau3 = traco_cnn_idx in arestas_fecha

    # Tipo de erro:
    if cnn_jogou_em_grau3:
        tipo = "FALSO_POSITIVO_AVALIADOR"  # avaliador marcou mas era captura
    elif sac:
        # A heurística Berlekamp diz que sacrifício é racional. Mesmo assim,
        # se o evento foi gerado, a CNN escolheu a opção errada de sacrifício
        # (jogou em outra aresta que não fecha grau-3, mas que tampouco é o
        # double-dealing correto). Vamos chamar isso de "tentou_sacrificio".
        tipo = "PROVAVEL_SACRIFICIO"
    elif cap >= 2:
        # Cadeia de 2: existe a "exceção curta" — sacrifício de 2 caixas.
        tipo = "CADEIA_CURTA_2"
    elif cap == 1:
        # Apenas 1 caixa grau-3 isolada: o "guloso correto" é capturar,
        # nada justifica a CNN não ter feito.
        tipo = "ERRO_TRIVIAL"
    else:
        tipo = "INCLASSIFICAVEL"

    return {
        "fase": f,
        "n_grau3": n_grau3,
        "cnn_jogou_em_grau3": cnn_jogou_em_grau3,
        "cap_gulosa": cap,
        "foi_ciclo": ciclo,
        "sacrificio_aplicavel": sac,
        "tipo_erro": tipo,
    }


def parse_md(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8", errors="replace")
    mat_partida = parse_matriz(txt)
    mat_treino = normalizar_para_encoding_treino(mat_partida)

    m_traco = RX_TRACO.search(txt)
    traco = m_traco.group(1) if m_traco else None
    traco_idx = LABEL_TO_IDX.get(traco) if traco else None

    m_adv = RX_ADVERSARIO.search(txt)
    adversario = m_adv.group(1) if m_adv else "?"

    return {
        "path": path,
        "traco_cnn": traco,
        "traco_cnn_idx": traco_idx,
        "adversario": adversario,
        "mat_partida": mat_partida,
        "mat_treino": mat_treino,
    }


def analisar_pasta(pasta_exec: Path) -> None:
    arquivos = sorted(pasta_exec.rglob("*.md"))
    if not arquivos:
        raise SystemExit(f"Nenhum .md em {pasta_exec}")
    print(f"Analisando {len(arquivos)} eventos em {pasta_exec}")

    total_por_fase = defaultdict(int)
    por_fase_tipo = defaultdict(lambda: defaultdict(int))  # fase -> tipo -> n
    por_adversario = defaultdict(lambda: defaultdict(int))
    por_n_grau3 = defaultdict(int)
    triviais: List[Tuple[Path, dict, dict]] = []

    falhas = 0
    for arq in arquivos:
        try:
            ev = parse_md(arq)
        except Exception as e:  # parsing ruim
            falhas += 1
            continue
        if ev["traco_cnn_idx"] is None:
            falhas += 1
            continue

        cls = classificar_evento(ev["mat_treino"], ev["traco_cnn_idx"])
        f = cls["fase"]
        total_por_fase[f] += 1
        por_fase_tipo[f][cls["tipo_erro"]] += 1
        por_adversario[ev["adversario"]][cls["tipo_erro"]] += 1
        por_n_grau3[cls["n_grau3"]] += 1

        if cls["tipo_erro"] == "ERRO_TRIVIAL" and len(triviais) < 8:
            triviais.append((arq, ev, cls))

    if falhas:
        print(f"  (avisos: {falhas} arquivos não parseados)")

    # ---------- Tabela 1: por fase × tipo de erro -------------------------
    tipos = ["ERRO_TRIVIAL", "CADEIA_CURTA_2", "PROVAVEL_SACRIFICIO",
             "FALSO_POSITIVO_AVALIADOR", "INCLASSIFICAVEL"]
    print()
    print("=" * 96)
    print("CAIXAS PERDIDAS PELA CNN — distribuição por fase do jogo × tipo de erro")
    print("=" * 96)
    hdr = f'{"Fase":<22}{"Total":>8}'
    for t in tipos:
        hdr += f'{t:>26}'
    print(hdr)
    print("-" * len(hdr))
    for f in (0, 1, 2, 3):
        linha = f'{FASE_NOMES[f]:<22}{total_por_fase[f]:>8}'
        for t in tipos:
            linha += f'{por_fase_tipo[f][t]:>26}'
        print(linha)
    tot = sum(total_por_fase.values())
    linha = f'{"TOTAL":<22}{tot:>8}'
    for t in tipos:
        n = sum(por_fase_tipo[f][t] for f in (0, 1, 2, 3))
        linha += f'{n:>26}'
    print(linha)

    # ---------- Tabela 2: por adversário × tipo de erro -------------------
    print()
    print("=" * 96)
    print("Por adversário × tipo de erro")
    print("=" * 96)
    hdr = f'{"Adversário":<20}{"Total":>8}'
    for t in tipos:
        hdr += f'{t:>26}'
    print(hdr)
    print("-" * len(hdr))
    for adv in sorted(por_adversario):
        total_adv = sum(por_adversario[adv].values())
        linha = f'{adv:<20}{total_adv:>8}'
        for t in tipos:
            linha += f'{por_adversario[adv][t]:>26}'
        print(linha)

    # ---------- Tabela 3: distribuição por nº de caixas grau-3 ------------
    print()
    print("Distribuição dos eventos por nº de caixas grau-3 oferecidas:")
    for n in sorted(por_n_grau3):
        print(f"  {n} caixa(s) grau-3: {por_n_grau3[n]:>5} eventos")

    # ---------- Exemplos de erros triviais --------------------------------
    if triviais:
        print()
        print("=" * 96)
        print("Exemplos de ERRO TRIVIAL (1 caixa grau-3 isolada, sem cadeia)")
        print("=" * 96)
        for (arq, ev, cls) in triviais:
            arestas_ok = sorted(
                LABELS_CANONICOS[i] for i in arestas_que_fecham_grau3(ev["mat_treino"])
            )
            print()
            print(f"  {arq.name}")
            print(f"    adversário={ev['adversario']}  fase={FASE_NOMES[cls['fase']]}")
            print(f"    aresta gulosa correta: {arestas_ok}")
            print(f"    aresta jogada pela CNN: {ev['traco_cnn']}")
            print("    matriz (encoding treino):")
            for row in ev["mat_treino"]:
                print("     ", " ".join(f"{int(v):2d}" for v in row))


def main():
    if len(sys.argv) < 2:
        # Default: pega a execução mais recente.
        base = Path(__file__).resolve().parent.parent / "visualizacoes" / "avaliacao_partidas"
        execs = sorted([p for p in base.iterdir() if p.is_dir()])
        if not execs:
            raise SystemExit("Sem execuções em visualizacoes/avaliacao_partidas")
        pasta = execs[-1]
    else:
        pasta = Path(sys.argv[1])

    print(f"Pasta de execução: {pasta}")
    analisar_pasta(pasta)


if __name__ == "__main__":
    main()
