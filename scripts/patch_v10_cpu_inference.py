import json

path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Pontinhos_V10.ipynb'
with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    cid = cell.get('id', '')

    # Célula 4: avalia_conjunto + model.predict
    if cid == 'afb8515e':
        src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
        src = src.replace(
            '    m = model.evaluate(X_, y_soft_, verbose=0, return_dict=True)',
            '    with tf.device("/CPU:0"):\n        m = model.evaluate(X_, y_soft_, verbose=0, return_dict=True)'
        )
        src = src.replace(
            'y_pred_prob = model.predict(X_test, verbose=0)',
            'with tf.device("/CPU:0"):\n    y_pred_prob = model.predict(X_test, verbose=0)'
        )
        cell['source'] = src
        cell['outputs'] = []
        cell['execution_count'] = None
        print('Patched afb8515e')

    # Célula 9: TFLite conversion
    if cid == '5dcf0b4b':
        src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
        src = src.replace(
            'converter = tf.lite.TFLiteConverter.from_keras_model(model)',
            'with tf.device("/CPU:0"):\n    converter = tf.lite.TFLiteConverter.from_keras_model(model)'
        )
        cell['source'] = src
        cell['outputs'] = []
        cell['execution_count'] = None
        print('Patched 5dcf0b4b')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print('Done.')
