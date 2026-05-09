# Caixa perdida — partida 27, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9_500mil_amostras_5_canais_sem_espelhamento__20260508_142506`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)
- **Placar parcial (CNN x Minimax):** **2 × 8**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,2)
- **Traço jogado pela CNN:** `V_5_6`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.---.---.
|[M] |[M] |[M] |
.---.---.---.
|[M] |[M] |[M] |
.---.---.---.
|[M] |[M] |    *
.---.---.   .
|[C] |[C] |[?] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  1,  8,  1,  8],
 [ 1, -1,  1, -1,  1, -1,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1, -1, -1, -1, -1, -1, -1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [-1, -1, -1, -1, -1,  0,  0],
 [ 8, -1,  8, -1,  8,  0,  8],
 [-1,  1,  1,  1,  1,  0, -1],
 [ 8,  1,  8, -1,  8,  1,  8]]
```
