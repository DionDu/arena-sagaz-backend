# Caixa perdida — partida 23, jogada 25

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **5** × **1** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_1_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1)
- **Traço jogado pela CNN:** `V_1_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
     |[?]      *
.   .---.---.
|    |[C] |[C] |
.   .---.---.
|    |[C] |[C] |
.   .---.---.
     |[C] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_1_6    |      0.965660 | ⭐ (Escolhida)  |
|   V_1_4    |      0.029140 |                |
|   H_0_5    |      0.001669 | (Indisponível) |
|   V_1_0    |      0.001034 |                |
|   H_0_1    |      0.000342 | (Indisponível) |
|   H_2_1    |      0.000291 |                |
|   V_7_0    |      0.000261 |                |
|   H_4_1    |      0.000256 |                |
|   H_0_3    |      0.000252 | (Indisponível) |
|   H_6_1    |      0.000213 |                |
|   V_1_2    |      0.000188 | (Indisponível) |
|   V_5_0    |      0.000107 | (Indisponível) |
|   V_3_6    |      0.000101 | (Indisponível) |
|   V_3_0    |      0.000060 | (Indisponível) |
|   H_8_1    |      0.000058 | (Indisponível) |
|   V_5_2    |      0.000043 | (Indisponível) |
|   H_8_5    |      0.000039 | (Indisponível) |
|   H_2_3    |      0.000038 | (Indisponível) |
|   V_3_2    |      0.000035 | (Indisponível) |
|   H_8_3    |      0.000029 | (Indisponível) |
|   H_2_5    |      0.000028 | (Indisponível) |
|   V_7_6    |      0.000024 | (Indisponível) |
|   V_7_2    |      0.000021 | (Indisponível) |
|   V_7_4    |      0.000018 | (Indisponível) |
|   H_4_5    |      0.000017 | (Indisponível) |
|   H_6_5    |      0.000016 | (Indisponível) |
|   V_5_6    |      0.000015 | (Indisponível) |
|   V_3_4    |      0.000013 | (Indisponível) |
|   H_6_3    |      0.000013 | (Indisponível) |
|   V_5_4    |      0.000011 | (Indisponível) |
|   H_4_3    |      0.000008 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  1,  0,  0,  0,  0],
 [ 8,  0,  8,  1,  8, -1,  8],
 [-1,  0,  1,  1,  1,  1,  1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 1,  0,  1,  1, -1,  1,  1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 0,  0,  1,  1, -1, -1, -1],
 [ 8, -1,  8,  1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida023_jogada025_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida023_jogada025_vit_cnn.md` — este relatório
- `cnn1_partida023_jogada025_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida023_jogada025_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
