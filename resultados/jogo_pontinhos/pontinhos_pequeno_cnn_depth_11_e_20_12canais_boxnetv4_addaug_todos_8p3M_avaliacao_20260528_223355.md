
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-28 22:11 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_todos_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 189 (94.5%)  | 5 (2.5%)  | 6 (3.0%)     | 8.49        | 0.3        | 0×              | 62/1921 (3.2%)  |
| Minimax(p=3) | 200      | 183 (91.5%)  | 12 (6.0%) | 5 (2.5%)     | 2.16        | 89.2       | 41×             | 110/1843 (6.0%) |
| Minimax(p=5) | 200      | 173 (86.5%)  | 13 (6.5%) | 14 (7.0%)    | 2.05        | 1595.4     | 779×            | 117/1769 (6.6%) |
| Minimax(p=6) | 200      | 169 (84.5%)  | 16 (8.0%) | 15 (7.5%)    | 2.04        | 5101.3     | 2506×           | 102/1695 (6.0%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 189 (94.5%) |
| Empates | 5 (2.5%) |
| Derrotas CNN | 6 (3.0%) |
| Tempo médio CNN | 8.49 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 62/1921 (3.2%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 183 (91.5%) |
| Empates | 12 (6.0%) |
| Derrotas CNN | 5 (2.5%) |
| Tempo médio CNN | 2.16 ms/jogada |
| Tempo médio Minimax | 89.2 ms/jogada |
| CNN é mais rápida | 41× |
| Caixas cedidas ao Minimax | 110/1843 (6.0%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 173 (86.5%) |
| Empates | 13 (6.5%) |
| Derrotas CNN | 14 (7.0%) |
| Tempo médio CNN | 2.05 ms/jogada |
| Tempo médio Minimax | 1595.4 ms/jogada |
| CNN é mais rápida | 779× |
| Caixas cedidas ao Minimax | 117/1769 (6.6%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 169 (84.5%) |
| Empates | 16 (8.0%) |
| Derrotas CNN | 15 (7.5%) |
| Tempo médio CNN | 2.04 ms/jogada |
| Tempo médio Minimax | 5101.3 ms/jogada |
| CNN é mais rápida | 2506× |
| Caixas cedidas ao Minimax | 102/1695 (6.0%) |


---

