# Caixa perdida — partida 90, jogada 27

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **8** × **0** Minimax
- **Final da partida:** CNN **10** × **2** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 10 × 2

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,1)
- **Traço jogado pela CNN:** `H_8_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
     |[C] |[C] |
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
|[C] |[?]      |
.---.---.***.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_5    |      0.579096 | ⭐ (Escolhida)  |
|   V_7_4    |      0.405370 |                |
|   V_1_0    |      0.002842 |                |
|   H_2_1    |      0.002721 |                |
|   V_3_0    |      0.001458 |                |
|   V_7_6    |      0.001069 | (Indisponível) |
|   H_8_3    |      0.001013 | (Indisponível) |
|   H_6_5    |      0.000960 | (Indisponível) |
|   H_0_1    |      0.000645 | (Indisponível) |
|   H_6_3    |      0.000594 | (Indisponível) |
|   V_5_0    |      0.000458 | (Indisponível) |
|   V_5_6    |      0.000445 | (Indisponível) |
|   H_4_1    |      0.000429 | (Indisponível) |
|   V_5_4    |      0.000319 | (Indisponível) |
|   V_1_2    |      0.000274 | (Indisponível) |
|   V_7_2    |      0.000273 | (Indisponível) |
|   V_5_2    |      0.000269 | (Indisponível) |
|   V_3_6    |      0.000219 | (Indisponível) |
|   H_4_5    |      0.000215 | (Indisponível) |
|   V_3_2    |      0.000205 | (Indisponível) |
|   H_6_1    |      0.000175 | (Indisponível) |
|   V_7_0    |      0.000160 | (Indisponível) |
|   H_8_1    |      0.000138 | (Indisponível) |
|   H_2_5    |      0.000136 | (Indisponível) |
|   H_0_5    |      0.000108 | (Indisponível) |
|   V_1_6    |      0.000088 | (Indisponível) |
|   H_0_3    |      0.000080 | (Indisponível) |
|   H_4_3    |      0.000075 | (Indisponível) |
|   V_3_4    |      0.000056 | (Indisponível) |
|   H_2_3    |      0.000055 | (Indisponível) |
|   V_1_4    |      0.000055 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  1,  8, -1,  8],
 [ 0,  0,  1,  1,  1,  1, -1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 0,  0,  1,  1, -1,  1,  1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [ 1,  1,  1,  1,  1,  1,  1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [ 1,  1, -1,  0,  0,  0,  1],
 [ 8, -1,  8, -1,  8,  0,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida090_jogada027_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida090_jogada027_vit_cnn.md` — este relatório
- `cnn1_partida090_jogada027_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida090_jogada027_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
