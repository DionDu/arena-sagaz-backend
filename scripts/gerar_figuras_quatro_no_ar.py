"""Grava o manifesto das FIGURAS DO QUATRO NO AR, e a copia dele no app (T152).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Desde a T152 (`DECISOES-do-dono.md` §8zzzw) a frase do "Forme a figura" diz
QUAL e a figura: *"Forme um Z em ate 7 lances contra Magno"*. O job publica o
CODIGO (`z`), e o app o traduz pelos tres `.arb`. Codigo que o app nao conhece
cai na frase generica ("Forme esta figura..."), e por isso uma figura nova vai
ao ar sem esperar versao nova.

⚠️ **Mas alguem precisa lembrar de dar o nome a ela na versao seguinte.** Esse
alguem e um cadeado NO APP (`test/modulos/desafio_do_dia/logica/
nome_da_figura_do_quatro_test.dart`), que le a lista de figuras no ar e fica
vermelho quando falta o nome de alguma nos tres idiomas. ⛔ Ele mora no app, e
nao no job: travar o job impediria publicar a figura antes da versao nova.

O app nao le Python. Entao a lista viaja como dado:

    contratos/figuras_quatro_no_ar.json               (este repositorio)
    arena-sagaz-frontend/specs/010-jogo-quatro-em-linha/contracts/
        figuras-quatro-no-ar.json                     (a copia, byte-identica)

e `tests/unitarios/test_figuras_quatro_no_ar.py` confere que o manifesto bate
com o editorial (`editorial.codigos_das_figuras_no_ar`) e que a copia e igual.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\gerar_figuras_quatro_no_ar.py

⚠️ **Rode-o sempre que uma figura entrar no ar ou sair** (uma variante de
`quatro_figura` promovida ou retirada do `EDITORIAL`), na mesma resposta. O
teste do backend avisa se o manifesto envelheceu; o do app, se falta o nome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

from job.editorial import codigos_das_figuras_no_ar  # noqa: E402

#: O manifesto, ao lado dos outros contratos do backend.
MANIFESTO = RAIZ_BACKEND / "contratos" / "figuras_quatro_no_ar.json"

#: A copia do app - so existe quando os repositorios estao lado a lado.
COPIA_DO_APP = (
    RAIZ_BACKEND.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "010-jogo-quatro-em-linha"
    / "contracts"
    / "figuras-quatro-no-ar.json"
)


def conteudo_do_manifesto() -> str:
    """O texto do manifesto, como ele deve estar no disco.

    ⚠️ `ensure_ascii=False`, indentacao e `\\n` no fim: o arquivo e lido por
    gente numa revisao de diff, e o teste compara BYTES com a copia do app.
    """
    dados = {
        "de_documento": (
            "As figuras do 'Forme a figura' (Quatro em Linha) que o editorial do "
            "backend poe no ar. O app exige o nome de cada uma nos tres .arb "
            "(T152). Gerado por scripts/gerar_figuras_quatro_no_ar.py - NAO "
            "edite a mao."
        ),
        "co_fonte_da_verdade": (
            "arena-sagaz-backend/job/editorial.py (EDITORIAL['quatro_figura'])"
        ),
        "nu_versao": 1,
        "co_figuras": list(codigos_das_figuras_no_ar()),
    }
    return json.dumps(dados, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    """Grava o manifesto e, havendo o app ao lado, a copia dele."""
    # O console do Windows nao fala UTF-8 por padrao; sem isto o `✅` estoura.
    # (Aqui, e nao na importacao: o teste importa este modulo.)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    texto = conteudo_do_manifesto()
    # `newline=""`: grava o `\n` como esta, sem virar `\r\n` no Windows.
    with MANIFESTO.open("w", encoding="utf-8", newline="") as arquivo:
        arquivo.write(texto)
    print(f"✅ {MANIFESTO.name}: {json.loads(texto)['co_figuras']}")

    if COPIA_DO_APP.parent.is_dir():
        with COPIA_DO_APP.open("w", encoding="utf-8", newline="") as arquivo:
            arquivo.write(texto)
        print(f"✅ copia do app: {COPIA_DO_APP}")
    else:
        print(
            "⚠️ o repositorio arena-sagaz-frontend nao esta ao lado deste: a "
            "copia do app NAO foi gravada"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
