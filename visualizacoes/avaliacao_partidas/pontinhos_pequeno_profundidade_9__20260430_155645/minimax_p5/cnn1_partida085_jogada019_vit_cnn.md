# Caixa perdida — partida 85, jogada 19

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **0** × **0** Minimax
- **Final da partida:** CNN **8** × **4** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 8 × 4

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,2)
- **Traço jogado pela CNN:** `H_0_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
.   .***.---.
|    |     [?] |
.   .---.---.
|    |         |
.   .   .   .
|    |    |    |
.   .   .   .
|    |         |
.   .---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_0_3    |      0.946950 | ⭐ (Escolhida)  |
|   V_1_4    |      0.051511 |                |
|   H_0_1    |      0.000355 |                |
|   V_1_6    |      0.000219 | (Indisponível) |
|   H_0_5    |      0.000219 | (Indisponível) |
|   H_2_1    |      0.000185 |                |
|   V_1_0    |      0.000089 | (Indisponível) |
|   H_8_1    |      0.000043 |                |
|   V_1_2    |      0.000041 | (Indisponível) |
|   H_2_5    |      0.000041 | (Indisponível) |
|   H_4_1    |      0.000040 |                |
|   H_6_1    |      0.000038 |                |
|   V_3_0    |      0.000034 | (Indisponível) |
|   V_3_6    |      0.000033 | (Indisponível) |
|   V_7_6    |      0.000024 | (Indisponível) |
|   V_5_6    |      0.000017 | (Indisponível) |
|   H_4_5    |      0.000017 |                |
|   V_7_0    |      0.000017 | (Indisponível) |
|   V_5_0    |      0.000016 | (Indisponível) |
|   V_7_4    |      0.000016 |                |
|   H_8_5    |      0.000013 | (Indisponível) |
|   V_3_2    |      0.000012 | (Indisponível) |
|   H_6_5    |      0.000011 |                |
|   H_2_3    |      0.000011 | (Indisponível) |
|   H_8_3    |      0.000011 | (Indisponível) |
|   H_6_3    |      0.000008 |                |
|   V_3_4    |      0.000007 |                |
|   V_7_2    |      0.000007 | (Indisponível) |
|   H_4_3    |      0.000006 |                |
|   V_5_2    |      0.000005 | (Indisponível) |
|   V_5_4    |      0.000005 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  0,  8,  0,  8, -1,  8],
 [-1,  0,  1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  1,  8],
 [ 1,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  1,  0, -1,  0,  1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida085_jogada019_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida085_jogada019_vit_cnn.md` — este relatório
- `cnn1_partida085_jogada019_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida085_jogada019_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
