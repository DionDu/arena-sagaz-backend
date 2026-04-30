# Caixa perdida — partida 34, jogada 25

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **2** × **4** Minimax
- **Final da partida:** CNN **4** × **8** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 4 × 8

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,1)
- **Traço jogado pela CNN:** `V_3_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
     |[C] |[C] |
.   .---.---.
|    |[?]      *
.   .---.---.
|    |[M] |[M] |
.   .---.---.
     |[M] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_6    |      0.979659 | ⭐ (Escolhida)  |
|   V_3_4    |      0.017908 |                |
|   V_1_0    |      0.000391 |                |
|   H_2_1    |      0.000304 |                |
|   V_7_0    |      0.000285 |                |
|   H_0_1    |      0.000223 | (Indisponível) |
|   V_5_0    |      0.000131 | (Indisponível) |
|   H_6_1    |      0.000123 |                |
|   H_4_1    |      0.000117 |                |
|   V_3_0    |      0.000097 | (Indisponível) |
|   V_3_2    |      0.000091 | (Indisponível) |
|   H_8_1    |      0.000067 | (Indisponível) |
|   V_5_6    |      0.000062 | (Indisponível) |
|   H_2_3    |      0.000056 | (Indisponível) |
|   V_5_2    |      0.000055 | (Indisponível) |
|   V_1_2    |      0.000052 | (Indisponível) |
|   H_0_3    |      0.000040 | (Indisponível) |
|   V_1_6    |      0.000036 | (Indisponível) |
|   H_0_5    |      0.000035 | (Indisponível) |
|   H_6_5    |      0.000034 | (Indisponível) |
|   H_8_5    |      0.000029 | (Indisponível) |
|   V_7_6    |      0.000028 | (Indisponível) |
|   V_7_2    |      0.000026 | (Indisponível) |
|   H_2_5    |      0.000026 | (Indisponível) |
|   H_4_3    |      0.000021 | (Indisponível) |
|   V_5_4    |      0.000021 | (Indisponível) |
|   H_8_3    |      0.000020 | (Indisponível) |
|   H_4_5    |      0.000018 | (Indisponível) |
|   H_6_3    |      0.000018 | (Indisponível) |
|   V_7_4    |      0.000015 | (Indisponível) |
|   V_1_4    |      0.000013 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8, -1,  8],
 [ 0,  0,  1,  1, -1,  1,  1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 1,  0,  1, -1, -1, -1,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 0,  0, -1, -1,  1, -1, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida034_jogada025_vit_mm.png` — visualização com numeração de arestas
- `cnn1_partida034_jogada025_vit_mm.md` — este relatório
- `cnn1_partida034_jogada025_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida034_jogada025_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
