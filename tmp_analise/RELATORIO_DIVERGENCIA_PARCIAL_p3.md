# Relatório de divergência estratégica — CNN vs Minimax

**Modelo:** `C:\desenvolvimento\apps_backup_260429\arena-sagaz\arena-sagaz-backend\modelos\pontinhos_pequeno_profundidade_9.tflite`  
**Tamanho:** `pequeno`  
**Oráculo:** Minimax(p=9)  
**Adversários:** p=3  
**Partidas por adversário:** 200  
**Workers:** 1  
**Tempo total de execução:** 0s
**Retratos PNG:** `C:\desenvolvimento\apps_backup_260429\arena-sagaz\arena-sagaz-backend\tmp_analise\retratos_divergencia`

Diferença em relação ao `RELATORIO_ERROS_CNN.md`: 
aquele só captura erros TÁTICOS (não fechou caixa grau-3 disponível). 
ESTE captura também erros ESTRATÉGICOS de meio de jogo, comparando 
a jogada da CNN com a melhor jogada Minimax em **todas** as posições, 
não só nas que tinham caixa-pronta.

## 1. Sumário por adversário

| Adversário | Partidas | Vit. CNN | % Vitórias | Divergências | Fatais | Fatais/partida (média) |
|---|---:|---:|---:|---:|---:|---:|
| Minimax(p=3) | 200 | 109 | 54.5% | 3323 | 154 | 0.77 |

## 2. Distribuição de divergências por fase de jogo

Limiares de Δ-score (caixas):
- **Inócua:** Δ ≤ 1 (CNN escolheu jogada quase tão boa)
- **Moderada:** 2 ≤ Δ ≤ 3
- **Fatal:** Δ ≥ 4

Fases (por nº de traços já jogados antes da decisão):
- **abertura:** 0–9
- **meio:** 10–24  *(decisões de paridade/controle de cadeias)*
- **transicao:** 25–27
- **fim:** 28–30  *(tática de captura grau-3)*

| Adversário | Fatais (meio) | Fatais (transição) | Fatais (fim) |
|---|---:|---:|---:|
| Minimax(p=3) | 15 | 0 | 139 |

## 3. Cruzamento — partidas perdidas pela CNN × tipo de erro

Para cada partida perdida pela CNN, classificamos:
- **Fatal precoce:** existe divergência fatal em jogada com ≤ 25 traços (= erro estratégico de meio).
- **Fatal apenas tardia:** divergência fatal só aparece com ≥ 26 traços (= erro tático puro).
- **Sem fatal:** nenhuma divergência fatal — CNN perdeu por acúmulo de divergências moderadas ou pelo adversário ter jogado bem.

| Adversário | Perdidas | Fatal precoce | Fatal apenas tardia | Sem fatal | % precoce |
|---|---:|---:|---:|---:|---:|
| Minimax(p=3) | 42 | 7 | 21 | 14 | 16.7% |

## 4. Histograma de divergências por nº de traços

| Traços antes | Total divergências | Fatais | Moderadas |
|---:|---:|---:|---:|
| 0 | 100 | 0 | 0 |
| 1 | 100 | 0 | 0 |
| 2 | 100 | 0 | 0 |
| 3 | 100 | 0 | 0 |
| 4 | 100 | 0 | 0 |
| 5 | 100 | 0 | 0 |
| 6 | 100 | 0 | 0 |
| 7 | 100 | 0 | 0 |
| 8 | 100 | 0 | 0 |
| 9 | 100 | 0 | 0 |
| 10 | 100 | 0 | 2 |
| 11 | 100 | 0 | 11 |
| 12 | 100 | 2 | 28 |
| 13 | 100 | 0 | 18 |
| 14 | 100 | 10 | 16 |
| 15 | 100 | 1 | 7 |
| 16 | 99 | 2 | 1 |
| 17 | 83 | 0 | 0 |
| 18 | 100 | 0 | 2 |
| 19 | 103 | 0 | 1 |
| 20 | 108 | 0 | 1 |
| 21 | 112 | 0 | 1 |
| 22 | 119 | 0 | 1 |
| 23 | 119 | 0 | 0 |
| 24 | 128 | 0 | 0 |
| 25 | 128 | 0 | 0 |
| 26 | 118 | 0 | 0 |
| 27 | 140 | 0 | 0 |
| 28 | 170 | 3 | 0 |
| 29 | 166 | 136 | 0 |
| 30 | 30 | 0 | 0 |

## 5. Top pares 'jogada ótima → jogada CNN' (Δ ≥ 2)

Útil para identificar padrões sistêmicos onde a CNN escolhe a aresta errada.

| Jogada ótima | Jogada CNN | Fase | N |
|---|---|---|---:|
| H_2_1 | V_1_0 | fim | 18 |
| H_6_1 | V_7_0 | fim | 15 |
| V_1_4 | V_1_6 | fim | 12 |
| V_1_4 | H_0_5 | fim | 9 |
| H_6_3 | H_8_3 | fim | 9 |
| H_6_1 | H_8_1 | fim | 9 |
| H_4_1 | V_3_0 | fim | 7 |
| H_2_3 | H_0_3 | fim | 7 |
| H_6_5 | V_7_6 | fim | 7 |
| H_6_5 | H_8_5 | fim | 6 |
| H_4_1 | V_3_2 | meio | 5 |
| H_0_3 | V_7_2 | meio | 5 |
| H_8_3 | V_7_2 | meio | 4 |
| V_1_4 | H_0_3 | fim | 4 |
| H_4_1 | V_3_0 | meio | 4 |

## 6. Exemplos visuais de divergências fatais

Cada figura tem 2 painéis: à **esquerda** o estado antes da jogada com a aresta jogada pela CNN destacada em **laranja**; à **direita** o mesmo estado com a aresta **ótima** segundo o oráculo destacada em **verde**. Caixas azuis = CNN; vermelhas = adversário. Pasta-base dos PNGs = `<pasta_retratos>`.

Selecionados os 8 piores Δ-score em fase ≤ meio (primeiros) e os 8 piores em fase ≥ transição (últimos).

| # | Adversário | Partida | Jogada | Traços | Fase | Δ | CNN→Ótima | Retrato |
|---:|---|---:|---:|---:|---|---:|---|---|
| 1 | Minimax(p=3) | 1053 | 16 | 15 | meio | 8 | V_7_2 → V_7_0 | `Minimax_p_3/cnn2_partida1053/jogada016_cnn_t15_d8_fatal.png` |
| 2 | Minimax(p=3) | 38 | 15 | 14 | meio | 6 | H_2_3 → V_1_2 | `Minimax_p_3/cnn1_partida0038/jogada015_cnn_t14_d6_fatal.png` |
| 3 | Minimax(p=3) | 39 | 15 | 14 | meio | 6 | V_3_0 → H_4_1 | `Minimax_p_3/cnn1_partida0039/jogada015_cnn_t14_d6_fatal.png` |
| 4 | Minimax(p=3) | 43 | 15 | 14 | meio | 5 | H_0_5 → H_4_1 | `Minimax_p_3/cnn1_partida0043/jogada015_cnn_t14_d5_fatal.png` |
| 5 | Minimax(p=3) | 71 | 15 | 14 | meio | 5 | V_3_6 → V_3_4 | `Minimax_p_3/cnn1_partida0071/jogada015_cnn_t14_d5_fatal.png` |
| 6 | Minimax(p=3) | 84 | 15 | 14 | meio | 5 | H_2_3 → V_1_4 | `Minimax_p_3/cnn1_partida0084/jogada015_cnn_t14_d5_fatal.png` |
| 7 | Minimax(p=3) | 42 | 13 | 12 | meio | 4 | H_0_5 → V_1_2 | `Minimax_p_3/cnn1_partida0042/jogada013_cnn_t12_d4_fatal.png` |
| 8 | Minimax(p=3) | 89 | 13 | 12 | meio | 4 | H_8_3 → V_7_2 | `Minimax_p_3/cnn1_partida0089/jogada013_cnn_t12_d4_fatal.png` |
| 9 | Minimax(p=3) | 54 | 29 | 28 | fim | 8 | H_2_3 → V_1_4 | `Minimax_p_3/cnn1_partida0054/jogada029_cnn_t28_d8_fatal.png` |
| 10 | Minimax(p=3) | 68 | 29 | 28 | fim | 8 | H_2_5 → V_1_4 | `Minimax_p_3/cnn1_partida0068/jogada029_cnn_t28_d8_fatal.png` |
| 11 | Minimax(p=3) | 1000 | 29 | 28 | fim | 8 | H_2_5 → V_1_4 | `Minimax_p_3/cnn2_partida1000/jogada029_cnn_t28_d8_fatal.png` |
| 12 | Minimax(p=3) | 2 | 30 | 29 | fim | 4 | H_0_5 → V_1_4 | `Minimax_p_3/cnn1_partida0002/jogada030_cnn_t29_d4_fatal.png` |
| 13 | Minimax(p=3) | 11 | 30 | 29 | fim | 4 | V_1_0 → V_1_2 | `Minimax_p_3/cnn1_partida0011/jogada030_cnn_t29_d4_fatal.png` |
| 14 | Minimax(p=3) | 5 | 30 | 29 | fim | 4 | V_7_0 → H_6_1 | `Minimax_p_3/cnn1_partida0005/jogada030_cnn_t29_d4_fatal.png` |
| 15 | Minimax(p=3) | 10 | 30 | 29 | fim | 4 | H_8_3 → H_6_3 | `Minimax_p_3/cnn1_partida0010/jogada030_cnn_t29_d4_fatal.png` |
| 16 | Minimax(p=3) | 0 | 30 | 29 | fim | 4 | V_1_6 → V_1_4 | `Minimax_p_3/cnn1_partida0000/jogada030_cnn_t29_d4_fatal.png` |

Para visualizar, abra `<pasta_retratos>/<caminho do retrato>` (ex.: `tmp_analise/retratos_divergencia/Minimax_p_5/cnn1_partida0007/jogada015_t12_d6_fatal.png`).

## 7. Cenário diagnosticado e parecer

**Cenário:** X3

Cenário misto: 17% das partidas perdidas com divergência fatal precoce. Manter plano completo (A→D); calibrar expectativas: Fases A+B+C atacam ~50% do gap, Fase D ataca a outra metade.

Critérios (alinhados ao PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md`, Seção 2.4):
- **X1:** < 10% das partidas perdidas têm divergência fatal precoce → Fases A+B+C suficientes; D opcional.
- **X2:** > 30% das partidas perdidas têm divergência fatal precoce → Fase D obrigatória.
- **X3:** 10–30% → manter plano completo, calibrar expectativas.

## 8. Próximos passos

1. Revisar este relatório com o usuário antes de iniciar a Fase A.
2. Registrar a decisão sobre cenário X1/X2/X3 em `docs/historico_decisoes.md`.
3. Caso o cenário seja X2 com sinais novos não previstos no PRD (ex.: feature estrutural específica que aparece nos top pares acima), revisar Seção 6 do PRD antes de começar a geração de dados.
4. Re-rodar este script após cada fase (B, C, D) e comparar os números — usar como métrica de acompanhamento da Categoria B.
