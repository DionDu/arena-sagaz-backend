
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-29 18:26 |
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
| Parâmetros treináveis | 3,571,743 |
| Classes | 31 |
| Loss | KL Divergence |
| Optimizer | Adam (lr=1e-3) |
| L2 regularização | 0.0 |
| Monitor de época | val_oma (max) |
| Batch size | 2048 |
| EarlyStopping patience | 20 |
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
| flatten                | Flatten            | (None, 3072)      | 0         | activation_10                                 | True        |
| dense                  | Dense              | (None, 256)       | 786,432   | flatten                                       | True        |
| batch_normalization_13 | BatchNormalization | (None, 256)       | 1,024     | dense                                         | True        |
| activation_11          | Activation         | (None, 256)       | 0         | batch_normalization_13                        | True        |
| dropout                | Dropout            | (None, 256)       | 0         | activation_11                                 | True        |
| dense_1                | Dense              | (None, 256)       | 65,792    | dropout                                       | True        |
| dropout_1              | Dropout            | (None, 256)       | 0         | dense_1                                       | True        |
| jogada                 | Dense              | (None, 31)        | 7,967     | dropout_1                                     | True        |


---


## 3. Treinamento

*(logs de epoca omitidos do relatorio — ver notebook)*

| Metrica | Valor |
|---------|-------|
| Epocas treinadas | 109 |
| KLD final — treino | 0.0260 |
| KLD final — val | 0.0255 |
| Top-1 final — treino | 0.5512 |
| Top-1 final — val | 0.5434 |
| **Melhor val_oma** | **0.9842** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,837,600 |     0.0175 |  0.5451 |  0.7247 |  0.7920 |
| Validação  | 1,250,915 |     0.0257 |  0.5394 |  0.7193 |  0.7876 |
| Teste      | 1,250,915 |     0.0257 |  0.5391 |  0.7188 |  0.7874 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.57 pp |
| Gap KLD (Val − Treino) | +0.0082 |
| **OMA global** | **98.4%** |
| Média jogadas Minimax-equiv. | 6.3 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 31.0%   | 44.2%   | 53.3%   | 97.4%  |
| 1a Metade (12-17)   | 402638 | 63.6%   | 84.9%   | 92.4%   | 98.3%  |
| 2a Metade (18-23)   | 242595 | 72.3%   | 92.5%   | 95.9%   | 100.0% |
| Fase Quente (24-28) |  91075 | 68.2%   | 94.9%   | 98.7%   | 100.0% |
| Final (29-31)       |  34248 | 93.1%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.5391 |
| Macro avg | 0.5506 | 0.7163 | 0.5812 |
| Weighted avg | 0.6681 | 0.5391 | 0.4908 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_2_5    |      0.6030 |   0.7612 |     0.6729 | 34532.0000 | False   |
| V_1_4    |      0.6350 |   0.6846 |     0.6589 | 43740.0000 | False   |
| H_4_3    |      0.5721 |   0.7735 |     0.6577 | 28789.0000 | False   |
| V_3_2    |      0.5966 |   0.7260 |     0.6550 | 33528.0000 | False   |
| H_6_1    |      0.5277 |   0.8620 |     0.6547 | 26201.0000 | False   |
| V_1_6    |      0.6946 |   0.6172 |     0.6536 | 27506.0000 | True    |
| H_2_3    |      0.6438 |   0.6548 |     0.6493 | 33913.0000 | False   |
| H_2_1    |      0.5893 |   0.7212 |     0.6486 | 36673.0000 | False   |
| V_1_2    |      0.6366 |   0.6483 |     0.6424 | 49272.0000 | False   |
| V_7_6    |      0.5677 |   0.7294 |     0.6385 | 19129.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_8_5    |      0.3509 |   0.9900 |     0.5181 |  13696.0000 | True    |
| H_8_3    |      0.3554 |   0.9438 |     0.5163 |  16727.0000 | True    |
| H_0_5    |      0.7331 |   0.3435 |     0.4678 |  72655.0000 | True    |
| H_0_3    |      0.7989 |   0.2385 |     0.3673 | 114985.0000 | True    |
| H_0_1    |      0.9892 |   0.0992 |     0.1803 | 264161.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 805352 | 46.8%   | 62.8%   | 97.9% |
| 1 cadeia   | 368774 | 67.3%   | 88.9%   | 99.4% |
| 2 cadeias  |  75065 | 64.9%   | 85.4%   | 99.7% |
| ≥3 cadeias |   1724 | 47.3%   | 69.1%   | 99.2% |


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
| aresta_topo                 | 1221473 | 55.1%   | 73.4%   | 80.2%   | 98.4%  |
| aresta_base                 | 1221428 | 55.1%   | 73.4%   | 80.2%   | 98.4%  |
| aresta_esquerda             | 1221647 | 55.1%   | 73.4%   | 80.3%   | 98.4%  |
| aresta_direita              | 1221870 | 55.1%   | 73.3%   | 80.2%   | 98.4%  |
| caixa_fechada               |  706033 | 66.6%   | 87.2%   | 92.8%   | 99.1%  |
| eh_grau3                    |  539361 | 87.5%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 1170298 | 55.5%   | 74.3%   | 81.4%   | 98.3%  |
| em_cadeia_curta             |  562183 | 61.4%   | 82.5%   | 89.4%   | 98.4%  |
| em_cadeia_longa             |  445563 | 66.8%   | 88.2%   | 94.1%   | 99.5%  |
| em_loop                     |   20882 | 70.4%   | 91.3%   | 97.2%   | 100.0% |
| em_cadeia_aberta_uma_ponta  |  159608 | 79.8%   | 100.0%  | 100.0%  | 100.0% |
| paridade_cadeia_longa_impar |  370498 | 67.2%   | 88.8%   | 94.5%   | 99.4%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 19438 de 1250915 (1.6%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 99.9%          |       6.3000 |
| em_cadeia_curta             | 44.9%       | 47.6%          |       2.7000 |
| aresta_base                 | 97.6%       | 99.5%          |       1.9000 |
| aresta_topo                 | 97.6%       | 99.4%          |       1.8000 |
| aresta_esquerda             | 97.7%       | 99.4%          |       1.8000 |
| aresta_direita              | 97.7%       | 99.4%          |       1.7000 |
| em_loop                     | 1.7%        | 0.0%           |      -1.6000 |
| em_cadeia_aberta_uma_ponta  | 12.8%       | 0.3%           |     -12.5000 |
| paridade_cadeia_longa_impar | 29.6%       | 10.6%          |     -19.0000 |
| caixa_fechada               | 56.4%       | 33.0%          |     -23.4000 |
| em_cadeia_longa             | 35.6%       | 11.6%          |     -24.0000 |
| eh_grau3                    | 43.1%       | 0.3%           |     -42.8000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 31.0%   | 44.2%   | 53.3%   | 97.4%  |
| 1a Metade (12-17)   | 402638 | 63.6%   | 84.9%   | 92.4%   | 98.3%  |
| 2a Metade (18-23)   | 242595 | 72.3%   | 92.5%   | 95.9%   | 100.0% |
| Fase Quente (24-28) |  91075 | 68.2%   | 94.9%   | 98.7%   | 100.0% |
| Final (29-31)       |  34248 | 93.1%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_dense256_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_dense256_8p3M.tflite` |
| Tamanho | 13935.6 KB |
| Quantizacao | Nenhuma (float32) |


---

