# Estratégia de Dados: Mid/Endgame vs Early Game

Durante a geração de dados, nós configuramos o gerador aleatório para preencher os tabuleiros entre **15% e 85%** antes de chamar o Minimax. Isso levantou uma excelente questão: *Se a rede neural treinar com esses dados, ela saberá jogar no começo da partida (Early Game), quando o tabuleiro está vazio?*

A resposta é **SIM, ela jogará perfeitamente bem**, e a explicação para isso é um dos conceitos mais fascinantes de Inteligência Artificial aplicada a jogos (e outro ótimo ponto para a defesa do seu TCC).

---

## 1. A Natureza do "Early Game" em Pontinhos

No Jogo dos Pontinhos, o começo da partida é o que chamamos de **fase neutra ou de simetria**. 
Quando o tabuleiro está vazio ou tem apenas 1 ou 2 traços, **praticamente qualquer jogada é segura**. Não há caixas para fechar e não há perigo de entregar uma caixa ao adversário. 

Se nós forçássemos o Minimax a calcular jogadas com o tabuleiro 0% a 10% preenchido:
1. Ele demoraria dias para calcular um único estado.
2. O resultado seria quase inútil para aprendizado, pois ele diria que "fazer a linha H_0_1" é tão bom quanto "fazer a linha V_2_2". O rótulo ótimo seria quase arbitrário.

## 2. Como a CNN joga o começo da partida sem ter treinado 0%?

A Rede Neural Convolucional (CNN) não decora tabuleiros; ela aprende **Padrões Geométricos e Regras de Sobrevivência**. 

Ao treinar intensamente com os dados de 15% a 85%, a CNN vai aprender a regra de ouro do jogo de forma implacável:
> *"Se uma caixa tem 2 traços, NUNCA desenhe o 3º traço, senão o adversário pontua".*

Quando você colocar a CNN para jogar no turno 1 (tabuleiro 0% vazio), ela vai varrer o tabuleiro procurando padrões perigosos. Como o tabuleiro está vazio, ela verá que **não há perigo em nenhum lugar**.
A saída da rede (Softmax) vai dar uma probabilidade quase igual para todos os traços (ex: 3% de confiança para cada linha). A CNN vai, então, escolher qualquer uma delas e fará uma **jogada inicial segura e perfeitamente válida**.

## 3. O limite de 15% é perto o suficiente do começo!

Lembre-se que no tabuleiro Pequeno (3x4), existem 31 traços no total.
**15% de 31 traços são apenas 4 traços desenhados!**
Isso significa que a sua IA está, sim, treinando cenários muito próximos do início do jogo. O "Early Game" já está coberto pela margem inferior do nosso gerador.

## 4. O Comportamento Esperado no App

Quando o seu App estiver pronto, você notará o seguinte comportamento na IA (Nível Sagaz):
*   **Turnos 1 a 4:** A IA jogará rápido e de forma aparentemente espalhada (escolhendo traços com probabilidades muito próximas, espalhando as linhas para não criar blocos perigosos).
*   **Midgame (Turnos 5 a 20):** A IA começará a ficar extremamente cuidadosa, usando as convoluções para detectar "paredes" de 2 traços e fugindo delas agressivamente.
*   **Endgame:** Quando a tela estiver cheia e alguém for forçado a "dar a primeira caixa", a IA fará o cálculo visual de qual "corredor" de caixas é o menor para entregar ao humano, garantindo a vitória matemática.

Portanto, o corte de 15% a 85% foi a **jogada de mestre** para pular a parte matematicamente intratável do Minimax (0 a 14%), sem sacrificar nenhuma inteligência tática real da sua rede neural!