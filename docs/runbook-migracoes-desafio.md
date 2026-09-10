# Runbook — aplicar as migrações `0018`, `0019` e `0020` (Desafio do Dia)

**Escrito em 10/09/2026**, e **executado no `des` no mesmo dia** — as três
migrações estão aplicadas lá (revisão `0020`), e ⛔ **no `prd` não**. Ele é
autossuficiente: não depende da conversa em que foi escrito, e serve tanto para o
`prd`, quando chegar a hora, quanto para reaplicar no `des` depois de uma
correção de modelagem.

| migração | o que faz | risco |
|---|---|---|
| `0018_schema_desafio` | cria o schema `desafio` — 6 tabelas, 6 VIEWs, 2 índices, e os `INSERT` das duas primeiras dimensões | schema **novo e vazio**: nada a perder |
| `0019_schema_desafio_dia` | cria o schema `desafio_dia` — 9 tabelas, 9 VIEWs | schema **novo e vazio**: nada a perder |
| `0020_partida_modo_desafio` | ⚠️ **toca `partida.tb001_partida`**, que tem dado real: troca o `CHECK` de `co_modo` para aceitar `'desafio'` | estritamente **aditiva** — a constraint nova é superconjunto da antiga, e nenhuma linha gravada deixa de passar |

> ⚠️ **O que foi aprovado é o `data-model.md`, não o código das migrações**
> (decisão do dono, 09/09/2026 — `DECISOES-do-dono.md` §8d). Quem garante que os
> dois dizem a mesma coisa é
> `tests/unitarios/test_migracao_bate_com_data_model.py`, que compara tabela a
> tabela, coluna a coluna **na ordem**, constraint a constraint e índice a
> índice, e não tem `skip` nem `xfail`.
> ⚠️ **O que continua valendo é a conferência de AMBIENTE** — que é outra coisa.

---

## Passo 0 — os testes ainda passam?

Rápido (~1 min) e vale a pena: é ele que sustenta a decisão de não ler o Alembic.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\pytest tests\unitarios\test_migracao_bate_com_data_model.py -q
```

Tem de sair **34 passed**. Se reprovar, ⛔ **não aplique nada**: a migração
divergiu do modelo aprovado, e o certo é consertar a migração.

---

## Passo 1 — QUE BANCO É ESTE? (obrigatório, e não é formalidade)

Os dois bancos se chamam `railway` — é o nome padrão do Postgres em todo projeto
Railway, e **o nome não distingue nada**. O `AMBIENTE` do `.env` também não: ele
diz como a API se comporta, não a qual banco ela se liga.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py
```

Ele é **somente leitura** e nunca imprime a senha. O que olhar primeiro:

- a linha do ambiente tem de dizer **DES** (`hopper.proxy.rlwy.net:21165`);
- `revisao do alembic` deve estar em `0017_poder_e_probing_base`;
- `schemas do projeto` **ainda não** deve listar `desafio` nem `desafio_dia`.

⛔ Se disser **PRD** (`hayabusa…:42857`) ou **DESCONHECIDO**, pare aqui.
"Desconhecido" é o resultado mais perigoso, não o mais inofensivo: é um banco que
ninguém catalogou.

---

## Passo 2 — aplicar

Leva segundos. A `head` dos arquivos é `0020_partida_modo_desafio`, e o `upgrade`
aplica as três em ordem, cada uma na sua transação.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python -m alembic upgrade head
```

Saída esperada: três linhas `Running upgrade …`, de `0017` até `0020`.

> ⚠️ **Se o passo 2 falhar no meio**, o Postgres desfaz a migração que falhou
> (DDL é transacional), mas **mantém** as anteriores. O `alembic current` do
> passo 3 dirá exatamente onde parou — não rode de novo antes de olhar.

---

## Passo 3 — conferir pelo ESTADO, não pelo código de saída

`upgrade` sem erro prova que os comandos rodaram, não que o banco ficou certo. A
`0017` ensinou que o defeito caro de migração é o **silencioso**.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\conferir_migracao_desafio.py
```

Também **somente leitura**. Ele confere, e nenhuma lista é escrita à mão — o
esperado sai das próprias migrações:

1. a revisão do alembic é `0020_partida_modo_desafio`;
2. as **15 tabelas** e as **15 VIEWs** existem, e nenhuma sobra;
2b. as **126 colunas**, **na ordem**, batem com o que a migração declara — e o
   parser não é escrito lá: é o mesmo do cadeado
   `test_migracao_bate_com_data_model.py`, porque duas implementações de leitura
   de SQL acabam discordando, e a que discordaria calada seria a que ninguém roda
   no CI;
3. as cinco dimensões que a migração popula têm linha — e
   `desafio.tb903_perfil_dificuldade` está **vazia**, de propósito: quem a
   preenche é o job;
4. o `CHECK` `ck_partida_modo` aceita `'desafio'`;
5. **AVISO** (não falha) para coluna de tabela que a VIEW irmã não expõe.

Última linha esperada: `OK - o banco esta como as migracoes 0018/0019/0020 mandam`.

---

## ⚠️ E se, depois disto, um defeito de modelagem aparecer

A regra §8b (dropa e recria) continua valendo até o `prd` subir — mas com o `des`
já migrado ela ganhou um passo que **não avisa**:

```
editar a 0018 e rodar `alembic upgrade head`  →  NÃO FAZ NADA
```

O alembic não reaplica revisão já aplicada. O arquivo passa a dizer uma coisa e o
`des` a ter outra, e `test_migracao_bate_com_data_model.py` fica **verde**: ele
compara o documento com o arquivo, e nenhum dos dois é o banco.

O caminho certo, depois de editar:

```powershell
.venv\Scripts\python -m alembic downgrade 0017_poder_e_probing_base
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python scripts\conferir_migracao_desafio.py
```

É a conferência 2b do passo 3 que pega o esquecimento — ela compara as colunas do
**banco** com as da migração, na ordem.

⛔ Isso deixa de ser possível no dia em que o `prd` subir, e é por isso que a §8b
tem prazo.

---

## E se precisar voltar

```powershell
.venv\Scripts\python -m alembic downgrade 0017_poder_e_probing_base
```

⚠️ **O `downgrade` da `0020` falha de propósito se já houver partida de desafio
gravada** — o `ADD CONSTRAINT` revalida a tabela e recusa as linhas com
`co_modo = 'desafio'`. Falhar alto é o comportamento certo: um downgrade que
apagasse essas linhas destruiria partidas de gente real.

---

## Depois do `des`, o `prd` — mas **ainda não**

⛔ Nada disto vai ao `prd` antes de o **portão T050** fechar. Quando for a hora,
o procedimento é o mesmo, trocando a `DATABASE_URL` do `.env` pela linha do
`hayabusa` e **rodando o passo 1 de novo** — a troca da URL sem reconferir é
exatamente o descuido de um segundo que o passo 1 existe para pegar.

⚠️ **A migração não roda no start**: não há `alembic upgrade` no `Dockerfile` nem
no `railway.json`, e isso é deliberado (mesma decisão da `0017`).
