# Caixa perdida — partida 31, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260429_222717`
- **Adversário:** `Minimax(p=1)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **7** × **3** Minimax
- **Final da partida:** CNN **7** × **5** Minimax
- **Resultado da partida:** **VITÓRIA da CNN** — placar final 7 × 5

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `H_8_3` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (2,1)
- **Traço jogado pela CNN:** `H_8_3` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[C] |[M] |[C] |
.---.---.---.
|[C] |[M] |[C] |
.---.---.---.
|[C] |[?] |[C] |
.---.   .---.
|[M] |    |[C] |
.---.***.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [-1,  1, -1, -1,  1,  1, -1],
 [ 8,  1,  8, -1,  8,  1,  8],
 [-1,  1,  1, -1, -1,  1,  1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [ 1,  1,  1,  0, -1,  1,  1],
 [ 8,  1,  8,  0,  8,  1,  8],
 [ 1, -1,  1,  0,  1,  1,  1],
 [ 8, -1,  8,  0,  8,  1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida031_jogada030_vit_cnn.png` — visualização com numeração de arestas
- `cnn1_partida031_jogada030_vit_cnn.md` — este relatório
- `cnn1_partida031_jogada030_vit_cnn_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida031_jogada030_vit_cnn_crua.npy` — matriz crua (encoding partida bruto, NumPy)
