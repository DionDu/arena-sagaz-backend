
# Relatório de Treinamento — BoxNet V8

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-14 00:43 |
| Canais (11) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta |
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
| Modelo | BoxNet_v3_V8_11canais |
| Input shape | (4, 3, 11) |
| Parâmetros treináveis | 76,239 |
| Classes | 31 |
| Loss | KL Divergence |
| Optimizer | Adam (lr=1e-3) |
| L2 regularização | 0.0002 |
| Batch size | 256 |
| EarlyStopping patience | 10 |
| ReduceLROnPlateau patience | 4 |

**Estrutura das Camadas:**

| Camada                     | Tipo                   | Output Shape     | Param #   | Connected to                                   | Treinável   |
|:---------------------------|:-----------------------|:-----------------|:----------|:-----------------------------------------------|:------------|
| canais_estruturais         | InputLayer             | (None, 4, 3, 11) | 0         | —                                              | True        |
| conv2d_4                   | Conv2D                 | (None, 4, 3, 32) | 3,168     | canais_estruturais                             | True        |
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
| Épocas treinadas | 59 |
| KLD final — treino | 0.2241 |
| KLD final — val | 0.1345 |
| Top-1 final — treino | 0.4692 |
| Top-1 final — val | 0.5880 |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N       |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:--------|-----------:|--------:|--------:|--------:|
| Treino     | 531,047 |     0.1666 |  0.7131 |  0.8819 |  0.9228 |
| Validação  | 113,797 |     0.1669 |  0.7126 |  0.8810 |  0.9235 |
| Teste      | 113,796 |     0.1669 |  0.7119 |  0.8810 |  0.9223 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.05 pp |
| Gap KLD (Val − Treino) | +0.0003 |
| **OMA global** | **93.4%** |
| Média jogadas Minimax-equiv. | 8.4 |


### 4.2 Métricas por Fase

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 76.2%   | 89.6%   | 91.1%   | 95.9%  |
| 1a Metade (12-17)   | 22759 | 53.1%   | 74.7%   | 84.4%   | 77.0%  |
| 2a Metade (18-23)   | 22759 | 73.5%   | 90.5%   | 95.0%   | 97.5%  |
| Fase Quente (24-28) | 18966 | 69.9%   | 93.3%   | 97.7%   | 100.0% |
| Final (29-31)       |  7587 | 94.1%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.7119 |
| Macro avg | 0.7100 | 0.7121 | 0.6731 |
| Weighted avg | 0.7838 | 0.7119 | 0.7133 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_8_5    |      0.8356 |   0.9636 |     0.8951 |  1155.0000 | True    |
| H_0_1    |      0.9499 |   0.7960 |     0.8662 | 31921.0000 | True    |
| V_7_4    |      0.7839 |   0.8333 |     0.8079 |  1950.0000 | False   |
| H_2_1    |      0.8354 |   0.7716 |     0.8022 |  2605.0000 | False   |
| H_2_5    |      0.7872 |   0.7627 |     0.7747 |  2604.0000 | False   |
| H_8_3    |      0.6468 |   0.8946 |     0.7508 |  1423.0000 | True    |
| H_4_3    |      0.7301 |   0.7578 |     0.7437 |  2399.0000 | False   |
| H_6_5    |      0.6467 |   0.8263 |     0.7255 |  2217.0000 | False   |
| H_6_1    |      0.6228 |   0.8288 |     0.7112 |  2325.0000 | False   |
| V_5_4    |      0.7036 |   0.7139 |     0.7087 |  2464.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |   support | Borda   |
|:---------|------------:|---------:|-----------:|----------:|:--------|
| V_7_2    |      0.4220 |   0.8779 |     0.5700 | 2113.0000 | False   |
| H_8_1    |      0.3891 |   0.9443 |     0.5511 | 1220.0000 | True    |
| V_5_6    |      0.4142 |   0.8088 |     0.5478 | 2040.0000 | True    |
| V_5_2    |      0.3851 |   0.7459 |     0.5079 | 2487.0000 | False   |
| H_0_5    |      0.9630 |   0.2575 |     0.4063 | 6059.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|
| Abertura (0-11)     |          86.6 |          86.7 |              86.8 |             86.8 |             7.5 |       11.4 |       71.9 |              16.8 |               2.2 |       0.0 |                          0.3 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            70.0 |       36.6 |      100.0 |              72.1 |              49.5 |       0.8 |                          6.0 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.7 |       60.8 |      100.0 |              47.0 |              86.5 |       7.4 |                         23.8 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       83.3 |      100.0 |              29.2 |              57.6 |       9.0 |                         63.4 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |      100.0 |       43.4 |               0.0 |               0.0 |       0.0 |                         35.6 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                      |      N | Top-1   | Top-3   | Top-5   | OMA   |
|:---------------------------|-------:|:--------|:--------|:--------|:------|
| aresta_topo                | 108215 | 70.2%   | 87.5%   | 91.8%   | 93.1% |
| aresta_base                | 108255 | 70.4%   | 87.6%   | 92.0%   | 93.1% |
| aresta_esquerda            | 108294 | 70.7%   | 87.6%   | 91.9%   | 93.1% |
| aresta_direita             | 108308 | 70.6%   | 87.6%   | 91.9%   | 93.1% |
| caixa_fechada              |  68284 | 69.6%   | 88.0%   | 93.2%   | 93.4% |
| eh_grau3                   |  50280 | 87.3%   | 100.0%  | 100.0%  | 99.9% |
| eh_grau2                   |  97780 | 68.4%   | 86.3%   | 91.1%   | 92.3% |
| em_cadeia_curta            |  39671 | 62.7%   | 82.7%   | 88.7%   | 87.0% |
| em_cadeia_longa            |  42794 | 68.0%   | 86.8%   | 93.0%   | 93.7% |
| em_loop                    |   3599 | 71.3%   | 90.0%   | 96.3%   | 98.9% |
| em_cadeia_aberta_uma_ponta |  21624 | 82.5%   | 100.0%  | 100.0%  | 99.8% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 7525 de 113796 (6.6%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                      | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:---------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta            | 34.9%       | 68.3%          |      33.5000 |
| eh_grau2                   | 85.9%       | 100.0%         |      14.1000 |
| aresta_topo                | 95.1%       | 99.9%          |       4.8000 |
| aresta_direita             | 95.2%       | 100.0%         |       4.8000 |
| aresta_base                | 95.1%       | 100.0%         |       4.8000 |
| aresta_esquerda            | 95.2%       | 99.9%          |       4.7000 |
| caixa_fechada              | 60.0%       | 59.7%          |      -0.3000 |
| em_cadeia_longa            | 37.6%       | 35.8%          |      -1.8000 |
| em_loop                    | 3.2%        | 0.5%           |      -2.6000 |
| em_cadeia_aberta_uma_ponta | 19.0%       | 0.6%           |     -18.4000 |
| eh_grau3                   | 44.2%       | 0.6%           |     -43.5000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 76.2%   | 89.6%   | 91.1%   | 95.9%  |
| 1a Metade (12-17)   | 22759 | 53.1%   | 74.7%   | 84.4%   | 77.0%  |
| 2a Metade (18-23)   | 22759 | 73.5%   | 90.5%   | 95.0%   | 97.5%  |
| Fase Quente (24-28) | 18966 | 69.9%   | 93.3%   | 97.7%   | 100.0% |
| Final (29-31)       |  7587 | 94.1%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportação TFLite

| Parâmetro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_profundidade_11_v8_11canais.tflite` |
| Tamanho | 91.5 KB |
| Drive | `/content/drive/MyDrive/Arena Sagaz/CNN/pontinhos_pequeno_profundidade_11_v8_11canais.tflite` |
| Quantização | DEFAULT (float16 / dynamic range) |


---

