"""O MOLDE NAO PODE ENTREGAR O OBJETIVO NO PRIMEIRO LANCE (T049g).

═══════════════════════════════════════════════════════════════════════════
⚠️ O DEFEITO, E POR QUE A CACADA NAO O PEGAVA
═══════════════════════════════════════════════════════════════════════════

`scripts/cacar_moldes_damas.py` mede um molde pondo o **Sagaz para jogar os dois
lados** e anotando em que lance o objetivo caiu. Moldes que cumpriam no lance 1
eram descartados (`trivial_no_lance_1`), e isso parecia bastar.

⛔ **Nao bastava, e a razao e sutil: o Sagaz joga a PARTIDA, nao o DESAFIO.** Ele
escolhe o melhor lance para vencer — e coroar de cara costuma ser mau lance, uma
pedra que avanca sozinha e e capturada na resposta. Entao a medicao dizia
*"objetivo no lance 3"* em posicoes onde ⚠️ **qualquer pessoa coroa no lance 1**,
porque a pessoa nao esta jogando para vencer: esta cumprindo a tarefa.

Medido em 11/09/2026, depois da cacada de 300: **10 dos 171 moldes de coroar** e
**3 dos 12 de captura** entregavam o objetivo no primeiro lance. Tres deles sao os
fundadores escritos a mao em 09/09, e os outros passaram pela peneira do Sagaz.

⚠️ **O desafio sairia bem formado**: posicao legal, solucao encontrada, regua
medida, XP calculado. So que resolvido no primeiro toque — e ⛔ nada no log
acusaria.

═══════════════════════════════════════════════════════════════════════════
A PERGUNTA CERTA E DIRETA, E NAO CUSTA BUSCA NENHUMA
═══════════════════════════════════════════════════════════════════════════

*"Existe um lance legal, agora, que cumpre o objetivo?"* — uma geracao de lances
por modalidade, sem um no de busca. Por isso ela cabe **na suite** (cadeado
permanente em `tests/unitarios/test_moldes_de_damas.py`) **e** na peneira do
script, antes de gastar o Sagaz.

⛔ **Um modulo so, e nao uma copia em cada lado.** O script cacaria com um
criterio e o cadeado guardaria com outro; no dia em que os dois discordassem,
quem estivesse errado mandaria — e o projeto ja tem a cicatriz dessa especie de
defeito em `leitura_de_migracao.py`.

⚠️ **E a pergunta e feita nas QUATRO modalidades.** A peneira do script roda so na
brasileira, e foi assim que dois moldes entraram com a portuguesa cumprindo no
lance 1: publicariam um desafio de um lance **num dia de cada quatro**.

═══════════════════════════════════════════════════════════════════════════
⛔ 11/09/2026, A NOITE — O CADEADO ESTAVA OLHANDO A POSICAO ERRADA
═══════════════════════════════════════════════════════════════════════════

A primeira execucao no Railway publicou `72542794` com **solucao de um lance**
(`21x30x23`), depois de todos os moldes triviais terem sido removidos. Nao foi
regressao: o cadeado nunca cobriu a posicao que vai ao ar.

⚠️ **O que o job publica NAO e o molde.** O molde e a posicao de onde se parte;
sobre ela o gerador joga **um lance de variacao** (`gerador._preparar_damas`), e
e o resultado disso que vira `js_posicao_inicial`. Um lance basta para armar uma
cadeia de captura que o molde nao tinha.

⛔ **E o lance de variacao troca o lado a jogar.** O molde tem as brancas a jogar
(`W:`); depois de um lance, quem joga sao as **pretas** — e e com elas que a
pessoa resolve o desafio (`vez_de: -1` em toda linha de damas ja gravada).
⚠️ **Entao este modulo, escrito para perguntar "as brancas cumprem?", perguntava
pelo lado que nao resolve nada.**

✅ **As duas coisas foram corrigidas juntas**, porque uma sozinha nao resolve:

  1. as perguntas passaram a ser sobre **quem esta a jogar** na FEN recebida —
     `_lado_e_adversario` —, o que as torna validas para molde **e** para posicao
     publicada;
  2. o gerador passou a fazer a pergunta **na posicao preparada**, descartando a
     tentativa em vez de publica-la (o cadeado do molde continua, como peneira
     barata: recusar cedo poupa a variacao inteira).
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence

from motores.damas.motor_damas import EstadoDamas, MotorDamas

#: As quatro modalidades do rodizio — os moldes servem a todas.
MODALIDADES = ("brasileira", "anglo", "portuguesa", "casa")


def _campos(fen: str) -> tuple[str, list[str], list[str]]:
    """Quebra a FEN em `(lado_a_jogar, brancas, pretas)`.

    ⚠️ **O primeiro campo e o LADO A JOGAR, e nao uma cor de peca** — `B:W...:B...`
    quer dizer "pretas jogam". Confundir os dois faz um `startswith("B")` casar
    com o campo errado e contar zero peca preta, o que transforma qualquer lance
    numa captura de quatro. (Aconteceu ao escrever este modulo, em 11/09/2026.)
    """
    lado, brancas, pretas = fen.split(":")
    partir = lambda campo: [x for x in campo[1:].split(",") if x.strip()]
    return lado, partir(brancas), partir(pretas)


def _lado_e_adversario(antes: str) -> tuple[int, int]:
    """Os indices de `_campos` de **quem joga** e de quem sofre.

    ⚠️ **Quem cumpre o objetivo e quem esta a jogar**, e nas damas do desafio isso
    quase nunca e o branco: o molde tem `W:`, o gerador joga um lance de
    variacao, e a posicao publicada sai com as **pretas** a jogar. Perguntar
    sempre pelas brancas — como este modulo fazia ate 11/09/2026 a noite — e
    perguntar pelo lado que nao resolve o desafio.

    Returns:
        `(indice_de_quem_joga, indice_do_adversario)` em `_campos`, onde 1 sao as
        brancas e 2 as pretas.
    """
    lado = _campos(antes)[0]
    return (1, 2) if lado.upper().startswith("W") else (2, 1)


def _coroou(antes: str, depois: str) -> bool:
    """Quem jogou ganhou uma dama neste lance?

    ⚠️ **Pergunta-se a POSICAO RESULTANTE, e nao a notacao.** Contar casas de
    chegada em `{1,2,3,4}` erraria nas regras em que uma captura que **atravessa**
    a ultima fileira nao coroa — e acertar por acidente seria pior, porque a
    proxima modalidade mudaria a resposta sem ninguem perceber.

    ⚠️ E contam-se as damas **do lado que jogou**: as casas de coroacao de um sao
    as de partida do outro, entao olhar o campo errado nunca acusa nada.
    """
    meu, _ = _lado_e_adversario(antes)
    damas = lambda fen: sum(
        1 for casa in _campos(fen)[meu] if casa.upper().startswith("K")
    )
    return damas(depois) > damas(antes)


def _capturou_duas(antes: str, depois: str) -> bool:
    """O lance tirou duas ou mais pecas **do adversario** do tabuleiro?

    E a captura encadeada que o tipo `damas_capturar_multipla` pede — medida pelo
    **numero de pecas que sumiram**, e nao pelos `x` da notacao.
    """
    _, dele = _lado_e_adversario(antes)
    return len(_campos(antes)[dele]) - len(_campos(depois)[dele]) >= 2


#: Que pergunta se faz para cada tipo. ⛔ Tipo sem verificador falha alto: um
#: molde que ninguem sabe conferir e um molde que ninguem esta conferindo.
CUMPRIU_O_OBJETIVO: Mapping[str, Callable[[str, str], bool]] = {
    "damas_coroar": _coroou,
    "damas_capturar_multipla": _capturou_duas,
}


def objetivo_no_primeiro_lance(
    fen: str, co_tipo: str, co_modalidade: str
) -> Optional[str]:
    """O lance que entrega o objetivo de cara, ou `None` se nao houver.

    Args:
        fen: a posicao a examinar. ⚠️ **Serve para o molde E para a posicao
            publicada** — a pergunta e sempre sobre quem esta a jogar naquela
            FEN, e nao sobre uma cor fixa.
        co_tipo: `damas_coroar` ou `damas_capturar_multipla`.
        co_modalidade: o regulamento.

    Returns:
        A notacao do primeiro lance que cumpre o objetivo sozinho — `None` quando
        a posicao esta saudavel.

    Raises:
        KeyError: tipo sem verificador declarado.
    """
    cumpriu = CUMPRIU_O_OBJETIVO[co_tipo]
    estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
    motor = MotorDamas(co_modalidade)
    for lance in motor.lances_legais(estado):
        if cumpriu(estado.fen, estado.com_lance(lance).fen):
            return lance
    return None


def moldes_triviais(
    moldes: Sequence[str],
    co_tipo: str,
    modalidades: Sequence[str] = MODALIDADES,
) -> dict[str, list[str]]:
    """Quais moldes entregam o objetivo no primeiro lance, e onde.

    Returns:
        `{fen: ["brasileira:7-2", ...]}` — vazio quando todos estao saudaveis.

    ⚠️ **Basta UMA modalidade** para o molde nao servir: ele publicaria o desafio
    de um lance num dia de cada quatro, e os outros tres dias pareceriam normais.
    """
    achados: dict[str, list[str]] = {}
    for fen in moldes:
        ruins = [
            f"{co_modalidade}:{lance}"
            for co_modalidade in modalidades
            if (lance := objetivo_no_primeiro_lance(fen, co_tipo, co_modalidade))
        ]
        if ruins:
            achados[fen] = ruins
    return achados
