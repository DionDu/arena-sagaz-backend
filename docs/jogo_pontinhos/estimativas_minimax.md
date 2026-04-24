# Estimativas de Treinamento e Processamento do Algoritmo Oráculo (Minimax)

Este documento registra as estimativas reais de tempo necessárias para gerar os datasets de treinamento (50.000 estados) para cada tamanho de tabuleiro do **Arena Sagaz**, baseadas em simulações empíricas executadas com **Minimax com Poda Alpha-Beta na profundidade 7** e paralelismo (Multiprocessing) em um processador equivalente a um **AMD Ryzen 7 5700X (8 núcleos / 16 threads, com uso de 90% da CPU)**.

A lentidão profunda deste cálculo é a prova fundamental do projeto de TCC: é fisicamente impossível executar uma árvore combinatória tão massiva em tempo real no hardware de um smartphone para que a IA jogue no nível "Sagaz" instantaneamente. A solução é pré-processar esses cenários no laboratório e treinar uma Rede Neural Convolucional (CNN / Edge AI).

---

## 1. A Nova Lógica de Geração e o Fator de Ramificação

Anteriormente, o gerador criava tabuleiros muito vazios (máximo de 50% de preenchimento). Para o treinamento da CNN ser eficaz nas decisões de meio e fim de jogo, o gerador foi atualizado para preencher aleatoriamente de **15% a 85%** dos traços antes de pedir para a IA calcular a jogada.

Porém, quando o sorteio cai perto de 15% (tabuleiro quase vazio), o número de caminhos possíveis (fator de ramificação) para 7 turnos à frente beira os bilhões de cálculos, mesmo com Poda Alpha-Beta e Processamento Paralelo.

---

## 2. Cenários Empíricos (Simulações Reais)

De acordo com o LOG de processamento usando **14 threads simultâneas a 90% de uso de CPU**, os 50 primeiros registros levaram **280 segundos** (média de **5,6 segundos por registro**).

Baseado nesse tempo real de processamento, as estimativas projetadas para a geração completa dos lotes de 50.000 são:

### 2.1 Tabuleiro Pequeno (3x4 quadrados)
- **Traços Totais:** 31 traços.
- **Duração Média por Jogada na d=7:** ~5,6 segundos.
- **Tempo para gerar 50.000 rótulos:** ~280.000 segundos.
- **Tempo Contínuo Estimado:** **~77 horas (~3 dias).**

### 2.2 Tabuleiro Médio (4x5 quadrados)
- **Traços Totais:** 49 traços.
- **Escalonamento Exponencial:** A árvore combinatória do Minimax cresce absurdamente mais rápido que a adição de novos quadrados. Estimamos que a busca no tabuleiro médio demorará de 5 a 10 vezes mais que no pequeno.
- **Duração Média por Jogada na d=7:** ~35 segundos.
- **Tempo para gerar 50.000 rótulos:** ~1.750.000 segundos.
- **Tempo Contínuo Estimado:** **~486 horas (~20 dias).**

### 2.3 Tabuleiro Grande (5x7 quadrados)
- **Traços Totais:** 82 traços.
- **Escalonamento Exponencial:** Com mais de 80 opções no início, a profundidade 7 se torna matematicamente proibitiva. O tempo para avaliar um tabuleiro vazio neste tamanho chegaria à casa dos minutos ou horas *por jogada*.
- **Tempo Contínuo Estimado:** **Intratável (Meses ou Anos).**

---

## 3. Otimizações de Laboratório (Move Ordering)

Para mitigar a explosão combinatória, os seguintes ajustes técnicos foram registrados no código fonte (`minimax.py`):
1. **Move Ordering (Ordenação de Jogadas):** O Minimax foi modificado para não testar os traços disponíveis cegamente. Ele agora prioriza traços que **fecham caixas**. Se a IA encontra uma jogada excelente logo na primeira tentativa, a Poda Alpha-Beta imediatamente "poda" (ignora) milhares de outros caminhos inúteis sem calculá-los.

## 4. O Que Fazer no TCC?

Esses dados de 77 horas para o menor tabuleiro com um Ryzen 7 fritando em 90% são o maior argumento do seu TCC. Eles justificam o uso da **Edge AI**.

Para concluir a geração de dados para os tabuleiros maiores e não travar o cronograma do seu projeto, a recomendação oficial é:

1. **Pequeno:** Manter `--profundidade 7` e deixar rodando por 3 dias.
2. **Médio:** Reduzir para `--profundidade 5`. O tempo cairá de 20 dias para algumas poucas horas/dias, sacrificando pouquíssima inteligência tática do Oráculo.
3. **Grande:** Reduzir para `--profundidade 4` ou `--profundidade 3`. A geração será ágil e o modelo treinado ainda será capaz de derrotar humanos iniciantes e intermediários, graças ao reconhecimento de padrões geométricos (não entregar caixas óbvias) da rede convolucional.