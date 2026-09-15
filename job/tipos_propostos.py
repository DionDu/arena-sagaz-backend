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
        # ✅ **ACERVO PESCADO EM PARTIDAS REAIS DO `des`, 15/09/2026.** As duas
        # sementes sinteticas de 14/09 sairam inteiras: elas serviram para provar
        # que o tipo gera, e o acervo de verdade as substituiu.
        #
        # O funil, de 1.777 posicoes unicas:
        #
        #     1.205  passaram o filtro de material (12+ pecas)
        #       752  nunca cumpriram dentro do teto
        #        34  partida ja acabada
        #         4  material insuficiente para o pedido (⚠️ a recusa nova)
        #       415  passaram a peneira
        #       203  serviram a tres ou mais modalidades (124 servem as quatro)
        #
        # ⚠️ **O rendimento e MUITO melhor que o do `capturar_multipla`:** 415 de
        # 1.205 na peneira, contra 408 de 4.090. Posicoes de sacrificio sao
        # comuns nas partidas reais — o que e raro e alguem **ver** o sacrificio.
        #
        # ✅ **E a distribuicao saiu invertida, a favor:** onde a captura multipla
        # tinha 97 dos 184 moldes caindo em 3 lances, aqui o grupo maior e o de
        # **8 lances**. Distancia ate o objetivo, nos 203 pescados:
        #
        #     3 lances: 12 · 4: 9 · 5: 26 · 6: 29 · 7: 32 · 8: 46 · 9: 21 ·
        #     10 lances: 19 · 11: 9
        #
        # ⛔ **E SO OS 188 DE 4 LANCES OU MAIS ENTRARAM**, pelo mesmo criterio que
        # o dono fixou para a captura multipla em 12/09/2026: um molde curto no
        # meio do acervo publica, de vez em quando, o desafio de um toque.
        # ⚠️ Os 12 curtos **nao foram apagados** — saem do diario a qualquer
        # momento (`pescaria_damas_sacrificio.jsonl`).
        #
        # ⚠️ **Como refazer** (o diario permite interromper e retomar):
        #
        #     .venv\\Scripts\\python -u scripts\\pescar_moldes_de_partidas.py ^
        #         fens_damas_des.json --tipo damas_sacrificio --minimo-pecas 12 ^
        #         --processos 14 --bloco
        #
        # O comentario de cada linha e `modalidades validas/4 · lance medio`.
        moldes=(
            "W:W21,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,10,12,13,22",   # 4/4 · lance 11.0
            "W:W20,21,22,23,25,26,29,30,32:B1,2,3,4,5,7,10,11,14,19",   # 4/4 · lance 11.0
            "W:W18,19,20,21,26,28,29:B1,4,7,10,11,12,13",   # 4/4 · lance 11.0
            "W:W17,20,21,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,14,19",   # 4/4 · lance 11.0
            "W:W14,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,12,13,23",   # 4/4 · lance 11.0
            "W:W13,21,22,23,27,28,29,30,32:B4,5,8,9,10,11,15,20",   # 4/4 · lance 11.0
            "W:W20,21,22,25,26,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,11,23",   # 4/4 · lance 10.5
            "W:W21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,12,14,15",   # 4/4 · lance 10.0
            "W:W19,20,21,22,23,25,26,28,29,30,31,32:B1,2,3,4,5,7,8,9,10,12,13,16",   # 4/4 · lance 10.0
            "W:W18,21,22,23,24,26,27,28,29,30,32:B1,3,4,5,8,9,10,11,12,13,14",   # 4/4 · lance 10.0
            "W:W17,18,21,24,28,29,30,31,32:B2,3,4,5,7,8,11,12,14",   # 4/4 · lance 10.0
            "W:WK1,18,20,24,26,29,32:B4,11,12,13,16,21",   # 4/4 · lance 9.5
            "W:W9,17,21,22,25,28,29,30,31,32:B4,11,12,20,27",   # 4/4 · lance 9.5
            "W:W21,24,25,26,27,28,29,30,32:B2,3,4,6,7,8,11,13,14,19",   # 4/4 · lance 9.5
            "W:W21,22,23,24,25,27,28,29,31,32:B2,3,4,7,8,10,11,12,13,17",   # 4/4 · lance 9.5
            "W:W18,19,21,24,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,11,12,15",   # 4/4 · lance 9.5
            "W:W12,17,19,24,25,27,28,31:B3,4,10,11,18,20",   # 4/4 · lance 9.5
            "W:W21,23,24,27,28,29,30,32:B2,3,4,8,11,12,14,17",   # 4/4 · lance 9.0
            "W:W21,23,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,11,12,13,17",   # 4/4 · lance 9.0
            "W:W21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,11,12,13,19",   # 4/4 · lance 9.0
            "W:W21,22,23,24,25,26,29,30,32:B1,2,4,5,6,10,13,14,18",   # 4/4 · lance 9.0
            "W:W20,21,22,25,26,27,28,29,31,32:B1,2,3,4,5,6,8,9,10,12,24",   # 4/4 · lance 9.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,14,15",   # 4/4 · lance 9.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,10,12,19",   # 4/4 · lance 9.0
            "W:W19,20,22,25,26,27,29,30,31:B1,3,4,5,6,7,8,12,18",   # 4/4 · lance 9.0
            "W:W18,20,21,23,27,28,29,30,31,32:B2,3,4,5,7,8,9,10,12,16",   # 4/4 · lance 9.0
            "W:W18,19,21,23,25,26,28,29,30,31,32:B1,3,4,5,7,8,10,11,12,13,14",   # 4/4 · lance 9.0
            "W:W18,19,20,21,22,23,26,27,29,30,31:B1,4,5,6,7,8,9,11,12,14,15",   # 4/4 · lance 9.0
            "W:W13,16,19,21,24,25,29,30:B1,4,5,6,7,12,14",   # 4/4 · lance 9.0
            "W:WK3,K13,18,20,21,23,27,28,29,30,31,32:B4,5,8,12,16",   # 4/4 · lance 8.5
            "W:WK1,20,26,27,28,29,32:B3,4,6,10,11,12,18",   # 4/4 · lance 8.5
            "W:W20,21,23,24,25,26,28,29,30,31,32:B1,2,3,4,5,7,8,10,11,12,14,22",   # 4/4 · lance 8.5
            "W:W19,21,22,23,24,25,28,29,30,31,32:B1,2,3,4,5,7,11,12,13,15,16",   # 4/4 · lance 8.5
            "W:W19,21,22,23,24,25,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,12,14,15",   # 4/4 · lance 8.5
            "W:W13,18,20,21,22,23,28,29:B3,4,9,10,11,14,15",   # 4/4 · lance 8.5
            "W:WK1,20,27,28,29,31,32:B3,4,6,8,10,12,18",   # 4/4 · lance 8.0
            "W:W7,20,21,22,25,26,27,28,29,30,31:B1,3,4,5,6,9,10,11,13,14",   # 4/4 · lance 8.0
            "W:W21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,12,15,23",   # 4/4 · lance 8.0
            "W:W20,21,23,24,25,26,28,29,31:B1,3,4,5,6,8,10,14,22",   # 4/4 · lance 8.0
            "W:W19,21,22,23,24,26,27,28,29,30,32:B2,3,4,6,7,8,10,12,13,14,15",   # 4/4 · lance 8.0
            "W:W19,20,21,23,24,K26,28,29,31:B4,5,8,12,13",   # 4/4 · lance 8.0
            "W:W19,20,21,22,23,25,27,28,29,32:B2,4,5,9,10,12,13,14,15,16",   # 4/4 · lance 8.0
            "W:W18,21,23,24,25,26,27,28,29,31,32:B2,3,4,5,7,8,10,11,12,13,14",   # 4/4 · lance 8.0
            "W:W18,21,22,23,24,25,26,27,28,29,32:B1,3,4,5,8,9,11,12,13,14,15",   # 4/4 · lance 8.0
            "W:W18,20,21,22,24,25,27,29:B4,5,9,10,11,13,15",   # 4/4 · lance 8.0
            "W:W18,19,20,23,25,26,27,29,30,31:B1,3,4,5,6,7,9,11,12,17",   # 4/4 · lance 8.0
            "W:W15,19,22,23,24,27,28,29,30,32:B3,4,5,6,8,9,12,13,14,16,21",   # 4/4 · lance 8.0
            "W:W12,19,20,21,22,24,25,28,29,31,32:B1,3,4,5,7,8,10,11,13,15",   # 4/4 · lance 8.0
            "W:WK2,17,18,19,21,22,24,25,28,29,32:B4,5,6,8,9,12,13,14,15",   # 4/4 · lance 7.5
            "W:W21,22,23,24,26,27,28,29,30,32:B2,3,4,6,7,8,10,13,14,15,19",   # 4/4 · lance 7.5
            "W:W20,21,22,23,25,26,28,29,30,31,32:B1,2,3,4,5,7,8,9,10,12,14,24",   # 4/4 · lance 7.5
            "W:W20,21,22,23,24,25,26,28,29,30,31:B1,2,3,4,5,6,8,10,12,13,15",   # 4/4 · lance 7.5
            "W:W15,K19,21,22,28,29,30,31:B4,7,8,16,20",   # 4/4 · lance 7.5
            "W:W15,21,23,24,29,30,31,32:B2,4,7,8,12,13,16,17",   # 4/4 · lance 7.5
            "W:W12,K13,17,20,21,24,27,28,29,30:B3,4,5,16",   # 4/4 · lance 7.5
            "W:WK2,21,25,28,29,31:B1,3,4,5,12,13,23",   # 4/4 · lance 7.0
            "W:W21,22,24,25,27,29:B5,9,11,13,14,20",   # 4/4 · lance 7.0
            "W:W21,22,23,25,28,29,30,31:B2,3,4,6,7,8,9,18,20",   # 4/4 · lance 7.0
            "W:W21,22,23,25,27,29,30:B1,2,4,5,6,13,18,K32",   # 4/4 · lance 7.0
            "W:W20,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,15,23",   # 4/4 · lance 7.0
            "W:W20,21,22,23,25,26,29,30,31:B1,2,4,5,6,8,9,10,11,19",   # 4/4 · lance 7.0
            "W:W20,21,22,23,25,26,28,29,30,32:B1,2,3,4,5,7,8,10,12,14,24",   # 4/4 · lance 7.0
            "W:W19,20,21,25,29,30,31:B1,2,3,4,5,9,10,12,15,22",   # 4/4 · lance 7.0
            "W:W19,20,21,25,26,27,28,29,30,31,32:B1,2,3,4,7,8,9,10,12,13,16",   # 4/4 · lance 7.0
            "W:W19,20,21,22,23,24,25,28,29,30,32:B1,4,5,6,7,8,9,10,11,12,15",   # 4/4 · lance 7.0
            "W:W18,21,22,24,25,27,29:B4,5,9,10,13,15,20",   # 4/4 · lance 7.0
            "W:W18,19,26,28,29,30,31,32:B4,5,8,10,11,12,13,21",   # 4/4 · lance 7.0
            "W:W18,19,20,21,23,25,26,27,29,30,31:B1,3,4,5,6,7,9,10,11,12,17",   # 4/4 · lance 7.0
            "W:W17,18,20,21,22,23,24,25,28,29,32:B4,5,6,7,8,9,10,11,12,13,15",   # 4/4 · lance 7.0
            "W:W16,K19,21,23,24,26,28,29,31:B4,7,12",   # 4/4 · lance 7.0
            "W:W16,21,22,24,26,27,28,29,30,32:B2,3,4,6,7,8,10,13,14,18",   # 4/4 · lance 7.0
            "W:W16,20,21,22,25,26,28,29,30,32:B1,2,3,4,6,8,9,10,12,18,24",   # 4/4 · lance 7.0
            "W:W15,19,20,21,24,26,29,31:B3,4,9,11,12,14,17",   # 4/4 · lance 7.0
            "W:W12,13,19,21,24,25,26,27,28,29:B1,4,5,6,9,10,14,15,18,20",   # 4/4 · lance 7.0
            "W:W19,20,21,24,26,28,29,30,32:B2,4,5,8,11,12,13,14,15",   # 4/4 · lance 6.5
            "W:W19,20,21,22,23,25,26,27,28,29,30,31:B1,3,4,5,6,8,9,10,11,12,13,14",   # 4/4 · lance 6.5
            "W:W18,21,22,23,24,25,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,15,16",   # 4/4 · lance 6.5
            "W:W18,20,22,23,25,26,27,28,29,30:B2,4,5,6,8,9,11,12,14,17,21",   # 4/4 · lance 6.5
            "W:W17,19,21,25,26,29,30,31:B2,3,4,6,9,10,12,14",   # 4/4 · lance 6.5
            "W:WK3,17,20,21,22,25,27,29,30,32:B1,4,5,6,7,9,10,15,23",   # 4/4 · lance 6.0
            "W:W20,21,23,25,29,31:B4,6,8,10,11,14,22",   # 4/4 · lance 6.0
            "W:W20,21,22,23,25,26,28,29,30,31:B1,2,4,5,6,7,8,9,10,12,24",   # 4/4 · lance 6.0
            "W:W19,20,23,25,26,27,29,30,31:B1,3,4,5,6,7,9,12,17,18",   # 4/4 · lance 6.0
            "W:W19,20,21,22,23,25,26,27,29,30,31:B1,3,4,5,6,7,9,10,11,12,14",   # 4/4 · lance 6.0
            "W:W18,20,21,23,25,27,28,29,30,31,32:B2,3,4,5,7,8,9,10,12,13,16",   # 4/4 · lance 6.0
            "W:W18,19,20,22,23,26,27,29,30,31:B1,4,5,6,7,8,9,11,12,17",   # 4/4 · lance 6.0
            "W:W17,18,19,20,21,22,24,25,28,29,32:B4,5,6,7,8,9,10,12,13,15,16",   # 4/4 · lance 6.0
            "W:W20,21,23,24,25,26,28,29,30,31:B1,2,3,4,5,6,8,10,12,15,22",   # 4/4 · lance 5.5
            "W:W19,21,22,23,24,25,28,29,30,31,32:B1,2,3,4,7,8,10,11,13,14,16",   # 4/4 · lance 5.5
            "W:W17,20,21,25,29,31:B1,2,3,4,9,10,18,26",   # 4/4 · lance 5.5
            "W:WK2,K3,18,20,21,23,27,28,29,30,31,32:B4,5,6,8,11,12",   # 4/4 · lance 5.0
            "W:WK2,18,19,20,21,23,27,28,29,30,31,32:B1,4,5,7,8,11,12,15",   # 4/4 · lance 5.0
            "W:WK1,K2,18,19,21,22,24,25,28,29,32:B4,5,8,12,13,14,15",   # 4/4 · lance 5.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,14,16",   # 4/4 · lance 5.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,11,12,18",   # 4/4 · lance 5.0
            "W:W19,21,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,11,12,22",   # 4/4 · lance 5.0
            "W:W19,20,23,27,28,29,31,32:B1,3,4,7,8,9,10,12,18",   # 4/4 · lance 5.0
            "W:W19,20,21,22,25,26,27,29,30,31:B1,3,4,5,6,7,8,9,12,17",   # 4/4 · lance 5.0
            "W:W19,20,21,22,23,25,26,29,30,31,32:B1,2,3,4,5,7,8,9,10,12,17",   # 4/4 · lance 5.0
            "W:W18,21,22,24,25,27,28,29,30,31,32:B1,2,3,4,5,7,8,12,13,15,16",   # 4/4 · lance 5.0
            "W:W18,20,21,22,23,25,26,27,28,29,32:B1,3,4,5,8,9,11,12,13,15,17",   # 4/4 · lance 5.0
            "W:W18,19,20,23,27,28,29,31,32:B1,3,4,7,8,9,10,11,12",   # 4/4 · lance 5.0
            "W:W18,19,20,21,22,24,25,28,29,30,32:B1,4,5,6,7,8,10,11,12,13,15",   # 4/4 · lance 5.0
            "W:W18,19,20,21,22,23,27,28,29,30,31,32:B1,3,4,5,6,7,10,11,12,14",   # 4/4 · lance 5.0
            "W:W18,19,20,21,22,23,26,27,29,30,31:B1,4,5,6,7,8,9,10,11,12,17",   # 4/4 · lance 5.0
            "W:W15,16,19,21,24,26,29,31:B3,4,11,12,13,14,17",   # 4/4 · lance 5.0
            "W:W14,15,21,23,29,31:B6,9,12,16,17,22",   # 4/4 · lance 5.0
            "W:W13,18,20,23,26,27,29,30,31:B1,4,5,6,8,9,10,11,19",   # 4/4 · lance 5.0
            "W:W12,19,20,21,22,24,25,27,28,29,31:B3,4,5,6,7,8,10,11,13,15",   # 4/4 · lance 5.0
            "W:WK1,18,21,22,28,29,30,31:B2,4,6,8,12,15,20",   # 4/4 · lance 4.5
            "W:W18,19,21,22,23,26,27,29,30,32:B1,2,3,4,5,9,12,14,15,17",   # 4/4 · lance 4.5
            "W:W13,18,19,20,23,26,27,29,30,31:B1,4,5,6,8,9,10,11,12",   # 4/4 · lance 4.5
            "W:W12,19,21,24,25,27,28,29,31:B3,4,5,6,7,8,10,15,20,22",   # 4/4 · lance 4.0
            "W:W19,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,8,9,11,12,18",   # 3/4 · lance 11.0
            "W:W13,23,25,28,29,30:B2,4,5,6,9,12,14,21,24",   # 3/4 · lance 11.0
            "W:W13,18,20,22,23,25,28,29:B3,4,6,9,11,14,15",   # 3/4 · lance 11.0
            "W:WK1,20,22,24,26,29,32:B4,11,12,13,16,17",   # 3/4 · lance 10.3
            "W:W18,20,21,22,23,28,29:B1,3,4,11,14,15",   # 3/4 · lance 10.3
            "W:W20,21,24,25,26,28,29,30,31:B1,2,3,4,5,8,9,10,12,13,15",   # 3/4 · lance 9.7
            "W:W20,21,23,24,26,28,29,30,32:B1,2,4,8,11,12,13,14,15",   # 3/4 · lance 9.7
            "W:W20,21,22,23,25,27,28,29,31,32:B1,2,3,4,5,10,11,12,14,15",   # 3/4 · lance 9.7
            "W:W19,20,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,6,7,8,9,10,11,12,13",   # 3/4 · lance 9.7
            "W:W17,18,19,23,25,26,27,28,29,30,31:B2,3,4,5,6,8,9,10,11,12,16",   # 3/4 · lance 9.7
            "W:W13,19,21,22,25,26,28,29,30,31,32:B1,2,4,5,8,11,12,20",   # 3/4 · lance 9.7
            "W:WK19,20,21,23,24,26,28,29,31:B3,4,12",   # 3/4 · lance 9.0
            "W:WK1,14,20,24,26,29,32:B4,11,12,16,17,21",   # 3/4 · lance 9.0
            "W:W21,22,23,25,26,28,29,30,31,32:B1,2,3,4,5,7,9,10,12,13,24",   # 3/4 · lance 9.0
            "W:W21,22,23,24,25,27,28,29,32:B2,3,4,6,7,10,13,15,17,20",   # 3/4 · lance 9.0
            "W:W20,21,22,23,24,25,26,27,28,29,30,31:B1,3,4,5,6,7,8,9,11,12,13,14",   # 3/4 · lance 9.0
            "W:W19,20,21,22,24,25,27,28,29,30,32:B1,3,4,5,6,8,9,10,11,12,15",   # 3/4 · lance 9.0
            "W:W17,18,22,23,24,25,28,29:B1,3,4,5,6,10,11,12,20",   # 3/4 · lance 9.0
            "W:W13,19,20,21,22,25,29,31:B2,3,4,6,10,12,14,18",   # 3/4 · lance 9.0
            "W:W12,17,20,21,22,23,25,29,30,31,32:B1,2,4,5,7,8,9,10,11,14",   # 3/4 · lance 9.0
            "W:W21,22,24,25,26,27,28,29,32:B2,3,4,6,7,10,13,14,15,20",   # 3/4 · lance 8.3
            "W:W19,21,22,23,24,25,27,28,29,32:B2,4,5,9,10,11,12,13,14,16",   # 3/4 · lance 8.3
            "W:W19,20,21,23,25,26,29,30,31:B1,3,4,5,7,10,12,14",   # 3/4 · lance 8.3
            "W:W18,19,21,28,29,30,31,32:B1,3,4,6,7,10,12,14,15,27",   # 3/4 · lance 8.3
            "W:W18,19,21,23,24,25,26,28,29,30,31,32:B1,2,3,4,5,7,8,10,11,12,13,14",   # 3/4 · lance 8.3
            "W:W18,19,20,21,23,24,28,29,31:B1,4,5,6,8,10,11,12,14,22",   # 3/4 · lance 8.3
            "W:W17,18,19,20,21,22,28:B7,8,10,11,12,13,14",   # 3/4 · lance 8.3
            "W:W13,18,20,23,25,26,27,28,29,30:B2,4,5,6,8,9,12,14,16,21",   # 3/4 · lance 8.3
            "W:WK1,18,21,25,28,29,30,31:B2,4,6,8,10,12,20",   # 3/4 · lance 7.7
            "W:W21,22,23,25,26,28,29,32:B1,2,3,4,5,6,10,12,13,14,15,K31",   # 3/4 · lance 7.7
            "W:W19,21,23,24,25,26,27,28,29,30,32:B2,3,4,6,7,8,10,11,12,13,14",   # 3/4 · lance 7.7
            "W:W19,21,22,23,25,26,27,29,30,32:B1,2,3,4,5,9,11,12,13,14",   # 3/4 · lance 7.7
            "W:W19,20,21,22,24,25,27,28,29,30,32:B1,3,4,5,6,7,9,10,11,12,15",   # 3/4 · lance 7.7
            "W:W18,21,22,23,24,27,28,29,30,31,32:B2,3,4,5,7,8,10,11,12,13,14",   # 3/4 · lance 7.7
            "W:W18,20,22,23,25,26,28,29,30,32:B2,4,5,6,8,9,11,12,13,14,21",   # 3/4 · lance 7.7
            "W:W18,20,21,22,23,24,25,26,27,28,29:B1,4,5,8,9,11,12,13,14,15,16",   # 3/4 · lance 7.7
            "W:W18,19,20,21,24,K26,28,29,31:B4,8,9,12,13",   # 3/4 · lance 7.7
            "W:W18,19,20,21,23,25,26,27,29,30,31:B1,4,5,6,7,8,9,10,11,12,14",   # 3/4 · lance 7.7
            "W:W17,18,25,26,27,28,29,31,32:B1,2,4,5,6,8,10,11,12,20",   # 3/4 · lance 7.7
            "W:W15,17,19,21,25,29,31:B4,5,6,9,10,12,14",   # 3/4 · lance 7.7
            "W:WK3,21,23,K26,27,28,29,30,31,32:B4,5,16",   # 3/4 · lance 7.0
            "W:W6,12,19,20,21,25,29:B2,3,4,9,13,14,K28",   # 3/4 · lance 7.0
            "W:W21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,11,12,23",   # 3/4 · lance 7.0
            "W:W20,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,11,12,17",   # 3/4 · lance 7.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,12,13,15",   # 3/4 · lance 7.0
            "W:W19,20,21,22,23,25,26,29,30,31,32:B1,2,3,4,5,8,9,10,11,12,14",   # 3/4 · lance 7.0
            "W:W17,18,22,24,25,27,28,29:B1,3,4,5,6,8,12,14,16",   # 3/4 · lance 7.0
            "W:W17,18,19,20,22,25,28:B7,8,9,10,11,12,13",   # 3/4 · lance 7.0
            "W:W14,18,20,22,23,25,26,27,28,29,32:B1,3,4,5,8,9,11,12,15,17",   # 3/4 · lance 7.0
            "W:W13,19,20,22,24,28:B4,8,9,10,11,12",   # 3/4 · lance 7.0
            "W:W12,19,20,21,22,24,25,28,29,30,32:B1,3,4,5,6,9,10,11,14,15",   # 3/4 · lance 7.0
            "W:W12,13,19,20,21,24,25,26,27,28,29:B1,4,5,6,9,10,11,14,15,18",   # 3/4 · lance 7.0
            "W:W11,21,22,24,25,27,29:B4,5,10,13,14,20",   # 3/4 · lance 7.0
            "W:WK2,12,17,20,21,24,27,28,29,30:B3,4,5,6,11",   # 3/4 · lance 6.3
            "W:WK1,17,21,22,23,25,28,29,30,31:B4,16,18,20",   # 3/4 · lance 6.3
            "W:WK1,15,20,26,28,29,32:B4,8,12,13,14,16,18",   # 3/4 · lance 6.3
            "W:W21,22,23,24,25,26,27,28,29,32:B2,3,4,6,7,10,11,13,14,15,19",   # 3/4 · lance 6.3
            "W:W20,21,22,25,28,29,31:B1,3,4,5,7,9,12,13,16",   # 3/4 · lance 6.3
            "W:W20,21,22,23,25,26,28,29,30,31:B1,2,3,4,5,6,9,10,11,12,24",   # 3/4 · lance 6.3
            "W:W20,21,22,23,25,26,27,28,29,30,31:B1,3,4,5,6,8,9,10,11,13,14,19",   # 3/4 · lance 6.3
            "W:W18,20,21,24,K26,28,29,31:B4,8,9,13,19",   # 3/4 · lance 6.3
            "W:W17,19,20,21,25,26,29,31:B1,2,3,4,9,10,12,18",   # 3/4 · lance 6.3
            "W:WK1,K2,17,18,19,21,22,25,28,29,32:B4,8,12,13,14",   # 3/4 · lance 5.7
            "W:W20,21,24,28,29,30,31:B3,4,5,9,10,12,18",   # 3/4 · lance 5.7
            "W:W18,20,21,22,24,25,28,29,30,32:B1,4,5,6,7,8,10,11,13,15,19",   # 3/4 · lance 5.7
            "W:W11,17,19,21,25,29,31:B4,5,6,9,10,12,18",   # 3/4 · lance 5.7
            "W:WK7,19,20,21,23,24,28,29,31:B1,4,8,12,13,14,22",   # 3/4 · lance 5.0
            "W:W21,22,23,26,28,29,30,32:B1,2,3,4,5,6,10,11,12,13,14,K31",   # 3/4 · lance 5.0
            "W:W20,21,22,23,24,25,26,28,29,30,31:B1,2,3,4,5,6,8,9,10,11,19",   # 3/4 · lance 5.0
            "W:W18,20,21,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,12,13,16",   # 3/4 · lance 5.0
            "W:W18,19,22,23,25,27,29:B2,4,8,10,12,13,15",   # 3/4 · lance 5.0
            "W:W12,13,17,19,21,29,32:B3,6,9,10,11,14,18",   # 3/4 · lance 5.0
            "W:W11,12,16,17,21,27,28:B2,3,4,10,18,19",   # 3/4 · lance 5.0
            "W:W17,18,19,23,24,25,26,27,29,30,31:B2,3,4,5,6,8,9,10,11,12,20",   # 3/4 · lance 4.3
            "W:W16,19,21,22,24,28,29,30,31,32:B1,3,4,6,7,10,11,12,14,15",   # 3/4 · lance 4.3
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
        # ⛔ **E O PISO DE MATERIAL E RELATIVO, E NAO `>= 1`. A REGUA OBRIGOU.**
        #
        # ⚠️ **O desenho de 14/09 premiava jogar MAL**, e foi preciso medir os
        # mascotes para ver. Com `material_restante >= 1` — *"voce ainda esta de
        # pe"* — a Cacau resolveu **30 de 30** em tres dias diferentes, enquanto o
        # Tex e o Magno ficavam em 7 e 8 de 10:
        #
        #     piso `>= 1`      cacau 10/10 · tex  8/10 · magno 10/10   taxa 0.93
        #                      cacau 10/10 · pita 10/10 · tex 10/10    taxa 1.00
        #                      cacau 10/10 · tex  7/10 · magno  7/10   taxa 0.80
        #
        # ⛔ **A escada do produto saiu INVERTIDA**, e a razao e estrutural:
        # **resistir nao e vencer**. Quem joga para vencer troca pecas e as vezes
        # se liquida; a Cacau, que anda quase ao acaso, so empurra pedra — e a
        # partida arrasta ate o oitavo lance sozinha. ⚠️ *"Ter pelo menos uma
        # peca depois de 8 lances"* nao cobra habilidade nenhuma num tabuleiro
        # com 15 pecas.
        #
        # ✅ **Apertar o piso restaurou a escada, e poe a taxa na banda:**
        #
        #     piso `>= M-2`    cacau  6/10 · tex  8/10 · magno 10/10   taxa 0.80
        #                      cacau  4/10 · pita 8/10 · tex   10/10   taxa 0.73
        #
        # ⚠️ Monotona nas duas amostras, e na ordem certa. ⛔ **Sao DUAS amostras**,
        # e nao a rodada cheia — o rotulo definitivo sai da medicao com regua.
        #
        # ⚠️ **E `entregar` aqui e o MESMO mecanismo do `damas_sacrificio`**, com o
        # comparador virado: la `material_restante <= M - entregar` **exige** a
        # perda; aqui `>= M - entregar` a **limita**. Um numero relativo, dois
        # tipos opostos.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("lances_do_jogador", "maior_ou_igual", p["lances"]),
                _medida("material_restante", "maior_ou_igual", p["resta_a_voce"]),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "perder": p["entregar"],
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
        # **zero candidato** (medido em 14/09/2026).
        #
        # ✅ **ACERVO PESCADO EM PARTIDAS REAIS DO `des`, 15/09/2026**, com o
        # filtro `--desvantagem 2`, que nasceu para este tipo: ele e o unico que
        # procura posicao em que **quem joga esta atras**.
        #
        #     1.426  com 10+ pecas
        #       207  com quem joga 2+ pecas atras   ← o filtro novo
        #        89  partida ja acabada
        #       118  passaram a peneira
        #       112  serviram a tres ou mais modalidades (107 servem as quatro)
        #
        # ⚠️ **57% de aproveitamento na peneira** (118 de 207) — o maior de todas
        # as pescarias. ⛔ E isso **nao** quer dizer que o tipo e facil: quer
        # dizer que a pergunta *"da para resistir daqui?"* e mais frequentemente
        # sim do que *"da para coroar daqui?"*. Quem diz se e dificil e a regua.
        #
        # ⚠️ **Os 89 descartes sao TODOS `partida_acabou`**, e nenhum e
        # `nao_cumpriu_no_teto`: quando este tipo falha, e porque a pessoa foi
        # liquidada antes do oitavo lance — nunca por falta de tempo de busca.
        # ✅ O teto de 18 meios-lances, entao, esta certo.
        #
        # ⚠️ **Todos caem no lance 15**, e isso nao e coincidencia: e o piso
        # aritmetico de `lances_do_jogador >= 8` quando os dois lados alternam.
        # ⛔ Neste tipo o "comprimento da solucao" nao mede dificuldade nenhuma —
        # e por isso o corte dos curtos que o `sacrificio` levou nao se aplica
        # aqui: nao ha molde curto, todos sao o mesmo comprimento.
        moldes=(
            "W:WK2,25,28,29,31:B1,3,4,5,12,22,23",   # 4/4 · lance 15.0
            "W:W7,15,22,30:B1,4,12,21,K31,K32",   # 4/4 · lance 15.0
            "W:W6,21,23,29,30,32:B1,2,3,4,5,12,14,15",   # 4/4 · lance 15.0
            "W:W27,28,29,31:B3,4,5,7,11,12,13,K30",   # 4/4 · lance 15.0
            "W:W26,28,29,30,32:B4,5,10,12,13,21,K31",   # 4/4 · lance 15.0
            "W:W24,27,28,29,30,32:B2,3,4,5,6,8,12,13,14,17",   # 4/4 · lance 15.0
            "W:W24,25,28,29,32:B1,2,4,5,8,11,12,K31",   # 4/4 · lance 15.0
            "W:W23,28,29,30,32:B4,5,12,13,14,21,K31",   # 4/4 · lance 15.0
            "W:W23,25,28,29,30:B2,4,5,7,9,10,12,13,K20",   # 4/4 · lance 15.0
            "W:W23,25,28,29,30,32:B2,4,5,7,9,10,12,13,K31",   # 4/4 · lance 15.0
            "W:W23,24,28,29,30,32:B2,3,4,5,6,8,12,13,14,21",   # 4/4 · lance 15.0
            "W:W23,24,27,28,29,32:B1,3,4,8,11,12,13,16,K30,K31",   # 4/4 · lance 15.0
            "W:W23,24,27,28,29,30:B2,3,4,5,6,8,12,14,17,21",   # 4/4 · lance 15.0
            "W:W23,24,25,27,28,29,30,31,32:B2,3,4,5,7,8,9,11,12,13,26",   # 4/4 · lance 15.0
            "W:W22,25,26,32:B4,11,13,14,16,24",   # 4/4 · lance 15.0
            "W:W22,23,25,29:B2,4,10,12,13,K31",   # 4/4 · lance 15.0
            "W:W21,28,29,32:B1,2,4,5,8,11,12,K20",   # 4/4 · lance 15.0
            "W:W21,28,29,30,31:B1,4,5,11,12,13,14,25,K32",   # 4/4 · lance 15.0
            "W:W21,27,29,31,32:B3,4,5,7,11,12,22,26",   # 4/4 · lance 15.0
            "W:W21,27,28,29,31:B3,4,5,7,11,12,22,K30",   # 4/4 · lance 15.0
            "W:W21,25,28,29:B2,3,4,15,16,22",   # 4/4 · lance 15.0
            "W:W21,25,28,29,30:B1,2,4,5,12,15,27",   # 4/4 · lance 15.0
            "W:W21,25,28,29,30,31:B1,4,5,11,12,13,14,18,K32",   # 4/4 · lance 15.0
            "W:W21,25,28,29,30,31,32:B1,4,5,11,12,13,14,18,23",   # 4/4 · lance 15.0
            "W:W21,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,12,20,22",   # 4/4 · lance 15.0
            "W:W21,24,29,30:B2,3,4,7,8,K9,12",   # 4/4 · lance 15.0
            "W:W21,24,25,29,30:B1,2,4,5,12,15,K31",   # 4/4 · lance 15.0
            "W:W21,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,8,9,10,11,12,13",   # 4/4 · lance 15.0
            "W:W21,23,25,30,32:B1,3,4,5,9,12,14,15",   # 4/4 · lance 15.0
            "W:W21,23,24,25,26,28,29,30,31,32:B1,2,3,4,5,6,8,9,10,12,13,15",   # 4/4 · lance 15.0
            "W:W21,22,28,30,31:B1,4,5,11,12,13,14,K23",   # 4/4 · lance 15.0
            "W:W21,22,25,29:B5,9,11,13,14,18",   # 4/4 · lance 15.0
            "W:W21,22,25,28,29,32:B1,2,3,4,5,6,10,12,13,15,K30,K31",   # 4/4 · lance 15.0
            "W:W21,22,24,25,27,28,29,32:B1,2,3,4,5,7,8,12,16,23",   # 4/4 · lance 15.0
            "W:W21,22,23,30,32:B1,3,4,5,9,12,15,18",   # 4/4 · lance 15.0
            "W:W21,22,23,26,28,29,30,32:B1,2,3,4,5,6,10,11,12,13,14,K31",   # 4/4 · lance 15.0
            "W:W21,22,23,25,26,28,29,32:B1,2,3,4,5,6,10,12,13,14,15,K31",   # 4/4 · lance 15.0
            "W:W21,22,23,24,26,28,29,30,31,32:B1,2,3,4,5,6,8,10,12,13,14,15",   # 4/4 · lance 15.0
            "W:W21,22,23,24,26,27,28,29,30,32:B1,2,3,4,5,6,10,11,12,13,14,15",   # 4/4 · lance 15.0
            "W:W20,28,29,30:B3,4,5,9,12,K17",   # 4/4 · lance 15.0
            "W:W20,22,23,25,26,29,30,31,32:B1,2,3,4,5,8,9,10,11,19,21",   # 4/4 · lance 15.0
            "W:W20,21,29,30,31:B1,3,4,5,9,11,14,19",   # 4/4 · lance 15.0
            "W:W20,21,27,29,30:B1,3,4,5,9,11,18,19",   # 4/4 · lance 15.0
            "W:W20,21,26,27,29:B1,3,4,5,9,15,18,19",   # 4/4 · lance 15.0
            "W:W20,21,25,28,29,30,32:B2,3,4,8,9,11,13,14,27",   # 4/4 · lance 15.0
            "W:W20,21,25,26,28,29,30,31:B1,2,3,4,5,8,9,10,12,13,24",   # 4/4 · lance 15.0
            "W:W20,21,25,26,28,29,30,31,32:B1,2,3,4,5,6,8,9,11,12,13",   # 4/4 · lance 15.0
            "W:W20,21,25,26,27,28,29,30,31:B1,2,3,4,5,6,8,9,12,13,15",   # 4/4 · lance 15.0
            "W:W20,21,24,25,26,28,29,30,31:B1,2,3,4,5,8,9,10,12,13,15",   # 4/4 · lance 15.0
            "W:W20,21,22,25,28,29,31:B1,3,4,5,7,9,12,13,16",   # 4/4 · lance 15.0
            "W:W19,25,28,29,30:B2,4,5,7,10,12,13,14,K20",   # 4/4 · lance 15.0
            "W:W19,23,27,28,29,30:B2,3,4,5,6,8,12,14,21,22",   # 4/4 · lance 15.0
            "W:W19,22,23,24,26,28,29,31,32:B1,2,3,4,8,10,11,12,13,16,K30",   # 4/4 · lance 15.0
            "W:W19,20,23,24,27,28,29,30,32:B2,3,4,5,6,7,8,11,12,13,17",   # 4/4 · lance 15.0
            "W:W19,20,21,25,29,30,31:B1,2,3,4,5,9,10,12,15,22",   # 4/4 · lance 15.0
            "W:W19,20,21,25,26,29,30,31:B1,2,3,4,5,9,10,11,12,13",   # 4/4 · lance 15.0
            "W:W19,20,21,22,25,29,30,31:B1,2,3,4,5,9,10,12,13,15",   # 4/4 · lance 15.0
            "W:W18,22,29,30,32:B4,5,10,11,12,13,24",   # 4/4 · lance 15.0
            "W:W18,22,26,29,32:B4,5,10,11,13,16,24",   # 4/4 · lance 15.0
            "W:W18,22,25,26,32:B4,5,11,13,14,16,24",   # 4/4 · lance 15.0
            "W:W18,22,23,28,29,30,32:B3,4,5,6,9,12,13,14,21,K31",   # 4/4 · lance 15.0
            "W:W18,21,22,25,28,29,30,32:B1,4,5,6,7,8,10,13,15,19,27",   # 4/4 · lance 15.0
            "W:W18,20,21,23,24,25,27,28,29:B1,4,5,8,9,11,12,14,15,16,K31",   # 4/4 · lance 15.0
            "W:W18,19,23,24,26,28,29,31,32:B1,3,4,6,8,10,11,12,13,16,K30",   # 4/4 · lance 15.0
            "W:W18,19,23,24,26,27,28,29,32:B1,3,4,6,8,11,12,13,15,16,K30",   # 4/4 · lance 15.0
            "W:W18,19,22,23,29,30:B4,5,10,11,12,13,15,27",   # 4/4 · lance 15.0
            "W:W18,19,21,28,29,30,31,32:B1,3,4,6,7,10,12,14,15,27",   # 4/4 · lance 15.0
            "W:W18,19,20,24,27,28,29,30,32:B2,3,4,5,6,7,8,12,13,16,17",   # 4/4 · lance 15.0
            "W:W17,21,25,26,28,29,31,32:B1,2,3,4,5,7,8,10,11,12,20",   # 4/4 · lance 15.0
            "W:W17,20,21,25,29,31:B1,2,3,4,9,10,18,26",   # 4/4 · lance 15.0
            "W:W17,18,25,26,28,29,31,32:B1,2,4,5,6,8,10,11,12,27",   # 4/4 · lance 15.0
            "W:W16,19,21,24,29,30:B2,4,7,9,12,13,14,25",   # 4/4 · lance 15.0
            "W:W15,23,27,28,29,30:B2,3,4,5,6,8,12,14,21,26",   # 4/4 · lance 15.0
            "W:W13,23,25,28,29,30:B2,4,5,6,9,12,14,21,24",   # 4/4 · lance 15.0
            "W:W13,21,25,29,31:B2,3,4,5,11,12,K14,15",   # 4/4 · lance 15.0
            "W:W13,21,25,27,28,29,30,31:B2,3,4,6,7,8,9,14,16,17",   # 4/4 · lance 15.0
            "W:W13,21,25,26,29:B2,3,4,5,11,12,K14,18",   # 4/4 · lance 15.0
            "W:W13,21,25,26,28,29,31,32:B1,2,3,4,5,7,8,11,12,14,20",   # 4/4 · lance 15.0
            "W:W13,21,22,29:B2,3,4,5,8,10,11,12,16,24",   # 4/4 · lance 15.0
            "W:W13,21,22,25,28,29,31:B1,2,3,4,5,8,11,12,14,15,27",   # 4/4 · lance 15.0
            "W:W13,21,22,25,28,29,31,32:B1,2,3,4,5,8,10,11,12,14,20",   # 4/4 · lance 15.0
            "W:W13,21,22,25,27,28,29,31:B1,2,3,4,5,8,11,12,14,15,20",   # 4/4 · lance 15.0
            "W:W13,21,22,24,25,28,29:B1,2,3,4,5,8,11,12,15,18",   # 4/4 · lance 15.0
            "W:W13,19,23,25,29,30:B2,5,6,8,9,12,14,21",   # 4/4 · lance 15.0
            "W:W13,18,22,23,25,28,29:B1,3,4,5,6,10,11,12,27",   # 4/4 · lance 15.0
            "W:W13,17,22,29:B2,3,4,5,8,10,11,12,16,28",   # 4/4 · lance 15.0
            "W:W13,17,22,28,29:B1,3,4,5,6,10,24",   # 4/4 · lance 15.0
            "W:W13,17,22,25,28,29:B1,2,3,4,5,8,11,12,15,16",   # 4/4 · lance 15.0
            "W:W13,17,22,24,25,28,29:B1,2,3,4,5,8,11,12,15,23",   # 4/4 · lance 15.0
            "W:W13,17,21,22,28,29:B1,2,3,4,5,8,11,12,16,19",   # 4/4 · lance 15.0
            "W:W13,17,18,29:B1,4,5,6,10,19",   # 4/4 · lance 15.0
            "W:W13,15,23,25,29,30:B2,5,6,8,9,14,16,21",   # 4/4 · lance 15.0
            "W:W13,15,22,23,29,30:B2,5,6,8,9,16,18,21",   # 4/4 · lance 15.0
            "W:W13,15,17,29:B1,4,5,6,10,24",   # 4/4 · lance 15.0
            "W:W13,14,21,22,29:B1,2,3,4,5,8,11,12,16,20",   # 4/4 · lance 15.0
            "W:W13,14,21,22,28,29:B1,2,3,4,5,8,11,12,16,23",   # 4/4 · lance 15.0
            "W:W13,14,21,22,24,29:B1,2,3,4,5,8,11,12,20,23",   # 4/4 · lance 15.0
            "W:W12,24,28,29,31:B1,3,4,6,11,14,17",   # 4/4 · lance 15.0
            "W:W12,19,28,29,31:B1,3,4,6,11,14,22",   # 4/4 · lance 15.0
            "W:W12,19,24,29,31:B1,3,4,6,14,16,22",   # 4/4 · lance 15.0
            "W:W12,17,21,22,29:B1,4,9,13,16,24,K32",   # 4/4 · lance 15.0
            "W:W11,20,21,29,30,31:B1,2,3,4,5,9,14,19",   # 4/4 · lance 15.0
            "W:W11,19,21,25,28,29,32:B2,4,5,9,10,12,13,14,K17",   # 4/4 · lance 15.0
            "W:W11,19,21,24,25,29,32:B2,4,5,9,10,12,13,14,K26",   # 4/4 · lance 15.0
            "W:W11,17,21,24:B2,4,10,18,19,28",   # 4/4 · lance 15.0
            "W:W10,15,22,30:B1,4,12,21,27,K32",   # 4/4 · lance 15.0
            "W:W10,13,21,22,29:B1,2,3,4,5,8,11,12,16,24",   # 4/4 · lance 15.0
            "W:W23,28,29,30:B4,5,12,13,14,K20,21",   # 3/4 · lance 15.0
            "W:W20,27,28,29,32:B1,3,4,8,11,12,13,16,K19,K31",   # 3/4 · lance 15.0
            "W:W19,22,28,29,30:B2,4,5,7,10,12,13,14,K16",   # 3/4 · lance 15.0
            "W:W18,23,25,29:B2,4,10,12,13,K27",   # 3/4 · lance 15.0
            "W:W18,22,23,29:B2,4,12,13,15,K27",   # 3/4 · lance 15.0
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
    # ⚠️ `entregar` aqui LIMITA a perda (`material_restante >= M - 2`), enquanto
    # no sacrificio a EXIGE. Mesmo mecanismo, comparador virado.
    "damas_sobreviver": {"lances": 8, "entregar": 2},
    "damas_armadilha": {"turnos": 2, "pecas": 3},
    "damas_dupla_coroacao": {"lances": 8},
    "damas_limpeza": {"lances": 5, "restam": 1},
    "damas_troca_favoravel": {"comer": 2, "pecas": 3},
    "damas_vitoria_relampago": {"lances": 4},
    "damas_empate_honroso": {},
}
