# Caixa perdida — partida 21, jogada 24

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **2** × **3** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

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
.---.---.   .
|[C] |[M] |    |
.---.---.   .
|[C] |         |
.---.   .---.
|[?] |    |[M] |
.   .   .---.
*    |    |[M] |
.---.   .---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_7_0    |      0.990159 | ⭐ (Escolhida)  |
|   H_6_1    |      0.007080 |                |
|   H_8_3    |      0.000825 |                |
|   H_8_1    |      0.000630 | (Indisponível) |
|   H_6_3    |      0.000240 |                |
|   V_5_0    |      0.000231 | (Indisponível) |
|   H_0_5    |      0.000201 |                |
|   H_2_5    |      0.000089 |                |
|   V_5_2    |      0.000077 | (Indisponível) |
|   H_4_1    |      0.000047 | (Indisponível) |
|   H_4_3    |      0.000047 |                |
|   V_7_2    |      0.000034 | (Indisponível) |
|   V_7_4    |      0.000033 | (Indisponível) |
|   H_8_5    |      0.000032 | (Indisponível) |
|   V_7_6    |      0.000030 | (Indisponível) |
|   V_3_4    |      0.000025 |                |
|   V_5_4    |      0.000024 | (Indisponível) |
|   V_3_0    |      0.000022 | (Indisponível) |
|   V_3_6    |      0.000022 | (Indisponível) |
|   V_5_6    |      0.000020 | (Indisponível) |
|   V_3_2    |      0.000019 | (Indisponível) |
|   H_0_1    |      0.000019 | (Indisponível) |
|   V_1_6    |      0.000019 | (Indisponível) |
|   H_6_5    |      0.000018 | (Indisponível) |
|   H_4_5    |      0.000016 | (Indisponível) |
|   H_2_1    |      0.000013 | (Indisponível) |
|   V_1_0    |      0.000013 | (Indisponível) |
|   H_0_3    |      0.000006 | (Indisponível) |
|   V_1_2    |      0.000004 | (Indisponível) |
|   H_2_3    |      0.000004 | (Indisponível) |
|   V_1_4    |      0.000003 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8, -1,  8,  0,  8],
 [-1, -1, -1,  1,  1,  0,  1],
 [ 8, -1,  8,  1,  8,  0,  8],
 [ 1, -1, -1,  0,  0,  0, -1],
 [ 8,  1,  8,  0,  8,  1,  8],
 [ 1,  0, -1,  0, -1,  1, -1],
 [ 8,  0,  8,  0,  8,  1,  8],
 [ 0,  0, -1,  0,  1,  1,  1],
 [ 8,  1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida021_jogada024_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida021_jogada024_vit_mm.md` — este relatório
- `cnn2_partida021_jogada024_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida021_jogada024_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
