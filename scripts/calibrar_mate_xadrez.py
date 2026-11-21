"""A calibracao do acervo de mate do xadrez: que problema cai na escada contra quem.

═══════════════════════════════════════════════════════════════════════════
POR QUE EXISTE (21/11/2026, historico "2026-11-21 (8)")
═══════════════════════════════════════════════════════════════════════════

O `xadrez_dar_mate` caiu na escada em 1 dia de 9 na 4a regua da T077, e o motivo
e do proprio mate: num problema de mate em 2, cada mascote acerta quase sempre ou
quase nunca (a busca do nivel ve o mate ou nao ve, e em dois lances o erro
sorteado quase nao pesa). Em 600 problemas medidos, so 27 (4,5%) cairam na
escada, e o rating do Lichess nao separa os que caem (de 3% a 6% em toda faixa).

O acervo e fixo (`dados/jogo_xadrez/problemas_de_mate.json`), entao se mede UMA
vez: cada problema contra cada adversario possivel, com a mesma conta da regua
do job (`regua.tentativa_com_motor`, 20 execucoes por mascote, o mesmo teto de
meios-lances do editorial). O resultado vai para
`dados/jogo_xadrez/calibracao_do_mate.json` (no Git: o job do Railway le), e o
sorteio do dia escolhe entre os problemas que cairam na escada contra o
adversario do dia (`provas_xadrez.problemas_calibrados`).

⛔ **A regua do dia continua medindo.** A calibracao escolhe o acervo, e nao
aprova o candidato: as sementes do dia sao outras, e a regua e quem decide.

⚠️ **Motor novo, calibracao nova.** O arquivo leva a versao do motor; com outra,
o sorteio volta ao acervo inteiro e avisa no log. Rode este script de novo.

═══════════════════════════════════════════════════════════════════════════
O ATALHO: PARAR CEDO
═══════════════════════════════════════════════════════════════════════════

Um problema so serve se TODOS os mascotes medidos cairem na escada, entao a
medicao de uma unidade (um problema contra um adversario) para no primeiro
mascote que sai dela - e o primeiro medido e o mais seletivo (a Pita, depois o
Tex). Dentro de um mascote, as execucoes param quando a contagem ja nao pode
terminar dentro da faixa (a Pita com 10 acertos em 20 ja passou de 0,45).
O resultado e o mesmo de medir tudo; so o tempo muda.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA (comando do dono; §8zzzm: retomavel, todos os nucleos, arquivo)
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python -u scripts\\calibrar_mate_xadrez.py

Cada unidade concluida vira uma linha de
`medicoes/calibrar_mate_xadrez/diario.jsonl`; rodar de novo pula o que ja esta
la (da mesma versao do motor, do mesmo N e das mesmas execucoes). No fim, o
script reescreve `dados/jogo_xadrez/calibracao_do_mate.json` e
`medicoes/calibrar_mate_xadrez/relatorio.txt` a partir do diario inteiro.
Opcoes: `--processos N` (padrao: os nucleos menos um), `--limite N` (so os N
primeiros problemas; para cronometrar).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

# `Path(__file__).resolve().parents[1]` e a pasta do backend (o pai de
# `scripts/`): e de la que `job` e `motores` se importam.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from job import alvo_observado as alvo_mod  # noqa: E402
from job import editorial as editorial_mod  # noqa: E402
from job import provas_xadrez as provas_mod  # noqa: E402
from job import regua as regua_mod  # noqa: E402
from job import tipos_de_desafio as tipos_mod  # noqa: E402
from job.perfil import NIVEL_POR_PERSONAGEM  # noqa: E402
from motores.xadrez import contrato_xadrez  # noqa: E402

#: O tipo calibrado.
TIPO = provas_mod.TIPO_DO_MATE

#: Onde moram o diario e o relatorio (fora do Git: `medicoes/` esta no `.gitignore`).
PASTA = RAIZ / "medicoes" / "calibrar_mate_xadrez"

#: Quantas execucoes por mascote: as MESMAS da regua do job.
EXECUCOES = regua_mod.EXECUCOES_PADRAO

#: A ordem em que os mascotes sao medidos numa unidade: o mais seletivo primeiro.
#:
#: ⚠️ Medidos em 600 problemas: a Pita cai na faixa dela (0,05 a 0,45) em poucos,
#: o Tex em mais, a Cacau na maioria e o Magno em quase todos. Comecar pela Pita
#: e o que deixa a maioria das unidades terminar depois de um mascote so.
ORDEM_DE_MEDIDA = ("pita", "tex", "cacau", "magno")


def publicacao_do_mate():
    """A variante do editorial do mate (o N e o teto de meios-lances).

    ⚠️ O mate tem uma variante so; se um dia tiver mais, a calibracao precisa de
    um arquivo por N, e o script recusa em vez de escolher uma calado.
    """
    # No ar, o editorial; ainda em avaliacao (a T077), o editorial fora do ar.
    if TIPO in editorial_mod.EDITORIAL:
        variantes = editorial_mod.variantes_de(TIPO)
    else:
        variantes = editorial_mod.EDITORIAL_FORA_DO_AR[TIPO]
    if len(variantes) != 1:
        raise SystemExit(
            f"⛔ o editorial do {TIPO} tem {len(variantes)} variantes; a calibracao "
            "mede um N so. Ajuste o script antes de rodar."
        )
    return variantes[0]


def receita_do_mate():
    """A receita do mate, no ar ou ainda em avaliacao."""
    return tipos_mod.RECEITAS.get(TIPO) or tipos_mod.RECEITAS_FORA_DO_AR[TIPO]


def faixa_de_acertos(faixa: tuple[float, float], execucoes: int) -> tuple[int, int]:
    """A faixa da escada em ACERTOS: (minimo, maximo) de `execucoes`.

    O `1e-9` protege da conta em ponto flutuante: 0,45 x 20 da
    9,000000000000002, e sem a folga o `floor` ainda daria 9, mas 0,05 x 20 =
    1,0000000000000002 daria `ceil` 2.
    """
    piso, teto = faixa
    return math.ceil(piso * execucoes - 1e-9), math.floor(teto * execucoes + 1e-9)


def semente_da_unidade(id_problema: str, adversario: str) -> int:
    """Uma semente fixa por unidade, na faixa da semente do job ([1, 2^32 - 1]).

    Fixa para a medicao ser reproduzivel; derivada do texto (SHA-256) para nao
    coincidir com as sementes do job, que sao sorteadas por candidato.
    """
    resumo = hashlib.sha256(f"calibracao-mate:{id_problema}:{adversario}".encode()).digest()
    return 1 + int.from_bytes(resumo[:4], "big") % (2**32 - 1)


# O jogador do processo: um motor por processo, aberto na primeira unidade.
_JOGADOR = None


def medir_unidade(unidade: tuple[dict[str, Any], str, int, int, dict]) -> dict[str, Any]:
    """Um problema contra um adversario: os mascotes medidos, ate o primeiro fora.

    Returns:
        A linha do diario: o problema, o adversario, os acertos de cada mascote
        medido e se a unidade caiu na escada.
    """
    global _JOGADOR
    from motores.juiz import julgar_desafio

    problema, adversario, lances, teto, escada = unidade
    if _JOGADOR is None:
        _JOGADOR = provas_mod.JogadorDoDesafioXadrez()
    posicao = {
        "jogo": "xadrez",
        "modalidade": "tradicional",
        "fen": problema["fen"],
        "cor_da_pessoa": problema["cor_da_pessoa"],
        "origem": provas_mod.ORIGEM_PROBLEMAS_LICHESS,
    }
    chegada = receita_do_mate().montar({"lances": lances})

    def julgar(fita):
        """Julga a fita contra a chegada do mate, como a bancada do job."""
        return julgar_desafio(
            co_jogo="xadrez",
            js_posicao_inicial=posicao,
            js_chegada=chegada,
            fita=fita,
            jogador=provas_mod.VEZ_DA_PESSOA,
        )

    # ⛔ A MESMA funcao da regua do job: o mesmo orcamento por lance, a mesma
    # derivacao de semente por execucao e o mesmo nivel de cada lado.
    tentar = regua_mod.tentativa_com_motor(
        jogador=_JOGADOR,
        estado_inicial=provas_mod.estado_inicial(posicao),
        julgar=julgar,
        nu_semente=semente_da_unidade(problema["id"], adversario),
        maximo_de_meios_lances=teto,
        co_personagem_do_dia=adversario,
        # O mate nao tem solucionador proprio: o mascote joga para vencer.
        solucionador=None,
    )
    acertos: dict[str, list[int]] = {}
    na_escada = True
    for quem in ORDEM_DE_MEDIDA:
        if quem == adversario:
            continue
        minimo, maximo = faixa_de_acertos(escada[quem], EXECUCOES)
        feitos = tentados = 0
        for execucao in range(1, EXECUCOES + 1):
            feitos += 1 if tentar(quem, execucao) else 0
            tentados += 1
            restantes = EXECUCOES - tentados
            # Parar cedo: ja passou do maximo, ou nem acertando todas as
            # restantes chega ao minimo.
            if feitos > maximo or feitos + restantes < minimo:
                break
        acertos[quem] = [feitos, tentados]
        if not (tentados == EXECUCOES and minimo <= feitos <= maximo):
            na_escada = False
            break
    return {
        "id": problema["id"],
        "rating": problema["rating"],
        "adversario": adversario,
        "acertos": acertos,
        "na_escada": na_escada,
    }


def ler_diario(caminho: Path) -> list[dict[str, Any]]:
    """As linhas do diario (lista vazia se ele nao existe)."""
    if not caminho.exists():
        return []
    linhas = []
    for texto in caminho.read_text(encoding="utf-8").splitlines():
        if texto.strip():
            linhas.append(json.loads(texto))
    return linhas


def escrever_resultado(linhas: list[dict[str, Any]], carimbo: dict[str, Any], escada) -> str:
    """Grava a calibracao em `dados/` e devolve o texto do relatorio."""
    na_escada_contra: dict[str, list[str]] = defaultdict(list)
    medidos = Counter()
    for linha in linhas:
        medidos[linha["adversario"]] += 1
        if linha["na_escada"]:
            na_escada_contra[linha["adversario"]].append(linha["id"])
    calibracao = {
        **carimbo,
        "escada": {quem: list(faixa) for quem, faixa in escada.items()},
        "medido_em": date.today().isoformat(),
        "medidos_por_adversario": dict(sorted(medidos.items())),
        # `sorted`: o arquivo vai ao Git, e a ordem fixa da um diff legivel.
        "na_escada_contra": {k: sorted(v) for k, v in sorted(na_escada_contra.items())},
    }
    provas_mod.CALIBRACAO_DO_MATE.write_text(
        json.dumps(calibracao, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    partes = [
        f"calibrar_mate_xadrez · {carimbo['versao_do_motor']} · N={carimbo['lances']} "
        f"· {carimbo['execucoes']} execucoes por mascote",
        "",
        "NA ESCADA, por adversario do dia (o que o sorteio do mate tem para escolher):",
    ]
    for adversario in NIVEL_POR_PERSONAGEM:
        total = medidos.get(adversario, 0)
        bons = len(na_escada_contra.get(adversario, ()))
        fracao = f"{bons / total:.1%}" if total else "-"
        partes.append(f"  contra {adversario:6s} {bons:4d} de {total:4d} ({fracao})")
    partes += ["", "Onde as unidades sairam da escada (o primeiro mascote fora):"]
    saidas = Counter()
    for linha in linhas:
        if not linha["na_escada"]:
            ultimo = list(linha["acertos"])[-1]
            feitos, tentados = linha["acertos"][ultimo]
            lado = "alto" if feitos > faixa_de_acertos(escada[ultimo], EXECUCOES)[1] else "baixo"
            saidas[f"{ultimo} {lado}"] += 1
    for motivo, quantas in saidas.most_common():
        partes.append(f"  {motivo:12s} {quantas}")
    partes += [
        "",
        "O QUE OLHAR PRIMEIRO: a linha 'contra magno'. E o adversario mais dificil",
        "(a defesa e a melhor), e se ele ficar com poucos problemas (menos de ~20),",
        "o mate desse dia repete posicoes cedo.",
        f"Calibracao gravada em {provas_mod.CALIBRACAO_DO_MATE.relative_to(RAIZ).as_posix()}.",
    ]
    return "\n".join(partes) + "\n"


def main() -> None:
    """Le o diario, mede o que falta em paralelo e grava a calibracao."""
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--processos", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    analisador.add_argument("--limite", type=int, default=None)
    argumentos = analisador.parse_args()

    publicacao = publicacao_do_mate()
    lances = int(publicacao.parametros["lances"])
    teto = publicacao.nu_maximo_de_meios_lances
    # Sem escada observada, a regua usa a fixa (`regua.ESCADA_ALVO`), e aqui tambem.
    escada = dict(alvo_mod.alvo_para_a_regua().escada or regua_mod.ESCADA_ALVO)
    carimbo = {
        "versao_do_motor": contrato_xadrez.versao_do_motor(),
        "lances": lances,
        "execucoes": EXECUCOES,
    }

    problemas = [p for p in provas_mod.carregar_problemas_de_mate() if int(p["mate_em"]) <= lances]
    if argumentos.limite:
        problemas = problemas[: argumentos.limite]

    PASTA.mkdir(parents=True, exist_ok=True)
    diario = PASTA / "diario.jsonl"
    # So valem as linhas do mesmo motor, N e execucoes: as outras mediram outra coisa.
    validas = [l for l in ler_diario(diario) if all(l.get(k) == v for k, v in carimbo.items())]
    feitas = {(l["id"], l["adversario"]) for l in validas}
    unidades = [
        (problema, adversario, lances, teto, escada)
        for problema in problemas
        for adversario in NIVEL_POR_PERSONAGEM
        if (problema["id"], adversario) not in feitas
    ]
    print(
        f"[calibrar] {len(problemas)} problemas de mate em ate {lances} x 4 adversarios; "
        f"{len(feitas)} unidades no diario, {len(unidades)} a medir, "
        f"{argumentos.processos} processos",
        flush=True,
    )

    inicio = time.time()
    if unidades:
        with diario.open("a", encoding="utf-8") as arquivo, multiprocessing.Pool(
            argumentos.processos
        ) as pool:
            # `imap_unordered` devolve cada unidade quando ela termina: a linha
            # vai ao diario na hora, e uma interrupcao perde so as que estavam
            # no meio.
            for feitas_agora, linha in enumerate(
                pool.imap_unordered(medir_unidade, unidades, chunksize=4), start=1
            ):
                arquivo.write(json.dumps({**carimbo, **linha}, ensure_ascii=False) + "\n")
                arquivo.flush()
                validas.append({**carimbo, **linha})
                if feitas_agora % 200 == 0 or feitas_agora == len(unidades):
                    gasto = time.time() - inicio
                    falta = gasto / feitas_agora * (len(unidades) - feitas_agora)
                    print(
                        f"[calibrar] {feitas_agora}/{len(unidades)} · {gasto / 60:.1f} min "
                        f"gastos · faltam ~{falta / 60:.1f} min",
                        flush=True,
                    )

    # So as unidades dos problemas pedidos (com `--limite`, o diario pode ter mais).
    pedidos = {p["id"] for p in problemas}
    relatorio = escrever_resultado([l for l in validas if l["id"] in pedidos], carimbo, escada)
    (PASTA / "relatorio.txt").write_text(relatorio, encoding="utf-8")
    print(relatorio)


if __name__ == "__main__":
    main()
