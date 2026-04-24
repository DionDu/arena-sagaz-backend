# Por que CNN em vez de Minimax Puro?

Argumentação completa para a defesa do TCC. Cobre velocidade, variedade de
jogadas, portabilidade, dificuldade ajustável, limitações e a narrativa
unificada para a banca.

---

## 1. Velocidade e Latência Variável

### O problema do Minimax em um jogo interativo

O Minimax é um algoritmo de busca em árvore. A cada turno, ele explora
recursivamente todas as jogadas possíveis até a profundidade configurada,
avaliando o estado resultante.

O custo computacional cresce exponencialmente com a profundidade e com o
número de traços disponíveis (o "fator de ramificação"):

```
Nós explorados (pior caso) ≈ traços_disponíveis ^ profundidade

Profundidade 7, início do jogo (31 traços): 31^7 ≈ 27 bilhões de nós
Profundidade 5, início do jogo (31 traços): 31^5 ≈  28 milhões de nós
```

A **Poda Alpha-Beta** reduz isso em até 50% na prática — mas o custo ainda
cresce com a profundidade e varia radicalmente com o estado do tabuleiro.

### Dados medidos no hardware do projeto (Ryzen 5700X)

| Profundidade | Início de jogo | Meio de jogo | Final de jogo |
|---|---|---|---|
| 7 | **~20 segundos** | ~0.5s | ~0.01s |
| 5 | ~0.5s | ~0.05s | ~0.01s |
| **CNN** | **~3ms** | **~3ms** | **~3ms** |

**Por que o Minimax é mais lento no início?** No início há muitos traços
disponíveis e poucos desequilíbrios de score entre ramos — a Alpha-Beta corta
pouco. No final do jogo, com poucos traços e scores bem diferenciados, a poda
elimina a maior parte da árvore e o cálculo é quase instantâneo.

### O problema real: latência imprevisível

Para um jogo interativo, latência variável é tão grave quanto latência alta.
Um jogador humano não consegue calibrar a espera quando às vezes a IA responde
em 0.01s e às vezes em 20s — dependendo do estado do tabuleiro.

A CNN realiza **sempre o mesmo cálculo** independente do estado: uma única
passagem pela rede neural (multiplicações de matrizes). O resultado:

- Profundidade 7: inviável (20s no início)
- Profundidade 5: aceitável, mas latência variável e qualidade limitada
- **CNN:** ~3ms constantes em qualquer posição, qualquer dispositivo

### Argumento para a banca

> *"O Minimax de profundidade 7 leva 20 segundos nas jogadas iniciais em
> hardware de alta performance (Ryzen 5700X). Em um smartphone de entrada,
> esse tempo seria dezenas de vezes maior. Além da velocidade absoluta, a
> latência do Minimax é altamente variável — quase instantânea no final da
> partida, intolerável no início. A rede neural realiza sempre o mesmo
> cálculo — uma passagem por matrizes fixas — gastando ~3ms consistentemente
> em qualquer posição e em qualquer hardware."*

---

## 2. Variedade de Jogadas e Dificuldade Ajustável

### O que o argumento "maior aleatoriedade" acerta

O comportamento da CNN parece mais variado que o Minimax porque ela aprendeu
preferências a partir de dezenas de milhares de posições distintas. O Minimax,
para o mesmo tabuleiro, sempre avalia a mesma árvore e chega ao mesmo resultado
— exceto pelo `random.choice` aplicado quando há empate de scores, que é o
único ponto de variação do algoritmo.

### O argumento mais forte: dificuldade ajustável por temperatura

A CNN produz uma **distribuição de probabilidade** sobre as 31 jogadas
possíveis. O Minimax produz apenas um score — um único número por jogada.

Essa diferença permite controlar a dificuldade com um único parâmetro chamado
**temperatura de inferência**, sem precisar recriar nem retreinar nada:

```python
probs = modelo.predict(tabuleiro)   # ex: [0.45, 0.30, 0.15, 0.05, ...]

# DIFÍCIL: concentra em torno da melhor jogada (T = 0.3)
probs_sharp = probs ** (1 / 0.3)
probs_sharp /= probs_sharp.sum()
jogada = random.choices(jogadas, weights=probs_sharp)[0]

# MÉDIO: usa a distribuição aprendida (T = 1.0)
jogada = random.choices(jogadas, weights=probs)[0]

# FÁCIL: distribui mais aleatoriamente (T = 2.0)
probs_soft = probs ** (1 / 2.0)
probs_soft /= probs_soft.sum()
jogada = random.choices(jogadas, weights=probs_soft)[0]
```

**Com Minimax puro**, você precisaria de três implementações separadas
(profundidades 3, 5, 7) para ter três níveis de dificuldade — e cada um com
seus problemas de latência. **Com a CNN**, um único modelo de ~100KB serve
todos os níveis.

Isso transforma o projeto de exercício algorítmico em solução de produto.

### Argumento para a banca

> *"O Minimax é determinístico: para o mesmo estado de tabuleiro, sempre
> escolhe a mesma jogada. Para ter diferentes níveis de dificuldade, seria
> necessário manter múltiplas instâncias do algoritmo em diferentes
> profundidades, cada uma com seus custos computacionais. A rede neural produz
> uma distribuição de probabilidade que pode ser amostrada com diferentes
> temperaturas de inferência — um único modelo serve como adversário fácil,
> médio ou difícil, simplesmente ajustando um parâmetro numérico."*

---

## 3. Portabilidade para Qualquer Dispositivo

### O problema do Minimax em hardware limitado

O Minimax consome CPU intensivamente durante a busca. Em dispositivos com
processadores lentos (smartphones de entrada, navegadores web, hardware
embarcado), a latência aumenta proporcionalmente.

Um Minimax de profundidade 5 que leva 0.5s em um Ryzen 5700X pode levar
5–10s em um smartphone de entrada — novamente inviabilizando o jogo.

### A vantagem da CNN

O modelo exportado em **TFLite** (TensorFlow Lite) pesa ~100KB e roda em:

| Ambiente | Requer modificação? |
|---|---|
| Android / iOS | Não — TFLite é nativo |
| Navegador web | Não — via TensorFlow.js |
| Raspberry Pi / hardware embarcado | Não — TFLite roda em ARM |
| Backend em servidor | Não — Python/TF padrão |

O cálculo é sempre o mesmo — multiplicações de matrizes otimizadas para o
hardware disponível. O TFLite usa automaticamente aceleração por GPU ou NPU
quando disponível no dispositivo.

### Argumento para a banca

> *"O modelo gerado tem ~100KB e roda nativamente em qualquer plataforma via
> TensorFlow Lite — Android, iOS, navegadores e hardware embarcado — sem
> nenhuma modificação de código. O Minimax requer CPU dedicada e cresce em
> custo com a profundidade necessária para jogo de qualidade. Essa portabilidade
> é o que torna a abordagem de destilação de política aplicável a produtos
> reais."*

---

## 4. Escalabilidade para Tabuleiros Maiores

O tabuleiro Pequeno tem 31 traços. O tabuleiro Médio (5×4) teria 49 traços.
O crescimento exponencial do Minimax torna profundidades altas inviáveis:

```
Tabuleiro pequeno (31 traços), profundidade 7: ~27 bilhões de nós
Tabuleiro médio  (49 traços), profundidade 7: ~49^7 ≈ 678 bilhões de nós
```

O Minimax de profundidade 7 no tabuleiro médio levaria **horas** por jogada.

A CNN do tabuleiro médio teria exatamente a mesma latência (~3ms) — o tamanho
da arquitetura é fixo, independente do número de traços.

---

## 5. Analogia com AlphaGo e AlphaZero

O projeto segue o mesmo princípio fundamental usado pela DeepMind em 2016–2017:

| AlphaGo/AlphaZero | Arena Sagaz |
|---|---|
| Jogo: Go (19×19) | Jogo: Dots and Boxes (4×3) |
| Professor: MCTS (Monte Carlo Tree Search) | Professor: Minimax Alpha-Beta |
| Aprendizado: rede neural imita o professor | Aprendizado: CNN imita o Minimax |
| Técnica: destilação de política | Técnica: destilação de política |
| Resultado: qualidade de oráculo, custo de rede | Resultado: OMA=99%, custo ~3ms |

**Destilação de política** (*policy distillation*) é o termo técnico para
transferir o conhecimento de um algoritmo lento (o "professor") para uma rede
neural rápida (o "aluno"). O AlphaZero generalizou isso para aprender do zero;
no nosso projeto, o professor já existe (Minimax) e o aluno aprende com seus
dados.

### Argumento para a banca

> *"A estratégia deste trabalho é análoga à empregada pela DeepMind no
> AlphaGo: substituir um algoritmo de busca computacionalmente custoso por uma
> rede neural que aprende a imitar seu comportamento. O processo é chamado de
> destilação de política — o Minimax funciona como professor, gerando exemplos
> de jogadas ótimas, e a CNN funciona como aluno, aprendendo a reproduzi-las
> em tempo constante. A diferença de escala — Go contra Dots and Boxes — não
> muda o princípio; muda apenas a viabilidade dentro do escopo de um TCC."*

---

## 6. Limitações Honestas (Importante para a Defesa)

Uma banca forte vai questionar. Apresentar as limitações antes demonstra
maturidade acadêmica.

### 6.1 — A CNN não joga perfeitamente

O Minimax com profundidade suficiente joga de forma **ótima garantida**. A CNN
tem Optimal Move Accuracy de 99% — escolhe uma jogada subótima em 1% dos casos.

**Resposta preparada:**
> *"Aceitamos esse trade-off de forma deliberada. Em 200 partidas contra o
> Minimax de profundidade 5, a CNN venceu X% — qualidade competitiva sem
> garantia formal de otimalidade. Para aplicações críticas, o Minimax é mais
> seguro; para jogos interativos em tempo real, a CNN é a escolha prática."*

### 6.2 — A CNN é uma caixa-preta

Não é possível explicar *por que* a CNN escolheu uma jogada específica. O
Minimax é completamente transparente: você pode ver a árvore de busca inteira.

**Resposta preparada:**
> *"Explainability é uma limitação conhecida de redes neurais profundas. No
> contexto de um jogo educacional, o que importa para o usuário é o resultado
> da jogada, não sua justificativa algorítmica. Em aplicações onde
> transparência é crítica — medicina, finanças — o Minimax seria preferível."*

### 6.3 — A qualidade depende dos dados de treinamento

Se o Minimax que gerou os dados tiver erros ou limitações (ex: profundidade
insuficiente para enxergar sacrifícios longos), a CNN herda esses erros. O
Minimax com profundidade suficiente não depende de dados — ele calcula.

**Resposta preparada:**
> *"Geramos os dados com Minimax de profundidade 6, que é suficiente para
> cobrir as decisões críticas do tabuleiro Pequeno. Para tabuleiros maiores,
> profundidades maiores seriam necessárias — o que é viável com a
> paralelização implementada no gerador."*

---

## 7. Narrativa Unificada para a Apresentação

### Versão curta (30 segundos)

> *"O Minimax joga perfeitamente, mas leva 20 segundos por turno no início do
> jogo. Isso o torna inviável para qualquer produto interativo. Nossa CNN imita
> o Minimax com 99% de precisão estratégica, decide em 3 milissegundos
> constantes, cabe em 100KB e roda em qualquer dispositivo — celular, navegador
> ou hardware embarcado."*

### Versão completa (2–3 minutos para a banca)

> *"A escolha de uma CNN em vez do Minimax puro é motivada por quatro
> limitações práticas do algoritmo de busca.*
>
> *Primeiro, velocidade: o Minimax de profundidade 7 levou 20 segundos nas
> jogadas iniciais em um processador Ryzen 5700X. Em um smartphone, isso seria
> dezenas de segundos — inaceitável para uma experiência de jogo. A CNN decide
> em 3ms independente do estado do tabuleiro.*
>
> *Segundo, previsibilidade: a latência do Minimax varia de 20 segundos no
> início a quase zero no final — o usuário não sabe quanto vai esperar. A CNN
> tem latência constante.*
>
> *Terceiro, portabilidade: o modelo TFLite de 100KB roda nativamente em
> Android, iOS e navegadores sem nenhuma modificação. O Minimax requer CPU
> dedicada.*
>
> *Quarto, flexibilidade: a CNN produz uma distribuição de probabilidade que
> permite ajustar a dificuldade por temperatura de inferência. Com Minimax,
> seriam necessárias implementações separadas para cada nível.*
>
> *Essa abordagem — treinar uma rede neural para imitar um algoritmo de busca
> — é chamada de destilação de política e é o mesmo princípio do AlphaGo. O
> resultado: OMA de 99% com custo computacional 10.000 vezes menor."*

---

## 8. Tabela Comparativa Final

| Critério | Minimax puro | CNN (este projeto) |
|---|---|---|
| Tempo início do jogo | 20s (prof. 7) | **~3ms** |
| Tempo meio do jogo | ~0.5s | **~3ms** |
| Latência previsível | ❌ Não | ✅ Sim |
| Funciona em celular | ❌ Muito lento | ✅ Nativo |
| Funciona em navegador | ❌ Limitado | ✅ TensorFlow.js |
| Tamanho do modelo | Não tem (é código) | **~100KB** |
| Qualidade estratégica | 100% (ótimo garantido) | 99% (OMA) |
| Dificuldade ajustável | ❌ Múltiplas instâncias | ✅ Temperatura de inferência |
| Explicável | ✅ Sim (árvore de busca) | ❌ Caixa-preta |
| Escala para tabuleiro maior | ❌ Exponencialmente mais lento | ✅ Mesma latência |
