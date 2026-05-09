# Caixa perdida — partida 37, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260508_145334`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)
- **Placar parcial (CNN x Minimax):** **6 × 4**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,1)
- **Traço jogado pela CNN:** `H_0_3`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.***.---.
|[M] |    |[C] |
.---.   .---.
|[M] |[?] |[C] |
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
|[M] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  0,  8,  1,  8],
 [ 1,  1, -1,  0,  1, -1, -1],
 [ 8, -1,  8,  0,  8,  1,  8],
 [ 1,  1, -1,  0, -1, -1, -1],
 [ 8,  1,  8,  1,  8, -1,  8],
 [-1,  1, -1, -1,  1, -1, -1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [ 1,  1,  1, -1, -1, -1, -1],
 [ 8,  1,  8,  1,  8, -1,  8]]
```
