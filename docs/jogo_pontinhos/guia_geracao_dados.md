# Guia Completo: Geração de Dados e Simulador - Fase Zero

Com base na documentação e no código gerado para a **Fase Zero** do projeto Arena Sagaz, este é o guia passo a passo para iniciar a geração de dados, monitorar o progresso, visualizar as matrizes e testar o simulador tático.

Certifique-se de estar dentro da pasta `arena-sagaz-backend` e com seu ambiente virtual ativado.

---

## 0A. Treinamento CNN — PC Local (`.venv_gpu`, V10)

> **Decisão 2026-05-25**: o Colab free-tier não comporta os 608 NPZs (OOM ~12 GB).
> O treinamento migrou para o PC local usando `Treinamento_CNN_Pontinhos_V10.ipynb`.

### Pré-requisitos de hardware

| Item | Mínimo para CPU | Recomendado (GPU) |
|---|---|---|
| RAM | 16 GB | 32 GB |
| GPU VRAM | — | 4 GB (GTX 1650 ou superior) |
| Armazenamento livre | 5 GB | 5 GB |

### Ativar o ambiente `.venv_gpu`

```powershell
.\.venv_gpu\Scripts\activate
```

O `.venv_gpu` já está configurado com **Python 3.10.11 + TensorFlow 2.10.0** (último TF com
GPU nativa no Windows). Para verificar:

```powershell
python -c "import tensorflow as tf; print(tf.__version__, tf.config.list_physical_devices('GPU'))"
```

Saída esperada sem GPU: `2.10.0 []`
Saída esperada com GPU: `2.10.0 [PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]`

### Habilitar a GPU GTX 1650 (ação manual)

TF 2.10 requer **CUDA Toolkit 11.2** e **cuDNN 8.1** instalados separadamente no Windows.

1. **CUDA 11.2**: baixar e instalar de `https://developer.nvidia.com/cuda-11-2-2-download-archive`
   - Selecionar: Windows > x86_64 > 10 > exe (local)
   - Após a instalação, `cudart64_110.dll` deve estar em `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.2\bin\`
   - Adicionar `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.2\bin` ao PATH do sistema.

2. **cuDNN 8.1**: baixar de `https://developer.nvidia.com/rdp/cudnn-archive` (conta gratuita NVIDIA)
   - Versão: cuDNN 8.1.x for CUDA 11.x (Windows)
   - Copiar arquivos da pasta `bin\` do cuDNN para `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.2\bin\`

3. Reiniciar o terminal e verificar: `python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"`

> **Sem CUDA**: o notebook V10 funciona em CPU — apenas mais lento (8–20h vs 8–14h com GPU).

### Rodar o notebook de treinamento

```powershell
# Ativar o kernel no Jupyter (já registrado):
jupyter notebook notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V10.ipynb
```

Selecione o kernel **"Python 3.10 (venv_gpu — TF 2.10 GPU)"** na interface do Jupyter.

Saídas geradas automaticamente em `resultados/jogo_pontinhos/`:
- `BoxNet_V10_12canais_best_valloss.keras` — checkpoint do melhor modelo
- `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss.tflite` — modelo TFLite
- `pontinhos_pequeno_cnn_depth_11_e_20_12canais_valloss_treinamento_<timestamp>.md` — relatório

---

## 0. Preparando o Ambiente Virtual (Windows)

Antes de executar os scripts, você precisa criar e ativar um ambiente virtual isolado para instalar as dependências do projeto.

Abra o terminal (PowerShell ou Prompt de Comando) na pasta `arena-sagaz-backend` e execute:

### Criar o ambiente virtual
```powershell
python -m venv .venv
```

### Ativar o ambiente virtual
```powershell
.venv\Scripts\activate
```
*(Nota: Se usar PowerShell e ocorrer erro de permissão, execute `Set-ExecutionPolicy Unrestricted -Scope CurrentUser` primeiro e tente ativar novamente.)*

Quando ativado, você verá `(.venv)` no início da linha de comando.

### Instalar dependências
```powershell
pip install -r requirements.txt
```

---

## 1C. Pipeline V7 — Adaptativo (DAC) `Geracao_Amostras_v7_adaptativo.ipynb`

> **Pipeline atual** acordado em 2026-05-08 (ver `docs/historico_decisoes.md`,
> entrada V7). Substitui o V6 (§1B) por profundidade Minimax adaptativa,
> Boltzmann sampling e snapshots por partida. Fundamentação completa em
> `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`.

> **EXECUTADO (2026-05-12):** 152 NPZs em `dados/profundidade_minimax_11_v7_adaptativo/`
> (~758k amostras brutas, ~500k distintos, cobertura t=1–30). Fase 1 rodou local;
> Fase 2 (Minimax p=11) rodou no Databricks via
> `Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb`. Dois bugs críticos de
> Bitboard corrigidos (falsos positivos em caixas pré-fechadas + offset alpha-beta
> incremental). Schema V2 — ver `specs/004-melhoria-geracao-dados-cnn/contracts/npz_schema.md`.

### Visão geral

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Fase 1 — Geração de estados via DAC                                      │
│   Notebook:  notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb│
│   Workers:   gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py│
│   Saída:     dados/profundidade_minimax_11_v7_adaptativo/dataset_pequeno_*.npz│
│              (campos da Fase 2 como placeholder)                         │
│   Algoritmo: Minimax(p adaptativo por τ) + Boltzmann(T(t)).              │
│              30 snapshots/partida. Sem faixas, sem quotas.               │
│   Meta:      ≥ 500.000 estados DISTINTOS                                  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼  (mesmo notebook, célula seguinte)
┌──────────────────────────────────────────────────────────────────────────┐
│ Fase 2 — Cálculo da melhor jogada (Minimax p=11, via Databricks)         │
│   - Coleta estados únicos cobrindo TODOS os NPZs pendentes               │
│   - Roda `melhor_jogada_com_scores` em paralelo (cache por hash)         │
│   - Reescreve cada NPZ atomicamente (.tmp.npz + os.replace), populando   │
│     melhor_jogada, score_melhor_jogada, depth_melhor_jogada.             │
└──────────────────────────────────────────────────────────────────────────┘
```

### Schema do NPZ V2

| Campo | Shape | Dtype | Fase | Descrição |
|---|---|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` | 1 | Matriz neutra `{0,1,8,9}` |
| `qtd_tracos` | `(N,)` | `int8` | 1 | Número de traços (1..30) |
| `score_jogada` | `(N, 31)` | `float32` | 1 | Scores Minimax(p adaptativo) no estado atual |
| `depth_jogada` | `(N,)` | `int8` | 1 | Profundidade Minimax usada NESTE estado |
| `depth_geracao` | `(N,)` | `int8` | 1 | Profundidade Minimax usada no estado anterior |
| `melhor_jogada` | `(N,)` | `<U5` | 2 | Argmax de `score_melhor_jogada` |
| `score_melhor_jogada` | `(N, 31)` | `float32` | 2 | Scores Minimax(p=11, execução atual) — **verdade-padrão para treino** |
| `depth_melhor_jogada` | `(N,)` | `int8` | 2 | Profundidade Minimax usada (=11 na execução atual) |
| `labels_canonicos` | `(31,)` | `<U5` | 1 | Ordem dos slots de score |

### Como rodar

#### Fase 1 — Geração local (máquina do desenvolvedor)

```powershell
.venv\Scripts\activate
jupyter lab notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb
```

Execute as células sequencialmente:

1. **§2 (Recuperação)** — varre `dados/profundidade_minimax_11_v7_adaptativo/`
   e mostra estados distintos já gerados. Permite retomada idempotente.
2. **§3 (Fase 1)** — `fase1_gerar(...)` aciona `ProcessPoolExecutor` com
   `cpu_count()-2` workers. Cada partida emite 30 snapshots (t=1..30).
   Loop até atingir 500k distintos, depois drena partidas em curso.
3. **§5 (Auditoria local)** — sanidade do dataset gerado (domínio do tensor,
   distribuição por `qtd_tracos`, distribuição de profundidades).

Os NPZs gerados terão `melhor_jogada = ""` (placeholder) até a Fase 2 rodar.

#### Fase 2 — Enriquecimento no Databricks (supervisão Minimax profunda)

1. Subir os NPZs de `dados/profundidade_minimax_11_v7_adaptativo/` para o
   workspace Databricks (ex.: `/Workspace/Users/diondu@gmail.com/CNN/profundidade_7_v7_adaptativo`).
2. Abrir `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb`
   no Databricks.
3. Ajustar as constantes no início do notebook:
   ```python
   INPUT_DIR = Path("/Workspace/Users/diondu@gmail.com/CNN/profundidade_7_v7_adaptativo")
   DEPTH_TARGET = 11   # profundidade da supervisão Minimax
   LOTE_ARQUIVOS = 4   # ~20.000 amostras por checkpoint
   ```
4. Executar todas as células. O notebook:
   - Detecta automaticamente os NPZs com `melhor_jogada[0] == ""` (pendentes).
   - Distribui os estados via `mapInPandas` para os workers Spark.
   - Grava `melhor_jogada`, `score_melhor_jogada` e `depth_melhor_jogada` via
     sobrescrita atômica (`.tmp.npz` + `os.replace`).
   - Faz checkpoint a cada lote de 4 NPZs — retomada automática se o cluster cair.
5. Baixar os NPZs enriquecidos de volta para `dados/profundidade_minimax_11_v7_adaptativo/`.

### Retomada

- Interromper qualquer célula → re-executar a partir da §2 reconstrói o
  estado e continua de onde parou. O último lote em buffer (sub-5.000)
  é perdido se a Fase 1 cair antes do flush — aceitável.
- Fase 2 é idempotente: NPZs com `melhor_jogada[0] != ""` são pulados.

### Notas de implementação

- **Algoritmo DAC** está documentado em detalhe (fórmulas, exemplo de
  partida turno-a-turno, distribuição emergente esperada e justificativa
  dos pesos) em `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`.
  Esse documento é o material de referência para o TCC.
- **Formato neutro** segue o contrato §`contexto_1_geracao_dataset` em
  `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`.
- **Duplicatas são gravadas no NPZ** — apenas o set de hashes em memória
  é usado para contar distintos e disparar o stop. Dedup ocorre no
  notebook de treino.
- **30 estados por partida** (t=1..30); t=0 (vazio) e t=31 (terminal) são
  descartados.
- **Ordem dos campos `score_jogada` vs `score_melhor_jogada`**:
  `score_jogada` vem de Minimax raso (p adaptativo, qualidade variável)
  e serve para análise/curriculum. `score_melhor_jogada` é a verdade-padrão
  para treino. Não confundir.

---

## 1B. Pipeline V6 — Notebook único `Geracao_Amostras_v6.ipynb`

> **Pipeline anterior**, substituído pelo V7 adaptativo (§1C). Mantido aqui
> para referência histórica e para auditar NPZs já gerados em
> `dados/profundidade_minmax_7_corrigido/`. Não usar para novas rodadas.

> Pipeline acordado em 2026-05-08 (ver `docs/historico_decisoes.md`).
> Substitui o fluxo V5 (Databricks + V5_Local + consolidação) por um único
> notebook local em duas fases, sem dependência de Databricks.

### Visão geral

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Fase 1 — Geração de estados                                              │
│   Notebook:  notebooks/jogo_pontinhos/Geracao_Amostras_v6.ipynb          │
│   Workers:   gerador_dados/jogo_pontinhos/gerador_amostras_v6_pontinhos.py │
│   Saída:     dados/profundidade_minmax_7_corrigido/dataset_pequeno_*.npz │
│              (rotulos vazios, scores = -1e9 — placeholder)               │
│   Modo:      95% autoplay Minimax(p=3) × Minimax(p=3) | 5% aleatório     │
│   Quotas:    501.500 estados DISTINTOS por faixa de traços               │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼  (mesmo notebook, célula seguinte)
┌──────────────────────────────────────────────────────────────────────────┐
│ Fase 2 — Cálculo da melhor jogada (Minimax p=7)                          │
│   - Coleta estados únicos cobrindo TODOS os NPZs                         │
│   - Roda `melhor_jogada_com_scores` em paralelo (cache por hash)         │
│   - Reescreve cada NPZ atomicamente (.tmp + os.replace), populando       │
│     rotulos e scores; estados/generation_mode preservados.               │
└──────────────────────────────────────────────────────────────────────────┘
```

### Distribuição-alvo (estados distintos, 501.500 no total)

| Faixa de traços | Quota | % |
|---|---:|---:|
| 5–11 (abertura) | 55.000 | 10,97% |
| 12–17 (1ª metade) | 160.000 | 31,90% |
| 18–23 (2ª metade) | 220.000 | 43,87% |
| 24–28 (fase quente) | 66.000 | 13,16% |
| 29–30 (final) | 500 | 0,10% |

### Schema do NPZ (idêntico ao de referência)

| Campo | Shape | Dtype |
|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` (domínio `{0, 1, 8, 9}`) |
| `rotulos` | `(N,)` | `<U5` |
| `scores` | `(N, 31)` | `float32` |
| `generation_mode` | `(N,)` | `int8` — `0`=aleatório, `3`=autoplay p=3 |
| `labels_canonicos` | `(31,)` | `<U5` |
| `minimax_depth` | `(1,)` | `int32` (= 7) |

### Como rodar

```powershell
# Ative o venv e abra o Jupyter
.venv\Scripts\activate
jupyter lab notebooks/jogo_pontinhos/Geracao_Amostras_v6.ipynb
```

Execute as células sequencialmente. As três etapas principais:

1. **Célula §2 (Recuperação)** — varre `dados/profundidade_minmax_7_corrigido/`
   e mostra o progresso por faixa. Permite retomada: o estado é **inteiramente
   reconstruído a partir do diretório**, sem sidecar JSON.
2. **Célula §3 (Fase 1)** — chama `fase1_gerar(...)` que aciona um
   `ProcessPoolExecutor` com `cpu_count()-2` workers (Ryzen 7 5700X → 14
   workers). Logs a cada 30 s e a cada NPZ salvo.
3. **Célula §4 (Fase 2)** — `fase2_scoring()` colete o set de estados únicos
   pendentes, roda Minimax(p=7) em paralelo (cache por bytes do tabuleiro)
   e reescreve cada NPZ atomicamente.

### Retomada

- Interromper qualquer célula → re-executar a partir da §2 reconstrói o
  estado e continua de onde parou. O último lote em buffer (sub-5.000)
  é perdido se a Fase 1 cair antes do flush — aceitável, basta deixar o
  motor gerar mais alguns estados.
- Fase 2 é idempotente: NPZs com `rotulos[0] != ""` são pulados.

### Notas de implementação

- **Formato neutro `{0,1,8,9}`** segue o contrato §`contexto_1_geracao_dataset`
  em `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json`. A
  conversão de matriz live → neutra é **posicional** (par/ímpar), não por
  valor — evita ambiguidade entre traço `+1` e caixa fechada `+1`.
- **Determinismo**: o main usa `SEED_GLOBAL` para sortear modo (random/auto)
  e seed por worker; cada worker reseta `random.seed(...)` para o
  desempate aleatório do Minimax ficar reproduzível por chamada.
- **Distintos**: chave do set é `estados[i].tobytes()` da matriz já neutra.
  Tabuleiros gerados por modos diferentes mas estruturalmente idênticos
  contam como uma única amostra distinta.

---

## 1A. Pipeline V5/V6 — Fase A.1 + A.2 (cobertura terminal expandida + 11 canais)

> Esta seção documenta o **pipeline atual** definido em `specs/004-melhoria-geracao-dados-cnn/`.
> O fluxo legado em duas etapas (script `gerador_pontinhos.py` local + notebook V4 no Databricks)
> continua funcional para auditoria histórica e está descrito a partir da Seção 1 abaixo.

### Visão geral

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Fase A.1 — Databricks                                                   │
│   Notebook: Otimizacao_Topologia_Rede_V5.ipynb                          │
│   Saída:    NPZs em /Workspace/.../profundidade_9/dataset_pequeno_*.npz │
│             Campos: estados, rotulos, scores, generation_mode,          │
│                     labels_canonicos, depth                             │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼  (cópia local)
┌─────────────────────────────────────────────────────────────────────────┐
│ Fase A.2 — local/Colab                                                  │
│   Notebook: Enriquece_NPZ_Com_Canais.ipynb                              │
│   Sobrescrita atômica: <arquivo>.tmp + os.replace()                     │
│   Campos novos: canais (N,4,3,11) int8, nomes_canais (11,) <U32         │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Validação visual (gate manual da A.2)                                   │
│   Script: scripts/pontinhos/validar_canais_visualmente.py               │
│   ≥ 30 PNGs revisados nas faixas t∈[12,17], [24,28], [29,30]            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1A.1 — Fase A.1 no Databricks (geração)

1. **Pré-requisito**: o NPZ legado V4 (`profundidade_9_legado/`) com seus 314.323 estados únicos por `mat.tobytes()` precisa estar disponível no workspace para a pré-população do set de hashes.
2. Subir o notebook `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb` no Databricks.
3. Executar célula a célula até a célula `[T-A1-002 + T-A1-003]` — ela define `COMPLEMENTO_POR_CELULA`, `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` e `FAIXA_TRACOS = (0.15, 0.97)`. **`sim_l1` está desligado** (peso 0).
4. Executar a célula `[T-A1-004]` — pré-popula `hashes_iniciais` lendo o legado.
5. **Adaptar manualmente** a célula 9 (laço principal — herdada do V4) para:
   - usar `hashes_iniciais` como state inicial do set de dedup;
   - sortear `(gen_mode, faixa)` consultando `COMPLEMENTO_POR_CELULA` até fechar todas as cotas;
   - descartar e regerar estado duplicado por `mat.tobytes()` (até 20 tentativas).
6. Rodar o laço principal e o **diagnóstico V4** (célula 10).
7. Executar a célula final `[T-A1-005]` — auditoria pós-execução: confere ≥ 500.000 únicos, distribuição empírica dentro da tolerância ±2pp por bucket, mix `gen_mode` e `sim_l1 == 0`.
8. Baixar os NPZs do Databricks para a máquina local (ou ponto compartilhado lido pelo Colab).

> **Nota**: a otimização de cluster (workers/cores/timeout) é decidida pelo desenvolvedor no momento da execução — não é parametrizada na spec (research.md §1.1, clarification 2026-05-07).

#### 1A.1.alt — Alternativa local (sem Databricks): `Otimizacao_Topologia_Rede_V5_Local.ipynb`

Quando não há cluster Databricks pago disponível e o serverless free é
inviável (overhead de Spark domina; ver entrada 2026-05-07 em
`docs/historico_decisoes.md`), o pipeline A.1 pode rodar **inteiramente
local** com `multiprocessing`. A lógica é a mesma do PRD §4.1.3 rev.3
(loop por cota com `COMPLEMENTO_POR_CELULA`, dedup contra `hashes_iniciais`).

> **Estado atual (2026-05-08 rev.5 — CONSOLIDAÇÃO CONCLUÍDA):**
> `Consolidar_500k_Final.ipynb` executado com sucesso — **499.997 estados únicos**
> (shortfall residual: 3, arredondamento).
> Distribuição: 55.501 / 169.875 / 223.551 / 50.867 / 203.
> Mix gen_mode: 5,00% / 40,06% / 54,94%.
> Origem: legado=168.661, v5_databricks=181.456, v5_local=149.880.
> Saída: 100 NPZs em `dados/profundidade_minmax_9/`.
> **Próximo passo: executar `Enriquece_NPZ_Com_Canais.ipynb` (Fase A.2).**

**Artefatos:**

- `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb` — notebook orquestrador.
- `notebooks/jogo_pontinhos/v5_local_engine.py` — engine importável pelos
  workers spawnados (precisa ser `.py` porque `multiprocessing` no Windows usa `spawn`).

**Como rodar (para nova geração do zero ou retomada):**

1. **Pré-requisito**: legado em `dados/profundidade_minmax_9/` e
   V5_Databricks em `dados/profundidade_minmax_9_v5_databricks/` presentes.
2. Abrir o notebook em VS Code/Jupyter local. Editar `REPO_ROOT` se necessário.
3. Atualizar `COMPLEMENTO_POR_CELULA` com os alvos por célula (ver PRD §4.1.3).
4. Executar todas as células sequencialmente. O loop principal:
   - Pré-popula `hashes_iniciais` com legado + v5_databricks.
   - Checkpoint lê v5_local existente e decrementa cotas (retoma de onde parou).
   - Sorteia `(gen_mode, bucket)` ponderado por cota residual.
   - Pool de `cpu_count()-1` workers gera, dedup, decrementa cota.
   - Para quando todas as cotas zeram.
5. **Saída**: `dados/profundidade_minmax_9_v5_local/dataset_pequeno_*.npz`.

**Quando preferir Databricks:** geração massiva em cluster pago dedicado.
Free serverless **não** é recomendado.

#### 1A.1.cons — Consolidação ~500k (novo passo, entre A.1 e A.2)

A geração da Fase A.1 produz **três diretórios** (consolidado em 2026-05-08 rev.5):

| Diretório | Conteúdo | Aceitos na consolidação |
|---|---|---:|
| `dados/profundidade_minmax_9_desbalanceado/` | Legado V4 | 168.661 |
| `dados/profundidade_minmax_9_v5_databricks/` | V5 Databricks | 181.456 |
| `dados/profundidade_minmax_9_v5_local/` | V5 Local | 149.880 |
| **Total consolidado** | | **499.997 únicos** |

**Distribuição final consolidada (rev.5):**

| Bucket | Consolidado | % |
|---|---:|---:|
| 5–11 | 55.501 | 11,10% |
| 12–17 | 169.875 | 33,98% |
| 18–23 | 223.551 | 44,71% |
| 24–28 | 50.867 | 10,17% — CAPEADO (autoplay satura) |
| 29–30 | 203 | 0,04% — LIMITE FÍSICO |

**Notebook:** `notebooks/jogo_pontinhos/Consolidar_500k_Final.ipynb`.

**Como rodar:**

1. Abrir `Consolidar_500k_Final.ipynb`. Editar `REPO_ROOT` se necessário.
2. Executar todas as células sequencialmente.
   - **Passo 1**: lê legado, aceita até `cota_alvo[m,b]` rev.5 (descarta `sim_l1`,
     bucket `<5` e `>30`, duplicatas, excedentes).
   - **Passo 2**: lê v5_databricks + v5_local, completa células abertas.
   - **Gravação**: embaralha global (seed=42), grava 100 NPZs em
     `dados/profundidade_minmax_9/dataset_pequeno_*.npz`.
   - **Auditoria**: confere total ≥ 499.000 (shortfall ≤ 1.000 aceito),
     dedup, desvio por bucket ≤ ±2pp, `sim_l1 == 0`.

**Saída**: `dados/profundidade_minmax_9/` com **499.997 estados únicos**
(100 NPZs), prontos para a Fase A.2.

### 1A.2 — Fase A.2 local: enriquecer NPZ com 11 canais

> **Status (2026-05-12): PENDENTE.** Os NPZs em `dados/profundidade_minimax_11_v7_adaptativo/`
> estão prontos (Fase A.1 concluída), mas ainda não foram enriquecidos com os canais estruturais.

```powershell
# Pré-requisito: módulo analisador disponível.
py -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais, NOMES_CANAIS; print(len(NOMES_CANAIS))"
# Esperado: 11
```

Abra `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` (Jupyter ou VSCode).
Na **segunda célula** do notebook, altere `DIR_NPZ`:

```python
DIR_NPZ = 'dados/profundidade_minimax_11_v7_adaptativo/'  # dataset V7 com schema V2
PADRAO  = 'dataset_pequeno_*.npz'
FORCAR_REGRAVAR = False   # True só se o algoritmo de canais mudar
```

O notebook é **schema-agnóstico**: usa `novo = dict(d)` para preservar todos os campos
existentes e apenas acrescenta `canais` e `nomes_canais`. Funciona com schema V2 sem
nenhuma alteração adicional.

Rode todas as células. O notebook:

- lê cada NPZ (152 arquivos, ~5.000 estados cada);
- chama `extrair_canais(estados[i])` para cada estado;
- adiciona `canais (N, 4, 3, 11) int8` e `nomes_canais (11,) <U32`;
- preserva todos os campos do schema V2 (`estados`, `qtd_tracos`, `score_jogada`,
  `depth_jogada`, `depth_geracao`, `melhor_jogada`, `score_melhor_jogada`,
  `depth_melhor_jogada`, `labels_canonicos`);
- regrava via `np.savez_compressed(<path>.tmp.npz, ...)` + `os.replace(...)` — atômico;
- ao fim, valida que `nomes_canais` é byte-a-byte idêntico em **todos** os arquivos.

Se um Ctrl+C interromper o processo: o NPZ original permanece intacto; basta rerodar.

**Tempo estimado:** ~152 NPZs × ~5.000 estados = ~760k estados. Cada estado gera um tensor
`(4, 3, 11)` via operações numpy puras — deve rodar em minutos na máquina local.

### 1A.3 — Validação visual (gate manual)

```powershell
py scripts/pontinhos/validar_canais_visualmente.py `
   --diretorio-npz dados/profundidade_minimax_11_v7_adaptativo `
   --diretorio-saida out/validacao_canais `
   --qtd-tracos 14 17 24 29 `
   --n-amostras 30 `
   --seed 42
```

Cada PNG (150 DPI) traz: matriz crua à esquerda, 11 boxnets `(4, 3)` à direita, paleta categórica fixa por canal, **borda destacada em caixas fechadas**, título canônico (`aresta_topo`, `caixa_fechada`, etc.) acima de cada boxnet.

O desenvolvedor deve revisar manualmente ao menos **30 PNGs** distribuídos nas faixas `t ∈ [12, 17]`, `[24, 28]` e `[29, 30]` antes de assinar o gate da Fase A.2 em `docs/historico_decisoes.md`.

### 1A.4 — Auditoria do diretório

A última célula do notebook de enriquecimento já roda a auditoria automática. Para inspecionar manualmente:

```python
import numpy as np, glob, os
from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import NOMES_CANAIS

esperado = np.array(NOMES_CANAIS, dtype='U32')
for arq in sorted(glob.glob('dados/profundidade_minimax_11_v7_adaptativo/dataset_pequeno_*.npz')):
    d = np.load(arq)
    assert 'canais' in d.files
    assert d['canais'].dtype == np.int8 and d['canais'].shape[1:] == (4, 3, 11)
    assert np.array_equal(d['nomes_canais'], esperado)
print('OK')
```

### 1A.5 — Testes unitários relevantes

```bash
py -m pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v
```

Cobre: domínio binário, exclusão mútua canal 4 vs 5–10, coerência sob simetrias, casos canônicos (vazio, caixa fechada, double-cross, loop 4 caixas, half-open chain).

---

## 1. Como rodar a geração de dados

O script principal para gerar os dados de treinamento é o `gerador.py`. Ele utiliza o algoritmo Minimax com Poda Alpha-Beta para criar os cenários e calcular a jogada perfeita.

Para iniciar a geração, execute:

```bash
# Recomendado para o tabuleiro pequeno (Q-values + soft targets)
python -m gerador_dados.jogo_pontinhos.gerador_pontinhos --tamanho pequeno --total 200000 --profundidade 6
```

**Parâmetros disponíveis:**
- `--tamanho`: O tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--total`: A quantidade total de estados/jogadas que você quer gerar.
- `--profundidade` *(Opcional)*: A profundidade do Minimax (padrão: `7`). Use `6` para o `pequeno` se quiser equilíbrio velocidade/qualidade; `5` só se realmente precisar acelerar (qualidade do "professor" cai).
- `--retomar` *(Opcional)*: Continua de onde parou caso tenha interrompido com `Ctrl+C`. Os lotes já salvos não são regerados; o checkpoint guarda `total_gerado` e `ultimo_lote`.

**Quanto gerar (tabuleiro `pequeno`, 31 classes):**
- **100k** — mínimo viável (~2h). Já se beneficia bastante dos soft targets.
- **200k** — *sweet spot* recomendado (~3–4h). Com 4× simetria no notebook = 800k efetivos.
- **>300k** — retorno decrescente; prefira aumentar `--profundidade` para `7`.

**Interromper e retomar:** pressione `Ctrl+C` a qualquer momento. O script termina os cálculos em andamento, salva o lote parcial, atualiza o checkpoint e sai limpo. Para continuar:

```bash
python -m gerador_dados.jogo_pontinhos.gerador_pontinhos --tamanho pequeno --total 200000 --profundidade 6 --retomar
```

---

## 2. Onde os dados serão salvos

Tudo será salvo automaticamente na pasta **`dados/`** (na raiz do backend), dividido em lotes de 5.000 registros:

- **`dataset_pequeno_0001.npz`**: Arquivos compactados NumPy. Cada um contém:
  - `estados` — matrizes do tabuleiro `(N, 9, 7)` em `int8`.
  - `rotulos` — string da jogada ótima (argmax) para cada estado, ex.: `H_2_3`. Mantido para métricas e compatibilidade.
  - `scores` — vetor de Q-values do Minimax `(N, 31)` em `float32`. Slots indisponíveis (jogadas já preenchidas) marcados com `-1e9` e devem ser mascarados antes do softmax. **Este é o alvo principal do treino com `KLDivergence`.**
  - `indices` — índice global do registro.
  - `labels_canonicos` — vetor `(31,)` de strings com a ordem canônica dos slots, mapeando posição ↔ rótulo.
  - `generation_mode` — estratégia de amostragem por registro `(N,)` em `int8`: 0=uniform, 1=sim_l1, 2=sim_l2, 3=sim_l3.
  - `minimax_depth` — profundidade do Minimax usada no scoring `(1,)` em `int32`, ex.: `[8]`. Permite auditar lotes antigos sem depender de metadados externos.
- **`checkpoint_pequeno.json`**: Arquivo de controle que salva o status da geração.

### Lotes legados sem `minimax_depth`

Lotes gerados antes do campo existir no notebook precisam ser retroativamente
atualizados. Use o script abaixo (requer numpy; rode em Colab ou Databricks):

```bash
# Lotes na raiz de dados/ → depth=7
python gerador_dados/jogo_pontinhos/patch_minimax_depth_pontinhos.py dados/ 7

# Lotes em dados/profundidade_minimax_6/ → depth=6
python gerador_dados/jogo_pontinhos/patch_minimax_depth_pontinhos.py dados/profundidade_minimax_6/ 6

# Lotes novos do Databricks (depth=8) — rodar assim que chegarem
python gerador_dados/jogo_pontinhos/patch_minimax_depth_pontinhos.py dados/profundidade_minimax_8/ 8
```

O script é idempotente: arquivos que já têm `minimax_depth` são ignorados.

> ⚠️ **Atenção sobre dados antigos:** datasets gerados antes da introdução do campo `scores` **não são compatíveis** com o novo notebook de treino (que usa soft targets). Apague o conteúdo de `dados/` antes de rodar a nova geração:
>
> ```bash
> rm dados/dataset_pequeno_*.npz dados/checkpoint_pequeno.json
> ```

---

## 3. Como avaliar se tudo está rodando bem

O script emite um log no formato JSON a cada 1.000 registros gerados. No terminal, você verá:

```json
{"registros_gerados": 1000, "total_alvo": 50000, "porcentagem": 2.0, "tempo_decorrido_s": 15.4, "estimativa_restante_s": 754.6}
```

Isso informa:
- A quantidade gerada.
- A porcentagem de conclusão.
- A estimativa de tempo restante (`estimativa_restante_s`), útil para calibrar a `--profundidade`.

---

## 4. Como enxergar os dados no formato PNG

Para extrair e visualizar as matrizes como imagens PNG, você pode executar o seguinte comando diretamente no terminal:

```bash
# Gera imagens PNG de todas as matrizes de um arquivo .npz específico
python -c "from gerador_dados.jogo_pontinhos.visualizador_pontinhos import lote_para_png; lote_para_png('dados/dataset_pequeno_0001.npz', 'visualizacoes/lote_01/')"
```

Isso criará a pasta `visualizacoes/lote_01/` com imagens PNG onde:
- **Cinza**: Traços (arestas preenchidas, sem distinção de jogador).
- **Azul**: Caixas fechadas pela IA (Jogador 1).
- **Vermelho**: Caixas fechadas pelo Humano (Jogador 2).
- **Preto/Branco**: Pontos da grade e espaços vazios.

---

## 5. Como testar o modelo treinado

Após treinar a CNN e exportar o modelo `.tflite`, existem duas formas de testar: o **Simulador Interativo** (Pygame) e o **Avaliador Automático** (partidas em lote contra o Minimax).

> ⚠️ **Compatibilidade de versão TFLite:** Se o modelo foi exportado no Google Colab (TensorFlow 2.16+), você **deve** usar o ambiente `.venv_tf` (TF 2.21) para carregá-lo. O ambiente `.venv_gpu` (TF 2.10) não reconhece opcodes mais recentes do TFLite e gerará o erro `Didn't find op for builtin opcode 'FULLY_CONNECTED' version '12'`.

### 5.1 Simulador Interativo (Pygame)

Jogue partidas ao vivo contra a IA treinada. É útil para avaliar qualitativamente o comportamento da CNN.

#### Jogar contra o Minimax (sem modelo treinado)
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.jogo_pontinhos.simulador_tatico_pontinhos --tamanho pequeno --modo minimax
```

#### Jogar contra a CNN treinada
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.jogo_pontinhos.simulador_tatico_pontinhos --tamanho pequeno --modo cnn --modelo modelos/pontinhos_pequeno_profundidade_8.tflite
```

**Parâmetros disponíveis:**
- `--tamanho`: O tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--modo`: O agente adversário (`cnn` ou `minimax`).
- `--profundidade`: Profundidade do Minimax (só para `--modo minimax`).
- `--modelo`: Caminho para o arquivo `.tflite` (obrigatório para `--modo cnn`).

**Controles:**
- **Mouse**: Clique nos espaços entre os pontos na tela para fazer um traço. A IA jogará em seguida.
- Tecla **`R`**: Reinicia a partida atual.
- Tecla **`Q`**: Sai do jogo.

O simulador imprime o **tempo de decisão da IA** em milissegundos no terminal a cada jogada.

### 5.2 Avaliador Automático (CNN vs Minimax em lote)

Joga centenas de partidas automatizadas entre a CNN e o Minimax em diferentes profundidades, medindo taxa de vitória, empates e velocidade de decisão. Utiliza **todos os núcleos do processador** via `ProcessPoolExecutor` para acelerar a avaliação.

#### Via linha de comando (recomendado)
```powershell
.venv_tf\Scripts\python.exe -m gerador_dados.jogo_pontinhos.avaliador_partidas_pontinhos --modelo modelos/pontinhos_pequeno_profundidade_7.tflite --tamanho pequeno --partidas 200 --profundidades 1 3 5 6
```

**Parâmetros disponíveis:**
- `--modelo`: Caminho para o arquivo `.tflite` (obrigatório).
- `--tamanho`: Tamanho do tabuleiro (`pequeno`, `medio` ou `grande`).
- `--partidas`: Total de partidas por profundidade (padrão: `200`). Metade com CNN como primeiro jogador, metade como segundo.
- `--profundidades`: Lista de profundidades do Minimax para testar (padrão: `1 3 5 6`).

#### Via Notebook (alternativa)

O notebook `notebooks/jogo_pontinhos/Avaliacao_CNN_vs_Minimax.ipynb` executa a mesma avaliação. Certifique-se de selecionar o kernel **`.venv_tf`** antes de executar.

**Estimativa de tempo (Ryzen 5700X, 200 partidas por profundidade, multi-core):**

| Profundidade | Tempo aproximado |
|:---:|---|
| 1 | < 10 segundos |
| 3 | ~30 segundos |
| 5 | ~5 minutos |
| 6 | ~20–30 minutos |

**Exemplo de saída:**
```
========================================================================
AVALIAÇÃO POR PARTIDAS REAIS — CNN vs Minimax
========================================================================

  Adversário: Minimax(p=5)  (200 partidas)
  Vitórias CNN           180  ( 90.0%)
  Empates                 10  (  5.0%)
  Derrotas CNN            10  (  5.0%)
  Tempo médio CNN:  0.15 ms/jogada
  Tempo médio Minimax(p=5): 245.3 ms/jogada
  CNN é 1635× mais rápida
========================================================================
```
