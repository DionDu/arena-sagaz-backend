# Modelo de Dados — Fase 1 do plano

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](./plan.md)

> Esta seção descreve as entidades persistidas no NPZ ao longo do pipeline, suas validações, e as transições de estado entre Fases A.1 e A.2. **Espelha** `spec.md > Key Entities` e PRD §3.2 / §4.2; em caso de divergência, o PRD prevalece.

---

## 1. Entidade: `Estado bruto` (`estados[i]`)

| Campo | Valor |
|---|---|
| Shape | `(9, 7)` |
| Dtype | `int8` |
| Domínio | `{0, 1, 8, 9}` (`contexto_1_geracao_dataset`) |
| Significado | Matriz expandida do tabuleiro 4×3 |

### Codificação

- `0`: aresta livre (não jogada).
- `9`: aresta jogada.
- `8`: ponto fixo (canto/intersecção do tabuleiro — não é aresta).
- `1`: caixa fechada (interior, célula `[2r+1, 2c+1]`).

### Validações

- `estados[i, r, c] ∈ {0, 1, 8, 9}` para todos `(i, r, c)`.
- Posições `[2r, 2c]` para `r ∈ {0..4}, c ∈ {0..3}` valem `8` (pontos fixos imutáveis).
- Posições `[2r+1, 2c+1]` para `r ∈ {0..3}, c ∈ {0..2}` valem `0` (caixa aberta) ou `1` (caixa fechada).
- Posições de aresta valem `0` ou `9`.

### Transições

- **Fase A.1**: produzido pelo gerador a partir de `mat_inicial = zeros + pontos_fixos` + sequência de jogadas. Persistido no NPZ.
- **Fase A.2**: lido (sem modificação) para alimentar `extrair_canais()`. **Não modificado pela A.2**.

---

## 2. Entidade: `Tensor de canais` (`canais[i]`)

| Campo | Valor |
|---|---|
| Shape | `(4, 3, 11)` |
| Dtype | `int8` |
| Domínio | `{0, 1}` (binário em todos os 11 canais) |
| Significado | Tensor pré-computado de entrada da CNN |

### Estrutura por slot K

| K | Canal | Categoria | Origem (Fase) |
|---|---|---|---|
| 0 | `aresta_topo` | Geométrico | Pré-computado (era Lambda no V5) |
| 1 | `aresta_base` | Geométrico | Pré-computado (era Lambda no V5) |
| 2 | `aresta_esquerda` | Geométrico | Pré-computado (era Lambda no V5) |
| 3 | `aresta_direita` | Geométrico | Pré-computado (era Lambda no V5) |
| 4 | `caixa_fechada` | Geométrico | Pré-computado (era Lambda no V5) |
| 5 | `eh_grau3` | Estrutural | A.2 |
| 6 | `eh_grau2` | Estrutural | A.2 |
| 7 | `em_cadeia_curta` | Estrutural | A.2 |
| 8 | `em_cadeia_longa` | Estrutural | A.2 |
| 9 | `em_loop` | Estrutural | A.2 |
| 10 | `em_cadeia_aberta_uma_ponta` | Estrutural | A.2 |

### Regras de exclusão mútua

- Para qualquer caixa `(r, c)` com `canais[r, c, 4] == 1` (fechada), **todos os canais 5–10 valem 0** nessa célula. "Grau", "cadeia" e "loop" só fazem sentido em caixas abertas.
- Para qualquer caixa `(r, c)` aberta com grau 3, `canais[r, c, 5] == 1` e `canais[r, c, 6] == 0`.
- Cadeias curta e longa são mutuamente exclusivas por componente (componente de comprimento ≤ 2 marca canal 7; comprimento ≥ 3 marca canal 8).

### Algoritmo de derivação

Especificação completa em `contracts/canais_estruturais.md`.

### Transições

- **Fase A.1**: **NÃO presente no NPZ**.
- **Fase A.2**: computado por `extrair_canais(estados[i])` e adicionado ao NPZ via sobrescrita atômica.
- **Fases B/C/D/E/F**: lido do NPZ; sliced por fase (`canais[..., :5]` em B/C; `canais[..., :11]` em D/E/F).

---

## 3. Entidade: `Vetor de scores` (`scores[i]`)

| Campo | Valor |
|---|---|
| Shape | `(31,)` |
| Dtype | `float32` |
| Significado | Q-values do Minimax(p=9) por aresta canônica |

### Validações

- `scores[i, k] ∈ [-6.0, +6.0]` para arestas legais (caixa líquida pode ser de -6 a +6 em 4×3).
- `scores[i, k] == -1e9` para arestas inválidas (já jogadas ou fora do tabuleiro lógico).
- Ordem das 31 entradas é fixada por `labels_canonicos[k]` (ver entidade abaixo).

### Transições

- **Fase A.1**: produzido pelo Minimax(p=9). Persistido no NPZ.
- **Fase A.2**: lido (sem modificação).
- **Fase E**: usado para calcular `Δ_top2` por amostra.
- **Fase F**: usado para calcular `value_target = clip(score_max / 6.0, -1, +1)`.

---

## 4. Entidade: `Label canônico` (`rotulos[i]`)

| Campo | Valor |
|---|---|
| Shape | `()` (escalar por amostra) |
| Dtype | `str` (numpy `<U10` ou `<U16`) |
| Significado | Nome canônico da melhor aresta segundo o supervisor |

### Convenção de nomenclatura

- Formato: `H_r_c` (aresta horizontal na linha `r`, coluna canônica `c`) ou `V_r_c` (aresta vertical).
- Existe uma única jogada ótima escolhida por desempate (PRD não detalha; herda do V4).

### Transições

- **Fase A.1**: produzido. Persistido.
- **Fase A.2**: lido (sem modificação).
- **Fase C**: simetrias permutam o label conforme tabela em `permutacoes_simetria_pontinhos.py`.

---

## 5. Entidade: `Modo de geração` (`generation_mode[i]`)

| Campo | Valor |
|---|---|
| Shape | `()` |
| Dtype | `int8` |
| Domínio | `{0, 1, 2, 3}` |

### Significado

| Valor | Modo |
|---|---|
| 0 | `uniform` (preenchimento aleatório de traços) |
| 1 | `sim_l1` — **DESLIGADO** em A.1 (peso 0 em `STRAT_WEIGHTS`) |
| 2 | `sim_l2` (autoplay Minimax(p=2) × Minimax(p=2)) |
| 3 | `sim_l3` (autoplay Minimax(p=3) × Minimax(p=3)) |

### Transições

- **Fase A.1**: gravado pelo gerador.
- Demais fases: lido (sem modificação).

---

## 6. Entidade: `Labels canônicos` (`labels_canonicos`)

| Campo | Valor |
|---|---|
| Shape | `(31,)` |
| Dtype | `str` (`<U10` típico) |
| Significado | Lista canônica de labels na mesma ordem do eixo K de `scores` |

### Validações

- `labels_canonicos[k]` ∈ {`"H_r_c"`, `"V_r_c"`} com `(r, c)` válidos para o tabuleiro 4×3.
- Total: 31 entradas (4 colunas × 4 linhas + 1 = 16 horizontais + 3 colunas × 5 linhas = 15 verticais? — herda do V4 a contagem exata).

### Transições

- **Fase A.1**: gravado uma vez por NPZ.
- Demais fases: lido (sem modificação).

---

## 7. Entidade: `Profundidade do supervisor` (`minimax_depth`)

| Campo | Valor |
|---|---|
| Shape | `(1,)` |
| Dtype | `int32` |
| Valor canônico | `9` (Minimax(p=9)) |

### Transições

- **Fase A.1**: gravado uma vez por NPZ.
- Demais fases: lido (auditoria).

---

## 8. Entidade: `Nomes canônicos dos canais` (`nomes_canais`)

| Campo | Valor |
|---|---|
| Shape | `(11,)` |
| Dtype | `<U32` (numpy unicode string até 32 chars) |
| Significado | Auto-descrição do tensor `canais` |

### Conteúdo canônico

```python
NOMES_CANAIS = (
    "aresta_topo", "aresta_base", "aresta_esquerda", "aresta_direita",
    "caixa_fechada",
    "eh_grau3", "eh_grau2",
    "em_cadeia_curta", "em_cadeia_longa", "em_loop",
    "em_cadeia_aberta_uma_ponta",
)
```

### Validações (gate de A.2)

- `nomes_canais.shape == (11,)`.
- `np.array_equal(nomes_canais, np.array(NOMES_CANAIS, dtype="U32"))` em **todos** os NPZs do diretório.
- O teste `test_analisador_estrutural_pontinhos.py` falha o merge se divergir byte-a-byte.

### Transições

- **Fase A.1**: **NÃO presente no NPZ**.
- **Fase A.2**: criado e gravado pela primeira vez.
- Demais fases: lido (auditoria).

---

## 9. Entidade: `Snapshot da COMPLEMENTO_POR_CELULA` (auditoria)

> Não é campo do NPZ — é entrada documental em `docs/historico_decisoes.md` (FR-A-07, SC-D-06).

### Conteúdo (PRD §4.1.3 rev.5 — cotas finais do `Consolidar_500k_Final.ipynb`)

```python
# cota_alvo rev.5 — todas as cotas capeadas nos únicos reais disponíveis.
cota_alvo = {
    (0, (5, 11)):  2_775,  (0, (12, 17)):  7_879,  (0, (18, 23)):  11_031,
    (0, (24, 28)): 3_289,  (0, (29, 30)):     25,
    (2, (5, 11)): 22_200,  (2, (12, 17)): 67_898,  (2, (18, 23)):  83_787,
    (2, (24, 28)):26_317,  (2, (29, 30)):     84,
    (3, (5, 11)): 30_526,  (3, (12, 17)): 94_099,  (3, (18, 23)): 128_735,
    (3, (24, 28)):21_261,  (3, (29, 30)):     94,
}
# mode_0=24.999, mode_2=200.286, mode_3=274.715, total=500.000
# Consolidação empírica: 499.997 (shortfall 3 — arredondamento)
```

### Transições

- **Fase A.1 (planejamento)**: tabela embutida literalmente na célula de parâmetros do notebook V5 (sem leitura externa).
- **Fase A.1 (execução)**: gera o complemento.
- **Consolidação (rev.5)**: `Consolidar_500k_Final.ipynb` filtra 3 fontes (legado + v5_databricks + v5_local) contra `cota_alvo` e produz 100 NPZs com 499.997 estados únicos.
- **Pós-execução**: snapshot fiel da tabela usada vai para `docs/historico_decisoes.md` como prova de auditoria.

---

## 10. Esquema do NPZ por fase

### NPZ Fase A.1 (saída do Databricks)

| Campo | Shape | Dtype |
|---|---|---|
| `estados` | `(N, 9, 7)` | `int8` |
| `rotulos` | `(N,)` | `<U10` |
| `scores` | `(N, 31)` | `float32` |
| `generation_mode` | `(N,)` | `int8` |
| `labels_canonicos` | `(31,)` | `<U10` |
| `minimax_depth` | `(1,)` | `int32` |

**Não contém** `canais` nem `nomes_canais`.

### NPZ Fase A.2 (saída do enriquecimento local)

Mesmos campos da Fase A.1 **+**:

| Campo | Shape | Dtype |
|---|---|---|
| `canais` | `(N, 4, 3, 11)` | `int8` |
| `nomes_canais` | `(11,)` | `<U32` |

### Sobrescrita atômica

- A regravação usa arquivo temporário `<original>.tmp` + `os.replace(<original>.tmp, <original>)` (NFR-06, FR-B-03).
- Nunca corrompe original mesmo com Ctrl+C.
- Idempotente por sobrescrita (FR-B-04).

---

## 11. Saída

Modelo de dados completo. Próximos artefatos: `contracts/canais_estruturais.md` (algoritmo dos 11 canais), `contracts/npz_schema.md` (formato concreto dos NPZ por fase), `quickstart.md` (fluxo do desenvolvedor).
