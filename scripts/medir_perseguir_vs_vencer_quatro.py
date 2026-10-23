"""O perseguidor do objetivo contra o personagem que so quer vencer (T124c, defeito 1).

═══════════════════════════════════════════════════════════════════════════
A PERGUNTA
═══════════════════════════════════════════════════════════════════════════

Nos seis tipos do Quatro que pedem um JEITO de vencer (ou de jogar), a regua
mediu o cumprimento por acaso: o personagem joga para vencer e nao le o
objetivo. `motores/quatro/perseguir_objetivo_quatro.py` e um jogador que
persegue o objetivo, com nivel. Antes de liga-lo em
`gerador.SOLUCIONADOR_POR_TIPO`, este script responde tres perguntas, na mesma
posicao, contra o mesmo adversario e com o mesmo orcamento (PAREADO):

  1. ⛔ **O CONTROLE** - o perseguidor, quando o objetivo e so vencer, vence
     tanto quanto o Magno? Se vencer bem menos, ele e incompetente, e o resto da
     tabela mede a incompetencia dele, e nao a dificuldade do tipo (a licao de
     18/09 nas damas, `medir_perseguir_vs_vencer.py`).
  2. **O GANHO** - o perseguidor no nivel do Magno cumpre o objetivo mais vezes
     que o Magno que so quer vencer?
  3. **A ESCADA** - do Cacau ao Magno, o perseguidor cumpre MAIS a cada degrau?
     E o que a regua precisa enxergar (Cacau 0-0,20 · Pita 0,05-0,45 · Tex
     0,45-0,85 · Magno 0,75-1, `job/regua.ESCADA_ALVO`).

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomavel, todos os nucleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\medir_perseguir_vs_vencer_quatro.py

Cada POSICAO concluida vira uma linha do diario
`medicoes/medir_perseguir_vs_vencer_quatro/diario.jsonl`; rodar de novo pula o
que ja esta la. O relatorio sai em `relatorio.txt`, na mesma pasta, e e
reescrito a cada execucao a partir do diario inteiro. `--processos N` muda o
numero de processos (padrao: todos os nucleos); `--posicoes N` quantas posicoes
por tipo (padrao 30); `--tipos a,b` so alguns tipos.

⚠️ **O "Forme a figura" (T148) e medido por VARIANTE**, e nao pelo tipo: cada
figura e um desafio diferente. O alvo se escreve `quatro_figura:<figura>:<folga>`
(`--tipos quatro_figura:quadrado:3,quatro_figura:l:3` sao os CONTROLES: figuras
faceis com folga larga, que o perseguidor no nivel do Magno tem de formar quase
sempre). Na figura nao ha o modo de controle "so vencer" (o controle sao essas
duas figuras), e o teto de cada partida e o prazo do candidato (`2M - 1`).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from job import editorial as editorial_mod  # noqa: E402
from job import figuras_quatro as figuras_mod  # noqa: E402
from job import posicao_inicial as posicao_inicial_mod  # noqa: E402
from job import posicoes_de_autoplay_quatro as acervo_mod  # noqa: E402
from job import provas_quatro as provas_mod  # noqa: E402
from job import semente as semente_mod  # noqa: E402
from job.gerador import JANELA_DO_PREPARO_QUATRO, vitoria_imediata_quatro  # noqa: E402
from job.regua import NOS_POR_LANCE_NA_MEDICAO, SEGUNDOS_POR_LANCE_NA_MEDICAO  # noqa: E402
from job.tipos_de_desafio import RECEITAS, RECEITAS_FORA_DO_AR  # noqa: E402
from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.orcamento import Orcamento  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.quatro import feitos_quatro  # noqa: E402
from motores.quatro import perseguir_objetivo_quatro as perseguir  # noqa: E402
from motores.quatro.jogador_dart_quatro import JogadorDartQuatro  # noqa: E402
from motores.quatro.jogador_quatro import JogadorQuatro  # noqa: E402
from motores.quatro.motor_quatro import EstadoQuatro, MotorQuatro  # noqa: E402

PASTA = RAIZ / "medicoes" / "medir_perseguir_vs_vencer_quatro"
DIARIO = PASTA / "diario.jsonl"
RELATORIO = PASTA / "relatorio.txt"

CO_MODALIDADE = "tradicional"

#: Os seis tipos que pedem um jeito de vencer (ou de jogar), e o "Encoste N em
#: ate M" (T143, 22/10/2026), que fecha no meio da partida.
TIPOS = (
    "quatro_vencer_diagonal",
    "quatro_golpe_duplo",
    "quatro_linha_de_cinco",
    "quatro_encostadas",
    "quatro_sem_o_meio",
    "quatro_bloquear",
    "quatro_encoste",
)

#: ⚠️ **Os tipos com CONTROLE PROPRIO**: o controle de "so vencer" nao serve a
#: um objetivo que nao e vencer. No "Encoste" o controle e o mesmo desafio com o
#: alvo de JOGAR COLADO (`E + M`, sem pecas soltas a juntar): ele cabe sempre
#: (cada lance encosta a peca nova), entao o perseguidor no nivel do Magno tem
#: de cumpri-lo quase sempre - senao ele mede a propria incompetencia (a
#: proposta, §1, passo 3). E o controle e julgado pela chegada DELE, e nao pela
#: do desafio.
CONTROLE_PROPRIO = frozenset({"quatro_encoste"})

#: O tipo do "Forme a figura", medido por variante (ver o cabecalho).
TIPO_DA_FIGURA = "quatro_figura"

#: Os CONTROLES da figura (a proposta §2, "Como medir", passo 5): o quadrado e o
#: L, com a maior folga. Se o perseguidor-Magno nao os formar quase sempre, ele
#: nao serve para medir as outras figuras.
CONTROLES_DA_FIGURA = ("quatro_figura:quadrado:3", "quatro_figura:l:3")

#: A semente da amostra: a mesma posicao a cada execucao (retomavel e pareado).
SEMENTE = 20261021

#: O adversario de todas as partidas: o Tex, o degrau do meio de cima. ⚠️ O
#: mesmo nos modos todos - o que muda e so a cabeca de quem resolve.
ADVERSARIO = NivelDeMotor.TEX

#: Quantos nos a prova do Magno pode gastar por lance candidato. ⚠️ Bem abaixo
#: do teto da geracao (2 milhoes): aqui e uma pergunta por coluna, a cada lance,
#: e "nao provado" so deixa o lance na lista.
TETO_DA_PROVA_DO_MAGNO = 200_000

#: Quantas posicoes do acervo se tentam ate uma passar na prova do tipo.
TENTATIVAS_POR_POSICAO = 60

#: Os modos de quem resolve, na ordem do relatorio.
MODOS = (
    "magno_so_vence",
    "persegue_cacau",
    "persegue_pita",
    "persegue_tex",
    "persegue_magno",
    "controle_persegue_vencer",
)

NIVEL_DO_MODO = {
    "persegue_cacau": NivelDeMotor.CACAU,
    "persegue_pita": NivelDeMotor.PITA,
    "persegue_tex": NivelDeMotor.TEX,
    "persegue_magno": NivelDeMotor.SAGAZ,
    "controle_persegue_vencer": NivelDeMotor.SAGAZ,
}

#: A chegada do controle: so vencer (a da virada, que a regua mede de verdade).
CHEGADA_DE_SO_VENCER = RECEITAS["quatro_virada"].montar({})


def _receita(co_tipo: str):
    """A receita do tipo, no ar ou fora dele."""
    return RECEITAS.get(co_tipo) or RECEITAS_FORA_DO_AR[co_tipo]


def _tipo_do_alvo(alvo: str) -> str:
    """`quatro_figura:quadrado:3` → `quatro_figura`; um tipo comum, ele mesmo."""
    return alvo.split(":")[0]


def _publicacao(alvo: str):
    """A variante medida: a primeira do tipo, ou a da figura e da folga do alvo.

    Raises:
        KeyError: a figura ou a folga do alvo nao tem variante no editorial.
    """
    co_tipo = _tipo_do_alvo(alvo)
    tabela = (
        editorial_mod.EDITORIAL
        if co_tipo in editorial_mod.EDITORIAL
        else editorial_mod.EDITORIAL_FORA_DO_AR
    )
    if co_tipo != TIPO_DA_FIGURA:
        return tabela[co_tipo][0]
    # `str.split(":")` com tres partes: o tipo, o nome da figura e a folga.
    _, nome, folga = alvo.split(":")
    for publicacao in tabela[co_tipo]:
        p = publicacao.parametros
        if (
            p[figuras_mod.CHAVE_FIGURA] == nome
            and p[figuras_mod.CHAVE_FOLGA_DA_FIGURA] == int(folga)
        ):
            return publicacao
    raise KeyError(f"nenhuma variante de {alvo!r} no editorial")


def _modos(alvo: str) -> tuple[str, ...]:
    """Os modos do alvo: na figura nao ha o controle de "so vencer"."""
    if _tipo_do_alvo(alvo) == TIPO_DA_FIGURA:
        return tuple(m for m in MODOS if not m.startswith("controle"))
    return MODOS


def _posicao(alvo: str, indice: int, provador) -> dict[str, Any] | None:
    """A [indice]-esima posicao do alvo: do acervo, na faixa do preparo, provada.

    ⚠️ Determinista pela semente: rodar de novo sorteia a MESMA posicao, e e isso
    que deixa o diario retomar sem mudar a amostra.
    """
    publicacao = _publicacao(alvo)
    co_tipo = _tipo_do_alvo(alvo)
    # ⚠️ A semente leva o ALVO inteiro: cada figura sorteia as suas posicoes, e
    # nos tipos comuns o alvo e o proprio tipo (as sementes de antes valem).
    sorteio = random.Random(f"{SEMENTE}:{alvo}:{indice}")
    motor = provador.arbitro
    for _ in range(TENTATIVAS_POR_POSICAO):
        sorteada = acervo_mod.sortear(
            sorteio,
            co_modalidade=CO_MODALIDADE,
            minimo=publicacao.nu_lances_de_preparo,
            maximo=publicacao.nu_lances_de_preparo + JANELA_DO_PREPARO_QUATRO - 1,
        )
        estado = EstadoQuatro(CO_MODALIDADE, tuple(sorteada.lances))
        if vitoria_imediata_quatro(motor, estado) is not None:
            continue
        tabuleiro = motor.tabuleiro(estado)
        encostadas = feitos_quatro.pecas_encostadas(
            motor.regras.dimensoes, tabuleiro, tabuleiro.vez
        )
        # No "Forme a figura" o prazo sai da distancia nesta posicao, como no
        # gerador; figura sem lugar livre de conflito: a posicao nao serve.
        distancia = None
        if editorial_mod.alvo_sai_da_figura(publicacao.parametros):
            distancia = figuras_mod.distancia(
                figuras_mod.FIGURAS_QUATRO[publicacao.parametros[figuras_mod.CHAVE_FIGURA]],
                tabuleiro,
                motor.regras.dimensoes,
            )
            if distancia is None:
                continue
        parametros = editorial_mod.parametros_efetivos(
            publicacao.parametros, encostadas=encostadas, distancia=distancia
        )
        prova = provas_mod.provar(
            co_tipo, provador, estado, parametros, continuacao=sorteada.continuacao
        )
        if not prova.passou:
            continue
        posicao = {
            "lances": list(sorteada.lances),
            "chegada": _receita(co_tipo).montar(parametros),
            "teto": publicacao.nu_maximo_de_meios_lances,
        }
        if distancia is not None:
            # O teto apertado ao prazo deste candidato, como no gerador: depois
            # do M-esimo lance da pessoa a janela fechou.
            posicao["teto"] = min(posicao["teto"], 2 * parametros["lances"] - 1)
            posicao["distancia"] = distancia
        if co_tipo in CONTROLE_PROPRIO:
            # O alvo de jogar colado: o que ja esta encostado mais um por lance.
            facil = {**parametros, "pecas": encostadas + parametros["lances"]}
            posicao["controle"] = _receita(co_tipo).montar(facil)
        return posicao
    return None


def _jogar(
    jogador: JogadorQuatro,
    provador,
    co_tipo: str,
    iniciais: list[str],
    chegada: dict[str, Any],
    teto: int,
    modo: str,
    nu_semente: int,
    adversario: NivelDeMotor = ADVERSARIO,
    controle: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """Uma partida de [modo] a partir da posicao; devolve cumpriu e venceu.

    [adversario] e o nivel de quem joga contra quem resolve. O padrao e o Tex,
    o desta medicao; `scripts/medir_objetivo_forcavel_quatro.py` passa os
    quatro, para medir a hipotese do dono de que o Tex e o Magno bloqueiam
    demais o golpe duplo e a linha de cinco (T124c, 21/10/2026).

    [controle]: a chegada do controle PROPRIO do tipo ([CONTROLE_PROPRIO]).
    Com ela, o modo de controle persegue e e julgado por ela.
    """
    motor: MotorQuatro = jogador.arbitro
    # O controle persegue "so vencer" (ou o controle proprio do tipo); os
    # outros, o objetivo do tipo.
    if modo.startswith("controle") and controle is not None:
        chegada = controle
    chegada_do_modo = (
        CHEGADA_DE_SO_VENCER
        if modo.startswith("controle") and controle is None
        else chegada
    )
    desafio = perseguir.desafio_de(motor, co_tipo, iniciais, chegada_do_modo)
    # ⚠️ O sorteio da mistura do nivel: a semente e a da partida, e entao os
    # modos ficam pareados no adversario (as sementes dos lances sao as mesmas).
    sorteio = random.Random(nu_semente)
    fita: list[str] = []

    def prova(estado: EstadoQuatro) -> int | None:
        return provador.resultado(estado).vencedor

    for numero in range(1, teto + 1):
        estado = EstadoQuatro(CO_MODALIDADE, tuple(iniciais) + tuple(fita))
        if not motor.lances_legais(estado):
            break
        semente = semente_mod.semente_do_lance(nu_semente, numero)

        def do_nivel(nivel: NivelDeMotor) -> str:
            orcamento = Orcamento(
                nos_maximos=NOS_POR_LANCE_NA_MEDICAO,
                segundos_maximos=SEGUNDOS_POR_LANCE_NA_MEDICAO,
            ).iniciar()
            return jogador.escolher_lance(
                estado, nivel, limite=orcamento, semente=semente
            )

        if motor.vez_de(estado) != desafio.pessoa:
            lance = do_nivel(adversario)
        elif modo == "magno_so_vence":
            lance = do_nivel(NivelDeMotor.SAGAZ)
        else:
            nivel = NIVEL_DO_MODO[modo]
            lance = perseguir.lance_de_quem_persegue(
                motor,
                desafio,
                fita,
                nivel=nivel,
                sorteio=sorteio,
                lance_do_nivel=lambda: do_nivel(nivel),
                prova=prova,
            )
        fita.append(lance)

    final = EstadoQuatro(CO_MODALIDADE, tuple(iniciais) + tuple(fita))
    desfecho = motor.desfecho(final)
    julgamento = julgar_desafio(
        co_jogo="quatro",
        js_posicao_inicial=posicao_inicial_mod.do_quatro(
            iniciais, co_modalidade=CO_MODALIDADE
        ),
        js_chegada=chegada,
        fita=[
            {"n": n, "jogador": desafio.pessoa if n % 2 else -desafio.pessoa, "lance": l}
            for n, l in enumerate(fita, start=1)
        ],
        jogador=desafio.pessoa,
        co_modalidade=CO_MODALIDADE,
    )
    return {
        "cumpriu": julgamento.veredito == "cumpriu",
        "venceu": desfecho is not None and desfecho.vencedor == desafio.pessoa,
    }


def medir_unidade(unidade: tuple[str, int]) -> dict[str, Any]:
    """Uma posicao de um tipo, nos seis modos. Um executavel SO desta unidade.

    ⚠️ Aberto e fechado pelo `with` (memoria "pool-fechado-deixa-os-processos"):
    o processo do motor nao sobrevive a unidade.
    """
    alvo, indice = unidade
    co_tipo = _tipo_do_alvo(alvo)
    inicio = time.time()
    with JogadorDartQuatro() as motor_dart:
        jogador = JogadorQuatro(CO_MODALIDADE, motor_dart)
        provador = provas_mod.ProvadorQuatro(
            CO_MODALIDADE, motor_dart, teto_de_nos=TETO_DA_PROVA_DO_MAGNO
        )
        provador_da_amostra = provas_mod.ProvadorQuatro(CO_MODALIDADE, motor_dart)
        posicao = _posicao(alvo, indice, provador_da_amostra)
        # ⚠️ A chave do diario e o ALVO (no campo `co_tipo`, o nome de sempre):
        # nos tipos comuns e o proprio tipo, e as linhas antigas continuam valendo.
        linha: dict[str, Any] = {"co_tipo": alvo, "indice": indice}
        if posicao is None:
            linha["sem_posicao"] = True
        else:
            linha["lances"] = "".join(posicao["lances"])
            if "distancia" in posicao:
                linha["distancia"] = posicao["distancia"]
            nu_semente = int(
                random.Random(f"{SEMENTE}:jogo:{alvo}:{indice}").getrandbits(31)
            )
            for modo in _modos(alvo):
                linha[modo] = _jogar(
                    jogador,
                    provador,
                    co_tipo,
                    posicao["lances"],
                    posicao["chegada"],
                    posicao["teto"],
                    modo,
                    nu_semente,
                    controle=posicao.get("controle"),
                )
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


def _ler_diario() -> list[dict[str, Any]]:
    """As linhas ja medidas (vazio na 1a execucao)."""
    if not DIARIO.is_file():
        return []
    return [json.loads(l) for l in DIARIO.read_text(encoding="utf-8").splitlines() if l]


def relatorio(linhas: list[dict[str, Any]]) -> str:
    """A tabela por tipo: cumpriu (e venceu) por modo, sobre as posicoes medidas."""
    saida = [
        "Perseguidor do objetivo x Magno que so vence (Quatro, T124c defeito 1)",
        f"adversario: {ADVERSARIO.value} · posicoes por tipo: as do diario",
        "",
        "⛔ CONTROLE: o perseguidor-Magno vencendo quando o objetivo e SO vencer,",
        "contra o Magno que so vence (coluna 'venceu'). Perto = competente.",
        "⛔ No quatro_encoste o controle e o alvo de JOGAR COLADO (coluna",
        "'cumpriu' da linha de controle): perto de 1,00 = competente.",
        "⛔ Na figura o controle sao o quadrado e o L com folga 3 (persegue_magno",
        "perto de 1,00 = competente). `distancia`: a media nas posicoes medidas.",
        "",
    ]
    # Os tipos de sempre, e depois os alvos de figura que estiverem no diario.
    alvos = list(TIPOS) + sorted(
        {l["co_tipo"] for l in linhas if l["co_tipo"].startswith(TIPO_DA_FIGURA + ":")}
    )
    for co_tipo in alvos:
        medidas = [l for l in linhas if l["co_tipo"] == co_tipo and not l.get("sem_posicao")]
        sem = sum(1 for l in linhas if l["co_tipo"] == co_tipo and l.get("sem_posicao"))
        if not medidas and not sem:
            continue
        n = len(medidas)
        cabeca = f"{co_tipo}: {n} posicoes ({sem} sem posicao provada)"
        distancias = [l["distancia"] for l in medidas if "distancia" in l]
        if distancias:
            cabeca += f" · distancia media {sum(distancias) / len(distancias):.1f}"
        saida.append(cabeca)
        for modo in _modos(co_tipo):
            cumpriu = sum(l[modo]["cumpriu"] for l in medidas)
            venceu = sum(l[modo]["venceu"] for l in medidas)
            taxa = cumpriu / n if n else 0.0
            saida.append(
                f"   {modo:<26} cumpriu {cumpriu:>3} de {n} ({taxa:4.2f})"
                f"   venceu {venceu:>3}"
            )
        saida.append("")
    return "\n".join(saida)


def principal(argumentos: list[str]) -> int:
    """Le os argumentos, mede o que falta, e escreve o relatorio."""
    leitor = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    leitor.add_argument("--posicoes", type=int, default=30)
    leitor.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    leitor.add_argument("--tipos", default=",".join(TIPOS))
    args = leitor.parse_args(argumentos)

    PASTA.mkdir(parents=True, exist_ok=True)
    feitas = {(l["co_tipo"], l["indice"]) for l in _ler_diario()}
    pendentes = [
        (co_tipo, indice)
        for indice in range(args.posicoes)
        for co_tipo in args.tipos.split(",")
        if (co_tipo, indice) not in feitas
    ]
    print(
        f"{len(feitas)} unidades ja no diario; {len(pendentes)} a medir, "
        f"em {args.processos} processos."
    )
    inicio = time.time()
    with multiprocessing.Pool(args.processos) as pool, DIARIO.open(
        "a", encoding="utf-8"
    ) as diario:
        for i, linha in enumerate(pool.imap_unordered(medir_unidade, pendentes), 1):
            # Uma linha por unidade, gravada na hora: e o que torna a medicao
            # retomavel se a janela fechar no meio.
            diario.write(json.dumps(linha, ensure_ascii=False) + "\n")
            diario.flush()
            print(
                f"[{i}/{len(pendentes)}] {linha['co_tipo']} #{linha['indice']} "
                f"{linha['segundos']} s · {time.time() - inicio:.0f} s no total"
            )
    texto = relatorio(_ler_diario())
    RELATORIO.write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
