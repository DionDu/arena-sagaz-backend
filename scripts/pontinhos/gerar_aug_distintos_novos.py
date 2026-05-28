# -*- coding: utf-8 -*-
"""Gera um unico NPZ consolidado com as amostras DISTINTAS NOVAS dos NPZ
_refH/_refV/_r180 que NAO estao presentes nos originais.

Saida: <PASTA_NPZ>/aug_distintos_novos_todos_t.npz com os mesmos campos do
schema NPZ do projeto (estados, canais, melhor_jogada, score_melhor_jogada,
qtd_tracos, qtd_cadeias_longas, labels_canonicos), permitindo que o notebook
de treino carregue esse arquivo lado a lado com os 419 originais sem precisar
de logica especial.

Uso:
    .venv_gpu/Scripts/python scripts/pontinhos/gerar_aug_distintos_novos.py

Tempo esperado (PC local): ~2-4 min. Memoria pico: ~6-8 GB.
"""
from __future__ import annotations

import glob
import os
import sys
import time

import numpy as np


# Pasta padrao do projeto. Se necessario, passe outra como argv[1].
PASTA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    'dados', 'profundidade_minimax_11_adaptativo')
SAIDA = os.path.join(PASTA, 'aug_distintos_novos_todos_t.npz')

SUFIXOS_AUG = ('_refH', '_refV', '_r180')


def _eh_aug(caminho: str) -> bool:
    base = os.path.basename(caminho)
    return any(s in base for s in SUFIXOS_AUG)


def main() -> None:
    todos = sorted(glob.glob(os.path.join(PASTA, '*.npz')))
    orig = [a for a in todos if not _eh_aug(a)
            and os.path.basename(a) != os.path.basename(SAIDA)]
    augm = [a for a in todos if _eh_aug(a)]
    print(f'{len(orig)} originais, {len(augm)} augmentados')
    print(f'Saida: {SAIDA}')

    # ----- Etapa 1: states dos originais (para comparacao de dedup) -----
    print('\n[1/4] Lendo states dos originais...')
    t0 = time.time()
    orig_states_list = []
    for a in orig:
        orig_states_list.append(np.load(a)['estados'].reshape(-1, 63))
    orig_states = np.concatenate(orig_states_list, axis=0)
    del orig_states_list
    orig_uniq = np.unique(orig_states, axis=0)
    print(f'    [{time.time()-t0:.0f}s] Originais distintos: {len(orig_uniq):,}')
    del orig_states

    # ----- Etapa 2: TODOS os campos dos augmentados -----
    print('\n[2/4] Lendo TODOS os campos dos augmentados...')
    t0 = time.time()
    estados_l, canais_l, melhor_l, score_l, qt_l, cad_l = [], [], [], [], [], []
    labels_canonicos = None
    for i, a in enumerate(augm):
        if i % 200 == 0 and i > 0:
            print(f'    {i}/{len(augm)}...')
        dd = np.load(a, allow_pickle=True)
        estados_l.append(dd['estados'])
        canais_l.append(dd['canais'])
        melhor_l.append(dd['melhor_jogada'])
        score_l.append(dd['score_melhor_jogada'])
        qt_l.append(dd['qtd_tracos'])
        cad_l.append(dd['qtd_cadeias_longas'])
        if labels_canonicos is None:
            labels_canonicos = dd['labels_canonicos']
    estados = np.concatenate(estados_l, axis=0)
    canais = np.concatenate(canais_l, axis=0)
    melhor = np.concatenate(melhor_l, axis=0)
    score = np.concatenate(score_l, axis=0)
    qtd_tracos = np.concatenate(qt_l, axis=0)
    qtd_cadeias = np.concatenate(cad_l, axis=0)
    del estados_l, canais_l, melhor_l, score_l, qt_l, cad_l
    print(f'    [{time.time()-t0:.0f}s] Augmentados brutas: {len(estados):,}')
    print(f'    Dtypes: estados={estados.dtype} canais={canais.dtype} '
          f'melhor={melhor.dtype} score={score.dtype} qt={qtd_tracos.dtype}')

    # ----- Etapa 3: identifica indices NOVOS distintos -----
    print('\n[3/4] Identificando distintos NOVOS (nao presentes nos originais)...')
    t0 = time.time()
    states_2d = estados.reshape(-1, 63)
    _, idx_uniq = np.unique(states_2d, axis=0, return_index=True)
    aug_uniq_states = states_2d[idx_uniq]
    print(f'    [{time.time()-t0:.0f}s] Augmentados distintos: {len(idx_uniq):,}')

    t0 = time.time()
    combined = np.concatenate([orig_uniq, aug_uniq_states], axis=0)
    _, inv = np.unique(combined, axis=0, return_inverse=True)
    inv_orig = inv[:len(orig_uniq)]
    inv_aug = inv[len(orig_uniq):]
    mask_novos = ~np.isin(inv_aug, inv_orig)
    idx_novos = np.sort(idx_uniq[mask_novos])
    n_novos = len(idx_novos)
    print(f'    [{time.time()-t0:.0f}s] Distintos NOVOS: {n_novos:,}')

    # ----- Etapa 4: salva NPZ consolidado -----
    print(f'\n[4/4] Salvando {n_novos:,} amostras em {SAIDA}...')
    t0 = time.time()
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    np.savez_compressed(
        SAIDA,
        estados=estados[idx_novos],
        canais=canais[idx_novos],
        melhor_jogada=melhor[idx_novos],
        score_melhor_jogada=score[idx_novos],
        qtd_tracos=qtd_tracos[idx_novos],
        qtd_cadeias_longas=qtd_cadeias[idx_novos],
        labels_canonicos=labels_canonicos,
    )
    tam_mb = os.path.getsize(SAIDA) / 1e6
    print(f'    [{time.time()-t0:.0f}s] Tamanho do arquivo: {tam_mb:.0f} MB')

    # Auditoria
    print('\nAuditoria do arquivo salvo:')
    dd = np.load(SAIDA, allow_pickle=True)
    print(f'  Campos: {sorted(dd.files)}')
    for k in ['estados', 'canais', 'melhor_jogada', 'score_melhor_jogada',
              'qtd_tracos', 'qtd_cadeias_longas']:
        v = dd[k]
        print(f'  {k:25s} shape={v.shape!s:25s} dtype={v.dtype}')
    print(f'  labels_canonicos: {len(dd["labels_canonicos"])} labels')

    print('\nProjecao do dataset final no Colab:')
    print(f'  419 originais (brutas):   3,423,460')
    print(f'+ Este arquivo (distintos): {n_novos:>9,}')
    print(f'= Total:                    {3_423_460 + n_novos:>9,}')


if __name__ == '__main__':
    main()
