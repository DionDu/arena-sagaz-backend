
# Relatorio de Treinamento — BoxNet v4 (V11)

| Parametro | Valor |
|-----------|-------|
| Data | 2026-05-29 12:02 |
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
| Parâmetros treináveis | 4,424,735 |
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
| flatten                | Flatten            | (None, 3072)      | 0         | activation_10                                 | True        |
| dense                  | Dense              | (None, 512)       | 1,572,864 | flatten                                       | True        |
| batch_normalization_13 | BatchNormalization | (None, 512)       | 2,048     | dense                                         | True        |
| activation_11          | Activation         | (None, 512)       | 0         | batch_normalization_13                        | True        |
| dropout                | Dropout            | (None, 512)       | 0         | activation_11                                 | True        |
| dense_1                | Dense              | (None, 256)       | 131,328   | dropout                                       | True        |
| dropout_1              | Dropout            | (None, 256)       | 0         | dense_1                                       | True        |
| jogada                 | Dense              | (None, 31)        | 7,967     | dropout_1                                     | True        |


---


## 3. Treinamento

*(logs de epoca omitidos do relatorio — ver notebook)*

| Metrica | Valor |
|---------|-------|
| Epocas treinadas | 116 |
| KLD final — treino | 0.0225 |
| KLD final — val | 0.0226 |
| Top-1 final — treino | 0.5596 |
| Top-1 final — val | 0.5519 |
| **Melhor val_oma** | **0.9817** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,837,600 |     0.0129 |  0.5593 |  0.7458 |  0.8137 |
| Validação  | 1,250,915 |     0.0225 |  0.5533 |  0.7395 |  0.8092 |
| Teste      | 1,250,915 |     0.0225 |  0.5531 |  0.7392 |  0.8084 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +0.60 pp |
| Gap KLD (Val − Treino) | +0.0096 |
| **OMA global** | **98.2%** |
| Média jogadas Minimax-equiv. | 6.3 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 33.2%   | 48.6%   | 58.4%   | 97.1%  |
| 1a Metade (12-17)   | 402638 | 64.4%   | 85.5%   | 92.6%   | 98.1%  |
| 2a Metade (18-23)   | 242595 | 73.8%   | 93.1%   | 96.3%   | 99.9%  |
| Fase Quente (24-28) |  91075 | 69.0%   | 95.6%   | 98.9%   | 100.0% |
| Final (29-31)       |  34248 | 91.2%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.5531 |
| Macro avg | 0.5568 | 0.7233 | 0.5911 |
| Weighted avg | 0.6688 | 0.5531 | 0.5145 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| V_7_4    |      0.5495 |   0.9265 |     0.6898 | 23019.0000 | False   |
| V_5_4    |      0.5912 |   0.7894 |     0.6760 | 27480.0000 | False   |
| H_2_5    |      0.6097 |   0.7454 |     0.6707 | 34532.0000 | False   |
| H_6_1    |      0.5379 |   0.8853 |     0.6692 | 26201.0000 | False   |
| H_6_5    |      0.5279 |   0.9043 |     0.6666 | 24493.0000 | False   |
| V_1_4    |      0.7045 |   0.6279 |     0.6640 | 43740.0000 | False   |
| H_2_1    |      0.5924 |   0.7388 |     0.6575 | 36673.0000 | False   |
| V_7_2    |      0.5102 |   0.9009 |     0.6514 | 24104.0000 | False   |
| H_4_3    |      0.5470 |   0.7928 |     0.6474 | 28789.0000 | False   |
| H_4_5    |      0.5367 |   0.8145 |     0.6470 | 30038.0000 | False   |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_8_3    |      0.3659 |   0.9570 |     0.5294 |  16727.0000 | True    |
| H_8_1    |      0.3654 |   0.9480 |     0.5274 |  14832.0000 | True    |
| H_0_5    |      0.7298 |   0.3191 |     0.4441 |  72655.0000 | True    |
| H_0_3    |      0.7376 |   0.2487 |     0.3720 | 114985.0000 | True    |
| H_0_1    |      0.9852 |   0.1586 |     0.2733 | 264161.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 805352 | 48.2%   | 65.6%   | 97.6% |
| 1 cadeia   | 368774 | 68.7%   | 89.7%   | 99.3% |
| 2 cadeias  |  75065 | 66.4%   | 85.9%   | 99.7% |
| ≥3 cadeias |   1724 | 50.1%   | 68.4%   | 99.3% |


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
| aresta_topo                 | 1221473 | 56.4%   | 75.2%   | 82.2%   | 98.2%  |
| aresta_base                 | 1221428 | 56.4%   | 75.2%   | 82.1%   | 98.2%  |
| aresta_esquerda             | 1221647 | 56.5%   | 75.4%   | 82.3%   | 98.2%  |
| aresta_direita              | 1221870 | 56.4%   | 75.2%   | 82.2%   | 98.2%  |
| caixa_fechada               |  706033 | 67.6%   | 88.0%   | 93.3%   | 99.0%  |
| eh_grau3                    |  539361 | 87.6%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 1170298 | 56.9%   | 76.2%   | 83.3%   | 98.1%  |
| em_cadeia_curta             |  562183 | 62.2%   | 83.2%   | 90.0%   | 98.1%  |
| em_cadeia_longa             |  445563 | 68.2%   | 88.9%   | 94.3%   | 99.4%  |
| em_loop                     |   20882 | 68.7%   | 88.6%   | 97.6%   | 99.9%  |
| em_cadeia_aberta_uma_ponta  |  159608 | 80.5%   | 100.0%  | 100.0%  | 100.0% |
| paridade_cadeia_longa_impar |  370498 | 68.6%   | 89.6%   | 94.7%   | 99.3%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 22043 de 1250915 (1.8%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 99.8%          |       6.3000 |
| em_cadeia_curta             | 44.9%       | 47.2%          |       2.3000 |
| aresta_topo                 | 97.6%       | 99.5%          |       1.9000 |
| aresta_base                 | 97.6%       | 99.5%          |       1.9000 |
| aresta_direita              | 97.7%       | 99.5%          |       1.8000 |
| aresta_esquerda             | 97.7%       | 99.4%          |       1.7000 |
| em_loop                     | 1.7%        | 0.1%           |      -1.6000 |
| em_cadeia_aberta_uma_ponta  | 12.8%       | 0.2%           |     -12.6000 |
| paridade_cadeia_longa_impar | 29.6%       | 11.0%          |     -18.6000 |
| em_cadeia_longa             | 35.6%       | 12.0%          |     -23.6000 |
| caixa_fechada               | 56.4%       | 32.4%          |     -24.0000 |
| eh_grau3                    | 43.1%       | 0.3%           |     -42.8000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 480359 | 33.2%   | 48.6%   | 58.4%   | 97.1%  |
| 1a Metade (12-17)   | 402638 | 64.4%   | 85.5%   | 92.6%   | 98.1%  |
| 2a Metade (18-23)   | 242595 | 73.8%   | 93.1%   | 96.3%   | 99.9%  |
| Fase Quente (24-28) |  91075 | 69.0%   | 95.6%   | 98.9%   | 100.0% |
| Final (29-31)       |  34248 | 91.2%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_addaug_noattn_8p3M.tflite` |
| Tamanho | 17264.6 KB |
| Quantizacao | Nenhuma (float32) |


---

