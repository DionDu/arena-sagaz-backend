"""O MOTOR DO APARELHO DECIDINDO OS LANCES DO PONTINHOS (T093, 28/09/2026).

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE O SERVIDOR DEIXOU DE DECIDIR EM PYTHON
═══════════════════════════════════════════════════════════════════════════

Até 28/09/2026 a política de dificuldade do Pontinhos existia **duas vezes**: em
Dart, no aplicativo, e em Python, em `motores/pontinhos/politica.py`. As duas
liam os mesmos números do mesmo contrato e mesmo assim jogavam diferente, por
dois motivos que ninguém havia decidido:

  1. ⛔ **O SORTEADOR.** O Python usa o Mersenne Twister e o Dart, um xorshift:
     mesma semente, sequências diferentes. Então nem a semente publicada do
     desafio (RF-DES-210) fazia os dois jogarem a mesma partida.
  2. ⚠️ **A ORDEM das listas sorteadas.** O `topo` e o `resto` saem do
     ranqueamento, e o Python o ordenava com desempate por rótulo enquanto o
     aplicativo ordena só pela nota. Onde havia empate - e há, é para isso que o
     arredondamento de três casas existe - os dois sorteavam sobre listas
     diferentes.

⚠️ **E o defeito do Pontinhos é pior que o das damas**, porque ⛔ dá erro: o
lance sai plausível, a partida corre até o fim, e a única evidência seria o
gabarito do desafio não ser seguível lance a lance contra Cacau, Pita ou Tex.

⛔ **A correção não é ajustar um lado: é parar de ter dois.** Este módulo faz o
servidor decidir com **o código que o aparelho embarca**, compilado - decisão do
dono em 26/09/2026 (`docs/DECISOES-do-dono.md` §8zj item 1).

═══════════════════════════════════════════════════════════════════════════
⚠️ A INFERÊNCIA CONTINUA AQUI, E ISSO É DECISÃO
═══════════════════════════════════════════════════════════════════════════

A fronteira entre os dois lados passa pelos **números da rede**: o Dart monta o
tensor de 12 canais, o Python o alimenta ao `ai-edge-litert`, e a saída volta
para o Dart, que ranqueia e decide.

Três razões, em ordem de peso:

  1. ⚠️ **A inferência é a única peça do Pontinhos que JÁ TINHA prova de
     paridade.** `scripts/conferir_runtime_inferencia.py` compara a saída do
     runtime daqui com a do runtime do aplicativo contra uma referência
     versionada, e é **portão do build** da imagem do job desde a T001. O que
     não tinha prova - a política, a ordenação e o sorteador - é justamente o
     que passou para o Dart.
  2. ⛔ **O `tflite_flutter` é um pacote Flutter** e não compila num binário Dart
     puro. Abrir a `libtensorflowlite_c` por FFI traria um **terceiro** runtime
     (Linux x86-64, dentro da imagem), diferente tanto do `ai-edge-litert` quanto
     do que o aparelho Android carrega: ⛔ compraria paridade de inferência
     nenhuma, e ainda acrescentaria um artefato binário à imagem, com trava
     própria para manter.
  3. ⚠️ A `.tflite` e o mapeamento **já viajam no espelho**, já entram no
     manifesto de hashes e já definem o `co_versao_motor`.

═══════════════════════════════════════════════════════════════════════════
⚠️ A TRAVA: O EXECUTÁVEL PRECISA PROVAR DE QUE CÓDIGO SAIU
═══════════════════════════════════════════════════════════════════════════

Pedido do dono, na mesma conversa: *"É preciso todas as travas para que não
corremos o risco de ter uma versão compilada diferente da do App."*

A corrente que fecha isso:

    app        == laboratório   `paridade_motor_pontinhos_test.dart`, SHA-256
                                dos 5 arquivos de `lib/`
    espelho    == laboratório   `scripts/espelhar_laboratorio.py` + o manifesto
    executável == espelho       ESTE módulo, na abertura do processo
    ───────────────────────────────────────────────────────────────────────
    logo, executável == app

⛔ **A conferência é na ABERTURA, e falha alto** - a mecânica inteira mora em
`motores/nucleo/processo_dart.py`, e é a mesma das damas.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Sequence

from motores.nucleo import recursos_por_thread
from motores.nucleo.processo_dart import (
    MotorDartDivergente,
    MotorDartIndisponivel,
    ProcessoDart,
    caminho_do_executavel as _caminho_do_executavel,
    resumo_dos_fontes as _resumo_dos_fontes,
)

__all__ = [
    "MotorDartDivergente",
    "MotorDartIndisponivel",
    "JogadorDartPontinhos",
    "caminho_do_executavel",
    "jogador_compartilhado",
    "resumo_dos_fontes",
]

RAIZ = Path(__file__).resolve().parents[2]

#: Os fontes do motor Dart do Pontinhos, espelhados do laboratório. São a
#: REFERÊNCIA contra a qual o carimbo do executável é conferido.
FONTES_DO_MOTOR_DART = (
    RAIZ / "espelho_laboratorio" / "jogos" / "jogo_pontinhos" / "motor_dart" / "lib"
)

#: A versão do protocolo que este módulo sabe falar. Tem de bater com
#: `versaoDoProtocolo` em `bin/servidor_de_lances_pontinhos.dart`.
#:
#: ⚠️ Ela sobe quando o formato do pedido ou da resposta muda de forma que o
#: outro lado precise saber - sem isto, um backend novo conversando com um
#: executável velho receberia respostas plausíveis e erradas.
VERSAO_DO_PROTOCOLO = 1

#: O que dizer a quem tem um executável ausente ou divergente.
RECEITA_DE_CONSERTO = (
    "Recompile o motor e espelhe de novo:\n"
    "  cd ..\\ia\\jogos\\jogo_pontinhos\\motor_dart\n"
    "  dart run bin\\compilar_servidor_de_lances_pontinhos.dart\n"
    "  cd ..\\..\\..\\..\\arena-sagaz-backend\n"
    "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
)


def resumo_dos_fontes(pasta: Path = FONTES_DO_MOTOR_DART) -> str:
    """O resumo dos fontes Dart do motor do Pontinhos.

    ⚠️ **A conta mora em `motores/nucleo/processo_dart.py`**, e é a mesma que as
    damas usam. Aqui só se fixa a pasta de onde ela lê.
    """
    return _resumo_dos_fontes(pasta)


def caminho_do_executavel() -> Path:
    """Onde está o executável do motor Dart do Pontinhos.

    A ordem de procura (a variável `MOTOR_DART_PONTINHOS`, depois o laboratório
    vizinho) e o porquê de cada degrau estão em
    `motores/nucleo/processo_dart.py`.

    Raises:
        MotorDartIndisponivel: com a receita de como compilar.
    """
    return _caminho_do_executavel(
        variavel_de_ambiente="MOTOR_DART_PONTINHOS",
        nome_do_binario="servidor_de_lances_pontinhos",
        vizinho=RAIZ.parent
        / "ia"
        / "jogos"
        / "jogo_pontinhos"
        / "motor_dart"
        / "bin",
        receita=RECEITA_DE_CONSERTO,
    )


class JogadorDartPontinhos(ProcessoDart):
    """Um processo do motor Dart do Pontinhos, vivo, respondendo a pedidos.

    ⚠️ **Ele não sabe inferir, e não deve saber.** Quem chama monta o diálogo:
    pede os `canais`, roda a rede, e volta com a saída em `ranquear` ou
    `decidir`. É o que mantém a CNN onde ela já tem prova de paridade.

    Use como contexto, para o processo ser encerrado mesmo se algo estourar::

        with JogadorDartPontinhos() as motor:
            canais = motor.canais(lances=())
    """

    def __init__(self, caminho: Path | None = None) -> None:
        super().__init__(
            caminho=caminho or caminho_do_executavel(),
            fontes=FONTES_DO_MOTOR_DART,
            versao_do_protocolo=VERSAO_DO_PROTOCOLO,
            receita_de_conserto=RECEITA_DE_CONSERTO,
        )

    # ── O diálogo ────────────────────────────────────────────────────────────

    def _exigir(self, resposta: dict[str, Any]) -> dict[str, Any]:
        """Devolve a resposta, ou levanta o erro que o motor recusou.

        ⚠️ Falha alto: um estado impossível ⛔ se constrói em silêncio, e um
        pedido malformado que virasse um lance qualquer seria indistinguível de
        uma jogada de verdade no banco.
        """
        if "erro" in resposta:
            raise ValueError(f"o motor Dart do Pontinhos recusou: {resposta['erro']}")
        return resposta

    def canais(self, lances: Sequence[str]) -> dict[str, Any]:
        """O tensor de entrada da rede para esta partida, e o estado dela.

        Args:
            lances: os traços já marcados, na ordem. ⚠️ **O estado do Pontinhos
                é a SEQUÊNCIA, e não a posição**: o turno extra faz "de quem é a
                vez" depender da história.

        Returns:
            `tensor` (144 `float`, na ordem (r, c, k)), `disponiveis`,
            `capturas`, `vez_de`, `placar` e `acabou`.
        """
        return self._exigir(self.pedir({"comando": "canais", "lances": list(lances)}))

    def ranquear(
        self,
        *,
        lances: Sequence[str],
        softmax: Sequence[float],
        mapeamento: dict[str, int],
    ) -> list[tuple[str, float]]:
        """Os traços disponíveis com a probabilidade da rede, do maior ao menor.

        ⛔ **Sem política nenhuma** - é o motor cru. Quem transforma isto nos
        quatro mascotes é [decidir].

        ⚠️ A renormalização e a **ordenação** são feitas pelo Dart, e não aqui: é
        a ordem que define sobre o que a política sorteia, e era uma das duas
        divergências que a T093 fechou.
        """
        resposta = self._exigir(
            self.pedir(
                {
                    "comando": "ranquear",
                    "lances": list(lances),
                    "softmax": list(softmax),
                    "mapeamento": mapeamento,
                }
            )
        )
        return [(item["label"], item["score"]) for item in resposta["ranqueados"]]

    def decidir(
        self,
        *,
        lances: Sequence[str],
        nivel_do_contrato: str,
        softmax: Sequence[float],
        mapeamento: dict[str, int],
        semente: int | None = None,
    ) -> dict[str, Any]:
        """O lance daquele nível, e **como** ele foi decidido.

        Args:
            nivel_do_contrato: `facil` · `normal` · `dificil` · `sagaz`. ⚠️ É o
                vocabulário do **contrato do Pontinhos**, e não o dos
                personagens: a ponte entre os dois é a posição na escada, e ela
                mora em `politica.py`.
            semente: a fonte de acaso daquele lance. ⚠️ **Sem ela o motor sorteia
                do nada**, e duas medições da mesma posição divergiriam - a
                régua deixaria de significar alguma coisa.

        Returns:
            A resposta inteira - `lance`, `co_acao`, `ranqueados`,
            `tamanho_do_topo` e os números do nível. ⚠️ Devolve tudo, e não só o
            lance: é comparando o **ranqueamento** que se descobre que dois lados
            concordaram no lance por sorte, com a rede discordando por baixo.

        Raises:
            ValueError: se o motor recusar (lance ilegal, partida terminada,
                nível desconhecido).
        """
        return self._exigir(
            self.pedir(
                {
                    "comando": "decidir",
                    "lances": list(lances),
                    "nivel": nivel_do_contrato,
                    "softmax": list(softmax),
                    "mapeamento": mapeamento,
                    "semente": semente,
                }
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
# O PROCESSO COMPARTILHADO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **UM MOTOR POR THREAD, e não um por processo.** A fronteira é um
# `stdin`/`stdout` de linha única: quem escreve um pedido espera a resposta antes
# do próximo, e duas threads dividindo o mesmo processo receberiam as respostas
# **trocadas** - sem erro nenhum, que é o pior modo de falha possível.
#
# ⚠️ É a mesma decisão (e o mesmo mecanismo) do motor de damas, inclusive na
# limpeza: `recursos_por_thread` fecha os processos das threads que já morreram,
# e quem abre um motor novo varre os mortos primeiro. Sem isso, gerar 7 dias pelo
# painel deixou 81 motores de damas parados ocupando 5,4 GB (medido em
# 25/09/2026) - e o Pontinhos entraria na mesma armadilha.
_por_thread = threading.local()


def jogador_compartilhado() -> JogadorDartPontinhos:
    """O motor Dart do Pontinhos **desta thread**, subindo-o na primeira vez.

    ⚠️ **Preguiçoso de propósito.** Quem só usa o papel de *árbitro* do
    `MotorPontinhos` - o auditor de resoluções, por exemplo - nunca escolhe um
    lance, e não deve pagar um executável nem falhar por não ter um.

    Raises:
        MotorDartIndisponivel: não há executável compilado.
        MotorDartDivergente: há, mas não saiu dos fontes deste backend.
    """
    meu = getattr(_por_thread, "jogador", None)
    if meu is not None and not meu.morreu:
        return meu

    recursos_por_thread.liberar_de_threads_mortas()
    meu = JogadorDartPontinhos()
    _por_thread.jogador = meu
    recursos_por_thread.registrar(meu)
    return meu
