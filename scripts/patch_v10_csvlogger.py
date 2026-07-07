"""
Adiciona CSVLogger ao bloco de treinamento normal (dentro do else).
O arquivo CSV e salvo em RESULTADO_DIR com timestamp fixo baseado no nome do .keras.
"""
import json

path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Pontinhos_V10.ipynb'
with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

OLD_CALLBACKS = (
    "    callbacks = [\n"
    "        EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),\n"
    "        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-5, verbose=1),\n"
    "        ModelCheckpoint(\n"
    "            _ckpt_path,\n"
    "            monitor='val_loss',\n"
    "            save_best_only=True,\n"
    "            verbose=1,\n"
    "        ),\n"
    "    ]"
)

NEW_CALLBACKS = (
    "    from tensorflow.keras.callbacks import CSVLogger\n"
    "    _csv_path = _ckpt_path.replace('.keras', '_historico.csv')\n"
    "    callbacks = [\n"
    "        EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),\n"
    "        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-5, verbose=1),\n"
    "        ModelCheckpoint(\n"
    "            _ckpt_path,\n"
    "            monitor='val_loss',\n"
    "            save_best_only=True,\n"
    "            verbose=1,\n"
    "        ),\n"
    "        CSVLogger(_csv_path, append=True),\n"
    "    ]\n"
    "    print(f'Historico de epocas sera salvo em: {_csv_path}')"
)

for cell in nb['cells']:
    if cell.get('id') == '593a9cfd':
        src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
        if OLD_CALLBACKS in src:
            src = src.replace(OLD_CALLBACKS, NEW_CALLBACKS)
            cell['source'] = src
            cell['outputs'] = []
            cell['execution_count'] = None
            print('Patched 593a9cfd: CSVLogger adicionado')
        else:
            print('AVISO: bloco de callbacks nao encontrado — verifique manualmente')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print('Done.')
