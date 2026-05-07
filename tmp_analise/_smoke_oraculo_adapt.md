# Relatório de divergência estratégica — CNN vs Minimax

**Modelo:** `modelos/pontinhos_pequeno_profundidade_9.tflite`  
**Tamanho:** `pequeno`  
**Oráculo:** Minimax(p=9)  
**Adversários:** p=1  
**Partidas por adversário:** 4  
**Workers:** 4  
**Tempo total de execução:** 84s

Diferença em relação ao `RELATORIO_ERROS_CNN.md`: 
aquele só captura erros TÁTICOS (não fechou caixa grau-3 disponível). 
ESTE captura também erros ESTRATÉGICOS de meio de jogo, comparando 
a jogada da CNN com a melhor jogada Minimax em **todas** as posições, 
não só nas que tinham caixa-pronta.

## 1. Sumário por adversário

| Adversário | Partidas | Vit. CNN | % Vitórias | Divergências | Fatais | Fatais/partida (média) |
|---|---:|---:|---:|---:|---:|---:|
| Minimax(p=1) | 4 | 4 | 100.0% | 78 | 5 | 1.25 |

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
| Minimax(p=1) | 2 | 0 | 3 |

## 3. Cruzamento — partidas perdidas pela CNN × tipo de erro

Para cada partida perdida pela CNN, classificamos:
- **Fatal precoce:** existe divergência fatal em jogada com ≤ 25 traços (= erro estratégico de meio).
- **Fatal apenas tardia:** divergência fatal só aparece com ≥ 26 traços (= erro tático puro).
- **Sem fatal:** nenhuma divergência fatal — CNN perdeu por acúmulo de divergências moderadas ou pelo adversário ter jogado bem.

| Adversário | Perdidas | Fatal precoce | Fatal apenas tardia | Sem fatal | % precoce |
|---|---:|---:|---:|---:|---:|
| Minimax(p=1) | 0 | 0 | 0 | 0 | 0.0% |

## 4. Histograma de divergências por nº de traços

| Traços antes | Total divergências | Fatais | Moderadas |
|---:|---:|---:|---:|
| 0 | 2 | 0 | 0 |
| 1 | 2 | 0 | 0 |
| 2 | 2 | 0 | 0 |
| 3 | 2 | 0 | 0 |
| 4 | 2 | 0 | 0 |
| 5 | 2 | 0 | 0 |
| 6 | 2 | 0 | 0 |
| 7 | 2 | 0 | 0 |
| 8 | 2 | 0 | 0 |
| 9 | 3 | 0 | 0 |
| 10 | 1 | 0 | 0 |
| 11 | 4 | 0 | 0 |
| 13 | 4 | 0 | 0 |
| 14 | 2 | 0 | 1 |
| 15 | 2 | 0 | 0 |
| 16 | 4 | 2 | 0 |
| 17 | 2 | 0 | 0 |
| 18 | 3 | 0 | 0 |
| 19 | 2 | 0 | 0 |
| 20 | 4 | 0 | 0 |
| 21 | 3 | 0 | 0 |
| 22 | 4 | 0 | 0 |
| 23 | 2 | 0 | 0 |
| 24 | 3 | 0 | 0 |
| 25 | 3 | 0 | 0 |
| 26 | 2 | 0 | 0 |
| 27 | 3 | 0 | 0 |
| 28 | 4 | 0 | 0 |
| 29 | 4 | 3 | 0 |
| 30 | 1 | 0 | 0 |

## 5. Top pares 'jogada ótima → jogada CNN' (Δ ≥ 2)

Útil para identificar padrões sistêmicos onde a CNN escolhe a aresta errada.

| Jogada ótima | Jogada CNN | Fase | N |
|---|---|---|---:|
| H_6_3 | H_8_3 | fim | 2 |
| V_1_0 | V_1_2 | meio | 1 |
| V_1_4 | H_4_3 | meio | 1 |
| H_4_3 | V_3_4 | meio | 1 |
| V_1_4 | H_0_5 | fim | 1 |

## 7. Cenário diagnosticado e parecer

**Cenário:** X1

Categoria B desprezível: apenas 0% das partidas perdidas têm divergência fatal em fase de meio de jogo (<= 25 traços). Fases A+B+C devem ser suficientes; Fase D opcional.

Critérios (alinhados ao PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md`, Seção 2.4):
- **X1:** < 10% das partidas perdidas têm divergência fatal precoce → Fases A+B+C suficientes; D opcional.
- **X2:** > 30% das partidas perdidas têm divergência fatal precoce → Fase D obrigatória.
- **X3:** 10–30% → manter plano completo, calibrar expectativas.

## 8. Próximos passos

1. Revisar este relatório com o usuário antes de iniciar a Fase A.
2. Registrar a decisão sobre cenário X1/X2/X3 em `docs/historico_decisoes.md`.
3. Caso o cenário seja X2 com sinais novos não previstos no PRD (ex.: feature estrutural específica que aparece nos top pares acima), revisar Seção 6 do PRD antes de começar a geração de dados.
4. Re-rodar este script após cada fase (B, C, D) e comparar os números — usar como métrica de acompanhamento da Categoria B.
