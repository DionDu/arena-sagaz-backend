
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-27 09:10 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss_13.8MM.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates    | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | ---------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 196 (98.0%)  | 3 (1.5%)   | 1 (0.5%)     | 0.22        | 0.2        | 1×              | 88/1950 (4.5%)  |
| Minimax(p=3) | 200      | 154 (77.0%)  | 32 (16.0%) | 14 (7.0%)    | 0.25        | 83.8       | 337×            | 112/1585 (7.1%) |
| Minimax(p=5) | 200      | 146 (73.0%)  | 32 (16.0%) | 22 (11.0%)   | 0.26        | 1683.8     | 6505×           | 132/1501 (8.8%) |
| Minimax(p=6) | 200      | 143 (71.5%)  | 27 (13.5%) | 30 (15.0%)   | 0.25        | 5416.4     | 21528×          | 109/1449 (7.5%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 196 (98.0%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 1 (0.5%) |
| Tempo médio CNN | 0.22 ms/jogada |
| Tempo médio Minimax | 0.2 ms/jogada |
| CNN é mais rápida | 1× |
| Caixas cedidas ao Minimax | 88/1950 (4.5%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 154 (77.0%) |
| Empates | 32 (16.0%) |
| Derrotas CNN | 14 (7.0%) |
| Tempo médio CNN | 0.25 ms/jogada |
| Tempo médio Minimax | 83.8 ms/jogada |
| CNN é mais rápida | 337× |
| Caixas cedidas ao Minimax | 112/1585 (7.1%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 146 (73.0%) |
| Empates | 32 (16.0%) |
| Derrotas CNN | 22 (11.0%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 1683.8 ms/jogada |
| CNN é mais rápida | 6505× |
| Caixas cedidas ao Minimax | 132/1501 (8.8%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 143 (71.5%) |
| Empates | 27 (13.5%) |
| Derrotas CNN | 30 (15.0%) |
| Tempo médio CNN | 0.25 ms/jogada |
| Tempo médio Minimax | 5416.4 ms/jogada |
| CNN é mais rápida | 21528× |
| Caixas cedidas ao Minimax | 109/1449 (7.5%) |


---

