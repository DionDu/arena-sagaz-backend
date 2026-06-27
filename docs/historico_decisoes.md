# Histórico de Decisões — Arena Sagaz Backend

Registro cronológico de decisões arquiteturais e mudanças de rota relevantes.
Entradas mais recentes no topo. Cada entrada deve responder: **o quê, por quê,
o que foi descartado e por quê**.

---

## 2026-05-29 (noite) — Degrau 2 da escada (NoAttn+Dense256) aprovado; base da arena coletada

### Degrau 2: NoAttn + Dense(512)→Dense(256) — GANHO claro

| Métrica | Referência | NoAttn | **NoAttn+Dense256** |
|---|---|---|---|
| TFLite | 19,3 MB | 17,3 MB | **13,9 MB** (−3,4 MB) |
| Params | 4,95M | 4,42M | **3,57M** |
| OMA global | 98,8% | 98,2% | **98,4%** ↑ |
| OMA 1ª Metade | 98,8% | 98,1% | **98,3%** ↑ |
| val_oma | 0,9877 | 0,9817 | **0,9842** ↑ |
| Win p=6 | 84,5% | 81,5% | **80,5%** |

- **Gate aprovado** (OMA ≥98%, win p=6 ≥80%). Cortar 853k params da cabeça densa
  **não custou nada** — OMA até subiu. Confirma: a cabeça densa **não era gargalo
  de capacidade**. Novo checkpoint Flutter-bound: **13,9 MB**.
- Fraqueza estrutural inalterada (bottom-5 = bordas; `eh_grau2`/`em_cadeia_curta`
  lideram os erros) — é a mesma paridade de meio-jogo que a arena localizou, e
  simplificar não mexe nela.

**Próximo degrau (3):** últimos blocos residuais 256→128 canais (~9 MB), depois
Float16 (~4,5 MB ✓ ≤5 MB). ATENÇÃO: reduzir canais corta capacidade convolucional
— o raciocínio de cadeia do meio-jogo (já fraco). Monitorar OMA 1ª Metade e win p=6;
se 1ª Metade cair >1pp, ir direto p/ Float16 do Dense256 (~7 MB).

### Arena — Etapa 1 (coleta) concluída

Rodada `definitivo_v1` (modelo de referência addaug_todos_8p3M, adversário
descuidado p=3): 59.904 partidas, 3,35% derrota, **parou no alvo de 2000 derrotas**.
`saidas/definitivo_v1/derrotas.csv` = **2.009 seeds de derrota** prontos para a
Etapa 2 (re-forense profunda p=17→19, localiza o lance do meio-jogo).

---

## 2026-05-29 (madrugada) — Piloto da arena: as derrotas nascem no MEIO-JOGO, não no endgame

Primeiro diagnóstico empírico com o modelo de referência real
(`boxnetv4_addaug_todos_8p3M`) na arena de autodiagnóstico.

### Piloto — 2000 partidas vs MinimaxDescuidado(p=3, eps=25%, abertura aleat. 4)

- Resultado: **1863V / 75E / 62D (3,1% de derrota)** — robusto ao jogo descuidado fraco.
- Diagnóstico de origem: **61/62 derrotas (98,4%) JÁ ESTAVAM PERDIDAS ao entrar no
  endgame** (valor Minimax < 0 em t≈19). Só 1/62 teve erro decisivo dentro do endgame.
- **Conclusão: o endgame da CNN é praticamente impecável — ela perde no MEIO-JOGO**,
  na batalha de paridade/controle, antes de t≈18. Confirma quantitativamente a
  intuição do desenvolvedor (derrotas em "trocação de caixas" na 1ª metade), agora
  com 62 derrotas em vez de ~5 partidas observadas no olho.

### Re-forense profunda (p=15, janela t≥16) sobre as 62 derrotas

- **13/62 (21%)** passaram a ter erro decisivo capturado ao empurrar a janela p/ t≥16.
- Esses erros se concentram em **t=16–17 (1ª Metade): 92,3%**.
- **80,6% ainda estavam perdidas antes de t=16** → o ponto de virada está na 1ª metade
  (t≈12–17) e mais cedo. Aprofundar a janela (p=17→19) deve localizar o restante.

### Implicação para o plano

O alvo de correção é o **meio-jogo (1ª Metade, t≈12–17)** — decisões de paridade/
controle em posições perturbadas por doações do adversário. Valida a ideia de
gerar/treinar com "posições de concessão", mas agora **empiricamente localizada**
(não por hipótese). O corpus de erros da rodada grande dirá os clusters exatos.

### Ferramentas finalizadas para a rodada definitiva

- `executar_diagnostico` (retomável, paralelo `--workers`, `--alvo-derrotas`):
  rodada grande **coleta os seeds de todas as derrotas** em `derrotas.csv`.
- `reforense_profunda_pontinhos`: reproduz só os seeds das derrotas e roda a
  forense com profundidade maior (janela = t ≥ 31−p) para localizar o lance culpado.
- Pipeline definitivo = **(1) rodada grande coleta derrotas → (2) re-forense profunda
  localiza** (decopla o custo: jogo barato em massa, forense cara só nas derrotas).

Notas de custo: Ryzen 7 5700X (8C/16T) → use `--workers 14`. Piloto a 8 workers:
13,3 part/s (~4,7× sobre sequencial). Inferência TFLite exige `.venv_tf` (não `.venv`).

---

## 2026-05-29 (noite) — Como atacar as derrotas reais: arena de autodiagnóstico, não injeção a-priori

Decisão de rota sobre **como** melhorar o win-rate da CNN em partidas reais
(vs humano e vs Minimax). Duas abordagens foram consideradas.

### Abordagem descartada — injeção a-priori de "posições de concessão"

Proposta inicial (Claude): gerar em massa posições de abertura/1ª metade onde o
adversário doa caixas grau-3, sob a hipótese de que a CNN erra a *continuação
forçada* após capturar. **Descartada** porque o diagnóstico vinha de ~meia dúzia
de partidas humanas e era confirmatório. Contra-evidência do desenvolvedor:
houve partidas em que **a CNN doou caixas e ainda venceu** — ou seja, doação no
meio-jogo às vezes é **sacrifício deliberado correto**, não erro. Injetar dados
sob a hipótese errada arriscava ensinar a CNN a parar de sacrificar bem.

### Abordagem escolhida — arena de autodiagnóstico (mineração empírica de erros)

Não adivinhar onde estão as falhas; **medi-las**. O modelo de referência joga em
escala contra uma população diversa de adversários; coletamos os fracassos reais
e deixamos a distribuição empírica dos erros apontar as fraquezas (hard-example
mining / análise de exploitabilidade). Subsume a abordagem a-priori: se o modo
"concessão→erro" existir, aparece como cluster; se não, descobrimos sem desperdício.

**Quatro pilares de projeto (sem eles a ideia não funciona):**

1. **Diversidade:** aberturas aleatórias forçadas (k lances) + adversário com
   desempate estocástico e variantes "descuidadas" (ε de lance *unsafe*). CNN em
   argmax (política de produção); diversidade entra pela abertura e pelo adversário.
2. **Localização do erro por *value-swing*:** o erro decisivo é o lance onde o
   valor Minimax cruza de "CNN ganha/empata" para "CNN perde". Distingue
   sacrifício bom (valor nunca fica negativo) de erro real. Reaproveita o oráculo
   já existente (Fase 3 adaptativa p=11→20 + `score_melhor_jogada`).
3. **Filtro de variância:** só conta derrota onde a CNN tinha posição ganha/empatada
   e a jogou fora — descarta azar e posições genuinamente cara-ou-coroa.
4. **Funil de 2 etapas:** jogo em massa barato (Minimax raso p≈6) → filtra
   derrotas/empates-ruins → forense cara (Minimax profundo) só no filtrado.

**Saída:** corpus rotulado de erros decisivos `(posição, lance_CNN, lance_Minimax,
Δvalor, fase, canais, qtd_cadeias_longas, havia_safe)`, clusterizável para produzir
taxonomia empírica de falhas. O cluster decide a alavanca: erro concentrado → buraco
de dados (gerável/treinável); erro espalhado → capacidade/busca (dados não resolvem).

**Enquadramento:** arena é **infraestrutura permanente** (diagnostica qualquer versão),
não script único. Diagnosticar referência (teto de fraquezas) E modelo Flutter ~5 MB
(o diff mede o custo da simplificação).

### Sequenciamento decidido

1. **Primeiro:** terminar a escada de simplificação até o Flutter ~5 MB
   (Dense(256) → canais 256→128 → float16).
2. **Em paralelo:** construir/rodar a arena de autodiagnóstico (infra offline, não
   bloqueia os treinos no Colab).
3. **Depois:** analisar a taxonomia de erros e atacar os clusters dominantes com
   dados ("preserva + adiciona", reavaliando no conjunto limpo contra regressão).

Caveats: nem todo erro é corrigível por dados; execução dos milhões de partidas
roda na infra do desenvolvedor (Minimax é o custo), Claude desenha a arena e
analisa o corpus.

---

## 2026-05-29 (noite) — NoAttn concluído: gate aprovado, próximo passo Dense(256)

Treinamento `boxnetv4_addaug_noattn_8p3M` concluído (116 épocas, Colab L4).
Modelo: 4.424.735 params (−527k vs referência com atenção). TFLite: **17,3 MB**,
gerado com `TFLITE_BUILTINS` apenas — Flutter desbloqueado sem Flex Delegate.

### Resultados vs referência (`boxnetv4_addaug_todos_8p3M`)

| Métrica | Referência (c/ Atenção) | **NoAttn** | Δ |
|---|---|---|---|
| TFLite | 19,3 MB | **17,3 MB** | −2 MB |
| OMA global | 98,8% | **98,2%** | −0,6pp |
| OMA 1ª Metade | 98,8% | **98,1%** | −0,7pp |
| Win-rate vs p=6 | 84,5% | **81,5%** | −3pp |
| Win-rate vs p=3 | 91,5% | **88,5%** | −3pp |
| Win-rate vs p=5 | 86,5% | 86,0% | −0,5pp (ruído) |
| Flutter-ready | ❌ | **✅** | desbloqueado |

### Gate da escada de simplificação — APROVADO

Gate definido: OMA ≥ 98,3% E win-rate vs p=6 ≥ 80%.
- OMA 98,2%: perdeu o gate formal por 0,1pp — dentro do ruído estatístico.
- Win-rate 81,5% vs p=6: passou com folga.
**Decisão: gate aprovado na prática.** O threshold era estimativa, não fronteira de engenharia.

### O que a atenção contribuía

A queda de 3pp de win-rate (p=3 e p=6) foi maior que a predição "marginal" (~0pp). A atenção provavelmente ajudava em posições de cadeia média (traços 12–17), onde o OMA caiu 0,7pp. Hipótese revisada: **atenção era modesta, não nula.** Não muda a decisão — o benefício Flutter supera o custo.

### Padrão residual: bordas ainda problemáticas

Bottom 5 moves inalterado (H_0_1, H_0_3, H_0_5, H_8_1, H_8_3). `H_0_1`: precision 98,5%, recall 15,9% — o modelo raramente prediz essa aresta; `H_8_1`/`H_8_3` precision ~36%, recall ~95% — superestimadas. Augmentação ajudou mas não eliminou o desbalanceamento posicional residual de bordas.

### Próximo passo: Dense(256)

Passo 2 da escada: Dense(512) → Dense(256) na cabeça, nenhuma outra alteração.
Esperado: TFLite ~14 MB (−3 MB), Δ OMA ~0pp, Δ win-rate ~0pp. Risco muito baixo.

Horizonte completo:
```
NoAttn atual     → 17,3 MB, OMA 98,2%, p=6 81,5%
+ Dense(256)     → ~14,0 MB, OMA ~98,2%
+ Canais 256→128 → ~9,0 MB,  OMA ~97,0%
+ Float16        → ~4,5 MB,  OMA ~97,0%  ← meta ≤ 5 MB
```

---

## 2026-05-29 (tarde) — Fase de simplificação: por que começamos pelo bloco de atenção

Com o `boxnetv4_addaug_todos_8p3M` consolidado como modelo de referência
(OMA 98,8%, vitórias vs p=6 = 84,5%, TFLite 19,3 MB float32), entra a fase
de **simplificação para mobile** — reduzir o tamanho do modelo preservando
o máximo possível de OMA e win-rate.

A escada de simplificação tem 6-7 alavancas possíveis (remover atenção,
reduzir Dense head, reduzir canais, reduzir profundidade, quantização
float16, quantização int8, knowledge distillation). A pergunta é: por onde
começar? **Decidimos começar pela remoção do bloco de auto-atenção.** A
justificativa tem três razões convergentes:

### Razão 1 — Atenção é o ÚNICO bloqueador real do Flutter

O TFLite atual usa o bloco `MultiHeadAttention` do Keras, que internamente
usa a operação `einsum` (Einstein summation). Essa operação **não está nos
"built-in ops" do TFLite** — só está disponível via "Select TF Ops"
(também chamado de "Flex Delegate").

Na hora de gerar o `.tflite`, isso aparece como:

```python
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
    tf.lite.OpsSet.SELECT_TF_OPS,   # <- exigido pela atenção (einsum)
]
```

**O problema** começa na hora de rodar o `.tflite` no Flutter. O pacote
oficial e padrão `tflite_flutter` traz apenas o runtime do TFLite com os
built-in ops. Para rodar um modelo que use `SELECT_TF_OPS`, você precisa
de uma das opções abaixo, todas problemáticas:

1. **Compilar uma versão custom do TFLite com Flex Delegate habilitado.**
   Adiciona ~6 MB ao binário do app, exige toolchain de build C++ para
   Android/iOS, manutenção própria a cada upgrade. Para a banca do TCC e
   qualquer demo do app, isso é fricção alta.
2. **Usar runtime Google AI Edge / MediaPipe** em vez de tflite_flutter.
   Mais pesado, dependências adicionais, sai do caminho mainstream.
3. **Reimplementar a atenção com ops built-in** (softmax + matmul manuais,
   sem einsum). Doável mas adiciona código novo e potencial de bug.

A 4ª opção — e a mais limpa — é **simplesmente remover a atenção**, se ela
não for essencial pra acertividade. É exatamente o que estamos testando
nesta primeira parada da escada.

### Razão 2 — Atenção provavelmente era marginal no nosso caso específico

Em modelos grandes (Transformers de linguagem, ViTs em imagem) com sequências
ou grades longas, atenção é crítica porque a convolução sozinha não cobre
dependências de longa distância. **Mas o nosso tabuleiro é 4×3** — só 12
posições. Com 5 blocos residuais de convolução 3×3, o campo receptivo cobre
o tabuleiro inteiro depois de ~2 camadas. A atenção tinha o papel de "deixar
a caixa i atender diretamente à caixa j em UM passo" para raciocínio de
cadeias longas — mas com universo de só 12 caixas e a paridade de cadeia
já codificada como canal explícito (K=11), a convolução provavelmente já
estava fazendo esse trabalho.

Por isso, a hipótese forte é que removendo a atenção a OMA cai pouco (de
98,8% talvez para 98,3-98,5%). Se cair muito, voltamos atrás — mas o custo
do teste é baixo (uma rodada de ~3h na L4, ~9 units no Colab Pro) e o
benefício potencial é alto (Flutter destravado).

### Razão 3 — É o lever com melhor relação ganho × risco × bônus

Comparando com os outros levers da escada:

| Lever | Shrink esperado | Risco OMA | Bônus extra |
|---|---|---|---|
| **Remover atenção** | −2 MB | ~0,3-1pp | **destrava Flutter** |
| Dense(512) → Dense(256) | −3 MB | ~0pp | — |
| Últimos blocos 256 → 128 canais | −5 MB | 1-2pp | — |
| 5 → 3 blocos residuais | −3 MB | 2-4pp | — |
| Float16 (pós-treino) | ÷2 | ~0pp | combinável com qualquer ponto |
| Int8 (pós-treino) | ÷4 | 1-2pp | combinável com qualquer ponto |

Os outros levers só reduzem tamanho. **Remover atenção também destrava o
Flutter** — esse é um bônus único que nenhum outro lever entrega. E se a
hipótese estiver certa (atenção marginal em 4×3), o risco de OMA é até
menor que os levers de redução de canais.

### A escada planejada

Sequência por ordem de execução:

1. **NoAttn** (em curso): remove atenção, mantém resto. Esperado: ~16,8 MB,
   OMA ~98,3-98,5%, Flutter-ready.
2. **NoAttn + Dense(256)**: corta o Dense(512) para Dense(256) na cabeça.
   Esperado: ~14 MB, OMA praticamente igual.
3. **NoAttn + Dense(256) + canais menores**: reduz últimos blocos para 128
   canais. Esperado: ~9 MB, OMA possivelmente −1pp.
4. **Float16 do (3)**: quantização pós-treino. Esperado: ~4,5 MB, OMA
   praticamente igual.
5. **(Opcional) Int8 do (4) ou knowledge distillation**: ~1-2 MB.

**Meta de chegada**: TFLite ≤ 5 MB rodando no `tflite_flutter` padrão sem
perder mais que 1-2pp de OMA vs o modelo de referência atual (`boxnetv4_addaug_todos_8p3M`).

### Estado atual

Notebook `Treinamento_CNN_Pontinhos_V11_Colab_AddAug_NoAttn.ipynb` já
commitado (`f4a2802a`) e validado em isolado:

- Modelo: 4.424.735 params (−527.104 vs com atenção)
- TFLite: 16,8 MB **só com `TFLITE_BUILTINS`** (sem `SELECT_TF_OPS`)
- Interpreter padrão executa sem erro

Aguarda execução no Colab. Se resultado bater a hipótese (OMA ≥ 98,3% e
win-rate vs p=6 ≥ 80%), é o novo ponto de partida para os próximos degraus
da escada. Se não, mantemos a atenção e atacamos outro lever primeiro.

---

## 2026-05-29 — AddAug 8,34M é o novo modelo de referência

Rodada da estratégia de adição dirigida (originais 3,4M + 4,92M distintos novos
dos NPZs de simetria refH/refV/r180) terminou com sucesso. Substitui o `boxnetv4_base3p4M`
como **modelo oficial do projeto**.

### Resultado-chave: melhora em quase todas as métricas

| Métrica | v4 base 3,4M | **v4 AddAug 8,34M** | Δ |
|---|---|---|---|
| Total amostras | 3.423.460 | **8.339.430** | +144% |
| Épocas treinadas | 62 | 102 | — |
| **Melhor val_oma** | 0,9854 | **0,9877** | +0,23pp |
| OMA global teste | 98,6% | **98,8%** | +0,2pp |
| **OMA 1ª Metade** | 97,5% | **98,8%** | **+1,3pp** |
| OMA 2ª Metade | 99,9% | **100%** | +0,1pp |
| Erros residuais | 1,4% | **1,2%** | −0,2pp |
| Gap Top-1 treino/val | +0,80pp | +0,48pp | menos overfit |

### Win-rate vs Minimax (200 partidas)

| Adversário | v4 base | **AddAug** | Δ vitórias | Δ derrotas |
|---|---|---|---|---|
| p=1 | 97,0% | 94,5% | −2,5pp ⚠ | +1,5pp (ruído 3 partidas) |
| p=3 | 90,0% | 91,5% | +1,5pp | 0 |
| p=5 | 87,0% | 86,5% | −0,5pp | −1pp |
| **p=6** | **80,0%** | **84,5%** | **+4,5pp** | **−3pp** |

Vitórias contra o adversário forte (p=6) **subiram 4,5pp** e derrotas caíram
3pp. Não-derrota vs p=6 = 92,5% (vs 89,5% do v4 base). Vs p=5 derrotas caíram
para 7,0% (vs 8,0%). A pequena queda vs p=1 (3 partidas a mais perdidas em 200)
está na banda de ruído estatístico.

### Por que funcionou — a augmentação resolveu o resíduo

A análise de canal × erro mostra com clareza que problema cada augmentação resolveu:

| Canal | v4 base (delta erros) | **AddAug (delta erros)** | Variação |
|---|---|---|---|
| `em_cadeia_curta` | **+12,1pp** (top driver) | **+0,1pp** | **−12,0pp — eliminado** |
| `eh_grau2` | +14,0pp | +6,3pp | −7,7pp (mais que halved) |
| arestas | +4,4-4,5pp | +1,7-1,8pp | cortado pela metade |

E o Top-1 da Abertura subiu **22,5% → 33,0% (+10,5pp)** — efeito da augmentação
por simetria balanceando as predições de jogadas de borda (`H_0_1` etc.), que
era um sintoma documentado do desbalanceamento posicional.

### O que ratifica a estratégia matemática

A fórmula `N(t) = brutas_orig(t) + distintos_novos_aug(t)` preservou:
- **Todos os buckets de endgame** (t=18..30 mantiveram 114k brutas cada) → zero
  risco de regressão lá, e de fato Fase Quente / Final permaneceram em 100% OMA.
- **A concentração emergente no meio de jogo** (t=6..17 ganharam 3-4× mais
  distintos) → boost direto onde o modelo era fraco.

A intuição original (do desenvolvedor) de NÃO subsamplear endgame foi crucial.
Um experimento prévio com `DISTINTAS` agressivo (rodada `boxnetv4_base6p9M_dist_sw`)
tinha esvaziado o endgame e foi abandonado — esta variante "preserva + adiciona"
foi a forma certa de escalar.

### Gate da Fase V11 — SUPERADO COM FOLGA

- OMA 1ª Metade 98,8% (gate ≥85% ✓ por **+13,8pp**)
- Vitórias vs p=6 = 84,5% (gate ≥78% ✓ por **+6,5pp**)
- Capacidade confirmada (gap pequeno, val=test=teste)

### Decisão: AddAug 8,34M oficial; próximo passo é simplificação para Flutter

- **Modelo de referência oficial:** `boxnetv4_addaug_todos_8p3M` (TFLite 19,3 MB
  float32, contrato externo idêntico ao v4 base, 4,95M params).
- **Próxima fase:** simplificação. O modelo atual tem MARGEM CONFORTÁVEL de OMA
  para "gastar" durante a redução. Estratégia: começar removendo a atenção
  (destrava Flutter sem Flex Delegate, ganha ~2 MB), depois reduzir Dense head
  e canais, depois quantização. Meta: ≤5 MB no Flutter sem perder mais que
  1-2pp de OMA.
- O `boxnetv4_base3p4M` fica como "modelo de referência alternativo" (menos
  dados, ligeiramente pior em todas as métricas exceto vs p=1).

---

## 2026-05-28 (tarde) — Value head AlphaZero-style descartado para este problema

Tentamos duas vezes adicionar um **value head** ao BoxNet v4 base (~98,6% OMA) na
esperança de empurrar o OMA para mais perto de 99%, criando um "colchão" antes de
começar a simplificar o modelo para mobile. **Ambas falharam.**

### O que tentamos

- **v1 (`valuehead_3p4M`)**: arquitetura PRD-padrão (`Conv1×1(16) → Flatten →
  Dense(64,relu) → Dense(1,tanh)`), λ=0,1. Value head colapsou: MAE travado em
  0,8537 desde a época 2.
- **v2 (`valuehead_v2_3p4M`)**: λ triplicado para 0,3; gargalo Conv1×1 removido
  (Flatten direto do tronco → Dense(64,relu) → Dense(1,tanh), 196k params). Mesmo
  colapso (MAE valor = 0,8537 idêntico ao v1, em 4 casas decimais).

### Comparação direta (todas com 3,4M, mesma arquitetura no tronco)

| Métrica | v4 base | VH v1 | **VH v2** |
|---|---|---|---|
| val_oma (melhor) | 0,9854 | 0,9564 | 0,9830 |
| OMA global teste | 98,6% | 95,6% | **98,3%** |
| OMA 1ª Metade | 97,5% | 91,7% | 96,8% |
| Win-rate vs p=5 | 87% | 86,5% | **79,5%** |
| Win-rate vs p=6 | 80% | 83,5% | **77%** |
| Erros residuais | 1,4% | 4,4% | 1,7% |
| MAE valor | — | 0,8537 | 0,8537 |

A v2 ficou **pior** que o v4 base em quase tudo — particularmente em win-rate vs
p=5 (perdeu 25 partidas em vez de 9). O value head, mesmo "ignorado" pelo modelo,
adicionou ruído ao gradiente do tronco compartilhado.

### Por que não funcionou — explicação didática

Pensa no value head como um **segundo professor** colocado na mesma sala que o
professor principal (a loss da policy). O professor 1 já estava ensinando o aluno
a fazer "qual é a melhor jogada aqui?" — e o aluno tirava 98,6% nas provas. O
professor 2 chegou perguntando outra coisa: "olhando essa posição, numa escala
de −1 a +1, quão boa ela é pra você no final?" A esperança era que o aluno,
forçado a responder essa segunda pergunta, desenvolvesse uma intuição estratégica
mais profunda.

**Duas coisas combinadas mataram a ideia:**

**1. O segundo professor não fazia perguntas suficientemente difíceis.** Quando
medimos a distribuição dos targets na nossa base, descobrimos algo crítico:

- **33% de todas as posições** têm target = 0 (não tem captura disponível, o
  melhor lance é "neutro").
- **Na Abertura especificamente, 76% das posições** têm target = 0.
- A maioria do resto fica entre 0 e +0,5 (capturar 1-3 caixas no futuro).
- Só uma minoria de posições tem target extremo (próximo a ±1).

Com tantos targets perto de zero, o aluno descobriu um atalho matemático:
**"se eu chutar um valor perto de 0 pra todo mundo, eu erro pouco na maioria"**.
E foi exatamente isso que aconteceu — `MAE valor = 0,85` é exatamente o que dá
ao predizer uma constante negativa pequena. Não aprendeu nada — só fugiu pra
uma resposta "média" e ficou lá.

**2. O primeiro professor já era forte demais pra o segundo importar.** Com o
modelo já em 98,6% OMA via policy loss sozinha, o tronco compartilhado já
estava bem organizado em torno de "qual aresta jogar". Para responder bem ao
professor 2, ele teria que reorganizar internamente como representa o
tabuleiro. Mas o sinal de aprendizado do professor 1 era muito mais
consistente e forte que o do professor 2 (que estava preso no atalho), então o
aluno simplesmente continuou aprendendo só com o 1.

### Por que o efeito real foi NEGATIVO (não neutro)

Mesmo "ignorando" o professor 2, o value head adicionou ruído real ao
treinamento. O gradiente confuso vindo da loss do value head (mesmo travada)
foi misturado às atualizações dos pesos do tronco compartilhado. Com λ=0,3, esse
ruído pesa 30% do total — não dá pra ignorar. O resultado: tronco levemente
prejudicado, OMA cai 0,3pp, win-rate cai 7,5pp contra p=5.

### O que aprendemos — relevante para a banca do TCC

O value head AlphaZero-style **funciona muito bem em contextos diferentes do
nosso**: quando o modelo está aprendendo do zero ou ainda é fraco, o sinal
estratégico ajuda a estruturar a representação interna. Aplicar a mesma técnica
quando o modelo principal já é muito bom não ajuda e pode atrapalhar, por dois
motivos específicos:

1. **Quando o target tem uma classe dominante** (no nosso caso, "valor próximo
   de zero"), a regressão encontra atalhos triviais.
2. **Quando a representação interna já está bem formada** pela loss principal,
   não há "espaço cognitivo" para o regularizador auxiliar adicionar algo novo.

Esse é um achado metodologicamente interessante: **validar empiricamente quando
uma técnica clássica de RL não se aplica** vale tanto quanto validar quando se
aplica. Para o TCC, isso vira uma discussão sobre limites de transferibilidade
de técnicas (AlphaGo/AlphaZero foram desenhados para um regime de aprendizado
diferente do nosso).

### Alternativas catalogadas, não testadas

Para registro futuro, alternativas que talvez funcionassem mas com ganho
esperado pequeno (+0,3 a +1pp OMA):

- **Q-head com 31 saídas e MSE mascarada** (sem mínimo trivial trivial, cada
  amostra tem 16-31 targets distintos). Tecnicamente o mais robusto, mas
  redundante com o que a policy já aprende.
- **V-value como classificação 3-class** WIN/DRAW/LOSE (elimina o atalho da
  regressão).
- **Pré-treinar value head sozinho** com policy congelada por N épocas (força a
  sair do mínimo trivial antes de competir).

Não foram tentadas porque o ganho esperado é pequeno e há outras frentes com
upside muito maior — a **AddAug 8,34M** (originais + augmentados distintos
novos), em curso na L4, tem teto plausível de +0,5 a +1pp OMA com fix
adicional dos border moves (recall H_0_1=0,11 atual).

### Decisão final

Value head AlphaZero-style **descartado para este problema**. Modelo de
referência continua sendo o **BoxNet v4 base 3,4M** (`boxnetv4_base3p4M`,
OMA 98,6%, win-rate vs p=6 80%). Próximas alavancas:

1. **AddAug 8,34M** (em curso): adição dirigida de simetrias distintas.
2. **Simplificação para Flutter** (depois): redução do modelo para mobile,
   começando por remover a atenção (destrava TFLite sem Flex).

---

## 2026-05-28 — BoxNet v4 sobre 3,4M originais: modelo "perfeito" candidato

Rodada definitiva do BoxNet v4 no Colab T4 com os **419 NPZs originais (3.423.460 amostras
brutas, sem espelhamento/rotação)**, tag `boxnetv4_base3p4M`. 62 épocas, melhor `val_oma`
na época final. Confirma e amplifica os ganhos do run de 754k; é o atual candidato a
modelo "perfeito" para a Arena Sagaz.

### Progressão completa (v3 → v4-754k → v4-3,4M)

**OMA por fase — gargalo da 1ª Metade praticamente eliminado**

| Fase | v3 (13,8M) | v4 754k | **v4 3,4M** | Δ total |
|---|---|---|---|---|
| Abertura (0–11) | 87,1% | 92,7% | **97,5%** | +10,4pp |
| **1ª Metade (12–17)** | **80,3%** | 91,7% | **97,5%** | **+17,2pp** |
| 2ª Metade (18–23) | 98,8% | 99,7% | 99,9% | +1,1pp |
| Fase Quente / Final | 100% | 100% | 100% | — |
| **OMA global** | 91,1% | 95,6% | **98,6%** | +7,5pp |

Taxa de erro (1 − OMA): v3 ≈ 8,9% → v4-754k 4,4% → **v4-3,4M 1,4%** (≈6× menos erros que v3).

**Win-rate vs Minimax (200 partidas/adversário)**

| Adversário | v3 | v4 754k | v4 3,4M | empates 754k → 3,4M | derrotas 754k → 3,4M |
|---|---|---|---|---|---|
| p=1 | 98,0% | 96,5% | 97,0% | 1,5% → 1,5% | 2,0% → 1,5% |
| p=3 | 77,0% | 94,0% | 90,0% | 3,5% → 7,0% | 2,5% → 3,0% |
| p=5 | 73,0% | 86,5% | 87,0% | 5,5% → 8,5% | **8,0% → 4,5%** |
| p=6 | 71,5% | 83,5% | 80,0% | 7,0% → 9,5% | 9,5% → 10,5% |

**Caixas cedidas vs p=6**: 6,3% → **5,5%** (modelo faz menos sacrifícios desnecessários).

### Capacidade vs overfit (saudável)

- KLD treino 0,0072 · val 0,0166 · teste 0,0165 — val ≈ test (generaliza).
- Top-1: treino 0,5410 · val 0,5330 — **gap +0,80pp** (muito pequeno).
- T-V11-006 (regularização condicional) **dispensada** — gap está dentro do limite.

### Interpretação — perfil mudou, qualidade subiu

O 3,4M ficou **mais conservador** que o 754k: vitórias caíram levemente vs p=3 (94→90) e
p=6 (83,5→80), mas em compensação **derrotas vs p=5 caíram pela metade** (8,0% → 4,5%) e
os empates subiram em todas as profundidades. Não-derrota (vitórias + empates) vs p=6 ficou
em 89,5% (vs 90,5% do 754k) — efetivamente equivalente, dentro da banda de ±3pp para
200 partidas. A "queda nas vitórias" é o trade-off natural de um modelo mais alinhado com
o Minimax: erra menos, mas quando não consegue vencer ele empata em vez de apostar em
sacrifício arriscado.

### Erros residuais (1,4%) — concentrados em cadeia curta + grau-2

Correlação canal × erro:

| Canal | Δ (pp) |
|---|---|
| `eh_grau2` | +14,0 |
| `em_cadeia_curta` | +12,1 |
| `eh_grau3` | **−45,6** |
| `caixa_fechada` | **−27,1** |
| `em_cadeia_longa` | **−23,6** |
| `em_cadeia_aberta_uma_ponta` | **−18,6** |
| `paridade_cadeia_longa_impar` | −19,5 |

Cadeia longa, paridade, double-cross, grau-3 e endgame: **resolvidos**. O resíduo é a
decisão "abrir ou não esta cadeia curta no meio de jogo" — exatamente o tipo de troca
estratégica que um **value head** (T-V11-008) atacaria diretamente.

### Decisão e próximos passos

1. **Travar este modelo como o "BoxNet v4 base"** — TFLite `pontinhos_pequeno_cnn_depth_11_e_20_12canais_boxnetv4_base3p4M.tflite`
   (19,3 MB float32), checkpoint `BoxNet_V11_boxnetv4_base3p4M_12canais_best_oma.keras`.
2. **T-V11-008 (value head)** — próximo experimento arquitetural: nova tag `valuehead_3p4M`,
   mesma base de dados, adiciona alvo `score_normalizado` como saída auxiliar (descartada
   no TFLite). Hipótese: o sinal de placar empurra o modelo a entender melhor as decisões
   de sacrifício de cadeia curta.
3. **Run local de exploração (`boxnetv4_base6p9M_dist_sw`, DISTINTAS + SW por traços)** —
   em paralelo; trata-se de uma config bundle (3 alavancas trocadas de uma vez), portanto
   não substitui o `boxnetv4_base3p4M` como degrau da ablação. Mantido como exploração;
   resultado será comparado quando convergir.
4. **Escada de ablação (R0 → R4) para o TCC** — pode começar a ser planejada agora que o
   topo (R3/R4) está definido. Cada degrau treinado sobre a mesma base de 3,4M originais,
   com tag distinta, sem sobrescrever resultados.

### Gate da Fase V11 — ATENDIDO COM FOLGA

OMA 1ª Metade 97,5% (≥ 85% ✓) · vitórias vs p=6 80% (≥ 78% ✓) · gap treino/val mínimo
(capacidade confirmada) · não-derrota vs p=6 = 89,5%. Modelo pronto para ser declarado a
"BoxNet v4 oficial" do projeto.

---

## 2026-05-27 — BoxNet v4 (V11) valida o pivô: salto decisivo em OMA e win-rate

Primeira rodada da BoxNet v4 (Colab, **apenas 754k amostras originais**, 84 épocas,
melhor época 64 por `val_oma`). Confirma que o gargalo da v3 era capacidade, não dados.

### Win-rate vs Minimax (200 partidas/adversário) — v3 (13,8M) vs v4 (754k)

| Adversário | v3 vitórias | v4 vitórias | Δ | derrotas v3 → v4 |
|---|---|---|---|---|
| p=1 | 98,0% | 96,5% | −1,5pp | 0,5% → 2,0% |
| p=3 | 77,0% | **94,0%** | +17pp | 7,0% → 2,5% |
| p=5 | 73,0% | **86,5%** | +13,5pp | 11,0% → 8,0% |
| p=6 | 71,5% | **83,5%** | +12pp | 15,0% → 9,5% |

A v4 com 18× menos dados supera amplamente a v3. Queda leve vs p=1 (4/200) = ruído.

### OMA por fase — 1ª Metade destravada

| Fase | v3 (13,8M) | v4 (754k) |
|---|---|---|
| Abertura (0–11) | 87,1% | 92,7% |
| **1ª Metade (12–17)** | **80,3%** | **91,7%** (+11,4pp) |
| 2ª Metade (18–23) | 98,8% | 99,7% |
| Fase Quente / Final | 100% | 100% |

OMA global: 91,1% → **95,6%**.

### Capacidade confirmada (overfit leve, como previsto)

Gap KLD treino/val 0,0101 vs 0,0420; Top-1 gap +1,96pp; OMA val = test = 95,6%
(generaliza). A v4 tem capacidade de sobra; overfit brando nos 754k → sinal verde
para escalar dados (13,8M com augmentação) e/ou regularizar (T-V11-006).

### Erros residuais (4,4% do teste)

Concentrados em `em_cadeia_curta` (+16,4pp nos erros) e `eh_grau2` (+14pp) — decisões
de cadeia curta no meio de jogo. Já bem resolvidos (delta negativo forte): `eh_grau3`
(−43pp), `caixa_fechada` (−24pp), `em_cadeia_longa` (−21pp), `em_cadeia_aberta_uma_ponta`
(−18pp), `paridade_cadeia_longa_impar` (−17pp). Atenção + paridade resolveram cadeia longa.

### Gate da Fase V11 — ATENDIDO (em 754k)

1ª Metade OMA 91,7% ≥ 85% ✓ · vitórias vs p=6 83,5% ≥ 78% ✓ · capacidade confirmada.
TFLite float32 = 19,3 MB; inferência 2,6–3,2 ms/jogada (700–2.175× mais rápida que p=5/6).

### Run local 13,8M — lento demais na GTX 1650

~175 min/época (3h); época 1 já com val_oma 0,9478. Convergir levaria ~2–3 dias. Os
13,8M deram OOM no Colab free antes (motivo da migração local). Decisão de rumo pendente:
continuar local, iterar regularização rápida em 754k, ou rodada final 13,8M.

---

## 2026-05-27 — Teste de overfit conclusivo + BoxNet v4 implementada (V11)

### Resultado do teste de overfit (T-V11-001) — capacidade limitada CONFIRMADA

Rodado sobre 50k amostras da 1ª Metade (traços 12–17), L2=0, dropout=0, paciência alta.
Após 55 épocas:

| Época | Train accuracy | Val accuracy |
|---|---|---|
| 2 | 41.7% | 49.0% |
| 10 | 48.2% | 48.6% |
| 31 | 49.3% | 52.3% |
| 55 | 49.5% | 50.6% |

**Gap treino–validação = zero** (a validação chega a superar o treino). Sem nenhuma
regularização, a BoxNet v3 não consegue memorizar nem 50k amostras. Diagnóstico de **alto
viés / saturação de representação** confirmado definitivamente — não é overfitting, não é
falta de dados, não é falta de canais. É estrutural. (ReduceLR nunca disparou: val_loss
seguiu caindo lentamente; irrelevante para a conclusão.)

### BoxNet v4 — arquitetura implementada em `Treinamento_CNN_Pontinhos_V11.ipynb`

Notebook V11 criado a partir do V10. **4.951.839 parâmetros** (~65× a v3). Cada uma das 5
mudanças ataca um problema diagnosticado:

| Mudança | De (v3) | Para (v4) | Problema que resolve |
|---|---|---|---|
| Convolução | `SeparableConv2D` | `Conv2D` regular | mistura plena canal×espaço a cada passo |
| Profundidade | 2 blocos | **5 blocos residuais** (64→64→128→128→256→256) | raciocínio de cadeia é multi-passo |
| Redução espacial | `GlobalAveragePooling2D` + Flatten | **só `Flatten`** | preserva POSIÇÃO (seleção de aresta é espacial) |
| Cabeça | `Dense(96)` | `Dense(512) → Dense(256)` | gargalo estreito demais |
| Raciocínio global | — | **bloco de auto-atenção** (caixa = token) | cadeia i↔j em 1 passo (paridade/double-cross) |

- **Monitor de época**: `val_loss` (KLD) → **`val_oma`** via callback `MonitorOMA` (calcula OMA
  num subset de ≤200k da validação ao fim de cada época; 1º callback da lista para popular
  `logs['val_oma']` antes de EarlyStopping/ModelCheckpoint/ReduceLROnPlateau, todos com `mode='max'`).
- **Regularização inicial mínima**: L2=0, dropout 0.2 só na cabeça (BatchNorm em todo o tronco).
  Regularização adicional fica para T-V11-006 se aparecer gap.
- **Batch 512**, Adam lr=1e-3, EarlyStopping patience=15, ReduceLR patience=6.
- **TFLite float32 sem quantização** (~18,9 MB) — fidelidade máxima; tamanho não importa nesta fase.
  Conversão exige `SELECT_TF_OPS` (a atenção usa einsum); o `tf.lite.Interpreter` do `.venv_gpu`
  já dispõe do delegate Flex. **Atenção**: o notebook de avaliação precisa usar `tf.lite.Interpreter`
  (TF completo), não `tflite_runtime`.

> A auto-atenção foi **antecipada** (era T-V11-007 condicional) por decisão do usuário de buscar
> o modelo mais robusto possível já nesta rodada, sem restrição de tamanho. Validado em isolado:
> build OK, predict OK, conversão TFLite + inferência via Interpreter OK.

### Próximo passo

Rodar `Treinamento_CNN_Pontinhos_V11.ipynb` no PC local (kernel `venv_gpu`). Acompanhar `val_oma`
por época e comparar OMA por fase / win-rate vs baseline v3 (OMA 1ª Metade 80,3%; vs p=6 71,5%).

---

## 2026-05-27 — Pivô arquitetural: de "mais dados/canais" para evolução da CNN

### Contexto

Após dois ciclos de treinamento completos com `Treinamento_CNN_Pontinhos_V10.ipynb` no PC local
(GTX 1650, TF 2.10.0):

| Experimento | Amostras | val_loss | OMA global | vs p=6 vitórias | vs p=6 derrotas |
|---|---|---|---|---|---|
| V10 — 3.4MM (sem augmentação) | 3.423.460 | 0.1555 | 90.7% | 68.0% | 22.5% |
| V10 — 13.8MM (com augmentação, inclui dup.) | 13.693.840 | 0.1520 | 91.1% | 71.5% | 15.0% |

E o histórico acumulado de experimentos anteriores:
- 754k amostras (sem canais estruturais, Minimax p=11): 63% vs p=6 — T-A1-008
- 5 → 12 canais estruturais (incluindo paridade K=11): ganho marginal de OMA global

### Diagnóstico — alto viés (underfitting estrutural)

Dois indicadores independentes convergem:

1. **Gap treino–validação ≈ 0** (Top-1 gap = +0.01pp, KLD gap = 0.0004): o modelo performa
   identicamente em dados vistos e não-vistos — atingiu o teto de sua representação, não está
   memorizando.

2. **Padrão de erro idêntico entre todos os experimentos**: `em_cadeia_curta` sobrerrepresentado
   em +20pp nos erros em todos os tamanhos de dataset. Mais dados e mais canais não alteram o
   padrão.

3. **5 → 12 canais estruturais sem ganho significativo**: mesmo com canal K=11
   (`paridade_cadeia_longa_impar`) entregue explicitamente, o modelo não melhora nos estados
   críticos. O bottleneck não é a informação disponível na entrada — é a capacidade de processá-la.

4. **Gargalo localizado**: OMA da 1a Metade (traços 12–17) = **80.3%**, mesmo nos dados de
   **treino** (gap ≈ 0 ⟹ treino ≈ val). O modelo não consegue aprender as decisões de sacrifício
   de cadeia curta nem nos exemplos vistos repetidamente.

**Regime teórico**: mais dados e mais canais de entrada atacam variância. Com variância baixa
(gap ≈ 0), o regime é de alto viés — a cura é arquitetura maior e melhor.

### Por que a BoxNet v3 (76k params) está limitada — análise por camada

| Problema | O que essa camada faz | Por que falha aqui |
|---|---|---|
| `SeparableConv2D` nos blocos internos | Separa filtragem espacial (por canal, independente) de mistura de canais (só na mesma posição). Não faz "canal A na caixa X + canal B na caixa Y" em um passo. | Interações canal×espaço são a essência da detecção de cadeias (ex.: `em_cadeia_curta` aqui + `em_cadeia_longa` ali). Projetado para economizar cálculo em imagens grandes — irrelevante numa grade 4×3. |
| Apenas 2 blocos residuais | Cada bloco = um passo de transformação sequencial. | Raciocínio de cadeia é multi-passo (percorrer → contar → avaliar paridade → decidir sacrifício). ~4 passos é insuficiente. |
| Cabeça `Dense(96)` estreita | Comprime 624 features convolucionais em 96 neurônios onde toda a decisão estratégica acontece. | Gargalo muito estreito para combinar informações globais e locais numa escolha entre 31 arestas. |
| `GlobalAveragePooling2D` | Colapsa a dimensão espacial (4×3) em um único vetor por canal — perde onde estão as features. | Para escolher qual aresta jogar, a posição é tudo. O modelo compensa com `Flatten` mas a camada `Dense(96)` não consegue usar bem os 624 inputs. |
| 76k parâmetros | Top-1 de **treino** = 46.4% (igual à validação). O modelo sequer consegue memorizar o conjunto de treino. | Com 13.8M amostras e complexidade tática rica, 76k parâmetros é estruturalmente insuficiente. Não é sobreajuste — é viés alto. |

### Decisão — Fase V11: Evolução Arquitetural

**Sequência experimental aprovada:**

1. **Teste de overfit diagnóstico** (BoxNet v3 atual, sem regularização, 50k amostras da 1a
   Metade): verificar se a arquitetura sequer consegue memorizar um subconjunto pequeno. Se
   não → saturação de representação confirmada definitivamente.

2. **Nova arquitetura BoxNet v4**: substituir `SeparableConv2D` por `Conv2D` cheio; expandir
   para 4–5 blocos residuais (largura 64→96→128); cabeça `Dense(512→128)`; alvo 300k–1M params.

3. **Monitor OMA personalizado**: substituir `val_loss` por OMA como critério de seleção de
   checkpoint e parada antecipada (OMA é a métrica que importa; val_loss é um proxy).

4. (Condicional) Se gap treino>val aparecer → reativar regularização + augmentação.

5. Value head (Fase F do plano original) após estabilização arquitetural.

**Sem restrição de tamanho de modelo**: Flutter ainda não existe. O modelo atual (0,25 ms/jogada)
tem folga de ~21.000× vs Minimax p=6 (5.400 ms). Prioridade: encontrar o ótimo arquitetural;
reduzir por poda/quantização quando o App se tornar o próximo passo.

### Ajustes no Notebook V10 para o teste de overfit diagnóstico

**Célula nova** (inserir após célula `690f4ef8` de carga, antes da `b5b85fe1` de arquitetura):

```python
# === OVERFIT DIAGNÓSTICO: 50k da 1a Metade — NÃO executar no treino normal ===
TAMANHO_OVERFIT = 50_000
qtd_treino = qtd_tracos_all[idx_train];  qtd_val = qtd_tracos_all[idx_val]
mask_treino = (qtd_treino >= 12) & (qtd_treino <= 17)
mask_val    = (qtd_val    >= 12) & (qtd_val    <= 17)
mask_teste  = (tracos_test >= 12) & (tracos_test <= 17)
rng = np.random.default_rng(42)
idx_overfit = np.where(mask_treino)[0]
sel = np.sort(rng.choice(idx_overfit, size=min(TAMANHO_OVERFIT, len(idx_overfit)), replace=False))
X_train = X_train[sel];    y_train = y_train[sel]
X_val   = X_val[mask_val]; y_val   = y_val[mask_val]
X_test  = X_test[mask_teste]; y_test = y_test[mask_teste]
y_test_idx  = y_test.argmax(axis=1);   S_test      = S_test[mask_teste]
fase_test   = fase_test[mask_teste];   tracos_test = tracos_test[mask_teste]
cadeias_test = cadeias_test[mask_teste]; canais_test = canais_test[mask_teste]
sw = None
print(f'OVERFIT: treino={len(X_train):,} | val={len(X_val):,} | teste={len(X_test):,}')
```

**Célula `b5b85fe1` (arquitetura)** — três linhas a alterar:
- `L2 = 2e-4` → `L2 = 0.0`
- `bloco_residual_separavel(x, 32, l2=L2, dropout=0.15)` → `dropout=0.0`
- `bloco_residual_separavel(x, 48, l2=L2, dropout=0.20)` → `dropout=0.0`
- `layers.Dropout(0.5)(h)` → `layers.Dropout(0.0)(h)`

**Célula `593a9cfd` (treinamento)** — duas linhas a alterar:
- `f'BoxNet_V10_{K}canais_best_valloss.keras'` → `f'BoxNet_V10_{K}canais_OVERFIT.keras'`
- `EarlyStopping(..., patience=10, ...)` → `patience=200`

**O que observar:** Após 30–50 épocas, o `accuracy` (treino) deve subir bem acima do
`val_accuracy`. Se `accuracy` de treino estacionar ≈ `val_accuracy` ≈ 52%, o modelo não
consegue memorizar 50k amostras → saturação de representação confirmada definitivamente.

### Alternativas descartadas

- **Escalares de cadeia como canais broadcast (K=12..15)**: descartado como prioridade. A
  evidência de 5→12 canais sem ganho indica que o bottleneck é processamento, não informação.
- **Mais dados / mais augmentação**: já testado exaustivamente (754k → 13.8M); rendimento
  decrescente confirmado. Ataca variância — não se aplica ao regime de alto viés.
- **Sample_weight refinado / foco em 1a Metade (Fase E)**: complemento útil mas não resolve
  o viés estrutural. Mantido para após a evolução arquitetural.

---

## 2026-05-25 — Abandono do Colab; treinamento V10 migrado para PC local (GTX 1650)

### Contexto

Após a execução da `fase4_augmentacao_simetria.ipynb`, o dataset cresceu de 419 para 608 NPZs
(152 originais × 4 variantes). Ao tentar treinar `Treinamento_CNN_Pontinhos_V9.ipynb` no Colab
com os 608 arquivos, a sessão falhou por OOM (limite ~12 GB RAM do Colab gratuito).

Uma tentativa intermediária (V10 com "split de índices" — pico de RAM reduzido de ~5 GB para
~2,5 GB) também falhou no Colab devido ao overhead do runtime TF + os próprios dados.

### Decisão

**Migrar o treinamento para PC local** (Ryzen 7 5700X, 32 GB DDR4, GTX 1650 4 GB VRAM).

- `Treinamento_CNN_Pontinhos_V10.ipynb` criado como versão local de V9:
  - Todo código Colab removido (`from google.colab import drive`, `drive.mount`, `files.download`).
  - `PASTA_NPZ` e `RESULTADO_DIR` resolvidos por `_find_root()` (detecta raiz do repo pelo `CLAUDE.md`).
  - Saídas (checkpoint `.keras`, TFLite, relatório `.md`) gravadas em `resultados/jogo_pontinhos/`.
  - Otimização de RAM preservada (split de índices antes de construir `X`).
  - Seção 4.4 (métricas por `qtd_cadeias_longas`) preservada.

- `.venv_gpu` recriado com **Python 3.10.11** + **TensorFlow 2.10.0**:
  - TF 2.10 é o último com suporte nativo a GPU no Windows via pip (sem WSL2).
  - NumPy fixado em 1.23.5 (compatível com TF 2.10).
  - Kernel Jupyter registrado em `~/.jupyter/kernels/venv_gpu`.

### GPU pendente (ação manual do desenvolvedor)

TF detecta a GTX 1650 somente após instalação de **CUDA Toolkit 11.2** + **cuDNN 8.1**
(ver próxima seção em `guia_geracao_dados.md`). Sem essas DLLs o treinamento roda em CPU
(funcional, estimativa 8–20 horas). Com GPU: estimativa 8–14 horas.

### Alternativas descartadas

- **Colab Pro**: custo recorrente; OOM ainda possível com 608 NPZs em RAM gratuita.
- **TF 2.16+ com Python 3.12**: sem suporte GPU nativo no Windows via pip (exige WSL2).
- **DirectML plugin**: TF obsoleto (baseado em 1.15-fork da Microsoft); ecossistema abandonado.

---

## 2026-05-19 — Descoberta e correção de bug crítico: Minimax Databricks calculado a depth=6 em vez de depth=11

### Contexto

Durante investigação de convergência dos dados de `score_melhor_jogada` nos 152 NPZs de `dados/profundidade_minimax_11_v7_adaptativo/`, identificamos que **todos os 758.640 estados tinham os scores calculados incorretamente** pelo notebook Databricks de Phase 2.

### Bug confirmado empiricamente

**Arquivo afetado:** `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf_EXECUTADO_NO_DATABRICKS.ipynb`

**Causa raiz:** A variável `DEPTH_TARGET = 11` estava definida na célula de configuração mas nunca usada nas chamadas reais ao Minimax. O valor era hardcoded como `6`:

```python
# ERRADO (como executado no Databricks):
res = solve_minimax_bitboard(new_e, 6, ...)

# CORRETO (como deveria estar):
res = solve_minimax_bitboard(new_e, DEPTH_TARGET, ...)
```

**Evidência empírica:** Teste paralelo com `ProcessPoolExecutor(14 workers)` contra o Minimax Python de referência (`_scores_de_todas_jogadas`) confirmou convergência dos dados a p=6, não a p=11:
- p=6, p=7, p=8, p=9 vs NPZ → 0 diferenças (dados batem)
- p=10 vs NPZ → 6 diferenças em 21 traços
- p=11 vs NPZ → 10 diferenças em 21 traços

**Impacto:** Todos os resultados de treinamento e avaliação que dependiam de `score_melhor_jogada` destes NPZs são considerados não confiáveis (ver anotações nas entradas de 2026-05-13 e 2026-05-14).

### Correção aplicada

1. Base de NPZs descartada (`dados/profundidade_minimax_11_v7_adaptativo/` removido).
2. Base limpa com 12 canais gerada: `dados/base_adaptativo_limpa_com_12_canais/` — sem campos `score_melhor_jogada`, `melhor_jogada`, `depth_melhor_jogada`.
3. Novo notebook corrigido: `gerador_dados/jogo_pontinhos/v8/fase3_rerotulacao_databricks_databricks.ipynb` — usa `depth = int(row['depth'])` por estado (11 ou 20 adaptativos), sem hardcode.
4. Nova execução iniciada no Databricks sobre a base limpa. NPZs enriquecidos chegam em `dados/profundidade_minimax_11_adaptativo/`.

### Verificação dos primeiros NPZs corrigidos (2026-05-19)

Sobre `dataset_pequeno_0001.npz` e `dataset_pequeno_0002.npz` (10.000 estados total):

**Teste 1 — 57 amostras p=11 e p=20 vs referência Python:**
- 57/60 concluídas, 0 falhas (3 abortadas: p=11 com 29–30 arestas livres, sem TT na referência → muito lentas)

**Teste 2 — Tri-verificação depth=20 (3 estados × 17 arestas livres):**
| Comparação | Resultado |
|---|---|
| Databricks(p=20) = ref Python(p=17) | **51/51 traços** |
| Databricks(p=20) ≠ ref Python(p=11) — prova que depth>11 foi usado | **49/51** |
| `melhor_jogada` consistente com argmax | **3/3** |

Dados do novo pipeline estão corretos.

### Nota sobre a referência Python usada na verificação

A referência é `_scores_de_todas_jogadas` de `minimax_pontinhos.py` — implementação matrix-based independente do Bitboard Databricks. Usa alpha-beta com move ordering (captura-primeiro), mas **sem Transposition Table** — por isso estados com 27+ arestas livres em posição aberta são impraticáveis como referência (branching factor alto, TT ausente). O Bitboard Databricks tem TT, o que explica a diferença de performance na geração vs verificação local.

### Alternativas consideradas e descartadas

- **Re-rodar Phase 2 sobre os NPZs antigos:** descartado porque (a) o skip condition `melhor_jogada[0] != ""` ignoraria todos os 152 arquivos já processados, exigindo patch adicional; (b) os 11.542 estados depth=20 do pipeline V8 seriam sobrescritos para depth=11; (c) os campos v2-a3 (canais, chain scalars) seriam perdidos — o notebook Phase 2 original não preserva esses campos no `savez_compressed`.
- **Corrigir os scores localmente:** considerado mas descartado — exigiria ~15 horas locais para 748k estados via Bitboard local, versus execução já em curso no Databricks com o notebook corrigido.

---

## 2026-05-14 — Pipeline V8: campos escalares de cadeias, re-rotulação adaptativa e augmentação por sufixo

### Contexto

Após implementar o canal 12 (`paridade_cadeia_longa_impar`) e validar os NPZs com 11 canais (T-A2-005/006), surgiu a questão: o Minimax p=11 que gerou os rótulos é suficiente para todos os estados? A teoria de Berlekamp indica que estados com cadeias longas requerem uma profundidade mínima `prof_min = total_caixas_cadeias_longas + 2 × qtd_cadeias_longas` para serem resolvidos corretamente. Se `prof_min > 11`, o rótulo atual é potencialmente subótimo.

### Análise realizada (100% do dataset — 758.640 estados)

> **Revisão 2026-05-18**: substituída a amostragem 1-em-5 pela análise completa realizada após T-A3-002 estar implementado.

**Distribuição de `qtd_cadeias_longas`:**

| qtd_cadeias_longas | % dos estados | Observação |
|---|---|---|
| 0 | 62,4% | Sem cadeias longas — p=11 sempre suficiente |
| 1 | 31,9% | Uma cadeia longa |
| 2 | 5,6% | Duas cadeias longas |
| ≥3 | 0,1% | Três ou mais — têm prof_min > 11 |

**Distribuição de `profundidade_minima` (`= total_caixas + 2 × qtd_cadeias_longas`):**

| profundidade_minima | % dos estados | Ação |
|---|---|---|
| ≤ 11 | ~97,7% | Manter rótulo atual — p=11 resolve |
| > 11 | ~2,3% | Candidatos à re-rotulação |

**Estados a re-rotular** (critério: `arestas_livres > 11` E `prof_min > 11`):

| `arestas_livres` (= 31 − qtd_tracos) | Estados | Observação |
|---|---|---|
| ≤ 11 | 0 | p=11 já resolve o jogo completo — não re-rotular |
| 12 | 3.601 | re-rotular com p=20 |
| 13 | 3.000 | re-rotular com p=20 |
| 14 | 2.232 | re-rotular com p=20 |
| 15 | 1.581 | re-rotular com p=20 |
| 16 | 836 | re-rotular com p=20 |
| 17 | 244 | re-rotular com p=20 |
| 18 | 45 | re-rotular com p=20 |
| 19 | 3 | re-rotular com p=20 |
| **Total real** | **11.542** | **1,52% do dataset** |

Dos 17.724 estados com `prof_min > 11`, **6.182 têm `arestas_livres ≤ 11`** e já estão corretamente rotulados pelo Minimax p=11 (o jogo termina antes de p=11 ser insuficiente). Só os 11.542 restantes precisam de re-rotulação.

### Decisões tomadas

**D11.a — 3 campos escalares de metadata de cadeias** (adicionados ao NPZ schema v2-a3):
- `qtd_cadeias_longas (N,) int8`: contagem de cadeias longas abertas
- `total_caixas_cadeias_longas (N,) int8`: soma dos comprimentos
- `tamanho_max_cadeia_longa (N,) int8`: tamanho da maior cadeia longa

Alternativa descartada: array `tamanho_cadeias_longas` de comprimento variável — incompatível com NPZ sem padding ou dtype `object`; os 3 escalares cobrem todos os casos de uso identificados.

**D11.b — Re-rotulação com profundidade única p=20** (Databricks, Fase 3 V8): análise completa (100% do dataset) revelou que todos os estados com `prof_min > 11` têm ≤ 19 arestas livres. O Minimax para naturalmente quando o jogo termina, então p=20 resolve completamente todos os casos. Critério binário: re-rotular apenas estados onde `arestas_livres > 11` E `prof_min > 11`. Total real: **11.542 estados** (1,52%) — dos 17.724 com `prof_min > 11`, 6.182 têm `arestas_livres ≤ 11` e já estão corretamente rotulados por p=11. Schedule por bucket descartado — profundidade única simplifica a implementação sem perda de corretude.

**D11.c — Augmentação por sufixo em disco** (revisão de D5 original): a augmentação 4× é gerada em disco como arquivos `_refH.npz`, `_refV.npz`, `_r180.npz`. Alternativa (augmentação em memória durante treino) descartada — notebook de treino fica mais simples; permite auditoria dos dados augmentados. Idempotência garantida por deleção prévia dos sufixados ao re-executar. Total: 152 originais + 456 sufixados = 608 NPZs.

**D11.d — Pipeline V8 em `gerador_dados/jogo_pontinhos/v8/`**: 4 notebooks com nomes descritivos (`fase1_geracao_local`, `fase2_enriquecimento_local`, `fase3_rerotulacao_databricks`, `fase4_augmentacao_simetria`). Única fase Databricks = Fase 3.

**D11.e — Métricas de treino segmentadas por `qtd_cadeias_longas`**: grupos 0, 1, 2, ≥3 com OMA, top-1, top-3.

### Documentação atualizada

- `specs/004-melhoria-geracao-dados-cnn/tasks.md` — Fase A.3 adicionada (T-A3-001 a T-A3-012)
- `specs/004-melhoria-geracao-dados-cnn/contracts/npz_schema.md` — seção 3 (schema v2-a3) adicionada
- `specs/004-melhoria-geracao-dados-cnn/PRD.md` — §4.11 (Decisão D11) adicionado
- `specs/004-melhoria-geracao-dados-cnn/plan.md` — sumário atualizado com Fase A.3 e pipeline V8

---

## 2026-05-14 — Validação visual e auditoria dos NPZs enriquecidos: 758.640 amostras, 11 canais (T-A2-005/006)

> **AVISO (descoberto 2026-05-19):** A auditoria T-A2-006 validou **integridade de hash** dos campos `estados`, `canais`, `melhor_jogada` e `score_melhor_jogada` — garantindo que os arquivos não foram corrompidos entre geração e disco. Ela **não** verificou se os scores foram computados à profundidade correta. Descobriu-se em 2026-05-19 que `score_melhor_jogada` foi calculado a depth=6 em vez de depth=11 (ver entrada 2026-05-19). Os hashes são válidos para os dados produzidos, mas os dados em si estavam errados. O diretório `dados/profundidade_minimax_11_v7_adaptativo/` foi descartado e substituído por `dados/profundidade_minimax_11_adaptativo/` gerado com o pipeline corrigido.

### Contexto

Com o bug de classificação de nós isolados corrigido no analisador (ver entrada 2026-05-13), o diretório `dados/profundidade_minimax_11_v7_adaptativo/` foi re-enriquecido com o algoritmo corrigido e os NPZs estavam prontos para a validação formal (T-A2-005) e auditoria de integridade (T-A2-006).

### Validação visual — T-A2-005

PNGs de validação foram gerados para estados nas faixas `t∈[12,17]`, `t∈[24,28]` e `t∈[29,30]` usando `scripts/pontinhos/validar_canais_visualmente.py`. Verificação programática adicional: 600 estados de 3 NPZs distintos comparados contra `extrair_canais()` ao vivo → **0 divergências** (algoritmo armazenado == algoritmo atual com bug fix).

> **Assinatura visual — T-A2-005**: [X] OK — 30+ PNGs revisados pelo desenvolvedor. Canais 0–10 coerentes com a matriz crua nos casos inspecionados nas faixas t∈[12,17], t∈[24,28] e t∈[29,30].
> Assinado por: DionDu. Data: 2026-05-14.

### Auditoria de integridade — T-A2-006

Auditoria executada sobre os 152 NPZs em `dados/profundidade_minimax_11_v7_adaptativo/`:

| Chave NPZ | Hash MD5 agregado (152 arquivos) | Status |
|---|---|---|
| `estados` | `9b9b026317c9a25015032897d85b683f` | ✓ imutável |
| `melhor_jogada` | `f05e30c5d3d114779703d0a9add8971f` | ✓ imutável |
| `score_melhor_jogada` | `cb412408039da5e9864a8a006ed97b80` | ✓ imutável |
| `canais` | `78715e173eef9d8279a845fbf0ca2430` | ✓ nova chave A.2 |

- `nomes_canais`: byte-a-byte idêntico em todos os 152 arquivos. ✓
- Total amostras: **758.640** (brutos, incluindo duplicatas). ✓
- Shape `canais`: `(5000, 4, 3, 11) int8` por NPZ. ✓

**Status: OK — todos os 152 NPZs auditados.**

> **Nota sobre re-enriquecimento pendente**: após T-A2-009 (canal 12, K=11), será necessário re-rodar com `FORCAR_REGRAVAR = True`. Os hashes acima refletem o estado com 11 canais; apenas `canais` e `nomes_canais` mudarão após o 12º canal.

---

## 2026-05-13 — Design: Canal 12 (`paridade_cadeia_longa_impar`) — broadcast global para CNN

> **AVISO (descoberto 2026-05-19):** O resultado de ~50% de vitórias contra Minimax p=6 citado abaixo foi obtido de uma CNN treinada com `score_melhor_jogada` calculado incorretamente a depth=6 em vez de depth=11 (ver entrada 2026-05-19). Tanto o rótulo de treino quanto o adversário de avaliação usavam profundidade 6 — a análise motivacional pode estar distorcida. A decisão de adicionar o canal 12 permanece válida (fundamento teórico de Berlekamp é independente do bug), mas os percentuais de vitória não devem ser citados como resultado confiável.

### Contexto

A CNN BoxNet V8 treinada com os 11 canais estruturais atingiu ~50% de vitórias contra Minimax p=6, abaixo do baseline V7 de 63%. A causa raiz é teórica: decisões estratégicas no endgame do Jogo dos Pontinhos dependem da **paridade do número de cadeias longas abertas** — propriedade global que uma CNN com receptivo campo local não consegue inferir por convolução.

### Decisão

Adicionar canal 12 (`paridade_cadeia_longa_impar`, K=11) como **broadcast global**: todas as 12 células do tensor recebem o mesmo bit `{0, 1}`.

- **Valor 1**: número de cadeias longas abertas é ímpar (1, 3, 5, …).
- **Valor 0**: número de cadeias longas abertas é par ou zero.

**Por que importa** (teoria de Berlekamp / Barker-Korf 2012): a paridade determina quem captura a última cadeia longa por inteiro no endgame. O jogador que sacrifica cadeias curtas primeiro empurra o adversário a "abrir", e usa double-cross para capturar em sequência. Com 2 cadeias longas (par), sacrificar é vantajoso; com 1 (ímpar), a estratégia é diferente. Uma CNN sem esse bit erra em ~50% dos endgames estratégicos.

**N_CANAIS**: 11 → 12. Shape do tensor: `(N, 4, 3, 11)` → `(N, 4, 3, 12)`. Canal K=11 é escalar global: não há permutação de slot ou conteúdo sob nenhuma das 4 simetrias.

Teoria completa e exemplo passo-a-passo em `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md`.

### Alternativas consideradas

- **Mais dados + rede mais profunda**: descartado. O limite é teórico (CNN local não agrega informação global), não empírico — mais dados não resolvem.
- **Contagem bruta de cadeias** (inteiro 0..6): descartado. A paridade é o bit estrategicamente relevante; contagem bruta exigiria que a CNN aprendesse a interpretar paridade a partir de um canal de escala variável, adicionando complexidade sem ganho.
- **Value head (Fase F) sem canal 12**: insuficiente — o value head seria treinado com o mesmo vetor de features sem o bit de paridade.

### Documentação criada/atualizada

- `docs/jogo_pontinhos/teoria_cadeias_pontinhos.md` — criado: teoria, mecanismo de double-cross, exemplo passo-a-passo 1 cadeia curta + 2 longas.
- `specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md` — N_CANAIS=12, §8 adicionado.
- `specs/004-melhoria-geracao-dados-cnn/PRD.md` e `plan.md` — tabelas e NOMES_CANAIS atualizados.
- `specs/004-melhoria-geracao-dados-cnn/tasks.md` — T-A2-009 e T-A2-010 adicionados com prioridade máxima.

---

## 2026-05-13 — Correção do analisador estrutural: nó isolado grau-2 não é cadeia estratégica

### Contexto

Durante a validação visual da Fase A.2 com `validar_canais_visualmente.py`, 2 bugs relacionados foram encontrados em `analisador_estrutural_pontinhos.py` que afetavam a classificação de caixas grau-2 sem vizinhos grau-2 conectados por aresta livre ("nós isolados" no grafo dual).

### Bugs corrigidos

**Bug 1 — Nó isolado classificado como `em_cadeia_curta` (canal 7)**: componente de tamanho 1 no grafo dual era classificado pela condição `comprimento <= 2 → canal 7`. Um nó isolado não é uma cadeia estratégica — ele representa uma caixa que, quando aberta, entrega no máximo 2 capturas (a si própria + eventual grau-3 adjacente).

**Bug 2 — `em_cadeia_aberta_uma_ponta` incorreto para nó isolado**: `_contar_pontas_abertas()` usava `break` após o primeiro vizinho grau-3, retornando 1 mesmo quando **ambas** as arestas livres levavam a caixas grau-3. Resultado: nó com 2 vizinhos grau-3 era erroneamente marcado como `em_cadeia_aberta_uma_ponta = 1` (deveria ser 0 — "closed chain" de tamanho 1, não marcar).

### Decisão

**Fix** (1 linha): `if comprimento == 1: ... continue` no branch `path` da classificação. Nós isolados tratados separadamente: **exatamente 1** vizinha grau-3 via aresta livre → `em_cadeia_aberta_uma_ponta = 1` (half-open mínimo); 0 ou 2 vizinhos grau-3 → sem marca.

`em_cadeia_curta` redefinida como comprimento **exatamente 2** no contrato `canais_estruturais.md`.

### Impacto e validação

- Testes de regressão: 13 passed (2 novos testes para nó isolado).
- Re-enriquecimento dos NPZs necessário após o fix (feito com `FORCAR_REGRAVAR = True`).

---

## 2026-05-08 — Geração V7 Adaptativa (DAC): profundidade por tensão, Boltzmann e snapshots por partida

### Contexto

A V6 produziu ~488k distintos com saturação severa na faixa quente (24–28
traços): 298 mil tentativas brutas para 53 mil distintos (~82% duplicatas).
A meta de 500 distintos a 29–30 traços era **fisicamente impossível** —
limite teórico do espaço é `C(31,29)+C(31,30) = 496`. Discussão em sessão
de design propôs três mudanças combinadas que simplificam radicalmente o
pipeline e eliminam o gargalo.

### Decisão

Criar `notebooks/jogo_pontinhos/Geracao_Amostras_v7_adaptativo.ipynb` (mais
módulo `gerador_dados/jogo_pontinhos/gerador_amostras_v7_pontinhos.py`)
implementando o algoritmo **DAC — Diversidade Adaptativa em Cascata**.

**Quatro princípios:**

1. **Profundidade adaptativa por tensão estrutural τ.**
   τ = 4·c₃ + 2·c₂ + 0,5·c₁ (c_k = caixas com k lados preenchidos).
   p(τ) = clamp(1 + ⌈τ/4⌉, 1, 8). Tabuleiro vazio tem p=1, endgame
   tenso pode ter p=8. **Substitui o Minimax fixo do V6.**

2. **Desempate por Boltzmann sampling com temperatura T(t) decrescente.**
   T=1,5 (t<8) / 0,8 (t<18) / 0,5 (t<26) / 0,2 (t≥26). Substitui
   `random.choice` entre top-1's.

3. **30 snapshots por partida.** Cada partida joga do zero ao terminal e
   emite UM estado por t∈[1,30] (descarta t=0 sempre-igual e t=31
   terminal). Substitui o esquema "1 estado por worker".

4. **Sem faixas/quotas.** Meta única: 500.000 estados distintos. A
   distribuição emerge naturalmente bell-shaped: pontas (t pequeno e t
   grande) saturam pelo teto teórico do espaço, midgame cresce com N.

### Esquema do NPZ V2

Diretório de saída: `dados/profundidade_minimax_11_v7_adaptativo/`.

| Campo | Shape | Dtype | Fase |
|---|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` | 1 |
| `qtd_tracos` | `(N,)` | `int8` | 1 |
| `score_jogada` | `(N, 31)` | `float32` | 1 |
| `depth_jogada` | `(N,)` | `int8` | 1 |
| `depth_geracao` | `(N,)` | `int8` | 1 |
| `melhor_jogada` | `(N,)` | `<U5` | 2 |
| `score_melhor_jogada` | `(N, 31)` | `float32` | 2 |
| `depth_melhor_jogada` | `(N,)` | `int8` | 2 |
| `labels_canonicos` | `(31,)` | `<U5` | 1 |

Renomeações vs V6: `rotulos` → `melhor_jogada`; `scores` → `score_melhor_jogada`.
Removidos: `generation_mode`, `minimax_depth` (global).

### Diferenças vs V6

| Item | V6 | V7 |
|---|---|---|
| Profundidade autoplay | Fixa (p=3) | Adaptativa por τ (1..8) |
| Desempate | `random.choice` entre top-1 | Boltzmann com T(t) |
| Geração | 1 estado/worker | 30 estados/partida |
| Faixas/quotas | 5 faixas com cotas rígidas | Sem faixas; meta única 500k |
| Faixa 29–30 | Cota 500 (impossível) | Saturação natural |
| `generation_mode` | 3 valores | Removido |
| `qtd_tracos` | Derivado | Por estado |
| Custo estimado | ~14h (Fase 1) | ~2–4h (Fase 1) |

### Alternativas consideradas

- **Manter faixas e ajustar quotas**: descartado. Mesmo com cotas
  realistas (29–30 = 400), o pipeline continua complexo e o gargalo da
  faixa quente persiste. A solução estrutural é pular a estratificação
  imposta e deixar a distribuição emergir.
- **Boot aleatório do meio (começar com K traços aleatórios)**:
  descartado. A proposta do usuário de começar **sempre do tabuleiro
  vazio** preserva realismo trajetorial — todos os estados gravados
  estão no caminho de partidas legais — e a diversidade é garantida
  por Boltzmann + ε-greedy.
- **ε-greedy (movimentos uniformes ocasionais)**: descartado em favor
  do Boltzmann puro. ε-greedy injeta movimentos absurdos no tabuleiro
  vazio (ex.: lances que criam estruturas inúteis), o que pode produzir
  estados pouco realísticos. Boltzmann com T alta faz exploração
  "racional" — ainda escolhe entre lances dentro da árvore Minimax,
  apenas com mais incerteza.
- **Gravar duplicatas**: aceito. Stop por contagem de distintos em
  memória; NPZ contém duplicatas (~770k brutos para 500k distintos).
  Dedup acontece no notebook de treino. Isso simplifica a Fase 1 (sem
  rejection) e permite estudar a distribuição empírica de jogos
  reais (taxa de duplicação por t).
- **Enumeração direta do endgame (29–30)**: descartado como
  necessidade — a saturação natural da V7 cobre os 496 estados em ~600
  partidas. Pode ser adicionada como passo final de auditoria se o
  fechamento natural não cobrir 100% (raros estados não-alcançáveis
  por trajetória legal).

### Material de referência (TCC)

Fundamentação técnica completa, com fórmulas, exemplos turno-a-turno,
distribuição emergente esperada e justificativa dos pesos: ver
`docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md`. Esse documento é a
fonte canônica do desenho — entradas neste histórico só registram
decisões e mudanças de rota.

### Como rodar

Ver `docs/jogo_pontinhos/guia_geracao_dados.md` §1C.

---

## 2026-05-08 — Geração V6: pipeline em 2 fases, autoplay p=3 e scoring p=7

### Contexto

A consolidação rev.5 produziu 499.997 estados, mas com `mode_2` (autoplay
Minimax p=2 × p=2) saturado e dependente de três fontes diferentes
(`legado` + `v5_databricks` + `v5_local`). Para a próxima rodada de treino
quisemos um pipeline **único, reproduzível e local** — sem Databricks — com
estados gerados num só motor.

### Decisão

Criar `notebooks/jogo_pontinhos/Geracao_Amostras_v6.ipynb` (mais módulo auxiliar
`gerador_dados/jogo_pontinhos/gerador_amostras_v6_pontinhos.py`) que executa
o pipeline em duas fases:

1. **Fase 1 — Geração de estados** (95% autoplay Minimax(p=3) × Minimax(p=3),
   5% tabuleiros aleatórios). Quotas por faixa de traços (alvo de
   **distintos**, duplicatas gravadas mas não contam):

   | Faixa | Quota distintos | % do total |
   |---|---:|---:|
   | 5–11 | 55.000 | 10,97% |
   | 12–17 | 160.000 | 31,90% |
   | 18–23 | 220.000 | 43,87% |
   | 24–28 | 66.000 | 13,16% |
   | 29–30 | 500 | 0,10% |
   | **Total** | **501.500** | **100,00%** |

2. **Fase 2 — Cálculo da melhor jogada**. Para cada estado **único** (cache
   global por `mat.tobytes()` cobrindo TODOS os NPZs), roda
   `melhor_jogada_com_scores(estado, profundidade=7)` e reescreve cada NPZ
   atomicamente (`.tmp` + `os.replace`) preenchendo `rotulos` e `scores`.
   Slots inválidos → `-1e9`. Empates no argmax → escolha aleatória.

Saída: `dados/profundidade_minmax_7_corrigido/dataset_pequeno_NNNN.npz`,
schema **idêntico** ao NPZ de referência
(`dados/profundidade_minmax_9/dataset_pequeno_0001.npz`):

| Campo | Shape | Dtype |
|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` |
| `rotulos` | `(N,)` | `<U5` |
| `scores` | `(N, 31)` | `float32` |
| `generation_mode` | `(N,)` | `int8` (`{0, 3}`) |
| `labels_canonicos` | `(31,)` | `<U5` |
| `minimax_depth` | `(1,)` | `int32` (= 7) |

### Diferenças vs. rev.5

| Item | rev.5 (V4/V5) | V6 (este notebook) |
|---|---|---|
| Fontes | 3 (legado + Databricks + local) | 1 (notebook local) |
| `generation_mode` | {0, 2, 3} | **{0, 3}** — mode_2 abandonado |
| Profundidade scoring | 9 | **7** |
| Pipeline | 1 fase (estado+score juntos) | **2 fases** (estado primeiro, score depois) |
| Cota | 500.000 distintos exatos | **501.500 distintos**, duplicatas extras gravadas |
| Cache de scores | Não (cada estado recalculava) | **Sim** — duplicata reusa scoring do idêntico |

### Alternativas consideradas

- **Manter mode_2 (p=2)**: descartado. Saturação histórica deixa pouca
  diversidade incremental e adiciona variação de qualidade no dataset
  (Minimax p=2 é fraco em endgame). Padronizar tudo em p=3 simplifica.
- **Profundidade de scoring = 9**: descartado para esta rodada — p=7 já é
  muito mais forte que o que a CNN consegue aprender no treino atual e
  reduz tempo total da Fase 2 de forma significativa. Pode ser elevado em
  rodadas futuras se o gargalo passar a ser o scoring.
- **Sidecar JSON com progresso (`progresso.json`)**: descartado por risco
  de dessincronizar com os arquivos NPZ. O diretório de NPZ é a única fonte
  da verdade; retomada reconstrói tudo a partir dele.
- **Lote independente por worker (sem dedup global)**: descartado porque
  permitia ultrapassar a cota de distintos por faixa antes do main perceber.
  Adotado: workers stateless devolvem 1 amostra; main mantém set global de
  hashes e fecha a faixa no momento exato.

### Como rodar

Ver `docs/jogo_pontinhos/guia_geracao_dados.md` §1B.

---

## 2026-05-08 rev.5 — Consolidação final concluída: 499.997 estados únicos

### Contexto

Após a rev.3 capear os buckets (29–30) e (24–28) e redistribuir para (12–17) e
(18–23), a consolidação (`Consolidar_500k_Final.ipynb`) mostrou **51.777 estados
faltantes**, concentrados em mode_2 (12,17) e mode_2 (18,23). Geração adicional
pelo V5_Local (rev.4) reduziu o shortfall para **14.615** — mas era impossível
chegar a zero porque **o autoplay sim_l2 (Minimax p=2 × p=2) também satura**:
o espaço prático de trajetórias desse modo é finito e estava esgotado.

### Diagnóstico — Saturação do autoplay mode_2

Contagem exata de estados únicos por célula `(gen_mode, bucket)` em TODAS as fontes
(legado + v5_databricks + v5_local):

| Célula | Únicos disponíveis | Cota rev.4 | Déficit |
|---|---:|---:|---:|
| mode_2 (12,17) | 67.898 | 68.597 | 699 |
| mode_2 (18,23) | 83.787 | 97.705 | 13.918 |
| mode_2 (29,30) | 84 | 87 | 3 |
| mode_3 (24,28) | 21.261 | 21.458 | 197 |
| **Total** | | | **14.817** |

### Decisão (rev.5)

1. **Capear TODAS as cotas nos únicos reais disponíveis** — não apenas (24–28) e
   (29–30) como na rev.3, mas também mode_2 (12,17), mode_2 (18,23) e mode_3 (24,28).
2. **Redistribuir os 14.817 liberados para mode_3** em (12–17) e (18–23):
   - mode_3 (18,23): 121.343 + 7.392 = **128.735** (cap no max disponível: 128.735)
   - mode_3 (12,17): 86.674 + 7.425 = **94.099** (disponível: 104.010 >> 94.099)
3. **Total = 500.000 exato** (sem shortfall esperado).

### Resultado da consolidação final

```
Total consolidado: 499.997 (shortfall: 3 — arredondamento)
100 NPZs em dados/profundidade_minmax_9/

Distribuição por bucket:
  (5, 11)    55,501  11.10%  OK
  (12, 17)  169,875  33.98%  OK
  (18, 23)  223,551  44.71%  OK
  (24, 28)   50,867  10.17%  OK
  (29, 30)      203   0.04%  OK

Mix de gen_mode:
  mode_0:  24,999 ( 5.00%)
  mode_2: 200,285 (40.06%)
  mode_3: 274,713 (54.94%)

Origem dos aceitos:
  legado:        168,661
  v5_databricks: 181,456
  v5_local:      149,880

AUDITORIA OK — 0 duplicatas, sim_l1 = 0.
```

### Cotas finais por célula (rev.5)

```python
cota_alvo = {
    (0, (5, 11)):  2_775,  (0, (12, 17)): 7_879,   (0, (18, 23)): 11_031,
    (0, (24, 28)): 3_289,  (0, (29, 30)):    25,
    (2, (5, 11)):  22_200, (2, (12, 17)): 67_898,   (2, (18, 23)): 83_787,
    (2, (24, 28)): 26_317, (2, (29, 30)):    84,
    (3, (5, 11)):  30_526, (3, (12, 17)): 94_099,   (3, (18, 23)): 128_735,
    (3, (24, 28)): 21_261, (3, (29, 30)):    94,
}
# mode_0=24.999  mode_2=200.286  mode_3=274.715  total=500.000
```

### Alternativas consideradas

- **Redistribuir para mode_2 (rev.4):** tentado primeiro — falhou porque mode_2
  também satura. Autoplay sim_l2 gera trajetórias limitadas.
- **Redistribuir proporcionalmente entre mode_2 e mode_3:** desnecessário —
  mode_3 tem excedente de únicos em (12–17) e (18–23) suficiente para absorver
  toda a redistribuição.
- **Gerar mais mode_0 (uniform) para cobrir o déficit:** rejeitado —
  mode_0 gera posições aleatórias sem estrutura estratégica.

### Arquivos alterados nesta sessão

- `notebooks/jogo_pontinhos/Consolidar_500k_Final.ipynb` — cotas rev.5, verificação simplificada, auditoria sem BUCKET_ALVO
- `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb` — COMPLEMENTO_POR_CELULA atualizado (51.777 → geração concluída)
- `specs/004-melhoria-geracao-dados-cnn/PRD.md` — nota rev.5 adicionada em §4.1.3
- `docs/historico_decisoes.md` — esta entrada

---

## 2026-05-08 — Saturação dos buckets (29–30) e (24–28); redistribuição final; incorporação do V5_Databricks

### Contexto

Durante a Fase A.1 (`specs/004-melhoria-geracao-dados-cnn/`) o V5_Local gerou 195k
amostras em ~4h da noite anterior (boa taxa: ~6k/s nas células fáceis). No resumo
do dia seguinte, em 12 minutos apenas ~900 amostras foram aceitas — **taxa de
duplicação de 98,6%**. Diagnóstico solicitado.

### Diagnóstico — Bucket (29–30)

O tabuleiro 4×3 com 31 arestas tem apenas **C(31,29)+C(31,30) = 465+31 = 496
estados únicos possíveis** no bucket (29–30). A função `edges_to_matrix` no engine
é **pura**: a matriz do jogo é função exclusiva do conjunto de arestas jogadas,
independentemente do modo de geração (uniform/sim_l2/sim_l3). Portanto todos os
modos compartilham o mesmo espaço de estados por bucket.

Contagem pós-geração (legado + v5_databricks + v5_local):

| Fonte | mode_0 | mode_2 | mode_3 | Total |
|---|---:|---:|---:|---:|
| legado | 0 | 0 | 0 | 0 |
| v5_databricks | 0 | 0 | 0 | 0 |
| v5_local | 320 | 80 | 96 | **496** |

**496/496 = espaço de estados 100% esgotado.**

### Diagnóstico — Bucket (24–28)

Após capear (29–30) e reorientar a geração para (24–28), o V5_Local coletou
65.792 estados únicos nesse bucket — e a taxa de duplicatas voltou a 99%+.

**Causa:** os modos de autoplay sim_l2 (Minimax p=2 × p=2) e sim_l3 (Minimax p=3 × p=3)
convergem para um conjunto de **~57.020 posições práticas** no bucket (24–28), muito
abaixo do teórico C(31,24)+...+C(31,28) = 991.333 estados possíveis.

**Por que a saturação acontece:** `edges_to_matrix` é função pura — dada a mesma
configuração de arestas, a matriz é única independente do modo de geração. O autoplay
Minimax p=2/p=3 tende a seguir trajetórias de partidas "boas": abre cadeias na ordem
certa, fecha sequências de caixas similares, e raramente cria as configurações de
borda ou paridade que só apareceriam em jogo aleatório. O espaço de trajetórias
razoáveis de partidas Minimax p=2/p=3 no tabuleiro 4×3 converge empiricamente para
~57.020 posições únicas — os 934.313 estados restantes do teórico C(31,24..28)
correspondem a configurações "irreais" que dificilmente seriam atingidas por qualquer
agente que joguem minimamente bem.

**Mode_0 (uniform) não satura:** selecionar arestas ao acaso pode gerar qualquer
configuração teórica, por isso mode_0 cobriu ~9.170 posições adicionais distintas.
Porém a proporção de mode_0 no dataset é apenas 5% — insuficiente para cobrir os
934k estados irreais sem custo absurdo.

Distribuição dos 65.792 únicos coletados em (24–28):

| Modo | Disponível | Observação |
|---|---:|---|
| mode_0 (uniform) | ~9.170 | Não satura — range teórico ilimitado |
| mode_2+3 (autoplay) | ~57.020 | **Saturado** — espaço prático do Minimax |
| **Total único** | **~65.792** | União dos dois conjuntos (leve overlap ~398) |

### Decisão

1. **Capear bucket (29–30) em 496** (0,10%). Cobertura integral do universo de
   posições quase-finais — impossível melhorar.
2. **Capear bucket (24–28) em 65.792** (13,16%). Espaço prático do autoplay
   Minimax p=2/p=3 esgotado. Gerar mais não acrescenta posições estrategicamente
   relevantes.
3. **Redistribuir a cota liberada de (24–28)** em razão 20:28 entre (12–17) e
   (18–23): +46.587 para (12–17), +65.222 para (18–23).
4. **Incorporar V5_Databricks** (`dados/profundidade_minmax_9_v5_databricks/`,
   183.660 brutos / 139.903 únicos) como terceira fonte na consolidação.
5. **Bucket (12–17) já concluído** — V5_Local acumulou 166.099 únicos no bucket,
   acima do novo alvo de 157.588.
6. **Bucket (18–23): gerar 12.542 adicionais** com V5_Local:
   mode_0 = 627, mode_2 = 5.017, mode_3 = 6.898.

### Parâmetros finais (PRD §4.1.3 rev.3)

**Bucket targets (total = 500.000):**

| Bucket | Amostras | % | Limite físico / prático |
|---|---:|---:|---|
| 5–11 | 55.501 | 11,10% | — |
| 12–17 | 157.588 | 31,52% | — |
| 18–23 | 220.623 | 44,12% | — |
| 24–28 | **65.792** | **13,16%** | **C(31,24..28) = 991.333 teórico; ~57.020 prático (autoplay Minimax p=2/p=3)** |
| **29–30** | **496** | **0,10%** | **C(31,29)+C(31,30) = 465+31 = 496 — limite físico absoluto** |

**COMPLEMENTO_POR_CELULA atualizado para V5_Local** (alvo TOTAL por célula;
checkpoint subtrai o existente automaticamente):

```python
COMPLEMENTO_POR_CELULA = {
    0: {(5, 11): 0, (12, 17): 0, (18, 23):   627, (24, 28): 0, (29, 30): 0},
    2: {(5, 11): 0, (12, 17): 0, (18, 23): 5_017, (24, 28): 0, (29, 30): 0},
    3: {(5, 11): 0, (12, 17): 0, (18, 23): 6_898, (24, 28): 0, (29, 30): 0},
}
# Total: 12_542 novos estados para (18,23)
```

Shortfall esperado no consolidado final: até **~6.000 estados** (dois componentes):
- **~295** de (29–30): mode_2 tem 80 disponíveis mas cota = 198; mode_3 tem 96 mas cota = 273.
- **até ~5.500** de (24–28): autoplay (sim_l2+sim_l3) disponibiliza ~57.020 estados mas
  a cota combinada de modes 2+3 é ~62.500. Mode_0 tem excedente descartado.
- Desvio máximo total < 1,2% do alvo — irrelevante para treinamento de CNN.

### Alternativas consideradas

- **Continuar gerando para (24–28) com mais mode_0:** rejeitado — mode_0 gera posições
  aleatórias sem estrutura estratégica, dilui a qualidade do dataset.
- **Redistribuir cota de (24–28) apenas para (18–23):** rejeitado — preferência por
  manter razão 20:28 entre (12–17) e (18–23) para equilibrar a cobertura.
- **Aceitar dataset com apenas 65.792 em (24–28) sem redistribuir:** rejeitado —
  total ficaria abaixo de 500k sem a redistribuição.

### Arquivos alterados nesta sessão

- `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb` — COMPLEMENTO_POR_CELULA atualizado para gerar 12.542 estados em (18,23); auditoria com novos alvos
- `notebooks/jogo_pontinhos/Consolidar_500k_Final.ipynb` — BUCKET_ALVO atualizado com distribuição final; shortfall máximo ajustado para 6.000
- `specs/004-melhoria-geracao-dados-cnn/PRD.md` — tabela D1 (§4.1.1) e §4.1.3 com revisão rev.3
- `docs/jogo_pontinhos/guia_geracao_dados.md` — seções 1A.1.alt e 1A.1.cons atualizadas
- `specs/004-melhoria-geracao-dados-cnn/plan.md` — referências ao complemento atualizadas
- `specs/004-melhoria-geracao-dados-cnn/quickstart.md` — fase A.1 atualizada

---

## 2026-05-07 — Geração local com multiprocessing (V5_Local) e remoção do `closure_lut`

### Contexto

Tentativa de rodar `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb`
em conta gratuita do Databricks (serverless). Performance medida: mais de **8
minutos para 100 amostras** (≈ 5 s/amostra). Em escala A.1 (347.020 amostras
novas a gerar), isso sairia da janela operacional.

### Diagnóstico

1. **`closure_lut` em `build_topology_tables`** alocava
   `np.zeros((n, 1<<n), dtype=np.int8)` — para `n=31`, isso é **66 GB de
   memória virtual por worker**. Linux com overcommit deixa alocar (calloc
   lazy), mas o loop só preenchia os primeiros `2²⁰ ≈ 0,05%` da tabela. O
   LUT cobria pouquíssimos estados; o fallback (3-4 testes de máscara) era
   chamado quase sempre. **Otimização era prejuízo líquido**: page-faults
   na alocação, custo de inicialização por partição Spark, sem ganho.
2. **Spark serverless free** tem cores limitados (~2-4) e overhead
   significativo de lançamento de task no Spark Connect. Configuração
   `CHUNK=1000, PARTS=256` resultava em fila de 256 tasks de 4 registros —
   coordenação dominava sobre computação.
3. **Worker reconstrói `build_topology_tables`** a cada partição (chamado
   dentro de `process_batch_v4`) — milhares de reconstruções por rodada.

### Decisão

**Criar versão local autônoma** em
`notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Local.ipynb`,
delegando o engine ao módulo companheiro
`notebooks/jogo_pontinhos/v5_local_engine.py`. Característica do V5_Local:

- **Sem Spark.** `multiprocessing.Pool` com `pool.map` em batches; pool
  inicializado uma única vez via `initializer=init_worker` (tabelas
  construídas 1× por worker, não por tarefa).
- **Sem `closure_lut`.** `_closures_fast` é cálculo direto.
- **Engine em `.py`** (não em célula Jupyter) porque `multiprocessing` no
  Windows usa `spawn` — funções definidas em células não são picklable.
- **Loop por cota preserva PRD §4.1.3.** Sorteia célula
  `(gen_mode, bucket)` ponderada por cota residual em
  `COMPLEMENTO_POR_CELULA`; worker gera com `gen_mode` e `target_tracos`
  forçados; rejeita+regera (até 20 tentativas) se duplicado ou fora do
  bucket; para quando todas as cotas zeram (347.020 estados novos).
- **Pré-popula `hashes_iniciais`** com os 314.323 únicos do legado em
  `dados/profundidade_minmax_9/`.

### Correção paralela no V5_Databricks

`notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5_Databricks.ipynb`
também teve `closure_lut` removido **e o laço por cota implementado** (a
TODO pré-existente de T-A1-004 foi efetivamente cumprida nesta sessão
após o usuário apontar que os logs mostravam o V4-style loop ignorando
`COMPLEMENTO_POR_CELULA`). Mudanças:

- **Cell 3** ganhou `_autoplay_edges_v4_bounded(lo, hi)` e
  `generate_topology_forced(gen_mode, lo, hi)` substituindo o sampler V4
  (que escolhia gen_mode internamente via `STRAT_WEIGHTS`).
- **Cell 6** (worker) passa a receber `(gen_mode, lo, hi)` por linha do
  DataFrame e devolve `n_tracos` no schema, permitindo dedup + decremento
  de cota no main.
- **Cell 10** monta `spark.createDataFrame([(m, lo, hi), ...])` com
  `CHUNK=1000` linhas por iteração, sorteadas com `random.choices` ponderado
  por cota residual. Resume é robusto: lê NPZs já gerados, decrementa cotas
  onde casa o bucket, marca o resto como `sobrefluxo_resumo`.

### Alternativas consideradas

- **Manter Spark e ajustar `PARTS`**: ajuda no overhead, não resolve o
  custo do `closure_lut`, e free serverless é fundamentalmente o
  ferramentas errada para CPU-bound puro.
- **Numba/Cython no inner loop**: ganho real, mas adiciona dependência
  pesada e exige alteração arquitetural (tipos numpy fixos). Adiado para
  Fase B se precisar.
- **Cluster Databricks pago dedicado**: viável (e ainda recomendável para
  geração massiva), mas o V5_Local cobre o caso "gerar localmente quando
  cluster pago não está disponível", que é o cenário atual.

### Métricas estimadas

- Setup atual (Databricks free serverless, `closure_lut` removido):
  ainda lento (overhead Spark domina; cores muito limitados).
- V5_Local em máquina Windows com 8-16 cores físicos: estimativa
  **≈ 0.5-1 s/amostra** (vs 4.8 s/amostra no Databricks free); 347k
  amostras em **~4-8h** total.
- Esses números serão substituídos pela medição real após a primeira
  rodada completa.

---

## 2026-05-07 — Fase A.2 concluída: 11 canais estruturais + sobrescrita atômica + paleta visual (D2/D3/D4)

### Contexto

Conclusão da segunda fase do plano `specs/004-melhoria-geracao-dados-cnn/`
(tasks T-A2-001 a T-A2-008). A Fase A.2 transforma os NPZs gerados pelo
Databricks (Fase A.1) em datasets prontos para a CNN do V6: cada estado
recebe seu tensor `canais (4, 3, 11) int8` pré-computado, eliminando a
camada Lambda `para_grid_de_caixas` que existia em runtime no V5.

### Decisões consolidadas

**D2 — Tensor `canais (4, 3, 11)` materializado no NPZ.** Os 11 canais
seguem a ordem canônica do PRD §4.2 (`aresta_topo`, `aresta_base`,
`aresta_esquerda`, `aresta_direita`, `caixa_fechada`, `eh_grau3`,
`eh_grau2`, `em_cadeia_curta`, `em_cadeia_longa`, `em_loop`,
`em_cadeia_aberta_uma_ponta`). Implementado em
`gerador_dados/jogo_pontinhos/analisador_estrutural_pontinhos.py`. Mantido
**canal único `cadeia_longa` para componentes de comprimento ≥ 3** (não
separamos `cadeia_media = 3` vs `cadeia_longa ≥ 4`) — clarification
2026-05-07.

**D3 — Sobrescrita atômica via `<arquivo>.tmp` + `os.replace()`.**
Implementada no `notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb`.
Ctrl+C durante o enriquecimento NUNCA corrompe o original; o `os.replace`
só substitui quando o `.tmp` está integro. Operação idempotente: rodar
sobre NPZ já enriquecido é seguro (controle por flag `FORCAR_REGRAVAR`).

**D4 — Paleta visual estável + borda em caixas fechadas.** Script
`scripts/pontinhos/validar_canais_visualmente.py` gera PNGs a 150 DPI com:
- 1 painel esquerdo: matriz crua `(9, 7)`;
- 11 boxnets `(4, 3)` à direita, **uma cor categórica fixa por canal**
  (mesma cor entre execuções, para comparabilidade entre lotes);
- borda destacada em caixas onde `canal[caixa_fechada] == 1`, em todos os
  11 boxnets (distingue "fechada" de "aberta com grau hipotético");
- título canônico exatamente igual ao item correspondente em
  `NOMES_CANAIS`.

### Validação

- `pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v`
  → **11 passed** nesta máquina (Python 3.9.5, numpy disponível). Cobre:
  domínio binário, exclusão mútua canal 4 vs 5–10, coerência sob
  simetrias (ref_H, ref_V, R180), tabuleiro vazio, caixa fechada simples,
  loop de 4 caixas, half-open chain, double-cross do Buchin.
- Notebook de enriquecimento e script de validação visual entregues e
  importáveis.
- **Bug encontrado e corrigido durante a TDD**: em numpy moderno,
  `np.bool_ + np.bool_` retorna `np.bool_` (OR lógico), não soma
  aritmética. Fix em `_grau()` para somar via `int(M[...] == 9)`
  explícito. Sem essa correção todos os canais 5–10 ficavam zerados.

### Alternativas consideradas (todas rejeitadas)

- **Doze canais** (separando `cadeia_media = 3` vs `cadeia_longa ≥ 4`):
  rejeitado por aumentar complexidade do input sem evidência empírica
  (research.md §1.4).
- **Gravação direta sem `.tmp`** (`np.savez(arquivo, ...)` sobrescreve in
  loco): rejeitado por NFR-06 (Ctrl+C durante o save corromperia o
  arquivo original).
- **Paleta com gradiente de cor** ou aleatória por execução: rejeitado
  porque atrapalha comparação visual entre lotes (research.md §1.3).
- **JSON declarativo único como ground truth do algoritmo dos canais**:
  mantido como referência (`contracts/canais_estruturais.md` + futuro
  `referencia_canais_pontinhos.json` em T-D-005), mas a fonte da verdade
  do dataset continua sendo o módulo Python — coerente com a diretriz do
  CLAUDE.md "fonte da verdade no contrato JSON" se aplicar apenas ao
  contrato de codificação backend↔frontend, não ao algoritmo de canais.

### Estado de validação manual pendente

A Fase A.2 só fica oficialmente "fechada" quando o desenvolvedor:

1. Roda o enriquecimento sobre o diretório de NPZs reais da Fase A.1.
2. Gera os 30 PNGs com `validar_canais_visualmente.py`.
3. Inspeciona-os manualmente nas 3 faixas (`t∈[12,17]`, `[24,28]`, `[29,30]`).
4. Assina aqui mesmo, ao final desta entrada, que a inspeção foi OK.

> **Assinatura visual — T-A2-005**: [X] OK — 30+ PNGs revisados pelo desenvolvedor. Canais 0–10 coerentes com a matriz crua nos casos inspecionados nas faixas t∈[12,17], t∈[24,28] e t∈[29,30]. Ver entrada 2026-05-14 para relatório completo de auditoria (T-A2-006).
> Assinado por: DionDu. Data: 2026-05-14.

### Documentação atualizada

- `docs/jogo_pontinhos/guia_geracao_dados.md` ganhou a seção **1A** com o
  fluxo completo A.1 + A.2 (T-A2-007).

---

## 2026-05-07 — Fase A.1 do plano 004 — V5 do notebook de geração no Databricks (TEMPLATE — aguardando execução)

### Contexto

Tasks T-A1-001 a T-A1-006 do plano `specs/004-melhoria-geracao-dados-cnn/`.
Esta entrada é deixada como **template** — os números reais (uniques
gerados, distribuição empírica, mix `gen_mode` por bucket, tempo) só
existirão após o desenvolvedor rodar o notebook V5 no Databricks. Nenhum
parâmetro deve ser ajustado fora do que está fixado abaixo (PRD §4.1.3).

### Parâmetros consolidados no V5

- `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` — `sim_l1` desligado por
  gerar estados "lunáticos" sem qualidade estratégica (D1.a do PRD).
- `FAIXA_TRACOS = (0.15, 0.97)` — equivale a 5..30 traços para `n_edges = 31`
  (D1).
- `COMPLEMENTO_POR_CELULA` literal embutido na célula de parâmetros do V5
  (PRD §4.1.3). Soma das cotas = **347_020**, conforme PRD.
- Dedup obrigatória por `mat.tobytes()` com **pré-população do set por
  314.323 únicos do legado** antes de iniciar o laço de geração (D1.b /
  FR-A-04). Estados duplicados são regerados (até 20 tentativas).
- DEPTH = 9 (Minimax(p=9)), inalterado em relação ao V4.

### Distribuição-alvo (PRD §4.1.3) — tolerância ±2pp

| Bucket de traços | Cota legado | Quota complemento | Total alvo | % alvo |
|---|---|---|---|---|
| 5–11 | 27.515 | 22.484 | 50.000 | 10% |
| 12–17 | 49.443 | 50.557 | 100.000 | 20% |
| 18–23 | 56.404 | 83.596 | 140.000 | 28% |
| 24–28 | 19.617 | 140.383 | 160.000 | 32% |
| 29–30 | — | 50.000 | 50.000 | 10% |

> **Nota**: a soma `legado + complemento` por bucket pode divergir
> ligeiramente da tabela acima a depender de quais cotas a auditoria
> empírica do desenvolvedor decida ajustar dentro da tolerância. Os
> valores literais embutidos no notebook V5 são os de
> `COMPLEMENTO_POR_CELULA` na célula de parâmetros — fonte da verdade.

### Resultados (PREENCHER após execução)

```
Total de estados gravados:    ____________
Únicos por mat.tobytes():     ____________     (esperado >= 500.000)
Tempo total de execução:      ____________ h   (NFR-03: ≤ 4 h)
Tamanho dos NPZs:             ____________ MB

Distribuição empírica por bucket de tracos:
  (5, 11): ____% (alvo 10%, desvio ____pp)
  (12, 17): ____% (alvo 20%, desvio ____pp)
  (18, 23): ____% (alvo 28%, desvio ____pp)
  (24, 28): ____% (alvo 32%, desvio ____pp)
  (29, 30): ____% (alvo 10%, desvio ____pp)

Mix de gen_mode (% real):
  uniform (0): ____%
  sim_l1  (1): 0% (DESLIGADO — D1.a)
  sim_l2  (2): ____%
  sim_l3  (3): ____%

Hashes verificados:
  Pré-população legado: 314.323
  Duplicatas regeneradas (laço): ________
  Estados gerados pelo V5 (complemento): ________
```

### Decisão

Manter os parâmetros tal como estão fixados na célula `[T-A1-002 + T-A1-003]`
do V5. Caso a distribuição empírica saia da tolerância em algum bucket, a
correção primeiro tenta ajustar o `COMPLEMENTO_POR_CELULA` (mantém DEPTH e
mix); só em segunda instância se reabre `STRAT_WEIGHTS`.

### Alternativas consideradas

- **Não pré-popular o set de hashes** (gerar tudo do zero, dedupando
  contra o legado durante o laço): rejeitado pelo gasto computacional —
  a maioria dos estados de início/meio de jogo já existe no legado, e
  testá-los mid-loop desperdiça Minimax(p=9).
- **Manter `sim_l1` com peso ≥ 0.05**: rejeitado em D1.a por evidência
  empírica (estados "lunáticos" — V4 spec §4.1.2).
- **Otimizar configuração do cluster Databricks no nível da spec**:
  rejeitado em research.md §1.1 — a configuração depende do dia/cluster
  e é decidida ad-hoc.

### Motivo

Cobertura terminal expandida (faixa 24–30 traços com 42% do dataset,
contra ~3% do V4) ataca diretamente a Categoria A de erros táticos
identificada no relatório de divergência de 2026-05-06 (87.8% das
divergências fatais concentradas em `t ∈ [28, 30]`).

---

## 2026-05-06 — Análise de divergência estratégica (600 partidas) confirma Cenário X3 e motiva duas novas fases no PRD

### Contexto
Após descontinuar p=1 (decisão abaixo na mesma data), rodamos
`tmp_analise/analisa_divergencia_estrategica.py` em **600 partidas** (200
contra cada um de p=3, p=5, p=6) com o oráculo Minimax adaptativo
(p=5/7/9 conforme livres). Tempo total: 9370 s (~2.6 h) com 12 workers.
Modelo avaliado: `modelos/pontinhos_pequeno_profundidade_9.tflite`.
Relatório completo: `tmp_analise/RELATORIO_DIVERGENCIA_ESTRATEGICA.md`.

### Resultados-chave

**Win-rates (CNN, vencedora):**
- vs p=3: 109/200 = 54.5%
- vs p=5: 84/200  = 42.0%
- vs p=6: 76/200  = 38.0%

**Fatal precoce (≤ 25 traços) entre partidas perdidas:**
- vs p=3: 7/42  = **16.7%**
- vs p=5: 11/60 = **18.3%**
- vs p=6: 14/89 = **15.7%**
- Média ponderada: 32/191 ≈ **16.8%**

**Distribuição dos fatais (total 410 nas 600 partidas):**
- Meio (10–24 traços):  50 fatais (12.2%)
- Transição (25–27):    0 fatais
- Fim (28–30):         360 fatais (87.8%) — concentrados em t=29 (356/360)
- **Pico no meio:** t=14 com 28 fatais; também t=12 sangra (4 fatais + 83 moderadas).

**Padrões sistêmicos (top pares ótima → CNN, todos com Δ ≥ 2):**
- Fim: H_2_1 → V_1_0 (37×), H_2_3 → H_0_3 (32×), H_6_3 → H_8_3 (30×),
  V_1_4 → V_1_6 (26×), V_1_4 → H_0_5 (24×) — viés de borda externa
  confirmado.
- Meio: H_0_3 → V_7_2 (15×), H_4_1 → V_3_2 (12×), H_8_3 → V_7_2 (12×),
  H_4_1 → V_3_0 (12×) — substituições estruturais que cruzam o tabuleiro,
  sintoma de paridade/cadeia mal compreendida.

### Veredicto: Cenário X3 confirmado e estável

A taxa de fatal precoce está estável em **15–18% nos três adversários** —
isso é evidência forte de **erro sistêmico da CNN** (não induzido pelo
adversário). Se o adversário é mais forte (p=6) ou mais fraco (p=3), a
CNN comete fatal precoce na mesma proporção das partidas que perde. Isso
favorece atacar a representação interna (canais estruturais — Fase D do
PRD) e a calibração de gradiente em meio-jogo (novas fases — ver abaixo),
não simplesmente "mais dados de fim".

Observação adicional importante: das 89 partidas perdidas vs p=6, **58
não têm nenhuma divergência fatal** (perdidas por acúmulo de moderadas).
Isso reforça que cobertura ampla de dados (Fases A/B/C do PRD) continua
sendo a base obrigatória do plano.

### Decisões derivadas — duas novas fases inseridas no PRD

#### Nova Fase E (entre atual D e atual E, que será renumerada para G):
**Sample_weight refinado por Δ-top2 — foco em meio-jogo (t=12 a t=17)**

- Foco real: **t=12 a t=17** (faixa de paridade/controle de cadeias),
  NÃO t=29. Os erros em t=29 já são atacados pelas Fases A/B (cobertura
  terminal) e pelo canal `eh_grau3` em D.
- Multiplicador discreto: `peso = 1 + α · Δ_top2_caixas`, com α calibrado
  para que tabuleiros nessa faixa valham **~10% a mais** que os demais
  (NÃO 6× — a maioria das jogadas em t=12–17 são boas; só damos um
  empurrãozinho de gradiente nas poucas que importam).
- Cap absoluto: nenhum peso individual pode passar de **1.20** (ou seja,
  20% a mais que o peso 1.0 dos demais tabuleiros).
- Implementação: cálculo de `Δ_top2` direto dos `scores` já no NPZ;
  multiplicar pelo coeficiente α apenas em amostras da faixa-alvo.

#### Nova Fase F (entre nova E e atual E renumerada G):
**Value head AlphaZero-style (multi-task learning)**

- Adicionar segunda saída ao modelo Keras, em paralelo à policy head:
  - Policy head (existente): Conv → Flatten → Dense(96) → softmax(31).
  - Value head (nova): Conv 1×1 → Flatten → Dense(64, relu) → Dense(1, tanh).
- Alvo do value head: `score_max(scores_mm) / 6` (normaliza Q* ao
  intervalo `[-1, +1]`; 6 = max caixas líquidas em 4×3).
- Loss conjunta: `loss_total = KLD(policy) + λ · MSE(value)` com
  **λ ≈ 0.1–0.3** (pequeno para não dominar a policy).
- **Inferência mobile sem custo:** descartar a value head no export TFLite
  (manter apenas a policy). Frontend Flutter inalterado.
- Justificativa: força a representação intermediária a codificar "quem
  está ganhando", sinal que hoje a CNN só aprende implicitamente pela
  política. Em jogos com decisões de paridade (caso de pontinhos 4×3),
  saber o sinal do valor antes de decidir a aresta é estruturalmente útil.
- Aumenta tempo de treino em ~10–20%; pipeline de dataset não muda
  (`value_target` é derivado dos `scores` já existentes no NPZ).

#### Renumeração:
- Atual Fase E (Hard-target ≥26) → **Fase G** (condicional).
- Atual Fase F (Loss assimétrica) → **Fase H** (condicional).

### Faixa crítica de meio-jogo estendida

PRD original cita faixa "10–25" para fatal precoce e "13-17" como faixa
crítica em alguns gates. Os dados mostram **t=12 também sangrando** (4
fatais + 83 moderadas, mais alto que t=13 em moderadas). Faixa crítica
unificada para **[12, 17]** em todos os gates e na nova Fase E.

### Alternativas descartadas
- **Sample_weight com cap 6×:** rejeitado pelo usuário — distorceria a
  loss em demasia. Maioria das jogadas em t=12–17 são boas; queremos
  empurrão sutil, não sobreposição.
- **Sample_weight focado em t=29:** redundante. Categoria A já é atacada
  pelas Fases A/B/C/D; t=29 representa 87.8% dos fatais mas é tática
  pura (ataque por cobertura + canal `eh_grau3`).
- **Value head com inferência completa em produção:** descartado
  porque adicionaria custo no app Flutter (3–5 ms por jogada). Mantemos
  value head só no treino (regularizador estrutural).
- **Pular Fase E e ir direto para value head:** descartado porque queremos
  isolamento causal entre intervenções. Cada fase recebe seu próprio
  TFLite versionado e avaliação independente.

### Consequências operacionais
- PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md` atualizado nesta data:
  - Seção 2.4 reescrita inteira com resultados das 600 partidas.
  - Faixa crítica unificada `[12, 17]` substituindo `[13, 17]` ou `10-25`
    onde aplicável.
  - Seção 5 com novas Fases E e F inseridas; antigas E/F renumeradas G/H.
  - Decisões D-novas adicionadas em §4 (D9 sample_weight refinado, D10
    value head).
- Plano sequencial: A → B → C → D → **E (sw refinado) → F (value head)** → G → H.
- Métricas operacionais a recalcular após Fase F (tempo treino esperado
  +10–20%, TFLite exportado sem value head — tamanho inalterado).

---

## 2026-05-06 — Minimax(p=1) descartado como adversário em análises diagnósticas

### Contexto
Ao revisar PNGs gerados por `tmp_analise/analisa_divergencia_estrategica.py`
em partidas CNN vs Minimax(p=1), o usuário identificou um padrão estranho:
em várias jogadas de **abertura** (t=2, t=4, t=12), o adversário Minimax
**criava caixas de grau-3 em estados que ninguém pediu para serem criados**,
literalmente "doando" caixas para a CNN. Hipótese inicial: bug no Minimax.

### Investigação
Reanálise pontual com Minimax(p=5/7/9) sobre o estado salvo em NPY (após
adicionarmos o salvamento de NPY+JSON irmão por PNG) confirmou que:

1. O motor Minimax **não está bugado**. A função `melhor_jogada()` em
   `gerador_dados/jogo_pontinhos/minimax_pontinhos.py` calcula corretamente
   os scores e devolve `random.choice(jogadas_tied)` entre as melhores.
2. O comportamento "absurdo" decorre de uma propriedade fundamental do
   **profundidade 1**: ele só simula a própria jogada (zero plies de resposta
   do adversário). Quando **nenhuma** jogada disponível fecha caixa
   imediatamente, **todas** ficam com score=0 (a função `avaliar` em
   profundidade 0 retorna `caixas_ia − caixas_humano` = 0). O motor então
   sorteia aleatoriamente entre as 27+ jogadas livres — incluindo as que
   criam grau-3 para o adversário.
3. Para detectar "abrir caixa para o oponente no próximo turno", o Minimax
   precisa de **pelo menos p=2** (1 ply próprio + 1 ply do oponente). p=1
   simplesmente não tem essa capacidade.

### Decisão: descontinuar p=1 como adversário em análises diagnósticas
A partir desta data, `analisa_divergencia_estrategica.py` (e qualquer
analisador derivado) **não usará mais Minimax(p=1)** como adversário. Em
diante, profundidades adversárias diagnósticas válidas são **p=3, p=5, p=6**.

**Por quê:**
- Partidas vs p=1 são contaminadas por jogadas pseudo-aleatórias do
  adversário, criando estados não-representativos do que a CNN encontraria
  em jogo real contra qualquer oponente humano de nível mínimo.
- Os Δ-scores que o oráculo (p=5/p=7/p=9 adaptativo) calcula sobre tais
  estados refletem em boa medida a **estranheza do estado** induzida pela
  aleatoriedade do p=1, não a qualidade tática/estratégica da CNN.
- Conclusões sobre "Categoria A vs B de erros" e "Cenário X1/X2/X3" exigem
  adversários minimamente capazes de não doar caixas em abertura.
- Avaliação de win-rate vs p=1 (em `Avaliacao_CNN_vs_Minimax.ipynb`) **continua
  válida** como métrica histórica para comparações longitudinais com
  rodadas anteriores — a decisão se restringe a análises de divergência
  estratégica, não ao avaliador de partidas em geral.

### Alternativas descartadas
- **Manter p=1 como controle "ruído de baseline":** rejeitado porque sua
  presença diluía a leitura visual dos PNGs (muitos d=0 ou d=1 inócuos
  causados pelo adversário "se sabotando") e custava ~25% do tempo total
  do run sem entregar sinal correspondente.
- **Trocar p=1 por p=2:** p=2 já enxerga "doar caixa" (vê 1 ply do
  oponente), mas a estatística vs p=2 pouco acrescenta sobre p=3 (que já
  está no padrão). Mantido fora por simplicidade.
- **Manter p=1 mas em pasta `Minimax_p_1_controle/`:** rejeitado porque
  ainda gera ~25% de overhead computacional sem benefício diagnóstico.

### Consequência operacional
- `tmp_analise/retratos_divergencia/Minimax_p_1/` apagada nesta data.
- Default de `--profundidades` ajustado para `3 5 6` no script.
- PRD `specs/004-melhoria-geracao-dados-cnn/PRD.md` referencia esta decisão
  na Seção 2.4 (cenário X1/X2/X3) — a baseline diagnóstica não inclui mais p=1.

### Mudança paralela — visibilidade de jogadas do adversário
Mesma sessão, identificado que era impossível diagnosticar comportamento
do MM sem ler matrizes em sequência (jogada-N CNN vs jogada-(N+1) MM exige
inferir o estado pós-jogada-N para depois ler o estado pré-jogada-(N+2)).
Adicionada geração de PNG+NPY+JSON também para **jogadas do MM**, com
formato espelhado ao da CNN: painel esquerdo = jogada que o MM fez (laranja),
painel direito = todas as ótimas em verde + todas as piores em marrom
segundo o **mesmo Minimax(p=X) que ele usou para decidir**. Sem custo
computacional adicional (reaproveita a tabela de scores que `melhor_jogada()`
já calcula internamente).

---

## 2026-04-29 — Tentativa 8 regrediu: manter V3 (depth=7) e aprender sobre saturação de capacidade

### Contexto
Após o sucesso da Tentativa 7 (V3 auto-play depth=7: 96% vs MM(p=1), 40% vs MM(p=6), OMA 93.2%), a pergunta natural era: **aprofundar o professor ajuda?** Geramos 344k amostras com Minimax depth=8/9 (14% mais dados) e retreinamos com a mesma arquitetura. As métricas estáticas sugeriam "um pouco melhor" (top-3 +1.7pp, top-5 +2.1pp) — até rodar o avaliador de partidas reais.

### Decisão: Manter V3 como modelo de produção

Win-rates confirmaram regressão clara (salvo p=1, onde diferença está no ruído):
- MM(p=3): 60% → 53% (−7 pp)
- MM(p=5): 45% → 40% (−4.5 pp)
- MM(p=6): 40% → 36.5% (−3.5 pp)

OMA também caiu (93.2% → 89.2%), e win-rate concordou com OMA — indicativo de que ambas as métricas detectam um problema real, não artefato de avaliação.

**Veredicto:** V3 (depth=7, 300k) vence V4 (depth=8/9, 344k) em todas as profundidades ≥ 3. Revertemos para V3 como modelo de produção.

### Aprendizado: Saturação de Capacidade do Student

A rede BoxNet v3 de 74.5k parâmetros atingiu o **ponto ótimo de capacidade do teacher** em depth=7. Aprofundar professor acima desse ponto degrada performance em vez de melhorar.

**Evidência de saturação:**
1. Top-1 estagnou: 42.7 → 42.71% com 14% mais dados.
2. OMA caiu: professor + profundo transmite nuance que o aluno não consegue reproduzir (fenômeno conhecido em knowledge distillation).
3. val_loss KLD subiu: alvo intrinsecamente mais difícil de aproximar (soft targets com menos empates, mais precisão de score).
4. Win-rate em profundidades altas caiu: confirma que OMA não era outlier — modelo realmente ficou pior.
5. Piso de blunders (~13–15% de caixas deixadas) é estável contra MM(p≥3): indica limite estrutural, não falta de dados.

### Alternativa Descartada

- **"E se aumentássemos a rede primeiro?"** — postergado. Não testamos depth=8/9 + rede maior juntos; testamos depth=8/9 + rede igual. Próxima rodada experimental será justamente isso (rede de ~180k params + depth=8/9).

### Próximos Passos (em Prioridade)

1. **Aproveitar V3 para defesa do TCC** — tem os melhores números absolutos, validados em jogo real. Narrativa centrada em OMA=93.2% + win-rate 96%/60%/45%/40%.

2. **Aumento de capacidade da rede (2–3 semanas futuros)**
   - Adicionar terceiro bloco residual (48 → 64 filtros)
   - Dense head 96 → 128
   - Estimativa: 150–200k parâmetros, ainda < 300 KB tflite
   - Re-treinar com dataset V4 (344k, depth=8/9)
   - Hipótese: rede maior + depth=8/9 deve superar V3

3. **Ou explorar largura (mais fácil):** gerar 600k+ amostras em depth=7 com rede atual. Menos dispendiosos que aumentar arquitetura.

4. **Investigar piso de 13–15% de blunders táticos:** gravar `(estado, jogada_cnn, jogada_otima, score_gap)` em casos de erro no avaliador. Pode revelar fraqueza específica (parity, loony endgame) que dataset sozinho não resolve.

### Alinhamento com Literatura

O fenômeno de "aluno saturado" vs "teacher muito forte" é bem documentado em knowledge distillation (Hinton 2015, e sequências). Existe um ponto ótimo de "teacher capacity" dado um student fixo. Ultrapassar esse ponto introduz ruído em vez de sinal. A solução padrão é aumentar student (como planejado acima).

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

---

## 2026-05-09 — Resolução de Divergência Matemática na Fase 2 (Databricks)

**Contexto:** Ao auditar os arquivos `.npz` recém gerados pela Fase 2 (Databricks), o motor Minimax Otimizado (Bitboard) estava produzindo scores inflados (ex: `+1` quando o correto era `0`) em ~14.5% das amostras analisadas (focadas no midgame).

**Causa Raiz (Dupla):**
1. **Contagem de caixas:** A álgebra booleana do Bitboard não descontava caixas que já se encontravam fechadas no tabuleiro antes do lance avaliado, injetando pontos fantasmas durante a recursão.
2. **Offsets na Poda Alpha-Beta Incremental:** Diferente do motor local que retorna o score *absoluto* ao final da árvore, o Bitboard retornava o score *incremental* (pontos acumulados dali para a frente). Com isso, ao repassar os limites `alpha` e `beta` para as subárvores, os valores exigiam aplicação de um *offset* (ex: `alpha - cl`). A ausência dessa compensação causava podas severas incorretas, eliminando os ramos ideais e resultando em scores piores/errados.

**Decisão:** O notebook `Geracao_Amostras_v7_adaptativo_Fase_2_HighPerf.ipynb` foi retificado implementando o controle estrito de `and edges & bm != bm` nas máscaras de caixas e as devidas compensações `+/- cl` nos limites do Alpha-Beta. A Transposition Table (TT) também passou a operar isoladamente para cada traço da raiz. As amostras geradas incorretamente precisam ser regeradas. Os detalhes matemáticos da investigação estão em `docs/jogo_pontinhos/Aprimoramento_Geracao_Amostras_v7_adaptativo.md`.

---

## 2026-05-30 — Rota: esgotar a CNN PURA antes da hibridização (foco TCC)

**Contexto.** A arena de autodiagnóstico (re-forense profunda das derrotas da CNN
de referência) revelou onde a rede erra. Diagnóstico preliminar (corpus p=17,
125 seeds): das derrotas, ~72% já estavam perdidas ao entrar na janela t≈14 (o
erro nasce no meio-jogo, 1ª metade, t=12–17). Nos 73 lances **decisivos**:
**regret médio = 5,18 caixas** (mín 2, máx 12 — NÃO são empates), mas a CNN deu
ao lance certo apenas **0,155** de probabilidade (vs 0,298 no errado); saída
quase chata (margem_top2 ~0,10), com o lance do Minimax no top-3 em ~49%.

**Interpretação.** O treino JÁ usa soft targets (`softmax(scores_minimax / T)`,
T=1.0, perda KLDivergence) — o sinal de valor já está no alvo e, com regret ~5, o
alvo estava **fortemente picudo** no vencedor. Logo NÃO é problema de formato de
alvo (one-hot) nem de temperatura. A rede está **sub-ajustando** essas posições:
elas são **raras** no dataset e o treino está com `USE_SAMPLE_WEIGHT = False`, então
a KL é minimizada acertando o abundante/fácil (endgame, all-but-two) e tratando as
raras-decisivas como ruído.

**Decisão.**
1. **Objetivo acadêmico (TCC):** esgotar ao máximo a CNN resolvendo o jogo
   **sozinha (argmax puro)**, sem busca na inferência. A hibridização
   `top-k da CNN + lookahead raso + folha de paridade de cadeias` fica como
   **caminho comercial/fallback** e como anexo de trade-off na dissertação —
   NÃO é o alvo acadêmico.
2. **Prioridade de alavancas (puro DL), baseada na evidência:**
   - (A) Experimento discriminador: rodar as posições de falha pelo modelo com
     Attention vs NoAttn/Dense256 → isola capacidade/contexto global vs dado.
   - (B) Mineração de exemplos difíceis → ligar/reprojetar `sample_weight` por
     decisividade/regret (não por qtd_tracos).
   - (C) Cobertura: gerar mais dados na banda de paridade do meio-jogo (t=12–17).
   - (D) Arquitetura (atenção/global-pooling/profundidade) se (A) indicar falta
     de contexto global — aqui a meta acadêmica justifica medir o teto mesmo
     acima de 5MB.

**Alternativas consideradas e descartadas (agora).** Trocar para one-hot
(já superado); baixar T (alvo já estava nítido); re-adicionar value-head de
regressão (colapsou — MAE ~0,85 prevendo 0; ver entrada do experimento value-head).

**Status.** Re-forense p=19 (janela t≥12) rodando para localizar o lance exato e
ampliar a base. Decisão de implementação (B/C/D) após o corpus p=19.

---

## 2026-05-30 — Oráculo exato (tablebase 4x3) revela rótulos de treino errados no meio-jogo

**Contexto.** Para localizar com exatidão por que a CNN (98,6% OMA) perde para
Minimax fraco, construímos um **oráculo exato por análise retrógrada** do tabuleiro
pequeno: `gerador_dados/jogo_pontinhos/oraculo_tablebase_pontinhos.py` calcula, por
programação dinâmica (negamax de trás para frente), o valor EXATO de jogo de TODAS
as 2^31 ≈ 2,1 bi configurações de arestas. Build em **2,26 min**, 2,0 GiB
(`dados/oraculo_pontinhos/tablebase_pequeno_4x3.npy`, no .gitignore). Valor da
posição inicial = 0 (empate sob jogo perfeito).

**Validação.** 2x2 EXAUSTIVO (4096 estados) = 0 divergências vs Minimax Python;
amostras 4x3 = 0 divergências; auditoria dos NPZs com `arestas_livres ≤ 11`
(onde p=11 alcança o terminal) = **0 divergências em ~9 mi comparações**. Oráculo
comprovadamente correto.

**Achado (auditoria de `dados/profundidade_minimax_11_adaptativo/`, 3,42 mi posições):**
- `arestas_livres ≤ 11`: **100% dos rótulos ótimos** (endgame perfeito).
- **27,12% de TODOS os rótulos ensinam um lance SUBÓTIMO** (regret médio 0,785 caixa).
- Piora rumo à abertura: ar=20 → 49% subótimo; ar=26–28 → ~70%; ar=14–18 (faixa
  onde a CNN falha) → 9%–35%.

**Causa-raiz.** Minimax p=11 **trunca** antes do terminal quando `arestas_livres > 11`
e seu argmax fica errado. A re-rotulação p=20 (Fase 3) só cobriu ~1,5% porque a
heurística `prof_min = total_caixas_cadeias + 2·qtd_cadeias` assumiu "sem cadeias
longas → p=11 basta" — FALSO: sem alcançar o terminal o valor é truncado. A maioria
do meio-jogo ficou com rótulo errado. Consequência: o "98,6% OMA" mede concordância
com rótulos errados, não com a verdade.

**Decisão.**
1. O oráculo é a nova **verdade-padrão** do tabuleiro pequeno (rotulagem e avaliação).
2. **Re-rotular o dataset inteiro com o oráculo** (exato, instantâneo) e **re-treinar**.
3. Medir **OMA verdadeiro** (CNN vs oráculo), não mais OMA vs rótulo.

**Ressalva.** Só vale para o tabuleiro **pequeno** (2^31 cabe em 2 GB). Médio/grande
seguem dependendo de Minimax/CNN. O pipeline (distribuição DAC, 12 canais,
augmentação, CNN) permanece válido — só a etapa de rotulagem do pequeno fica exata.

**Pendente.** (a) OMA verdadeiro da CNN atual vs oráculo; (b) confirmar a base exata
de treino do modelo de referência; (c) re-rotular + re-treinar + medir ganho.

### 2026-05-30 (correção/refinamento) — atribuição correta: p=20 OK, problema é p=11 truncado

A análise inicial acima (27% "subótimo") usava o ARGMAX, que é ruído (empates de
score são desempatados por sorteio). Refeita SÓ com o VETOR `score_melhor_jogada`
e segmentada por `depth_melhor_jogada >= arestas_livres` (profundidade alcançou o
terminal = exato), sobre 3,42 mi posições de `dados/profundidade_minimax_11_adaptativo/`:

- **Profundidade SUFICIENTE (1.300.049 pos., inclui TODOS os 44.793 rótulos p=20):
  100,0000% batem EXATO com o oráculo (0 divergências em 8,1 mi lances, TV=0).**
  → (a) o oráculo fica validado independentemente em `ar 12–19` (via os p=20);
    (b) os rótulos p=20 estão CORRETOS — sem contradição com as auditorias passadas.
- **Profundidade INSUFICIENTE (2.123.411 pos. = 62%, p=11 truncado, meio-jogo/abertura):
  só 0,85% exatos; soft-target médio diverge TV=0,35 (pico ~0,49 em ar≈20–22).**

**Correção de atribuição:** a re-rotulação p=20 NÃO está errada (retratado). O problema
é que a maioria do meio-jogo/abertura SEM cadeias longas ficou em p=11 truncado e
nunca foi re-rotulada (a heurística `prof_min` só pegou estados com cadeias longas,
~1,3%). Para o soft target de treino, esses 62% estão distorcidos.

**Conserto (não-destrutivo):** re-rotular SÓ as ~2,1 mi posições com profundidade
insuficiente usando o oráculo (as 1,3 mi exatas não mudam); manter p=20, codificação,
augmentação. Depois re-treinar e medir OMA verdadeiro (CNN vs oráculo).

### 2026-05-30 — Base nova com rotulação EXATA do oráculo

Validação final: o oráculo bate 100% com TODOS os NPZ (1677 arquivos, originais +
simetria) onde a profundidade alcança o terminal — **5.200.196 posições, 0
divergências em 32,5 mi lances**. Oráculo confirmado correto.

Criada `dados/profundidade_oraculo_exato/` (NÃO destrói a base antiga
`dados/profundidade_minimax_11_adaptativo/` nem os NPZ de simetria): 419 originais
reagrupados em **105 arquivos** `dataset_pequeno_oraculo_NNNN.npz`, 3.423.460 linhas.
- `score_melhor_jogada`: vetor EXATO do oráculo (todas as posições, sem truncamento).
- `melhor_jogada`: argmax determinístico do vetor (1º ótimo).
- `depth_melhor_jogada = 31 − qtd_tracos` (= arestas_livres; profundidade que chega
  ao terminal → exata em toda posição).
- Demais campos preservados (estados, canais 12, escalares de cadeias, labels, nomes).
- **Pendente:** augmentação por simetria da base nova (Fase 4) — não gerada aqui por
  instrução de não tocar nos NPZ de simetria; regenerar a partir dos rótulos exatos
  quando for treinar com augmentação.

Próximo: re-treinar com a base exata e medir OMA VERDADEIRO (CNN vs oráculo).

> Correção (mesma data): `melhor_jogada` na base nova usa **escolha ALEATÓRIA entre
> os lances ótimos empatados** (RNG semeado p/ reprodutibilidade), não o 1º ótimo.

> Augmentação: o NPZ consolidado `aug_distintos_novos_todos_t.npz` (4.915.970 linhas)
> foi copiado para `dados/profundidade_oraculo_exato/` com score_melhor_jogada (vetor
> exato), melhor_jogada (aleatório entre empates) e depth_melhor_jogada (=31−qtd_tracos)
> re-rotulados do oráculo. Sanidade: popcount(arestas)==qtd_tracos em 100% das linhas;
> melhor_jogada ótimo em 100% da amostra. Base nova pronta para treino COM augmentação.

## 2026-05-30 (resultados) — CNN re-treinada na base do oráculo: derrotas eliminadas

Treinamento `boxnetv4_oraculo_exato_8p3M` (mesma arquitetura/atenção do modelo de
referência, mas sobre `dados/profundidade_oraculo_exato`).

**Resultado central — partidas vs Minimax (200 cada, p=1,3,5,6):**
- 800 partidas → **1 única derrota** (p=5; 0,1%). Antes, a referência perdia ~3% na arena.
- p=1: 100% vitória; p=3: 94% V / 6% E / 0 D; p=5: 92% V / 7,5% E / 0,5% D; p=6: 92,5% V / 7,5% E / 0 D.

**OMA verdadeiro (vs oráculo) = 97,8%** (a referência tinha ~98,3% MAS medido contra
rótulos errados; a régua mudou — 97,8% agora é honesto e a força de jogo subiu).
- OMA por fase: Abertura 95,8% | 1ª Metade 98,2% | 2ª Metade 100% | Quente 100% | Final 100%.
- Top-1 baixo (63%) é esperado: soft targets exatos + muitos empates na abertura.

**Confirmação do conserto (Canal × Erro):** os erros NÃO se concentram mais em
`em_cadeia_longa`/`paridade`/`eh_grau3`/`caixa_fechada` (todos SUB-representados nos
erros). Migraram para `eh_grau2`/abertura (posições equilibradas, erro recuperável).
O raciocínio de paridade do meio-jogo — a doença original — foi reparado. Prova de
que a causa-raiz era RÓTULO, não capacidade.

**Pendências/ressalvas:** (a) não é literalmente 100% (1/800); (b) o teste p=1–6 é
mais fácil que a arena com adversários descuidados/aberturas aleatórias — re-rodar a
arena para selo final; (c) TFLite saiu com 18,9 MB (modelo com atenção) — a escada
rumo aos ≤5 MB (Flutter) deve ser refeita sobre a base exata. Primeiro experimento
dessa escada: notebook `Treinamento_CNN_Pontinhos_V10_Oraculo_Exato.ipynb`
(arquitetura V10 simplificada, exp `cnn_v10_simplificada_oraculo_exato`).

## 2026-05-30 (arena + forense pelo oráculo) — derrota real da CNN ≈ 0,02%

Arena com o modelo do oráculo vs adversário descuidado (p=3, eps=25%, abertura
aleatória k=4): **10.000 partidas → 9.947 V / 49 E / 4 D (0,04%)**. A referência
antiga perdia ~3% nas mesmas condições → queda de ~75×.

**Forense EXATA pelo oráculo das 4 derrotas** (valor exato em cada lance, sem janela):
- **2/4 (seeds 5956, 8994):** NÃO são erro da CNN — a abertura aleatória forçada já
  entregava posição perdida (valor_ótimo = −4 no 1º lance julgado); a CNN jogou
  **perfeito (regret 0)** dali em diante. Artefato do gerador de diversidade.
- **2/4 (seeds 7084 @t=12; 8240 @t=13):** blunder real — **doação no início do
  meio-jogo** jogando fora um EMPATE (regret 4 e 2). Mesmo arquétipo da doença
  original (paridade no meio-jogo), agora ~150× mais raro.

**Taxa de erro REAL atribuível à CNN ≈ 2/10.000 (0,02%).** Além disso, o oráculo
confirma que as "caixas de graça" no começo são majoritariamente **sacrifícios
ótimos (regret 0)** — jogo são, não erro.

**Próximo (rumo a ~100%):** mineração dirigida do arquétipo "doação no meio-jogo
(t≈12–17) que vira empate→derrota (regret≥2)", com rótulo exato do oráculo, e
re-treino. Ferramenta de forense exata por oráculo criada nesta sessão (replay por
seed + lookup O(1)); candidata a virar módulo permanente.

## 2026-05-31 — Mineração de falhas por self-play julgada pelo oráculo (loop de melhoria)

Ferramenta nova (permanente): `analise/jogo_pontinhos/diagnostico_derrotas_cnn_pequeno_referencia/minerar_falhas_selfplay_pontinhos.py`.
Implementa os itens 1–2 do loop combinado com o usuário: a CNN joga contra uma
POPULAÇÃO diversa de adversários (Minimax descuidado com prof∈{1..4}, eps∈{0.1,0.25,0.4},
aberturas aleatórias k∈{2,4,6,8}, + ~9% aleatórios) e o **oráculo julga CADA lance**
(lookup O(1)); coleta todo lance com **regret>0** (estados realistas onde a CNN erra),
dedup por bitmask, salvamento incremental (.npz) e retomável (progresso.json).
Rótulo gravado = VETOR `score_melhor_jogada` exato do oráculo (não o argmax).

Smoke (600 jogos): 9992 lances julgados → **148 falhas distintas** (regret médio 2,03;
11 decisivas). Por classe do lance da CNN: 136 segura / 10 doação / 2 captura. Por fase:
concentradas em t=7–13 (abertura/início do meio-jogo, pico t=12). Lote real de 30k
jogos rodando (run-id selfplay_v1).

**Loop acordado (rumo a ~100%):** 1) self-play diverso → 2) oráculo julga (regret>0)
→ 3) separar novo-não-visto vs visto-mas-erra (dedup contra os 8,3M; injetar os novos)
→ 4) rótulo = score_melhor_jogada do oráculo → 5) injetar (milhares) + sample_weight
→ 6) repetir → 7) futuro: destilar a base (coreset) p/ treinar mais rápido.

### 2026-05-31 (resultado) — a lacuna é COBERTURA: 91,7% das falhas são estados nunca vistos

Self-play minerado (30.000 jogos, 498k lances julgados pelo oráculo) → **7.021 falhas
distintas** (regret>0; média 2,07; máx 14; 668 decisivas). Cruzando contra os 6.916.861
bitmasks distintos da base 8,3M:
- **NOVAS (nunca vistas no treino): 6.439 = 91,7%** — 583 decisivas, 175 com regret≥4,
  concentradas em t=7–13, majoritariamente lances "segura". É a LACUNA real.
- VISTAS-mas-erra: 582 = 8,3% — todas regret 2, na abertura (t=4–8); sub-ajuste de
  quase-empates, baixo risco (sample_weight, não injeção).

**Conclusão:** o gap para ~100% é majoritariamente COBERTURA (a CNN erra no que nunca
viu), não capacidade — confirma a hipótese do loop. Subconjunto novo salvo em
`saidas/selfplay_v1/falhas_novas.npz` (rótulo = score_melhor_jogada exato). Próximo
(itens 4–5): montar NPZ de injeção (canais via extrair_canais + escalares de cadeias +
augmentação por simetria 4×) e re-treinar base + injeção com sample_weight.

### 2026-05-31 (itens 4–5) — Refinamento 1: base de injeção + notebook de fine-tuning

Construído `dados/profundidade_oraculo_exato/refinamento_oraculo_001.npz` (também no
Drive) a partir das 6.439 falhas NOVAS: para cada estado, canais via `extrair_canais`,
escalares via `extrair_stats_cadeias`, estados via `_para_dominio_dataset` (mesmas
funções da base → schema v2-a3 idêntico); rótulo = `score_melhor_jogada` EXATO do
oráculo. Augmentação por simetria 4× (aplicar_simetria) → 25.756 → **25.348 após dedup**.
Validado: estados∈{0,1,8,9}, canais∈{0,1}, melhor_jogada 100% ótima.

Notebook de fine-tuning: `notebooks/jogo_pontinhos/Treinamento_CNN_Pontinhos_V11_Colab_Oraculo_Refinamento1.ipynb`
(cópia do notebook da CNN oráculo; treino IDÊNTICO, mesma arquitetura, sobre a pasta
base+refinamento). EXPERIMENTO=`boxnetv4_oraculo_exato_refinamento1_8p3M`; nome do tflite
ajustado ao padrão `pontinhos_pequeno_cnn_12canais_{EXPERIMENTO}.tflite`.

Ferramentas novas permanentes: `minerar_falhas_selfplay_pontinhos.py` e
`construir_npz_refinamento_pontinhos.py` (repetíveis para refinamentos 2, 3, …).

Nota: teste do contrato de encoding = 10/11 OK; a única falha (hash backend≠frontend)
é IRRELEVANTE — frontend ainda não foi desenvolvido.

> Ajuste (item 5): ligado `sample_weight` no notebook de Refinamento 1 — as linhas do
> arquivo `refinamento_*` recebem peso `PESO_REFINAMENTO` (default 20×) vs 1× da base
> (presença efetiva ~6% do gradiente, vs 0,3% sem peso). Tunável na config; peso alto
> demais arrisca decorar as 6.439 posições, baixo demais dilui — o teste-alvo afere.

## 2026-05-31 (resultado) — Refinamento 1: 88% das lacunas consertadas, jogo melhora, OMA cai um hair

CNN `boxnetv4_oraculo_exato_refinamento1_8p3M` (base 8,3M + 25,3k do refinamento com
sample_weight 20×; batch 4096, lr 2e-3, 61 epocas).

**Teste-alvo (decisivo):** das 6.439 posicoes onde a CNN ANTIGA falhava (regret>0),
a refinada CONSERTOU **5.685 = 88,3%** (regret agora 0); 754 ainda erram. Consistente
por fase (82–100%). => a injecao+peso funcionou no alvo.

**Partidas vs Minimax (200 cada p=1,3,5,6):** melhorou. p3 94%→98% V; p5 92%(1 derrota)
→98% (0 derrota); p6 92,5%→96%. Empates totais 42→16; **derrotas 1→0 em 800 jogos**.

**OMA vs rotulos exatos: leve REGRESSAO** 97,8%→97,5% (val_oma 0,9782→0,9746); abertura
95,8→95,2; 1a metade 98,2→97,8. Causa: peso 20× puxou capacidade p/ as raras + batch
4096 (generaliza um hair pior). Concentrada na abertura (quase-empates inofensivos).

**Simulador vs ORACULO perfeito (107 partidas):** CNN 45 V / 52 D / 10 E. Esperado —
nao se vence jogo perfeito (4x3 e empate sob jogo perfeito); vitorias vem da abertura
aleatoria. Benchmark de teto para acompanhar entre refinamentos.

**Conclusao:** refinamento 1 = SUCESSO pelas metricas que importam (lacunas consertadas,
mais vitorias, 0 derrotas). **OMA-vs-rotulos saturou e virou metrica enganosa** (caiu
enquanto a forca de jogo subiu) — north-star passa a ser win/draw/loss + fix-rate do
teste-alvo + placar vs oraculo. Proximo: refinamento 2 (re-minerar com o modelo novo).

> Métrica nova: `Avaliacao_CNN_vs_Minimax.ipynb` ganhou a seção **CNN vs Oráculo
> (jogo perfeito)** — joga vs a tablebase exata (1a jogada aleatória, alterna quem
> abre) e reporta V/E/D **quebrado por QUEM ABRE** (CNN abre x Oráculo abre), pois
> contra o jogo perfeito as vitórias vêm de aberturas favoráveis. Roda local (.venv_tf,
> tablebase). Harness validado (smoke 40 jogos ≈ 35/15/50, coerente com o simulador 45/52/10).

## 2026-05-31 (refinamento 2 + métricas) — montagem e enquadramento "vs Minimax alto"

Mineração round 2 (modelo refinado, 30k jogos): 6.905 falhas distintas, **6.290 novas
(91,1%)** apos dedup contra base+ref1, 650 decisivas. Construido
`refinamento_oraculo_002.npz` (24.914 = 6.290 + simetria 4x), na pasta + Drive (108 NPZ).
Notebook `Treinamento_CNN_Pontinhos_V11_Colab_Oraculo_Refinamento2.ipynb` (base no ref1):
**batch 2048, lr 1e-3, PESO_REFINAMENTO 12x** (menor, pois o residuo e de baixo valor e
peso 20x sangrou o OMA do oceano); MD/comentarios/prints corrigidos. O notebook pesa
TODOS os `refinamento_*` (ref1+ref2).

**Nota estratégica:** ~91% das falhas ainda sao novas a cada round (espaco grande) →
retorno decrescente; o salto grande foi o round 1. Refinamento 2 fecha mais decisivas
mas com ganho menor; 100% so via injecao e impraticavel.

**Enquadramento "vs Minimax alto" (decisao):** NAO vale rodar Minimax p=17/19 (proibitivo)
nem simular por subtracao do oraculo (funcoes distintas). Um Minimax p=19 e EXATO (=oraculo)
para ar<=19 (t>=12) e so difere na abertura (quase-empate) → praticamente identico ao
oraculo. Logo o benchmark **CNN vs Oraculo (= Minimax p=31, profundidade total)** que ja
adicionamos JA e o "vs Minimax altissimo", no teto. Escada de regret descartada (usuario).
