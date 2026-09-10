"""O PERFIL DE DIFICULDADE: com que numeros a regua foi medida (T035).

═══════════════════════════════════════════════════════════════════════════
O PROBLEMA QUE ELE RESOLVE
═══════════════════════════════════════════════════════════════════════════

*"A Pita resolve este desafio em 14 de 20 execucoes"* e uma frase que **deixa de
ser verdade sozinha**. Os numeros que definem a Pita — taxa de erro, teto de nos,
temperatura da CNN, tempo de pensar — sao afinados de tempos em tempos, e quando
mudam, a medicao antiga nao vale mais como aprovacao. ⚠️ **E nada no banco muda.**

O carimbo `co_versao_perfil` e o que permite descobrir isso depois.

═══════════════════════════════════════════════════════════════════════════
⚠️ ESTE ARQUIVO NAO INVENTA NUMERO NENHUM — E ISSO E A DECISAO
═══════════════════════════════════════════════════════════════════════════

Os numeros de dificuldade ja existem, e tem dono:

    damas      → `espelho_laboratorio/.../contrato_damas.json`
    Pontinhos  → `espelho_laboratorio/contrato_dificuldade_pontinhos.json`

⛔ **Um perfil com os numeros escritos de novo seria uma SEGUNDA fonte da
verdade** — exatamente o que os contratos existem para impedir. As duas
divergiriam no primeiro ajuste, e a que estivesse errada mandaria no job.

Entao o perfil e um **carimbo**, e nao uma tabela de parametros: ele le os
contratos vigentes, tira o SHA-256 de cada um e monta a linha que vai para
`desafio.tb903_perfil_dificuldade`. O `js_perfil` de cada mascote traz os numeros
**extraidos** dos contratos, para a linha ser interpretavel meses depois sem
precisar descobrir qual commit estava no ar.

⚠️ **A versao sai dos HASHES, e nao de um numero a mao** — a mesma disciplina de
`co_versao_motor`. Um `perfil-2026-09` escrito a mao envelheceria calado: alguem
afina a Pita, esquece de subir a versao, e as medicoes novas ficam
indistinguiveis das velhas.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from motores.damas import contrato_damas
from motores.nucleo.papeis import NivelDeMotor
from motores.pontinhos import politica

#: Os quatro mascotes e o degrau de cada um.
#:
#: ⚠️ **Sagaz e o degrau; Magno e o personagem.** Os dois vocabularios convivem no
#: projeto desde as damas.
NIVEL_POR_PERSONAGEM = {
    "cacau": NivelDeMotor.CACAU,
    "pita": NivelDeMotor.PITA,
    "tex": NivelDeMotor.TEX,
    "magno": NivelDeMotor.SAGAZ,
}


def _sha256(caminho: Path) -> str:
    """O SHA-256 de um arquivo, em hexadecimal.

    ⚠️ Le em **bytes**: e o arquivo que se mede, nao o texto. Ler como texto
    passaria pela traducao de fim de linha do Windows, e o hash descreveria uma
    coisa que nao esta no disco — o defeito que o manifesto do contrato de damas
    pegou no dia em que nasceu.
    """
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def versao_vigente() -> str:
    """A versao do perfil, derivada dos hashes dos contratos.

    Formato: `perfil-<8 hex>`. Os oito digitos sao o comeco do SHA-256 da
    concatenacao dos hashes dos dois contratos, em ordem estavel.

    ⚠️ **Deriva, e nao se digita.** Um numero a mao envelhece calado: alguem
    afina a Pita, esquece de subir a versao, e as medicoes novas ficam
    indistinguiveis das velhas no banco. E a mesma armadilha que
    `co_versao_motor` ja documenta, aplicada aos numeros de dificuldade.
    """
    partes = []
    for caminho in sorted(_contratos().values()):
        partes.append(_sha256(caminho))
    digerido = hashlib.sha256("".join(partes).encode("utf-8")).hexdigest()
    return f"perfil-{digerido[:8]}"


def _contratos() -> dict[str, Path]:
    """De onde saem os numeros de cada jogo."""
    return {
        "damas": contrato_damas.CAMINHO_DO_CONTRATO,
        "pontinhos": politica.CAMINHO_DO_CONTRATO,
    }


def _numeros_das_damas(nivel: NivelDeMotor) -> dict[str, Any]:
    """Os parametros daquele degrau, lidos do contrato de damas.

    ⚠️ Sao **copiados** para o `js_perfil` da linha, e nao referenciados: a linha
    precisa ser legivel daqui a um ano sem o contrato daquele dia na mao. Copia
    para *explicar* nao e segunda fonte da verdade — quem *roda* continua sendo o
    contrato, e o hash ao lado prova qual foi.
    """
    parametros = contrato_damas.parametros_do_nivel(nivel)
    # `dataclasses.asdict` nao serve aqui porque `ParametrosDeNivel` pode conter
    # tipos nao serializaveis; a extracao explicita tambem documenta o que entra.
    return {
        campo: getattr(parametros, campo)
        for campo in dir(parametros)
        if not campo.startswith("_") and not callable(getattr(parametros, campo))
    }


def _numeros_do_pontinhos(nivel: NivelDeMotor) -> dict[str, Any]:
    """Os parametros daquele degrau, lidos do contrato de dificuldade."""
    parametros = politica.parametros_do_nivel(nivel)
    return {
        campo: getattr(parametros, campo)
        for campo in dir(parametros)
        if not campo.startswith("_") and not callable(getattr(parametros, campo))
    }


def linhas_da_dimensao() -> list[dict[str, Any]]:
    """As linhas de `desafio.tb903_perfil_dificuldade` do perfil vigente.

    Uma por `(perfil, jogo, mascote)` — oito no total, com dois jogos.

    ⚠️ **E o JOB que grava estas linhas, nunca a migracao.** Uma migracao que
    soubesse a taxa de erro da Cacau estaria publicando calibracao por `INSERT`,
    e o `data-model.md` diz isso com todas as letras.

    ⚠️ **Consequencia operacional, e ela e desejada:** o primeiro `INSERT` em
    `tb001_desafio` falha enquanto estas linhas nao existirem — a FK composta
    `fk001_perfil` recusa. Desafio medido com um perfil que ninguem declarou nao
    entra.
    """
    versao = versao_vigente()
    contratos = _contratos()
    numeros = {"damas": _numeros_das_damas, "pontinhos": _numeros_do_pontinhos}

    linhas: list[dict[str, Any]] = []
    for co_jogo, caminho in contratos.items():
        # O caminho gravado e **relativo a raiz do repositorio**: um caminho
        # absoluto descreveria a maquina de quem rodou, e nao o arquivo.
        relativo = str(caminho).replace("\\", "/")
        if "espelho_laboratorio" in relativo:
            relativo = "espelho_laboratorio" + relativo.split("espelho_laboratorio", 1)[1]

        for co_personagem, nivel in NIVEL_POR_PERSONAGEM.items():
            linhas.append(
                {
                    "co_versao_perfil": versao,
                    "co_jogo": co_jogo,
                    "co_personagem": co_personagem,
                    "js_perfil": numeros[co_jogo](nivel),
                    "co_arquivo": relativo,
                    "co_sha256": _sha256(caminho),
                }
            )
    return linhas


def resumo() -> dict[str, Any]:
    """Um resumo legivel do perfil vigente — para log e para o painel.

    ⚠️ Ele **nao** e o que se grava: o que se grava sao as linhas da dimensao.
    Este resumo existe para o log do job dizer, em uma linha, com que numeros
    aquela execucao mediu.
    """
    return {
        "co_versao_perfil": versao_vigente(),
        "contratos": {
            co_jogo: {"co_arquivo": caminho.name, "co_sha256": _sha256(caminho)[:16]}
            for co_jogo, caminho in _contratos().items()
        },
        "nu_linhas": len(linhas_da_dimensao()),
    }
