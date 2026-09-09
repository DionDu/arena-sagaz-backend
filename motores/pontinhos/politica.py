"""A POLÍTICA de dificuldade do Pontinhos, portada do app (RF-DES-018c).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTA PEÇA EXISTE — E É ELA QUE FAZ OS NÍVEIS SEREM QUATRO
═══════════════════════════════════════════════════════════════════════════

⚠️ **A CNN sozinha não é o nível.** A rede é uma só e é determinística: dada a
mesma matriz, devolve sempre a mesma distribuição. Sem esta camada, o job mediria
**quatro vezes o mesmo adversário** e a régua de dificuldade sairia plana — o
Cacau com a mesma nota do Magno, e o desafio do dia sem escada nenhuma.

O que separa os quatro é o que está aqui: com que frequência a CPU erra de
propósito (`epsilon`), e se ela fecha caixa de graça sem pensar
(`usa_captura_gulosa`).

═══════════════════════════════════════════════════════════════════════════
OS NÚMEROS NÃO MORAM AQUI
═══════════════════════════════════════════════════════════════════════════

Eles vêm do `contrato_dificuldade_pontinhos.json`, lido do espelho em tempo de
execução (RF-DES-141). ⚠️ **A fonte da verdade é o Dart** — o enum `Dificuldade`
do aplicativo (`research.md` §R-20) —, e o contrato é a declaração dele. Repetir
os valores neste arquivo criaria uma terceira cópia, e a divergência não daria
erro: o job calibraria contra um adversário que ninguém enfrenta.

═══════════════════════════════════════════════════════════════════════════
AS TRÊS FASES, NA ORDEM EM QUE O APLICATIVO AS APLICA
═══════════════════════════════════════════════════════════════════════════

    FASE 0 — abertura      só o Magno, e só quando ele abre: sorteia o 1º traço
    FASE A — gulosa        Cacau/Pita/Tex: fecha caixa de graça sem ver a CNN
    FASE B — tática        todos: ε-greedy sobre o ranqueamento da rede

É um porte fiel de `escolherLance`, em `oraculo.dart`. ⛔ Divergir dele em
qualquer detalhe — a ordem das fases, o arredondamento do empate, o que conta
como "topo" — faria o servidor medir um jogador que o aparelho não tem.
"""

from __future__ import annotations

import functools
import json
import random
from dataclasses import dataclass
from pathlib import Path

from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos.motor_pontinhos import (
    ESPELHO,
    EstadoPontinhos,
    MotorPontinhos,
)

CAMINHO_DO_CONTRATO = ESPELHO / "contrato_dificuldade_pontinhos.json"

# Casas decimais usadas para decidir o "empate no topo". ⚠️ **Vale para todos os
# personagens**: é o que conta como "o melhor lance", e portanto o que define o
# que é erro. Calibrado por análise da CNN no aplicativo
# (`tools/analise_empates_cnn_pontinhos.py`): 3 casas reproduzem ~92% dos empates
# de uma tolerância relativa de 0,5%.
#
# ⚠️ Sem o arredondamento, um lance que a rede considera praticamente idêntico ao
# melhor (0,4001 contra 0,4004) contaria como "pior", e a CPU "erraria"
# escolhendo um lance tão bom quanto o argmax — o que não é erro nenhum.
CASAS_DO_DESEMPATE = 3


# ── Os valores canônicos de `co_acao` ──────────────────────────────────────
#
# COMO a CPU decidiu o lance. Espelham `AcaoCpu` do aplicativo e a dimensão de
# `specs/006-conta-nuvem/data-model.md`, e vão para a coluna `co_acao` do log.
#
# ⛔ **Não reciclar nome aposentado.** `cnn_nucleo_top_p` existe na dimensão do
# banco por causa das partidas já gravadas com a política anterior; reaproveitar
# a string faria as duas épocas virarem uma só no relatório.
class AcaoCpu:
    """Os identificadores de como a decisão foi tomada."""

    CAPTURA_GULOSA = "captura_gulosa"
    """Fechou caixa de graça na fase gulosa. NÃO consultou a CNN para o lance."""

    CNN_EPSILON_ALEATORIO = "cnn_epsilon_aleatorio"
    """Erro de propósito: sorteou dentro do epsilon e jogou fora do topo."""

    CNN_ARGMAX_ABSOLUTO = "cnn_argmax_absoluto"
    """Melhor lance da rede, sem empate no topo. O Magno cai sempre aqui."""

    CNN_ARGMAX_DESEMPATADO = "cnn_argmax_desempatado"
    """Melhor lance da rede, com empate no topo — sorteado entre os empatados."""

    CNN_ABERTURA_ALEATORIA = "cnn_abertura_aleatoria"
    """Primeiro lance da partida, sorteado. Só o Magno usa."""


@dataclass(frozen=True, slots=True)
class ParametrosDeNivel:
    """A política de um nível, como o contrato a declara.

    Atributos:
        chave: `facil` · `normal` · `dificil` · `sagaz`.
        epsilon: probabilidade de jogar de propósito fora do topo da rede.
        usa_captura_gulosa: fecha caixa de graça sem consultar a CNN.
        timer_segundos: o relógio da jogada do humano. ⚠️ **Não é usado pelo
            job** — ele não tem tela nem humano —, mas viaja junto porque é o
            mesmo contrato que o aplicativo declara, e omiti-lo aqui convidaria a
            uma segunda leitura parcial em outro lugar.
    """

    chave: str
    epsilon: float
    usa_captura_gulosa: bool
    timer_segundos: int | None


# ── A escada, e o nome que cada degrau tem em cada lado ────────────────────
#
# ⚠️ Os dois vocabulários existem e não se fundem: o contrato do Pontinhos fala a
# língua do aplicativo (`facil`/`normal`/`dificil`/`sagaz`), e a camada de motores
# fala a do hub (`cacau`/`pita`/`tex`/`sagaz`), que é a dos personagens. A ponte é
# a POSIÇÃO na escada, e é ela que este mapa declara — nunca uma coincidência de
# nomes, que quebraria no dia em que um personagem for renomeado.
_CHAVE_DO_CONTRATO_POR_NIVEL = {
    NivelDeMotor.CACAU: "facil",
    NivelDeMotor.PITA: "normal",
    NivelDeMotor.TEX: "dificil",
    NivelDeMotor.SAGAZ: "sagaz",
}


@functools.lru_cache(maxsize=1)
def carregar_contrato() -> dict:
    """O contrato de dificuldade do Pontinhos, lido do espelho.

    `lru_cache` porque o job pergunta os parâmetros milhares de vezes por
    calibração — e porque um contrato relido no meio faria metade dos candidatos
    ser medida com uma régua e metade com outra.
    """
    if not CAMINHO_DO_CONTRATO.exists():
        raise FileNotFoundError(
            f"contrato de dificuldade ausente em {CAMINHO_DO_CONTRATO}.\n"
            "Ele vem do aplicativo e viaja no espelho. Rode, na máquina do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    return json.loads(CAMINHO_DO_CONTRATO.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=8)
def parametros_do_nivel(nivel: NivelDeMotor) -> ParametrosDeNivel:
    """Os parâmetros do nível, como o contrato os declara.

    Raises:
        KeyError: se o contrato não declarar o nível. ⚠️ Cair num valor padrão
            faria o job medir o Magno com o desleixo da Cacau e gravar "sagaz"
            no banco — o pior desfecho possível.
    """
    chave = _CHAVE_DO_CONTRATO_POR_NIVEL[nivel]
    for bruto in carregar_contrato()["niveis"]:
        if bruto["chave"] == chave:
            return ParametrosDeNivel(
                chave=chave,
                epsilon=float(bruto["epsilon"]),
                usa_captura_gulosa=bool(bruto["usa_captura_gulosa"]),
                timer_segundos=bruto["timer_segundos"],
            )
    declarados = [n["chave"] for n in carregar_contrato()["niveis"]]
    raise KeyError(
        f"o contrato de dificuldade do Pontinhos não declara {chave!r}. "
        f"Declara: {', '.join(declarados)}."
    )


def capturas_disponiveis(
    motor: MotorPontinhos, estado: EstadoPontinhos
) -> list[str]:
    """Os traços que fecham **pelo menos uma caixa agora**.

    ⚠️ A conta é feita **jogando o lance num estado novo** e olhando o placar, e
    não inspecionando a matriz por fora. É o mesmo resultado, e evita reescrever
    a regra de "caixa fechada" — que é do laboratório, e ⛔ não se reimplementa.
    """
    capturas = []
    antes = sum(estado.placar.values())
    for lance in motor.lances_legais(estado):
        if sum(motor.aplicar(estado, lance).placar.values()) > antes:
            capturas.append(lance)
    return capturas


def _separar_topo(
    ranqueados: list[tuple[str, float]],
) -> tuple[list[str], list[str]]:
    """Parte o ranqueamento em (topo, resto).

    O **topo** é o melhor lance e todos os que empatam com ele depois de
    arredondar a `CASAS_DO_DESEMPATE`; o resto é o restante. ⚠️ O topo nunca é
    vazio — se estivesse, a fase tática não teria o que jogar quando acertasse.
    """
    def arredondar(valor: float) -> float:
        fator = 10.0**CASAS_DO_DESEMPATE
        # `round(x * 1000) / 1000` — a mesma conta que o Dart faz com
        # `roundToDouble`, e de propósito: dois arredondamentos diferentes
        # separariam o topo de formas diferentes nos dois lados.
        return round(valor * fator) / fator

    maximo = max(arredondar(p) for _, p in ranqueados)
    topo = [rotulo for rotulo, p in ranqueados if arredondar(p) == maximo]
    resto = [rotulo for rotulo, p in ranqueados if arredondar(p) != maximo]
    return topo, resto


@dataclass(frozen=True, slots=True)
class Decisao:
    """O traço escolhido e **como** ele foi escolhido.

    O `co_acao` não é enfeite de log: é ele que permite, depois, distinguir uma
    derrota da CPU por erro de propósito de uma derrota por a rede ter jogado o
    melhor lance e não bastar. Sem isso, calibrar dificuldade é adivinhação.
    """

    lance: str
    co_acao: str


def escolher_lance(
    motor: MotorPontinhos,
    estado: EstadoPontinhos,
    nivel: NivelDeMotor,
    sorteio: random.Random | None = None,
) -> Decisao:
    """Aplica a política do nível sobre o ranqueamento da rede.

    Porte fiel de `escolherLance` (`oraculo.dart`), fase por fase.

    Args:
        sorteio: a fonte de acaso. ⚠️ **Entra por parâmetro**, e nunca é o
            `random` global: uma calibração precisa ser reprodutível, e o estado
            global faz uma chamada influenciar a seguinte.

    Raises:
        ValueError: se a partida já acabou.
    """
    sorteio = sorteio or random.Random()
    parametros = parametros_do_nivel(nivel)
    disponiveis = motor.lances_legais(estado)
    if not disponiveis:
        raise ValueError("a partida já acabou: não há lance a escolher.")

    # ── FASE 0 (abertura): só o Magno, e só quando ELE abre ────────────────
    #
    # POR QUE existe: num tabuleiro virgem a rede é determinística, e com
    # `epsilon == 0` o Magno abriria TODA partida com o mesmo traço — previsível
    # para quem joga, e, no desafio, um dia igual ao outro.
    #
    # POR QUE é seguro: no tabuleiro vazio os 31 traços são equivalentes por
    # simetria, então sortear não o enfraquece. E o encoding **não** é
    # canonicalizado (não há rotação nem espelhamento antes da inferência), logo
    # o traço sorteado é diretamente jogável.
    #
    # Os outros três não passam por aqui porque o `epsilon` deles já dá variedade.
    if nivel is NivelDeMotor.SAGAZ and not estado.lances:
        return Decisao(
            lance=sorteio.choice(disponiveis),
            co_acao=AcaoCpu.CNN_ABERTURA_ALEATORIA,
        )

    # ── FASE A (gulosa): fecha caixa de graça sem pensar ───────────────────
    #
    # Capturar caixa aberta não é habilidade, é instinto: todo iniciante faz.
    # Sabotar isso com o `epsilon` faria a CPU ignorar caixa de graça na cara
    # dela, o que parece DEFEITO e não dificuldade — e ainda quebraria o turno
    # extra que encadeia a captura da cadeia inteira.
    #
    # ⚠️ O Magno é o único que NÃO passa aqui, e é isso que o deixa livre para o
    # sacrifício da dupla-cruz: abrir mão das duas últimas caixas de uma cadeia
    # para manter o turno. É a jogada mestre que os outros três nunca fazem.
    if parametros.usa_captura_gulosa:
        capturas = capturas_disponiveis(motor, estado)
        if capturas:
            return Decisao(
                lance=sorteio.choice(capturas), co_acao=AcaoCpu.CAPTURA_GULOSA
            )

    # ── FASE B (tática): ε-greedy sobre o ranqueamento ─────────────────────
    ranqueados = motor.ranquear(estado)
    topo, resto = _separar_topo(ranqueados)

    # `random()` devolve um número em [0,1). Cair abaixo do epsilon é errar de
    # propósito. Com epsilon 0 (Magno) a condição é sempre falsa.
    vai_errar = sorteio.random() < parametros.epsilon

    # ⚠️ Se TODOS os lances empatam no topo, não existe "fora do topo" para
    # errar — qualquer escolha é ótima, e o ε não tem o que fazer.
    if vai_errar and resto:
        return Decisao(
            lance=sorteio.choice(resto), co_acao=AcaoCpu.CNN_EPSILON_ALEATORIO
        )

    return Decisao(
        lance=sorteio.choice(topo),
        co_acao=(
            AcaoCpu.CNN_ARGMAX_DESEMPATADO
            if len(topo) > 1
            else AcaoCpu.CNN_ARGMAX_ABSOLUTO
        ),
    )


class JogadorPontinhos:
    """O motor do Pontinhos **com** a política — o adversário de verdade.

    É esta a classe que o job usa: `MotorPontinhos` sozinho joga sempre como o
    Magno, e quatro medições dele dariam a mesma nota quatro vezes.

    Satisfaz `JogadorDeMotor` estruturalmente, e delega os três métodos do
    árbitro ao motor — o que mantém "validar não é jogar" de pé: quem recebe um
    `Arbitro` continua recebendo um objeto sem `escolher_lance`.
    """

    co_jogo = "pontinhos"

    def __init__(self, motor: MotorPontinhos | None = None) -> None:
        self._motor = motor or MotorPontinhos()

    def escolher_lance(
        self,
        estado: EstadoPontinhos,
        nivel: NivelDeMotor,
        limite=None,
        semente: int | None = None,
    ) -> str:
        """O lance daquele nível. Com semente, é reprodutível.

        ⚠️ A semente cria uma fonte de acaso **própria desta consulta**. Sem ela,
        duas calibrações da mesma posição divergiriam, e a régua deixaria de
        significar alguma coisa.
        """
        sorteio = random.Random(semente) if semente is not None else None
        decisao = escolher_lance(self._motor, estado, nivel, sorteio)
        if limite is not None and hasattr(limite, "contar_no"):
            limite.contar_no(1)
        return decisao.lance

    def decidir(
        self,
        estado: EstadoPontinhos,
        nivel: NivelDeMotor,
        semente: int | None = None,
    ) -> Decisao:
        """Como `escolher_lance`, mas devolvendo também o `co_acao`."""
        sorteio = random.Random(semente) if semente is not None else None
        return escolher_lance(self._motor, estado, nivel, sorteio)
