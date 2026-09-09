"""Os dois empates que dependem do **histórico** da partida — arts. 97b e 98.

Por que um módulo só para isto
------------------------------
Quase toda regra de damas se decide olhando **a posição**: quem tem a vez, onde
estão as peças, que capturas são obrigatórias. Estas duas não. Elas perguntam
*como se chegou aqui*:

- **art. 98** — a mesma posição pela **terceira** vez, com o mesmo lado a jogar,
  é empate. Duas posições idênticas no tabuleiro podem valer coisas diferentes,
  porque uma é a primeira ocorrência e a outra é a terceira.
- **art. 97b** — **20 lances de cada lado** só com movimentos de dama, sem
  captura e sem deslocamento de pedra, é empate. O tabuleiro não guarda esse
  contador em lugar nenhum.

Como nenhuma das duas cabe numa função `avaliar(tabuleiro)`, elas precisam de um
objeto que **acompanhe a partida** — é o `HistoricoDaPartida` daqui.

Quem usa, e por que os dois têm de usar o MESMO código
------------------------------------------------------
Até 2026-07-28 estas regras existiam só dentro da arena (`avaliacao/arena_damas.py`),
como faria um árbitro: o árbitro conhecia a regra, o jogador não. A consequência
prática era feia — **o motor avaliava mal posições que o regulamento já declara
empatadas**. Ele achava que estava ganhando um final que o árbitro ia encerrar
empatado, e por isso recusava trocas favoráveis para "manter a vantagem" que já
não existia.

Agora os dois leem daqui:

| Quem | O que faz com isto |
|---|---|
| `avaliacao/arena_damas.py` (o árbitro) | encerra a partida quando `motivo_de_empate` responde |
| `motor/busca_damas.py` (o jogador) | devolve nota **0** dentro da busca ao ver a regra disparar |

Um único lugar decide, então árbitro e jogador não podem discordar — e a
discordância entre eles é precisamente o tipo de defeito que não dá erro nenhum,
só faz o motor jogar mal.

⚠️ Uma diferença de leitura em relação à base de finais
-------------------------------------------------------
`tablebase/empates_declarados_damas.py` aplica o art. 97b **somente a fatias sem
pedras**. Não é outra leitura do artigo: é o que a base **consegue** fazer. Ela é
indexada por posição, não por histórico, e só numa fatia sem pedras é possível
afirmar que o contador nunca zerou — ali todo lance é de dama por construção.

Aqui existe o histórico de verdade, então vale o texto literal: o que conta é
que os **lances** tenham sido só de dama, sem captura e sem mover pedra. Pedra
parada no tabuleiro não impede o empate. Quando as duas fontes discordam, a mais
restritiva ganha, porque a busca consulta esta antes da base — e é o resultado
certo, já que aqui a informação é maior.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from jogos.jogo_damas.motor.regras_damas import BRASILEIRAS, Lance, Regulamento
from jogos.jogo_damas.motor.tabuleiro_damas import RIO, Cor, Peca, Tabuleiro

# ⚠️ Os números NÃO moram aqui — moram no `Regulamento`, e a razão é um defeito
# real encontrado em 2026-07-28. Enquanto foram constantes deste módulo, o motor
# aplicava a regra brasileira (20 lances) em partida anglo-americana, cujo
# regulamento manda **40** (WCDF 1.27.2). Nenhum teste pegava: as regras de
# empate não mudam a contagem de lances legais, então o `perft` passa igual.
#
# | | brasileiras (art. 97b) | anglo-americanas (WCDF 1.27.2) |
# |---|---|---|
# | lances de cada lado | 20 | **40** |
# | repetições (art. 98 / 1.27.1) | 3 | 3 |

# --- os TRÊS relógios, e por que não é um só --------------------------------
#
# | regra | conta em | quando ANDA | o que ZERA |
# |---|---|---|---|
# | art. 97b / WCDF 1.27.2 | meios-lances | sempre | captura **ou movimento de pedra** |
# | FPD 3.8.b | meios-lances | só em final de ≤4 peças por lado com dama dos dois lados | idem, **e** sair desse final |
# | FMJD 8.5 | meios-lances | dama dos dois lados, 4–7 peças | captura **ou promoção** |
# | FPD 3.8.a (Forçada) | **lances do lado forte** | 3 damas × 1 dama, com o forte no Rio | sair da configuração 3×1 |
#
# Movimento de pedra zera o primeiro e não zera o terceiro; promoção zera o
# terceiro e — como toda promoção vem de um lance de pedra — zera os dois. Eles
# correm juntos e discordam, então são campos separados. Somá-los num só faria a
# regra mais frouxa disparar cedo demais.
#
# O quarto é o mais diferente de todos, e por duas razões: conta **lances de um
# jogador só**, não meios-lances dos dois; e o art. 3.8.b.(4) manda que, enquanto
# ele vale, o relógio dos 20 lances **não valha**. Não é "o mais apertado ganha"
# como nos outros — é substituição.

# As duas peças que, ao se moverem, zeram o contador de progresso.
_PEDRAS = (Peca.PEDRA_BRANCA, Peca.PEDRA_PRETA)


def chave_da_posicao(tabuleiro: Tabuleiro) -> int:
    """A identidade de uma posição para efeito de repetição.

    É o **hash de Zobrist** (`Tabuleiro.hash`): as 32 casas e mais a vez,
    resumidas num número de 64 bits. A vez faz parte da identidade porque o art.
    98 exige "com o mesmo jogador a jogar" — o mesmo desenho de peças com as
    brancas a jogar e com as pretas a jogar são posições diferentes, e tratá-las
    como iguais declararia empates que não existem.

    É a mesma chave que a tabela de transposição da busca usa — e de propósito:
    duas noções de "mesma posição" no mesmo motor acabariam divergindo.

    ⚠️ **Mudou em 03/09/2026.** Antes devolvia ``(tuple(casas), vez)``, que não
    tem colisão: duas posições diferentes nunca eram confundidas. O hash tem
    colisão, com chance de uma em 2⁶⁴ — e passou a ser usado assim mesmo porque é
    o que o motor do aparelho faz. Um motor de referência que declara empates por
    um critério que o app não tem responde por um aparelho que não existe.

    A função continua existindo, em vez de o código chamar ``tabuleiro.hash``
    direto, porque ela é o **nome** desta decisão: quem procurar "como este
    projeto decide que duas posições são a mesma" chega aqui, e lê o porquê.
    """
    return tabuleiro.hash


def zera_o_contador(tabuleiro_antes: Tabuleiro, lance: Lance) -> bool:
    """Este lance interrompe a sequência do art. 97b?

    Interrompe se for **captura** ou se a peça que se moveu for **pedra**. Repare
    que a consulta é ao tabuleiro **antes** do lance: depois de aplicado, a peça
    já saiu da casa de origem, e uma pedra que coroou nem pedra é mais.
    """
    return lance.e_captura or tabuleiro_antes.ler(lance.origem) in _PEDRAS


def muda_o_equilibrio(lance: Lance) -> bool:
    """Este lance interrompe a sequência da FMJD 8.5?

    O texto define equilíbrio pelo que **não** aconteceu: *"there was no capture
    and man did not become a king"*. Então só duas coisas o mudam — captura e
    promoção. Uma pedra que anda sem coroar **não** zera este contador, e é aí
    que ele difere do art. 97b.
    """
    return lance.e_captura or lance.vira_dama


def tres_damas_contra_uma(tabuleiro: Tabuleiro) -> bool:
    """A correlação de forças da FMJD 8.3: 3 damas **ou mais** × 1 dama sozinha.

    Sem pedras de nenhum dos lados — o texto fala em *kings* dos dois lados, e
    uma pedra em jogo tira a posição desta correlação.

    ⚠️ Diferente do art. 100 do CBJD, esta regra **não** exige que a dama
    solitária esteja na grande diagonal. As duas coexistem: o art. 100 dá 5
    lances quando a dama está lá, e esta dá 15 em qualquer caso. A mais apertada
    é que decide.
    """
    contagem = tabuleiro.contar()
    if contagem[Peca.PEDRA_BRANCA] or contagem[Peca.PEDRA_PRETA]:
        return False

    damas_brancas = contagem[Peca.DAMA_BRANCA]
    damas_pretas = contagem[Peca.DAMA_PRETA]
    return ((damas_brancas >= 3 and damas_pretas == 1)
            or (damas_pretas >= 3 and damas_brancas == 1))


def _contagem_por_cor(tabuleiro: Tabuleiro) -> dict[Cor, tuple[int, int]]:
    """Quantas peças e quantas damas cada lado tem: `{cor: (total, damas)}`.

    Existe para não repetir três vezes a mesma soma nas funções da FPD abaixo —
    e porque somar pedra com dama na ordem errada é o tipo de engano que passa
    despercebido numa expressão longa.
    """
    contagem = tabuleiro.contar()
    return {
        Cor.BRANCAS: (
            contagem[Peca.PEDRA_BRANCA] + contagem[Peca.DAMA_BRANCA],
            contagem[Peca.DAMA_BRANCA],
        ),
        Cor.PRETAS: (
            contagem[Peca.PEDRA_PRETA] + contagem[Peca.DAMA_PRETA],
            contagem[Peca.DAMA_PRETA],
        ),
    }


def contador_de_progresso_esta_ligado(
    tabuleiro: Tabuleiro, regulamento: Regulamento
) -> bool:
    """A posição satisfaz o **gatilho** da contagem de lances sem progresso?

    Nas brasileiras e nas anglo-americanas não há gatilho: o contador anda desde
    o primeiro lance, e esta função responde sempre `True`.

    Nas portuguesas há (FPD 3.8.b.1), e é o que faltava implementar até
    2026-07-29: a contagem de 20 lances *"begins immediately"* — mas só quando a
    posição tem **no máximo 4 peças de cada lado**, com **pelo menos uma dama de
    cada lado**. Antes disso ela não corre.

    A diferença é real, não formal. Numa posição de 8 peças por lado em que só se
    movem damas, o regulamento brasileiro empata em 20 lances e o português não
    empata nunca — ali ainda não é final para ele.
    """
    maximo = regulamento.maximo_de_pecas_por_lado_para_contar
    if maximo is None and not regulamento.exige_dama_dos_dois_lados_para_contar:
        return True

    por_cor = _contagem_por_cor(tabuleiro)
    for total, damas in por_cor.values():
        if maximo is not None and total > maximo:
            return False
        if regulamento.exige_dama_dos_dois_lados_para_contar and damas == 0:
            return False
    return True


def lado_forte_da_forcada(
    tabuleiro: Tabuleiro, regulamento: Regulamento
) -> Cor | None:
    """Quem é o lado forte da **Forçada** (FPD 3.8.a), ou `None` se não é o caso.

    A configuração é fechada: **sem pedras**, um lado com exatamente
    `damas_da_forcada` damas (três, no texto português) e o outro com exatamente
    uma. Qualquer pedra no tabuleiro tira a posição desta correlação — o artigo
    fala de *kings* dos dois lados.

    Devolver a **cor** em vez de um booleano é o que permite contar só os lances
    de quem tem de ganhar, que é a leitura adotada dos "12 moves" (ver o campo
    `lances_da_forcada` do `Regulamento`).

    ⚠️ Repare que esta função **não** olha o Rio. Ela responde "estamos na
    configuração da Forçada?", e é essa pergunta que a FPD 3.8.b.(4) usa para
    desligar a regra dos 20 lances — inclusive antes de o Rio ser ocupado, caso
    que o próprio 3.8.a.(2) descreve. Quem olha o Rio é `forcada_em_curso`.
    """
    if regulamento.lances_da_forcada is None:
        return None

    contagem = tabuleiro.contar()
    if contagem[Peca.PEDRA_BRANCA] or contagem[Peca.PEDRA_PRETA]:
        return None

    damas_brancas = contagem[Peca.DAMA_BRANCA]
    damas_pretas = contagem[Peca.DAMA_PRETA]
    if damas_brancas == regulamento.damas_da_forcada and damas_pretas == 1:
        return Cor.BRANCAS
    if damas_pretas == regulamento.damas_da_forcada and damas_brancas == 1:
        return Cor.PRETAS
    return None


def forcada_em_curso(
    tabuleiro: Tabuleiro, regulamento: Regulamento
) -> Cor | None:
    """A Forçada já **começou a contar** aqui? Devolve o lado forte, ou `None`.

    É a configuração de `lado_forte_da_forcada` **mais** a ocupação do Rio pelo
    lado forte — *"3 kings controlling the River"* (FPD 3.8.a). Enquanto o forte
    não puser uma dama na grande diagonal, o relógio dos 12 lances não anda, e o
    lance que a põe lá *"is not counted among the 12 moves"*.

    Por que "ocupar" é ter uma dama numa casa do Rio, e não outra coisa: é o que
    o 3.8.a.(2) diz ao descrever o caso oposto — *"3 kings **without occupying**
    the River"* e o adversário *"also not occupying that line"*. Ocupar uma linha
    é estar nela.
    """
    forte = lado_forte_da_forcada(tabuleiro, regulamento)
    if forte is None:
        return None

    damas_do_forte = (
        Peca.DAMA_BRANCA if forte is Cor.BRANCAS else Peca.DAMA_PRETA
    )
    for casa in RIO:
        if tabuleiro.ler(casa) == damas_do_forte:
            return forte
    return None


def limite_de_equilibrio_parado(
    tabuleiro: Tabuleiro, regulamento: Regulamento
) -> int | None:
    """Quantos **meios-lances** a FMJD 8.5 dá nesta posição. `None` se não vale.

    Duas condições, e as duas vêm do texto:

    1. *"both players having kings"* — cada lado tem ao menos uma dama;
    2. o total de peças cai numa das faixas declaradas pelo regulamento (4–5
       peças → 30 lances; 6–7 → 60).

    Fora disso a regra não se aplica, e devolver `None` deixa isso explícito em
    vez de escolher um limite por omissão.
    """
    if not regulamento.lances_equilibrio_parado:
        return None

    contagem = tabuleiro.contar()
    if not contagem[Peca.DAMA_BRANCA] or not contagem[Peca.DAMA_PRETA]:
        return None

    total = (
        contagem[Peca.PEDRA_BRANCA] + contagem[Peca.DAMA_BRANCA]
        + contagem[Peca.PEDRA_PRETA] + contagem[Peca.DAMA_PRETA]
    )
    for minimo, maximo, lances in regulamento.lances_equilibrio_parado:
        if minimo <= total <= maximo:
            return 2 * lances
    return None


@dataclass
class HistoricoDaPartida:
    """O que a partida acumulou e que a posição sozinha não conta.

    São só dois números — mas são os dois que faltavam para o motor conhecer o
    fim da partida tão bem quanto o árbitro.

    Attributes:
        repeticoes: quantas vezes cada posição já ocorreu, **incluindo a atual**.
            Um `Counter` em vez de uma lista porque a pergunta que se faz é
            sempre "quantas vezes esta?", nunca "qual foi a quinta?".
        meios_lances_sem_progresso: há quantos meios-lances só se movem damas,
            sem captura e sem mexer pedra.
    """

    repeticoes: Counter = field(default_factory=Counter)
    meios_lances_sem_progresso: int = 0
    meios_lances_sem_mudar_o_equilibrio: int = 0
    """O segundo relógio, o da FMJD 8.5. Zera com captura ou promoção — **não**
    com movimento de pedra. Ver o quadro no topo do módulo."""

    lances_de_forcada: int = 0
    """O terceiro relógio, o da **Forçada** portuguesa (FPD 3.8.a).

    Conta em **lances do lado forte**, não em meios-lances — é a única das três
    contagens que não é "de cada lado" no texto, e misturar as unidades faria a
    regra disparar com o dobro ou a metade do prazo. Ver o campo
    `lances_da_forcada` do `Regulamento` para as duas leituras assumidas.

    Começa a andar no lance **seguinte** ao que ocupa o Rio, e não volta a zero
    enquanto a configuração de três damas contra uma durar."""

    regulamento: Regulamento = BRASILEIRAS
    """De qual regulamento saem os limites. O padrão é o brasileiro porque é o do
    primeiro jogo a entrar na loja — mas passar o certo **não é opcional**: nas
    anglo-americanas o limite de progresso é o dobro."""

    @classmethod
    def desde(cls, posicao_inicial: Tabuleiro,
              regulamento: Regulamento = BRASILEIRAS) -> "HistoricoDaPartida":
        """Um histórico começando numa posição, que já conta como ocorrida uma vez.

        Esquecer de contar a posição inicial faria o art. 98 precisar de
        **quatro** ocorrências para disparar — um erro de um, silencioso, que só
        apareceria como "o motor às vezes não vê o empate".
        """
        historico = cls(regulamento=regulamento)
        historico.repeticoes[chave_da_posicao(posicao_inicial)] += 1
        return historico

    def registrar(
        self, antes: Tabuleiro, lance: Lance, depois: Tabuleiro
    ) -> None:
        """Anota um lance jogado de verdade na partida.

        Recebe as duas posições porque cada uma responde a uma das regras: a de
        **antes** diz se o contador do art. 97b zera (era pedra que se moveu?), e
        a de **depois** é a que passa a contar para o art. 98.
        """
        if zera_o_contador(antes, lance):
            self.meios_lances_sem_progresso = 0
        else:
            self.meios_lances_sem_progresso += 1

        # FPD 3.8.b.(1): fora do gatilho o contador não anda **nem guarda o que
        # já andou**. A contagem "begins immediately" quando a posição de final
        # surge — logo, some quando ela deixa de existir.
        if not contador_de_progresso_esta_ligado(depois, self.regulamento):
            self.meios_lances_sem_progresso = 0

        if muda_o_equilibrio(lance):
            self.meios_lances_sem_mudar_o_equilibrio = 0
        else:
            self.meios_lances_sem_mudar_o_equilibrio += 1

        self._registrar_a_forcada(antes, depois)

        self.repeticoes[chave_da_posicao(depois)] += 1

    def _registrar_a_forcada(self, antes: Tabuleiro, depois: Tabuleiro) -> None:
        """O relógio dos 12 lances da Forçada (FPD 3.8.a), só para as portuguesas.

        Três decisões estão nestas poucas linhas, e cada uma vem de uma frase do
        artigo:

        1. **Conta-se pelo tabuleiro de ANTES.** O lance que ocupa o Rio não
           entra na conta — e em `antes` o Rio ainda não estava ocupado, então
           `forcada_em_curso` responde `None` e nada é somado. O lance seguinte
           já vê o Rio ocupado nas duas posições e conta 1.
        2. **Só os lances do lado forte contam** (`antes.vez is forte`). É a
           leitura de "12 moves" sem o "for each color" que o outro artigo usa.
        3. **Sair da configuração zera.** Se `depois` não é mais três damas
           contra uma — porque houve captura, ou porque a dama solitária virou
           duas por algum caminho —, a Forçada acabou e o relógio some. Note que
           isto olha a *configuração*, não a ocupação do Rio: sair do Rio **não**
           zera, senão bastaria sair e voltar para ganhar mais 12 lances.
        """
        if self.regulamento.lances_da_forcada is None:
            return

        if lado_forte_da_forcada(depois, self.regulamento) is None:
            self.lances_de_forcada = 0
            return

        forte = forcada_em_curso(antes, self.regulamento)
        if forte is not None and antes.vez is forte:
            self.lances_de_forcada += 1

    def ocorrencias(self, chave: int) -> int:
        """Quantas vezes esta posição já apareceu na partida."""
        return self.repeticoes.get(chave, 0)

    def motivo_de_empate(self, tabuleiro: Tabuleiro) -> str | None:
        """O texto do artigo que encerra a partida aqui, ou `None` se nenhum.

        ⚠️ **Os textos são SEM ACENTUAÇÃO, e não se corrige isso aqui.** Eles
        têm de ser byte a byte os do motor em Dart — que é quem os produz no
        aparelho — e lá estão sem acento. Três deles ("solitária", "Forçada",
        "promoção") tinham acento neste arquivo até 03/09/2026, enquanto
        "posicao", logo abaixo, já não tinha: o Python estava inconsistente
        consigo mesmo, e ninguém notou porque nada comparava os dois lados. Hoje
        `testes/test_paridade_empates_damas.py` compara.

        ⚠️ **Este texto chega à tela do jogador**, cru, como subtítulo da tela de
        resultado (`resultado_damas_overlay.dart`, `_subtitulo`) — os irmãos dele
        naquele `switch` vêm todos do `l10n`, e este não. Logo, hoje o app mostra
        português sem acento a quem joga em inglês ou espanhol. **Isso é defeito
        do app, não deste módulo**, e o conserto é de lá: trocar o texto por uma
        chave de i18n. Enquanto não for feito, tirar o acento daqui é o que
        mantém os dois motores dizendo a mesma coisa; pôr o acento de volta só
        acrescentaria uma terceira grafia.

        Devolver **texto** e não um booleano é decisão de rastreabilidade: o
        motivo vai para o PDN da partida, e "empatou" sem dizer por qual artigo é
        exatamente o registro que não deixa auditar depois.
        """
        # O nome do artigo muda com a família, e isso não é preciosismo: o motivo
        # vai para o PDN, e citar o artigo brasileiro numa partida anglo-americana
        # é registro errado num arquivo que outro programa vai ler.
        #
        # Até 2026-07-29 a escolha era um `if identificador == "brasileira"`, o
        # que jogava toda modalidade nova no rótulo do WCDF — a Damas de Casa
        # teria saído citando o regulamento inglês. Agora cada regulamento
        # declara a própria citação.
        if self.ocorrencias(chave_da_posicao(tabuleiro)) >= self.regulamento.repeticoes_para_empate:
            artigo = self.regulamento.artigo_da_repeticao
            return (
                f"posicao repetida {self.regulamento.repeticoes_para_empate} "
                f"vezes ({artigo})"
            )
        # FMJD 8.3 vem ANTES do art. 97b: na correlação de três damas contra uma
        # ela é mais apertada (15 lances contra 20), e a mais apertada decide.
        limite_da_correlacao = self.regulamento.lances_tres_damas_contra_uma
        if (limite_da_correlacao is not None
                and self.meios_lances_sem_progresso >= 2 * limite_da_correlacao
                and tres_damas_contra_uma(tabuleiro)):
            return (
                f"{limite_da_correlacao} lances sem capturar a dama solitaria "
                f"(FMJD 8.3)"
            )

        # FPD 3.8.a — a Forçada. Vem antes da regra dos lances sem progresso, e
        # não por ser mais apertada: por **excluí-la**. O art. 3.8.b.(4) diz que
        # "the 20-move rule does not apply to the Forçada", então na configuração
        # de três damas contra uma o único relógio que vale é este.
        if lado_forte_da_forcada(tabuleiro, self.regulamento) is not None:
            limite = self.regulamento.lances_da_forcada
            assert limite is not None, (
                "lado_forte_da_forcada só responde com a regra ligada"
            )
            if self.lances_de_forcada >= limite:
                return (
                    f"{limite} lances sem liquidar a dama solitaria na Forcada "
                    f"({self.regulamento.artigo_da_forcada})"
                )
            return None

        if (self.meios_lances_sem_progresso
                >= self.regulamento.meios_lances_sem_progresso_para_empate):
            artigo = self.regulamento.artigo_dos_lances_sem_progresso
            return (
                f"{self.regulamento.lances_sem_progresso_para_empate} lances de "
                f"cada lado sem progresso ({artigo})"
            )

        # FMJD 8.5 por último: é a mais frouxa em número, e roda no outro
        # relógio — o que só zera com captura ou promoção.
        limite_do_equilibrio = limite_de_equilibrio_parado(tabuleiro, self.regulamento)
        if (limite_do_equilibrio is not None
                and self.meios_lances_sem_mudar_o_equilibrio >= limite_do_equilibrio):
            return (
                f"{limite_do_equilibrio // 2} lances sem captura nem promocao "
                f"(FMJD 8.5)"
            )

        return None
