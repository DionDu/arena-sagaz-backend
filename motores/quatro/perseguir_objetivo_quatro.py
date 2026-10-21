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
[PROBABILIDADE_DE_PERSEGUIR] do nivel, o lance e o do passo 4; senao, e o lance
que o motor Dart daria naquele nivel (se ele sobreviver aos passos 2 e 3), com
os erros que a politica de dificuldade ja tem. E o lance de perseguir consulta a
busca do executavel (ver `lance_de_quem_persegue`: a v1 so com a nota reprovou
no controle). Os numeros sao o palpite de partida, e
⛔ **nada disto entra em `gerador.SOLUCIONADOR_POR_TIPO` antes da medicao pareada
e com controle** (`scripts/medir_perseguir_vs_vencer_quatro.py`): um
perseguidor que vence MENOS que o Magno no objetivo facil (vencer, so) nao mede
o dificil - mede a propria incompetencia.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from motores.nucleo.chegada import LinhaDeChegada, avaliar
from motores.nucleo.papeis import NivelDeMotor
from motores.quatro import feitos_quatro
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
    return avaliar(desafio.chegada, medidas, predicados=predicados)


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
    agora, lances = candidatos(motor, desafio, fita)
    if agora is not None:
        return agora

    # O lance do nivel custa uma ida ao executavel: pedido no maximo uma vez.
    guardado: list[str] = []

    def do_nivel() -> str:
        if not guardado:
            guardado.append(lance_do_nivel())
        return guardado[0]

    # A mistura do nivel: o lance do proprio nivel, se ele sobreviveu aos filtros.
    if sorteio.random() >= PROBABILIDADE_DE_PERSEGUIR[nivel]:
        if do_nivel() in lances:
            return do_nivel()

    estado = EstadoQuatro(motor.co_modalidade, desafio.iniciais + tuple(fita))

    # ⚠️ **A v1 (so a nota) reprovou no controle** em 21/10/2026: perseguindo
    # "so vencer", venceu 111 de 174 partidas contra 140 do Magno - uma heuristica
    # de um lance joga pior que a busca. A v2 so se afasta do motor onde isso NAO
    # custa: quando a busca PROVA vitoria em algum lance, escolhe entre os que
    # vencem o que mais aproxima do objetivo; sem vitoria provada, joga o lance
    # do nivel, tirando so os provadamente perdidos.
    if prova is not None:
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
