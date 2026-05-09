import numpy as np, random, time, os, json, glob

try:
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName('SpatialRoutingSimV5').getOrCreate()
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
# V5_Databricks (corrigido): SEM `closure_lut`. A versao V4 alocava
# np.zeros((n, 1<<n)) = 31 * 2**31 = 66 GB de memoria virtual por worker para
# preencher so ~0,05% da tabela. Era prejuizo liquido (overhead de page-fault,
# alocacao por particao Spark, sem ganho real de velocidade). _closures_fast
# agora e calculo direto (3-4 testes de mascara), trivial.

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
    return n, all_mask, edge_boxes, labels, bit_to_rc, box_masks


def _closures_fast(edges, i, edge_boxes):
    new = edges | (1<<i)
    return sum(1 for bm in edge_boxes[i] if (new & bm) == bm)


def _ordered_moves_v4(edges, n_edges, edge_boxes, killer_moves=None):
    killers = []; good = []; normal = []
    for i in range(n_edges):
        if edges & (1<<i): continue
        cl = _closures_fast(edges, i, edge_boxes)
        if killer_moves and i in killer_moves:
            killers.append((i, cl) if cl > 0 else i)
        elif cl > 0:
            good.append((i, cl))
        else:
            normal.append(i)
    good.sort(key=lambda x: x[1], reverse=True)
    return killers, good, normal


def deep_evaluate_v4(edges, minimax_depth, alpha, beta, maximizing, n_edges, all_mask,
                     edge_boxes, tt, killer_moves=None):
    if minimax_depth == 0 or edges == all_mask: return 0

    key = (edges, minimax_depth, maximizing)
    cached = tt.get(key)
    if cached:
        f, v, cached_depth = cached
        if cached_depth >= minimax_depth :
            if f == 0: return v
            if f == 1 and v >= beta: return v
            if f == 2 and v <= alpha: return v
            if f == 1: alpha = max(alpha, v)
            elif f == 2: beta = min(beta, v)

    killers, good, normal = _ordered_moves_v4(edges, n_edges, edge_boxes, killer_moves)
    orig_alpha = alpha
    best_move = None

    if maximizing:
        best = -10000
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes)
            child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha-cl, beta-cl,
                                    True, n_edges, all_mask, edge_boxes, tt, killer_moves)
            score = cl+child
            if score > best:
                best = score; best_move = move
            alpha = max(alpha, best)
            if beta <= alpha: break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha-cl, beta-cl,
                                        True, n_edges, all_mask, edge_boxes, tt, killer_moves)
                score = cl+child
                if score > best:
                    best = score; best_move = move
                alpha = max(alpha, best)
                if beta <= alpha: break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha, beta,
                                        False, n_edges, all_mask, edge_boxes, tt, killer_moves)
                if child > best:
                    best = child; best_move = move
                alpha = max(alpha, best)
                if beta <= alpha: break
    else:
        best = 10000
        for move_info in killers:
            move = move_info[0] if isinstance(move_info, tuple) else move_info
            cl = move_info[1] if isinstance(move_info, tuple) else _closures_fast(edges, move, edge_boxes)
            child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha+cl, beta+cl,
                                    False, n_edges, all_mask, edge_boxes, tt, killer_moves)
            score = -cl+child
            if score < best:
                best = score; best_move = move
            beta = min(beta, best)
            if beta <= alpha: break
        if beta > alpha:
            for move, cl in good:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha+cl, beta+cl,
                                        False, n_edges, all_mask, edge_boxes, tt, killer_moves)
                score = -cl+child
                if score < best:
                    best = score; best_move = move
                beta = min(beta, best)
                if beta <= alpha: break
        if beta > alpha:
            for move in normal:
                child = deep_evaluate_v4(edges|(1<<move), minimax_depth-1, alpha, beta,
                                        True, n_edges, all_mask, edge_boxes, tt, killer_moves)
                if child < best:
                    best = child; best_move = move
                beta = min(beta, best)
                if beta <= alpha: break

    flag = 2 if best <= orig_alpha else (1 if best >= beta else 0)
    tt[key] = (flag, best, minimax_depth)

    if killer_moves is not None and best_move is not None and best_move not in killer_moves:
        killer_moves.add(best_move)
        if len(killer_moves) > 4:
            killer_moves.pop()

    return best


def compute_all_scores_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes):
    tt = {}; killer_moves = set(); scores = {}
    for i in range(n_edges):
        if edges & (1<<i): continue
        cl = _closures_fast(edges, i, edge_boxes)
        new = edges | (1<<i)
        child = deep_evaluate_v4(new, minimax_depth-1, -10001, 10001,
                                cl > 0, n_edges, all_mask, edge_boxes, tt, killer_moves)
        scores[i] = cl + child if cl > 0 else child
    return scores


def get_optimal_configuration_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes, labels):
    bit_scores = compute_all_scores_v4(edges, minimax_depth, n_edges, all_mask, edge_boxes)
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

print('Core engine V5 (sem closure_lut) carregado.')

# ====== CELL ======

# V5: Agent-Based Topology Sampling
# sampling_strategy: 0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3
# V5_Databricks (corrigido): adiciona generate_topology_forced(gen_mode, lo, hi)
# para o laco por cota da Fase A.1 (PRD §4.1.3 + tasks.md T-A1-004).

STRAT_MODES  = [0,    1,    2,    3  ]
STRAT_WEIGHTS= [0.15, 0.25, 0.55, 0.05]   # legado V4 — ignorado pelo laco por cota

MODE_NAMES  = {0: 'uniform', 1: 'sim_l1',
               2: 'sim_l2', 3: 'sim_l3'}


def _autoplay_edges_v4_bounded(gen_depth, n_edges, all_mask, edge_boxes, target_lo, target_hi):
    """Autoplay com target em numero ABSOLUTO de tracos no intervalo [lo, hi].

    Usado pelo laco por cota: cada celula (gen_mode, bucket) sorteia um target
    dentro do bucket, evitando off-by-one de converter para fracao.
    """
    target = random.randint(target_lo, target_hi)
    edges = 0; maximizing = True
    while bin(edges).count('1') < target and edges != all_mask:
        tt = {}; killer_moves = set()
        best_score = -99999 if maximizing else 99999
        best_moves = []
        for i in range(n_edges):
            if edges & (1<<i): continue
            cl = _closures_fast(edges, i, edge_boxes)
            new = edges | (1<<i)
            child = deep_evaluate_v4(
                new, gen_depth-1, -10001, 10001,
                (not maximizing) if cl == 0 else maximizing,
                n_edges, all_mask, edge_boxes, tt, killer_moves)
            score = cl + child if maximizing else -cl + child
            if score > best_score if maximizing else score < best_score:
                best_score = score; best_moves = [i]
            elif score == best_score:
                best_moves.append(i)
        if not best_moves: break
        best_move = random.choice(best_moves)
        cl = _closures_fast(edges, best_move, edge_boxes)
        edges |= (1 << best_move)
        if cl == 0: maximizing = not maximizing
    return edges


def generate_topology_forced(n_edges, all_mask, edge_boxes, gen_mode, target_lo, target_hi):
    """Gera topologia com gen_mode FORCADO e #tracos em [lo, hi].

    Substitui o legado generate_topology_v4 no laco por cota: a celula
    (gen_mode, bucket) decide ambos os parametros antes de chamar.
    """
    if gen_mode == 0:
        qty = random.randint(target_lo, target_hi)
        idx = list(range(n_edges)); random.shuffle(idx)
        edges = 0
        for i in idx[:qty]: edges |= (1 << i)
        return edges
    if gen_mode in (1, 2, 3):
        return _autoplay_edges_v4_bounded(gen_mode, n_edges, all_mask, edge_boxes, target_lo, target_hi)
    raise ValueError(f'gen_mode invalido: {gen_mode}')


print('V5 sampler (forced) loaded. STRAT_WEIGHTS legado:', dict(zip(MODE_NAMES.values(), STRAT_WEIGHTS)))

# ====== CELL ======

# Execution Parameters
# V5_Databricks: o numero de estados a gerar e DEFINIDO POR `COMPLEMENTO_POR_CELULA`
# (~347.020 estados) na celula seguinte. NUM_SAMPLES nao e mais usado pelo laco.

TAMANHO_LOTE   = 5000      # estados por NPZ (V4: testado e funcional)
DEPTH          = 9
ROWS, COLS     = 4, 3
SCORE_IND      = -1e9
DIRETORIO_SAIDA = f'/Workspace/Users/diondu@gmail.com/CNN/profundidade_{DEPTH}'
os.makedirs(DIRETORIO_SAIDA, exist_ok=True)

_n, _mask, _eboxes, _labels, _brc, _bmasks = build_topology_tables(ROWS, COLS)
_idx_label = {l: i for i, l in enumerate(_labels)}
_n_labels  = len(_labels)

print(f'=== CONFIGURATION ===')
print(f'Grid: {ROWS}x{COLS}, {_n} edges | Output: {DIRETORIO_SAIDA}')
print(f'DEPTH: {DEPTH} | TAMANHO_LOTE: {TAMANHO_LOTE:,}')
print(f'Target: definido por COMPLEMENTO_POR_CELULA na celula seguinte (espera-se 347.020).')

# ====== CELL ======

# === V5 [T-A1-002 + T-A1-003]: parametros novos da Fase A.1 ===
# Documentos: PRD §4.1.3 + research.md (clarification 2026-05-07).
# Estes parametros SUBSTITUEM o STRAT_WEIGHTS legado da celula 3 do V4.

# --- D1: faixa de tracos ativa (em fracao de n_edges) ---
FAIXA_TRACOS = (0.15, 0.97)   # de 5 a 30 tracos para n_edges=31

# --- D1.a: mix de geracao sem sim_l1 (peso 0) ---
# Ordem: [uniform=0, sim_l1=1, sim_l2=2, sim_l3=3]
STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]
assert abs(sum(STRAT_WEIGHTS) - 1.0) < 1e-9, 'STRAT_WEIGHTS deve somar 1.0'
assert STRAT_WEIGHTS[1] == 0.0, 'sim_l1 (modo 1) DEVE ter peso 0'

# --- D1: COMPLEMENTO_POR_CELULA (PRD §4.1.3) ---
# Cota por (gen_mode, faixa_de_tracos): quantos estados NOVOS gerar em cada celula.
# Soma esperada das cotas = 500.000 - 314.323 (únicos legados) = 185.677.
COMPLEMENTO_POR_CELULA = {
    0: {(5, 11):      0, (12, 17):      0, (18, 23):      0, (24, 28):  1_236, (29, 30):  2_500},
    2: {(5, 11):      0, (12, 17):      0, (18, 23): 10_776, (24, 28): 52_321, (29, 30): 20_000},
    3: {(5, 11): 22_484, (12, 17): 50_557, (18, 23): 72_820, (24, 28): 86_826, (29, 30): 27_500},
}
_total_quotas = sum(v for celulas in COMPLEMENTO_POR_CELULA.values() for v in celulas.values())
print(f'Quotas totais: {_total_quotas:,} (esperado 347_020 conforme PRD §4.1.3)')
assert _total_quotas == 347_020, f'Soma das cotas != 347_020: obtido {_total_quotas:,}'
print('STRAT_WEIGHTS:', STRAT_WEIGHTS)
print('FAIXA_TRACOS :', FAIXA_TRACOS)

# ====== CELL ======

# V5: Distributed worker — recebe (gen_mode, lo, hi) por linha e gera UM estado
# com gen_mode forcado e #tracos no bucket [lo, hi]. Substitui o worker V4 que
# escolhia gen_mode internamente via STRAT_WEIGHTS.

def make_worker_v4(minimax_depth, rows, cols):
    def process_batch_v4(iterator):
        import pandas as pd, numpy as np, random, json
        n, mask, eboxes, labels, brc, bms = build_topology_tables(rows, cols)
        for pdf in iterator:
            results = []
            for _, input_row in pdf.iterrows():
                gen_mode = int(input_row['gen_mode'])
                lo = int(input_row['lo'])
                hi = int(input_row['hi'])
                for _attempt in range(20):
                    try:
                        edges = generate_topology_forced(n, mask, eboxes, gen_mode, lo, hi)
                        if edges == mask: continue
                        n_tracos = bin(edges).count('1')
                        if not (lo <= n_tracos <= hi): continue
                        best, scores = get_optimal_configuration_v4(
                            edges, minimax_depth, n, mask, eboxes, labels)
                        mat = edges_to_matrix(edges, rows, cols, n, brc, bms)
                        results.append({
                            'matriz': [int(x) for x in mat.flatten()],
                            'best_link': best,
                            'scores_dict': json.dumps(scores),
                            'generation_mode': gen_mode,
                            'n_tracos': int(n_tracos),
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


def log_prog(gerados, total, inicio, dups=0, sobre=0, falhas=0):
    dec = time.time() - inicio
    rate = gerados / dec if dec > 0 else 0.0
    rest = (total - gerados) / rate if rate > 0 else 0.0
    print(json.dumps({'gerados': gerados, 'total': total,
                      'pct': round(gerados/total*100, 2),
                      'rate_sps': round(rate, 2),
                      'duplicados': dups, 'sobrefluxo': sobre, 'falhas': falhas,
                      'decorrido_s': round(dec, 2),
                      'restante_s': round(rest, 2),
                      'restante_h': round(rest/3600, 2)}))

print(f'Worker V5 (forced gen_mode + bucket) ready. DEPTH={DEPTH}, ROWS={ROWS}, COLS={COLS}.')

# ====== CELL ======

# Spark Configuration - Optimized for long-running compute
spark.conf.set('spark.databricks.execution.timeout', 14400)  # 4 horas (era 1h)
print('Spark timeout: 4h (Arrow already optimized on Serverless)')

# ====== CELL ======

# === V5 [T-A1-004]: pre-popular set de hashes com 314.323 unicos do legado ===
# Le todos os NPZ legados (V4) em DIR_LEGADO e popula `hashes_iniciais` por
# mat.tobytes() ANTES do laco de geracao do V5. O laco por cota (celula 10)
# usa esse set como semente do dedup global.

DIR_LEGADO = '/Workspace/Users/diondu@gmail.com/CNN/profundidade_9_legado'
hashes_iniciais = set()
_n_lidos = 0
if os.path.isdir(DIR_LEGADO):
    for arq in sorted(glob.glob(os.path.join(DIR_LEGADO, 'dataset_pequeno_*.npz'))):
        d = np.load(arq, allow_pickle=True)
        for mat in d['estados']:
            hashes_iniciais.add(mat.tobytes())
            _n_lidos += 1
    print(f'Legado: {_n_lidos:,} estados lidos | unicos: {len(hashes_iniciais):,}')
    if len(hashes_iniciais) != 314_323:
        print(f'AVISO: esperados 314.323 unicos no legado; obtidos {len(hashes_iniciais):,}.')
else:
    print(f'AVISO: {DIR_LEGADO} nao existe. Ajuste DIR_LEGADO conforme seu workspace antes de rodar.')

# ====== CELL ======

# V5: Execution loop POR COTA (PRD §4.1.3 + tasks.md T-A1-004)
# Sorteia (gen_mode, bucket) ponderado por cota residual em COMPLEMENTO_POR_CELULA,
# dispara worker que gera com mode/bucket forcados, deduplica contra hashes_iniciais
# (legado) + estados ja gravados, decrementa cota, grava NPZ a cada TAMANHO_LOTE.
# Para quando todas as cotas zeram (~347.020 estados novos esperados).

import pandas as pd
import random as _random
from collections import defaultdict

SCHEMA = 'matriz array<int>, best_link string, scores_dict string, generation_mode int, n_tracos int'
CHUNK  = 1000   # tarefas dispatcheadas por iteracao do laco
PARTS  = 256    # particoes Spark por dispatch (V4 testado)

BUCKETS = [(5, 11), (12, 17), (18, 23), (24, 28), (29, 30)]
def _bucket_de(t):
    return next((b for b in BUCKETS if b[0] <= t <= b[1]), None)

# === Cotas iniciais a partir de COMPLEMENTO_POR_CELULA ===
quotas = {(m, b): q for m, cells in COMPLEMENTO_POR_CELULA.items()
                    for b, q in cells.items()}
quotas = {k: v for k, v in quotas.items() if v > 0}
total_a_gerar = sum(quotas.values())  # 347.020 do zero

# === Resume: legado + arquivos ja gravados nesta rodada ===
hashes_unicos = set(hashes_iniciais)
ja_gerados      = 0
sobrefluxo_resumo = 0

arqs_existentes = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
if arqs_existentes:
    ul = int(arqs_existentes[-1].split('_')[-1].split('.')[0])
    print(f'Resume: lendo {len(arqs_existentes)} arquivos existentes em {DIRETORIO_SAIDA}...')
    for arq in arqs_existentes:
        d = np.load(arq, allow_pickle=True)
        gm  = d['generation_mode']
        est = d['estados']
        for i in range(len(est)):
            mat = est[i]; h = mat.tobytes()
            if h in hashes_unicos:
                continue
            hashes_unicos.add(h)
            n_tracos = int((mat == 9).sum())
            b = _bucket_de(n_tracos)
            if b is None: continue
            cell = (int(gm[i]), b)
            if quotas.get(cell, 0) > 0:
                quotas[cell] -= 1
                ja_gerados += 1
                if quotas[cell] == 0:
                    del quotas[cell]
            else:
                # Gerado fora de cota (ex.: rodada anterior sem laco por cota).
                # Nao conta como progresso — vai exigir gerar mais p/ fechar.
                sobrefluxo_resumo += 1
    print(f'Resume: ja_gerados={ja_gerados:,} | sobrefluxo_existente={sobrefluxo_resumo:,} '
          f'| hashes_unicos={len(hashes_unicos):,}')
    print(f'Cotas restantes: {sum(quotas.values()):,} de {total_a_gerar:,}')
else:
    ul = 0
    print(f'Comecando do zero. Set inicial de hashes: {len(hashes_unicos):,} (apenas legado).')
    print(f'Cotas a preencher: {total_a_gerar:,}')

# === Loop principal por cota ===
estados, rotulos, scores_l, gen_modes = [], [], [], []
duplicados_total = 0
sobrefluxo_total = 0
falhas_total     = 0
total_gerado     = ja_gerados
inicio = time.time()
last_log = inicio
LOG_INTERVAL_S = 30

print(f'\nIniciando laco por cota (Depth {DEPTH}, CHUNK={CHUNK}, PARTS={PARTS})...')

while quotas:
    cells_l = list(quotas.keys())
    weights = [quotas[c] for c in cells_l]
    size    = min(CHUNK, sum(weights))
    sampled = _random.choices(cells_l, weights=weights, k=size)
    input_rows = [(m, int(b[0]), int(b[1])) for (m, b) in sampled]

    if spark:
        df = spark.createDataFrame(input_rows, schema='gen_mode int, lo int, hi int') \
                  .repartition(min(PARTS, size))
        _worker = make_worker_v4(DEPTH, ROWS, COLS)
        rows_out = df.mapInPandas(_worker, schema=SCHEMA).collect()
    else:
        # Local fallback (modo single-process; util pra debug fora do Spark).
        rows_out = []
        for (m, lo, hi) in input_rows:
            for _attempt in range(20):
                try:
                    edges = generate_topology_forced(_n, _mask, _eboxes, m, lo, hi)
                    if edges == _mask: continue
                    n_tracos = bin(edges).count('1')
                    if not (lo <= n_tracos <= hi): continue
                    best, sd = get_optimal_configuration_v4(
                        edges, DEPTH, _n, _mask, _eboxes, _labels)
                    mat = edges_to_matrix(edges, ROWS, COLS, _n, _brc, _bmasks)
                    class _Row: pass
                    r = _Row()
                    r.matriz = mat.flatten().tolist()
                    r.best_link = best
                    r.scores_dict = json.dumps(sd)
                    r.generation_mode = m
                    r.n_tracos = int(n_tracos)
                    rows_out.append(r); break
                except Exception: pass

    for row in rows_out:
        mat = np.array(row.matriz, dtype=np.int8).reshape(2*ROWS+1, 2*COLS+1)
        h = mat.tobytes()
        if h in hashes_unicos:
            duplicados_total += 1; continue
        b = _bucket_de(int(row.n_tracos))
        if b is None:
            falhas_total += 1; continue
        cell = (int(row.generation_mode), b)
        if quotas.get(cell, 0) <= 0:
            sobrefluxo_total += 1; continue

        quotas[cell] -= 1
        if quotas[cell] == 0:
            del quotas[cell]
        hashes_unicos.add(h)

        sd = json.loads(row.scores_dict)
        estados.append(mat); rotulos.append(row.best_link)
        scores_l.append(vetor_scores(sd, _idx_label, _n_labels))
        gen_modes.append(int(row.generation_mode))
        total_gerado += 1

        if len(estados) >= TAMANHO_LOTE:
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

    now = time.time()
    if now - last_log >= LOG_INTERVAL_S:
        log_prog(total_gerado, total_a_gerar, inicio,
                 duplicados_total, sobrefluxo_total, falhas_total)
        print(f'  cotas_restantes={sum(quotas.values()):,} | celulas_abertas={len(quotas)}')
        last_log = now

# Flush do residuo do ultimo lote.
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
    print(f'Batch {ul:04d} (final) -> {path}')

log_prog(total_gerado, total_a_gerar, inicio,
         duplicados_total, sobrefluxo_total, falhas_total)
print(f'\nCompleted: {total_gerado:,} unicos novos | dups={duplicados_total:,} '
      f'| sobrefluxo={sobrefluxo_total:,} | falhas={falhas_total}')

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

# ====== CELL ======

# === V5 [T-A1-005]: auditoria pos-execucao ===
# Verifica unicos totais por mat.tobytes(), distribuicao empirica por nro
# de tracos (em buckets) e mix de gen_mode por faixa.

from collections import Counter, defaultdict

_arqs = sorted(glob.glob(os.path.join(DIRETORIO_SAIDA, 'dataset_pequeno_*.npz')))
_set_unicos = set()
_traços_por_estado = []
_modo_por_estado = []
for arq in _arqs:
    d = np.load(arq, allow_pickle=True)
    gm = d['generation_mode']
    est = d['estados']
    for i in range(len(est)):
        mat = est[i]
        _set_unicos.add(mat.tobytes())
        # Conta tracos jogados (== 9) na matriz expandida 9x7.
        n_tracos = int((mat == 9).sum())
        _traços_por_estado.append(n_tracos)
        _modo_por_estado.append(int(gm[i]))

print(f'Total de estados gravados: {len(_traços_por_estado):,}')
print(f'Unicos por mat.tobytes(): {len(_set_unicos):,}')
assert len(_set_unicos) >= 500_000, f'Esperado >= 500.000 unicos, obtido {len(_set_unicos):,}'

# --- Distribuicao por bucket de tracos (PRD §4.1.3) ---
BUCKETS = [(5, 11), (12, 17), (18, 23), (24, 28), (29, 30)]
ALVO = {(5, 11): 0.10, (12, 17): 0.20, (18, 23): 0.28, (24, 28): 0.32, (29, 30): 0.10}
_bucket_de = lambda t: next((b for b in BUCKETS if b[0] <= t <= b[1]), None)
_cont_bucket = Counter(_bucket_de(t) for t in _traços_por_estado)
total = len(_traços_por_estado)
print()
print('Distribuicao por bucket de tracos:')
print(f"  {'Bucket':<10} {'N':>8} {'%real':>7} {'%alvo':>7} {'desvio_pp':>10}")
for b in BUCKETS:
    n = _cont_bucket.get(b, 0)
    pct = n / total * 100 if total else 0
    alvo = ALVO[b] * 100
    desvio = pct - alvo
    print(f'  {str(b):<10} {n:>8,} {pct:>6.2f}% {alvo:>6.2f}% {desvio:>+9.2f}')
    assert abs(desvio) <= 2.0, f'Bucket {b}: desvio {desvio:+.2f}pp > tolerancia 2pp'

# --- Mix de gen_mode por bucket ---
_modo_bucket = defaultdict(Counter)
for t, m in zip(_traços_por_estado, _modo_por_estado):
    b = _bucket_de(t)
    if b is not None:
        _modo_bucket[b][m] += 1
print()
print('Mix de gen_mode por bucket:')
for b in BUCKETS:
    cnt = _modo_bucket[b]
    tot_b = sum(cnt.values())
    if tot_b == 0: continue
    fmt = ', '.join(f'mode_{m}={cnt[m]/tot_b*100:.1f}%' for m in sorted(cnt))
    print(f'  {b}: {fmt}')

# --- sim_l1 (modo 1) DEVE estar zerado ---
_n_sim_l1 = sum(1 for m in _modo_por_estado if m == 1)
print()
print(f'sim_l1 (modo 1) total: {_n_sim_l1} (esperado 0 — desligado por D1.a)')
assert _n_sim_l1 == 0, f'sim_l1 deve estar 0 (D1.a), obtido {_n_sim_l1}'

print()
print('AUDITORIA OK — NPZ aprovado.')