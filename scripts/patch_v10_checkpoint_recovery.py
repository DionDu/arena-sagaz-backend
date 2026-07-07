"""
Patch do V10:
- Célula 593a9cfd (treinamento): detecta checkpoint existente e pula o treino.
- Célula afb8515e (avaliação):   protege gráficos de curva que dependem de history.
"""
import json

path = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\notebooks\jogo_pontinhos\Treinamento_CNN_Pontinhos_V10.ipynb'
with open(path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# ── Nova fonte da célula de treinamento ──────────────────────────────────────
NEW_TRAINING = """\
# =========================================================================
# 3. TREINAMENTO
# =========================================================================
_iniciar_secao('treinamento')
_md_h(2, '3. Treinamento')

from tensorflow.keras.callbacks import ModelCheckpoint

_ckpt_path = os.path.join(RESULTADO_DIR, f'BoxNet_V10_{K}canais_best_valloss.keras')

if os.path.exists(_ckpt_path):
    # Recuperacao: checkpoint ja existe — pula treinamento e carrega pesos salvos.
    print(f'Checkpoint encontrado: {_ckpt_path}')
    print('Carregando modelo salvo (treinamento pulado)...')
    with tf.device('/CPU:0'):
        model = tf.keras.models.load_model(_ckpt_path)
    history = None
    rprint('*(modelo carregado de checkpoint — treinamento pulado)*\\n')
    rprint('| Metrica | Valor |')
    rprint('|---------|-------|')
    rprint(f'| Checkpoint | `{os.path.basename(_ckpt_path)}` |')
    rprint()
    print('Modelo carregado. Pronto para avaliacao (celulas seguintes).')
else:
    # Treinamento normal do zero.
    rprint('*(logs de epoca omitidos do relatorio — ver notebook)*\\n')
    callbacks = [
        EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=4, min_lr=1e-5, verbose=1),
        ModelCheckpoint(
            _ckpt_path,
            monitor='val_loss',
            save_best_only=True,
            verbose=1,
        ),
    ]
    print(f'Checkpoint sera salvo em: {_ckpt_path}')

    history = model.fit(
        X_train, y_train,
        epochs=300,
        batch_size=256,
        validation_data=(X_val, y_val),
        sample_weight=sw,
        callbacks=callbacks,
        verbose=1,
    )

    ult = len(history.history['loss']) - 1
    rprint('| Metrica | Valor |')
    rprint('|---------|-------|')
    rprint(f'| Epocas treinadas | {ult + 1} |')
    rprint(f'| KLD final — treino | {history.history["loss"][ult]:.4f} |')
    rprint(f'| KLD final — val | {history.history["val_loss"][ult]:.4f} |')
    rprint(f'| Top-1 final — treino | {history.history["accuracy"][ult]:.4f} |')
    rprint(f'| Top-1 final — val | {history.history["val_accuracy"][ult]:.4f} |')
    rprint()

_md_sep()
"""

# ── Guard para os gráficos de curva de aprendizado (history pode ser None) ──
LEARNING_CURVE_OLD = """\
# 4.5 Gráficos de treino (não capturados no relatório)
fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))"""

LEARNING_CURVE_NEW = """\
# 4.5 Gráficos de treino (não capturados no relatório)
if history is None:
    print('Histórico de treino não disponível (modelo carregado de checkpoint).')
else:
 fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))"""

# O restante do bloco de gráficos precisa ser indentado 1 espaço pois está dentro do else.
# Mais simples: substituir todo o bloco de curvas.

CURVES_BLOCK_OLD = (
    "# 4.5 Gráficos de treino (não capturados no relatório)\n"
    "fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))\n"
    "axes[0].plot(history.history['accuracy'],     label='Treino')\n"
    "axes[0].plot(history.history['val_accuracy'], label='Validacao')\n"
    "axes[0].set_title('Top-1 Accuracy'); axes[0].legend(); axes[0].grid(True)\n"
    "axes[1].plot(history.history['top3_acc'],     label='Treino')\n"
    "axes[1].plot(history.history['val_top3_acc'], label='Validacao')\n"
    "axes[1].set_title('Top-3 Accuracy'); axes[1].legend(); axes[1].grid(True)\n"
    "axes[2].plot(history.history['loss'],     label='Treino (KLD)')\n"
    "axes[2].plot(history.history['val_loss'], label='Validacao (KLD)')\n"
    "axes[2].set_title('KL Divergence Loss'); axes[2].legend(); axes[2].grid(True)\n"
    "plt.suptitle(f'BoxNet v3 V8 — {K} canais estruturais', fontsize=13)\n"
    "plt.tight_layout(); plt.show()"
)

CURVES_BLOCK_NEW = (
    "# 4.5 Gráficos de treino (não capturados no relatório)\n"
    "if history is not None:\n"
    "    fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))\n"
    "    axes[0].plot(history.history['accuracy'],     label='Treino')\n"
    "    axes[0].plot(history.history['val_accuracy'], label='Validacao')\n"
    "    axes[0].set_title('Top-1 Accuracy'); axes[0].legend(); axes[0].grid(True)\n"
    "    axes[1].plot(history.history['top3_acc'],     label='Treino')\n"
    "    axes[1].plot(history.history['val_top3_acc'], label='Validacao')\n"
    "    axes[1].set_title('Top-3 Accuracy'); axes[1].legend(); axes[1].grid(True)\n"
    "    axes[2].plot(history.history['loss'],     label='Treino (KLD)')\n"
    "    axes[2].plot(history.history['val_loss'], label='Validacao (KLD)')\n"
    "    axes[2].set_title('KL Divergence Loss'); axes[2].legend(); axes[2].grid(True)\n"
    "    plt.suptitle(f'BoxNet v3 V8 — {K} canais estruturais', fontsize=13)\n"
    "    plt.tight_layout(); plt.show()\n"
    "else:\n"
    "    print('Curvas de aprendizado indisponiveis (modelo carregado de checkpoint).')"
)

for cell in nb['cells']:
    cid = cell.get('id', '')

    if cid == '593a9cfd':
        cell['source'] = NEW_TRAINING
        cell['outputs'] = []
        cell['execution_count'] = None
        print('Patched 593a9cfd (treinamento com recovery)')

    if cid == 'afb8515e':
        src = cell['source'] if isinstance(cell['source'], str) else ''.join(cell['source'])
        if CURVES_BLOCK_OLD in src:
            src = src.replace(CURVES_BLOCK_OLD, CURVES_BLOCK_NEW)
            cell['source'] = src
            cell['outputs'] = []
            cell['execution_count'] = None
            print('Patched afb8515e (guard history)')
        else:
            print('AVISO: bloco de curvas nao encontrado em afb8515e — verifique manualmente.')

with open(path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print('Done.')
