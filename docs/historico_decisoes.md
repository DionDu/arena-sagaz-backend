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
