---
description: "Tasks para a feature 004 — Melhoria da geração de dados e arquitetura da CNN do Jogo dos Pontinhos"
---

# Tasks: Melhoria da geração de dados e arquitetura da CNN do Jogo dos Pontinhos

**Input**: Design documents em `/specs/004-melhoria-geracao-dados-cnn/`
**Prerequisites**: `plan.md`, `spec.md`, `PRD.md`, `research.md`, `data-model.md`, `contracts/canais_estruturais.md`, `contracts/npz_schema.md`, `quickstart.md`, `CLAUDE.md` (raiz)

**Tests**: testes unitários são obrigatórios para o analisador estrutural (Fase A.2), permutações de simetria (Fase C) e contrato de codificação (Fases B, D, F). Demais validações são via auditoria de notebook + scripts de avaliação.

**Organização**: Tasks são agrupadas por **fase sequencial** (A.1 → A.2 → B → C → D → E → F → G/H). O bloco da fase seguinte só começa após o **gate de saída** da fase anterior bater. Dentro de uma fase, tarefas com `[P]` podem rodar em paralelo se tocam arquivos diferentes e não dependem uma da saída da outra.

## Format: `- [ ] [TaskID] [P?] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência interna na fase)
- **blockedBy**: dependência explícita dentro da mesma fase
- **Gate de saída**: comando, teste ou métrica que prova que a tarefa terminou

---

## Fase A.1 — Geração no Databricks (notebook V5)

**Objetivo**: produzir NPZ com **500.000 estados únicos** cobrindo 5–30 traços (distribuição U-invertida), preservando os 314.323 únicos legados como núcleo invariante e completando o restante com `gen_mode` declarado por estado.

**Gate da fase**: NPZ aprovado em auditoria — 500.000 estados únicos confirmados, distribuição empírica dentro das tolerâncias da §4.1.3 do PRD, mix `gen_mode` declarado, snapshot registrado em `docs/historico_decisoes.md`.

- [x] T-A1-001 Criar `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb` partindo de uma cópia byte-a-byte do V4 atual; alterar apenas o título e a célula de versão. **Gate**: notebook abre no Databricks sem erro de parse e roda end-to-end com os mesmos parâmetros do V4 (smoke run).
- [x] T-A1-002 Embutir literal `COMPLEMENTO_POR_CELULA` (mapa traços → quota) da §4.1.3 do PRD na célula de parâmetros do V5, em `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`. **blockedBy**: T-A1-001. **Gate**: célula importável; soma das quotas == 500.000 − 314.323; valores idênticos ao PRD §4.1.3 verificados por inspeção.
- [x] T-A1-003 [P] Embutir constantes `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` e `FAIXA_TRACOS = (0.15, 0.97)` na mesma célula de parâmetros de `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`. **blockedBy**: T-A1-001. **Gate**: `assert sum(STRAT_WEIGHTS) == 1.0`; `FAIXA_TRACOS` propagada para todas as funções de amostragem do notebook.
- [x] T-A1-004 Implementar pré-população do `set` de hashes com os 314.323 estados únicos do NPZ legado **antes** do laço de geração no V5 (em `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`). **blockedBy**: T-A1-002, T-A1-003. **Gate**: `len(hashes_iniciais) == 314_323` impresso na célula; verificar que o laço só gera estados novos (contador de duplicatas exibido).
- [x] T-A1-005 Implementar célula de auditoria pós-execução em `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`: contar únicos totais, distribuição empírica por nº de traços, mix de `gen_mode` por faixa. **blockedBy**: T-A1-004. **Gate**: 500.000 únicos confirmados; histograma de traços corresponde a `COMPLEMENTO_POR_CELULA + legado`; mix `gen_mode` impresso.
- [x] T-A1-006 [P] Registrar entrada datada (2026-05-07 ou data corrente da execução) em `docs/historico_decisoes.md` consolidando: parâmetros usados, distribuição final, tamanho do NPZ, hashes verificados. **blockedBy**: T-A1-005. **Gate**: arquivo contém seção com data, contexto, decisão, alternativas consideradas, motivo (formato exigido pelo `CLAUDE.md`).

**Checkpoint Fase A.1**: NPZ com 500.000 únicos disponível em path conhecido; auditoria registrada; pode-se iniciar Fase A.2.

---

## Fase A.2 — Enriquecimento local (11 canais estruturais)

**Objetivo**: enriquecer cada NPZ produzido em A.1 com o array `canais (N, 4, 3, 11) int8` derivado da matriz crua, junto do array `nomes_canais` (string array com 11 nomes canônicos), preservando todas as chaves anteriores. Sobrescrita atômica.

**Gate da fase**: todos os NPZs do diretório enriquecidos com sucesso; teste do analisador verde; ≥ 30 PNGs visualmente validados pelo desenvolvedor; auditoria de `nomes_canais` byte-a-byte idêntica em todos os arquivos; `docs/jogo_pontinhos/guia_geracao_dados.md` atualizado; entrada D2/D3/D4 em `docs/historico_decisoes.md`.

- [x] T-A2-001 Criar `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` com constante pública `NOMES_CANAIS` (lista de 11 strings na ordem do PRD §4.2) e função `extrair_canais(M: np.ndarray) -> np.ndarray` retornando `(4, 3, 11) int8` conforme algoritmo de `contracts/canais_estruturais.md`. **Gate**: `python -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais, NOMES_CANAIS; print(len(NOMES_CANAIS))"` imprime `11`.
- [x] T-A2-002 Criar `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` cobrindo: (a) domínio binário `{0,1}` em todos os canais; (b) exclusão mútua canal 4 (`caixa_fechada`) vs canais 5–10 (graus/cadeias/loops); (c) coerência sob simetria (canais transformam coerentemente sob ref_H, ref_V, R180); (d) casos canônicos: tabuleiro vazio, caixa fechada simples, **double-cross do Buchin**, **loop de 4 caixas**, **half-open chain**. **blockedBy**: T-A2-001. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v` 100% verde.
- [x] T-A2-003 Criar `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` que: lê NPZ de entrada, computa `canais` chamando `extrair_canais` para cada estado, escreve novo NPZ com sobrescrita **atômica** via `tmp_path = path + '.tmp'` + `os.replace(tmp_path, path)`; preserva todas as chaves originais; adiciona `nomes_canais`. **blockedBy**: T-A2-001. **Gate**: rodando o notebook sobre um NPZ de teste, o arquivo final contém todas as chaves originais + `canais` (dtype int8, shape `(N, 4, 3, 11)`) + `nomes_canais` (shape `(11,)`); nenhum `.tmp` remanescente.
- [x] T-A2-004 [P] Criar `scripts/pontinhos/validar_canais_visualmente.py` com CLI `--qtd-tracos N1 N2 ... --n-amostras K`, gerando PNGs a 150 DPI, paleta categórica estável (uma cor por canal, fixa entre execuções), borda destacada em boxnets de caixas fechadas, título acima de cada boxnet com o nome canônico exatamente igual ao item de `NOMES_CANAIS`. **blockedBy**: T-A2-001. **Gate**: `python scripts/pontinhos/validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30` produz 30 PNGs válidos no diretório de saída.
- [ ] T-A2-005 Validação visual manual de **≥ 30 estados** distribuídos nas faixas `t∈[12,17]`, `t∈[24,28]` e `t∈[29,30]` usando os PNGs gerados em T-A2-004. **blockedBy**: T-A2-003, T-A2-004. **Gate**: desenvolvedor confirma na entrada de `docs/historico_decisoes.md` que os canais 0–10 estão coerentes com a matriz crua nos casos inspecionados (assinatura textual).
- [ ] T-A2-006 Auditoria do diretório de NPZs enriquecidos: verificar que `nomes_canais` é **byte-a-byte idêntico** em todos os arquivos; computar e registrar hashes pré e pós enriquecimento (matriz crua, scores e rótulo devem ter hash inalterado; `canais` e `nomes_canais` são chaves novas). **blockedBy**: T-A2-003. **Gate**: célula de auditoria no notebook ou script equivalente imprime `OK` para todos os arquivos; relatório anexado à entrada de `docs/historico_decisoes.md`.
- [x] T-A2-007 [P] Atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` documentando o novo fluxo A.1 (V5 no Databricks) + A.2 (notebook de enriquecimento local), com comandos, paths e ordem de execução. **blockedBy**: T-A2-003. **Gate**: leitor consegue reproduzir o fluxo do zero a partir do guia, sem precisar abrir o PRD.
- [x] T-A2-008 Adicionar entrada datada em `docs/historico_decisoes.md` consolidando D2 (canal `cadeia_longa = ≥3` único, K=11), D3 (sobrescrita atômica via `.tmp` + `os.replace`) e D4 (paleta visual estável + borda em fechadas). **blockedBy**: T-A2-005, T-A2-006. **Gate**: entrada presente com data, contexto, decisão, alternativas consideradas, motivo.

**Checkpoint Fase A.2**: NPZs enriquecidos prontos para consumo pelo treino; pode-se iniciar Fase B.

---

## Fase B — Treino com 5 canais geométricos

**Objetivo**: substituir a Lambda interna `para_grid_de_caixas` por leitura direta de `canais[..., :5]` do NPZ; treinar e exportar primeiro TFLite da nova arquitetura.

**Gate da fase**: SC-F-05 (top-1 ≥ 95% na faixa 29–30 traços) atendido; erros táticos ≤ 250 em `analisa_padrao_erros.py`; nenhum win-rate vs Minimax(p=3/5/6) cai > 3pp vs baseline; TFLite ≤ 200 KB; latência ≤ 5 ms/jogada; teste do contrato verde; entrada em `docs/historico_decisoes.md`.

- [ ] T-B-001 Criar `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` baseado no V5 atual de treino, eliminando a camada Lambda `para_grid_de_caixas` e lendo `canais[..., :5]` diretamente do NPZ; introduzir constante de notebook `SLICE_CANAIS = slice(0, 5)` e `INPUT_SHAPE = (4, 3, 5)`. **Gate**: notebook abre, executa a célula de carga e imprime `X_train.shape == (..., 4, 3, 5)`.
- [ ] T-B-002 Atualizar `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` para refletir input `(4, 3, 5)` (shape, número de canais, lista parcial de `nomes_canais` 0–4). **Gate**: JSON válido; campo de shape == `[4, 3, 5]`.
- [ ] T-B-003 **Copiar `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` byte-a-byte** para `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` na mesma PR. **blockedBy**: T-B-002. **Gate**: `diff` entre os dois arquivos retorna vazio (0 bytes de diferença).
- [ ] T-B-004 Rodar `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py -v`. **blockedBy**: T-B-002, T-B-003. **Gate**: teste 100% verde (cópia idêntica backend↔frontend; helper Python aplica regras do JSON; tensor pós-normalização ⊂ `{0,1}`).
- [ ] T-B-005 Treinar a CNN em `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` com `SLICE_CANAIS = slice(0, 5)` e exportar `modelos/pontinhos_pequeno_p9_faseB.tflite`. **blockedBy**: T-B-001, T-B-004. **Gate**: arquivo `.tflite` gerado; `os.path.getsize` ≤ 200 KB.
- [ ] T-B-006 Avaliar `pontinhos_pequeno_p9_faseB.tflite` via `notebooks/jogo_pontinhos/Avaliacao_CNN_vs_Minimax.ipynb` em **200 partidas × 3 adversários (p=3, p=5, p=6)**. **blockedBy**: T-B-005. **Gate**: relatório de win-rates por adversário coletado pelo desenvolvedor.
- [ ] T-B-007 [P] Rodar `gerador_dados/jogo_pontinhos/analisa_padrao_erros.py` e `gerador_dados/jogo_pontinhos/analisa_divergencia_estrategica.py` sobre o log das 600 partidas da T-B-006. **blockedBy**: T-B-006. **Gate**: erros táticos totais ≤ 250; relatório dos pares "deveria→jogou" coletado.
- [ ] T-B-008 [P] Medir latência média por jogada do `pontinhos_pequeno_p9_faseB.tflite` em CPU (notebook auxiliar ou célula no V6). **blockedBy**: T-B-005. **Gate**: latência ≤ 5 ms/jogada confirmada.
- [ ] T-B-009 Verificar gates da Fase B: SC-F-05 (top-1 faixa 29–30 ≥ 95%); erros táticos ≤ 250; nenhum win-rate cai > 3pp vs baseline; TFLite ≤ 200 KB; latência ≤ 5 ms. **blockedBy**: T-B-005, T-B-006, T-B-007, T-B-008. **Gate**: todos os critérios atendidos; se algum falhar, parar a fase e investigar.
- [ ] T-B-010 Atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` com o novo fluxo de treino V6 (5 canais, sem Lambda). **blockedBy**: T-B-001. **Gate**: guia reflete a nova arquitetura.
- [ ] T-B-011 Adicionar entrada datada em `docs/historico_decisoes.md` com tabela **Baseline vs Fase B**: win-rates por adversário (p=3/5/6) e accuracy por faixa (§2.5 do PRD). **blockedBy**: T-B-009. **Gate**: entrada presente com data, contexto, decisão, alternativas, motivo + tabela.

**Checkpoint Fase B**: TFLite v Fase B aprovado; pode-se iniciar Fase C.

---

## Fase C — Augmentação 4× por simetria

**Objetivo**: eliminar viés posicional de borda externa via augmentação 4× (identidade + ref_H + ref_V + R180) coerente entre matriz crua, canais, scores e rótulo.

**Gate da fase**: nenhum par "deveria→jogou" individual > 5% do total de erros; nenhum win-rate cai vs Fase B; faixa 29–30 ainda ≥ 95%; entrada em `docs/historico_decisoes.md`.

- [ ] T-C-001 Criar `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py` com as 4 transformações (identidade, ref_H, ref_V, R180) aplicáveis a: matriz crua, tensor de canais `(4,3,11)`, vetor de scores e índice de rótulo; incluindo a permutação coerente `aresta_esquerda↔aresta_direita` em ref_H e `aresta_topo↔aresta_base` em ref_V. **Gate**: módulo importável; expõe função `aplicar_simetria(estado, sym_id) -> estado`.
- [ ] T-C-002 Criar `tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py` cobrindo: (a) idempotência (aplicar identidade não muda nada); (b) composição (R180 == ref_H ∘ ref_V); (c) coerência **canais ↔ matriz crua ↔ scores ↔ rótulo** sob cada simetria. **blockedBy**: T-C-001. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py -v` 100% verde.
- [ ] T-C-003 Ativar bloco de augmentação no `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` com flag `USAR_AUGMENTACAO = True`, ainda com `SLICE_CANAIS = slice(0, 5)`; importar e usar `permutacoes_simetria_pontinhos`. **blockedBy**: T-C-001, T-C-002. **Gate**: célula imprime tamanho do dataset 4× maior que o original.
- [ ] T-C-004 Treinar e exportar `modelos/pontinhos_pequeno_p9_faseC.tflite`. **blockedBy**: T-C-003. **Gate**: arquivo gerado; tamanho ≤ 200 KB.
- [ ] T-C-005 Avaliar `_faseC.tflite` via `Avaliacao_CNN_vs_Minimax.ipynb` (200 partidas × p=3/5/6). **blockedBy**: T-C-004. **Gate**: relatório coletado.
- [ ] T-C-006 Rodar `analisa_padrao_erros.py` e `analisa_divergencia_estrategica.py` sobre o log da T-C-005. **blockedBy**: T-C-005. **Gate**: tabela de pares "deveria→jogou" coletada.
- [ ] T-C-007 Verificar gates da Fase C: nenhum par "deveria→jogou" > 5%; nenhum win-rate cai vs Fase B; faixa 29–30 ≥ 95%. **blockedBy**: T-C-005, T-C-006. **Gate**: todos os critérios atendidos.
- [ ] T-C-008 Adicionar entrada datada em `docs/historico_decisoes.md` com tabela **Fase B vs Fase C** (win-rates + accuracy por faixa + top-5 pares "deveria→jogou"). **blockedBy**: T-C-007. **Gate**: entrada presente.

**Checkpoint Fase C**: viés posicional eliminado; pode-se iniciar Fase D.

---

## Fase D — 11 canais + contrato v2 + vetores de referência

**Objetivo**: ativar os 11 canais estruturais; consolidar contrato v2 backend↔frontend; gerar vetores de referência para futuro porte Dart.

**Gate da fase**: vitórias vs p=5 ≥ 70%; erros totais ≤ 80; divergências fatais por partida caem ≥ 50% vs baseline; faixa 29–30 ≥ 95%; teste do contrato verde; cópia byte-a-byte para o frontend; entrada em `docs/historico_decisoes.md`.

- [ ] T-D-001 Alternar `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` para `SLICE_CANAIS = slice(0, 11)` e `INPUT_SHAPE = (4, 3, 11)`. **Gate**: célula de carga imprime `X_train.shape == (..., 4, 3, 11)`.
- [ ] T-D-002 Atualizar `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` para versão refletindo input `(4, 3, 11)` com lista completa de `NOMES_CANAIS` (0–10). **Gate**: JSON válido; shape == `[4, 3, 11]`; lista de nomes contém 11 entradas idênticas ao algoritmo de `contracts/canais_estruturais.md`.
- [ ] T-D-003 **Copiar `contrato_codificacao_pontinhos.json` byte-a-byte** para `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` na mesma PR. **blockedBy**: T-D-002. **Gate**: `diff` retorna vazio.
- [ ] T-D-004 Rodar `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py -v`. **blockedBy**: T-D-002, T-D-003. **Gate**: teste 100% verde.
- [ ] T-D-005 [P] Gerar `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` cobrindo casos canônicos (vazio, caixa fechada, double-cross, loop 4 caixas, half-open chain) **+ ≥ 20 estados sorteados em t ∈ {14, 17, 24, 29}** (5 por traço). Cada entrada: matriz crua + tensor `canais (4,3,11) int8` esperado. **blockedBy**: T-A2-001 (depende do analisador da Fase A.2). **Gate**: arquivo contém ≥ 25 entradas; carregando e revalidando com `extrair_canais`, todos os tensores batem byte-a-byte.
- [ ] T-D-006 Treinar e exportar `modelos/pontinhos_pequeno_p9_faseD.tflite`. **blockedBy**: T-D-001, T-D-004. **Gate**: arquivo gerado; ≤ 200 KB.
- [ ] T-D-007 Avaliar `_faseD.tflite` via `Avaliacao_CNN_vs_Minimax.ipynb` (200 partidas × p=3/5/6) + `analisa_padrao_erros.py` + `analisa_divergencia_estrategica.py`. **blockedBy**: T-D-006. **Gate**: relatórios coletados.
- [ ] T-D-008 Verificar gates da Fase D: vitórias vs p=5 ≥ 70%; erros totais ≤ 80; divergências fatais por partida caem ≥ 50% vs baseline; faixa 29–30 ≥ 95%. **blockedBy**: T-D-007. **Gate**: todos os critérios atendidos.
- [ ] T-D-009 Atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` com a transição Fase C → D (11 canais ativos, contrato v2). **blockedBy**: T-D-001, T-D-002. **Gate**: guia reflete a nova versão do contrato.
- [ ] T-D-010 Adicionar entrada datada em `docs/historico_decisoes.md` com tabela **Fase C vs Fase D** (win-rates + accuracy por faixa + queda de divergências fatais). **blockedBy**: T-D-008. **Gate**: entrada presente.

> **Nota**: porte Dart do analisador estrutural está **fora do escopo** desta spec (clarification 2026-05-07). Os vetores de referência de T-D-005 servem como ground truth para uma futura feature dedicada.

**Checkpoint Fase D**: contrato v2 consolidado backend↔frontend; pode-se iniciar Fase E.

---

## Fase E — `sample_weight` refinado em t ∈ [12, 17]

**Objetivo**: aumentar marginalmente o peso de amostras com decisão estratégica difícil (alta margem entre top-1 e top-2 do supervisor) na faixa de meio de jogo, sem distorcer o treino.

**Gate da fase**: histograma valida; nenhum win-rate cai > 2pp vs Fase D; divergências fatais em t ∈ [12, 17] caem ≥ 25%.

- [ ] T-E-001 Implementar bloco de cálculo de `Δ_top2` (margem score_top1 − score_top2 do supervisor) e função `peso = clip(1 + α·Δ_top2, 1.0, 1.20)` com `α = 0.03` inicial em `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb`. Aplicar **somente** a amostras com `t ∈ [12, 17]`; demais recebem peso 1.0. **Gate**: célula computa vetor `pesos` com shape `(N,)`; `pesos.min() == 1.0`; `pesos.max() ≤ 1.20`.
- [ ] T-E-002 Validar histograma: peso médio em `t ∈ [12, 17]` entre **1.05 e 1.15**; `pesos.max() ≤ 1.20` global. **blockedBy**: T-E-001. **Gate**: célula de auditoria imprime média e max conformes; histograma plotado.
- [ ] T-E-003 Treinar com `model.fit(..., sample_weight=pesos)` e exportar `modelos/pontinhos_pequeno_p9_faseE.tflite`. **blockedBy**: T-E-002. **Gate**: arquivo gerado; ≤ 200 KB.
- [ ] T-E-004 Avaliar `_faseE.tflite` via `Avaliacao_CNN_vs_Minimax.ipynb` + analisadores. **blockedBy**: T-E-003. **Gate**: relatórios coletados.
- [ ] T-E-005 Verificar gates da Fase E: nenhum win-rate cai > 2pp vs Fase D; divergências fatais em `t ∈ [12, 17]` caem ≥ 25%. **blockedBy**: T-E-004. **Gate**: todos os critérios atendidos.
- [ ] T-E-006 Adicionar entrada datada em `docs/historico_decisoes.md` com tabela **Fase D vs Fase E** (win-rates + accuracy por faixa + queda de divergências fatais em meio de jogo + valor final de α). **blockedBy**: T-E-005. **Gate**: entrada presente.

**Checkpoint Fase E**: meio de jogo reforçado; pode-se iniciar Fase F.

---

## Fase F — Value head AlphaZero-style

**Objetivo**: adicionar uma cabeça `value` (regressão tanh) ao Keras durante o treino; manter TFLite só com a cabeça `policy` (compatibilidade com inferência atual).

**Gate da fase**: teste do contrato verde **com hash idêntico ao da Fase D** (TFLite continua expondo apenas policy); nenhum win-rate cai > 2pp vs Fase E; MSE final ≤ 0.10; divergências fatais ≥ 50% vs baseline; entrada em `docs/historico_decisoes.md`.

- [ ] T-F-001 Modificar a célula de definição do modelo Keras em `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` para dual-output: shared trunk → policy head (atual) + value head (`Conv 1×1(16) → Flatten → Dense(64, relu) → Dense(1, tanh)`). **Gate**: `model.summary()` mostra dois outputs; nenhuma mudança no shared trunk.
- [ ] T-F-002 Configurar loss conjunta `loss = KLD(policy) + λ·MSE(value)` com `λ = 0.1` inicial; `value_target = clip(score_max / 6.0, -1, +1)`. **blockedBy**: T-F-001. **Gate**: `model.compile` aceita os dois losses; célula de loss imprime os dois componentes a cada época.
- [ ] T-F-003 Treinar o modelo dual-head; persistir checkpoint Keras completo. **blockedBy**: T-F-002. **Gate**: treino conclui; checkpoint salvo.
- [ ] T-F-004 Para export TFLite, **construir segundo Keras** `Model(inputs=base.input, outputs=policy_pred)` (descartando explicitamente a value head) e converter para `modelos/pontinhos_pequeno_p9_faseF.tflite`. **blockedBy**: T-F-003. **Gate**: TFLite gerado; `Interpreter.get_output_details()` mostra **um único output** (policy); tamanho ≤ 200 KB.
- [ ] T-F-005 Rodar `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py -v`. **blockedBy**: T-F-004. **Gate**: teste verde; **hash do contrato JSON idêntico ao da Fase D** (sem mudança de contrato externo).
- [ ] T-F-006 Avaliar `_faseF.tflite` via `Avaliacao_CNN_vs_Minimax.ipynb` + analisadores. **blockedBy**: T-F-004. **Gate**: relatórios coletados.
- [ ] T-F-007 Verificar gates da Fase F: nenhum win-rate cai > 2pp vs Fase E; MSE final ≤ 0.10; divergências fatais ≥ 50% vs baseline. **blockedBy**: T-F-006. **Gate**: todos os critérios atendidos.
- [ ] T-F-008 Adicionar entrada datada em `docs/historico_decisoes.md` com tabela **Fase E vs Fase F** (win-rates + accuracy por faixa + λ calibrado + MSE final do value head). **blockedBy**: T-F-007. **Gate**: entrada presente.

**Checkpoint Fase F**: avaliação final consolidada; decidir se G/H são necessárias.

---

## Fase G — Hard-target em ≥ 26 traços (CONDICIONAL)

**Gate de entrada**: executar **SOMENTE se Fase F não atinge SC-W-* (win-rates) ou SC-A-* (accuracy por faixa)** definidos no `spec.md`. Caso contrário, pular.

**Detalhamento**: ver PRD §5 (Fase G). Tarefas internas serão geradas via re-execução de `/speckit-tasks` com escopo restrito a esta fase, somente se ativada.

- [ ] T-G-000 Bloco condicional Fase G — hard-target (rótulo one-hot estrito) em estados com ≥ 26 traços. **Pré-condição**: gates da Fase F falharam em pelo menos um SC-W-* ou SC-A-*. **Gate**: PRD §5 detalha; só expandir se ativada.

---

## Fase H — Loss assimétrica calibrada com BCE (CONDICIONAL)

**Gate de entrada**: executar **SOMENTE se Fase F (e G, se executada) não atinge SC-W-* ou SC-A-***. Caso contrário, pular.

**Detalhamento**: ver PRD §5 (Fase H).

- [ ] T-H-000 Bloco condicional Fase H — loss assimétrica BCE penalizando mais erros tipo "deveria-fechar mas não fechou" em estados terminais. **Pré-condição**: gates de F (e G) ainda não satisfeitos. **Gate**: PRD §5 detalha; só expandir se ativada.

---

## Tarefas atravessadas (lembretes)

Estas obrigações se aplicam **a cada fase** que tocar os artefatos correspondentes — já estão cobertas pelas tarefas específicas acima, mas ficam aqui como checklist de revisão de PR:

- Toda alteração em `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` **DEVE** ser seguida da cópia byte-a-byte em `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` **na mesma PR** (Fases B, D, F).
- Toda mudança no fluxo do dia-a-dia (geração, enriquecimento, treino, avaliação) **DEVE** atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` na mesma resposta (Fases A.1, A.2, B, D).
- Cada fase **DEVE** terminar com entrada datada em `docs/historico_decisoes.md` contendo data, contexto, decisão, alternativas consideradas, motivo, e tabela de win-rates por adversário + accuracy por faixa (§2.5 do PRD).
- Todo arquivo game-specific criado **DEVE** carregar sufixo `_pontinhos` ou viver em pasta `jogo_pontinhos/` (CLAUDE.md — nomenclatura por jogo).

---

## Dependências & ordem de execução

### Ordem estrita das fases

```
Fase A.1 → Fase A.2 → Fase B → Fase C → Fase D → Fase E → Fase F → (G/H condicionais)
```

Cada fase só inicia após o **gate de saída** da anterior bater. Isso é regra do PRD (mudança isolada por fase para atribuição de causa).

### Dentro de cada fase

- Tarefas marcadas `[P]` podem rodar em paralelo se tocam arquivos diferentes e não dependem da saída uma da outra.
- Tarefas com `blockedBy` aguardam as dependências listadas.
- Testes unitários em paralelo com a implementação **somente em modo TDD** (escrever teste antes); caso contrário, são sequenciais (teste após implementação).

### Oportunidades de paralelização por fase

- **A.1**: T-A1-003 [P] em paralelo com T-A1-002; T-A1-006 [P] após T-A1-005.
- **A.2**: T-A2-004 [P] (script de visualização) em paralelo com T-A2-003 (notebook de enriquecimento); T-A2-007 [P] (atualizar guia) em paralelo com T-A2-005/006.
- **B**: T-B-007 [P] (analisadores) em paralelo com T-B-008 [P] (latência), ambos após T-B-005/006.
- **D**: T-D-005 [P] (vetores de referência) em paralelo com T-D-001/002/003/004 desde que o analisador da Fase A.2 esteja pronto.

---

## Estratégia de implementação

### Entrega incremental (uma fase por vez)

1. Concluir Fase A.1 → auditoria de geração registrada → checkpoint.
2. Concluir Fase A.2 → NPZs enriquecidos → checkpoint.
3. Concluir Fase B → primeiro TFLite com nova arquitetura → **MVP do refinamento tático** → demo possível.
4. Concluir Fase C → viés de borda eliminado → demo.
5. Concluir Fase D → contrato v2 consolidado backend↔frontend → demo.
6. Concluir Fase E → meio de jogo reforçado → demo.
7. Concluir Fase F → value head treinado, TFLite policy-only → demo final.
8. Avaliar se G/H são necessárias com base nos gates SC-W-* / SC-A-*.

### MVP da feature

Fase A.1 + A.2 + B = **MVP** (corrige a Categoria A — erros táticos óbvios em 30ª jogada — que é US1 P1 do `spec.md`).

---

## Pendências da geração de tarefas

> Esta seção é preenchida **apenas** quando a geração das tarefas encontra ambiguidade que os documentos de entrada não resolvam. NÃO inventar — registrar aqui.

Nenhuma pendência identificada nesta geração. Todas as decisões necessárias estão cobertas por:

- `PRD.md` §4.1.3 (`COMPLEMENTO_POR_CELULA`, `STRAT_WEIGHTS`, `FAIXA_TRACOS`, pré-população do set de hashes).
- `PRD.md` §4.2 e `contracts/canais_estruturais.md` (algoritmo dos 11 canais e nomes canônicos).
- `PRD.md` §5 (detalhe das Fases G e H — não expandidas aqui por serem condicionais).
- `research.md` (5 clarifications de 2026-05-07: Databricks fora do escopo; Dart fora do escopo; PNGs 150 DPI / paleta categórica / borda em fechadas / título canônico; canal único `cadeia_longa = ≥3`; sem padrão obrigatório de logging).
- `data-model.md` e `contracts/npz_schema.md` (esquema NPZ por fase).
- `CLAUDE.md` (nomenclatura por jogo, contrato CNN backend↔frontend, documentação viva).

Pendências de **planejamento** registradas em `plan.md` e `research.md` §3 não foram convertidas em tarefas — são itens a resolver durante a execução, não bloqueiam o `tasks.md` (regra 7 do prompt).

---

## Estado de execução — sessão 2026-05-07

> Esta seção é mantida pela sessão de implementação para registrar o que foi entregue e o que ficou aguardando execução manual em ambientes externos (Databricks/Colab).

### Entregue nesta sessão (Fases A.1 + A.2 — artefatos)

- **`notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`** — clone do V4 com 4 novas células: parâmetros A.1 (`COMPLEMENTO_POR_CELULA` + `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` + `FAIXA_TRACOS = (0.15, 0.97)`), pré-população do set de hashes a partir do legado, auditoria pós-execução. Notebook não foi rodado: precisa do Databricks com workspace `c092820@corp.caixa.gov.br/CNN/...` montado.
- **`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`** — módulo com `NOMES_CANAIS` e `extrair_canais(M)` implementando o algoritmo dos 11 canais conforme `contracts/canais_estruturais.md`.
- **`tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`** — 11 testes cobrindo domínio binário, exclusão mútua, simetrias, casos canônicos. **Resultado nesta máquina: 11 passed em 0.21s** (Python 3.9.5, pytest 8.4.2). Bug encontrado e corrigido durante TDD: `np.bool_ + np.bool_` retorna OR lógico em numpy moderno, não soma; correção em `_grau()`.
- **`notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb`** — sobrescrita atômica `.tmp` + `os.replace()`, validação `nomes_canais` byte-a-byte por arquivo. Notebook não foi rodado: precisa do diretório real de NPZs Fase A.1.
- **`scripts/pontinhos/validar_canais_visualmente.py`** — CLI funcional (paleta categórica, borda em fechadas, 150 DPI, títulos canônicos). Não foi rodado por falta de NPZ enriquecido neste ambiente.
- **`docs/jogo_pontinhos/guia_geracao_dados.md`** — nova seção **1A** com o fluxo completo A.1 + A.2 + validação visual + auditoria + testes.
- **`docs/historico_decisoes.md`** — duas novas entradas datadas no topo:
    - **2026-05-07 (A.2)**: consolidação D2/D3/D4, com bloco "Assinatura visual" pendente para T-A2-005.
    - **2026-05-07 (A.1)**: TEMPLATE com placeholders para os números reais — preencher após execução do V5 no Databricks (T-A1-006 fica oficialmente fechada quando os placeholders forem substituídos).

### Aguardando execução manual em ambiente externo

| Tarefa | Por quê | Comando esperado |
|---|---|---|
| T-A1-001..005 (rodar V5 no Databricks) | Notebook depende de cluster Databricks com workspace `c092820@corp.caixa.gov.br/CNN/profundidade_9_legado/` montado para a pré-população do set de hashes; tempo estimado 1.34h em 12 workers. | Subir o `.ipynb` no Databricks e executar célula a célula. |
| T-A1-006 (preencher template do histórico) | Os números empíricos só existem após a execução do V5. | Substituir os placeholders `____________` na entrada `2026-05-07 — Fase A.1` em `docs/historico_decisoes.md`. |
| T-A2-003 (rodar enriquecimento) | Depende dos NPZs reais da Fase A.1 (~500MB total). | Configurar `DIR_NPZ` no notebook e executar todas as células. |
| T-A2-005 (validação visual ≥ 30 PNGs) | Gate manual humano, requer revisão olho-a-olho. | `py scripts/pontinhos/validar_canais_visualmente.py --diretorio-npz <path> --qtd-tracos 14 17 24 29 --n-amostras 30 --seed 42` e revisar PNGs. |
| T-A2-006 (auditoria do diretório enriquecido) | A célula de auditoria já está no notebook A.2 — basta executá-la sobre o diretório real e anexar o relatório à entrada A.2 do histórico. | Rodar a última célula do notebook A.2 e copiar a saída para o histórico. |

### Itens checados nesta máquina

```bash
$ py -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais, NOMES_CANAIS; print(len(NOMES_CANAIS))"
11

$ py -m pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v
============================= 11 passed in 0.21s ==============================

$ py -c "import json; json.load(open('notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb', encoding='utf-8'))"
JSON OK
```

### Não tocado (Fases B+ explicitamente fora do escopo desta sessão)

Nenhum arquivo das Fases B/C/D/E/F/G/H foi criado ou modificado nesta sessão. O contrato `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` permanece na sua versão atual (v1, com input `(4, 3, 5)` ainda usando `dono_caixa` ternário) — sua atualização é responsabilidade da Fase B (T-B-002/003/004).
