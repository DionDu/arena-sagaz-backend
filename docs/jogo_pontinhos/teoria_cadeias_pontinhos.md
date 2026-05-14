# Teoria de Cadeias e Paridade no Jogo dos Pontinhos

**Data**: 2026-05-13 | **Branch**: `004-melhoria-geracao-dados-cnn`

> Documento de referência teórica sobre paridade de cadeias longas e o mecanismo de double-cross. Motivou a criação do canal 12 (`paridade_cadeia_longa_impar`) no pipeline de canais estruturais.

---

## 1. Por que a CNN estagna?

A CNN BoxNet v3 atingiu um teto de performance contra Minimax profundo que não é eliminado por:
- Aumentar o volume de dados
- Aumentar a profundidade da rede
- Adicionar sample_weight por fase do jogo

A causa raiz é teórica: certas decisões estratégicas no Jogo dos Pontinhos dependem de uma propriedade **global** do tabuleiro — a paridade do número de cadeias longas abertas — que uma CNN com receptivo campo local não consegue inferir por convolução.

---

## 2. Cadeias abertas no Jogo dos Pontinhos

Uma **cadeia aberta** é uma sequência de caixas abertas (não fechadas) onde cada caixa tem exatamente 2 arestas preenchidas (grau-2). No grafo dual do tabuleiro (nós = caixas grau-2, arestas = vizinhos que compartilham aresta livre), uma cadeia corresponde a um **caminho** (path) no grafo.

Classificação:
- **Cadeia curta**: comprimento 1–2 caixas (sem oportunidade de double-cross puro)
- **Cadeia longa**: comprimento ≥ 3 caixas (double-cross possível — vide §3)

No endgame típico, o tabuleiro fica com algumas cadeias longas e/ou curtas abertas, e o jogador que melhor administrar essas estruturas vence.

---

## 3. O mecanismo de double-cross

Quando um jogador **abre** uma cadeia longa (joga a aresta que torna a primeira caixa da cadeia grau-3), o adversário tem o direito de capturar toda a cadeia. Mas existe uma jogada mais sofisticada:

**Double-cross**: o adversário captura apenas as `n-2` primeiras caixas da cadeia (n = comprimento). Para as 2 caixas finais, joga a aresta interna *entre* elas — tornando ambas grau-3 sem fechar nenhuma. O turno passa para o abridor.

O abridor agora tem duas caixas grau-3 para capturar ("handout"). Ele as captura (+2 caixas) e, depois de capturar, precisa fazer uma nova jogada. Como todas as jogadas restantes no endgame abrem outra cadeia, ele é **obrigado** a abrir a próxima cadeia longa.

**Por que ele é obrigado?** Porque no endgame puro de cadeias, todas as arestas livres do tabuleiro fazem parte de cadeias. Qualquer aresta que o jogador escolha tornar a próxima caixa no caminho de uma cadeia em grau-3, abrindo-a. Não existe jogada "neutra" nessa fase — todas as jogadas abrem alguma cadeia.

---

## 4. Exemplo passo-a-passo: 1 cadeia curta + 2 cadeias longas

**Estado inicial**:
- S = cadeia curta de 2 caixas
- L1 = cadeia longa de 4 caixas
- L2 = cadeia longa de 4 caixas
- Canal 12 = **0** (2 cadeias longas = número PAR)
- **Seu turno**

### Jogada correta: sacrificar S primeiro

| Passo | Quem | Ação | Placar você | Placar adversário |
|-------|------|------|-------------|-------------------|
| 1 | Você | Abre S (joga a aresta que torna caixa 1 de S grau-3) | 0 | 0 |
| 2 | Adversário | Captura S inteira (+2) | 0 | 2 |
| 3 | Adversário | Deve jogar; única opção: abre L1 | 0 | 2 |
| 4 | Você | Captura L1 com **double-cross**: pega 2 caixas, joga aresta interna (último par) | +2 → **2** | 2 |
| 5 | Adversário | Captura as 2 caixas de handout de L1 (+2) | 2 | **4** |
| 6 | Adversário | Deve jogar; única opção: abre L2 | 2 | 4 |
| 7 | Você | Captura **toda** L2 sem double-cross (última cadeia): +4 | **6** | 4 |

**Resultado: você vence 6 × 4.**

### Por que o passo 6 é forçado?

No passo 5, o adversário captura as 2 caixas de handout de L1. Isso é uma captura, então ele continua com o turno. Mas depois dessas capturas, a única aresta livre que ele pode jogar pertence a L2. Ele não tem escolha.

### Comparação: abrir L1 diretamente (jogada errada)

| Passo | Quem | Ação |
|-------|------|------|
| 1 | Você | Abre L1 |
| 2 | Adversário | Captura L1 inteira (+4) **sem double-cross** |
| 3 | Adversário | Abre S |
| 4 | Você | Captura S (+2) |
| 5 | Você | Abre L2 |
| 6 | Adversário | Captura L2 inteira (+4) |

**Resultado: você perde 2 × 8.**

O adversário tem a liberdade de usar ou não o double-cross. Se você abrir L1 diretamente, o adversário toma L1 inteira (nenhum double-cross — ele fica com 4 caixas e pode controlar o ritmo das próximas capturas). O resultado é muito pior para você.

---

## 5. Por que a paridade é decisiva

O exemplo acima funciona porque **sacrificar S muda QUEM abre a primeira cadeia longa**. Ao sacrificar S:
- O adversário captura S e fica com o turno
- Todas as jogadas restantes abrem L1 ou L2 — o adversário é forçado a abrir a primeira

Depois disso, você usa double-cross em L1 para forçar o adversário a abrir L2. Então você captura L2 por inteiro.

Este mecanismo de "forçar o adversário a abrir" só funciona porque há **um número par de cadeias longas**. Com 2 cadeias longas:
- O adversário abre a primeira → você double-cross → adversário é forçado a abrir a segunda → você captura a segunda inteira

Com 1 cadeia longa (ímpar) + 1 cadeia curta:
- Você sacrifica S → adversário captura S → adversário abre L → você captura L inteira

Com 3 cadeias longas (ímpar) + 1 cadeia curta:
- Você sacrifica S → adversário abre L1 → você double-cross → adversário abre L2 → você double-cross → adversário abre L3 → você captura L3 inteira

Em geral: a paridade do número de cadeias longas determina quem captura a **última** cadeia longa por inteiro (o maior ganho). O jogador que sacrifica as cadeias curtas primeiro, empurrando o adversário para a posição de abrir, consegue capturar a última cadeia longa completamente.

A teoria de Berlekamp (Winning Ways) formaliza isso: o valor de jogo de um estado com `n` cadeias longas tem componente de paridade que determina o sinal do ganho esperado. Este é o resultado estratégico mais importante do jogo além das capturas imediatas de grau-3.

---

## 6. Por que a CNN local não aprende paridade

Os canais K=7 (`em_cadeia_curta`) e K=8 (`em_cadeia_longa`) marcam as células pertencentes a cadeias. Mas eles são **binários**: valor 1 indica "essa célula pertence a uma cadeia longa", sem indicar quantas cadeias longas existem no total.

A CNN é uma rede convolucional: cada neurônio vê apenas um receptivo campo local. Para determinar se o número de cadeias longas é par ou ímpar, a rede precisaria **contar** quantas cadeias longas existem em todo o tabuleiro — uma operação global que exige integrar informação de todas as 12 caixas simultaneamente.

Convoluções locais não conseguem fazer isso eficientemente. Mesmo com múltiplas camadas, a rede teria que "propagar" a contagem por todo o tabuleiro, o que não é a tarefa para a qual CNNs convolucionais são otimizadas.

**Consequência prática**: a CNN pode identificar que existem cadeias longas (canal K=8 ativado), mas não sabe se há 1, 2, ou 3 delas. Com esse bit faltando, ela não consegue distinguir "devo sacrificar a cadeia curta para me posicionar bem" de "devo sacrificar a cadeia longa diretamente". O resultado é uma política subótima no meio-jogo.

---

## 7. Canal 12 — `paridade_cadeia_longa_impar`

**Definição**: canal binário, broadcast global (mesmo valor para as 12 células do tabuleiro).

- Valor **1**: número de cadeias longas abertas é **ímpar** (1, 3, 5, ...)
- Valor **0**: número de cadeias longas abertas é **par** (0, 2, 4, ...)

Uma "cadeia longa aberta" é um componente conexo no grafo dual de grau-2 que:
- Tem comprimento ≥ 3
- Não é um loop (nem todos os nós do componente têm grau 2 no componente)
- Não é complexa (nenhum nó tem grau ≥ 3 no componente)

**Implementação** (extensão de `extrair_canais` em `analisador_estrutural_pontinhos.py`):

```python
# Após a classificação dos componentes (BFS já executado):
n_cadeias_longas = sum(
    1 for comp in componentes
    if len(comp) >= 3
    and not all(len(adj[u]) == 2 for u in comp)   # não é loop
    and max(len(adj[u]) for u in comp) < 3         # não é complexa
)
paridade_impar = (n_cadeias_longas % 2) == 1

# Canal K=11 (0-based): broadcast para todas as células
for r in range(N_LINHAS):
    for c in range(N_COLUNAS):
        canais[r, c, 11] = 1 if paridade_impar else 0
```

**Propriedades**:
- **Broadcast**: todas as 12 células recebem o mesmo valor. A CNN pode ler de qualquer posição e inferir a paridade global.
- **Sem permutação sob simetria**: por ser um escalar global, reflexão/rotação do tabuleiro não altera o valor. Não há troca de slots necessária.
- **Exclusão mútua**: não conflita com os outros canais (canal 12 pode ser 1 mesmo quando `em_cadeia_longa = 0` para uma caixa que não pertence a nenhuma cadeia longa — mas o valor é o mesmo para toda a linha/coluna do tensor).

**Por que ajuda a CNN**:

Com canal 12 explícito, a CNN não precisa inferir a paridade por convolução. O valor já está lá, em todas as 12 células, como um sinal direto. A rede pode então aprender as políticas condicionadas à paridade:
- Canal 12 = 1 (ímpar): política A — sacrificar cadeia curta é vantajoso
- Canal 12 = 0 (par): política B — diferente gestão das cadeias

Este é o canal com maior potencial de impacto na performance vs Minimax de profundidade 5+, que explora exatamente esse tipo de erro estratégico de paridade.

---

## 8. Referências

- Berlekamp, E.R., Conway, J.H., Guy, R.K. (2001). *Winning Ways for Your Mathematical Plays*, Vol. 1. Canal 12 é motivado pelo "long chain rule" de Berlekamp.
- Barker, J.K., Korf, R.E. (2012). Solving Dots-and-Boxes. *AAAI 2012*. Chains e half-open chains como features de poda em Alpha-Beta.
- Buchin, K. et al. (2021). Dots & Boxes is PSPACE-complete. Formalização do grafo dual e estrutura de cadeias.
