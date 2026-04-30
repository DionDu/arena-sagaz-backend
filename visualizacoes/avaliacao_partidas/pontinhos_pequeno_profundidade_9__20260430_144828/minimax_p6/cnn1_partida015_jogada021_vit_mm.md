# Caixa perdida — partida 15, jogada 21

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **0** × **2** Minimax
- **Final da partida:** CNN **4** × **8** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 4 × 8

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_2_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1)
- **Traço jogado pela CNN:** `H_2_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
     |[?]      |
.   .---.***.
|    |         |
.   .   .   .
|    |         |
.   .---.---.
|    |[M] |[M] |
.   .---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_2_5    |      0.796710 | ⭐ (Escolhida)  |
|   V_1_4    |      0.194737 |                |
|   H_4_5    |      0.001157 |                |
|   V_1_0    |      0.000869 |                |
|   V_3_6    |      0.000833 | (Indisponível) |
|   V_3_4    |      0.000811 |                |
|   H_0_5    |      0.000447 | (Indisponível) |
|   H_2_3    |      0.000421 | (Indisponível) |
|   H_4_1    |      0.000405 |                |
|   V_1_2    |      0.000388 | (Indisponível) |
|   V_1_6    |      0.000316 | (Indisponível) |
|   H_0_1    |      0.000314 | (Indisponível) |
|   H_0_3    |      0.000285 | (Indisponível) |
|   V_5_4    |      0.000285 |                |
|   H_4_3    |      0.000225 |                |
|   H_2_1    |      0.000220 |                |
|   H_8_1    |      0.000187 |                |
|   V_5_6    |      0.000165 | (Indisponível) |
|   H_8_5    |      0.000148 | (Indisponível) |
|   H_6_3    |      0.000131 | (Indisponível) |
|   H_6_5    |      0.000121 | (Indisponível) |
|   H_6_1    |      0.000103 |                |
|   V_7_6    |      0.000093 | (Indisponível) |
|   V_7_4    |      0.000089 | (Indisponível) |
|   V_5_2    |      0.000087 | (Indisponível) |
|   V_5_0    |      0.000084 | (Indisponível) |
|   V_7_2    |      0.000081 | (Indisponível) |
|   V_7_0    |      0.000080 | (Indisponível) |
|   H_8_3    |      0.000074 | (Indisponível) |
|   V_3_2    |      0.000070 | (Indisponível) |
|   V_3_0    |      0.000064 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  1,  0,  0,  0,  1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  1,  0,  0,  0,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [-1,  0, -1, -1,  1, -1,  1],
 [ 8,  0,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida015_jogada021_vit_mm.png` — visualização com numeração de arestas
- `cnn1_partida015_jogada021_vit_mm.md` — este relatório
- `cnn1_partida015_jogada021_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida015_jogada021_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
