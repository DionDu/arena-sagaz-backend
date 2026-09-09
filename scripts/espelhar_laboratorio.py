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

⚠️ Ele **precisa do `ia/` e do `arena-sagaz-frontend/` no disco**, então roda na
máquina do dono, nunca no CI. O CI usa o outro lado do mecanismo: o manifesto,
que viaja junto com a cópia.

⚠️ **Duas origens, e não uma** (ver ARQUIVOS_DO_APP): o motor de damas vem do
laboratório; o contrato de dificuldade do Pontinhos vem do **aplicativo**, porque
é lá que a política dele vive (R-20).
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
RAIZ_APP = RAIZ_ECOSSISTEMA / "arena-sagaz-frontend"

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
    # ── O motor do Pontinhos: as REGRAS e a CODIFICAÇÃO ──
    # ⛔ Nada aqui é reimplementado no backend (RF-DES-018b). A extração dos 12
    # canais tem BFS no grafo dual das caixas e é justamente o tipo de código que
    # uma segunda escrita erraria em silêncio: o tensor sairia plausível, a CNN
    # responderia, e o adversário do desafio seria outro.
    "jogos/jogo_pontinhos/__init__.py",
    "jogos/jogo_pontinhos/motor/__init__.py",
    "jogos/jogo_pontinhos/motor/tabuleiro_pontinhos.py",
    "jogos/jogo_pontinhos/motor/analisador_estrutural_pontinhos.py",
    # ── O contrato de damas e o seu manifesto (RF-DES-141/149) ──
    # O job LÊ o contrato em tempo de execução: é a declaração única dos
    # parâmetros de nível, e é ela que o motor consulta para saber o que é o
    # Sagaz. Sem o contrato dentro da imagem, o job não sabe jogar em nível
    # nenhum.
    "jogos/jogo_damas/contrato/__init__.py",
    "jogos/jogo_damas/contrato/contrato_damas.json",
    "jogos/jogo_damas/contrato/MANIFESTO_HASHES.json",
)


# ═══════════════════════════════════════════════════════════════════════════
# O QUE VEM DO APLICATIVO, E NÃO DO LABORATÓRIO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **A fonte da verdade de cada jogo está num lugar diferente, e isso é
# deliberado** (R-20). No damas, a política de dificuldade vive no Python do
# laboratório e o contrato é **gerado** dela. No Pontinhos, ela vive em **Dart**,
# no enum `Dificuldade` de `lib/modulos/jogos/pontinhos/logica/modelos.dart` — o
# aplicativo é a origem, e o contrato é a declaração dela.
#
# Então o espelho tem duas origens. ⛔ Não "uniformize": fingir que o Pontinhos
# vem do laboratório criaria uma segunda fonte de números de dificuldade, que é
# exatamente o que o contrato existe para impedir.
#
# ⚠️ Estes vão para a **raiz do espelho**, e não para dentro de `jogos/`: aquela
# subárvore é a estrutura de pacotes Python do laboratório, e o motor se importa
# por caminho absoluto dentro dela. Um JSON do app ali dentro seria mentira sobre
# de onde ele veio.

ARQUIVOS_DO_APP: tuple[tuple[str, str], ...] = (
    (
        "assets/jogos/pontinhos/contrato_dificuldade_pontinhos.json",
        "contrato_dificuldade_pontinhos.json",
    ),
    # ── A CNN do Pontinhos: os MESMOS arquivos que vão no aparelho ──
    #
    # ⚠️ RF-DES-018b não diz "um modelo equivalente": diz **o mesmo**. O job tem
    # de enfrentar o adversário que a pessoa enfrenta, e um `.tflite` diferente
    # — ainda que treinado igual — daria outro jogador.
    #
    # ⚠️ São 19,8 MB entrando no Git, e é o preço declarado de RF-DES-148: o
    # Railway constrói a imagem a partir deste repositório, e o que não estiver
    # aqui dentro não existe na nuvem.
    (
        "assets/jogos/pontinhos/modelos/"
        "pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite",
        "modelos/"
        "pontinhos_pequeno_cnn_12canais_boxnetv4_oraculo_exato_refinamento2_8p3M.tflite",
    ),
    # O mapeamento diz qual neurônio de saída é qual traço. ⚠️ A ordem é a
    # varredura canônica da matriz, que INTERCALA H_ e V_; a ordem alfabética
    # inutilizaria 28 das 31 predições, e já inutilizou uma vez.
    (
        "assets/jogos/pontinhos/ia_mappings/mapeamento_pequeno.json",
        "ia_mappings/mapeamento_pequeno.json",
    ),
    # O contrato de codificação: a fonte única sobre como o tabuleiro vira
    # tensor. ⚠️ **Este arquivo tem o SHA-256 travado no CI**, e é conferido
    # contra a cópia da API — a que vive em `gerador_dados/`. A cópia daqui é uma
    # terceira, dentro do espelho, e o manifesto é quem a trava.
    (
        "assets/jogos/pontinhos/contrato_codificacao_pontinhos.json",
        "contrato_codificacao_pontinhos.json",
    ),
)
"""Pares `(caminho no frontend, caminho dentro do espelho)`."""


def _origem(relativo: str) -> Path:
    """Onde o arquivo vive no laboratório."""
    return RAIZ_LABORATORIO / relativo


def _destino(relativo: str) -> Path:
    """Onde a cópia vive no backend — mesma estrutura, outra raiz."""
    return ESPELHO / relativo


def _todos_os_pares() -> list[tuple[Path, Path, str]]:
    """Todos os arquivos espelhados: `(origem, destino, caminho no espelho)`.

    Junta as duas origens numa lista só, para que copiar, conferir e manifestar
    percorram exatamente o mesmo conjunto. ⚠️ Três funções percorrendo listas
    separadas é como um arquivo acaba copiado e fora do manifesto — e o cadeado
    do outro lado não teria o que conferir.
    """
    pares = [(_origem(r), _destino(r), r) for r in ARQUIVOS_ESPELHADOS]
    pares += [(RAIZ_APP / o, _destino(d), d) for o, d in ARQUIVOS_DO_APP]
    return pares


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
    for origem, destino, relativo in _todos_os_pares():
        if not origem.exists():
            raise SystemExit(
                f"ORIGEM AUSENTE: {origem}\n"
                "A origem mudou de forma. Ajuste ARQUIVOS_ESPELHADOS ou "
                "ARQUIVOS_DO_APP antes de espelhar — copiar por adivinhação é "
                "pior que não copiar."
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
        "origens": [
            "ia/ (repositório arena-sagaz) - o motor de damas e o contrato dele",
            "arena-sagaz-frontend/ - o contrato de dificuldade do Pontinhos, cuja fonte da verdade é o Dart do aplicativo (R-20)",
        ],
        "como_atualizar": (
            "Não edite nada dentro de espelho_laboratorio/. Mexa no laboratório e "
            "rode, na máquina do dono: "
            ".venv\\\\Scripts\\\\python scripts\\\\espelhar_laboratorio.py"
        ),
        "arquivos": [
            {
                "caminho": relativo,
                "sha256": _sha256(destino),
                "tamanho_bytes": destino.stat().st_size,
            }
            for _, destino, relativo in _todos_os_pares()
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
    for origem, destino, relativo in _todos_os_pares():
        if not destino.exists():
            divergentes.append(f"{relativo}  (falta no espelho)")
        elif not origem.exists():
            divergentes.append(f"{relativo}  (falta na origem: {origem})")
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

    for nome, raiz in (("LABORATÓRIO", RAIZ_LABORATORIO), ("APLICATIVO", RAIZ_APP)):
        if not raiz.is_dir():
            raise SystemExit(
                f"{nome} NÃO ENCONTRADO em {raiz}.\n"
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
        print(f"OK - os {len(_todos_os_pares())} arquivos do espelho conferem.")
        return 0

    mudaram = copiar()
    escrever_manifesto()

    print(f"espelho_laboratorio/  -  {len(_todos_os_pares())} arquivos")
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
