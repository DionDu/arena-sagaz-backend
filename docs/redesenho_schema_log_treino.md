# Redesenho do schema do log de partidas/treino — PROPOSTA PARA VALIDAÇÃO

> **Status:** ✅ **VALIDADO pelo dono em 2026-07-12** (Q1–Q4 respondidas, §10).
> É o contrato do que será implementado.
> **Origem:** decisões de 2026-07-11 (`arena-sagaz-frontend/specs/006-conta-nuvem/checklist-producao.md`)
> + refinamentos de 2026-07-12 (códigos numéricos, prefixo `no_`, sem i18n na dimensão).
> **Objetivo:** cortar o custo de disco no Railway (o log de treino é o motor de
> crescimento) sem perder informação para o treino da IA.

---

## 0. O que mudou em relação ao checklist (refinamentos de 2026-07-12)

| Ponto | Checklist (11/07) | **Agora (12/07)** | Motivo |
|---|---|---|---|
| `co_acao` | `char(3)` (`CNN`/`CAP`/…) | **`nu_acao smallint`** | 5 valores reais, 3 deles CNN — três letras ficariam ilegíveis |
| `co_situacao` | `char(3)` | **`nu_situacao smallint`** | coerência com a tabela de jogada |
| `co_tipo_xp` | `char(3)` | **`nu_tipo_xp smallint`** | 6 valores; três letras ficariam ilegíveis |
| descrição na dimensão | `ds_x` + `ds_x_en` + `ds_x_es` | **`no_x`, sem i18n** | o dono não usa `ds_`; usa `no_` (nome) e `de_` (texto longo). Os JOINs são para relatório interno |
| `co_status` e cia. | manter descritivo | **manter descritivo** ✅ | 1 linha por partida — legibilidade vence |
| migração | dropar se preciso | **pode dropar/limpar tudo, des E prd** | dados dos dois bancos são de teste, descartáveis |

⚠️ **Correção importante encontrada no código:** o checklist previa 4 códigos de
ação (`CNN`/`CAP`/`MMX`/`ALE`), mas o app emite **5 valores** e **três deles são
CNN diferentes**. Colapsá-los perderia — para sempre — a distinção entre o núcleo
top-p (Pita/Cacau) e o argmax (Magno). `MMX` e `ALE` **não existem** no app hoje.
O desenho abaixo é fiel aos 5 valores reais
(`lib/modulos/jogos/pontinhos/logica/oraculo.dart:43`).

---

## 1. Convenção adotada

- **Dimensões** na faixa 900 (`tb901_…`, `tb902_…`), mesmo padrão de nome das demais,
  **sem** `dim` no nome. A numeração **pode repetir entre schemas**.
- A **chave tem o mesmo nome** na dimensão (PK) e no fato (FK): `nu_acao`, `nu_situacao`…
- **`nu_…`** = código numérico (aqui, a chave da dimensão). **`no_…`** = nome.
  **`co_…`** = código textual (aqui, a **string canônica que o app envia**).
- Cada dimensão guarda **as duas coisas**:
  - `co_…` → a string que chega no payload (`'cnn_nucleo_top_p'`). **É a tabela de
    tradução da ingestão**: o backend faz `co_ → nu_` ao gravar.
  - `no_…` → o nome legível, para os seus relatórios.
- **Sem colunas por idioma.** App e backend trabalham com o código; o JOIN é seu.
- **Nada de `ENUM` nativo do Postgres.**
- Toda tabela ganha sua **VIEW** (`vwNNN_…`), mantendo a regra "ler pela VIEW,
  escrever na tabela".

---

## 2. Dimensões novas (4 tabelas)

### 2.1 `jogo_pontinhos.tb901_jogada_acao` — COMO a CPU decidiu o lance

```sql
CREATE TABLE jogo_pontinhos.tb901_jogada_acao (
  nu_acao SMALLINT    PRIMARY KEY,
  co_acao VARCHAR(30) NOT NULL UNIQUE,  -- string canônica enviada pelo app
  no_acao VARCHAR(40) NOT NULL          -- nome legível (relatório)
);
```

| `nu_acao` | `co_acao` (do app) | `no_acao` |
|---|---|---|
| 1 | `captura_gulosa` | Captura gulosa |
| 2 | `cnn_nucleo_top_p` | CNN — núcleo top-p |
| 3 | `cnn_argmax_absoluto` | CNN — argmax absoluto |
| 4 | `cnn_argmax_desempatado` | CNN — argmax desempatado |
| 5 | `heuristica_gulosa` | Heurística gulosa (reserva) |
| **9999** | `desconhecido` | Desconhecido (código novo) |

*(1 = fecha caixa de graça na fase gulosa, sem consultar a CNN. 5 = oráculo de
reserva, sem rede neural. 9999 = ver §6, política de código desconhecido.)*

### 2.2 `jogo_pontinhos.tb902_jogada_situacao` — fase/contexto do lance

```sql
CREATE TABLE jogo_pontinhos.tb902_jogada_situacao (
  nu_situacao SMALLINT    PRIMARY KEY,
  co_situacao VARCHAR(20) NOT NULL UNIQUE,
  no_situacao VARCHAR(30) NOT NULL
);
```

| `nu_situacao` | `co_situacao` | `no_situacao` |
|---|---|---|
| 1 | `tatica` | Tática (não fechou caixa) |
| 2 | `captura` | Captura (fechou caixa) |
| **9999** | `desconhecido` | Desconhecido |

### 2.3 `partida.tb901_jogada_origem_decisao` — quem/o que originou o lance

```sql
CREATE TABLE partida.tb901_jogada_origem_decisao (
  nu_origem_decisao SMALLINT    PRIMARY KEY,
  co_origem_decisao VARCHAR(15) NOT NULL UNIQUE,
  no_origem_decisao VARCHAR(30) NOT NULL
);
```

| `nu_origem_decisao` | `co_origem_decisao` | `no_origem_decisao` |
|---|---|---|
| 1 | `humano` | Humano |
| 2 | `cpu` | CPU |
| 3 | `timeout_auto` | Tempo esgotado (automático) |
| **9999** | `desconhecido` | Desconhecido |

> ✅ **DECIDIDO (Q1, 2026-07-12):** numérico, como está. Ele mora na tabela mais
> quente do banco (31 linhas/partida) e fica na mesma família dos demais códigos
> de fato.

### 2.4 `partida.tb902_tipo_xp` — a natureza da parcela de XP

```sql
CREATE TABLE partida.tb902_tipo_xp (
  nu_tipo_xp SMALLINT    PRIMARY KEY,
  co_tipo_xp VARCHAR(20) NOT NULL UNIQUE,
  no_tipo_xp VARCHAR(30) NOT NULL
);
```

| `nu_tipo_xp` | `co_tipo_xp` | `no_tipo_xp` |
|---|---|---|
| 1 | `resultado` | Resultado da partida |
| 2 | `caixas` | Bônus de caixas |
| 3 | `dificuldade` | Bônus de dificuldade |
| 4 | `primeira_vitoria` | Primeira vitória |
| 5 | `conquista` | Conquista |
| 6 | `ajuste` | Ajuste (teto diário de XP) |
| **9999** | `desconhecido` | Desconhecido |

*(O checklist listava só 4 — faltavam `primeira_vitoria` e `conquista`, que estão
no `CHECK` do banco e o app **realmente envia**: `partida_screen.dart:736`.)*

---

## 3. Fatos alterados

### 3.1 `partida.tb001_partida` — fuso do jogador (PASSO 1)

```sql
ALTER TABLE partida.tb001_partida
  ADD COLUMN nu_offset_minuto_j1 SMALLINT,  -- offset UTC em MINUTOS (ex.: -180 = BRT)
  ADD COLUMN nu_offset_minuto_j2 SMALLINT,  -- NULL em vs_cpu (não há J2 humano)
  ADD CONSTRAINT ck_partida_offset_j1
      CHECK (nu_offset_minuto_j1 IS NULL OR nu_offset_minuto_j1 BETWEEN -840 AND 840),
  ADD CONSTRAINT ck_partida_offset_j2
      CHECK (nu_offset_minuto_j2 IS NULL OR nu_offset_minuto_j2 BETWEEN -840 AND 840);
```

**Por quê:** `timestamptz` guarda o **instante**, não o fuso de origem. Sem o offset
não dá para saber que a partida foi jogada "às 21h da noite do jogador" — dado que
interessa para análise de comportamento. Faixa −840..+840 = UTC−14 a UTC+14 (os
extremos reais existentes).

*(Nome por extenso — `minuto`, não `min` — de propósito: `min` seria lido como
"mínimo" daqui a seis meses. Decisão do dono, 2026-07-12.)*

**INALTERADOS** (regra de ouro — 1 linha por partida, legibilidade vence):
`co_jogo`, `co_variante`, `co_modo`, `co_dificuldade`, **`co_status`**.

### 3.2 `partida.tb002_jogada` — origem vira FK

```sql
-- co_origem_decisao VARCHAR(15) + CHECK   →   nu_origem_decisao SMALLINT + FK
nu_origem_decisao SMALLINT NOT NULL REFERENCES partida.tb901_jogada_origem_decisao(nu_origem_decisao)
```
Ganho: 16 B → 2 B por lance. São **31 lances/partida** (a tabela mais quente do banco).

### 3.3 `partida.tb003_xp_partida` — tipo de XP vira FK

```sql
-- co_tipo_xp VARCHAR(20) + CHECK   →   nu_tipo_xp SMALLINT + FK
nu_tipo_xp SMALLINT NOT NULL REFERENCES partida.tb902_tipo_xp(nu_tipo_xp)
```

### 3.4 `jogo_pontinhos.tb002_jogada` — **o coração da economia** (PASSOS 2 e 3)

```sql
CREATE TABLE jogo_pontinhos.tb002_jogada (
    id_jogada            UUID PRIMARY KEY
        REFERENCES partida.tb002_jogada(id_jogada) ON DELETE CASCADE,
    co_jogador           SMALLINT    NOT NULL,   -- ⚠️ +1 / -1 — CONTRATUAL, não mexer
    co_aresta            VARCHAR(15) NOT NULL,   -- 'H_0_1' — texto, sem dimensão
    nu_caixas_fechadas   SMALLINT    NOT NULL,
    nu_acao              SMALLINT REFERENCES jogo_pontinhos.tb901_jogada_acao(nu_acao),
    nu_situacao          SMALLINT REFERENCES jogo_pontinhos.tb902_jogada_situacao(nu_situacao),
    ar_probabilidade_cnn REAL[],                 -- float4[], 31 posições DENSAS
    ar_score_busca       REAL[],                 -- idem
    nu_profundidade      INT,
    js_extra             JSONB
);
-- ❌ REMOVIDAS: ar_tabuleiro_antes, ar_tabuleiro_apos  (~158 B cada)
```

**Por que remover as matrizes:** elas são **100% reconstruíveis** da sequência de
arestas (`co_aresta` + `co_jogador` + `nu_ordem`), aplicando o
`contrato_codificacao_pontinhos.json` — que **NÃO muda**. Guardá-las é pagar disco
por algo que sabemos recalcular.

**Impacto medido:** ~24 KB → ~11 KB por partida. A 5.000 partidas/dia:
**~3,6 GB/mês → ~1,7 GB/mês.**

**INALTERADOS e por quê:**

| Coluna | Motivo |
|---|---|
| `co_jogador` (±1) | Valores **contratuais** (aparecem na matriz da CNN). Nome fica: para a rede, o jogador é uma **classe**, não uma quantidade. |
| `co_aresta` (`H_0_1`) | **Texto, sem dimensão.** Um índice numérico seria ambíguo entre variantes (pequeno/médio/grande têm espaços de ação distintos). É autodescritivo e vale para qualquer tabuleiro. E, sem as matrizes, **vira o dado mais crítico da tabela** — mantê-lo legível é ainda mais valioso. *(Custo: ~19 MB/mês — ruído.)* |
| `ar_probabilidade_cnn` / `ar_score_busca` | Já são `float4[]` — tamanho ótimo. **Manter o vetor DENSO de 31 posições** (0 nas arestas inválidas/preenchidas, **NUNCA NULL**): o treino precisa da distribuição completa e o vetor sem buracos evita erro em cálculo futuro. |

*(Nota: `co_aresta` continua `VARCHAR(15)` e não `VARCHAR(8)` — `varchar` é de
comprimento variável, então o limite maior **não custa byte nenhum**. Só relaxa a
restrição para variantes futuras com grade grande.)*

### 3.5 `conta.tb005_dispositivo_notificacao` — idioma + fuso (PASSO 2)

```sql
ALTER TABLE conta.tb005_dispositivo_notificacao
  ADD COLUMN co_fuso          VARCHAR(64),  -- IANA: 'America/Sao_Paulo'
  ADD COLUMN nu_offset_minuto SMALLINT;     -- -180 (snapshot/fallback)
```

- **`co_idioma CHAR(2) NOT NULL` — JÁ BASTA.** É ISO 639-1 (`pt`/`en`/`es`), que é
  o necessário para escolher o texto do push. **Nada a fazer.**
- **Por que os dois (IANA + offset):** o **IANA resolve horário de verão sozinho** —
  é o que o worker de campanha vai precisar. O offset é snapshot para consulta
  rápida e **fallback** se o IANA não vier.
- **Nullable de propósito:** apps antigos (já publicados) não mandam esses campos.
- 🎁 O fuso IANA dá uma **pista do país** sem coletar IP nem GPS.
- ⚖️ Declarar no Data Safety (Play) / App Privacy (Apple) como dados de dispositivo.

⚠️ **Pegadinha do Postgres:** as VIEWs foram criadas com `SELECT *`, e o Postgres
**congela** a lista de colunas na criação. Toda view sobre tabela alterada precisa
ser **derrubada e recriada**, senão as colunas novas não aparecem:
`partida.vw001_partida`, `partida.vw002_jogada`, `jogo_pontinhos.vw002_jogada`,
`conta.vw005_dispositivo_notificacao`.

---

## 4. Migração (Alembic `0006`)

Você autorizou limpar/dropar **nos dois ambientes** (des **e** prd) — os dados são
seus, de teste, descartáveis.

| Objeto | Ação | Perde o quê? |
|---|---|---|
| `partida.*`, `jogo_pontinhos.*` | **DROP + CREATE** com o novo desenho | partidas/jogadas de teste |
| `progressao.tb001/tb002/tb003` | **TRUNCATE** (estrutura fica) | XP, nível, conquistas e lotes de teste |
| `conta.*` | **ALTER** (só `tb005` ganha 2 colunas) | **nada — suas contas ficam** |
| `log.*` | intacto | nada |

**Por que truncar a progressão:** o XP acumulado é derivado do log de partidas. Se
o log zera e a progressão não, o ranking passa a mostrar XP sem partida que o
justifique — inconsistência permanente. Zerar os dois deixa o banco coerente.

✅ **Q3 (2026-07-12): confirmado.** O dono autorizou inclusive apagar as tabelas de
`conta` (são 2 usuários por ambiente, recadastráveis no Firebase). **Não é
necessário**: o `conta` só recebe `ALTER` (colunas novas em `tb005`), e nada nele
depende do log. Manter as contas evita mexer no Firebase à toa — se algo der
errado, apagá-las continua sendo uma opção, a qualquer momento.

O `downgrade()` recria o schema antigo (com as matrizes) — mas, obviamente, **sem
os dados**.

---

## 5. Ingestão TOLERANTE (o backend sobe ANTES do app)

O app publicado hoje **ainda manda o payload antigo**. O backend novo precisa
aceitar **os dois formatos** — senão a fila de sincronização dos apps em campo
trava. Regras:

| Campo do payload | Comportamento do backend |
|---|---|
| `ar_tabuleiro_antes` / `ar_tabuleiro_apos` | **Aceitar e IGNORAR** (não existe mais coluna). Sem erro. |
| `co_acao` (string) | **Traduzir** para `nu_acao` via `tb901_jogada_acao.co_acao`. |
| `co_situacao` (string) | Traduzir para `nu_situacao`. |
| `co_origem_decisao` (string) | Traduzir para `nu_origem_decisao`. |
| `co_tipo_xp` (string) | Traduzir para `nu_tipo_xp`. |
| `nu_offset_minuto_j1` / `_j2` | **Opcional** (o app começa a enviar depois). Ausente → NULL. |
| `co_fuso` / `nu_offset_minuto` (dispositivo) | **Opcional**. Ausente → NULL. |

O app **continua enviando as strings** — a tradução é do backend, na ingestão.
**O contrato da CNN e o frontend não mudam** por causa disto.

---

## 6. ✅ Política de código DESCONHECIDO — `9999`

**O cenário:** o app publicado na loja é uma versão **mais nova** que o backend
(ou o backend fica para trás num deploy). Ele manda uma estratégia de IA nova
(`co_acao: 'cnn_temperatura'`). A FK não encontra → **erro 500** → o evento fica
**preso para sempre** na fila de sincronização do aparelho.

**Decidido (Q2, 2026-07-12): `nu_… = 9999` em todas as dimensões.**
- `nu_acao` / `nu_situacao` são **anuláveis** → poderiam ir a NULL, mas NULL já
  significa "lance humano, sem telemetria". Usar **9999 = desconhecido** preserva a
  diferença entre *"não se aplica"* e *"não sei o que é isto"*.
- `nu_origem_decisao` / `nu_tipo_xp` são **NOT NULL** → **9999** é a única saída sem 500.
- A **string crua** vai para `js_extra` (e para `log.tb001_evento_sync_rejeitado`),
  para você descobrir o que apareceu e cadastrar o código de verdade depois.

**Por que 9999 e não 99:** deixa uma **faixa larga e óbvia** para os códigos reais
(1…N) sem risco de um dia esbarrarem no valor sentinela — e `9999` "salta aos
olhos" num relatório, que é justamente o efeito desejado. Cabe folgado em
`smallint` (que vai até 32.767).

Resultado: nada de 500, nada de fila travada, nenhum dado perdido — e um rastro
claro do que precisa ser cadastrado.

---

## 7. Utilitário de reconstrução do tabuleiro

**Boa notícia: a peça já existe.**
`gerador_dados/jogo_pontinhos/tabuleiro_pontinhos.py` traz
`EstadoTabuleiro.de_tamanho(variante)` e `aplicar_traco(label, jogador)` — que é
exatamente a primitiva da reconstrução. Não vou reinventar regra de jogo.

```python
# gerador_dados/jogo_pontinhos/reconstrutor_partida_pontinhos.py  (NOVO)
estado = EstadoTabuleiro.de_tamanho(co_variante)      # de partida.tb001_partida
for jogada in jogadas_ordenadas_por_nu_ordem:         # co_aresta + co_jogador
    estado.aplicar_traco(jogada.co_aresta, jogada.co_jogador)
    yield estado.matriz.copy()                        # == o antigo ar_tabuleiro_apos
    # (o "antes" é a matriz do passo anterior)
```

**Usado em:** exportação do dataset de treino e, no futuro, no relatório Web da partida.

**Validação de integridade (importante):** sem as matrizes, uma jogada faltante
deixa de ser detectável de outra forma. O utilitário vai **recusar** a partida se:
- as ordens (`nu_ordem`) não forem contíguas de 1 a N;
- alguma aresta não existir na variante do tabuleiro;
- alguma aresta se repetir.

E vou escrever um **teste que prova a equivalência**: pega partidas com as matrizes
ainda gravadas, reconstrói a partir das arestas e compara **byte a byte**. Só depois
disso a remoção das colunas é segura.

---

## 8. ✅ Verificação já feita: timestamps em UTC

O app agora envia ISO-8601 com sufixo `Z`. Confirmei que
`api/sincronizacao/repositorio.py:39` (`_dt`) faz
`datetime.fromisoformat(valor.replace("Z", "+00:00"))` → gera um `datetime`
**com fuso**, e o asyncpg grava o **instante correto** no `timestamptz`.
**Nada a corrigir aqui.** *(O bug antigo era o app mandar "naive" e o backend
interpretar como UTC, deslocando pelo offset local — 21h virava 18h.)*

---

## 9. NÃO fazer agora (só registrar)

- **Offload periódico do log de treino** (mover para CSV/banco local e podar do
  Railway). É a alavanca **estrutural** de custo: mesmo otimizado, 5.000
  partidas/dia crescem ~1,7 GB/mês. Fica planejado, não implementado.
- **Módulo de campanha de push** (token + worker agendado, com idioma e hora local).
  Os dados do PASSO 2 existem justamente para **preparar o terreno** — eles não
  podem ser preenchidos retroativamente.

---

## 10. ✅ Decisões fechadas (2026-07-12)

| # | Pergunta | Decisão |
|---|---|---|
| **Q1** | `nu_origem_decisao` numérico ou textual? | **Numérico** (mantida a proposta). |
| **Q2** | Código para "desconhecido"? | **Sim — `9999`** (não `99`): faixa larga, salta aos olhos no relatório. |
| **Q3** | Truncar `progressao.*` junto com o log? | **Sim.** As tabelas de `conta` também podem ser apagadas se preciso (2 usuários/ambiente, recadastráveis no Firebase) — mas **não será necessário**. |
| **Q4** | Outros ajustes de nome | **(a)** As 3 dimensões da jogada ganham `jogada_` no nome: `tb901_jogada_acao`, `tb902_jogada_situacao`, `tb901_jogada_origem_decisao`. **(b)** `nu_offset_min…` → **`nu_offset_minuto…`** (`min` seria lido como "mínimo" no futuro). |

**Nomes finais das 4 dimensões:**

| Schema | Tabela | PK |
|---|---|---|
| `jogo_pontinhos` | `tb901_jogada_acao` | `nu_acao` |
| `jogo_pontinhos` | `tb902_jogada_situacao` | `nu_situacao` |
| `partida` | `tb901_jogada_origem_decisao` | `nu_origem_decisao` |
| `partida` | `tb902_tipo_xp` | `nu_tipo_xp` |

*(A `tb902_tipo_xp` **não** leva `jogada_`: ela qualifica a parcela de XP da
partida, não um lance.)*
