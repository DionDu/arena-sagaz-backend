"""T094 - A BANCADA DE PARIDADE: o servidor joga, o aplicativo reproduz.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

Ideia e decisao do dono, 26/09/2026, depois do **terceiro** episodio de
divergencia entre o motor do aplicativo e o do servidor
(`docs/DECISOES-do-dono.md` §8zj no repositorio do app, item 2):

    "O codigo do nosso backend rodaria inumeras partidas de autoplay, e
    guardaria a semente. Elas ficariam salvas em algum lugar, o App rodaria as
    mesmas partidas com mesma semente e 100% dos lances seriam comparados."

Este script e a metade do servidor: ele joga as partidas e escreve o arquivo.
A outra metade e o teste do aplicativo,
`test/modulos/jogos/damas/paridade_da_bancada_test.dart`, que reproduz cada
partida lance a lance e para na **primeira** divergencia.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE AS TRAVAS DE HOJE NAO OLHAM: OS ARGUMENTOS
═══════════════════════════════════════════════════════════════════════════

As travas que existiam ate aqui comparam **SHA-256 de arquivo**:

    app        == laboratorio   `paridade_motor_test.dart`
    espelho    == laboratorio   `scripts/espelhar_laboratorio.py` + manifesto
    executavel == espelho       `motores/damas/jogador_dart.py`, na abertura

Elas provam que os dois lados rodam **o mesmo codigo**. Os tres episodios de
divergencia foram todos o mesmo codigo recebendo **argumentos diferentes**:

    25/09   o RELOGIO        10 s mordiam no servidor e nunca no aparelho
    25/09   o TETO da camada 60 mil no job contra 288 mil no contrato
    26/09   a SEMENTE        duas contas para derivar a semente do lance

⛔ **Nenhuma trava olhava para argumento**, e por isso os tres passaram. Esta
bancada olha: ela compara o **lance escolhido** e o **numero de nos gastos** em
100% dos lances de partidas inteiras, que e onde argumento diferente aparece.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS DECISOES DO FORMATO, E O PORQUE DE CADA UMA
═══════════════════════════════════════════════════════════════════════════

1. ⛔ **A semente vem pelo caminho do DESAFIO** (`job/semente.py`): uma mestra
   por partida, e `semente_do_lance(mestra, n)` em cada lance. Uma semente
   propria da bancada provaria um caminho que o desafio nao percorre - que e
   exatamente como o defeito de 26/09 passou por baixo dos vetores.

2. ⛔ **Os niveis FRACOS entram.** Os tres episodios moraram neles ou so
   apareceram neles: o Sagaz tem `ruido=0` e `chance_de_errar=0,0` e nao
   consulta o sorteador, entao uma varredura so do Magno repetiria o ponto cego
   que deixou a semente passar.

3. ⚠️ **Os nos entram no arquivo, e nao so o lance.** Dois motores podem
   escolher o mesmo lance parando em pontos diferentes da busca; foi comparando
   **nos** que o defeito do relogio apareceu, em 25/09. Lance igual com nos
   diferentes e o aviso de que a proxima posicao pode ja nao ser igual.

4. ⚠️ **Os ARGUMENTOS do nivel entram no arquivo**, no bloco `argumentos`. O
   aplicativo os confere contra o `niveisPorIdentificador` dele antes de jogar
   qualquer lance: e a unica parte desta bancada que acusa o defeito **pelo
   nome** em vez de pelo sintoma.

5. ⚠️ **As sementes-mestras sao FIXAS**, e nao sorteadas na hora. Rodar duas
   vezes tem de dar o mesmo arquivo - senao o `git diff` do dia mostra um
   arquivo inteiro trocado e ninguem consegue revisar o que mudou de verdade.

6. ⚠️ **As duas copias sao byte-identicas**, como as dos vetores de verificacao,
   e ha teste conferindo o SHA-256 das duas.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA
═══════════════════════════════════════════════════════════════════════════

A matriz inteira (as 4 modalidades x os 4 niveis x 3 partidas) leva **dezenas de
minutos**, e por isso e comando do dono:

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\gerar_vetores_paridade_motores.py

Uma amostra, para conferir que o caminho esta de pe (segundos), que escreve num
arquivo temporario e **nao** toca as duas copias versionadas:

    .venv\\Scripts\\python scripts\\gerar_vetores_paridade_motores.py --amostra
        --modalidades brasileira --niveis cacau --partidas 1

⚠️ **Precisa do motor Dart compilado** (`servidor_de_lances_damas.exe`), como
todo o resto do servidor desde 25/09. Sem ele, o script para na primeira partida
com a receita de como compilar.
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
from motores.damas import jogador_dart  # noqa: E402
from motores.damas.contrato_damas import (  # noqa: E402
    modalidades_declaradas,
    parametros_do_nivel,
)
from motores.damas.motor_damas import (  # noqa: E402
    NIVEIS_QUE_USAM_A_BASE,
    EstadoDamas,
    MotorDamas,
)
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402

#: A versao do documento. Sobe quando a FORMA muda, e nunca por conteudo novo:
#: um leitor da versao 1 tem de saber, pelo numero, que nao entende o arquivo.
VERSAO = 1

#: As duas copias. A do frontend fica em `contracts/` da spec, ao lado dos
#: vetores de verificacao; a daqui fica em `contratos/`.
DESTINOS = (
    RAIZ / "contratos" / "vetores-paridade-motores.json",
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-paridade-motores.json",
)

#: As sementes-mestras de cada partida de uma combinacao.
#:
#: ⚠️ **Numeros escolhidos e fixos.** O primeiro e a semente real do desafio que
#: revelou o defeito de 26/09 (`449864e6-...`, damas_sobreviver anglo contra a
#: Pita) - se algum dia a conta da semente voltar a divergir, e esta partida que
#: acusa primeiro. As outras duas sao arbitrarias, dentro da faixa que
#: `job/semente.py` declara (1 a 2^32-1), e escolhidas distantes uma da outra.
SEMENTES_MESTRAS: tuple[int, ...] = (697571591, 12345, 4_000_000_007)

#: Os quatro degraus, do mais fraco ao mais forte. ⛔ **Nenhum fica de fora** -
#: ver a decisao 2 do cabecalho.
NIVEIS: tuple[NivelDeMotor, ...] = tuple(NivelDeMotor)

#: Quantos meios-lances uma partida pode ter antes de o script desistir.
#:
#: ⚠️ Nao e um limite de regra, e sim uma rede: duas CPUs fracas se arrastando
#: podem empurrar uma partida para centenas de lances sem nunca empatar por
#: regra, e o arquivo cresceria sem nada acrescentar. Quando ela morde, o
#: desfecho gravado e `teto_de_lances` - e o aplicativo compara ate ali,
#: exatamente onde o servidor parou.
MAXIMO_DE_MEIOS_LANCES = 160

#: O teto de alguns niveis e menor, e o motivo e o **custo do lance**.
#:
#: ⚠️ O Sagaz gasta 288 mil nos por lance, e quem paga duas vezes por isso e o
#: `flutter test`. Medido em 28/09/2026: **~0,43 s por lance dos dois lados** -
#: o executavel compilado aqui e a VM do Dart la levam praticamente o mesmo
#: tempo, porque o trabalho e a busca. Uma partida inteira do Sagaz em cada
#: modalidade
#: acrescentaria dezenas de minutos a uma suite que o dono roda o dia todo - e
#: cadeado que ninguem aguenta rodar e cadeado desligado, que e o defeito que
#: esta bancada existe para evitar.
#:
#: ⛔ **Nao e a mesma coisa que cobrir menos.** Os lances gravados sao comparados
#: em 100%, e o Sagaz e o unico nivel que ⛔ consulta o sorteador (`ruido=0`,
#: `chance_de_errar=0`): o que ele acrescenta a bancada e a busca funda, que
#: diverge - quando diverge - nos primeiros lances, por teto de nos ou relogio.
#: Foram os dois primeiros episodios, e os dois apareceram na abertura.
MAXIMO_POR_NIVEL: dict[NivelDeMotor, int] = {NivelDeMotor.SAGAZ: 30}


def maximo_de_meios_lances(nivel: NivelDeMotor) -> int:
    """Quantos meios-lances aquele nivel joga nesta bancada."""
    return MAXIMO_POR_NIVEL.get(nivel, MAXIMO_DE_MEIOS_LANCES)


#: Quantas sementes-mestras cada nivel merece.
#:
#: ⛔ **O Sagaz joga UMA partida por modalidade, e nao tres - porque as tres
#: seriam a MESMA.** Ele tem `ruido=0` e `chance_de_errar=0`: nao consulta o
#: sorteador, e a semente nao muda um lance sequer. Medido em 28/09/2026, na
#: brasileira, com as sementes 697571591 e 12345: os 30 lances e os 30 numeros
#: de nos sairam identicos.
#:
#: ⚠️ **E e por isso que o defeito da semente, em 26/09, era invisivel contra o
#: Magno**: os desafios dele se reproduziam mesmo com a semente errada. Guardar
#: aqui a mesma partida tres vezes engordaria o arquivo e a suite sem
#: acrescentar uma unica comparacao nova.
SEMENTES_POR_NIVEL: dict[NivelDeMotor, int] = {NivelDeMotor.SAGAZ: 1}


def sementes_do_nivel(
    nivel: NivelDeMotor, sementes: tuple[int, ...]
) -> tuple[int, ...]:
    """As sementes-mestras que aquele nivel usa, na ordem."""
    return sementes[: SEMENTES_POR_NIVEL.get(nivel, len(sementes))]


class _ContadorDeNos:
    """Um `LimiteDeBusca` que nao limita nada: so anota quantos nos custou.

    ⚠️ **Ele existe para que o script use o caminho REAL do servidor.**
    `MotorDamas.escolher_lance` devolve so o texto do lance; quem recebe o
    numero de nos e o `limite`, por `contar_no`. Chamar o `jogador_dart`
    diretamente daria os nos, mas criaria uma **segunda** montagem dos
    argumentos - que e justamente a especie de coisa que esta bancada existe
    para achar.

    Os tetos sao os maiores possiveis de proposito: desde 25/09/2026 o teto de
    nos de quem joga e o do **contrato**, e o da camada nao o corta mais
    (`motores/damas/motor_damas.py`). Um teto pequeno aqui nao mudaria o lance
    (este caminho ja ignora o limite), mas deixaria no arquivo a impressao de
    que a bancada joga com freio.
    """

    def __init__(self) -> None:
        self.nos = 0

    @property
    def nos_maximos(self) -> int:
        return 10**12

    @property
    def segundos_maximos(self) -> float:
        return float("inf")

    def cancelado(self) -> bool:
        return False

    def contar_no(self, quantos: int = 1) -> None:
        self.nos += quantos


def argumentos_do_nivel(nivel: NivelDeMotor) -> dict[str, Any]:
    """O que o servidor manda ao motor naquele nivel, como dado.

    ⚠️ **Sai do contrato, e nao de numeros escritos aqui.** Se este script
    guardasse os numeros por conta propria, o arquivo diria que os dois lados
    concordam com uma terceira escrituracao que ninguem usa para jogar.

    ⛔ **`tempo_maximo` nao entra**, e a ausencia e a informacao: o servidor joga
    **sem relogio** desde 25/09/2026 (o relogio foi o primeiro dos tres
    episodios). O aplicativo joga com a rede de seguranca de 10 s, e e por isso
    que o teste do lado de la olha o `motivoDaParada` quando os nos divergem.
    """
    p = parametros_do_nivel(nivel)
    return {
        "profundidade": p.profundidade,
        "ruido": p.ruido,
        "teto_de_nos": p.teto_de_nos,
        "extensao_de_captura": p.extensao_de_captura,
        "chance_de_errar": p.chance_de_errar,
        "margem_do_erro": p.margem_do_erro,
        "com_base_de_finais": nivel in NIVEIS_QUE_USAM_A_BASE,
    }


def _fen_inicial(co_modalidade: str) -> str:
    """A posicao de comeco daquela modalidade, em FEN.

    ⚠️ **Quem sabe quem abre e o REGULAMENTO**, e nao este arquivo:
    `quem_comeca` e brancas nas brasileiras e pretas nas anglo-americanas.
    Montar a FEN a mao aqui seria mais uma escrituracao de uma regra que o motor
    ja declara - e o `EstadoDamas` importa o mesmo motor, pelo espelho.
    """
    # ⚠️ O import e aqui dentro, e nao no topo: quem poe o espelho no
    # `sys.path` e `motores.damas.motor_damas`, ao ser importado. No topo deste
    # arquivo o pacote `jogos.` ainda nao existe para o Python.
    from jogos.jogo_damas.motor.regras_damas import REGULAMENTOS
    from jogos.jogo_damas.motor.tabuleiro_damas import Tabuleiro

    regulamento = REGULAMENTOS[co_modalidade]
    return Tabuleiro.inicial(vez=regulamento.quem_comeca).para_fen()


def jogar_uma_partida(
    *,
    co_modalidade: str,
    nivel: NivelDeMotor,
    nu_semente: int,
) -> dict[str, Any]:
    """Uma partida inteira de CPU contra CPU, no mesmo nivel dos dois lados.

    ⚠️ **Os dois lados no MESMO nivel, e nao e detalhe.** O que se quer comparar
    e o adversario que o aparelho enfrenta; pondo um nivel de cada lado, metade
    dos lances do arquivo mediria uma combinacao que o desafio nao produz.

    Returns:
        O dicionario da partida, na forma que vai ao arquivo.
    """
    motor = MotorDamas(co_modalidade=co_modalidade)
    estado = EstadoDamas(
        co_modalidade=co_modalidade,
        fen_inicial=_fen_inicial(co_modalidade),
    )

    lances: list[dict[str, Any]] = []
    co_desfecho = "teto_de_lances"
    vencedor: int | None = None

    teto = maximo_de_meios_lances(nivel)
    for n in range(1, teto + 1):
        veredito = motor.veredito(estado)
        if veredito.acabou:
            co_desfecho = veredito.co_motivo or "acabou"
            vencedor = veredito.vencedor
            break

        contador = _ContadorDeNos()
        # ⚠️ A semente do lance **pela conta do aplicativo** - a mesma funcao que
        # o gerador de desafios usa. Ver `job/semente.py`.
        semente = semente_mod.semente_do_lance(nu_semente, n)
        lance = motor.escolher_lance(
            estado, nivel, limite=contador, semente=semente
        )
        lances.append(
            {"n": n, "semente": semente, "lance": lance, "nos": contador.nos}
        )
        estado = motor.aplicar(estado, lance)

    return {
        "id": f"damas-{co_modalidade}-{nivel.value}-{nu_semente}",
        "co_jogo": "damas",
        "co_modalidade": co_modalidade,
        "co_nivel": nivel.value,
        "nu_semente": nu_semente,
        "fen_inicial": estado.fen_inicial,
        "argumentos": argumentos_do_nivel(nivel),
        "lances": lances,
        "fen_final": estado.fen,
        "co_desfecho": co_desfecho,
        "vencedor": vencedor,
        # ⚠️ O teto daquela partida, escrito nela: e o que separa "a partida
        # acabou" de "a bancada parou aqui", sem quem le precisar saber de cor
        # qual nivel tem qual teto.
        "maximo_de_meios_lances": teto,
    }


def montar(
    *,
    modalidades: tuple[str, ...],
    niveis: tuple[NivelDeMotor, ...],
    sementes: tuple[int, ...],
    falar: bool = True,
) -> dict[str, Any]:
    """O documento inteiro, com as partidas em ordem estavel.

    ⚠️ **Ordem estavel importa**: as duas copias sao comparadas byte a byte, e
    uma reordenacao inocente faria o cadeado acusar divergencia onde nao ha.
    """
    partidas: list[dict[str, Any]] = []
    comeco = time.monotonic()

    for co_modalidade in modalidades:
        for nivel in niveis:
            for nu_semente in sementes_do_nivel(nivel, sementes):
                t0 = time.monotonic()
                partida = jogar_uma_partida(
                    co_modalidade=co_modalidade,
                    nivel=nivel,
                    nu_semente=nu_semente,
                )
                partidas.append(partida)
                if falar:
                    print(
                        f"  {partida['id']}: "
                        f"{len(partida['lances'])} meios-lances, "
                        f"{partida['co_desfecho']}, "
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
        "de_documento": "Bancada de paridade dos motores (T094). GERADO por "
        "scripts/gerar_vetores_paridade_motores.py - nao edite a mao. O "
        "aplicativo reproduz estas partidas em "
        "test/modulos/jogos/damas/paridade_da_bancada_test.dart.",
        "versao": VERSAO,
        # De que motor sairam estes lances. ⚠️ E o SHA-256 dos fontes do espelho,
        # que e o mesmo resumo que o executavel carimba e que o aplicativo
        # confere contra os arquivos dele - um arquivo gerado por um motor
        # antigo se denuncia por aqui, e nao por uma divergencia misteriosa.
        "motor": {
            "damas": jogador_dart.jogador_compartilhado().resumo_do_motor,
        },
        "partidas": partidas,
    }


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Gera as partidas da bancada de paridade (T094).",
    )
    analisador.add_argument(
        "--modalidades",
        nargs="+",
        default=None,
        help="quais modalidades (padrao: todas as do contrato)",
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
        help="quantas sementes-mestras por combinacao (padrao: todas)",
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

    modalidades = tuple(args.modalidades or modalidades_declaradas())
    niveis = (
        tuple(NivelDeMotor(n) for n in args.niveis) if args.niveis else NIVEIS
    )
    sementes = SEMENTES_MESTRAS[: max(1, args.partidas)]

    # ⚠️ A conta nao e uma multiplicacao: o Sagaz joga uma partida por
    # modalidade, e nao tres (ver `SEMENTES_POR_NIVEL`).
    quantas = len(modalidades) * sum(
        len(sementes_do_nivel(nivel, sementes)) for nivel in niveis
    )
    print(
        f"{len(modalidades)} modalidades x {len(niveis)} niveis = "
        f"{quantas} partidas",
        flush=True,
    )

    documento = montar(modalidades=modalidades, niveis=niveis, sementes=sementes)

    # `ensure_ascii=False` mantem os acentos legiveis no diff; `indent=2` deixa o
    # arquivo revisavel. O `\n` final e explicito, e a escrita usa `newline=""`
    # porque este arquivo e comparado por SHA-256 entre repositorios - o
    # `write_text` do Windows converteria LF em CRLF e as duas copias deixariam
    # de bater por um motivo que nao tem nada a ver com o conteudo.
    texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"

    if args.amostra:
        # ⚠️ **Fora do repositorio, de proposito.** Uma amostra e um arquivo
        # parcial - falta nivel, falta modalidade -, e um arquivo parcial
        # largado em `contratos/` seria commitado por engano um dia.
        destinos: tuple[Path, ...] = (
            Path(tempfile.gettempdir()) / "amostra-paridade-motores.json",
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
