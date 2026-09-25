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

⛔ **E ate 11/09/2026 era exatamente a pergunta errada que o codigo fazia.** O
cabecalho acima ja estava escrito, mas `tentativa_com_motor` usava o nivel do
mascote medido para **todos** os lances — os dois lados do tabuleiro. A regua
media *"Cacau contra Cacau"*, e nao *"Cacau contra o adversario do dia"*, que e
o que a pessoa vai enfrentar.

⚠️ **Um comentario correto nao conserta um codigo errado**, e este arquivo e o
exemplo: a intencao estava documentada, e a implementacao nunca a cumpriu.

═══════════════════════════════════════════════════════════════════════════
⚠️ O CARIMBO NAO E OPCIONAL
═══════════════════════════════════════════════════════════════════════════

Cada linha leva `co_versao_perfil` e `co_versao_motor` (RF-DES-146). Sem eles,
*"14 de 20"* e um numero **sem regua** — e a regua muda quando o perfil e afinado
ou quando a busca e corrigida.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

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
#:
#: ═══════════════════════════════════════════════════════════════════════════
#: ⛔ DESDE 25/09/2026 ESTE TETO NÃO CORTA MAIS A BUSCA DAS DAMAS
#: ═══════════════════════════════════════════════════════════════════════════
#:
#: Ele continua contando o que foi gasto e continua respondendo `cancelado()` —
#: mas ⛔ **não reduz mais o teto do nível**. Nas damas quem joga é o motor Dart
#: compilado, o mesmo do aparelho, e o orçamento que vale é o do **contrato**.
#:
#: ⛔ **O motivo é o defeito que custou a investigação de 25/09.** O adversário
#: do dia é o mesmo personagem que responde no aparelho de quem resolve. Com um
#: teto menor aqui, ele escolhe outro lance no meio da partida, e o gabarito
#: publicado deixa de ser reproduzível a partir dali. Medido na posição que abriu
#: o caso: o servidor parava em **24.576 nós** e jogava `19-23`; o aparelho via
#: **288.001** e jogava `16-20`. Era o `19-23` que estava no painel de curadoria.
#:
#: ⚠️ **E o teto existia por um motivo real, que acabou:** o port Python é ~40x
#: mais lento que o motor do aparelho, e sem coleira uma geração de damas passava
#: de 6 minutos. O Dart cumpre os 288 mil nós do Sagaz em ~0,7 s.
#:
#: ⚠️ **No Pontinhos ele continua cortando**, porque lá o motor é o do espelho e
#: a conta é outra. Ver `motores/damas/motor_damas.py`.
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
    maximo_de_meios_lances: int,
    co_personagem_do_dia: str,
    solucionador=None,
) -> Callable[[str, int], bool]:
    """Monta a funcao `tentar` que a regua consome, usando um motor de verdade.

    ⚠️ **Cada execucao recebe uma semente propria** (`semente_do_lance` sobre o
    par candidato/execucao): sem isso, as 20 execucoes de um mascote seriam
    identicas, e "14 de 20" so poderia dar 0 ou 20.

    ⛔ **E cada LADO recebe o seu nivel.** O mascote medido joga o lado de quem
    resolve; o adversario do dia joga o outro. Ver o topo do modulo: ate
    11/09/2026 o nivel do mascote medido era aplicado aos dois lados, e a taxa
    descrevia uma partida que ninguem joga.

    ⛔ **E `solucionador`, de 16/09/2026, e a MESMA licao outra vez.** Quando o
    tipo tem um solucionador proprio (`gerador.SOLUCIONADOR_POR_TIPO`), a geracao
    o usa e ⚠️ **a regua nao usava** — entao `pontinhos_cadeia_longa` era gerado
    pelo arquiteto e medido pelo Sagaz, que e o pior solucionador possivel para
    ele (7% contra 43%, medido em 30 posicoes).

    ⚠️ **O solucionador proprio nao tem nivel**, e isso e uma limitacao conhecida:
    ele joga igual para Cacau e para Magno, e a escada daquele tipo passa a
    depender so do adversario. ⛔ E ainda assim e melhor que o anterior — medir com
    o solucionador errado nao mede a dificuldade de coisa nenhuma.
    """
    nivel_do_adversario = NIVEL_POR_PERSONAGEM[co_personagem_do_dia]
    # ⚠️ Quem resolve e quem joga primeiro — a mesma definicao do julgamento.
    vez_do_solucionador = estado_inicial.vez_de

    def tentar(co_personagem: str, execucao: int) -> bool:
        nivel = NIVEL_POR_PERSONAGEM[co_personagem]
        atual = estado_inicial
        fita: list[dict[str, Any]] = []

        for numero in range(1, maximo_de_meios_lances + 1):
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
                if solucionador is not None and atual.vez_de == vez_do_solucionador:
                    # ⚠️ **So a vez de quem resolve** — a mesma fronteira do
                    # `_resolver` da geracao. O adversario do dia continua sendo
                    # o personagem publicado, no nivel dele.
                    lance = solucionador(
                        getattr(jogador, "arbitro", jogador), atual
                    )
                else:
                    lance = jogador.escolher_lance(
                        atual,
                        nivel
                        if atual.vez_de == vez_do_solucionador
                        else nivel_do_adversario,
                        limite=orcamento,
                        semente=semente,
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


def taxa_media(medicoes: Sequence[Medicao]) -> float:
    """A taxa media dos mascotes medidos.

    ⚠️ **Escrita uma vez.** Ate 11/09/2026 esta conta existia identica dentro de
    `dentro_da_banda` e de `distancia_da_banda`, e o log precisava de uma
    terceira copia para dizer ao dono se o candidato ficou **acima** ou
    **abaixo** da banda. Tres copias de uma media e uma divergencia esperando o
    dia em que alguem mudar o criterio (ponderar pelo mascote, por exemplo) num
    lugar so.

    Args:
        medicoes: as linhas da regua daquele candidato. ⛔ Nao pode ser vazia —
            quem chama ja precisa ter tratado esse caso, porque "nada medido"
            nao tem media, e devolver zero faria o desafio parecer duríssimo.
    """
    return sum(m.taxa for m in medicoes) / len(medicoes)


#: A folga que absorve o erro de ponto flutuante na comparacao com a banda.
#:
#: ⛔ **SEM ELA, UMA TAXA EXATAMENTE IGUAL AO TETO FICA DE FORA DA BANDA.** Tres
#: mascotes resolvendo 8 de 10 dao `0.8 + 0.8 + 0.8 / 3 = 0.8000000000000002`, que
#: e **maior** que o teto `0.80` — e o candidato perfeitamente calibrado seria
#: recusado, guardado como "menos pior" e provavelmente trocado por outro.
#:
#: ⚠️ **Nada no log acusaria**, porque o log imprime `0.80` arredondado: a linha
#: diria *"taxa 0.80, fora da banda [0.70, 0.80]"*, e quem lesse procuraria o
#: defeito em qualquer lugar menos na decima sexta casa decimal.
#:
#: ⚠️ O valor e menor que qualquer taxa que a regua consegue produzir: com 20
#: execucoes e 3 mascetes, o menor passo e 1/60 ≈ 0,017. ⛔ Entao esta folga nunca
#: aceita um candidato que erraria a banda **de verdade**.
TOLERANCIA_DA_BANDA = 1e-9


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
    media = taxa_media(medicoes)
    # ⚠️ Com a folga nas duas pontas — ver `TOLERANCIA_DA_BANDA`.
    return piso - TOLERANCIA_DA_BANDA <= media <= teto + TOLERANCIA_DA_BANDA


def distancia_da_banda(
    medicoes: Sequence[Medicao], *, piso: float, teto: float
) -> float:
    """Quao longe da banda a taxa media ficou. Zero quando esta dentro.

    Args:
        medicoes: as linhas da regua daquele candidato.
        piso, teto: a banda alvo.

    Returns:
        A distancia em fracao de taxa — `0.05` quer dizer "cinco pontos
        percentuais fora".

    ⚠️ **Existe para ESCOLHER entre candidatos que nenhum coube.** Sem ela, a
    unica resposta possivel seria "nenhum serve", e o dia ficaria descoberto — o
    unico defeito deste job que a pessoa ve na tela. Com ela da para publicar o
    **menos pior** e dizer, no log, de quanto foi o erro.

    ⚠️ **Lista vazia devolve infinito**, e nao zero: nada a medir nao pode virar
    "encaixou perfeitamente". E o mesmo principio do cadeado de uniao de XP.
    """
    if not medicoes:
        return float("inf")
    media = taxa_media(medicoes)
    # ⛔ **As duas funcoes usam a MESMA folga**, e isso nao e simetria decorativa:
    # `dentro_da_banda` dizendo "sim" enquanto `distancia_da_banda` devolve um
    # numero positivo seria uma contradicao que o job carregaria em silencio.
    if media < piso - TOLERANCIA_DA_BANDA:
        return piso - media
    if media > teto + TOLERANCIA_DA_BANDA:
        return media - teto
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# ⛔ A ESCADA — o criterio que o dono trocou em 16/09/2026
# ═══════════════════════════════════════════════════════════════════════════
#
# > *"Com relacao a regua, se ela esta impactando na dificuldade, mesmo tendo
# > sido uma decisao minha no passado, precisamos ajusta-la. Pouquissimos ou
# > quase nenhum dos desafios serem resolviveis pela Cacau, poucos pela Pita, uma
# > quantidade maior pelo Tex (talvez mais da metade) e quase sempre o Magno
# > resolve os desafios."*
#
# ⛔ **POR QUE A MEDIA PRODUZIA DESAFIOS FACEIS, e isto nao e opiniao.** Junte
# duas coisas que ja estavam medidas:
#
#   1. a banda exigia **media 0,70-0,80 dos tres**, e um dos tres e sempre o mais
#      fraco disponivel;
#   2. ⛔ a regua mede **cumprimento ACIDENTAL** (15/09/2026): o mascote nao le o
#      enunciado, ele joga a partida.
#
# Logo, para a media chegar a 0,75 **com a Cacau dentro**, o objetivo tinha de
# acontecer sozinho em ~70% das partidas de um jogador fraco. ⚠️ Um objetivo que
# acontece sozinho nessa frequencia e, por definicao, quase inevitavel — e a
# banda estava **selecionando os desafios cujo objetivo mais se confunde com
# jogar normalmente**. Viés de selecao, e nao erro de calibracao.
#
# ⚠️ **E RF-DES-016 NASCEU ASSIM** — *"a PITA precisa resolver, e a CACAU nao"*.
# RF-DES-204 reescreveu para *"a taxa dos tres"* e **nao diz media**: a media foi
# escolha do codigo, e este bloco a desfaz.
#
# ⚠️ **A media nao foi apagada.** Ela continua sendo calculada, gravada e
# impressa no log — e o que mudou e **quem decide**. As duas respondem perguntas
# diferentes, e a media continua sendo a forma mais curta de dizer a um humano
# quao dificil o dia ficou.

#: A faixa de taxa esperada de cada mascote, do mais fraco ao mais forte.
#:
#: ⚠️ **As faixas se SOBREPOEM de proposito.** Um perfil de pontos exatos
#: ("Cacau 0,10") seria inalcancavel com 20 execucoes, onde o passo e 0,05; e um
#: perfil sem sobreposicao obrigaria a escada a ser ingreme em todos os tipos,
#: quando ela so precisa ser **crescente**.
#:
#: ⛔ **Estes numeros sao a primeira leitura da frase do dono, e vao ser
#: corrigidos pela medicao** — e essa e a ordem certa: o criterio muda primeiro,
#: os numeros se ajustam ao que o acervo consegue entregar. O que nao se faz e o
#: contrario.
ESCADA_ALVO: dict[str, tuple[float, float]] = {
    # *"quase nenhum"* — a Cacau resolvendo muito e o sinal de desafio banal.
    "cacau": (0.00, 0.20),
    # *"poucos"*
    "pita": (0.05, 0.45),
    # *"uma quantidade maior (talvez mais da metade)"*
    "tex": (0.45, 0.85),
    # *"quase sempre o Magno resolve"* — e este e o piso de RESOLUBILIDADE.
    "magno": (0.75, 1.00),
}


def _distancia_da_faixa(taxa: float, faixa: tuple[float, float]) -> float:
    """Quanto a taxa ficou fora da faixa daquele mascote. Zero quando dentro."""
    piso, teto = faixa
    if taxa < piso - TOLERANCIA_DA_BANDA:
        return piso - taxa
    if taxa > teto + TOLERANCIA_DA_BANDA:
        return taxa - teto
    return 0.0


def distancia_da_escada(
    medicoes: Sequence[Medicao],
    *,
    escada: "Mapping[str, tuple[float, float]] | None" = None,
) -> float:
    """Quao longe do perfil do dono a escada deste candidato ficou.

    ⚠️ **E a media das distancias, uma por mascote medido** — e nao a distancia da
    media, que e o criterio antigo. A diferenca importa: `0,00 / 0,50 / 1,00` tem
    media 0,50 e parece calibrado, enquanto a escada ve que a Cacau esta no lugar,
    o Tex tambem e o Magno **falhou o piso de resolubilidade**.
    """
    if not medicoes:
        # ⚠️ Nada medido nao pode virar "encaixou perfeitamente" — o mesmo
        # principio de `distancia_da_banda`.
        return float("inf")
    alvo = ESCADA_ALVO if escada is None else escada
    faltas = [
        _distancia_da_faixa(m.taxa, alvo[m.co_personagem])
        for m in medicoes
        if m.co_personagem in alvo
    ]
    if not faltas:
        return float("inf")
    return sum(faltas) / len(faltas)


def dentro_da_escada(
    medicoes: Sequence[Medicao],
    *,
    escada: "Mapping[str, tuple[float, float]] | None" = None,
) -> bool:
    """Todos os mascotes medidos caem na faixa deles?

    ⚠️ **O adversario do dia nao entra**, porque nao e medido (ver o cabecalho do
    modulo) — entao a escada e julgada sobre tres degraus, e quais tres depende de
    quem foi sorteado. ⛔ Isso e uma assimetria conhecida e nao resolvida: no dia
    do Magno, o degrau que garante a **resolubilidade** e justamente o que falta.
    """
    return bool(medicoes) and distancia_da_escada(medicoes, escada=escada) == 0.0


def descrever_escada(
    medicoes: Sequence[Medicao],
    *,
    escada: "Mapping[str, tuple[float, float]] | None" = None,
) -> str:
    """A escada em uma linha, para o log: `cacau 0.05 ✅ · pita 0.60 ⛔(+0.15)`.

    ⚠️ **O que o dono precisa ler nao e a distancia, e sim QUAL degrau errou.** Uma
    distancia media de 0,15 pode ser um mascote muito fora ou tres pouco fora, e as
    duas pedem reacoes opostas: a primeira e um tipo mal escolhido, a segunda e
    calibracao.
    """
    alvo = ESCADA_ALVO if escada is None else escada
    partes = []
    for medicao in medicoes:
        faixa = alvo.get(medicao.co_personagem)
        if faixa is None:
            partes.append(f"{medicao.co_personagem} {medicao.taxa:.2f} (sem alvo)")
            continue
        falta = _distancia_da_faixa(medicao.taxa, faixa)
        if falta == 0.0:
            partes.append(f"{medicao.co_personagem} {medicao.taxa:.2f} ✅")
        else:
            sinal = "+" if medicao.taxa > faixa[1] else "-"
            partes.append(
                f"{medicao.co_personagem} {medicao.taxa:.2f} ⛔({sinal}{falta:.2f} "
                f"de [{faixa[0]:.2f},{faixa[1]:.2f}])"
            )
    return " · ".join(partes)
