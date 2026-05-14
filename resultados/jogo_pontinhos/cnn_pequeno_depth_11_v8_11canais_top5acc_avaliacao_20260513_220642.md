
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-13 21:39 |
| Modelo | `pontinhos_pequeno_profundidade_11_v8_11canais_top5acc.tflite` |
| Canais (11) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 3 (1.5%)  | 4 (2.0%)     | 0.19        | 0.2        | 1×              | 34/1986 (1.7%)  |
| Minimax(p=3) | 200      | 154 (77.0%)  | 12 (6.0%) | 34 (17.0%)   | 0.24        | 79.8       | 332×            | 89/1539 (5.8%)  |
| Minimax(p=5) | 200      | 134 (67.0%)  | 14 (7.0%) | 52 (26.0%)   | 0.26        | 1561.2     | 6092×           | 108/1409 (7.7%) |
| Minimax(p=6) | 200      | 100 (50.0%)  | 9 (4.5%)  | 91 (45.5%)   | 0.26        | 4924.2     | 18613×          | 72/1191 (6.0%)  |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 4 (2.0%) |
| Tempo médio CNN | 0.19 ms/jogada |
| Tempo médio Minimax | 0.2 ms/jogada |
| CNN é mais rápida | 1× |
| Caixas cedidas ao Minimax | 34/1986 (1.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 154 (77.0%) |
| Empates | 12 (6.0%) |
| Derrotas CNN | 34 (17.0%) |
| Tempo médio CNN | 0.24 ms/jogada |
| Tempo médio Minimax | 79.8 ms/jogada |
| CNN é mais rápida | 332× |
| Caixas cedidas ao Minimax | 89/1539 (5.8%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 134 (67.0%) |
| Empates | 14 (7.0%) |
| Derrotas CNN | 52 (26.0%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 1561.2 ms/jogada |
| CNN é mais rápida | 6092× |
| Caixas cedidas ao Minimax | 108/1409 (7.7%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 100 (50.0%) |
| Empates | 9 (4.5%) |
| Derrotas CNN | 91 (45.5%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 4924.2 ms/jogada |
| CNN é mais rápida | 18613× |
| Caixas cedidas ao Minimax | 72/1191 (6.0%) |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 3 (1.5%)  | 4 (2.0%)     | 0.19        | 0.2        | 1×              | 34/1986 (1.7%)  |
| Minimax(p=3) | 200      | 154 (77.0%)  | 12 (6.0%) | 34 (17.0%)   | 0.24        | 79.8       | 332×            | 89/1539 (5.8%)  |
| Minimax(p=5) | 200      | 134 (67.0%)  | 14 (7.0%) | 52 (26.0%)   | 0.26        | 1561.2     | 6092×           | 108/1409 (7.7%) |
| Minimax(p=6) | 200      | 100 (50.0%)  | 9 (4.5%)  | 91 (45.5%)   | 0.26        | 4924.2     | 18613×          | 72/1191 (6.0%)  |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 4 (2.0%) |
| Tempo médio CNN | 0.19 ms/jogada |
| Tempo médio Minimax | 0.2 ms/jogada |
| CNN é mais rápida | 1× |
| Caixas cedidas ao Minimax | 34/1986 (1.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 154 (77.0%) |
| Empates | 12 (6.0%) |
| Derrotas CNN | 34 (17.0%) |
| Tempo médio CNN | 0.24 ms/jogada |
| Tempo médio Minimax | 79.8 ms/jogada |
| CNN é mais rápida | 332× |
| Caixas cedidas ao Minimax | 89/1539 (5.8%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 134 (67.0%) |
| Empates | 14 (7.0%) |
| Derrotas CNN | 52 (26.0%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 1561.2 ms/jogada |
| CNN é mais rápida | 6092× |
| Caixas cedidas ao Minimax | 108/1409 (7.7%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 100 (50.0%) |
| Empates | 9 (4.5%) |
| Derrotas CNN | 91 (45.5%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 4924.2 ms/jogada |
| CNN é mais rápida | 18613× |
| Caixas cedidas ao Minimax | 72/1191 (6.0%) |


---

