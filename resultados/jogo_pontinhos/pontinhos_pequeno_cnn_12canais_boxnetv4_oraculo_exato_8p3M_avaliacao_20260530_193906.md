
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-30 19:15 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_oraculo_exato_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates   | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas |
| ------------ | -------- | ------------ | --------- | ------------ | ----------- | ---------- | --------------- | -------------- |
| Minimax(p=1) | 200      | 200 (100.0%) | 0 (0.0%)  | 0 (0.0%)     | 8.71        | 0.3        | 0×              | 76/1977 (3.8%) |
| Minimax(p=3) | 200      | 188 (94.0%)  | 12 (6.0%) | 0 (0.0%)     | 2.16        | 86.0       | 40×             | 85/1827 (4.7%) |
| Minimax(p=5) | 200      | 184 (92.0%)  | 15 (7.5%) | 1 (0.5%)     | 2.02        | 1641.7     | 813×            | 84/1791 (4.7%) |
| Minimax(p=6) | 200      | 185 (92.5%)  | 15 (7.5%) | 0 (0.0%)     | 2.01        | 5504.2     | 2735×           | 86/1772 (4.9%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 200 (100.0%) |
| Empates | 0 (0.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 8.71 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 76/1977 (3.8%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 188 (94.0%) |
| Empates | 12 (6.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.16 ms/jogada |
| Tempo médio Minimax | 86.0 ms/jogada |
| CNN é mais rápida | 40× |
| Caixas cedidas ao Minimax | 85/1827 (4.7%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 184 (92.0%) |
| Empates | 15 (7.5%) |
| Derrotas CNN | 1 (0.5%) |
| Tempo médio CNN | 2.02 ms/jogada |
| Tempo médio Minimax | 1641.7 ms/jogada |
| CNN é mais rápida | 813× |
| Caixas cedidas ao Minimax | 84/1791 (4.7%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 185 (92.5%) |
| Empates | 15 (7.5%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.01 ms/jogada |
| Tempo médio Minimax | 5504.2 ms/jogada |
| CNN é mais rápida | 2735× |
| Caixas cedidas ao Minimax | 86/1772 (4.9%) |


---

