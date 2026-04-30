# Caixa perdida — partida 66, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **4** × **2** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,0)
- **Traço jogado pela CNN:** `V_5_0` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
|[M] |         |
.---.   .   .
*    |         |
.   .---.---.
|[?] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_5_0    |      0.972021 | ⭐ (Escolhida)  |
|   H_6_1    |      0.025493 |                |
|   H_4_5    |      0.000416 |                |
|   V_5_4    |      0.000354 |                |
|   H_4_3    |      0.000337 |                |
|   V_3_4    |      0.000164 |                |
|   V_3_2    |      0.000118 | (Indisponível) |
|   H_8_1    |      0.000106 | (Indisponível) |
|   H_8_5    |      0.000089 | (Indisponível) |
|   V_5_6    |      0.000079 | (Indisponível) |
|   V_5_2    |      0.000077 | (Indisponível) |
|   V_7_0    |      0.000076 | (Indisponível) |
|   V_7_6    |      0.000073 | (Indisponível) |
|   H_6_5    |      0.000072 | (Indisponível) |
|   V_7_2    |      0.000066 | (Indisponível) |
|   V_3_0    |      0.000060 | (Indisponível) |
|   V_7_4    |      0.000057 | (Indisponível) |
|   V_3_6    |      0.000056 | (Indisponível) |
|   H_6_3    |      0.000055 | (Indisponível) |
|   H_0_1    |      0.000033 | (Indisponível) |
|   H_8_3    |      0.000027 | (Indisponível) |
|   H_2_5    |      0.000026 | (Indisponível) |
|   V_1_0    |      0.000025 | (Indisponível) |
|   H_0_5    |      0.000023 | (Indisponível) |
|   H_4_1    |      0.000019 | (Indisponível) |
|   H_2_1    |      0.000019 | (Indisponível) |
|   V_1_6    |      0.000015 | (Indisponível) |
|   V_1_2    |      0.000013 | (Indisponível) |
|   H_2_3    |      0.000012 | (Indisponível) |
|   H_0_3    |      0.000011 | (Indisponível) |
|   V_1_4    |      0.000010 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 1,  1, -1, -1,  1, -1,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1,  1, -1,  0,  0,  0, -1],
 [ 8,  1,  8,  0,  8,  0,  8],
 [ 0,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 1,  0, -1, -1, -1, -1, -1],
 [ 8,  1,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida066_jogada026_vit_cnn.png` — visualização com numeração de arestas
- `cnn2_partida066_jogada026_vit_cnn.md` — este relatório
- `cnn2_partida066_jogada026_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida066_jogada026_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
