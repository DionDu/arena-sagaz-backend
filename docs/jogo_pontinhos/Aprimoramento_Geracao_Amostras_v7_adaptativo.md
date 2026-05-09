# Aprimoramento V7 — Acelerar a Fase 2 com Move Ordering por Principal Variation

> **Status:** PROPOSTA DOCUMENTADA, NÃO IMPLEMENTADA.
>
> Esta é uma otimização opcional do pipeline V7. O notebook
> `Geracao_Amostras_v7_adaptativo.ipynb` continua sendo a fonte da
> verdade do fluxo atual. Esta proposta só será materializada se a
> Fase 2 do V7 atual provar ser proibitivamente lenta em medição real.
>
> Documentos relacionados:
> - Pipeline atual: `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`
> - Histórico de decisões: `docs/historico_decisoes.md`
> - Guia operacional: `docs/jogo_pontinhos/guia_geracao_dados.md` §1C

---

## 1. Resumo executivo

A Fase 2 do pipeline V7 calcula a "melhor jogada" para cada estado único
do dataset usando Minimax(p=7). Atualmente, essa busca começa **do zero**
para cada estado — sem nenhuma informação prévia sobre quais jogadas são
mais promissoras.

Mas a Fase 1 já produziu, para cada estado, um vetor `score_jogada` com a
avaliação Minimax de **todas as jogadas legais** numa profundidade
adaptativa (p=1 a p=8 conforme a tensão estrutural τ). Esses scores
podem ser usados como **dica de ordenação de busca** na Fase 2,
acelerando a poda alpha-beta sem alterar a profundidade ou qualidade do
resultado.

**Ganho esperado:** redução de 30–50% no tempo da Fase 2 (sem mudar p=7).
Alternativamente, mantendo o orçamento de tempo atual, permite subir
para **p=8** com folga, ou para **p=9** com transposition table
adicional.

**Risco:** baixo. Mudança localizada em duas funções; não altera o
formato do NPZ; é trivial fazer A/B testing entre versões.

---

## 2. Fundamentação técnica

### 2.1 Recapitulação: como o Minimax com poda alpha-beta funciona

O Minimax explora a árvore de jogadas avaliando posições futuras. A
poda **alpha-beta** elimina ramos que comprovadamente não podem mudar
o resultado:

- **α** (alpha): melhor valor garantido para o jogador maximizador até agora.
- **β** (beta): melhor valor garantido para o minimizador até agora.
- Se um ramo prova que `β ≤ α`, o subramo é cortado (pruned) — não
  precisa explorá-lo.

A eficácia da poda depende **criticamente da ordem em que os lances
são testados**. Se o primeiro lance testado já é forte, α sobe rápido,
e ramos posteriores são cortados cedo. Se o primeiro lance testado é
fraco, α começa baixo e a poda é fraca.

### 2.2 O que a literatura chama de "Move Ordering"

Em motores de jogos modernos (xadrez, Go, etc.), o move ordering é
considerado **a otimização mais importante do alpha-beta** — pode
acelerar a busca em fatores de 5× a 100×. Heurísticas comuns:

| Heurística | Como funciona | Eficácia |
|---|---|---|
| **Capturas/fechamentos primeiro** | Lances que produzem ganho imediato | Boa (já implementada) |
| **MVV-LVA** (Most Valuable Victim - Least Valuable Attacker) | Em xadrez: capturas de peças valiosas com peças baratas primeiro | N/A aqui |
| **Killer moves** | Lances que causaram corte alpha-beta em outros ramos da mesma profundidade | Boa |
| **History heuristic** | Lances que historicamente foram bons em posições similares | Boa |
| **Principal Variation (PV) de busca prévia** | A ordem dada por uma busca rasa anterior | **Excelente** |

A última — Principal Variation — é a base do **iterative deepening**:
busca-se p=1, depois p=2 reusa a ordem do p=1, depois p=3 reusa a do
p=2, etc. Cada nível raso é "barato" e fornece ordering para o próximo.

### 2.3 A oportunidade no V7

O pipeline V7 já gera, na Fase 1, scores Minimax com profundidade
adaptativa (campo `score_jogada` no NPZ). **Esses scores são
exatamente uma "Principal Variation rasa" disponível de graça** para
cada estado do dataset.

Em vez de descartá-los na Fase 2 e refazer a busca p=7 do zero, podemos
usá-los como hint inicial de ordenação. O ganho é exatamente o ganho
clássico do iterative deepening.

### 2.4 Implementação atual (V7 sem otimização)

`gerador_dados/jogo_pontinhos/minimax_pontinhos.py`:

```python
def _scores_de_todas_jogadas(estado, profundidade):
    tracos = estado.tracos_disponiveis()
    scores = {}
    for traco in tracos:
        fechadas = estado.aplicar_traco(traco, 1)
        if fechadas > 0:
            valor = minimax(estado, profundidade - 1, -10001, 10001, True, fechadas, 0)
        else:
            valor = minimax(estado, profundidade - 1, -10001, 10001, False, 0, 0)
        estado.desfazer_traco(traco)
        scores[traco] = valor
    return scores
```

A função interna `minimax()` já tem ordenação heurística simples
(`tracos_bons` = lances que fecham caixa primeiro). Mas a função
externa `_scores_de_todas_jogadas` (chamada na raiz) **explora todos
os lances na ordem da lista `tracos_disponiveis()`** — sem prioridade.

---

## 3. Análise quantitativa

### 3.1 Custo exponencial do Minimax

Para fator de ramificação efetivo `b` após poda (típico para nosso jogo:
~8-12 no midgame), o custo do Minimax cresce como `b^p`:

| Profundidade p | Custo relativo a p=7 | Tempo estimado (1 estado) |
|---:|---:|---:|
| 4 | ~0,8% | ~10 ms |
| 5 | ~7% | ~80 ms |
| 6 | ~30% | ~300 ms |
| 7 | 100% | ~1 s |
| 8 | ~3-4× | ~3-4 s |
| 9 | ~10-15× | ~10-15 s |

(Os tempos absolutos são estimativas grosseiras; a calibração precisa
vem da medição real.)

**Implicação:** o trabalho de uma busca p=4 é apenas ~1% do trabalho
de uma busca p=7. Não há atalho para "pular" os primeiros 4 níveis.
Mas a INFORMAÇÃO produzida por p=4 (a ordem das jogadas) é o que
permite acelerar p=7.

### 3.2 Ganho típico por move ordering com PV

Move ordering com Principal Variation é uma técnica antiga e bem
estudada. Em xadrez, o ganho típico ao adicionar PV ordering ao alpha-
beta é da ordem de 30–60% — equivalente a poder ir 0,5 a 1 nível mais
fundo no mesmo orçamento.

Para o nosso caso (dots and boxes, p=7), a estimativa é:

| Cenário | Tempo estimado da Fase 2 | Profundidade efetiva |
|---|---|---|
| V7 atual (sem otimização) | T (baseline) | p=7 |
| V7 + move ordering | ~0,6 T (40% mais rápido) | p=7 |
| V7 + move ordering + p=8 | ~2 T (≈ p=7 sem otimização × 3 × 0,6) | p=8 |
| V7 + move ordering + p=9 | ~6 T | p=9 |
| V7 + move ordering + transposition table + p=9 | ~3-4 T | p=9 |

**T é o tempo da Fase 2 atual**, ainda não medido. As três decisões
possíveis ficam claras quando T for conhecido:

- **T pequeno (<2h)**: não precisa otimizar. Manter V7 atual.
- **T médio (2-6h)**: implementar move ordering simples; manter p=7.
- **T grande (6-12h)**: implementar move ordering; considerar p=8 ou
  notebook Databricks.
- **T proibitivo (>12h)**: implementar notebook separado, com move
  ordering + transposition table + paralelismo extra (Databricks).

### 3.3 Insight: o ganho é maior exatamente onde mais importa

Como a Fase 1 usou **profundidade adaptativa por τ**, a qualidade do
hint herdado escala automaticamente com a importância da posição:

| Estado do jogo | `depth_jogada` típica | Qualidade do hint p=7 | Custo p=7 sem ordering |
|---|---:|---|---|
| Abertura (t<10) | 1–2 | Hint quase inútil | Mas barato: árvore acaba antes de p=7 importar |
| Midgame (t=12–20) | 3–5 | Hint moderado | Custo médio; ganho moderado |
| Endgame (t>20) | 6–8 | **Hint excelente** | **Caro**; ganho alto |

A correlação é direta: estados onde a Fase 2 é cara são exatamente os
estados onde a Fase 1 calculou hints de alta qualidade. **A otimização
acelera onde mais importa.** Não é coincidência — é consequência direta
do τ adaptativo.

---

## 4. Plano de implementação em 3 fases

### Fase A — Move ordering simples com PV externa

**Esforço:** ~30 LOC. **Risco:** baixo. **Ganho esperado:** 30–40%.

#### Mudanças em `minimax_pontinhos.py`

Adicionar parâmetro `ordem_hint` na função `_scores_de_todas_jogadas`:

```python
def _scores_de_todas_jogadas(
    estado: EstadoTabuleiro,
    profundidade: int,
    ordem_hint: list[str] | None = None,
) -> dict[str, int]:
    """Igual ao atual, mas se `ordem_hint` for dado, explora os lances
    na ordem dele primeiro. Lances ausentes do hint vão depois (na ordem
    natural)."""
    tracos = estado.tracos_disponiveis()
    if ordem_hint is not None:
        # Reordena: hint primeiro (preserva ordem do hint), depois o resto
        no_hint = set(ordem_hint)
        tracos_ordenados = [t for t in ordem_hint if t in tracos]
        tracos_ordenados += [t for t in tracos if t not in no_hint]
        tracos = tracos_ordenados

    scores = {}
    for traco in tracos:
        # ... corpo idêntico ao atual ...
    return scores


def melhor_jogada_com_scores(
    estado: EstadoTabuleiro,
    profundidade: int = 7,
    ordem_hint: list[str] | None = None,
) -> tuple[str, dict[str, int]]:
    """Aceita `ordem_hint` e o repassa ao `_scores_de_todas_jogadas`."""
    import random
    if not estado.tracos_disponiveis():
        raise ValueError("Nenhum traço disponível.")
    scores = _scores_de_todas_jogadas(estado, profundidade, ordem_hint=ordem_hint)
    melhor_valor = max(scores.values())
    melhores = [t for t, v in scores.items() if v == melhor_valor]
    return random.choice(melhores), scores
```

#### Mudanças em `gerador_amostras_v7_pontinhos.py`

Função `calcular_scores_v7` aceita um parâmetro extra:

```python
def calcular_scores_v7(
    args: tuple[bytes, int, list[str] | None],
) -> tuple[str, np.ndarray, int]:
    estado_bytes, profundidade, ordem_hint = args
    # ... mesma lógica de hoje, mas passando ordem_hint
    rotulo, scores_dict = melhor_jogada_com_scores(
        estado, profundidade=profundidade, ordem_hint=ordem_hint
    )
    # ...
```

#### Mudanças no notebook (Fase 2)

Antes de submeter cada estado ao pool, extrair os scores da Fase 1 do
NPZ e converter em ordem decrescente:

```python
def derivar_ordem_hint(score_jogada_estado: np.ndarray) -> list[str]:
    """Retorna labels canônicos ordenados por score decrescente,
    descartando posições inválidas (-1e9)."""
    indices_validos = np.where(score_jogada_estado > SCORE_INDISPONIVEL / 2)[0]
    indices_ordenados = indices_validos[
        np.argsort(-score_jogada_estado[indices_validos])
    ]
    return [LABELS_CANONICOS[i] for i in indices_ordenados]
```

E na coleta de pendentes da Fase 2, agregar score_jogada por estado:

```python
def coletar_estados_pendentes_com_hint(output_dir):
    estados_unicos = {}  # bytes -> melhor score_jogada disponível
    pendentes = []
    for path in sorted(output_dir.glob("dataset_pequeno_*.npz")):
        with np.load(path) as d:
            if npz_processado(d):
                continue
            pendentes.append(path)
            estados = d["estados"]
            scores_jog = d["score_jogada"]
            depths_jog = d["depth_jogada"]
            for i in range(estados.shape[0]):
                eb = estados[i].tobytes()
                # Mantém o score_jogada com MAIOR profundidade calculada
                if eb not in estados_unicos or \
                   depths_jog[i] > estados_unicos[eb][1]:
                    estados_unicos[eb] = (scores_jog[i], int(depths_jog[i]))
    return estados_unicos, pendentes


# Ao submeter ao pool:
for eb, (sj, _) in estados_unicos.items():
    hint = derivar_ordem_hint(sj)
    futuros[executor.submit(calcular_scores_v7, (eb, p_alvo, hint))] = eb
```

#### Validação

Como medir o ganho:

1. Rodar a Fase 2 atual (sem hint) sobre uma amostra de 5.000 estados;
   medir tempo total e por-bucket de `qtd_tracos`.
2. Rodar a Fase 2 com hint sobre os MESMOS 5.000 estados; medir tempo.
3. Validar que **as melhores jogadas são idênticas** (sanidade — o
   resultado não pode mudar).
4. Comparar tempos.

Se ganho ≥ 25%, aprovar e rodar nos 500k estados completos.

### Fase B — Subir profundidade aproveitando o ganho

**Esforço:** trivial (mudar uma constante). **Risco:** baixo. **Ganho:** +0,5 a +1 nível de profundidade pelo mesmo tempo.

Se a Fase A der ganho de 35-40%, p=8 com move ordering custa
aproximadamente o mesmo tempo do p=7 atual sem ordering. Decisão:

- **Manter p=7**: já é forte para o que a CNN consegue extrair em treino atual; libera CPU.
- **Subir para p=8**: scores de melhor qualidade; valor marginal para a CNN é incerto.
- **Subir para p=9**: requer Fase C (transposition table) ou Databricks.

Recomendação default: **manter p=7**, gastar o ganho em mais robustez
(rodar a Fase 2 num orçamento mais confortável, com sobra para
re-execuções).

### Fase C — Transposition table compartilhada (avançada)

**Esforço:** ~150 LOC + cuidados de concorrência. **Risco:** médio. **Ganho:** +30-50% adicional sobre Fase A.

Cache global de posições (hash → score, profundidade, bound type).
Quando o Minimax descobre uma posição já avaliada com profundidade ≥ a
necessária, retorna direto.

Detalhes não cobertos aqui (decisão para se/quando for necessário):
- Hashing de posições (Zobrist hash recomendado).
- Política de substituição (depth-preferred ou always-replace).
- Concorrência: cache compartilhada via `multiprocessing.Manager`
  (lento) ou cache local por processo (rápido, mas não compartilha
  entre workers).

Implementação só vale o esforço se a Fase 2 medida for proibitiva
(>8h) E se quisermos **subir para p=9**. Para p=7 ou p=8 com move
ordering, o ganho da TT é menor (a poda alpha-beta já é bem agressiva
em árvores pequenas).

---

## 5. Estratégia de mitigação de risco — Notebook separado para Fase 2

### 5.1 Por que separar

Concordo com a sugestão de criar **um notebook separado** se a
otimização for implementada. Razões:

1. **Preservar V7 atual estável.** O notebook
   `Geracao_Amostras_v7_adaptativo.ipynb` continua sendo a referência
   funcional, sem mudanças. Se a otimização tiver bug, basta voltar a
   rodar a Fase 2 do V7 original.
2. **Fase 2 é embaraçosamente paralela.** Não tem dependência da Fase 1
   além do NPZ gerado. Pode ser um pipeline standalone.
3. **A/B test trivial.** Rodar as duas versões sobre o mesmo input,
   comparar scores e tempos.
4. **Habilita Databricks de forma natural.** Notebook separado pode ser
   adaptado para Databricks sem desacoplar a Fase 1 (que é local).

### 5.2 Nome sugerido e localização

`notebooks/jogo_pontinhos/Fase2_MelhorJogada_Acelerada.ipynb` (ou
nome equivalente — `Geracao_Amostras_v7_Fase2_acelerada.ipynb` também
funciona). Lê NPZs do mesmo diretório
`dados/profundidade_minmax_7_adaptativo/` e os reescreve.

### 5.3 Estrutura proposta

```
┌──────────────────────────────────────────────────────────────────────┐
│ Notebook: Fase2_MelhorJogada_Acelerada.ipynb                         │
│                                                                      │
│ Entrada:                                                             │
│   - NPZs em dados/profundidade_minmax_7_adaptativo/                  │
│     gerados pela Fase 1 do V7 (campos da Fase 1 preenchidos,         │
│     campos da Fase 2 ainda vazios)                                   │
│                                                                      │
│ Processamento:                                                       │
│   1. Coleta estados únicos com hint = score_jogada da Fase 1         │
│   2. Para cada estado único, roda Minimax(p_alvo) COM ordem_hint     │
│   3. Cache de resultados por hash (mesmo lance computado uma vez)    │
│                                                                      │
│ Saída:                                                               │
│   - Mesmos NPZs (in-place, atomicamente) com campos da Fase 2        │
│     preenchidos: melhor_jogada, score_melhor_jogada,                 │
│     depth_melhor_jogada                                              │
└──────────────────────────────────────────────────────────────────────┘
```

A Fase 1 continua sendo executada pelo notebook V7 original. A Fase 2 é
trocada (ou alternada) pelo notebook acelerado.

### 5.4 Quando criar este notebook

Recomendação operacional:

1. **Rodar V7 atual** (Fase 1 + Fase 2 sem otimização). Medir tempo
   real da Fase 2.
2. **Se Fase 2 < 4h**: parar. Não criar notebook acelerado. O custo de
   manter dois notebooks não compensa o ganho.
3. **Se Fase 2 entre 4h e 12h**: criar notebook acelerado com Fase A
   (move ordering simples). Rodar localmente.
4. **Se Fase 2 > 12h**: criar notebook acelerado E avaliar Databricks
   em paralelo.

Critério de decisão é o tempo medido, não a estimativa. Não otimizar
prematuramente.

---

## 6. Local vs Databricks

### 6.1 Quando vale Databricks

**Vale a pena se**:

- Fase 2 local com 14 workers > 12h de execução contínua
- Cluster Databricks oferece ≥ 32-64 cores efetivos
- Custo monetário aceitável (cluster paid, não free)
- Equipe já tem o setup de Databricks operacional (você tem)

**Não vale a pena se**:

- Fase 2 local for menor que 6h
- Rodada é única (não recorrente) — overhead de subir cluster, copiar
  NPZs, configurar dependências domina o ganho
- Move ordering local já reduz o tempo a um patamar aceitável

### 6.2 Adaptações necessárias para Databricks

Se chegarmos lá, o notebook acelerado pode ser portado com:

1. **Distribuir os estados únicos** entre os nós do cluster via
   `mapInPandas` (PySpark) ou `RDD.map`.
2. **Cada partição** processa N estados independentemente; resultado
   volta como DataFrame Spark.
3. **Coalescer resultados** num cache global (broadcast ou collect)
   para reescrever NPZs no driver.

A geração da Fase 1 NÃO precisa migrar — ela continua local. Apenas a
Fase 2 (que é paralela e CPU-bound) ganha com o cluster.

### 6.3 Comparativo de custo de tempo

Estimativa grosseira para 500k estados com Minimax(p=7):

| Setup | Tempo estimado |
|---|---|
| Local 14 workers, sem move ordering | ~8h (T baseline) |
| Local 14 workers, com move ordering | ~5h (T × 0,6) |
| Databricks 32 cores, sem move ordering | ~3,5h |
| Databricks 32 cores, com move ordering | ~2h |
| Databricks 64 cores, com move ordering + TT | ~1h |

**Os números são especulativos.** A medição real do baseline local é
o ponto de partida obrigatório antes de qualquer decisão.

---

## 7. Riscos e mitigações

### 7.1 Riscos técnicos

| Risco | Mitigação |
|---|---|
| Bug no novo código produz `melhor_jogada` errada | A/B test com versão original sobre amostra; comparação `assert melhor_jogada_nova == melhor_jogada_antiga` antes de aprovar |
| Hint de ordem com p baixo é ENGANOSO em algumas posições raras | Move ordering com hint ruim degrada para o tempo do baseline, não piora |
| `score_jogada` no NPZ pode estar corrompido em algum estado | Validação prévia: rejeitar hint se contém todos os slots `-1e9` |
| Concorrência: workers gravam cache compartilhada | Não aplicável na Fase A (cada worker é stateless) |

### 7.2 Riscos de processo

| Risco | Mitigação |
|---|---|
| Implementar otimização sem necessidade real | Critério objetivo: medir Fase 2 atual ANTES de implementar |
| Manter dois notebooks divergentes | Notebook acelerado IMPORTA do V7 quando possível; documentar claramente qual é o oficial |
| Dependência de Databricks quebra portabilidade | Manter versão local sempre funcional; Databricks só como aceleração opcional |

---

## 8. Plano de medição (antes de qualquer otimização)

Antes de decidir implementar a Fase A, queremos saber:

1. **Tempo total da Fase 2** atual sobre 500k estados únicos. Métrica
   simples: `time.time()` no início e fim da célula §4 do notebook V7.
2. **Distribuição do tempo por bucket de `qtd_tracos`**. Se 80% do
   tempo está na faixa 20–30 traços, a otimização tem alto ROI lá. Se
   o tempo está distribuído uniformemente, ROI é menor.
3. **Taxa por estado**: estados/segundo total. Se < 10/s no endgame,
   move ordering vai ajudar muito; se > 50/s, não compensa.

Métricas a coletar no notebook V7 atual (uma adição simples na função
`calcular_cache_scores`):

```python
import time
from collections import defaultdict

tempo_por_bucket = defaultdict(float)
contagem_por_bucket = defaultdict(int)

# dentro do loop de as_completed:
n_tracos_estado = ...  # extraído do estado_bytes
inicio = time.time()
resultado = f.result()
elapsed = time.time() - inicio
tempo_por_bucket[n_tracos_estado] += elapsed
contagem_por_bucket[n_tracos_estado] += 1
```

Após a Fase 2 terminar, imprimir:

```
qtd_tracos | nº estados | tempo total (s) | tempo médio (ms)
---------- | ---------- | --------------- | ----------------
   1       |    31      |    0.5          |   16
  ...
  20       |  25_000    |  500.0          |   20
  21       |  24_000    |  600.0          |   25
  ...
  30       |    31      |   30.0          |  967
```

Esse perfil decide o caminho.

---

## 9. Resumo das decisões em aberto

| Decisão | Quando tomar | Como tomar |
|---|---|---|
| Implementar Fase A (move ordering)? | Após medir Fase 2 baseline | Se T > 4h, sim |
| Subir profundidade (p=7 → p=8)? | Após validar Fase A | Decisão de produto, não de engenharia — depende do que a CNN consegue aprender com p=8 vs p=7 |
| Implementar Fase C (TT)? | Só se quiser p=9 | Custo de implementação alto; só se p=9 for desejável |
| Migrar para Databricks? | Se T mesmo otimizado > 8h | Avaliar custo monetário vs ganho |

---

## 10. Referências cruzadas

- **Pipeline V7 atual:** `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`
- **Histórico de decisões:** `docs/historico_decisoes.md` (entrada V7)
- **Guia operacional:** `docs/jogo_pontinhos/guia_geracao_dados.md` §1C
- **Implementação Minimax:** `gerador_dados/jogo_pontinhos/minimax_pontinhos.py`
- **Worker V7:** `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py`
- **Notebook V7:** `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb`
- **Análise de profundidade Minimax (geral):** `docs/jogo_pontinhos/analise_profundidade_minimax.md`
- **Estimativas de tempo Minimax:** `docs/jogo_pontinhos/estimativas_minimax.md`

---

## 11. Glossário

- **Move ordering**: estratégia de ordenar os lances candidatos antes
  de explorar a árvore Minimax. Lances "promissores" primeiro melhoram
  drasticamente a poda alpha-beta.
- **Principal Variation (PV)**: o caminho de jogadas ótimas escolhido
  pela busca Minimax. Numa busca anterior rasa (p baixo), a PV é uma
  boa aproximação da PV da busca profunda (p alto).
- **Iterative Deepening Search (IDS)**: estratégia de buscar p=1, p=2,
  p=3, ..., p_alvo, cada um informando o próximo via PV. Custa um
  pouco mais que p_alvo direto, mas com excelente move ordering.
- **Aspiration Window**: técnica relacionada — usar o score da busca
  rasa como "chute" e fazer a busca profunda numa janela
  `[chute-δ, chute+δ]`. Mais agressiva que move ordering, mas requer
  fallback se cair fora da janela.
- **Transposition Table (TT)**: cache de posições já avaliadas (hash
  → score, profundidade, bound). Acelera buscas onde a mesma posição
  é alcançável por múltiplos caminhos.
- **Zobrist hashing**: técnica para gerar hashes incrementais de
  posições de tabuleiro (cada peça em cada casa tem um número
  aleatório fixo; o hash da posição é o XOR dos números dos elementos
  presentes). Permite recalcular o hash em O(1) após cada movimento.
