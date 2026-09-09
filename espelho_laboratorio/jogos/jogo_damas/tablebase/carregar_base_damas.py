"""Ler do disco a base de finais que o construtor em Dart gravou.

Por que isto existe
-------------------
A base é construída em Dart (84× mais rápido que em Python — ver o §6d do plano)
e gravada em `dados/jogo_damas/<regulamento>_<peças>/`. Só que quem **consulta**
a base no laboratório é o Python: a arena, a auditoria de lance, e sobretudo a
busca, que precisa perguntar "esta posição já está resolvida?" no meio da
recursão.

Sem este módulo, usar a base em Python significava reconstruí-la — 19 minutos
para 5 peças, a cada vez. Com ele, é abrir arquivo.

O que fica na memória
---------------------
`BaseDeFinais` guarda os vetores em RAM. Para 4 peças isso é ~38 MB, o que é
tranquilo; para 5 peças completas são ~1,8 GB, o que já não é. Daí o parâmetro
`fatias`: dá para carregar **só as fatias que interessam** — o que também é
exatamente o que o app vai fazer, e por isso o formato é o mesmo (ver a decisão
6e do plano, sobre quanto da base viaja no APK).

⚠️ **Base parcial não quebra nada.** Fatia ausente faz `consultar` devolver
`None`, e quem chama trata isso como "não sei, busque normalmente". Confundir
"fora da base" com "empate" faria o motor achar que toda posição de meio-jogo
está equilibrada — é o erro que o tipo `int | None` existe para impedir.
"""
from __future__ import annotations

import json
from array import array
from pathlib import Path

from jogos.jogo_damas.motor.regras_damas import (
    ANGLO_AMERICANAS,
    BRASILEIRAS,
    Regulamento,
)
from jogos.jogo_damas.tablebase.indice_damas import Fatia, fatias_ate
from jogos.jogo_damas.tablebase.retrograda_damas import BaseDeFinais
from nucleo.log import obter_logger

log = obter_logger("jogos.jogo_damas.tablebase.carregar_base")

PASTA_PADRAO_DOS_DADOS = Path("dados/jogo_damas")
"""Relativa a `ia/`, como todo caminho padrão do laboratório.

`dados/` está **fora do Git** (é grande e regenerável) — o espelho é o Google
Drive. Se a pasta não existir, a mensagem de erro diz o comando que a recria.
"""

_REGULAMENTOS = {r.identificador: r for r in (BRASILEIRAS, ANGLO_AMERICANAS)}


def caminho_da_base(
    total_de_pecas: int = 4,
    regulamento: Regulamento = BRASILEIRAS,
    pasta: Path | None = None,
) -> Path:
    """Onde o construtor em Dart grava a base — a convenção, num lugar só."""
    raiz = PASTA_PADRAO_DOS_DADOS if pasta is None else Path(pasta)
    return raiz / f"{regulamento.identificador}_{total_de_pecas}"


def carregar_base(
    pasta: Path,
    fatias: list[Fatia] | None = None,
    com_distancias: bool = True,
) -> BaseDeFinais:
    """Lê o manifesto e os vetores de uma base gravada.

    Args:
        pasta: a pasta com `manifesto.json` e os `.bin` (ver `caminho_da_base`).
        fatias: quais fatias carregar. `None` = todas as do manifesto. Passar uma
            lista curta é o que permite trabalhar com a base de 5 peças sem
            1,8 GB de RAM — e é o mesmo recorte que o app fará.
        com_distancias: ler também `<fatia>.distancias.bin`. A distância só é
            necessária para as regras de empate declarado (arts. 97 a 100) e para
            "ganha em quantos lances"; a consulta de resultado não precisa dela,
            e não lê-la corta o consumo de memória pela metade.

    Returns:
        A `BaseDeFinais` pronta para `consultar`.

    Raises:
        FileNotFoundError: com o comando que reconstrói a base, porque `dados/`
            não está no Git e o erro mais provável é justamente ela não existir
            nesta máquina.
    """
    pasta = Path(pasta)
    manifesto_json = pasta / "manifesto.json"
    if not manifesto_json.exists():
        raise FileNotFoundError(
            f"não achei {manifesto_json}.\n"
            "A base fica em dados/, que está FORA do Git (espelho no Google "
            "Drive). Para reconstruí-la:\n"
            "  cd ia\\jogos\\jogo_damas\\motor_dart\n"
            "  dart compile exe bin/construir_base_damas.dart -o construir_base.exe\n"
            "  .\\construir_base.exe --pecas=4 "
            "--saida=..\\..\\..\\dados\\jogo_damas\\brasileira_4"
        )

    manifesto = json.loads(manifesto_json.read_text(encoding="utf-8"))
    regulamento = _REGULAMENTOS[manifesto["regulamento"]]
    base = BaseDeFinais(regulamento=regulamento)

    # As fatias vêm do manifesto por NOME; o objeto `Fatia` correspondente sai
    # de `fatias_ate`, que é a mesma função que a construção usou. Reconstruir a
    # fatia a partir do nome (dígito a dígito) seria uma segunda implementação
    # da mesma convenção — e duas implementações da mesma convenção é como se
    # perde a igualdade entre o que grava e o que lê.
    por_nome = {f.nome: f for f in fatias_ate(manifesto["total_de_pecas"])}
    pedidas = {f.nome for f in fatias} if fatias is not None else None

    carregadas = 0
    for entrada in manifesto["fatias"]:
        nome = entrada["fatia"]
        if pedidas is not None and nome not in pedidas:
            continue

        fatia = por_nome[nome]
        valores = bytearray((pasta / f"{nome}.valores.bin").read_bytes())
        if len(valores) != fatia.tamanho:
            raise ValueError(
                f"a fatia {nome} tem {len(valores)} bytes no disco e "
                f"{fatia.tamanho} índices na numeração — o arquivo foi gravado "
                "por outra versão da indexação"
            )

        distancias = None
        if com_distancias:
            arquivo = pasta / f"{nome}.distancias.bin"
            if arquivo.exists():
                # 'h' é int16 com sinal, que é o formato gravado pelo Dart
                # (Int16List). A distância cabe: a fatia mais funda medida tem
                # 108 camadas, e `SEM_DISTANCIA` é -1.
                distancias = array("h")
                distancias.frombytes(arquivo.read_bytes())

        base.guardar(fatia, valores, distancias)
        carregadas += 1

    log.info("base carregada de %s — %d fatias, %d posições",
             pasta, carregadas, base.total_de_posicoes)
    return base


def fatias_com_ate(total_de_pecas: int) -> list[Fatia]:
    """Atalho para "todas as fatias com no máximo N peças".

    Serve ao caso mais comum de carga parcial: ter a base de 5 peças no disco e
    querer só a de 4 na memória — que é exatamente o experimento que decide a
    etapa 6e (quanto da base viaja no app).
    """
    return fatias_ate(total_de_pecas)
