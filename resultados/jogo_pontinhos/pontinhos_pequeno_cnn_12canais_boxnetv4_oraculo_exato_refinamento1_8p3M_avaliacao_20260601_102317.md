
# Relatório de Avaliação — CNN vs Minimax e Oráculo

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-06-01 09:59 |
| Modelo | `pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento1_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## CNN vs Oráculo (jogo perfeito = Minimax p=31)

_Protocolo: 1a jogada aleatoria; alterna quem ABRE. O ORACULO = Minimax de profundidade total (p=31), o teto de forca (mais forte que qualquer Minimax p<=19). Nao se vence o jogo perfeito (4x3 e empate sob jogo otimo) — vitorias da CNN vem de aberturas favoraveis. Por isso a quebra por QUEM ABRE._

| Quem abre | Partidas | Vitorias CNN | Empates | Derrotas CNN |
|-----------|----------|--------------|---------|--------------|
| TOTAL | 200 | 77 (38.5%) | 32 (16.0%) | 91 (45.5%) |
| CNN abre | 100 | 0 (0.0%) | 12 (12.0%) | 88 (88.0%) |
| Oraculo abre | 100 | 77 (77.0%) | 20 (20.0%) | 3 (3.0%) |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates  | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas |
| ------------ | -------- | ------------ | -------- | ------------ | ----------- | ---------- | --------------- | -------------- |
| Minimax(p=1) | 200      | 200 (100.0%) | 0 (0.0%) | 0 (0.0%)     | 8.66        | 0.3        | 0×              | 74/2026 (3.7%) |
| Minimax(p=3) | 200      | 196 (98.0%)  | 4 (2.0%) | 0 (0.0%)     | 2.22        | 93.3       | 42×             | 85/1879 (4.5%) |
| Minimax(p=5) | 200      | 196 (98.0%)  | 4 (2.0%) | 0 (0.0%)     | 2.03        | 1700.1     | 837×            | 86/1853 (4.6%) |
| Minimax(p=6) | 200      | 192 (96.0%)  | 8 (4.0%) | 0 (0.0%)     | 2.04        | 5454.0     | 2680×           | 86/1815 (4.7%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 200 (100.0%) |
| Empates | 0 (0.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 8.66 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 74/2026 (3.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 196 (98.0%) |
| Empates | 4 (2.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.22 ms/jogada |
| Tempo médio Minimax | 93.3 ms/jogada |
| CNN é mais rápida | 42× |
| Caixas cedidas ao Minimax | 85/1879 (4.5%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 196 (98.0%) |
| Empates | 4 (2.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.03 ms/jogada |
| Tempo médio Minimax | 1700.1 ms/jogada |
| CNN é mais rápida | 837× |
| Caixas cedidas ao Minimax | 86/1853 (4.6%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 192 (96.0%) |
| Empates | 8 (4.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.04 ms/jogada |
| Tempo médio Minimax | 5454.0 ms/jogada |
| CNN é mais rápida | 2680× |
| Caixas cedidas ao Minimax | 86/1815 (4.7%) |


---

