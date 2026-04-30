# Caixa perdida — partida 83, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **5** × **2** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,1)
- **Traço jogado pela CNN:** `V_3_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
|[C] |[?]      *
.---.---.---.
|[M] |          
.---.   .---.
|[M] |    |[C] |
.---.   .---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_6    |      0.966159 | ⭐ (Escolhida)  |
|   V_3_4    |      0.030105 |                |
|   V_5_6    |      0.001457 |                |
|   V_5_4    |      0.000314 |                |
|   H_8_3    |      0.000273 |                |
|   H_6_5    |      0.000178 | (Indisponível) |
|   H_6_3    |      0.000173 |                |
|   V_7_6    |      0.000096 | (Indisponível) |
|   H_8_5    |      0.000095 | (Indisponível) |
|   H_0_1    |      0.000093 | (Indisponível) |
|   V_3_2    |      0.000093 | (Indisponível) |
|   H_2_3    |      0.000075 | (Indisponível) |
|   V_5_0    |      0.000068 | (Indisponível) |
|   H_4_1    |      0.000066 | (Indisponível) |
|   V_7_4    |      0.000065 | (Indisponível) |
|   H_4_3    |      0.000064 | (Indisponível) |
|   V_5_2    |      0.000062 | (Indisponível) |
|   H_4_5    |      0.000061 | (Indisponível) |
|   V_3_0    |      0.000060 | (Indisponível) |
|   V_1_0    |      0.000057 | (Indisponível) |
|   H_0_3    |      0.000056 | (Indisponível) |
|   H_2_1    |      0.000049 | (Indisponível) |
|   V_7_2    |      0.000046 | (Indisponível) |
|   V_1_6    |      0.000042 | (Indisponível) |
|   H_0_5    |      0.000038 | (Indisponível) |
|   H_2_5    |      0.000036 | (Indisponível) |
|   V_1_2    |      0.000032 | (Indisponível) |
|   V_7_0    |      0.000031 | (Indisponível) |
|   H_8_1    |      0.000021 | (Indisponível) |
|   V_1_4    |      0.000017 | (Indisponível) |
|   H_6_1    |      0.000016 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1,  1,  1,  1,  1,  1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1, -1,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1, -1,  1,  0,  0,  0,  0],
 [ 8,  1,  8,  0,  8,  1,  8],
 [ 1, -1, -1,  0,  1,  1, -1],
 [ 8, -1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida083_jogada026_emp.png` — visualização com numeração de arestas
- `cnn1_partida083_jogada026_emp.md` — este relatório
- `cnn1_partida083_jogada026_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida083_jogada026_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
