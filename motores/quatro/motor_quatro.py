"""O ÁRBITRO do Quatro em Linha: o que é legal e o que acabou (T105).

═══════════════════════════════════════════════════════════════════════════
POR QUE UM ÁRBITRO EM PYTHON, SE QUEM JOGA É O DART
═══════════════════════════════════════════════════════════════════════════

A camada de motores separa dois papéis (`motores/nucleo/papeis.py`): o
**árbitro**, que conhece as regras e não escolhe lance nenhum, e o **jogador**,
que escolhe. O avaliador de resoluções do Desafio do Dia só recebe o árbitro,
e é isso que torna "validar não é jogar" estrutural: por construção, ele não tem
como jogar.

No Quatro em Linha o jogador é o executável Dart compilado
(`jogador_dart_quatro.py`, T109), o mesmo código do aparelho. O árbitro é este
arquivo, e as regras dele são conferidas contra as do motor Dart pelos vetores
de paridade (`contratos/vetores-paridade-quatro.json`, T106/T107): lances
legais, desfecho e linhas vencedoras em mil posições. ⚠️ As regras de
alinhar e de gravidade são poucas linhas, e escrevê-las aqui custa menos que
uma volta ao executável por pergunta; a garantia de que não divergem é o vetor,
e não a confiança.

═══════════════════════════════════════════════════════════════════════════
O QUE NÃO ESTÁ ESCRITO AQUI
═══════════════════════════════════════════════════════════════════════════

Nenhum tamanho de tabuleiro: a largura, a altura e quantas alinhar vêm do
contrato (`contrato_quatro.py`). E nenhuma modalidade pelo nome: a regra de
cada modalidade é escolhida pelos TIPOS DE LANCE que ela declara (só `soltar`
→ a gravidade). Uma modalidade com outro tipo de lance (o `tirar` do Pop Out)
precisa da sua classe de regras; até lá, o árbitro a recusa com essa frase.

═══════════════════════════════════════════════════════════════════════════
A FORMA DO ESTADO
═══════════════════════════════════════════════════════════════════════════

O estado é a SEQUÊNCIA de lances na notação do contrato (`s4` = soltar na
coluna 4) mais o id da modalidade: é como a partida viaja entre o aparelho, o
log e o servidor (`co_lances_iniciais`, `data-model.md` §2). O Jogador 1 (`+1`,
o azul) faz o 1º lance da sequência.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from motores.nucleo.carimbo import Carimbo
from motores.nucleo.papeis import NivelDeMotor, Veredito
from motores.quatro import contrato_quatro

#: Fim por linha formada: o vencedor é quem fez o último lance.
MOTIVO_ALINHOU = "alinhou"

#: Fim por tabuleiro cheio, sem linha: empate.
MOTIVO_TABULEIRO_CHEIO = "tabuleiro_cheio"

#: O nome do tipo de lance da gravidade (o `tipoSoltarQuatro` do Dart).
TIPO_SOLTAR = "soltar"

# Um lance: uma letra minúscula e a coluna, a partir de 1, sem zero à esquerda
# (a mesma expressão do `_lanceUnico` do motor Dart).
_LANCE = re.compile(r"^([a-z])([1-9][0-9]*)$")

# Um pedaço de sequência: letra seguida de dígitos (o `_pedacoDaSequencia`).
_PEDACO = re.compile(r"[a-z][0-9]*")

#: Uma casa do tabuleiro, **1-based**: `(coluna, linha)`, linha 1 embaixo.
Casa = tuple[int, int]


@dataclass(frozen=True, slots=True)
class TabuleiroQuatro:
    """Uma posição como valor: as colunas e de quem é a vez.

    Atributos:
        colunas: uma tupla por coluna, da esquerda para a direita, com as peças
            DE BAIXO PARA CIMA (`+1` ou `-1`). Uma coluna com menos peças que a
            altura tem casas livres em cima.
        vez: quem joga agora, `+1` ou `-1`.
        lances_jogados: quantos lances levaram até aqui.
    """

    colunas: tuple[tuple[int, ...], ...]
    vez: int
    lances_jogados: int

    def peca(self, casa: Casa) -> int:
        """A peça da casa (`+1`, `-1`), ou 0 se ela está vazia."""
        coluna, linha = casa
        pilha = self.colunas[coluna - 1]
        return pilha[linha - 1] if linha <= len(pilha) else 0


@dataclass(frozen=True, slots=True)
class DesfechoQuatro:
    """Como a partida terminou: `vencedor` `+1`/`-1`, ou `None` no empate.

    `linhas` traz TODAS as linhas formadas pelo vencedor (um lance pode fechar
    duas), cada uma com as casas em ordem ao longo da direção; vazia no empate.
    """

    vencedor: int | None
    linhas: tuple[tuple[Casa, ...], ...] = ()


class RegrasQuatro(Protocol):
    """O que uma modalidade precisa saber responder. Espelha a interface
    `RegrasDaModalidadeQuatro` do motor Dart, com o tabuleiro em Python.

    ⚠️ É a porta da modalidade-sonda (T108): ela entra com uma classe sua, sem
    mudar uma linha do árbitro.
    """

    dimensoes: contrato_quatro.DimensoesQuatro
    tipos_de_lance: Mapping[str, str]

    def inicial(self) -> TabuleiroQuatro: ...

    def lances_legais(self, tabuleiro: TabuleiroQuatro) -> list[tuple[str, int]]:
        """Os lances `(tipo, coluna)`, sem olhar o desfecho (como no Dart)."""
        ...

    def aplicar(self, tabuleiro: TabuleiroQuatro, lance: tuple[str, int]) -> TabuleiroQuatro: ...

    def desfecho(self, tabuleiro: TabuleiroQuatro) -> DesfechoQuatro | None: ...


def linhas_alinhadas(
    dimensoes: contrato_quatro.DimensoesQuatro, tabuleiro: TabuleiroQuatro, jogador: int
) -> list[tuple[Casa, ...]]:
    """As linhas de pelo menos `alinhar` peças do [jogador], nas quatro direções.

    ⚠️ **A ordem é a do motor Dart** (`linhasAlinhadasQuatro`), para os vetores
    se compararem lista contra lista: as direções na ordem vertical,
    horizontal, diagonal que sobe e diagonal que desce (sempre para a direita);
    dentro de cada uma, pela casa de começo, coluna por coluna e de baixo para
    cima (a ordem dos bits do bitboard de coluna-maior).

    Cinco ou mais em linha na mesma direção são UMA linha, com todas as casas.

    ⚠️ **A resposta é guardada por tabuleiro** (`_linhas_guardadas`), e a lista
    devolvida é uma cópia: quem a altera não altera a guardada.
    """
    return list(_linhas_guardadas(dimensoes, tabuleiro, jogador))


#: Quantos tabuleiros `linhas_alinhadas` guarda. ⚠️ Cada entrada é um tabuleiro
#: de 42 casas e uma tupla quase sempre vazia: ~100 mil cabem em poucas dezenas
#: de MB, e a régua de um candidato não passa de algumas dezenas de milhares.
TABULEIROS_GUARDADOS = 1 << 17


@functools.lru_cache(maxsize=TABULEIROS_GUARDADOS)
def _linhas_guardadas(
    dimensoes: contrato_quatro.DimensoesQuatro, tabuleiro: TabuleiroQuatro, jogador: int
) -> tuple[tuple[Casa, ...], ...]:
    """O corpo de `linhas_alinhadas`, guardado por (dimensões, tabuleiro, jogador).

    ⛔ **Existe por causa da régua (T117), e o número é medido.** O juiz do
    desafio reproduz a partida desde a posição publicada para cada prefixo da
    fita, e a régua julga a cada lance: o mesmo tabuleiro chega aqui centenas de
    vezes. Sem a memória, três tentativas de um candidato levaram 35 s, 32 deles
    nesta varredura (20/10/2026). `TabuleiroQuatro` e `DimensoesQuatro` são
    valores imutáveis, então a mesma pergunta tem sempre a mesma resposta.
    """
    largura, altura, n = dimensoes.largura, dimensoes.altura, dimensoes.alinhar
    # Cada direção como (passo na coluna, passo na linha).
    direcoes = ((0, 1), (1, 0), (1, 1), (1, -1))

    def minha(coluna: int, linha: int) -> bool:
        return (
            1 <= coluna <= largura
            and 1 <= linha <= altura
            and tabuleiro.peca((coluna, linha)) == jogador
        )

    linhas: list[tuple[Casa, ...]] = []
    for dc, dl in direcoes:
        for coluna in range(1, largura + 1):
            for linha in range(1, altura + 1):
                # Só começa linha a casa cuja anterior, na direção, não é dele:
                # é o que junta 5 em linha numa só, a partir do 1º começo.
                if not minha(coluna, linha) or minha(coluna - dc, linha - dl):
                    continue
                casas = []
                c, l = coluna, linha
                while minha(c, l):
                    casas.append((c, l))
                    c, l = c + dc, l + dl
                if len(casas) >= n:
                    linhas.append(tuple(casas))
    return tuple(linhas)


class RegrasDeGravidadeQuatro:
    """A regra de gravidade: a peça cai até a casa livre mais baixa da coluna.

    Vence quem forma uma linha de `alinhar`; com o tabuleiro cheio sem linha, é
    empate. Vale para qualquer tamanho que o contrato declare.
    """

    def __init__(
        self,
        dimensoes: contrato_quatro.DimensoesQuatro,
        tipos_de_lance: Mapping[str, str],
    ) -> None:
        self.dimensoes = dimensoes
        self.tipos_de_lance = tipos_de_lance

    def inicial(self) -> TabuleiroQuatro:
        return TabuleiroQuatro(
            colunas=tuple(() for _ in range(self.dimensoes.largura)),
            vez=1,
            lances_jogados=0,
        )

    def lances_legais(self, tabuleiro: TabuleiroQuatro) -> list[tuple[str, int]]:
        # Da coluna 1 à última, as que ainda têm casa livre (a ordem do Dart).
        return [
            (TIPO_SOLTAR, coluna)
            for coluna in range(1, self.dimensoes.largura + 1)
            if len(tabuleiro.colunas[coluna - 1]) < self.dimensoes.altura
        ]

    def aplicar(
        self, tabuleiro: TabuleiroQuatro, lance: tuple[str, int]
    ) -> TabuleiroQuatro:
        if lance not in self.lances_legais(tabuleiro):
            raise ValueError(f"lance ilegal: {lance[0]} na coluna {lance[1]}")
        _, coluna = lance
        colunas = list(tabuleiro.colunas)
        # A peça entra no TOPO da pilha da coluna, que é a casa livre mais baixa.
        colunas[coluna - 1] = colunas[coluna - 1] + (tabuleiro.vez,)
        return TabuleiroQuatro(
            colunas=tuple(colunas),
            vez=-tabuleiro.vez,
            lances_jogados=tabuleiro.lances_jogados + 1,
        )

    def desfecho(self, tabuleiro: TabuleiroQuatro) -> DesfechoQuatro | None:
        if tabuleiro.lances_jogados == 0:
            return None
        # Na gravidade só quem acabou de jogar pode ter formado linha.
        jogador = -tabuleiro.vez
        linhas = linhas_alinhadas(self.dimensoes, tabuleiro, jogador)
        # Vitória ANTES de empate: a última casa, quando fecha linha, é vitória.
        if linhas:
            return DesfechoQuatro(vencedor=jogador, linhas=tuple(linhas))
        if all(len(p) == self.dimensoes.altura for p in tabuleiro.colunas):
            return DesfechoQuatro(vencedor=None)
        return None


#: Qual classe de regras joga uma modalidade, pelos TIPOS de lance que ela
#: declara. ⚠️ É assim que o árbitro escolhe a regra sem saber o nome da
#: modalidade; o Pop Out (`soltar` + `tirar`) entra com uma linha aqui e a sua
#: classe.
FAMILIAS_DE_REGRAS: Mapping[frozenset[str], Callable[..., RegrasQuatro]] = {
    frozenset({TIPO_SOLTAR}): RegrasDeGravidadeQuatro,
}


def regras_da_modalidade(co_modalidade: str) -> RegrasQuatro:
    """As regras da modalidade, montadas a partir do contrato.

    Raises:
        contrato_quatro.ModalidadeDesconhecida: o contrato não a declara.
        contrato_quatro.ContratoQuatroInvalido: os tipos de lance dela não têm
            regra implementada no árbitro.
    """
    dimensoes = contrato_quatro.dimensoes(co_modalidade)
    tipos = contrato_quatro.tipos_de_lance(co_modalidade)
    familia = FAMILIAS_DE_REGRAS.get(frozenset(tipos.values()))
    if familia is None:
        raise contrato_quatro.ContratoQuatroInvalido(
            f"o árbitro não tem regra para os tipos de lance "
            f"{sorted(tipos.values())} da modalidade {co_modalidade!r}."
        )
    return familia(dimensoes, tipos)


@dataclass(frozen=True)
class EstadoQuatro:
    """Uma partida do Quatro em Linha como **valor**: serializável, sem sessão.

    Atributos:
        co_modalidade: o id da modalidade no contrato. ⚠️ Modalidade é dado.
        lances: os lances jogados desde o tabuleiro vazio, um por item
            (`("s4", "s4", "s3")`), inclusive os da posição publicada de um
            desafio.
    """

    co_modalidade: str
    lances: tuple[str, ...] = ()

    # O tabuleiro reconstruído, guardado na 1ª vez que alguém pergunta.
    # `frozen` proíbe trocar o campo, e não mexer no dicionário que ele aponta;
    # `compare=False` mantém iguais dois estados iguais, com cache ou sem.
    _cache: dict = field(default_factory=dict, compare=False, repr=False, hash=False)

    @property
    def sequencia(self) -> str:
        """A partida na notação concatenada (`s4s4s3`), a forma do log."""
        return "".join(self.lances)

    def com_lance(self, lance: str) -> "EstadoQuatro":
        """Um estado NOVO com o lance a mais. Não confere a legalidade."""
        return EstadoQuatro(co_modalidade=self.co_modalidade, lances=self.lances + (lance,))


def ler_sequencia(sequencia: str) -> tuple[str, ...]:
    """Separa `s4s4s3` em `("s4", "s4", "s3")`.

    Raises:
        ValueError: um trecho que não é lance (sobra, espaço, coluna 0).
    """
    lances = []
    consumido = 0
    for pedaco in _PEDACO.finditer(sequencia):
        # Um pedaço que não começa onde o anterior terminou quer dizer lixo
        # entre os dois.
        if pedaco.start() != consumido:
            break
        if not _LANCE.match(pedaco.group(0)):
            raise ValueError(f"lance fora da notação: {pedaco.group(0)!r}")
        lances.append(pedaco.group(0))
        consumido = pedaco.end()
    if consumido != len(sequencia):
        raise ValueError(
            f"sequência com trecho fora da notação a partir de {consumido}: "
            f"{sequencia!r}"
        )
    return tuple(lances)


class MotorQuatro:
    """O árbitro do Quatro em Linha numa modalidade. ⛔ Não escolhe lance.

    Args:
        co_modalidade: o id, que o contrato tem de declarar.
        regras: só para os testes (a modalidade-sonda); sem ele, as regras
            saem do contrato por `regras_da_modalidade`.
    """

    co_jogo = "quatro"

    def __init__(self, co_modalidade: str, regras: RegrasQuatro | None = None) -> None:
        self.co_modalidade = co_modalidade
        self.regras = regras if regras is not None else regras_da_modalidade(co_modalidade)
        # Letra → tipo (`{"s": "soltar"}`) e o inverso, para escrever o lance.
        self._tipo_da_letra = dict(self.regras.tipos_de_lance)
        self._letra_do_tipo = {t: l for l, t in self._tipo_da_letra.items()}

    # ── A notação ───────────────────────────────────────────────────────────

    def _ler_lance(self, texto: str) -> tuple[str, int]:
        achado = _LANCE.match(texto)
        if achado is None:
            raise ValueError(
                f"lance fora da notação (letra + coluna a partir de 1): {texto!r}"
            )
        tipo = self._tipo_da_letra.get(achado.group(1))
        if tipo is None:
            raise ValueError(
                f"tipo de lance desconhecido nesta modalidade: {achado.group(1)!r}"
            )
        return tipo, int(achado.group(2))

    def _escrever_lance(self, lance: tuple[str, int]) -> str:
        tipo, coluna = lance
        return f"{self._letra_do_tipo[tipo]}{coluna}"

    # ── A reconstrução ─────────────────────────────────────────────────────

    def tabuleiro(self, estado: EstadoQuatro) -> TabuleiroQuatro:
        """A posição depois dos lances do [estado], reconstruída uma vez.

        Raises:
            ValueError: um lance ilegal, fora da notação ou depois do fim.
        """
        self._conferir_modalidade(estado)
        if "tabuleiro" not in estado._cache:
            tabuleiro = self.regras.inicial()
            for ordem, texto in enumerate(estado.lances, start=1):
                if self.regras.desfecho(tabuleiro) is not None:
                    raise ValueError(f"lance {ordem} ({texto}) depois do fim da partida")
                lance = self._ler_lance(texto)
                if lance not in self.regras.lances_legais(tabuleiro):
                    raise ValueError(f"lance {ordem} ({texto}) ilegal nesta posição")
                tabuleiro = self.regras.aplicar(tabuleiro, lance)
            estado._cache["tabuleiro"] = tabuleiro
        return estado._cache["tabuleiro"]

    def _conferir_modalidade(self, estado: EstadoQuatro) -> None:
        # Um estado de outra modalidade daria uma partida plausível e errada.
        if estado.co_modalidade != self.co_modalidade:
            raise ValueError(
                f"estado da modalidade {estado.co_modalidade!r} entregue ao "
                f"árbitro da {self.co_modalidade!r}"
            )

    # ── Papel ÁRBITRO ───────────────────────────────────────────────────────

    def lances_legais(self, estado: EstadoQuatro) -> list[str]:
        """Os lances permitidos, da coluna 1 à última; vazia se acabou.

        ⚠️ Diferente do Dart, que lista as colunas livres mesmo numa posição já
        vencida (a busca confere o fim por conta própria): aqui o árbitro
        responde a pergunta inteira, e depois do fim nenhum lance é legal.
        """
        tabuleiro = self.tabuleiro(estado)
        if self.regras.desfecho(tabuleiro) is not None:
            return []
        return [self._escrever_lance(l) for l in self.regras.lances_legais(tabuleiro)]

    def aplicar(self, estado: EstadoQuatro, lance: str) -> EstadoQuatro:
        """Aplica o lance e devolve o estado NOVO.

        Raises:
            ValueError: lance ilegal. Recusar alto é o comportamento certo:
                quem chama é o auditor, re-executando o que chegou do app.
        """
        novo = estado.com_lance(lance)
        # Reconstruir agora faz a recusa acontecer aqui, nomeando o lance.
        self.tabuleiro(novo)
        return novo

    def desfecho(self, estado: EstadoQuatro) -> DesfechoQuatro | None:
        """O desfecho com as linhas vencedoras, ou `None` se não acabou."""
        return self.regras.desfecho(self.tabuleiro(estado))

    def veredito(self, estado: EstadoQuatro) -> Veredito:
        """Acabou? Por quê (identificador, nunca texto de tela)? Quem venceu?"""
        desfecho = self.desfecho(estado)
        if desfecho is None:
            return Veredito(acabou=False)
        if desfecho.vencedor is None:
            return Veredito(acabou=True, co_motivo=MOTIVO_TABULEIRO_CHEIO, vencedor=0)
        return Veredito(acabou=True, co_motivo=MOTIVO_ALINHOU, vencedor=desfecho.vencedor)

    def vez_de(self, estado: EstadoQuatro) -> int:
        """Quem joga agora: `+1` ou `-1`."""
        return self.tabuleiro(estado).vez

    # ── Papel TRADUTOR DE ESTADO ────────────────────────────────────────────

    def para_dado(self, estado: EstadoQuatro) -> dict[str, Any]:
        """O estado na forma que o banco grava (`sequencia_lances`)."""
        return {
            "co_jogo": self.co_jogo,
            "co_modalidade": estado.co_modalidade,
            "co_formato_posicao": "sequencia_lances",
            "sequencia_lances": list(estado.lances),
            "co_lances": estado.sequencia,
            "vez_de": self.vez_de(estado),
        }

    def de_dado(self, dado: dict[str, Any]) -> EstadoQuatro:
        """Reconstrói o estado de uma linha do banco, e confere que ele joga.

        ⚠️ Recusa o formato das damas (`fen`) e o de outro jogo: uma linha
        errada chegando aqui tem de dar erro, e não uma partida plausível.
        """
        if dado.get("co_jogo", self.co_jogo) != self.co_jogo:
            raise ValueError(f"dado do jogo {dado.get('co_jogo')!r}, e não do Quatro")
        formato = dado.get("co_formato_posicao")
        if formato != "sequencia_lances":
            raise ValueError(
                f"o Quatro grava a posição em 'sequencia_lances', veio {formato!r}."
            )
        estado = EstadoQuatro(
            co_modalidade=dado["co_modalidade"],
            lances=tuple(dado.get("sequencia_lances", ())),
        )
        self.tabuleiro(estado)
        return estado

    def estado_de_sequencia(self, sequencia: str) -> EstadoQuatro:
        """O estado a partir da notação concatenada (`co_lances_iniciais`)."""
        estado = EstadoQuatro(co_modalidade=self.co_modalidade, lances=ler_sequencia(sequencia))
        self.tabuleiro(estado)
        return estado

    # ── O carimbo ───────────────────────────────────────────────────────────

    def carimbo(self, nivel: NivelDeMotor, co_versao_perfil: str) -> Carimbo:
        """Quem produziu, com que régua, em que nível (RF-DES-164/146)."""
        return Carimbo(
            co_jogo=self.co_jogo,
            co_nivel=nivel,
            co_versao_motor=contrato_quatro.versao_do_motor(),
            co_versao_perfil=co_versao_perfil,
            co_modalidade=self.co_modalidade,
        )


def estado_inicial(co_modalidade: str) -> EstadoQuatro:
    """O tabuleiro vazio da modalidade, conferido contra o contrato."""
    contrato_quatro.dimensoes(co_modalidade)  # recusa a que não existe
    return EstadoQuatro(co_modalidade=co_modalidade)
