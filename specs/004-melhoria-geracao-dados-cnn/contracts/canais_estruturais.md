# Contrato — Especificação algorítmica dos 11 canais

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](../plan.md) — espelha PRD §6.1–6.8 com mesma ordem canônica.

> Esta especificação é a fonte da verdade para a implementação Python (`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`) e — por extensão — para qualquer cliente externo (futuro porte Dart, fora do escopo). O `contrato_codificacao_pontinhos.json` versão 2.faseD é a representação declarativa equivalente; este documento é a explicação algorítmica em pt-BR.

---

## 1. Sistema de coordenadas

- **Tabuleiro**: 4 linhas × 3 colunas de caixas. 12 caixas total.
- **Matriz expandida**: `(9, 7)` (`2*r+1` × `2*c+1`).
- Caixa `(r, c)` com `r ∈ {0,1,2,3}`, `c ∈ {0,1,2}` corresponde à célula `[2r+1, 2c+1]`.

### Arestas vizinhas da caixa `(r, c)`

| Direção | Posição na matriz expandida |
|---|---|
| Topo | `[2r,   2c+1]` |
| Base | `[2r+2, 2c+1]` |
| Esquerda | `[2r+1, 2c  ]` |
| Direita | `[2r+1, 2c+2]` |

### Domínio do estado

Dataset (`contexto_1_geracao_dataset`): `M[i, j] ∈ {0, 1, 8, 9}` — **NUNCA `-1`**. Logo, caixa fechada é apenas valor `1` no centro (PRD §6.2).

---

## 2. Helpers fundamentais

```python
def _grau(M, r, c):
    """Grau da caixa (r, c): nº de arestas vizinhas com valor 9."""
    if M[2*r+1, 2*c+1] == 1:   # caixa fechada
        return 4
    return (
        (M[2*r,   2*c+1] == 9)
      + (M[2*r+2, 2*c+1] == 9)
      + (M[2*r+1, 2*c  ] == 9)
      + (M[2*r+1, 2*c+2] == 9)
    )

def _caixa_fechada(M, r, c):
    """True se a caixa (r, c) está fechada. Dataset NUNCA contém -1."""
    return M[2*r+1, 2*c+1] == 1
```

---

## 3. Canais 1–4 — arestas geométricas (`aresta_*`)

```python
# K=0: aresta_topo
canais[r, c, 0] = 1 if M[2*r,   2*c+1] == 9 else 0

# K=1: aresta_base
canais[r, c, 1] = 1 if M[2*r+2, 2*c+1] == 9 else 0

# K=2: aresta_esquerda
canais[r, c, 2] = 1 if M[2*r+1, 2*c  ] == 9 else 0

# K=3: aresta_direita
canais[r, c, 3] = 1 if M[2*r+1, 2*c+2] == 9 else 0
```

Reproduzem exatamente o que a Lambda `para_grid_de_caixas` do V5 calculava em runtime. A diferença é que agora ficam materializados no NPZ.

---

## 4. Canal 5 — `caixa_fechada`

```python
# K=4: caixa_fechada
canais[r, c, 4] = 1 if M[2*r+1, 2*c+1] == 1 else 0
```

**Observação para inferência em runtime (`contexto_3_partidas_ao_vivo`)**: lá o domínio é `{-1, 0, 1, 8}` e a normalização canônica `-1 → 1` é aplicada antes do tensor entrar no TFLite (vide `contrato_codificacao_pontinhos.json`). Portanto o cliente Dart, ao computar `caixa_fechada` on-device, opera sobre matriz já normalizada onde `1` significa "fechada por qualquer jogador" — exatamente igual ao dataset.

---

## 5. Canais 6–7 — `eh_grau3` e `eh_grau2`

```python
# K=5: eh_grau3 (não-fechada com 3 lados ocupados)
canais[r, c, 5] = 1 if (not _caixa_fechada(M, r, c) and _grau(M, r, c) == 3) else 0

# K=6: eh_grau2 (não-fechada com 2 lados ocupados)
canais[r, c, 6] = 1 if (not _caixa_fechada(M, r, c) and _grau(M, r, c) == 2) else 0
```

---

## 6. Canais 8–10 — `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`

### Algoritmo

1. Construir grafo dual `G_d`:
   - **Nós**: caixas `(r, c)` com `_grau(M, r, c) == 2` e `not _caixa_fechada(M, r, c)`.
   - **Arestas**: pares de nós que compartilham uma aresta livre (não-jogada).
2. Encontrar componentes conexas via BFS.
3. Para cada componente:
   - Se algum nó tem grau ≥ 3 dentro do componente (estrutura "T", rara em 4×3 mas possível) → **cadeia complexa**, atribuir todas as caixas a `em_cadeia_longa` (canal 8).
   - Se todos os nós têm grau exatamente 2 dentro do componente → **loop**. Marcar `em_loop = 1` (canal 9) para todas as caixas.
   - Caso contrário (caminho path/aberto) → **cadeia**. Comprimento = `|componente|`.
     - Comprimento 1–2 → `em_cadeia_curta` (canal 7).
     - Comprimento ≥ 3 → `em_cadeia_longa` (canal 8).

### Observação importante

**Múltiplas instâncias no mesmo estado**: se houver 2+ cadeias longas (ou curtas, ou loops) disjuntas no mesmo tabuleiro, todas as caixas de todas as instâncias são marcadas com 1 no mesmo canal (binário). Não há canais separados por instância — a CNN convolucional já é capaz de separar duas estruturas espacialmente disjuntas a partir do padrão binário (PRD §4.2).

### Exclusão mútua entre canais 7 e 8

Por componente: ou todas as caixas vão para `em_cadeia_curta` (≤ 2 caixas) ou todas vão para `em_cadeia_longa` (≥ 3 caixas). Componentes diferentes podem disparar canais diferentes — mas dentro de um mesmo componente, escolha é única.

---

## 7. Canal 11 — `em_cadeia_aberta_uma_ponta`

Para cada cadeia identificada na seção anterior (não loop), examinar as duas pontas:

- **Ponta** = nó da cadeia que tem grau 1 dentro do componente (apenas um vizinho grau-2 conectado por aresta livre).
- Examinar a aresta livre que sai da ponta para fora do componente:
  - Se a célula adjacente é uma **caixa grau-3** → ponta é "aberta" (capturável).

**Marcação** (canal 10):

- Se **exatamente 1** ponta é aberta → marcar todos os nós da cadeia em `em_cadeia_aberta_uma_ponta` (chain "half-open" do Barker & Korf 2012, Fig. 2-A).
- Se ambas as pontas estão abertas → "closed chain" — **não marcar** (cai em `em_cadeia_curta` ou `_longa` conforme comprimento).
- Se nenhuma ponta é aberta → cadeia interior — não marcar.

---

## 8. Permutação dos canais sob simetrias (Fase C)

Tabela completa de permutação para as 4 simetrias do tabuleiro 4×3. Espelho de PRD §6.8.

| Simetria | Espacial sobre `(r, c)` | Permutação de canais |
|---|---|---|
| Identidade | `(r, c) → (r, c)` | nenhuma |
| Reflexão horizontal | `(r, c) → (r, n_cols-1-c)` | `aresta_esquerda ↔ aresta_direita` (canais 2 e 3 trocam) |
| Reflexão vertical | `(r, c) → (n_rows-1-r, c)` | `aresta_topo ↔ aresta_base` (canais 0 e 1 trocam) |
| Rotação 180° | `(r, c) → (n_rows-1-r, n_cols-1-c)` | ambas as trocas acima |

Os canais 4 (`caixa_fechada`) e 5–10 (estruturais binários) **não trocam de slot** — apenas o conteúdo espacial é refletido/rotacionado.

### Pseudo-código

```python
def aplicar_simetria_horizontal(canais):
    out = canais[:, ::-1, :].copy()              # reflete em c
    out[..., [2, 3]] = out[..., [3, 2]]          # troca aresta_esquerda ↔ aresta_direita
    return out

def aplicar_simetria_vertical(canais):
    out = canais[::-1, :, :].copy()              # reflete em r
    out[..., [0, 1]] = out[..., [1, 0]]          # troca aresta_topo ↔ aresta_base
    return out

def aplicar_rotacao_180(canais):
    out = canais[::-1, ::-1, :].copy()
    out[..., [0, 1]] = out[..., [1, 0]]
    out[..., [2, 3]] = out[..., [3, 2]]
    return out
```

### Permutação coerente de outros tensores associados

A simetria deve ser aplicada **a TODOS os tensores associados a cada amostra** (FR-E-03):

- Matriz crua `(9, 7)`: `np.flip` / `np.rot90` correspondente.
- Vetor de scores `(31,)`: cada label é remapeado pela mesma simetria via tabela de `permutacoes_simetria_pontinhos.py`.
- Label canônico (rótulo de melhor aresta): remapeado via tabela.
- Tensor `canais (4, 3, 11)`: como acima.

---

## 9. Garantias verificáveis pelo teste unitário

- **Determinismo**: `extrair_canais(M)` é uma função pura.
- **Domínio binário**: `canais.dtype == np.int8`; `set(canais.flatten()) ⊆ {0, 1}`.
- **Exclusão mútua**: para toda caixa `(r, c)` com `canais[r, c, 4] == 1`, todos os canais 5–10 valem 0 nessa célula.
- **Coerência sob simetria**: `extrair_canais(simetria(M)) == simetria(extrair_canais(M))` (byte-a-byte).
- **Auto-descrição**: `np.array(NOMES_CANAIS, dtype="U32")` é o array gravado em `nomes_canais` no NPZ Fase A.2.

---

## 10. Vetores de referência (Fase D)

Conjunto canônico em `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` cobrindo:

1. Estado vazio (todas as arestas livres).
2. Caixa fechada simples.
3. Double-cross do Buchin Fig. 2.
4. Loop fechado de 4 caixas.
5. 2 cadeias longas disjuntas.
6. Half-open chain (1 ponta capturável).
7. Handout (Berlekamp).
8. ≥ 20 estados sorteados em t ∈ {14, 17, 24, 29}.

Cada entrada é um par `(matriz_crua (9,7) int8, canais (4,3,11) int8)` com seed reproducível para auditoria.

---

**Fim do contrato algorítmico.** Implementação fiel em `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`.
