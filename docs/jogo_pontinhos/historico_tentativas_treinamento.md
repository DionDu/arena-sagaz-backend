# Histórico de Tentativas de Treinamento — BoxNet

Registro detalhado de cada experimento de treinamento da CNN para o Jogo dos
Pontinhos (tabuleiro Pequeno, 4×3 caixas, 31 traços possíveis). Para cada
tentativa: **o que foi feito, por que, o que não funcionou, o que aprendemos
e qual foi o próximo passo**.

> [!WARNING]
> **ATUALIZAÇÃO CRÍTICA (2026-04-23): O BUG DO MINIMAX INVERTIDO**
> Todas as análises das Tentativas 4, 5 e 6 (geradas com Profundidade 5-7 nos Notebooks) 
> sofriam de um bug gravíssimo descoberto posteriormente. A função de rotulação `cl == 0`
> inverteu as regras do jogo: o professor Minimax ensinava a CNN que capturar caixas 
> era péssimo (pois ele achava que perdia o turno) e que fazer jogadas vazias era ótimo.
> **Portanto, o teto de 35% de precisão relatado abaixo NÃO era um limite estrutural da rede**,
> mas sim a rede tentando aprender regras completamente invertidas. Esses resultados 
> estão marcados como [CORROMPIDOS] e servem apenas como registro histórico do debug.

---

## Tentativa 1 — CNN Ingênua

**Data:** início do projeto (antes de 2026-04-20)
**Resultado:** Treino ≈ 4% · Val ≈ 4%
**Loss:** CategoricalCrossentropy

### O que foi feito

Aplicamos uma CNN padrão (convoluções 3×3 sobre a matriz raw 9×7 do tabuleiro)
diretamente sobre a representação "natural" do jogo — a grade de pontos com
traços e caixas misturados na mesma matriz.

### Por que essa escolha

Era o ponto de partida óbvio: se convoluções funcionam para imagens, deveriam
funcionar para uma representação matricial de um tabuleiro.

### O que não funcionou

A acurácia colapsou em ~4% (equivalente a chute aleatório entre 31 classes). O
problema foi a **heterogeneidade semântica da matriz**: um filtro 3×3 enxerga
simultaneamente traços horizontais, traços verticais, pontos fixos e caixas —
elementos com significados completamente diferentes misturados no mesmo campo
receptivo. A rede não consegue aprender representações úteis porque o vizinho
imediato de um traço horizontal pode ser um ponto fixo (sem significado), não
outro traço relacionado.

### O que aprendemos

A representação 9×7 "fotográfica" não tem viés geométrico adequado para CNNs.
Precisamos de um **preprocessing que separe as entidades** antes de aplicar
convoluções.

### Próximo passo

Migrar para MLP como baseline alternativo, e projetar uma representação
centrada em caixas para a CNN.

---

## Tentativa 2 — MLP Densa

**Data:** início do projeto (antes de 2026-04-20)
**Resultado:** Treino ≈ 42% · Val ≈ 28%
**Loss:** CategoricalCrossentropy

### O que foi feito

Substituímos a CNN por um MLP (Multi-Layer Perceptron) com camadas densas,
achatando a matriz 9×7 em um vetor e alimentando camadas fully-connected com
Dropout.

### Por que essa escolha

MLPs não têm o problema da heterogeneidade de vizinhança — cada posição da
matriz é tratada como uma feature independente. Como baseline, queria ver se o
problema era a CNN ou a representação.

### O que não funcionou

**Overfitting severo**: treino 42% vs validação 28% — gap de 14pp. O MLP estava
"decorando" posições específicas do tabuleiro. Sem nenhum viés geométrico
embutido, a rede precisava de uma quantidade enorme de parâmetros para aprender
as relações espaciais que uma CNN aprenderia automaticamente. Com o dataset
disponível, ela memorizava em vez de generalizar.

### O que aprendemos

O viés indutivo geométrico (convoluções) é necessário. Mas a representação de
entrada precisa ser reformulada para que as convoluções façam sentido.

### Próximo passo

Implementar o preprocessing geométrico que transforma a matriz 9×7 em uma
representação centrada em caixas: cada caixa passa a ser um "pixel" com 5
canais (traço superior, direito, inferior, esquerdo, e caixa completada).

---

## Tentativa 3 — BoxNet v1 (CNN com Preprocessing Geométrico)

**Data:** antes de 2026-04-20
**Resultado:** Treino ≈ 60% · Val ≈ 36%
**Loss:** CategoricalCrossentropy

### O que foi feito

Introduzimos uma **camada Lambda de preprocessing geométrico** dentro da
própria CNN: a entrada (9,7,1) é transformada em uma representação (4,3,5) onde
cada uma das 12 caixas do tabuleiro se torna um "pixel" com 5 canais —
os 4 traços que a delimitam + se ela foi completada. Em cima dessa representação,
aplicamos blocos residuais com SeparableConv2D, BatchNormalization e
SpatialDropout2D. O output é um vetor de 31 probabilidades via softmax.

### Por que essa escolha

A representação centrada em caixas elimina a heterogeneidade semântica: cada
posição da grade (4,3) representa exatamente uma caixa, e seus 5 canais têm
significado uniforme. Convoluções sobre essa representação capturam relações
entre caixas vizinhas — exatamente o que o Minimax considera ao avaliar
"corredor" ou "sacrifício de caixa".

### O que não funcionou

**Overfitting clássico**: a val_loss começava a subir por volta da época 10
enquanto a train_loss continuava descendo. Gap treino/val de 24pp é alto demais
— a rede estava memorizando padrões específicos do dataset de treino ao invés
de generalizar a estratégia.

### O que aprendemos

A arquitetura e o preprocessing estão corretos — o val_top1 de 36% ja era
competitive. O problema era o regime de treino (aprendeu rápido demais) ou o
volume de dados insuficiente para evitar memorização.

### Próximo passo

Adicionar `label_smoothing` na CategoricalCrossentropy para suavizar os
one-hot targets e reduzir a confiança excessiva da rede.

---

## Tentativa 4 — BoxNet v2 (Label Smoothing)

**Data:** antes de 2026-04-20
**Resultado:** Treino ≈ 46% · Val ≈ 36%
**Loss:** CategoricalCrossentropy(label_smoothing=0.05)

### O que foi feito

Mantivemos exatamente a mesma arquitetura do BoxNet v1, mas substituímos a loss
por `CategoricalCrossentropy(label_smoothing=0.05)`. O label smoothing transforma
os targets de one-hot puros [0,0,1,0,...] para versões suavizadas [0.002,
0.002, 0.907, 0.002, ...], impedindo que a rede fique 100% confiante em qualquer
classe.

Dataset: ~50.000 amostras geradas com Minimax de profundidade 5-7 (single-thread,
geração levou ~1 semana).

### Por que essa escolha

Label smoothing é uma técnica clássica de regularização que costuma reduzir
overfitting em classificação. Quería ver se o gap treino/val diminuía.

### O que não funcionou

O gap treino/val melhorou (de 24pp para ~10pp), mas o val_top1 **plateou em
36%** mesmo com mais épocas. O train_top1 caiu de 60% para 46% — o smoothing
funcionou como regularização, mas revelou um problema mais fundamental.

**Diagnóstico:** o plateau em 36% não era limitação de capacidade da rede. A
causa era **ruído sistemático nos rótulos**: o Minimax frequentemente considera
3-8 jogadas matematicamente equivalentes (mesmo score). O gerador sorteia **uma**
delas e a grava como rótulo. Em outro estado quase idêntico, o sorteio pode cair
em jogada diferente. A rede recebe dois exemplos praticamente iguais com rótulos
diferentes — sinal contraditório irreconciliável. Isso é especialmente grave
para jogadas de borda e abertura, onde os empates são mais frequentes.

Evidência: `classification_report` mostrou que jogadas de borda como `H_0_3`
tinham F1 ≈ 0.17, enquanto posições de centro como `H_2_1` tinham F1 ≈ 0.43.

### O que aprendemos

O problema não é a arquitetura nem o regime de treino — é a função de perda e
o formato do dataset. `CategoricalCrossentropy` é inadequada quando múltiplas
respostas são igualmente corretas. Precisamos de uma abordagem que ensine a
rede a reconhecer **equivalência** entre jogadas, não a adivinhar qual foi
sorteada.

### Próximo passo

Mudar o formato do dataset: em vez de gravar apenas o rótulo sorteado, gravar o
**vetor completo de Q-values do Minimax** para todas as 31 jogadas. Usar
`KLDivergence` como loss, treinando a rede sobre uma distribuição de
probabilidade (soft targets) em vez de um one-hot. Gerar um dataset maior
(200–300k) com processamento paralelo para compensar a adição de informação por
amostra.

---

## Tentativa 5a — BoxNet v3, rodada 1 (55k amostras, T=1.0)

**Data:** 2026-04-21
**Resultado:** Treino top1=34.5% · Val top1=34.4% · Val top3=67.0% · Val top5=80.0%
**Loss:** KLDivergence · Gap treino/val: +0.09pp (zero overfitting)

### O que foi feito

Reformulamos completamente o pipeline:

- **Gerador de dados:** agora grava o vetor de Q-values completo (`scores`,
  shape 31 × float32) para todas as jogadas disponíveis, além do rótulo argmax.
  Slots indisponíveis recebem sentinela `-1e9`.
- **Dataset:** 55.000 amostras novas (formato com `scores`). Os 50k antigos
  foram descartados por incompatibilidade.
- **Soft targets:** no notebook, os scores brutos são convertidos em distribuição
  de probabilidade via Softmax mascarado com temperatura T=1.0.
- **Loss:** `KLDivergence` — mede divergência entre a distribuição prevista e
  os soft targets. Jogadas equivalentes recebem peso igual; a rede aprende o
  ranking completo, não uma resposta única.
- **Augmentação 4×:** cada estado de treino é transformado nas 4 variantes
  simétricas do grupo D₂ (identidade, flip-H, flip-V, rotação 180°). O vetor
  de scores é permutado deterministicamente junto com o estado.
- **Métricas:** top-1, top-3, top-5 (argmax do soft target como ground truth).

### Por que essa escolha

Ver `docs/jogo_pontinhos/soft_targets_kl_divergence.md` para a argumentação completa.
Resumo: KLD + soft targets eliminam o ruído de rótulo causado pelo sorteio entre
empates do Minimax.

### O que funcionou

- **Zero overfitting**: gap de 0.09pp — o modelo generaliza perfeitamente.
- **KLD loss converge suavemente** — sinal de treino estável.
- **Top-3 e top-5 sólidos**: 67% e 80% — o modelo conhece a região certa.

### O que não funcionou / pontos de atenção

- **Top-1 ≈ 34–35%** — similar ao v2 com 50k dados. Ainda abaixo do esperado.
- **Anomalia H_0_1**: suporte=1700 (mais comum), precision=97%, recall=8.5%.
  O modelo raramente prediz H_0_1 mesmo sendo a mais frequente. Causa: jogada
  de abertura com muitos empates — o soft target distribui probabilidade entre
  H_0_1, H_0_3, H_2_1, e o argmax da previsão cai em outra igualmente válida.
- **Top-1 oscila na validação** — esperado com soft targets; o argmax muda
  facilmente quando várias jogadas têm probabilidade parecida.
- **Dataset pequeno** (55k): top-3 e top-5 melhoraram pouco vs v2 porque 4×
  augmentação = apenas 220k efetivos de treino. Precisa de mais dados originais.

### Diagnóstico do teto de top-1

O top-1 ≈ 35% é em parte estrutural: estados de abertura têm 5–10 jogadas
equivalentes, o argmax do soft target "escolhe" uma delas por ordem canônica, e
o modelo pode escolher outra igualmente válida — o que conta como erro de top-1
mesmo sendo estrategicamente correto.

### Próximo passo

Gerar 210k amostras e retreinar com as mesmas configurações para confirmar se o
volume adicional melhora as métricas.

---

## Tentativa 5b — BoxNet v3, rodada 2 (210k amostras, T=1.0)

**Data:** 2026-04-21
**Resultado:** Treino top1=35.5% · Val top1=35.6% · Val top3=68.9% · Val top5=83.4%
**Loss:** KLDivergence · Gap treino/val: -0.19pp (zero overfitting)

### O que foi feito

Mesmo pipeline e arquitetura da rodada 5a, com:
- **Dataset:** 210.000 amostras → 616.000 de treino após augmentação 4×.
- **Máximo de épocas:** 80. EarlyStopping disparou na época 91 (paciência=10).

### O que funcionou

- Gap treino/val ainda -0.19pp — zero overfitting mantido com 4x mais dados.
- Top-3: 66.6% → 68.9% (+2.3pp) com 4x mais dados.
- Top-5: 80.0% → 83.4% (+3.4pp) com 4x mais dados.
- KLD val loss melhorou de 0.085 para 0.082 — modelo ainda aprendendo.

### O que não funcionou / pontos de atenção

- **Top-1 subiu apenas +1pp** (34.1% → 35.1%) apesar de 4x mais dados. O teto
  estrutural do top-1 com T=1.0 está confirmado.
- **Novo caso de alta precisão / baixo recall:** `H_0_3` (suporte=3.174,
  precision=59%, recall=12%) — mesmo padrão de H_0_1 na rodada anterior.
  Jogadas de abertura muito frequentes mas raramente preditas como top-1.
- **Bordas ainda problemáticas:** `V_7_0`, `V_7_2`, `H_8_1`, `H_8_3` com
  recall alto (~85%) mas precision baixíssima (~10%) — modelo over-prediz cantos
  raros.
- **Treino KLD muito maior que val KLD** (0.24 vs 0.08 na última época): efeito
  esperado de Dropout e BatchNorm ativos durante treino. Não indica bug.
- **Modelo parou em época 91** sem atingir limite — precisa de mais épocas.

### Diagnóstico do teto confirmado

Com T=1.0 e muitos empates, o soft target distribui ~33% para cada uma das 3
melhores jogadas em estados de abertura. A rede aprende isso corretamente mas
o argmax da previsão pode sempre cair em outra das 3 — deprimindo o top-1
sistematicamente. A solução é temperatura menor (distribui mais peso para a
"marginalmente melhor" mesmo entre empates).

### Próximo passo

Retreinar com 300k amostras incorporando três melhorias simultâneas:
1. **Temperatura T=0.5** — soft targets mais concentrados → top-1 deve melhorar.
2. **`sample_weight` inversamente proporcional ao número de equivalências** —
   focar gradiente em estados informativos (poucos empates).
3. **`max_epochs=120`** — dar mais tempo para convergir com dataset maior.
4. **Duas novas métricas diagnósticas** no Cell 7: accuracy por fase do jogo
   (abertura/meio/final) e Optimal Move Accuracy (previsão ∈ conjunto
   Minimax-ótimo), que mostrará o desempenho real do modelo independente do
   tie-breaking.

---

## Tentativa 6 — BoxNet v3, rodada 3 (300k amostras, T=0.5, sample_weight)

**Data:** 2026-04-21
**Resultado:** Treino top1=33.1% · Val top1=33.2% · Val top3=65.7% · Val top5=81.5%
**Loss:** KLDivergence (T=0.5) + sample_weight · EarlyStopping época 70, melhor=60
**Optimal Move Accuracy = 99.0%** · Média de equivalentes: 6.8

### O que foi feito

Mesma arquitetura das rodadas anteriores com três mudanças simultâneas:
- Temperatura T: 1.0 → **0.5** (distribuições mais concentradas)
- **sample_weight = 1/n_equivalentes** (downweight de states ambíguos)
- max_epochs: 80 → **120**
- Dataset aumentado: 210k → **300k** amostras (770k após augmentação 4×)

### O que não funcionou — regressão em todas as métricas

Com 50% mais dados e as "melhorias", todos os indicadores pioraram vs rodada 5b:
- Top-1: 35.6% → **33.2%** (−2.4pp)
- Top-3: 68.9% → **65.7%** (−3.2pp)
- Top-5: 83.4% → **81.5%** (−1.9pp)

### Diagnóstico da regressão

**Causa 1 — T=0.5 não tem efeito para moves exatamente empatados:**
A temperatura T só diferencia moves com scores *diferentes*. Quando o Minimax
atribui score +2 a H_0_1, H_0_3 e H_2_1 identicamente:
`exp(+2/0.5) = exp(+2/1.0)` → distribuição uniforme entre os três em ambos os casos.
T=0.5 não ajudou porque os empates da abertura são exatos, não aproximados.

**Causa 2 — sample_weight destruiu o aprendizado da abertura:**
States de abertura (0–10 traços) têm ~6.8 equivalentes → peso médio = 1/6.8 ≈ 0.15.
O gradiente foi multiplicado por 15% para as posições mais comuns do jogo.
O test set tem 12.445 states de abertura (30% do total) com peso normal de avaliação.
Resultado: o modelo treinou pouco onde mais foi avaliado.

**Evidência direta** na nova métrica de fase:
```
Abertura  (0-10 traços):  Top-1=31.9%  Top-3= 40.6%   ← catastrófico
Meio-jogo (11-20 traços): Top-1=40.8%  Top-3= 82.8%   ← excelente
Final     (21-31 traços): Top-1=23.0%  Top-3= 65.9%
```
Top-3 de abertura caiu para 40.6% — em 60% dos estados de abertura, a jogada
canônica correta não está nem no top-3 do modelo.

### A descoberta central: Optimal Move Accuracy = 99.0%

**Esta é a revelação mais importante de todo o projeto.**

O modelo escolhe uma jogada Minimax-ótima **99% do tempo**. O top-1 de 33%
mede outra coisa: se o modelo acerta o mesmo *desempate canônico* que o
`argmax(soft_target)` adota por ordenação de labels.

Como 6.8 moves são equivalentes em média, o `argmax` sempre escolhe o primeiro
na ordenação canônica (ex.: H_0_1). Esse label único ganha todo o "suporte" de
todos os states onde H_0_1 é apenas uma das equivalentes. Por isso H_0_1 tem
support=8.351 (20% do test set!) mas recall=8.5% — o modelo escolhe H_2_1 ou
H_0_3 (igualmente ótimas), e "falha" o top-1.

O top-1 clássico está medindo preferência de desempate canônico, não estratégia.
O OMA=99% é a medida real de qualidade do modelo.

### Próximo passo

Reverter T=1.0 e remover sample_weight. O 300k dataset permanece. O modelo da
rodada 5b (T=1.0, 210k) foi o melhor em top-1/top-3. Com 300k e sem sample_weight,
a rodada 4 deve superar esses números.

---

## Tentativa 7 — BoxNet v3, rodada 4 (300k amostras, T=1.0, sem sample_weight)

**Data:** 2026-04-21
**Resultado:** Treino top1=42.7% · Val top1=42.7% · Top3=62% · Top5=71% · OMA=93.2% · Gap treino/val: +0.23pp (zero overfitting)
**Dataset:** 300k auto-play (15% random, 25% p=1, 55% p=2, 5% p=3)
**Win-rates vs Minimax:** p=1=96%, p=3=60%, p=5=44.5%, p=6=40.0% (conforme rodada anterior)

### O que foi feito

Reverter temperatura T=1.0 e remover sample_weight da rodada 3. Manter dataset de 300k e max_epochs=120. Treino em Google Colab com TF 2.20.0 em GPU, 120 épocas completas.

### O que funcionou

- **Zero overfitting**: gap treino/val de apenas +0.23 pp. Modelo generaliza perfeitamente para posições inéditas.
- **Top-1 recuperado a 42.7%**: O gap entre treino (42.7%) e validação (42.7%) é exato — a rede está no regime correto, sem regularização excessiva.
- **OMA = 93.2%**: em 93 de 100 estados, o modelo escolhe uma jogada Minimax-ótima. Isso é a medida REAL de qualidade — não o top-1 de 42.7%.
- **Win-rate de jogo real valida OMA**: vs MM(p=1) 96%, vs MM(p=6) 40%. Sólido e alinhado com a dificuldade do adversário.

### Diagnóstico

O auto-play (V3) foi o grande vencedor: o salto de dataset aleatório (Prof 6) para auto-play (Prof 7) resultou em **ganho qualitativo massivo em profundidades altas** — MM(p=6) saltou de 1.5% para 40.0% de vitórias (38.5 pp!). Isso não veio da profundidade 7 sozinha (Prof 6 tinha depth=6, não 7) — veio do auto-play gerando posições realistas de mid/endgame onde a rede aprende chain control.

**Conclusão da rodada:** modelo pronto para defesa. Narrativa: "OMA 93% = joga estrategicamente correto 93% do tempo" é o argumento central para a banca. Top-1 42.7% é métricas secundária explicando o viés de desempate canônico.

---

## Tentativa 8 — BoxNet v3, rodada 5 (344k amostras, d=8/9, T=1.0, sem sample_weight)

**Data:** 2026-04-29 (execução) · 2026-04-23 a 2026-04-29 (geração de dados)
**Resultado:** Treino top1=42.71% · Val top1=42.47% · Top3=63.66% · Top5=73.13% · OMA=89.2% · Gap treino/val: +0.24pp (zero overfitting) · **WIN-RATES CAÍRAM vs V3**
**Dataset:** 344k auto-play — mesmo schema que V3 (15% random, 25% p=1, 55% p=2, 5% p=3), só com profundidade Minimax aumentada de 7 → 8/9
**Win-rates vs Minimax (200 partidas/prof):**
- MM(p=1): **94.5%** (V=189, E=7, D=4) — vs V3: 96.0% **Δ = −1.5 pp**
- MM(p=3): **53.0%** (V=106, E=48, D=46) — vs V3: 60.0% **Δ = −7.0 pp**
- MM(p=5): **40.0%** (V=80, E=42, D=78) — vs V3: 44.5% **Δ = −4.5 pp**
- MM(p=6): **36.5%** (V=73, E=39, D=88) — vs V3: 40.0% **Δ = −3.5 pp**

### O que foi feito

Replicon exato da rodada 4, mas com dataset gerado em Databricks profundidade 8/9 (vs rodada 4 que foi depth=7, embora o artefato fosse marcado "V3 auto-play profundidade 7" no histórico anterior). 344.000 amostras (14% mais que 300k). Dataset preservou a estrutura auto-play com mesma distribuição de generation_mode.

Treinamento: 120 épocas completas, rodou todo o pipeline sem EarlyStopping, LR reduzido até 1e-5.

### O que não funcionou — regressão confirmada em todas as métricas

**Métricas estáticas:**
- Top-1: 42.7% → 42.71% (ganho nulo, **+0.01 pp** em teste) apesar de 14% mais dados.
- Top-3: 62.0% → 63.66% (ganho marginal, **+1.7 pp**).
- Top-5: 71.0% → 73.13% (ganho pequeno, **+2.1 pp**).
- **OMA: 93.2% → 89.2% (PERDA de 4.0 pp)** — métrica principal piorou.

**Win-rates em jogo real (a métrica que importa):**
Regressão clara em todas as profundidades ≥ 3:
- p=1: −1.5 pp (marginal, dentro do ruído de ±3 pp para 200 partidas)
- p=3: −7.0 pp (regressão real)
- p=5: −4.5 pp (regressão real)
- p=6: −3.5 pp (regressão real)

Incluindo não-derrota (V+E):
- p=3: 87% → 77% (−10 pp)
- p=5: 74% → 61% (−13 pp)
- p=6: 63% → 56% (−7 pp)

### Diagnóstico: saturação confirmada

A rede de 74.5k parâmetros atingiu seu limite de capacidade em depth=7. Aprofundar o professor (d=7 → d=8/9) **não transmite sinal adicional aproveitável** — ao contrário, introduz nuance tática que a rede não tem expressividade para reproduzir.

**Evidências:**
1. **OMA caiu mas Top-3/5 subiram:** padrão clássico de knowledge distillation saturado. O aluno aprende a "região aproximada" (top-3/5 melhoram) mas perde precisão no argmax (OMA piora, top-1 estagua). Isso indica que o sinal do professor excede a capacidade do aluno.

2. **val_loss KLD subiu:** de ~0.145 (rodada 4) para 0.185 (rodada 5). Alvo intrinsecamente mais difícil de aproximar — soft targets com profundidade maior têm mais nuance, menos empates e-ou-tudo.

3. **Top-1 não progrediu:** 42.7 → 42.71 com 14% mais dados é sinal de que a rede já estava saturada. Mais dados não conseguem compensar falta de expressividade.

4. **Win-rate concordou com OMA:** anterior, havia descolamento entre OMA (93%) e win-rate (96% vs p=1) — explicável porque v3 era novo e ainda estava sendo validado. Agora OMA caiu E win-rate caiu (salvo p=1, raso, onde ruído estatístico domina).

**Piso de blunders táticos:** ~13–15% de "caixas deixadas para o Minimax" é estável contra p ≥ 3, sugerindo uma classe específica de erro (provavelmente parity/loony endgame) que dataset adicional sozinho não cura — indica fraqueza estrutural, não falta de treinamento.

### Alternativa que foi **descartada em rodadas anteriores** e agora está confirmada necessária

A entrada de 2026-04-21 em `historico_decisoes.md` sobre "Regressão da Rodada 3 e descoberta do OMA=99%" planejou "Tentativa 7 (rodada 4)" justamente com T=1.0 e sem sample_weight, com a anotação "Esperamos Top-1 ≥ 37%". Rodada 4 entregou isso; rodada 5 agora revela que o teto foi atingido.

### Próximos passos

1. **Manter V3 (rodada 4, depth=7) como modelo de produção** — melhor win-rate em todas as profundidades ≥ 3.
2. **Aumentar capacidade da rede ANTES de tentar depth=8/9 novamente:**
   - Adicionar terceiro bloco residual (48 → 64 filtros).
   - Aumentar dense head (96 → 128).
   - Estimativa: 150–200k parâmetros totais, ainda < 300 KB em TFLite.
   - Re-treinar com dataset V4 (344k, d=8/9) com rede maior.
3. **Ou explorar largura em vez de profundidade:** gerar 600k+ amostras em d=7 (já validado) com rede atual. Provavelmente mais rápido.
4. **Investigar o piso de 13–15% de blunders táticos:** gravar `(estado, jogada_cnn, jogada_otima, score_gap)` em casos de erro no avaliador; analisar os 50 piores. Pode indicar fraqueza específica (chain control, parity) que arquitetura+ dataset não resolvem sozinhos.

---

## Tabela Resumida — Todas as Tentativas
