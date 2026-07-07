
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-30 18:18 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_oraculo_exato` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 106 |
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
| Epocas treinadas | 48 |
| KLD final — treino | 0.0651 |
| KLD final — val | 0.0828 |
| Top-1 final — treino | 0.6457 |
| Top-1 final — val | 0.6294 |
| **Melhor val_oma** | **0.9782** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,837,600 |     0.0628 |  0.6378 |  0.8406 |  0.9023 |
| Validação  | 1,250,915 |     0.0851 |  0.6301 |  0.8325 |  0.8963 |
| Teste      | 1,250,915 |     0.0852 |  0.6299 |  0.8329 |  0.8968 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.77 pp |
| Gap KLD (Val − Treino) | +0.0223 |
| **OMA global** | **97.8%** |
| Média jogadas Minimax-equiv. | 3.4 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 50.0%   | 70.5%   | 79.7%   | 95.8%  |
| 1a Metade (12-17)   | 402638 | 68.0%   | 88.7%   | 94.6%   | 98.2%  |
| 2a Metade (18-23)   | 242595 | 74.7%   | 93.2%   | 96.5%   | 100.0% |
| Fase Quente (24-28) |  91075 | 67.2%   | 93.9%   | 98.5%   | 100.0% |
| Final (29-31)       |  34248 | 92.2%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.6299 |
| Macro avg | 0.6488 | 0.7165 | 0.6449 |
| Weighted avg | 0.7003 | 0.6299 | 0.6118 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_7_2    |      0.7151 |   0.8541 |     0.7784 | 24373.0000 | False   |
| H_8_1    |      0.6323 |   0.9449 |     0.7576 | 15343.0000 | True    |
| H_6_5    |      0.6563 |   0.8825 |     0.7528 | 25661.0000 | False   |
| V_7_0    |      0.6941 |   0.8023 |     0.7443 | 23192.0000 | True    |
| H_4_1    |      0.7096 |   0.7171 |     0.7133 | 44307.0000 | False   |
| V_7_4    |      0.5659 |   0.9298 |     0.7036 | 22960.0000 | False   |
| H_2_5    |      0.6560 |   0.7238 |     0.6882 | 38976.0000 | False   |
| H_4_5    |      0.5552 |   0.8661 |     0.6766 | 38242.0000 | False   |
| H_4_3    |      0.5480 |   0.8597 |     0.6693 | 54464.0000 | False   |
| V_5_2    |      0.6226 |   0.7179 |     0.6669 | 36888.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| V_1_0    |      0.8778 |   0.4452 |     0.5908 |  36578.0000 | True    |
| H_8_5    |      0.4017 |   0.9894 |     0.5714 |  14355.0000 | True    |
| H_0_3    |      0.8178 |   0.4229 |     0.5575 |  88659.0000 | True    |
| H_0_5    |      0.8825 |   0.3360 |     0.4867 |  65800.0000 | True    |
| H_0_1    |      0.9811 |   0.2119 |     0.3486 | 130315.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 805352 | 59.3%   | 79.9%   | 97.0% |
| 1 cadeia   | 368774 | 70.3%   | 90.2%   | 99.2% |
| 2 cadeias  |  75065 | 67.0%   | 85.8%   | 99.7% |
| ≥3 cadeias |   1724 | 52.6%   | 72.3%   | 99.7% |


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
| aresta_topo                 | 1221473 | 63.9%   | 84.2%   | 90.6%   | 97.8%  |
| aresta_base                 | 1221428 | 63.9%   | 84.2%   | 90.5%   | 97.8%  |
| aresta_esquerda             | 1221647 | 63.9%   | 84.3%   | 90.6%   | 97.7%  |
| aresta_direita              | 1221870 | 63.9%   | 84.3%   | 90.7%   | 97.7%  |
| caixa_fechada               |  706033 | 70.3%   | 90.4%   | 95.3%   | 99.1%  |
| eh_grau3                    |  539361 | 87.6%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 1170298 | 64.2%   | 84.9%   | 91.3%   | 97.7%  |
| em_cadeia_curta             |  562183 | 67.7%   | 88.3%   | 93.7%   | 97.9%  |
| em_cadeia_longa             |  445563 | 69.7%   | 89.3%   | 94.7%   | 99.3%  |
| em_loop                     |   20882 | 68.0%   | 90.5%   | 97.5%   | 99.8%  |
| em_cadeia_aberta_uma_ponta  |  159608 | 81.4%   | 100.0%  | 100.0%  | 99.9%  |
| paridade_cadeia_longa_impar |  370498 | 70.3%   | 90.1%   | 95.2%   | 99.2%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 27808 de 1250915 (2.2%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 98.5%          |       4.9000 |
| aresta_esquerda             | 97.7%       | 98.9%          |       1.3000 |
| aresta_direita              | 97.7%       | 98.9%          |       1.2000 |
| aresta_base                 | 97.6%       | 98.5%          |       0.8000 |
| aresta_topo                 | 97.6%       | 98.4%          |       0.8000 |
| em_cadeia_curta             | 44.9%       | 43.4%          |      -1.5000 |
| em_loop                     | 1.7%        | 0.1%           |      -1.5000 |
| em_cadeia_aberta_uma_ponta  | 12.8%       | 0.6%           |     -12.2000 |
| paridade_cadeia_longa_impar | 29.6%       | 11.1%          |     -18.6000 |
| em_cadeia_longa             | 35.6%       | 11.8%          |     -23.9000 |
| caixa_fechada               | 56.4%       | 23.6%          |     -32.8000 |
| eh_grau3                    | 43.1%       | 0.6%           |     -42.5000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 50.0%   | 70.5%   | 79.7%   | 95.8%  |
| 1a Metade (12-17)   | 402638 | 68.0%   | 88.7%   | 94.6%   | 98.2%  |
| 2a Metade (18-23)   | 242595 | 74.7%   | 93.2%   | 96.5%   | 100.0% |
| Fase Quente (24-28) |  91075 | 67.2%   | 93.9%   | 98.5%   | 100.0% |
| Final (29-31)       |  34248 | 92.2%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_oraculo_exato_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_oraculo_exato_8p3M.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

