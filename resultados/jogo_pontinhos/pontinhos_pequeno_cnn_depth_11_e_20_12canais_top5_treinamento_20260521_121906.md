
# Relatório de Treinamento — BoxNet V8

| Parâmetro | Valor |
|-----------|-------|
| Data | 2026-05-21 12:13 |
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
| Épocas treinadas | 13 |
| KLD final — treino | 0.2906 |
| KLD final — val | 0.2898 |
| Top-1 final — treino | 0.4587 |
| Top-1 final — val | 0.4207 |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N       |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:--------|-----------:|--------:|--------:|--------:|
| Treino     | 531,047 |     0.2588 |  0.4632 |  0.6261 |  0.7114 |
| Validação  | 113,797 |     0.2583 |  0.4618 |  0.6252 |  0.7119 |
| Teste      | 113,796 |     0.2600 |  0.4616 |  0.6249 |  0.7123 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.14 pp |
| Gap KLD (Val − Treino) | -0.0005 |
| **OMA global** | **88.0%** |
| Média jogadas Minimax-equiv. | 7.9 |


### 4.2 Métricas por Fase

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 14.8%   | 24.6%   | 37.1%   | 85.9%  |
| 1a Metade (12-17)   | 22759 | 48.2%   | 70.0%   | 81.8%   | 72.6%  |
| 2a Metade (18-23)   | 22759 | 67.5%   | 87.0%   | 91.7%   | 93.4%  |
| Fase Quente (24-28) | 18966 | 68.0%   | 92.3%   | 97.4%   | 99.8%  |
| Final (29-31)       |  7587 | 93.9%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.4616 |
| Macro avg | 0.5873 | 0.6441 | 0.5708 |
| Weighted avg | 0.6521 | 0.4616 | 0.4508 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |   support | Borda   |
|:---------|------------:|---------:|-----------:|----------:|:--------|
| V_7_2    |      0.8641 |   0.7489 |     0.8024 | 2071.0000 | False   |
| H_8_1    |      0.7225 |   0.8590 |     0.7849 | 1255.0000 | True    |
| V_7_4    |      0.6919 |   0.8198 |     0.7505 | 1926.0000 | False   |
| H_6_1    |      0.7606 |   0.7353 |     0.7478 | 2320.0000 | False   |
| V_7_0    |      0.7567 |   0.7172 |     0.7364 | 1934.0000 | True    |
| H_6_5    |      0.6172 |   0.8203 |     0.7044 | 2154.0000 | False   |
| H_4_5    |      0.6405 |   0.7018 |     0.6698 | 2458.0000 | False   |
| V_5_6    |      0.6651 |   0.6727 |     0.6689 | 2084.0000 | True    |
| H_8_3    |      0.5386 |   0.8385 |     0.6559 | 1449.0000 | True    |
| V_5_0    |      0.6891 |   0.6201 |     0.6528 | 2448.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_0_5    |      0.8584 |   0.2809 |     0.4232 |  5786.0000 | True    |
| V_3_2    |      0.2410 |   0.5927 |     0.3426 |  3047.0000 | False   |
| H_0_3    |      0.5817 |   0.2235 |     0.3229 |  9751.0000 | True    |
| H_4_1    |      0.0997 |   0.8969 |     0.1795 |  2706.0000 | False   |
| H_0_1    |      0.8299 |   0.1004 |     0.1792 | 29205.0000 | True    |

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
| aresta_topo                 | 108215 | 48.5%   | 65.6%   | 74.5%   | 87.4% |
| aresta_base                 | 108255 | 48.5%   | 65.5%   | 74.5%   | 87.4% |
| aresta_esquerda             | 108294 | 48.5%   | 65.5%   | 74.3%   | 87.4% |
| aresta_direita              | 108308 | 48.4%   | 65.5%   | 74.2%   | 87.4% |
| caixa_fechada               |  68284 | 63.9%   | 83.5%   | 89.9%   | 89.7% |
| eh_grau3                    |  50280 | 87.1%   | 100.0%  | 100.0%  | 98.9% |
| eh_grau2                    |  97780 | 49.1%   | 67.6%   | 76.9%   | 86.0% |
| em_cadeia_curta             |  39671 | 53.0%   | 74.0%   | 82.5%   | 80.2% |
| em_cadeia_longa             |  42794 | 62.0%   | 82.3%   | 89.7%   | 89.9% |
| em_loop                     |   3599 | 61.9%   | 88.3%   | 95.8%   | 97.2% |
| em_cadeia_aberta_uma_ponta  |  21624 | 81.4%   | 100.0%  | 100.0%  | 97.9% |
| paridade_cadeia_longa_impar |  36222 | 62.5%   | 82.7%   | 90.2%   | 89.9% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 13657 de 113796 (12.0%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 57.5%          |      22.7000 |
| eh_grau2                    | 85.9%       | 99.9%          |      14.0000 |
| aresta_base                 | 95.1%       | 99.8%          |       4.7000 |
| aresta_topo                 | 95.1%       | 99.7%          |       4.6000 |
| aresta_esquerda             | 95.2%       | 99.7%          |       4.6000 |
| aresta_direita              | 95.2%       | 99.7%          |       4.5000 |
| em_loop                     | 3.2%        | 0.7%           |      -2.4000 |
| paridade_cadeia_longa_impar | 31.8%       | 26.9%          |      -4.9000 |
| em_cadeia_longa             | 37.6%       | 31.5%          |      -6.1000 |
| caixa_fechada               | 60.0%       | 51.5%          |      -8.5000 |
| em_cadeia_aberta_uma_ponta  | 19.0%       | 3.3%           |     -15.7000 |
| eh_grau3                    | 44.2%       | 3.9%           |     -40.3000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 14.8%   | 24.6%   | 37.1%   | 85.9%  |
| 1a Metade (12-17)   | 22759 | 48.2%   | 70.0%   | 81.8%   | 72.6%  |
| 2a Metade (18-23)   | 22759 | 67.5%   | 87.0%   | 91.7%   | 93.4%  |
| Fase Quente (24-28) | 18966 | 68.0%   | 92.3%   | 97.4%   | 99.8%  |
| Final (29-31)       |  7587 | 93.9%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportação TFLite

| Parâmetro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais.tflite` |
| Tamanho | 91.7 KB |
| Drive | `/content/drive/MyDrive/Arena Sagaz/CNN/pontinhos_pequeno_cnn_depth_11_e_20_12canais.tflite` |
| Quantização | DEFAULT (float16 / dynamic range) |


---

