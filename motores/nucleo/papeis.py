"""Os DOIS PAPÉIS da camada de motores — árbitro e jogador (RF-DES-161).

═══════════════════════════════════════════════════════════════════════════
POR QUE SÃO DOIS, E NÃO UM
═══════════════════════════════════════════════════════════════════════════

RF-DES-035 promete que **"validar não é jogar"**: o avaliador de resoluções
confere o que a pessoa fez sem nunca calcular um lance por conta própria. Se o
avaliador recebesse "o motor", cumprir essa promessa seria questão de
**disciplina** — alguém, um dia, chamaria a busca sem má intenção, e nada
denunciaria.

Aqui ele recebe um objeto tipado como `Arbitro`, e o `Arbitro` **não tem o método
que escolhe lance**. Deixa de ser disciplina e passa a ser a peça:

| papel | responde | **não** faz | quem consome nesta entrega |
|---|---|---|---|
| `Arbitro` | lances legais · aplicar lance · veredito | busca, CNN, escolha, acaso | o avaliador (`job/auditoria.py`) |
| `JogadorDeMotor` | "qual lance no nível N?" | — | o gerador e a régua (`job/`) |

É a mesma ideia de *"o motor decide, o app pergunta"* que as damas já aplicam no
app, com o papel invertido.

═══════════════════════════════════════════════════════════════════════════
POR QUE `Protocol`, E NÃO CLASSE-BASE ABSTRATA
═══════════════════════════════════════════════════════════════════════════

O motor de damas é o Python do laboratório (RF-DES-018), que **já existe** e entra
aqui como **cópia byte-idêntica** dentro do espelho (RF-DES-148). Ele não vai
herdar de nada nosso — herdar obrigaria a editar a cópia, e a cópia editada deixa
de ser byte-idêntica, quebrando o cadeado do manifesto de hashes.

`typing.Protocol` é tipagem **estrutural**: quem tem os métodos, serve. Nenhuma
linha do código espelhado precisa mudar; o adaptador de cada jogo é que veste o
motor com os dois papéis.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO NÃO CONTÉM, DE PROPÓSITO
═══════════════════════════════════════════════════════════════════════════

⛔ Nenhum nome ligado a transporte: requisição, resposta, sessão, token, `Request`,
`Response`. É o critério de aceitação escrito de RF-DES-166, e
`test_papeis_dos_motores.py` o confere lendo as assinaturas — não é só uma
promessa em prosa.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar, runtime_checkable

# ── Os dois tipos que cada jogo escolhe por conta própria ───────────────────
#
# `TypeVar` é uma "variável de tipo": ela não fixa um tipo, ela diz que, sejam
# quais forem, os do árbitro e os do jogador de um MESMO jogo são os mesmos.
# Damas usam FEN e um lance de damas; Pontinhos usam a matriz e um rótulo de
# traço (`H_0_1`). A camada os reúne sem uniformizar (RF-DES-160).
#
# Os dois são INVARIANTES (o padrão, sem `covariant`/`contravariant`), e não por
# descuido: `aplicar()` recebe estado E devolve estado, então o mesmo tipo aparece
# nas duas pontas — declarar variância aqui seria erro de tipagem, não refinamento.
TipoEstado = TypeVar("TipoEstado")
TipoLance = TypeVar("TipoLance")


class NivelDeMotor(enum.Enum):
    """Os quatro degraus da escada da Arena, do mais fraco ao mais forte.

    ⚠️ **É só o degrau.** Os números de cada nível (ε, teto de nós, profundidade,
    timer) NÃO moram aqui: eles vêm do **contrato do jogo**, lido em tempo de
    execução (RF-DES-140/141), porque não viajam entre jogos — o Sagaz das damas
    são 288 mil nós, e o do Pontinhos é a CNN sem ruído nenhum.

    É a mesma separação que `lib/core/jogos/nivel_dificuldade.dart` faz no app, e
    pelo mesmo motivo: pôr número de jogo no degrau faria a camada comum saber de
    um jogo.
    """

    CACAU = "cacau"
    PITA = "pita"
    TEX = "tex"
    SAGAZ = "sagaz"

    @property
    def indice_forca(self) -> int:
        """Posição na escada, de 0 (Cacau) a 3 (Sagaz).

        Serve para ordenar e para gravar no banco um número comparável entre
        jogos — o mesmo papel do `indiceForca` do app.
        """
        # `list(NivelDeMotor)` respeita a ordem de declaração acima.
        return list(NivelDeMotor).index(self)


@dataclass(frozen=True, slots=True)
class Veredito:
    """O que o árbitro responde sobre uma posição: acabou? por quê? quem ganhou?

    `frozen=True` torna o objeto imutável: quem recebe um veredito não consegue
    alterá-lo por engano e devolvê-lo adiante como se fosse outro. `slots=True`
    dispensa o dicionário de atributos — são milhares destes por candidato medido.

    Campos:
        acabou: a partida chegou a estado terminal nesta posição.
        co_motivo: identificador do motivo, **nunca texto de tela**. Quem traduz é
            o app, pelo `l10n` — é a mesma regra do empate das damas
            (RF-DES-019b). `None` enquanto a partida não acabou.
        vencedor: `+1` (jogador 1), `-1` (jogador 2), `0` para empate, `None`
            enquanto não acabou. ⚠️ A convenção `+1`/`-1` é a do log de partidas
            que já existe, e é de propósito: a resolução de um desafio **é uma
            partida** (`co_modo='desafio'`), gravada no mesmo log.
    """

    acabou: bool
    co_motivo: str | None = None
    vencedor: int | None = None


@runtime_checkable
class LimiteDeBusca(Protocol):
    """O que o papel *jogador* precisa saber sobre até onde pode ir.

    ⚠️ **É a fronteira, não a implementação.** A peça concreta — com o relógio, a
    contagem de nós e o cancelamento sem estado sujo — nasce em
    `motores/nucleo/orcamento.py` (RF-DES-163). Aqui fica só a forma que a
    assinatura de `escolher_lance` precisa enxergar, para que este arquivo não
    dependa daquele: os papéis são a base de tudo e não podem depender de nada.

    Um motor bem-comportado consulta `cancelado()` no laço de busca e devolve o
    melhor lance encontrado até ali, em vez de estourar o teto calado.
    """

    @property
    def nos_maximos(self) -> int:
        """Teto de nós da busca. Protege o job de uma posição patológica."""
        ...

    @property
    def segundos_maximos(self) -> float:
        """Teto de tempo. Amanhã, é o que cabe dentro do prazo de um turno."""
        ...

    def cancelado(self) -> bool:
        """`True` quando a busca deve parar e devolver o que já tem."""
        ...


@runtime_checkable
class Arbitro(Protocol[TipoEstado, TipoLance]):
    """O papel que diz o que É LEGAL e o que ACABOU — e nada além disso.

    ⛔ **Não escolhe lance, não faz busca, não consulta rede neural e não sorteia.**
    A ausência do método de escolha é o mecanismo inteiro: o avaliador de
    resoluções recebe um `Arbitro` e, por construção, não tem como jogar.

    ⚠️ Todo método é **puro em relação ao estado**: recebe estado por valor e
    devolve estado novo (RF-DES-162). Nenhum guarda nada entre chamadas — o job é
    um container que morre ao terminar, e o avaliador roda em lote.
    """

    def lances_legais(self, estado: TipoEstado) -> list[TipoLance]:
        """Todos os lances permitidos nesta posição, na ordem canônica do jogo.

        A ordem importa: é ela que o gerador usa como desempate reprodutível, e é
        ela que o mapeamento de rótulos da CNN do Pontinhos assume.
        """
        ...

    def aplicar(self, estado: TipoEstado, lance: TipoLance) -> TipoEstado:
        """Aplica o lance e devolve o **estado novo**, sem tocar no que recebeu.

        Raises:
            ValueError: se o lance for ilegal. ⚠️ Recusar alto é o comportamento
                certo aqui: quem chama é o auditor, re-executando o que chegou do
                app, e um lance ilegal é exatamente o que ele foi olhar.
        """
        ...

    def veredito(self, estado: TipoEstado) -> Veredito:
        """Diz se a partida acabou nesta posição, por que motivo e quem venceu."""
        ...


@runtime_checkable
class JogadorDeMotor(Protocol[TipoEstado, TipoLance]):
    """O papel que ESCOLHE um lance, no nível pedido, dentro de um orçamento.

    O nome não é `Jogador` para não colidir com a pessoa que joga (que no log é
    `+1`/`-1`) nem com o `Jogador` do app. Aqui é *"o motor no papel de quem
    joga"*.

    ⚠️ Este papel **já existe nesta entrega**, e não é preparação especulativa: é
    ele que gera os candidatos e mede a régua de dificuldade. O bot do lobby, um
    dia, consome a mesma peça — sem que ela precise mudar.
    """

    def escolher_lance(
        self,
        estado: TipoEstado,
        nivel: NivelDeMotor,
        limite: LimiteDeBusca,
    ) -> TipoLance:
        """Devolve o lance que este motor joga nesta posição, neste nível.

        ⚠️ **Pode ser não determinístico**, e é de propósito: Cacau, Pita e Tex
        têm ruído (ε) declarado no contrato do jogo. Só o Sagaz é reprodutível, e
        é por isso que o gabarito de referência sai dele (RF-DES-019a).
        A semente, quando existe, é derivada do desafio e do número do lance —
        assunto de `job/`, não daqui.
        """
        ...


@runtime_checkable
class TradutorDeEstado(Protocol[TipoEstado]):
    """Converte o estado do jogo para dado serializável, e de volta (RF-DES-162).

    ⚠️ **Por que é um papel separado, e não métodos no estado.** O estado do motor
    de damas é um objeto do código do laboratório, que entra aqui como cópia
    byte-idêntica: acrescentar métodos nele quebraria o manifesto de hashes. O
    tradutor mora **fora**, no adaptador de cada jogo, e o código espelhado
    continua intocado.

    O formato de saída é o do `data-model.md` — `co_formato_posicao` em
    `sequencia_lances` (Pontinhos) ou `fen` (damas).
    """

    def para_dado(self, estado: TipoEstado) -> dict[str, Any]:
        """Estado → dicionário JSON-serializável, pronto para ir ao banco."""
        ...

    def de_dado(self, dado: dict[str, Any]) -> TipoEstado:
        """Dicionário → estado. É por aqui que se retoma de uma linha do banco."""
        ...
