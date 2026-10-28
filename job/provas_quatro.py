"""AS PROVAS de cada tipo de desafio do Quatro em Linha (T116 da spec 010).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE MÓDULO RESPONDE
═══════════════════════════════════════════════════════════════════════════

Antes de uma posição virar desafio, o job pergunta: *esta posição serve a este
tipo?* (`contracts/desafio-quatro.md` §2, coluna "o job prova"). São duas
famílias de resposta:

  * **as que a busca PROVA** - cinco tipos cuja graça é um fato do jogo, e não
    um gosto: "vença em N" (a vitória forçada existe em N lances da pessoa, e
    não em N-1), "segure o Magno" (o empate existe e a maioria das colunas
    perde), "única coluna" (exatamente uma não perde), "sem o meio" (a vitória
    existe com a coluna do meio proibida à pessoa) e "virada" (a posição PARECE
    do adversário, e a busca prova a vitória da pessoa);
  * **as que só precisam do objetivo AO ALCANCE** - os outros cinco (diagonal,
    golpe duplo, linha de cinco, encostadas, bloquear): a prova diz que o
    tabuleiro ainda comporta o objetivo, e quem decide se ele é bom é a régua
    ("a Pita resolve, a Cacau não", T117).

⚠️ **"Provar" quer dizer a busca TERMINAR com a resposta**, e não estimar. Quando
a busca estoura o teto de nós sem decidir, a resposta é "não provado", e a
posição é descartada como qualquer outra: o laço do gerador tem centenas de
posições para tentar, e um desafio publicado com uma prova pela metade ensinaria
a pessoa a procurar uma vitória que talvez não exista.

═══════════════════════════════════════════════════════════════════════════
⛔ A BUSCA É A DO EXECUTÁVEL, E NÃO UMA SEGUNDA ESCRITA EM PYTHON
═══════════════════════════════════════════════════════════════════════════

Quem responde "há vitória forçada daqui?" é o comando `buscar` do motor Dart
(`JogadorDartQuatro.buscar`), o mesmo código que o aparelho embarca. O Python
só COMBINA as respostas: pergunta por coluna, conta, e - no "sem o meio" -
percorre a árvore E/OU com a busca podando cada ramo. As regras (lances legais,
desfecho) são do árbitro Python, que não escolhe lance.

A leitura da resposta segue o desenho da busca (`busca_quatro.dart`):

  * a vitória vale `VALOR_VITORIA - lances_jogados_no_fim`, contados desde o
    tabuleiro vazio. Então `|avaliacao| > LIMIAR_DECIDIDO` = alguém vence à
    força, o sinal diz quem (a avaliação é do ponto de vista do jogador 1), e
    a DISTÂNCIA até o fim sai da conta: `VALOR_VITORIA - |avaliacao| -
    lances_jogados_agora` meios-lances;
  * a busca aprofunda de um em um e para na 1ª profundidade que decide, então
    a distância é a MÍNIMA: é isso que prova o "e não em N-1" de graça;
  * motivo `profundidade` com avaliação zero = a busca viu o fim de todos os
    caminhos sem cortar nenhum no horizonte: **empate provado**. Com motivo
    `nos`, nada está provado.

⚠️ **E há uma terceira família, ainda fora de `PROVAS`** (T124c, 21/10/2026):
o objetivo FORÇÁVEL (`ProvadorQuatro.objetivo_forcavel`). A régua mostrou que
"ao alcance" não basta no golpe duplo e na linha de cinco - nem quem persegue o
objetivo no nível do Magno o alcançou. Ela entra no lugar da prova "ao alcance"
desses dois só depois da medição por fase
(`scripts/medir_objetivo_forcavel_quatro.py`), que diz se a taxa de posições
que passam cabe no gerador.

Os três números da busca estão aqui como constantes nomeadas, e um teste os
confere contra o fonte Dart do espelho (`test_provas_quatro.py`): mudou lá,
o teste reprova antes de uma prova passar a ler errado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

from motores.nucleo.chegada import LinhaDeChegada, avaliar
from motores.quatro import feitos_quatro
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, TabuleiroQuatro

from job import figuras_quatro

#: O valor-base da vitória na busca (`valorVitoriaQuatro`).
VALOR_VITORIA = 1000

#: Acima disto, em valor absoluto, a partida está decidida (`limiarDecididoQuatro`).
LIMIAR_DECIDIDO = VALOR_VITORIA - 64

#: O limite contra partida sem fim (`profundidadeMaximaQuatro`). Uma busca que
#: chegou até ele parou por ele, e não por ter visto o fim de tudo.
PROFUNDIDADE_MAXIMA = 100

#: O peso de uma ameaça na linha da paridade certa para o dono dela
#: (`pesoAmeacaNaParidadeQuatro`, em `heuristica_quatro.dart`).
PESO_AMEACA_NA_PARIDADE = 32

#: Quanto a heurística tem de dar ao adversário para a posição PARECER dele, na
#: prova da virada: o valor de uma ameaça na linha certa. Abaixo disso a
#: diferença é de posição das peças, e a pessoa não a enxerga (27/10/2026).
LIMIAR_DA_VIRADA = PESO_AMEACA_NA_PARIDADE

#: Quantos nós cada pergunta à busca pode gastar. ⚠️ Aqui não há aparelho
#: esperando: o teto é do JOB, e é alto para a prova terminar na maior parte das
#: posições de fim de meio-jogo. A conta: a ~3 milhões de nós por segundo no
#: executável, uma pergunta cheia custa menos de 1 s.
TETO_DA_PROVA = 2_000_000

#: O teto do "sem o meio", em meios-lances (8 lances da pessoa). A árvore E/OU
#: cresce rápido; acima disto a busca restrita é mais cara que o desafio vale.
MAXIMO_SEM_O_MEIO = 15

#: Quantas perguntas à busca o "sem o meio" pode fazer numa posição. ⚠️ Medido
#: em 20/10/2026: sem teto, uma posição de meio de jogo pediu 15.820 buscas.
#: Passou disso, a resposta é "não provado", como a de uma busca que estoura nós.
PERGUNTAS_SEM_O_MEIO = 400

#: O teto da prova de objetivo FORÇÁVEL (golpe duplo, linha de cinco), em
#: meios-lances. ⚠️ Palpite de partida, o mesmo do "sem o meio": quem diz se ele
#: serve é a medição por fase (`scripts/medir_objetivo_forcavel_quatro.py`).
MAXIMO_FORCAVEL = 15

#: Quantas perguntas à busca a prova forçável pode fazer numa posição. O mesmo
#: palpite do "sem o meio", pela mesma razão (a árvore E/OU cresce rápido).
PERGUNTAS_FORCAVEL = 400


#: As duas defesas do nó do adversário na árvore E/OU (`_Arvore.defesa`).
#:
#: * `DEFESA_DO_OBJETIVO` - TODA resposta conta, inclusive a de um adversário
#:   que lê o objetivo e só joga para estragá-lo (aceita perder a partida, desde
#:   que não do jeito pedido). É a garantia mais forte, e a das provas do gerador.
#: * `DEFESA_DO_JOGO` - contam só as respostas que o MOTOR daria: as que não
#:   perdem (ou que a busca não decidiu), e, quando todas perdem, as que adiam a
#:   derrota ao máximo. É como os quatro personagens jogam: nenhum lê o objetivo.
#:
#: ⚠️ Medido em 21/10/2026 (histórico do backend, "2026-10-21 (11)"): em 47
#: posições com a vitória livre a 5 a 12 lances, a defesa do objetivo deixou
#: passar 0 golpes duplos e 0 linhas de cinco; a do jogo, 4 e 9, a 6 a 11 lances.
#: Com muitos lances pela frente, quem só sabota sempre desmancha a forma.
DEFESA_DO_OBJETIVO = "objetivo"
DEFESA_DO_JOGO = "jogo"


class _SemPerguntas(Exception):
    """A árvore E/OU gastou as perguntas que tinha (uso interno)."""


@dataclass(slots=True)
class _Arvore:
    """O que muda de uma árvore E/OU para outra (uso interno de `_forca`).

    A árvore é uma só - a pessoa escolhe UM lance, o adversário pode responder
    QUALQUER um - e duas provas a usam: o "sem o meio" e o objetivo forçável.
    O que as separa cabe em duas funções:

    Atributos:
        quem: a pessoa (`+1`/`-1`).
        permitido: `(antes, depois) -> bool`: o lance da pessoa vale? (o "sem
            o meio" recusa a coluna central).
        folha: `(estado final) -> bool`: a partida acabou num lance da pessoa;
            isso cumpre o que se pede?
        perguntas_ate: a partir de quantas perguntas a prova desiste.
        defesa: quais respostas do adversário contam (`DEFESA_DO_OBJETIVO` ou
            `DEFESA_DO_JOGO`).
        visto: as respostas guardadas, por (tabuleiro, meios-lances restantes).
    """

    quem: int
    permitido: Callable[[EstadoQuatro, EstadoQuatro], bool]
    folha: Callable[[EstadoQuatro], bool]
    perguntas_ate: int
    defesa: str = DEFESA_DO_OBJETIVO
    visto: dict[tuple, bool] = field(default_factory=dict)


class Oraculo(Protocol):
    """Quem responde à busca e à heurística (o `JogadorDartQuatro`)."""

    def buscar(self, *, lances: str, co_modalidade: str, teto_de_nos: int) -> dict[str, Any]: ...

    def avaliar(self, *, lances: str, co_modalidade: str) -> int: ...


@dataclass(frozen=True, slots=True)
class Resultado:
    """O que a busca PROVOU sobre uma posição (jogando os dois o melhor).

    Atributos:
        vencedor: `+1` ou `-1` (vence à força), `0` (empate provado) ou `None`
            (nada provado: o teto acabou antes).
        meios_lances: com vencedor, quantos meios-lances faltam até a vitória,
            a partir desta posição. `None` sem vencedor.
        lance: o melhor lance que a busca achou (`None` sem busca). É por ele
            que o "sem o meio" começa: costuma ser o da vitória.
    """

    vencedor: int | None
    meios_lances: int | None = None
    lance: str | None = None


@dataclass(frozen=True, slots=True)
class ProvaQuatro:
    """A resposta de uma prova: passou ou não, e por quê.

    Atributos:
        passou: a posição serve ao tipo.
        motivo: uma frase que se lê meses depois sem contexto - vai ao log e,
            no descarte, a `de_motivo_descarte`.
        dados: os números que a prova achou (a coluna única, a distância), para
            o log e para quem monta o enunciado.
    """

    passou: bool
    motivo: str
    dados: Mapping[str, Any] = field(default_factory=dict)


class ProvadorQuatro:
    """Faz as perguntas à busca de UMA modalidade, guardando as respostas.

    ⚠️ **Guarda pelo TABULEIRO, e não pela sequência**: o "sem o meio" e as
    provas por coluna perguntam a mesma posição muitas vezes, e por ordens de
    lance diferentes (as transposições). Cada pergunta é uma busca cheia. A
    distância guardada é RELATIVA (meios-lances até o fim), e por isso vale para
    qualquer caminho que chegue ao mesmo tabuleiro.

    Args:
        co_modalidade: a modalidade do desafio.
        oraculo: o executável (`JogadorDartQuatro`), ou um duplo nos testes.
        teto_de_nos: o teto de cada pergunta.
    """

    def __init__(
        self, co_modalidade: str, oraculo: Oraculo, *, teto_de_nos: int = TETO_DA_PROVA
    ) -> None:
        self.co_modalidade = co_modalidade
        self.arbitro = MotorQuatro(co_modalidade)
        self.oraculo = oraculo
        self.teto_de_nos = teto_de_nos
        self._guardados: dict[tuple, Resultado] = {}
        #: Quantas perguntas foram de fato à busca (as guardadas não contam).
        #: Existe para o log dizer quanto uma prova custou.
        self.perguntas = 0

    # ── A leitura da busca ──────────────────────────────────────────────────

    def resultado(self, estado: EstadoQuatro) -> Resultado:
        """O que se prova sobre [estado], com quem tem a vez jogando primeiro."""
        chave = self._chave(estado)
        if chave not in self._guardados:
            self._guardados[chave] = self._resultado(estado)
        return self._guardados[chave]

    def _chave(self, estado: EstadoQuatro) -> tuple:
        """O tabuleiro como chave: as colunas e de quem é a vez."""
        tabuleiro = self.arbitro.tabuleiro(estado)
        return (tabuleiro.colunas, tabuleiro.vez)

    def _resultado(self, estado: EstadoQuatro) -> Resultado:
        veredito = self.arbitro.veredito(estado)
        if veredito.acabou:
            return Resultado(vencedor=veredito.vencedor, meios_lances=0)

        legais = self.arbitro.lances_legais(estado)
        if len(legais) == 1:
            # ⚠️ Com um lance só, a busca responde `lance_unico` sem buscar (valor
            # zero, nenhum nó): não é empate, é falta de pergunta. Joga-se o lance
            # e pergunta-se a posição seguinte, um meio-lance mais perto do fim.
            seguinte = self.resultado(self.arbitro.aplicar(estado, legais[0]))
            if seguinte.meios_lances is None:
                return seguinte
            return Resultado(seguinte.vencedor, seguinte.meios_lances + 1)

        self.perguntas += 1
        resposta = self.oraculo.buscar(
            lances=estado.sequencia,
            co_modalidade=self.co_modalidade,
            teto_de_nos=self.teto_de_nos,
        )
        avaliacao = int(resposta["avaliacaoJ1"])
        if abs(avaliacao) > LIMIAR_DECIDIDO:
            # Quantos lances a partida terá no instante da vitória, menos os de
            # agora: a distância, em meios-lances, jogando os dois o melhor.
            lances_no_fim = VALOR_VITORIA - abs(avaliacao)
            agora = self.arbitro.tabuleiro(estado).lances_jogados
            return Resultado(
                vencedor=1 if avaliacao > 0 else -1,
                meios_lances=lances_no_fim - agora,
                lance=resposta["lance"],
            )
        if (
            resposta["motivoParada"] == "profundidade"
            and avaliacao == 0
            and int(resposta["profundidadeAtingida"]) < PROFUNDIDADE_MAXIMA
        ):
            return Resultado(vencedor=0, lance=resposta["lance"])
        return Resultado(vencedor=None, lance=resposta["lance"])

    def por_coluna(self, estado: EstadoQuatro) -> dict[str, Resultado]:
        """O resultado provado depois de cada lance legal de quem tem a vez."""
        return {
            lance: self.resultado(self.arbitro.aplicar(estado, lance))
            for lance in self.arbitro.lances_legais(estado)
        }

    # ── As cinco provas pela busca ──────────────────────────────────────────

    def vencer_em_n(self, estado: EstadoQuatro, lances: int) -> ProvaQuatro:
        """A vitória forçada existe em [lances] lances da pessoa, e NÃO em menos.

        Em meios-lances, N lances da pessoa são `2N - 1`: os dela e as N-1
        respostas do adversário entre eles. Como a distância provada é a mínima,
        "exatamente `2N - 1`" já é "em N e não em N-1".
        """
        quem = self.arbitro.vez_de(estado)
        alvo = 2 * lances - 1
        achado = self.resultado(estado)
        if achado.vencedor != quem:
            return ProvaQuatro(False, f"sem vitória forçada provada para {quem:+d}")
        if achado.meios_lances != alvo:
            em = (achado.meios_lances + 1) // 2
            return ProvaQuatro(
                False,
                f"a vitória forçada vem em {em} lances, e não em {lances}",
                {"lances": em},
            )
        return ProvaQuatro(True, f"vitória forçada em {lances} lances, e não em menos",
                           {"lances": lances})

    def segurar_magno(self, estado: EstadoQuatro) -> ProvaQuatro:
        """O empate existe, é o melhor da pessoa, e a MAIORIA das colunas perde.

        ⚠️ Só contam as colunas PROVADAS perdedoras: uma coluna que a busca não
        decidiu não ajuda a passar (seria contar o que não se sabe).
        """
        quem = self.arbitro.vez_de(estado)
        achado = self.resultado(estado)
        if achado.vencedor != 0:
            return ProvaQuatro(
                False,
                "o melhor da pessoa não é um empate provado "
                f"(vencedor provado: {achado.vencedor})",
            )
        colunas = self.por_coluna(estado)
        perdem = sorted(l for l, r in colunas.items() if r.vencedor == -quem)
        if 2 * len(perdem) <= len(colunas):
            return ProvaQuatro(
                False,
                f"só {len(perdem)} de {len(colunas)} colunas perdem: não é a maioria",
                {"perdem": perdem},
            )
        return ProvaQuatro(
            True,
            f"o empate existe e {len(perdem)} de {len(colunas)} colunas perdem",
            {"perdem": perdem},
        )

    def unica_coluna(self, estado: EstadoQuatro) -> ProvaQuatro:
        """EXATAMENTE uma coluna legal não perde - e as outras, todas, perdem.

        As duas metades são provadas: a coluna que salva (empate ou vitória) e
        cada uma das que perdem. Uma coluna não decidida reprova, porque ela
        poderia ser a segunda salvação.
        """
        quem = self.arbitro.vez_de(estado)
        colunas = self.por_coluna(estado)
        if len(colunas) < 2:
            return ProvaQuatro(False, "há um lance legal só: não há o que escolher")
        salvam = sorted(l for l, r in colunas.items() if r.vencedor in (0, quem))
        perdem = sorted(l for l, r in colunas.items() if r.vencedor == -quem)
        if len(salvam) == 1 and len(perdem) == len(colunas) - 1:
            return ProvaQuatro(
                True,
                f"só {salvam[0]} não perde; as outras {len(perdem)} perdem",
                {"coluna": salvam[0]},
            )
        return ProvaQuatro(
            False,
            f"{len(salvam)} coluna(s) provada(s) que não perde(m), {len(perdem)} "
            f"que perde(m), de {len(colunas)}",
            {"salvam": salvam, "perdem": perdem},
        )

    def sem_o_meio(
        self,
        estado: EstadoQuatro,
        *,
        maximo_de_meios_lances: int = MAXIMO_SEM_O_MEIO,
        perguntas: int = PERGUNTAS_SEM_O_MEIO,
        defesa: str = DEFESA_DO_OBJETIVO,
    ) -> ProvaQuatro:
        """A pessoa vence à força SEM jogar na coluna do meio.

        A busca do executável não proíbe coluna, e não há por que ensiná-la (o
        app não precisa disso). Aqui se percorre a árvore E/OU: nos lances da
        pessoa, BASTA um fora do meio que leve à vitória; nos do adversário,
        TODOS têm de levar. ⚠️ **E a busca poda cada ramo**: se nem sem a
        proibição a pessoa vence à força dali, com ela também não - e a pergunta
        custa uma busca, e não a subárvore inteira.

        O teto cresce de dois em dois (aprofundamento iterativo): a 1ª
        profundidade que acha a vitória é a mais curta, e ela vai aos dados.
        `perguntas` e `defesa` são os da prova forçável (`objetivo_forcavel`);
        os padrões são os do gerador.
        """
        dimensoes = self.arbitro.regras.dimensoes
        if dimensoes.largura % 2 == 0:
            return ProvaQuatro(False, "largura par: não há coluna do meio")
        meio = (dimensoes.largura + 1) // 2
        tabuleiro = self.arbitro.tabuleiro(estado)
        if len(tabuleiro.colunas[meio - 1]) >= dimensoes.altura:
            return ProvaQuatro(
                False, "a coluna do meio já está cheia: a proibição não proíbe nada"
            )
        quem = tabuleiro.vez
        livre = self.resultado(estado)
        if livre.vencedor != quem:
            return ProvaQuatro(False, f"sem vitória forçada provada para {quem:+d}")

        # ⚠️ A vitória restrita não pode ser mais curta que a livre: começar dela
        # poupa todas as profundidades que não teriam como achar nada. E se a
        # livre já passa do teto, a restrita também passa - e a frase tem de
        # dizer ISSO, e não que o meio é obrigatório (o laço nem rodaria).
        if livre.meios_lances > maximo_de_meios_lances:
            return ProvaQuatro(
                False,
                f"a vitória livre já leva {(livre.meios_lances + 1) // 2} lances, "
                f"acima do teto de {(maximo_de_meios_lances + 1) // 2}",
            )
        arvore = _Arvore(
            quem=quem,
            # A proibição mora no lance da pessoa: a coluna do meio não é opção.
            permitido=lambda antes, depois: self._coluna_do_lance(antes, depois) != meio,
            # E a folha que vale é a vitória dela (a proibição já garantiu o resto).
            folha=lambda fim: self.arbitro.veredito(fim).vencedor == quem,
            perguntas_ate=self.perguntas + perguntas,
            defesa=defesa,
        )
        try:
            for teto in range(livre.meios_lances, maximo_de_meios_lances + 1, 2):
                if self._forca(estado, arvore, teto):
                    lances = (teto + 1) // 2
                    return ProvaQuatro(
                        True, f"vitória sem a coluna {meio} em {lances} lances",
                        {"lances": lances},
                    )
        except _SemPerguntas:
            return ProvaQuatro(
                False,
                f"a busca sem a coluna {meio} passou de {perguntas} "
                "perguntas sem decidir",
            )
        return ProvaQuatro(
            False,
            f"a vitória existe, mas não sem a coluna {meio} em até "
            f"{(maximo_de_meios_lances + 1) // 2} lances",
        )

    def objetivo_forcavel(
        self,
        estado: EstadoQuatro,
        js_chegada: Mapping[str, Any],
        *,
        maximo_de_meios_lances: int = MAXIMO_FORCAVEL,
        perguntas: int = PERGUNTAS_FORCAVEL,
        defesa: str = DEFESA_DO_OBJETIVO,
    ) -> ProvaQuatro:
        """A pessoa CUMPRE o objetivo à força, faça o adversário o que fizer.

        A prova do golpe duplo e da linha de cinco (T124c, item 1 do plano do
        que sobra). A prova "ao alcance" (`golpe_duplo`, `linha_de_cinco`, mais
        abaixo) só diz que o tabuleiro ainda COMPORTA o objetivo; a régua de
        21/10 mostrou que isso não basta: nem o perseguidor no nível do Magno
        alcançou o objetivo nessas posições. Aqui a pergunta é a forte: existe
        um jeito de jogar que termina na vitória DO JEITO PEDIDO contra qualquer
        resposta?

        É a mesma árvore E/OU do "sem o meio", com outra folha: a partida
        terminou e a linha de chegada do desafio vale. ⛔ **A regra da folha não
        é reescrita aqui**: quem mede é `feitos_quatro.medir` e quem julga é
        `avaliar`, os mesmos que julgam a pessoa no app e no servidor.

        ⚠️ **Serve às chegadas que dependem só do TABULEIRO final** (a vitória e
        as linhas que ela fechou): a árvore guarda as respostas por tabuleiro, e
        uma medida que dependesse do caminho (os lances na coluna do meio, as
        ameaças bloqueadas) leria a resposta de outro caminho. Por isso o "sem o
        meio" põe a proibição no LANCE (`permitido`), e não na folha.

        Args:
            estado: a posição publicada (a vez é de quem resolve).
            js_chegada: a linha de chegada do tipo, com os parâmetros (a da
                receita: `RECEITAS[tipo].montar(parametros)`).
            maximo_de_meios_lances: até onde a árvore desce.
            perguntas: quantas buscas a prova pode gastar nesta posição.
            defesa: contra quem a força vale. `DEFESA_DO_OBJETIVO` (o padrão):
                qualquer resposta. `DEFESA_DO_JOGO`: as que o motor daria - a
                da pescaria de 21/10, porque com muitos lances a outra quase
                não acha posição (ver a constante).
        """
        quem = self.arbitro.vez_de(estado)
        livre = self.resultado(estado)
        if livre.vencedor != quem:
            return ProvaQuatro(False, f"sem vitória forçada provada para {quem:+d}")
        if livre.meios_lances > maximo_de_meios_lances:
            return ProvaQuatro(
                False,
                f"a vitória livre já leva {(livre.meios_lances + 1) // 2} lances, "
                f"acima do teto de {(maximo_de_meios_lances + 1) // 2}",
            )
        chegada = LinhaDeChegada.de_dado(js_chegada)
        iniciais = estado.lances

        def cumpre(fim: EstadoQuatro) -> bool:
            # A fita é o que se jogou DEPOIS da posição publicada, dos dois lados.
            fita = fim.lances[len(iniciais):]
            medidas = feitos_quatro.medir(self.arbitro, iniciais, fita, jogador=quem)
            predicados = feitos_quatro.responder_predicados(self.arbitro, iniciais, fita)
            return avaliar(chegada, medidas, predicados=predicados)

        arvore = _Arvore(
            quem=quem,
            permitido=lambda _antes, _depois: True,
            folha=cumpre,
            perguntas_ate=self.perguntas + perguntas,
            defesa=defesa,
        )
        try:
            for teto in range(livre.meios_lances, maximo_de_meios_lances + 1, 2):
                if self._forca(estado, arvore, teto):
                    lances = (teto + 1) // 2
                    return ProvaQuatro(
                        True, f"o objetivo é forçável em {lances} lances",
                        {"lances": lances, "lances_livre": (livre.meios_lances + 1) // 2},
                    )
        except _SemPerguntas:
            return ProvaQuatro(
                False, f"a árvore do objetivo passou de {perguntas} perguntas sem decidir"
            )
        return ProvaQuatro(
            False,
            f"a vitória existe em {(livre.meios_lances + 1) // 2} lances, mas o "
            f"objetivo não é forçável em até {(maximo_de_meios_lances + 1) // 2}",
            {"lances_livre": (livre.meios_lances + 1) // 2},
        )

    def _coluna_do_lance(self, antes: EstadoQuatro, depois: EstadoQuatro) -> int | None:
        """A coluna que o lance ocupou (a pilha que cresceu), sem ler a notação."""
        a = self.arbitro.tabuleiro(antes).colunas
        d = self.arbitro.tabuleiro(depois).colunas
        for indice, (x, y) in enumerate(zip(a, d)):
            if len(y) > len(x):
                return indice + 1
        return None

    def _forca(self, estado: EstadoQuatro, arvore: "_Arvore", restam: int) -> bool:
        """OU: algum lance permitido da pessoa leva à folha em até [restam].

        ⚠️ A resposta é guardada por (tabuleiro, restam): duas ordens de lance que
        chegam ao mesmo tabuleiro fazem a mesma pergunta.
        """
        if restam <= 0:
            return False
        chave = (self._chave(estado), restam)
        if chave not in arvore.visto:
            arvore.visto[chave] = self._forca_agora(estado, arvore, restam)
        return arvore.visto[chave]

    def _forca_agora(self, estado: EstadoQuatro, arvore: "_Arvore", restam: int) -> bool:
        """O corpo de `_forca`, sem a memória."""
        if self.perguntas > arvore.perguntas_ate:
            raise _SemPerguntas
        quem = arvore.quem
        legais = self.arbitro.lances_legais(estado)
        # O melhor lance da busca livre vai na frente: quando ele é permitido,
        # costuma ser o da vitória, e o primeiro que acha a folha encerra o OU.
        melhor = self.resultado(estado).lance
        if melhor in legais:
            legais = [melhor] + [l for l in legais if l != melhor]
        for lance in legais:
            filho = self.arbitro.aplicar(estado, lance)
            if not arvore.permitido(estado, filho):
                continue
            if self.arbitro.veredito(filho).acabou:
                # A partida acabou no lance da pessoa: vale se a folha vale (a
                # vitória do jeito errado acaba a partida e NÃO cumpre).
                if arvore.folha(filho):
                    return True
                continue
            # A poda: toda folha pedida é uma vitória da pessoa; sem a vitória
            # forçada livre, a restrita não existe.
            if self.resultado(filho).vencedor != quem:
                continue
            if self._todas_as_respostas(filho, arvore, restam - 1):
                return True
        return False

    def _todas_as_respostas(self, estado: EstadoQuatro, arvore: "_Arvore", restam: int) -> bool:
        """E: toda resposta do adversário que CONTA ainda deixa a pessoa chegar
        à folha. Quais contam é a defesa da árvore (ver `DEFESA_DO_JOGO`)."""
        if restam <= 0:
            return False
        vivos: list[EstadoQuatro] = []
        for lance in self.arbitro.lances_legais(estado):
            neto = self.arbitro.aplicar(estado, lance)
            veredito = self.arbitro.veredito(neto)
            if veredito.acabou:
                # O adversário venceu ou empatou: este ramo não é da pessoa. Nas
                # duas defesas - é o lance que qualquer motor jogaria.
                if veredito.vencedor != arvore.quem:
                    return False
                continue
            if arvore.defesa == DEFESA_DO_OBJETIVO:
                # Toda resposta conta: a primeira que escapa encerra o E.
                if not self._forca(neto, arvore, restam - 1):
                    return False
            else:
                vivos.append(neto)
        return all(
            self._forca(neto, arvore, restam - 1)
            for neto in self._respostas_do_jogo(vivos, arvore.quem)
        )

    def _respostas_do_jogo(
        self, netos: list[EstadoQuatro], quem: int
    ) -> list[EstadoQuatro]:
        """Das respostas do adversário, as que o MOTOR poderia escolher.

        A que não perde à força (ou que a busca não decidiu) é escolha possível
        do adversário, e conta. Quando todas perdem, o motor escolhe a que adia
        a derrota ao máximo - e contam todas as empatadas nessa distância, porque
        o empate do motor se desfaz por sorteio. Vazio na `DEFESA_DO_OBJETIVO`
        (lá o laço já conferiu cada resposta, e não sobra nenhuma em `netos`).
        """
        resultados = [(neto, self.resultado(neto)) for neto in netos]
        escapam = [neto for neto, r in resultados if r.vencedor != quem]
        if escapam or not resultados:
            return escapam
        mais_longe = max(r.meios_lances for _, r in resultados)
        return [neto for neto, r in resultados if r.meios_lances == mais_longe]

    def virada(self, estado: EstadoQuatro) -> ProvaQuatro:
        """A posição PARECE do adversário, à vista, e a busca prova a da pessoa.

        "Parece" são duas condições, e as duas valem (decisão do dono em
        27/10/2026: *"precisa ficar visualmente claro para o usuário que ele está
        em clara desvantagem"*):

          1. **o adversário tem MAIS AMEAÇAS que a pessoa** - casas vazias onde
             uma peça dele fecharia quatro (`feitos_quatro.casas_de_ameaca`). É
             o que se vê no tabuleiro sem calcular nada;
          2. **a heurística do motor** (o comando `avaliar`, o "à primeira
             vista" que a busca usa quando a visão acaba) dá ao adversário pelo
             menos [LIMIAR_DA_VIRADA]: o peso de uma ameaça na linha certa.

        ⚠️ Até 27/10/2026 bastava a heurística abaixo de zero, e isso não
        filtrava nada: com a vez da pessoa, o adversário tem quase sempre uma
        peça a mais no tabuleiro, e a heurística sai a favor dele por poucos
        pontos (uma peça no meio vale 7). Um desafio publicado com +2 para a
        Cacau, sem ameaça nenhuma dos dois lados, foi o que o dono viu no painel.
        Medido no acervo naquele dia: 3.232 de 5.707 posições passavam no
        critério antigo, e 1.224 passam no novo (antes da busca).

        As duas contas baratas vêm antes da busca, que é a única cara.
        """
        quem = self.arbitro.vez_de(estado)
        tabuleiro = self.arbitro.tabuleiro(estado)
        dimensoes = self.arbitro.regras.dimensoes
        # `-quem` é o adversário: as peças são +1 e -1, e trocar o sinal troca o lado.
        ameacas_dele = len(feitos_quatro.casas_de_ameaca(dimensoes, tabuleiro, -quem))
        ameacas_minhas = len(feitos_quatro.casas_de_ameaca(dimensoes, tabuleiro, quem))
        ameacas = {"ameacas_adversario": ameacas_dele, "ameacas_pessoa": ameacas_minhas}
        if ameacas_dele <= ameacas_minhas:
            return ProvaQuatro(
                False,
                f"o adversário não tem mais ameaças que a pessoa "
                f"({ameacas_dele} contra {ameacas_minhas})",
                ameacas,
            )
        # A heurística vem do ponto de vista do jogador 1; multiplicar por `quem`
        # a põe do ponto de vista da pessoa (negativa = ruim para ela).
        aparencia = quem * self.oraculo.avaliar(
            lances=estado.sequencia, co_modalidade=self.co_modalidade
        )
        if aparencia > -LIMIAR_DA_VIRADA:
            return ProvaQuatro(
                False,
                f"a heurística não dá ao adversário a vantagem de uma ameaça "
                f"({aparencia:+d}, e a virada pede {-LIMIAR_DA_VIRADA:+d} ou menos)",
                {**ameacas, "heuristica": aparencia},
            )
        achado = self.resultado(estado)
        if achado.vencedor != quem:
            return ProvaQuatro(
                False, "a posição parece perdida, mas a vitória forçada não foi provada",
                {**ameacas, "heuristica": aparencia},
            )
        return ProvaQuatro(
            True,
            f"parece do adversário ({aparencia:+d}, {ameacas_dele} ameaça(s) contra "
            f"{ameacas_minhas}) e a pessoa vence à força em "
            f"{(achado.meios_lances + 1) // 2} lances",
            {**ameacas, "heuristica": aparencia, "lances": (achado.meios_lances + 1) // 2},
        )

    # ── As cinco do "objetivo ao alcance" ───────────────────────────────────

    def _nao_perdida(self, estado: EstadoQuatro) -> ProvaQuatro | None:
        """A recusa comum: a posição não pode estar PROVADA perdida para a pessoa.

        Os cinco tipos pedem uma vitória (ou "não perca"); numa posição que a
        busca prova perdida, nem o Magno jogando mal a deixa ao alcance de quem
        joga certo. `None` = segue.
        """
        quem = self.arbitro.vez_de(estado)
        if self.resultado(estado).vencedor == -quem:
            return ProvaQuatro(False, "a posição está provada perdida para a pessoa")
        return None

    def _janelas_abertas(
        self, tabuleiro: TabuleiroQuatro, quem: int, tamanho: int,
        direcoes: Sequence[tuple[int, int]] = feitos_quatro.DIRECOES_DE_LINHA,
    ) -> list[tuple[tuple[int, int], tuple[tuple[int, int], ...]]]:
        """As janelas de [tamanho] casas em linha sem peça do adversário.

        Cada janela vem com a direção e as casas. Uma janela já toda da pessoa
        não conta: seria uma linha feita, e a partida teria acabado.
        """
        dimensoes = self.arbitro.regras.dimensoes
        janelas = []
        for dc, dl in direcoes:
            for coluna in range(1, dimensoes.largura + 1):
                for linha in range(1, dimensoes.altura + 1):
                    casas = tuple(
                        (coluna + dc * k, linha + dl * k) for k in range(tamanho)
                    )
                    if not all(
                        1 <= c <= dimensoes.largura and 1 <= l <= dimensoes.altura
                        for c, l in casas
                    ):
                        continue
                    pecas = [tabuleiro.peca(casa) for casa in casas]
                    if -quem in pecas or 0 not in pecas:
                        continue
                    janelas.append(((dc, dl), casas))
        return janelas

    def vencer_diagonal(self, estado: EstadoQuatro) -> ProvaQuatro:
        """Ainda há uma diagonal inteira sem peça do adversário."""
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        tabuleiro = self.arbitro.tabuleiro(estado)
        abertas = self._janelas_abertas(
            tabuleiro, tabuleiro.vez, self.arbitro.regras.dimensoes.alinhar,
            direcoes=((1, 1), (1, -1)),
        )
        if not abertas:
            return ProvaQuatro(False, "nenhuma diagonal livre do adversário")
        return ProvaQuatro(True, f"{len(abertas)} diagonal(is) livre(s)",
                           {"diagonais": len(abertas)})

    def golpe_duplo(self, estado: EstadoQuatro, linhas: int) -> ProvaQuatro:
        """Há uma casa vazia por onde passam [linhas] janelas livres, em direções
        diferentes - o lugar onde um lance só pode fechar duas linhas."""
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        tabuleiro = self.arbitro.tabuleiro(estado)
        direcoes_por_casa: dict[tuple[int, int], set[tuple[int, int]]] = {}
        for direcao, casas in self._janelas_abertas(
            tabuleiro, tabuleiro.vez, self.arbitro.regras.dimensoes.alinhar
        ):
            for casa in casas:
                if tabuleiro.peca(casa) == 0:
                    direcoes_por_casa.setdefault(casa, set()).add(direcao)
        cruzamentos = sorted(c for c, d in direcoes_por_casa.items() if len(d) >= linhas)
        if not cruzamentos:
            return ProvaQuatro(False, f"nenhuma casa cruza {linhas} linhas livres")
        return ProvaQuatro(True, f"{len(cruzamentos)} casa(s) cruzam {linhas} linhas livres",
                           {"cruzamentos": len(cruzamentos)})

    def linha_de_cinco(self, estado: EstadoQuatro, tamanho: int) -> ProvaQuatro:
        """Ainda há uma janela de [tamanho] casas sem peça do adversário."""
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        tabuleiro = self.arbitro.tabuleiro(estado)
        abertas = self._janelas_abertas(tabuleiro, tabuleiro.vez, tamanho)
        if not abertas:
            return ProvaQuatro(False, f"nenhuma janela de {tamanho} livre do adversário")
        return ProvaQuatro(True, f"{len(abertas)} janela(s) de {tamanho} livres",
                           {"janelas": len(abertas)})

    def encostadas(self, estado: EstadoQuatro, pecas: int) -> ProvaQuatro:
        """O alvo de peças encostadas está acima do que já há, e cabe nos lances
        que restam à pessoa (cada lance encosta no máximo uma peça nova dela)."""
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        dimensoes = self.arbitro.regras.dimensoes
        tabuleiro = self.arbitro.tabuleiro(estado)
        ja = feitos_quatro.pecas_encostadas(dimensoes, tabuleiro, tabuleiro.vez)
        falta = pecas - ja
        if falta <= 0:
            return ProvaQuatro(False, f"já há {ja} encostadas: o alvo {pecas} cumpre sem jogar")
        livres = dimensoes.largura * dimensoes.altura - sum(map(len, tabuleiro.colunas))
        # A pessoa joga primeiro: das casas livres, ela ocupa a metade arredondada
        # para cima. ⚠️ Um lance pode encostar DUAS peças (a nova e uma vizinha
        # que estava sozinha); contar uma por lance é a conta conservadora.
        lances_dela = (livres + 1) // 2
        if falta > lances_dela:
            return ProvaQuatro(False, f"faltam {falta} encostadas e restam {lances_dela} lances")
        return ProvaQuatro(True, f"{ja} encostadas; o alvo {pecas} pede mais {falta}",
                           {"ja": ja, "falta": falta})

    def encoste(self, estado: EstadoQuatro, pecas: int, lances: int) -> ProvaQuatro:
        """O alvo de [pecas] encostadas em [lances] lances pede JUNTAR peças soltas.

        O alvo é `E + M + k` (`editorial.parametros_efetivos`): jogar sempre
        colado dá no máximo uma encostada a mais por lance (a peça nova), e só
        quem junta uma peça SOLTA (sem vizinha da mesma cor) ganha duas de uma
        vez - a nova e a solta, que passa a contar. Então o `k = alvo - E - M`
        exige pelo menos `k` soltas na posição publicada; sem elas, o alvo está
        fora do alcance até de quem joga perfeito. Com `k <= 0` o desafio seria
        "jogue colado", e a geração também recusa (é o defeito que o `k` veio
        evitar: fácil para todos, a escada plana).

        ⚠️ É a conta de cima, e não uma prova de que o alvo é alcançável: o
        adversário pode tapar a casa da junção. Quem diz se é alcançável é o
        gabarito (o perseguidor no nível do Magno), e quem diz se é difícil é a
        régua.
        """
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        dimensoes = self.arbitro.regras.dimensoes
        tabuleiro = self.arbitro.tabuleiro(estado)
        quem = tabuleiro.vez
        ja = feitos_quatro.pecas_encostadas(dimensoes, tabuleiro, quem)
        # As peças da pessoa: as encostadas mais as soltas. A conta das
        # encostadas é a do medidor (`pecas_encostadas`), e a das soltas sai dela.
        minhas = sum(
            1
            for coluna in range(1, dimensoes.largura + 1)
            for linha in range(1, len(tabuleiro.colunas[coluna - 1]) + 1)
            if tabuleiro.peca((coluna, linha)) == quem
        )
        soltas = minhas - ja
        juntar = pecas - ja - lances
        if juntar <= 0:
            return ProvaQuatro(
                False, f"o alvo {pecas} cabe jogando colado ({ja} + {lances} lances)"
            )
        if soltas < juntar:
            return ProvaQuatro(
                False, f"o alvo pede juntar {juntar} peça(s) solta(s), e há {soltas}"
            )
        return ProvaQuatro(
            True, f"{ja} encostadas e {soltas} soltas; o alvo {pecas} pede juntar {juntar}",
            {"ja": ja, "soltas": soltas, "juntar": juntar},
        )

    def figura(self, estado: EstadoQuatro, nome: str, lances: int) -> ProvaQuatro:
        """A figura [nome] nao esta formada, nao se forma num lance, e cabe em [lances].

        A distancia (`figuras_quatro.distancia`) e recalculada aqui, da posicao, e
        nao lida dos parametros: a prova nao confia no numero de quem a chama.
        Recusa a figura sem lugar livre de conflito (ela nunca mais se forma), a
        ja formada ou formavel num lance (a proposta §2, recusa 5), a longe demais
        (a faixa da T147, sondada na T148), e o prazo menor que a distancia (recusa 6).

        ⚠️ Como no Encoste, e a conta de cima, e nao a prova de que a figura e
        alcancavel: quem diz isso e o gabarito, e quem diz se e dificil e a regua.
        """
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        figura = figuras_quatro.FIGURAS_QUATRO[nome]
        quanto = figuras_quatro.distancia(
            figura, self.arbitro.tabuleiro(estado), self.arbitro.regras.dimensoes
        )
        if quanto is None:
            return ProvaQuatro(False, f"a figura {nome} nao cabe sem conflito em lugar nenhum")
        if quanto < figuras_quatro.DISTANCIA_MINIMA_DA_FIGURA:
            return ProvaQuatro(
                False, f"a figura {nome} esta a {quanto} casa(s): ja formada ou formavel num lance"
            )
        if quanto > figuras_quatro.DISTANCIA_MAXIMA_DA_FIGURA:
            return ProvaQuatro(False, f"a figura {nome} esta a {quanto} casas: longe demais")
        if lances < quanto:
            return ProvaQuatro(
                False, f"o prazo de {lances} lances e menor que a distancia {quanto}"
            )
        return ProvaQuatro(
            True, f"a figura {nome} esta a {quanto} casas; o prazo e {lances}",
            {"distancia": quanto},
        )

    def bloquear(
        self, estado: EstadoQuatro, ameacas: int, continuacao: Sequence[str] | None
    ) -> ProvaQuatro:
        """No autoplay a partir da posição, a pessoa bloqueou [ameacas] ameaças.

        A continuação é a partida que o autoplay jogou dali (T117, Magno × Tex):
        é ela que mostra que o tabuleiro gera ameaças a bloquear. A conta é a do
        medidor do desafio (`feitos_quatro.medir`, a medida `ameacas_bloqueadas`),
        e não uma segunda escrita.
        """
        if (recusa := self._nao_perdida(estado)) is not None:
            return recusa
        if not continuacao:
            return ProvaQuatro(False, "sem a continuação do autoplay, não há o que contar")
        medidas = feitos_quatro.medir(self.arbitro, estado.lances, list(continuacao))
        vistas = int(medidas["ameacas_bloqueadas"])
        if vistas < ameacas:
            return ProvaQuatro(
                False, f"o autoplay bloqueou {vistas} ameaça(s), e o alvo é {ameacas}",
                {"ameacas": vistas},
            )
        return ProvaQuatro(True, f"o autoplay bloqueou {vistas} ameaça(s)",
                           {"ameacas": vistas})


#: A prova de cada tipo, pelo `co_tipo_desafio`. Cada entrada recebe o provador,
#: a posição, os parâmetros EFETIVOS do candidato e a continuação do autoplay.
#:
#: ⚠️ As chaves são exatamente os tipos do Quatro (cadeado em
#: `test_provas_quatro.py`): um tipo novo sem prova seria publicado sem que
#: ninguém tivesse perguntado se a posição serve a ele.
PROVAS: dict[
    str,
    Callable[[ProvadorQuatro, EstadoQuatro, Mapping[str, Any], Sequence[str] | None], ProvaQuatro],
] = {
    "quatro_vencer_em_n": lambda p, e, par, _c: p.vencer_em_n(e, par["lances"]),
    "quatro_segurar_magno": lambda p, e, _par, _c: p.segurar_magno(e),
    "quatro_unica_coluna": lambda p, e, _par, _c: p.unica_coluna(e),
    "quatro_vencer_diagonal": lambda p, e, _par, _c: p.vencer_diagonal(e),
    "quatro_golpe_duplo": lambda p, e, par, _c: p.golpe_duplo(e, par["linhas"]),
    "quatro_linha_de_cinco": lambda p, e, par, _c: p.linha_de_cinco(e, par["tamanho"]),
    "quatro_encostadas": lambda p, e, par, _c: p.encostadas(e, par["pecas"]),
    "quatro_encoste": lambda p, e, par, _c: p.encoste(e, par["pecas"], par["lances"]),
    "quatro_figura": lambda p, e, par, _c: p.figura(
        e, par[figuras_quatro.CHAVE_FIGURA], par["lances"]
    ),
    "quatro_sem_o_meio": lambda p, e, _par, _c: p.sem_o_meio(e),
    "quatro_bloquear": lambda p, e, par, c: p.bloquear(e, par["ameacas"], c),
    "quatro_virada": lambda p, e, _par, _c: p.virada(e),
}


def provar(
    co_tipo_desafio: str,
    provador: ProvadorQuatro,
    estado: EstadoQuatro,
    parametros: Mapping[str, Any],
    *,
    continuacao: Sequence[str] | None = None,
) -> ProvaQuatro:
    """A prova do tipo, para a posição.

    Raises:
        KeyError: tipo sem prova. ⚠️ Falha alto: "sem prova" não é "passou".
    """
    if co_tipo_desafio not in PROVAS:
        raise KeyError(
            f"o tipo {co_tipo_desafio!r} não tem prova do Quatro em Linha "
            "(job/provas_quatro.PROVAS)."
        )
    return PROVAS[co_tipo_desafio](provador, estado, parametros, continuacao)
