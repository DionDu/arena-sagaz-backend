# Caixa perdida — partida 1, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260429_222717`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 2 (Minimax começou)

## Placar
- **No momento da decisão:** CNN **9** × **1** Minimax
- **Final da partida:** CNN **9** × **3** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 9 × 3

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_5_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (1,2)
- **Traço jogado pela CNN:** `V_5_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[C] |[C] |[M] |
.---.---.---.
|[C] |[C] |[?] |
.---.---.   .
|[C] |[C] |    *
.---.---.---.
|[C] |[C] |[C] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 1, -1,  1, -1, -1,  1,  1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [-1, -1, -1, -1, -1,  0, -1],
 [ 8, -1,  8, -1,  8,  0,  8],
 [-1, -1, -1, -1, -1,  0,  0],
 [ 8,  1,  8, -1,  8, -1,  8],
 [-1, -1,  1, -1, -1, -1,  1],
 [ 8,  1,  8,  1,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn2_partida001_jogada030_vit_cnn.png` — visualização com numeração de arestas
- `cnn2_partida001_jogada030_vit_cnn.md` — este relatório
- `cnn2_partida001_jogada030_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn2_partida001_jogada030_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
