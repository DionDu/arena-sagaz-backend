# Caixa perdida — partida 37, jogada 19

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **0** × **0** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,2)
- **Traço jogado pela CNN:** `H_8_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|               
.   .---.---.
|    |         |
.   .   .   .
|    |         |
.   .---.---.
     |     [?] |
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_3    |      0.877269 | ⭐ (Escolhida)  |
|   V_7_4    |      0.119669 |                |
|   V_5_4    |      0.000316 |                |
|   H_8_5    |      0.000236 | (Indisponível) |
|   V_7_0    |      0.000230 |                |
|   H_4_3    |      0.000197 |                |
|   V_7_6    |      0.000189 | (Indisponível) |
|   H_4_5    |      0.000175 |                |
|   V_1_6    |      0.000166 |                |
|   H_6_5    |      0.000157 | (Indisponível) |
|   H_6_3    |      0.000146 | (Indisponível) |
|   V_5_6    |      0.000139 | (Indisponível) |
|   H_0_1    |      0.000113 | (Indisponível) |
|   H_0_5    |      0.000112 | (Indisponível) |
|   V_3_6    |      0.000111 | (Indisponível) |
|   V_3_4    |      0.000094 |                |
|   V_1_0    |      0.000072 | (Indisponível) |
|   H_8_1    |      0.000066 | (Indisponível) |
|   H_4_1    |      0.000062 |                |
|   V_1_4    |      0.000060 |                |
|   H_2_5    |      0.000052 | (Indisponível) |
|   V_5_2    |      0.000051 | (Indisponível) |
|   H_0_3    |      0.000049 | (Indisponível) |
|   H_6_1    |      0.000045 |                |
|   V_7_2    |      0.000044 | (Indisponível) |
|   V_1_2    |      0.000043 |                |
|   H_2_3    |      0.000041 | (Indisponível) |
|   V_5_0    |      0.000030 | (Indisponível) |
|   V_3_2    |      0.000025 | (Indisponível) |
|   V_3_0    |      0.000021 | (Indisponível) |
|   H_2_1    |      0.000019 |                |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8, -1,  8,  1,  8],
 [-1,  0,  1,  0,  0,  0,  1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  1,  0,  0,  0,  1],
 [ 8,  0,  8, -1,  8, -1,  8],
 [ 0,  0, -1,  0,  0,  0,  1],
 [ 8, -1,  8,  0,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida037_jogada019_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida037_jogada019_vit_cnn.md` — este relatório
- `cnn1_partida037_jogada019_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida037_jogada019_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
