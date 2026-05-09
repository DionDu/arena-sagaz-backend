import os
import shutil
import numpy as np
import random
import time
from pathlib import Path
import multiprocessing
import concurrent.futures

from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS, todos_labels_canonicos

def _vetor_scores(scores_dict, indice_label, n_labels):
    SCORE_INDISPONIVEL = -1e9
    vetor = np.full(n_labels, SCORE_INDISPONIVEL, dtype=np.float32)
    for label, valor in scores_dict.items():
        vetor[indice_label[label]] = float(valor)
    return vetor

def gerar_late_game(dest_dir, n_samples=5000, profundidade=9):
    linhas, colunas = TAMANHOS["pequeno"]
    labels_canonicos = todos_labels_canonicos(linhas, colunas)
    indice_label = {lab: i for i, lab in enumerate(labels_canonicos)}
    n_labels = len(labels_canonicos)

    estados_lote = []
    rotulos_lote = []
    scores_lote = []
    generation_mode_lote = []

    print(f"Gerando {n_samples} amostras com >= 27 traços preenchidos...")
    inicio = time.time()

    def generate_task():
        while True:
            estado = EstadoTabuleiro(linhas, colunas)
            tracos = estado.tracos_disponiveis()
            total = len(tracos)
            # >= 27
            qtd = random.randint(27, 30)
            random.shuffle(tracos)
            for tr in tracos[:qtd]:
                if tr in estado.tracos_disponiveis():
                    estado.aplicar_traco(tr, 9)
            
            if not estado.esta_terminal():
                return estado

    # Single-process is enough because depth is small (<= 4 available moves)
    # Wait, total traces = 31. If qtd >= 27, remaining moves <= 4. Minimax depth 9 will evaluate it instantly.
    
    for i in range(n_samples):
        estado = generate_task()
        try:
            rotulo, scores_dict = melhor_jogada_com_scores(estado, profundidade)
            estados_lote.append(estado.matriz.copy())
            rotulos_lote.append(rotulo)
            scores_lote.append(_vetor_scores(scores_dict, indice_label, n_labels))
            # using 4 to distinguish our late game samples
            generation_mode_lote.append(4) 
        except Exception as e:
            pass

        if (i + 1) % 500 == 0:
            print(f"Gerados {i + 1}/{n_samples}...")

    caminho_lote = os.path.join(dest_dir, "dataset_pequeno_late_game_0001.npz")
    np.savez_compressed(
        caminho_lote,
        estados=np.array(estados_lote, dtype=np.int8),
        rotulos=np.array(rotulos_lote, dtype=str),
        scores=np.array(scores_lote, dtype=np.float32),
        generation_mode=np.array(generation_mode_lote, dtype=np.int8),
        labels_canonicos=np.array(labels_canonicos, dtype=str),
        minimax_depth=np.array([profundidade], dtype=np.int32)
    )
    print(f"Salvo em {caminho_lote}. Tempo: {time.time() - inicio:.2f}s")

def main():
    src_dir = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minmax_9"
    dest_dir = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minmax_9_97pct"

    if not os.path.exists(dest_dir):
        print(f"Copiando {src_dir} para {dest_dir}...")
        shutil.copytree(src_dir, dest_dir)
        print("Cópia concluída.")
    else:
        print(f"Diretório {dest_dir} já existe, pulando cópia.")

    gerar_late_game(dest_dir, n_samples=5000, profundidade=9)

if __name__ == "__main__":
    main()
