# Caixa perdida — partida 65, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **2** × **5** Minimax
- **Final da partida:** CNN **3** × **9** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 3 × 9

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_7_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,0)
- **Traço jogado pela CNN:** `V_7_0` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.   .---.---.
|               
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
|[?] |[M] |[M] |
.   .---.---.
*    |[C] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_7_0    |      0.891527 | ⭐ (Escolhida)  |
|   H_6_1    |      0.096045 |                |
|   H_0_1    |      0.003566 |                |
|   V_1_2    |      0.002102 |                |
|   V_1_6    |      0.001284 |                |
|   H_8_1    |      0.001166 | (Indisponível) |
|   V_1_4    |      0.000894 |                |
|   V_5_0    |      0.000885 | (Indisponível) |
|   V_1_0    |      0.000366 | (Indisponível) |
|   H_0_5    |      0.000323 | (Indisponível) |
|   H_2_1    |      0.000298 | (Indisponível) |
|   H_4_1    |      0.000297 | (Indisponível) |
|   H_0_3    |      0.000235 | (Indisponível) |
|   V_3_0    |      0.000150 | (Indisponível) |
|   H_2_5    |      0.000101 | (Indisponível) |
|   V_7_2    |      0.000097 | (Indisponível) |
|   V_5_2    |      0.000092 | (Indisponível) |
|   H_8_3    |      0.000075 | (Indisponível) |
|   H_8_5    |      0.000070 | (Indisponível) |
|   V_7_6    |      0.000064 | (Indisponível) |
|   V_7_4    |      0.000062 | (Indisponível) |
|   V_3_6    |      0.000061 | (Indisponível) |
|   H_6_5    |      0.000049 | (Indisponível) |
|   V_5_6    |      0.000039 | (Indisponível) |
|   H_6_3    |      0.000036 | (Indisponível) |
|   V_3_2    |      0.000028 | (Indisponível) |
|   H_2_3    |      0.000023 | (Indisponível) |
|   V_5_4    |      0.000020 | (Indisponível) |
|   H_4_5    |      0.000018 | (Indisponível) |
|   H_4_3    |      0.000016 | (Indisponível) |
|   V_3_4    |      0.000011 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  0,  8,  1,  8,  1,  8],
 [ 1,  0,  0,  0,  0,  0,  0],
 [ 8,  1,  8, -1,  8, -1,  8],
 [-1, -1, -1,  1,  1,  1,  1],
 [ 8,  1,  8,  1,  8,  1,  8],
 [-1,  0, -1,  1, -1,  1, -1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 0,  0, -1, -1,  1,  1, -1],
 [ 8,  1,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida065_jogada026_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida065_jogada026_vit_mm.md` — este relatório
- `cnn2_partida065_jogada026_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida065_jogada026_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
