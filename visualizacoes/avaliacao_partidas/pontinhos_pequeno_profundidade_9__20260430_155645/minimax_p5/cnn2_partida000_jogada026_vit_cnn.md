# Caixa perdida — partida 0, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **5** × **1** Minimax
- **Final da partida:** CNN **9** × **3** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 9 × 3

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,0)
- **Traço jogado pela CNN:** `H_8_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
|[C] |[C] |[C] |
.---.---.---.
|[C] |         |
.---.   .   .
|[C] |         |
.---.---.---.
|[?]      |[M] |
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_3    |      0.975104 | ⭐ (Escolhida)  |
|   V_7_2    |      0.023798 |                |
|   V_7_0    |      0.000164 | (Indisponível) |
|   V_7_4    |      0.000140 | (Indisponível) |
|   V_5_4    |      0.000106 |                |
|   H_8_5    |      0.000087 | (Indisponível) |
|   H_8_1    |      0.000072 | (Indisponível) |
|   H_4_3    |      0.000061 |                |
|   H_4_5    |      0.000058 |                |
|   V_7_6    |      0.000056 | (Indisponível) |
|   H_6_5    |      0.000046 | (Indisponível) |
|   V_5_6    |      0.000038 | (Indisponível) |
|   V_3_6    |      0.000038 | (Indisponível) |
|   H_6_3    |      0.000037 | (Indisponível) |
|   V_3_4    |      0.000031 |                |
|   H_0_1    |      0.000021 | (Indisponível) |
|   H_4_1    |      0.000019 | (Indisponível) |
|   V_1_0    |      0.000016 | (Indisponível) |
|   H_6_1    |      0.000013 | (Indisponível) |
|   V_5_2    |      0.000013 | (Indisponível) |
|   H_2_3    |      0.000013 | (Indisponível) |
|   V_1_6    |      0.000012 | (Indisponível) |
|   H_0_5    |      0.000012 | (Indisponível) |
|   H_0_3    |      0.000011 | (Indisponível) |
|   V_5_0    |      0.000009 | (Indisponível) |
|   V_3_2    |      0.000007 | (Indisponível) |
|   H_2_5    |      0.000007 | (Indisponível) |
|   V_3_0    |      0.000005 | (Indisponível) |
|   V_1_2    |      0.000003 | (Indisponível) |
|   V_1_4    |      0.000003 | (Indisponível) |
|   H_2_1    |      0.000002 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 1, -1, -1, -1, -1, -1,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1, -1, -1,  0,  0,  0,  1],
 [ 8, -1,  8,  0,  8,  0,  8],
 [-1, -1, -1,  0,  0,  0,  1],
 [ 8, -1,  8,  1,  8, -1,  8],
 [ 1,  0,  0,  0, -1,  1,  1],
 [ 8,  1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida000_jogada026_vit_cnn.png` — visualização com numeração de arestas
- `cnn2_partida000_jogada026_vit_cnn.md` — este relatório
- `cnn2_partida000_jogada026_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida000_jogada026_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
