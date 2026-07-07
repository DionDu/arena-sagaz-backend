
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-29 19:20 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_dense256_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 5 (2.5%)  | 2 (1.0%)     | 4.78        | 0.3        | 0×              | 69/1951 (3.5%)  |
| Minimax(p=3) | 200      | 191 (95.5%)  | 2 (1.0%)  | 7 (3.5%)     | 1.96        | 105.2      | 54×             | 122/1841 (6.6%) |
| Minimax(p=5) | 200      | 176 (88.0%)  | 6 (3.0%)  | 18 (9.0%)    | 2.69        | 2194.6     | 816×            | 117/1720 (6.8%) |
| Minimax(p=6) | 200      | 161 (80.5%)  | 16 (8.0%) | 23 (11.5%)   | 2.48        | 7015.4     | 2828×           | 107/1642 (6.5%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 5 (2.5%) |
| Derrotas CNN | 2 (1.0%) |
| Tempo médio CNN | 4.78 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 69/1951 (3.5%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 191 (95.5%) |
| Empates | 2 (1.0%) |
| Derrotas CNN | 7 (3.5%) |
| Tempo médio CNN | 1.96 ms/jogada |
| Tempo médio Minimax | 105.2 ms/jogada |
| CNN é mais rápida | 54× |
| Caixas cedidas ao Minimax | 122/1841 (6.6%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 176 (88.0%) |
| Empates | 6 (3.0%) |
| Derrotas CNN | 18 (9.0%) |
| Tempo médio CNN | 2.69 ms/jogada |
| Tempo médio Minimax | 2194.6 ms/jogada |
| CNN é mais rápida | 816× |
| Caixas cedidas ao Minimax | 117/1720 (6.8%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 161 (80.5%) |
| Empates | 16 (8.0%) |
| Derrotas CNN | 23 (11.5%) |
| Tempo médio CNN | 2.48 ms/jogada |
| Tempo médio Minimax | 7015.4 ms/jogada |
| CNN é mais rápida | 2828× |
| Caixas cedidas ao Minimax | 107/1642 (6.5%) |


---

