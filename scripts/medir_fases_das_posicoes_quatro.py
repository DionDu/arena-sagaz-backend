"""T124c (spec 010), defeito 2 - o que o acervo do Quatro TEM, fase a fase.

═══════════════════════════════════════════════════════════════════════════
A PERGUNTA
═══════════════════════════════════════════════════════════════════════════

A régua de 20/10/2026 (histórico do backend, "2026-10-20 (5)") deixou dois tipos
sem candidato por falta de POSIÇÃO, e não por falta de medição:

- *"Vença {personagem} em até N lances"* (`quatro_vencer_em_n`): a prova pede a
  vitória forçada de quem tem a vez em EXATAMENTE `2N - 1` meios-lances;
- *"Segure {personagem}: não perca a partida"* (`quatro_segurar_magno`): a prova
  pede o empate PROVADO, e a maioria das colunas perdendo.

A tarefa propõe duas saídas - escolher o LADO da posição, ou um acervo dirigido
por tipo -, e manda medir antes de mexer. Este script responde, para cada
comprimento de posição (quantos lances já foram jogados), o que a busca PROVA
sobre ela, separado pelo lado de quem teria a vez: o do Magno ou o do Tex na
partida de autoplay de onde ela saiu.

⚠️ **O lado importa, e a fase também.** Uma amostra de 21/10 mostrou as vitórias
forçadas a 14-23 meios-lances com 12 a 18 lances jogados - longe dos 9 do
`{lances: 5}` -, e a 2-18 com 22 a 28. Por isso a tabela é por COMPRIMENTO, e não
só pela faixa que o editorial usa hoje.

═══════════════════════════════════════════════════════════════════════════
O CONTROLE, ANTES DA MEDIÇÃO
═══════════════════════════════════════════════════════════════════════════

Um instrumento novo prova o caso fácil antes de responder o difícil. Em toda
partida decidida do acervo, a posição UM lance antes do fim tem a vez de quem
venceu, e ele vence em 1 meio-lance. Se a busca não disser isso nessas posições,
o script para: a tabela que viria depois mediria o instrumento, e não o acervo.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\medir_fases_das_posicoes_quatro.py

Opções: `--de 8 --ate 34` (os comprimentos), `--amostra 80` (posições DISTINTAS
por comprimento; menos, se o acervo não tiver tantas), `--threads 8`.

⚠️ **Quanto demora:** medido em 21/10/2026, a busca custa ~0,35 s por posição com
12 a 18 lances jogados e ~0,01 s com 22 a 28. Com o padrão, ~1 a 2 minutos em 8
threads. ⚠️ A saída é determinística (a amostra sai de uma semente fixa).

═══════════════════════════════════════════════════════════════════════════
O QUE OLHAR PRIMEIRO NA SAÍDA
═══════════════════════════════════════════════════════════════════════════

1. a linha do CONTROLE (tem de ser "N de N");
2. na tabela, as colunas `N=4` a `N=7`: quantas posições daquele comprimento
   passariam na prova do *"Vença em N"*, por lado - é onde o preparo do
   editorial deveria cair;
3. a coluna `segure`: quantas passam na prova inteira do *"Segure"* (empate
   provado e a maioria das colunas perdendo), por lado.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

# ⚠️ Um script em `scripts/` não é pacote: sem isto, `from job import ...` falha.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ⚠️ O console do Windows é cp1252; sem isto o primeiro `×` derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from job import posicoes_de_autoplay_quatro as acervo_mod  # noqa: E402
from job import provas_quatro as provas_mod  # noqa: E402
from job.gerador import vitoria_imediata_quatro  # noqa: E402
from motores.quatro.jogador_dart_quatro import JogadorDartQuatro  # noqa: E402
from motores.quatro.motor_quatro import EstadoQuatro  # noqa: E402

#: A semente da amostra. Fixa: rodar de novo dá a mesma tabela.
SEMENTE_DA_AMOSTRA = 20261021

#: Os N do *"Vença em N"* que a tabela mostra. O editorial mediu 5 e 6; a faixa
#: em volta diz se outro N caberia melhor no que o acervo tem.
NS_DO_VENCER = (3, 4, 5, 6, 7, 8)

#: Os dois lados, pelo papel na partida de autoplay de onde a posição saiu.
LADOS = ("magno", "tex")


@dataclass
class Contagem:
    """O que se provou nas posições de UM comprimento e UM lado.

    Atributos:
        total: posições medidas.
        de_cara: quem tem a vez vence no 1º lance (o job descarta antes da prova).
        vence / empata / perde / aberto: o resultado provado para quem tem a
            vez; `aberto` = a busca não decidiu dentro do teto.
        distancias: nas que `vence`, quantas a cada distância em meios-lances.
        segure: quantas passam na prova inteira do *"Segure"*.
    """

    total: int = 0
    de_cara: int = 0
    vence: int = 0
    empata: int = 0
    perde: int = 0
    aberto: int = 0
    distancias: Counter = field(default_factory=Counter)
    segure: int = 0

    def somar(self, outra: "Contagem") -> None:
        """Junta a contagem de outra thread nesta."""
        self.total += outra.total
        self.de_cara += outra.de_cara
        self.vence += outra.vence
        self.empata += outra.empata
        self.perde += outra.perde
        self.aberto += outra.aberto
        self.distancias.update(outra.distancias)
        self.segure += outra.segure


def amostrar(
    partidas: tuple[acervo_mod.PartidaDeAutoplay, ...],
    comprimento: int,
    quantas: int,
    sorteio: random.Random,
) -> list[tuple[tuple[str, ...], str]]:
    """Até [quantas] posições DISTINTAS com [comprimento] lances, e o lado de cada.

    O lado é o de quem tem a vez: com `n` lances jogados, a vez é do jogador 1
    (`+1`, quem abre) quando `n` é par. Se o Magno jogou com essa cor naquela
    partida, a posição é "do lado do Magno".

    ⚠️ **Distintas**: aberturas repetidas dão o mesmo prefixo em partidas
    diferentes. A mesma posição contada duas vezes pesaria em dobro na tabela.
    """
    vistas: dict[tuple[str, ...], str] = {}
    for partida in partidas:
        # O prefixo precisa de um lance a jogar: mais curto que a partida inteira.
        if len(partida.lances) <= comprimento:
            continue
        vez = 1 if comprimento % 2 == 0 else -1
        prefixo = partida.lances[:comprimento]
        # A primeira partida que alcança o prefixo decide o lado (a cor de quem
        # tem a vez é a mesma em todas; quem a jogava, Magno ou Tex, pode mudar).
        vistas.setdefault(prefixo, "magno" if vez == partida.magno else "tex")
    todas = sorted(vistas.items())
    sorteio.shuffle(todas)
    return todas[:quantas]


def medir_um_comprimento(
    comprimento: int, posicoes: list[tuple[tuple[str, ...], str]], co_modalidade: str
) -> dict[str, Contagem]:
    """Mede as posições de um comprimento, num processo do motor SÓ desta tarefa.

    ⚠️ **Um processo por tarefa, aberto e fechado pelo `with`**: o processo de
    uma thread de pool sobrevive ao `with` do pool (memória
    "pool-fechado-deixa-os-processos"), e aqui quem o encerra é o próprio bloco.
    """
    contagens = {lado: Contagem() for lado in LADOS}
    with JogadorDartQuatro() as motor:
        provador = provas_mod.ProvadorQuatro(co_modalidade, motor)
        for lances, lado in posicoes:
            conta = contagens[lado]
            conta.total += 1
            estado = EstadoQuatro(co_modalidade, lances)
            # A mesma recusa que o gerador faz antes de qualquer prova.
            if vitoria_imediata_quatro(provador.arbitro, estado) is not None:
                conta.de_cara += 1
                continue
            quem = provador.arbitro.vez_de(estado)
            achado = provador.resultado(estado)
            if achado.vencedor is None:
                conta.aberto += 1
            elif achado.vencedor == 0:
                conta.empata += 1
                # A prova inteira do Segure só faz sentido aqui (ela começa
                # pedindo o empate), e só aqui custa as sete perguntas por coluna.
                if provador.segurar_magno(estado).passou:
                    conta.segure += 1
            elif achado.vencedor == quem:
                conta.vence += 1
                conta.distancias[achado.meios_lances] += 1
            else:
                conta.perde += 1
    return contagens


def controle(partidas, co_modalidade: str, quantas: int, sorteio: random.Random) -> bool:
    """A busca acerta o caso fácil? Um lance antes do fim, quem venceu vence em 1."""
    decididas = [p for p in partidas if p.vencedor != 0]
    amostra = sorteio.sample(decididas, min(quantas, len(decididas)))
    certas = 0
    with JogadorDartQuatro() as motor:
        provador = provas_mod.ProvadorQuatro(co_modalidade, motor)
        for partida in amostra:
            achado = provador.resultado(EstadoQuatro(co_modalidade, partida.lances[:-1]))
            certas += achado.vencedor == partida.vencedor and achado.meios_lances == 1
    print(f"[controle] um lance antes do fim, quem venceu vence em 1: {certas} de {len(amostra)}")
    return certas == len(amostra)


def imprimir(resultado: dict[int, dict[str, Contagem]]) -> None:
    """A tabela: uma linha por comprimento e lado."""
    cabecalho = (
        f"{'lances':>6} {'lado':<5} {'n':>4} {'cara':>4} {'vence':>5} {'empata':>6} "
        f"{'perde':>5} {'aberto':>6} | "
        + " ".join(f"N={n:<2}" for n in NS_DO_VENCER)
        + f" | {'segure':>6}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for comprimento in sorted(resultado):
        for lado in LADOS:
            c = resultado[comprimento][lado]
            if c.total == 0:
                continue
            # Passa no "Vença em N" quem vence à força em exatamente 2N - 1.
            por_n = " ".join(f"{c.distancias[2 * n - 1]:>4}" for n in NS_DO_VENCER)
            print(
                f"{comprimento:>6} {lado:<5} {c.total:>4} {c.de_cara:>4} {c.vence:>5} "
                f"{c.empata:>6} {c.perde:>5} {c.aberto:>6} | {por_n} | {c.segure:>6}"
            )


def principal(argumentos: list[str]) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--de", type=int, default=8)
    leitor.add_argument("--ate", type=int, default=34)
    leitor.add_argument("--amostra", type=int, default=80)
    leitor.add_argument("--modalidade", default="tradicional")
    leitor.add_argument("--threads", type=int, default=8)
    args = leitor.parse_args(argumentos)

    acervo = acervo_mod.carregar(args.modalidade)
    print(
        f"[acervo] {len(acervo.partidas)} partidas de {args.modalidade} "
        f"({acervo.co_versao_motor})"
    )
    sorteio = random.Random(SEMENTE_DA_AMOSTRA)
    if not controle(acervo.partidas, args.modalidade, 20, sorteio):
        print("⛔ o controle falhou: a tabela mediria o instrumento. Parando.")
        return 1

    # A amostra de cada comprimento sai ANTES das threads, de um sorteio só: a
    # ordem em que as threads terminam não muda quais posições foram medidas.
    tarefas = {
        n: amostrar(acervo.partidas, n, args.amostra, sorteio)
        for n in range(args.de, args.ate + 1)
    }
    inicio = time.time()
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futuros = {
            n: pool.submit(medir_um_comprimento, n, posicoes, args.modalidade)
            for n, posicoes in tarefas.items()
        }
        resultado = {n: futuro.result() for n, futuro in futuros.items()}
    print(f"[medicao] {sum(len(p) for p in tarefas.values())} posicoes em {time.time() - inicio:.0f} s\n")
    imprimir(resultado)

    # O resumo por lado, somando os comprimentos: é o número que responde
    # "escolher o lado ajuda?".
    print()
    for lado in LADOS:
        soma = Contagem()
        for por_lado in resultado.values():
            soma.somar(por_lado[lado])
        por_n = ", ".join(f"N={n}: {soma.distancias[2 * n - 1]}" for n in NS_DO_VENCER)
        print(
            f"[{lado}] {soma.total} posicoes: vence {soma.vence}, empata {soma.empata}, "
            f"perde {soma.perde}, aberto {soma.aberto}, de cara {soma.de_cara}; "
            f"segure {soma.segure}; {por_n}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
