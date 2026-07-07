
# Relatório de Avaliação — CNN vs Minimax e Oráculo

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-06-01 17:27 |
| Modelo | `pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite` |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| Partidas por profundidade | 200 |
| Profundidades | [1, 3, 5, 6] |
| Timer Minimax | sem limite |


---


## CNN vs Oráculo (jogo perfeito = Minimax p=31)

_Protocolo: 1a jogada aleatoria; alterna quem ABRE. O ORACULO = Minimax de profundidade total (p=31), o teto de forca (mais forte que qualquer Minimax p<=19). Nao se vence o jogo perfeito (4x3 e empate sob jogo otimo) — vitorias da CNN vem de aberturas favoraveis. Por isso a quebra por QUEM ABRE._

| Quem abre | Partidas | Vitorias CNN | Empates | Derrotas CNN |
|-----------|----------|--------------|---------|--------------|
| TOTAL | 200 | 80 (40.0%) | 31 (15.5%) | 89 (44.5%) |
| CNN abre | 100 | 0 (0.0%) | 12 (12.0%) | 88 (88.0%) |
| Oraculo abre | 100 | 80 (80.0%) | 19 (19.0%) | 1 (1.0%) |


---


## Resultados por Adversário

| Adversário   | Partidas | Vitórias CNN | Empates  | Derrotas CNN | T. CNN (ms) | T. MM (ms) | CNN mais rápida | Caixas cedidas |
| ------------ | -------- | ------------ | -------- | ------------ | ----------- | ---------- | --------------- | -------------- |
| Minimax(p=1) | 200      | 200 (100.0%) | 0 (0.0%) | 0 (0.0%)     | 8.87        | 0.3        | 0×              | 76/2030 (3.7%) |
| Minimax(p=3) | 200      | 194 (97.0%)  | 6 (3.0%) | 0 (0.0%)     | 2.17        | 88.7       | 41×             | 86/1887 (4.6%) |
| Minimax(p=5) | 200      | 192 (96.0%)  | 7 (3.5%) | 1 (0.5%)     | 2.00        | 1689.6     | 844×            | 87/1857 (4.7%) |
| Minimax(p=6) | 200      | 192 (96.0%)  | 8 (4.0%) | 0 (0.0%)     | 2.00        | 5402.3     | 2703×           | 89/1839 (4.8%) |


## Detalhes por Adversário


### Minimax(p=1)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 200 (100.0%) |
| Empates | 0 (0.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 8.87 ms/jogada |
| Tempo médio Minimax | 0.3 ms/jogada |
| CNN é mais rápida | 0× |
| Caixas cedidas ao Minimax | 76/2030 (3.7%) |


### Minimax(p=3)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 194 (97.0%) |
| Empates | 6 (3.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.17 ms/jogada |
| Tempo médio Minimax | 88.7 ms/jogada |
| CNN é mais rápida | 41× |
| Caixas cedidas ao Minimax | 86/1887 (4.6%) |


### Minimax(p=5)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 192 (96.0%) |
| Empates | 7 (3.5%) |
| Derrotas CNN | 1 (0.5%) |
| Tempo médio CNN | 2.00 ms/jogada |
| Tempo médio Minimax | 1689.6 ms/jogada |
| CNN é mais rápida | 844× |
| Caixas cedidas ao Minimax | 87/1857 (4.7%) |


### Minimax(p=6)

| Métrica | Valor |
|---------|-------|
| Vitórias CNN | 192 (96.0%) |
| Empates | 8 (4.0%) |
| Derrotas CNN | 0 (0.0%) |
| Tempo médio CNN | 2.00 ms/jogada |
| Tempo médio Minimax | 5402.3 ms/jogada |
| CNN é mais rápida | 2703× |
| Caixas cedidas ao Minimax | 89/1839 (4.8%) |


---

