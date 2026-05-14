# Caixa perdida — partida 83, jogada 23

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_11_v8_5canais__20260513_202452`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 1 (CNN começou)
- **Placar parcial (CNN x Minimax):** **4 × 0**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (3,0)
- **Traço jogado pela CNN:** `H_8_3`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.---.---.
|         |     
.   .   .   .
     |         |
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
|[?]      |[C] |
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  1,  0,  0,  0,  1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [-1,  1,  1,  1,  1,  1,  1],
 [ 8,  1,  8,  1,  8, -1,  8],
 [ 1,  0,  0,  0,  1,  1,  1],
 [ 8,  1,  8,  0,  8, -1,  8]]
```
