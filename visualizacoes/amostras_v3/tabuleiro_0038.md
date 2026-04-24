# tabuleiro_0038

## Metadados do Tabuleiro
- **Estratégia de Geração (STRAT_MODES):** `p0 (Aleatorio / Uniforme)`
- **Melhor Jogada (Rótulo):** `H_8_3`

## Matriz Crua (NPZ)
Abaixo está exatamente o que a CNN enxerga em `estados`. Note que não existe nenhum valor `-1` (J2) no dataset inteiro.

```text
[[8, 0, 8, 9, 8, 9, 8],
 [9, 0, 9, 1, 9, 0, 9],
 [8, 0, 8, 9, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 9],
 [8, 9, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 9, 8, 9, 8, 9, 8],
 [0, 0, 9, 0, 9, 0, 9],
 [8, 9, 8, 0, 8, 0, 8]]
```

## Visão Física do Tabuleiro

Aqui desfazemos a matriz convolucional em uma representação visual humana.
As arestas marcadas (valor `9`) são exibidas como `---` ou `|`. Os vértices (`8`) são `.`.

```text
.   .---.---.
|    | [X]|    |
.   .---.   .
               |
.---.   .   .
                
.---.---.---.
     |    |    |
.---.***.   .
```

## Avaliação Minimax (Professor de Profundidade 7)

Tabela completa com a "percepção de valor" do nosso algoritmo professor para cada traço do jogo:

|  Classe  |    Score    | É a melhor? |
|:--------:|:-----------:|-------------|
|   H_0_1    |      -5.00   |  |
|   H_0_3    |   Inválida   |  |
|   H_0_5    |   Inválida   |  |
|   V_1_0    |   Inválida   |  |
|   V_1_2    |   Inválida   |  |
|   V_1_4    |   Inválida   |  |
|   V_1_6    |   Inválida   |  |
|   H_2_1    |      -5.00   |  |
|   H_2_3    |   Inválida   |  |
|   H_2_5    |       4.00   |  |
|   V_3_0    |      -4.00   |  |
|   V_3_2    |      -4.00   |  |
|   V_3_4    |      -5.00   |  |
|   V_3_6    |   Inválida   |  |
|   H_4_1    |   Inválida   |  |
|   H_4_3    |      -4.00   |  |
|   H_4_5    |      -5.00   |  |
|   V_5_0    |      -5.00   |  |
|   V_5_2    |      -5.00   |  |
|   V_5_4    |      -4.00   |  |
|   V_5_6    |      -4.00   |  |
|   H_6_1    |   Inválida   |  |
|   H_6_3    |   Inválida   |  |
|   H_6_5    |   Inválida   |  |
|   V_7_0    |       4.00   |  |
|   V_7_2    |   Inválida   |  |
|   V_7_4    |   Inválida   |  |
|   V_7_6    |   Inválida   |  |
|   H_8_1    |   Inválida   |  |
|   H_8_3    |       4.00   | ⭐ (Melhor) |
|   H_8_5    |       4.00   |  |
