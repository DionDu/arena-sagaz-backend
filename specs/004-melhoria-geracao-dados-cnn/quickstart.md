# Quickstart — Fluxo end-to-end do desenvolvedor

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](./plan.md)

> Roteiro operacional para reproduzir cada fase do plano. Cada seção lista o **comando**, o **gate de saída** e o **registro obrigatório** antes de avançar.

---

## Pré-requisitos

- Acesso ao Databricks (cluster Spark V4 atual).
- Máquina local com Python 3.11+, dependências de `requirements.txt`, `pytest`.
- Acesso ao Colab T4 (treino).
- Repositório frontend `arena-sagaz-frontend` clonado em paralelo (apenas para Fases B e D — copiar contrato JSON).

---

## Fase A.1 — Geração no Databricks

### Comando

1. Abrir `notebooks/jogo_pontinhos/Otimizacao_Topologia_Rede_V5.ipynb` no Databricks.
2. Conferir a célula de parâmetros — `COMPLEMENTO_POR_CELULA` deve estar literalmente preenchida com a tabela de PRD §4.1.3.
3. Conferir `STRAT_WEIGHTS = [0.05, 0.00, 0.40, 0.55]` e `FAIXA_TRACOS = (0.15, 0.97)`.
4. Executar todas as células. Esperar até gerar 347.020 amostras únicas no diretório.

### Gate de saída

- ≥ 500.000 estados únicos no diretório (legados + complemento).
- Distribuição empírica ±2pp das cotas D1/D1.a.
- Mix gen_mode final ≈ 0=5%, 1=0%, 2=40%, 3=55%.

### Registro obrigatório

Em `docs/historico_decisoes.md` (entrada datada): snapshot completo da `COMPLEMENTO_POR_CELULA` usada + distribuição empírica + tempo de geração.

---

## Fase A.2 — Enriquecimento local

### Comando

```bash
# Ambiente local, raiz do backend
python -m pytest tests/unitarios/jogo_pontinhos/test_analisador_estrutural_pontinhos.py -v
# Esperar: todos os testes passam

# Notebook A.2:
jupyter notebook notebooks/jogo_pontinhos/Enriquece_NPZ_Com_Canais.ipynb
# Executar todas as células (parâmetro: --diretorio-npz=dados/profundidade_minmax_9)

# Validação visual:
python scripts/pontinhos/validar_canais_visualmente.py \
    --diretorio-npz dados/profundidade_minmax_9 \
    --qtd-tracos 14 17 29 \
    --n-amostras 30 \
    --saida tmp_analise/validacao_canais_estruturais/ \
    --seed 42
```

### Gate de saída

- Cada NPZ no diretório tem `canais (N,4,3,11) int8` + `nomes_canais (11,) <U32>`.
- `nomes_canais` byte-a-byte igual à constante `NOMES_CANAIS` em todos os NPZs.
- Validação visual manual de ≥ 30 estados (12–17, 24–28, 29–30) — incluir handout, double-cross do Buchin, loop simples, 2 cadeias longas disjuntas.
- `pytest test_analisador_estrutural_pontinhos.py` passa.

### Registro obrigatório

Entrada em `docs/historico_decisoes.md` consolidando D2/D3/D4 + casos canônicos verificados + hashes pré/pós enriquecimento.

---

## Fase B — Treino com 5 canais geométricos

### Comando

1. Abrir `notebooks/jogo_pontinhos/Treinamento_CNN_Arena_Sagaz_V6.ipynb` no Colab T4.
2. Configurar célula de parâmetros: `FASE = "B"`, `SLICE_CANAIS = slice(0, 5)`, `INPUT_SHAPE = (4, 3, 5)`.
3. Verificar que a `Lambda para_grid_de_caixas` está **fora do grafo Keras**.
4. Treinar. Exportar `modelos/pontinhos_pequeno_p9_faseB.tflite`.
5. Atualizar `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` para versão refletindo `(4, 3, 5)`.
6. **Copiar JSON byte-a-byte para `arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json` na MESMA PR**.
7. Rodar `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py`.
8. Avaliar: `Avaliacao_CNN_vs_Minimax.ipynb` (200 partidas × p=3/p=5/p=6).
9. Rodar `analisa_padrao_erros.py` e `analisa_divergencia_estrategica.py`.

### Gate de saída

- SC-F-05: faixa 29–30 ≥ 95% top-1 (gate forte).
- Erros táticos ≤ 250 (≥ 50% redução vs baseline 505).
- Nenhum win-rate cai > 3pp; nenhuma faixa cai > 2pp.
- TFLite ≤ 200 KB; latência ≤ 5 ms/jogada.
- Hash do contrato byte-a-byte igual entre backend e frontend.

### Registro obrigatório

Entrada em `docs/historico_decisoes.md` com tabela comparativa Baseline vs Fase B + tabela de accuracy por faixa + diff de configuração.

---

## Fase C — Augmentação 4×

### Comando

1. Implementar `gerador_dados/jogo_pontinhos/permutacoes_simetria_pontinhos.py`.
2. `pytest tests/unitarios/jogo_pontinhos/test_permutacoes_simetria_pontinhos.py` passa.
3. No V6, ativar bloco de augmentação (ainda com `canais[..., :5]`):
   ```python
   FASE = "C"
   USAR_AUGMENTACAO = True
   ```
4. Treinar. Se RAM apertar no Colab, migrar para `tf.data.Dataset.map(...)` em vez de materializar 2M tensores em memória.
5. Exportar `modelos/pontinhos_pequeno_p9_faseC.tflite`.
6. Avaliar.

### Gate de saída

- Nenhum par "deveria→jogou" individual > 5% do total de erros.
- Nenhum win-rate cai vs Fase B.
- Nenhuma faixa cai > 2pp; faixa 29–30 permanece ≥ 95%.
- Testes unitários de `permutacoes_simetria_pontinhos` passam.

### Registro obrigatório

Entrada em `docs/historico_decisoes.md` com tabela Fase B vs Fase C + distribuição dos pares "deveria→jogou".

---

## Fase D — 11 canais + contrato v2 + vetores de referência

### Comando

1. No V6, alternar:
   ```python
   FASE = "D"
   SLICE_CANAIS = slice(0, 11)
   INPUT_SHAPE = (4, 3, 11)
   ```
2. Treinar. Exportar `modelos/pontinhos_pequeno_p9_faseD.tflite`.
3. Atualizar `contrato_codificacao_pontinhos.json` para versão refletindo `(4, 3, 11)`.
4. **Copiar JSON byte-a-byte para o frontend na MESMA PR**.
5. Gerar `gerador_dados/jogo_pontinhos/referencia_canais_pontinhos.json` cobrindo: estado vazio, caixa fechada, double-cross do Buchin, loop 4 caixas, 2 cadeias longas disjuntas, half-open chain, handout, ≥ 20 estados sorteados em t ∈ {14, 17, 24, 29}.
6. `pytest tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py` passa.
7. Avaliar.

### Gate de saída

- Vitórias vs p=5 ≥ 70%.
- Erros totais ≤ 80.
- Divergências fatais por partida caem ≥ 50% vs baseline.
- Faixa 29–30 ≥ 95%; nenhuma faixa regride > 2pp vs Fase C.
- Hash do contrato igual backend↔frontend.
- `referencia_canais_pontinhos.json` versionado.

### Registro obrigatório

Entrada em `docs/historico_decisoes.md` com tabela Fase C vs Fase D + lista dos casos canônicos cobertos pelos vetores de referência.

---

## Fase E — sample_weight refinado em t=12–17

### Comando

1. No V6, ativar bloco de cálculo de Δ_top2 + função de peso. `α = 0.03` inicial.
2. Confirmar histograma: peso médio na faixa-alvo entre 1.05 e 1.15; `pesos.max() ≤ 1.20`.
3. Treinar com `model.fit(sample_weight=pesos)`. Exportar `_faseE.tflite`.
4. Avaliar.

### Gate de saída

- Nenhum win-rate cai > 2pp vs Fase D.
- Divergências fatais em t ∈ [12, 17] caem ≥ 25% vs Fase D.
- Nenhuma faixa cai > 2pp; faixa 29–30 ≥ 95%.
- Histograma de pesos validado.

---

## Fase F — Value head AlphaZero-style

### Comando

1. No V6, modificar célula do modelo Keras com dual-output (policy + value).
2. Loss conjunta: `KLD(policy) + λ · MSE(value)` com `λ = 0.1` inicial.
3. `value_target = clip(score_max / 6.0, -1, +1)`.
4. Treinar.
5. **Export TFLite descartando value head**: gerar segundo modelo Keras `Model(inputs, policy_pred)` e converter.
6. `pytest test_contrato_codificacao_pontinhos.py` passa (hash idêntico ao da Fase D).
7. Avaliar.

### Gate de saída

- Nenhum win-rate cai > 2pp vs Fase E.
- MSE final do value_pred em validação ≤ 0.10.
- Divergências fatais por partida caem ≥ 50% vs baseline.
- Contrato byte-a-byte idêntico ao da Fase D.
- TFLite ≤ 200 KB; latência ≤ 5 ms/jogada.

### Registro obrigatório

Entrada em `docs/historico_decisoes.md` com valor de λ calibrado + MSE final + tabela Fase E vs Fase F.

---

## Fases G/H — Condicionais

Só executam se Fase F não bater meta de SC-W-* ou SC-A-*. Detalhamento em PRD §5 (Fase G — Hard-target em ≥26 traços; Fase H — Loss assimétrica calibrada com BCE).

---

## Critério de aceitação geral do feature

A feature está entregue quando:

1. SC-A-01: erros táticos ≤ 80.
2. SC-B-01: divergências fatais por partida caem ≥ 50% vs baseline.
3. SC-W-01..03: vitórias vs p=3 ≥ 80%, vs p=5 ≥ 70%, vs p=6 ≥ 60%.
4. SC-W-04: vitórias vs p=1 ≥ 92% (não regredir).
5. SC-D-01..06: dataset com ≥ 500k únicos, distribuição ±2pp, `canais` + `nomes_canais` em todos os NPZs, snapshot da `COMPLEMENTO_POR_CELULA` em historico.
6. SC-O-01..06: TFLite ≤ 200 KB, latência ≤ 5 ms, geração ≤ 4h, hash backend=frontend, pipeline E2E executável, testes obrigatórios passam.

---

**Fim do quickstart.**
