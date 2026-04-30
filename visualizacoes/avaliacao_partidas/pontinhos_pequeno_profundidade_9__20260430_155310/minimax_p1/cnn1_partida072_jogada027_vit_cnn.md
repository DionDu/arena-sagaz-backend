# Caixa perdida — partida 72, jogada 27

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **7** × **1** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,2)
- **Traço jogado pela CNN:** `V_5_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.   .---.
|[M] |          
.---.---.---.
|[C] |[C] |[?] |
.---.---.   .
|[C] |[C] |    *
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_5_6    |      0.549298 | ⭐ (Escolhida)  |
|   H_4_5    |      0.436907 |                |
|   V_1_6    |      0.001742 |                |
|   H_0_3    |      0.001686 |                |
|   V_3_6    |      0.001615 | (Indisponível) |
|   V_1_4    |      0.001196 |                |
|   H_6_5    |      0.000934 | (Indisponível) |
|   H_0_5    |      0.000717 | (Indisponível) |
|   V_5_4    |      0.000616 | (Indisponível) |
|   V_7_6    |      0.000600 | (Indisponível) |
|   H_8_5    |      0.000585 | (Indisponível) |
|   H_2_5    |      0.000552 | (Indisponível) |
|   V_7_4    |      0.000396 | (Indisponível) |
|   V_1_2    |      0.000346 | (Indisponível) |
|   H_0_1    |      0.000293 | (Indisponível) |
|   V_1_0    |      0.000256 | (Indisponível) |
|   H_4_1    |      0.000228 | (Indisponível) |
|   V_5_0    |      0.000213 | (Indisponível) |
|   V_7_0    |      0.000190 | (Indisponível) |
|   H_8_3    |      0.000188 | (Indisponível) |
|   H_8_1    |      0.000168 | (Indisponível) |
|   H_6_3    |      0.000165 | (Indisponível) |
|   H_2_3    |      0.000154 | (Indisponível) |
|   V_3_0    |      0.000150 | (Indisponível) |
|   V_7_2    |      0.000148 | (Indisponível) |
|   V_3_4    |      0.000133 | (Indisponível) |
|   V_5_2    |      0.000128 | (Indisponível) |
|   H_2_1    |      0.000119 | (Indisponível) |
|   H_6_1    |      0.000112 | (Indisponível) |
|   H_4_3    |      0.000088 | (Indisponível) |
|   V_3_2    |      0.000076 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  0,  8, -1,  8],
 [-1, -1,  1,  0,  0,  0,  0],
 [ 8, -1,  8,  1,  8,  1,  8],
 [ 1,  1,  1,  1,  1,  0,  1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [ 1,  1,  1,  1, -1,  0,  0],
 [ 8, -1,  8,  1,  8, -1,  8],
 [ 1,  1,  1,  1,  1,  1, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida072_jogada027_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida072_jogada027_vit_cnn.md` — este relatório
- `cnn1_partida072_jogada027_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida072_jogada027_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
