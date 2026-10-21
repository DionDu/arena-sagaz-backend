"""T124c (spec 010) - o golpe duplo, a linha de cinco e o "sem o meio", fase a fase.

═══════════════════════════════════════════════════════════════════════════
AS TRÊS PERGUNTAS (o item 2 do "plano do que sobra", 21/10/2026)
═══════════════════════════════════════════════════════════════════════════

A régua com o perseguidor (histórico do backend, "2026-10-21 (9)") deixou três
tipos de fora por defeitos que não são de régua:

  (a) **golpe duplo e linha de cinco**: nem o perseguidor no nível do Magno
      alcançou o objetivo. A prova de geração de hoje só diz que o tabuleiro
      COMPORTA o objetivo ("ao alcance"). A prova nova
      (`ProvadorQuatro.objetivo_forcavel`) pede mais: o objetivo é FORÇÁVEL,
      faça o adversário o que fizer. A pergunta: quantas posições do acervo
      passam nela, por comprimento? Algumas por cento (como o Segure) = a
      prova cabe no gerador; raríssimas = pescaria offline;
  (b) **sem o meio**: fácil para todos (0,75 a 0,96 de cumprimento). A que
      distância está a vitória SEM a coluna do meio, por comprimento? É dessa
      tabela que sai o botão (distância mínima na prova e/ou preparo maior),
      como a do "Vença em N" saiu da `medir_fases_das_posicoes_quatro.py`;
  (c) ⚠️ **a hipótese do dono**: *"como o Tex e o Magno têm um percentual alto
      de bloquear jogadas, golpe duplo e linha de cinco seriam desafios
      praticamente impossíveis com os 2 como adversário"*. A medição de 21/10
      só usou o Tex (0,13 e 0,10). Aqui o perseguidor no nível do Magno joga
      contra os QUATRO, nas mesmas posições.

═══════════════════════════════════════════════════════════════════════════
OS CONTROLES, ANTES DOS NÚMEROS
═══════════════════════════════════════════════════════════════════════════

Um instrumento novo prova o caso fácil antes de responder o difícil:

  * **fase 1**: em toda partida do acervo que terminou com cinco em linha ou
    com duas linhas no mesmo lance, a posição UM lance antes do fim tem de
    passar na prova forçável em 1 lance (o lance jogado prova que existe). E a
    posição montada à mão em que o único jeito de vencer é uma linha de quatro
    tem de REPROVAR nos dois tipos. Se um controle falhar, o script para: a
    tabela mediria o instrumento, e não o acervo;
  * **fase 2**: em cada adversário, o perseguidor com o objetivo "só vencer"
    (`controle_persegue_vencer`) tem de vencer perto do Magno que só vence
    (`magno_so_vence`), como na medição pareada. Longe = o perseguidor é
    incompetente CONTRA AQUELE adversário, e a linha dele não mede o tipo.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomável, todos os núcleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\medir_objetivo_forcavel_quatro.py

Cada unidade concluída (uma posição da fase 1; uma posição × adversário da
fase 2) vira uma linha do diário `medicoes/medir_objetivo_forcavel_quatro/
diario.jsonl`; rodar de novo pula o que já está lá. O relatório sai em
`relatorio.txt`, na mesma pasta, reescrito a cada execução a partir do diário
inteiro. Opções: `--processos N` (padrão: todos os núcleos), `--de 8 --ate 34`
(os comprimentos da fase 1), `--amostra 40` (posições distintas por
comprimento), `--posicoes 30` (posições por tipo e grupo na fase 2),
`--perguntas 400` (o teto da prova forçável; o do gerador é
`provas_quatro.PERGUNTAS_FORCAVEL`). ⚠️ Mudar `--perguntas` com o diário cheio
mistura dois tetos: apague a pasta antes (ou mova-a).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

# ⚠️ Um script em `scripts/` não é pacote instalado: sem isto, `from job import
# ...` falha. `parents[1]` sobe de `scripts/este_arquivo.py` para a raiz.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows é cp1252; sem isto o primeiro `×` derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job import posicoes_de_autoplay_quatro as acervo_mod  # noqa: E402
from job import provas_quatro as provas_mod  # noqa: E402
from job.editorial import CASAS_DO_TRADICIONAL  # noqa: E402
from job.gerador import vitoria_imediata_quatro  # noqa: E402
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import feitos_quatro  # noqa: E402
from motores.quatro.jogador_dart_quatro import JogadorDartQuatro  # noqa: E402
from motores.quatro.jogador_quatro import JogadorQuatro  # noqa: E402
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro, ler_sequencia  # noqa: E402

# Os dois scripts irmãos: a amostra por comprimento e a partida pareada vêm
# deles, e não de uma segunda escrita (uma diferença entre as duas cópias
# mudaria o que se mede sem ninguém ver).
from scripts.medir_fases_das_posicoes_quatro import amostrar  # noqa: E402
from scripts import medir_perseguir_vs_vencer_quatro as pareada  # noqa: E402

PASTA = RAIZ / "medicoes" / "medir_objetivo_forcavel_quatro"
DIARIO = PASTA / "diario.jsonl"
RELATORIO = PASTA / "relatorio.txt"

CO_MODALIDADE = "tradicional"

#: A semente da amostra da fase 1. Fixa: rodar de novo sorteia as mesmas.
SEMENTE = 20261021

#: Os dois tipos da prova forçável, com o parâmetro do editorial (`EDITORIAL_
#: FORA_DO_AR`: duas linhas; cinco em linha).
FORCAVEIS: dict[str, dict[str, int]] = {
    "quatro_golpe_duplo": {"linhas": 2},
    "quatro_linha_de_cinco": {"tamanho": 5},
}

#: Os quatro adversários da fase 2, do mais fraco ao mais forte.
ADVERSARIOS = (NivelDeMotor.CACAU, NivelDeMotor.PITA, NivelDeMotor.TEX, NivelDeMotor.SAGAZ)

#: Os modos de quem resolve na fase 2 (os nomes da medição pareada).
MODOS = ("magno_so_vence", "persegue_magno", "controle_persegue_vencer")

#: Quantos casos do acervo o controle da fase 1 confere, no máximo, por tipo.
CASOS_DE_CONTROLE = 20

#: Os controles montados à mão (os mesmos de `test_provas_quatro.py`): a vez é
#: do jogador 1, e ele vence em 1 lance - do jeito pedido, ou só do errado.
CONTROLE_MANUAL_PASSA = {
    "quatro_golpe_duplo": "s1s1s2s1s3s2s3s7s2s7s1s6",
    "quatro_linha_de_cinco": "s1s7s2s7s4s6s5s6",
}
CONTROLE_MANUAL_REPROVA = "s1s7s2s7s3s6"


def chegada(co_tipo: str) -> dict[str, Any]:
    """A linha de chegada do tipo com o parâmetro do editorial (a da receita)."""
    receita = RECEITAS.get(co_tipo) or RECEITAS_FORA_DO_AR[co_tipo]
    return receita.montar(FORCAVEIS.get(co_tipo, {}))


# ═══════════════════════════════════════════════════════════════════════════
# Fase 1 - o que o acervo tem, por comprimento
# ═══════════════════════════════════════════════════════════════════════════


def _forcavel(motor_dart, estado: EstadoQuatro, co_tipo: str, perguntas: int) -> dict[str, Any]:
    """A prova forçável de um tipo, com um provador SÓ dela.

    ⚠️ Um provador novo por prova: as respostas guardadas de uma prova
    baratearia a seguinte, e o número de perguntas (que decide o teto) sairia
    dependendo da ORDEM em que as provas rodaram.
    """
    provador = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
    prova = provador.objetivo_forcavel(estado, chegada(co_tipo), perguntas=perguntas)
    return {
        "passou": prova.passou,
        "lances": prova.dados.get("lances"),
        # "Estourou" é o não provado: nem sim, nem não. A tabela o separa da
        # recusa, porque um teto maior pode virá-lo.
        "estourou": "perguntas" in prova.motivo,
        "perguntas": provador.perguntas,
    }


def medir_posicao(unidade: dict[str, Any]) -> dict[str, Any]:
    """Uma posição da fase 1: a vitória livre, as duas forçáveis e o "sem o meio".

    ⚠️ Um executável SÓ desta unidade, aberto e fechado pelo `with` (memória
    "pool-fechado-deixa-os-processos").
    """
    inicio = time.time()
    lances = ler_sequencia(unidade["lances"])
    estado = EstadoQuatro(CO_MODALIDADE, lances)
    linha: dict[str, Any] = {
        "fase": 1, "comprimento": unidade["comprimento"], "lances": unidade["lances"],
    }
    with JogadorDartQuatro() as motor_dart:
        provador = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
        # A mesma recusa que o gerador faz antes de qualquer prova.
        if vitoria_imediata_quatro(provador.arbitro, estado) is not None:
            linha["de_cara"] = True
        else:
            quem = provador.arbitro.vez_de(estado)
            livre = provador.resultado(estado)
            # O resultado livre do ponto de vista de quem tem a vez.
            linha["livre"] = (
                "aberto" if livre.vencedor is None
                else "empata" if livre.vencedor == 0
                else "vence" if livre.vencedor == quem
                else "perde"
            )
            linha["distancia"] = livre.meios_lances if linha["livre"] == "vence" else None
            # As forçáveis e o "sem o meio" pedem a vitória livre: sem ela, as
            # três recusam na 1ª linha, e não vale gastar a busca de novo.
            if linha["livre"] == "vence":
                for co_tipo in FORCAVEIS:
                    linha[co_tipo] = _forcavel(motor_dart, estado, co_tipo, unidade["perguntas"])
                sem = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart).sem_o_meio(estado)
                linha["quatro_sem_o_meio"] = {"passou": sem.passou, "lances": sem.dados.get("lances")}
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


def casos_de_controle(partidas: Iterable[acervo_mod.PartidaDeAutoplay]) -> dict[str, list[str]]:
    """As posições um lance antes do fim que terminaram do jeito de cada tipo.

    Quem diz o jeito é o medidor de produção, com a fita de um lance só: as
    linhas do lance final e a maior linha do vencedor.
    """
    motor = MotorQuatro(CO_MODALIDADE)
    casos: dict[str, list[str]] = {co_tipo: [] for co_tipo in FORCAVEIS}
    for partida in partidas:
        if partida.vencedor == 0:
            continue
        medidas = feitos_quatro.medir(motor, partida.lances[:-1], partida.lances[-1:])
        anterior = "".join(partida.lances[:-1])
        if medidas["linhas_no_lance_final"] >= 2:
            casos["quatro_golpe_duplo"].append(anterior)
        if medidas["maior_linha"] >= 5:
            casos["quatro_linha_de_cinco"].append(anterior)
    # Sem repetição e em ordem estável: a mesma conferência a cada execução.
    return {t: sorted(set(c))[:CASOS_DE_CONTROLE] for t, c in casos.items()}


def controle_da_fase_1(partidas, perguntas: int) -> bool:
    """O caso fácil passa em 1 lance, e o do jeito errado reprova. Imprime e
    devolve se TUDO bateu."""
    casos = casos_de_controle(partidas)
    tudo_certo = True
    with JogadorDartQuatro() as motor_dart:
        for co_tipo in FORCAVEIS:
            posicoes = casos[co_tipo] + [CONTROLE_MANUAL_PASSA[co_tipo]]
            certas = 0
            for sequencia in posicoes:
                estado = EstadoQuatro(CO_MODALIDADE, ler_sequencia(sequencia))
                achado = _forcavel(motor_dart, estado, co_tipo, perguntas)
                certas += achado["passou"] and achado["lances"] == 1
            errado = _forcavel(
                motor_dart, EstadoQuatro(CO_MODALIDADE, ler_sequencia(CONTROLE_MANUAL_REPROVA)),
                co_tipo, perguntas,
            )
            print(
                f"[controle] {co_tipo}: um lance antes do fim, forçável em 1: "
                f"{certas} de {len(posicoes)} ({len(casos[co_tipo])} do acervo + 1 à mão); "
                f"o jeito errado {'REPROVA' if not errado['passou'] else 'PASSA (defeito)'}"
            )
            tudo_certo = tudo_certo and certas == len(posicoes) and not errado["passou"]
    return tudo_certo


# ═══════════════════════════════════════════════════════════════════════════
# Fase 2 - o perseguidor no nível do Magno contra os quatro adversários
# ═══════════════════════════════════════════════════════════════════════════


def medir_adversario(unidade: dict[str, Any]) -> dict[str, Any]:
    """Uma posição × um adversário, nos três modos (a partida da medição pareada).

    Dois grupos de posição: `alcance` (as MESMAS da medição de 21/10, pela
    semente dela: o que o gerador entrega hoje) e `forcavel` (as que passaram
    na prova forçável da fase 1).
    """
    inicio = time.time()
    co_tipo, grupo, indice = unidade["co_tipo"], unidade["grupo"], unidade["indice"]
    adversario = NivelDeMotor(unidade["adversario"])
    linha: dict[str, Any] = {
        "fase": 2, "co_tipo": co_tipo, "grupo": grupo, "indice": indice,
        "adversario": adversario.value,
    }
    with JogadorDartQuatro() as motor_dart:
        jogador = JogadorQuatro(CO_MODALIDADE, motor_dart)
        provador = provas_mod.ProvadorQuatro(
            CO_MODALIDADE, motor_dart, teto_de_nos=pareada.TETO_DA_PROVA_DO_MAGNO
        )
        if grupo == "alcance":
            posicao = pareada._posicao(
                co_tipo, indice, provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
            )
        else:
            lances = list(ler_sequencia(unidade["lances"]))
            # Até o fim da partida: o teto de quem persegue um jeito de vencer
            # é o resto do tabuleiro (o mesmo do editorial).
            posicao = {
                "lances": lances, "chegada": chegada(co_tipo),
                "teto": CASAS_DO_TRADICIONAL - len(lances),
            }
        if posicao is None:
            linha["sem_posicao"] = True
        else:
            linha["lances"] = "".join(posicao["lances"])
            # A semente da partida é a da medição pareada (por tipo e
            # identidade): os quatro adversários enfrentam os mesmos sorteios,
            # e no grupo `alcance` são os mesmos da medição de 21/10.
            nu_semente = int(
                random.Random(
                    f"{pareada.SEMENTE}:jogo:{co_tipo}:{identidade(unidade)}"
                ).getrandbits(31)
            )
            for modo in MODOS:
                linha[modo] = pareada._jogar(
                    jogador, provador, co_tipo, posicao["lances"], posicao["chegada"],
                    posicao["teto"], modo, nu_semente, adversario=adversario,
                )
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


# ═══════════════════════════════════════════════════════════════════════════
# O diário e o relatório
# ═══════════════════════════════════════════════════════════════════════════


def identidade(unidade: dict[str, Any]) -> int | str:
    """Quem é a posição da fase 2: o índice no `alcance`, os lances no `forcavel`.

    ⚠️ No `forcavel` o índice NÃO serve: a lista sai do diário da fase 1, e uma
    execução com mais posições mudaria o que cada índice aponta - o diário
    pularia uma posição nova achando que já a mediu.
    """
    return unidade["indice"] if unidade["grupo"] == "alcance" else unidade["lances"]


def chave(linha: dict[str, Any]) -> tuple:
    """A identidade de uma unidade no diário (o que "já medido" quer dizer)."""
    if linha["fase"] == 1:
        return (1, linha["lances"])
    return (2, linha["co_tipo"], linha["grupo"], identidade(linha), linha["adversario"])


def ler_diario() -> list[dict[str, Any]]:
    """As linhas já medidas (vazio na 1ª execução)."""
    if not DIARIO.is_file():
        return []
    return [json.loads(l) for l in DIARIO.read_text(encoding="utf-8").splitlines() if l]


def forcaveis_do_diario(linhas: list[dict[str, Any]], co_tipo: str, quantas: int) -> list[str]:
    """As posições da fase 1 que passaram na prova forçável de [co_tipo].

    Em ordem estável (comprimento, depois os lances): o grupo `forcavel` da
    fase 2 é o mesmo a cada execução enquanto o diário da fase 1 não mudar.
    """
    passaram = sorted(
        (l["comprimento"], l["lances"])
        for l in linhas
        if l["fase"] == 1 and (l.get(co_tipo) or {}).get("passou")
    )
    return [lances for _, lances in passaram[:quantas]]


def _tabela_da_fase_1(linhas: list[dict[str, Any]]) -> list[str]:
    """Uma linha por comprimento: o que a busca provou, e quantas passam."""
    por_comprimento: dict[int, list[dict[str, Any]]] = {}
    for l in linhas:
        if l["fase"] == 1:
            por_comprimento.setdefault(l["comprimento"], []).append(l)
    saida = [
        "FASE 1 - por comprimento (lances jogados). 'vence' = quem tem a vez vence à força.",
        "golpe/cinco: passou · estourou (o teto de perguntas: nem sim, nem não).",
        "sem o meio: passou, e a distância da vitória sem o meio em LANCES da pessoa (1 a 8).",
        "",
        f"{'lances':>6} {'n':>4} {'cara':>4} {'vence':>5} | {'golpe':>5} {'estr':>4} | "
        f"{'cinco':>5} {'estr':>4} | {'sem':>4}  distância 1..8",
    ]
    for comprimento in sorted(por_comprimento):
        grupo = por_comprimento[comprimento]
        vence = [l for l in grupo if l.get("livre") == "vence"]

        def conta(co_tipo: str, campo: str) -> int:
            return sum(1 for l in vence if l[co_tipo][campo])

        sem = Counter(
            l["quatro_sem_o_meio"]["lances"] for l in vence if l["quatro_sem_o_meio"]["passou"]
        )
        distancias = " ".join(f"{sem[d]:>3}" for d in range(1, 9))
        saida.append(
            f"{comprimento:>6} {len(grupo):>4} {sum(1 for l in grupo if l.get('de_cara')):>4} "
            f"{len(vence):>5} | {conta('quatro_golpe_duplo', 'passou'):>5} "
            f"{conta('quatro_golpe_duplo', 'estourou'):>4} | "
            f"{conta('quatro_linha_de_cinco', 'passou'):>5} "
            f"{conta('quatro_linha_de_cinco', 'estourou'):>4} | {sum(sem.values()):>4}  {distancias}"
        )
    # O resumo: a taxa sobre TODAS as posições medidas (é a que o gerador vê:
    # ele sorteia do acervo, e não só das que vencem), e o custo das que passam.
    total = sum(len(g) for g in por_comprimento.values())
    saida.append("")
    for co_tipo in FORCAVEIS:
        medidas = [l[co_tipo] for g in por_comprimento.values() for l in g if co_tipo in l]
        passaram = [m for m in medidas if m["passou"]]
        estouros = sum(1 for m in medidas if m["estourou"])
        perguntas = sorted(m["perguntas"] for m in passaram)
        mediana = perguntas[len(perguntas) // 2] if perguntas else "-"
        distancia = Counter(m["lances"] for m in passaram)
        saida.append(
            f"[{co_tipo}] passaram {len(passaram)} de {total} posições "
            f"({len(passaram) / total if total else 0:.1%}); estouraram {estouros}; "
            f"perguntas das que passaram: mediana {mediana}, máxima "
            f"{perguntas[-1] if perguntas else '-'}; em lances: {dict(sorted(distancia.items()))}"
        )
    return saida


def _tabela_da_fase_2(linhas: list[dict[str, Any]]) -> list[str]:
    """Por tipo e grupo: uma linha por adversário, cumpriu e venceu por modo."""
    saida = [
        "FASE 2 - o perseguidor no nível do Magno contra os quatro adversários.",
        "⛔ CONTROLE por adversário: 'venceu' do controle_persegue_vencer perto do",
        "magno_so_vence. Longe = a linha daquele adversário não mede o tipo.",
        "",
    ]
    for co_tipo in FORCAVEIS:
        for grupo in ("alcance", "forcavel"):
            do_grupo = [
                l for l in linhas
                if l["fase"] == 2 and l["co_tipo"] == co_tipo and l["grupo"] == grupo
            ]
            if not do_grupo:
                continue
            saida.append(f"{co_tipo} · posições '{grupo}'")
            for adversario in ADVERSARIOS:
                medidas = [
                    l for l in do_grupo
                    if l["adversario"] == adversario.value and not l.get("sem_posicao")
                ]
                n = len(medidas)
                if not n:
                    continue
                partes = []
                for modo in MODOS:
                    cumpriu = sum(l[modo]["cumpriu"] for l in medidas)
                    venceu = sum(l[modo]["venceu"] for l in medidas)
                    partes.append(f"{modo} {cumpriu / n:4.2f} (venceu {venceu:>2})")
                saida.append(f"   contra {adversario.value:<6} n={n:<3} " + " · ".join(partes))
            saida.append("")
    return saida


def relatorio(linhas: list[dict[str, Any]]) -> str:
    """O relatório inteiro, das duas fases, a partir do diário."""
    return "\n".join(
        ["Golpe duplo, linha de cinco e sem o meio (Quatro, T124c, plano do que sobra)", ""]
        + _tabela_da_fase_1(linhas)
        + [""]
        + _tabela_da_fase_2(linhas)
    )


def _rodar(pool, funcao, unidades: list[dict[str, Any]], diario, rotulo: str) -> None:
    """Mede as unidades no pool, gravando uma linha do diário por unidade."""
    inicio = time.time()
    for i, linha in enumerate(pool.imap_unordered(funcao, unidades), 1):
        # Gravada na hora: é o que torna a medição retomável se a janela fechar.
        diario.write(json.dumps(linha, ensure_ascii=False) + "\n")
        diario.flush()
        if i % 20 == 0 or i == len(unidades):
            print(f"[{rotulo} {i}/{len(unidades)}] {time.time() - inicio:.0f} s", flush=True)


def principal(argumentos: list[str]) -> int:
    """Lê os argumentos, confere os controles, mede o que falta e escreve o relatório."""
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--de", type=int, default=8)
    leitor.add_argument("--ate", type=int, default=34)
    leitor.add_argument("--amostra", type=int, default=40)
    leitor.add_argument("--posicoes", type=int, default=30)
    leitor.add_argument("--perguntas", type=int, default=provas_mod.PERGUNTAS_FORCAVEL)
    leitor.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    args = leitor.parse_args(argumentos)

    acervo = acervo_mod.carregar(CO_MODALIDADE)
    print(f"[acervo] {len(acervo.partidas)} partidas ({acervo.co_versao_motor})")
    if not controle_da_fase_1(acervo.partidas, args.perguntas):
        print("⛔ o controle da fase 1 falhou: a tabela mediria o instrumento. Parando.")
        return 1

    PASTA.mkdir(parents=True, exist_ok=True)
    feitas = {chave(l) for l in ler_diario()}

    # A amostra da fase 1 sai de um sorteio só, ANTES do pool: a ordem em que
    # os processos terminam não muda quais posições foram medidas.
    sorteio = random.Random(SEMENTE)
    fase_1 = [
        {"comprimento": n, "lances": "".join(lances), "perguntas": args.perguntas}
        for n in range(args.de, args.ate + 1)
        for lances, _lado in amostrar(acervo.partidas, n, args.amostra, sorteio)
    ]
    fase_1 = [u for u in fase_1 if (1, u["lances"]) not in feitas]
    print(f"[fase 1] {len(fase_1)} posições a medir, em {args.processos} processos.")
    with multiprocessing.Pool(args.processos) as pool, DIARIO.open("a", encoding="utf-8") as diario:
        _rodar(pool, medir_posicao, fase_1, diario, "fase 1")

    # A fase 2 vem DEPOIS: o grupo `forcavel` sai do diário da fase 1.
    linhas = ler_diario()
    fase_2 = []
    for co_tipo in FORCAVEIS:
        grupos = {
            "alcance": [None] * args.posicoes,
            "forcavel": forcaveis_do_diario(linhas, co_tipo, args.posicoes),
        }
        for grupo, posicoes in grupos.items():
            for indice, lances in enumerate(posicoes):
                for adversario in ADVERSARIOS:
                    unidade = {
                        "fase": 2, "co_tipo": co_tipo, "grupo": grupo, "indice": indice,
                        "adversario": adversario.value, "lances": lances,
                    }
                    if chave(unidade) not in feitas:
                        fase_2.append(unidade)
    print(f"[fase 2] {len(fase_2)} unidades a medir.")
    with multiprocessing.Pool(args.processos) as pool, DIARIO.open("a", encoding="utf-8") as diario:
        _rodar(pool, medir_adversario, fase_2, diario, "fase 2")

    texto = relatorio(ler_diario())
    RELATORIO.write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
