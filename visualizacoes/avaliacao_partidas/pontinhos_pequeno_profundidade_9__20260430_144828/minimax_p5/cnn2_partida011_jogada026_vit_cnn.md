# Caixa perdida — partida 11, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **4** × **2** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

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
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
|[C] |         |
.---.   .   .
|[?] |         |
.   .---.---.
*    |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_7_0    |      0.927680 | ⭐ (Escolhida)  |
|   H_6_1    |      0.063186 |                |
|   H_8_1    |      0.001669 | (Indisponível) |
|   V_5_4    |      0.001146 |                |
|   H_4_5    |      0.001014 |                |
|   V_5_0    |      0.000919 | (Indisponível) |
|   H_4_3    |      0.000739 |                |
|   V_5_2    |      0.000486 | (Indisponível) |
|   V_3_4    |      0.000485 |                |
|   H_4_1    |      0.000266 | (Indisponível) |
|   V_7_2    |      0.000252 | (Indisponível) |
|   H_6_3    |      0.000223 | (Indisponível) |
|   H_8_3    |      0.000195 | (Indisponível) |
|   H_6_5    |      0.000192 | (Indisponível) |
|   V_7_4    |      0.000180 | (Indisponível) |
|   V_3_2    |      0.000180 | (Indisponível) |
|   H_8_5    |      0.000163 | (Indisponível) |
|   V_7_6    |      0.000156 | (Indisponível) |
|   V_5_6    |      0.000149 | (Indisponível) |
|   V_3_6    |      0.000137 | (Indisponível) |
|   V_3_0    |      0.000105 | (Indisponível) |
|   H_2_1    |      0.000082 | (Indisponível) |
|   H_0_1    |      0.000078 | (Indisponível) |
|   H_2_5    |      0.000066 | (Indisponível) |
|   V_1_0    |      0.000057 | (Indisponível) |
|   H_0_5    |      0.000046 | (Indisponível) |
|   H_2_3    |      0.000044 | (Indisponível) |
|   H_0_3    |      0.000041 | (Indisponível) |
|   V_1_2    |      0.000035 | (Indisponível) |
|   V_1_6    |      0.000021 | (Indisponível) |
|   V_1_4    |      0.000010 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  1,  8,  1,  8],
 [-1, -1, -1,  1, -1,  1,  1],
 [ 8,  1,  8,  1,  8, -1,  8],
 [-1, -1,  1,  0,  0,  0, -1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 0,  0, -1, -1, -1, -1,  1],
 [ 8,  1,  8,  1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida011_jogada026_vit_cnn.png` — visualização com numeração de arestas
- `cnn2_partida011_jogada026_vit_cnn.md` — este relatório
- `cnn2_partida011_jogada026_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida011_jogada026_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
