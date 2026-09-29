"""A BANCADA DE PARIDADE DO PONTINHOS - o servidor joga, o aplicativo reproduz.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT FAZ, E POR QUE ELE E IRMAO DO DAS DAMAS E NAO O MESMO
═══════════════════════════════════════════════════════════════════════════

Ele roda partidas de CPU contra CPU pelo caminho REAL do servidor
(`JogadorPontinhos.decidir`, que desde a T093 decide pelo motor Dart compilado),
guarda a semente-mestra e **todos os lances**, e escreve um arquivo versionado
nas duas pontas. O aplicativo reproduz cada partida em
`test/modulos/jogos/pontinhos/paridade_da_bancada_pontinhos_test.dart`.

⚠️ **E um arquivo SEPARADO do das damas** (`vetores-paridade-motores.json`), e o
motivo e a forma do que precisa viajar:

  ⛔ **A SOFTMAX DA REDE VIAJA COM CADA LANCE.** Em `flutter test` ⛔ ha TFLite -
  a biblioteca nativa nao existe num teste headless, e nenhum teste do
  aplicativo roda a CNN hoje (conferido em 26/09/2026). Se a bancada dependesse
  da rede, ela ⛔ existiria do lado do aplicativo. Gravando os 31 numeros que a
  rede devolveu, o teste reproduz **tudo o que a T093 mudou** - a
  renormalizacao, a ordenacao, as tres fases e o sorteador - sem inferir nada.

  ⚠️ **E o que fica de fora e nomeado:** a inferencia em si. Ela ja tem prova
  propria (`scripts/conferir_runtime_inferencia.py`, portao do build da imagem
  do job) e volta a ser conferida no aparelho pela T094a.

O documento tem a mesma FORMA do das damas - `de_documento`, `versao`, `motor`,
`partidas` -, e de proposito: quem aprendeu a ler um le o outro.

═══════════════════════════════════════════════════════════════════════════
COMO RODAR
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\gerar_vetores_paridade_pontinhos.py

⚠️ **Sempre que o motor mudar** - e o teste do backend avisa, comparando o
resumo gravado com o dos fontes do espelho de hoje.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from job import semente as semente_mod  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.pontinhos import jogador_dart_pontinhos  # noqa: E402
from motores.pontinhos.motor_pontinhos import (  # noqa: E402
    TAMANHO,
    MotorPontinhos,
    estado_inicial,
)
from motores.pontinhos.politica import (  # noqa: E402
    JogadorPontinhos,
    parametros_do_nivel,
)

#: A versao do documento. Sobe quando a FORMA muda, e nunca por conteudo novo:
#: um leitor da versao 1 tem de saber, pelo numero, que nao entende o arquivo.
VERSAO = 1

#: As duas copias, nos mesmos lugares em que as da bancada de damas moram.
DESTINOS = (
    RAIZ / "contratos" / "vetores-paridade-pontinhos.json",
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-paridade-pontinhos.json",
)

#: As sementes-mestras de cada partida de uma combinacao.
#:
#: ⚠️ **Sao as MESMAS tres da bancada de damas**, e nao por comodidade: a
#: primeira e a semente real do desafio que revelou o defeito de 26/09/2026, e
#: repetir os numeros entre as duas bancadas deixa uma falha comparavel com a
#: outra sem ninguem precisar traduzir nada.
SEMENTES_MESTRAS: tuple[int, ...] = (697571591, 12345, 4_000_000_007)

#: Os quatro degraus, do mais fraco ao mais forte. ⛔ **Nenhum fica de fora** -
#: os tres episodios de divergencia moraram nos niveis fracos ou so apareceram
#: neles, e uma bancada que rodasse so o Magno repetiria o ponto cego.
NIVEIS: tuple[NivelDeMotor, ...] = tuple(NivelDeMotor)

#: ⚠️ **Aqui TODOS os niveis jogam com as tres sementes** - inclusive o Sagaz, e
#: e a diferenca em relacao a bancada de damas.
#:
#: Nas damas o Sagaz ⛔ consulta o sorteador (`ruido=0`, `chance_de_errar=0`), e
#: as tres sementes dariam a mesma partida. Aqui ⛔: o Magno do Pontinhos
#: **sorteia a abertura** quando e ele quem abre (a Fase 0 da politica, que
#: existe desde 30/07/2026 porque com `epsilon == 0` ele abria toda partida com a
#: mesma aresta). Tres sementes sao tres aberturas, e tres partidas diferentes.
SEMENTES_POR_NIVEL: dict[NivelDeMotor, int] = {}

#: Quantos meios-lances uma partida pode ter antes de o script desistir.
#:
#: ⚠️ **No Pontinhos isto ⛔ e um freio: e aritmetica.** O tabuleiro 4x3 tem 31
#: tracos, cada lance ocupa um, e nenhum lance os devolve - entao toda partida
#: acaba em exatamente 31 meios-lances. O numero esta aqui para o arquivo dizer
#: onde parou, como o das damas diz, e para uma partida que nao terminasse se
#: denunciar em vez de correr para sempre.
MAXIMO_DE_MEIOS_LANCES = 31


def argumentos_do_nivel(nivel: NivelDeMotor) -> dict[str, Any]:
    """O que define aquele nivel, como dado.

    ⚠️ **Sai do contrato de dificuldade, e nao de numeros escritos aqui.** Se
    este script guardasse os numeros por conta propria, o arquivo diria que os
    dois lados concordam com uma terceira escrituracao que ninguem usa para
    jogar. O teste do aplicativo compara este bloco campo a campo com o enum
    `Dificuldade` do motor - e e essa comparacao que acusa o defeito **pelo
    nome**, antes de qualquer partida.
    """
    p = parametros_do_nivel(nivel)
    return {
        "chave": p.chave,
        "epsilon": p.epsilon,
        "usa_captura_gulosa": p.usa_captura_gulosa,
        "timer_segundos": p.timer_segundos,
    }


def jogar_uma_partida(
    *,
    jogador: JogadorPontinhos,
    nivel: NivelDeMotor,
    nu_semente: int,
) -> dict[str, Any]:
    """Uma partida inteira de CPU contra CPU, no mesmo nivel dos dois lados.

    ⚠️ **Os dois lados no MESMO nivel, e nao e detalhe.** O que se quer comparar
    e o adversario que o aparelho enfrenta; pondo um nivel de cada lado, metade
    dos lances do arquivo mediria uma combinacao que o desafio nao produz.

    ⚠️ **A softmax e pedida ANTES da decisao**, e nao depois: e exatamente a
    mesma chamada que a politica faz por baixo, e e ela que o arquivo guarda para
    o aplicativo reproduzir o lance sem inferir.
    """
    motor = jogador.arbitro
    estado = estado_inicial()
    lances: list[dict[str, Any]] = []
    co_desfecho = "teto_de_lances"

    for n in range(1, MAXIMO_DE_MEIOS_LANCES + 1):
        veredito = motor.veredito(estado)
        if veredito.acabou:
            co_desfecho = veredito.co_motivo or "acabou"
            break

        # ⚠️ A semente do lance **pela conta do aplicativo** - a mesma funcao que
        # o gerador de desafios usa. Ver `job/semente.py`.
        semente = semente_mod.semente_do_lance(nu_semente, n)
        softmax = motor.softmax(estado)
        decisao = jogador.decidir(estado, nivel, semente=semente)
        lances.append(
            {
                "n": n,
                "semente": semente,
                "vez_de": estado.vez_de,
                "lance": decisao.lance,
                "co_acao": decisao.co_acao,
                # ⛔ Os 31 numeros crus, **antes** da mascara e da
                # renormalizacao: e o que o aplicativo tem na mao quando chama
                # `ranquearDaSoftmax`, e guardar o vetor ja renormalizado
                # esconderia justamente a conta que se quer comparar.
                "softmax": softmax,
            }
        )
        estado = motor.aplicar(estado, decisao.lance)

    # ⚠️ **O desfecho e decidido DEPOIS do laco, e nao por ele ter terminado.**
    # No Pontinhos os 31 lances enchem o tabuleiro exatamente no ultimo, entao o
    # laco sai por esgotar o alcance e ⛔ pelo `break` - e gravar
    # "teto_de_lances" ali diria que a bancada desistiu de uma partida que
    # acabou sozinha. Quem responde e o veredito, que e o arbitro.
    veredito = motor.veredito(estado)
    if veredito.acabou:
        co_desfecho = veredito.co_motivo or "acabou"

    return {
        "id": f"pontinhos-{TAMANHO}-{nivel.value}-{nu_semente}",
        "co_jogo": "pontinhos",
        "co_tamanho_tabuleiro": TAMANHO,
        "co_nivel": nivel.value,
        "nu_semente": nu_semente,
        "argumentos": argumentos_do_nivel(nivel),
        "lances": lances,
        "sequencia_final": list(estado.lances),
        "placar_final": {"1": estado.placar[1], "-1": estado.placar[-1]},
        "co_desfecho": co_desfecho,
        "vencedor": veredito.vencedor,
        "maximo_de_meios_lances": MAXIMO_DE_MEIOS_LANCES,
    }


def montar(
    *,
    niveis: tuple[NivelDeMotor, ...],
    sementes: tuple[int, ...],
    falar: bool = True,
) -> dict[str, Any]:
    """O documento inteiro, com as partidas em ordem estavel.

    ⚠️ **Ordem estavel importa**: as duas copias sao comparadas byte a byte, e
    uma reordenacao inocente faria o cadeado acusar divergencia onde nao ha.
    """
    jogador = JogadorPontinhos()
    partidas: list[dict[str, Any]] = []
    comeco = time.monotonic()

    for nivel in niveis:
        quantas = SEMENTES_POR_NIVEL.get(nivel, len(sementes))
        for nu_semente in sementes[:quantas]:
            t0 = time.monotonic()
            partida = jogar_uma_partida(
                jogador=jogador, nivel=nivel, nu_semente=nu_semente
            )
            partidas.append(partida)
            if falar:
                print(
                    f"  {partida['id']}: "
                    f"{len(partida['lances'])} meios-lances, "
                    f"{partida['co_desfecho']}, "
                    f"placar {partida['placar_final']}, "
                    f"{time.monotonic() - t0:.1f}s",
                    flush=True,
                )

    identificadores = [p["id"] for p in partidas]
    assert len(set(identificadores)) == len(identificadores), (
        f"ha identificador de partida repetido: {identificadores}"
    )

    if falar:
        print(f"total: {time.monotonic() - comeco:.1f}s", flush=True)

    return {
        "de_documento": "Bancada de paridade do Pontinhos (T093/T094). GERADO "
        "por scripts/gerar_vetores_paridade_pontinhos.py - nao edite a mao. O "
        "aplicativo reproduz estas partidas em test/modulos/jogos/pontinhos/"
        "paridade_da_bancada_pontinhos_test.dart.",
        "versao": VERSAO,
        "co_tamanho_tabuleiro": TAMANHO,
        # ⚠️ Rotulo → indice do neuronio, UMA vez no documento. Ele e igual em
        # todas as partidas, e repeti-lo em cada lance multiplicaria o arquivo
        # por nada. O aplicativo confere o dele contra este antes de reproduzir
        # qualquer partida: um mapeamento diferente faria os dois lados lerem a
        # mesma softmax como tracos diferentes.
        "mapeamento": MotorPontinhos().mapeamento_de_rotulos,
        # De que motor sairam estes lances. ⚠️ E o SHA-256 dos fontes do espelho,
        # que e o mesmo resumo que o executavel carimba e que o aplicativo
        # confere contra os arquivos dele - um arquivo gerado por um motor
        # antigo se denuncia por aqui, e nao por uma divergencia misteriosa.
        "motor": {
            "pontinhos": jogador_dart_pontinhos.jogador_compartilhado().resumo_do_motor,
        },
        "partidas": partidas,
    }


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Gera as partidas da bancada de paridade do Pontinhos (T093).",
    )
    analisador.add_argument(
        "--niveis",
        nargs="+",
        default=None,
        help="quais niveis (padrao: os quatro)",
    )
    analisador.add_argument(
        "--partidas",
        type=int,
        default=len(SEMENTES_MESTRAS),
        help="quantas sementes-mestras por nivel (padrao: todas)",
    )
    analisador.add_argument(
        "--amostra",
        action="store_true",
        help=(
            "escreve num arquivo temporario e NAO toca as copias versionadas - "
            "e o modo de conferir que o caminho esta de pe"
        ),
    )
    args = analisador.parse_args(argv)

    niveis = (
        tuple(NivelDeMotor(n) for n in args.niveis) if args.niveis else NIVEIS
    )
    sementes = SEMENTES_MESTRAS[: max(1, args.partidas)]
    quantas = sum(
        len(sementes[: SEMENTES_POR_NIVEL.get(nivel, len(sementes))])
        for nivel in niveis
    )
    print(f"{len(niveis)} niveis = {quantas} partidas", flush=True)

    documento = montar(niveis=niveis, sementes=sementes)

    # `ensure_ascii=False` mantem os acentos legiveis no diff; `indent=2` deixa o
    # arquivo revisavel. O `\n` final e explicito, e a escrita usa `newline=""`
    # porque este arquivo e comparado por SHA-256 entre repositorios - o
    # `write_text` do Windows converteria LF em CRLF e as duas copias deixariam
    # de bater por um motivo que nao tem nada a ver com o conteudo.
    texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"

    if args.amostra:
        # ⚠️ **Fora do repositorio, de proposito.** Uma amostra e um arquivo
        # parcial - falta nivel -, e um arquivo parcial largado em `contratos/`
        # seria commitado por engano um dia.
        destinos: tuple[Path, ...] = (
            Path(tempfile.gettempdir()) / "amostra-paridade-pontinhos.json",
        )
        print("AMOSTRA: as copias versionadas NAO foram tocadas.")
    else:
        destinos = DESTINOS

    for destino in destinos:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8", newline="") as arquivo:
            arquivo.write(texto)
        print(f"escrito: {destino} ({len(texto.encode('utf-8'))} bytes)")

    total_de_lances = sum(len(p["lances"]) for p in documento["partidas"])
    print(
        f"{len(documento['partidas'])} partidas e {total_de_lances} lances, "
        f"versao {VERSAO}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
