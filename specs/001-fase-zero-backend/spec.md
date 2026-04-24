# Especificação da Feature: Backend Arena Sagaz — Fase Zero e Infraestrutura de Dados

**Feature Branch**: `001-fase-zero-backend`
**Criado em**: 2026-04-19
**Status**: Rascunho
**Entrada**: Descrição do usuário + PRD Arena Sagaz v1.0

## Esclarecimentos

### Sessão 2026-04-19

- Q: Como funciona o sistema de XP e pontuação por partida? → A: Sistema composto — pontos por caixas fechadas + bônus de vitória + multiplicador de dificuldade.
- Q: Qual a estratégia de autenticação (tokens)? → A: JWT com access token de curta duração (1h) + refresh token de longa duração (30 dias).
- Q: A API deve ser versionada nas URLs? → A: Sim, prefixo `/v1/` em todos os endpoints desde o início.
- Q: Qual a profundidade padrão do Minimax para o tabuleiro Grande? → A: Configurável via parâmetro; valor padrão inicial = 7. Pode ser aumentado se o tempo de geração permitir.
- Q: Quais requisitos mínimos de observabilidade para o deploy no Railway? → A: Endpoint de health check HTTP (`GET /v1/health`) + logs estruturados em JSON com níveis INFO/WARNING/ERROR.

## Cenários de Usuário e Testes *(obrigatório)*

<!--
  Jornadas ordenadas por prioridade de negócio/pesquisa. Cada jornada é
  independentemente testável e entregável como incremento de valor.
-->

### Jornada 1 — Pesquisador Gera a Massa de Dados de Treinamento (Prioridade: P1)

O pesquisador precisa produzir um dataset rotulado com dezenas de milhares de
estados do Jogo dos Pontinhos, cada um acompanhado da jogada ótima calculada pelo
algoritmo Oráculo (Minimax com Poda Alpha-Beta). Esse dataset é a matéria-prima
para o treinamento da rede neural convolucional (CNN).

**Por que esta prioridade**: É o pré-requisito absoluto de todo o projeto de TCC.
Sem o dataset, nenhum modelo pode ser treinado; sem o modelo, a prova de viabilidade
da Edge AI não ocorre.

**Teste Independente**: Totalmente testável executando o script gerador e
verificando que os arquivos de saída existem, contêm o número esperado de registros
e que os rótulos são traços válidos para cada estado de tabuleiro gerado.

**Cenários de Aceite**:

1. **Dado** que o pesquisador executa o gerador para o tabuleiro Pequeno (3×4 quadrados),
   **Quando** a execução conclui normalmente,
   **Então** existem 50.000 pares válidos (matriz de estado + rótulo do traço ótimo)
   persistidos no armazenamento de saída, sem registros duplicados ou corrompidos.

2. **Dado** que o pesquisador executa o gerador para o tabuleiro Médio (4×5),
   **Quando** a execução conclui,
   **Então** 50.000 pares válidos são gerados e o tempo total de execução é
   informado ao final do processo.

3. **Dado** que o pesquisador executa o gerador para o tabuleiro Grande (5×7),
   **Quando** o Minimax atinge o limite de profundidade configurado,
   **Então** o script aplica a limitação automaticamente e finaliza sem travar,
   gerando 50.000 pares com rótulos derivados da profundidade limitada.

4. **Dado** que o script é interrompido no meio da execução,
   **Quando** é reiniciado,
   **Então** retoma a partir do último checkpoint salvo, sem reprocessar registros
   já calculados.

---

### Jornada 2 — Pesquisador Inspeciona Visualmente as Matrizes Geradas (Prioridade: P1)

O pesquisador precisa confirmar que a representação matricial dos estados está
correta antes de treinar o modelo. Ele converte uma ou mais matrizes em imagens
estáticas para inspeção visual.

**Por que esta prioridade**: Um erro na codificação das matrizes corromperia todo
o dataset. A validação visual é a defesa mais rápida e barata contra esse risco.

**Teste Independente**: Totalmente testável fornecendo matrizes de estado conhecidas
(construídas manualmente) e comparando as imagens geradas com o resultado esperado.

**Cenários de Aceite**:

1. **Dado** uma matriz de estado de tabuleiro válida (arquivo `.npy` ou lista em
   memória),
   **Quando** a função de abstração visual é acionada,
   **Então** é gerada uma imagem onde: traços do Jogador 1 aparecem em azul,
   traços do Jogador 2 aparecem em vermelho, pontos de grade são pretos e espaços
   livres são brancos — com cada célula da matriz claramente distinguível.

2. **Dado** um lote de múltiplas matrizes,
   **Quando** a função é chamada em modo lote com um diretório de saída especificado,
   **Então** uma imagem é gerada para cada matriz no diretório indicado, com nome
   de arquivo correspondente ao índice ou identificador de cada estado.

---

### Jornada 3 — Pesquisador Valida a CNN Jogando contra ela (Prioridade: P1)

Após o primeiro treinamento da CNN, o pesquisador precisa jogar manualmente contra
o modelo para verificar empiricamente se ele aprendeu as estratégias corretas:
priorizar o fechamento de caixas e bloquear o adversário.

**Por que esta prioridade**: É o Critério de Aceite (Go/No-Go) do TCC. O
desenvolvimento do app mobile só se inicia após aprovação nesta etapa.

**Teste Independente**: Totalmente funcional como uma partida completa do Jogo dos
Pontinhos contra a CNN, sem dependências além do arquivo de modelo exportado.

**Cenários de Aceite**:

1. **Dado** um modelo exportado carregado no simulador,
   **Quando** o pesquisador realiza um traço na interface,
   **Então** o simulador exibe a jogada escolhida pela CNN e o estado atualizado
   do tabuleiro em menos de 1 segundo para o tabuleiro Pequeno.

2. **Dado** que a CNN está em seu turno e existe uma caixa com 3 lados já
   desenhados (oportunidade óbvia de fechamento),
   **Quando** a CNN decide sua jogada,
   **Então** ela fecha a caixa em pelo menos 90% dessas situações ao longo de
   uma sessão de 10 partidas completas.

3. **Dado** que a partida termina com todos os traços preenchidos,
   **Quando** o placar final é calculado,
   **Então** o simulador exibe o número de caixas de cada jogador e declara
   o vencedor corretamente.

4. **Dado** que o pesquisador deseja comparar eficiência,
   **Quando** alterna entre o modo CNN e o modo Minimax como oponente,
   **Então** o simulador exibe o tempo de decisão em milissegundos após cada
   jogada da IA, permitindo comparação direta.

---

### Jornada 4 — App Mobile Sincroniza Partidas Concluídas (Prioridade: P2)

Após uma partida contra a CPU, o app do jogador envia os dados da partida ao
backend para atualização de pontuação, XP e ranking global.

**Por que esta prioridade**: Essencial para a camada competitiva do produto final,
mas não bloqueia a validação do motor de IA.

**Teste Independente**: Testável simulando requisições de sincronização via cliente
HTTP e verificando consistência dos dados persistidos no banco.

**Cenários de Aceite**:

1. **Dado** que o app de um jogador autenticado envia os dados de uma partida
   concluída contra a CPU,
   **Quando** o backend recebe a requisição,
   **Então** persiste a partida, atualiza o XP e a pontuação do jogador e retorna
   confirmação com os valores atualizados.

2. **Dado** que o app solicita o ranking global,
   **Quando** o backend processa a requisição,
   **Então** retorna a lista dos top-100 jogadores com apelido, pontuação e nível,
   ordenada de forma decrescente por pontuação.

3. **Dado** que o token de autenticação do jogador está expirado,
   **Quando** o app tenta sincronizar uma partida,
   **Então** o backend retorna resposta de não autorizado e o app é notificado
   para solicitar novo login.

---

### Jornada 5 — Jogador Cria Conta e Realiza Login (Prioridade: P2)

O jogador precisa criar uma conta para acumular XP e aparecer no ranking.

**Por que esta prioridade**: Pré-requisito para sincronização de partidas; pode
ser desenvolvido em paralelo com a Fase Zero.

**Teste Independente**: Fluxo de criação e autenticação de conta completamente
testável de forma isolada.

**Cenários de Aceite**:

1. **Dado** que um novo usuário fornece e-mail, apelido e senha que atendem às
   regras de validação,
   **Quando** solicita a criação de conta,
   **Então** a conta é criada, um e-mail de verificação é disparado e um token
   de acesso temporário é retornado.

2. **Dado** que um usuário existente fornece credenciais corretas,
   **Quando** solicita login,
   **Então** recebe um token de acesso válido com prazo de expiração definido.

3. **Dado** que alguém tenta criar uma conta com e-mail já cadastrado,
   **Quando** a solicitação é processada,
   **Então** recebe mensagem de erro indicando conflito de e-mail, sem expor
   dados da conta existente.

---

### Casos de Borda

- O que acontece quando o Minimax excede o tempo máximo de cálculo para um
  estado do tabuleiro Grande durante a geração?
- Como o simulador se comporta se o arquivo do modelo exportado está ausente
  ou corrompido ao iniciar?
- O que acontece se dois usuários tentam criar conta com o mesmo apelido
  simultaneamente?
- Como a API se comporta quando o banco de dados está temporariamente
  indisponível?
- O que acontece se o gerador tentar criar um traço em posição já preenchida?

## Requisitos *(obrigatório)*

### Requisitos Funcionais

**[RF — Gerador de Massa de Dados]**

- **RF-001**: O sistema DEVE gerar estados aleatórios válidos do Jogo dos Pontinhos
  para os três tamanhos definidos: Pequeno (3×4 quadrados), Médio (4×5) e
  Grande (5×7).
- **RF-002**: O sistema DEVE representar cada estado como matriz numérica
  bidimensional de dimensões `(2×Largura+1) × (2×Altura+1)`, com valores
  `8` (ponto fixo da grade), `0` (vazio), `9` (traço/aresta preenchido por
  qualquer jogador), `1` (caixa fechada pelo Jogador 1) e `-1` (caixa fechada
  pelo Jogador 2). Antes de alimentar a CNN, normalizar: `8 → 0`, `9 → 1`.
- **RF-003**: O sistema DEVE aplicar o algoritmo Minimax com Poda Alpha-Beta para
  determinar a jogada ótima a partir de cada estado gerado.
- **RF-004**: O sistema DEVE permitir configuração do limite máximo de profundidade
  do Minimax via parâmetro de execução. O valor padrão inicial é 7 para todos os
  tamanhos de tabuleiro; esse valor DEVE ser facilmente ajustável sem alteração
  de código, permitindo aumentos incrementais conforme a performance de geração
  observada na prática.
- **RF-005**: O sistema DEVE salvar os pares (estado, rótulo do traço ótimo) em
  formato binário compacto, com suporte a retomada a partir de checkpoint.
- **RF-006**: O sistema DEVE gerar no mínimo 50.000 registros por tamanho de
  tabuleiro, com rótulos no formato `H_linha_coluna` (traço horizontal) ou
  `V_linha_coluna` (traço vertical).
- **RF-007**: O sistema DEVE registrar logs de progresso durante a geração,
  informando quantidade de registros gerados, tempo decorrido e estimativa
  de conclusão.

**[RF — Abstração Visual]**

- **RF-008**: O sistema DEVE converter qualquer matriz de estado numérica válida
  em imagem estática, respeitando a legenda de cores definida no PRD.
- **RF-009**: O sistema DEVE aceitar tanto um único estado quanto um lote,
  gerando imagens individuais ou em diretório de saída configurável.

**[RF — Simulador Tático]**

- **RF-010**: O sistema DEVE permitir que o pesquisador realize uma partida completa
  do Jogo dos Pontinhos contra o modelo de IA carregado.
- **RF-011**: O sistema DEVE exibir o estado atualizado do tabuleiro após cada
  jogada, com distinção visual clara entre caixas fechadas por cada jogador.
- **RF-012**: O sistema DEVE registrar e exibir o tempo de decisão da IA em
  milissegundos após cada turno computacional.
- **RF-013**: O sistema DEVE oferecer modo de comparação, permitindo alternar
  entre a CNN e o Minimax como oponente durante a mesma sessão.
- **RF-014**: O sistema DEVE exibir o placar final e o vencedor ao término
  de cada partida.
- **RF-015**: O sistema DEVE validar que o arquivo de modelo exportado existe
  e está íntegro ao iniciar, emitindo mensagem de erro descritiva caso contrário.

**[RF — API e Autenticação]**

- **RF-016**: O sistema DEVE oferecer endpoint de criação de conta com validação
  de unicidade de e-mail e apelido. Todos os endpoints públicos e protegidos
  DEVEM ser acessíveis sob o prefixo `/v1/` (ex: `POST /v1/usuarios`,
  `POST /v1/auth/login`, `GET /v1/ranking`).
- **RF-017**: O sistema DEVE oferecer endpoint de autenticação que retorne
  um JWT de acesso (validade padrão: 1 hora) e um refresh token opaco de
  longa duração (validade padrão: 30 dias), ambos com prazo configurável
  via variável de ambiente.
- **RF-017a**: O sistema DEVE oferecer endpoint de renovação de token que,
  mediante refresh token válido, emita novo JWT de acesso sem exigir nova
  autenticação do usuário.
- **RF-018**: O sistema DEVE validar o JWT em todos os endpoints protegidos,
  retornando resposta padronizada de não autorizado (401) quando o token
  estiver ausente, inválido ou expirado.
- **RF-019**: O sistema DEVE oferecer endpoint de sincronização de partida
  concluída, calculando e persistindo: XP = (caixas fechadas pelo jogador × 1)
  + bônus de vitória (valor fixo configurável) + multiplicador de dificuldade
  (Fácil × 1, Normal × 1,5, Sagaz × 2), atualizando a pontuação total e o
  nível do jogador.
- **RF-020**: O sistema DEVE oferecer endpoint de ranking retornando os top-100
  jogadores com paginação.

**[RF — Banco de Dados]**

- **RF-021**: O sistema DEVE persistir: usuários, partidas, entradas de ranking
  e troféus/selos.
- **RF-022**: O sistema DEVE carregar os dados iniciais de troféus e selos a
  partir de scripts SQL de carga inicial.
- **RF-023**: O sistema DEVE garantir integridade referencial entre partidas e
  usuários participantes.
- **RF-024**: O sistema DEVE expor endpoint público de health check
  (`GET /v1/health`) que retorne status de disponibilidade da API e do banco
  de dados, para uso pelo Railway no gerenciamento do ciclo de vida do contêiner.
- **RF-025**: Toda operação relevante (requisição recebida, erro de negócio,
  falha de banco, início/fim de geração de dataset) DEVE gerar log estruturado
  em formato JSON com campos: timestamp, nível (INFO/WARNING/ERROR), módulo
  de origem e mensagem descritiva em pt-BR.

### Entidades-Chave

- **EstadoTabuleiro**: Estado instantâneo de jogo — matriz numérica, dimensões
  do tabuleiro, mapeamento dos traços desenhados e caixas fechadas com respectivos
  proprietários.
- **RegistroTreinamento**: Par (EstadoTabuleiro, rótulo do traço ótimo) calculado
  pelo Oráculo Minimax, destinado ao treinamento da CNN.
- **Usuário**: Conta do jogador — identificador único, apelido, e-mail, senha
  protegida, nível, XP acumulado, data de cadastro.
- **Partida**: Registro de partida concluída — jogadores envolvidos, tamanho do
  tabuleiro, modo de jogo (vs CPU / vs Humano), nível de dificuldade, caixas
  fechadas por cada jogador, resultado (vitória/derrota/empate), XP calculado,
  data e hora.
- **EntradaRanking**: Posição de um usuário no ranking — referência ao Usuário,
  pontuação total, posição calculada.
- **Troféu/Selo**: Conquista desbloqueável — identificador, nome, descrição,
  critério de desbloqueio.

## Critérios de Sucesso *(obrigatório)*

### Resultados Mensuráveis

- **CS-001**: O gerador produz 50.000 registros válidos para cada um dos três
  tamanhos de tabuleiro sem nenhum registro duplicado ou com rótulo inválido.
- **CS-002**: O dataset do tabuleiro Pequeno (3×4) é gerado em menos de 24 horas
  em hardware de desenvolvimento convencional sem GPU dedicada.
- **CS-003**: O modelo treinado fecha caixas óbvias (3 lados preenchidos) em
  pelo menos 90% das oportunidades durante partidas no simulador, medido em
  sessão de 10 partidas completas no tabuleiro Pequeno.
- **CS-004**: O tempo de decisão do modelo é pelo menos 10 vezes menor que o
  do Minimax de profundidade 5 para o mesmo estado de tabuleiro, medido no
  simulador.
- **CS-005**: O arquivo de modelo exportado é menor que 50 MB por tamanho de
  tabuleiro, viabilizando embutimento no app mobile.
- **CS-006**: Os endpoints da API suportam 500 requisições simultâneas de
  sincronização de partidas sem perda de dados ou erros de integridade.
- **CS-007**: O processo de criação de conta e primeiro login é concluído em
  menos de 30 segundos em condições normais de rede.

## Premissas

- A geração do dataset ocorre em ambiente local de desenvolvimento; não há
  dependência de GPU durante a geração (somente CPU).
- O treinamento da CNN ocorre externamente ao backend (em notebooks/scripts
  locais); o backend e o simulador consomem o modelo pronto, não realizam
  treinamento.
- O backend será implantado na plataforma Railway (PaaS), que fornece
  gerenciamento automático de contêineres e banco de dados gerenciado.
- O app mobile acessará o backend via HTTPS; o simulador tático é uma
  ferramenta de laboratório executada estritamente de forma local.
- Multiplayer online (P2P/Firebase) está fora do escopo desta especificação.
- A interface do simulador tático é propositalmente rudimentar — seu único
  propósito é validar a IA, não proporcionar experiência visual refinada.
- Partidas entre dois jogadores no mesmo dispositivo não geram dados de ranking
  (o segundo jogador entra como convidado local, conforme PRD).
- Os dados iniciais de troféus e selos são carregados via scripts SQL na pasta
  `sql/` do repositório.
- Comunicação entre jogadores humanos via sistema de emotes (online) está
  fora do escopo do backend nesta fase.
- As personas e frases de provocação da CPU são gerenciadas localmente pelo
  app mobile e estão fora do escopo do backend.
