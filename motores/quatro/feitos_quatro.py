"""Os FEITOS do Quatro em Linha: as medidas de uma tentativa de desafio (T112).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO MEDE, E DE QUEM
═══════════════════════════════════════════════════════════════════════════

Números lidos do tabuleiro e da fita, que outros transformam em objetivo
cumprido e em XP. ⚠️ Aqui não há XP nenhum: medida é medida, e quem converte é
a coleção (`job/editorial.py`, o extrato de XP do desafio).

A **pessoa** é quem tem a vez na posição publicada (`contracts/desafio-quatro.md`
§4.1): é ela quem resolve. Os lances iniciais são de ninguém, e nada se conta
neles. A fita traz os lances dos DOIS lados, e é preciso que traga (sem os do
adversário a partida não se reproduz); o laço abaixo separa de quem é cada um
pela vez do tabuleiro, e não por um campo do lance - o defeito das damas de
11/09/2026 foi contar os lances do adversário como se fossem da pessoa.

As medidas, uma frase cada (as chaves são as do catálogo de feitos, 50 a 56,
mais as universais `vitoria`, `empate` e `lances_do_jogador`):

- `pecas_encostadas` / `pecas_encostadas_do_adversario`: quantas peças da cor
  têm pelo menos uma vizinha da MESMA cor nas oito direções; cada peça conta
  uma vez. Medidas na posição de agora, terminada ou não;
- `vitoria_diagonal`, `linhas_no_lance_final`, `maior_linha`: como a PESSOA
  venceu. ⚠️ **Zero quando ela não venceu**, inclusive quando o adversário
  venceu com uma diagonal ou uma linha de cinco: o extrato é dela, e uma linha
  do adversário não é feito seu (decisão da T112, 20/10/2026). Nas chegadas
  todas elas vêm junto com `vitoria`, então o objetivo não muda;
- `lances_na_coluna_central`: lances da pessoa na coluna do meio, que só existe
  em largura ímpar;
- `ameacas_bloqueadas`: lances da pessoa que OCUPARAM uma casa onde uma peça do
  adversário formaria linha. Conta lances, e não ameaças.

E o predicado `quatro_perdeu` ([responder_predicados]): `True` quando a partida
terminou com vitória do adversário, `False` quando terminou sem ela, e **sem
resposta (`None`) enquanto ela não terminou**. Ver o porquê lá.

⚠️ **A fonte é o motor Dart** (`medidas_quatro.dart`, `medirFitaQuatro`): esta
é a escrita do servidor, e os vetores de paridade da T106
(`contratos/vetores-paridade-quatro.json`) conferem que as duas contam igual.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from motores.quatro import contrato_quatro
from motores.quatro.motor_quatro import (
    Casa,
    EstadoQuatro,
    MotorQuatro,
    TabuleiroQuatro,
)

#: As oito direções, como `(passo na coluna, passo na linha)`.
VIZINHAS: tuple[tuple[int, int], ...] = tuple(
    (dc, dl) for dc in (-1, 0, 1) for dl in (-1, 0, 1) if (dc, dl) != (0, 0)
)

#: As quatro direções de uma linha (cada uma cobre os dois sentidos).
DIRECOES_DE_LINHA: tuple[tuple[int, int], ...] = ((0, 1), (1, 0), (1, 1), (1, -1))


def _dentro(dimensoes: contrato_quatro.DimensoesQuatro, casa: Casa) -> bool:
    """A casa existe no tabuleiro (as casas são 1-based)."""
    coluna, linha = casa
    return 1 <= coluna <= dimensoes.largura and 1 <= linha <= dimensoes.altura


def pecas_encostadas(
    dimensoes: contrato_quatro.DimensoesQuatro, tabuleiro: TabuleiroQuatro, cor: int
) -> int:
    """Quantas peças da [cor] têm uma vizinha da mesma cor (`pecasEncostadas`)."""
    total = 0
    for coluna in range(1, dimensoes.largura + 1):
        for linha in range(1, len(tabuleiro.colunas[coluna - 1]) + 1):
            if tabuleiro.peca((coluna, linha)) != cor:
                continue
            # `any` para no primeiro vizinho da cor: a peça conta UMA vez.
            if any(
                _dentro(dimensoes, (coluna + dc, linha + dl))
                and tabuleiro.peca((coluna + dc, linha + dl)) == cor
                for dc, dl in VIZINHAS
            ):
                total += 1
    return total


def casas_de_ameaca(
    dimensoes: contrato_quatro.DimensoesQuatro, tabuleiro: TabuleiroQuatro, jogador: int
) -> frozenset[Casa]:
    """As casas VAZIAS onde uma peça do [jogador] formaria uma linha.

    Todas as casas vazias, e não só as jogáveis agora (`casasDeAmeacaQuatro` no
    Dart): quem pergunta "esta jogada bloqueou?" olha a casa que o lance ocupou,
    e essa era jogável por definição.

    A conta: pôr a peça na casa e contar, em cada direção, as peças do jogador
    encostadas dos dois lados; com `alinhar - 1` ou mais, a casa fecha linha.
    """
    casas: set[Casa] = set()
    for coluna in range(1, dimensoes.largura + 1):
        # As casas vazias de uma coluna são as de cima da pilha.
        for linha in range(len(tabuleiro.colunas[coluna - 1]) + 1, dimensoes.altura + 1):
            for dc, dl in DIRECOES_DE_LINHA:
                seguidas = 0
                for sentido in (1, -1):
                    c, l = coluna + dc * sentido, linha + dl * sentido
                    while _dentro(dimensoes, (c, l)) and tabuleiro.peca((c, l)) == jogador:
                        seguidas += 1
                        c, l = c + dc * sentido, l + dl * sentido
                if seguidas + 1 >= dimensoes.alinhar:
                    casas.add((coluna, linha))
                    break
    return frozenset(casas)


def _casa_ocupada(antes: TabuleiroQuatro, depois: TabuleiroQuatro) -> Casa | None:
    """A casa que o lance ocupou: a coluna cuja pilha cresceu, no topo dela.

    `None` num lance que não ocupa casa nova (o `tirar` de modalidades futuras):
    esse lance não bloqueia por ocupação.
    """
    for indice, (a, d) in enumerate(zip(antes.colunas, depois.colunas)):
        if len(d) > len(a):
            return (indice + 1, len(d))
    return None


def _direcao(linha: Sequence[Casa]) -> str:
    """`vertical`, `horizontal` ou `diagonal`, lida das duas primeiras casas."""
    (c1, l1), (c2, l2) = linha[0], linha[1]
    if c1 == c2:
        return "vertical"
    if l1 == l2:
        return "horizontal"
    return "diagonal"


def _reproduzir(
    motor: MotorQuatro, lances_iniciais: Iterable[str], fita: Iterable[str]
) -> tuple[int, list[tuple[TabuleiroQuatro, str, TabuleiroQuatro]], EstadoQuatro]:
    """A pessoa, os lances da fita com o tabuleiro antes e depois, e o fim.

    Raises:
        ValueError: um lance ilegal ou depois do fim (o árbitro recusa). ⚠️ É
            dado inválido, e quem chama distingue de "não cumpriu".
    """
    estado = EstadoQuatro(co_modalidade=motor.co_modalidade, lances=tuple(lances_iniciais))
    pessoa = motor.tabuleiro(estado).vez
    passos: list[tuple[TabuleiroQuatro, str, TabuleiroQuatro]] = []
    for lance in fita:
        antes = motor.tabuleiro(estado)
        if motor.regras.desfecho(antes) is not None:
            raise ValueError(f"lance {lance} depois do fim da partida")
        estado = motor.aplicar(estado, lance)
        passos.append((antes, lance, motor.tabuleiro(estado)))
    return pessoa, passos, estado


def medir(
    motor: MotorQuatro,
    lances_iniciais: Sequence[str],
    fita: Sequence[str],
    *,
    jogador: int | None = None,
) -> dict[str, float]:
    """Reproduz a fita depois da posição publicada e mede os feitos da pessoa.

    Args:
        motor: o árbitro da modalidade, que valida cada lance.
        lances_iniciais: a posição publicada, um lance por item (`("s4", "s4")`).
        fita: os lances jogados depois dela, dos dois lados, na ordem.
        jogador: de quem é o desafio, como o juiz o recebe. ⚠️ Conferido contra
            a vez na posição publicada: um desafio julgado do lado errado mediria
            os feitos do adversário, sem erro nenhum.

    Raises:
        ValueError: lance ilegal, depois do fim, ou [jogador] que não é quem
            tem a vez na posição publicada.
    """
    pessoa, passos, estado = _reproduzir(motor, lances_iniciais, fita)
    if jogador is not None and jogador != pessoa:
        raise ValueError(
            f"o desafio é do jogador {jogador:+d}, mas a vez na posição "
            f"publicada é do {pessoa:+d}"
        )
    dimensoes = motor.regras.dimensoes
    # A coluna do meio só existe em largura ímpar (`colunaCentralQuatro`).
    meio = (dimensoes.largura + 1) // 2 if dimensoes.largura % 2 == 1 else None

    lances_do_jogador = 0
    na_coluna_central = 0
    bloqueadas = 0
    for antes, lance, depois in passos:
        # De quem é o lance: de quem tinha a vez ANTES dele.
        if antes.vez != pessoa:
            continue
        lances_do_jogador += 1
        casa = _casa_ocupada(antes, depois)
        if casa is not None and casa[0] == meio:
            na_coluna_central += 1
        if casa is not None and casa in casas_de_ameaca(dimensoes, antes, -pessoa):
            bloqueadas += 1

    final = motor.tabuleiro(estado)
    desfecho = motor.regras.desfecho(final)
    venceu = desfecho is not None and desfecho.vencedor == pessoa
    empatou = desfecho is not None and desfecho.vencedor is None
    # As linhas só contam quando são DA PESSOA (ver o cabeçalho).
    linhas = desfecho.linhas if venceu else ()

    return {
        # Marcos: 1 ou 0, e não True/False - a coluna do extrato é numérica.
        "vitoria": 1 if venceu else 0,
        "empate": 1 if empatou else 0,
        "lances_do_jogador": lances_do_jogador,
        "pecas_encostadas": pecas_encostadas(dimensoes, final, pessoa),
        "pecas_encostadas_do_adversario": pecas_encostadas(dimensoes, final, -pessoa),
        "vitoria_diagonal": 1 if any(_direcao(l) == "diagonal" for l in linhas) else 0,
        "linhas_no_lance_final": len(linhas),
        "maior_linha": max((len(l) for l in linhas), default=0),
        "lances_na_coluna_central": na_coluna_central,
        "ameacas_bloqueadas": bloqueadas,
    }


def responder_predicados(
    motor: MotorQuatro, lances_iniciais: Sequence[str], fita: Sequence[str]
) -> dict[str, Any]:
    """As respostas dos predicados do Quatro depois de [fita].

    `quatro_perdeu`: `True` se a partida terminou com vitória do adversário da
    pessoa, `False` se terminou sem ela (vitória da pessoa ou empate), e
    **`None` enquanto não terminou**.

    ⚠️ **Por que `None`, e não `False`, no meio da partida.** O juiz avalia a
    chegada a cada lance da pessoa e para no primeiro em que ela vale. Os tipos
    que usam este predicado pedem "não perca" (`quatro_perdeu` igual `false`):
    com `False` no meio da partida, o "Segure o Magno" seria cumprido no 1º
    lance, e quem abandonasse no 2º lance teria segurado o Magno. Com `None`,
    `igual false` só vale no fim - e `comparar(None, "igual", False)` é falso.
    A mesma armadilha do `damas_sobreviver` (§8k-10), fechada aqui na forma do
    predicado em vez de num piso de lances.
    """
    pessoa, _, estado = _reproduzir(motor, lances_iniciais, fita)
    desfecho = motor.regras.desfecho(motor.tabuleiro(estado))
    if desfecho is None:
        return {"quatro_perdeu": None}
    return {"quatro_perdeu": desfecho.vencedor == -pessoa}
