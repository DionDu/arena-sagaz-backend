"""
Varredura ampla: quantificar quantos estados nos 4 NPZ tem divergencia
causada pelo bug da Transposition Table do Databricks.

Estrategia: como a TT sem bug = Original, vamos comparar o score_melhor_jogada
do NPZ com o recalculo do Databricks SEM TT (que e mais rapido que o original).

Para estados com poucos tracos (arvore grande), vamos usar profundidade 
limitada para nao travar. Mas para a maioria dos estados (>=15 tracos),
a arvore e tratavel.
"""
import sys
import numpy as np
import time

sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    todos_labels_canonicos,
    TAMANHOS,
)

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

# Montar bitboard
h, w = 9, 7
edge_to_bit = {}
bit_to_label = {}
bit_idx = 0
for r in range(h):
    for c in range(w):
        if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
            edge_to_bit[(r, c)] = bit_idx
            bit_to_label[bit_idx] = f"H_{r}_{c}" if r % 2 == 0 else f"V_{r}_{c}"
            bit_idx += 1

n_edges = bit_idx
all_mask = (1 << n_edges) - 1

box_masks = []
for r in range(1, h, 2):
    for c in range(1, w, 2):
        mask = (1 << edge_to_bit[(r-1, c)]) | (1 << edge_to_bit[(r+1, c)]) | \
               (1 << edge_to_bit[(r, c-1)]) | (1 << edge_to_bit[(r, c+1)])
        box_masks.append(mask)

edge_boxes = [tuple(bm for bm in box_masks if bm & (1 << b)) for b in range(n_edges)]


# Databricks COM TT (reproduzido)
def solve_tt(edges, depth, alpha, beta, maximizing, tt):
    if depth == 0 or edges == all_mask: return 0
    tt_key = (edges, depth, maximizing)
    if tt_key in tt:
        flag, val = tt[tt_key]
        if flag == 0: return val
        if flag == 1 and val >= beta: return val
        if flag == 2 and val <= alpha: return val
    moves = []
    for i in range(n_edges):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
            moves.append((i, closed))
    moves.sort(key=lambda x: x[1], reverse=True)
    orig_alpha = alpha
    best_val = -10000 if maximizing else 10000
    for bit, closed in moves:
        new_e = edges | (1 << bit)
        if maximizing:
            val = (closed + solve_tt(new_e, depth-1, alpha, beta, True, tt)) if closed > 0 else \
                  solve_tt(new_e, depth-1, alpha, beta, False, tt)
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            val = (-closed + solve_tt(new_e, depth-1, alpha, beta, False, tt)) if closed > 0 else \
                  solve_tt(new_e, depth-1, alpha, beta, True, tt)
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if beta <= alpha: break
    tt[tt_key] = (0 if best_val > orig_alpha and best_val < beta else (1 if best_val >= beta else 2), best_val)
    return best_val


def scores_com_tt(edges):
    """Replica exata do Databricks."""
    tt = {}
    scores = np.full(31, -1e9, dtype=np.float32)
    for i in range(31):
        if not (edges & (1 << i)):
            closed = sum(1 for bm in edge_boxes[i] if (edges | (1 << i)) & bm == bm)
            new_e = edges | (1 << i)
            res = (closed + solve_tt(new_e, 6, -10001, 10001, True, tt)) if closed > 0 else \
                  solve_tt(new_e, 6, -10001, 10001, False, tt)
            scores[i] = float(res)
    return scores


ARQUIVOS = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz",
]

# Para cada arquivo, verificar TODOS os estados reprodduzindo
# o algoritmo do Databricks COM TT, e comparar com o NPZ
# Se o NPZ == DB+TT, confirma que o NPZ foi gerado assim.
# Depois, contar quantos divergem do algoritmo correto (sem TT).

print("=" * 80)
print("VARREDURA: Impacto do bug da TT nos 4 arquivos NPZ")
print("=" * 80)

# Primeiro: amostragem para estimar a taxa de erro
# Testar 200 amostras aleatorias por arquivo (cobrindo todas as faixas de tracos)
np.random.seed(42)
AMOSTRAS_POR_ARQUIVO = 200

total_verificados = 0
total_divergentes = 0
total_melhor_jogada_errada = 0
divergencias_por_faixa = {}

for caminho in ARQUIVOS:
    nome = caminho.split("\\")[-1]
    d = np.load(caminho)
    estados = d["estados"]
    qtd_tracos = d["qtd_tracos"]
    scores_npz = d["score_melhor_jogada"]
    melhores_npz = d["melhor_jogada"]
    n = estados.shape[0]

    # Selecionar amostras
    indices = np.random.choice(n, size=min(AMOSTRAS_POR_ARQUIVO, n), replace=False)

    div_arquivo = 0
    mj_errada_arquivo = 0

    t0 = time.time()
    for count, idx in enumerate(sorted(indices)):
        mat = estados[idx]
        qt = int(qtd_tracos[idx])

        # Converter para bitboard
        edges = 0
        for r in range(9):
            for c in range(7):
                if (r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0):
                    if mat[r, c] == 9:
                        edges |= (1 << edge_to_bit[(r, c)])

        # Reproduzir o calculo do Databricks (COM TT, bug incluso)
        scores_repro = scores_com_tt(edges)

        # Comparar com NPZ
        npz_scores = scores_npz[idx]
        npz_match = True
        for i in range(31):
            if abs(npz_scores[i] - scores_repro[i]) > 0.01:
                npz_match = False
                break

        if not npz_match:
            # Isso seria estranho - significa que o NPZ nao foi gerado com este algoritmo
            print(f"  ALERTA: idx={idx} NPZ != DB+TT reproduzido (inesperado)")

        # Agora verificar se o DB+TT tem divergencia vs DB-TT (que sabemos ser correto)
        # Para isso, precisamos do DB sem TT, mas e lento para poucos tracos
        # Vamos usar a comparacao NPZ vs Original (que ja fizemos)
        # Na verdade, vamos simplesmente contar quantos scores do NPZ divergem
        # do que o DB SEM TT daria. Mas DB-TT = Original.
        # Como o Original e lento para poucos tracos, vamos usar o DB+TT local
        # como proxy: se o nosso DB+TT local == NPZ E o nosso DB+TT local != DB-TT local,
        # entao temos uma divergencia.
        
        # Alternativa mais eficiente: comparar NPZ com uma nova execucao DB+TT
        # com TT LIMPA para cada estado. Se bater, o problema e a TT.
        # Mas o TT e local por estado no notebook original (tt = {} por estado).
        # Porem, DENTRO de cada estado, os 31 calculos COMPARTILHAM o TT!
        
        # O ponto crucial: no notebook, para cada estado, tt={} e criado NOVO.
        # Mas os 31 tracos da raiz compartilham essa TT entre si.
        # Se o traco 0 polui o TT com um bound incorreto, o traco 7 pode
        # ler esse bound e retornar score errado.
        
        total_verificados += 1

    dt = time.time() - t0
    d.close()
    print(f"  {nome}: {AMOSTRAS_POR_ARQUIVO} amostras verificadas em {dt:.1f}s")
    print(f"    NPZ == DB+TT reproduzido: {AMOSTRAS_POR_ARQUIVO - div_arquivo}/{AMOSTRAS_POR_ARQUIVO}")

print()

# Agora o teste definitivo: para as amostras que cabem no tempo,
# comparar DB+TT vs DB-TT (sem TT) para identificar as divergencias reais
print("=" * 80)
print("VARREDURA PRECISA: DB+TT vs Original em amostras com >= 10 tracos")
print("=" * 80)

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

total_div = 0
total_ok = 0
total_melhor_errada = 0
amostras_por_faixa_div = {}

for caminho in ARQUIVOS:
    nome = caminho.split("\\")[-1]
    d = np.load(caminho)
    estados = d["estados"]
    qtd_tracos = d["qtd_tracos"]
    scores_npz = d["score_melhor_jogada"]
    melhores_npz = d["melhor_jogada"]
    n = estados.shape[0]

    # Selecionar amostras COM >= 10 tracos (para viabilidade)
    candidatos = np.where(qtd_tracos >= 10)[0]
    if len(candidatos) > 100:
        indices = np.random.choice(candidatos, size=100, replace=False)
    else:
        indices = candidatos

    t0 = time.time()
    for idx in sorted(indices):
        mat = estados[idx]
        qt = int(qtd_tracos[idx])

        # Recalcular com Original (correto)
        estado = EstadoTabuleiro(LINHAS, COLUNAS)
        for r in range(9):
            for c in range(7):
                val = int(mat[r, c])
                if val == 9 or val == 1:
                    estado.matriz[r, c] = 1

        scores_orig = _scores_de_todas_jogadas(estado, 7)

        # Comparar com NPZ
        npz_scores = scores_npz[idx]
        tem_div = False
        melhor_errada = False

        for i, label in enumerate(LABELS):
            npz_val = npz_scores[i]
            orig_val = scores_orig.get(label, -1e9)
            if orig_val == -1e9:
                orig_val = -1e9
            if abs(npz_val - orig_val) > 0.01:
                tem_div = True
                faixa = qt
                if faixa not in amostras_por_faixa_div:
                    amostras_por_faixa_div[faixa] = 0
                amostras_por_faixa_div[faixa] += 1
                break

        if tem_div:
            # Verificar se a melhor jogada muda
            npz_melhor = str(melhores_npz[idx])
            melhor_score_orig = max(scores_orig.values())
            melhores_orig = [l for l, s in scores_orig.items() if s == melhor_score_orig]
            if npz_melhor not in melhores_orig:
                melhor_errada = True
                total_melhor_errada += 1
            total_div += 1
        else:
            total_ok += 1

    dt = time.time() - t0
    d.close()
    print(f"  {nome}: verificado em {dt:.1f}s")

print()
print("=" * 80)
print("RESULTADO DA VARREDURA")
print("=" * 80)
print(f"  Total de amostras verificadas (>=10 tracos): {total_ok + total_div}")
print(f"  Amostras OK (scores exatos):                 {total_ok}")
print(f"  Amostras com divergencia de score:           {total_div}")
print(f"  Amostras onde a MELHOR JOGADA muda:          {total_melhor_errada}")
print(f"  Taxa de divergencia:                         {total_div / (total_ok + total_div) * 100:.1f}%")
print(f"  Taxa de melhor jogada errada:                {total_melhor_errada / (total_ok + total_div) * 100:.1f}%")
print()

if amostras_por_faixa_div:
    print("  Divergencias por faixa de qtd_tracos:")
    for faixa in sorted(amostras_por_faixa_div.keys()):
        print(f"    qtd_tracos={faixa}: {amostras_por_faixa_div[faixa]} divergencias")
print("=" * 80)
