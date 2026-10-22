"""O BANCO de posições pescadas do Quatro em Linha (T124c da spec 010).

═══════════════════════════════════════════════════════════════════════════
O QUE MORA AQUI, E POR QUÊ
═══════════════════════════════════════════════════════════════════════════

Três tipos do Quatro não acham posição no acervo do gerador (medição de
21/10/2026, histórico do backend "2026-10-21 (10)"): o golpe duplo, a linha de
cinco e o "sem o meio". O dono decidiu (`DECISOES-do-dono.md` §8zzzn) que as
posições deles vêm de uma PESCARIA offline, com acervo próprio e maior, e com
muitos lances da pessoa. A pescaria
(`scripts/pescar_posicoes_forcaveis_quatro.py`) prova cada posição - o objetivo
é forçável contra quem defende o jogo, a 5 a 12 lances da pessoa - e grava o
banco `dados/jogo_quatro/banco_forcavel_<modalidade>.json`. Este módulo o lê e
sorteia dele; o gerador pede a posição aqui em vez do acervo, e NÃO refaz a
prova (ela custa até minutos por posição, e já foi feita).

⚠️ **O piso de publicação** (`piso_do_tipo`): só entram posições cuja vitória do
objetivo, contra quem defende o jogo, leva pelo menos 7 lances da pessoa
(`PISO_DE_LANCES_DA_PESSOA`). É a régua do *"Vença em 7"*, e a escolha pelos
critérios do dono (§8k-0: "não muito curtos"; "entre duas variantes, entra a mais
longa") e pela frase dele em 21/10: *"resolver o desafio em tão poucos lances do
jogador humano é muito ruim"*. Na pescaria de 21/10 sobram 44 golpes duplos e 94
linhas de cinco.

⚠️ **O "sem o meio" tem piso próprio, 9** (`PISO_POR_TIPO`; decisão do dono em
22/10/2026, `DECISOES-do-dono.md` §8zzzq). Com 7 a régua de 18 dias deu 11 dias
na escada, um abaixo do critério, e seis dos sete erros foram de "fácil demais"
(histórico do backend "2026-10-22 (1)"): o dono escolheu posições mais longas, e
não tirar mais um adversário. Com 9 sobram 33 das 60 posições. O golpe duplo e a
linha de cinco já estavam no ar com 7, medidos assim, e não mudam.

⚠️ **Não repetir** não é trabalho daqui: o job confere a assinatura de cada
candidato contra o histórico inteiro antes de publicar (T049i), e um sorteio que
caia numa posição já usada é recusado lá, como no acervo.
"""

from __future__ import annotations

import functools
import json
import random
from dataclasses import dataclass
from pathlib import Path

from motores.quatro.motor_quatro import ler_sequencia

from . import posicoes_de_autoplay_quatro as acervo_mod

#: A versão do formato do arquivo (quem escreve é a pescaria; quem lê confere).
VERSAO_DO_BANCO = 1

#: Os tipos cujas posições vêm do banco, e não do acervo do gerador.
TIPOS_DO_BANCO: frozenset[str] = frozenset(
    {"quatro_golpe_duplo", "quatro_linha_de_cinco", "quatro_sem_o_meio"}
)

#: O piso de publicação padrão, em lances da PESSOA (ver o cabeçalho).
PISO_DE_LANCES_DA_PESSOA = 7

#: Os tipos que pedem um piso diferente do padrão (ver o cabeçalho). Tipo que
#: não está aqui usa `PISO_DE_LANCES_DA_PESSOA`.
PISO_POR_TIPO: dict[str, int] = {"quatro_sem_o_meio": 9}


def piso_do_tipo(co_tipo: str) -> int:
    """Quantos lances da pessoa, no mínimo, uma posição do [co_tipo] precisa ter.

    É o único lugar que decide o piso: o gerador e a bancada da régua sorteiam
    pelo `sortear`, que pergunta aqui.
    """
    # `dict.get(chave, padrão)` devolve o padrão quando a chave não existe.
    return PISO_POR_TIPO.get(co_tipo, PISO_DE_LANCES_DA_PESSOA)

#: Posições com menos lances jogados que isto são aberturas, e a pescaria não as
#: prova. ⚠️ É também o "preparo" desses tipos no editorial: o teto do gabarito
#: tem de cobrir o tabuleiro inteiro a partir da posição mais curta do banco.
MINIMO_DE_LANCES_JOGADOS = 8


@dataclass(frozen=True, slots=True)
class PosicaoDoBanco:
    """Uma posição pescada.

    Atributos:
        lances: a posição, desde o tabuleiro vazio (`("s4", "s4", ...)`).
        lances_da_pessoa: em quantos lances da pessoa o objetivo é forçável
            contra quem defende o jogo (a prova da pescaria).
        confronto: de que confronto de autoplay ela saiu (procedência).
    """

    lances: tuple[str, ...]
    lances_da_pessoa: int
    confronto: str


def caminho_do_banco(co_modalidade: str) -> Path:
    """O arquivo do banco, ao lado do acervo do gerador (vai ao Git)."""
    return acervo_mod.PASTA_DO_ACERVO / f"banco_forcavel_{co_modalidade}.json"


@functools.lru_cache(maxsize=None)
def carregar(co_modalidade: str) -> dict[str, tuple[PosicaoDoBanco, ...]]:
    """As posições de cada tipo, lidas do disco uma vez por processo.

    Raises:
        FileNotFoundError: sem o arquivo, com a receita de como refazê-lo.
        ValueError: o arquivo é de outro formato ou de outra modalidade.
    """
    caminho = caminho_do_banco(co_modalidade)
    if not caminho.is_file():
        raise FileNotFoundError(
            f"o banco de posições do Quatro não está no disco ({caminho}).\n"
            "Refaça com, na raiz do backend:\n"
            "  .venv\\Scripts\\python -u scripts\\pescar_posicoes_forcaveis_quatro.py"
        )
    dado = json.loads(caminho.read_text(encoding="utf-8"))
    if dado.get("versao") != VERSAO_DO_BANCO:
        raise ValueError(
            f"{caminho.name}: formato {dado.get('versao')!r}, e este módulo lê o "
            f"{VERSAO_DO_BANCO}."
        )
    if dado.get("co_modalidade") != co_modalidade:
        # ⛔ Um arquivo renomeado à mão entregaria posições de outro tabuleiro.
        raise ValueError(
            f"{caminho.name} traz posições de {dado.get('co_modalidade')!r}, e foi "
            f"pedido {co_modalidade!r}."
        )
    return {
        co_tipo: tuple(
            PosicaoDoBanco(
                lances=ler_sequencia(achada["lances"]),
                lances_da_pessoa=int(achada["lances_da_pessoa"]),
                confronto=achada["confronto"],
            )
            for achada in achadas
        )
        for co_tipo, achadas in dado["tipos"].items()
    }


class BancoSemPosicao(RuntimeError):
    """Nenhuma posição do tipo no banco passa do piso de publicação."""


def sortear(
    sorteio: random.Random,
    co_tipo: str,
    co_modalidade: str,
    *,
    piso: int | None = None,
    banco: dict[str, tuple[PosicaoDoBanco, ...]] | None = None,
) -> PosicaoDoBanco:
    """Uma posição do tipo, com pelo menos [piso] lances da pessoa.

    Args:
        sorteio: o `random.Random` **já semeado** pela tentativa do dia (a mesma
            tentativa sorteia a mesma posição: o job é reproduzível).
        piso: só para os testes; sem ele (`None`), o piso do tipo
            (`piso_do_tipo`), que é o que o gerador usa.
        banco: só para os testes; sem ele, `carregar(co_modalidade)`.

    Raises:
        BancoSemPosicao: nenhuma posição passa do piso. ⚠️ Falha alto: um tipo
            sem posição não pode cair, calado, no acervo do gerador.
    """
    if piso is None:
        piso = piso_do_tipo(co_tipo)
    posicoes = (banco if banco is not None else carregar(co_modalidade)).get(co_tipo, ())
    servem = [p for p in posicoes if p.lances_da_pessoa >= piso]
    if not servem:
        raise BancoSemPosicao(
            f"o banco do Quatro ({co_modalidade}) não tem posição de {co_tipo} com "
            f"{piso} lances da pessoa ou mais ({len(posicoes)} no total)."
        )
    return sorteio.choice(servem)
