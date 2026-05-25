"""Teste decisivo: para estados smj==sj com scores NAO-ZERO,
verifica se os scores sao consistentes com p=7 ou com p=11.

Se smj == p7 mas smj != p11 -> dados sao de p=7 (Phase 2 rodou a p=7)
Se smj == p11 (e smj == sj por coincidencia) -> dados sao corretos em p=11
Se smj != p7 e smj != p11 -> algo inesperado
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
import time
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

DIR = Path("dados/profundidade_minimax_11_v7_adaptativo")

def e_original(p):
    n = p.stem
    return not (n.endswith('_refH') or n.endswith('_refV') or n.endswith('_r180'))

def reconstruir(M):
    e = EstadoTabuleiro(4, 3)
    e.matriz = M.copy()
    return e

def score_bate(smj_vetor, ref_dict, labels):
    label_to_idx = {l: i for i, l in enumerate(labels)}
    for t, v in ref_dict.items():
        i = label_to_idx.get(t)
        if i is None: continue
        if abs(float(smj_vetor[i]) - float(v)) > 0.01:
            return False
    return True

# === Teste do estado específico que falhou ===
print("=== ESTADO ESPECÍFICO (dataset_pequeno_0066.npz idx=3569) ===\n")
d = np.load(str(DIR / "dataset_pequeno_0066.npz"), allow_pickle=False)
idx = 3569
M = d["estados"][idx]
smj = d["score_melhor_jogada"][idx]
dj = int(d["depth_jogada"][idx])
dmj = int(d["depth_melhor_jogada"][idx])
labels = [str(s) for s in d["labels_canonicos"]]
estado = reconstruir(M)
tracos = estado.tracos_disponiveis()
print(f"qtd_tracos={int(d['qtd_tracos'][idx])} dj={dj} dmj={dmj} movs={len(tracos)}")

for dep in [6, 7, 8, 9, 10, 11]:
    t0 = time.time()
    ref = _scores_de_todas_jogadas(estado, dep)
    bate = score_bate(smj, ref, labels)
    elapsed = time.time() - t0
    # Listar diferenças
    label_to_idx = {l: i for i, l in enumerate(labels)}
    difs = [(t, float(smj[label_to_idx[t]]), float(ref[t])) for t in tracos if abs(float(smj[label_to_idx[t]]) - float(ref[t])) > 0.01]
    print(f"  p={dep:2d}: smj_bate_p={dep}? {'SIM' if bate else 'NAO':3s}  diffs={len(difs):2d}/{len(tracos)}  ({elapsed:.1f}s)")

# === Amostrar estados smj==sj com scores NAO-ZERO em qt=9-12 ===
print("\n=== AMOSTRA: estados smj==sj, qt=9-12, scores NAO-ZERO ===")
print("(Testando p=7 e p=11 para verificar consistência)\n")

rng = np.random.default_rng(77)
candidatos = []
npzs = sorted(p for p in DIR.glob("*.npz") if e_original(p))
for p in npzs[:10]:  # primeiros 10 arquivos
    d = np.load(p, allow_pickle=False)
    smj_all = d["score_melhor_jogada"]
    sj_all  = d["score_jogada"]
    qt_all  = d["qtd_tracos"]
    dmj_all = d["depth_melhor_jogada"]
    N = smj_all.shape[0]
    for i in range(N):
        qt = int(qt_all[i])
        dmj = int(dmj_all[i])
        if not (9 <= qt <= 12 and dmj == 11):
            continue
        if not np.allclose(smj_all[i], sj_all[i]):
            continue
        # Verificar se tem scores nao-zero (pelo menos 1 movimento com score != 0)
        smj_i = smj_all[i]
        labels_i = [str(s) for s in d["labels_canonicos"]]
        avail = [float(smj_i[j]) for j, l in enumerate(labels_i) if smj_i[j] > -1e8]
        if len(avail) > 0 and any(abs(v) > 0.01 for v in avail):
            candidatos.append((str(p), i, qt, int(d["depth_jogada"][i])))

print(f"Candidatos com scores nao-zero (smj==sj, qt=9-12): {len(candidatos)}")
rng.shuffle(candidatos)
amostra = candidatos[:8]

print(f"Testando {len(amostra)} estados...\n")
p7_ok = 0; p11_ok = 0

for caminho, idx, qt, dj_val in amostra:
    d = np.load(caminho, allow_pickle=False)
    M   = d["estados"][idx]
    smj = d["score_melhor_jogada"][idx]
    labels = [str(s) for s in d["labels_canonicos"]]
    estado = reconstruir(M)
    tracos = estado.tracos_disponiveis()
    if not tracos: continue

    ref7  = _scores_de_todas_jogadas(estado, 7)
    bate7 = score_bate(smj, ref7, labels)

    ref11 = _scores_de_todas_jogadas(estado, 11)
    bate11 = score_bate(smj, ref11, labels)

    if bate7: p7_ok += 1
    if bate11: p11_ok += 1

    label_to_idx = {l: i for i, l in enumerate(labels)}
    avail_nonzero = [(t, float(smj[label_to_idx[t]]), float(ref7[t]), float(ref11[t]))
                     for t in tracos if abs(float(smj[label_to_idx[t]])) > 0.01]

    print(f"  {Path(caminho).name} idx={idx} qt={qt} dj={dj_val}")
    print(f"    smj==p7? {'SIM' if bate7 else 'NAO'}  smj==p11? {'SIM' if bate11 else 'NAO'}")
    if avail_nonzero:
        for t, s_npz, s7, s11 in avail_nonzero[:4]:
            print(f"    {t}: npz={s_npz:.0f} p7={s7:.0f} p11={s11:.0f}")

print(f"\nSUMARIO: smj==p7 em {p7_ok}/{len(amostra)}, smj==p11 em {p11_ok}/{len(amostra)}")
print("Se smj==p7 >> smj==p11: dados sao de p=7, NAO de p=11")
print("Se smj==p11: dados sao de p=11 (corretos)")
