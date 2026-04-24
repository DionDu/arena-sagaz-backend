# Métricas e Conceitos do Modelo de IA — Arena Sagaz

Documento-guia único sobre **todas** as métricas que aparecem no nosso pipeline
de treino e avaliação da CNN. Vale como referência para consulta rápida e como
material de estudo para a defesa do TCC.

> **Como usar este documento.** Cada métrica tem quatro blocos:
> **O que é** (definição formal), **De onde vem** (qual arquivo/célula gera),
> **Como ler** (valor típico / limiar de alerta) e **Pegadinha específica do
> nosso domínio**. Se uma métrica não tiver "pegadinha", é porque funciona
> direto no jogo dos pontinhos como funciona em qualquer classificação.

---

## Índice

1. [Por que precisamos de métricas específicas](#1-por-que-precisamos-de-métricas-específicas)
2. [Métricas padrão do Keras (o que aparece a cada época)](#2-métricas-padrão-do-keras-o-que-aparece-a-cada-época)
   - 2.1 [Loss / KL Divergence](#21-loss--kl-divergence)
   - 2.2 [Val Loss](#22-val-loss-val_loss)
   - 2.3 [Accuracy / Top-1](#23-accuracy--top-1-accuracy-categoricalaccuracy)
   - 2.4 [Val Accuracy](#24-val-accuracy-val_accuracy)
   - 2.5 [Top-3 Accuracy / Top-5 Accuracy](#25-top-3-accuracy--top-5-accuracy)
   - 2.6 [Learning Rate](#26-learning-rate-learning_rate)
   - 2.7 [Gap Treino/Val](#27-gap-treinoval-derivada-de-14-e-22)
3. [Métricas do `classification_report` (sklearn)](#3-métricas-do-classification_report-sklearn)
   - 3.1 [Precision por classe](#31-precision-por-classe)
   - 3.2 [Recall por classe](#32-recall-por-classe)
   - 3.3 [F1-Score](#33-f1-score)
   - 3.4 [Support](#34-support)
   - 3.5 [Macro avg / Weighted avg](#35-macro-avg--weighted-avg)
4. [Métricas específicas do projeto](#4-métricas-específicas-do-projeto)
   - 4.1 [OMA — Optimal Move Accuracy](#41-oma--optimal-move-accuracy-métrica-principal)
   - 4.2 [OMA por fase do jogo](#42-oma-por-fase-do-jogo)
   - 4.3 [OMA/Top-K por generation_mode](#43-omatop-k-por-generation_mode-só-no-v3-auto-play)
   - 4.4 [Win-Rate vs Minimax](#44-win-rate-vs-minimax)
   - 4.5 [Score-Gap](#45-score-gap-proposta-ainda-não-implementada)
5. [Conceitos do pipeline](#5-conceitos-do-pipeline)
   - 5.1 [Soft targets](#51-soft-targets-q-values-do-minimax)
   - 5.2 [Temperatura T](#52-temperatura-t-nos-soft-targets)
   - 5.3 [Sample weight](#53-sample-weight-e-por-que-não-usamos-mais)
6. [Tabela-resumo](#6-tabela-resumo-o-que-olhar-antes-de-declarar-uma-rodada-pronta)
7. [Respostas prontas para a banca do TCC](#7-respostas-prontas-para-a-banca-do-tcc)

---

## 1. Por que precisamos de métricas específicas

Na sua pós-graduação, os exemplos clássicos de classificação têm **uma única
resposta correta** por amostra: gato/cachorro, spam/não-spam, maligno/benigno.

No Jogo dos Pontinhos isso NÃO vale. Em um tabuleiro com 5 traços jogados, o
Minimax pode devolver:

```
H_0_1 → score +2   ← ótimo
H_0_3 → score +2   ← ótimo (matematicamente equivalente)
H_2_1 → score +2   ← ótimo (matematicamente equivalente)
V_1_4 → score  0   ← neutro
H_4_1 → score -1   ← ruim
```

Três jogadas são **igualmente corretas**. Um modelo que escolha qualquer uma
das três está jogando perfeitamente — mas uma métrica ingênua (Top-1) vai
penalizar duas delas. Por isso temos uma camada extra de métricas
(principalmente **OMA**) e interpretamos as métricas clássicas com cuidado.

---

## 2. Métricas padrão do Keras (o que aparece a cada época)

Estas são as métricas impressas linha-a-linha durante `model.fit(...)`. Elas
vêm de `model.compile(loss=..., metrics=[...])` no Cell 5 do
`Treinamento_CNN_Arena_Sagaz_V3.ipynb`.

### 2.1 Loss / KL Divergence

**O que é.** A função-objetivo que o otimizador minimiza. No nosso treino
usamos `tf.keras.losses.KLDivergence()`, que mede a distância entre duas
distribuições de probabilidade: a que o modelo prevê (`ŷ`, softmax sobre
31 classes) e o soft-target gerado a partir dos Q-values do Minimax (`y`).

Fórmula (para uma amostra):

```
KL(y ‖ ŷ) = Σ  y_i · log(y_i / ŷ_i)
            i
```

**De onde vem.** Impresso a cada época como `loss:` no log. Também gravado em
`history.history['loss']` (um valor por época). Quando mais baixo, melhor.

**Como ler.**
- **Magnitude.** Não é comparável com Crossentropy (são famílias diferentes de
  loss). Típico do nosso treino: começa em ~0.45 e estabiliza em ~0.25 no
  treino e ~0.14 na validação.
- **Por que val_loss costuma ser MENOR que loss.** A `loss` de treino inclui a
  regularização L2 (somada ao KLD puro); a `val_loss` é KLD puro. Os dois
  valores NÃO são diretamente comparáveis em magnitude — olhe as TENDÊNCIAS
  (ambos descendo?) e o **Gap** (§2.7).
- **Tendência.** Deve descer monotonicamente com alguns soluços. Se val_loss
  começa a subir enquanto loss continua descendo, é overfitting — o
  EarlyStopping com `patience=10` já corta isso.

**Pegadinha.** Soft targets para estados com muitas jogadas equivalentes
colocam 1/k em várias classes. Isso deixa um "piso" de KL impossível de
atravessar — não espere loss → 0.

### 2.2 Val Loss (`val_loss`)

**O que é.** O mesmo KLD calculado no conjunto de **validação** (dados nunca
vistos durante o treino). É a métrica monitorada pelo `EarlyStopping` e pelo
`ReduceLROnPlateau`.

**Como ler.** Se `val_loss` plateou por `patience=10` épocas, o treino para e
restaura os pesos da melhor época (`restore_best_weights=True`). Na V3 isso
aconteceu na época 106 com `val_loss ≈ 0.145`.

### 2.3 Accuracy / Top-1 (`accuracy`, `CategoricalAccuracy`)

**O que é.** Fração de amostras onde o argmax da previsão bate com o argmax do
soft-target (que coincide com a "melhor jogada canônica" do Minimax).

```
accuracy = (argmax(ŷ) == argmax(y)) / N
```

**De onde vem.** `tf.keras.metrics.CategoricalAccuracy(name='accuracy')`.
Impresso a cada época e gravado em `history.history['accuracy']`.

**Como ler no nosso projeto.**
- **Aleatório total** (1/31): ~3%.
- **Aleatório entre as ~6.8 ótimas médias**: ~15%.
- **Baseline ingênuo** (H_0_1 sempre): ~22% (pela frequência da classe
  canônica).
- **Nosso modelo V3 auto-play**: **~42.7%** (teste) → modelo aprendeu de
  verdade, não só o desempate canônico.

**Pegadinha CRÍTICA.** Top-1 baixo **NÃO significa modelo ruim** no nosso
domínio. Se o dataset grava `H_0_1` como "certa" e o modelo escolhe `H_0_3`
(igualmente ótima), Top-1 conta isso como erro. Por isso reportamos junto com
Top-3/Top-5/OMA.

### 2.4 Val Accuracy (`val_accuracy`)

**O que é.** A mesma Top-1 calculada na validação.

**Como ler.** Na V3 auto-play: `val_accuracy ≈ 0.42` — quase idêntica à
accuracy de treino. Isso é ótimo: o modelo generaliza para posições inéditas
sem esforço.

### 2.5 Top-3 Accuracy / Top-5 Accuracy

**O que é.** "O rótulo canônico do dataset está entre as K jogadas que o modelo
mais confia?"

```
top_k_acc = (rank_canônico_dentro_das_probs_previstas ≤ K) / N
```

**De onde vem.** `tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_acc')`
e a variante `k=5`.

**Como ler.**
- **Por que Top-3 > Top-1.** Mesmo quando o modelo não escolhe exatamente a
  jogada canônica, em ~62% das posições ela está entre as 3 mais prováveis.
- **Por que Top-5 cresce pouco em relação a Top-3 (71% vs 62%).** O modelo já
  está concentrando probabilidade no grupo certo; o 4º e 5º candidato raramente
  são quem fecha o problema.

**Pegadinha específica da V3.** No dataset auto-play, Top-5 CAIU comparado ao
dataset aleatório anterior (71% vs 83%). Isso é ESPERADO e positivo — estados
auto-play têm menos jogadas equivalentes, então há menos margem para "chutar
em um vizinho ótimo". Se Top-5 estivesse ALTO no auto-play, seria sintoma de
que o modelo não aprendeu as jogadas agudas.

### 2.6 Learning Rate (`learning_rate`)

**O que é.** Tamanho do passo do otimizador (Adam) a cada atualização de
gradiente.

**De onde vem.** Inicial em `Adam(learning_rate=1e-3)`. Reduzido
automaticamente pelo callback `ReduceLROnPlateau(factor=0.5, patience=4)` —
sempre que `val_loss` para de melhorar por 4 épocas consecutivas, o LR cai
pela metade. Chão em `min_lr=1e-5`.

**Como ler.** Olhar quantas vezes o LR caiu é um bom indicador de saúde do
treino. Na V3 caiu 7 vezes (1e-3 → 5e-4 → 2.5e-4 → ... → 1e-5) antes do
EarlyStopping disparar. Se o LR cair demais sem `val_loss` melhorar, o modelo
provavelmente está saturado na capacidade atual.

### 2.7 Gap Treino/Val (derivada de §2.4 e §2.3)

**O que é.** `train_accuracy - val_accuracy` na última época.

**Como ler.**
- **< 5 pp**: saudável, modelo generalizando bem.
- **5–10 pp**: atenção, pode estar começando a decorar.
- **> 10 pp**: overfitting claro — aumentar regularização ou reduzir capacidade.
- **Negativo próximo de zero** (o que vimos na V3: -0.23 pp): o modelo está
  com capacidade no limite ou abaixo. Pode valer aumentar filtros/profundidade
  se o objetivo for arrancar mais alguns pontos.

---

## 3. Métricas do `classification_report` (sklearn)

Impressas no Cell 7 do notebook de treino. Mostram o desempenho **por classe**
(uma linha para cada um dos 31 traços possíveis).

### 3.1 Precision por classe

"Das vezes que o modelo previu `H_0_1`, quantas estavam corretas?"

```
precision(H_0_1) = previsões de H_0_1 corretas / total de previsões de H_0_1
```

### 3.2 Recall por classe

"Das vezes que a resposta certa era `H_0_1`, em quantas o modelo acertou?"

```
recall(H_0_1) = previsões de H_0_1 corretas / total de amostras com H_0_1 como gabarito
```

### 3.3 F1-Score

Média harmônica de precision e recall. Útil para identificar classes
problemáticas (F1 próximo de 0) vs dominadas (F1 próximo de 1).

### 3.4 Support

Quantas amostras do conjunto de teste tinham aquela classe como gabarito.
**Importante.** `H_0_1` tem support enorme (~13k no test set da V3) porque é
a primeira classe na ordenação canônica e ganha o argmax de todos os estados
com empate no topo. Isso distorce as médias.

### 3.5 Macro avg / Weighted avg

- **Macro avg**: média simples entre as 31 classes (cada classe pesa igual).
- **Weighted avg**: média ponderada pelo `support` (classes mais frequentes
  pesam mais).

**Pegadinha.** No nosso domínio, `weighted avg` é puxado para baixo por
`H_0_1` (recall=8.9%, f1=0.16). Isso **não** reflete qualidade real de jogo;
veja OMA (§4.1).

---

## 4. Métricas específicas do projeto

### 4.1 OMA — Optimal Move Accuracy (métrica principal)

**O que é.** "A jogada escolhida pelo modelo pertence ao conjunto de jogadas
Minimax-ótimas para aquele estado?"

```python
# Para cada estado no test set:
max_score      = S_test.max(axis=1, keepdims=True)          # melhor score
conjunto_otimo = (S_test == max_score) & (S_test > -1e8)    # máscara 0/1

pred_no_conjunto = conjunto_otimo[np.arange(N), y_pred_idx]
OMA              = pred_no_conjunto.mean()
```

**De onde vem.** Calculada no Cell 7 (versão global) e Cell 9 (versão por
`generation_mode`) do notebook de treino.

**Como ler.**
- **V3 auto-play global**: 93.2%
- **V3 auto-play random(p=0)**: 98.6%
- **V3 auto-play autoplay(p=2)**: 92.5%
- **p=6 aleatório (antes)**: 99% (mas em dataset mais fácil)

Quanto **mais agudos** os estados (auto-play mid/endgame), **mais baixa** a
OMA — porque há menos jogadas equivalentes para "acertar sem saber". **A OMA
cair de 99% para 93% quando mudamos de dataset aleatório para auto-play NÃO é
regressão** — é reflexo de um dataset genuinamente mais difícil.

**Pegadinha.** OMA de 93% por move parece altíssima, mas em uma partida com
~15 jogadas da IA, a probabilidade de AO MENOS UM erro é
`1 - 0.93^15 ≈ 66%`. Em dots-and-boxes, um único erro em parity ou em uma
chain longa decide o jogo. Por isso OMA alta sozinha **não** garante win-rate
alta — precisamos também de §4.4.

**Literatura relacionada.** O conceito existe com outros nomes:
- **Move Agreement Rate** (Leela Chess Zero, KataGo): % de posições onde a
  rede concorda com o motor de busca.
- **Oracle Accuracy / Set Accuracy** (VQA, sumarização): previsão ∈ conjunto
  de respostas válidas.
- **Policy Accuracy** (AlphaGo, Silver et al. 2016): acerto ∈ política ótima.

### 4.2 OMA por fase do jogo

**O que é.** OMA recalculada separadamente para cada faixa de traços já
jogados no estado. Nossas faixas:

| Fase | Traços jogados | Por quê |
|---|---|---|
| Abertura | 0–9 | Muitos empates, árvore gigante |
| 1ª Metade | 10–17 | Começam as escolhas táticas |
| 2ª Metade | 18–25 | Chain control, parity |
| Final | 26–31 | Fim-de-jogo forçado |

**De onde vem.** Cell 7 do notebook V3 (`tracos_jogados = (X_test != 0).sum`).

**Como ler.** Deficit de OMA no final do jogo (comparado à abertura) indica
fraqueza em chain control — a parte tática mais difícil do jogo.

**Pegadinha.** A Top-1 por fase SOBE naturalmente com o nº de traços, porque
no endgame há menos jogadas disponíveis e menos empates. Isso não é "o modelo
ficar melhor" — é o problema ficar mais fácil. OMA é a métrica que não sofre
esse viés.

### 4.3 OMA/Top-K por `generation_mode` (só no V3 auto-play)

**O que é.** Quebra das mesmas métricas (Top-1, Top-3, Top-5, OMA) separando
as amostras por **como a topologia foi gerada**:

- `random(p=0)` — tabuleiro amostrado uniformemente (traços sorteados).
- `autoplay(p=1/2/3)` — tabuleiro reached por dois agentes Minimax jogando
  entre si em profundidade 1/2/3, parando em saturação aleatória 15–85%.

**De onde vem.** Cell 9 do notebook de treino.

**Como ler.** Se a CNN for **muito** melhor em `random` que em `autoplay`,
ela não aprendeu mid-game real — só topologias irreais. É essa métrica que
precisamos **monitorar** para validar que o auto-play está pagando. Resultado
V3: `autoplay(p=2)` com OMA 92.5% e Top-1 **42.2%** (contra 37.0% de
`random`) — ou seja, a CNN aprendeu MELHOR as posições auto-play em Top-1.

### 4.4 Win-Rate vs Minimax

**O que é.** % de partidas que a CNN vence contra o Minimax em uma
profundidade fixa. Metade das partidas com CNN como primeiro jogador, metade
como segundo — remove o efeito de quem abre.

**De onde vem.** `gerador_dados/avaliador_partidas.py` e o notebook
`Avaliacao_CNN_vs_Minimax.ipynb` (executado no `.venv_tf`).

**Como ler.**
- **Expectativa realista**: >85% vs MM(p=1), 55–70% vs MM(p=3), 40–55% vs
  MM(p=5), ~45% vs MM(p=6).
- Win-rate drasticamente abaixo disso indica ou **bug de inferência**
  (como o do `-1`, corrigido em 2026-04-23) ou **dataset enviesado** para
  topologias não-realistas.

**Pegadinha.** Win-rate tem ruído de ±3 pp por 200 partidas. Diferenças
menores que isso são inconclusivas. Para comparar modelos, use pelo menos 400
partidas por profundidade.

### 4.5 Score-Gap (proposta, ainda não implementada)

**O que é.** Diferença entre o Q-value da jogada escolhida e o Q-value da
melhor jogada:

```
score_gap(estado) = max(Q) - Q[jogada_escolhida]   # 0 se escolheu ótima
mean_score_gap    = média sobre o test set
```

**Por que pode ser a melhor métrica de todas.** Mede o "custo médio" das
decisões em **unidades de caixas de diferença no placar final**. Se a CNN
tiver `score_gap = 0.05`, significa que em média perde 0.05 caixa por jogada
versus a escolha ótima do Minimax. Em um jogo de 12 caixas, isso equivale a
0.6 caixa de desvantagem total — imperceptível. Se `score_gap = 0.3`, são 3.6
caixas de desvantagem — a CNN vai perder.

**Implementação sugerida** (5 linhas no Cell 7):

```python
gap = S_test.max(axis=1) - S_test[np.arange(len(S_test)), y_pred_idx]
print(f'mean score-gap: {gap.mean():.3f} | median: {np.median(gap):.3f} | p95: {np.percentile(gap,95):.1f}')
```

---

## 5. Conceitos do pipeline

### 5.1 Soft targets (Q-values do Minimax)

Em vez de treinar com one-hot `[0,0,1,0,...]`, o dataset grava o vetor
completo de Q-values do Minimax para cada estado:

```
Q-values: [+2, +2, +2, 0, -1, -1e9, -1e9, ...]
          H_0_1 H_0_3 H_2_1 V_1_4 H_4_1 (indisp.)
```

O valor `-1e9` é a sentinela para jogadas indisponíveis (traços já
desenhados). Antes do treino, convertemos os Q-values em uma distribuição de
probabilidade via softmax mascarado:

```python
mascara   = (Q > -1e8)
exp_vals  = exp(Q / T) × mascara
soft_tgt  = exp_vals / soma(exp_vals)
```

É essa distribuição que entra na KLDivergence. **Motivação**: permitir que o
modelo aprenda a distribuir probabilidade entre jogadas equivalentes em vez
de ter que chutar uma única entre várias (evitando o "sinal ambíguo" do
argmax).

### 5.2 Temperatura T nos soft targets

Controla quão "picudos" são os soft targets:

| T | Efeito |
|---|---|
| 0.5 | Concentra probabilidade nas melhores; sub-ótimas ≈ 0% |
| **1.0** (padrão) | Equilíbrio: equivalentes dividem igualmente |
| 2.0 | Suaviza, sub-ótimas ganham alguma massa |

**Por que T não ajuda com empates exatos.** Quando Q = [+2, +2, +2], qualquer
T produz 33% para cada um. Só muda quando há gradiente de qualidade real.
**Histórico:** testamos T=0.5 e foi neutro; ficamos com T=1.0.

### 5.3 Sample weight (e por que NÃO usamos mais)

**Ideia original:** dar peso menor a estados de abertura (muitos empates,
"ambíguos") e peso maior a estados de endgame ("claros"). Testamos com peso
= 1 / nº_jogadas_equivalentes.

**Por que backfired:** o test set avalia tudo com peso igual. Como 30% das
amostras são de abertura, dar 0.15 de peso para elas tira 85% do sinal de
treino nas posições mais comuns → Top-3 de abertura caiu de ~60% para ~40%.

**Lição.** A ambiguidade de abertura não é ruído. É o jogo sendo
genuinamente multi-ótimo. Remover sample_weight e confiar nos soft targets
foi o caminho correto.

---

## 6. Tabela-resumo: o que olhar antes de declarar uma rodada "pronta"

Ordem de prioridade ao avaliar um novo modelo treinado:

| # | Métrica | Onde achar | Valor alvo | Sinal de alerta |
|---|---------|------------|------------|------------------|
| 1 | `val_loss` | log do fit, history | KLD ~0.14 | Subindo enquanto loss desce = overfit |
| 2 | **Gap Treino/Val** | impresso no Cell 7 | < 5 pp | > 10 pp = overfit / < -3 pp = underfit |
| 3 | **OMA global** | Cell 7 e Cell 9 | ≥ 90% | < 85% indica erro de pipeline |
| 4 | **OMA por `generation_mode`** | Cell 9 | autoplay ≥ 90% | autoplay << random = só aprendeu topologias irreais |
| 5 | Top-1 / Top-3 / Top-5 | Cell 7 | T1≥40%, T3≥60%, T5≥70% | Top-5 baixo = região errada |
| 6 | **Win-Rate vs MM(p=1)** | `Avaliacao_CNN_vs_Minimax` | ≥ 85% | < 70% quase sempre é bug de inferência (revisar §4.4) |
| 7 | Win-Rate vs MM(p=3/5/6) | idem | ~60 / ~45 / ~45 | Degradação rápida com profundidade |
| 8 | OMA por fase | Cell 7 | Final ≥ abertura − 5pp | Queda no endgame = chain control fraco |

**Regra de ouro:** **NUNCA** confie em um único número. Um modelo com OMA 93%
e Win-Rate vs MM(p=1) de 57% tem bug, não tem qualidade. Um modelo com Top-1
35% e OMA 99% e Win-Rate 96% é excelente.

---

## 7. Respostas prontas para a banca do TCC

**"Por que a acurácia é só 42%?"**

> "A acurácia Top-1 mede se o modelo escolhe exatamente a mesma jogada que
> gravamos como rótulo. No Jogo dos Pontinhos, o Minimax frequentemente
> considera múltiplas jogadas matematicamente equivalentes, e o rótulo é uma
> escolha arbitrária entre elas. Um modelo que aprendeu perfeitamente a
> distribuir probabilidade entre equivalentes escolherá uma diferente do
> rótulo convencional — Top-1 penaliza isso mesmo sendo estrategicamente
> perfeito. Nossa métrica principal é a Optimal Move Accuracy, que atingiu
> 93%. Esta métrica segue a tradição de AlphaGo e KataGo, onde a IA é avaliada
> pela concordância com o oráculo de busca."

**"Por que Top-5 caiu de 83% (dataset antigo) para 71% (V3)?"**

> "Os dois datasets medem coisas diferentes. O dataset anterior era amostrado
> uniformemente — muitos estados com várias jogadas equivalentes, onde estar
> no Top-5 é fácil. O dataset V3 usa auto-play entre Minimax, gerando estados
> mid/endgame com poucas jogadas ótimas. É intencional que Top-5 caia: o
> dataset é mais difícil e reflete situações realistas de jogo. A métrica
> relevante para comparar qualidade é Win-Rate em partidas completas."

**"Por que 99% de OMA mas só 57% de vitória contra Minimax(p=1)?"** *(antes
de 2026-04-23)*

> "Esse gap revelou um bug de inferência: o avaliador apresentava ao modelo
> caixas fechadas pelo adversário com valor `-1`, uma distribuição que a CNN
> nunca viu no treino (todos os exemplos do dataset usavam `1` para caixa
> fechada). Após a correção, a OMA em partidas reais convergiu com a OMA
> estática, validando a qualidade do modelo."

**"OMA é uma métrica consolidada?"**

> "O nome 'Optimal Move Accuracy' foi cunhado para este projeto, mas o
> conceito é amplamente estabelecido sob nomes diferentes: Move Agreement Rate
> (Leela Chess Zero, KataGo), Oracle Accuracy (Visual Question Answering),
> Policy Accuracy (AlphaGo). Todos verificam se a previsão do modelo pertence
> ao conjunto de respostas válidas em vez de exigir um único rótulo
> pré-escolhido. No nosso caso, o 'oráculo' é o Minimax."
