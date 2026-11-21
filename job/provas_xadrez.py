"""AS PROVAS dos desafios do xadrez, e as pecas que o gerador e a regua usam (T076).

═══════════════════════════════════════════════════════════════════════════
O QUE "PROVAR" QUER DIZER NO XADREZ (RF-XDR-183, research R-33)
═══════════════════════════════════════════════════════════════════════════

O servidor **joga** cada desafio contra o personagem do nivel, com a semente
publicada, ate a chegada: o gabarito e a prova de que o desafio e possivel. Quem
joga e o laco comum do gerador (`gerador._resolver`), com as pecas deste modulo:

  * [EstadoXadrez] - a posicao publicada mais os lances desde ela (e o FEN de
    depois do ultimo, para o painel desenhar o gabarito lance a lance);
  * [JogadorDoDesafioXadrez] - quem escolhe o lance (o `buscar` do executavel,
    no nivel pedido e com a semente do lance) e quem o aplica (o `aplicar`);
  * a semente de cada lance e `semente.semente_do_lance(nu_semente, n)`, com o
    `n` contado em meios-lances A PARTIR DA POSICAO PUBLICADA, comecando em 1
    (`contracts/motor-xadrez.md` §3): e a mesma conta que o app faz, e por isso
    o adversario do aparelho responde o mesmo que o do gabarito.

Quem resolve, do lado da pessoa: nos dez tipos em que vencer nao e o objetivo,
o perseguidor (`motores/xadrez/perseguir_objetivo_xadrez.py`) - mas so depois da
medicao pareada (T076a), quando entra em `gerador.SOLUCIONADOR_POR_TIPO`; ate
la, o Magno cru. No `xadrez_dar_mate`, sempre o Magno cru, o motor que joga para
vencer (`DECISOES-do-dono.md` §8zzzz57).

═══════════════════════════════════════════════════════════════════════════
E O QUE AS [PROVAS] PERGUNTAM, ANTES DO GABARITO
═══════════════════════════════════════════════════════════════════════════

O gabarito custa uma partida inteira; as [PROVAS] sao as recusas BARATAS que
vem antes dele, uma por tipo (como em `job/provas_quatro.py`):

  * todas: a partida nao acabou, e o objetivo NAO cai no primeiro lance (um
    desafio que se resolve num toque nao e desafio: a regra do dono de
    16/09/2026, *"o usuario entra no App e em 10 segundos conclui o desafio"*);
  * os quatro da espia que pedem que ela ANDE (comer, atravessar, xeque, alvo):
    a espia tem lance agora. Presa atras das outras pecas, ela so andaria
    depois que o tabuleiro abrisse, e o prazo e curto;
  * o `xadrez_comer_com`: alguma peca da classe que come tem lance agora.

⚠️ **Caber na posicao nao e ser possivel**, e nenhuma destas prova o objetivo:
quem prova e o gabarito, e quem diz se ele e bom e a regua ("a Pita resolve, a
Cacau nao", T077).

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUMA REGRA DE XADREZ AQUI
═══════════════════════════════════════════════════════════════════════════

Tudo o que e regra vem do executavel (`motores/xadrez/jogador_xadrez.py`); o
medidor e o juiz dizem se o objetivo caiu. A vez alterna a cada lance (no
xadrez nao ha lance extra), e e so isso que [ArbitroXadrez] sabe.
"""

from __future__ import annotations

import functools
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import contrato_xadrez
from motores.xadrez import feitos_xadrez
from motores.xadrez import perseguir_objetivo_xadrez as perseguir
from motores.xadrez.jogador_xadrez import JogadorXadrez, jogador_compartilhado
from motores.nucleo.chegada import LinhaDeChegada

from . import posicoes_xadrez as posicoes_mod

RAIZ = Path(__file__).resolve().parents[1]

#: Os 10 000 problemas de mate em 2 a 5 do Lichess (T074/T075), para o
#: `xadrez_dar_mate`.
PROBLEMAS_DE_MATE = RAIZ / "dados" / "jogo_xadrez" / "problemas_de_mate.json"

#: A calibracao do acervo de mate: os problemas que cairam na escada contra cada
#: adversario (`scripts/calibrar_mate_xadrez.py`, 21/11/2026).
#:
#: ⚠️ **Por que o mate precisa dela, e os outros dez tipos nao.** Num problema
#: de mate em 2 cada mascote acerta quase sempre ou quase nunca: a busca do
#: nivel ve o mate ou nao ve, e em dois lances o erro sorteado quase nao pesa.
#: Medidos 600 problemas (10 execucoes, um adversario sorteado), a Pita deu 0,0
#: ou 1,0 na grande maioria, e so 27 (4,5%) cairam na escada; a 4a regua da
#: T077 viu o mesmo, 1 dia de 9. O rating do Lichess nao separa (de 3% a 6% em
#: toda faixa). O que separa e medir: o acervo e fixo, entao se mede uma vez e
#: o sorteio do dia escolhe entre os que ja cairam na escada contra o
#: adversario do dia. ⛔ A regua do dia continua medindo: a calibracao escolhe
#: o acervo, nao aprova o candidato.
CALIBRACAO_DO_MATE = RAIZ / "dados" / "jogo_xadrez" / "calibracao_do_mate.json"

#: O valor de `js_posicao_inicial.origem` das posicoes do mate (contrato §1).
ORIGEM_PROBLEMAS_LICHESS = "problemas_lichess"

#: O tipo que parte dos problemas, e nao da base equilibrada.
TIPO_DO_MATE = "xadrez_dar_mate"

#: A pessoa no vocabulario da fita: `+1`, como nos vetores do juiz. ⚠️ A
#: posicao do xadrez nao tem `vez_de` (o contrato §1 diz a COR, em
#: `cor_da_pessoa`), e e este numero que o gerador passa ao juiz.
VEZ_DA_PESSOA = perseguir.VEZ_DA_PESSOA


# ═══════════════════════════════════════════════════════════════════════════
# 1. O estado e o jogador, no formato que o gerador e a regua consomem
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EstadoXadrez:
    """Uma posicao do desafio: a publicada, mais os lances desde ela.

    Atributos:
        posicao: a `js_posicao_inicial` (o FEN publicado, a cor, as marcas).
        lances: os lances desde a posicao publicada, dos dois lados.
        fen: a posicao DEPOIS do ultimo lance (a publicada, sem lance). O
            gerador o grava em cada passo do gabarito (`passo["fen"]`), e e
            com ele que o painel de curadoria desenha a solucao.
    """

    posicao: Mapping[str, Any] = field(compare=False)
    lances: tuple[str, ...] = ()
    fen: str = ""

    @property
    def fen_inicial(self) -> str:
        return str(self.posicao["fen"])

    @property
    def modalidade(self) -> str:
        return str(self.posicao["modalidade"])


def estado_inicial(posicao: Mapping[str, Any]) -> EstadoXadrez:
    """O estado da posicao publicada, sem lance nenhum."""
    return EstadoXadrez(posicao=posicao, lances=(), fen=str(posicao["fen"]))


@dataclass(frozen=True, slots=True)
class DecisaoXadrez:
    """O lance escolhido e COMO ele foi escolhido (a forma da `DecisaoQuatro`).

    Atributos:
        lance: o lance (`e2e4`).
        co_acao: a `acao` do motor (`busca_melhor`, `erro_sorteado`,
            `cegueira`, `mate_em_um`, `lance_unico`). ⚠️ E ela que mostra na
            curadoria o erro de proposito do adversario: o xadrez ACEITA o
            desafio que depende de um erro sorteado (`DECISOES-do-dono.md`
            §8zzzz59), e o erro fica a vista no gabarito.
        resposta: a resposta inteira do motor.
    """

    lance: str
    co_acao: str
    resposta: dict[str, Any]


class ArbitroXadrez:
    """O que o laco do gerador pergunta ao "arbitro": de quem e a vez.

    No xadrez a vez alterna a cada lance, e a posicao publicada e sempre da
    vez da pessoa (`feitos_xadrez.reproduzir` confere isso pelo motor): o lance
    de indice par e dela (`+1`), o impar e do adversario (`-1`).
    """

    co_jogo = "xadrez"

    def vez_de(self, estado: EstadoXadrez) -> int:
        return VEZ_DA_PESSOA if len(estado.lances) % 2 == 0 else -VEZ_DA_PESSOA


class JogadorDoDesafioXadrez:
    """O personagem do xadrez no desafio, jogando pelo executavel.

    Args:
        motor: o processo do executavel. `None` usa o DA THREAD
            (`jogador_compartilhado`), que e o caminho do job e da regua.
    """

    co_jogo = "xadrez"

    def __init__(self, motor: JogadorXadrez | None = None) -> None:
        self._motor = motor
        self._arbitro = ArbitroXadrez()

    @property
    def arbitro(self) -> ArbitroXadrez:
        return self._arbitro

    @property
    def motor(self) -> JogadorXadrez:
        """O executavel: o injetado, ou o da thread que pergunta.

        ⛔ **O da thread nao e guardado no objeto**, pela mesma razao do
        `JogadorQuatro.motor_dart`: a regua entrega o MESMO jogador a varias
        threads, e um processo so receberia as respostas trocadas, sem erro.
        """
        return self._motor if self._motor is not None else jogador_compartilhado()

    def decidir(self, estado: EstadoXadrez, nivel: NivelDeMotor, semente: int) -> DecisaoXadrez:
        """O lance do [nivel], com a semente do lance, e o motivo."""
        resposta = self.motor.buscar(
            modalidade=estado.modalidade,
            fen_inicial=estado.fen_inicial,
            lances=list(estado.lances),
            nivel=nivel,
            semente=semente,
        )
        return DecisaoXadrez(lance=resposta["lance"], co_acao=resposta["acao"], resposta=resposta)

    def escolher_lance(
        self,
        estado: EstadoXadrez,
        nivel: NivelDeMotor,
        limite=None,
        semente: int | None = None,
    ) -> str:
        """O lance do [nivel], para quem nao quer o motivo (a regua).

        Raises:
            ValueError: sem semente (o `buscar` a exige: sem ela duas medicoes
                da mesma posicao divergiriam), ou a partida acabou
                (`partida_terminada`, que e `ValueError`).
        """
        if semente is None:
            raise ValueError("o xadrez joga so com a semente do lance")
        # O orcamento do job nao manda no motor (os nos sao do contrato do
        # nivel), mas conta-se o lance, como no Quatro.
        if limite is not None and hasattr(limite, "contar_no"):
            limite.contar_no(1)
        return self.decidir(estado, nivel, semente).lance

    def aplicar(self, estado: EstadoXadrez, lance: str) -> EstadoXadrez:
        """O estado depois de [lance], com o FEN que o motor devolveu.

        Raises:
            ValueError: o lance nao e legal ali (`lance_ilegal`), ou a partida
                ja acabou (`partida_terminada`).
        """
        resposta = self.motor.aplicar(
            modalidade=estado.modalidade,
            fen_inicial=estado.fen_inicial,
            lances=list(estado.lances),
            lance=lance,
        )
        return EstadoXadrez(
            posicao=estado.posicao,
            lances=estado.lances + (lance,),
            fen=resposta["fen_depois"],
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. A posicao do dia: a base equilibrada, ou um problema de mate
# ═══════════════════════════════════════════════════════════════════════════


@functools.lru_cache(maxsize=1)
def carregar_problemas_de_mate(caminho: Path = PROBLEMAS_DE_MATE) -> tuple[dict[str, Any], ...]:
    """Os problemas de mate, na ordem do arquivo (lido uma vez por processo).

    Raises:
        FileNotFoundError: o arquivo sumiu. ⚠️ Falhar alto: sem ele o mate
            ficaria sem desafio, calado.
    """
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return tuple(dados["problemas"])


def carregar_calibracao_do_mate(caminho: Path = CALIBRACAO_DO_MATE) -> dict[str, Any] | None:
    """A calibracao do acervo de mate ([CALIBRACAO_DO_MATE]), ou `None` sem ela.

    ⚠️ **Sem o arquivo nao e erro**: o sorteio volta ao acervo inteiro, como era
    ate 21/11/2026, e diz isso no log ([problemas_calibrados]). A regua do dia
    continua medindo; o que se perde e a chance de o candidato cair na escada.
    """
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def problemas_calibrados(
    cabem: list[dict[str, Any]],
    *,
    lances: int,
    co_personagem: str | None,
    calibracao: Mapping[str, Any] | None,
    versao_do_motor: str,
) -> list[dict[str, Any]]:
    """Os problemas de [cabem] que ja cairam na escada contra [co_personagem].

    Volta a [cabem] inteira, com um aviso no log, quando a calibracao nao serve:
    sem arquivo, de outro motor (a busca mudou, e o que caia na escada pode nao
    cair mais), de outro N, ou sem nenhum problema daquele adversario.
    ⛔ Nenhum desses casos para o job: o desafio do dia sai, so menos calibrado.

    Args:
        cabem: os problemas que cabem na janela de [lances].
        lances: o N do desafio; a calibracao foi medida com um N so.
        co_personagem: o adversario do dia; `None` (a medicao pareada, os testes
            antigos) usa o acervo inteiro, sem aviso.
        calibracao: o que [carregar_calibracao_do_mate] devolveu.
        versao_do_motor: a de hoje (`contrato_xadrez.versao_do_motor`).
    """
    if co_personagem is None:
        return cabem
    motivo = None
    if calibracao is None:
        motivo = f"sem {CALIBRACAO_DO_MATE.name}"
    elif calibracao.get("versao_do_motor") != versao_do_motor:
        motivo = (
            f"calibrada com o motor {calibracao.get('versao_do_motor')}, "
            f"e o de hoje e {versao_do_motor}"
        )
    elif int(calibracao.get("lances", -1)) != lances:
        motivo = f"calibrada com N={calibracao.get('lances')}, e o desafio pede N={lances}"
    else:
        ids = set((calibracao.get("na_escada_contra") or {}).get(co_personagem, ()))
        escolhidos = [p for p in cabem if p["id"] in ids]
        if escolhidos:
            return escolhidos
        motivo = f"nenhum problema calibrado contra {co_personagem}"
    # ⚠️ Alto, e a cada sorteio: e o aviso de que a calibracao precisa ser
    # refeita (`scripts/calibrar_mate_xadrez.py`), e um aviso unico se perderia.
    print(f"⚠️ [mate] acervo inteiro, sem calibracao: {motivo}", flush=True)
    return cabem


def sortear_problema_de_mate(
    sorteio: random.Random,
    *,
    lances: int,
    co_personagem: str | None = None,
    problemas: tuple[dict[str, Any], ...] | None = None,
    calibracao: Mapping[str, Any] | None = None,
) -> posicoes_mod.PosicaoDoDesafioXadrez:
    """Um problema de mate que caiba na janela de [lances] lances da pessoa.

    Args:
        sorteio: o `random.Random` ja semeado pelo dia (o mesmo dia da o mesmo
            problema).
        lances: o N do desafio ("em ate N lances"): so entram os problemas de
            mate em N ou menos.
        co_personagem: o adversario do dia. Com ele, o sorteio fica entre os
            problemas que ja cairam na escada contra ele ([problemas_calibrados]).
        problemas: so para os testes; sem eles, [carregar_problemas_de_mate].
        calibracao: so para os testes; sem ela, [carregar_calibracao_do_mate].

    Raises:
        posicoes_mod.SemPosicaoXadrez: nenhum problema cabe na janela.
    """
    if problemas is None:
        problemas = carregar_problemas_de_mate()
    cabem = [p for p in problemas if int(p["mate_em"]) <= lances]
    if not cabem:
        raise posicoes_mod.SemPosicaoXadrez(
            f"nenhum problema de mate cabe em {lances} lance(s)"
        )
    if co_personagem is not None and calibracao is None:
        calibracao = carregar_calibracao_do_mate()
    cabem = problemas_calibrados(
        cabem,
        lances=lances,
        co_personagem=co_personagem,
        calibracao=calibracao,
        versao_do_motor=contrato_xadrez.versao_do_motor(),
    )
    problema = cabem[sorteio.randrange(len(cabem))]
    # A ordem das chaves e a do contrato §1 (e a dos vetores do juiz).
    posicao = {
        "jogo": "xadrez",
        "modalidade": posicoes_mod.MODALIDADE,
        "fen": problema["fen"],
        "cor_da_pessoa": problema["cor_da_pessoa"],
        "origem": ORIGEM_PROBLEMAS_LICHESS,
    }
    return posicoes_mod.PosicaoDoDesafioXadrez(js_posicao_inicial=posicao, pecas={})


def sortear_posicao(
    sorteio: random.Random,
    *,
    co_tipo: str,
    parametros: Mapping[str, Any],
    co_personagem: str | None = None,
) -> posicoes_mod.PosicaoDoDesafioXadrez:
    """A posicao do dia de [co_tipo]: um problema no mate, a base nos outros dez.

    `co_personagem` (o adversario do dia) so pesa no mate: e ele que escolhe a
    lista calibrada ([sortear_problema_de_mate]).

    Raises:
        posicoes_mod.SemPosicaoXadrez: nada serviu.
    """
    if co_tipo == TIPO_DO_MATE:
        return sortear_problema_de_mate(
            sorteio, lances=int(parametros["lances"]), co_personagem=co_personagem
        )
    return posicoes_mod.sortear(sorteio, co_tipo=co_tipo, parametros=parametros)


# ═══════════════════════════════════════════════════════════════════════════
# 3. As provas baratas, antes do gabarito
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ProvaXadrez:
    """A resposta de uma prova: passou ou nao, e por que (uma frase para o log)."""

    passou: bool
    motivo: str


def _o_objetivo_cai_no_primeiro_lance(
    motor: JogadorXadrez, co_tipo: str, posicao: Mapping[str, Any], js_chegada: Mapping[str, Any]
) -> ProvaXadrez | None:
    """A recusa comum: a partida acabou, ou o objetivo cai no 1o lance.

    Pelo mesmo exame que o perseguidor faz (cada lance legal aplicado e medido),
    para a pergunta "cumpre agora?" ter uma resposta so. Devolve `None` quando a
    posicao passa.
    """
    desafio = perseguir.DesafioXadrez(
        co_tipo=co_tipo, posicao=posicao, chegada=LinhaDeChegada.de_dado(js_chegada)
    )
    try:
        _, examinados = perseguir.examinar_todos(motor, desafio, [])
    except ValueError as erro:
        return ProvaXadrez(False, f"a posicao nao tem lance para a pessoa ({erro})")
    for examinado in examinados:
        if examinado.cumpre:
            return ProvaXadrez(
                False, f"o objetivo cai no 1o lance ({examinado.lance}): resolve-se num toque"
            )
    return None


def _a_peca_anda(
    motor: JogadorXadrez, posicao: Mapping[str, Any], *, casas: set[str], oque: str
) -> ProvaXadrez | None:
    """Alguma das [casas] tem lance agora? `None` quando sim."""
    estado = motor.estado(modalidade=posicao["modalidade"], fen_inicial=posicao["fen"], lances=[])
    if any((estado.get("lances_legais") or {}).get(casa) for casa in casas):
        return None
    return ProvaXadrez(False, f"{oque} nao tem lance na posicao publicada")


def _espia_anda(motor: JogadorXadrez, posicao: Mapping[str, Any]) -> ProvaXadrez | None:
    casa = (posicao.get("marcas") or {}).get(feitos_xadrez.MARCA_DA_ESPIA)
    return _a_peca_anda(motor, posicao, casas={casa} if casa else set(), oque="a espia")


def _classe_que_come_anda(motor: JogadorXadrez, posicao: Mapping[str, Any]) -> ProvaXadrez | None:
    come = (posicao.get("classes") or {}).get("come")
    tabela = posicoes_mod.pecas_do_fen(posicao["fen"])
    casas = {
        casa
        for casa, peca in tabela.items()
        if peca.cor == posicao["cor_da_pessoa"] and peca.peca == come
    }
    return _a_peca_anda(motor, posicao, casas=casas, oque=f"nenhuma peca da classe {come!r}")


#: As perguntas de cada tipo, alem da comum. Uma funcao `(motor, posicao) ->
#: ProvaXadrez | None` por item (`None` = passou).
Pergunta = Callable[[JogadorXadrez, Mapping[str, Any]], "ProvaXadrez | None"]

#: A prova de cada tipo, pelo `co_tipo_desafio`.
#:
#: ⚠️ As chaves sao exatamente os onze tipos do xadrez (cadeado em
#: `test_provas_xadrez.py`): um tipo novo sem prova seria publicado sem que
#: ninguem tivesse perguntado se a posicao serve a ele. Os tipos de lista vazia
#: tem so a recusa comum, e estao aqui de proposito, e nao por esquecimento.
PROVAS: dict[str, tuple[Pergunta, ...]] = {
    "xadrez_espia_comer": (_espia_anda,),
    # Proteger e a unica da espia em que ela pode ficar parada.
    "xadrez_espia_proteger": (),
    "xadrez_espia_atravessar": (_espia_anda,),
    "xadrez_espia_xeque": (_espia_anda,),
    "xadrez_espia_alvo": (_espia_anda,),
    "xadrez_comer_com": (_classe_que_come_anda,),
    "xadrez_nao_perder": (),
    "xadrez_xeques_seguidos": (),
    "xadrez_sem_levar_xeque": (),
    "xadrez_troca": (),
    "xadrez_dar_mate": (),
}


def provar(
    co_tipo: str,
    posicao: Mapping[str, Any],
    js_chegada: Mapping[str, Any],
    *,
    motor: JogadorXadrez | None = None,
) -> ProvaXadrez:
    """A prova do tipo, para a posicao publicada e a chegada do candidato.

    Raises:
        KeyError: tipo sem prova. ⚠️ Falha alto: "sem prova" nao e "passou".
    """
    if co_tipo not in PROVAS:
        raise KeyError(
            f"o tipo {co_tipo!r} nao tem prova do xadrez (job/provas_xadrez.PROVAS)."
        )
    motor = motor or jogador_compartilhado()
    for pergunta in PROVAS[co_tipo]:
        recusa = pergunta(motor, posicao)
        if recusa is not None:
            return recusa
    recusa = _o_objetivo_cai_no_primeiro_lance(motor, co_tipo, posicao, js_chegada)
    if recusa is not None:
        return recusa
    return ProvaXadrez(True, "a partida esta viva e o objetivo nao cai no 1o lance")
