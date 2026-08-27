# Runbook — aplicar a migração `0017` e o que vem depois

**Escrito em 28/08/2026.** Este documento é **autossuficiente de propósito**: ele
existe para ser lido do zero, meses depois, sem a conversa que o originou.

> **Estado em 28/08/2026:**
> ✅ **DES em `0017`** (migrado, em segundos, sobre 134 mil jogadas).
> ⬜ **PRD em `0011`** — lá o `upgrade head` aplica **seis** migrações
> (`0012`…`0017`), e não uma. Ver o passo 3, que analisa as seis uma a uma.
>
> ⚠️ A branch `main` do backend também está em `0011`: o código em produção
> conhece o schema até ali. Migrar o PRD deixa o **banco à frente do código**, o
> que é seguro (tudo é aditivo) e é justamente o desenho — mas explica por que
> nada muda em produção até o backend novo subir.

---

## 0. O que é a `0017`, em uma tela

`migrations/versions/0017_poder_e_probing_base.py` — o cabeçalho do arquivo
carrega o raciocínio completo de cada decisão. Ela cria:

| onde | colunas |
|---|---|
| `partida.tb002_jogada` | `nu_lance`, `ic_cancelada`, `co_poder`, `dh_cancelamento` |
| `partida.tb001_partida` | `qt_usos_poder` |
| `jogo_damas.tb002_jogada` | `qt_consultas_base`, `qt_acertos_base` |

Mais 8 CHECKs, 2 índices parciais e as 3 VIEWs recriadas.

**É puramente aditiva:** só `ADD COLUMN` (todas anuláveis ou com `DEFAULT`),
`ADD CONSTRAINT` (todos satisfeitos pelas linhas que já existem) e `DROP VIEW`
**com o `CREATE VIEW` correspondente na mesma migração** — a exceção que a `0014`
abriu. Nenhum `DROP TABLE`, `DROP COLUMN`, `UPDATE`, `DELETE` ou `TRUNCATE`.

**Nada quebra se ela demorar.** O app e o backend já estão prontos para o mundo
sem ela: as chaves novas simplesmente não aparecem no payload de quem não tem
poder, e o ingestor as ignora quando não existem no banco... **exceto** que o
`INSERT` do ingestor **já cita as colunas novas**. Ver o passo 4, que é onde isso
importa.

---

## 1. ⚠️ ANTES DE TUDO — que banco é este?

**Nunca rode `alembic upgrade` sem este passo.** Ele existe porque em 25/08/2026
um comando de migração foi entregue sem dizer contra qual banco rodaria. Os dois
bancos se chamam `railway` (é o nome padrão do Postgres em todo projeto Railway),
e o `AMBIENTE=` do `.env` **não é prova** — ele diz como a API se comporta, não a
qual banco ela se liga. Há usuários reais em `prd` desde 04/08/2026.

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python scripts\identificar_banco.py
```

Demora ~5 s. É **somente leitura** e nunca imprime senha.

O que olhar primeiro: a linha **`VEREDITO:`** no fim, e a **`revisao do alembic`**
no meio (tem de ser `0016_diagnostico_motor_nativo` antes de subir a `0017`).

| host:porta | é |
|---|---|
| `hopper.proxy.rlwy.net:21165` | **DES** |
| `hayabusa.proxy.rlwy.net:42857` | **PRD** |

Código de saída: `0` = DES · `2` = PRD **ou desconhecido** · `1` = não
diagnosticou.

⚠️ **"Não bate com nenhum dos dois" é o resultado mais perigoso, não o mais
inofensivo** — significa um banco que ninguém catalogou. O script trata esse caso
como PARE, igual ao PRD.

**Em 28/08/2026 o `.env` apontava para o DES**, revisão `0016`, 92 contas.

---

## 2. A migração no **DES**

Confirmado o veredito `DES`:

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\alembic upgrade head
```

Demora **poucos segundos** — são `ALTER TABLE` que não reescrevem linha (colunas
anuláveis ou com default são metadados no Postgres moderno) e três VIEWs.

O que olhar primeiro na saída: a linha
`Running upgrade 0016_diagnostico_motor_nativo -> 0017_poder_e_probing_base`.
Se aparecer `Target database is not up to date` ou um erro de constraint, **pare
e traga o texto** — não tente consertar rodando de novo.

### Conferir que subiu

```powershell
.venv\Scripts\python scripts\identificar_banco.py
```

A `revisao do alembic` tem de dizer **`0017_poder_e_probing_base`**.

### Conferir que as VIEWs enxergam as colunas novas

Este é o passo que **não pode ser pulado**, e o motivo é o modo de falha mais
silencioso desta migração: `partida.vw001_partida` e `partida.vw002_jogada`
foram criadas com `SELECT p.*`, e o PostgreSQL **expande o `*` no momento da
criação**. Uma VIEW não enxerga coluna acrescentada depois. Se a recriação
falhasse, a coluna existiria na tabela e seria **invisível** para quem lê pela
VIEW — que é como o projeto manda ler. Nenhum erro, nenhum log: só a coluna nunca
aparecendo, e alguém concluindo meses depois que *"o app não está gravando"*.

Rode no cliente SQL de sua preferência, contra o **DES**:

```sql
-- Tem de devolver as 4 colunas novas + nu_lance_efetivo.
SELECT column_name
  FROM information_schema.columns
 WHERE table_schema = 'partida' AND table_name = 'vw002_jogada'
   AND column_name IN ('nu_lance', 'ic_cancelada', 'co_poder',
                       'dh_cancelamento', 'nu_lance_efetivo')
 ORDER BY column_name;

-- Tem de devolver qt_usos_poder e ic_com_poder.
SELECT column_name
  FROM information_schema.columns
 WHERE table_schema = 'partida' AND table_name = 'vw001_partida'
   AND column_name IN ('qt_usos_poder', 'ic_com_poder');

-- Tem de devolver as 2 do probing.
SELECT column_name
  FROM information_schema.columns
 WHERE table_schema = 'jogo_damas' AND table_name = 'vw002_jogada'
   AND column_name IN ('qt_consultas_base', 'qt_acertos_base');
```

**Esperado: 5, 2 e 2 linhas.** Menos que isso = uma VIEW não foi recriada.

---

## 3. A migração no **PRD**

> ✅ **DES migrado em 28/08/2026.** `0016 -> 0017` em segundos, sobre
> **134.247 linhas** em `partida.tb002_jogada` e 4.849 em `tb001_partida`.
> `alembic current` = `0017_poder_e_probing_base (head)`.

### ⚠️ O PRD estava em `0011` — lá são SEIS migrações, não uma

Descoberto em 28/08/2026, e é a informação mais importante desta seção. Um
`alembic upgrade head` no PRD aplica, de uma vez:

| revisão | o que faz | toca o que o app em campo usa? |
|---|---|---|
| `0012` | cria o schema `jogo_damas` inteiro | **não** — schema novo |
| `0013` | `co_motor_busca` + dimensão, em `jogo_damas` | **não** |
| `0014` | alarga `co_versao_motor` (30→60), em `jogo_damas` | **não** |
| `0015` | o motivo `6 = base_finais`, em `jogo_damas` | **não** |
| `0016` | cria `log.tb002_diagnostico_motor_nativo` | **não** — tabela nova |
| `0017` | o poder, em `partida.*` + o probing, em `jogo_damas` | **sim** ⬅ a única |

**Cinco das seis não tocam nada que o app publicado ou o backend em produção
conheçam** — elas vivem em `jogo_damas` e `log`. As damas não estão publicadas;
o app em campo (v1.1.0+8) tem Pontinhos e Velha.

### Por que a `0017` também não quebra quem está em campo

1. **Toda coluna nova é anulável ou tem `DEFAULT`.** O `INSERT` do backend que
   está em produção **não cita** as colunas novas, e continua válido.
2. **Os CHECKs são satisfeitos pelas linhas que já existem**: elas ficam com
   `ic_cancelada = FALSE` (o default) e os demais campos nulos, que é exatamente
   o ramo permitido de `ck_jogada_cancelamento_completo`.
3. **O código em produção NÃO lê `partida.vw001_partida` nem
   `partida.vw002_jogada`** — conferido na branch `main`: ele escreve direto nas
   tabelas, e as únicas views que consulta com `SELECT *` são
   `conta.vw001_usuario`, `conta.vw002_provedor_login` e
   `progressao.vw001_progressao_usuario`, nenhuma tocada aqui. As duas views de
   `partida` são de **gestão**, não do caminho quente.
4. **`ADD COLUMN` com `DEFAULT` não reescreve a tabela** no Postgres moderno, e o
   `ADD CONSTRAINT CHECK` (que varre) levou segundos sobre as 134 mil linhas do
   DES. Se um dia a tabela crescer a ponto de isso incomodar, a saída é
   `NOT VALID` + `VALIDATE CONSTRAINT` — hoje não é necessário.

⚠️ **O que a migração no PRD NÃO faz é mudar alguma coisa hoje.** O app em campo
não joga damas, e o poder só existe nas damas: as colunas nascem e ficam
esperando. Isso é bom — o risco é quase nulo e o ganho imediato é zero. Aplicar
agora é **preparação**, e o efeito só aparece quando o backend novo subir e um
app com damas chegar às lojas.

### Ordem recomendada

Só depois de o DES estar verde **e** de você ter jogado uma partida de damas no
`des` usando o poder (passo 5) — não faz sentido levar ao PRD um formato que
ainda não se viu funcionar.

### Como apontar para o PRD

O alembic lê `DATABASE_URL` do `.env` do backend
(`arena-sagaz-backend/.env`), exatamente como `migrations/env.py` faz. A URL do
PRD está em `..\ferramentas\debug-bancos\ambientes.env`, na chave
`DATABASE_URL_PRD`.

1. abra `arena-sagaz-backend\.env`;
2. troque o valor de `DATABASE_URL` pelo de `DATABASE_URL_PRD`;
3. **rode o `identificar_banco.py` de novo** e confirme `VEREDITO: e o PRD`;
4. `.venv\Scripts\alembic upgrade head`;
5. rode o `identificar_banco.py` mais uma vez — a revisão tem de ser `0017`;
6. repita as três consultas de VIEW do passo 2, agora contra o PRD;
7. ⚠️ **devolva o `.env` para a URL do DES.** Deixá-lo apontando para produção é
   como deixar a chave na porta: o próximo comando que você rodar sem pensar
   rodará lá.

⚠️ **Não edite o `AMBIENTE=` achando que ele muda o banco.** As duas variáveis
são independentes; é exatamente esse descuido que o `identificar_banco.py`
existe para pegar.

---

## 4. ⚠️ O deploy do backend — e por que a ORDEM é esta

**A migração vem ANTES do deploy do backend, e não depois.** O `INSERT` do
ingestor (`api/sincronizacao/repositorio.py`) já cita `nu_lance`,
`ic_cancelada`, `co_poder`, `dh_cancelamento`, `qt_usos_poder`,
`qt_consultas_base` e `qt_acertos_base`. Um backend novo contra um banco velho
falha em **toda sincronização de partida** — de todos os jogos, não só das damas.

A ordem, então:

```
migração no DES  →  conferir  →  migração no PRD  →  conferir
                                        ↓
                          deploy do backend (Railway)
                                        ↓
                              testar de ponta a ponta
                                        ↓
                                    lojas
```

### Como o deploy acontece

O Railway constrói pelo `Dockerfile` (`railway.json`, `"builder": "DOCKERFILE"`)
e faz *healthcheck* em `/v1/health`. **A migração NÃO roda no start** — não há
`alembic upgrade` no `Dockerfile` nem no `railway.json`, e é de propósito: é o
que permite decidir quando ela sobe.

⚠️ **O código está na branch `jogo-damas`, e o Railway observa uma branch por
serviço.** Confirme no console qual branch cada serviço (des e prd) está
observando antes de esperar que o deploy aconteça. Se for `main`, o backend só
sobe quando `jogo-damas` for para lá — e aí a migração do PRD e o merge têm de
ser pensados juntos.

### Depois do deploy

```
GET https://api.arenasagaz.santiagodata.com/v1/health
```

E uma partida de qualquer jogo sincronizando sem erro — é o teste que prova que o
`INSERT` novo casa com o banco.

---

## 5. Testar de ponta a ponta (no `des`)

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-frontend
flutter run --flavor des --dart-define-from-file=config/dev.json
```

1. abra uma partida de **damas contra a CPU** (o poder não existe no modo 2
   jogadores — desfazer entre duas pessoas na mesma mesa é negociação, não
   compra, e um anúncio em tela cheia interromperia as duas);
2. jogue **pelo menos dois lances** (o poder desfaz um **par**: o seu e a
   resposta do personagem);
3. o botão dourado aparece no canto inferior direito **quando o anúncio
   carregar**;
4. use o poder, termine a partida, e confira no banco do **DES**:

```sql
-- A partida mais recente com poder.
SELECT id_partida, co_jogo, co_dificuldade, qt_usos_poder, ic_com_poder
  FROM partida.vw001_partida
 WHERE qt_usos_poder > 0
 ORDER BY dh_inicio DESC
 LIMIT 5;

-- E as jogadas dela: as canceladas continuam lá, e o LANCE se repete.
SELECT nu_ordem, nu_lance_efetivo, ic_cancelada, co_poder, dh_cancelamento
  FROM partida.vw002_jogada
 WHERE id_partida = '<cole o id acima>'
 ORDER BY nu_ordem;

-- O probing da base, nos lances da CPU.
SELECT nu_ordem, qt_nos_visitados, qt_consultas_base, qt_acertos_base,
       co_motor_busca, co_motivo_parada_busca
  FROM jogo_damas.vw002_jogada d
  JOIN partida.tb002_jogada j ON j.id_jogada = d.id_jogada
 WHERE j.id_partida = '<cole o id acima>'
 ORDER BY nu_ordem;
```

### O que esperar, e o que seria defeito

| observação | leitura |
|---|---|
| jogadas canceladas **continuam** na tabela | ✅ correto — o log é append-only, e a jogada desfeita aconteceu |
| `nu_ordem` 9 com `nu_lance_efetivo` 7 | ✅ correto — a refeita repete o lance, nunca a ordem |
| `qt_consultas_base` **nulo** no lance do humano | ✅ correto — não houve busca |
| `qt_consultas_base` **`0`** num lance da CPU | ✅ normal com o probing desligado — `0` é "buscou e não consultou" |
| `qt_consultas_base` nulo com `co_motivo_parada_busca = 'base_finais'` | ✅ correto — a base respondeu na **raiz**, e estes contadores são do probing **dentro** da árvore |
| `qt_acertos_base` **maior** que `qt_consultas_base` | ⛔ defeito — o CHECK deveria ter barrado |
| a coluna nova **não aparece** na consulta pela VIEW | ⛔ a VIEW não foi recriada — volte ao passo 2 |

⚠️ **O botão não aparecer não é, por si só, defeito.** Ele exige anúncio
carregado, modo contra a CPU, ao menos um par para desfazer, e usos restantes.
Ver a tabela de estados em `lib/shared/botao_voltar_jogada.dart`.

---

## 6. Depois: as lojas

Só depois de tudo acima. A ordem completa, que é a mesma da velha e pelo mesmo
motivo: **migração → backend → app às lojas**. Um app novo contra um backend
antigo perde a telemetria das damas em silêncio (o ingestor ignora a chave que
não conhece — decisão V-5: *"ignorar perde o detalhe, rejeitar perde a
partida"*); o inverso não custa nada.

Ver `arena-sagaz-frontend/specs/006-conta-nuvem/checklist-producao.md`.

---

## 7. ⬜ O que continua pendente depois de tudo isto

* **T207 — as conquistas COM USO DE PODER**, e as de hoje passando a significar
  **SEM PODER**. ⚠️ Entra pelas **guardas e testes**, nunca pelo catálogo: as
  conquistas já quebraram três vezes neste projeto, e sempre em silêncio.
* **T208 — a régua do Magno conta vitórias SEM PODER.** Toda consulta de
  `ferramentas/consultas_sql/` que apura reputação ganha `qt_usos_poder = 0`, e
  toda consulta que conta lances ganha `WHERE NOT ic_cancelada`. Enquanto as
  damas não estiverem publicadas isso não muda número nenhum — não há partida com
  poder em campo —, mas é dívida.
* ~~A ad unit PREMIADA do iOS~~ - **feita em 28/08/2026**
  (`ca-app-pub-7502939199237784/3057876314`). As duas premiadas estao em
  `config/prod.json`, e so valem no **release do prd**: `AdUnits._resolver`
  exige `kReleaseMode` E o ID preenchido.
* **T186** — medir o tamanho do APK/IPA antes e depois do asset da base.

---

## 8. Se der errado

**`alembic downgrade 0016_diagnostico_motor_nativo`** desfaz tudo — o
`downgrade()` está escrito e derruba as VIEWs primeiro (elas dependem das
colunas, e o Postgres recusaria o `DROP COLUMN` com elas de pé), depois as
constraints, depois as colunas, e por fim recria as três VIEWs com o corpo que
tinham antes.

⚠️ **Mas prefira trazer o erro a desfazer no PRD.** O DDL do Postgres é
transacional: uma migração que falha no meio **não deixa estado parcial**, ela
volta inteira sozinha. Se o `upgrade` deu erro, o banco já está como estava — o
que falta é entender o porquê, não desfazer.
