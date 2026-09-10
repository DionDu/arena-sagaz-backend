"""A PROVA DE QUE A PARTIDA TEM FIM (RF-DES-187/188, T036).

═══════════════════════════════════════════════════════════════════════════
O QUE SE PROVA, E O QUE **NAO** SE EXIGE
═══════════════════════════════════════════════════════════════════════════

Prova-se que a partida daquele desafio **e levavel a estado terminal** — que o
jogo, a partir daquela posicao, chega ao fim se alguem jogar ate la.

⛔ **Nao se exige que a pessoa jogue ate o fim.** Determinacao do dono, 04/09/2026:
quando a linha de chegada cai antes do fim, o **desafio** fecha no objetivo, e o
aplicativo ⛔ **nao interrompe a partida** de quem quiser continuar. Quem para no
objetivo deixa a partida sem fim, e ha tres caminhos de saida — fim natural, sair
da tela, e o job de expiracao de 7 dias.

⚠️ **Isto e sobre o JOGO ter fim, e nao sobre a pessoa jogar ate la.** A distincao
parece sutil e nao e: sem ela, alguem escreveria um guarda que fecha a tela no
instante do objetivo, e o requisito diz exatamente o contrario.

═══════════════════════════════════════════════════════════════════════════
POR QUE PROVAR ISSO NA GERACAO
═══════════════════════════════════════════════════════════════════════════

Um desafio que deixe o jogo num estado **sem fim** — uma posicao de damas em que
nenhum dos dois pode mover e o motor nao declara desfecho, por exemplo — nao e um
desafio dificil. E **dado invalido**: o replay nao termina, a auditoria nao
consegue reconferir, e a partida fica `em_andamento` para sempre.

⚠️ **A conferencia na gravacao e a SEGUNDA rede, nao a primeira.** Descobrir isso
na hora de gravar significa ter gastado a medicao inteira num candidato que nao
serve.

═══════════════════════════════════════════════════════════════════════════
⚠️ A PROVA SAI DO TRABALHO QUE A REGUA JA FAZ
═══════════════════════════════════════════════════════════════════════════

A regua roda `3 mascotes x 20 execucoes` a partir daquela posicao. Se **qualquer**
uma dessas execucoes chegou a um estado terminal, esta provado — e nao custou um
lance a mais.

Rodar uma partida extra so para provar isso seria pagar duas vezes pela mesma
informacao.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from motores.nucleo.orcamento import Orcamento
from motores.nucleo.papeis import NivelDeMotor

from . import semente as semente_mod

#: O orcamento de cada lance na prova de termino.
#:
#: ⚠️ Apertado: aqui nao se quer jogar bem, se quer **acabar**. Um lance legal
#: qualquer serve para levar a partida adiante.
NOS_POR_LANCE = 8_000
SEGUNDOS_POR_LANCE = 0.5

#: O teto de lances de uma prova. Uma partida que passe disso sem terminar e
#: tratada como **nao provada**, e o candidato e descartado.
#:
#: ⚠️ **Descartar por nao provar nao e o mesmo que provar que nao tem fim.** O
#: motivo do descarte diz isso, e a distincao importa para quem for investigar
#: uma fila que ficou curta.
TETO_DE_LANCES = 200


@dataclass(frozen=True, slots=True)
class Prova:
    """O resultado da tentativa de levar a partida ao fim.

    Atributos:
        tem_fim: se algum caminho chegou a estado terminal.
        nu_lances: quantos lances foram precisos (ou tentados).
        co_motivo: o desfecho do motor, quando houve.
    """

    tem_fim: bool
    nu_lances: int
    co_motivo: str | None = None

    @property
    def de_descarte(self) -> str | None:
        """O motivo de descarte, pronto para `de_motivo_descarte`.

        ⚠️ `None` quando o candidato passou. Quando nao passou, o texto **diz que
        nao foi provado**, e nao que o jogo nao tem fim — sao coisas diferentes, e
        a linha precisa ser interpretavel meses depois por quem nao estava la.
        """
        if self.tem_fim:
            return None
        return (
            f"a partida nao chegou a estado terminal em {self.nu_lances} lances. "
            "⚠️ Isto NAO prova que ela nao tem fim: prova que o job nao conseguiu "
            "leva-la ate la dentro do teto. O candidato e descartado como dado "
            "nao verificavel (RF-DES-188)."
        )


def provar_termino(
    *,
    jogador,
    estado_inicial,
    veredito_de,
    nu_semente: int,
    teto_de_lances: int = TETO_DE_LANCES,
) -> Prova:
    """Joga ate o fim e diz se a partida chegou a estado terminal.

    Args:
        jogador: quem escolhe os lances. ⚠️ **Qualquer nivel serve** — aqui nao se
            quer jogar bem, se quer acabar.
        estado_inicial: a posicao do candidato.
        veredito_de: `(estado) -> Veredito`, do arbitro daquele jogo.
        nu_semente: para a prova ser reproduzivel.
        teto_de_lances: quantos lances tentar antes de desistir.

    ⚠️ **O arbitro e quem responde se acabou**, e nao uma regra escrita aqui. As
    regras de fim de partida — afogamento, repeticao tripla, lei dos 20 lances —
    moram no motor, que e copia byte-identica do laboratorio.
    """
    estado = estado_inicial

    for numero in range(1, teto_de_lances + 1):
        veredito = veredito_de(estado)
        if veredito.acabou:
            return Prova(tem_fim=True, nu_lances=numero - 1, co_motivo=veredito.co_motivo)

        orcamento = Orcamento(
            nos_maximos=NOS_POR_LANCE, segundos_maximos=SEGUNDOS_POR_LANCE
        ).iniciar()
        try:
            lance = jogador.escolher_lance(
                estado,
                NivelDeMotor.SAGAZ,
                limite=orcamento,
                semente=semente_mod.semente_do_lance(nu_semente, numero),
            )
        except ValueError:
            # O motor recusa escolher lance numa posicao sem lance legal — o que
            # e, ele proprio, um fim de partida. Perguntar ao arbitro confirma.
            veredito = veredito_de(estado)
            return Prova(
                tem_fim=veredito.acabou,
                nu_lances=numero - 1,
                co_motivo=veredito.co_motivo,
            )

        estado = (
            jogador.aplicar(estado, lance)
            if hasattr(jogador, "aplicar")
            else estado.com_lance(lance)
        )

    # Estourou o teto sem terminar.
    return Prova(tem_fim=False, nu_lances=teto_de_lances)


def prova_a_partir_da_regua(desfechos: list[Any]) -> Prova:
    """Aproveita o que a regua ja viu, sem jogar um lance a mais.

    Args:
        desfechos: os `Veredito` finais das execucoes da regua.

    ⚠️ **Uma execucao terminal basta.** A pergunta e se a partida *pode* acabar, e
    nao se ela *sempre* acaba — um desafio em que so um dos caminhos leva ao fim
    continua sendo um desafio de um jogo que tem fim.

    ⚠️ Lista vazia devolve `tem_fim=False`: **nada a inspecionar e falha, nao
    sucesso**. E o mesmo principio do cadeado de uniao de XP.
    """
    for veredito in desfechos:
        if getattr(veredito, "acabou", False):
            return Prova(
                tem_fim=True,
                nu_lances=0,
                co_motivo=getattr(veredito, "co_motivo", None),
            )
    return Prova(tem_fim=False, nu_lances=0)
