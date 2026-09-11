"""PESCA moldes de damas nas posicoes de PARTIDAS REAIS, em vez de sortea-las.

═══════════════════════════════════════════════════════════════════════════
⚠️ POR QUE ESTE SCRIPT EXISTE — A IDEIA E DO DONO, E O BANCO DEU RAZAO A ELA
═══════════════════════════════════════════════════════════════════════════

Em 11/09/2026, depois de curar a primeira fila de verdade, o dono escreveu:

> *"Os desafios de coroar damas tem muitos lances agora, no entanto estao
> absurdamente faceis. E basicamente so seguir em linha reta com a peca ate o
> final, nao tem desafio algum."*

> *"Sera que nao deveriamos voltar aquela minha ideia? Voce olhar o banco de
> dados das partidas de pontinhos jogadas por humanos no App real e pescar de la
> desafios possiveis?"*

**A medida que fecha o caso**, tirada do `des` no mesmo dia:

    material medio da posicao        | nos MOLDES sorteados | em PARTIDAS REAIS
    ---------------------------------+----------------------+------------------
    posicao de coroar                |  6,0 pecas (sempre!) | 12,3 pecas
    posicao de captura de 3+ pecas    |  7,0 pecas (sempre!) | 17,6 pecas

⛔ **Os 330 moldes de `damas_coroar` tem EXATAMENTE 3 brancas e 3 pretas — todos
eles.** Nao e uma tendencia: e um parametro escrito a mao em
`cacar_moldes_damas.candidatas_para_coroar`, que sorteia a ponta de lanca em
5..12 e as pretas em 13..24. ⚠️ **As pretas ficam ATRAS da branca que vai coroar**
— elas andam para numeros maiores, e a coroacao branca e em 1..4. Nada podia
interceptar, em molde nenhum. O dono descreveu com precisao o que o codigo
construia.

**O que este script faz de diferente:** nao inventa posicao. Le posicoes que
**aconteceram** — `jogo_damas.tb002_jogada.co_fen_antes` guarda a FEN antes de
cada lance de cada partida — e as entrega a **mesma** peneira e a **mesma**
medicao da cacada. ⚠️ **A troca e so da FONTE**: `cacar_moldes_damas` ja separa
"de onde vem a candidata" (`CANDIDATAS`) de "ela presta?" (`_peneirar_uma` /
`_medir_uma`), e e por isso que pescar custa um arquivo novo em vez de uma
reescrita.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ISTO **NAO** RESOLVE
═══════════════════════════════════════════════════════════════════════════

Pescar entrega **posicao plausivel**, e nao **posicao dificil**. Quem diz se um
desafio e dificil continua sendo a regua (`job/regua.py`), medindo os mascotes.
⛔ A licao de 11/09 foi exatamente essa: trocar um criterio errado (distancia ate
o objetivo) por outro criterio errado nao conserta nada. Material alto e uma
**hipotese** de que a posicao tem oposicao — quem confirma e a medicao.

═══════════════════════════════════════════════════════════════════════════
COMO SE USA
═══════════════════════════════════════════════════════════════════════════

1. Tirar as posicoes do banco (somente leitura, ⛔ **sempre o `des`**):

    .venv\\Scripts\\python scripts\\consultar_des.py --json "SELECT d.co_fen_antes AS fen
      FROM jogo_damas.tb002_jogada d" > fens_reais.json

2. Pescar:

    .venv\\Scripts\\python -u scripts\\pescar_moldes_de_partidas.py fens_reais.json ^
        --tipo damas_coroar --minimo-pecas 10 --processos 14

⚠️ **`-u` importa**: sem ele o Windows segura a saida num buffer e a execucao
parece travada.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

# O script mora em `scripts/`, e importa `job/` e `motores/`, que sao irmaos dele.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows e cp1252; sem isto um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from job.espelho_de_damas import com_as_brancas_a_jogar  # noqa: E402

# ⚠️ **Importar da cacada, e nao copiar dela.** A peneira, a medicao, os
# orcamentos e o teto de lances tem de ser os MESMOS — um molde pescado com
# criterio diferente do sorteado produziria uma fila com duas qualidades, e
# ninguem saberia qual desafio veio de onde.
from scripts.cacar_moldes_damas import (  # noqa: E402
    MINIMO_DE_MODALIDADES,
    TIPOS,
    _mapear,
    _medir_uma,
    _peneirar_uma,
    processos_padrao,
)


def pecas_da_fen(fen: str) -> tuple[int, int]:
    """Quantas brancas e quantas pretas ha na posicao.

    A FEN de damas tem tres campos separados por `:` — de quem e a vez, as
    brancas e as pretas: `W:W7,11,14:B2,5,10`. O `[1:]` de cada campo pula a
    letra da cor; o `K` de uma dama fica colado na casa (`K31`) e nao atrapalha
    a contagem, porque aqui so se conta quantos itens ha.
    """
    campos = fen.split(":")
    brancas = [c for c in campos[1][1:].split(",") if c]
    pretas = [c for c in campos[2][1:].split(",") if c]
    return len(brancas), len(pretas)


def fileiras_ate_coroar(fen: str) -> int:
    """A quantos PASSOS de fileira esta a pedra branca mais adiantada.

    As 32 casas escuras sao numeradas de 1 a 32, quatro por fileira: a casa `c`
    esta na fileira `(c - 1) // 4`. As brancas coroam na fileira 0 (casas 1..4),
    e uma pedra anda **uma fileira por lance**. Entao este numero e o **piso
    absoluto** de lances para coroar — nenhuma posicao coroa em menos do que ele,
    por mais livre que o caminho esteja.

    ⚠️ **As damas (`K`) sao ignoradas de proposito:** peca ja coroada nao coroa de
    novo, e contar a dama como "a mais adiantada" faria uma posicao sem nenhuma
    pedra promovivel parecer a um passo do objetivo.

    ⚠️ **Isto NAO e um criterio de dificuldade — e aritmetica**, e a distincao
    importa: foi confundir as duas coisas que produziu os 330 moldes faceis de
    11/09/2026. Aqui o numero so serve para nao gastar dois minutos de Sagaz
    provando que uma peca a sete fileiras nao chega em seis lances.

    Returns:
        A menor distancia em fileiras, ou `99` se nao ha pedra branca alguma.
    """
    campo_branco = fen.split(":")[1][1:]
    distancias = [
        (int(casa) - 1) // 4
        for casa in campo_branco.split(",")
        if casa and not casa.startswith("K")
    ]
    return min(distancias) if distancias else 99


def carregar(caminho: Path) -> list[str]:
    """Le o JSON do `consultar_des.py` e devolve as FENs, normalizadas e sem repeticao.

    ⚠️ **Toda posicao sai com as BRANCAS a jogar.** Metade das posicoes reais tem
    a vez das pretas, e o acervo de moldes e de posicoes com as brancas na vez
    (`job/gerador.py` conta com isso). `com_as_brancas_a_jogar` espelha quando
    preciso — rotacao de 180 graus mais troca de cores —, o que preserva a
    posicao **e** o lado que resolve.

    ⚠️ **A deduplicacao vem DEPOIS do espelho**, de proposito: duas posicoes que
    so diferem pelo lado da vez viram a mesma candidata, e medir as duas seria
    pagar o dobro pela mesma resposta.
    """
    if caminho.suffix.lower() == ".csv":
        # ⚠️ `utf-8-sig` e nao `utf-8`: o Excel e o export do Postgres no Windows
        # escrevem um BOM no comeco, e sem isto a PRIMEIRA coluna se chamaria
        # `﻿fen` — o cabecalho parece certo na tela e o `linha["fen"]` falha.
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            dados: list = list(csv.DictReader(arquivo))
    else:
        dados = json.loads(caminho.read_text(encoding="utf-8"))

    vistas: dict[str, None] = {}  # dict e nao set: preserva a ordem de chegada
    for linha in dados:
        fen = linha["fen"] if isinstance(linha, dict) else linha
        if not fen:
            continue
        try:
            vistas.setdefault(com_as_brancas_a_jogar(fen), None)
        except Exception:  # noqa: BLE001 — FEN malformada no log nao derruba a pesca
            continue
    return list(vistas)


class Diario:
    """O caderno em disco: o que ja foi medido nao se mede de novo.

    ═══════════════════════════════════════════════════════════════════════
    ⚠️ POR QUE ISTO EXISTE
    ═══════════════════════════════════════════════════════════════════════

    A pescaria de captura multipla leva ~7 h. O dono pediu, com razao, que ela
    *"permita interromper e retomar, sem perder todo o trabalho"* — em sete horas
    acontece queda de energia, atualizacao do Windows e arrependimento.

    ⚠️ **O formato e JSONL — uma linha por posicao medida**, e nao um JSON unico.
    Um JSON so teria de ser reescrito inteiro a cada posicao (caro, e com janela
    de corrupcao a cada gravacao); no JSONL, uma queda no meio da escrita perde
    **a ultima linha** e nada mais. ⛔ A leitura ignora linha quebrada de
    proposito, em vez de falhar: perder a ultima posicao e barato, refazer sete
    horas nao e.

    ⚠️ **`flush()` a cada linha.** Sem ele o Python segura os dados num buffer de
    8 KB, e um `Ctrl+C` jogaria fora dezenas de posicoes ja calculadas — o
    trabalho estaria feito e o arquivo nao saberia.
    """

    def __init__(self, caminho: Path, assinatura: dict) -> None:
        """Abre o diario, conferindo que ele e da MESMA pescaria.

        Args:
            caminho: o arquivo `.jsonl`.
            assinatura: os parametros que definem esta pescaria (tipo, filtros,
                arquivo de origem).

        Raises:
            SystemExit: se o diario existente for de outra pescaria. ⛔ **Retomar
                com filtro diferente misturaria dois acervos** — metade das
                posicoes medidas com um criterio e metade com outro —, e o
                resultado pareceria normal.
        """
        self.caminho = caminho
        self.peneira: dict[str, object] = {}
        self.medicao: dict[str, list] = {}
        self.motivos: Counter[str] = Counter()

        if caminho.exists():
            self._ler(assinatura)

        # Abre em modo append: retomar acrescenta, ⛔ nunca sobrescreve — abrir em
        # `w` apagaria as sete horas anteriores sem dizer nada.
        vazio = not caminho.exists() or caminho.stat().st_size == 0
        # ⛔ **Se a sessao anterior morreu no meio de uma linha, ela nao terminou
        # em `\n`** — e o proximo registro grudaria nela, corrompendo tambem um
        # registro BOM. Um `\n` antes de tudo isola o lixo numa linha so.
        precisa_de_quebra = not vazio and not caminho.read_bytes().endswith(b"\n")

        self._arquivo = caminho.open("a", encoding="utf-8")
        if precisa_de_quebra:
            self._arquivo.write("\n")
            self._arquivo.flush()
        if vazio:
            self._escrever({"tipo_de_linha": "assinatura", **assinatura})

    def _ler(self, assinatura: dict) -> None:
        """Carrega o que ja foi feito, e confere a assinatura."""
        for numero, linha in enumerate(
            self.caminho.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not linha.strip():
                continue
            try:
                registro = json.loads(linha)
            except json.JSONDecodeError:
                # ⚠️ Quase sempre a ultima linha, cortada por uma queda. Avisa e
                # segue: e exatamente o caso para o qual o JSONL foi escolhido.
                print(f"  ⚠️ linha {numero} do diario esta quebrada; ignorada")
                continue

            tipo_de_linha = registro.get("tipo_de_linha")
            if tipo_de_linha == "assinatura":
                divergentes = [
                    f"{chave}: diario={registro.get(chave)!r} agora={valor!r}"
                    for chave, valor in assinatura.items()
                    if registro.get(chave) != valor
                ]
                if divergentes:
                    raise SystemExit(
                        f"⛔ o diario {self.caminho.name} e de OUTRA pescaria:\n    "
                        + "\n    ".join(divergentes)
                        + "\n   Apague-o para comecar do zero, ou use --diario com "
                        "outro nome."
                    )
            elif tipo_de_linha == "peneira":
                self.peneira[registro["fen"]] = registro["lance"]
                self.motivos.update(registro.get("motivos") or {})
            elif tipo_de_linha == "medicao":
                self.medicao[registro["fen"]] = registro["lances"]

    def _escrever(self, registro: dict) -> None:
        """Uma linha, e o disco na hora."""
        self._arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
        self._arquivo.flush()

    def anotar_peneira(self, fen: str, lance: object, motivos: dict) -> None:
        """Guarda o resultado da fase 1 para uma posicao."""
        self.peneira[fen] = lance
        self.motivos.update(motivos)
        self._escrever(
            {"tipo_de_linha": "peneira", "fen": fen, "lance": lance, "motivos": motivos}
        )

    def anotar_medicao(self, fen: str, lances: list) -> None:
        """Guarda o resultado da fase 2 para uma posicao."""
        self.medicao[fen] = lances
        self._escrever({"tipo_de_linha": "medicao", "fen": fen, "lances": lances})

    def fechar(self) -> None:
        """Fecha o arquivo. Chamado tambem quando a pescaria e interrompida."""
        self._arquivo.close()


def _distancias(lances: list[int]) -> str:
    """`[3, 3, 7]` vira `3L:2 7L:1` — quantos desafios de cada tamanho ja sairam.

    ⚠️ **E o indicador que mais importa durante a pescaria**, e foi o que o dono
    pediu: *"quantas ja sao elegiveis para cada um dos desafios"*. O acervo
    sorteado nao tinha NENHUM molde de captura acima de 4 lances; ver um `7L`
    aparecer na primeira hora diz, sem esperar as sete, que a pesca esta valendo.
    """
    if not lances:
        return "nenhum ainda"
    contagem = Counter(lances)
    return " ".join(f"{n}L:{contagem[n]}" for n in sorted(contagem))


def _resumo_da_peneira(diario: "Diario") -> str:
    """Quantas passaram, e com que tamanho de solucao.

    ⚠️ **A peneira ja sabe a distancia** — ela devolve em que lance o objetivo
    caiu, e nao um sim/nao. Entao o retrato do acervo aparece desde a primeira
    fase, horas antes de a medicao confirmar.
    """
    passaram = [v for v in diario.peneira.values() if v is not None]
    return f"— elegiveis {len(passaram)} | {_distancias(passaram)}"


def _resumo_da_medicao(diario: "Diario") -> str:
    """Quantos moldes fecharam, com que distancia e com quanto material."""
    distancias: list[int] = []
    material: list[int] = []
    for fen, lances in diario.medicao.items():
        validos = [n for n in lances if n is not None]
        if len(validos) >= MINIMO_DE_MODALIDADES:
            distancias.append(round(sum(validos) / len(validos)))
            material.append(sum(pecas_da_fen(fen)))
    media = f" | material {sum(material) / len(material):.1f}" if material else ""
    return f"— moldes {len(distancias)} | {_distancias(distancias)}{media}"


def _tempo(segundos: float) -> str:
    """`4530` vira `1h15m`. Numero de sete horas em segundos nao se le."""
    if segundos < 90:
        return f"{segundos:.0f}s"
    minutos = int(segundos // 60)
    if minutos < 90:
        return f"{minutos}m"
    return f"{minutos // 60}h{minutos % 60:02d}m"


def _andamento(
    nome: str, feitas: int, total: int, retomadas: int, relogio: float, extra: str
) -> str:
    """A linha de progresso, com previsao de termino.

    ⚠️ **A previsao usa so o que foi medido NESTA execucao** (`feitas -
    retomadas`): incluir as posicoes lidas do diario daria uma velocidade
    fantasiosa — elas vieram do disco, em microssegundos.
    """
    nesta_vez = feitas - retomadas
    decorrido = time.monotonic() - relogio
    if nesta_vez > 0 and feitas < total:
        falta = (total - feitas) * (decorrido / nesta_vez)
        previsao = f" — faltam ~{_tempo(falta)}"
    else:
        previsao = ""
    return f"  {nome} {feitas}/{total} ({100 * feitas // total}%) {extra}{previsao}"


def _rodar_fase(
    nome: str,
    funcao,
    pendentes: list[str],
    ja_feitas: int,
    total: int,
    args,
    parametros,
    anotar,
    resumo,
) -> None:
    """Roda uma fase em paralelo, anotando cada resultado no diario.

    ⚠️ **Anota ANTES de contar**, e nao depois: se a maquina cair entre uma coisa
    e outra, e melhor ter a posicao no diario e o numero na tela errado do que o
    contrario.
    """
    relogio = time.monotonic()
    feitas = ja_feitas
    for resultado in _mapear(
        funcao, [(f, args.tipo, parametros) for f in pendentes], args.processos
    ):
        anotar(resultado)
        feitas += 1
        # A cada 25 posicoes, e sempre na ultima: sete horas caladas parecem
        # travamento, e foi isso que o dono pediu para nao acontecer.
        if feitas % 25 == 0 or feitas == total:
            print(_andamento(nome, feitas, total, ja_feitas, relogio, resumo()), flush=True)


def main() -> int:
    """Pesca, peneira, mede e imprime — nesta ordem, com o tempo de cada fase."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivo", type=Path, help="JSON com as FENs (do consultar_des.py)")
    ap.add_argument("--tipo", default="damas_coroar", choices=sorted(TIPOS))
    ap.add_argument(
        "--minimo-pecas",
        type=int,
        default=0,
        help=(
            "descarta posicoes com menos pecas que isto. ⚠️ E uma HIPOTESE de "
            "oposicao, nao um criterio de dificuldade — quem decide e a medicao."
        ),
    )
    ap.add_argument(
        "--amostra",
        type=int,
        default=0,
        help="pesca so N posicoes (para uma sondagem rapida)",
    )
    ap.add_argument(
        "--alcancavel",
        type=int,
        default=0,
        help=(
            "so posicoes com uma pedra branca a ate N fileiras da coroacao. "
            "⚠️ Aritmetica, nao dificuldade: uma pedra a sete fileiras nao coroa "
            "em seis lances, e provar isso custa dois minutos de Sagaz por "
            "posicao. Use o numero de lances da janela do tipo."
        ),
    )
    ap.add_argument(
        "--embaralhar",
        action="store_true",
        help=(
            "sorteia a amostra em vez de pegar as N primeiras. ⚠️ As posicoes "
            "chegam na ordem das partidas, entao as primeiras sao todas ABERTURA "
            "— uma sondagem sem isto mede o comeco do jogo, e nao o acervo."
        ),
    )
    ap.add_argument("--processos", type=int, default=processos_padrao())
    ap.add_argument(
        "--diario",
        type=Path,
        default=None,
        help=(
            "onde guardar o andamento, para poder interromper e retomar. "
            "Padrao: `pescaria_<tipo>.jsonl` ao lado do CSV. ⚠️ Rodar o MESMO "
            "comando de novo continua de onde parou; apagar o arquivo recomeça."
        ),
    )
    ap.add_argument(
        "--bloco",
        action="store_true",
        help="imprime as aprovadas como um bloco Python, pronto para colar",
    )
    args = ap.parse_args()
    if args.diario is None:
        # Ao lado do CSV, com o tipo no nome: as duas pescarias (coroar e
        # captura) rodam no mesmo CSV e ⛔ nao podem dividir o mesmo diario.
        args.diario = args.arquivo.parent / f"pescaria_{args.tipo}.jsonl"

    parametros = TIPOS[args.tipo]
    candidatas = carregar(args.arquivo)
    print(f"posicoes reais, sem repeticao: {len(candidatas)}")

    if args.minimo_pecas:
        antes = len(candidatas)
        candidatas = [f for f in candidatas if sum(pecas_da_fen(f)) >= args.minimo_pecas]
        print(f"com {args.minimo_pecas}+ pecas: {len(candidatas)} (de {antes})")

    if args.alcancavel:
        antes = len(candidatas)
        candidatas = [f for f in candidatas if fileiras_ate_coroar(f) <= args.alcancavel]
        print(
            f"com pedra branca a {args.alcancavel} fileira(s) ou menos da coroacao: "
            f"{len(candidatas)} (de {antes})"
        )

    if args.embaralhar:
        # ⚠️ Semente fixa: a sondagem de amanha tem de olhar a MESMA amostra da de
        # hoje, senao um rendimento que mudou pode ser o criterio ou pode ser o
        # sorteio, e nao ha como saber qual.
        random.Random(20260911).shuffle(candidatas)

    if args.amostra:
        candidatas = candidatas[: args.amostra]
        print(f"⚠️ AMOSTRA: {len(candidatas)} posicoes")

    print(
        f"[{args.tipo}] processos: {args.processos} "
        f"(a maquina tem {os.cpu_count()} nucleos logicos)",
        flush=True,
    )

    # ── O diario: e ele que torna a pescaria retomavel ───────────────────────
    diario = Diario(
        args.diario,
        {
            "tipo": args.tipo,
            "arquivo": args.arquivo.name,
            "minimo_pecas": args.minimo_pecas,
            "alcancavel": args.alcancavel,
            "embaralhar": args.embaralhar,
            "amostra": args.amostra,
            "posicoes": len(candidatas),
        },
    )
    if diario.peneira or diario.medicao:
        print(
            f"↻ retomando de {args.diario.name}: "
            f"{len(diario.peneira)} peneiradas, {len(diario.medicao)} medidas"
        )

    try:
        # ── Fase 1: a peneira ────────────────────────────────────────────────
        pendentes = [f for f in candidatas if f not in diario.peneira]
        if pendentes:
            _rodar_fase(
                "peneira",
                _peneirar_uma,
                pendentes,
                len(candidatas) - len(pendentes),
                len(candidatas),
                args,
                parametros,
                anotar=lambda r: diario.anotar_peneira(r[0], r[1], r[2]),
                resumo=lambda: _resumo_da_peneira(diario),
            )

        aprovadas = [f for f in candidatas if diario.peneira.get(f) is not None]
        print(f"peneira: {len(aprovadas)} de {len(candidatas)}")
        for causa, quantas in diario.motivos.most_common(8):
            print(f"    {causa}: {quantas}")

        if not aprovadas:
            print("⛔ nenhuma posicao real resolve este objetivo dentro da janela.")
            return 1

        # ── Fase 2: a medicao nas quatro modalidades ─────────────────────────
        pendentes = [f for f in aprovadas if f not in diario.medicao]
        if pendentes:
            _rodar_fase(
                "medicao",
                _medir_uma,
                pendentes,
                len(aprovadas) - len(pendentes),
                len(aprovadas),
                args,
                parametros,
                anotar=lambda r: diario.anotar_medicao(r[0], r[1]),
                resumo=lambda: _resumo_da_medicao(diario),
            )
    except KeyboardInterrupt:
        # ⚠️ Sai limpo e diz como voltar. Sem esta mensagem, um Ctrl+C deixaria a
        # impressao de que as horas ja rodadas foram perdidas — e elas nao foram.
        print(
            f"\n⚠️ interrompido. Nada se perdeu: {len(diario.peneira)} peneiradas e "
            f"{len(diario.medicao)} medidas estao em {args.diario}.\n"
            "   Rode o MESMO comando para continuar de onde parou."
        )
        return 130
    finally:
        diario.fechar()

    bons = sorted(
        (
            (len(validos), sum(validos) / len(validos), fen)
            for fen in aprovadas
            if (validos := [n for n in diario.medicao.get(fen, []) if n is not None])
            and len(validos) >= MINIMO_DE_MODALIDADES
        ),
        key=lambda t: (-t[0], -t[1]),
    )
    print(f"medicao: {len(bons)} moldes")

    # ── O retrato: material e distancia, que e o que se quer comparar ────────
    if bons:
        material = [sum(pecas_da_fen(f)) for _, _, f in bons]
        print(
            f"material dos aprovados: media {sum(material) / len(material):.1f} "
            f"| min {min(material)} | max {max(material)}"
        )
        distancia: Counter[int] = Counter(round(m) for _, m, _ in bons)
        print("distancia ate o objetivo (lance medio):")
        for lance in sorted(distancia):
            print(f"    {lance} lances: {distancia[lance]}")

    if args.bloco:
        print("\n# ── colar em job/tipos_de_desafio.py ──")
        for _quantas, _media, fen in bons:
            print(f'    "{fen}",')
    return 0


if __name__ == "__main__":
    # ⚠️ Obrigatorio no Windows: `multiprocessing` usa `spawn`, e cada processo
    # filho **reimporta este modulo**. Sem a guarda, cada filho chamaria `main()`
    # de novo e a pesca se multiplicaria sozinha.
    raise SystemExit(main())
