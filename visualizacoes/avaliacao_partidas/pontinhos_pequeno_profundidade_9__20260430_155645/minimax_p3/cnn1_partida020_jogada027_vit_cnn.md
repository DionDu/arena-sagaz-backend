# Caixa perdida — partida 20, jogada 27

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **7** × **1** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,0)
- **Traço jogado pela CNN:** `V_3_0` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas fechadas e arestas marcadas pela CNN
- 🟠 laranja = caixas fechadas e arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = aresta que a CNN está prestes a marcar (não numerada, pois ainda não foi aplicada)
- ⚪ círculos cinza-claros = vértices · linhas pontilhadas = arestas ainda não jogadas
- réguas (números cinza-escuros) = índices da matriz `(linha, coluna)` em todos os 4 lados

Cada aresta marcada exibe um número branco no centro: a ordem cronológica em que foi jogada (`0` = primeiro traço da partida; números crescem ao longo da partida).

```text
.---.   .---.
          |[M] |
.---.---.---.
*    |[C] |[C] |
.   .---.---.
|[?] |[C] |[C] |
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_0    |      0.637363 | ⭐ (Escolhida)  |
|   H_4_1    |      0.354356 |                |
|   V_1_0    |      0.002479 |                |
|   V_1_2    |      0.001494 |                |
|   H_0_3    |      0.000814 |                |
|   H_0_1    |      0.000505 | (Indisponível) |
|   H_2_1    |      0.000477 | (Indisponível) |
|   V_5_0    |      0.000372 | (Indisponível) |
|   V_3_2    |      0.000235 | (Indisponível) |
|   H_6_1    |      0.000195 | (Indisponível) |
|   V_5_2    |      0.000185 | (Indisponível) |
|   V_1_4    |      0.000143 | (Indisponível) |
|   H_0_5    |      0.000119 | (Indisponível) |
|   V_3_6    |      0.000112 | (Indisponível) |
|   V_7_0    |      0.000105 | (Indisponível) |
|   V_7_6    |      0.000100 | (Indisponível) |
|   H_2_5    |      0.000099 | (Indisponível) |
|   H_8_1    |      0.000096 | (Indisponível) |
|   H_8_3    |      0.000090 | (Indisponível) |
|   H_8_5    |      0.000083 | (Indisponível) |
|   H_6_5    |      0.000082 | (Indisponível) |
|   V_1_6    |      0.000078 | (Indisponível) |
|   V_5_6    |      0.000069 | (Indisponível) |
|   H_2_3    |      0.000068 | (Indisponível) |
|   V_7_4    |      0.000066 | (Indisponível) |
|   H_4_5    |      0.000052 | (Indisponível) |
|   V_7_2    |      0.000046 | (Indisponível) |
|   H_6_3    |      0.000042 | (Indisponível) |
|   V_5_4    |      0.000033 | (Indisponível) |
|   H_4_3    |      0.000023 | (Indisponível) |
|   V_3_4    |      0.000018 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  0,  8,  1,  8],
 [ 0,  0,  0,  0, -1, -1, -1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [ 0,  0,  1,  1,  1,  1,  1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 1,  0,  1,  1,  1,  1, -1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1,  1,  1, -1,  1, -1],
 [ 8, -1,  8, -1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida020_jogada027_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida020_jogada027_vit_cnn.md` — este relatório
- `cnn1_partida020_jogada027_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida020_jogada027_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
