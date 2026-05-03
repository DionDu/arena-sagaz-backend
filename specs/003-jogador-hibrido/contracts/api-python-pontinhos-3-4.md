# Contrato Python: `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Data**: 2026-05-01

Este documento define o **contrato público Python** do agente: assinaturas,
pré e pós-condições, exceções e invariantes. É o que consumidores
(`avaliador_partidas_pontinhos`, `simulador_tatico_pontinhos`, futuro App
Flutter via FFI) podem assumir e o que o agente garante.

---

## Superfície Pública

```python
# gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py

def escolher_jogada(
    estado: EstadoTabuleiro,
    configuracao: ConfiguracaoAgente,
    metadados: MetadadosTurno,
) -> ResultadoJogada: ...
```

Tudo o mais (`tipos_pontinhos_3_4.*`, `correntes_pontinhos_3_4.*`,
`cnn_inferencia_pontinhos_3_4.*`) é **suporte**: os tipos podem ser importados
do `tipos_pontinhos_3_4` para construir os argumentos, mas a função
`escolher_jogada` é o único entry-point.

---

## Assinatura completa

```python
def escolher_jogada(
    estado: EstadoTabuleiro,
    configuracao: ConfiguracaoAgente,
    metadados: MetadadosTurno,
) -> ResultadoJogada:
    """Escolhe a próxima jogada do agente híbrido `ia-pontinhos-3-4`.

    Pipeline determinístico em 4 passos com degradação graciosa por
    timeout (3 prioridades de saída):
        1. Captura segura/gulosa (caixa grau-3 sem ser final de corrente longa).
        2. Exceção do sacrifício (double-cross em final de corrente/ciclo).
        3. Fase tática via CNN (TOP-5 arestas).
        4. Validação Minimax depth=N sobre as TOP-5.

    Quando `metadados.nu_timer_ms > 0` é fornecido, o pipeline mantém
    três respostas candidatas com prioridade decrescente (P3 ≺ P2 ≺ P1):
        P3. Aresta livre uniformemente aleatória, preparada IMEDIATAMENTE
            no acionamento — piso garantido de saída.
        P2. Argmax da distribuição da CNN entre arestas livres (sem
            Minimax), preparada após inferência da CNN — só na fase tática.
        P1. Saída do pipeline completo (Passos 1–4) — jogada ideal.
    Em cada checkpoint (após P3, após CNN, antes de cada iteração do
    Minimax sobre TOP-5), se o tempo decorrido excede `nu_timer_ms`, o
    agente retorna a melhor resposta já disponível e marca `co_acao`
    com `cnn_timeout` (P2) ou `aleatoria_timeout` (P3).

    O tempo é medido com `time.monotonic_ns()` (não wall-clock) e
    reportado em `ResultadoJogada.nu_tempo_calculo_ms` mesmo quando
    `nu_timer_ms` não foi configurado (útil para benchmarking offline).

    Args:
        estado: Estado atual do tabuleiro 3×4 (linhas=4, colunas=3).
        configuracao: Configuração do agente (nível, modelo, profundidade,
            aleatoriedade, semente).
        metadados: Identidade do turno (UUIDs e timestamp) + tempo máximo
            opcional (`nu_timer_ms` em milissegundos), gerados pela camada
            de partida. UUIDs, `ts_jogada` e `nu_timer_ms` são ecoados no
            resultado sem alteração.

    Returns:
        ResultadoJogada com a aresta escolhida e telemetria de decisão,
        incluindo `nu_timer_ms` (eco) e `nu_tempo_calculo_ms` (sempre
        presente). Se o timer estourou, `co_acao` indica o nível de
        degradação (`cnn_timeout` ou `aleatoria_timeout`).

    Raises:
        ValueError: Se `estado` está terminal (sem arestas livres),
            `metadados.nu_jogador ∉ {1, -1}`, ou
            `metadados.nu_timer_ms < 0`.
        FileNotFoundError: Se `configuracao.caminho_modelo_cnn` não existe.
        RuntimeError: Se TFLite falhar ao carregar/inferir, ou se a saída
            contiver NaN/inf.
        AssertionError: Se o tensor pós-normalização sair de {0, 1}
            (sinaliza bug de contrato).
    """
```

---

## Pré-condições

O chamador DEVE garantir:

1. **`estado: EstadoTabuleiro`**
   - Instanciado com `(linhas=4, colunas=3)` (3 caixas largura × 4 caixas altura).
   - `estado.matriz` em domínio `{-1, 0, 1, 8}` (contexto de partida; valores
     `9` permitidos defensivamente, normalizador faz a substituição).
   - `estado.tracos_disponiveis()` retorna pelo menos 1 elemento (não terminal).

2. **`configuracao: ConfiguracaoAgente`**
   - `profundidade_minimax >= 1` (validado em `__post_init__`).
   - `percentual_aleatoriedade ∈ [0.0, 1.0]` (validado em `__post_init__`).
   - `caminho_modelo_cnn` aponta para arquivo `.tflite` legível (validado em
     `cnn_inferencia_pontinhos_3_4.carregar_modelo`).

3. **`metadados: MetadadosTurno`**
   - `nu_jogador ∈ {1, -1}` (validado em `__post_init__`).
   - UUIDs e `ts_jogada` são opacos para a IA (apenas ecoados).
   - `nu_timer_ms` é opcional (default `None`); quando informado, deve ser
     `int` com valor `>= 0`. Validado em `__post_init__`. `None` ou `0`
     desabilitam o timeout (comportamento legado, sem limite de tempo).
     Valores positivos definem o tempo máximo em milissegundos para
     devolver a Prioridade 1.

---

## Pós-condições

A função GARANTE (caso retorne sem exceção):

1. **`co_aresta` é uma aresta livre no `estado` recebido**: estava em
   `estado.tracos_disponiveis()` antes da chamada.

2. **`ar_tabuleiro_antes` corresponde ao `estado.matriz` no início**: cópia
   exata; sem normalização.

3. **`ar_tabuleiro_apos` reflete o estado pós-jogada**: `ar_tabuleiro_antes`
   com a aresta `co_aresta` aplicada (e capturas resultantes contabilizadas).

4. **`nu_placar_jogador_apos = nu_placar_jogador_antes + caixas_capturadas`**,
   onde `caixas_capturadas ∈ {0, 1, 2}` (jogada pode capturar 0, 1 ou 2 caixas
   simultaneamente — Edge Case "captura múltipla").

5. **Identificadores ecoados**: `id_partida`, `id_jogada`, `id_jogador`,
   `ts_jogada`, `nu_jogador` e `nu_timer_ms` no `ResultadoJogada` são
   **idênticos** aos recebidos em `metadados` (eco bit-a-bit; `nu_timer_ms`
   pode ser `None`).

6. **`co_situacao` e `co_acao` são consistentes** segundo a tabela do
   `data-model.md`:

   | `co_situacao` | `co_acao` válidas |
   |---|---|
   | `captura_segura` | `captura_gulosa` ou `aleatoria_timeout` |
   | `final_corrente_longa` | `captura_completa`, `sacrificio_double_cross`, ou `aleatoria_timeout` |
   | `final_ciclo` | `captura_completa`, `sacrificio_double_cross`, ou `aleatoria_timeout` |
   | `tatica` | `cnn_e_minimax`, `cnn_timeout`, ou `aleatoria_timeout` |

   `aleatoria_timeout` pode aparecer em qualquer `co_situacao` (a P3 está
   sempre disponível). `cnn_timeout` só aparece em `tatica` (P2 só é
   preparada na fase tática, após inferência da CNN).

7. **Campos opcionais respeitam o padrão por origem**:

   | Origem | `nu_profundidade_minimax` | `ar_score_minimax` | `ar_probabilidade_cnn` | `js_extra` |
   |---|---|---|---|---|
   | US1 (P1) | `None` | `None` | `None` | `None` |
   | US2 (P1) | int | array (31,) c/ nan | `None` | dict obrigatório (ver abaixo) |
   | US3+4 (P1) | int | array (31,) c/ nan | array (31,) | `None` |
   | Fallback P2 (`cnn_timeout`) | int **ou** `None` | array parcial c/ nan **ou** `None` | array (31,) | `None` |
   | Fallback P3 (`aleatoria_timeout`) | `None` | `None` | `None` | `None` |

8. **Em US2 (P1), `js_extra` contém OBRIGATORIAMENTE**:
   - `co_acao_nao_selecionada: str` — `"captura_completa"` ou
     `"sacrificio_double_cross"` (a opção rejeitada).
   - `ar_score_minimax_opcao_nao_selecionada: list[float]` — array da opção
     rejeitada serializado como lista (uso de `.tolist()` para JSON-friendly).

9. **Arrays opcionais não-`None` têm shape `(31,)`, dtype `float32`**, com
   `np.nan` em posições não-avaliadas (FR-038). Em `cnn_timeout` com
   `ar_score_minimax` parcial, posições das arestas TOP-5 já avaliadas
   contêm scores reais; demais posições contêm `np.nan`.

10. **Determinismo qualificado** (FR-024):
    - Se `configuracao.percentual_aleatoriedade == 0.0` (expert) → mesma
      entrada produz mesma saída em qualquer chamada.
    - Se `configuracao.percentual_aleatoriedade > 0` e
      `configuracao.seed_aleatoriedade is not None` → mesma entrada + mesma
      semente produz mesma saída (P3 também usa essa seed via
      `np.random.default_rng`).
    - Se `percentual_aleatoriedade > 0` e `seed_aleatoriedade is None` →
      saída pode variar entre chamadas (não-determinismo por design;
      inclui escolha aleatória da P3 quando o timer estoura cedo).
    - Determinismo de `nu_tempo_calculo_ms` **não é garantido**: o tempo
      depende de carga do SO, cache de CPU, etc. Apenas a aresta
      retornada é determinística sob as condições acima.

11. **Garantias do timer** (FR-043 a FR-049):
    - `nu_tempo_calculo_ms` é sempre `int >= 0`, sempre presente.
    - Quando `metadados.nu_timer_ms is None or 0`: o agente roda sem
      checkpoint de timeout (caminho clássico). `co_acao` jamais será
      `cnn_timeout` ou `aleatoria_timeout`.
    - Quando `metadados.nu_timer_ms > 0`: vale a hierarquia P1 > P2 > P3.
      Slack admissível ≈ duração de uma sub-busca Minimax (~200ms em
      depth=3) — checkpoint é entre iterações do laço TOP-5, não dentro.
    - **Saída sempre garantida** enquanto houver pelo menos uma aresta
      livre (P3 é preparada antes de qualquer outro custo).

---

## Exceções

| Exceção | Quando | Mensagem (pt-BR) |
|---|---|---|
| `ValueError` | `estado` é terminal | `"não há jogadas disponíveis no estado recebido"` |
| `ValueError` | `nu_jogador ∉ {1, -1}` | `"nu_jogador deve ser 1 ou -1, recebido <X>"` |
| `ValueError` | `nu_timer_ms < 0` | `"nu_timer_ms deve ser ≥ 0 ou None, recebido <X>"` |
| `ValueError` | `profundidade_minimax < 1` | `"profundidade_minimax deve ser ≥ 1, recebido <X>"` |
| `ValueError` | `percentual_aleatoriedade ∉ [0, 1]` | `"percentual_aleatoriedade fora de [0.0, 1.0], recebido <X>"` |
| `FileNotFoundError` | `caminho_modelo_cnn` não existe | `"modelo CNN não encontrado em <caminho>"` |
| `RuntimeError` | TFLite falha ao carregar | `"falha ao carregar TFLite em <caminho>: <erro original>"` |
| `RuntimeError` | TFLite retorna NaN | `"saída da CNN contém NaN — modelo possivelmente corrompido"` |
| `RuntimeError` | Estado pós-jogada inválido | `"aresta <label> não estava em tracos_disponiveis"` (sanity check; bug interno) |
| `AssertionError` | Tensor pós-normalização ≠ {0, 1} | `"violação de contrato: tensor contém valores fora de {0, 1}"` |

**Política**: nenhum desses erros tem fallback silencioso. Todos propagam
para o chamador. (Clarification 2026-04-30.)

---

## Statelessness e Reentrância

- A função NÃO mantém estado mutável compartilhado entre chamadas, exceto:
  - **Cache de interpretadores TFLite** (module-level dict). É detalhe de
    implementação, NÃO estado de jogo. O cache é seguro entre chamadas porque
    `Interpreter` é stateless após `allocate_tensors()` (a sequência crítica
    `set_tensor → invoke → get_tensor` é protegida por `Lock`).
- Pode ser chamada concorrentemente de múltiplas threads, desde que cada
  thread use `MetadadosTurno` distintos e `EstadoTabuleiro` distintos. O
  cache de interpretadores é compartilhado com lock.
- Pode ser chamada para o **mesmo** modelo ou modelos diferentes (níveis
  diferentes) intercalados — o cache mantém ambos quentes.

---

## Exemplos de Chamada

### Exemplo 1 — Sem timer (comportamento legado)

```python
from uuid import uuid4
from datetime import datetime, timezone

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    ConfiguracaoAgente,
    MetadadosTurno,
    NivelDificuldade,
)

estado = EstadoTabuleiro.de_tamanho("pequeno")  # 4 linhas × 3 colunas
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.DIFICIL,
    seed_aleatoriedade=42,
)
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    # nu_timer_ms omitido → default None → sem limite de tempo
)

resultado = escolher_jogada(estado, configuracao, metadados)
# resultado.nu_timer_ms          == None  (eco)
# resultado.nu_tempo_calculo_ms  == 87    (exemplo: 87ms)
# resultado.co_acao              == CodigoAcao.CNN_E_MINIMAX

capturas = estado.aplicar_traco(resultado.co_aresta, jogador=metadados.nu_jogador)
```

### Exemplo 2 — Com timer, caso feliz (P1 retornada)

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=500,      # 500ms para devolver a jogada ideal
)

resultado = escolher_jogada(estado, configuracao, metadados)
# Cenário típico em hardware desktop: pipeline completo executa em < 300ms
# resultado.nu_timer_ms          == 500   (eco do input)
# resultado.nu_tempo_calculo_ms  == 213   (exemplo: 213ms — bem abaixo do limite)
# resultado.co_acao              == CodigoAcao.CNN_E_MINIMAX  (P1)
```

### Exemplo 3 — Com timer apertado, fallback P2 retornado

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=80,       # 80ms — provavelmente insuficiente para Minimax
)

resultado = escolher_jogada(estado, configuracao, metadados)
# Cenário: CNN inferida (~30ms), mas Minimax depth=3 não cabe nos 50ms
# restantes → timer estoura entre iterações do laço TOP-5
# resultado.nu_timer_ms          == 80
# resultado.nu_tempo_calculo_ms  == 92    (estourou levemente — slack)
# resultado.co_acao              == CodigoAcao.CNN_TIMEOUT
# resultado.co_situacao          == CodigoSituacao.TATICA
# resultado.ar_probabilidade_cnn != None  (CNN foi inferida)
# resultado.ar_score_minimax     pode ser parcial (NaN nas posições não-avaliadas) ou None
```

### Exemplo 4 — Timer extremamente apertado, fallback P3 retornado

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=1,        # 1ms — não dá tempo nem de invocar CNN
)

resultado = escolher_jogada(estado, configuracao, metadados)
# resultado.nu_timer_ms          == 1
# resultado.nu_tempo_calculo_ms  == 2
# resultado.co_acao              == CodigoAcao.ALEATORIA_TIMEOUT
# resultado.co_situacao          == CodigoSituacao.TATICA  (default; fase não detectada)
# resultado.ar_probabilidade_cnn == None
# resultado.ar_score_minimax     == None
# resultado.co_aresta            é uma aresta livre uniformemente aleatória
#                                 (reprodutível se seed_aleatoriedade fornecida)
```

---

## Contratos Internos (entre módulos do agente)

Estes não são públicos para o exterior, mas valem como contrato entre os 4
módulos novos.

### `correntes_pontinhos_3_4`

```python
def caixas_grau_3(estado: EstadoTabuleiro) -> list[tuple[int, int]]: ...
def detectar_estruturas(estado: EstadoTabuleiro) -> list[Estrutura]: ...
def estrutura_ativa(estado: EstadoTabuleiro,
                    caixas_grau_3: list[tuple[int, int]]) -> Estrutura | None: ...
def trigger_double_dealing(estrutura: Estrutura,
                           caixas_grau_3: list[tuple[int, int]]) -> bool: ...
def aresta_double_cross(estrutura: Estrutura, estado: EstadoTabuleiro) -> str: ...
def primeira_aresta_de_captura(estrutura: Estrutura, estado: EstadoTabuleiro) -> str: ...
def estado_apos_captura_completa(estado: EstadoTabuleiro,
                                 estrutura: Estrutura,
                                 jogador: int) -> EstadoTabuleiro: ...
def estado_apos_double_cross(estado: EstadoTabuleiro,
                             estrutura: Estrutura,
                             jogador: int) -> EstadoTabuleiro: ...
```

### `cnn_inferencia_pontinhos_3_4`

```python
def carregar_modelo(caminho_tflite: str) -> InferenciaCNN:
    """Carrega (ou retorna do cache) o interpretador TFLite.

    Raises:
        FileNotFoundError: caminho_tflite não existe.
        RuntimeError: TFLite falhou ao carregar.
    """

def inferir(inferencia: InferenciaCNN, estado: EstadoTabuleiro) -> np.ndarray:
    """Executa inferência sobre `estado`.

    Returns:
        np.ndarray shape (31,) dtype float32 com probabilidades.

    Raises:
        AssertionError: tensor pós-normalização ≠ {0, 1}.
        RuntimeError: saída contém NaN/inf.
    """

def top_k_arestas_livres(distribuicao: np.ndarray,
                         estado: EstadoTabuleiro,
                         k: int = 5) -> list[tuple[str, float]]:
    """Retorna [(label, prob), ...] ordenado por prob desc, apenas livres.

    Tie-break: menor índice canônico.
    Se livres < k, retorna todas (degrade gracioso).
    """

def _limpar_cache_interpretadores() -> None:
    """USO INTERNO E TESTES. Limpa o cache module-level."""
```

### `minimax_pontinhos` (alterações)

```python
FuncaoAvaliacao = Callable[[EstadoTabuleiro, int, int], int]

def avaliar(estado: EstadoTabuleiro,
            caixas_ia: int, caixas_humano: int) -> int: ...  # INALTERADO

def minimax(
    estado: EstadoTabuleiro,
    profundidade: int,
    alpha: float,
    beta: float,
    maximizando: bool,
    caixas_ia: int = 0,
    caixas_humano: int = 0,
    fn_avaliacao: FuncaoAvaliacao = avaliar,    # NOVO PARÂMETRO
) -> int: ...
```

---

## Versionamento do Contrato

Este contrato é **v1.1.0** (mesma versão da spec ratificada). Histórico:

- **v1.1.0** (esta versão) — adição do timer cooperativo: novo campo
  opcional `nu_timer_ms` em `MetadadosTurno` (default `None` preserva
  compatibilidade com chamadores antigos), novos campos comuns
  `nu_timer_ms` e `nu_tempo_calculo_ms` em `ResultadoJogada`, e novos
  valores no enum `CodigoAcao` (`cnn_timeout`, `aleatoria_timeout`).
  Compatível com chamadores que não fornecem `nu_timer_ms` — comportamento
  idêntico ao v1.0.0 nesse caso.
- **v1.0.0** — versão inicial do contrato (spec 003 ratificada).

### Critérios de versionamento

- Assinatura de `escolher_jogada` (parâmetros, ordem, tipos) → MAJOR.
- Estrutura de `ResultadoJogada` (remoção/renomeação de campo, mudança de
  obrigatoriedade de campo opcional → comum) → MAJOR.
- Adição de campo opcional a `MetadadosTurno` com default que preserva
  comportamento → MINOR.
- Adição de campo comum a `ResultadoJogada` cuja ausência não invalida
  consumidores antigos → MINOR.
- Adição de valor novo a enum (`CodigoAcao`, `CodigoSituacao`) → MINOR.
- Esclarecimento de comportamento sem mudança de API → PATCH.

Quando bumpar, atualizar simultaneamente:
- Esta especificação (`api-python-pontinhos-3-4.md`).
- `docs/historico_decisoes.md`.
- `docs/jogo_pontinhos/documentacao_ia_pontinhos_3_4.md`.
