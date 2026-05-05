# Documentação Técnica e de Negócio — Agente `ia-pontinhos-3-4`

**Status**: implementação completa (feature 003 entregue em 2026-05-04).

Atende FR-031 (CLAUDE.md): documento único cobrindo negócio + técnico do
agente híbrido para mantenedores e LLMs futuros.

---

## 1. Visão geral

`ia-pontinhos-3-4` é o agente jogador do tabuleiro 3×4 (4 linhas × 3 colunas
de caixas) do Jogo dos Pontinhos. É **híbrido**: combina raciocínio
simbólico (regras de captura e double-dealing), heurística aprendida (CNN
TFLite) e busca clássica (Minimax com poda alpha-beta), num pipeline
determinístico em 4 passos. Suporta **timer cooperativo** com degradação
graciosa em 3 prioridades.

**Entry-point único**: `escolher_jogada(estado, configuracao, metadados)
→ ResultadoJogada` em `gerador_dados/jogo_pontinhos/ia_pontinhos_3_4.py`.

---

## 2. Arquitetura — pipeline em 4 passos

| Passo | Quando dispara | Saída | Custo típico |
|---|---|---|---|
| 1. Captura gulosa | Existe ≥ 1 caixa grau-3 e Passo 2 não aplicável | Aresta que fecha menor caixa canônica | < 1ms |
| 2. Sacrifício / double-cross | Caixas grau-3 são tail de corrente longa ou ciclo | Minimax compara A (captura completa) vs B (double-cross); empate → B | ~50ms (depth=3) |
| 3. Fase tática (CNN) | Sem grau-3 | Distribuição (31,) sobre arestas + TOP-5 livres | ~30ms |
| 4. Validação Minimax | Após Passo 3 | Aresta com maior score Minimax dentre o TOP-5 | ~200ms (depth=3) |

A **aleatoriedade** (FR-042) só se aplica ao passo 4: com probabilidade
`percentual_aleatoriedade` o agente troca a melhor aresta por uma escolhida
uniformemente entre as TOP-5. Isso introduz variabilidade controlada para
combinar com o `nivel_dificuldade`.

---

## 3. Timer cooperativo — degradação graciosa (D10)

Se `metadados.nu_timer_ms > 0`, o agente mantém respostas candidatas com
prioridade decrescente. Em cada checkpoint o tempo decorrido é comparado
com o limite; quando estoura, retorna a melhor resposta já disponível:

| Prioridade | Quando preparada | `co_acao` no estouro |
|---|---|---|
| **P1** | Pipeline completo concluído | mantém o `co_acao` da origem (`captura_gulosa`, `sacrificio_double_cross`, `cnn_e_minimax`, etc.) |
| **P2** | Após inferência da CNN (argmax sobre arestas livres) | `cnn_timeout` |
| **P3** | Imediatamente no início (aresta livre uniformemente aleatória) | `aleatoria_timeout` |

Tempo medido com `time.monotonic_ns()` (não wall-clock) para portabilidade
Windows/macOS/Linux.

`nu_timer_ms = None` ou `0` desabilitam o timer (modo legado: sem limite).

---

## 4. Níveis de dificuldade

| Nível | Modelo CNN | `profundidade_minimax` | `percentual_aleatoriedade` |
|---|---|---|---|
| `facil` | `pontinhos_pequeno_profundidade_6.tflite` | 1 | 0.30 |
| `medio` | `pontinhos_pequeno_profundidade_7.tflite` | 2 | 0.15 |
| `dificil` | `pontinhos_pequeno_profundidade_9.tflite` | 3 | 0.05 |
| `expert` | `pontinhos_pequeno_profundidade_11.tflite` | 3 | 0.00 |

Definidos em `tipos_pontinhos_3_4.MAPEAMENTO_NIVEIS`. Cada campo é
override-able via `ConfiguracaoAgente` para testes ou cenários especiais.

> **Nota**: nível `expert` espera `pontinhos_pequeno_profundidade_11.tflite`,
> que **não existe** no repositório. Levantar `FileNotFoundError` é o
> comportamento correto (sem workaround).

---

## 5. Módulos

### 5.1 `tipos_pontinhos_3_4.py` — fontes de tipos
- Enums `NivelDificuldade`, `CodigoSituacao`, `CodigoAcao` (str-mixin para
  serialização JSON nativa).
- `ConfiguracaoAgente` — derivação automática de defaults por nível, com
  validações `ValueError` em `__post_init__`.
- `MetadadosTurno` (frozen) — UUIDs + `nu_jogador ∈ {1,-1}` + timer opcional.
- `ResultadoJogada` — campos comuns + opcionais (`nu_profundidade_minimax`,
  `ar_score_minimax`, `ar_probabilidade_cnn`, `js_extra`).
- `Estrutura` (frozen) — `tipo: corrente | ciclo | ramificada | isolada`,
  `caixas`, `extremidades`; propriedades `tamanho` e `eh_corrente_longa`.
- Helpers: `array_31_com_nan()`, `contar_caixas_jogador(estado, jogador)`.

### 5.2 `correntes_pontinhos_3_4.py` — detecção de estruturas
**Autossuficiente**: depende apenas de `EstadoTabuleiro` e `Estrutura`.
Importável diretamente por `avaliador_partidas_pontinhos.py` (uso futuro)
para classificar entrega de caixas pela CNN como erro vs. sacrifício.

API pública:
- `caixas_grau_3(estado)` — lista de caixas com 3 lados preenchidos.
- `aresta_que_fecha(estado, caixa)` — aresta livre que fecha caixa grau-3.
- `detectar_estruturas(estado)` — BFS sobre grafo dual; classifica em 4 tipos.
- `estrutura_ativa(estado, caixas_grau_3)` — estrutura adjacente às grau-3.
- `trigger_double_dealing(estrutura, caixas_grau_3)` — boolean.
- `primeira_aresta_de_captura(estrutura, estado)` / `aresta_double_cross(...)`.
- `estado_apos_captura_completa(...)` / `estado_apos_double_cross(...)`.

### 5.3 `cnn_inferencia_pontinhos_3_4.py` — wrapper TFLite
- `@dataclass InferenciaCNN` — interpretador + metadados (índices, forma)
  + `Lock` para serializar `set_tensor → invoke → get_tensor`.
- `carregar_modelo(caminho)` — cache module-level thread-safe; ImportError
  se nenhum runtime TFLite disponível (tenta `tensorflow.lite` →
  `tflite_runtime` → `ai_edge_litert`).
- `inferir(inferencia, estado)` — aplica normalização contexto 3 (
  `8→0, -1→1, 9→1` sobre **cópia**, nunca a matriz original) e devolve
  distribuição `(31,)` float32.
- `top_k_arestas_livres(distribuicao, estado, k=5)` — filtra preenchidas,
  ordena por prob desc com tie-break canônico.
- `_limpar_cache_interpretadores()` — uso interno e testes.

### 5.4 `ia_pontinhos_3_4.py` — orquestrador
Implementa `escolher_jogada` + helpers privados de timer
(`_elapsed_ms`, `_estourou_timer`), de escolha (`_aresta_aleatoria_livre`,
`_arg_max_arestas_livres`, `_arg_max_com_tiebreak`, `_aplicar_aleatoriedade`)
e de construção de `ResultadoJogada` (`_montar_resultado_us1`,
`_montar_resultado_us2`, `_montar_resultado_us3_4`,
`_montar_resultado_timeout_cnn`, `_montar_resultado_timeout_aleatoria`).

---

## 6. Exemplos de uso

### 6.1 Sem timer (modo legado)

```python
from datetime import datetime, timezone
from uuid import uuid4
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    ConfiguracaoAgente, MetadadosTurno, NivelDificuldade,
)

estado = EstadoTabuleiro.de_tamanho("pequeno")
cfg = ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.DIFICIL,
                         seed_aleatoriedade=42)
md = MetadadosTurno(
    id_partida=uuid4(), id_jogada=uuid4(), id_jogador=uuid4(),
    nu_jogador=1, ts_jogada=datetime.now(timezone.utc).isoformat(),
)
r = escolher_jogada(estado, cfg, md)
# r.co_acao = CodigoAcao.CNN_E_MINIMAX
estado.aplicar_traco(r.co_aresta, jogador=md.nu_jogador)
```

### 6.2 Com timer largo (P1)
```python
md = MetadadosTurno(..., nu_timer_ms=500)  # 500ms
r = escolher_jogada(estado, cfg, md)
# Pipeline completo cabe; r.co_acao = CNN_E_MINIMAX
```

### 6.3 Timer apertado (P2)
```python
md = MetadadosTurno(..., nu_timer_ms=80)  # 80ms
# CNN inferida (~30ms), Minimax depth=3 não cabe → fallback P2
# r.co_acao = CNN_TIMEOUT
# r.ar_probabilidade_cnn != None
# r.ar_score_minimax pode ser parcial (NaN nas posições não-avaliadas)
```

### 6.4 Timer extremo (P3)
```python
md = MetadadosTurno(..., nu_timer_ms=1)  # 1ms
# Nem CNN dá tempo → fallback P3
# r.co_acao = ALEATORIA_TIMEOUT
# r.ar_probabilidade_cnn == None
# r.ar_score_minimax == None
```

---

## 7. Testes

| Arquivo | Cobre | Comando |
|---|---|---|
| `tests/unitarios/jogo_pontinhos/test_tipos_pontinhos_3_4.py` | Enums, dataclasses, validações | `pytest tests/unitarios/jogo_pontinhos/test_tipos_pontinhos_3_4.py` |
| `tests/unitarios/jogo_pontinhos/test_correntes_pontinhos_3_4.py` | 40+ estados canônicos | `pytest tests/unitarios/jogo_pontinhos/test_correntes_pontinhos_3_4.py` |
| `tests/unitarios/jogo_pontinhos/test_cnn_inferencia_pontinhos_3_4.py` | Carga/inferência/cache (TFLite real) | `pytest tests/unitarios/jogo_pontinhos/test_cnn_inferencia_pontinhos_3_4.py` |
| `tests/unitarios/jogo_pontinhos/test_minimax_pontinhos_di.py` | Dependency injection (D3) | `pytest tests/unitarios/jogo_pontinhos/test_minimax_pontinhos_di.py` |
| `tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py` | Pipeline 4 passos + timer | `pytest tests/unitarios/jogo_pontinhos/test_ia_pontinhos_3_4.py` |
| `tests/integracao/jogo_pontinhos/test_partida_completa_pontinhos_3_4.py` | Auto-jogo end-to-end | `pytest tests/integracao/jogo_pontinhos/` |

**Runtime exigido**: TFLite (TensorFlow ≥ 2.0, `tflite_runtime` ou
`ai_edge_litert`). Em ambientes sem TFLite, testes que dependem de inferência
real são **skipados automaticamente**; testes que mockam `carregar_modelo`/
`inferir` rodam normalmente.

Neste repositório existe um virtualenv dedicado **`.venv_tf`** (Python
3.12 + TF 2.21) usado para todos os testes de IA. O virtualenv padrão
`.venv` (Python 3.14) não tem TFLite — use `.venv_tf` para a feature 003.

---

## 8. Design de uso futuro de `correntes_pontinhos_3_4.py`

O módulo é deliberadamente **autossuficiente** (depende apenas de
`EstadoTabuleiro` e `Estrutura`) para permitir importação direta por
módulos diferentes sem acoplar ao agente:

| Consumidor | Uso atual | Uso futuro previsto |
|---|---|---|
| `ia_pontinhos_3_4.py` | Pipeline tático (Passos 1–2) | — |
| `avaliador_partidas_pontinhos.py` | — | `detectar_estruturas` para classificar entregas da CNN como erro vs. sacrifício |
| `visualizador_pontinhos.py` | — | `detectar_estruturas` para enriquecer visualizações (highlight de chains/ciclos) |

A assinatura `detectar_estruturas(estado) -> list[Estrutura]` é suficiente
para todos os usos previstos sem alteração futura.
