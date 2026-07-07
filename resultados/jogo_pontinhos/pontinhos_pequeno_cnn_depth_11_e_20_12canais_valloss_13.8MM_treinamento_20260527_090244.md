
# Relatorio de Treinamento — BoxNet V10

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-27 08:52 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\dados\profundidade_minimax_11_adaptativo` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 1676 |
| Total de amostras | 13,693,840 |
| Treino | 9,585,687 |
| Validacao | 2,054,077 |
| Teste | 2,054,076 |

**Distribuicao por fase (%)**

| Fase                |   Treino (%) |   Val (%) |   Teste (%) |
|:--------------------|-------------:|----------:|------------:|
| Abertura (0-11)     |         36.7 |      36.7 |        36.7 |
| 1a Metade (12-17)   |         20.0 |      20.0 |        20.0 |
| 2a Metade (18-23)   |         20.0 |      20.0 |        20.0 |
| Fase Quente (24-28) |         16.7 |      16.7 |        16.7 |
| Final (29-31)       |          6.7 |       6.7 |         6.7 |


---


## 2. Arquitetura

| Parâmetro | Valor |
|-----------|-------|
| Modelo | BoxNet_v3_V8_12canais |
| Input shape | (4, 3, 12) |
| Parâmetros treináveis | 76,527 |
| Classes | 31 |
| Loss | KL Divergence |
| Optimizer | Adam (lr=1e-3) |
| L2 regularização | 0.0002 |
| Batch size | 256 |
| EarlyStopping patience | 10 |
| ReduceLROnPlateau patience | 6 |

**Estrutura das Camadas:**

| Camada                   | Tipo                   | Output Shape     |   Param # | Connected to                                 | Treinável   |
|:-------------------------|:-----------------------|:-----------------|----------:|:---------------------------------------------|:------------|
| canais_estruturais       | InputLayer             | (None, 4, 3, 12) |         0 |                                              | True        |
| conv2d                   | Conv2D                 | (None, 4, 3, 32) |     3,456 | canais_estruturais                           | True        |
| batch_normalization      | BatchNormalization     | (None, 4, 3, 32) |       128 | conv2d                                       | True        |
| activation               | Activation             | (None, 4, 3, 32) |         0 | batch_normalization                          | True        |
| separable_conv2d         | SeparableConv2D        | (None, 4, 3, 32) |     1,312 | activation                                   | True        |
| batch_normalization_1    | BatchNormalization     | (None, 4, 3, 32) |       128 | separable_conv2d                             | True        |
| activation_1             | Activation             | (None, 4, 3, 32) |         0 | batch_normalization_1                        | True        |
| spatial_dropout2d        | SpatialDropout2D       | (None, 4, 3, 32) |         0 | activation_1                                 | True        |
| separable_conv2d_1       | SeparableConv2D        | (None, 4, 3, 32) |     1,312 | spatial_dropout2d                            | True        |
| batch_normalization_2    | BatchNormalization     | (None, 4, 3, 32) |       128 | separable_conv2d_1                           | True        |
| add                      | Add                    | (None, 4, 3, 32) |         0 | batch_normalization_2, activation            | True        |
| activation_2             | Activation             | (None, 4, 3, 32) |         0 | add                                          | True        |
| separable_conv2d_2       | SeparableConv2D        | (None, 4, 3, 48) |     1,824 | activation_2                                 | True        |
| batch_normalization_3    | BatchNormalization     | (None, 4, 3, 48) |       192 | separable_conv2d_2                           | True        |
| activation_3             | Activation             | (None, 4, 3, 48) |         0 | batch_normalization_3                        | True        |
| spatial_dropout2d_1      | SpatialDropout2D       | (None, 4, 3, 48) |         0 | activation_3                                 | True        |
| separable_conv2d_3       | SeparableConv2D        | (None, 4, 3, 48) |     2,736 | spatial_dropout2d_1                          | True        |
| conv2d_1                 | Conv2D                 | (None, 4, 3, 48) |     1,536 | activation_2                                 | True        |
| batch_normalization_4    | BatchNormalization     | (None, 4, 3, 48) |       192 | separable_conv2d_3                           | True        |
| batch_normalization_5    | BatchNormalization     | (None, 4, 3, 48) |       192 | conv2d_1                                     | True        |
| add_1                    | Add                    | (None, 4, 3, 48) |         0 | batch_normalization_4, batch_normalization_5 | True        |
| activation_4             | Activation             | (None, 4, 3, 48) |         0 | add_1                                        | True        |
| global_average_pooling2d | GlobalAveragePooling2D | (None, 48)       |         0 | activation_4                                 | True        |
| flatten                  | Flatten                | (None, 576)      |         0 | activation_4                                 | True        |
| concatenate              | Concatenate            | (None, 624)      |         0 | global_average_pooling2d, flatten            | True        |
| dense                    | Dense                  | (None, 96)       |    60,000 | concatenate                                  | True        |
| batch_normalization_6    | BatchNormalization     | (None, 96)       |       384 | dense                                        | True        |
| dropout                  | Dropout                | (None, 96)       |         0 | batch_normalization_6                        | True        |
| jogada                   | Dense                  | (None, 31)       |     3,007 | dropout                                      | True        |


---


## 3. Treinamento

*(modelo carregado de checkpoint — treinamento pulado)*

| Metrica | Valor |
|---------|-------|
| Checkpoint | `BoxNet_V10_12canais_best_valloss.keras` |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   |         N |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|----------:|-----------:|--------:|--------:|--------:|
| Treino     | 9,585,687 |     0.1516 |  0.4638 |  0.6221 |  0.6859 |
| Validação  | 2,054,077 |     0.1520 |  0.4637 |  0.6222 |  0.6860 |
| Teste      | 2,054,076 |     0.1518 |  0.4642 |  0.6227 |  0.6863 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.01 pp |
| Gap KLD (Val − Treino) | +0.0004 |
| **OMA global** | **91.1%** |
| Média jogadas Minimax-equiv. | 7.8 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 753166 | 15.1%   | 21.4%   | 28.8%   | 87.1%  |
| 1a Metade (12-17)   | 410817 | 52.0%   | 73.4%   | 83.4%   | 80.3%  |
| 2a Metade (18-23)   | 410814 | 67.3%   | 88.2%   | 92.5%   | 98.8%  |
| Fase Quente (24-28) | 342342 | 65.3%   | 92.7%   | 97.4%   | 100.0% |
| Final (29-31)       | 136937 | 92.3%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.4642 |
| Macro avg | 0.5098 | 0.6538 | 0.5277 |
| Weighted avg | 0.6430 | 0.4642 | 0.4195 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_6_1    |      0.5749 |   0.8196 |     0.6757 | 41041.0000 | False   |
| H_2_1    |      0.6904 |   0.6530 |     0.6712 | 55263.0000 | False   |
| H_4_3    |      0.6037 |   0.7335 |     0.6623 | 46071.0000 | False   |
| V_7_0    |      0.6297 |   0.6287 |     0.6292 | 35933.0000 | True    |
| V_7_2    |      0.4994 |   0.8349 |     0.6250 | 37142.0000 | False   |
| H_4_5    |      0.5445 |   0.7141 |     0.6179 | 45207.0000 | False   |
| H_2_5    |      0.5694 |   0.6713 |     0.6161 | 51567.0000 | False   |
| H_6_3    |      0.5006 |   0.7819 |     0.6104 | 37305.0000 | False   |
| V_3_2    |      0.5879 |   0.6276 |     0.6071 | 55320.0000 | False   |
| V_1_0    |      0.7582 |   0.5044 |     0.6058 | 55222.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_0_5    |      0.6754 |   0.3133 |     0.4281 | 102692.0000 | True    |
| V_5_4    |      0.2629 |   0.6440 |     0.3734 |  45180.0000 | False   |
| H_0_3    |      0.6641 |   0.2220 |     0.3328 | 173065.0000 | True    |
| V_1_6    |      0.1564 |   0.6237 |     0.2501 |  43254.0000 | True    |
| H_0_1    |      0.9825 |   0.0651 |     0.1221 | 524156.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |       N | Top-1   | Top-3   | OMA   |
|:-----------|--------:|:--------|:--------|:------|
| 0 cadeias  | 1309160 | 37.3%   | 49.9%   | 88.9% |
| 1 cadeia   |  635156 | 63.3%   | 84.7%   | 94.7% |
| 2 cadeias  |  107688 | 58.3%   | 79.9%   | 95.7% |
| ≥3 cadeias |    2072 | 44.9%   | 71.2%   | 96.3% |


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          86.6 |          86.6 |              86.6 |             86.7 |             7.1 |       12.9 |       71.9 |              16.3 |               2.1 |       0.0 |                          0.4 |                           2.1 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            71.4 |       41.9 |      100.0 |              70.6 |              47.0 |       0.7 |                          6.9 |                          38.0 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.8 |       61.7 |      100.0 |              48.0 |              84.1 |       6.8 |                         23.6 |                          66.9 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       82.9 |       99.9 |              31.1 |              55.7 |       8.7 |                         62.5 |                          55.7 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       99.8 |       42.7 |               0.0 |               0.0 |       0.0 |                         34.9 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |       N | Top-1   | Top-3   | Top-5   | OMA   |
|:----------------------------|--------:|:--------|:--------|:--------|:------|
| aresta_topo                 | 1953362 | 48.8%   | 65.3%   | 71.7%   | 90.7% |
| aresta_base                 | 1953308 | 48.8%   | 65.3%   | 71.7%   | 90.7% |
| aresta_esquerda             | 1953283 | 48.8%   | 65.3%   | 71.7%   | 90.7% |
| aresta_direita              | 1953491 | 48.7%   | 65.3%   | 71.5%   | 90.7% |
| caixa_fechada               | 1235834 | 63.9%   | 84.7%   | 90.3%   | 93.6% |
| eh_grau3                    |  942763 | 85.0%   | 100.0%  | 100.0%  | 99.8% |
| eh_grau2                    | 1763399 | 49.5%   | 67.1%   | 73.7%   | 89.6% |
| em_cadeia_curta             |  716826 | 54.8%   | 75.7%   | 82.6%   | 85.9% |
| em_cadeia_longa             |  744916 | 62.5%   | 84.0%   | 90.7%   | 94.9% |
| em_loop                     |   60436 | 63.3%   | 88.9%   | 96.1%   | 99.1% |
| em_cadeia_aberta_uma_ponta  |  390300 | 79.8%   | 100.0%  | 100.0%  | 99.6% |
| paridade_cadeia_longa_impar |  637228 | 63.2%   | 84.7%   | 91.4%   | 94.8% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 183248 de 2054076 (8.9%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 55.0%          |      20.1000 |
| eh_grau2                    | 85.8%       | 99.9%          |      14.1000 |
| aresta_base                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_topo                 | 95.1%       | 99.6%          |       4.5000 |
| aresta_esquerda             | 95.1%       | 99.6%          |       4.5000 |
| aresta_direita              | 95.1%       | 99.6%          |       4.5000 |
| em_loop                     | 2.9%        | 0.3%           |      -2.6000 |
| paridade_cadeia_longa_impar | 31.0%       | 18.2%          |     -12.8000 |
| em_cadeia_longa             | 36.3%       | 20.7%          |     -15.5000 |
| caixa_fechada               | 60.2%       | 43.1%          |     -17.0000 |
| em_cadeia_aberta_uma_ponta  | 19.0%       | 0.9%           |     -18.1000 |
| eh_grau3                    | 45.9%       | 0.9%           |     -45.0000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 753166 | 15.1%   | 21.4%   | 28.8%   | 87.1%  |
| 1a Metade (12-17)   | 410817 | 52.0%   | 73.4%   | 83.4%   | 80.3%  |
| 2a Metade (18-23)   | 410814 | 67.3%   | 88.2%   | 92.5%   | 98.8%  |
| Fase Quente (24-28) | 342342 | 65.3%   | 92.7%   | 97.4%   | 100.0% |
| Final (29-31)       | 136937 | 92.3%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` |
| Caminho | `d:\Desenvolvimento\arena-sagaz\arena-sagaz-backend\resultados\jogo_pontinhos\pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` |
| Tamanho | 90.5 KB |
| Quantizacao | DEFAULT (float16 / dynamic range) |


---

