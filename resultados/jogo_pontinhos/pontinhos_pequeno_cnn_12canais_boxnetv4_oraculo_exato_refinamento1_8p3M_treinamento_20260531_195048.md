
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-31 15:13 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_oraculo_exato` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |
| PESO_REFINAMENTO | 20.0x |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 107 |
| Total de amostras | 8,364,778 |
| Treino | 5,855,344 |
| Validacao | 1,254,717 |
| Teste | 1,254,717 |

**Distribuicao por fase (%)**

| Fase                |   Treino (%) |   Val (%) |   Teste (%) |
|:--------------------|-------------:|----------:|------------:|
| Abertura (0-11)     |         38.5 |      38.5 |        38.5 |
| 1a Metade (12-17)   |         32.2 |      32.2 |        32.2 |
| 2a Metade (18-23)   |         19.3 |      19.3 |        19.3 |
| Fase Quente (24-28) |          7.3 |       7.3 |         7.3 |
| Final (29-31)       |          2.7 |       2.7 |         2.7 |


---


## 2. Arquitetura

| Parâmetro | Valor |
|-----------|-------|
| Modelo | BoxNet_v4_V11_12canais |
| Input shape | (4, 3, 12) |
| Parâmetros treináveis | 4,951,839 |
| Classes | 31 |
| Loss | KL Divergence |
| Optimizer | Adam (lr=2e-3) |
| L2 regularização | 0.0 |
| Monitor de época | val_oma (max) |
| Batch size | 4096 |
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
| Epocas treinadas | 61 |
| KLD final — treino | 0.0696 |
| KLD final — val | 0.0893 |
| Top-1 final — treino | 0.6451 |
| Top-1 final — val | 0.6308 |
| **Melhor val_oma** | **0.9746** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,855,344 |     0.0624 |  0.6375 |  0.8344 |  0.8972 |
| Validação  | 1,254,717 |     0.0902 |  0.6261 |  0.8242 |  0.8897 |
| Teste      | 1,254,717 |     0.0902 |  0.6268 |  0.8247 |  0.8900 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +1.14 pp |
| Gap KLD (Val − Treino) | +0.0278 |
| **OMA global** | **97.5%** |
| Média jogadas Minimax-equiv. | 3.4 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 482977 | 49.9%   | 69.3%   | 78.8%   | 95.2%  |
| 1a Metade (12-17)   | 403783 | 67.3%   | 87.8%   | 93.9%   | 97.8%  |
| 2a Metade (18-23)   | 242633 | 74.1%   | 92.6%   | 96.0%   | 100.0% |
| Fase Quente (24-28) |  91075 | 68.3%   | 94.8%   | 98.8%   | 100.0% |
| Final (29-31)       |  34249 | 92.6%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.6268 |
| Macro avg | 0.6433 | 0.7196 | 0.6424 |
| Weighted avg | 0.6985 | 0.6268 | 0.6042 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_7_4    |      0.6441 |   0.9131 |     0.7553 | 23019.0000 | False   |
| H_6_1    |      0.6757 |   0.8310 |     0.7453 | 27490.0000 | False   |
| H_6_5    |      0.6456 |   0.8565 |     0.7363 | 25701.0000 | False   |
| H_8_1    |      0.5950 |   0.9272 |     0.7248 | 15383.0000 | True    |
| V_7_0    |      0.6797 |   0.7690 |     0.7216 | 23234.0000 | True    |
| H_4_1    |      0.6759 |   0.7309 |     0.7024 | 44460.0000 | False   |
| H_2_5    |      0.7214 |   0.6769 |     0.6984 | 39020.0000 | False   |
| H_4_3    |      0.5861 |   0.8634 |     0.6983 | 54536.0000 | False   |
| V_7_2    |      0.5662 |   0.8862 |     0.6910 | 24495.0000 | False   |
| H_4_5    |      0.5834 |   0.8210 |     0.6821 | 38274.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| V_7_6    |      0.4249 |   0.9165 |     0.5806 |  20083.0000 | True    |
| H_8_5    |      0.3978 |   0.9862 |     0.5669 |  14349.0000 | True    |
| H_0_3    |      0.8681 |   0.3326 |     0.4810 |  88911.0000 | True    |
| H_0_5    |      0.8509 |   0.3133 |     0.4579 |  66215.0000 | True    |
| H_0_1    |      0.9797 |   0.1789 |     0.3025 | 130589.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 808444 | 59.3%   | 79.1%   | 96.6% |
| 1 cadeia   | 369558 | 69.5%   | 89.6%   | 99.0% |
| 2 cadeias  |  74997 | 65.4%   | 84.0%   | 99.6% |
| ≥3 cadeias |   1718 | 47.8%   | 66.6%   | 99.9% |


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          93.9 |          93.9 |              93.9 |             94.0 |            10.9 |       18.9 |       87.4 |              24.6 |               3.3 |       0.0 |                          0.6 |                           3.2 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            71.3 |       42.4 |      100.0 |              70.5 |              46.6 |       0.6 |                          7.0 |                          37.9 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.6 |       68.8 |      100.0 |              54.3 |              79.1 |       4.5 |                         24.4 |                          62.7 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       83.9 |       99.9 |              31.8 |              55.3 |       8.2 |                         63.0 |                          55.3 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       99.8 |       42.4 |               0.0 |               0.0 |       0.0 |                         34.9 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |       N | Top-1   | Top-3   | Top-5   | OMA   |
|:----------------------------|--------:|:--------|:--------|:--------|:------|
| aresta_topo                 | 1225188 | 63.6%   | 83.5%   | 89.9%   | 97.4% |
| aresta_base                 | 1225164 | 63.6%   | 83.5%   | 89.8%   | 97.4% |
| aresta_esquerda             | 1225371 | 63.7%   | 83.6%   | 89.9%   | 97.4% |
| aresta_direita              | 1225545 | 63.7%   | 83.5%   | 90.0%   | 97.4% |
| caixa_fechada               |  707791 | 69.9%   | 89.9%   | 94.8%   | 98.9% |
| eh_grau3                    |  539656 | 88.1%   | 100.0%  | 100.0%  | 99.9% |
| eh_grau2                    | 1173813 | 63.8%   | 84.2%   | 90.6%   | 97.3% |
| em_cadeia_curta             |  564103 | 67.0%   | 87.5%   | 93.0%   | 97.5% |
| em_cadeia_longa             |  446273 | 68.8%   | 88.6%   | 94.1%   | 99.1% |
| em_loop                     |   20867 | 70.4%   | 94.8%   | 97.7%   | 99.8% |
| em_cadeia_aberta_uma_ponta  |  159513 | 82.2%   | 100.0%  | 100.0%  | 99.8% |
| paridade_cadeia_longa_impar |  371276 | 69.4%   | 89.5%   | 94.7%   | 99.0% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 31898 de 1254717 (2.5%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 98.6%          |       5.1000 |
| aresta_direita              | 97.7%       | 99.0%          |       1.3000 |
| aresta_esquerda             | 97.7%       | 98.9%          |       1.3000 |
| aresta_base                 | 97.6%       | 98.5%          |       0.9000 |
| aresta_topo                 | 97.6%       | 98.5%          |       0.8000 |
| em_cadeia_curta             | 45.0%       | 43.8%          |      -1.2000 |
| em_loop                     | 1.7%        | 0.1%           |      -1.6000 |
| em_cadeia_aberta_uma_ponta  | 12.7%       | 0.8%           |     -11.9000 |
| paridade_cadeia_longa_impar | 29.6%       | 11.8%          |     -17.8000 |
| em_cadeia_longa             | 35.6%       | 12.6%          |     -23.0000 |
| caixa_fechada               | 56.4%       | 24.8%          |     -31.6000 |
| eh_grau3                    | 43.0%       | 0.8%           |     -42.2000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 482977 | 49.9%   | 69.3%   | 78.8%   | 95.2%  |
| 1a Metade (12-17)   | 403783 | 67.3%   | 87.8%   | 93.9%   | 97.8%  |
| 2a Metade (18-23)   | 242633 | 74.1%   | 92.6%   | 96.0%   | 100.0% |
| Fase Quente (24-28) |  91075 | 68.3%   | 94.8%   | 98.8%   | 100.0% |
| Final (29-31)       |  34249 | 92.6%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento1_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento1_8p3M.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

