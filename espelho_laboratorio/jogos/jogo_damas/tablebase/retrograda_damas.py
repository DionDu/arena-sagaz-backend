"""Análise retrógrada: o resultado **exato** de todo final com poucas peças.

A ideia, que inverte o sentido normal de pensar sobre um jogo
--------------------------------------------------------------
Um motor de busca olha para a frente e chuta. Aqui se olha para **trás** e se
sabe:

1. **Comece pelo que já está decidido.** Quem não tem lance legal perdeu —
   "imobilizar ou capturar todas as peças do adversário". Essas posições são
   marcadas direto.
2. **Ande um lance para trás.** Uma posição é **vitória** se existe *algum*
   lance meu que leva a uma posição já marcada como derrota do adversário. É
   **derrota** se *todos* os meus lances levam a vitórias dele.
3. **Repita até nada mais mudar.** O que sobrou sem marca é **empate** — ninguém
   consegue forçar nada.

O resultado não é estimativa: é o resultado do jogo perfeito. É por isso que a
base de finais tem **papel duplo** no plano — no app ela faz o fim de jogo ser
perfeito, e no PC ela é a **régua** que prova o nível Sagaz.

Por que a ordem das fatias importa
----------------------------------
Toda captura leva a uma fatia com menos peças; toda promoção troca pedra por dama
sem mudar o total. Resolvendo na ordem de `fatias_ate`, quando uma fatia é
processada **todas as suas saídas já estão resolvidas** — exceto os lances
tranquilos, que ficam dentro da própria fatia e são justamente o que o laço de
ponto fixo resolve.

Os empates declarados
---------------------
As Regras Oficiais brasileiras declaram empatados certos finais que a análise
retrógrada pura chamaria de vitória — o mais famoso é *três damas contra uma
dama na grande diagonal*. Uma base sem isso **mente**, e a medição do §7.1 da
proposta viraria ruído.

Eles vivem em `empates_declarados_damas.py`, e são aplicados **fatia a fatia,
logo depois de resolvê-la** — ver `construir_base`. Ficam ligados por padrão nas
brasileiras e desligados nas anglo-americanas, que não têm esses artigos.
"""
from __future__ import annotations

import random
import time
from array import array
from dataclasses import dataclass, field

from jogos.jogo_damas.motor.regras_damas import (
    BRASILEIRAS,
    Regulamento,
    aplicar_lance,
    gerar_lances,
)
from jogos.jogo_damas.motor.tabuleiro_damas import Tabuleiro
from jogos.jogo_damas.tablebase.empates_declarados_damas import (
    aplicar_empates_declarados,
    regra_aplicavel,
)
from jogos.jogo_damas.tablebase.indice_damas import (
    DERROTA,
    DESCONHECIDO,
    EMPATE,
    VITORIA,
    Fatia,
    fatia_da_posicao,
    fatias_ate,
)
from nucleo.log import obter_logger

log = obter_logger("jogos.jogo_damas.tablebase.retrograda")

_OPOSTO = {VITORIA: DERROTA, DERROTA: VITORIA, EMPATE: EMPATE}


SEM_DISTANCIA = -1
"""Marca de "não se aplica": posição de empate, ou vão da numeração."""


@dataclass
class BaseDeFinais:
    """As fatias resolvidas, prontas para consulta.

    Guarda dois vetores por fatia:

    - **`valores`** — vitória, derrota ou empate. Um byte por posição, quando
      dois bits bastariam; o empacotamento é da etapa 8, quando o tamanho passa
      a importar.
    - **`distancias`** — em quantos meios-lances a partida acaba com jogo
      perfeito. Existe porque as **regras de empate declarado** (arts. 97 a 100)
      não perguntam "quem ganha?", perguntam "ganha **em quantos lances?**". Sem
      a distância, elas não têm como ser aplicadas.
    """

    regulamento: Regulamento = BRASILEIRAS
    valores: dict[str, bytearray] = field(default_factory=dict)
    distancias: dict[str, array] = field(default_factory=dict)
    fatias: dict[str, Fatia] = field(default_factory=dict)

    def guardar(self, fatia: Fatia, valores: bytearray,
                distancias: array | None = None) -> None:
        self.valores[fatia.nome] = valores
        self.fatias[fatia.nome] = fatia
        if distancias is not None:
            self.distancias[fatia.nome] = distancias

    def distancia_de(self, tabuleiro: Tabuleiro) -> int:
        """Em quantos meios-lances a partida acaba, com jogo perfeito.

        `SEM_DISTANCIA` para empate e para posição fora da base.
        """
        fatia = fatia_da_posicao(tabuleiro)
        guardado = self.distancias.get(fatia.nome)
        if guardado is None:
            return SEM_DISTANCIA
        return guardado[fatia.da_posicao(tabuleiro)]

    def tem(self, fatia: Fatia) -> bool:
        return fatia.nome in self.valores

    def consultar(self, tabuleiro: Tabuleiro) -> int | None:
        """O resultado exato desta posição, do ponto de vista de quem tem a vez.

        ``None`` quando a posição está fora da base — material demais. Quem
        chama precisa tratar: confundir "fora da base" com "empate" faria o motor
        achar que toda posição de meio-jogo é equilibrada.
        """
        fatia = fatia_da_posicao(tabuleiro)
        if not fatia.tem_os_dois_lados:
            # Um dos lados ficou sem peça: quem tem a vez não tem o que jogar.
            return DERROTA if _sem_pecas(tabuleiro) else VITORIA
        guardado = self.valores.get(fatia.nome)
        if guardado is None:
            return None
        return guardado[fatia.da_posicao(tabuleiro)]

    @property
    def total_de_posicoes(self) -> int:
        return sum(len(v) for v in self.valores.values())

    def contar_resultados(self) -> dict[int, int]:
        """Quantas posições de cada resultado a base tem, somando todas as fatias."""
        contagem = {VITORIA: 0, DERROTA: 0, EMPATE: 0}
        for valores in self.valores.values():
            for resultado in (VITORIA, DERROTA, EMPATE):
                contagem[resultado] += valores.count(resultado)
        return contagem


@dataclass(frozen=True)
class Inconsistencia:
    """Uma posição cujo valor guardado não bate com o dos próprios sucessores."""

    fen: str
    fatia: str
    guardado: int
    esperado: int


def conferir_consistencia(
    base: BaseDeFinais,
    fatias: list[Fatia] | None = None,
    amostra_por_fatia: int | None = None,
    semente: int = 20260728,
) -> list[Inconsistencia]:
    """Confere a base contra ela mesma: o valor de X bate com o dos filhos?

    **Este é o teste que faltava, e ele custou caro.** Em 2026-07-28, ~0,6% das
    posições da base de 5 peças estavam gravadas como *empate* sendo vitória ou
    derrota — porque o laço de camadas parava antes de alcançar as distâncias que
    chegavam de fora da fatia. Nada disso dava erro: dava uma base que responde
    com confiança sobre a posição errada, que é o pior defeito possível aqui.

    O que a conferência usa é a definição do jogo, e não a implementação:

    > O valor de uma posição é o **melhor** entre os valores dos seus sucessores,
    > trocados de sinal. Vitória > empate > derrota.

    Por isso ela é uma testemunha independente da análise retrógrada — do mesmo
    jeito que `minimax_sem_poda` é testemunha da poda alfa-beta.

    ⚠️ **Fatias com empate declarado (arts. 97 a 100) ficam de fora.** Ali o valor
    guardado é uma decisão de *regulamento*, não o resultado do jogo perfeito, e
    ele legitimamente discorda dos sucessores. Conferi-las aqui produziria
    "erros" que não são erros.

    Args:
        base: a base a conferir.
        fatias: quais conferir. `None` = todas as carregadas.
        amostra_por_fatia: quantas posições sortear por fatia. `None` = todas,
            que é o que se quer nas fatias pequenas e é caro demais nas grandes.

    Returns:
        A lista de inconsistências. **Vazia** é o único resultado aceitável.
    """
    aleatorio = random.Random(semente)
    escolhidas = fatias if fatias is not None else list(base.fatias.values())
    achados: list[Inconsistencia] = []

    for fatia in escolhidas:
        if fatia.nome not in base.valores:
            continue
        if regra_aplicavel(fatia) is not None:
            continue

        if amostra_por_fatia is None:
            indices = range(fatia.tamanho)
        else:
            indices = [
                aleatorio.randrange(fatia.tamanho)
                for _ in range(min(amostra_por_fatia, fatia.tamanho))
            ]

        for indice in indices:
            tabuleiro = fatia.para_posicao(indice)
            if tabuleiro is None:
                continue                      # vão da numeração
            lances = gerar_lances(tabuleiro, base.regulamento)
            if not lances:
                continue                      # terminal: não tem sucessor

            valores_dos_filhos = []
            for lance in lances:
                do_filho = base.consultar(aplicar_lance(tabuleiro, lance))
                if do_filho is None:
                    break                     # fatia não carregada: não dá para conferir
                valores_dos_filhos.append(_OPOSTO[do_filho])
            else:
                # VITORIA(2) > EMPATE(1) > DERROTA(0): o melhor é o máximo.
                esperado = max(valores_dos_filhos)
                guardado = base.valores[fatia.nome][indice]
                if guardado != esperado:
                    achados.append(Inconsistencia(
                        fen=tabuleiro.para_fen(), fatia=fatia.nome,
                        guardado=guardado, esperado=esperado,
                    ))

    return achados


def _maior_distancia(distancias: array) -> int:
    """A maior distância já atribuída. Serve de teto para a varredura por camada:
    enquanto houver posição decidida numa camada mais funda, ainda pode haver
    outra que dependa dela."""
    maior = -1
    for d in distancias:
        if d > maior:
            maior = d
    return maior


def _sem_pecas(tabuleiro: Tabuleiro) -> bool:
    """Quem tem a vez ficou sem nenhuma peça?"""
    return not tabuleiro.casas_de(tabuleiro.vez)


def resolver_fatia(
    fatia: Fatia, base: BaseDeFinais, regulamento: Regulamento = BRASILEIRAS
) -> tuple[bytearray, array]:
    """Resolve uma fatia inteira, supondo as menores já resolvidas.

    Devolve (resultados, distâncias): um resultado e uma distância por índice, do
    ponto de vista de **quem tem a vez** naquela posição. A distância é em
    meios-lances até o fim da partida, e é `SEM_DISTANCIA` no empate.
    """
    valores = bytearray([DESCONHECIDO]) * fatia.tamanho
    distancias = array("h", [SEM_DISTANCIA]) * fatia.tamanho

    # Os sucessores que saem da fatia (captura ou promoção) já têm resposta; os
    # que ficam dentro dela dependem do laço adiante. Separar os dois aqui evita
    # refazer geração de lances a cada passada — que é o que domina o custo.
    # Cada sucessor externo vira o par (resultado, distância), já resolvido.
    sucessores: dict[int, tuple[list[int], list[tuple[int, int]]]] = {}

    # A maior distância que chega de FORA da fatia. Ela é o teto de verdade do
    # laço de camadas — ver o comentário do critério de parada, adiante.
    maior_distancia_externa = -1

    for indice in range(fatia.tamanho):
        tabuleiro = fatia.para_posicao(indice)
        if tabuleiro is None:
            valores[indice] = EMPATE      # vão da numeração: nunca consultado
            continue

        lances = gerar_lances(tabuleiro, regulamento)
        if not lances:
            valores[indice] = DERROTA     # sem lance legal, perdeu
            distancias[indice] = 0        # a partida acaba aqui mesmo
            continue

        internos: list[int] = []
        externos: list[tuple[int, int]] = []
        for lance in lances:
            depois = aplicar_lance(tabuleiro, lance)
            fatia_alvo = fatia_da_posicao(depois)

            if fatia_alvo == fatia:
                internos.append(fatia.da_posicao(depois))
                continue

            resultado = base.consultar(depois)
            if resultado is None:
                raise RuntimeError(
                    f"a fatia {fatia_alvo.nome} não estava resolvida quando "
                    f"{fatia.nome} precisou dela — ordem de dependência quebrada"
                )
            distancia = _distancia_externa(base, depois, resultado)
            externos.append((resultado, distancia))
            if distancia > maior_distancia_externa:
                maior_distancia_externa = distancia

        sucessores[indice] = (internos, externos)

    # --- propagação POR CAMADA DE DISTÂNCIA ---------------------------------
    #
    # ⚠️ A primeira versão disto iterava até o ponto fixo percorrendo os índices
    # em ordem, marcando cada posição assim que a condição batesse. O
    # **resultado** saía certo — o ponto fixo não depende da ordem —, mas a
    # **distância** saía dependente dela: uma vitória podia ser descoberta por um
    # caminho longo antes de o curto existir, e ficava com a distância errada.
    #
    # Isso apareceu como uma assimetria: fatias espelhadas davam os mesmos
    # resultados e distâncias diferentes. Não era detalhe — as regras de empate
    # declarado dos arts. 97 a 100 perguntam exatamente "ganha em quantos
    # lances?", e uma distância inflada declara empate onde não há.
    #
    # A correção é processar em camadas: primeiro tudo que se decide em 1
    # meio-lance, depois em 2, e assim por diante. Aí a primeira marca que uma
    # posição recebe é, por construção, a de distância mínima.
    camada = 0
    while True:
        mudou = False

        # Vitória em `camada + 1`: existe um sucessor que é derrota EXATAMENTE
        # em `camada`. Como as camadas anteriores já foram esgotadas, esta é a
        # vitória mais curta possível para esta posição.
        for indice, (internos, externos) in sucessores.items():
            if valores[indice] != DESCONHECIDO:
                continue
            perde_agora = any(r == DERROTA and d == camada for r, d in externos)
            if not perde_agora:
                perde_agora = any(
                    valores[i] == DERROTA and distancias[i] == camada
                    for i in internos
                )
            if perde_agora:
                valores[indice] = VITORIA
                distancias[indice] = camada + 1
                mudou = True

        # Derrota em `camada + 1`: **todos** os sucessores já são vitória, e o
        # mais distante deles está exatamente em `camada` — quem perde resiste o
        # máximo que puder.
        for indice, (internos, externos) in sucessores.items():
            if valores[indice] != DESCONHECIDO:
                continue
            resultados = list(externos)
            for i in internos:
                resultados.append((valores[i], distancias[i]))
            if all(r == VITORIA for r, _ in resultados) and \
                    max(d for _, d in resultados) == camada:
                valores[indice] = DERROTA
                distancias[indice] = camada + 1
                mudou = True

        camada += 1
        # Uma camada vazia não encerra sozinha: uma derrota longa pode depender
        # de vitórias ainda mais longas. Só se para quando nada mais é decidível,
        # e o teto é o número de posições.
        #
        # ⚠️ CORRIGIDO EM 2026-07-28, e o bug era grave e silencioso. O teto
        # olhava só as distâncias JÁ ATRIBUÍDAS DENTRO da fatia
        # (`_maior_distancia`) e ignorava as que chegam de fora. Numa fatia cujas
        # posições internas se decidem em ~16 camadas, mas que tem sucessores
        # externos a 32 ou 40 meios-lances do fim, o laço parava na camada 17: as
        # posições que dependiam daqueles sucessores ficavam DESCONHECIDO e, no
        # fecho abaixo, viravam **EMPATE**.
        #
        # Não dava erro, não dava exceção: dava uma base que responde "empate"
        # com confiança sobre posições ganhas ou perdidas. Apareceu em ~0,6% das
        # posições de 5 peças (a base de 4 escapou por acaso: lá as camadas
        # internas cobrem o intervalo das externas sem lacuna).
        teto = max(_maior_distancia(distancias), maior_distancia_externa)
        if not mudou and camada > teto:
            break
        if camada > fatia.tamanho:
            break

    passadas = camada

    # O que sobrou sem marca é empate: ninguém força nada.
    for indice in range(fatia.tamanho):
        if valores[indice] == DESCONHECIDO:
            valores[indice] = EMPATE

    log.info("fatia %s (%s) — %d índices, %d passadas",
             fatia.nome, fatia, fatia.tamanho, passadas)
    return valores, distancias


def _distancia_externa(base: BaseDeFinais, depois: Tabuleiro, resultado: int) -> int:
    """A distância de um sucessor que caiu em outra fatia.

    Quando a captura zerou um dos lados, a fatia nem existe na base: a partida
    acabou naquele lance, e a distância é 0.
    """
    if resultado == EMPATE:
        return SEM_DISTANCIA
    if not fatia_da_posicao(depois).tem_os_dois_lados:
        return 0
    return base.distancia_de(depois)


def construir_base(
    total_de_pecas: int = 4,
    regulamento: Regulamento = BRASILEIRAS,
    aplicar_regras_de_empate: bool | None = None,
) -> BaseDeFinais:
    """Resolve todas as fatias com até N peças, na ordem de dependência.

    Args:
        aplicar_regras_de_empate: se os arts. 99 e 100 entram. O padrão sai do
            campo `empates_declarados_por_posicao` do regulamento — ligado nas
            brasileiras e na Damas de Casa, desligado nas anglo-americanas e nas
            portuguesas, que não têm esses artigos. Passar explicitamente serve
            para medir o que a regra muda, comparando as duas bases.

            ⚠️ Até 2026-07-29 este padrão era `identificador == "brasileira"`, e
            teria dado à Damas de Casa uma base **sem** os empates declarados —
            uma base que aponta vitória onde a modalidade manda empatar. Bug sem
            sintoma, do mesmo tipo que a auditoria de 28/07 achou.

    A aplicação acontece **fatia a fatia, logo depois de resolvê-la**, e não no
    fim. Tem de ser assim: as fatias grandes decidem consultando o resultado das
    pequenas, e uma regra que chegasse atrasada as deixaria decidindo em cima de
    vitórias que o regulamento não reconhece.
    """
    if aplicar_regras_de_empate is None:
        aplicar_regras_de_empate = regulamento.empates_declarados_por_posicao

    base = BaseDeFinais(regulamento=regulamento)
    comeco = time.monotonic()
    total_declarado = 0

    for fatia in fatias_ate(total_de_pecas):
        valores, distancias = resolver_fatia(fatia, base, regulamento)
        if aplicar_regras_de_empate:
            mudadas = aplicar_empates_declarados(fatia, valores, distancias)
            if mudadas:
                total_declarado += mudadas
                log.info("  fatia %s — %d posições viraram empate por regra "
                         "(%s)", fatia.nome, mudadas,
                         regra_aplicavel(fatia).onde_no_documento)
        base.guardar(fatia, valores, distancias)

    if aplicar_regras_de_empate:
        log.info("empates declarados pelos arts. 97 a 100: %d posições",
                 total_declarado)

    contagem = base.contar_resultados()
    log.info(
        "base de %d peças pronta em %.1fs — %d posições "
        "(%d vitórias, %d derrotas, %d empates)",
        total_de_pecas, time.monotonic() - comeco, base.total_de_posicoes,
        contagem[VITORIA], contagem[DERROTA], contagem[EMPATE],
    )
    return base
