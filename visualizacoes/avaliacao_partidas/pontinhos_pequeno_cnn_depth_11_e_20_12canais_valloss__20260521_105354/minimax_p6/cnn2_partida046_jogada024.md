# Caixa perdida — partida 46, jogada 24

## Contexto
- **Avaliação:** `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss__20260521_105354`
- **Adversário:** `Minimax(p=6)`
- **Posição da CNN:** Jogador 2 (Minimax começou)
- **Placar parcial (CNN x Minimax):** **2 × 3**

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_0` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,1)
- **Traço jogado pela CNN:** `V_5_0`

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG: 🔵 azul = caixas da CNN · 🔴 vermelho = caixas do Minimax · 🟡 amarelo = caixa pronta cedida · 🟢 verde = traço efetivamente jogado.

```text
.---.---.---.
|[M] |[M] |[M] |
.---.---.---.
               |
.---.---.   .
*     [?] |    |
.---.---.   .
|[C] |[C] |     
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1,  1,  1,  1,  1,  1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [ 0,  0,  0,  0,  0,  0, -1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [ 0,  0,  0,  0,  1,  0, -1],
 [ 8,  1,  8,  1,  8,  0,  8],
 [ 1, -1, -1, -1, -1,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8]]
```
