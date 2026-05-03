# Feature Specification: Agente Jogador Híbrido `ia-pontinhos-3-4`

**Feature Branch**: `003-jogador-hibrido`
**Created**: 2026-04-30
**Status**: Draft
**Input**: Algoritmo híbrido CNN + Minimax para Dots-and-Boxes em tabuleiro 3x4 caixas. Pipeline de 4 passos por turno: (1) Captura Segura e Gulosa, (2) Exceção do Sacrifício / Double-Dealing, (3) Fase Tática via Rede Neural Convolucional, (4) Validação Final via Minimax com poda. Modelo: `modelos/pontinhos_pequeno_profundidade_9.tflite` ou outro modelo passado como parâmetro.

---

## Visão Geral

A `ia-pontinhos-3-4` é o agente computacional que joga **Dots-and-Boxes (Pontinhos)** no formato fixo **3 caixas de largura × 4 caixas de altura** (12 caixas, 31 arestas), parte do hub de jogos **Arena Sagaz**.

A arquitetura é deliberadamente **híbrida**: combina conhecimento simbólico de teoria dos jogos (regras de captura, detecção de correntes e ciclos, sacrifício double-dealing), inferência neural por **CNN treinada (TFLite)** sobre o estado do tabuleiro, e **busca clássica Minimax** com poda alpha-beta. Cada componente cobre uma deficiência do outro: a CNN é rápida e portável (importante para o frontend Flutter via TFLite), o Minimax fornece garantias táticas onde a profundidade simbólica é decisiva, e o blindado simbólico (Passos 1 e 2) impede que a CNN "perca" capturas triviais ou ceda controle de correntes longas.

A justificativa estratégica e os trade-offs estão consolidados em `docs/argumentacao_cnn_vs_minimax.md` (referência da memória do projeto).

---

## Modos de Operação e Adversários

A `ia-pontinhos-3-4` é projetada para atuar como **um jogador** entre múltiplos possíveis adversários no hub Arena Sagaz. Os cenários de adversário previstos são:

- **Humano** — usuário do app Arena Sagaz jogando via interface Flutter.
- **Outra IA** — agentes que usam apenas a CNN (sem Minimax / sem proteções simbólicas) para experimentos comparativos.
- **Robô (Minimax puro)** — agentes que executam apenas Minimax (sem CNN) com profundidade configurável, usados como baseline e em testes de regressão (cf. SC-006).
- **Ela mesma (auto-jogo)** — agente vs agente, para geração de telemetria e testes de integração (cf. User Story 5 / SC-003).

A `ia-pontinhos-3-4` **não distingue** o tipo de adversário em sua lógica interna — apenas joga seu turno conforme o estado recebido. A alternância de turnos e a coleta da jogada do oponente são responsabilidade da camada de partida (fora desta feature).

### Níveis de Dificuldade

A `ia-pontinhos-3-4` DEVE oferecer **4 níveis de dificuldade** ajustáveis em runtime: `facil`, `medio`, `dificil`, `expert`. Cada nível mapeia para uma combinação distinta de:

- **Modelo CNN** — caminho do arquivo `.tflite`.
- **Profundidade Minimax** — inteiro ≥ 1.
- **Percentual de aleatoriedade** — probabilidade [0.0, 1.0] de o agente escolher aleatoriamente uma aresta da TOP-5 em vez da indicada pelo Minimax (introduzido para tornar o agente menos previsível em níveis baixos e dar chance de vitória ao adversário).

#### Mapeamento canônico

| Nível | Modelo CNN | Profundidade Minimax | Aleatoriedade |
|-------|------------|----------------------|---------------|
| `facil` | `modelos/pontinhos_pequeno_profundidade_6.tflite` | `1` | `0.30` (30%) |
| `medio` | `modelos/pontinhos_pequeno_profundidade_7.tflite` | `2` | `0.15` (15%) |
| `dificil` | `modelos/pontinhos_pequeno_profundidade_9.tflite` | `3` | `0.05` (5%) |
| `expert` | `modelos/pontinhos_pequeno_profundidade_11.tflite` *(modelo a ser treinado — bloqueia disponibilidade prática do nível expert)* | `3` | `0.00` (determinístico) |

**Notas:**
- O `expert` mantém depth=3 (não 5) para preservar p95 < 1000 ms em hardware-alvo (ver SC-005), inclusive com vistas a portabilidade futura para mobile. A maior força do `expert` vem do modelo CNN mais profundo (`profundidade_11`) — que captura padrões mais sutis — combinado com **ausência total de aleatoriedade**.
- `profundidade_11.tflite` ainda **não existe** nesta data; a disponibilidade do nível `expert` está condicionada à conclusão do treinamento desse modelo (out-of-scope desta feature). Antes disso, a `ia-pontinhos-3-4` configurada como `expert` DEVE falhar com erro duro (consistente com FR sobre falha do TFLite).
- A aleatoriedade nos 3 primeiros níveis introduz não-determinismo controlado — ver qualificação em FR-024 e SC-004.

---

## Glossário Específico do Domínio

Ancorar a terminologia antes das User Stories evita ambiguidade nas Acceptance Scenarios e nos Functional Requirements.

- **Caixa**: célula unitária do tabuleiro 3x4 (12 caixas no total).
- **Aresta**: segmento entre dois pontos da grade (31 arestas no total: **15 horizontais + 16 verticais** para o tabuleiro 3x4 — 3 caixas de largura × 4 caixas de altura).
- **Adversário**: contraparte da `ia-pontinhos-3-4` em uma partida. Pode ser: humano (via UI), outra IA (ex.: CNN pura sem Minimax), robô (Minimax puro sem CNN), ou outra instância da própria `ia-pontinhos-3-4` (auto-jogo).
- **Nível de Dificuldade**: configuração externa do agente que mapeia para uma combinação `(modelo_cnn, profundidade_minimax)`. Valores: `facil`, `medio`, `dificil`, `expert`.
- **co_situacao**: código (string) que identifica a situação de decisão que originou a jogada. Valores: `captura_segura`, `final_corrente_longa`, `final_ciclo`, `tatica`.
- **co_acao**: código (string) que identifica a ação/estratégia executada. Valores: `captura_gulosa`, `captura_completa`, `sacrificio_double_cross`, `cnn_e_minimax`, `cnn_timeout`, `aleatoria_timeout`. Os dois últimos são acionados quando `nu_timer_ms` força a degradação graciosa antes que a jogada ideal (Prioridade 1) seja calculada — ver FR-047.
- **co_aresta**: representação textual da aresta no formato `<TIPO>_<dim1>_<dim2>` (ex.: `H_0_1`, `V_2_3`), onde `<TIPO> ∈ {H, V}` conforme contrato JSON.
- **nu_timer_ms**: tempo máximo (inteiro, em milissegundos) permitido para a `ia-pontinhos-3-4` retornar a *jogada ideal* (Prioridade 1). Recebido como input via `MetadadosTurno`. Quando `None` ou `0`, timeout está desabilitado e o agente se comporta como nas versões anteriores (sem limite). Ver FR-043.
- **nu_tempo_calculo_ms**: tempo (inteiro, em milissegundos) efetivamente gasto desde o acionamento de `escolher_jogada(...)` até a saída finalmente retornada. Sempre presente no `ResultadoJogada` — útil para telemetria mesmo quando `nu_timer_ms` não foi configurado. Ver FR-044, FR-049.
- **Prioridade 1 / Prioridade 2 / Prioridade 3**: hierarquia das três respostas candidatas mantidas pelo agente quando há controle de tempo. P1 = jogada ideal (pipeline completo); P2 = argmax da CNN sobre arestas livres (sem Minimax, somente em fase tática); P3 = aresta livre uniformemente aleatória, preparada imediatamente no acionamento (piso garantido). Ver FR-045.
- **ResultadoJogada**: objeto retornado por `escolher_jogada(...)`, contendo a aresta escolhida + telemetria de decisão (ver User Story 5 e Key Entities).
- **Grau de uma caixa**: número de arestas adjacentes já preenchidas (0 a 4). Caixa de **grau 3** está pronta para ser capturada (basta preencher a 4ª aresta).
- **Dono de uma caixa**: jogador (J1 ou J2) que preencheu a 4ª aresta. Caixas de grau < 4 não têm dono.
- **Captura**: ato de preencher a 4ª aresta de uma caixa grau-3, atribuindo a caixa ao jogador ativo. Concede **turno extra** ao mesmo jogador (regra do jogo).
- **Corrente (chain)**: caminho **aberto** formado por caixas conectadas via arestas livres compartilhadas, em que cada caixa tem grau 2. Tamanho = número de caixas no caminho.
- **Corrente longa**: corrente com **≥ 3 caixas**. Corrente curta (1 ou 2 caixas) não satisfaz a precondição do double-dealing.
- **Ciclo (anel, cycle)**: caminho **fechado** (loop) de caixas grau-2 conectadas. Em tabuleiro 3x4, os tamanhos possíveis são 4, 6, 8 ou 10.
- **Double-dealing (double-cross, sacrifício)**: jogada que entrega ao adversário as 2 últimas caixas de uma corrente longa (ou as 4 últimas de um ciclo) sem pontuar, forçando o adversário a capturá-las e abrir a próxima estrutura. Estratégia central de **controle de paridade**.
- **Fase tática**: estado do tabuleiro em que **nenhuma caixa tem grau 3**. Decisão é guiada por CNN + Minimax (Passos 3 e 4).
- **TOP-5**: as cinco arestas livres com maior probabilidade na saída da CNN.
- **Estado**: snapshot completo do jogo (configuração das 31 arestas, donos das 12 caixas, jogador da vez, scores parciais).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Captura Segura e Gulosa (Priority: P1)

Sempre que o tabuleiro tiver uma ou mais caixas de **grau 3**, a `ia-pontinhos-3-4` DEVE preencher a aresta que fecha uma delas, capturando a caixa. Em chamadas subsequentes (em que o turno permanece com a `ia-pontinhos-3-4` por força da regra de turno extra), o agente DEVE continuar capturando todas as caixas grau-3 que se sucedem em sequência (chain capture), **a não ser que** seja detectada a Exceção do Passo 2 (User Story 2).

**Why this priority**: Sem captura gulosa, o agente perde pontos triviais e é não-competitivo. É o piso absoluto de comportamento esperado — qualquer jogador iniciante humano realiza esse passo. Tudo o mais (CNN, Minimax) é refinamento sobre essa base.

**Independent Test**: Carregar tabuleiros sintéticos com 1 ou mais caixas grau-3 isoladas (não pertencentes a corrente longa nem ciclo terminando); chamar `ia_pontinhos.escolher_jogada(estado)`; verificar que a aresta retornada fecha uma das caixas grau-3 e que o estado sucessor contabiliza a captura.

**Acceptance Scenarios**:

1. **Given** tabuleiro com 1 caixa grau-3 isolada (sem que pertença a corrente longa nem ciclo terminando), **When** o agente é invocado, **Then** retorna a aresta que fecha aquela caixa.
2. **Given** chain capture em curso — corrente curta (2 caixas) com a primeira já em grau 3, **When** o agente joga e em seguida é invocado novamente (após a captura), **Then** as duas chamadas resultam em arestas de captura, encerrando a corrente.
3. **Given** múltiplas caixas grau-3 não conectadas (capturas independentes), **When** o agente joga, **Then** captura uma delas (qualquer, mas determinística para o mesmo estado), e em chamadas subsequentes captura as restantes.
4. **Given** tabuleiro com caixas grau-3 que não estão em corrente longa nem em ciclo, **When** o agente joga, **Then** NÃO ativa a Exceção do Passo 2 e captura normalmente.

---

### User Story 2 — Exceção do Sacrifício / Double-Dealing (Priority: P1)

Durante a captura gulosa do User Story 1, o agente DEVE **interromper imediatamente** o processo se as **únicas caixas grau-3 disponíveis** representarem **exatamente uma das duas situações abaixo**:

- **(a)** As **2 últimas caixas** de uma **corrente longa** (≥ 3 caixas no total).
- **(b)** As **4 últimas caixas** de um **ciclo** (de qualquer tamanho).

Nesse cenário, o agente é forçado a escolher entre apenas duas opções táticas válidas:

- **Opção A** — *Captura completa*: preencher as arestas que capturam todas as caixas restantes da estrutura. Implica capturar todos os pontos restantes, mas **perder o controle do turno** (a próxima jogada do agente, fora da estrutura, abrirá outra estrutura para o adversário).
- **Opção B** — *Sacrifício (double-cross)*: preencher a **aresta interna que NÃO pontua** — a aresta que conecta as duas caixas que ainda não estão em grau 3 dentro da estrutura, fazendo com que ambas saltem de grau 2 para grau 3 simultaneamente, oferecidas ao adversário. O adversário é forçado a capturar (2 caixas no caso de corrente, 4 no caso de ciclo) e em seguida **abrir a próxima estrutura** para o agente.

A decisão entre A e B DEVE ser feita gerando os dois estados sucessores e submetendo cada um ao **Minimax com profundidade fixa p = 3**. O agente executa a opção cujo estado sucessor retornou o **maior score** Minimax.

**Why this priority**: Double-dealing é o conceito mais importante de teoria de jogos em Dots-and-Boxes (cf. Berlekamp, *Winning Ways*). Sem ele, o agente sempre engole correntes longas e cede o controle do tabuleiro em fases avançadas, comportando-se como amador. Distinguir Passo 1 de Passo 2 é o que separa um jogador funcional de um jogador forte. P1 (não P2) porque Passo 2 só faz sentido se Passo 1 existe; e a falha aqui mascara qualquer ganho da CNN.

**Independent Test**: Construir tabuleiros canônicos onde existe uma corrente longa (e/ou ciclo) com as duas (ou quatro) últimas caixas em grau-3, e onde Minimax depth=3 indica claramente que B (sacrifício) supera A (captura completa). Chamar o agente; verificar que retorna a aresta de double-cross, não a aresta de captura.

**Acceptance Scenarios**:

1. **Given** corrente longa de 5 caixas, com as 2 últimas em grau 3 e as 3 anteriores em grau 2, em uma posição em que sacrificar leva à vitória pelo controle de paridade, **When** o agente joga, **Then** retorna a aresta de double-cross (jogada que NÃO captura; deixa as duas caixas oferecidas ao adversário).
2. **Given** ciclo de 6 caixas com as 4 últimas em grau 3 e as 2 restantes em grau 2, **When** o agente joga, **Then** consulta Minimax depth=3 sobre os dois estados sucessores e executa a opção (A ou B) com maior score.
3. **Given** corrente curta de 2 caixas (não é "longa", regra `≥ 3`), **When** o agente joga, **Then** **NÃO** aplica double-dealing — captura ambas conforme Passo 1.
4. **Given** 2 caixas grau-3 isoladas (não pertencem a uma única corrente longa nem ciclo), **When** o agente joga, **Then** **NÃO** aplica double-dealing — captura conforme Passo 1.
5. **Given** Minimax depth=3 retorna mesmo score para A e B, **When** o agente decide, **Then** prefere B (sacrifício) — controle de paridade é estratégia long-term e este é o tie-breaker definido.

---

### User Story 3 — Fase Tática via CNN (Priority: P2)

Quando o tabuleiro **não possui nenhuma caixa de grau 3** (i.e., os Passos 1 e 2 são inaplicáveis), o jogo está em fase tática. A `ia-pontinhos-3-4` DEVE:

1. Codificar o estado atual em matriz conforme o **contrato `gerador_dados/contrato_codificacao_pontinhos.json`**, contexto **"Partidas / uso interativo"**.
2. Aplicar a normalização do contrato (`8 → 0`, `-1 → 1`, `9 → 1`) **imediatamente antes** de `interp.set_tensor()`.
3. Submeter o tensor à CNN `modelos/pontinhos_pequeno_profundidade_9.tflite` ou outro modelo passado como parâmetro.
4. Extrair a **distribuição de probabilidade** sobre as 31 arestas.
5. **Filtrar** arestas já preenchidas.
6. Selecionar as **TOP-5 arestas livres** com maiores probabilidades.

**Why this priority**: A CNN é o cérebro tático do agente — é o que confere "intuição" para fases iniciais e médias do jogo, onde o branching factor é grande demais para Minimax puro com profundidade adequada, e onde regras simbólicas têm pouca aplicabilidade (não há ainda capturas pendentes nem estruturas formadas). A portabilidade da CNN via TFLite também é o que viabiliza rodar o agente no app Flutter sem reescrever o algoritmo.

**Independent Test**: Mockar uma chamada de CNN sobre tabuleiro vazio (jogada inicial); verificar que a função retorna 5 arestas distintas, todas livres, ordenadas por probabilidade descendente. Verificar (com assertion) que a normalização foi aplicada antes de `set_tensor`.

**Acceptance Scenarios**:

1. **Given** tabuleiro vazio (31 arestas livres, 0 caixas grau-3), **When** a fase tática é acionada, **Then** a CNN é invocada, e a função retorna 5 arestas distintas, todas livres, ordenadas por probabilidade descendente.
2. **Given** tabuleiro mid-game com 12 arestas preenchidas e nenhuma caixa grau-3, **When** o agente joga, **Then** retorna 5 arestas livres distintas.
3. **Given** o contrato JSON especifica normalização `8→0, -1→1, 9→1` antes de `interp.set_tensor()`, **When** o tensor é entregue ao modelo, **Then** todos os valores estão em `{0, 1}`.
4. **Given** tabuleiro avançado em que restam apenas 4 arestas livres, **When** a CNN é consultada, **Then** o agente retorna as 4 (não pode haver 5 — degrade gracioso).
5. **Given** a saída crua da CNN inclui probabilidades para arestas já preenchidas, **When** a filtragem é aplicada, **Then** essas arestas são excluídas do TOP-5.

---

### User Story 4 — Validação Final via Minimax com Poda (Priority: P2)

Para cada estado em fase tática, depois de obter o TOP-5 da CNN (User Story 3), a `ia-pontinhos-3-4` DEVE executar **Minimax com poda alpha-beta** com **profundidade fixa p = 3**, considerando **apenas os ramos que partem das 5 arestas TOP-5**. O restante do tabuleiro é ignorado na raiz da busca (mas considerado em níveis subsequentes — a poda só restringe o branching factor inicial).

A jogada finalmente executada é a aresta cuja sub-árvore retorna o **maior score Minimax**.

**Why this priority**: O Minimax sobre TOP-5 é o "veto tático" que protege contra erros pontuais da CNN — uma probabilidade alta na CNN não garante que a jogada não ofereça caixas para o adversário no horizonte de 3 plies. Ao reduzir o branching factor de 31 para 5 na raiz, depth=3 com alpha-beta executa em milissegundos, viabilizando o acoplamento.

**Independent Test**: Mockar a CNN para retornar 5 arestas conhecidas; configurar tabuleiro onde uma das 5 leva o adversário a capturar caixa no ply seguinte (score baixo) e outra é neutra (score alto); chamar o agente; verificar que retorna a aresta neutra.

**Acceptance Scenarios**:

1. **Given** TOP-5 onde uma aresta cria caixa grau-3 para o adversário no ply seguinte e outra é neutra, **When** Minimax depth=3 é executado, **Then** o agente retorna a aresta neutra (score Minimax maior).
2. **Given** TOP-5 com duas arestas empatadas em score Minimax, **When** o desempate é aplicado, **Then** a primeira na ordem da CNN (maior probabilidade) é escolhida.
3. **Given** TOP-5 e tempo medido fim-a-fim (CNN + filtragem + Minimax), **When** o agente executa em hardware-alvo, **Then** o tempo total da jogada é < 1000 ms (ver SC-005).
4. **Given** Minimax internamente atravessa um ramo onde o oponente faz captura e ganha turno extra, **When** a alternância min/max é resolvida, **Then** a regra de turno extra é respeitada (não alterna se houve captura).

---

### User Story 5 — Saída Estruturada (`ResultadoJogada`) e Integração End-to-End (Priority: P3)

A `ia-pontinhos-3-4` DEVE ser invocável de modo **stateless**, com assinatura aproximada `escolher_jogada(estado: Tabuleiro, configuracao: ConfiguracaoAgente, metadados: MetadadosTurno) -> ResultadoJogada`. **O retorno NÃO é uma `Aresta` simples** — é um objeto rico (`ResultadoJogada`) contendo a aresta escolhida **mais** telemetria de decisão suficiente para persistência futura na tabela `jogo_pontinhos.tb002_jogada` (banco local do app, com sincronização periódica para o servidor — ver Out of Scope).

Os 3 UUIDs e o `ts_jogada` que aparecem nos campos comuns são **fornecidos pela camada de partida** (avaliador, simulador, App Flutter) via `metadados` e simplesmente ecoados pela IA no `ResultadoJogada`. A IA não gera nem valida esses identificadores.

A persistência em banco e a sincronização **não fazem parte desta feature**; esta especificação garante apenas que a função produz os dados estruturados necessários para essa persistência.

#### Campos comuns ao `ResultadoJogada` (sempre presentes)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id_partida` | UUID | Identificador da partida em curso. |
| `id_jogada` | UUID | Identificador único desta jogada dentro da partida. |
| `id_jogador` | UUID | Identificador do jogador (instância da IA) que fez a jogada. |
| `nu_jogador` | int (`1` ou `-1`) | Convenção de jogador no tabuleiro. |
| `co_situacao` | string (enum) | Código da situação que originou a decisão. Ver Glossário. |
| `co_acao` | string (enum) | Código da ação/estratégia executada. Ver Glossário. |
| `co_aresta` | string | Aresta escolhida no formato `<TIPO>_<dim1>_<dim2>` (ex.: `H_0_1`). |
| `ar_tabuleiro_antes` | numpy.ndarray | Estado do tabuleiro **sem normalização** ANTES da jogada. |
| `ar_tabuleiro_apos` | numpy.ndarray | Estado do tabuleiro **sem normalização** APÓS a jogada. |
| `nu_placar_jogador_antes` | int | Placar do jogador (`id_jogador`) ANTES da jogada. |
| `nu_placar_jogador_apos` | int | Placar do jogador APÓS a jogada. |
| `ts_jogada` | timestamp ISO 8601 c/ tz | Momento da jogada, no fuso horário do `id_jogador`. |
| `nu_timer_ms` | int \| None | **Eco** do tempo máximo permitido (ms) para retornar a jogada ideal — recebido em `MetadadosTurno`. `None` ou `0` indica timeout desabilitado. |
| `nu_tempo_calculo_ms` | int | Tempo efetivamente gasto (ms) desde o acionamento de `escolher_jogada(...)` até a saída retornada. Sempre presente. |

#### Campos opcionais (presentes conforme o passo originador)

| Campo | Tipo | Quando é preenchido |
|-------|------|---------------------|
| `nu_profundidade_minimax` | int | US2 e US3+US4 (sempre que Minimax é executado). |
| `ar_score_minimax` | `numpy.ndarray` (dtype `float32`, shape `(31,)`) | US2 (scores da opção ESCOLHIDA) e US3+US4 (scores das arestas avaliadas). Posições não-avaliadas usam `numpy.nan`. |
| `ar_probabilidade_cnn` | `numpy.ndarray` (dtype `float32`, shape `(31,)`) | US3+US4 (saída crua da CNN, antes de filtragem). |
| `js_extra` | dict / JSON | Metadados adicionais. **Em US2:** OBRIGATÓRIO conter `{ "co_acao_nao_selecionada": <opção rejeitada>, "ar_score_minimax_opcao_nao_selecionada": <array tamanho 31 da opção rejeitada> }`. |

#### Padrões por User Story originadora

- **US1 (Captura Segura/Gulosa)**:
  - `co_situacao = "captura_segura"`, `co_acao = "captura_gulosa"`.
  - Campos opcionais Minimax/CNN ausentes ou `None`.

- **US2 (Sacrifício / Double-Dealing)**:
  - `co_situacao = "final_corrente_longa"` OU `"final_ciclo"`.
  - `co_acao = "captura_completa"` OU `"sacrificio_double_cross"` (a opção escolhida).
  - `nu_profundidade_minimax = <profundidade configurada>`.
  - `ar_score_minimax = <array tamanho 31 com scores da opção ESCOLHIDA>`.
  - `js_extra = { "co_acao_nao_selecionada": "<a outra opção>", "ar_score_minimax_opcao_nao_selecionada": <array tamanho 31 da opção REJEITADA> }`.

- **US3 + US4 (Fase Tática CNN + Minimax)**:
  - `co_situacao = "tatica"`, `co_acao = "cnn_e_minimax"`.
  - `nu_profundidade_minimax`, `ar_score_minimax`, `ar_probabilidade_cnn` todos preenchidos.

#### Integração End-to-End

Uma partida completa simulada agente-vs-agente DEVE terminar sem exceções, com todas as 31 arestas preenchidas e todas as 12 caixas atribuídas. Cada chamada a `escolher_jogada(...)` deve retornar um `ResultadoJogada` válido, e a sequência de retornos deve ser consistente (sem jogadas inválidas, sem campos obrigatórios faltando).

**Why this priority**: P3 (não P1) porque cada User Story anterior já é independentemente testável. A integração + a saída estruturada validam o pipeline completo e habilitam telemetria/análise futura. Sem `ResultadoJogada` robusto, a equipe perde visibilidade sobre as decisões da IA — comprometendo iteração e aprimoramento da inteligência da `ia-pontinhos-3-4`.

**Independent Test**:
1. **(Saída)** Para cada User Story origem (US1, US2, US3+US4), invocar `escolher_jogada(...)` em estado controlado e validar que o `ResultadoJogada` contém os campos esperados conforme padrão acima.
2. **(Integração)** Rodar simulação `ia-pontinhos-3-4` vs `ia-pontinhos-3-4` em ≥ 100 partidas; verificar que todas terminam com tabuleiro completo, score legítimo, e nenhuma jogada inválida.

**Acceptance Scenarios**:

1. **Given** estado com captura grau-3 isolada (US1), **When** o agente é invocado, **Then** retorna `ResultadoJogada` com `co_situacao = "captura_segura"`, `co_acao = "captura_gulosa"`, e os campos opcionais Minimax/CNN ausentes ou `None`.
2. **Given** estado de double-dealing em corrente longa (US2), **When** o agente decide pela opção B (sacrifício), **Then** retorna `ResultadoJogada` com `co_situacao = "final_corrente_longa"`, `co_acao = "sacrificio_double_cross"`, `ar_score_minimax` preenchido para a opção B, e `js_extra` contendo `co_acao_nao_selecionada = "captura_completa"` e os scores da opção A.
3. **Given** estado de double-dealing em ciclo (US2), **When** o agente decide, **Then** retorna `ResultadoJogada` com `co_situacao = "final_ciclo"` e demais campos análogos ao caso corrente.
4. **Given** estado tático sem caixas grau-3 (US3+US4), **When** o agente joga, **Then** retorna `ResultadoJogada` com `co_situacao = "tatica"`, `co_acao = "cnn_e_minimax"`, `nu_profundidade_minimax`, `ar_score_minimax`, e `ar_probabilidade_cnn` todos preenchidos.
5. **Given** partida completa agente-vs-agente, **When** todas as 31 arestas são preenchidas, **Then** todas as chamadas retornaram `ResultadoJogada` válidos, sem exceção, e a soma de caixas atribuídas = 12.
6. **Given** simulação de 100 partidas, **When** ao final, **Then** 0 jogadas inválidas e 100 partidas concluídas.

---

### Edge Cases

- **Tabuleiro vazio (jogada inicial)**: nenhuma caixa grau-3, nenhuma corrente, nenhum ciclo → entra direto em Passos 3 e 4.
- **Múltiplas correntes simultâneas com grau-3 em ambas**: o agente captura uma chain inteira (Passo 1); antes de pular para outra, **reavalia a Exceção do Passo 2** para a chain ATIVA. A regra do double-dealing aplica-se a UMA estrutura por vez.
- **Mistura corrente + ciclo no mesmo tabuleiro**: cada estrutura é avaliada independentemente. O double-dealing dispara apenas se a estrutura sendo capturada **agora** se enquadra na regra (2 últimas em corrente longa OU 4 últimas em ciclo).
- **Ciclo de exatamente 4 caixas, todas em grau-3**: as 4 últimas SÃO o ciclo inteiro. O double-dealing aplica-se: o agente sacrifica todas as 4 ao adversário (opção B), ou captura todas (opção A), conforme Minimax depth=3 indicar.
- **Corrente de exatamente 3 caixas com as 2 últimas em grau-3**: corrente longa (≥ 3); regra ativa.
- **Empate de score Minimax entre A e B no Passo 2**: prefere B (sacrifício). Tie-breaker definido por estratégia long-term de controle de paridade.
- **Empate de score Minimax entre arestas TOP-5 no Passo 4**: prefere a de maior probabilidade na CNN (ordem original).
- **TOP-5 da CNN contém aresta já preenchida**: filtra silenciosamente. Se sobrar < 5, usa o que sobrar. Se sobrar 0, é erro irrecuperável (não deve ocorrer com modelo bem treinado).
- **Modelo TFLite falha ao carregar ou retorna NaN**: Deve ser um ERRO DURO (`raise`). Não deve haver fallback para Minimax puro.
- **Tabuleiro simétrico**: várias arestas com mesma probabilidade na CNN; seleção determinística capturando a aresta de menor índice conforme o contrato gerador_dados\jogo_pontinhos\contrato_codificacao_pontinhos.json.
- **Detecção da exceção em chain capture interrompida**: o agente acabou de capturar a 1ª caixa de uma corrente; a 2ª está em grau 3; a 3ª e 4ª também — não é "as 2 últimas". Nesse caso, captura normalmente, e **só ao chegar nas 2 últimas** ativa a exceção.
- **Captura múltipla por uma única jogada**: existe configuração rara em que preencher uma aresta interna fecha **duas caixas simultâneas** (uma de cada lado da aresta). O agente DEVE contabilizar ambas; o estado sucessor reflete +2 caixas e mantém o turno.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Captura Segura e Gulosa (Passo 1)

- **FR-001**: O sistema MUST identificar todas as caixas de grau 3 do tabuleiro corrente.
- **FR-002**: Se houver pelo menos uma caixa grau-3 e a Exceção do Passo 2 NÃO se aplicar, o sistema MUST retornar a aresta que fecha uma dessas caixas.
- **FR-003**: Após cada captura, o sistema MUST reavaliar o estado para detectar novas caixas grau-3 surgidas (chain capture). Como a interface pública é stateless, a reavaliação ocorre na chamada subsequente do agente, mantida pela regra de turno extra do jogo.
- **FR-004**: Se múltiplas caixas grau-3 estão disponíveis e nenhuma é exceção, a escolha entre elas MAY ser arbitrária, mas DEVE ser **determinística** para o mesmo estado de entrada (ex.: menor índice da aresta no contrato JSON).

#### Exceção do Sacrifício / Double-Dealing (Passo 2)

- **FR-005**: O sistema MUST detectar quando as **únicas** caixas grau-3 disponíveis representam:
  - **(a)** Exatamente as 2 últimas caixas de **uma única** corrente longa (corrente com ≥ 3 caixas), OU
  - **(b)** Exatamente as 4 últimas caixas de **um único** ciclo.
- **FR-006**: Quando a Exceção do FR-005 for ativada, o sistema MUST gerar dois estados sucessores:
  - **Estado A** — após capturar todas as caixas restantes da estrutura (sequência completa de capturas).
  - **Estado B** — após executar a jogada de double-cross (preencher a aresta interna que entrega as 2 ou 4 caixas ao adversário sem pontuar).
- **FR-007**: O sistema MUST avaliar ambos os estados via **Minimax com profundidade fixa p = 3**.
- **FR-008**: O sistema MUST executar a jogada cujo estado sucessor (A ou B) retornou o **maior score** do Minimax. Em caso de **empate**, MUST preferir B (sacrifício) — tie-breaker pelo controle de paridade.

#### Detecção de Correntes e Ciclos

- **FR-009**: O sistema MUST construir, a cada chamada, um grafo onde cada **nó** é uma caixa de grau 2 (ou grau 3 que faz parte da estrutura sendo avaliada) e cada **aresta-do-grafo** liga duas caixas que compartilham uma aresta-do-jogo NÃO preenchida.
- **FR-010**: O sistema MUST classificar cada componente conexa do grafo como:
  - **Corrente** — caminho aberto, com 2 extremidades. Tamanho = número de caixas no caminho.
  - **Ciclo** — caminho fechado, sem extremidades. Tamanho = número de caixas no laço.
- **FR-011**: Uma corrente é considerada **longa** se possui ≥ 3 caixas. Correntes curtas (1 ou 2 caixas) **não** disparam o double-dealing.
- **FR-012**: O sistema MUST identificar, para cada corrente / ciclo, **quais caixas estão em grau 3** (i.e., já tomáveis), para verificar a condição "as 2 (ou 4) últimas restantes".

#### Fase Tática e CNN (Passo 3)

- **FR-013**: Se NÃO existir nenhuma caixa grau-3 no tabuleiro, o sistema MUST entrar na fase tática (Passos 3 e 4).
- **FR-014**: O sistema MUST codificar o estado do tabuleiro conforme o contrato `gerador_dados/contrato_codificacao_pontinhos.json`, **contexto "Partidas / uso interativo"**.
- **FR-015**: O sistema MUST aplicar normalização **`8 → 0`, `-1 → 1`, `9 → 1`** imediatamente antes de `interp.set_tensor()`, conforme item 5 do contrato JSON.
- **FR-016**: O sistema MUST carregar o modelo `modelos/pontinhos_pequeno_profundidade_9.tflite` ou outro modelo passado como parâmetro via runtime TFLite e executar inferência sobre o tensor normalizado.
- **FR-017**: O sistema MUST extrair da saída da CNN a **distribuição de probabilidade sobre as 31 arestas** do tabuleiro 3x4. A saída do modelo é um **vetor 1D de 31 floats**, onde `output[i]` corresponde à probabilidade da aresta de índice `i` conforme mapeamento no contrato JSON.
- **FR-018**: O sistema MUST filtrar arestas já preenchidas, considerando apenas arestas livres como candidatas.
- **FR-019**: O sistema MUST selecionar as **TOP-5 arestas livres** com maiores probabilidades. Se houver menos de 5 arestas livres, o sistema MUST usar todas as livres disponíveis (degrade gracioso).

#### Validação Final via Minimax (Passo 4)

- **FR-020**: O sistema MUST executar Minimax com poda alpha-beta com **profundidade fixa p = 3**, considerando apenas os ramos que partem das arestas TOP-5 na raiz da busca. Em níveis subsequentes (depth 2 e 1), o branching factor é ditado pelas regras do jogo (todas as arestas livres no estado intermediário).
- **FR-021**: A função de avaliação do Minimax em folhas (depth = 0) ou em estados terminais MUST retornar `score_próprio - score_adversário` (caixas atribuídas a cada lado). Features posicionais  só devem ser introduzidas se a win-rate (SC-006) ficar abaixo da meta. 
- **FR-022**: O sistema MUST respeitar a regra do jogo de **turno extra após captura**: a alternância min/max no Minimax depende de a jogada simulada ter capturado caixa(s); se houve captura, o mesmo jogador joga no próximo nível.
- **FR-023**: O sistema MUST retornar a aresta correspondente ao ramo TOP-5 com **maior score Minimax**. Em caso de empate, MUST preferir a de maior probabilidade na CNN (ordem original do TOP-5).

#### Determinismo, Validade e Performance

- **FR-024**: Para um mesmo estado de entrada **e mesma `ConfiguracaoAgente`** (incluindo `seed_aleatoriedade` quando aplicável), o sistema MUST retornar sempre a mesma jogada (determinismo). Quando `percentual_aleatoriedade > 0` e `seed_aleatoriedade is None`, o agente é **não-determinístico por desígnio** (níveis `facil`, `medio`, `dificil`); nesse modo, FR-024 não se aplica e a SC-004 fica restrita a configurações com `percentual_aleatoriedade = 0.0` ou `seed_aleatoriedade` fixo.
- **FR-025**: O sistema MUST garantir que a jogada retornada corresponde a uma **aresta livre** (não preenchida) em todos os casos.
- **FR-026**: O sistema MUST completar uma decisão (Passo 1+2 ou Passo 3+4) em **< 1000 ms p95** em dispositivos móveis populares. No entanto, o alvo de benchmark inicial deve ser o ambiente desktop x86 local. O foco agora é validar a lógica, a extração de dados e a integração CNN+Minimax aproveitando o poder de processamento da máquina (explorando bem o multithreading do processador). A validação rigorosa de performance do TFLite diretamente no app em Flutter para dispositivos móveis entra em uma feature subsequente de integração de frontend.
- **FR-027**: O sistema MUST expor uma função pública com assinatura **stateless**: recebe `(estado: Tabuleiro, configuracao: ConfiguracaoAgente, metadados: MetadadosTurno)` e retorna um objeto `ResultadoJogada` com os campos definidos no User Story 5. Os UUIDs (`id_partida`, `id_jogada`, `id_jogador`), `ts_jogada` e `nu_timer_ms` vêm em `metadados` e são **ecoados** pelo agente no `ResultadoJogada` — a IA não os gera nem os valida. Não mantém estado interno entre chamadas (modelo TFLite carregado pode ser cacheado em escopo de módulo, mas isso é detalhe de implementação, não estado de jogo).

#### Controle de Tempo e Degradação Graciosa (Fallback)

- **FR-043**: O sistema MUST aceitar como input opcional `nu_timer_ms` (inteiro ≥ 0, em milissegundos) via `MetadadosTurno`, representando o tempo máximo permitido para devolver a *jogada ideal* (Prioridade 1). O valor é fornecido pela camada de partida (App Flutter, simulador, avaliador). Quando ausente (`None`) ou `0`, a execução **não** tem limite de tempo (timeout desabilitado — comportamento equivalente ao das versões anteriores desta SPEC, antes da introdução do timer).
- **FR-044**: O sistema MUST iniciar a contagem do tempo no instante exato em que `escolher_jogada(...)` é acionado (relógio monotônico) e MUST registrar em `nu_tempo_calculo_ms` (inteiro, ms) o tempo total efetivamente gasto até a saída finalmente retornada — campo sempre presente no `ResultadoJogada`, mesmo quando `nu_timer_ms` não foi fornecido.
- **FR-045**: O sistema MUST manter três respostas candidatas com prioridade decrescente, preparadas em ordem antes dos checkpoints de timeout:
  - **Prioridade 3 — fallback final (aleatória)**: aresta livre escolhida **uniformemente ao acaso** entre as livres do tabuleiro. **Preparada IMEDIATAMENTE** no acionamento, antes de qualquer outro custo computacional. É o piso garantido de saída — não pode falhar enquanto houver pelo menos uma aresta livre. Usa `seed_aleatoriedade` quando configurada (FR-024) para reprodutibilidade.
  - **Prioridade 2 — fallback intermediário (CNN)**: argmax entre arestas livres do vetor de probabilidades da CNN (sem Minimax). Preparada na fase tática (Passo 3) **após a inferência da CNN** e antes de qualquer iteração do Minimax (Passo 4). NÃO se aplica quando o estado cai nos Passos 1 ou 2 (capturas / double-dealing) — nesses casos, o agente vai diretamente da Prioridade 3 para a Prioridade 1, pois Passos 1 e 2 são operações sub-milissegundo.
  - **Prioridade 1 — jogada ideal**: saída do pipeline completo (Passos 1–4 conforme aplicável). Comportamento canônico já especificado nos User Stories 1–4 e não alterado por esta seção.
- **FR-046**: Em cada checkpoint do pipeline (após preparar a Prioridade 3; após inferência da CNN; antes de cada iteração do Minimax sobre TOP-5), se `nu_timer_ms > 0` E o tempo decorrido excedeu `nu_timer_ms`, o sistema MUST interromper o cálculo e retornar a resposta de mais alta prioridade já disponível, na ordem **P1 > P2 > P3**.
- **FR-047**: Quando a saída retornada NÃO é a Prioridade 1 (porque o timeout disparou antes do pipeline completar), o `co_acao` MUST refletir a degradação:
  - `co_acao = "cnn_timeout"` quando a Prioridade 2 (argmax da CNN) é retornada;
  - `co_acao = "aleatoria_timeout"` quando a Prioridade 3 (aleatória) é retornada.
  Quando a Prioridade 1 é retornada, `co_acao` segue os padrões já existentes (`captura_gulosa`, `captura_completa`, `sacrificio_double_cross`, `cnn_e_minimax`) — esta SPEC não altera os valores nem semântica das saídas ideais.
- **FR-048**: O `co_situacao` retornado em saídas de fallback MUST refletir a fase do tabuleiro detectada antes do disparo do timeout (`captura_segura`, `final_corrente_longa`, `final_ciclo` ou `tatica`). Quando o timeout dispara antes que a fase tenha sido detectada, o default é `"tatica"` — fase em que o custo computacional se concentra e em que o timeout é ecologicamente esperado.
- **FR-049**: O `ResultadoJogada` MUST conter os campos:
  - `nu_timer_ms` — **eco** do valor recebido em `MetadadosTurno` (incluindo `None` ou `0` quando o input desativa o timeout);
  - `nu_tempo_calculo_ms` — total de ms efetivamente gastos no cálculo da resposta retornada (Prioridade 1, 2 ou 3, conforme o caso).
  Mesmo quando o agente retorna fallback de Prioridade 2 ou 3, os demais campos do `ResultadoJogada` que estiverem disponíveis no momento do timeout (ex.: `ar_probabilidade_cnn` quando o fallback é P2; `ar_score_minimax` parcialmente preenchido com `numpy.nan` nas posições não-avaliadas) DEVEM ser preservados conforme as invariantes de FR-038 — telemetria parcial é melhor que ausência total.

#### Configuração e Parametrização

- **FR-032**: O sistema MUST aceitar como parâmetro o caminho do **modelo CNN (`.tflite`)**. O default é `modelos/pontinhos_pequeno_profundidade_9.tflite`. Qualquer modelo `.tflite` com mesma assinatura de input/output (compatível com tabuleiro 3x4 e contrato de codificação) DEVE ser aceito.
- **FR-033**: O sistema MUST aceitar como parâmetro a **profundidade do Minimax**. O default é `3`. Mínimo aceito: `1`. Sem máximo rígido (limitado por performance — ver SC-005).
- **FR-034**: O sistema MUST suportar **4 níveis de dificuldade** configuráveis: `facil`, `medio`, `dificil`, `expert`. Cada nível mapeia para uma combinação `(modelo_cnn, profundidade_minimax)` definida em configuração. Quando o nível é fornecido, modelo e profundidade são derivados; quando passados explicitamente, sobrescrevem o default do nível.
- **FR-035**: O sistema MUST permitir que o agente jogue contra **adversários heterogêneos**: humanos (via interface), outras IAs (CNN pura), robôs (Minimax puro), e a si mesmo (auto-jogo). A interface pública é **agnóstica ao adversário** — o agente apenas recebe o estado e retorna sua jogada; a alternância de turnos é responsabilidade da camada de partida.

#### Saída Estruturada (Telemetria de Decisão)

- **FR-036**: O sistema MUST retornar a cada chamada de `escolher_jogada(...)` um objeto `ResultadoJogada` contendo **todos os campos comuns** descritos no User Story 5 (`id_partida`, `id_jogada`, `id_jogador`, `nu_jogador`, `co_situacao`, `co_acao`, `co_aresta`, `ar_tabuleiro_antes`, `ar_tabuleiro_apos`, `nu_placar_jogador_antes`, `nu_placar_jogador_apos`, `ts_jogada`, `nu_timer_ms`, `nu_tempo_calculo_ms`).
- **FR-037**: O sistema MUST preencher os campos opcionais do `ResultadoJogada` (`nu_profundidade_minimax`, `ar_score_minimax`, `ar_probabilidade_cnn`, `js_extra`) conforme o passo originador da decisão, seguindo os padrões da User Story 5.
- **FR-038**: Quando `ar_score_minimax` ou `ar_probabilidade_cnn` são preenchidos, MUST ser **`numpy.ndarray` dtype `float32`** de tamanho fixo `31` (uma posição por aresta no tabuleiro 3x4). Posições não-avaliadas MUST ser marcadas com `numpy.nan` (sentinela canônica) — **não omitidas, não substituídas por outro valor**. Isso preserva a invariante de **indexabilidade direta** `array[i] == score_da_aresta_i` e permite filtragem vetorizada via `np.isnan()`.
- **FR-039**: O `co_aresta` MUST seguir a convenção textual definida no contrato `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` (formato `<TIPO>_<dim1>_<dim2>` onde `<TIPO> ∈ {H, V}`).
- **FR-040**: Em decisões originadas no Passo 2 (Double-Dealing), `js_extra` MUST conter pelo menos as chaves `co_acao_nao_selecionada` e `ar_score_minimax_opcao_nao_selecionada` para permitir análise comparativa A vs B na telemetria.
- **FR-041**: O `ar_tabuleiro_antes` e `ar_tabuleiro_apos` MUST representar o estado do tabuleiro **sem normalização** (em domínio bruto `{0, 1, 8, -1}` ou compatível com o NPZ do contrato), preservando informação completa para reconstrução posterior.
- **FR-042**: Quando `percentual_aleatoriedade > 0` (níveis `facil`, `medio`, `dificil` por default), no Passo 4 o agente DEVE, com probabilidade `p = percentual_aleatoriedade`, escolher uma aresta da TOP-5 **uniformemente ao acaso** em vez da aresta de maior score Minimax. Com probabilidade `1 - p`, escolhe a de maior score (comportamento padrão). A aleatoriedade NÃO se aplica aos Passos 1 e 2 (capturas e double-dealing permanecem sempre determinísticos — proteções táticas não são sacrificadas por dificuldade).

#### Conformidade com Contrato e Convenções

- **FR-028**: O sistema MUST seguir a regra de nomenclatura hub-de-jogos (memória `feedback_nomenclatura_hub.md`): todos os arquivos novos com lógica game-specific carregam sufixo `_pontinhos_3_4` (ex.: `ia_pontinhos_3_4.py`, `correntes_pontinhos_3_4.py`, `cnn_inferencia_pontinhos_3_4.py`).
- **FR-029**: O sistema MUST consumir o contrato de codificação como **fonte única da verdade**. Qualquer mudança em encoding, normalização ou layout do tensor de entrada exige primeiro, solicitação de permissão para alterar `gerador_dados/contrato_codificacao_pontinhos.json` (memória `project_contrato_codificacao_pontinhos.md`).
- **FR-030**: O sistema MUST atualizar `docs/historico_decisoes.md` quando esta SPEC for ratificada e quando houver mudanças de rota durante a implementação (memória `feedback_documentacao_viva.md`).
- **FR-031**: O sistema MUST gerar novo documento detalhado contendo toda a documentação de negócio e técnica da `ia-pontinhos-3-4` em `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md` quando esta SPEC for ratificada e quando houver mudanças de rota durante a implementação (memória `feedback_documentacao_viva.md`).

### Key Entities

#### Entidades de Estado de Jogo

- **Tabuleiro** — estado completo do jogo. Atributos: dimensões (3x4 fixo: 3 caixas largura × 4 caixas altura), estado das 31 arestas (livre / preenchida-J1 / preenchida-J2), donos das 12 caixas (J1, J2, nenhum), jogador da vez (J1 ou J2), scores parciais.
- **Caixa** — célula unitária do tabuleiro. Atributos: posição (linha, coluna), 4 arestas associadas (top, right, bottom, left), grau (0–4 derivado das arestas), dono (J1, J2, nenhum).
- **Aresta** — segmento entre dois pontos da grade. Atributos: tipo (horizontal / vertical), índice no contrato JSON (0 a 30), código textual `co_aresta` (ex.: `H_0_1`), estado (livre / preenchida), preenchida-por (J1 / J2 / N/A), caixas adjacentes (1 se borda, 2 se interna).
- **Corrente** — lista ordenada de caixas grau-2 conectadas, caminho aberto. Atributos: caixas (lista), tamanho (≥ 1), classificação (curta < 3, longa ≥ 3), extremidades (2 caixas, podem estar em grau 2 ou 3).
- **Ciclo** — lista ordenada de caixas grau-2 formando laço fechado. Atributos: caixas (lista), tamanho (4, 6, 8 ou 10 em tabuleiro 3x4).
- **EstadoTático** — snapshot do Tabuleiro sem caixas grau-3, codificado para entrada da CNN conforme contrato. Atributos: tensor de entrada (após normalização), turno do jogador.

#### Entidades de Decisão e Busca

- **JogadaCandidata** — tupla `(aresta, probabilidade_cnn, score_minimax)` produzida pelo Passo 4.
- **NóMinimax** — estado intermediário durante a busca. Atributos: estado, profundidade restante, jogador ativo (considerando turno extra), alpha, beta, score acumulado.

#### Entidades de Configuração

- **NivelDificuldade** — enumeração de strings: `facil`, `medio`, `dificil`, `expert`. Cada valor mapeia para uma combinação `(modelo_cnn, profundidade_minimax)`.
- **ConfiguracaoAgente** — parâmetros de instanciação do agente. Atributos:
  - `nivel_dificuldade: NivelDificuldade` (default: `dificil`).
  - `caminho_modelo_cnn: str` (path para `.tflite`; default derivado do nível).
  - `profundidade_minimax: int` (default `3`; ≥ 1).
  - `percentual_aleatoriedade: float` (default derivado do nível; faixa `[0.0, 1.0]`; valor `0.0` = totalmente determinístico). Define a probabilidade de o agente escolher aleatoriamente uma aresta da TOP-5 em vez da indicada pelo Minimax no Passo 4 (ver FR-042 e Modos de Operação > Níveis de Dificuldade).
  - `seed_aleatoriedade: int | None` (default `None`). Quando fornecida, fixa a semente do gerador pseudo-aleatório para tornar a sequência de jogadas reprodutível mesmo com `percentual_aleatoriedade > 0` (essencial para testes determinísticos com aleatoriedade — ver SC-004).
  - `verbose: bool` (default `False`; controla logs de decisão — opt-in).

  Quando `nivel_dificuldade` é fornecido, `caminho_modelo_cnn`, `profundidade_minimax` e `percentual_aleatoriedade` são derivados do mapeamento do nível; quando passados explicitamente, sobrescrevem o default do nível (**override granular** — pode-se sobrescrever apenas um dos três campos, mantendo os demais derivados do nível).
- **Adversario** — abstração externa ao agente (não implementada por esta feature). Tipos previstos: `humano`, `cnn_pura`, `minimax_puro`, `ia_pontinhos_3_4` (auto-jogo). A `ia-pontinhos-3-4` é agnóstica ao tipo do adversário.
- **MetadadosTurno** — estrutura passada a cada chamada de `escolher_jogada(...)` carregando os identificadores e parâmetros temporais deste turno específico, gerados pela camada de partida (avaliador / simulador / App Flutter), não pela IA. Atributos:
  - `id_partida: UUID` — gerado **uma vez** pela aplicação no início da partida; constante durante toda a partida.
  - `id_jogada: UUID` — gerado pela aplicação **antes de cada turno** e passado à IA; a IA o ecoa no `ResultadoJogada`.
  - `id_jogador: UUID` — identidade do jogador deste turno. Pode ser: `id_usuario` do usuário logado (humano), ID fixo configurado para a IA, ou UUID gerado em runtime (para CPU Minimax puro ou usuário não-logado). A IA **não valida** este UUID — apenas o ecoa.
  - `ts_jogada: timestamp ISO 8601 c/ tz` — momento de início do turno, **gerado pela camada de partida** no fuso horário do `id_jogador` e passado já formatado. A IA ecoa sem alteração — não consulta clock, não converte fuso.
  - `nu_timer_ms: int | None` — **opcional**, tempo máximo (em milissegundos) permitido para a IA retornar a *jogada ideal* (Prioridade 1). Quando `None` ou `0`, o timeout está desabilitado (sem limite). Quando `> 0`, ativa a degradação graciosa descrita em FR-043 a FR-049. Valor é decidido externamente (App Flutter, simulador, avaliador) — a IA apenas o respeita e o ecoa em `ResultadoJogada`.
  Separar `MetadadosTurno` da `ConfiguracaoAgente` preserva: (a) `ConfiguracaoAgente` reutilizável entre partidas (vida longa); (b) `Tabuleiro` puro como estado de jogo (sem identidade); (c) statelessness por chamada do agente; (d) o timer pode variar **a cada turno** (ex.: relógio xadrez-like com tempo restante decrescente), o que justifica colocá-lo em `MetadadosTurno` e não em `ConfiguracaoAgente`.

#### Entidades de Saída (Telemetria)

- **CodigoSituacao** — enumeração de strings: `captura_segura`, `final_corrente_longa`, `final_ciclo`, `tatica`. Identifica o ramo do algoritmo que originou a decisão.
- **CodigoAcao** — enumeração de strings: `captura_gulosa`, `captura_completa`, `sacrificio_double_cross`, `cnn_e_minimax`, `cnn_timeout`, `aleatoria_timeout`. Os 4 primeiros identificam estratégias executadas com sucesso pelo pipeline canônico (Prioridade 1). Os 2 últimos identificam fallbacks de degradação graciosa por timeout — `cnn_timeout` para Prioridade 2 (CNN argmax) e `aleatoria_timeout` para Prioridade 3 (aresta uniformemente aleatória) — ver FR-047.
- **ResultadoJogada** — **objeto principal de saída** de `escolher_jogada(...)`. Substitui completamente o conceito de retorno simples `Aresta`. Estrutura:
  - **Campos comuns (sempre presentes)**: `id_partida` (UUID), `id_jogada` (UUID), `id_jogador` (UUID), `nu_jogador` (int 1 ou -1), `co_situacao` (CodigoSituacao), `co_acao` (CodigoAcao), `co_aresta` (str), `ar_tabuleiro_antes` (numpy.ndarray sem normalização), `ar_tabuleiro_apos` (numpy.ndarray sem normalização), `nu_placar_jogador_antes` (int), `nu_placar_jogador_apos` (int), `ts_jogada` (timestamp ISO 8601 com tz), `nu_timer_ms` (int | None — eco de `MetadadosTurno`), `nu_tempo_calculo_ms` (int — tempo gasto até a saída retornada).
  - **Campos opcionais (presentes conforme passo originador, ver User Story 5)**: `nu_profundidade_minimax` (int), `ar_score_minimax` (`numpy.ndarray` dtype `float32`, shape `(31,)`), `ar_probabilidade_cnn` (`numpy.ndarray` dtype `float32`, shape `(31,)`), `js_extra` (dict serializável em JSON).
  - **Invariantes**: arrays opcionais sempre têm shape `(31,)` (uma posição por aresta) com `numpy.nan` em posições não-avaliadas (sentinela canônica fixada — ver FR-038); `co_situacao` e `co_acao` sempre vêm de seus respectivos enums; `nu_tempo_calculo_ms` ≥ 0; quando `nu_timer_ms > 0` e a saída retornada é Prioridade 1, vale `nu_tempo_calculo_ms ≤ nu_timer_ms` (caso contrário, a saída teria sido fallback).

---

## Pseudo-Algoritmo (referência)

Esta seção formaliza o fluxo dos 4 passos sem comprometer com sintaxe Python. Serve de oráculo para a fase de planejamento e geração de tasks.

```
função escolher_jogada(estado, configuracao, metadados) -> ResultadoJogada:
    # metadados carrega: id_partida, id_jogada, id_jogador, ts_jogada, nu_timer_ms

    # ---------- T0 — início da contagem de tempo ----------
    inicio = relogio_monotonico()                          # base para nu_tempo_calculo_ms
    nu_timer_ms = metadados.nu_timer_ms ou 0               # 0 / None = sem timeout
    timeout_ativo = nu_timer_ms > 0

    função elapsed_ms():
        retornar (relogio_monotonico() - inicio) em ms

    função estourou_timer():
        retornar timeout_ativo E elapsed_ms() > nu_timer_ms

    # ---------- Prioridade 3 — fallback aleatório (preparado IMEDIATAMENTE) ----------
    # Custo desprezível; precede QUALQUER outra computação para garantir piso de saída.
    fallback_p3 = aresta_livre_uniformemente_aleatoria(
        estado, seed=configuracao.seed_aleatoriedade
    )
    fallback_p2 = None                                      # preenchido apenas em fase tática

    # Captura snapshot do estado ANTES da jogada (para telemetria)
    tabuleiro_antes = estado.snapshot_sem_normalizacao()
    placar_antes = estado.placar_do_jogador_atual()
    profundidade = configuracao.profundidade_minimax        # default 3

    # ---------- PASSO 1 — Captura Segura ----------
    caixas_grau3 = identificar_caixas_grau_3(estado)

    se estourou_timer():                                    # extremamente raro nesta fase
        retornar montar_resultado(
            aresta = fallback_p3,
            co_situacao = "tatica",                         # default quando fase ainda não detectada
            co_acao = "aleatoria_timeout",
            nu_timer_ms = nu_timer_ms,
            nu_tempo_calculo_ms = elapsed_ms(),
            ... # demais campos comuns
        )

    se caixas_grau3 não está vazia:

        # ---------- PASSO 2 — verificar Exceção ----------
        estrutura = estrutura_ativa(caixas_grau3, estado)
        # estrutura ∈ { corrente_longa, ciclo, "espalhadas" }

        se estrutura é corrente_longa E caixas_grau3 == 2_ultimas_de(estrutura):
            estado_A = simular_captura_completa(estado, estrutura)
            estado_B = simular_double_cross_corrente(estado, estrutura)
            scores_A = minimax_completo(estado_A, profundidade)  # array tamanho 31
            scores_B = minimax_completo(estado_B, profundidade)  # array tamanho 31
            score_A = max(scores_A); score_B = max(scores_B)

            se score_B >= score_A:                # tie-breaker prefere B
                aresta = aresta_double_cross(estrutura)
                retornar ResultadoJogada(
                    co_situacao = "final_corrente_longa",
                    co_acao = "sacrificio_double_cross",
                    nu_profundidade_minimax = profundidade,
                    ar_score_minimax = scores_B,
                    js_extra = {
                        "co_acao_nao_selecionada": "captura_completa",
                        "ar_score_minimax_opcao_nao_selecionada": scores_A
                    },
                    ... # campos comuns
                )
            senão:
                aresta = primeira_aresta_de_captura(estrutura)
                retornar ResultadoJogada(
                    co_situacao = "final_corrente_longa",
                    co_acao = "captura_completa",
                    nu_profundidade_minimax = profundidade,
                    ar_score_minimax = scores_A,
                    js_extra = {
                        "co_acao_nao_selecionada": "sacrificio_double_cross",
                        "ar_score_minimax_opcao_nao_selecionada": scores_B
                    },
                    ...
                )

        senão se estrutura é ciclo E caixas_grau3 == 4_ultimas_de(estrutura):
            # análogo ao caso corrente, com co_situacao = "final_ciclo"
            ...

        senão:
            # ---------- PASSO 1 puro: captura gulosa simples ----------
            aresta = aresta_que_fecha(escolha_deterministica(caixas_grau3))
            retornar ResultadoJogada(
                co_situacao = "captura_segura",
                co_acao = "captura_gulosa",
                # campos opcionais Minimax/CNN ausentes
                ...
            )

    # ---------- PASSO 3 — Fase Tática (CNN) ----------
    tensor = codificar_estado(estado, contexto="partida")
    tensor_normalizado = normalizar(tensor)                 # 8→0, -1→1, 9→1
    distribuicao_31 = inferir_cnn(tensor_normalizado, configuracao.caminho_modelo_cnn)

    # ---- Prioridade 2 pronta: argmax da CNN entre arestas livres ----
    fallback_p2 = arg_max_entre_livres(distribuicao_31, estado)

    se estourou_timer():                                    # timeout após CNN, antes do Minimax
        retornar montar_resultado(
            aresta = fallback_p2,
            co_situacao = "tatica",
            co_acao = "cnn_timeout",
            ar_probabilidade_cnn = distribuicao_31,
            nu_timer_ms = nu_timer_ms,
            nu_tempo_calculo_ms = elapsed_ms(),
            ...
        )

    candidatas = filtrar_arestas_livres(distribuicao_31, estado)
    top5 = selecionar_top_k(candidatas, k=5)

    # ---------- PASSO 4 — Validação Minimax sobre TOP-5 ----------
    scores_31 = array_de_tamanho_31_com_NaN()
    para cada (aresta, prob) em top5:
        # Checkpoint de timeout dentro do laço — Minimax pode dominar o custo total.
        # Se estourar antes de avaliar todas as 5, devolve a melhor resposta já disponível (P2).
        se estourou_timer():
            retornar montar_resultado(
                aresta = fallback_p2,
                co_situacao = "tatica",
                co_acao = "cnn_timeout",
                ar_probabilidade_cnn = distribuicao_31,
                ar_score_minimax = scores_31,               # parcial: posições não-avaliadas = NaN
                nu_profundidade_minimax = profundidade,
                nu_timer_ms = nu_timer_ms,
                nu_tempo_calculo_ms = elapsed_ms(),
                ...
            )
        estado_sucessor = aplicar_jogada(estado, aresta)
        score = minimax(estado_sucessor, profundidade, alpha=-∞, beta=+∞)
        scores_31[aresta.indice] = score

    melhor_aresta = arg_max(scores_31)                      # tie-breaker: maior prob da CNN

    # ---- Prioridade 1 atingida ----
    retornar ResultadoJogada(
        co_situacao = "tatica",
        co_acao = "cnn_e_minimax",
        nu_profundidade_minimax = profundidade,
        ar_score_minimax = scores_31,
        ar_probabilidade_cnn = distribuicao_31,
        nu_timer_ms = nu_timer_ms,
        nu_tempo_calculo_ms = elapsed_ms(),
        ...
    )
```

> **Nota sobre Passos 1 e 2 e timeout**: Capturas (Passo 1) e double-dealing (Passo 2) são operações sub-milissegundo em hardware-alvo — detecção de caixas grau-3, classificação de correntes/ciclos, e Minimax depth=3 sobre 2 estados sucessores. Esperamos que sempre completem dentro de qualquer `nu_timer_ms` razoável (≥ 50 ms). O checkpoint de timeout existe nessas fases por **defesa em profundidade** apenas; em prática, a degradação graciosa é predominantemente um mecanismo da fase tática (Passos 3 e 4).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (Correção do Passo 1)** — em **100%** dos cenários sintéticos com caixa grau-3 isolada (sem corrente longa nem ciclo terminando), o agente retorna uma aresta de captura.
- **SC-002 (Correção do Passo 2)** — em **100%** dos cenários sintéticos canônicos de double-dealing publicados na literatura (Berlekamp et al.), o agente concorda com a decisão ótima quando Minimax depth=3 é suficiente para enxergá-la.
- **SC-003 (Validade)** — em **1000 partidas simuladas** (`ia-pontinhos-3-4` vs `ia-pontinhos-3-4`, e `ia-pontinhos-3-4` vs Minimax-puro), **0 jogadas inválidas** (preenchimento de aresta já preenchida).
- **SC-004 (Determinismo, escopo restrito)** — para um mesmo estado serializado de entrada e configuração com `percentual_aleatoriedade = 0.0` (i.e., nível `expert`) **ou** `seed_aleatoriedade` fixo, **100 chamadas consecutivas** retornam a mesma aresta. Para configurações com aleatoriedade ativa e seed nula, este SC não se aplica (não-determinismo é comportamento por design).
- **SC-005 (Performance)** — tempo médio por jogada **≤ 500 ms**; p95 **≤ 1000 ms**; p99 **≤ 1500 ms**, em dispotivos móveis populares.
- **SC-006 (Win-rate vs Minimax puro)** — em 200 partidas contra Minimax puro com profundidade p=5 (sem CNN), o agente híbrido obtém **win-rate ≥ 50%** (paridade é o piso aceitável; superar valida o ganho da CNN).
- **SC-007 (Win-rate vs ingênuo)** — em 200 partidas contra agente ingênuo (apenas Passo 1, sem Passo 2, com jogadas aleatórias na fase tática), o agente híbrido obtém **win-rate ≥ 90%**.
- **SC-008 (Cobertura de testes)** — cobertura de linha **≥ 90%** nos módulos novos: `ia_pontinhos_3_4.py`, `correntes_pontinhos_3_4.py`, `cnn_inferencia_pontinhos_3_4.py` (e quaisquer outros adicionados nesta feature).
- **SC-009 (Conformidade com contrato)** — **100%** das execuções aplicam a normalização do contrato (`8→0, -1→1, 9→1`) imediatamente antes do `interp.set_tensor()`, verificável por assertion (ou hook) no fluxo. Drift entre código e contrato JSON quebra o teste CI já existente em `tests/unitarios/test_contrato_codificacao_pontinhos.py`.

---

## Assumptions

- **Tabuleiro fixo 3x4** — generalização para outros tamanhos é trabalho futuro, fora de escopo desta feature.
- **Modelo CNN parametrizável** — o caminho do modelo `.tflite` é parâmetro de configuração. O default é `modelos/pontinhos_pequeno_profundidade_9.tflite`. Outros modelos compatíveis com o tabuleiro 3x4 (mesma assinatura input/output) podem ser carregados conforme o `nivel_dificuldade` (ex.: `pontinhos_pequeno_profundidade_6.tflite` para `facil`, `..._7.tflite` para `medio`).
- **Profundidade Minimax parametrizável** — valor padrão `3` (compatível com a especificação original); ajustável via configuração (mínimo `1`, sem máximo rígido — limitado por SC-005).
- **TOP-K da CNN = 5** — valor fixo nesta versão. Literatura de poda guiada por heurística sugere 3 a 7; K=5 é o compromisso definido.
- **Stateless** — a função pública não mantém memória entre chamadas. Estado completo entra como argumento; `ResultadoJogada` sai como retorno. Cache do interpretador TFLite em escopo de módulo é permitido (otimização, não estado de jogo).
- **Contrato de codificação implementado** — assume-se que `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` e o helper Python existem (memória de 2026-04-24). **Verificar conformidade** no início da implementação — caso ausentes nesta branch, importar/copiar do estado consolidado na última branch enviada (`main`).
- **Lógica de jogo subjacente (genérica em dimensão)** — assume-se módulo `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py` parametrizável por dimensões (não específico de 3x4), com representação do Tabuleiro, regras de transição (aplicar jogada, contabilizar captura, alternância de turno) e detecção de fim de jogo. A `ia-pontinhos-3-4` consome essa API instanciando-a com `(largura=3, altura=4)`.
- **Minimax subjacente (genérico)** — assume-se módulo `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` com algoritmo Minimax (com poda alpha-beta) parametrizável por profundidade e por **função de avaliação injetada** (DI obrigatória — ver Clarifications). A `ia-pontinhos-3-4` chama essa API.
- **Determinismo da CNN** — inferência TFLite é reprodutível para o mesmo input (garantia do runtime).
- **Runtime** — Python 3.12+ (consistente com `__pycache__` `.cpython-312` e `.cpython-314` observados no projeto). TFLite via `tflite_runtime` ou `tensorflow.lite.Interpreter` (a definir em `plan.md`).
- **Identidade do jogador** — o agente sabe se está jogando como J1 ou J2 (`nu_jogador` ∈ `{1, -1}`, informação contida no Tabuleiro de entrada). Crítico para a função de avaliação Minimax e para os campos do `ResultadoJogada`.
- **Geração de UUIDs e timestamp** — `id_partida`, `id_jogada`, `id_jogador` e `ts_jogada` são gerados externamente pela camada de partida (avaliador / simulador / App Flutter), nunca pela `ia-pontinhos-3-4`. O agente os recebe via `MetadadosTurno` em cada chamada de `escolher_jogada(...)` e os ecoa no `ResultadoJogada` sem alteração. Política de geração:
  - `id_partida`: gerado uma vez no início da partida.
  - `id_jogada`: gerado a cada turno antes da chamada à IA.
  - `id_jogador`: identidade do jogador da vez — pode ser `id_usuario` do usuário logado, ID fixo da IA, ou UUID runtime para CPU/usuário-anônimo.
  - `ts_jogada`: gerado pela camada de partida no fuso horário do `id_jogador`; ecoado pela IA sem alteração.

---

## Dependencies

### Artefatos game-specific da `ia-pontinhos-3-4` (sufixo `_pontinhos_3_4` obrigatório)

- **Agente principal** — `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` (a criar nesta feature).
- **Detector de correntes/ciclos** — `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py` (a criar; específico para 3x4 conforme FR-028).
- **Wrapper de inferência CNN** — `gerador_dados/jogo_pontinhos/cnn_inferencia_pontinhos_3_4.py` (a criar; carrega TFLite, normaliza, retorna vetor 31).

### Artefatos genéricos do jogo Pontinhos (parametrizáveis por dimensão)

- **Lógica do jogo (genérica)** — `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py` (sem sufixo `_3_4`; projetado para qualquer dimensão, instanciado pelo agente com `(largura=3, altura=4)`). A criar / já existente em `main`.
- **Minimax (genérico)** — `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` (sem sufixo `_3_4`; algoritmo independente de dimensão; recebe estado e função de avaliação injetada). A criar / já existente em `main`.
- **Helper Python do contrato** — `gerador_dados/contrato_codificacao_pontinhos.py` (genérico do jogo Pontinhos).

### Modelos e contratos

- **Modelo TFLite default** — `modelos/pontinhos_pequeno_profundidade_9.tflite` (presente). Outros modelos `.tflite` compatíveis com 3x4 podem ser passados como parâmetro de `ConfiguracaoAgente`.
- **Modelos alternativos para níveis de dificuldade** — `modelos/pontinhos_pequeno_profundidade_6.tflite` (`facil`), `modelos/pontinhos_pequeno_profundidade_7.tflite` (`medio`), `modelos/pontinhos_pequeno_profundidade_9.tflite` (`dificil`) — todos presentes. **`modelos/pontinhos_pequeno_profundidade_11.tflite` (`expert`) ainda não existe** — depende de treinamento futuro (out-of-scope desta feature). Habilitar nível `expert` exige esse arquivo.
- **Contrato JSON** — `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` (a verificar nesta branch — caso ausente, importar de `main`).

### Convenções e documentação viva

- **Convenção de nomenclatura hub** — `feedback_nomenclatura_hub.md`. Aplicação:
  - Arquivos **específicos a uma dimensão** do jogo Pontinhos: sufixo `_pontinhos_<L>_<H>` (ex.: `_pontinhos_3_4`).
  - Arquivos **genéricos** do jogo Pontinhos (parametrizáveis): sufixo `_pontinhos` apenas.
- **Histórico de decisões** — `docs/historico_decisoes.md` (atualizar ao ratificar a SPEC e em mudanças de rota; memória `feedback_documentacao_viva.md`).
- **Documentação técnica da IA** — `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md` (a criar ao ratificar a SPEC; cobre negócio + técnico da `ia-pontinhos-3-4`; ver FR-031).

---

## Out of Scope

### Pipeline de dados e treino (responsabilidade de outras features)

- Treinamento da CNN (já feito em pipeline separado: Databricks → NPZ; Colab → `.keras` → `.tflite`).
- Geração de dataset de partidas (`gerador_dados/`).
- Avaliação offline de modelos / validação cruzada de CNNs.

### Persistência e telemetria (consumidores futuros do `ResultadoJogada`)

- **Persistência local da `tb002_jogada`** — banco SQLite (ou equivalente) embarcado no app, schema, migrations, índices. Esta SPEC produz **apenas** o objeto `ResultadoJogada` em memória; gravar é feature posterior.
- **Sincronização do banco local com o servidor** — fila de envio, conflict resolution, autenticação. Fora de escopo.
- **Schema e migrations da tabela `jogo_pontinhos.tb002_jogada`** — desenho de DDL no banco local e/ou no servidor. Fora de escopo (mas o `ResultadoJogada` define o **conjunto canônico de campos** que essa tabela deve aceitar).
- **Pipeline de análise / dashboards** sobre as jogadas persistidas. Fora de escopo.

### Interfaces e adversários (camadas adjacentes)

- **Interface de usuário** (frontend Flutter, repositório separado `arena-sagaz-frontend`) — incluindo a UI que captura jogadas humanas.
- **API HTTP** que serve o agente (`api/`, fora desta feature).
- **Implementação dos adversários** (CNN pura, Minimax puro como agentes independentes) — esta SPEC apenas define que a `ia-pontinhos-3-4` é agnóstica ao tipo do adversário.
- **Camada de partida** que orquestra alternância de turnos, gera UUIDs (`id_partida`, `id_jogada`), gerencia placar global, detecta vitória/empate. A `ia-pontinhos-3-4` **consome** UUIDs e estados; não os cria.

### Generalizações futuras

- Suporte a tamanhos de tabuleiro diferentes de 3x4 (futuras features `ia_pontinhos_5_5`, etc., reutilizando `tabuleiro_pontinhos.py` e `minimax_pontinhos.py` genéricos).
- Aprendizado em tempo real (online learning, RL, MCTS / AlphaZero-like).
- Otimizações avançadas de Minimax (transposition tables, iterative deepening, killer-move heuristic).
- Modos de jogo alternativos (variantes de regras, tabuleiros não-retangulares).

---

## Clarifications

### Session 2026-04-30

- Q: Heurística do Minimax (FR-021): Utilizar APENAS a diferença pura de caixas (`caixas_próprias - caixas_adversário`) para folhas não-terminais nesta versão. O objetivo é estabelecer uma baseline limpa para provar o valor da arquitetura híbrida. Features posicionais adicionariam ruído na avaliação e só devem ser introduzidas se a win-rate (SC-006) ficar abaixo da meta.
- Q: Hardware-alvo (FR-026, SC-005): O alvo de benchmark inicial deve ser o ambiente desktop x86 local. O foco agora é validar a lógica, a extração de dados e a integração CNN+Minimax aproveitando o poder de processamento da máquina (explorando bem o multithreading do processador). A validação rigorosa de performance do TFLite diretamente no app em Flutter para dispositivos móveis entra em uma feature subsequente de integração de frontend.
- Q: Falha do modelo TFLite: Deve ser um ERRO DURO (`raise`). Não deve haver fallback para Minimax puro. Silenciar a falha mascararia problemas de carregamento do TFLite ou divergências de contrato.
- Q: Logs e tracing: Deve ser opt-in via flag (ex: `verbose=False`). Quando ativo, deve registrar metadados da decisão (qual Passo originou a jogada, scores do Minimax e o TOP-5 da CNN).
- Q: Formato da saída da CNN (FR-017): Oficializar que a saída é estritamente um Vetor 1D de 31 floats, com índice-direto mapeado no JSON. (Integrar a Clarification da Sessão 2026-04-30 aos requisitos).
- Q: Injeção de Dependência (DI) no Minimax: A função de avaliação DEVE ser injetável. Isso é obrigatório para viabilizar testes unitários mockados e isolar os Passos 2 e 4 com facilidade.
- Q: Detecção de "estrutura ativa": Oficializar o default sugerido. Em caso de múltiplas estruturas, a estrutura avaliada no Passo 2 é aquela à qual pertence a próxima caixa grau-3 que seria escolhida pela regra determinística do FR-004 (menor índice no contrato JSON).
- Q: Orientação do tabuleiro → A: 3x4 (3 caixas de largura × 4 caixas de altura). 31 arestas = 15 horizontais + 16 verticais. Identidade do agente passa a ser `ia-pontinhos-3-4`.
- Q: Modelo CNN — fixo ou parametrizável? → A: **Parametrizável**. Aceita qualquer `.tflite` compatível com o tabuleiro 3x4. Default: `pontinhos_pequeno_profundidade_9.tflite`.
- Q: Profundidade Minimax — fixa ou parametrizável? → A: **Parametrizável**, default `3`, mínimo `1`.
- Q: Adversários da `ia-pontinhos-3-4` → A: humanos (UI), IAs (CNN pura), robôs (Minimax puro), ela mesma (auto-jogo). Agente é agnóstico ao tipo do adversário.
- Q: Níveis de dificuldade → A: **4 níveis** — `facil`, `medio`, `dificil`, `expert`. Cada um mapeia para `(modelo_cnn, profundidade_minimax)`. Mapeamento exato é Open Question.
- Q: Saída de `escolher_jogada()` → A: **Não é uma `Aresta` simples**. Retorna objeto `ResultadoJogada` rico com: campos comuns (UUIDs, tabuleiros antes/depois, placar, timestamp, código situação/ação, código aresta) e campos opcionais condicionais (profundidade Minimax, scores Minimax tamanho 31, probabilidades CNN tamanho 31, JSON extra). Estrutura completa documentada em US5 e Key Entities.
- Q: Persistência da telemetria → A: **Fora de escopo desta feature**. A SPEC apenas garante que o agente PRODUZ os dados estruturados; gravar em `tb002_jogada` (banco local SQLite + sync com servidor) é feature posterior.
- Q: Nomenclatura dos arquivos subjacente — `tabuleiro_pontinhos.py` e `minimax_pontinhos.py` levam `_3_4`? → A: **Não**. Esses dois arquivos são **genéricos** (parametrizáveis por dimensão), permanecem com sufixo `_pontinhos` apenas. Apenas arquivos específicos a 3x4 (o agente, detector de correntes específico, wrapper TFLite específico) levam `_pontinhos_3_4`.
- Q: Contagem de arestas para 3x4 → A: 31 arestas totais = **15 horizontais + 16 verticais** (3 caixas largura × 4 caixas altura → 4 colunas × 5 linhas de pontos).
- Q: Mapeamento exato dos 4 níveis de dificuldade → A: Adotada a Opção A com 2 ajustes: (i) `expert` usa `pontinhos_pequeno_profundidade_11.tflite` (modelo a ser treinado) + depth=3 (mantido baixo para preservar p95 em mobile); (ii) os 3 primeiros níveis (`facil`, `medio`, `dificil`) introduzem **percentual de aleatoriedade** na escolha entre TOP-5 do Passo 4. Tabela canônica fixada em "Modos de Operação > Níveis de Dificuldade". Detalhes da aleatoriedade (percentuais por nível, escopo) — ver Open Question pendente.
- Q: Determinismo (FR-024 / SC-004) com aleatoriedade → A: Determinismo é qualificado por configuração: (a) sempre vale para `expert` (`percentual_aleatoriedade = 0.0`); (b) vale para os demais níveis quando `seed_aleatoriedade` é fornecida; (c) NÃO se aplica quando aleatoriedade > 0 e seed é nula (não-determinismo proposital).
- Q: Aleatoriedade afeta os Passos 1 e 2? → A: Não. Aleatoriedade aplica-se EXCLUSIVAMENTE ao Passo 4 (escolha da aresta entre TOP-5). Capturas (Passo 1) e double-dealing (Passo 2) permanecem determinísticos em todos os níveis — a tática simbólica é considerada "vital" e não deve ser sacrificada para gerar dificuldade ajustável.
- Q: Percentuais de aleatoriedade por nível (FR-042) → A: Adotada Opção A — `facil`: 30%, `medio`: 15%, `dificil`: 5%, `expert`: 0%. Valores fixados na tabela canônica em "Modos de Operação > Níveis de Dificuldade".
- Q: Sentinela em arrays opcionais do `ResultadoJogada` (FR-038) → A: `numpy.nan` em `numpy.ndarray` dtype `float32` shape `(31,)`. `None` rejeitado por incompatibilidade com numpy; sentinela explícito (`-999.0`) rejeitado por risco de colisão com scores Minimax legítimos. Permite filtragem vetorizada via `np.isnan()` e preserva indexabilidade direta `array[i] == aresta_i`.
- Q: Como UUIDs (`id_partida`, `id_jogada`, `id_jogador`) chegam ao agente → A: Adotada Opção C — nova entidade `MetadadosTurno` passada como 3º argumento de `escolher_jogada(estado, configuracao, metadados)`. Os 3 UUIDs + `ts_jogada` são gerados pela camada de partida (avaliador / simulador / App Flutter) e simplesmente ecoados pela IA no `ResultadoJogada`. `id_partida` é gerado uma vez por partida; `id_jogada` é gerado antes de cada turno; `id_jogador` é a identidade do jogador da vez (pode ser `id_usuario`, ID fixo da IA, ou UUID runtime para CPU/anônimo). A IA não valida UUIDs — integridade referencial é responsabilidade da camada de persistência.
- Q: Origem e fuso horário do `ts_jogada` → A: Adotada Opção A — aplicação externa (avaliador / simulador / App Flutter) gera `ts_jogada` no fuso horário do `id_jogador` antes de chamar a IA, e o passa via `MetadadosTurno`. A IA ecoa sem alteração — não consulta relógio do sistema, não converte fusos. Garante simetria total com UUIDs e mantém a IA puramente stateless.

---

## Open Questions / NEEDS CLARIFICATION

Sem questões pendentes. Todas as ambiguidades foram resolvidas em sessões de Clarification (ver acima).
