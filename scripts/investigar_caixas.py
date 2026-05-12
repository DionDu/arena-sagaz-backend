"""Investigar se o bitboard trata caixas pre-fechadas diferente do original."""
import sys, numpy as np
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import minimax

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

# Matriz do idx=44
mat = np.array([
    [8, 9, 8, 9, 8, 9, 8],
    [0, 0, 9, 1, 9, 1, 9],
    [8, 0, 8, 9, 8, 9, 8],
    [0, 0, 0, 0, 0, 0, 9],
    [8, 9, 8, 0, 8, 0, 8],
    [9, 0, 0, 0, 9, 0, 9],
    [8, 0, 8, 9, 8, 0, 8],
    [0, 0, 9, 0, 0, 0, 0],
    [8, 0, 8, 0, 8, 0, 8]
], dtype=np.int8)

print("Matriz NPZ:")
print(mat)
print()

# Caixas ja fechadas no NPZ (valor 1 em posicao impar x impar)
print("Caixas ja fechadas:")
for r in range(1,9,2):
    for c in range(1,7,2):
        if mat[r,c] == 1:
            print(f"  ({r},{c}) = FECHADA")
            # Verificar se os 4 lados estao preenchidos
            lados = [mat[r-1,c], mat[r+1,c], mat[r,c-1], mat[r,c+1]]
            print(f"    Lados: cima={lados[0]}, baixo={lados[1]}, esq={lados[2]}, dir={lados[3]}")

# Reconstruir no Original
estado = EstadoTabuleiro(LINHAS, COLUNAS)
for r in range(9):
    for c in range(7):
        v = int(mat[r,c])
        if v == 9 or v == 1:
            estado.matriz[r,c] = 1

print("\nMatriz Original reconstruida:")
print(estado.matriz)

# Testar jogada H_4_5 (indice 16) no Original
label = "H_4_5"
estado2 = estado.clonar()
fechadas = estado2.aplicar_traco(label, 1)
print(f"\nAplicar {label}: fecha {fechadas} caixa(s)")

# No bitboard: H_4_5 esta em qual bit?
h, w = 9, 7
edge_to_bit = {}
bit_idx = 0
for r in range(h):
    for c in range(w):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            edge_to_bit[(r,c)] = bit_idx
            bit_idx += 1

n_edges = bit_idx
all_mask = (1 << n_edges) - 1
box_masks = []
for r in range(1,h,2):
    for c in range(1,w,2):
        mask = (1<<edge_to_bit[(r-1,c)])|(1<<edge_to_bit[(r+1,c)])|(1<<edge_to_bit[(r,c-1)])|(1<<edge_to_bit[(r,c+1)])
        box_masks.append(mask)
edge_boxes = [tuple(bm for bm in box_masks if bm&(1<<b)) for b in range(n_edges)]

# Converter para bitboard
edges = 0
for r in range(9):
    for c in range(7):
        if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
            if mat[r,c] == 9:
                edges |= (1 << edge_to_bit[(r,c)])

print(f"\nBitboard edges: {bin(edges)}")
print(f"Bits setados: {bin(edges).count('1')}")

# H_4_5 = H na posicao (4,5)
bit_h45 = edge_to_bit[(4,5)]
print(f"\nH_4_5 = bit {bit_h45}")

# Quantas caixas H_4_5 fecha no bitboard?
new_e = edges | (1 << bit_h45)
closed_bb = sum(1 for bm in edge_boxes[bit_h45] if new_e & bm == bm)
print(f"Caixas fechadas por H_4_5 no bitboard: {closed_bb}")
print(f"Caixas fechadas por H_4_5 no original: {fechadas}")

# PROBLEMA POTENCIAL: o bitboard conta caixas JA FECHADAS como "novas"!
# No original, a caixa ja tem valor 1 no interior, entao _caixa_fechada verifica
# os 4 lados, e o interior ja esta marcado (nao re-conta).
# Mas o bitboard so verifica se os 4 lados estao preenchidos!

# Verificar quais caixas o bitboard acha que H_4_5 fecha
print(f"\nCaixas adjacentes a H_4_5 (bit {bit_h45}):")
for bm in edge_boxes[bit_h45]:
    # Encontrar qual caixa e
    for r in range(1,h,2):
        for c in range(1,w,2):
            expected = (1<<edge_to_bit[(r-1,c)])|(1<<edge_to_bit[(r+1,c)])|(1<<edge_to_bit[(r,c-1)])|(1<<edge_to_bit[(r,c+1)])
            if expected == bm:
                ja_fechada_antes = (edges & bm == bm)
                fecha_agora = (new_e & bm == bm)
                # No NPZ, essa caixa ja estava fechada?
                npz_fechada = (mat[r,c] == 1)
                print(f"  Caixa ({r},{c}): mask={bin(bm)}")
                print(f"    Ja fechada antes (bitboard): {ja_fechada_antes}")
                print(f"    Fecha agora (bitboard):      {fecha_agora}")
                print(f"    Ja fechada no NPZ:           {npz_fechada}")
                if ja_fechada_antes and fecha_agora:
                    print(f"    >>> PROBLEMA! Bitboard conta caixa JA FECHADA como nova!")
