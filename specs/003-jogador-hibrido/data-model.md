# Modelo de Dados: Agente `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Data**: 2026-05-01

Este documento detalha as **estruturas de dados** internas do agente híbrido.
Todas vivem em `gerador_dados/jogo_pontinhos/tipos_pontinhos_3_4.py` (exceto
`Estrutura` e `InferenciaCNN`, que ficam nos módulos que as usam por motivos
de coesão).

> **Observação**: estas estruturas são **internas** (in-process Python). Não
> atravessam fronteira de sistema (HTTP, banco, IPC). Por isso usamos
> `@dataclass` (constituição II); Pydantic seria adequado quando, em feature
> futura, `ResultadoJogada` for serializado para `tb002_jogada`.

---

## Enumerações

Todas herdam de `(str, Enum)` para serialização imediata em JSON via
`.value` ou `json.dumps` com `default=str`.

### `NivelDificuldade(str, Enum)`

```python
class NivelDificuldade(str, Enum):
    FACIL   = "facil"
    MEDIO   = "medio"
    DIFICIL = "dificil"
    EXPERT  = "expert"
```

| Valor | Modelo CNN default | Profundidade default | Aleatoriedade default |
|---|---|---|---|
| `facil`   | `modelos/pontinhos_pequeno_profundidade_6.tflite`  | 1 | 0.30 |
| `medio`   | `modelos/pontinhos_pequeno_profundidade_7.tflite`  | 2 | 0.15 |
| `dificil` | `modelos/pontinhos_pequeno_profundidade_9.tflite`  | 3 | 0.05 |
| `expert`  | `modelos/pontinhos_pequeno_profundidade_11.tflite` ⚠️ | 3 | 0.00 |

⚠️ Modelo do `expert` ainda não existe; usar o nível levanta `FileNotFoundError`.

### `CodigoSituacao(str, Enum)`

```python
class CodigoSituacao(str, Enum):
    CAPTURA_SEGURA       = "captura_segura"
    FINAL_CORRENTE_LONGA = "final_corrente_longa"
    FINAL_CICLO          = "final_ciclo"
    TATICA               = "tatica"
```

Identifica qual ramo do algoritmo originou a decisão.

### `CodigoAcao(str, Enum)`

```python
class CodigoAcao(str, Enum):
    # ─── Saídas de Prioridade 1 (jogada ideal) ───
    CAPTURA_GULOSA          = "captura_gulosa"
    CAPTURA_COMPLETA        = "captura_completa"
    SACRIFICIO_DOUBLE_CROSS = "sacrificio_double_cross"
    CNN_E_MINIMAX           = "cnn_e_minimax"

    # ─── Saídas de fallback por timeout (FR-047) ───
    CNN_TIMEOUT             = "cnn_timeout"
    ALEATORIA_TIMEOUT       = "aleatoria_timeout"
```

Identifica a estratégia executada. Os 4 primeiros valores são saídas
canônicas do pipeline completo (Prioridade 1). Os 2 últimos são acionados
quando `nu_timer_ms` força degradação graciosa antes que a jogada ideal
seja calculada — `cnn_timeout` para Prioridade 2 (argmax da CNN sem
Minimax) e `aleatoria_timeout` para Prioridade 3 (aresta livre uniformemente
aleatória, preparada no acionamento).

---

## Constante `MAPEAMENTO_NIVEIS`

```python
MAPEAMENTO_NIVEIS: dict[NivelDificuldade, dict[str, object]] = {
    NivelDificuldade.FACIL: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_6.tflite",
        "profundidade_minimax": 1,
        "percentual_aleatoriedade": 0.30,
    },
    NivelDificuldade.MEDIO: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_7.tflite",
        "profundidade_minimax": 2,
        "percentual_aleatoriedade": 0.15,
    },
    NivelDificuldade.DIFICIL: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_9.tflite",
        "profundidade_minimax": 3,
        "percentual_aleatoriedade": 0.05,
    },
    NivelDificuldade.EXPERT: {
        "caminho_modelo_cnn": "modelos/pontinhos_pequeno_profundidade_11.tflite",
        "profundidade_minimax": 3,
        "percentual_aleatoriedade": 0.00,
    },
}
```

Acesso público; testes parametrizam sobre todas as chaves.

---

## `ConfiguracaoAgente`

Configuração externa do agente, passada como 2º argumento de `escolher_jogada`.

```python
@dataclass
class ConfiguracaoAgente:
    nivel_dificuldade: NivelDificuldade = NivelDificuldade.DIFICIL
    caminho_modelo_cnn: str | None = None
    profundidade_minimax: int | None = None
    percentual_aleatoriedade: float | None = None
    seed_aleatoriedade: int | None = None
    verbose: bool = False

    def __post_init__(self) -> None:
        defaults = MAPEAMENTO_NIVEIS[self.nivel_dificuldade]
        if self.caminho_modelo_cnn is None:
            self.caminho_modelo_cnn = defaults["caminho_modelo_cnn"]
        if self.profundidade_minimax is None:
            self.profundidade_minimax = defaults["profundidade_minimax"]
        if self.percentual_aleatoriedade is None:
            self.percentual_aleatoriedade = defaults["percentual_aleatoriedade"]

        # Validações
        if self.profundidade_minimax < 1:
            raise ValueError(
                f"profundidade_minimax deve ser ≥ 1, recebido {self.profundidade_minimax}"
            )
        if not (0.0 <= self.percentual_aleatoriedade <= 1.0):
            raise ValueError(
                f"percentual_aleatoriedade fora de [0.0, 1.0], recebido "
                f"{self.percentual_aleatoriedade}"
            )
```

### Campos

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `nivel_dificuldade` | `NivelDificuldade` | `DIFICIL` | Define os defaults para os outros campos |
| `caminho_modelo_cnn` | `str \| None` | derivado | Caminho do `.tflite` |
| `profundidade_minimax` | `int \| None` | derivado | Profundidade da busca; ≥ 1 |
| `percentual_aleatoriedade` | `float \| None` | derivado | Probabilidade de jogada aleatória entre TOP-5 no Passo 4; em [0.0, 1.0] |
| `seed_aleatoriedade` | `int \| None` | `None` | Semente do RNG; quando `None`, RNG é não-reprodutível |
| `verbose` | `bool` | `False` | Habilita logs detalhados de decisão (opt-in) |

### Override granular

```python
# Tudo derivado do nível
ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.MEDIO)
# → profundidade_minimax=2, percentual_aleatoriedade=0.15, ...

# Override apenas profundidade
ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.MEDIO, profundidade_minimax=5)
# → caminho_modelo_cnn ainda derivado de MEDIO; profundidade=5 fixo
```

---

## `MetadadosTurno`

Identidade e parâmetros temporais deste turno específico, fornecidos pela
camada de partida e **ecoados** pela IA no `ResultadoJogada` (`nu_timer_ms`
inclusive). Imutável.

```python
@dataclass(frozen=True)
class MetadadosTurno:
    id_partida: UUID
    id_jogada: UUID
    id_jogador: UUID
    nu_jogador: int               # +1 ou -1
    ts_jogada: str                # ISO 8601 com tz, ex.: "2026-05-01T14:23:45-03:00"
    nu_timer_ms: int | None = None  # tempo máx. (ms) para devolver Prioridade 1

    def __post_init__(self) -> None:
        if self.nu_jogador not in (1, -1):
            raise ValueError(
                f"nu_jogador deve ser 1 ou -1, recebido {self.nu_jogador}"
            )
        if self.nu_timer_ms is not None and self.nu_timer_ms < 0:
            raise ValueError(
                f"nu_timer_ms deve ser ≥ 0 ou None, recebido {self.nu_timer_ms}"
            )
```

### Campos

| Campo | Tipo | Origem | Descrição |
|---|---|---|---|
| `id_partida` | `UUID` | gerado pela camada de partida no início | Constante durante toda a partida |
| `id_jogada` | `UUID` | gerado pela camada de partida antes de cada turno | Único por jogada |
| `id_jogador` | `UUID` | identidade do jogador da vez | Pode ser `id_usuario` (humano), ID fixo (IA) ou UUID runtime (CPU/anônimo) |
| `nu_jogador` | `int` | derivado da camada de partida | +1 ou -1 |
| `ts_jogada` | `str` | gerado pela camada de partida no fuso de `id_jogador` | ISO 8601 com tz |
| `nu_timer_ms` | `int \| None` | decidido pela camada de partida (App Flutter, simulador, avaliador) | **Opcional**. Tempo máximo (ms) para devolver a *jogada ideal* (Prioridade 1). `None` ou `0` = timeout desabilitado (sem limite, comportamento legado). `> 0` ativa degradação graciosa (FR-043 a FR-049). Pode variar a cada turno (ex.: relógio xadrez-like) |

A IA **não gera** nem **valida** os UUIDs (apenas `nu_jogador` e o sinal
de `nu_timer_ms`); a integridade referencial é responsabilidade da camada
de persistência futura. O `nu_timer_ms` é **respeitado** pela IA e
**ecoado** sem alteração no `ResultadoJogada`.

---

## `ResultadoJogada`

Saída de `escolher_jogada`. **Não é uma `Aresta` simples** — carrega telemetria
suficiente para futura persistência em `tb002_jogada`.

```python
@dataclass
class ResultadoJogada:
    # ─── Campos comuns (sempre presentes) ───
    id_partida: UUID
    id_jogada: UUID
    id_jogador: UUID
    nu_jogador: int
    co_situacao: CodigoSituacao
    co_acao: CodigoAcao
    co_aresta: str
    ar_tabuleiro_antes: np.ndarray   # sem normalização, dtype int8
    ar_tabuleiro_apos: np.ndarray    # sem normalização, dtype int8
    nu_placar_jogador_antes: int
    nu_placar_jogador_apos: int
    ts_jogada: str
    nu_timer_ms: int | None          # eco de MetadadosTurno (None/0 = sem timer)
    nu_tempo_calculo_ms: int         # ms gastos até a saída retornada (sempre presente)

    # ─── Campos opcionais ───
    nu_profundidade_minimax: int | None = None
    ar_score_minimax: np.ndarray | None = None         # shape (31,) float32 c/ np.nan
    ar_probabilidade_cnn: np.ndarray | None = None     # shape (31,) float32
    js_extra: dict | None = None
```

### Campos comuns (sempre presentes)

| Campo | Tipo | Descrição |
|---|---|---|
| `id_partida` | `UUID` | Ecoado de `MetadadosTurno` |
| `id_jogada` | `UUID` | Ecoado de `MetadadosTurno` |
| `id_jogador` | `UUID` | Ecoado de `MetadadosTurno` |
| `nu_jogador` | `int` | +1 ou -1 |
| `co_situacao` | `CodigoSituacao` | Ramo do algoritmo |
| `co_acao` | `CodigoAcao` | Estratégia executada |
| `co_aresta` | `str` | `<TIPO>_<dim1>_<dim2>` (ex.: `H_0_1`, `V_2_3`) |
| `ar_tabuleiro_antes` | `np.ndarray` | Matriz **sem normalização** (domínio bruto), shape `(9, 7)` para 3×4 |
| `ar_tabuleiro_apos` | `np.ndarray` | idem |
| `nu_placar_jogador_antes` | `int` | Caixas do `nu_jogador` ANTES |
| `nu_placar_jogador_apos` | `int` | Caixas do `nu_jogador` APÓS |
| `ts_jogada` | `str` | Ecoado de `MetadadosTurno` |
| `nu_timer_ms` | `int \| None` | **Eco** de `MetadadosTurno.nu_timer_ms`. `None`/`0` ⇒ chamada sem timeout |
| `nu_tempo_calculo_ms` | `int` | Tempo (ms inteiros) entre o acionamento de `escolher_jogada` e a saída retornada. Medido com `time.monotonic_ns()` (D10). Sempre ≥ 0; **sempre presente**, mesmo sem timer |

### Campos opcionais (preenchidos conforme passo originador)

| Campo | Quando preenchido |
|---|---|
| `nu_profundidade_minimax` | Sempre que Minimax foi executado (Passos 2 e 3+4) |
| `ar_score_minimax` | Passos 2 (scores da opção ESCOLHIDA) e 3+4 (scores das arestas TOP-5 avaliadas) |
| `ar_probabilidade_cnn` | Apenas Passos 3+4 (saída crua da CNN antes de filtragem) |
| `js_extra` | Sempre opcional; em US2 é OBRIGATÓRIO conter `co_acao_nao_selecionada` e `ar_score_minimax_opcao_nao_selecionada` |

### Padrão por User Story

| Origem | `co_situacao` | `co_acao` | Profundidade | Score MM | Prob CNN | `js_extra` |
|---|---|---|---|---|---|---|
| US1 | `captura_segura` | `captura_gulosa` | `None` | `None` | `None` | `None` |
| US2 (B chosen) | `final_corrente_longa` ou `final_ciclo` | `sacrificio_double_cross` | int | array B | `None` | `{co_acao_nao_selecionada: "captura_completa", ar_score_minimax_opcao_nao_selecionada: array A}` |
| US2 (A chosen) | `final_corrente_longa` ou `final_ciclo` | `captura_completa` | int | array A | `None` | `{co_acao_nao_selecionada: "sacrificio_double_cross", ar_score_minimax_opcao_nao_selecionada: array B}` |
| US3+4 | `tatica` | `cnn_e_minimax` | int | array TOP-5 | array CNN | `None` |
| **Fallback P2 (timeout pós-CNN)** | `tatica` | `cnn_timeout` | int **ou** `None` | array parcial c/ NaN **ou** `None` | array CNN | `None` |
| **Fallback P3 (timeout pré-CNN)** | `tatica` (default) ou fase detectada | `aleatoria_timeout` | `None` | `None` | `None` | `None` |

**Notas sobre fallbacks (FR-046 a FR-049 e D10)**:
- `cnn_timeout` é retornado quando o timer estoura **após** a inferência da
  CNN (P2 já preparada) e antes de o Minimax terminar de avaliar todas as 5
  arestas TOP-5. Se o estouro for entre iterações do laço, `ar_score_minimax`
  carrega scores parciais (com `np.nan` nas posições não-avaliadas) — telemetria
  parcial é melhor que ausência total.
- `aleatoria_timeout` é retornado quando o timer estoura **antes** da CNN
  ser invocada (extremamente raro com timers ≥ 50ms; existe por defesa em
  profundidade). `co_situacao` reflete a fase detectada antes do estouro;
  default `tatica` quando a fase ainda não foi determinada.
- `nu_tempo_calculo_ms` é sempre preenchido com o tempo decorrido até o
  retorno (P1, P2 ou P3); `nu_timer_ms` é sempre ecoado.

### Invariantes (FR-038, FR-041, FR-049)

1. **Arrays opcionais** (`ar_score_minimax`, `ar_probabilidade_cnn`):
   - `dtype == np.float32`
   - `shape == (31,)`
   - Posições não-avaliadas → `np.nan` (sentinela canônica).

2. **Arrays de tabuleiro** (`ar_tabuleiro_antes`, `ar_tabuleiro_apos`):
   - `dtype == np.int8` (igual ao `EstadoTabuleiro.matriz`).
   - **Sem normalização** (domínio bruto `{-1, 0, 1, 8}`).
   - `shape == (2*linhas+1, 2*colunas+1)`, ou seja, `(9, 7)` para 3×4.

3. **`co_aresta` segue o contrato canônico**: formato `<TIPO>_<r>_<c>`.
   `<TIPO> ∈ {"H", "V"}`, `r` e `c` em coordenadas da matriz.

4. **`co_situacao` e `co_acao`**: sempre vindas dos enums; `str` literal não
   é aceito (validação implícita via type hint do dataclass).

5. **Timer (FR-049)**:
   - `nu_timer_ms` é **eco exato** do valor recebido em `MetadadosTurno`
     (incluindo `None` quando o input não foi fornecido).
   - `nu_tempo_calculo_ms` é sempre `int >= 0`. Sempre presente.
   - Quando `nu_timer_ms is not None and nu_timer_ms > 0` E
     `co_acao in {CAPTURA_GULOSA, CAPTURA_COMPLETA, SACRIFICIO_DOUBLE_CROSS,
     CNN_E_MINIMAX}` (Prioridade 1 retornada), vale
     `nu_tempo_calculo_ms <= nu_timer_ms + slack`, onde `slack` ≈ 200ms é
     a duração máxima de uma sub-busca Minimax que pode atrasar o
     checkpoint. Se a desigualdade fosse violada com folga maior, a saída
     teria sido fallback (FR-046).
   - Quando `co_acao in {CNN_TIMEOUT, ALEATORIA_TIMEOUT}`, é garantido que
     `nu_timer_ms > 0` (caso contrário a degradação não teria sido acionada).

6. **Coerência fallback × campos opcionais (FR-049, conservação de telemetria)**:
   - Se `co_acao == CNN_TIMEOUT`: `ar_probabilidade_cnn` **deve** estar
     preenchido (a CNN foi inferida). `ar_score_minimax` **pode** estar
     parcialmente preenchido (scores das primeiras arestas TOP-5 já
     avaliadas) ou ser `None` (timeout disparou exatamente após CNN, antes
     da primeira iteração).
   - Se `co_acao == ALEATORIA_TIMEOUT`: `ar_probabilidade_cnn` é `None`
     (CNN não chegou a ser executada). `ar_score_minimax` é `None`.
     `nu_profundidade_minimax` é `None`.

---

## `Estrutura` (interno a `correntes_pontinhos_3_4.py`)

Representação de uma corrente, ciclo ou estrutura ramificada detectada pelo
algoritmo de grafo dual.

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class Estrutura:
    tipo: Literal["corrente", "ciclo", "ramificada", "isolada"]
    caixas: tuple[tuple[int, int], ...]      # ordenado ao longo da estrutura
    extremidades: tuple[tuple[int, int], ...]  # 2 para corrente, 0 p/ ciclo

    @property
    def tamanho(self) -> int:
        return len(self.caixas)

    @property
    def eh_corrente_longa(self) -> bool:
        return self.tipo == "corrente" and self.tamanho >= 3
```

| Campo | Tipo | Descrição |
|---|---|---|
| `tipo` | enum-like | Classificação do componente conexo |
| `caixas` | `tuple[tuple[int, int], ...]` | Coordenadas `(box_r, box_c)` dos centros das caixas, ordenadas ao longo da estrutura |
| `extremidades` | `tuple[tuple[int, int], ...]` | Subconjunto de `caixas` que são folhas no grafo dual (apenas correntes têm 2; ciclos têm 0) |

Imutabilidade (`frozen=True`) garante que análise/cache sejam thread-safe e
evita bugs onde duas instâncias do detector retornariam estruturas mutadas.

---

## `InferenciaCNN` (interno a `cnn_inferencia_pontinhos_3_4.py`)

Wrapper sobre o `Interpreter` do TFLite com metadados pré-calculados.

```python
from dataclasses import dataclass
import threading
import tensorflow.lite as tflite

@dataclass
class InferenciaCNN:
    interpretador: tflite.Interpreter
    indice_entrada: int
    indice_saida: int
    forma_entrada: tuple[int, ...]
    lock: threading.Lock
```

| Campo | Tipo | Descrição |
|---|---|---|
| `interpretador` | `tflite.Interpreter` | Instância já com `allocate_tensors()` chamado |
| `indice_entrada` | `int` | `interpretador.get_input_details()[0]['index']` (cacheado) |
| `indice_saida` | `int` | `interpretador.get_output_details()[0]['index']` (cacheado) |
| `forma_entrada` | `tuple[int, ...]` | Shape esperado pelo modelo, ex.: `(1, 9, 7, 1)` |
| `lock` | `threading.Lock` | Protege a sequência crítica `set_tensor → invoke → get_tensor` |

Esta dataclass **não** é exposta como contrato público — é detalhe de
implementação. Apenas o `caminho_modelo_cnn` (str) atravessa a fronteira do
módulo.

---

## Helpers Públicos em `tipos_pontinhos_3_4.py`

```python
def array_31_com_nan() -> np.ndarray:
    """Retorna uma nova array float32 shape (31,) preenchida com np.nan.

    Sentinela canônica para arrays opcionais do ResultadoJogada (FR-038).
    """
    return np.full((31,), np.nan, dtype=np.float32)


def contar_caixas_jogador(estado: EstadoTabuleiro, jogador: int) -> int:
    """Conta caixas fechadas atribuídas ao jogador (+1 ou -1).

    Workaround para o defeito conhecido em
    EstadoTabuleiro.caixas_fechadas_por (não filtra por jogador).
    """
    contagem = 0
    matriz = estado.matriz
    for box_r in range(1, matriz.shape[0], 2):
        for box_c in range(1, matriz.shape[1], 2):
            if matriz[box_r, box_c] == jogador:
                contagem += 1
    return contagem
```

---

## Diagrama de Dependências entre Estruturas

```text
                            ┌──────────────────────┐
                            │  ConfiguracaoAgente  │  ← passada pelo chamador
                            └──────────┬───────────┘
                                       │ contém ref a
                                       ▼
                            ┌──────────────────────┐
                            │   NivelDificuldade   │
                            └──────────────────────┘

                            ┌──────────────────────┐
                            │   MetadadosTurno     │  ← passada pelo chamador
                            │  + nu_timer_ms (opc.)│
                            └──────────┬───────────┘
                                       │ ecoada em (UUIDs, ts_jogada,
                                       │           nu_timer_ms)
                                       ▼
┌──────────────────────────────────────────────────────────────┐
│                      ResultadoJogada                          │
│                                                                │
│  - id_partida, id_jogada, id_jogador (UUID, ecoados)          │
│  - co_situacao  : CodigoSituacao                              │
│  - co_acao      : CodigoAcao  (inclui *_timeout em fallback)  │
│  - nu_timer_ms          : eco do input                        │
│  - nu_tempo_calculo_ms  : medido c/ time.monotonic_ns() (D10) │
│  - ar_score_minimax     : array_31_com_nan() [parcial em P2]  │
│  - ar_probabilidade_cnn : np.ndarray (31,) float32            │
└──────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────┐
         │   Estrutura (interno a correntes_pontinhos_3_4) │
         │   - tipo: corrente / ciclo / ramificada         │
         │   - caixas: tuple[(box_r, box_c), ...]          │
         │   - extremidades                                │
         └─────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────┐
         │  InferenciaCNN (interno a cnn_inferencia_*)     │
         │  - interpretador: tflite.Interpreter            │
         │  - lock: threading.Lock                         │
         └─────────────────────────────────────────────────┘
```
