
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-31 18:05 |
| Modelo | `pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento1_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates  | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas |
| ------------ | -------- | ------------ | -------- | ------------ | ----------- | ---------- | --------------- | -------------- |
| Minimax(p=1) | 200      | 200 (100.0%) | 0 (0.0%) | 0 (0.0%)     | 8.73        | 0.3        | 0×              | 74/2026 (3.7%) |
| Minimax(p=3) | 200      | 196 (98.0%)  | 4 (2.0%) | 0 (0.0%)     | 2.28        | 93.6       | 41×             | 85/1879 (4.5%) |
| Minimax(p=5) | 200      | 196 (98.0%)  | 4 (2.0%) | 0 (0.0%)     | 2.12        | 1753.8     | 827×            | 86/1853 (4.6%) |
| Minimax(p=6) | 200      | 192 (96.0%)  | 8 (4.0%) | 0 (0.0%)     | 2.07        | 5473.2     | 2647×           | 86/1815 (4.7%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 200 (100.0%) |
| Empates | 0 (0.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 8.73 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 74/2026 (3.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 196 (98.0%) |
| Empates | 4 (2.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.28 ms/jogada |
| Tempo médio Minimax | 93.6 ms/jogada |
| CNN é mais rápida | 41× |
| Caixas cedidas ao Minimax | 85/1879 (4.5%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 196 (98.0%) |
| Empates | 4 (2.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.12 ms/jogada |
| Tempo médio Minimax | 1753.8 ms/jogada |
| CNN é mais rápida | 827× |
| Caixas cedidas ao Minimax | 86/1853 (4.6%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 192 (96.0%) |
| Empates | 8 (4.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.07 ms/jogada |
| Tempo médio Minimax | 5473.2 ms/jogada |
| CNN é mais rápida | 2647× |
| Caixas cedidas ao Minimax | 86/1815 (4.7%) |


---

