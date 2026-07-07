
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-29 13:01 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 191 (95.5%)  | 6 (3.0%)  | 3 (1.5%)     | 7.43        | 0.3        | 0×              | 53/1931 (2.7%)  |
| Minimax(p=3) | 200      | 177 (88.5%)  | 8 (4.0%)  | 15 (7.5%)    | 1.81        | 87.4       | 48×             | 100/1770 (5.6%) |
| Minimax(p=5) | 200      | 172 (86.0%)  | 13 (6.5%) | 15 (7.5%)    | 1.77        | 1625.5     | 920×            | 105/1706 (6.2%) |
| Minimax(p=6) | 200      | 163 (81.5%)  | 16 (8.0%) | 21 (10.5%)   | 1.81        | 5477.9     | 3027×           | 93/1653 (5.6%)  |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 191 (95.5%) |
| Empates | 6 (3.0%) |
| Derrotas CNN | 3 (1.5%) |
| Tempo médio CNN | 7.43 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 53/1931 (2.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 177 (88.5%) |
| Empates | 8 (4.0%) |
| Derrotas CNN | 15 (7.5%) |
| Tempo médio CNN | 1.81 ms/jogada |
| Tempo médio Minimax | 87.4 ms/jogada |
| CNN é mais rápida | 48× |
| Caixas cedidas ao Minimax | 100/1770 (5.6%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 172 (86.0%) |
| Empates | 13 (6.5%) |
| Derrotas CNN | 15 (7.5%) |
| Tempo médio CNN | 1.77 ms/jogada |
| Tempo médio Minimax | 1625.5 ms/jogada |
| CNN é mais rápida | 920× |
| Caixas cedidas ao Minimax | 105/1706 (6.2%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 163 (81.5%) |
| Empates | 16 (8.0%) |
| Derrotas CNN | 21 (10.5%) |
| Tempo médio CNN | 1.81 ms/jogada |
| Tempo médio Minimax | 5477.9 ms/jogada |
| CNN é mais rápida | 3027× |
| Caixas cedidas ao Minimax | 93/1653 (5.6%) |


---

