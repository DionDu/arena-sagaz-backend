"""O PORTÃO DE BUILD DO MOTOR DE DAMAS — a imagem joga igual ao aparelho?

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO É UM PORTÃO, E NÃO UM COMANDO QUE ALGUÉM RODA
═══════════════════════════════════════════════════════════════════════════

Desde 25/09/2026 o job em batch joga com o **motor Dart compilado**, o mesmo
código que o aplicativo embarca — porque o gabarito do Desafio do Dia precisa ser
a partida que a CPU vai jogar no aparelho de quem resolve. Até ali o servidor
jogava com o port Python, e o resultado foi um desafio que o dono descreveu como
*"praticamente impossível"*: no lance 8 o painel dizia `19-23` e o aparelho jogava
`16-20` (`docs/investigacao_paridade_motores.md`).

Na imagem do Railway o binário é **compilado no próprio build** (`Dockerfile.job`,
estágio `motor`), porque o executável da máquina do dono é de Windows. Isso abre
uma pergunta que precisa de resposta a cada imagem construída, e não uma vez:

    *este binário, compilado aqui, joga o mesmo que o aparelho joga?*

⚠️ **É a mesma decisão de `conferir_runtime_inferencia.py`**, que fica logo acima
no Dockerfile pelo mesmo motivo: *"comando avulso se roda uma vez e envelhece; o
portão re-confere a cada imagem construída"*. E o risco que ele fecha é do mesmo
feitio — ⛔ não é *"não compilou"*, que falharia alto e cedo. É compilar, abrir e
devolver lances **um pouco** diferentes.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ELE CONFERE, E POR QUE CADA UM
═══════════════════════════════════════════════════════════════════════════

1. **A trava de identidade.** O binário carimba o SHA-256 dos dezesseis arquivos
   de `lib/`; o backend recalcula a partir do espelho. Divergiu, não conversa.
   ⚠️ Isto já acontece na abertura do processo — chegar ao passo 2 significa que
   passou. O portão o afirma por escrito para que a falha diga **qual** foi.

2. **A base de finais, nas quatro modalidades.** O rodízio publica qualquer uma
   delas; descobrir que falta a `casa` no dia em que ela sai é descobrir tarde.

3. **Os lances de uma partida real.** ⛔ É este o passo que vale: os dois primeiros
   provam que as peças estão no lugar, e só este prova que elas jogam. As posições
   vêm da partida `a267bba1`, jogada pelo dono no `des` em 25/09/2026, com a
   telemetria que o **aparelho** gravou no banco.

   ⚠️ **Nós e consultas à base entram na conferência, e não só o lance.** Dois
   motores que param em pontos diferentes só escolhem o mesmo lance por sorte —
   e foi justamente por olhar os nós que o defeito original apareceu. O lance 16
   traz 795 consultas e 636 acertos: são eles que separam *"usa uma base"* de
   *"usa A base"*.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    python scripts/conferir_motor_dart.py

Sai com `0` quando as três conferências passam, `1` quando alguma falha — e a
mensagem diz o que esperava, o que veio e o que fazer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ⚠️ A raiz do backend entra no caminho de busca: `python scripts/este.py` põe
# `scripts/` no `sys.path`, e não `/app`. Sem isto, `import motores` falha dentro
# da imagem — a mesma linha que `conferir_runtime_inferencia.py` carrega.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.damas.contrato_damas import parametros_do_nivel  # noqa: E402
from motores.damas.jogador_dart import (  # noqa: E402
    JogadorDart,
    pasta_da_base_de_finais,
    resumo_dos_fontes,
)
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402

#: As quatro modalidades do rodízio.
MODALIDADES = ("anglo", "brasileira", "casa", "portuguesa")

#: A posição de onde a partida do dono partiu.
FEN_INICIAL = "W:W18,22,23,28,29,30,31,32:B4,6,8,10,12,13,15,16,21"

#: A partida inteira, na ordem. O índice `n-1` é o lance de ordem `n`.
PARTIDA_DO_DONO = (
    "18x11", "8x15", "23-18", "15-19", "18-15", "4-8", "32-27", "16-20",
    "15-11", "8x15", "22-18", "15x22", "27-23", "19x26", "30x23", "21-25",
    "31-26", "22x31", "29x22", "13-17", "22x13", "31-26", "28-24", "26x19x28",
    "13-9", "6x13",
)

#: `(ordem, semente, nós, profundidade, consultas à base)` — o que o **aparelho**
#: gravou em `jogo_damas.tb002_jogada`.
#:
#: ⚠️ **Três lances, e não os treze.** O portão roda em todo build e precisa ser
#: rápido; os treze estão em `tests/unitarios/test_jogador_dart.py`, que ⛔ não
#: viaja na imagem (o `.dockerignore` barra `tests/`). Os escolhidos cobrem os
#: três regimes: a busca cheia sem base, a busca cheia **com** base, e o final
#: raso onde a base responde quase tudo.
LANCES_CONFERIDOS = (
    # O lance que abriu a investigação: aqui o servidor dizia `19-23`.
    (8, 43215085, 288001, 12, 0),
    # O primeiro lance com a base ligada de verdade.
    (16, 1951348341, 288001, 14, 795),
    # Um final, onde a busca para cedo porque a base já sabe.
    (22, 698093723, 3989, 8, 34),
)


def main() -> int:
    """Confere as três coisas e devolve o código de saída."""
    print("[portao] 1. a trava de identidade do executável")
    try:
        jogador = JogadorDart()
    except Exception as erro:  # noqa: BLE001 — qualquer falha aqui é fatal
        print(f"⛔ o motor Dart não abriu:\n{erro}", file=sys.stderr)
        return 1

    with jogador:
        esperado = resumo_dos_fontes()
        if jogador.resumo_do_motor != esperado:
            # ⚠️ Inalcançável na prática — a abertura já teria recusado. Fica
            # porque um portão que só confia noutro portão não é um portão.
            print(
                f"⛔ o binário carimba {jogador.resumo_do_motor[:16]} e os "
                f"fontes espelhados dão {esperado[:16]}.",
                file=sys.stderr,
            )
            return 1
        print(f"   ✅ resumo {esperado[:16]}, dos dezesseis arquivos de lib/")

        print("[portao] 2. a base de finais das quatro modalidades")
        pastas = {}
        for co_modalidade in MODALIDADES:
            try:
                pastas[co_modalidade] = pasta_da_base_de_finais(co_modalidade)
            except Exception as erro:  # noqa: BLE001
                print(f"⛔ {co_modalidade}: {erro}", file=sys.stderr)
                return 1
        print(f"   ✅ {len(pastas)} modalidades em {pastas['anglo'].parent}")

        print("[portao] 3. os lances que o aparelho do dono jogou")
        parametros = parametros_do_nivel(NivelDeMotor.SAGAZ)
        for ordem, semente, nos, profundidade, consultas in LANCES_CONFERIDOS:
            esperado_lance = PARTIDA_DO_DONO[ordem - 1]
            resposta = jogador.escolher_lance(
                co_modalidade="anglo",
                fen_inicial=FEN_INICIAL,
                lances=PARTIDA_DO_DONO[: ordem - 1],
                parametros=parametros,
                semente=semente,
                pasta_da_base=pastas["anglo"],
            )
            obtido = (
                resposta["lance"],
                resposta["nos"],
                resposta["profundidade"],
                resposta.get("consultas_base"),
            )
            if obtido != (esperado_lance, nos, profundidade, consultas):
                print(
                    f"⛔ lance {ordem}: esta imagem joga diferente do aparelho.\n"
                    f"   aparelho: {esperado_lance} · nos={nos} · "
                    f"prof={profundidade} · consultas={consultas}\n"
                    f"   imagem:   {obtido[0]} · nos={obtido[1]} · "
                    f"prof={obtido[2]} · consultas={obtido[3]}\n"
                    f"   ⚠️ Olhe NÓS e CONSULTAS antes do lance: orçamento "
                    f"diferente é a causa, lance diferente é o sintoma. Ver "
                    f"docs/investigacao_paridade_motores.md.",
                    file=sys.stderr,
                )
                return 1
            print(
                f"   ✅ lance {ordem}: {esperado_lance} · nos={nos} · "
                f"prof={profundidade} · base={consultas}"
            )

    print("[portao] ✅ esta imagem joga o que o aparelho joga.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
