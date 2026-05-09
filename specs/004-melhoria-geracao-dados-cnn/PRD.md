# PRD — CNN Pontinhos com Canais Estruturais e Cobertura de Final de Jogo

> **Status:** Draft — pronto para servir de input ao `/speckit-plan` e em seguida `/speckit-specify`.
> **Autor:** Time Arena Sagaz — sessão de revisão de modelo CNN para o Jogo dos Pontinhos.
> **Data inicial:** 2026-05-05.
> **Última revisão:** 2026-05-07 — revisão sobre proporção de sampling (eliminação de p=1, novo mix 5/0/40/55), deduplicação obrigatória, aproveitamento dos 314.323 únicos já gerados (cálculo do complemento fixado em §4.1.3, sem notebook de planejamento separado), separação do enriquecedor de canais em notebook próprio (com sobrescrita), pré-computação dos 11 canais no NPZ, ajustes nas decisões D2/D3/D4 e na Fase A (agora dividida em A.1 = geração + A.2 = enriquecimento; o antigo "A.1 planejamento" foi eliminado). **Correção 2026-05-07 (tarde):** canal 5 renomeado de `dono_caixa` (ternário `{-1, 0, +1}`) para `caixa_fechada` (binário `{0, 1}`) — alinhamento com o domínio real do dataset (`contexto_1_geracao_dataset` no contrato nunca tem -1). Adicionado campo `nomes_canais` ao NPZ enriquecido (auto-descrição) com validação cruzada contra a PRD §4.2.
> **Última revisão anterior:** 2026-05-06 — Fase 0 concluída (Cenário X3 confirmado em 600 partidas); inseridas novas Fases E (sample_weight refinado — D9) e F (value head — D10); antigas E/F renumeradas G/H; faixa crítica de meio-jogo unificada para [12, 17].
> **Escopo do feature branch sugerido:** `004-melhoria-geracao-dados-cnn`.

---

## 1. Resumo executivo

Nossa CNN BoxNet v3 (variante AutoPlay/Minimax-9, treinada com 300 mil tabuleiros 4×3) hoje vence:
- **92%** das partidas contra Minimax(p=1)
- **60%** contra Minimax(p=3)
- **44%** contra Minimax(p=5)
- **40%** contra Minimax(p=6)

### 1.1 O que sabemos a partir do relatório de erros (e o que NÃO sabemos)

A análise do relatório `tmp_analise/RELATORIO_ERROS_CNN.md` (765 caixas perdidas avaliadas, 505 erros reais) identificou que **98% dos erros do tipo "deixou de fechar caixa grau-3 disponível"** acontecem na **jogada 30 do tabuleiro pequeno** (29 traços preenchidos), e **99% desses erros** ocorrem em estados onde existe **uma única caixa grau-3 disponível** — ou seja, dentro da classe de erro detectada, a captura que a CNN deveria fazer é dramaticamente óbvia, e ainda assim ela escolhe uma aresta de borda em vez da aresta interna que fecharia as 2 últimas caixas do tabuleiro. Ao selecionar a aresta da borda a CNN passa a jogada para o adversário que não tem outra opção a não ser fechar estas 2 caixas.

**Importante — escopo limitado do diagnóstico atual:** o relatório `tmp_analise/RELATORIO_ERROS_CNN.md` se baseia exclusivamente em eventos de "caixa-perdida" (situações em que existia uma caixa grau-3 capturável e a CNN não a fechou). Esse universo **não cobre** modos de falha que provavelmente também afetam a performance:

1. **Decisões estratégicas erradas no meio de jogo** (jogadas 10–25): abrir uma cadeia longa quando deveria abrir uma curta, ou vice-versa. Não aparecem como "caixa-perdida" porque nessa fase pode não existir grau-3 no tabuleiro — são erros de paridade/controle de cadeias.
2. **Sacrifícios mal calibrados:** sacrificar 2 caixas quando deveria sacrificar 4 (ou o oposto). O detector atual não distingue.
3. **Perda de "control" cedo:** uma jogada estratégica errada na transição abertura→fase quente entrega o controle da paridade. O custo aparece muitas jogadas depois, sem nunca passar por uma situação grau-3 não capturada.
4. **Caixas perdidas em série dentro de uma cadeia mal aberta:** se a CNN abre cedo demais uma cadeia de N caixas, o oponente fecha as N. O avaliador conta isso como N eventos individuais distribuídos ao longo de várias jogadas — inflando artificialmente a contagem da jogada de captura e **subnotificando** a jogada estratégica original (que aconteceu antes, sem grau-3 no tabuleiro).

### 1.2 Sinais de que existe uma segunda causa raiz (estratégica) além da jogada 30

A escala de queda dos win-rates contra Minimax mais profundo é assinatura forte de **erro estratégico de meio de jogo**, não de erro tático isolado de fim:

- Se a única falha fosse "última jogada", a CNN venceria Minimax(p=1) próximo de 100% (p=1 não arma trapaças sofisticadas que culminam em "entregar uma grau-3 na penúltima jogada"). Hoje vence 92%.
- O gap entre p=1 (92%) e p=6 (40%) é grande demais para ser explicado por uma falha que ocorre com qualquer adversário, independente da profundidade. Quanto mais profundo o oponente, mais ele explora **decisões estratégicas erradas no meio do jogo** — exatamente a classe que o relatório atual não captura.

### 1.3 Viés posicional observado

Identificamos forte **viés para arestas de borda externa** (linhas/colunas 0, 6, 8) nos pares "deveria→jogou", indicando que a CNN aprendeu uma representação com peso desproporcional em features de borda durante o treino.

### 1.4 Evidência visual do erro tático elementar (revisão de 2026-05-06)

A análise complementar de divergência estratégica (Seção 2.4), executada em sessão de revisão posterior à redação inicial deste PRD, gerou retratos PNG por jogada da CNN. Em revisão visual desses retratos, identificamos um **padrão recorrente** e qualitativamente revelador na **30ª jogada da partida** (com 29 traços já preenchidos, 2 traços livres restantes):

- **Estado:** duas caixas vizinhas, uma já em grau-3 (3 lados preenchidos), outra em grau-2 (2 lados preenchidos), separadas por uma aresta interna ainda livre que é o 4º lado de ambas as caixas potencialmente.
- **Jogada ótima:** preencher a aresta interna → fecha a caixa grau-3 → ganha turno extra → fecha a outra → +2 caixas para a CNN.
- **Jogada da CNN:** preencher a aresta externa (lado faltante da caixa grau-2) → não fecha caixa, transforma a grau-2 em grau-3 → adversário joga a aresta interna e fecha as duas caixas simultaneamente → +0 CNN, +2 adversário (Δ = 4 caixas).

Caso canônico: `tmp_analise/retratos_divergencia/Minimax_p_1/cnn1_partida0010/jogada030_t29_d4_fatal.png`. **Importante:** este caso ocorreu contra Minimax(p=1) — o adversário mais fraco do experimento. Profundidade 1 não exige antecipação; o erro é puramente tático e visível em uma jogada à frente.

**Implicações para o diagnóstico:**

1. **A CNN está aplicando uma heurística de sacrifício no contexto errado.** No meio de jogo, doar 2 caixas para receber o controle de uma cadeia maior é, em algumas situações, o correto. Mas com apenas 2 traços restantes, **não há cadeia maior nenhuma** — a CNN aprendeu o padrão "preencher a aresta entre dois grau-3 doa caixas" sem condicionar à existência de jogada futura.
2. **Esse estado (29 traços = 93,5% de preenchimento) está fora da faixa atual do dataset (15-85%).** A CNN nunca foi exposta a esse tipo de posição durante o treino. Qualquer profundidade de supervisor é inútil sem cobertura amostral. Reforça D1.
3. **O efeito é detectável com Minimax(p=2)** — diferencial declarado pelo oráculo é 4 caixas. Se nem com supervisor p=9 (atual) a CNN aprendeu, a causa é **distribuição de exemplos**, não profundidade.

### 1.5 Estratégia geral

Este PRD especifica um conjunto de mudanças coordenadas — geração de dados, augmentação no carregamento, novos canais estruturais, calibração de gradiente em meio-jogo, value head AlphaZero-style e ajustes de loss — que atacam **duas categorias de causa raiz**:

- **Categoria A (tática, fim de jogo):** os 505 erros tabelados na jogada 30, incluindo o padrão "ignorar grau-3 disponível" descrito em 1.4. Confirmada em §2.4: 87.8% dos fatais (360/410) estão em t=29. Atacada principalmente pelas Fases A+B (cobertura terminal) e Fase C (augmentação por simetria contra viés de borda) e Fase D (canal `eh_grau3`).
- **Categoria B (estratégica, meio de jogo):** decisões de controle de paridade e escolha de cadeia/loop. Confirmada em §2.4: 16.8% das partidas perdidas têm divergência fatal precoce (≤ 25 traços), estável nos três adversários (p=3/5/6). Atacada principalmente pela Fase D (canais estruturais `em_cadeia_*`, `em_loop`, `em_cadeia_aberta_uma_ponta`), pela **Fase E** (sample_weight refinado por Δ-top2 em t=12–17 — ver D9) e pela **Fase F** (value head AlphaZero-style — ver D10).

A magnitude relativa de cada categoria foi **medida empiricamente** pela análise complementar de divergência estratégica (Seção 2.4) **antes** do início da Fase A. **Veredicto: Cenário X3** (16.8% de fatal precoce, faixa misto-estratégica). Esse resultado motivou a inserção das novas Fases E e F entre as antigas D e (antiga) E, esta última renumerada G.

**Cada fase será implementada, treinada e avaliada isoladamente** para que possamos atribuir o ganho/regressão a uma mudança específica.

---

## 2. Objetivos e métricas de sucesso

### 2.1 Objetivos qualitativos

- **Eliminar a falha tática de não capturar a única caixa grau-3 disponível** na jogada 30 (Categoria A).
- **Reduzir erros estratégicos de meio de jogo** que entregam controle de paridade (Categoria B), na medida em que a análise complementar (Seção 2.4) confirme sua existência.
- **Eliminar o viés posicional para arestas de borda externa** identificado no relatório.
- **Não degradar performance em fases iniciais e médias**, onde a CNN já tem boa performance.
- **Não quebrar o pipeline de inferência mobile** (TFLite / Flutter): o modelo continua aceitando matriz `(9, 7)` int8 e devolvendo 31 probabilidades.
- **Permitir comparação iterativa (uma mudança por vez)** entre cada fase, com métricas comparáveis em todas elas.

### 2.2 Métricas de sucesso (medidas a cada fase)

Métrica primária — win-rate contra Minimax:

| Métrica | Baseline (medido em 600 partidas, 2026-05-06) | Meta final (Fase H) |
|---|---|---|
| Vitórias vs Minimax(p=1) | 92% (medição anterior; p=1 descartado em diagnósticos) | ≥ 96% |
| Vitórias vs Minimax(p=3) | **54.5%** | ≥ 80% |
| Vitórias vs Minimax(p=5) | **42.0%** | ≥ 70% |
| Vitórias vs Minimax(p=6) | **38.0%** | ≥ 60% |

Métrica secundária — erros táticos (Categoria A):

| Métrica | Baseline (hoje) | Meta final |
|---|---|---|
| Total de erros reais (`analisa_padrao_erros.py`) | 505 | ≤ 80 |
| Concentração no top-3 pares "deveria→jogou" | 153 (30%) | balanceado, sem par com >5% |
| Erros em estados com uma única caixa grau-3 | 496 (98%) | ≤ 30 |

Métrica secundária — erros estratégicos (Categoria B, definida na Seção 2.4):

| Métrica | Baseline (600 partidas, 2026-05-06) | Meta final |
|---|---|---|
| Divergências fatais totais (Δ-score ≥ 4) | 410 (média 0.68/partida) | redução ≥ 50% |
| Fatais em meio (t ∈ [10, 24]) | 50 (12.2% dos fatais) | redução ≥ 50% |
| % partidas perdidas com fatal precoce (≤ 25 traços) | 16.8% (32/191) | ≤ 8% |
| % partidas perdidas sem nenhum fatal (acúmulo de moderadas) | 51.8% (99/191) | ≤ 25% |

Métricas operacionais:

- Tamanho do modelo TFLite: ≤ 200 KB (hoje ~100 KB; aumento aceito por canais extras).
- Tempo de inferência mobile: ≤ 5 ms/jogada (hoje ~0.1 ms — folga grande).
- Tempo de geração de dataset 500k em Databricks com Minimax(p=9): ≤ 4 horas (hoje 300k em ~2h).

### 2.3 Critérios de não-regressão

A cada fase, comparar os 4 win-rates (p=1, p=3, p=5, p=6) com a fase anterior. Se **alguma queda > 3 pontos percentuais** for observada sem ganho compensatório em outra dimensão, a fase **deve ser revertida ou recalibrada** antes de prosseguir.

### 2.4 Análise complementar de divergência estratégica — EXECUTADA (2026-05-06) — Cenário X3 confirmado

**Status:** Esta análise foi executada antes de iniciar a Fase A. Os números abaixo são reais, não placeholders. Detalhes em `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md`.

**Motivação:** o relatório original (`RELATORIO_ERROS_CNN.md`) só enxerga falhas táticas de captura. Para calibrar o peso relativo das fases, quantificamos a fração da derrota contra Minimax(p=3/5/6) que vem de **erros estratégicos de meio de jogo** (Categoria B), separando-os de erros táticos puros de fim (Categoria A).

#### 2.4.1 Setup do experimento

- **Modelo avaliado:** `modelos/pontinhos_pequeno_profundidade_9.tflite` (BoxNet v3 V5, baseline atual).
- **Adversários:** Minimax(p=3), Minimax(p=5), Minimax(p=6). p=1 descartado em decisão de 2026-05-06 (ver `docs/historico_decisoes.md`) — sua aleatoriedade contamina a análise.
- **Oráculo de referência:** Minimax adaptativo — p=5 quando arestas livres ≥ 26, p=7 entre 18 e 25, p=9 quando arestas livres ≤ 17. Garante que a comparação não é cega em estados onde o estado de jogo cabe inteiro em uma árvore p=9.
- **Volume:** 200 partidas × 3 adversários = **600 partidas**, ~9.4k jogadas analisadas.
- **Tempo total:** 9370 s (~2.6 h) com 12 workers paralelos.
- **Limiares de Δ-score (caixas):**
  - Inócua: Δ ≤ 1
  - Moderada: 2 ≤ Δ ≤ 3
  - Fatal: Δ ≥ 4

#### 2.4.2 Resultados — win-rate e divergências por adversário

| Adversário | Partidas | Vit. CNN | % Vit. | Divergências | Fatais | Fatais/partida |
|---|---:|---:|---:|---:|---:|---:|
| Minimax(p=3) | 200 | 109 | **54.5%** | 3323 | 154 | 0.77 |
| Minimax(p=5) | 200 |  84 | **42.0%** | 3208 | 144 | 0.72 |
| Minimax(p=6) | 200 |  76 | **38.0%** | 3075 | 112 | 0.56 |

#### 2.4.3 Distribuição dos fatais por fase do jogo

Fases (por nº de traços antes da decisão):
- Abertura: 0–9
- Meio: 10–24 (decisões de paridade/controle de cadeias)
- Transição: 25–27
- Fim: 28–30 (tática de captura grau-3)

| Adversário | Fatais (meio) | Fatais (transição) | Fatais (fim) |
|---|---:|---:|---:|
| Minimax(p=3) | 15 | 0 | 139 |
| Minimax(p=5) | 18 | 0 | 126 |
| Minimax(p=6) | 17 | 0 | 95 |
| **Total**     | **50 (12.2%)** | **0** | **360 (87.8%)** |

**Observação chave:** 88% dos fatais estão em **t=29** (penúltima jogada do tabuleiro pequeno) — confirma que a Categoria A (tática) ainda domina em volume bruto. Mas como veremos em 2.4.4, **a Categoria B explica a estrutura das partidas perdidas**, não a Categoria A sozinha.

#### 2.4.4 Cruzamento — partidas perdidas × tipo de erro

Para cada partida perdida pela CNN classificamos:
- **Fatal precoce:** existe divergência fatal em jogada com ≤ 25 traços (= erro estratégico de meio).
- **Fatal apenas tardia:** divergência fatal só com ≥ 26 traços (= erro tático puro).
- **Sem fatal:** nenhuma divergência fatal — perdida por acúmulo de divergências moderadas ou pelo adversário ter jogado bem.

| Adversário | Perdidas | Fatal precoce | Fatal tardia | Sem fatal | % precoce |
|---|---:|---:|---:|---:|---:|
| Minimax(p=3) | 42 |  7 | 21 | 14 | **16.7%** |
| Minimax(p=5) | 60 | 11 | 22 | 27 | **18.3%** |
| Minimax(p=6) | 89 | 14 | 17 | 58 | **15.7%** |
| **Total**     | **191** | **32** | **60** | **99** | **16.8%** |

**Achado crítico:** a taxa de fatal precoce é **estável em 15–18%** nos três adversários. Isso é evidência forte de **erro sistêmico da CNN**, não induzido pelo adversário. Adversário mais forte (p=6) ou mais fraco (p=3) — a CNN comete fatal precoce na mesma proporção das partidas que perde.

**Achado adicional:** das 89 partidas perdidas vs p=6, **58 (65%) não têm nenhum fatal** — perdidas por acúmulo de moderadas. Isso reforça a importância de cobertura ampla de dados (Fases A/B/C) como base obrigatória — não há "uma jogada-chave" que fixe o problema; é qualidade média.

#### 2.4.5 Histograma de fatais e moderadas por nº de traços

| Traços | Fatais | Moderadas | Observação |
|---:|---:|---:|---|
|  9–10 |  0 |  6 | Abertura limpa |
| **11**  |  0 | 34 | |
| **12**  |  4 | 83 | **Sangra silenciosa — sub-ótimas frequentes** |
| **13**  |  0 | 52 | |
| **14**  | 28 | 42 | **Pico de fatais no meio** |
| **15**  |  7 | 22 | |
| **16**  |  9 |  6 | |
| **17**  |  0 |  2 | Cauda do meio |
| 18–24 |  2 | 17 | Estável |
| 25–27 |  0 |  0 | Transição limpa |
| **28**  |  4 |  0 | |
| **29**  | **356** |  0 | **Pico massivo — caixas-de-graça grau-3** |
| 30    |  0 |  0 | Decisão trivial |

**Inferência operacional:** a faixa crítica de meio-jogo é **t=12 a t=17** (não t=13–17 como assumido inicialmente). t=12 tem o maior volume de moderadas (83); t=14 tem o pico de fatais (28). Faixa crítica unificada para **[12, 17]** em todos os gates por faixa.

#### 2.4.6 Padrões sistêmicos — top pares "ótima → CNN" (Δ ≥ 2)

| Jogada ótima | Jogada CNN | Fase | N |
|---|---|---|---:|
| H_2_1 | V_1_0 | fim | 37 |
| H_2_3 | H_0_3 | fim | 32 |
| H_6_3 | H_8_3 | fim | 30 |
| V_1_4 | V_1_6 | fim | 26 |
| V_1_4 | H_0_5 | fim | 24 |
| H_6_1 | H_8_1 | fim | 24 |
| H_6_1 | V_7_0 | fim | 23 |
| H_0_3 | V_7_2 | meio | 15 |
| H_4_1 | V_3_2 | meio | 12 |
| H_8_3 | V_7_2 | meio | 12 |

**Leitura qualitativa:**
- **Fase fim:** padrão consistente de viés para **bordas externas** (linhas/colunas 0, 6, 8) — confirma o viés posicional descrito em §1.3 e justifica a augmentação por simetria (Fase C).
- **Fase meio:** substituições estruturais que **cruzam o tabuleiro** (`H_4_1 → V_3_2`, `H_8_3 → V_7_2`) — sintoma de paridade/cadeia mal compreendida. Exatamente a Categoria B que motivou as decisões D9 (sample_weight refinado) e D10 (value head).

#### 2.4.7 Veredicto: Cenário X3 confirmado

Critérios definidos pré-execução:
- **Cenário X1:** < 10% das partidas perdidas têm fatal precoce → Fases A+B+C suficientes; D opcional.
- **Cenário X2:** > 30% das partidas perdidas têm fatal precoce → Fase D obrigatória.
- **Cenário X3:** 10–30% → manter plano completo, calibrar expectativas.

**Resultado: 16.8% médio (16.7% / 18.3% / 15.7%) → CENÁRIO X3.**

#### 2.4.8 Implicações para o plano de fases

1. **Plano A → B → C → D mantido integralmente.** X3 não permite pular D.
2. **Categoria A (87.8% dos fatais em t=29) atacada por:** cobertura terminal (Fase A — D1), augmentação por simetria (Fase C), canal `eh_grau3` (Fase D).
3. **Categoria B (16.8% das partidas perdidas) exige duas intervenções adicionais inseridas entre as Fases D e G (= antiga E):**
   - **Nova Fase E — Sample_weight refinado por Δ-top2 em t=12–17.** Empurrão sutil (~10% extra) nas amostras dessa faixa onde a top-2 mostra que a decisão importa. NÃO em t=29 (já coberto em D).
   - **Nova Fase F — Value head AlphaZero-style.** Multi-task learning com Q* normalizado como alvo auxiliar. Força a representação intermediária a codificar "quem está ganhando" — sinal estrutural em jogos de paridade.
4. **Acúmulo de moderadas (29% das partidas perdidas vs p=6 sem nenhum fatal):** confirma que cobertura ampla das Fases A/B/C é base obrigatória; "uma só intervenção mágica" não resolve.
5. **Estabilidade entre adversários (15–18%):** evidência de erro sistêmico → favorece intervenções estruturais (D, F) sobre intervenções táticas estreitas.

**Gate de Fase 0 (esta análise) — atendido em 2026-05-06.** Decisão registrada em `docs/historico_decisoes.md` na entrada de mesma data.

### 2.5 Métricas de validação por faixa de preenchimento (treino)

**Motivação:** a curva U-invertida da D1 (5–11→0.5/10%, 12–17→1.0/20%, 18–23→1.7/28%, 24–28→2.5/32%, 29–30→1.5/10%) atribui pesos deliberadamente desiguais às faixas de traços preenchidos. Sem métricas separadas por faixa, a accuracy global pode mascarar dois problemas opostos: (a) a faixa 29–30 com peso 1.5 sobre apenas 10% das amostras pode não ser suficiente para corrigir o erro tático elementar da Seção 1.4, ou (b) o foco na fase quente (24–28) pode degradar performance em estados de abertura.

**Métrica obrigatória durante o treino e a avaliação de cada fase (B, C, D, E, F):**

| Faixa de preenchimento | Faixa de traços | Métrica primária |
|---|---|---|
| Abertura | 5–11 | top-5 accuracy ≥ 40% |
| **Crítica meio (paridade/cadeias)** | **12–17** | **top-3 accuracy ≥ 80%** — faixa-alvo da Fase E (D9) |
| 2ª metade | 18–23 | top-3 accuracy ≥ 95% |
| Fase quente | 24–28 | top-1 accuracy ≥ 80% |
| **Final** | **29–30** | **top-1 accuracy ≥ 95%** |

**Justificativa do piso 95% para a faixa final:** com 1 ou 2 traços livres, o estado é praticamente resolvido — Minimax(p=2) já decide com certeza. Não há ambiguidade legítima onde o supervisor poderia escolher uma jogada sub-ótima. Qualquer accuracy < 95% nesta faixa indica que a CNN ainda comete o erro de ignorar grau-3 disponível, e o gate da fase corrente deve **falhar**.

**Gate de não-regressão por faixa:** entre fases consecutivas (B→C→D), nenhuma faixa pode regredir mais que 2 pp. Útil para detectar quando uma mudança (ex.: augmentação por simetria) ajuda em algumas faixas mas degrada em outras.

**Onde implementar:** dentro do bloco de avaliação do `Treinamento_CNN_Arena_Sagaz_V6.ipynb` (Fase B em diante). Reaproveitar o split treino/val/teste já existente, segmentando o conjunto de teste por número de traços. Reportar tabela em `docs/historico_decisoes.md` ao final de cada fase.

**Justificativa da faixa crítica [12, 17]:** medições da Seção 2.4.5 mostram que **t=12 também sangra** (4 fatais + 83 moderadas — maior volume de moderadas em todo o histograma), além do pico de fatais em t=14 (28). t=12 não estava em versões anteriores deste PRD e foi incorporado em 2026-05-06. Faixa crítica unificada para [12, 17] em todos os gates por faixa e na Fase E.

---

## 3. Contexto técnico

### 3.1 Arquivos relevantes

- **Geração de dataset:** `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V4.ipynb` (Databricks + PySpark + Minimax(p=9), 31 arestas).
- **Treinamento:** `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V5.ipynb` (Colab/TensorFlow, BoxNet v3, KL Divergence).
- **Avaliação por partidas:** `notebooks/jogo_pontinhos/Avaliacao_CNN_vs_Minimax.ipynb`.
- **Análise de erros:** `tmp_analise/RELATORIO_ERROS_CNN.md` e `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md` + scripts `analisa_*.py`.
- **Contrato de codificação:** `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` (espelhado no frontend).
- **Lógica de jogo:** `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py`, `minimax_pontinhos.py`.

### 3.2 Estado atual do dataset NPZ

O NPZ atual contém:

| Campo | Shape | Conteúdo |
|---|---|---|
| `estados` | (N, 9, 7) int8 | Matriz crua: `0` (livre), `9` (aresta jogada), `8` (ponto fixo), `1`/`-1` (caixa fechada) |
| `rotulos` | (N,) str | Label canônico da melhor aresta (ex: `H_2_3`) |
| `scores` | (N, 31) float32 | Q-values do Minimax(p=9) por aresta canônica (`-1e9` para arestas inválidas) |
| `generation_mode` | (N,) int8 | 0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3 |
| `labels_canonicos` | (31,) str | Lista canônica de labels |
| `depth` | (1,) int32 | Profundidade Minimax usada na geração |

A faixa de preenchimento atual é **15% a 85%** (5 a 26 traços) — *o ponto onde a CNN mais erra (29 traços) não está no dataset*.

### 3.3 Estado atual do modelo (BoxNet v3 V5)

- Input: matriz `(9, 7, 1)` int8 normalizada para `{0, 1}`.
- Camada `Lambda` `para_grid_de_caixas` reorganiza em `(4, 3, 5)` com 5 canais geométricos: topo, base, esquerda, direita, interior.
- Stem Conv 3×3 (32 filtros) + BN + ReLU.
- 2 blocos residuais com SeparableConv2D (32 → 48 canais).
- GAP + Flatten concatenados → Dense(96) + BN + Dropout(0.5).
- Saída softmax 31 logits.
- Loss: KLDivergence sobre soft-targets gerados por softmax dos Q-values (T=1.0).
- ~74k parâmetros, ~100 KB em TFLite.

---

## 4. Decisões arquiteturais (com fundamentação)

### 4.1 Decisão D1 — Geração de dados expandida com cobertura terminal

**Decisão:** Aumentar a faixa de amostragem de `[0.15·n_edges, 0.85·n_edges]` para `[0.15·n_edges, 0.97·n_edges]` (de 5–26 traços para 5–30 traços), e usar **distribuição não-uniforme em forma de U invertido** com pico na "fase quente" do jogo (onde caixas começam a fechar em sequência).

**Por quê:**

1. O relatório de erros mostra que 98% dos 505 erros estão em estados com 29 traços. **Esses estados não existem no dataset atual.**
2. Distribuição uniforme entre 5 e 26 traços gasta ~22 amostras na "abertura" para cada amostra na "fase quente" — desperdício.
3. **A fase quente (≈18 a 26 traços)** é onde a maior parte das decisões estratégicas críticas acontece (sacrifícios, double-cross, decisão de qual cadeia abrir). Essa faixa precisa receber mais densidade.
4. Estados muito iniciais (5–9 traços) têm Q-values quase planos — a CNN aprende pouco com eles e ainda perpetua o problema de soft-target plano com gradientes fracos.
5. Estados quase terminais (30 traços = falta 1 aresta) têm decisão trivial (sobra geralmente 1 jogada legal). Não vale gastar 30% dos dados nisso, como uma distribuição linearmente crescente faria.

**Distribuição alvo (peso relativo por nº de traços):**

```
Distribuição final (total = 500.000):
- 5–11 traços (abertura):      11,10% das amostras ( 55.501) — peso relativo 0.5
- 12–17 traços (1ª metade):    31,52% das amostras (157.588) — peso relativo 1.0
- 18–23 traços (2ª metade):    44,12% das amostras (220.623) — peso relativo 1.7
- 24–28 traços (fase quente):  13,16% das amostras ( 65.792) — CAPEADO (ver nota abaixo)
- 29–30 traços (final):         0,10% das amostras (    496) — CAPEADO (ver nota abaixo)
```

> **Notas de revisão (2026-05-08):**
>
> **Bucket (29–30):** apenas C(31,29)+C(31,30) = 465+31 = **496 estados únicos possíveis**
> no tabuleiro 4×3. Limite físico absoluto — 100% do espaço foi coletado.
> (Originalmente peso 1.5 → 10% = 50.000. Fisicamente inviável.)
>
> **Bucket (24–28):** C(31,24..28) = 991.333 estados teóricos, mas o autoplay
> Minimax p=2 (sim_l2) e p=3 (sim_l3) converge para ~**57.020 posições práticas**,
> pois ambos seguem trajetórias de partidas "razoáveis" que cobrem apenas uma fração
> do espaço teórico. Mode_0 (uniform) contribuiu ~9.170 adicionais. Total coletado:
> **65.792 únicos** — espaço prático esgotado.
>
> **Redistribuição:** a cota liberada de (24–28) foi redistribuída em razão 20:28
> para (12–17) (+46.587) e (18–23) (+65.222), mantendo o total em 500.000.
>
> Ver `docs/historico_decisoes.md` (entrada 2026-05-08) para diagnóstico completo.
>
> **Revisão 2026-05-08 rev.5 — Consolidação empírica final:**
> mode_2 (sim_l2) também satura nos buckets (12–17) e (18–23). Cotas capeadas nos
> únicos reais; excedente redistribuído para mode_3. Distribuição final consolidada
> (**499.997 estados**): 55.501 / 169.875 / 223.551 / 50.867 / 203.
> Mix gen_mode real: 5,00% / 40,06% / 54,94% — praticamente inalterado do alvo.

A **manutenção de uma fração mínima (~10%) de amostras de abertura** é deliberada: a CNN precisa lidar com adversários "irracionais" que joguem aleatoriamente também. Sem essa cobertura ela pode regredir contra Minimax(p=1).

#### 4.1.1 Sub-decisão D1.a — Mix de geração autoplay/aleatório

O notebook V4 atual gera estados misturando 4 modos de sampling (`STRAT_MODES`):

| Modo | Significado | Peso V4 | Peso V5 (novo) |
|---|---|---:|---:|
| 0 | `uniform` (preenchimento aleatório de traços) | 0.15 | **0.05** |
| 1 | `sim_l1` (autoplay Minimax(p=1) × Minimax(p=1)) | 0.25 | **0.00** |
| 2 | `sim_l2` (autoplay Minimax(p=2) × Minimax(p=2)) | 0.55 | **0.40** |
| 3 | `sim_l3` (autoplay Minimax(p=3) × Minimax(p=3)) | 0.05 | **0.55** |

**Por quê eliminar p=1:** o relatório de divergência estratégica (§2.4) e a análise complementar de Fase 0 mostraram que estados produzidos por autoplay de Minimax(p=1) contaminam o conjunto de treino com posições que nunca apareceriam contra adversários sérios — p=1 não enxerga sequer uma jogada à frente, abre cadeias longas em horários absurdos, e muitos dos estados gerados são "lunáticos" no sentido formal. Esses estados **dilatam a cobertura sem qualidade estratégica** e foram apontados em revisão como provável fonte de viés.

**Por quê p=3 dominar (55%):** estados produzidos por dois Minimax(p=3) jogando entre si têm a estrutura estratégica mais próxima dos jogos reais que a CNN enfrentará após treino — são posições "razoáveis" no sentido de paridade/cadeia. Mesmo que o supervisor seja Minimax(p=9), o que importa para a CNN é **ver estados que se parecem com partidas reais**, e p=3 é a melhor aproximação prática.

**Por quê manter 5% de aleatório (uniform):** preserva robustez contra jogadores lunáticos no app real (humanos casuais, jogadores aleatórios). Sem essa fração mínima, a CNN regride contra adversários "irracionais".

**Por quê 40% de p=2:** complementa p=3 cobrindo posições com paridade ligeiramente diferente (p=2 não vê tão longe quanto p=3 e às vezes abre cadeias um turno mais cedo). Mantém diversidade estrutural.

**Implicação para Fase A:** o notebook `Otimizacao_Topologia_Rede_V5.ipynb` deve usar `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` por padrão. O peso 0.0 em modo 1 desliga completamente o ramo de geração `sim_l1` no V4 — pode ser parametrizado para permitir override em experimentos isolados.

#### 4.1.2 Sub-decisão D1.b — Deduplicação obrigatória

**Decisão:** Estados duplicados (mesma matriz `(9,7) int8`) **não devem entrar duas vezes no dataset de treino**, independentemente do modo de geração que os produziu.

**Motivação empírica:** análise dos 344.000 estados existentes em `dados/profundidade_minmax_9` mostrou **8,63% de duplicatas** (314.323 únicos / 344.000 totais), distribuídas entre todos os modos de geração. Estados duplicados:

1. **Inflam artificialmente o gradiente** em posições já bem cobertas — a CNN gasta capacidade aprendendo de novo o que já viu.
2. **Distorcem o split treino/validação/teste** quando as cópias caem em conjuntos diferentes — vazamento implícito de dados.
3. **Atrapalham a leitura do `analisa_padrao_erros.py`**, que conta erros independentemente de a posição ser única ou repetida.

**Implementação:**

- **No notebook de geração principal (Fase A — `Otimizacao_Topologia_Rede_V5.ipynb`):** manter um `set()` de hashes (`mat.tobytes()`) acumulado durante a execução. Se um estado já está no set, **descartar e regerar** (até 20 tentativas, idêntico ao retry atual). Reset do set apenas no início da geração.
- **No cálculo do complemento (executado uma única vez durante a redação do PRD em 2026-05-07; resultado em §4.1.3):** ao contar estados existentes para calcular o complemento, contar **apenas únicos**.
- **Ao consolidar dados antigos + novos no treinamento:** carregar todos os NPZs, deduplicar pela matriz crua, então aplicar split estratificado.

**Meta:** o NPZ final entregue à Fase B deve ter **≥ 500.000 estados únicos** (não 500.000 estados gerados com duplicatas).

### 4.2 Decisão D2 — NPZ enriquecido com TODOS os canais (geométricos + estruturais) pré-computados

**Decisão:** O NPZ passa a conter um campo extra `canais` de shape `(N, 4, 3, 11)` com **TODOS os 11 canais** (5 geométricos + 6 estruturais) já pré-computados — não mais derivados em runtime pela `Lambda` do modelo Keras.

**Por quê pré-computar os 5 canais geométricos também (decisão revisada em 2026-05-07):** o usuário apontou corretamente que se o NPZ não traz os 5 atuais, o notebook V6 *ainda precisaria* da `Lambda para_grid_de_caixas` para derivá-los. Pré-computar todos os 11 elimina essa ambiguidade: o NPZ enriquecido é a fonte única da verdade do tensor de entrada da CNN. O notebook V6 carrega `canais` direto e concatena no input. Mais simples, mais auditável, mais barato em CPU de treino (bytes prontos em vez de operações tensoriais a cada batch).

**Tabela completa dos 11 canais:**

| # | Canal | Shape | Categoria | Significado |
|---|---|---|---|---|
| 1 | `aresta_topo` | (4,3) bin | Geométrico (atual) | Aresta horizontal acima da caixa está jogada (1) ou livre (0) |
| 2 | `aresta_base` | (4,3) bin | Geométrico (atual) | Aresta horizontal abaixo da caixa está jogada |
| 3 | `aresta_esquerda` | (4,3) bin | Geométrico (atual) | Aresta vertical à esquerda da caixa está jogada |
| 4 | `aresta_direita` | (4,3) bin | Geométrico (atual) | Aresta vertical à direita da caixa está jogada |
| 5 | `caixa_fechada` | (4,3) bin | Geométrico (atual) | Interior da caixa: `1` = caixa fechada (qualquer jogador), `0` = aberta. **Binário porque o dataset nunca contém -1** (vide `contexto_1_geracao_dataset` no contrato). É o canal que registra "caixa fechada". Equivale ao 5º slot extraído pela `Lambda para_grid_de_caixas` do V5 — o V5 também recebe binário em runtime, embora o comentário no código diga "dono da caixa" (enganoso). |
| 6 | `eh_grau3` | (4,3) bin | Estrutural (novo) | Caixa não-fechada com 3 lados ocupados (captura imediata possível). Caixas fechadas recebem 0. |
| 7 | `eh_grau2` | (4,3) bin | Estrutural (novo) | Caixa não-fechada com 2 lados ocupados (membro candidato a cadeia/ciclo). |
| 8 | `em_cadeia_curta` | (4,3) bin | Estrutural (novo) | Caixa pertence a cadeia de comprimento 1–2. **Se houver várias cadeias curtas no mesmo estado, todas as caixas de todas elas são marcadas com 1 no mesmo canal** — não há canais separados por instância. |
| 9 | `em_cadeia_longa` | (4,3) bin | Estrutural (novo) | Caixa pertence a cadeia de comprimento ≥3. **Idem para múltiplas cadeias longas no mesmo estado** — todas marcadas com 1, sem canal por instância. A CNN aprende a contar/separar cadeias pelo padrão espacial. |
| 10 | `em_loop` | (4,3) bin | Estrutural (novo) | Caixa pertence a um ciclo fechado de comprimento par. Múltiplos loops são unidos no mesmo canal. |
| 11 | `em_cadeia_aberta_uma_ponta` | (4,3) bin | Estrutural (novo) | Caixa em cadeia "half-open" (Barker & Korf 2012, Fig. 2-A) — uma ponta capturável (conecta a uma caixa grau-3). |

**Importante — caixas fechadas:** o canal 5 (`caixa_fechada`) **é o registro autoritativo de caixa fechada**, exatamente como o V5 já entrega via `Lambda para_grid_de_caixas` (que extrai `interior = M[1:8:2, 1:7:2]` de uma matriz que, no contexto 1 do contrato, só tem valores `{0, 1, 8, 9}` — após normalização `8→0`/`9→1` o slot fica binário `{0, 1}`). Os canais estruturais 6–11 **excluem** caixas fechadas (recebem 0 lá), porque conceitos como "grau", "cadeia", "loop" só fazem sentido em caixas abertas. Quem quiser saber se uma caixa está fechada lê o canal 5.

**Correspondência canal → nome no NPZ (decisão de 2026-05-07, opção "Ambos"):** o NPZ enriquecido carrega um array adicional `nomes_canais` shape `(11,) U32` com os nomes dos canais na ordem canônica abaixo. Isso torna o NPZ auto-descritivo (qualquer ferramenta consegue interpretar sem consultar este PRD) **e** mantém a PRD §4.2 como fonte declarativa para gerar o tensor. O teste de contrato (`tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py`) compara `nomes_canais` do NPZ com a constante derivada desta tabela — divergência **falha o merge**.

```python
NOMES_CANAIS = (
    "aresta_topo", "aresta_base", "aresta_esquerda", "aresta_direita",
    "caixa_fechada",
    "eh_grau3", "eh_grau2",
    "em_cadeia_curta", "em_cadeia_longa", "em_loop",
    "em_cadeia_aberta_uma_ponta",
)
```

**Por quê um único canal binário por classe estrutural (e não um canal por cadeia):** revisão em 2026-05-07 confirmou que estados com 2+ cadeias longas no mesmo tabuleiro acontecem e a CNN precisa lidar com eles. Optamos pelo design mais simples — um canal binário por classe — porque:
1. Mantém K=11 fixo (compatível com Concatenate sem padding dinâmico).
2. Mantém simetrias 4× triviais (canais binários permutam idênticos sob reflexão).
3. A CNN convolucional já é capaz de separar duas cadeias espacialmente disjuntas a partir do padrão binário — não precisa de IDs explícitos.

**Por quê esses canais e não outros:**

A escolha é fundamentada em três trabalhos:

1. **Berlekamp et al. (Winning Ways) e Buchin et al. (2021)** estabelecem que a vitória em loony endgames depende de **maximizar o número de ciclos disjuntos** que o jogador "fora de controle" pode reservar. A diferenciação cadeia × ciclo é, portanto, a feature estratégica de mais alto nível no jogo.
2. **Barker & Korf (AAAI 2012)** identificam *chains* como **a feature de poda mais eficaz** em solvers Alpha-Beta — eliminando ramos onde a jogada ótima é forçada. Chains half-open vs closed têm estratégias ótimas diferentes (sacrificar 2 vs sacrificar 4).
3. **Li et al. (ACAIT 2019)** reportam ganho mensurável em CNN ao usar canais binários explícitos `score grid` (caixa grau-3) e `change hands grid` (oportunidade de hand-change). Nosso `eh_grau3` é o equivalente direto do `score grid`.

**Por que pré-computar no NPZ em vez de derivar na CNN:**

- **Validação visual mais fácil.** O usuário pediu explicitamente poder gerar PNGs por canal e conferir se o cálculo está correto antes de treinar.
- **Custo CPU mínimo.** Cada canal é uma BFS ou contagem trivial em 12 caixas — tempo desprezível na geração.
- **Pipeline de treino mais simples.** O notebook V6 lê `canais` direto do NPZ; **a `Lambda para_grid_de_caixas` deixa de existir no modelo de treino** (eliminação confirmada em 2026-05-07). Os 5 canais geométricos passam a vir prontos no NPZ junto com os 6 estruturais.
- **Permite Fase B (treinar só com os 5 canais geométricos isolando-os de `canais[..., :5]`)** vs. **Fase D (treinar com todos os 11 canais via `canais[..., :11]`)** sem regenerar dados.
- **Inferência mobile:** o app Flutter pré-computa os 11 canais on-device (custo desprezível — BFS em 12 nós) antes de chamar o TFLite. O contrato de codificação será ampliado na Fase D para registrar a regra dos canais estruturais; os 5 geométricos já estão implícitos hoje (apenas mudam de "derivados em runtime pela Lambda" para "derivados em runtime pelo cliente Dart").

**Lógica de identificação (especificação algorítmica):**

Para cada caixa `(r, c)` do grid 4×3 com posição na matriz expandida `(2r+1, 2c+1)`:

- **`grau(caixa)`** = soma binária dos 4 traços vizinhos (top, bottom, left, right). Se a caixa já está fechada (`mat[2r+1, 2c+1] == 1` ou `-1`), grau = 4 e a caixa é **excluída** dos 6 canais.
- **`eh_grau3`** = (grau == 3 && caixa não fechada).
- **`eh_grau2`** = (grau == 2 && caixa não fechada).
- **Cadeias e ciclos** são componentes conexos no **grafo dual** onde nós são caixas grau-2 e arestas conectam duas caixas grau-2 que compartilham uma aresta livre. Algoritmo:
  - BFS em cada componente de caixas grau-2.
  - Se o componente forma um caminho aberto → **cadeia**, comprimento = |componente|.
  - Se o componente forma um ciclo (toda caixa do componente tem 2 vizinhos grau-2 dentro do componente) → **loop**.
  - Cadeia "half-open" = cadeia onde uma das pontas conecta a uma caixa grau-3 (inicia captura imediata).
  - Cadeia "closed" = cadeia onde ambas as pontas conectam a caixas grau-3.
  - Comprimento ≥3 → **longa** (Buchin et al. — base para double-cross). Comprimento 1–2 → **curta** (sem oportunidade de double-cross em chain pura, embora chain de 2 + extremidade = 4 às vezes possa).

**Onde implementar:** novo módulo `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` (estende e generaliza o que já existe em `tmp_analise/analisa_grau3_minimax.py`).

### 4.3 Decisão D3 — Pipeline em dois notebooks (geração no Databricks + enriquecimento local)

**Decisão (revisada em 2026-05-07):** A geração de estados e o cálculo dos canais ficam em **notebooks separados**, executados em ambientes diferentes:

| Notebook | Onde roda | Responsabilidade |
|---|---|---|
| `Otimizacao_Topologia_Rede_V5.ipynb` | Databricks (cluster Spark) | Gera estados (matriz crua `(9,7) int8`) com Minimax(p=9) como supervisor, aplicando a distribuição U-invertida de traços (D1) e o mix de sampling (D1.a). Deduplicação obrigatória (D1.b). NPZ contém **apenas** matriz crua + scores + rótulo + generation_mode + depth. |
| `Enriquece_NPZ_Com_Canais.ipynb` (novo) | Máquina local do usuário | Lê NPZs gerados pelo notebook anterior, computa os 11 canais (`(N, 4, 3, 11)`), e **regrava** os mesmos NPZs adicionando o campo `canais`. **Sobrescrita sempre:** se o NPZ já tem `canais`, recalcula e substitui (idempotência por sobrescrita). |

**Por quê separar:**

1. **Reaproveitamento de dados existentes:** já temos 314.323 estados únicos em `dados/profundidade_minmax_9` que custaram horas de Databricks. Separando geração e enriquecimento, podemos rodar o enriquecedor sobre esses dados antigos sem regerá-los.
2. **Foco do notebook do Databricks:** mantém o V5 enxuto (gera estados, computa Q-values) e otimizado para PySpark/cluster. Não obriga o notebook do cluster a importar as bibliotecas de análise estrutural.
3. **Iteração local mais barata:** se a lógica de algum canal estrutural mudar (ex.: redefinir "cadeia longa"), basta rerodar o enriquecedor localmente — não consome tempo de Databricks.
4. **Sobrescrita garante consistência:** se o usuário rodar o enriquecedor duas vezes (com o analisador atualizado entre as execuções), a segunda execução substitui canais antigos pelos recalculados. **Não há merge nem skip por padrão.** Comportamento:
   ```
   Para cada NPZ no diretório de entrada:
     - Carregar TODOS os campos atuais (estados, scores, rotulos, gen_mode, depth, labels_canonicos, [canais se existir]).
     - Computar canais novos (N, 4, 3, 11) sobre `estados`.
     - Regravar o mesmo arquivo com TODOS os campos + `canais` (substituindo o antigo se houver).
   ```
5. **Atomicidade:** a regravação usa arquivo temporário (`.tmp`) + `os.replace()` para evitar corrupção em caso de Ctrl+C no meio.

**Trade-off aceito:** I/O duplo (ler+gravar 500k registros). Em SSD local, 500k matrizes `(9,7) int8` + scores + canais ≈ 5 GB total — leitura+gravação em ~2-3 minutos. Custo desprezível comparado ao tempo de Databricks economizado.

**Diretório recomendado:** o enriquecedor sobrescreve in-place os NPZs de entrada por padrão. Pode aceitar parâmetro opcional `--saida-dir` para gravar em pasta diferente caso o usuário queira manter a versão crua intacta.

### 4.4 Decisão D4 — Validação visual de TODOS os 11 canais antes do treino

**Decisão (revisada em 2026-05-07):** Antes de aceitar o NPZ enriquecido como válido, gerar **um PNG por estado selecionado**, contendo a representação dos **11 canais** (5 geométricos + 6 estruturais) ao lado da matriz crua em duas versões.

**Parâmetros do script (`scripts/pontinhos/validar_canais_visualmente.py`):**

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `--diretorio-npz` | str | `dados/profundidade_minmax_9` | Pasta com NPZs enriquecidos a amostrar. |
| `--qtd-tracos` | list[int] | None (todos) | Filtro por nº de traços preenchidos. Ex.: `--qtd-tracos 14 17 29` mostra apenas estados com 14, 17 ou 29 traços. |
| `--generation-mode` | list[int] | None (todos) | Filtro por modo de geração. Ex.: `--generation-mode 2 3` ignora amostras `uniform` e `sim_l1`. |
| `--n-amostras` | int | 30 | Quantos estados sortear que satisfaçam os filtros. |
| `--saida` | str | `tmp_analise/validacao_canais_estruturais/` | Pasta de saída. Cria se não existir. |
| `--seed` | int | 42 | Seed para reprodutibilidade do sorteio. |

**Layout do PNG por estado (1 PNG = 1 estado):**

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Estado #N — gen_mode=X — n_tracos=Y — rotulo_canonico=H_r_c              │
├───────────────────────────────────┬──────────────────────────────────────┤
│  Matriz crua — arestas marcadas   │  Matriz crua — heatmap de scores     │
│  + aresta canônica em destaque    │  (azul = ótima, neutra, marrom=ruim) │
├───────────────────────────────────┴──────────────────────────────────────┤
│  Canais geométricos (5) — boxnets 4×3, células com valor 1 destacadas    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │aresta_top│ │aresta_bas│ │aresta_esq│ │aresta_dir│ │ caixa_fechada  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  Canais estruturais (6) — boxnets 4×3, células com valor 1 destacadas    │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ ┌──────┐ ┌─────────┐  │
│  │ eh_grau3 │ │ eh_grau2 │ │c_curta  │ │c_longa  │ │loop  │ │c_aberta │  │
│  └──────────┘ └──────────┘ └─────────┘ └─────────┘ └──────┘ └─────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Detalhes das duas visualizações da matriz crua:**

1. **Esquerda — arestas marcadas + canônica em destaque:** mesmo estilo visual usado em `tmp_analise/retratos_divergencia/` e demais utilitários. Arestas já jogadas em traço sólido cinza; arestas livres em traço pontilhado claro; **a aresta `rotulo` (jogada canônica do Minimax) destacada em cor (verde) e espessura maior**.
2. **Direita — heatmap de scores:** mesma matriz, mas as arestas livres recebem cor por interpolação do `score` correspondente no Q-vector:
   - score próximo de `score_max` → azul intenso (ótima)
   - score `0` → cor neutra (cinza claro)
   - score `score_min` (mas > -1e8) → marrom escuro (péssima)
   - score `-1e9` (jogada inválida) → invisível
   Escala de cor calibrada por estado (não global), para que o gradiente seja sempre legível.

**Detalhes das visualizações dos canais (boxnets):**

- Cada boxnet é uma grade `4×3` com bordas claras representando as 12 caixas do tabuleiro pequeno.
- **Todos os 11 canais são binários** (`{0, 1}`): caixas com valor `1` recebem fundo colorido (cor diferente por canal para legibilidade); valor `0` fundo branco.
- O canal 5 (`caixa_fechada`) segue a mesma convenção dos outros — `1` = caixa fechada, `0` = aberta. Não existe distinção visual de "dono" porque o dataset não carrega essa informação (vide §4.2).
- Título por boxnet: nome do canal exatamente como na tabela de §4.2 (e como aparecerá no array `nomes_canais` do NPZ).

**Por quê:**

- Os canais são features estratégicas críticas. Um bug no analisador (ex.: marcar caixa fechada como grau-3, ou perder uma cadeia que dá volta no canto) **envenenaria todo o treino**.
- Validação visual em estados sorteados por filtros (especialmente `--qtd-tracos 29` e `--qtd-tracos 14`, faixas críticas de §2.4.5) é a maneira mais rápida e segura de detectar bugs.
- Os filtros por traços e gen_mode permitem revisão dirigida — verificar exatamente os estados que mais importam para o diagnóstico (final tático em t=29; meio estratégico em t=12–17).
- Está incorporada como **gate obrigatório** entre Fase A e Fase B (gate de saída da Fase A.2 — enriquecimento).

### 4.5 Decisão D5 — Augmentação de simetria 4× no carregamento, não na geração

**Decisão:** Augmentação por simetrias do tabuleiro retangular acontece **no notebook de treino**, ao carregar o NPZ, e expande o dataset em memória de 500k → 2M. Não é gravada em disco.

**Simetrias aplicadas (4 — não 8, porque tabuleiro 4×3 não é quadrado):**

| # | Transformação | Equivalente matricial |
|---|---|---|
| 1 | Identidade | `mat[r, c]` |
| 2 | Reflexão horizontal | `mat[r, n_cols-1-c]` |
| 3 | Reflexão vertical | `mat[n_rows-1-r, c]` |
| 4 | Rotação 180° | `mat[n_rows-1-r, n_cols-1-c]` |

**Importante:** a augmentação **deve ser aplicada a TODOS os tensores associados a cada amostra**, com permutação coerente de labels:

- Matriz crua `(9, 7)` ✓
- Vetor de scores `(31,)` ✓ — cada label é remapeado pela mesma simetria
- Label canônico (rótulo de melhor aresta) ✓ — remapeado via tabela de permutação
- **Todos os 11 canais estruturais `(4, 3)`** ✓ — remapeados pela simetria correspondente

**Por quê 4 e não 8:**

O usuário corretamente apontou que o tabuleiro 4×3 não é quadrado. Rotação 90° produziria um tabuleiro 3×4 com conjunto de labels canônicos diferente. As 4 simetrias listadas são as únicas que preservam a forma. Isto está alinhado com Barker & Korf (2012, seção "Symmetries"): "All Dots-And-Boxes instances have horizontal and vertical symmetry, and square boards have diagonal symmetry."

**Por que isso ajuda contra o viés L/R observado:**

A reflexão não elimina o conceito de "borda" — uma borda continua sendo borda. O que ela elimina é a **assimetria L/R aprendida acidentalmente** durante o treino. Hoje cada estado é visto uma única vez na orientação original; com augmentação, cada estado é visto 4 vezes em 4 orientações, **forçando a CNN a representar a função-alvo como invariante sob essas simetrias**. O top de erros de hoje (`H_2_1 → V_1_0`, 55 erros, todos no lado L) deve, após augmentação, distribuir-se igualmente entre L e R — e, mais importante, a soma absoluta deve cair (porque a rede que aprende a representação certa erra menos em ambos os lados).

**Decisão lateral D5b — D4 não se aplica:**

A reflexão diagonal e rotações de 90°, que compõem o grupo D4 completo, **não fazem parte deste plano**. Mencioná-las é incorreto em retângulo 4×3.

### 4.6 Decisão D6 — Treinos em fases separadas (5 canais → 5+6 canais)

**Decisão:** O treino acontece em duas etapas, com **avaliação independente** entre elas:

- **Fase B:** Treinar com **apenas os 5 canais geométricos** (slice `canais[..., :5]` do NPZ enriquecido), sobre o **novo dataset (500k únicos com cobertura terminal)**. Permite isolar o ganho da cobertura de dados puro. **Importante:** a partir desta fase a Lambda `para_grid_de_caixas` é eliminada do modelo Keras — os 5 canais vêm prontos do NPZ. Modelo arquiteturalmente equivalente ao V5, mas com input direto `(4, 3, 5)`.
- **Fase D (após Fase C de augmentação):** Re-treinar com **todos os 11 canais** (slice `canais[..., :11]` = tensor inteiro). Permite isolar o ganho dos canais estruturais. Input do modelo: `(4, 3, 11)`.

**Por quê esta separação:**

- **Atribuição de causa.** Se passarmos direto para 11 canais + dataset novo + augmentação, e o win-rate subir, não saberemos qual mudança causou o ganho.
- **Conservadorismo.** Se algum dos canais estruturais tiver bug semântico (ex.: `em_loop` mal-detectado), a Fase B nos dá uma "linha de base com dataset novo" para isolar o erro.
- **Custo baixo.** Cada treino do BoxNet v3 é ~30 min em Colab T4. 4 treinos extras é trivial.

### 4.7 Decisão D7 — Loss assimétrica e hard-target como contingência

**Decisão:** As otimizações de regime de treino (hard-target em ≥26 traços e loss assimétrica calibrada com termo BCE) são **adiadas para Fases G e H** (renumeradas de E e F após inserção das novas fases — ver D9 e D10), e só serão aplicadas se as fases A–F não atingirem a meta.

**Por quê:**

- Já discutimos com o usuário que o canal `eh_grau3` ataca o mesmo problema (entrega o gabarito da jogada óbvia) com **menos risco de distorção do regime de treino**.
- Loss assimétrica corre o risco de virar a CNN gulosa (sempre fechar grau-3, mesmo quando deveria sacrificar). A calibração foi discutida em detalhe (gate `I_minimax_concorda` para preservar double-cross), mas a implementação é mais cara que canais.
- **Princípio de parada antecipada:** se Fase F já bater meta, paramos. Não há valor em adicionar complexidade em uma rede já boa o suficiente.

### 4.8 Decisão D9 — Sample_weight refinado por Δ-top2, focado em t=12–17 (Nova Fase E)

**Decisão:** Inserir nova Fase E entre as atuais D e (antiga) E, atacando a Categoria B com calibração sutil de gradiente em meio-jogo.

**Especificação:**

- **Faixa-alvo:** amostras com `n_tracos_antes ∈ [12, 17]` (faixa crítica unificada — ver §2.4.5).
- **Definição de Δ-top2:** `Δ_top2[i] = scores[i, top1] − scores[i, top2]`, em **caixas líquidas** (mesma escala do score Minimax). Para amostras com várias jogadas ótimas (empate em top1), `Δ_top2 = 0`.
- **Função de peso:**
  ```
  peso[i] = 1.0                                     se n_tracos_antes[i] ∉ [12, 17]
          = clip(1 + α · Δ_top2[i],  1.0, 1.20)     caso contrário
  ```
  com α calibrado para que o **peso médio na faixa-alvo seja ≈ 1.10** (10% a mais que o peso 1.0 dos demais tabuleiros), e nenhum peso individual ultrapasse 1.20.
- **Calibração inicial sugerida:** α ≈ 0.03. Δ_top2 típico em t=12–17 ≈ 2–3 caixas → peso ≈ 1.06–1.10 nas amostras médias da faixa, capando em 1.20 para Δ_top2 ≥ 7.
- **Por que NÃO em t=29:** a Categoria A já é atacada pelas Fases A/B/C/D. Aplicar sample_weight em t=29 seria redundante e poderia inflar o gradiente em uma faixa onde a CNN já recebe sinal forte via canal `eh_grau3`.
- **Por que tão sutil (1.10 médio, não 6×):** a maioria das jogadas em t=12–17 são boas. Os 50 fatais em meio (12.2% do total) são minoria; a maior parte das amostras dessa faixa não tem decisão crítica. Multiplicador alto distorceria a loss e potencialmente prejudicaria amostras boas.

**Por quê:**

- A análise §2.4.5 mostrou pico de fatais em t=14 (28) e maior volume de moderadas em t=12 (83). t=15–17 também tem sangramento residual.
- Δ-top2 é o sinal mais limpo de "esta é uma decisão importante": se as duas melhores jogadas têm scores próximos, a decisão é tolerável; se a top1 distancia da top2, a CNN precisa acertar.
- Custo de implementação trivial: cálculo direto dos `scores` já presentes no NPZ; adiciona apenas uma chamada `model.fit(sample_weight=...)`.

**Trade-offs avaliados:**
- **Cap em 6× (proposta inicial):** rejeitado pelo usuário — distorce a loss em demasia em uma faixa cujas amostras são majoritariamente boas. Confirmado em §2.4 que pico de fatais em meio é apenas 28 amostras (de ~3000 amostras nessa faixa).
- **Sample_weight global (toda faixa de t):** rejeitado por pulverizar o sinal — perde-se a especificidade de "atacar paridade de meio-jogo".
- **α adaptativo durante treino (curriculum):** descartado nesta fase. Pode ser reavaliado se Fase F (value head) também não bater meta.

### 4.9 Decisão D10 — Value head AlphaZero-style (Nova Fase F)

**Decisão:** Inserir nova Fase F entre a nova E (sample_weight refinado) e a (antiga) E renumerada G (Hard-target). Adicionar uma segunda saída ao modelo Keras dedicada a regredir o valor da posição (Q* do oráculo p=9), em estilo policy + value como em AlphaZero.

**Especificação arquitetural (sem Lambda — input direto do NPZ):**

```
Input canais (4, 3, 11) — vem pronto do NPZ enriquecido (Fase A.2)
                              │
                              ↓
                 Stem Conv 3×3 (32)
                              │
                              ↓
                  2 blocos residuais SeparableConv (32→48)
                              │
              ┌───────────────┴───────────────┐
              ↓ Policy head                   ↓ Value head (NOVA)
        GAP+Flatten+Dense(96)             Conv 1×1 (16) → Flatten
              │                               │
              ↓                               ↓
        Dense(31, softmax)              Dense(64, relu)
              │                               ↓
              ↓                         Dense(1, tanh)
        policy_pred (31)                value_pred (1)
```

**Alvos:**
- **Policy target (existente):** softmax(scores / T) com T=1.0 — soft-target já usado.
- **Value target (novo):** `score_max(scores_mm) / 6.0`, clipado em `[-1, +1]`. 6 = max caixas líquidas em 4×3 (12 caixas total / 2 jogadores). Valor `> 0` = posição vencedora para o jogador a mover; `< 0` = perdedora; `0` = empate.

**Loss conjunta:**
```
loss_total = KLD(policy_pred, policy_target) + λ · MSE(value_pred, value_target)
```
com **λ ∈ [0.1, 0.3]** — pequeno o suficiente para que a value head atue como regularizador estrutural sem dominar a policy.

**Inferência em produção:**
- **Treino:** modelo Keras completo com as duas saídas.
- **Export TFLite:** descartar a value head no momento do export. Apenas a policy head vai para o app Flutter.
- **Resultado:** zero impacto no contrato de codificação (`contrato_codificacao_pontinhos.json` inalterado), zero impacto no cliente Flutter, zero overhead na inferência mobile.

**Por que value head ajuda em pontinhos 4×3:**

- O jogo é dominado por **decisões de paridade**: quem entra primeiro no loony endgame perde controle da cadeia. A política sozinha precisa aprender essa estrutura implicitamente; uma value head explicita o sinal.
- O Q* do Minimax(p=9) já é informação rica no NPZ — extrair `value_target` é gratuito.
- AlphaZero comprovou empiricamente que **multi-task value+policy learning supera policy-only** em jogos com horizontes longos onde a recompensa final só aparece no fim. Pontinhos 4×3 tem essa estrutura (recompensa = caixas no fim do jogo).
- Risco: value head pode "puxar" a representação para predição de valor à custa da policy. Mitigado por λ pequeno e gate de não-regressão por faixa (Seção 2.5).

**Custo estimado:**
- **Tempo de treino:** +10–20% (mais um head + mais uma loss + targets adicionais).
- **Pipeline de dataset:** zero mudança — `value_target` é derivado dos `scores` já existentes no NPZ.
- **Memória:** +6 KB no modelo Keras (treino). 0 KB no TFLite (descartado no export).

**Trade-offs avaliados:**
- **λ alto (≥ 0.5):** rejeitado de saída — distorce a loss da policy. AlphaZero usa λ=1.0 com value head muito mais informativa (rede gigante, treinada via self-play em milhões de jogos). Em destilação supervisionada com 500k amostras, λ pequeno é o ponto seguro.
- **Manter value head no TFLite final:** rejeitado para preservar o contrato e o tamanho do modelo móvel inalterados. Inferência fica policy-only.
- **Curriculum learning por t (alternativa):** descartado nesta rodada por aumentar complexidade do pipeline de carregamento. Pode ser reavaliado se Fase F não bater meta.

### 4.10 Decisão D8 — Versionamento e documentação por fase

**Decisão:**

- Cada fase produz um **modelo TFLite versionado** com nome explícito: `pontinhos_pequeno_p9_faseB.tflite`, `..._faseC.tflite`, etc. Fase A não produz TFLite (apenas dataset).
- Cada fase produz uma **entrada datada em `docs/historico_decisoes.md`** com win-rates, métricas por faixa (§2.5), e diff de configuração.
- **Contrato de codificação muda em duas ocasiões:**
  - **Fase B:** input do TFLite muda de `(9, 7, 1)` (matriz crua, era convertida pela Lambda) para `(4, 3, 5)` (5 canais geométricos prontos). Frontend precisa pré-computar os 5 canais geométricos em Dart (lógica trivial — replica `para_grid_de_caixas`). Isso **já requer atualização do contrato e do frontend na mesma PR** (regra do `CLAUDE.md`).
  - **Fase D:** input cresce de `(4, 3, 5)` para `(4, 3, 11)` (adiciona 6 canais estruturais). Frontend precisa estender o cálculo on-device para os 6 canais novos. Nova versão do contrato + nova cópia idêntica para o frontend.
- A partir da **Fase F** o contrato volta a ser preservado (value head só vive no treino — descartada no export TFLite, conforme D10).

---

## 5. Plano de execução em fases

> **Sequência completa:** Fase 0 (concluída em 2026-05-06) → A → B → C → D → **E (sample_weight refinado, NOVA — D9)** → **F (value head, NOVA — D10)** → G (Hard-target, condicional, antiga E) → H (Loss assimétrica, condicional, antiga F).

### Fase 0 — Análise complementar de divergência estratégica (CONCLUÍDA — 2026-05-06)

**Entregas (CONCLUÍDAS):**

1. ✅ Implementação do `tmp_analise/analisa_divergencia_estrategica.py` conforme Seção 2.4.
2. ✅ Geração do `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md` em 600 partidas (200 × 3 adversários p=3/5/6).
3. ✅ Decisão registrada em `docs/historico_decisoes.md` (entrada de 2026-05-06): **Cenário X3 confirmado** (16.8% de fatal precoce, estável entre adversários). Plano completo A→D mantido. Inseridas as novas Fases E (sample_weight refinado — D9) e F (value head — D10) entre antigas D e E (esta renumerada G).

**Gate de saída:** ✅ atendido. Relatório revisado pelo usuário; decisão sobre obrigatoriedade da Fase D mantida. Não foram identificados canais estruturais novos não previstos em §6 — os 6 canais existentes cobrem os padrões observados nos top pares de §2.4.6.

**Tempo real:** 2.6h execução + ½ dia análise. Estimativa original (½ dia + 1h) subestimou tempo de análise por causa do volume (600 partidas em vez de 200).

### Fase A — Geração de dataset enriquecido (dividida em 2 sub-fases)

A Fase A se divide em duas sub-fases sequenciais (A.1 = geração no Databricks, A.2 = enriquecimento local), cada uma com gate de saída próprio. **A sub-fase de planejamento de complemento foi eliminada** em revisão de 2026-05-07: o cálculo do complemento foi feito uma única vez durante a redação deste PRD (rodando ad-hoc sobre os 58 NPZs de `dados/profundidade_minmax_9/`) e a tabela resultante está fixada no §4.1.3 abaixo, servindo direto como entrada para o A.1. Não há notebook de planejamento — o cálculo não precisa ser refeito.

#### 4.1.3 Tabela de complemento (calculada empiricamente em 2026-05-07)

> Cálculo derivado dos 58 NPZs em `dados/profundidade_minmax_9/`: 344.000 estados brutos → 314.323 únicos após dedup (29.677 duplicatas, 8,63%). Aplicação das fórmulas `cota[m,b] = 500.000 × peso_gen[m] × peso_tracos[b]` (D1.a + D1) → `aproveitavel[m,b] = min(unicos[m,b], cota[m,b])` → `complemento[m,b] = cota[m,b] − aproveitavel[m,b]`.

**Resultado consolidado:**

```
Aproveitado dos 314.323 únicos existentes: 152.980 (48,7% dos únicos; 30,6% do alvo final 500k)
Descartado dos 314.323 únicos:             149.560 (modo 1: 79.264 + bucket <5: 11.783 + excedentes: 58.513)
Duplicatas filtradas dos 344k brutos:       29.677 (8,63% — fora do cálculo acima)

Total a gerar (complemento):               347.020
Soma final (aproveitado + complemento):    500.000 ✓

Distribuição alvo final (500k):
  - 5–11 traços (abertura):    peso 0.5  →  10% das amostras ( 50.000)
  - 12–17 traços (1ª metade):  peso 1.0  →  20% das amostras (100.000)
  - 18–23 traços (2ª metade):  peso 1.7  →  28% das amostras (140.000)
  - 24–28 traços (fase quente):peso 2.5  →  32% das amostras (160.000)
  - 29–30 traços (final):      peso 1.5  →  10% das amostras ( 50.000)

Mix gen_mode alvo final (500k):
  STRAT_MODES   = [0,    1,    2,    3   ]
  STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]
```

**Tabela de complemento por célula `(gen_mode × bucket de traços)` — números a transcrever para o notebook A.1:**

| gen_mode | 5–11 | 12–17 | 18–23 | 24–28 | 29–30 | Total |
|---|---:|---:|---:|---:|---:|---:|
| 0 (uniform) | 0 | 0 | 0 | 1.236 | 2.500 | 3.736 |
| 1 (sim_l1) | — | — | — | — | — | 0 (descartado) |
| 2 (sim_l2) | 0 | 0 | 10.776 | 52.321 | 20.000 | 83.097 |
| 3 (sim_l3) | 22.484 | 50.557 | 72.820 | 86.826 | 27.500 | 260.187 |
| **Total** | **22.484** | **50.557** | **83.596** | **140.383** | **50.000** | **347.020** |

**Distribuição agregada do complemento (não confundir com distribuição final dos 500k):**

- gen_mode 0 (uniform): 3.736 (1,08% do complemento) ← chega aos 5% finais somente após contabilizar os 21.264 estados aproveitados desse modo.
- gen_mode 2 (sim_l2): 83.097 (23,95% do complemento) ← chega aos 40% finais após somar os 116.903 aproveitados.
- gen_mode 3 (sim_l3): 260.187 (74,98% do complemento) ← peso alto porque o dataset antigo praticamente não tinha sim_l3 (apenas 14.813 únicos = 4,9%).

**Estimativa de tempo de geração (original):**

- Cluster Databricks padrão (12 workers, ~72 amostras/s com Minimax(p=9) em V4 otimizado): **347.020 / 72 ≈ 4.820 s ≈ 1,34 h**.
- Cluster maior (24 workers, ~144 amostras/s): **~0,67 h**.

---

> **Revisão 2026-05-08 rev.3 — Saturação dos buckets (29–30) e (24–28); redistribuição final:**
>
> **Bucket (29–30):** apenas C(31,29)+C(31,30) = 465+31 = **496 estados únicos possíveis**.
> Todos os 496 coletados — espaço 100% esgotado.
>
> **Bucket (24–28):** C(31,24..28) = 991.333 teórico, mas o autoplay Minimax p=2/p=3
> (sim_l2/sim_l3) converge para ~**57.020 posições práticas**. Mode_0 contribuiu ~9.170
> adicionais. Total coletado: **65.792 únicos** — espaço prático esgotado.
>
> **Bucket (12–17) concluído:** 166.099 coletados, acima do novo alvo de 157.588.
>
> **Redistribuição final (total = 500.000):**
>
> | Bucket | Amostras | % | Limite físico/prático |
> |---|---:|---:|---|
> | 5–11 | 55.501 | 11,10% | — |
> | 12–17 | 157.588 | 31,52% | — |
> | 18–23 | 220.623 | 44,12% | — |
> | 24–28 | **65.792** | **13,16%** | C(31,24..28)=991.333 teórico; ~57.020 prático (autoplay) |
> | **29–30** | **496** | **0,10%** | C(31,29)+C(31,30) = 465+31 = **496** |
>
> **COMPLEMENTO_POR_CELULA final (V5_Local rev.3)** — gera 12.542 estados em (18,23):
>
> ```python
> COMPLEMENTO_POR_CELULA = {
>     0: {(5, 11): 0, (12, 17): 0, (18, 23):   627, (24, 28): 0, (29, 30): 0},
>     2: {(5, 11): 0, (12, 17): 0, (18, 23): 5_017, (24, 28): 0, (29, 30): 0},
>     3: {(5, 11): 0, (12, 17): 0, (18, 23): 6_898, (24, 28): 0, (29, 30): 0},
> }
> # Total: 12_542
> ```
>
> Shortfall esperado no consolidado: até **~6.000 estados** (295 de (29–30) por mode
> distribution + até ~5.500 de (24–28) por saturação do autoplay). Desvio < 1,2%.
>
> Ver `docs/historico_decisoes.md` (entrada 2026-05-08) para diagnóstico completo.

> **Revisão 2026-05-08 rev.5 — Consolidação final concluída (499.997 estados):**
>
> A rev.3 subestimava a saturação do autoplay mode_2 (sim_l2) nos buckets (12–17)
> e (18–23). Após contagem exata dos únicos disponíveis em todas as fontes
> (legado + v5_databricks + v5_local), **todas as cotas foram capeadas nos
> valores reais** e o excedente redistribuído para mode_3 (que tinha excedente
> de únicos em (12–17) e (18–23)).
>
> **Distribuição final consolidada (rev.5, total = 499.997):**
>
> | Bucket | Amostras | % |
> |---|---:|---:|
> | 5–11 | 55.501 | 11,10% |
> | 12–17 | 169.875 | 33,98% |
> | 18–23 | 223.551 | 44,71% |
> | 24–28 | 50.867 | 10,17% |
> | 29–30 | 203 | 0,04% |
>
> **Mix gen_mode:** mode_0 = 5,00% | mode_2 = 40,06% | mode_3 = 54,94%
> (praticamente inalterado do alvo 5/40/55).
>
> **Origem dos aceitos:** legado = 168.661 | v5_databricks = 181.456 | v5_local = 149.880.
>
> **Shortfall final: 3 estados** (arredondamento — irrelevante).
> Auditoria OK. Pronto para `Enriquece_NPZ_Com_Canais.ipynb`.
>
> Ver `docs/historico_decisoes.md` (entrada 2026-05-08 rev.5).

#### Fase A.1 — Notebook de geração no Databricks (complemento dos 314k → 500k únicos)

**Entregas:**

1. Novo notebook `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb` baseado em V4, com:
   - **Foco único:** gerar matriz crua + Q-values com Minimax(p=9). **Não computa canais estruturais** (isso é responsabilidade da Fase A.2).
   - **Autonomia total:** o notebook **não lê nenhum arquivo externo de planejamento** (nada de JSON, CSV, pickle). A tabela de complemento (§4.1.3) é transcrita literal e diretamente para a célula de parâmetros do notebook.
   - **Célula única de parâmetros no topo do notebook**, com a tabela do §4.1.3 em formato literal Python:
     ```python
     # Tabela calculada em 2026-05-07 (§4.1.3 do PRD). Editar manualmente
     # se algum dia for preciso recalcular o complemento.
     # Linhas: gen_mode (0=uniform, 2=sim_l2, 3=sim_l3) — modo 1 fica fora.
     # Colunas: bucket de traços (5–11, 12–17, 18–23, 24–28, 29–30).
     COMPLEMENTO_POR_CELULA = {
         0: {(5, 11):      0, (12, 17):      0, (18, 23):      0, (24, 28):  1_236, (29, 30):  2_500},
         2: {(5, 11):      0, (12, 17):      0, (18, 23): 10_776, (24, 28): 52_321, (29, 30): 20_000},
         3: {(5, 11): 22_484, (12, 17): 50_557, (18, 23): 72_820, (24, 28): 86_826, (29, 30): 27_500},
     }
     # Total esperado: 347_020
     ```
   - **Sorteador customizado de `target_traços`** — para cada estado a gerar, o notebook escolhe uma célula `(m, b)` com cota residual em `COMPLEMENTO_POR_CELULA` e usa o gerador correspondente (modo `m`) limitando o `target_tracos` ao bucket `b`. A distribuição U-invertida de D1 e o mix de D1.a emergem naturalmente de `COMPLEMENTO_POR_CELULA` sem precisar reescrever pesos.
   - **Faixa estendida `[0.15, 0.97]`** em vez de `[0.15, 0.85]` (cobre 5–30 traços).
   - **Deduplicação obrigatória** (D1.b): set de hashes alimentado em tempo de execução; rejeitar+regerar até 20 tentativas. **Cuidado de inicialização:** o set deve ser pré-populado com os hashes dos 314k estados antigos, carregados pelo próprio A.1 a partir dos NPZs em `dados/profundidade_minmax_9/`. Isso garante que o complemento não colida com estados já existentes.
   - **Otimizações V4 mantidas:** killer move heuristic, transposition table profundidade-aware, alpha-beta agressivo, batch sizes calibrados, dynamic worker detection via Databricks SDK.
   - **Checkpoint/resume:** mesmo esquema do V4 (NPZ em batches de 5.000, glob ordenado para retomar).
   - **NPZ contém apenas:** `estados`, `rotulos`, `scores`, `generation_mode`, `labels_canonicos`, `depth`. **Sem `canais` ainda** — Fase A.2 adiciona.
2. Atualização de `docs/jogo_pontinhos/guia_geracao_dados.md` com:
   - Novo formato de NPZ (campos atuais; `canais` documentado como "adicionado pela Fase A.2").
   - Novas proporções (D1 + D1.a).
   - Regra de deduplicação (D1.b).
   - Procedimento operacional do A.1: abrir o notebook → conferir a `COMPLEMENTO_POR_CELULA` (já preenchida com os números do §4.1.3) → executar.

**Gate de saída A.1:** geração concluída sem falhas; total de estados (antigos aproveitados + novos gerados) ≥ 500.000 únicos; distribuição empírica final dentro de ±2pp das cotas D1/D1.a; entrada datada em `docs/historico_decisoes.md` registrando a tabela `COMPLEMENTO_POR_CELULA` efetivamente usada.

**Estimativa:** 1 dia dev (V5 baseado em V4) + ~1,5 h Databricks (~347k amostras a gerar com 12 workers).

#### Fase A.2 — Notebook de enriquecimento local (adiciona os 11 canais)

**Entregas:**

1. Novo notebook `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` (roda local). Etapas:
   1. Recebe parâmetro `--diretorio-npz` (default `dados/profundidade_minmax_9`).
   2. Para cada NPZ no diretório:
      - Carrega TODOS os campos atuais.
      - Computa `canais` shape `(N, 4, 3, 11)` int8 chamando `extrair_canais(estado)` para cada estado.
      - Constrói o array `nomes_canais` shape `(11,) U32` a partir da constante canônica `NOMES_CANAIS` (ver §4.2).
      - Regrava o mesmo arquivo (via `.tmp` + `os.replace()`) com TODOS os campos + `canais` + `nomes_canais`. **Sobrescrita sempre** se já existirem.
   3. Imprime resumo: arquivos processados, tempo total, amostras/s.
2. Novo módulo `gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py` com função:
   ```python
   def extrair_canais(matriz_estado: np.ndarray) -> np.ndarray:
       """
       Recebe matriz (9, 7) int8 com codificação canônica.
       Retorna tensor (4, 3, 11) int8 contendo TODOS os 11 canais
       (5 geométricos + 6 estruturais), na ordem definida em §4.2.
       """
   ```
3. Script `scripts/pontinhos/validar_canais_visualmente.py` conforme D4 (1 PNG por estado, 11 canais + 2 visualizações da matriz crua).
4. Teste unitário `tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py` com casos canônicos:
   - Matriz vazia (5 canais geométricos zerados, 6 estruturais zerados).
   - Caixa fechada → `caixa_fechada` = 1 nessa célula, todos os 6 estruturais = 0 nessa célula.
   - Estado de double-cross do Buchin Fig. 2 → `em_cadeia_aberta_uma_ponta` correto.
   - Loop fechado de 4 caixas → `em_loop` correto.
   - 2 cadeias longas disjuntas → todas as 6+ caixas marcadas em `em_cadeia_longa`.
   - **Auto-descrição:** `nomes_canais` do NPZ regravado é byte-a-byte igual à constante `NOMES_CANAIS` declarada em `analisador_estrutural_pontinhos.py` (que por sua vez espelha §4.2 da PRD).
5. Entrada em `docs/historico_decisoes.md` documentando D1, D1.a, D1.b, D2, D3, D4.

**Gate de saída A.2:** PNGs validados manualmente pelo usuário (mínimo 30 estados sorteados nas faixas 12–17, 24–28 e 29–30); lógica de cadeia/ciclo confirmada em estados conhecidos (handout, double-cross do Buchin Fig. 2, loop simples 4 caixas, 2 cadeias longas disjuntas); testes unitários do analisador passam.

**Estimativa:** 1 dia dev (analisador + notebook + visualizador + testes) + ~10 min execução local (500k estados em SSD).

**Estimativa total da Fase A:** ~2 dias dev + ~1,5 h Databricks + ~10 min local.

### Fase B — Treino com cobertura terminal apenas (5 canais geométricos do NPZ)

**Entregas:**

1. Novo notebook `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` baseado em V5, com mudanças:
   - **Carregamento do NPZ:** lê o campo `canais` shape `(N, 4, 3, 11)` int8 (não mais `estados` cru + Lambda).
   - **Slicing para Fase B:** usa apenas `canais[..., :5]` (os 5 canais geométricos atuais). Os canais 6–11 (estruturais) são **ignorados** nesta fase.
   - **Eliminação da `Lambda para_grid_de_caixas`:** o tensor de entrada do modelo passa de `(9, 7, 1)` para `(4, 3, 5)` direto. A Lambda do V5 sai do grafo.
   - **Modelo arquiteturalmente equivalente:** stem Conv 3×3 (32) + 2 blocos residuais (32→48) + GAP+Flatten+Dense(96)+Dropout + softmax(31). Mesma capacidade do V5, apenas mudou a entrada.
   - **Stratified split por fase do jogo:** mantido conforme V5 (recomputado a partir de `canais[..., 0:4]` que ainda contêm a informação de aresta).
2. Treino sobre o NPZ Fase A.2 usando **só os 5 canais geométricos** (canais 1–5 do tensor `canais`).
3. Modelo TFLite `pontinhos_pequeno_p9_faseB.tflite`.
4. Re-execução do `Avaliacao_CNN_vs_Minimax.ipynb` (200 partidas vs cada Minimax p=3, 5, 6 — p=1 descartado em §2.4 da Fase 0).
5. Re-execução do `tmp_analise/analisa_padrao_erros.py` e do `tmp_analise/analisa_divergencia_estrategica.py`.
6. Entrada em `docs/historico_decisoes.md` com tabela comparativa Baseline vs Fase B.

**Gates de saída (todos obrigatórios):**

1. **Não-regressão:** nenhum win-rate cai > 3pp em relação ao baseline.
2. **Redução tática mínima:** total de erros reais (`analisa_padrao_erros.py`) cai pelo menos 50% (de 505 para ≤ 250).
3. **Acoplamento entre redução tática e win-rate:** se a Categoria B (medida na Fase 0) era ≤ 10% das partidas perdidas (cenário X1), a queda de erros táticos **deve** ser acompanhada de subida proporcional de win-rate vs p=3 (≥ +10pp). Se cenário X2/X3, a subida pode ser menor — mas a **divergência estratégica medida pelo `analisa_divergencia_estrategica.py` não pode aumentar**.
4. **Top-1 accuracy por faixa de preenchimento (Seção 2.5):** atingir os pisos da tabela em **todas** as faixas, com atenção crítica à faixa **29-30 traços (≥ 95%)** — é onde o erro tático elementar da Seção 1.4 ocorre e é a principal motivação para a Fase A. **Este gate falha** se a faixa 29-30 ficar abaixo de 95%, ainda que o win-rate global suba.
5. **Não-regressão por faixa:** nenhuma faixa cai > 2pp em relação ao baseline (mesma regra do gate global, agora aplicada por faixa).
6. **Diagnóstico de gap residual:** registrar em `docs/historico_decisoes.md` quanto da meta final foi atingida apenas com cobertura terminal, e quanto resta para Fases C/D — quebrar por faixa de preenchimento.

**Hipótese:** redução de 505 erros para ~150–250; subida de win-rate vs p=3 para 70–75%; faixa 29-30 saindo de baseline atual (a medir na Fase 0) para ≥ 95%. **Atenção:** se win-rate vs p=5/p=6 mal subir, é sinal forte de Categoria B dominante e Fase D torna-se obrigatória.

**Estimativa:** ½ dia dev + 1h treino + ½h avaliação.

### Fase C — Augmentação por simetria (4×)

**Entregas:**

1. Modificação no V6: bloco de augmentação executado após carregamento do NPZ, antes do split treino/val/teste. Augmentação operando diretamente sobre o tensor `canais` shape `(N, 4, 3, 5)` carregado da Fase B (slice dos 5 geométricos).
2. Tabelas de permutação de labels canônicos para cada uma das 4 simetrias (validadas em teste unitário).
3. **Permutação coerente dos 5 canais geométricos sob simetria:** sob reflexão horizontal, os canais `aresta_esquerda` e `aresta_direita` trocam de lugar; sob reflexão vertical, `aresta_topo` e `aresta_base` trocam; sob rotação 180°, ambas as trocas acontecem. Canal `caixa_fechada` é apenas espelhado/rotacionado (não troca de canal). Lógica encapsulada em `permutacoes_simetria_pontinhos.py`.
4. Treino sobre o dataset 4× (efetivo 2M) ainda com **só 5 canais geométricos**.
5. Modelo `pontinhos_pequeno_p9_faseC.tflite`.
6. Re-execução do `Avaliacao_CNN_vs_Minimax.ipynb` + `analisa_padrao_erros.py` + `analisa_divergencia_estrategica.py`.
7. Entrada em `docs/historico_decisoes.md`.

**Gates de saída (todos obrigatórios):**

1. **Redução do viés posicional:** nenhum par "deveria→jogou" individual representa > 5% do total de erros.
2. **Não-regressão:** nenhum win-rate cai em relação à Fase B.
3. **Não-regressão por faixa (Seção 2.5):** nenhuma faixa de preenchimento cai > 2pp em accuracy em relação à Fase B. A faixa **29-30 deve permanecer ≥ 95%**.
4. **Decisão sobre Fase D:** registrar em `docs/historico_decisoes.md` o win-rate atingido. Se metas finais (Seção 2.2) já foram batidas E a divergência estratégica medida pelo `analisa_divergencia_estrategica.py` é ≤ 10% das partidas perdidas, **Fase D pode ser dispensada**. Caso contrário, prosseguir para Fase D.

**Hipótese:** viés de borda externa desaparece. Erros caem ~30% adicionais. Win-rate vs p=5 sobe ~5–10pp.

**Estimativa:** ½ dia dev + 2h treino (dataset 4×) + ½h avaliação.

### Fase D — Treino com TODOS os 11 canais (5 geométricos + 6 estruturais)

**Entregas:**

1. Modificação no V6 para usar **todos os 11 canais** do tensor `canais` (slice `canais[..., :11]` = tensor inteiro). Input do modelo passa de `(4, 3, 5)` para `(4, 3, 11)`. Stem Conv recebe 11 canais em vez de 5; primeira camada cresce ~6 × 32 = 192 parâmetros adicionais (negligível).
2. **Sem mudança de Lambda — não há Lambda no V6** (eliminada na Fase B). Todos os 11 canais vêm prontos do NPZ. Cliente Flutter passa a calcular os 11 canais on-device antes de chamar o TFLite.
3. **Atualização do `contrato_codificacao_pontinhos.json`** para versão 2:
   - Documentar o novo input do TFLite: `(1, 4, 3, 11)` int8 normalizado.
   - Documentar a regra de derivação de cada um dos 11 canais a partir da matriz crua `(9, 7) int8` (algoritmos espelhados de `analisador_estrutural_pontinhos.py`).
   - Manter o output igual: 31 probabilidades softmax por aresta canônica.
   - Cópia idêntica do JSON para o frontend (regra do CLAUDE.md).
4. Atualização do teste `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` para validar a nova versão do contrato.
5. **Implementação Dart no frontend Flutter** do `analisador_estrutural_pontinhos.dart` espelhando o Python. Testes paralelos garantindo que dado um conjunto de matrizes cruas, Python e Dart produzem `canais` idênticos byte a byte.
6. Treino. Modelo `pontinhos_pequeno_p9_faseD.tflite`.
7. Re-execução completa de avaliação.
8. Entrada em `docs/historico_decisoes.md`.

**Gates de saída (todos obrigatórios):**

1. **Métrica primária estratégica:** vitórias vs p=5 ≥ 70%.
2. **Métrica secundária tática:** redução total de erros para ≤ 80.
3. **Redução de divergência estratégica:** divergências fatais por partida (medidas pelo `analisa_divergencia_estrategica.py`) caem ≥ 50% em relação ao baseline.
4. **Accuracy por faixa de preenchimento (Seção 2.5):** todas as faixas batem ou superam os pisos da tabela; faixa **29-30 ≥ 95%**; nenhuma faixa regride > 2pp em relação à Fase C.

**Hipótese:** salto maior de qualidade. Win-rate vs p=6 sobe ~15–20pp. Os canais `em_cadeia_longa`/`em_loop`/`em_cadeia_aberta_uma_ponta` atacam diretamente a Categoria B de erros.

**Estimativa:** 1–2 dias dev (incluindo frontend Flutter e teste de contrato) + 2h treino + ½h avaliação.

### Fase E — Sample_weight refinado por Δ-top2 em t=12–17 (NOVA — ver D9)

**Entregas:**

1. Modificação no V6 (célula de preparação de dados) para calcular `Δ_top2` por amostra a partir do `scores` já presente no NPZ.
2. Função de peso conforme D9: `peso[i] = clip(1 + α · Δ_top2[i], 1.0, 1.20)` apenas em amostras com `n_tracos_antes ∈ [12, 17]`; `1.0` caso contrário.
3. Calibração de α (sugestão inicial: 0.03) verificando que o **peso médio na faixa-alvo é ≈ 1.10**. Reportar histograma de pesos.
4. Treino sobre o NPZ com 11 canais (mesma config da Fase D), usando `model.fit(sample_weight=pesos)`.
5. Modelo `pontinhos_pequeno_p9_faseE.tflite`.
6. Re-execução completa: `Avaliacao_CNN_vs_Minimax.ipynb` + `analisa_padrao_erros.py` + `analisa_divergencia_estrategica.py`.
7. Entrada em `docs/historico_decisoes.md` com tabela comparativa Fase D vs E.

**Gates de saída (todos obrigatórios):**

1. **Não-regressão global:** nenhum win-rate cai > 2pp em relação à Fase D.
2. **Redução em meio-jogo:** divergências fatais em t ∈ [12, 17] (medidas pelo `analisa_divergencia_estrategica.py`) caem ≥ 25% em relação à Fase D.
3. **Não-regressão por faixa (Seção 2.5):** nenhuma faixa cai > 2pp em accuracy. Faixa 29–30 permanece ≥ 95%.
4. **Histograma de pesos validado:** peso médio na faixa-alvo entre 1.05 e 1.15; nenhum peso > 1.20; razão `peso_medio_faixa_alvo / peso_medio_outras` entre 1.05 e 1.15.

**Hipótese:** redução modesta mas mensurável de fatais em meio-jogo (de 50 para ~30); win-rate vs p=5/p=6 sobe 2–4pp adicionais.

**Estimativa:** ½ dia dev + 1h treino + ½h avaliação.

### Fase F — Value head AlphaZero-style (NOVA — ver D10)

**Entregas:**

1. Modificação no V6 (célula do modelo Keras) para adicionar segunda saída `value_pred`:
   - Branch dedicado a partir do último bloco residual: `Conv 1×1 (16) → Flatten → Dense(64, relu) → Dense(1, tanh)`.
2. Cálculo de `value_target` a partir dos `scores` no NPZ: `value_target = score_max / 6.0`, clipado em `[-1, +1]`.
3. Loss conjunta: `KLD(policy) + λ · MSE(value)` com **λ inicial 0.1** (tunável via grid search se necessário, mas dentro de [0.1, 0.3]).
4. Manter o `sample_weight` da Fase E aplicado **apenas à policy loss** (a value loss usa peso 1.0 uniforme).
5. Treino. **Export TFLite descartando a value head** (apenas policy head no modelo móvel).
6. Modelo `pontinhos_pequeno_p9_faseF.tflite` — verificar que mantém o mesmo input shape e mesma única saída softmax(31).
7. Validação automatizada: hash do contrato `contrato_codificacao_pontinhos.json` inalterado entre Fase E e Fase F.
8. Re-execução completa de avaliação.
9. Entrada em `docs/historico_decisoes.md`.

**Gates de saída (todos obrigatórios):**

1. **Não-regressão global:** nenhum win-rate cai > 2pp em relação à Fase E.
2. **Convergência da value head:** MSE final do value_pred no conjunto de validação ≤ 0.10 (em escala normalizada `[-1, +1]`).
3. **Redução de divergência estratégica:** divergências fatais por partida (medidas pelo `analisa_divergencia_estrategica.py`) caem ≥ 50% em relação ao baseline da Fase 0.
4. **Contrato preservado:** `contrato_codificacao_pontinhos.json` (backend e frontend) inalterado em relação à Fase D. Teste `test_contrato_codificacao_pontinhos.py` passa.
5. **Tamanho TFLite preservado:** modelo final ≤ 200 KB (mesmo cap das fases anteriores).
6. **Accuracy por faixa (Seção 2.5):** todas as faixas batem os pisos; faixa 29–30 ≥ 95%; nenhuma faixa regride > 2pp em relação à Fase E.

**Hipótese:** salto qualitativo na fração "Sem fatal" das partidas perdidas (hoje 99/191) e na fração "Fatal precoce" (hoje 32/191 = 16.8%). Win-rate vs p=5 sobe ≥ 5pp; vs p=6 sobe ≥ 5pp.

**Estimativa:** 1 dia dev + 1.5h treino + ½h avaliação.

### Fase G — Hard-target em ≥26 traços (CONDICIONAL — antiga Fase E)

**Aplicada apenas se Fase F não bater metas.**

Modificação no V6 célula 3 substituindo soft-target por one-hot quando `qtd_tracos_preenchidos[i] >= 26`. Sem mudança em arquitetura. Mantém value head e sample_weight refinado das fases E/F.

**Estimativa:** ½ dia.

### Fase H — Loss assimétrica calibrada (CONDICIONAL — antiga Fase F)

**Aplicada apenas se Fase G não bater metas.**

Loss customizada conforme detalhado em sessão anterior:
```
loss = KL(policy_pred, policy_target) + λ_v · MSE(value_pred, value_target)
     + λ_a · I_grau3 · I_minimax_concorda · BCE(P[idx_grau3], 1.0)
```

Iniciar λ_a = 0.1, tunar via grid search com critério de **não-regressão em win-rate vs Minimax(p=5)**. Manter λ_v calibrado da Fase F.

**Estimativa:** 1 dia + várias rodadas de tuning.

---

## 6. Especificação dos 11 canais (referência canônica)

> **Nota de versão (2026-05-07):** esta seção foi renumerada para abranger os **11 canais** (5 geométricos + 6 estruturais) e não apenas os 6 estruturais como na versão original. A ordem canônica é exatamente a da tabela de §4.2 — repetida abaixo como referência rápida — e é a mesma ordem usada pelo eixo `K` do tensor `canais` shape `(N, 4, 3, 11)` no NPZ enriquecido.

| # | Canal | Tipo | Origem |
|---|---|---|---|
| 1 | `aresta_topo` | Geométrico | Pré-computado (era Lambda no V5) |
| 2 | `aresta_base` | Geométrico | Pré-computado (era Lambda no V5) |
| 3 | `aresta_esquerda` | Geométrico | Pré-computado (era Lambda no V5) |
| 4 | `aresta_direita` | Geométrico | Pré-computado (era Lambda no V5) |
| 5 | `caixa_fechada` | Geométrico | Pré-computado (era Lambda no V5) |
| 6 | `eh_grau3` | Estrutural | Novo (Fase A.2) |
| 7 | `eh_grau2` | Estrutural | Novo (Fase A.2) |
| 8 | `em_cadeia_curta` | Estrutural | Novo (Fase A.2) |
| 9 | `em_cadeia_longa` | Estrutural | Novo (Fase A.2) |
| 10 | `em_loop` | Estrutural | Novo (Fase A.2) |
| 11 | `em_cadeia_aberta_uma_ponta` | Estrutural | Novo (Fase A.2) |

### 6.1 Sistema de coordenadas

- **Tabuleiro:** 4 linhas × 3 colunas de caixas. 12 caixas total.
- **Matriz expandida:** 9 linhas × 7 colunas (`2*r+1` × `2*c+1`).
- **Caixa `(r, c)` com `r ∈ {0,1,2,3}, c ∈ {0,1,2}`** corresponde à célula `[2r+1, 2c+1]` na matriz expandida.
- **Arestas vizinhas da caixa `(r, c)`:**
  - Top: `(2r, 2c+1)` — aresta horizontal acima da caixa
  - Bottom: `(2r+2, 2c+1)` — aresta horizontal abaixo
  - Left: `(2r+1, 2c)` — aresta vertical à esquerda
  - Right: `(2r+1, 2c+2)` — aresta vertical à direita

### 6.2 Definições formais

Dado o estado da matriz expandida `M` proveniente do dataset (`contexto_1_geracao_dataset`, domínio `{0, 1, 8, 9}` — sem -1):

```python
def grau(M, r, c):
    """Grau da caixa (r,c): nº de arestas vizinhas ocupadas (valor 9)."""
    if M[2*r+1, 2*c+1] == 1:  # caixa fechada (dataset NUNCA contém -1)
        return 4
    return sum(1 for (i,j) in arestas_da_caixa(r,c) if M[i,j] == 9)

def caixa_fechada(M, r, c):
    """Dataset NUNCA contém -1 — caixa fechada é apenas valor 1 no centro."""
    return M[2*r+1, 2*c+1] == 1
```

> **Observação para inferência em runtime (`contexto_3_partidas_ao_vivo`):** lá o domínio é `{-1, 0, 1, 8}` e a normalização canônica `-1 → 1` é aplicada antes do tensor entrar no TFLite (vide contrato). Portanto o cliente Dart/Flutter, ao computar `caixa_fechada` on-device, opera sobre uma matriz já normalizada onde `1` significa "fechada por qualquer jogador" — exatamente igual ao dataset.

### 6.3 Canais 1–4 — arestas geométricas (`aresta_topo`, `aresta_base`, `aresta_esquerda`, `aresta_direita`)

```python
def canal_aresta_topo(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        out[r, c] = 1 if M[2*r,   2*c+1] == 9 else 0
    return out

def canal_aresta_base(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        out[r, c] = 1 if M[2*r+2, 2*c+1] == 9 else 0
    return out

def canal_aresta_esquerda(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        out[r, c] = 1 if M[2*r+1, 2*c]   == 9 else 0
    return out

def canal_aresta_direita(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        out[r, c] = 1 if M[2*r+1, 2*c+2] == 9 else 0
    return out
```

Observação: estes 4 canais reproduzem exatamente o que a Lambda `para_grid_de_caixas` do V5 calculava em runtime. A diferença é que agora ficam materializados no NPZ.

### 6.4 Canal 5 — `caixa_fechada`

```python
def canal_caixa_fechada(M):
    """Interior da caixa: 1 (fechada — qualquer jogador), 0 (aberta).

    O dataset é gerado em `contexto_1_geracao_dataset` (vide
    contrato_codificacao_pontinhos.json), cujo domínio é {0, 1, 8, 9} —
    NUNCA contém -1. Logo, `M[2*r+1, 2*c+1] == 1` significa caixa fechada
    e o canal é binário puro.

    Equivale ao 5º slot extraído pela `Lambda para_grid_de_caixas` do V5
    (linha `interior = x[:, 1:8:2, 1:7:2]`). O comentário `# (B,4,3) dono
    da caixa` no código do V5 é enganoso — o slot é binário em runtime
    porque a entrada do modelo passa pela normalização 8→0/9→1 que
    preserva apenas {0, 1}.
    """
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        out[r, c] = 1 if M[2*r+1, 2*c+1] == 1 else 0
    return out
```

### 6.5 Canais 6 e 7 — `eh_grau3` e `eh_grau2`

```python
def canal_eh_grau3(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        if not caixa_fechada(M, r, c) and grau(M, r, c) == 3:
            out[r, c] = 1
    return out

def canal_eh_grau2(M):
    out = zeros((4, 3), int8)
    for r, c in produto(range(4), range(3)):
        if not caixa_fechada(M, r, c) and grau(M, r, c) == 2:
            out[r, c] = 1
    return out
```

### 6.6 Canais 8, 9, 10 — `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`

Algoritmo:

1. Construir grafo dual `G_d` cujos nós são caixas grau-2 (não-fechadas) e cujas arestas conectam pares de caixas grau-2 que compartilham uma aresta livre (não-jogada).
2. Encontrar componentes conexas via BFS.
3. Para cada componente:
   - Se algum nó tem grau ≥ 3 dentro do componente, há um "T" (raro em 4×3 mas possível) — tratar como **cadeia complexa** (assignar a `em_cadeia_longa`).
   - Se todos os nós têm grau exatamente 2 dentro do componente → **loop**. Marcar `em_loop = 1` para todas as caixas.
   - Caso contrário (estrutura caminho/path) → **cadeia**. Comprimento = |componente|.
     - Comprimento 1 ou 2 → `em_cadeia_curta`.
     - Comprimento ≥ 3 → `em_cadeia_longa`.

**Múltiplas instâncias no mesmo estado:** se houver 2+ cadeias longas (ou curtas, ou loops) disjuntas no mesmo tabuleiro, todas as caixas de todas as instâncias são marcadas com 1 no mesmo canal (binário). A CNN aprende a separá-las pelo padrão espacial — não há canais por instância (ver justificativa em §4.2).

### 6.7 Canal 11 — `em_cadeia_aberta_uma_ponta`

Para cada cadeia identificada acima (não loop), examinar as duas pontas:

- Ponta = nó da cadeia que tem grau 1 dentro do componente (apenas um vizinho grau-2 conectado por aresta livre).
- Examinar a aresta livre que sai da ponta para fora do componente:
  - Se a célula adjacente é uma **caixa grau-3** → ponta é "aberta" (capturável).
- Se exatamente **uma** ponta é aberta → marcar todos os nós da cadeia em `em_cadeia_aberta_uma_ponta` (chain "half-open" do Barker & Korf).
- Se ambas estão abertas → "closed chain" — não marcar (cai em `em_cadeia_curta` ou `_longa` conforme comprimento).

### 6.8 Permutação sob simetrias (Fase C)

Tabela de permutação de labels canônicos sob cada simetria — definida em arquivo dedicado `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py`. Validada em test unitário.

Para cada simetria S e label `L`, o mapa `S(L)` é determinado pela transformação geométrica das coordenadas `(r, c)` no nome do label (`H_r_c` ou `V_r_c`) sob S.

**Permutação dos canais geométricos sob simetria** (precisa ser aplicada ao tensor `canais` ao mesmo tempo que a transformação espacial 4×3):

| Simetria | Espacial sobre `(r, c)` | Permutação de canais |
|---|---|---|
| Identidade | `(r, c) → (r, c)` | nenhuma |
| Reflexão horizontal | `(r, c) → (r, n_cols-1-c)` | `aresta_esquerda ↔ aresta_direita` |
| Reflexão vertical | `(r, c) → (n_rows-1-r, c)` | `aresta_topo ↔ aresta_base` |
| Rotação 180° | `(r, c) → (n_rows-1-r, n_cols-1-c)` | ambas as trocas acima |

Os canais 5 (`caixa_fechada`) e 6–11 (estruturais binários) **não trocam de slot** — apenas o conteúdo espacial é refletido/rotacionado. Isso simplifica a augmentação no Fase C: uma única operação `np.flip`/`np.rot90` no tensor `(4, 3, 11)` + reordenação dos slots 0–3 conforme a tabela acima.

---

## 7. Riscos e mitigações

| Risco | Severidade | Mitigação |
|---|---|---|
| Bug no analisador estrutural envenena treino | Alta | Gate de validação visual (PNGs) na Fase A. Testes unitários em estados conhecidos. |
| Augmentação 4× em NPZ 500k estoura RAM no Colab | Média | Aplicar augmentação como gerador (não materializar em memória) ou usar `tf.data` com map. |
| Frontend Flutter não consegue replicar lógica do analisador | Média | Lógica é simples (BFS em ≤12 nós). Implementar em Dart com testes paralelos. Considerar empacotar como WebAssembly se complicar. |
| Modelo cresce demais com 11 canais e perde performance mobile | Baixa | Stem inicial passa de Conv(5→32) para Conv(11→32) — apenas +1.7k parâmetros. Negligível. |
| Win-rate vs p=1 cai (CNN ficou "muito sofisticada", erra contra jogador aleatório) | Baixa | Manutenção de 10% de amostras de abertura na D1. Gate de não-regressão a cada fase. |
| Mudança no contrato de codificação não chega em frontend (regra do CLAUDE.md) | Alta | PR única abrangendo backend + frontend. Test de contrato no CI já cobre isso. |
| Tempo de geração 500k Minimax(p=9) excede orçamento Databricks | Baixa | Atual 300k = 2h. 500k extrapolando = ~3.5h. Folga grande. |

---

## 8. Referências bibliográficas

1. **Buchin, K., Hagedoorn, M., Kostitsyna, I., van Mulken, M.** (2021). *Dots & Boxes is PSPACE-complete.* arXiv:2105.02837. — Base teórica para definição formal de cadeia, ciclo, loony endgame, double-dealing, double-cross, e a importância estratégica de maximizar ciclos disjuntos. Lemma 1 fornece a fórmula `4c + T - 2k - 4` que justifica por que `em_loop` é canal de alto valor estratégico.

2. **Barker, J. K., & Korf, R. E.** (2012). *Solving Dots-And-Boxes.* AAAI 2012. — Justifica a primazia de chains como feature de poda. Define formalmente "half-open chain" (uma ponta capturável) e "closed chain" (ambas pontas) — base do canal `em_cadeia_aberta_uma_ponta`. Documenta as 4 simetrias do tabuleiro retangular ("horizontal and vertical symmetry, and square boards have diagonal symmetry") — fundamentação direta da decisão D5 (4× e não 8×).

3. **Li, S., Zhang, Y., Ding, M., Dai, P.** (2019). *Research on integrated computer game algorithm for dots and boxes.* The Journal of Engineering, ACAIT 2019. — Demonstra empiricamente o ganho de canais binários explícitos para representação CNN em Dots and Boxes 5×5. Tabela 1 do artigo lista 17 canais; nossos 6 escolhidos são o subconjunto **estritamente estratégico** (descartando canais redundantes como "all 1", "all 0", "side area" que já estão implícitos no nosso `para_grid_de_caixas`).

4. **Berlekamp, E.** (2000). *The Dots-and-Boxes Game: Sophisticated Child's Play.* AK Peters. — Texto canônico sobre estratégia em Dots and Boxes. Fonte original das definições de "loony move", "double-dealing", "hard-hearted handout".

5. **Berlekamp, E., Conway, J., Guy, R.** (2003). *Winning Ways for Your Mathematical Plays, Vol. 3, Chapter 16.* — Capítulo 16 dedicado a Dots and Boxes; formaliza estratégia ótima em loony endgames.

6. **Relatório interno:** `tmp_analise/RELATORIO_ERROS_CNN.md` — análise dos 505 erros reais que motivam este PRD.

7. **Histórico interno:** `notebooks/jogo_pontinhos/Avaliacao_CNN_vs_Minimax.ipynb` — baseline empírica de performance.

---

## 9. Glossário (para uso por `/speckit-specify`)

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

## 10. Pendências não resolvidas (para `/speckit-clarify` ou discussão)

1. **Implementação do analisador no Flutter (Fase D):** Dart puro, FFI para C++ ou WebAssembly do código Python? Preferência inicial: Dart puro (lógica é < 200 linhas, BFS em 12 nós).
2. **Limite máximo de comprimento de cadeia para "longa":** estamos usando ≥ 3. O artigo do Buchin trata cadeias ≥ 4 com tratamento especial em loony endgame (double-dealing yields ≥ as many boxes). Avaliar se vale separar `cadeia_media (3)` de `cadeia_longa (≥4)` em canal extra.
3. **Calibração de λ na Fase F (value head, MSE) e Fase H (loss assimétrica, BCE):** grid search ou Bayesian optimization? Para Fase F, sugestão inicial λ_v = 0.1 e validação isolada antes de tuning. Para Fase H, decisão protelada até Fase H ser necessária.
4. **Versionamento do TFLite no app:** o app Flutter precisará carregar dinamicamente diferentes versões durante A/B testing? Ou fixamos a versão final pós-Fase D?

---

## 11. Critério de aceitação geral do feature

**O feature é considerado entregue (independente de quantas fases foram necessárias) quando:**

1. **Categoria A — falhas táticas:** total de erros reais (`analisa_padrao_erros.py`) é **≤ 80**, com distribuição balanceada nos pares "deveria→jogou" (nenhum par > 5% do total).
2. **Categoria B — falhas estratégicas:**
   - Divergências fatais por partida (`analisa_divergencia_estrategica.py`) caem ≥ 50% em relação ao baseline da Fase 0 (de 0.68 para ≤ 0.34).
   - Fração de partidas perdidas com fatal precoce (≤ 25 traços) cai de 16.8% para ≤ 8%.
3. **Win-rate primário:** a CNN atinge **≥ 80% de vitórias contra Minimax(p=3)** (baseline 54.5%) e **≥ 70% contra Minimax(p=5)** (baseline 42.0%) em 200 partidas.
4. **Não-regressão global:** vitórias contra Minimax(p=1) ≥ 92% (não cair abaixo do baseline anterior).
5. **Dataset enriquecido válido (Fase A):**
   - **≥ 500.000 estados únicos** (dedup por `mat.tobytes()`) no NPZ entregue à Fase B — não 500.000 estados gerados com duplicatas.
   - Distribuição empírica final dentro de **±2pp** das cotas D1 (faixa de traços) e D1.a (gen_mode).
   - **Mix gen_mode final:** 0=5%, 1=0%, 2=40%, 3=55% (proporção alvo D1.a).
   - Campo `canais` shape `(N, 4, 3, 11)` int8 presente em todos os NPZs do diretório de dados.
   - Campo `nomes_canais` shape `(11,) U32` presente em todos os NPZs e byte-a-byte igual à constante canônica `NOMES_CANAIS` declarada em `analisador_estrutural_pontinhos.py` (espelho da tabela §4.2). Teste unitário cruza os dois; divergência **falha o merge**.
   - **Snapshot da tabela `COMPLEMENTO_POR_CELULA`** efetivamente usada no A.1 registrado em `docs/historico_decisoes.md`. A tabela canônica é a do §4.1.3 do PRD (calculada uma única vez); o snapshot serve como prova de auditoria caso o código do notebook seja alterado depois.
6. **Pipeline completo** (geração + enriquecimento + treino + avaliação + export TFLite + integração Flutter) funciona end-to-end.
7. **Documentação viva** (CLAUDE.md) atualizada: `historico_decisoes.md` (com entradas das Fases 0–H), `guia_geracao_dados.md`, `contrato_codificacao_pontinhos.json` (sincronizado backend↔frontend).
8. **Testes unitários passam:** `test_contrato_codificacao_pontinhos.py`, `test_analisador_estrutural_pontinhos.py` (a ser criado), `test_permutacoes_simetria_pontinhos.py` (a ser criado).
9. **Contrato preservado a partir da Fase E:** `contrato_codificacao_pontinhos.json` da Fase F é IDÊNTICO ao da Fase D (value head só vive no treino — descartada no export TFLite).

---

**Fim do PRD.** Pronto para servir como input ao `/speckit-plan`.
