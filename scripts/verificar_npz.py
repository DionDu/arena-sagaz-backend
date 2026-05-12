"""Script de verificação dos NPZ gerados no Databricks.

Verifica:
1. Presença e completude de todas as chaves esperadas
2. Ausência de dados não preenchidos (NaN, zeros indevidos, etc.)
3. Recálculo independente do Minimax para amostras aleatórias
"""
import sys
import os
import numpy as np
import time

# Adicionar o diretório raiz do projeto ao path
sys.path.insert(0, r"d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import (
    EstadoTabuleiro,
    todos_labels_canonicos,
    TAMANHOS,
)
from gerador_dados.jogo_pontinhos.minimax_pontinhos import (
    _scores_de_todas_jogadas,
    melhor_jogada_com_scores,
)

# ── Configuração ──────────────────────────────────────────────
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

# Quantas amostras recalcular por arquivo
AMOSTRAS_POR_ARQUIVO = 3

print("=" * 80)
print("VERIFICAÇÃO COMPLETA DOS ARQUIVOS NPZ")
print("=" * 80)
print(f"Tamanho do tabuleiro: {TAMANHO} ({LINHAS}x{COLUNAS})")
print(f"Labels canônicos ({NUM_TRACOS}): {LABELS_CANONICOS[:5]} ... {LABELS_CANONICOS[-3:]}")
print(f"Profundidade Minimax: {PROFUNDIDADE}")
print(f"Amostras para recálculo por arquivo: {AMOSTRAS_POR_ARQUIVO}")
print()

# ── FASE 1: Inspeção de estrutura e completude ────────────────
print("=" * 80)
print("FASE 1: INSPEÇÃO DE ESTRUTURA E COMPLETUDE")
print("=" * 80)

todos_ok = True

for caminho in ARQUIVOS_NPZ:
    nome = os.path.basename(caminho)
    print(f"\n{'─' * 60}")
    print(f"📁 Arquivo: {nome}")
    print(f"{'─' * 60}")
    
    if not os.path.exists(caminho):
        print(f"  ❌ ARQUIVO NÃO ENCONTRADO!")
        todos_ok = False
        continue
    
    dados = np.load(caminho)
    chaves = list(dados.keys())
    print(f"  Chaves presentes: {chaves}")
    
    # Verificar chaves esperadas
    chaves_esperadas = ["estados", "targets", "minimax_depth"]
    # Verificar também chaves opcionais/novas
    chaves_novas_possiveis = ["melhor_jogada", "scores_minimax", "best_move_index", 
                               "best_move_label", "minimax_scores"]
    
    for chave in chaves_esperadas:
        if chave in chaves:
            print(f"  ✅ Chave '{chave}' presente")
        else:
            print(f"  ⚠️  Chave '{chave}' AUSENTE")
    
    # Mostrar chaves extras
    chaves_extras = [c for c in chaves if c not in chaves_esperadas]
    if chaves_extras:
        print(f"  📋 Chaves adicionais: {chaves_extras}")
    
    # ── Análise de cada array ──
    for chave in chaves:
        arr = dados[chave]
        print(f"\n  📊 Array '{chave}':")
        print(f"     Shape: {arr.shape}")
        print(f"     Dtype: {arr.dtype}")
        print(f"     Valores únicos (primeiros 20): {np.unique(arr)[:20]}")
        
        # Verificar NaN
        if np.issubdtype(arr.dtype, np.floating):
            nan_count = np.isnan(arr).sum()
            if nan_count > 0:
                print(f"     ❌ {nan_count} valores NaN encontrados!")
                todos_ok = False
            else:
                print(f"     ✅ Nenhum NaN")
        
        # Verificar Inf
        if np.issubdtype(arr.dtype, np.floating):
            inf_count = np.isinf(arr).sum()
            if inf_count > 0:
                print(f"     ❌ {inf_count} valores Inf encontrados!")
                todos_ok = False
            else:
                print(f"     ✅ Nenhum Inf")
        
        # Análise específica por chave
        if chave == "estados":
            n_amostras = arr.shape[0]
            print(f"     Número de amostras: {n_amostras}")
            # Verificar domínio esperado: {0, 1, 8, 9}
            valores_unicos = set(np.unique(arr).tolist())
            dominio_esperado = {0, 1, 8, 9}
            if valores_unicos.issubset(dominio_esperado):
                print(f"     ✅ Domínio correto: {sorted(valores_unicos)} ⊆ {sorted(dominio_esperado)}")
            else:
                print(f"     ❌ Domínio inesperado: {sorted(valores_unicos)} (esperado ⊆ {sorted(dominio_esperado)})")
                todos_ok = False
            
            # Verificar dimensão da matriz
            if len(arr.shape) >= 3:
                h, w = arr.shape[1], arr.shape[2]
                esperado_h = 2 * LINHAS + 1
                esperado_w = 2 * COLUNAS + 1
                if h == esperado_h and w == esperado_w:
                    print(f"     ✅ Dimensões da matriz corretas: {h}x{w}")
                else:
                    print(f"     ❌ Dimensões incorretas: {h}x{w} (esperado {esperado_h}x{esperado_w})")
                    todos_ok = False
            
            # Verificar se algum estado está completamente zerado (sem traços)
            estados_todos_zero = 0
            for i in range(n_amostras):
                mat = arr[i]
                # Verificar se tem ao menos 1 traço (valor 9) ou caixa (valor 1)
                if np.count_nonzero((mat == 9) | (mat == 1)) == 0:
                    # Pode ser estado inicial legítimo (sem nenhum traço)
                    estados_todos_zero += 1
            if estados_todos_zero > 0:
                print(f"     ⚠️  {estados_todos_zero} estados sem nenhum traço (podem ser estados iniciais)")
        
        elif chave == "targets":
            n_amostras = arr.shape[0]
            print(f"     Número de targets: {n_amostras}")
            if len(arr.shape) >= 2:
                n_classes = arr.shape[1]
                print(f"     Dimensão do target: {n_classes}")
                if n_classes == NUM_TRACOS:
                    print(f"     ✅ Número de classes correto ({NUM_TRACOS})")
                else:
                    print(f"     ❌ Número de classes incorreto: {n_classes} (esperado {NUM_TRACOS})")
                    todos_ok = False
            
            # Verificar se os targets estão preenchidos (não todos zero)
            targets_zero = 0
            targets_nan_rows = 0
            targets_soma_errada = 0
            for i in range(n_amostras):
                t = arr[i]
                soma = t.sum()
                if np.issubdtype(arr.dtype, np.floating) and np.isnan(soma):
                    targets_nan_rows += 1
                elif soma == 0:
                    targets_zero += 1
                # Se é soft-target (probabilidade), soma deveria ser ~1.0
                # Se é score bruto, pode ter qualquer soma
            
            if targets_zero > 0:
                print(f"     ❌ {targets_zero} targets com soma zero (não preenchidos)!")
                todos_ok = False
            else:
                print(f"     ✅ Nenhum target com soma zero")
            
            if targets_nan_rows > 0:
                print(f"     ❌ {targets_nan_rows} targets com NaN!")
                todos_ok = False
            
            # Verificar se cada target tem pelo menos um valor != 0
            targets_sem_jogada = 0
            for i in range(n_amostras):
                t = arr[i]
                if np.all(t == 0):
                    targets_sem_jogada += 1
            if targets_sem_jogada > 0:
                print(f"     ❌ {targets_sem_jogada} targets com TODOS os valores zerados!")
                todos_ok = False
            else:
                print(f"     ✅ Todos os targets têm pelo menos um valor não-zero")
            
            # Amostra dos primeiros targets
            print(f"     Primeiro target (amostra): {arr[0][:10]}...")
            print(f"     Min/Max target: {arr.min():.6f} / {arr.max():.6f}")
        
        elif chave == "minimax_depth":
            vals = np.unique(arr)
            print(f"     Valores de profundidade: {vals}")
            if PROFUNDIDADE in vals:
                print(f"     ✅ Profundidade {PROFUNDIDADE} presente")
            else:
                print(f"     ⚠️  Profundidade {PROFUNDIDADE} não encontrada entre os valores")
        
        elif "best_move" in chave or "melhor_jogada" in chave:
            print(f"     ✅ Dados de melhor jogada presentes!")
            if np.issubdtype(arr.dtype, np.integer):
                vals_unicos = np.unique(arr)
                print(f"     Range de índices: {vals_unicos.min()} a {vals_unicos.max()}")
                if vals_unicos.max() < NUM_TRACOS:
                    print(f"     ✅ Índices dentro do range válido (0 a {NUM_TRACOS-1})")
                else:
                    print(f"     ❌ Índice máximo {vals_unicos.max()} excede {NUM_TRACOS-1}!")
                    todos_ok = False
                # Verificar se há -1 ou sentinela
                if -1 in vals_unicos or -999 in vals_unicos:
                    count_sentinela = np.sum((arr == -1) | (arr == -999))
                    print(f"     ❌ {count_sentinela} entradas com valor sentinela (-1 ou -999)!")
                    todos_ok = False
                else:
                    print(f"     ✅ Nenhum valor sentinela")
        
        elif "scores" in chave.lower():
            print(f"     ✅ Dados de scores Minimax presentes!")
            if len(arr.shape) >= 2:
                print(f"     Dimensão: {arr.shape[1]} scores por amostra")
    
    dados.close()

print(f"\n{'=' * 80}")
if todos_ok:
    print("✅ FASE 1 CONCLUÍDA - Todos os arquivos passaram na inspeção estrutural")
else:
    print("❌ FASE 1 CONCLUÍDA - Problemas encontrados (ver acima)")
print(f"{'=' * 80}")

# ── FASE 2: Recálculo do Minimax para validação ──────────────
print(f"\n{'=' * 80}")
print("FASE 2: RECÁLCULO DO MINIMAX PARA VALIDAÇÃO")
print("=" * 80)

def reconstruir_tabuleiro_de_matriz(mat_npz):
    """Reconstrói um EstadoTabuleiro a partir da matriz do NPZ.
    
    No NPZ (contexto 1): 0=vazio, 1=caixa fechada, 8=ponto, 9=aresta preenchida.
    Na classe: 0=vazio, 8=ponto, jogador=1/-1 para traços e caixas.
    
    Para o Minimax, precisamos marcar os traços como preenchidos (jogador genérico = 1).
    """
    estado = EstadoTabuleiro(LINHAS, COLUNAS)
    h, w = mat_npz.shape[0], mat_npz.shape[1]
    
    for r in range(h):
        for c in range(w):
            val = int(mat_npz[r, c])
            if val == 8:
                # Ponto fixo - já está na matriz
                continue
            elif val == 9:
                # Aresta preenchida - marcar com jogador genérico
                estado.matriz[r, c] = 1
            elif val == 1:
                # Caixa fechada - marcar com jogador genérico
                estado.matriz[r, c] = 1
            # val == 0 já é vazio
    
    return estado


def verificar_amostra(idx, mat_npz, target_npz, arquivo_nome):
    """Recalcula o Minimax localmente e compara com o target do NPZ."""
    print(f"\n  🔍 Amostra #{idx} de '{arquivo_nome}':")
    
    # Reconstruir tabuleiro
    estado = reconstruir_tabuleiro_de_matriz(mat_npz)
    
    # Mostrar estado do tabuleiro
    tracos_disp = estado.tracos_disponiveis()
    n_tracos_disp = len(tracos_disp)
    n_tracos_total = NUM_TRACOS
    n_tracos_preenchidos = n_tracos_total - n_tracos_disp
    
    print(f"     Traços preenchidos: {n_tracos_preenchidos}/{n_tracos_total}")
    print(f"     Traços disponíveis: {n_tracos_disp}")
    
    if n_tracos_disp == 0:
        print(f"     ⚠️  Estado terminal - pulando recálculo")
        return None
    
    # Mostrar a matriz de forma visual compacta
    print(f"     Matriz NPZ (valores únicos): {np.unique(mat_npz).tolist()}")
    
    # Recalcular scores do Minimax
    print(f"     ⏳ Recalculando Minimax (profundidade={PROFUNDIDADE})...")
    t0 = time.time()
    scores_local = _scores_de_todas_jogadas(estado, PROFUNDIDADE)
    t1 = time.time()
    print(f"     ⏱️  Tempo de cálculo: {t1-t0:.2f}s")
    
    # Montar vetor de scores na ordem canônica
    scores_vetor_local = np.zeros(NUM_TRACOS, dtype=np.float32)
    for i, label in enumerate(LABELS_CANONICOS):
        if label in scores_local:
            scores_vetor_local[i] = scores_local[label]
    
    # Encontrar melhor jogada local
    melhor_local_idx = np.argmax(scores_vetor_local[scores_vetor_local != 0] if np.any(scores_vetor_local != 0) else scores_vetor_local)
    
    # Na verdade, preciso considerar que o score 0 pode ser válido.
    # A melhor jogada é o argmax dentre os traços disponíveis.
    indices_disponiveis = []
    for i, label in enumerate(LABELS_CANONICOS):
        if label in scores_local:
            indices_disponiveis.append(i)
    
    if not indices_disponiveis:
        print(f"     ⚠️  Nenhum traço disponível para comparação")
        return None
    
    scores_disponiveis = [scores_vetor_local[i] for i in indices_disponiveis]
    melhor_score_local = max(scores_disponiveis)
    melhor_idx_local = indices_disponiveis[scores_disponiveis.index(melhor_score_local)]
    melhor_label_local = LABELS_CANONICOS[melhor_idx_local]
    
    print(f"     📊 Scores recalculados (traços disponíveis):")
    for i, label in enumerate(LABELS_CANONICOS):
        if label in scores_local:
            marker = " ← MELHOR" if scores_local[label] == melhor_score_local else ""
            print(f"        [{i:2d}] {label}: score={scores_local[label]:+d}{marker}")
    
    # Comparar com target do NPZ
    print(f"\n     📋 Target do NPZ:")
    target_nonzero = np.nonzero(target_npz)[0]
    print(f"        Posições não-zero: {target_nonzero.tolist()}")
    for idx_t in target_nonzero:
        label_t = LABELS_CANONICOS[idx_t] if idx_t < len(LABELS_CANONICOS) else f"[idx={idx_t}]"
        print(f"        [{idx_t:2d}] {label_t}: valor={target_npz[idx_t]:.6f}")
    
    # O target pode ser soft-target (softmax dos scores) ou one-hot
    # Vamos comparar a MELHOR JOGADA (argmax do target vs argmax do recálculo)
    melhor_idx_npz = np.argmax(target_npz)
    melhor_label_npz = LABELS_CANONICOS[melhor_idx_npz] if melhor_idx_npz < len(LABELS_CANONICOS) else f"[idx={melhor_idx_npz}]"
    
    print(f"\n     🎯 Comparação da melhor jogada:")
    print(f"        NPZ (argmax target):    [{melhor_idx_npz:2d}] {melhor_label_npz} (valor={target_npz[melhor_idx_npz]:.6f})")
    print(f"        Recálculo local:         [{melhor_idx_local:2d}] {melhor_label_local} (score={melhor_score_local:+d})")
    
    # Verificar se a melhor jogada coincide
    # Pode haver empates - verificar se o argmax do NPZ está entre os empatados
    melhores_labels_local = [l for l, s in scores_local.items() if s == melhor_score_local]
    melhores_indices_local = [LABELS_CANONICOS.index(l) for l in melhores_labels_local]
    
    if melhor_idx_npz in melhores_indices_local:
        print(f"        ✅ MELHOR JOGADA COINCIDE!")
        if len(melhores_labels_local) > 1:
            print(f"        ℹ️  (Havia {len(melhores_labels_local)} jogadas empatadas com score {melhor_score_local})")
        return True
    else:
        # Verificar se o score do NPZ argmax é pelo menos igual
        label_npz_melhor = LABELS_CANONICOS[melhor_idx_npz]
        if label_npz_melhor in scores_local:
            score_da_escolha_npz = scores_local[label_npz_melhor]
            if score_da_escolha_npz == melhor_score_local:
                print(f"        ✅ MELHOR JOGADA EQUIVALENTE (mesmo score, empate)")
                return True
            else:
                print(f"        ❌ DIVERGÊNCIA! Score da escolha NPZ: {score_da_escolha_npz:+d} vs melhor local: {melhor_score_local:+d}")
                return False
        else:
            print(f"        ❌ DIVERGÊNCIA! Label {label_npz_melhor} não está nos traços disponíveis!")
            return False


# Executar recálculo em amostras
np.random.seed(42)
resultados_totais = {"ok": 0, "falha": 0, "skip": 0}

for caminho in ARQUIVOS_NPZ:
    nome = os.path.basename(caminho)
    if not os.path.exists(caminho):
        print(f"\n  ⚠️  Pulando {nome} (não encontrado)")
        continue
    
    dados = np.load(caminho)
    estados = dados["estados"]
    targets = dados["targets"]
    n_amostras = estados.shape[0]
    
    print(f"\n{'─' * 60}")
    print(f"📁 Recalculando amostras de: {nome} ({n_amostras} amostras)")
    print(f"{'─' * 60}")
    
    # Selecionar amostras aleatórias (preferir estados com traços intermediários)
    indices = np.random.choice(n_amostras, size=min(AMOSTRAS_POR_ARQUIVO, n_amostras), replace=False)
    
    for idx in sorted(indices):
        mat = estados[idx]
        # Se a matriz tem 4 dimensões (batch, h, w, channels), ajustar
        if len(mat.shape) == 3:
            mat = mat[:, :, 0]  # remover canal
        
        target = targets[idx]
        
        resultado = verificar_amostra(idx, mat, target, nome)
        if resultado is None:
            resultados_totais["skip"] += 1
        elif resultado:
            resultados_totais["ok"] += 1
        else:
            resultados_totais["falha"] += 1
    
    dados.close()

# ── Resumo Final ──────────────────────────────────────────────
print(f"\n{'=' * 80}")
print("RESUMO FINAL")
print(f"{'=' * 80}")
print(f"  ✅ Verificações OK:     {resultados_totais['ok']}")
print(f"  ❌ Divergências:        {resultados_totais['falha']}")
print(f"  ⏭️  Pulados (terminal): {resultados_totais['skip']}")
print()

if resultados_totais["falha"] == 0 and todos_ok:
    print("🎉 TODOS OS TESTES PASSARAM! Os dados do Databricks estão corretos.")
else:
    print("⚠️  ATENÇÃO: Foram encontrados problemas. Revise os detalhes acima.")
print(f"{'=' * 80}")
