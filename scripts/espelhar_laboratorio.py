"""T009 - A CÓPIA AUTORIZADA do laboratório para dentro do backend (RF-DES-148).

═══════════════════════════════════════════════════════════════════════════
POR QUE O BACKEND PRECISA DE UMA CÓPIA
═══════════════════════════════════════════════════════════════════════════

O job em batch joga damas e Pontinhos no servidor para gerar e calibrar os
desafios. O motor de damas é o Python do laboratório (RF-DES-018) — ele existe,
está medido, e reimplementá-lo seria criar uma segunda fonte da verdade.

Só que **o Railway constrói a imagem a partir do repositório do backend**: o que
não estiver dentro dele não existe na nuvem. Uma dependência de caminho para
`../ia/` funciona na máquina do dono e **falha em produção**, com um `ImportError`
no meio da madrugada em que o desafio do dia deveria ter sido gerado.

Então entra aqui uma **cópia versionada**, exatamente como o app já faz com os
quinze arquivos do motor Dart de damas. ⚠️ **Um mecanismo, não dois**: os mesmos
dois cadeados — o que prova a paridade por SHA-256 e o que impede alguém de
trocar a cópia por uma dependência de caminho para outro repositório.

═══════════════════════════════════════════════════════════════════════════
CÓPIA AUTORIZADA, NÃO POSSE (RF-DES-149)
═══════════════════════════════════════════════════════════════════════════

⛔ **A fonte da verdade não muda de dono.** Ela continua sendo o código em `ia/`.
Este script **copia**; ele nunca é a origem de nada. Editar um arquivo dentro de
`espelho_laboratorio/` é sempre erro: a próxima execução o desfaz, e o cadeado
(`tests/unitarios/test_espelho_laboratorio.py`) acusa antes disso.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\espelhar_laboratorio.py            # copia e regrava o manifesto
    .venv\\Scripts\\python scripts\\espelhar_laboratorio.py --conferir  # só confere, não escreve

⚠️ Ele **precisa do `ia/` no disco**, então roda na máquina do dono, nunca no CI.
O CI usa o outro lado do mecanismo: o manifesto, que viaja junto com a cópia.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

# `parents[1]` sobe de `scripts/este_arquivo.py` para a raiz do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_ECOSSISTEMA = RAIZ_BACKEND.parent
RAIZ_LABORATORIO = RAIZ_ECOSSISTEMA / "ia"

ESPELHO = RAIZ_BACKEND / "espelho_laboratorio"
CAMINHO_DO_MANIFESTO = ESPELHO / "MANIFESTO_HASHES.json"

VERSAO_DO_MANIFESTO = "1.0.0"
"""Sobe quando a **forma** do manifesto mudar, não quando um hash mudar."""


# ═══════════════════════════════════════════════════════════════════════════
# O QUE SE ESPELHA
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **A lista é escrita à mão, e é de propósito.** Espelhar `ia/` inteiro traria
# notebooks, datasets e modelos de treino para dentro da imagem que o Railway
# constrói — centenas de megabytes que o job nunca abre. Cada arquivo aqui está
# porque **alguma linha do job o importa**, direta ou indiretamente.
#
# ⚠️ **O caminho de destino repete o de origem**, e isso não é enfeite: o motor do
# laboratório se importa por caminho absoluto (`jogos.jogo_damas.motor.regras_damas`).
# Achatar a estrutura obrigaria a editar os imports — e um arquivo editado deixa
# de ser byte-idêntico, que é justamente o que o cadeado prova.
#
# Quem garante que a lista está completa NÃO é esta lista: é o teste do backend
# que **importa** o motor a partir do espelho. Faltando um arquivo, ele quebra.

ARQUIVOS_ESPELHADOS: tuple[str, ...] = (
    # ── A cadeia de pacotes (arquivos vazios, mas sem eles nada importa) ──
    "jogos/__init__.py",
    "jogos/jogo_damas/__init__.py",
    "jogos/jogo_damas/motor/__init__.py",
    "jogos/jogo_damas/tablebase/__init__.py",
    "jogos/jogo_damas/treino/__init__.py",
    "nucleo/__init__.py",
    # ── O motor de damas (RF-DES-018) ──
    "jogos/jogo_damas/motor/avaliacao_damas.py",
    "jogos/jogo_damas/motor/avaliacao_treinada_damas.py",
    "jogos/jogo_damas/motor/busca_damas.py",
    "jogos/jogo_damas/motor/empates_por_historico_damas.py",
    "jogos/jogo_damas/motor/especificacao_captura_damas.py",
    "jogos/jogo_damas/motor/explicacao_de_recusa_damas.py",
    "jogos/jogo_damas/motor/notacao_algebrica_damas.py",
    "jogos/jogo_damas/motor/politica_dificuldade_damas.py",
    "jogos/jogo_damas/motor/regras_damas.py",
    "jogos/jogo_damas/motor/tabuleiro_damas.py",
    "jogos/jogo_damas/motor/zobrist_damas.py",
    # ── A base de finais: a BUSCA a importa, e sem ela o motor não carrega ──
    # ⚠️ Só o CÓDIGO entra. Os dados da base (9,5 MB de `.gz`) NÃO: o job calibra
    # posições de abertura e meio-jogo, e quem a quiser um dia acrescenta os
    # dados aqui pelo mesmo mecanismo.
    "jogos/jogo_damas/tablebase/carregar_base_damas.py",
    "jogos/jogo_damas/tablebase/empates_declarados_damas.py",
    "jogos/jogo_damas/tablebase/indice_damas.py",
    "jogos/jogo_damas/tablebase/retrograda_damas.py",
    # ── As janelas: a avaliação treinada as importa de `treino/` ──
    # Ela mora em `treino/` por história (dezoito arquivos já a importavam de
    # lá), não por pertencer ao treino. O comentário está no próprio arquivo.
    "jogos/jogo_damas/treino/janelas_damas.py",
    # ── O logger, que `retrograda_damas` usa ──
    "nucleo/log.py",
    # ── O contrato de damas e o seu manifesto (RF-DES-141/149) ──
    # O job LÊ o contrato em tempo de execução: é a declaração única dos
    # parâmetros de nível, e é ela que o motor consulta para saber o que é o
    # Sagaz. Sem o contrato dentro da imagem, o job não sabe jogar em nível
    # nenhum.
    "jogos/jogo_damas/contrato/__init__.py",
    "jogos/jogo_damas/contrato/contrato_damas.json",
    "jogos/jogo_damas/contrato/MANIFESTO_HASHES.json",
)


def _origem(relativo: str) -> Path:
    """Onde o arquivo vive no laboratório."""
    return RAIZ_LABORATORIO / relativo


def _destino(relativo: str) -> Path:
    """Onde a cópia vive no backend — mesma estrutura, outra raiz."""
    return ESPELHO / relativo


def _sha256(caminho: Path) -> str:
    """SHA-256 dos **bytes** do arquivo, sem interpretar nada.

    Bytes, e não texto: interpretar como texto reintroduziria a tradução de fim
    de linha que este mecanismo existe para tornar irrelevante.
    """
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def copiar() -> list[str]:
    """Copia todos os arquivos declarados e devolve os que mudaram.

    Usa `shutil.copyfile`, que copia **os bytes** e não os metadados — nada de
    horário de modificação viajando junto e produzindo diferença onde não há.
    """
    mudaram: list[str] = []
    for relativo in ARQUIVOS_ESPELHADOS:
        origem, destino = _origem(relativo), _destino(relativo)
        if not origem.exists():
            raise SystemExit(
                f"ORIGEM AUSENTE: {origem}\n"
                "O laboratório mudou de forma. Ajuste ARQUIVOS_ESPELHADOS antes "
                "de espelhar — copiar por adivinhação é pior que não copiar."
            )
        destino.parent.mkdir(parents=True, exist_ok=True)
        if not destino.exists() or destino.read_bytes() != origem.read_bytes():
            shutil.copyfile(origem, destino)
            mudaram.append(relativo)
    return mudaram


def montar_manifesto() -> dict:
    """O manifesto de hashes do espelho inteiro (RF-DES-143a).

    É o **nível de CI** da conferência: qualquer repositório, sozinho, confere as
    suas cópias contra estes valores. ⛔ Sem carimbo de hora — ele é regerado e
    comparado, e uma hora dentro faria o arquivo diferir de si mesmo sempre.
    """
    return {
        "versao_do_manifesto": VERSAO_DO_MANIFESTO,
        "sobre": (
            "SHA-256 de cada arquivo copiado do laboratório para dentro do "
            "backend. A fonte da verdade continua sendo o código em ia/ - esta é "
            "uma cópia autorizada, não a posse (RF-DES-148/149). O cadeado "
            "tests/unitarios/test_espelho_laboratorio.py confere estes valores "
            "SEM precisar do ia/ no disco, e por isso NUNCA pula."
        ),
        "origem": "ia/ (repositório arena-sagaz)",
        "como_atualizar": (
            "Não edite nada dentro de espelho_laboratorio/. Mexa no laboratório e "
            "rode, na máquina do dono: "
            ".venv\\\\Scripts\\\\python scripts\\\\espelhar_laboratorio.py"
        ),
        "arquivos": [
            {
                "caminho": relativo,
                "sha256": _sha256(_destino(relativo)),
                "tamanho_bytes": _destino(relativo).stat().st_size,
            }
            for relativo in ARQUIVOS_ESPELHADOS
        ],
    }


def escrever_manifesto() -> Path:
    """Grava o manifesto com fim de linha LF, em qualquer sistema.

    ⚠️ `newline=""` desliga a tradução do Python. No Windows, sem isso, cada
    quebra vira CR+LF e o arquivo passa a ter bytes diferentes em cada máquina —
    num arquivo cuja razão de existir é comparar bytes.
    """
    texto = json.dumps(montar_manifesto(), ensure_ascii=False, indent=2) + "\n"
    CAMINHO_DO_MANIFESTO.write_text(texto, encoding="utf-8", newline="")
    return CAMINHO_DO_MANIFESTO


def conferir() -> list[str]:
    """Compara o espelho com o laboratório e devolve as divergências.

    É o **nível local** da conferência (RF-DES-143a): só funciona onde o `ia/`
    está no disco. Quando ele não está, quem responde é o manifesto.
    """
    divergentes: list[str] = []
    for relativo in ARQUIVOS_ESPELHADOS:
        origem, destino = _origem(relativo), _destino(relativo)
        if not destino.exists():
            divergentes.append(f"{relativo}  (falta no espelho)")
        elif not origem.exists():
            divergentes.append(f"{relativo}  (falta no laboratório)")
        elif origem.read_bytes() != destino.read_bytes():
            divergentes.append(f"{relativo}  (bytes diferentes)")
    return divergentes


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Copia do laboratório para espelho_laboratorio/ e regrava o manifesto."
    )
    analisador.add_argument(
        "--conferir",
        action="store_true",
        help="só compara com o laboratório; não escreve nada",
    )
    args = analisador.parse_args()

    if not RAIZ_LABORATORIO.is_dir():
        raise SystemExit(
            f"LABORATÓRIO NÃO ENCONTRADO em {RAIZ_LABORATORIO}.\n"
            "Este script roda na máquina do dono, onde os três repositórios "
            "convivem. No CI, quem confere é o manifesto."
        )

    if args.conferir:
        divergentes = conferir()
        if divergentes:
            print("ESPELHO DIVERGENTE do laboratório:")
            for linha in divergentes:
                print(f"  {linha}")
            print("\nRode sem --conferir para atualizar.")
            return 1
        print(f"OK - os {len(ARQUIVOS_ESPELHADOS)} arquivos do espelho conferem.")
        return 0

    mudaram = copiar()
    escrever_manifesto()

    print(f"espelho_laboratorio/  -  {len(ARQUIVOS_ESPELHADOS)} arquivos")
    if mudaram:
        print(f"  {len(mudaram)} atualizado(s):")
        for relativo in mudaram:
            print(f"    {relativo}")
    else:
        print("  nada mudou (o manifesto foi regravado assim mesmo)")
    print(f"\nmanifesto: {CAMINHO_DO_MANIFESTO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
