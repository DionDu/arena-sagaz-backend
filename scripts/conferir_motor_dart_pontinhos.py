"""O PORTÃO DE BUILD DO MOTOR DO PONTINHOS — a imagem decide igual ao aparelho?

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO É UM PORTÃO, E NÃO UM COMANDO QUE ALGUÉM RODA
═══════════════════════════════════════════════════════════════════════════

Desde 28/09/2026 (T093) o job em batch decide os lances do Pontinhos com o
**motor Dart compilado**, o mesmo código que o aplicativo embarca. Até ali o
servidor decidia com um porte em Python, e os dois divergiam em dois pontos que
nenhum porte fiel resolve: o **sorteador** (Mersenne Twister × xorshift: mesma
semente, sequências diferentes) e a **ordem** das listas sobre as quais se
sorteia.

Medido em 28/09/2026 sobre a bancada: **139 dos 372 meios-lances (37%)**
divergiriam, e **11 das 12 partidas se separavam já no lance 1**. Ou seja, o
gabarito do Pontinhos contra Cacau, Pita ou Tex nunca foi seguível lance a lance.

Na imagem do Railway o binário é **compilado no próprio build**
(`Dockerfile.job`, estágio `motor`), porque o executável da máquina do dono é de
Windows. Isso abre uma pergunta que precisa de resposta a cada imagem construída,
e não uma vez:

    *este binário, compilado aqui, decide o mesmo que o aparelho decide?*

⚠️ É a mesma decisão dos outros dois portões que ficam ao lado dele no
Dockerfile, e o risco que ele fecha é do mesmo feitio — ⛔ não é *"não
compilou"*, que falharia alto e cedo. É compilar, abrir e decidir **um pouco**
diferente.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ELE CONFERE, E POR QUE ASSIM
═══════════════════════════════════════════════════════════════════════════

1. **A trava de identidade.** O binário carimba o SHA-256 dos cinco arquivos de
   `lib/`; o backend recalcula a partir do espelho. Divergiu, não conversa.
   ⚠️ Isto já acontece na abertura do processo — chegar ao passo 2 significa que
   passou. O portão o afirma por escrito para que a falha diga **qual** foi.

2. **A bancada de paridade inteira, reproduzida aqui dentro.** As 12 partidas de
   `contratos/vetores-paridade-pontinhos.json` são refeitas lance a lance, e o
   traço **e** o `co_acao` são comparados.

   ⛔ **E ele ⛔ roda a CNN, de propósito.** A softmax de cada lance viaja no
   arquivo, e é ela que alimenta a decisão: assim este portão mede **só** o
   binário Dart desta imagem. Quem pergunta *"esta imagem infere igual ao
   aplicativo?"* é `conferir_runtime_inferencia.py`, que roda logo acima e tem
   referência própria — misturar os dois faria uma falha de inferência aparecer
   como uma falha de política, e vice-versa.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    python scripts/conferir_motor_dart_pontinhos.py

Sai com `0` quando as duas conferências passam, `1` quando alguma falha — e a
mensagem diz o que esperava, o que veio e o que fazer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ⚠️ A raiz do backend entra no caminho de busca: `python scripts/este.py` põe
# `scripts/` no `sys.path`, e não `/app`. Sem isto, `import motores` falha dentro
# da imagem.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from motores.pontinhos.jogador_dart_pontinhos import (  # noqa: E402
    JogadorDartPontinhos,
    resumo_dos_fontes,
)

#: A bancada, na cópia deste repositório. ⚠️ Ela entra na imagem pelo `COPY . .`,
#: como o resto de `contratos/`.
BANCADA = RAIZ / "contratos" / "vetores-paridade-pontinhos.json"


def main() -> int:
    # ⚠️ **O console do Windows é cp1252**, e os ✅/⛔ desta saída o derrubam com
    # `UnicodeEncodeError` - no meio do portão, com código de saída enganoso.
    # Dentro da imagem (Linux, UTF-8) esta linha não faz nada; na máquina do
    # dono, é o que permite rodar o portão à mão antes de empurrar.
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8", errors="replace")

    if not BANCADA.is_file():
        print(
            f"⛔ a bancada de paridade não está em {BANCADA}.\n"
            "   Gere-a com `python scripts/gerar_vetores_paridade_pontinhos.py`.",
            file=sys.stderr,
        )
        return 1

    documento = json.loads(BANCADA.read_text(encoding="utf-8"))
    mapeamento = {k: int(v) for k, v in documento["mapeamento"].items()}

    print("[portao] 1. a trava de identidade do executavel")
    try:
        motor = JogadorDartPontinhos()
    except Exception as erro:  # noqa: BLE001
        print(f"⛔ {erro}", file=sys.stderr)
        return 1

    with motor:
        esperado = resumo_dos_fontes()
        if motor.resumo_do_motor != esperado:
            # ⚠️ Inalcançável na prática — a abertura já teria recusado. Fica
            # como afirmação por escrito: um dia alguém afrouxa a abertura, e
            # este `if` é o que sobra.
            print(
                f"⛔ o executavel carimba {motor.resumo_do_motor[:16]} e o "
                f"espelho tem {esperado[:16]}.",
                file=sys.stderr,
            )
            return 1
        print(f"   ✅ resumo {esperado[:16]}, dos cinco arquivos de lib/")

        if documento["motor"]["pontinhos"] != esperado:
            print(
                f"⛔ a bancada foi gerada por outro motor.\n"
                f"   no arquivo: {documento['motor']['pontinhos'][:16]}\n"
                f"   nesta imagem: {esperado[:16]}\n"
                f"   Regere: python scripts/gerar_vetores_paridade_pontinhos.py",
                file=sys.stderr,
            )
            return 1

        print("[portao] 2. as partidas da bancada, refeitas aqui dentro")
        total = 0
        for partida in documento["partidas"]:
            chave = partida["argumentos"]["chave"]
            lances_ate_agora: list[str] = []
            for esperado_lance in partida["lances"]:
                resposta = motor.decidir(
                    lances=lances_ate_agora,
                    nivel_do_contrato=chave,
                    softmax=esperado_lance["softmax"],
                    mapeamento=mapeamento,
                    semente=esperado_lance["semente"],
                )
                obtido = (resposta["lance"], resposta["co_acao"])
                queria = (esperado_lance["lance"], esperado_lance["co_acao"])
                if obtido != queria:
                    print(
                        f"⛔ {partida['id']}, lance {esperado_lance['n']}: esta "
                        f"imagem decide diferente do aparelho.\n"
                        f"   aparelho: {queria[0]} ({queria[1]})\n"
                        f"   imagem:   {obtido[0]} ({obtido[1]})\n"
                        f"   semente:  {esperado_lance['semente']}\n"
                        f"   ⚠️ A softmax é a MESMA dos dois lados (veio do "
                        f"arquivo), entao a divergencia esta na politica, na "
                        f"ordenacao ou no sorteador - e nao na rede.",
                        file=sys.stderr,
                    )
                    return 1
                lances_ate_agora.append(esperado_lance["lance"])
                total += 1
            print(f"   ✅ {partida['id']}: {len(partida['lances'])} meios-lances")

        print(
            f"[portao] ✅ esta imagem decide o que o aparelho decide "
            f"({total} meios-lances, {len(documento['partidas'])} partidas)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
