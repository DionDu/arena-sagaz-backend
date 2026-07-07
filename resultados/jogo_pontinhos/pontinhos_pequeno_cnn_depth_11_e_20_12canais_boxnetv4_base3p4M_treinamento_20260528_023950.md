
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-27 21:51 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_minimax_11_adaptativo` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 419 |
| Total de amostras | 3,423,460 |
| Treino | 2,396,421 |
| Validacao | 513,520 |
| Teste | 513,519 |

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
| Modelo | BoxNet_v4_V11_12canais |
| Input shape | (4, 3, 12) |
| Parâmetros treináveis | 4,951,839 |
| Classes | 31 |
| Loss | KL Divergence |
| Optimizer | Adam (lr=1e-3) |
| L2 regularização | 0.0 |
| Monitor de época | val_oma (max) |
| Batch size | 512 |
| EarlyStopping patience | 15 |
| ReduceLROnPlateau patience | 6 |

**Estrutura das Camadas:**

| Camada                 | Tipo               | Output Shape      | Param #   | Connected to                                  | Treinável   |
|:-----------------------|:-------------------|:------------------|:----------|:----------------------------------------------|:------------|
| canais_estruturais     | InputLayer         | (None, 4, 3, 12)  | 0         | —                                             | True        |
| conv2d                 | Conv2D             | (None, 4, 3, 64)  | 6,912     | canais_estruturais                            | True        |
| batch_normalization    | BatchNormalization | (None, 4, 3, 64)  | 256       | conv2d                                        | True        |
| activation             | Activation         | (None, 4, 3, 64)  | 0         | batch_normalization                           | True        |
| conv2d_1               | Conv2D             | (None, 4, 3, 64)  | 36,864    | activation                                    | True        |
| batch_normalization_1  | BatchNormalization | (None, 4, 3, 64)  | 256       | conv2d_1                                      | True        |
| activation_1           | Activation         | (None, 4, 3, 64)  | 0         | batch_normalization_1                         | True        |
| conv2d_2               | Conv2D             | (None, 4, 3, 64)  | 36,864    | activation_1                                  | True        |
| batch_normalization_2  | BatchNormalization | (None, 4, 3, 64)  | 256       | conv2d_2                                      | True        |
| add                    | Add                | (None, 4, 3, 64)  | 0         | batch_normalization_2, activation             | True        |
| activation_2           | Activation         | (None, 4, 3, 64)  | 0         | add                                           | True        |
| conv2d_3               | Conv2D             | (None, 4, 3, 128) | 73,728    | activation_2                                  | True        |
| batch_normalization_3  | BatchNormalization | (None, 4, 3, 128) | 512       | conv2d_3                                      | True        |
| activation_3           | Activation         | (None, 4, 3, 128) | 0         | batch_normalization_3                         | True        |
| conv2d_4               | Conv2D             | (None, 4, 3, 128) | 147,456   | activation_3                                  | True        |
| conv2d_5               | Conv2D             | (None, 4, 3, 128) | 8,192     | activation_2                                  | True        |
| batch_normalization_4  | BatchNormalization | (None, 4, 3, 128) | 512       | conv2d_4                                      | True        |
| batch_normalization_5  | BatchNormalization | (None, 4, 3, 128) | 512       | conv2d_5                                      | True        |
| add_1                  | Add                | (None, 4, 3, 128) | 0         | batch_normalization_4, batch_normalization_5  | True        |
| activation_4           | Activation         | (None, 4, 3, 128) | 0         | add_1                                         | True        |
| conv2d_6               | Conv2D             | (None, 4, 3, 128) | 147,456   | activation_4                                  | True        |
| batch_normalization_6  | BatchNormalization | (None, 4, 3, 128) | 512       | conv2d_6                                      | True        |
| activation_5           | Activation         | (None, 4, 3, 128) | 0         | batch_normalization_6                         | True        |
| conv2d_7               | Conv2D             | (None, 4, 3, 128) | 147,456   | activation_5                                  | True        |
| batch_normalization_7  | BatchNormalization | (None, 4, 3, 128) | 512       | conv2d_7                                      | True        |
| add_2                  | Add                | (None, 4, 3, 128) | 0         | batch_normalization_7, activation_4           | True        |
| activation_6           | Activation         | (None, 4, 3, 128) | 0         | add_2                                         | True        |
| conv2d_8               | Conv2D             | (None, 4, 3, 256) | 294,912   | activation_6                                  | True        |
| batch_normalization_8  | BatchNormalization | (None, 4, 3, 256) | 1,024     | conv2d_8                                      | True        |
| activation_7           | Activation         | (None, 4, 3, 256) | 0         | batch_normalization_8                         | True        |
| conv2d_9               | Conv2D             | (None, 4, 3, 256) | 589,824   | activation_7                                  | True        |
| conv2d_10              | Conv2D             | (None, 4, 3, 256) | 32,768    | activation_6                                  | True        |
| batch_normalization_9  | BatchNormalization | (None, 4, 3, 256) | 1,024     | conv2d_9                                      | True        |
| batch_normalization_10 | BatchNormalization | (None, 4, 3, 256) | 1,024     | conv2d_10                                     | True        |
| add_3                  | Add                | (None, 4, 3, 256) | 0         | batch_normalization_9, batch_normalization_10 | True        |
| activation_8           | Activation         | (None, 4, 3, 256) | 0         | add_3                                         | True        |
| conv2d_11              | Conv2D             | (None, 4, 3, 256) | 589,824   | activation_8                                  | True        |
| batch_normalization_11 | BatchNormalization | (None, 4, 3, 256) | 1,024     | conv2d_11                                     | True        |
| activation_9           | Activation         | (None, 4, 3, 256) | 0         | batch_normalization_11                        | True        |
| conv2d_12              | Conv2D             | (None, 4, 3, 256) | 589,824   | activation_9                                  | True        |
| batch_normalization_12 | BatchNormalization | (None, 4, 3, 256) | 1,024     | conv2d_12                                     | True        |
| add_4                  | Add                | (None, 4, 3, 256) | 0         | batch_normalization_12, activation_8          | True        |
| activation_10          | Activation         | (None, 4, 3, 256) | 0         | add_4                                         | True        |
| reshape                | Reshape            | (None, 12, 256)   | 0         | activation_10                                 | True        |
| layer_normalization    | LayerNormalization | (None, 12, 256)   | 512       | reshape                                       | True        |
| multi_head_attention   | MultiHeadAttention | (None, 12, 256)   | 263,168   | layer_normalization                           | True        |
| add_5                  | Add                | (None, 12, 256)   | 0         | reshape, multi_head_attention                 | True        |
| layer_normalization_1  | LayerNormalization | (None, 12, 256)   | 512       | add_5                                         | True        |
| dense                  | Dense              | (None, 12, 512)   | 131,584   | layer_normalization_1                         | True        |
| dense_1                | Dense              | (None, 12, 256)   | 131,328   | dense                                         | True        |
| add_6                  | Add                | (None, 12, 256)   | 0         | add_5, dense_1                                | True        |
| reshape_1              | Reshape            | (None, 4, 3, 256) | 0         | add_6                                         | True        |
| flatten                | Flatten            | (None, 3072)      | 0         | reshape_1                                     | True        |
| dense_2                | Dense              | (None, 512)       | 1,572,864 | flatten                                       | True        |
| batch_normalization_13 | BatchNormalization | (None, 512)       | 2,048     | dense_2                                       | True        |
| activation_11          | Activation         | (None, 512)       | 0         | batch_normalization_13                        | True        |
| dropout_1              | Dropout            | (None, 512)       | 0         | activation_11                                 | True        |
| dense_3                | Dense              | (None, 256)       | 131,328   | dropout_1                                     | True        |
| dropout_2              | Dropout            | (None, 256)       | 0         | dense_3                                       | True        |
| jogada                 | Dense              | (None, 31)        | 7,967     | dropout_2                                     | True        |


---


## 3. Treinamento

*(logs de epoca omitidos do relatorio — ver notebook)*

| Metrica | Valor |
|---------|-------|
| Epocas treinadas | 62 |
| KLD final — treino | 0.0136 |
| KLD final — val | 0.0166 |
| Top-1 final — treino | 0.5393 |
| Top-1 final — val | 0.5316 |
| **Melhor val_oma** | **0.9854** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 2,396,421 |     0.0072 |  0.5410 |  0.7171 |  0.7762 |
| Validação  | 513,520   |     0.0166 |  0.5330 |  0.7088 |  0.7699 |
| Teste      | 513,519   |     0.0165 |  0.5342 |  0.7095 |  0.7701 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.80 pp |
| Gap KLD (Val − Treino) | +0.0094 |
| **OMA global** | **98.6%** |
| Média jogadas Minimax-equiv. | 7.8 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 22.5%   | 35.4%   | 44.3%   | 97.5%  |
| 1a Metade (12-17)   | 102704 | 63.4%   | 84.8%   | 92.3%   | 97.5%  |
| 2a Metade (18-23)   | 102704 | 71.8%   | 91.6%   | 95.6%   | 99.9%  |
| Fase Quente (24-28) |  85586 | 71.7%   | 96.1%   | 99.1%   | 100.0% |
| Final (29-31)       |  34234 | 92.8%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.5342 |
| Macro avg | 0.5422 | 0.7316 | 0.5874 |
| Weighted avg | 0.6668 | 0.5342 | 0.4828 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_6_5    |      0.6440 |   0.8758 |     0.7422 |  9539.0000 | False   |
| V_7_2    |      0.5766 |   0.8876 |     0.6991 |  9309.0000 | False   |
| H_4_3    |      0.6762 |   0.7008 |     0.6883 | 11337.0000 | False   |
| H_6_3    |      0.5789 |   0.7948 |     0.6699 |  9273.0000 | False   |
| V_7_4    |      0.4935 |   0.9444 |     0.6482 |  8943.0000 | False   |
| H_4_5    |      0.4995 |   0.8798 |     0.6372 | 11384.0000 | False   |
| H_2_1    |      0.5716 |   0.7161 |     0.6357 | 13594.0000 | False   |
| H_6_1    |      0.4838 |   0.9134 |     0.6326 | 10232.0000 | False   |
| H_2_5    |      0.5252 |   0.7875 |     0.6301 | 12834.0000 | False   |
| V_1_4    |      0.6777 |   0.5864 |     0.6287 | 17199.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| V_5_6    |      0.3847 |   0.8834 |     0.5359 |   9152.0000 | True    |
| H_8_5    |      0.3370 |   0.9934 |     0.5033 |   5490.0000 | True    |
| H_0_5    |      0.7009 |   0.3478 |     0.4649 |  25673.0000 | True    |
| H_0_3    |      0.6782 |   0.3330 |     0.4467 |  43216.0000 | True    |
| H_0_1    |      0.9896 |   0.1060 |     0.1914 | 131346.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 327272 | 44.4%   | 60.2%   | 98.0% |
| 1 cadeia   | 158652 | 70.4%   | 90.9%   | 99.5% |
| 2 cadeias  |  27032 | 62.7%   | 84.8%   | 99.7% |
| ≥3 cadeias |    563 | 43.3%   | 63.6%   | 99.3% |


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

| Canal                       |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:----------------------------|-------:|:--------|:--------|:--------|:-------|
| aresta_topo                 | 488156 | 55.9%   | 73.9%   | 80.0%   | 98.5%  |
| aresta_base                 | 488342 | 55.9%   | 73.9%   | 80.0%   | 98.5%  |
| aresta_esquerda             | 488205 | 56.1%   | 74.3%   | 80.5%   | 98.5%  |
| aresta_direita              | 488350 | 55.9%   | 73.9%   | 80.0%   | 98.5%  |
| caixa_fechada               | 309017 | 70.6%   | 90.6%   | 95.1%   | 99.2%  |
| eh_grau3                    | 235646 | 87.4%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 440609 | 57.2%   | 76.5%   | 82.9%   | 98.3%  |
| em_cadeia_curta             | 179218 | 63.9%   | 85.2%   | 91.1%   | 98.1%  |
| em_cadeia_longa             | 186247 | 69.2%   | 89.9%   | 95.2%   | 99.5%  |
| em_loop                     |  15195 | 69.0%   | 91.8%   | 96.8%   | 100.0% |
| em_cadeia_aberta_uma_ponta  |  97007 | 83.0%   | 100.0%  | 100.0%  | 100.0% |
| paridade_cadeia_longa_impar | 159215 | 70.3%   | 90.8%   | 95.8%   | 99.5%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 7348 de 513519 (1.4%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 85.8%       | 99.8%          |      14.0000 |
| em_cadeia_curta             | 34.9%       | 47.0%          |      12.1000 |
| aresta_topo                 | 95.1%       | 99.6%          |       4.5000 |
| aresta_base                 | 95.1%       | 99.6%          |       4.5000 |
| aresta_esquerda             | 95.1%       | 99.5%          |       4.5000 |
| aresta_direita              | 95.1%       | 99.2%          |       4.1000 |
| em_loop                     | 3.0%        | 0.0%           |      -2.9000 |
| em_cadeia_aberta_uma_ponta  | 18.9%       | 0.3%           |     -18.6000 |
| paridade_cadeia_longa_impar | 31.0%       | 11.5%          |     -19.5000 |
| em_cadeia_longa             | 36.3%       | 12.6%          |     -23.6000 |
| caixa_fechada               | 60.2%       | 33.0%          |     -27.1000 |
| eh_grau3                    | 45.9%       | 0.3%           |     -45.6000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 22.5%   | 35.4%   | 44.3%   | 97.5%  |
| 1a Metade (12-17)   | 102704 | 63.4%   | 84.8%   | 92.3%   | 97.5%  |
| 2a Metade (18-23)   | 102704 | 71.8%   | 91.6%   | 95.6%   | 99.9%  |
| Fase Quente (24-28) |  85586 | 71.7%   | 96.1%   | 99.1%   | 100.0% |
| Final (29-31)       |  34234 | 92.8%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_base3p4M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_base3p4M.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

