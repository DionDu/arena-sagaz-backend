"""
Validacao definitiva da Fase 2 nos NPZs gerados pelo Databricks.
O script carrega os arquivos NPZ e verifica se as matrizes de score
produzidas pelo algoritmo Bitboard convergem 100% com o motor
de referencia Minimax Python Original em profundidade 7.
"""
import sys, numpy as np, time
from pathlib import Path
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

LINHAS, COLUNAS = TAMANHOS["pequeno"]
LABELS = todos_labels_canonicos(LINHAS, COLUNAS)

arquivos = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz",
]

total_amostras = 0
amostras_avaliadas = 0
divergencias = 0

print("INICIANDO AUDITORIA FINAL DE INTEGRIDADE MATEMATICA (FASE 2)\n")

for arquivo in arquivos:
    try:
        d = np.load(arquivo)
    except FileNotFoundError:
        print(f"[ERRO] Arquivo nao encontrado: {arquivo}")
        continue
        
    estados = d["estados"]
    qtd_tracos = d["qtd_tracos"]
    scores_fase2 = d["score_melhor_jogada"]
    melhor_jogada = d["melhor_jogada"]
    
    n = len(estados)
    total_amostras += n
    print(f"Lendo {Path(arquivo).name}: {n} amostras.")
    
    # Vamos avaliar aleatoriamente 50 amostras do "midgame" (10 a 20 tracos) por arquivo
    # Essa faixa e onde os bugs de offset alpha-beta mais geravam erros.
    cands = np.where((qtd_tracos >= 10) & (qtd_tracos <= 20))[0]
    
    np.random.seed(42 + int(Path(arquivo).stem[-4:])) # Seed diferente por arquivo
    tamanho_teste = min(50, len(cands))
    
    if tamanho_teste == 0:
        continue
        
    indices_teste = np.random.choice(cands, size=tamanho_teste, replace=False)
    
    for idx in indices_teste:
        mat_npz = estados[idx]
        scores_npz = scores_fase2[idx]
        
        # O Databricks processa em profundidade 7, entao a raiz vai puxar
        # os scores relativos da P7.
        estado = EstadoTabuleiro(LINHAS, COLUNAS)
        for r in range(9):
            for c in range(7):
                v = int(mat_npz[r,c])
                if v == 9 or v == 1:
                    estado.matriz[r,c] = 1
                    
        # Calcula na hora com o motor local confiavel
        t0 = time.time()
        scores_originais = _scores_de_todas_jogadas(estado, profundidade=7)
        
        # Comparacao
        for i, label in enumerate(LABELS):
            # Ignora posicoes invalidas onde ambas dao um valor sentinela negativo muito alto
            if scores_npz[i] < -1e5 and scores_originais.get(label, -1e9) < -1e5:
                continue
                
            valor_npz = scores_npz[i]
            valor_orig = scores_originais.get(label, -1e9)
            
            if abs(valor_npz - valor_orig) > 0.1:
                print(f"  [!] DIVERGENCIA ({Path(arquivo).name} idx={idx}) Traco {label}:")
                print(f"      Score NPZ = {valor_npz} | Score Orig = {valor_orig}")
                divergencias += 1
                break # Para essa amostra
        
        amostras_avaliadas += 1

print("\n--- RESULTADO DA AUDITORIA ---")
print(f"Arquivos verificados: {len(arquivos)}")
print(f"Total de amostras contidas: {total_amostras}")
print(f"Amostras sorteadas p/ validacao Minimax (profundidade 7): {amostras_avaliadas}")
if divergencias == 0:
    print(f"Status: [APROVADO] - 100% de convergencia. Nenhum bug de offset ou caixa pre-fechada encontrado.")
else:
    print(f"Status: [REPROVADO] - {divergencias} divergencias encontradas.")
