
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-28 17:11 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valuehead_v2_3p4M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates    | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | ---------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 3 (1.5%)   | 4 (2.0%)     | 8.45        | 0.3        | 0×              | 63/1937 (3.3%)  |
| Minimax(p=3) | 200      | 185 (92.5%)  | 11 (5.5%)  | 4 (2.0%)     | 2.19        | 92.2       | 42×             | 114/1833 (6.2%) |
| Minimax(p=5) | 200      | 159 (79.5%)  | 16 (8.0%)  | 25 (12.5%)   | 2.15        | 1623.1     | 755×            | 115/1687 (6.8%) |
| Minimax(p=6) | 200      | 154 (77.0%)  | 22 (11.0%) | 24 (12.0%)   | 2.13        | 5339.0     | 2508×           | 108/1660 (6.5%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 4 (2.0%) |
| Tempo médio CNN | 8.45 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 63/1937 (3.3%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 185 (92.5%) |
| Empates | 11 (5.5%) |
| Derrotas CNN | 4 (2.0%) |
| Tempo médio CNN | 2.19 ms/jogada |
| Tempo médio Minimax | 92.2 ms/jogada |
| CNN é mais rápida | 42× |
| Caixas cedidas ao Minimax | 114/1833 (6.2%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 159 (79.5%) |
| Empates | 16 (8.0%) |
| Derrotas CNN | 25 (12.5%) |
| Tempo médio CNN | 2.15 ms/jogada |
| Tempo médio Minimax | 1623.1 ms/jogada |
| CNN é mais rápida | 755× |
| Caixas cedidas ao Minimax | 115/1687 (6.8%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 154 (77.0%) |
| Empates | 22 (11.0%) |
| Derrotas CNN | 24 (12.0%) |
| Tempo médio CNN | 2.13 ms/jogada |
| Tempo médio Minimax | 5339.0 ms/jogada |
| CNN é mais rápida | 2508× |
| Caixas cedidas ao Minimax | 108/1660 (6.5%) |


---

