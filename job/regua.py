"""A REGUA DOS MASCOTES: quao dificil este candidato e (RF-DES-203/204, T035).

═══════════════════════════════════════════════════════════════════════════
A MEDIDA E UMA TAXA, E ELA E POR MASCOTE
═══════════════════════════════════════════════════════════════════════════

Para cada candidato, cada mascote joga N vezes (sugerido 20) e a regua anota
**quantas vezes resolveu**. Uma linha por mascote em `desafio.tb002_medicao_regua`.

⚠️ **E isso que a torna tabela em vez de um par de colunas**: descartar um desafio
por *"duro demais"* e por *"banal"* sao motivos diferentes, e e a taxa **por
nivel** que os separa. A evidencia de que a Pita resolve e a Cacau nao vale mais
que qualquer nota de dificuldade inventada.

═══════════════════════════════════════════════════════════════════════════
⚠️ QUEM MEDE SAO OS TRES QUE **NAO** SAO O ADVERSARIO DO DIA
═══════════════════════════════════════════════════════════════════════════

A escada roda **junto com o personagem** (RF-DES-204). O adversario do dia esta
do outro lado do tabuleiro; medir com ele seria perguntar *"a Pita resolve um
desafio contra a Pita?"*, que nao e a pergunta.

Os outros tres entram como **quem tenta resolver**, e e a taxa deles que diz se o
desafio esta na banda certa.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CARIMBO NAO E OPCIONAL
═══════════════════════════════════════════════════════════════════════════

Cada linha leva `co_versao_perfil` e `co_versao_motor` (RF-DES-146). Sem eles,
*"14 de 20"* e um numero **sem regua** — e a regua muda quando o perfil e afinado
ou quando a busca e corrigida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from motores.nucleo.orcamento import Orcamento
from motores.nucleo.papeis import NivelDeMotor

from . import semente as semente_mod
from .perfil import NIVEL_POR_PERSONAGEM

#: Quantas vezes cada mascote tenta, por padrao (RF-DES-016).
#:
#: ⚠️ Vinte e o numero sugerido pela spec, e ele e um equilibrio declarado: menos
#: execucoes dao uma taxa que oscila demais para separar 70% de 80%; mais
#: multiplicam o tempo do job por candidato.
EXECUCOES_PADRAO = 20

#: O orcamento de busca de cada lance na medicao.
#:
#: ⚠️ **Mais apertado que o da geracao, e de proposito**: a geracao roda uma vez
#: por candidato, a medicao roda `3 mascotes x 20 execucoes x varios lances`. Sem
#: um teto proprio, a regua sozinha domina o tempo do job.
NOS_POR_LANCE_NA_MEDICAO = 20_000
SEGUNDOS_POR_LANCE_NA_MEDICAO = 1.0


@dataclass(frozen=True, slots=True)
class Medicao:
    """A linha de `desafio.tb002_medicao_regua` de um mascote.

    Atributos:
        co_personagem: quem tentou.
        nu_execucoes: quantas vezes.
        nu_resolveu: quantas deram certo.
        co_versao_perfil, co_versao_motor: em que condicoes se mediu.
    """

    co_personagem: str
    nu_execucoes: int
    nu_resolveu: int
    co_versao_perfil: str
    co_versao_motor: str

    @property
    def taxa(self) -> float:
        """A fracao de execucoes resolvidas.

        Calculada, e nao guardada: uma coluna com a divisao poderia discordar dos
        dois numeros que a originaram, e ai nao haveria como saber qual vale.
        """
        return self.nu_resolveu / self.nu_execucoes


def medir_candidato(
    *,
    co_personagem_do_dia: str,
    tentar: Callable[[str, int], bool],
    co_versao_perfil: str,
    co_versao_motor: str,
    nu_execucoes: int = EXECUCOES_PADRAO,
) -> list[Medicao]:
    """Roda a escada e devolve uma linha por mascote.

    Args:
        co_personagem_do_dia: o adversario. ⚠️ Ele **nao** entra na medicao.
        tentar: `(co_personagem, numero_da_execucao) -> resolveu?`. E ela que
            carrega o motor; esta funcao so conta.
        co_versao_perfil, co_versao_motor: o carimbo das condicoes.
        nu_execucoes: quantas vezes cada mascote tenta.

    ⚠️ **A funcao `tentar` entra por parametro**, e nao e construida aqui, por
    duas razoes: o teste consegue medir a regua sem rodar motor nenhum, e o job
    consegue trocar a forma de tentar (um jogo novo, um motor nativo) sem tocar na
    contagem.
    """
    if nu_execucoes < 1:
        raise ValueError(f"nu_execucoes precisa ser >= 1; veio {nu_execucoes}")
    if co_personagem_do_dia not in NIVEL_POR_PERSONAGEM:
        raise ValueError(f"personagem desconhecido: {co_personagem_do_dia!r}")

    medicoes: list[Medicao] = []
    for co_personagem in NIVEL_POR_PERSONAGEM:
        if co_personagem == co_personagem_do_dia:
            continue

        resolveu = sum(
            1 for execucao in range(1, nu_execucoes + 1)
            if tentar(co_personagem, execucao)
        )
        medicoes.append(
            Medicao(
                co_personagem=co_personagem,
                nu_execucoes=nu_execucoes,
                nu_resolveu=resolveu,
                co_versao_perfil=co_versao_perfil,
                co_versao_motor=co_versao_motor,
            )
        )
    return medicoes


def tentativa_com_motor(
    *,
    jogador,
    estado_inicial,
    julgar,
    nu_semente: int,
    maximo_de_lances: int,
) -> Callable[[str, int], bool]:
    """Monta a funcao `tentar` que a regua consome, usando um motor de verdade.

    ⚠️ **Cada execucao recebe uma semente propria** (`semente_do_lance` sobre o
    par candidato/execucao): sem isso, as 20 execucoes de um mascote seriam
    identicas, e "14 de 20" so poderia dar 0 ou 20.
    """

    def tentar(co_personagem: str, execucao: int) -> bool:
        nivel = NIVEL_POR_PERSONAGEM[co_personagem]
        atual = estado_inicial
        fita: list[dict[str, Any]] = []

        for numero in range(1, maximo_de_lances + 1):
            orcamento = Orcamento(
                nos_maximos=NOS_POR_LANCE_NA_MEDICAO,
                segundos_maximos=SEGUNDOS_POR_LANCE_NA_MEDICAO,
            ).iniciar()
            # A semente muda por execucao E por lance: duas execucoes do mesmo
            # mascote precisam divergir, e dois lances da mesma execucao tambem.
            semente = semente_mod.semente_do_lance(
                nu_semente, execucao * 1000 + numero
            )
            try:
                lance = jogador.escolher_lance(
                    atual, nivel, limite=orcamento, semente=semente
                )
            except ValueError:
                # A partida acabou antes do objetivo: nao resolveu.
                return False

            fita.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
            atual = (
                jogador.aplicar(atual, lance)
                if hasattr(jogador, "aplicar")
                else atual.com_lance(lance)
            )

            if julgar(fita).cumpriu:
                return True

        return False

    return tentar


def dentro_da_banda(
    medicoes: Sequence[Medicao],
    *,
    piso: float,
    teto: float,
) -> bool:
    """A taxa MEDIA dos mascotes cai na banda alvo?

    ⚠️ **A media dos tres, e nao a de um so.** Um desafio que so a Cacau resolve e
    banal; um que so o Magno resolve e duro demais. A banda e sobre a escada
    inteira — e e por isso que as tres linhas sao gravadas, e nao so a media: a
    media decide a aprovacao, mas quem explica o descarte sao as linhas.
    """
    if not medicoes:
        return False
    media = sum(m.taxa for m in medicoes) / len(medicoes)
    return piso <= media <= teto
