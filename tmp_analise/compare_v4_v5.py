import numpy as np

# Load old NPZ
old_file = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minmax_9\dataset_pequeno_0001.npz"
print(f"Loading old file: {old_file}")
old_data = np.load(old_file, allow_pickle=True)
print(f"Old file keys: {list(old_data.keys())}")

# Load new NPZ
new_file = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minimax_7_v7_adaptativo\dataset_pequeno_0001.npz"
print(f"\\nLoading new file: {new_file}")
new_data = np.load(new_file, allow_pickle=True)
print(f"New file keys: {list(new_data.keys())}")

# Compare expected shapes and types for relevant fields
print("\\n--- Comparison ---")

# Labels
if 'rotulos' in old_data:
    print(f"Old 'rotulos' shape: {old_data['rotulos'].shape}, dtype: {old_data['rotulos'].dtype}")
if 'melhor_jogada' in new_data:
    print(f"New 'melhor_jogada' shape: {new_data['melhor_jogada'].shape}, dtype: {new_data['melhor_jogada'].dtype}")

# Scores
if 'scores' in old_data:
    print(f"Old 'scores' shape: {old_data['scores'].shape}, dtype: {old_data['scores'].dtype}")
if 'score_melhor_jogada' in new_data:
    print(f"New 'score_melhor_jogada' shape: {new_data['score_melhor_jogada'].shape}, dtype: {new_data['score_melhor_jogada'].dtype}")
    
# Estados
if 'estados' in old_data and 'estados' in new_data:
    print(f"Old 'estados' shape: {old_data['estados'].shape}, dtype: {old_data['estados'].dtype}")
    print(f"New 'estados' shape: {new_data['estados'].shape}, dtype: {new_data['estados'].dtype}")

# Labels canonicos
if 'labels_canonicos' in old_data and 'labels_canonicos' in new_data:
    print(f"Old 'labels_canonicos' matches new: {np.array_equal(old_data['labels_canonicos'], new_data['labels_canonicos'])}")

