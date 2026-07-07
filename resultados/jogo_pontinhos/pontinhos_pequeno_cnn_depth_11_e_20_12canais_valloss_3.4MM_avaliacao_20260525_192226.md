
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-25 18:57 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss_3.4MM.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 188 (94.0%)  | 6 (3.0%)  | 6 (3.0%)     | 0.21        | 0.2        | 1×              | 76/1984 (3.8%)  |
| Minimax(p=3) | 200      | 164 (82.0%)  | 16 (8.0%) | 20 (10.0%)   | 0.25        | 83.9       | 336×            | 117/1683 (7.0%) |
| Minimax(p=5) | 200      | 147 (73.5%)  | 19 (9.5%) | 34 (17.0%)   | 0.25        | 1621.5     | 6480×           | 124/1533 (8.1%) |
| Minimax(p=6) | 200      | 136 (68.0%)  | 19 (9.5%) | 45 (22.5%)   | 0.25        | 5194.8     | 20760×          | 104/1430 (7.3%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 188 (94.0%) |
| Empates | 6 (3.0%) |
| Derrotas CNN | 6 (3.0%) |
| Tempo médio CNN | 0.21 ms/jogada |
| Tempo médio Minimax | 0.2 ms/jogada |
| CNN é mais rápida | 1× |
| Caixas cedidas ao Minimax | 76/1984 (3.8%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 164 (82.0%) |
| Empates | 16 (8.0%) |
| Derrotas CNN | 20 (10.0%) |
| Tempo médio CNN | 0.25 ms/jogada |
| Tempo médio Minimax | 83.9 ms/jogada |
| CNN é mais rápida | 336× |
| Caixas cedidas ao Minimax | 117/1683 (7.0%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 147 (73.5%) |
| Empates | 19 (9.5%) |
| Derrotas CNN | 34 (17.0%) |
| Tempo médio CNN | 0.25 ms/jogada |
| Tempo médio Minimax | 1621.5 ms/jogada |
| CNN é mais rápida | 6480× |
| Caixas cedidas ao Minimax | 124/1533 (8.1%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 136 (68.0%) |
| Empates | 19 (9.5%) |
| Derrotas CNN | 45 (22.5%) |
| Tempo médio CNN | 0.25 ms/jogada |
| Tempo médio Minimax | 5194.8 ms/jogada |
| CNN é mais rápida | 20760× |
| Caixas cedidas ao Minimax | 104/1430 (7.3%) |


---

