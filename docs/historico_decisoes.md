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

## 2026-09-12 — A pescaria do COROAR: 185 moldes reais SOMAM, e não substituem

A segunda pescaria na base de produção terminou (`pescar_moldes_de_partidas.py
--tipo damas_coroar`), no mesmo CSV de 4.090 posições de partidas humanas que já
tinha dado o acervo da captura múltipla.

**Funil:** 2.842 nunca coroaram dentro do teto · 636 com a partida já acabada ·
212 já nasciam coroando (166 na brasileira, 46 na anglo) · **400 passaram a
peneira** · **295 serviram a três ou mais modalidades** (220 servem às quatro).

Distância até o objetivo, nos 295: 3L:63 · 4L:38 · 5L:40 · 6L:43 · 7L:32 ·
8L:40 · 9L:18 · 10L:16 · 11L:5.

### A decisão: somar, não trocar

⛔ **O acervo sintético do coroar NÃO saiu**, e é aqui que este caso se separa
do da captura múltipla, medido três horas antes. Lá a troca foi obrigatória
porque a premissa do acervo estava errada — tabuleiros quase vazios (material
~7) nunca concedem cadeia, e por isso os 29 moldes cabiam **todos** em 3 lances.
⚠️ O coroar nunca teve esse defeito: os 330 moldes publicados foram medidos,
cobrem de 5 a 10 lances e estão no ar desde 11/09. Não havia o que corrigir.

**Entraram os 194 de lance 5 ou depois** — o mesmo corte da T049s, que é do dono
(*"o usuário entra pra resolver um desafio e não joga praticamente nada"*). Os
101 mais curtos ficaram de fora apesar de aprovados, e nada foi recaçado: a
medição já anota a distância, então o corte é uma leitura do diário.

⚠️ **Nove dos 194 já estavam no acervo**, achados pela caçada sintética meses
antes. Não é problema — é o sinal de que as duas fontes olham para o mesmo tipo
de final. Sobraram **185**, e o acervo do coroar foi de 330 para **515**.

### O número que explica os dois casos

| | material dos moldes reais | o que se fez |
|---|---|---|
| captura múltipla | **17,3** (sintéticos: ~7) | trocou o acervo inteiro |
| coroar | **9,7** (sintéticos: equivalente) | somou ao acervo |

A diferença de material era a **causa** do problema na captura múltipla. No
coroar não há diferença — porque não havia problema.

---

## 2026-09-12 — A CADEIA LONGA entra no ar: o primeiro tipo com adversario fixo

**A ideia e do dono**, no mesmo dia: *"deixa o usuario conectar tracos de tal
forma que consiga montar uma cadeia extremamente longa, e depois captura-la, ao
inves do adversario"*. E a medida veio com ela: *"talvez voce possa avaliar o
cumprimento pela quantidade de lances seguidos, ja que ao capturar caixa o
humano/CPU continuam jogando"*.

⚠️ **Essa observacao dispensa geometria.** Quem fecha caixa joga de novo, entao
uma **corrida de lances consecutivos e, literalmente, uma cadeia sendo
capturada** — basta ler a fita. ⛔ Mas a medida conta **caixas**, e nao lances: um
unico traco pode fechar duas.

### O que o tipo obrigou a inventar

1. **Uma medida que le o CAMINHO** (`maior_cadeia_capturada`, feito 12). Todas as
   anteriores se leem no estado final; *"em sequencia"* e uma pergunta sobre a
   ordem dos lances, e duas partidas que terminam na mesma posicao podem ter uma
   cadeia de sete e outra de duas.
2. **Um solucionador que NAO e o Sagaz** (`SOLUCIONADOR_POR_TIPO`). ⛔ O Sagaz e o
   pior gabarito possivel aqui: vencer no Pontinhos e partir o tabuleiro em
   cadeias curtas e controlar a paridade — o oposto do que o desafio pede. O
   **arquiteto** joga com tres regras: fecha se ha caixa; senao marca o traco
   seguro que deixa a maior cadeia; em zugzwang entrega a menor.
3. **Um adversario restrito** (`Publicacao.co_personagens`). ⛔ Contra o Magno o
   desafio e **impossivel**: 0 de 30 posicoes. Ele fica com a Cacau e a Pita.

### As medidas que sustentam cada escolha

    quem resolve        >= 5 caixas   >= 6   >= 7
    Magno (para vencer)     33%         7%     0%
    arquiteto               57%        43%    30%

⚠️ **O placar final e o MESMO nos dois** (9,1 e 9,3 de 12): o desafio nao e ganhar
mais, e jogar diferente — exatamente como o dono o descreveu.

    adversario   >= 5   >= 6
    Cacau         57%    43%
    Pita          67%    57%
    Tex           20%    20%
    Magno          0%     0%

**Publicadas:** `{caixas: 6}` (pior dia 3, solucao 20,6 meios-lances) e
`{caixas: 7}` (pior 3, 21,4). ⛔ **`{caixas: 5}` ficou de fora** apesar de medir
pior 3: o criterio nao e gerar, e **separar** — com cinco, um terco dos dias
seria cumprido por quem jogou normal.

⚠️ **Preparo 4, contra os 14 dos outros tipos de Pontinhos.** Cadeia longa se
**constroi**; com o tabuleiro cheio nao ha o que moldar, e o desafio viraria
*"capture o que ja esta la"*.

### ⛔ E a regra de recusa NAO se aplica aqui — pelo segundo motivo

Com ela ligada, as tres variantes deram **pior dia 0**; sem ela, **pior 3**. A
causa e estrutural: no Pontinhos **alguem tem de abrir** uma cadeia — e o
zugzwang, a regra central do jogo —, e a pergunta *"havia um traco seguro?"*
acusa como erro algo inevitavel. Num tabuleiro de quatro tracos ela acusa
**todo** lance que entrega.

⚠️ **Honestamente: aqui o desafio DEPENDE de um adversario que nao joga
perfeito** — e isso e diferente do caso `acima_do_guloso`, em que o erro entra
nos dois lados da conta e se cancela. Nao esta disfarcado: esta **declarado** em
`co_personagens`, e a frase diz contra quem se joga. O que a regra protege e
outra coisa — o desafio que parece dificil por causa de um erro **pontual e
improvavel**.

**E um defeito que a primeira execucao achou:** o arquiteto estourava com
`min() iterable argument is empty` quando a partida acabava antes do teto de
lances. Ele passou a levantar `ValueError`, o mesmo vocabulario da politica, para
quem chama tratar o fim da partida num lugar so.

---

## 2026-09-12 — A regra de recusa derruba TODAS as variantes do Pontinhos

**Contexto.** Com a regra de recusa por erro do adversario ja no gerador (a que o
dono escreveu: *"se ele entregou caixas e existia um traco livre que entregaria
zero, recusa o desafio"*), o medidor de variantes foi rodado duas vezes sobre as
mesmas onze candidatas — uma com a regra ligada, outra com ela desligada e nada
mais mudado. ⚠️ **Foi a primeira medicao pareada**: ate aqui os numeros do
editorial eram todos anteriores a regra.

    variante                        SEM a regra      COM a regra
    ------------------------------  ---------------  ---------------
    fechar_caixas  {4 caixas, 2 t}  pior 2  ← no ar  pior 0   ⛔
    fechar_caixas  {3 caixas, 2 t}  pior 3  ← no ar  pior 1
    fechar_caixas  {5 caixas, 2 t}  pior 2           pior 0   ⛔
    fechar_caixas  {4 caixas, 3 t}  pior 3  ← no ar  pior 3
    fechar_caixas  {6 caixas, 3 t}  pior 1           pior 0   ⛔
    chegar_placar  {7 caixas}       pior 3  ← no ar  pior 1
    chegar_placar  {6 caixas}       pior 3  ← no ar  pior 1
    chegar_placar  {5 caixas}       pior 3  ← no ar  pior 1
    chegar_placar  {8 caixas}       pior 2           pior 0   ⛔
    chegar_placar  {9 caixas}       pior 2           pior 0   ⛔
    chegar_placar  {acima_do_guloso 1, preparo 14}  pior 3 → pior 0   ⛔
    chegar_placar  {acima_do_guloso 2, preparo 14}  pior 3 → pior 0   ⛔

⛔ **Onze de onze caem, e seis vao a zero** — incluindo `{4 caixas, 2 turnos}`,
que **esta publicada**. Uma variante com pior 0 nao e "mais dificil": e dia
descoberto na fila, e o log so dira *"sem candidato"*.

**Por que.** Ja estava medido em 11/09 e agora tem consequencia: nas partidas
reais, **71%** dos lances que entregam 1 caixa tinham um traco seguro
disponivel. Entregar caixa e comum, e o adversario do desafio nao e o Sagaz — e o
personagem do dia, que pode ser a Cacau, que erra de proposito em 80% dos lances.
A regra, aplicada a **toda** a fita do gabarito, exige do personagem uma
perfeicao que o proprio produto decidiu que ele nao tem.

⚠️ **E no tipo `acima_do_guloso` a regra e redundante, nao so cara.** O alvo
publicado e `G + k`, e `G` e calculado **na mesma posicao, contra o mesmo
adversario**: um erro do personagem levanta os dois lados da conta e se cancela.
E por isso que `guloso.py` ja dizia, desde o primeiro dia, que este desenho
*"dispensa o filtro de erro do adversario"* — a dificuldade deixou de vir do erro
dele e passou a vir da escolha de quem resolve.

**Decisao do dono, 12/09/2026: a regra sai SO no tipo em que o alvo vem da
posicao.** Ela continua valendo em *"feche N caixas"*, onde o erro do personagem
entrega o desafio de graca e nao ha nada do outro lado da conta para compensar.
Sai em `acima_do_guloso`, onde ha. No codigo e uma linha nomeada no gerador
(`objetivo_cancela_o_erro`), e nao um `if` no meio do laco; travada por
`test_acima_do_guloso.py`, **com controle** — o mesmo caso confere que a regra
**continua** sendo consultada no tipo de alvo fixo, senao ele passaria igual se
alguem a tivesse desligado para todo mundo.

**Consequencias, no mesmo dia:**

- ⛔ **`{caixas: 4, turnos: 2}` saiu do editorial.** Entrou em 11/09 com pior dia
  2, medido antes de a regra existir; remedida com ela, deu **0**. ⚠️ **Medicao
  nao e selo vitalicio** — o numero descreve a variante *com o gerador daquele
  dia*, e quem nao remede publica um ⛔ achando que publica um ✅.
- ✅ **`{acima_do_guloso: 1}` entrou**, com pior dia **3**, preparo 14 e teto 34.
- ⚠️ **`{caixas: 5}` e `{caixas: 5, turnos: 3}` estavam no ar e nao estavam na
  lista do medidor.** Entraram: variante publicada fora da lista deixa de ser
  remedida justamente quando o gerador muda.
- ⛔ **E um defeito que so apareceu ao publicar a variante:** `job/__main__.py`
  montava as medidas de saida com `publicacao.parametros`, que nesta variante nem
  tem a chave `caixas` (`KeyError` **depois** de gerar, medir e aprovar o
  candidato). O `Candidato` passa a carregar os `parametros` com que foi montado —
  **sem valor padrao**, para quem esquecer descobrir na construcao — e a traducao
  `acima_do_guloso → caixas` virou funcao unica em `editorial.parametros_efetivos`,
  com uma irma (`parametros_para_conferencia`) para os testes que rodam sem
  posicao nenhuma. ⚠️ Havia duas contas para manter iguais; uma discordancia entre
  elas publicaria a frase pedindo 7 com a nota calibrada para outro alvo.

O medidor tambem passou a aceitar botoes de geracao **por candidata**
(`Candidata`): sem isso a variante seria medida com o preparo 8 da publicacao no
ar e levaria um ⛔ pela medicao errada, e nao pela variante.

⚠️ **E a variante `{caixas: 5}` faltava na lista do medidor** apesar de estar no
ar desde 11/09. Variante publicada fora da lista deixa de ser remedida quando o
gerador muda — que e exatamente quando o numero dela pode ter mudado. Entrou.

---

## 2026-09-12 — A pescaria terminou: 184 moldes REAIS, e a premissa que caiu

**Contexto.** A pescaria de `damas_capturar_multipla` nas partidas humanas do
`prd` rodou ate o fim (interrompida uma vez com Ctrl+C e retomada pelo diario,
como previsto). 4.090 posicoes reais peneiradas, 408 aprovadas, **184 moldes**
com tres ou mais modalidades — 128 deles servem as quatro.

⛔ **E ela derrubou o que este documento afirmava em 11/09.** O comentario do
acervo dizia, com medicao por tras, que *"este tipo resiste a geracao automatica,
e o motivo e o jogo, nao a ferramenta"*: capturar duas em sequencia ou estaria
armado de imediato, ou nunca aconteceria, porque a captura obrigatoria e
justamente o que um Sagaz usa para nao conceder cadeia. **Era a FONTE, e nao o
jogo.**

    sinteticas (11/09)    939 candidatas →  29 moldes, TODOS cumprindo em 3 lances
    reais      (12/09)  4.090 candidatas → 184 moldes,  87 deles em 4 lances ou mais

⚠️ **O que separava os dois acervos era o material**, o mesmo diagnostico que ja
tinha explicado os desafios faceis de coroar: as candidatas sinteticas nasciam de
tabuleiros quase vazios (material ~7), onde o adversario tem espaco de sobra para
recusar; as posicoes reais tem material **17,3**, e ai a cadeia se forma. A
distancia ate o objetivo deixou de ser uma coluna so:

    3 lances: 97 · 4: 35 · 5: 30 · 6: 9 · 7: 13

**Decisao.** O acervo sintetico de 29 moldes **saiu inteiro** e foi substituido
pelos 184 pescados. ⚠️ **Substituido, e nao somado:** o gerador sorteia entre os
moldes, entao manter os 29 antigos reintroduziria, em ~14% das publicacoes,
exatamente o desafio banal que a pescaria existe para acabar.

⚠️ **E isso reabriu a §8j do `DECISOES-do-dono.md`**, decidida quando todo molde
cumpria no lance 3 e nao havia escolha a fazer. **O dono decidiu em 12/09/2026:
so os 87 moldes de 4 lances ou mais entram.** A captura multipla deixa de ser *"o
tipo rapido"* da fila e passa a durar como o coroar.

⚠️ **Os 97 curtos nao foram apagados** — saem do diario da pescaria com um
comando, e o comentario do acervo diz qual. ⛔ Mas nao voltam por descuido: um
molde curto no meio do acervo publicaria, de vez em quando, exatamente o desafio
de um toque que a decisao acabou de recusar.

⚠️ **A pescaria de `damas_coroar` ainda nao rodou** (~4,5 h estimadas). Ate la,
aquele acervo continua sintetico — e e o unico dos dois que ainda esta.

---

## 2026-09-11 — A PARIDADE DE CADEIAS LONGAS e o eixo certo do Pontinhos

⛔ **Duas recomendacoes minhas foram derrubadas pelo dono no mesmo dia, e as duas
pelo mesmo motivo: eu estava contando caixas onde o jogo conta CONTROLE.**

**A primeira.** Propus subir o limiar da recusa de 1 para 3 caixas, com o
argumento de que ceder 2 caixas e o proprio double-cross e seria punido. O dono:
*"pra mim isso nao faz sentido"*. **A segunda**, logo depois: afirmei que o
double-cross acontece sempre em zugzwang, e portanto a regra nunca dispararia
sobre ele. ⚠️ **Medido nas partidas reais do `prd` (80 partidas), e falso:**

    entregou | zugzwang (forcado) | tinha saida | % com saida
    ---------+--------------------+-------------+------------
       1     |         44         |     106     |     71%
       2     |         69         |      53     |     43%
       3     |         17         |      10     |     37%
       6+    |         35         |       4     |     10%

⚠️ **Ceder 1 ou 2 caixas COM alternativa segura acontece 159 vezes** — e a
contagem de caixas nao diz se aquilo foi sacrificio de proposito ou burrice. ⛔
**Nenhum limiar separa as duas coisas**, porque a diferenca nao esta no tamanho
do presente: esta em quem fica no controle depois dele.

### O que o dono disse, e que e a teoria do jogo

> *"O jogador que controla a paridade das cadeias longas e quem vence o jogo. (…)
> O jogador inexperiente vai capturar as cadeias longas ate o final e sera
> obrigado a abrir a proxima cadeia longa para a CPU. Ja o jogador experiente vai
> fazer o double dealing (…) ou capturar a cadeia longa ate faltarem somente 2
> caixas (…) e deixa estas 2 ultimas para o adversario, que sera obrigado a
> captura-las e abrir a cadeia longa."*

✅ **E a medida ja existe, e ja esta no backend.**
`analisador_estrutural_pontinhos.extrair_stats_cadeias(M)` devolve
`(qtd_cadeias_longas, total_de_caixas, maior_cadeia)`, e chega aqui pelo
**espelho do laboratorio** que `motores/pontinhos/motor_pontinhos.py` ja poe no
`sys.path` — nao ha nada para portar.

⛔ **A armadilha, custou uma medicao inteira:** `extrair_stats_cadeias` espera a
matriz no formato do **dataset** (`{0,1,8,9}`), e nao a matriz crua da partida
(que tem `-1`). Passando a crua ela devolve **zero cadeias em toda posicao**, sem
erro nenhum — a primeira medicao "provou" que nao havia cadeia longa em lugar
algum. A conversao e `motor_pontinhos.partida_para_dataset(matriz)`.

### Ha material de sobra (80 partidas reais do `prd`)

    posicoes de zugzwang, por cadeias longas no tabuleiro:
        0 cadeias:  30
        1 cadeia : 135
        2 cadeias:  49      <- e aqui que a paridade decide

    **30 das 80 partidas (38%)** chegam a um zugzwang com 2+ cadeias longas.
    A maior cadeia dessas posicoes chega a **10 caixas**.

Projetado nas 4.316 partidas do acervo: ~1.600 partidas com o momento de
paridade.

### ⚠️ E a forma de desafio que o dono desenhou dispensa o filtro

> *"1. Entregamos um estado com caixas a capturar. Se ele capturar de forma
> gulosa ele fecha o jogo com 5 caixas. 2. Se capturar usando double dealing ele
> fecha com 7. 3. O desafio seria: capture 7 ou mais caixas."*

⚠️ **O objetivo passa a excluir a solucao ingenua por construcao.** Nao se
pergunta mais "o adversario errou?", porque a dificuldade deixa de depender do
adversario: ela vem da escolha de **quem resolve**. Duas simulacoes dao o numero:
guloso → `G`; com controle de paridade → `D`; publica-se *"capture `D` ou mais"*
**se, e somente se, `D > G`**.

⛔ **E isso torna o desafio auto-verificavel**: um desafio em que `D == G` nao tem
graça e nao e publicado, sem ninguem precisar opinar sobre dificuldade.

### ✅ MEDIDO em 60 posicoes reais (o dono decidiu: `D` sai do Magno)

O guloso e o **proprio Magno com uma unica diferenca**: quando ha caixa
disponivel, ele a pega. ⚠️ Assim a comparacao isola exatamente a decisao de
**recusar**, em vez de misturar "jogou pior em tudo" com "nao sabe fazer double
dealing". E o adversario e o Magno nos dois casos — se ele mudasse junto, a
diferenca nao seria atribuivel a nada.

    com D > G (viram desafio): 16 de 60  (27%)

    D - G:  +0: 44 | +1: 5 | +2: 6 | +3: 4 | +5: 1

⚠️ **Um dos exemplos saiu `(guloso 5, magno 7)`** — exatamente o numero que o dono
usou ao descrever a ideia, sem ter visto o dado. Projetado nas 87.945 posicoes do
acervo real: **~23 mil** posicoes candidatas.

⛔ **Duas correcoes de desenho que a medicao revelou:**

  1. **`D` e `G` tem de ser calculados contra o PERSONAGEM DO DIA**, e nao contra
     o Magno. O adversario publicado pode ser a Cacau (epsilon 0,80); um `D`
     medido contra o Magno descreveria outra partida, e o numero publicado nao
     valeria para o desafio que foi ao ar.
  2. **`D` ser alcancavel pelo Magno nao quer dizer alcancavel por gente.** Quem
     responde isso e a regua (`job/regua.py`), medindo os mascotes — e aqui ela
     finalmente tem um trabalho de verdade, em vez de confirmar o obvio.

---

## 2026-09-11 — A pesca medida no acervo do `prd`, e o pescador do Pontinhos

O dono exportou do `prd` os lances de damas (4.519 posicoes, contra 2.034 do
`des`) e pediu: *"para os 2 jogos, se conseguirmos pescar os desafios da base de
producao sera o melhor dos mundos, pois dispensaria mecanismos complexos de
geracao de desafios."*

### ✅ Damas: medido, e funciona

Calibracao em amostras de 48 posicoes sorteadas do acervo real (4.090 unicas
depois do espelho), com 14 processos:

    tipo                     | rendimento | material medio | distancias
    -------------------------+------------+----------------+--------------
    damas_capturar_multipla  | 4 de 48    | 16,8 pecas     | 3, 4, 4, 7
    damas_coroar             | 3 de 48    | 10,0 pecas     | 3, 7, 8

⚠️ **Compare com o acervo sorteado:** 7,0 e 6,0 pecas, sempre. E o de captura
tinha **zero** moldes com distancia ≥5 — a pesca achou um de 7 na primeira
amostra de 48.

**Projecao para o acervo inteiro:** ~340 moldes de captura e ~208 de coroar.
⛔ **Custo: ~11 h de CPU** (peneira + medicao nas quatro modalidades), que e
comando do dono, nao do assistente.

### ⚠️ Pontinhos: a pesca e conversao, mas NAO conserta o que o dono relatou

A posicao do Pontinhos **e o conjunto de tracos marcados**, e marcar um traco
nunca desmarca outro. Logo **todo prefixo de uma partida real e uma posicao
real** — sem motor, sem busca, sem custo. `scripts/pescar_posicoes_pontinhos.py`
converte o CSV de lances no NPZ que `posicoes_de_autoplay_pontinhos.carregar` ja
le. Provado com os dados do `des`: 167 partidas, **4.251 posicoes distintas**, bem
distribuidas em todas as fases, e ⚠️ **as 167 reproduziram sem um unico traco
repetido** — o log e integro.

⛔ **Mas trocar a fonte nao resolve o relato** *"os desafios dos pontinhos sao
quase sempre baseados numa jogada errada do personagem"*. Quem seleciona e o
gerador, pela pergunta *"o objetivo cai aqui?"*; como o objetivo e *"feche N
caixas"* e fechar cadeia **exige que o adversario abra**, a selecao continua
concentrada no instante seguinte a uma abertura, venha a posicao de onde vier.
⚠️ O problema esta no **objetivo**, nao na fonte.

⚠️ **E o acervo de autoplay tem 897 mil posicoes** contra as ~4 mil por
167 partidas reais: no Pontinhos a pesca troca variedade por representatividade,
e essa troca e uma decisao de produto, nao uma correcao de defeito.

### ⛔ O cadeado do `consultar_des.py` recusava portugues

A consulta que pesca lances do Pontinhos foi recusada pelo proprio script:
*"isto nao e uma consulta de leitura: **do**"*. A palavra vinha do comentario
*"os lances **do** Jogo dos Pontinhos"*, e `DO` e palavra-chave do Postgres.

⚠️ **Todo comentario em portugues tem "do", "da" ou "com"**, e a diretriz do
projeto manda comentar tudo — o cadeado recusaria praticamente qualquer SQL
comentado. `sem_comentarios()` agora tira `--` e `/* */` antes da conferencia.
⚠️ O preco, dito em voz alta no teste: `-- DELETE` deixa de ser recusado. Esta
certo — e comentario, o banco nao o executa, e **quem defende de verdade e a
transacao `READ ONLY`**.

---

## 2026-09-11 — Por que os desafios de damas sao faceis: o MATERIAL

**O relato.** *"Os desafios de coroar damas tem muitos lances agora, no entanto
estao absurdamente faceis. E basicamente so seguir em linha reta com a peca ate o
final, nao tem desafio algum."*

⛔ **Ele estava certo, e a causa nao era a distancia — era o material.** Medida
tirada do `des`, comparando o que o acervo produz com o que acontece em partida:

    posicao de...                   | nos MOLDES sorteados | em PARTIDAS REAIS
    --------------------------------+----------------------+------------------
    coroar                          |  6,0 pecas (SEMPRE)  | 12,3 pecas
    captura de 3+ pecas             |  7,0 pecas (SEMPRE)  | 17,6 pecas

⚠️ **O "sempre" e literal:** os 330 moldes de `damas_coroar` tem exatamente 3
brancas e 3 pretas, e os 29 de `damas_capturar_multipla`, 3 e 4. Nao e tendencia
estatistica — e parametro escrito a mao em `cacar_moldes_damas`.

⛔ **E ha um defeito pior dentro dele.** `candidatas_para_coroar` sorteia a ponta
de lanca em 5..12 e as pretas em **13..24**. As brancas coroam em 1..4 e andam
para numeros menores; as pretas andam para numeros maiores. ⚠️ **As pretas
nasciam ATRAS da peca que ia coroar, em todos os 330 moldes** — nao havia como
interceptar. O comentario da funcao dizia *"tres pretas no miolo, que e onde elas
atrapalham sem fechar o caminho"*; elas nao atrapalhavam nada.

### ⚠️ A licao, que ja custou duas correcoes erradas

Foram tres criterios tentados, e os dois primeiros mediam a coisa errada:

  1. **distancia ate o objetivo** — mede COMPRIMENTO. Produziu desafios longos e
     vazios, que foi o relato acima;
  2. **material minimo** — mede POPULACAO. E so uma hipotese de que ha oposicao;
  3. ✅ **a regua** (`job/regua.py`) — mede o que os mascotes conseguem, que e a
     unica definicao operacional de dificuldade que o projeto tem. ⚠️ E ela ja
     vinha avisando: os desafios de coroar saiam com *"banal por 0,07"* no log, e
     a selecao de moldes nao a consultava.

### A pesca em partidas reais (ideia do dono, medida no mesmo dia)

`scripts/pescar_moldes_de_partidas.py` troca **so a fonte** das candidatas: em vez
de sortear, le posicoes que aconteceram. ⚠️ **As damas ja gravam a posicao** —
`jogo_damas.tb002_jogada.co_fen_antes` guarda a FEN antes de cada lance —, entao
nao ha o que reconstruir. A peneira e a medicao sao as mesmas, importadas de
`cacar_moldes_damas`, e nao copiadas.

**O que a sondagem mediu** (37 partidas de damas no `des` → 1.777 posicoes unicas
depois do espelho, 1.421 com 10+ pecas e uma pedra a ate 6 fileiras):

  · **rendimento: 1 em 36** (~2,8%), a ~2,5 s de parede por posicao com 12 processos;
  · a unica aprovada tem **14 pecas** e distancia **10 lances** — exatamente o
    perfil que faltava;
  · ⚠️ **o motivo das 34 reprovas foi `nao_cumpriu_no_teto`**: numa posicao real
    com material, o Sagaz jogando os dois lados **nao consegue** coroar em doze
    lances. Isso e a confirmacao de que a posicao tem oposicao — e ao mesmo tempo
    o aviso de que *coroar* e um objetivo caro em meio de jogo.

⛔ **Consequencia de volume:** ~1 molde por partida real. Um acervo de 300 moldes
pede ~300 partidas de damas, e o `prd` e que as tem. A extracao e do dono (⛔ o
assistente nao conecta no `prd`).

### ⚠️ E o Pontinhos: a cadeia entregue NAO e anomalia do gerador

O dono estranhou um lance do adversario que entregava 6 caixas. Medida das
cadeias reais nas 167 partidas do `des` (ilhas de lances consecutivos do mesmo
jogador):

    1 caixa: 318 | 2: 258 | 3: 68 | 4: 92 | 5: 24 | 6: 38 | 7: 15 | 8: 7 | 9: 3 | 10: 4 | 11: 2

**253 turnos fecharam 3 ou mais caixas; 69 fecharam 6 ou mais.** Entregar uma
cadeia e como o Jogo dos Pontinhos termina — alguem e obrigado a abrir. ⚠️ O que
resta de vies nao e a cadeia existir: e o gerador **selecionar** posicoes por
"existe cadeia grande aqui", o que concentra a fila no instante imediatamente
posterior a abertura. Pescar de partidas reais ataca justamente isso, porque a
posicao entra por ter acontecido, e nao por ser conveniente.

---

## 2026-09-11 — A varredura por funcoes sem teste, e o que ela achou

**De onde veio.** No mesmo dia, `regua.tentativa_com_motor` revelou um defeito de
meses: aplicava o nivel do mascote medido aos **dois lados** do tabuleiro, e a
regua media *"Cacau contra Cacau"*. ⛔ **O comentario no topo do modulo descrevia
o comportamento certo** — so o codigo nunca o cumpriu.

⚠️ **O que deixou isso durar foi a ausencia de teste:** a funcao nao era
mencionada em lugar nenhum da suite. Entao a pergunta natural virou uma
varredura: *quais outras funcoes publicas nao aparecem uma unica vez nos
testes?*

**Nove.** Duas de infraestrutura (`banco.py`), uma criada no mesmo dia
(`regua.taxa_media`, ja coberta indiretamente), e seis de dominio.

### (a) `estado_terminal.provar_termino` ganhou cadeado

⚠️ Ela guarda uma garantia declarada em documento — *"toda partida de desafio
chega a estado terminal, provado **na geracao**"* (`CLAUDE.md`, Bloco 1c) — e
nao tinha um caso sequer. Quatro entraram, todos com dubles (⛔ sem motor de
verdade, para caberem na suite):

  · partida que ja nasce terminada;
  · ⚠️ **a contagem e de lances JOGADOS**, e nao de perguntas ao arbitro — o laco
    pergunta antes de cada lance, entao a quarta pergunta responde "acabou" numa
    partida de **tres** lances. Um erro de um aqui nao quebraria nada
    visivelmente;
  · ⛔ partida que nao acaba dentro do teto **reprova** — e o caso que a funcao
    existe para pegar;
  · ⚠️ motor sem lance legal **pergunta ao arbitro** em vez de supor: se o motor
    nao tem lance e o arbitro diz que a partida segue, isso e contradicao, e a
    prova nao pode passar por cima dela.

### (b) ⛔ `gabarito.lance_chave_padrao` era CODIGO MORTO — e foi removida

Ninguem a chamava: o gerador ja recebe o numero pronto do julgamento
(`julgamento.nu_lance_cumpre_desafio or numero`).

⚠️ **A prova de que nunca foi exercitada estava nela mesma:** a docstring
declarava um parametro `(quantos) -> Julgamento` e o corpo chamava a funcao **sem
argumento nenhum**. Uma unica execucao teria levantado `TypeError` — e foi
exatamente o que aconteceu ao escrever o primeiro teste dela.

⛔ **Codigo morto com docstring divergente e pior que codigo morto:** quem
precisasse do lance chave um dia leria a docstring, escreveria o chamador
conforme ela, e descobriria a divergencia em producao. A nota ficou no lugar da
funcao — quem a procurar daqui a um ano acha o motivo, e nao um vazio.

⚠️ **As outras quatro ficaram sem cadeado, e isso e escolha:** `versao_do_motor_de`
e `modalidades_declaradas` sao leitura de constante, `tracos_da_mascara` ja e
exercitada de lado pelos testes do acervo de autoplay, e `reprise.linha_para_copia`
so tem o que provar quando houver desafio antigo com tentativas reais — hoje ela
devolveria vazio em qualquer teste, que e o que ela ja faz em producao.

---

## 2026-09-11 — A cacada de 1.000, e o acervo de moldes refeito por DISTANCIA

**1.000 candidatas por tipo, 14 processos, ~1 h de maquina.** E a primeira
cacada grande do projeto, e ela so coube numa noite por causa da paralelizacao
da mesma tarde.

### `damas_coroar`: o problema do dono estava no acervo, e acabou

> *"Todos sao resolviveis em 3 lances no total. O usuario entra pra resolver um
> desafio e nao joga praticamente nada. Consegue resolve-los em uns 10 segundos
> e sai do App?"*

Ele tinha razao, e a causa nao era o gerador: **os moldes em uso tinham sido
cacados com o alvo *"objetivo no lance 3"*** (`LANCE_MINIMO`), e a fila mostrava
exatamente o que se pediu a cacada.

Dos 999 candidatos: 549 passaram a peneira (335 s), 540 serviram a tres ou mais
modalidades. A distribuicao da **distancia ate o objetivo**:

    lance  3 ->  90     lance  7 ->  41
    lance  4 -> 120     lance  8 ->  69
    lance  5 ->  83     lance  9 ->   6
    lance  6 -> 127     lance 10 ->   4

✅ **Ficaram os 330 com objetivo no lance 5 ou depois** — o dobro do acervo
anterior **inteiro** (161). ⛔ Os 210 mais curtos foram descartados **apesar de
aprovados pela cacada**: eles publicariam o desafio de dez segundos de novo.

⚠️ **E nao se recacou nada para isso.** A cacada ja anota a distancia molde a
molde; quem corta e `scripts/selecionar_moldes_damas.py`, em segundos. ⚠️ **A
separacao importa:** medir custa horas e o criterio pode mudar — misturar os dois
faria toda mudanca de criterio custar outra noite.

**Medido depois da troca**, gerando quatro dias reais: solucoes de **9, 3, 5 e 9**
meios-lances, contra **3, 3, 3** antes. A media dobrou.

### `damas_capturar_multipla`: agora esta medido que nao tem jeito

O funil das 939 candidatas conta a historia inteira:

    621  nunca cumpriram dentro do teto
    200  ja nasciam com a cadeia armada (objetivo no lance 1)
     51  partida acabada
     67  passaram a peneira
     29  serviram a tres ou mais modalidades

⛔ **Dos 29, vinte e oito cumprem no lance 3 e um no lance 4. Zero com distancia
5 ou mais** — contra 330 no `damas_coroar`, na mesma cacada e com o mesmo
esforco.

⚠️ **Nao e falta de cacada, e o jogo.** Capturar duas em sequencia ou esta
disponivel de imediato, ou nao acontece: a captura obrigatoria das damas e
justamente o que o adversario usa para nao conceder. As tres janelas medidas
(`lances` 2, 3 e 4) deram **3,0 meios-lances** em todas, com ate o tempo
identico.

⏳ **Fica uma decisao para o dono, e ela nao e tecnica:** aceitar que este e o
tipo rapido da fila, ou tira-lo do rodizio. Enquanto nao decidir, ele publica —
com 29 moldes, tres vezes o acervo anterior.

### ⛔ E o job nao pode morrer por causa de uma MENSAGEM

Ao medir o acervo novo, um `print` de descarte derrubou o processo:

    UnicodeEncodeError: 'charmap' codec can't encode characters

⚠️ O console do Windows e cp1252, e o log deste job e cheio de `⚠️` e `⛔`. No
Railway nao ha problema (stdout e UTF-8), mas **localmente o primeiro emoji mata
o processo — no meio do trabalho**, depois de gerar e medir.

`job/__init__.py` passou a reconfigurar `stdout`/`stderr` para UTF-8 com
`errors="replace"`. ⚠️ **Ali, e nao em cada ponto de entrada**: o job e rodado de
quatro lugares (o `-m job`, os dois scripts, os testes), e uma chamada em cada um
envelheceria torto — bastaria um script novo esquecer.

---

## 2026-09-11 — A cacada de moldes passa a usar todos os nucleos

**A pergunta do dono:** *"Para recacar moldes com alvo de distancia maior essas
horas nao seriam reduzidas se seu script passar a usar 14 nucleos do meu Ryzen
5700X?"*

Seriam. A cacada e um caso de livro: cada candidata e independente de todas as
outras, nao ha estado compartilhado e o trabalho e 100% CPU.

⛔ **`threading` nao serve** — o motor e Python puro, e o GIL faria catorze
threads se revezarem num nucleo so; o programa ficaria **mais lento** que a
versao sequencial. E `multiprocessing`.

### ⚠️ O que quase passou despercebido: o teto de TEMPO invalidaria a medicao

O orcamento do motor para **no que vier primeiro** — nos ou segundos. Medido
antes de paralelizar: **~0,66 s por lance**, contra um teto de 2,0 s. Numa
maquina ociosa o teto de tempo nunca mordia, e o criterio efetivo era o numero
de nos.

⛔ **Em paralelo isso deixa de valer.** Catorze processos disputando oito nucleos
fisicos deixam cada busca mais lenta em tempo de **parede**, sem mudar o numero
de nos. Com o teto antigo, a busca pararia mais cedo — e ⛔ **o resultado da
cacada passaria a depender do quanto a maquina estava ocupada**. Uma "medicao"
que muda conforme o dono abre o navegador nao e medicao.

**Decisao: o teto de tempo sobe (30 s na peneira, 60 s na medicao) e passa a ser
rede de seguranca**, nunca criterio. Quem manda e o numero de nos, que e
identico em qualquer maquina e com qualquer carga.

⚠️ **Isto tambem melhora a versao sequencial**, e de graca: os poucos lances
caros que estouravam os 2 s agora terminam a busca.

### Detalhes que o Windows impoe

  · ⚠️ **as funcoes de trabalho sao de MODULO**, e nao closures: o `spawn` do
    Windows re-importa o arquivo em cada processo e localiza a funcao pelo nome.
    Uma closure daria `PicklingError` depois de o Pool ja ter aberto;
  · ⚠️ **o `if __name__ == "__main__"` deixa de ser estilo**: sem ele, cada
    processo filho re-executaria a cacada inteira ao importar o modulo;
  · ⚠️ **os motivos de descarte voltam no RETORNO** de cada tarefa. Um `Counter`
    global seria incrementado em catorze copias, e nenhuma delas chegaria ao pai.

### O padrao

`--processos N`, com padrao `cpu_count() - 2`. ⚠️ **Dois de fora de proposito**:
o dono roda isto na maquina que ele usa, e uma cacada que trava o computador e
uma cacada que ninguem deixa terminar. `--processos 1` roda em sequencia, e e o
modo de depurar — o rastro de uma excecao aparece inteiro.

---

## 2026-09-11 (madrugada) — O espelho, e a correcao de uma correcao

**Contexto.** A correcao da vespera (*"a variacao passa a ser par, para a pessoa
ser o jogador 1"*) estava certa no diagnostico e **errada na saida**. A execucao
seguinte mostrou o preco, no mesmo log:

  · ⛔ **2026-09-11 ficou SEM DESAFIO.** `damas_capturar_multipla` descartou nove
    posicoes seguidas por *"o objetivo cai no lance 1"*, nao sobrou candidato, e
    a reprise tambem nao tinha o que copiar - o pior caso operacional previsto;
  · ⛔ **as damas viraram desafios de dois lances.** As tres linhas de damas da
    fila sairam com `nu_lances_solucao = 3` (tres **meios**-lances). O dono: *"o
    usuario entra pra resolver um desafio e nao joga praticamente nada. Consegue
    resolve-los em uns 10 segundos e sai do App?"*.

⚠️ **A causa das duas coisas e a mesma: o preparo CONSOME a distancia ate o
objetivo.** Os moldes foram cacados como posicoes a ~3 lances do alvo; gastar
dois deles em variacao deixa o desafio a um lance - ou a zero, e ai ele e
descartado pelo cadeado de trivialidade.

### A saida: variar UM lance e ESPELHAR

`job/espelho_de_damas.py` gira o tabuleiro 180 graus e troca as cores. A posicao
resultante e **a mesma tarefa vista do outro lado**, com o lado a jogar tambem
trocado - entao um lance de variacao (que preserva a distancia) seguido do
espelho devolve uma posicao com as **brancas** a jogar, que e o jogador 1.

⚠️ **Isto so vale porque as damas sao simetricas sob essa transformacao**, e isso
e afirmacao sobre o **motor**, nao sobre a aritmetica: o cadeado pergunta ao
motor o numero de lances legais dos dois lados do espelho, nas quatro
modalidades, sobre os 170 moldes. ⛔ Num jogo com regras assimetricas por cor o
espelho estaria errado - por isso o modulo leva o nome do jogo.

⚠️ **A casa `n` vira `33 - n`**, e a casa escura continua escura: a rotacao leva
`(l, c)` para `(7-l, 7-c)`, e `14 - (l+c)` tem a mesma paridade que `l + c`.

⛔ **O `K` viaja junto.** Uma dama espelhada que virasse pedra daria uma posicao
legal e silenciosamente diferente - a pior especie de defeito desta feature.

### O que continua em aberto: as damas ainda sao curtas

⚠️ **O espelho nao conserta isso, e nao deveria.** Com um lance de variacao as
solucoes voltaram a 3 e 5 meios-lances - melhor, mas ainda curto para o gosto do
dono. A razao e anterior ao preparo: **os moldes foram cacados com o alvo
*"objetivo no lance 3"***, entao a fila reflete exatamente o que se pediu a
cacada.

Os dois caminhos, ambos medicao longa e portanto **comando do dono**:

  1. medir a variante `{damas: 2}` (coroar **duas** damas), ja escrita em
     `A_MEDIR` de `scripts/medir_variantes_do_editorial.py` - e literalmente o
     que o dono sugeriu (*"se fosse ao menos coroar 2 damas"*);
  2. cacar moldes com alvo de distancia maior.

## 2026-09-11 (madrugada) — O painel ganhou o id, rotulos legiveis e o erro de proposito

Tres pedidos do dono na primeira curadoria de verdade, e o terceiro veio de uma
pergunta que valia mais que o pedido.

### (a) O `id_desafio` no cartao

> *"Traga o id_desafio para o Painel para que possamos discutir os desafios sem
> que eu precise printar telas."*

Inteiro, em monospace e com `user-select: all`. ⛔ Encurtar para oito caracteres
obrigaria a voltar ao banco para saber de qual linha se fala - o trabalho que ele
esta tentando evitar.

### (b) Os rotulos das arestas se sobrepunham

O rotulo de uma vertical, deitado, tem a largura de uma casa inteira e encosta no
da horizontal vizinha. Agora ele vai **de pe** (`rotate(-90)`), na mesma direcao
do traco que nomeia, e o tabuleiro da fita e maior que o da miniatura **porque
leva texto**.

### (c) ⚠️ O lance que a CPU erra de proposito agora aparece

> *"Este desafio depende do Tex fazer uma jogada muito ruim e ate mesmo improvavel
> (...) Nao entra na minha cabeca como pode ter feito esta escolha? Sera que este
> lance caiu no epsilon que ele joga errado?"*

Caiu: o Tex tem `epsilon = 0,14` no contrato de dificuldade. A cada jogada
tatica ele sorteia, e em 14% das vezes joga **fora** do melhor lance.

⚠️ **A informacao ja existia e era jogada fora.** `politica.py` devolve um
`co_acao` por lance (`cnn_epsilon_aleatorio` quando errou de proposito), e o
gerador guardava so a notacao. Agora o `co_acao` entra no gabarito e o painel
marca o quadro.

⛔ **E a pergunta seguinte dele e a boa:** *"e se nao cair neste epsilon na
partida real?"*. Com a semente publicada, cai — mesmo nivel e mesma semente
escolhem o mesmo lance. Mas isso vale enquanto a pessoa seguir o gabarito; por
outro caminho o sorteio encontra outra posicao. ⚠️ **Quem responde se o desafio
depende do erro e a REGUA**, que mede 20 execucoes com sorteios diferentes - e e
por isso que a marca no painel nao decide nada sozinha: ela diz onde olhar.

### (d) E o assistente passou a consultar o banco sozinho

> *"Estou cansado de ficar consultando o banco e trazendo os dados das tabelas
> para voce."*

`scripts/consultar_des.py` le `DATABASE_URL_DES` de
`ferramentas/debug-bancos/ambientes.env` (fora do Git, ja e o catalogo dos dois
bancos) e roda a consulta numa transacao `READ ONLY`. ⛔ Tres travas: so a URL do
`des`, a transacao somente-leitura imposta **pelo banco**, e a conferencia de
palavra - que e a mais fraca das tres e existe para dar a mensagem boa, nao para
ser a defesa.

---

## 2026-09-11 (noite) — Tres perguntas do dono sobre o painel, e duas eram defeitos

O dono curou a primeira fila de verdade e voltou com tres observacoes. Duas
viraram correcao; a terceira virou descarte.

### (a) ⛔ Nas damas a pessoa estava jogando de jogador 2

> *"No App eu sou sempre as pecas e arestas azuis. Nas damas o humano sempre joga
> com as pecas iniciando na parte de baixo do tabuleiro, nao no topo. No painel
> isso aparece tudo invertido."*

⚠️ **Nao era o painel.** Todo desafio de damas saía com `vez_de: -1` - a pessoa
como **jogador 2**, vermelho, com as pecas no topo. O `CLAUDE.md` diz o
contrario com todas as letras: *"jogador 1 = AZUL e jogador 2 = VERMELHO.
Sempre. (...) No modo contra a CPU, o humano e o Jogador 1"*.

**A causa era aritmetica.** O molde tem as brancas a jogar, e os moldes foram
cacados para que **as brancas** cumpram o objetivo; sobre ele o gerador jogava
**um** lance de variacao, e um lance troca o lado. Numero impar de lances =
solucionador trocado.

**Decisao: a variacao passa a ser par** (`2` com preparo 8). ⛔ Zero foi recusado:
sem variacao, todo desafio tirado do mesmo molde seria a mesma posicao.

⚠️ **O Pontinhos ja estava certo** (`vez_de: 1` em toda linha), e foi isso que
escondeu o defeito - metade da fila parecia bem.

### (b) ⛔ O gabarito nao se reproduzia, e a regua media outra partida

> *"E garantido que o adversario fara os lances que estao postos no gabarito caso
> o humano jogue as mesmas jogadas do gabarito no seu turno?"*

A resposta, antes desta correcao, era **nao** - e por dois motivos independentes:

  · ⛔ **o gabarito era Sagaz contra Sagaz.** `_resolver` recebia
    `nivel=NivelDeMotor.SAGAZ` e o usava para **todos** os lances. Mas o desafio
    publica `co_personagem` como adversario: nos dias da Pita, a pessoa enfrenta
    uma Pita, que nao responde o que um Sagaz responderia;
  · ⛔ **a regua media "Cacau contra Cacau".** `tentativa_com_motor` aplicava o
    nivel do mascote medido aos dois lados do tabuleiro.

⚠️ **O mais desconfortavel do segundo caso: o comentario estava certo.** O
cabecalho de `regua.py` ja dizia *"o adversario do dia esta do outro lado do
tabuleiro; medir com ele seria perguntar 'a Pita resolve um desafio contra a
Pita?', que nao e a pergunta"* - e era exatamente isso que o codigo fazia, ha
meses. ⚠️ `tentativa_com_motor` **nao tinha teste nenhum**; e a licao a levar.

**Decisao: cada lado joga com o seu nivel**, na geracao e na medicao. O lado de
quem resolve usa o nivel de quem resolve (Sagaz no gabarito, o mascote medido na
regua) e o outro lado usa sempre `NIVEL_POR_PERSONAGEM[co_personagem]`.

⚠️ **A semente e o que torna isso uma garantia**: ela e publicada (RF-DES-206) e
derivada por lance, entao o mesmo nivel com a mesma semente escolhe o mesmo
lance - inclusive nos niveis que erram de proposito, cujo `epsilon` e sorteado a
partir dela.

⛔ **Consequencia obrigatoria: a fila inteira precisa ser regerada**, e a
calibracao anterior nao vale mais. As taxas mudam porque o adversario mudou.

### (c) A solucao "banal" - e o dono tem razao, mas o job ja tinha dito

> *"Esta solucao me parece extremamente banal. Ate um macaco treinado conseguiria
> resolver. Se fosse ao menos coroar 2 damas (...) Este e um tipo de desafio que
> eu recusaria."*

Era o `55a03cfd` (coroar 1 dama, casa): Cacau 90%, Pita 95%, Tex 100%, media
**0,95**. ⚠️ **O job ja o tinha marcado**: *"taxa media 0.95 (acima por 0.15)
fora da banda"*. O julgamento do dono e o da regua bateram - o que e a melhor
evidencia, ate aqui, de que a banda de 70-80% esta no lugar certo.

⏳ **E o "coroar 2 damas" que ele sugere e a variante `{damas: 2}`**, ja escrita
em `A_MEDIR` de `scripts/medir_variantes_do_editorial.py` e ainda **nao medida**.
E a proxima medicao a pedir.

---

## 2026-09-11 — A primeira execucao real no Railway, e os quatro defeitos que so ela achou

**Contexto.** Ate aqui o job tinha rodado **local**, contra o mesmo banco `des`.
O dono contestou essa escolha - *"nao e melhor roda-lo no servidor do Railway
pra ja corrigir qualquer problema la?"* - e estava certo: rodar local prova o
codigo e nao prova a operacao. A primeira execucao no servico do Railway gerou
**6 dias de 7** e terminou em `crashed`. Os quatro achados abaixo saem dela.

### (a) ⛔ Um desafio de UM lance, com os moldes ja limpos

`72542794` foi publicado com `js_solucao` de um unico lance (`21x30x23`) e a
regua marcando **20/20 nos tres mascotes**. T049g tinha removido os moldes
triviais na vespera, e mesmo assim.

⚠️ **O cadeado olhava a posicao errada.** O que vai ao ar nao e o molde: e o
molde **mais um lance de variacao** (`gerador._preparar_damas`). Um lance basta
para armar uma cadeia de captura que o molde nao tinha - e ninguem perguntava
nada sobre o resultado dessa soma.

⛔ **E havia um segundo erro dentro do primeiro: a variacao troca o lado.** O
molde tem as brancas a jogar (`W:`); depois de um lance quem joga sao as
**pretas**, e e com elas que a pessoa resolve (`vez_de: -1` em toda linha de
damas ja gravada). `job/moldes_de_damas.py`, escrito para perguntar *"as brancas
cumprem?"*, perguntava pelo lado que nao resolve nada.

**Decisao.** As duas metades foram consertadas juntas, porque uma sozinha nao
resolve: as perguntas passaram a ser sobre **quem esta a jogar** na FEN recebida
(`_lado_e_adversario`), o que as torna validas para molde **e** para posicao
publicada; e o gerador passou a fazer a pergunta **na posicao preparada**,
descartando a tentativa. O cadeado do molde continua, como peneira barata.

⚠️ **Alternativa considerada e recusada:** deixar so o cadeado do gerador. Ele
pegaria tudo, mas gastaria a variacao inteira antes de recusar - e o molde ruim
voltaria a ser sorteado no dia seguinte.

### (b) ⛔ `InternalClientError` matou o dia 7/7

    asyncpg.exceptions._base.InternalClientError:
    cannot switch to state 15; another operation (2) is in progress

A engine do job tinha `pool_size=1` + `pool_pre_ping=True`, e o comentario que
justificava o ping descrevia o problema **certo**: a geracao de um dia passa
minutos em CPU sem tocar no banco, e o proxy do Railway derruba a conexao parada.

⛔ **A defesa e que estava errada.** O pre-ping abre uma transacao para testar a
conexao; numa conexao derrubada o asyncpg devolve um `InternalClientError`, que
o dialeto do SQLAlchemy **nao reconhece como desconexao**. Em vez de trocar a
conexao (que e o que o pre-ping existe para fazer), o erro sobe.

**Decisao: `NullPool`.** Sem pool nao ha conexao dormindo, e o problema deixa de
existir por construcao. O preco - uma conexao TCP nova por operacao - e
irrelevante num processo que acorda uma vez por dia e passa a maior parte do
tempo em CPU. ⛔ `pool_recycle` foi recusado (so encurta a janela) e um
`try/except` em volta da consulta tambem (reintroduz o erro em cada chamada nova
que alguem escrever).

### (c) ⚠️ O relatorio trocava o SINAL do problema

A linha `⚠️ [job] FORA DA BANDA: ['2026-09-11: taxa media 0.10 fora da banda
[0.70, 0.80]']` nao dizia a taxa: `0.10` era a **distancia**. O caso real era
taxa **0.90** - dez pontos **acima** do teto, um desafio banal - e o log se lia
como um desafio duríssimo. ⛔ Um relatorio que troca o sinal manda investigar o
lado errado.

A media virou `regua.taxa_media()` - ela ja existia identica em `dentro_da_banda`
e `distancia_da_banda` - e a linha passou a dizer taxa, lado e distancia.

### (d) A curadoria era impossivel na pratica

O dono abriu o painel e relatou: *"realmente fica muito dificil para mim aprovar
sem conseguir ver as possibilidades de jogadas. O painel deveria ao menos exibir
a solucao de gabarito, lance por lance. Olhando so o JSON dos lances fica muito
dificil para mim visualizar isso."*

**Decisao: o gabarito passa a carregar a posicao depois de cada lance**, e o
painel desenha a sequencia.

⛔ **Quem grava a posicao e quem TEM o motor.** Aplicar `21x30x23` e trabalho do
motor de damas, e a imagem da API nao o importa - ela nao instala `numpy`, e nao
vai instalar por causa de uma pagina interna. Reescrever as regras no painel
seria a **segunda implementacao**.

⚠️ **E no Pontinhos nao ha nada a gravar**, o que parece incoerente e nao e: a
posicao de la **e** a lista de lances (`co_formato_posicao = sequencia_lances`),
entao o quadro k e a concatenacao - sem aplicar regra nenhuma. A posse das caixas
ja era calculada por `_donos_das_caixas`, que desenha a posicao inicial desde o
primeiro dia.

⚠️ **`js_solucao.posicoes` e aditivo, e por isso nao houve migracao** (a coluna e
`JSONB`). A chave nasce ausente nas linhas antigas, e o painel **recusa desenhar
meia sequencia**: ou tem todas as posicoes, ou diz que faltam e manda regerar.
⛔ Desenhar os quadros que existem seria pior - o salto entre dois lances
apareceria como se fosse um lance.

Junto entraram a **numeracao** que o dono pediu: casas 1 a 32 nas damas (com o
caminho do lance aceso) e o rotulo de cada traco livre no Pontinhos (`V_3_4`).
Sem elas a notacao do gabarito nao se liga a desenho nenhum.

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

---

## 2026-09-10 — As modalidades rodiziam, e o enunciado passa a dizer por quais regras se joga

**Contexto.** O dono reparou que as três partidas de damas geradas eram **todas
brasileiras** e perguntou se era coincidência. Não era: estava fixo no código
(`co_modalidade = "brasileira"`). Ele decidiu (`DECISOES-do-dono.md` §8g):
*"precisamos de toda variabilidade de desafios possíveis. Quanto mais variado,
melhor."*

### A medição veio antes da decisão

Os quatro regulamentos — `brasileira`, `anglo`, `portuguesa`, `casa` — rodam nos
**mesmos moldes**: todos são damas de 32 casas, e o que muda são as regras, não o
tabuleiro. Testei os 8 moldes existentes contra cada um:

| modalidade | moldes com solução |
|---|---|
| brasileira | 4 de 8 |
| anglo | 5 de 8 |
| **portuguesa** | **7 de 8** |
| casa | 4 de 8 |

⚠️ Rodiziar não só quadruplica a variedade: **alivia o gargalo**, que é achar
candidato. A portuguesa gera quase o dobro da brasileira com os mesmos moldes.

### ⛔ O ponto perigoso era o motor, e ele não daria erro nenhum

`MotorDamas()` tem `brasileira` por padrão, e ele é construído em **três**
lugares: a geração, o preparo (lances "legais" dependem do regulamento) e a
bancada de medição. Esquecer um deles faria o gabarito ser buscado por um
regulamento enquanto o desafio publicado dizia outro — ⚠️ **e os dois lados
seriam internamente coerentes**. A divergência só apareceria no aparelho de quem
jogasse, como "lance ilegal" num gabarito que o servidor jurava válido. É a mesma
classe do defeito do `uid` do Firebase.

### ⛔ E o rodízio quase travou em fase de novo

Se a modalidade usasse o contador do tipo, metade das combinações
(tipo × modalidade) nunca sairia — e seria **pior de enxergar** que o travamento
anterior, porque a fila *pareceria* variada: tipos alternando, modalidades
alternando, e só uma contagem revelaria os pares ausentes.

Virou um **odômetro**: o dígito da direita (o tipo) gira rápido, o da esquerda (a
modalidade) gira quando o da direita completa a volta. Cadeado conta as 8
combinações em 200 dias.

### `js_objetivo` carrega ONDE e COMO se joga

`variante` sempre, `modalidade` quando existe. ⛔ **Acrescentados por fora de
`valores_da_frase`**, e isso é estrutural: modalidade e variante não são
conhecimento do **tipo**, são fatos do candidato. Se cada receita tivesse de
lembrar de incluí-los, a primeira que esquecesse publicaria uma frase que não diz
por quais regras se joga — e **nada acusaria**, porque a frase sairia bem formada.

### A mentira antiga que isso desenterrou

`co_variante` das damas era `"brasileiras"` fixo. Mas o `data-model.md` diz que
essa coluna usa *"o mesmo vocabulário de `partida.tb001`"*, e lá o aplicativo
grava a **modalidade** (`coVariante: config.modalidade`); a migração `0012`
afirma o mesmo com todas as letras. Enquanto havia um regulamento só, a mentira
era invisível; com o rodízio, o desafio sairia com `variante: brasileiras` ao
lado de `modalidade: casa`, e ⛔ um `JOIN` com o log de partidas nunca casaria.

⚠️ **Fica uma redundância não resolvida:** nas damas, `co_variante` e
`co_modalidade` guardam agora a mesma string. A própria `0012` avisa que *"a
segunda cópia é a que fica errada quando as duas discordam"*. Largar uma das duas
colunas é migração nova, e decisão do dono.

### ⛔ E o Jogo da Velha saiu do Desafio do Dia

*"Jogo da velha não teremos no desafio pois ele não tem muita variação. É um jogo
chato, não há formas diferentes de jogar para caber num desafio."*

⚠️ Até aqui a ausência dela no rodízio era **pendência técnica** (sem medidor no
juiz, sem vetores) e parecia uma tarefa esperando a vez. Agora é **escolha de
produto**: ela não ganha medidor nem vetores para este fim, e a T050(a) deixou de
pedir *"os três jogos"* — são dois.

## 2026-09-11 — A posição inicial do Pontinhos passa a vir do AUTOPLAY (T049h)

**Contexto.** O gerador sorteava os traços da posição de partida **às cegas**, e
o comentário que justificava isso dizia que *"uma partida bem jogada dos dois
lados converge para posições parecidas; o acaso é o que dá variedade à fila"*.

⛔ **É o mesmo argumento que o projeto já testou e descartou.** O dono o
relembrou: no começo do Jogo dos Pontinhos o dataset era de traços aleatórios, a
CNN treinada assim jogava mal *"pois 2 jogadores jogando quase nunca chegavam
àqueles estados aleatórios"*, e foi por isso que se passou ao **autoplay de
minimax** — com o melhor lance de cada estado definido depois pelo oráculo
perfeito. É essa a rede que joga no aplicativo hoje.

**O que torna a reincidência cara aqui**, e não apenas incoerente: **o gabarito
do desafio é produzido pela própria CNN** (o backend roda o mesmo `.tflite` do
aplicativo, e o portão T001 existe para provar que os dois runtimes concordam).
Posição fora da distribuição de treino ⇒ solução de referência subótima ⇒ a régua
mede a coisa errada — e ⚠️ **nada no log denuncia**.

### ⚠️ A ponte não era direta, e o obstáculo é de modelagem

O desafio guarda uma **sequência de lances** (`co_formato_posicao =
'sequencia_lances'`), não uma matriz: a posse de uma caixa é **histórico**, e de
quem é a vez depende de quem fechou caixa. Os NPZ têm só a matriz `9×7`, e os
valores `{0, 1, 8, 9}` dizem *que* uma caixa está fechada, **não de quem** ela é.

✅ **A saída são as posições sem caixa fechada nenhuma.** Nelas o placar é 0-0, a
vez sai da paridade, e **qualquer ordem dos mesmos traços dá o mesmo estado** —
porque "sem caixa fechada" é **monótono**: se o conjunto final não fecha caixa
nenhuma, nenhum prefixo dele fecha. É essa propriedade que devolve um conjunto de
traços à forma de sequência legal.

### O que foi medido, e o que entrou

Dos **3.423.460** estados dos 419 NPZ de
`ia/dados/jogo_pontinhos/profundidade_minimax_11_adaptativo/`, **1.362.893** não
têm caixa fechada, e destes **897.125 são distintos** — 107.577 com 8 traços e
36.000 com 14, as duas fases que o editorial usa hoje.

⚠️ **As três pastas de `ia/dados/jogo_pontinhos/` carregam os mesmos estados** —
3.423.460 em cada uma, com as mesmas 897.125 posições. O que muda entre elas são
os rótulos e os canais, não os tabuleiros. A escolhida é a que **nomeia a
procedência**.

**Formato** (escolha de implementação; o critério do dono foi *"o que fique mais
limpo, claro e de fácil manutenção"*): um `uint32` por posição, um bit por traço.
`dados/jogo_pontinhos/posicoes_de_autoplay_pequeno.npz` — **2,58 MB**, contra
106 MB dos NPZ de origem.

⚠️ **A ordem canônica dos 31 rótulos viaja DENTRO do arquivo** (`co_rotulo`), e
não combinada de boca entre o script e o módulo. Ler um bit com a ordem errada
daria um tabuleiro diferente e **igualmente válido** — a falha mais cara que
existe, porque nada a acusa. `test_posicoes_de_autoplay_pontinhos.py` compara
essa ordem com a do motor do backend.

**Onde está:**

| peça | arquivo |
|---|---|
| constrói o acervo | `scripts/extrair_posicoes_de_autoplay_pontinhos.py` |
| o acervo | `dados/jogo_pontinhos/posicoes_de_autoplay_pequeno.npz` + `LEIA-ME.md` |
| sorteia a posição do dia | `job/posicoes_de_autoplay_pontinhos.py` |
| consome | `job/gerador.py::_preparar_pontinhos` |

### Decisões menores, ditas em voz alta

- ⚠️ **A ordem sai embaralhada, e não a canônica.** Sem caixa fechada os jogadores
  se alternam estritamente, então a ordem decide **de quem é cada traço** — e é
  isso que o aplicativo pinta de azul e vermelho. A ordem canônica é uma varredura
  geométrica do tabuleiro e daria sempre o mesmo padrão. Embaralhar **não** tira a
  posição da distribuição da CNN: a rede não vê dono de traço
  (`partida_para_dataset` manda todo traço ocupado para `9`).
- ⛔ **Pedir uma fase sem acervo falha alto**, com a mensagem dizendo o teto real
  (20 traços no 4×3) e onde se ajusta (`nu_lances_de_preparo`, no editorial).
  Cair de volta no sorteio às cegas resolveria o sintoma e reintroduziria,
  calado, o defeito que a tarefa veio corrigir.
- ⛔ **A semente continua vindo do dia.** O módulo não cria gerador próprio —
  trocar a fonte da posição não podia custar a idempotência de T038.
- ⚠️ **`dados/` não pode voltar ao `.dockerignore`.** A nota histórica daquele
  arquivo diz que `dados/` saiu por ter se mudado para o laboratório, e isso
  convida alguém a reexcluí-lo; sem o acervo na imagem, o job quebra no Railway
  às 6 da manhã e o build fica verde. Cadeado em `test_imagem_do_job.py`.

## 2026-09-11 — ⛔ Nenhum desafio se repete, e a reprise é a única exceção (T049i)

> *"Não podemos ter desafios repetidos, a não ser como fallback de reprise."*
> — o dono, 11/09/2026

**Contexto.** ⚠️ Nada impedia a repetição, e ela **já tinha acontecido**:
`SQL_TIPOS_RECENTES` evita repetir o **tipo**, não a **posição** — e a mesma FEN
`B:W25,26,29:B2,13,17,21` saiu duas vezes em sete dias no `des`, com sementes
diferentes e sem que nada acusasse.

**A regra.** Um candidato só é publicável se a sua **assinatura** —
`(co_tipo_desafio, co_modalidade, js_posicao_inicial, js_chegada)` — não existir
em nenhum desafio já publicado.

⚠️ **Contra o histórico inteiro, não contra os 7 dias da fila.** Um desafio é
publicado **uma vez só** (determinação do dono, 04/09/2026), e repetir o de três
meses atrás é exatamente o que a regra proíbe. É por isso que
`SQL_ASSINATURA_JA_PUBLICADA` ⛔ **não tem `BETWEEN`**, e é a única das três
consultas de leitura do job que não tem — as outras duas têm de propósito.

⚠️ **A modalidade não é redundante com o tipo.** `damas_coroar` roda nas quatro
modalidades sobre os **mesmos** moldes: a mesma posição inicial jogada por
regulamentos diferentes é um desafio diferente. Tirá-la da assinatura recusaria
três candidatos legítimos por dia de damas.

### Três decisões que evitam falha silenciosa

- ⛔ **`IS NOT DISTINCT FROM` e não `=` na modalidade.** `co_modalidade` é **nula**
  no Pontinhos, e em SQL `NULL = NULL` dá `NULL`, não `TRUE`. Com um `=` simples,
  **todo** desafio de Pontinhos pareceria inédito para sempre: a consulta rodaria,
  não acusaria nada, e o cadeado protegeria apenas as damas.
- ⚠️ **Comparação de `jsonb`, não de texto.** O Postgres normaliza `jsonb` — ordem
  de chave e espaço em branco não contam. Comparar `::text` diria "inédito" para o
  mesmo tabuleiro com as chaves em outra ordem.
- ⚠️ **A consulta devolve o `id_desafio` anterior, e não um booleano.** *"Recusado
  por repetição"* não ajuda ninguém a investigar; *"repetiria o desafio `<uuid>`"*
  leva direto à linha que já existe.

### Sem migração, e a conta

`tb001_desafio` cresce **uma linha por dia**: em dez anos são 3.650. A consulta de
unicidade cabe num `SELECT` com `LIMIT 1` sem índice novo, e uma coluna de hash
com `UNIQUE` seria migração para resolver problema que não existe.

### Onde a pergunta entra, e por que ali

**Antes de tudo**, no laço de candidatos de `cobrir_um_dia`. Provar o término
custa até 200 lances e medir a régua custa `3 mascotes × 20 execuções`; esta
pergunta custa um `SELECT` com `LIMIT 1`. Perguntar depois seria pagar o caro
antes do barato — e o candidato seria jogado fora do mesmo jeito.

### ⛔ A recusa não sai calada

Entra em `Relatorio.repetidos`, grita no `stderr` e aparece no resumo. ⚠️ **Sem
isso, o dia em que o acervo de um tipo se esgotar pareceria um dia sem sorte**: o
log diria *"sem candidato"*, a reprise entraria, e ninguém saberia que a causa tem
conserto.

⛔ **Mas repetição sozinha não sai com código 1.** É a mesma lição que
`fora_da_banda` já registra: sinal que dispara sempre é sinal que ninguém lê. O
que acende o painel continua sendo **dia descoberto** — o único defeito deste job
que a pessoa vê na tela.

### ⚠️ E a reprise continua permitida, de propósito

Ela é **cópia com identificador próprio**, e o caminho dela (`job/reprise.py`)
⛔ **não passa por esta consulta** — senão a saída de emergência se recusaria a si
mesma, e o dia ficaria descoberto justamente quando mais precisa de cobertura.

⚠️ As reprises já gravadas **contam** como histórico, e não há por que excluí-las:
uma reprise tem a mesma assinatura da origem, que já está lá.

## 2026-09-11 — Os parâmetros do desafio passam a VARIAR (T049f)

> *"É muito importante que estes parâmetros variem, senão os desafios viram pura
> repetição."* — o dono, 10/09/2026

**Contexto.** O `EDITORIAL` tinha **um** dicionário por tipo: todo
`chegar_ao_placar` era "7 caixas", todo `coroar` era "1 dama em 6 lances". A
**posição** variava; a **tarefa**, não.

**A mudança.** `EDITORIAL` passa a guardar uma **lista de variantes** por tipo, e
a escolha do dia é do **odômetro** — o mesmo mecanismo que já roda tipo e
modalidade —, nunca sorteada: sortear faria a idempotência de T038 depender de
sorte, e duas execuções do job para o mesmo dia gerariam desafios diferentes.

### ⛔ O terceiro dígito, e a armadilha que já pegou duas vezes

O odômetro ganhou um dígito, e é o mesmo erro que apareceu duas vezes em
10/09/2026:

1. `dias % 2` escolhia o jogo **e** o tipo. Um jogo só aparece numa das paridades
   de `dias`, então para ele `dias % 2` era **constante** — sete dias seguidos com
   o mesmo tipo, e os outros nunca.
2. A modalidade quase usou `vez_do_jogo % 4` enquanto o tipo usava
   `vez_do_jogo % 2`: metade das combinações nunca sairia. ⚠️ E esse seria **pior
   de enxergar** — a fila *pareceria* variada, e só uma contagem revelaria os
   pares ausentes.

A regra: o dígito da direita gira rápido; o da esquerda gira quando o da direita
completa a volta. A variante divide pelo **produto** dos dois dígitos à sua
direita — `tipos × modalidades`. Cadeado conta o produto esperado em 400 dias e
exige que **todas** as combinações saiam; dois cadeados irmãos dizem **qual**
dígito ficou em fase, quando algum ficar.

⚠️ **O divisor usa os tipos publicáveis, não os `frescos`** de `escolher_tipo` —
esses variam com `tipos_recentes`, e um divisor que dependesse disso deixaria de
ser reproduzível.

### ⛔ Nenhuma variante entrou sem ser medida

`scripts/medir_variantes_do_editorial.py` roda cada candidata em **oito dias
diferentes** (dias diferentes são posições de partida diferentes) e reporta o
**pior dia**. ⚠️ **A média esconderia o que importa:** 3 candidatos num dia e 0 no
outro publica dia descoberto a cada duas aparições, e a média de 1,5 pareceria
saudável.

**Medido em 11/09/2026 — `pontinhos_fechar_caixas`** (preparo 14, teto 12):

| parâmetros | pior dia | solução média | |
|---|---:|---:|---|
| `{caixas: 4, turnos: 2}` | 2 | 6,6 | ✅ entra (a atual) |
| `{caixas: 3, turnos: 2}` | 3 | 5,7 | ✅ entra |
| `{caixas: 4, turnos: 3}` | 3 | 8,6 | ✅ entra |
| `{caixas: 5, turnos: 3}` | 3 | 9,8 | ✅ entra |
| `{caixas: 5, turnos: 2}` | **0** | — | ⛔ recusada |
| `{caixas: 6, turnos: 3}` | **1** | 10,2 | ⛔ recusada (margem nenhuma) |

**`pontinhos_chegar_ao_placar`** (preparo 8, teto 34):

| parâmetros | pior dia | solução média | |
|---|---:|---:|---|
| `{caixas: 7}` | 2 | 21,5 | ✅ entra (a atual) |
| `{caixas: 6}` | 3 | 20,2 | ✅ entra |
| `{caixas: 5}` | 3 | 18,9 | ✅ entra |
| `{caixas: 8}` | **0** | — | ⛔ recusada |
| `{caixas: 9}` | **0** | — | ⛔ recusada (nada em três dias) |

### ⬜ As damas continuam com UMA variante, e isso é pendência declarada

Uma geração de damas custa **~26 s** (medido), então medir as candidatas é
trabalho de outra janela. As candidatas já estão escritas em
`A_MEDIR` do script; ⛔ **até o número chegar, elas não entram**. Uma variante de
damas não medida é pior que nenhuma: os moldes foram escritos e validados contra
*"coroar em 6 lances"*, e uma janela mais curta pode não ser alcançável a partir
de nenhum deles — o que viraria dia descoberto, e não erro.

### Duas decisões de API que evitam o congelamento silencioso

- ⛔ **`publicacao_de(co_tipo, nu_variante)` exige o índice, sem valor padrão.** Um
  padrão `0` faria uma chamada esquecida publicar a primeira variante para
  sempre, e ⚠️ nada denunciaria: o desafio sairia bem formado, com posição nova
  todo dia, só que sempre com a mesma tarefa. É o mesmo motivo pelo qual
  `RegrasXp.calcularGanho` exige o perfil do jogo sem padrão.
- ⛔ **`parametros_de()` foi removida.** Ela devolvia "os números daquele tipo"
  sem passar pela variante — uma segunda porta que voltaria a congelar a fila.
  Não tinha nenhum chamador.
- ⚠️ **`quantas_variantes` entra por parâmetro em `escolher_variante`:** o gerador
  ⛔ não conhece o editorial, e se conhecesse passaria a depender de com que
  números as coisas vão ao ar — a fronteira que `editorial.py` existe para
  desenhar.

---

## 2026-09-11 — T049e: o `co_versao_motor` deixa de ser um resumo mudo

**Contexto.** `desafio.tb001_desafio.co_versao_motor` guarda `damas-py-2f8e15cd`.
Os oito dígitos são o começo de um SHA-256 da lista de hashes dos arquivos do
motor dentro do espelho do laboratório. ⛔ **Isso não se inverte, e nada no banco
diz de que arquivos saiu.**

O dono viu as primeiras linhas geradas no `des` e pediu a tabela
(`DECISOES-do-dono.md` §8f, 10/09/2026). O argumento que fecha o caso é a
comparação com a irmã:

| | como se decifra |
|---|---|
| `co_versao_perfil` = `perfil-50aede72` | ✅ **sem o Git** — `js_perfil` traz os números, `co_arquivo` e `co_sha256` dizem de onde |
| `co_versao_motor` = `damas-py-2f8e15cd` | ⛔ **de jeito nenhum** |

**Decisão.** `desafio.tb904_motor`, na migração **`0022`** (nova — a `0021` já
estabeleceu que migração aplicada não se edita). Uma linha por
`(co_versao_motor, co_jogo)`, com `js_motores`, o `co_sha256` do
`MANIFESTO_HASHES.json` e `js_arquivos`.

### O formato de `js_motores` não é livre — ele fecha o par de diagnóstico

    o aparelho reporta  →  dart_1.4.0|rust_0.4.0   (tb007_desafio_impedido)
    o servidor guardava →  damas-py-2f8e15cd       (tb001_desafio)

Uma é versão semântica de dois motores; a outra é um hash de um terceiro. ⚠️ **As
duas metades não se cruzavam**, e a pergunta *"por que este desafio não coube no
aparelho desta pessoa?"* ficava sem resposta exatamente quando alguém a fazia.

Por isso a coluna usa a **mesma lista de registros** da `tb007` —
`[{co_jogo, co_motor, co_versao}]` sob a chave `motores`, com `"versao": 1` —, e
as duas se abrem com o mesmo `jsonb_to_recordset`.

⚠️ **São dois registros por jogo, e o contrato entra de propósito:**

| jogo | registros |
|---|---|
| damas | `python` (o port do laboratório) · `contrato` (`contrato_damas.json`, `1.0.0`) |
| pontinhos | `tflite` (SHA-256 do modelo) · `codificacao` (o contrato, `1.0.0`) |

O port Python do servidor e o Dart do aparelho são implementações diferentes e
⛔ **não têm número em comum**. O que os dois lados obedecem, byte a byte — e
onde a comparação é possível — é o contrato.

### A lista de arquivos subiu para os motores, e esse é o ponto delicado

Até aqui o filtro que escolhe os arquivos do resumo era **variável local** dentro
de `versao_do_motor()`. Montar a linha do banco exigiria reescrevê-lo noutro
módulo, e ⛔ **as duas cópias divergiriam no primeiro arquivo novo do motor** —
com o pior sintoma possível: a linha do banco afirmando que o resumo saiu de um
conjunto de arquivos, quando ele saiu de outro, e nada acusando.

Então nasceu `arquivos_do_motor()` nos dois motores, e `versao_do_motor()` passou
a resumir **essa** lista. ⚠️ **A ordem do digesto continua sendo a dos hashes, e
não a dos caminhos** — trocá-la daria outro carimbo sem que um byte do motor
tivesse mudado. Conferido antes e depois: `damas-py-2f8e15cd` e
`pontinhos-py-cd28a45b`, iguais.

### O cadeado que vale por todos: a linha se decifra sozinha

`test_motor_decifravel.py` soma os hashes de `js_arquivos`, recalcula o resumo e
exige chegar de volta ao `co_versao_motor` — com uma **segunda implementação** da
conta, porque reusar a de produção provaria apenas que ela é igual a si mesma. E
um caso **estraga a lista de propósito** (tira um arquivo) e exige que a conta
deixe de bater, para o cadeado não virar decoração.

⚠️ **É isso que liberta a decifração da fórmula de hoje.** Enquanto a única forma
fosse *"descobrir o commit e refazer a conta"*, no dia em que alguém mudasse a
derivação **toda string antiga ficaria irresolvível para sempre** — e ninguém
notaria, porque nada quebra.

### As duas `fk002_motor`, e por que são `NOT VALID`

*"Um catálogo que ninguém referencia não é catálogo"* (o dono, 08/09). A FK
entrou em `tb001_desafio` **e** em `tb002_medicao_regua`: o desafio diz com que
motor foi gerado, a medição diz com que motor a taxa da Pita foi medida.

⚠️ **`NOT VALID` porque o `des` já tem desafios de antes da dimensão.** Validá-los
agora exigiria **inventar** para eles uma linha com um `co_sha256` de manifesto
que ninguém conferiu — ⛔ o oposto do que a tabela existe para fazer. A cláusula
confere toda linha nova e não revarre as antigas; no `prd` a diferença nem
existe, porque lá a tabela nasce vazia.

⚠️ **A reprise é o caso a vigiar, e ganhou vigia.** Ela copia o `co_versao_motor`
da origem, e cópia é **linha nova**: se a origem for anterior à `0022`, o
`INSERT` bate na FK ⛔ **no pior dia operacional** — aquele em que a fila de
aprovados secou e a reprise é o único caminho. Por isso o job pergunta, no começo
de cada execução, se há versão publicada fora da dimensão (`motores_orfaos`) e
**grita no resumo**; ⛔ sem mudar o código de saída, pela mesma lição de
`fora_da_banda`.

### Dois cadeados de migração ficaram menos cegos no caminho

- **O sentinela `9999`** era pergunta de **arquivo**: bastava a palavra aparecer
  em qualquer lugar do SQL. A `0018` cria **quatro** dimensões e só **uma** leva o
  sentinela — as outras três passavam de carona, e uma dimensão nova que
  precisasse dele passaria igual. Agora a pergunta é **tabela a tabela**, sobre os
  `INSERT` daquela tabela, e a isenção é declarada em `DIMENSOES_SO_DO_SERVIDOR`
  com o motivo. ⚠️ **O padrão é exigir**: dimensão nova que não estiver na lista
  reprova — a omissão falha fechada.
- **`test_toda_VW_declarada_e_criada_pela_migracao`** comparava as constantes com
  **uma** migração escolhida à mão, e teria acusado a `vw904_motor` (que existe)
  de não existir. Passou a varrer a pasta. ⚠️ É a sétima aparição do mesmo
  defeito no projeto: cadeado que sabe de antemão onde olhar fica cego
  exatamente quando algo novo chega.

### ✅ Aplicada no `des` em 11/09/2026

`alembic current` → `0022_motor_decifravel`, e o conferidor: **17 tabelas / 17
VIEWs, 17/17 com as colunas na ordem**, `tb904_motor` com **0 linhas** (o estado
certo — quem preenche é o job). ⛔ **No `prd` não**, e não vai antes do portão
T050. ⚠️ A migração vem **antes** do deploy do backend, a lição da `0017`.

### E o conferidor virou alarme falso no mesmo dia — consertado

`scripts/conferir_migracao_desafio.py` reprovava
`desafio.tb903_perfil_dificuldade` por **ter linha**. A regra estava escrita para
um banco recém-migrado, e no `des` o job já havia rodado em 10/09: as 8 linhas
são o resultado **certo** de uma execução. ⚠️ Ele reprovaria assim em toda
conferência dali em diante — e um portão que acusa sempre ensina a ser ignorado,
a mesma lição do `--reporter compact` e do `fora_da_banda`.

⚠️ **A pergunta certa não é *"está vazia?"* — é *"quem pôs isto aqui?"***. Linha
de dimensão só pode ter vindo da migração se o banco **não tiver desafio nenhum**:
sem desafio, o job nunca gravou, e não há outra mão. É isso que ele pergunta
agora. O cadeado principal continua sendo o que lê a **migração**, e esse não
depende de banco nem de ordem de execução.

---

## 2026-09-11 — T049j: o job parava de falar com o banco sem terminar a transação

**O sintoma, visto na operação real:** a sessão do job aparecia
`idle in transaction` por minutos, e o `dh_geracao` dos sete desafios de uma
execução saía com carimbos quase iguais - todos anteriores ao instante em que as
linhas de fato nasceram.

**A causa.** No Postgres a transação começa na **primeira consulta** e só termina
no `commit`/`rollback`. O job lê (plano, taxa observada, rodízio de tipos e, desde
T049i, a pergunta de unicidade) e só depois faz o trabalho caro - gerar
candidatos, provar o término, medir a régua -, que não toca no banco. A transação
aberta atravessava tudo isso.

⛔ **Três consequências, e nenhuma delas dá erro:**

1. `dh_geracao` tem `DEFAULT now()`, e `now()` é o instante em que a **transação**
   começou. O painel de curadoria ordena por `dh_geracao ASC` e mostra *"gerado
   em"* - os dois passam a mentir por minutos.
2. Uma sessão aberta segura o `xmin` e **impede o `VACUUM` de limpar linhas
   mortas no banco inteiro**, não só nestas tabelas.
3. Se o provedor tiver `idle_in_transaction_session_timeout`, ele derruba a
   conexão **no meio** - e o trabalho caro já feito se perde, uma vez por dia,
   sem nada no log explicando por quê.

**A correção** são duas linhas: `await sessao.rollback()` antes da geração e
outro depois da pergunta de unicidade, cada um com o motivo escrito ao lado.

⚠️ **`rollback` e não `commit`, de propósito.** Nada foi escrito desde o último
`commit`, e o verbo diz isso. Um `commit` ali gravaria, sem querer, qualquer
escrita que alguém viesse a acrescentar acima dele - e um `commit` silencioso é
pior que um `rollback` explícito, porque ele **funciona**, e só se descobre o que
ele gravou quando alguém for procurar outra coisa.

⚠️ **O dublê ganhou uma linha do tempo.** `executadas` diz o que foi consultado e
em que ordem, mas **não onde a transação terminou** - e era exatamente isso que
precisava ser visto: uma sessão aberta durante a geração não muda consulta
nenhuma, só segura a conexão. `linha_do_tempo` guarda consultas e fins de
transação na mesma lista, e é lista própria porque vários testes leem
`executadas` por índice.

Conferido que os três cadeados ficam **vermelhos** com o defeito reintroduzido.

⚠️ **O que continua valendo:** a pergunta *"já foi publicado?"* nunca foi atômica
com o `INSERT` - entre as duas está a geração inteira -, e este job roda uma vez
por dia, sozinho.

---

## 2026-09-11 — T049g: o Sagaz joga a PARTIDA, e o desafio é outra coisa

A caçada de 300 candidatas terminou (2h15 de uma thread) e rendeu **161 moldes
para `damas_coroar`** e **9 para `damas_capturar_multipla`**, contra os 4+4
escritos à mão em 09/09.

| tipo | candidatas | passaram na peneira | serviram a 3+ modalidades |
|---|---:|---:|---:|
| `damas_coroar` | 300 | 188 | **167** (156 nas quatro) |
| `damas_capturar_multipla` | 295 | 17 | **8** (as oito nas quatro) |

⚠️ **Os 2,7% do `capturar_multipla` confirmam o diagnóstico do jogo, e não da
ferramenta**: 185 das 295 nunca cumpriram dentro do teto e 73 já nasciam com a
cadeia armada. Capturar duas em sequência é objetivo **adversarial**.

### ⛔ O achado que importa: 13 moldes aprovados publicavam desafio de um lance

O cadeado novo (`tests/unitarios/test_moldes_de_damas.py`) reprovou **10 dos 171
moldes de coroar** e **3 dos 12 de captura** — e os 10 tinham passado pela peneira
com Sagaz deste mesmo script.

⚠️ **A causa é sutil, e vale para qualquer medição futura: o Sagaz joga a
PARTIDA, não o DESAFIO.** Ele escolhe o melhor lance para vencer, e coroar de cara
costuma ser mau lance — a pedra avança sozinha e é capturada na resposta. Então a
medição anotava *"objetivo no lance 3"* em posições onde **qualquer pessoa cumpre
no lance 1**: quem joga o desafio não está jogando para vencer, está cumprindo a
tarefa.

⛔ **E o desafio sairia bem formado:** posição legal, solução achada, régua
medida, XP calculado — e resolvido no primeiro toque, sem nada no log acusar.

Os 3 de captura eram fundadores escritos à mão, o que responde **por medição** a
pergunta que estava aberta sobre eles. ⚠️ E note a assimetria que justifica ter
mantido os outros fundadores: um molde **trivial** publica um desafio ruim; um
molde de que o objetivo é **inalcançável** só faz o gerador tentar outro.

### A pergunta certa é direta, e não custa um nó de busca

*"Existe um lance legal, agora, que cumpre o objetivo?"* — uma geração de lances
por modalidade. Por isso ela cabe **na suíte** e **na peneira** do script, antes
de gastar o Sagaz.

⛔ **Um módulo só** (`job/moldes_de_damas.py`), usado pelos dois. Duas cópias do
critério divergiriam, e no dia em que discordassem quem estivesse errado mandaria
— a mesma lição que `leitura_de_migracao.py` já carrega.

⚠️ **A pergunta é feita nas QUATRO modalidades**, porque a peneira com Sagaz roda
só na brasileira — foi assim que dois moldes entraram com a portuguesa cumprindo
no lance 1, publicando um desafio de um lance **num dia de cada quatro**.

⚠️ **E o verificador olha a POSIÇÃO RESULTANTE, não a notação.** Contar casas de
chegada em `{1,2,3,4}` erraria nas regras em que uma captura que *atravessa* a
última fileira não coroa. (Escrevendo este módulo eu errei o parser da FEN uma
vez: o primeiro campo de `B:W…:B…` é o **lado a jogar**, não uma cor de peça, e um
`startswith("B")` ingênuo conta zero peça preta — o que transforma qualquer lance
numa captura de quatro.)

### A medição das variantes de damas ficou contaminada

`scripts/medir_variantes_do_editorial.py damas` rodou **antes** desta limpeza:
`damas_coroar` aprovou as quatro candidatas (pior 3), mas
`damas_capturar_multipla` deu `[3, 2, 1]` nas três, com solução média de **2,0
lances** — o sintoma de que 3 dos 5 moldes daquele tipo eram triviais. ⏳ Refazer
depois da limpeza; ⛔ variante escolhida sobre medição contaminada é pior que
nenhuma, porque parece fundamentada.

---

## 2026-09-11 — T049f fecha: o que é variante, e o que é só um número na frase

A medição das damas foi **refeita** depois da limpeza dos moldes triviais, e a
contaminação era exatamente o que se supunha:

| tipo | antes (moldes sujos) | depois (moldes limpos) |
|---|---|---|
| `damas_coroar` | pior 3, solução média **3,9** | pior 3, solução média **6,8** |
| `damas_capturar_multipla` | **`[3,2,1]`**, média **2,0** | **`[3,3,3]`**, média **2,8** |

⚠️ A fragilidade do `capturar_multipla` era dos **moldes**, não do tipo. Três dos
cinco entregavam o objetivo no primeiro lance.

### ⚠️ A unidade que não estava clara, e sem a qual os números enganam

`lances`, no `js_chegada`, é a janela em **lances do jogador**
(`{"tipo": "lances_do_jogador"}`). Já o `nu_lances_solucao` que o script imprime
é `len(js_solucao["lances"])` — e a fita do gabarito **inclui os lances do
adversário**, de propósito (sem eles a sequência não é reproduzível). São
**meios-lances**.

Por isso uma solução de 6,8 cabe numa janela de 6: são ~3,4 lances do jogador.

### O que isso revelou: janela que não aperta não é variante

Medindo `coroar` com janelas 4, 6, 8 e 10, as três últimas saíram **idênticas —
inclusive no tempo de geração** (117s, solução 6,8). ⚠️ Números iguais ali não são
coincidência: é o gerador **não descartando candidato nenhum** por causa da
janela. Só a de 4 apertou — 210s contra 117s, com a solução caindo para 4,3 —, e é
esse custo que prova que ela muda o que é aceito.

Em `capturar_multipla` as três janelas medidas deram o mesmo número (116s, 2,8),
porque a captura encadeada cai em ~1,4 lances do jogador.

⛔ **Então entraram duas variantes em `coroar` e uma em `capturar_multipla`.**
Publicar `{lances: 8}` e `{lances: 10}` seria a mesma tarefa com outro número na
frase — e a frase é o que a pessoa lê, mas não é o que ela joga. Era essa
repetição que a prioridade do dono (*"é muito importante que estes parâmetros
variem"*) mandou acabar.

⏳ **A variação que falta muda a TAREFA, e não a folga**, e está escrita em
`A_MEDIR`: `{damas: 2}` no coroar e `{lances: 2}` / `{lances: 3}` na captura.
⚠️ `{damas: 2}` pode não ser alcançável a partir de moldes escritos para uma dama;
se der `pior 0`, a resposta é caçar moldes próprios, ⛔ nunca afrouxar a janela
para o número passar.
