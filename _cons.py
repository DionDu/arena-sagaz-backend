import os, glob, json, time
import random as _random
from collections import Counter, defaultdict
import numpy as np

REPO_ROOT        = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend'
DIR_LEGADO       = os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9_desbalanceado')
DIR_V5_DATABRICKS= os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9_v5_databricks')
DIR_V5_LOCAL     = os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9_v5_local')
DIR_FINAL        = os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9')
os.makedirs(DIR_FINAL, exist_ok=True)

TAMANHO_LOTE = 5_000
SEED_GLOBAL  = 42

print(f'DIR_LEGADO        : {DIR_LEGADO}')
print(f'DIR_V5_DATABRICKS : {DIR_V5_DATABRICKS}')
print(f'DIR_V5_LOCAL      : {DIR_V5_LOCAL}')
print(f'DIR_FINAL         : {DIR_FINAL}')
print(f'TAMANHO_LOTE: {TAMANHO_LOTE:,}')


# ====== CELL ======

# === Cota alvo — PRD §4.1.3 rev.5 (2026-05-08) ===
#
# rev.5: todas as celulas capeadas nos unicos reais disponiveis.
#   Excedente redistribuido para mode_3 em (12-17) e (18-23).
#
# Celulas capeadas (rev.5):
#   mode_2 (12,17): 67.898 unicos disponiveis (cota rev.4: 68.597, delta -699)
#   mode_2 (18,23): 83.787 unicos disponiveis (cota rev.4: 97.705, delta -13.918)
#   mode_2 (29,30): 84 unicos (cota rev.4: 87, delta -3)
#   mode_3 (24,28): 21.261 unicos (cota rev.4: 21.458, delta -197)
#   Total liberado: 14.817
#
# Redistribuicao para mode_3 (tem excedente de unicos):
#   mode_3 (18,23): 121.343 + 7.392 = 128.735 (cap no max disponivel: 128.735)
#   mode_3 (12,17): 86.674 + 7.425 = 94.099 (disponivel: 104.010 >> 94.099)
#   Total redistribuido: 7.392 + 7.425 = 14.817 ✓
#
# Mix gen_mode: mode_0=5.0%, mode_2=40.1%, mode_3=54.9%
#   (praticamente inalterado do alvo 5/40/55).

PESO_GEN    = {0: 0.05, 2: 0.40, 3: 0.55}
BUCKETS     = [(5, 11), (12, 17), (18, 23), (24, 28), (29, 30)]
ALVO_TOTAL  = 500_000

# Cotas explicitas — capeadas nos unicos reais de todas as fontes.
cota_alvo = {
    # mode_0: inalterado
    (0, (5, 11)):  2_775,
    (0, (12, 17)): 7_879,
    (0, (18, 23)): 11_031,
    (0, (24, 28)): 3_289,
    (0, (29, 30)):    25,
    # mode_2: (12,17) e (18,23) capeados nos unicos reais
    (2, (5, 11)):  22_200,
    (2, (12, 17)): 67_898,   # cap: 67.898 unicos disponiveis
    (2, (18, 23)): 83_787,   # cap: 83.787 unicos disponiveis
    (2, (24, 28)): 26_317,
    (2, (29, 30)):     84,   # cap: 84 unicos disponiveis
    # mode_3: (12,17) e (18,23) recebem redistribuicao; (24,28) capeado
    (3, (5, 11)):  30_526,
    (3, (12, 17)): 94_099,   # 86.674 + 7.425 redistribuidos
    (3, (18, 23)): 128_735,  # 121.343 + 7.392 redistribuidos (cap no max disponivel)
    (3, (24, 28)): 21_261,   # cap: 21.261 unicos disponiveis
    (3, (29, 30)):     94,
}

_total = sum(cota_alvo.values())
assert _total == ALVO_TOTAL, f'Soma cota_alvo {_total:,} != {ALVO_TOTAL:,}'

print(f'cota_alvo (total {_total:,}):')
print(f"  {'celula':<22} {'cota':>7}")
for m in sorted(PESO_GEN):
    for b in BUCKETS:
        print(f'  mode_{m} bucket {str(b):<10} {cota_alvo[(m, b)]:>7,}')
    print(f"  {'  -- subtotal mode_' + str(m):<22} {sum(cota_alvo[(m, b)] for b in BUCKETS):>7,}")
print(f'\nNOTA rev.5: todas as cotas capeadas nos unicos reais. Zero shortfall esperado.')


def bucket_de(t):
    return next((b for b in BUCKETS if b[0] <= t <= b[1]), None)

# ====== CELL ======

# === Estado da consolidacao (acumulado entre os passos 1 e 2) ===

hashes_unicos = set()
aceitos = {k: 0 for k in cota_alvo}     # contador por celula (mode, bucket)
estados_out, rotulos_out, scores_out, modes_out = [], [], [], []
labels_canon = None
minimax_depth_canon  = None

# Contadores de descarte (uteis pra auditoria do que veio do legado).
descartado = defaultdict(int)
origem_aceitos = defaultdict(int)        # 'legado' | 'v5_local'


def processa_arquivo(arq: str, origem: str) -> None:
    """Le um NPZ e tenta aceitar cada estado conforme regras de cota + dedup."""
    global labels_canon, minimax_depth_canon
    d = np.load(arq, allow_pickle=True)
    estados = d['estados']
    rotulos = d['rotulos']
    scores  = d['scores']
    modes   = d['generation_mode']

    # Schema: snapshot do primeiro arquivo, valida demais.
    if labels_canon is None:
        labels_canon = np.array(d['labels_canonicos'])
        minimax_depth_canon  = np.array(d['minimax_depth'])
    else:
        if not np.array_equal(labels_canon, d['labels_canonicos']):
            raise ValueError(f'labels_canonicos divergente em {arq}')
        if not np.array_equal(minimax_depth_canon, d['minimax_depth']):
            raise ValueError(f'minimax_depth divergente em {arq}')

    n = len(estados)
    indices = list(range(n))
    rng = _random.Random(hash(os.path.basename(arq)) & 0x7FFFFFFF)
    rng.shuffle(indices)

    for i in indices:
        mat = estados[i]
        m   = int(modes[i])
        if m == 1:
            descartado['sim_l1'] += 1
            continue
        if m not in PESO_GEN:
            descartado['mode_invalido'] += 1
            continue
        n_tracos = int((mat == 9).sum())
        b = bucket_de(n_tracos)
        if b is None:
            descartado['bucket_fora'] += 1
            continue
        h = mat.tobytes()
        if h in hashes_unicos:
            descartado['duplicado'] += 1
            continue
        cell = (m, b)
        if aceitos[cell] >= cota_alvo[cell]:
            descartado['cota_excedida'] += 1
            continue

        hashes_unicos.add(h)
        aceitos[cell] += 1
        origem_aceitos[origem] += 1
        estados_out.append(np.array(mat, dtype=np.int8, copy=True))
        rotulos_out.append(str(rotulos[i]))
        scores_out.append(np.array(scores[i], dtype=np.float32, copy=True))
        modes_out.append(m)


def imprime_aceitos_por_celula(titulo: str) -> None:
    print(f'\n--- {titulo} ---')
    print(f"  {'celula':<22} {'aceitos':>8} {'cota':>8} {'falta':>8}")
    for m in sorted(PESO_GEN):
        for b in BUCKETS:
            c = (m, b)
            print(f'  mode_{m} bucket {str(b):<10} {aceitos[c]:>8,} {cota_alvo[c]:>8,} {cota_alvo[c]-aceitos[c]:>8,}')
    print(f"  {'TOTAL':<22} {sum(aceitos.values()):>8,} {sum(cota_alvo.values()):>8,} {sum(cota_alvo.values())-sum(aceitos.values()):>8,}")


print('Estado inicial pronto.')

# ====== CELL ======

# === Passo 1: legado ===
# Aceita ate cota_alvo[m,b] de cada celula. O excedente (incluindo modo 1
# inteiro, bucket <5, e excedentes por cota) e descartado.

t0 = time.time()
arqs_leg = sorted(glob.glob(os.path.join(DIR_LEGADO, 'dataset_pequeno_*.npz')))
if not arqs_leg:
    raise FileNotFoundError(f'Nenhum NPZ encontrado em {DIR_LEGADO}')
print(f'Lendo {len(arqs_leg)} arquivos legado...')
for k, arq in enumerate(arqs_leg, 1):
    processa_arquivo(arq, 'legado')
    if k % 10 == 0 or k == len(arqs_leg):
        print(f'  {k}/{len(arqs_leg)} | aceitos={sum(aceitos.values()):,} | t={time.time()-t0:.1f}s')

imprime_aceitos_por_celula('Apos passo 1 (legado)')
print(f"\nDescartado nesta fase (acumulado):")
for k, v in sorted(descartado.items()):
    print(f'  {k}: {v:,}')

# ====== CELL ======

# === Passo 2: v5_databricks + v5_local (complemento) ===
# Prioridade: v5_databricks primeiro (menor sobrefluxo esperado), depois v5_local.

t1 = time.time()
for fonte, diretorio in [('v5_databricks', DIR_V5_DATABRICKS), ('v5_local', DIR_V5_LOCAL)]:
    arqs = sorted(glob.glob(os.path.join(diretorio, 'dataset_pequeno_*.npz')))
    if not arqs:
        print(f'AVISO: nenhum NPZ em {diretorio} ({fonte}).')
        continue
    print(f'Lendo {len(arqs)} arquivos {fonte}...')
    for k, arq in enumerate(arqs, 1):
        processa_arquivo(arq, fonte)
        if k % 10 == 0 or k == len(arqs):
            print(f'  {k}/{len(arqs)} | aceitos={sum(aceitos.values()):,} | t={time.time()-t1:.1f}s')

imprime_aceitos_por_celula('Apos passo 2 (legado + v5_databricks + v5_local)')
print(f"\nDescartado total ate aqui:")
for k, v in sorted(descartado.items()):
    print(f'  {k}: {v:,}')
print(f"\nOrigem dos aceitos:")
for k, v in sorted(origem_aceitos.items()):
    print(f'  {k}: {v:,}')

_total_aceitos = sum(aceitos.values())
_falta = ALVO_TOTAL - _total_aceitos
if _falta == 0:
    print(f'\nTotal {_total_aceitos:,} — 500.000 exato. Pronto para gravar.')
elif _falta <= 1_000:
    print(f'\nTotal {_total_aceitos:,} — shortfall residual de {_falta:,} (< 0,2%). Pronto para gravar.')
else:
    print(f'\nATENCAO: faltam {_falta:,} estados. Gerar mais dados no V5_Local antes de gravar.')

# ====== CELL ======

# === Gravacao do consolidado ===
# Embaralha a ordem global (seed fixa) para misturar legado/v5_local entre os NPZs
# de saida. Sem isso os primeiros NPZs seriam so legado e os ultimos so v5_local.

N = len(estados_out)
if N == 0:
    raise RuntimeError('Nada a gravar. Verifique se os diretorios de entrada tem dados.')

indices = list(range(N))
_random.Random(SEED_GLOBAL).shuffle(indices)

# Limpa NPZs anteriores em DIR_FINAL para evitar mistura com rodada antiga.
antigos = sorted(glob.glob(os.path.join(DIR_FINAL, 'dataset_pequeno_*.npz')))
if antigos:
    print(f'Removendo {len(antigos)} NPZs anteriores em {DIR_FINAL}...')
    for arq in antigos:
        os.remove(arq)

ul = 0
t2 = time.time()
for i0 in range(0, N, TAMANHO_LOTE):
    chunk = indices[i0:i0 + TAMANHO_LOTE]
    ul += 1
    path = os.path.join(DIR_FINAL, f'dataset_pequeno_{ul:04d}.npz')
    np.savez_compressed(
        path,
        estados          = np.array([estados_out[i] for i in chunk], dtype=np.int8),
        rotulos          = np.array([rotulos_out[i] for i in chunk], dtype=str),
        scores           = np.array([scores_out[i] for i in chunk], dtype=np.float32),
        generation_mode  = np.array([modes_out[i] for i in chunk], dtype=np.int8),
        labels_canonicos = labels_canon,
        minimax_depth = minimax_depth_canon,
    )
    if ul % 10 == 0 or i0 + TAMANHO_LOTE >= N:
        print(f'  Batch {ul:04d} -> {os.path.basename(path)} ({len(chunk)} estados) | t={time.time()-t2:.1f}s')

print(f'\nGravados {ul} NPZs em {DIR_FINAL} ({N:,} estados, {time.time()-t2:.1f}s).')

# ====== CELL ======

# === Auditoria pos-gravacao ===

arqs = sorted(glob.glob(os.path.join(DIR_FINAL, 'dataset_pequeno_*.npz')))
hashes_aud  = set()
modes_aud   = []
tracos_aud  = []
for arq in arqs:
    d = np.load(arq, allow_pickle=True)
    for i in range(len(d['estados'])):
        mat = d['estados'][i]
        hashes_aud.add(mat.tobytes())
        modes_aud.append(int(d['generation_mode'][i]))
        tracos_aud.append(int((mat == 9).sum()))

total = len(modes_aud)
print(f'Total auditado: {total:,}')
print(f'Unicos por mat.tobytes(): {len(hashes_aud):,}')
assert len(hashes_aud) == total, 'Existem duplicatas no consolidado.'

# Distribuicao por bucket (alvo derivado de cota_alvo)
bucket_alvo_aud = {}
for (m, b), v in cota_alvo.items():
    bucket_alvo_aud[b] = bucket_alvo_aud.get(b, 0) + v

cont_buc = Counter(bucket_de(t) for t in tracos_aud)
print('\nDistribuicao por bucket:')
print(f"  {'Bucket':<10} {'N':>8} {'%real':>7} {'alvo_N':>8} {'desvio_pp':>10}")
for b in BUCKETS:
    n = cont_buc.get(b, 0)
    pct = n / total * 100 if total else 0
    alvo_n = bucket_alvo_aud[b]
    alvo_pct = alvo_n / ALVO_TOTAL * 100
    desv = pct - alvo_pct
    tol = 2.0
    flag = 'OK' if abs(desv) <= tol else 'FORA DA TOLERANCIA'
    print(f'  {str(b):<10} {n:>8,} {pct:>6.2f}% {alvo_n:>8,} {desv:>+9.2f}  {flag}')

# Mix de gen_mode
cont_mode = Counter(modes_aud)
print('\nMix de gen_mode:')
for m, p in sorted(PESO_GEN.items()):
    n = cont_mode.get(m, 0)
    pct = n / total * 100 if total else 0
    alvo = p * 100
    desv = pct - alvo
    print(f'  mode_{m}: {n:>7,} ({pct:>5.2f}%, alvo {alvo:.2f}%, desvio {desv:+.2f}pp)')

# sim_l1 zerado
n_sim_l1 = cont_mode.get(1, 0)
print(f'\nsim_l1 (mode 1): {n_sim_l1} (esperado 0)')
assert n_sim_l1 == 0, f'sim_l1 deve estar 0, encontrado {n_sim_l1}'

# Total: aceita shortfall residual minimo (arredondamentos).
# rev.4 eliminou o shortfall de celulas saturadas via redistribuicao.
SHORTFALL_MAX = 1_000
if total >= ALVO_TOTAL - SHORTFALL_MAX:
    print(f'\nAUDITORIA OK — {total:,} consolidados (shortfall {ALVO_TOTAL-total:,}, max aceito {SHORTFALL_MAX:,}).')
    print('Pronto para Enriquece_NPZ_Com_Canais.ipynb.')
else:
    print(f'\nATENCAO: total {total:,} < {ALVO_TOTAL - SHORTFALL_MAX:,} (shortfall {ALVO_TOTAL-total:,} > {SHORTFALL_MAX:,}).')
    print('Verificar se o V5_Local terminou a geracao — rodar COMPLEMENTO_POR_CELULA rev.4.')