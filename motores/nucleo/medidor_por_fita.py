"""O MEDIDOR POR FITA: julga um desafio re-executando os lances (RF-DES-197, T029).

═══════════════════════════════════════════════════════════════════════════
POR QUE MEDIR PELA FITA, E NAO PELA POSICAO FINAL
═══════════════════════════════════════════════════════════════════════════

As funções de feito que o aplicativo já tem leem o **estado**: elas olham o
tabuleiro no fim e contam. Isso basta para a tela de vitória, e nao basta aqui.

⚠️ *"Feche 4 caixas em 2 TURNOS"* nao e uma pergunta sobre o tabuleiro final. Duas
partidas podem terminar na mesma posição, uma com as caixas fechadas em dois
turnos e a outra em seis — e so uma delas cumpriu o desafio. **A janela so existe
no tempo**, e o tempo so existe na fita.

Por isso o árbitro **re-executa** a sequência de lances a partir da posição
inicial, medindo enquanto anda.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS TRES SAIDAS, E POR QUE A TERCEIRA NAO E UM GRAU DA SEGUNDA
═══════════════════════════════════════════════════════════════════════════

    cumpriu        — a linha de chegada foi satisfeita dentro da janela
    nao_cumpriu    — a fita e válida, e o objetivo nao foi atingido
    dado_invalido  — a fita NAO e reproduzível: lance ilegal, traço repetido,
                     rótulo que nao existe no tabuleiro

⛔ **Lance ilegal e DADO INVALIDO, nunca "nao cumpriu"** (D-05). A diferença nao
e formal: uma sincronização com defeito, um aplicativo adulterado ou um bug de
gravação produzem fita irreproduzivel — e tratar isso como tentativa fracassada
esconderia o defeito atrás de milhares de derrotas legítimas.

⚠️ **`Q` divergente e ALERTA, nunca correção** (D-05). Este medidor devolve o que
mediu; quem compara com o que o aplicativo disse e a auditoria, e ela **marca**
a linha — nao apaga resolução, nao tira XP de ninguém.

═══════════════════════════════════════════════════════════════════════════
O QUE E UM "TURNO", E POR QUE ISSO E A PARTE DIFICIL
═══════════════════════════════════════════════════════════════════════════

Um turno e uma **corrida de lances consecutivos do mesmo jogador**.

No Pontinhos, quem fecha uma caixa joga de novo: quatro caixas fechadas em quatro
lances seguidos sao **um** turno, nao quatro. Nas damas cada lance e um turno,
porque nao há jogada extra.

⚠️ Medir turno como lance faria *"em 2 turnos"* virar *"em 2 lances"* — e um
desafio de dificuldade completamente diferente, sem que ninguém tivesse mexido
nele. E o contrário também: um desafio de damas medido por corrida daria o mesmo
número, o que e exatamente por que a regra e uma só para os dois jogos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .chegada import ChegadaInvalida, LinhaDeChegada, avaliar

#: Os tres vereditos possíveis. Mesmo vocabulário dos vetores de verificação.
CUMPRIU = "cumpriu"
NAO_CUMPRIU = "nao_cumpriu"
DADO_INVALIDO = "dado_invalido"


@dataclass(frozen=True, slots=True)
class Julgamento:
    """O que o árbitro achou ao reproduzir a fita.

    Atributos:
        veredito: `cumpriu` · `nao_cumpriu` · `dado_invalido`.
        feitos: as medidas da janela. Vazio quando a fita nao e reproduzível —
            ⚠️ fita recusada nao produz medida, e declarar uma seria inventar dado.
        nu_lance_cumpre_desafio: em que lance da fita a última cláusula passou a
            valer, contado a partir de 1. `None` quando nao cumpriu.
        de_motivo: por que a fita foi recusada, quando foi. Texto de diagnóstico,
            ⛔ **nunca** algo que o aplicativo mostre a alguém — ele nao fala três
            idiomas.
    """

    veredito: str
    feitos: dict[str, float]
    nu_lance_cumpre_desafio: int | None = None
    de_motivo: str | None = None

    @property
    def cumpriu(self) -> bool:
        """Atalho legível para o caso mais consultado."""
        return self.veredito == CUMPRIU


def turnos_da_fita(fita: Sequence[Mapping[str, Any]]) -> list[int]:
    """Para cada lance, em que TURNO ele caiu (contando de 1).

    Um turno e uma corrida de lances consecutivos do mesmo jogador. A contagem e
    **global**, e nao por jogador: o turno 1 e do primeiro a jogar, o 2 do
    seguinte, e assim por diante.

    Exemplo, no Pontinhos, com o jogador 1 fechando três caixas seguidas:

        jogador   1  1  1  -1  1
        turno     1  1  1   2  3

    ⚠️ **A alternância vem da FITA, e nao de uma regra escrita aqui.** Quem sabe
    se houve turno extra e o motor, e a fita e o registro do que ele decidiu. Uma
    regra de turno reimplementada neste arquivo seria uma segunda fonte da
    verdade sobre a alternância — e discordaria do motor no primeiro caso de
    borda.
    """
    turnos: list[int] = []
    turno_atual = 0
    ultimo_jogador: int | None = None

    for lance in fita:
        jogador = lance["jogador"]
        if jogador != ultimo_jogador:
            turno_atual += 1
            ultimo_jogador = jogador
        turnos.append(turno_atual)

    return turnos


def prefixo_da_janela(
    fita: Sequence[Mapping[str, Any]],
    chegada: LinhaDeChegada,
    *,
    jogador: int,
) -> int:
    """Quantos lances da fita cabem dentro da janela.

    Devolve um índice: os `n` primeiros lances de `fita` que a janela abrange.

    ⚠️ **A janela nao corta a fita — ela limita ate onde se MEDE.** A pessoa pode
    continuar jogando depois do objetivo (RF-DES-213), e continua sendo a mesma
    partida; o que a janela decide e ate que lance o desafio olha.
    """
    janela = chegada.janela

    if janela.tipo == "partida":
        return len(fita)

    if janela.tipo == "lances_do_jogador":
        # Os N primeiros lances DAQUELE jogador. Os lances do adversário no meio
        # nao contam para o limite, mas continuam na fita — eles mudam a posição.
        contados = 0
        for indice, lance in enumerate(fita):
            if lance["jogador"] == jogador:
                contados += 1
                if contados > janela.n:
                    return indice
        return len(fita)

    # As duas janelas de turno.
    alvo = jogador if janela.tipo == "turnos_do_jogador" else -jogador
    turnos = turnos_da_fita(fita)
    vistos: list[int] = []
    for indice, (lance, turno) in enumerate(zip(fita, turnos)):
        if lance["jogador"] != alvo:
            continue
        if turno not in vistos:
            vistos.append(turno)
            if len(vistos) > janela.n:
                return indice
    return len(fita)


def julgar(
    *,
    chegada: LinhaDeChegada,
    fita: Sequence[Mapping[str, Any]],
    jogador: int,
    medir_ate,
    predicados: Mapping[str, Any] | None = None,
) -> Julgamento:
    """Reproduz a fita e diz se o desafio foi cumprido.

    Args:
        chegada: a linha de chegada, já validada.
        fita: os lances, cada um `{"n", "jogador", "lance"}` — o vocabulário do
            log de partidas.
        jogador: de quem e o desafio (`+1` ou `-1`).
        medir_ate: função `(quantos_lances) -> dict[str, float]` que reproduz os
            `quantos_lances` primeiros lances da fita e devolve as medidas. E ela
            que carrega as regras do jogo, e por isso vem de fora: este arquivo
            nao conhece Pontinhos nem damas.
        predicados: as respostas dos predicados, quando a chegada os consulta.

    ⚠️ **Mede-se lance a lance, e nao só no fim.** Duas razões, e as duas
    importam: (a) e assim que se descobre **em que lance** o objetivo caiu, que e
    a coluna `nu_lance_cumpre_desafio` — o replay do Raio-X abre em torno dela;
    (b) uma medida que passa pelo alvo e volta (material capturado depois
    perdido) teria cumprido o desafio no meio do caminho, e olhar só o fim diria
    que nao.
    """
    limite = prefixo_da_janela(fita, chegada, jogador=jogador)

    # ── A fita e reproduzível? ──────────────────────────────────────────────
    # A pergunta vem primeiro, e sobre a fita INTEIRA: um lance ilegal depois do
    # objetivo ainda torna o registro corrompido, e um registro corrompido nao
    # sustenta uma resolução — nem a favor nem contra.
    try:
        medir_ate(len(fita))
    except (ValueError, KeyError) as erro:
        return Julgamento(
            veredito=DADO_INVALIDO,
            feitos={},
            de_motivo=str(erro),
        )

    # ── Onde, dentro da janela, a chegada passou a valer ────────────────────
    feitos_na_janela: dict[str, float] = {}
    lance_que_cumpriu: int | None = None

    for quantos in range(1, limite + 1):
        medidas = medir_ate(quantos)
        # Só o lance do jogador do desafio pode fechar a conta: o adversário
        # jogando nao "cumpre" nada por ele.
        if fita[quantos - 1]["jogador"] != jogador:
            continue
        try:
            if avaliar(chegada, medidas, predicados):
                lance_que_cumpriu = quantos
                feitos_na_janela = medidas
                break
        except ChegadaInvalida:
            # ⚠️ Chegada malformada NAO e "nao cumpriu": e desafio que nao deveria
            # ter sido publicado. Sobe para quem chamou, que decide (o job
            # descarta o candidato; a auditoria marca a linha).
            raise

    if lance_que_cumpriu is not None:
        return Julgamento(
            veredito=CUMPRIU,
            feitos=feitos_na_janela,
            nu_lance_cumpre_desafio=lance_que_cumpriu,
        )

    # Nao cumpriu: as medidas são as do fim da janela, e elas continuam valendo.
    # ⚠️ **Quem nao cumpre também tem feitos**, e eles vão para o extrato: o XP de
    # consolo e o Raio-X existem justamente para quem tentou.
    return Julgamento(veredito=NAO_CUMPRIU, feitos=medir_ate(limite))
