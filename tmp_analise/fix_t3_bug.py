import json
import re

nb_path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Arena_Sagaz_V7.ipynb'

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        src = "".join(cell['source'])
        if 'TOP-1 / TOP-3 ACCURACY POR FASE DO JOGO' in src:
            
            # The buggy part is:
            #     top5_pred = np.argsort(y_pred_prob[mask], axis=1)[:, -5:]
            #     t5 = (top5_pred == y_test_idx[mask, np.newaxis]).any(axis=1).mean()
            #     print(f"  {nome:<28}  {mask.sum():>6}  {t1:>6.1%}  {t3:>6.1%}  {t5:>6.1%}")
            
            buggy_code = """    top5_pred = np.argsort(y_pred_prob[mask], axis=1)[:, -5:]
    t5 = (top5_pred == y_test_idx[mask, np.newaxis]).any(axis=1).mean()
    print(f"  {nome:<28}  {mask.sum():>6}  {t1:>6.1%}  {t3:>6.1%}  {t5:>6.1%}")"""
            
            fixed_code = """    t3 = (top3_pred == y_test_idx[mask, np.newaxis]).any(axis=1).mean()
    top5_pred = np.argsort(y_pred_prob[mask], axis=1)[:, -5:]
    t5 = (top5_pred == y_test_idx[mask, np.newaxis]).any(axis=1).mean()
    print(f"  {nome:<28}  {mask.sum():>6}  {t1:>6.1%}  {t3:>6.1%}  {t5:>6.1%}")"""
            
            if buggy_code in src and "t3 = (top3_pred ==" not in src:
                src = src.replace(buggy_code, fixed_code)
                
                # Format back to list
                lines = [line if line.endswith('\n') else line + '\n' for line in src.splitlines()]
                if src and not src.endswith('\n'):
                    lines[-1] = lines[-1].rstrip('\n')
                cell['source'] = lines
                print("Bug corrigido com sucesso!")
                break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
