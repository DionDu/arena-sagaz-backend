"""O Sagaz joga a PARTIDA; um humano com o objetivo na tela joga o DESAFIO.

Hipotese do dono (18/09/2026): depois de coroar a primeira dama, o motor prefere
usa-la para ganhar a partida em vez de conduzir a segunda pedra a coroacao -
entao os moldes de "coroar 2 damas" nao seriam raros, seriam INVISIVEIS a busca
que os procurou. ⚠️ Ela nasce de uma leitura do codigo que e fato, e nao
hipotese: `job/gerador.py` so tem solucionador proprio para um tipo do
Pontinhos, entao a pescaria e a regua das damas escolhem o lance com
`motor.escolher_lance(..., SAGAZ, ...)`, onde o objetivo do desafio **nao entra**.

⛔ **TODO SOLUCIONADOR AQUI PASSA POR UM CONTROLE, E ELE NAO E DECORACAO.**
A primeira versao deste script (18/09/2026) mediu 5 de 163 e parecia refutar a
hipotese - ate o controle mostrar que o mesmo solucionador coroava UMA dama em
apenas 51 das 163 posicoes em que o Sagaz coroava nas 163. ⚠️ Um solucionador
que perde para o Sagaz no objetivo FACIL nao esta medindo o dificil: esta
medindo a propria incompetencia. A coluna `X=1` de cada linha existe para essa
pergunta, e uma linha que afunda nela nao responde nada sobre `X=2`.

⚠️ **A comparacao e PAREADA:** mesma posicao, mesma modalidade, mesmo
adversario, mesmo orcamento - muda so a cabeca de quem resolve.
"""

from __future__ import annotations

import json
import multiprocessing
import sys
import time
from pathlib import Path

RAIZ = Path(r"D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend")
sys.path.insert(0, str(RAIZ))

from job import posicao_inicial as pos  # noqa: E402
from job import semente as sem  # noqa: E402
from job.moldes_de_damas import _campos, _lado_e_adversario, MODALIDADES  # noqa: E402
from motores.damas.motor_damas import EstadoDamas, MotorDamas, NivelDeMotor  # noqa: E402
from motores.damas.perseguir_coroacao import (  # noqa: E402
    lance_de_quem_persegue_a_coroacao,
    nota_da_posicao,
    PESO_DA_PECA,
)
from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.orcamento import Orcamento  # noqa: E402
from scripts.cacar_moldes_damas import (  # noqa: E402
    chegada_da_posicao,
    MINIMO_DE_MODALIDADES,
    parametros_do_tipo,
    SEMENTE_DA_BUSCA,
)
from scripts.pescar_moldes_de_partidas import _por_alvo  # noqa: E402

DIARIO = RAIZ / "pescaria_coroar_123_teto26_novo.jsonl"

#: ⚠️ 19 meios-lances = p 10, que e o teto de 20 da publicacao. Medir alem disso
#: acharia solucoes que nenhuma variante publicada poderia usar.
TETO = 19

#: ⛔ Orcamento IGUAL em todos os modos e nos dois lados. E menor que o da
#: pescaria (60k/60s) de proposito: o que se mede e a diferenca ENTRE os modos, e
#: um orcamento alto so faria cada posicao custar minutos sem mudar a comparacao.
#: ⚠️ Por isso os numeros absolutos daqui nao se comparam com os da pescaria.
NOS = 3_000
SEGUNDOS = 0.30


# ─────────────────────────────────────────────────────────────────────────────
# As pecas da conta
# ─────────────────────────────────────────────────────────────────────────────


def _fileira_ate_coroar(casa: str, sou_branco: bool) -> int:
    """Quantas fileiras faltam para esta pedra coroar. Dama devolve 0.

    ⚠️ As casas vao de 1 a 32, quatro por fileira. As brancas coroam em 1..4 (a
    fileira 0) e as pretas em 29..32 (a fileira 7) - a conta das pretas e o
    espelho da das brancas.
    """
    if casa.upper().startswith("K"):
        return 0
    n = int(casa.upper().lstrip("K"))
    fileira = (n - 1) // 4
    return fileira if sou_branco else 7 - fileira


def _retrato(fen: str, indice_meu: int) -> tuple[int, int, int]:
    """`(damas, pecas, distancia_das_duas_pedras_mais_adiantadas)` do meu lado.

    ⚠️ Olham-se as **duas** pedras mais adiantadas porque o alvo pode ser duas
    coroacoes: premiar so a melhor faria o solucionador empurrar a mesma pedra e
    abandonar a segunda - que e exatamente o defeito que se esta medindo no motor.
    """
    minhas = _campos(fen)[indice_meu]
    sou_branco = indice_meu == 1
    damas = sum(1 for c in minhas if c.upper().startswith("K"))
    pedras = sorted(
        _fileira_ate_coroar(c, sou_branco)
        for c in minhas
        if not c.upper().startswith("K")
    )
    return damas, len(minhas), sum(pedras[:2]) if pedras else 0


def _pior_perda(motor, estado_depois, indice_meu: int) -> int:
    """Quantas pecas minhas o adversario leva na melhor captura dele?

    ⚠️ E um unico meio-lance de antecipacao, e nao uma busca: o que se quer e so
    impedir que o solucionador entregue material de graca para avancar uma casa.
    ⛔ Nas damas a captura e **obrigatoria**, entao entregar peca nao e um risco
    que o adversario talvez aceite - e um lance que ele sera forcado a fazer.
    """
    try:
        legais = motor.lances_legais(estado_depois)
    except Exception:  # noqa: BLE001 — posicao terminal nao tem lance
        return 0
    antes = _retrato(estado_depois.fen, indice_meu)[1]
    pior = 0
    for lance in legais:
        try:
            depois = motor.aplicar(estado_depois, lance)
        except Exception:  # noqa: BLE001
            continue
        pior = max(pior, antes - _retrato(depois.fen, indice_meu)[1])
    return pior


# ─────────────────────────────────────────────────────────────────────────────
# Os quatro modos que se comparam
# ─────────────────────────────────────────────────────────────────────────────
#
# ⚠️ Os tres solucionadores proprios usam a MESMA leitura da posicao; o que muda
# e o peso que cada um da a nao perder peca. E de proposito: assim a diferenca
# entre eles isola exatamente a variavel que derrubou a primeira medicao.

MODOS = ("sagaz", "guloso", "ponderado", "defensivo")


def _nota(modo: str, motor, estado_depois, indice_meu: int) -> tuple:
    """A nota de um lance ja aplicado, do ponto de vista do OBJETIVO."""
    damas, pecas, distancia = _retrato(estado_depois.fen, indice_meu)
    if modo == "guloso":
        # ⛔ A versao de 18/09 que reprovou no controle, mantida para comparar:
        # lexicografica, com material em ULTIMO - entao qualquer avanco vale mais
        # que a peca que ele custa.
        return (damas, -distancia, pecas)
    if modo == "ponderado":
        # Material e progresso na mesma conta, e o material pesa dez vezes mais
        # que uma fileira.
        return (100 * damas + 10 * pecas - distancia,)
    # ⛔ "defensivo" NAO tem conta propria: e o solucionador de producao
    # (`motores/damas/perseguir_coroacao.py`). Duas copias da mesma heuristica
    # divergiriam no dia em que uma fosse ajustada, e o numero medido aqui
    # deixaria de descrever o que a pescaria faz.
    return (
        nota_da_posicao(estado_depois.fen, indice_meu)
        - PESO_DA_PECA * _pior_perda(motor, estado_depois, indice_meu),
    )


def resolve(fen: str, modalidade: str, modo: str) -> dict[str, int | None]:
    """Em que meio-lance cada alvo cai, com este modo? `None` se nao cai no teto.

    ⚠️ **Uma fita responde pelos dois alvos.** O solucionador persegue "coroar o
    maximo", e nao um numero especifico, entao a mesma partida serve para julgar
    `damas=1` e `damas=2` - o que corta o custo pela metade sem trocar a pergunta.

    Returns:
        `{"damas=1": n | None, "damas=2": n | None}`.
    """
    motor = MotorDamas(modalidade)
    achados: dict[str, int | None] = {"damas=1": None, "damas=2": None}
    try:
        estado = EstadoDamas(co_modalidade=modalidade, fen_inicial=fen)
        js_posicao = pos.das_damas(estado.fen, co_modalidade=modalidade)
        chegadas = {
            f"damas={x}": chegada_da_posicao(
                "damas_coroar",
                {**parametros_do_tipo("damas_coroar"), "damas": x},
                fen,
            )
            for x in (1, 2)
        }
    except Exception:  # noqa: BLE001
        return achados

    vez_de_quem_resolve = estado.vez_de
    indice_meu, _ = _lado_e_adversario(fen)
    fita: list[dict] = []
    atual = estado

    for numero in range(1, TETO + 1):
        minha_vez = atual.vez_de == vez_de_quem_resolve
        try:
            if modo != "sagaz" and minha_vez:
                # ⛔ Aqui esta a troca inteira: em vez de perguntar ao motor qual
                # lance ganha a partida, prova-se cada lance legal e fica-se com
                # o que melhor serve ao objetivo.
                legais = motor.lances_legais(atual)
                if not legais:
                    break
                lance = max(
                    legais,
                    key=lambda l: _nota(modo, motor, motor.aplicar(atual, l), indice_meu),
                )
            else:
                lance = motor.escolher_lance(
                    atual,
                    NivelDeMotor.SAGAZ,
                    limite=Orcamento(nos_maximos=NOS, segundos_maximos=SEGUNDOS).iniciar(),
                    semente=sem.semente_do_lance(SEMENTE_DA_BUSCA, numero),
                )
        except ValueError:
            break

        fita.append({"n": numero, "jogador": atual.vez_de, "lance": lance})
        atual = motor.aplicar(atual, lance)

        for alvo, js_chegada in chegadas.items():
            if achados[alvo] is not None:
                continue
            if julgar_desafio(
                co_jogo="damas",
                js_posicao_inicial=js_posicao,
                js_chegada=js_chegada,
                fita=fita,
                jogador=js_posicao["vez_de"],
                co_modalidade=modalidade,
            ).cumpriu:
                achados[alvo] = numero

        if all(v is not None for v in achados.values()):
            break

    return achados


def _uma_posicao(fen: str) -> tuple[str, dict[str, dict[str, int]]]:
    """Quantas modalidades servem a cada alvo, em cada modo.

    ⚠️ Devolve a FEN junto porque o resultado vai para o **diario**, e com
    `imap_unordered` a ordem de chegada nao e a da lista: sem a FEN na linha, a
    retomada nao saberia o que ja foi medido.
    """
    contagem = {modo: {"damas=1": 0, "damas=2": 0} for modo in MODOS}
    for modo in MODOS:
        for modalidade in MODALIDADES:
            achados = resolve(fen, modalidade, modo)
            for alvo, n in achados.items():
                if n is not None:
                    contagem[modo][alvo] += 1
    return fen, contagem


def tabela(resultados: list[dict[str, dict[str, int]]]) -> None:
    """Imprime o quadro que decide, a partir de quantas posicoes houver.

    ⚠️ Serve tanto ao fim da medicao quanto a leitura de um diario interrompido:
    e a mesma conta, e duas copias dela divergiriam.
    """
    total = len(resultados)
    if not total:
        print("diario vazio - nada a resumir")
        return

    print(f"\n== QUANTAS POSICOES SERVIRIAM DE MOLDE ==")
    print(f"   (de {total}; 'serve' = objetivo cai em {MINIMO_DE_MODALIDADES}+ modalidades)\n")
    print(f"   {'modo':<12} {'X=1 (CONTROLE)':>16} {'X=2':>10}")
    print("   " + "-" * 44)
    base_x1 = sum(
        1 for r in resultados if r["sagaz"]["damas=1"] >= MINIMO_DE_MODALIDADES
    )
    for modo in MODOS:
        x1 = sum(1 for r in resultados if r[modo]["damas=1"] >= MINIMO_DE_MODALIDADES)
        x2 = sum(1 for r in resultados if r[modo]["damas=2"] >= MINIMO_DE_MODALIDADES)
        # ⛔ A marca do controle: um solucionador que coroa UMA dama menos vezes
        # que o Sagaz nao esta apto a responder sobre DUAS.
        marca = (
            ""
            if modo == "sagaz"
            else ("  OK" if x1 >= base_x1 * 0.9 else "  <-- REPROVA")
        )
        print(f"   {modo:<12} {x1:>16} {x2:>10}{marca}")

    print(
        "\nCOMO LER\n"
        "  A coluna X=1 e o CONTROLE: o solucionador tem de coroar uma dama pelo\n"
        "  menos tao bem quanto o Sagaz. Linha que afunda ali nao responde nada\n"
        "  sobre a coluna X=2, por maior que o numero dela pareca.\n"
        "  Entre as linhas APROVADAS, a coluna X=2 e a resposta: se ela for muito\n"
        "  maior que a do sagaz, o acervo de duas damas estava subestimado."
    )


#: ⛔ Onde cada posicao medida e gravada, UMA POR LINHA e na hora.
#:
#: ⚠️ A primeira versao deste script (18/09/2026) nao tinha diario: as ~2h de
#: medicao existiam so na tela, e fechar a janela as perdia inteiras. O pescador
#: de moldes ja fazia isso certo (`--diario`), e a diferenca nao e de tamanho do
#: trabalho - e de o trabalho sobreviver a maquina.
DIARIO_PADRAO = RAIZ / "perseguir_vs_vencer.jsonl"


def _ja_medidas(diario: Path) -> dict[str, dict[str, dict[str, int]]]:
    """O que o diario ja tem, por FEN. Linha corrompida e ignorada, nao fatal.

    ⚠️ Um diario truncado no meio de uma escrita e o caso NORMAL de quem matou o
    processo - e exatamente quem mais precisa da retomada.
    """
    if not diario.exists():
        return {}
    feitas: dict[str, dict[str, dict[str, int]]] = {}
    for linha in diario.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            r = json.loads(linha)
            feitas[r["fen"]] = r["contagem"]
        except (json.JSONDecodeError, KeyError):
            continue
    return feitas


def main() -> None:
    # ⚠️ `--tabela` nao mede nada: le o diario e imprime o quadro. E o que se roda
    # depois de interromper, ou para olhar o parcial sem parar a medicao.
    if "--tabela" in sys.argv:
        tabela(list(_ja_medidas(DIARIO_PADRAO).values()))
        return

    quantas = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    processos = int(sys.argv[2]) if len(sys.argv) > 2 else 14

    # ⚠️ A amostra sao as posicoes que ja servem a `damas=1` com o Sagaz: e sobre
    # elas que o acervo e construido, entao e nelas que a pergunta "quantos
    # moldes de X=2 existem?" tem sentido.
    candidatas: list[str] = []
    for linha in DIARIO.read_text(encoding="utf-8").splitlines():
        if not linha.strip():
            continue
        try:
            r = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if r.get("tipo_de_linha") != "medicao":
            continue
        uma = [n for n in (_por_alvo(r["lances"], "damas=1") or []) if n is not None]
        if len(uma) >= MINIMO_DE_MODALIDADES:
            candidatas.append(r["fen"])
        if len(candidatas) >= quantas:
            break

    # ⚠️ A retomada e por FEN, e nao por contagem: com `imap_unordered` a ordem
    # de chegada nao e a da lista, entao "pular as N primeiras" pularia as erradas.
    feitas = _ja_medidas(DIARIO_PADRAO)
    restantes = [fen for fen in candidatas if fen not in feitas]

    print(f"{len(candidatas)} posicoes que ja servem a 'coroar 1 dama' com o Sagaz")
    print(f"teto {TETO} meios-lances (= p 10) - {processos} processos")
    print(f"diario: {DIARIO_PADRAO.name}")
    if feitas:
        print(f"   ja medidas antes: {len(feitas)} - faltam {len(restantes)}")
    print("medindo 4 modos na mesma posicao...\n", flush=True)

    comeco = time.monotonic()
    resultados = [feitas[fen] for fen in candidatas if fen in feitas]

    # ⛔ Aberto em modo APPEND e com `flush` a cada linha: o objetivo inteiro do
    # diario e sobreviver a um processo morto no meio.
    with DIARIO_PADRAO.open("a", encoding="utf-8") as diario:
        with multiprocessing.Pool(processes=processos) as piscina:
            # ⚠️ `imap_unordered` e nao `map`: o `map` so devolve quando a ultima
            # posicao termina, e uma medicao longa sem sinal na tela e
            # indistinguivel de uma travada.
            for n, (fen, contagem) in enumerate(
                piscina.imap_unordered(_uma_posicao, restantes), start=1
            ):
                resultados.append(contagem)
                diario.write(
                    json.dumps({"fen": fen, "contagem": contagem}, ensure_ascii=False)
                    + "\n"
                )
                diario.flush()

                gasto = time.monotonic() - comeco
                # ⚠️ O que cada posicao rendeu, e nao so que ela terminou: sem
                # isso a unica noticia em duas horas e a tabela final.
                placar = " · ".join(
                    f"{modo[:3]} {contagem[modo]['damas=1']}/{contagem[modo]['damas=2']}"
                    for modo in MODOS
                )
                achou_duas = any(
                    contagem[modo]["damas=2"] >= MINIMO_DE_MODALIDADES for modo in MODOS
                )
                print(
                    f"   {n:>4}/{len(restantes)} · {gasto/60:.1f}m "
                    f"· faltam ~{gasto/n*(len(restantes)-n)/60:.0f}m "
                    f"· {placar}" + ("   <<< X=2" if achou_duas else ""),
                    flush=True,
                )

    tabela(resultados)
    print(f"\n   {(time.monotonic()-comeco):.0f}s")


if __name__ == "__main__":
    main()
