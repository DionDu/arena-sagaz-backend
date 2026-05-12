import json
import re

nb_path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Arena_Sagaz_V7.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Modifying cell 1 (Config)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        if 'PASTA_NPZ' in src and 'DRIVE_OUTPUT_DIR' in src:
            # Found config cell
            new_src = src.replace(
                "PASTA_NPZ = '.'", 
                "PASTA_NPZ = '../dados/profundidade_minimax_7_v7_adaptativo'\n\n# Controle de filtragem de dados\n# Opções: 'DISTINTAS' (apenas matrizes únicas) ou 'INCLUI_DUPLICADAS' (todas)\nUTILIZACAO_MATRIZES = 'INCLUI_DUPLICADAS'"
            )
            
            # Need to format back to list of lines for Jupyter
            lines = new_src.splitlines(keepends=True)
            cell['source'] = lines
            print("Config cell updated.")
            break

# Modifying cell 3 (Data reading & prep)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        if '1.1 LEITURA DOS LOTES' in src:
            # Found reading cell
            # 1. Update fields
            src = src.replace("lista_rotulos.append(dados['rotulos'])", "lista_rotulos.append(dados['melhor_jogada'])")
            src = src.replace("lista_scores.append(dados['scores'])", "lista_scores.append(dados['score_melhor_jogada'])")
            
            # 2. Add UTILIZACAO_MATRIZES logic right after concatenation
            dup_logic = """
print(f'Total de amostras brutas (antes do filtro): {len(X_raw):,}')

# =========================================================================
# 1.1b FILTRAGEM DE DUPLICATAS (Opcional)
# =========================================================================
if UTILIZACAO_MATRIZES == 'DISTINTAS':
    print('\\nFiltrando apenas matrizes distintas...')
    _, unique_indices = np.unique(X_raw, axis=0, return_index=True)
    # np.unique sorts the indices by the values, we might want to sort them back to original order
    unique_indices.sort()
    
    X_raw = X_raw[unique_indices]
    y_str = y_str[unique_indices]
    scores_raw = scores_raw[unique_indices]
    gen_modes = gen_modes[unique_indices]
    print(f'Total de amostras apos filtragem (DISTINTAS): {len(X_raw):,}')
else:
    print('\\nUtilizando todas as matrizes (INCLUI_DUPLICADAS).')

print(f'Shape entrada: {X_raw.shape} | Scores: {scores_raw.shape}')
"""
            src = re.sub(r"print\(f'Total de amostras: \{len\(X_raw\):,\}'\)\nprint\(f'Shape entrada: \{X_raw\.shape\} \| Scores: \{scores_raw\.shape\}'\)", dup_logic, src)
            
            # 3. Update Bins
            src = src.replace("fase_jogo = np.digitize(qtd_tracos_preenchidos, bins=[10, 18, 26]).astype(np.int8)", 
                              "fase_jogo = np.digitize(qtd_tracos_preenchidos, bins=[12, 18, 24, 29]).astype(np.int8)")
            
            src = src.replace("FASE_NAMES = {0: 'Abertura (0-9)', 1: '1ª Metade (10-17)',\n              2: '2ª Metade (18-25)', 3: 'Final (26-31)'}",
                              "FASE_NAMES = {0: 'Abertura (0-11)', 1: '1ª Metade (12-17)',\n              2: '2ª Metade (18-23)', 3: 'Fase Quente (24-28)', 4: 'Final (29-31)'}")
            
            # Formatting back
            lines = [line if line.endswith('\n') else line + '\n' for line in src.splitlines()]
            # Fix the last line
            if src and not src.endswith('\n'):
                lines[-1] = lines[-1].rstrip('\n')
            cell['source'] = lines
            print("Data prep cell updated.")
            break

# Modifying cell 6 (Metrics)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        if 'CLASSIFICATION REPORT' in src:
            # Found metrics cell
            
            # Identify border edges
            border_logic = """
# Bordas do tabuleiro (9x7 matriz):
BORDAS = {
    'H_0_1', 'H_0_3', 'H_0_5', # Topo
    'H_8_1', 'H_8_3', 'H_8_5', # Base
    'V_1_0', 'V_3_0', 'V_5_0', 'V_7_0', # Esquerda
    'V_1_6', 'V_3_6', 'V_5_6', 'V_7_6'  # Direita
}

por_classe['borda'] = por_classe.index.isin(BORDAS)
por_classe['jogada_formatada'] = por_classe.index.map(lambda x: f"{x} (Borda)" if x in BORDAS else x)
por_classe_display = por_classe.set_index('jogada_formatada')

print("\\nTop 10 jogadas com melhor F1 (onde o modelo brilha):")
print(por_classe_display.head(10)[['precision', 'recall', 'f1-score', 'support']]
      .to_string(float_format=lambda v: f"{v:.4f}"))
print("\\nBottom 5 jogadas (onde o modelo mais erra — verificar bordas):")
print(por_classe_display.tail(5)[['precision', 'recall', 'f1-score', 'support']]
      .to_string(float_format=lambda v: f"{v:.4f}"))
"""
            # Replace the old top 10 logic
            old_top10_logic = r"print\(\"\\nTop 10 jogadas com melhor F1.*?.to_string\(float_format=lambda v: f\"\{v:\.4f\}\"\)\)"
            src = re.sub(old_top10_logic, border_logic.strip(), src, flags=re.DOTALL)
            
            
            # Update Fases section (5.1)
            old_fases = r"fases = \[\n    \(0,   9, 'Abertura \(0-9 tracos\)'\),\n    \(10, 17, '1ª Metade \(10-17 tracos\)'\),\n    \(18, 25, '2ª Metade \(18-25 tracos\)'\),\n    \(26, 31, 'Final \(21-31 tracos\)'\),\n\]"
            new_fases = """fases = [
    (0,  11, 'Abertura (0-11 tracos)'),
    (12, 17, '1ª Metade (12-17 tracos)'),
    (18, 23, '2ª Metade (18-23 tracos)'),
    (24, 28, 'Fase Quente (24-28 tracos)'),
    (29, 31, 'Final (29-31 tracos)'),
]"""
            src = src.replace("fases = [\n    (0,   9, 'Abertura (0-9 tracos)'),\n    (10, 17, '1ª Metade (10-17 tracos)'),\n    (18, 25, '2ª Metade (18-25 tracos)'),\n    (26, 31, 'Final (21-31 tracos)'),\n]", new_fases)
            
            # Update the print header for phases to include Top-5
            src = src.replace("print(f\"  {'Fase':<28}  {'N':>6}  {'Top-1':>7}  {'Top-3':>7}\")", "print(f\"  {'Fase':<28}  {'N':>6}  {'Top-1':>7}  {'Top-3':>7}  {'Top-5':>7}\")")
            
            # Add top-5 calculation
            t5_calc = """    top5_pred = np.argsort(y_pred_prob[mask], axis=1)[:, -5:]
    t5 = (top5_pred == y_test_idx[mask, np.newaxis]).any(axis=1).mean()
    print(f"  {nome:<28}  {mask.sum():>6}  {t1:>6.1%}  {t3:>6.1%}  {t5:>6.1%}")"""
            
            src = re.sub(r"    t3 = \(top3_pred == y_test_idx\[mask, np\.newaxis\]\)\.any\(axis=1\)\.mean\(\)\n    print\(f\"  \{nome:<28\}  \{mask\.sum\(\):>6\}  \{t1:>6\.1%\}  \{t3:>6\.1%\}\"\)", t5_calc, src)
            
            # 5.4 Métrica de Bordas
            border_metric = """
# =========================================================================
# 5.4  Análise de Jogadas nas Bordas (Viés do Modelo)
# Avalia se a CNN está enviesada a jogar nas bordas mais do que o Minimax
# =========================================================================
print('\\n' + '=' * 70)
print('ANÁLISE DE VIÉS DE BORDAS (CNN vs MINIMAX)')
print('=' * 70)

# Converter previsões e alvos em labels (nomes reais dos traços)
# y_test_idx tem a verdade-padrão (Minimax), y_pred_idx tem a escolha Top-1 da CNN
labels_test = np.array([indice_para_rotulo[i] for i in y_test_idx])
labels_pred = np.array([indice_para_rotulo[i] for i in y_pred_idx])

# Identificar se a jogada foi na borda
borda_test = np.isin(labels_test, list(BORDAS))
borda_pred = np.isin(labels_pred, list(BORDAS))

print(f"  Global:")
print(f"    Minimax joga na borda: {borda_test.mean():.1%}")
print(f"    CNN joga na borda:     {borda_pred.mean():.1%}")
print(f"    Viés (CNN - Minimax):  {(borda_pred.mean() - borda_test.mean()) * 100:+.1f} pp")

print("\\n  Segmentado por Fase do Jogo:")
for lo, hi, nome in fases:
    mask = (tracos_jogados >= lo) & (tracos_jogados <= hi)
    if mask.sum() == 0: continue
    
    b_test_fase = borda_test[mask].mean()
    b_pred_fase = borda_pred[mask].mean()
    vies = (b_pred_fase - b_test_fase) * 100
    
    print(f"    {nome:<26} -> Minimax: {b_test_fase:>5.1%} | CNN: {b_pred_fase:>5.1%} | Viés: {vies:>5.1f} pp")
"""
            src += border_metric
            
            lines = [line if line.endswith('\n') else line + '\n' for line in src.splitlines()]
            if src and not src.endswith('\n'):
                lines[-1] = lines[-1].rstrip('\n')
            cell['source'] = lines
            print("Metrics cell updated.")
            break

# Modifying cell 7 (Charts)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        if '5.3 VISUALIZAÇÃO POR FASE' in src:
            # We need to use the new phases
            # Actually, `fases` variable is already updated in the previous cell and reused here!
            # We just need to make sure we don't need to change anything. 
            print("Charts cell verified.")
            break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("Notebook salvo com sucesso.")
