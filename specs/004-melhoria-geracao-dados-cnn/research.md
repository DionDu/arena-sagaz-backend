# Pesquisa — Fase 0 do plano

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](./plan.md)

> Esta pesquisa **não inventa** decisões: todas as resoluções abaixo já foram tomadas no `/speckit-clarify` de 2026-05-07 (consolidadas em `spec.md > Clarifications`) ou estão fixadas no PRD como decisões D1–D10. Esta seção apenas consolida e referencia.

---

## 1. Resoluções de NEEDS CLARIFICATION (5 itens — `/speckit-clarify` 2026-05-07)

### 1.1 Limites operacionais do Databricks para o A.1

- **Decisão**: Não otimizar para o Databricks no escopo desta spec.
- **Racional**: A.1 herda a configuração do V4 atual (paralelismo, batch sizes, checkpointing, killer move heuristic, transposition table profundidade-aware). Ajustes de cluster/timeout/workers são feitos ad-hoc pelo desenvolvedor diretamente no Databricks no momento da execução. NFR-03 (≤ 4 h) tem folga grande sobre a estimativa de 1.34 h em 12 workers (PRD §4.1.3).
- **Alternativas consideradas**: parametrizar workers/timeout/batch via spec → rejeitada pela impossibilidade de prever a configuração do cluster naquele dia.

### 1.2 Linguagem do analisador estrutural no Flutter (Fase D)

- **Decisão**: Dart puro registrado como diretriz canônica para futura implementação no frontend, **mas a implementação Flutter está explicitamente fora do escopo desta spec**.
- **Racional**: Esta spec entrega no backend (a) o módulo Python `analisador_estrutural_pontinhos.py`, (b) o `contrato_codificacao_pontinhos.json` documentando regra de derivação, (c) **vetores de referência** versionados (`referencia_canais_pontinhos.json`) que servirão como ground truth para futura paridade Python↔Dart. O porte Dart, a publicação no app e o teste paralelo são feature(s) separada(s).
- **Alternativas consideradas**: FFI para C++ (overhead de build mobile alto), WebAssembly (overhead de carregamento alto). Lógica é < 200 linhas com BFS em ≤ 12 nós; Dart puro é viável e auditável.

### 1.3 Formato dos PNGs de validação visual (gate de A.2)

- **Decisão**:
  - **Resolução**: 150 DPI (FR-C-02a).
  - **Paleta**: categórica com **uma cor distinta por canal**, estável em todas as execuções para que revisão visual seja consistente entre lotes.
  - **Borda**: caixas fechadas (canal 5 = 1) recebem **borda destacada em todos os 11 boxnets** para distinguir visualmente "fechada" de "aberta com grau-4 hipotético".
  - **Título**: cada boxnet tem o **nome canônico do canal exatamente como aparece em `NOMES_CANAIS`** (ex.: `aresta_topo`, `caixa_fechada`, `em_cadeia_longa`).
- **Racional**: paleta categórica estável + borda destacada permitem detectar bugs do analisador estrutural em revisão rápida; títulos canônicos eliminam ambiguidade entre o array `nomes_canais` no NPZ e a constante `NOMES_CANAIS` em código.
- **Alternativas consideradas**: gradiente de cor (rejeitado — confunde quando vários canais têm o mesmo valor 1); paleta aleatória por execução (rejeitado — atrapalha comparação entre lotes).

### 1.4 Limite mínimo do canal `em_cadeia_longa`

- **Decisão**: Manter `cadeia_longa = ≥ 3` (canal único). K permanece em **11 canais**; tensor `(N, 4, 3, 11)` e array `nomes_canais` da §4.2 do PRD inalterados.
- **Racional**: separar `cadeia_media (=3)` vs `cadeia_longa (≥4)` introduziria 12º canal e mudaria o input do modelo, sem benefício mensurável a priori. Reavaliação só se experimento dedicado mostrar regressão atribuível a cadeias de comprimento exatamente 3 nas faixas 24–28 ou 29–30.
- **Alternativas consideradas**: 12 canais com separação fina (rejeitado — aumenta complexidade sem evidência empírica).

### 1.5 Observabilidade durante geração/enriquecimento/treino

- **Decisão**: Sem padrão obrigatório. Cada notebook decide ad-hoc o que exibir (distribuições, contadores, métricas, gráficos). Os notebooks rodam em ambiente externo (Databricks, Colab) e os resultados são trazidos manualmente pelo desenvolvedor para registro em `docs/historico_decisoes.md`. A spec **não exige** logging estruturado JSONL, MLflow, TensorBoard ou dashboards externos. Única obrigação preservada: diretriz do `CLAUDE.md` ("documentação viva") — entrada datada em `docs/historico_decisoes.md` ao fim de cada fase.
- **Racional**: notebooks rodam em ambientes que o desenvolvedor não controla integralmente; padronizar logging estruturado bloquearia o trabalho sem benefício imediato.
- **Alternativas consideradas**: MLflow obrigatório (rejeitado — overhead de setup), TensorBoard obrigatório (rejeitado — Colab/Databricks não preservam runs entre sessões com a confiabilidade necessária).

---

## 2. Decisões técnicas herdadas do PRD

> Já tomadas antes deste plano. Listadas para referência rápida.

### 2.1 D1 — Cobertura terminal expandida

- Faixa estendida: `[0.15·n_edges, 0.97·n_edges]` (de 5 a 30 traços).
- Distribuição U-invertida em 5 buckets: 5–11=10%, 12–17=20%, 18–23=28%, 24–28=32%, 29–30=10%.
- Tolerância: ±2pp na distribuição empírica final.

### 2.2 D1.a — Mix de geração

- `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]`:
  - 0=uniform: 5%
  - 1=sim_l1: **0% (DESLIGADO)** — eliminado por gerar estados "lunáticos" sem qualidade estratégica.
  - 2=sim_l2: 40%
  - 3=sim_l3: 55%

### 2.3 D1.b — Deduplicação obrigatória

- Hash por `mat.tobytes()`.
- Pré-população do set com hashes dos 314.323 únicos legados antes de iniciar a geração do complemento (FR-A-04, US6 cenário 3).
- Estados duplicados são regerados (até 20 tentativas).

### 2.4 D2 — NPZ pré-computa todos os 11 canais

- Tensor `canais (N, 4, 3, 11) int8` materializado no NPZ enriquecido.
- Canal 5 = `caixa_fechada` (binário) — não mais `dono_caixa` ternário.
- Campo auxiliar `nomes_canais (11,) U32` para auto-descrição (FR-B-02).
- `Lambda para_grid_de_caixas` **eliminada** do grafo Keras a partir do V6.

### 2.5 D3 — Pipeline em 2 notebooks

- A.1 Databricks: gera estados + Q-values, sem canais.
- A.2 local: enriquece com 11 canais, sobrescrita atômica via `.tmp` + `os.replace()` (NFR-06).

### 2.6 D4 — Validação visual obrigatória

- Script `scripts/pontinhos/validar_canais_visualmente.py` (parâmetros em FR-C-01).
- Layout: 1 PNG por estado, matriz crua dupla + 11 boxnets com título canônico.
- Gate manual: ≥ 30 PNGs revisados nas faixas 12–17, 24–28, 29–30 (FR-C-03).

### 2.7 D5 — Augmentação 4× (não 8×)

- Tabuleiro 4×3 não é quadrado: identidade + ref_H + ref_V + R180 são as únicas simetrias que preservam a forma.
- Permutação coerente de canais sob simetria (FR-E-03):
  - H: `aresta_esquerda ↔ aresta_direita`.
  - V: `aresta_topo ↔ aresta_base`.
  - R180: ambas.
  - Canais 5 e 6–11 não trocam de slot.

### 2.8 D9 — Sample_weight refinado por Δ_top2 em t=12–17

- `peso[i] = clip(1 + α · Δ_top2[i], 1.0, 1.20)` se `n_tracos_antes ∈ [12, 17]`; senão 1.0.
- α inicial sugerido: 0.03.
- Peso médio na faixa-alvo entre 1.05 e 1.15 (FR-G-03).

### 2.9 D10 — Value head AlphaZero-style

- Branch dedicado: `Conv 1×1 (16) → Flatten → Dense(64, relu) → Dense(1, tanh)`.
- Loss: `KLD(policy) + λ · MSE(value)` com λ ∈ [0.1, 0.3], inicial 0.1.
- `value_target = clip(score_max / 6.0, -1, +1)`.
- **Export TFLite descarta a value head** (contrato preservado, NFR-04).

---

## 3. Pendências de planejamento (não inventadas)

Listadas para registro; resolver durante implementação ou via `/speckit-clarify` futuro.

1. **Ordem exata de operações dentro de uma célula do notebook A.1** — pré-popular set de hashes antes vs depois de carregar `COMPLEMENTO_POR_CELULA`. Detalhe sem impacto de correção; resolver durante implementação.
2. **Seed específica para o split treino/val/teste no V6** — sugestão `42` (alinhada com V5). Reabrir se houver patologia empírica.
3. **Valor inicial de λ na Fase F** — PRD declara faixa `[0.1, 0.3]` com sugestão 0.1. Calibração final ad-hoc no início da Fase F (grid search com gate de não-regressão da policy + MSE da value ≤ 0.10).
4. **Formato do `referencia_canais_pontinhos`** — JSON (legível em diff de PR) vs NPZ (compacto). Recomendação inicial **JSON**.
5. **Esquema de versionamento do contrato JSON** — atualmente campo `versao` simples; considerar SemVer no futuro. Não bloqueia esta feature.

---

## 4. Saída

Todos os NEEDS CLARIFICATION resolvidos. Plano pode prosseguir para Fase 1 (design e contratos).
