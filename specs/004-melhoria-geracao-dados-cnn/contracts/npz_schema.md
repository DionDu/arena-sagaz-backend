# Contrato — Esquema dos NPZ por fase

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Última revisão**: 2026-05-12 — V7 DAC substituiu o pipeline V5/cotas; schema V2 com renomeação de campos e remoção de `generation_mode`.
**Documento pai**: [plan.md](../plan.md)

> Esquema concreto dos arquivos NPZ produzidos/consumidos em cada fase do pipeline. Espelha `data-model.md` §10.

---

## 1. NPZ Fase A.1 — Saída do pipeline V7 DAC (schema V2)

> **Revisão 2026-05-12:** o pipeline V5/cotas (`COMPLEMENTO_POR_CELULA`, `STRAT_WEIGHTS`, `generation_mode`) foi **substituído** pelo algoritmo DAC (Diversidade Adaptativa em Cascata). Ver `docs/jogo_pontinhos/geracao_dados_v7_adaptativo.md` para especificação completa.
>
> O schema V2 é produzido em **duas etapas** separadas: Fase 1 (geração local, campos de autoplay) e Fase 2 (enriquecimento no Databricks, campos de supervisão). O NPZ final da Fase A.1 contém os campos de ambas as etapas.

### 1.1 Campos da Fase 1 (geração local — autoplay DAC)

```python
np.savez(
    arquivo,
    estados=estados,              # (N, 9, 7) int8  — matriz crua {0,1,8,9}
    qtd_tracos=qtd_tracos,        # (N,) int8        — número de traços aplicados (1..30)
    score_jogada=score_jogada,    # (N, 31) float32  — Q-values Minimax(p adaptativo) do estado atual
    depth_jogada=depth_jogada,    # (N,) int8        — profundidade Minimax usada NESTE estado
    depth_geracao=depth_geracao,  # (N,) int8        — profundidade usada no estado ANTERIOR (= depth_jogada[k-1])
    labels_canonicos=labels_canonicos,  # (31,) <U5  — ordem canônica dos 31 slots
)
```

### 1.2 Campos da Fase 2 (Databricks — supervisão Minimax profunda)

Acrescentados ao mesmo NPZ via sobrescrita atômica (`.tmp` + `os.replace`):

```python
# Adicionados à Fase 2 (Databricks):
melhor_jogada=melhor_jogada,                # (N,) <U5      — argmax de score_melhor_jogada
score_melhor_jogada=score_melhor_jogada,    # (N, 31) float32 — Q-values Minimax(p=7 ou p=11)
depth_melhor_jogada=depth_melhor_jogada,    # (N,) int8      — profundidade usada na Fase 2 (fixo por rodada)
```

**Distinção crítica:**

| Campo | Origem | Profundidade | Uso recomendado |
|---|---|---|---|
| `score_jogada` | Fase 1 (autoplay local) | Adaptativa, p∈[1,8] | Análise / curriculum / hint de ordenação na Fase 2 |
| `score_melhor_jogada` | Fase 2 (Databricks) | Fixa (7 ou 11) | **Verdade-padrão para treino da CNN** |

> ⚠️ **Nunca treinar contra `score_jogada`.** Esse campo reflete decisões rápidas de qualidade variável. O campo de treino é sempre `score_melhor_jogada`.

**Restrições**:
- `estados[i, j, k] ∈ {0, 1, 8, 9}`.
- `qtd_tracos[i] ∈ [1, 30]` (t=0 e t=31 nunca gravados).
- `score_jogada[i, k]` e `score_melhor_jogada[i, k]` ∈ `[-6.0, 6.0] ∪ {-1e9}` (slots inválidos = `-1e9`).
- N por arquivo = ~5.000 (pode variar; a Fase 2 reescreve atomicamente preservando N).
- **NÃO contém** `generation_mode` (removido no V7), nem `depth` global, nem `rotulos` (renomeado para `melhor_jogada`), nem `scores` (renomeado para `score_melhor_jogada`).

**Diretório**: `dados/profundidade_minimax_{DEPTH_F2}_v7_adaptativo/` → na configuração padrão (execução 2026-05-12): `dados/profundidade_minimax_11_v7_adaptativo/`.

### 1.3 Dados gerados (execução 2026-05-12)

Pipeline DAC com ~25.288 partidas. Distribuição empírica:

| qtd_tracos | Amostras brutas | Amostras distintas |
|---:|---:|---:|
| 1 | 25.288 | 31 |
| 2 | 25.288 | 465 |
| 3 | 25.288 | 4.475 |
| 4 | 25.288 | 17.247 |
| 5–25 | 25.288 cada | 23.000–25.276 cada |
| 26 | 25.288 | 4.003 |
| 27 | 25.288 | 1.734 |
| 28 | 25.288 | 616 |
| 29 | 25.288 | 168 |
| 30 | 25.288 | 31 |
| **Total** | **~758.640** | **~500.000 distintos** |

Distribuição bell-shaped emergente — sem quotas manuais. Pontas saturam o espaço teórico combinatório (`C(31,1)=31`, `C(31,30)=31`).

---

## 2. NPZ Fase A.2 (saída do enriquecimento local com 11 canais estruturais)

Mesmos campos da Fase A.1 completa **+**:

```python
np.savez(
    arquivo,
    # Campos preservados da Fase A.1 (todos):
    estados=estados,
    qtd_tracos=qtd_tracos,
    score_jogada=score_jogada,
    depth_jogada=depth_jogada,
    depth_geracao=depth_geracao,
    melhor_jogada=melhor_jogada,
    score_melhor_jogada=score_melhor_jogada,
    depth_melhor_jogada=depth_melhor_jogada,
    labels_canonicos=labels_canonicos,
    # Campos novos:
    canais=canais,                    # (N, 4, 3, 11) int8
    nomes_canais=nomes_canais,        # (11,) <U32
)
```

**Restrições adicionais**:
- `canais[i, r, c, k] ∈ {0, 1}`.
- `nomes_canais` byte-a-byte igual à constante `NOMES_CANAIS` em `analisador_estrutural_pontinhos.py`.
- Sobrescrita atômica: gravar em `<arquivo>.tmp` + `os.replace(<arquivo>.tmp, <arquivo>)`.

---

## 3. Garantias do pipeline

| Invariante | Onde é verificada |
|---|---|
| Total ≥ 500.000 estados distintos por `mat.tobytes()` | Auditoria pós-A.1 (script ad-hoc) e pós-A.2 (auditoria do diretório) |
| Distribuição emergente bell-shaped (sem quotas) | Inspecionada manualmente; registrada em `historico_decisoes.md` |
| `nomes_canais` igual em todos os NPZs do diretório | Teste `test_analisador_estrutural_pontinhos.py` |
| Sobrescrita atômica não corrompe original | NFR-06; testado por simulação de Ctrl+C durante A.2 |
| `melhor_jogada` != `""` em todo NPZ processado pela Fase 2 | Verificação no notebook de orquestração da Fase 2 |

---

## 4. Versionamento dos NPZ

Versão implícita pelo conjunto de campos presentes:

| Versão | Fase | Campos presentes |
|---|---|---|
| **v1** (legado — pipeline V4/V5) | — | `estados`, `rotulos`, `scores`, `generation_mode`, `labels_canonicos`, `depth` |
| **v2-f1** (V7 Fase 1) | A.1 parcial | `estados`, `qtd_tracos`, `score_jogada`, `depth_jogada`, `depth_geracao`, `labels_canonicos` |
| **v2-f2** (V7 completo) | A.1 completa | todos acima + `melhor_jogada`, `score_melhor_jogada`, `depth_melhor_jogada` |
| **v2-a2** (enriquecido) | A.2 | todos acima + `canais`, `nomes_canais` |

Auditoria por `np.load(arquivo).files` — lista de campos.

> **Atenção:** arquivos v1 (legado em `dados/profundidade_minmax_9/`) usam campos com nomes diferentes (`rotulos`, `scores`, `generation_mode`). Não misturar com v2 sem conversão explícita.

---

**Fim do esquema NPZ.**
