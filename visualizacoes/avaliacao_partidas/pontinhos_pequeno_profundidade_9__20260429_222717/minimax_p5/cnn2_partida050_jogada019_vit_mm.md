# Caixa perdida — partida 50, jogada 19

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260429_222717`
- **Adversário:** `Minimax(p=5)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **0** × **1** Minimax
- **Final da partida:** CNN **5** × **7** Minimax
- **Resultado da partida:** **DERROTA da CNN** — placar final 5 × 7

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_0_5` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1)
- **Traço jogado pela CNN:** `H_0_5` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.***.
     |[?]      |
.   .---.---.
|    |          
.   .   .---.
|    |    |[M] |
.   .   .---.
|    |          
.   .---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8,  0,  8],
 [ 0,  0, -1,  0,  0,  0,  1],
 [ 8,  0,  8,  1,  8, -1,  8],
 [ 1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  1,  8],
 [-1,  0, -1,  0,  1,  1, -1],
 [ 8,  0,  8,  0,  8, -1,  8],
 [ 1,  0,  1,  0,  0,  0,  0],
 [ 8,  0,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida050_jogada019_vit_mm.png` — visualização com numeração de arestas
- `cnn2_partida050_jogada019_vit_mm.md` — este relatório
- `cnn2_partida050_jogada019_vit_mm_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida050_jogada019_vit_mm_crua.npy` — matriz crua (encoding partida bruto, NumPy)
