# Soft Targets e KL Divergence: Por Que a Rede Aprende uma Distribuição, Não uma Resposta

Esta seção responde três perguntas que uma banca de TCC certamente fará ao
avaliar uma rede neural treinada para jogar o Jogo dos Pontinhos.

---

## 1. O Problema do Rótulo Único (Argmax)

No Minimax, é muito comum que **várias jogadas sejam igualmente ótimas**.
Considere um tabuleiro em que o Minimax calcula o seguinte:

```
H_0_1  →  score +2   ← ótimo
H_0_3  →  score +2   ← ótimo (empate!)
H_2_1  →  score +2   ← ótimo (empate!)
V_1_0  →  score  0   ← neutro
V_3_2  →  score -1   ← ruim
```

Três jogadas são matematicamente equivalentes. Na abordagem clássica de aprendizado
supervisionado, o gerador de dados **sorteia uma** e grava apenas ela como rótulo:

```
foto do tabuleiro  →  rótulo: "H_0_1"    ← foi sorteada, mas H_0_3 e H_2_1 são iguais
```

Em outro momento, para um tabuleiro em situação idêntica, o sorteio pode recair
em `H_0_3`. A rede recebe dois exemplos praticamente iguais com **rótulos
diferentes** — um sinal contraditório que ela não consegue reconciliar. O resultado
é uma rede que aprende mal justamente as jogadas de borda e abertura, onde os
empates são mais frequentes.

---

## 2. O Que São Soft Targets (Alvos Suaves)?

Em vez de gravar apenas o vencedor do sorteio, o gerador agora salva o **score
do Minimax para todas as 31 jogadas disponíveis** de cada tabuleiro:

```
foto do tabuleiro  →  scores: [+2, +2, +2, 0, -1, -1e9, -1e9, ...]
                                H_0_1  H_0_3  H_2_1  V_1_0  V_3_2  (vazias)
```

O valor `-1e9` indica uma jogada indisponível (traço já preenchido ou ponto fixo).

No notebook de treinamento, esses scores são convertidos em uma **distribuição de
probabilidade** via função Softmax com temperatura T:

```python
# 1. Mascara posições indisponíveis
mascara = scores > -1e8

# 2. Softmax estabilizado numericamente
exp = np.exp((scores - scores.max(axis=1, keepdims=True)) / T)

# 3. Zera as posições mascaradas e normaliza
exp = exp * mascara
prob_alvo = exp / exp.sum(axis=1, keepdims=True)
```

Com T = 1.0, o resultado para o exemplo acima é:

```
alvo suave:  [0.33,  0.33,  0.33,  0.01,  0.0,  0.0, ...]
              H_0_1  H_0_3  H_2_1  V_1_0  V_3_2  vazias
```

A rede não está mais sendo treinada para adivinhar qual das três foi sorteada.
Ela está sendo treinada para aprender que **as três jogadas valem o mesmo**.

---

## 3. Por Que KL Divergence em Vez de Categorical Crossentropy?

### Categorical Crossentropy (abordagem antiga)

A `CategoricalCrossentropy` mede o quanto a previsão da rede erra em relação a
um alvo **one-hot** — um vetor com um único `1` e o restante `0`:

```
alvo one-hot:  [0, 0, 1, 0, 0, 0, ...]   ← só H_0_1 "existe"
previsão:      [0.1, 0.05, 0.6, 0.15, 0.1, ...]
loss = -log(0.6) ≈ 0.51                  ← pune por não ter 100% em H_0_1
```

O problema: a loss pune a rede por atribuir probabilidade a `H_0_3` e `H_2_1`,
que são **igualmente corretas**. A rede aprende a fingir certeza onde não há.

### KL Divergence (abordagem nova)

A `KLDivergence` mede o quanto a distribuição prevista pela rede diverge da
distribuição alvo (os soft targets):

```
alvo suave:  [0.33, 0.33, 0.33, 0.01, 0.0, ...]
previsão:    [0.30, 0.28, 0.25, 0.05, 0.02, ...]

KLD = Σ alvo × log(alvo / previsão)
    ≈ pequeno, pois as formas das distribuições são parecidas
```

A rede é recompensada por aprender a *forma* do ranking do Minimax — não por
adivinhar qual dos empates foi sorteado.

### Tabela comparativa

| Critério | Categorical Crossentropy | KL Divergence |
|---|---|---|
| Tipo de alvo | One-hot (1 classe) | Distribuição completa |
| Empates no Minimax | Punidos como erros | Distribuídos igualmente |
| Sinal para bordas | Ruidoso (sorteio) | Claro (peso proporcional) |
| Interpretação | "A resposta correta é X" | "O ranking correto é este" |
| Uso aqui | Dataset antigo (50k) | Dataset novo (200–300k) |

---

## 4. Onde Ainda Existe um Argmax?

Com soft targets, o argmax desaparece **do treino**. Mas ele ainda existe em
dois lugares:

| Momento | O que acontece |
|---|---|
| **Dataset** | `rotulos` (string da jogada ótima) mantido para métricas e conferência, mas não é o alvo do treino |
| **Avaliação** | `argmax(previsão)` = classe com maior probabilidade prevista → usado para calcular top-1, top-3, top-5 |
| **Jogo (inferência)** | `argmax(previsão)` = o traço que a IA executa de fato na partida |

O argmax voltou a ser relevante **depois** que a rede aprendeu — é o momento de
usar o conhecimento, não de ensiná-lo.

---

## 5. Por Que Isso Exige um Dataset Novo?

O soft target de um estado requer o **vetor completo de scores do Minimax** para
aquele estado. O dataset antigo (50k registros) gravava apenas a string da jogada
sorteada — não há como reconstruir os outros 30 scores sem rodar o Minimax
novamente para cada tabuleiro.

Por isso os 50k registros antigos foram descartados e o gerador foi modificado
para salvar `scores` (vetor 31 × `float32`) em todos os novos lotes.

---

## 6. Resumo para a Defesa do TCC

Se a banca perguntar: *"Por que você trocou a função de perda?"*

> *"A função de perda original, Categorical Crossentropy, trata o problema como
> classificação com uma única resposta correta. Porém, no Jogo dos Pontinhos,
> múltiplas jogadas podem ter valor idêntico pelo algoritmo Minimax — são
> matematicamente equivalentes. Sortear uma e punir as outras introduz ruído
> sistemático no treinamento, especialmente para as jogadas de borda, onde os
> empates são mais frequentes na abertura do jogo.*
>
> *Para eliminar esse ruído, passei a salvar o vetor completo de scores do
> Minimax para todas as jogadas disponíveis em cada estado. Durante o
> treinamento, esses scores são normalizados via Softmax e usados como alvo
> de uma distribuição de probabilidade. A KL Divergence mede o quanto a
> distribuição prevista pela rede diverge desse alvo — em vez de punir a rede
> por distribuir probabilidade entre jogadas equivalentes, ela a recompensa por
> aprender o ranking correto. Essa técnica é análoga à destilação de política
> usada no AlphaZero, adaptada ao escopo do trabalho."*
