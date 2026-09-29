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

⚠️ **E QUEM AS APLICA ⛔ É MAIS ESTE ARQUIVO, desde a T093 (28/09/2026).** As
três fases moram no motor Dart, em `politica_dificuldade_pontinhos.dart`, e é ele
- compilado, byte-idêntico ao que o aplicativo embarca - que decide. Este módulo
ficou com o que é **do servidor**: ler o contrato, traduzir o vocabulário dos
personagens para o do contrato, e vestir a decisão nos papéis da camada.

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE O PORTE PYTHON SAIU
═══════════════════════════════════════════════════════════════════════════

Ele era um porte fiel de `escolherLance` — e mesmo assim os dois jogavam
diferente, por duas razões que nenhum "porte fiel" resolve:

  1. ⛔ **O SORTEADOR.** `random.Random` é o Mersenne Twister; o `Random` do Dart
     é um xorshift. **Mesma semente, sequências diferentes** — então nem a
     semente publicada do desafio (RF-DES-210) fazia os dois jogarem a mesma
     partida.
  2. ⚠️ **A ORDEM das listas sorteadas.** O `topo` e o `resto` saem do
     ranqueamento, e o servidor o ordenava com desempate por rótulo enquanto o
     aplicativo ordena só pela nota.

⚠️ E o defeito ⛔ dava erro: o lance saía plausível, a partida corria até o fim, e
a única evidência seria o gabarito não ser seguível lance a lance contra Cacau,
Pita ou Tex. Decisão do dono em 26/09/2026, `docs/DECISOES-do-dono.md` §8zj.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from pathlib import Path

from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos import jogador_dart_pontinhos
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
#
# ⚠️ **Quem APLICA este número é o motor Dart** (`casasDoDesempate`, em
# `politica_dificuldade_pontinhos.dart`), desde a T093. Ele fica declarado aqui
# porque o servidor precisa dele para explicar o que fez, e 🔒
# `test_politica_pontinhos_paridade.py` o confere contra o fonte espelhado - um
# número solto que ninguém confere é a definição de comentário que envelhece.
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
    """Os traços que fecham **pelo menos uma caixa agora**, em ordem canônica.

    ⚠️ **A resposta vem do motor Dart** (T093), e não de uma conta feita aqui: é
    sobre esta lista que a Fase A sorteia, e a ORDEM dela é parte do
    comportamento. Duas listas com as mesmas capturas em ordens diferentes
    escolhem lances diferentes com a mesma semente.

    ⚠️ O `motor` entra na assinatura e ⛔ é usado: ele fica porque quem chama tem
    um árbitro na mão, e tirá-lo obrigaria a mexer em todos os chamadores para
    ganhar nada. O estado do Pontinhos é a **sequência de lances**, e é só o que
    o motor Dart precisa.
    """
    return list(
        jogador_dart_pontinhos.jogador_compartilhado().canais(estado.lances)[
            "capturas"
        ]
    )


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
    semente: int | None = None,
) -> Decisao:
    """O lance daquele nível, decidido **pelo motor do aparelho**.

    O caminho é: o motor Dart monta o tensor, a CNN daqui responde, e o motor
    Dart aplica a política sobre a resposta - as três fases, o arredondamento do
    empate e o sorteio, tudo do outro lado da fronteira.

    Args:
        semente: a fonte de acaso **daquele lance**. ⚠️ **Substituiu o
            `random.Random` que este arquivo recebia** (T093): quem sorteia é o
            Dart, e um objeto de sorteio do Python ⛔ atravessa a fronteira. É a
            mesma semente que o desafio publica, derivada por
            `job/semente.semente_do_lance` - e é isso que faz a partida do
            gabarito ser a partida que a pessoa joga.

            `None` = sem semente: o motor sorteia do nada, e duas chamadas da
            mesma posição podem divergir. ⛔ Serve para calibração.

    Raises:
        ValueError: se a partida já acabou, ou se o motor recusar o estado.
    """
    parametros = parametros_do_nivel(nivel)
    if not motor.lances_legais(estado):
        raise ValueError("a partida já acabou: não há lance a escolher.")

    resposta = jogador_dart_pontinhos.jogador_compartilhado().decidir(
        lances=estado.lances,
        nivel_do_contrato=parametros.chave,
        # A softmax crua da rede - a única parte do caminho que é Python.
        softmax=motor.softmax(estado),
        mapeamento=motor.mapeamento_de_rotulos,
        semente=semente,
    )
    return Decisao(lance=resposta["lance"], co_acao=resposta["co_acao"])


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

    @property
    def arbitro(self) -> MotorPontinhos:
        """O motor por baixo, para quem precisa só das REGRAS.

        ⚠️ **Existe porque jogador e árbitro não são a mesma coisa**, e quem
        precisa de um não pode receber o outro por acidente: este objeto sabe
        *escolher* lance (`decidir`), e o árbitro sabe *aplicar* (`aplicar`,
        `lances_legais`). Em 11/09/2026 a recusa por erro do adversário
        (`abertura_forcada`) recebeu o jogador onde queria o árbitro, e quebrou
        com `'JogadorPontinhos' object has no attribute 'aplicar'`.

        ⛔ **Devolver o motor não abre a porta da busca**: `MotorPontinhos` é a
        CNN vestida de papéis, e quem consome esta propriedade usa só o papel de
        árbitro. A alternativa — cada chamador construir o seu `MotorPontinhos()`
        — criaria um segundo intérprete TFLite por candidato, para responder a
        mesma coisa.
        """
        return self._motor

    def escolher_lance(
        self,
        estado: EstadoPontinhos,
        nivel: NivelDeMotor,
        limite=None,
        semente: int | None = None,
    ) -> str:
        """O lance daquele nível. Com semente, é reprodutível.

        ⚠️ A semente cria uma fonte de acaso **própria daquele lance**, do outro
        lado da fronteira. Sem ela, duas calibrações da mesma posição
        divergiriam, e a régua deixaria de significar alguma coisa.
        """
        decisao = escolher_lance(self._motor, estado, nivel, semente)
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
        return escolher_lance(self._motor, estado, nivel, semente)
