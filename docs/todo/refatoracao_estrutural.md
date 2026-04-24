# Plano de Refatoração Estrutural — Arena Sagaz Backend

> **Documento de referência multi-sessão.** Cada fase pode ser executada em janela de tokens separada.
> Marque cada checkbox quando concluído. Não pule fases — cada uma é pré-requisito da seguinte.

**Branch de partida:** `001-fase-zero-backend` (estado, já no GitHub)
**Branch atual:** `002-refatoracao-estrutural` (em execução — Fase 0 concluída, api/ limpa)
**Branch da api/ nova:** criar `003-api-layer-driven` a partir de `main` (fase separada)

---

## Decisões acordadas (referência rápida)

| Ponto | Decisão |
|---|---|
| Plural dos jogos | `jogo_pontinhos`, `jogo_da_velha`, `jogo_da_forca` |
| Modelos TFLite | `gerador_dados/jogo_pontinhos/modelos/` |
| API versioning | URL path — `/api/v1/`, `/api/v2/` |
| Autenticação | **Firebase Auth** — valida token no backend, Google/Apple grátis |
| api/ nova | Branch separada (`003-api-layer-driven`), começar do zero |
| SpecKit | NÃO usar — gerou docs ilegíveis anteriormente |
| Backup | git history é backup — branch `001-fase-zero-backend` preserva estado anterior |
| `normalizar_datasets.py` | ✅ DELETADO |
| `temp_cells.txt` | ✅ DELETADO |
| `test.py` (raiz) | ✅ DELETADO |
| `visualizador_minimax.html` | ✅ MOVIDO → `docs/jogo_pontinhos/` |
| `api/banco/`, `api/auth/`, etc. | ✅ DELETADOS (SpecKit garbage — recriar do zero quando o jogo rodar) |
| `nucleo_log.py` | MOVER → fundir com `api/nucleo/log.py` (já existe e faz a mesma coisa) |
| Notebooks Avaliação | Único que precisa de update de paths; demais são contexto histórico |
| Sufixos legados | Renomear nesta refatoração (era débito técnico declarado) |

---

## Estrutura-alvo completa

```
arena-sagaz-backend/
│
├── api/                               ← ESTADO ATUAL (após limpeza)
│   ├── __init__.py
│   ├── main.py
│   ├── configuracao.py
│   └── nucleo/
│       ├── __init__.py
│       ├── log.py           ← absorverá gerador_dados/nucleo_log.py (Fase 2)
│       ├── excecoes.py
│       └── rotas.py         (GET /v1/health)
│
│   ── [FASE 4 — branch 003-api-layer-driven, criada do zero] ──
│   ├── banco/               ← SQLAlchemy + Alembic, criar quando definições fechadas
│   ├── routers/
│   │   └── v1/
│   │       ├── jogo_pontinhos/
│   │       │   └── partidas.py
│   │       ├── auth.py      ← Firebase token validation
│   │       ├── usuarios.py
│   │       └── ranking.py
│   ├── schemas/
│   │   └── v1/
│   │       ├── jogo_pontinhos/
│   │       └── ...
│   ├── models/
│   │   ├── jogo_pontinhos/
│   │   └── ...
│   └── services/
│       └── v1/
│           ├── jogo_pontinhos/
│           └── ...
│
├── gerador_dados/
│   ├── __init__.py
│   └── jogo_pontinhos/
│       ├── __init__.py
│       ├── tabuleiro_pontinhos.py      ← atual gerador_dados/tabuleiro.py
│       ├── minimax_pontinhos.py        ← atual gerador_dados/minimax.py
│       ├── gerador_pontinhos.py        ← atual gerador_dados/gerador.py
│       ├── visualizador_pontinhos.py   ← atual gerador_dados/visualizador.py
│       ├── avaliador_partidas_pontinhos.py ← atual gerador_dados/avaliador_partidas.py
│       ├── simulador_tatico_pontinhos.py ← atual gerador_dados/simulador/simulador_tatico.py
│       ├── contrato_codificacao_pontinhos.py ← atual gerador_dados/contrato_codificacao_pontinhos.py
│       ├── contrato_codificacao_pontinhos.json ← atual gerador_dados/contrato_codificacao_pontinhos.json
│       └── modelos/                    ← NOVA pasta (colocar .tflite aqui)
│
├── notebooks/
│   └── jogo_pontinhos/
│       ├── Avaliacao_CNN_vs_Minimax.ipynb
│       ├── Otimizacao_Topologia_Rede.ipynb
│       ├── Otimizacao_Topologia_Rede_V2.ipynb
│       ├── Otimizacao_Topologia_Rede_V3.ipynb
│       ├── Treinamento_CNN_Arena_Sagaz.ipynb
│       └── Treinamento_CNN_Arena_Sagaz_V3.ipynb
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unitarios/
│   │   ├── __init__.py
│   │   └── jogo_pontinhos/
│   │       ├── __init__.py
│   │       ├── test_contrato_codificacao_pontinhos.py
│   │       ├── test_tabuleiro_pontinhos.py  ← atual test_tabuleiro.py
│   │       ├── test_minimax_pontinhos.py    ← atual test_minimax.py
│   │       └── test_visualizador_pontinhos.py ← atual test_visualizador.py
│   ├── unitarios/
│   │   ├── test_seguranca.py  (fica fora de jogo_pontinhos — testa api/nucleo)
│   │   └── test_xp.py         (fica fora — testa lógica de XP da plataforma)
│   └── integracao/
│       ├── __init__.py
│       ├── test_auth.py
│       ├── test_health.py
│       ├── test_partidas.py
│       ├── test_ranking.py
│       └── test_usuarios.py
│
├── docs/
│   ├── historico_decisoes.md          ← MANTÉM AQUI (hub-genérico)
│   ├── metricas_e_conceitos.md        ← MANTÉM AQUI (hub-genérico)
│   ├── todo/
│   │   └── refatoracao_estrutural.md  ← ESTE ARQUIVO
│   ├── tcc/
│   │   └── argumentacao_cnn_vs_minimax.md  ← MOVE de docs/
│   └── jogo_pontinhos/
│       ├── analise_combinatoria_profundidade.md
│       ├── analise_profundidade_minimax.md
│       ├── aprendizado_cnn_padroes_ruins.md
│       ├── estimativas_minimax.md
│       ├── estrategia_early_game.md
│       ├── gpu_vs_cpu_minimax.md
│       ├── guia_geracao_dados.md
│       ├── historico_tentativas_treinamento.md
│       ├── justificativa_50k_amostras.md
│       ├── soft_targets_kl_divergence.md
│       ├── visualizador_minimax.html  ← MOVE de raiz/
│       └── workflow_minimax_exemplo.md
│
├── sql/
├── specs/
├── visualizacoes/
├── .env.example
├── .gitignore
├── alembic.ini
├── Dockerfile
├── pytest.ini
├── railway.json
└── requirements.txt
```

---

## Fase 0 — Backup e limpeza ✅ CONCLUÍDA

**Executada em 2026-04-24 na branch `002-refatoracao-estrutural`.**

O que foi feito (não re-executar):
- Branch `002-refatoracao-estrutural` criada a partir de `001-fase-zero-backend`
- `scripts/normalizar_datasets.py` deletado (git rm)
- `temp_cells.txt` e `test.py` deletados (eram untracked, rm)
- `visualizador_minimax.html` movido → `docs/jogo_pontinhos/`
- `api/banco/`, `api/auth/`, `api/partidas/`, `api/ranking/`, `api/trofeus/`, `api/usuarios/` deletados (git rm)
- `api/nucleo/dependencias.py`, `api/nucleo/seguranca.py`, `alembic.ini` deletados
- `api/main.py`, `api/configuracao.py`, `api/nucleo/rotas.py` reescritos (minimalistas)
- `requirements.txt` limpo (SQLAlchemy, bcrypt, asyncpg, psycopg2, python-jose removidos)
- `.env.example` simplificado (só AMBIENTE + comentários Firebase)
- `tests/conftest.py` reescrito (sem DB setup)
- Testes obsoletos deletados: `test_auth.py`, `test_partidas.py`, `test_ranking.py`, `test_usuarios.py`, `test_seguranca.py`, `test_xp.py`
- `test_health.py` atualizado (sem checar banco)

**Backup:** o git history de `001-fase-zero-backend` é o backup. `git checkout 001-fase-zero-backend` restaura o estado anterior completo.

---

## Fase 1 — Reorganização de `docs/` ✅ CONCLUÍDA

**Executada em 2026-04-24.**

### 1.1 Criar subpastas

```bash
mkdir -p docs/tcc
mkdir -p docs/jogo_pontinhos   # já criada na fase 0.4
```

### 1.2 Mover docs para `docs/tcc/`

```bash
git mv docs/argumentacao_cnn_vs_minimax.md docs/tcc/argumentacao_cnn_vs_minimax.md
```

> **Por que `tcc/` e não `jogo_pontinhos/`?** O arquivo tem seção explícita "Argumentação para defesa do TCC" — seu público primário é a banca, não desenvolvedores do jogo. Vai para `tcc/`.

### 1.3 Mover docs para `docs/jogo_pontinhos/`

```bash
git mv docs/analise_combinatoria_profundidade.md  docs/jogo_pontinhos/
git mv docs/analise_profundidade_minimax.md        docs/jogo_pontinhos/
git mv docs/aprendizado_cnn_padroes_ruins.md       docs/jogo_pontinhos/
git mv docs/estimativas_minimax.md                 docs/jogo_pontinhos/
git mv docs/estrategia_early_game.md               docs/jogo_pontinhos/
git mv docs/gpu_vs_cpu_minimax.md                  docs/jogo_pontinhos/
git mv docs/guia_geracao_dados.md                  docs/jogo_pontinhos/
git mv docs/historico_tentativas_treinamento.md    docs/jogo_pontinhos/
git mv docs/justificativa_50k_amostras.md          docs/jogo_pontinhos/
git mv docs/soft_targets_kl_divergence.md          docs/jogo_pontinhos/
git mv docs/workflow_minimax_exemplo.md             docs/jogo_pontinhos/
```

### 1.4 Docs que FICAM em `docs/` (hub-genéricos)

Não mover:
- `docs/historico_decisoes.md` — decisões arquiteturais de toda a plataforma
- `docs/metricas_e_conceitos.md` — referência de métricas para qualquer jogo

### 1.5 Atualizar referências cruzadas

Grep por links quebrados após os moves:
```bash
grep -r "docs/argumentacao\|docs/analise\|docs/aprendizado\|docs/estimativas\|docs/estrategia\|docs/gpu\|docs/guia_geracao\|docs/historico_tentativas\|docs/justificativa\|docs/soft_targets\|docs/workflow" docs/ CLAUDE.md specs/
```
Atualize qualquer link que aponte para os paths antigos.

**Checklist fase 1:**
- [ ] `docs/tcc/` criado
- [ ] `docs/jogo_pontinhos/` criado
- [ ] `argumentacao_cnn_vs_minimax.md` movido para `docs/tcc/`
- [ ] 11 docs pontinhos movidos para `docs/jogo_pontinhos/`
- [ ] `historico_decisoes.md` e `metricas_e_conceitos.md` permanecem em `docs/`
- [ ] Links cruzados verificados/atualizados
- [ ] Commit intermediário: `refactor(docs): reorganiza docs em tcc/ e jogo_pontinhos/`

---

## Fase 2 — Reorganização de `gerador_dados/`

**Objetivo:** criar `gerador_dados/jogo_pontinhos/`, renomear arquivos legados com sufixo `_pontinhos`, mover `nucleo_log.py` para `api/nucleo/`.

> **Atenção Alembic:** os models SQLAlchemy ficam em `api/` (não em `gerador_dados/`). Esta fase não toca em migrations.

### 2.1 Criar pasta de destino

```bash
mkdir -p gerador_dados/jogo_pontinhos
touch gerador_dados/jogo_pontinhos/__init__.py
```

### 2.2 Mover e renomear arquivos (com `git mv`)

| Origem (atual) | Destino |
|---|---|
| `gerador_dados/tabuleiro.py` | `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py` |
| `gerador_dados/minimax.py` | `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` |
| `gerador_dados/gerador.py` | `gerador_dados/jogo_pontinhos/gerador_pontinhos.py` |
| `gerador_dados/visualizador.py` | `gerador_dados/jogo_pontinhos/visualizador_pontinhos.py` |
| `gerador_dados/avaliador_partidas.py` | `gerador_dados/jogo_pontinhos/avaliador_partidas_pontinhos.py` |
| `gerador_dados/simulador/simulador_tatico.py` | `gerador_dados/jogo_pontinhos/simulador_tatico_pontinhos.py` |
| `gerador_dados/contrato_codificacao_pontinhos.py` | `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py` |
| `gerador_dados/contrato_codificacao_pontinhos.json` | `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` |
| `gerador_dados/nucleo_log.py` | `api/nucleo/nucleo_log_pontinhos.py` (**ver nota abaixo**) |

> **Nota sobre `nucleo_log.py`:** `api/nucleo/log.py` já contém `obter_logger()` com implementação idêntica. Ao mover os arquivos de `gerador_dados/`, simplesmente atualizar os imports de `gerador_dados.nucleo_log` para `api.nucleo.log` — sem mover o arquivo. Depois que ninguém mais importar `gerador_dados/nucleo_log.py`, executar `git rm gerador_dados/nucleo_log.py`.

```bash
git mv gerador_dados/tabuleiro.py          gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py
git mv gerador_dados/minimax.py            gerador_dados/jogo_pontinhos/minimax_pontinhos.py
git mv gerador_dados/gerador.py            gerador_dados/jogo_pontinhos/gerador_pontinhos.py
git mv gerador_dados/visualizador.py       gerador_dados/jogo_pontinhos/visualizador_pontinhos.py
git mv gerador_dados/avaliador_partidas.py gerador_dados/jogo_pontinhos/avaliador_partidas_pontinhos.py
git mv gerador_dados/simulador/simulador_tatico.py gerador_dados/jogo_pontinhos/simulador_tatico_pontinhos.py
git mv gerador_dados/contrato_codificacao_pontinhos.py gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py
git mv gerador_dados/contrato_codificacao_pontinhos.json gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json
# Decidir destino final de nucleo_log.py antes de executar o mv
```

Após os moves, deletar pasta vazia:
```bash
rmdir gerador_dados/simulador   # fica vazia após mover simulador_tatico.py
```

### 2.3 Atualizar imports dentro de `gerador_dados/jogo_pontinhos/`

Após mover, todos os arquivos precisam de imports atualizados. Mapa completo:

**`minimax_pontinhos.py`** — 1 import a corrigir:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
```

**`gerador_pontinhos.py`** — 2 imports a corrigir:
```python
# ANTES:
from gerador_dados.minimax import melhor_jogada_com_scores
from gerador_dados.tabuleiro import EstadoTabuleiro, TAMANHOS, todos_labels_canonicos
# DEPOIS:
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada_com_scores
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS, todos_labels_canonicos
```

**`avaliador_partidas_pontinhos.py`** — 3 imports a corrigir:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.minimax import melhor_jogada, _scores_de_todas_jogadas
from gerador_dados.contrato_codificacao_pontinhos import (...)
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, todos_labels_canonicos
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada, _scores_de_todas_jogadas
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (...)
```

**`simulador_tatico_pontinhos.py`** — 4 imports a corrigir:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro, TAMANHOS
from gerador_dados.minimax import melhor_jogada
from gerador_dados.nucleo_log import obter_logger
from gerador_dados.contrato_codificacao_pontinhos import (...)
# + import lazy dentro de função:
from gerador_dados.tabuleiro import todos_labels_canonicos
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada
from api.nucleo.log import obter_logger  # ou api.nucleo.nucleo_log conforme decisão
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (...)
# + import lazy:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import todos_labels_canonicos
```

**`visualizador_pontinhos.py`** — 1 import a corrigir:
```python
# ANTES:
from gerador_dados.nucleo_log import obter_logger
# DEPOIS:
from api.nucleo.log import obter_logger
```

**`contrato_codificacao_pontinhos.py`** — verificar path do JSON:
```python
# O path hardcoded para o JSON precisa ser atualizado de:
Path(__file__).parent.parent / "contrato_codificacao_pontinhos.json"
# Para (dentro de jogo_pontinhos/):
Path(__file__).parent / "contrato_codificacao_pontinhos.json"
```

### 2.4 Atualizar imports nos testes

**`tests/unitarios/test_contrato_codificacao_pontinhos.py`** — 3 mudanças:
```python
# ANTES:
from gerador_dados.contrato_codificacao_pontinhos import (...)
JSON_BACKEND = RAIZ_BACKEND / "gerador_dados" / "contrato_codificacao_pontinhos.json"
# DEPOIS:
from gerador_dados.jogo_pontinhos.contrato_codificacao_pontinhos import (...)
JSON_BACKEND = RAIZ_BACKEND / "gerador_dados" / "jogo_pontinhos" / "contrato_codificacao_pontinhos.json"
```

**`tests/unitarios/test_minimax.py`** — 2 imports:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro
from gerador_dados.minimax import melhor_jogada, minimax
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.minimax_pontinhos import melhor_jogada, minimax
```

**`tests/unitarios/test_tabuleiro.py`** — 1 import:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro, TAMANHOS
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro, TAMANHOS
```

**`tests/unitarios/test_visualizador.py`** — 2 imports:
```python
# ANTES:
from gerador_dados.tabuleiro import EstadoTabuleiro
from gerador_dados.visualizador import lote_para_png, matriz_para_png
# DEPOIS:
from gerador_dados.jogo_pontinhos.tabuleiro_pontinhos import EstadoTabuleiro
from gerador_dados.jogo_pontinhos.visualizador_pontinhos import lote_para_png, matriz_para_png
```

### 2.5 Renomear arquivos de teste

Mover os testes para `tests/unitarios/jogo_pontinhos/`:

```bash
mkdir -p tests/unitarios/jogo_pontinhos
touch tests/unitarios/jogo_pontinhos/__init__.py
git mv tests/unitarios/test_contrato_codificacao_pontinhos.py tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py
git mv tests/unitarios/test_tabuleiro.py   tests/unitarios/jogo_pontinhos/test_tabuleiro_pontinhos.py
git mv tests/unitarios/test_minimax.py     tests/unitarios/jogo_pontinhos/test_minimax_pontinhos.py
git mv tests/unitarios/test_visualizador.py tests/unitarios/jogo_pontinhos/test_visualizador_pontinhos.py
```

Os testes que ficam em `tests/unitarios/` (fora de jogo_pontinhos/):
- `test_seguranca.py` — testa `api/nucleo/seguranca.py` (hub)
- `test_xp.py` — testa lógica de XP da plataforma (hub)

### 2.6 Verificar que os testes passam

```bash
python -m pytest tests/unitarios/ -v
```

Todos os 12 testes do contrato devem continuar passando após o refactor de imports.

**Checklist fase 2:**
- [ ] `gerador_dados/jogo_pontinhos/` criado com `__init__.py`
- [ ] Todos os 8 arquivos movidos/renomeados com `git mv`
- [ ] `gerador_dados/simulador/` removida (vazia)
- [ ] `nucleo_log.py` tratado (decidir: fundir em `api/nucleo/log.py` ou mover)
- [ ] Imports corrigidos em todos os 5 arquivos de `gerador_dados/jogo_pontinhos/`
- [ ] Path do JSON no `contrato_codificacao_pontinhos.py` corrigido
- [ ] Imports corrigidos nos 4 arquivos de teste afetados
- [ ] Testes de `test_contrato` e demais movidos para `tests/unitarios/jogo_pontinhos/`
- [ ] `python -m pytest tests/unitarios/ -v` — todos passando
- [ ] Commit intermediário: `refactor(gerador_dados): reorganiza em jogo_pontinhos/, renomeia legados`

---

## Fase 3 — Reorganização de `notebooks/`

**Objetivo:** mover todos os notebooks para `notebooks/jogo_pontinhos/`.

### 3.1 Criar pasta e mover

```bash
mkdir -p notebooks/jogo_pontinhos
git mv notebooks/Avaliacao_CNN_vs_Minimax.ipynb          notebooks/jogo_pontinhos/
git mv notebooks/Otimizacao_Topologia_Rede.ipynb         notebooks/jogo_pontinhos/
git mv notebooks/Otimizacao_Topologia_Rede_V2.ipynb      notebooks/jogo_pontinhos/
git mv notebooks/Otimizacao_Topologia_Rede_V3.ipynb      notebooks/jogo_pontinhos/
git mv notebooks/Treinamento_CNN_Arena_Sagaz.ipynb       notebooks/jogo_pontinhos/
git mv notebooks/Treinamento_CNN_Arena_Sagaz_V3.ipynb    notebooks/jogo_pontinhos/
```

### 3.2 Atualizar paths em `Avaliacao_CNN_vs_Minimax.ipynb`

**Apenas este notebook** precisa de atualização de paths (os demais são histórico).

Abrir o notebook e localizar células que referenciam:
- `gerador_dados/tabuleiro` → `gerador_dados/jogo_pontinhos/tabuleiro_pontinhos`
- `gerador_dados/minimax` → `gerador_dados/jogo_pontinhos/minimax_pontinhos`
- `gerador_dados/avaliador_partidas` → `gerador_dados/jogo_pontinhos/avaliador_partidas_pontinhos`
- `gerador_dados/contrato_codificacao_pontinhos` → `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos`

Atualizar via Grep no JSON do ipynb:
```bash
grep -n "gerador_dados\." notebooks/jogo_pontinhos/Avaliacao_CNN_vs_Minimax.ipynb
```

### 3.3 Atualizar `guia_geracao_dados.md`

O guia em `docs/jogo_pontinhos/guia_geracao_dados.md` pode ter instruções de como executar os notebooks. Verificar se menciona paths e atualizar.

**Checklist fase 3:**
- [ ] `notebooks/jogo_pontinhos/` criado
- [ ] Todos os 6 notebooks movidos
- [ ] `Avaliacao_CNN_vs_Minimax.ipynb` com imports atualizados
- [ ] `guia_geracao_dados.md` com paths atualizados (se necessário)
- [ ] Commit intermediário: `refactor(notebooks): move todos para jogo_pontinhos/`

---

## Fase 4 — Nova `api/` layer-driven (branch separada)

**Esta fase NÃO é executada na branch `002-refatoracao-estrutural`.**
**Pré-requisito: primeiro jogo rodando no Frontend.**

### Estratégia

```bash
# Criar a partir de main — não de 001 ou 002
git checkout main
git checkout -b 003-api-layer-driven
```

Partir da `api/` minimalista já existente (nucleo/ + main + configuracao) e adicionar
as camadas conforme as definições ficarem claras. Não copiar nada do código SpecKit.

### Autenticação: Firebase Auth

Ao implementar auth, instalar:
```
firebase-admin>=6.0.0
```

Descomentar no `requirements.txt` e no `.env.example`.

Fluxo no backend:
1. Flutter autentica com Firebase e recebe um `idToken`.
2. Flutter envia `Authorization: Bearer <idToken>` em chamadas à API.
3. Backend valida com `firebase_admin.auth.verify_id_token(token)`.
4. Nenhuma senha é armazenada no backend — Firebase gerencia tudo.

O router de auth no backend será mínimo: apenas um endpoint `POST /v1/auth/verificar`
que valida o token e retorna o `uid` Firebase (para associar com dados no banco).

### Estrutura-alvo da nova api/

```
api/
├── main.py               (adicionar novos routers aqui conforme criados)
├── configuracao.py       (adicionar FIREBASE_PROJECT_ID quando implementar auth)
├── nucleo/               (já existe, não mexer)
├── banco/                (criar quando modelo de dados definido)
│   ├── base.py
│   ├── conexao.py
│   └── migrations/
├── routers/
│   └── v1/
│       ├── __init__.py
│       ├── jogo_pontinhos/
│       │   ├── __init__.py
│       │   └── partidas.py     # POST /v1/pontinhos/partidas
│       ├── auth.py             # POST /v1/auth/verificar (valida Firebase token)
│       ├── usuarios.py         # GET/PATCH /v1/usuarios/me
│       └── ranking.py          # GET /v1/ranking
├── schemas/
│   └── v1/
│       ├── jogo_pontinhos/
│       └── ...
├── models/
│   ├── jogo_pontinhos/
│   └── ...
└── services/
    └── v1/
        ├── jogo_pontinhos/
        └── ...
```

### Nota sobre Alembic

Ao criar `api/banco/migrations/env.py`, garantir que todos os models SQLAlchemy
sejam importados ANTES de `target_metadata = Base.metadata` — Alembic só detecta
tabelas cujos models foram importados no `env.py`.

**Checklist fase 4** (sessão dedicada, branch `003-api-layer-driven`):
- [ ] Branch `003-api-layer-driven` criada a partir de `main`
- [ ] Primeira rota de jogo implementada e testada (ex: `POST /v1/pontinhos/partidas`)
- [ ] Firebase Auth integrado (opcional nesta fase se auth ainda não for prioridade)
- [ ] `api/banco/` criado com primeira migration
- [ ] Testes de integração passando: `python -m pytest tests/integracao/ -v`

---

## Fase 5 — Atualizar configurações e documentação

**Executar na branch `002-refatoracao-estrutural` após fases 1–3.**

### 5.1 pytest.ini

Verificar `testpaths` e `python_files` — devem encontrar testes em `tests/unitarios/jogo_pontinhos/`:
```ini
testpaths = tests
```
Se já usa `tests` como raiz, não precisa mudar.

### 5.2 Dockerfile

Verificar se há algum `COPY` ou `CMD` que referencia paths específicos de `gerador_dados/`:
```bash
grep -n "gerador_dados\|simulador\|avaliador" Dockerfile
```
Atualizar paths se necessário.

### 5.3 alembic.ini

Verificar `script_location` aponta para `api/banco/migrations` — não deve mudar.

### 5.4 CLAUDE.md

Atualizar os paths mencionados nas diretivas obrigatórias:
- Contrato: novo path `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`
- Teste CI: novo path `tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py`

### 5.5 `specs/001-fase-zero-backend/plan.md`

Verificar se menciona paths que mudaram e atualizar.

### 5.6 `docs/historico_decisoes.md`

Adicionar entrada com data da refatoração, decisões de estrutura e motivação.

**Checklist fase 5:**
- [ ] `pytest.ini` verificado/atualizado
- [ ] `Dockerfile` verificado/atualizado
- [ ] `alembic.ini` verificado
- [ ] `CLAUDE.md` com paths atualizados
- [ ] `docs/historico_decisoes.md` com entrada da refatoração
- [ ] `python -m pytest tests/ -v` — todos passando na nova estrutura
- [ ] Commit final: `refactor(estrutura): reorganização completa — docs, gerador_dados, notebooks`

---

## Fase 6 — Push e PR

```bash
git push -u origin 002-refatoracao-estrutural
# Criar PR: 002-refatoracao-estrutural → 001-fase-zero-backend
```

> **Base do PR:** `001-fase-zero-backend`, não `main`. A fase zero ainda não foi mergeada em main.

---

## Notas de sessão

### Como iniciar uma nova sessão de execução

Diga ao modelo: "Executar Fase N do plano em `docs/todo/refatoracao_estrutural.md`. Leia o documento e marque os checkboxes conforme conclui cada item."

### Armadilhas conhecidas

1. **`git mv` vs `mv`** — sempre use `git mv` para preservar histórico.
2. **`__pycache__/`** — pode ficar órfão após moves; `git status` vai ignorar (já está em .gitignore).
3. **Path do JSON no contrato** — o helper usa `Path(__file__).parent` para localizar o JSON; após mover o `.py` para dentro de `jogo_pontinhos/`, o JSON também deve estar lá (já planejado).
4. **Hash test frontend** — o teste compara `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` com `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`. Atualizar o path no teste.
5. **`nucleo_log.py`** — verificar se `api/nucleo/log.py` já exporta `obter_logger()` antes de decidir: fundir ou re-exportar.
6. **Import circular** — `simulador_tatico_pontinhos.py` importa de `api.nucleo.log`. Verificar que `api/` não importa de volta de `gerador_dados/` (não deve, mas verificar).

### Estimativa de esforço por fase

| Fase | Esforço estimado | Modelo recomendado |
|---|---|---|
| 0 — Backup + limpeza | 5 min | Sonnet normal |
| 1 — docs/ | 10 min | Sonnet normal |
| 2 — gerador_dados/ | 30–45 min | Sonnet normal |
| 3 — notebooks/ | 10 min | Sonnet normal |
| 4 — api/ nova | 2–4 h (sessão dedicada) | Opus high |
| 5 — Configs + docs | 15 min | Sonnet normal |
| 6 — PR | 5 min | Sonnet normal |
