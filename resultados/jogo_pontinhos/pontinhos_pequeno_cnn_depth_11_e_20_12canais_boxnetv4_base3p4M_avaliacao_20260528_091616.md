
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-28 08:53 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_base3p4M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas  |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | --------------- |
| Minimax(p=1) | 200      | 194 (97.0%)  | 3 (1.5%)  | 3 (1.5%)     | 8.28        | 0.3        | 0×              | 58/1940 (3.0%)  |
| Minimax(p=3) | 200      | 180 (90.0%)  | 14 (7.0%) | 6 (3.0%)     | 2.10        | 86.4       | 41×             | 100/1799 (5.6%) |
| Minimax(p=5) | 200      | 174 (87.0%)  | 17 (8.5%) | 9 (4.5%)     | 1.97        | 1608.4     | 818×            | 115/1745 (6.6%) |
| Minimax(p=6) | 200      | 160 (80.0%)  | 19 (9.5%) | 21 (10.5%)   | 2.06        | 5235.8     | 2537×           | 91/1661 (5.5%)  |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 194 (97.0%) |
| Empates | 3 (1.5%) |
| Derrotas CNN | 3 (1.5%) |
| Tempo médio CNN | 8.28 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 58/1940 (3.0%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 180 (90.0%) |
| Empates | 14 (7.0%) |
| Derrotas CNN | 6 (3.0%) |
| Tempo médio CNN | 2.10 ms/jogada |
| Tempo médio Minimax | 86.4 ms/jogada |
| CNN é mais rápida | 41× |
| Caixas cedidas ao Minimax | 100/1799 (5.6%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 174 (87.0%) |
| Empates | 17 (8.5%) |
| Derrotas CNN | 9 (4.5%) |
| Tempo médio CNN | 1.97 ms/jogada |
| Tempo médio Minimax | 1608.4 ms/jogada |
| CNN é mais rápida | 818× |
| Caixas cedidas ao Minimax | 115/1745 (6.6%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 160 (80.0%) |
| Empates | 19 (9.5%) |
| Derrotas CNN | 21 (10.5%) |
| Tempo médio CNN | 2.06 ms/jogada |
| Tempo médio Minimax | 5235.8 ms/jogada |
| CNN é mais rápida | 2537× |
| Caixas cedidas ao Minimax | 91/1661 (5.5%) |


---

