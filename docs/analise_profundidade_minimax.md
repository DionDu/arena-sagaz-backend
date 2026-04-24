# Análise de Profundidade do Minimax e Estimativas de Geração

**Projeto Arena Sagaz — Jogo dos Pontinhos (Dots and Boxes)**
**Data**: Abril/2026

Este documento fundamenta a escolha da profundidade do Minimax para cada tamanho de tabuleiro na geração de dados de treinamento da CNN. Serve como referência técnica para o TCC.

---

## 1. O que é a profundidade do Minimax

O Minimax com Poda Alpha-Beta é um algoritmo de busca em árvore que explora jogadas futuras para encontrar a **jogada ótima**. A **profundidade** define quantas jogadas (traços) à frente o algoritmo simula antes de retornar uma avaliação.

```
Profundidade 7 = o algoritmo simula 7 traços à frente,
alternando entre IA e Humano, antes de avaliar o resultado.
```

### O que a profundidade NÃO é

- **Não é o número de caixas que o algoritmo "enxerga".**
  Uma jogada pode fechar 0, 1 ou 2 caixas (aresta compartilhada entre duas caixas).
  Além disso, fechar uma caixa dá **turno extra** ao jogador, gerando cadeias onde
  várias caixas são fechadas em sequência dentro de poucas jogadas.

- **Não é o número de jogadas restantes.**
  O algoritmo enxerga *no máximo* `profundidade` jogadas, mas se restarem menos
  jogadas do que a profundidade, ele enxerga **o jogo inteiro até o final**.

### Quando o Minimax joga perfeitamente

O Minimax joga de forma **matematicamente perfeita** (imbatível) quando:

```
profundidade ≥ jogadas_restantes
```

Nesse cenário, o algoritmo enxerga até o final do jogo e calcula o resultado exato.
Quando `profundidade < jogadas_restantes`, o algoritmo usa uma **heurística** (diferença
de caixas no horizonte), que é uma boa aproximação mas não garante perfeição.

---

## 2. Tabuleiro Pequeno (4×3) — 12 caixas, 31 traços

### Cobertura por profundidade

O dataset gera estados aleatórios com **15% a 85% de preenchimento** dos traços.
A tabela mostra a qualidade do Minimax em diferentes fases do jogo:

| Fase do Jogo | Traços marcados | Restantes | Depth 6 | Depth 7 | Depth 8 |
|---|:---:|:---:|---|---|---|
| **Abertura** | ~5 (15%) | ~26 | 23% visível | 27% visível | 31% visível |
| **Meio-jogo** | ~15 (50%) | ~16 | 38% visível | 44% visível | 50% visível |
| **Pré-endgame** | ~20 (65%) | ~11 | 55% visível | 64% visível | 73% visível |
| **Endgame** | ~24 (77%) | ~7 | 86% visível | ✅ **100% perfeito** | ✅ 100% perfeito |
| **Final** | ~26 (85%) | ~5 | ✅ 100% perfeito | ✅ 100% perfeito | ✅ 100% perfeito |

### Por que a profundidade 7 foi escolhida

1. **Jogo perfeito a partir de 77% do tabuleiro.** Quando restam 7 ou menos traços,
   o Minimax com profundidade 7 calcula o resultado exato. É nessa fase que as
   cadeias de caixas se formam e as partidas são decididas.

2. **Cobertura sólida no meio-jogo (44%).** Em posições com ~15 traços marcados,
   o algoritmo enxerga quase metade do jogo restante, capturando a maioria das
   decisões estratégicas.

3. **Tempo de geração viável.** 300.000 amostras em ~18 minutos no Databricks,
   contra ~29 horas na profundidade 6 em CPU local (Ryzen 5700X).

### Profundidade 8: vale a pena?

A profundidade 8 oferece melhoria genuína no **meio-jogo** (50% vs 44% de cobertura)
e antecipa o jogo perfeito para 74% do tabuleiro (23 traços marcados). O custo estimado
é de ~1h a 1h30 no Databricks, que é aceitável.

**Recomendação**: se o cluster estiver disponível, gerar um dataset adicional com
profundidade 8 para comparação. Caso contrário, profundidade 7 é mais que suficiente
para produzir uma CNN que vença humanos com facilidade.

### Profundidades 9+ não são recomendadas

| Profundidade | Melhoria sobre depth 7 | Custo estimado (Databricks) |
|:---:|---|---|
| 8 | Meio-jogo: +6 pp de cobertura | ~1h a 1h30 |
| 9 | Meio-jogo: +13 pp de cobertura | ~5h a 8h |
| 10 | Meio-jogo: +19 pp de cobertura | ~18h a 30h |

O custo de depth 9+ cresce exponencialmente enquanto o benefício é marginal: um humano
casual raramente planeja mais de 2-3 jogadas à frente.

---

## 3. Tabuleiro Médio (5×4) — 20 caixas, 49 traços

### Parâmetros

- Matriz: `(11, 9)` — 11 linhas × 9 colunas
- Total de traços: **49**
- Total de caixas: **20**
- Fator de ramificação médio em mid-game (~50% preenchido): **~25**

### Cobertura por profundidade

| Fase do Jogo | Restantes | Depth 5 | Depth 6 | Depth 7 |
|---|:---:|---|---|---|
| **Abertura** (~15%) | ~42 | 12% | 14% | 17% |
| **Meio-jogo** (~50%) | ~24 | 21% | 25% | 29% |
| **Pré-endgame** (~70%) | ~15 | 33% | 40% | 47% |
| **Endgame** (~85%) | ~7 | 71% | ✅ 86% | ✅ 100% |
| **Final** (~90%) | ~5 | ✅ 100% | ✅ 100% | ✅ 100% |

### Profundidade recomendada: 6

- **Jogo perfeito no endgame** (a partir de ~86% do tabuleiro com 6 traços restantes).
- **Custo viável**: ~1h20 no Databricks para 300k amostras.
- Profundidade 7 levaria ~6h — o benefício extra (+4-7 pp no meio-jogo) não justifica o custo.

### Estimativas de tempo (300k amostras, Databricks)

| Profundidade | Tempo estimado | Recomendação |
|:---:|---|---|
| 5 | ~10 min | Rápido, qualidade boa |
| **6** | **~1h20** | **Recomendado — equilíbrio velocidade/qualidade** |
| 7 | ~6h | Opcional, para dataset premium |

---

## 4. Tabuleiro Grande (7×5) — 35 caixas, 82 traços

### Parâmetros

- Matriz: `(15, 11)` — 15 linhas × 11 colunas
- Total de traços: **82**
- Total de caixas: **35**
- Fator de ramificação médio em mid-game (~50% preenchido): **~40**

### Cobertura por profundidade

| Fase do Jogo | Restantes | Depth 4 | Depth 5 | Depth 6 |
|---|:---:|---|---|---|
| **Abertura** (~15%) | ~70 | 6% | 7% | 9% |
| **Meio-jogo** (~50%) | ~41 | 10% | 12% | 15% |
| **Pré-endgame** (~75%) | ~20 | 20% | 25% | 30% |
| **Endgame** (~90%) | ~8 | 50% | 63% | 75% |
| **Final** (~94%) | ~5 | 80% | ✅ 100% | ✅ 100% |

### Profundidade recomendada: 5

- O tabuleiro Grande tem **82 traços** — o espaço de busca é enormemente maior.
- Mesmo com profundidade 5, a CNN aprende os padrões estruturais (cadeias, double-crosses,
  sacrifícios) que são transferíveis de cenários mais profundos.
- **Custo viável**: ~1h10 no Databricks.
- Profundidade 6 levaria ~19h (overnight) e é viável se houver janela de tempo no cluster.

### Estimativas de tempo (300k amostras, Databricks)

| Profundidade | Tempo estimado | Recomendação |
|:---:|---|---|
| 4 | ~7 min | Mínimo viável para testes |
| **5** | **~1h10** | **Recomendado** |
| 6 | ~19h | Overnight, se cluster disponível |
| 7 | ~5+ dias ⚠️ | Não recomendado |

---

## 5. Complexidade computacional

A Poda Alpha-Beta reduz a complexidade do Minimax de `O(b^d)` para aproximadamente
`O(b^(d/2))` no melhor caso, onde:

- `b` = fator de ramificação (jogadas disponíveis)
- `d` = profundidade

### Comparação entre tamanhos

```
Pequeno (b≈15, d=7):  15^3.5  ≈      42.000 nós/estado
Médio   (b≈25, d=6):  25^3.0  ≈      15.600 nós/estado
Grande  (b≈40, d=5):  40^2.5  ≈     10.000 nós/estado
```

> **Nota**: esses valores são estimativas teóricas. Na prática, a Transposition Table
> com flags (EXACT, LOWERBOUND, UPPERBOUND) e o move ordering (caixa-closing moves
> primeiro) do Notebook V2 melhoram drasticamente o índice de poda, reduzindo os nós
> efetivamente avaliados.

### Tempos medidos vs estimados

| Tamanho | Profundidade | Ryzen 5700X (local) | Databricks (8 workers) |
|---|:---:|---|---|
| Pequeno | 6 | ~29h | ~4 min (estimado) |
| Pequeno | 7 | — | **18 min** (medido) |
| Médio | 6 | — | ~1h20 (estimado) |
| Grande | 5 | — | ~1h10 (estimado) |

O ganho do Databricks vem de:
1. **Paralelismo Spark**: 8 workers × 8 cores = 64 cores vs 16 threads do Ryzen.
2. **Motor Bitboard V2**: representação por inteiro de 31/49/82 bits com operações
   bitwise O(1), ~10-50× mais rápido que a versão original com strings e arrays.
3. **Transposition Table**: cache de estados já avaliados, eliminando reavaliações
   redundantes na árvore do Minimax.

---

## 6. Resumo de decisões para o TCC

| Tamanho | Profundidade | Justificativa | Tempo (Databricks) |
|---|:---:|---|---|
| **Pequeno** (4×3) | **7** | Jogo perfeito a partir de 77% do tabuleiro. Cobertura de 44% no meio-jogo. | 18 min |
| **Médio** (5×4) | **6** | Melhor equilíbrio custo-benefício. Jogo perfeito a partir de ~86% do tabuleiro. | ~1h20 |
| **Grande** (7×5) | **5** | Espaço de busca exponencialmente maior. CNN aprende padrões estruturais transferíveis. | ~1h10 |

> **Argumento-chave para o TCC**: a CNN não precisa replicar o Minimax perfeitamente
> em todas as posições. Ela precisa aprender os *padrões estratégicos* (cadeias de
> caixas, sacrifícios, double-crosses) que o Minimax descobre. Mesmo com profundidades
> moderadas, esses padrões estão presentes nos dados e a CNN os generaliza para
> posições que o Minimax nunca viu — jogando em **milissegundos** o que levaria
> segundos ou minutos no Minimax.
