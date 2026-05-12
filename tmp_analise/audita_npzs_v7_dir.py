import numpy as np
import os
import glob
from collections import Counter

dir_v7 = 'dados/profundidade_minimax_7_v7_adaptativo'
files = glob.glob(os.path.join(dir_v7, '*.npz'))

if not files:
    print(f"Nenhum arquivo encontrado em {dir_v7}")
    exit(0)

print(f"Analisando {len(files)} arquivos NPZ em {dir_v7}...")

total_bruto = 0
distintos = set()

# Campos esperados na V7:
campos_esperados = {
    'estados', 'qtd_tracos', 'score_jogada', 'depth_jogada', 'depth_geracao', 
    'melhor_jogada', 'score_melhor_jogada', 'depth_melhor_jogada', 'labels_canonicos'
}

arquivos_com_erro_chaves = []
vazios_em_melhor_jogada = 0
estados_terminais_totais = 0
falhas_de_preenchimento = 0

faixas = {
    'Abertura (1-11)': 0,
    '1a Metade (12-17)': 0,
    '2a Metade (18-23)': 0,
    'Fase Quente (24-28)': 0,
    'Final (29-30)': 0
}

for f in files:
    try:
        npz = np.load(f, allow_pickle=True)
        chaves = set(npz.keys())
        
        if not campos_esperados.issubset(chaves):
            arquivos_com_erro_chaves.append((os.path.basename(f), chaves))
            continue
            
        estados = npz['estados']
        melhor_jogada = npz['melhor_jogada']
        score_melhor_jogada = npz['score_melhor_jogada']
        qtd_tracos = npz['qtd_tracos']
        
        n = estados.shape[0]
        total_bruto += n
        
        # Validando preenchimento da melhor jogada
        vazios_neste = np.sum(melhor_jogada == "")
        vazios_em_melhor_jogada += vazios_neste
        
        terminais_neste = 0
        for i in range(n):
            validos = score_melhor_jogada[i][score_melhor_jogada[i] > -1e8]
            if validos.size == 0:
                terminais_neste += 1
                
        estados_terminais_totais += terminais_neste
        
        # A quantia de vazios DEVE ser igual a quantidade de estados terminais.
        if vazios_neste != terminais_neste:
            falhas_de_preenchimento += abs(vazios_neste - terminais_neste)
        
        for i in range(n):
            estado_bytes = estados[i].tobytes()
            distintos.add(estado_bytes)
            
            qt = qtd_tracos[i]
            if 1 <= qt <= 11:
                faixas['Abertura (1-11)'] += 1
            elif 12 <= qt <= 17:
                faixas['1a Metade (12-17)'] += 1
            elif 18 <= qt <= 23:
                faixas['2a Metade (18-23)'] += 1
            elif 24 <= qt <= 28:
                faixas['Fase Quente (24-28)'] += 1
            elif 29 <= qt <= 30:
                faixas['Final (29-30)'] += 1
                
    except Exception as e:
        print(f"Erro ao ler {f}: {e}")

total_distintos = len(distintos)

print(f"\\n=== AUDITORIA DE INTEGRIDADE E PREENCHIMENTO V7 ===")
print(f"Arquivos validados: {len(files) - len(arquivos_com_erro_chaves)} / {len(files)}")
print(f"Volume Bruto Total: {total_bruto:,}")
print(f"Estados Distintos Retidos: {total_distintos:,}")

print(f"\\n--- STATUS ESTRUTURAL DOS ARQUIVOS ---")
if len(arquivos_com_erro_chaves) > 0:
    print(f"[FALHA] {len(arquivos_com_erro_chaves)} arquivos não possuem todas as chaves exigidas pela V7.")
else:
    print(f"[OK] Todos os arquivos possuem as {len(campos_esperados)} chaves do schema V7.")

print(f"\\n--- VERIFICAÇÃO DE DADOS DA FASE 2 (SCORING) ---")
print(f"Total de registros vazios em 'melhor_jogada': {vazios_em_melhor_jogada:,}")
print(f"Total de estados terminais reais (sem jogadas): {estados_terminais_totais:,}")

if falhas_de_preenchimento == 0:
    print(f"STATUS: [APROVADO] 100% das matrizes não-terminais possuem a Fase 2 (scores e melhor jogada) devidamente preenchidas.")
else:
    print(f"STATUS: [ALERTA] Existem {falhas_de_preenchimento:,} registros que deveriam ter melhor_jogada mas estão vazios. (A Fase 2 pode ainda não ter passado por todos os arquivos).")

print(f"\\n--- DISTRIBUIÇÃO DAS AMOSTRAS ---")
for k, v in faixas.items():
    print(f"{k:20}: {v:>10,} ({v/total_bruto*100 if total_bruto>0 else 0:.2f}%)")
