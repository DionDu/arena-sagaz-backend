# Caixa perdida — partida 44, jogada 25

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **4** × **2** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,1)
- **Traço jogado pela CNN:** `H_8_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.   .
|[C] |[C] |    |
.---.---.   .
|[M] |[C] |    |
.---.---.   .
|[M] |[?] |    |
.---.   .   .
|[C] |    |     
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_3    |      0.965949 | ⭐ (Escolhida)  |
|   H_6_3    |      0.029839 |                |
|   V_7_6    |      0.001322 |                |
|   H_0_5    |      0.000744 |                |
|   H_6_5    |      0.000388 |                |
|   H_2_5    |      0.000233 |                |
|   H_8_5    |      0.000222 | (Indisponível) |
|   V_1_6    |      0.000160 | (Indisponível) |
|   H_4_5    |      0.000142 |                |
|   V_3_6    |      0.000133 | (Indisponível) |
|   V_5_2    |      0.000109 | (Indisponível) |
|   V_5_4    |      0.000100 | (Indisponível) |
|   V_5_6    |      0.000078 | (Indisponível) |
|   V_7_4    |      0.000078 | (Indisponível) |
|   H_0_1    |      0.000071 | (Indisponível) |
|   V_5_0    |      0.000057 | (Indisponível) |
|   H_4_1    |      0.000057 | (Indisponível) |
|   V_1_0    |      0.000047 | (Indisponível) |
|   V_7_0    |      0.000040 | (Indisponível) |
|   V_3_0    |      0.000029 | (Indisponível) |
|   H_4_3    |      0.000028 | (Indisponível) |
|   H_0_3    |      0.000026 | (Indisponível) |
|   V_1_4    |      0.000024 | (Indisponível) |
|   H_8_1    |      0.000022 | (Indisponível) |
|   V_7_2    |      0.000019 | (Indisponível) |
|   V_3_4    |      0.000018 | (Indisponível) |
|   H_2_3    |      0.000015 | (Indisponível) |
|   V_3_2    |      0.000015 | (Indisponível) |
|   V_1_2    |      0.000013 | (Indisponível) |
|   H_2_1    |      0.000009 | (Indisponível) |
|   H_6_1    |      0.000009 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8, -1,  8,  0,  8],
 [-1, -1, -1, -1, -1,  0,  1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [-1,  1, -1, -1,  1,  0, -1],
 [ 8,  1,  8, -1,  8,  0,  8],
 [-1,  1, -1,  0,  1,  0, -1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [ 1, -1,  1,  0,  1,  0,  0],
 [ 8,  1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida044_jogada025_emp.png` — visualização com numeração de arestas
- `cnn2_partida044_jogada025_emp.md` — este relatório
- `cnn2_partida044_jogada025_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida044_jogada025_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
