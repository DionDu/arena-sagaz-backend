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

---

## ⏳ A `0022_motor_decifravel` — escrita em 11/09/2026, **ainda não aplicada**

| migração | o que faz | risco |
|---|---|---|
| `0022_motor_decifravel` | cria `desafio.tb904_motor` + `vw904_motor`, e acrescenta a `fk002_motor` em `tb001_desafio` e em `tb002_medicao_regua` | tabela **nova e vazia**; as duas FKs entram `NOT VALID`, então ⛔ **nenhuma linha existente é revalidada** |

⚠️ **Por que as FKs são `NOT VALID`:** o `des` já tem desafios publicados,
gerados antes de a dimensão existir. Validá-los agora exigiria **inventar** para
eles uma linha com um `co_sha256` de manifesto que ninguém conferiu - o oposto do
que a tabela existe para fazer. Para frente nada é afrouxado: toda linha nova é
conferida normalmente.

**O passo 1 continua obrigatório** (`identificar_banco.py`). Depois dele:

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python -m alembic current      # esperado: 0021_desafio_impedido
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current      # esperado: 0022_motor_decifravel (head)
```

**O que conferir depois**, na ordem:

1. `.venv\Scripts\python scripts\conferir_migracao_desafio.py` - a
   `desafio.tb904_motor` tem de aparecer com **0 linha(s)**. ⚠️ **Zero é o
   resultado correto**: quem preenche é o job, e uma linha ali agora seria hash
   de manifesto que ninguém conferiu. ⚠️ **Já a `tb903_perfil_dificuldade`
   aparece com 8 linhas no `des`, e isso também é o certo** - o job rodou lá em
   10/09. O conferidor só reprova dimensão com linha num banco **sem nenhum
   desafio**, onde o job nunca gravou.
2. A primeira execução do job depois disto grava **2 linhas** (uma por jogo) e
   imprime `[job] motor: 2 linha(s) nova(s)`.
3. ⚠️ **Olhe o aviso `MOTOR FORA DA DIMENSÃO` no resumo.** Se ele listar alguma
   versão, são desafios anteriores à `0022` cujo carimbo a dimensão não conhece -
   e uma **reprise** de um deles falharia na `fk002_motor`. Na prática o aviso
   deve sumir na primeira execução, porque o espelho não mudou desde que aqueles
   desafios foram gerados: a versão que o job grava é a mesma que eles carimbam.
   ⛔ Se **não** sumir, o caminho certo é regerar aqueles dias, e nunca inventar
   a linha de dimensão.

## ✅ A `0026_notificacao_de_reacao` — escrita e **aplicada no `des` em 22/09/2026**

> ✅ **Aplicada no `des` em 22/09/2026** (`identificar_banco.py` → DES;
> `0025_reacoes_do_design` → `0026_notificacao_de_reacao (head)`). Conferido em
> seguida, só leitura: a `tb008` e a `vw008` existem com **0 linhas**, e as
> restrições `un001_notificacao_reacao`, `ck001_pessoa` e `ck002_dispositivo`
> estão lá. ⏳ **No `prd` ainda não** - ela entra antes do push que levar a T079 à
> produção, como toda migração deste runbook.

| migração | o que faz | risco |
|---|---|---|
| `0026_notificacao_de_reacao` | cria `desafio_dia.tb008_notificacao_reacao` + `vw008_notificacao_reacao` | tabela **nova e vazia**; ⛔ **não toca nenhuma coluna existente** e ⛔ não acrescenta FK a tabela povoada |

**O que ela guarda.** O **fato** de a notificação *"N pessoas reagiram ao seu desafio
de ontem"* ter saído (T079, RF-DES-074a/b). O `UNIQUE (id_resolucao)` é o teto de
**uma por desafio**: sem ele, reação tardia renderia uma notificação nova por pessoa,
e qualquer reexecução do disparo reenviaria tudo.

**O passo 1 continua obrigatório** (`identificar_banco.py`). Depois dele:

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py
.venv\Scripts\python -m alembic current      # esperado: 0025_reacoes_do_design
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current      # esperado: 0026_notificacao_de_reacao (head)
```

**O que conferir depois:**

1. A tabela existe e tem **0 linhas** - ⚠️ **zero é o resultado certo**, e vai
   continuar zero até o **quarto serviço** do Railway existir (o disparo é quem
   escreve). Ver `arena-sagaz-frontend/specs/009-desafio-do-dia/guia-producao.md` §4.
2. ⛔ **A migração sozinha não envia nada.** Enquanto o serviço de cron não for
   criado, o código está no ar (ele vive na imagem da API) mas **ninguém o chama** -
   e isso é o estado esperado, não um defeito.

## ✅ A `0027_retrato_da_resolucao` — escrita em 24/09/2026, **aplicada e conferida no `des` em 25/09/2026**

> ✅ **Aplicada pelo dono em 25/09/2026**: `identificar_banco.py` disse DES,
> `alembic current` saiu de `0026_notificacao_de_reacao` para
> `0027_retrato_da_resolucao (head)`, e o `conferir_migracao_desafio.py` fechou com
> *"18/18 tabelas conferem"* (colunas na ordem, `js_feito` no fim da
> `tb003_resolucao`). O push do backend da T085za veio **depois** disso.
> ⏳ **No `prd`** ela entra na virada de chave (`specs/009-desafio-do-dia/guia-producao.md`).
>
> ⚠️ Registro de por que a ordem importa: a API nova
> grava `js_feito` em toda resolução e lê a `vw003_resolucao` com ela - publicada
> sem a coluna, ela quebra no primeiro envio (o push é o deploy).

| migração | o que faz | risco |
|---|---|---|
| `0027_retrato_da_resolucao` | `ALTER TABLE desafio_dia.tb003_resolucao ADD COLUMN js_feito JSONB` + `CREATE OR REPLACE VIEW vw003_resolucao` com a coluna no fim | coluna **nula** numa tabela povoada: ⛔ reescreve linha nenhuma, e as resoluções de antes ficam `NULL` (= "anterior ao retrato", e o app cai em *"Objetivo cumprido"*) |

**O que ela guarda.** O retrato do que a pessoa FEZ no instante do objetivo -
`{"medidas": {...}, "janela_gasta": n}` - para o outro aparelho dela escrever *"4
caixas em 2 turnos"* (`DECISOES-do-dono.md` §8z item 13, T085za). ⚠️ **No fim da
tabela, por `ALTER`**: a regra de 10/09 (*"migração já aplicada NÃO se edita. Crie
outra"*).

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer DES
.venv\Scripts\python -m alembic current                  # esperado: 0026_notificacao_de_reacao
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current                  # esperado: 0027_retrato_da_resolucao (head)
.venv\Scripts\python scripts\conferir_migracao_desafio.py
```

**O que conferir depois:** o `conferir_migracao_desafio.py` sai com as colunas **na
ordem** - desde a T085za ele lê também as colunas acrescentadas por `ALTER`, então a
`tb003_resolucao` tem de terminar em `js_feito`.

## ⏳ A `0028_piso_de_xp_do_desafio` — escrita em 04/10/2026, **aguardando o `des`**

| migração | o que faz | risco |
|---|---|---|
| `0028_piso_de_xp_do_desafio` | troca o `ck001_xp` de `desafio_dia.tb003_resolucao`: `BETWEEN 18 AND 30` → `BETWEEN 12 AND 30` (derruba e recria com o mesmo nome, numa transação) | ⛔ **nenhuma linha muda**: a regra nova contém a antiga, e o `ADD CONSTRAINT` revalida a tabela inteira - se algo estivesse fora, a migração falharia em vez de passar |

**Por que existe.** A pontuação do desafio passou a `12 + 18 x Q`
(`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zs). ⚠️ **Ela vem ANTES do
push do backend**: a API nova aceita 12..17 no modelo, e o `CHECK` antigo
recusaria essas resoluções com erro 500 (o push é o deploy).

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer DES
.venv\Scripts\python -m alembic current                  # esperado: 0027_retrato_da_resolucao
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current                  # esperado: 0028_piso_de_xp_do_desafio (head)
```

Leva segundos (a `tb003_resolucao` do `des` tem 6 linhas).

**O que conferir depois** (só leitura - o `conferir_migracao_desafio.py` não lê o
conteúdo deste `CHECK`):

```powershell
.venv\Scripts\python scripts\consultar_des.py "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck001_xp'"
```

Tem de sair `CHECK (((nu_xp >= 12) AND (nu_xp <= 30)))` - o Postgres guarda o
`BETWEEN` assim.

## ✅ A `0030_regua_da_nota` — escrita em 10/10/2026, aplicada no `des` e no `prd` (11/10, 01h03 UTC)

| migração | o que faz | risco |
|---|---|---|
| `0030_regua_da_nota` | cria `desafio_dia.tb904_regua_nota` e `tb905_parcela_regua_nota`, as VIEWs `vw904`/`vw905`, e insere a versão 1 (desde 01/09/2026) e a versão 2 (do **dia seguinte**, em UTC) | ⛔ **nenhuma linha existente muda**: só tabelas novas. Provada no `des` em 10/10/2026 numa transação desfeita (8 parcelas, soma 1,000 nas duas versões, `CHECK` recusando curva incoerente) |

**Por que existe.** A régua da nota sai do código e vai para o banco, por vigência
(`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zzo e §8zzq; o modelo em
`specs/009-desafio-do-dia/data-model.md`).

⚠️ **A data da versão 2 é a do dia da APLICAÇÃO + 1.** No `des`, aplicar já. No
`prd`, aplicar **imediatamente antes** do deploy do backend da versão 1.3.1, e
⛔ **não entre 20h30 e 21h de Brasília** (23h30-00h UTC): o deploy cairia no dia
seguinte, e alguns minutos dele seriam pontuados pelo código antigo.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer DES
.venv\Scripts\python -m alembic current                  # esperado: 0029_ic_cpu_no_desafio
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current                  # esperado: 0030_regua_da_nota (head)
.venv\Scripts\python scripts\conferir_migracao_desafio.py
.venv\Scripts\python scripts\consultar_des.py "SELECT nu_versao_regua, co_tipo_xp, vr_peso, co_forma, vr_x0, vr_escala FROM desafio_dia.vw905_parcela_regua_nota ORDER BY 1, nu_tipo_xp"
```

Leva segundos. A última consulta tem de mostrar **8 linhas**: a versão 1 com
0,300 / 0,300 / 0,150 / 0,250 (`linear`, a escala do tempo vazia) e a versão 2 com
0,500 / 0,150 / 0,200 / 0,150 (`hiperbolica`).

## ⏳ `0031` e `0032` — o conserto da vigência da régua (aprovado em 11/10/2026), **escritas em 11/10, aguardando o `des`**

**Por que existem.** A `0030` entrou no `prd` em 11/10/2026 (01h03 UTC), antes do
código que a lê, e pôs a **versão 2** da régua valendo desde **12/10/2026**. O dono
decidiu que a régua nova vale a partir da **liberação da 1.3.1 nas lojas**
(`arena-sagaz-frontend/docs/DECISOES-do-dono.md` §8zzr). As duas são aditivas, só
com `INSERT` em `tb904`/`tb905` (⛔ sem `UPDATE` na versão 2: `test_migracoes_aditivas`
proíbe, e a `un001_inicio_vigencia` não deixa repetir a data).

| migração | o que insere | no `des` | no `prd` |
|---|---|---|---|
| `0031_regua_antiga_ate_liberar` | **versão 3** = os números da versão 1 (0,300 / 0,300 / 0,150 / 0,250, `linear`), a partir de **13/10/2026** (data fixa) | junto com a `0032`, já | **imediatamente antes do deploy do backend** (merge na `main`), que vem ANTES de mandar a 1.3.1 à revisão |
| `0032_regua_nova_na_liberacao` | **versão 4** = os números da versão 2 (0,500 / 0,150 / 0,200 / 0,150, `hiperbolica`), a partir de `GREATEST(amanhã em UTC, 14/10/2026)` | junto com a `0031`, já | **aprovadas as duas lojas**: o dono aplica e libera a 1.3.1 em seguida. ⛔ Não entre 20h30 e 21h de Brasília |

⚠️ **O piso de 14/10 na data da `0032`.** Sem ele, aplicada em 11/10 ela nasceria em
12/10, **antes** da versão 3 - e, pela regra (vale a de maior vigência ≤ o dia), a
versão 3 venceria de 13/10 em diante para sempre, sem erro nenhum. Aplicada em 12/10,
cairia em 13/10 e a `un001_inicio_vigencia` recusaria. No `prd` o piso nunca decide
(a liberação vem dias depois); no `des`, sim.

✅ **A conferência que faltava (11/10):** o caso da T115 (Maria 23 × Fernando 22,
`test_v2_Maria_23_e_Fernando_22`) é da **régua 2**. Por isso o `des` recebe as duas
juntas e fica como o `prd` vai ficar depois da liberação: régua 1 até 13/10, régua 2
de 14/10 em diante. ⚠️ O desafio da Maria e do Fernando é de **10/10**, e pela data a
régua dele é a **1** em qualquer ambiente: a conferência da T115 no `des` tem de
passar a régua 2 explicitamente (ou usar um desafio de 14/10 em diante), e não deixar
a vigência escolher.

Cadeado: `tests/unitarios/test_regua_da_nota.py` (as quatro versões com os números
escritos à mão, a data fixa da 3, o `GREATEST` da 4, a linha do tempo do `prd`, o caso
"sem o piso a versão 4 nunca valeria" e a cadeia das revisões).

### No `des`: as duas juntas

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer DES
.venv\Scripts\python -m alembic current                  # esperado: 0030_regua_da_nota
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current                  # esperado: 0032_regua_nova_na_liberacao (head)
.venv\Scripts\python scripts\consultar_des.py "SELECT nu_versao_regua, dt_inicio_vigencia, co_tipo_xp, vr_peso, co_forma, vr_x0, vr_escala FROM desafio_dia.vw905_parcela_regua_nota ORDER BY 1, nu_tipo_xp"
```

Leva segundos. A consulta tem de mostrar **16 linhas**: as versões 1 e 3 com
0,300 / 0,300 / 0,150 / 0,250 (`linear`), as 2 e 4 com 0,500 / 0,150 / 0,200 / 0,150
(`hiperbolica`); a versão 3 em **2026-10-13** e a 4 em **2026-10-14** (o piso, se
aplicada até 13/10).

### No `prd`, em DOIS momentos

⚠️ **Primeiro momento - a `0031`, PELO NOME, imediatamente antes do deploy.** O
arquivo da `0032` já está no repositório, e `upgrade head` aplicaria as duas de uma
vez - a régua nova valeria durante a revisão inteira das lojas.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer PRD
.venv\Scripts\python -m alembic current                  # esperado: 0030_regua_da_nota
.venv\Scripts\python -m alembic upgrade 0031_regua_antiga_ate_liberar
.venv\Scripts\python -m alembic current                  # esperado: 0031_regua_antiga_ate_liberar (SEM "(head)")
```

O `alembic current` sem o `(head)` é o sinal certo: falta a `0032`, de propósito.

**Segundo momento - a `0032`, aprovadas as duas lojas**, imediatamente antes do
clique de liberação (⛔ não entre 20h30 e 21h de Brasília):

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py        # tem de dizer PRD
.venv\Scripts\python -m alembic current                  # esperado: 0031_regua_antiga_ate_liberar
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic current                  # esperado: 0032_regua_nova_na_liberacao (head)
```

A conferência dos dois momentos é a mesma consulta do `des`, pelo
`scripts\consultar_prd.py` (só leitura): 12 linhas depois do primeiro, 16 depois do
segundo, e a versão 4 no **dia seguinte** à aplicação.

⚠️ **As lojas precisam segurar a publicação** (App Store Connect: *"liberar esta
versão manualmente"*; Google Play: *publicação gerenciada*), senão a aprovação
publica a 1.3.1 antes da `0032`.
