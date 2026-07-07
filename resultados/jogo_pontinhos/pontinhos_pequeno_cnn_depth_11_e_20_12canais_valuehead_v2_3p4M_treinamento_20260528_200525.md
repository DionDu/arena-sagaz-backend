
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-28 17:41 |
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
| Modelo | BoxNet_v4_VH_V11_12canais |
| Input shape | (4, 3, 12) |
| Parâmetros treináveis | 5,148,576 |
| Classes | 31 |
| Loss | KLD(jogada) + 0.30*MSE(valor) |
| LAMBDA_VALUE (peso value head) | 0.3 |
| Saidas | jogada (31 softmax) + valor (1 tanh) |
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
| value_flatten          | Flatten            | (None, 3072)      | 0         | reshape_1                                     | True        |
| dropout_2              | Dropout            | (None, 256)       | 0         | dense_3                                       | True        |
| value_dense64          | Dense              | (None, 64)        | 196,672   | value_flatten                                 | True        |
| jogada                 | Dense              | (None, 31)        | 7,967     | dropout_2                                     | True        |
| valor                  | Dense              | (None, 1)         | 65        | value_dense64                                 | True        |


---


## 3. Treinamento

*(logs de epoca omitidos do relatorio — ver notebook)*

| Metrica | Valor |
|---------|-------|
| Epocas treinadas | 80 |
| Loss total final — treino | 0.2855 |
| Loss total final — val | 0.2928 |
| KLD policy — treino | 0.0130 |
| KLD policy — val | 0.0197 |
| Top-1 policy — treino | 0.5415 |
| Top-1 policy — val | 0.5273 |
| MAE valor — treino | 0.8529 |
| MAE valor — val | 0.8537 |
| MSE valor — treino | 0.9085 |
| MSE valor — val | 0.9102 |
| **Melhor val_oma** | **0.9830** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 2,396,421 |     0.0076 |  0.5300 |  0.7094 |  0.7734 |
| Validação  | 513,520   |     0.0201 |  0.5212 |  0.6992 |  0.7655 |
| Teste      | 513,519   |     0.0198 |  0.5223 |  0.7002 |  0.7657 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.88 pp |
| Gap KLD (Val − Treino) | +0.0125 |
| **OMA global** | **98.3%** |
| Média jogadas Minimax-equiv. | 7.8 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 22.7%   | 35.6%   | 44.7%   | 97.2%  |
| 1a Metade (12-17)   | 102704 | 62.7%   | 84.4%   | 91.8%   | 96.8%  |
| 2a Metade (18-23)   | 102704 | 70.6%   | 89.1%   | 93.8%   | 99.9%  |
| Fase Quente (24-28) |  85586 | 67.1%   | 93.4%   | 98.3%   | 100.0% |
| Final (29-31)       |  34234 | 91.1%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.5223 |
| Macro avg | 0.5394 | 0.7156 | 0.5728 |
| Weighted avg | 0.6716 | 0.5223 | 0.4787 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_7_2    |      0.5684 |   0.9058 |     0.6985 |  9309.0000 | False   |
| H_4_3    |      0.6256 |   0.7349 |     0.6759 | 11337.0000 | False   |
| H_2_5    |      0.6105 |   0.7568 |     0.6759 | 12834.0000 | False   |
| V_1_6    |      0.6275 |   0.7152 |     0.6685 | 10766.0000 | True    |
| H_6_3    |      0.5726 |   0.7846 |     0.6621 |  9273.0000 | False   |
| H_2_1    |      0.6409 |   0.6832 |     0.6613 | 13594.0000 | False   |
| H_4_5    |      0.5450 |   0.7781 |     0.6410 | 11384.0000 | False   |
| V_3_2    |      0.5357 |   0.7641 |     0.6299 | 13944.0000 | False   |
| H_6_5    |      0.4867 |   0.8735 |     0.6251 |  9539.0000 | False   |
| H_8_1    |      0.4654 |   0.9296 |     0.6203 |  5924.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_8_5    |      0.3539 |   0.9934 |     0.5219 |   5490.0000 | True    |
| V_5_0    |      0.4163 |   0.6972 |     0.5213 |  11360.0000 | True    |
| H_0_3    |      0.7127 |   0.2895 |     0.4117 |  43216.0000 | True    |
| H_8_3    |      0.2563 |   0.9714 |     0.4056 |   6632.0000 | True    |
| H_0_1    |      0.9885 |   0.1154 |     0.2067 | 131346.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 327272 | 43.5%   | 59.9%   | 97.7% |
| 1 cadeia   | 158652 | 68.8%   | 89.3%   | 99.3% |
| 2 cadeias  |  27032 | 61.1%   | 80.3%   | 99.6% |
| ≥3 cadeias |    563 | 44.0%   | 57.4%   | 98.8% |


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
| aresta_topo                 | 488156 | 54.7%   | 72.9%   | 79.6%   | 98.2%  |
| aresta_base                 | 488342 | 54.6%   | 72.8%   | 79.3%   | 98.2%  |
| aresta_esquerda             | 488205 | 54.7%   | 73.2%   | 79.8%   | 98.2%  |
| aresta_direita              | 488350 | 54.4%   | 72.8%   | 79.4%   | 98.2%  |
| caixa_fechada               | 309017 | 68.5%   | 88.9%   | 94.1%   | 99.0%  |
| eh_grau3                    | 235646 | 85.0%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 440609 | 55.8%   | 75.3%   | 82.2%   | 98.0%  |
| em_cadeia_curta             | 179218 | 62.5%   | 84.5%   | 90.5%   | 97.6%  |
| em_cadeia_longa             | 186247 | 67.6%   | 87.9%   | 93.8%   | 99.4%  |
| em_loop                     |  15195 | 66.8%   | 82.0%   | 96.5%   | 99.9%  |
| em_cadeia_aberta_uma_ponta  |  97007 | 79.3%   | 100.0%  | 100.0%  | 100.0% |
| paridade_cadeia_longa_impar | 159215 | 68.7%   | 89.1%   | 94.8%   | 99.3%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 8660 de 513519 (1.7%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 49.0%          |      14.1000 |
| eh_grau2                    | 85.8%       | 99.8%          |      14.0000 |
| aresta_base                 | 95.1%       | 99.6%          |       4.5000 |
| aresta_topo                 | 95.1%       | 99.4%          |       4.4000 |
| aresta_esquerda             | 95.1%       | 99.5%          |       4.4000 |
| aresta_direita              | 95.1%       | 99.4%          |       4.3000 |
| em_loop                     | 3.0%        | 0.1%           |      -2.8000 |
| em_cadeia_aberta_uma_ponta  | 18.9%       | 0.4%           |     -18.5000 |
| paridade_cadeia_longa_impar | 31.0%       | 12.3%          |     -18.7000 |
| em_cadeia_longa             | 36.3%       | 13.6%          |     -22.7000 |
| caixa_fechada               | 60.2%       | 34.7%          |     -25.5000 |
| eh_grau3                    | 45.9%       | 0.5%           |     -45.4000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 188291 | 22.7%   | 35.6%   | 44.7%   | 97.2%  |
| 1a Metade (12-17)   | 102704 | 62.7%   | 84.4%   | 91.8%   | 96.8%  |
| 2a Metade (18-23)   | 102704 | 70.6%   | 89.1%   | 93.8%   | 99.9%  |
| Fase Quente (24-28) |  85586 | 67.1%   | 93.4%   | 98.3%   | 100.0% |
| Final (29-31)       |  34234 | 91.1%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valuehead_v2_3p4M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_valuehead_v2_3p4M.tflite` |
| Tamanho | 19337.6 KB |
| Quantizacao | Nenhuma (float32) |


---

