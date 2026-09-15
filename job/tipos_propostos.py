"""TIPOS NOVOS DE DESAFIO, PROPOSTOS AO DONO (RF-DES-128, T049).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO E UM ARQUIVO, E NAO UMA LISTA NUMA MENSAGEM
═══════════════════════════════════════════════════════════════════════════

O dono foi explicito em 03/09/2026:

    "eu espero na fase de implementacao que se proponha diversos outros tipos
    criativos de desafios para os 2 jogos. Nao pode ficar restrito a apenas os
    que estao na SPEC e PRD atuais"

⚠️ **Proposta em prosa nao se confere.** Escrita aqui, cada `js_chegada` passa
pelo **mesmo avaliador** que julgaria o desafio de verdade — e um teste prova
que ela e valida e que ⛔ **nao exige vocabulario novo**. E essa a diferenca
entre *"acho que da"* e *"esta pronto para o dono aprovar"*.

═══════════════════════════════════════════════════════════════════════════
✅ QUATRO JA SAIRAM DAQUI — PROMOVIDAS EM 14/09/2026
═══════════════════════════════════════════════════════════════════════════

| proposta                       | virou                          | onde esta |
|--------------------------------|--------------------------------|-----------|
| `pontinhos_nao_entregar_nada`  | `pontinhos_nao_entregar` (2)   | `tipos_de_desafio.py` |
| `pontinhos_troca_favoravel`    | o mesmo, numero 12             | idem |
| `pontinhos_economia_de_lances` | o mesmo, numero 14             | idem |
| `pontinhos_paciencia`          | o mesmo, numero 15             | idem |

⛔ **Promover e MOVER, e nao copiar.** Uma receita escrita em dois lugares seria
duas fontes da verdade para a mesma regra — o defeito que este projeto mais
persegue —, e ha tres cadeados em `test_tipos_propostos.py` que falham se uma
proposta aparecer tambem em `RECEITAS`. ⚠️ O codigo delas continua no Git: o que
esta tabela registra e **para onde** foram, que e a informacao que se perde.

⚠️ **As quatro foram MEDIDAS antes de subir** (3 dias x 20 tentativas): tres
deram FOLGA e uma APERTADO, com solucoes de 5,0 a 10,1 meios-lances. E duas delas
subiram **corrigidas**: a clausula de `lances_do_jogador` que a familia
*"impeca"/"aguente"* precisa foi descoberta medindo, e sem ela as duas eram
cumpridas no primeiro lance.

⛔ **`pontinhos_nao_entregar_nada` mudou de NOME ao subir** (`_nada` saiu): o tipo
2 ja existia na `tb901` desde a `0018` como `pontinhos_nao_entregar`, e era ele
que esperava por uma receita. ⚠️ Ele nao custou migracao nenhuma.

═══════════════════════════════════════════════════════════════════════════
⛔ AS QUE FICARAM NAO ESTAO EM `RECEITAS`, E ISSO E DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

Um tipo so vai ao ar quando tiver **as tres** coisas, e nenhuma delas e minha:

  1. **linha em `desafio.tb901_tipo_desafio`** — e migracao, e o `data-model.md`
     e o que o dono pre-validou. ⛔ Mudar o modelo e decisao dele;
  2. **chave de i18n nos tres `.arb`** — e a unica coisa que ainda exige versao
     nova do aplicativo (exercicio §8), e ela e trabalho do BLOCO 3;
  3. **vetor de verificacao** (RF-DES-198) — a prova de que Dart e Python leem a
     mesma regra.

Enquanto as tres nao existirem, importar daqui para `RECEITAS` publicaria um tipo
que o aplicativo mostraria como chave crua, e cairia na tela de atualizar.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CRITERIO QUE TODAS ELAS PASSAM: NENHUM VOCABULARIO NOVO
═══════════════════════════════════════════════════════════════════════════

Cada `js_chegada` daqui usa **so** o que os tres vocabularios fechados ja tem:

    janelas       partida · lances_do_jogador · turnos_do_jogador ·
                  turnos_do_adversario
    comparadores  maior_ou_igual · menor_ou_igual · igual · diferente · em ·
                  fora_de
    medidas       as chaves que os medidores dos dois jogos ja produzem

⚠️ **E isso e o que torna um tipo publicavel sem versao nova.** Um tipo que
precisasse de uma medida nova exigiria codigo no aparelho — e ai ele deixa de ser
dado e vira release, que e a fronteira que RF-DES-192 protege.

⛔ Nenhuma proposta usa `predicado`: os predicados sao funcoes **compiladas** no
aplicativo, e um predicado novo tambem seria release.
"""

from __future__ import annotations

from typing import Any, Mapping

from job.tipos_de_desafio import VERSAO_CHEGADA, Receita, _medida

#: A partir de que numero os tipos novos entrariam na dimensao.
#:
#: ⚠️ Os 10 primeiros ja existem na `0018`. ⛔ Estes numeros sao **sugestao**: quem
#: os fixa e a migracao que o dono aprovar, e ate la eles servem so para o
#: documento e para os testes nao colidirem.
PRIMEIRO_NUMERO_LIVRE = 11


# ═══════════════════════════════════════════════════════════════════════════
# PONTINHOS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ O tabuleiro e o **pequeno** (4x3 caixas, RF-DES-018d) — o unico que tem
# `.tflite`. Os numeros abaixo foram escolhidos para caber nele: sao 12 caixas no
# total, entao "feche 5" ja e quase metade.

PROPOSTAS_PONTINHOS: dict[str, Receita] = {
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_escada_em_um_turno": Receita(
        nu_tipo_desafio=13,
        co_tipo_desafio="pontinhos_escada_em_um_turno",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoEscadaEmUmTurno",
        # ⛔ **ESTE TIPO E DUPLICATA, POR DOIS CAMINHOS — 12/09/2026.**
        #
        # ⚠️ **Pela FORMA, ele e `pontinhos_fechar_caixas` com `turnos: 1`**:
        # mesma janela (`turnos_do_jogador`), mesma clausula
        # (`caixas_fechadas >= N`). E isso e parametro, nao tipo novo.
        #
        # ⚠️ **Pela INTENCAO, ele e `pontinhos_cadeia_longa`**, que ja publica
        # *"feche N caixas de uma vez"* com a forma certa:
        #
        #     janela: partida   clausula: maior_cadeia_capturada >= N
        #
        # ⛔ **E a forma daqui, alem de duplicada, nao funciona.** `turnos_do_jogador
        # n=1` limita a fita ao PRIMEIRO turno do jogador, e nele as caixas ainda
        # nao existem: medido, **zero candidatos** em 24 tentativas, com preparo 8
        # e 14, com o Sagaz e com o solucionador do arquiteto. Nenhum descarte por
        # recusa - simplesmente nao ha solucao dentro de um turno.
        #
        # ⚠️ **A licao nao e sobre este tipo:** `maior_cadeia_capturada` e uma
        # MEDIDA que ja diz "de uma vez so", e por isso o `cadeia_longa` nao
        # precisa de janela apertada nenhuma. Quando a medida certa existe, a
        # janela nao e o lugar de exprimir a tarefa.
        #
        # ⛔ **Nao e apagado** (nada e apagado neste projeto), mas nao entra em
        # `EM_AVALIACAO`: medi-lo seria pagar horas de maquina por uma linha que
        # ja se sabe como sai.
        #
        # ⚠️ `n = 1` e o caso extremo da janela de turnos, e ele **so faz sentido
        # no Pontinhos**: quem fecha caixa joga de novo, entao um turno pode ter
        # muitos lances. Nas damas, `turnos_do_jogador n=1` seria um lance so.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_jogador", "n": 1},
            "clausulas": [
                _medida("caixas_fechadas", "maior_ou_igual", p["caixas"])
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "personagem": personagem,
        },
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# DAMAS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ `material_restante` e `material_do_adversario` contam **pecas**, e nao
# pontos: uma dama vale uma. Os numeros abaixo assumem finais e meios-jogos
# pequenos, que e o que os moldes produzem.

PROPOSTAS_DAMAS: dict[str, Receita] = {
    # ─────────────────────────────────────────────────────────────────────────
    # ⚠️ **OS DOIS PRIMEIROS NAO PRECISAM DE MIGRACAO** — e isso os separa dos
    # outros seis. Os numeros 5 e 9 ja estao em `desafio.tb901_tipo_desafio`
    # desde a `0018`; como o tipo 2 do Pontinhos, eles esperam por uma receita.
    #
    # ⛔ **E eles entraram aqui por correcao do dono** (14/09/2026, §8k-12):
    # *"Por que estamos deixando o sacrificio e sobreviver de fora? Eu nao decidi
    # isso. Minha decisao e que deveriamos ter a maior variedade possivel de
    # desafios, que eles sejam resolviveis, nao se repitam."*
    # ─────────────────────────────────────────────────────────────────────────
    "damas_sacrificio": Receita(
        nu_tipo_desafio=5,
        co_tipo_desafio="damas_sacrificio",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoSacrificio",
        # ⚠️ **AS DUAS CLAUSULAS SAO O TIPO, E NENHUMA DELAS SOZINHA E.**
        #
        #   `material_do_adversario <= A - capturar`  →  voce comeu N dele
        #   `material_restante      <= M - entregar`  →  e deu pelo menos uma
        #
        # ⛔ A primeira sozinha e `damas_capturar_multipla`, que esta no ar desde
        # 12/09/2026. E a segunda que diz *"e voce chegou la com menos pecas do
        # que comecou"* — e e ela que faz o sacrificio ser sacrificio.
        #
        # ⚠️ **Por que nao `capturas_extras`,** que era o desenho da primeira
        # versao deste plano: `capturas_extras` conta `capturas - 1` **por lance**,
        # entao `>= 2` tanto casa com uma cadeia tripla quanto com duas cadeias
        # duplas — que somam **quatro** pecas, e nao tres. A frase diria 3 e o
        # juiz aceitaria 4. ⛔ `material_do_adversario` conta o que sumiu do
        # tabuleiro, que e exatamente o que a frase promete.
        #
        # ⚠️ **A conjuncao nao tem ORDEM, e a frase respeita isso.** O juiz para
        # no primeiro lance em que as duas valem, sem perguntar qual veio antes;
        # entao o enunciado fala de **saldo** (*"troque 1 por 3"*) e nao de
        # sequencia (*"entregue e depois capture"*), que seria uma promessa que o
        # vocabulario fechado nao sabe cobrar.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("material_do_adversario", "menor_ou_igual", p["resta_ao_adversario"]),
                _medida("material_restante", "menor_ou_igual", p["resta_a_voce"]),
            ],
        },
        # ⚠️ A frase le os numeros **relativos** (`capturar`/`entregar`), e a
        # clausula le os absolutos. Os dois convivem no mesmo dicionario porque
        # `editorial.parametros_efetivos` acrescenta sem apagar.
        valores_da_frase=lambda p, personagem: {
            "capturar": p["capturar"],
            "entregar": p["entregar"],
            "personagem": personagem,
        },
        # ⛔ **Sementes MEDIDAS, e nao acervo.** Sao duas posicoes que a cacada
        # sintetica aprovou em 14/09/2026 — ⚠️ nenhuma FEN aqui foi escrita a
        # mao, pela regra de sempre: molde nao se inventa, molde se mede.
        #
        # ⚠️ **Duas nao fazem um rodizio.** O acervo de verdade sai da pescaria em
        # partidas reais, que e o que deu 515 moldes ao `coroar` e 184 a captura:
        #
        #     .venv\\Scripts\\python -u scripts\\pescar_moldes_de_partidas.py ^
        #         fens_reais.json --tipo damas_sacrificio --minimo-pecas 12 ^
        #         --processos 14 --bloco
        #
        # O comentario de cada linha e `modalidades validas/4 · lance medio`.
        moldes=(
            "W:W11,22,28,30,31:B2,6,17,20,23,25",   # 3/4 · lance 7.0
            "W:W10,21,23,29,30:B3,6,19,22,26,27",   # 3/4 · lance 5.0
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_sobreviver": Receita(
        nu_tipo_desafio=9,
        co_tipo_desafio="damas_sobreviver",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoSobreviver",
        # ⛔ **A CLAUSULA DE `lances_do_jogador` E OBRIGATORIA, E FOI DESCOBERTA
        # MEDINDO** (§8k-10, 13/09/2026). A janela e um **teto**, nunca um piso:
        # o juiz varre a fita e para no primeiro lance em que a conjuncao vale, e
        # `material_restante >= 1` ja e verdade antes de a pessoa jogar. Sem o
        # piso, *"resista 8 lances"* sairia cumprido em **um meio-lance**.
        #
        # ⚠️ **E `material_restante >= 1` nao e enfeite**: e ele que diz *"sem
        # perder"*. Nas damas ficar sem pecas e derrota, entao a clausula e a
        # traducao literal de "voce ainda esta de pe".
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("lances_do_jogador", "maior_ou_igual", p["lances"]),
                _medida("material_restante", "maior_ou_igual", 1),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "personagem": personagem,
        },
        # ⚠️ **A pescaria deste procura o CONTRARIO das outras**: posicoes em que
        # quem joga esta em desvantagem material e ainda assim segura. Todas as
        # pescarias ate hoje procuraram vantagem, e o filtro e escrito do zero.
        #
        # ⛔ **E ha um segundo risco ja identificado**: o solucionador e o Sagaz, e
        # ele busca **vencer**, nao resistir. Numa posicao perdida os dois
        # costumam coincidir, mas isso e hipotese, nao medida.
        #
        # ⛔ **A DESVANTAGEM NAO PODE SER GRANDE — e as duas primeiras sementes
        # escritas a mao estavam erradas por isso.** Duas brancas contra quatro
        # pretas nao resistem: perdem antes do oitavo lance, e o gerador devolve
        # **zero candidato** (medido em 14/09/2026, com o teto ja corrigido para
        # 18 meios-lances). As quatro abaixo sairam da cacada, com 5 ou 6 pecas
        # contra 6 a 8.
        #
        # ⚠️ **Todas caem no lance 15**, e isso nao e coincidencia: e o piso
        # aritmetico de `lances_do_jogador >= 8` quando os dois lados alternam.
        # ⛔ Neste tipo o "comprimento da solucao" nao mede dificuldade nenhuma —
        # quem mede e a regua dos mascotes.
        moldes=(
            "W:W21,26,30,31,32:B5,7,10,11,14,16,22,24",   # 4/4 · lance 15.0
            "W:W24,26,29,32:B5,9,10,11,14,17",   # 4/4 · lance 15.0
            "W:W22,24,28,29,30,32:B6,9,10,12,13,14,15,19",   # 4/4 · lance 15.0
            "W:W21,22,27,29:B5,9,10,13,14,20",   # 4/4 · lance 15.0
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_armadilha": Receita(
        nu_tipo_desafio=16,
        co_tipo_desafio="damas_armadilha",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoArmadilha",
        # ⚠️ **A janela e do adversario, e a medida e sua** — e essa combinacao e
        # o que descreve uma armadilha: nos proximos N turnos dele, voce nao
        # perde nada. Nas damas a captura e **obrigatoria**, entao "nao perder
        # peca" quer dizer "nao deixar captura disponivel".
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            # ⛔ Mesma correcao de 12/09/2026 dos tipos 11 e 15: `material_restante
            # >= pecas` ja e verdade na posicao inicial, e sem a clausula de
            # `lances_do_jogador` o juiz cumpria o desafio no primeiro lance.
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("lances_do_jogador", "maior_ou_igual", p["turnos"]),
                _medida("material_restante", "maior_ou_igual", p["pecas"]),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "turnos": p["turnos"],
            "personagem": personagem,
        },
        moldes=(
            "W:W21,22,27:B10,11,15",
            "W:W23,24,28:B12,13,16",
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_dupla_coroacao": Receita(
        nu_tipo_desafio=17,
        co_tipo_desafio="damas_dupla_coroacao",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoDuplaCoroacao",
        # ⚠️ Duas damas, e nao uma: o tipo 6 (`damas_coroar`) ja existe, e a
        # graca deste e que coroar a segunda **atrapalha** a primeira — a dama
        # recem-feita vira alvo enquanto a outra atravessa.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [
                _medida("damas_coroadas", "maior_ou_igual", 2)
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "personagem": personagem,
        },
        moldes=(
            "W:W9,10,23,27:B5,6,12,20",
            "W:W13,14,25,30:B7,8,17,22",
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_limpeza": Receita(
        nu_tipo_desafio=18,
        co_tipo_desafio="damas_limpeza",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoLimpeza",
        # ⚠️ A medida e o **material do adversario**, e nao as suas capturas: sao
        # coisas diferentes quando ele tambem captura. Contar as suas capturas
        # premiaria quem come tres e perde quatro.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [
                _medida("material_do_adversario", "menor_ou_igual", p["restam"])
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "restam": p["restam"],
            "personagem": personagem,
        },
        moldes=(
            "W:W19,23,27,28:B10,11,14,15",
            "W:W20,24,29,30:B9,12,13,16",
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_troca_favoravel": Receita(
        nu_tipo_desafio=19,
        co_tipo_desafio="damas_troca_favoravel",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoTrocaFavoravelDamas",
        # ⚠️ **O sacrificio ao contrario.** O tipo 5 (`damas_sacrificio`) pede que
        # voce **de** para comer mais; este pede que voce **nao de** enquanto
        # come. Sao duas licoes opostas sobre a mesma mecanica, e por isso valem
        # como dois tipos.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("capturas_extras", "maior_ou_igual", p["comer"]),
                _medida("material_restante", "maior_ou_igual", p["pecas"]),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "comer": p["comer"],
            "personagem": personagem,
        },
        moldes=(
            "W:W22,26,31:B11,12,18",
            "W:W21,25,29:B9,10,17",
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_vitoria_relampago": Receita(
        nu_tipo_desafio=20,
        co_tipo_desafio="damas_vitoria_relampago",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoVitoriaRelampago",
        # ⚠️ `vitoria` e um **marco** (`1` ou `0`), e nao uma contagem — por isso
        # o comparador e `igual` e o valor e `1`. Um `maior_ou_igual` funcionaria
        # e leria pior: nao ha "duas vitorias".
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("vitoria", "igual", 1)],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "personagem": personagem,
        },
        moldes=(
            "W:W26,27,30:B18",
            "W:W23,24,28:B14",
        ),
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "damas_empate_honroso": Receita(
        nu_tipo_desafio=21,
        co_tipo_desafio="damas_empate_honroso",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoEmpateHonroso",
        # ⚠️ **O unico tipo em que empatar e vencer**, e ele so faz sentido
        # contra os mascotes fortes: a posicao inicial e perdida, e segurar o
        # empate e a proeza. ⛔ Contra a Cacau ele seria banal — e e por isso que
        # RF-DES-202 amarra objetivo e personagem.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [_medida("empate", "igual", 1)],
        },
        valores_da_frase=lambda p, personagem: {"personagem": personagem},
        moldes=(
            "W:W31:B10,15",
            "W:W28:B12,19",
        ),
    ),
}


#: Todas as propostas, num lugar so.
#: As propostas que ja SUBIRAM para `RECEITAS`, e o nome com que subiram.
#:
#: ⚠️ **Elas saem de `PROPOSTAS` ao subir** (promover e mover, nao copiar), e
#: e por isso que esta lista existe: sem ela, o cadeado do RF-DES-128 — *"ha
#: propostas para os DOIS jogos"* — contaria menos propostas a cada promocao e
#: acabaria falhando **por sucesso**, que e o pior jeito de um teste falhar.
PROMOVIDAS: dict[str, str] = {
    "pontinhos_nao_entregar_nada": "pontinhos_nao_entregar",
    "pontinhos_troca_favoravel": "pontinhos_troca_favoravel",
    "pontinhos_economia_de_lances": "pontinhos_economia_de_lances",
    "pontinhos_paciencia": "pontinhos_paciencia",
}

PROPOSTAS: dict[str, Receita] = {**PROPOSTAS_PONTINHOS, **PROPOSTAS_DAMAS}


#: Os parametros de exemplo de cada proposta — o que a receita recebe.
#:
#: ⚠️ Eles existem para o **teste** poder montar cada `js_chegada` e para o
#: documento mostrar a linha como ela ficaria gravada. ⛔ Nao sao a calibracao:
#: quem escolhe os numeros do dia e o gerador, contra a regua dos mascotes.
PARAMETROS_DE_EXEMPLO: Mapping[str, dict[str, Any]] = {
    "pontinhos_escada_em_um_turno": {"caixas": 4},
    # ⚠️ **Estes dois sao RELATIVOS**, e por isso passam por
    # `editorial.parametros_efetivos` antes de chegar a receita: o que `montar`
    # recebe e `resta_ao_adversario`/`resta_a_voce`, calculados na posicao.
    "damas_sacrificio": {"capturar": 3, "entregar": 1},
    "damas_sobreviver": {"lances": 8},
    "damas_armadilha": {"turnos": 2, "pecas": 3},
    "damas_dupla_coroacao": {"lances": 8},
    "damas_limpeza": {"lances": 5, "restam": 1},
    "damas_troca_favoravel": {"comer": 2, "pecas": 3},
    "damas_vitoria_relampago": {"lances": 4},
    "damas_empate_honroso": {},
}
