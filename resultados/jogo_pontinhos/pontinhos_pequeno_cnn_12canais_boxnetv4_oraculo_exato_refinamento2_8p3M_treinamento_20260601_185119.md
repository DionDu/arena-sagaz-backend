
# Relatorio de Treinamento — BoxNet v4 (V11) — Refinamento 2

| Parametro | Valor |
|-----------|-------|
| Data | 2026-06-01 13:23 |
| Canais (12) | aresta_topo, aresta_base, aresta_esquerda, aresta_direita, caixa_fechada, eh_grau3, eh_grau2, em_cadeia_curta, em_cadeia_longa, em_loop, em_cadeia_aberta_uma_ponta, paridade_cadeia_longa_impar |
| PASTA_NPZ | `/content/drive/MyDrive/Arena Sagaz/CNN/dados/profundidade_oraculo_exato` |
| UTILIZACAO_MATRIZES | INCLUI_DUPLICADAS |
| USE_SAMPLE_WEIGHT | False |
| PESO_REFINAMENTO | 12.0x |


## 1. Dados de Treinamento

| Parametro | Valor |
|-----------|-------|
| Arquivos NPZ | 108 |
| Total de amostras | 8,389,692 |
| Treino | 5,872,784 |
| Validacao | 1,258,454 |
| Teste | 1,258,454 |

**Distribuicao por fase (%)**

| Fase                |   Treino (%) |   Val (%) |   Teste (%) |
|:--------------------|-------------:|----------:|------------:|
| Abertura (0-11)     |         38.6 |      38.6 |        38.6 |
| 1a Metade (12-17)   |         32.2 |      32.2 |        32.2 |
| 2a Metade (18-23)   |         19.3 |      19.3 |        19.3 |
| Fase Quente (24-28) |          7.2 |       7.2 |         7.2 |
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
| Batch size | 2048 |
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
| Epocas treinadas | 77 |
| KLD final — treino | 0.0709 |
| KLD final — val | 0.0889 |
| Top-1 final — treino | 0.6446 |
| Top-1 final — val | 0.6294 |
| **Melhor val_oma** | **0.9747** |


---


## 4. Avaliação no Conjunto de Teste


### 4.1 Resumo Geral

| Conjunto   | N         |   KLD Loss |   Top-1 |   Top-3 |   Top-5 |
|:-----------|:----------|-----------:|--------:|--------:|--------:|
| Treino     | 5,872,784 |     0.0575 |  0.6344 |  0.8413 |  0.9015 |
| Validação  | 1,258,454 |     0.0890 |  0.6215 |  0.8290 |  0.8923 |
| Teste      | 1,258,454 |     0.0893 |  0.6221 |  0.8293 |  0.8929 |

| Métrica | Valor |
|---------|-------|
| Gap Top-1 (Treino − Val) | +1.29 pp |
| Gap KLD (Val − Treino) | +0.0315 |
| **OMA global** | **97.4%** |
| Média jogadas Minimax-equiv. | 3.4 |


### 4.2 Métricas por Fase

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 485556 | 49.4%   | 69.2%   | 78.5%   | 95.1%  |
| 1a Metade (12-17)   | 404916 | 67.2%   | 88.5%   | 94.5%   | 97.8%  |
| 2a Metade (18-23)   | 242659 | 74.2%   | 94.0%   | 96.9%   | 100.0% |
| Fase Quente (24-28) |  91075 | 65.4%   | 95.4%   | 98.9%   | 100.0% |
| Final (29-31)       |  34248 | 92.0%   | 100.0%  | 100.0%  | 100.0% |


### 4.3 Classification Report

| Métrica | Precision | Recall | F1 |
|---------|-----------|--------|----|
| Accuracy | — | — | 0.6221 |
| Macro avg | 0.6351 | 0.7096 | 0.6354 |
| Weighted avg | 0.6941 | 0.6221 | 0.6054 |


#### Top 10 jogadas (melhor F1)

| Jogada   |   precision |   recall |   f1-score |    support | Borda   |
|:---------|------------:|---------:|-----------:|-----------:|:--------|
| H_6_1    |      0.6567 |   0.8082 |     0.7246 | 27476.0000 | False   |
| H_2_5    |      0.7278 |   0.6924 |     0.7096 | 39253.0000 | False   |
| V_1_6    |      0.7091 |   0.7091 |     0.7091 | 28600.0000 | True    |
| H_4_5    |      0.6500 |   0.7681 |     0.7042 | 38405.0000 | False   |
| H_4_1    |      0.6711 |   0.7247 |     0.6968 | 44640.0000 | False   |
| H_6_5    |      0.5683 |   0.8886 |     0.6932 | 25951.0000 | False   |
| V_1_0    |      0.7471 |   0.6282 |     0.6825 | 36793.0000 | True    |
| H_4_3    |      0.5679 |   0.8488 |     0.6805 | 54542.0000 | False   |
| V_1_4    |      0.6934 |   0.6539 |     0.6731 | 49641.0000 | False   |
| V_7_0    |      0.6530 |   0.6773 |     0.6649 | 23363.0000 | True    |


#### Bottom 5 jogadas (pior F1)

| Jogada   |   precision |   recall |   f1-score |     support | Borda   |
|:---------|------------:|---------:|-----------:|------------:|:--------|
| H_8_1    |      0.4299 |   0.9555 |     0.5930 |  15489.0000 | True    |
| V_5_4    |      0.4632 |   0.8177 |     0.5914 |  35791.0000 | False   |
| H_0_5    |      0.8345 |   0.4214 |     0.5600 |  66433.0000 | True    |
| H_0_3    |      0.8583 |   0.3304 |     0.4771 |  89105.0000 | True    |
| H_0_1    |      0.9789 |   0.2101 |     0.3459 | 130983.0000 | True    |

*[Gráficos de curvas de aprendizado — ver notebook]*


---


### 4.4 Métricas por qtd_cadeias_longas

| Grupo      |      N | Top-1   | Top-3   | OMA   |
|:-----------|-------:|:--------|:--------|:------|
| 0 cadeias  | 811311 | 58.5%   | 79.1%   | 96.5% |
| 1 cadeia   | 370465 | 69.6%   | 90.7%   | 99.0% |
| 2 cadeias  |  74946 | 66.7%   | 86.5%   | 99.7% |
| ≥3 cadeias |   1732 | 49.9%   | 71.8%   | 99.4% |


---


## 5. Presença de Canais por Fase (%)

*Percentual de amostras no conjunto de Teste com ao menos uma célula = 1 no canal*

| Fase                |   aresta_topo |   aresta_base |   aresta_esquerda |   aresta_direita |   caixa_fechada |   eh_grau3 |   eh_grau2 |   em_cadeia_curta |   em_cadeia_longa |   em_loop |   em_cadeia_aberta_uma_ponta |   paridade_cadeia_longa_impar |
|:--------------------|--------------:|--------------:|------------------:|-----------------:|----------------:|-----------:|-----------:|------------------:|------------------:|----------:|-----------------------------:|------------------------------:|
| Abertura (0-11)     |          93.9 |          93.9 |              94.0 |             94.0 |            11.0 |       18.8 |       87.5 |              24.7 |               3.3 |       0.0 |                          0.6 |                           3.3 |
| 1a Metade (12-17)   |         100.0 |         100.0 |             100.0 |            100.0 |            71.3 |       42.2 |      100.0 |              70.5 |              46.6 |       0.6 |                          7.0 |                          38.0 |
| 2a Metade (18-23)   |         100.0 |         100.0 |             100.0 |            100.0 |            99.6 |       68.8 |      100.0 |              54.3 |              79.1 |       4.4 |                         24.4 |                          62.6 |
| Fase Quente (24-28) |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       83.7 |       99.9 |              31.7 |              55.4 |       8.2 |                         62.9 |                          55.4 |
| Final (29-31)       |         100.0 |         100.0 |             100.0 |            100.0 |           100.0 |       99.8 |       42.6 |               0.0 |               0.0 |       0.0 |                         35.1 |                           0.0 |


---


## 6. Métricas por Canal

*Amostras do Teste onde o canal tem ao menos uma célula = 1*

| Canal                       |       N | Top-1   | Top-3   | Top-5   | OMA    |
|:----------------------------|--------:|:--------|:--------|:--------|:-------|
| aresta_topo                 | 1228962 | 63.2%   | 84.0%   | 90.2%   | 97.4%  |
| aresta_base                 | 1228939 | 63.1%   | 84.0%   | 90.2%   | 97.4%  |
| aresta_esquerda             | 1229201 | 63.2%   | 84.1%   | 90.4%   | 97.4%  |
| aresta_direita              | 1229287 | 63.1%   | 84.0%   | 90.3%   | 97.4%  |
| caixa_fechada               |  709380 | 69.5%   | 90.7%   | 95.4%   | 98.9%  |
| eh_grau3                    |  539435 | 86.7%   | 100.0%  | 100.0%  | 100.0% |
| eh_grau2                    | 1177714 | 63.4%   | 84.8%   | 91.0%   | 97.3%  |
| em_cadeia_curta             |  565825 | 66.6%   | 88.0%   | 93.6%   | 97.5%  |
| em_cadeia_longa             |  447143 | 69.0%   | 89.9%   | 95.0%   | 99.1%  |
| em_loop                     |   20894 | 68.3%   | 91.6%   | 96.9%   | 99.8%  |
| em_cadeia_aberta_uma_ponta  |  159635 | 79.0%   | 100.0%  | 100.0%  | 99.8%  |
| paridade_cadeia_longa_impar |  372197 | 69.5%   | 90.6%   | 95.4%   | 99.0%  |


---


## 7. Correlação Canal × Erro

*Erros (OMA=0): 32534 de 1258454 (2.6%) no conjunto de Teste*
*Delta positivo = canal sobrerrepresentado nos erros*

| Canal                       | Total (%)   | Em Erros (%)   |   Delta (pp) |
|:----------------------------|:------------|:---------------|-------------:|
| eh_grau2                    | 93.6%       | 98.6%          |       5.0000 |
| aresta_esquerda             | 97.7%       | 99.1%          |       1.4000 |
| aresta_direita              | 97.7%       | 99.0%          |       1.3000 |
| aresta_base                 | 97.7%       | 98.7%          |       1.1000 |
| aresta_topo                 | 97.7%       | 98.6%          |       1.0000 |
| em_cadeia_curta             | 45.0%       | 44.2%          |      -0.8000 |
| em_loop                     | 1.7%        | 0.1%           |      -1.5000 |
| em_cadeia_aberta_uma_ponta  | 12.7%       | 0.8%           |     -11.9000 |
| paridade_cadeia_longa_impar | 29.6%       | 11.7%          |     -17.9000 |
| em_cadeia_longa             | 35.5%       | 12.5%          |     -23.0000 |
| caixa_fechada               | 56.4%       | 24.9%          |     -31.4000 |
| eh_grau3                    | 42.9%       | 0.8%           |     -42.1000 |


---


## 8. Performance por Fase (Numérico)

| Fase                |      N | Top-1   | Top-3   | Top-5   | OMA    |
|:--------------------|-------:|:--------|:--------|:--------|:-------|
| Abertura (0-11)     | 485556 | 49.4%   | 69.2%   | 78.5%   | 95.1%  |
| 1a Metade (12-17)   | 404916 | 67.2%   | 88.5%   | 94.5%   | 97.8%  |
| 2a Metade (18-23)   | 242659 | 74.2%   | 94.0%   | 96.9%   | 100.0% |
| Fase Quente (24-28) |  91075 | 65.4%   | 95.4%   | 98.9%   | 100.0% |
| Final (29-31)       |  34248 | 92.0%   | 100.0%  | 100.0%  | 100.0% |

*[Gráfico de barras por fase — ver notebook]*


---


## 9. Exportacao TFLite

| Parametro | Valor |
|-----------|-------|
| Arquivo | `pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite` |
| Caminho | `/content/drive/MyDrive/Arena Sagaz/CNN/resultados/pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite` |
| Tamanho | 19337.1 KB |
| Quantizacao | Nenhuma (float32) |


---

