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

## Fase A.1 — Geração de dataset (pipeline V7 DAC)

> **Revisão 2026-05-12:** esta fase foi concluída com o algoritmo **V7 DAC** (não o notebook V5/cotas como especificado originalmente). Ver PRD §4.1.4 e `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`. As tasks abaixo estão marcadas como concluídas, mas o que foi entregue é diferente do escopo original — as notas inline registram o que foi feito de fato.

**Objetivo (revisado)**: produzir NPZs com ~758k amostras brutas e ~500k distintos cobrindo t=1–30 (distribuição bell-shaped emergente), supervisão Minimax p=11, schema V2. Diretório: `dados/profundidade_minimax_11_v7_adaptativo/`.

**Gate da fase (revisado — ATENDIDO)**: ~758k amostras gravadas; ~500k distintos; cobertura 1–30 traços; campos `melhor_jogada` e `score_melhor_jogada` preenchidos em todos os NPZs; dois bugs críticos de Bitboard corrigidos e aplicados; snapshot em `docs/historico_decisoes.md`.

- [x] T-A1-001 ~~Criar `Otimizacao_Topologia_Rede_V5.ipynb`~~ → **Entregue como:** `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb` (Fase 1 — geração local DAC) + `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py`. Pipeline V5/cotas substituído por V7 DAC.
- [x] T-A1-002 ~~Embutir `COMPLEMENTO_POR_CELULA`~~ → **Substituído:** V7 DAC não usa quotas; distribuição bell-shaped emergente por snapshots por partida. Parâmetros: ~25.288 partidas, 30 snapshots cada.
- [x] T-A1-003 ~~`STRAT_WEIGHTS` e `FAIXA_TRACOS`~~ → **Substituído:** V7 usa tensão estrutural τ para profundidade adaptativa e Boltzmann sampling para diversidade. Sem `STRAT_WEIGHTS` ou `FAIXA_TRACOS`.
- [x] T-A1-004 ~~Pré-população do set de hashes com legado~~ → **Substituído:** V7 não reaproveitou o legado V4/V5. Dataset novo do zero em `dados/profundidade_minimax_11_v7_adaptativo/`.
- [x] T-A1-005 Célula de auditoria pós-execução implementada no notebook V7. **Entregue:** distribuição por `qtd_tracos` auditada; ~758k amostras brutas, ~500k distintos confirmados.
- [x] T-A1-006 [P] Entrada datada em `docs/historico_decisoes.md` (2026-05-08 — Geração V7 Adaptativa DAC). Bugs críticos de Bitboard documentados em PRD §4.1.5. **Gate atendido.**
- [x] T-A1-007 [NOVO] Enriquecimento Fase 2 (Databricks) — `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb` rodou sobre todos os 152 NPZs, adicionando `melhor_jogada`, `score_melhor_jogada` e `depth_melhor_jogada` com Minimax p=7. Re-executado posteriormente com p=11.
- [x] T-A1-008 [NOVO] Experimentos de treino preliminares (sem canais estruturais): 4 configurações p=7 + 1 configuração p=11. Melhor resultado: 90,5% vs p=3 e 63% vs p=6 com todas as 758k amostras (incluindo duplicatas). BoxNet v3 em saturação arquitetural. Ver PRD §4.1.6.

**Checkpoint Fase A.1**: NPZ com 500.000 únicos disponível em path conhecido; auditoria registrada; pode-se iniciar Fase A.2.

---

## Fase A.2 — Enriquecimento local (11 canais estruturais)

**Objetivo**: enriquecer cada NPZ produzido em A.1 com o array `canais (N, 4, 3, 11) int8` derivado da matriz crua, junto do array `nomes_canais` (string array com 11 nomes canônicos), preservando todas as chaves anteriores. Sobrescrita atômica.

**Gate da fase**: todos os NPZs do diretório enriquecidos com sucesso; teste do analisador verde; ≥ 30 PNGs visualmente validados pelo desenvolvedor; auditoria de `nomes_canais` byte-a-byte idêntica em todos os arquivos; `docs/jogo_pontinhos/guia_geracao_dados.md` atualizado; entrada D2/D3/D4 em `docs/historico_decisoes.md`.

- [x] T-A2-001 Criar `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` com constante pública `NOMES_CANAIS` (lista de 11 strings na ordem do PRD §4.2) e função `extrair_canais(M: np.ndarray) -> np.ndarray` retornando `(4, 3, 11) int8` conforme algoritmo de `contracts/canais_estruturais.md`. **Gate**: `python -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais, NOMES_CANAIS; print(len(NOMES_CANAIS))"` imprime `11`.
- [x] T-A2-002 Criar `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` cobrindo: (a) domínio binário `{0,1}` em todos os canais; (b) exclusão mútua canal 4 (`caixa_fechada`) vs canais 5–10 (graus/cadeias/loops); (c) coerência sob simetria (canais transformam coerentemente sob ref_H, ref_V, R180); (d) casos canônicos: tabuleiro vazio, caixa fechada simples, **double-cross do Buchin**, **loop de 4 caixas**, **half-open chain**. **blockedBy**: T-A2-001. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v` 100% verde.
- [x] T-A2-003 Criar `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` que: lê NPZ de `dados/profundidade_minimax_11_v7_adaptativo/` (schema V2), computa `canais` chamando `extrair_canais` para cada estado, escreve novo NPZ com sobrescrita **atômica** via `tmp_path = path + '.tmp'` + `os.replace(tmp_path, path)`; preserva todas as chaves schema V2; adiciona `nomes_canais`. **blockedBy**: T-A2-001. **Gate**: rodando o notebook sobre um NPZ de teste, o arquivo final contém todos os campos do schema V2 + `canais` (dtype int8, shape `(N, 4, 3, 11)`) + `nomes_canais` (shape `(11,)`); nenhum `.tmp` remanescente.
- [x] T-A2-004 [P] Criar `scripts/pontinhos/validar_canais_visualmente.py` com CLI `--qtd-tracos N1 N2 ... --n-amostras K`, gerando PNGs a 150 DPI, paleta categórica estável (uma cor por canal, fixa entre execuções), borda destacada em boxnets de caixas fechadas, título acima de cada boxnet com o nome canônico exatamente igual ao item de `NOMES_CANAIS`. **blockedBy**: T-A2-001. **Gate**: `python scripts/pontinhos/validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30` produz 30 PNGs válidos no diretório de saída. **Entregue 2026-05-13**: script funcional em `scripts/pontinhos/validar_canais_visualmente.py`; default `--diretorio-npz` aponta para `dados/profundidade_minimax_11_v7_adaptativo`. Gate de execução aguarda NPZs enriquecidos (T-A2-003).
- [x] T-A2-005 Validação visual manual de **≥ 30 estados** distribuídos nas faixas `t∈[12,17]`, `t∈[24,28]` e `t∈[29,30]` usando os PNGs gerados em T-A2-004. **blockedBy**: T-A2-003, T-A2-004. **Gate**: desenvolvedor confirma na entrada de `docs/historico_decisoes.md` que os canais 0–10 estão coerentes com a matriz crua nos casos inspecionados (assinatura textual). **Concluído 2026-05-14**: assinatura registrada em `docs/historico_decisoes.md` (entrada 2026-05-14).
- [x] T-A2-006 Auditoria do diretório de NPZs enriquecidos: verificar que `nomes_canais` é **byte-a-byte idêntico** em todos os arquivos; computar e registrar hashes pré e pós enriquecimento (`estados`, `score_melhor_jogada` e `melhor_jogada` devem ter hash inalterado; `canais` e `nomes_canais` são chaves novas). **blockedBy**: T-A2-003. **Gate**: célula de auditoria no notebook ou script equivalente imprime `OK` para todos os arquivos; relatório anexado à entrada de `docs/historico_decisoes.md`. **Concluído 2026-05-14**: 152 NPZs auditados, nomes_canais byte-a-byte idêntico, hashes registrados em `docs/historico_decisoes.md` (entrada 2026-05-14).
- [x] T-A2-007 [P] Atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` documentando o novo fluxo A.1 (V7 DAC local + Fase 2 Databricks) + A.2 (notebook de enriquecimento local), com comandos, paths e ordem de execução. Diretório correto: `dados/profundidade_minimax_11_v7_adaptativo/`. **blockedBy**: T-A2-003. **Gate**: leitor consegue reproduzir o fluxo do zero a partir do guia, sem precisar abrir o PRD.
- [x] T-A2-008 Adicionar entrada datada em `docs/historico_decisoes.md` consolidando D2 (canal `cadeia_longa = ≥3` único, K=11), D3 (sobrescrita atômica via `.tmp` + `os.replace`) e D4 (paleta visual estável + borda em fechadas). **blockedBy**: T-A2-005, T-A2-006. **Gate**: entrada presente com data, contexto, decisão, alternativas consideradas, motivo.

- [ ] T-A2-009 **[PRIORIDADE MÁXIMA]** Implementar canal 12 (`paridade_cadeia_longa_impar`, K=11) em `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`: expandir `NOMES_CANAIS` para 12 entradas, atualizar `N_CANAIS = 12`, adicionar bloco de cálculo de `n_cadeias_longas` e `paridade_impar` ao final de `extrair_canais()`, broadcast para todas as 12 células em `canais[:, :, 11]`. **Gate**: `python -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import NOMES_CANAIS; print(len(NOMES_CANAIS))"` imprime `12`.
- [ ] T-A2-010 **[PRIORIDADE MÁXIMA]** Adicionar testes de regressão para canal 12 em `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`: (a) estado vazio → K=11 = 0; (b) 1 cadeia longa → K=11 = 1; (c) 2 cadeias longas → K=11 = 0; (d) 1 loop + 1 cadeia longa → K=11 = 1 (loop não conta); (e) broadcast: `canais[:, :, 11]` é uniforme para qualquer estado. **blockedBy**: T-A2-009. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v` 100% verde (≥ 18 testes).

> **Nota de repriorização 2026-05-13**: T-A2-009 e T-A2-010 devem ser executados **antes** do re-enriquecimento dos NPZs (T-A2-003 re-run). Após a implementação de canal 12, o re-enriquecimento incluirá automaticamente K=11. A Fase C (espelhamento 4×) é co-prioridade com canal 12 — T-C-001 e T-C-002 devem ser iniciados logo após T-A2-010 verde. Ver motivação em `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`.

**Checkpoint Fase A.2**: NPZs enriquecidos prontos para consumo pelo treino (com 12 canais incluindo K=11); pode-se iniciar Fase A.3.

---

## Fase A.3 — Pipeline V8: campos escalares de cadeias, re-rotulação adaptativa e augmentação por simetria

> **Criada em 2026-05-14.** Esta fase formaliza as decisões de design tomadas em sessão de análise: (1) 3 novos campos escalares por estado para metadata de cadeias; (2) reorganização do pipeline em `gerador_dados/jogo_pontinhos/v8/` com 4 fases; (3) re-rotulação Databricks com profundidade adaptativa (~2,3% dos estados precisam de p>11); (4) augmentação por simetria com sufixos `_refH`/`_refV`/`_r180`. Decisão completa em `docs/historico_decisoes.md` (entrada 2026-05-14 — Pipeline V8).

**Objetivo**: enriquecer os NPZs com 3 campos escalares de metadata de cadeias (`qtd_cadeias_longas`, `total_caixas_cadeias_longas`, `tamanho_max_cadeia_longa`); reorganizar o pipeline em pasta `v8/` com nomes descritivos; corrigir rótulos dos ~2,3% de estados onde Minimax p=11 é insuficiente; gerar augmentação 4× via sufixos; atualizar notebooks de treino e análise.

**Fórmula de profundidade mínima**: `profundidade_minima = total_caixas_cadeias_longas + 2 × qtd_cadeias_longas`

**Critério de re-rotulação** (Databricks — Fase 3 V8 — profundidade única p=20):
- `arestas_livres ≤ 11` (qtd_tracos ≥ 20): manter rótulo — p=11 já resolve o jogo completo
- `arestas_livres > 11` E `prof_min > 11`: re-rotular com p=20

O Minimax para naturalmente quando não há mais jogadas. p=20 resolve qualquer estado com ≤ 19 arestas livres (máximo observado). Sem schedule por bucket — profundidade única simplifica a implementação.

**Estados a re-rotular (análise 100% do dataset — 2026-05-14)**: **11.542** (1,52% de 758.640). Dos 17.724 estados com `prof_min > 11`, 6.182 têm `arestas_livres ≤ 11` e já estão corretamente rotulados.

**Gate da fase**: 152 NPZs originais enriquecidos com 3 novos campos escalares + canais com shape `(N,4,3,12)`; notebook Databricks (Fase 3) pronto para execução; 152×3 = 456 NPZs sufixados gerados pela Fase 4; notebook de treino e análise atualizados; entrada em `docs/historico_decisoes.md`.

- [ ] T-A3-001 [P] Registrar formalmente em `docs/historico_decisoes.md` os resultados da análise de distribuição de cadeias realizada em 2026-05-14: distribuição de `qtd_cadeias_longas` (0: 62,4%, 1: 31,9%, 2: 5,6%, 3+: 0,1%), distribuição de `profundidade_minima` (≤11: 97,7%; 12–18: 2,3%), schedule de re-rotulação, justificativa do cap p=20. **Gate**: entrada datada presente em `docs/historico_decisoes.md`.

- [ ] T-A3-002 Adicionar `extrair_stats_cadeias(M: np.ndarray) -> tuple[int, int, int]` em `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`, retornando `(qtd_cadeias_longas, total_caixas_cadeias_longas, tamanho_max_cadeia_longa)`. Reutiliza o mesmo grafo BFS já executado em `extrair_canais`. **blockedBy**: T-A2-009 (compartilha código BFS de classificação de componentes). **Gate**: `python -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_stats_cadeias; print(len(extrair_stats_cadeias.__doc__))"` não lança ImportError.

- [ ] T-A3-003 [P] Adicionar testes para `extrair_stats_cadeias` em `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`: (a) estado vazio → `(0, 0, 0)`; (b) 1 cadeia longa de 3 caixas → `(1, 3, 3)`; (c) 2 cadeias longas de 4 caixas → `(2, 8, 4)`; (d) 1 cadeia longa + 1 cadeia curta → `qtd=1`, `total=len(longa)`, `max=len(longa)`; (e) loop não conta como cadeia longa → `qtd=0`. **blockedBy**: T-A3-002. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v` 100% verde.

- [ ] T-A3-004 Criar estrutura de diretório `gerador_dados/jogo_pontinhos/v8/` com 4 notebooks nomeados de forma descritiva (Fase 1 a 4). O notebook da Fase 1 é o mesmo gerador existente — apenas link/referência; Fases 2, 3, 4 são notebooks novos. **Gate**: `ls gerador_dados/jogo_pontinhos/v8/` mostra 4 notebooks `.ipynb`.

- [ ] T-A3-005 Criar notebook `gerador_dados/jogo_pontinhos/v8/fase2_enriquecimento_local.ipynb`: enriquece os 152 NPZs de `dados/profundidade_minimax_11_v7_adaptativo/` adicionando canal 12 (shape `canais`: `(N,4,3,12) int8`) e os 3 campos escalares `qtd_cadeias_longas (N,) int8`, `total_caixas_cadeias_longas (N,) int8`, `tamanho_max_cadeia_longa (N,) int8`. Sobrescrita atômica via `.tmp` + `os.replace()`. Flag `FORCAR_REGRAVAR = True`. **blockedBy**: T-A2-009, T-A3-002. **Gate**: executando sobre 1 NPZ de teste, o resultado contém `canais` com shape `(N,4,3,12)` e os 3 novos campos escalares.

- [ ] T-A3-006 Executar Fase 2 V8 (`fase2_enriquecimento_local.ipynb`) sobre os 152 NPZs. **blockedBy**: T-A3-005. **Gate**: auditoria célula final confirma que todos os 152 NPZs têm `canais.shape == (N,4,3,12)` e os 3 campos escalares presentes; nenhum `.tmp` remanescente.

- [ ] T-A3-007 Criar notebook Databricks `gerador_dados/jogo_pontinhos/v8/fase3_rerotulacao_databricks.ipynb`: re-calcula `melhor_jogada` e `score_melhor_jogada` somente para estados onde `arestas_livres > 11` E `prof_min > 11`, usando profundidade única `p=20`. O Minimax para naturalmente quando o jogo termina. Usa PySpark `mapInPandas` (padrão do Fase 2 HighPerf existente). Sobrescrita atômica. **blockedBy**: T-A3-006. **Gate**: notebook importável no Databricks; célula de diagnóstico imprime contagem de estados a re-rotular por `arestas_livres` (esperado: 12→3.601, 13→3.000, 14→2.232, 15→1.581, 16→836, 17→244, 18→45, 19→3; total=11.542).

- [ ] T-A3-008 Criar `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py` com as 4 transformações (identidade, ref_H, ref_V, R180) aplicáveis a: matriz crua `(9,7)`, tensor `canais (4,3,12)` com permutação coerente de arestas (K=0↔1 em ref_V; K=2↔3 em ref_H; K=11 preservado por ser broadcast), vetor de scores `(31,)`, índice de rótulo via tabela de permutação canônica. **Gate**: módulo importável; expõe função `aplicar_simetria(estado, sym_id)`.

- [ ] T-A3-009 [P] Criar `tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py`: (a) idempotência (identidade não muda nada); (b) composição (R180 = ref_H ∘ ref_V); (c) coerência `canais ↔ matriz crua ↔ scores ↔ rótulo` sob cada simetria; (d) K=11 preservado bit-a-bit em todas as 4 simetrias. **blockedBy**: T-A3-008. **Gate**: `pytest tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py -v` 100% verde.

- [ ] T-A3-010 Criar notebook `gerador_dados/jogo_pontinhos/v8/fase4_augmentacao_simetria.ipynb`: (1) começa **deletando** todos os arquivos `*_refH.npz`, `*_refV.npz`, `*_r180.npz` de `dados/profundidade_minimax_11_v7_adaptativo/` (idempotência garantida); (2) para cada NPZ original (sem sufixo), gera 3 variantes aplicando as 3 simetrias não-triviais via `permutacoes_simetria_pontinhos`; (3) nome dos arquivos gerados: `<nome_original>_refH.npz`, `<nome_original>_refV.npz`, `<nome_original>_r180.npz`; (4) sobrescrita atômica. **blockedBy**: T-A3-007, T-A3-008, T-A3-009. **Gate**: para cada NPZ original (152), existem 3 sufixados; total de arquivos no diretório = 152 × 4 = 608.

- [ ] T-A3-011 Atualizar `notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V8.ipynb`: (a) expandir `NOMES_CANAIS_REF` de 11 para 12 entradas (adicionar `"paridade_cadeia_longa_impar"`); (b) na célula de carga de dados, ler também arquivos `*_refH.npz`, `*_refV.npz`, `*_r180.npz` do diretório; (c) adicionar métricas segmentadas por `qtd_cadeias_longas` (grupos 0, 1, 2, ≥3): OMA, top-1 e top-3 por grupo. **blockedBy**: T-A3-006 (campos), T-A3-010 (arquivos sufixados). **Gate**: célula de diagnóstico imprime OMA por grupo de `qtd_cadeias_longas` sem erros.

- [ ] T-A3-012 [P] Atualizar `notebooks/jogo_pontinhos/Analise_Dados_Adaptativo.ipynb`: adicionar 3 novas seções após a análise de `qtd_tracos` existente: (a) distribuição de `qtd_cadeias_longas` por `qtd_tracos`; (b) distribuição de `tamanho_max_cadeia_longa`; (c) distribuição de `profundidade_minima = total_caixas_cadeias_longas + 2×qtd_cadeias_longas` com linha vertical em 11 (threshold atual) para quantificar estados que precisam de re-rotulação. **blockedBy**: T-A3-006. **Gate**: notebook roda do zero e gera gráficos sem erros.

**Checkpoint Fase A.3**: NPZs enriquecidos com 12 canais + 3 escalares; Databricks Fase 3 pronto para execução pontual; 608 NPZs totais (152 originais + 456 sufixados); notebooks de treino e análise atualizados; pode-se iniciar Fase B.

---

## Fase B — Treino com 5 canais geométricos

> **Nota 2026-05-12:** experimentos preliminares de treino foram realizados com os dados V7 (sem canais estruturais, usando `estados` brutos). Esses experimentos não substituem a Fase B formal, que introduz `canais[..., :5]` e remove a Lambda. O novo baseline de comparação é 63% vs p=6 (não mais 38%). NPZ usa schema V2: leia `score_melhor_jogada` (não `scores`) e `melhor_jogada` (não `rotulos`); não existe mais `generation_mode`.

**Objetivo**: substituir a Lambda interna `para_grid_de_caixas` por leitura direta de `canais[..., :5]` do NPZ (schema V2 em `dados/profundidade_minimax_11_v7_adaptativo/`); treinar e exportar primeiro TFLite da nova arquitetura.

**Gate da fase**: SC-F-05 (top-1 ≥ 95% na faixa 29–30 traços) atendido; erros táticos ≤ 250 em `analisa_padrao_erros.py`; nenhum win-rate vs Minimax(p=3/5/6) cai > 3pp vs baseline; TFLite ≤ 200 KB; latência ≤ 5 ms/jogada; teste do contrato verde; entrada em `docs/historico_decisoes.md`.

- [ ] T-B-001 Criar `notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V8.ipynb` baseado no `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V7_Sample_Weight.ipynb` atual de treino, eliminando a camada Lambda `para_grid_de_caixas` e lendo `canais` diretamente do NPZ; introduzir `CANAIS_TREINAMENTO` (lista configurável dos canais a incluir no treino) e `INPUT_SHAPE = (4, 3, K)` onde `K = len(CANAIS_TREINAMENTO)`. Inclui: OMA correto (aceita qualquer jogada Minimax-ótima empatada), OMA por fase, Tabela 1 (presença de canal por fase), Tabela 2 (Top-1/3/5/OMA por canal), Correlação canal × erro. **Entregue 2026-05-13** — arquivo criado em `notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V8.ipynb`. **Gate**: notebook abre no Colab, executa célula de carga e imprime `X_train.shape == (..., 4, 3, K)` com K correto para `CANAIS_TREINAMENTO`.
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

> **Revisão 2026-05-12:** T-A1-001..006 foram concluídas com V7 DAC (não V5). As pendências abaixo são relativas à Fase A.2 (enriquecimento com canais estruturais), que ainda não foi executada sobre o dataset V7.

| Tarefa | Por quê | Como executar |
|---|---|---|
| T-A2-003 (rodar enriquecimento A.2) | NPZs V7 em `dados/profundidade_minimax_11_v7_adaptativo/` prontos mas sem canais estruturais ainda. | Abrir `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb`; alterar `DIR_NPZ = 'dados/profundidade_minimax_11_v7_adaptativo/'` na 2ª célula; executar todas as células. O notebook é schema-agnóstico. Ver §1A.2 de `docs/jogo_pontinhos/guia_geracao_dados.md`. |
| T-A2-004 (criar script de validação visual) | Script `scripts/pontinhos/validar_canais_visualmente.py` ainda não foi criado. | Implementar CLI com `--diretorio-npz`, `--qtd-tracos`, `--n-amostras`, `--seed`; paleta categórica estável por canal; borda em caixas fechadas; 150 DPI. Requer NPZs já enriquecidos (depende de T-A2-003). |
| T-A2-005 (validação visual ≥ 30 PNGs) | Gate manual humano, requer revisão olho-a-olho. Depende de T-A2-003 e T-A2-004. | `py scripts/pontinhos/validar_canais_visualmente.py --diretorio-npz dados/profundidade_minimax_11_v7_adaptativo --qtd-tracos 14 17 24 29 --n-amostras 30 --seed 42` e revisar PNGs gerados. |
| T-A2-006 (auditoria do diretório enriquecido) | A célula de auditoria já está no notebook A.2 — basta executá-la sobre o diretório V7 e anexar o relatório. Depende de T-A2-003. | Rodar a última célula do notebook `Enriquece_NPZ_Com_Canais.ipynb` e copiar a saída para `docs/historico_decisoes.md`. |

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

---

## Estado de execução — sessão 2026-05-13

### Decisões de design tomadas (Fase B)

- **Lambda removida definitivamente**: a camada `para_grid_de_caixas` foi abandonada. A CNN recebe o tensor `canais (N,4,3,K)` pré-computado nos NPZ da Fase A.2 diretamente como input. Motivação: canais BFS (eh_grau3, cadeia, loop) não são implementáveis como ops TFLite-compatíveis sem `tf.while_loop`; manter Lambda restringiria o input a 5 canais geométricos apenas.
- **CANAIS_TREINAMENTO**: parâmetro de configuração do notebook que permite selecionar subconjunto dos 11 canais. Permite experimentos com 5 canais (geométricos) vs 11 canais (completo) sem alterar arquitetura.
- **OMA corrigido**: métrica aceita qualquer jogada com Q-value máximo (empates incluídos), não apenas o argmax do soft target.
- **Notebook renomeado**: T-B-001 foi atualizado para usar `Treinamento_CNN_Pontinhos_V8.ipynb` (não `11_Canais.ipynb`).

### Entregue nesta sessão

- **`scripts/pontinhos/validar_canais_visualmente.py`** — corrigido: `--diretorio-npz` agora tem default `dados/profundidade_minimax_11_v7_adaptativo` (gate de T-A2-004 funciona sem flag).
- **T-A2-004 marcada como `[x]`** em `tasks.md`.
- **`notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V8.ipynb`** — notebook de treino V8 criado. Baseado no V7; Lambda removida; input `canais (4,3,K)`; `CANAIS_TREINAMENTO`; OMA correto; Table 1 (presença canal/fase); Table 2 (métricas por canal); Correlação canal × erro; OMA por fase; exportação TFLite.

### Aguardando execução manual

| Tarefa | Por quê | Como executar |
|---|---|---|
| T-A2-003 (enriquecimento) | NPZs em `dados/profundidade_minimax_11_v7_adaptativo/` sem canais ainda | Rodar `Enriquece_NPZ_Com_Canais.ipynb` localmente |
| T-A2-004 gate (gerar PNGs) | Requer NPZs enriquecidos | `py scripts/pontinhos/validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30` |
| T-B-001 gate (executar V8) | Requer Google Colab + NPZs enriquecidos | Abrir `Treinamento_CNN_Pontinhos_V8.ipynb` no Colab |

---

## Estado de execução — sessão 2026-05-13 (validação visual dos canais)

### Bugs encontrados e corrigidos no analisador

Validação visual com `validar_canais_visualmente.py` revelou 2 bugs relacionados em `analisador_estrutural_pontinhos.py`:

**Bug 1 — Nó isolado classificado como `em_cadeia_curta`**: uma caixa grau-2 sem nenhum vizinho grau-2 conectado por aresta livre formava um componente de tamanho 1 no grafo dual. O código classificava `comprimento <= 2 → em_cadeia_curta`, incluindo esses isolados. Um nó isolado não é cadeia estratégica (sem par para captura encadeada). Afetava: PROBLEMAS 1, 2, 3, 6 reportados na validação visual.

**Bug 2 — `em_cadeia_aberta_uma_ponta` incorreto para nó isolado**: `_contar_pontas_abertas` usava `break` após o primeiro vizinho grau-3, retornando 1 mesmo quando **ambas** as arestas livres levavam a caixas grau-3 (2 pontas abertas, não 1). Afetava: PROBLEMAS 4, 5.

**Fix (1 linha)**: `if comprimento == 1: continue` no branch path da classificação de componentes. Ambos os bugs desaparecem ao ignorar componentes tamanho 1.

### Entregue nesta sessão

- **`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`** — fix dos 2 bugs; definição `K=7 em_cadeia_curta` atualizada para "comprimento exatamente 2".
- **`tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`** — 2 novos testes de regressão adicionados (13/13 passando).
- **`specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md`** — contrato atualizado: comprimento 1 → ignorar; comprimento 2 → em_cadeia_curta.

### Re-enriquecimento obrigatório

⚠️ Os NPZs já enriquecidos em `dados/profundidade_minimax_11_v7_adaptativo/` usam o algoritmo **com bug**. É necessário re-rodar `Enriquece_NPZ_Com_Canais.ipynb` com `FORCAR_REGRAVAR = True` para recalcular os canais com o algoritmo corrigido.

| Tarefa | Por quê | Como executar |
|---|---|---|
| Re-enriquecimento dos NPZs | Canais gravados têm nós isolados marcados incorretamente | Rodar `Enriquece_NPZ_Com_Canais.ipynb` com `FORCAR_REGRAVAR = True` — **aguardar T-A2-009 (canal 12) antes de re-enriquecer** |
| Re-gerar PNGs de validação | Confirmar visualmente que bugs foram corrigidos + canal 12 correto | `py scripts/pontinhos/validar_canais_visualmente.py --qtd-tracos 14 17 29 --n-amostras 30` |

---

## Estado de execução — sessão 2026-05-13 (canal 12 + repriorização)

### Decisão de design

- **Canal 12 (`paridade_cadeia_longa_impar`)**: análise da estagnação da CNN V8 (50% vs Minimax p=6) identificou que a causa raiz é a impossibilidade de CNNs locais inferirem paridade global de cadeias longas. Canal 12 é um broadcast global (K=11) que entrega esse bit diretamente a todas as células do tensor. Teoria completa em `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`.
- **Fase C (espelhamento) co-prioridade**: augmentação 4× por simetria é igualmente urgente e deve ser executada no mesmo ciclo de treino que canal 12.

### Entregue nesta sessão

- **`docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`** — criado: teoria de cadeias, mecanismo de double-cross, exemplo passo-a-passo 1 cadeia curta + 2 longas, motivação para canal 12.
- **`specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md`** — atualizado: N_CANAIS=12, canal 12 adicionado (§8), simetria atualizada (K=11 broadcast, sem permutação), garantias e vetores de referência atualizados.
- **`specs/004-melhoria-geracao-dados-cnn/PRD.md`** — atualizado: §4.2 tabela e NOMES_CANAIS com canal 12; §6 tabela com canal 12; revisões datadas.
- **`specs/004-melhoria-geracao-dados-cnn/plan.md`** — atualizado: sumário, NOMES_CANAIS, nota de repriorização 2026-05-13.
- **`specs/004-melhoria-geracao-dados-cnn/tasks.md`** — adicionado: T-A2-009, T-A2-010 com prioridade máxima; nota de repriorização.

### Próximas ações (ordem de execução)

| Tarefa | Onde | O quê |
|--------|------|-------|
| **T-A2-009** | `analisador_estrutural_pontinhos.py` | Implementar canal 12 (K=11) |
| **T-A2-010** | `test_analisador_estrutural_pontinhos.py` | 5 novos testes para canal 12 |
| **T-A3-002** | `analisador_estrutural_pontinhos.py` | `extrair_stats_cadeias()` retornando 3 escalares |
| **T-A3-003** | `test_analisador_estrutural_pontinhos.py` | Testes dos 3 escalares |
| **T-A3-004** | `gerador_dados/jogo_pontinhos/v8/` | Criar pasta com 4 notebooks |
| **T-A3-005** | `v8/fase2_enriquecimento_local.ipynb` | Notebook de enriquecimento com 12 canais + 3 escalares |
| **T-A3-006** | `dados/profundidade_minimax_11_v7_adaptativo/` | Executar Fase 2 V8 nos 152 NPZs |
| **T-A3-007** | `v8/fase3_rerotulacao_databricks.ipynb` | Notebook Databricks p/ re-rotulação adaptativa |
| **T-A3-008** | `permutacoes_simetria_pontinhos.py` | 4 transformações coerentes (12 canais) |
| **T-A3-009** | `test_permutacoes_simetria_pontinhos.py` | Testes das 4 simetrias + K=11 |
| **T-A3-010** | `v8/fase4_augmentacao_simetria.ipynb` | Notebook de augmentação por sufixo |
| **T-A3-011** | `Treinamento_CNN_Pontinhos_V8.ipynb` | Métricas por `qtd_cadeias_longas` + ler sufixados |
| **T-A3-012** | `Analise_Dados_Adaptativo.ipynb` | Análise de distribuição de cadeias |

---

## Estado de execução — sessão 2026-05-14 (Pipeline V8 e documentação)

### Decisões de design tomadas e documentadas

Todas as decisões abaixo foram registradas em `docs/historico_decisoes.md` (entrada 2026-05-14 — Pipeline V8) e nos documentos de spec:

1. **Análise de distribuição de cadeias** (T-A3-001 — PENDENTE formalização): ~2,3% dos estados têm `profundidade_minima > 11`. Max observado = 18.
2. **3 campos escalares** (`qtd_cadeias_longas`, `total_caixas_cadeias_longas`, `tamanho_max_cadeia_longa`): adicionados ao schema NPZ v2-a3.
3. **Pipeline V8**: reorganizado em `gerador_dados/jogo_pontinhos/v8/` com 4 fases.
4. **Augmentação por sufixo**: arquivos `_refH`/`_refV`/`_r180` em disco (revisão de D5).
5. **Re-rotulação adaptativa**: schedule p=13/15/17/20 para ~17.449 estados.

### Documentação entregue nesta sessão

- **`specs/004-melhoria-geracao-dados-cnn/tasks.md`** — Fase A.3 adicionada (T-A3-001 a T-A3-012).
- **`specs/004-melhoria-geracao-dados-cnn/contracts/npz_schema.md`** — seção 3 (schema v2-a3 com 12 canais + 3 escalares) e fórmula de profundidade mínima.
- **`specs/004-melhoria-geracao-dados-cnn/PRD.md`** — §4.11 (Decisão D11.a–e) adicionado.
- **`specs/004-melhoria-geracao-dados-cnn/plan.md`** — sumário e tabela de arquivos atualizados.
- **`docs/historico_decisoes.md`** — entrada 2026-05-14 com análise completa e decisões.

### Próximas ações (ordem de execução)

| Prioridade | Tarefa | Onde | O quê |
|---|---|---|---|
| 1 | **T-A2-009** | `analisador_estrutural_pontinhos.py` | Canal 12 (K=11) |
| 2 | **T-A2-010** | `test_analisador_estrutural_pontinhos.py` | 5 testes canal 12 |
| 3 | **T-A3-002** | `analisador_estrutural_pontinhos.py` | `extrair_stats_cadeias()` |
| 4 | **T-A3-003** | `test_analisador_estrutural_pontinhos.py` | Testes dos 3 escalares |
| 5 | **T-A3-004/005** | `gerador_dados/.../v8/` | Estrutura V8 + notebook Fase 2 |
| 6 | **T-A3-006** | Dataset | Executar Fase 2 nos 152 NPZs |
| 7 | **T-A3-008/009** | `permutacoes_simetria_pontinhos.py` | Simetrias + testes |
| 8 | **T-A3-010** | `v8/fase4_augmentacao_simetria.ipynb` | Augmentação por sufixo |
| 9 | **T-A3-007** | Databricks | Notebook Fase 3 re-rotulação |
| 10 | **T-A3-011/012** | Notebooks | Treino e análise atualizados |
