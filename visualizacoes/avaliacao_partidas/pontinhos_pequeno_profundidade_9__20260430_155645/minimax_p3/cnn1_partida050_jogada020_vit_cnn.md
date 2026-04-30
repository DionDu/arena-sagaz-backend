# Caixa perdida — partida 50, jogada 20

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **0** × **1** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_1_4` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,2)
- **Traço jogado pela CNN:** `V_1_4` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas fechadas e arestas marcadas pela CNN
- 🟠 laranja = caixas fechadas e arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = aresta que a CNN está prestes a marcar (não numerada, pois ainda não foi aplicada)
- ⚪ círculos cinza-claros = vértices · linhas pontilhadas = arestas ainda não jogadas
- réguas (números cinza-escuros) = índices da matriz `(linha, coluna)` em todos os 4 lados

Cada aresta marcada exibe um número branco no centro: a ordem cronológica em que foi jogada (`0` = primeiro traço da partida; números crescem ao longo da partida).

```text
.---.   .---.
|[M] |    *     
.---.---.---.
|              |
.   .---.   .
|    |         |
.   .   .---.
|         |[?] |
.---.---.   .
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_1_4    |      0.505468 | ⭐ (Escolhida)  |
|   H_8_5    |      0.455586 |                |
|   V_1_6    |      0.011844 |                |
|   H_0_3    |      0.008144 |                |
|   V_7_6    |      0.002221 | (Indisponível) |
|   H_4_1    |      0.001599 |                |
|   H_2_5    |      0.001398 | (Indisponível) |
|   H_0_5    |      0.001107 | (Indisponível) |
|   H_4_5    |      0.001082 |                |
|   H_8_3    |      0.000891 | (Indisponível) |
|   V_3_2    |      0.000886 |                |
|   H_6_5    |      0.000811 | (Indisponível) |
|   V_7_4    |      0.000777 | (Indisponível) |
|   V_5_4    |      0.000753 |                |
|   V_3_6    |      0.000699 | (Indisponível) |
|   V_3_4    |      0.000689 |                |
|   V_5_0    |      0.000664 | (Indisponível) |
|   V_1_2    |      0.000662 | (Indisponível) |
|   V_7_2    |      0.000646 |                |
|   H_6_3    |      0.000612 |                |
|   H_2_3    |      0.000518 | (Indisponível) |
|   H_6_1    |      0.000385 |                |
|   V_5_6    |      0.000371 | (Indisponível) |
|   H_0_1    |      0.000313 | (Indisponível) |
|   V_7_0    |      0.000306 | (Indisponível) |
|   V_3_0    |      0.000295 | (Indisponível) |
|   H_4_3    |      0.000290 | (Indisponível) |
|   V_5_2    |      0.000262 | (Indisponível) |
|   V_1_0    |      0.000259 | (Indisponível) |
|   H_8_1    |      0.000256 | (Indisponível) |
|   H_2_1    |      0.000206 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  0,  8, -1,  8],
 [-1, -1,  1,  0,  0,  0,  0],
 [ 8,  1,  8, -1,  8,  1,  8],
 [-1,  0,  0,  0,  0,  0,  1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [ 1,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8,  0,  8, -1,  8],
 [-1,  0,  0,  0,  1,  0, -1],
 [ 8,  1,  8, -1,  8,  0,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida050_jogada020_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida050_jogada020_vit_cnn.md` — este relatório
- `cnn1_partida050_jogada020_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida050_jogada020_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
