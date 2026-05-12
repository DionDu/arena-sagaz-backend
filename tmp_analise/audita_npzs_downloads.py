import numpy as np
import os
import sys

# Ajusta path para importar do gerador
sys.path.insert(0, 'D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend')
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro

arquivos = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz"
]

print("--- AUDITORIA DE PREENCHIMENTO ---")
for f in arquivos:
    try:
        if not os.path.exists(f):
            print(f"ERRO: Arquivo não encontrado: {f}")
            continue
            
        npz = np.load(f, allow_pickle=True)
        melhor_jogada = npz['melhor_jogada']
        
        # Pega as chaves para verificar se estão certas
        chaves = list(npz.keys())
        
        # Verifica quantos estão vazios
        vazios = np.sum(melhor_jogada == "")
        terminais = 0
        
        # Temos que achar terminais pra abater dos vazios. Terminais tem scores indisponíveis
        score_melhor_jogada = npz['score_melhor_jogada']
        for i in range(score_melhor_jogada.shape[0]):
            validos = score_melhor_jogada[i][score_melhor_jogada[i] > -1e8]
            if validos.size == 0:
                terminais += 1
                
        falhas = vazios - terminais
        
        print(f"Arquivo: {os.path.basename(f)}")
        print(f"  Amostras: {melhor_jogada.shape[0]}")
        print(f"  Vazios em 'melhor_jogada': {vazios} (Esperado igual aos Terminais: {terminais})")
        print(f"  Status de Preenchimento: {'[OK]' if falhas == 0 else '[FALHA] ' + str(falhas) + ' não preenchidos'}")
        print(f"  Chaves presentes: {chaves}\\n")
        
    except Exception as e:
        print(f"Erro ao ler {f}: {e}")

print("--- AUDITORIA DE MATEMÁTICA MINIMAX (RECALCULO DE 2 AMOSTRAS ALEATÓRIAS) ---")
try:
    npz = np.load(arquivos[0], allow_pickle=True)
    estados = npz['estados']
    melhor_jogada = npz['melhor_jogada']
    score_melhor_jogada = npz['score_melhor_jogada']
    labels_canonicos = npz['labels_canonicos'].tolist()
    
    indices_para_testar = [10, 2500] # Duas amostras espalhadas no arquivo 1
    
    for idx in indices_para_testar:
        estado_np = estados[idx]
        
        # Reconstruir estado
        # O npz salvo na Fase 1 é formato neutro {0, 1, 8, 9}. 
        # O Minimax espera um estado live, onde os tracos (arestas) podem ser de um jogador.
        # Contudo, nosso gerador_amostras_v7_pontinhos Fase 2 faz copy() do mat_neutro 
        # diretamente para estado.matriz. E trata tudo != 0 como ocupado.
        
        estado = EstadoTabuleiro(4, 3)
        estado.matriz = estado_np.copy()
        
        # Ignora se for terminal
        if estado.esta_terminal():
            print(f"Idx {idx} é terminal, pulando verificação.")
            continue
            
        print(f"\\nTestando Índice {idx} do {os.path.basename(arquivos[0])}:")
        print(f"Traços já preenchidos na matriz: {np.sum(estado_np == 9)}")
        
        # Recalcula
        rotulo_calc, dict_scores_calc = melhor_jogada_com_scores(estado, profundidade=7)
        
        # O NPZ grava um array flat. Vamos reconstruí-lo como dict para comparar com facilidade.
        # Os slots inválidos têm valor de -1e9.
        vetor_scores_npz = score_melhor_jogada[idx]
        rotulo_npz = melhor_jogada[idx]
        
        # Transformar o vetor do NPZ de volta num dict válido 
        dict_scores_npz = {}
        for i, label in enumerate(labels_canonicos):
            if vetor_scores_npz[i] > -1e8: # Se não for SCORE_INDISPONIVEL
                dict_scores_npz[label] = vetor_scores_npz[i]
                
        print(f"-> Melhor Jogada Arquivo: {rotulo_npz} | Minimax Recalculado: {rotulo_calc}")
        print(f"-> Maior Score Arquivo: {max(dict_scores_npz.values())} | Minimax Recalculado: {max(dict_scores_calc.values())}")
        
        # Verificar convergência
        # Como pode haver empates (argmax randômico), a label pode ser diferente, 
        # mas os scores dos dicionários têm que ser ESTRITAMENTE IDÊNTICOS para toda jogada.
        divergencias = 0
        for jogada in dict_scores_calc.keys():
            if jogada not in dict_scores_npz:
                print(f"  [ERRO] Jogada {jogada} presente no recalc mas não no arquivo!")
                divergencias += 1
            elif dict_scores_calc[jogada] != dict_scores_npz[jogada]:
                print(f"  [ERRO] Score da {jogada} divergiu: Arq={dict_scores_npz[jogada]} Calc={dict_scores_calc[jogada]}")
                divergencias += 1
                
        for jogada in dict_scores_npz.keys():
            if jogada not in dict_scores_calc:
                print(f"  [ERRO] Jogada {jogada} presente no arquivo mas não é possível no recalc!")
                divergencias += 1
                
        if divergencias == 0:
            print("-> [CONFORMIDADE TOTAL] A matriz de Scores (Q-values) bate exatamente em todas as casas decimais!")
        else:
            print(f"-> [FALHA] Foram encontradas {divergencias} divergências nos cálculos!")
        
except Exception as e:
    print(f"Erro na auditoria matemática: {e}")
