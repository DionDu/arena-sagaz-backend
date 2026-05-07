# Histórico de Decisões — Arena Sagaz Backend

Registro cronológico de decisões arquiteturais e mudanças de rota relevantes.
Entradas mais recentes no topo. Cada entrada deve responder: **o quê, por quê,
o que foi descartado e por quê**.

---

## 2026-05-07 — Geração local com multiprocessing (V5_Local) e remoção do `closure_lut`

### Contexto

Tentativa de rodar `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`
em conta gratuita do Databricks (serverless). Performance medida: mais de **8
minutos para 100 amostras** (≈ 5 s/amostra). Em escala A.1 (347.020 amostras
novas a gerar), isso sairia da janela operacional.

### Diagnóstico

1. **`closure_lut` em `build_topology_tables`** alocava
   `np.zeros((n, 1<<n), dtype=np.int8)` — para `n=31`, isso é **66 GB de
   memória virtual por worker**. Linux com overcommit deixa alocar (calloc
   lazy), mas o loop só preenchia os primeiros `2²⁰ ≈ 0,05%` da tabela. O
   LUT cobria pouquíssimos estados; o fallback (3-4 testes de máscara) era
   chamado quase sempre. **Otimização era prejuízo líquido**: page-faults
   na alocação, custo de inicialização por partição Spark, sem ganho.
2. **Spark serverless free** tem cores limitados (~2-4) e overhead
   significativo de lançamento de task no Spark Connect. Configuração
   `CHUNK=1000, PARTS=256` resultava em fila de 256 tasks de 4 registros —
   coordenação dominava sobre computação.
3. **Worker reconstrói `build_topology_tables`** a cada partição (chamado
   dentro de `process_batch_v4`) — milhares de reconstruções por rodada.

### Decisão

**Criar versão local autônoma** em
`notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb`,
delegando o engine ao módulo companheiro
`notebooks/jogo_pontinhos/v5_local_engine.py`. Característica do V5_Local:

- **Sem Spark.** `multiprocessing.Pool` com `pool.map` em batches; pool
  inicializado uma única vez via `initializer=init_worker` (tabelas
  construídas 1× por worker, não por tarefa).
- **Sem `closure_lut`.** `_closures_fast` é cálculo direto.
- **Engine em `.py`** (não em célula Jupyter) porque `multiprocessing` no
  Windows usa `spawn` — funções definidas em células não são picklable.
- **Loop por cota preserva PRD §4.1.3.** Sorteia célula
  `(gen_mode, bucket)` ponderada por cota residual em
  `COMPLEMENTO_POR_CELULA`; worker gera com `gen_mode` e `target_tracos`
  forçados; rejeita+regera (até 20 tentativas) se duplicado ou fora do
  bucket; para quando todas as cotas zeram (347.020 estados novos).
- **Pré-popula `hashes_iniciais`** com os 314.323 únicos do legado em
  `dados/profundidade_minmax_9/`.

### Correção paralela no V5_Databricks

`notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Databricks.ipynb`
também teve `closure_lut` removido (mesma motivação). A lógica do laço
principal foi preservada (TODO de quota-based dispatch já era
pré-existente — pertence a futura iteração de T-A1-004 no Databricks, fora
do escopo desta sessão).

### Alternativas consideradas

- **Manter Spark e ajustar `PARTS`**: ajuda no overhead, não resolve o
  custo do `closure_lut`, e free serverless é fundamentalmente o
  ferramentas errada para CPU-bound puro.
- **Numba/Cython no inner loop**: ganho real, mas adiciona dependência
  pesada e exige alteração arquitetural (tipos numpy fixos). Adiado para
  Fase B se precisar.
- **Cluster Databricks pago dedicado**: viável (e ainda recomendável para
  geração massiva), mas o V5_Local cobre o caso "gerar localmente quando
  cluster pago não está disponível", que é o cenário atual.

### Métricas estimadas

- Setup atual (Databricks free serverless, `closure_lut` removido):
  ainda lento (overhead Spark domina; cores muito limitados).
- V5_Local em máquina Windows com 8-16 cores físicos: estimativa
  **≈ 0.5-1 s/amostra** (vs 4.8 s/amostra no Databricks free); 347k
  amostras em **~4-8h** total.
- Esses números serão substituídos pela medição real após a primeira
  rodada completa.

---

## 2026-05-07 — Fase A.2 concluída: 11 canais estruturais + sobrescrita atômica + paleta visual (D2/D3/D4)

### Contexto

Conclusão da segunda fase do plano `specs/004-melhoria-geracao-dados-cnn/`
(tasks T-A2-001 a T-A2-008). A Fase A.2 transforma os NPZs gerados pelo
Databricks (Fase A.1) em datasets prontos para a CNN do V6: cada estado
recebe seu tensor `canais (4, 3, 11) int8` pré-computado, eliminando a
camada Lambda `para_grid_de_caixas` que existia em runtime no V5.

### Decisões consolidadas

**D2 — Tensor `canais (4, 3, 11)` materializado no NPZ.** Os 11 canais
seguem a ordem canônica do PRD §4.2 (`aresta_topo`, `aresta_base`,
`aresta_esquerda`, `aresta_direita`, `caixa_fechada`, `eh_grau3`,
`eh_grau2`, `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`,
`em_cadeia_aberta_uma_ponta`). Implementado em
`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`. Mantido
**canal único `cadeia_longa` para componentes de comprimento ≥ 3** (não
separamos `cadeia_media = 3` vs `cadeia_longa ≥ 4`) — clarification
2026-05-07.

**D3 — Sobrescrita atômica via `<arquivo>.tmp` + `os.replace()`.**
Implementada no `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb`.
Ctrl+C durante o enriquecimento NUNCA corrompe o original; o `os.replace`
só substitui quando o `.tmp` está integro. Operação idempotente: rodar
sobre NPZ já enriquecido é seguro (controle por flag `FORCAR_REGRAVAR`).

**D4 — Paleta visual estável + borda em caixas fechadas.** Script
`scripts/pontinhos/validar_canais_visualmente.py` gera PNGs a 150 DPI com:
- 1 painel esquerdo: matriz crua `(9, 7)`;
- 11 boxnets `(4, 3)` à direita, **uma cor categórica fixa por canal**
  (mesma cor entre execuções, para comparabilidade entre lotes);
- borda destacada em caixas onde `canal[caixa_fechada] == 1`, em todos os
  11 boxnets (distingue "fechada" de "aberta com grau hipotético");
- título canônico exatamente igual ao item correspondente em
  `NOMES_CANAIS`.

### Validação

- `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v`
  → **11 passed** nesta máquina (Python 3.9.5, numpy disponível). Cobre:
  domínio binário, exclusão mútua canal 4 vs 5–10, coerência sob
  simetrias (ref_H, ref_V, R180), tabuleiro vazio, caixa fechada simples,
  loop de 4 caixas, half-open chain, double-cross do Buchin.
- Notebook de enriquecimento e script de validação visual entregues e
  importáveis.
- **Bug encontrado e corrigido durante a TDD**: em numpy moderno,
  `np.bool_ + np.bool_` retorna `np.bool_` (OR lógico), não soma
  aritmética. Fix em `_grau()` para somar via `int(M[...] == 9)`
  explícito. Sem essa correção todos os canais 5–10 ficavam zerados.

### Alternativas consideradas (todas rejeitadas)

- **Doze canais** (separando `cadeia_media = 3` vs `cadeia_longa ≥ 4`):
  rejeitado por aumentar complexidade do input sem evidência empírica
  (research.md §1.4).
- **Gravação direta sem `.tmp`** (`np.savez(arquivo, ...)` sobrescreve in
  loco): rejeitado por NFR-06 (Ctrl+C durante o save corromperia o
  arquivo original).
- **Paleta com gradiente de cor** ou aleatória por execução: rejeitado
  porque atrapalha comparação visual entre lotes (research.md §1.3).
- **JSON declarativo único como ground truth do algoritmo dos canais**:
  mantido como referência (`contracts/canais_estruturais.md` + futuro
  `referencia_canais_pontinhos.json` em T-D-005), mas a fonte da verdade
  do dataset continua sendo o módulo Python — coerente com a diretriz do
  CLAUDE.md "fonte da verdade no contrato JSON" se aplicar apenas ao
  contrato de codificação backend↔frontend, não ao algoritmo de canais.

### Estado de validação manual pendente

A Fase A.2 só fica oficialmente "fechada" quando o desenvolvedor:

1. Roda o enriquecimento sobre o diretório de NPZs reais da Fase A.1.
2. Gera os 30 PNGs com `validar_canais_visualmente.py`.
3. Inspeciona-os manualmente nas 3 faixas (`t∈[12,17]`, `[24,28]`, `[29,30]`).
4. Assina aqui mesmo, ao final desta entrada, que a inspeção foi OK.

> **Assinatura visual (preencher após T-A2-005)**:
> _[ ] OK — 30 PNGs revisados, canais 0–10 coerentes com a matriz crua nos casos inspecionados._
> _Assinado por: ____________ Data: ____________

### Documentação atualizada

- `docs/jogo_pontinhos/guia_geracao_dados.md` ganhou a seção **1A** com o
  fluxo completo A.1 + A.2 (T-A2-007).

---

## 2026-05-07 — Fase A.1 do plano 004 — V5 do notebook de geração no Databricks (TEMPLATE — aguardando execução)

### Contexto

Tasks T-A1-001 a T-A1-006 do plano `specs/004-melhoria-geracao-dados-cnn/`.
Esta entrada é deixada como **template** — os números reais (uniques
gerados, distribuição empírica, mix `gen_mode` por bucket, tempo) só
existirão após o desenvolvedor rodar o notebook V5 no Databricks. Nenhum
parâmetro deve ser ajustado fora do que está fixado abaixo (PRD §4.1.3).

### Parâmetros consolidados no V5

- `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` — `sim_l1` desligado por
  gerar estados "lunáticos" sem qualidade estratégica (D1.a do PRD).
- `FAIXA_TRACOS = (0.15, 0.97)` — equivale a 5..30 traços para `n_edges = 31`
  (D1).
- `COMPLEMENTO_POR_CELULA` literal embutido na célula de parâmetros do V5
  (PRD §4.1.3). Soma das cotas = **347_020**, conforme PRD.
- Dedup obrigatória por `mat.tobytes()` com **pré-população do set por
  314.323 únicos do legado** antes de iniciar o laço de geração (D1.b /
  FR-A-04). Estados duplicados são regerados (até 20 tentativas).
- DEPTH = 9 (Minimax(p=9)), inalterado em relação ao V4.

### Distribuição-alvo (PRD §4.1.3) — tolerância ±2pp

| Bucket de traços | Cota legado | Quota complemento | Total alvo | % alvo |
|---|---|---|---|---|
| 5–11 | 27.515 | 22.484 | 50.000 | 10% |
| 12–17 | 49.443 | 50.557 | 100.000 | 20% |
| 18–23 | 56.404 | 83.596 | 140.000 | 28% |
| 24–28 | 19.617 | 140.383 | 160.000 | 32% |
| 29–30 | — | 50.000 | 50.000 | 10% |

> **Nota**: a soma `legado + complemento` por bucket pode divergir
> ligeiramente da tabela acima a depender de quais cotas a auditoria
> empírica do desenvolvedor decida ajustar dentro da tolerância. Os
> valores literais embutidos no notebook V5 são os de
> `COMPLEMENTO_POR_CELULA` na célula de parâmetros — fonte da verdade.

### Resultados (PREENCHER após execução)

```
Total de estados gravados:    ____________
Únicos por mat.tobytes():     ____________     (esperado >= 500.000)
Tempo total de execução:      ____________ h   (NFR-03: ≤ 4 h)
Tamanho dos NPZs:             ____________ MB

Distribuição empírica por bucket de tracos:
  (5, 11): ____% (alvo 10%, desvio ____pp)
  (12, 17): ____% (alvo 20%, desvio ____pp)
  (18, 23): ____% (alvo 28%, desvio ____pp)
  (24, 28): ____% (alvo 32%, desvio ____pp)
  (29, 30): ____% (alvo 10%, desvio ____pp)

Mix de gen_mode (% real):
  uniform (0): ____%
  sim_l1  (1): 0% (DESLIGADO — D1.a)
  sim_l2  (2): ____%
  sim_l3  (3): ____%

Hashes verificados:
  Pré-população legado: 314.323
  Duplicatas regeneradas (laço): ________
  Estados gerados pelo V5 (complemento): ________
```

### Decisão

Manter os parâmetros tal como estão fixados na célula `[T-A1-002 + T-A1-003]`
do V5. Caso a distribuição empírica saia da tolerância em algum bucket, a
correção primeiro tenta ajustar o `COMPLEMENTO_POR_CELULA` (mantém DEPTH e
mix); só em segunda instância se reabre `STRAT_WEIGHTS`.

### Alternativas consideradas

- **Não pré-popular o set de hashes** (gerar tudo do zero, dedupando
  contra o legado durante o laço): rejeitado pelo gasto computacional —
  a maioria dos estados de início/meio de jogo já existe no legado, e
  testá-los mid-loop desperdiça Minimax(p=9).
- **Manter `sim_l1` com peso ≥ 0.05**: rejeitado em D1.a por evidência
  empírica (estados "lunáticos" — V4 spec §4.1.2).
- **Otimizar configuração do cluster Databricks no nível da spec**:
  rejeitado em research.md §1.1 — a configuração depende do dia/cluster
  e é decidida ad-hoc.

### Motivo

Cobertura terminal expandida (faixa 24–30 traços com 42% do dataset,
contra ~3% do V4) ataca diretamente a Categoria A de erros táticos
identificada no relatório de divergência de 2026-05-06 (87.8% das
divergências fatais concentradas em `t ∈ [28, 30]`).

---

## 2026-05-06 — Análise de divergência estratégica (600 partidas) confirma Cenário X3 e motiva duas novas fases no PRD

### Contexto
Após descontinuar p=1 (decisão abaixo na mesma data), rodamos
`tmp_analise/analisa_divergencia_estrategica.py` em **600 partidas** (200
contra cada um de p=3, p=5, p=6) com o oráculo Minimax adaptativo
(p=5/7/9 conforme livres). Tempo total: 9370 s (~2.6 h) com 12 workers.
Modelo avaliado: `modelos/pontinhos_pequeno_profundidade_9.tflite`.
Relatório completo: `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md`.

### Resultados-chave

**Win-rates (CNN, vencedora):**
- vs p=3: 109/200 = 54.5%
- vs p=5: 84/200  = 42.0%
- vs p=6: 76/200  = 38.0%

**Fatal precoce (≤ 25 traços) entre partidas perdidas:**
- vs p=3: 7/42  = **16.7%**
- vs p=5: 11/60 = **18.3%**
- vs p=6: 14/89 = **15.7%**
- Média ponderada: 32/191 ≈ **16.8%**

**Distribuição dos fatais (total 410 nas 600 partidas):**
- Meio (10–24 traços):  50 fatais (12.2%)
- Transição (25–27):    0 fatais
- Fim (28–30):         360 fatais (87.8%) — concentrados em t=29 (356/360)
- **Pico no meio:** t=14 com 28 fatais; também t=12 sangra (4 fatais + 83 moderadas).

**Padrões sistêmicos (top pares ótima → CNN, todos com Δ ≥ 2):**
- Fim: H_2_1 → V_1_0 (37×), H_2_3 → H_0_3 (32×), H_6_3 → H_8_3 (30×),
  V_1_4 → V_1_6 (26×), V_1_4 → H_0_5 (24×) — viés de borda externa
  confirmado.
- Meio: H_0_3 → V_7_2 (15×), H_4_1 → V_3_2 (12×), H_8_3 → V_7_2 (12×),
  H_4_1 → V_3_0 (12×) — substituições estruturais que cruzam o tabuleiro,
  sintoma de paridade/cadeia mal compreendida.

### Veredicto: Cenário X3 confirmado e estável

A taxa de fatal precoce está estável em **15–18% nos três adversários** —
isso é evidência forte de **erro sistêmico da CNN** (não induzido pelo
adversário). Se o adversário é mais forte (p=6) ou mais fraco (p=3), a
CNN comete fatal precoce na mesma proporção das partidas que perde. Isso
favorece atacar a representação interna (canais estruturais — Fase D do
PRD) e a calibração de gradiente em meio-jogo (novas fases — ver abaixo),
não simplesmente "mais dados de fim".

Observação adicional importante: das 89 partidas perdidas vs p=6, **58
não têm nenhuma divergência fatal** (perdidas por acúmulo de moderadas).
Isso reforça que cobertura ampla de dados (Fases A/B/C do PRD) continua
sendo a base obrigatória do plano.

### Decisões derivadas — duas novas fases inseridas no PRD

#### Nova Fase E (entre atual D e atual E, que será renumerada para G):
**Sample_weight refinado por Δ-top2 — foco em meio-jogo (t=12 a t=17)**

- Foco real: **t=12 a t=17** (faixa de paridade/controle de cadeias),
  NÃO t=29. Os erros em t=29 já são atacados pelas Fases A/B (cobertura
  terminal) e pelo canal `eh_grau3` em D.
- Multiplicador discreto: `peso = 1 + α · Δ_top2_caixas`, com α calibrado
  para que tabuleiros nessa faixa valham **~10% a mais** que os demais
  (NÃO 6× — a maioria das jogadas em t=12–17 são boas; só damos um
  empurrãozinho de gradiente nas poucas que importam).
- Cap absoluto: nenhum peso individual pode passar de **1.20** (ou seja,
  20% a mais que o peso 1.0 dos demais tabuleiros).
- Implementação: cálculo de `Δ_top2` direto dos `scores` já no NPZ;
  multiplicar pelo coeficiente α apenas em amostras da faixa-alvo.

#### Nova Fase F (entre nova E e atual E renumerada G):
**Value head AlphaZero-style (multi-task learning)**

- Adicionar segunda saída ao modelo Keras, em paralelo à policy head:
  - Policy head (existente): Conv → Flatten → Dense(96) → softmax(31).
  - Value head (nova): Conv 1×1 → Flatten → Dense(64, relu) → Dense(1, tanh).
- Alvo do value head: `score_max(scores_mm) / 6` (normaliza Q* ao
  intervalo `[-1, +1]`; 6 = max caixas líquidas em 4×3).
- Loss conjunta: `loss_total = KLD(policy) + λ · MSE(value)` com
  **λ ≈ 0.1–0.3** (pequeno para não dominar a policy).
- **Inferência mobile sem custo:** descartar a value head no export TFLite
  (manter apenas a policy). Frontend Flutter inalterado.
- Justificativa: força a representação intermediária a codificar "quem
  está ganhando", sinal que hoje a CNN só aprende implicitamente pela
  política. Em jogos com decisões de paridade (caso de pontinhos 4×3),
  saber o sinal do valor antes de decidir a aresta é estruturalmente útil.
- Aumenta tempo de treino em ~10–20%; pipeline de dataset não muda
  (`value_target` é derivado dos `scores` já existentes no NPZ).

#### Renumeração:
- Atual Fase E (Hard-target ≥26) → **Fase G** (condicional).
- Atual Fase F (Loss assimétrica) → **Fase H** (condicional).

### Faixa crítica de meio-jogo estendida

PRD original cita faixa "10–25" para fatal precoce e "13-17" como faixa
crítica em alguns gates. Os dados mostram **t=12 também sangrando** (4
fatais + 83 moderadas, mais alto que t=13 em moderadas). Faixa crítica
unificada para **[12, 17]** em todos os gates e na nova Fase E.

### Alternativas descartadas
- **Sample_weight com cap 6×:** rejeitado pelo usuário — distorceria a
  loss em demasia. Maioria das jogadas em t=12–17 são boas; queremos
  empurrão sutil, não sobreposição.
- **Sample_weight focado em t=29:** redundante. Categoria A já é atacada
  pelas Fases A/B/C/D; t=29 representa 87.8% dos fatais mas é tática
  pura (ataque por cobertura + canal `eh_grau3`).
- **Value head com inferência completa em produção:** descartado
  porque adicionaria custo no app Flutter (3–5 ms por jogada). Mantemos
  value head só no treino (regularizador estrutural).
- **Pular Fase E e ir direto para value head:** descartado porque queremos
  isolamento causal entre intervenções. Cada fase recebe seu próprio
  TFLite versionado e avaliação independente.

### Consequências operacionais
- PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md` atualizado nesta data:
  - Seção 2.4 reescrita inteira com resultados das 600 partidas.
  - Faixa crítica unificada `[12, 17]` substituindo `[13, 17]` ou `10-25`
    onde aplicável.
  - Seção 5 com novas Fases E e F inseridas; antigas E/F renumeradas G/H.
  - Decisões D-novas adicionadas em §4 (D9 sample_weight refinado, D10
    value head).
- Plano sequencial: A → B → C → D → **E (sw refinado) → F (value head)** → G → H.
- Métricas operacionais a recalcular após Fase F (tempo treino esperado
  +10–20%, TFLite exportado sem value head — tamanho inalterado).

---

## 2026-05-06 — Minimax(p=1) descartado como adversário em análises diagnósticas

### Contexto
Ao revisar PNGs gerados por `tmp_analise/analisa_divergencia_estrategica.py`
em partidas CNN vs Minimax(p=1), o usuário identificou um padrão estranho:
em várias jogadas de **abertura** (t=2, t=4, t=12), o adversário Minimax
**criava caixas de grau-3 em estados que ninguém pediu para serem criados**,
literalmente "doando" caixas para a CNN. Hipótese inicial: bug no Minimax.

### Investigação
Reanálise pontual com Minimax(p=5/7/9) sobre o estado salvo em NPY (após
adicionarmos o salvamento de NPY+JSON irmão por PNG) confirmou que:

1. O motor Minimax **não está bugado**. A função `melhor_jogada()` em
   `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` calcula corretamente
   os scores e devolve `random.choice(jogadas_tied)` entre as melhores.
2. O comportamento "absurdo" decorre de uma propriedade fundamental do
   **profundidade 1**: ele só simula a própria jogada (zero plies de resposta
   do adversário). Quando **nenhuma** jogada disponível fecha caixa
   imediatamente, **todas** ficam com score=0 (a função `avaliar` em
   profundidade 0 retorna `caixas_ia − caixas_humano` = 0). O motor então
   sorteia aleatoriamente entre as 27+ jogadas livres — incluindo as que
   criam grau-3 para o adversário.
3. Para detectar "abrir caixa para o oponente no próximo turno", o Minimax
   precisa de **pelo menos p=2** (1 ply próprio + 1 ply do oponente). p=1
   simplesmente não tem essa capacidade.

### Decisão: descontinuar p=1 como adversário em análises diagnósticas
A partir desta data, `analisa_divergencia_estrategica.py` (e qualquer
analisador derivado) **não usará mais Minimax(p=1)** como adversário. Em
diante, profundidades adversárias diagnósticas válidas são **p=3, p=5, p=6**.

**Por quê:**
- Partidas vs p=1 são contaminadas por jogadas pseudo-aleatórias do
  adversário, criando estados não-representativos do que a CNN encontraria
  em jogo real contra qualquer oponente humano de nível mínimo.
- Os Δ-scores que o oráculo (p=5/p=7/p=9 adaptativo) calcula sobre tais
  estados refletem em boa medida a **estranheza do estado** induzida pela
  aleatoriedade do p=1, não a qualidade tática/estratégica da CNN.
- Conclusões sobre "Categoria A vs B de erros" e "Cenário X1/X2/X3" exigem
  adversários minimamente capazes de não doar caixas em abertura.
- Avaliação de win-rate vs p=1 (em `Avaliacao_CNN_vs_Minimax.ipynb`) **continua
  válida** como métrica histórica para comparações longitudinais com
  rodadas anteriores — a decisão se restringe a análises de divergência
  estratégica, não ao avaliador de partidas em geral.

### Alternativas descartadas
- **Manter p=1 como controle "ruído de baseline":** rejeitado porque sua
  presença diluía a leitura visual dos PNGs (muitos d=0 ou d=1 inócuos
  causados pelo adversário "se sabotando") e custava ~25% do tempo total
  do run sem entregar sinal correspondente.
- **Trocar p=1 por p=2:** p=2 já enxerga "doar caixa" (vê 1 ply do
  oponente), mas a estatística vs p=2 pouco acrescenta sobre p=3 (que já
  está no padrão). Mantido fora por simplicidade.
- **Manter p=1 mas em pasta `Minimax_p_1_controle/`:** rejeitado porque
  ainda gera ~25% de overhead computacional sem benefício diagnóstico.

### Consequência operacional
- `tmp_analise/retratos_divergencia/Minimax_p_1/` apagada nesta data.
- Default de `--profundidades` ajustado para `3 5 6` no script.
- PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md` referencia esta decisão
  na Seção 2.4 (cenário X1/X2/X3) — a baseline diagnóstica não inclui mais p=1.

### Mudança paralela — visibilidade de jogadas do adversário
Mesma sessão, identificado que era impossível diagnosticar comportamento
do MM sem ler matrizes em sequência (jogada-N CNN vs jogada-(N+1) MM exige
inferir o estado pós-jogada-N para depois ler o estado pré-jogada-(N+2)).
Adicionada geração de PNG+NPY+JSON também para **jogadas do MM**, com
formato espelhado ao da CNN: painel esquerdo = jogada que o MM fez (laranja),
painel direito = todas as ótimas em verde + todas as piores em marrom
segundo o **mesmo Minimax(p=X) que ele usou para decidir**. Sem custo
computacional adicional (reaproveita a tabela de scores que `melhor_jogada()`
já calcula internamente).

---

## 2026-04-29 — Tentativa 8 regrediu: manter V3 (depth=7) e aprender sobre saturação de capacidade

### Contexto
Após o sucesso da Tentativa 7 (V3 auto-play depth=7: 96% vs MM(p=1), 40% vs MM(p=6), OMA 93.2%), a pergunta natural era: **aprofundar o professor ajuda?** Geramos 344k amostras com Minimax depth=8/9 (14% mais dados) e retreinamos com a mesma arquitetura. As métricas estáticas sugeriam "um pouco melhor" (top-3 +1.7pp, top-5 +2.1pp) — até rodar o avaliador de partidas reais.

### Decisão: Manter V3 como modelo de produção

Win-rates confirmaram regressão clara (salvo p=1, onde diferença está no ruído):
- MM(p=3): 60% → 53% (−7 pp)
- MM(p=5): 45% → 40% (−4.5 pp)
- MM(p=6): 40% → 36.5% (−3.5 pp)

OMA também caiu (93.2% → 89.2%), e win-rate concordou com OMA — indicativo de que ambas as métricas detectam um problema real, não artefato de avaliação.

**Veredicto:** V3 (depth=7, 300k) vence V4 (depth=8/9, 344k) em todas as profundidades ≥ 3. Revertemos para V3 como modelo de produção.

### Aprendizado: Saturação de Capacidade do Student

A rede BoxNet v3 de 74.5k parâmetros atingiu o **ponto ótimo de capacidade do teacher** em depth=7. Aprofundar professor acima desse ponto degrada performance em vez de melhorar.

**Evidência de saturação:**
1. Top-1 estagnou: 42.7 → 42.71% com 14% mais dados.
2. OMA caiu: professor + profundo transmite nuance que o aluno não consegue reproduzir (fenômeno conhecido em knowledge distillation).
3. val_loss KLD subiu: alvo intrinsecamente mais difícil de aproximar (soft targets com menos empates, mais precisão de score).
4. Win-rate em profundidades altas caiu: confirma que OMA não era outlier — modelo realmente ficou pior.
5. Piso de blunders (~13–15% de caixas deixadas) é estável contra MM(p≥3): indica limite estrutural, não falta de dados.

### Alternativa Descartada

- **"E se aumentássemos a rede primeiro?"** — postergado. Não testamos depth=8/9 + rede maior juntos; testamos depth=8/9 + rede igual. Próxima rodada experimental será justamente isso (rede de ~180k params + depth=8/9).

### Próximos Passos (em Prioridade)

1. **Aproveitar V3 para defesa do TCC** — tem os melhores números absolutos, validados em jogo real. Narrativa centrada em OMA=93.2% + win-rate 96%/60%/45%/40%.

2. **Aumento de capacidade da rede (2–3 semanas futuros)**
   - Adicionar terceiro bloco residual (48 → 64 filtros)
   - Dense head 96 → 128
   - Estimativa: 150–200k parâmetros, ainda < 300 KB tflite
   - Re-treinar com dataset V4 (344k, depth=8/9)
   - Hipótese: rede maior + depth=8/9 deve superar V3

3. **Ou explorar largura (mais fácil):** gerar 600k+ amostras em depth=7 com rede atual. Menos dispendiosos que aumentar arquitetura.

4. **Investigar piso de 13–15% de blunders táticos:** gravar `(estado, jogada_cnn, jogada_otima, score_gap)` em casos de erro no avaliador. Pode revelar fraqueza específica (parity, loony endgame) que dataset sozinho não resolve.

### Alinhamento com Literatura

O fenômeno de "aluno saturado" vs "teacher muito forte" é bem documentado em knowledge distillation (Hinton 2015, e sequências). Existe um ponto ótimo de "teacher capacity" dado um student fixo. Ultrapassar esse ponto introduz ruído em vez de sinal. A solução padrão é aumentar student (como planejado acima).

---

## 2026-04-24 — Refatoração estrutural do repositório (branch `002-refatoracao-estrutural`)

### Contexto
O repositório acumulou nomes genéricos em `gerador_dados/` (`tabuleiro.py`,
`minimax.py`, `gerador.py`, etc.) e em `docs/` (arquivos game-specific na raiz
sem subfolder), criados antes de Arena Sagaz ser tratado explicitamente como um
**hub de jogos**. Com a regra de nomenclatura hub-de-jogos estabelecida
(2026-04-24), ficou claro que um segundo jogo criaria colisões imediatas de
nomes: `gerador_dados/tabuleiro.py` poderia ser do Pontinhos ou da Velha.

### Decisão
Refatoração em cinco fases executadas na branch `002-refatoracao-estrutural`:

1. **Fase 0 — Limpeza:** deletar arquivos gerados pelo SpecKit que nunca foram
   validados (`api/banco/`, `api/auth/`, etc.), reescrever `api/` de forma
   minimalista, limpar `requirements.txt`.

2. **Fase 1 — docs/:** criar `docs/tcc/` e `docs/jogo_pontinhos/`, mover 11
   documentos game-specific para `docs/jogo_pontinhos/` e
   `argumentacao_cnn_vs_minimax.md` para `docs/tcc/`.

3. **Fase 2 — gerador_dados/:** criar `gerador_dados/jogo_pontinhos/`, renomear
   os 8 arquivos game-specific com sufixo `_pontinhos` (usando `git mv` para
   preservar histórico), atualizar todos os imports, mover testes para
   `tests/unitarios/jogo_pontinhos/`. `nucleo_log.py` deletado — imports
   redirecionados para `api.nucleo.log`, que já tinha implementação idêntica.

4. **Fase 3 — notebooks/:** mover 6 notebooks para `notebooks/jogo_pontinhos/`,
   atualizar paths em `Avaliacao_CNN_vs_Minimax.ipynb` (único que roda
   ativamente).

5. **Fase 5 — Configurações e documentação:** verificar `pytest.ini`,
   `Dockerfile`; atualizar `CLAUDE.md` com novos paths do contrato e do teste CI;
   registrar refatoração no histórico.

### Descartado
- **Renomear arquivo por arquivo durante outras tarefas (caso a caso):** gerava
  inconsistência incremental. Preferiu-se sessão dedicada, clean-slate, com
  checklist explícito.
- **Manter nomes genéricos e usar só pastas para separar:** insuficiente quando
  um arquivo legado fica na raiz compartilhada (`gerador_dados/tabuleiro.py` —
  de qual jogo?).

### Estado final
- `gerador_dados/jogo_pontinhos/` — 8 arquivos com sufixo `_pontinhos`
- `notebooks/jogo_pontinhos/` — 6 notebooks
- `docs/jogo_pontinhos/` — 11 docs game-specific
- `docs/tcc/` — 1 doc de argumentação acadêmica
- `tests/unitarios/jogo_pontinhos/` — 4 arquivos de teste
- 31/31 testes passando

---

## 2026-04-24 — Autenticação via Firebase Auth + limpeza do api/ gerado por SpecKit

### Contexto
O SpecKit gerou automaticamente toda uma camada de API (`api/banco/`, `api/auth/`,
`api/partidas/`, `api/ranking/`, `api/trofeus/`, `api/usuarios/`) com SQLAlchemy,
Alembic migrations, JWT e hashing de senha. O usuário não reconheceu nem validou
esse código — foi gerado sem decisões explícitas sobre banco de dados, modelo de
dados ou fluxo de autenticação.

Além disso, o usuário definiu que: (a) o cadastro/login é **opcional** — o app
funciona offline sem conta; (b) quando houver conta, suportará Google e outros
providers OAuth além de email/senha.

### Decisão
1. **Deletar integralmente** `api/banco/`, `api/auth/`, `api/partidas/`,
   `api/ranking/`, `api/trofeus/`, `api/usuarios/` e `alembic.ini`. Nada
   disso foi validado e criar-se-á do zero no momento oportuno (após o primeiro
   jogo rodar no frontend).

2. **Autenticação: Firebase Auth.** Elimina a necessidade de implementar
   hashing de senha, JWT, refresh tokens e OAuth flows no backend. O backend
   valida tokens Firebase (SDK `firebase-admin`) em vez de emiti-los. Login
   social (Google, Apple etc.) sai de graça pelo Firebase console.
   Dependência: `firebase-admin` — adicionada ao `requirements.txt` apenas
   quando a feature for implementada.

3. **`api/` minimalista por enquanto:**
   - `api/main.py` — FastAPI app + middleware de log
   - `api/configuracao.py` — só `AMBIENTE`
   - `api/nucleo/log.py` — logger JSON estruturado
   - `api/nucleo/excecoes.py` — exceções de negócio reutilizáveis
   - `api/nucleo/rotas.py` — `GET /v1/health` sem dependência de banco

### Descartado
- **Auth própria (JWT + bcrypt):** mais controle, mas exige implementar
  hashing, refresh tokens e cada provider OAuth manualmente. Custo alto
  para um app onde o login é opcional.
- **Manter o código do SpecKit "para depois refatorar":** decisão consciente
  de não carregar código não-validado no repositório. Mais fácil criar do zero
  quando as definições estiverem claras.

---

## 2026-04-24 — Contrato de codificação da CNN como fonte única da verdade

### Contexto
A normalização da matriz de entrada da CNN vinha sendo duplicada em vários
lugares: `simulador_tatico.py`, `avaliador_partidas.py`, notebooks de geração
(Databricks) e de treino (Colab), além do app Flutter. Cada fix de bug pedia
coordenar edições em 4–5 arquivos em dois repositórios, e o documento
`arena-sagaz-frontend/docs/ia_mappings.md` já havia divergido do código em
produção (bug #3 de 2026-04-23). Sem uma fonte única, a próxima regressão
silenciosa é questão de tempo.

### Decisão
Introduzir `gerador_dados/contrato_codificacao_pontinhos.json` como **fonte
única da verdade** da codificação da matriz de entrada da CNN do Pontinhos.
O JSON declara explicitamente os TRÊS contextos de uso (geração de dataset,
treinamento, partidas ao vivo), o domínio de valores permitido em cada um,
as regras de normalização aplicáveis com justificativa técnica, e os invariantes
do tensor final (`{0, 1}`, `float32`, `(1, H, W, 1)`).

Consumidores:
- Backend Python (`simulador_tatico.py`, `avaliador_partidas.py`) usa o helper
  `gerador_dados/contrato_codificacao_pontinhos.py`, que é uma fina camada
  sobre o JSON. Zero regra duplicada.
- Notebooks (Databricks + Colab) **não** importam scripts Python externos —
  carregam o JSON inline com `json.load()` conforme snippet documentado no
  próprio JSON (`snippet_de_uso_para_notebooks`).
- Frontend Flutter lê `assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`
  em runtime.

Sincronização:
- Duas cópias versionadas (backend + frontend) com hash SHA-256 idêntico.
- Teste CI (`tests/unitarios/test_contrato_codificacao_pontinhos.py`) **falha
  o merge** se divergirem.

CLAUDE.md (backend e frontend) atualizado para OBRIGAR leitura do JSON antes
de qualquer mudança em encoding, pipeline de geração/treino, lógica de
inferência ou normalização.

### Alternativas descartadas
- **Módulo Python `encoding.py` compartilhado**: descartado porque obrigaria
  enviar um arquivo Python extra ao Databricks e ao Colab a cada iteração, e
  o usuário explicitamente proibiu notebooks chamarem scripts externos.
- **Mascaramento da terminologia no JSON** (ex.: "classe A/B" no lugar de
  "jogador 1/2"): descartado porque o público-alvo do JSON são LLMs editando
  código; mascaramento prejudicou a compreensão num primeiro protótipo.
- **Gerar os mapeamentos de labels também a partir do JSON**: fora de escopo
  desta rodada — os `mapeamento_*.json` continuam sendo gerados por
  `todos_labels_canonicos()` no backend. Podem ser unificados em rodada futura
  se vier necessidade.

### Regra de nomenclatura associada
Mesmo dia ficou registrada a regra de nomenclatura hub-de-jogos: arquivos
game-specific devem carregar o nome do jogo OU estar dentro de pasta do jogo.
Isso motivou mover `assets/ia_mappings/` para
`assets/jogos/pontinhos/ia_mappings/` no frontend, alinhando com a estrutura
declarada no PRD §5.1 (`lib/modulos/jogos/pontinhos/`).

---

## 2026-04-23 — Análise do modelo V3 auto-play e 3 bugs corrigidos

### Contexto
Dataset V3 (300k amostras auto-play, gerado no Databricks em 4h) + re-treino
completo (BoxNet v3 auto-play) entregaram métricas estáticas **melhores** que
o modelo p=6 aleatório (Top-1 42.7% vs ~35%, gap treino/val +0.23 pp, zero
overfitting), mas o avaliador de partidas reais reportou **regressão massiva**:
apenas 57% de vitória contra MM(p=1), antes 96%. Três bugs identificados na
inspeção.

### Bug #1 — Inferência nunca normalizou caixas fechadas com `-1`
`gerador_dados/avaliador_partidas.py` e `gerador_dados/simulador/simulador_tatico.py`
normalizavam apenas os **traços** (1/-1 → 1) mas deixavam as caixas fechadas
com o valor do jogador (1 ou -1). No dataset de treino, caixas fechadas são
SEMPRE 1 (confirmado em `dados/dataset_pequeno_0002.npz`: interior unique = [0, 1]).
Consequência: sempre que o adversário fechava uma caixa, a CNN recebia `-1`
em um slot onde nunca viu esse valor no treino.

Pior no avaliador: metade das partidas tem a CNN como "agente 2" →
`_VALOR_MATRIZ[2] = -1`, então as **próprias** marcações da CNN (traços e
caixas) saem como `-1`. A CNN literalmente não reconhecia o próprio tabuleiro
nessas metades. Isso explica o padrão invertido dos resultados: contra MM(p=1)
caiu de 96% para 57%, mas contra MM(p=6) subiu de 1.5% para 7.5% — o auto-play
de fato ensinou táticas de endgame, mas ficava sabotado pela má-inferência.

### Bug #2 — Worker Spark do V3 com `depth = 7` hardcoded
No `notebooks/Otimizacao_Topologia_Rede_V3.ipynb` cell 5, `process_batch_v3`
tinha `rows, cols, depth = 4, 3, 7` hardcoded dentro da função serializada aos
executors. O outer cell definia `DEPTH = 8` mas isso só valia no fallback
local. Resultado: os 4h de Databricks geraram o dataset **em depth=7**,
apesar do artefato se chamar `pontinhos_pequeno_profundidade_8.tflite`. A
hipótese "depth-8 + auto-play rompe a regressão do depth-7 aleatório" **não
foi testada** — testamos depth-7 + auto-play.

### Bug #3 — Contrato `ia_mappings.md` do frontend divergia do treino
O documento `arena-sagaz-frontend/docs/ia_mappings.md` declarava que `-1`
representa "caixa fechada pelo Jogador 2 (Humano)" na matriz enviada à CNN.
Esse contrato **conflita** com o encoding real do treino (caixas = 0 ou 1,
nunca -1). Se um cliente Flutter obedecesse ao contrato à risca, reproduziria
exatamente o bug #1.

### Decisão e Resolução
1. **Corrigido Bug #1** em `avaliador_partidas.py:94-104` e
   `simulador/simulador_tatico.py:50-58` — agora ambos aplicam normalização
   unificada: `mat == 8 → 0`, `mat == -1 → 1`, `mat == 9 → 1`.
2. **Corrigido Bug #2** em `Otimizacao_Topologia_Rede_V3.ipynb`: cell 5 virou
   `make_worker(depth, rows, cols)` (factory pattern) e cell 6 instancia o
   worker com `make_worker(DEPTH, ROWS, COLS)` antes de passar ao
   `mapInPandas`. Garante que o valor declarado no driver é o efetivamente
   usado.
3. **Bug #3** a ser corrigido no repositório do frontend (próxima rodada) —
   o documento `ia_mappings.md` precisa ser atualizado para refletir o
   encoding real do treino.
4. **Métricas do treino V3** **validadas como boas** (Top-1 42.7%, OMA global
   93.2%, gap 0.23 pp). A regressão aparente em win-rate era artefato do bug
   #1. Re-avaliação pós-fix necessária para confirmar que win-rate sobe.
5. Documento de métricas `docs/metricas_e_conceitos.md` reescrito com TODAS
   as métricas (padrão Keras + custom) explicadas.

### Próximos passos imediatos
- Re-rodar `Avaliacao_CNN_vs_Minimax.ipynb` no `.venv_tf` com o `.tflite`
  atual e os fixes aplicados. Expectativa: win-rate vs MM(p=1) ≥ 85%.
- Se expectativa bater, regenerar dataset em **depth=8 real** no Databricks
  (mesmo 300k + mesmas estratégias, só com bug #2 corrigido) para testar a
  hipótese original depth-8 + auto-play.
- Definir padronização central do encoding da matriz — fonte única de verdade
  entre backend, frontend, gerador, avaliador e simulador (discussão aberta).

---

## 2026-04-23 — A Grande Revelação: O Bug da Regra Invertida no Minimax (cl == 0)

### Contexto
Após gerar amostras com Minimax profundidade 7 e treinar a CNN, observamos uma regressão brutal na força de jogo da CNN: ela estacionava em ~36% de precisão (Top-1) e performava pior do que modelos treinados com profundidade 6. 
Inicialmente, atribuímos essa falha ao uso de tabuleiros aleatórios ("topologias irreais") e desenhamos a geração de Autoplay (V3) para mitigar o problema.

### A Descoberta da Verdadeira Causa Raiz
Ao desenvolver e utilizar um novo Visualizador de Matrizes ASCII (Markdown), um teste manual revelou que o algoritmo estava avaliando a captura de caixas como uma jogada péssima (score 0) e sacrifícios forçados absurdos como jogadas excelentes (score +3).

Uma auditoria imediata no código apontou um **bug gravíssimo na função `compute_all_scores`** dentro dos Notebooks Spark (V2 e V3). 
Na tradução do backend `minimax.py` para a otimização em bits, o trecho de repasse de turno:
```python
child = deep_evaluate(..., cl == 0, ...)
```
Foi escrito com `==` em vez de `>`. Isso causou a **inversão total das regras do jogo na rotulação dos dados**:
- Se a IA fechasse uma caixa (`cl = 1`), `cl == 0` dava `False` (a Engine achava que o turno passava para o adversário, anulando a jogada extra).
- Se a IA NÃO fechasse caixa (`cl = 0`), `cl == 0` dava `True` (a Engine achava que a IA continuava jogando e ganhando turnos extras no vazio).

### Impacto
- **Toda a rotulação (scores) de profundidade 7 gerada até o dia 23 de Abril estava invertida/enviesada.** 
- O plateau da BoxNet em ~36% (Tentativas 5 e 6) era literalmente a CNN confusa tentando aprender um jogo de regras ao contrário.
- A "regressão" da profundidade 7 vs 6 ocorreu porque quanto mais profundo o Minimax pensava nas regras erradas, mais ele escolhia lixo topológico.

### Decisão e Resolução
1. O bug foi instantaneamente corrigido (`cl > 0`).
2. A hipótese da topologia aleatória (que nos levou à criação do Dataset V3 com AutoPlay) foi descartada como vilã exclusiva, mas o pipeline V3 foi **MANTIDO E VALIDADO** porque ele gera partidas reais, o que provou ser de valor inestimável para generalização da rede.
3. Todo o dataset corrompido foi expurgado, e iniciaremos o Treinamento Real 1.0 utilizando os Q-Values corretos do V3.

---

## 2026-04-21 — Documento de argumentação CNN vs Minimax criado

**Decisão.** Criar `docs/tcc/argumentacao_cnn_vs_minimax.md` com todos os
argumentos para justificar a CNN em vez do Minimax puro.

**Motivação.** Banca do TCC certamente questionará a escolha. O documento
cobre: velocidade (20s vs 3ms, dados medidos no Ryzen 5700X), latência
variável do Minimax, portabilidade TFLite, dificuldade ajustável por
temperatura, analogia com AlphaGo/AlphaZero (destilação de política),
limitações honestas e narrativa unificada pronta para apresentação.

**Conteúdo:** 8 seções com argumentos curtos (30s) e longos (3 min) para
a banca, tabela comparativa final e respostas preparadas para questionamentos.

---

## 2026-04-21 — Avaliador por partidas reais implementado

**Decisão.** Criar `gerador_dados/avaliador_partidas.py` e Cell 9 no notebook
para avaliar a CNN jogando partidas completas contra o Minimax em diferentes
profundidades (1, 3, 5, 6). 200 partidas por profundidade (100 CNN primeiro,
100 CNN segundo).

**Motivação.** Taxa de vitória é autoexplicativa para a banca — elimina a
necessidade de defender OMA como "nova métrica". "A CNN vence o Minimax
profundidade 5 em 65% das partidas sendo 100× mais rápida" é mais poderoso
do que qualquer métrica estática.

**Expectativas:** CNN deve vencer ~85–95% vs profundidade 1, ~70–80% vs
profundidade 3, ~60–70% vs profundidade 5, ~45–55% vs profundidade 6.

**Impacto:**
- `gerador_dados/avaliador_partidas.py`: script standalone + funções importáveis
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb`: Cell 9 adicionada (roda após TFLite)
- `docs/metricas_e_conceitos.md`: seção 9 adicionada com narrativa para banca

---

## 2026-04-21 — Documento de métricas e conceitos criado

**Decisão.** Criar `docs/metricas_e_conceitos.md` com explicação completa de:
Top-1/Top-3/Top-5, OMA (origem, cálculo, literatura relacionada), Temperatura
nos soft targets e sample_weight — tudo no contexto do Jogo dos Pontinhos,
com argumentação pronta para a banca do TCC.

**Motivação.** O usuário não conhecia essas métricas e precisava de material de
estudo para a defesa. A origem da OMA como métrica proposta pelo projeto (não
padronizada) é explicada com honestidade e comparada com conceitos similares
da literatura (AlphaGo, KataGo, imitation learning, VQA).

---

## 2026-04-21 — Regressão da Rodada 3 e descoberta do OMA=99%

**Contexto.** BoxNet v3 rodada 3 (300k, T=0.5, sample_weight) regrediu em todas
as métricas vs rodada 2 (210k, T=1.0, sem sample_weight). Top-1 caiu 2.4pp,
top-3 caiu 3.2pp apesar de 50% mais dados. Diagnóstico detalhado abaixo.

**Decisão.** Reverter T=1.0 e remover sample_weight para a rodada 4. Manter
300k dados e max_epochs=120. Adotar **Optimal Move Accuracy (OMA)** como
métrica principal do projeto.

**Por que T=0.5 não ajudou:**
A temperatura só diferencia moves com scores diferentes. Empates exatos do
Minimax (frequentes na abertura) distribuem probabilidade uniforme entre
equivalentes independente de T. A mudança foi ineficaz para o problema real.

**Por que sample_weight prejudicou:**
States de abertura têm ~6.8 equivalentes → peso médio 1/6.8 ≈ 0.15. O modelo
treinou com 85% menos gradiente nas posições mais comuns, mas foi avaliado com
peso normal. Top-3 de abertura caiu para 40.6% (era provalmente ~60%+ antes).

**Descoberta central — OMA=99%:**
O modelo escolhe uma jogada Minimax-ótima 99% das vezes. O top-1 de 33% mede
o "acerto do desempate canônico", não qualidade estratégica. H_0_1 acumula
support=8.351 (20% do test set) porque é o primeiro label na ordenação
canônica e ganha o argmax de todos os states com empate — mas o modelo escolhe
H_0_3 ou H_2_1 (igualmente ótimas), contando como "erro" de top-1.

**Nova métrica oficial:** OMA = percentual de predições dentro do conjunto
Minimax-ótimo. Implementada no Cell 7 do notebook.

**Alternativas descartadas:**
- Manter T=0.5 e sample_weight: causa provada da regressão.
- Hybrid loss (KLD + 0.1×CE): adicionaria complexidade; OMA já é 99%, teto real.
- Aumentar profundidade Minimax para 7: melhora qualidade mas 50% mais lento;
  postergado para após confirmar que arquitetura é o gargalo.

**Impacto:**
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 3: T=1.0 restaurado.
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 6: sample_weight removido.
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 4: tabela com rodada 3
  (resultados reais) e rodada 4 (planejada); nota sobre OMA como métrica oficial.
- `docs/jogo_pontinhos/historico_tentativas_treinamento.md`: rodada 3 completa + rodada 4 planejada.

---

## 2026-04-21 — Documento detalhado de tentativas de treinamento

**Decisão.** Criar `docs/jogo_pontinhos/historico_tentativas_treinamento.md` com registro
narrativo de cada experimento: CNN ingênua → MLP → BoxNet v1 → v2 → v3 rodadas
1, 2 e 3 (planejada). Para cada tentativa: o que foi feito, por que, o que não
funcionou, o que aprendemos e o próximo passo.

**Motivação.** A tabela compacta do notebook (Cell 4) não tem espaço para
argumentação acadêmica. O documento separado serve tanto para retrospectiva
interna quanto para a banca do TCC questionar as decisões de modelo.

**Tabela no Cell 4** do notebook também atualizada: adicionadas colunas top-3,
top-5 e dados, e preenchidos os resultados reais das rodadas 1 e 2 do v3.

---

## 2026-04-21 — Novas métricas diagnósticas: fase do jogo e Optimal Move Accuracy

**Contexto.** BoxNet v3 treinado em 210k amostras atingiu top-1 ≈ 35% com gap
treino/val de -0.19pp (zero overfitting). O teto do top-1 é estrutural: estados
de abertura têm múltiplas jogadas Minimax-equivalentes; o argmax do soft target
escolhe uma arbitrariamente, e o modelo pode escolher outra igualmente válida —
deprimindo o top-1 sem indicar erro estratégico.

**Decisão.** Adicionar duas métricas ao Cell 7 do notebook:

1. **Accuracy por fase do jogo** — divide o test set em Abertura (0–10 traços),
   Meio-jogo (11–20) e Final (21–31). Espera-se que top-1 cresça com o número
   de traços jogados, pois states finais têm menos equivalências.

2. **Optimal Move Accuracy** — verifica se a predição top-1 pertence ao conjunto
   Minimax-ótimo (`score == max_score`). Métrica mais justa para este domínio.

**Alternativas consideradas.**
- Temperatura T=0.5 (distribuições mais sharp → melhor top-1): postergado para
  após ver os resultados das novas métricas com 300k dados.
- `sample_weight` pelo inverso de jogadas equivalentes: postergado pelo mesmo
  motivo.

**Impacto.** `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 7 atualizado.

---

## 2026-04-20 — Adoção de soft targets (Q-values do Minimax) no dataset

**Contexto.** A primeira iteração do treino da CNN (BoxNet v2, 4×3) plateauou em
val_top1 ≈ 36% mesmo com gap treino/val controlado em ~9.6pp. As métricas
val_top3 ≈ 70% e val_top5 ≈ 83% indicam que o modelo aprende a *região* certa,
mas o argmax do Minimax descarta jogadas equivalentes (várias com mesmo score),
criando ambiguidade artificial no rótulo.

**Decisão.** Mudar o formato do dataset para gravar o vetor completo de
Q-values (`scores`, shape `(N, 31)` para o tabuleiro pequeno) ao lado do
argmax (`rotulos`). Treino futuro usará `KLDivergence` sobre o softmax
mascarado dos scores, no estilo "policy distillation" do AlphaZero.

**Alternativas consideradas.**
- *Apenas adicionar `class_weight` ao fit:* corrigia desequilíbrio mas não o
  problema de ambiguidade; ganho estimado +1–2pp vs. +15–25pp esperado da
  abordagem escolhida.
- *Aumentar profundidade do Minimax mantendo argmax:* não resolve a
  ambiguidade entre jogadas com score idêntico.

**Impacto.**
- `gerador_dados/minimax.py`: nova função `melhor_jogada_com_scores()`
  reaproveitando o mesmo loop (custo computacional zero).
- `gerador_dados/tabuleiro.py`: helper `todos_labels_canonicos()` para
  indexação determinística.
- `gerador_dados/gerador.py`: `.npz` agora inclui `scores` e
  `labels_canonicos`.
- **Datasets antigos (formato sem `scores`) ficaram incompatíveis e devem ser
  apagados.** Os 50k já gerados foram descartados.

**Sentinela usada para slots indisponíveis:** `-1e9` em `float32`. O notebook
deve mascarar antes do softmax.

---

## 2026-04-20 — Alvo de geração: 200k–300k registros, profundidade 6

**Contexto.** Com a paralelização via `ProcessPoolExecutor` (Gemini ajustou
para usar `cpu_count - 2` workers) e profundidade 5, o gerador produz ~50k/h.
O usuário relatou capacidade prática de gerar centenas de milhares de
registros ao longo de dias.

**Decisão.**
- Alvo padrão recomendado no guia: **200k** (sweet spot — diminishing returns
  acima disso para o pequeno).
- Usuário escolheu rodar **300k** dado o orçamento de tempo disponível.
- Profundidade recomendada: **6** (equilíbrio qualidade/velocidade do
  "professor"). 5 só se realmente precisar acelerar.

**Alternativas consideradas.**
- *Manter 50k:* insuficiente para 31 classes com soft targets diluídos.
- *Gerar 500k+:* custo-benefício ruim — preferível investir tempo em
  profundidade maior do que em volume.

**Garantia operacional.** O parâmetro `--total` do CLI sobrescreve o checkpoint
a cada execução. É seguro começar com `--total 300000` e mais tarde rodar
`--total 200000 --retomar` — o loop simplesmente para quando atinge o novo
alvo, sem apagar lotes já gerados.

---

## 2026-04-20 — Em aberto: desbalanceamento centro vs. bordas

**Contexto.** O `classification_report` da BoxNet v2 mostrou F1 de centro
(`H_2_1` ≈ 0.43, support 282) muito superior ao das bordas (`H_0_3` ≈ 0.17,
support 167). Causa provável dupla: (a) frequência menor das bordas no
dataset; (b) ambiguidade do argmax — bordas empatam em score com mais
frequência na abertura/midgame, e o sorteio entre empates produz rótulos
ruidosos.

**O que já mitiga indiretamente.**
- Simetria 4× (multiplica bordas também, mas não muda a proporção).
- **Soft targets / KLDivergence** (decisão acima) — ataca a causa (b)
  diretamente: a rede aprende "qualquer uma dessas três bordas serve" em vez
  de adivinhar a sorteada.

**O que NÃO foi feito (decisão deliberada de adiar).**
- `sample_weight` por inverso da frequência da classe do `argmax(scores)`.
  Não usamos `class_weight` porque a loss agora é `KLDivergence` sobre
  distribuição (não classe única).
- Amostragem viesada no `_gerar_estado_aleatorio` favorecendo estados onde a
  jogada ótima é de borda — descartado por complexidade e baixo retorno
  esperado.

**Critério de retomada.** Após o treino com o dataset novo (Q-values, 200–300k),
re-avaliar `classification_report` por classe. Se bordas continuarem com F1
< 0.25 enquanto centro > 0.40, adicionar `sample_weight` no `fit`. Se a
diferença encolher para < 10pp, considerar o problema resolvido.

---

## 2026-04-20 — Notebook atualizado: BoxNet v2 → v3 (KL Divergence)

**Arquivo:** `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb`

**Células alteradas:**
- **Cell 2 (markdown):** atualizada para descrever carregamento de `scores`,
  permutações de simetria e soft targets.
- **Cell 3 (carregamento):** reescrita. Agora lê `scores` e `labels_canonicos`
  do `.npz`; usa `labels_canonicos` como ordem canônica de classes (em vez de
  `sorted(np.unique(y_str))` — as duas ordens diferem); pré-computa 3
  permutações de índice para augmentação; augmenta estado e vetor de scores
  juntos; aplica softmax mascarado com `T=1.0` para gerar soft targets `(N,31)`;
  mantém `y_*_idx = y_soft.argmax(axis=1)` para métricas de avaliação.
- **Cell 4 (markdown):** tabela de histórico atualizada com BoxNet v3.
- **Cell 5 (modelo):** loss trocada de
  `CategoricalCrossentropy(label_smoothing=0.05)` para `KLDivergence()`;
  nome `BoxNet_v3_ArenaSagaz`.
- **Cell 7 (avaliação):** coluna `kld_loss`; `classification_report` usa
  `y_test_idx` (argmax do soft target); gráfico rotulado como "KL Divergence".

**Compatibilidade:** exige dataset no novo formato (com `scores`). Arquivos
`.npz` sem esse campo lançam `ValueError` na leitura.

---

## 2026-04-20 — Documentação técnica para defesa do TCC

Criados/atualizados documentos de argumentação acadêmica:
- `docs/jogo_pontinhos/soft_targets_kl_divergence.md` — explicação completa de soft targets,
  KL Divergence vs Categorical Crossentropy, onde o argmax ainda existe, e
  resposta modelo para a banca.
- `docs/jogo_pontinhos/justificativa_50k_amostras.md` — atualizado para refletir a nova
  realidade: 200–300k registros, paralelização (1 semana → ~6h), soft targets,
  e Data Augmentation por simetria D₂. O documento antigo citava 300k como
  "fisicamente impossível" — estava desatualizado após a migração para
  `ProcessPoolExecutor`.

---

## 2026-04-20 — Diretriz: documentação viva obrigatória

**Decisão.** Toda mudança arquitetural, de formato de dados, de parâmetros
recomendados ou de rota técnica deve atualizar os `.md` relevantes na mesma
resposta. Diretriz codificada em `CLAUDE.md` para não depender da memória do
usuário.
