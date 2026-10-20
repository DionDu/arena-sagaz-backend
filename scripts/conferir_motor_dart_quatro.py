"""O PORTÃO DE BUILD DO MOTOR DO QUATRO EM LINHA - a imagem joga igual ao aparelho?

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO É UM PORTÃO, E NÃO UM COMANDO QUE ALGUÉM RODA
═══════════════════════════════════════════════════════════════════════════

O Quatro em Linha nasce sem segunda escrita da política no servidor (T109): quem
escolhe os lances do gabarito e da régua é o executável
`servidor_de_lances_quatro`, compilado do mesmo pacote Dart que o aplicativo
embarca. Na imagem do Railway esse binário é **compilado no próprio build**
(`Dockerfile.job`, estágio `motor`), porque o da máquina do dono é um `.exe` de
Windows. A pergunta que isso abre precisa de resposta a cada imagem construída:

    *este binário, compilado aqui, joga o mesmo que o aparelho joga?*

⚠️ É a decisão dos três portões que ficam ao lado dele no Dockerfile, e o risco
que ele fecha é do mesmo feitio: não é *"não compilou"*, que falharia alto e
cedo. É compilar, abrir e jogar **um pouco** diferente - o gabarito sairia de um
adversário que não é o adversário da pessoa, e nada no dado denunciaria.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ELE CONFERE, E POR QUE ASSIM
═══════════════════════════════════════════════════════════════════════════

1. **As duas travas da abertura.** O binário carimba o SHA-256 dos arquivos de
   `lib/` e anuncia o SHA-256 do contrato que leu (`--contrato`); o backend
   recalcula os dois a partir do espelho. Divergiu, não conversa. ⚠️ Isto já
   acontece ao abrir o processo; o portão o afirma por escrito para que a falha
   diga **qual** das travas foi.

2. **Os lances que o aparelho do dono jogou.** É este o passo que vale: o
   primeiro prova que as peças estão no lugar, e só este prova que elas jogam.
   São **duas partidas inteiras** jogadas pelo dono no `des` em 15/10/2026, num
   APK com o motor `dart_1.1.0`, com a telemetria que o **aparelho** gravou em
   `jogo_quatro.tb002_jogada`:

   - contra o **Magno** (`ccdbd991`, 24 lances): a busca cheia de 216.496 nós,
     depois a busca que prova o resultado (`decidido`), os bloqueios e os
     empates sorteados entre lances de mesma nota;
   - contra o **Tex** (`cef6d255`, 30 lances): o teto de 8.170 nós e o
     **ε aleatório**, que é onde a semente manda no lance.

   ⚠️ **Nós e profundidade entram na conferência, e não só o lance.** Dois
   motores que param em pontos diferentes só escolhem a mesma coluna por sorte -
   foi olhando os nós que o defeito das damas de 25/09/2026 apareceu. E a
   **ação** (`busca_melhor`, `epsilon_aleatorio`...) também: é ela que diz
   *por que* o personagem jogou ali, e uma política diferente pode chegar à
   mesma coluna por outro caminho.

   ⚠️ **Por que todos os 27 lances da CPU, e não três como nas damas:** aqui
   cabem. O lance mais caro (216 mil nós) leva uma fração de segundo, e o portão
   inteiro roda em poucos segundos dentro do build.

═══════════════════════════════════════════════════════════════════════════
⚠️ QUANDO ELE PRECISA MUDAR
═══════════════════════════════════════════════════════════════════════════

Uma mudança DE PROPÓSITO na política ou na busca (outro teto, outro ε, outra
ordenação) faz estes lances legitimamente mudarem: a falha aqui é o aviso de
que o aparelho de quem tem o APK antigo joga outro jogo. A referência então se
refaz com partidas de um APK com o motor novo, lidas no `des` por
`scripts/consultar_des.py` - nunca copiando o que a imagem respondeu, que
transformaria o portão em espelho de si mesmo.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    python scripts/conferir_motor_dart_quatro.py

Sai com `0` quando as duas conferências passam, `1` quando alguma falha - e a
mensagem diz o que esperava, o que veio e o que fazer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ⚠️ A raiz do backend entra no caminho de busca: `python scripts/este.py` põe
# `scripts/` no `sys.path`, e não `/app`. Sem isto, `import motores` falha dentro
# da imagem.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from motores.quatro.jogador_dart_quatro import (  # noqa: E402
    JogadorDartQuatro,
    resumo_dos_fontes,
)

#: A modalidade em que as duas partidas foram jogadas, como o banco a gravou
#: (`partida.tb001_partida.co_variante`). ⚠️ É um DADO das partidas, e não uma
#: escolha deste script: por isso ele é conferido contra o contrato antes de
#: jogar (uma modalidade que saísse do contrato reprovaria aqui, com a mensagem
#: certa, e não lá no meio de um lance).
MODALIDADE_DAS_PARTIDAS = "tradicional"

#: As duas partidas do dono. Cada uma tem:
#:   - `colunas`: a coluna de CADA lance, na ordem; o índice `n-1` é o lance de
#:     ordem `n` (todos os lances são `soltar`, a única ação da modalidade);
#:   - `cpu`: para cada lance da CPU, pela ordem, o que o aparelho gravou:
#:     `(nós visitados, profundidade, semente do lance, ação)`.
#:
#: ⚠️ A CPU é o J2 nas duas (o dono abriu), então os lances dela são os de ordem
#: par. O lance do humano não tem telemetria, e não há o que conferir nele: ele
#: entra só como parte da posição.
PARTIDAS_DO_DONO = (
    {
        "id": "ccdbd991 (Magno)",
        "nivel": NivelDeMotor.SAGAZ,
        "colunas": (
            4, 4, 6, 5, 5, 4, 2, 4, 4, 5, 2, 7,
            6, 5, 6, 6, 3, 1, 7, 3, 6, 2, 3, 3,
        ),
        "cpu": {
            2: (216496, 11, 794831215, "busca_melhor"),
            4: (216496, 12, 1808735441, "busca_melhor"),
            6: (216496, 13, 675156019, "busca_melhor"),
            8: (216496, 12, 1689060245, "busca_melhor"),
            10: (216496, 12, 555480823, "busca_melhor"),
            12: (82071, 12, 1569385049, "empate_sorteado"),
            14: (20393, 10, 435805627, "busca_melhor"),
            16: (820, 8, 1449709853, "bloqueio_imediato"),
            18: (715, 6, 316130431, "bloqueio_imediato"),
            20: (327, 4, 1330034657, "empate_sorteado"),
            22: (35, 2, 196455235, "empate_sorteado"),
            24: (0, 1, 1210359461, "vitoria_imediata"),
        },
    },
    {
        "id": "cef6d255 (Tex)",
        "nivel": NivelDeMotor.TEX,
        "colunas": (
            4, 5, 2, 1, 4, 7, 5, 5, 3, 6, 2, 3, 6, 7, 6,
            5, 4, 4, 6, 6, 3, 3, 1, 1, 1, 3, 3, 5, 5, 4,
        ),
        "cpu": {
            2: (8170, 6, 387603079, "empate_sorteado"),
            4: (8170, 6, 1401507305, "busca_melhor"),
            6: (8170, 6, 267927883, "epsilon_aleatorio"),
            8: (8170, 7, 1281832109, "busca_melhor"),
            10: (8170, 7, 148252687, "epsilon_aleatorio"),
            12: (8170, 9, 1162156913, "bloqueio_imediato"),
            14: (8170, 8, 28577491, "bloqueio_imediato"),
            16: (8170, 8, 1042481717, "busca_melhor"),
            18: (8170, 10, 2056385943, "bloqueio_imediato"),
            20: (8170, 9, 922806521, "bloqueio_imediato"),
            22: (8170, 9, 1936710747, "empate_sorteado"),
            24: (8170, 9, 803131325, "epsilon_aleatorio"),
            26: (8170, 10, 1817035551, "busca_melhor"),
            28: (25, 2, 683456129, "busca_melhor"),
            30: (0, 1, 1697360355, "vitoria_imediata"),
        },
    },
)


def _notacao(colunas: tuple[int, ...]) -> str:
    """A sequência de colunas na notação do motor (`(4, 4, 6)` → `"s4s4s6"`)."""
    return "".join(f"s{coluna}" for coluna in colunas)


def main() -> int:
    """Confere as duas coisas e devolve o código de saída."""
    # ⚠️ O console do Windows é cp1252, e os ✅/⛔ desta saída o derrubariam com
    # `UnicodeEncodeError` no meio do portão. Dentro da imagem (UTF-8) esta
    # linha não faz nada; na máquina do dono, é o que permite rodá-lo à mão.
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8", errors="replace")

    if MODALIDADE_DAS_PARTIDAS not in contrato_quatro.modalidades_declaradas():
        print(
            f"⛔ as partidas de referência são da modalidade "
            f"'{MODALIDADE_DAS_PARTIDAS}', que o contrato do espelho não declara "
            f"({contrato_quatro.modalidades_declaradas()}).",
            file=sys.stderr,
        )
        return 1

    print("[portao] 1. as travas de identidade do executavel")
    try:
        # A abertura já confere o carimbo dos fontes E o SHA-256 do contrato.
        motor = JogadorDartQuatro()
    except Exception as erro:  # noqa: BLE001 - qualquer falha aqui é fatal
        print(f"⛔ o motor Dart do Quatro não abriu:\n{erro}", file=sys.stderr)
        return 1

    with motor:
        esperado = resumo_dos_fontes()
        if motor.resumo_do_motor != esperado:
            # ⚠️ Inalcançável na prática: a abertura já teria recusado. Fica
            # porque um portão que só confia noutro portão não é um portão.
            print(
                f"⛔ o binário carimba {motor.resumo_do_motor[:16]} e os fontes "
                f"espelhados dão {esperado[:16]}.",
                file=sys.stderr,
            )
            return 1
        print(
            f"   ✅ resumo {esperado[:16]} dos fontes, contrato "
            f"{contrato_quatro.sha256_do_contrato()[:16]}"
        )

        print("[portao] 2. os lances que o aparelho do dono jogou")
        total = 0
        for partida in PARTIDAS_DO_DONO:
            colunas = partida["colunas"]
            for ordem, (nos, profundidade, semente, acao) in partida["cpu"].items():
                resposta = motor.decidir(
                    # A posição é a partida inteira ATÉ o lance anterior.
                    lances=_notacao(colunas[: ordem - 1]),
                    co_modalidade=MODALIDADE_DAS_PARTIDAS,
                    nivel=partida["nivel"],
                    semente=semente,
                )
                queria = (f"s{colunas[ordem - 1]}", acao, nos, profundidade)
                obtido = (
                    resposta["lance"],
                    resposta["acao"],
                    resposta["nosVisitados"],
                    resposta["profundidadeAtingida"],
                )
                if obtido != queria:
                    print(
                        f"⛔ {partida['id']}, lance {ordem}: esta imagem joga "
                        f"diferente do aparelho.\n"
                        f"   aparelho: {queria[0]} · {queria[1]} · "
                        f"nos={queria[2]} · prof={queria[3]}\n"
                        f"   imagem:   {obtido[0]} · {obtido[1]} · "
                        f"nos={obtido[2]} · prof={obtido[3]}\n"
                        f"   semente:  {semente}\n"
                        f"   ⚠️ Olhe NÓS e PROFUNDIDADE antes do lance: "
                        f"orçamento diferente é a causa, lance diferente é o "
                        f"sintoma. Se a política mudou de propósito, leia "
                        f"'QUANDO ELE PRECISA MUDAR' no topo deste arquivo.",
                        file=sys.stderr,
                    )
                    return 1
                total += 1
            print(f"   ✅ {partida['id']}: {len(partida['cpu'])} lances da CPU")

    print(
        f"[portao] ✅ esta imagem joga o que o aparelho joga "
        f"({total} lances, {len(PARTIDAS_DO_DONO)} partidas)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
