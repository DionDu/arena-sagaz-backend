
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-28 18:01 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_minimax_11_adaptativo` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 420 |
| Total de amostras | 8,339,430 |
| Treino | 5,837,600 |
| Validacao | 1,250,915 |
| Teste | 1,250,915 |

**Distribuicao por fase (%)**

| Fase                |   Treino (%) |   Val (%) |   Teste (%) |
|:--------------------|-------------:|----------:|------------:|
| Abertura (0-11)     |         38.4 |      38.4 |        38.4 |
| 1a Metade (12-17)   |         32.2 |      32.2 |        32.2 |
| 2a Metade (18-23)   |         19.4 |      19.4 |        19.4 |
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
| Epocas treinadas | 102 |
| KLD final — treino | 0.0172 |
| KLD final — val | 0.0157 |
| Top-1 final — treino | 0.5582 |
| Top-1 final — val | 0.5523 |
| **Melhor val_oma** | **0.9877** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,837,600 |     0.0089 |  0.5538 |  0.7443 |  0.8124 |
| Validação  | 1,250,915 |     0.0158 |  0.5490 |  0.7392 |  0.8084 |
| Teste      | 1,250,915 |     0.0158 |  0.5487 |  0.7392 |  0.8083 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.48 pp |
| Gap KLD (Val − Treino) | +0.0069 |
| **OMA global** | **98.8%** |
| Média jogadas Minimax-equiv. | 6.3 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 33.0%   | 48.3%   | 58.1%   | 97.9%  |
| 1a Metade (12-17)   | 402638 | 64.0%   | 85.5%   | 92.7%   | 98.8%  |
| 2a Metade (18-23)   | 242595 | 72.5%   | 93.4%   | 96.5%   | 100.0% |
| Fase Quente (24-28) |  91075 | 69.2%   | 96.4%   | 99.2%   | 100.0% |
| Final (29-31)       |  34248 | 92.1%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.5487 |
| Macro avg | 0.5591 | 0.7200 | 0.5907 |
| Weighted avg | 0.6710 | 0.5487 | 0.5087 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_4_3    |      0.6835 |   0.7903 |     0.7330 | 28789.0000 | False   |
| V_7_2    |      0.5826 |   0.8988 |     0.7069 | 24104.0000 | False   |
| H_6_1    |      0.6061 |   0.8359 |     0.7027 | 26201.0000 | False   |
| H_2_5    |      0.6813 |   0.7195 |     0.6999 | 34532.0000 | False   |
| H_2_1    |      0.6913 |   0.7079 |     0.6995 | 36673.0000 | False   |
| V_1_2    |      0.6978 |   0.6539 |     0.6752 | 49272.0000 | False   |
| V_1_4    |      0.7387 |   0.6126 |     0.6698 | 43740.0000 | False   |
| H_4_5    |      0.5590 |   0.8128 |     0.6624 | 30038.0000 | False   |
| V_5_4    |      0.5695 |   0.7638 |     0.6525 | 27480.0000 | False   |
| H_6_5    |      0.5034 |   0.9067 |     0.6474 | 24493.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_8_1    |      0.3248 |   0.9500 |     0.4841 |  14832.0000 | True    |
| H_8_5    |      0.3147 |   0.9937 |     0.4780 |  13696.0000 | True    |
| H_8_3    |      0.3131 |   0.9720 |     0.4737 |  16727.0000 | True    |
| H_0_3    |      0.7403 |   0.2579 |     0.3825 | 114985.0000 | True    |
| H_0_1    |      0.9908 |   0.1198 |     0.2137 | 264161.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 805352 | 48.0%   | 65.5%   | 98.3% |
| 1 cadeia   | 368774 | 67.9%   | 89.8%   | 99.6% |
| 2 cadeias  |  75065 | 65.3%   | 86.3%   | 99.9% |
| ≥3 cadeias |   1724 | 46.1%   | 67.4%   | 99.4% |


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          93.9 |          93.9 |              93.9 |             94.0 |            10.8 |       19.0 |       87.3 |              24.5 |               3.2 |       0.0 |                          0.6 |                           3.2 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            71.3 |       42.4 |      100.0 |              70.5 |              46.6 |       0.6 |                          7.0 |                          37.9 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.6 |       68.7 |      100.0 |              54.3 |              79.2 |       4.4 |                         24.4 |                          62.8 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       83.9 |       99.9 |              31.8 |              55.2 |       8.2 |                         63.0 |                          55.2 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       99.8 |       42.8 |               0.0 |               0.0 |       0.0 |                         35.2 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |       N | Top-1   | Top-3   | Top-5   | OMA    |
|:----------------------------|--------:|:--------|:--------|:--------|:-------|
| aresta_topo                 | 1221473 | 56.0%   | 75.3%   | 82.2%   | 98.8%  |
| aresta_base                 | 1221428 | 56.0%   | 75.3%   | 82.2%   | 98.8%  |
| aresta_esquerda             | 1221647 | 56.1%   | 75.4%   | 82.4%   | 98.8%  |
| aresta_direita              | 1221870 | 55.9%   | 75.2%   | 82.2%   | 98.8%  |
| caixa_fechada               |  706033 | 67.0%   | 88.3%   | 93.6%   | 99.4%  |
| eh_grau3                    |  539361 | 87.5%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 1170298 | 56.4%   | 76.3%   | 83.4%   | 98.7%  |
| em_cadeia_curta             |  562183 | 61.8%   | 83.4%   | 90.1%   | 98.8%  |
| em_cadeia_longa             |  445563 | 67.3%   | 89.1%   | 94.5%   | 99.7%  |
| em_loop                     |   20882 | 67.6%   | 91.5%   | 97.4%   | 100.0% |
| em_cadeia_aberta_uma_ponta  |  159608 | 79.8%   | 100.0%  | 100.0%  | 100.0% |
| paridade_cadeia_longa_impar |  370498 | 67.8%   | 89.7%   | 94.9%   | 99.6%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 15126 de 1250915 (1.2%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 99.8%          |       6.3000 |
| aresta_base                 | 97.6%       | 99.4%          |       1.8000 |
| aresta_esquerda             | 97.7%       | 99.3%          |       1.7000 |
| aresta_topo                 | 97.6%       | 99.3%          |       1.7000 |
| aresta_direita              | 97.7%       | 99.4%          |       1.7000 |
| em_cadeia_curta             | 44.9%       | 45.1%          |       0.1000 |
| em_loop                     | 1.7%        | 0.0%           |      -1.6000 |
| em_cadeia_aberta_uma_ponta  | 12.8%       | 0.1%           |     -12.6000 |
| paridade_cadeia_longa_impar | 29.6%       | 9.0%           |     -20.6000 |
| em_cadeia_longa             | 35.6%       | 9.7%           |     -25.9000 |
| caixa_fechada               | 56.4%       | 29.9%          |     -26.5000 |
| eh_grau3                    | 43.1%       | 0.2%           |     -42.9000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 33.0%   | 48.3%   | 58.1%   | 97.9%  |
| 1a Metade (12-17)   | 402638 | 64.0%   | 85.5%   | 92.7%   | 98.8%  |
| 2a Metade (18-23)   | 242595 | 72.5%   | 93.4%   | 96.5%   | 100.0% |
| Fase Quente (24-28) |  91075 | 69.2%   | 96.4%   | 99.2%   | 100.0% |
| Final (29-31)       |  34248 | 92.1%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_todos_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_todos_8p3M.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

