# Caixa perdida — partida 55, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **3** × **3** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,2)
- **Traço jogado pela CNN:** `H_0_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.***.---.
|[M] |     [?] |
.---.---.---.
|[M] |         |
.---.   .   .
|[C] |         |
.---.---.---.
|[C] |[C] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_0_3    |      0.966245 | ⭐ (Escolhida)  |
|   V_1_4    |      0.032312 |                |
|   V_1_6    |      0.000293 | (Indisponível) |
|   H_0_5    |      0.000238 | (Indisponível) |
|   H_4_5    |      0.000122 |                |
|   V_5_4    |      0.000087 |                |
|   V_3_4    |      0.000083 |                |
|   H_2_5    |      0.000079 | (Indisponível) |
|   H_4_3    |      0.000067 |                |
|   V_3_6    |      0.000062 | (Indisponível) |
|   V_7_6    |      0.000046 | (Indisponível) |
|   V_5_6    |      0.000034 | (Indisponível) |
|   H_6_5    |      0.000030 | (Indisponível) |
|   H_2_3    |      0.000029 | (Indisponível) |
|   H_8_5    |      0.000028 | (Indisponível) |
|   H_0_1    |      0.000026 | (Indisponível) |
|   H_4_1    |      0.000025 | (Indisponível) |
|   V_7_4    |      0.000023 | (Indisponível) |
|   V_1_0    |      0.000022 | (Indisponível) |
|   V_3_2    |      0.000022 | (Indisponível) |
|   H_8_3    |      0.000020 | (Indisponível) |
|   V_3_0    |      0.000018 | (Indisponível) |
|   V_1_2    |      0.000016 | (Indisponível) |
|   H_2_1    |      0.000015 | (Indisponível) |
|   H_6_3    |      0.000013 | (Indisponível) |
|   V_5_0    |      0.000013 | (Indisponível) |
|   V_5_2    |      0.000009 | (Indisponível) |
|   V_7_2    |      0.000007 | (Indisponível) |
|   H_8_1    |      0.000006 | (Indisponível) |
|   V_7_0    |      0.000006 | (Indisponível) |
|   H_6_1    |      0.000006 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  0,  8,  1,  8],
 [ 1,  1,  1,  0,  0,  0,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1,  1,  1,  0,  0,  0,  1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [-1, -1, -1,  0,  0,  0, -1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [ 1, -1, -1, -1,  1,  1, -1],
 [ 8, -1,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida055_jogada026_vit_cnn.png` — visualização com numeração de arestas
- `cnn2_partida055_jogada026_vit_cnn.md` — este relatório
- `cnn2_partida055_jogada026_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida055_jogada026_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
