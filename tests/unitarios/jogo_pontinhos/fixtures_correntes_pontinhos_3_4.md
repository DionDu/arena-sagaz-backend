# Fixtures de Estados Canônicos — `ia-pontinhos-3-4`

**Branch**: `003-jogador-hibrido` | **Gerado por**: T005 (Phase 1, tasks.md)
**Builders**: `gerador_dados/jogo_pontinhos/gerador_pontinhos.py`

Este arquivo é uma **referência humana** dos 40 estados canônicos (8 tipos × 5
variantes) usados pelos testes `test_correntes_pontinhos_3_4.py` (T020 e T027).
Se a representação ASCII de algum estado parecer errada visualmente, o builder
está errado — corrija o builder, **não o teste**.

## Convenções

- **Tabuleiro**: 3x4 (4 linhas × 3 colunas de caixas), matriz shape `(9, 7)`.
- **Domínio**: `{-1, 0, 1, 8}` — domínio de partida (contrato contexto 3 de
  `contrato_codificacao_pontinhos.json`).
  - `8` = ponto fixo da grade (par×par).
  - `0` = aresta livre OU caixa não fechada.
  - `+1` = aresta colocada pelo Jogador 1 OU caixa fechada pelo Jogador 1.
  - `-1` = aresta colocada pelo Jogador 2 OU caixa fechada pelo Jogador 2.
- **Marker por variante**: `+1` em variantes pares (0, 2, 4); `-1` em variantes
  ímpares (1, 3) — para cobrir ambos os jogadores ao longo das estruturas.
- **ASCII**:
  - `.` = ponto fixo da grade.
  - `---` = aresta horizontal preenchida (qualquer valor != 0).
  - `   ` (3 espaços) = aresta horizontal livre.
  - `|` = aresta vertical preenchida.
  - ` ` = aresta vertical livre.
  - `[1] ` = caixa fechada pelo Jogador 1.
  - `[-1]` = caixa fechada pelo Jogador 2.
  - `[ ] ` = caixa não fechada.

## Sumário

| Tipo | Builder | Variantes | Total |
|---|---|---|---|
| Corrente curta (1-2 cx) | `construir_estado_corrente_curta(0..4)` | 5 | 5 |
| Corrente longa (3-7 cx) | `construir_estado_corrente_longa(0..4)` | 5 | 5 |
| Ciclo de 4 caixas | `construir_estado_ciclo(4, 0..4)` | 5 | 5 |
| Ciclo de 6 caixas | `construir_estado_ciclo(6, 0..4)` | 5 | 5 |
| Ciclo de 8 caixas | `construir_estado_ciclo(8, 0..4)` | 5 | 5 |
| Ciclo de 10 caixas | `construir_estado_ciclo(10, 0..4)` | 5 | 5 |
| Ramificada | `construir_estado_ramificada(0..4)` | 5 | 5 |
| Mistura | `construir_estado_mistura(0..4)` | 5 | 5 |
| **Total** | | | **40** |

---

## Corrente curta (1-2 caixas)
**Builder**: `construir_estado_corrente_curta`

### Variante 0 — 1 caixa isolada (canto sup-esq), 2 arestas livres na borda

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 0],
 [8, 1, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ] |[ ]  [ ]  
.---.   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Corrente de 2 caixas horizontais (linha do topo)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8, -1,  8, -1,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Corrente de 2 caixas verticais (coluna esquerda)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 0],
 [8, 1, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
 [ ] |[ ]  [ ]  
.---.   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 3 — 1 caixa isolada (canto inf-dir), 2 arestas livres na borda

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8, -1,  8],
 [ 0,  0,  0,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .---.
 [ ]  [ ] |[ ]  
.   .   .   .
```

---

### Variante 4 — Corrente de 2 caixas horizontais (meio-direita)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 1, 8],
 [0, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .---.
 [ ] |[ ]  [ ]  
.   .---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

## Corrente longa (3-7 caixas)
**Builder**: `construir_estado_corrente_longa`

### Variante 0 — Corrente de 3 caixas horizontais (linha do topo)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Corrente de 4 caixas verticais (coluna esquerda completa)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Corrente de 5 caixas em formato L (esq + base)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
|[ ] |[ ]  [ ]  
.   .---.---.
|[ ]  [ ]  [ ]  
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 3 — Corrente de 6 caixas em formato S (zigue-zague médio)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8, -1,  8,  0,  8, -1,  8],
 [ 0,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [ 0,  0,  0,  0, -1,  0, -1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0, -1,  0, -1],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .---.   .
|[ ]  [ ] |[ ]  
.---.   .---.
 [ ] |[ ]  [ ] |
.   .---.   .
 [ ]  [ ] |[ ] |
.   .   .   .
 [ ]  [ ] |[ ] |
.   .   .   .
```

---

### Variante 4 — Corrente de 7 caixas em formato zigue-zague longo

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 0, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .---.   .
|[ ]  [ ] |[ ]  
.---.   .---.
 [ ] |[ ]  [ ] |
.   .---.   .
 [ ] |[ ]  [ ] |
.   .   .---.
```

---

## Ciclo de 4 caixas
**Builder**: `construir_estado_ciclo(4, ...)`

### Variante 0 — Bloco 2x2 superior-esquerdo

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 1, 8, 1, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Bloco 2x2 superior-direito

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8, -1,  8, -1,  8],
 [ 0,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0, -1,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .---.---.
 [ ] |[ ]  [ ] |
.   .   .   .
 [ ] |[ ]  [ ] |
.   .---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Bloco 2x2 médio-esquerdo

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 1, 8, 1, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 3 — Bloco 2x2 inferior-esquerdo

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8, -1,  8, -1,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
```

---

### Variante 4 — Bloco 2x2 inferior-direito

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 1, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .---.---.
 [ ] |[ ]  [ ] |
.   .   .   .
 [ ] |[ ]  [ ] |
.   .---.---.
```

---

## Ciclo de 6 caixas
**Builder**: `construir_estado_ciclo(6, ...)`

### Variante 0 — Anel 2x3 no topo (linhas 1-3)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Anel 2x3 no meio (linhas 3-5)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Anel 2x3 no fundo (linhas 5-7)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 3 — Bloco 3x2 esquerdo (3 linhas x 2 colunas)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8, -1,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0,  0,  0, -1,  0,  0],
 [ 8, -1,  8, -1,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ] |[ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 4 — Bloco 3x2 direito (3 linhas x 2 colunas)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 1, 8, 1, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 1, 0, 1],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .---.---.
 [ ] |[ ]  [ ] |
.   .   .   .
 [ ] |[ ] |[ ] |
.   .   .   .
 [ ] |[ ]  [ ] |
.   .---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

## Ciclo de 8 caixas
**Builder**: `construir_estado_ciclo(8, ...)`

### Variante 0 — Anel 3x3 superior (sem centro 3,3) — caixa central fechada

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Anel 3x3 inferior (sem centro 5,3) — caixa central fechada

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 2 — Anel 3x3 superior (mesma topologia, marker +1)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 3 — Anel 3x3 inferior (mesma topologia, marker -1)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 4 — Anel 3x3 superior (mesma topologia, marker +1)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

## Ciclo de 10 caixas
**Builder**: `construir_estado_ciclo(10, ...)`

### Variante 0 — Anel 4x3 sem centros (3,3) e (5,3) — ambas fechadas — marker +1

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 1 — Mesma topologia — marker -1

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 2 — Mesma topologia — marker +1

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 3 — Mesma topologia — marker -1

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0, -1, -1, -1,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ] |[-1]|[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

### Variante 4 — Mesma topologia — marker +1

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 1, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 1, 1, 1, 0, 1],
 [8, 0, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 0, 0, 1],
 [8, 1, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ] |[1] |[ ] |
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
```

---

## Ramificada
**Builder**: `construir_estado_ramificada`

### Variante 0 — Pivô (3,3) com 3 ramos: topo, esquerda, direita

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 1, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ] |[ ] |[ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 1 — Pivô (3,3) com 4 ramos: topo, base, esquerda, direita

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0, -1,  0, -1,  0,  0],
 [ 8, -1,  8,  0,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8,  0,  8, -1,  8],
 [ 0,  0, -1,  0, -1,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ] |[ ] |[ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.---.   .---.
 [ ] |[ ] |[ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Pivô (5,3) com 3 ramos: topo, esquerda, direita

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 1, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ] |[ ] |[ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 3 — Pivô (3,1) com 3 ramos: cima, baixo, direita

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [-1,  0, -1,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0, -1,  0,  0],
 [ 8,  0,  8, -1,  8,  0,  8],
 [ 0,  0, -1,  0,  0,  0,  0],
 [ 8, -1,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
 [ ]  [ ] |[ ]  
.   .---.   .
 [ ] |[ ]  [ ]  
.---.   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 4 — Pivô (5,3) com 4 ramos: topo, esquerda, direita, baixo

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 1, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 0, 8, 1, 8],
 [0, 0, 1, 0, 1, 0, 0],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ] |[ ] |[ ]  
.---.   .---.
 [ ]  [ ]  [ ]  
.---.   .---.
 [ ] |[ ] |[ ]  
.   .   .   .
```

---

## Mistura
**Builder**: `construir_estado_mistura`

### Variante 0 — Corrente curta (2 cx topo) + ciclo de 4 (canto inf-esq)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 1, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 1, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 1, 8, 1, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ] |[ ]  [ ] |
.   .---.---.
 [ ]  [ ]  [ ]  
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
```

---

### Variante 1 — Corrente longa (3 cx linha 3) + corrente curta (1 cx topo-dir)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0, -1,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
 [ ]  [ ] |[ ]  
.---.---.---.
 [ ]  [ ]  [ ]  
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.   .   .   .
```

---

### Variante 2 — Ciclo de 4 (topo-esq) + corrente curta (2 cx fundo)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 1, 8, 1, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 0, 0, 1, 0, 0],
 [8, 1, 8, 1, 8, 0, 8],
 [0, 0, 0, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 1, 8],
 [0, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 0, 8, 0, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.---.---.   .
|[ ]  [ ] |[ ]  
.   .   .   .
|[ ]  [ ] |[ ]  
.---.---.   .
 [ ]  [ ]  [ ]  
.   .---.---.
 [ ] |[ ]  [ ] |
.   .   .   .
```

---

### Variante 3 — Duas correntes longas paralelas (linhas 1 e 7)

**Matriz crua (numpy, dtype int8)**:

```text
[[ 8,  0,  8, -1,  8,  0,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8, -1,  8, -1,  8, -1,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8,  0,  8,  0,  8,  0,  8],
 [ 0,  0,  0,  0,  0,  0,  0],
 [ 8, -1,  8, -1,  8, -1,  8],
 [-1,  0,  0,  0,  0,  0, -1],
 [ 8,  0,  8, -1,  8,  0,  8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .---.   .
|[ ]  [ ]  [ ] |
.---.---.---.
 [ ]  [ ]  [ ]  
.   .   .   .
 [ ]  [ ]  [ ]  
.---.---.---.
|[ ]  [ ]  [ ] |
.   .---.   .
```

---

### Variante 4 — Corrente longa (4 cx coluna esq) + ciclo de 4 (canto inf-dir)

**Matriz crua (numpy, dtype int8)**:

```text
[[8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 0],
 [8, 0, 8, 1, 8, 1, 8],
 [1, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 0, 8, 0, 8],
 [1, 0, 1, 0, 0, 0, 1],
 [8, 0, 8, 1, 8, 1, 8]]
```

**Visualização ASCII (estilo partida)**:

```text
.   .   .   .
|[ ] |[ ]  [ ]  
.   .   .   .
|[ ] |[ ]  [ ]  
.   .---.---.
|[ ] |[ ]  [ ] |
.   .   .   .
|[ ] |[ ]  [ ] |
.   .---.---.
```

---

