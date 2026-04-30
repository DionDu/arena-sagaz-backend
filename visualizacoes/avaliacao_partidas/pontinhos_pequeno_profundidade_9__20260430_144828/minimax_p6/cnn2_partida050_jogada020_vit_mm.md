# Caixa perdida — partida 50, jogada 20

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **1** × **1** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1)
- **Traço jogado pela CNN:** `H_0_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.***.
     |[?]      |
.   .---.---.
|    |          
.   .   .---.
|    |          
.   .---.---.
|    |[M] |[C] |
.   .---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_0_5    |      0.961161 | ⭐ (Escolhida)  |
|   V_1_4    |      0.026450 |                |
|   V_1_6    |      0.005364 | (Indisponível) |
|   V_3_6    |      0.002030 |                |
|   V_1_0    |      0.001168 |                |
|   V_5_6    |      0.000431 |                |
|   H_0_3    |      0.000410 | (Indisponível) |
|   H_0_1    |      0.000370 | (Indisponível) |
|   H_8_1    |      0.000265 |                |
|   V_5_4    |      0.000206 |                |
|   V_1_2    |      0.000189 | (Indisponível) |
|   H_2_1    |      0.000155 |                |
|   H_4_1    |      0.000148 |                |
|   V_7_6    |      0.000143 | (Indisponível) |
|   H_8_5    |      0.000136 | (Indisponível) |
|   V_3_4    |      0.000123 |                |
|   H_2_3    |      0.000116 | (Indisponível) |
|   H_8_3    |      0.000114 | (Indisponível) |
|   H_4_5    |      0.000105 | (Indisponível) |
|   V_5_0    |      0.000102 | (Indisponível) |
|   V_3_0    |      0.000098 | (Indisponível) |
|   H_6_1    |      0.000094 |                |
|   V_7_0    |      0.000086 | (Indisponível) |
|   H_6_5    |      0.000080 | (Indisponível) |
|   V_3_2    |      0.000079 | (Indisponível) |
|   H_4_3    |      0.000078 |                |
|   H_6_3    |      0.000068 | (Indisponível) |
|   V_5_2    |      0.000065 | (Indisponível) |
|   V_7_4    |      0.000059 | (Indisponível) |
|   H_2_5    |      0.000058 | (Indisponível) |
|   V_7_2    |      0.000049 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8,  0,  8],
 [ 0,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  1,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 1,  0,  1,  1, -1, -1,  1],
 [ 8,  0,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida050_jogada020_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida050_jogada020_vit_mm.md` — este relatório
- `cnn2_partida050_jogada020_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida050_jogada020_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
