# Histórico de Decisões — Arena Sagaz Backend

Registro cronológico de decisões arquiteturais e mudanças de rota relevantes.
Entradas mais recentes no topo. Cada entrada deve responder: **o quê, por quê,
o que foi descartado e por quê**.

---

## 2026-04-24 — Refatoração estrutural do repositório (branch `002-refatoracao-estrutural`)

### Contexto
O repositório acumulou nomes genéricos em `gerador_dados/` (`tabuleiro.py`,
`minimax.py`, `gerador.py`, etc.) e em `docs/` (arquivos game-specific na raiz
sem subfolder), criados antes de Arena Sagaz ser tratado explicitamente como um
**hub de jogos**. Com a regra de nomenclatura hub-de-jogos estabelecida
(2026-04-24), ficou claro que um segundo jogo criaria colisões imediatas de
nomes: `gerador_dados/tabuleiro.py` poderia ser do Pontinhos ou da Velha.

### Decisão
Refatoração em cinco fases executadas na branch `002-refatoracao-estrutural`:

1. **Fase 0 — Limpeza:** deletar arquivos gerados pelo SpecKit que nunca foram
   validados (`api/banco/`, `api/auth/`, etc.), reescrever `api/` de forma
   minimalista, limpar `requirements.txt`.

2. **Fase 1 — docs/:** criar `docs/tcc/` e `docs/jogo_pontinhos/`, mover 11
   documentos game-specific para `docs/jogo_pontinhos/` e
   `argumentacao_cnn_vs_minimax.md` para `docs/tcc/`.

3. **Fase 2 — gerador_dados/:** criar `gerador_dados/jogo_pontinhos/`, renomear
   os 8 arquivos game-specific com sufixo `_pontinhos` (usando `git mv` para
   preservar histórico), atualizar todos os imports, mover testes para
   `tests/unitarios/jogo_pontinhos/`. `nucleo_log.py` deletado — imports
   redirecionados para `api.nucleo.log`, que já tinha implementação idêntica.

4. **Fase 3 — notebooks/:** mover 6 notebooks para `notebooks/jogo_pontinhos/`,
   atualizar paths em `Avaliacao_CNN_vs_Minimax.ipynb` (único que roda
   ativamente).

5. **Fase 5 — Configurações e documentação:** verificar `pytest.ini`,
   `Dockerfile`; atualizar `CLAUDE.md` com novos paths do contrato e do teste CI;
   registrar refatoração no histórico.

### Descartado
- **Renomear arquivo por arquivo durante outras tarefas (caso a caso):** gerava
  inconsistência incremental. Preferiu-se sessão dedicada, clean-slate, com
  checklist explícito.
- **Manter nomes genéricos e usar só pastas para separar:** insuficiente quando
  um arquivo legado fica na raiz compartilhada (`gerador_dados/tabuleiro.py` —
  de qual jogo?).

### Estado final
- `gerador_dados/jogo_pontinhos/` — 8 arquivos com sufixo `_pontinhos`
- `notebooks/jogo_pontinhos/` — 6 notebooks
- `docs/jogo_pontinhos/` — 11 docs game-specific
- `docs/tcc/` — 1 doc de argumentação acadêmica
- `tests/unitarios/jogo_pontinhos/` — 4 arquivos de teste
- 31/31 testes passando

---

## 2026-04-24 — Autenticação via Firebase Auth + limpeza do api/ gerado por SpecKit

### Contexto
O SpecKit gerou automaticamente toda uma camada de API (`api/banco/`, `api/auth/`,
`api/partidas/`, `api/ranking/`, `api/trofeus/`, `api/usuarios/`) com SQLAlchemy,
Alembic migrations, JWT e hashing de senha. O usuário não reconheceu nem validou
esse código — foi gerado sem decisões explícitas sobre banco de dados, modelo de
dados ou fluxo de autenticação.

Além disso, o usuário definiu que: (a) o cadastro/login é **opcional** — o app
funciona offline sem conta; (b) quando houver conta, suportará Google e outros
providers OAuth além de email/senha.

### Decisão
1. **Deletar integralmente** `api/banco/`, `api/auth/`, `api/partidas/`,
   `api/ranking/`, `api/trofeus/`, `api/usuarios/` e `alembic.ini`. Nada
   disso foi validado e criar-se-á do zero no momento oportuno (após o primeiro
   jogo rodar no frontend).

2. **Autenticação: Firebase Auth.** Elimina a necessidade de implementar
   hashing de senha, JWT, refresh tokens e OAuth flows no backend. O backend
   valida tokens Firebase (SDK `firebase-admin`) em vez de emiti-los. Login
   social (Google, Apple etc.) sai de graça pelo Firebase console.
   Dependência: `firebase-admin` — adicionada ao `requirements.txt` apenas
   quando a feature for implementada.

3. **`api/` minimalista por enquanto:**
   - `api/main.py` — FastAPI app + middleware de log
   - `api/configuracao.py` — só `AMBIENTE`
   - `api/nucleo/log.py` — logger JSON estruturado
   - `api/nucleo/excecoes.py` — exceções de negócio reutilizáveis
   - `api/nucleo/rotas.py` — `GET /v1/health` sem dependência de banco

### Descartado
- **Auth própria (JWT + bcrypt):** mais controle, mas exige implementar
  hashing, refresh tokens e cada provider OAuth manualmente. Custo alto
  para um app onde o login é opcional.
- **Manter o código do SpecKit "para depois refatorar":** decisão consciente
  de não carregar código não-validado no repositório. Mais fácil criar do zero
  quando as definições estiverem claras.

---

## 2026-04-24 — Contrato de codificação da CNN como fonte única da verdade

### Contexto
A normalização da matriz de entrada da CNN vinha sendo duplicada em vários
lugares: `simulador_tatico.py`, `avaliador_partidas.py`, notebooks de geração
(Databricks) e de treino (Colab), além do app Flutter. Cada fix de bug pedia
coordenar edições em 4–5 arquivos em dois repositórios, e o documento
`arena-sagaz-frontend/docs/ia_mappings.md` já havia divergido do código em
produção (bug #3 de 2026-04-23). Sem uma fonte única, a próxima regressão
silenciosa é questão de tempo.

### Decisão
Introduzir `gerador_dados/contrato_codificacao_pontinhos.json` como **fonte
única da verdade** da codificação da matriz de entrada da CNN do Pontinhos.
O JSON declara explicitamente os TRÊS contextos de uso (geração de dataset,
treinamento, partidas ao vivo), o domínio de valores permitido em cada um,
as regras de normalização aplicáveis com justificativa técnica, e os invariantes
do tensor final (`{0, 1}`, `float32`, `(1, H, W, 1)`).

Consumidores:
- Backend Python (`simulador_tatico.py`, `avaliador_partidas.py`) usa o helper
  `gerador_dados/contrato_codificacao_pontinhos.py`, que é uma fina camada
  sobre o JSON. Zero regra duplicada.
- Notebooks (Databricks + Colab) **não** importam scripts Python externos —
  carregam o JSON inline com `json.load()` conforme snippet documentado no
  próprio JSON (`snippet_de_uso_para_notebooks`).
- Frontend Flutter lê `assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`
  em runtime.

Sincronização:
- Duas cópias versionadas (backend + frontend) com hash SHA-256 idêntico.
- Teste CI (`tests/unitarios/test_contrato_codificacao_pontinhos.py`) **falha
  o merge** se divergirem.

CLAUDE.md (backend e frontend) atualizado para OBRIGAR leitura do JSON antes
de qualquer mudança em encoding, pipeline de geração/treino, lógica de
inferência ou normalização.

### Alternativas descartadas
- **Módulo Python `encoding.py` compartilhado**: descartado porque obrigaria
  enviar um arquivo Python extra ao Databricks e ao Colab a cada iteração, e
  o usuário explicitamente proibiu notebooks chamarem scripts externos.
- **Mascaramento da terminologia no JSON** (ex.: "classe A/B" no lugar de
  "jogador 1/2"): descartado porque o público-alvo do JSON são LLMs editando
  código; mascaramento prejudicou a compreensão num primeiro protótipo.
- **Gerar os mapeamentos de labels também a partir do JSON**: fora de escopo
  desta rodada — os `mapeamento_*.json` continuam sendo gerados por
  `todos_labels_canonicos()` no backend. Podem ser unificados em rodada futura
  se vier necessidade.

### Regra de nomenclatura associada
Mesmo dia ficou registrada a regra de nomenclatura hub-de-jogos: arquivos
game-specific devem carregar o nome do jogo OU estar dentro de pasta do jogo.
Isso motivou mover `assets/ia_mappings/` para
`assets/jogos/pontinhos/ia_mappings/` no frontend, alinhando com a estrutura
declarada no PRD §5.1 (`lib/modulos/jogos/pontinhos/`).

---

## 2026-04-23 — Análise do modelo V3 auto-play e 3 bugs corrigidos

### Contexto
Dataset V3 (300k amostras auto-play, gerado no Databricks em 4h) + re-treino
completo (BoxNet v3 auto-play) entregaram métricas estáticas **melhores** que
o modelo p=6 aleatório (Top-1 42.7% vs ~35%, gap treino/val +0.23 pp, zero
overfitting), mas o avaliador de partidas reais reportou **regressão massiva**:
apenas 57% de vitória contra MM(p=1), antes 96%. Três bugs identificados na
inspeção.

### Bug #1 — Inferência nunca normalizou caixas fechadas com `-1`
`gerador_dados/avaliador_partidas.py` e `gerador_dados/simulador/simulador_tatico.py`
normalizavam apenas os **traços** (1/-1 → 1) mas deixavam as caixas fechadas
com o valor do jogador (1 ou -1). No dataset de treino, caixas fechadas são
SEMPRE 1 (confirmado em `dados/dataset_pequeno_0002.npz`: interior unique = [0, 1]).
Consequência: sempre que o adversário fechava uma caixa, a CNN recebia `-1`
em um slot onde nunca viu esse valor no treino.

Pior no avaliador: metade das partidas tem a CNN como "agente 2" →
`_VALOR_MATRIZ[2] = -1`, então as **próprias** marcações da CNN (traços e
caixas) saem como `-1`. A CNN literalmente não reconhecia o próprio tabuleiro
nessas metades. Isso explica o padrão invertido dos resultados: contra MM(p=1)
caiu de 96% para 57%, mas contra MM(p=6) subiu de 1.5% para 7.5% — o auto-play
de fato ensinou táticas de endgame, mas ficava sabotado pela má-inferência.

### Bug #2 — Worker Spark do V3 com `depth = 7` hardcoded
No `notebooks/Otimizacao_Topologia_Rede_V3.ipynb` cell 5, `process_batch_v3`
tinha `rows, cols, depth = 4, 3, 7` hardcoded dentro da função serializada aos
executors. O outer cell definia `DEPTH = 8` mas isso só valia no fallback
local. Resultado: os 4h de Databricks geraram o dataset **em depth=7**,
apesar do artefato se chamar `pontinhos_pequeno_profundidade_8.tflite`. A
hipótese "depth-8 + auto-play rompe a regressão do depth-7 aleatório" **não
foi testada** — testamos depth-7 + auto-play.

### Bug #3 — Contrato `ia_mappings.md` do frontend divergia do treino
O documento `arena-sagaz-frontend/docs/ia_mappings.md` declarava que `-1`
representa "caixa fechada pelo Jogador 2 (Humano)" na matriz enviada à CNN.
Esse contrato **conflita** com o encoding real do treino (caixas = 0 ou 1,
nunca -1). Se um cliente Flutter obedecesse ao contrato à risca, reproduziria
exatamente o bug #1.

### Decisão e Resolução
1. **Corrigido Bug #1** em `avaliador_partidas.py:94-104` e
   `simulador/simulador_tatico.py:50-58` — agora ambos aplicam normalização
   unificada: `mat == 8 → 0`, `mat == -1 → 1`, `mat == 9 → 1`.
2. **Corrigido Bug #2** em `Otimizacao_Topologia_Rede_V3.ipynb`: cell 5 virou
   `make_worker(depth, rows, cols)` (factory pattern) e cell 6 instancia o
   worker com `make_worker(DEPTH, ROWS, COLS)` antes de passar ao
   `mapInPandas`. Garante que o valor declarado no driver é o efetivamente
   usado.
3. **Bug #3** a ser corrigido no repositório do frontend (próxima rodada) —
   o documento `ia_mappings.md` precisa ser atualizado para refletir o
   encoding real do treino.
4. **Métricas do treino V3** **validadas como boas** (Top-1 42.7%, OMA global
   93.2%, gap 0.23 pp). A regressão aparente em win-rate era artefato do bug
   #1. Re-avaliação pós-fix necessária para confirmar que win-rate sobe.
5. Documento de métricas `docs/metricas_e_conceitos.md` reescrito com TODAS
   as métricas (padrão Keras + custom) explicadas.

### Próximos passos imediatos
- Re-rodar `Avaliacao_CNN_vs_Minimax.ipynb` no `.venv_tf` com o `.tflite`
  atual e os fixes aplicados. Expectativa: win-rate vs MM(p=1) ≥ 85%.
- Se expectativa bater, regenerar dataset em **depth=8 real** no Databricks
  (mesmo 300k + mesmas estratégias, só com bug #2 corrigido) para testar a
  hipótese original depth-8 + auto-play.
- Definir padronização central do encoding da matriz — fonte única de verdade
  entre backend, frontend, gerador, avaliador e simulador (discussão aberta).

---

## 2026-04-23 — A Grande Revelação: O Bug da Regra Invertida no Minimax (cl == 0)

### Contexto
Após gerar amostras com Minimax profundidade 7 e treinar a CNN, observamos uma regressão brutal na força de jogo da CNN: ela estacionava em ~36% de precisão (Top-1) e performava pior do que modelos treinados com profundidade 6. 
Inicialmente, atribuímos essa falha ao uso de tabuleiros aleatórios ("topologias irreais") e desenhamos a geração de Autoplay (V3) para mitigar o problema.

### A Descoberta da Verdadeira Causa Raiz
Ao desenvolver e utilizar um novo Visualizador de Matrizes ASCII (Markdown), um teste manual revelou que o algoritmo estava avaliando a captura de caixas como uma jogada péssima (score 0) e sacrifícios forçados absurdos como jogadas excelentes (score +3).

Uma auditoria imediata no código apontou um **bug gravíssimo na função `compute_all_scores`** dentro dos Notebooks Spark (V2 e V3). 
Na tradução do backend `minimax.py` para a otimização em bits, o trecho de repasse de turno:
```python
child = deep_evaluate(..., cl == 0, ...)
```
Foi escrito com `==` em vez de `>`. Isso causou a **inversão total das regras do jogo na rotulação dos dados**:
- Se a IA fechasse uma caixa (`cl = 1`), `cl == 0` dava `False` (a Engine achava que o turno passava para o adversário, anulando a jogada extra).
- Se a IA NÃO fechasse caixa (`cl = 0`), `cl == 0` dava `True` (a Engine achava que a IA continuava jogando e ganhando turnos extras no vazio).

### Impacto
- **Toda a rotulação (scores) de profundidade 7 gerada até o dia 23 de Abril estava invertida/enviesada.** 
- O plateau da BoxNet em ~36% (Tentativas 5 e 6) era literalmente a CNN confusa tentando aprender um jogo de regras ao contrário.
- A "regressão" da profundidade 7 vs 6 ocorreu porque quanto mais profundo o Minimax pensava nas regras erradas, mais ele escolhia lixo topológico.

### Decisão e Resolução
1. O bug foi instantaneamente corrigido (`cl > 0`).
2. A hipótese da topologia aleatória (que nos levou à criação do Dataset V3 com AutoPlay) foi descartada como vilã exclusiva, mas o pipeline V3 foi **MANTIDO E VALIDADO** porque ele gera partidas reais, o que provou ser de valor inestimável para generalização da rede.
3. Todo o dataset corrompido foi expurgado, e iniciaremos o Treinamento Real 1.0 utilizando os Q-Values corretos do V3.

---

## 2026-04-21 — Documento de argumentação CNN vs Minimax criado

**Decisão.** Criar `docs/tcc/argumentacao_cnn_vs_minimax.md` com todos os
argumentos para justificar a CNN em vez do Minimax puro.

**Motivação.** Banca do TCC certamente questionará a escolha. O documento
cobre: velocidade (20s vs 3ms, dados medidos no Ryzen 5700X), latência
variável do Minimax, portabilidade TFLite, dificuldade ajustável por
temperatura, analogia com AlphaGo/AlphaZero (destilação de política),
limitações honestas e narrativa unificada pronta para apresentação.

**Conteúdo:** 8 seções com argumentos curtos (30s) e longos (3 min) para
a banca, tabela comparativa final e respostas preparadas para questionamentos.

---

## 2026-04-21 — Avaliador por partidas reais implementado

**Decisão.** Criar `gerador_dados/avaliador_partidas.py` e Cell 9 no notebook
para avaliar a CNN jogando partidas completas contra o Minimax em diferentes
profundidades (1, 3, 5, 6). 200 partidas por profundidade (100 CNN primeiro,
100 CNN segundo).

**Motivação.** Taxa de vitória é autoexplicativa para a banca — elimina a
necessidade de defender OMA como "nova métrica". "A CNN vence o Minimax
profundidade 5 em 65% das partidas sendo 100× mais rápida" é mais poderoso
do que qualquer métrica estática.

**Expectativas:** CNN deve vencer ~85–95% vs profundidade 1, ~70–80% vs
profundidade 3, ~60–70% vs profundidade 5, ~45–55% vs profundidade 6.

**Impacto:**
- `gerador_dados/avaliador_partidas.py`: script standalone + funções importáveis
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb`: Cell 9 adicionada (roda após TFLite)
- `docs/metricas_e_conceitos.md`: seção 9 adicionada com narrativa para banca

---

## 2026-04-21 — Documento de métricas e conceitos criado

**Decisão.** Criar `docs/metricas_e_conceitos.md` com explicação completa de:
Top-1/Top-3/Top-5, OMA (origem, cálculo, literatura relacionada), Temperatura
nos soft targets e sample_weight — tudo no contexto do Jogo dos Pontinhos,
com argumentação pronta para a banca do TCC.

**Motivação.** O usuário não conhecia essas métricas e precisava de material de
estudo para a defesa. A origem da OMA como métrica proposta pelo projeto (não
padronizada) é explicada com honestidade e comparada com conceitos similares
da literatura (AlphaGo, KataGo, imitation learning, VQA).

---

## 2026-04-21 — Regressão da Rodada 3 e descoberta do OMA=99%

**Contexto.** BoxNet v3 rodada 3 (300k, T=0.5, sample_weight) regrediu em todas
as métricas vs rodada 2 (210k, T=1.0, sem sample_weight). Top-1 caiu 2.4pp,
top-3 caiu 3.2pp apesar de 50% mais dados. Diagnóstico detalhado abaixo.

**Decisão.** Reverter T=1.0 e remover sample_weight para a rodada 4. Manter
300k dados e max_epochs=120. Adotar **Optimal Move Accuracy (OMA)** como
métrica principal do projeto.

**Por que T=0.5 não ajudou:**
A temperatura só diferencia moves com scores diferentes. Empates exatos do
Minimax (frequentes na abertura) distribuem probabilidade uniforme entre
equivalentes independente de T. A mudança foi ineficaz para o problema real.

**Por que sample_weight prejudicou:**
States de abertura têm ~6.8 equivalentes → peso médio 1/6.8 ≈ 0.15. O modelo
treinou com 85% menos gradiente nas posições mais comuns, mas foi avaliado com
peso normal. Top-3 de abertura caiu para 40.6% (era provalmente ~60%+ antes).

**Descoberta central — OMA=99%:**
O modelo escolhe uma jogada Minimax-ótima 99% das vezes. O top-1 de 33% mede
o "acerto do desempate canônico", não qualidade estratégica. H_0_1 acumula
support=8.351 (20% do test set) porque é o primeiro label na ordenação
canônica e ganha o argmax de todos os states com empate — mas o modelo escolhe
H_0_3 ou H_2_1 (igualmente ótimas), contando como "erro" de top-1.

**Nova métrica oficial:** OMA = percentual de predições dentro do conjunto
Minimax-ótimo. Implementada no Cell 7 do notebook.

**Alternativas descartadas:**
- Manter T=0.5 e sample_weight: causa provada da regressão.
- Hybrid loss (KLD + 0.1×CE): adicionaria complexidade; OMA já é 99%, teto real.
- Aumentar profundidade Minimax para 7: melhora qualidade mas 50% mais lento;
  postergado para após confirmar que arquitetura é o gargalo.

**Impacto:**
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 3: T=1.0 restaurado.
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 6: sample_weight removido.
- `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 4: tabela com rodada 3
  (resultados reais) e rodada 4 (planejada); nota sobre OMA como métrica oficial.
- `docs/jogo_pontinhos/historico_tentativas_treinamento.md`: rodada 3 completa + rodada 4 planejada.

---

## 2026-04-21 — Documento detalhado de tentativas de treinamento

**Decisão.** Criar `docs/jogo_pontinhos/historico_tentativas_treinamento.md` com registro
narrativo de cada experimento: CNN ingênua → MLP → BoxNet v1 → v2 → v3 rodadas
1, 2 e 3 (planejada). Para cada tentativa: o que foi feito, por que, o que não
funcionou, o que aprendemos e o próximo passo.

**Motivação.** A tabela compacta do notebook (Cell 4) não tem espaço para
argumentação acadêmica. O documento separado serve tanto para retrospectiva
interna quanto para a banca do TCC questionar as decisões de modelo.

**Tabela no Cell 4** do notebook também atualizada: adicionadas colunas top-3,
top-5 e dados, e preenchidos os resultados reais das rodadas 1 e 2 do v3.

---

## 2026-04-21 — Novas métricas diagnósticas: fase do jogo e Optimal Move Accuracy

**Contexto.** BoxNet v3 treinado em 210k amostras atingiu top-1 ≈ 35% com gap
treino/val de -0.19pp (zero overfitting). O teto do top-1 é estrutural: estados
de abertura têm múltiplas jogadas Minimax-equivalentes; o argmax do soft target
escolhe uma arbitrariamente, e o modelo pode escolher outra igualmente válida —
deprimindo o top-1 sem indicar erro estratégico.

**Decisão.** Adicionar duas métricas ao Cell 7 do notebook:

1. **Accuracy por fase do jogo** — divide o test set em Abertura (0–10 traços),
   Meio-jogo (11–20) e Final (21–31). Espera-se que top-1 cresça com o número
   de traços jogados, pois states finais têm menos equivalências.

2. **Optimal Move Accuracy** — verifica se a predição top-1 pertence ao conjunto
   Minimax-ótimo (`score == max_score`). Métrica mais justa para este domínio.

**Alternativas consideradas.**
- Temperatura T=0.5 (distribuições mais sharp → melhor top-1): postergado para
  após ver os resultados das novas métricas com 300k dados.
- `sample_weight` pelo inverso de jogadas equivalentes: postergado pelo mesmo
  motivo.

**Impacto.** `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb` Cell 7 atualizado.

---

## 2026-04-20 — Adoção de soft targets (Q-values do Minimax) no dataset

**Contexto.** A primeira iteração do treino da CNN (BoxNet v2, 4×3) plateauou em
val_top1 ≈ 36% mesmo com gap treino/val controlado em ~9.6pp. As métricas
val_top3 ≈ 70% e val_top5 ≈ 83% indicam que o modelo aprende a *região* certa,
mas o argmax do Minimax descarta jogadas equivalentes (várias com mesmo score),
criando ambiguidade artificial no rótulo.

**Decisão.** Mudar o formato do dataset para gravar o vetor completo de
Q-values (`scores`, shape `(N, 31)` para o tabuleiro pequeno) ao lado do
argmax (`rotulos`). Treino futuro usará `KLDivergence` sobre o softmax
mascarado dos scores, no estilo "policy distillation" do AlphaZero.

**Alternativas consideradas.**
- *Apenas adicionar `class_weight` ao fit:* corrigia desequilíbrio mas não o
  problema de ambiguidade; ganho estimado +1–2pp vs. +15–25pp esperado da
  abordagem escolhida.
- *Aumentar profundidade do Minimax mantendo argmax:* não resolve a
  ambiguidade entre jogadas com score idêntico.

**Impacto.**
- `gerador_dados/minimax.py`: nova função `melhor_jogada_com_scores()`
  reaproveitando o mesmo loop (custo computacional zero).
- `gerador_dados/tabuleiro.py`: helper `todos_labels_canonicos()` para
  indexação determinística.
- `gerador_dados/gerador.py`: `.npz` agora inclui `scores` e
  `labels_canonicos`.
- **Datasets antigos (formato sem `scores`) ficaram incompatíveis e devem ser
  apagados.** Os 50k já gerados foram descartados.

**Sentinela usada para slots indisponíveis:** `-1e9` em `float32`. O notebook
deve mascarar antes do softmax.

---

## 2026-04-20 — Alvo de geração: 200k–300k registros, profundidade 6

**Contexto.** Com a paralelização via `ProcessPoolExecutor` (Gemini ajustou
para usar `cpu_count - 2` workers) e profundidade 5, o gerador produz ~50k/h.
O usuário relatou capacidade prática de gerar centenas de milhares de
registros ao longo de dias.

**Decisão.**
- Alvo padrão recomendado no guia: **200k** (sweet spot — diminishing returns
  acima disso para o pequeno).
- Usuário escolheu rodar **300k** dado o orçamento de tempo disponível.
- Profundidade recomendada: **6** (equilíbrio qualidade/velocidade do
  "professor"). 5 só se realmente precisar acelerar.

**Alternativas consideradas.**
- *Manter 50k:* insuficiente para 31 classes com soft targets diluídos.
- *Gerar 500k+:* custo-benefício ruim — preferível investir tempo em
  profundidade maior do que em volume.

**Garantia operacional.** O parâmetro `--total` do CLI sobrescreve o checkpoint
a cada execução. É seguro começar com `--total 300000` e mais tarde rodar
`--total 200000 --retomar` — o loop simplesmente para quando atinge o novo
alvo, sem apagar lotes já gerados.

---

## 2026-04-20 — Em aberto: desbalanceamento centro vs. bordas

**Contexto.** O `classification_report` da BoxNet v2 mostrou F1 de centro
(`H_2_1` ≈ 0.43, support 282) muito superior ao das bordas (`H_0_3` ≈ 0.17,
support 167). Causa provável dupla: (a) frequência menor das bordas no
dataset; (b) ambiguidade do argmax — bordas empatam em score com mais
frequência na abertura/midgame, e o sorteio entre empates produz rótulos
ruidosos.

**O que já mitiga indiretamente.**
- Simetria 4× (multiplica bordas também, mas não muda a proporção).
- **Soft targets / KLDivergence** (decisão acima) — ataca a causa (b)
  diretamente: a rede aprende "qualquer uma dessas três bordas serve" em vez
  de adivinhar a sorteada.

**O que NÃO foi feito (decisão deliberada de adiar).**
- `sample_weight` por inverso da frequência da classe do `argmax(scores)`.
  Não usamos `class_weight` porque a loss agora é `KLDivergence` sobre
  distribuição (não classe única).
- Amostragem viesada no `_gerar_estado_aleatorio` favorecendo estados onde a
  jogada ótima é de borda — descartado por complexidade e baixo retorno
  esperado.

**Critério de retomada.** Após o treino com o dataset novo (Q-values, 200–300k),
re-avaliar `classification_report` por classe. Se bordas continuarem com F1
< 0.25 enquanto centro > 0.40, adicionar `sample_weight` no `fit`. Se a
diferença encolher para < 10pp, considerar o problema resolvido.

---

## 2026-04-20 — Notebook atualizado: BoxNet v2 → v3 (KL Divergence)

**Arquivo:** `notebooks/Treinamento_CNN_Arena_Sagaz.ipynb`

**Células alteradas:**
- **Cell 2 (markdown):** atualizada para descrever carregamento de `scores`,
  permutações de simetria e soft targets.
- **Cell 3 (carregamento):** reescrita. Agora lê `scores` e `labels_canonicos`
  do `.npz`; usa `labels_canonicos` como ordem canônica de classes (em vez de
  `sorted(np.unique(y_str))` — as duas ordens diferem); pré-computa 3
  permutações de índice para augmentação; augmenta estado e vetor de scores
  juntos; aplica softmax mascarado com `T=1.0` para gerar soft targets `(N,31)`;
  mantém `y_*_idx = y_soft.argmax(axis=1)` para métricas de avaliação.
- **Cell 4 (markdown):** tabela de histórico atualizada com BoxNet v3.
- **Cell 5 (modelo):** loss trocada de
  `CategoricalCrossentropy(label_smoothing=0.05)` para `KLDivergence()`;
  nome `BoxNet_v3_ArenaSagaz`.
- **Cell 7 (avaliação):** coluna `kld_loss`; `classification_report` usa
  `y_test_idx` (argmax do soft target); gráfico rotulado como "KL Divergence".

**Compatibilidade:** exige dataset no novo formato (com `scores`). Arquivos
`.npz` sem esse campo lançam `ValueError` na leitura.

---

## 2026-04-20 — Documentação técnica para defesa do TCC

Criados/atualizados documentos de argumentação acadêmica:
- `docs/jogo_pontinhos/soft_targets_kl_divergence.md` — explicação completa de soft targets,
  KL Divergence vs Categorical Crossentropy, onde o argmax ainda existe, e
  resposta modelo para a banca.
- `docs/jogo_pontinhos/justificativa_50k_amostras.md` — atualizado para refletir a nova
  realidade: 200–300k registros, paralelização (1 semana → ~6h), soft targets,
  e Data Augmentation por simetria D₂. O documento antigo citava 300k como
  "fisicamente impossível" — estava desatualizado após a migração para
  `ProcessPoolExecutor`.

---

## 2026-04-20 — Diretriz: documentação viva obrigatória

**Decisão.** Toda mudança arquitetural, de formato de dados, de parâmetros
recomendados ou de rota técnica deve atualizar os `.md` relevantes na mesma
resposta. Diretriz codificada em `CLAUDE.md` para não depender da memória do
usuário.
