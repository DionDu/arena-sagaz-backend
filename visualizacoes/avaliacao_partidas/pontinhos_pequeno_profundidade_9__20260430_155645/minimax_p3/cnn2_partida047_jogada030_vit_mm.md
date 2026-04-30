# Caixa perdida — partida 47, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **4** × **6** Minimax
- **Final da partida:** CNN **4** × **8** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 4 × 8

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,2)
- **Traço jogado pela CNN:** `V_5_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
|[M] |[M] |[M] |
.---.---.---.
|[M] |[C] |[?] |
.---.---.   .
|[M] |[C] |    *
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   V_5_6    |      0.961687 | ⭐ (Escolhida)  |
|   H_4_5    |      0.037995 |                |
|   V_3_6    |      0.000091 | (Indisponível) |
|   H_6_5    |      0.000047 | (Indisponível) |
|   H_8_5    |      0.000032 | (Indisponível) |
|   V_7_6    |      0.000030 | (Indisponível) |
|   V_5_4    |      0.000022 | (Indisponível) |
|   H_2_5    |      0.000018 | (Indisponível) |
|   V_7_4    |      0.000017 | (Indisponível) |
|   H_0_5    |      0.000006 | (Indisponível) |
|   H_0_1    |      0.000006 | (Indisponível) |
|   H_6_3    |      0.000005 | (Indisponível) |
|   V_7_0    |      0.000005 | (Indisponível) |
|   V_1_6    |      0.000005 | (Indisponível) |
|   V_1_0    |      0.000004 | (Indisponível) |
|   H_8_3    |      0.000004 | (Indisponível) |
|   H_8_1    |      0.000004 | (Indisponível) |
|   H_4_1    |      0.000004 | (Indisponível) |
|   V_7_2    |      0.000003 | (Indisponível) |
|   V_5_0    |      0.000003 | (Indisponível) |
|   V_3_4    |      0.000002 | (Indisponível) |
|   H_0_3    |      0.000002 | (Indisponível) |
|   V_5_2    |      0.000002 | (Indisponível) |
|   V_1_2    |      0.000001 | (Indisponível) |
|   V_3_0    |      0.000001 | (Indisponível) |
|   V_1_4    |      0.000001 | (Indisponível) |
|   H_2_1    |      0.000001 | (Indisponível) |
|   H_6_1    |      0.000001 | (Indisponível) |
|   H_4_3    |      0.000001 | (Indisponível) |
|   H_2_3    |      0.000000 | (Indisponível) |
|   V_3_2    |      0.000000 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8,  1,  8],
 [-1,  1,  1,  1,  1,  1,  1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [ 1,  1, -1, -1, -1,  0,  1],
 [ 8,  1,  8, -1,  8,  0,  8],
 [-1,  1, -1, -1,  1,  0,  0],
 [ 8,  1,  8, -1,  8,  1,  8],
 [ 1,  1, -1, -1,  1, -1,  1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida047_jogada030_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida047_jogada030_vit_mm.md` — este relatório
- `cnn2_partida047_jogada030_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida047_jogada030_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
