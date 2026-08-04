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
