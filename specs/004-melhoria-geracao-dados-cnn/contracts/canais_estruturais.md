# Contrato — Especificação algorítmica dos 12 canais

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](../plan.md) — espelha PRD §6.1–6.8 com mesma ordem canônica.

> Esta especificação é a fonte da verdade para a implementação Python (`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`) e — por extensão — para qualquer cliente externo (futuro porte Dart, fora do escopo). O `contrato_codificacao_pontinhos.json` versão 2.faseD é a representação declarativa equivalente; este documento é a explicação algorítmica em pt-BR.

> **Revisão 2026-05-13**: adicionado canal 12 (`paridade_cadeia_longa_impar`, K=11) — canal broadcast global que codifica a paridade do número de cadeias longas abertas. Motivação e teoria em `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`. N_CANAIS passa de 11 para **12**.

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
     - Comprimento = 1 → **nó isolado** — ver regra de half-open mínimo abaixo.
     - Comprimento = 2 → `em_cadeia_curta` (canal 7).
     - Comprimento ≥ 3 → `em_cadeia_longa` (canal 8).

### Observação importante

**Múltiplas instâncias no mesmo estado**: se houver 2+ cadeias longas (ou curtas, ou loops) disjuntas no mesmo tabuleiro, todas as caixas de todas as instâncias são marcadas com 1 no mesmo canal (binário). Não há canais separados por instância — a CNN convolucional já é capaz de separar duas estruturas espacialmente disjuntas a partir do padrão binário (PRD §4.2).

### Exclusão mútua entre canais 7 e 8

Por componente: ou todas as caixas vão para `em_cadeia_curta` (exatamente 2 caixas), ou todas vão para `em_cadeia_longa` (≥ 3 caixas). Componentes de tamanho 1 (nó isolado) não recebem canal 7 nem 8 — podem receber canal 10 (ver seção 7). Componentes diferentes podem disparar canais diferentes — mas dentro de um mesmo componente, a escolha é única.

---

## 7. Canal 11 — `em_cadeia_aberta_uma_ponta`

### Cadeias de comprimento ≥ 2 (path)

Para cada cadeia identificada na seção anterior (não loop), examinar as duas pontas:

- **Ponta** = nó da cadeia que tem grau 1 dentro do componente (apenas um vizinho grau-2 conectado por aresta livre).
- Examinar a aresta livre que sai da ponta para fora do componente:
  - Se a célula adjacente é uma **caixa grau-3** → ponta é "aberta" (capturável).

**Marcação** (canal 10):

- Se **exatamente 1** ponta é aberta → marcar todos os nós da cadeia em `em_cadeia_aberta_uma_ponta` (chain "half-open" do Barker & Korf 2012, Fig. 2-A).
- Se ambas as pontas estão abertas → "closed chain" — **não marcar** (cai em `em_cadeia_curta` ou `_longa` conforme comprimento).
- Se nenhuma ponta é aberta → cadeia interior — não marcar.

### Nó isolado (comprimento = 1) — half-open mínimo

Uma caixa grau-2 sem vizinhos grau-2 via aresta livre (nó isolado no grafo dual) representa o menor padrão de sacrifício possível: jogar sua aresta livre restante entrega 2 capturas ao oponente (a própria caixa + a grau-3 adjacente).

**Regra**: contar quantas vizinhas ortogonais `v` satisfazem simultaneamente `_aresta_livre_entre(M, nó, v)` e `grau(v) == 3`.

| Contagem | Significado | Canal 10 |
|---|---|---|
| 0 | isolado interior | 0 |
| **1** | **half-open mínimo** | **1** |
| 2 | "closed" de comprimento 1 | 0 |

**Nota de implementação**: esta contagem deve ser feita sem `break` (diferentemente de `_contar_pontas_abertas`, que usa `break` para cadeias ≥ 2 onde um único caminho por ponta basta).

---

## 8. Canal 12 — `paridade_cadeia_longa_impar`

Canal **broadcast global**: todas as 12 células do tensor recebem o mesmo valor inteiro em `{0, 1}`.

- **Valor 1**: o número de cadeias longas abertas no estado é **ímpar** (1, 3, 5, …).
- **Valor 0**: o número de cadeias longas abertas é **par ou zero** (0, 2, 4, …).

Uma "cadeia longa aberta" é um componente conexo no grafo dual de grau-2 que satisfaz simultaneamente:
- Comprimento ≥ 3 (não é nó isolado nem cadeia curta).
- Não é loop (não ocorre `all(grau_no_componente == 2)`).
- Não é complexa (`max(grau_no_componente) < 3`).

**Pseudo-código** (integrado ao loop de classificação de `extrair_canais`, após construir `adj` e `componentes`):

```python
n_cadeias_longas = sum(
    1 for comp in componentes
    if len(comp) >= 3
    and not all(len(adj[u]) == 2 for u in comp)   # não é loop
    and max(len(adj[u]) for u in comp) < 3         # não é complexa
)
paridade_impar = (n_cadeias_longas % 2) == 1

# K=11: broadcast para todas as células
for r in range(N_LINHAS):
    for c in range(N_COLUNAS):
        canais[r, c, 11] = 1 if paridade_impar else 0
```

**Motivação teórica**: ver `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`. Em síntese: a paridade do número de cadeias longas abertas é uma propriedade global que determina a estratégia ótima de sacrifício/double-cross no endgame. Uma CNN com receptivo campo local não consegue inferir paridade global por convolução; este canal entrega o bit diretamente a todas as posições.

---

## 9. Permutação dos canais sob simetrias (Fase C)

Tabela completa de permutação para as 4 simetrias do tabuleiro 4×3. Espelho de PRD §6.8.

| Simetria | Espacial sobre `(r, c)` | Permutação de canais |
|---|---|---|
| Identidade | `(r, c) → (r, c)` | nenhuma |
| Reflexão horizontal | `(r, c) → (r, n_cols-1-c)` | `aresta_esquerda ↔ aresta_direita` (canais 2 e 3 trocam) |
| Reflexão vertical | `(r, c) → (n_rows-1-r, c)` | `aresta_topo ↔ aresta_base` (canais 0 e 1 trocam) |
| Rotação 180° | `(r, c) → (n_rows-1-r, n_cols-1-c)` | ambas as trocas acima |

Os canais 4 (`caixa_fechada`) e 5–11 (estruturais binários) **não trocam de slot** — apenas o conteúdo espacial é refletido/rotacionado.

**Canal 12 (`paridade_cadeia_longa_impar`, K=11) sob simetria**: por ser broadcast (escalar global), o valor não muda sob nenhuma simetria espacial. Reflexão/rotação do tabuleiro não altera o número de cadeias longas, apenas reposiciona suas células. Não há permutação de slot nem de conteúdo para K=11.

### Pseudo-código

```python
def aplicar_simetria_horizontal(canais):
    out = canais[:, ::-1, :].copy()              # reflete em c
    out[..., [2, 3]] = out[..., [3, 2]]          # troca aresta_esquerda ↔ aresta_direita
    # K=11 (paridade) não muda — valor broadcast é idêntico após reflexão
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
- Tensor `canais (4, 3, 12)`: como acima (K=11 preservado byte-a-byte — broadcast não muda).

---

## 10. Garantias verificáveis pelo teste unitário

- **Determinismo**: `extrair_canais(M)` é uma função pura.
- **Domínio binário**: `canais.dtype == np.int8`; `set(canais.flatten()) ⊆ {0, 1}`.
- **Exclusão mútua**: para toda caixa `(r, c)` com `canais[r, c, 4] == 1`, todos os canais 5–11 valem 0 nessa célula. (Canal 12 / K=11 é broadcast global — pode ter qualquer valor em `{0,1}` independentemente do status de fechamento da caixa.)
- **Broadcast K=11**: todos os 12 valores `canais[r, c, 11]` são idênticos para dado `M`.
- **Coerência sob simetria**: `extrair_canais(simetria(M)) == simetria(extrair_canais(M))` (byte-a-byte). Para K=11, igualdade trivial (broadcast preservado).
- **Auto-descrição**: `np.array(NOMES_CANAIS, dtype="U32")` é o array gravado em `nomes_canais` no NPZ Fase A.2. `len(NOMES_CANAIS) == 12`.

---

## 11. Vetores de referência (Fase D)

Conjunto canônico em `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` cobrindo:

1. Estado vazio (todas as arestas livres). → K=11 deve ser 0 (zero cadeias longas).
2. Caixa fechada simples.
3. Double-cross do Buchin Fig. 2.
4. Loop fechado de 4 caixas. → K=11 deve ser 0 (loop não conta como cadeia longa).
5. 2 cadeias longas disjuntas. → K=11 deve ser **0** (par).
6. 1 cadeia longa + 1 cadeia curta. → K=11 deve ser **1** (ímpar).
7. Half-open chain (1 ponta capturável).
8. Handout (Berlekamp).
9. ≥ 20 estados sorteados em t ∈ {14, 17, 24, 29}.

Cada entrada é um par `(matriz_crua (9,7) int8, canais (4,3,12) int8)` com seed reproducível para auditoria.

---

**Fim do contrato algorítmico.** Implementação fiel em `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`.
