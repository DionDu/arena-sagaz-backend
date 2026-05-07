# Relatório de erros da CNN BoxNet v3 (profundidade 9) — pequeno 4x3

**Pasta da execução:** `pontinhos_pequeno_profundidade_9__20260505_140950`
**Data:** 2026-05-05
**Eventos analisados:** 765 caixas perdidas vs Minimax(p=1) e Minimax(p=3)

## Sumário executivo

Confronto com oráculo Minimax(p=7) em cada estado de "caixa perdida":

| Categoria | Eventos | % | Significado |
|-----------|--------:|--:|-------------|
| **CNN_OTIMA** | 260 | 34% | Falso alarme — a CNN sacrificou conscientemente; Minimax concorda |
| **ERRO_DEVERIA_CAPTURAR** | 505 | 66% | Erro real — Minimax recomenda capturar grau-3, CNN não capturou |
| SAC_OK_OUTRA | 0 | 0% | A CNN nunca "sacrifica na aresta errada" (não há esse modo de falha) |

Só **505 erros são reais** dos 765 originalmente reportados pelo avaliador.
O avaliador estava super-reportando: 1 em cada 3 eventos era sacrifício correto.

## Diagnóstico — perfil dos 505 erros reais

### Concentração no fim de jogo

| Nº traços preenchidos | Erros | % |
|----------------------:|------:|--:|
| 19–28                 | 12    | 2% |
| 29 (jogada 30)        | **493** | **98%** |

Os 505 erros estão **quase totalmente concentrados na penúltima jogada da partida**
(jogada 30 de 31), quando faltam apenas 2 arestas no tabuleiro e exatamente 1
caixa grau-3 está disponível.

### 99% dos erros têm apenas 1 caixa grau-3

| Nº caixas grau-3 disponíveis | Erros |
|-----------------------------:|------:|
| 1                            | 496   |
| 2                            | 9     |

Não é um problema de "qual cadeia capturar primeiro" — é um problema de
**reconhecer a única captura óbvia**.

### Top pares "deveria → jogou"

A CNN escolhe sistematicamente arestas de **borda** (linha 0/8, coluna 0/6) em
vez da aresta interna que fecha a caixa grau-3:

| Aresta correta | CNN jogou | N |
|---------------|-----------|--:|
| V_1_4 | V_1_6 | 65 |
| H_2_1 | V_1_0 | 55 |
| H_4_1 | V_3_0 | 33 |
| H_6_1 | V_7_0 | 32 |
| H_2_3 | H_0_3 | 25 |
| H_6_3 | H_8_3 | 24 |

A distribuição L/R é simétrica (não é viés horizontal), mas há um forte viés
para **bordas externas** do tabuleiro.

### Δ-score (impacto)

| Categoria | n | min | mediana | max |
|-----------|--:|----:|--------:|----:|
| CNN_OTIMA | 260 | 0 | 0.0 | 0 |
| ERRO_DEVERIA_CAPTURAR | 505 | 2 | 4.0 | 8 |

Cada erro custa em média 4 unidades de score (tipicamente 2 caixas → cadeia →
diferença de 4 caixas no fim). Em um tabuleiro de 12 caixas isso costuma ser
fatal.

## Hipóteses mecanísticas

1. **Sub-representação do estado quase-terminal no dataset.** Estados com 29
   traços só aparecem em ~2 jogadas finais por partida; em 30 mil partidas
   geradas, isso significa milhares de exemplos, mas todos com **soft targets
   quase degenerados** (jogada quase trivial, scores Minimax±pequenos). A KL
   divergence aprende mal essa região porque o sinal é raro e plano.

2. **Viés de borda.** A CNN tende a escolher arestas em linhas/colunas
   extremas (índices 0, 6, 8). Isso pode ser efeito do padding/conv: as
   features de borda têm receptive-field assimétrico e podem dominar quando
   o estado está quase cheio.

3. **Magnitude do soft target.** Q-values Minimax na jogada 30 são pequenos
   inteiros (±2 a ±8). Se a temperatura do softmax usado para gerar o target
   é alta, todas as arestas viram quase-equiprováveis e a CNN não aprende a
   distinção crucial.

## Recomendações — em ordem de custo/benefício

### 1. Augmentar dataset com simetrias (custo: baixíssimo, benefício: alto)
O tabuleiro 4×3 admite rotação/reflexão. Aplicar simetrias D4 multiplicaria
por 4 a cobertura de cada estado terminal sem gerar nenhuma nova partida
Minimax. Isso ataca diretamente o viés posicional de borda.

**Ação:** adicionar passe de augmentação no notebook de treinamento V5.

### 2. Re-amostragem do final de jogo (custo: médio, benefício: alto)
Gerar **partidas curtas a partir de estados aleatórios com 25–29 traços já
preenchidos**, rotuladas pelo Minimax(p=9). Adiciona milhares de amostras
exatamente onde a CNN erra.

**Ação:** novo gerador `gerar_estados_terminais.py` que sorteia estados
finais válidos e roda Minimax(p=9). Salvar em
`dados/profundidade_minmax_9/final_*.npz`.

### 3. Hard-target (one-hot) no final de jogo (custo: baixo, benefício: alto)
Para estados com ≥26 traços, substituir o soft target por one-hot na jogada
ótima. Isso força a CNN a aprender a distinção crucial. Misturar com 50% de
soft-target padrão evita over-fitting.

**Ação:** modificar pipeline de treino V5 para detectar fase 3 e trocar o
target.

### 4. Loss assimétrica em fase final (custo: médio, benefício: médio)
Adicionar termo de loss extra penalizando "não fechar grau-3 quando há
captura ótima". Isso é um indutor explícito da regra gulosa.

**Ação:** custom loss = KL + λ * indicator(estado tem grau-3 ótimo) * BCE(jogou_grau3).

### 5. Distillation por curriculum (custo: alto, benefício: incerto)
Treinar primeiro só nos estados terminais (fase 3), depois fazer fine-tuning
no dataset completo. Garante que a "regra de captura" seja aprendida primeiro.

## Próximos passos sugeridos

| Prioridade | Tarefa |
|-----------:|--------|
| 1 | Augmentação D4 (rotação + reflexão) — implementar e re-treinar |
| 2 | Re-amostragem dos estados com 25–29 traços (5–10 mil novos exemplos) |
| 3 | Hard target em fase 3 |
| 4 | Re-rodar avaliador e comparar nº de erros |

## Arquivos de apoio

- `tmp_analise/analisa_grau3_minimax.py` — primitivas de geometria/captura
- `tmp_analise/analisa_misses_cnn.py` — parser dos MDs do avaliador
- `tmp_analise/analisa_misses_com_minimax.py` — oráculo Minimax(p=7) por estado
- `tmp_analise/analisa_padrao_erros.py` — análise estatística dos 505 erros
- `visualizacoes/avaliacao_partidas/.../erros_deveria_capturar.csv` — CSV completo
