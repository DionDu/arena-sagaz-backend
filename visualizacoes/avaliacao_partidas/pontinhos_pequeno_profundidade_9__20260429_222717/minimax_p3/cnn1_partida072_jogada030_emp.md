# Caixa perdida — partida 72, jogada 30

## Contexto
- **Avaliação:** `pontinhos_pequeno_profundidade_9__20260429_222717`
- **Adversário:** `Minimax(p=3)`
- **Posição da CNN:** Jogador 1 (CNN começou)

## Placar
- **No momento da decisão:** CNN **6** × **4** Minimax
- **Final da partida:** CNN **6** × **6** Minimax
- **Resultado da partida:** **EMPATE** — placar final 6 × 6

## O que aconteceu
A CNN tinha **1 caixa pronta** (3 arestas preenchidas) disponíveis para fechar, mas escolheu jogar `V_1_6` — uma jogada que NÃO fecha caixa, cedendo o fechamento ao Minimax.

- **Caixa(s) pronta(s) — coords (linha, coluna):** (0,1)
- **Traço jogado pela CNN:** `V_1_6` (destacado em verde no PNG; ainda não estava marcado na matriz capturada)

## Visão do tabuleiro (ANTES da jogada da CNN)

Legenda PNG:
- 🔵 azul = caixas e números das arestas marcadas pela CNN
- 🔴 vermelho = caixas e números das arestas marcadas pelo Minimax
- 🟡 amarelo = caixa pronta cedida (3 arestas preenchidas)
- 🟢 verde = traço que a CNN está prestes a jogar (não numerado, pois ainda não foi aplicado)

Os números nas arestas cinza indicam a ordem cronológica em que cada traço foi marcado durante a partida (`0` = primeiro traço; números crescem ao longo da partida).

```text
.---.---.---.
|[C] |[?]      *
.---.---.---.
|[C] |[C] |[M] |
.---.---.---.
|[C] |[C] |[M] |
.---.---.---.
|[C] |[M] |[M] |
.---.---.---.
```

Legenda ASCII: `[C]` = caixa CNN · `[M]` = caixa Minimax · `[?]` = caixa pronta cedida · `***`/`*` = traço escolhido pela CNN.

## Matriz crua (estado ANTES da jogada da CNN)

```text
[[ 8, -1,  8,  1,  8, -1,  8],
 [ 1,  1,  1,  0,  0,  0,  0],
 [ 8, -1,  8,  1,  8,  1,  8],
 [-1,  1,  1,  1,  1, -1,  1],
 [ 8,  1,  8, -1,  8, -1,  8],
 [ 1,  1,  1,  1,  1, -1,  1],
 [ 8, -1,  8, -1,  8,  1,  8],
 [-1,  1, -1, -1,  1, -1, -1],
 [ 8,  1,  8, -1,  8, -1,  8]]
```

## Arquivos gerados nesta amostra
- `cnn1_partida072_jogada030_emp.png` — visualização com numeração de arestas
- `cnn1_partida072_jogada030_emp.md` — este relatório
- `cnn1_partida072_jogada030_emp_norm.npy` — matriz normalizada (input da CNN, NumPy)
- `cnn1_partida072_jogada030_emp_crua.npy` — matriz crua (encoding partida bruto, NumPy)
