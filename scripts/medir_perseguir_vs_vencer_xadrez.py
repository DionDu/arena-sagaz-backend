"""O perseguidor do objetivo do xadrez contra o Magno que so quer vencer (T076a da spec 012).

═══════════════════════════════════════════════════════════════════════════
AS PERGUNTAS (`DECISOES-do-dono.md` §8zzzz57)
═══════════════════════════════════════════════════════════════════════════

Antes de ligar o perseguidor (`motores/xadrez/perseguir_objetivo_xadrez.py`) em
`gerador.SOLUCIONADOR_POR_TIPO`, este script responde, nas MESMAS posicoes,
contra o MESMO adversario e com as MESMAS sementes (PAREADO):

  1. ⛔ **O CONTROLE** - o perseguidor no nivel do Magno, perseguindo SO
     vencer (o pseudo-tipo `xadrez_vencer`), joga uma partida inteira contra o
     Tex tao bem quanto o Magno cru? Se vencer bem menos (ou perder mais), ele
     e incompetente, e o resto da tabela mede a incompetencia dele (a licao do
     Quatro, a v1 de 21/10/2026). Nada se liga se o controle reprovar.
  2. **O GANHO, por tipo** - o perseguidor no nivel do Magno cumpre o
     objetivo mais vezes que o Magno que so quer vencer?
  3. **A ESCADA, por tipo** - do Cacau ao Magno, o perseguidor cumpre MAIS a
     cada degrau? E o que a regua precisa enxergar (`job/regua.ESCADA_ALVO`:
     Cacau 0-0,20 · Pita 0,05-0,45 · Tex 0,45-0,85 · Magno 0,75-1).
  4. **A FOLGA DO PRAZO** (pedido do dono, 21/11/2026) - em que lance da
     pessoa o objetivo caiu, e quantos ERROS SORTEADOS do adversario
     (`erro_sorteado`/`cegueira`) houve antes dele. E com isso que se decide se
     o N publicado ("em ate N lances") deve sair do gabarito com uma folga.

Tipo com ganho e escada crescente entra em `SOLUCIONADOR_POR_TIPO`; tipo em que
nem o Magno perseguindo chega volta a T073 (o defeito e da posicao).

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomavel, todos os nucleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\medir_perseguir_vs_vencer_xadrez.py

Cada unidade concluida (uma posicao de um tipo, nos cinco modos; ou uma posicao
do controle) vira uma linha do diario
`medicoes/medir_perseguir_vs_vencer_xadrez/diario.jsonl`; rodar de novo pula o
que ja esta la. O relatorio sai em `relatorio.txt`, na mesma pasta, reescrito a
cada execucao a partir do diario inteiro. Opcoes: `--processos N` (padrao:
todos os nucleos), `--posicoes N` (por tipo, padrao 30), `--controle N`
(posicoes do controle, padrao 30), `--tipos a,b` (so alguns tipos; `controle`
e um deles).

⚠️ **Quem resolve e o MESMO perseguidor da producao**: a partida chama
`solucionadores.perseguidor_do_xadrez`, com o `ContextoDoSolucionador` que o
gerador e a regua montam. Medir uma copia dele seria medir outro jogador.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from job import posicoes_xadrez as posicoes_mod  # noqa: E402
from job import provas_xadrez as provas_mod  # noqa: E402
from job import semente as semente_mod  # noqa: E402
from job import solucionadores as solucionadores_mod  # noqa: E402
from job.editorial import EDITORIAL_FORA_DO_AR  # noqa: E402
from job.tipos_de_desafio import RECEITAS_FORA_DO_AR  # noqa: E402
from motores.juiz import julgar_desafio  # noqa: E402
from motores.nucleo.papeis import NivelDeMotor  # noqa: E402
from motores.xadrez import perseguir_objetivo_xadrez as perseguir  # noqa: E402
from motores.xadrez.jogador_xadrez import JogadorXadrez  # noqa: E402

PASTA = RAIZ / "medicoes" / "medir_perseguir_vs_vencer_xadrez"
DIARIO = PASTA / "diario.jsonl"
RELATORIO = PASTA / "relatorio.txt"

#: Os dez tipos em que vencer nao e o objetivo (o mate fica com o Magno cru).
TIPOS = tuple(
    sorted(perseguir.TIPOS_DO_PERSEGUIDOR - {perseguir.TIPO_DE_CONTROLE})
)

#: O nome do "tipo" do controle no diario e em `--tipos`.
CONTROLE = "controle"

#: A semente da amostra: as mesmas posicoes a cada execucao (retomavel e pareado).
SEMENTE = 20261121

#: O adversario de todas as partidas: o Tex, como no Quatro. ⚠️ O mesmo em
#: todos os modos: o que muda e so a cabeca de quem resolve.
ADVERSARIO = NivelDeMotor.TEX

#: Quantas posicoes da base se tentam ate uma passar na prova do tipo.
TENTATIVAS_POR_POSICAO = 60

#: O tamanho da partida do controle, em lances da pessoa. ⚠️ Uma partida
#: inteira, e nao a janela de um tipo: em oito lances, a partir de uma posicao
#: equilibrada, quase ninguem vence, e o controle nao separaria nada. Partida
#: que passa disso sem fim conta como "sem fim".
LANCES_DO_CONTROLE = 80

#: Os modos de quem resolve, na ordem do relatorio.
MODOS = (
    "magno_so_vence",
    "persegue_cacau",
    "persegue_pita",
    "persegue_tex",
    "persegue_magno",
)

NIVEL_DO_MODO = {
    "magno_so_vence": NivelDeMotor.SAGAZ,
    "persegue_cacau": NivelDeMotor.CACAU,
    "persegue_pita": NivelDeMotor.PITA,
    "persegue_tex": NivelDeMotor.TEX,
    "persegue_magno": NivelDeMotor.SAGAZ,
}

#: Os dois modos do controle: o Magno cru e o perseguidor-Magno de "so vencer".
MODOS_DO_CONTROLE = ("magno_cru", "persegue_vencer")

#: Os motivos do motor que sao ERRO DE PROPOSITO do personagem.
ACOES_DE_ERRO = frozenset({"erro_sorteado", "cegueira"})

#: Os "Passe N lances": neles o objetivo so cai no N-esimo lance, e a folga nao
#: tem sentido (mais lances deixariam o desafio mais dificil).
TIPOS_PASSE_N = frozenset(
    {"xadrez_espia_proteger", "xadrez_nao_perder", "xadrez_sem_levar_xeque"}
)


# ═══════════════════════════════════════════════════════════════════════════
# A amostra
# ═══════════════════════════════════════════════════════════════════════════


def _posicao_do_tipo(
    motor: JogadorXadrez, co_tipo: str, indice: int
) -> dict[str, Any] | None:
    """A [indice]-esima posicao do tipo: da base, com as pecas, e provada.

    ⚠️ Determinista pela semente: rodar de novo sorteia a MESMA posicao, e e isso
    que deixa o diario retomar sem mudar a amostra.
    """
    publicacao = EDITORIAL_FORA_DO_AR[co_tipo][0]
    sorteio = random.Random(f"{SEMENTE}:{co_tipo}:{indice}")
    for _ in range(TENTATIVAS_POR_POSICAO):
        escolhida = provas_mod.sortear_posicao(
            sorteio, co_tipo=co_tipo, parametros=publicacao.parametros
        )
        parametros = {**publicacao.parametros, **escolhida.pecas}
        chegada = RECEITAS_FORA_DO_AR[co_tipo].montar(parametros)
        prova = provas_mod.provar(co_tipo, escolhida.js_posicao_inicial, chegada, motor=motor)
        if prova.passou:
            return {
                "posicao": escolhida.js_posicao_inicial,
                "chegada": chegada,
                "teto": publicacao.nu_maximo_de_meios_lances,
                "lances": int(parametros["lances"]),
            }
    return None


def _posicao_do_controle(indice: int) -> dict[str, Any]:
    """Uma posicao da base, crua: o controle nao tem pecas marcadas."""
    base = posicoes_mod.carregar_base()
    fen = base[random.Random(f"{SEMENTE}:{CONTROLE}:{indice}").randrange(len(base))]
    return {
        "jogo": "xadrez",
        "modalidade": posicoes_mod.MODALIDADE,
        "fen": fen,
        "cor_da_pessoa": posicoes_mod.cor_da_vez(fen),
        "origem": posicoes_mod.ORIGEM_BASE_EQUILIBRADA,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Uma partida
# ═══════════════════════════════════════════════════════════════════════════


def _lance_de_quem_resolve(
    jogador: provas_mod.JogadorDoDesafioXadrez,
    solucionador,
    inicial: provas_mod.EstadoXadrez,
    estado: provas_mod.EstadoXadrez,
    nivel: NivelDeMotor,
    semente: int,
) -> str:
    """O lance da pessoa: o do nivel cru, ou o do perseguidor DA PRODUCAO."""
    def do_nivel() -> str:
        return jogador.escolher_lance(estado, nivel, semente=semente)

    if solucionador is None:
        return do_nivel()
    return solucionador(
        solucionadores_mod.ContextoDoSolucionador(
            arbitro=jogador.arbitro,
            jogador=jogador,
            estado_inicial=inicial,
            estado=estado,
            nivel=nivel,
            semente=semente,
            lance_do_nivel=do_nivel,
        )
    )


def _jogar_desafio(
    jogador: provas_mod.JogadorDoDesafioXadrez,
    co_tipo: str,
    amostra: dict[str, Any],
    modo: str,
    nu_semente: int,
) -> dict[str, Any]:
    """Uma partida de [modo] a partir da posicao do tipo, ate cumprir ou o teto.

    Returns:
        `cumpriu`; `lance` (o lance DA PESSOA em que caiu, contado de 1; `None`
        sem cumprir); `erros` (os erros sorteados do adversario ANTES de cumprir,
        ou na partida toda, sem cumprir); `meios` (os meios-lances jogados).
    """
    posicao, chegada = amostra["posicao"], amostra["chegada"]
    solucionador = (
        None
        if modo == "magno_so_vence"
        else solucionadores_mod.com_chegada(
            solucionadores_mod.perseguidor_do_xadrez(co_tipo), chegada
        )
    )
    inicial = provas_mod.estado_inicial(posicao)
    estado, fita, erros = inicial, [], 0
    for numero in range(1, amostra["teto"] + 1):
        # A semente do lance e a do gerador (`n` a partir da posicao publicada).
        semente = semente_mod.semente_do_lance(nu_semente, numero)
        vez = jogador.arbitro.vez_de(estado)
        try:
            if vez == provas_mod.VEZ_DA_PESSOA:
                lance = _lance_de_quem_resolve(
                    jogador, solucionador, inicial, estado, NIVEL_DO_MODO[modo], semente
                )
            else:
                decisao = jogador.decidir(estado, ADVERSARIO, semente)
                lance = decisao.lance
                erros += decisao.co_acao in ACOES_DE_ERRO
        except ValueError:
            # A partida acabou antes do objetivo.
            break
        estado = jogador.aplicar(estado, lance)
        fita.append({"n": numero, "jogador": vez, "lance": lance})
        julgamento = julgar_desafio(
            co_jogo="xadrez", js_posicao_inicial=posicao, js_chegada=chegada,
            fita=fita, jogador=provas_mod.VEZ_DA_PESSOA,
        )
        if julgamento.cumpriu:
            n = julgamento.nu_lance_cumpre_desafio or numero
            return {"cumpriu": True, "lance": (n + 1) // 2, "erros": erros, "meios": len(fita)}
    return {"cumpriu": False, "lance": None, "erros": erros, "meios": len(fita)}


def _jogar_controle(
    jogador: provas_mod.JogadorDoDesafioXadrez,
    posicao: dict[str, Any],
    modo: str,
    nu_semente: int,
) -> dict[str, Any]:
    """Uma partida INTEIRA do controle contra o Tex: venceu, empatou, perdeu."""
    chegada = RECEITAS_FORA_DO_AR["xadrez_dar_mate"].montar({"lances": LANCES_DO_CONTROLE})
    solucionador = (
        None
        if modo == "magno_cru"
        else solucionadores_mod.com_chegada(
            solucionadores_mod.perseguidor_do_xadrez(perseguir.TIPO_DE_CONTROLE), chegada
        )
    )
    motor = jogador.motor
    inicial = provas_mod.estado_inicial(posicao)
    estado = inicial
    for numero in range(1, 2 * LANCES_DO_CONTROLE):
        semente = semente_mod.semente_do_lance(nu_semente, numero)
        if jogador.arbitro.vez_de(estado) == provas_mod.VEZ_DA_PESSOA:
            lance = _lance_de_quem_resolve(
                jogador, solucionador, inicial, estado, NivelDeMotor.SAGAZ, semente
            )
        else:
            lance = jogador.escolher_lance(estado, ADVERSARIO, semente=semente)
        # O `aplicar` do motor direto: e dele que se le o fim da partida.
        resposta = motor.aplicar(
            modalidade=estado.modalidade, fen_inicial=estado.fen_inicial,
            lances=list(estado.lances), lance=lance,
        )
        estado = provas_mod.EstadoXadrez(
            posicao=posicao, lances=estado.lances + (lance,), fen=resposta["fen_depois"]
        )
        fim = resposta["fatos"].get("fim")
        if fim is not None:
            vencedor = fim.get("vencedor")
            if vencedor is None:
                desfecho = "empatou"
            else:
                desfecho = "venceu" if vencedor == posicao["cor_da_pessoa"] else "perdeu"
            return {"desfecho": desfecho, "meios": len(estado.lances)}
    return {"desfecho": "sem_fim", "meios": len(estado.lances)}


def medir_unidade(unidade: tuple[str, int]) -> dict[str, Any]:
    """Uma posicao de um tipo nos cinco modos, ou uma posicao do controle.

    ⚠️ Um executavel SO desta unidade, aberto e fechado pelo `with`: o processo
    do motor nao sobrevive a unidade (a licao do pool que deixava os processos).
    """
    alvo, indice = unidade
    inicio = time.time()
    linha: dict[str, Any] = {"co_tipo": alvo, "indice": indice}
    # Uma semente por unidade, a mesma nos modos: o adversario fica pareado.
    nu_semente = int(random.Random(f"{SEMENTE}:jogo:{alvo}:{indice}").getrandbits(31))
    with JogadorXadrez() as motor:
        jogador = provas_mod.JogadorDoDesafioXadrez(motor)
        if alvo == CONTROLE:
            posicao = _posicao_do_controle(indice)
            linha["fen"] = posicao["fen"]
            for modo in MODOS_DO_CONTROLE:
                linha[modo] = _jogar_controle(jogador, posicao, modo, nu_semente)
        else:
            amostra = _posicao_do_tipo(motor, alvo, indice)
            if amostra is None:
                linha["sem_posicao"] = True
            else:
                linha["fen"] = amostra["posicao"]["fen"]
                linha["janela"] = amostra["lances"]
                for modo in MODOS:
                    linha[modo] = _jogar_desafio(jogador, alvo, amostra, modo, nu_semente)
    linha["segundos"] = round(time.time() - inicio, 1)
    return linha


# ═══════════════════════════════════════════════════════════════════════════
# O relatorio
# ═══════════════════════════════════════════════════════════════════════════


def _ler_diario() -> list[dict[str, Any]]:
    """As linhas ja medidas (vazio na 1a execucao)."""
    if not DIARIO.is_file():
        return []
    return [json.loads(l) for l in DIARIO.read_text(encoding="utf-8").splitlines() if l]


def _percentil(valores: list[int], fracao: float) -> int:
    """O valor abaixo do qual fica [fracao] dos [valores] (o mais proximo)."""
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(fracao * len(ordenados)))]


def _relatorio_do_controle(linhas: list[dict[str, Any]]) -> list[str]:
    medidas = [l for l in linhas if l["co_tipo"] == CONTROLE]
    if not medidas:
        return []
    saida = [
        f"⛔ CONTROLE ({len(medidas)} partidas inteiras contra o {ADVERSARIO.value}, ate "
        f"{LANCES_DO_CONTROLE} lances): o perseguidor de 'so vencer' tem de jogar",
        "   tao bem quanto o Magno cru. Pior aqui = nada se liga.",
    ]
    for modo in MODOS_DO_CONTROLE:
        contagem = {d: 0 for d in ("venceu", "empatou", "perdeu", "sem_fim")}
        for linha in medidas:
            contagem[linha[modo]["desfecho"]] += 1
        saida.append(
            f"   {modo:<18} venceu {contagem['venceu']:>3} · empatou {contagem['empatou']:>3}"
            f" · perdeu {contagem['perdeu']:>3} · sem fim {contagem['sem_fim']:>3}"
        )
    return saida + [""]


def _leitura(co_tipo: str, taxas: dict[str, float]) -> str:
    """Uma primeira leitura do tipo, para o dono saber onde olhar.

    ⚠️ E LEITURA, e nao decisao: quem liga o tipo e a entrada no historico.
    """
    escada = [taxas[m] for m in ("persegue_cacau", "persegue_pita", "persegue_tex", "persegue_magno")]
    crescente = all(b >= a - 0.05 for a, b in zip(escada, escada[1:]))
    ganho = taxas["persegue_magno"] - taxas["magno_so_vence"]
    if taxas["persegue_magno"] < 0.75:
        return "⛔ NEM O MAGNO PERSEGUINDO CHEGA (< 0,75): a posicao volta a T073"
    if ganho > 0 and crescente:
        return "✅ GANHO E ESCADA CRESCENTE: candidato a SOLUCIONADOR_POR_TIPO"
    if ganho <= 0:
        return "⚠️ SEM GANHO sobre o Magno que so vence"
    return "⚠️ GANHO, mas a escada nao cresce"


def relatorio(linhas: list[dict[str, Any]]) -> str:
    """O controle, e por tipo: cumpriu por modo, a leitura e a folga do prazo."""
    saida = [
        "Perseguidor do objetivo x Magno que so vence (xadrez, T076a da spec 012)",
        f"adversario: {ADVERSARIO.value} · as posicoes e as sementes sao as mesmas nos modos",
        "",
    ]
    saida += _relatorio_do_controle(linhas)
    for co_tipo in TIPOS:
        medidas = [l for l in linhas if l["co_tipo"] == co_tipo and not l.get("sem_posicao")]
        sem = sum(1 for l in linhas if l["co_tipo"] == co_tipo and l.get("sem_posicao"))
        if not medidas and not sem:
            continue
        n = len(medidas)
        janela = medidas[0]["janela"] if medidas else "?"
        saida.append(f"{co_tipo} (em ate {janela} lances): {n} posicoes ({sem} sem posicao provada)")
        taxas = {}
        for modo in MODOS:
            cumpriu = sum(l[modo]["cumpriu"] for l in medidas)
            taxas[modo] = cumpriu / n if n else 0.0
            saida.append(f"   {modo:<16} cumpriu {cumpriu:>3} de {n} ({taxas[modo]:4.2f})")
        if n:
            saida.append(f"   leitura: {_leitura(co_tipo, taxas)}")
        # A folga do prazo: em que lance o perseguidor-Magno cumpriu, e os erros
        # do adversario antes. ⚠️ Nos "Passe N" o lance e sempre o N.
        lances = [l["persegue_magno"]["lance"] for l in medidas if l["persegue_magno"]["cumpriu"]]
        erros = [l["persegue_magno"]["erros"] for l in medidas if l["persegue_magno"]["cumpriu"]]
        if lances and co_tipo not in TIPOS_PASSE_N:
            saida.append(
                f"   folga (persegue_magno, {len(lances)} cumpridos): lance mediano "
                f"{statistics.median(lances):.1f} · 75% ate o {_percentil(lances, 0.75)}o · "
                f"o mais tarde {max(lances)}o, de {janela} · no ultimo lance: "
                f"{sum(1 for x in lances if x == janela)} · erros do adversario antes: "
                f"media {statistics.mean(erros):.1f}, maximo {max(erros)}"
            )
        saida.append("")
    return "\n".join(saida)


# ═══════════════════════════════════════════════════════════════════════════
# A execucao
# ═══════════════════════════════════════════════════════════════════════════


def principal(argumentos: list[str]) -> int:
    """Le os argumentos, mede o que falta, e escreve o relatorio."""
    leitor = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    leitor.add_argument("--posicoes", type=int, default=30)
    leitor.add_argument("--controle", type=int, default=30)
    leitor.add_argument("--processos", type=int, default=os.cpu_count() or 1)
    leitor.add_argument("--tipos", default=",".join((CONTROLE, *TIPOS)))
    args = leitor.parse_args(argumentos)

    alvos = args.tipos.split(",")
    desconhecidos = set(alvos) - {CONTROLE, *TIPOS}
    if desconhecidos:
        leitor.error(f"tipos desconhecidos: {sorted(desconhecidos)}")

    PASTA.mkdir(parents=True, exist_ok=True)
    feitas = {(l["co_tipo"], l["indice"]) for l in _ler_diario()}
    pendentes = [
        (alvo, indice)
        for alvo in alvos
        for indice in range(args.controle if alvo == CONTROLE else args.posicoes)
        if (alvo, indice) not in feitas
    ]
    # ⚠️ O controle primeiro (e o mais longo, e o que reprova tudo), depois os
    # tipos intercalados: a previsao de tempo dos primeiros minutos fica honesta.
    pendentes.sort(key=lambda u: (u[0] != CONTROLE, u[1], u[0]))
    print(
        f"{len(feitas)} unidades ja no diario; {len(pendentes)} a medir, "
        f"em {args.processos} processos.",
        flush=True,
    )
    inicio = time.time()
    with multiprocessing.Pool(args.processos) as pool, DIARIO.open("a", encoding="utf-8") as diario:
        for i, linha in enumerate(pool.imap_unordered(medir_unidade, pendentes), 1):
            # Uma linha por unidade, gravada na hora: e o que torna a medicao
            # retomavel se a janela fechar no meio.
            diario.write(json.dumps(linha, ensure_ascii=False) + "\n")
            diario.flush()
            gasto = time.time() - inicio
            falta = gasto / i * (len(pendentes) - i)
            print(
                f"[{i}/{len(pendentes)}] {linha['co_tipo']} #{linha['indice']} "
                f"{linha['segundos']} s · {gasto / 60:.1f} min no total · "
                f"faltam ~{falta / 60:.0f} min",
                flush=True,
            )
    texto = relatorio(_ler_diario())
    RELATORIO.write_text(texto, encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
