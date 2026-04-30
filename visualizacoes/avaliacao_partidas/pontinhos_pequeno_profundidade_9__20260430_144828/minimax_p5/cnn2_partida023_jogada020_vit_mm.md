# Caixa perdida — partida 23, jogada 20

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **1** × **1** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,1)
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
     |    |     
.   .   .   .
|    |         |
.   .---.---.
|    |[?]      *
.   .---.---.
|    |[C] |[M] |
.   .---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_5_6    |      0.775146 | ⭐ (Escolhida)  |
|   V_5_4    |      0.216623 |                |
|   V_1_6    |      0.000749 |                |
|   V_1_0    |      0.000647 |                |
|   V_7_6    |      0.000617 | (Indisponível) |
|   H_2_5    |      0.000594 |                |
|   H_8_5    |      0.000524 | (Indisponível) |
|   H_0_3    |      0.000420 |                |
|   H_8_1    |      0.000339 |                |
|   H_0_1    |      0.000328 | (Indisponível) |
|   V_3_6    |      0.000316 | (Indisponível) |
|   V_7_0    |      0.000302 | (Indisponível) |
|   H_4_5    |      0.000245 | (Indisponível) |
|   H_0_5    |      0.000245 | (Indisponível) |
|   H_6_5    |      0.000232 | (Indisponível) |
|   V_7_4    |      0.000231 | (Indisponível) |
|   V_5_0    |      0.000230 | (Indisponível) |
|   H_2_3    |      0.000226 |                |
|   H_4_1    |      0.000207 |                |
|   H_6_1    |      0.000197 |                |
|   H_2_1    |      0.000194 |                |
|   H_4_3    |      0.000190 | (Indisponível) |
|   V_3_2    |      0.000182 | (Indisponível) |
|   H_6_3    |      0.000182 | (Indisponível) |
|   V_7_2    |      0.000151 | (Indisponível) |
|   H_8_3    |      0.000130 | (Indisponível) |
|   V_3_4    |      0.000127 |                |
|   V_5_2    |      0.000120 | (Indisponível) |
|   V_1_2    |      0.000119 | (Indisponível) |
|   V_3_0    |      0.000102 | (Indisponível) |
|   V_1_4    |      0.000084 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  0,  8, -1,  8],
 [ 0,  0, -1,  0,  1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 1,  0,  1, -1,  1,  1, -1],
 [ 8,  0,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida023_jogada020_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida023_jogada020_vit_mm.md` — este relatório
- `cnn2_partida023_jogada020_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida023_jogada020_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
