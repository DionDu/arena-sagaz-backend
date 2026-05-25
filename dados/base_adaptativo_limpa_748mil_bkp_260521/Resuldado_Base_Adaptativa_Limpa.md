# Base de dados utilizada nos testes:

Base foi gerada pelo Notebook @notebooks\jogo_pontinhos\Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb no Databricks.

Notebook faz partidas (autoplay) da primeira até a última jogada e salva o estado do tabuleiro em cada um dos turnos.

Mais detalhes em @docs\jogo_pontinhos\geracao_dados_v7_adaptativo.md

Index	Quantidade de Traços	Amostras Brutas (Total)	Amostras Distintas (Únicas)
0	1	25288	31
1	2	25288	465
2	3	25288	4475
3	4	25288	17247
4	5	25288	23432
5	6	25288	24851
6	7	25288	25158
7	8	25288	25236
8	9	25288	25262
9	10	25288	25274
10	11	25288	25268
11	12	25288	25276
12	13	25288	25276
13	14	25288	25265
14	15	25288	25255
15	16	25288	25234
16	17	25288	25204
17	18	25288	25099
18	19	25288	24654
19	20	25288	23636
20	21	25288	21549
21	22	25288	18437
22	23	25288	14885
23	24	25288	10818
24	25	25288	7200
25	26	25288	4003
26	27	25288	1734
27	28	25288	616
28	29	25288	168
29	30	25288	31

# Modelo com Melhor Jogada definido por Minimax p=7 **SOMENTE AMOSTRAS DISTINTAS**

Epoch 155/300
1371/1371 - 9s - 6ms/step - accuracy: 0.4379 - loss: 0.2886 - top3_acc: 0.6113 - top5_acc: 0.6966 - val_accuracy: 0.4668 - val_loss: 0.1793 - val_top3_acc: 0.6420 - val_top5_acc: 0.7369 - learning_rate: 1.0000e-05

 ======================================================================
RESUMO DE DESEMPENHO (BoxNet v3 — soft targets / KL Divergence)
======================================================================
 conjunto  amostras  kld_loss  top1_acc  top3_acc  top5_acc
   Treino    350727    0.1782    0.4648    0.6428    0.7380
Validação     75156    0.1793    0.4668    0.6420    0.7369
    Teste     75156    0.1799    0.4663    0.6432    0.7369

Gap top1 (Treino - Val): -0.21 pp   [< 5 pp saudável; > 10 pp = overfit]
Gap KLD  (Val - Treino): +0.0012

Última época: 165
  kld_loss  treino=0.2888  val=0.1798
  top1_acc  treino=0.4391  val=0.4470

======================================================================
CLASSIFICATION REPORT (conjunto de TESTE)
======================================================================
  accuracy:      0.4663
  macro avg:     P=0.5173  R=0.6686  F1=0.5459
  weighted avg:  P=0.6313  R=0.4663  F1=0.4337
Top 10 jogadas com melhor F1 (onde o modelo brilha):
                  precision  recall  f1-score   support
jogada_formatada                                       
V_7_4                0.6734  0.8581    0.7546 1353.0000
V_7_2                0.6600  0.7881    0.7183 1458.0000
H_4_5                0.6331  0.7759    0.6973 1428.0000
H_6_3                0.6624  0.7080    0.6845 1250.0000
H_8_5 (Borda)        0.5304  0.9540    0.6818  805.0000
V_1_4                0.7156  0.6484    0.6803 2045.0000
V_5_2                0.6586  0.6856    0.6719 1317.0000
H_2_1                0.6146  0.7359    0.6698 1723.0000
V_1_2                0.6820  0.6321    0.6561 2188.0000
V_3_4                0.6514  0.6336    0.6424 1504.0000
Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
                  precision  recall  f1-score    support
jogada_formatada                                        
H_8_1 (Borda)        0.2372  0.9236    0.3775   851.0000
H_0_5 (Borda)        0.4941  0.3038    0.3763  5085.0000
H_0_3 (Borda)        0.5587  0.2568    0.3519  8527.0000
V_5_6 (Borda)        0.1429  0.7633    0.2407  1356.0000
H_0_1 (Borda)        0.9645  0.1090    0.1958 19713.0000

Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
        precision  recall  f1-score    support
jogada                                        
H_8_1      0.2372  0.9236    0.3775   851.0000
H_0_5      0.4941  0.3038    0.3763  5085.0000
H_0_3      0.5587  0.2568    0.3519  8527.0000
V_5_6      0.1429  0.7633    0.2407  1356.0000
H_0_1      0.9645  0.1090    0.1958 19713.0000

======================================================================
TOP-1 / TOP-3 ACCURACY POR FASE DO JOGO
======================================================================
  Fase                               N    Top-1    Top-3    Top-5
  Abertura (0-11 tracos)         29505   21.7%   35.2%   47.9%
  1ª Metade (12-17 tracos)       22726   52.2%   73.7%   83.9%
  2ª Metade (18-23 tracos)       19239   73.8%   91.4%   96.3%
  Fase Quente (24-28 tracos)      3656   70.5%   97.9%   99.2%
  Final (29-31 tracos)              30   46.7%  100.0%  100.0%

  Optimal Move Accuracy (previsao in conjunto Minimax-otimo): 92.2%
  Media de jogadas Minimax-equivalentes por estado: 7.4


======================================================================
ANÁLISE DE VIÉS DE BORDAS (CNN vs MINIMAX)
======================================================================
  Global:
    Minimax joga na borda: 65.7%
    CNN joga na borda:     51.9%
    Viés (CNN - Minimax):  -13.7 pp

  Segmentado por Fase do Jogo:
    Abertura (0-11 tracos)     -> Minimax: 83.8% | CNN: 62.0% | Viés: -21.7 pp
    1ª Metade (12-17 tracos)   -> Minimax: 55.0% | CNN: 43.0% | Viés: -11.9 pp
    2ª Metade (18-23 tracos)   -> Minimax: 54.7% | CNN: 49.2% | Viés:  -5.5 pp
    Fase Quente (24-28 tracos) -> Minimax: 43.9% | CNN: 39.7% | Viés:  -4.2 pp
    Final (29-31 tracos)       -> Minimax: 43.3% | CNN: 66.7% | Viés:  23.3 pp

========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=1)  (200 partidas)
  Vitórias CNN          186  ( 93.0%)
  Empates                 8  (  4.0%)
  Derrotas CNN            6  (  3.0%)
  Tempo médio CNN:  0.09 ms/jogada
  Tempo médio Minimax(p=1): 0.2 ms/jogada
  CNN é 2× mais rápida
  Caixas deixadas p/ Minimax:  161 / 1866 oportunidades (8.6%)

  Adversário: Minimax(p=3)  (200 partidas)
  Vitórias CNN          114  ( 57.0%)
  Empates                45  ( 22.5%)
  Derrotas CNN           41  ( 20.5%)
  Tempo médio CNN:  0.13 ms/jogada
  Tempo médio Minimax(p=3): 80.5 ms/jogada
  CNN é 630× mais rápida
  Caixas deixadas p/ Minimax:  219 / 1505 oportunidades (14.6%)

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN           86  ( 43.0%)
  Empates                45  ( 22.5%)
  Derrotas CNN           69  ( 34.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=5): 1550.9 ms/jogada
  CNN é 11099× mais rápida
  Caixas deixadas p/ Minimax:  230 / 1362 oportunidades (16.9%)

  Adversário: Minimax(p=6)  (200 partidas)
  Vitórias CNN           74  ( 37.0%)
  Empates                43  ( 21.5%)
  Derrotas CNN           83  ( 41.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=6): 4909.8 ms/jogada
  CNN é 34346× mais rápida
  Caixas deixadas p/ Minimax:  193 / 1245 oportunidades (15.5%)

========================================================================




# Modelo com Melhor Jogada definido por Minimax p=7 **COM AMOSTRAS DUPLICADAS**

Epoch 94/300
2075/2075 - 13s - 6ms/step - accuracy: 0.4691 - loss: 0.2161 - top3_acc: 0.6307 - top5_acc: 0.7059 - val_accuracy: 0.4776 - val_loss: 0.1285 - val_top3_acc: 0.6417 - val_top5_acc: 0.7181 - learning_rate: 1.0000e-05
Restoring model weights from the end of the best epoch: 94.

 ======================================================================
RESUMO DE DESEMPENHO (BoxNet v3 — soft targets / KL Divergence)
======================================================================
 conjunto  amostras  kld_loss  top1_acc  top3_acc  top5_acc
   Treino    531047    0.1277    0.4788    0.6427    0.7191
Validação    113797    0.1285    0.4776    0.6417    0.7181
    Teste    113796    0.1287    0.4806    0.6438    0.7199

Gap top1 (Treino - Val): +0.12 pp   [< 5 pp saudável; > 10 pp = overfit]
Gap KLD  (Val - Treino): +0.0008

Última época: 104
  kld_loss  treino=0.2160  val=0.1286
  top1_acc  treino=0.4685  val=0.4799

======================================================================
CLASSIFICATION REPORT (conjunto de TESTE)
======================================================================
  accuracy:      0.4806
  macro avg:     P=0.5113  R=0.6904  F1=0.5446
  weighted avg:  P=0.6546  R=0.4806  F1=0.4367
Top 10 jogadas com melhor F1 (onde o modelo brilha):
                  precision  recall  f1-score   support
jogada_formatada                                       
H_4_5                0.6126  0.7951    0.6920 2265.0000
H_4_1                0.6183  0.7775    0.6888 2463.0000
H_2_5                0.5865  0.8333    0.6885 2604.0000
H_6_5                0.5707  0.8615    0.6866 2217.0000
H_2_1                0.6123  0.7313    0.6666 2605.0000
V_1_4                0.6848  0.6436    0.6636 3241.0000
V_7_2                0.5432  0.8358    0.6585 2113.0000
H_2_3                0.6156  0.6933    0.6522 2511.0000
V_5_2                0.5904  0.7053    0.6427 2487.0000
H_6_3                0.5433  0.7837    0.6417 1993.0000
Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
                  precision  recall  f1-score    support
jogada_formatada                                        
H_8_5 (Borda)        0.2494  0.9740    0.3971  1155.0000
V_1_0 (Borda)        0.2970  0.5355    0.3821  2975.0000
H_0_3 (Borda)        0.6270  0.2179    0.3235 10452.0000
V_7_0 (Borda)        0.1847  0.7243    0.2944  2013.0000
H_0_1 (Borda)        0.9728  0.1018    0.1843 31921.0000

Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
        precision  recall  f1-score    support
jogada                                        
H_8_5      0.2494  0.9740    0.3971  1155.0000
V_1_0      0.2970  0.5355    0.3821  2975.0000
H_0_3      0.6270  0.2179    0.3235 10452.0000
V_7_0      0.1847  0.7243    0.2944  2013.0000
H_0_1      0.9728  0.1018    0.1843 31921.0000

======================================================================
TOP-1 / TOP-3 ACCURACY POR FASE DO JOGO
======================================================================
  Fase                               N    Top-1    Top-3    Top-5
  Abertura (0-11 tracos)         41725   15.9%   26.2%   36.6%
  1ª Metade (12-17 tracos)       22759   51.0%   73.1%   83.3%
  2ª Metade (18-23 tracos)       22759   71.0%   89.8%   94.7%
  Fase Quente (24-28 tracos)     18966   69.6%   93.1%   97.7%
  Final (29-31 tracos)            7587   93.1%  100.0%  100.0%

  Optimal Move Accuracy (previsao in conjunto Minimax-otimo): 94.3%
  Media de jogadas Minimax-equivalentes por estado: 8.4


======================================================================
ANÁLISE DE VIÉS DE BORDAS (CNN vs MINIMAX)
======================================================================
  Global:
    Minimax joga na borda: 62.7%
    CNN joga na borda:     49.1%
    Viés (CNN - Minimax):  -13.6 pp

  Segmentado por Fase do Jogo:
    Abertura (0-11 tracos)     -> Minimax: 88.4% | CNN: 65.8% | Viés: -22.7 pp
    1ª Metade (12-17 tracos)   -> Minimax: 53.9% | CNN: 40.4% | Viés: -13.5 pp
    2ª Metade (18-23 tracos)   -> Minimax: 54.0% | CNN: 48.0% | Viés:  -6.0 pp
    Fase Quente (24-28 tracos) -> Minimax: 32.4% | CNN: 24.0% | Viés:  -8.4 pp
    Final (29-31 tracos)       -> Minimax: 49.0% | CNN: 49.0% | Viés:  -0.0 pp


========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=1)  (200 partidas)
  Vitórias CNN          192  ( 96.0%)
  Empates                 6  (  3.0%)
  Derrotas CNN            2  (  1.0%)
  Tempo médio CNN:  0.09 ms/jogada
  Tempo médio Minimax(p=1): 0.2 ms/jogada
  CNN é 2× mais rápida
  Caixas deixadas p/ Minimax:   41 / 1937 oportunidades (2.1%)

  Adversário: Minimax(p=3)  (200 partidas)
  Vitórias CNN          167  ( 83.5%)
  Empates                11  (  5.5%)
  Derrotas CNN           22  ( 11.0%)
  Tempo médio CNN:  0.12 ms/jogada
  Tempo médio Minimax(p=3): 78.8 ms/jogada
  CNN é 667× mais rápida
  Caixas deixadas p/ Minimax:   97 / 1556 oportunidades (6.2%)

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN          137  ( 68.5%)
  Empates                20  ( 10.0%)
  Derrotas CNN           43  ( 21.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=5): 1708.3 ms/jogada
  CNN é 12576× mais rápida
  Caixas deixadas p/ Minimax:  131 / 1440 oportunidades (9.1%)

  Adversário: Minimax(p=6)  (200 partidas)
  Vitórias CNN          113  ( 56.5%)
  Empates                17  (  8.5%)
  Derrotas CNN           70  ( 35.0%)
  Tempo médio CNN:  0.15 ms/jogada
  Tempo médio Minimax(p=6): 5839.6 ms/jogada
  CNN é 39914× mais rápida
  Caixas deixadas p/ Minimax:   96 / 1287 oportunidades (7.5%)

========================================================================




# Modelo com Melhor Jogada definido por Minimax p=7 **AMOSTRAS DISTINTAS + SAMPLE WEIGHT + CLIP PESOS 20X**

Notebook @notebooks\jogo_pontinhos\Treinamento_CNN_Arena_Sagaz_V7_Sample_Weight.ipynb

Epoch 282/300
1371/1371 - 8s - 6ms/step - accuracy: 0.4324 - loss: 1.5895 - top3_acc: 0.6056 - top5_acc: 0.6927 - val_accuracy: 0.4574 - val_loss: 0.2303 - val_top3_acc: 0.6437 - val_top5_acc: 0.7353 - learning_rate: 1.0000e-05

Restoring model weights from the end of the best epoch: 282.


 ======================================================================
RESUMO DE DESEMPENHO (BoxNet v3 — soft targets / KL Divergence)
======================================================================
 conjunto  amostras  kld_loss  top1_acc  top3_acc  top5_acc
   Treino    350727    0.2286    0.4551    0.6452    0.7375
Validação     75156    0.2303    0.4574    0.6437    0.7353
    Teste     75156    0.2311    0.4570    0.6464    0.7367

Gap top1 (Treino - Val): -0.23 pp   [< 5 pp saudável; > 10 pp = overfit]
Gap KLD  (Val - Treino): +0.0017

Última época: 292
  kld_loss  treino=1.5863  val=0.2303
  top1_acc  treino=0.4300  val=0.4524

======================================================================
CLASSIFICATION REPORT (conjunto de TESTE)
======================================================================
  accuracy:      0.4570
  macro avg:     P=0.4815  R=0.6514  F1=0.5222
  weighted avg:  P=0.6071  R=0.4570  F1=0.4246
Top 10 jogadas com melhor F1 (onde o modelo brilha):
                  precision  recall  f1-score   support
jogada_formatada                                       
H_2_1                0.5814  0.7174    0.6422 1723.0000
H_6_1                0.5195  0.7839    0.6249 1513.0000
H_6_5                0.5113  0.8003    0.6239 1417.0000
H_4_5                0.5332  0.7262    0.6149 1428.0000
H_4_1                0.5374  0.7106    0.6120 1517.0000
H_2_5                0.5088  0.7625    0.6103 1625.0000
H_4_3                0.5447  0.6905    0.6090 1173.0000
V_1_4                0.5752  0.6377    0.6048 2045.0000
V_1_2                0.5543  0.6481    0.5976 2188.0000
V_7_0 (Borda)        0.5096  0.7065    0.5921 1574.0000
Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
                  precision  recall  f1-score    support
jogada_formatada                                        
V_1_0 (Borda)        0.3861  0.4609    0.4202  2074.0000
H_0_5 (Borda)        0.4038  0.2877    0.3360  5085.0000
H_0_3 (Borda)        0.5515  0.2186    0.3131  8527.0000
H_0_1 (Borda)        0.9711  0.1332    0.2342 19713.0000
H_8_3 (Borda)        0.1163  0.8401    0.2043   982.0000

Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
        precision  recall  f1-score    support
jogada                                        
V_1_0      0.3861  0.4609    0.4202  2074.0000
H_0_5      0.4038  0.2877    0.3360  5085.0000
H_0_3      0.5515  0.2186    0.3131  8527.0000
H_0_1      0.9711  0.1332    0.2342 19713.0000
H_8_3      0.1163  0.8401    0.2043   982.0000

======================================================================
TOP-1 / TOP-3 ACCURACY POR FASE DO JOGO
======================================================================
  Fase                               N    Top-1    Top-3    Top-5
  Abertura (0-11 tracos)         29505   22.9%   37.1%   49.4%
  1ª Metade (12-17 tracos)       22726   49.7%   72.4%   82.1%
  2ª Metade (18-23 tracos)       19239   71.7%   91.3%   96.0%
  Fase Quente (24-28 tracos)      3656   67.9%   98.1%   99.0%
  Final (29-31 tracos)              30   53.3%  100.0%  100.0%

  Optimal Move Accuracy (previsao in conjunto Minimax-otimo): 91.0%
  Media de jogadas Minimax-equivalentes por estado: 7.4


======================================================================
ANÁLISE DE VIÉS DE BORDAS (CNN vs MINIMAX)
======================================================================
  Global:
    Minimax joga na borda: 65.7%
    CNN joga na borda:     52.2%
    Viés (CNN - Minimax):  -13.4 pp

  Segmentado por Fase do Jogo:
    Abertura (0-11 tracos)     -> Minimax: 83.8% | CNN: 62.9% | Viés: -20.8 pp
    1ª Metade (12-17 tracos)   -> Minimax: 55.0% | CNN: 41.9% | Viés: -13.1 pp
    2ª Metade (18-23 tracos)   -> Minimax: 54.7% | CNN: 49.9% | Viés:  -4.8 pp
    Fase Quente (24-28 tracos) -> Minimax: 43.9% | CNN: 42.5% | Viés:  -1.4 pp
    Final (29-31 tracos)       -> Minimax: 43.3% | CNN: 53.3% | Viés:  10.0 pp



========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=1)  (200 partidas)
  Vitórias CNN          176  ( 88.0%)
  Empates                15  (  7.5%)
  Derrotas CNN            9  (  4.5%)
  Tempo médio CNN:  0.09 ms/jogada
  Tempo médio Minimax(p=1): 0.2 ms/jogada
  CNN é 2× mais rápida
  Caixas deixadas p/ Minimax:  142 / 1899 oportunidades (7.5%)

  Adversário: Minimax(p=3)  (200 partidas)
  Vitórias CNN          121  ( 60.5%)
  Empates                30  ( 15.0%)
  Derrotas CNN           49  ( 24.5%)
  Tempo médio CNN:  0.13 ms/jogada
  Tempo médio Minimax(p=3): 80.6 ms/jogada
  CNN é 599× mais rápida
  Caixas deixadas p/ Minimax:  184 / 1450 oportunidades (12.7%)

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN          112  ( 56.0%)
  Empates                35  ( 17.5%)
  Derrotas CNN           53  ( 26.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=5): 1620.9 ms/jogada
  CNN é 11332× mais rápida
  Caixas deixadas p/ Minimax:  175 / 1380 oportunidades (12.7%)

  Adversário: Minimax(p=6)  (200 partidas)
  Vitórias CNN           92  ( 46.0%)
  Empates                35  ( 17.5%)
  Derrotas CNN           73  ( 36.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=6): 5218.8 ms/jogada
  CNN é 36086× mais rápida
  Caixas deixadas p/ Minimax:  159 / 1259 oportunidades (12.6%)

========================================================================





# Modelo com Melhor Jogada definido por Minimax p=7 **AMOSTRAS DISTINTAS + SAMPLE WEIGHT + SEM CLIP**


Restoring model weights from the end of the best epoch: 253.

Epoch 253/300
1371/1371 - 9s - 6ms/step - accuracy: 0.4319 - loss: 1.5421 - top3_acc: 0.6063 - top5_acc: 0.6930 - val_accuracy: 0.4442 - val_loss: 0.2274 - val_top3_acc: 0.6194 - val_top5_acc: 0.7092 - learning_rate: 1.0000e-05



 ======================================================================
RESUMO DE DESEMPENHO (BoxNet v3 — soft targets / KL Divergence)
======================================================================
 conjunto  amostras  kld_loss  top1_acc  top3_acc  top5_acc
   Treino    350727    0.2258    0.4414    0.6216    0.7112
Validação     75156    0.2274    0.4442    0.6194    0.7092
    Teste     75156    0.2284    0.4416    0.6213    0.7116

Gap top1 (Treino - Val): -0.28 pp   [< 5 pp saudável; > 10 pp = overfit]
Gap KLD  (Val - Treino): +0.0016

Última época: 263
  kld_loss  treino=1.5406  val=0.2279
  top1_acc  treino=0.4302  val=0.4402

======================================================================
CLASSIFICATION REPORT (conjunto de TESTE)
======================================================================
  accuracy:      0.4416
  macro avg:     P=0.4831  R=0.6449  F1=0.5154
  weighted avg:  P=0.6045  R=0.4416  F1=0.4029
Top 10 jogadas com melhor F1 (onde o modelo brilha):
                  precision  recall  f1-score   support
jogada_formatada                                       
H_6_1                0.5845  0.7865    0.6706 1513.0000
V_7_4                0.5585  0.8285    0.6673 1353.0000
V_7_6 (Borda)        0.6018  0.7031    0.6485 1337.0000
H_2_5                0.5754  0.7329    0.6447 1625.0000
H_4_1                0.5784  0.6829    0.6264 1517.0000
V_1_2                0.6196  0.6321    0.6258 2188.0000
V_1_4                0.6232  0.6171    0.6201 2045.0000
H_2_1                0.5418  0.7145    0.6163 1723.0000
H_6_5                0.4951  0.7925    0.6095 1417.0000
V_3_4                0.5944  0.6197    0.6068 1504.0000
Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
                  precision  recall  f1-score    support
jogada_formatada                                        
H_0_5 (Borda)        0.3858  0.2818    0.3257  5085.0000
V_5_0 (Borda)        0.2063  0.5913    0.3059  1654.0000
V_7_0 (Borda)        0.1929  0.6747    0.3000  1574.0000
H_0_3 (Borda)        0.5696  0.2024    0.2987  8527.0000
H_0_1 (Borda)        0.9527  0.0950    0.1727 19713.0000

Bottom 5 jogadas (onde o modelo mais erra — verificar bordas):
        precision  recall  f1-score    support
jogada                                        
H_0_5      0.3858  0.2818    0.3257  5085.0000
V_5_0      0.2063  0.5913    0.3059  1654.0000
V_7_0      0.1929  0.6747    0.3000  1574.0000
H_0_3      0.5696  0.2024    0.2987  8527.0000
H_0_1      0.9527  0.0950    0.1727 19713.0000

======================================================================
TOP-1 / TOP-3 ACCURACY POR FASE DO JOGO
======================================================================
  Fase                               N    Top-1    Top-3    Top-5
  Abertura (0-11 tracos)         29505   19.4%   31.0%   43.2%
  1ª Metade (12-17 tracos)       22726   49.7%   72.0%   82.0%
  2ª Metade (18-23 tracos)       19239   71.3%   91.3%   96.0%
  Fase Quente (24-28 tracos)      3656   66.2%   98.1%   99.0%
  Final (29-31 tracos)              30   40.0%  100.0%  100.0%

  Optimal Move Accuracy (previsao in conjunto Minimax-otimo): 91.0%
  Media de jogadas Minimax-equivalentes por estado: 7.4


======================================================================
ANÁLISE DE VIÉS DE BORDAS (CNN vs MINIMAX)
======================================================================
  Global:
    Minimax joga na borda: 65.7%
    CNN joga na borda:     55.5%
    Viés (CNN - Minimax):  -10.1 pp

  Segmentado por Fase do Jogo:
    Abertura (0-11 tracos)     -> Minimax: 83.8% | CNN: 70.2% | Viés: -13.6 pp
    1ª Metade (12-17 tracos)   -> Minimax: 55.0% | CNN: 43.5% | Viés: -11.5 pp
    2ª Metade (18-23 tracos)   -> Minimax: 54.7% | CNN: 49.7% | Viés:  -5.0 pp
    Fase Quente (24-28 tracos) -> Minimax: 43.9% | CNN: 43.0% | Viés:  -0.9 pp
    Final (29-31 tracos)       -> Minimax: 43.3% | CNN: 66.7% | Viés:  23.3 pp




========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=1)  (200 partidas)
  Vitórias CNN          183  ( 91.5%)
  Empates                10  (  5.0%)
  Derrotas CNN            7  (  3.5%)
  Tempo médio CNN:  0.09 ms/jogada
  Tempo médio Minimax(p=1): 0.2 ms/jogada
  CNN é 2× mais rápida
  Caixas deixadas p/ Minimax:  169 / 1860 oportunidades (9.1%)

  Adversário: Minimax(p=3)  (200 partidas)
  Vitórias CNN          127  ( 63.5%)
  Empates                31  ( 15.5%)
  Derrotas CNN           42  ( 21.0%)
  Tempo médio CNN:  0.13 ms/jogada
  Tempo médio Minimax(p=3): 80.9 ms/jogada
  CNN é 640× mais rápida
  Caixas deixadas p/ Minimax:  212 / 1488 oportunidades (14.2%)

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN          100  ( 50.0%)
  Empates                33  ( 16.5%)
  Derrotas CNN           67  ( 33.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=5): 1738.6 ms/jogada
  CNN é 12654× mais rápida
  Caixas deixadas p/ Minimax:  217 / 1355 oportunidades (16.0%)

  Adversário: Minimax(p=6)  (200 partidas)
  Vitórias CNN           73  ( 36.5%)
  Empates                28  ( 14.0%)
  Derrotas CNN           99  ( 49.5%)
  Tempo médio CNN:  0.14 ms/jogada
  Tempo médio Minimax(p=6): 5500.3 ms/jogada
  CNN é 38343× mais rápida
  Caixas deixadas p/ Minimax:  164 / 1133 oportunidades (14.5%)

========================================================================