# Contrato — Esquema dos NPZ por fase

**Branch**: `004-melhoria-geracao-dados-cnn` | **Data**: 2026-05-07
**Documento pai**: [plan.md](../plan.md)

> Esquema concreto dos arquivos NPZ produzidos/consumidos em cada fase do pipeline. Espelha `data-model.md` §10.

---

## 1. NPZ Fase A.1 (saída do Databricks, antes do enriquecimento)

```python
np.savez(
    arquivo,
    estados=estados,                  # (N, 9, 7) int8
    rotulos=rotulos,                  # (N,) <U10
    scores=scores,                    # (N, 31) float32
    generation_mode=generation_mode,  # (N,) int8
    labels_canonicos=labels_canonicos,# (31,) <U10
    depth=depth,                      # (1,) int32
)
```

**Restrições**:
- `estados[i, j, k] ∈ {0, 1, 8, 9}`.
- `scores[i, k] ∈ [-6.0, 6.0] ∪ {-1e9}`.
- `generation_mode[i] ∈ {0, 2, 3}` (modo 1 desligado).
- N por arquivo = 5.000 (batch padrão do V4, mantido).
- **NÃO contém** `canais` nem `nomes_canais`.

---

## 2. NPZ Fase A.2 (saída do enriquecimento local)

Mesmos campos da Fase A.1 **+**:

```python
np.savez(
    arquivo,
    # Campos preservados:
    estados=estados,
    rotulos=rotulos,
    scores=scores,
    generation_mode=generation_mode,
    labels_canonicos=labels_canonicos,
    depth=depth,
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
| Total ≥ 500.000 estados únicos por `mat.tobytes()` | Auditoria pós-A.1 (script ad-hoc) e pós-A.2 (auditoria do diretório) |
| Distribuição empírica ±2pp das cotas D1/D1.a | Auditoria pós-A.1, registrada em `historico_decisoes.md` |
| `nomes_canais` igual em todos os NPZs do diretório | Teste `test_analisador_estrutural_pontinhos.py` |
| Sobrescrita atômica não corrompe original | NFR-06; testado por simulação de Ctrl+C durante A.2 |

---

## 4. Versionamento dos NPZ

- **Sem campo `versao`** dentro do NPZ. A versão é implícita pelo conjunto de campos presentes:
  - **v1 (Fase A.1)**: 6 campos (sem `canais`).
  - **v2 (Fase A.2)**: 8 campos (com `canais` + `nomes_canais`).
- Auditoria por `np.load(arquivo).files` — lista de campos.

---

**Fim do esquema NPZ.**
