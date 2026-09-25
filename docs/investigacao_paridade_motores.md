# Investigação: o motor do servidor não joga como o do app

⚠️ **Este arquivo é o diário de uma investigação em curso**, e existe para o
raciocínio sobreviver às compactações da conversa. Ele é acrescentado, nunca
reescrito: cada sessão entra com data, o que foi medido e o que se concluiu.

Aberto em **2026-09-25**, a partir de um relato do dono.

---

## O relato que abriu o caso (25/09/2026)

O desafio do dia `d6a7317e-c0e4-458f-89a3-4c3c0e10f8f0` (`damas_coroar`, anglo,
*"Coroe 1 dama em até 8 lances contra Magno"*) ficou, nas palavras do dono,
*"praticamente impossível"*.

Ele jogou a partida no `des` e comparou, lance a lance, com a solução de
referência desenhada no painel de curadoria:

| lance | o painel dizia | o app jogou |
|---|---|---|
| 2, 4, 6 | igual | igual |
| **8** | **19-23** | **16-20** |

A partida está no banco (`a267bba1-88f1-4f49-9121-bda8def57955`), com FEN antes
de cada lance e o motor de busca identificado em cada linha. Ela é o vetor de
teste desta investigação inteira.

---

## ✅ O que foi DESCARTADO, com prova

### A semente está correta

A derivação do app é `(mestra + ordem × 2654435761) & 0x7FFFFFFF`
(`lib/core/jogos/semente_da_partida.dart:81`). Conferida contra o banco, com a
semente publicada `282565477`:

- ordem 2 → `1296469703` ✅ (banco: 1296469703)
- ordem 4 → `162890281` ✅ (banco: 162890281)

⛔ **Não mexer nisto.** O app usa a semente publicada, e a garantia que importa -
duas pessoas enfrentando o mesmo adversário - está intacta.

### A tabela de transposição é a mesma nos três motores

`BITS_DA_TABELA = 20` no Python (`motor/busca_damas.py:130`), `bitsDaTabela: 20`
no Dart, `bits_padrao() = 20` no Rust. Era a hipótese principal e **está
descartada**.

### O port é FIEL — os dois varrem a mesma árvore, nó a nó

Ver a medição abaixo. Esta era a dúvida mais cara da investigação, e a resposta
é a melhor possível.

---

## ⛔ A CAUSA RAIZ: a rede de segurança de tempo morde SEMPRE no servidor

Medido na posição de antes do lance 8
(`B:W15,22,27,28,29,30,31:B6,8,10,12,13,16,19,21`), com o motor do backend, nível
Sagaz:

| | lance | nós | profundidade | tempo |
|---|---|---|---|---|
| Python **como está hoje** | `19-23` | **124.928** | **11** | 10,0 s (estourou) |
| Python **sem o relógio** | `16-20` | **288.001** | **12** | 29,8 s |
| Rust no aparelho (do banco) | `16-20` | **288.001** | **12** | 114 ms |

⚠️ **Os parâmetros do Sagaz são `teto_de_nos=288000` e `tempo_maximo=10.0`.** No
aparelho o Rust cumpre os 288 mil nós em 114 ms, e os 10 segundos nunca chegam
perto de morder. No servidor, o Python é cerca de **40× mais lento** e bate no
relógio **todo lance**, sempre - parando com menos da metade do orçamento e **um
ply mais raso**.

⛔ **É o relógio, e só ele.** Desligado, os dois motores param no mesmo nó
(288.001), na mesma profundidade (12), com a mesma avaliação (132, e `-132` no
banco porque o Rust reporta pela perspectiva das brancas) e escolhem **o mesmo
lance**. O laboratório já tinha avisado, em
`motor_dart/bin/conferir_equivalencia_com_rust.dart`: *"Toda vez que ela morde, a
promessa do teto de nós se quebra."*

### As três consequências, e a terceira é a pior

1. **O gabarito é jogado por um Sagaz enfraquecido** (124 mil nós, profundidade
   11). O adversário do painel é mais fraco que o do aparelho, então o desafio
   real é sempre mais difícil que o medido. É exatamente o sintoma relatado.
2. **A régua mede contra esse mesmo adversário enfraquecido.** A calibração dos
   11 tipos descreve uma partida que ninguém joga.
3. ⛔ **O gabarito NÃO É REPRODUTÍVEL.** O ponto de parada depende de quantos nós
   couberam em 10 segundos, logo da **velocidade e da carga da máquina**. Duas
   execuções do job na mesma posição podem escolher lances diferentes. Isso
   contradiz a reprodutibilidade que `job/semente.py` declara como razão de ser
   da semente derivada, e nada no dado denuncia.

---

## ⚠️ A SEGUNDA divergência, real e ainda não consertada: a base de finais

`motores/damas/motor_damas.py:390` chama `buscador.buscar(...)` **sem passar base
de finais**. O `Buscador` do laboratório aceita uma (o *probing* está em
`motor/busca_damas.py:876`), e o app joga **com** ela: na partida do dono, o
lance 16 fez **795 consultas, 636 acertos (80%)**.

O `Cargo.toml` do motor Rust é explícito sobre a versão 0.4.0: *"**Muda quais
lances o motor escolhe** nos finais que a base cobre"*.

⚠️ **Ela não explica o lance 8** - ali houve zero consultas à base, porque com 16
peças a busca não alcança os finais cobertos. Mas é uma divergência **garantida**
em todo final, e precisa ser fechada depois do relógio.

---

## ⛔ Por que nada disso foi pego por teste

A corrente de cadeados tem um elo faltando:

| cadeado | prova |
|---|---|
| `tests/unitarios/test_espelho_laboratorio.py` | SHA-256: espelho do backend = laboratório (Python = Python) |
| `test/modulos/jogos/damas/paridade_motor_test.dart` | SHA-256: motor do app = laboratório (Dart = Dart) |
| `motor_dart/bin/conferir_equivalencia_com_rust.dart` | comportamento: Dart = Rust, **sem teto e sem relógio** |

⛔ **Nenhum confere Python contra Dart/Rust**, e o único cadeado de comportamento
que existe roda justamente **sem o relógio** - isto é, na única condição em que o
defeito não aparece. As cópias estão todas trancadas; o comportamento entre as
duas linguagens nunca foi conferido uma vez.

---

## O caminho proposto (a decidir com o dono)

1. ⛔ **Desligar o relógio no motor do servidor** é a correção de corretude, e é
   quase de uma linha. Mas custa **~30 s por lance do adversário** em vez de 10 s,
   e a régua roda 20 execuções × 3 mascotes por candidato: o job passaria de horas
   para dezenas de horas. Corrige e inviabiliza.
2. ✅ **Chamar o motor Rust do servidor** resolve os dois de uma vez. Ele já expõe
   fronteira C de texto - `damas_buscar(json) -> json`, `damas_versao`,
   `damas_liberar` em `motor_rust/src/ffi.rs`, e o crate é `cdylib` -, então o
   Python o chama com `ctypes`. São 114 ms contra 29,8 s: **260× mais rápido**.
   ⚠️ **E a medição de hoje é o que torna essa troca segura**: como os dois varrem
   a mesma árvore nó a nó, trocar o Python pelo Rust não muda resultado nenhum,
   só o tempo.
   ⚠️ Ressalva: o Rust **não tem campo de semente nem de ruído** (conferido no
   `Pedido` de `ffi.rs`) - ele existe só para o Magno. Os níveis fracos da régua
   sorteiam o erro na avaliação, do lado do Dart/Python, então a régua precisa de
   estudo próprio.
3. **Ligar a base de finais** no servidor, na mesma versão que o app extrai.
4. **Fechar o elo do cadeado**: conferir o lance escolhido por Python e Rust nas
   condições reais de jogo (com o teto de 288 mil), e não só sem teto.

---

## Scripts desta investigação

Ficaram no scratchpad da sessão (`.../scratchpad/`):

- `prova_lance8.py` - reproduz a partida até o lance 8 e pergunta o lance ao
  motor do servidor.
- `estatisticas_lance8.py` - o mesmo, chamando o `Buscador` direto para expor
  nós, profundidade e acertos na tabela. É o que achou a causa.

⚠️ Ambos precisam de `PYTHONPATH` na raiz do backend quando rodados de fora dela.

---

## 25/09/2026, parte 2 — o dono aponta que escolher o Rust só MOVE a fronteira

Pergunta dele, e ela está certa: *"No App rodamos Dart e Rust? Se o nosso problema
vem de diferenças na forma de jogar entre App e Servidor, ao utilizarmos apenas
motor Rust não estaríamos diante de uma nova divergência App/Servidor?"*

**Sim.** A divisão no aparelho é:

| nível | quem joga no aparelho |
|---|---|
| Magno (Sagaz) | **Rust** onde há biblioteca nativa; **Dart** onde não há |
| Cacau · Pita · Tex | **Dart** sempre — o Rust não tem campo de ruído nem de semente |

⚠️ **E a implicação é maior que a pergunta:** se Dart e Rust divergirem sob o teto
de nós, isso **já acontece hoje entre dois aparelhos**, sem o servidor entrar na
história — duas pessoas no mesmo desafio enfrentando adversários diferentes, que é
precisamente o que a semente publicada existe para impedir (RF-DES-206).

⛔ **E o cadeado que deveria cobrir isso tem o mesmo ponto cego do Python:**
`conferir_equivalencia_com_rust.dart` roda **sem teto e sem relógio**, de
propósito (para a contagem de nós não ficar cega à qualidade da poda). É a única
condição em que este defeito não aparece.

### A pergunta que reordena o trabalho

⛔ **Não é "qual motor roda no servidor".** É: **os três escolhem o mesmo lance sob
o teto real de 288 mil nós?**

- Se **sim**, a escolha do servidor vira operacional (custo e deploy), porque
  qualquer um representa o app fielmente.
- Se **não**, escolher motor no servidor é irrelevante enquanto o app divergir de
  si mesmo.

✅ **Primeira evidência a favor, medida hoje:** Python e Rust pararam no mesmo nó
(288.001), na mesma profundidade (12), com o mesmo lance. Dois motores que varrem
a árvore na mesma ordem param no mesmo lugar quando o orçamento acaba.

### Recomendação revista: Dart, não Rust

| | cobre | velocidade |
|---|---|---|
| Rust | só o **adversário** (Magno). A régua continuaria no Python | 114 ms |
| **Dart** | **gabarito e régua** — é o código que 100% dos aparelhos embarcam, com o ruído e o `Random` dos níveis fracos | entre os dois, a medir |

⚠️ Como é a **régua** que decide o que vai ao ar, deixá-la no Python mantém de pé
a consequência nº 2 do defeito original.

### ⚠️ Risco novo, ainda NÃO medido

Se o Dart no aparelho não cumprir os 288 mil nós dentro dos 10 s, **o relógio morde
no app também**, num celular modesto — e dois aparelhos divergem pelo mesmo
mecanismo achado no servidor. É medição de bancada, e ainda não foi feita.

---

## 25/09/2026, parte 3 — onde os parâmetros moram, e por que sincronizá-los não bastaria

Pergunta do dono: *"o que acontece se amanhã revisarmos esse teto de 288 mil nós
e essa rede de segurança de 10 segundos? Qual o risco de nos esquecermos de
ajustar no gerador?"*

### O levantamento (varredura nos três repositórios)

| onde | forma | quem consome |
|---|---|---|
| `contrato_damas.json` (backend/laboratório) | dado | o **servidor**, via `parametros_do_nivel()` |
| `contrato_damas.json` (frontend, `assets/jogos/damas/`) | dado, cópia byte-idêntica | o **app**, via `_nivelDoJson` em `logica/contrato_damas.dart:276` |
| `motor/busca_damas.py:243` e `:385` | hard-code | presets do laboratório |
| `motor/busca_damas.dart:256` e `:331` | hard-code | presets do motor Dart |
| `logica/ritmo_damas.dart:152` | `const int tetoDeNosDoMagno = 288000;` | o tempo que a CPU "pensa" **na tela** |
| `bancada/bancada_screen.dart` | hard-code | a bancada de medição |

✅ **O contrato JSON é fonte única nos dois lados, e já tem cadeado:**
`test/modulos/jogos/damas/contrato_hash_test.dart` compara o SHA-256 das duas
cópias e falha se divergirem. Mudar o teto no contrato chega ao servidor e ao app
juntos.

⚠️ **As quatro cópias hard-coded não têm cadeado.** A mais perigosa é
`ritmo_damas.dart:152`: ela não decide o lance, decide a espera anunciada na tela.
Fora de sincronia, nada quebra — só fica errado.

### ⛔ E nada disso teria evitado o defeito de hoje

Os dois lados tinham **os mesmos** 288.000 e 10,0, lidos do mesmo contrato. A
sincronização estava perfeita. O defeito é que **o mesmo par de números significa
níveis diferentes em máquinas de velocidades diferentes**.

⚠️ **Subir o teto PIORA o defeito**, em silêncio: de 288 mil para 500 mil não muda
nada no Rust, que continua terminando antes dos 10 s; no lado lento o relógio
morde ainda mais cedo, e a distância entre gabarito e partida real cresce sem
nenhum parâmetro fora de lugar.

### A proteção que falta é de COMPORTAMENTO

Um conjunto de posições conhecidas com o lance esperado, conferido nos dois lados.
Ele quebra se alguém mudar o teto num lugar só **e** se mudarem nos dois — e a
segunda quebra é a informação certa, porque obriga a atualizar o vetor
conscientemente.

⚠️ **O primeiro vetor já existe de graça:** a partida `a267bba1` do dono, com FEN
antes de cada lance, o lance jogado e o motor identificado em cada linha.

---

## DECISÕES DO DONO (25/09/2026)

1. ⛔ **O servidor passa a jogar com o motor DART.** Não com Python (custo e
   divergência) e não com Rust (cobre só o adversário, deixando a régua no Python).
2. ⛔ **Sem reteste de Rust ↔ Dart.** O dono considera a equivalência já concluída
   há semanas, e a evidência sustenta: nas três medições disponíveis — Rust no
   aparelho, Python sem relógio, e o Dart numa fotografia de teste do frontend
   (`specs/009-desafio-do-dia/fotografias/bruto/antes.json`) — os três motores
   pararam em **288.001 nós**.
3. ⛔ **O cadeado de comportamento entra JUNTO com a migração**, na mesma tarefa.
   Trocar o motor sem ele deixaria a próxima divergência igualmente muda.

---

## 25/09/2026, parte 4 — a correção, construída e provada

### ✅ A prova de que o motor Dart no servidor resolve

Mesma posição (antes do lance 8 da partida `a267bba1`), mesmos parâmetros do
contrato, **sem relógio**:

| | lance | nós | profundidade | acertos na tabela | tempo |
|---|---|---|---|---|---|
| Python, como estava | `19-23` | 124.928 | 11 | — | 10,0 s (estourou) |
| Python, sem relógio | `16-20` | **288.001** | **12** | **27.908** | 29,8 s |
| **Dart, o novo servidor** | **`16-20`** | **288.001** | **12** | **27.908** | **0,66 s** |
| Rust, no aparelho | `16-20` | **288.001** | **12** | — | 0,11 s |

⚠️ **O número que fecha a questão é o de acertos na tabela de transposição:
27.908 nos dois.** Dois motores só chegam ao mesmo número de acertos se visitarem
as mesmas posições **na mesma ordem**. O port sempre foi fiel; o que o traía era a
coleira de tempo.

E o custo caiu **43×** em relação ao Python de hoje, o que tira a régua do
caminho crítico.

### As peças construídas

| arquivo | o quê |
|---|---|
| `ia/…/motor_dart/bin/servidor_de_lances_damas.dart` | o motor do aparelho atendendo por linha de texto (um pedido JSON, uma resposta JSON), processo que fica vivo |
| `ia/…/motor_dart/bin/compilar_servidor_de_lances.dart` | compila **e carimba** no binário o SHA-256 dos 15 arquivos de `lib/` |
| `arena-sagaz-backend/motores/damas/jogador_dart.py` | o cliente: abre o processo, **confere o carimbo na abertura** e pede lances |
| `arena-sagaz-backend/tests/unitarios/test_jogador_dart.py` | a trava e o vetor de paridade — 7 casos, 2,9 s |
| `scripts/espelhar_laboratorio.py` | passou a espelhar os 15 fontes `.dart`, que são a **referência** da trava |

⛔ **Nenhum parâmetro de nível mora nas peças novas.** Teto, profundidade, ruído e
relógio chegam no pedido, e quem os lê é o backend, no contrato. Era o risco que
o dono levantou: o número já mora em quatro lugares, e uma quinta cópia seria a
que ficaria para trás.

### A corrente da trava, fechada

    app        == laboratório   `paridade_motor_test.dart` (SHA-256 dos 15) — já existia
    espelho    == laboratório   `espelhar_laboratorio.py` + manifesto
    executável == espelho       `jogador_dart.py`, na abertura do processo
    ─────────────────────────────────────────────────────────────────────
    logo, executável == app

✅ **E a trava foi vista MORDENDO**, não só passando: acrescentado um byte a
`regras_damas.dart` no espelho, a abertura falhou com
`divergem: regras_damas.dart`, os dois resumos e a receita de recompilar. Espelho
restaurado em seguida.

### ⛔ O servidor joga SEM relógio — e isso é decisão registrada

`tempo_maximo` não é enviado. A rede de segurança existe no aparelho porque há
alguém esperando na tela; no servidor não há, e mantê-la reintroduziria o defeito:
o ponto de parada dependeria da carga da máquina, e **o mesmo desafio daria
lances diferentes em duas execuções**.

### O que AINDA falta (em ordem)

1. ⛔ **Ligar o `JogadorDart` no job.** As peças existem e estão provadas, mas
   `job/` e `regua.py` continuam chamando `MotorDamas` (Python). Enquanto isso não
   mudar, **nada do que está acima afeta um desafio gerado**.
2. ⚠️ **A base de finais no servidor**, com a mesma versão que o app extrai. É a
   segunda divergência, garantida em todo final, e é o que impede o vetor de
   paridade de cobrir os lances 16 em diante.
3. **A régua**: os níveis fracos sorteiam o erro, e o `Random` do Dart não é o do
   Python. Com o `JogadorDart` a régua passa a usar o mesmo sorteador do aparelho
   — mas isso precisa ser conferido, não presumido.
4. **O executável no deploy**: hoje ele é achado no laboratório vizinho ou pela
   variável `MOTOR_DART_DAMAS`. O job roda na máquina do dono, então isso basta
   por agora; se um dia rodar em contêiner, o binário precisa viajar.

---

## 25/09/2026, parte 5 — ligado no job, e a SEGUNDA CAMADA do defeito

### ⛔ O teto do contrato não era o que o servidor gastava

Ao ligar o `JogadorDart` no caminho que o job realmente usa, apareceu uma camada
do defeito que a parte 4 não tinha visto. `MotorDamas.escolher_lance` usava o
**menor** entre o teto do nível e o da camada — e o da camada era sempre menor:

| onde | teto da camada | teto do contrato (Sagaz) |
|---|---|---|
| `job/gerador.py` (o gabarito) | 60.000 nós · 2,0 s | 288.000 |
| `job/regua.py` (a medição) | 20.000 nós · 1,0 s | 288.000 |
| `job/estado_terminal.py` (a prova de fim) | 8.000 nós · 0,5 s | 288.000 |

⛔ **O adversário do gabarito é o mesmo personagem que responde no aparelho de
quem resolve.** Jogando com 4,8x menos nós no servidor, ele escolhe outro lance
no meio da partida, e a solução publicada deixa de ser reproduzível a partir
dali.

Medido na posição do lance 8 da partida do dono, **pelo caminho do job**:

| | lance | nós | tempo |
|---|---|---|---|
| Python, como o job estava | `19-23` | **24.576** | 2,03 s |
| Dart, ligado | **`16-20`** | **288.001** | 0,68 s |
| o aparelho (banco) | `16-20` | 288.001 | 0,11 s |

⚠️ O `19-23` é exatamente o lance que estava no painel de curadoria. E note: o
Python gastava **3x mais tempo** para fazer **12x menos trabalho**.

⚠️ **O teto da camada existia por um motivo real, e ele acabou.** Estava escrito
em `gerador.py`: *"sem orçamento, uma única geração de damas passou de 6 minutos
sem terminar"*. O motivo era a lentidão do port. Medido agora, por lance:

| nível | abertura | meio-jogo | final |
|---|---|---|---|
| cacau · pita · tex | 0,012 - 0,054 s | 0,012 s | 0,012 s |
| **sagaz** | 0,960 s | 0,891 s | 0,140 s |

O `limite` continua sendo **alimentado** (`contar_no`) e continua respondendo
`cancelado()`. O que ele não faz mais é mudar a força do adversário.

### ✅ A base de finais entrou, e a paridade agora cobre a partida INTEIRA

A segunda divergência da parte 3 está fechada. Três peças:

1. **`consulta_base_finais_damas.dart` mudou de casa** — de
   `arena-sagaz-frontend/lib/modulos/jogos/damas/logica/` para o motor. É a
   consulta **na raiz**: quando a posição cabe na base, o aparelho responde sem
   buscar. Sem ela o servidor buscaria em todo final de até 4 peças. ⚠️ É a mesma
   mudança que `oraculo_de_finais_damas.dart` fez em 27/08/2026, com a mesma
   solução: o endereço antigo virou reexporte de uma linha. O motor passou de
   **15 para 16** arquivos.
2. **O servidor de lances abre a base** (protocolo **2**): `pasta_da_base` no
   pedido, cache por pasta e modalidade, e a base entra **na raiz e na busca** (o
   *probing*), como no aparelho.
3. **⛔ É a base do APP, não a do laboratório.** O laboratório tem 41 fatias por
   modalidade; o que viaja no APK tem 23 (metade sai por simetria de cor). Onde
   falta uma fatia a resposta é `foraDaBase` e o motor **busca** — então a base
   crua daria **mais** base e mesmo assim divergiria. `pasta_da_base_de_finais`
   recusa a crua pela chave `empacotado_em` do manifesto.

⚠️ **E ela só entra no Sagaz**, porque é assim na tela (`_talvezCarregarABase`
desiste quando o nível não é o Magno). Ligá-la para todos faria Cacau, Pita e Tex
jogarem melhor no servidor do que jogam no aparelho — a mesma classe de erro, com
o sinal trocado.

### ✅ A PROVA: 13 de 13 lances da partida do dono

A partida `a267bba1` veio do banco (`jogo_damas.vw002_jogada`) com FEN, semente e
telemetria de cada lance. O servidor reproduziu **todos os treze lances da CPU**:

| lance | aparelho | servidor | nós | prof. | consultas/acertos na base |
|---|---|---|---|---|---|
| 4 · 6 · 8 | `15-19` `4-8` `16-20` | iguais | 288.001 | 12 | 0 / 0 |
| **16** | `21-25` | **igual** | **288.001** | **14** | **795 / 636** |
| 20 | `13-17` | igual | 23.404 | 10 | 73 / 64 |
| 22 | `31-26` | igual | 3.989 | 8 | 34 / 34 |
| 24 | `26x19x28` | igual | 12 | 2 | 0 / 0 |

⚠️ **Os números da base são a prova de que é A base, e não uma base.** Acertar
795 consultas e 636 acertos por acaso não acontece.

⚠️ Nos lances 2, 10, 12, 14, 18 e 26 o aparelho não gravou telemetria: é o
**atalho de lance único** da tela. O servidor buscou e chegou ao mesmo lance,
porque era o único legal. ⛔ Reproduzir o atalho no motor seria copiar para lá uma
decisão que é de tela, e ela não muda lance nenhum.

### O que mudou no código

| arquivo | o quê |
|---|---|
| `motores/damas/motor_damas.py` | `escolher_lance` delega ao Dart; `MOTOR_DAMAS_DO_SERVIDOR` escolhe, padrão `dart`, ⛔ **sem queda silenciosa**; `NIVEIS_QUE_USAM_A_BASE` |
| `motores/damas/jogador_dart.py` | processo compartilhado (`jogador_compartilhado`), `pasta_da_base_de_finais`, protocolo 2 |
| `ia/.../bin/servidor_de_lances_damas.dart` | base na raiz e na busca; `consultas_base`/`acertos_base` na resposta |
| `ia/.../lib/consulta_base_finais_damas.dart` | **novo** (mudou de casa) — o 16º arquivo do motor |
| `arena-sagaz-frontend/.../logica/consulta_base_finais_damas.dart` | virou reexporte |
| `test/modulos/jogos/damas/paridade_motor_test.dart` | 15 → 16 arquivos |
| `scripts/espelhar_laboratorio.py` | o 16º arquivo entra no espelho |
| `job/gerador.py` · `job/regua.py` · `job/estado_terminal.py` | os três tetos ficam, documentados: ⛔ não cortam mais a busca das damas |
| `tests/unitarios/test_jogador_dart.py` | o vetor virou a partida inteira: 13 lances, com nós, profundidade e base |
| `tests/unitarios/test_motor_damas.py` | o padrão é Dart; o teto da camada não corta; a paridade com o port roda em `MOTOR_DAMAS_DO_SERVIDOR=python` |
| `ferramentas/consultas_sql/desafio_limpar_TUDO_DES.sql` | **novo** — esvaziar a fila gerada com o motor errado |
| `Dockerfile.job` | **multi-stage**: um estágio `dart:stable` compila o motor para `linux/amd64` |
| `scripts/conferir_motor_dart.py` | **novo** — o portão de build: a imagem joga o que o aparelho joga? |
| `scripts/espelhar_laboratorio.py` | o pacote do motor e a base de finais entram no espelho |
| `.gitignore` · `.dockerignore` | barram o `pubspec.lock` e o `.dart_tool/` do espelho |

### ✅ O JOB DO RAILWAY VOLTOU A FUNCIONAR — a imagem compila o motor

Ligar o motor Dart quebrou o job da nuvem, e por um bom motivo: o `Dockerfile.job`
constrói uma imagem `python:3.11-slim`, e nela não havia nem o executável (o que
existe na máquina do dono é um `.exe`, de Windows) nem a base de finais (ela mora
nos assets do *frontend*). O job falhava alto — que é o certo, comparado a gerar
com o motor errado — mas a fila pararia de crescer.

⛔ **Isso foi consertado no mesmo dia**, e não deixado como escolha para o dono:

1. **O espelho passou a carregar o que compila o motor** — `pubspec.yaml`,
   `bin/servidor_de_lances_damas.dart` e `bin/compilar_servidor_de_lances.dart`.
   ⚠️ O `pubspec.lock` ⛔ vai junto (entrou no `.gitignore` e no `.dockerignore`):
   ele fixaria versões resolvidas no Windows, e o que o build precisa é de um
   `pub get` resolvido na própria imagem.
2. **E a base de finais**, em `espelho_laboratorio/base_finais_damas/` — 9,5 MB,
   copiados **dos assets do aplicativo**, pelo mesmo mecanismo e com a mesma
   justificativa do `.tflite` de 19,8 MB do Pontinhos (RF-DES-148: o que não
   estiver neste repositório não existe na nuvem). ⚠️ E o `jogador_dart.py` passou
   a ler **só** do espelho: uma segunda origem consultada em tempo de execução é
   como duas versões passam a existir sem ninguém decidir.
3. **O `Dockerfile.job` virou multi-stage.** Um estágio `dart:stable` roda
   `dart pub get` e `dart run bin/compilar_servidor_de_lances.dart`; o executável
   Linux atravessa com `COPY --from=motor`, e o SDK de ~700 MB fica para trás.
4. **E há um portão de build novo** — `scripts/conferir_motor_dart.py` —, irmão do
   que já existia para o runtime de inferência e pelo mesmo motivo escrito lá:
   *"comando avulso se roda uma vez e envelhece; o portão re-confere a cada imagem
   construída"*. Ele confere a trava, a base das quatro modalidades e **três
   lances da partida do dono**, com nós, profundidade e consultas à base.

⛔ **A trava de identidade não afrouxa por o binário ser compilado na nuvem.** Quem
compila é o mesmo programa que roda na máquina do dono, e ele carimba o SHA-256
dos dezesseis arquivos de `lib/` dentro do executável; a abertura do processo
recalcula a partir do espelho e recusa se divergir.

**Ensaiado sem Docker** (a máquina do dono não o tem, conferido em 09/09/2026):
copiei o espelho para uma pasta limpa, rodei `dart pub get` **sem lock** e
compilei. O resumo saiu **idêntico** ao do binário do laboratório
(`a68628f014e20e11`), e o portão passou apontando para esse executável. ⚠️ O que o
ensaio não cobre é o alvo `linux/amd64` — isso só o build do Railway responde, e é
para isso que o portão está lá.

⚠️ **E o job continua podendo rodar na máquina do dono** (`rodar_job_local.py`),
que é a decisão de 16/09 e segue valendo por custo: ~15 min por dia gerado. A
diferença é que agora as duas portas funcionam, em vez de uma estar quebrada.

### O que AINDA falta

1. ⚠️ **Regerar a fila.** Nada do que está acima muda um desafio já gravado: a
   fila do `des` inteira saiu do adversário enfraquecido. O script de limpeza
   está em `ferramentas/consultas_sql/desafio_limpar_TUDO_DES.sql`.
2. ⚠️ **Medir o job de ponta a ponta com o motor novo.** Um candidato de damas com
   adversário Pita levou **287 s** (2,7 s de geração, 285 s de régua), o que dá
   ~15 min por dia. ⛔ O custo de um dia de `damas_sobreviver` (que já levou 17 min
   antes) não foi refeito.
3. ⚠️ **O `co_versao_motor` continua com prefixo `damas-py-`**, e agora ele é
   duplamente mentiroso: o espelho tem 16 `.dart` dentro e quem joga é o Dart.
   Trocar o prefixo é migração de dado, não só de código.
4. ⚠️ **O risco não medido da parte 2 continua aberto:** se o Dart no aparelho não
   cumprir 288 mil nós dentro dos 10 s num celular modesto, o relógio morde no
   app também, e dois aparelhos divergem pelo mesmo mecanismo.
