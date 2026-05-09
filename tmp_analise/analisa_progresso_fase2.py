import numpy as np
import os
import glob
import time
from datetime import datetime

dir_7 = 'dados/profundidade_minmax_7_corrigido'
files_7 = glob.glob(os.path.join(dir_7, '*.npz'))

total_files = len(files_7)
processed_files = []
pending_files = []

total_samples = 0
processed_samples = 0

for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        rotulos = npz['rotulos']
        n = rotulos.shape[0]
        total_samples += n
        
        if rotulos.size > 0 and rotulos[0] != "":
            processed_files.append(f)
            processed_samples += n
        else:
            pending_files.append(f)
    except Exception as e:
        print(f"Erro ao ler {f}: {e}")

# Calculate ETA
if len(processed_files) >= 2:
    # Sort processed files by mtime
    processed_files.sort(key=os.path.getmtime)
    t_start = os.path.getmtime(processed_files[0])
    t_end = os.path.getmtime(processed_files[-1])
    elapsed = t_end - t_start
    
    # Samples processed in the window between the first and last finished file
    samples_in_window = (len(processed_files) - 1) * 5000
    rate = samples_in_window / elapsed if elapsed > 0 else 0
    
    pending_samples = total_samples - processed_samples
    eta_sec = pending_samples / rate if rate > 0 else 0
else:
    elapsed = 0
    rate = 0
    eta_sec = 0

print(f"\\n--- PROGRESSO DA FASE 2 (SCORING MINIMAX P=7) ---")
print(f"Total de Arquivos: {total_files}")
print(f"Arquivos Scorados: {len(processed_files)}")
print(f"Amostras Scoradas: {processed_samples} / {total_samples}")
print(f"Progresso: {(processed_samples/total_samples)*100 if total_samples > 0 else 0:.2f}%")

if rate > 0:
    print(f"Taxa Média de Scoring: {rate:.2f} amostras / segundo")
    print(f"ETA para concluir Fase 2: {eta_sec/3600:.2f} horas ({eta_sec/60:.2f} minutos)")
else:
    print(f"Aguardando mais arquivos concluídos para estimar ETA...")
