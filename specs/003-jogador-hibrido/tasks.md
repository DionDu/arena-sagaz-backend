# Tasks: Agente Híbrido `ia-pontinhos-3-4`

**Input**: Design documents from `/specs/003-jogador-hibrido/`
**Prerequisites**: spec.md ✓, plan.md ✓, research.md ✓, data-model.md ✓, contracts/api-python-pontinhos-3-4.md ✓, quickstart.md ✓

**Tests**: Incluídos — cobertura ≥ 90% nos módulos novos é requisito explícito (SC-008, plan.md Princípio III). 40+ estados canônicos de tabuleiro cobrem 8 tipos de estrutura × 5 variantes. Cenários de timer com mock determinístico de `time.monotonic_ns` (4 casos obrigatórios).

**Organization**: Tasks organizadas por User Story para implementação e teste independentes. US1 e US2 são ambas P1 e acopladas (Passo 2 é exceção dentro do Passo 1); US3 e US4 são P2 e sequenciais; US5 é P3 de integração.

## Formato: `[ID] [P?] [Story?] Descrição com caminho do arquivo`

- **[P]**: Pode rodar em paralelo (arquivos distintos, sem dependência ativa)
- **[US#]**: User Story de origem (rastreabilidade)
- Caminhos de arquivo incluídos em toda task de implementação

---

## Phase 1: Setup (Verificação, Orientação e Fixtures)

**Purpose**: Leitura obrigatória de contratos e APIs existentes + criação dos builders de estados canônicos que serão usados nos testes.

- [ ] T001 Ler `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` na íntegra para mapear assinatura atual de `minimax()` e `avaliar()` antes das alterações requeridas por D3 (DI obrigatória)
- [ ] T002 Ler `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` na íntegra para mapear encoding do contexto 3 "Partidas / uso interativo" — domínio `{-1, 0, 1, 8}`, normalização `8→0, -1→1, 9→1` — obrigatório por CLAUDE.md antes de qualquer pipeline de inferência ou construção de estado de tabuleiro
- [ ] T003 [P] Verificar presença de `modelos/pontinhos_pequeno_profundidade_6.tflite`, `modelos/pontinhos_pequeno_profundidade_7.tflite` e `modelos/pontinhos_pequeno_profundidade_9.tflite` antes de implementar carregamento TFLite
- [ ] T004 Adicionar funções públicas de construção de estados canônicos em `gerador_dados/jogo_pontinhos/gerador_pontinhos.py`: `construir_estado_corrente_curta(variante: int) -> EstadoTabuleiro`, `construir_estado_corrente_longa(variante: int) -> EstadoTabuleiro`, `construir_estado_ciclo(tamanho: Literal[4, 6, 8, 10], variante: int) -> EstadoTabuleiro`, `construir_estado_ramificada(variante: int) -> EstadoTabuleiro`, `construir_estado_mistura(variante: int) -> EstadoTabuleiro` — cada função entrega 5 variantes determinísticas (variante 0–4) de tabuleiros 3×4 com a estrutura já formada, usando domínio de partida `{-1, 0, 1, 8}` conforme contrato_codificacao_pontinhos.json contexto 3; estas funções são a fonte de verdade dos 40+ estados de teste
- [ ] T005 Gerar `tests/unitarios/jogo_pontinhos/fixtures_correntes_pontinhos_3_4.md` — para cada um dos 40+ estados produzidos pelos builders de T004 (8 tipos × 5 variantes), registrar: (a) cabeçalho com tipo, variante e breve descrição da estrutura esperada; (b) matriz numpy crua em `np.array2string` no domínio de partida `{-1, 0, 1, 8}`; (c) representação ASCII do tabuleiro conforme estilo de `_matriz_partida_para_ascii` de `visualizador_pontinhos.py` — pontos `.`, arestas `---`/`|`, caixas `[1]`/`[-1]`/`[ ]`; (d) legenda de leitura. Arquivo serve como referência humana permanente para validar que os tabuleiros de teste representam corretamente as estruturas desejadas.

**Checkpoint**: Contratos mapeados + 40+ estados canônicos construídos + MD de visualização gerado → implementação pode iniciar

---

## Phase 2: Foundational (Tipos + Minimax DI)

**Purpose**: Infraestrutura de dados compartilhada por todos os módulos. DEVE estar completa antes de qualquer User Story.

**⚠️ CRÍTICO**: Nenhuma User Story pode ser implementada antes desta fase.

- [ ] T006 Criar `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py` com enums `NivelDificuldade(str, Enum)`, `CodigoSituacao(str, Enum)`, `CodigoAcao(str, Enum)` e constante `MAPEAMENTO_NIVEIS` (data-model.md § Enumerações e MAPEAMENTO_NIVEIS)
- [ ] T007 Adicionar `@dataclass ConfiguracaoAgente` com campos `nivel_dificuldade`, `caminho_modelo_cnn`, `profundidade_minimax`, `percentual_aleatoriedade`, `seed_aleatoriedade`, `verbose` e `__post_init__` derivando defaults de `MAPEAMENTO_NIVEIS` com validações ValueError em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py`
- [ ] T008 Adicionar `@dataclass(frozen=True) MetadadosTurno` com campos `id_partida`, `id_jogada`, `id_jogador`, `nu_jogador`, `ts_jogada`, `nu_timer_ms: int | None = None` e `__post_init__` com ValueError em `nu_jogador ∉ {1,-1}` e `nu_timer_ms < 0` em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py`
- [ ] T009 Adicionar `@dataclass ResultadoJogada` com todos os campos comuns (`id_partida`, `id_jogada`, `id_jogador`, `nu_jogador`, `co_situacao`, `co_acao`, `co_aresta`, `ar_tabuleiro_antes`, `ar_tabuleiro_apos`, `nu_placar_jogador_antes`, `nu_placar_jogador_apos`, `ts_jogada`, `nu_timer_ms`, `nu_tempo_calculo_ms`) e campos opcionais (`nu_profundidade_minimax`, `ar_score_minimax`, `ar_probabilidade_cnn`, `js_extra`) em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py`
- [ ] T010 Adicionar `@dataclass(frozen=True) Estrutura` com campos `tipo: Literal["corrente", "ciclo", "ramificada", "isolada"]`, `caixas: tuple[tuple[int, int], ...]`, `extremidades: tuple[tuple[int, int], ...]` e propriedades `tamanho` e `eh_corrente_longa` em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py`
- [ ] T011 Adicionar helpers públicos `array_31_com_nan() -> np.ndarray` e `contar_caixas_jogador(estado, jogador) -> int` em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py`
- [ ] T012 Adicionar type alias `FuncaoAvaliacao = Callable[[EstadoTabuleiro, int, int], int]` e parâmetro `fn_avaliacao: FuncaoAvaliacao = avaliar` à função `minimax()` em `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` mantendo default compatível com chamadores legados (D3)
- [ ] T013 [P] Criar `tests/unitarios/jogo_pontinhos/test_tipos_pontinhos_3_4.py` com casos: ConfiguracaoAgente deriva defaults corretos por NivelDificuldade; override granular de um campo mantém outros derivados do nível; ValueError em `profundidade_minimax < 1` e `percentual_aleatoriedade ∉ [0,1]`; MetadadosTurno ValueError em `nu_jogador ∉ {1,-1}` e `nu_timer_ms < 0`; `nu_timer_ms = None` e `0` são válidos; `array_31_com_nan()` retorna `float32` shape `(31,)` com `np.nan`; `contar_caixas_jogador` conta corretamente caixas atribuídas
- [ ] T014 [P] Criar `tests/unitarios/jogo_pontinhos/test_minimax_pontinhos_di.py` com casos: com `fn_avaliacao` mockada que retorna constante, score é alterado conforme esperado; com default `fn_avaliacao=avaliar`, comportamento idêntico ao código legado; mock confirma que DI é passada corretamente através da recursão

**Checkpoint**: `tipos_pontinhos_3_4.py` completo + Minimax com DI + testes passando → User Stories podem iniciar

---

## Phase 3: User Story 1 — Captura Segura e Gulosa (Priority: P1) 🎯 MVP

**Goal**: Agente identifica caixas de grau-3 e captura deterministicamente, sem ativar lógica de double-dealing.

**Independent Test**: Carregar tabuleiros sintéticos com 1+ caixas grau-3 isoladas (não pertencentes a corrente longa nem ciclo terminando); chamar `escolher_jogada`; verificar que `co_aresta` fecha uma caixa grau-3 e que `co_situacao = "captura_segura"`, `co_acao = "captura_gulosa"`.

- [ ] T015 [US1] Criar `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py` com função pública `caixas_grau_3(estado: EstadoTabuleiro) -> list[tuple[int, int]]` que identifica todas as caixas de grau 3 no tabuleiro. **Requisito de design**: o módulo deve ser autossuficiente e importável diretamente por `avaliador_partidas_pontinhos.py` e `visualizador_pontinhos.py` sem depender de `ia_pontinhos_3_4.py` — as funções públicas operam apenas sobre `EstadoTabuleiro` e `Estrutura`, preparando o módulo para uso futuro na classificação de entregas de caixas pela CNN (fora do escopo desta feature, mas o design deve prevê-lo)
- [ ] T016 [US1] Criar stub de `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` com: importações necessárias, cache module-level `_cache_interpretadores: dict[str, InferenciaCNN]` + `_lock_cache: threading.Lock`, helpers privados `_elapsed_ms(inicio_ns) -> int`, `_estourou_timer(inicio_ns, nu_timer_ms) -> bool`, `_aresta_aleatoria_livre(estado, rng) -> str`, `_arg_max_arestas_livres(distribuicao, estado) -> str`, e assinatura pública de `escolher_jogada` com `raise NotImplementedError` temporário
- [ ] T017 [US1] Implementar início de `escolher_jogada` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: capturar `inicio_ns = time.monotonic_ns()`, `nu_timer_ms = metadados.nu_timer_ms or 0`, instanciar `rng = np.random.default_rng(configuracao.seed_aleatoriedade)`, preparar `fallback_p3 = _aresta_aleatoria_livre(estado, rng)`, snapshot `tabuleiro_antes = estado.matriz.copy()`, calcular `placar_antes`
- [ ] T018 [US1] Implementar Passo 1 em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: chamar `caixas_grau_3(estado)`, verificar `_estourou_timer` para retorno de fallback P3, se caixas_grau3 não vazia e Passo 2 não aplicável capturar aresta de menor índice canônico (FR-004)
- [ ] T019 [US1] Implementar helpers `_montar_resultado_us1(aresta, estado, tabuleiro_antes, placar_antes, inicio_ns, metadados, configuracao) -> ResultadoJogada` e `_montar_resultado_timeout_aleatoria(aresta, co_situacao, tabuleiro_antes, placar_antes, inicio_ns, metadados) -> ResultadoJogada` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` populando todos os campos comuns e opcionais corretos (None para Minimax/CNN em US1)
- [ ] T020 [P] [US1] Criar `tests/unitarios/jogo_pontinhos/test_correntes_pontinhos_3_4.py` — importar builders de T004 (`from gerador_dados.jogo_pontinhos.gerador_pontinhos import construir_estado_corrente_curta, construir_estado_corrente_longa, construir_estado_ciclo, construir_estado_ramificada, construir_estado_mistura`); testes iniciais com variantes 0–4 de `construir_estado_corrente_curta`: `caixas_grau_3` retorna `[]` em estados sem caixas grau-3; retorna a lista correta quando caixas grau-3 existem; valida que os 5 estados de corrente curta produzidos pelo builder estão no domínio correto `{-1, 0, 1, 8}` conforme contrato
- [ ] T021 [P] [US1] Criar `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py` com cenários US1: captura grau-3 isolada retorna `co_aresta` que fecha aquela caixa; múltiplas grau-3 isoladas → determinístico (menor índice canônico); `co_situacao = "captura_segura"` e `co_acao = "captura_gulosa"`; `nu_profundidade_minimax`, `ar_score_minimax`, `ar_probabilidade_cnn` são `None`; `nu_tempo_calculo_ms` é `int >= 0`

**Checkpoint**: US1 implementada e testada — `escolher_jogada` captura caixas grau-3 simples corretamente

---

## Phase 4: User Story 2 — Exceção do Sacrifício / Double-Dealing (Priority: P1)

**Goal**: Agente detecta correntes longas e ciclos via BFS, avalia Minimax nos estados A e B, executa double-cross quando score_B ≥ score_A (tie-breaker prefere B).

**Independent Test**: Construir tabuleiro canônico com corrente longa de 5 caixas onde as 2 últimas estão em grau-3 e Minimax depth=3 indica que B (sacrifício) supera A; chamar agente; verificar `co_acao = "sacrificio_double_cross"` e `js_extra["co_acao_nao_selecionada"] = "captura_completa"`.

- [ ] T022 [US2] Adicionar BFS sobre grafo dual a `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py` — função pública `detectar_estruturas(estado: EstadoTabuleiro) -> list[Estrutura]` constrói grafo onde nós são caixas grau-2, arestas-grafo ligam caixas que compartilham aresta-jogo livre, classifica componentes conexos como `"corrente"` (caminho aberto), `"ciclo"` (caminho fechado), `"ramificada"` (grafo com nó de grau > 2) ou `"isolada"` (caixa grau-2 sem vizinhas) (D2). **Requisito de design para uso futuro**: `detectar_estruturas` é a função central para classificação de situação de tabuleiro em `avaliador_partidas_pontinhos.py` e `visualizador_pontinhos.py` — quando a CNN entregar uma caixa grau-3 ao adversário (fora do escopo desta feature), esses módulos chamarão `detectar_estruturas` sobre o estado anterior para determinar se a entrega era erro ou sacrifício válido. O retorno `list[Estrutura]` com o campo `tipo` completo (incluindo `"ramificada"` e `"isolada"`) é suficiente para esse uso sem modificação futura da assinatura
- [ ] T023 [US2] Adicionar funções de análise de estrutura a `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py`: `estrutura_ativa(estado, caixas_grau_3) -> Estrutura | None`, `trigger_double_dealing(estrutura, caixas_grau_3) -> bool` (True quando as caixas_grau_3 são exatamente as 2 últimas de corrente longa OU as 4 últimas de ciclo), `aresta_double_cross(estrutura, estado) -> str`, `primeira_aresta_de_captura(estrutura, estado) -> str`. Todas as funções públicas devem operar exclusivamente sobre `EstadoTabuleiro` e `Estrutura` — sem acoplamento a `ia_pontinhos_3_4.py`
- [ ] T024 [US2] Adicionar funções de simulação a `gerador_dados/jogo_pontinhos/correntes_pontinhos_3_4.py`: `estado_apos_captura_completa(estado, estrutura, jogador) -> EstadoTabuleiro` e `estado_apos_double_cross(estado, estrutura, jogador) -> EstadoTabuleiro` gerando estados sucessores A e B para avaliação pelo Minimax
- [ ] T025 [US2] Implementar Passo 2 em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: chamar `estrutura_ativa`, verificar `trigger_double_dealing`, se ativo gerar estados A e B com `estado_apos_captura_completa`/`estado_apos_double_cross`, invocar `minimax()` com `fn_avaliacao=avaliar` e `profundidade=configuracao.profundidade_minimax` em cada estado, decidir por score (empate → B)
- [ ] T026 [US2] Implementar helper `_montar_resultado_us2(aresta, co_situacao, co_acao, scores_escolhida, scores_rejeitada, co_acao_rejeitada, tabuleiro_antes, placar_antes, inicio_ns, metadados, configuracao) -> ResultadoJogada` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` — preenche `ar_score_minimax` com array da opção escolhida e `js_extra` obrigatoriamente com `co_acao_nao_selecionada` e `ar_score_minimax_opcao_nao_selecionada` (FR-040)
- [ ] T027 [P] [US2] Expandir `tests/unitarios/jogo_pontinhos/test_correntes_pontinhos_3_4.py` com **40+ casos canônicos** usando os builders de T004 — 5 variantes por tipo, totalizando 40 estados base:
  - **5 correntes curtas** (1–2 caixas via `construir_estado_corrente_curta(0..4)`): `detectar_estruturas` retorna corrente com `tamanho <= 2` e `eh_corrente_longa = False`; `trigger_double_dealing` retorna `False`
  - **5 correntes longas** (3–7 caixas via `construir_estado_corrente_longa(0..4)`): `detectar_estruturas` retorna corrente com `tamanho >= 3` e `eh_corrente_longa = True`; `trigger_double_dealing` retorna `True` quando as 2 últimas estão em grau-3
  - **5 ciclos de 4 caixas** (via `construir_estado_ciclo(4, 0..4)`): `detectar_estruturas` retorna `tipo = "ciclo"` com `tamanho = 4`; `trigger_double_dealing` retorna `True` quando as 4 últimas estão em grau-3
  - **5 ciclos de 6 caixas** (via `construir_estado_ciclo(6, 0..4)`): idem com `tamanho = 6`
  - **5 ciclos de 8 caixas** (via `construir_estado_ciclo(8, 0..4)`): idem com `tamanho = 8`
  - **5 ciclos de 10 caixas** (via `construir_estado_ciclo(10, 0..4)`): idem com `tamanho = 10`
  - **5 estruturas ramificadas** (via `construir_estado_ramificada(0..4)`): `detectar_estruturas` retorna `tipo = "ramificada"`; `trigger_double_dealing` retorna `False`; `estrutura_ativa` retorna `None` ou estrutura sem ativar double-dealing
  - **5 misturas** (via `construir_estado_mistura(0..4)`): `detectar_estruturas` retorna múltiplas estruturas de tipos distintos no mesmo tabuleiro; double-dealing ativo somente para a estrutura correta
- [ ] T028 [P] [US2] Adicionar cenários US2 a `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py`: corrente longa onde score_B > score_A → `co_acao = "sacrificio_double_cross"`, `js_extra` com opção rejeitada `"captura_completa"`; ciclo onde score_A > score_B → `co_acao = "captura_completa"`, `js_extra` com opção rejeitada `"sacrificio_double_cross"`; empate → prefere B; corrente curta (2 caixas) NÃO ativa Passo 2 — captura normalmente; caixas grau-3 em estruturas distintas NÃO ativa Passo 2; `co_situacao = "final_corrente_longa"` ou `"final_ciclo"` conforme caso

**Checkpoint**: US1 + US2 funcionando — agente captura e aplica double-dealing corretamente (pipeline simbólico completo)

---

## Phase 5: User Story 3 — Fase Tática via CNN (Priority: P2)

**Goal**: Quando não há caixas grau-3, agente codifica estado conforme contrato, invoca CNN TFLite e extrai TOP-5 arestas livres ordenadas por probabilidade.

**Independent Test**: Mockar inferência CNN sobre tabuleiro vazio; verificar que função retorna 5 arestas distintas, todas livres, ordenadas por probabilidade descendente; verificar que AssertionError é levantado se tensor contém valores fora de `{0, 1}`.

- [ ] T029 [US3] Criar `gerador_dados/jogo_pontinhos/cnn_inferencia_pontinhos_3_4.py` com `@dataclass InferenciaCNN` (campos: `interpretador`, `indice_entrada`, `indice_saida`, `forma_entrada`, `lock`) e cache module-level `_cache_interpretadores: dict[str, InferenciaCNN]` protegido por `_lock_cache: threading.Lock`
- [ ] T030 [US3] Implementar `carregar_modelo(caminho_tflite: str) -> InferenciaCNN` em `gerador_dados/jogo_pontinhos/cnn_inferencia_pontinhos_3_4.py` — verifica cache primeiro (thread-safe via `_lock_cache`), se miss instancia `tensorflow.lite.Interpreter`, chama `allocate_tensors()`, pré-calcula `indice_entrada`/`indice_saida`/`forma_entrada`, entra no cache; `FileNotFoundError` se caminho inexistente; `RuntimeError` se TFLite falha (D1, D6, D9)
- [ ] T031 [US3] Implementar `inferir(inferencia: InferenciaCNN, estado: EstadoTabuleiro) -> np.ndarray` em `gerador_dados/jogo_pontinhos/cnn_inferencia_pontinhos_3_4.py` — lê `estado.matriz`, aplica normalização `8→0, -1→1, 9→1` sobre cópia (NUNCA sobre a matriz original — conforme contrato contexto 3), `AssertionError` se tensor normalizado contém valores fora de `{0, 1}`, adquire `inferencia.lock`, chama `set_tensor → invoke → get_tensor`, `RuntimeError` se saída contém NaN/inf (FR-015, FR-029, D9)
- [ ] T032 [US3] Implementar `top_k_arestas_livres(distribuicao: np.ndarray, estado: EstadoTabuleiro, k: int = 5) -> list[tuple[str, float]]` e `_limpar_cache_interpretadores() -> None` em `gerador_dados/jogo_pontinhos/cnn_inferencia_pontinhos_3_4.py` — filtra arestas já preenchidas, ordena por probabilidade desc, tie-break menor índice canônico, degrade gracioso se livres < k (FR-018, FR-019)
- [ ] T033 [US3] Implementar Passo 3 em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: chamar `carregar_modelo(configuracao.caminho_modelo_cnn)`, `inferir(inferencia, estado)` para obter `distribuicao_31`, atualizar `fallback_p2 = _arg_max_arestas_livres(distribuicao_31, estado)`, verificar `_estourou_timer` para retorno P2 com `co_acao = "cnn_timeout"`, chamar `top_k_arestas_livres(distribuicao_31, estado, k=5)` para obter `top5`
- [ ] T034 [P] [US3] Criar `tests/unitarios/jogo_pontinhos/test_cnn_inferencia_pontinhos_3_4.py` com casos: `carregar_modelo` com caminho inexistente levanta `FileNotFoundError`; normalização aplica `8→0, -1→1, 9→1` sobre cópia (matriz original não modificada); `inferir` retorna `ndarray` shape `(31,)` dtype `float32`; `AssertionError` se tensor pós-normalização contém valor fora de `{0, 1}`; `top_k_arestas_livres` retorna 5 arestas distintas livres em ordem descendente de probabilidade; cache retorna mesma instância na 2ª chamada; lock presente no dataclass; determinismo: mesmo input produz mesmo top-5

**Checkpoint**: US3 implementada — CNN inferida e TOP-5 extraído corretamente

---

## Phase 6: User Story 4 — Validação Final via Minimax (Priority: P2)

**Goal**: Para cada aresta do TOP-5, executa Minimax com depth configurado; retorna aresta com maior score; respeita checkpoints de timer devolvendo P1, P2 ou P3 conforme o tempo disponível.

**Independent Test**: Mockar CNN para retornar 5 arestas conhecidas; configurar tabuleiro onde 1 das 5 cria caixa grau-3 para o adversário no próximo ply (score baixo) e outra é neutra (score alto); chamar agente; verificar que retorna a aresta neutra.

- [ ] T035 [US4] Implementar Passo 4 em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: inicializar `scores_31 = array_31_com_nan()`, loop sobre `top5`, verificar `_estourou_timer` antes de cada iteração (retorna P2 se expirado), chamar `minimax(estado_sucessor, configuracao.profundidade_minimax, fn_avaliacao=avaliar)` via `minimax_pontinhos.minimax`, preencher `scores_31[idx(aresta)]` com score retornado (FR-020, FR-022)
- [ ] T036 [US4] Implementar `_arg_max_com_tiebreak(scores_31: np.ndarray, top5: list[tuple[str, float]]) -> str` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` — seleciona aresta com maior score Minimax entre as avaliadas; em empate prefere a de maior probabilidade CNN (ordem original do top5) (FR-023)
- [ ] T037 [US4] Implementar lógica de aleatoriedade FR-042 em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`: após `_arg_max_com_tiebreak`, se `rng.random() < configuracao.percentual_aleatoriedade` substituir `melhor_aresta` por `rng.choice([a for (a, _) in top5])`; a aleatoriedade NÃO se aplica aos Passos 1 e 2 (D7)
- [ ] T038 [US4] Implementar helpers `_montar_resultado_us3_4(aresta, distribuicao_31, scores_31, tabuleiro_antes, placar_antes, inicio_ns, metadados, configuracao) -> ResultadoJogada` e `_montar_resultado_timeout_cnn(fallback_p2, distribuicao_31, scores_31_parcial, tabuleiro_antes, placar_antes, inicio_ns, metadados, configuracao) -> ResultadoJogada` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` — primeiro preenche `ar_score_minimax` completo, segundo preserva scores parciais com nan e seta `co_acao = "cnn_timeout"` (FR-049)
- [ ] T039 [P] [US4] Adicionar cenários US3+US4 a `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py`: aresta que cria oportunidade de captura para adversário no próximo ply tem score menor → agente retorna aresta neutra; empate de score Minimax entre duas arestas → aresta de maior probabilidade CNN é escolhida (FR-023); turno extra respeitado dentro do Minimax (captura de caixa não alterna min/max); `co_situacao = "tatica"`, `co_acao = "cnn_e_minimax"`, `ar_probabilidade_cnn` preenchido, `nu_profundidade_minimax = 3`
- [ ] T040 [P] [US4] Adicionar cenários timer a `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py` com mock de `time.monotonic_ns` via `unittest.mock.patch`: (a) sem timer `nu_timer_ms=None` → P1 retornada, `nu_tempo_calculo_ms` reportado, `co_acao ≠ cnn_timeout`; (b) timer largo ≥ 800ms → P1 retornada dentro do limite; (c) mock força estouro após CNN → P2 `co_acao = "cnn_timeout"`, `ar_probabilidade_cnn` preenchido, `ar_score_minimax` None ou parcial; (d) mock força estouro no início → P3 `co_acao = "aleatoria_timeout"`, todos os opcionais None

**Checkpoint**: US3 + US4 funcionando — fase tática completa com CNN + Minimax + timer cooperativo

---

## Phase 7: User Story 5 — Saída Estruturada e Integração End-to-End (Priority: P3)

**Goal**: Toda chamada retorna `ResultadoJogada` válido com todos os campos obrigatórios; auto-jogo de 100 partidas termina sem exceção; win-rate vs Minimax puro ≥ meta (SC-006).

**Independent Test**: (1) Para cada US de origem, invocar em estado controlado e validar campos do `ResultadoJogada`. (2) 100 partidas auto-jogo com 0 jogadas inválidas, 12 caixas atribuídas, e `sum(caixas_J1) + sum(caixas_J2) = 12` em toda partida.

- [ ] T041 [US5] Revisar e completar todos os helpers `_montar_resultado_*` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py` verificando: eco exato de `id_partida`, `id_jogada`, `id_jogador`, `nu_jogador`, `ts_jogada`, `nu_timer_ms` de `MetadadosTurno`; `ar_tabuleiro_antes` e `ar_tabuleiro_apos` sem normalização, dtype `int8`, copiados corretamente (NUNCA normalizar o tabuleiro da partida — contrato contexto 3); `nu_placar_jogador_apos = nu_placar_jogador_antes + caixas_capturadas` (FR-036, FR-041, FR-049)
- [ ] T042 [US5] Adicionar cenários US5 a `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py`: `ResultadoJogada` de US1 tem `nu_profundidade_minimax`, `ar_score_minimax`, `ar_probabilidade_cnn`, `js_extra` todos `None`; `ResultadoJogada` de US2 tem `js_extra` obrigatoriamente com `co_acao_nao_selecionada` e `ar_score_minimax_opcao_nao_selecionada`; `ResultadoJogada` de US3+US4 tem `ar_probabilidade_cnn` e `ar_score_minimax` shape `(31,)` dtype `float32`; `nu_timer_ms` ecoado bit-a-bit (incluindo `None`); `nu_tempo_calculo_ms` é sempre `int >= 0`; `co_aresta` está em `estado.tracos_disponiveis()` antes da chamada
- [ ] T043 [US5] Criar `tests/integracao/jogo_pontinhos/test_partida_completa_pontinhos_3_4.py` com: (a) auto-jogo `ia-pontinhos-3-4` vs `ia-pontinhos-3-4` — 100 partidas, verificar que cada partida termina com 31 arestas preenchidas, 12 caixas atribuídas e 0 jogadas inválidas (SC-003, SC-007); (b) win-rate vs Minimax puro depth=5 — 200 partidas, registrar resultado (SC-006); (c) cenário timer — 50 partidas com `nu_timer_ms = 200`, verificar que ≥ 80% das jogadas são P1 (`co_acao not in {cnn_timeout, aleatoria_timeout}`) e que nenhuma jogada inválida ocorre

**Checkpoint**: Todos os 5 User Stories funcionando e integrados — agente pronto para uso em produção

---

## Phase 8: Polish e Cross-Cutting

**Purpose**: Documentação obrigatória, validação de cobertura e conformidade de contrato.

- [ ] T044 Criar `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md` com: visão geral do agente híbrido; arquitetura dos 4 passos; modos de operação e adversários; 4 níveis de dificuldade com mapeamento canônico; timer cooperativo (D10) e hierarquia P1/P2/P3; exemplos de uso (sem timer, timer largo, timer apertado, timer extremo); design do módulo `correntes_pontinhos_3_4.py` e seu uso futuro previsto em `avaliador_partidas_pontinhos.py` / `visualizador_pontinhos.py`; instruções de execução dos testes (FR-031)
- [ ] T045 Atualizar `docs/historico_decisoes.md` registrando entrada para timer cooperativo D10: data 2026-05-02, contexto (necessidade de degradação graciosa para app Flutter), decisão (checkpoints síncronos com `time.monotonic_ns()`), alternativas rejeitadas (`signal.SIGALRM` POSIX-only, `threading.Timer` sem cancelamento real, `concurrent.futures` sem interrupção, async com custo de refatoração), motivo (portabilidade Windows/macOS/Linux, determinismo, custo zero no caminho feliz) (FR-030)
- [ ] T046 [P] Executar `pytest tests/unitarios/jogo_pontinhos/ --cov=gerador_dados/jogo_pontinhos/ --cov-report=term-missing` e verificar cobertura ≥ 90% em `ia_pontinhos_3_4.py`, `correntes_pontinhos_3_4.py`, `cnn_inferencia_pontinhos_3_4.py` e `tipos_pontinhos_3_4.py` (SC-008)
- [ ] T047 [P] Executar `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` para verificar que cópia do JSON no backend é idêntica ao frontend e que helper aplica exatamente as regras declaradas (CI obrigatório por CLAUDE.md)
- [ ] T048 Validar manualmente exemplos 1–4 de `specs/003-jogador-hibrido/quickstart.md`: Exemplo 1 (sem timer), Exemplo 2 (timer 500ms → P1), Exemplo 3 (timer 80ms → P2 `cnn_timeout`), Exemplo 4 (timer 1ms → P3 `aleatoria_timeout`)

---

## Dependencies & Execution Order

### Dependências de Fase

- **Phase 1 (Setup)**: T001-T003 sem dependências — iniciar imediatamente; T004 depende de T001 + T002 (builders usam EstadoTabuleiro e domínio de partida); T005 depende de T004
- **Phase 2 (Foundational)**: Depende de Phase 1 — BLOQUEANTE para todas as User Stories
- **Phase 3 (US1)**: Depende de Phase 2 completa; T015 pode avançar em paralelo com Phase 2 (módulo diferente)
- **Phase 4 (US2)**: Depende de Phase 3 completa (Passo 2 é exceção dentro do Passo 1 já implementado)
- **Phase 5 (US3)**: Depende de Phase 2 completa; pode avançar em paralelo com Phase 4 com dois developers
- **Phase 6 (US4)**: Depende de Phase 5 completa + Phase 2 (Minimax DI deve estar pronto)
- **Phase 7 (US5)**: Depende de Phases 3, 4, 5, 6 todas completas
- **Phase 8 (Polish)**: Depende de todas as User Stories completas

### Dependências entre User Stories

| User Story | Depende de | Pode ser independente de |
|---|---|---|
| US1 (P1) | Phase 2 (tipos + minimax DI) + T004 (builders para testes) | US2, US3, US4, US5 |
| US2 (P1) | US1 (Passo 2 é exceção no Passo 1) | US3, US4, US5 |
| US3 (P2) | Phase 2 (tipos + minimax DI) | US1, US2 (módulo cnn_inferencia independente) |
| US4 (P2) | US3 (consume TOP-5 do Passo 3) | US1, US2 |
| US5 (P3) | US1, US2, US3, US4 | — |

### Dependências dos Builders e do MD (Phase 1)

```
T001 (ler minimax) ─┐
T002 (ler contrato) ─┼→ T004 (builders em gerador_pontinhos.py) → T005 (MD visualização)
T003 (ver modelos) ─┘                                            ↓
                                                         T020 (test_correntes inicial)
                                                         T027 (test_correntes 40+ casos)
```

---

## Parallel Execution Examples

### Phase 1 — Builders e verificações

```bash
# T001, T002, T003 em paralelo (leituras independentes):
Task T001: ler minimax_pontinhos.py
Task T002: ler contrato_codificacao_pontinhos.json
Task T003: verificar modelos .tflite

# Após T001 + T002:
Task T004: builders em gerador_pontinhos.py
# Após T004:
Task T005: gerar MD fixtures_correntes_pontinhos_3_4.md
```

### Phase 2 — Após T006-T012 concluídos

```bash
# T013 e T014 em paralelo (arquivos distintos):
Task T013: test_tipos_pontinhos_3_4.py
Task T014: test_minimax_pontinhos_di.py
```

### Phase 3 — US1

```bash
# T015 e T016 em paralelo (arquivos distintos):
Task T015: correntes_pontinhos_3_4.py (caixas_grau_3)
Task T016: stub de ia_pontinhos_3_4.py

# Após T015-T019, testes em paralelo:
Task T020: test_correntes_pontinhos_3_4.py (casos iniciais, usa builders T004)
Task T021: test_ia_pontinhos_3_4.py (cenários US1)
```

### Phase 4 vs Phase 5 — Com dois developers

```bash
# Após Phase 3 (US1) completa:
Developer A: T022-T026  # Phase 4 (US2 - double-dealing)
Developer B: T029-T033  # Phase 5 (US3 - CNN)

# Testes em paralelo dentro de cada developer:
Developer A: T027 + T028
Developer B: T034
```

### Phase 8 — Polish em paralelo

```bash
Task T046: pytest --cov (cobertura ≥ 90%)
Task T047: test_contrato_codificacao_pontinhos.py (CI)
```

---

## Canonical Test States — Distribution Reference

A tabela abaixo resume os 40 estados que `fixtures_correntes_pontinhos_3_4.md` (T005) deve conter e que `test_correntes_pontinhos_3_4.py` (T020 + T027) deve cobrir:

| Tipo | Builder | Variantes | Total | `tipo` esperado | `eh_corrente_longa` | `trigger_double_dealing` |
|---|---|---|---|---|---|---|
| Corrente curta (1–2 cx) | `construir_estado_corrente_curta(0..4)` | 5 | 5 | `"corrente"` | `False` | `False` |
| Corrente longa (3–7 cx) | `construir_estado_corrente_longa(0..4)` | 5 | 5 | `"corrente"` | `True` | `True` (com 2 últimas grau-3) |
| Ciclo de 4 | `construir_estado_ciclo(4, 0..4)` | 5 | 5 | `"ciclo"` | N/A | `True` (com 4 últimas grau-3) |
| Ciclo de 6 | `construir_estado_ciclo(6, 0..4)` | 5 | 5 | `"ciclo"` | N/A | `True` (com 4 últimas grau-3) |
| Ciclo de 8 | `construir_estado_ciclo(8, 0..4)` | 5 | 5 | `"ciclo"` | N/A | `True` (com 4 últimas grau-3) |
| Ciclo de 10 | `construir_estado_ciclo(10, 0..4)` | 5 | 5 | `"ciclo"` | N/A | `True` (com 4 últimas grau-3) |
| Ramificada | `construir_estado_ramificada(0..4)` | 5 | 5 | `"ramificada"` | N/A | `False` |
| Mistura | `construir_estado_mistura(0..4)` | 5 | 5 | múltiplos | misto | situacional |
| **Total** | | | **40** | | | |

Todos os estados usam domínio de partida `{-1, 0, 1, 8}` conforme `contrato_codificacao_pontinhos.json` contexto 3. O MD de visualização (T005) deve mostrar cada estado com representação ASCII legível por humano, facilitando validação visual antes da execução dos testes.

---

## API Pública de `correntes_pontinhos_3_4.py` — Design para Uso Futuro

O módulo é projetado para ser importado por três consumidores:

| Consumidor | Uso atual (esta feature) | Uso futuro (fora do escopo) |
|---|---|---|
| `ia_pontinhos_3_4.py` | `caixas_grau_3`, `detectar_estruturas`, `estrutura_ativa`, `trigger_double_dealing`, `aresta_double_cross`, `primeira_aresta_de_captura`, `estado_apos_captura_completa`, `estado_apos_double_cross` | — |
| `avaliador_partidas_pontinhos.py` | — | `detectar_estruturas` para classificar entrega de caixas pela CNN como erro vs. sacrifício/double-dealing |
| `visualizador_pontinhos.py` | — | `detectar_estruturas` para enriquecer visualizações com informação sobre estruturas ativas no tabuleiro |

O contrato de `detectar_estruturas(estado: EstadoTabuleiro) -> list[Estrutura]` é suficiente para todos os usos previstos. Nenhuma adição de API será necessária para os casos de uso futuros — apenas novos chamadores da função existente.

---

## Implementation Strategy

### MVP First (US1 + US2 — Pipeline Simbólico Completo)

1. Completar Phase 1: Setup (leituras obrigatórias + builders de fixtures)
2. Completar Phase 2: Foundational (tipos + minimax DI + testes)
3. Completar Phase 3: US1 (captura segura e gulosa)
4. Completar Phase 4: US2 (exceção double-dealing)
5. **PARAR e VALIDAR**: Agente captura e aplica double-dealing; 40+ testes de estruturas passando
6. Demonstrar se desejado

### Entrega Incremental

1. Setup + Foundational → base pronta (inclui 40+ estados canônicos prontos para testes)
2. US1 → captura básica determinística
3. US2 → controle de correntes/ciclos (MVP tático P1 completo)
4. US3 → CNN integrada com TFLite (fase tática sem garantia Minimax)
5. US4 → Minimax sobre TOP-5 + timer cooperativo P1/P2/P3 (P2 completo)
6. US5 → integração end-to-end + telemetria completa (P3 completo)
7. Polish → documentação obrigatória + cobertura ≥ 90% validada

---

## Summary

| Phase | Tasks | User Story | Arquivos Produzidos |
|---|---|---|---|
| 1 — Setup | T001–T005 | — | `gerador_pontinhos.py` (builders), `fixtures_correntes_pontinhos_3_4.md` |
| 2 — Foundational | T006–T014 | — | `tipos_pontinhos_3_4.py`, `minimax_pontinhos.py` (mod.), `test_tipos_*.py`, `test_minimax_di.py` |
| 3 — US1 | T015–T021 | US1 | `correntes_pontinhos_3_4.py` (v1), `ia_pontinhos_3_4.py` (stub+P1), `test_correntes_*.py` (v1), `test_ia_*.py` (v1) |
| 4 — US2 | T022–T028 | US2 | `correntes_pontinhos_3_4.py` (v2+BFS), `ia_pontinhos_3_4.py` (P2), `test_correntes_*.py` (v2+40 casos), `test_ia_*.py` (v2) |
| 5 — US3 | T029–T034 | US3 | `cnn_inferencia_pontinhos_3_4.py`, `ia_pontinhos_3_4.py` (P3), `test_cnn_inferencia_*.py` |
| 6 — US4 | T035–T040 | US4 | `ia_pontinhos_3_4.py` (P4+timer+aleatoriedade), `test_ia_*.py` (v3+v4) |
| 7 — US5 | T041–T043 | US5 | `ia_pontinhos_3_4.py` (revisão final), `test_ia_*.py` (v5), `test_partida_completa_*.py` |
| 8 — Polish | T044–T048 | — | `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md`, `docs/historico_decisoes.md` (upd.) |

**Total**: 48 tasks | **Testes**: 6 arquivos de teste novos | **Implementação**: 4 módulos novos + 2 modificados (`minimax_pontinhos.py`, `gerador_pontinhos.py`)

---

## Notes

- Ler `contrato_codificacao_pontinhos.json` (T002) é **obrigatório por CLAUDE.md** antes de qualquer mudança em pipeline de inferência ou construção de estados de tabuleiro
- Builders de T004 devem usar domínio de partida `{-1, 0, 1, 8}` — NUNCA `{0, 1, 8, 9}` (esse é o domínio do dataset/treino)
- `fixtures_correntes_pontinhos_3_4.md` (T005) é referência de revisão humana — se o MD parecer errado visualmente, os builders estão errados
- `correntes_pontinhos_3_4.py` **não depende** de `ia_pontinhos_3_4.py` — importável standalone por qualquer módulo
- `[P]` = arquivos distintos sem dependência ativa — pode rodar em paralelo
- `[US#]` = rastreabilidade para User Story de origem na spec.md
- Cobertura ≥ 90% nos módulos novos é requisito, não opcional (SC-008)
- `test_contrato_codificacao_pontinhos.py` é obrigatório no CI — **falha o merge** se JSON divergir do frontend (CLAUDE.md)
- Nível `expert` não tem modelo `.tflite` — `FileNotFoundError` é o comportamento correto, não implementar workaround
- Timer usa `time.monotonic_ns()` (não wall-clock) para portabilidade Windows/macOS/Linux (D10)
- Após editar módulos importados por notebooks, lembrar de reiniciar kernel (memória `feedback_jupyter_kernel_reload.md`)
- Commits após cada checkpoint (fim de fase) recomendados pelo hook `after_tasks`
