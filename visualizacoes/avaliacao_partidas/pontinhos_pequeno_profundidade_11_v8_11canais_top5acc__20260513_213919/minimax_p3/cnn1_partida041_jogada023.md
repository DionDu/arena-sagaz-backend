# Caixa perdida — partida 41, jogada 23

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_11_v8_11canais_top5acc__20260513_213919`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)
- **Placar parcial (CNN x Minimax):** **3 × 1**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_1_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,0)
- **Traço jogado pela CNN:** `V_1_0`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.   .---.
*    |    |[M] |
.   .   .---.
|[?] |         |
.---.---.   .
|[C] |[C] |    |
.---.---.   .
|[C] |         |
.---.   .---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8,  0,  8, -1,  8],
 [ 0,  0,  1,  0, -1, -1,  1],
 [ 8,  0,  8,  0,  8, -1,  8],
 [ 1,  0, -1,  0,  0,  0, -1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [ 1,  1,  1,  1, -1,  0,  1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [-1,  1,  1,  0,  0,  0, -1],
 [ 8, -1,  8,  0,  8, -1,  8]]
```
