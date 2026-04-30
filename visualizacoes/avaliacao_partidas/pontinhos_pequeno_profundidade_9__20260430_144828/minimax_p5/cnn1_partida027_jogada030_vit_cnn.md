# Caixa perdida — partida 27, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_144828`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **7** × **3** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,2)
- **Traço jogado pela CNN:** `H_8_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[C] |[C] |[M] |
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
|[M] |[C] |[?] |
.---.---.   .
|[C] |[C] |    |
.---.---.***.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_5    |      0.967608 | ⭐ (Escolhida)  |
|   H_6_5    |      0.031722 |                |
|   V_7_6    |      0.000192 | (Indisponível) |
|   H_4_5    |      0.000106 | (Indisponível) |
|   V_5_6    |      0.000093 | (Indisponível) |
|   V_5_4    |      0.000058 | (Indisponível) |
|   V_3_6    |      0.000030 | (Indisponível) |
|   H_4_1    |      0.000024 | (Indisponível) |
|   H_8_3    |      0.000020 | (Indisponível) |
|   H_2_5    |      0.000019 | (Indisponível) |
|   H_6_3    |      0.000018 | (Indisponível) |
|   V_7_2    |      0.000016 | (Indisponível) |
|   V_7_4    |      0.000015 | (Indisponível) |
|   V_1_6    |      0.000011 | (Indisponível) |
|   V_5_0    |      0.000009 | (Indisponível) |
|   H_0_5    |      0.000009 | (Indisponível) |
|   H_8_1    |      0.000009 | (Indisponível) |
|   H_0_1    |      0.000008 | (Indisponível) |
|   V_7_0    |      0.000007 | (Indisponível) |
|   V_1_0    |      0.000006 | (Indisponível) |
|   V_3_4    |      0.000004 | (Indisponível) |
|   V_5_2    |      0.000003 | (Indisponível) |
|   H_4_3    |      0.000003 | (Indisponível) |
|   V_3_0    |      0.000002 | (Indisponível) |
|   H_0_3    |      0.000002 | (Indisponível) |
|   V_1_2    |      0.000002 | (Indisponível) |
|   H_2_1    |      0.000002 | (Indisponível) |
|   V_3_2    |      0.000002 | (Indisponível) |
|   V_1_4    |      0.000001 | (Indisponível) |
|   H_6_1    |      0.000001 | (Indisponível) |
|   H_2_3    |      0.000001 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8,  1,  8],
 [ 1,  1,  1,  1, -1, -1, -1],
 [ 8,  1,  8,  1,  8, -1,  8],
 [-1, -1,  1,  1,  1,  1, -1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1, -1,  1,  1,  1,  0,  1],
 [ 8, -1,  8,  1,  8,  0,  8],
 [-1,  1,  1,  1,  1,  0,  1],
 [ 8, -1,  8,  1,  8,  0,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida027_jogada030_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida027_jogada030_vit_cnn.md` — este relatório
- `cnn1_partida027_jogada030_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida027_jogada030_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
