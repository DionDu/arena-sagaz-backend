
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-27 15:38 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_754k.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 3 (1.5%)  | 4 (2.0%)     | 13.31       | 0.4        | 0×              | 47/1975 (2.4%)  |
| Minimax(p=3) | 200      | 188 (94.0%)  | 7 (3.5%)  | 5 (2.5%)     | 3.18        | 99.7       | 31×             | 108/1840 (5.9%) |
| Minimax(p=5) | 200      | 173 (86.5%)  | 11 (5.5%) | 16 (8.0%)    | 2.63        | 1883.2     | 717×            | 118/1742 (6.8%) |
| Minimax(p=6) | 200      | 167 (83.5%)  | 14 (7.0%) | 19 (9.5%)    | 2.82        | 6142.8     | 2175×           | 107/1687 (6.3%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 4 (2.0%) |
| Tempo médio CNN | 13.31 ms/jogada |
| Tempo médio Minimax | 0.4 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 47/1975 (2.4%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 188 (94.0%) |
| Empates | 7 (3.5%) |
| Derrotas CNN | 5 (2.5%) |
| Tempo médio CNN | 3.18 ms/jogada |
| Tempo médio Minimax | 99.7 ms/jogada |
| CNN é mais rápida | 31× |
| Caixas cedidas ao Minimax | 108/1840 (5.9%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 173 (86.5%) |
| Empates | 11 (5.5%) |
| Derrotas CNN | 16 (8.0%) |
| Tempo médio CNN | 2.63 ms/jogada |
| Tempo médio Minimax | 1883.2 ms/jogada |
| CNN é mais rápida | 717× |
| Caixas cedidas ao Minimax | 118/1742 (6.8%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 167 (83.5%) |
| Empates | 14 (7.0%) |
| Derrotas CNN | 19 (9.5%) |
| Tempo médio CNN | 2.82 ms/jogada |
| Tempo médio Minimax | 6142.8 ms/jogada |
| CNN é mais rápida | 2175× |
| Caixas cedidas ao Minimax | 107/1687 (6.3%) |


---

