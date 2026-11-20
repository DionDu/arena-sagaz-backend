"""O PORTÃO DE BUILD DO MOTOR DO XADREZ - a imagem joga igual ao aparelho? (T061)

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO É UM PORTÃO, E NÃO UM COMANDO QUE ALGUÉM RODA
═══════════════════════════════════════════════════════════════════════════

Quem escolhe os lances do gabarito e da régua do xadrez é o executável
`servidor_de_lances_xadrez`, compilado do mesmo crate Rust que o aplicativo
embarca. Na imagem do Railway ele é **compilado no próprio build**
(`Dockerfile.job`, estágio `motor_xadrez`), porque o da máquina do dono é um
`.exe` de Windows. A pergunta que isso abre precisa de resposta a cada imagem:

    *este binário, compilado aqui, é o motor do aparelho, e joga?*

É o irmão dos três portões dos motores Dart, ao lado dele no Dockerfile.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ELE CONFERE, E POR QUE ASSIM
═══════════════════════════════════════════════════════════════════════════

1. **As três travas da abertura** (`motores/xadrez/jogador_xadrez.py`): o carimbo
   dos fontes contra o crate do espelho, o SHA-256 do contrato, a versão do
   `Cargo.toml`. Isto já acontece ao abrir o processo; o portão o afirma por
   escrito para a falha dizer **qual** trava foi.
2. **As regras numa máquina que não é a do dono.** O `perft` da posição inicial
   a 4 meios-lances tem de dar **197 281** (o número de todo gerador de lances
   correto). Um erro de compilação para `linux/amd64` que mudasse a geração de
   lances apareceria aqui, e não num gabarito.
3. **Cada personagem do build acha o mate em um** (a regra que sai antes de
   todo ruído, R-12): o lance tem de ser `a1a8` e a `acao`, `mate_em_um`.
4. **Os vetores de paridade, lance a lance** (T064, a 3ª ponta;
   `motores/xadrez/paridade_xadrez.py`): cada pedido de `buscar` de
   `contratos/vetores-paridade-xadrez.json` tem de dar o mesmo lance, a mesma
   `acao` e os mesmos nós que o motor deu no laboratório. Aqui, dentro da
   imagem, esta conferência **nunca pula**; no `pytest` local ela pula só sem o
   executável compilado.

⚠️ **Por que os vetores, e não os lances de uma partida do aparelho, como no
Quatro:** os vetores são gerados pelo mesmo crate, cobrem os quatro personagens,
os três inícios, os lances especiais e as cinco `acao`, e o app os confere pela
ponte (a 2ª ponta). Uma partida do `des` cobriria menos.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    python scripts/conferir_motor_xadrez.py

Sai com `0` quando tudo passa, `1` quando algo falha - e a mensagem diz o que
esperava, o que veio e o que fazer.
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

from motores.xadrez import contrato_xadrez, paridade_xadrez  # noqa: E402
from motores.xadrez.jogador_xadrez import (  # noqa: E402
    JogadorXadrez,
    MotorDartDivergente,
    MotorDartIndisponivel,
    resumo_dos_fontes,
)

#: O perft da posição inicial a 4 meios-lances: o número de todo gerador certo.
PERFT_4_DA_INICIAL = 197_281

#: Mate em um para as brancas: a torre de a1 vai a a8 (os peões prendem o rei).
MATE_EM_UM = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
LANCE_DO_MATE = "a1a8"


def main() -> int:
    """Confere as quatro coisas e devolve o código de saída."""
    # ⚠️ O console do Windows é cp1252, e os ✅/⛔ desta saída o derrubariam com
    # `UnicodeEncodeError`. Dentro da imagem (UTF-8) esta linha não faz nada.
    for canal in (sys.stdout, sys.stderr):
        if hasattr(canal, "reconfigure"):
            canal.reconfigure(encoding="utf-8", errors="replace")

    try:
        motor = JogadorXadrez()
    except (MotorDartDivergente, MotorDartIndisponivel) as erro:
        print(f"⛔ a abertura do executável do xadrez falhou:\n{erro}")
        return 1

    falhas: list[str] = []
    with motor:
        print(
            f"✅ abertura: carimbo {motor.resumo_do_motor[:16]} = espelho "
            f"{resumo_dos_fontes()[:16]}; contrato {contrato_xadrez.sha256_do_contrato()[:16]}; "
            f"versão {motor.abertura['versao']}"
        )
        for modalidade in contrato_xadrez.modalidades_declaradas():
            inicial = contrato_xadrez.fen_inicial(modalidade)
            nos = motor.perft(modalidade=modalidade, fen_inicial=inicial, lances=[], profundidade=4)
            if nos == PERFT_4_DA_INICIAL:
                print(f"✅ {modalidade}: perft 4 da inicial = {nos}")
            else:
                falhas.append(
                    f"{modalidade}: perft 4 da inicial deu {nos}, e o certo é "
                    f"{PERFT_4_DA_INICIAL} (o gerador de lances desta compilação está errado)"
                )
            for nivel in contrato_xadrez.niveis_disponiveis(modalidade):
                resposta = motor.buscar(
                    modalidade=modalidade, fen_inicial=MATE_EM_UM, lances=[], nivel=nivel, semente=1
                )
                if (resposta["lance"], resposta["acao"]) == (LANCE_DO_MATE, "mate_em_um"):
                    print(f"✅ {modalidade}, {nivel.value}: acha o mate em um")
                else:
                    falhas.append(
                        f"{modalidade}, {nivel.value}: esperava {LANCE_DO_MATE}/mate_em_um, "
                        f"veio {resposta['lance']}/{resposta['acao']}"
                    )

        # 4. Os vetores: o cabeçalho primeiro (uma versão errada explica em uma
        # linha o que, lance a lance, seriam centenas de diferenças).
        documento = paridade_xadrez.ler_vetores()
        cabecalho = paridade_xadrez.problemas_do_cabecalho(documento)
        if cabecalho:
            falhas.extend(f"vetores: {problema}" for problema in cabecalho)
        else:
            divergentes = paridade_xadrez.conferir_todos(motor, documento)
            total = len(documento["vetores"])
            if divergentes:
                falhas.append(
                    f"{len(divergentes)} de {total} vetores de paridade divergiram; os "
                    "primeiros:\n    " + "\n    ".join(divergentes[:10])
                )
            else:
                print(f"✅ os {total} vetores de paridade: o mesmo lance, ação e nós")

    if falhas:
        print("⛔ o executável do xadrez desta imagem não joga como o do aparelho:")
        for falha in falhas:
            print(f"  - {falha}")
        return 1
    print("✅ o motor do xadrez desta imagem é o do aparelho.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
