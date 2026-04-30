# Caixa perdida — partida 0, jogada 20

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **2** × **0** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_1` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,0)
- **Traço jogado pela CNN:** `H_0_1` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.***.   .---.
|    |    |     
.   .   .   .
|[?] |         |
.---.---.---.
|[C] |         |
.---.   .   .
|[C] |    |     
.---.   .---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_0_1    |      0.968463 | ⭐ (Escolhida)  |
|   H_2_1    |      0.024110 |                |
|   V_1_0    |      0.002936 | (Indisponível) |
|   H_0_3    |      0.000722 |                |
|   H_2_3    |      0.000357 |                |
|   H_8_3    |      0.000305 |                |
|   V_7_6    |      0.000277 |                |
|   V_3_2    |      0.000258 | (Indisponível) |
|   V_5_0    |      0.000210 | (Indisponível) |
|   V_5_4    |      0.000197 |                |
|   V_1_6    |      0.000193 |                |
|   H_6_3    |      0.000182 |                |
|   H_2_5    |      0.000169 |                |
|   V_3_6    |      0.000162 | (Indisponível) |
|   H_8_5    |      0.000142 | (Indisponível) |
|   H_6_5    |      0.000140 |                |
|   H_0_5    |      0.000130 | (Indisponível) |
|   V_5_2    |      0.000126 | (Indisponível) |
|   V_3_0    |      0.000123 | (Indisponível) |
|   V_3_4    |      0.000094 |                |
|   H_4_1    |      0.000092 | (Indisponível) |
|   V_5_6    |      0.000085 | (Indisponível) |
|   V_1_4    |      0.000080 | (Indisponível) |
|   H_4_5    |      0.000073 | (Indisponível) |
|   V_7_4    |      0.000073 | (Indisponível) |
|   H_6_1    |      0.000069 | (Indisponível) |
|   V_1_2    |      0.000057 | (Indisponível) |
|   V_7_0    |      0.000049 | (Indisponível) |
|   H_4_3    |      0.000048 | (Indisponível) |
|   V_7_2    |      0.000048 | (Indisponível) |
|   H_8_1    |      0.000029 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  0,  8,  0,  8,  1,  8],
 [ 1,  0, -1,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  1],
 [ 8,  1,  8,  1,  8,  1,  8],
 [-1, -1, -1,  0,  0,  0, -1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [ 1, -1,  1,  0, -1,  0,  0],
 [ 8, -1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida000_jogada020_emp.png` — visualização com numeração de arestas
- `cnn2_partida000_jogada020_emp.md` — este relatório
- `cnn2_partida000_jogada020_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida000_jogada020_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
