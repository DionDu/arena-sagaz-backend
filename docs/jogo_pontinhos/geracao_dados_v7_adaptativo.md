# Geração V7 Adaptativa — Algoritmo DAC

> **Documento de design.** Fonte canônica das decisões, fórmulas, exemplos
> e raciocínio por trás do pipeline V7. Material referenciado pelo TCC.
>
> Notebook: `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb`
> Worker: `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py`
> Histórico: ver entrada de 2026-05-08 em `docs/historico_decisoes.md`.

---

## 1. Motivação

Os pipelines anteriores (V4, V5, V5_Local, V6) sofriam com três problemas
crônicos no Jogo dos Pontinhos (tabuleiro 9×7, 4×3 caixas, 31 traços):

1. **Estrangulamento de duplicatas no endgame.** A geração V6 com Minimax
   p=2 atingia ~40% de duplicatas, com a faixa "quente" (24–28 traços)
   exigindo ~298 mil tentativas brutas para 53 mil distintos.
2. **Meta inviável na faixa final.** A faixa 29–30 tinha cota de 500 estados
   distintos, mas o limite teórico do espaço é
   `C(31,29) + C(31,30) = 465 + 31 = 496` — fisicamente impossível.
3. **Profundidade fixa do autoplay desperdiça CPU.** Rodar Minimax p=3
   uniformemente significa pagar tempo cubico em posições de abertura
   onde o resultado é uma escolha aleatória entre lances neutros.

A V7 reformula a geração com base em uma observação simples: **a profundidade
necessária para escolher uma jogada bem é função da estrutura do tabuleiro,
não do número de traços**. E **uma única partida do início ao fim cobre
naturalmente todos os t∈[1,30]**, eliminando a necessidade de quotas
estratificadas.

---

## 2. Princípios do algoritmo DAC

DAC = **Diversidade Adaptativa em Cascata**. Quatro alavancas combinadas:

| # | Alavanca | Decisão |
|---|---|---|
| 1 | Profundidade do Minimax | Adaptativa por **tensão estrutural τ** |
| 2 | Desempate de jogadas | **Boltzmann sampling** com temperatura T(t) |
| 3 | Forma de gerar amostras | **30 snapshots por partida** (t=1..30) |
| 4 | Estratificação | **Emergente** — sem quotas; meta única de 500k distintos |

Os itens 1 e 2 garantem **qualidade e diversidade** das trajetórias. O item 3
garante **cobertura** automática de todas as fases do jogo. O item 4 elimina
toda a complexidade administrativa de balanceamento manual.

---

## 3. Tensão estrutural τ

A **tensão estrutural** é uma medida da pressão estratégica de um tabuleiro:
quantas caixas estão "perto de fechar" e, portanto, quantas decisões
imediatas têm consequência alta.

### 3.1 Definição

Para cada caixa do tabuleiro (não fechada), conta-se o número de lados (0 a 4)
já preenchidos. A função τ é uma soma ponderada:

$$
\tau = 4 \cdot c_3 + 2 \cdot c_2 + 0{,}5 \cdot c_1
$$

Onde:
- $c_3$ = número de caixas com **3 lados** preenchidos (ameaças imediatas)
- $c_2$ = número de caixas com **2 lados** (decisões potenciais de cadeia)
- $c_1$ = número de caixas com **1 lado** (estruturas iniciais)

Caixas com 0 ou 4 lados não contribuem (não há decisão envolvida).

### 3.2 Justificativa dos pesos

Os pesos `(4, 2, 0.5)` refletem o impacto estratégico relativo:

- **Caixa-3-lados (peso 4)**: o adversário pode fechá-la na próxima jogada.
  Se for parte de uma cadeia, perdemos potencialmente várias caixas. É a
  decisão mais quente do jogo.
- **Caixa-2-lados (peso 2)**: cada lado adicional pode iniciar ou bloquear
  uma cadeia. Decisão importante mas não imediata.
- **Caixa-1-lado (peso 0,5)**: pouca consequência por si só, mas indica
  que o tabuleiro está saindo da fase neutra de abertura.

### 3.3 Mapeamento τ → profundidade

A profundidade do Minimax é função afim de τ, com piso 1 e teto 8:

$$
p(\tau) = \mathrm{clamp}\!\left(1 + \left\lceil \frac{\tau}{4} \right\rceil,\; 1,\; 8\right)
$$

| τ | p (profundidade) |
|---:|---:|
| 0 | 1 |
| 1–4 | 2 |
| 5–8 | 3 |
| 9–12 | 4 |
| 13–16 | 5 |
| 17–20 | 6 |
| 21–24 | 7 |
| ≥ 25 | 8 |

O teto p=8 é prudência: posições com τ muito alto têm árvore pequena
(poucos traços livres), e p=8 já enxerga até o terminal.

---

## 4. Boltzmann sampling (desempate)

Em vez de escolher sempre o lance ótimo (argmax) ou de desempatar
uniformemente entre top-1's, o Boltzmann sampling pondera todos os
lances pela sua qualidade:

$$
P(\text{lance } i) = \frac{\exp(s_i / T)}{\sum_j \exp(s_j / T)}
$$

Onde $s_i$ é o score Minimax do lance $i$ e $T$ é a **temperatura**:

- $T \to 0$: tende ao argmax determinístico (escolha gulosa).
- $T \to \infty$: tende à distribuição uniforme (escolha aleatória).
- $T$ intermediário: escolhe os bons com mais frequência, mas dá
  alguma chance aos quase-bons.

### 4.1 Schedule de temperatura T(t)

A temperatura decresce com o número de traços já jogados:

| Faixa de t | T |
|---|---:|
| t < 8 (abertura) | 1,5 |
| 8 ≤ t < 18 (midgame) | 0,8 |
| 18 ≤ t < 26 (transição) | 0,5 |
| t ≥ 26 (endgame) | 0,2 |

**Justificativa**: na abertura, vários lances têm scores quase iguais —
distinguir o "melhor" é ilusão de precisão. T alta dá diversidade real
sem sacrificar qualidade. No endgame, lances erróneos têm consequência
imediata (perder uma cadeia) — T baixa preserva qualidade.

---

## 5. Snapshots por partida

Cada partida começa do tabuleiro vazio e vai até o terminal (31 traços
aplicados). Após cada traço, captura-se um snapshot do estado para o
dataset.

### 5.1 Fluxo

```
t=0: tabuleiro vazio (DESCARTADO — sempre o mesmo)
   ↓ aplica 1ª jogada
t=1: snapshot #1
   ↓ aplica 2ª jogada
t=2: snapshot #2
   ...
t=30: snapshot #30
   ↓ aplica 31ª jogada
t=31: terminal (DESCARTADO — não há jogada a aprender)
```

**30 snapshots por partida.** Os estados t=0 e t=31 são descartados:
- t=0 é sempre o tabuleiro vazio (1 único estado, gravar é desperdício).
- t=31 é terminal (a CNN nunca precisa decidir o que jogar lá).

### 5.2 Distribuição emergente

Como cada partida cobre exatamente um estado por t∈[1,30], a distribuição
de DISTINTOS após N partidas é governada pelo teto teórico do espaço
combinatorial em cada t:

| t | Espaço teórico C(31,t) | Distintos esperados (~25k partidas) | Comportamento |
|---:|---:|---:|---|
| 1 | 31 | 31 | satura em ~30 partidas |
| 2 | 465 | 465 | satura em ~600 partidas |
| 3 | 4.495 | ~4.490 | satura em ~5k partidas |
| 4 | 31.465 | ~22.000 | quase saturando |
| 5–25 | 10⁵ – 10⁸ | ~25.000 cada | longe de saturar |
| 26 | 169.911 | ~24.000 | sem saturar |
| 27 | 31.465 | ~22.000 | quase saturando |
| 28 | 4.495 | ~4.490 | satura em ~5k |
| 29 | 465 | 465 | satura em ~600 |
| 30 | 31 | 31 | satura em ~30 |

A distribuição final é **bell-shaped** centrada em t≈15–17, com platôs de
saturação nas pontas (espaços pequenos preenchidos completamente). Esta é
a distribuição **ideal** para a CNN: cobertura completa onde o espaço é
finito, e milhares de exemplos no midgame onde decisões importam mais.

### 5.3 Estimativa de custo

Para atingir 500 mil estados distintos com N partidas, considerando taxa
média de retenção ~65% (devido à saturação progressiva nas pontas):

$$
\frac{500{.}000}{0{,}65 \times 30} \approx 25.000 \text{ partidas}
$$

Com 14 workers e profundidade adaptativa (média efetiva ~p=3), uma partida
completa leva ~3-8s. Estimativa total: **2 a 4 horas**.

---

## 6. Exemplo: profundidade τ-adaptativa em uma partida real

A tabela abaixo mostra como τ (e portanto p) variam ao longo de uma
partida típica. As contagens `c1`, `c2`, `c3` são exemplos plausíveis para
cada turno.

| Turno (t) | qtd_tracos | c1 | c2 | c3 | τ | depth_geracao |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 0 | 0 | 0,5 | **1** |
| 2 | 2 | 2 | 0 | 0 | 1,0 | **1** |
| 3 | 3 | 1 | 1 | 0 | 2,5 | **1** |
| 5 | 5 | 3 | 1 | 0 | 3,5 | **1** |
| 8 | 8 | 4 | 2 | 0 | 6,0 | **2** |
| 12 | 12 | 4 | 4 | 0 | 10,0 | **4** |
| 16 | 16 | 2 | 6 | 0 | 13,0 | **5** |
| 20 | 20 | 1 | 6 | 1 | 16,5 | **6** |
| 24 | 24 | 0 | 5 | 2 | 18,0 | **6** |
| 27 | 27 | 0 | 3 | 3 | 18,0 | **6** |
| 29 | 29 | 0 | 1 | 4 | 18,0 | **6** |
| 30 | 30 | 0 | 0 | 1 | 4,0 | **2** |

**Padrão observado:**

- **Abertura (t=1..7)**: traços ainda não tocam as mesmas caixas; τ baixo;
  p=1. O Minimax praticamente "sorteia" entre lances equivalentes (com
  Boltzmann T=1,5 a distribuição é quase uniforme). Custo desprezível.
- **Midgame (t=12..20)**: caixas começam a acumular 2 lados; τ cresce; p
  sobe a 4–6. Minimax já enxerga 4–6 níveis à frente, suficiente para
  detectar quem ficaria preso na próxima cadeia.
- **Endgame (t=24..29)**: tabuleiro com várias caixas-3-lados (cada uma é
  decisão crítica), mas τ não explode porque há cada vez menos jogadas
  legais (31−t restantes); p=6 é suficiente para enxergar todo o resto.
- **Último turno (t=30)**: quase todas as caixas estão fechadas; τ
  desabou (sobrou 1 caixa-3-lados a fechar); p volta a ser baixo. Custo
  desprezível.

**Por que isso é eficiente**: a maior parte do tempo de CPU é gasta nos
turnos t=16..29 (onde p=5..7). Os 15 primeiros turnos passam quase grátis
(p=1..3). Sem adaptatividade, gastaríamos p=7 em todos os 31 turnos × N
partidas — várias ordens de magnitude mais caro.

---

## 7. Esquema do NPZ V2

NPZs gerados pelo pipeline V7 seguem o esquema abaixo:

| Campo | Shape | Dtype | Preenchido em | Descrição |
|---|---|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` | Fase 1 | Matriz neutra `{0,1,8,9}` |
| `qtd_tracos` | `(N,)` | `int8` | Fase 1 | Número de traços aplicados (1..30) |
| `score_jogada` | `(N, 31)` | `float32` | Fase 1 | Scores Minimax CALCULADOS no estado atual (decidem jogada que leva ao próximo) |
| `depth_jogada` | `(N,)` | `int8` | Fase 1 | Profundidade Minimax usada NESTE estado |
| `depth_geracao` | `(N,)` | `int8` | Fase 1 | Profundidade Minimax usada no estado ANTERIOR (= depth_jogada[k−1]) |
| `melhor_jogada` | `(N,)` | `<U5` | Fase 2 | Argmax dos `score_melhor_jogada` |
| `score_melhor_jogada` | `(N, 31)` | `float32` | Fase 2 | Scores Minimax(p=7) — verdade-padrão para treino |
| `depth_melhor_jogada` | `(N,)` | `int8` | Fase 2 | Profundidade Minimax usada na Fase 2 (= 7 fixo, mas por estado) |
| `labels_canonicos` | `(31,)` | `<U5` | Fase 1 | Ordem canônica dos slots de score |

**Slots inválidos (jogadas já preenchidas)**: recebem `SCORE_INDISPONIVEL = -1e9`
em ambos `score_jogada` e `score_melhor_jogada`.

**Diretório de saída**: `dados/profundidade_minmax_{DEPTH_MELHOR_JOGADA}_adaptativo/`,
ou seja, `dados/profundidade_minmax_7_adaptativo/` na configuração padrão.

### 7.1 Distinção score_jogada vs score_melhor_jogada

| Campo | Origem | Profundidade | Uso recomendado |
|---|---|---:|---|
| `score_jogada` | Calculado durante a Fase 1 (autoplay) | Adaptativa, p∈[1,8] | Análise / curriculum / soft-label opcional |
| `score_melhor_jogada` | Calculado na Fase 2 com profundidade fixa | 7 (fixo) | **Verdade-padrão para treino da CNN** |

Confundir os dois ao treinar é erro grave: `score_jogada` reflete decisões
rápidas durante a geração (qualidade variável), enquanto `score_melhor_jogada`
é a deliberação completa e uniforme. **Sempre treinar contra
`score_melhor_jogada`**.

---

## 8. Pipeline completo

### 8.1 Fase 1 — Geração de estados via DAC

1. Configura pool de workers (`cpu_count() - 2`, ≈14 no Ryzen 7 5700X).
2. Para cada partida:
   - Worker recebe seed aleatória do main.
   - Joga 31 traços do zero ao terminal:
     - A cada turno, calcula τ → p, escolhe T(t).
     - Roda Minimax(p) para todas as jogadas legais (Q-values).
     - Boltzmann-sample um lance proporcional aos Q-values.
     - Aplica o lance.
   - Retorna lista de **30 snapshots** (estados a t=1..30).
3. Main desempacota cada lista, deduplica via hash global, acumula em
   buffer; a cada 5.000 amostras grava NPZ atomicamente.
4. **Stop**: ao atingir ≥ 500.000 distintos, drena partidas em curso e
   encerra.

**Duplicatas são gravadas** no NPZ (não filtradas durante a geração) — o
dedup é feito apenas em memória, para contar progresso da meta de
distintos. Isso permite ao notebook de treino fazer dedup posterior de
forma centralizada.

### 8.2 Fase 2 — Cálculo da melhor jogada

1. Coleta o set de estados ÚNICOS de todos os NPZs pendentes.
2. Em paralelo: para cada estado único, roda
   `melhor_jogada_com_scores(estado, profundidade=7)`.
   - Resultado: `(rotulo_argmax, scores_(31,))`.
   - Cache global por hash → cada estado único é processado uma vez,
     duplicatas reusam o resultado.
3. Reescreve cada NPZ atomicamente, populando `melhor_jogada`,
   `score_melhor_jogada` e `depth_melhor_jogada`.

---

## 9. Comparação V6 vs V7

| Item | V6 | V7 |
|---|---|---|
| Profundidade autoplay | Fixa (p=2 ou p=3) | **Adaptativa por τ** |
| Desempate | `random.choice` entre top-1 | **Boltzmann com T(t)** |
| Geração | 1 estado/worker | **30 estados/worker (1 partida)** |
| Faixas/quotas | 5 faixas com cotas rígidas | **Sem faixas; meta única 500k** |
| Faixa 29–30 | Cota 500 (impossível, teto 496) | **Saturação natural** (todos os 496) |
| `generation_mode` | Campo do NPZ (3 valores) | **Removido** |
| `qtd_tracos` | Não armazenado | **Por estado** |
| Métricas Minimax/estado | Só `score` global | **score_jogada, depth_jogada, depth_geracao, score_melhor_jogada, depth_melhor_jogada** |
| Custo estimado | ~14h | **~2-4h** |

---

## 10. Glossário

- **τ (tau)**: tensão estrutural do tabuleiro. Soma ponderada de caixas
  com 1, 2 ou 3 lados preenchidos.
- **p**: profundidade do Minimax. Inteiro em [1, 8].
- **T (temperatura)**: parâmetro do Boltzmann sampling. Controla
  quão "guloso" é o desempate de jogadas.
- **DAC**: Diversidade Adaptativa em Cascata — nome do algoritmo desta
  V7.
- **Snapshot**: par (estado, metadados) gravado no dataset, capturado
  durante uma partida.
- **score_jogada**: scores Minimax calculados no estado atual durante
  a Fase 1 (autoplay com p adaptativo). Serve para **decidir a próxima
  jogada da partida**.
- **score_melhor_jogada**: scores Minimax calculados na Fase 2 com
  profundidade fixa (=7). É a **verdade-padrão para treino da CNN**.
- **depth_geracao[k]**: profundidade Minimax usada para escolher a
  jogada que LEVOU ao estado a t=k (= profundidade no estado a t=k-1).
- **depth_jogada[k]**: profundidade Minimax usada NO ESTADO a t=k para
  decidir a jogada seguinte. Note: `depth_geracao[k] = depth_jogada[k-1]`.

---

## 11. Referências cruzadas

- Contrato de codificação: `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`
  (§contexto_1_geracao_dataset)
- Implementação Minimax: `gerador_dados/jogo_pontinhos/minimax_pontinhos.py`
- Worker V7: `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py`
- Notebook V7: `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb`
- Guia de uso: `docs/jogo_pontinhos/guia_geracao_dados.md` §1C
- Decisões: `docs/historico_decisoes.md` (entrada 2026-05-08 — V7)
