# Plano de Implementação: Melhoria da geração de dados e arquitetura da CNN do Jogo dos Pontinhos

**Branch**: `004-melhoria-geracao-dados-cnn` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification em `specs/004-melhoria-geracao-dados-cnn/spec.md`
**PRD (fonte da verdade técnica)**: [PRD.md](./PRD.md)

> **Regra de resolução de divergências:** o PRD prevalece sobre o spec.md em qualquer divergência técnica. O `CLAUDE.md` na raiz do repositório prevalece em qualquer questão de processo (documentação viva, contrato CNN sincronizado backend↔frontend, nomenclatura por jogo).

---

## Sumário

Esta feature evolui o pipeline de dados e a arquitetura da CNN BoxNet v3 do Jogo dos Pontinhos (tabuleiro pequeno 4×3) em **fases sequenciais e isoladas** (uma mudança por vez) para atribuir causa de cada ganho/regressão. O entregável central é uma família de modelos TFLite versionados (`pontinhos_pequeno_p9_faseB.tflite`, …, `_faseF.tflite`) gerados a partir de um pipeline V8 em `gerador_dados/jogo_pontinhos/v8/` (4 fases: geração local + enriquecimento local + re-rotulação Databricks + augmentação por simetria) que produz NPZs com 758k amostras brutas / ~500k distintos, tensor `canais (N, 4, 3, 12) int8` pré-computado e 3 campos escalares de metadata de cadeias.

> **Revisão 2026-05-12 — Fase A.1 CONCLUÍDA com V7 DAC:** A geração usou o algoritmo DAC (Diversidade Adaptativa em Cascata) em vez do notebook V5/cotas especificado originalmente. O dataset produzido tem **758k amostras brutas / ~500k distintos** com distribuição bell-shaped emergente, salvo em `dados/profundidade_minimax_11_v7_adaptativo/` (152 NPZs). Dois bugs críticos de Bitboard foram corrigidos no notebook de Fase 2. Experimentos preliminares de treino com ground truth Minimax p=11 atingiram **63% de vitórias vs Minimax(p=6)** e **90,5% vs Minimax(p=3)**, indicando saturação arquitetural da BoxNet v3 (~74k params). O novo baseline de comparação para Fase B é **63% vs p=6** (não mais 38%).

> **Revisão 2026-05-14 — Pipeline V8 e Fase A.3:** análise de distribuição de cadeias em ~155.000 estados identificou que ~2,3% precisam de Minimax p>11 para rótulo correto (prof_min_max observado = 18). Decisões tomadas: (1) 3 novos campos escalares por estado (`qtd_cadeias_longas`, `total_caixas_cadeias_longas`, `tamanho_max_cadeia_longa`); (2) re-rotulação adaptativa no Databricks somente para esses 2,3% com schedule p=13/15/17/20; (3) augmentação por simetria movida para disco com sufixos `_refH`/`_refV`/`_r180` (608 NPZs totais); (4) pipeline reorganizado em `gerador_dados/jogo_pontinhos/v8/`. Ver PRD §4.11 e `docs/historico_decisoes.md` (entrada 2026-05-14 — Pipeline V8).

O plano cobre: (a) Fase A.1 — ✅ **CONCLUÍDA** — geração V7 DAC local (~25.288 partidas × 30 snapshots) + enriquecimento Fase 2 Databricks (Minimax p=7 → p=11) + experimentos preliminares de treino; (b) Fase A.2 — enriquecimento local com analisador estrutural (12 canais, incluindo canal 12 `paridade_cadeia_longa_impar`) + sobrescrita atômica + script de validação visual; (c) Fase A.3 — 3 campos escalares de cadeias + pipeline V8 reorganizado + re-rotulação adaptativa Databricks + augmentação por sufixo; (d) Fase B — treino com 5 canais geométricos, eliminando a `Lambda para_grid_de_caixas`; (e) Fase C — agora integrada na Fase A.3 (augmentação por sufixo); (f) Fase D — treino com 12 canais + atualização do contrato + vetores de referência; (g) Fase E — sample_weight refinado por Δ-top2 em t=12–17; (h) Fase F — value head AlphaZero-style com export TFLite policy-only; (i) Fases G/H condicionais.

> **Repriorização 2026-05-13**: análise da estagnação da CNN V8 (50% vs Minimax p=6, abaixo do baseline V7 de 63%) identificou que a causa raiz é a ausência de um bit de paridade global. Canal 12 (`paridade_cadeia_longa_impar`) e Fase C (espelhamento 4×) são as **próximas tarefas a executar**, com prioridade máxima, antes de qualquer novo ciclo de treino. Ver `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`.

---

## Contexto Técnico

**Linguagem/Versão**: Python 3.11+ (módulos backend Python e notebooks TensorFlow/Keras 2.15)
**Dependências principais**: `numpy`, `tensorflow==2.15.*` (Keras), `matplotlib` (validação visual), `pyspark` (Databricks no A.1), `scipy` (BFS interno se preferido), `pytest` para testes.
**Armazenamento**: NPZ em `dados/profundidade_minimax_11_v7_adaptativo/` (152 NPZs do dataset V7, gerados na Fase A.1 com Minimax p=11). TFLite versionado em `modelos/`.
**Testes**: `pytest` em `tests/unitarios/jogo_pontinhos/`.
**Plataforma alvo**: Databricks (cluster Spark V4) para A.1; máquina local (Windows + Python 3.11) para A.2; Colab T4 para Fases B–F; CI Linux para testes obrigatórios.
**Tipo de projeto**: backend Python (hub de jogos) + pipeline ML offline. **Frontend Flutter está fora do escopo desta spec** — é consumidor downstream apenas.
**Metas de performance**: TFLite final ≤ 200 KB; inferência mobile ≤ 5 ms/jogada; geração 500k em Databricks ≤ 4 h.
**Restrições**: contrato `contrato_codificacao_pontinhos.json` byte-a-byte idêntico backend↔frontend; sobrescrita atômica do A.2 (Ctrl+C tolerável); deduplicação obrigatória por `mat.tobytes()`.
**Escala/Escopo**: NPZ Fase A.1 = 758k amostras brutas / ~500k distintos (bell-shaped); NPZ Fase A.2 adiciona tensor `canais (N, 4, 3, 11) int8`; 4 simetrias × 758k ≈ 3M amostras de treino em memória (Fase C — ou ~2M se deduplicado antes da augmentação).

### Arquivos relevantes (espelha PRD §3.1)

#### Existentes — leitura/referência

| Arquivo | Papel | Modificação prevista |
|---|---|---|
| `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V4.ipynb` | Notebook V4 atual de geração (Databricks/PySpark, Minimax(p=9)) | Base para o V5 (clone + ajustes) — **mantido como está** |
| `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V5.ipynb` | Notebook V5 atual de treino (Colab, BoxNet v3, Lambda `para_grid_de_caixas`) | Base para o V6 (clone + ajustes) — **mantido como está** |
| `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py` | Lógica de jogo (matriz expandida, arestas canônicas) | Não modificado nesta feature |
| `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` | Supervisor Minimax | Não modificado nesta feature |
| `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` | Contrato de codificação backend↔frontend | **Modificado em Fase B (input `(4,3,5)`) e Fase D (input `(4,3,11)`)** |
| `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py` | Helper Python que aplica regras do contrato | **Atualizado nas Fases B e D para refletir novo input** |
| `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` | Teste obrigatório de paridade backend↔frontend | **Atualizado nas Fases B e D** |
| `dados/profundidade_minimax_11_v7_adaptativo/` | 152 NPZs com 758k amostras brutas / ~500k distintos — dataset V7 DAC (schema V2, Minimax p=11) | **Lidos pelo A.2 para enriquecimento com `canais` + `nomes_canais`** |
| `tmp_analise/analisa_padrao_erros.py` | Avaliador tático (Categoria A) | Não modificado — referência para gates |
| `tmp_analise/analisa_divergencia_estrategica.py` | Avaliador estratégico (Categoria B) | Não modificado — referência para gates |

#### Criados nesta feature

| Arquivo | Fase | Descrição |
|---|---|---|
| `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb` | A.1 ✅ | Fase 1 local V7 DAC: ~25.288 partidas × 30 snapshots; profundidade τ-adaptativa; Boltzmann sampling. Produz 152 NPZs em `dados/profundidade_minimax_11_v7_adaptativo/`. |
| `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py` | A.1 ✅ | Worker Python do V7 DAC (τ, Boltzmann, snapshots). |
| `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb` | A.1 ✅ | Fase 2 Databricks: calcula `melhor_jogada`, `score_melhor_jogada`, `depth_melhor_jogada` com Minimax p=7 → p=11. Inclui correção de 2 bugs críticos de Bitboard. |
| `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` | A.2 | Lê NPZs de `dados/profundidade_minimax_11_v7_adaptativo/`, computa `canais (N,4,3,11) int8`, regrava com `.tmp` + `os.replace()`. **Supersedido pelo v8/fase2** para 12 canais. |
| `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` | A.2 | Função `extrair_canais(M) -> (4,3,12) int8` + `extrair_stats_cadeias(M) -> (int,int,int)` + `NOMES_CANAIS` (12 entradas). |
| `gerador_dados/jogo_pontinhos/v8/fase1_geracao_local.ipynb` | A.3 | Referência para o notebook de geração V7 existente. Formaliza a Fase 1 dentro do pipeline V8. |
| `gerador_dados/jogo_pontinhos/v8/fase2_enriquecimento_local.ipynb` | A.3 | Enriquece 152 NPZs com canal 12 (`canais (N,4,3,12)`) + 3 escalares. Sobrescrita atômica. |
| `gerador_dados/jogo_pontinhos/v8/fase3_rerotulacao_databricks.ipynb` | A.3 | Databricks: re-rotula ~17.449 estados (prof_min > 11) com schedule p=13/15/17/20. PySpark `mapInPandas`. |
| `gerador_dados/jogo_pontinhos/v8/fase4_augmentacao_simetria.ipynb` | A.3 | Local: gera `*_refH.npz`, `*_refV.npz`, `*_r180.npz` para os 152 NPZs originais. Total: 608 NPZs. |
| `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py` | A.3/C | 4 transformações coerentes (matriz crua, `canais (4,3,12)`, scores, rótulo). K=11 preservado. |
| `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` | D | Ground truth `(matriz_crua, canais (4,3,12) int8)` para casos canônicos + ≥20 estados sorteados. |
| `notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V8.ipynb` | B/C/D/E/F | Sem `Lambda para_grid_de_caixas`; lê `canais (4,3,K)` + arquivos sufixados; métricas por `qtd_cadeias_longas`. |
| `scripts/pontinhos/validar_canais_visualmente.py` | A.2 ✅ | Gera 1 PNG por estado (150 DPI, paleta categórica, borda em fechadas, título canônico). |
| `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` | A.2 | Testa casos canônicos + canal 12 + `extrair_stats_cadeias`. |
| `tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py` | A.3/C | Testa as 4 simetrias coerentes (incluindo preservação de K=11). |
| `modelos/pontinhos_pequeno_p9_faseB.tflite` … `_faseF.tflite` | B–F | TFLite versionado por fase. |

#### Atualizados nesta feature

| Arquivo | Quando | Mudança |
|---|---|---|
| `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` | Fase B (versão refletindo `(4,3,5)`) e Fase D (versão refletindo `(4,3,11)`) | Atualização do input do TFLite + regra de derivação dos canais. **Cópia idêntica para o frontend (`arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`) NA MESMA PR.** |
| `docs/jogo_pontinhos/guia_geracao_dados.md` | Após cada fase com mudança operacional (A.1, A.2, B, D) | Novo formato de NPZ, regras de dedup, procedimento operacional dos notebooks. |
| `docs/historico_decisoes.md` | Após cada fase | Entrada datada com win-rates, métricas por faixa (PRD §2.5), diff de configuração; **snapshot do V7 DAC e resultados dos experimentos de treino ao fim do A.1**. |
| `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` | Fase B e Fase D | Cópia byte-a-byte do backend, mesma PR. *Repositório frontend é separado; instrução é regra de processo, não item de código deste backend.* |

---

## Verificação da Constituição

*PORTÃO: Deve ser aprovado antes da Fase 0 de pesquisa. Reverificar após o design da Fase 1.*

- [x] **I. Código Limpo**: módulos criados (`analisador_estrutural_pontinhos.py`, `permutacoes_simetria_pontinhos.py`) têm responsabilidade única (extração de canais; permutações de simetria). Sem duplicação de lógica de BFS — encapsulada num único helper interno. Nomes em pt-BR expressivos (`extrair_canais`, `aplicar_simetria_horizontal`).
- [x] **II. Tipagem Estática**: todas as funções públicas dos novos módulos terão type hints (`np.ndarray`, `tuple[int, int]`, `Literal["H", "V", "R180"]`). Pydantic não se aplica diretamente (não há fronteira de API web nesta feature), mas o **contrato JSON** desempenha papel equivalente — é o esquema declarativo que o teste de paridade backend↔frontend valida.
- [x] **III. Testes Unitários**: `test_analisador_estrutural_pontinhos.py` e `test_permutacoes_simetria_pontinhos.py` cobrem todos os casos canônicos (handout, double-cross, loop, 2 cadeias disjuntas, half-open chain, simetrias coerentes). Cobertura mínima 80% nos novos módulos. Determinísticos, < 1 s por teste.
- [x] **IV. Documentação**: docstrings em pt-BR em todas as funções públicas dos novos módulos. Atualização viva de `docs/historico_decisoes.md` após cada fase, `docs/jogo_pontinhos/guia_geracao_dados.md` quando o fluxo operacional mudar, e do contrato JSON nas Fases B e D (regra dura do `CLAUDE.md`).
- [x] **V. Idioma pt-BR**: nomes de funções, classes, variáveis, comentários, docstrings, mensagens de log, todos em pt-BR. Identificadores estabelecidos do TensorFlow/numpy ficam em inglês (`np.flip`, `tf.data.Dataset`, `model.fit`) — exceção justificada pelo Princípio V.

**Nenhuma violação detectada.** Tabela de Complexidade não preenchida.

---

## Estrutura do Projeto

### Documentação (esta feature)

```text
specs/004-melhoria-geracao-dados-cnn/
├── plan.md                      # Este arquivo (/speckit-plan output)
├── spec.md                      # Especificação (já passada por /speckit-clarify)
├── PRD.md                       # Fonte da verdade técnica
├── research.md                  # Fase 0 deste plano (resoluções de NEEDS CLARIFICATION + decisões herdadas)
├── data-model.md                # Fase 1 deste plano (entidades NPZ, canais, contratos)
├── quickstart.md                # Fase 1 deste plano (fluxo end-to-end do desenvolvedor)
├── contracts/
│   ├── npz_schema.md            # Esquema dos NPZ Fase A.1 e Fase A.2
│   ├── canais_estruturais.md    # Especificação algorítmica dos 11 canais
│   └── contrato_codificacao_v_faseB.json   # Snapshot do contrato pós-Fase B (referência interna)
└── tasks.md                     # Fase 2 (gerada por /speckit-tasks — NÃO criada por este comando)
```

### Código-fonte (raiz do repositório backend)

```text
arena-sagaz-backend/
├── gerador_dados/
│   └── jogo_pontinhos/
│       ├── analisador_estrutural_pontinhos.py        # (NOVO — Fase A.2)
│       ├── permutacoes_simetria_pontinhos.py         # (NOVO — Fase C)
│       ├── referencia_canais_pontinhos.json|.npz     # (NOVO — Fase D, ground truth)
│       ├── contrato_codificacao_pontinhos.json       # (MODIFICADO — Fases B e D)
│       ├── contrato_codificacao_pontinhos.py         # (MODIFICADO — Fases B e D)
│       ├── tabuleiro_pontinhos.py                    # (existente, não modificado)
│       ├── gerador_amostras_v7_pontinhos.py          # (NOVO — Fase A.1 ✅ worker V7 DAC)
│       └── minimax_pontinhos.py                      # (existente, não modificado)
├── notebooks/
│   └── jogo_pontinhos/
│       ├── Otimizacao_Topologia_Rede_V4.ipynb        # (existente, não modificado)
│       ├── Geracao_Amostras_v7_adaptativo.ipynb      # (NOVO — Fase A.1 ✅ Fase 1 local)
│       ├── Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb  # (NOVO — Fase A.1 ✅ Fase 2 Databricks)
│       ├── Enriquece_NPZ_Com_Canais.ipynb            # (NOVO — Fase A.2)
│       ├── Treinamento_CNN_Arena_Sagaz_V5.ipynb      # (existente, não modificado)
│       └── Treinamento_CNN_Arena_Sagaz_V6.ipynb      # (NOVO — Fases B, C, D, E, F)
├── scripts/
│   └── pontinhos/
│       └── validar_canais_visualmente.py             # (NOVO — Fase A.2)
├── tests/
│   └── unitarios/
│       └── jogo_pontinhos/
│           ├── test_contrato_codificacao_pontinhos.py        # (existente, ATUALIZADO Fases B, D)
│           ├── test_analisador_estrutural_pontinhos.py       # (NOVO — Fase A.2)
│           └── test_permutacoes_simetria_pontinhos.py        # (NOVO — Fase C)
├── modelos/
│   ├── pontinhos_pequeno_p9_faseB.tflite             # (NOVO — Fase B)
│   ├── pontinhos_pequeno_p9_faseC.tflite             # (NOVO — Fase C)
│   ├── pontinhos_pequeno_p9_faseD.tflite             # (NOVO — Fase D)
│   ├── pontinhos_pequeno_p9_faseE.tflite             # (NOVO — Fase E)
│   └── pontinhos_pequeno_p9_faseF.tflite             # (NOVO — Fase F)
├── docs/
│   ├── historico_decisoes.md                         # (MODIFICADO — entrada por fase)
│   └── jogo_pontinhos/
│       └── guia_geracao_dados.md                     # (MODIFICADO — fluxo A.1/A.2/V6)
└── dados/
    └── profundidade_minimax_11_v7_adaptativo/        # (152 NPZs do dataset V7 ✅; sobrescritos pelo A.2 com canais)
```

**Decisão de estrutura**: Single project (Python backend + notebooks ML offline). Toda nomenclatura de arquivos `pontinhos`-specific carrega o sufixo `_pontinhos` ou fica em pasta `jogo_pontinhos/`, conforme diretriz do `CLAUDE.md` (hub de jogos).

---

## Fase 0 — Pesquisa e resoluções

Veja `research.md` para o registro completo. Resumo:

- **NEEDS CLARIFICATION resolvidos no `/speckit-clarify` de 2026-05-07** (5 itens; ver `spec.md > Clarifications`):
  - Otimização de cluster Databricks → fora do escopo (herda V4, ad-hoc no momento da execução).
  - Implementação Flutter → fora do escopo (Dart puro registrado como diretriz, mas tratado em feature separada).
  - Formato dos PNGs de validação visual → 150 DPI, paleta categórica estável por canal, borda destacada para caixas fechadas, título canônico por boxnet.
  - Limite mínimo do canal `em_cadeia_longa` → manter ≥ 3 (canal único; K=11 inalterado).
  - Observabilidade durante notebooks → sem padrão obrigatório (cada notebook decide ad-hoc; resultados manuais em `docs/historico_decisoes.md`).

- **Decisões técnicas herdadas do PRD e revisadas na execução**:
  - ~~D1 (cobertura terminal `[0.15, 0.97]` + distribuição U-invertida com 5 buckets).~~ → **Substituído por V7 DAC**: distribuição bell-shaped emergente; sem quotas por faixa; meta única de ~500k distintos.
  - ~~D1.a (mix `STRAT_WEIGHTS`).~~ → **Substituído por Boltzmann sampling** com temperatura T(t) decrescente por fase do jogo.
  - ~~D1.b (deduplicação pré-populada com hashes legados).~~ → **V7 gera do zero** (sem reaproveitamento do legado); dedup por `mat.tobytes()` em memória.
  - **V7-DAC** (2026-05-08): profundidade adaptativa por τ = 4·c₃ + 2·c₂ + 0,5·c₁; schedule de temperatura T(t) por fase; 30 snapshots por partida (t=1..30). Ver `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`.
  - **V7-Bugs** (2026-05-12): 2 bugs críticos de Bitboard corrigidos no notebook de Fase 2 — (1) caixas pré-fechadas: verificar `(edges & mask) != mask` antes de contar; (2) offsets alpha-beta incremental: ajustar α/β com `−closed`/`+closed`. Ver PRD §4.1.5 e notebook `Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb`.
  - **V7-Treino** (2026-05-12): experimentos preliminares com p=11 indicam saturação arquitetural BoxNet v3 (~74k params). Melhor config: todas as 758k amostras (com duplicatas) → 63% vs p=6, 90,5% vs p=3.
  - D2 (NPZ pré-computa todos os 11 canais; canal 5 é `caixa_fechada` binário; campo auxiliar `nomes_canais (11,) U32`).
  - D3 (pipeline em 2 notebooks: A.1 geração local + Databricks, A.2 enriquecimento local; sobrescrita atômica `.tmp` + `os.replace()`).
  - D5 (augmentação 4× — não 8× — porque 4×3 não é quadrado).
  - D9 (sample_weight refinado por Δ-top2 em t=12–17, peso médio 1.05–1.15).
  - D10 (value head AlphaZero-style, descartada no export TFLite).

**Pendências de planejamento** (registradas em `research.md`, NÃO inventadas aqui):

1. Ordem exata dos passos dentro de uma célula do notebook A.1 (ex.: pré-popular set de hashes antes ou depois de carregar `COMPLEMENTO_POR_CELULA`?). Detalhe sem impacto de correção; resolver durante implementação.
2. Seed específica para o split treino/val/teste no V6 (sugestão: 42, alinhada com o V5; reabrir se não bater).
3. Valor inicial de **λ** na Fase F. PRD declara faixa `[0.1, 0.3]` com sugestão 0.1; a calibração final fica para o início da Fase F (grid search ad-hoc).

**Output**: `research.md` consolidando o que está acima.

---

## Fase 1 — Design e contratos

Veja `data-model.md` (esquema NPZ Fase A.1, NPZ Fase A.2, tensor `canais`), `contracts/canais_estruturais.md` (especificação algorítmica dos 11 canais espelhada do PRD §6) e `quickstart.md` (fluxo end-to-end do desenvolvedor para reproduzir cada fase).

---

## Decomposição por fase

### Ordem de execução estrita

```
Fase 0 (Análise de divergência estratégica) ✅ CONCLUÍDA em 2026-05-06
    ↓
Fase A.1 (Geração V7 DAC + enriquecimento p=11 + experimentos de treino) ✅ CONCLUÍDA em 2026-05-12
    ↓ gate atendido: 758k amostras brutas / ~500k distintos; campos melhor_jogada + score_melhor_jogada (p=11); bugs Bitboard corrigidos; snapshot em historico_decisoes.md
    ↓
Fase A.2 (Enriquecimento local com 11 canais)
    ↓ gate: validação visual de ≥30 estados; testes do analisador passam; nomes_canais byte-a-byte igual à constante
    ↓
Fase B (Treino com 5 canais geométricos, sem Lambda)
    ↓ gate: SC-F-05 (29-30 ≥ 95%); erros táticos ≤ 250; nenhum win-rate cai > 3pp
    ↓
Fase C (Augmentação 4×)
    ↓ gate: nenhum par "deveria→jogou" > 5%; não-regressão por faixa; vs C, vitórias ≥ Fase B
    ↓
Fase D (11 canais + contrato v2 + vetores de referência)
    ↓ gate: vs p=5 ≥ 70%; erros táticos ≤ 80; redução fatais ≥ 50%; faixa 29-30 ≥ 95%
    ↓
Fase E (sample_weight refinado em t=12–17)
    ↓ gate: fatais em t=[12,17] caem ≥ 25%; peso médio na faixa 1.05–1.15; nenhum peso > 1.20
    ↓
Fase F (Value head, TFLite policy-only)
    ↓ gate: contrato hash inalterado vs Fase D; MSE value ≤ 0.10; TFLite ≤ 200 KB; redução fatais ≥ 50% baseline
    ↓
Fases G/H (CONDICIONAIS — só executam se F não bater meta de SC-W-* ou SC-A-*)
```

**Cada fase só inicia após o gate da anterior atendido.** A.2 depende dos NPZs gerados em A.1 em `dados/profundidade_minimax_11_v7_adaptativo/`.

---

### Fase A.1 — Geração do dataset V7 DAC ✅ CONCLUÍDA (2026-05-12)

> **Nota:** Esta fase foi executada com o algoritmo **V7 DAC** (Diversidade Adaptativa em Cascata) — não com o notebook V5/cotas especificado originalmente. Os artefatos entregues diferem do escopo original; ver PRD §4.1.4 e `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`.

**Objetivo (executado)**: produzir 152 NPZs com ~758k amostras brutas / ~500k distintos cobrindo t=1–30 (distribuição bell-shaped emergente), supervisão Minimax p=11, schema V2. Diretório: `dados/profundidade_minimax_11_v7_adaptativo/`.

**Artefatos criados** (reais):
- `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb` — Fase 1: geração local DAC. ~25.288 partidas × 30 snapshots.
- `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py` — worker Python do V7 DAC.
- `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb` — Fase 2 Databricks: calcula `melhor_jogada`, `score_melhor_jogada`, `depth_melhor_jogada`. Inclui correção de 2 bugs críticos de Bitboard.
- `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md` — documento de design V7 (material do TCC).
- `docs/jogo_pontinhos/Aprimoramento_Geracao_Amostras_v7_adaptativo.md` — proposta de otimização Fase 2 via move ordering (não implementada; condicional ao tempo medido da Fase 2).

**Algoritmo V7 DAC** (resumo; ver `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`):
- **Profundidade adaptativa**: τ = 4·c₃ + 2·c₂ + 0,5·c₁ → p(τ) = clamp(1 + ⌈τ/4⌉, 1, 8).
- **Boltzmann sampling**: desempate por P(lance i) ∝ exp(score_i / T), com T(t) decrescente (T=1,5 abertura → T=0,2 endgame).
- **30 snapshots por partida**: t=1..30; t=0 e t=31 descartados.
- **Meta única**: ≥500k distintos (sem quotas por faixa; distribuição emergente).

**Bugs críticos corrigidos no Bitboard** (PRD §4.1.5; notebooks V5 anteriores afetados):
1. **Caixas pré-fechadas** (falsos positivos): verificação obrigatória `(edges & mask) != mask` antes de contar fechamento — sem ela, o Bitboard injeta pontos fantasmas e corrompe os scores.
2. **Offsets alpha-beta incremental**: ao chamar a subárvore, repassar α e β com offset de `−closed` (ou `+closed` para o adversário) — sem isso, ocorre poda prematura e o motor escolhe jogadas perdedoras.

**Dataset produzido** (distribuição real por qtd_traços):

| qtd_traços | Amostras Brutas | Amostras Distintas |
|---:|---:|---:|
| 1 | 25.288 | 31 |
| 2 | 25.288 | 465 |
| 3 | 25.288 | 4.475 |
| 4 | 25.288 | 17.247 |
| 5 | 25.288 | 23.432 |
| 6–17 | 25.288 cada | 24.851 – 25.276 (quase saturados) |
| 18 | 25.288 | 25.099 |
| 19 | 25.288 | 24.654 |
| 20 | 25.288 | 23.636 |
| 21 | 25.288 | 21.549 |
| 22 | 25.288 | 18.437 |
| 23 | 25.288 | 14.885 |
| 24 | 25.288 | 10.818 |
| 25 | 25.288 | 7.200 |
| 26 | 25.288 | 4.003 |
| 27 | 25.288 | 1.734 |
| 28 | 25.288 | 616 |
| 29 | 25.288 | 168 |
| 30 | 25.288 | 31 |
| **Total** | **758.640** | **~500.000** |

**Enriquecimento Fase 2** (executado duas vezes via `Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb`):
- Rodada 1: Minimax p=7 → `score_melhor_jogada` inicial.
- Rodada 2: Minimax p=11 → `score_melhor_jogada` final (fonte da verdade para treino). Campo `depth_melhor_jogada = 11`.

**Experimentos preliminares de treino** (antes da Fase A.2; ground truth p=11):

| Configuração | Dataset | vs Minimax p=3 | vs Minimax p=6 |
|---|---|---:|---:|
| **Todas as 758k amostras (com dup.)** | 758k brutas | **90,5%** | **63,0%** |
| Apenas distintos | ~500k únicos | ~87% | ~58% |
| Distintos + sample_weight (clip 20×) | ~500k únicos | ~88% | ~60% |
| Distintos + sample_weight (sem clip) | ~500k únicos | ~85% | ~57% |

**Melhor resultado**: todas as 758k amostras (incluindo duplicatas) → **90,5% vs p=3 e 63% vs p=6**. Este é o novo baseline de comparação para as Fases B+.

**Diagnóstico de saturação** (BoxNet v3, ~74k parâmetros): KLD Loss = 0,125; Optimal Move Accuracy estagnada em ~94,4%. A arquitetura atual atingiu seu teto. O gargalo não é mais a qualidade do dataset — é a capacidade da rede. Os canais estruturais (Fases B→D) e o Value Head (Fase F) são as alavancas restantes.

> **Atenção (avaliação de partida):** verificar amostras de que a CNN entregou 2 caixas ao Minimax para capturar cadeias longas no próximo turno — esse é sacrifício estratégico correto, não erro tático.

**Atualizações de contrato**: nenhuma nesta fase.

**Gate de saída A.1 (ATENDIDO)**:
1. ✅ ~758k amostras brutas gravadas em 152 NPZs.
2. ✅ ~500k distintos confirmados (auditoria pós-geração).
3. ✅ Cobertura t=1–30; campos `melhor_jogada` e `score_melhor_jogada` preenchidos.
4. ✅ 2 bugs críticos de Bitboard corrigidos e aplicados.
5. ✅ Snapshot em `docs/historico_decisoes.md` (entrada 2026-05-08).

---

### Fase A.2 — Enriquecimento local (11 canais)

**Objetivo**: enriquecer cada NPZ do diretório com `canais (N,4,3,11) int8` + `nomes_canais (11,) U32`, via sobrescrita atômica.

**Arquivos criados**:
- `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb`.
- `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` com:
  - Constante `NOMES_CANAIS: tuple[str, ...] = ("aresta_topo", "aresta_base", "aresta_esquerda", "aresta_direita", "caixa_fechada", "eh_grau3", "eh_grau2", "em_cadeia_curta", "em_cadeia_longa", "em_loop", "em_cadeia_aberta_uma_ponta", "paridade_cadeia_longa_impar")`. **N_CANAIS = 12** (revisão 2026-05-13).
  - Função pública `extrair_canais(matriz_estado: np.ndarray) -> np.ndarray` retornando `(4, 3, 11) int8` na ordem canônica.
  - Helpers internos: `_grau`, `_caixa_fechada`, `_componentes_grau2_dual`, `_classifica_componente` (path/loop/T-complexo), `_marca_half_open`.
- `scripts/pontinhos/validar_canais_visualmente.py` com parâmetros `--diretorio-npz`, `--qtd-tracos`, `--generation-mode`, `--n-amostras`, `--saida`, `--seed`.
- `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`.

**Arquivos modificados**:
- `dados/profundidade_minimax_11_v7_adaptativo/*.npz` — todos sobrescritos in-place via `.tmp` + `os.replace()` adicionando `canais` + `nomes_canais`.
- `docs/jogo_pontinhos/guia_geracao_dados.md` — seção nova "Fase A.2 — Enriquecimento local".
- `docs/historico_decisoes.md` — entrada Fase A.2 (consolidando D2/D3/D4 com data efetiva).

**Layout do notebook A.2** (etapas):
1. Recebe `--diretorio-npz` (default `dados/profundidade_minimax_11_v7_adaptativo`).
2. Para cada NPZ no diretório (em ordem):
   a. Carrega TODOS os campos atuais.
   b. Computa `canais = np.stack([extrair_canais(estados[i]) for i in range(N)], axis=0).astype(np.int8)`.
   c. Constrói `nomes_canais = np.array(NOMES_CANAIS, dtype="U32")`.
   d. Grava arquivo `<original>.tmp` com TODOS os campos antigos + `canais` + `nomes_canais`.
   e. `os.replace(<original>.tmp, <original>)` (atômico).
3. Resumo: arquivos processados, tempo total, amostras/s.

**Sobrescrita atômica** (FR-B-03, NFR-06): nunca corrompe NPZ original mesmo com Ctrl+C — o `.tmp` é descartado e a próxima execução rerode in-place.

**Idempotência por sobrescrita** (FR-B-04): se `canais`/`nomes_canais` já existirem, recalcula e substitui (sem merge).

**Especificação algorítmica dos 11 canais**: ver `contracts/canais_estruturais.md` (espelha PRD §6.2–6.7). Síntese:
- **Canais 1–4** (`aresta_*`): leitura direta da matriz expandida `(2r, 2c+1)`, `(2r+2, 2c+1)`, `(2r+1, 2c)`, `(2r+1, 2c+2)` — `1` se valor `9`.
- **Canal 5** (`caixa_fechada`): `M[2r+1, 2c+1] == 1`. Domínio do dataset é `{0, 1, 8, 9}` (sem `-1`) — binário.
- **Canais 6–7** (`eh_grau3`, `eh_grau2`): grau (soma binária dos 4 vizinhos = 9) em caixas não-fechadas.
- **Canais 8–10** (`em_cadeia_curta`, `em_cadeia_longa`, `em_loop`): BFS em grafo dual (nós = caixas grau-2; arestas = grau-2 vizinhos com aresta livre entre eles); classificar componente como path (curta/longa por comprimento) ou loop. T-complexo cai em `em_cadeia_longa`.
- **Canal 11** (`em_cadeia_aberta_uma_ponta`): cadeia (não loop) com exatamente 1 ponta conectada a uma caixa grau-3.

**Validação visual** (FR-C, gate de saída A.2):
- Script `scripts/pontinhos/validar_canais_visualmente.py` gera 1 PNG por estado sorteado.
- **Layout fixo**: cabeçalho com metadados; primeira linha = matriz crua dupla (arestas + label canônica em verde / heatmap de scores); segunda linha = 5 canais geométricos como boxnets 4×3 binários; terceira linha = 6 canais estruturais como boxnets 4×3 binários.
- **Cada boxnet com título** acima exatamente igual a `NOMES_CANAIS[k]` (ex.: `aresta_topo`, `caixa_fechada`, `em_cadeia_longa`).
- **150 DPI**, **paleta categórica com 1 cor distinta por canal estável entre execuções**, **caixas fechadas com borda destacada em todos os 11 boxnets** (FR-C-02a).
- Filtros operacionais: `--qtd-tracos` (default todos), `--generation-mode` (default todos), `--n-amostras` (default 30), `--seed` (default 42).

**Testes obrigatórios** (`test_analisador_estrutural_pontinhos.py`):
1. Matriz vazia (5 geométricos zerados; 6 estruturais zerados).
2. Caixa fechada em `(r, c)` → canal 5 = 1; canais 6–11 = 0 nessa célula.
3. Double-cross do Buchin Fig. 2 → `em_cadeia_aberta_uma_ponta` correto.
4. Loop fechado de 4 caixas → `em_loop` = 1 nas 4 caixas; canais 8–9 = 0 nelas.
5. 2 cadeias longas disjuntas (≥ 6 caixas total) → todas marcadas em `em_cadeia_longa`.
6. Half-open chain (1 ponta capturável) → canal 11 = 1 em todos os nós da cadeia.
7. Half-open chain mista com double-cross do Buchin.
8. Estado de handout (Berlekamp).
9. Paridade `nomes_canais`: `np.load(npz)["nomes_canais"]` byte-a-byte igual à constante `NOMES_CANAIS`.
10. Determinismo: `extrair_canais(M)` chamado duas vezes retorna tensor idêntico.

Localização: `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`. Roda no CI (pytest).

**Atualizações de contrato**: nenhuma (contrato muda só na Fase B e Fase D).

**Atualizações em `docs/historico_decisoes.md`** (Fase A.2):
- Data efetiva de execução do A.2.
- Tempo total + amostras/s do enriquecimento.
- Confirmação visual de ≥ 30 PNGs revisados (3 faixas × ≥ 10 amostras: 12–17, 24–28, 29–30).
- Lista de casos canônicos verificados (handout, double-cross, loop simples, 2 cadeias longas disjuntas).
- Hashes dos NPZs antes e depois do enriquecimento (auditoria de integridade).

**Atualizações em `docs/jogo_pontinhos/guia_geracao_dados.md`**:
- Seção nova: "Fase A.2 — Enriquecimento local (11 canais)" com comando do notebook + procedimento de validação visual.
- Atualização do formato do NPZ (agora com `canais` + `nomes_canais`).

**Gate de saída A.2** (transcrito de FR-B, FR-C, SC-D, PRD §5):
1. Cada NPZ no diretório tem `canais (N,4,3,11) int8` + `nomes_canais (11,) U32`.
2. `nomes_canais` byte-a-byte igual à constante `NOMES_CANAIS` em **todos** os NPZs.
3. Total ≥ 500.000 únicos pós-enriquecimento (não pode ter regredido — sobrescrita preserva matriz crua).
4. Validação visual manual de ≥ 30 estados nas faixas 12–17, 24–28 e 29–30 (incluindo casos canônicos).
5. `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` passa.

---

### Fase B — Treino com 5 canais geométricos (sem `Lambda`)

**Objetivo**: re-treinar a CNN sobre o NPZ Fase A.2 usando **apenas os 5 canais geométricos** (slice `canais[..., :5]`), eliminando a `Lambda para_grid_de_caixas` do V5. Atribuição isolada do ganho da cobertura terminal.

**Arquivos criados**:
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` (clone do V5 + mudanças abaixo).
- `modelos/pontinhos_pequeno_p9_faseB.tflite`.

**Arquivos modificados**:
- `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` — versão atualizada para input `(4, 3, 5)` na Fase B.
- `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py` — helper Python espelhando o JSON.
- **`arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` — cópia idêntica byte-a-byte na MESMA PR** (regra do `CLAUDE.md`).
- `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` — atualizado para validar nova versão.
- `docs/historico_decisoes.md` — entrada Fase B.
- `docs/jogo_pontinhos/guia_geracao_dados.md` — seção V6 (substitui referências ao V5).

**Modificações sobre o V5**:
1. Carregamento do NPZ lê o campo `canais (N,4,3,11) int8` (não mais `estados (N,9,7) int8` cru).
2. `entrada_modelo = canais[..., :5]` (slice dos 5 canais geométricos).
3. **`Lambda para_grid_de_caixas` REMOVIDA do grafo Keras**. Input do modelo passa de `(9, 7, 1)` para `(4, 3, 5)` direto.
4. Stem Conv 3×3 (32) recebe 5 canais em vez do tensor pós-Lambda; arquitetura equivalente em capacidade ao V5.
5. Stratified split por fase do jogo recomputado a partir dos 4 canais de aresta (canais 1–4 ainda contêm essa informação).
6. **Bloco de avaliação por faixa de preenchimento (PRD §2.5)** ao final do treino: tabela top-1/top-3/top-5 por faixa (5–11, 12–17, 18–23, 24–28, 29–30).

**Atualizações de contrato — Fase B** (FR-D-03, FR-D-04, FR-I-02, NFR-04):
- Versão (campo `versao`) sobe para `2.faseB` (ou esquema equivalente) refletindo input `(4, 3, 5)`.
- Documenta a regra de derivação dos 5 canais geométricos a partir da matriz crua `(9, 7) int8` normalizada (espelhando `contracts/canais_estruturais.md` §1–4).
- **CÓPIA IDÊNTICA byte-a-byte para `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` NA MESMA PR** (regra dura do `CLAUDE.md`; teste `test_contrato_codificacao_pontinhos.py` falha o merge se divergir).

**Testes obrigatórios**:
- `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` passa (nova versão).
- `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` continua passando.
- TFLite gerado: input shape `(1, 4, 3, 5)`; output shape `(1, 31)`; tamanho ≤ 200 KB (NFR-01).
- Avaliação: `Avaliacao_CNN_vs_Minimax.ipynb` em 200 partidas vs cada Minimax(p=3, p=5, p=6); `analisa_padrao_erros.py` e `analisa_divergencia_estrategica.py` reexecutados.

**Atualizações em `docs/historico_decisoes.md`** (Fase B):
- Data efetiva.
- Tabela comparativa Baseline vs Fase B: win-rates (vs p=1/p=3/p=5/p=6), total de erros táticos, divergências fatais por partida, fatais em meio (t∈[10,24]), fração de perdidas com fatal precoce.
- Tabela de accuracy por faixa (PRD §2.5): top-1/top-3/top-5 em 5–11, 12–17, 18–23, 24–28, 29–30.
- Diff de configuração: `(9,7,1) → (4,3,5)` direto (sem Lambda); fonte do tensor é `canais[..., :5]` do NPZ.
- Diagnóstico de gap residual: quanto da meta final foi atingida apenas com cobertura terminal; quanto resta para Fases C/D.

**Atualizações em `docs/jogo_pontinhos/guia_geracao_dados.md`**:
- Substituir referências ao V5 por V6 onde aplicável.
- Documentar que o tensor de entrada agora vem do NPZ enriquecido (não mais derivado por Lambda).

**Gate de saída B** (transcrito de FR-D + FR-J + SC-W + SC-F + PRD §5):
1. **Não-regressão global**: nenhum win-rate (p=3, p=5, p=6) cai > 3pp em relação ao baseline (Fase 0).
2. **Redução tática mínima**: total de erros reais (`analisa_padrao_erros.py`) cai pelo menos 50% (de 505 para ≤ 250).
3. **SC-F-05 (gate forte)**: top-1 accuracy na faixa 29–30 traços ≥ 95% — abaixo disso a fase falha.
4. **Não-regressão por faixa**: nenhuma faixa cai > 2pp em accuracy vs baseline.
5. **Contrato preservado backend↔frontend**: `test_contrato_codificacao_pontinhos.py` passa (hash byte-a-byte igual entre as duas cópias do JSON).
6. **TFLite ≤ 200 KB; latência ≤ 5 ms/jogada** (NFR-01, NFR-02).

---

### Fase C — Augmentação 4× por simetria

**Objetivo**: eliminar viés posicional (PRD §1.3, §2.4.6) treinando sobre dataset 4× expandido em memória (identidade + reflexão H + reflexão V + rotação 180°).

**Arquivos criados**:
- `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py`.
- `tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py`.
- `modelos/pontinhos_pequeno_p9_faseC.tflite`.

**Arquivos modificados**:
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` — bloco de augmentação executado após carregamento do NPZ, antes do split.
- `docs/historico_decisoes.md` — entrada Fase C.

**Conteúdo de `permutacoes_simetria_pontinhos.py`**:
- 4 funções de simetria espacial: `aplicar_identidade`, `aplicar_reflexao_horizontal`, `aplicar_reflexao_vertical`, `aplicar_rotacao_180`.
- Permutação coerente:
  - Sob H: `aresta_esquerda ↔ aresta_direita` (canais 3 e 4 trocam de slot); demais canais preservam slot, conteúdo espacial é refletido em `c → n_cols-1-c`.
  - Sob V: `aresta_topo ↔ aresta_base` (canais 1 e 2 trocam de slot).
  - Sob R180: ambas as trocas.
  - Canal 5 (`caixa_fechada`) e canais 6–11 (estruturais binários) **não trocam de slot** — apenas conteúdo espacial é refletido/rotacionado.
- Tabelas de permutação de **labels canônicos** `H_r_c` / `V_r_c` para as 4 simetrias, derivadas geometricamente.
- Função `aplicar_simetria_completa(canais, scores, rotulo, simetria) -> tuple`.

**Modificações sobre o V6** (Fase C):
- Bloco de augmentação ao carregar dataset Fase B (com `canais[..., :5]`):
  ```python
  ds_aug = []
  for sim in [identidade, ref_h, ref_v, rot_180]:
      ds_aug.append(aplicar_simetria_completa(canais_5, scores, rotulos, sim))
  # Resultado: 500k * 4 = 2M amostras
  ```
- **Preferência por gerador `tf.data`** (ver Riscos abaixo): se RAM apertar no Colab, materializar como `tf.data.Dataset` com `map(aplicar_simetria_aleatoria)` em vez de empilhar em memória os 2M tensores.
- Treino sobre dataset 4× ainda com **só 5 canais geométricos** (Fase C isola o ganho da augmentação).

**Testes obrigatórios** (`test_permutacoes_simetria_pontinhos.py`):
1. Identidade preserva tensor, scores e label.
2. Reflexão H aplicada 2× retorna ao original (involução).
3. Reflexão V aplicada 2× retorna ao original.
4. R180 = ref_H ∘ ref_V.
5. Sob ref_H, label `H_2_1 → H_2_1` (col 1 → col `n_cols-1-1 = 1` em 4×3? validar geometricamente).
6. Sob ref_H, canais 3 e 4 trocam de slot e conteúdo é refletido.
7. Sob ref_V, canais 1 e 2 trocam de slot.
8. Sob ref_H aplicada a `canais[..., 5:]` (estruturais), nenhum canal troca de slot — só conteúdo espacial é refletido.
9. Coerência: aplicando simetria a `(matriz_crua, scores, label, canais)` e depois extraindo canais via `extrair_canais(matriz_crua_simetrica)` produz resultado byte-a-byte igual a aplicar a simetria diretamente sobre `canais` originais.
10. Sample_weight de Fase E (se já presente) não é distorcido pela augmentação.

**Atualizações de contrato**: nenhuma (Fase C não muda input/output do TFLite — apenas treino).

**Atualizações em `docs/historico_decisoes.md`** (Fase C):
- Data efetiva.
- Tabela comparativa Fase B vs Fase C: win-rates, distribuição dos pares "deveria→jogou" (especialmente `H_2_1 → V_1_0`, `H_2_3 → H_0_3` etc.), tabela de accuracy por faixa.
- Confirmação de que nenhum par individual representa > 5% do total de erros.
- Decisão sobre Fase D: registrar se metas finais já foram batidas (cenário X1) ou se Fase D continua obrigatória (cenário X3 — confirmado em §2.4.7 do PRD).

**Gate de saída C** (transcrito de FR-E + FR-J + PRD §5):
1. Nenhum par "deveria→jogou" individual > 5% do total de erros.
2. **Não-regressão estrita**: nenhum win-rate cai em relação à Fase B.
3. **Não-regressão por faixa**: nenhuma faixa cai > 2pp em accuracy. Faixa 29–30 permanece ≥ 95%.
4. `pytest tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py` passa.

---

### Fase D — Treino com 11 canais + contrato v2 + vetores de referência

**Objetivo**: incorporar os 6 canais estruturais ao input do modelo. Atualizar contrato para input `(4, 3, 11)`. Gerar **vetores de referência** que servem como ground truth para futura paridade com clientes externos (ex.: porte Dart, **fora do escopo**).

**Arquivos criados**:
- `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` (ou `.npz`, decisão durante implementação).
- `modelos/pontinhos_pequeno_p9_faseD.tflite`.

**Arquivos modificados**:
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` — slice passa de `canais[..., :5]` para `canais[..., :11]`. Input do modelo: `(4, 3, 11)`.
- `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` — **versão 2** (input `(1, 4, 3, 11)`).
- `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py` — helper atualizado.
- **`arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` — cópia idêntica byte-a-byte na MESMA PR**.
- `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` — atualizado.
- `docs/historico_decisoes.md` — entrada Fase D.
- `docs/jogo_pontinhos/guia_geracao_dados.md` — atualização para 11 canais.

**Modificações sobre o V6** (Fase D):
- Slice: `entrada_modelo = canais[..., :11]` (tensor inteiro, todos os 11 canais).
- Input do modelo Keras passa de `(4, 3, 5)` para `(4, 3, 11)`.
- Stem Conv 3×3 (32) cresce ~6×32 = 192 parâmetros (negligível, NFR-01 com folga).
- Demais blocos do modelo inalterados.
- Augmentação 4× da Fase C **mantida** (Fase D = Fase C + canais estruturais).

**Vetores de referência** (FR-F-03, US3 cenário 3): artefato versionado contendo pares `(matriz_crua (9,7) int8, canais (4,3,11) int8)` para:
- Estado vazio (todas as arestas livres).
- Caixa fechada simples.
- Double-cross do Buchin Fig. 2.
- Loop fechado de 4 caixas.
- 2 cadeias longas disjuntas.
- Half-open chain (1 ponta capturável, 1 ponta livre).
- Handout (Berlekamp).
- ≥ 20 estados sorteados em t ∈ {14, 17, 24, 29}.

Formato: `referencia_canais_pontinhos.json` (legível) ou `.npz` (compacto). Decisão durante implementação — o JSON é mais auditável; o NPZ comprime melhor. Recomendação inicial: **`.json`** (mais transparente em diff de PR).

**NÃO inclui porte Dart no plano** (Flutter está fora do escopo desta spec — ver Clarifications 2026-05-07).

**Atualizações de contrato — Fase D** (FR-F-02, FR-I-02, NFR-04):
- Versão sobe para `2.faseD` (ou esquema equivalente) refletindo input `(1, 4, 3, 11) int8`.
- Documenta regra de derivação dos 11 canais (espelhando `contracts/canais_estruturais.md` §1–11 / PRD §6.2–6.7).
- **CÓPIA IDÊNTICA byte-a-byte para o frontend NA MESMA PR**.

**Testes obrigatórios**:
- `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` passa (versão 2).
- TFLite gerado: input `(1, 4, 3, 11)`, output `(1, 31)`, tamanho ≤ 200 KB.
- Avaliação completa (200 partidas × 3 adversários) + `analisa_*`.

**Atualizações em `docs/historico_decisoes.md`** (Fase D):
- Data efetiva.
- Tabela comparativa Fase C vs Fase D: win-rates, divergências fatais por partida, fração de partidas perdidas com fatal precoce, fração sem nenhum fatal.
- Tabela de accuracy por faixa (PRD §2.5).
- Lista dos casos canônicos cobertos pelo `referencia_canais_pontinhos.json`.

**Gate de saída D** (transcrito de FR-F + FR-J + SC-W + PRD §5):
1. Vitórias vs Minimax(p=5) ≥ 70% (SC-W-02).
2. Total de erros reais ≤ 80 (SC-A-01).
3. Divergências fatais por partida caem ≥ 50% em relação ao baseline da Fase 0 (SC-B-01).
4. Faixa 29–30 ≥ 95% (SC-F-05); nenhuma faixa regride > 2pp vs Fase C.
5. Contrato byte-a-byte idêntico backend↔frontend; teste passa.
6. `referencia_canais_pontinhos.json` versionado e documentado.

---

### Fase E — sample_weight refinado por Δ-top2 em t=12–17

**Objetivo**: empurrão sutil (~10% de peso médio extra) em amostras da faixa crítica de meio-jogo modulado por Δ_top2 = `scores[i, top1] − scores[i, top2]`.

**Arquivos criados**:
- `modelos/pontinhos_pequeno_p9_faseE.tflite`.

**Arquivos modificados**:
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` — bloco de cálculo de `Δ_top2` + função de peso + `model.fit(sample_weight=...)`.
- `docs/historico_decisoes.md` — entrada Fase E.

**Modificações sobre o V6** (Fase E):
- Cálculo de `Δ_top2`:
  ```python
  scores_validos = np.where(scores > -1e8, scores, -np.inf)
  ordem = np.argsort(scores_validos, axis=1)[:, ::-1]   # top1 primeiro
  top1 = np.take_along_axis(scores_validos, ordem[:, 0:1], axis=1)
  top2 = np.take_along_axis(scores_validos, ordem[:, 1:2], axis=1)
  delta_top2 = (top1 - top2).squeeze(-1)
  delta_top2 = np.where(np.isinf(delta_top2), 0.0, delta_top2)   # empate em top1 → 0
  ```
- Função de peso (FR-G-02):
  ```python
  alfa = 0.03   # sugestão inicial; calibrar para peso médio na faixa-alvo ≈ 1.10
  n_tracos = contar_tracos_preenchidos(canais)   # soma dos canais 1-4
  na_faixa = (n_tracos >= 12) & (n_tracos <= 17)
  pesos = np.where(na_faixa, np.clip(1.0 + alfa * delta_top2, 1.0, 1.20), 1.0).astype(np.float32)
  ```
- Validação (FR-G-03): histograma de `pesos` na faixa-alvo; média entre 1.05 e 1.15; `pesos.max() ≤ 1.20`.
- `model.fit(..., sample_weight=pesos)`.

**Sem mudança de contrato**, sem mudança de arquitetura.

**Testes obrigatórios**:
- Teste unitário inline no notebook: histograma + `assert peso_medio_faixa ∈ [1.05, 1.15]`, `assert pesos.max() ≤ 1.20`.
- Avaliação completa.

**Atualizações em `docs/historico_decisoes.md`** (Fase E):
- Data efetiva.
- Valor de `α` calibrado.
- Histograma de pesos na faixa-alvo (média + p95).
- Tabela comparativa Fase D vs Fase E em divergências fatais em t∈[12,17].
- Tabela de accuracy por faixa.

**Gate de saída E** (transcrito de FR-G + FR-J + PRD §5):
1. Nenhum win-rate cai > 2pp em relação à Fase D.
2. Divergências fatais em t∈[12, 17] caem ≥ 25% em relação à Fase D.
3. Nenhuma faixa cai > 2pp em accuracy. Faixa 29–30 ≥ 95%.
4. Peso médio na faixa-alvo entre 1.05 e 1.15; nenhum peso > 1.20.

---

### Fase F — Value head AlphaZero-style (TFLite policy-only)

**Objetivo**: adicionar value head ao modelo Keras (regressão de Q* normalizado em `[-1, +1]`) atuando como regularizador estrutural — multi-task. **Value head é descartada no export TFLite** (contrato preservado).

**Arquivos criados**:
- `modelos/pontinhos_pequeno_p9_faseF.tflite` (apenas policy head).

**Arquivos modificados**:
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` — célula do modelo Keras com dual-output + loss conjunta + export filtrado.
- `docs/historico_decisoes.md` — entrada Fase F.

**Modificações sobre o V6** (Fase F):
- Branch dedicado a partir do último bloco residual (FR-H-01):
  ```python
  # Policy head (existente)
  policy_branch = layers.GlobalAveragePooling2D()(ult_residual)
  policy_flat = layers.Flatten()(policy_branch)
  policy_dense = layers.Dense(96, activation='relu')(policy_flat)
  policy_dense = layers.Dropout(0.5)(policy_dense)
  policy_pred = layers.Dense(31, activation='softmax', name='policy_pred')(policy_dense)

  # Value head (NOVA)
  value_branch = layers.Conv2D(16, (1,1), activation='relu')(ult_residual)
  value_flat = layers.Flatten()(value_branch)
  value_dense = layers.Dense(64, activation='relu')(value_flat)
  value_pred = layers.Dense(1, activation='tanh', name='value_pred')(value_dense)

  modelo_treino = Model(inputs, [policy_pred, value_pred])
  ```
- Targets:
  - Policy: `softmax(scores / T)` com T=1.0 (existente).
  - Value (FR-H-02): `value_target = clip(score_max / 6.0, -1.0, +1.0)`.
- Loss conjunta (FR-H-03):
  ```python
  modelo_treino.compile(
      optimizer=Adam(lr),
      loss={'policy_pred': 'kld', 'value_pred': 'mse'},
      loss_weights={'policy_pred': 1.0, 'value_pred': lambd},   # lambd ∈ [0.1, 0.3], inicial 0.1
  )
  ```
  Sample_weight da Fase E aplica-se **apenas à policy** (a value loss usa peso uniforme 1.0).
- **Export TFLite descartando value head** (FR-H-04):
  ```python
  modelo_export = Model(inputs, policy_pred)   # value_pred descartado
  converter = tf.lite.TFLiteConverter.from_keras_model(modelo_export)
  ...
  ```

**Sem mudança de contrato** — JSON byte-a-byte idêntico ao da Fase D (FR-H-04, NFR-04).

**Testes obrigatórios**:
- `test_contrato_codificacao_pontinhos.py` passa: hash do JSON é idêntico ao da Fase D.
- TFLite tem input `(1, 4, 3, 11)`, output **único** `(1, 31)`, tamanho ≤ 200 KB.
- MSE final do `value_pred` em validação ≤ 0.10 (gate de convergência da value head).

**Atualizações em `docs/historico_decisoes.md`** (Fase F):
- Data efetiva.
- Valor de `λ` calibrado (entre 0.1 e 0.3).
- MSE final do `value_pred` (treino + validação).
- Tabela comparativa Fase E vs Fase F: win-rates, divergências fatais, fração "Sem fatal" das partidas perdidas.
- Tabela de accuracy por faixa.
- Confirmação de hash idêntico do contrato em relação à Fase D.

**Gate de saída F** (transcrito de FR-H + FR-J + SC + PRD §5):
1. Nenhum win-rate cai > 2pp em relação à Fase E.
2. MSE final do `value_pred` em validação ≤ 0.10.
3. Divergências fatais por partida caem ≥ 50% em relação ao baseline da Fase 0.
4. Contrato byte-a-byte idêntico ao da Fase D (`test_contrato_codificacao_pontinhos.py` passa).
5. TFLite ≤ 200 KB; latência ≤ 5 ms/jogada.
6. Faixa 29–30 ≥ 95%; nenhuma faixa regride > 2pp vs Fase E.

---

### Fases G/H — Condicionais

**G (Hard-target em ≥26 traços)** e **H (Loss assimétrica calibrada com BCE)** são **blocos condicionais**: só executam se a Fase F não bater meta de SC-W-* ou SC-A-*.

**Gate de entrada para G**:
- Win-rate vs p=5 < 70% **ou** win-rate vs p=6 < 60% **ou** total de erros táticos > 80 ao final da Fase F.

**Gate de entrada para H**:
- Mesmas condições, mas medidas ao final da Fase G.

**Detalhamento**: ver PRD §5 (Fases G, H). Não detalhamos aqui porque dependem de medições da Fase F. Quando ativadas, mantêm o esquema do plano (criação de TFLite versionado `_faseG.tflite` / `_faseH.tflite`, entrada em `docs/historico_decisoes.md`, gates de não-regressão).

---

## Riscos e mitigações

> Espelha PRD §7, com ênfase nos itens explicitamente destacados pelo usuário.

| Risco | Severidade | Mitigação |
|---|---|---|
| **Bug no analisador estrutural envenena treino (Fase A.2 → contamina B/C/D/E/F)** | **Alta** | **Gate de validação visual obrigatório**: PNGs gerados pelo `validar_canais_visualmente.py` (150 DPI, paleta categórica, borda em fechadas) com **revisão manual de ≥ 30 estados nas faixas 12–17, 24–28 e 29–30** antes de prosseguir para Fase B. Testes unitários cobrindo casos canônicos (handout, double-cross, loop, 2 cadeias longas, half-open). Falha de qualquer item bloqueia a Fase B. |
| **Augmentação 4× estourar RAM no Colab T4 (500k × 4 = 2M tensores em memória, Fase C)** | Média | **Preferir gerador `tf.data` com `map(aplicar_simetria_aleatoria)` em vez de materializar 2M tensores em memória.** Ordem: tentar materializar em `numpy` primeiro (mais rápido); se OOM, migrar para `tf.data.Dataset.from_tensor_slices(...).map(...)` com lazy evaluation. |
| **Mudança de contrato sem cópia para o frontend (Fases B e D)** | **Alta** | **Regra do `CLAUDE.md` é dura**: alteração no `contrato_codificacao_pontinhos.json` ⇒ cópia idêntica para `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` **NA MESMA PR**. O teste `test_contrato_codificacao_pontinhos.py` falha o merge se hashes divergirem. CI bloqueia. |
| Modelo cresce demais com 11 canais e perde performance mobile (Fase D) | Baixa | Stem inicial passa de Conv(5→32) para Conv(11→32) — apenas +1.7k parâmetros. NFR-01 (≤ 200 KB) tem folga grande sobre os ~100 KB atuais. |
| Win-rate vs p=1 cai (CNN ficou "muito sofisticada", erra contra jogador aleatório) | Baixa | Manutenção de 10% de amostras de abertura (5–11 traços) na D1. Gate de não-regressão por fase em SC-W-04 (vs p=1 ≥ 92%). |
| Tempo de geração 500k Minimax(p=9) no Databricks excede orçamento (NFR-03 = 4h) | Baixa | Estimativa do PRD §4.1.3 é 1.34 h em 12 workers (pior caso ~1.7 h). Folga grande sobre as 4 h. Otimização de cluster fica ad-hoc no momento da execução (fora do escopo). |
| Ctrl+C durante o A.2 corrompe NPZ original | Baixa | **Sobrescrita atômica via `.tmp` + `os.replace()`** (FR-B-03, NFR-06). O `.tmp` é descartado em caso de interrupção; o original nunca fica corrompido pela metade. |
| **Bugs de Bitboard ao adaptar notebook de Fase 2** | **Alta** | **Dois bugs críticos já identificados e corrigidos** em `Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb`: (1) caixas pré-fechadas injetam pontos fantasmas; (2) offsets α/β incremental causam poda prematura. Se adaptar o código do Bitboard para outro notebook, rever obrigatoriamente esses dois pontos. Ver PRD §4.1.5. |

---

## Pendências de planejamento

> Ambiguidades que o spec/PRD não resolveu — registradas aqui para futura discussão; **não inventadas pelo plano**.

1. **Ordem exata dos passos dentro de uma célula do notebook A.1**: pré-popular o set de hashes antes ou depois de carregar `COMPLEMENTO_POR_CELULA`? Como tratar duplicatas dentro do próprio complemento (já filtradas por `mat.tobytes()`, mas a contagem residual pode bater na cota errada)? Detalhe sem impacto de correção; resolver durante implementação.
2. **Seed específica para o split treino/val/teste no V6**: o V5 usa seed `42`. Sugestão é manter `42` por consistência. Reabrir se a semente coincidir com algum padrão patológico medido empiricamente (improvável).
3. **Valor inicial de λ na Fase F**: o PRD declara faixa `[0.1, 0.3]` com sugestão 0.1. A calibração final fica para o início da Fase F (grid search ad-hoc com critério de não-regressão da policy + MSE da value ≤ 0.10).
4. **Formato dos vetores de referência da Fase D**: `referencia_canais_pontinhos.json` (legível em diff) ou `.npz` (compacto)? Recomendação inicial **`.json`**; reabrir se o tamanho do JSON ficar > 5 MB (improvável com 27 estados).
5. **Política de versionamento do contrato JSON**: o esquema atual usa campo `versao` simples (string). Considerar SemVer (`2.0.0` para Fase D) para evolução futura, mas **não bloqueia esta feature**.

---

## Não inclui no plano

> Conforme instrução explícita do usuário.

- ❌ Otimização de cluster Databricks (workers, timeout, batch size) — fora do escopo (Clarifications 2026-05-07; ad-hoc no momento da execução).
- ❌ Implementação no app Flutter, porte Dart do `analisador_estrutural_pontinhos.py`, A/B testing de TFLite no app — feature separada.
- ❌ Logging estruturado obrigatório, MLflow, TensorBoard, dashboards externos — cada notebook decide ad-hoc; resultados são trazidos manualmente para `docs/historico_decisoes.md` (Clarifications 2026-05-07).
- ❌ Separação `cadeia_media (=3)` vs `cadeia_longa (≥4)` — canal único `em_cadeia_longa = ≥3`; K=11 inalterado (Clarifications 2026-05-07).

---

## Tabela de Complexidade

> **Preencher SOMENTE se houver violações da Constituição que precisem ser justificadas.**

(Vazia — nenhuma violação detectada.)

---

**Output da Fase 1**: `research.md`, `data-model.md`, `contracts/canais_estruturais.md`, `contracts/npz_schema.md`, `quickstart.md`. Atualização do `CLAUDE.md` na raiz do repositório com a referência a este plano (entre os marcadores `<!-- SPECKIT START -->` e `<!-- SPECKIT END -->`, se existirem).

**Próximo passo**: `/speckit-tasks` (gera `tasks.md` a partir deste plano).
