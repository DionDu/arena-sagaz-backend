# Pesquisa Técnica: Agente `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Data**: 2026-05-01

Este documento consolida as decisões técnicas tomadas durante o planejamento.
Como a SPEC encerrou todas as Open Questions em sessões de Clarification, este
documento foca em **como** as decisões serão executadas, com alternativas
consideradas.

---

## D1 — Biblioteca de Inferência TFLite

### Decisão

Usar `tensorflow.lite.Interpreter` (do pacote `tensorflow`).

### Justificativa

- **Compatibilidade Python ≥ 3.12**: builds oficiais de `tflite_runtime` ficaram
  frágeis em Python 3.13/3.14 (anotação herdada do `requirements.txt`). O
  pacote `tensorflow` mantém builds atualizados para o Python da casa.
- **API idêntica**: `tensorflow.lite.Interpreter` expõe o mesmo conjunto de
  métodos que `tflite_runtime.Interpreter` (`set_tensor`, `invoke`,
  `get_tensor`, `allocate_tensors`, `get_input_details`,
  `get_output_details`). Migrar para um runtime mais leve no futuro é uma
  troca de import.
- **Já no pipeline**: a geração de dataset (Databricks) e o treino (Colab) já
  usam TF; manter o backend desktop também em TF reduz divergência de versões
  e facilita reprodução de bugs.
- **Isolamento de instalação**: `tensorflow` permanece em
  `requirements_tf.txt` (separado de `requirements.txt`), evitando inflar o
  build da API quando ela for exposta em produção.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| `tflite_runtime` direto | Builds frágeis em Python ≥ 3.13; postergado para a feature de portabilidade mobile, quando o ambiente for fixado em 3.11/3.12 |
| `ai_edge_litert` (sucessor lightweight do Google) | Muito recente; sem maturidade comprovada no nosso pipeline. Avaliar em feature dedicada |
| ONNX Runtime + conversão TFLite→ONNX | Adiciona uma etapa extra de conversão e retreino; a CNN já está em TFLite |

### Impacto na arquitetura

- `cnn_inferencia_pontinhos_3_4.py` importa `tensorflow.lite as tflite`.
- O wrapper expõe apenas a interface mínima (`carregar_modelo`, `inferir`,
  `top_k_arestas_livres`). Quando vier a troca para `tflite_runtime`, basta
  alterar o import no topo do módulo.

---

## D2 — Algoritmo de Detecção de Correntes e Ciclos

### Decisão

BFS sobre **grafo dual** do tabuleiro, onde:
- Vértices = caixas com grau ∈ {2, 3} (uncaptured, estruturalmente relevantes).
- Arestas-do-grafo = par de caixas adjacentes que compartilham uma aresta-do-
  jogo NÃO preenchida.

Classificação por grau-no-grafo dos nós da componente conexa:
- Todos os nós com grau-no-grafo == 2 → **ciclo**.
- Exatamente 2 nós com grau-no-grafo == 1 e demais com grau == 2 → **corrente**.
- Algum nó com grau-no-grafo ≥ 3 → **ramificada** (não dispara double-dealing).

### Justificativa

- **Linear no tamanho**: BFS é O(V+E), e em 3×4 temos no máximo 12 caixas e
  31 arestas-do-jogo, então a detecção é trivial em CPU.
- **Sem dependências externas**: implementado em Python puro com `collections.deque`
  e `set`/`dict`.
- **Modelo padrão da literatura** (Berlekamp, *Winning Ways*): o "dual graph"
  de Dots-and-Boxes é a forma canônica de raciocinar sobre correntes/ciclos.
- **Reaproveitável**: o algoritmo é genérico em dimensão; quando o sufixo
  `_3_4` for retirado em sessão dedicada, o módulo se torna `correntes_pontinhos.py`
  sem alteração de lógica.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| Detecção por padrões hard-coded (templates) | Frágil; não escala para diferentes dimensões; difícil de testar exaustivamente |
| Union-Find sobre arestas livres | Identifica componentes mas não classifica chain/cycle/branching diretamente; precisaria pós-processamento |
| Pacote externo (`networkx`) | Dependência adicional para algoritmo de 30 linhas; overhead de instalação injustificado |

### Impacto na arquitetura

- `correntes_pontinhos_3_4.py` exporta:
  - `caixas_grau_3(estado) -> list[tuple[int, int]]`
  - `detectar_estruturas(estado) -> list[Estrutura]`
  - `estrutura_ativa(estado, caixas_grau_3) -> Estrutura | None`
  - `trigger_double_dealing(estrutura, caixas_grau_3) -> bool`
  - `aresta_double_cross(estrutura, estado) -> str`
  - `estado_apos_captura_completa(estado, estrutura, jogador) -> EstadoTabuleiro`
  - `estado_apos_double_cross(estado, estrutura, jogador) -> EstadoTabuleiro`
  - `primeira_aresta_de_captura(estrutura, estado) -> str`

---

## D3 — Padrão de Injeção de Dependência no Minimax

### Decisão

Adicionar parâmetro `fn_avaliacao: Callable[[EstadoTabuleiro, int, int], int] = avaliar`
à função `minimax(...)` em `minimax_pontinhos.py`. O default aponta para a
função `avaliar` já existente, garantindo compatibilidade retroativa.

### Justificativa

- **Compatibilidade total**: callers existentes (`avaliador_partidas_pontinhos`,
  `gerador_pontinhos`, `melhor_jogada`, etc.) não precisam mudar — recebem
  o comportamento atual via default.
- **Zero overhead em produção**: passar uma referência de função é trivial;
  o mesmo bytecode é executado quando o default é usado.
- **Testabilidade**: testes do agente podem mockar `fn_avaliacao` para isolar
  a busca do score. Testes de regressão garantem que default == comportamento
  legado.
- **Conformidade com a Clarification 2026-04-30**: "DI obrigatória".

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| Classe `MinimaxRunner` com método `avaliar()` sobrescritível | Quebra a função pura existente; força refator dos callers; adiciona estado mutável |
| Função separada `minimax_com_avaliacao(...)` | Bifurca a base de código; risco de duas implementações divergirem |
| Variável global mutável `AVALIACAO_ATIVA` | Anti-padrão (estado global); impossibilita execução paralela de testes com mocks diferentes |
| Decorator `@avaliacao(fn)` antes da chamada | Magia desnecessária para passar uma função; menos explícito que parâmetro |

### Impacto na arquitetura

- `minimax_pontinhos.py` ganha:
  - Novo type alias: `FuncaoAvaliacao = Callable[[EstadoTabuleiro, int, int], int]`.
  - Parâmetro novo (com default) em `minimax`, `_scores_de_todas_jogadas`,
    `melhor_jogada`, `melhor_jogada_com_scores`.
- O agente passa `fn_avaliacao=avaliar` explicitamente para deixar a intenção
  clara no código (mesmo sendo o default), sinalizando ao leitor que a
  estratégia de avaliação é uma escolha consciente do agente.

---

## D4 — Sentinela e Layout das Arrays Opcionais (`ar_score_minimax`, `ar_probabilidade_cnn`)

### Decisão

`numpy.ndarray` com `dtype=np.float32`, `shape=(31,)`, sentinela `numpy.nan`
para posições não-avaliadas. Já oficializado em FR-038 e na Clarification
2026-04-30.

### Justificativa (recapitulação)

- **Indexabilidade direta**: `array[i] == score_da_aresta_i` (i = índice
  canônico do contrato JSON). Permite jointar com o vetor de saída da CNN
  via slice.
- **Filtragem vetorizada**: `np.isnan(arr)` em O(n).
- **Sem colisão semântica**: scores Minimax legítimos podem ser `0`, negativos
  ou positivos — qualquer valor numérico é "real". `numpy.nan` é o único
  sentinela seguro.
- **Compatibilidade futura com persistência JSON**: `numpy.nan` serializa para
  `null` em conversores comuns (`pandas.DataFrame.to_json` com
  `default_handler`); `None` direto não é suportado em arrays NumPy de
  `float32`.

### Helper canônico

`tipos_pontinhos_3_4.array_31_com_nan() -> np.ndarray` retorna uma nova array
preenchida com `nan`. Toda construção de array opcional no agente passa por
esse helper para garantir uniformidade.

---

## D5 — Padrão de Derivação de `ConfiguracaoAgente` a Partir de `NivelDificuldade`

### Decisão

`@dataclass` mutável com `__post_init__` que consulta uma constante
module-level `MAPEAMENTO_NIVEIS: dict[NivelDificuldade, dict[str, Any]]`.
Para qualquer campo passado como `None`, o default do nível é aplicado;
campos explicitamente passados sobrescrevem.

### Justificativa

- **Override granular** (Clarification): permitir, ex., `ConfiguracaoAgente(nivel='facil', profundidade_minimax=3)`
  para fixar profundidade independente do nível.
- **Sem mágica**: o usuário lê o código, vê a tabela, entende o mapeamento.
- **Testável**: `MAPEAMENTO_NIVEIS` é uma constante pública; testes podem
  parametrizar sobre todos os níveis.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| Subclasses por nível (`ConfiguracaoFacil`, ...) | Polimorfismo desnecessário para configuração estática; complica typing |
| Factory `ConfiguracaoAgente.de_nivel('facil', overrides={...})` | Adiciona segundo construtor; menos uniforme do que `__post_init__` |
| Enum com payload (Python `Enum` + `tuple` value) | Limitação para overrides parciais; menos legível |

### Tabela canônica (replicada da SPEC para conveniência)

| Nível | Modelo CNN | Profundidade | Aleatoriedade |
|---|---|---|---|
| `facil` | `modelos/pontinhos_pequeno_profundidade_6.tflite` | 1 | 0.30 |
| `medio` | `modelos/pontinhos_pequeno_profundidade_7.tflite` | 2 | 0.15 |
| `dificil` | `modelos/pontinhos_pequeno_profundidade_9.tflite` | 3 | 0.05 |
| `expert` | `modelos/pontinhos_pequeno_profundidade_11.tflite` ⚠️ | 3 | 0.00 |

⚠️ `profundidade_11.tflite` ainda não existe. Tentar `expert` levanta
`FileNotFoundError` em `cnn_inferencia_pontinhos_3_4.carregar_modelo`.

---

## D6 — Modelo de Concorrência

### Decisão

**Single-thread por chamada** de `escolher_jogada`. O cache de interpretadores
TFLite é compartilhado entre chamadas (module-level dict), e cada interpretador
é protegido por `threading.Lock` para a sequência crítica
`set_tensor → invoke → get_tensor`.

### Justificativa

- **TFLite Interpreter NÃO é thread-safe**: a sequência crítica precisa de
  exclusão mútua. Sem lock, chamadas concorrentes corrompem o tensor de saída.
- **Single-thread é suficiente** para SC-005 (p95 < 1000 ms) em hardware
  desktop x86 — um modelo BoxNet de 74.5k parâmetros + Minimax depth=3 sobre
  TOP-5 roda muito abaixo do orçamento.
- **Defensiva contra paralelização futura**: o `avaliador_partidas_pontinhos.py`
  já usa `concurrent.futures` para rodar várias partidas em paralelo; o lock
  protege esse caso quando o agente for plugado lá.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| Um interpretador por chamada (sem cache) | Recarregar TFLite custa ~50–200ms; estouraria SC-005 |
| Pool de interpretadores | Complexidade extra para ganho marginal em modo single-thread |
| Async/await | TFLite é CPU-bound síncrono; async não ajuda |

### Impacto na arquitetura

- `cnn_inferencia_pontinhos_3_4.py` mantém:
  - `_CACHE_INTERPRETADORES: dict[str, Interpreter]`
  - `_LOCKS_INTERPRETADORES: dict[str, Lock]`
- Função privada `_obter_interpretador(caminho)` retorna `(Interpreter, Lock)`
  e é chamada por `inferir(...)`.
- Função `_limpar_cache_interpretadores()` exposta apenas para testes.

---

## D7 — Estratégia de Determinismo

### Decisão

- `numpy.random.default_rng(seed)` instanciado **por chamada** de
  `escolher_jogada`. Nunca usar `random.seed()` global ou `np.random.seed()`
  global (efeito colateral em outras partes do programa).
- Tie-breakers determinísticos definidos por regra escrita (vide tabela no
  `plan.md` seção "Determinismo e Tie-breakers").

### Justificativa

- **Não-vazamento entre chamadas**: dois agentes operando em threads diferentes
  ou em alternância não interferem na semente um do outro.
- **Reprodutibilidade exata**: `default_rng(42).integers(0, 5)` produz sempre
  o mesmo valor, em qualquer ambiente que rode NumPy compatível.
- **Decorrelação CNN/Minimax**: a CNN é determinística por garantia do TFLite
  (D8); a aleatoriedade existe apenas no Passo 4 e é controlável pela
  configuração.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| `random.Random(seed)` (stdlib) | NumPy oferece `default_rng` com geradores PCG64 mais robustos; manter consistência com NumPy |
| `np.random.seed()` global | Efeito colateral em código que compartilha o módulo NumPy |
| `secrets.SystemRandom` | Não-reprodutível; oposto do que queremos |

---

## D8 — Determinismo da CNN

### Decisão

Confiar na garantia do runtime TFLite: para o mesmo tensor de entrada, o
modelo retorna o mesmo tensor de saída. Documentado pela Google;
empiricamente válido para `Interpreter` em CPU.

### Riscos residuais e mitigação

- **Sequência crítica**: garantida pelo `Lock` em D6 (sem reentrância
  concorrente).
- **Mudança de versão do TF**: novas versões podem alterar comportamento
  numérico (raríssimo). Mitigação: travar versão de `tensorflow` em
  `requirements_tf.txt`; teste de regressão `test_cnn_inferencia_pontinhos_3_4.py`
  inclui um teste de "saída fixa" (mesmo input → mesmo top-5 com seed
  fixado).

---

## D9 — Política de Erros

### Decisão

**Erro duro** (raise) em qualquer violação de contrato. Sem fallback silencioso
para Minimax puro quando TFLite falha. Mensagens de erro em pt-BR,
explicitando a causa.

### Justificativa

- **Bug é melhor visível do que mascarado**: silenciar a falha do TFLite levou
  ao bug histórico de 2026-04-23 (regressão de 39pp na win-rate quando o
  domínio do tensor estava errado).
- **Conformidade com Clarification 2026-04-30**: "Falha do modelo TFLite:
  Deve ser um ERRO DURO".
- **Diagnóstico fácil**: o avaliador de partidas e o simulador veem a
  exceção propagar e sabem exatamente onde olhar.

### Tabela completa em `plan.md` (seção "Tratamento de Erros").

---

## D10 — Mecanismo de Cooperative Timeout (Controle de Tempo / Fallback)

### Decisão

**Checkpoints síncronos com `time.monotonic_ns()`** chamados em pontos
específicos do pipeline:

1. Imediatamente após preparar a Prioridade 3 (aleatória) — antes de detectar
   caixas grau-3.
2. Após a inferência da CNN (Passo 3), antes de iniciar Minimax.
3. **Dentro do laço** sobre TOP-5 do Minimax, **antes de cada iteração**.

Quando `nu_timer_ms > 0` E `monotonic_ns() - inicio_ns > nu_timer_ms * 1e6`,
o agente retorna a melhor resposta já disponível (P1 > P2 > P3) e marca
`co_acao` com `cnn_timeout` ou `aleatoria_timeout` conforme o caso.

### Justificativa

- **Portabilidade Windows/macOS/Linux**: `time.monotonic_ns()` é parte da
  stdlib desde Python 3.7, com semântica idêntica em todos os SOs. **Crítico
  porque**: o avaliador desktop atual roda em Windows (DionDu), CI/CD
  futuro pode ser Linux, e quando portarmos a lógica para o app Flutter
  o equivalente Dart (`Stopwatch`) tem semântica análoga. Soluções
  específicas de Linux (signal.SIGALRM) seriam impossíveis no Windows e
  no app móvel.
- **Resolução nanossegundos**: `monotonic_ns()` é robusto contra ajustes
  de wall-clock (NTP, mudança manual de horário). Crítico para
  benchmarking justo de `nu_tempo_calculo_ms`.
- **Determinismo**: checkpoints são síncronos e estritamente sequenciais —
  a ordem de execução é a mesma toda vez. Não há race condition entre
  thread de timer e thread de cálculo.
- **Granularidade de interrupção adequada**: Minimax depth=3 sobre TOP-5
  faz no máximo 5 sub-buscas; cada uma custa < 200 ms em hardware-alvo.
  Verificar timeout entre as 5 sub-buscas oferece resolução de ~200 ms,
  suficiente para `nu_timer_ms` de centenas de ms a alguns segundos
  (faixa típica de jogos turn-based).
- **Sem custo no caminho feliz**: 3 checkpoints adicionam ~µs cada quando
  o timer não estoura — invisível dentro do orçamento de SC-005.

### Alternativas consideradas

| Alternativa | Por que rejeitada |
|---|---|
| `signal.SIGALRM` + handler que dispara exceção | **Não funciona em Windows** (signal.SIGALRM é POSIX-only). Inviável dado que o ambiente principal de desenvolvimento é Windows. Adicionalmente, não pode ser usado fora da main thread (limitação adicional para integração futura) |
| `threading.Timer` cancelando uma flag compartilhada | Adiciona thread auxiliar por chamada (overhead de criação ~1ms, comparável ao timer mais curto que faria sentido). A flag ainda precisa ser checada cooperativamente nos mesmos pontos — não traz cancelamento real, só esconde a complexidade |
| `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=…)` | Não cancela trabalho em andamento (apenas o resultado é descartado); a thread continua consumindo CPU. Pior que checkpoints porque desperdiça ciclos após o timeout |
| `multiprocessing` com timeout no `join()` | Cancela de fato (kill do processo), mas overhead de spawn de processo (~50–200ms) é comparável a uma jogada inteira; inviável |
| Refatorar Minimax para `async` + `asyncio.wait_for(...)` | Exigiria refatoração ampla de `minimax_pontinhos.py` e quebraria callers existentes (`avaliador_partidas`, `gerador_pontinhos`); custo desproporcional ao benefício |
| Bibliotecas externas (`stopit`, `wrapt-timeout-decorator`) | Adicionar dependência para problema solucionável em ~20 linhas com stdlib. Anti-padrão por Princípio I (Código Limpo) |

### Posicionamento dos checkpoints — racional detalhado

| Checkpoint | Custo até aqui | Justificativa do posicionamento |
|---|---|---|
| **Após preparar P3 (aleatória)** | < 1ms (escolha de aresta livre uniformemente) | Defesa em profundidade. Em prática nunca deve estourar — mas garante que o invariante "resposta disponível em qualquer instante" é satisfeito |
| **Após inferência CNN (antes do Minimax)** | ~10–50ms (carregamento de modelo cacheado + inferência) | Ponto natural de transição: a CNN argmax (P2) acabou de ficar pronta. Vale checar antes de entrar no Minimax que pode adicionar centenas de ms |
| **Antes de cada iteração do laço TOP-5 do Minimax** | acumulativo, até ~700ms em depth=3 | É onde o tempo é consumido. Verificar entre iterações é a granularidade certa: não interromper no meio de uma sub-busca (custo de invalidar resultado parcial), mas também não esperar todas as 5 (que é o caso onde o timer realmente importa) |

Dentro de cada chamada recursiva do Minimax (níveis 2, 1, 0 de profundidade)
**não** há checkpoint — o overhead seria significativo e a granularidade já
adequada está nos níveis externos.

### Impacto na arquitetura

- `ia_pontinhos_3_4.py` ganha:
  - Função interna `_elapsed_ms(inicio_ns: int) -> int` para calcular o
    tempo decorrido em ms a partir de `time.monotonic_ns()`.
  - Função interna `_estourou_timer(inicio_ns: int, nu_timer_ms: int) -> bool`.
  - Função interna `_aresta_aleatoria_livre(estado: EstadoTabuleiro,
    rng: np.random.Generator) -> str` — preparação da P3.
  - Função interna `_arg_max_arestas_livres(distribuicao: np.ndarray,
    estado: EstadoTabuleiro) -> str` — preparação da P2.
- `minimax_pontinhos.py` **NÃO** é alterado (continua sendo síncrono e
  bloqueante). O laço sobre TOP-5 fica em `ia_pontinhos_3_4.py`, e é nele
  que os checkpoints residem.
- O RNG usado para P3 é o mesmo `np.random.Generator` instanciado em D7
  (com seed da `ConfiguracaoAgente`). Garante reprodutibilidade quando
  `seed_aleatoriedade` é fornecida.

### Garantias

1. **Sempre retorna**: enquanto houver pelo menos uma aresta livre no
   `estado`, P3 está pronta antes de qualquer outro custo. Se o timer
   estourar antes mesmo de detectar fase, P3 é retornada com
   `co_acao = "aleatoria_timeout"` e `co_situacao = "tatica"` (default).
2. **Resolução máxima de slack**: o tempo efetivamente gasto pode exceder
   `nu_timer_ms` por até a duração de uma sub-busca Minimax (~200ms em
   depth=3). Isto é aceitável para a faixa típica de uso (timers de
   centenas de ms ou mais). Para timers muito apertados (< 100ms), o
   agente quase sempre devolverá P2 ou P3.
3. **Telemetria completa em `nu_tempo_calculo_ms`**: medido sempre, mesmo
   quando o timer não foi configurado (útil para benchmarking offline).

---

## Síntese: por que esta arquitetura

A arquitetura híbrida de 4 passos não é "uma CNN com filtros simbólicos
acoplados" — é um **pipeline com vetos**:

1. Passos 1 e 2 são **vetos simbólicos** que protegem a CNN dos pontos onde
   ela é provadamente fraca (conforme `argumentacao_cnn_vs_minimax.md`):
   capturas pendentes e controle de paridade em correntes longas.
2. Passos 3 e 4 são **convergência neural + tática**: a CNN sugere as 5
   jogadas mais promissoras, e o Minimax depth=3 verifica que nenhuma
   delas oferece caixas no horizonte de 3 plies.

Cada decisão técnica acima preserva essa estrutura: módulos genéricos
(Tier 1) entregam a infraestrutura matemática; módulos específicos (Tier 2)
implementam a lógica do agente; o orquestrador (`ia_pontinhos_3_4`) costura
sem misturar tiers.
