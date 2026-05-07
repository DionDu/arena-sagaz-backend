# Fundamentos de CNN aplicados ao Jogo dos Pontinhos

Este documento consolida os conceitos fundamentais de Redes Neurais
Convolucionais (CNN) necessários para entender, manter e evoluir o modelo
`BoxNet` utilizado no Arena Sagaz. O material foi construído com foco
pedagógico para servir de apoio a quem esteja estudando deep learning pela
primeira vez — em especial para uso como material de TCC — e todas as
explicações são contextualizadas para o nosso produto (CNN para Dots and
Boxes) e para os dados que alimentam o modelo (matrizes de tabuleiro codificadas
conforme `contrato_codificacao_pontinhos.json`).

O documento não substitui o contrato de codificação nem o guia de geração de
dados — ele complementa esses artefatos, explicando os **fundamentos** que
justificam as escolhas de arquitetura registradas em
`historico_decisoes.md` e implementadas em
`notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V5.ipynb`.

---

## 1. O conceito de canal em uma CNN

### 1.1 De onde vem a ideia de canal

Quando uma câmera tira uma foto colorida, a imagem de, por exemplo, 100×100
pixels não é representada por um único array 2D. Ela é representada por **três
arrays 2D empilhados**:

```
Canal R (vermelho): 100×100 números de 0 a 255
Canal G (verde):    100×100 números de 0 a 255
Canal B (azul):     100×100 números de 0 a 255
```

Juntos, formam um tensor de shape `(100, 100, 3)`. O número `3` é o **número de
canais**.

Cada canal é uma "visão" da mesma cena, medindo uma **propriedade diferente**
no mesmo lugar. No pixel `(50, 50)`:

- Canal R responde "quanto vermelho tem aqui?" — por exemplo, 200.
- Canal G responde "quanto verde tem aqui?" — por exemplo, 50.
- Canal B responde "quanto azul tem aqui?" — por exemplo, 30.

Esses três valores juntos dizem que aquele pixel é laranja escuro.

A ideia-chave é: na **mesma posição espacial**, empilha-se **várias medições
diferentes**, e a rede aprende a combiná-las.

### 1.2 Por que convoluções se dão bem com canais

Uma camada convolucional passa um **filtro** — tipicamente uma janelinha 3×3 —
por toda a imagem. Em cada posição da janela, o filtro faz uma soma ponderada
dos valores **de todos os canais juntos**. O filtro então enxerga
simultaneamente "quanto R, G e B tem nesta vizinhança 3×3" e pode aprender
padrões como "isto parece uma boca" combinando informação de cor.

Canais são, portanto, **camadas de informação sobrepostas no mesmo espaço** que
a convolução processa em conjunto.

### 1.3 Canais em tarefas que não são imagens

A ideia de canais não se limita a RGB. Em qualquer problema é possível empilhar
múltiplas visões da mesma posição:

- **Áudio (espectrograma):** um canal de intensidade por frequência.
- **Imagem médica (tomografia):** vários canais, cada um um tipo diferente de
  contraste.
- **AlphaGo:** tabuleiro 19×19 de Go com 17 canais — um dizendo onde estão as
  pedras pretas, outro as brancas, outro o histórico de jogadas anteriores,
  outro de quem é a vez de jogar, e assim por diante. A rede recebe um tensor
  `(19, 19, 17)`.

O padrão é sempre o mesmo: **mesma grade espacial, várias propriedades em cada
célula, empilhadas como canais**.

---

## 2. A entrada da BoxNet e a transformação `para_grid_de_caixas`

### 2.1 A entrada crua da rede

No notebook `Treinamento_CNN_Arena_Sagaz_V4.ipynb`, logo após a normalização da
matriz conforme `contrato_codificacao_pontinhos.json`, existe a linha:

```python
X = X_raw[..., np.newaxis]
```

Essa operação transforma cada matriz `(9, 7)` em `(9, 7, 1)` — ou seja, a rede
recebe **um único canal**. O shape da entrada é:

```
(numero_de_amostras, 9, 7, 1)
                          ↑
                          1 canal apenas
```

Esse canal único contém valores `{0, 1}` (após a normalização), e um valor `1`
pode significar três coisas diferentes dependendo da paridade da célula:

- `1` em célula linha-par / coluna-ímpar: traço horizontal preenchido.
- `1` em célula linha-ímpar / coluna-par: traço vertical preenchido.
- `1` em célula linha-ímpar / coluna-ímpar: caixa fechada.

A rede teria, então, que deduzir sozinha qual é qual, olhando a posição da
célula na matriz.

### 2.2 O que a função `para_grid_de_caixas` faz

A primeira camada útil da BoxNet é uma `Lambda` que chama a função
`para_grid_de_caixas`. Ela reorganiza a matriz `9×7×1` em uma grade `4×3×5`:

- `4×3` é o espaço natural do tabuleiro pequeno: 4 linhas × 3 colunas **de
  caixas**. Esse é o formato declarado em
  `contrato_codificacao_pontinhos.json`, seção `dimensoes_por_tamanho.pequeno`
  (`linhas_caixas_conceituais = 4`, `colunas_caixas_conceituais = 3`).
- `5` é o número de **canais** criados.

Cada uma das 12 caixas (4×3) passa a ser uma célula com 5 informações
empilhadas:

- **Canal 0 — topo:** o traço horizontal acima desta caixa está preenchido?
  (0 ou 1)
- **Canal 1 — base:** o traço horizontal abaixo desta caixa está preenchido?
  (0 ou 1)
- **Canal 2 — esquerda:** o traço vertical à esquerda desta caixa está
  preenchido? (0 ou 1)
- **Canal 3 — direita:** o traço vertical à direita desta caixa está
  preenchido? (0 ou 1)
- **Canal 4 — interior:** esta caixa já foi fechada? (0 ou 1)

Cada caixa, portanto, é descrita por um perfil de 5 bits que cobre exatamente
o vocabulário tático do Dots and Boxes.

### 2.3 Visualizando o empilhamento

Pode-se imaginar cinco pranchas transparentes empilhadas, cada uma uma grade
4×3:

```
    ┌───┬───┬───┐
    │   │   │   │   ← canal 4: interior (caixa fechada?)
    ├───┼───┼───┤
    │   │   │   │
    └───┴───┴───┘
    ┌───┬───┬───┐
    │   │   │   │   ← canal 3: direita
    ├───┼───┼───┤
    │   │   │   │
    └───┴───┴───┘
    ┌───┬───┬───┐
    │   │   │   │   ← canal 2: esquerda
    ├───┼───┼───┤
    │   │   │   │
    └───┴───┴───┘
    ┌───┬───┬───┐
    │   │   │   │   ← canal 1: base
    ├───┼───┼───┤
    │   │   │   │
    └───┴───┴───┘
    ┌───┬───┬───┐
    │   │   │   │   ← canal 0: topo
    ├───┼───┼───┤
    │   │   │   │
    └───┴───┴───┘
```

Quando a próxima camada — um `Conv2D` — passa um filtro 3×3 por esse tensor,
em cada posição de caixa o filtro enxerga **cinco números simultaneamente**:
todo o perfil estrutural daquela caixa. A rede pode então aprender padrões
como:

- "Se canais 0, 1, 2 = 1 e canal 3 = 0, então esta caixa tem três arestas —
  completá-la é crítico" (captura de caixa).
- "Se uma caixa tem duas arestas adjacentes preenchidas e a caixa ao lado
  também, cuidado: está se formando uma cadeia que será entregue ao
  adversário" (padrão de cadeia).

Aprender esses padrões seria muito mais difícil lendo a matriz crua `9×7×1`,
porque a rede teria primeiro que descobrir sozinha a regra de paridade antes
de começar a raciocinar estrategicamente.

### 2.4 Como o código concretamente implementa essa transformação

```python
def para_grid_de_caixas(x):
    x = tf.squeeze(x, axis=-1)                # (B, 9, 7)
    topo     = x[:, 0:8:2, 1:7:2]             # (B,4,3) traço H acima
    base     = x[:, 2:9:2, 1:7:2]             # (B,4,3) traço H abaixo
    esquerda = x[:, 1:8:2, 0:6:2]             # (B,4,3) traço V à esquerda
    direita  = x[:, 1:8:2, 2:7:2]             # (B,4,3) traço V à direita
    interior = x[:, 1:8:2, 1:7:2]             # (B,4,3) dono da caixa
    return tf.stack([topo, base, esquerda, direita, interior], axis=-1)
```

Pontos importantes sobre as operações utilizadas:

- `tf.squeeze(x, axis=-1)` remove a dimensão de canal vazia (o `1` do
  `(9, 7, 1)`), resultando em `(9, 7)` por amostra. Isso facilita as operações
  de fatiamento abaixo.
- `0:8:2` é a notação `[início:fim:passo]` do Python/NumPy e significa "pegue
  índices 0, 2, 4, 6" — as **linhas pares**, onde ficam os traços horizontais.
  São 4 linhas, o que gera o eixo de 4 caixas de altura.
- `1:7:2` pega "índices 1, 3, 5" — as colunas ímpares, onde ficam os traços
  horizontais. São 3, gerando o eixo de 3 caixas de largura.
- `x[:, 0:8:2, 1:7:2]` captura, em cada amostra, as 12 posições onde moram
  os traços horizontais do **topo** das caixas. Resultado: um tensor
  `(B, 4, 3)`.
- O mesmo padrão se repete para base (linhas 2, 4, 6, 8), esquerda (colunas
  0, 2, 4), direita (colunas 2, 4, 6) e interior.
- `tf.stack([...], axis=-1)` empilha esses cinco tensores `(B, 4, 3)` ao
  longo de um novo eixo no final, produzindo `(B, 4, 3, 5)`. Esse "5" é o
  eixo de canais, exatamente o que uma CNN espera consumir.

Uma observação relevante: como cada aresta fica entre duas caixas, o **mesmo
traço aparece em dois canais de duas caixas diferentes** — o traço da base da
caixa (0,0) é o mesmo que o traço do topo da caixa (1,0). Isso é redundância
intencional: cada caixa carrega seu perfil completo, simplificando o que a
rede precisa aprender.

---

## 3. Representações alternativas: `(9, 7, 2)` versus `(4, 3, 5)`

Uma representação alternativa plausível da entrada seria manter a grade
`9×7` e usar **dois canais**:

- **Canal 0 — arestas:** em posições linha-par/coluna-ímpar e
  linha-ímpar/coluna-par (traços H e V), recebe `1` se preenchido e `0` se
  vazio. Em todas as outras posições (pontos fixos e interiores de caixa),
  fica sempre em `0`.
- **Canal 1 — caixas:** em posições linha-ímpar/coluna-ímpar (interior de
  caixa), recebe `1` se fechada e `0` se aberta. Em todas as outras posições,
  fica sempre em `0`.

Essa representação **separa a semântica pelo canal em vez de separá-la pela
paridade da posição**. Visualmente é muito mais intuitiva: olhando o canal 0
vê-se exatamente onde há traço sem ambiguidade, e olhando o canal 1 vê-se
quais caixas foram fechadas.

A construção em NumPy seria algo como:

```python
canal_arestas = np.zeros_like(X_raw)
canal_caixas  = np.zeros_like(X_raw)

canal_arestas[:, 0::2, 1::2] = (X_raw[:, 0::2, 1::2] == 1)  # H
canal_arestas[:, 1::2, 0::2] = (X_raw[:, 1::2, 0::2] == 1)  # V
canal_caixas[:,  1::2, 1::2] = (X_raw[:, 1::2, 1::2] == 1)  # interior

X = np.stack([canal_arestas, canal_caixas], axis=-1)  # (N, 9, 7, 2)
```

### 3.1 Qual formato é melhor para a CNN?

A resposta curta: **`(4, 3, 5)` é melhor para a CNN; `(9, 7, 2)` é melhor para
um humano entender.** Existem três ângulos que sustentam essa afirmação.

**Ângulo 1 — Densidade de informação.** No formato `(9, 7, 2)`, o total de
posições é 63 × 2 = 126. Porém mais de 80% dessas posições são sempre zero
(no canal 0, os interiores e pontos fixos; no canal 1, tudo que não é
interior). No formato `(4, 3, 5)`, o total é 12 × 5 = 60 posições, e **todas
carregam informação tática útil**. A CNN, se treinada no formato `(9, 7, 2)`,
gastaria capacidade tentando aprender padrões sobre posições que são ruído
constante. No formato compacto, toda operação convolucional ocorre sobre bits
semanticamente relevantes.

**Ângulo 2 — O que o filtro 3×3 enxerga.** No formato `(9, 7, 2)`, cada
deslocamento do filtro 3×3 sobrevoa uma vizinhança heterogênea — pode conter
pontos fixos (ruído), traços e interiores de caixa misturados. O filtro
precisa primeiro aprender a "mascarar" as posições irrelevantes para a
decisão que está tomando. É aprendível, mas consome capacidade. No formato
`(4, 3, 5)`, cada deslocamento do filtro 3×3 sobrevoa uma vizinhança de
**3×3 caixas**, e em cada caixa já encontra os cinco atributos táticos
prontos. O filtro aprende padrões do tipo: "se a caixa central tem perfil
(1,1,1,0,0) e a caixa à direita tem perfil (_,_,0,_,_), então completar a
caixa central entrega a próxima ao adversário". Conceitualmente muito mais
direto.

**Ângulo 3 — Alinhamento com a estrutura do jogo.** Dots and Boxes é um jogo
cuja unidade atômica de decisão é a caixa — o objetivo é fechar suas próprias,
evitar entregar cadeias ao adversário, e assim por diante. Representar o
tabuleiro como uma grade **de caixas** (e não de arestas + caixas
misturadas) espelha essa estrutura. Quando a representação do dado espelha
a estrutura do problema, a rede aprende mais rápido e com menos parâmetros.
Este é um princípio geral de aprendizado de máquina chamado **inductive
bias** (viés indutivo): quanto mais a forma do dado já carrega a estrutura
certa, menos a rede precisa descobrir sozinha.

### 3.2 Por que isso não é uma decisão preto-e-branco

O formato `(9, 7, 2)` **também funcionaria**. Uma CNN com capacidade
suficiente e dados suficientes consegue aprender a partir das duas
representações. A diferença prática é:

- `(4, 3, 5)` treina mais rápido, precisa de menos parâmetros, encaixa melhor
  na tática do jogo. Downside: menos intuitivo para humanos depurarem.
- `(9, 7, 2)` é mais intuitivo para humanos, mapeia 1-para-1 com o tabuleiro
  visual. Downside: a rede gasta capacidade aprendendo a regra de paridade e
  a ignorar zeros.

Para o produto atual — tabuleiro pequeno com 12 caixas e dataset de 344 mil
exemplos — ambos funcionariam. A escolha do `(4, 3, 5)` foi deliberada para
extrair o máximo de sinal do dataset, e isso aparece no histórico de
experimentos: o salto do MLP flat para a BoxNet v1 com grid de caixas foi o
maior ganho registrado.

Manutenibilidade e clareza conceitual têm valor real. Se, no futuro, o
formato `(9, 7, 2)` for escolhido por razões didáticas, vale ser registrado
como experimento em `historico_decisoes.md`, medindo-se a performance antes
da troca.

---

## 4. Filtros em uma camada convolucional

### 4.1 O que é um filtro

Um **filtro** é um pequeno detector de padrão que a rede aprende sozinha. No
caso da primeira camada `Conv2D(32)` da BoxNet, cada filtro tem shape
`3×3×5` — três linhas, três colunas, cobrindo todos os cinco canais de
entrada. Isso corresponde a `3 × 3 × 5 = 45 pesos + 1 bias = 46 números` que
a rede vai ajustar por backpropagation durante o treino.

Esse filtro "desliza" pelo tensor de entrada `(4, 3, 5)`. Em cada posição de
parada, ele faz uma soma ponderada dos 45 valores cobertos pela janela,
aplica a função de ativação (ReLU, por exemplo), e produz **um único número**:
a "resposta" do filtro naquela posição.

Como a grade é 4×3, o filtro para em 12 posições (com padding "same" para
preservar o tamanho da grade). O resultado é uma grade 4×3 de respostas desse
filtro.

Pode-se pensar em cada filtro como uma **pergunta** que a rede faz em cada
caixa: "você se parece com este padrão que eu aprendi?" E o filtro responde
com um número — alto para "sim", baixo para "não".

### 4.2 Por que 32 filtros, e não um só

Um único filtro só consegue detectar um tipo de padrão. Dots and Boxes, em
contrapartida, tem dezenas de padrões táticos relevantes:

- Caixa com três arestas preenchidas (oportunidade imediata de fechamento).
- Caixa com duas arestas em formato "L" (segura, não entrega nada).
- Caixa com duas arestas paralelas (parte de cadeia).
- Par de caixas vizinhas, ambas com três arestas (sequência de capturas).
- Caixa vazia cercada por caixas semifechadas.
- ... e outros.

Ter **32 filtros** significa que a rede aprende **32 detectores de padrão
diferentes em paralelo**, cada um produzindo sua própria grade 4×3 de
respostas. Empilhando as 32 grades, o output dessa camada é um tensor
`(4, 3, 32)` — ou seja, **um tensor com 32 canais na saída**.

Aqui está a chave conceitual: **canais de entrada (5) ≠ canais de saída
(32)**. A camada convolucional é uma "fábrica de canais" — ela converte um
tensor com X canais semânticos crus em um tensor com Y canais de *features
aprendidas*.

### 4.3 A próxima camada continua o mesmo jogo

A segunda camada convolucional da BoxNet (no primeiro bloco residual mantém
32 canais, no segundo sobe para 48) lê o tensor `(4, 3, 32)`, passa seus
filtros — que agora têm shape `3×3×32`, cobrindo todos os 32 canais da etapa
anterior — e produz outro tensor `(4, 3, N)`, onde N é o número de filtros
dessa camada.

**Cada camada aprende padrões mais abstratos combinando os padrões da
anterior.** A primeira camada aprende micro-padrões (quantas arestas tem a
caixa? quais?); a segunda camada combina micro-padrões em táticas (há cadeia
curta à direita? há captura iminente?); uma terceira camada, se existisse,
combinaria táticas em estratégia (vale entregar a cadeia pequena para forçar o
adversário a abrir uma grande?).

### 4.4 Por que 32 filtros especificamente, e não outro número

A escolha de 32 filtros é um hiperparâmetro empírico — não há uma fórmula
fechada que o determine. Mas existem razões objetivas por trás dessa escolha
específica.

1. **Potência de 2.** `32 = 2⁵`. É tradição em deep learning: memória de GPU
   alinha melhor com potências de 2, e cálculos são ligeiramente mais
   rápidos. Valores comuns nessa faixa: 16, 32, 64, 128, 256. 32 é
   pequeno-médio.
2. **Proporção com o problema.** Como regra de bolso, o número de filtros da
   primeira camada costuma ficar entre 2x e 10x o número de canais de
   entrada. Com 5 canais de entrada, 32 filtros (~6x) é uma escolha razoável
   — capacidade suficiente para aprender padrões ricos sem explodir
   parâmetros.
3. **Escala do dataset.** 344 mil amostras é um dataset de porte médio. Mais
   filtros significam mais parâmetros, mais risco de overfit em datasets
   pequenos, e mais tempo de treino. 32 é um compromisso sensato.
4. **Tamanho do tabuleiro.** Com apenas 12 caixas, o espaço de padrões locais
   distintos é limitado. Não faz sentido ter 256 filtros varrendo uma grade
   de 12 células — seria capacidade desperdiçada.
5. **Histórico empírico.** A evolução BoxNet v1 → v2 → v3 provavelmente
   testou variantes, e 32 emergiu como baseline estável. Redes similares em
   outros jogos pequenos usam números próximos (16, 24, 32, 48).
6. **Progressão dentro da rede.** A arquitetura usa 32 na primeira camada e
   48 na segunda. Esse padrão "começa pequeno, vai aumentando" é comum: os
   primeiros filtros detectam coisas simples (não precisa de muitos), as
   camadas posteriores combinam em coisas complexas (precisam de mais). Isso
   é desenvolvido na seção 5.

Se o notebook fosse rodado com 16 filtros em vez de 32, provavelmente haveria
perda de alguns pontos em top-1 (menos capacidade). Se rodado com 128,
provavelmente não haveria ganho significativo (capacidade sobrando, risco de
overfit, treino mais lento). 32 é, portanto, uma escolha defensável mas não
sagrada — é um dial ajustável em experimentos futuros.

### 4.5 Analogia para amarrar o conceito

Pode-se imaginar a primeira camada `Conv2D(32)` como 32 "analistas táticos
independentes", cada um com uma especialidade diferente que a rede descobriu
sozinha durante o treino:

- O analista 1 "grita alto" quando vê uma caixa com três arestas.
- O analista 2 grita alto quando vê um canto do tabuleiro vazio.
- O analista 3 grita alto quando vê uma cadeia de duas caixas
  meio-abertas.
- ... e assim por diante até o analista 32.

Os 32 analistas olham **a mesma posição** em **paralelo** e cada um emite uma
opinião (um número). O resultado é que, para cada uma das 12 caixas, a rede
passa a ter **32 descritores aprendidos** daquela região do tabuleiro. Esse é
o tensor `(4, 3, 32)` que segue para a próxima camada.

---

## 5. Progressão de filtros em CNNs vs neurônios em MLPs

Uma pergunta natural de quem vem de redes densas (MLPs) é: "meu professor
ensinou que em MLP a gente reduz neurônios ao longo das camadas (128 → 64 →
32). Isso vale também para CNNs?" A resposta merece cuidado porque **o
padrão em CNNs é inverso** — e os dois padrões, MLP decrescente e CNN
crescente, são duas faces do mesmo princípio.

### 5.1 O padrão em MLPs: neurônios decrescentes

Em redes densas clássicas:

```
Entrada (784) → Dense(128) → Dense(64) → Dense(32) → Saída (10)
```

A lógica é que cada camada **condensa** informação. Começa-se com muitos
neurônios representando o input cru e "afunila-se" progressivamente até uma
representação compacta que alimenta a decisão final. Isso funciona em MLP
porque cada camada é totalmente conectada — todos os neurônios de uma camada
conversam com todos da anterior. Reduzir progressivamente força a rede a
selecionar features mais abstratas e descartar ruído.

### 5.2 O padrão em CNNs: filtros crescentes

Em CNNs a convenção é o oposto:

```
Entrada (224, 224, 3) → Conv(32) → Conv(64) → Conv(128) → Conv(256) → Dense(10)
```

E na BoxNet também, de forma mais modesta:

```
Entrada (4, 3, 5) → Conv(32) → Conv(48) → Dense(96) → Dense(31)
                        ↑         ↑
                    aumenta   (ainda pequeno, mas sobe)
```

Há duas razões que se reforçam para esse padrão crescente.

**Razão 1 — A grade espacial diminui, então os canais podem crescer sem
explodir parâmetros.** Em CNNs com pooling (o caso mais comum), a grade
espacial encolhe a cada camada:

```
Conv(32)  em grade 224×224 → tensor (224, 224, 32)  = 1.605.632 valores
Pool
Conv(64)  em grade 112×112 → tensor (112, 112, 64)  = 802.816 valores
Pool
Conv(128) em grade  56×56  → tensor  (56, 56, 128)  = 401.408 valores
```

Mesmo dobrando os filtros, o tensor total diminui porque a grade encolhe
quatro vezes a cada pooling. Dobrar canais compensa parcialmente essa perda
de resolução — a rede troca "extensão espacial" por "profundidade
semântica".

**Razão 2 — Hierarquia de abstração: poucas primitivas, muitas combinações.**
A primeira camada de uma CNN aprende primitivas **locais e simples**: bordas,
cantos, variações de intensidade. Essas primitivas são poucas e universais —
32 filtros já dão conta de cobrir o vocabulário básico. A segunda camada
**combina primitivas em padrões**: "borda vertical + borda horizontal
ligadas = canto", "múltiplos cantos = janela", e assim por diante. O número
de combinações possíveis cresce combinatorialmente, então a rede precisa de
mais filtros para representar esse espaço maior. A terceira camada combina
padrões em **conceitos**: "conjunto de janelas + telhado = fachada de casa".
Ainda mais combinações possíveis → ainda mais filtros.

Pode-se resumir assim: poucas letras (26) geram muitas palavras (~100 mil)
que geram muitíssimas frases (infinitas). A quantidade de coisas que
precisam ser representadas cresce conforme sobe o nível de abstração. Os
filtros seguem essa explosão combinatorial.

### 5.3 O princípio subjacente é o mesmo dos dois lados

Olhando com atenção, MLP e CNN dizem a mesma coisa, só que sobre eixos
diferentes:

| Arquitetura | O que **diminui** ao longo das camadas     | O que **aumenta** ao longo das camadas          |
|-------------|--------------------------------------------|-------------------------------------------------|
| MLP         | Número de neurônios (128 → 64 → 32)        | Nível de abstração das features                 |
| CNN         | Tamanho da grade espacial (224 → 112 → 56) | Número de canais (32 → 64 → 128) e abstração    |

Em ambos os casos, o volume de informação (total de ativações) tende a
diminuir ou estabilizar conforme se sobe na rede, e a abstração aumenta. A
diferença é onde cada arquitetura coloca seu "gargalo de compressão":

- MLP comprime via **menos neurônios**.
- CNN comprime via **grade espacial menor** (pooling), e ao mesmo tempo
  expande canais para capturar padrões mais complexos.

### 5.4 Aplicando o princípio à BoxNet

A BoxNet usa `Conv(32) → Conv(48)`. Segue o padrão crescente (32 → 48), só
que de forma suave. Por que não vai além (por exemplo, 32 → 64 → 128)?

Duas razões específicas do problema:

1. **A grade espacial começa minúscula.** A entrada tem apenas `(4, 3)` —
   12 posições. Não há pooling na rede, e nem faria sentido: com uma grade
   tão pequena, um pooling 2×2 a reduziria a `(2, 1)` ou `(1, 1)`. A grade
   então **não diminui** ao longo das camadas, e aumentar muito os canais
   faria o tensor ficar desnecessariamente grande em parâmetros, sem ganho
   de informação.
2. **O vocabulário tático do Dots and Boxes é limitado.** Há um número
   relativamente pequeno de padrões táticos distintos: "caixa com três
   arestas", "cadeia curta", "cadeia longa", "L-shape", "cadeia fechada em
   loop", e algumas outras variações. Talvez algumas dezenas de padrões
   relevantes. A rede não precisa de 256 filtros para representar esse
   vocabulário — 48 já cobre o espaço de combinações.

Por comparação: uma CNN clássica de visão como a ResNet50 sobe até 2048
canais na última camada convolucional. É porque o espaço de "partes de
objetos que existem no mundo visual" é gigantesco. O espaço de "padrões
táticos num tabuleiro 4×3" é modesto.

### 5.5 Seria válido testar o padrão "MLP" em CNN (decrescente)?

A intuição de "começar com mais filtros e reduzir" não é inválida — é um
padrão menos comum, mas existe na literatura (algumas arquiteturas
encoder-decoder fazem isso). Para a BoxNet, testar `Conv(64) → Conv(32)`
como experimento seria interessante e produziria um dado empírico útil.

Mas a aposta informada é que o experimento não traria ganho relevante. O
gargalo atual do modelo não parece ser capacidade da rede — 74 mil
parâmetros já é suficiente para um problema de 12 caixas — e sim qualidade
e composição do dataset: os 15% de amostras aleatórias ("random(p=0)"), o
`sample_weight` desligado e a escolha do professor Minimax profundidade 9
são alavancas mais prováveis. Ainda assim, vale registrar como tentativa em
`historico_decisoes.md` caso o experimento seja feito — resultado nulo
também é informação.

### 5.6 Resumo da diferença

- **MLP → neurônios decrescentes** (princípio: afunilar informação para
  decisão).
- **CNN → filtros crescentes + grade decrescente** (princípio: trocar
  extensão espacial por profundidade semântica, acompanhando a explosão
  combinatorial de padrões abstratos).
- **Os dois padrões são duas faces do mesmo princípio**: reduzir volume
  total de ativações enquanto aumenta abstração.
- **A BoxNet segue o padrão CNN** (32 → 48), de forma modesta porque a
  grade já começa minúscula e o vocabulário tático é limitado.

---

## 6. Batch size e a dimensão `B` dos tensores

Todo tensor que flui por uma rede Keras/TensorFlow tem a primeira dimensão
reservada para o **batch** — o lote de amostras que são processadas
simultaneamente. Essa é uma convenção rígida do framework: por isso os shapes
aparecem sempre como `(B, altura, largura, canais)` e nunca como
`(altura, largura, canais)` sozinho.

### 6.1 Por que existe mini-batch

Durante o treino, a rede não vê um único tabuleiro por vez. Ela recebe um
lote (tipicamente 32, 64, 128, 256 ou 512 tabuleiros) e executa:

- Forward pass de todos os tabuleiros em paralelo — operação massivamente
  acelerada por GPU, que é projetada para aplicar a mesma operação a
  muitos dados simultaneamente.
- Cálculo da loss **média** sobre o batch.
- Um único gradiente baseado nessa loss média, que atualiza os pesos uma
  vez por batch.

Esse procedimento chama-se **mini-batch stochastic gradient descent** e é a
base do treinamento moderno de redes neurais. Trade-offs entre as três
opções:

- **Batch size = 1 (SGD puro):** gradiente extremamente ruidoso a cada
  passo, treino instável, não aproveita paralelismo.
- **Batch size = dataset inteiro (full-batch):** gradiente "perfeito" mas
  cada passo demora muito, converge para o mesmo mínimo local toda vez
  (ruim para generalização).
- **Mini-batch (32–512):** ruído suficiente para escapar de mínimos
  locais ruins, suave o bastante para convergir, e aproveita GPU. Melhor
  dos dois mundos.

### 6.2 O que `B` vale ao longo do pipeline

O valor de `B` muda conforme o contexto:

- **Treino** (`model.fit(X_train, y_train, batch_size=256, ...)`):
  `B = 256` em cada passo.
- **Validação/teste** (`model.evaluate(...)`): `B` = batch size do evaluate
  (default 32), processando o conjunto inteiro em pedaços.
- **Inferência em produção** (app Flutter consultando a CNN via TFLite
  durante uma partida): `B = 1` — um único tabuleiro por vez. O shape
  fica `(1, 9, 7, 1)`.

Isso é coerente com o que declara o contrato de codificação, seção
`invariante_final_do_tensor_da_cnn`: `shape_esperado: "(1, altura_matriz,
largura_matriz, 1)"`. O contrato descreve o caso de inferência, onde `B = 1`.

### 6.3 Por que a Lambda `para_grid_de_caixas` funciona com `B` indefinido

O código da Lambda usa a notação:

```python
topo = x[:, 0:8:2, 1:7:2]
```

O primeiro `:` (dois pontos sozinhos) significa "seja lá qual for o tamanho
da dimensão batch, use todos os elementos". Isso torna a mesma função
agnóstica ao valor de `B`: funciona com batch 1 (inferência), 256 (treino),
32 (evaluate) — o código é o mesmo.

No `Input(shape=(9, 7, 1))` da BoxNet, o Keras automaticamente adiciona a
dimensão de batch como `None` (tamanho variável). Ao inspecionar o
`model.summary()`, o shape aparece como `(None, 9, 7, 1)` — esse `None` é
exatamente o `B`, com valor ainda indefinido porque depende de quem chamar
a rede.

### 6.4 Interação com Batch Normalization

O tamanho do batch interage com a camada `BatchNormalization` discutida na
seção 8 deste documento. A BN calcula estatísticas (média e variância) **por
canal, dentro do batch atual**. Se `B` for muito pequeno (por exemplo, 4),
essas estatísticas ficam ruidosas demais e prejudicam o treino. Regra
prática:

- **BN funciona bem com `B ≥ 16`**, com `B ≥ 32` sendo o alvo ideal.
- Em inferência (`B = 1`) a BN não usa estatísticas do batch — usa médias e
  variâncias acumuladas durante o treino via moving average. Por isso a
  predição de um tabuleiro isolado em produção continua válida.

---

## 7. Kernel 3×3, padding e receptive field

### 7.1 O que o padding "same" faz

A `Conv2D(32, (3, 3), padding='same', ...)` da BoxNet processa o tensor
`(B, 4, 3, 5)` usando kernels 3×3. À primeira vista, parece que um kernel
3×3 num grid 4×3 só caberia em poucas posições — mas o `padding='same'` muda
isso. O Keras adiciona uma moldura de zeros fictícios ao redor do grid para
que o kernel possa ser centrado em **cada uma das 12 posições do grid
original**, produzindo uma saída com o **mesmo tamanho espacial** da entrada.

Visualmente, o grid 4×3 com padding `'same'`:

```
       c-1   c0    c1    c2    c3
l-1   [ 0 ] [ 0 ] [ 0 ] [ 0 ] [ 0 ]   ← zeros fictícios
l0    [ 0 ] [C00] [C01] [C02] [ 0 ]
l1    [ 0 ] [C10] [C11] [C12] [ 0 ]
l2    [ 0 ] [C20] [C21] [C22] [ 0 ]
l3    [ 0 ] [C30] [C31] [C32] [ 0 ]
l4    [ 0 ] [ 0 ] [ 0 ] [ 0 ] [ 0 ]   ← zeros fictícios
```

O kernel 3×3, com `strides=1` (default), **se posiciona centrado em cada
caixa**, uma de cada vez. Cada caixa do grid original é o centro do kernel
exatamente uma vez na saída. Caixas do interior participam do cálculo de
várias posições de saída (até 9, quando são vizinhas de 9 caixas centrais),
mas isso é **receptive field**, não "contagem múltipla".

### 7.2 Uma intuição errada comum

Uma intuição natural de quem encontra o kernel 3×3 pela primeira vez é
imaginar que o kernel "passa duas vezes" pelo tabuleiro — uma nas 9 caixas
superiores, outra nas 9 inferiores, com sobreposição de 6 caixas no meio.
Essa intuição seria verdadeira se o código usasse:

- `padding='valid'` (sem zeros ao redor)
- `strides=3` (pula de 3 em 3)

Mas a BoxNet usa `padding='same'` e `strides=1` (default). Com esses
parâmetros, o kernel se **aplica em cada caixa**, não em blocos. O que muda
entre posições é quem é o vizinho — e quando o kernel está numa caixa da
borda, parte dos vizinhos são zeros fictícios do padding.

### 7.3 Receptive field: o que uma caixa "enxerga" depois de N camadas

**Receptive field** é o conceito central para decidir quantas camadas uma
CNN precisa ter. Ele responde à pergunta: "depois de `N` camadas
convolucionais, cada posição da saída final depende de quantas posições da
entrada original?"

Para kernel 3×3 com `stride=1` e `padding='same'`:

- Após **1** camada: receptive field efetivo 3×3 — cada posição "vê" 9 caixas
  ao redor (ou menos, nas bordas).
- Após **2** camadas: receptive field 5×5 — já cobre o grid 4×3 **inteiro**
  com folga.
- Após **3** camadas: 7×7.
- A regra geral: `rf = N · (k−1) + 1`, onde `N` é o número de camadas e `k`
  é o tamanho do kernel.

Como a BoxNet tem 3 camadas convolucionais (stem + 2 blocos residuais, cada
bloco com 2 SeparableConv), o receptive field efetivo é bem maior que o grid
— cada posição da saída final "sabe" do tabuleiro inteiro. Isso é desejável
para Dots and Boxes, jogo cuja estratégia é intrinsecamente **global**
(cadeias podem atravessar o tabuleiro).

### 7.4 Por que 3×3 e não 2×2

Uma pergunta pertinente, dado que o grid é pequeno, é se não caberia usar
kernel 2×2. Três razões pelas quais 3×3 é preferível:

**Razão 1 — Receptive field mais agressivo.** Com kernel 3×3, 2 camadas
cobrem o grid 4×3 inteiro. Com kernel 2×2, precisariam de ~4 camadas —
praticamente o dobro. Mais profundidade significa mais risco de vanishing
gradient, mais custo, mais overfit. Troca ruim para nosso problema.

**Razão 2 — Simetria preservada.** Um kernel 3×3 tem um **centro bem
definido** (posição `(1, 1)` do kernel). Ao deslizar com `padding='same'`,
fica claro "sobre qual caixa o kernel está centrado". Um kernel 2×2 **não
tem centro** — ele cobre 4 posições e precisa escolher arbitrariamente
qual delas é o "centro". Com `padding='same'`, isso introduz assimetria nas
bordas (padding adicionado à esquerda ≠ padding adicionado à direita),
quebrando a **equivariância à translação** — uma das propriedades mais
valiosas das CNNs.

**Razão 3 — Padrão canônico desde VGG.** O paper VGG (Simonyan & Zisserman,
2014) mostrou empiricamente que kernels 3×3 empilhados dominam kernels
maiores ou menores:

- Dois kernels 3×3 empilhados têm o mesmo receptive field que um kernel
  5×5, com 28% menos parâmetros.
- E introduzem duas não-linearidades ReLU intermediárias em vez de uma,
  aumentando a capacidade expressiva.

Desde então, praticamente toda CNN moderna (ResNet, MobileNet, EfficientNet,
ConvNeXt) usa kernels 3×3 em camadas convolucionais. Kernels 2×2 só
sobrevivem em **max pooling**, onde o objetivo é exatamente reduzir o
tamanho espacial pela metade. Em camadas `Conv2D`, 2×2 foi historicamente
abandonado.

### 7.5 Ressalva honesta para o TCC

É verdade que num grid 4×3 o kernel 3×3 ocupa fração enorme da entrada
(cobre 9 das 12 caixas). Em redes de imagens 224×224 um kernel 3×3 cobre
menos de 2% da área; aqui cobre 75%. Isso tem uma consequência **não
necessariamente ruim**: a rede aprende a processar o tabuleiro **como um
todo desde a primeira camada**. Não há hierarquia "padrões locais → médios
→ globais" como em ImageNet — é tudo global, o que é coerente com a
natureza do jogo. Para tabuleiros maiores (médio 5×4 com matriz 11×9, ou
grande 7×5 com matriz 15×11), o receptive field relativo muda e o
trade-off poderia ser diferente.

---

## 8. Batch Normalization, `use_bias=False` e ordem das operações

A primeira camada convolucional da BoxNet é seguida por três operações em
sequência:

```python
x = layers.Conv2D(32, (3, 3), padding='same', use_bias=False,
                  kernel_regularizer=regularizers.l2(L2))(x)
x = layers.BatchNormalization()(x)
x = layers.Activation('relu')(x)
```

Esse trio `Conv → BN → ReLU` é tão comum em arquiteturas modernas que
ganhou apelido: **"stem"** (tronco). Esta seção abre cada peça.

### 8.1 O problema que a Batch Normalization resolve

Durante o treino, cada camada da rede recebe ativações da camada anterior.
Conforme os pesos são atualizados, **a distribuição dessas ativações muda
constantemente**: em uma época o layer pode receber valores na faixa
`[-2, 2]`, na seguinte `[-10, 15]`, na seguinte `[0.1, 0.3]`. Esse
fenômeno foi batizado na literatura como ***internal covariate shift***.

O efeito prático é que as camadas seguintes precisam **perseguir um alvo
em movimento** — toda vez que os pesos das camadas anteriores mudam, elas
precisam se ajustar à nova faixa de valores. Isso torna o treino:

- **Lento** — a taxa de aprendizado precisa ser pequena para não divergir.
- **Sensível à inicialização** — pesos iniciais ruins podem impedir
  convergência.
- **Difícil de empilhar muitas camadas** — o problema cresce com a
  profundidade.

### 8.2 O que a Batch Normalization faz

Para cada mini-batch durante o treino, a camada BN:

1. Calcula a **média μ** e a **variância σ²** das ativações do batch,
   **por canal** — num tensor com 32 canais, ela calcula 32 pares de
   `(μ, σ²)`.
2. **Normaliza** cada ativação: `x̂ = (x − μ) / √(σ² + ε)`. Após este
   passo, cada canal tem média 0 e variância 1 dentro do batch.
3. **Reescala e desloca** com dois parâmetros treináveis por canal:
   `y = γ · x̂ + β`. O `γ` (gamma) e o `β` (beta) permitem que a rede
   "desfaça" a normalização se precisar, mas agora sob controle do
   gradiente.

Em inferência (predição em produção), a BN usa médias e variâncias
acumuladas durante o treino via moving average, **não** as do batch atual
— senão a predição dependeria do que mais está no batch, o que seria
absurdo.

### 8.3 Benefícios mensuráveis

- **Permite learning rates maiores** — pode-se usar Adam com `lr=1e-3` sem
  divergir (como faz a BoxNet), em vez de `lr=1e-4`. Treino 3–10× mais
  rápido.
- **Regulariza levemente** — o ruído introduzido pelas estatísticas do
  mini-batch funciona como uma forma fraca de dropout.
- **Reduz dependência da inicialização** — a rede "repara"
  automaticamente distribuições ruins.
- **Permite empilhar camadas profundas** — ResNet-50 sem BN praticamente
  não treina.

### 8.4 Detalhe que vale para o TCC

Em 2018, um paper influente (Santurkar et al., *How Does Batch
Normalization Help Optimization?*) mostrou que a explicação original de
Ioffe & Szegedy (2015) sobre *internal covariate shift* **estava
parcialmente errada**. O que a BN realmente faz, segundo o paper
posterior, é **suavizar a paisagem da loss** (o *landscape* dos
gradientes), tornando o treino mais previsível. Essa discussão rende um
parágrafo interessante no TCC sobre como a prática de ML muitas vezes
precede a compreensão teórica.

### 8.5 Por que `use_bias=False`

O argumento `use_bias=False` aparece em todas as convoluções da BoxNet que
são seguidas por `BatchNormalization`. A razão é simples: a BN subtrai a
média e adiciona um `β` treinável — e o `β` **já faz o papel do bias**.
Manter os dois é redundante, cria duas variáveis aprendendo a mesma coisa,
e pode dificultar a otimização.

Regra prática de arquiteturas modernas: **toda Conv2D ou Dense seguida por
BN deve ter `use_bias=False`**.

### 8.6 Ordem `Conv → BN → ReLU` vs `Conv → ReLU → BN`

A ordem usada na BoxNet — `Conv → BN → ReLU` — é o padrão "pós-ativação"
clássico, adotado no paper original do BN e na maioria das arquiteturas
modernas (Keras default). Existe uma variante chamada **"pré-ativação"**
(`BN → ReLU → Conv`, proposta por He et al., 2016 no ResNet v2) que em
redes muito profundas (50+ camadas) performa ligeiramente melhor. Para
redes rasas como a BoxNet (3 camadas convolucionais), a diferença
prática é desprezível — vale registrar como trade-off consciente no TCC.

### 8.7 Inconsistência a corrigir no futuro

A BoxNet v3 aplica a ordem canônica `Conv → BN → ReLU` nos blocos
convolucionais, mas na **Dense final** usa uma ordem um pouco diferente:
`Dense(activation='relu') → BN → Dropout`. Isso coloca a ReLU **antes** da
BN, o que tecnicamente viola o princípio "BN normaliza saídas lineares
antes da ativação". Empiricamente a diferença é pequena (< 1% de accuracy
em redes pequenas), mas para consistência seria preferível:

```python
h = layers.Dense(96, use_bias=False, kernel_regularizer=regularizers.l2(L2))(h)
h = layers.BatchNormalization()(h)
h = layers.Activation('relu')(h)
h = layers.Dropout(0.5)(h)
```

Essa troca é candidata a experimento futuro, a registrar em
`historico_decisoes.md`.

### 8.8 Parâmetros treináveis da BN

Para um tensor com `C` canais, a BN treina `2C` parâmetros (`γ` e `β` por
canal). Na BoxNet, a BN que segue o stem tem `2 × 32 = 64` parâmetros
treináveis. Além disso, ela mantém `2C` estatísticas **não-treináveis**
(média e variância acumuladas via moving average) que são atualizadas
durante o treino mas não participam do gradiente.

---

## 9. Blocos residuais e skip connections

A BoxNet v3 empilha dois blocos definidos pela função
`bloco_residual_separavel`. Estruturalmente, cada bloco tem o seguinte
formato:

```
                 ┌──────────────── atalho ────────────────┐
                 │                                        │
  entrada ──────┼──► SepConv → BN → ReLU → Dropout ─┐    │
                                                    │    ▼
                                                    └──► Add ──► ReLU ──► saída
                 SepConv → BN ──────────────────────┘
```

A saída do bloco é `ReLU(F(x) + x)`, onde `F(x)` é o que as duas
SeparableConv2D calculam — o **resíduo** (daí o nome).

### 9.1 O problema histórico que motivou a criação do bloco residual

Antes de 2015, a regra era "mais profundo é melhor": 8 camadas (AlexNet,
2012), 16–19 camadas (VGG, 2014). Mas pesquisadores notaram algo
perturbador: redes com 30, 50, 100 camadas treinavam **pior** que redes
com 20 camadas. Não era overfitting (o erro de treino também piorava) —
era um problema de otimização puro.

A causa: o **vanishing gradient**. Durante o backward pass, o gradiente se
propaga das camadas finais para as iniciais multiplicando-se por
derivadas de ativação a cada camada. Quando se empilham 50 camadas, o
gradiente efetivo nas primeiras camadas vira algo como `0.9⁵⁰ ≈ 0.005` —
praticamente zero. As primeiras camadas paravam de aprender e a rede
inteira ficava ruim.

**ResNet (He et al., 2015)** resolveu com uma ideia de uma linha: cada
bloco de camadas aprende um **resíduo** (uma correção sobre a entrada) em
vez de aprender a representação inteira do zero.

- Representação tradicional: `y = H(x)` (a camada aprende a função H
  inteira).
- Representação residual: `y = F(x) + x` (a camada aprende só a
  **diferença** F que precisa adicionar a x).

### 9.2 Por que funciona

Dois efeitos combinados:

1. **Gradiente tem caminho "limpo" para trás.** Na soma `F(x) + x`, o
   gradiente se propaga pela parte `x` **sem ser multiplicado por nada**.
   Ele passa intacto pelas camadas. O vanishing gradient é eliminado.
2. **Aprender identidade é barato.** Se um bloco residual não tiver nada
   útil para adicionar, ele aprende `F(x) ≈ 0` e a saída vira
   aproximadamente a própria entrada. Isso é fácil (basta zerar os pesos
   da SepConv). Em uma rede tradicional, aprender identidade é difícil
   (a rede teria que aprender pesos que reproduzem a entrada exatamente).
   Ou seja: **se um bloco residual não ajuda, custa pouco; se ajuda,
   aproveita**.

Após o ResNet, praticamente toda CNN moderna (EfficientNet, MobileNet v2+,
ConvNeXt, RegNet) usa conexões residuais. É uma das ideias mais
importantes de deep learning pós-2010, ao lado de Batch Normalization,
Adam, atenção/Transformer, e dropout.

### 9.3 Por que usar residual numa rede tão rasa?

Uma crítica legítima à BoxNet é: a motivação original do ResNet era
permitir redes **profundíssimas** — 50, 101, 152 camadas. A BoxNet tem
apenas 3 camadas convolucionais. O vanishing gradient não é um risco real.

Então por que usar residual aqui?

1. **Atalho de informação.** Mesmo em redes rasas, permitir que a rede
   escolha entre "usar a representação bruta" (atalho) ou "usar a
   representação transformada" (F(x)) dá mais flexibilidade — um filtro
   que quer preservar informação estrutural sobre caixas fechadas, por
   exemplo, pode fazê-lo sem passar por mais convoluções que podem diluí-la.
2. **Treino mais estável.** Mesmo sem risco catastrófico de vanishing, o
   treino com skip connections é empiricamente mais estável: curvas de
   loss menos ruidosas, menos sensível a learning rate, converge mais
   rápido.
3. **Custo quase zero.** A operação `Add` tem 0 parâmetros treináveis.
   A única exceção é quando o número de canais muda (caso do bloco 2 da
   BoxNet: entrada com 32 canais, saída com 48), aí precisa-se de uma
   projeção 1×1 (detalhada na seção 9.5).

**Honestidade para o TCC:** para uma rede de 3 blocos, treinar sem
residual produziria performance próxima. As skip connections estão aqui
mais por "higiene arquitetural" (seguir o padrão moderno) do que por
necessidade absoluta. É uma decisão conservadora e defensiva — vale
mencionar isso explicitamente.

### 9.4 A operação `Add`

`Add()([y, atalho])` é a operação mais simples da rede: soma
elemento-a-elemento de dois tensores com o mesmo shape. Se `y` tem shape
`(B, 4, 3, 32)` e `atalho` tem shape `(B, 4, 3, 32)`, `Add` produz
`(B, 4, 3, 32)` onde cada elemento é a soma dos correspondentes. Zero
parâmetros treináveis. Toda a riqueza conceitual do bloco residual vem do
**caminho de conexão**, não da operação de soma em si.

### 9.5 Quando o número de canais muda: projeção 1×1

No bloco 1 da BoxNet (32 → 32 canais), o atalho é usado diretamente —
entrada e saída têm o mesmo shape, `Add` funciona sem ajustes.

No bloco 2 (32 → 48 canais), há um problema geométrico:

- `y` (após as duas SepConv): shape `(B, 4, 3, 48)`.
- `atalho` (entrada direta): shape `(B, 4, 3, 32)`.

Tensores com shapes diferentes não podem ser somados. O código entra no
`if atalho.shape[-1] != filtros:` e aplica uma **convolução 1×1** para
projetar o atalho para 48 canais:

```python
atalho = layers.Conv2D(filtros, (1, 1), padding='same', use_bias=False,
                       kernel_regularizer=regularizers.l2(l2))(atalho)
atalho = layers.BatchNormalization()(atalho)
```

A conv 1×1 é conceitualmente uma "camada Dense viajando pelo grid" — para
cada posição `(i, j)`, ela calcula uma combinação linear dos 32 canais de
entrada produzindo 48 canais de saída. **Não processa espaço** (kernel de
1 pixel). Parâmetros: `1 · 1 · 32 · 48 = 1 536` — muito baratos.

Dois usos clássicos de convoluções 1×1 na literatura:

1. **"Bottleneck"** para reduzir canais antes de uma conv 3×3 cara, depois
   expandir de volta. Muito usado em ResNet-50+, Inception, MobileNet.
2. **"Projection shortcut"** — o caso da BoxNet: alinhar o número de
   canais do atalho com a saída do bloco quando eles divergem.

A BN após a conv 1×1 é por simetria: a saída `y` do bloco passou por BN
duas vezes (uma após cada SepConv); se o atalho não passasse por nenhuma
BN, os dois tensores somados estariam em escalas diferentes e a soma
ficaria dominada pelo de maior magnitude. A BN no atalho coloca ambos na
mesma escala.

### 9.6 Por que o salto 32 → 48 e não 32 → 64

A regra canônica de CNNs de imagem é **dobrar canais a cada bloco**: 32 →
64 → 128 → 256. A BoxNet não dobra. Por quê?

1. **Grid pequeno, capacidade limitada.** Num grid 4×3 com 12 posições,
   um tensor `(B, 4, 3, 64)` tem 768 valores por amostra. Comparado com
   `(B, 4, 3, 48) = 576`, a diferença não é grande, mas os parâmetros da
   SepConv subiriam consideravelmente — sem ganho claro de expressividade
   em um problema tão compacto.
2. **Orçamento total de parâmetros.** Dobrar de 32 para 64 empurraria a
   rede para ~110k–130k parâmetros, aumentando o risco de overfit sem
   benefício mensurável.

48 é um meio-termo pragmático, calibrado para o tamanho do problema. Não é
um número mágico — 40, 56 ou 64 provavelmente produziriam resultados
similares.

---

## 10. SeparableConv2D: convolução separável em profundidade

### 10.1 O problema: Conv2D tradicional é custoso

A primeira Conv2D dentro do bloco residual 1 da BoxNet recebe um tensor
`(B, 4, 3, 32)` e deveria produzir `(B, 4, 3, 32)` com filtros 3×3. Uma
Conv2D "normal" teria:

- 32 filtros, cada um shape `(3, 3, 32)`.
- Parâmetros: `3 · 3 · 32 · 32 = 9 216`.

O problema fundamental: numa Conv2D normal, **cada filtro mistura espaço e
canais ao mesmo tempo**. Processa um padrão 3×3 *e* combina os 32 canais
na mesma operação. Isso custa muitos parâmetros para fazer duas coisas
juntas.

### 10.2 A ideia: separar as duas operações

A convolução separável (introduzida em 2017 nos papers **Xception** de
Chollet e **MobileNet** de Howard et al.) faz a mesma coisa em duas
etapas:

**Etapa 1 — Depthwise convolution:** um kernel 3×3 **por canal de entrada**,
independentemente. 32 canais → 32 kernels 3×3. Cada kernel processa
**apenas o seu canal** — não mistura com os outros. Produz 32 mapas de
ativação 4×3.

**Etapa 2 — Pointwise convolution:** uma convolução 1×1 com 32 filtros
(os "filtros de saída"). Cada filtro 1×1 tem shape `(1, 1, 32)` e
**combina os 32 canais** do depthwise, produzindo **1 canal de saída**.
32 filtros → 32 canais de saída.

```
Entrada (4, 3, 32)
       │
       ▼
  ┌──────────┐   32 kernels 3×3 (um por canal)
  │Depthwise │   Cada kernel processa só seu canal.
  │  3×3     │   Não mistura canais. Captura
  └──────────┘   padrões espaciais.
       │
       ▼
Intermediário (4, 3, 32)
       │
       ▼
  ┌──────────┐   32 kernels 1×1 (cada um vê 32 canais)
  │Pointwise │   Mistura canais. Não processa
  │  1×1     │   espaço (kernel de 1 pixel).
  └──────────┘   Produz 32 canais de saída.
       │
       ▼
Saída (4, 3, 32)
```

### 10.3 Economia de parâmetros

Para a mesma transformação `(4, 3, 32) → (4, 3, 32)` com kernel 3×3:

| Camada | Parâmetros |
|---|---|
| **Conv2D normal** | `3·3·32·32 = 9 216` |
| **SeparableConv2D** | `3·3·32 + 1·1·32·32 = 288 + 1 024 = 1 312` |

**~7× menos parâmetros** para aproximadamente a mesma transformação. Em
redes grandes (MobileNet com centenas de camadas) isso significa 10× menos
parâmetros totais, modelos que cabem em 4 MB em vez de 40 MB, e inferência
5–10× mais rápida em celular.

### 10.4 Por que funciona

A intuição é que **padrões espaciais são relativamente independentes de
padrões de canal**. Um filtro que detecta "aresta horizontal" em imagens
RGB não precisa de versões especializadas para "aresta horizontal no
vermelho" vs "aresta horizontal no verde" — a detecção espacial é a
mesma, só o uso posterior dos canais diferencia. Separar as duas operações
permite aprender cada uma com menos redundância.

Isso é conhecido na literatura como **hipótese de fatoração**
(*factorization hypothesis*): assumir que a operação pode ser fatorada sem
perda apreciável de expressividade. Para imagens naturais, a hipótese se
verifica empiricamente — SeparableConv atinge precisão comparável a Conv
normal em muitos problemas.

### 10.5 Faz sentido na BoxNet?

Sim, com ressalvas honestas:

1. **Economia de parâmetros é boa para nosso problema.** Com ~74k
   parâmetros totais e um dataset de algumas centenas de milhares de
   amostras, cada parâmetro "a mais" é risco adicional de overfit. Trocar
   os 4 convs dos blocos residuais por SepConv economiza ~20k parâmetros.
2. **Grid 4×3 é pequeno — hipótese de fatoração é forte.** Em imagens
   224×224, o espaço de padrões espaciais é rico. Em 4×3, é quase trivial
   — SepConv praticamente não perde nada.
3. **Ressalva:** os 5 canais de entrada da BoxNet (topo, base, esquerda,
   direita, interior) **não são intercambiáveis** como R, G, B. Eles têm
   significado geométrico fixo. Em tese, isso poderia tornar a fatoração
   canal/espaço ligeiramente menos eficiente — a rede poderia querer um
   filtro que processa "topo" de um jeito e "interior" de outro. Com 32
   ou 48 filtros e pointwise que mistura canais, isso se resolve na
   prática, mas vale o registro no TCC.

### 10.6 Regularização separada

Note que a SeparableConv2D da BoxNet aplica L2 em **dois conjuntos
separados** de pesos:

```python
layers.SeparableConv2D(
    filtros, (3, 3), padding='same', use_bias=False,
    depthwise_regularizer=regularizers.l2(l2),
    pointwise_regularizer=regularizers.l2(l2),
)
```

Os kernels depthwise e pointwise são **conceitualmente distintos** —
depthwise aprende padrões espaciais, pointwise aprende combinações de
canais. Regularizá-los separadamente permite, se necessário, ajustar cada
um de forma independente (experimento futuro).

---

## 11. SpatialDropout2D vs Dropout clássico

A BoxNet usa duas variantes de dropout em lugares diferentes:

- **`SpatialDropout2D`** dentro dos blocos residuais (após a primeira
  SepConv de cada bloco), com taxas 0.15 e 0.20.
- **`Dropout`** clássico após a Dense(96), com taxa 0.5.

A distinção entre as duas variantes não é cosmética — é estrutural.

### 11.1 Dropout clássico: zera neurônios individuais

Durante o treino, **cada neurônio individual** da camada é zerado com
probabilidade `p`. Obriga a rede a não depender de nenhum neurônio
específico — é um "seguro de redundância". Foi desenhado para camadas
totalmente conectadas (Dense), onde cada neurônio representa uma feature
independente. Zerar um neurônio remove uma feature — faz sentido.

### 11.2 SpatialDropout2D: zera canais inteiros

Durante o treino, **canais inteiros** do mapa de ativação são zerados com
probabilidade `p`. Num tensor `(B, 4, 3, 32)` com `p=0.15`, ~5 canais
inteiros são zerados (todos os 12 valores espaciais daquele canal viram
0), enquanto os outros 27 ficam intocados.

### 11.3 Por que Dropout clássico falha em camadas convolucionais

Em camadas convolucionais, pixels adjacentes num mesmo mapa de ativação
são **altamente correlacionados** — são produtos de um mesmo filtro
aplicado em posições próximas. Se o filtro detecta "cadeia horizontal",
pixels vizinhos no mapa vão ter valores parecidos.

O problema: com dropout clássico em um tensor `(B, 4, 3, 32)` e `p=0.15`,
zeram-se ~58 pixels individuais espalhados pelo tensor. Mas como pixels
adjacentes são correlacionados, a rede aprende a **"preencher os buracos"**
usando os vizinhos do mesmo canal. O efeito regularizador é muito menor
que o esperado — dropout clássico em conv é quase ruído cosmético.

**SpatialDropout2D resolve:** zerando canais inteiros, remove **features
inteiras**. Se o canal "detector de cadeia horizontal" vira 0 em todas as
posições, não há como pixels vizinhos compensarem — a feature sumiu. A
rede é forçada a aprender features redundantes distribuídas entre canais.

### 11.4 Representação visual

**Dropout clássico** em tensor `(4, 3, 32)` com `p=0.15`:

```
Canal 0:   [X ✓ ✓]     Canal 1:   [✓ X ✓]     Canal 2:   [✓ ✓ X]     ...
           [✓ ✓ X]                [✓ ✓ ✓]                [✓ X ✓]
           [✓ X ✓]                [X ✓ ✓]                [✓ ✓ ✓]
           [✓ ✓ ✓]                [✓ ✓ X]                [X ✓ ✓]
```

**SpatialDropout2D** no mesmo tensor com `p=0.15`:

```
Canal 0:   [✓ ✓ ✓]     Canal 1:   [X X X]     Canal 2:   [✓ ✓ ✓]     ...
           [✓ ✓ ✓]                [X X X]                [✓ ✓ ✓]
           [✓ ✓ ✓]                [X X X]                [✓ ✓ ✓]
           [✓ ✓ ✓]                [X X X]                [✓ ✓ ✓]
```

Canal 1 inteiro foi apagado; canais 0 e 2 intactos.

### 11.5 Por que taxas diferentes em lugares diferentes

As taxas usadas na BoxNet seguem padrões empíricos bem estabelecidos:

- **SpatialDropout em camadas conv: 0.10–0.25.** Zerar canais é muito mais
  disruptivo que zerar pixels, então a mesma "pressão regularizadora" se
  consegue com taxa menor. A BoxNet usa 0.15 no primeiro bloco e 0.20 no
  segundo — progressão "mais regularização nas camadas mais profundas", que
  é o padrão moderno (essas camadas têm mais capacidade e mais risco de
  overfit).
- **Dropout clássico em Dense: 0.3–0.5.** Na BoxNet a Dense(96) é **a
  camada de maior capacidade** da rede (~80% dos parâmetros treináveis),
  então recebe a taxa mais agressiva (0.5), exatamente como recomendado no
  paper original do dropout (Srivastava et al., 2014).

### 11.6 Ordem `BN → Dropout` (e não o contrário)

Existe debate na literatura: `BN → Dropout` ou `Dropout → BN`? O paper
"Understanding the Disharmony between Dropout and Batch Normalization"
(Li et al., 2019) mostra que **Dropout antes de BN pode causar problemas
sutis em inferência**, porque as estatísticas da BN são calculadas com o
ruído do dropout, e em inferência (sem dropout) a distribuição efetiva
muda.

A BoxNet aplica `BN → Dropout`, que é a ordem recomendada pela literatura
recente e evita esse problema. Ponto para a arquitetura.

---

## 12. Cabeça de classificação: GAP, Flatten e o truque do Concatenate

Depois dos dois blocos residuais, o tensor está em `(B, 4, 3, 48)`. Ele
contém 48 mapas de ativação com 12 valores espacialmente organizados cada.
Essa é uma representação **espacial bidimensional**. A saída da rede
precisa ser um vetor de 31 probabilidades (uma por jogada possível). A
parte da rede responsável por essa transição se chama **cabeça de
classificação** (*classifier head*).

A BoxNet usa uma escolha arquitetural interessante:

```python
gap  = layers.GlobalAveragePooling2D()(x)
flat = layers.Flatten()(x)
h    = layers.Concatenate()([gap, flat])
```

### 12.1 `Flatten`: retrato fiel, posição por posição

`Flatten` pega o tensor multidimensional e "desenrola" em um único vetor
longo, preservando **todos** os valores individualmente. Para
`(B, 4, 3, 48)`, produz `(B, 576)` — `4 · 3 · 48 = 576` valores por
amostra.

**O que Flatten preserva:**

- **Informação posicional completa.** Cada valor do vetor "sabe" de qual
  caixa do tabuleiro veio (posição 0–575 do vetor corresponde a uma
  combinação única linha × coluna × canal).
- **Toda a ativação**, sem compressão.

**Limitações:**

- **Não reduz dimensionalidade.** A matriz de pesos da Dense seguinte fica
  grande: `576 × 96 = 55 296 parâmetros`. Isso é ~75% dos parâmetros
  totais da rede em uma única camada — **o maior risco de overfit** na
  arquitetura.
- **Não é translation-invariante.** Um padrão no canto superior esquerdo
  produz pesos diferentes de um padrão idêntico no canto inferior direito.

### 12.2 GlobalAveragePooling2D: resumo compacto, canal por canal

`GlobalAveragePooling2D` (GAP) faz o oposto: para cada canal, calcula a
**média de todos os valores espaciais** daquele canal e produz um único
número. Para `(B, 4, 3, 48)`, produz `(B, 48)` — 12× mais compacto que
Flatten.

**O que GAP preserva:**

- **Presença de features.** Se o canal 3 é "detector de caixa com 3 lados
  fechados", um valor alto em `gap_3` significa "esse padrão aparece
  bastante em algum lugar do tabuleiro", independentemente **de onde**.
- **Compressão agressiva.** De 576 valores para 48.

**Limitações:**

- **Não preserva informação posicional.** Depois do GAP, a rede não
  consegue distinguir "caixa com 3 lados no canto" de "caixa com 3 lados no
  meio".
- **Dilui ativações localizadas.** Se apenas uma posição tem valor alto e
  as outras 11 são zero, a média fica baixa (dividida por 12).

### 12.3 Histórico: por que GAP foi inventado

Flatten + Dense é a abordagem **clássica**: AlexNet (2012), VGG (2014) e
quase toda CNN pré-2015 usam isso. O problema: a matriz da primeira Dense
(que em VGG tinha `25088 × 4096 = 100 milhões de parâmetros`) era **o
maior contribuinte para overfit** em CNNs.

**GAP foi introduzido** pelo paper "Network in Network" (Lin et al., 2013)
e popularizado por GoogLeNet/Inception (2014) e ResNet (2015). A ideia: se
os últimos mapas convolucionais já capturam o que importa, basta tirar a
média por canal — nenhum parâmetro adicional, nenhum overfit,
translation-invariante de graça.

Desde então, praticamente toda CNN moderna de visão usa GAP ou variante.

### 12.4 O truque do Concatenate

Aqui a BoxNet faz algo **não-convencional**: em vez de escolher entre GAP
ou Flatten, usa **os dois** e concatena lado a lado, produzindo um vetor
de 624 valores (48 + 576).

A motivação vem diretamente do domínio Dots and Boxes, que precisa dos
**dois tipos de informação**:

**Flatten captura o que é posicional:**

- "A caixa no canto superior direito tem 3 lados fechados." — essencial,
  porque a rede precisa escolher uma jogada específica (rótulo tipo
  `H_0_5` ou `V_1_4`), e para isso precisa saber **em qual caixa** o
  padrão está.
- Qualquer padrão que envolva **onde** no tabuleiro algo está acontecendo.

**GAP captura o que é global:**

- "Existe pelo menos uma cadeia longa em algum lugar do tabuleiro." —
  sinal estratégico que indica "essa posição é perigosa".
- "Quantas caixas no total têm 2 lados fechados?" — contagem agregada,
  independente de onde estão.
- Features **invariantes a translação** — padrões que valem em qualquer
  canto.

Usando só Flatten, a rede teria que gastar capacidade redescobrindo
features agregadas a partir da informação posicional. Usando só GAP,
perderia a capacidade de escolher corretamente um rótulo posicional.
Concatenando, a Dense seguinte pondera cada sabor conforme a necessidade.

### 12.5 Custo do Concatenate

Sem o GAP, a Dense(96) teria `576 × 96 = 55 296` parâmetros. Com o GAP
concatenado, a matriz vira `624 × 96 = 59 904` — apenas 4 608 parâmetros a
mais (~6% do total da rede). Custo pequeno para um ganho conceitual claro.

### 12.6 É uma ideia comum?

**Não.** A grande maioria das CNNs usa OU Flatten OU GAP, não os dois
concatenados. Essa escolha do BoxNet v3 é **deliberada e justificada pelo
domínio**, não um padrão seguido cegamente. Vale como ponto de discussão
no TCC: "a arquitetura incorpora a natureza dupla da decisão no Dots and
Boxes — onde (posicional) e o que (presença/contexto global)."

Arquiteturas similares existem. O padrão **"Concat Pooling"**, popular em
NLP (Howard & Ruder, 2018, ULMFiT), concatena
`[max_pool, mean_pool, last_hidden]` pela mesma razão: múltiplas "visões"
do mesmo tensor para a camada de classificação.

### 12.7 Diagrama do caminho

```
      tensor (B, 4, 3, 48)  ← saída do bloco residual 2
            │
            ├──────────────┬───────────────┐
            │              │               │
            ▼              ▼               │
        GAP              Flatten           │
        (B, 48)         (B, 576)           │
            │              │               │
            └────► Concatenate ◄───────────┘
                     (B, 624)
                        │
                   (segue para a Dense)
```

---

## 13. Softmax, saída da rede e mascaramento em inferência

A camada final da BoxNet é:

```python
outputs = layers.Dense(num_classes, activation='softmax',
                       kernel_regularizer=regularizers.l2(L2),
                       name='jogada')(h)
```

É uma Dense com 31 neurônios (um por jogada possível no tabuleiro pequeno)
e ativação **softmax**.

### 13.1 O que softmax faz

Para um vetor de entrada `z = [z_1, z_2, ..., z_31]` (chamados "logits"),
softmax produz:

```
softmax(z_i) = exp(z_i) / Σ exp(z_j)
```

O vetor de saída tem três propriedades:

1. Todos os valores em `[0, 1]` — são probabilidades válidas.
2. A soma total é 1 — é uma distribuição de probabilidade válida.
3. Valores maiores dominam **exponencialmente** — a jogada com maior
   logit recebe uma probabilidade muito maior que as outras, não só um
   pouco maior.

### 13.2 Conexão elegante com o treino KL Divergence

Esse é um ponto elegante da arquitetura. Na seção 1.3 do notebook, o
código gera **soft targets** aplicando softmax sobre os Q-values do
Minimax. A saída da rede também é softmax. A loss `KLDivergence` mede a
distância entre **duas distribuições softmax**.

Em outras palavras: o treino é literalmente "converta seus Q-values
internos em uma distribuição softmax que bata com a softmax do Minimax".
É uma arquitetura desenhada sob medida para **knowledge distillation** —
um professor (Minimax) ensinando um aluno (rede) via distribuições de
probabilidade.

### 13.3 Mascaramento de jogadas inválidas acontece DEPOIS

Ponto importante para entender o pipeline de inferência: a rede produz
probabilidades para **todas as 31 jogadas**, inclusive as que são
**inválidas** no tabuleiro atual (arestas já preenchidas). A rede não sabe
quais estão disponíveis — apenas emite uma distribuição global.

Em inferência (simulador Pygame, avaliador, app Flutter), **o código
consumidor é responsável por mascarar** jogadas inválidas antes de
escolher o `argmax`:

```python
probs = model.predict(tabuleiro)[0]        # 31 probabilidades
probs[jogadas_ja_preenchidas] = 0          # zera inválidas
jogada_escolhida = probs.argmax()          # escolhe a melhor válida
```

Isso não é limitação de arquitetura — é separação de responsabilidades: a
**rede propõe**, o **código dispõe**. A rede se mantém agnóstica ao
tabuleiro específico e o código de jogo aplica as regras.

---

## 14. Resumo da topologia da BoxNet v3

Para fechar o panorama, segue uma tabela com o papel conceitual de cada
camada da rede (a contagem de parâmetros é aproximada):

| # | Camada | Shape saída | Params | Propósito |
|---|---|---|---|---|
| 0 | Input | `(B, 9, 7, 1)` | 0 | Tabuleiro cru normalizado `{0, 1}` |
| 1 | Lambda (`para_grid_de_caixas`) | `(B, 4, 3, 5)` | 0 | Reorganiza em grid de caixas (inductive bias) |
| 2 | Conv2D(32) + BN + ReLU | `(B, 4, 3, 32)` | ~1.5k | Stem: primeira leitura convolucional |
| 3 | Bloco residual 1 (32 filtros) | `(B, 4, 3, 32)` | ~3k | Aprofunda representação mantendo canais |
| 4 | Bloco residual 2 (48 filtros, projeção 1×1) | `(B, 4, 3, 48)` | ~7k | Expande capacidade |
| 5 | GAP + Flatten + Concatenate | `(B, 624)` | 0 | Achatamento dual (posicional + global) |
| 6 | Dense(96) + BN + Dropout(0.5) | `(B, 96)` | ~60k | Camada oculta final — maior capacidade |
| 7 | Dense(31, softmax) | `(B, 31)` | ~3k | Distribuição de probabilidades sobre jogadas |
| | **Total** | | **~74k** | |

Observações relevantes sobre o orçamento:

- A camada 6 (Dense 96) concentra **~80% dos parâmetros treináveis** da
  rede. Dropout 0.5 e regularização L2 existem principalmente para
  controlar essa camada.
- Os blocos convolucionais (camadas 2–4) são relativamente **baratos** em
  parâmetros graças ao uso de SeparableConv2D. Fazem o "trabalho pesado"
  de entender o jogo sem ocupar muito do orçamento total.
- O Concatenate (GAP + Flatten, camada 5) **não adiciona parâmetros por
  si só**, mas afeta o tamanho da matriz de pesos da Dense seguinte
  (624 × 96 em vez de 576 × 96 ou 48 × 96).

---

## 15. Referências cruzadas

- `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` —
  codificação canônica da matriz do tabuleiro, regras de normalização e
  invariante final do tensor da CNN.
- `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V5.ipynb` —
  implementação concreta da BoxNet discutida neste documento.
- `docs/jogo_pontinhos/soft_targets_kl_divergence.md` — complemento sobre a
  forma como o "professor Minimax" é consumido como alvo de treino.
- `docs/jogo_pontinhos/historico_tentativas_treinamento.md` — registro
  cronológico das rodadas de treino e seus resultados.
- `docs/historico_decisoes.md` — registro de decisões arquiteturais e
  abandonos de abordagens.
