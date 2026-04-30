# Caixa perdida — partida 25, jogada 27

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **7** × **1** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,2)
- **Traço jogado pela CNN:** `V_3_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
|[C] |[C] |    *
.---.---.   .
|[C] |[C] |[?] |
.---.---.---.
          |[C] |
.---.   .---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_3_6    |      0.567585 | ⭐ (Escolhida)  |
|   H_4_5    |      0.421522 |                |
|   V_7_0    |      0.001485 |                |
|   V_7_2    |      0.001454 |                |
|   V_5_6    |      0.001041 | (Indisponível) |
|   H_8_3    |      0.000783 |                |
|   V_7_6    |      0.000642 | (Indisponível) |
|   H_2_5    |      0.000634 | (Indisponível) |
|   H_6_5    |      0.000579 | (Indisponível) |
|   H_8_5    |      0.000503 | (Indisponível) |
|   V_7_4    |      0.000499 | (Indisponível) |
|   H_8_1    |      0.000466 | (Indisponível) |
|   H_6_3    |      0.000334 | (Indisponível) |
|   V_5_4    |      0.000239 | (Indisponível) |
|   H_4_1    |      0.000220 | (Indisponível) |
|   H_6_1    |      0.000211 | (Indisponível) |
|   H_0_5    |      0.000203 | (Indisponível) |
|   V_1_6    |      0.000187 | (Indisponível) |
|   V_5_0    |      0.000184 | (Indisponível) |
|   H_0_1    |      0.000163 | (Indisponível) |
|   H_0_3    |      0.000145 | (Indisponível) |
|   V_5_2    |      0.000143 | (Indisponível) |
|   V_3_4    |      0.000139 | (Indisponível) |
|   V_1_0    |      0.000136 | (Indisponível) |
|   V_3_0    |      0.000127 | (Indisponível) |
|   V_1_2    |      0.000094 | (Indisponível) |
|   V_1_4    |      0.000088 | (Indisponível) |
|   H_2_1    |      0.000084 | (Indisponível) |
|   H_4_3    |      0.000039 | (Indisponível) |
|   V_3_2    |      0.000037 | (Indisponível) |
|   H_2_3    |      0.000034 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 1, -1, -1,  1, -1,  1,  1],
 [ 8, -1,  8,  1,  8,  1,  8],
 [ 1,  1,  1,  1, -1,  0,  0],
 [ 8, -1,  8,  1,  8,  0,  8],
 [ 1,  1,  1,  1,  1,  0,  1],
 [ 8,  1,  8,  1,  8,  1,  8],
 [ 0,  0,  0,  0,  1,  1, -1],
 [ 8, -1,  8,  0,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida025_jogada027_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida025_jogada027_vit_cnn.md` — este relatório
- `cnn1_partida025_jogada027_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida025_jogada027_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
