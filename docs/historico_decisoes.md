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

## 2026-09-10 — O quadro do dia: a escada tem TRÊS degraus, não quatro

**Contexto.** Ao implementar T044, RF-DES-060a mandava pôr *"os quatro"* mascotes
no quadro desde 00:00 UTC. Foi o que fiz — e estava errado.

**RF-DES-203, de 04/09/2026, reescreve aquela leitura:** ⛔ **o personagem do dia
não joga contra si mesmo, logo não é régua naquele dia.** A escada tem **três**
degraus, e ela **roda junto** com o adversário:

    dia de Magno  →  Cacau · Pita · Tex     (mais encorajadora)
    dia de Cacau  →  Pita · Tex · Magno     (mais dura)

A regra de precedência da spec é explícita — *onde os blocos discordarem, vale o
mais recente* —, e é ela que resolve. Corrigido, com a precedência citada no
código para que a próxima leitura não refaça o mesmo caminho.

⚠️ **E RF-DES-204 fecha a consequência:** a banda *"a Pita resolve, a Cacau não"*
pressupunha adversário fixo; com rotação, a régua é a taxa dos **três que não são
o adversário**.

**Decisão de implementação — o tempo é encenado por SHA-256, e não por `random`.**
⛔ `hash()` do Python não serve: ele é salgado por processo desde a 3.3, e dois
reinícios do servidor dariam tempos diferentes para o mesmo mascote no mesmo dia
— o Magno mudaria de tempo no meio da tarde, e a conversa *"o Magno fez em 21
segundos"* deixaria de fazer sentido.

⚠️ **O XP dos mascotes também é encenado, e isso é decisão.** Calcular `Q` pela
fórmula real daria `1` para os quatro: `Q` soma parcelas de tentativas, tempo e
dicas, e o mascote não tem nenhuma das três de verdade. A **taxa medida** da
régua entra como modulador — é o único número real ali, e é o que faz um desafio
duro para o Magno lhe dar XP no pé da faixa.

**⛔ A trava de spoiler responde 403, e não 404.** O replay **existe**; o que
falta é o direito de vê-lo. Um 404 faria a tela dizer "não encontrado" para algo
que está lá, e a pessoa concluiria que o app perdeu a partida dela.

---

## 2026-09-10 — O ingestor completa a partida, e o `WHERE` é o que impede o estrago

**Contexto.** RF-DES-213: quando a linha de chegada cai antes do fim, a resolução
sobe com a partida ainda `em_andamento` e o resto dos lances sobe depois. Com
`ON CONFLICT (co_evento) DO NOTHING`, o segundo envio era **descartado em
silêncio**: a partida ficava `em_andamento` para sempre, sem `dh_fim` e sem
replay (RF-DES-187).

**Decisão 1 — `DO UPDATE`, com `WHERE co_status = 'em_andamento'`.** ⛔ O `WHERE`
não é detalhe: sem ele, a idempotência do `co_evento` viraria *"o último envio
manda"*, e um reenvio antigo do outbox **reabriria** uma partida já concluída —
pior que o defeito que a mudança conserta. Com ele, a mudança é de mão única:
`em_andamento → concluida/abandonada`, e nunca de volta.

**Decisão 2 — `RETURNING id_partida, (xmax = 0)`.** É o truque do Postgres para
distinguir INSERT de UPDATE: na linha recém-inserida `xmax` é zero. Sem isso não
daria para saber se o envio é o primeiro (grava tudo) ou a completação (grava só
o que falta) — e gravar tudo de novo **dobraria o XP da partida**.

**Decisão 3 — as jogadas viraram append-only.** `ON CONFLICT DO NOTHING`, ⛔ **sem
nomear a constraint**: o app reenvia a fita inteira com o **mesmo `id_jogada`**, e
esse conflito é na chave primária — nomear só `(id_partida, nu_ordem)` deixaria o
erro passar e o evento inteiro seria rejeitado.

**Decisão 4 — a sentinela do XP é a própria ausência.** `partida.tb003_xp_partida`
não tem chave natural, então nada no banco impede gravar as mesmas parcelas duas
vezes. Na completação, o XP e a progressão só entram se ainda não houver parcela
nenhuma.

**O job de expiração (T046) é o outro lado disso.** ⚠️ `dh_fim = COALESCE(dh_fim,
dh_inicio)`, e não `now()`: a partida parou quando a pessoa parou, e carimbar o
instante da expiração poria no log uma partida de sete dias de duração — qualquer
análise de tempo passaria a mentir. Sete dias porque **a fila do app segura
eventos sem rede**: fechar antes marcaria como abandonada uma partida que ainda
vai chegar completa, e aí o `WHERE` do ingestor barraria a completação, com razão,
por causa de uma decisão tomada cedo demais.

---

## 2026-09-10 — O cadeado 8 tem duas metades, e uma delas não cabe no CI

**Contexto.** T048 pede que *"toda resolução aponte para partida em estado
terminal, e **sem resolução para conferir é falha**"*. A segunda parte é sobre
**dados**, e o CI não tem Postgres.

**Decisão.** Duas metades, e a divisão é a mesma "conferência em dois níveis" que
o projeto já usa nas migrações:

- `tests/unitarios/test_partida_de_desafio_fechada.py` prova a **estrutura**: as
  três saídas de `em_andamento` existem, o replay recusa partida sem desfecho,
  abandonar não desfaz nada. Roda no CI, sempre.
- `scripts/conferir_desafio_no_banco.py` prova o **dado**, e ⛔ **reprova banco
  vazio** — porque um conferidor que aprova o nada ensina a confiar nele
  exatamente quando ele não está olhando nada. O portão T050 o executa.

⛔ **E há um caso no CI que falha se aquele script sumir.** Sem ele, a metade de
dados poderia desaparecer num commit e o CI continuaria verde — que é a cegueira
que os cadeados existem para impedir.

**O cadeado 7 (união de XP) e a regra contra listas escritas à mão.** A proibição
do projeto é contra cadeado que *acha* que sabe o que existe. Aqui o padrão é o
oposto: `api/nucleo/uniao_xp.py` é o **contrato** (o que a união cobre) e a
varredura das migrações é a **realidade** — o cadeado falha quando a realidade tem
algo que o contrato não tem. Uma tabela de XP nova quebra o CI, e o conserto é uma
linha tomada com decisão consciente.

---

## 2026-09-10 — O quinto buraco: cadeado que lê texto em vez de `ast`

**Contexto.** Ao escrever o cadeado de *"validar não é jogar"* (T043a), usei
`assert "escolher_lance" not in fonte`. Ele **reprovou o código correto** — porque
a docstring do módulo auditado menciona `escolher_lance` justamente para dizer que
não o chama.

**É a quinta ocorrência da mesma espécie neste projeto**, e a primeira fora das
migrações. As quatro anteriores estão na docstring de
`tests/unitarios/leitura_de_migracao.py`; esta entrou lá junto.

**A regra, generalizada:** todo cadeado que pergunta *"este arquivo faz X?"* lê
`ast`, e nunca texto. Um `in fonte` acerta enquanto ninguém escrever um comentário
sobre o assunto — e o comentário sobre o assunto é justamente o que um arquivo bem
documentado tem.

⚠️ O mesmo cuidado apareceu duas vezes mais no mesmo dia, e as duas foram
consertadas do mesmo jeito: o cadeado do `DO UPDATE` recorta o comando `INSERT`
em vez de ler o arquivo (a docstring do módulo descreve as três formas de
idempotência que ele usa), e o do `DO NOTHING` das jogadas busca um trecho longo o
bastante para não casar com outro.

---

## 2026-09-10 — Onze tipos novos de desafio, e o que eles revelaram do formato

**Contexto.** RF-DES-128, pedido do dono em 03/09: *"eu espero na fase de
implementação que se proponha diversos outros tipos criativos de desafios para os
2 jogos"*.

**Decisão — a proposta é código validável, e não prosa.** `job/tipos_propostos.py`
traz onze receitas (cinco de Pontinhos, seis de damas), e cada `js_chegada` passa
pelo **mesmo avaliador** que julgaria o desafio de verdade. 60 testes provam duas
coisas: que cada uma é formalmente válida, e ⛔ que **nenhuma exige vocabulário
novo** — o critério de ser publicável como **dado**, e não como release.

**⛔ Nenhuma entrou em `RECEITAS`**, e há cadeado que falha se alguém as importar.
Faltam três coisas, e nenhuma é minha: linha em `desafio.tb901_tipo_desafio` (é
migração, e o `data-model.md` é o que o dono pré-validou), chave de i18n nos três
`.arb` (BLOCO 3) e vetor de verificação.

**O que o exercício revelou** — três folgas do formato que o catálogo atual não
mostrava:

1. **A janela `turnos_do_adversario` nunca foi usada.** Dois dos onze a usam, e
   ela abre uma família inteira de objetivos **defensivos** — *impedir* em vez de
   *fazer*, que é metade do Pontinhos e das damas.
2. **A conjunção de cláusulas nunca foi exercitada.** Três dos onze usam duas, e é
   isso que separa *"feche caixas"* de *"feche caixas sem entregar"*.
3. ⚠️ **Nenhum precisou de medida nova** — é a prova prática de que o catálogo de
   tipos é estrutura de dados, e não `enum` de código. Era a promessa de
   RF-DES-128; agora está medida.

---

## 2026-09-10 — O painel de curadoria é HTML servido pela API, sem framework e sem dependência nova

**Contexto.** RF-DES-012e pede *"página administrativa servida pelo próprio
backend, protegida por token, sem app novo e sem build de Flutter Web"*. O
Flutter Web foi descontinuado como alvo em 2026-07, e ressuscitá-lo para uma
ferramenta interna de **um** usuário criaria um segundo pipeline de build, um
segundo deploy e um segundo lugar onde a identidade visual envelhece.

**Decisão.** `api/desafios/painel/`, servido em `/painel/desafios` — HTML gerado
por string, CSS embutido, **zero JavaScript**, toda ação num `<form method=post>`
com o padrão POST → 303 → GET.

**Três dependências que NÃO entraram, e o motivo de cada uma:**

- **Jinja2** — seria conforto de escrita, ao preço de um pacote novo na imagem
  que serve o app em produção. A troca foi escapar à mão, com uma regra única:
  *todo* valor vindo do banco passa por `_txt()`. Sem exceção — nem para o que
  "claramente" é um UUID, porque a próxima coluna a entrar não será.
- **`python-multipart`** — `Form(...)` do FastAPI e até `await request.form()` do
  Starlette 1.0 o exigem, mesmo para `application/x-www-form-urlencoded`. O corpo
  de um `<form>` sem `enctype` é lido pela **biblioteca padrão**
  (`urllib.parse.parse_qsl`), que trata percent-encoding, `+` como espaço e
  chaves repetidas. ⛔ Isso não aceita `multipart/form-data`, e não precisa: não
  há campo de arquivo neste painel.
- **o motor de jogo** — a posição é desenhada em SVG a partir do JSON cru
  (`painel/desenho.py`), sem importar `motores/`. A imagem da API instala
  `requirements_api.txt`; quem instala o runtime de inferência é o
  `Dockerfile.job`. Um `from motores.pontinhos...` derrubaria a API inteira no
  import — e a rota que quebraria primeiro seria o `/health`, que é o
  `healthcheckPath` do Railway.
  ⚠️ **Desenhar não é conferir:** quem prova que a posição é alcançável, que a
  vez bate e que o placar fecha é `job/posicao_inicial.conferir()`, na geração,
  com o motor de verdade. Se aquilo passou, o JSON é confiável.

**A precisão que virou duas ações.** RF-DES-153 diz que aprovar acontece *antes*
de o desafio entrar em qualquer coleção, e que agendar é ato separado. O painel
reflete isso: **aprovar** mexe em `desafio.tb001_desafio.co_curadoria`;
**agendar** cria ou move a linha de `desafio_dia.tb001_desafio_dia`.

⛔ **Só aprovado entra no calendário**, e a regra vive em `painel/servico.py`, não
num botão desabilitado. Um `<form>` ausente na tela é decoração que um `curl`
ignora; e o estrago seria silencioso — um candidato agendado ocupa a data
(`un001_dia` recusa outro) e a rota não o serve, então o app abriria com o dia em
branco e **nada** acusaria.

**Segredo próprio, e não o do broadcast.** `PAINEL_CURADORIA_TOKEN`, vazio por
padrão (= painel desabilitado, como o broadcast). São dois porque quem pode
disparar notificação para toda a base não deveria, pelo mesmo token, poder
aprovar conteúdo que vai ao ar. Entrou no `.env.example` e no
`specs/006-conta-nuvem/checklist-producao.md`.

**O cookie, e por que ele existe.** Navegador não manda cabeçalho próprio ao
seguir um link, e `?token=` em toda URL deixaria o segredo no histórico e no
`Referer`. A primeira visita traz o token na query; o servidor confere, grava um
cookie `HttpOnly`/`SameSite=strict` (`Secure` só em produção — em
`http://localhost` o navegador o descartaria **sem avisar**) e redireciona para a
URL limpa.

**Alternativas consideradas.** (a) Papel de administrador no banco: exigiria
coluna nova em `conta`, migração em schema **de produção** e uma superfície de
escalonamento de privilégio, tudo para uma página que uma pessoa abre. (b)
Servir o painel sob `/v1`: `/v1` é a promessa feita aos apps em campo, e uma tela
interna não participa dela — o painel mora ao lado de `/legal`, que também é
conteúdo web.

---

## 2026-09-10 — A vigilância avisa antes de a fila acabar, e conta dias consecutivos

**Contexto.** RF-DES-012f pede duas seções de alerta no painel, vistas na **mesma
visita** em que os candidatos são aprovados. Elas moram ali, e não num canal
próprio, porque o SDK de telemetria saiu de escopo em 02/09/2026 e o backend
**não tem canal de alerta**: sem um lugar que o dono já abre por outro motivo,
"alerta" vira linha de log que ninguém lê.

**Decisão 1 — o limiar do aviso é o `DIAS_MINIMOS` do job (7).** O mesmo número,
de propósito. Se divergissem, o painel chamaria de confortável uma fila que o job
considera curta, e um dos dois estaria mentindo. Abaixo de 7 é atenção; 3 ou
menos, crítico.

**Decisão 2 — a cobertura conta dias CONSECUTIVOS a partir de hoje.** Um
calendário com hoje e o dia 20 preenchidos tem **um** dia de folga, não dois: é a
sequência sem buraco que diz quando o app abre vazio pela primeira vez. Somar
dias soltos daria um número maior e uma promessa falsa.

**Decisão 3 — ⛔ candidato agendado NÃO conta como dia coberto.** É a armadilha
silenciosa desta feature: a data fica ocupada (`un001_dia` impede outro desafio
de entrar), a rota só serve `aprovado`, e o app abre com o dia em branco. Contar
essa data como coberta faria o painel jurar que está tudo bem exatamente no dia
em que não está.

**Decisão 4 — os três contadores de auditoria aparecem juntos.** `divergente = 0`
sozinho significa duas coisas opostas — *"conferimos tudo e está certo"* e
*"ninguém conferiu nada"* —, e é o contador de **pendentes** que as separa. Há
aviso vermelho próprio para o caso de haver resoluções e nenhuma conferida: é o
sinal de que o avaliador (T043a) não está rodando, e como `co_auditoria` tem
`DEFAULT 'pendente'`, **nada mais no sistema acusaria**.

---

## 2026-09-10 — A reprise copia com `INSERT ... SELECT`, e os feitos vão antes do dia

**Contexto.** RF-DES-152, precisado pelo dono em 04/09/2026: a reprise é uma
**cópia** — identificador próprio, ponteiro para a origem, marca de reprise —, e
não o mesmo desafio publicado de novo. É essa regra que mantém o vínculo
dia↔desafio em 1:1, o quadro da reprise limpo e o teto de duas dicas por desafio
sem exceção.

**Decisão 1 — `INSERT ... SELECT`, e não ler em Python e reescrever campo a
campo.** Uma coluna nova em `tb001_desafio` entraria na tabela e ficaria de fora
da cópia **sem que nada acusasse**: a reprise sairia com um campo `NULL` que
ninguém procuraria. Só as cinco colunas que mudam estão escritas, cada uma com o
motivo ao lado.

**Decisão 2 — os feitos de saída são copiados ANTES de o dia ser publicado.** Sem
`tb003_feito_desafio`, a reprise vai ao ar pagando **só o piso de 18 XP**, e nada
dá erro: o `INSERT` do desafio passa, o app baixa a linha, e a diferença só
aparece no extrato de quem jogou — que ninguém confere. Publicar o dia antes
abriria uma janela curta, intermitente e impossível de reproduzir depois.

**Decisão 3 — não há cadeia de cópias.** A origem apontada é sempre a linha
**original**: `COALESCE(id_desafio_origem, id_desafio)`. Sem isso, *"quantas vezes
este desafio já foi ao ar"* deixaria de ser uma consulta e viraria travessia
recursiva.

**Os números da elegibilidade, e de onde cada um veio.** ≥ 20 tentativas (o mesmo
piso de RF-DES-063: "2 de 3 resolveram" não é uma medida), taxa ≥ 70% (o alvo de
RF-DES-014), e ≥ 60 dias desde a estreia — repetir o desafio da semana passada
parece o job travado. Entre as elegíveis, ganha a de **menor participação**
(RF-DES-029, textual).

**⛔ Sem candidata, exceção — não `None`.** `RepriseImpossivel` existe porque este
é o pior caso operacional da spec: a fila acabou **e** não há reprise. Um `None`
devolvido calado faria o job "terminar bem" no dia em que o app abre sem desafio
— indistinguível, no painel do Railway, de um dia normal.

---

## 2026-09-10 — Aplicar migração tem runbook próprio, e um conferidor que lê as migrações

**Contexto.** O dono perguntou como executar o `alembic upgrade` das `0018`,
`0019` e `0020`. A resposta não cabia numa mensagem: `upgrade` que termina sem
erro **não prova** que o banco ficou como deveria — foi a lição da `0017`, em que
o defeito perigoso era o silencioso (VIEW que deixa de enxergar coluna, dimensão
que ninguém populou).

**Decisão.** O procedimento vira arquivo — `docs/runbook-migracoes-desafio.md` —
e a conferência vira script: `scripts/conferir_migracao_desafio.py`, somente
leitura, com código de saída (`0` confere · `2` reprovou · `1` não conectou).

⛔ **E ele não tem lista de tabelas escrita à mão.** O esperado é extraído das
próprias migrações (`CREATE TABLE` / `CREATE VIEW`), porque lista à mão envelhece
calada: alguém acrescenta uma tabela, esquece de acrescentá-la no conferidor, e
ele fica **verde e cego** — o defeito que já custou quatro fluxos de fim de
partida no app.

**O que ele confere:** a revisão do alembic · as 15 tabelas e as 15 VIEWs · as
cinco dimensões populadas pela migração · a `tb903_perfil_dificuldade` **vazia**,
que é o certo (quem a preenche é o job) · o `CHECK` `ck_partida_modo` aceitando
`'desafio'`. Coluna que a VIEW irmã não expõe sai como **AVISO**, não como falha:
há VIEW que reduz de propósito, e um portão que acusa o que é correto ensina a
ser ignorado.

**Mudança de uma linha, no mesmo passo:** `scripts/identificar_banco.py` passou a
listar `desafio` e `desafio_dia` entre os schemas do projeto — sem isso, o
diagnóstico rodado **depois** da migração não mostraria o que ela criou.

**✅ Aplicado no `des` no mesmo dia**, revisão `0017` → `0020`, e conferido: 15
tabelas, 15 VIEWs, **126 colunas na ordem**, cinco dimensões populadas,
`tb903_perfil_dificuldade` vazia e `ck_partida_modo` aceitando `'desafio'`. ⛔ No
`prd` não, e não vai antes do portão T050.

**A conferência de colunas (2b) nasceu depois de aplicar, e por causa disso.**
Com o `des` migrado, o dropa-e-recria da §8b ganhou um passo silencioso: editar a
`0018` e rodar `upgrade head` **não faz nada** — o alembic não reaplica revisão
aplicada —, e o cadeado contra o `data-model.md` continuaria verde, porque ele
compara o documento com o arquivo e **nenhum dos dois é o banco**. A 2b é o único
lugar do projeto onde o banco entra na comparação. ⚠️ Ela **não escreve o próprio
parser**: importa o do cadeado, porque ler SQL de migração tem sutileza bastante
(f-string, strings adjacentes, comentário dentro do SQL) para duas
implementações discordarem — e a que discordasse calada seria esta, a que não
roda no CI.

**E aí apareceu o quarto buraco da mesma espécie.** Atualizar o cabeçalho da
`0020` — que menciona `tb903_perfil_dificuldade` justamente para dizer que **não**
a toca — fez `test_o_sentinela_9999_existe_se_ha_dimensao` reprovar: ele lia o
**arquivo inteiro**, e não distinguia o que a migração diz do que ela faz. Ao
corrigi-lo, a cegueira oposta apareceu: a `0013`, a `0015` e a `0017` passavam
**porque a palavra "9999" estava numa docstring** — nenhuma delas cria dimensão,
todas apenas fazem `JOIN` com uma. Duas cegueiras que se anulavam, e por isso
nunca deram sinal.

Agora a marca é **criar** (`CREATE TABLE …tb9NN_`), não mencionar, e o SQL vem de
`ast`. O extrator saiu de dentro do cadeado e virou
`tests/unitarios/leitura_de_migracao.py` — **um** lugar, usado pelos dois
cadeados e pelo script, com o histórico dos quatro buracos escrito na docstring.
Todos foram o mesmo defeito: o cadeado confundiu o texto do arquivo com o
comando executado.

---

## 2026-09-09 — A migração deixa de esperar leitura, e ganha um cadeado contra o modelo

**Decisão do dono:** *"Eu não vou conferir código de Alembic. Eu já pré validei o
data-model.md."*

Os cabeçalhos das três migrações pediam leitura e aprovação antes de rodar. Isso
saiu: o que foi aprovado é o **modelo**, e a migração é a tradução dele.

⚠️ **A decisão transfere o peso da prova**, e a contrapartida entrou junto:
`tests/unitarios/test_migracao_bate_com_data_model.py` compara o `data-model.md`
com as migrações `0018` e `0019` — tabela a tabela, coluna a coluna **na ordem**,
constraint a constraint, índice a índice.

**Por que a ordem das colunas entra na comparação:** a regra §8b diz que campo
importante não fica no fim da tabela. Uma comparação de conjuntos perderia
exatamente isso — uma coluna que escorregasse para o fim passaria por qualquer
teste que só olhasse *quais* colunas existem.

**O que ele deliberadamente não compara** é o texto dos `CHECK`: o documento os
escreve com outra indentação, e comparar texto formatado geraria alarme falso a
cada reindentação — e alarme falso é o começo de todo teste ignorado. Quem guarda
o **conteúdo** dos `CHECK` é `test_modelos_desafio.py`, que lê os valores e os
compara com os `Literal` do código. Dois cadeados, duas metades.

⚠️ **E ele não pode ganhar saída de emergência.** Um caso do próprio arquivo lê a
árvore de si mesmo com `ast` e falha se aparecer um `skip`, `skipif` ou `xfail` —
porque um `skip` aqui devolveria a pré-validação ao estado de cheque em branco.

**Provado que reprova**, com três sabotagens simultâneas na `0018`:
`nu_versao_catalogo` movida para o fim da tabela, `co_versao_minima` alargada de
`VARCHAR(20)` para `VARCHAR(30)`, e `ck005_solucao` apagada. As três foram
apontadas pelo nome.

⚠️ **O `ast` foi necessário de novo**, e pelo mesmo motivo da terceira vez: as
migrações escrevem comandos curtos como strings adjacentes (`"CREATE INDEX x "`
`"ON tabela (coluna)"`), e no arquivo há uma aspa e uma quebra de linha entre o
nome e o `ON` — nenhum regex de SQL casa com isso. O cadeado tem de ler o que o
código **executa**, e não como ele está escrito.

**O que continua valendo:** `scripts/identificar_banco.py` antes de qualquer
`alembic upgrade`. Isso nunca foi sobre aprovar conteúdo — é sobre não escrever
no banco errado.

---

## 2026-09-09 — O job do Desafio do Dia: três decisões que saíram de medida, não de gosto

O BLOCO 2 (T018 a T038) trouxe `job/` para o backend. As três decisões abaixo
apareceram **durante** a implementação, cada uma a partir de um número.

### 1. A geração precisa de ORÇAMENTO de busca — medido, não suposto

Sem teto, **uma única geração de damas passou de 6 minutos sem terminar**. O
motivo não é o motor estar lento: o contrato do nível foi calibrado para o
**aparelho de alguém** esperando ~0,8 s por lance, e no job são dezenas de
candidatos × vários lances cada.

O motor usa o **menor** entre o teto do contrato e o do orçamento — um define o
*nível*, o outro protege o *job*. Deixar o maior mandar anularia um dos dois.

⚠️ **O preço, dito em voz alta:** com teto baixo o Sagaz joga um pouco pior, e o
gabarito pode não ser a solução mais curta. É aceitável — o gabarito prova que o
desafio **tem** solução (RF-DES-196), e não que aquela é a melhor.

Três orçamentos diferentes, e a diferença entre eles é a frequência: geração
(60 mil nós), medição da régua (20 mil, porque ela roda 3 × 20 vezes) e prova de
término (8 mil, porque ali não se quer jogar bem, se quer **acabar**).

### 2. Os MOLDES de posição, e por que o gerador ingênuo não serve para damas

O gerador ingênuo parte da posição inicial e joga lances aleatórios até chegar a
algo interessante. Isso funciona no Pontinhos e **não funciona nas damas**:
medido, três tentativas de gerar *"coroe uma dama em 6 lances"* a partir de 40
lances aleatórios deram **zero** candidatos em 35 segundos.

A razão é do jogo: coroar exige atravessar o tabuleiro, e uma abertura aleatória
quase nunca deixa uma peça perto da oitava fileira com caminho livre.

**Molde** é uma posição de onde o objetivo é alcançável, escrita à mão e validada
pelo motor; o gerador a **varia** com poucos lances legais. ⚠️ Molde **não é
garantia**: se a variação destruir o objetivo, o gerador não acha solução e tenta
outra. Com moldes, dois candidatos de damas saem em 12 segundos.

### 3. O perfil de dificuldade é um CARIMBO, e não uma tabela de parâmetros

`co_versao_perfil` não tinha dono no código. A tentação era criar
`motores/perfis/perfil-2026-09.json` com os números de cada mascote — e isso
seria uma **segunda fonte da verdade**: os números já existem nos dois contratos
do espelho, e as duas cópias divergiriam no primeiro ajuste.

`job/perfil.py` lê os contratos vigentes, tira o SHA-256 de cada um e monta as
oito linhas de `desafio.tb903_perfil_dificuldade`. O `js_perfil` de cada linha
traz os números **extraídos** dos contratos — copiar para *explicar* não é
segunda fonte: quem **roda** continua sendo o contrato, e o hash ao lado prova
qual foi.

⚠️ **A versão deriva dos hashes** (`perfil-<8 hex>`), como `co_versao_motor`. Um
`perfil-2026-09` escrito à mão envelheceria calado: alguém afina a Pita, esquece
de subir a versão, e as medições novas ficam indistinguíveis das velhas.

### O que o cadeado 2 pegou, e por que isso é uma boa notícia

O arquivo que liga a linha de chegada aos motores nasceu como
`motores/juiz_do_desafio.py`, e o cadeado recusou: **a camada de motores não
conhece desafio** (RF-DES-165). Ele virou `motores/juiz.py` — o nome diz o que a
peça faz, e não para quem ela serve.

⚠️ Dois buracos de cadeado foram consertados no caminho, ambos da mesma espécie —
o teste que deixa de olhar sem avisar: o extrator de comandos de migração
ignorava `op.execute(f"...")` **inteiro**, e o parser de `INSERT`, sem
ponto-e-vírgula, esticava o corpo até o fim do arquivo e lia as colunas da tabela
seguinte como valores.

---

## 2026-09-09 — Os modelos do Desafio do Dia não são ORM, e o catálogo de feitos vira manifesto

Duas decisões da mesma tarde, ao escrever `api/desafios/` (T024 a T026).

### 1. Não há `class Desafio(Base)` — e não deveria haver

As tarefas T024/T025 pediam *"models SQLAlchemy"*. Ao implementar, isso não se
sustenta neste repositório: **o projeto não tem ORM declarativo em lugar nenhum**.
Toda a API fala com o banco por `sqlalchemy.text(...)` com parâmetros nomeados,
lendo pelas VIEWs — `api/sincronizacao/repositorio.py` tem mais de mil linhas
assim, e `api/nucleo/banco.py` entrega uma `AsyncSession`, não uma
`DeclarativeBase`.

Introduzir mapeamento declarativo agora criaria **duas formas** de falar com o
mesmo banco, e as duas discordariam em silêncio no primeiro ponto em que o
mapeamento envelhecesse. E há um agravante de convenção: um `Mapped[...]` mapeia
**tabela**, enquanto a regra do projeto é que a leitura nunca toca a tabela.

**O que os dois módulos entregam, então:** os vocabulários fechados como
`Literal` (o mesmo recurso que `api/conta/modelos.py` usa para `IdiomaSuportado`),
os nomes das VIEWs em constantes, e os modelos Pydantic do que cruza fronteira.

⚠️ **O preço declarado:** os vocabulários passam a existir duas vezes — como
`CHECK` na migração e como `Literal` no modelo. É proposital (cada um pega o erro
num momento diferente), mas as duas cópias podem se separar sem dar erro. Por
isso `tests/unitarios/test_modelos_desafio.py` lê o `CHECK` da migração e o
`Literal` do modelo e exige que digam a mesma coisa — inclusive os números da
dimensão de tipo de XP, que o código guarda como constantes nomeadas em vez de
espalhar `nu_tipo_xp == 5`.

### 2. O catálogo de feitos passa por um manifesto, e não por comparação direta

⚠️ **O CI não pode comparar Dart com Python.** Cada repositório roda sozinho, sem
o outro no disco. É a mesma lição do RF-DES-143a, que já produziu o
`MANIFESTO_HASHES.json` do espelho: a comparação entre repositórios **não é
executável**; o que é executável é cada lado conferir a sua cópia contra um
manifesto versionado.

```text
fonte da verdade   lib/core/feitos/catalogo_feitos.dart      (o aplicativo)
        ↓ dart run tool/gerar_manifesto_feitos.dart
manifesto          catalogo_feitos.json, em DUAS cópias byte-idênticas
        ↓                                    ↓
cadeado do app     cadeado do backend (T026, migração 0018)
```

Os dois são de **nível de CI e ⛔ nunca pulam**: manifesto ausente é falha, não
motivo para pular. Um cadeado que se desliga quando o alvo some não guarda nada.

**O que o gerador acrescenta ao que o Dart já tem**, e por isso ele existe em vez
de um `jsonEncode` de três linhas: o `nu_feito` (numeração por blocos, com folga:
comuns 1-9, Pontinhos 10-19, velha 20-29, damas 30-39, sessão 40-49), o rótulo
para o painel de curadoria, o sentinela `9999` — que ⛔ **não** vem do catálogo do
app, de propósito: declará-lo lá ofereceria a alguém a chance de usá-lo como
feito de verdade — e a tradução dos `enum` de camelCase para o snake_case do
banco (`marcoAtingido` → `marco_atingido`).

⚠️ **O atributo mais perigoso é `co_direcao`.** Um feito marcado `maior_melhor`
de um lado e `menor_melhor` do outro **não produz erro nenhum**: só paga mais XP
a quem jogou pior. Ele tem caso próprio nos dois cadeados, e os dois foram
provados que reprovam.

---

## 2026-09-09 — O serviço do job se declara em `railway.job.json`, não dentro do `railway.json`

**Contexto.** A T018 pedia "declarar o **terceiro serviço** do Railway em
`arena-sagaz-backend/railway.json`". Ao implementar, a frase não se sustenta ao pé
da letra, e vale registrar por quê antes que alguém tente de novo.

**O fato.** O `railway.json` **não modela vários serviços**. O schema
(`railway.schema.json`) descreve **um** serviço: um `build` e um `deploy`. Não há
chave `services`, nem lista. O que o Railway oferece é *config as code* **por
serviço**: cada serviço aponta, nas suas configurações, para **qual arquivo** do
repositório ele lê.

**Decisão.** Dois arquivos, um por serviço:

| arquivo | serviço | o que declara |
|---|---|---|
| `railway.json` | API | `Dockerfile`, `healthcheckPath: /v1/health`, reinício `ON_FAILURE` |
| `railway.job.json` | job | `Dockerfile.job`, `cronSchedule`, reinício **`NEVER`**, sem healthcheck |

⚠️ **O passo que não dá erro quando é esquecido** está no console, e por isso
entrou no `checklist-producao.md`: se o serviço do job não for apontado para
`railway.job.json`, ele lê o `railway.json` e sobe **uma segunda API** — deploy
verde, healthcheck verde, e o desafio do dia nunca gerado. É exatamente a classe
de falha silenciosa que o projeto vem catalogando desde o push que dizia
`Everything up-to-date`.

**Alternativa descartada:** um `railway.json` com um objeto por serviço e um
script que o traduz. Inventaria um formato que o Railway não lê, e a tradução
seria mais uma peça a manter entre o que está escrito e o que roda.

**O cron entra aqui, e não em T038.** `cronSchedule: "0 6 * * *"` (06:00 UTC =
03:00 em Brasília) é **cadência de operação**, não regra de produto — RF-DES-011
diz isso com todas as letras: *"a frequência do job não é a frequência do
desafio"*. Quem garante que nenhum dia fica descoberto é a folga de 7 a 30 dias da
T038, não este horário; mudá-lo não muda o conteúdo de nada.

---

## 2026-09-09 — A camada de motores nasce: quatro decisões que o código não conta sozinho

**Contexto.** O BLOCO 1 do Desafio do Dia (T004 a T017) trouxe `motores/` e
`espelho_laboratorio/` para o backend. O que segue são as decisões que apareceram
**durante** a implementação e não estavam escritas em lugar nenhum.

### 1. A versão do motor sai dos hashes do espelho, não de um número à mão

`co_versao_motor` é `damas-py-<8 hex>` e `pontinhos-py-<8 hex>`, onde os oito
dígitos são o começo do SHA-256 da lista de hashes dos arquivos daquele motor no
manifesto do espelho.

**Por quê.** Um número escrito à mão envelhece calado: alguém reespelha um motor
novo, esquece de subir a versão, e as medições novas ficam indistinguíveis das
velhas no banco. É exatamente a armadilha registrada em 26/08/2026, e o campo
existe para não cair nela.

**Alternativa descartada:** usar a versão do contrato. Ela descreve a **forma** do
contrato, não o motor — dois motores diferentes podem gerar contratos de mesma
versão.

### 2. O adaptador traduz o motivo de empate; o espelho não se toca

O motor de damas do laboratório devolve o motivo em **prosa** — `"posicao repetida
3 vezes (art. 98)"` —, porque o destino dele é o PDN da partida, onde "empatou"
sem dizer o artigo é o registro que não deixa auditar depois.

RF-DES-019b exige que o servidor devolva **identificador**, com o app traduzindo
pelo `l10n`. ⛔ Consertar isso dentro do espelho está fora de questão: ele é cópia
byte-idêntica, e editá-lo derruba o cadeado 6. Então a tradução mora no adaptador
(`_MOTIVOS_DE_EMPATE`), e ela **falha alto** em motivo desconhecido — deixar a
prosa passar mandaria português para dentro de `co_motivo`, e o app cairia na tela
de "motivo desconhecido" sem que ninguém soubesse por quê.

⚠️ **Nota de fato:** o app hoje mostra essa prosa crua no subtítulo da tela de
resultado das damas, então quem joga em inglês ou espanhol vê português sem
acento. É defeito do app, tem tarefa própria (T003), e não se conserta daqui.

### 3. O espelho tem DUAS origens, e elas não se fundem

`espelho_laboratorio/` recebe do `ia/` (o motor de damas, o contrato dele, a
extração dos 12 canais e as regras do Pontinhos) **e** do
`arena-sagaz-frontend/` (o contrato de dificuldade do Pontinhos, o `.tflite` de
19,8 MB, o mapeamento de rótulos e o contrato de codificação).

**Por quê.** A fonte da verdade de cada jogo está num lugar diferente, de
propósito (`research.md` §R-20): no damas a política vive no Python e o contrato é
gerado dela; no Pontinhos ela vive em Dart e o contrato é a declaração dela. ⛔
Fingir que os dois vêm do laboratório criaria uma segunda fonte de números de
dificuldade — o que o contrato existe para impedir.

Os arquivos do laboratório preservam a **estrutura de pacotes**
(`jogos/jogo_damas/motor/...`), porque o motor se importa por caminho absoluto e
editar esses imports quebraria a cópia byte-idêntica. Os do app vão para a raiz
do espelho: um JSON do aplicativo dentro de `jogos/` seria mentira sobre de onde
ele veio.

### 4. `newline=""` em todo arquivo que é comparado por hash

O `write_text` do Python converte cada quebra de linha em CR+LF no Windows. O
contrato de damas gravado assim tinha **667 bytes a mais** que o texto medido, e o
hash declarado no manifesto não descrevia o arquivo declarado — o manifesto pegou
o próprio defeito no dia em que nasceu.

Todo arquivo que atravessa repositórios e é comparado por SHA-256 agora é gravado
com `newline=""` e marcado `-text` no `.gitattributes` dos três repositórios. ⛔
Não troque `-text` por `text eol=lf`: `text` ainda **normaliza** na entrada, e
normalizar é a operação que se quer ausente dos dois lados de uma comparação de
bytes.

**Custo aceito, dito em voz alta:** 19,8 MB de `.tflite` entram no Git do backend.
É o preço declarado de RF-DES-148 — o Railway constrói a imagem a partir deste
repositório, e o que não estiver aqui dentro não existe na nuvem.

---

## 2026-09-09 — O runtime de inferência do job: `ai-edge-litert` confere com o do app

**Contexto.** O `research.md` §R-03 da spec 009 escolheu `python:3.11-slim` +
`ai-edge-litert` para a imagem do job em batch, e deixou um ponto explícito a
confirmar antes de qualquer outra coisa (tarefa **T001**): a versão que instala em
`linux/amd64` + Python 3.11 e abre o `.tflite` de 19,8 MB. O plano B declarado era
`tensorflow-cpu` — imagem muito maior, mesmo resultado. ⛔ Reimplementar a
inferência nunca foi opção (RF-DES-018b).

**O que se mediu.** Duas coisas, e a segunda é a que importa:

1. **O wheel existe.** `ai-edge-litert` 2.2.0 publica
   `cp311-manylinux_2_27_x86_64` (21,3 MB). O `python:3.11-slim` é Debian
   bookworm, glibc 2.36 — folgado sobre o 2.27 exigido.
2. **Os números batem.** `scripts/conferir_runtime_inferencia.py` roda 12 tensores
   determinísticos `(1,4,3,12)` pelo modelo pequeno e compara a saída dos 31
   neurônios, arredondada a 6 casas. O `ai-edge-litert` 2.2.0 e o
   `tensorflow.lite` 2.21.0 — a **mesma** biblioteca C que o `tflite_flutter` do
   app embrulha — produziram saída **idêntica, número por número**.

**Decisão.** Vale o **plano A**: `ai-edge-litert==2.2.0` no `requirements_job.txt`.
`tensorflow` não entra na imagem do job.

**Por que a conferência é por número, e não por "abriu".** "Abrir" falha alto e
cedo; o risco de verdade era abrir e devolver números **um pouco** diferentes. A
calibração do desafio sairia então de um adversário que não é o adversário que a
pessoa enfrenta, e nada no sistema denunciaria — é o mesmo tipo de defeito
silencioso que o contrato de codificação existe para impedir.

**A execução em `linux/amd64` virou PORTÃO DE BUILD.** A prova rodou em Windows
(Python 3.12 para o TensorFlow, 3.14 para o LiteRT), e a máquina do dono **não tem
Docker, nem WSL, nem Python 3.11** — os três foram conferidos em 09/09/2026. Rodar
o script dentro de `python:3.11-slim` exigiria instalar um deles só para isso.

Em vez disso, a conferência entra no **`Dockerfile.job`** (T018): depois do
`pip install`, a imagem roda `scripts/conferir_runtime_inferencia.py` contra o
`scripts/referencia_runtime_inferencia.json` versionado, e **o build falha** se
divergir.

⚠️ **É melhor que o comando avulso, e não um contorno.** Um comando manual se roda
uma vez e envelhece; o portão re-confere a cada imagem construída — inclusive no
dia em que alguém subir a versão do `ai-edge-litert` sem pensar. E é a **única**
execução em `linux/amd64` que o projeto tem.

**O que sustenta a decisão enquanto o build não roda**, medido em 09/09/2026:

| evidência | resultado |
|---|---|
| o wheel existe para o alvo | `ai_edge_litert-2.2.0-cp311-cp311-manylinux_2_27_x86_64.whl`, 21,3 MB |
| é o binário certo | ELF de 64 bits, máquina x86-64 |
| a glibc cabe | a maior versão exigida pelos `.so` é **2.26**; `python:3.11-slim` é bookworm, glibc **2.36** |
| os números batem | saída idêntica à do `tensorflow.lite` 2.21.0, os 31 neurônios, 12 tensores |

O que **não** está provado, dito com todas as letras: que o wheel *executa* em
Python 3.11. É risco baixo — mesma família de wheels, mesma biblioteca C, ABI
declarada — e é exatamente o que o portão de build vai fechar.

**Alternativa considerada e descartada:** comparar contra a saída do app rodando
em `flutter test`. Descartada porque o `tflite_flutter` depende de `dart:ffi` e a
biblioteca nativa não existe na VM de teste — `carregarOraculoCnn()` devolve `null`
lá de propósito. O `tensorflow.lite` do laboratório é o mesmo runtime C, e está
disponível.

---

## 2026-09-08 — O ingestor precisa aceitar a MESMA partida duas vezes

**Contexto.** O Desafio do Dia (spec 009 do frontend) traz um caso que o log de
partidas nunca teve: uma partida que sobe **antes de terminar**. Quando a linha de
chegada do desafio cai antes do fim natural - *"feche 4 caixas em 2 turnos"* deixa
8 caixas em aberto -, o desafio fecha no objetivo, o XP é creditado ali, e o app
**não interrompe** a partida de quem quiser continuar. Então o envio é em dois
tempos: no objetivo, com `co_status = 'em_andamento'`; depois, o resto.

O dono perguntou, ao revisar o `data-model.md`, se a coluna de status aguentava
isso, e o que aconteceria com uma partida abandonada.

**O que se descobriu.** A coluna aguenta desde a `0006` - `ck_partida_status` já
aceita `('concluida', 'abandonada', 'em_andamento')`. **O defeito estava no
ingestor**, em `api/sincronizacao/repositorio.py`:

```sql
INSERT INTO partida.tb001_partida (…) VALUES (…)
ON CONFLICT (co_evento) DO NOTHING
```

`DO NOTHING`. O segundo envio - o que completaria a partida - seria descartado
**em silêncio**: as jogadas novas subiriam (a `tb002_jogada` é append-only, com
`UNIQUE (id_partida, nu_ordem)`), mas `co_status`, `dh_fim` e os placares
ficariam congelados no primeiro envio. A partida ficaria `em_andamento` para
sempre, sem erro nenhum no log.

**Decisão.** Trocar por `DO UPDATE`, **restrito à transição legítima**:

```sql
ON CONFLICT (co_evento) DO UPDATE SET
       co_status     = EXCLUDED.co_status,
       dh_fim        = EXCLUDED.dh_fim,
       nu_placar_j1  = EXCLUDED.nu_placar_j1,
       nu_placar_j2  = EXCLUDED.nu_placar_j2,
       qt_usos_poder = EXCLUDED.qt_usos_poder
 WHERE partida.tb001_partida.co_status = 'em_andamento'
```

⚠️ **O `WHERE` é a decisão, não um detalhe.** Só uma partida `em_andamento` pode
ser alterada, e ela sai desse estado uma vez só; `concluida` e `abandonada` voltam
a ser imutáveis. Um reenvio antigo - o que a fila de sincronização faz o tempo
todo - não reabre nada nem reescreve um placar fechado.

**Alternativa considerada e descartada:** `DO UPDATE` sem o `WHERE`. Transformaria
a idempotência do `co_evento` em *"o último envio manda"*, que é pior que o defeito
que conserta - qualquer reenvio de fila poderia sobrescrever um resultado final com
um estado intermediário guardado no aparelho.

**E o job de expiração.** A pessoa pode cumprir o objetivo e fechar o app; o
segundo envio nunca vem, e nenhuma regra do aparelho alcança isso (desinstalou,
trocou de aparelho, limpou o armazenamento). Entra um job diário, junto com o de
publicação do desafio:

```sql
UPDATE partida.tb001_partida
   SET co_status = 'abandonada',
       dh_fim    = COALESCE(dh_fim, dh_inicio)
 WHERE co_modo   = 'desafio'
   AND co_status = 'em_andamento'
   AND dh_inicio < now() - INTERVAL '7 days';
```

Sete dias, e não sete horas, porque a fila de sincronização segura eventos
enquanto o aparelho está sem rede - fechar cedo demais marcaria como abandonada
uma partida que esperava Wi-Fi. Se um envio atrasado chegar depois disso, o `WHERE`
do ingestor o recusa, que é o comportamento certo: a partida já foi arquivada.

⛔ **Abandonar não desfaz nada** - a resolução, o XP e a linha do quadro foram
creditados no instante do objetivo e não dependem do desfecho da partida.

**Onde está:** `arena-sagaz-frontend/specs/009-desafio-do-dia/data-model.md`,
§*"O que muda no schema `partida`"*, e os requisitos RF-DES-225 da spec. Nada foi
implementado ainda - a migração do Desafio do Dia não foi escrita.

---

## 2026-09-02 (3) — A reconciliação dos tópicos exclusivos: rastro + faxina

**Contexto.** Horas depois de os tópicos de fuso entrarem, o dono leu a frase
"o fuso sai só do anterior" e reconheceu um padrão que já custou caro:

> *"fiquei preocupado de só excluir o que ficou salvo no aparelho. Já tivemos
> muito problema com isso na assinatura dos termos. (…) O que acontece se houver
> alguma falha na hora de apagar o tópico anterior e cadastrar o novo? Nestas
> situações de erro teremos o usuário em vários tópicos de fuso e ele poderá
> receber várias mensagens repetidas."*

Ele estava certo, e o furo é maior que uma falha isolada. Guardando só "o
anterior": estando em `X` e indo para `Y`, o app inscreve em `Y`, falha ao sair
de `X` e **não grava** (a marca continua `X`). Numa segunda viagem, para `Z`:
inscreve em `Z`, tenta sair de `X`, falha. O aparelho está nos três, e a memória
local só conhece `X` — **o `Y` nunca mais seria limpo**.

**Decisão.** Duas camadas, as duas no app:

1. **Rastro** (`<chave>_rastro`): antes de falar com o FCM, grava-se em disco o
   conjunto de tudo o que *pode* estar assinado. Como é escrito **antes**, uma
   falha no meio não o perde — a próxima sincronização sabe de onde sair. Só
   depois do sucesso completo o conjunto encolhe para um item.
2. **Faxina** (`<chave>_faxina`): a cada **30 dias**, a saída passa pela família
   **inteira**, e não só pelo rastro. É o que cura o que nenhuma memória local
   conhece — tópico assinado por versão anterior do app, aparelho restaurado de
   backup, falha ocorrida antes deste código existir. E ela roda **mesmo quando
   nada mudou**, que é justamente quando serve.

**Sobre "excluir vários tópicos de uma vez", que o dono perguntou.** Não existe:
o SDK do app aceita **um tópico por chamada**, e não há versão em lote. O que
existe é do lado do servidor — `unsubscribe_from_topic(tokens, topic)` do Admin
SDK, que agrupa **até 1000 tokens** para *um* tópico. É lote em token, não em
tópico. Serviria a uma limpeza em massa feita pelo backend (varrendo
`conta.tb005`), e fica registrada aqui como opção **não implementada**: hoje a
reconciliação no aparelho resolve, e ela não depende de o backend conhecer o
token certo.

**Alternativas consideradas.**

1. **Varrer a família inteira em toda sincronização.** São ~40 chamadas de rede
   por troca de fuso (viagem, horário de verão) e ~40 na primeira abertura de
   cada instalação, para sair de tópicos onde nunca se esteve. Rejeitada pelo
   custo, e porque o `subscribe`/`unsubscribe` do cliente tem limite de taxa.
2. **Reconciliar pelo servidor**, com o backend perguntando ao FCM em que
   tópicos um token está. A API de Instance ID que fazia isso foi descontinuada;
   não há como consultar as inscrições de forma suportada.
3. **Não guardar estado e sempre reinscrever.** Não resolve: reinscrever no
   certo não tira do errado.

**⚠️ O que fica valendo para o resto do app.** Este é o segundo caso (depois dos
termos) em que confiar num único valor local produziu um estado que ninguém
consegue corrigir depois. A forma da solução — **rastro escrito antes da ação +
reconciliação periódica que não depende do histórico local** — é a que deve ser
copiada na próxima vez que houver estado espelhado num serviço de terceiro.

---

## 2026-09-02 (2) — Os tópicos de PÚBLICO (idioma · fuso · plataforma) e o envio por combinação

**Contexto.** Poucas horas depois de o broadcast ganhar destino por idioma, o
dono pediu o resto do desenho: tópicos por **fuso** e por **plataforma**, e um
envio que aceite **combinar** tópicos. O objetivo declarado, nas palavras dele:

> *"o que eu quero destes tópicos é que no futuro a gente possa ter um JOB ou
> rotina que consiga fazer um loop por todos os fusos possíveis e vai
> disparando os pushes num horário razoável (ex: 20h no fuso de cada usuário)"*
> — e, sobre a alternativa: *"Teria como fazer a nível de usuário, mas pode cair
> no token do FCM que mudou para alguns usuários."*

**Decisão.** Três famílias de tópico, com regras diferentes de propósito:

| família | exemplo | exclusiva? | de onde sai |
|---|---|---|---|
| idioma | `todos_pt` | sim - entra num, sai dos outros | idioma efetivo do app |
| fuso | `fuso_utc_menos_3` | sim - entra num, sai do **anterior** | offset do aparelho, em minutos |
| plataforma | `plataforma_ios` | **não** | a plataforma do aparelho |

E o envio: `POST /v1/notificacoes/broadcast` aceita `idioma`, `fuso`,
`plataforma` e `topicos` (avulsos). **Nenhum critério** → `todos`, como sempre.
**Um** → aquele tópico (`topic=`). **Dois ou mais** → uma condição
(`condition=`), com `&&`: só recebe quem está em todos.

**Alternativas consideradas.**

1. **Varrer os tokens do banco** (`conta.tb005` tem `co_idioma`, `co_fuso` e
   `nu_offset_minuto`). É a que o dono levantou e descartou pelo motivo certo:
   **token roda**. Um token velho falha no envio e a pessoa não recebe nada;
   quem varre tokens precisa tratar token morto, paginar e limpar a tabela. A
   inscrição em tópico é do FCM, e ele a mantém quando o token da instalação
   muda.
2. **Fuso pelo nome IANA** (`America/Sao_Paulo`), que resolve horário de verão
   sozinho. Descartada como chave de tópico: são ~400 nomes, e o job teria de
   percorrer 400 disparos em vez de ~38. O IANA continua no banco, onde é útil
   para relatório.
3. **`fuso` em horas na API** (`-3`, `+5:30`). Descartada depois de o dono dizer
   que não vai digitar fuso à mão: quem consome é um job, e ele tem o offset em
   **minutos** - que é também como o aparelho o reporta. Sem parser no meio e
   sem a ambiguidade de `5.5` para UTC+5:30.
4. **Nome de tópico `fuso_+3`.** Impossível: o FCM só aceita
   `[a-zA-Z0-9-_.~%]`, e o `+` está fora. Daí `menos`/`mais` por extenso.

**⚠️ O que o teste pegou antes de o job existir.** A janela de tolerância de
`fusos_na_hora_local` nasceu **fechada dos dois lados**, e os oito fusos de meia
hora (Índia, Nepal, Terra Nova, Chatham, Marquesas…) caíam na borda de **duas**
janelas consecutivas - o job entregaria o mesmo push duas vezes para eles, e
para mais ninguém. A janela é semiaberta desde então, e
`test_a_janela_do_job_cobre_o_dia_sem_repetir` percorre as 24 horas conferindo
que cada fuso é atingido **exatamente uma vez**.

**⚠️ O que ainda NÃO existe: o job.** O FCM não agenda nada; ele entrega no
instante da chamada. O backend saiu com as duas peças que a rotina vai pedir -
`OFFSETS_DE_FUSO` (a lista a percorrer) e `fusos_na_hora_local(hora, agora_utc)`
(quem está naquela hora agora, com a hora como **parâmetro**, não como
constante). Falta quem as chame de tempos em tempos.

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

---

## 2026-09-10 — O dia impedido, e o defeito que ele desenterrou

**Contexto.** O dono escolheu a **Opção A** da proposta de registro de visita:
tabela nova em `desafio_dia`, com a chama continuando **derivada**. Ele pediu
dois ajustes, e os dois procediam.

**Decisão 1 — o nome é `tb007_desafio_impedido`.** O rascunho dizia
`tb007_visita`, e ele recusou: *"fica parecendo que registrará a visita de todos
os usuários"*. Eu propus `visita_impedida`; ele preferiu `desafio_impedido`,
porque *"visita impedida me remete ao App ter rejeitado o usuário a abrir a
Home"*. ⚠️ Ele está certo sobre o que o nome sugere: o que foi impedido não foi a
pessoa de entrar — foi **o desafio de chegar até ela**.

**Decisão 2 — os motores vão em `js_motores` JSONB, como LISTA.** O pedido dele
foi guardar *"o que o usuário tinha naquele momento contra o que o backend
exigia"*, notando que os motores são **vários e por jogo**.

⛔ **A forma composta plana não escala, e o projeto já tem a cicatriz.**
`partida.tb001_partida.co_versao_motor` guarda `dart_X|rust_Y` porque uma partida
é de **um** jogo com **dois** motores conhecidos — e mesmo assim
`_versoes_do_motor()` existe só para impedir que duas formas convivam na mesma
coluna. Estendê-la daria `damas:dart_1.4.0|rust_0.4.0;pontinhos:tflite_2.2.0`:
uma mini-linguagem que ninguém valida. ⛔ E coluna por motor faria **jogo novo
exigir migração**, o acoplamento que *"modalidade é DADO, não `enum`"* ensinou a
evitar.

⚠️ **Lista, e não dicionário por jogo**, porque é a mesma forma que uma tabela
filha teria: `jsonb_to_recordset` a abre em linhas e devolve o relacional de
graça. Um `{"damas": {"rust": "0.4.0"}}` põe o jogo na **posição de chave**, e
toda consulta agregada passa a ter de saber os jogos de antemão.

⛔ **Sem `CHECK` de vocabulário em `co_motor`**, e é o lado certo da troca: um
aplicativo **mais novo** que o servidor vai reportar motor que ele nunca ouviu
falar, e recusar perderia o diagnóstico exatamente quando ele é mais
interessante. O `ck003_motores` é guarda **estrutural** (é uma lista?), não de
vocabulário.

**Decisão 3 — migração nova, e não edição da `0019`.** *"Não quero que você
modifique migração já aplicada."* ⚠️ E não há contradição com a §8b: aquela regra
é contra **remendar modelagem defeituosa com `ALTER`**; aqui é uma tabela
**nova**, aditiva por natureza.

### ⚠️ O `CHECK` que era mais estreito que o cabeçalho

O primeiro rascunho da migração aceitava `co_plataforma IN ('android', 'ios')`.
`PLATAFORMAS_VALIDAS` tem **três** valores — `web` continua no vocabulário do
`exigir_cabecalhos`, mesmo tendo deixado de ser alvo do produto. Uma requisição
**válida** viraria erro de banco, e ⛔ **nenhum teste de unidade veria**, porque
eles não passam pelo Postgres. Cadeado escrito no mesmo padrão "contrato ×
realidade" do da união de XP.

### ⛔ O defeito que isto desenterrou: o uid do Firebase não é o `id_usuario`

As rotas de desafio que eu entreguei na T043/T044 passavam `identidade.uid` — a
string do Firebase — para colunas `UUID` que são chave estrangeira de
`conta.tb001_usuario`. **Toda resolução e toda dica teriam estourado no `des`.**

⚠️ **E a suíte passava, antes e depois da correção.** Os testes trocam a
dependência por um fake e nunca veem o tipo real — o defeito era invisível ao CI
por construção, e só apareceria no portão T050.

Quem resolve o id interno é `usuario_autenticado` / `usuario_opcional`
(`api/nucleo/dependencias_conta_nuvem.py`), que busca a linha pelo
`co_identidade_externa`. As quatro chamadas foram corrigidas, e o cadeado novo lê
`ast` — um `"identidade.uid" in fonte` reprovaria a própria docstring que explica
o defeito, que é a **sexta** vez que esse padrão apareceria neste projeto.

### 🔒 E o cadeado do `data-model` estava cego

`test_migracao_bate_com_data_model.py` nomeava `0018` e `0019` **em duas linhas
fixas**. A `0021` criou uma tabela, e o cadeado passou **verde sem nunca tê-la
visto** — o único teste do projeto cuja falha significa *"o que foi aprovado não
é o que vai rodar"* estava aprovando uma tabela que o dono não tinha visto.

Passou a **descobrir** as migrações que criam tabela nesses dois schemas, e há
caso que falha se a lista fixa voltar disfarçada.

---

## 2026-09-10 — O job passa a rodar: a conexão, a ordem das escritas e o editorial

**Contexto.** Todas as peças do BLOCO 2 existiam e eram testadas, e **nenhuma
falava com o Postgres**. `job/__main__.py` era um esqueleto que saía com 2. O
`tasks.md` ia de T038 direto ao portão T050 sem nenhuma tarefa que abrisse
conexão nem que encadeasse os passos — ⛔ o portão era inalcançável por
impossibilidade física, e não por dependência declarada. Daí T049b, T049c e
T049d.

### Decisão 1 — o job tem engine PRÓPRIA (`job/banco.py`)

⛔ **Não se importa `api/nucleo/banco.py`.** Aquele módulo **constrói a engine no
import**, com o pool dimensionado para um servidor web que fica de pé. Importá-lo
faria duas coisas erradas de uma vez: a engine da API nasceria dentro do
container do job só por importar, e a gravação do job passaria a depender da
afinação do **servidor** — mudar o pool da API para aguentar mais gente mudaria,
calado, como o job escreve. É a fronteira RF-DES-011a: os dois se falam **pelo
Postgres**.

⚠️ **E `DATABASE_URL` aqui não tem padrão de fábrica.** O de `api/configuracao.py`
existe por um motivo bom — a app precisa importar sem banco, e os testes fazem
isso o tempo todo. ⛔ Herdá-lo seria caro: um container sem a Variable tentaria
`localhost:5432`, não acharia ninguém, e morreria com `ConnectionRefusedError` —
que no log do Railway **se lê como "o banco caiu"**. A causa real (alguém
esqueceu a Variable no serviço novo) só apareceria depois de investigar um banco
que está perfeitamente de pé. Agora a ausência tem exceção própria, com recado
que diz **onde arrumar**, e vira saída 2.

⚠️ **`dispose()` ao sair não é zelo: é o que permite o processo TERMINAR.** A
política de reinício do serviço é `NEVER`, e sair com 0 é o comportamento
correto; uma engine viva segura conexões e o loop de eventos, e o container
ficaria de pé depois de o trabalho acabar — indistinguível, no painel, de um job
travado.

⚠️ **A normalização da URL está escrita duas vezes**, porque não dá para importar
a da API sem construir a engine dela. Duas cópias de uma regra envelhecem torto,
então há cadeado comparando as duas funções sobre as mesmas entradas. Sem ele, o
esquecimento seria um job escolhendo o driver **síncrono** (`psycopg2`, que nem
está na imagem) e morrendo com `ModuleNotFoundError` no meio da primeira
consulta.

### Decisão 2 — a ordem das escritas é parte da modelagem, não arrumação

    perfil → desafio → régua → medidas → **dia**

**O perfil vem primeiro** porque `fk001_perfil` é uma FK composta e recusa o
desafio sem ele — e recusaria **depois** de o candidato ter sido gerado e medido
pelos três mascotes. A parte cara feita e jogada fora, uma vez por dia. Gravar o
perfil custa milissegundos.

**O dia vem por último**, depois dos feitos de saída: publicar antes abriria uma
janela em que o aplicativo baixaria um desafio **sem medidas**, pagando só o piso
de XP. ⚠️ **Nada daria erro** — o `INSERT` passa, a resposta sai, e a diferença só
apareceria no extrato de quem jogou. É a mesma lição que `reprise.py` já
registrava sobre `SQL_COPIAR_FEITOS`; agora ela é teste.

**Um `commit` só, no fim.** Commitar a cada passo deixaria, se a máquina caísse no
meio, um desafio sem medidas no banco — e a curadoria o aprovaria sem que nada
aparentasse estar errado.

⚠️ **`co_feito` é texto aqui e `nu_feito` no banco**, e a tradução acontece **no
próprio `INSERT`**, por subconsulta na VIEW do catálogo: chave que não existe
devolve `NULL` numa coluna `NOT NULL`, e o banco recusa. Traduzir em Python antes
exigiria reimplementar a mesma recusa — e a primeira versão esquecida dela
gravaria uma medida que nenhum jogo produz, pagando zero para sempre, sem erro
nenhum.

### 🔒 O cadeado que importa: o `INSERT` contra a MIGRAÇÃO

`test_banco_e_repositorio_do_job.py` lê a migração com `ast` e exige que **toda
coluna `NOT NULL` sem `DEFAULT`** de `desafio.tb001_desafio` (são 21) apareça no
`INSERT` do job. ⛔ Uma coluna nova esquecida ali **não daria erro no CI** — nada
do CI passa pelo Postgres —, e o estouro chegaria no Railway, uma vez por dia,
depois da parte cara. Há caso que prova a varredura reprovando.

⚠️ **E o leitor de DDL subiu** de `test_migracao_bate_com_data_model.py` para
`tests/unitarios/leitura_de_migracao.py`. Escrever um segundo seria exatamente a
segunda fonte que aquele módulo existe para evitar — a docstring dele já dizia
que três cadeados o usam e que três implementações acabariam discordando. Agora
são quatro.

### Decisão 3 — RECEITA e EDITORIAL são coisas diferentes

    `tipos_de_desafio.py`  → a RECEITA: como um tipo vira linha de chegada
    `editorial.py`         → com QUE NÚMEROS ele vai ao ar, o que MEDE, que
                             versão EXIGE, qual é o teto do log

⚠️ Trocar 4 caixas por 6 é mudança de **DADO** (SC-027): não toca `.arb`, não toca
código do aplicativo, não muda `co_versao_minima`. Se os números morassem dentro
da receita, mexer na dificuldade **pareceria** mexer na regra que julga. ⛔ E não
cabia em `gravacao.py`, que é sobre a fila.

⛔ **Sem padrão de fábrica também aqui.** Um *"se não souber, use 3"* poria no ar
um desafio cuja dificuldade ninguém escolheu, e ele pareceria igual aos outros na
tela. `TipoSemEditorial` falha alto; há caso garantindo que todo tipo publicável
tem editorial, e o inverso.

⚠️ **`MILISSEGUNDOS_POR_LANCE_DO_GABARITO = 6000` não é chute.** É o número que
reproduz o exemplo **pré-validado** do `data-model.md`: `nu_lances_solucao = 5` →
piso 30000, teto 180000 (a folga de 6× é de `regua_de_tempo`). Há caso travando
isso — sem ele, alguém ajustaria a constante sem saber que existe um documento
aprovado do outro lado.

### Decisão 4 — a convenção de saída, e o que ela protege

    0 → fez · 1 → fez e algo divergiu · 2 → nem começou

⛔ **Dia descoberto sai com 1**, mesmo com todo o resto certo. Era a única coisa
que o esqueleto antigo protegia, e não podia se perder na troca: um job que
*"termina bem"* sem gerar nada é indistinguível, no painel do Railway, de um que
funcionou — e a fila secaria em silêncio até alguém abrir o aplicativo e ver o dia
vazio.

⚠️ **`2` é reservado ao que aconteceu ANTES do trabalho.** Um estouro no quarto
dia, com três publicados, **não** é "nem começou": vira dia descoberto, o log diz
qual foi o erro, e o código é 1. Confundir os dois faria alguém reiniciar o job
achando que nada tinha sido gravado.

⚠️ **`impossiveis` da auditoria também acende a luz.** Uma resolução que a
auditoria não consegue reproduzir é sintoma de **desafio publicado quebrado**, e
não de trapaça — e ele fica no ar enquanto ninguém olhar, com `co_auditoria` em
`pendente`, que na tela de divergências se lê como *"está tudo certo"*.

### Duas peças novas no gerador

**`Candidato.estado_inicial`** — a posição de partida **como objeto do motor**. A
régua e a prova de término precisam jogar de novo a partir dali, e reconstruir a
posição a partir de `js_posicao_inicial` seria uma segunda travessia do mesmo
caminho, capaz de discordar da primeira. ⛔ **Isso não dispensa
`posicao_inicial.conferir()`**, que o `principal()` chama antes de gravar: é ele
que faz `vez_de` e `placar` valerem alguma coisa.

**`bancada(candidato)`** — jogador **e** árbitro, montados para o jogo dele. ⛔ E
os dois nem sempre são o mesmo objeto: nas damas `MotorDamas` faz as duas coisas;
no Pontinhos quem escolhe lance é `JogadorPontinhos` (que não tem `veredito`) e
quem arbitra é `MotorPontinhos`. Deixar isso para o chamador adivinhar plantaria
um `AttributeError` no meio da medição.

---

## 2026-09-10 — O portão T001 reprovou o primeiro build real, e o defeito era dele

**O que aconteceu.** O primeiro build do serviço `job-desafio` no Railway — o
primeiro que de fato usou o `Dockerfile.job` — reprovou no portão de runtime:

```
[X] DIVERGIU. O runtime do job NAO reproduz o do app:
    vetor  1: desvio maximo 0.000001000
    vetor  2: desvio maximo 0.000001000
    vetor  3: desvio maximo 0.000001000
    vetor 10: desvio maximo 0.000001000
```

⚠️ **Os quatro desvios eram idênticos e exatamente 1e-6** — um passo da sexta casa
decimal, nunca dois. E os outros oito vetores bateram **dígito a dígito**: 248
valores exatos.

### O diagnóstico

O portão arredondava a saída a **6 casas** e exigia igualdade **exata**
(`if desvio > 0`). A intenção estava escrita na docstring e estava certa:
absorver a divergência de último bit que dois interpretadores corretos têm por
ordem de soma.

⛔ **Mas arredondar não absorve nada — apenas muda o problema de lugar.** Um
valor a 1e-7 de uma fronteira `x.xxxxxx5` arredonda para lados opostos nas duas
máquinas, e a diferença medida vira um degrau inteiro da última casa.

**Medido**, rodando o runtime de referência (`tensorflow`, no `ia/.venv_tf`) e
guardando a saída crua: **65 dos 372 neurônios — 17% — ficam a menos de 1e-7 de
uma fronteira de arredondamento**, distribuídos por 11 dos 12 vetores.

⚠️ **A comparação anterior era incapaz de passar.** Nem dois runtimes idênticos
em CPUs diferentes a satisfariam — e um portão sem condição de aprovação
alcançável é um portão que se aprende a ignorar.

### A correção

- `inferir()` deixa de arredondar e guarda o valor **cru**;
- a comparação passa a ser por **tolerância absoluta**, `TOLERANCIA = 1e-5`;
- a referência foi **regerada** com valores crus, pelo mesmo `tensorflow` de
  antes (mesma semente, mesmo modelo, mesmos 12 vetores);
- ⚠️ **o pior desvio passa a ser impresso SEMPRE**, inclusive quando aprova. Um
  portão que só diz "sim" ou "não" esconde a deriva: o dia em que esse número
  pular de 1e-7 para 1e-6 é o dia de olhar, mesmo dentro da tolerância.

**Por que 1e-5.** Fica **100× acima** do ruído de último bit observado (~1e-7) e
ao menos **10× abaixo** do que uma implementação de fato diferente produziria —
kernel outro, quantização outra, grafo outro aparecem em 1e-4 ou mais.

### ⛔ Isto NÃO é afrouxar o portão, e a distinção precisa ficar registrada

O próprio projeto tem a regra de que *"alguém 'consertaria' o teste afrouxando a
comparação, que é como uma regra vira decoração"*. A diferença aqui:

- **afrouxar** seria aumentar a tolerância porque o número não passa;
- **consertar** é trocar uma comparação matematicamente impossível de satisfazer
  por uma que tem significado — e o portão saiu mais informativo do que entrou.

⚠️ **A prova de que os runtimes concordam veio do que PASSOU**, e não do que
falhou: 248 valores exatos a 6 casas. Um runtime calculando outro grafo não faz
isso. O plano B de `research.md` §R-03 (`tensorflow-cpu` na imagem) ⛔ **não é
necessário**.

⚠️ **O que ainda não foi verificado**: a máquina do dono não roda o
`ai-edge-litert` (ele publica wheel para cp311, e o `.venv` do backend é 3.14).
A conferência local prova o encanamento — `tensorflow` contra a própria
referência dá desvio **0.000000000** —, e ⛔ **quem prova a concordância entre os
dois runtimes continua sendo o build no Railway**, que é a única execução em
`linux/amd64` que o projeto tem.
