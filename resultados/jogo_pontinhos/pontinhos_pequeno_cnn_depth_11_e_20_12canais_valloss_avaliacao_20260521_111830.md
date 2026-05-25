
# Relatório de Avaliação — CNN vs Minimax

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-21 10:53 |
| Modelo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates    | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas |
| ------------ | -------- | ------------ | ---------- | ------------ | ----------- | ---------- | --------------- | -------------- |
| Minimax(p=1) | 200      | 193 (96.5%)  | 7 (3.5%)   | 0 (0.0%)     | 0.27        | 0.2        | 1×              | 44/1981 (2.2%) |
| Minimax(p=3) | 200      | 164 (82.0%)  | 21 (10.5%) | 15 (7.5%)    | 0.24        | 83.1       | 346×            | 77/1681 (4.6%) |
| Minimax(p=5) | 200      | 143 (71.5%)  | 21 (10.5%) | 36 (18.0%)   | 0.26        | 1648.0     | 6363×           | 98/1550 (6.3%) |
| Minimax(p=6) | 200      | 127 (63.5%)  | 20 (10.0%) | 53 (26.5%)   | 0.26        | 5055.2     | 19364×          | 90/1406 (6.4%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 193 (96.5%) |
| Empates | 7 (3.5%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 0.27 ms/jogada |
| Tempo médio Minimax | 0.2 ms/jogada |
| CNN é mais rápida | 1× |
| Caixas cedidas ao Minimax | 44/1981 (2.2%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 164 (82.0%) |
| Empates | 21 (10.5%) |
| Derrotas CNN | 15 (7.5%) |
| Tempo médio CNN | 0.24 ms/jogada |
| Tempo médio Minimax | 83.1 ms/jogada |
| CNN é mais rápida | 346× |
| Caixas cedidas ao Minimax | 77/1681 (4.6%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 143 (71.5%) |
| Empates | 21 (10.5%) |
| Derrotas CNN | 36 (18.0%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 1648.0 ms/jogada |
| CNN é mais rápida | 6363× |
| Caixas cedidas ao Minimax | 98/1550 (6.3%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 127 (63.5%) |
| Empates | 20 (10.0%) |
| Derrotas CNN | 53 (26.5%) |
| Tempo médio CNN | 0.26 ms/jogada |
| Tempo médio Minimax | 5055.2 ms/jogada |
| CNN é mais rápida | 19364× |
| Caixas cedidas ao Minimax | 90/1406 (6.4%) |


---

