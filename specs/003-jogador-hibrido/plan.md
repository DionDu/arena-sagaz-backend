# Implementation Plan: Agente Híbrido `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-jogador-hibrido/spec.md`

**Note**: Este `plan.md` é a peça mestre da fase de planejamento. Decisões
técnicas detalhadas vivem em [`research.md`](./research.md); estruturas de
dados em [`data-model.md`](./data-model.md); contrato público da função em
[`contracts/api-python-pontinhos-3-4.md`](./contracts/api-python-pontinhos-3-4.md);
exemplos de uso em [`quickstart.md`](./quickstart.md).

## Summary

A `ia-pontinhos-3-4` é um agente híbrido para Dots-and-Boxes 3×4 que
combina **três camadas de decisão** (User Stories 1–4) com **degradação
graciosa por timeout** (FR-043 a FR-049):

1. **Vetos simbólicos** (Passos 1 e 2) — captura gulosa e exceção do
   double-dealing protegem a CNN dos pontos onde ela é provadamente fraca
   (controle de paridade em correntes longas).
2. **Convergência neural + tática** (Passos 3 e 4) — CNN sugere TOP-5
   arestas; Minimax depth=3 com poda alpha-beta veta jogadas que oferecem
   caixas no horizonte de 3 plies.
3. **Hierarquia de fallback por timer** (novo, FR-043 a FR-049) — três
   respostas candidatas com prioridade decrescente (P3 aleatória ≺ P2
   argmax CNN ≺ P1 jogada ideal). Quando `nu_timer_ms > 0` é fornecido em
   `MetadadosTurno`, o agente respeita o orçamento de tempo e devolve a
   melhor resposta já disponível em cada checkpoint.

A implementação preserva statelessness por chamada (com cache de
interpretadores TFLite protegido por lock), determinismo qualificado
(controlado por `seed_aleatoriedade`), e telemetria rica via
`ResultadoJogada` (suficiente para futura persistência em
`tb002_jogada`).

**Abordagem técnica** (consolidada de research.md):
- TFLite via `tensorflow.lite.Interpreter` (D1).
- Detecção de correntes/ciclos via BFS em grafo dual (D2).
- Minimax com função de avaliação injetada (DI obrigatória, D3).
- Arrays opcionais como `np.ndarray` `float32` shape `(31,)` com `np.nan`
  como sentinela canônica (D4).
- Configuração via dataclass com `__post_init__` derivando defaults do
  nível de dificuldade (D5).
- Single-thread por chamada com cache de interpretadores TFLite
  protegido por `threading.Lock` (D6).
- Determinismo via `np.random.default_rng(seed)` por chamada (D7); CNN
  determinística por garantia do TFLite runtime (D8).
- Erros propagam (sem fallback silencioso para Minimax puro quando TFLite
  falha) — D9.
- **Timer cooperativo via `time.monotonic_ns()` + checkpoints síncronos**
  (D10) — portátil Windows/macOS/Linux, sem custo no caminho feliz.

## Technical Context

**Language/Version**: Python 3.12+ (compatível com 3.13/3.14; observado
`__pycache__` em `cpython-312` e `cpython-314` no projeto).

**Primary Dependencies**:
- `tensorflow` (≥ 2.16) — runtime TFLite via `tensorflow.lite.Interpreter`.
  Isolado em `requirements_tf.txt` para não inflar o build da API.
- `numpy` (≥ 1.26) — arrays do tabuleiro, distribuições da CNN, RNG via
  `numpy.random.default_rng`.
- Standard library: `dataclasses`, `enum`, `typing`, `uuid`, `threading`,
  **`time` (`monotonic_ns`)**, `logging`, `collections` (`deque`).

**Storage**: N/A nesta feature. A futura persistência em `tb002_jogada`
(SQLite local + sync com servidor) é out-of-scope; esta feature entrega
apenas o objeto `ResultadoJogada` em memória, com schema canônico
suficiente para consumo posterior.

**Testing**:
- `pytest` + `pytest-cov` — testes unitários e de integração.
- Mocks via `unittest.mock` (sem dependência adicional). DI no Minimax
  (D3) habilita mocking limpo da função de avaliação.
- Cobertura mínima: 90% nos módulos novos (SC-008), excede o piso
  constitucional de 80% (Princípio III).

**Target Platform**: Desktop x86 (Windows/Linux/macOS). Foco inicial em
ambiente local para validar correção e integração; performance mobile
fica para feature futura de portabilidade Flutter (Clarification
2026-04-30).

**Project Type**: Biblioteca Python in-process (sem API HTTP nesta
feature). Consumida por `avaliador_partidas_pontinhos.py`,
`simulador_tatico_pontinhos.py` e — futuramente, em outra feature — pelo
app Flutter via FFI ou reescrita em Dart.

**Performance Goals** (SC-005, FR-026):
- p95 < 1000 ms por jogada em hardware desktop.
- p99 < 1500 ms.
- Média < 500 ms.
- Quando `nu_timer_ms > 0` é fornecido, o agente respeita o orçamento
  com slack ≈ 200ms (duração de uma sub-busca Minimax). Para
  `nu_timer_ms ≥ 800ms`, P1 é entregue na vasta maioria dos casos.

**Constraints**:
- Mesma seed de RNG produz mesma jogada (FR-024) — exceto em
  `percentual_aleatoriedade > 0` com `seed_aleatoriedade is None`.
- Conformidade absoluta com o contrato de codificação JSON
  (`gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`):
  normalização `8→0, -1→1, 9→1` aplicada imediatamente antes de
  `interp.set_tensor()` (FR-015, SC-009).
- Erro duro em qualquer divergência de contrato (D9).
- **Saída sempre garantida** quando há ao menos uma aresta livre (P3 é
  preparada antes de qualquer outro custo).

**Scale/Scope**:
- 1 jogo, 1 dimensão (3×4) — generalizações são out-of-scope.
- 31 arestas, 12 caixas — espaço de estado pequeno, branching factor
  inicial reduzido a 5 pelo Passo 4.
- 4 níveis de dificuldade configuráveis (`facil`, `medio`, `dificil`,
  `expert`); o nível `expert` está bloqueado pela inexistência do modelo
  `pontinhos_pequeno_profundidade_11.tflite`.

## Verificação da Constituição

*PORTÃO: aprovado antes da Fase 0 e reverificado após Fase 1.*

- [x] **I. Código Limpo**: módulos com responsabilidade única
  (`ia_pontinhos_3_4.py` orquestra; `correntes_pontinhos_3_4.py` detecta
  estruturas; `cnn_inferencia_pontinhos_3_4.py` encapsula TFLite;
  `tipos_pontinhos_3_4.py` agrega dataclasses/enums). Nomes em pt-BR
  expressivos (`escolher_jogada`, `caixas_grau_3`, `aresta_double_cross`).
  Sem duplicação: detecção de correntes não vive no agente; lógica do
  Minimax não vaza para o agente. **Timer adiciona ~30 linhas a
  `ia_pontinhos_3_4.py` em forma de helpers privados (`_elapsed_ms`,
  `_estourou_timer`, `_aresta_aleatoria_livre`, `_arg_max_arestas_livres`)
  — sem nova classe, sem nova abstração**.

- [x] **II. Tipagem Estática**:
  - Funções públicas com type hints completos (`escolher_jogada`,
    `caixas_grau_3`, etc.).
  - Estruturas internas: `@dataclass` (Princípio II permite `@dataclass`
    para dados internos in-process; Pydantic ficaria sobre a fronteira
    de sistema, que aqui é a futura tabela `tb002_jogada`).
  - `Any` evitado; quando a função de avaliação injetada precisa receber
    `EstadoTabuleiro`, o tipo é declarado via type alias
    `FuncaoAvaliacao = Callable[[EstadoTabuleiro, int, int], int]`.
  - **Timer**: `nu_timer_ms: int | None` em `MetadadosTurno`;
    `nu_tempo_calculo_ms: int` em `ResultadoJogada`.

- [x] **III. Testes Unitários**:
  - Cobertura ≥ 90% nos módulos novos (SC-008; supera o piso
    constitucional de 80%).
  - Mocks: função de avaliação Minimax mockada via DI (D3); CNN
    mockada via fixture com `numpy.ndarray` controlado;
    `_limpar_cache_interpretadores()` exposto para testes.
  - **Testes do timer**: 4 cenários novos — sem timer, timer largo (P1),
    timer apertado (P2), timer extremo (P3). Mock de `time.monotonic_ns`
    via `unittest.mock.patch` para simular estouros determinísticos.
  - Determinismo via `seed_aleatoriedade` torna os testes reprodutíveis.

- [x] **IV. Documentação Viva**:
  - Docstrings em pt-BR em todas as funções públicas (D9 reforça com
    mensagens de erro pt-BR).
  - Artefatos `.specify/`: spec.md, plan.md, research.md, data-model.md,
    contracts/, quickstart.md mantidos sincronizados.
  - `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md` deve ser
    criado quando a SPEC for ratificada (FR-031); este plano apenas
    referencia esse compromisso, sem implementá-lo aqui.
  - `docs/historico_decisoes.md` deve registrar a adoção do timer
    cooperativo quando a feature for ratificada (FR-030, memória
    `feedback_documentacao_viva.md`).

- [x] **V. Idioma pt-BR**:
  - Identificadores: `escolher_jogada`, `caixas_grau_3`, `aresta_double_cross`,
    `nu_timer_ms`, `nu_tempo_calculo_ms`, `aleatoria_timeout`,
    `cnn_timeout` — todos pt-BR ou termos técnicos sem tradução
    estabelecida (Minimax, Double-cross, TOP-5).
  - Comentários e docstrings exclusivamente pt-BR.
  - Logs (Princípio V, opt-in via `verbose=True`) em pt-BR.

**Resultado**: nenhuma violação. Não há entradas em "Complexity Tracking".

## Project Structure

### Documentation (this feature)

```text
specs/003-jogador-hibrido/
├── plan.md                    # Este arquivo (peça mestre)
├── spec.md                    # Especificação ratificada (fonte da verdade)
├── research.md                # Decisões técnicas D1–D10
├── data-model.md              # Estruturas de dados (dataclasses, enums)
├── quickstart.md              # Exemplos de uso (incluindo timer)
├── contracts/
│   └── api-python-pontinhos-3-4.md   # Contrato público Python
├── checklists/
│   └── requirements.md        # Checklist de qualidade da spec
└── tasks.md                   # (gerado por /speckit.tasks — não nesta fase)
```

### Source Code (repository root)

```text
gerador_dados/
└── jogo_pontinhos/
    ├── ia_pontinhos_3_4.py                  # NOVO — agente principal (orquestrador)
    ├── correntes_pontinhos_3_4.py           # NOVO — detector de correntes/ciclos (BFS grafo dual)
    ├── cnn_inferencia_pontinhos_3_4.py      # NOVO — wrapper TFLite (carrega, normaliza, inferir, top-k)
    ├── tipos_pontinhos_3_4.py               # NOVO — dataclasses + enums (Configuracao, Metadados, Resultado, etc.)
    ├── tabuleiro_pontinhos.py               # EXISTENTE — lógica genérica do jogo (parametrizável por dimensão)
    ├── minimax_pontinhos.py                 # EXISTENTE — Minimax com poda; ALTERADO (D3) p/ aceitar fn_avaliacao injetada
    ├── contrato_codificacao_pontinhos.json  # EXISTENTE — fonte única da verdade do encoding (NÃO ALTERAR nesta feature)
    └── contrato_codificacao_pontinhos.py    # EXISTENTE — helper de normalização

modelos/
├── pontinhos_pequeno_profundidade_6.tflite   # facil
├── pontinhos_pequeno_profundidade_7.tflite   # medio
├── pontinhos_pequeno_profundidade_9.tflite   # dificil (default)
└── pontinhos_pequeno_profundidade_11.tflite  # expert (NÃO EXISTE — bloqueia o nível)

tests/
├── unitarios/jogo_pontinhos/
│   ├── test_ia_pontinhos_3_4.py                       # NOVO — Passos 1–4 + timer
│   ├── test_correntes_pontinhos_3_4.py                # NOVO — detecção de correntes/ciclos
│   ├── test_cnn_inferencia_pontinhos_3_4.py           # NOVO — TFLite, normalização, top-k
│   ├── test_tipos_pontinhos_3_4.py                    # NOVO — validações de dataclasses
│   ├── test_minimax_pontinhos_di.py                   # NOVO — DI no Minimax (D3)
│   └── test_contrato_codificacao_pontinhos.py         # EXISTENTE — CI obrigatório
└── integracao/jogo_pontinhos/
    └── test_partida_completa_pontinhos_3_4.py         # NOVO — auto-jogo + win-rate vs Minimax puro
```

**Structure Decision**: a feature segue o layout existente do projeto
(`gerador_dados/jogo_pontinhos/`). Convenção de nomenclatura
hub-de-jogos (FR-028, memória `feedback_nomenclatura_hub.md`): arquivos
específicos a 3×4 levam sufixo `_pontinhos_3_4`; arquivos genéricos
(parametrizáveis por dimensão) levam sufixo `_pontinhos`. A diferença
está documentada na seção "Dependencies" da spec.

## Decisões Arquiteturais Críticas

Resumo das decisões; **detalhes em [`research.md`](./research.md)**.

| ID | Decisão | Onde |
|---|---|---|
| D1 | TFLite via `tensorflow.lite.Interpreter` | research.md |
| D2 | BFS sobre grafo dual para correntes/ciclos | research.md |
| D3 | DI obrigatória no Minimax (`fn_avaliacao` parâmetro com default) | research.md |
| D4 | `np.ndarray` float32 shape (31,) com `np.nan` como sentinela | research.md, data-model.md |
| D5 | `ConfiguracaoAgente` como `@dataclass` + `__post_init__` derivando defaults do nível | research.md, data-model.md |
| D6 | Single-thread por chamada com cache de interpretadores TFLite + Lock | research.md |
| D7 | RNG via `np.random.default_rng(seed)` por chamada | research.md |
| D8 | Determinismo da CNN garantido pelo runtime TFLite | research.md |
| D9 | Erro duro (raise) sem fallback silencioso | research.md |
| **D10** | **Cooperative timeout: `time.monotonic_ns()` + checkpoints síncronos** | **research.md** |

### Por que D10 (timer cooperativo) e não threading/signals

Ver `research.md > D10` para tabela completa de alternativas. O resumo:

- **`signal.SIGALRM`**: POSIX-only — inviável em Windows (ambiente
  principal de desenvolvimento).
- **`threading.Timer` + flag**: adiciona thread auxiliar por chamada
  (~1ms de overhead) sem cancelamento real — a flag ainda precisa ser
  checada cooperativamente nos mesmos pontos.
- **`concurrent.futures` com timeout**: não cancela trabalho — apenas
  descarta o resultado, mantendo CPU consumida.
- **Async/await**: refatoração ampla com custo desproporcional ao benefício.

A escolha de checkpoints síncronos preserva: portabilidade total
(Windows/macOS/Linux/futuro mobile), determinismo (sem race
conditions), simplicidade (sem dependências), e custo zero no caminho
feliz (3 chamadas de `monotonic_ns()` adicionam ~µs).

## Pseudo-Fluxo de Execução

Esta seção é um espelho do pseudo-algoritmo da spec, anotado com
referências aos módulos e helpers. **Implementação canônica** está em
`spec.md` § "Pseudo-Algoritmo" e em `data-model.md` (estruturas).

```text
escolher_jogada(estado, configuracao, metadados):
    inicio_ns = time.monotonic_ns()                                # D10
    nu_timer_ms = metadados.nu_timer_ms or 0
    rng = np.random.default_rng(configuracao.seed_aleatoriedade)   # D7

    # Prioridade 3 — preparada IMEDIATAMENTE
    fallback_p3 = _aresta_aleatoria_livre(estado, rng)             # ia_pontinhos_3_4
    fallback_p2 = None

    if _estourou_timer(inicio_ns, nu_timer_ms):                    # D10
        return _montar_resultado_timeout_aleatoria(...)

    caixas_grau3 = correntes_pontinhos_3_4.caixas_grau_3(estado)   # D2
    if caixas_grau3:
        # Passos 1 e 2 — vetos simbólicos
        estrutura = correntes_pontinhos_3_4.estrutura_ativa(...)
        if estrutura and trigger_double_dealing(estrutura, caixas_grau3):
            # Passo 2 — double-dealing via Minimax(depth=p) sobre A vs B
            scores_A = minimax_pontinhos.melhor_jogada_com_scores(estado_A, p,
                fn_avaliacao=avaliar)                              # D3
            scores_B = minimax_pontinhos.melhor_jogada_com_scores(estado_B, p,
                fn_avaliacao=avaliar)
            return _montar_resultado_us2(escolha=B if scores_B>=scores_A else A,
                                         scores_A, scores_B)
        else:
            # Passo 1 puro — captura gulosa
            return _montar_resultado_us1(...)

    # Passo 3 — Fase Tática (CNN)
    inferencia = cnn_inferencia_pontinhos_3_4.carregar_modelo(
        configuracao.caminho_modelo_cnn)                            # D1, D6
    distribuicao_31 = cnn_inferencia_pontinhos_3_4.inferir(
        inferencia, estado)                                         # contrato JSON
    fallback_p2 = _arg_max_arestas_livres(distribuicao_31, estado)

    if _estourou_timer(inicio_ns, nu_timer_ms):                    # D10
        return _montar_resultado_timeout_cnn(...)

    top5 = cnn_inferencia_pontinhos_3_4.top_k_arestas_livres(
        distribuicao_31, estado, k=5)

    # Passo 4 — Validação Minimax
    scores_31 = tipos_pontinhos_3_4.array_31_com_nan()              # D4
    for (aresta, prob) in top5:
        if _estourou_timer(inicio_ns, nu_timer_ms):                 # D10
            return _montar_resultado_timeout_cnn(scores_parciais=scores_31)
        scores_31[idx(aresta)] = minimax_pontinhos.minimax(
            estado_sucessor(estado, aresta),
            profundidade=configuracao.profundidade_minimax,
            fn_avaliacao=avaliar)                                   # D3

    melhor_aresta = _arg_max_com_tiebreak(scores_31, top5)          # FR-023

    # Aleatoriedade do Passo 4 (FR-042) — só em P1, não em P2/P3
    if rng.random() < configuracao.percentual_aleatoriedade:
        melhor_aresta = rng.choice([a for (a, _) in top5])          # D7

    return _montar_resultado_us3_4(melhor_aresta, distribuicao_31, scores_31)
```

## Determinismo e Tie-breakers (resumo)

| Origem do empate | Tie-breaker | Onde |
|---|---|---|
| Múltiplas caixas grau-3 isoladas | Menor índice canônico no contrato JSON | FR-004 |
| Score Minimax igual em A vs B (Passo 2) | Prefere B (sacrifício / controle de paridade) | FR-008 |
| Score Minimax igual entre arestas TOP-5 (Passo 4) | Prefere a de maior probabilidade na CNN | FR-023 |
| Múltiplas arestas com mesma probabilidade na CNN | Menor índice canônico (filtragem estável) | Edge Case "tabuleiro simétrico" |
| Múltiplas arestas livres para fallback P3 | `rng.choice` com seed da `ConfiguracaoAgente` (D7) | FR-045 |

## Tratamento de Erros (resumo)

| Cenário | Política | Onde |
|---|---|---|
| Tabuleiro terminal (sem arestas livres) | `ValueError` propagado | api-python-*.md |
| `nu_jogador ∉ {1, -1}` | `ValueError` em `MetadadosTurno.__post_init__` | data-model.md |
| `nu_timer_ms < 0` | `ValueError` em `MetadadosTurno.__post_init__` | data-model.md |
| `profundidade_minimax < 1` | `ValueError` em `ConfiguracaoAgente.__post_init__` | data-model.md |
| `caminho_modelo_cnn` não existe | `FileNotFoundError` na primeira inferência | api-python-*.md |
| TFLite falha ao carregar | `RuntimeError` (sem fallback silencioso, D9) | api-python-*.md |
| CNN retorna NaN/inf | `RuntimeError` (sem fallback silencioso, D9) | api-python-*.md |
| Tensor pós-normalização ≠ {0, 1} | `AssertionError` (sinaliza bug de contrato) | api-python-*.md |
| Timer estoura antes de qualquer cálculo significativo | **NÃO é erro** — retorna fallback P3 com `co_acao = aleatoria_timeout` | spec.md FR-049 |

## Testes Planejados (alto nível; detalhes em `tasks.md` na fase seguinte)

### Unitários

- `test_correntes_pontinhos_3_4.py` — 12+ casos canônicos: corrente curta,
  corrente longa, ciclo de 4/6/8/10, estrutura ramificada, mistura.
- `test_cnn_inferencia_pontinhos_3_4.py` — carregamento, normalização,
  inferência, top-k, cache + lock, erro em modelo inexistente,
  determinismo (mesmo input → mesmo top-5).
- `test_minimax_pontinhos_di.py` — DI funciona; default == comportamento
  legado; mock de função de avaliação altera score conforme esperado.
- `test_tipos_pontinhos_3_4.py` — validações de `ConfiguracaoAgente`,
  `MetadadosTurno` (incluindo `nu_timer_ms < 0`), `ResultadoJogada`
  (invariantes FR-038, FR-049).
- `test_ia_pontinhos_3_4.py` — Passo 1 (captura grau-3 isolada), Passo 2
  (corrente longa, ciclo, tie-breaker B), Passos 3+4 (CNN+Minimax,
  veto tático), e:
  - **Timer sem estouro** (P1 retornada, `nu_tempo_calculo_ms <
    nu_timer_ms`).
  - **Timer estoura após CNN** (P2 retornada, `co_acao = cnn_timeout`,
    `ar_probabilidade_cnn` preenchido, `ar_score_minimax` parcial ou
    `None`).
  - **Timer estoura no início** (P3 retornada,
    `co_acao = aleatoria_timeout`, todos os campos opcionais `None`).
  - **Sem timer** (`nu_timer_ms = None`): comportamento idêntico ao
    legado v1.0.0; `nu_tempo_calculo_ms` reportado mesmo assim.
  - Mock de `time.monotonic_ns` via `unittest.mock.patch` para forçar
    estouros determinísticos sem flakiness.

### Integração

- `test_partida_completa_pontinhos_3_4.py`:
  - Auto-jogo `ia-pontinhos-3-4` vs `ia-pontinhos-3-4` (100 partidas;
    SC-003, SC-007).
  - Win-rate vs Minimax puro depth=5 (200 partidas; SC-006).
  - **Cenário com timer**: 50 partidas com `nu_timer_ms = 200` —
    verificar que pelo menos 80% das jogadas retornam P1 e que jamais
    há jogada inválida.

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| TFLite muda comportamento numérico em release futura | Baixa | Médio (cobrindo SC-002) | Travar versão de `tensorflow` em `requirements_tf.txt`; teste de regressão "saída fixa" com seed fixada |
| CNN aprende padrão que oferece caixas — Minimax nunca consegue corrigir | Baixa | Alto (compromete SC-006) | TOP-5 da CNN + Minimax depth=3 já mitiga; SC-006 mede; se falhar, considerar features posicionais (Clarification 2026-04-30) |
| Cache de interpretadores TFLite vaza memória sob uso prolongado | Muito baixa | Baixo | `_limpar_cache_interpretadores()` exposto para limpeza periódica; testes de stress no avaliador |
| `expert` é configurado em produção sem o modelo `profundidade_11.tflite` | Média | Médio (UX quebrada) | `FileNotFoundError` em `cnn_inferencia_pontinhos_3_4.carregar_modelo` é claro e acionável; mensagem em pt-BR explica que o modelo precisa ser treinado |
| **Timer estoura antes mesmo da P3 (extremamente raro com `np.random.default_rng`)** | **Muito baixa** | **Alto (sem saída garantida)** | **P3 é preparada antes de qualquer custo computacional significativo (cf. spec FR-045). Helper `_aresta_aleatoria_livre` usa apenas `rng.choice` sobre lista de arestas livres do `EstadoTabuleiro` — operação µs em tabuleiro 3×4** |
| Slack do timer (200ms) é inaceitável para timers muito apertados (< 100ms) | Média (nicho) | Baixo | Documentado em `quickstart.md` § 6.5; agente devolve P2/P3 sob esses regimes — comportamento esperado, não defeito |

## Pós-Fase 1: Reverificação da Constituição

Reanálise após design completo (research.md, data-model.md, contracts/,
quickstart.md):

- ✅ **I. Código Limpo** — adicionar timer não introduziu nova classe ou
  abstração; helpers privados pequenos (`_elapsed_ms`, etc.).
- ✅ **II. Tipagem Estática** — todos os campos novos têm type hints
  (`int | None`, `int`); enums expandidos preservam type-safety.
- ✅ **III. Testes Unitários** — 4 cenários novos para o timer com
  estratégia de mock determinística (patch `monotonic_ns`).
- ✅ **IV. Documentação Viva** — spec.md, plan.md, research.md,
  data-model.md, contracts/, quickstart.md atualizados na mesma sessão.
- ✅ **V. Idioma pt-BR** — todos os identificadores novos em pt-BR
  (`nu_timer_ms`, `nu_tempo_calculo_ms`, `aleatoria_timeout`,
  `cnn_timeout`); termos técnicos preservados (timeout, fallback).

**Resultado: aprovado, sem novas violações.**

## Complexity Tracking

> **Sem violações que exijam justificativa.**

A introdução do timer cooperativo poderia ter sido implementada de
formas mais complexas (threading, async, multiprocessing — ver D10), mas
a opção escolhida (checkpoints síncronos com `monotonic_ns`) é a mais
simples disponível. Nenhuma complexidade adicional foi introduzida sem
necessidade.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| (nenhuma) | — | — |
