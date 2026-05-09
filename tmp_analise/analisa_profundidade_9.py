import os
import glob
import numpy as np
import pandas as pd

# Directory containing the NPZ files
data_dir = r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minmax_9"
npz_files = glob.glob(os.path.join(data_dir, "*.npz"))

# Dictionary to hold the counts: (traces, mode) -> count
data = []

for filepath in npz_files:
    try:
        with np.load(filepath, allow_pickle=True) as f:
            estados = f['estados']
            generation_mode = f['generation_mode']
            
            # Number of filled traces is the count of 9s in each state matrix
            # estados shape is (N, H, W). We sum over axis 1 and 2
            traces_count = np.sum(estados == 9, axis=(1, 2))
            
            # Create a dataframe for this batch and append
            batch_df = pd.DataFrame({
                'Tracos_Preenchidos': traces_count,
                'Generation_Mode': generation_mode
            })
            data.append(batch_df)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

# Combine all batches
df = pd.concat(data, ignore_index=True)

# Create a pivot table: Rows = Tracos_Preenchidos, Cols = Generation_Mode, Values = Count
pivot = pd.crosstab(df['Tracos_Preenchidos'], df['Generation_Mode'])

# Print the result as a markdown table
print(pivot.to_csv())
pivot.to_csv(r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\tmp_analise\distribuicao_amostras_profundidade_9.csv")

