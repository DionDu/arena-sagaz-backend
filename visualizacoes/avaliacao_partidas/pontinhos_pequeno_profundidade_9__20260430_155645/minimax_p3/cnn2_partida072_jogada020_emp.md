# Caixa perdida — partida 72, jogada 20

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260430_155645`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **0** × **0** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **2 caixas prontas** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_2_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1), (1,1)
- **Traço jogado pela CNN:** `H_2_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

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
     |[?]      |
.   .---.***.
|    |[?]      |
.   .---.---.
|    |         |
.   .   .   .
|         |    |
.---.---.   .
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.


## Probabilidades da CNN para cada traço

Distribuição de probabilidade que a CNN atribuiu a cada traço neste estado, ordenada de forma decrescente. A linha marcada com ⭐ é a jogada que a CNN efetivamente escolheu (filtrada apenas entre as disponíveis); traços já marcados no tabuleiro aparecem como "Indisponível".

|   Traço    | Probabilidade |   Escolhida?   |
|:----------:|:-------------:|:--------------:|
|   H_2_5    |      0.870023 | ⭐ (Escolhida)  |
|   V_3_4    |      0.065168 |                |
|   V_1_4    |      0.063391 |                |
|   H_2_3    |      0.000213 | (Indisponível) |
|   V_3_6    |      0.000187 | (Indisponível) |
|   V_1_6    |      0.000176 | (Indisponível) |
|   H_0_5    |      0.000108 | (Indisponível) |
|   V_1_2    |      0.000101 | (Indisponível) |
|   H_4_3    |      0.000082 | (Indisponível) |
|   H_0_1    |      0.000062 | (Indisponível) |
|   H_0_3    |      0.000060 | (Indisponível) |
|   V_1_0    |      0.000052 |                |
|   H_4_1    |      0.000051 |                |
|   H_4_5    |      0.000046 | (Indisponível) |
|   V_3_2    |      0.000046 | (Indisponível) |
|   H_8_5    |      0.000034 |                |
|   H_6_5    |      0.000027 |                |
|   V_5_4    |      0.000026 |                |
|   V_5_6    |      0.000021 | (Indisponível) |
|   H_6_3    |      0.000019 |                |
|   H_2_1    |      0.000019 |                |
|   V_7_6    |      0.000016 | (Indisponível) |
|   V_7_4    |      0.000012 | (Indisponível) |
|   V_5_2    |      0.000011 | (Indisponível) |
|   H_8_3    |      0.000010 | (Indisponível) |
|   V_5_0    |      0.000010 | (Indisponível) |
|   V_3_0    |      0.000009 | (Indisponível) |
|   V_7_0    |      0.000008 | (Indisponível) |
|   V_7_2    |      0.000008 |                |
|   H_8_1    |      0.000004 | (Indisponível) |
|   H_6_1    |      0.000004 |                |

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 0,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8,  1,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8, -1,  8,  1,  8],
 [-1,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 1,  0,  0,  0,  1,  0,  1],
 [ 8,  1,  8,  1,  8,  0,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida072_jogada020_emp.png` — visualização com numeração de arestas
- `cnn2_partida072_jogada020_emp.md` — este relatório
- `cnn2_partida072_jogada020_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida072_jogada020_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
