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
⛔ ELAS NAO ESTAO EM `RECEITAS`, E ISSO E DE PROPOSITO
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
    "pontinhos_nao_entregar_nada": Receita(
        nu_tipo_desafio=11,
        co_tipo_desafio="pontinhos_nao_entregar_nada",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoNaoEntregarNada",
        # ⚠️ **A janela e do ADVERSARIO**, e e essa a ideia do tipo: o objetivo
        # nao e o que voce faz, e o que voce **impede**. E o unico dos dez tipos
        # atuais que usaria `turnos_do_adversario` — a janela existe no
        # vocabulario desde o inicio e nunca foi usada.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_adversario", "n": p["turnos"]},
            "clausulas": [
                _medida("caixas_do_adversario", "menor_ou_igual", 0)
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "turnos": p["turnos"],
            "personagem": personagem,
        },
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_troca_favoravel": Receita(
        nu_tipo_desafio=12,
        co_tipo_desafio="pontinhos_troca_favoravel",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoTrocaFavoravel",
        # ⚠️ **DUAS clausulas**, e e a primeira proposta a usar isso. A conjuncao
        # ja existe no formato desde T028 e nenhum tipo atual a exercita — e ela
        # e o que transforma "feche caixas" em "feche caixas **sem** entregar",
        # que e a decisao real do Pontinhos.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("caixas_fechadas", "maior_ou_igual", p["ganhar"]),
                _medida("caixas_do_adversario", "menor_ou_igual", p["ceder"]),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "ganhar": p["ganhar"],
            "ceder": p["ceder"],
            "personagem": personagem,
        },
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_escada_em_um_turno": Receita(
        nu_tipo_desafio=13,
        co_tipo_desafio="pontinhos_escada_em_um_turno",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoEscadaEmUmTurno",
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
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_economia_de_lances": Receita(
        nu_tipo_desafio=14,
        co_tipo_desafio="pontinhos_economia_de_lances",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoEconomiaDeLances",
        # ⚠️ Janela de **lances**, e nao de turnos: aqui o aperto e justamente
        # nao poder gastar lance nenhum a toa. O contraste com o tipo 13 e o que
        # ensina a diferenca entre lance e turno a quem joga.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [
                _medida("caixas_fechadas", "maior_ou_igual", p["caixas"])
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_cadeia_longa": Receita(
        nu_tipo_desafio=22,
        co_tipo_desafio="pontinhos_cadeia_longa",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoCadeiaLonga",
        # ── ⚠️ A IDEIA E DO DONO, 12/09/2026 ────────────────────────────────
        #
        # > *"Deixa o usuario conectar tracos de tal forma que consiga montar uma
        # > cadeia extremamente longa, e depois captura-la, ao inves do
        # > adversario. Ao inves de quebrar o tabuleiro em varias cadeias
        # > pequenas, formar cadeias longas."*
        #
        # A frase: *"Capture N ou mais caixas em sequencia"*, com N grande.
        #
        # ── ⛔ POR QUE NAO E O TIPO 13, QUE PARECE O MESMO ──────────────────
        #
        # `pontinhos_escada_em_um_turno` usa `turnos_do_jogador n=1` com
        # `caixas_fechadas`, e um turno **e** uma corrida de lances seguidos —
        # entao ele parece medir a mesma coisa. ⚠️ **Mas a janela e o PRIMEIRO
        # turno**, e este desafio precisa dos turnos anteriores: e neles que a
        # pessoa constroi a cadeia. Com `n=1` o desafio seria *"ja chegue
        # capturando"*, que e o oposto do que o dono descreveu.
        #
        # Por isso a janela aqui e a **partida** e a medida e outra: a pergunta
        # e *"em ALGUM momento voce capturou N seguidas?"*.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("maior_cadeia_capturada", "maior_ou_igual", p["caixas"])
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "personagem": personagem,
        },
    ),
    # ─────────────────────────────────────────────────────────────────────────
    "pontinhos_paciencia": Receita(
        nu_tipo_desafio=15,
        co_tipo_desafio="pontinhos_paciencia",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoPaciencia",
        # ⚠️ **O objetivo e nao fazer nada** — nem fechar, nem entregar. E o tipo
        # mais contraintuitivo do catalogo, e ensina a regra central do Pontinhos:
        # quem e forcado a abrir uma cadeia perde. ⛔ Ele **precisa** das duas
        # clausulas: so "nao entregue" seria cumprido por quem fechasse tudo.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_jogador", "n": p["turnos"]},
            "clausulas": [
                _medida("caixas_do_adversario", "menor_ou_igual", 0),
                _medida("caixas_fechadas", "igual", 0),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "turnos": p["turnos"],
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
            "janela": {"tipo": "turnos_do_adversario", "n": p["turnos"]},
            "clausulas": [
                _medida("material_restante", "maior_ou_igual", p["pecas"])
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
PROPOSTAS: dict[str, Receita] = {**PROPOSTAS_PONTINHOS, **PROPOSTAS_DAMAS}


#: Os parametros de exemplo de cada proposta — o que a receita recebe.
#:
#: ⚠️ Eles existem para o **teste** poder montar cada `js_chegada` e para o
#: documento mostrar a linha como ela ficaria gravada. ⛔ Nao sao a calibracao:
#: quem escolhe os numeros do dia e o gerador, contra a regua dos mascotes.
PARAMETROS_DE_EXEMPLO: Mapping[str, dict[str, Any]] = {
    "pontinhos_nao_entregar_nada": {"turnos": 3},
    "pontinhos_troca_favoravel": {"ganhar": 4, "ceder": 1},
    "pontinhos_escada_em_um_turno": {"caixas": 4},
    "pontinhos_economia_de_lances": {"caixas": 3, "lances": 5},
    "pontinhos_paciencia": {"turnos": 2},
    # ⚠️ **Seis, e nao quatro.** Medido em 12/09/2026: contra a Cacau, quem joga
    # para vencer (a CNN no nivel Magno) chega a seis caixas seguidas em **7%**
    # das posicoes; quem joga para a cadeia, em 43%. Com quatro o desafio sairia
    # cumprido por acidente.
    "pontinhos_cadeia_longa": {"caixas": 6},
    "damas_armadilha": {"turnos": 2, "pecas": 3},
    "damas_dupla_coroacao": {"lances": 8},
    "damas_limpeza": {"lances": 5, "restam": 1},
    "damas_troca_favoravel": {"comer": 2, "pecas": 3},
    "damas_vitoria_relampago": {"lances": 4},
    "damas_empate_honroso": {},
}
