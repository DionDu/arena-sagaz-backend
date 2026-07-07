
# Relatório de Treinamento — BoxNet V9

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-25 11:43 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parâmetro | Valor |
|-----------|-------|
| Arquivos NPZ | 419 |
| Total de amostras | 3,423,460 |
| Treino | 2,396,421 |
| Validação | 513,520 |
| Teste | 513,519 |

**Distribuição por fase (%)**

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

| Camada                   | Tipo                   | Output Shape     | Param #   | Connected to                                 | Treinável   |
|:-------------------------|:-----------------------|:-----------------|:----------|:---------------------------------------------|:------------|
| canais_estruturais       | InputLayer             | (None, 4, 3, 12) | 0         | —                                            | True        |
| conv2d                   | Conv2D                 | (None, 4, 3, 32) | 3,456     | canais_estruturais                           | True        |
| batch_normalization      | BatchNormalization     | (None, 4, 3, 32) | 128       | conv2d                                       | True        |
| activation               | Activation             | (None, 4, 3, 32) | 0         | batch_normalization                          | True        |
| separable_conv2d         | SeparableConv2D        | (None, 4, 3, 32) | 1,312     | activation                                   | True        |
| batch_normalization_1    | BatchNormalization     | (None, 4, 3, 32) | 128       | separable_conv2d                             | True        |
| activation_1             | Activation             | (None, 4, 3, 32) | 0         | batch_normalization_1                        | True        |
| spatial_dropout2d        | SpatialDropout2D       | (None, 4, 3, 32) | 0         | activation_1                                 | True        |
| separable_conv2d_1       | SeparableConv2D        | (None, 4, 3, 32) | 1,312     | spatial_dropout2d                            | True        |
| batch_normalization_2    | BatchNormalization     | (None, 4, 3, 32) | 128       | separable_conv2d_1                           | True        |
| add                      | Add                    | (None, 4, 3, 32) | 0         | batch_normalization_2, activation            | True        |
| activation_2             | Activation             | (None, 4, 3, 32) | 0         | add                                          | True        |
| separable_conv2d_2       | SeparableConv2D        | (None, 4, 3, 48) | 1,824     | activation_2                                 | True        |
| batch_normalization_3    | BatchNormalization     | (None, 4, 3, 48) | 192       | separable_conv2d_2                           | True        |
| activation_3             | Activation             | (None, 4, 3, 48) | 0         | batch_normalization_3                        | True        |
| spatial_dropout2d_1      | SpatialDropout2D       | (None, 4, 3, 48) | 0         | activation_3                                 | True        |
| separable_conv2d_3       | SeparableConv2D        | (None, 4, 3, 48) | 2,736     | spatial_dropout2d_1                          | True        |
| conv2d_1                 | Conv2D                 | (None, 4, 3, 48) | 1,536     | activation_2                                 | True        |
| batch_normalization_4    | BatchNormalization     | (None, 4, 3, 48) | 192       | separable_conv2d_3                           | True        |
| batch_normalization_5    | BatchNormalization     | (None, 4, 3, 48) | 192       | conv2d_1                                     | True        |
| add_1                    | Add                    | (None, 4, 3, 48) | 0         | batch_normalization_4, batch_normalization_5 | True        |
| activation_4             | Activation             | (None, 4, 3, 48) | 0         | add_1                                        | True        |
| global_average_pooling2d | GlobalAveragePooling2D | (None, 48)       | 0         | activation_4                                 | True        |
| flatten                  | Flatten                | (None, 576)      | 0         | activation_4                                 | True        |
| concatenate              | Concatenate            | (None, 624)      | 0         | global_average_pooling2d, flatten            | True        |
| dense                    | Dense                  | (None, 96)       | 60,000    | concatenate                                  | True        |
| batch_normalization_6    | BatchNormalization     | (None, 96)       | 384       | dense                                        | True        |
| dropout                  | Dropout                | (None, 96)       | 0         | batch_normalization_6                        | True        |
| jogada                   | Dense                  | (None, 31)       | 3,007     | dropout                                      | True        |


---


## 3. Treinamento

*(logs de época omitidos do relatório — ver notebook)*

| Métrica | Valor |
|---------|-------|
| Épocas treinadas | 144 |
| KLD final — treino | 0.2414 |
| KLD final — val | 0.1558 |
| Top-1 final — treino | 0.4757 |
| Top-1 final — val | 0.4753 |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 2,396,421 |     0.1550 |  0.4723 |  0.6339 |  0.7117 |
| Validação  | 513,520   |     0.1558 |  0.4703 |  0.6328 |  0.7113 |
| Teste      | 513,519   |     0.1555 |  0.4718 |  0.6335 |  0.7122 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.20 pp |
| Gap KLD (Val − Treino) | +0.0008 |
| **OMA global** | **90.7%** |
| Média jogadas Minimax-equiv. | 7.8 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 15.3%   | 23.2%   | 34.5%   | 87.3%  |
| 1a Metade (12-17)   | 102704 | 51.4%   | 73.1%   | 83.4%   | 78.5%  |
| 2a Metade (18-23)   | 102704 | 70.0%   | 90.0%   | 94.2%   | 98.3%  |
| Fase Quente (24-28) |  85586 | 66.6%   | 93.4%   | 98.4%   | 100.0% |
| Final (29-31)       |  34234 | 92.8%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.4718 |
| Macro avg | 0.5129 | 0.6573 | 0.5367 |
| Weighted avg | 0.6148 | 0.4718 | 0.4293 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_7_6    |      0.7140 |   0.6847 |     0.6991 |  8098.0000 | True    |
| V_1_6    |      0.7428 |   0.6322 |     0.6830 | 10766.0000 | True    |
| V_7_0    |      0.7067 |   0.6531 |     0.6788 |  8907.0000 | True    |
| V_7_2    |      0.5269 |   0.8368 |     0.6467 |  9309.0000 | False   |
| V_5_2    |      0.5850 |   0.7204 |     0.6457 | 11611.0000 | False   |
| H_6_3    |      0.5561 |   0.7598 |     0.6422 |  9273.0000 | False   |
| H_2_5    |      0.5923 |   0.6861 |     0.6357 | 12834.0000 | False   |
| V_3_2    |      0.6422 |   0.6089 |     0.6251 | 13944.0000 | False   |
| V_3_4    |      0.6428 |   0.5981 |     0.6196 | 13520.0000 | False   |
| V_1_0    |      0.6835 |   0.5516 |     0.6105 | 13975.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| V_5_6    |      0.2857 |   0.6942 |     0.4048 |   9152.0000 | True    |
| H_8_3    |      0.2432 |   0.8667 |     0.3798 |   6632.0000 | True    |
| H_8_1    |      0.2358 |   0.9171 |     0.3752 |   5924.0000 | True    |
| H_0_3    |      0.3251 |   0.2298 |     0.2693 |  43216.0000 | True    |
| H_0_1    |      0.9489 |   0.0809 |     0.1490 | 131346.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          86.5 |          86.6 |              86.6 |             86.6 |             7.2 |       12.8 |       71.7 |              16.4 |               2.1 |       0.0 |                          0.4 |                           2.1 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            71.4 |       41.9 |      100.0 |              70.5 |              47.2 |       0.7 |                          6.8 |                          38.1 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.7 |       61.7 |      100.0 |              47.9 |              84.1 |       6.8 |                         23.4 |                          66.9 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       82.9 |       99.9 |              31.3 |              55.5 |       8.8 |                         62.3 |                          55.5 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       99.8 |       42.7 |               0.0 |               0.0 |       0.0 |                         35.0 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |      N | Top-1   | Top-3   | Top-5   | OMA   |
|:----------------------------|-------:|:--------|:--------|:--------|:------|
| aresta_topo                 | 488156 | 49.6%   | 66.2%   | 73.6%   | 90.3% |
| aresta_base                 | 488342 | 49.5%   | 66.2%   | 73.7%   | 90.3% |
| aresta_esquerda             | 488205 | 49.6%   | 66.3%   | 74.2%   | 90.3% |
| aresta_direita              | 488350 | 49.6%   | 66.4%   | 74.2%   | 90.3% |
| caixa_fechada               | 309017 | 65.0%   | 85.5%   | 91.1%   | 93.0% |
| eh_grau3                    | 235646 | 85.4%   | 100.0%  | 100.0%  | 99.8% |
| eh_grau2                    | 440609 | 50.3%   | 68.0%   | 75.5%   | 89.2% |
| em_cadeia_curta             | 179218 | 55.3%   | 75.9%   | 83.0%   | 85.0% |
| em_cadeia_longa             | 186247 | 64.2%   | 85.3%   | 91.9%   | 94.1% |
| em_loop                     |  15195 | 66.9%   | 89.7%   | 97.0%   | 98.9% |
| em_cadeia_aberta_uma_ponta  |  97007 | 80.0%   | 100.0%  | 100.0%  | 99.5% |
| paridade_cadeia_longa_impar | 159215 | 64.7%   | 85.7%   | 92.4%   | 94.0% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 47672 de 513519 (9.3%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 56.6%          |      21.7000 |
| eh_grau2                    | 85.8%       | 99.9%          |      14.1000 |
| aresta_topo                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_base                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_esquerda             | 95.1%       | 99.7%          |       4.6000 |
| aresta_direita              | 95.1%       | 99.6%          |       4.5000 |
| em_loop                     | 3.0%        | 0.3%           |      -2.6000 |
| paridade_cadeia_longa_impar | 31.0%       | 20.1%          |     -10.9000 |
| em_cadeia_longa             | 36.3%       | 22.9%          |     -13.4000 |
| caixa_fechada               | 60.2%       | 45.5%          |     -14.6000 |
| em_cadeia_aberta_uma_ponta  | 18.9%       | 0.9%           |     -17.9000 |
| eh_grau3                    | 45.9%       | 1.0%           |     -44.9000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 15.3%   | 23.2%   | 34.5%   | 87.3%  |
| 1a Metade (12-17)   | 102704 | 51.4%   | 73.1%   | 83.4%   | 78.5%  |
| 2a Metade (18-23)   | 102704 | 70.0%   | 90.0%   | 94.2%   | 98.3%  |
| Fase Quente (24-28) |  85586 | 66.6%   | 93.4%   | 98.4%   | 100.0% |
| Final (29-31)       |  34234 | 92.8%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportação TFLite

| Parâmetro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` |
| Tamanho | 91.7 KB |
| Drive | `/content/drive/MyDrive/Arena Sagaz/CNN/pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` |
| Quantização | DEFAULT (float16 / dynamic range) |


---

