# Caixa perdida — partida 76, jogada 26

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **5** × **2** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,2)
- **Traço jogado pela CNN:** `H_8_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
                
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
|[C] |[C] |[?] |
.---.---.   .
|[C] |[C] |    |
.---.---.***.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_8_5    |      0.919447 | ⭐ (Escolhida)  |
|   H_6_5    |      0.072040 |                |
|   V_1_6    |      0.001902 |                |
|   V_1_0    |      0.001494 |                |
|   V_1_2    |      0.001267 |                |
|   V_1_4    |      0.000883 |                |
|   V_7_6    |      0.000551 | (Indisponível) |
|   V_5_6    |      0.000334 | (Indisponível) |
|   H_0_1    |      0.000273 | (Indisponível) |
|   H_2_5    |      0.000263 | (Indisponível) |
|   H_4_5    |      0.000240 | (Indisponível) |
|   H_0_5    |      0.000240 | (Indisponível) |
|   V_5_4    |      0.000180 | (Indisponível) |
|   V_3_6    |      0.000117 | (Indisponível) |
|   H_0_3    |      0.000103 | (Indisponível) |
|   H_4_1    |      0.000089 | (Indisponível) |
|   H_6_3    |      0.000073 | (Indisponível) |
|   H_8_3    |      0.000070 | (Indisponível) |
|   V_7_4    |      0.000069 | (Indisponível) |
|   H_2_1    |      0.000054 | (Indisponível) |
|   V_5_0    |      0.000051 | (Indisponível) |
|   V_7_2    |      0.000044 | (Indisponível) |
|   V_7_0    |      0.000035 | (Indisponível) |
|   H_2_3    |      0.000034 | (Indisponível) |
|   H_8_1    |      0.000029 | (Indisponível) |
|   H_4_3    |      0.000025 | (Indisponível) |
|   V_3_4    |      0.000023 | (Indisponível) |
|   V_3_0    |      0.000022 | (Indisponível) |
|   V_5_2    |      0.000020 | (Indisponível) |
|   V_3_2    |      0.000018 | (Indisponível) |
|   H_6_1    |      0.000010 | (Indisponível) |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 1,  1, -1, -1,  1, -1,  1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [ 1,  1,  1,  1,  1,  0, -1],
 [ 8, -1,  8,  1,  8,  0,  8],
 [ 1,  1,  1,  1,  1,  0,  1],
 [ 8, -1,  8,  1,  8,  0,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida076_jogada026_emp.png` — visualização com numeração de arestas
- `cnn1_partida076_jogada026_emp.md` — este relatório
- `cnn1_partida076_jogada026_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida076_jogada026_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
