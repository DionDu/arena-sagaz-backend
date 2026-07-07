
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-27 16:41 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_minimax_11_adaptativo` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 152 |
| Total de amostras | 758,640 |
| Treino | 531,047 |
| Validacao | 113,797 |
| Teste | 113,796 |

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
| Epocas treinadas | 84 |
| KLD final — treino | 0.0157 |
| KLD final — val | 0.0422 |
| Top-1 final — treino | 0.5443 |
| Top-1 final — val | 0.5270 |
| **Melhor val_oma** | **0.9564** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N       |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:--------|-----------:|--------:|--------:|--------:|
| Treino     | 531,047 |     0.0101 |  0.5116 |  0.7027 |  0.7693 |
| Validação  | 113,797 |     0.0420 |  0.4920 |  0.6776 |  0.7490 |
| Teste      | 113,796 |     0.0421 |  0.4923 |  0.6797 |  0.7498 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +1.96 pp |
| Gap KLD (Val − Treino) | +0.0319 |
| **OMA global** | **95.6%** |
| Média jogadas Minimax-equiv. | 7.9 |


### 4.2 Métricas por Fase

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 20.0%   | 33.1%   | 42.7%   | 92.7%  |
| 1a Metade (12-17)   | 22759 | 57.6%   | 79.8%   | 88.8%   | 91.7%  |
| 2a Metade (18-23)   | 22759 | 68.3%   | 88.7%   | 93.1%   | 99.7%  |
| Fase Quente (24-28) | 18966 | 64.0%   | 92.8%   | 97.5%   | 100.0% |
| Final (29-31)       |  7587 | 90.9%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.4923 |
| Macro avg | 0.5126 | 0.6845 | 0.5451 |
| Weighted avg | 0.6361 | 0.4923 | 0.4514 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |   support | Borda   |
|:---------|------------:|---------:|-----------:|----------:|:--------|
| H_6_1    |      0.6995 |   0.7737 |     0.7348 | 2320.0000 | False   |
| H_6_5    |      0.6183 |   0.8519 |     0.7165 | 2154.0000 | False   |
| H_2_5    |      0.6420 |   0.7567 |     0.6946 | 2856.0000 | False   |
| H_2_1    |      0.6360 |   0.7476 |     0.6873 | 2928.0000 | False   |
| H_4_5    |      0.6442 |   0.6953 |     0.6688 | 2458.0000 | False   |
| V_1_4    |      0.7333 |   0.5958 |     0.6574 | 3748.0000 | False   |
| V_7_4    |      0.4981 |   0.9283 |     0.6483 | 1926.0000 | False   |
| H_4_1    |      0.5531 |   0.7313 |     0.6299 | 2706.0000 | False   |
| V_1_2    |      0.7443 |   0.5447 |     0.6290 | 4131.0000 | False   |
| H_2_3    |      0.6298 |   0.5995 |     0.6143 | 2809.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_1_0    |      0.3781 |   0.4619 |     0.4158 |  3048.0000 | True    |
| H_0_5    |      0.5020 |   0.2817 |     0.3609 |  5786.0000 | True    |
| H_8_5    |      0.2192 |   0.9784 |     0.3582 |  1204.0000 | True    |
| H_0_3    |      0.5468 |   0.2437 |     0.3371 |  9751.0000 | True    |
| H_0_1    |      0.9657 |   0.1146 |     0.2049 | 29205.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |     N | Top-1   | Top-3   | OMA   |
|:-----------|------:|:--------|:--------|:------|
| 0 cadeias  | 71002 | 40.0%   | 57.0%   | 94.2% |
| 1 cadeia   | 36086 | 65.6%   | 87.2%   | 98.0% |
| 2 cadeias  |  6572 | 59.2%   | 80.6%   | 98.5% |
| ≥3 cadeias |   136 | 47.8%   | 60.3%   | 97.8% |


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
| aresta_topo                 | 108215 | 51.3%   | 70.6%   | 77.5%   | 95.4% |
| aresta_base                 | 108255 | 51.3%   | 70.3%   | 77.1%   | 95.4% |
| aresta_esquerda             | 108294 | 51.6%   | 70.9%   | 77.8%   | 95.4% |
| aresta_direita              | 108308 | 51.3%   | 70.4%   | 77.1%   | 95.4% |
| caixa_fechada               |  68284 | 65.4%   | 87.0%   | 92.5%   | 97.3% |
| eh_grau3                    |  50280 | 84.4%   | 100.0%  | 100.0%  | 99.9% |
| eh_grau2                    |  97780 | 52.2%   | 72.3%   | 79.2%   | 94.9% |
| em_cadeia_curta             |  39671 | 58.0%   | 80.7%   | 87.6%   | 93.6% |
| em_cadeia_longa             |  42794 | 64.6%   | 86.1%   | 92.5%   | 98.0% |
| em_loop                     |   3599 | 64.4%   | 89.7%   | 97.2%   | 99.9% |
| em_cadeia_aberta_uma_ponta  |  21624 | 79.1%   | 100.0%  | 100.0%  | 99.8% |
| paridade_cadeia_longa_impar |  36222 | 65.6%   | 87.1%   | 93.5%   | 98.0% |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 4989 de 113796 (4.4%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| em_cadeia_curta             | 34.9%       | 51.3%          |      16.4000 |
| eh_grau2                    | 85.9%       | 99.9%          |      14.0000 |
| aresta_topo                 | 95.1%       | 99.6%          |       4.5000 |
| aresta_esquerda             | 95.2%       | 99.6%          |       4.5000 |
| aresta_base                 | 95.1%       | 99.6%          |       4.4000 |
| aresta_direita              | 95.2%       | 99.5%          |       4.3000 |
| em_loop                     | 3.2%        | 0.1%           |      -3.1000 |
| paridade_cadeia_longa_impar | 31.8%       | 14.9%          |     -17.0000 |
| em_cadeia_aberta_uma_ponta  | 19.0%       | 0.8%           |     -18.2000 |
| em_cadeia_longa             | 37.6%       | 16.9%          |     -20.7000 |
| caixa_fechada               | 60.0%       | 36.4%          |     -23.6000 |
| eh_grau3                    | 44.2%       | 0.8%           |     -43.4000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |     N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 41725 | 20.0%   | 33.1%   | 42.7%   | 92.7%  |
| 1a Metade (12-17)   | 22759 | 57.6%   | 79.8%   | 88.8%   | 91.7%  |
| 2a Metade (18-23)   | 22759 | 68.3%   | 88.7%   | 93.1%   | 99.7%  |
| Fase Quente (24-28) | 18966 | 64.0%   | 92.8%   | 97.5%   | 100.0% |
| Final (29-31)       |  7587 | 90.9%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

