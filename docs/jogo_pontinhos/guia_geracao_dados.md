# Guia Completo: Geração de Dados e Simulador - Fase Zero

Com base na documentação e no código gerado para a **Fase Zero** do projeto Arena Sagaz, este é o guia passo a passo para iniciar a geração de dados, monitorar o progresso, visualizar as matrizes e testar o simulador tático.

Certifique-se de estar dentro da pasta `arena-sagaz-backend` e com seu ambiente virtual ativado.

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
local** com `multiprocessing`. A lógica é a mesma do PRD §4.1.3 (loop por
cota com `COMPLEMENTO_POR_CELULA`, dedup contra `hashes_iniciais`).

**Artefatos:**

- `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb` — notebook orquestrador.
- `notebooks/jogo_pontinhos/v5_local_engine.py` — engine importável pelos
  workers spawnados (precisa ser `.py`, não pode estar em célula Jupyter,
  porque `multiprocessing` no Windows usa modo `spawn`).

**Como rodar:**

1. **Pré-requisito**: NPZ legado V4 em `dados/profundidade_minmax_9/`
   (314.323 únicos esperados).
2. Abrir o notebook V5_Local em VS Code/Jupyter local. Editar `REPO_ROOT`
   na célula de parâmetros se a árvore do repositório não estiver no
   caminho default.
3. Executar todas as células sequencialmente. O loop principal:
   - Pré-popula `hashes_iniciais` com os 314.323 do legado.
   - Sorteia `(gen_mode, bucket)` ponderado por cota residual em
     `COMPLEMENTO_POR_CELULA`.
   - Pool de `cpu_count()-1` workers gera amostras com `gen_mode` e
     `target_tracos` forçados, retornando até 20 tentativas por task.
   - Main deduplica por `mat.tobytes()`, decrementa cota, grava NPZ a cada
     `TAMANHO_LOTE = 5.000` estados.
   - Para quando todas as cotas zeram (347.020 estados novos).
4. **Saída**: `dados/profundidade_minmax_9_v5_local/dataset_pequeno_*.npz`
   (mesmo schema do V5 Databricks).
5. Auditoria final compara cotas alvo vs preenchidas e confere
   distribuição combinada (legado + rodada) dentro de ±2pp por bucket.

**Quando preferir Databricks:** geração massiva em cluster pago dedicado
(maior paralelismo do que máquina única). Free serverless **não** é
recomendado.

### 1A.2 — Fase A.2 local: enriquecer NPZ com 11 canais

```bash
# Pré-requisito: módulo analisador disponível.
py -c "from gerador_dados.jogo_pontinhos.analisador_estrutural_pontinhos import extrair_canais, NOMES_CANAIS; print(len(NOMES_CANAIS))"
# Esperado: 11
```

Abra `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb` (Jupyter, Colab ou VSCode). Configure:

```python
DIR_NPZ = '/caminho/para/profundidade_9'   # diretório baixado da Fase A.1
PADRAO  = 'dataset_pequeno_*.npz'
FORCAR_REGRAVAR = False                    # True só se o algoritmo de canais mudar
```

Rode todas as células. O notebook:

- lê cada NPZ;
- chama `extrair_canais(estados[i])` para cada um dos 5.000 estados;
- adiciona `canais (5000, 4, 3, 11) int8` e `nomes_canais (11,) U32`;
- regrava via `np.savez_compressed(<path>.tmp, ...)` + `os.replace(<path>.tmp, <path>)` — atômico;
- ao fim, valida que `nomes_canais` é byte-a-byte idêntico em **todos** os arquivos.

Se um Ctrl+C interromper o processo: o original NPZ permanece intacto; basta rerodar.

### 1A.3 — Validação visual (gate manual)

```bash
py scripts/pontinhos/validar_canais_visualmente.py \
   --diretorio-npz /caminho/para/profundidade_9 \
   --diretorio-saida out/validacao_canais \
   --qtd-tracos 14 17 24 29 \
   --n-amostras 30 \
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
for arq in sorted(glob.glob('caminho/para/profundidade_9/dataset_pequeno_*.npz')):
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
