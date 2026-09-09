"""O motor de damas vestido com os dois papéis (RF-DES-018/019/161/162).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO FAZ, E O QUE ELE NÃO FAZ
═══════════════════════════════════════════════════════════════════════════

**Faz:** traduz entre o vocabulário da camada de motores (`Arbitro`,
`JogadorDeMotor`, estado por valor) e o do motor do laboratório (`Tabuleiro`
mutável, `Lance`, `Buscador`, `HistoricoDaPartida`).

⛔ **Não faz:** regra de damas. Nenhuma. Se uma linha aqui decidir se a dama voa
ou se a captura é obrigatória, o servidor passa a calibrar um jogo que ninguém
joga. Quem sabe as regras é o espelho, byte a byte igual ao laboratório.

═══════════════════════════════════════════════════════════════════════════
O ESTADO É UM VALOR, E CARREGA A PARTIDA INTEIRA
═══════════════════════════════════════════════════════════════════════════

`EstadoDamas` guarda a **posição inicial em FEN** e a **sequência de lances**, e
não só a posição atual. Parece redundante e não é: os empates de damas dependem
da *história* — a mesma posição pela terceira vez (art. 98), vinte lances só de
damas sem progresso (art. 97b), os doze lances da Forçada portuguesa. Um estado
que fosse só o FEN faria o árbitro dizer "a partida continua" numa posição já
empatada, e o desafio publicado prometeria uma vitória impossível.

⚠️ **E é isso que torna o estado serializável de verdade** (RF-DES-162): o job é
um container que morre ao terminar, e o avaliador roda em lote, horas depois,
noutra máquina. O que atravessa é texto.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from motores.damas.contrato_damas import (
    ESPELHO,
    parametros_do_nivel,
    versao_do_motor,
)
from motores.nucleo.carimbo import Carimbo
from motores.nucleo.papeis import LimiteDeBusca, NivelDeMotor, Veredito

# ── A ponte para o espelho ──────────────────────────────────────────────────
#
# O motor do laboratório se importa por caminho absoluto
# (`jogos.jogo_damas.motor.regras_damas`), porque é assim que ele vive no `ia/` —
# e ⛔ editar esses imports quebraria a cópia byte-idêntica que o cadeado 6 prova.
# Então a raiz do espelho entra no caminho de busca do Python, e é ESTE arquivo o
# único lugar do backend que sabe disso.
#
# ⚠️ `str(ESPELHO)` é um caminho DENTRO deste repositório. Não é uma dependência
# de caminho para o `ia/`: o Railway constrói a imagem daqui, e o espelho vem
# junto.
if str(ESPELHO) not in sys.path:
    sys.path.insert(0, str(ESPELHO))

from jogos.jogo_damas.motor.busca_damas import Buscador  # noqa: E402
from jogos.jogo_damas.motor.empates_por_historico_damas import (  # noqa: E402
    HistoricoDaPartida,
)
from jogos.jogo_damas.motor.regras_damas import (  # noqa: E402
    REGULAMENTOS,
    Lance,
    aplicar_lance,
    gerar_lances,
)
from jogos.jogo_damas.motor.tabuleiro_damas import Cor, Tabuleiro  # noqa: E402

# Os motivos de fim de partida, como identificadores — ⛔ **nunca texto de tela**.
# Quem traduz é o app, pelo `l10n`; é a mesma regra do empate das damas
# (RF-DES-019b), e é o que permite acrescentar um idioma sem tocar no servidor.
MOTIVO_SEM_LANCES = "sem_lances"
"""Imobilizar ou capturar tudo: quem tem a vez e não tem lance legal, perdeu."""

# ── Os motivos de EMPATE, traduzidos de prosa para identificador ───────────
#
# ⚠️ **O motor do laboratório devolve prosa**, e de propósito: o motivo dele vai
# para o PDN da partida, onde "empatou" sem dizer por qual artigo é exatamente o
# registro que não deixa auditar depois. Ele diz, por exemplo,
# `"posicao repetida 3 vezes (art. 98)"`.
#
# RF-DES-019b exige que o **servidor** devolva identificador e que quem traduz
# seja o app, pelo `l10n`. ⛔ Consertar isso dentro do espelho está fora de
# questão — ele é cópia byte-idêntica, e editá-lo derruba o cadeado 6. Então a
# tradução é trabalho do adaptador, e é este o lugar dela.
#
# ⚠️ Nota de fato, para quem vier depois: o app HOJE mostra essa prosa crua no
# subtítulo da tela de resultado das damas, então quem joga em inglês ou espanhol
# vê português sem acento. Isso é defeito do app, tem tarefa própria (T003, o
# i18n do empate das damas na spec 008), e ⛔ não se conserta aqui: pôr acento ou
# traduzir no espelho criaria uma terceira grafia e quebraria a paridade com o
# motor em Dart.
#
# A chave é um pedaço estável da prosa; o valor é o identificador que sobe.
_MOTIVOS_DE_EMPATE = (
    ("posicao repetida", "empate_posicao_repetida"),
    ("capturar a dama solitaria", "empate_tres_damas_contra_uma"),
    ("liquidar a dama solitaria na Forcada", "empate_forcada"),
    ("sem progresso", "empate_sem_progresso"),
    ("sem captura nem promocao", "empate_equilibrio_parado"),
)


def _identificador_do_empate(prosa: str) -> str:
    """Traduz a prosa do motor para o identificador que o app conhece.

    Raises:
        ValueError: se a prosa não casar com nenhum motivo conhecido. ⚠️ Falhar
            alto é o comportamento certo: deixar a prosa passar adiante mandaria
            texto em português para dentro de `co_motivo`, e o app cairia na
            tela de "motivo desconhecido" sem que ninguém soubesse por quê. Uma
            regra de empate nova no laboratório **tem de** ser mapeada aqui de
            propósito.
    """
    for pedaco, identificador in _MOTIVOS_DE_EMPATE:
        if pedaco in prosa:
            return identificador
    raise ValueError(
        f"motivo de empate desconhecido vindo do motor: {prosa!r}.\n"
        "O laboratório ganhou uma regra de empate nova. Acrescente-a a "
        "_MOTIVOS_DE_EMPATE, e a chave `.arb` correspondente nos três idiomas."
    )


@dataclass(frozen=True)
class EstadoDamas:
    """Uma partida de damas como **valor** — serializável e sem sessão.

    Atributos:
        co_modalidade: a chave do regulamento (`brasileira`, `anglo`,
            `portuguesa`, `casa`). ⚠️ **Modalidade é dado, não `enum`**: é isso
            que faz italiana e russa caberem depois sem migração.
        fen_inicial: a posição de onde a partida partiu, em FEN de damas.
        lances: os lances jogados desde ali, na notação do motor (`23-18`,
            `30x23x16`). É a mesma forma que `str(Lance)` produz, e é o
            vocabulário que o log de partidas do app já usa.
    """

    co_modalidade: str
    fen_inicial: str
    lances: tuple[str, ...] = ()

    # ⚠️ O estado é **congelado**, mas guarda um cache — e as duas coisas convivem
    # porque `frozen` proíbe *trocar* o campo, não mexer no dicionário que ele já
    # aponta. `compare=False` mantém dois estados iguais comparando iguais mesmo
    # que um deles já tenha reproduzido a partida e o outro não.
    #
    # ⚠️ E é por causa deste campo que a classe **não** usa `slots=True`: sem
    # `__dict__`, `functools.cached_property` não teria onde guardar nada.
    _cache: dict = field(
        default_factory=dict, compare=False, repr=False, hash=False
    )

    # ── Reconstrução ────────────────────────────────────────────────────────

    @property
    def _partida(self) -> tuple[Tabuleiro, HistoricoDaPartida]:
        """Reproduz a partida do início e devolve `(posição atual, histórico)`.

        ⚠️ Reproduzir é o preço de o estado ser um valor, e é um preço baixo: uma
        partida de damas tem dezenas de lances, e o custo some perto de uma busca
        de 288 mil nós. O que se compra é grande: nenhum objeto vivo entre
        chamadas, e um estado que cabe numa coluna de texto do banco.

        O resultado fica guardado em `_cache` — então reproduzir acontece uma
        vez por estado, e não uma vez por pergunta. `veredito` pergunta a posição
        e o histórico na mesma respiração, e o gerador chama `lances_legais`
        antes de `escolher_lance`: sem o cache, a partida seria reproduzida três
        vezes por lance.

        Raises:
            ValueError: se algum lance da sequência for ilegal na posição em que
                aparece. É o que torna o estado **autoverificável**: um estado
                impossível não se constrói em silêncio.
        """
        if "partida" in self._cache:
            return self._cache["partida"]

        regulamento = self._regulamento
        tabuleiro = Tabuleiro.de_fen(self.fen_inicial)
        historico = HistoricoDaPartida.desde(tabuleiro, regulamento)

        for i, texto in enumerate(self.lances, start=1):
            lance = self._lance_de_texto(tabuleiro, texto, ordem=i)
            depois = aplicar_lance(tabuleiro, lance)
            historico.registrar(tabuleiro, lance, depois)
            tabuleiro = depois

        self._cache["partida"] = (tabuleiro, historico)
        return tabuleiro, historico

    @property
    def _regulamento(self):
        """O regulamento da modalidade, recusando alto o que não existe."""
        if self.co_modalidade not in REGULAMENTOS:
            raise ValueError(
                f"modalidade desconhecida: {self.co_modalidade!r}. "
                f"O contrato declara: {', '.join(REGULAMENTOS)}."
            )
        return REGULAMENTOS[self.co_modalidade]

    def _lance_de_texto(self, tabuleiro: Tabuleiro, texto: str, ordem: int) -> Lance:
        """Acha, entre os lances LEGAIS, aquele cujo texto é este.

        ⚠️ Interpretar assim — procurando entre os legais em vez de decompor a
        string — é de propósito: um texto que não corresponda a nenhum lance
        legal simplesmente não existe, e a mensagem diz em que lance da sequência
        o problema está. É a garantia de que nada ilegal atravessa o árbitro.
        """
        for lance in gerar_lances(tabuleiro, self._regulamento):
            if str(lance) == texto:
                return lance
        legais = ", ".join(str(l) for l in gerar_lances(tabuleiro, self._regulamento))
        raise ValueError(
            f"lance {ordem} da sequência ({texto!r}) é ilegal na posição "
            f"{tabuleiro.para_fen()!r} da modalidade {self.co_modalidade!r}.\n"
            f"Legais ali: {legais or '(nenhum — a partida já tinha acabado)'}"
        )

    # ── Leituras ────────────────────────────────────────────────────────────

    @property
    def tabuleiro(self) -> Tabuleiro:
        """A posição atual. ⚠️ É a cópia interna — não a altere."""
        return self._partida[0]

    @property
    def fen(self) -> str:
        """A posição atual em FEN. É o que vai para `co_posicao_inicial`."""
        return self.tabuleiro.para_fen()

    @property
    def vez_de(self) -> int:
        """De quem é a vez, na convenção do log de partidas: `+1` ou `-1`.

        ⚠️ A tradução para `+1`/`-1` acontece aqui, e não no árbitro, porque é
        vocabulário **do log**, não do jogo de damas — e a resolução de um desafio
        é uma partida gravada nesse log (`co_modo='desafio'`).
        """
        return 1 if self.tabuleiro.vez is Cor.BRANCAS else -1

    def com_lance(self, lance: str) -> "EstadoDamas":
        """O estado NOVO depois deste lance. O de origem fica intacto."""
        return EstadoDamas(
            co_modalidade=self.co_modalidade,
            fen_inicial=self.fen_inicial,
            lances=self.lances + (lance,),
        )


class MotorDamas:
    """Veste o motor do laboratório com os dois papéis da camada.

    Satisfaz `Arbitro`, `JogadorDeMotor` e `TradutorDeEstado` **estruturalmente**
    — sem herdar de nada, que é o que permite o motor espelhado continuar
    byte-idêntico (RF-DES-148).

    ⚠️ **Uma instância não guarda partida nenhuma.** O `Buscador` do laboratório
    tem tabela de transposição, mas ele é criado por consulta, dentro de
    `escolher_lance`: reaproveitá-lo entre chamadas faria o mesmo nível jogar
    diferente conforme a ordem em que as posições foram perguntadas, e a
    calibração deixaria de ser reprodutível.
    """

    co_jogo = "damas"

    def __init__(self, co_modalidade: str = "brasileira") -> None:
        if co_modalidade not in REGULAMENTOS:
            raise ValueError(
                f"modalidade desconhecida: {co_modalidade!r}. "
                f"O contrato declara: {', '.join(REGULAMENTOS)}."
            )
        self.co_modalidade = co_modalidade

    # ── Papel ÁRBITRO ───────────────────────────────────────────────────────
    #
    # ⛔ Nenhum destes três métodos faz busca, consulta avaliação ou sorteia. É
    # por isso que o avaliador de resoluções pode receber este objeto tipado como
    # `Arbitro` e ficar impossibilitado de jogar (RF-DES-035/161).

    def lances_legais(self, estado: EstadoDamas) -> list[str]:
        """Todos os lances permitidos na posição atual, na ordem canônica.

        A ordem é a que o motor do laboratório produz, e importa: é ela que o
        gerador usa como desempate reprodutível.
        """
        return [str(l) for l in gerar_lances(estado.tabuleiro, estado._regulamento)]

    def aplicar(self, estado: EstadoDamas, lance: str) -> EstadoDamas:
        """Aplica o lance e devolve o estado NOVO.

        Raises:
            ValueError: se o lance for ilegal. Recusar alto é o comportamento
                certo: quem chama é o auditor, re-executando o que chegou do app,
                e um lance ilegal é exatamente o que ele foi olhar.
        """
        novo = estado.com_lance(lance)
        # Forçar a reconstrução aqui faz a recusa acontecer **agora**, com a
        # mensagem que nomeia o lance — e não três chamadas adiante, quando
        # alguém finalmente perguntar a posição.
        _ = novo.tabuleiro
        return novo

    def veredito(self, estado: EstadoDamas) -> Veredito:
        """Acabou? Por quê? Quem venceu?

        Duas famílias de fim, e as duas precisam do estado inteiro:

        1. **Sem lance legal** — "imobilizar ou capturar" —, e quem tem a vez
           perdeu. Isso a posição sozinha responde.
        2. **Empate por histórico** — a mesma posição pela terceira vez, os
           lances sem progresso, a Forçada portuguesa. ⚠️ Isso a posição sozinha
           **não** responde, e é por isso que `EstadoDamas` carrega a partida.

        ⚠️ O motivo sai como **identificador** (`empate_posicao_repetida`), nunca
        como o texto em prosa que o motor produz — ver `_MOTIVOS_DE_EMPATE`.
        """
        tabuleiro, historico = estado._partida

        if not gerar_lances(tabuleiro, estado._regulamento):
            # Quem não tem lance perdeu; o vencedor é o outro lado.
            vencedor = -1 if tabuleiro.vez is Cor.BRANCAS else 1
            return Veredito(
                acabou=True, co_motivo=MOTIVO_SEM_LANCES, vencedor=vencedor
            )

        prosa = historico.motivo_de_empate(tabuleiro)
        if prosa is not None:
            # ⚠️ Traduzido para identificador: o servidor não manda texto de tela
            # (RF-DES-019b). A prosa original continua disponível no motor, para
            # quem quiser o registro do artigo no PDN.
            return Veredito(
                acabou=True,
                co_motivo=_identificador_do_empate(prosa),
                vencedor=0,
            )

        return Veredito(acabou=False)

    # ── Papel JOGADOR ───────────────────────────────────────────────────────

    def escolher_lance(
        self,
        estado: EstadoDamas,
        nivel: NivelDeMotor,
        limite: LimiteDeBusca | None = None,
        semente: int | None = None,
    ) -> str:
        """Qual lance este motor joga nesta posição, neste nível.

        Args:
            limite: o orçamento da camada. ⚠️ Quando presente, o **menor** entre
                ele e o do contrato é o que vale — o teto do contrato define o
                *nível*, e o da camada protege o *job*; deixar o maior mandar
                anularia um dos dois. `None` usa só o do contrato.
            semente: fixa o acaso do nível, para reprodutibilidade. ⚠️ Só o Sagaz
                é reprodutível sem semente, porque é o único com `ruido=0` e
                `chance_de_errar=0` — é por isso que o gabarito de referência sai
                dele (RF-DES-019a).

        Raises:
            ValueError: se a partida já acabou. Perguntar um lance a uma posição
                terminal é erro de quem chamou, não um caso a tratar com `None`.
        """
        parametros = parametros_do_nivel(nivel)
        tabuleiro, historico = estado._partida

        if not gerar_lances(tabuleiro, estado._regulamento):
            raise ValueError(
                f"a partida já acabou em {estado.fen!r}: não há lance a escolher."
            )

        teto_de_nos = parametros.teto_de_nos
        tempo_maximo = parametros.tempo_maximo
        if limite is not None:
            teto_de_nos = min(teto_de_nos, limite.nos_maximos)
            tempo_maximo = min(tempo_maximo, limite.segundos_maximos)

        # ⚠️ Um `Buscador` NOVO por consulta, e é de propósito: ele carrega
        # tabela de transposição, e reaproveitá-lo entre chamadas faria o mesmo
        # nível jogar diferente conforme a ordem em que as posições foram
        # perguntadas — a calibração deixaria de ser reprodutível.
        buscador = Buscador(regulamento=estado._regulamento, semente=semente)
        resultado = buscador.buscar(
            tabuleiro,
            profundidade=parametros.profundidade,
            teto_de_nos=teto_de_nos,
            tempo_maximo=tempo_maximo,
            ruido=parametros.ruido,
            historico=historico,
            extensao_de_captura=parametros.extensao_de_captura,
            chance_de_errar=parametros.chance_de_errar,
            margem_do_erro=parametros.margem_do_erro,
        )

        if resultado.lance is None:  # pragma: sem cobertura — já recusado acima
            raise ValueError(f"a busca não devolveu lance em {estado.fen!r}.")

        if limite is not None:
            # Devolve à camada o que a busca gastou, para o resumo que vai ao
            # banco: sem isso, "jogou mal" e "não teve tempo de pensar" ficam
            # indistinguíveis.
            gastos = getattr(resultado.estatisticas, "nos", None)
            if gastos and hasattr(limite, "contar_no"):
                limite.contar_no(int(gastos))

        return str(resultado.lance)

    # ── Papel TRADUTOR DE ESTADO ────────────────────────────────────────────

    def para_dado(self, estado: EstadoDamas) -> dict[str, Any]:
        """O estado na forma que o `data-model.md` grava.

        `co_formato_posicao` é **`fen`** nas damas — o Pontinhos usa
        `sequencia_lances`. A chave vai no dicionário para que quem lê a linha do
        banco saiba como interpretá-la sem consultar o jogo.
        """
        return {
            "co_jogo": self.co_jogo,
            "co_modalidade": estado.co_modalidade,
            "co_formato_posicao": "fen",
            "co_posicao_inicial": estado.fen_inicial,
            "sequencia_lances": list(estado.lances),
            "co_posicao_atual": estado.fen,
            "vez_de": estado.vez_de,
        }

    def de_dado(self, dado: dict[str, Any]) -> EstadoDamas:
        """Reconstrói o estado a partir de uma linha do banco.

        ⚠️ Recusa formato que não seja `fen`: uma sequência de lances do
        Pontinhos chegando aqui produziria uma partida de damas plausível e
        errada, em vez de um erro.
        """
        formato = dado.get("co_formato_posicao")
        if formato != "fen":
            raise ValueError(
                f"as damas gravam a posição em 'fen', veio {formato!r}. "
                "O 'sequencia_lances' é o formato do Pontinhos."
            )
        return EstadoDamas(
            co_modalidade=dado["co_modalidade"],
            fen_inicial=dado["co_posicao_inicial"],
            lances=tuple(dado.get("sequencia_lances", ())),
        )

    # ── O carimbo ───────────────────────────────────────────────────────────

    def carimbo(self, nivel: NivelDeMotor, co_versao_perfil: str) -> Carimbo:
        """Quem produziu, com que régua, em que nível (RF-DES-164/146)."""
        return Carimbo(
            co_jogo=self.co_jogo,
            co_nivel=nivel,
            co_versao_motor=versao_do_motor(),
            co_versao_perfil=co_versao_perfil,
            co_modalidade=self.co_modalidade,
        )


def estado_inicial(co_modalidade: str = "brasileira") -> EstadoDamas:
    """A posição de começo de partida da modalidade.

    ⚠️ Nas anglo-americanas quem começa são as **pretas**, e é o regulamento que
    diz isso — não uma constante daqui.
    """
    if co_modalidade not in REGULAMENTOS:
        raise ValueError(
            f"modalidade desconhecida: {co_modalidade!r}. "
            f"O contrato declara: {', '.join(REGULAMENTOS)}."
        )
    regulamento = REGULAMENTOS[co_modalidade]
    return EstadoDamas(
        co_modalidade=co_modalidade,
        fen_inicial=Tabuleiro.inicial(vez=regulamento.quem_comeca).para_fen(),
    )
