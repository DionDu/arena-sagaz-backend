"""Quem PERSEGUE o objetivo do desafio no Quatro em Linha, com nivel (T124c, defeito 1).

═══════════════════════════════════════════════════════════════════════════
O DEFEITO QUE ISTO ATACA
═══════════════════════════════════════════════════════════════════════════

A regua de 20/10/2026 (historico do backend, "2026-10-20 (5)") mediu os dez
tipos do Quatro com os personagens jogando para VENCER - eles nao leem o
objetivo. Em seis tipos o objetivo e um JEITO de vencer (pela diagonal, com
duas linhas no mesmo lance, com cinco em linha, sem a coluna do meio, com as
pecas encostadas) ou de jogar (bloquear tres ameacas sem perder), e ali a
escada mediu o cumprimento POR ACASO: *"0 de 3" e NAO MEDIDO, e nao "dificil"*
(correcao do dono, 20/10). E a mesma forma do 18/09 das damas
(`motores/damas/perseguir_coroacao.py`).

═══════════════════════════════════════════════════════════════════════════
O DESENHO, E POR QUE ELE E BARATO DE PROPOSITO
═══════════════════════════════════════════════════════════════════════════

⛔ **Nada aqui reescreve uma regra.** Quem diz se um lance cumpre o objetivo e o
MEDIDOR DE PRODUCAO (`feitos_quatro.medir` + `avaliar` da linha de chegada), o
mesmo que julga a pessoa; quem diz se um lance e legal ou encerra a partida e o
arbitro (`MotorQuatro`). Este modulo so ESCOLHE entre os lances, em quatro
passos:

  1. o lance que cumpre o objetivo agora, se houver, e jogado;
  2. o lance que ENCERRA a partida sem o objetivo (a vitoria do jeito errado,
     a ultima casa) sai da lista - ganhar pela horizontal num desafio de
     diagonal e perder o desafio;
  3. o lance que deixa ao adversario uma vitoria imediata sai da lista (e e
     isso que faz o perseguidor bloquear);
  4. entre os que sobram, a NOTA DO OBJETIVO (uma funcao por tipo, abaixo)
     escolhe.

⚠️ **O nivel e uma MISTURA, e nao um segundo motor.** Com a probabilidade
[PROBABILIDADE_DE_PERSEGUIR] do nivel, o lance e o de perseguir (os quatro
passos); senao, e o lance que o motor Dart daria naquele nivel, CRU, com os
erros que a politica de dificuldade ja tem (v3: filtra-lo dava competencia a
Cacau, ver `lance_de_quem_persegue`). E o lance de perseguir consulta a
busca do executavel (ver `lance_de_quem_persegue`: a v1 so com a nota reprovou
no controle). Os numeros sao o palpite de partida, e
⛔ **nada disto entra em `gerador.SOLUCIONADOR_POR_TIPO` antes da medicao pareada
e com controle** (`scripts/medir_perseguir_vs_vencer_quatro.py`): um
perseguidor que vence MENOS que o Magno no objetivo facil (vencer, so) nao mede
o dificil - mede a propria incompetencia.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from motores.nucleo.chegada import LinhaDeChegada, avaliar
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import distancia_da_figura_quatro, feitos_quatro
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, TabuleiroQuatro

#: Com que frequencia cada nivel joga o lance que persegue o objetivo (o resto
#: e o lance do proprio nivel no motor). ⚠️ Palpite de partida, a medir.
PROBABILIDADE_DE_PERSEGUIR: dict[NivelDeMotor, float] = {
    NivelDeMotor.CACAU: 0.25,
    NivelDeMotor.PITA: 0.50,
    NivelDeMotor.TEX: 0.80,
    NivelDeMotor.SAGAZ: 1.00,
}

#: As quatro direcoes de uma linha: vertical, horizontal e as duas diagonais.
DIRECOES = ((0, 1), (1, 0), (1, 1), (1, -1))

#: So as duas diagonais (o `quatro_vencer_diagonal`).
DIAGONAIS = ((1, 1), (1, -1))

#: Os tipos cujo objetivo NAO e um jeito de vencer, e que fecham no meio da
#: partida (T143 e T148, §8zzzr): o "Encoste" e o "Forme a figura". ⚠️ Neles o
#: ramo de perseguir nao espera uma vitoria provada para se afastar do lance do
#: nivel: vencer nao e o objetivo, e esperar por ela faria o perseguidor jogar
#: como quem so quer vencer (ver `lance_de_quem_persegue`).
FECHAM_NO_MEIO = frozenset({"quatro_encoste", "quatro_figura"})

#: O peso de um lugar da figura que falta uma casa (`_potencial_da_figura`). ⚠️
#: Alto contra o `comum` (que raramente passa de algumas dezenas), como as
#: encostadas no "Encoste": o prazo e curto, e o `comum` so desempata.
PESO_DA_FIGURA = 1_000

#: Os tipos em que o ramo de perseguir NAO consulta a prova (T148). ⚠️ No "Forme
#: a figura" ela atrapalha: a prova e jogo perfeito, e nas posicoes do acervo
#: (Magno x Tex, ja decididas) ela deixa poucos lances "nao perdidos", quase
#: nenhum que constroi a figura. Medido em 23/10/2026 no controle (quadrado e
#: L, folga 3, 30 posicoes, contra a Cacau e o Tex): sem a prova o Magno formou
#: 23 a 25 de 30; com ela, 20 a 23. O passo 3 (nao entregar a vitoria pronta)
#: continua valendo.
TIPOS_SEM_A_PROVA = frozenset({"quatro_figura"})

#: Quem responde "esta posicao e perdida a forca para quem tem a vez?". Na
#: producao e o `ProvadorQuatro` (a busca do executavel); `None` desliga o passo.
Prova = Callable[[EstadoQuatro], "int | None"]


@dataclass(frozen=True)
class Desafio:
    """O que o perseguidor precisa saber do desafio, uma vez por partida.

    Atributos:
        co_tipo: o tipo do desafio (escolhe a nota do objetivo).
        iniciais: a posicao publicada, um lance por item.
        chegada: a linha de chegada (a da receita, ja com os parametros).
        pessoa: quem resolve (`+1`/`-1`): quem tem a vez na posicao publicada.
    """

    co_tipo: str
    iniciais: tuple[str, ...]
    chegada: LinhaDeChegada
    pessoa: int


def desafio_de(
    motor: MotorQuatro,
    co_tipo: str,
    iniciais: Sequence[str],
    js_chegada: Mapping[str, Any],
) -> Desafio:
    """Monta o [Desafio], com a pessoa lida do arbitro (a vez na posicao)."""
    estado = EstadoQuatro(motor.co_modalidade, tuple(iniciais))
    return Desafio(
        co_tipo=co_tipo,
        iniciais=tuple(iniciais),
        chegada=LinhaDeChegada.de_dado(js_chegada),
        pessoa=motor.vez_de(estado),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Os passos 1 a 3: o que o medidor e o arbitro respondem
# ─────────────────────────────────────────────────────────────────────────────


def cumpre(motor: MotorQuatro, desafio: Desafio, fita: Sequence[str]) -> bool:
    """A fita ja cumpre o objetivo? A mesma pergunta do juiz, no fim da fita.

    ⚠️ O juiz pergunta a cada lance da pessoa e para no primeiro que cumpre; o
    perseguidor so precisa saber do lance que esta escolhendo, que e o ultimo.
    """
    medidas = feitos_quatro.medir(
        motor, desafio.iniciais, fita, jogador=desafio.pessoa
    )
    predicados = feitos_quatro.responder_predicados(motor, desafio.iniciais, fita)
    # A grade so quando ha `figura` (T148): o juiz a pede por uma porta propria,
    # e montar o tabuleiro custa uma reproducao da fita a mais.
    grade = (
        feitos_quatro.grade(motor, desafio.iniciais, fita)
        if desafio.chegada.figuras
        else None
    )
    return avaliar(
        desafio.chegada,
        medidas,
        predicados=predicados,
        grade=grade,
        jogador=desafio.pessoa,
    )


def _vitoria_imediata(motor: MotorQuatro, estado: EstadoQuatro, quem: int) -> bool:
    """[quem] tem, NESTE tabuleiro e com a vez, um lance que vence?

    ⚠️ A vez no [estado] tem de ser de [quem]: o arbitro so aplica o lance de
    quem tem a vez.
    """
    for lance in motor.lances_legais(estado):
        desfecho = motor.desfecho(estado.com_lance(lance))
        if desfecho is not None and desfecho.vencedor == quem:
            return True
    return False


def candidatos(
    motor: MotorQuatro,
    desafio: Desafio,
    fita: Sequence[str],
) -> tuple[str | None, list[str]]:
    """Os passos 1 a 3: `(lance que cumpre agora, lances que sobram)`.

    Os lances que sobram nunca ficam vazios enquanto houver lance legal: se o
    filtro tirar todos, volta-se ao passo anterior (melhor perder jogando do
    que nao ter lance).
    """
    estado = EstadoQuatro(motor.co_modalidade, desafio.iniciais + tuple(fita))
    legais = motor.lances_legais(estado)
    # ⚠️ No "sem o meio" a coluna central nao e lance da pessoa: jogar nela ja
    # e falhar o desafio (`lances_na_coluna_central <= 0`).
    if desafio.co_tipo == "quatro_sem_o_meio":
        meio = _coluna_do_meio(motor)
        fora_do_meio = [l for l in legais if _coluna(l) != meio]
        legais = fora_do_meio or legais

    vivos: list[str] = []
    for lance in legais:
        depois = list(fita) + [lance]
        if cumpre(motor, desafio, depois):
            return lance, [lance]
        # Passo 2: acabar a partida sem o objetivo e perder o desafio.
        if not _acabou(motor, estado.com_lance(lance)):
            vivos.append(lance)
    vivos = vivos or legais

    # Passo 3: o lance que deixa a vitoria pronta para o adversario.
    seguros = [
        l
        for l in vivos
        if not _vitoria_imediata(motor, estado.com_lance(l), -desafio.pessoa)
    ]
    return None, seguros or vivos


def _acabou(motor: MotorQuatro, estado: EstadoQuatro) -> bool:
    """A partida acabou (vitoria ou tabuleiro cheio)? Nao ha lance legal."""
    return not motor.lances_legais(estado)


# ─────────────────────────────────────────────────────────────────────────────
# O passo 4: a nota do objetivo, uma por tipo
# ─────────────────────────────────────────────────────────────────────────────


def _coluna(lance: str) -> int:
    """`s4` → 4: a coluna do lance (a letra e o tipo, o numero a coluna)."""
    return int(lance[1:])


def _coluna_do_meio(motor: MotorQuatro) -> int | None:
    """A coluna do meio, so em largura impar (a mesma conta do medidor)."""
    largura = motor.regras.dimensoes.largura
    return (largura + 1) // 2 if largura % 2 == 1 else None


def _janelas(
    motor: MotorQuatro, tamanho: int, direcoes: Sequence[tuple[int, int]]
) -> list[tuple[tuple[int, int], ...]]:
    """Todas as janelas de [tamanho] casas em linha, nas [direcoes].

    Uma janela e uma tupla de casas `(coluna, linha)`, contadas a partir de 1,
    como o arbitro as conta. ⚠️ Recalculada por chamada, mas e barata (69
    janelas de 4 no 7 x 6).
    """
    dimensoes = motor.regras.dimensoes
    janelas = []
    for dc, dl in direcoes:
        for coluna in range(1, dimensoes.largura + 1):
            for linha in range(1, dimensoes.altura + 1):
                casas = tuple(
                    (coluna + dc * i, linha + dl * i) for i in range(tamanho)
                )
                if all(
                    1 <= c <= dimensoes.largura and 1 <= l <= dimensoes.altura
                    for c, l in casas
                ):
                    janelas.append(casas)
    return janelas


def _potencial(
    motor: MotorQuatro,
    tabuleiro: TabuleiroQuatro,
    cor: int,
    *,
    tamanho: int = 4,
    direcoes: Sequence[tuple[int, int]] = DIRECOES,
    proibida: int | None = None,
) -> float:
    """O quanto a [cor] esta perto de fechar janelas: a soma de `pecas²`.

    So contam as janelas sem peca do adversario (as que ainda podem fechar). O
    quadrado faz tres pecas numa janela valerem mais que tres janelas com uma.
    ⚠️ [proibida]: uma coluna que a [cor] nao pode usar (o "sem o meio"); janela
    que precisa de uma casa VAZIA nela nao conta.
    """
    total = 0.0
    for janela in _janelas(motor, tamanho, direcoes):
        pecas = [tabuleiro.peca(casa) for casa in janela]
        if -cor in pecas:
            continue
        if proibida is not None and any(
            p == 0 and casa[0] == proibida for p, casa in zip(pecas, janela)
        ):
            continue
        total += pecas.count(cor) ** 2
    return total


def _pontos_de_golpe_duplo(
    motor: MotorQuatro, tabuleiro: TabuleiroQuatro, cor: int
) -> int:
    """Casas vazias em que UMA peca da [cor] fecharia duas linhas de uma vez."""
    contagem: dict[tuple[int, int], int] = {}
    for janela in _janelas(motor, 4, DIRECOES):
        pecas = [tabuleiro.peca(casa) for casa in janela]
        if pecas.count(cor) == 3 and pecas.count(0) == 1:
            vazia = janela[pecas.index(0)]
            contagem[vazia] = contagem.get(vazia, 0) + 1
    return sum(1 for n in contagem.values() if n >= 2)


def _vence_ali(
    motor: MotorQuatro, tabuleiro: TabuleiroQuatro, lance: tuple[str, int], quem: int
) -> bool:
    """[quem] venceria pondo a peca em [lance], neste [tabuleiro], se fosse a vez dele?

    ⚠️ `dataclasses.replace` faz uma COPIA do tabuleiro com outro campo (a vez):
    o arbitro so poe a peca de quem tem a vez, e aqui a vez e do adversario.
    """
    regras = motor.regras
    desfecho = regras.desfecho(regras.aplicar(replace(tabuleiro, vez=quem), lance))
    return desfecho is not None and desfecho.vencedor == quem


def _soma_dos_lugares(
    motor: MotorQuatro, tabuleiro: TabuleiroQuatro, desafio: Desafio
) -> float:
    """Todos os lugares da figura somados: cada um vale `PESO_DA_FIGURA / 3**custo`.

    A 1 casa, 333; a 2, 111; a 3, 37. ⚠️ A soma, e nao so o lugar mais perto: com
    o mais perto, os lances que nao o mudam valem todos igual, e quem escolhe
    entre eles e o `comum` (jogar bem), e nao a figura. Medido em 23/10/2026 no
    controle (quadrado e L, folga 3, 30 posicoes): a soma e o mais perto
    deram o mesmo (19 e 20 de 30 no quadrado, 22 e 21 no L) - ela fica porque
    da direcao onde o mais perto empata, e nao porque mediu melhor. E a mesma
    ideia do [_potencial] das linhas, que soma todas as janelas abertas.
    """
    dimensoes = motor.regras.dimensoes
    total = 0.0
    for figura in desafio.chegada.figuras:
        for custo in distancia_da_figura_quatro.custos(
            figura.desenho, figura.espelhar, tabuleiro, dimensoes, desafio.pessoa
        ):
            total += PESO_DA_FIGURA / 3**custo
    return total


def _potencial_da_figura(
    motor: MotorQuatro, tabuleiro: TabuleiroQuatro, desafio: Desafio
) -> float:
    """O quanto o [tabuleiro] aproxima a pessoa da figura, DEPOIS do bloqueio.

    [tabuleiro] e o de depois do lance da pessoa (a vez e do adversario). ⚠️
    **O modo de falha que isto ataca** (o rastro do controle, 23/10/2026): o
    adversario nao le o objetivo, mas bloqueia toda vitoria pronta, como
    qualquer motor. Isso so derruba a figura num caso estreito: quando a casa
    que FALTA a figura e a 4a de uma linha que uma peca que JA estava no
    tabuleiro completa (a posicao #14 do L: X nas linhas 1 a 3 da coluna 3, e
    o unico L possivel pedia a casa (3, 4), a 4a da vertical). ⛔ O bloqueio na
    ponta da propria figura nao a desfaz: a figura ja esta formada. Entao,
    quando o lance deixa a pessoa com UMA casa de vitoria, a nota e a do
    tabuleiro depois do bloqueio nela; com duas ou mais, o adversario nao
    bloqueia tudo, e a nota e a de agora.

    ⚠️ Esta previsao mediu o mesmo que a soma sem ela (23 a 25 de 30 no
    controle): ela nao prova que esse caso e a causa das falhas (historico do
    backend "2026-10-23 (3)").

    ⚠️ Os `X` sao da PESSOA, passada explicita: neste tabuleiro a vez ja e do
    adversario.
    """
    regras = motor.regras
    bloqueios = [
        lance
        for lance in regras.lances_legais(tabuleiro)
        if _vence_ali(motor, tabuleiro, lance, desafio.pessoa)
    ]
    if len(bloqueios) == 1:
        tabuleiro = regras.aplicar(tabuleiro, bloqueios[0])
    return _soma_dos_lugares(motor, tabuleiro, desafio)


def nota_do_objetivo(
    motor: MotorQuatro, tabuleiro: TabuleiroQuatro, desafio: Desafio
) -> float:
    """O quanto o [tabuleiro] aproxima a pessoa do objetivo do tipo.

    ⚠️ Cada tipo soma o seu termo PRINCIPAL e um pouco do potencial comum de
    vencer: sem o segundo, o perseguidor montaria a diagonal e perderia a
    partida antes de fecha-la.
    """
    eu = desafio.pessoa
    comum = _potencial(motor, tabuleiro, eu) - _potencial(motor, tabuleiro, -eu)
    tipo = desafio.co_tipo
    if tipo == "quatro_vencer_diagonal":
        return 4 * _potencial(motor, tabuleiro, eu, direcoes=DIAGONAIS) + comum
    if tipo == "quatro_linha_de_cinco":
        return 4 * _potencial(motor, tabuleiro, eu, tamanho=5) + comum
    if tipo == "quatro_golpe_duplo":
        return 40 * _pontos_de_golpe_duplo(motor, tabuleiro, eu) + comum
    if tipo == "quatro_encostadas":
        encostadas = feitos_quatro.pecas_encostadas(
            motor.regras.dimensoes, tabuleiro, eu
        )
        return 10 * encostadas + comum
    if tipo == "quatro_encoste":
        # ⚠️ As encostadas MANDAM (100 por peca, contra o `comum`, que raramente
        # passa de algumas dezenas): o prazo e curto, e um lance gasto em jogar
        # bem e um lance a menos para o alvo. O `comum` so desempata - e o
        # passo 3 ja tira o lance que entrega a vitoria ao adversario. Juntar
        # uma peca solta vale 200 (a nova e a solta passam a contar), e jogar
        # colado 100: e isso que faz o perseguidor procurar as soltas.
        encostadas = feitos_quatro.pecas_encostadas(
            motor.regras.dimensoes, tabuleiro, eu
        )
        return 100 * encostadas + comum
    if tipo == "quatro_figura":
        return _potencial_da_figura(motor, tabuleiro, desafio) + comum
    if tipo == "quatro_sem_o_meio":
        meio = _coluna_do_meio(motor)
        return _potencial(motor, tabuleiro, eu, proibida=meio) - _potencial(
            motor, tabuleiro, -eu
        )
    # O resto (o "bloquear", e o "vencer, so" do controle): jogar bem.
    return comum


# ─────────────────────────────────────────────────────────────────────────────
# O lance
# ─────────────────────────────────────────────────────────────────────────────


def lance_de_quem_persegue(
    motor: MotorQuatro,
    desafio: Desafio,
    fita: Sequence[str],
    *,
    nivel: NivelDeMotor,
    sorteio: random.Random,
    lance_do_nivel: Callable[[], str],
    prova: Prova | None = None,
) -> str:
    """O lance de quem persegue o objetivo, no [nivel].

    Args:
        motor: o arbitro da modalidade.
        desafio: o desafio (tipo, posicao publicada, chegada, pessoa).
        fita: os lances desde a posicao publicada, dos dois lados.
        nivel: o degrau do personagem que esta resolvendo.
        sorteio: o `random.Random` desta partida (semeado por quem chama: a
            mesma semente da a mesma partida).
        lance_do_nivel: devolve o lance que o motor Dart daria neste nivel. ⚠️
            Uma funcao, e nao o lance: so e chamada quando o sorteio manda, e
            cada chamada custa uma ida ao executavel.
        prova: o vencedor provado de uma posicao, ou `None` (ver [Prova]).
            Consultada so quando o lance e o de perseguir (nao na mistura).
    """
    # ── A mistura do nivel: o lance do proprio nivel, CRU ───────────────────
    #
    # ⚠️ **A v2 filtrava tambem este lance** (passos 1 a 3), e a regua de
    # 21/10/2026 mostrou o efeito: a Cacau resolvia 0,40 a 0,80 (o teto dela e
    # 0,20), porque os filtros SAO competencia - nunca entregar a vitoria, nunca
    # perder o objetivo que esta na mesa - e a v2 os dava a todos os niveis. Na
    # v3 o lance de quando o nivel nao persegue e o do motor, com os erros dele;
    # os filtros e a prova sao so do ramo de perseguir. O Magno (que persegue
    # sempre) nao muda, e o controle continua o mesmo.
    if sorteio.random() >= PROBABILIDADE_DE_PERSEGUIR[nivel]:
        return lance_do_nivel()

    agora, lances = candidatos(motor, desafio, fita)
    if agora is not None:
        return agora

    # O lance do nivel custa uma ida ao executavel: pedido no maximo uma vez.
    guardado: list[str] = []

    def do_nivel() -> str:
        if not guardado:
            guardado.append(lance_do_nivel())
        return guardado[0]

    estado = EstadoQuatro(motor.co_modalidade, desafio.iniciais + tuple(fita))

    # ⚠️ **A v1 (so a nota) reprovou no controle** em 21/10/2026: perseguindo
    # "so vencer", venceu 111 de 174 partidas contra 140 do Magno - uma heuristica
    # de um lance joga pior que a busca. A v2 so se afasta do motor onde isso NAO
    # custa: quando a busca PROVA vitoria em algum lance, escolhe entre os que
    # vencem o que mais aproxima do objetivo; sem vitoria provada, joga o lance
    # do nivel, tirando so os provadamente perdidos.
    #
    # ⚠️ **Nos tipos que fecham no meio** ([FECHAM_NO_MEIO]) a prova so tira os
    # lances provadamente perdidos, e a nota escolhe entre os outros: o objetivo
    # nao e vencer, entao nem a vitoria provada nem o lance do nivel tem
    # prioridade sobre ele. Sem isso o perseguidor do "Encoste" jogaria o lance
    # do nivel quase sempre (sem vitoria provada a vista), e mediria o nivel
    # jogando para vencer - o defeito que este modulo veio atacar.
    if desafio.co_tipo in TIPOS_SEM_A_PROVA:
        prova = None
    if prova is not None and desafio.co_tipo in FECHAM_NO_MEIO:
        resultado = {l: prova(estado.com_lance(l)) for l in lances}
        lances = [l for l in lances if resultado[l] != -desafio.pessoa] or lances
    elif prova is not None:
        resultado = {l: prova(estado.com_lance(l)) for l in lances}
        vencem = [l for l in lances if resultado[l] == desafio.pessoa]
        if vencem:
            lances = vencem
        else:
            vivos = [l for l in lances if resultado[l] != -desafio.pessoa] or lances
            if do_nivel() in vivos:
                return do_nivel()
            lances = vivos

    notas = {
        lance: nota_do_objetivo(motor, motor.tabuleiro(estado.com_lance(lance)), desafio)
        for lance in lances
    }
    melhor = max(notas.values())
    # Empate de nota: o sorteio da partida escolhe (determinista pela semente).
    return sorteio.choice(sorted(l for l, n in notas.items() if n == melhor))
