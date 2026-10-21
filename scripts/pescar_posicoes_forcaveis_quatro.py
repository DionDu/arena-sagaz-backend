"""T124c (spec 010) - a PESCARIA do golpe duplo, da linha de cinco e do "sem o meio".

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

A medição de 21/10/2026 (`medir_objetivo_forcavel_quatro.py`, histórico do
backend "2026-10-21 (10)") mostrou que esses três tipos quase não têm posição no
acervo do gerador, e o dono decidiu (`DECISOES-do-dono.md` §8zzzn): as posições
deles vêm de uma pescaria OFFLINE, com um acervo próprio e MAIOR, e com muitos
lances da pessoa (*"resolver o desafio em tão poucos lances do jogador humano é
muito ruim"*).

⛔ **O acervo do gerador (`dados/jogo_quatro/partidas_de_autoplay_*.json`) não é
tocado.** A semente do dia sorteia dele os cinco tipos que estão no ar, medidos
sobre ele; trocá-lo mudaria a fila deles sem ninguém ver.

═══════════════════════════════════════════════════════════════════════════
AS TRÊS ETAPAS
═══════════════════════════════════════════════════════════════════════════

  A. **o acervo próprio**: partidas de autoplay em quatro CONFRONTOS (Magno ×
     Tex, Magno × Pita, Tex × Pita, Tex × Tex). Níveis variados dão posições
     que o acervo Magno × Tex não tem; o mais forte troca de cor a cada partida.
     A partida é a do extrator do acervo (`jogar_autoplay`), escrita uma vez;
  B. **as provas**: cada posição distinta cuja vitória livre está entre
     `PISO_DE_MEIOS_LANCES` e `--teto` meios-lances passa pelas três provas,
     com a **defesa do JOGO** (`provas_quatro.DEFESA_DO_JOGO`: o objetivo é
     forçável contra quem joga para não perder, como os quatro personagens -
     a outra defesa quase não acha posição com muitos lances, ver a
     constante). As posições vão numa ordem EMBARALHADA e fixa: interromper no
     meio deixa uma amostra de todo o acervo, e não só das primeiras partidas;
  C. **o banco**: `dados/jogo_quatro/banco_forcavel_<modalidade>.json`, reescrito
     a partir do diário a cada execução - inclusive a interrompida. É ele que o
     gerador vai ler (passo seguinte da T124c), e por isso vai ao Git.

⚠️ O piso é o do gabarito (`editorial.MINIMO_DE_MEIOS_LANCES_PADRAO`, 9 meios-
lances = 5 lances da pessoa): a prova começa da distância da vitória livre, então
nada abaixo dele entra. O piso de PUBLICAÇÃO de cada tipo sai da distribuição que
o relatório mostra (entre duas variantes, entra a mais longa, §8k-0).

═══════════════════════════════════════════════════════════════════════════
O CONTROLE, ANTES DE TUDO
═══════════════════════════════════════════════════════════════════════════

O mesmo de `medir_objetivo_forcavel_quatro.py`, com a defesa do jogo: em toda
partida do acervo do gerador terminada com cinco em linha ou duas linhas no mesmo
lance, a posição um lance antes do fim passa em 1 lance; a posição em que só a
linha de quatro vence reprova. Se falhar, o script para antes de jogar nada.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomável, todos os núcleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\pescar_posicoes_forcaveis_quatro.py

Pode ser interrompido com Ctrl+C a qualquer momento; rodar o MESMO comando
retoma do diário (`medicoes/pescar_posicoes_forcaveis_quatro/diario.jsonl`). O
relatório sai em `relatorio.txt`, na mesma pasta. Opções: `--partidas N` (por
confronto, padrão 100), `--teto 23` (meios-lances), `--perguntas 2000` (o teto
de buscas de cada prova), `--processos N` (padrão: todos os núcleos).
⚠️ Mudar `--teto` ou `--perguntas` com o diário cheio mistura dois critérios:
mova a pasta antes.
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
from job.editorial import MINIMO_DE_MEIOS_LANCES_PADRAO  # noqa: E402
from job.gerador import vitoria_imediata_quatro  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from motores.quatro.jogador_dart_quatro import JogadorDartQuatro  # noqa: E402
from motores.quatro.jogador_quatro import JogadorQuatro  # noqa: E402
from motores.quatro.motor_quatro import EstadoQuatro, ler_sequencia  # noqa: E402

# Os irmãos: a partida de autoplay, os casos de controle e a chegada de cada
# tipo vêm deles, e não de uma segunda escrita.
from scripts.extrair_posicoes_de_autoplay_quatro import jogar_autoplay  # noqa: E402
from scripts.medir_objetivo_forcavel_quatro import (  # noqa: E402
    CONTROLE_MANUAL_PASSA,
    CONTROLE_MANUAL_REPROVA,
    FORCAVEIS,
    casos_de_controle,
    chegada,
)

PASTA = RAIZ / "medicoes" / "pescar_posicoes_forcaveis_quatro"
DIARIO = PASTA / "diario.jsonl"
RELATORIO = PASTA / "relatorio.txt"

CO_MODALIDADE = "tradicional"

#: A versão do formato do banco (quem lê confere).
VERSAO_DO_BANCO = 1

#: A semente-base da pescaria. A partida `i` do confronto `k` usa
#: `SEMENTE + 100_000 * k + i`. ⚠️ Fixa: rodar de novo joga as mesmas partidas,
#: e é isso que deixa o diário retomar.
SEMENTE = 20261022

#: Os confrontos: (o mais forte, o outro). ⚠️ A ORDEM é parte da semente (o `k`
#: acima): acrescente no FIM, nunca no meio.
CONFRONTOS: dict[str, tuple[NivelDeMotor, NivelDeMotor]] = {
    "magno_tex": (NivelDeMotor.SAGAZ, NivelDeMotor.TEX),
    "magno_pita": (NivelDeMotor.SAGAZ, NivelDeMotor.PITA),
    "tex_pita": (NivelDeMotor.TEX, NivelDeMotor.PITA),
    "tex_tex": (NivelDeMotor.TEX, NivelDeMotor.TEX),
}

#: Os três tipos da pescaria, com o parâmetro de cada um (o do editorial).
TIPOS = ("quatro_golpe_duplo", "quatro_linha_de_cinco", "quatro_sem_o_meio")

#: O piso: a vitória livre (e então a do objetivo) a pelo menos 9 meios-lances.
PISO_DE_MEIOS_LANCES = MINIMO_DE_MEIOS_LANCES_PADRAO

#: Posições com menos lances jogados que isto são aberturas: ficam de fora.
MINIMO_DE_LANCES_JOGADOS = 8


def caminho_do_banco(co_modalidade: str) -> Path:
    """O arquivo do banco, ao lado do acervo do gerador (vai ao Git)."""
    return acervo_mod.PASTA_DO_ACERVO / f"banco_forcavel_{co_modalidade}.json"


# ═══════════════════════════════════════════════════════════════════════════
# Etapa A - as partidas
# ═══════════════════════════════════════════════════════════════════════════


def jogar(unidade: dict[str, Any]) -> dict[str, Any]:
    """Uma partida de um confronto, com um executável SÓ dela (o `with` o fecha)."""
    confronto, indice = unidade["confronto"], unidade["indice"]
    forte, outro = CONFRONTOS[confronto]
    # O mais forte abre nas partidas pares e responde nas ímpares (como no
    # acervo do gerador): a posição pode ter qualquer um dos dois a jogar.
    cor_do_forte = 1 if indice % 2 == 0 else -1
    niveis = {cor_do_forte: forte, -cor_do_forte: outro}
    semente = SEMENTE + 100_000 * list(CONFRONTOS).index(confronto) + indice
    with JogadorDartQuatro() as motor_dart:
        jogador = JogadorQuatro(CO_MODALIDADE, motor_dart)
        estado = jogar_autoplay(jogador, CO_MODALIDADE, niveis, semente)
        vencedor = int(jogador.arbitro.veredito(estado).vencedor)
    return {
        "etapa": "partida", "confronto": confronto, "indice": indice,
        "lances": "".join(estado.lances), "vencedor": vencedor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Etapa B - as provas
# ═══════════════════════════════════════════════════════════════════════════


def posicoes_das_partidas(partidas: Iterable[dict[str, Any]]) -> dict[str, str]:
    """As posições distintas das partidas, cada uma com o confronto de ORIGEM.

    A posição tem de ter um lance a jogar (é mais curta que a partida) e passar
    da abertura. A origem é o primeiro confronto (na ordem de `CONFRONTOS`, e
    depois do índice) que chega a ela: é a que o relatório usa para dizer qual
    confronto rende mais.
    """
    ordem = list(CONFRONTOS)
    origem: dict[str, str] = {}
    for partida in sorted(partidas, key=lambda p: (ordem.index(p["confronto"]), p["indice"])):
        lances = ler_sequencia(partida["lances"])
        for comprimento in range(MINIMO_DE_LANCES_JOGADOS, len(lances)):
            origem.setdefault("".join(lances[:comprimento]), partida["confronto"])
    return origem


def em_ordem_de_pescaria(posicoes: Iterable[str]) -> list[str]:
    """As posições numa ordem embaralhada e FIXA (a mesma a cada execução)."""
    lista = sorted(posicoes)
    random.Random(SEMENTE).shuffle(lista)
    return lista


def provar(unidade: dict[str, Any]) -> dict[str, Any]:
    """Uma posição: a vitória livre e, na faixa, as três provas com a defesa do jogo."""
    inicio = time.time()
    estado = EstadoQuatro(CO_MODALIDADE, ler_sequencia(unidade["lances"]))
    linha: dict[str, Any] = {
        "etapa": "posicao", "lances": unidade["lances"], "confronto": unidade["confronto"],
    }
    with JogadorDartQuatro() as motor_dart:
        provador = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
        # A mesma recusa que o gerador faz antes de qualquer prova.
        if vitoria_imediata_quatro(provador.arbitro, estado) is not None:
            linha["fora"] = "de_cara"
        else:
            quem = provador.arbitro.vez_de(estado)
            livre = provador.resultado(estado)
            linha["distancia"] = livre.meios_lances if livre.vencedor == quem else None
            if linha["distancia"] is None:
                linha["fora"] = "sem_vitoria"
            elif not PISO_DE_MEIOS_LANCES <= linha["distancia"] <= unidade["teto"]:
                linha["fora"] = "distancia"
            else:
                for co_tipo in TIPOS:
                    linha[co_tipo] = _uma_prova(motor_dart, estado, co_tipo, unidade)
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


def _uma_prova(motor_dart, estado: EstadoQuatro, co_tipo: str, unidade: dict[str, Any]) -> dict:
    """Uma prova, com um provador SÓ dela (o custo de cada uma sai limpo)."""
    provador = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
    inicio = time.time()
    opcoes = {
        "maximo_de_meios_lances": unidade["teto"],
        "perguntas": unidade["perguntas"],
        "defesa": provas_mod.DEFESA_DO_JOGO,
    }
    if co_tipo == "quatro_sem_o_meio":
        prova = provador.sem_o_meio(estado, **opcoes)
    else:
        prova = provador.objetivo_forcavel(estado, chegada(co_tipo), **opcoes)
    return {
        "passou": prova.passou,
        "lances": prova.dados.get("lances"),
        "estourou": "perguntas" in prova.motivo,
        "perguntas": provador.perguntas,
        "segundos": round(time.time() - inicio, 1),
    }


def controle(partidas, teto: int, perguntas: int) -> bool:
    """O caso fácil com a defesa do jogo: passa em 1, e o jeito errado reprova."""
    casos = casos_de_controle(partidas)
    tudo_certo = True
    with JogadorDartQuatro() as motor_dart:
        for co_tipo in FORCAVEIS:
            unidade = {"teto": teto, "perguntas": perguntas}
            posicoes = casos[co_tipo] + [CONTROLE_MANUAL_PASSA[co_tipo]]
            certas = 0
            for sequencia in posicoes:
                estado = EstadoQuatro(CO_MODALIDADE, ler_sequencia(sequencia))
                achado = _uma_prova(motor_dart, estado, co_tipo, unidade)
                certas += achado["passou"] and achado["lances"] == 1
            errado = _uma_prova(
                motor_dart, EstadoQuatro(CO_MODALIDADE, ler_sequencia(CONTROLE_MANUAL_REPROVA)),
                co_tipo, unidade,
            )
            print(
                f"[controle] {co_tipo} (defesa do jogo): forçável em 1, {certas} de "
                f"{len(posicoes)}; o jeito errado {'REPROVA' if not errado['passou'] else 'PASSA (defeito)'}",
                flush=True,
            )
            tudo_certo = tudo_certo and certas == len(posicoes) and not errado["passou"]
    return tudo_certo


# ═══════════════════════════════════════════════════════════════════════════
# Etapa C - o banco e o relatório
# ═══════════════════════════════════════════════════════════════════════════


def chave(linha: dict[str, Any]) -> tuple:
    """A identidade de uma unidade no diário (o que "já feito" quer dizer)."""
    if linha["etapa"] == "partida":
        return ("partida", linha["confronto"], linha["indice"])
    return ("posicao", linha["lances"])


def ler_diario() -> list[dict[str, Any]]:
    """As linhas já feitas (vazio na 1ª execução)."""
    if not DIARIO.is_file():
        return []
    return [json.loads(l) for l in DIARIO.read_text(encoding="utf-8").splitlines() if l]


def banco(linhas: list[dict[str, Any]], *, teto: int, perguntas: int) -> dict[str, Any]:
    """O banco: por tipo, as posições que passaram, com os lances da pessoa.

    Ordenado pelos lances (o arquivo sai igual para o mesmo diário, e o diff do
    Git mostra só o que mudou).
    """
    tipos: dict[str, list[dict[str, Any]]] = {}
    for co_tipo in TIPOS:
        achadas = [
            {"lances": l["lances"], "lances_da_pessoa": l[co_tipo]["lances"],
             "confronto": l["confronto"]}
            for l in linhas
            if l["etapa"] == "posicao" and (l.get(co_tipo) or {}).get("passou")
        ]
        tipos[co_tipo] = sorted(achadas, key=lambda a: a["lances"])
    return {
        "versao": VERSAO_DO_BANCO,
        "co_modalidade": CO_MODALIDADE,
        "co_versao_motor": contrato_quatro.versao_do_motor(),
        "defesa": provas_mod.DEFESA_DO_JOGO,
        "teto_de_meios_lances": teto,
        "perguntas": perguntas,
        "parametros": {co_tipo: FORCAVEIS.get(co_tipo, {}) for co_tipo in TIPOS},
        "tipos": tipos,
    }


def banco_para_json(dado: dict[str, Any]) -> str:
    """O banco como texto: uma posição por linha, para o diff ler."""
    cabeca = {k: v for k, v in dado.items() if k != "tipos"}
    blocos = []
    for co_tipo, achadas in dado["tipos"].items():
        corpo = ",\n      ".join(json.dumps(a, ensure_ascii=False) for a in achadas)
        blocos.append(f'    "{co_tipo}": [\n      {corpo}\n    ]' if achadas else f'    "{co_tipo}": []')
    return (
        "{" + json.dumps(cabeca, ensure_ascii=False)[1:-1]
        + ',\n  "tipos": {\n' + ",\n".join(blocos) + "\n  }\n}\n"
    )


def relatorio(linhas: list[dict[str, Any]]) -> str:
    """O que a pescaria achou: por confronto, por tipo, e a distância."""
    partidas = [l for l in linhas if l["etapa"] == "partida"]
    posicoes = [l for l in linhas if l["etapa"] == "posicao"]
    na_faixa = [l for l in posicoes if "fora" not in l]
    saida = [
        "Pescaria do golpe duplo, da linha de cinco e do sem o meio (Quatro, T124c)",
        f"{len(partidas)} partidas; {len(posicoes)} posições provadas; {len(na_faixa)} na faixa",
        "",
        "POR CONFRONTO (posições de origem; 'faixa' = vitória livre entre o piso e o teto)",
    ]
    for confronto in CONFRONTOS:
        de_cada = [l for l in posicoes if l["confronto"] == confronto]
        faixa = [l for l in de_cada if "fora" not in l]
        passaram = " · ".join(
            f"{t.removeprefix('quatro_')} {sum(1 for l in faixa if l[t]['passou'])}" for t in TIPOS
        )
        saida.append(
            f"   {confronto:<11} partidas {sum(1 for p in partidas if p['confronto'] == confronto):>4}"
            f" · posições {len(de_cada):>5} · faixa {len(faixa):>4} · {passaram}"
        )
    saida += ["", "POR TIPO (sobre as posições na faixa)"]
    for co_tipo in TIPOS:
        medidas = [l[co_tipo] for l in na_faixa]
        passaram = [m for m in medidas if m["passou"]]
        estouros = sum(1 for m in medidas if m["estourou"])
        distancia = Counter(m["lances"] for m in passaram)
        segundos = sorted(m["segundos"] for m in medidas)
        mediana = segundos[len(segundos) // 2] if segundos else "-"
        saida.append(
            f"   {co_tipo:<22} passaram {len(passaram):>4} de {len(medidas)} · estouraram "
            f"{estouros:>4} · segundos mediana {mediana} máx {segundos[-1] if segundos else '-'}"
        )
        saida.append(
            "      lances da pessoa: "
            + (", ".join(f"{n}: {q}" for n, q in sorted(distancia.items())) or "nenhuma")
        )
    return "\n".join(saida)


def _rodar(pool, funcao, unidades: list[dict[str, Any]], diario, rotulo: str) -> None:
    """Mede as unidades no pool, gravando uma linha do diário por unidade."""
    inicio = time.time()
    for i, linha in enumerate(pool.imap_unordered(funcao, unidades), 1):
        # Gravada na hora: é o que torna a pescaria retomável se a janela fechar.
        diario.write(json.dumps(linha, ensure_ascii=False) + "\n")
        diario.flush()
        if i % 100 == 0 or i == len(unidades):
            print(f"[{rotulo} {i}/{len(unidades)}] {time.time() - inicio:.0f} s", flush=True)


def escrever_saidas(teto: int, perguntas: int) -> None:
    """O banco e o relatório, a partir do diário inteiro."""
    linhas = ler_diario()
    caminho = caminho_do_banco(CO_MODALIDADE)
    # `newline="\n"`: o arquivo é comparado por bytes entre máquinas.
    caminho.write_text(
        banco_para_json(banco(linhas, teto=teto, perguntas=perguntas)),
        encoding="utf-8", newline="\n",
    )
    texto = relatorio(linhas)
    RELATORIO.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\nbanco: {caminho}\nrelatório: {RELATORIO}")


def principal(argumentos: list[str]) -> int:
    """Confere o controle, joga, prova, e escreve o banco e o relatório."""
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--partidas", type=int, default=100)
    leitor.add_argument("--teto", type=int, default=23)
    leitor.add_argument("--perguntas", type=int, default=2000)
    leitor.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    args = leitor.parse_args(argumentos)

    print(f"diário e relatório em {PASTA}", flush=True)
    if not controle(acervo_mod.carregar(CO_MODALIDADE).partidas, args.teto, args.perguntas):
        print("⛔ o controle falhou: o banco sairia do instrumento, e não do jogo. Parando.")
        return 1
    PASTA.mkdir(parents=True, exist_ok=True)
    feitas = {chave(l) for l in ler_diario()}

    try:
        with multiprocessing.Pool(args.processos) as pool, DIARIO.open("a", encoding="utf-8") as diario:
            partidas = [
                {"confronto": confronto, "indice": indice}
                for confronto in CONFRONTOS
                for indice in range(args.partidas)
                if ("partida", confronto, indice) not in feitas
            ]
            print(f"[etapa A] {len(partidas)} partidas a jogar.", flush=True)
            _rodar(pool, jogar, partidas, diario, "partidas")

            jogadas = [l for l in ler_diario() if l["etapa"] == "partida"]
            origem = posicoes_das_partidas(jogadas)
            posicoes = [
                {"lances": lances, "confronto": origem[lances],
                 "teto": args.teto, "perguntas": args.perguntas}
                for lances in em_ordem_de_pescaria(origem)
                if ("posicao", lances) not in feitas
            ]
            print(f"[etapa B] {len(posicoes)} posições a provar (de {len(origem)}).", flush=True)
            _rodar(pool, provar, posicoes, diario, "posições")
    finally:
        # Também no Ctrl+C: o banco do que já foi pescado sai do mesmo jeito.
        if DIARIO.is_file():
            escrever_saidas(args.teto, args.perguntas)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
