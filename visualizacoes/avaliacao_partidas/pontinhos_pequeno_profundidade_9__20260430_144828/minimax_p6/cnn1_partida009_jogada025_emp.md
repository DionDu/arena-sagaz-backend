# Caixa perdida — partida 9, jogada 25

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **2** × **2** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **2 caixas prontas** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_4` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1), (0,2)
- **Traço jogado pela CNN:** `V_3_4` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[M] |[?] |[?] |
.---.   .   .
|[M] |    *    |
.---.---.---.
|[C] |         |
.---.   .   .
|[C] |         |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_4    |      0.530704 | ⭐ (Escolhida)  |
|   H_2_5    |      0.314104 |                |
|   H_2_3    |      0.152304 |                |
|   H_0_5    |      0.000466 | (Indisponível) |
|   V_3_6    |      0.000414 | (Indisponível) |
|   V_1_6    |      0.000260 | (Indisponível) |
|   V_1_4    |      0.000215 | (Indisponível) |
|   V_1_2    |      0.000168 | (Indisponível) |
|   H_4_5    |      0.000164 | (Indisponível) |
|   H_0_3    |      0.000122 | (Indisponível) |
|   H_6_5    |      0.000114 |                |
|   H_6_3    |      0.000110 |                |
|   V_5_4    |      0.000109 |                |
|   V_7_4    |      0.000095 |                |
|   V_5_6    |      0.000094 | (Indisponível) |
|   H_8_5    |      0.000069 | (Indisponível) |
|   H_4_3    |      0.000065 | (Indisponível) |
|   H_4_1    |      0.000062 | (Indisponível) |
|   H_0_1    |      0.000055 | (Indisponível) |
|   V_3_2    |      0.000052 | (Indisponível) |
|   V_5_2    |      0.000043 | (Indisponível) |
|   H_8_3    |      0.000037 | (Indisponível) |
|   V_7_2    |      0.000036 | (Indisponível) |
|   V_1_0    |      0.000034 | (Indisponível) |
|   V_7_6    |      0.000033 | (Indisponível) |
|   V_5_0    |      0.000018 | (Indisponível) |
|   V_3_0    |      0.000013 | (Indisponível) |
|   H_2_1    |      0.000013 | (Indisponível) |
|   V_7_0    |      0.000012 | (Indisponível) |
|   H_6_1    |      0.000007 | (Indisponível) |
|   H_8_1    |      0.000006 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8, -1,  8, -1,  8],
 [-1, -1,  1,  0, -1,  0,  1],
 [ 8,  1,  8,  0,  8,  0,  8],
 [-1, -1,  1,  0,  0,  0,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1,  1,  1,  0,  0,  0,  1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [-1,  1,  1,  0,  0,  0,  1],
 [ 8,  1,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida009_jogada025_emp.png` — visualização com numeração de arestas
- `cnn1_partida009_jogada025_emp.md` — este relatório
- `cnn1_partida009_jogada025_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida009_jogada025_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
