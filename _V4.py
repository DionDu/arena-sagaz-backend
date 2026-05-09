import numpy as np, random, time, os, json, glob

try:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName('SpatialRoutingSimV4').getOrCreate()
    print('PySpark session initialized. DataFrame API available.')
    try:
        sc = spark.sparkContext
    except Exception:
        print('SparkContext restricted (Unity Catalog Shared Cluster). Using DataFrame/Pandas UDF mode.')
        sc = None
except Exception:
    spark = None; sc = None
    print('Local mode')

# ====== CELL ======

# Core Engine — Optimized graph topology solver
# V4: Enhanced transposition table, better move ordering, faster bitboard ops

def build_topology_tables(rows, cols):
    h = 2*rows+1; w = 2*cols+1
    edge_to_bit = {}; bit_to_rc = {}; bit_to_label = {}; bit_idx = 0
    for r in range(h):
        for c in range(w):
            if r%2 == 0 and c%2 == 1:
                edge_to_bit[(r,c)] = bit_idx; bit_to_rc[bit_idx] = (r,c)
                bit_to_label[bit_idx] = f'H_{r}_{c}'; bit_idx += 1
            elif r%2 == 1 and c%2 == 0:
                edge_to_bit[(r,c)] = bit_idx; bit_to_rc[bit_idx] = (r,c)
                bit_to_label[bit_idx] = f'V_{r}_{c}'; bit_idx += 1
    n = bit_idx; all_mask = (1 << n) - 1
    box_masks = []
    for r in range(1, h, 2):
        for c in range(1, w, 2):
            t=edge_to_bit[(r-1,c)]; b=edge_to_bit[(r+1,c)]
            l=edge_to_bit[(r,c-1)]; rr=edge_to_bit[(r,c+1)]
            box_masks.append((1<<t)|(1<<b)|(1<<l)|(1<<rr))
    edge_boxes = [tuple(bm for bm in box_masks if bm & (1<<i)) for i in range(n)]
    labels = [bit_to_label[i] for i in range(n)]
    
    # V4: Pre-compute closure lookup table for faster closure detection
    closure_lut = np.zeros((n, 1 << n), dtype=np.int8)
    for i in range(n):
        for edges in range(1 << min(n, 20)):  # limit for memory
            new = edges | (1<<i)
            cl = sum(1 for bm in edge_boxes[i] if (new & bm) == bm)
            if edges < closure_lut.shape[1]:
                closure_lut[i, edges] = cl
    
    return n, all_mask, edge_boxes, labels, bit_to_rc, box_masks, closure_lut


def _closures_fast(edges, i, edge_boxes, closure_lut=None):
    """V4: Use LUT when available, fallback to direct computation"""
    if closure_lut is not None and edges < closure_lut.shape[1]:
        return int(closure_lut[i, edges])
    new = edges | (1<<i)
    return sum(1 for bm in edge_boxes[i] if (new & bm) == bm)


def _ordered_moves_v4(edges, n_edges, edge_boxes, closure_lut=None, killer_moves=None):
    """V4: Enhanced move ordering with killer heuristic"""
    killers = []; good = []; normal = []
    for i in range(n_edges):
        if edges & (1<<i): continue
        cl = _closures_fast(edges, i, edge_boxes, closure_lut)
        if killer_moves and i in killer_moves:
            killers.append((i, cl) if cl > 0 else i)
        elif cl > 0:
            good.append((i, cl))
        else:
            normal.append(i)
    # Sort by closure count descending
    good.sort(key=lambda x: x[1], reverse=True)
    return killers, good, normal


def deep_evaluate_v4(edges, minimax_depth, alpha, beta, maximizing, n_edges, all_mask, 
                     edge_boxes, tt, closure_lut=None, killer_moves=None):
    """V4: Enhanced with killer moves and better pruning"""
    if minimax_depth == 0 or edges == all_mask: return 0
    
    # Enhanced TT lookup with minimax_depth consideration
    key = (edges, minimax_depth, maximizing)
    cached = tt.get(key)
    if cached:
        f, v, cached_depth = cached
        if cached_depth >= minimax_depth :  # Only use if cached minimax_depth is sufficient
            if f == 0: return v
            if f == 1 and v >= beta: return v
            if f == 2 and v <= alpha: return v
            if f == 1: alpha = max(alpha, v)
            elif f == 2: beta = min(beta, v)
    
    killers, good, normal = _ordered_moves_v4(edges, n_edges, edge_boxes, 
                                               closure_lut, killer_moves)
    orig_alpha = alpha
    best_move = None
    
    if maximizing:
        best = -10000
        # Try killer moves first
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes, closure_lut)
            child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha-cl, beta-cl,
                                    True, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
            score = cl+child
            if score > best:
                best = score; best_move = move
            alpha = max(alpha, best)
            if beta <= alpha: break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha-cl, beta-cl,
                                        True, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
                score = cl+child
                if score > best:
                    best = score; best_move = move
                alpha = max(alpha, best)
                if beta <= alpha: break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha, beta,
                                        False, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
                if child > best:
                    best = child; best_move = move
                alpha = max(alpha, best)
                if beta <= alpha: break
    else:
        best = 10000
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes, closure_lut)
            child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha+cl, beta+cl,
                                    False, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
            score = -cl+child
            if score < best:
                best = score; best_move = move
            beta = min(beta, best)
            if beta <= alpha: break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha+cl, beta+cl,
                                        False, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
                score = -cl+child
                if score < best:
                    best = score; best_move = move
                beta = min(beta, best)
                if beta <= alpha: break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha, beta,
                                        True, n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
                if child < best:
                    best = child; best_move = move
                beta = min(beta, best)
                if beta <= alpha: break
    
    flag = 2 if best <= orig_alpha else (1 if best >= beta else 0)
    tt[key] = (flag, best, minimax_depth)
    
    # Update killer moves
    if killer_moves is not None and best_move is not None:
        if best_move not in killer_moves:
            killer_moves.add(best_move)
            if len(killer_moves) > 4:  # Keep only top 4 killers
                killer_moves.pop()
    
    return best


def compute_all_scores_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes, closure_lut=None):
    """V4: Use optimized evaluation"""
    tt = {}; killer_moves = set(); scores = {}
    for i in range(n_edges):
        if edges & (1<<i): continue
        cl = _closures_fast(edges, i, edge_boxes, closure_lut)
        new = edges | (1<<i)
        child = deep_evaluate_v4(new, minimax_depth-1, -10001, 10001,
                                cl > 0, n_edges, all_mask, edge_boxes, tt, 
                                closure_lut, killer_moves)
        scores[i] = cl + child if cl > 0 else child
    return scores


def get_optimal_configuration_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes, labels, closure_lut=None):
    bit_scores = compute_all_scores_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes, closure_lut)
    label_scores = {labels[b]: v for b, v in bit_scores.items()}
    best_val = max(bit_scores.values())
    best_label = labels[random.choice([b for b, v in bit_scores.items() if v == best_val])]
    return best_label, label_scores


def edges_to_matrix(edges, rows, cols, n_edges, bit_to_rc, box_masks):
    h, w = 2*rows+1, 2*cols+1
    mat = np.zeros((h, w), dtype=np.int8)
    for r in range(0, h, 2):
        for c in range(0, w, 2): mat[r, c] = 8
    for i in range(n_edges):
        if edges & (1<<i): r, c = bit_to_rc[i]; mat[r, c] = 9
    for bm in box_masks:
        if (edges & bm) == bm:
            bits = [bit_to_rc[b] for b in range(n_edges) if bm & (1<<b)]
            ar = sum(rc[0] for rc in bits)//4
            ac = sum(rc[1] for rc in bits)//4
            if ar%2 == 1 and ac%2 == 1: mat[ar, ac] = 1
    return mat

print('Core engine V4 loaded with optimizations.')

# ====== CELL ======

# V4: Agent-Based Topology Sampling (preserved from V3)
# sampling_strategy: 0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3

STRAT_MODES  = [0,    1,    2,    3  ]
STRAT_WEIGHTS= [0.15, 0.25, 0.55, 0.05]

MODE_NAMES  = {0: 'uniform', 1: 'sim_l1',
               2: 'sim_l2', 3: 'sim_l3'}


def _autoplay_edges_v4(gen_depth, n_edges, all_mask, edge_boxes, closure_lut=None):
    """V4: Uses optimized evaluation"""
    target = random.randint(int(n_edges * 0.15), int(n_edges * 0.85))
    edges = 0; maximizing = True
    while bin(edges).count('1') < target and edges != all_mask:
        tt = {}; killer_moves = set()
        best_score = -99999 if maximizing else 99999
        best_moves = []
        for i in range(n_edges):
            if edges & (1<<i): continue
            cl = _closures_fast(edges, i, edge_boxes, closure_lut)
            new = edges | (1<<i)
            child = deep_evaluate_v4(
                new, gen_depth-1, -10001, 10001,
                (not maximizing) if cl == 0 else maximizing,
                n_edges, all_mask, edge_boxes, tt, closure_lut, killer_moves)
            score = cl + child if maximizing else -cl + child
            if score > best_score if maximizing else score < best_score:
                best_score = score; best_moves = [i]
            elif score == best_score:
                best_moves.append(i)
        if not best_moves: break
        best_move = random.choice(best_moves)
        cl = _closures_fast(edges, best_move, edge_boxes, closure_lut)
        edges |= (1 << best_move)
        if cl == 0: maximizing = not maximizing
    return edges


def generate_topology_v4(n_edges, all_mask, edge_boxes, closure_lut=None):
    """V4: Returns (state_bitboard, sampling_strategy_int)"""
    mode = random.choices(STRAT_MODES, weights=STRAT_WEIGHTS)[0]
    if mode == 0:
        qty = random.randint(int(n_edges * 0.15), int(n_edges * 0.85))
        idx = list(range(n_edges)); random.shuffle(idx)
        edges = 0
        for i in idx[:qty]: edges |= (1 << i)
    else:
        edges = _autoplay_edges_v4(mode, n_edges, all_mask, edge_boxes, closure_lut)
    return edges, mode


print('V4 sampler loaded. Strategy weights:', dict(zip(MODE_NAMES.values(), STRAT_WEIGHTS)))

# ====== CELL ======

# Execution Parameters — V4 optimized for higher minimax_depth

NUM_SAMPLES    = 300000
TAMANHO_LOTE   = 5000
DEPTH          = 9
ROWS, COLS     = 4, 3
SCORE_IND      = -1e9
DIRETORIO_SAIDA = f'/Workspace/Users/c092820@corp.caixa.gov.br/CNN/profundidade_{DEPTH}'
os.makedirs(DIRETORIO_SAIDA, exist_ok=True)

_n, _mask, _eboxes, _labels, _brc, _bmasks, _clut = build_topology_tables(ROWS, COLS)
_idx_label = {l: i for i, l in enumerate(_labels)}
_n_labels  = len(_labels)
print(f'Grid: {ROWS}x{COLS}, {_n} links | Output: {DIRETORIO_SAIDA}')
print(f'DEPTH: {DEPTH} (V4 optimized for higher minimax_depth)')
print(f'Sampling distribution: {dict(zip(MODE_NAMES.values(), STRAT_WEIGHTS))}')

for m, w in zip(STRAT_MODES, STRAT_WEIGHTS):
    print(f'  {MODE_NAMES[m]}: ~{int(NUM_SAMPLES*w):,} records')

# ====== CELL ======

# V4: Optimized distributed worker with reduced serialization overhead

def make_worker_v4(minimax_depth, rows, cols):
    def process_batch_v4(iterator):
        import pandas as pd, numpy as np, random, json
        n, mask, eboxes, labels, brc, bms, clut = build_topology_tables(rows, cols)
        for pdf in iterator:
            results = []
            for _ in range(len(pdf)):
                for _attempt in range(20):
                    try:
                        edges, mode = generate_topology_v4(n, mask, eboxes, clut)
                        if edges == mask: continue
                        best, scores = get_optimal_configuration_v4(
                            edges, minimax_depth, n, mask, eboxes, labels, clut)
                        mat = edges_to_matrix(edges, rows, cols, n, brc, bms)
                        results.append({
                            'matriz': [int(x) for x in mat.flatten()],
                            'best_link': best,
                            'scores_dict': json.dumps(scores),
                            'generation_mode': int(mode),
                        })
                        break
                    except Exception:
                        pass
            yield pd.DataFrame(results)
    return process_batch_v4


def vetor_scores(sd, il, nl):
    v = np.full(nl, SCORE_IND, dtype=np.float32)
    for lbl, val in sd.items(): v[il[lbl]] = float(val)
    return v


def log_prog(gerados, total, inicio):
    dec = time.time() - inicio
    est = (dec / gerados * (total - gerados)) if gerados > 0 else 0
    print(json.dumps({'gerados': gerados, 'total': total,
                      'pct': round(gerados/total*100, 2),
                      'decorrido_s': round(dec, 2),
                      'restante_s': round(est, 2)}))

print(f'Worker factory V4 ready. Will instantiate with DEPTH={DEPTH}, ROWS={ROWS}, COLS={COLS}.')

# ====== CELL ======

spark.conf.set('spark.databricks.execution.timeout', 3600)

# ====== CELL ======

# V4: Execution loop with optimized batch sizes and checkpointing
import pandas as pd

SCHEMA = 'matriz array<int>, best_link string, scores_dict string, generation_mode int'
RECORDS_PER_CORE = 3   # registros por core por iteração (~75s/iter a DEPTH=13)
LOG_INTERVAL_S   = 60  # log de progresso a cada N segundos

# --- Detecção dinâmica de cores via Databricks REST API ---
# sparkContext não funciona em Spark Connect (USER_ISOLATION).
# Usamos a SDK do Databricks que consulta o estado real do cluster.
_core_cache = {'cores': None, 'ts': 0}
_CACHE_TTL  = 60  # re-check cluster a cada 60s

def get_active_cores():
    """Detect active executor cores via Databricks SDK (Spark Connect compatible, cached 60s)."""
    import time as _t
    now = _t.time()
    if _core_cache['cores'] is not None and now - _core_cache['ts'] < _CACHE_TTL:
        return _core_cache['cores']
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        cid = spark.conf.get('spark.databricks.clusterUsageTags.clusterId')
        info = w.clusters.get(cid)
        # info.executors = lista de SparkNode (NÃO inclui o driver)
        num_workers = len(info.executors) if info.executors else 0
        if num_workers < 1:
            num_workers = 1
        try:
            cores_per = int(spark.conf.get('spark.executor.cores'))
        except Exception:
            cores_per = 8  # Standard_F8s = 8 vCPUs
        total = max(num_workers * cores_per, 8)
    except Exception:
        total = _core_cache.get('cores') or 8  # reutiliza último valor ou fallback
    _core_cache['cores'] = total
    _core_cache['ts'] = now
    return total

arqs = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
if arqs:
    ul = int(arqs[-1].split('_')[-1].split('.')[0])
    total_gerado = ul * TAMANHO_LOTE
    print(f'Checkpoint: resuming from batch {ul} ({total_gerado} records)')
else:
    total_gerado = 0; ul = 0

estados = []; rotulos = []; scores_l = []; gen_modes = []
inicio = time.time()
last_log = inicio
prev_cores = None

print(f'Starting execution loop (Depth {DEPTH}, optimized V4)...')
while total_gerado < NUM_SAMPLES:
    if spark:
        cores = get_active_cores()
        chunk = min(cores * RECORDS_PER_CORE, NUM_SAMPLES - total_gerado)
        parts = min(cores * 2, chunk)  # 2x cores -> ~1.5 rec/partition
        df = spark.range(0, chunk, 1, parts)
        _worker = make_worker_v4(DEPTH, ROWS, COLS)
        # Só loga [cluster] quando a quantidade de cores muda
        if cores != prev_cores:
            print(f'  [cluster] cores={cores} ({cores//8}w), chunk={chunk}, '
                  f'parts={parts}, ~{chunk/max(parts,1):.1f} rec/task')
            prev_cores = cores
        rows_out = df.mapInPandas(_worker, schema=SCHEMA).collect()
        for row in rows_out:
            mat = np.array(row.matriz, dtype=np.int8).reshape(2*ROWS+1, 2*COLS+1)
            sd  = json.loads(row.scores_dict)
            estados.append(mat)
            rotulos.append(row.best_link)
            scores_l.append(vetor_scores(sd, _idx_label, _n_labels))
            gen_modes.append(row.generation_mode)
            total_gerado += 1
    else:
        chunk = min(100, NUM_SAMPLES - total_gerado)
        for _ in range(chunk):
            for _attempt in range(20):
                try:
                    edges, mode = generate_topology_v4(_n, _mask, _eboxes, _clut)
                    if edges == _mask: continue
                    best, sd = get_optimal_configuration_v4(
                        edges, DEPTH, _n, _mask, _eboxes, _labels, _clut)
                    mat = edges_to_matrix(edges, ROWS, COLS, _n, _brc, _bmasks)
                    estados.append(mat); rotulos.append(best)
                    scores_l.append(vetor_scores(sd, _idx_label, _n_labels))
                    gen_modes.append(mode); total_gerado += 1; break
                except Exception: pass

    # Log throttled: a cada LOG_INTERVAL_S segundos (não a cada iteração)
    now = time.time()
    if now - last_log >= LOG_INTERVAL_S or total_gerado >= NUM_SAMPLES:
        log_prog(total_gerado, NUM_SAMPLES, inicio)
        last_log = now

    if len(estados) >= TAMANHO_LOTE or total_gerado >= NUM_SAMPLES:
        if estados:
            ul += 1
            path = os.path.join(DIRETORIO_SAIDA, f'dataset_pequeno_{ul:04d}.npz')
            np.savez_compressed(path,
                estados         = np.array(estados, dtype=np.int8),
                rotulos         = np.array(rotulos, dtype=str),
                scores          = np.array(scores_l, dtype=np.float32),
                generation_mode = np.array(gen_modes, dtype=np.int8),
                labels_canonicos= np.array(_labels, dtype=str),
                minimax_depth = np.array([DEPTH], dtype=np.int32))
            print(f'Batch {ul:04d} -> {path}')
            estados = []; rotulos = []; scores_l = []; gen_modes = []

print(f'Completed: {total_gerado} records written to {DIRETORIO_SAIDA}')

# ====== CELL ======

# Diagnostic Metrics — V4 (unchanged from V3)
import numpy as np, glob, os
try: import matplotlib.pyplot as plt; HAS_PLT = True
except ImportError: HAS_PLT = False

arqs = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
print(f'Files: {len(arqs)} | Estimated records: {len(arqs)*TAMANHO_LOTE:,}')

all_modes = []; all_fill = []; all_best_score = []; all_score_range = []
for f in arqs:
    d = np.load(f, allow_pickle=True)
    gm  = d['generation_mode']
    est = d['estados']
    sc  = d['scores']
    for i in range(len(gm)):
        mat = est[i]
        fill = 0
        h, w = mat.shape
        for r in range(h):
            for c in range(w):
                if (r%2==0 and c%2==1) or (r%2==1 and c%2==0):
                    if mat[r,c] != 0: fill += 1
        valid = sc[i][sc[i] > -1e8]
        bs = float(valid.max()) if len(valid) else 0.0
        sr = float(valid.max() - valid.min()) if len(valid) > 1 else 0.0
        all_modes.append(int(gm[i]))
        all_fill.append(fill)
        all_best_score.append(bs)
        all_score_range.append(sr)

all_modes = np.array(all_modes)
all_fill  = np.array(all_fill, dtype=float)
all_best_score  = np.array(all_best_score)
all_score_range = np.array(all_score_range)
total = len(all_modes)

print(f'Total records loaded: {total:,}')
print(f'Generated with DEPTH={DEPTH}')
print()
header = f'  {"Mode":<18}  {"N":>7}  {"% real":>7}  {"Fill_avg":>9}  {"BestScore":>10}  {"ScoreRange":>11}'
print(header); print('-' * len(header))
for m in sorted(set(all_modes.tolist())):
    mk = (all_modes == m)
    n  = int(mk.sum()); pct = n/total*100
    print(f'  {MODE_NAMES.get(m,str(m)):<18}  {n:>7}  {pct:>6.1f}%  '
          f'{all_fill[mk].mean():>9.1f}  {all_best_score[mk].mean():>10.2f}  '
          f'{all_score_range[mk].mean():>11.2f}')

if HAS_PLT:
    modes_present = sorted(set(all_modes.tolist()))
    colors = ['gray', 'steelblue', 'navy', 'purple']
    fig, axes = plt.subplots(len(modes_present), 2, figsize=(12, 4*len(modes_present)))
    if len(modes_present) == 1: axes = [axes]
    for idx, m in enumerate(modes_present):
        mk = (all_modes == m); c = colors[m % len(colors)]
        axes[idx][0].hist(all_fill[mk], bins=20, color=c, alpha=0.8)
        axes[idx][0].set_title(f'{MODE_NAMES.get(m,str(m))} — Link Saturation (DEPTH={DEPTH})')
        axes[idx][0].set_xlabel('Active links'); axes[idx][0].set_ylabel('Freq')
        axes[idx][1].hist(all_best_score[mk], bins=20, color=c, alpha=0.8)
        axes[idx][1].set_title(f'{MODE_NAMES.get(m,str(m))} — Optimality Score (DEPTH={DEPTH})')
        axes[idx][1].set_xlabel('Score'); axes[idx][1].set_ylabel('Freq')
    plt.suptitle(f'V4 Sampling Strategy Diagnostics (DEPTH={DEPTH})', fontsize=14)
    plt.tight_layout(); plt.show()
else:
    print('matplotlib indisponivel: instale para ver graficos.')