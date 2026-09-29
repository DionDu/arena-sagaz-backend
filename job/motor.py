"""A DIMENSAO DO MOTOR: tornar o `co_versao_motor` DECIFRAVEL (T049e).

═══════════════════════════════════════════════════════════════════════════
O PROBLEMA — e ele e o mesmo do perfil, um degrau abaixo
═══════════════════════════════════════════════════════════════════════════

`desafio.tb001_desafio.co_versao_motor` guarda `damas-dart-2f8e15cd`. Os oito
digitos sao o comeco de um SHA-256 da lista de hashes dos arquivos do motor
dentro do espelho — quer dizer: ⛔ **eles nao se invertem, e nada no banco diz de
que arquivos sairam.**

⚠️ **Compare com a irma `tb903_perfil_dificuldade`, porque e ela o argumento.**
O perfil e decifravel **sem o Git**: `js_perfil` traz os numeros, `co_arquivo` e
`co_sha256` dizem de onde eles vieram. O motor nao e decifravel de jeito nenhum.

A pergunta que fica sem resposta e concreta, e costuma ser feita meses depois:
*"este desafio foi medido com que motor?"* Hoje a unica forma de responder e
descobrir qual commit do backend estava no ar naquele dia, reconstruir o espelho
daquele commit e refazer a conta — e isso ⛔ **so funciona enquanto a formula for
a mesma**. No dia em que alguem mudar a funcao que deriva o resumo, **toda string
antiga fica irresolvivel para sempre**.

═══════════════════════════════════════════════════════════════════════════
⚠️ O PAR DE DIAGNOSTICO, QUE E O QUE DECIDE O FORMATO
═══════════════════════════════════════════════════════════════════════════

Existem **duas metades** da mesma informacao, e ate 11/09/2026 elas nao se
cruzavam:

    o aparelho reporta  →  `dart_1.4.0|rust_0.4.0`  (`partida.tb001_partida` e
                                                     `tb007_desafio_impedido`)
    o servidor guarda   →  `damas-dart-2f8e15cd`    (`desafio.tb001_desafio`)

Uma e versao semantica de dois motores; a outra e um hash de um terceiro. A
pergunta *"por que este desafio nao coube no aparelho desta pessoa?"* precisa das
duas metades, e ficava sem resposta exatamente quando alguem a fazia.

⛔ **E por isso o formato de `js_motores` NAO e livre**: e a **mesma lista de
registros** de `desafio_dia.tb007_desafio_impedido` — `[{co_jogo, co_motor,
co_versao}]`, sob a chave `motores`, com `"versao": 1`. As duas colunas se abrem
com o mesmo `jsonb_to_recordset` e se comparam sem tradutor no meio.

⚠️ **O que a lista do servidor diz, jogo a jogo** (a forma de 29/09/2026,
T095 — antes dela as damas declaravam `python` e o Pontinhos ⛔ declarava o Dart):

    damas      → `dart`              = o motor compilado, que escolhe o lance
                 `resumo_do_carimbo` = o SHA-256 dos fontes Dart, carimbado no
                                       executavel e identico no aplicativo
                 `contrato`          = `contrato_damas.json`, que o aplicativo
                                       carrega IGUAL
    pontinhos  → `dart`              = o motor compilado: tensor, politica,
                                       sorteador
                 `resumo_do_carimbo` = o mesmo cadeado, para o motor do Pontinhos
                 `tflite`            = os pesos que produzem a softmax
                 `codificacao`       = o contrato de codificacao, byte-identico
                                       no aplicativo

⚠️ **O contrato entra na lista de proposito, e o carimbo entrou depois.** Ate
25/09/2026 o servidor jogava com um port Python e o aparelho com Dart: duas
implementacoes **sem numero em comum**, e o unico terreno de comparacao era o
contrato que as duas obedecem. Hoje e o **mesmo codigo** nos dois lados, e por
isso a lista declara o `resumo_do_carimbo`: a comparacao deixou de ser indireta.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE ARQUIVO NAO INVENTA VERSAO NENHUMA
═══════════════════════════════════════════════════════════════════════════

Tudo o que vai para a linha e **derivado** do que esta no disco: o resumo sai de
`versao_do_motor()` de cada motor, a lista de arquivos sai de
`arquivos_do_motor()` **do mesmo modulo** que fez o resumo, e o `co_sha256` e o
do proprio `MANIFESTO_HASHES.json`.

⛔ **Reescrever aqui a lista de arquivos seria a segunda fonte da verdade** — e a
divergencia teria o pior sintoma possivel: a linha do banco afirmando que o
resumo saiu de um conjunto de arquivos, quando ele saiu de outro. Foi para
impedir isso que `arquivos_do_motor()` nasceu, extraida de dentro de
`versao_do_motor()` nos dois motores.

⚠️ **E o `co_sha256` do manifesto e o que liberta a decifracao da formula.** Com
ele na linha, decifrar deixa de depender de a funcao que deriva o resumo
continuar a mesma: os arquivos e os hashes estao ali, e o manifesto que os
declarava esta identificado.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from motores.damas import contrato_damas
from motores.damas import jogador_dart as jogador_dart_damas
from motores.pontinhos import jogador_dart_pontinhos
from motores.pontinhos import motor_pontinhos

#: A versao do formato de `js_motores` e de `js_arquivos`.
#:
#: ⚠️ **Obrigatoria, na mesma convencao de `js_chegada` e da `tb007`**: e ela que
#: permite mudar a forma da lista sem que quem le precise adivinhar qual esta
#: lendo.
VERSAO_DO_FORMATO = 1

#: Quantos digitos do resumo do motor Dart entram em `js_motores`.
#:
#: ⚠️ **Dezesseis, e a mesma largura do `.tflite` da linha de baixo** — sao
#: identificadores de diagnostico, e nao chaves: dezesseis digitos ja tornam a
#: colisao acidental impossivel na pratica e a linha continua legivel a olho nu.
#: O resumo inteiro tem 64, e e ele que o executavel carimba e a abertura do
#: processo confere; quem precisa dele por inteiro o tem no proprio binario.
DIGITOS_DO_RESUMO_DART = 16

#: O manifesto e UM so para os dois jogos — ele descreve o espelho inteiro.
#:
#: ⚠️ Lido daqui, e nao redeclarado: os dois motores ja apontam para o mesmo
#: arquivo, e um terceiro caminho escrito a mao envelheceria calado no dia em que
#: o espelho mudasse de lugar.
CAMINHO_DO_MANIFESTO: Path = contrato_damas.CAMINHO_DO_MANIFESTO


def _sha256_do_arquivo(caminho: Path) -> str:
    """O SHA-256 de um arquivo, em hexadecimal.

    ⚠️ Le em **bytes**, e nao como texto: ler como texto passaria pela traducao
    de fim de linha do Windows, e o hash descreveria uma coisa que nao esta no
    disco. E a mesma nota de `job/perfil.py`, pelo mesmo motivo.
    """
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _motores_das_damas() -> list[dict[str, str]]:
    """Os registros do jogador de damas, no vocabulario da `tb007`.

    O `co_versao` do `dart` e o resumo **inteiro** (`damas-dart-<8 hex>`), e nao
    so os oito digitos: assim a lista se le sozinha, sem voltar a coluna
    `co_versao_motor` da mesma linha.

    ⚠️ **O registro chamava-se `python` ate 29/09/2026 (T095)**, e o nome era
    verdade ate 25/09: era o port Python quem escolhia o lance. Desde o motor
    Dart, o Python das damas e **arbitro** — valida regras, ⛔ escolhe lance —, e
    um registro chamado `python` mandaria quem investigasse um lance divergente
    abrir o arquivo errado.

    ⚠️ **E o `resumo_do_carimbo` e a metade que de fato se compara com o
    aparelho.** O contrato ja era uma metade compartilhada (os dois lados o
    obedecem); este e mais forte: e o SHA-256 dos **proprios fontes Dart**, o
    mesmo numero que o executavel carimba, que a abertura do processo confere e
    que `paridade_motor_test.dart` exige igual no aplicativo. Com ele na linha, a
    pergunta *"o servidor e o aparelho rodaram o mesmo motor?"* se responde
    comparando dois hexadecimais.
    """
    return [
        {
            "co_jogo": "damas",
            "co_motor": "dart",
            "co_versao": contrato_damas.versao_do_motor(),
        },
        {
            "co_jogo": "damas",
            "co_motor": "resumo_do_carimbo",
            "co_versao": jogador_dart_damas.resumo_dos_fontes()[
                :DIGITOS_DO_RESUMO_DART
            ],
        },
        {
            "co_jogo": "damas",
            "co_motor": "contrato",
            "co_versao": contrato_damas.versao_do_contrato(),
        },
    ]


def _motores_do_pontinhos() -> list[dict[str, str]]:
    """Os registros do jogador do Pontinhos.

    ⚠️ O modelo e identificado pelo **SHA-256 do proprio `.tflite`** (16 digitos),
    e nao pelo nome do arquivo: o nome carrega a receita do treino e ja mudou
    varias vezes sem que os pesos mudassem — e o que decide o lance sao os pesos.

    ⚠️ **Sao QUATRO registros desde 29/09/2026 (T095), e cada um responde por uma
    peca do jogador**, que aqui e repartido entre dois processos:

        dart               quem monta o tensor, renormaliza, ordena, aplica a
                           politica e sorteia — o motor compilado
        resumo_do_carimbo  o SHA-256 dos fontes Dart, que o executavel carimba e
                           o aplicativo tem identico — a metade comparavel
        tflite             os pesos que produzem a softmax
        codificacao        o contrato que diz como o tabuleiro vira tensor

    ⛔ **Ate hoje a lista ⛔ mencionava o Dart**, embora fosse ele quem escolhesse
    o lance desde a T093: `js_motores` descrevia o modelo e o contrato, e o
    decisor ficava de fora. E a mesma familia do prefixo `pontinhos-py-` — um
    registro que envelheceu sem que nada denunciasse.

    Raises:
        FileNotFoundError: se nao houver `.tflite` no manifesto. ⛔ Falhar alto e
            o certo: sem o modelo nao ha jogador do Pontinhos, e gravar a linha
            assim mesmo descreveria um motor que nao existe.
    """
    arquivos = motor_pontinhos.arquivos_do_motor()
    modelo = next(
        (
            arquivo["sha256"]
            for arquivo in arquivos
            if arquivo["caminho"].endswith(".tflite")
        ),
        None,
    )
    if modelo is None:
        raise FileNotFoundError(
            "nenhum arquivo `.tflite` no manifesto do espelho. Rode, na maquina "
            "do dono:\n"
            "  .venv\\Scripts\\python scripts\\espelhar_laboratorio.py"
        )
    return [
        {
            "co_jogo": "pontinhos",
            "co_motor": "dart",
            "co_versao": motor_pontinhos.versao_do_motor(),
        },
        {
            "co_jogo": "pontinhos",
            "co_motor": "resumo_do_carimbo",
            "co_versao": jogador_dart_pontinhos.resumo_dos_fontes()[
                :DIGITOS_DO_RESUMO_DART
            ],
        },
        {"co_jogo": "pontinhos", "co_motor": "tflite", "co_versao": modelo[:16]},
        {
            "co_jogo": "pontinhos",
            "co_motor": "codificacao",
            "co_versao": str(motor_pontinhos.contrato_de_codificacao()["versao"]),
        },
    ]


def linhas_da_dimensao() -> list[dict[str, Any]]:
    """As linhas de `desafio.tb904_motor` dos motores vigentes — uma por jogo.

    Returns:
        Dicionarios prontos para o `INSERT`, com `co_versao_motor`, `co_jogo`,
        `js_motores`, `co_sha256` e `js_arquivos`.

    ⚠️ **E o JOB que grava estas linhas, nunca a migracao** — a mesma regra do
    perfil, e pelo mesmo motivo: uma migracao que soubesse o hash do motor
    estaria publicando por `INSERT` um fato que ela nao tem como conferir.

    ⚠️ **Consequencia operacional, e ela e desejada:** com a `fk002_motor` no
    lugar, o primeiro `INSERT` em `tb001_desafio` falha enquanto estas linhas nao
    existirem — depois de toda a geracao e toda a medicao terem sido feitas, que
    e a parte cara. Gravar isto custa milissegundos e roda no comeco.
    """
    sha_do_manifesto = _sha256_do_arquivo(CAMINHO_DO_MANIFESTO)

    por_jogo = {
        "damas": (
            contrato_damas.versao_do_motor(),
            contrato_damas.arquivos_do_motor(),
            _motores_das_damas(),
        ),
        "pontinhos": (
            motor_pontinhos.versao_do_motor(),
            motor_pontinhos.arquivos_do_motor(),
            _motores_do_pontinhos(),
        ),
    }

    linhas: list[dict[str, Any]] = []
    for co_jogo, (co_versao_motor, arquivos, motores) in por_jogo.items():
        linhas.append(
            {
                "co_versao_motor": co_versao_motor,
                "co_jogo": co_jogo,
                "js_motores": {"versao": VERSAO_DO_FORMATO, "motores": motores},
                "co_sha256": sha_do_manifesto,
                # ⚠️ A lista **inteira**, e nao uma amostra: e ela que permite
                # refazer a conta e chegar de volta ao `co_versao_motor` sem o
                # Git e sem a formula de hoje. Um cadeado faz exatamente isso em
                # `test_motor_decifravel.py`.
                "js_arquivos": {
                    "versao": VERSAO_DO_FORMATO,
                    "arquivos": [dict(arquivo) for arquivo in arquivos],
                },
            }
        )
    return linhas


def resumo() -> dict[str, Any]:
    """Um resumo legivel dos motores vigentes — para o log do job.

    ⚠️ Ele **nao** e o que se grava: o que se grava sao as linhas da dimensao.
    Este resumo existe para o log dizer, em uma linha, com que motores aquela
    execucao gerou e mediu.
    """
    return {
        linha["co_jogo"]: {
            "co_versao_motor": linha["co_versao_motor"],
            "nu_arquivos": len(linha["js_arquivos"]["arquivos"]),
        }
        for linha in linhas_da_dimensao()
    }
