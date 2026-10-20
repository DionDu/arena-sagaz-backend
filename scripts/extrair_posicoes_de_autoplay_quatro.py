"""T117 (spec 010) - joga o AUTOPLAY Magno × Tex e grava o acervo do Quatro.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

As posicoes de partida dos desafios do Quatro em Linha vem de partidas reais do
motor (RF-QTR-162), e nao de lances sorteados: e a licao do Pontinhos, escrita
em `job/posicoes_de_autoplay_pontinhos.py`. Aqui nao ha dataset de laboratorio
para aproveitar - o Quatro nao tem CNN -, entao as partidas sao JOGADAS agora,
pelo executavel do motor (`JogadorDartQuatro`), o mesmo codigo que o aparelho
embarca.

⚠️ **Magno contra Tex**: o mais forte contra o segundo mais forte. Partidas de
dois Magnos repetiriam a mesma linha quase sempre (ε de 1,5%); com a Cacau do
outro lado, o jogo acabaria cedo e mal jogado. O Tex erra o suficiente (ε 14%,
bloqueia 90%) para as partidas variarem, e joga bem o suficiente para elas
chegarem ao meio do jogo. **O Magno troca de cor a cada partida**: a posicao
de um desafio pode ter qualquer um dos dois a jogar.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\extrair_posicoes_de_autoplay_quatro.py

Opcoes: `--partidas N` (padrao 400), `--modalidade id` (padrao `tradicional`)
e `--threads N` (padrao: os nucleos da maquina menos um, ate 8).

⚠️ **Quanto demora:** ~1 s por partida numa thread (medido em 20/10/2026: seis
partidas em 5,8 s); com 8 threads, 48 partidas levaram 11 s, e as 400 levam
~1,5 minuto.

⚠️ **A saida e DETERMINISTICA.** Cada partida tem a sua semente (o indice), e
o resultado e reunido pelo indice, e nao pela ordem em que as threads acabam.
Rodar de novo, com o mesmo motor, reescreve um arquivo byte-identico - e e isso
que permite reconstruir o acervo sem deslocar a fila que a semente do dia ja
escolheu. Com um motor NOVO as partidas mudam, e o arquivo tambem: e o mesmo
que trocar o acervo, e se faz de proposito.

═══════════════════════════════════════════════════════════════════════════
O QUE OLHAR PRIMEIRO NA SAIDA
═══════════════════════════════════════════════════════════════════════════

1. **as partidas distintas** (as repetidas saem), e quem venceu;
2. **as posicoes distintas por comprimento** - e o que a fila tem para sortear
   em cada fase da partida. Comprimento curto com poucas posicoes e esperado
   (aberturas repetidas); poucas posicoes no meio do jogo nao e.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ⚠️ Um script em `scripts/` nao e pacote: sem isto, `from job import ...` falha.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows e cp1252; sem isto o primeiro `×` derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job import posicoes_de_autoplay_quatro as acervo_mod  # noqa: E402
from job import semente as semente_mod  # noqa: E402
from motores.nucleo import recursos_por_thread  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import contrato_quatro  # noqa: E402
from motores.quatro.jogador_quatro import JogadorQuatro  # noqa: E402
from motores.quatro.motor_quatro import estado_inicial  # noqa: E402

#: A semente-base da extracao. A partida `i` usa `SEMENTE_DA_EXTRACAO + i`, e
#: cada lance dela a derivacao de `job/semente.semente_do_lance`. ⚠️ Fixa: e o
#: que torna o arquivo reproduzivel.
SEMENTE_DA_EXTRACAO = 20261020

#: Quantas partidas jogar, por padrao.
PARTIDAS_PADRAO = 400


def jogar_partida(
    jogador: JogadorQuatro, co_modalidade: str, indice: int
) -> acervo_mod.PartidaDeAutoplay:
    """Joga a partida [indice] do acervo, do tabuleiro vazio ao fim.

    ⚠️ **O Magno abre nas partidas pares e responde nas impares.** A cor de quem
    joga a posicao sorteada sai da paridade do comprimento; sem a troca, metade
    das posicoes teria sempre o Magno a jogar.
    """
    magno = 1 if indice % 2 == 0 else -1
    semente_da_partida = SEMENTE_DA_EXTRACAO + indice
    estado = estado_inicial(co_modalidade)
    arbitro = jogador.arbitro
    numero = 0
    while not arbitro.veredito(estado).acabou:
        numero += 1
        nivel = NivelDeMotor.SAGAZ if arbitro.vez_de(estado) == magno else NivelDeMotor.TEX
        decisao = jogador.decidir(
            estado, nivel, semente_mod.semente_do_lance(semente_da_partida, numero)
        )
        estado = jogador.aplicar(estado, decisao.lance)
    return acervo_mod.PartidaDeAutoplay(
        lances=estado.lances,
        magno=magno,
        vencedor=int(arbitro.veredito(estado).vencedor),
    )


def sem_repetidas(
    partidas: list[acervo_mod.PartidaDeAutoplay],
) -> list[acervo_mod.PartidaDeAutoplay]:
    """As partidas sem as repetidas, mantendo a primeira e a ordem.

    ⚠️ Uma partida repetida dobraria a chance de as posicoes dela serem
    sorteadas, sem acrescentar posicao nenhuma.
    """
    vistas: set[tuple[str, ...]] = set()
    saida = []
    for partida in partidas:
        if partida.lances in vistas:
            continue
        vistas.add(partida.lances)
        saida.append(partida)
    return saida


def para_json(co_modalidade: str, partidas: list[acervo_mod.PartidaDeAutoplay]) -> str:
    """O arquivo do acervo, como texto (uma partida por linha, para o diff ler)."""
    linhas = [
        json.dumps(
            {"lances": "".join(p.lances), "magno": p.magno, "vencedor": p.vencedor},
            ensure_ascii=False,
        )
        for p in partidas
    ]
    cabeca = {
        "versao": acervo_mod.VERSAO_DO_ACERVO,
        "co_modalidade": co_modalidade,
        "co_versao_motor": contrato_quatro.versao_do_motor(),
        "semente_da_extracao": SEMENTE_DA_EXTRACAO,
    }
    # Montado a mao, e nao por um `json.dumps` do todo: com `indent` cada lance
    # viraria uma linha; sem ele, o arquivo inteiro seria uma linha so.
    corpo = ",\n    ".join(linhas)
    cabecalho = json.dumps(cabeca, ensure_ascii=False)[1:-1]
    return "{" + cabecalho + ',\n  "partidas": [\n    ' + corpo + "\n  ]\n}\n"


def principal(argumentos: list[str]) -> int:
    """Joga as partidas, grava o acervo e imprime o resumo. Devolve o codigo de saida."""
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--partidas", type=int, default=PARTIDAS_PADRAO)
    leitor.add_argument("--modalidade", default="tradicional")
    leitor.add_argument(
        "--threads", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1))
    )
    opcoes = leitor.parse_args(argumentos)

    # Recusa a modalidade que o contrato nao declara antes de abrir um processo.
    contrato_quatro.dimensoes(opcoes.modalidade)
    jogador = JogadorQuatro(opcoes.modalidade)
    print(
        f"⏳ {opcoes.partidas} partidas Magno × Tex em {opcoes.modalidade}, "
        f"{opcoes.threads} thread(s), motor {contrato_quatro.versao_do_motor()}…",
        flush=True,
    )
    inicio = time.perf_counter()
    feitas = [0]

    def uma(indice: int) -> acervo_mod.PartidaDeAutoplay:
        partida = jogar_partida(jogador, opcoes.modalidade, indice)
        # ⚠️ Contador sem trava, de proposito: ele so decide quando imprimir o
        # andamento, e uma soma perdida entre threads pula uma linha de log -
        # nunca muda o acervo, que sai do `map` abaixo.
        feitas[0] += 1
        # Uma linha a cada 100: um processo calado e indistinguivel de um travado.
        if feitas[0] % 100 == 0:
            print(f"   {feitas[0]}/{opcoes.partidas} ({time.perf_counter() - inicio:.0f}s)",
                  flush=True)
        return partida

    with ThreadPoolExecutor(max_workers=opcoes.threads) as pool:
        # `map` devolve na ORDEM dos indices, e nao na de termino: e o que deixa
        # a saida igual com qualquer numero de threads.
        jogadas = list(pool.map(uma, range(opcoes.partidas)))
    # ⛔ O `with` encerra as threads, e nao os processos do motor delas.
    recursos_por_thread.liberar_de_threads_mortas()

    partidas = sem_repetidas(jogadas)
    caminho = acervo_mod.caminho_do_acervo(opcoes.modalidade)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # `newline="\n"`: o arquivo e comparado por bytes entre maquinas.
    caminho.write_text(para_json(opcoes.modalidade, partidas), encoding="utf-8", newline="\n")

    gasto = time.perf_counter() - inicio
    venceu_magno = sum(1 for p in partidas if p.vencedor == p.magno)
    venceu_tex = sum(1 for p in partidas if p.vencedor == -p.magno)
    empates = sum(1 for p in partidas if p.vencedor == 0)
    tamanhos = sorted(len(p.lances) for p in partidas)
    print()
    print(f"✅ {caminho.relative_to(RAIZ)}  ({gasto:.0f}s)")
    print(
        f"   partidas distintas: {len(partidas)} de {len(jogadas)} "
        f"(Magno venceu {venceu_magno} · Tex {venceu_tex} · empates {empates})"
    )
    print(
        f"   lances por partida: min {tamanhos[0]} · mediana "
        f"{tamanhos[len(tamanhos) // 2]} · max {tamanhos[-1]}"
    )
    acervo = acervo_mod.AcervoQuatro(
        co_modalidade=opcoes.modalidade,
        co_versao_motor=contrato_quatro.versao_do_motor(),
        partidas=tuple(partidas),
    )
    print("   posicoes distintas por comprimento (lances jogados: posicoes):")
    distintas = acervo_mod.posicoes_distintas_por_comprimento(acervo)
    pares = [f"{n}:{q}" for n, q in distintas.items()]
    for inicio_da_linha in range(0, len(pares), 10):
        print("     " + "  ".join(pares[inicio_da_linha:inicio_da_linha + 10]))
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
