"""
Verificacao CIRURGICA do indice 10 do dataset_pequeno_0001.npz
para confrontar a alegacao do Gemini de divergencia.

Gemini alega que:
- Para o indice 10, as jogadas H_2_1, V_7_2, V_7_4 tem score 1.0 no NPZ
  mas o recalculo local da 0.0.

Vamos verificar isso meticulosamente.
"""
import sys
import numpy as np

sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
    TAMANHOS,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

TAMANHO = "pequeno"
LINHAS, COLUNAS = TAMANHOS[TAMANHO]
LABELS_CANONICOS = todos_labels_canonicos(LINHAS, COLUNAS)
NUM_TRACOS = len(LABELS_CANONICOS)
PROFUNDIDADE = 7

# =====================================================================
# CARREGAR O INDICE 10
# =====================================================================
d = np.load(r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz")
labels_npz = [str(l) for l in d["labels_canonicos"]]

IDX = 10
mat = d["estados"][IDX]
qtd = int(d["qtd_tracos"][IDX])
melhor = str(d["melhor_jogada"][IDX])
depth_mj = int(d["depth_melhor_jogada"][IDX])
depth_jog = int(d["depth_jogada"][IDX])
depth_ger = int(d["depth_geracao"][IDX])
scores_mj = d["score_melhor_jogada"][IDX]
scores_jog = d["score_jogada"][IDX]

print("=" * 80)
print(f"ANALISE CIRURGICA - dataset_pequeno_0001.npz, indice {IDX}")
print("=" * 80)
print(f"qtd_tracos: {qtd}")
print(f"melhor_jogada: {melhor}")
print(f"depth_melhor_jogada: {depth_mj}")
print(f"depth_jogada: {depth_jog}")
print(f"depth_geracao: {depth_ger}")
print()

# Mostrar a matriz
print("MATRIZ DO TABULEIRO (NPZ):")
print(mat)
print()

# Mostrar quais tracos estao preenchidos (valor 9)
print("TRACOS PREENCHIDOS:")
for r in range(mat.shape[0]):
    for c in range(mat.shape[1]):
        val = int(mat[r, c])
        if val == 9:
            if r % 2 == 0 and c % 2 == 1:
                print(f"  H_{r}_{c} (horizontal)")
            elif r % 2 == 1 and c % 2 == 0:
                print(f"  V_{r}_{c} (vertical)")
print()

# Mostrar caixas fechadas (valor 1)
print("CAIXAS FECHADAS:")
for r in range(mat.shape[0]):
    for c in range(mat.shape[1]):
        val = int(mat[r, c])
        if val == 1 and r % 2 == 1 and c % 2 == 1:
            print(f"  Caixa em ({r},{c})")
print()

# =====================================================================
# SCORES GRAVADOS NO NPZ
# =====================================================================
print("SCORES GRAVADOS NO NPZ (score_melhor_jogada, Fase 2, depth 7):")
for i, (lb, sc) in enumerate(zip(labels_npz, scores_mj)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.1f}")
print()

print("SCORES GRAVADOS NO NPZ (score_jogada, Fase 1, depth adaptativa):")
for i, (lb, sc) in enumerate(zip(labels_npz, scores_jog)):
    if sc != -1e9:
        print(f"  [{i:2d}] {lb}: {sc:+.1f}")
print()

# =====================================================================
# RECALCULO LOCAL
# =====================================================================

# Reconstruir tabuleiro
def reconstruir_tabuleiro(mat_npz):
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    for r in range(mat_npz.shape[0]):
        for c in range(mat_npz.shape[1]):
            val = int(mat_npz[r, c])
            if val == 9:
                estado.matriz[r, c] = 1
            elif val == 1:
                estado.matriz[r, c] = 1
    return estado

estado = reconstruir_tabuleiro(mat)
disp = estado.tracos_disponiveis()
print(f"Tracos disponiveis (localmente): {len(disp)}")
print(f"  {disp}")
print()

# Verificar que o tabuleiro local bate com o NPZ
print("MATRIZ LOCAL RECONSTRUIDA:")
print(estado.matriz)
print()

# Comparar matrizes
mat_esperada = mat.copy().astype(np.int8)
# No NPZ: 0=vazio, 1=caixa, 8=ponto, 9=aresta
# No local: 0=vazio, 1=jogador(aresta ou caixa), 8=ponto
mat_local = estado.matriz.copy()
for r in range(mat_esperada.shape[0]):
    for c in range(mat_esperada.shape[1]):
        npz_val = int(mat_esperada[r, c])
        loc_val = int(mat_local[r, c])
        if npz_val == 9 and loc_val == 1:
            pass  # OK - aresta
        elif npz_val == 1 and loc_val == 1:
            pass  # OK - caixa
        elif npz_val == 0 and loc_val == 0:
            pass  # OK - vazio
        elif npz_val == 8 and loc_val == 8:
            pass  # OK - ponto
        else:
            print(f"  DIFERENCA em ({r},{c}): NPZ={npz_val}, local={loc_val}")

# Recalcular Minimax
import time
print("Recalculando Minimax com profundidade 7...")
t0 = time.time()
scores_local = _scores_de_todas_jogadas(estado, PROFUNDIDADE)
dt = time.time() - t0
print(f"Tempo: {dt:.2f}s")
print()

# =====================================================================
# COMPARACAO DETALHADA
# =====================================================================
print("COMPARACAO DETALHADA score_melhor_jogada (NPZ) vs recalculo local:")
print(f"{'Idx':>3} {'Label':<6} {'NPZ':>6} {'Local':>6} {'Match':>6}")
print("-" * 35)

divergencias = []
for i, label in enumerate(LABELS_CANONICOS):
    sg = scores_mj[i]
    if label in scores_local:
        sl = float(scores_local[label])
    else:
        sl = -1e9
    
    if sg == -1e9 and sl == -1e9:
        continue
    
    match = "OK" if abs(sg - sl) < 0.01 else "DIFF"
    print(f"{i:3d} {label:<6} {sg:+6.1f} {sl:+6.1f} {match:>6}")
    
    if abs(sg - sl) > 0.01:
        divergencias.append((i, label, sg, sl))

print()

# =====================================================================
# VERIFICACAO ESPECIFICA DAS JOGADAS MENCIONADAS PELO GEMINI
# =====================================================================
print("=" * 80)
print("VERIFICACAO DAS JOGADAS MENCIONADAS PELO GEMINI:")
print("Gemini alega divergencia em: H_2_1, V_7_2, V_7_4")
print("=" * 80)

for label in ["H_2_1", "V_7_2", "V_7_4"]:
    idx_label = LABELS_CANONICOS.index(label) if label in LABELS_CANONICOS else -1
    if idx_label >= 0:
        sg = scores_mj[idx_label]
        sl = scores_local.get(label, None)
        sg_f1 = scores_jog[idx_label]
        print(f"\n  {label} (indice {idx_label}):")
        print(f"    score_melhor_jogada (NPZ, Fase 2): {sg:+.1f}")
        print(f"    score_jogada (NPZ, Fase 1):        {sg_f1:+.1f}")
        print(f"    Recalculo local (depth 7):          {sl:+d}" if sl is not None else "    N/A (traco indisponivel)")
        if sl is not None:
            if abs(sg - sl) < 0.01:
                print(f"    >>> CONFEREM <<<")
            else:
                print(f"    >>> DIVERGEM! NPZ={sg:+.1f} vs Local={sl:+d} <<<")
    else:
        print(f"\n  {label}: NAO ENCONTRADO nos labels canonicos")

print()

# =====================================================================
# RESULTADO FINAL
# =====================================================================
if len(divergencias) == 0:
    print("=" * 80)
    print("RESULTADO: ZERO DIVERGENCIAS no indice 10.")
    print("A alegacao do Gemini NAO se confirma neste recalculo.")
    print("=" * 80)
else:
    print("=" * 80)
    print(f"RESULTADO: {len(divergencias)} DIVERGENCIA(S) ENCONTRADA(S)!")
    for i, label, sg, sl in divergencias:
        print(f"  [{i}] {label}: NPZ={sg:+.1f}, Local={sl:+.1f}")
    print("=" * 80)

# =====================================================================
# BONUS: Testar com profundidades 8, 9, 10, 11 (como Gemini diz ter feito)
# =====================================================================
print()
print("=" * 80)
print("BONUS: Recalculo com multiplas profundidades")
print("=" * 80)

for prof in [8, 9, 10, 11]:
    # Para profundidades altas com poucos tracos, pode ser muito lento
    # So rodar se n_tracos_restantes <= 16
    n_rest = len(disp)
    if n_rest > 16 and prof > 8:
        print(f"\n  Profundidade {prof}: SKIP (muitos tracos restantes = {n_rest})")
        continue
    
    print(f"\n  Profundidade {prof}:")
    t0 = time.time()
    scores_prof = _scores_de_todas_jogadas(estado, prof)
    dt = time.time() - t0
    print(f"    Tempo: {dt:.2f}s")
    
    # Comparar com depth 7
    diffs = []
    for label in disp:
        s7 = scores_local[label]
        sp = scores_prof[label]
        if s7 != sp:
            diffs.append((label, s7, sp))
    
    if diffs:
        print(f"    Diferencas vs depth 7:")
        for lb, s7, sp in diffs:
            print(f"      {lb}: depth7={s7:+d}, depth{prof}={sp:+d}")
    else:
        print(f"    Identico ao depth 7 (todos os scores iguais)")
    
    # Verificar jogadas especificas do Gemini
    for label in ["H_2_1", "V_7_2", "V_7_4"]:
        if label in scores_prof:
            print(f"    {label}: score = {scores_prof[label]:+d}")

d.close()
