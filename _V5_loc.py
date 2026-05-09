import os, sys, glob, json, time, random
import numpy as np
from multiprocessing import Pool, cpu_count

# Garante que o engine companheiro fica importavel pelos workers spawnados.
_THIS_DIR = os.path.dirname(os.path.abspath(globals().get('__vsc_ipynb_file__', os.getcwd())))
if not os.path.isfile(os.path.join(_THIS_DIR, 'v5_local_engine.py')):
    _THIS_DIR = os.path.join(os.getcwd(), 'notebooks', 'jogo_pontinhos')
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import v5_local_engine as eng
from v5_local_engine import MODE_NAMES
print('Engine importado de:', eng.__file__)
print('CPUs logicas detectadas:', cpu_count())

# ====== CELL ======

# === Parametros de execucao ===
ROWS, COLS     = 4, 3
DEPTH          = 9
TAMANHO_LOTE   = 5_000
SCORE_IND      = -1e9

N_WORKERS      = max(1, cpu_count() - 1)
BATCH_DISPATCH = N_WORKERS * 8
LOG_INTERVAL_S = 30

REPO_ROOT          = r'D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend'
DIR_LEGADO         = os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9')
DIR_V5_DATABRICKS  = os.path.join(REPO_ROOT, 'dados', 'profundidade_minmax_9_v5_databricks')
DIRETORIO_SAIDA    = os.path.join(REPO_ROOT, 'dados', f'profundidade_minmax_{DEPTH}_v5_local')
os.makedirs(DIRETORIO_SAIDA, exist_ok=True)

# === V5 Fase A.1 — PRD §4.1.3 rev.3 (2026-05-08) ===
#
# Bucket (29,30): CONCLUIDO — limite fisico absoluto C(31,29)+C(31,30) = 465+31 = 496 estados.
#   Todos os 496 estados unicos possiveis ja foram coletados.
#
# Bucket (24,28): CONCLUIDO — 65.792 unicos coletados (57.020 via autoplay + 9.170 mode_0).
#   O espaco pratico do autoplay (sim_l2/sim_l3) esta saturado em ~57.020 estados:
#   o Minimax converge para trajetorias de jogo limitadas, atingindo apenas ~57k das
#   991.333 combinacoes teoricas C(31,24..28). Mode_0 cobre estados aleatorios (humanos/
#   jogadores subotimos) na proporcao correta (~5%). Nao ha ganho em gerar mais.
#
# Bucket (12,17): CONCLUIDO — 166.099 coletados (acima do alvo de 157.588).
#
# Redistribuicao: a cota remanescente de (24,28) foi realocada para (18,23): 12.542 estados.
#
# COMPLEMENTO_POR_CELULA = alvo TOTAL que V5_Local deve ter em cada celula
# (incluindo o que ja esta em DIRETORIO_SAIDA — o checkpoint subtrai o existente).
#
#   mode_0 (18,23) =   627  ( 5% de 12.542)
#   mode_2 (18,23) = 5.017  (40% de 12.542)
#   mode_3 (18,23) = 6.898  (55% de 12.542)

STRAT_WEIGHTS  = [0.05, 0.00, 0.40, 0.55]
assert abs(sum(STRAT_WEIGHTS) - 1.0) < 1e-9
assert STRAT_WEIGHTS[1] == 0.0, 'sim_l1 (modo 1) DEVE ter peso 0 (D1.a)'

COMPLEMENTO_POR_CELULA = {
    0: {(5, 11): 0, (12, 17):      0, (18, 23):      0, (24, 28): 0, (29, 30): 0},
    2: {(5, 11): 0, (12, 17): 19_875, (18, 23): 31_902, (24, 28): 0, (29, 30): 0},
    3: {(5, 11): 0, (12, 17):      0, (18, 23):      0, (24, 28): 0, (29, 30): 0},
}
# Total: 51_777


FAIXA_TRACOS = (0.15, 0.97)
BUCKETS = [(5, 11), (12, 17), (18, 23), (24, 28), (29, 30)]

_n, _mask, _eboxes, _labels, _brc, _bmasks = eng.build_topology_tables(ROWS, COLS)
_idx_label = {l: i for i, l in enumerate(_labels)}
_n_labels  = len(_labels)

print('=== CONFIGURATION ===')
print(f'Grid: {ROWS}x{COLS}, {_n} edges')
print(f'DEPTH: {DEPTH} | Workers: {N_WORKERS} (cpu_count={cpu_count()}) | BATCH_DISPATCH: {BATCH_DISPATCH}')
print(f'Output     : {DIRETORIO_SAIDA}')
print(f'Legado     : {DIR_LEGADO}')
print(f'Databricks : {DIR_V5_DATABRICKS}')
print(f'Restante estimado apos checkpoint: ~12.542 (PRD §4.1.3 rev.3)')


# ====== CELL ======

# === Pre-popular set de hashes com os unicos do legado + v5_databricks ===
# Impede que V5_Local regere estados ja cobertos por qualquer outra fonte.

hashes_iniciais = set()
_n_lidos = 0

for origem, dirpath in [('legado', DIR_LEGADO), ('v5_databricks', DIR_V5_DATABRICKS)]:
    if not os.path.isdir(dirpath):
        print(f'AVISO: {dirpath} nao existe — pulando {origem}.')
        continue
    arqs = sorted(glob.glob(os.path.join(dirpath, 'dataset_pequeno_*.npz')))
    cnt = 0
    for arq in arqs:
        d = np.load(arq, allow_pickle=True)
        for mat in d['estados']:
            hashes_iniciais.add(mat.tobytes())
            cnt += 1
    _n_lidos += cnt
    print(f'{origem}: {len(arqs)} arquivos | {cnt:,} estados | unicos acumulados: {len(hashes_iniciais):,}')

print(f'\nTotal lidos (legado + v5_databricks): {_n_lidos:,} | unicos no set inicial: {len(hashes_iniciais):,}')


# ====== CELL ======

# === Helpers de gravacao e checkpoint ===

def vetor_scores(sd, il, nl):
    v = np.full(nl, SCORE_IND, dtype=np.float32)
    for lbl, val in sd.items():
        v[il[lbl]] = float(val)
    return v


def salva_lote(ul, estados, rotulos, scores_l, gen_modes):
    path = os.path.join(DIRETORIO_SAIDA, f'dataset_pequeno_{ul:04d}.npz')
    np.savez_compressed(
        path,
        estados          = np.array(estados, dtype=np.int8),
        rotulos          = np.array(rotulos, dtype=str),
        scores           = np.array(scores_l, dtype=np.float32),
        generation_mode  = np.array(gen_modes, dtype=np.int8),
        labels_canonicos = np.array(_labels, dtype=str),
        minimax_depth = np.array([DEPTH], dtype=np.int32),
    )
    return path


def log_prog(gerados, total, inicio, dups=0, falhas=0):
    dec = time.time() - inicio
    rate = gerados / dec if dec > 0 else 0.0
    rest = (total - gerados) / rate if rate > 0 else 0.0
    print(json.dumps({
        'gerados'    : gerados,
        'total'      : total,
        'pct'        : round(gerados / total * 100, 2),
        'rate_sps'   : round(rate, 2),
        'duplicados' : dups,
        'falhas'     : falhas,
        'decorrido_s': round(dec, 2),
        'restante_s' : round(rest, 2),
        'restante_h' : round(rest / 3600, 2),
    }))


def _bucket_de(t):
    return next((b for b in BUCKETS if b[0] <= t <= b[1]), None)

# ====== CELL ======

# === Checkpoint: retomar a partir do diretorio de saida ===
# Le NPZs ja gerados nesta rodada para:
#  (a) reconstruir o set de hashes globais (legado + ja gerados)
#  (b) decrementar `quotas` pela quantidade ja gerada por (gen_mode, bucket)
#  (c) descobrir o ultimo `ul` para o nome do proximo arquivo

quotas = {(m, b): q for m, cells in COMPLEMENTO_POR_CELULA.items() for b, q in cells.items()}
quotas = {k: v for k, v in quotas.items() if v > 0}
total_a_gerar = sum(quotas.values())  # 12_542 do zero

hashes_unicos = set(hashes_iniciais)
ul = 0
ja_gerados_nesta_rodada = 0

arqs_existentes = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
if arqs_existentes:
    ul = int(arqs_existentes[-1].split('_')[-1].split('.')[0])
    for arq in arqs_existentes:
        d = np.load(arq, allow_pickle=True)
        gm  = d['generation_mode']
        est = d['estados']
        for i in range(len(est)):
            mat = est[i]
            hashes_unicos.add(mat.tobytes())
            n_tracos = int((mat == 9).sum())
            b = _bucket_de(n_tracos)
            cell = (int(gm[i]), b)
            if cell in quotas and quotas[cell] > 0:
                quotas[cell] -= 1
                ja_gerados_nesta_rodada += 1
    quotas = {k: v for k, v in quotas.items() if v > 0}
    print(f'Checkpoint: retomando do batch {ul} | ja gerados nesta rodada: {ja_gerados_nesta_rodada:,}')
    print(f'Cotas restantes: {sum(quotas.values()):,} de {total_a_gerar:,}')
else:
    print(f'Comecando do zero. Set inicial de hashes: {len(hashes_unicos):,} (legado + v5_databricks).')
    print(f'Cotas a preencher: {total_a_gerar:,}')


# ====== CELL ======

# === Loop principal por cota (PRD §4.1.3 + tasks.md T-A1-004) ===
#
# Estrategia:
#  1. Sorteia BATCH_DISPATCH celulas (gen_mode, bucket) ponderadas pela cota residual.
#  2. Pool.map dispara worker para cada celula; worker tenta gerar ate 20 vezes.
#  3. Main deduplica por mat.tobytes(), confere bucket, decrementa cota daquela
#     celula. Sobrefluxo (cota ja zerada, mas amostra valida) e descartado.
#  4. Repete ate `quotas` zerar.
#  5. NPZs sao gravados a cada TAMANHO_LOTE estados aceitos.

estados, rotulos, scores_l, gen_modes = [], [], [], []
duplicados_total = 0
falhas_total     = 0
sobrefluxo_total = 0
total_gerado     = ja_gerados_nesta_rodada
inicio = time.time()
last_log = inicio

init_args = (ROWS, COLS, DEPTH, int(time.time()))
print(f'Iniciando Pool: {N_WORKERS} workers, batch_dispatch={BATCH_DISPATCH}, minimax_depth ={DEPTH}')

with Pool(processes=N_WORKERS, initializer=eng.init_worker, initargs=init_args) as pool:
    while quotas:
        cells   = list(quotas.keys())
        weights = [quotas[c] for c in cells]
        size    = min(BATCH_DISPATCH, sum(weights))
        sampled = random.choices(cells, weights=weights, k=size)
        tasks   = [(m, b[0], b[1]) for (m, b) in sampled]

        results = pool.map(eng.gen_one_sample_quota, tasks, chunksize=1)

        for r in results:
            if r is None:
                falhas_total += 1
                continue
            mat_bytes, shape, best, scores_json, mode, n_tracos = r
            if mat_bytes in hashes_unicos:
                duplicados_total += 1
                continue
            b = _bucket_de(n_tracos)
            if b is None:
                falhas_total += 1
                continue
            cell = (mode, b)
            if quotas.get(cell, 0) <= 0:
                # Sobrefluxo: sorteamos antes da cota zerar; descarta para nao
                # distorcer a distribuicao final.
                sobrefluxo_total += 1
                continue

            quotas[cell] -= 1
            if quotas[cell] == 0:
                del quotas[cell]
            hashes_unicos.add(mat_bytes)

            mat = np.frombuffer(mat_bytes, dtype=np.int8).reshape(shape)
            sd  = json.loads(scores_json)
            estados.append(mat)
            rotulos.append(best)
            scores_l.append(vetor_scores(sd, _idx_label, _n_labels))
            gen_modes.append(mode)
            total_gerado += 1

            if len(estados) >= TAMANHO_LOTE:
                ul += 1
                path = salva_lote(ul, estados, rotulos, scores_l, gen_modes)
                print(f'Batch {ul:04d} -> {path} ({len(estados)} estados)')
                estados, rotulos, scores_l, gen_modes = [], [], [], []

        now = time.time()
        if now - last_log >= LOG_INTERVAL_S:
            log_prog(total_gerado, total_a_gerar, inicio, duplicados_total, falhas_total)
            print(f'  cotas restantes: {sum(quotas.values()):,} | celulas abertas: {len(quotas)} | sobrefluxo: {sobrefluxo_total}')
            last_log = now

    if estados:
        ul += 1
        path = salva_lote(ul, estados, rotulos, scores_l, gen_modes)
        print(f'Batch {ul:04d} (final) -> {path} ({len(estados)} estados)')

log_prog(total_gerado, total_a_gerar, inicio, duplicados_total, falhas_total)
print(f'\nCompleted: {total_gerado:,} unicos novos | duplicados: {duplicados_total:,} '
      f'| falhas: {falhas_total} | sobrefluxo: {sobrefluxo_total}')

# ====== CELL ======

# === Diagnostic Metrics (sobre os NPZs gerados nesta rodada) ===
import matplotlib.pyplot as plt

arqs = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
print(f'Files: {len(arqs)} | Estimated records: {len(arqs)*TAMANHO_LOTE:,}')

all_modes, all_fill, all_best_score, all_score_range = [], [], [], []
for f in arqs:
    d = np.load(f, allow_pickle=True)
    gm  = d['generation_mode']
    est = d['estados']
    sc  = d['scores']
    for i in range(len(gm)):
        mat = est[i]
        h, w = mat.shape
        fill = sum(
            1
            for r in range(h) for c in range(w)
            if ((r % 2 == 0 and c % 2 == 1) or (r % 2 == 1 and c % 2 == 0)) and mat[r, c] != 0
        )
        valid = sc[i][sc[i] > -1e8]
        bs = float(valid.max()) if len(valid) else 0.0
        sr = float(valid.max() - valid.min()) if len(valid) > 1 else 0.0
        all_modes.append(int(gm[i]))
        all_fill.append(fill)
        all_best_score.append(bs)
        all_score_range.append(sr)

all_modes       = np.array(all_modes)
all_fill        = np.array(all_fill, dtype=float)
all_best_score  = np.array(all_best_score)
all_score_range = np.array(all_score_range)
total = len(all_modes)

print(f'Total records loaded: {total:,} | Generated with DEPTH={DEPTH}')
header = f'  {"Mode":<10}  {"N":>7}  {"% real":>7}  {"Fill_avg":>9}  {"BestScore":>10}  {"ScoreRange":>11}'
print(header); print('-' * len(header))
for m in sorted(set(all_modes.tolist())):
    mk = (all_modes == m)
    n  = int(mk.sum()); pct = n / total * 100
    print(f'  {MODE_NAMES.get(m, str(m)):<10}  {n:>7}  {pct:>6.1f}%  '
          f'{all_fill[mk].mean():>9.1f}  {all_best_score[mk].mean():>10.2f}  '
          f'{all_score_range[mk].mean():>11.2f}')

# ====== CELL ======

# === Auditoria pos-execucao ===
# Confere que as cotas de COMPLEMENTO_POR_CELULA foram preenchidas.
# A consolidacao final dos 500.000 e feita em Consolidar_500k_Final.ipynb.
from collections import Counter, defaultdict

_arqs = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
_set_unicos_novos = set()
_tracos_por_estado = []
_modo_por_estado = []
for arq in _arqs:
    d = np.load(arq, allow_pickle=True)
    gm = d['generation_mode']
    est = d['estados']
    for i in range(len(est)):
        mat = est[i]
        _set_unicos_novos.add(mat.tobytes())
        _tracos_por_estado.append(int((mat == 9).sum()))
        _modo_por_estado.append(int(gm[i]))

print(f'Total de estados gravados (rodada): {len(_tracos_por_estado):,}')
print(f'Unicos por mat.tobytes() (rodada): {len(_set_unicos_novos):,}')
print(f'Unicos legado+v5_databricks: {len(hashes_iniciais):,}')
print(f'Uniao total (todas fontes): {len(hashes_iniciais | _set_unicos_novos):,}')

# --- Cotas preenchidas vs alvo ---
preenchidos = defaultdict(int)
for t, m in zip(_tracos_por_estado, _modo_por_estado):
    b = _bucket_de(t)
    if b is not None:
        preenchidos[(m, b)] += 1

print()
print('Cotas COMPLEMENTO_POR_CELULA — preenchimento por celula:')
print(f"  {'celula':<22} {'alvo':>7} {'real':>7} {'desvio':>8}")
soma_alvo = 0; soma_real = 0
for m in sorted(COMPLEMENTO_POR_CELULA):
    for b in BUCKETS:
        alvo = COMPLEMENTO_POR_CELULA[m].get(b, 0)
        real = preenchidos.get((m, b), 0)
        if alvo == 0 and real == 0:
            continue
        soma_alvo += alvo; soma_real += real
        print(f'  mode_{m} bucket {str(b):<10} {alvo:>7,} {real:>7,} {real-alvo:>+8,}')
print(f"  {'TOTAL':<22} {soma_alvo:>7,} {soma_real:>7,} {soma_real-soma_alvo:>+8,}")

# --- Distribuicao por bucket (legado + rodada) ---
# Referencia: distribuicao alvo do dataset final consolidado (PRD §4.1.3 rev.3)
ALVO = {(5, 11): 0.1110, (12, 17): 0.3152, (18, 23): 0.4412, (24, 28): 0.1316, (29, 30): 0.0010}
tracos_uniao = list(_tracos_por_estado)
if hashes_iniciais:
    for arq in sorted(glob.glob(os.path.join(DIR_LEGADO, 'dataset_pequeno_*.npz'))):
        d = np.load(arq, allow_pickle=True)
        for mat in d['estados']:
            tracos_uniao.append(int((mat == 9).sum()))
_cont_bucket = Counter(_bucket_de(t) for t in tracos_uniao)
print()
print('Distribuicao por bucket (legado + rodada):')
print(f"  {'Bucket':<10} {'N':>8} {'%real':>7} {'%alvo':>7} {'desvio_pp':>10}")
for b in BUCKETS:
    n = _cont_bucket.get(b, 0)
    pct = n / len(tracos_uniao) * 100 if tracos_uniao else 0
    alvo = ALVO[b] * 100
    desv = pct - alvo
    print(f'  {str(b):<10} {n:>8,} {pct:>6.2f}% {alvo:>6.2f}% {desv:>+9.2f}')

# --- sim_l1 (modo 1) DEVE estar zerado ---
_n_sim_l1 = sum(1 for m in _modo_por_estado if m == 1)
print()
print(f'sim_l1 (modo 1) total: {_n_sim_l1} (esperado 0 — desligado por D1.a)')
assert _n_sim_l1 == 0, f'sim_l1 deve estar 0 (D1.a), obtido {_n_sim_l1}'
print('AUDITORIA OK.')
