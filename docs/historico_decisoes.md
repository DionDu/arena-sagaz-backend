# Histórico de decisões — API (backend)

> **Onde está o histórico anterior a 21/07/2026:** em
> **`../ia/docs/historico_decisoes.md`**.
>
> Este arquivo nasceu vazio nessa data. O histórico antigo tinha ~160 KB e cerca
> de 95% dele era história do laboratório de IA (geração de dados, oráculo,
> arquitetura da CNN, rodadas de treino) — então foi junto com o laboratório
> quando ele saiu deste repositório. Fatiar aquele documento à mão para separar
> as poucas entradas de backend seria muito risco por muito pouco ganho: quem
> procura uma decisão antiga acha tudo lá, e a busca é a mesma.
>
> As entradas de backend que ficaram lá e vale conhecer:
> - **2026-07-13** — `co_anonimo` era coluna morta; removida das filhas (migração 0007)
> - **2026-07-12** — Redesenho do log de partidas/treino (migração 0006)
> - **2026-04-24** — Autenticação via Firebase Auth + limpeza da `api/` gerada por SpecKit
> - **2026-07-20** — Chama (sequência de dias) autoritativa no servidor, com fuso local

Daqui para a frente, **decisões de API entram aqui**. Cada entrada leva data,
contexto, decisão, alternativas consideradas e motivo.

---

## 2026-09-02 — O broadcast passa a ter destino por idioma (`todos_pt` · `todos_en` · `todos_es`)

**Contexto.** O broadcast sempre foi **um tópico só** (`todos`): o servidor manda
uma mensagem, o FCM entrega a todos os inscritos, e não guardamos token de
aparelho no banco. O preço disso é que **todo aviso saía num idioma só** — o
mesmo texto para quem lê o app em português, inglês ou espanhol. O dono pediu a
separação para poder avisar cada pessoa no idioma dela.

**Decisão.** Três tópicos novos, um por idioma suportado, **somados** ao `todos`:

* o **app** inscreve o aparelho em `todos_<idioma>` e o **desinscreve dos
  outros** (`lib/core/notificacoes/topico_de_idioma.dart`);
* o `POST /v1/notificacoes/broadcast` ganhou o campo opcional
  `idioma: "pt" | "en" | "es"`. Com ele, o destino é `todos_<idioma>`; **sem
  ele, nada muda** — vai para `todos`, como sempre foi.

Avisar nos três idiomas são **três chamadas**, cada uma com o seu texto. Não
existe envio "em três idiomas de uma vez": o FCM entrega o texto que recebe.

**Alternativas consideradas.**

1. **Guardar o idioma no banco e enviar por token** (`log.tb00x_dispositivo` já
   tem `co_idioma`). Descartada: exigiria iterar tokens, tratar token expirado e
   paginar o envio — trabalho de infraestrutura para resolver o que um tópico
   resolve de graça. O `co_idioma` continua útil para **relatório**, não para
   entrega.
2. **Mandar os três textos numa mensagem só**, com o app escolhendo. Descartada:
   o texto viajaria três vezes maior para todo mundo, e a escolha ficaria no
   cliente — versões antigas do app em campo mostrariam o idioma errado para
   sempre.
3. **`idioma: str` livre.** Descartada em favor de
   `Literal["pt","en","es"]`: com `str`, um `"pr"` digitado errado viraria um
   envio para `todos_pr` — e o FCM **devolve sucesso e um id de mensagem** para
   tópico sem inscritos. A falha seria perfeita: ninguém recebe, e o log diz que
   deu certo. Com `Literal`, é `422` com a lista dos aceitos.

**⚠️ O que descobrimos no caminho, e valia mais que a tarefa.** O app mandava
`co_idioma` no registro do dispositivo como
`locale?.languageCode ?? 'pt'`. O `locale` é **nulo** em "seguir o sistema", que
é o padrão de quem nunca abriu os Ajustes — então **toda essa gente estava
gravada como falante de português**, inclusive quem via o app em inglês. Os
dados de `co_idioma` anteriores a 02/09/2026 estão enviesados para `pt` e não
servem para dimensionar público por idioma. Corrigido no app
(`lib/core/i18n/idioma_efetivo.dart`); o banco se corrige sozinho conforme os
aparelhos reabrem o app e reenviam o registro.

---

## 2026-08-27 — O poder "voltar jogada" mora em `partida`, e não em `jogo_damas`

**Contexto.** O app ganhou o poder **voltar jogada**: a pessoa assiste a um
anúncio premiado e desfaz o próprio lance mais a resposta do personagem. Ele
estreia nas damas, mas nasceu em `lib/core/poderes/` — a tela de qualquer jogo do
hub pode chamá-lo. O log precisa registrar que aquilo aconteceu; se não
registrar, a partida sobe como se a pessoa tivesse acertado de primeira.

**Decisão.** As quatro colunas do cancelamento (`nu_lance`, `ic_cancelada`,
`co_poder`, `dh_cancelamento`) entram em **`partida.tb002_jogada`**, e
`qt_usos_poder` em **`partida.tb001_partida`** — as tabelas **genéricas**.
Migração `0017_poder_e_probing_base.py`.

**Alternativa considerada e descartada:** `jogo_damas.tb004_retorno`, uma tabela
de eventos de retorno com o par `(nu_ordem_apos, nu_ordem_alvo)`. Ela estava
esboçada no `data-model.md` §7.1 da spec 008 desde 15/08, e caiu por dois
motivos que só apareceram quando a feature foi escrita:

1. **O poder não é das damas.** Uma tabela em `jogo_damas` obrigaria a copiá-la
   para `jogo_velha` e `jogo_pontinhos` no dia em que o dono ligasse o poder
   neles — e a escrever a consulta de reputação três vezes. É a armadilha que o
   frontend já pagou caro três vezes (*"tela igual em dois jogos é UM widget,
   não dois parecidos"*), aparecendo agora no banco.
2. **A pergunta que se faz ao log é por LINHA**: *"esta jogada valeu?"*.
   Respondê-la a partir de uma tabela de retornos exige reconstruir a sequência
   inteira; uma marca na própria jogada responde direto.

### ⚠️ `nu_ordem` e `nu_lance` são dois números, e confundi-los é o erro mais provável de quem mexer nisto depois

`nu_ordem` é **sequência contínua de eventos**: nunca recua, nunca se repete —
`partida.tb002_jogada` tem `UNIQUE (id_partida, nu_ordem)` desde a `0003`, e
reaproveitar o número quebraria a chave. Mexer nessa constraint seria alterar uma
tabela **já publicada**, contra a regra aditiva que vale desde a `0011`.

`nu_lance` é o número do lance **no tabuleiro**, e recua com o desfazer:

```
nu_ordem  |  1 2 3 4 5 6   7    8    9  10
nu_lance  |  1 2 3 4 5 6   7    8    7   8
cancelada |  . . . . . .   X    X    .   .
```

`nu_lance` é **anulável e sem backfill**: o Pontinhos e a velha não o informam
(não têm poder, então lá `nu_lance` **é** `nu_ordem`), e o app só o envia quando
o jogo o preenche — é isso que mantém o payload dos dois jogos publicados byte a
byte idêntico ao que já está em campo. A leitura correta é
`COALESCE(nu_lance, nu_ordem)`, e a VIEW `partida.vw002_jogada` já a entrega
pronta em `nu_lance_efetivo`, para ninguém precisar lembrar.

**Um `UPDATE ... SET nu_lance = nu_ordem` foi considerado e recusado** — pelo
mesmo argumento com que a `0014` recusou consertar 25 linhas de teste no `des`:
custaria pôr `UPDATE` na lista de comandos permitidos do cadeado, e um `UPDATE`
mal escrito destrói dado tão bem quanto um `DELETE`.

### A linha cancelada não é apagada

O log é *append-only*, e a jogada desfeita **aconteceu**: a pessoa a viu no
tabuleiro, o personagem respondeu a ela, o relógio andou. Apagar esconderia
justamente o que a reputação do Magno precisa enxergar, e tornaria impossível
saber se o poder está sendo usado para consertar um deslize ou para procurar o
lance certo por tentativa e erro.

**Consequência para toda consulta já escrita:** contar lances passa a ser
`WHERE NOT ic_cancelada`. A coluna nasce `NOT NULL DEFAULT FALSE`, então nenhuma
consulta antiga muda de resultado hoje — mas é dívida, e ela tem dono (**T208**).

### O XP e a reputação foram decididos, e são coisas diferentes

Do dono, em 27/08/2026:

- **XP: igual com e sem poder.** *"O poder existe para a pessoa continuar
  jogando, e cortar o XP dela puniria exatamente o comportamento que se quer."*
- **Reputação: só sem poder.** *"Conta como vitória. Mas não leva a conquista SEM
  USO DE PODER. A reputação do Magno passa a ser contada pelas vitórias sem uso
  de poder pelo humano."*

Daí `qt_usos_poder` na partida, e o índice parcial `ix_partida_sem_poder` sobre
`(co_jogo, co_dificuldade) WHERE qt_usos_poder = 0` — o filtro exato dessa
consulta. Derivar de `EXISTS (SELECT 1 FROM tb002_jogada WHERE ic_cancelada)`
funcionaria, e rodaria uma subconsulta por partida em todo levantamento.

⚠️ **A coluna conta USOS, e não jogadas canceladas.** Um uso de "voltar jogada"
desfaz **duas** jogadas; um poder futuro (uma dica) pode não desfazer nenhuma.
Contar linhas canceladas responderia outra pergunta, e responderia errado no dia
em que o segundo poder chegar.

⚠️ **Uma coluna, e não duas.** Um `ic_com_poder` ao lado seria `qt_usos_poder >
0` escrito de novo. Duas verdades sobre o mesmo fato divergem no dia em que
alguém atualizar só uma — e a VIEW já entrega o booleano derivado de graça.

### `co_poder` é `VARCHAR` com `CHECK`, e não dimensão

Mesma escolha, e pelo mesmo motivo, do `co_motor_busca` na `0013` e do
`co_motivo` na `0016`: pouquíssimos valores fechados, e uma dimensão custaria um
JOIN em toda consulta para não entregar nada. Se um dia a lista crescer ou
precisar de rótulo traduzido, o CHECK vira dimensão — e aí o JOIN se paga.

Consequência: **nenhum sentinela `9999` novo**. Ele existe para o caso de um app
mais novo mandar um código que a dimensão ainda não conhece — sem ele a FK
estoura, o endpoint devolve 500, e o evento fica preso para sempre na fila do
aparelho. Com um `CHECK`, esse risco não se aplica.

---

## 2026-08-27 (2) — O *probing* da base de finais: dois contadores, e `NULL` ≠ `0`

**Contexto.** A base de finais entrou na busca dos dois motores em 27/08/2026
(Dart 1.4.0, Rust 0.4.0). Perguntar à base **custa**: é um acesso a arquivo no
disco, no meio da árvore. Os dois números já chegavam à tela desde então
(`RespostaDaBuscaDamas`); não havia onde gravá-los.

**Decisão.** `qt_consultas_base` e `qt_acertos_base` em
`jogo_damas.tb002_jogada`, na mesma migração `0017` — por pedido explícito do
dono: *"Lembre-se que aqueles 2 campos de quantidade de busca de base devem
entrar juntos nestas tarefas."*

**São dois, e não um**, porque é a **razão** entre eles que diz se o probing se
paga: muitas consultas com poucos acertos significa que a árvore quase nunca
alcança finais de 4 peças naquele tipo de partida, e aí o esforço custa mais do
que rende. Com um número só, esse diagnóstico não existe.

⚠️ **`NULL` não é `0`.** `NULL` = *"não houve busca"* (lance do humano, lance
único, lance que veio pronto da base); `0` = *"houve busca e ela não consultou
uma vez sequer"* — o estado normal com o probing desligado, e o sintoma a
investigar com ele ligado. O ingestor **não** tem `.get(..., 0)` nesses dois
campos, de propósito: colapsá-los repetiria, numa coluna nova, o defeito que
custou caro na T197 — a telemetria que responde `0` onde a verdade é "não sei".

⚠️ **Um lance vindo da base NÃO grava `1`/`1`.** É o erro tentador — a base
respondeu, afinal. Mas ela respondeu na **raiz**, antes de qualquer nó, e estes
dois contam o probing **dentro** da árvore. Marcar 1/1 faria a razão incluir
lances de 100% de acerto em que busca nenhuma houve. O motivo de parada já diz de
onde o lance veio: `6 = base_finais`.

⚠️ **Não há motivo de parada novo.** O `tasks.md` da spec 008 falava em
`7 = decidido_por_base`; conferido no motor, **ele não existe** — o probing não
encerra a busca.

### O que a `0017` obrigou a aprender sobre VIEWs

`partida.vw001_partida` e `partida.vw002_jogada` foram criadas com `SELECT p.*`,
e o PostgreSQL expande o `*` no momento da criação. Sem recriá-las, as colunas
novas existiriam na tabela e seriam **invisíveis** para quem lê pela VIEW — que é
como o projeto manda ler. Nenhum erro, nenhuma falha: só a coluna nunca
aparecendo, e alguém concluindo meses depois que "o app não está gravando".

E o conserto é `DROP VIEW` + `CREATE VIEW`, e não `CREATE OR REPLACE`: as duas
terminam numa coluna **derivada** (`co_resultado`, `ic_cpu`), e as colunas novas
do `p.*` entrariam **antes** dela — `CREATE OR REPLACE VIEW` só aceita
acrescentar ao fim. É a exceção que a `0014` abriu, e é segura: VIEW não guarda
dado, e o DDL do Postgres é transacional.

⚠️ **E os `DROP VIEW` vêm ANTES dos `ALTER TABLE`.** `test_migracoes_aditivas.py`
procura `ALTER TABLE …DROP` com `re.DOTALL`, então qualquer `DROP` **depois** de
um `ALTER TABLE` no mesmo `upgrade()` é recusado — mesmo sendo um `DROP VIEW`
legítimo. O cadeado pegou a primeira versão do arquivo; a `0014` já usava essa
ordem.

⚠️ **`qt_usos_poder` é sanitizado no ingestor** (`_inteiro_nao_negativo`), pela
mesma assimetria da decisão V-5 e a mesma escolha que `_offset` já fazia: um
valor podre do cliente estouraria o `CHECK` ou o `SMALLINT`, a partida voltaria
500, e o evento ficaria preso para sempre na fila daquele aparelho. Perder um
número de telemetria é barato; perder a partida não é. ⚠️ `bool` é `int` em
Python, e é recusado explicitamente: `"qt_usos_poder": true` viraria "um uso" em
silêncio.

⛔ **A `0017` está ESCRITA e NÃO APLICADA**, à espera do OK do dono. Ordem de
deploy: **migração em `des` → conferir → `prd` → backend com o ingestor novo →
só então o app às lojas.** Antes de qualquer `alembic upgrade`, rodar
`scripts/identificar_banco.py` — o `AMBIENTE` do `.env` não é prova.

---

## 2026-08-27 — Diagnóstico de campo: um endpoint novo, e não o `js_extra`

**Contexto.** Desde 25/08 o app esconde o nível **Sagaz** das damas quando o
motor nativo (Rust) não carrega — porque o orçamento daquele nível foi
dimensionado para ele. A trava funciona. O problema é que ela esconde **em
silêncio**, que é exatamente o defeito que veio consertar: o Release do iOS
jogou semanas no motor Dart sem que nada denunciasse.

**Decisão 1: endpoint novo — `POST /v1/diagnosticos/motor-nativo`.** Do dono:

> *"Não vejo sentido em mandar logs de erros no `js_extra` de outras partidas
> que não têm nada a ver com isso. Vamos criar esse novo endpoint."*

**Descartado: pendurar o aviso no `js_extra` do log de partida.** Era a
recomendação anterior, por ser aditiva e não pedir migração. O argumento que a
derrubou é bom: **com a trava ligada, ninguém joga no Sagaz naquele aparelho** —
o aviso viajaria preso a partidas de outros níveis, misturando dado de
diagnóstico com dado de jogo, num lugar onde ninguém o procuraria.

**Decisão 2: schema `log`, e `co_jogo` como COLUNA.** "O binário não carregou" é
problema do **app**, não do jogo. O TFLite do Pontinhos é igualmente nativo e a
mesma pergunta vale para ele; uma tabela em `jogo_damas` obrigaria a copiar a
estrutura por jogo. Tabela: `log.tb002_diagnostico_motor_nativo` (migração
`0016`, aditiva).

**Decisão 3: as cinco regras, e cada uma é um modo de falha real.**

1. **Deduplicar no APP.** Sem isso, um aparelho quebrado relata a cada abertura,
   para sempre — e a tabela passa a medir *aberturas* em vez de *aparelhos*,
   respondendo outra pergunta sem que ninguém perceba. A assinatura é
   jogo + motor + motivo + versão do app + versão do binário encontrada.
2. **Sem login.** `id_usuario` é nulo-ável e **sem FK**. Uma FK obrigaria login,
   e o relato mais valioso — o de quem está experimentando o app pela primeira
   vez — seria o único impossível.
3. **Nunca lançar nem bloquear.** `202 Accepted`, e o app não trata a resposta.
4. **Tolerar servidor antigo.** `404`/`501` é silêncio, pela diretriz de
   versionamento da API.
5. **Nada de identificador estável de aparelho.** Sem IMEI, sem `androidId`, sem
   `identifierForVendor`: modelo e ABI bastam para saber qual build refazer e
   não permitem seguir uma pessoa. ⚠️ **É esta regra que obriga o dedupe a morar
   no app** — no servidor ele exigiria justamente o identificador proibido.

**O motivo é gravado duas vezes, e não é redundância.** `co_motivo` é a
categoria (o que se agrupa numa consulta); `de_motivo` é o texto cru (o que diz
**onde olhar** — o nome do símbolo que faltou, o caminho, a mensagem do
`dlopen`). Guardar só a categoria perderia o diagnóstico; guardar só o texto
tornaria impossível contar.

**`co_motivo` é `VARCHAR` com `CHECK`, e não dimensão `tb9xx`** — mesma escolha,
e pelo mesmo motivo, do `co_motor_busca` na `0013`: cinco valores fechados, e uma
dimensão custaria um `JOIN` em toda consulta para não entregar nada.

⚠️ **`plataforma_sem_motor` está na lista de motivos e NÃO é defeito.** É o que a
VM do `flutter test` e qualquer desktop respondem. Existe como categoria própria
para não cair em `falha_desconhecida` e poluir a contagem do que importa.

**Efeito colateral bom:** `usuario_atual_opcional` subiu de
`api/notificacoes/rotas.py` para `api/nucleo/dependencias.py`, ao lado da irmã
obrigatória. Era a segunda rota sem login, e copiá-la seria a armadilha que o
projeto já pagou caro. `api.notificacoes.rotas` reexporta o **mesmo objeto**, e
os `dependency_overrides` dos testes de lá continuam valendo sem uma linha de
mudança.

### ⚠️ Revisao no mesmo dia — quatro correcoes do dono, e uma delas derrubou um argumento meu

**1. `co_jogo` era `VARCHAR(20)` e virou `(30)`.** *"Precisa manter um padrao de
dados nos campos correlatos."* E `(30)` em `partida.tb001_partida` e nas duas
tabelas de `log_treino`. Larguras diferentes para a mesma coisa sao a primeira
rachadura de um JOIN que um dia trunca.

**2. `co_versao_motor` nova — sao TRES versoes, e nao duas.** *"Tem `co_motor`. E
a versao do motor? O codigo do App tem uma versao esperada e podemos ter outra
compilada no App?"* Sim: o motor **logico** (`dart_1.3.0`), o **minimo** que ele
exige do binario (`0.3.0`) e o que o binario **declarou** (`0.2.0`). O `.so`/`.a`
e compilado por script a parte, entao "Dart novo com binario velho" e um estado
real — foi o do iOS entre 26 e 27/08/2026.

**3. `de_motivo` era `VARCHAR(300)` e virou `TEXT`.** *"E suficiente para trazer
todo o stacktrace de um erro?"* **Nao era** — um stacktrace de Dart tem alguns
milhares de caracteres. No Postgres, `TEXT` e `VARCHAR(n)` tem o mesmo desempenho
e o mesmo armazenamento. O corte continua no app (4000), onde ele serve para
alguma coisa: evitar a viagem, e nao a gravacao.

**4. ⚠️ `co_assinatura UNIQUE` — e aqui um argumento meu estava errado.**

*"O que vai garantir ai que um mesmo telefone de 1 usuario nao vai ficar
alimentando essa tabela indefinidamente com o mesmo registro?"*

Eu havia escrito, em tres lugares, que *"deduplicar no servidor exigiria um
identificador estavel de aparelho, que a regra 5 proibe"*. **Falso.** Deduplicar
por **configuracao** — modelo, ABI, SO, versoes, motivo — nao precisa de
identificador de pessoa nenhum, e e justamente a unidade que se quer contar.

O desenho antigo apostava so no dedupe do app, que vive no `shared_preferences`:
some numa reinstalacao, some num "limpar dados", e nao e gravado quando o envio
falha (corretamente). Cada caso desses gerava linha nova.

⚠️ **E o problema nao era volume; era leitura.** Com uma linha por relato, a
consulta *"quantas configuracoes estao quebradas?"* passa a responder *"quantas
vezes alguem reinstalou o app num aparelho quebrado"* — outra pergunta, sem que
nada denuncie a troca.

**Conserto:** `co_assinatura CHAR(64) UNIQUE` (SHA-256 de doze colunas, calculado
**no servidor**) + `ON CONFLICT DO UPDATE`, com `qt_ocorrencias`, `dh_primeiro` e
`dh_ultimo`. Um telefone em laco incrementa um contador.

A assinatura **nao** inclui `id_usuario` (a tabela conta configuracoes quebradas,
nao pessoas) nem `de_motivo` (varia entre execucoes, e faria a garantia sumir em
silencio). `dh_primeiro` **nao** e atualizado: e ele que diz ha quanto tempo a
configuracao esta quebrada.

**O que se perde, e e honesto dizer:** nao se sabe quantos aparelhos
**distintos** sofreram. Isso ja era verdade — sem identificador estavel nao ha
como contar aparelhos distintos de jeito nenhum.

**5. Descartado: um motivo de parada `base_finais_dentro_busca`.** O
`co_motivo_parada_busca` responde *"por que a busca parou"*, e um *probing*
dentro da arvore nao faz a busca parar. O que entra junto com a T185 parte 2b sao
outras duas coisas: `qt_consultas_base` + `qt_acertos_base` (quantidades, nao
motivo) e um `7 = decidido_por_base`, que separa *"a busca achou um mate
forcado"* de *"a resposta estava gravada"*. Nenhum dos dois entra antes de o app
produzir o dado.

---

## 2026-08-27 (2) — O motivo de parada `6 = base_finais`

**Contexto.** Desde 26/08 o Magno das damas consulta uma **base de finais** antes
de pensar: em toda posição de até 4 peças a resposta já está gravada no asset,
com veredito exato e distância até o fim. Esses lances gravam
`co_motivo_parada_busca = 'base_finais'`, um valor que não existia na dimensão.

**Decisão: `6` na `jogo_damas.tb902_motivo_parada_busca`** (migração `0015`), no
molde exato do `5 = lance_unico` da `0013`.

⚠️ **Isto nunca quebrou nada.** O sentinela `9999 = desconhecido` existe
justamente para um app **mais novo** que o backend: o valor caía nele e o texto
cru ia para o `js_extra`. Foi assim que o `lance_unico` viveu até a `0013`. O que
se ganha não é integridade — é poder **contar** quantos lances vieram da base.

**Não acrescenta coluna e não mexe em view.** A `0013` precisou refazer a
`vw002_jogada` porque acrescentava `co_motor_busca` à tabela, e o `SELECT j.*`
não enxerga coluna criada depois. Aqui o valor entra na **dimensão**, que a view
já lê pelo `JOIN`.

**Os campos de busca continuam indo a `NULL`, não a zero.** `base_finais` é irmão
de `lance_unico`: nos dois não houve árvore, nós nem avaliação. Zero em
`nu_avaliacao_brancas` significaria **posição equilibrada** — afirmação falsa
sobre uma posição que ninguém olhou. Foi o defeito que a `0013` corrigiu.

⚠️ **`co_motor_busca` fica nulo também.** `dart` e `rust` respondem *"quem
escolheu"*, e na base ninguém escolheu: a resposta estava gravada. Marcar um dos
dois inflaria a contagem "lances por motor" justamente nos **finais**, que é onde
os dois motores mais divergem — num levantamento que existe para compará-los.

**Nada converte os dados já gravados.** Os lances anteriores continuam como
`desconhecido` com o texto no `js_extra`: o projeto não reescreve histórico
de log.

---

## 2026-08-13 — `nu_dias_jogados`: o total de dias vira número DERIVADO, como a chama

**Contexto.** Relato de campo: uma usuária (Android, 1.0.1+3) com **21 dias de
chama** nunca recebeu a conquista "10 Dias na Arena". A investigação no banco de
`prd` confirmou 21 dias locais distintos e consecutivos (23/07 a 12/08), num
único aparelho, com as conquistas de **sequência** (3, 7, 14) desbloqueadas nas
datas certas — e nenhuma conquista de **dias jogados**.

A assimetria tem uma causa só: os dois números são de naturezas diferentes.

| | chama | dias jogados |
|---|---|---|
| natureza | **derivada** do histórico de partidas | **acumulador** `+1` por dia novo |
| onde mora | `nu_sequencia_atual`, no servidor | dentro de `js_estado_local`, **só no aparelho** |
| reconstrução | `recalcular_chama`, a cada leitura | **não existia** |

Um acumulador não se reconstrói; uma derivação sim. Quando o rascunho local do
app era sobrescrito (ver a entrada correspondente no frontend), a chama voltava
certa e o contador de dias não voltava nunca.

Sinal de que era sistêmico, e não daquela usuária: `dias_10` havia sido concedida
**3 vezes em toda a produção**, e o único usuário com ≥10 dias que a tinha também
tinha `dias_30` com apenas 14 dias jogados — resíduo do bug de inflação corrigido
em 20/07. Ou seja, a conquista provavelmente **nunca foi ganha legitimamente**.

**Decisão.** `recalcular_chama` passa a devolver também o total de dias
(`len(dias)` — a mesma lista `DISTINCT` que a sequência já usa, sem consulta
extra), e `obter_progressao` publica `nu_dias_jogados` na resposta de
`GET /estado` e `POST /eventos`. O app adota por `GREATEST`.

**Alternativas consideradas.**

- *Persistir o total numa coluna nova.* Recusada: exigiria migração em produção
  para não ganhar nada — o número é recalculável a cada leitura, e guardá-lo
  criaria uma **segunda cópia da mesma verdade**, que é exatamente a origem do
  defeito. Derivar é mais barato **e** mais correto aqui.
- *Deixar o app contar e só consertar a corrida no cliente.* Insuficiente: a
  trava do cliente impede a perda catastrófica, mas ainda perde 1 dia por
  ocorrência (o `dt_ultimo_dia_jogado` sobrevive à corrida e suprime o
  recontar). Medido em teste: 12 dias em vez de 21. As duas metades são
  necessárias.
- *Backfill único, como o `recalcular_chama_todos.py`.* Desnecessário: como o
  número é recalculado a cada leitura, todo mundo se corrige sozinho no próximo
  acesso — inclusive retroativamente.

**Compatibilidade.** Campo **aditivo**. Apps em campo ignoram chaves
desconhecidas (diretriz de versionamento da API), e as rotas devolvem
`dict[str, Any]` sem `response_model`, então nada é filtrado. Vai sempre,
inclusive zero, para o app não ter de distinguir "ausente" de "zero" — só a
ausência (servidor antigo) significa "não sei", e aí o app mantém o local.

**Efeito para quem já jogava.** A conquista sai na próxima partida depois do
deploy, sem rejogar nada. A avaliação de conquistas continua acontecendo no fim
de partida (não no sync), de propósito: é lá que mora a celebração na tela.

**Testes.** `tests/unitarios/test_dias_jogados_autoritativo.py` — sem partidas dá
zero e não escreve na linha; sem buracos o total iguala a chama (o caso dela);
com buracos o total supera a chama (é o que distingue dedicação de constância).

---

## 2026-08-06 — Schema `jogo_velha`: o 2o jogo do hub grava log, sem tocar em nada do 1o

**Contexto.** O Jogo da Velha (spec 007) e o segundo jogo da Arena Sagaz. Como o
Pontinhos, ele grava a jogada GENERICA em `partida.tb002_jogada` e uma extensao
especifica num schema proprio. **Ha usuarios reais em `prd` desde 04/08/2026**, e
o dono cravou a regra na mesma data:

> "Tome muito cuidado para nao usar DELETE, TRUNCATE, DROP. Nos ja temos usuarios
> no ambiente PRD. Todas as alteracoes que estamos fazendo com este novo jogo nao
> devem quebrar o App das pessoas que estao jogando versao mais antiga e nao vao
> atualizar o App."

**Decisao.** Migracao `0011_schema_jogo_velha`, **puramente aditiva**: `CREATE
SCHEMA`, `CREATE TABLE` x2 (`tb002_jogada` e a dimensao `tb901_jogada_acao`),
`INSERT` dos 6 codigos + `9999`, e `CREATE VIEW` x2. Nenhuma tabela, coluna ou
view existente e tocada.

E "aditiva" deixou de ser palavra do autor: `tests/unitarios/
test_migracao_aditiva_velha.py` **le o arquivo da migracao** e falha se achar
`DELETE`, `TRUNCATE` ou `DROP` no `upgrade()` — e ainda vira a regra do avesso,
conferindo que TODO comando executado comeca por um dos quatro permitidos. O
`downgrade()` e ignorado de proposito: ele derruba o schema, existe para o
ambiente local e nunca roda em producao.

**Por que a extensao existe, se a velha nao tem treino.** A do Pontinhos alimenta
a CNN. Esta nao — e por isso e tao menor (sem matriz, sem softmax, sem score de
busca, sem profundidade). Ela existe por **auditoria**:

1. **o XP passa a depender de `ic_otimo`** (RF-VLH-045/046). Um numero que decide
   recompensa e nao e verificavel no servidor e a palavra do aparelho;
2. **reconstruir a partida para suporte** — com a celula e a ordem, a partida
   inteira se remonta.

**Tres detalhes que divergem do irmao, e um copiar-colar apagaria:**

- `co_jogador` e **+1 / -1** (o SINAL), nao 1 / 2. O generico usa 1/2; a extensao
  usa o sinal, exatamente como no Pontinhos. Ha um `CHECK` que impede a confusao.
- `co_celula` e `VARCHAR(15)`, e nao o `VARCHAR(3)` que o PRD §7.2 escrevia — com
  3, **todo INSERT seria rejeitado**, porque `'C_1_2'` tem 5 caracteres. A largura
  ficou igual a do `co_aresta` do Pontinhos (validacao V-1 do dono).
- `ic_otimo` e **anulavel**, e `NULL` significa "lance da CPU". Um `false` ali
  significaria "a CPU jogou mal" e falsearia qualquer analise de qualidade feita
  sobre a tabela.

**Dimensoes qualificadas por jogo.** `api/sincronizacao/dimensoes.py` ganhou
`acao_pontinhos`, `situacao_pontinhos` e `acao_velha`, mantendo `"acao"` e
`"situacao"` como **apelidos** do Pontinhos para nenhum chamador quebrar no mesmo
commit (expand/contract). Sem isso, as acoes da velha seriam procuradas na tabela
do Pontinhos, cairiam **todas** no sentinela `9999`, e a telemetria do jogo novo
nasceria cega — sem erro, sem log de falha, so uma coluna inteira de
"desconhecido".

**Alternativa considerada e recusada: rejeitar a extensao desconhecida.** A
RF-VLH-064 pedia, na letra, que o backend rejeitasse o que nao conhece. Nao foi
o que se fez, e a assimetria e o motivo: rejeitar faz o app **descartar o evento
inteiro** — contrato escrito no proprio `validacao.py` — jogando fora a **partida
completa** do usuario para nao perder um detalhe que este backend nao saberia
guardar de todo modo. **Ignorar perde o detalhe; rejeitar perde a partida.** O
ingestor ignora e emite um `logger.warning` estruturado, que e o unico sinal de
que ha um app em campo mais novo que o backend. Divergencia deliberada da letra,
cumprindo a intencao (validacao V-5 do dono).

**Alternativa considerada e recusada: um `co_tipo_xp` proprio para a velha.** A
parcela de qualidade da velha (lances otimos) sobe como `caixas`, o codigo que o
Pontinhos usa. A dimensao `partida.vw902_tipo_xp` e **generica** (do schema
`partida`, nao de um jogo), e um codigo novo ali exigiria migracao e backend novo
em campo **antes** deste app — a ordem inversa da que a producao permite. Trocar
depois e possivel, com a migracao e o deploy na ordem certa.

**⚠️ ORDEM DE DEPLOY — sem inversao possivel** (RF-VLH-060):

1. migracao `0011` em **`des`** → conferir → **`prd`**;
2. backend com o ingestor novo (aceita `jogada["velha"]`);
3. **so entao** o app as lojas.

**Por que 2 antes de 3:** um backend antigo recebendo `jogada["velha"]` ignora a
chave (por desenho). A partida entra, mas o `ic_otimo` **evapora** — e e dele que
o XP depende. Ninguem quebra, mas o dado que justifica a recompensa se perde em
silencio, e nao volta.


## 2026-08-01 — Conta sem nome nasce batizada com o próprio `co_usuario`

**Contexto.** A App Review recusou a versão **1.0.1 (4)** pela **diretriz 4
(Design)**: *"users are required to provide their name and/or email address after
using Sign in with Apple even though that information is already provided by the
Authentication Services framework"*. A causa raiz é do app (ele pedia à Apple só o
escopo `email`, nunca o `name`), mas a correção respinga aqui.

O problema não se resolve só pedindo o escopo. A Apple entrega o nome **uma única
vez**, na primeira autorização de cada Apple ID para o App ID — numa reautorização
(quem excluiu a conta e voltou, por exemplo) ele chega nulo, sem erro. Por isso o
app passou a **esconder** o campo de nome quando o provedor não manda nome, em vez
de mostrá-lo vazio e obrigatório. Consequência para a API: `no_exibicao` agora
chega **ausente** num caminho legítimo e comum de criação de conta.

Até aqui, o serviço criava a conta com `no_exibicao = NULL` — e o app, sem nome,
exibia **"Convidado"** para quem tinha acabado de criar conta (`usuario_local.dart`
usa esse rótulo como fallback).

**Decisão.** Em `_criar_com_codigo_unico`, sem nome a conta é batizada com o
**próprio `co_usuario`** recém-gerado (`no_exibicao=dados.no_exibicao or codigo`).
O código já é a identidade pública da conta, é único (não cria uma multidão de
homônimos no ranking) e não depende de idioma. Trocar continua sendo pelo
`PATCH /conta/perfil`, e `_atualizar_existente` segue sem sobrescrever nome já
gravado.

Isso vale para **qualquer** caminho sem nome, não só o da Apple: nome reprovado
pela moderação (NEG-01) também cai no código, em vez de virar `NULL`.

**Alternativas consideradas.**
1. *O app manda um nome padrão* — descartada: o `co_usuario` só nasce **aqui**, na
   criação. Enquanto o portão de perfil está na tela, a conta não existe e o app
   não tem esse valor para enviar.
2. *Um rótulo traduzido ("Jogador"/"Player"/"Jugador") com número sorteado* —
   descartada: exige chave nos três `.arb`, pode colidir entre contas e obrigaria
   a decidir qual idioma usar num dado que é do servidor.
3. *Deixar `NULL` e o app tratar* — descartada: era o estado anterior, e o
   resultado visível era "Convidado" numa conta logada.

**Compatibilidade.** Mudança puramente aditiva no valor gravado; nenhum contrato
muda, nenhum campo entra ou sai da resposta. A build 1.0.1 (4) em campo continua
funcionando — ela só passa a receber um nome onde antes recebia `null`.

---

## 2026-07-30 — A data de nascimento sai; entra uma declaração de idade (13+)

**Contexto.** A App Review recusou a versão 1.0 (2) do app pela diretriz
**5.1.1(v)**: *"o app exige que o usuário forneça informação pessoal que não é
diretamente relevante para a funcionalidade principal"*, apontando nominalmente a
**data de nascimento**.

Ao conferir, a crítica procede. A data tinha exatamente dois usos: a trava de
idade mínima (13+, FR-005a) e o `ic_publico` do ranking global. Nenhum dos dois
precisa da **data** — os dois precisam apenas da resposta *"tem 13 anos ou mais?"*.
E ela não influenciava anúncio nenhum: o app serve não personalizados para todo
mundo, e convidado (sem data) já recebia o mesmo tratamento de quem tinha data.
Guardar a data era coletar mais do que se usava.

**Decisão.** Coluna `conta.tb001_usuario.ic_idade_minima_declarada` (migração
`0010_declaracao_idade`). A idade passa a ser **declarada** — mecanismo que a
própria Apple admite (*"verified or declared age"*, diretrizes 1.2.1(a) e 4.7.5).
A migração deriva a flag das datas existentes, **zera `dt_nascimento` em todas as
linhas** (decisão do dono: padronizar, ninguém fica com data) e recria as duas
views afetadas — `vw001_usuario`, cujo `SELECT *` é expandido na criação e não
enxergaria a coluna nova, e `vw101_ranking_global_geral`, cujo `ic_publico`
passaria a excluir todo mundo se continuasse olhando a data.

**Compatibilidade — o ponto delicado.** Há ~20 testadores com a build 1.0 (2)
instalada, e ela **só sabe enviar `dt_nascimento`**. Expand/contract: o serviço
aceita as duas formas (`resolver_declaracao_idade` centraliza a decisão), a data
recebida serve para **derivar** a declaração e é descartada, a coluna continua
existindo, e o 422 de "falta idade" mantém o código antigo
`data_nascimento_obrigatoria` — é por ele que o app 1.0 (2) decide abrir o portão
"Completar perfil". Renomear agora prenderia aqueles aparelhos num login que
nunca completa. A limpeza (dropar coluna, renomear o código) sai em `/v2`, depois
que o force-update retirar as versões antigas de campo.

**Alternativas descartadas.** (a) *Responder à App Review argumentando que a
diretriz 5.1.4(a) permite pedir data de nascimento para cumprir COPPA/LGPD*:
permite mesmo, mas o revisor aplicou 5.1.1(v) sabendo disso — risco alto de nova
recusa, sem ganho. (b) *Manter a data como campo opcional*: o revisor continuaria
vendo um campo "Date of Birth" na tela, e perderíamos a garantia de que toda conta
é 13+. (c) *Declared Age Range API da Apple (iOS 26+)*: é o caminho mais forte a
médio prazo, mas hoje só é obrigatória para apps 18+ e exigiria canal nativo — fica
para uma versão futura, com a declaração como fallback universal.

**Efeito colateral limpo.** `UsuarioAutenticado.dt_nascimento` foi removido: nenhuma
rota o lia, e a migração o deixaria permanentemente `None` — campo sem leitor e sem
valor só engana quem for confiar nele depois.

---

## 2026-07-21 — O laboratório de IA saiu deste repositório

**Contexto.** Este repositório era, na prática, dois projetos convivendo: a API
FastAPI (~2 MB de código) e um laboratório de IA (~2,7 GB entre datasets,
notebooks, geradores, oráculo tablebase e relatórios de treino). Mexer numa
coisa exigia rolar por cima da outra, e o `requirements.txt` misturava
`asyncpg` com `pygame`.

Os dois já viviam separados **de fato**, o que tornou a conta fácil:

- nenhum arquivo de `api/` importava `gerador_dados`;
- nenhum arquivo de `api/` lia `.tflite` ou o contrato de codificação;
- o `.dockerignore` já excluía `dados/ modelos/ notebooks/ resultados/ analise/
  visualizacoes/` da imagem;
- `requirements_api.txt` já era separado de `requirements.txt`;
- todo uso de `numpy` estava nos testes do Pontinhos.

O único acoplamento real eram **três** imports de `api.nucleo.log` feitos pelo
laboratório — um gerador de dataset importando código do servidor só para ter um
`print` organizado.

**Decisão.** O laboratório passa a viver em `../ia/`, dentro do repositório
guarda-chuva `arena-sagaz` (novo, privado no GitHub). Este repositório fica só
com a API. O logger virou `ia/nucleo/log.py`, cortando o último laço.

**Alternativas consideradas.**
1. *Deixar como estava* — descartada: o incômodo crescia a cada rodada de treino,
   e um novo jogo (damas, tabuleiros maiores) multiplicaria a bagunça.
2. *Criar um terceiro repositório `arena-sagaz-ia`* — descartada: mais um remoto
   para lembrar de empurrar, num projeto de uma pessoa só. O guarda-chuva já
   precisava existir para versionar design e documentação, que não estavam em git
   nenhum.
3. *Reescrever o histórico com `git filter-repo`* para levar os commits junto —
   descartada: o histórico continua acessível aqui até o commit da separação, e o
   custo/risco não se pagava.

**O que NÃO veio junto, de propósito.** O `.tflite` e o contrato da CNN. Hoje
nada em `api/` os lê — quem precisa do modelo é o app, que já o traz em
`assets/`. Se um dia o servidor precisar validar jogadas, o laboratório publica
em `ia/entregaveis/` e aí se copia.

**Rastro.** Todo arquivo movido está registrado, com SHA-256 de origem e destino,
em `../docs/reorganizacao/de_para_reorganizacao.csv`.

---

## 2026-08-04 — A vitrine deixa de ser um HTML único: imagens em `/img/`

**Contexto.** O app iOS foi publicado em 04/08/2026 (o Android seguia em revisão
na Play). O site precisava, no mesmo dia, de três coisas que só existem depois da
publicação: os **selos oficiais** das lojas no lugar da arte provisória, as
**capturas de tela** nas molduras que estavam vazias, e textos que parassem de
dizer "em breve" para uma loja onde o app já está.

Até aqui o site era **um único HTML autocontido** — decisão de 13/07, tomada
quando ele só tinha texto e fontes. Com as imagens, isso deixou de se pagar: são
9 capturas (3 telas × 3 idiomas) e 6 selos de loja. Em base64 dentro do HTML,
o arquivo saltaria de ~210 KB para ~450 KB, e **todo** visitante baixaria tudo —
inclusive as capturas dos dois idiomas que ele não vai ver.

**Decisão.** Uma terceira rota explícita, `GET /img/{nome}`, servindo de
`site/img/`. Os arquivos são lidos **no import** para um dicionário
(`_IMAGENS`), que **é** a lista de permissão: o que não está nele responde 404.
Cache de um dia (as capturas só mudam quando o app muda de cara) e o idioma vai
no **nome do arquivo**, então o cache nunca serve a imagem do idioma errado.

As **fontes continuam embutidas** em base64 — elas são necessárias no primeiro
quadro, e buscá-las de fora deixaria o texto invisível enquanto carregam. O teste
`test_landing_nao_depende_de_CDN` continua guardando isso.

**Alternativas consideradas.**
1. *Manter tudo em base64* — descartada pelo peso, acima.
2. *`StaticFiles` montado em `/img`* — descartada pela mesma razão que já barrava
   o mount em `/`: é uma superfície que serve o que estiver na pasta, hoje e no
   futuro. Um dicionário montado no import não tem "caminho" para percorrer.
3. *Hospedar as imagens fora (CDN/bucket)* — descartada: reintroduziria a
   dependência externa que o site existe para não ter, e a vitrine é também a
   **Support URL** que a Apple exige.

**Sobre os selos, que são marca de terceiro.** São as artes oficiais (Apple:
`tools.applemediaservices.com`; Google: `play.google.com/intl/<idioma>/badges`),
apenas redimensionadas — o que as duas diretrizes permitem. Não recolorir, não
recortar, não redesenhar. Usa-se a variante **preta** da Apple nos dois temas: o
selo do Google só existe em preto, e o branco da Apple ao lado dele deixava os
dois com aparências opostas no tema escuro.

⚠️ **O selo do Google Play entrou antes de o app estar na Play** — pedido do dono
em 04/08, ciente de que a diretriz de marca pede o app já publicado e o link
levando à ficha. Mitigação adotada: o `href` aponta desde já para a ficha
definitiva (passa a funcionar sozinho quando a Play publicar) e a nota sob os
selos diz, nos três idiomas, que o Android ainda está por vir.

*Ainda em 04/08, algumas horas depois, o dono reviu essa decisão e pediu para
**ocultar** o selo da Play até a confirmação — ver a entrada de 06/08 abaixo, que
o traz de volta.*

---

## 2026-08-06 — O selo da Google Play volta ao ar: os dois apps publicados

**Contexto.** A Play confirmou a publicação do app Android em 06/08/2026. O selo
estava comentado no HTML desde 04/08, quando o dono preferiu não exibir um botão
cujo link ainda daria em ficha inexistente. Com a publicação, ocultá-lo passou a
ser o defeito: o visitante de Android chegava à vitrine sem ter por onde baixar.

**Decisão.** Selo da Play reativado — bloco descomentado em `site/index.html` — e
a nota sob os selos (`hero_nota`) reescrita nos três idiomas: sai "Em breve na
Google Play", entra "Já disponível na App Store e na Google Play".

**O que NÃO foi preciso mexer,** porque já tinha sido preparado em 04/08: o
`href` do selo (sempre apontou para a ficha definitiva), os PNGs em `site/img/`,
a rota `/img/`, o `atualizarSelosDasLojas` (trata cada selo como opcional) e a
altura de 64px da classe `loja-selo-play` — que é 12px maior que a da Apple **de
propósito**, porque o PNG oficial do Google embute 10px de margem transparente em
cima e embaixo (arte de 84px num arquivo de 104px); com caixas iguais, a arte do
Google desenharia 42px contra 52px e pareceria menor.

**Alternativa considerada e descartada:** trocar o bloco comentado por um `hidden`
controlado no JS, para alternar sem editar HTML. Descartada — o comentário é o
mecanismo mais óbvio para quem lê o arquivo, e uma flag no JS convidaria a deixar
o selo servido e escondido, que é pior do que não servi-lo.

**Rede de segurança.** `test_os_dois_selos_de_loja_estao_visiveis` varre o HTML
**sem os comentários** e exige `linkApple`/`seloApple` e `linkPlay`/`seloPlay`. O
teste antigo (`..._conteudo_esperado`) não pegava isto: ele procura o domínio
`play.google.com` no texto, que continuava aparecendo **dentro** do comentário.
