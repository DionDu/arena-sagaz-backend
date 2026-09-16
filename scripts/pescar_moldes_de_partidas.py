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
import io
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

from job import editorial as editorial_mod  # noqa: E402
from job.espelho_de_damas import com_as_brancas_a_jogar  # noqa: E402

# ⚠️ **Importar da cacada, e nao copiar dela.** A peneira, a medicao, os
# orcamentos e o teto de lances tem de ser os MESMOS — um molde pescado com
# criterio diferente do sorteado produziria uma fila com duas qualidades, e
# ninguem saberia qual desafio veio de onde.
from job.moldes_de_damas import MODALIDADES  # noqa: E402
from scripts.cacar_moldes_damas import (  # noqa: E402
    MINIMO_DE_MODALIDADES,
    NOS_DA_MEDICAO,
    NOS_DA_PENEIRA,
    SEGUNDOS_DA_MEDICAO,
    SEGUNDOS_DA_PENEIRA,
    TIPOS,
    MotivoDeDescarte,
    parametros_do_tipo,
    teto_do_tipo,
    resolve_varios_alvos,
    _mapear,
    processos_padrao,
)

# ═══════════════════════════════════════════════════════════════════════════
# AS DUAS FASES, COM VARIOS ALVOS NA MESMA BUSCA
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **Precisam ser funcoes de MODULO** (e nao locais nem `lambda`): no Windows o
# `multiprocessing` usa `spawn`, que re-importa este arquivo em cada processo
# novo e localiza a funcao pelo nome. Uma closure nao sobrevive a isso.
#
# ⚠️ **E a tarefa leva os alvos junto**, e nao um alvo so — porque o ganho desta
# versao e exatamente esse: uma fita responde por todos. Ver
# `cacar_moldes_damas.resolve_varios_alvos` para o porque.


def _peneirar_varios(tarefa: tuple[str, str, dict]) -> tuple[str, dict, dict]:
    """Fase 1 com varios alvos. Devolve `(fen, {alvo: lance_ou_None}, motivos)`.

    ⚠️ **Os motivos voltam no retorno, e nao num contador compartilhado.** Cada
    processo tem a sua memoria; um `Counter` global seria incrementado em catorze
    copias e nenhuma delas chegaria ao pai.
    """
    fen, co_tipo, (alvos, teto) = tarefa
    motivos = MotivoDeDescarte()
    achados = resolve_varios_alvos(
        fen,
        co_tipo,
        alvos,
        "brasileira",
        nos=NOS_DA_PENEIRA,
        segundos=SEGUNDOS_DA_PENEIRA,
        motivos=motivos,
        teto=teto,
    )
    return fen, achados, dict(motivos)


def _medir_varios(tarefa: tuple[str, str, dict]) -> tuple[str, dict, dict]:
    """Fase 2 com varios alvos, nas quatro modalidades.

    Devolve `(fen, {alvo: [lance_por_modalidade]}, motivos)`. ⚠️ Uma modalidade
    que nao cumpre entra como `None`, e e o `MINIMO_DE_MODALIDADES` que decide se
    o molde presta — um molde nao precisa servir aos quatro regulamentos.
    """
    fen, co_tipo, (alvos, teto) = tarefa
    motivos = MotivoDeDescarte()
    por_alvo: dict[str, list] = {nome: [] for nome in alvos}
    for modalidade in MODALIDADES:
        achados = resolve_varios_alvos(
            fen,
            co_tipo,
            alvos,
            modalidade,
            nos=NOS_DA_MEDICAO,
            segundos=SEGUNDOS_DA_MEDICAO,
            motivos=motivos,
            teto=teto,
        )
        for nome, lance in achados.items():
            por_alvo[nome].append(lance)
    return fen, por_alvo, dict(motivos)


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


#: Os comecos de arquivo que denunciam a codificacao, do mais longo para o mais
#: curto. ⚠️ **A ordem importa:** o BOM de UTF-8 (`EF BB BF`) e de UTF-32LE
#: (`FF FE 00 00`) comecam com bytes que tambem abrem BOMs mais curtos, e testar
#: o curto primeiro casaria com o arquivo errado.
BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def _texto_do_arquivo(caminho: Path) -> str:
    """Le o arquivo seja qual for a codificacao com que o Windows o escreveu.

    ⛔ **ESTE SCRIPT JA TROPECOU NISTO DUAS VEZES, e a segunda custou uma
    pescaria** (14/09/2026). O redirecionamento do PowerShell (`>`) nao escreve
    UTF-8: dependendo da versao ele escreve **UTF-16LE com BOM**, e o
    `read_text(encoding="utf-8")` morre no primeiro byte com
    `'utf-8' codec can't decode byte 0xff in position 0`.

    ⚠️ **E o erro chega tarde e longe da causa.** Quem o le pensa em dado
    corrompido ou em FEN malformada; o arquivo esta perfeito, e o que esta errado
    e a suposicao de quem o abriu. A primeira vez foi no CSV, com o BOM de UTF-8:
    a primeira coluna passava a se chamar `﻿fen`, o cabecalho parecia certo na
    tela, e o `linha["fen"]` falhava.

    ✅ **A cura e ler os primeiros bytes e perguntar ao arquivo**, em vez de
    exigir que quem o gerou tenha acertado a codificacao — sao duas linhas, e
    valem para os dois formatos e para qualquer jeito de gerar o arquivo.

    Args:
        caminho: o JSON ou CSV com as FENs.

    Returns:
        O conteudo em texto, **sem o BOM**: ele nao e caractere, e um rotulo de
        codificacao. Deixa-lo passar poria um `﻿` invisivel na primeira chave
        do JSON ou no primeiro cabecalho do CSV.
    """
    bruto = caminho.read_bytes()
    for marca, codificacao in BOMS:
        if bruto.startswith(marca):
            # ⚠️ `utf-8-sig`, `utf-16-le` e companhia ja descartam o BOM sozinhos
            # quando ele casa com a codificacao nomeada.
            return bruto.decode(codificacao).lstrip("﻿")
    # Sem BOM: UTF-8 e a aposta certa (e o que o `consultar_des.py` escreve).
    return bruto.decode("utf-8")


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
    texto = _texto_do_arquivo(caminho)
    if caminho.suffix.lower() == ".csv":
        dados: list = list(csv.DictReader(io.StringIO(texto, newline="")))
    else:
        dados = json.loads(texto)

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


def _nome_do_alvo(alvo: dict, padrao: dict) -> str:
    """Um rotulo curto para o alvo, feito do que ele tem de DIFERENTE do padrao.

    `{damas: 2, lances: 10}` contra o padrao `{damas: 1, lances: 6}` vira
    `damas=2,lances=10`. ⚠️ **O nome vai para o diario e para a tela**, entao ele
    tem de ser estavel: sai ordenado por chave, e nao pela ordem em que o dono
    escreveu o JSON — senao retomar a pescaria com as chaves invertidas pareceria
    outro alvo.

    ⛔ Para VARIOS alvos use `_nomear_alvos`, que compara os alvos ENTRE SI.
    """
    diferentes = {k: v for k, v in sorted(alvo.items()) if padrao.get(k) != v}
    if not diferentes:
        return ",".join(f"{k}={v}" for k, v in sorted(alvo.items()))
    return ",".join(f"{k}={v}" for k, v in diferentes.items())


def _nomear_alvos(lista: list[dict], padrao: dict) -> dict[str, dict]:
    """Nomeia cada alvo pelo que o distingue **dos outros alvos**.

    ⛔ **E nao pelo que o distingue do padrao**, que foi a primeira versao e saiu
    confusa: com o padrao `{damas: 1, lances: 6}`, o alvo `{damas: 1, lances: 10}`
    virava `lances=10` — sem a palavra `damas` — ao lado de `damas=2,lances=10` e
    `damas=3,lances=10`. ⚠️ O leitor tinha de saber o padrao de cor para entender
    que o primeiro era "uma dama".

    ⚠️ **Um alvo so continua nomeado contra o padrao**, que e o rotulo mais curto
    possivel quando nao ha com quem comparar.
    """
    if len(lista) == 1:
        alvo = {**padrao, **lista[0]}
        return {_nome_do_alvo(alvo, padrao): alvo}

    completos = [{**padrao, **item} for item in lista]
    # As chaves que NAO sao iguais em todos os alvos: sao elas que distinguem.
    variaveis = sorted(
        {
            chave
            for chave in {c for alvo in completos for c in alvo}
            if len({alvo.get(chave) for alvo in completos}) > 1
        }
    )
    # ⚠️ Alvos identicos entre si nao tem o que variar; cai no nome contra o
    # padrao, e o `dict` abaixo colapsaria os repetidos numa entrada so — que e o
    # certo, porque medi-los duas vezes seria pagar o dobro pelo mesmo numero.
    if not variaveis:
        return {_nome_do_alvo(alvo, padrao): alvo for alvo in completos}
    return {
        ",".join(f"{chave}={alvo[chave]}" for chave in variaveis): alvo
        for alvo in completos
    }


def _por_alvo(valor: object, nome: str) -> object:
    """O valor daquele alvo, aceitando tambem o formato antigo de um alvo so.

    ⚠️ **Diarios escritos antes de 16/09/2026 guardam um numero solto**, e nao um
    dicionario por alvo. Eles continuam legiveis: um numero solto responde por
    qualquer alvo perguntado, que e o que ele significava.
    """
    if isinstance(valor, dict):
        return valor.get(nome)
    return valor


def _alvos_do_diario(diario: "Diario") -> list[str]:
    """Que alvos aparecem no diario, na ordem em que foram vistos."""
    for valor in diario.peneira.values():
        if isinstance(valor, dict):
            return list(valor)
    return [""]


def _resumo_da_peneira(diario: "Diario") -> str:
    """Quantas passaram, e com que tamanho de solucao — uma linha por alvo.

    ⚠️ **A peneira ja sabe a distancia** — ela devolve em que lance o objetivo
    caiu, e nao um sim/nao. Entao o retrato do acervo aparece desde a primeira
    fase, horas antes de a medicao confirmar.
    """
    nomes = _alvos_do_diario(diario)
    partes = []
    for nome in nomes:
        passaram = [
            _por_alvo(v, nome)
            for v in diario.peneira.values()
            if _por_alvo(v, nome) is not None
        ]
        rotulo = f"[{nome}] " if nome else ""
        partes.append(f"{rotulo}elegiveis {len(passaram)} | {_distancias(passaram)}")
    return "— " + "  ·  ".join(partes)


def _resumo_da_medicao(diario: "Diario") -> str:
    """Quantos moldes fecharam, com que distancia e com quanto material."""
    nomes = _alvos_do_diario(diario)
    partes = []
    for nome in nomes:
        distancias: list[int] = []
        material: list[int] = []
        for fen, lances in diario.medicao.items():
            do_alvo = _por_alvo(lances, nome) or []
            validos = [n for n in do_alvo if n is not None]
            if len(validos) >= MINIMO_DE_MODALIDADES:
                distancias.append(round(sum(validos) / len(validos)))
                material.append(sum(pecas_da_fen(fen)))
        media = f" | material {sum(material) / len(material):.1f}" if material else ""
        rotulo = f"[{nome}] " if nome else ""
        partes.append(f"{rotulo}moldes {len(distancias)} | {_distancias(distancias)}{media}")
    return "— " + "  ·  ".join(partes)


def tabela_do_p(distancia: "Counter[int]", piso: int) -> list[str]:
    """Quantos moldes cada `p` da frase renderia — *"coroe X damas em ate p lances"*.

    ⚠️ **Pedido do dono, 16/09/2026:** *"eu imaginei que o teto de 20 meios lances
    nos daria uma liberdade para escolher este `p` da frase do desafio. Este P
    poderia ser 6, 7, 8, 9, 10, 11, 12, 13 etc."*

    ⛔ **Sem esta tabela a liberdade era teorica.** Os dados estavam no diario,
    mas escolher exigiria rele-lo e fazer a conta a mao — e, sem a conta, a
    escolha viraria chute. Aqui e uma leitura.

    ⚠️ **Um molde cabe em `p` quando a solucao dele cabe em `p` lances DO
    JOGADOR.** Os lados alternam e o jogador comeca, entao o `p`-esimo lance dele
    e o meio-lance `2p - 1`: um molde de 9 meios-lances cabe em `p = 5`, e em
    qualquer `p` maior.

    Args:
        distancia: quantos moldes ha em cada distancia, em meios-lances.
        piso: o `nu_minimo_de_meios_lances` do editorial. `0` = sem piso.

    Returns:
        As linhas a imprimir. Vazio se nao houver molde nenhum.

    ⛔ **A coluna do piso nao e enfeite:** sem ela a tabela diria que ha 133
    moldes para um `p` onde o gerador publicaria 20 — ele recusa gabarito abaixo
    do piso, e a diferenca so apareceria como "sem candidato" semanas depois.
    """
    if not distancia:
        return []
    linhas = ["quantos moldes cada `p` da frase renderia:"]
    maior = max(distancia)
    for lances_p in range(1, (maior + 1) // 2 + 1):
        cabem = sum(
            quantos
            for meios, quantos in distancia.items()
            if meios <= 2 * lances_p - 1
        )
        if not cabem:
            continue
        com_piso = sum(
            quantos
            for meios, quantos in distancia.items()
            if piso <= meios <= 2 * lances_p - 1
        )
        aviso = "" if com_piso == cabem else f"  (com o piso de hoje: {com_piso})"
        linhas.append(f"    p = {lances_p:2} lances: {cabem} moldes{aviso}")
    return linhas


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


#: Quantas posicoes sao anunciadas uma a uma no comeco de cada fase.
#:
#: ⛔ **ISTO EXISTE PORQUE A FASE 2 PARECEU TRAVADA — e a suspeita era razoavel**
#: (14/09/2026, o dono: *"o passo 2 esta com este output ja faz um tempo. Sera
#: que travou?"*).
#:
#: ⚠️ **O passo de 25 foi calibrado na fase BARATA e nao serve para a cara.** A
#: peneira gasta ~1,7 s por posicao, entao 25 delas sao ~45 s de silencio; a
#: medicao roda **quatro** modalidades com **tres vezes** os nos, e as mesmas 25
#: viram ~8 minutos. ⛔ E esse silencio comeca logo depois do bloco de resumo da
#: peneira, que na tela **parece um encerramento** — o script parecia ter
#: terminado com um relatorio e travado no fim.
#:
#: ✅ A cura e dar sinal de vida cedo: as primeiras posicoes saem uma a uma, e so
#: depois o passo de 25 assume. O log nao cresce (sao cinco linhas), e a duvida
#: *"esta andando?"* morre no primeiro minuto.
PRIMEIRAS_ANUNCIADAS = 5


def _rodar_fase(
    nome: str,
    funcao,
    pendentes: list[str],
    ja_feitas: int,
    total: int,
    args,
    alvos_e_teto,
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
        funcao, [(f, args.tipo, alvos_e_teto) for f in pendentes], args.processos
    ):
        anotar(resultado)
        feitas += 1
        # As primeiras uma a uma (sinal de vida), depois a cada 25, e sempre na
        # ultima: horas caladas parecem travamento, e foi isso que o dono pediu
        # para nao acontecer — duas vezes.
        nesta_vez = feitas - ja_feitas
        if nesta_vez <= PRIMEIRAS_ANUNCIADAS or feitas % 25 == 0 or feitas == total:
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
        "--parametros",
        type=str,
        default="",
        help=(
            "JSON com os numeros que a peneira julga, sobrepondo o padrao do "
            "tipo. Ex.: --parametros \"{'damas': 2, 'lances': 10}\" (aspas "
            "simples aceitas, para nao brigar com o PowerShell). "
            "⛔ **A JANELA E UMA PAREDE, igual ao teto**: com `lances: 6` toda "
            "posicao que precise de sete lances do jogador reprova na peneira, "
            "por mais folgado que o teto esteja — foi assim que o acervo do "
            "`damas_coroar` nasceu curto duas vezes. ⚠️ **E o ALVO muda a "
            "tarefa**: `damas: 2` pede duas coroacoes e reprova quem so comporta "
            "uma, entao ele pede diario proprio."
        ),
    )
    ap.add_argument(
        "--teto",
        type=int,
        default=0,
        help=(
            "teto da busca em MEIOS-lances, sobrepondo o do editorial. "
            "⚠️ **MEIO-lance, e nao lance seu**: os lados alternam e o jogador "
            "comeca, entao o p-esimo lance DELE e o meio-lance 2p-1. "
            "teto 12 -> p ate 6 · teto 15 -> p ate 8 · teto 20 -> p ate 10 · "
            "teto 23 -> p ate 12 · teto 26 -> p ate 13. "
            "⚠️ **Serve para pescar um acervo mais FUNDO do que o que se publica "
            "hoje**, e assim poder escolher o `p` da frase (*'coroe X damas em "
            "ate p lances'*) depois, sem repescar: com teto 26 o acervo comporta "
            "p de 3 a 13. ⛔ **O preco e real**: a peneira vai mais fundo em toda "
            "posicao, e mais posicoes passam para a fase 2, que custa ~12x. "
            "⛔ **E o acervo passa a conter moldes que o editorial de hoje NAO "
            "gera** - cada linha do bloco final traz a distancia dela, e o resumo "
            "diz quantos moldes cada `p` renderia."
        ),
    )
    ap.add_argument(
        "--minimo-fileiras",
        type=int,
        default=0,
        help=(
            "so posicoes cuja pedra mais adiantada esta a N fileiras OU MAIS da "
            "coroacao. ⛔ E o PISO que faltava ao lado do teto `--alcancavel`, e "
            "ele nasceu de um numero: 82%% dos 515 moldes do `damas_coroar` tem a "
            "pedra a 1 ou 2 fileiras — dois lances e acabou. ⚠️ Pedido do dono em "
            "16/09/2026: *'se deixar as fileiras de tras totalmente livres e a "
            "peca do humano avancada demais, fica um desafio de simplesmente "
            "mover a peca pra frente'*."
        ),
    )
    ap.add_argument(
        "--desvantagem",
        type=int,
        default=0,
        help=(
            "so posicoes em que QUEM JOGA tem N pecas a menos que o adversario. "
            "⛔ E o filtro do `damas_sobreviver`, e ele procura o CONTRARIO de "
            "todos os outros: resistir de uma posicao confortavel nao e resistir, "
            "e uma pescaria sem isto devolveria o acervo do `coroar` com outro "
            "nome. ⚠️ Mantenha o numero baixo (1 a 3): medido em 14/09/2026, "
            "desvantagem grande nao produz resistencia, produz derrota antes do "
            "oitavo lance."
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

    # ⛔ **O padrao sai do EDITORIAL, e nao de `TIPOS`** — a tabela era uma copia
    # escrita a mao da janela publicada, e ficava velha calada. `--parametros`
    # sobrepoe, para pescar um acervo que ainda nao tem variante no ar.
    padrao = dict(parametros_do_tipo(args.tipo))
    alvos: dict[str, dict] = {}
    if args.parametros:
        try:
            de_fora = json.loads(args.parametros.replace("'", '"'))
        except json.JSONDecodeError as erro:
            raise SystemExit(
                f"⛔ --parametros nao e JSON valido: {erro}\n"
                "   Um alvo: --parametros \"{'damas': 2, 'lances': 10}\"\n"
                "   Varios:  --parametros \"[{'damas': 1, 'lances': 10}, "
                "{'damas': 2, 'lances': 10}]\""
            ) from erro
        # ⚠️ Um objeto e um alvo; uma lista sao varios. A forma de um alvo so
        # continua valendo, para nao quebrar quem ja usava a bandeira.
        lista = de_fora if isinstance(de_fora, list) else [de_fora]
        if not lista or not all(isinstance(item, dict) for item in lista):
            raise SystemExit(
                "⛔ --parametros tem de ser um objeto JSON, ou uma lista deles."
            )
        alvos = _nomear_alvos(lista, padrao)
    else:
        alvos[_nome_do_alvo(padrao, padrao)] = padrao

    # ── ⛔ A JANELA TEM DE CABER NO TETO ────────────────────────────────────
    #
    # ⛔ **E o defeito nº 1 desta familia de ferramentas, e ele volta sempre que
    # alguem escreve os dois numeros a mao.** A primeira cacada do
    # `damas_sobreviver` (10/09/2026) aprovou ZERO moldes porque o teto ficava
    # abaixo da janela do tipo — e o log dizia `nao_cumpriu_no_teto`, que e
    # indistinguivel de *"o jogo nao permite"*. Horas de busca para um numero que
    # nunca poderia fechar.
    #
    # ⚠️ **A aritmetica:** os dois lados alternam e o jogador comeca, entao o
    # N-esimo lance DELE e o meio-lance `2N - 1`. Uma janela de 10 lances do
    # jogador precisa de pelo menos 19 meios-lances de teto.
    #
    # ⛔ **Erro, e nao aviso.** Um aviso seria lido depois de trinta segundos de
    # barra de progresso, quando a pescaria ja parece estar indo bem.
    teto_publicado = teto_do_tipo(args.tipo)
    teto = args.teto or teto_publicado
    for nome, valores in alvos.items():
        if "lances" not in valores:
            continue
        preciso = 2 * valores["lances"] - 1
        if preciso > teto:
            raise SystemExit(
                f"⛔ o alvo [{nome}] pede janela de {valores['lances']} lances do "
                f"jogador, que sao {preciso} meios-lances — e o teto deste tipo e "
                f"{teto}.\n"
                "   Nenhum molde poderia fechar, e o log diria apenas "
                '"nao_cumpriu_no_teto".\n'
                f"   Ou baixe a janela para {(teto + 1) // 2} lances, ou suba "
                "`nu_maximo_de_meios_lances` no editorial do tipo."
            )

    # ⚠️ Lido do editorial, e nao escrito aqui: e o mesmo numero que o gerador
    # usa para recusar gabarito curto.
    try:
        piso_do_editorial = max(
            p.nu_minimo_de_meios_lances
            for p in editorial_mod.variantes_de(args.tipo)
        )
    except Exception:  # noqa: BLE001 — tipo em avaliacao nao tem editorial
        piso_do_editorial = 0

    # ⛔ **O maior `p` e `(teto + 1) // 2`, e nao `teto // 2`.** O p-esimo lance do
    # jogador e o meio-lance `2p - 1`, entao um teto impar (15) comporta um `p` a
    # mais do que a divisao simples sugere (8, e nao 7). ⚠️ A ambiguidade
    # "lance x meio-lance" ja causou QUATRO leituras erradas neste projeto — o
    # dono em 12/09 e em 16/09, o assistente em 11/09 e em 16/09 —, e todas
    # custaram horas de busca ou um acervo mal lido.
    print(
        f"teto da busca: {teto} meios-lances — comporta `p` de ate "
        f"{(teto + 1) // 2} lances do jogador"
    )
    if piso_do_editorial:
        print(
            f"piso do editorial: {piso_do_editorial} meios-lances "
            f"(~{-(-piso_do_editorial // 2)} lances) — o gerador recusa abaixo disso"
        )
    if args.teto and args.teto != teto_publicado:
        # ⛔ **Nao e um detalhe de log: e a diferenca entre o acervo e o que o job
        # consegue publicar.** O comentario de `TETO_POR_TIPO` avisa que "um teto
        # diferente aqui aprovaria molde que la nao gera", e foi o defeito da
        # primeira versao desta ferramenta. ⚠️ A diferenca agora e que o diario
        # **registra a distancia de cada molde**, entao a escolha e informada em
        # vez de cega — ver a tabela de `p` no fim da pescaria.
        print(
            f"⚠️ teto do editorial hoje: {teto_publicado}. Os moldes que passarem "
            f"de {teto_publicado} meios-lances entram no acervo mas NAO serao "
            "gerados ate `nu_maximo_de_meios_lances` subir no editorial."
        )
    if len(alvos) == 1:
        print(f"peneira julga com: {next(iter(alvos.values()))}")
    else:
        # ⛔ **Varios alvos custam o do MAIS EXIGENTE, e nao a soma** — a fita e a
        # mesma para todos, porque o Sagaz joga a PARTIDA e nao o DESAFIO. Ver
        # `cacar_moldes_damas.resolve_varios_alvos`.
        print(f"⚡ {len(alvos)} alvos na MESMA busca (a fita e uma so):")
        for nome, valores in alvos.items():
            print(f"     {nome}: {valores}")
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

    if args.minimo_fileiras:
        antes = len(candidatas)
        candidatas = [
            f for f in candidatas if fileiras_ate_coroar(f) >= args.minimo_fileiras
        ]
        print(
            f"com pedra a {args.minimo_fileiras}+ fileira(s) da coroacao: "
            f"{len(candidatas)} (de {antes})"
        )

    if args.desvantagem:
        antes = len(candidatas)
        # ⚠️ **Todas as FENs ja chegam com as brancas a jogar** (`carregar` as
        # normaliza), entao "quem joga" e sempre o primeiro numero do par.
        candidatas = [
            f
            for f in candidatas
            if (lambda b, pr: pr - b >= args.desvantagem)(*pecas_da_fen(f))
        ]
        print(
            f"com quem joga {args.desvantagem}+ peca(s) atras: "
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
            # ⚠️ Entra na assinatura como os outros: uma pescaria retomada com
            # filtro diferente misturaria dois acervos no mesmo diario.
            "minimo_fileiras": args.minimo_fileiras,
            # ⛔ **Sem isto, retomar com outro alvo misturaria dois acervos** no
            # mesmo diario — metade das posicoes julgada por "coroar 1" e metade
            # por "coroar 2" —, e o resultado pareceria normal.
            "parametros": [
                [nome, sorted(valores.items())] for nome, valores in sorted(alvos.items())
            ],
            # ⛔ Retomar com outro teto misturaria dois acervos: metade
            # peneirada ate 20 meios-lances e metade ate 26.
            "teto": teto,
            "desvantagem": args.desvantagem,
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
                _peneirar_varios,
                pendentes,
                len(candidatas) - len(pendentes),
                len(candidatas),
                args,
                (alvos, teto),
                anotar=lambda r: diario.anotar_peneira(r[0], r[1], r[2]),
                resumo=lambda: _resumo_da_peneira(diario),
            )

        # ⚠️ **Aprovada e quem passou em PELO MENOS UM alvo.** Medir so quem
        # passou em todos jogaria fora o acervo de uma coroacao inteiro, que e o
        # mais numeroso — e a medicao custa o mesmo, porque a fita e uma so.
        aprovadas = [
            f
            for f in candidatas
            if any(
                _por_alvo(diario.peneira.get(f), nome) is not None for nome in alvos
            )
        ]
        print(f"peneira: {len(aprovadas)} de {len(candidatas)}")
        if len(alvos) > 1:
            for nome in alvos:
                quantas = sum(
                    1
                    for f in candidatas
                    if _por_alvo(diario.peneira.get(f), nome) is not None
                )
                print(f"    [{nome}] {quantas}")
        for causa, quantas in diario.motivos.most_common(10):
            print(f"    {causa}: {quantas}")

        if not aprovadas:
            print("⛔ nenhuma posicao real resolve este objetivo dentro da janela.")
            return 1

        # ── Fase 2: a medicao nas quatro modalidades ─────────────────────────
        pendentes = [f for f in aprovadas if f not in diario.medicao]
        if pendentes:
            # ⛔ **O aviso de entrada nao e enfeite.** Sem ele a tela mostra o
            # resumo da peneira — que **parece um relatorio final** — e depois
            # emudece por minutos, enquanto a fase mais cara comeca sem se
            # anunciar. Foi exatamente assim que a pescaria do sacrificio pareceu
            # travada em 14/09/2026.
            #
            # ⚠️ **E o custo por posicao sobe ~12x aqui**, o que precisa estar na
            # tela: quatro modalidades em vez de uma, com o triplo dos nos. Quem
            # acompanha nao tem como saber disso lendo o progresso da peneira.
            print(
                f"\n── medicao: {len(pendentes)} posicao(oes) nas "
                f"{len(MODALIDADES)} modalidades ──\n"
                "⚠️ Esta fase custa ~12x a peneira por posicao (4 modalidades, "
                "3x os nos).",
                flush=True,
            )
            _rodar_fase(
                "medicao",
                _medir_varios,
                pendentes,
                len(aprovadas) - len(pendentes),
                len(aprovadas),
                args,
                (alvos, teto),
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

    # ⚠️ **Um acervo POR ALVO, e nao um acervo so.** Coroar duas damas e uma
    # tarefa diferente de coroar uma: o molde que serve a uma pode nao servir a
    # outra, e juntar os dois numa lista publicaria o desafio errado.
    codigo_de_saida = 0
    for nome in alvos:
        bons = sorted(
            (
                (len(validos), sum(validos) / len(validos), fen)
                for fen in aprovadas
                if (
                    validos := [
                        n
                        for n in (_por_alvo(diario.medicao.get(fen), nome) or [])
                        if n is not None
                    ]
                )
                and len(validos) >= MINIMO_DE_MODALIDADES
            ),
            key=lambda t: (-t[0], -t[1]),
        )
        rotulo = f" [{nome}]" if len(alvos) > 1 else ""
        print(f"\nmedicao{rotulo}: {len(bons)} moldes")

        # ── O retrato: material e distancia, que e o que se quer comparar ────
        if bons:
            material = [sum(pecas_da_fen(f)) for _, _, f in bons]
            print(
                f"material dos aprovados: media {sum(material) / len(material):.1f} "
                f"| min {min(material)} | max {max(material)}"
            )
            distancia: Counter[int] = Counter(round(m) for _, m, _ in bons)
            # ⛔ **MEIOS-lances, e a palavra esta escrita.** Ate 16/09/2026 esta
            # linha dizia so "lances", e o assistente leu como lances do jogador —
            # o dobro do que e. A ambiguidade ja custou tres leituras erradas.
            print("distancia ate o objetivo (meios-lances, media das modalidades):")
            for meios in sorted(distancia):
                print(
                    f"    {meios} meios-lances (~{-(-meios // 2)} do jogador): "
                    f"{distancia[meios]}"
                )

            for linha in tabela_do_p(distancia, piso_do_editorial):
                print(linha)
        else:
            codigo_de_saida = 1

        if args.bloco:
            print(f"\n# ── colar em job/tipos_de_desafio.py{rotulo} ──")
            for quantas, media, fen in bons:
                # ⛔ **O comentario nao e enfeite: e o que permite DECIDIR
                # depois.** Ate 15/09/2026 este bloco saia so com a FEN, e o
                # acervo do `capturar_multipla` — colado a mao em 12/09 — tinha
                # `# 4/4 · lance 7.0` em cada linha. ⚠️ Foi por essa informacao
                # que o dono pode escolher cortar os moldes curtos; sem ela, a
                # unica saida e reler o diario ou repescar.
                print(f'    "{fen}",   # {quantas}/4 · {media:.1f} meios-lances')
    return codigo_de_saida


if __name__ == "__main__":
    # ⚠️ Obrigatorio no Windows: `multiprocessing` usa `spawn`, e cada processo
    # filho **reimporta este modulo**. Sem a guarda, cada filho chamaria `main()`
    # de novo e a pesca se multiplicaria sozinha.
    raise SystemExit(main())
