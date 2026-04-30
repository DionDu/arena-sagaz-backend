# Caixa perdida — partida 0, jogada 25

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155310`
- **Adversário:** `Minimax(p=1)`
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
.---.   .---.
|[M] |    |     
.---.   .   .
|[M] |         |
.---.---.---.
|[C] |[?] |[C] |
.---.   .---.
|[C] |    |[C] |
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_3    |      0.971062 | ⭐ (Escolhida)  |
|   H_6_3    |      0.023979 |                |
|   V_1_6    |      0.001281 |                |
|   H_0_3    |      0.000781 |                |
|   H_2_5    |      0.000311 |                |
|   H_2_3    |      0.000295 |                |
|   V_7_6    |      0.000266 | (Indisponível) |
|   H_8_5    |      0.000252 | (Indisponível) |
|   H_0_5    |      0.000213 | (Indisponível) |
|   V_5_6    |      0.000201 | (Indisponível) |
|   V_3_6    |      0.000163 | (Indisponível) |
|   H_6_5    |      0.000121 | (Indisponível) |
|   V_5_2    |      0.000106 | (Indisponível) |
|   V_5_4    |      0.000096 | (Indisponível) |
|   V_1_4    |      0.000087 | (Indisponível) |
|   V_7_4    |      0.000087 | (Indisponível) |
|   H_0_1    |      0.000070 | (Indisponível) |
|   H_4_1    |      0.000066 | (Indisponível) |
|   V_5_0    |      0.000064 | (Indisponível) |
|   V_7_0    |      0.000064 | (Indisponível) |
|   H_4_3    |      0.000062 | (Indisponível) |
|   V_3_4    |      0.000056 |                |
|   H_4_5    |      0.000052 | (Indisponível) |
|   V_1_0    |      0.000051 | (Indisponível) |
|   V_3_0    |      0.000044 | (Indisponível) |
|   V_3_2    |      0.000043 | (Indisponível) |
|   V_1_2    |      0.000040 | (Indisponível) |
|   H_8_1    |      0.000035 | (Indisponível) |
|   V_7_2    |      0.000034 | (Indisponível) |
|   H_6_1    |      0.000011 | (Indisponível) |
|   H_2_1    |      0.000009 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  0,  8,  1,  8],
 [ 1,  1, -1,  0, -1,  0,  0],
 [ 8,  1,  8,  0,  8,  0,  8],
 [-1,  1, -1,  0,  0,  0,  1],
 [ 8,  1,  8,  1,  8,  1,  8],
 [-1, -1, -1,  0, -1, -1, -1],
 [ 8, -1,  8,  0,  8, -1,  8],
 [ 1, -1,  1,  0, -1, -1,  1],
 [ 8, -1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida000_jogada025_emp.png` — visualização com numeração de arestas
- `cnn2_partida000_jogada025_emp.md` — este relatório
- `cnn2_partida000_jogada025_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida000_jogada025_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
