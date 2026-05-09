import numpy as np
import os
import glob
import time
from datetime import datetime

dir_7 = 'dados/profundidade_minmax_7_corrigido'
files_7 = sorted(glob.glob(os.path.join(dir_7, '*.npz')), key=os.path.getmtime)

print(f'Analisando {len(files_7)} arquivos NPZ em {dir_7}...')

if len(files_7) < 2:
    print("Arquivos insuficientes para calcular taxa de geracao.")
    exit(0)

# Pega o timestamp do primeiro e do último arquivo
t_start = os.path.getmtime(files_7[0])
t_end = os.path.getmtime(files_7[-1])

elapsed_seconds = t_end - t_start

# Calcula amostras brutas
total_samples = len(files_7) * 5000  # assumindo 5000 por NPZ conforme observado

# Calcula distintos (aproximado usando a taxa observada antes ou recalculando rápido)
# Vamos recalcular os distintos rapidinho para termos a conta exata do momento atual
unique_estados_global = set()
for f in files_7:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        for i in range(estados.shape[0]):
            unique_estados_global.add(estados[i].tobytes())
    except Exception as e:
        pass

total_distintos = len(unique_estados_global)
alvo_distintos = 501500
restantes = alvo_distintos - total_distintos

# Taxa de geração (distintos / segundo)
# Considerando que o primeiro arquivo já levou X tempo para ser gerado,
# a variação de tempo reflete a geração dos arquivos de 2 a N.
# Para simplificar e pegar a média da janela inteira, vamos usar o elapsed_seconds
# e o delta de amostras distintas do arquivo 1 até N. Mas para uma aproximação 
# robusta em regime permanente, total_distintos / elapsed_seconds da janela do inicio ao fim
rate_per_sec = total_distintos / elapsed_seconds if elapsed_seconds > 0 else 0

eta_seconds = restantes / rate_per_sec if rate_per_sec > 0 else 0
eta_hours = eta_seconds / 3600

print(f"\\n--- ESTATÍSTICAS DE TEMPO ---")
print(f"Início: {datetime.fromtimestamp(t_start).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Último: {datetime.fromtimestamp(t_end).strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Tempo decorrido: {elapsed_seconds/60:.2f} minutos ({elapsed_seconds/3600:.2f} horas)")
print(f"Distintos atuais: {total_distintos}")
print(f"Taxa média: {rate_per_sec:.2f} amostras distintas / segundo")
print(f"Restantes: {restantes}")
print(f"ETA (Estimativa para concluir Fase 1): {eta_hours:.2f} horas ({eta_seconds/60:.2f} minutos)")
