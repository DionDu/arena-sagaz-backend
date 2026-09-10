"""A LINHA DE CHEGADA: como um desafio se conclui (RF-DES-191, T028).

═══════════════════════════════════════════════════════════════════════════
UMA FORMA SO, E ELA E UMA CONJUNCAO DE CLAUSULAS
═══════════════════════════════════════════════════════════════════════════

    {
      "versao": 1,
      "janela": { "tipo": "turnos_do_jogador", "n": 2 },
      "clausulas": [
        { "tipo": "medida", "chave": "caixas_fechadas",
          "comparador": "maior_ou_igual", "valor": 4 }
      ]
    }

Le-se: *dentro dos proximos 2 turnos do jogador, a medida `caixas_fechadas`
precisa chegar a 4 ou mais*. Havendo mais de uma clausula, **todas** precisam
valer — e sempre um "E", nunca um "ou".

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE FICA DE FORA, E POR QUE ISSO E A DECISAO CENTRAL DESTE ARQUIVO
═══════════════════════════════════════════════════════════════════════════

Ficam de fora, **de proposito** (RF-DES-192):

    ⛔ `OU` e `NAO` aninhados
    ⛔ aritmetica entre chaves
    ⛔ chave livre
    ⛔ expressao avaliada em tempo de execucao

⚠️ **E a fronteira entre publicar DADO e publicar CODIGO no aparelho dos
outros.** Um desafio viaja do servidor para milhoes de aparelhos sem passar por
revisao de loja; se a linha de chegada fosse uma expressao, publicar um desafio
seria publicar codigo — e um erro de digitacao viraria um aplicativo travado no
aparelho de alguem, sem caminho de volta.

⚠️ **Negar uma clausula isolada NAO e aninhar um `NAO`.** `diferente` e
`fora_de` sao folhas: cada uma tem um numero fixo de casos, e cada caso tem
teste. Um `NAO` sobre uma subarvore seria um interpretador — e um interpretador e
exatamente o que nao pode viajar como dado.

⚠️ **Os tres vocabularios sao fechados**, e um valor fora deles e recusado com
`ChegadaInvalida`. ⛔ Nunca "ignore o que nao entender": um comparador
desconhecido tratado como `maior_ou_igual` julgaria errado em silencio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

# ═══════════════════════════════════════════════════════════════════════════
# Os tres vocabularios fechados
# ═══════════════════════════════════════════════════════════════════════════

#: Sobre que pedaco da partida a medida e feita.
#:
#: `partida`               — a fita inteira, do primeiro lance ao ultimo
#: `lances_do_jogador`     — os N primeiros LANCES do jogador
#: `turnos_do_jogador`     — os N primeiros TURNOS do jogador
#: `turnos_do_adversario`  — os N primeiros turnos do adversario
#:
#: ⚠️ **Lance e turno nao sao a mesma coisa**, e a diferenca e do Pontinhos:
#: quem fecha uma caixa joga de novo. Quatro caixas fechadas em quatro lances
#: consecutivos sao **um** turno. Um desafio de "2 turnos" que fosse medido em
#: lances daria 2 onde ha 4 — e o objetivo mudaria de dificuldade sem que
#: ninguem tivesse mexido nele.
JANELAS = frozenset(
    {"partida", "lances_do_jogador", "turnos_do_jogador", "turnos_do_adversario"}
)

#: Como o valor medido e comparado com o valor do desafio.
COMPARADORES = frozenset(
    {"maior_ou_igual", "menor_ou_igual", "igual", "diferente", "em", "fora_de"}
)

#: O que a clausula pergunta.
#:
#: `medida`    — compara uma chave do catalogo de feitos com um numero
#: `predicado` — uma pergunta de sim ou nao sobre a posicao, respondida por uma
#:               funcao **nomeada e compilada** dentro do aplicativo e do job
TIPOS_DE_CLAUSULA = frozenset({"medida", "predicado"})

#: A versao de formato que este avaliador entende.
#:
#: ⚠️ Formato desconhecido e **recusa**, nunca "tenta assim mesmo": um desafio
#: escrito num formato futuro julgado por um avaliador antigo daria um veredito
#: que ninguem consegue explicar depois.
VERSAO_SUPORTADA = 1


class ChegadaInvalida(ValueError):
    """A linha de chegada nao esta no formato — o desafio nao e julgavel.

    ⚠️ **Nao confundir com "nao cumpriu".** Isto e defeito do DADO: o desafio nao
    deveria ter sido publicado. Quem recebe esta excecao no job descarta o
    candidato; quem a recebe na auditoria marca a linha para investigacao.
    """


# ═══════════════════════════════════════════════════════════════════════════
# As pecas, ja validadas
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Janela:
    """Sobre que pedaco da partida medir.

    Atributos:
        tipo: um dos [JANELAS].
        n: quantos lances ou turnos. `None` quando o tipo e `partida`.
    """

    tipo: str
    n: int | None = None

    @classmethod
    def de_dado(cls, dado: Mapping[str, Any]) -> "Janela":
        """Le e valida a janela vinda do JSON."""
        tipo = dado.get("tipo")
        if tipo not in JANELAS:
            raise ChegadaInvalida(
                f"janela {tipo!r} nao existe. As quatro sao: {sorted(JANELAS)}"
            )
        n = dado.get("n")
        if tipo == "partida":
            # `n` numa janela `partida` seria um numero que ninguem usa — e um
            # numero ignorado e a semente de uma discussao futura sobre por que
            # "nao esta funcionando".
            if n is not None:
                raise ChegadaInvalida("a janela `partida` nao aceita `n`")
        else:
            if not isinstance(n, int) or isinstance(n, bool) or n < 1:
                raise ChegadaInvalida(
                    f"a janela {tipo!r} exige `n` inteiro >= 1; veio {n!r}"
                )
        return cls(tipo=tipo, n=n)


@dataclass(frozen=True, slots=True)
class Clausula:
    """Uma pergunta unica, com resposta comparavel.

    Atributos:
        tipo: `medida` ou `predicado`.
        chave: a chave do catalogo de feitos, ou o nome do predicado.
        comparador: um dos [COMPARADORES].
        valor: o alvo. Numero nas medidas; tambem aceita `bool` e listas, para
            `igual`/`diferente` de predicado e para `em`/`fora_de`.
    """

    tipo: str
    chave: str
    comparador: str
    valor: Any

    @classmethod
    def de_dado(cls, dado: Mapping[str, Any]) -> "Clausula":
        """Le e valida uma clausula vinda do JSON."""
        tipo = dado.get("tipo")
        if tipo not in TIPOS_DE_CLAUSULA:
            raise ChegadaInvalida(
                f"clausula de tipo {tipo!r}; os dois sao: {sorted(TIPOS_DE_CLAUSULA)}"
            )
        comparador = dado.get("comparador")
        if comparador not in COMPARADORES:
            raise ChegadaInvalida(
                f"comparador {comparador!r} nao existe. "
                f"Os seis sao: {sorted(COMPARADORES)}"
            )
        chave = dado.get("chave")
        if not isinstance(chave, str) or not chave:
            raise ChegadaInvalida(f"clausula sem chave: {dado!r}")
        if "valor" not in dado:
            raise ChegadaInvalida(f"clausula sem valor: {dado!r}")

        valor = dado["valor"]
        # `em` e `fora_de` comparam com um CONJUNTO; os outros, com um escalar.
        # Trocar um pelo outro daria um resultado silenciosamente errado — por
        # exemplo, `igual` contra uma lista nunca seria verdadeiro.
        if comparador in {"em", "fora_de"}:
            if not isinstance(valor, (list, tuple)) or not valor:
                raise ChegadaInvalida(
                    f"o comparador {comparador!r} exige uma lista nao vazia; "
                    f"veio {valor!r}"
                )
        elif isinstance(valor, (list, tuple, dict)):
            raise ChegadaInvalida(
                f"o comparador {comparador!r} compara com um valor unico; "
                f"veio {valor!r}"
            )
        return cls(tipo=tipo, chave=chave, comparador=comparador, valor=valor)


@dataclass(frozen=True, slots=True)
class LinhaDeChegada:
    """A conjuncao inteira, ja validada.

    ⚠️ **Validar na construcao, e nao na avaliacao**, e decisao: assim um desafio
    malformado e recusado uma vez, na geracao, e nao a cada julgamento — e a
    mensagem de erro chega a quem pode consertar (o job), nao a quem esta jogando.
    """

    janela: Janela
    clausulas: tuple[Clausula, ...]

    @classmethod
    def de_dado(cls, dado: Mapping[str, Any]) -> "LinhaDeChegada":
        """Le `js_chegada` do banco ou de um vetor de verificacao."""
        if not isinstance(dado, Mapping):
            raise ChegadaInvalida(f"js_chegada precisa ser um objeto; veio {type(dado)}")

        versao = dado.get("versao")
        if versao != VERSAO_SUPORTADA:
            raise ChegadaInvalida(
                f"js_chegada versao {versao!r}; este avaliador entende "
                f"{VERSAO_SUPORTADA}. ⛔ Formato desconhecido e recusa, nunca "
                "'tenta assim mesmo'."
            )

        if "janela" not in dado:
            raise ChegadaInvalida("js_chegada sem janela")
        clausulas = dado.get("clausulas")
        if not isinstance(clausulas, Sequence) or isinstance(clausulas, (str, bytes)):
            raise ChegadaInvalida("js_chegada.clausulas precisa ser uma lista")
        if not clausulas:
            # Zero clausulas seria um desafio que qualquer um cumpre sem jogar —
            # o "todas valem" de um conjunto vazio e verdadeiro.
            raise ChegadaInvalida("js_chegada sem clausula nenhuma")

        return cls(
            janela=Janela.de_dado(dado["janela"]),
            clausulas=tuple(Clausula.de_dado(c) for c in clausulas),
        )

    @property
    def chaves_de_medida(self) -> tuple[str, ...]:
        """As chaves do catalogo que esta linha de chegada consulta.

        E o que o medidor precisa calcular, e o que o job confere contra
        `tb902_catalogo_feito` antes de publicar: chave que nao existe produz um
        desafio impossivel de cumprir, sem erro nenhum.
        """
        return tuple(c.chave for c in self.clausulas if c.tipo == "medida")

    @property
    def predicados(self) -> tuple[str, ...]:
        """Os predicados que esta linha de chegada consulta."""
        return tuple(c.chave for c in self.clausulas if c.tipo == "predicado")


# ═══════════════════════════════════════════════════════════════════════════
# A comparacao
# ═══════════════════════════════════════════════════════════════════════════

# Um dicionario de funcoes, e nao uma cadeia de `if`: acrescentar um comparador
# passa a ser acrescentar uma linha, e o `KeyError` que falta um deles e
# impossivel — a validacao da clausula ja recusou o desconhecido.
_COMPARACOES: dict[str, Callable[[Any, Any], bool]] = {
    "maior_ou_igual": lambda medido, alvo: medido >= alvo,
    "menor_ou_igual": lambda medido, alvo: medido <= alvo,
    "igual": lambda medido, alvo: medido == alvo,
    "diferente": lambda medido, alvo: medido != alvo,
    "em": lambda medido, alvo: medido in alvo,
    "fora_de": lambda medido, alvo: medido not in alvo,
}


def comparar(medido: Any, comparador: str, alvo: Any) -> bool:
    """Aplica um dos seis comparadores.

    ⚠️ **`bool` e `int` em Python:** `True == 1` e verdadeiro, e isso e util
    aqui — um predicado que devolve `True` casa com `valor: true` e tambem com
    `valor: 1`. O que NAO se aceita e comparar texto com numero, e por isso os
    tipos sao conferidos antes.
    """
    if comparador not in _COMPARACOES:
        raise ChegadaInvalida(f"comparador {comparador!r} nao existe")

    if comparador in {"em", "fora_de"}:
        return _COMPARACOES[comparador](medido, alvo)

    # Ordenacao entre tipos incompativeis levanta `TypeError` em Python, o que
    # viraria um 500 sem explicacao. Aqui vira `ChegadaInvalida`, que diz o que
    # aconteceu e onde.
    if comparador in {"maior_ou_igual", "menor_ou_igual"} and not isinstance(
        medido, (int, float)
    ):
        raise ChegadaInvalida(
            f"{comparador!r} exige numero; a medida veio como {type(medido).__name__}"
        )
    return _COMPARACOES[comparador](medido, alvo)


def avaliar(
    chegada: LinhaDeChegada,
    medidas: Mapping[str, Any],
    predicados: Mapping[str, Any] | None = None,
) -> bool:
    """Todas as clausulas valem?

    Args:
        chegada: a linha de chegada ja validada.
        medidas: as chaves do catalogo medidas na janela — o que o medidor por
            fita produziu.
        predicados: as respostas dos predicados, quando houver.

    Returns:
        `True` so quando **todas** as clausulas valem. E sempre uma conjuncao.

    Raises:
        ChegadaInvalida: se uma chave consultada nao foi medida.

    ⚠️ **Chave ausente e erro, nunca `False`.** Tratar "nao medi" como "nao
    cumpriu" faria um medidor com defeito parecer uma pessoa que nao conseguiu —
    e o defeito ficaria escondido atras de milhares de tentativas fracassadas.
    """
    respostas = dict(predicados or {})

    for clausula in chegada.clausulas:
        if clausula.tipo == "medida":
            if clausula.chave not in medidas:
                raise ChegadaInvalida(
                    f"a clausula consulta a medida {clausula.chave!r}, que nao foi "
                    f"medida. Medidas disponiveis: {sorted(medidas)}"
                )
            medido = medidas[clausula.chave]
        else:
            if clausula.chave not in respostas:
                raise ChegadaInvalida(
                    f"o predicado {clausula.chave!r} nao foi respondido. "
                    "⚠️ Predicado desconhecido nao se ignora: ele e codigo, e um "
                    "aplicativo que nao o conhece cai na tela de atualizar."
                )
            medido = respostas[clausula.chave]

        if not comparar(medido, clausula.comparador, clausula.valor):
            return False

    return True


# ═══════════════════════════════════════════════════════════════════════════
# T030 — `ic_chegada_encerra_partida` e DERIVADO, nao digitado
# ═══════════════════════════════════════════════════════════════════════════


def chegada_encerra_partida(
    chegada: LinhaDeChegada,
    *,
    total_de_unidades: int | None = None,
) -> bool:
    """A chegada so pode acontecer na posicao FINAL do jogo?

    Vale `True` quando as clausulas so podem ser satisfeitas com a partida
    acabada — *"vença a partir daqui"*. Vale `False` quando a chegada cai antes —
    *"feche 4 caixas em 2 turnos"* deixa 8 caixas em aberto.

    Args:
        chegada: a linha de chegada.
        total_de_unidades: quantas unidades daquela medida existem no tabuleiro
            inteiro (no Pontinhos pequeno, 12 caixas). Quando informado, uma
            clausula que exija o total tambem encerra a partida.

    ⚠️ **Ninguem digita este valor** (RF-DES-194), e a razao esta no caso de
    prova: *"chegue a 7x3"* num tabuleiro de 12 caixas nao encerra a partida —
    7 + 3 = 10, e sobram 2 caixas. Digitado a mao, esse `TRUE` erraria calado no
    dia em que o tabuleiro mudasse de tamanho, e a tela pararia a partida de
    quem quisesse continuar (RF-DES-213).

    ⚠️ **A pergunta e "SO na posicao final", nao "pode acontecer no fim".** Fechar
    4 caixas tambem pode acontecer no ultimo lance; o que decide e se existe
    alguma forma de cumprir **antes**.
    """
    # Uma janela limitada nunca chega ao fim do jogo por construcao: ela fecha
    # depois de N lances ou turnos, e o jogo continua.
    if chegada.janela.tipo != "partida":
        return False

    for clausula in chegada.clausulas:
        # `vitoria` e `empate` sao marcos que so existem com a partida terminada.
        # Sao os unicos casos em que a resposta e `True` sem depender de tamanho
        # de tabuleiro — e sao exatamente os desafios "vença a partir daqui".
        if clausula.tipo == "medida" and clausula.chave in {"vitoria", "empate"}:
            return True

        # Exigir TODAS as unidades do tabuleiro tambem encerra: fechar as 12
        # caixas de um tabuleiro de 12 nao deixa lance nenhum por jogar.
        if (
            total_de_unidades is not None
            and clausula.tipo == "medida"
            and clausula.comparador in {"maior_ou_igual", "igual"}
            and isinstance(clausula.valor, (int, float))
            and clausula.valor >= total_de_unidades
        ):
            return True

    return False
