"""O FEN do xadrez lido (e escrito) como TABELA, sem regra nenhuma (T073, T076).

═══════════════════════════════════════════════════════════════════════════
O QUE E UM FEN, EM UMA FRASE
═══════════════════════════════════════════════════════════════════════════

O FEN e a fotografia de uma posicao num texto de seis campos separados por
espaco: `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1`. O 1o
campo diz que peca esta em que casa; o 2o, de quem e a vez (`w` brancas, `b`
pretas); o 3o, os roques que ainda valem; o 4o, a casa da captura de passagem
(o "en passant"), quando ha uma; o 5o e o 6o, os relogios de lances.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MODULO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

Nenhuma regra de xadrez: nada aqui decide se um lance e legal, se ha xeque ou o
que acontece depois. Isso e do motor em Rust (`contracts/motor-xadrez.md`). O
FEN e lido como uma tabela ("que peca esta em que casa"), exatamente como o app
faz em `pecas_do_fen_xadrez.dart`.

⚠️ **Morava em `job/posicoes_xadrez.py` ate a T076.** Subiu para ca porque o
perseguidor (`motores/xadrez/perseguir_objetivo_xadrez.py`) tambem a usa, e
`motores/` nao importa de `job/` (o job usa os motores, e nunca o contrario).
`job/posicoes_xadrez.py` reexporta os mesmos nomes.
"""

from __future__ import annotations

from dataclasses import dataclass

#: As letras do FEN -> o nome da peca, no vocabulario do motor (`peca_movida`
#: nos fatos do lance). E a tabela `_pecaDaLetra` do app.
PECA_DA_LETRA: dict[str, str] = {
    "p": "peao",
    "n": "cavalo",
    "b": "bispo",
    "r": "torre",
    "q": "dama",
    "k": "rei",
}

#: A vez no 2o campo do FEN -> a cor de regra.
COR_DA_VEZ: dict[str, str] = {"w": "branca", "b": "preta"}

#: As colunas, da esquerda para a direita vistas pelas brancas.
COLUNAS = "abcdefgh"


@dataclass(frozen=True, slots=True)
class PecaNaCasa:
    """Uma peca numa casa: `casa` (`a1` a `h8`), `cor` (`branca`/`preta`) e
    `peca` (`peao` ... `rei`)."""

    casa: str
    cor: str
    peca: str


def pecas_do_fen(fen: str) -> dict[str, PecaNaCasa]:
    """As pecas do [fen], pela casa. Casa vazia nao aparece.

    Le so o 1o campo do FEN (as oito fileiras, da 8a a 1a, cada uma da coluna
    a a h; letra = peca, maiuscula = branca, numero = casas vazias). E a
    `pecasDoFenXadrez` do app, linha a linha.

    Raises:
        ValueError: FEN sem oito fileiras, letra desconhecida ou fileira que
            nao soma oito casas. ⚠️ Pular a letra em silencio sumiria com uma
            peca do tabuleiro.
    """
    fileiras = fen.strip().split(" ")[0].split("/")
    if len(fileiras) != 8:
        raise ValueError(f"o FEN nao tem 8 fileiras: {fen!r}")
    pecas: dict[str, PecaNaCasa] = {}
    for indice, texto in enumerate(fileiras):
        # A 1a fileira do texto e a 8a do tabuleiro.
        fileira = 8 - indice
        coluna = 0
        for letra in texto:
            if letra.isdigit():
                coluna += int(letra)
                continue
            peca = PECA_DA_LETRA.get(letra.lower())
            if peca is None or coluna > 7:
                raise ValueError(f"letra {letra!r} fora do FEN na fileira {fileira}: {fen!r}")
            casa = f"{COLUNAS[coluna]}{fileira}"
            cor = "branca" if letra.isupper() else "preta"
            pecas[casa] = PecaNaCasa(casa=casa, cor=cor, peca=peca)
            coluna += 1
        if coluna != 8:
            raise ValueError(f"a fileira {fileira} nao tem 8 casas: {fen!r}")
    return pecas


def cor_da_vez(fen: str) -> str:
    """De quem e a vez no [fen] (o 2o campo): `branca` ou `preta`.

    Raises:
        ValueError: o campo nao e `w` nem `b`.
    """
    campos = fen.strip().split(" ")
    if len(campos) < 2 or campos[1] not in COR_DA_VEZ:
        raise ValueError(f"o FEN nao diz de quem e a vez: {fen!r}")
    return COR_DA_VEZ[campos[1]]


def outra_cor(cor: str) -> str:
    """A cor do adversario de [cor]."""
    return "preta" if cor == "branca" else "branca"


def fen_com_a_vez_trocada(fen: str) -> str:
    """O mesmo tabuleiro, com a vez do OUTRO lado (T076).

    E a pergunta "se eu pudesse jogar de novo agora, o que alcancaria?", que o
    perseguidor faz no `xadrez_espia_alvo` (a espia ja ataca o alvo?). O motor
    faz a mesma troca por dentro no Radar (`radar.rs`, o "lance nulo" da
    `cozy-chess`).

    So dois campos mudam: o 2o (a vez) e o 4o (a casa da captura de passagem),
    que fica vazio (`-`), porque ela so vale no lance logo seguinte ao avanco de
    duas casas, e esse lance agora seria do outro lado. ⚠️ **Quem diz se a
    posicao nova vale e o motor**: com o lado que nao joga em xeque ela nao
    existe, e o `estado` responde `fen_invalido` (conferido em 21/11/2026).

    Raises:
        ValueError: o FEN nao tem os seis campos.
    """
    campos = fen.strip().split(" ")
    if len(campos) != 6 or campos[1] not in COR_DA_VEZ:
        raise ValueError(f"o FEN nao tem os seis campos: {fen!r}")
    campos[1] = "b" if campos[1] == "w" else "w"
    campos[3] = "-"
    return " ".join(campos)
