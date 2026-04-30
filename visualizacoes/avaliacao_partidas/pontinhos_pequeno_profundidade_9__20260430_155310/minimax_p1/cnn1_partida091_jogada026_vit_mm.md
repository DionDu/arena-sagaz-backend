# Caixa perdida — partida 91, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **4** × **3** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,1)
- **Traço jogado pela CNN:** `V_3_0` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[M] |[M] |[M] |
.---.---.---.
*     [?] |[C] |
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
                
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_0    |      0.914216 | ⭐ (Escolhida)  |
|   V_3_2    |      0.082140 |                |
|   V_7_0    |      0.000430 |                |
|   V_7_6    |      0.000423 |                |
|   V_7_2    |      0.000285 |                |
|   V_7_4    |      0.000261 |                |
|   H_8_5    |      0.000164 | (Indisponível) |
|   H_8_1    |      0.000162 | (Indisponível) |
|   V_5_0    |      0.000156 | (Indisponível) |
|   H_8_3    |      0.000144 | (Indisponível) |
|   H_0_1    |      0.000129 | (Indisponível) |
|   V_5_6    |      0.000122 | (Indisponível) |
|   H_6_1    |      0.000106 | (Indisponível) |
|   H_0_5    |      0.000095 | (Indisponível) |
|   H_6_5    |      0.000090 | (Indisponível) |
|   H_6_3    |      0.000090 | (Indisponível) |
|   V_3_6    |      0.000087 | (Indisponível) |
|   V_1_0    |      0.000085 | (Indisponível) |
|   V_5_4    |      0.000085 | (Indisponível) |
|   H_4_1    |      0.000084 | (Indisponível) |
|   H_4_3    |      0.000082 | (Indisponível) |
|   H_2_5    |      0.000075 | (Indisponível) |
|   V_5_2    |      0.000073 | (Indisponível) |
|   H_4_5    |      0.000070 | (Indisponível) |
|   V_3_4    |      0.000061 | (Indisponível) |
|   H_2_3    |      0.000059 | (Indisponível) |
|   H_2_1    |      0.000054 | (Indisponível) |
|   V_1_6    |      0.000054 | (Indisponível) |
|   H_0_3    |      0.000052 | (Indisponível) |
|   V_1_2    |      0.000038 | (Indisponível) |
|   V_1_4    |      0.000026 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  1,  8, -1,  8],
 [-1, -1,  1, -1, -1, -1, -1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [ 0,  0,  0,  0,  1,  1,  1],
 [ 8,  1,  8,  1,  8,  1,  8],
 [ 1,  1,  1,  1,  1,  1, -1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida091_jogada026_vit_mm.png` — visualização com numeração de arestas
- `cnn1_partida091_jogada026_vit_mm.md` — este relatório
- `cnn1_partida091_jogada026_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida091_jogada026_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
