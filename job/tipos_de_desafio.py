"""AS RECEITAS DE CADA TIPO DE DESAFIO (T034).

═══════════════════════════════════════════════════════════════════════════
TIPO x FORMA DE CHEGADA — E ISSO CONFUNDIU A SPEC POR SEMANAS
═══════════════════════════════════════════════════════════════════════════

**O tipo e a IDENTIDADE** do desafio: e ele que da a frase, o rodizio (para nao
cair o mesmo tipo dois dias seguidos) e o agrupamento na curadoria.

**A forma de chegada e COMO SE JULGA**, e ela e **uma so** — a conjuncao de
clausulas. Dez tipos diferentes usam hoje a mesma forma.

⚠️ Foi por confundir os dois que *"o lance unico"* e *"final da base"* pareceram,
por um tempo, nao ter forma propria: eles sao **tipos**, e a linha de chegada
deles e a comum.

Uma **receita** e o que liga um ao outro: dado o tipo e os parametros do dia, ela
monta o `js_chegada`, a chave de i18n do enunciado e os valores que entram na
frase.

═══════════════════════════════════════════════════════════════════════════
⛔ TIPO SEM RECEITA NAO E PUBLICAVEL — E E ASSIM QUE TEM DE SER
═══════════════════════════════════════════════════════════════════════════

E a regra 2 do contrato dos vetores, vista deste lado. Um tipo publicado sem
receita produziria um desafio cuja linha de chegada ninguem escreveu — e o
julgamento devolveria "nao cumpriu" para todo mundo, **sem erro nenhum**.

⚠️ E a receita nao basta sozinha: o gerador tambem exige **vetor de verificacao**
para o tipo (RF-DES-198). Duas portas, e as duas fecham a mesma falha silenciosa
por caminhos diferentes — a receita garante que existe regra, o vetor garante que
os dois lados a leem igual.

═══════════════════════════════════════════════════════════════════════════
⚠️ PARAMETRO NOVO E `INSERT`, NUNCA CODIGO (SC-027)
═══════════════════════════════════════════════════════════════════════════

Trocar `4` por `6` caixas no mesmo tipo **nao toca `.arb`, nao toca codigo e nao
muda `co_versao_minima`**. E por isso que os numeros sao argumento da receita, e
nao literais espalhados por ela.

O que **ainda exige versao nova do aplicativo** e a chave `.arb` do enunciado: uma
chave desconhecida cai na tela de atualizar. Por isso a chave e parte da receita —
acrescentar um tipo e, por definicao, acrescentar texto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

#: A versao do formato de `js_chegada` que as receitas emitem.
VERSAO_CHEGADA = 1


class TipoSemReceita(ValueError):
    """O tipo nao tem receita — e por isso nao e publicavel.

    ⚠️ Falha alto de proposito. A alternativa (devolver uma chegada vazia) daria
    um desafio que ninguem consegue cumprir, e o log ficaria limpo.
    """


@dataclass(frozen=True, slots=True)
class Receita:
    """Como um tipo vira desafio.

    Atributos:
        nu_tipo_desafio: o numero da dimensao `tb901_tipo_desafio`.
        co_tipo_desafio: o codigo, para leitura humana e para os vetores.
        co_jogo: de que jogo este tipo e.
        co_chave_objetivo: a chave de i18n do enunciado. ⛔ **Nunca a frase**: ela
            viajaria num idioma so.
        montar: `(parametros) -> js_chegada`.
        valores_da_frase: `(parametros, personagem) -> js_objetivo`, os valores
            que entram nos espacos da frase.
        moldes: posicoes de partida de onde este tipo costuma sair. Vazio quer
            dizer "gere a partir do inicio do jogo".

    ⚠️ **Por que MOLDES existem, e a medida que os justifica.** O gerador ingenuo
    parte do tabuleiro vazio (ou da posicao inicial) e joga lances aleatorios ate
    chegar a algo interessante. Isso funciona no Pontinhos, e ⛔ **nao funciona
    nas damas**: medido em 09/09/2026, tres tentativas de gerar *"coroe uma dama
    em 6 lances"* a partir de 40 lances aleatorios deram **zero** candidatos em
    35 segundos — coroar exige atravessar o tabuleiro, e uma abertura aleatoria
    quase nunca deixa uma peca perto da oitava fileira com caminho livre.

    Um molde e uma posicao **de onde o objetivo e alcancavel**, escrita a mao e
    validada pelo motor. O gerador sorteia um molde e o **varia** com poucos
    lances legais antes de procurar a solucao — e e a variacao que impede a fila
    de repetir a mesma posicao todo dia.

    ⚠️ Molde **nao e** o desafio pronto: se a variacao destruir o objetivo, o
    gerador simplesmente nao acha solucao e tenta outra. O molde e ponto de
    partida, nunca garantia.
    """

    nu_tipo_desafio: int
    co_tipo_desafio: str
    co_jogo: str
    co_chave_objetivo: str
    montar: Callable[[Mapping[str, Any]], dict[str, Any]]
    valores_da_frase: Callable[[Mapping[str, Any], str], dict[str, Any]]
    moldes: tuple[str, ...] = ()


def _medida(chave: str, comparador: str, valor: Any) -> dict[str, Any]:
    """Uma clausula de medida, no formato que o avaliador le."""
    return {
        "tipo": "medida",
        "chave": chave,
        "comparador": comparador,
        "valor": valor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# As receitas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **Sao quatro, e nao dez, e isso esta declarado.** As outras seis entram
# quando tiverem receita E vetor — nesta ordem, e nunca uma sem a outra.

RECEITAS: dict[str, Receita] = {
    "pontinhos_fechar_caixas": Receita(
        nu_tipo_desafio=1,
        co_tipo_desafio="pontinhos_fechar_caixas",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoFecharCaixasEmTurnos",
        # "Feche N caixas em T turnos": a janela e de TURNOS, e nao de lances,
        # porque quem fecha caixa joga de novo — quatro caixas em quatro lances
        # seguidos sao um turno so.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "turnos_do_jogador", "n": p["turnos"]},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "turnos": p["turnos"],
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
    "pontinhos_chegar_ao_placar": Receita(
        nu_tipo_desafio=4,
        co_tipo_desafio="pontinhos_chegar_ao_placar",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoChegarAoPlacar",
        # Sem limite de turnos: o que importa e o placar no fim.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "personagem": personagem,
        },
    ),
    "damas_coroar": Receita(
        nu_tipo_desafio=6,
        co_tipo_desafio="damas_coroar",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCoroarEmLances",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("damas_coroadas", "maior_ou_igual", p["damas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "damas": p["damas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Finais em que uma branca esta a algumas fileiras da oitava, com o
        # tabuleiro ainda CHEIO — pretas suficientes para atrapalhar o caminho, e
        # nao so para a partida nao acabar antes.
        #
        # ⛔ **O ACERVO INTEIRO FOI TROCADO em 16/09/2026**, e desta vez a troca
        # e uma reprovacao, nao um acrescimo. Os 515 moldes anteriores (3
        # desenhados a mao, 327 sinteticos de `scripts/cacar_moldes_damas.py` e
        # 185 pescados do `prd` em 12/09) sairam inteiros; quem os quiser de
        # volta os encontra no Git e em `docs/DECISOES-do-dono.md` §8k-13.
        #
        # ⚠️ **O motivo, do dono, olhando o desafio publicado de 17/09:**
        #
        # > *"Ele e extremamente facil. Ele e simplesmente empurrar as 2 pecas
        # > azuis para frente. Nao ha desafio algum nisso. Nao ha barreiras de
        # > pecas."*
        #
        # ⛔ **E a causa era estrutural, nao o azar do dia:** nos 515 moldes,
        # **82% (422) tinham a pedra mais adiantada a 1 ou 2 fileiras** da
        # coroacao, e o material medio era **7,3** — tabuleiro quase vazio.
        # ⚠️ O editorial chamava a variante de duas damas de *dura*, e estava
        # certo sobre a ESCASSEZ (poucos moldes comportam duas coroacoes na
        # janela) — so que os moldes que comportam sao justamente os vazios.
        # Escassez e facilidade eram a mesma coisa, e ninguem leu o rotulo assim.
        #
        # ⛔ **O criterio que separa e a DISTANCIA, e ele foi MEDIDO** (§8k-13):
        # *"a solucao exige captura"* nao separa nada — em 80 moldes, 80% dos de
        # 3-6 pecas ja exigem captura, contra 75% dos de 14+. ⚠️ Nas brasileiras a
        # captura e **obrigatoria**, entao ela diz *"fui forcado a comer no
        # caminho"* muito mais vezes que *"precisei comer para chegar"*.
        # ✅ Ja a distancia traz as duas coisas que o dono pediu de uma vez: peca
        # menos adiantada e tabuleiro mais cheio andam juntos.
        #
        # ── ✅ O ACERVO DE HOJE: 133 moldes, pescados do `prd` E do `des` ─────
        #
        # ⚠️ **As damas estao em campo desde 03/09**, entao pela primeira vez o
        # coroar tem posicoes de gente de verdade em volume: 118 partidas reais
        # deram **6.117 posicoes unicas** no `prd`, contra as 1.777 do `des` —
        # que, no fundo, eram o retrato de como **uma pessoa** joga damas.
        #
        # O funil da pescaria de 16/09 (as duas fases, ~3 h no total):
        #
        #     7.823  posicoes reais, sem repeticao (uniao prd + des)
        #     4.881  com 12+ pecas                      ← o piso de material
        #     4.871  com a pedra a 6 fileiras ou menos  ← o teto, `--alcancavel`
        #     4.096  com a pedra a 3+ fileiras          ← o PISO da §8k-13
        #       234  passaram a peneira
        #       142  serviram a tres ou mais modalidades
        #       133  depois de tirar as 9 que o `capturar_multipla` ja usa
        #
        # ⚠️ **Essas 9 nao eram erro de colagem, e a premissa do cadeado
        # envelheceu:** ate 11/09 os dois acervos vinham de funcoes geradoras
        # diferentes, entao uma FEN nos dois lados so podia ser engano. Desde
        # 12/09 os dois vem da **mesma** base de posicoes reais, e uma posicao
        # de verdade comporta perfeitamente coroar **e** capturar duas.
        # ⛔ Mesmo assim elas saem: o que o cadeado guarda agora e que ninguem
        # receba **o mesmo tabuleiro** em dois desafios diferentes. ⚠️ Quem cede
        # e o coroar, e nao o `capturar_multipla` — aquele ja esta no ar e
        # medido, e mexer nele obrigaria a remedir a variante dele junto.
        #
        # Os 3.954 reprovados da peneira, pelo motivo:
        #
        #     3.674  nunca coroaram dentro do teto
        #       129  partida ja acabada
        #        59  ja nasciam coroando (objetivo no lance 1) — 46 na
        #             brasileira, 13 na anglo
        #
        # Distancia ate o objetivo, nos 133 (lance medio das modalidades):
        #
        #     3 lances: 43     6 lances: 10      9 lances: 10
        #     4 lances: 13     7 lances: 12     10 lances:  7
        #     5 lances: 21     8 lances: 14     11 lances:  3
        #
        # ⚠️ **89 dos 133 servem as quatro modalidades**; os outros 44 servem a
        # tres. O molde e publicado e resolvido em brasileira de qualquer forma
        # — as modalidades sao o teste de robustez, nao o destino.
        #
        # ✅ **Material medio 16,1** (min 12, max 24), contra os 7,3 de antes —
        # agora na faixa dos outros tres tipos de damas (17,0 · 18,9 · 15,2).
        #
        # ⚠️ **Nada se perdeu na troca, e isso foi conferido, nao presumido:**
        # dos 515 antigos, apenas **27** passariam nos dois filtros de hoje, e os
        # 27 **ja estavam** entre os 142 pescados. Os outros 488 sao o acervo
        # reprovado — material 7,3 e a pedra a um ou dois lances da coroacao.
        #
        # ⚠️ **As quatro modalidades entram, de proposito.** Uma FEN e um arranjo
        # de pecas; a modalidade muda como se **chega** nela, nao se ela e uma
        # posicao brasileira valida. O molde e publicado e resolvido em
        # brasileira de qualquer forma.
        #
        # ⛔ **Nenhum molde entrega o objetivo no primeiro lance.** A medicao
        # sozinha nao pega isso — **o Sagaz joga a PARTIDA, e nao o DESAFIO**:
        # coroar de cara costuma ser mau lance, entao ele escolhe outra coisa e a
        # medicao anota *"objetivo no lance 3"*; so que quem joga o desafio nao
        # esta jogando para vencer, esta cumprindo a tarefa. Quem guarda isso e
        # `job/moldes_de_damas.py`, na peneira do script **e** no cadeado
        # `tests/unitarios/test_moldes_de_damas.py` — a pergunta e direta ("ha
        # lance legal que cumpre o objetivo agora?") e nao custa um no de busca.
        #
        # ⚠️ **Como refazer** (o diario permite interromper e retomar, e rerodar
        # com `--bloco` reimprime a lista sem remedir nada):
        #
        #     .venv\Scripts\python -u scripts\pescar_moldes_de_partidas.py ^
        #         fens_damas_prd_e_des.json --tipo damas_coroar ^
        #         --minimo-pecas 12 --minimo-fileiras 3 --alcancavel 6 ^
        #         --embaralhar --processos 14 ^
        #         --diario pescaria_damas_coroar_prd.jsonl --bloco
        #
        # O comentario de cada linha e `modalidades validas/4 · lance medio`.
        moldes=(
            "W:W15,16,19,21,24,26,29,31:B3,4,11,12,13,14,17",   # 4/4 · lance 9.5
            "W:W13,19,20,21,24,26,28,32:B2,4,7,8,11,12,17",   # 4/4 · lance 9.5
            "W:W19,20,21,23,24,K26,28,29,31:B4,5,8,12,13",   # 4/4 · lance 9.5
            "W:W14,15,23,27,28,29:B1,3,4,12,20,22",   # 4/4 · lance 9.0
            "W:W19,20,21,22,23,25,26,29,31:B1,5,7,9,10,11,12,13,14",   # 4/4 · lance 9.0
            "W:W13,18,19,20,26,27,28,29,30,31,32:B3,4,6,8,9,10,11,12",   # 4/4 · lance 9.0
            "W:W14,20,22,27,29,30,32:B1,2,4,5,15,21",   # 4/4 · lance 8.5
            "W:W17,20,29,30,31,32:B4,8,11,12,16,18,21",   # 4/4 · lance 8.5
            "W:W13,14,19,22,25,28,29,30:B2,4,7,12",   # 4/4 · lance 8.0
            "W:WK1,20,21,23,26,28,29,32:B8,10,11,13,15,16",   # 4/4 · lance 8.0
            "W:W15,21,23,27,28,29:B8,12,16,17,18,20,22",   # 4/4 · lance 8.0
            "W:W13,14,19,20,21,25,27,29:B3,4,5,12,16",   # 4/4 · lance 8.0
            "W:WK1,14,20,26,27,28,29,32:B3,7,8,11,21,23",   # 4/4 · lance 8.0
            "W:W15,19,21,24,26,29,31:B4,10,12,13,14,17",   # 4/4 · lance 7.5
            "W:W13,19,20,21,25,26,28,31,32:B4,6,16,18",   # 4/4 · lance 7.5
            "W:W13,24,27,29,30,31,32:B4,7,11,12,15,18,20,21",   # 4/4 · lance 7.5
            "W:W13,14,19,20,24,26,28,32:B2,4,7,8,12,16",   # 4/4 · lance 7.5
            "W:W14,15,18,22,23,24,25,27,29,31,32:B1,3,4,5,6,7,11,12,13,16,20",   # 4/4 · lance 7.0
            "W:W14,19,20,23,28,29,30,31,32:B3,4,5,6,7,8,11,12,13,21",   # 4/4 · lance 7.0
            "W:W19,21,22,23,25,26,29,31:B1,5,7,9,10,12,13,14,20",   # 4/4 · lance 7.0
            "W:W13,19,21,22,25,28,29,30:B2,3,4,6,9,12,17",   # 4/4 · lance 7.0
            "W:W17,18,20,21,22,23,24,26,27,28,29,32:B2,4,6,7,8,9,10,11,12,13,15,16",   # 4/4 · lance 7.0
            "W:W13,20,29,30,31,32:B4,8,11,12,18,19,21",   # 4/4 · lance 6.5
            "W:W17,18,20,21,22,23,25,26,27,29:B1,5,6,7,8,9,11,12,13,16,24,K32",   # 4/4 · lance 6.0
            "W:W17,18,20,21,22,23,24,26,27,29,30,31:B1,4,5,6,7,9,10,11,12,13,15,16",   # 4/4 · lance 6.0
            "W:W18,19,21,22,23,24,26,28,29,30,31,32:B2,3,4,5,6,7,8,9,11,12,13,14",   # 4/4 · lance 6.0
            "W:W17,19,20,21,22,23,25,26:B1,6,8,10,12,13,14,15",   # 4/4 · lance 6.0
            "W:W13,16,17,20,21,22,25,26,28,32:B4,5,6,7,8,10,11,15,18",   # 4/4 · lance 5.5
            "W:W18,19,20,22,25,29,32:B2,8,9,10,11,12,13",   # 4/4 · lance 5.5
            "W:W21,22,23,25,26,29,31:B1,5,7,9,12,13,14,19,20",   # 4/4 · lance 5.0
            "W:W16,17,21,22,23,25,26:B1,6,8,10,12,13,14,24",   # 4/4 · lance 5.0
            "W:W18,20,21,24,28,29,30,31,32:B1,3,4,5,7,8,9,11,13,15,16,19",   # 4/4 · lance 5.0
            "W:W16,K19,21,23,24,26,28,29,31:B4,7,12",   # 4/4 · lance 5.0
            "W:W13,16,20,21,22,27,29:B3,4,5,10,18",   # 4/4 · lance 5.0
            "W:W17,19,20,21,22,23,25,31:B1,6,8,10,11,12,13,14",   # 4/4 · lance 5.0
            "W:W13,20,21,24,28,30,31:B4,5,8,11,15,16,18,K32",   # 4/4 · lance 5.0
            "W:W17,18,19,20,22,25,28:B7,8,9,10,11,12,13",   # 4/4 · lance 5.0
            "W:W13,20,23,24,25,26,28,30:B5,7,9,10,11,12,16",   # 4/4 · lance 5.0
            "W:W14,18,22,23,24,25,27,29,31,32:B1,3,5,6,7,11,12,13,16,20",   # 4/4 · lance 5.0
            "W:W18,19,21,24,28,29,30,32:B1,3,10,11,12",   # 4/4 · lance 5.0
            "W:W13,17,20,21,23,24,26,28,29,30,31,32:B1,2,4,5,7,8,9,10,11,14,15,16",   # 4/4 · lance 5.0
            "W:W13,17,20,22,25,28,30,31:B2,5,6,8,9,11,16",   # 4/4 · lance 5.0
            "W:W17,21,25,26,27,K28,29,32:B2,3,4,9,12,18,20",   # 4/4 · lance 5.0
            "W:W13,14,17,20,21,24,25,28,30,31,32:B1,3,4,6,7,8,10,11,15,16",   # 4/4 · lance 4.0
            "W:W14,15,18,21,22,25,28,29:B2,3,4,5,6,9,13,20",   # 4/4 · lance 4.0
            "W:W13,14,21,28,29,31:B6,9,11,15,22,23",   # 4/4 · lance 4.0
            "W:W19,20,22,25,29,32:B2,8,9,10,12,13,18",   # 4/4 · lance 3.5
            "W:W20,21,24,26,28,29,31,32:B1,3,4,5,7,8,9,11,13,16,19,22",   # 4/4 · lance 3.5
            "W:W15,21,29,32:B1,2,5,7,8,9,12,14,20",   # 4/4 · lance 3.5
            "W:W14,24,28,29,30,31:B2,4,6,11,15,16",   # 4/4 · lance 3.5
            "W:W20,21,22,23,25,29,31:B4,6,8,10,11,14,15",   # 4/4 · lance 3.5
            "W:W14,17,18,21,22,25,26,27,28:B4,5,10,12",   # 4/4 · lance 3.5
            "W:W13,20,21,22,K24,26,28,29,30,32:B1,5,9,10,11",   # 4/4 · lance 3.5
            "W:W14,15,18,22,23,25,27,28,29,31,32:B1,3,4,5,6,7,8,11,13,16,20",   # 4/4 · lance 3.5
            "W:W16,21,23,25,26:B1,6,8,10,12,14,15,24",   # 4/4 · lance 3.0
            "W:WK3,13,15,18,25,27,29,30,31,32:B4,8,10,12,20",   # 4/4 · lance 3.0
            "W:W14,21,23,26,28,29,30:B3,5,6,7,8,9,12,15,16,20,K31",   # 4/4 · lance 3.0
            "W:W20,21,22,25,28,31:B3,8,11,13,16,18",   # 4/4 · lance 3.0
            "W:WK1,14,17,21,22,25,28,29,30,31:B4,16,24",   # 4/4 · lance 3.0
            "W:W14,18,19,24,25,27,28,29,30,31,32:B1,2,4,5,7,8,9,10,11,12,15,22",   # 4/4 · lance 3.0
            "W:W13,17,20,21,K23,27,28:B4,5,7,12,K29",   # 4/4 · lance 3.0
            "W:W13,14,17,21,22,23,26,28,32:B2,4,5,6,8,12,15,16,19,K20",   # 4/4 · lance 3.0
            "W:W20,22,23,24,26,29,31,32:B4,7,9,10,12,13,15,K30",   # 4/4 · lance 3.0
            "W:W20,21,22,23,24,25,26,28,29,31:B1,3,4,5,6,8,10,14,15",   # 4/4 · lance 3.0
            "W:W17,19,21,25,26,29,30,31:B2,3,4,6,9,10,12,14",   # 4/4 · lance 3.0
            "W:WK3,17,20,21,22,23,25,27,29,30,32:B1,4,5,6,7,9,10,14,15",   # 4/4 · lance 3.0
            "W:W13,20,21,23,24,26,28,29,30,31,32:B4,5,6,7,8,9,10,11,14,15,16",   # 4/4 · lance 3.0
            "W:W21,22,23,24,25,27,29,30:B1,2,3,5,6,7,8,13,14,15,20",   # 4/4 · lance 3.0
            "W:W17,18,20,21,22,23,24,25,28,29,32:B4,5,6,7,8,9,10,11,12,13,15",   # 4/4 · lance 3.0
            "W:W14,18,22,23,24,25,26,27,29,32:B1,5,6,7,8,11,12,13,16,20",   # 4/4 · lance 3.0
            "W:W13,17,20,21,24,28,30,31:B2,6,8,9,10,11,15,16,23",   # 4/4 · lance 3.0
            "W:W18,21,24,28,29,30,32:B1,3,11,12,19",   # 4/4 · lance 3.0
            "W:W20,21,24,28,29,31,32:B1,3,4,5,7,8,9,11,16,19,22",   # 4/4 · lance 3.0
            "W:W16,17,19,21,22,24,28,29,31:B1,4,7,8,10,12,13,15",   # 4/4 · lance 3.0
            "W:W17,21,25,26,K28,29,32:B2,3,4,9,12,18,27",   # 4/4 · lance 3.0
            "W:W13,18,20,22,24,25,26,27,28,29,30,32:B1,3,4,5,6,7,9,10,11,12,15,19",   # 4/4 · lance 3.0
            "W:W15,21:B1,2,3,5,6,11,12,13,14,K17,23",   # 4/4 · lance 3.0
            "W:W16,20,22,24,25,26,28,29,30:B2,5,6,7,8,10,11,13,15,21",   # 4/4 · lance 3.0
            "W:WK10,18,20,25,28,29,30,31:B2,3,8,9,11,16,22",   # 4/4 · lance 3.0
            "W:W13,17,20,22,23,24,26,28,29,30:B2,5,6,8,9,11,12,15,16",   # 4/4 · lance 3.0
            "W:W14,18,19,22,23,25,27,28,29,31,32:B1,3,4,5,6,7,8,11,12,13,20",   # 4/4 · lance 3.0
            "W:W13,20,22,25,28,30,31:B2,5,6,8,11,16,18",   # 4/4 · lance 3.0
            "W:W14,15,16,20,24,28,29,32:B5,7,8,13",   # 4/4 · lance 3.0
            "W:W20,22,23,24,26,28,29,31:B7,8,9,10,12,13,15,K30",   # 4/4 · lance 3.0
            "W:W18,20,21,24,26,28,29:B1,2,8,9,11,13,16",   # 4/4 · lance 3.0
            "W:W21,22,25,26,29,31:B1,5,7,9,13,14,19,20",   # 4/4 · lance 3.0
            "W:W13,17,21,22,25:B2,3,4,6,10,14,18,20,K31",   # 4/4 · lance 3.0
            "W:W17,18,19,22,24,25,27,28,29,30,31,32:B1,2,4,5,6,7,8,10,11,12,13,15",   # 4/4 · lance 3.0
            "W:W17,20,21,23,24,26,28,29,30,31,32:B1,4,5,7,8,9,10,11,14,15,16",   # 4/4 · lance 3.0
            "W:W13,18,19,20,25,26,27,28,30,31,32:B4,6,7,8,9,10,11,12",   # 3/4 · lance 11.0
            "W:W13,19,20,21,23,24,26,28,32:B2,4,7,8,10,11,12,18",   # 3/4 · lance 11.0
            "W:W13,20,21,22,23,29,30:B10,11,12,14,16,19",   # 3/4 · lance 11.0
            "W:W13,18,19,20,23,26,27,29,30,31:B1,4,5,6,8,9,10,11,12",   # 3/4 · lance 10.3
            "W:W20,26,28,29:B1,4,5,9,13,17,18,19",   # 3/4 · lance 9.7
            "W:W13,19,21,22,25,29,30,32:B2,3,4,6,9,12,14",   # 3/4 · lance 9.7
            "W:W14,18,19,20,28,29,30,31,32:B3,4,5,7,8,10,11,12,13,21",   # 3/4 · lance 9.7
            "W:W18,19,26,28,29,30,31,32:B4,5,8,10,11,12,13,21",   # 3/4 · lance 9.0
            "W:W13,21,22,28,29,31:B6,9,11,14,15,23",   # 3/4 · lance 9.0
            "W:W17,K19,20,21,22,23,24,28,29:B4,9,11,13",   # 3/4 · lance 9.0
            "W:W19,21,23,27,28,29:B8,12,14,16,17,20,22",   # 3/4 · lance 9.0
            "W:W14,15,19,27,28,29:B1,3,4,12,20,26",   # 3/4 · lance 9.0
            "W:WK1,13,19,22,25,28,29,30:B2,4,12,17",   # 3/4 · lance 9.0
            "W:W17,18,19,20,21,22,28:B7,8,10,11,12,13,14",   # 3/4 · lance 9.0
            "W:W13,18,20,23,26,27,29,30,31:B1,4,5,6,8,9,10,11,19",   # 3/4 · lance 8.3
            "W:W17,20,21,22,23,24,26,27,28,29,30:B1,2,5,8,9,10,11,12,13,16",   # 3/4 · lance 8.3
            "W:W20,21,22,23,24,25,27:B11,13,15,16,18",   # 3/4 · lance 7.7
            "W:W14,20,21,27,28,29,31,32:B4,6,8,11,12,13",   # 3/4 · lance 7.0
            "W:W13,17,K19,20,21,27,28:B4,5,7,K8,12",   # 3/4 · lance 7.0
            "W:W15,18,20,21,28,29:B2,3,4,5,12,13",   # 3/4 · lance 7.0
            "W:W14,17,18,20,22,25,26,28:B7,8,10,11,12,13,19",   # 3/4 · lance 7.0
            "W:W17,18,19,20,22:B6,8,9,10,11,12,13",   # 3/4 · lance 7.0
            "W:W13,17,21,28,29,31:B6,9,11,15,18,23",   # 3/4 · lance 7.0
            "W:W15,25,26,27,28:B4,6,8,9,11,12,20",   # 3/4 · lance 7.0
            "W:W17,18,20,22,25,26,28:B6,7,8,10,11,12,19",   # 3/4 · lance 6.3
            "W:W18,19,20,21,23,25,26,27,29,30,31:B1,4,5,6,7,8,9,10,11,12,14",   # 3/4 · lance 5.7
            "W:W14,18,20,21,22,26,28,29:B1,7,8,11,12,13,19",   # 3/4 · lance 5.7
            "W:W14,19,22,24,28,29,30,32:B3,4,6,12,13",   # 3/4 · lance 5.0
            "W:W14,18,21,22,23,26,27,29,30,32:B3,5,6,7,8,9,12,13,16,20,24",   # 3/4 · lance 5.0
            "W:W14,20,23,25,26,28,29,30,31,32:B2,3,7,9,11,12,16",   # 3/4 · lance 5.0
            "W:W19,20,21,23,25,26,29,30,31:B1,3,4,5,7,10,12,14",   # 3/4 · lance 5.0
            "W:WK8,18,20,21,22,23,24,26:B4,5,6,9,10,11,13,15",   # 3/4 · lance 5.0
            "W:W13,14,15,19,23,27,29,30,31:B6,7,8,12,16,20",   # 3/4 · lance 5.0
            "W:W13,17,18,20,22,24,26,28,29,30:B2,5,6,8,9,11,12,15,19",   # 3/4 · lance 5.0
            "W:W15,19,22,23,24,27,28,29,30,32:B3,4,5,6,8,9,12,13,14,16,21",   # 3/4 · lance 4.3
            "W:W18,19,20,21,22,25,29,31,32:B1,3,4,5,7,9,12,13,14",   # 3/4 · lance 3.7
            "W:W13,18,20,22,24,25,26,28,29,30,31,32:B1,3,4,5,6,7,8,9,10,11,15,19",   # 3/4 · lance 3.0
            "W:W13,18,20,22,25,26,28:B6,7,8,11,12,15,19",   # 3/4 · lance 3.0
            "W:W21,22,23,25,27,28,29,31,32:B1,4,5,7,8,9,15,16",   # 3/4 · lance 3.0
            "W:W14,24,28,29,31:B1,4,5,7,8,16,22,K27",   # 3/4 · lance 3.0
            "W:WK17,18,20,21,22,23,24,26:B5,6,8,9,11,13,15",   # 3/4 · lance 3.0
            "W:W14,21,24,28,29,31:B1,4,5,7,8,13,16,K27",   # 3/4 · lance 3.0
            "W:W18,21,24,28,29,31:B1,4,5,7,8,13,16,K32",   # 3/4 · lance 3.0
            "W:W20,21,22,23,25,29,32:B3,4,5,6,11,12,13,14,27",   # 3/4 · lance 3.0
        ),
    ),
    "damas_capturar_multipla": Receita(
        nu_tipo_desafio=8,
        co_tipo_desafio="damas_capturar_multipla",
        co_jogo="damas",
        co_chave_objetivo="desafioObjetivoCapturaMultipla",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("maior_captura", "maior_ou_igual", p["pecas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "pecas": p["pecas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
        # Posicoes REAIS de partidas humanas do `prd`, pescadas em 12/09/2026.
        #
        # ⛔ **O ACERVO SINTETICO SAIU INTEIRO, E A PREMISSA DELE TAMBEM.** Ate
        # 11/09/2026 este comentario dizia que *"este tipo resiste a geracao
        # automatica, e o motivo e o jogo, nao a ferramenta"* — que capturar duas
        # em sequencia ou esta armado de imediato ou nunca acontece. ⚠️ **A
        # pescaria na base de producao desmentiu isso:** era a **fonte**, e nao o
        # jogo. As candidatas sinteticas nasciam de tabuleiros quase vazios
        # (material ~7), onde um Sagaz com espaco de sobra nunca concede cadeia;
        # as posicoes reais tem material **17,3**, e ai a cadeia se forma.
        #
        #     sinteticas (11/09)    939 candidatas → 29 moldes, TODOS em 3 lances
        #     reais      (12/09)  4.090 candidatas → 184 moldes, 87 deles em 4+
        #
        # O funil da pescaria, para quem for repeti-la:
        #
        #     2.741  nunca cumpriram dentro do teto
        #       650  partida ja acabada
        #       291  ja nasciam com a cadeia armada (objetivo no lance 1)
        #       408  passaram a peneira
        #       184  serviram a tres ou mais modalidades (128 servem as quatro)
        #
        # Distancia ate o objetivo, nos 184 pescados (lance medio nas modalidades
        # que cumpriram): 3 lances: 97 · 4: 35 · 5: 30 · 6: 9 · 7: 13.
        #
        # ⛔ **E SO OS 87 DE 4 LANCES OU MAIS ENTRARAM** (decisao do dono,
        # 12/09/2026). A §8j do `DECISOES-do-dono.md` — *"eu aceito que ela pode
        # ser o tipo rapido"* — tinha sido decidida quando **todo** molde cumpria
        # no lance 3, e nao havia escolha a fazer. Com posicoes reais ha: o dono
        # optou por deixar a captura multipla durar como o coroar, e os 97 moldes
        # curtos ficaram de fora.
        #
        # ⚠️ **Eles nao foram apagados** — saem do diario da pescaria a qualquer
        # momento, com o comando abaixo. ⛔ Mas nao voltam por descuido: um molde
        # curto no meio do acervo publica, de vez em quando, o desafio de um toque
        # que a decisao acabou de recusar.
        #
        # ✅ **E o acervo aguenta:** 87 moldes × 4 modalidades = 348 posicoes de
        # partida sem contar a variacao por lance de preparo; com o fator 4,0
        # medido em 11/09 a extrapolacao da ~1.390, contra 460 do acervo antigo —
        # e com solucoes de 4 a 7 lances, onde as antigas tinham 3.
        #
        # ⚠️ **Como refazer** (o diario permite interromper e retomar):
        #
        #     .venv\Scripts\python -u scripts\pescar_moldes_de_partidas.py ^
        #         <csv de lances do prd> --tipo damas_capturar_multipla ^
        #         --processos 14 --bloco
        #
        # O comentario de cada linha e `modalidades validas/4 · lance medio`.
        moldes=(
            "W:W10,13,25,27,28,29,30,31:B1,2,3,5,8,18,19,20",   # 4/4 · lance 7.0
            "W:W20,21,22,28,30,31,32:B1,4,5,7,12,13,15",   # 4/4 · lance 7.0
            "W:W10,17,20,25,26,29,30,31,32:B1,2,3,9,12,18",   # 4/4 · lance 7.0
            "W:W19,20,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,11,12,18",   # 4/4 · lance 7.0
            "W:W5,20,27,29,30,31,32:B1,3,4,11,12,14,19,22",   # 4/4 · lance 7.0
            "W:W9,21,22,25,26,28,29,30,31,32:B1,2,3,4,5,6,8,12,13,16,27",   # 4/4 · lance 6.5
            "W:W18,19,20,21,22,23,25,26,28,29,31,32:B3,4,5,6,7,8,9,10,11,12,13,14",   # 4/4 · lance 6.0
            "W:W18,21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,10,11,12,15",   # 4/4 · lance 6.0
            "W:WK1,14,18,20,26,28,29,32:B3,7,11,12,21",   # 4/4 · lance 6.0
            "W:W14,17,19,22,24,25,27,28,29,30,31,32:B1,2,4,5,7,8,9,10,11,12,13,15",   # 4/4 · lance 5.5
            "W:W18,21,22,24,25,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,10,19,20",   # 4/4 · lance 5.0
            "W:W10,13,21,25,27,28,29,31:B1,2,3,5,16,18,19,20",   # 4/4 · lance 5.0
            "W:W10,13,21,27,28,29,30,31:B1,2,3,5,12,18,19,20",   # 4/4 · lance 5.0
            "W:W10,17,20,21,27,29,31,32:B1,2,3,4,8,12,18",   # 4/4 · lance 5.0
            "W:W20,21,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,14,16",   # 4/4 · lance 5.0
            "W:W10,18,23,24,26,28,29,30,31,32:B1,3,4,5,6,8,11,12,16",   # 4/4 · lance 5.0
            "W:W19,20,21,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,12,18",   # 4/4 · lance 5.0
            "W:W20,21,22,23,27,28,29,30,31,32:B1,2,3,4,5,6,8,12,14,16",   # 4/4 · lance 5.0
            "W:W18,20,21,22,25,26,28,29,30,31,32:B1,2,3,4,5,6,7,9,10,11,12",   # 4/4 · lance 5.0
            "W:W13,17,21,25,26,27:B2,3,4,6,10,14,18,20,24",   # 4/4 · lance 5.0
            "W:WK3,14,18,25,27,28,29,31,32:B1,4,5,6,8,12,13,22,23",   # 4/4 · lance 5.0
            "W:W18,20,21,22,23,25,26,27,28,29,31,32:B1,3,4,5,6,7,8,10,11,12,13,15",   # 4/4 · lance 5.0
            "W:WK8,18,20,21,23,24,25,26:B4,5,6,7,9,11,13,15",   # 4/4 · lance 5.0
            "W:W22,28,29,30,31,32:B1,4,5,8,11,12,18,20",   # 4/4 · lance 5.0
            "W:W12,18,21,22,24,25,29,31,32:B1,2,3,4,8,10,13,15",   # 4/4 · lance 5.0
            "W:W18,19,20,21,29,30:B8,11,12,13",   # 4/4 · lance 5.0
            "W:W20,22,24,25,27,28,29,30,32:B2,3,7,8,9,10,11,14,15,19",   # 4/4 · lance 5.0
            "W:W17,19,21,25,26,27,29,30,31:B1,2,3,4,5,7,8,9,10,12,18",   # 4/4 · lance 5.0
            "W:W18,20,21,22,25,28,31:B3,8,9,11,13,16",   # 4/4 · lance 4.5
            "W:WK12,13,16,21,26,28,29,30,31,32:B1,4,6,7,9,14,15",   # 4/4 · lance 4.0
            "W:W17,19,20,21,24,25,27,28,29,31:B1,2,4,5,7,8,10,11,12,18",   # 4/4 · lance 4.0
            "W:W17,22,23,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,8,9,12,15,16",   # 4/4 · lance 4.0
            "W:W18,21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,9,10,11,12,16",   # 4/4 · lance 4.0
            "W:W21,22,25,26,27,28,29,30,31,32:B1,2,3,4,7,8,12,13,14,15",   # 4/4 · lance 4.0
            "W:W21,22,24,25,27,28,30,31,32:B1,2,3,4,7,8,11,13,14,16,20",   # 4/4 · lance 4.0
            "W:W16,19,20,25,29,30:B2,5,6,7,12,13,17,21,27",   # 4/4 · lance 4.0
            "W:W10,22,24,26,28,30,32:B1,3,4,6,11,13,16",   # 4/4 · lance 4.0
            "W:W20,25,26,27,28,29,31,32:B1,2,3,5,7,8,9,12,17,18",   # 4/4 · lance 4.0
            "W:WK10,14,20,24,29,31,32:B5,8,9,12,18,21,22,K23",   # 4/4 · lance 4.0
            "W:WK10,14,20,24,29,31,32:B5,8,12,13,18,22,K23,25",   # 4/4 · lance 4.0
            "W:W18,20,21,22,23,25,26,27,28,29,30,32:B1,2,4,5,6,7,8,10,11,13,15,16",   # 4/4 · lance 4.0
            "W:W20,21,22,24,25,26,27,29,30,31:B1,2,3,4,5,8,13,14,15",   # 4/4 · lance 4.0
            "W:W19,20,21,22,23,25,26,28,29,30,31,32:B1,2,3,4,6,8,9,10,11,12,13,14",   # 4/4 · lance 4.0
            "W:W15,21,22,23,26,27,28,29,31,32:B1,2,3,4,5,8,12,13,14,20",   # 4/4 · lance 4.0
            "W:WK3,13,21,22,25,26,29,30,31,32:B5,6,9",   # 4/4 · lance 4.0
            "W:WK12,13,16,26,28,29,30,31,32:B1,4,6,7,9,15,21",   # 4/4 · lance 3.5
            "W:W17,20,21,25,26,27,K28,29,32:B2,3,4,9,11,12,18",   # 4/4 · lance 3.5
            "W:W19,21,23,24,26,27,28,31:B1,3,4,5,7,11,12,14,20,K29",   # 4/4 · lance 3.5
            "W:W20,24,K26,29,31:B8,12,13,18,K30,K32",   # 4/4 · lance 3.5
            "W:W13,19,20,21,25,26,27,28,29,31:B1,3,4,5,8,10,12,15,18",   # 4/4 · lance 3.5
            "W:W19,20,21,22,25,26,27,29,30,31,32:B1,2,3,4,5,6,7,8,11,12,14",   # 3/4 · lance 7.0
            "W:W17,18,K19,20,21,22,24,28,29:B8,9,11,13",   # 3/4 · lance 7.0
            "W:WK17,18,28,29,32:B4,11,20",   # 3/4 · lance 7.0
            "W:WK2,11,12,20,29,31:B3,4,5,22",   # 3/4 · lance 7.0
            "W:W19,20,21,22,25,28,29,30,31,32:B1,2,4,5,6,7,10,11,12,14",   # 3/4 · lance 7.0
            "W:W19,22,23,25,29,30,31:B1,3,4,5,10,12,13,15",   # 3/4 · lance 7.0
            "W:W19,20,22,24,25,27,28,29,30,32:B2,3,7,8,9,10,11,12,14,15",   # 3/4 · lance 7.0
            "W:W26,31:B1,2,3,4,5,7,8,10,25,K29",   # 3/4 · lance 7.0
            "W:WK2,21,22,23,24,27,29,30,31,32:B1,3,4,5,8,10,12,14",   # 3/4 · lance 6.3
            "W:W19,21,22,24,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,9,12,15,16",   # 3/4 · lance 6.3
            "W:WK3,13,17,20,24,29,30,31,32:B1,4,5,7,10,11,12,15",   # 3/4 · lance 5.7
            "W:WK3,18,20,21,23,24,25,26:B4,5,6,7,9,10,11,13",   # 3/4 · lance 5.7
            "W:WK12,13,16,26,28,29,31,32:B1,4,6,7,9,15,K30",   # 3/4 · lance 5.0
            "W:W15,18,21,22,27,28,29,31,32:B1,2,3,4,7,9,13,20,26",   # 3/4 · lance 5.0
            "W:W18,21,22,23,28,29,31,32:B1,2,3,4,9,13,16,20,K30",   # 3/4 · lance 5.0
            "W:WK21:B5,K12,13,K18,K26",   # 3/4 · lance 5.0
            "W:WK3:B5,K12,13,K22,K26",   # 3/4 · lance 5.0
            "W:W13,29,31:B4,5,8,15,20,22,K32",   # 3/4 · lance 5.0
            "W:WK5,15,18,29,30,32:B4,11,13,21,24,28",   # 3/4 · lance 5.0
            "W:W20,21,22,25,26,28,29,30,31,32:B1,2,3,4,5,6,8,12,13,16",   # 3/4 · lance 5.0
            "W:WK2,11,20,29,31:B4,5,12,22",   # 3/4 · lance 5.0
            "W:WK2,12,30,31,32:B4,5,13,25,28",   # 3/4 · lance 5.0
            "W:W21,24,28,29,K30,31:B4,6,13",   # 3/4 · lance 5.0
            "W:W23,31:B1,2,3,4,5,7,8,10,K29,K30",   # 3/4 · lance 5.0
            "W:W18,19,21,22,23,25,27,28,29,31,32:B1,2,3,4,5,8,10,11,12,13,16",   # 3/4 · lance 4.3
            "W:W17,22,25,26,28,29,30,31,32:B1,2,3,4,5,6,8,9,16,19",   # 3/4 · lance 4.3
            "W:W17,20,22,24,29,30,31:B2,3,4,5,8,12,13,15,K23",   # 3/4 · lance 4.3
            "W:W15,21,22,23,25,28,29,30,32:B2,4,5,6,7,8,12,13,14,20",   # 3/4 · lance 4.3
            "W:W7,13,15,18,22,23,26,27,28,30:B5,8,9,10,11,12,16,20,21",   # 3/4 · lance 4.3
            "W:W13,14,15,18,22,23,26,27,28,30:B5,6,8,9,10,11,12,16,20,21",   # 3/4 · lance 4.3
            "W:WK3,18,20,21,23,24,29,30:B1,2,4,7,9,10,11,13",   # 3/4 · lance 4.3
            "W:WK3,17,21,23,24,28,29,30,31,32:B2,4,6,10,11,14,15",   # 3/4 · lance 3.7
            "W:W18,21,22,27,28,29,31,32:B1,2,3,4,9,13,16,20,26",   # 3/4 · lance 3.7
            "W:WK3,14,18,19,22,29:B5,6,8,12,13",   # 3/4 · lance 3.7
            "W:WK3,11,15,20,21,28,29,32:B1,2,4,6,9,12,K22",   # 3/4 · lance 3.7
            "W:WK3,18,20,21,22,23,24,26:B4,5,6,9,11,13,14,15",   # 3/4 · lance 3.7
            "W:W18,20,21,22,25,26,27,28,29,30,31,32:B1,2,3,4,5,6,7,8,10,11,13,19",   # 3/4 · lance 3.7
        ),
    ),
    # ═══════════════════════════════════════════════════════════════════════
    # ⚠️ OS DOIS TIPOS DE DAMAS QUE ENTRARAM EM 16/09/2026
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⛔ **Eles estao aqui por CORRECAO DO DONO** (14/09/2026, §8k-12 de
    # `DECISOES-do-dono.md`), e a frase dele explica o resto deste bloco:
    #
    # > *"Por que estamos deixando o sacrificio e sobreviver de fora? Eu nao
    # > decidi isso. Minha decisao e que deveriamos ter a maior variedade
    # > possivel de desafios, que eles sejam resolviveis, nao se repitam."*
    #
    # ⚠️ **Nenhum dos dois custou migracao.** Os numeros 5 e 9 ja estao em
    # `desafio.tb901_tipo_desafio` desde a `0018`; como o tipo 2 do Pontinhos,
    # eles esperavam por uma receita. O que eles custaram foi acervo (duas
    # pescarias novas), chave de i18n e vetor.
    #
    # ✅ **As tres coisas que um tipo precisa, e as datas de cada uma:**
    #
    #     linha na `tb901`   ✅ desde a migracao `0018`
    #     chave nos 3 `.arb` ✅ 14/09/2026
    #     vetor (RF-DES-198) ✅ 16/09/2026 — seis casos, dois deles achando
    #                           defeito real (ver `gerar_vetores_verificacao.py`)
    #
    # ─────────────────────────────────────────────────────────────────────────
    # ⛔ E OS DOIS SAO O MESMO MECANISMO COM O COMPARADOR VIRADO
    # ─────────────────────────────────────────────────────────────────────────
    #
    # ⚠️ **Os numeros do editorial sao RELATIVOS A POSICAO**, como o
    # `acima_do_guloso` do Pontinhos: quem os traduz para teto absoluto e o
    # gerador, que tem as pecas na mao (`editorial.parametros_efetivos`).
    #
    #     sacrificio  `entregar: 1`  →  `material_restante <= M - 1`  EXIGE a perda
    #     sobreviver  `entregar: 2`  →  `material_restante >= M - 2`  LIMITA a perda
    #
    # ⛔ **Um teto fixo escrito a mao mentiria**, e em silencio: os moldes
    # pescados tem de 5 a 12 pecas por lado, entao o mesmo numero publicaria ora
    # um desafio impossivel (dia descoberto semanas depois), ora um que ja nasce
    # cumprido (desafio de um toque). ⚠️ **Nenhum dos dois erros daria excecao.**
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
    # ═══════════════════════════════════════════════════════════════════════
    # ⚠️ OS QUATRO TIPOS DE PONTINHOS QUE ENTRARAM EM 14/09/2026
    # ═══════════════════════════════════════════════════════════════════════
    #
    # ⛔ **Nenhum deles entrou por parecer boa ideia: os quatro foram MEDIDOS**
    # antes, como tipos em avaliacao (`scripts/medir_variantes_do_editorial.py
    # em-avaliacao`), e os numeros estao no editorial de cada um.
    #
    # ⚠️ **Eles nao exigiram codigo Dart nenhum**, e e isso que os tornou os
    # primeiros da fila: as quatro medidas que consultam — `caixas_fechadas`,
    # `caixas_do_adversario`, `lances_do_jogador` e `maior_cadeia_capturada` — ja
    # sao produzidas pelos DOIS medidores. O que eles custaram foi migracao
    # (`0024`), chave de i18n e vetor.
    #
    # ─────────────────────────────────────────────────────────────────────────
    # ⛔ A FAMILIA "IMPECA" / "AGUENTE", E A ARMADILHA QUE ELA TEM
    # ─────────────────────────────────────────────────────────────────────────
    #
    # Dois dos quatro (`nao_entregar` e `paciencia`) pedem que algo **nao
    # aconteca**. ⚠️ **A clausula sozinha nao basta**, e o motivo e do juiz: ele
    # varre a fita e para no **primeiro** lance em que as clausulas valem — e
    # *"o adversario nao fechou caixa"* ja e verdade **antes de ele jogar**.
    #
    # ⛔ Medido em 12/09/2026, antes da correcao: solucao de **1 meio-lance** com
    # qualquer numero no enunciado. Depois: **7** com `turnos: 4`.
    #
    # ✅ **A cura e `lances_do_jogador >= n` na conjuncao**, e ela nao custa
    # vocabulario novo: a conjuncao so pode ficar verdadeira no n-esimo lance.
    # Cadeado em `tests/unitarios/test_tipos_propostos.py`, e ele roda sobre os
    # tipos publicados tambem.
    "pontinhos_nao_entregar": Receita(
        # ⚠️ **O numero 2 e da migracao `0018`** — este tipo ja existia na
        # dimensao desde o inicio, sem receita. Nao houve tipo novo aqui: houve
        # uma receita escrita para uma linha que esperava por ela.
        nu_tipo_desafio=2,
        co_tipo_desafio="pontinhos_nao_entregar",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoNaoEntregar",
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("lances_do_jogador", "maior_ou_igual", p["lances"]),
                _medida("caixas_do_adversario", "menor_ou_igual", 0),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "personagem": personagem,
        },
    ),
    "pontinhos_economia_de_lances": Receita(
        # ⚠️ **14, e nao o proximo numero livre.** A `0023` deixou escrito que
        # os numeros 11 a 21 ja estavam tomados pelas propostas de
        # `job/tipos_propostos.py` - reaproveitar um deles faria duas coisas
        # diferentes responderem pelo mesmo `nu_tipo_desafio` no dia em que a
        # outra proposta fosse aprovada. Este tipo E a proposta 14.
        nu_tipo_desafio=14,
        co_tipo_desafio="pontinhos_economia_de_lances",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoEconomiaDeLances",
        # ⚠️ **A janela conta LANCES, e o `fechar_caixas` conta TURNOS** — e no
        # Pontinhos a diferenca e grande, porque quem fecha caixa joga de novo.
        # ⛔ E por isso os dois nao sao o mesmo tipo com outro nome: um turno
        # generoso cabe muitos lances, e este aqui cobra cada um deles.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "lances_do_jogador", "n": p["lances"]},
            "clausulas": [_medida("caixas_fechadas", "maior_ou_igual", p["caixas"])],
        },
        valores_da_frase=lambda p, personagem: {
            "caixas": p["caixas"],
            "lances": p["lances"],
            "personagem": personagem,
        },
    ),
    "pontinhos_troca_favoravel": Receita(
        nu_tipo_desafio=12,
        co_tipo_desafio="pontinhos_troca_favoravel",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoTrocaFavoravel",
        # ⚠️ **DUAS clausulas, e e a conjuncao que faz o tipo.** *"Feche caixas"*
        # sozinho e o `chegar_ao_placar`; o que transforma isso na decisao real
        # do Pontinhos e o teto do que se cede — porque toda caixa fechada abre
        # a proxima cadeia para o adversario.
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
    "pontinhos_paciencia": Receita(
        nu_tipo_desafio=15,
        co_tipo_desafio="pontinhos_paciencia",
        co_jogo="pontinhos",
        co_chave_objetivo="desafioObjetivoPaciencia",
        # ⛔ **O objetivo e nao fazer NADA** — nem fechar, nem ceder —, e ele
        # ensina a regra central do Pontinhos: quem for forcado a abrir a cadeia
        # perde. ⚠️ **Precisa das tres clausulas**: sem `caixas_fechadas == 0`,
        # quem fechasse tudo cumpriria; sem `lances_do_jogador`, cumpriria quem
        # nao fizesse lance nenhum.
        montar=lambda p: {
            "versao": VERSAO_CHEGADA,
            "janela": {"tipo": "partida"},
            "clausulas": [
                _medida("lances_do_jogador", "maior_ou_igual", p["lances"]),
                _medida("caixas_do_adversario", "menor_ou_igual", 0),
                _medida("caixas_fechadas", "igual", 0),
            ],
        },
        valores_da_frase=lambda p, personagem: {
            "lances": p["lances"],
            "personagem": personagem,
        },
    ),
}


def receita_de(co_tipo_desafio: str) -> Receita:
    """A receita de um tipo. Falha alto se ele nao tiver uma.

    Raises:
        TipoSemReceita: sempre que o tipo nao estiver em [RECEITAS].
    """
    if co_tipo_desafio not in RECEITAS:
        raise TipoSemReceita(
            f"o tipo {co_tipo_desafio!r} nao tem receita. ⛔ Tipo sem receita nao "
            "e publicavel: o desafio sairia com uma linha de chegada que ninguem "
            "escreveu, e o julgamento devolveria 'nao cumpriu' para todo mundo. "
            f"Os que tem receita hoje: {sorted(RECEITAS)}"
        )
    return RECEITAS[co_tipo_desafio]


def tipos_do_jogo(co_jogo: str) -> list[str]:
    """Os tipos publicaveis daquele jogo, em ordem estavel.

    ⚠️ Ordem estavel importa: e ela que faz o rodizio ser reproduzivel, e um
    rodizio que muda de ordem a cada execucao publicaria o mesmo tipo dois dias
    seguidos de vez em quando.
    """
    return sorted(
        codigo for codigo, receita in RECEITAS.items() if receita.co_jogo == co_jogo
    )
