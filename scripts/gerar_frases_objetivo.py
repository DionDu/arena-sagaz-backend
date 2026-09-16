"""GERA a copia das frases de objetivo em portugues, para o painel de curadoria.

═══════════════════════════════════════════════════════════════════════════
POR QUE UMA COPIA, E NAO UMA LEITURA
═══════════════════════════════════════════════════════════════════════════

A fonte da verdade e `arena-sagaz-frontend/lib/l10n/app_pt.arb`. ⛔ **Mas o painel
roda dentro da imagem da API**, onde o repositorio do aplicativo nao existe. Ler o
`.arb` em runtime funcionaria na maquina do dono e falharia em producao — o pior
modo de falhar que ha.

⚠️ **E o mesmo padrao do contrato da CNN e dos vetores de verificacao:** copia no
backend, e um teste que compara e **falha** quando divergem
(`tests/unitarios/test_frases_objetivo.py`).

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    .venv\\Scripts\\python scripts\\gerar_frases_objetivo.py

⚠️ **Rode-o sempre que uma chave `desafioObjetivo*` nascer ou mudar de texto**, na
mesma resposta — e a mesma regra dos tres `.arb`. O teste avisa se alguem
esquecer, mas avisar depois custa uma rodada.

⛔ **So o portugues.** O painel e ferramenta interna de uma pessoa so; carregar
tres idiomas triplicaria a copia para servir ninguem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_ECOSSISTEMA = RAIZ_BACKEND.parent
sys.path.insert(0, str(RAIZ_BACKEND))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from api.desafios.painel.frase_objetivo import (  # noqa: E402
    CAMINHO_DAS_FRASES,
    PREFIXO,
)

#: O `.arb` de autoria, no repositorio do aplicativo.
ARB_DE_ORIGEM = (
    RAIZ_ECOSSISTEMA / "arena-sagaz-frontend" / "lib" / "l10n" / "app_pt.arb"
)


def frases_do_arb(caminho: Path) -> dict[str, str]:
    """As chaves `desafioObjetivo*` daquele `.arb`, sem os metadados `@chave`."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {
        chave: texto
        for chave, texto in sorted(dados.items())
        if chave.startswith(PREFIXO) and not chave.startswith("@")
    }


def main() -> int:
    """Le o `.arb` e regrava a copia."""
    if not ARB_DE_ORIGEM.exists():
        raise SystemExit(
            f"⛔ nao achei o `.arb` do aplicativo em {ARB_DE_ORIGEM}\n"
            "   Este script precisa do repositorio `arena-sagaz-frontend` no "
            "disco, ao lado deste."
        )

    frases = frases_do_arb(ARB_DE_ORIGEM)
    if not frases:
        raise SystemExit(f"⛔ nenhuma chave `{PREFIXO}*` em {ARB_DE_ORIGEM}")

    CAMINHO_DAS_FRASES.parent.mkdir(parents=True, exist_ok=True)
    # ⚠️ `ensure_ascii=False` e `\n` no fim: o arquivo e lido por humanos numa
    # revisao de diff, e `ç` no lugar de `ç` tornaria isso impossivel.
    CAMINHO_DAS_FRASES.write_text(
        json.dumps(frases, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"✅ {len(frases)} frase(s) gravada(s) em {CAMINHO_DAS_FRASES.name}")
    for chave in frases:
        print(f"   · {chave}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
