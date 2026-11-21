"""AS POSICOES DOS DESAFIOS DO XADREZ, e a escolha das pecas de cada um (T073).

═══════════════════════════════════════════════════════════════════════════
DE ONDE VEM A POSICAO
═══════════════════════════════════════════════════════════════════════════

Dez dos onze tipos partem da **base de posicoes equilibradas** do inicio
adiantado (RF-XDR-133, RF-XDR-186, research R-22): 3 000 posicoes de partidas
reais do Lichess (CC0), calmas e equilibradas pelo Stockfish, uma por linha. O
servidor le o espelho dela (`espelho_laboratorio/jogos/jogo_xadrez/posicoes/`),
copia byte-identica da fonte do laboratorio, que o `test_espelho_laboratorio.py`
confere. ⛔ **Sem autoplay** (pergunta C, 13/11/2026).

O 11o, o `xadrez_dar_mate`, nao sai daqui: uma posicao equilibrada quase nunca
tem mate em ate 5. As dele vem do banco de PROBLEMAS do Lichess (T074).

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE MODULO ESCOLHE, E COM QUE REGRA
═══════════════════════════════════════════════════════════════════════════

A pessoa joga com a cor que tem a vez no FEN (`cor_da_pessoa`). Sobre a
posicao sorteada, conforme o tipo:

  · a ESPIA (os cinco tipos dela): uma peca da pessoa, nunca o rei
    (RF-XDR-192). No `xadrez_espia_atravessar`, so torre, dama ou cavalo
    (contrato §2), e fora da ultima fileira (ja estar la nao e atravessar);
  · o ALVO (`xadrez_espia_alvo`): uma peca do adversario, nunca o rei - rei
    nao se come;
  · as CLASSES do `xadrez_comer_com`: `come` e uma classe que a pessoa tem;
    `comida` e uma classe do adversario com pelo menos K pecas (ninguem come
    dois peoes onde ha um so). Sem classe assim, `comida` fica de fora, e
    qualquer peca comida conta (ela e opcional, contrato §2);
  · a PECA do `xadrez_nao_perder`: uma classe que a pessoa tem (perder o que
    nao se tem nao e desafio);
  · o PAR da troca: bispo por cavalo, cavalo por bispo, torre por torre ou
    dama por dama (RF-XDR-202), e so o par que existe na posicao - a pessoa
    com a `minha`, o adversario com a `dele`.

⚠️ **Caber na posicao nao e ser possivel.** O que este modulo garante e que as
pecas existem e obedecem as regras acima. Se a espia consegue mesmo comer duas
pecas contra a Pita, quem diz e o gabarito (a prova, T076), e a posicao que
nao passar volta para ca como defeito de escolha (`DECISOES-do-dono.md`
§8zzzz57, item 5).

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ESTE MODULO NAO FAZ
═══════════════════════════════════════════════════════════════════════════

⛔ **Nenhuma regra de xadrez.** O FEN e LIDO como uma tabela ("que peca esta
em que casa"), exatamente como o app faz em `pecas_do_fen_xadrez.dart`: nada
aqui decide se um lance e legal, se ha xeque ou o que acontece depois. Isso e
do motor.
⛔ **Nao semeia o sorteio**: o `random.Random` chega pronto, semeado pelo dia,
como nos acervos do Pontinhos e do Quatro (a idempotencia da T038). Mesmo dia,
mesmo sorteio, mesma posicao e mesmas pecas.
"""

from __future__ import annotations

import functools
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from motores.xadrez import contrato_xadrez
# ⚠️ A leitura do FEN como tabela mora em `motores/xadrez/fen_xadrez.py` desde
# a T076: o perseguidor (em `motores/`) tambem a usa, e `motores/` nao importa
# de `job/`. Os nomes continuam valendo aqui (`px.pecas_do_fen`...), como
# reexporte.
from motores.xadrez.fen_xadrez import (  # noqa: F401 (reexporte)
    COLUNAS,
    COR_DA_VEZ,
    PECA_DA_LETRA,
    PecaNaCasa,
    cor_da_vez,
    pecas_do_fen,
)
from motores.xadrez.fen_xadrez import outra_cor as _outra_cor
from motores.xadrez.feitos_xadrez import (
    MARCA_DA_ESPIA,
    MARCA_DO_ALVO,
    TIPOS_COMIVEIS,
    ULTIMA_FILEIRA,
)

RAIZ = Path(__file__).resolve().parents[1]

#: O espelho da base equilibrada (a fonte e `ia/jogos/jogo_xadrez/posicoes/`).
BASE_EQUILIBRADA = (
    RAIZ / "espelho_laboratorio" / "jogos" / "jogo_xadrez" / "posicoes" / "posicoes_adiantadas.txt"
)

#: O valor de `js_posicao_inicial.origem` para as posicoes daqui (contrato §1).
ORIGEM_BASE_EQUILIBRADA = "base_equilibrada"

#: A modalidade do xadrez, LIDA do contrato (o nome nao se escreve aqui: e
#: dado, RF-XDR-013).
MODALIDADE = contrato_xadrez.modalidades_declaradas()[0]


#: As espias que podem "atravessar" (contrato §2): o peao que chega la vira
#: outra peca, e o bispo nao alcanca toda casa da ultima fileira.
ESPIAS_QUE_ATRAVESSAM: tuple[str, ...] = ("cavalo", "torre", "dama")

#: Os pares da troca (RF-XDR-202), como (`minha`, `dele`): pecas de forca
#: parecida. Com pecas desiguais a CPU nunca aceitaria o mau negocio.
PARES_DA_TROCA: tuple[tuple[str, str], ...] = (
    ("bispo", "cavalo"),
    ("cavalo", "bispo"),
    ("torre", "torre"),
    ("dama", "dama"),
)

#: Os tipos que usam a espia.
TIPOS_DA_ESPIA: tuple[str, ...] = (
    "xadrez_espia_comer",
    "xadrez_espia_proteger",
    "xadrez_espia_atravessar",
    "xadrez_espia_xeque",
    "xadrez_espia_alvo",
)

#: Os dez tipos que partem da base equilibrada (todos menos o mate).
TIPOS_DA_BASE: tuple[str, ...] = (
    *TIPOS_DA_ESPIA,
    "xadrez_comer_com",
    "xadrez_nao_perder",
    "xadrez_xeques_seguidos",
    "xadrez_sem_levar_xeque",
    "xadrez_troca",
)

#: Quantas posicoes sortear antes de desistir de um tipo. ⚠️ Folgado: a base
#: tem 3 000 posicoes com pelo menos 10 pecas alem dos reis, e quase toda
#: posicao serve a quase todo tipo; o que mais recusa e o par da troca.
TENTATIVAS_PADRAO = 200


class PosicaoNaoServe(ValueError):
    """Aquela posicao nao tem as pecas que o tipo pede (o par da troca, uma
    espia que atravesse...). Nao e erro: o sorteio tenta outra."""


class SemPosicaoXadrez(RuntimeError):
    """Nenhuma posicao sorteada serviu ao tipo. ⚠️ Falha alto: com a base de
    3 000 isso e defeito de regra (ou da base), e nao azar."""


@dataclass(frozen=True, slots=True)
class PosicaoDoDesafioXadrez:
    """O que a posicao do dia entrega ao gerador.

    Atributos:
        js_posicao_inicial: a posicao publicada, no formato do contrato §1.
        pecas: os codigos de peca que entram nos PARAMETROS da receita e na
            frase (`espia`, `alvo`, `come`, `comida`, `peca`, `minha`, `dele`;
            `DECISOES-do-dono.md` §8zzzz58). ⚠️ Aqui `espia` e `alvo` sao a
            CLASSE da peca; na posicao, as `marcas` guardam a CASA.
    """

    js_posicao_inicial: dict[str, Any]
    pecas: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# 1. A base (a leitura do FEN mora em `motores/xadrez/fen_xadrez.py`)
# ═══════════════════════════════════════════════════════════════════════════


@functools.lru_cache(maxsize=1)
def carregar_base(caminho: Path = BASE_EQUILIBRADA) -> tuple[str, ...]:
    """As posicoes da base, uma por linha, na ordem do arquivo.

    `lru_cache` = o arquivo e lido uma vez por processo (o job sorteia varias
    posicoes por execucao, e a base nao muda no meio dela).

    Raises:
        FileNotFoundError: o espelho sumiu. ⚠️ Falhar alto: uma base vazia
            deixaria o xadrez sem desafio, calado.
    """
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return tuple(linha.strip() for linha in linhas if linha.strip())


# ═══════════════════════════════════════════════════════════════════════════
# 2. A escolha das pecas
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Toda escolha sorteia de uma lista ORDENADA (pela casa, ou pela ordem fixa
# das classes): a ordem de um `dict` e a da leitura do FEN, que e estavel, mas
# ordenar explicitamente deixa a idempotencia a vista de quem le.


def _escolher(sorteio: random.Random, opcoes: list, oque: str) -> Any:
    """Um item de [opcoes], ou `PosicaoNaoServe` quando nao ha nenhum."""
    if not opcoes:
        raise PosicaoNaoServe(f"a posicao nao tem {oque}")
    return opcoes[sorteio.randrange(len(opcoes))]


def _classes_de(pecas: Mapping[str, PecaNaCasa], cor: str) -> dict[str, int]:
    """Quantas pecas de cada classe comivel (sem o rei) a [cor] tem."""
    contagem = {classe: 0 for classe in TIPOS_COMIVEIS}
    for peca in pecas.values():
        if peca.cor == cor and peca.peca in contagem:
            contagem[peca.peca] += 1
    return contagem


def escolher_espia(
    sorteio: random.Random,
    pecas: Mapping[str, PecaNaCasa],
    *,
    cor: str,
    co_tipo: str,
) -> PecaNaCasa:
    """A espia: uma peca da pessoa, nunca o rei (RF-XDR-192).

    No `xadrez_espia_atravessar`, so torre, dama ou cavalo, e fora da ultima
    fileira dela (la ja estaria do outro lado).
    """
    candidatas = [
        p for _, p in sorted(pecas.items()) if p.cor == cor and p.peca != "rei"
    ]
    if co_tipo == "xadrez_espia_atravessar":
        candidatas = [
            p
            for p in candidatas
            if p.peca in ESPIAS_QUE_ATRAVESSAM and p.casa[-1] != ULTIMA_FILEIRA[cor]
        ]
    return _escolher(sorteio, candidatas, "espia para este tipo")


def escolher_alvo(
    sorteio: random.Random, pecas: Mapping[str, PecaNaCasa], *, cor: str
) -> PecaNaCasa:
    """O alvo: uma peca do ADVERSARIO de [cor], nunca o rei."""
    adversario = _outra_cor(cor)
    candidatas = [
        p for _, p in sorted(pecas.items()) if p.cor == adversario and p.peca != "rei"
    ]
    return _escolher(sorteio, candidatas, "alvo")


def escolher_classes(
    sorteio: random.Random,
    pecas: Mapping[str, PecaNaCasa],
    *,
    cor: str,
    capturas: int,
) -> dict[str, str]:
    """As classes do `xadrez_comer_com`: `{"come": ..., "comida": ...}`.

    `come` e uma classe que a pessoa tem. `comida` e uma classe do adversario
    com pelo menos [capturas] pecas; sem nenhuma, ela fica de fora (o desafio
    vale para qualquer peca comida, contrato §2).
    """
    minhas = _classes_de(pecas, cor)
    dele = _classes_de(pecas, _outra_cor(cor))
    come = _escolher(
        sorteio, [c for c in TIPOS_COMIVEIS if minhas[c] > 0], "classe para comer"
    )
    possiveis = [c for c in TIPOS_COMIVEIS if dele[c] >= capturas]
    classes = {"come": come}
    if possiveis:
        classes["comida"] = possiveis[sorteio.randrange(len(possiveis))]
    return classes


def escolher_peca_a_proteger(
    sorteio: random.Random, pecas: Mapping[str, PecaNaCasa], *, cor: str
) -> str:
    """A classe do `xadrez_nao_perder`: uma que a pessoa tem."""
    minhas = _classes_de(pecas, cor)
    return _escolher(
        sorteio, [c for c in TIPOS_COMIVEIS if minhas[c] > 0], "peca a proteger"
    )


def escolher_par_da_troca(
    sorteio: random.Random, pecas: Mapping[str, PecaNaCasa], *, cor: str
) -> dict[str, str]:
    """O par da troca, `{"minha": ..., "dele": ...}`: um dos [PARES_DA_TROCA]
    que existe na posicao (a pessoa com a `minha`, o adversario com a `dele`)."""
    minhas = _classes_de(pecas, cor)
    dele = _classes_de(pecas, _outra_cor(cor))
    pares = [(m, d) for m, d in PARES_DA_TROCA if minhas[m] > 0 and dele[d] > 0]
    minha, do_adversario = _escolher(sorteio, pares, "par para a troca")
    return {"minha": minha, "dele": do_adversario}


# ═══════════════════════════════════════════════════════════════════════════
# 3. A posicao do desafio
# ═══════════════════════════════════════════════════════════════════════════


def posicao_do_desafio(
    sorteio: random.Random,
    *,
    co_tipo: str,
    fen: str,
    parametros: Mapping[str, Any],
) -> PosicaoDoDesafioXadrez:
    """A posicao publicada de [co_tipo] a partir de [fen], com as pecas
    escolhidas pelo [sorteio].

    Args:
        parametros: os numeros do editorial; so o `xadrez_comer_com` le um
            (`capturas`, para a classe comida ter pecas bastantes).

    Raises:
        PosicaoNaoServe: o [fen] nao tem as pecas que o tipo pede.
        ValueError: tipo que nao parte da base (o mate, ou um que nao e do
            xadrez), ou FEN torto.
    """
    if co_tipo not in TIPOS_DA_BASE:
        raise ValueError(
            f"{co_tipo!r} nao parte da base equilibrada (o mate vem do banco de "
            "problemas do Lichess, T074)"
        )
    pecas = pecas_do_fen(fen)
    cor = cor_da_vez(fen)
    marcas: dict[str, str] = {}
    classes: dict[str, str] | None = None
    troca: dict[str, str] | None = None
    escolhidas: dict[str, str] = {}

    if co_tipo in TIPOS_DA_ESPIA:
        espia = escolher_espia(sorteio, pecas, cor=cor, co_tipo=co_tipo)
        marcas[MARCA_DA_ESPIA] = espia.casa
        escolhidas["espia"] = espia.peca
    if co_tipo == "xadrez_espia_alvo":
        alvo = escolher_alvo(sorteio, pecas, cor=cor)
        marcas[MARCA_DO_ALVO] = alvo.casa
        escolhidas["alvo"] = alvo.peca
    if co_tipo == "xadrez_comer_com":
        classes = escolher_classes(sorteio, pecas, cor=cor, capturas=int(parametros["capturas"]))
        escolhidas.update(classes)
    if co_tipo == "xadrez_nao_perder":
        escolhidas["peca"] = escolher_peca_a_proteger(sorteio, pecas, cor=cor)
    if co_tipo == "xadrez_troca":
        troca = escolher_par_da_troca(sorteio, pecas, cor=cor)
        escolhidas.update(troca)

    # ⚠️ A ordem das chaves e a do contrato §1 (e a dos vetores do juiz):
    # `marcas`, `classes` e `troca` so existem nos tipos que os usam.
    posicao: dict[str, Any] = {
        "jogo": "xadrez",
        "modalidade": MODALIDADE,
        "fen": fen,
        "cor_da_pessoa": cor,
    }
    if marcas:
        posicao["marcas"] = marcas
    if classes is not None:
        posicao["classes"] = classes
    if troca is not None:
        posicao["troca"] = troca
    posicao["origem"] = ORIGEM_BASE_EQUILIBRADA
    return PosicaoDoDesafioXadrez(js_posicao_inicial=posicao, pecas=escolhidas)


def sortear(
    sorteio: random.Random,
    *,
    co_tipo: str,
    parametros: Mapping[str, Any],
    base: tuple[str, ...] | None = None,
    tentativas: int = TENTATIVAS_PADRAO,
) -> PosicaoDoDesafioXadrez:
    """Uma posicao da base que sirva a [co_tipo], com as pecas escolhidas.

    Args:
        sorteio: o `random.Random` **ja semeado pelo dia**.
        base: so para os testes; sem ela, [carregar_base].
        tentativas: quantas posicoes sortear antes de desistir.

    ⚠️ A posicao que nao serve (sem par para a troca, sem espia que
    atravesse) e descartada e outra e sorteada, com o MESMO sorteio: o
    resultado continua dependendo so do dia.

    Raises:
        SemPosicaoXadrez: nenhuma das [tentativas] serviu.
    """
    if base is None:
        base = carregar_base()
    if not base:
        raise SemPosicaoXadrez("a base equilibrada do xadrez esta vazia")
    motivos: list[str] = []
    for _ in range(tentativas):
        fen = base[sorteio.randrange(len(base))]
        try:
            return posicao_do_desafio(sorteio, co_tipo=co_tipo, fen=fen, parametros=parametros)
        except PosicaoNaoServe as recusa:
            motivos.append(str(recusa))
    raise SemPosicaoXadrez(
        f"nenhuma de {tentativas} posicoes serviu a {co_tipo!r}; o ultimo motivo: "
        f"{motivos[-1] if motivos else '-'}"
    )
