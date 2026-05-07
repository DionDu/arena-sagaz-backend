# Caixa perdida — partida 107, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260505_140950`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)
- **Placar parcial (CNN x Minimax):** **6 × 4**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_3_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,0)
- **Traço jogado pela CNN:** `V_3_0`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
*    |[C] |[C] |
.   .---.---.
|[?] |[C] |[C] |
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1,  1, -1,  1, -1, -1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [ 0,  0, -1,  1, -1,  1,  1],
 [ 8,  0,  8,  1,  8,  1,  8],
 [ 1,  0,  1,  1,  1,  1,  1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1,  1, -1, -1, -1, -1, -1],
 [ 8,  1,  8,  1,  8,  1,  8]]
```
