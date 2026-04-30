# Caixa perdida — partida 56, jogada 21

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **0** × **2** Minimax
- **Final da partida:** CNN **4** × **8** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 4 × 8

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
     |     [?] |
.   .---.---.
|    |         |
.   .   .   .
|    |         |
.   .---.---.
     |[M] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_0_3    |      0.574410 | ⭐ (Escolhida)  |
|   V_1_4    |      0.410505 |                |
|   V_1_0    |      0.001424 |                |
|   H_2_1    |      0.001368 |                |
|   H_0_5    |      0.001072 | (Indisponível) |
|   V_1_6    |      0.000888 | (Indisponível) |
|   H_0_1    |      0.000826 | (Indisponível) |
|   H_4_5    |      0.000709 |                |
|   H_2_5    |      0.000694 | (Indisponível) |
|   V_3_6    |      0.000656 | (Indisponível) |
|   H_4_1    |      0.000641 |                |
|   V_5_4    |      0.000579 |                |
|   V_1_2    |      0.000579 | (Indisponível) |
|   H_2_3    |      0.000463 | (Indisponível) |
|   H_6_1    |      0.000458 |                |
|   V_3_0    |      0.000448 | (Indisponível) |
|   V_7_6    |      0.000439 | (Indisponível) |
|   V_7_0    |      0.000400 |                |
|   H_4_3    |      0.000382 |                |
|   V_3_4    |      0.000362 |                |
|   V_5_6    |      0.000330 | (Indisponível) |
|   V_3_2    |      0.000303 | (Indisponível) |
|   H_8_1    |      0.000294 | (Indisponível) |
|   H_8_5    |      0.000281 | (Indisponível) |
|   V_5_0    |      0.000267 | (Indisponível) |
|   H_6_5    |      0.000231 | (Indisponível) |
|   H_8_3    |      0.000212 | (Indisponível) |
|   V_7_4    |      0.000207 | (Indisponível) |
|   V_7_2    |      0.000195 | (Indisponível) |
|   V_5_2    |      0.000192 | (Indisponível) |
|   H_6_3    |      0.000187 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  0,  8, -1,  8],
 [ 0,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  1,  8],
 [ 1,  0,  1,  0,  0,  0,  1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8, -1,  8],
 [ 0,  0,  1, -1,  1, -1, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida056_jogada021_vit_mm.png` — visualização com numeração de arestas
- `cnn1_partida056_jogada021_vit_mm.md` — este relatório
- `cnn1_partida056_jogada021_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida056_jogada021_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
