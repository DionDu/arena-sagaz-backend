
# Relatório de Treinamento — BoxNet V8

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-21 12:59 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parâmetro | Valor |
|-----------|-------|
| Arquivos NPZ | 152 |
| Total de amostras | 758,640 |
| Treino | 531,047 |
| Validação | 113,797 |
| Teste | 113,796 |

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

| Camada                     | Tipo                   | Output Shape     | Param #   | Connected to                                   | Treinável   |
|:---------------------------|:-----------------------|:-----------------|:----------|:-----------------------------------------------|:------------|
| canais_estruturais         | InputLayer             | (None, 4, 3, 12) | 0         | —                                              | True        |
| conv2d_4                   | Conv2D                 | (None, 4, 3, 32) | 3,456     | canais_estruturais                             | True        |
| batch_normalization_14     | BatchNormalization     | (None, 4, 3, 32) | 128       | conv2d_4                                       | True        |
| activation_10              | Activation             | (None, 4, 3, 32) | 0         | batch_normalization_14                         | True        |
| separable_conv2d_8         | SeparableConv2D        | (None, 4, 3, 32) | 1,312     | activation_10                                  | True        |
| batch_normalization_15     | BatchNormalization     | (None, 4, 3, 32) | 128       | separable_conv2d_8                             | True        |
| activation_11              | Activation             | (None, 4, 3, 32) | 0         | batch_normalization_15                         | True        |
| spatial_dropout2d_4        | SpatialDropout2D       | (None, 4, 3, 32) | 0         | activation_11                                  | True        |
| separable_conv2d_9         | SeparableConv2D        | (None, 4, 3, 32) | 1,312     | spatial_dropout2d_4                            | True        |
| batch_normalization_16     | BatchNormalization     | (None, 4, 3, 32) | 128       | separable_conv2d_9                             | True        |
| add_4                      | Add                    | (None, 4, 3, 32) | 0         | batch_normalization_16, activation_10          | True        |
| activation_12              | Activation             | (None, 4, 3, 32) | 0         | add_4                                          | True        |
| separable_conv2d_10        | SeparableConv2D        | (None, 4, 3, 48) | 1,824     | activation_12                                  | True        |
| batch_normalization_17     | BatchNormalization     | (None, 4, 3, 48) | 192       | separable_conv2d_10                            | True        |
| activation_13              | Activation             | (None, 4, 3, 48) | 0         | batch_normalization_17                         | True        |
| spatial_dropout2d_5        | SpatialDropout2D       | (None, 4, 3, 48) | 0         | activation_13                                  | True        |
| separable_conv2d_11        | SeparableConv2D        | (None, 4, 3, 48) | 2,736     | spatial_dropout2d_5                            | True        |
| conv2d_5                   | Conv2D                 | (None, 4, 3, 48) | 1,536     | activation_12                                  | True        |
| batch_normalization_18     | BatchNormalization     | (None, 4, 3, 48) | 192       | separable_conv2d_11                            | True        |
| batch_normalization_19     | BatchNormalization     | (None, 4, 3, 48) | 192       | conv2d_5                                       | True        |
| add_5                      | Add                    | (None, 4, 3, 48) | 0         | batch_normalization_18, batch_normalization_19 | True        |
| activation_14              | Activation             | (None, 4, 3, 48) | 0         | add_5                                          | True        |
| global_average_pooling2d_2 | GlobalAveragePooling2D | (None, 48)       | 0         | activation_14                                  | True        |
| flatten_2                  | Flatten                | (None, 576)      | 0         | activation_14                                  | True        |
| concatenate_2              | Concatenate            | (None, 624)      | 0         | global_average_pooling2d_2, flatten_2          | True        |
| dense_2                    | Dense                  | (None, 96)       | 60,000    | concatenate_2                                  | True        |
| batch_normalization_20     | BatchNormalization     | (None, 96)       | 384       | dense_2                                        | True        |
| dropout_2                  | Dropout                | (None, 96)       | 0         | batch_normalization_20                         | True        |
| jogada                     | Dense                  | (None, 31)       | 3,007     | dropout_2                                      | True        |


---


## 3. Treinamento

*(logs de época omitidos do relatório — ver notebook)*

| Métrica | Valor |
|---------|-------|
| Épocas treinadas | 157 |
| KLD final — treino | 0.2518 |
| KLD final — val | 0.1688 |
| Top-1 final — treino | 0.4638 |
| Top-1 final — val | 0.4725 |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N       |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:--------|-----------:|--------:|--------:|--------:|
| Treino     | 531,047 |     0.1669 |  0.4690 |  0.6245 |  0.6858 |
| Validação  | 113,797 |     0.1685 |  0.4679 |  0.6239 |  0.6844 |
| Teste      | 113,796 |     0.1693 |  0.4674 |  0.6222 |  0.6821 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.11 pp |
| Gap KLD (Val − Treino) | +0.0016 |
| **OMA global** | **89.7%** |
| Média jogadas Minimax-equiv. | 7.9 |


### 4.2 Métricas por Fase

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 16.0%   | 23.4%   | 29.9%   | 86.5%  |
| 1a Metade (12-17)   | 22759 | 49.0%   | 70.8%   | 81.2%   | 75.9%  |
| 2a Metade (18-23)   | 22759 | 67.7%   | 86.6%   | 90.9%   | 97.5%  |
| Fase Quente (24-28) | 18966 | 69.0%   | 93.1%   | 97.0%   | 100.0% |
| Final (29-31)       |  7587 | 90.7%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.4674 |
| Macro avg | 0.5004 | 0.6576 | 0.5308 |
| Weighted avg | 0.6137 | 0.4674 | 0.4174 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |   support | Borda   |
|:---------|------------:|---------:|-----------:|----------:|:--------|
| H_6_5    |      0.5618 |   0.8162 |     0.6655 | 2154.0000 | False   |
| V_7_6    |      0.5855 |   0.7533 |     0.6589 | 1650.0000 | True    |
| V_7_2    |      0.5450 |   0.8180 |     0.6542 | 2071.0000 | False   |
| H_2_5    |      0.6186 |   0.6758 |     0.6459 | 2856.0000 | False   |
| V_3_2    |      0.6767 |   0.6154 |     0.6446 | 3047.0000 | False   |
| V_5_4    |      0.6322 |   0.6533 |     0.6426 | 2518.0000 | False   |
| H_8_1    |      0.4703 |   0.8972 |     0.6172 | 1255.0000 | True    |
| V_7_0    |      0.5375 |   0.7187 |     0.6150 | 1934.0000 | True    |
| H_6_1    |      0.4881 |   0.7974 |     0.6056 | 2320.0000 | False   |
| V_5_2    |      0.5586 |   0.6289 |     0.5917 | 2592.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_0_5    |      0.8471 |   0.2710 |     0.4106 |  5786.0000 | True    |
| V_3_0    |      0.3207 |   0.5488 |     0.4048 |  3280.0000 | True    |
| V_5_0    |      0.2995 |   0.6193 |     0.4038 |  2448.0000 | True    |
| H_0_3    |      0.4073 |   0.2570 |     0.3151 |  9751.0000 | True    |
| H_0_1    |      0.9505 |   0.0717 |     0.1333 | 29205.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          86.6 |          86.7 |              86.8 |             86.8 |             7.5 |       11.4 |       71.9 |              16.8 |               2.2 |       0.0 |                          0.3 |                           2.1 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            70.0 |       36.6 |      100.0 |              72.1 |              49.5 |       0.8 |                          6.0 |                          39.5 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.7 |       60.8 |      100.0 |              47.0 |              86.5 |       7.4 |                         23.8 |                          67.7 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       83.3 |      100.0 |              29.2 |              57.6 |       9.0 |                         63.4 |                          57.6 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |      100.0 |       43.4 |               0.0 |               0.0 |       0.0 |                         35.6 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |      N | Top-1   | Top-3   | Top-5   | OMA   |
|:----------------------------|-------:|:--------|:--------|:--------|:------|
| aresta_topo                 | 108215 | 49.1%   | 65.4%   | 71.6%   | 89.2% |
| aresta_base                 | 108255 | 48.8%   | 64.9%   | 71.1%   | 89.2% |
| aresta_esquerda             | 108294 | 48.9%   | 64.9%   | 71.1%   | 89.2% |
| aresta_direita              | 108308 | 48.9%   | 64.9%   | 71.1%   | 89.2% |
| caixa_fechada               |  68284 | 64.0%   | 83.6%   | 89.0%   | 92.0% |
| eh_grau3                    |  50280 | 85.7%   | 100.0%  | 100.0%  | 99.7% |
| eh_grau2                    |  97780 | 49.4%   | 66.7%   | 73.3%   | 88.0% |
| em_cadeia_curta             |  39671 | 53.8%   | 73.9%   | 81.0%   | 82.9% |
| em_cadeia_longa             |  42794 | 62.5%   | 82.7%   | 89.3%   | 93.1% |
| em_loop                     |   3599 | 73.4%   | 91.6%   | 97.2%   | 98.9% |
| em_cadeia_aberta_uma_ponta  |  21624 | 81.1%   | 100.0%  | 100.0%  | 99.3% |
| paridade_cadeia_longa_impar |  36222 | 63.5%   | 83.8%   | 90.3%   | 92.9% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 11696 de 113796 (10.3%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 57.9%          |      23.1000 |
| eh_grau2                    | 85.9%       | 99.9%          |      14.0000 |
| aresta_topo                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_base                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_direita              | 95.2%       | 99.6%          |       4.5000 |
| aresta_esquerda             | 95.2%       | 99.7%          |       4.5000 |
| em_loop                     | 3.2%        | 0.4%           |      -2.8000 |
| paridade_cadeia_longa_impar | 31.8%       | 22.0%          |      -9.8000 |
| em_cadeia_longa             | 37.6%       | 25.4%          |     -12.2000 |
| caixa_fechada               | 60.0%       | 46.8%          |     -13.2000 |
| em_cadeia_aberta_uma_ponta  | 19.0%       | 1.4%           |     -17.6000 |
| eh_grau3                    | 44.2%       | 1.4%           |     -42.8000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 16.0%   | 23.4%   | 29.9%   | 86.5%  |
| 1a Metade (12-17)   | 22759 | 49.0%   | 70.8%   | 81.2%   | 75.9%  |
| 2a Metade (18-23)   | 22759 | 67.7%   | 86.6%   | 90.9%   | 97.5%  |
| Fase Quente (24-28) | 18966 | 69.0%   | 93.1%   | 97.0%   | 100.0% |
| Final (29-31)       |  7587 | 90.7%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportação TFLite

| Parâmetro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais.tflite` |
| Tamanho | 91.8 KB |
| Drive | `/content/drive/MyDrive/Arena Sagaz/CNN/pontinhos_pequeno_cnn_depth_11_e_20_12canais.tflite` |
| Quantização | DEFAULT (float16 / dynamic range) |


---

