# Feature Specification: Melhoria da geração de dados e arquitetura da CNN do Jogo dos Pontinhos

**Feature Branch**: `004-melhoria-geracao-dados-cnn`
**Created**: 2026-05-07
**Status**: Draft
**Input**: PRD revisado em `specs/004-melhoria-geracao-dados-cnn/PRD.md` (revisão 2026-05-07).
**Documento-base**: o PRD é a fonte da verdade. Este `spec.md` é um espelho operacional pensado para `/speckit-plan` — qualquer divergência **entre PRD e spec resolve em favor do PRD**, e a correção retorna a este arquivo.

---

## Clarifications

### Session 2026-05-07

- Q: Limites operacionais reais do Databricks para o notebook A.1 (workers, timeout, batch size) — qual cluster é assumido para parametrizar a geração? → A: **Não otimizar para o Databricks no escopo desta spec.** A.1 mantém a configuração e os parâmetros do notebook V4 atual (paralelismo, batch sizes, checkpointing). Qualquer ajuste de cluster/timeout/workers é feito ad-hoc pelo desenvolvedor diretamente no Databricks no momento da execução, fora do escopo do `spec.md` e do `plan.md`.
- Q: Linguagem/estratégia de implementação do analisador estrutural no Flutter (Fase D) — Dart puro, FFI para C++ ou WebAssembly? → A: **Dart puro é a diretriz canônica registrada para futura implementação no frontend.** Porém, **a implementação Flutter está explicitamente fora do escopo desta spec.** Esta spec entrega no backend: (a) o módulo Python `analisador_estrutural_pontinhos.py`, (b) o `contrato_codificacao_pontinhos.json` documentando a regra de derivação dos 11 canais, (c) um conjunto de **vetores de referência** (pares `matriz crua → canais (4,3,11) int8` em formato JSON/NPZ versionado) que servirão como ground truth para o teste de paridade do futuro porte Dart. O porte Dart, sua publicação no app e o teste paralelo Python↔Dart são feature(s) separada(s).
- Q: Formato exato dos PNGs de validação visual gerados por `validar_canais_visualmente.py` (gate de A.2) — DPI, paleta, borda especial? → A: **Resolução 150 DPI**, **paleta categórica com uma cor distinta por canal** (cores estáveis em todas as execuções para que revisão visual seja consistente entre lotes), **borda destacada em boxnets para caixas fechadas** (distingue visualmente "fechada" de "aberta com grau-4 hipotético"), e **título acima de cada boxnet com o nome canônico do canal exatamente como aparece em `NOMES_CANAIS`** (ex.: `aresta_topo`, `aresta_base`, `aresta_esquerda`, `aresta_direita`, `caixa_fechada`, `eh_grau3`, `eh_grau2`, `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`, `em_cadeia_aberta_uma_ponta`).
- Q: Limite mínimo do canal `em_cadeia_longa` — manter `≥3` ou separar em `cadeia_media (=3)` e `cadeia_longa (≥4)`? → A: **Manter `cadeia_longa = ≥3` (canal único).** K permanece em 11 canais; o tensor `(N, 4, 3, 11)` e o array `nomes_canais` da §4.2 do PRD ficam inalterados. A separação `cadeia_media (=3)` vs `cadeia_longa (≥4)` está **fora do escopo desta feature** — pode ser reavaliada em iteração futura se um experimento dedicado mostrar regressão na faixa 24–28 ou se o gate da Fase D/E/F falhar por motivo atribuível a cadeias de comprimento exatamente 3.
- Q: Observabilidade durante geração/enriquecimento/treino — qual mínimo canônico de logging/relatório os notebooks devem emitir? → A: **Sem padrão obrigatório.** Cada notebook decide ad-hoc o que exibir (distribuições, contadores, métricas, gráficos). Os notebooks rodam em ambiente externo (Databricks, Colab) e os resultados são trazidos **manualmente pelo desenvolvedor** para registro posterior em `docs/historico_decisoes.md`. A spec **não exige** logging estruturado JSONL, MLflow, TensorBoard nem dashboards externos. A única obrigação preservada é a diretriz do `CLAUDE.md` ("documentação viva"): registrar a entrada datada em `docs/historico_decisoes.md` ao fim de cada fase, mas o conteúdo dessa entrada é redigido manualmente a partir do que o desenvolvedor coletou nos notebooks.

---

## Visão geral

Esta feature evolui a CNN BoxNet v3 do Jogo dos Pontinhos (tabuleiro pequeno 4×3) corrigindo duas categorias de erro identificadas empiricamente:

- **Categoria A (tática, fim de jogo):** 87,8% das divergências fatais (360/410) acontecem na 30ª jogada (29 traços preenchidos), uma faixa **fora do dataset atual** (15–85%).
- **Categoria B (estratégica, meio de jogo):** 16,8% das partidas perdidas têm divergência fatal precoce (≤ 25 traços), proporção estável entre adversários Minimax(p=3/5/6) — sinal de erro sistêmico de paridade/cadeia, não induzido pelo adversário (Cenário X3 confirmado em 2026-05-06).

A solução é executada em **fases sequenciais e isoladas** (uma mudança por vez), permitindo atribuição de causa de cada ganho/regressão. As fases vão de 0 (concluída) a H (condicional). O entregável central é uma família de modelos TFLite (`pontinhos_pequeno_p9_faseB.tflite`, …, `_faseF.tflite`) e um pipeline de dados em dois notebooks (geração no Databricks + enriquecimento local) que produz NPZs com **500.000 estados únicos** e **11 canais pré-computados** (`(N, 4, 3, 11) int8`) por estado.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Cobertura terminal corrigindo erros táticos óbvios (Priority: P1)

Como **desenvolvedor de IA do Arena Sagaz**, preciso que a CNN deixe de cometer o erro tático elementar de não capturar uma única caixa grau-3 disponível na 30ª jogada (98% dos 505 erros do baseline). O pipeline atual nunca vê esses estados (faixa 15–85% de preenchimento), então o problema é primariamente de **distribuição de dados**, não de profundidade de supervisor.

**Why this priority**: É o erro mais frequente, mais visualmente óbvio, mais fácil de medir (`analisa_padrao_erros.py`) e o que mais corrói a percepção de qualidade do jogador casual. Sem corrigir essa classe, qualquer melhoria estratégica posterior é mascarada.

**Independent Test**: Após Fase A (geração) + Fase B (treino com 5 canais geométricos sobre o novo dataset), rodar `Avaliacao_CNN_vs_Minimax.ipynb` com 200 partidas vs Minimax(p=3) e `analisa_padrao_erros.py` sobre os jogos. Sucesso: total de erros reais ≤ 250 (queda ≥ 50%) **e** top-1 accuracy na faixa 29–30 traços ≥ 95%.

**Acceptance Scenarios**:

1. **Given** o NPZ Fase A.2 com 500.000 estados únicos e cobertura 5–30 traços (distribuição U-invertida), **When** o desenvolvedor treina a CNN apenas com os 5 canais geométricos (slice `canais[..., :5]`) usando `Treinamento_CNN_Arena_Sagaz_V6.ipynb`, **Then** o modelo `pontinhos_pequeno_p9_faseB.tflite` deve atingir top-1 accuracy ≥ 95% na faixa 29–30 traços e nenhuma faixa pode regredir > 2pp em relação ao baseline.
2. **Given** estados idênticos passados ao analisador estrutural Python e à futura porta Dart, **When** ambos computam o tensor `canais (4, 3, 11) int8`, **Then** os tensores devem ser **byte-a-byte idênticos** em 100% dos casos de teste.
3. **Given** o NPZ enriquecido após Fase A.2, **When** o desenvolvedor executa `validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30`, **Then** o script deve gerar 30 PNGs (1 por estado) cada um contendo a matriz crua em duas visualizações + os 11 canais individuais como boxnets 4×3 binários.

---

### User Story 2 — Eliminação do viés posicional via simetria 4× (Priority: P1)

Como **desenvolvedor**, preciso que a CNN deixe de ter um viés sistemático para arestas de borda externa (linhas/colunas 0, 6, 8) — viés confirmado em §2.4.6 do PRD nos pares "ótima → CNN" como `H_2_1 → V_1_0` (37 erros), `H_2_3 → H_0_3` (32) etc. A reflexão do tabuleiro 4×3 é o instrumento estrutural correto: **4 simetrias** (identidade, reflexão H, reflexão V, rotação 180°) — **não 8**, porque 4×3 não é quadrado.

**Why this priority**: O viés é assimétrico por construção do dataset atual (cada estado visto em uma única orientação) e pode ser eliminado a custo computacional baixo. Acoplado a User Story 1, completa o tratamento da Categoria A.

**Independent Test**: Após Fase C (augmentação 4× sobre o dataset Fase B), rodar `analisa_padrao_erros.py` e verificar que **nenhum par "deveria→jogou" individual representa mais que 5% do total de erros**, e que a soma absoluta de erros cai ~30% adicionais em relação à Fase B.

**Acceptance Scenarios**:

1. **Given** o tensor `canais (N, 4, 3, 5)` da Fase B, **When** o módulo `permutacoes_simetria_pontinhos.py` aplica reflexão horizontal, **Then** os canais `aresta_esquerda` e `aresta_direita` devem trocar de slot, `aresta_topo`/`aresta_base`/`caixa_fechada` permanecem nos próprios slots, e o conteúdo espacial é refletido em `c → n_cols-1-c`.
2. **Given** um label canônico `H_r_c` ou `V_r_c`, **When** uma das 4 simetrias é aplicada, **Then** a tabela de permutação de labels (validada em teste unitário) produz o label refletido/rotacionado correspondente, mantendo a semântica de aresta canônica.
3. **Given** o modelo `pontinhos_pequeno_p9_faseC.tflite`, **When** rodar `Avaliacao_CNN_vs_Minimax.ipynb`, **Then** o win-rate vs cada Minimax (p=3, p=5, p=6) deve ser ≥ ao da Fase B (não-regressão estrita).

---

### User Story 3 — Canais estruturais explícitos atacando paridade/cadeia (Priority: P1)

Como **desenvolvedor**, preciso que a CNN tenha acesso explícito a **6 canais estruturais binários** (`eh_grau3`, `eh_grau2`, `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`, `em_cadeia_aberta_uma_ponta`) calculados pelo analisador estrutural a partir da matriz crua. O Cenário X3 da Fase 0 mostrou que a Categoria B (16,8% de fatal precoce) é estável entre adversários — sinal de erro sistêmico de paridade/cadeia que apenas dados não resolvem.

**Why this priority**: Sem D, as Fases A/B/C atacam apenas a Categoria A. A literatura (Buchin 2021, Barker & Korf 2012, Li 2019) sustenta que features de cadeia/loop são as mais discriminativas em Dots & Boxes. O Cenário X3 da §2.4 do PRD torna a Fase D **obrigatória**.

**Independent Test**: Treinar com tensor completo `(4, 3, 11)` (Fase D) e medir win-rate vs Minimax(p=5) ≥ 70% e redução de divergências fatais ≥ 50% em relação ao baseline da Fase 0.

**Acceptance Scenarios**:

1. **Given** um estado com 2 cadeias longas disjuntas no mesmo tabuleiro, **When** `extrair_canais(M)` é executado, **Then** todas as caixas de ambas as cadeias devem ser marcadas com 1 no canal `em_cadeia_longa` (binário, sem canal por instância).
2. **Given** uma caixa fechada em `(r, c)`, **When** os 11 canais são computados, **Then** o canal 5 (`caixa_fechada`) deve ter valor 1 nessa célula e **todos os 6 canais estruturais (6–11) devem ter valor 0** nessa mesma célula.
3. **Given** o backend Fase D, **When** os vetores de referência `(matriz_crua, canais)` gerados pelo `analisador_estrutural_pontinhos.py` são exportados como artefato versionado, **Then** esses vetores devem ser suficientes para uma futura implementação Dart (fora do escopo desta spec) verificar paridade byte-a-byte. *Nota: o porte Dart e os testes paralelos Python↔Dart são feature(s) separada(s).*

---

### User Story 4 — Sample_weight refinado por Δ-top2 em t=12–17 (Priority: P2)

Como **desenvolvedor**, preciso reforçar o sinal de aprendizado em meio-jogo (t=12–17) de forma sutil — ~10% extra de peso médio nas amostras dessa faixa, modulado por Δ-top2 (diferença entre top1 e top2 dos scores). O pico de fatais é em t=14 (28 fatais), mas t=12 sangra com 83 moderadas (maior volume do histograma).

**Why this priority**: É um ajuste fino que só faz sentido após D estabilizar. Sample_weight muito agressivo (cap 6×) foi rejeitado por distorcer a loss em uma faixa cujas amostras são majoritariamente boas.

**Independent Test**: Após Fase E, medir divergências fatais em t ∈ [12, 17] via `analisa_divergencia_estrategica.py` e validar queda ≥ 25% em relação à Fase D, sem regressão > 2pp em qualquer faixa.

**Acceptance Scenarios**:

1. **Given** o NPZ Fase A.2 com `scores (N, 31) float32`, **When** o V6 calcula `peso[i] = clip(1 + α · Δ_top2[i], 1.0, 1.20)` para `n_tracos_antes ∈ [12, 17]` e `1.0` caso contrário, **Then** o peso médio na faixa-alvo deve ficar entre 1,05 e 1,15 e nenhum peso individual pode exceder 1,20.

---

### User Story 5 — Value head AlphaZero-style sem alterar contrato móvel (Priority: P2)

Como **desenvolvedor**, preciso adicionar uma value head ao modelo Keras (regressão de Q* normalizado em `[-1, +1]`) atuando como regularizador estrutural — multi-task learning com policy. **A value head é descartada no export TFLite** para preservar contrato e tamanho do modelo móvel.

**Why this priority**: Ataque estrutural a Categoria B (acúmulo de divergências moderadas em partidas perdidas sem fatal — 51,8% das perdas vs p=6). Custo zero em produção.

**Independent Test**: Após Fase F, comparar hash do `contrato_codificacao_pontinhos.json` com Fase D (deve ser idêntico) e medir MSE final do `value_pred` em validação (≤ 0,10 em escala normalizada).

**Acceptance Scenarios**:

1. **Given** o modelo Keras Fase F com policy + value heads, **When** o desenvolvedor exporta para TFLite, **Then** o TFLite deve manter input `(1, 4, 3, 11) int8` e única saída softmax(31), e o tamanho deve permanecer ≤ 200 KB.
2. **Given** o backend e o frontend após Fase F, **When** o teste de contrato `test_contrato_codificacao_pontinhos.py` é executado, **Then** as duas cópias do JSON devem ter hash idêntico ao da Fase D (contrato preservado).

---

### User Story 6 — Pipeline operacional de dois notebooks com sobrescrita atômica (Priority: P1)

Como **desenvolvedor**, preciso que a geração e o enriquecimento de dados estejam em **notebooks separados**: A.1 no Databricks (gera matriz crua + Q-values, sem canais estruturais), A.2 local (lê os NPZs gerados, computa os 11 canais, e regrava com sobrescrita atômica via `.tmp` + `os.replace()`). A separação permite reaproveitar os 314.323 estados únicos já gerados (`152.980` aproveitáveis após dedup, conforme §4.1.3 do PRD) sem regenerá-los no Databricks.

**Why this priority**: Gate de entrada de qualquer outra fase. Sem o NPZ enriquecido válido (com `canais` + `nomes_canais`), nenhum treino pode rodar.

**Independent Test**: Após Fase A.2, rodar um script de auditoria que: (a) verifica que cada NPZ no diretório tem `canais` shape `(N, 4, 3, 11) int8`; (b) verifica que `nomes_canais` shape `(11,) U32` é byte-a-byte igual à constante canônica `NOMES_CANAIS`; (c) deduplica todos os estados de todos os NPZs e conta ≥ 500.000 únicos.

**Acceptance Scenarios**:

1. **Given** o notebook A.1 com a tabela `COMPLEMENTO_POR_CELULA` literal embutida (§4.1.3 do PRD: 347.020 a gerar, 152.980 aproveitados, 500.000 únicos finais), **When** o desenvolvedor executa o notebook no cluster Databricks, **Then** ele NÃO deve ler nenhum arquivo externo de planejamento (CSV/JSON/pickle), e a distribuição empírica final deve ficar dentro de ±2pp das cotas D1/D1.a.
2. **Given** uma execução anterior incompleta interrompida com Ctrl+C no meio da regravação de um NPZ pelo A.2, **When** o desenvolvedor reroda o A.2, **Then** nenhum NPZ original deve ter sido corrompido (graças ao padrão `.tmp` + `os.replace()`), e a re-execução deve completar sobrescrevendo `canais` e `nomes_canais` recalculados.
3. **Given** o conjunto inicial de 58 NPZs com 344.000 estados brutos, **When** o A.1 inicializa o set de hashes, **Then** ele deve pré-popular o set com os hashes dos 314.323 estados únicos existentes para evitar colisão com o complemento gerado.

---

### Edge Cases

- **Estados quase terminais (30 traços, 1 jogada legal restante):** decisão trivial — incluir apenas a fração mínima (~10% das amostras) prevista em D1; não inflar com algo que o Minimax(p=2) já decide com certeza.
- **Estado com 2+ cadeias longas disjuntas no mesmo tabuleiro:** todas as caixas de todas as cadeias marcadas com 1 no mesmo canal `em_cadeia_longa`. A CNN convolucional separa pelo padrão espacial — não há canais por instância (justificativa §4.2 do PRD).
- **Caixa fechada em `(r, c)`:** `caixa_fechada=1` lá; **todos os canais estruturais (6–11) recebem 0** nessa célula. "Grau", "cadeia" e "loop" só fazem sentido em caixas abertas.
- **Componente conexo de caixas grau-2 com nó de grau ≥ 3 dentro do componente (estrutura "T", rara em 4×3):** tratar como cadeia complexa e atribuir a `em_cadeia_longa`.
- **Domínio diferente backend×runtime:** o dataset é gerado em `contexto_1_geracao_dataset` (domínio `{0, 1, 8, 9}` — sem -1). O app Flutter opera em `contexto_3_partidas_ao_vivo` (domínio `{-1, 0, 1, 8}`) — a normalização canônica `-1 → 1` é aplicada antes do tensor entrar no TFLite (vide contrato). O canal 5 (`caixa_fechada`) é binário em ambos os contextos pós-normalização.
- **Recalibração tardia da `COMPLEMENTO_POR_CELULA`:** se o cálculo do complemento precisar ser refeito (ex.: dataset legado mudou), o desenvolvedor deve reabrir o notebook A.1 e editar manualmente a constante. **Não há arquivo externo nem notebook de planejamento separado.**
- **Augmentação 4× estourando RAM no Colab:** aplicar como gerador `tf.data` (não materializar 2M de tensores em memória) — risco listado em §7 do PRD.
- **Ctrl+C durante o A.2:** sobrescrita atômica (`.tmp` + `os.replace`) garante que o NPZ original nunca fique corrompido pela metade.

---

## Requirements *(mandatory)*

### Functional Requirements

#### FR-A — Geração de dados (Fase A.1)

- **FR-A-01**: O sistema MUST gerar estados de tabuleiro 4×3 com Minimax(p=9) como supervisor, na faixa estendida de **5 a 30 traços preenchidos** (`[0.15·n_edges, 0.97·n_edges]`).
- **FR-A-02**: O sistema MUST aplicar **distribuição U-invertida** de pesos por bucket de traços conforme D1 do PRD: 5–11=10%, 12–17=20%, 18–23=28%, 24–28=32%, 29–30=10%, com tolerância de ±2pp na distribuição empírica final.
- **FR-A-03**: O sistema MUST aplicar o mix `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` (D1.a — modos 0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3). O modo 1 fica DESLIGADO por padrão (peso 0).
- **FR-A-04**: O sistema MUST garantir **deduplicação obrigatória** (D1.b) por hash da matriz crua (`mat.tobytes()`), pré-populando o set com hashes dos NPZs legados antes de iniciar a geração do complemento. Estados duplicados devem ser regenerados (até 20 tentativas).
- **FR-A-05**: O notebook A.1 (`Otimizacao_Topologia_Rede_V5.ipynb`) MUST conter a tabela `COMPLEMENTO_POR_CELULA` (§4.1.3 do PRD: 347.020 a gerar, 152.980 aproveitados, 500.000 únicos finais) **transcrita literal e diretamente** numa célula de parâmetros, sem ler nenhum arquivo externo de planejamento.
- **FR-A-06**: O NPZ produzido pelo A.1 MUST conter exatamente os campos `estados (N, 9, 7) int8`, `rotulos (N,) str`, `scores (N, 31) float32`, `generation_mode (N,) int8`, `labels_canonicos (31,) str`, `depth (1,) int32` — **sem `canais` ainda**.
- **FR-A-07**: O sistema MUST registrar em `docs/historico_decisoes.md` snapshot da `COMPLEMENTO_POR_CELULA` efetivamente usada como prova de auditoria.

#### FR-B — Enriquecimento de canais (Fase A.2)

- **FR-B-01**: O notebook A.2 (`Enriquece_NPZ_Com_Canais.ipynb`) MUST ler cada NPZ do diretório de entrada, computar `canais (N, 4, 3, 11) int8` chamando `extrair_canais(estado)`, e regravar o NPZ com **TODOS os campos originais + `canais` + `nomes_canais`**.
- **FR-B-02**: O array `nomes_canais` MUST ter shape `(11,) U32` e conter EXATAMENTE a sequência canônica: `("aresta_topo", "aresta_base", "aresta_esquerda", "aresta_direita", "caixa_fechada", "eh_grau3", "eh_grau2", "em_cadeia_curta", "em_cadeia_longa", "em_loop", "em_cadeia_aberta_uma_ponta")`.
- **FR-B-03**: A regravação MUST usar **sobrescrita atômica** via arquivo temporário `.tmp` + `os.replace()` para tolerar Ctrl+C sem corrupção do original.
- **FR-B-04**: O comportamento MUST ser **idempotente por sobrescrita** — se `canais`/`nomes_canais` já existirem, recalcula e substitui (sem merge, sem skip).
- **FR-B-05**: O sistema MUST fornecer um módulo `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` com função `extrair_canais(matriz_estado: np.ndarray) -> np.ndarray` retornando o tensor `(4, 3, 11) int8` na ordem canônica de FR-B-02.
- **FR-B-06**: O módulo MUST declarar a constante `NOMES_CANAIS` espelhando §4.2 do PRD; o teste `test_analisador_estrutural_pontinhos.py` MUST falhar o merge se `nomes_canais` do NPZ regravado divergir byte-a-byte dessa constante.

#### FR-C — Validação visual (gate de saída A.2)

- **FR-C-01**: O sistema MUST fornecer o script `scripts/pontinhos/validar_canais_visualmente.py` com parâmetros `--diretorio-npz`, `--qtd-tracos` (lista, opcional), `--generation-mode` (lista, opcional), `--n-amostras` (default 30), `--saida` (default `tmp_analise/validacao_canais_estruturais/`), `--seed` (default 42).
- **FR-C-02**: O script MUST gerar **1 PNG por estado sorteado** com layout fixo: cabeçalho com metadados; primeira linha com 2 visualizações da matriz crua (arestas marcadas + aresta canônica em destaque verde; heatmap de scores); segunda linha com os 5 canais geométricos como boxnets 4×3 binários; terceira linha com os 6 canais estruturais como boxnets 4×3 binários. **Cada boxnet MUST ter o nome canônico do canal como título imediatamente acima** (texto exatamente igual a `NOMES_CANAIS[k]`, ex.: `aresta_topo`, `caixa_fechada`, `em_cadeia_longa`).
- **FR-C-02a**: Cada PNG MUST ser renderizado a **150 DPI** usando uma **paleta categórica** que atribua **uma cor distinta e estável por canal** (mesma cor em todas as execuções e em todos os estados do mesmo lote); caixas com valor `1` recebem fundo preenchido na cor do canal e caixas com valor `0` ficam em branco. **Caixas fechadas (canal 5 = 1) MUST ter borda destacada** em todos os 11 boxnets para distinguir visualmente "fechada" de "aberta com grau-4 hipotético".
- **FR-C-03**: O gate de saída A.2 MUST exigir validação manual de **no mínimo 30 estados** sorteados nas faixas 12–17, 24–28 e 29–30, incluindo casos canônicos: handout, double-cross do Buchin Fig. 2, loop de 4 caixas, 2 cadeias longas disjuntas.

#### FR-D — Treino com 5 canais geométricos (Fase B)

- **FR-D-01**: O notebook V6 (`Treinamento_CNN_Arena_Sagaz_V6.ipynb`) MUST ler `canais` direto do NPZ e usar slice `canais[..., :5]` na Fase B.
- **FR-D-02**: A camada `Lambda para_grid_de_caixas` do V5 MUST ser **eliminada do grafo Keras** a partir do V6. O input do modelo passa de `(9, 7, 1)` para `(4, 3, 5)` direto.
- **FR-D-03**: O `contrato_codificacao_pontinhos.json` MUST ser atualizado para versão refletindo o novo input `(4, 3, 5)` na Fase B; cópia idêntica MUST ser propagada para o frontend (`arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`) na mesma PR.
- **FR-D-04**: A spec MUST documentar no `contrato_codificacao_pontinhos.json` a regra exata de derivação dos 5 canais geométricos a partir da matriz crua `(9, 7) int8` normalizada, suficiente para que um cliente externo (ex.: futuro porte Dart no app Flutter, **fora do escopo desta spec**) pré-compute os canais antes de chamar o TFLite. *A implementação no cliente Flutter é tratada em feature separada.*
- **FR-D-05**: A arquitetura do modelo Fase B MUST permanecer equivalente ao V5 em capacidade: stem Conv 3×3 (32) + 2 blocos residuais SeparableConv (32→48) + GAP+Flatten+Dense(96)+Dropout(0.5) + softmax(31).

#### FR-E — Augmentação 4× (Fase C)

- **FR-E-01**: O sistema MUST aplicar augmentação por simetria **4×, não 8×** (tabuleiro 4×3 não é quadrado): identidade, reflexão horizontal, reflexão vertical, rotação 180°.
- **FR-E-02**: A augmentação MUST acontecer no carregamento (V6), não na geração — não materializada em disco. Resultado em memória: 500k × 4 = 2M amostras (preferir gerador `tf.data` se RAM apertar).
- **FR-E-03**: A simetria MUST ser aplicada de forma **coerente** a TODOS os tensores associados: matriz crua, scores (com permutação de labels), label canônico, e os canais. Sob reflexão H, `aresta_esquerda ↔ aresta_direita`. Sob reflexão V, `aresta_topo ↔ aresta_base`. Sob rotação 180°, ambas as trocas. Os canais 5 e 6–11 não trocam de slot — apenas o conteúdo espacial é refletido/rotacionado.
- **FR-E-04**: O sistema MUST fornecer `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py` com tabelas de permutação de labels para as 4 simetrias, validadas em teste unitário.

#### FR-F — Treino com 11 canais (Fase D)

- **FR-F-01**: O V6 MUST passar a usar **todos os 11 canais** (`canais[..., :11]`) na Fase D. Input do modelo: `(4, 3, 11)`.
- **FR-F-02**: O `contrato_codificacao_pontinhos.json` MUST ser atualizado para nova versão refletindo input `(4, 3, 11)` na Fase D, documentando a regra de derivação dos 11 canais a partir da matriz crua. Cópia idêntica para o frontend na mesma PR.
- **FR-F-03**: O backend MUST entregar, junto com o contrato versão Fase D, um **conjunto de vetores de referência** `(matriz_crua, canais (4,3,11) int8)` em artefato versionado (sugestão: `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` ou `.npz`) cobrindo no mínimo: estado vazio, caixa fechada, double-cross do Buchin Fig. 2, loop de 4 caixas, 2 cadeias longas disjuntas, half-open chain, e ≥ 20 estados sorteados em t∈{14, 17, 24, 29}. Esses vetores servem como ground truth para qualquer cliente externo verificar paridade byte-a-byte. *O porte Dart e seu teste paralelo são tratados em feature separada — fora do escopo desta spec.*

#### FR-G — Sample_weight refinado (Fase E)

- **FR-G-01**: O V6 MUST calcular `Δ_top2[i] = scores[i, top1] − scores[i, top2]` em caixas líquidas. Empate em top1 ⇒ `Δ_top2 = 0`.
- **FR-G-02**: O V6 MUST aplicar `peso[i] = clip(1 + α · Δ_top2[i], 1.0, 1.20)` SOMENTE para `n_tracos_antes ∈ [12, 17]`; demais amostras recebem peso `1.0`.
- **FR-G-03**: α MUST ser calibrado para que o peso médio na faixa-alvo fique entre 1,05 e 1,15. Sugestão inicial α=0,03.

#### FR-H — Value head (Fase F)

- **FR-H-01**: O modelo Keras Fase F MUST adicionar segunda saída `value_pred`: `Conv 1×1 (16) → Flatten → Dense(64, relu) → Dense(1, tanh)` ramificando do último bloco residual.
- **FR-H-02**: O `value_target` MUST ser `score_max / 6.0` clipado em `[-1, +1]`.
- **FR-H-03**: A loss conjunta MUST ser `KLD(policy) + λ · MSE(value)` com `λ ∈ [0.1, 0.3]` (sugestão inicial 0,1). O `sample_weight` da Fase E aplica APENAS à policy loss; a value loss usa peso uniforme 1,0.
- **FR-H-04**: O export TFLite MUST descartar a value head — apenas a policy head vai para o app. Hash do contrato MUST permanecer idêntico ao da Fase D.

#### FR-I — Versionamento e contrato

- **FR-I-01**: Cada fase MUST produzir TFLite versionado: `pontinhos_pequeno_p9_faseB.tflite`, `_faseC.tflite`, `_faseD.tflite`, `_faseE.tflite`, `_faseF.tflite`. (Fases G/H condicionais produzem `_faseG.tflite`, `_faseH.tflite` se executadas.)
- **FR-I-02**: O contrato MUST mudar em DUAS ocasiões: Fase B (input `(4, 3, 5)`) e Fase D (input `(4, 3, 11)`). A partir da Fase F, contrato é PRESERVADO.
- **FR-I-03**: A regra do `CLAUDE.md` MUST ser respeitada: alteração no JSON ⇒ cópia idêntica para o frontend NA MESMA RESPOSTA/PR.
- **FR-I-04**: Cada fase MUST registrar entrada datada em `docs/historico_decisoes.md` com win-rates, métricas por faixa (Seção 2.5 do PRD) e diff de configuração. **A entrada é redigida manualmente pelo desenvolvedor** a partir dos resultados dos notebooks executados em ambiente externo; **não há exigência de logging estruturado, MLflow, TensorBoard ou dashboards.** Cada notebook decide ad-hoc seu próprio formato de saída.

#### FR-J — Não-regressão e gates

- **FR-J-01**: Entre fases consecutivas, **nenhum win-rate** (vs Minimax p=3, p=5, p=6) pode cair > 3pp.
- **FR-J-02**: Entre fases consecutivas, **nenhuma faixa de preenchimento** (5–11, 12–17, 18–23, 24–28, 29–30) pode regredir > 2pp em accuracy.
- **FR-J-03**: A faixa **29–30 traços** MUST atingir top-1 accuracy ≥ 95% a partir da Fase B; abaixo disso o gate da fase falha mesmo se win-rate global subir.
- **FR-J-04**: Os testes obrigatórios MUST passar no CI: `test_contrato_codificacao_pontinhos.py`, `test_analisador_estrutural_pontinhos.py`, `test_permutacoes_simetria_pontinhos.py`.

### Non-Functional Requirements

- **NFR-01 (Tamanho do modelo móvel):** TFLite final ≤ **200 KB** em todas as fases (hoje ~100 KB; folga grande para os canais extras).
- **NFR-02 (Latência mobile):** inferência ≤ **5 ms/jogada** em smartphone alvo (hoje ~0,1 ms — folga grande).
- **NFR-03 (Tempo de geração no Databricks):** complemento de ~347k amostras com Minimax(p=9) ≤ **4 horas**, usando a configuração de cluster/paralelismo do V4 atual sem otimização adicional dentro do escopo desta spec. Estimativa §4.1.3 do PRD (~1,34 h em 12 workers, pior caso ~1,7 h) é referência informativa; ajustes finos de workers, batch size ou timeout são feitos ad-hoc no Databricks pelo desenvolvedor no momento da execução.
- **NFR-04 (Sincronização do contrato):** hash do `contrato_codificacao_pontinhos.json` no backend MUST ser **byte-a-byte idêntico** ao do frontend a cada PR. Teste de contrato falha o merge se divergir.
- **NFR-05 (Reprodutibilidade visual):** o script de validação visual MUST aceitar `--seed` para reproduzir o mesmo sorteio em execuções repetidas.
- **NFR-06 (Atomicidade da regravação):** Ctrl+C em qualquer ponto do A.2 NUNCA pode deixar um NPZ corrompido (`.tmp` + `os.replace()`).
- **NFR-07 (Auditabilidade do dataset):** o NPZ MUST ser auto-descritivo via `nomes_canais`; qualquer ferramenta consegue interpretar o tensor `canais` sem consultar este `spec.md` ou o PRD.

### Key Entities

- **Estado bruto (`estados[i]`):** matriz `(9, 7) int8` no domínio `{0, 1, 8, 9}` (contexto_1_geracao_dataset). Codifica arestas (`9` jogada / `0` livre), pontos fixos (`8`) e caixas fechadas (`1`).
- **Tensor de canais (`canais[i]`):** `(4, 3, 11) int8` binário, com 5 canais geométricos (1–5) + 6 estruturais (6–11) na ordem canônica de FR-B-02.
- **Vetor de scores (`scores[i]`):** `(31,) float32` com Q-values do Minimax(p=9) por aresta canônica. Inválidas recebem `-1e9`.
- **Label canônico (`rotulos[i]`):** string formato `H_r_c` ou `V_r_c` indicando a melhor aresta segundo o supervisor.
- **Modo de geração (`generation_mode[i]`):** `int8` ∈ {0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3}. Modo 1 fica DESLIGADO em A.1 (peso 0).
- **NOMES_CANAIS:** constante `(11,) U32` espelhada em código Python (`analisador_estrutural_pontinhos.py`), no NPZ enriquecido (`nomes_canais`) e em §4.2 do PRD. Validada cruzadamente.
- **COMPLEMENTO_POR_CELULA:** dicionário `{gen_mode: {bucket_tracos: cota}}` literal na célula de parâmetros do A.1, totalizando 347.020 a gerar.
- **Contrato de codificação:** `contrato_codificacao_pontinhos.json` (backend + cópia idêntica no frontend) declarando o input do TFLite, a regra de derivação de canais e a normalização de domínio.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### Categoria A — táticas

- **SC-A-01**: Total de erros reais (`analisa_padrao_erros.py`) cai de 505 (baseline) para **≤ 80**.
- **SC-A-02**: Distribuição balanceada nos pares "deveria→jogou": **nenhum par representa > 5%** do total de erros.
- **SC-A-03**: Erros em estados com uma única caixa grau-3 caem de 496 (98% do baseline) para **≤ 30**.

#### Categoria B — estratégicas

- **SC-B-01**: Divergências fatais por partida (`analisa_divergencia_estrategica.py`) caem **≥ 50%** em relação ao baseline da Fase 0 (de 0,68 para ≤ 0,34).
- **SC-B-02**: Fração de partidas perdidas com fatal precoce (≤ 25 traços) cai de **16,8%** para **≤ 8%**.
- **SC-B-03**: Fração de partidas perdidas sem nenhum fatal (acúmulo de moderadas) cai de **51,8%** para **≤ 25%**.

#### Win-rates primários (200 partidas por adversário)

- **SC-W-01**: Vitórias vs Minimax(p=3) ≥ **80%** (baseline 54,5%).
- **SC-W-02**: Vitórias vs Minimax(p=5) ≥ **70%** (baseline 42,0%).
- **SC-W-03**: Vitórias vs Minimax(p=6) ≥ **60%** (baseline 38,0%).
- **SC-W-04**: Vitórias vs Minimax(p=1) ≥ **92%** (não regredir).

#### Accuracy por faixa de preenchimento (Seção 2.5 do PRD)

- **SC-F-01**: Faixa 5–11 (abertura): top-5 accuracy ≥ 40%.
- **SC-F-02**: Faixa 12–17 (crítica meio): top-3 accuracy ≥ 80%.
- **SC-F-03**: Faixa 18–23 (2ª metade): top-3 accuracy ≥ 95%.
- **SC-F-04**: Faixa 24–28 (fase quente): top-1 accuracy ≥ 80%.
- **SC-F-05**: Faixa 29–30 (final): top-1 accuracy **≥ 95%** — gate forte; abaixo disso a fase falha.

#### Dataset

- **SC-D-01**: NPZ entregue à Fase B contém **≥ 500.000 estados únicos** (deduplicação por `mat.tobytes()`).
- **SC-D-02**: Distribuição empírica final dentro de **±2pp** das cotas D1 (faixa de traços) e D1.a (gen_mode).
- **SC-D-03**: Mix gen_mode final: 0=5%, 1=0%, 2=40%, 3=55%.
- **SC-D-04**: Campo `canais` shape `(N, 4, 3, 11) int8` presente em **todos os NPZs** do diretório de dados.
- **SC-D-05**: Campo `nomes_canais` shape `(11,) U32` byte-a-byte igual à constante canônica `NOMES_CANAIS` em todos os NPZs.
- **SC-D-06**: Snapshot da `COMPLEMENTO_POR_CELULA` efetivamente usada em A.1 registrado em `docs/historico_decisoes.md`.

#### Operacionais

- **SC-O-01**: TFLite final ≤ 200 KB.
- **SC-O-02**: Inferência mobile ≤ 5 ms/jogada.
- **SC-O-03**: Geração 500k em Databricks ≤ 4 horas.
- **SC-O-04**: Hash do contrato backend = hash do contrato frontend a cada PR.
- **SC-O-05**: Pipeline backend completo (geração + enriquecimento + treino + avaliação + export TFLite + publicação do contrato e dos vetores de referência) executável end-to-end. *Integração no app Flutter é entregue em feature separada e não conta como SC desta spec.*
- **SC-O-06**: Testes obrigatórios passam no CI (FR-J-04).

---

## Atores e fluxos

### Ator: Desenvolvedor de IA do Arena Sagaz

- **Fluxo Fase A.1 (Databricks):** abre o notebook `Otimizacao_Topologia_Rede_V5.ipynb`, confere a `COMPLEMENTO_POR_CELULA` literal na célula de parâmetros (já preenchida com §4.1.3), executa o cluster, monitora geração até 347.020 amostras únicas; o set de hashes é pré-populado com os 314.323 estados legados antes da geração começar.
- **Fluxo Fase A.2 (local):** roda `Enriquece_NPZ_Com_Canais.ipynb` apontando para `dados/profundidade_minmax_9`; o notebook sobrescreve in-place via `.tmp` + `os.replace()`. Em seguida executa `validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30` e revisa manualmente os 30 PNGs.
- **Fluxo Fases B–F (Colab):** roda `Treinamento_CNN_Arena_Sagaz_V6.ipynb` com slice apropriado dos canais, exporta TFLite versionado, registra entrada em `docs/historico_decisoes.md`, atualiza contrato (Fases B e D) propagando cópia idêntica para o frontend na mesma PR.

### Ator: CI

- **Antes do merge:** executa `test_contrato_codificacao_pontinhos.py`, `test_analisador_estrutural_pontinhos.py`, `test_permutacoes_simetria_pontinhos.py`. Compara hash do contrato backend×frontend; falha o merge se divergirem.

### Ator: App Flutter em runtime *(consumidor downstream — fora do escopo desta spec)*

O app Flutter consome os artefatos backend (TFLite versionado, `contrato_codificacao_pontinhos.json`, vetores de referência dos canais) em **feature separada**. A spec atual NÃO entrega:

- O porte Dart do `analisador_estrutural_pontinhos.py`.
- O carregamento dinâmico do TFLite no app.
- O teste paralelo Python↔Dart de paridade byte-a-byte.

A spec atual entrega o que **habilita** essa integração: contrato sincronizado backend↔frontend (regra do `CLAUDE.md`), TFLite estável, e vetores de referência suficientes para validar qualquer porte futuro.

---

## Glossário (espelha §9 do PRD)

- **Caixa grau-N:** caixa com N arestas vizinhas já ocupadas.
- **Cadeia (chain):** componente conexo de caixas grau-2 onde os nós formam um caminho.
- **Cadeia curta:** cadeia de comprimento 1–2 caixas.
- **Cadeia longa:** cadeia de comprimento ≥ 3 caixas.
- **Loop (ciclo):** componente conexo de caixas grau-2 onde todos os nós têm grau 2 internamente — formam um ciclo fechado.
- **Half-open chain:** cadeia onde apenas uma das pontas conecta a uma caixa grau-3 (capturável).
- **Closed chain:** cadeia onde ambas as pontas conectam a caixas grau-3.
- **Loony move:** abrir uma cadeia longa ou loop quando há outras opções — geralmente sub-ótimo.
- **Double-dealing move:** abrir mão de 2 caixas (em chain) ou 4 (em loop) para passar a vez ao oponente e forçá-lo a abrir a próxima cadeia.
- **Double-cross move:** o movimento que fecha 2 caixas de uma vez no fim de um double-dealing.
- **Loony endgame:** estado onde toda jogada legal é loony — tipicamente após todas as caixas grau-≤1 terem sido jogadas.
- **In control:** o jogador que **não** abre cadeias — geralmente vence o loony endgame.

---

## Assumptions

- Os 314.323 estados únicos legados em `dados/profundidade_minmax_9/` são considerados confiáveis e seus hashes são reaproveitáveis no set de deduplicação do A.1 (sem rerodar Minimax).
- A Fase A.1 herda a configuração e os parâmetros do notebook V4 atual (paralelismo, batch sizes, checkpointing). **Otimização de cluster Databricks está fora do escopo desta spec** — ajustes de workers/timeout/batch são feitos ad-hoc no próprio Databricks pelo desenvolvedor no momento da execução. O orçamento de tempo aceito é até 4h (NFR-03), com folga ampla sobre a estimativa de 1,34–1,7 h em 12 workers.
- **Os notebooks rodam em ambiente externo** (Databricks para A.1, máquina local para A.2, Colab para V6). O desenvolvedor traz os resultados manualmente para `docs/historico_decisoes.md`. Não há padrão obrigatório de logging estruturado, MLflow, TensorBoard ou dashboards externos.
- O ambiente de treino é Colab T4 (mantido do V5); ajustes para outro hardware não estão no escopo.
- **Implementação no app Flutter está fora do escopo desta spec.** A diretriz canônica registrada para a futura feature de integração mobile é Dart puro (lógica < 200 linhas, BFS em ≤ 12 nós), mas a decisão definitiva é tomada na spec dedicada ao Flutter. Esta spec entrega apenas o ground truth Python + contrato + vetores de referência.
- O cap inferior de comprimento de cadeia "longa" é **≥ 3** (atual; confirmado em Clarifications 2026-05-07). Separação adicional `cadeia_media (3) vs longa (≥ 4)` está fora do escopo desta feature; reavaliar apenas se um experimento dedicado evidenciar regressão atribuível a cadeias de comprimento exatamente 3.
- O `analisa_divergencia_estrategica.py` e o `analisa_padrao_erros.py` são considerados estáveis e referência para todos os gates da feature.
- Branch alvo `004-melhoria-geracao-dados-cnn` é assumida; a criação de branch git não é coberta por esta especificação (esta máquina não tem acesso ao GIT).

---

## Pendências/Perguntas (para `/speckit-clarify`)

> O PRD lista 4 pendências em §10. Listadas aqui literalmente, com possíveis ramificações no escopo. Resolver via `/speckit-clarify` antes de `/speckit-plan` se afetarem o plano.

1. ~~**[limites operacionais reais do Databricks]**~~ → **Resolvido em 2026-05-07** (ver Clarifications): Fase A.1 herda parâmetros do V4 atual; otimização de cluster fica fora do escopo da spec, ajustes ad-hoc no Databricks pelo desenvolvedor.
2. ~~**[formato exato dos PNGs de validação]**~~ → **Resolvido em 2026-05-07** (ver Clarifications): 150 DPI, paleta categórica com cor estável por canal, borda destacada para caixas fechadas em todos os boxnets, título com nome canônico do canal acima de cada boxnet. — o §4.4 do PRD especifica layout com 1 PNG por estado (matriz crua dupla + 11 boxnets); falta definir resolução fixa (DPI), paleta de cores por canal (cor única vs gradiente) e se boxnets fechadas devem ter borda destacada. Padrões visuais consistentes facilitam revisão em escala.
3. ~~**[política de versionamento TFLite no app Flutter]**~~ → **Resolvido em 2026-05-07** (ver Clarifications): integração no app Flutter está fora do escopo desta spec. Política de versionamento TFLite no app é decisão da feature dedicada ao Flutter. Esta spec apenas garante que cada fase produz TFLite versionado em arquivo nomeado distintamente (FR-I-01) e que o contrato é estável a partir da Fase D.
4. ~~**Implementação do analisador no Flutter (Fase D)**~~ → **Resolvido em 2026-05-07** (ver Clarifications): Dart puro registrado como diretriz canônica, **mas a implementação Flutter está fora do escopo desta spec**. Esta spec entrega o ground truth Python + contrato + vetores de referência; o porte Dart é feature separada.
5. **Calibração de λ na Fase F:** grid search vs Bayesian optimization vs valor fixo 0,1. Decisão protelada até início da Fase F.
6. ~~**Limite mínimo de cadeia "longa"**~~ → **Resolvido em 2026-05-07** (ver Clarifications): manter `cadeia_longa = ≥3` (canal único, K=11 inalterado). Reavaliar apenas em iteração futura se experimento dedicado mostrar regressão atribuível a cadeias de comprimento exatamente 3.

---

**Fim do `spec.md`.** Pronto para servir como input ao `/speckit-clarify` (resolver pendências 1–3) e em seguida `/speckit-plan`.
