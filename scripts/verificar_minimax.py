"""
FASE 2: Recalculo do Minimax para validacao dos NPZ do Databricks.

Para cada arquivo NPZ, seleciona amostras com diferentes quantidades de tracos
e recalcula os scores Minimax localmente com profundidade 7, comparando com
os valores gravados em 'score_melhor_jogada'.
"""
import sys
import os
import numpy as np
import time

sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
    TAMANHOS,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import _scores_de_todas_jogadas

ARQUIVOS_NPZ = [
    r"C:\Users\diondu\Downloads\dataset_pequeno_0001.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0002.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0003.npz",
    r"C:\Users\diondu\Downloads\dataset_pequeno_0004.npz",
]

TAMANHO = "pequeno"
LINHAS, COLUNAS = TAMANHOS[TAMANHO]
LABELS_CANONICOS = todos_labels_canonicos(LINHAS, COLUNAS)
NUM_TRACOS = len(LABELS_CANONICOS)
PROFUNDIDADE = 7

# Para cada arquivo, testaremos amostras com diferentes qtd de tracos
# Mais tracos = arvore mais rasa = mais rapido. Poucos tracos = pesado.
# Vamos pegar tracos entre 15 e 25 para ser viavel (arvore < 16 jogadas restantes)
FAIXAS_TRACOS = [15, 18, 20, 23, 25]
AMOSTRAS_POR_FAIXA = 1  # 1 amostra por faixa por arquivo = 5 x 4 = 20 recalculos

print("=" * 80)
print("FASE 2: RECALCULO INDEPENDENTE DO MINIMAX")
print("=" * 80)
print(f"Profundidade: {PROFUNDIDADE}")
print(f"Faixas de tracos: {FAIXAS_TRACOS}")
print()


def reconstruir_tabuleiro(mat_npz):
    """Reconstroi EstadoTabuleiro a partir da matriz NPZ (dominio {0,1,8,9})."""
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    h, w = mat_npz.shape
    for r in range(h):
        for c in range(w):
            val = int(mat_npz[r, c])
            if val == 9:
                estado.matriz[r, c] = 1  # aresta preenchida -> jogador generico
            elif val == 1:
                estado.matriz[r, c] = 1  # caixa fechada -> jogador generico
            # val == 0 (vazio) e val == 8 (ponto) ja estao corretos
    return estado


resultados = {"ok": 0, "falha": 0, "skip": 0}

for caminho in ARQUIVOS_NPZ:
    nome = os.path.basename(caminho)
    if not os.path.exists(caminho):
        print(f"SKIP: {nome} nao encontrado")
        continue

    dados = np.load(caminho)
    estados = dados["estados"]
    qtd_tracos = dados["qtd_tracos"]
    scores_npz = dados["score_melhor_jogada"]
    melhores_npz = dados["melhor_jogada"]
    labels_npz = [str(l) for l in dados["labels_canonicos"]]
    n = estados.shape[0]

    print(f"\n{'=' * 60}")
    print(f"ARQUIVO: {nome} ({n} amostras)")
    print(f"{'=' * 60}")

    # Verificar que os labels do NPZ sao iguais aos canonicos
    if labels_npz == LABELS_CANONICOS:
        print(f"  [OK] Labels canonicos conferem")
    else:
        print(f"  [ERRO] Labels canonicos DIVERGEM!")
        print(f"    NPZ:   {labels_npz}")
        print(f"    Local: {LABELS_CANONICOS}")
        resultados["falha"] += 1
        continue

    for faixa in FAIXAS_TRACOS:
        candidatos = np.where(qtd_tracos == faixa)[0]
        if len(candidatos) == 0:
            print(f"\n  Faixa {faixa} tracos: nenhuma amostra disponivel, tentando +/-1...")
            candidatos = np.where((qtd_tracos >= faixa - 1) & (qtd_tracos <= faixa + 1))[0]
            if len(candidatos) == 0:
                print(f"    SKIP")
                resultados["skip"] += 1
                continue

        np.random.seed(hash(nome + str(faixa)) % (2**31))
        idx = np.random.choice(candidatos, size=min(AMOSTRAS_POR_FAIXA, len(candidatos)), replace=False)

        for i in idx:
            qt = int(qtd_tracos[i])
            tracos_restantes = NUM_TRACOS - qt
            mat = estados[i]
            scores_gravados = scores_npz[i]
            melhor_gravada = str(melhores_npz[i])

            print(f"\n  --- Amostra idx={i}, qtd_tracos={qt}, restantes={tracos_restantes} ---")

            # Reconstruir tabuleiro
            estado = reconstruir_tabuleiro(mat)
            disp = estado.tracos_disponiveis()

            if len(disp) == 0:
                print(f"    SKIP: estado terminal")
                resultados["skip"] += 1
                continue

            print(f"    Tracos disponiveis localmente: {len(disp)}")
            print(f"    Melhor jogada gravada: {melhor_gravada}")

            # Recalcular Minimax localmente
            t0 = time.time()
            scores_local = _scores_de_todas_jogadas(estado, PROFUNDIDADE)
            dt = time.time() - t0
            print(f"    Tempo de recalculo: {dt:.2f}s")

            # Montar vetor de scores na ordem canonica para comparacao
            vetor_local = np.full(NUM_TRACOS, -1e9, dtype=np.float32)
            for j, label in enumerate(LABELS_CANONICOS):
                if label in scores_local:
                    vetor_local[j] = float(scores_local[label])

            # Comparar score por score
            divergencias = []
            for j in range(NUM_TRACOS):
                sg = scores_gravados[j]
                sl = vetor_local[j]
                # Ambos sentinela (-1e9): ok
                if sg == -1e9 and sl == -1e9:
                    continue
                # Um sentinela e outro nao: problema
                if (sg == -1e9) != (sl == -1e9):
                    divergencias.append((j, LABELS_CANONICOS[j], sg, sl, "sentinela mismatch"))
                    continue
                # Ambos tem valor: comparar
                if abs(sg - sl) > 0.01:
                    divergencias.append((j, LABELS_CANONICOS[j], sg, sl, "valor diferente"))

            if not divergencias:
                print(f"    [OK] Todos os {len(disp)} scores conferem EXATAMENTE!")
                # Verificar melhor jogada
                melhor_score_local = max(scores_local.values())
                melhores_local = [l for l, s in scores_local.items() if s == melhor_score_local]
                if melhor_gravada in melhores_local:
                    print(f"    [OK] Melhor jogada '{melhor_gravada}' esta entre as otimas locais: {melhores_local}")
                else:
                    # Pode ser empate que o Databricks desempatou diferente
                    score_da_gravada = scores_local.get(melhor_gravada, None)
                    if score_da_gravada == melhor_score_local:
                        print(f"    [OK] Melhor jogada '{melhor_gravada}' tem score otimo (empate)")
                    else:
                        print(f"    [WARN] Melhor jogada '{melhor_gravada}' score={score_da_gravada}, mas otimo={melhor_score_local}")
                        print(f"           Candidatas otimas locais: {melhores_local}")
                resultados["ok"] += 1
            else:
                print(f"    [ERRO] {len(divergencias)} divergencia(s) encontrada(s):")
                for j, lb, sg, sl, motivo in divergencias:
                    print(f"      [{j:2d}] {lb}: gravado={sg:+.0f}, local={sl:+.0f} ({motivo})")
                resultados["falha"] += 1

            # Mostrar detalhes dos scores para auditoria
            print(f"\n    Detalhes dos scores (gravado vs local):")
            for j, label in enumerate(LABELS_CANONICOS):
                sg = scores_gravados[j]
                sl = vetor_local[j]
                if sg == -1e9 and sl == -1e9:
                    continue
                match = "OK" if abs(sg - sl) < 0.01 else "DIFF"
                marker = " <-- MELHOR" if label == melhor_gravada else ""
                print(f"      [{j:2d}] {label}: gravado={sg:+.0f}, local={sl:+.0f}  [{match}]{marker}")

    dados.close()

# Resumo
print(f"\n{'=' * 80}")
print("RESUMO FINAL DA VERIFICACAO")
print(f"{'=' * 80}")
print(f"  Verificacoes OK:     {resultados['ok']}")
print(f"  Divergencias:        {resultados['falha']}")
print(f"  Pulados:             {resultados['skip']}")
if resultados["falha"] == 0:
    print("\n  >>> TODOS OS RECALCULOS CONFEREM COM O DATABRICKS! <<<")
else:
    print("\n  >>> ATENCAO: Divergencias encontradas! <<<")
print(f"{'=' * 80}")
