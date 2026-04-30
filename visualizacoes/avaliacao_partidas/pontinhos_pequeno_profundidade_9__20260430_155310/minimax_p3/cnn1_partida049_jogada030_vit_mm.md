# Caixa perdida — partida 49, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **5** × **5** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

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
|[M] |[?]      *
.---.---.---.
|[M] |[C] |[M] |
.---.---.---.
|[M] |[C] |[M] |
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_1_6    |      0.971751 | ⭐ (Escolhida)  |
|   V_1_4    |      0.025795 |                |
|   H_0_5    |      0.001936 | (Indisponível) |
|   H_0_3    |      0.000210 | (Indisponível) |
|   V_1_2    |      0.000062 | (Indisponível) |
|   H_0_1    |      0.000038 | (Indisponível) |
|   V_3_6    |      0.000030 | (Indisponível) |
|   V_1_0    |      0.000024 | (Indisponível) |
|   H_2_3    |      0.000019 | (Indisponível) |
|   H_8_5    |      0.000017 | (Indisponível) |
|   H_2_5    |      0.000015 | (Indisponível) |
|   H_4_1    |      0.000015 | (Indisponível) |
|   H_8_3    |      0.000010 | (Indisponível) |
|   V_7_6    |      0.000009 | (Indisponível) |
|   V_7_4    |      0.000009 | (Indisponível) |
|   H_6_5    |      0.000007 | (Indisponível) |
|   H_4_5    |      0.000007 | (Indisponível) |
|   V_5_6    |      0.000006 | (Indisponível) |
|   V_5_0    |      0.000005 | (Indisponível) |
|   V_3_0    |      0.000005 | (Indisponível) |
|   H_2_1    |      0.000005 | (Indisponível) |
|   V_3_4    |      0.000004 | (Indisponível) |
|   V_7_0    |      0.000003 | (Indisponível) |
|   H_6_3    |      0.000003 | (Indisponível) |
|   V_5_4    |      0.000003 | (Indisponível) |
|   V_3_2    |      0.000003 | (Indisponível) |
|   H_8_1    |      0.000003 | (Indisponível) |
|   V_5_2    |      0.000002 | (Indisponível) |
|   V_7_2    |      0.000002 | (Indisponível) |
|   H_4_3    |      0.000002 | (Indisponível) |
|   H_6_1    |      0.000001 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8, -1,  8],
 [-1, -1,  1,  0,  0,  0,  0],
 [ 8, -1,  8,  1,  8,  1,  8],
 [ 1, -1,  1,  1, -1, -1, -1],
 [ 8, -1,  8,  1,  8,  1,  8],
 [ 1, -1,  1,  1,  1, -1, -1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1, -1,  1, -1,  1, -1],
 [ 8, -1,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida049_jogada030_vit_mm.png` — visualização com numeração de arestas
- `cnn1_partida049_jogada030_vit_mm.md` — este relatório
- `cnn1_partida049_jogada030_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida049_jogada030_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
