# Caixa perdida — partida 12, jogada 23

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **4** × **0** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_2` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,2)
- **Traço jogado pela CNN:** `V_3_2` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|               
.   .---.---.
|    *     [?] |
.   .---.---.
|    |[C] |[C] |
.   .---.---.
     |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_2    |      0.900202 | ⭐ (Escolhida)  |
|   V_3_4    |      0.092884 |                |
|   H_2_1    |      0.002751 |                |
|   H_4_1    |      0.000616 |                |
|   V_3_6    |      0.000396 | (Indisponível) |
|   V_1_2    |      0.000284 |                |
|   V_1_0    |      0.000270 | (Indisponível) |
|   V_1_4    |      0.000235 |                |
|   H_2_5    |      0.000232 | (Indisponível) |
|   H_0_1    |      0.000222 | (Indisponível) |
|   V_1_6    |      0.000215 |                |
|   V_3_0    |      0.000186 | (Indisponível) |
|   H_2_3    |      0.000185 | (Indisponível) |
|   V_5_0    |      0.000176 | (Indisponível) |
|   H_6_1    |      0.000138 |                |
|   V_7_0    |      0.000135 |                |
|   H_0_5    |      0.000128 | (Indisponível) |
|   V_5_2    |      0.000102 | (Indisponível) |
|   H_4_5    |      0.000100 | (Indisponível) |
|   H_0_3    |      0.000083 | (Indisponível) |
|   H_8_1    |      0.000064 | (Indisponível) |
|   H_6_3    |      0.000059 | (Indisponível) |
|   H_4_3    |      0.000057 | (Indisponível) |
|   H_6_5    |      0.000048 | (Indisponível) |
|   V_5_4    |      0.000043 | (Indisponível) |
|   V_5_6    |      0.000041 | (Indisponível) |
|   H_8_5    |      0.000036 | (Indisponível) |
|   V_7_2    |      0.000035 | (Indisponível) |
|   V_7_6    |      0.000027 | (Indisponível) |
|   V_7_4    |      0.000026 | (Indisponível) |
|   H_8_3    |      0.000022 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8,  1,  8],
 [-1,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8, -1,  8,  1,  8],
 [ 1,  0,  0,  0,  0,  0,  1],
 [ 8,  0,  8, -1,  8, -1,  8],
 [ 1,  0,  1,  1,  1,  1,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 0,  0, -1,  1,  1,  1, -1],
 [ 8,  1,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida012_jogada023_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida012_jogada023_vit_cnn.md` — este relatório
- `cnn1_partida012_jogada023_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida012_jogada023_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
