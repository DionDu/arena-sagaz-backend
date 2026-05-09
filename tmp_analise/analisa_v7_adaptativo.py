import numpy as np
import os
import glob
import time
from datetime import datetime

dir_v7 = 'dados/profundidade_minmax_7_adaptativo'
files = glob.glob(os.path.join(dir_v7, '*.npz'))

if not files:
    print(f"Nenhum arquivo encontrado em {dir_v7}")
    exit(0)

files.sort(key=os.path.getmtime)

total_bruto = 0
distintos = set()

faixas = {
    'Abertura (1-11)': {'bruto': 0, 'distintos': set(), 'soma_depth_geracao': 0},
    '1a Metade (12-17)': {'bruto': 0, 'distintos': set(), 'soma_depth_geracao': 0},
    '2a Metade (18-23)': {'bruto': 0, 'distintos': set(), 'soma_depth_geracao': 0},
    'Fase Quente (24-28)': {'bruto': 0, 'distintos': set(), 'soma_depth_geracao': 0},
    'Final (29-30)': {'bruto': 0, 'distintos': set(), 'soma_depth_geracao': 0}
}

soma_depth_jogada = 0
soma_depth_geracao = 0

fase2_files = []
fase2_samples = 0

for f in files:
    try:
        npz = np.load(f, allow_pickle=True)
        estados = npz['estados']
        qtd_tracos = npz['qtd_tracos']
        depth_jogada = npz['depth_jogada']
        depth_geracao = npz['depth_geracao']
        melhor_jogada = npz['melhor_jogada']
        
        n = estados.shape[0]
        total_bruto += n
        
        soma_depth_jogada += np.sum(depth_jogada)
        soma_depth_geracao += np.sum(depth_geracao)
        
        # Check fase 2
        is_fase2 = False
        if melhor_jogada.size > 0 and melhor_jogada[0] != "":
            is_fase2 = True
            fase2_files.append(f)
            fase2_samples += n
            
        for i in range(n):
            estado_bytes = estados[i].tobytes()
            distintos.add(estado_bytes)
            
            qt = qtd_tracos[i]
            dg = depth_geracao[i]
            chave = ''
            if 1 <= qt <= 11:
                chave = 'Abertura (1-11)'
            elif 12 <= qt <= 17:
                chave = '1a Metade (12-17)'
            elif 18 <= qt <= 23:
                chave = '2a Metade (18-23)'
            elif 24 <= qt <= 28:
                chave = 'Fase Quente (24-28)'
            elif 29 <= qt <= 30:
                chave = 'Final (29-30)'
            
            if chave:
                faixas[chave]['bruto'] += 1
                faixas[chave]['distintos'].add(estado_bytes)
                faixas[chave]['soma_depth_geracao'] += float(dg)
                
    except Exception as e:
        print(f"Erro ao ler {f}: {e}")

total_distintos = len(distintos)
media_depth_jogada = soma_depth_jogada / total_bruto if total_bruto > 0 else 0
media_depth_geracao = soma_depth_geracao / total_bruto if total_bruto > 0 else 0

# ETA Fase 1
if len(files) >= 2:
    t_start = os.path.getmtime(files[0])
    t_end = os.path.getmtime(files[-1])
    elapsed_f1 = t_end - t_start
    rate_f1 = total_distintos / elapsed_f1 if elapsed_f1 > 0 else 0
    restantes_f1 = max(0, 500000 - total_distintos)
    eta_sec_f1 = restantes_f1 / rate_f1 if rate_f1 > 0 else 0
else:
    elapsed_f1 = rate_f1 = restantes_f1 = eta_sec_f1 = 0

# ETA Fase 2
if len(fase2_files) >= 2:
    fase2_files.sort(key=os.path.getmtime)
    t_start_f2 = os.path.getmtime(fase2_files[0])
    t_end_f2 = os.path.getmtime(fase2_files[-1])
    elapsed_f2 = t_end_f2 - t_start_f2
    
    # samples_in_window is approximately the processed samples minus the first file's samples
    # to be safe, just rate over elapsed
    rate_f2 = (len(fase2_files) - 1) * 5000 / elapsed_f2 if elapsed_f2 > 0 else 0
    pending_f2 = total_bruto - fase2_samples
    eta_sec_f2 = pending_f2 / rate_f2 if rate_f2 > 0 else 0
else:
    rate_f2 = eta_sec_f2 = 0

print(f"\\n=== RELATÓRIO GERENCIAL V7 (DAC) ===")
print(f"Arquivos processados: {len(files)}")
print(f"Volume Bruto Total: {total_bruto:,}")
print(f"Estados Distintos Retidos: {total_distintos:,} / 500,000")
print(f"Progresso Global (Distintos): {(total_distintos/500000)*100:.2f}%")
print(f"Taxa de Colisão (Repetição): {100 * (1 - total_distintos/total_bruto) if total_bruto > 0 else 0:.2f}%")
print(f"\\n[Métricas Adaptativas]")
print(f"Profundidade Média de Geração (Global): {media_depth_geracao:.2f}")
print(f"Profundidade Média de Jogada (Global): {media_depth_jogada:.2f}")

print(f"\\n[Distribuição por Faixas de Traços]")
print(f"| {'Faixa de Traços':<20} | {'Total Bruto':>12} | {'Total Distinto':>14} | {'% do Dataset':>12} | {'Prof. Média Ger.':>16} |")
print(f"|{'-'*22}|{'-'*14}|{'-'*16}|{'-'*14}|{'-'*18}|")

total_b = 0
total_d = 0

for k, v in faixas.items():
    qtd_b = v['bruto']
    qtd_d = len(v['distintos'])
    soma_dg = v['soma_depth_geracao']
    
    total_b += qtd_b
    total_d += qtd_d
    
    pct_d = (qtd_d / total_distintos * 100) if total_distintos > 0 else 0
    media_dg = soma_dg / qtd_b if qtd_b > 0 else 0
    
    print(f"| {k:20} | {qtd_b:>12,} | {qtd_d:>14,} | {pct_d:>11.2f}% | {media_dg:>16.2f} |")

print(f"|{'-'*22}|{'-'*14}|{'-'*16}|{'-'*14}|{'-'*18}|")
print(f"| {'Total Global':<20} | {total_b:>12,} | {total_d:>14,} | {'100.00%':>12} | {media_depth_geracao:>16.2f} |")

print(f"\\n[Performance e ETA - Fase 1 (Geração)]")
print(f"Tempo Decorrido: {elapsed_f1/60:.2f} min ({elapsed_f1/3600:.2f} h)")
if rate_f1 > 0:
    print(f"Taxa de Extração: {rate_f1:.2f} estados distintos / segundo")
    if total_distintos < 500000:
        print(f"ETA para 500k distintos: {eta_sec_f1/60:.2f} min ({eta_sec_f1/3600:.2f} h)")
    else:
        print(f"ETA: CONCLUÍDO")
else:
    print("Taxa de Extração: N/A")

print(f"\\n[Progresso e ETA - Fase 2 (Scoring)]")
print(f"NPZs Scorados: {len(fase2_files)} / {len(files)} ({(len(fase2_files)/len(files))*100 if files else 0:.2f}%)")
if rate_f2 > 0:
    print(f"Taxa de Scoring: {rate_f2:.2f} matrizes / segundo")
    print(f"ETA para Fase 2 global: {eta_sec_f2/60:.2f} min ({eta_sec_f2/3600:.2f} h)")
elif len(fase2_files) == 0:
    print("Fase 2 ainda não iniciada (aguardando conclusão da Fase 1).")
    # Estimativa teórica baseada em p=7
    # (Em media, Minimax p=7 leva ~2 a 10 ms por jogada, em 500k = ~1 a 2 horas)
    print("Estimativa Teórica para Fase 2: ~1.5 a 3 horas (após início).")
else:
    print("Calculando taxa... aguarde mais NPZs serem scorados.")
