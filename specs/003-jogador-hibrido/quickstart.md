# Guia de Início Rápido: `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Data**: 2026-05-01

Este guia mostra como **usar** o agente híbrido `ia-pontinhos-3-4` após a
implementação. Como esta feature entrega apenas Python in-process (sem API
HTTP, sem CLI), os exemplos são scripts/REPL.

> **Pré-requisitos**: feature implementada em `gerador_dados/jogo_pontinhos/`,
> `tensorflow` instalado a partir de `requirements_tf.txt`, modelos `.tflite`
> presentes em `modelos/`.

---

## 1. Instalação do Ambiente

```bash
# (a partir da raiz do repositório)
python -m venv .venv
.venv\Scripts\activate                          # Windows
# ou: source .venv/bin/activate                 # Linux/macOS

pip install -r requirements.txt                 # núcleo do projeto
pip install -r requirements_tf.txt              # tensorflow para inferência TFLite
```

Modelos necessários (pelo menos um):
```text
modelos/pontinhos_pequeno_profundidade_6.tflite     ← facil
modelos/pontinhos_pequeno_profundidade_7.tflite     ← medio
modelos/pontinhos_pequeno_profundidade_9.tflite     ← dificil (default)
modelos/pontinhos_pequeno_profundidade_11.tflite    ← expert (não disponível ainda)
```

---

## 2. Hello World — Uma Jogada

```python
# arquivo: exemplos/exemplo_uma_jogada.py
from uuid import uuid4
from datetime import datetime, timezone

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    ConfiguracaoAgente,
    MetadadosTurno,
    NivelDificuldade,
)

# 1) Tabuleiro 3×4 vazio (jogada inicial)
estado = EstadoTabuleiro.de_tamanho("pequeno")  # linhas=4, colunas=3

# 2) Configuração padrão (nível DIFICIL → modelo prof_9, depth=3)
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.DIFICIL,
)

# 3) Metadados (gerados pela camada de partida; aqui simulamos)
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    # nu_timer_ms omitido → default None → sem limite de tempo
)

# 4) Decisão
resultado = escolher_jogada(estado, configuracao, metadados)

print(f"Aresta escolhida   : {resultado.co_aresta}")
print(f"Situação           : {resultado.co_situacao.value}")
print(f"Ação               : {resultado.co_acao.value}")
print(f"Profundidade MM    : {resultado.nu_profundidade_minimax}")
print(f"Placar antes/apos  : {resultado.nu_placar_jogador_antes}/{resultado.nu_placar_jogador_apos}")
print(f"Timer (eco)        : {resultado.nu_timer_ms}")
print(f"Tempo de cálculo   : {resultado.nu_tempo_calculo_ms} ms")
```

Saída esperada (tabuleiro vazio → fase tática):
```
Aresta escolhida   : H_2_3              # (exemplo; depende do modelo)
Situação           : tatica
Ação               : cnn_e_minimax
Profundidade MM    : 3
Placar antes/apos  : 0/0
Timer (eco)        : None
Tempo de cálculo   : 87 ms              # (exemplo; depende da máquina)
```

> **Compatibilidade**: chamadores que NÃO fornecem `nu_timer_ms` em
> `MetadadosTurno` obtêm exatamente o comportamento legado da v1.0.0 do
> contrato — pipeline completo sem checkpoint de timeout. O agente
> apenas mede e reporta `nu_tempo_calculo_ms` (útil para benchmarking).

---

## 3. Partida Completa Agente-vs-Agente

```python
# arquivo: exemplos/exemplo_auto_jogo.py
from uuid import uuid4
from datetime import datetime, timezone

from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 import escolher_jogada
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import (
    ConfiguracaoAgente, MetadadosTurno, NivelDificuldade,
)

estado = EstadoTabuleiro.de_tamanho("pequeno")
configuracao_j1 = ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.DIFICIL)
configuracao_j2 = ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.MEDIO)

id_partida = uuid4()
id_jogador_1 = uuid4()
id_jogador_2 = uuid4()

jogador_da_vez = 1
jogadas: list = []

while not estado.esta_terminal():
    # Configuração e identidade do jogador da vez
    config = configuracao_j1 if jogador_da_vez == 1 else configuracao_j2
    id_jogador = id_jogador_1 if jogador_da_vez == 1 else id_jogador_2

    metadados = MetadadosTurno(
        id_partida=id_partida,
        id_jogada=uuid4(),
        id_jogador=id_jogador,
        nu_jogador=jogador_da_vez,
        ts_jogada=datetime.now(timezone.utc).isoformat(),
    )

    resultado = escolher_jogada(estado, config, metadados)
    capturas = estado.aplicar_traco(resultado.co_aresta, jogador=jogador_da_vez)
    jogadas.append(resultado)

    # Regra do jogo: turno extra após captura
    if capturas == 0:
        jogador_da_vez = -jogador_da_vez

# Resultado final
caixas_j1 = sum(1 for r in jogadas
                if r.nu_jogador == 1 and r.nu_placar_jogador_apos > r.nu_placar_jogador_antes)
caixas_j2 = sum(1 for r in jogadas
                if r.nu_jogador == -1 and r.nu_placar_jogador_apos > r.nu_placar_jogador_antes)
print(f"Total de jogadas : {len(jogadas)}")
print(f"Caixas J1 vs J2  : {caixas_j1} × {caixas_j2}")
```

---

## 4. Níveis de Dificuldade

```python
# Cada nível define modelo + profundidade + aleatoriedade defaults
ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.FACIL)
# → caminho_modelo_cnn = "modelos/pontinhos_pequeno_profundidade_6.tflite"
# → profundidade_minimax = 1
# → percentual_aleatoriedade = 0.30

ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.MEDIO)
# → caminho_modelo_cnn = "modelos/pontinhos_pequeno_profundidade_7.tflite"
# → profundidade_minimax = 2
# → percentual_aleatoriedade = 0.15

ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.DIFICIL)
# → caminho_modelo_cnn = "modelos/pontinhos_pequeno_profundidade_9.tflite"
# → profundidade_minimax = 3
# → percentual_aleatoriedade = 0.05

ConfiguracaoAgente(nivel_dificuldade=NivelDificuldade.EXPERT)
# → caminho_modelo_cnn = "modelos/pontinhos_pequeno_profundidade_11.tflite"  ⚠️ não existe ainda
# → profundidade_minimax = 3
# → percentual_aleatoriedade = 0.00
# → instanciar e usar levanta FileNotFoundError em escolher_jogada
```

---

## 5. Determinismo Reprodutível (Testes)

```python
# Configuração com aleatoriedade alta, mas com semente fixa → reprodutível
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.FACIL,    # percentual_aleatoriedade=0.30
    seed_aleatoriedade=42,                       # fixa o RNG
)

# Em duas chamadas com mesmos (estado, configuracao, metadados):
r1 = escolher_jogada(estado, configuracao, metadados)
r2 = escolher_jogada(estado, configuracao, metadados)
assert r1.co_aresta == r2.co_aresta              # garantido (FR-024)
```

Sem `seed_aleatoriedade`, os níveis `facil`/`medio`/`dificil` são
**não-determinísticos por design** (FR-024 qualificado). O `expert` é
sempre determinístico (`percentual_aleatoriedade=0.0`).

---

## 6. Controle de Tempo (Timer / Fallback)

A `ia-pontinhos-3-4` aceita um tempo máximo opcional (`nu_timer_ms`) para
devolver a *jogada ideal*. Se o pipeline não cabe no orçamento, o agente
devolve a melhor resposta disponível (P2: argmax da CNN, ou P3: aleatória)
e sinaliza a degradação no `co_acao`.

### 6.1 — Timer com folga (caso feliz, P1 retornada)

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=500,                # 500ms — confortável em hardware desktop
)

resultado = escolher_jogada(estado, configuracao, metadados)
print(resultado.co_acao.value)               # "cnn_e_minimax" (P1)
print(resultado.nu_tempo_calculo_ms)         # ex.: 213 (bem abaixo do limite)
print(resultado.nu_timer_ms)                 # 500 (eco)
```

### 6.2 — Timer apertado (fallback P2: CNN sem Minimax)

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=80,                 # 80ms — pode não caber Minimax depth=3
)

resultado = escolher_jogada(estado, configuracao, metadados)
# CNN inferida (~30ms), mas Minimax estourou entre iterações do TOP-5
print(resultado.co_acao.value)                  # "cnn_timeout"
print(resultado.co_situacao.value)              # "tatica"
print(resultado.nu_tempo_calculo_ms)            # ex.: 92 (slack admissível)
print(resultado.ar_probabilidade_cnn is None)   # False — CNN foi inferida
print(resultado.ar_score_minimax is None)       # pode ser True (timeout antes da 1ª iter)
                                                # ou False (parcial com NaN)
```

### 6.3 — Timer extremo (fallback P3: aleatória)

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    nu_timer_ms=1,                  # 1ms — não dá tempo nem para a CNN
)

resultado = escolher_jogada(estado, configuracao, metadados)
print(resultado.co_acao.value)                  # "aleatoria_timeout"
print(resultado.co_situacao.value)              # "tatica" (default; fase não detectada)
print(resultado.ar_probabilidade_cnn is None)   # True
print(resultado.ar_score_minimax is None)       # True
# resultado.co_aresta é uma aresta livre uniformemente aleatória.
# Reprodutível se configuracao.seed_aleatoriedade foi fornecida.
```

### 6.4 — Comportamento sem timer (compatibilidade v1.0.0)

```python
metadados = MetadadosTurno(
    id_partida=uuid4(),
    id_jogada=uuid4(),
    id_jogador=uuid4(),
    nu_jogador=1,
    ts_jogada=datetime.now(timezone.utc).isoformat(),
    # nu_timer_ms omitido (default None) → sem checkpoint de timeout
)

resultado = escolher_jogada(estado, configuracao, metadados)
# Comportamento idêntico ao v1.0.0 (pré-timer):
# - co_acao NUNCA será cnn_timeout ou aleatoria_timeout
# - nu_timer_ms == None
# - nu_tempo_calculo_ms é medido e reportado de qualquer forma (útil p/ benchmark)
```

### 6.5 — Diretrizes para escolher `nu_timer_ms`

| Cenário | Faixa recomendada | Comportamento esperado |
|---|---|---|
| App Flutter mobile (jogo turn-based) | 800–1500 ms | P1 quase sempre retornada; UX fluida |
| Avaliador desktop (auto-jogo em massa) | omitido (`None`) | Sem limite; foco em correção, não em latência |
| Benchmarking de degradação | 50–200 ms | Força aparição de P2/P3; útil para testar fallback |
| Relógio xadrez-like com tempo restante | dinâmico | A camada de partida calcula `min(restante, max_por_jogada)` |

**Importante**: em depth=3 com TOP-5, o slack máximo entre o estouro do
timer e o retorno é ≈ 200ms (uma sub-busca Minimax). Para timers menores
que isso, o agente quase sempre devolverá P2 ou P3. Não é defeito — é o
trade-off cooperativo descrito em `research.md` D10.

---

## 7. Override Granular de Configuração

```python
# Manter modelo "facil" mas usar profundidade do "expert"
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.FACIL,
    profundidade_minimax=5,            # sobrescreve o 1 default do facil
)
# → caminho_modelo_cnn ainda derivado de FACIL (prof_6)
# → percentual_aleatoriedade ainda 0.30 (default do facil)
# → profundidade_minimax = 5 (override explícito)
```

---

## 8. Logs Verbose (Opt-in)

```python
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.DIFICIL,
    verbose=True,                      # habilita logs de decisão
)

# Saída em stderr (logger nomeado `ia_pontinhos_3_4`):
# - qual passo originou a jogada (1, 2, 3+4)
# - scores Minimax e TOP-5 da CNN (em US3+4)
# - razão da decisão em US2 (score_A vs score_B)
```

Logs usam `logging` da stdlib, level INFO. Para silenciar globalmente:
`logging.getLogger("ia_pontinhos_3_4").setLevel(logging.WARNING)`.

---

## 9. Inspeção da Telemetria

`ResultadoJogada` é uma dataclass — todos os campos são acessíveis:

```python
import numpy as np

resultado = escolher_jogada(estado, configuracao, metadados)

# Estado bruto (sem normalização)
matriz_antes = resultado.ar_tabuleiro_antes      # shape (9, 7), dtype int8
matriz_apos = resultado.ar_tabuleiro_apos

# Telemetria de tempo (sempre presente)
print(f"Timer configurado : {resultado.nu_timer_ms} ms")  # eco; pode ser None
print(f"Tempo gasto       : {resultado.nu_tempo_calculo_ms} ms")
print(f"Estratégia        : {resultado.co_acao.value}")

# Telemetria de busca (apenas em US2/US3+4 quando P1 retornada;
# parcial quando cnn_timeout)
if resultado.ar_score_minimax is not None:
    avaliadas = ~np.isnan(resultado.ar_score_minimax)
    print(f"Posições avaliadas pelo Minimax: {avaliadas.sum()}")
    print(f"Score máximo observado: {np.nanmax(resultado.ar_score_minimax)}")

# Distribuição da CNN (em US3+4 e em cnn_timeout)
if resultado.ar_probabilidade_cnn is not None:
    top5_indices = np.argsort(resultado.ar_probabilidade_cnn)[-5:][::-1]
    print(f"TOP-5 índices da CNN: {top5_indices.tolist()}")

# Em US2: comparação A vs B
if resultado.js_extra and "co_acao_nao_selecionada" in resultado.js_extra:
    print(f"Opção rejeitada: {resultado.js_extra['co_acao_nao_selecionada']}")

# Detectar fallback por timeout
from gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 import CodigoAcao
if resultado.co_acao in (CodigoAcao.CNN_TIMEOUT, CodigoAcao.ALEATORIA_TIMEOUT):
    excedeu = resultado.nu_tempo_calculo_ms - (resultado.nu_timer_ms or 0)
    print(f"⚠ Fallback acionado (excedeu timer em {excedeu} ms)")
```

---

## 10. Carregar Modelo Customizado

```python
# Qualquer arquivo .tflite compatível com tabuleiro 3×4 (mesma assinatura
# input/output) pode ser usado:
configuracao = ConfiguracaoAgente(
    nivel_dificuldade=NivelDificuldade.DIFICIL,
    caminho_modelo_cnn="modelos_experimentais/meu_modelo_v5.tflite",
)
```

A compatibilidade é validada em runtime na primeira inferência (formato do
tensor de entrada, número de saídas == 31).

---

## 11. Rodar Testes

```bash
# Unitários (rápidos)
pytest tests/unitarios/jogo_pontinhos/ -v

# Cobertura mínima 90% nos módulos novos (SC-008)
pytest tests/unitarios/jogo_pontinhos/ \
    --cov=gerador_dados.jogo_pontinhos.ia_pontinhos_3_4 \
    --cov=gerador_dados.jogo_pontinhos.correntes_pontinhos_3_4 \
    --cov=gerador_dados.jogo_pontinhos.cnn_inferencia_pontinhos_3_4 \
    --cov=gerador_dados.jogo_pontinhos.tipos_pontinhos_3_4 \
    --cov-report=term-missing \
    --cov-fail-under=90

# Integração e2e (mais lento)
pytest tests/integracao/jogo_pontinhos/test_partida_completa_pontinhos_3_4.py -v

# Win-rate e performance (lentos; opt-in)
pytest tests/integracao/jogo_pontinhos/ -v -m lento
```

---

## 12. Fluxo Recomendado para Integradores Futuros

1. **Avaliador** (`avaliador_partidas_pontinhos.py`): adicione um agente
   `ia_pontinhos_3_4_agent_fn(nivel)` que chama `escolher_jogada` e retorna
   apenas `resultado.co_aresta`. A telemetria (`ar_score_minimax`,
   `ar_probabilidade_cnn`) pode ser persistida em CSV para análise offline.

2. **Simulador** (`simulador_tatico_pontinhos.py`): substitua a função-agente
   atual por uma chamada a `escolher_jogada` com nível configurável via
   parâmetro de linha de comando.

3. **App Flutter (futuro)**: portar o módulo `cnn_inferencia_pontinhos_3_4.py`
   para Dart/FFI usando o runtime TFLite nativo do Android/iOS. A lógica
   simbólica (`correntes_pontinhos_3_4`, parte de `ia_pontinhos_3_4`) pode
   ser reescrita em Dart 1:1 (algoritmos de grafo são simples).
