"""Os vetores de paridade do xadrez, na 3ª ponta: o executável do servidor (T064).

═══════════════════════════════════════════════════════════════════════════
O QUE É UM VETOR, E POR QUE QUATRO PONTAS
═══════════════════════════════════════════════════════════════════════════

Um vetor é um pedido de `buscar` (modalidade, posição, personagem, semente) e a
resposta que o motor deu no laboratório: o **lance**, a **`acao`** (como ele foi
decidido: a melhor busca, o erro sorteado, a cegueira, o mate em um, o lance
único) e os **nós** visitados. O arquivo é GERADO por
`ia/jogos/jogo_xadrez/ferramentas_rust` (`cargo run --release --bin
gerar_vetores`) e conferido em quatro lugares (RF-XDR-056, SC-002):

1. o `cargo test` do crate (`motor_rust/tests/vetores.rs`);
2. o `flutter test` pela ponte `dart:ffi` do app;
3. **aqui**: o executável `servidor_de_lances_xadrez` que escolhe os lances do
   gabarito e da régua no servidor;
4. a bancada nos aparelhos.

Comparar os NÓS, e não só o lance, é o que pega a coincidência: dois motores
diferentes podem concordar no lance de uma posição por sorte, mas não visitam a
mesma quantidade de nós.

═══════════════════════════════════════════════════════════════════════════
POR QUE EM `contratos/`, E NÃO EM `tests/dados/`
═══════════════════════════════════════════════════════════════════════════

O `.dockerignore` deixa `tests/` fora da imagem do job. A conferência que mais
importa é a do **portão do build** (`scripts/conferir_motor_xadrez.py`, no
`Dockerfile.job`): é lá que o executável compilado para Linux é posto à prova,
e lá ela nunca pula. Os vetores das damas e do Quatro moram em `contratos/` pelo
mesmo motivo. O `pytest` confere o mesmo arquivo pelo mesmo código deste módulo.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from motores.xadrez import contrato_xadrez
from motores.xadrez.jogador_xadrez import JogadorXadrez

RAIZ = Path(__file__).resolve().parents[2]

#: A cópia do servidor. ⛔ Não se edita à mão: copia-se da fonte do laboratório
#: na mesma resposta em que ela for regerada.
CAMINHO_DOS_VETORES = RAIZ / "contratos" / "vetores-paridade-xadrez.json"

#: A fonte, no laboratório (no repositório guarda-chuva, ao lado deste).
FONTE_NO_LABORATORIO = (
    RAIZ.parent / "ia" / "jogos" / "jogo_xadrez" / "vetores" / "vetores_paridade_xadrez.json"
)

#: A cópia do app, conferida pelo `flutter test` pela ponte.
COPIA_DO_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "test"
    / "modulos"
    / "jogos"
    / "xadrez"
    / "vetores_paridade_xadrez.json"
)

#: Os três campos da paridade. O `tempo_ms` é relógio e fica de fora; a
#: `profundidade` e o resto da resposta são consequência destes três.
CAMPOS_DA_PARIDADE = ("lance", "acao", "nos")

#: O piso da T043, escrito como número: um arquivo truncado passaria pela
#: conferência lance a lance sem conferir quase nada.
PISO_DE_VETORES = 200

#: O contrário de `contrato_xadrez.PERSONAGEM_DO_NIVEL`: o vetor nomeia o
#: PERSONAGEM (`cacau`), e o `buscar` do servidor pede o NÍVEL do hub. Passar
#: pelo `buscar` (e não mandar o pedido cru) é o que faz a conferência atravessar
#: o mesmo caminho que o gabarito usa, inclusive a recusa do Sagaz num build sem
#: o Magno.
NIVEL_DO_PERSONAGEM = {p: n for n, p in contrato_xadrez.PERSONAGEM_DO_NIVEL.items()}


def ler_vetores(caminho: Path = CAMINHO_DOS_VETORES) -> dict[str, Any]:
    """O arquivo inteiro: o cabeçalho (versões, `quantos`) e a lista `vetores`."""
    return json.loads(caminho.read_text(encoding="utf-8"))


def sha256_do_arquivo(caminho: Path) -> str:
    """O SHA-256 dos BYTES (o texto esconderia um `\\r\\n` do Windows)."""
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def problemas_do_cabecalho(documento: Mapping[str, Any]) -> list[str]:
    """O que o cabeçalho tem de errado contra o motor e o contrato DO ESPELHO.

    Sai primeiro porque explica a falha em uma linha: com os vetores de outra
    versão do motor, a conferência lance a lance mostraria centenas de
    diferenças sem dizer por quê.
    """
    problemas = []
    if documento.get("versao_do_motor") != contrato_xadrez.versao_do_crate():
        problemas.append(
            f"os vetores são do motor {documento.get('versao_do_motor')!r}, e o crate "
            f"espelhado é o {contrato_xadrez.versao_do_crate()!r}"
        )
    if documento.get("versao_do_contrato") != contrato_xadrez.versao_do_contrato():
        problemas.append(
            f"os vetores são do contrato {documento.get('versao_do_contrato')!r}, e o "
            f"espelhado é o {contrato_xadrez.versao_do_contrato()!r}"
        )
    vetores = documento.get("vetores") or []
    if documento.get("quantos") != len(vetores):
        problemas.append(
            f"o cabeçalho diz {documento.get('quantos')} vetores e a lista tem {len(vetores)}"
        )
    if len(vetores) < PISO_DE_VETORES:
        problemas.append(f"só {len(vetores)} vetores (o piso é {PISO_DE_VETORES})")
    return problemas


def conferir_vetor(motor: JogadorXadrez, vetor: Mapping[str, Any]) -> str | None:
    """Refaz o pedido de um vetor pelo executável; `None` = deu o mesmo.

    Returns:
        A diferença, numa linha com o id do vetor e cada campo divergente.
    """
    posicao = vetor["posicao"]
    resposta = motor.buscar(
        modalidade=vetor["modalidade"],
        fen_inicial=posicao["fen_inicial"],
        lances=posicao["lances"],
        nivel=NIVEL_DO_PERSONAGEM[vetor["nivel"]],
        semente=vetor["semente"],
    )
    diferentes = [
        f"{campo}: esperado {vetor[campo]!r}, veio {resposta.get(campo)!r}"
        for campo in CAMPOS_DA_PARIDADE
        if resposta.get(campo) != vetor[campo]
    ]
    return f"{vetor['id']}: {'; '.join(diferentes)}" if diferentes else None


def conferir_todos(motor: JogadorXadrez, documento: Mapping[str, Any]) -> list[str]:
    """As diferenças de todos os vetores (lista vazia = os 100%)."""
    return [
        falha
        for falha in (conferir_vetor(motor, v) for v in documento["vetores"])
        if falha is not None
    ]
