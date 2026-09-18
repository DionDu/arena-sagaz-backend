"""A fila de trabalho do gerador de desafios, para rodar por dias sem vigia.

⚠️ **Isto e um MAESTRO, e nao um instrumento novo.** Ele nao mede nada por conta
propria: chama `pescar_moldes_de_partidas.py` e `medir_variantes_do_editorial.py`,
que ja existem, ja sao testados e ja sabem retomar. ⛔ Reimplementar a pescaria
aqui criaria uma segunda verdade sobre o que e um molde bom — o defeito que este
projeto ja pagou caro tres vezes.

**O que ele resolve:** a fila do gerador tem ~20 h de maquina em etapas
independentes, e a janela do dono nao acompanha. Ele roda tudo em ordem, grava o
que terminou, e **recomeca de onde parou** quando for relancado.

⚠️ **Dois niveis de retomada, e vale saber a diferenca:**

  * **entre etapas** — este script. Etapa concluida nao se repete, nunca.
  * **dentro de uma etapa** — so as PESCARIAS tem, pelo diario delas. Uma medicao
    interrompida recomeca do zero na proxima vez, porque ela mede dias inteiros e
    meio dia medido nao e resultado nenhum.

⛔ **NADA AQUI ESCREVE NO ACERVO NEM NO EDITORIAL.** Ele junta materia-prima: os
diarios das pescarias e os relatorios das reguas. Trocar acervo e publicar
variante continuam sendo decisao lida e tomada por gente — foi assim que o
`damas_coroar` saiu do banal, e foi a leitura do resultado, e nao a coleta, que
achou cada um dos defeitos.

USO
    .venv\\Scripts\\python -u scripts\\maratona_do_gerador.py
    .venv\\Scripts\\python -u scripts\\maratona_do_gerador.py --estado
    .venv\\Scripts\\python -u scripts\\maratona_do_gerador.py --refazer <etapa>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ⚠️ **O console do PowerShell e cp1252**, e este script imprime ⏳ e ✅. Sem
# isto, a maratona morre na primeira linha do resumo com `UnicodeEncodeError` —
# ⛔ antes de rodar uma unica etapa, e depois de o dono ter saido de perto.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = RAIZ / ".venv" / "Scripts" / "python.exe"

#: Onde fica o que ja terminou. ⛔ Apagar este arquivo refaz a maratona inteira.
ESTADO = RAIZ / "maratona_do_gerador.json"

#: Um log por etapa, em append: relancar nao apaga o que a rodada anterior disse.
LOGS = RAIZ / "logs" / "maratona"

#: As posicoes reais de onde os moldes de damas saem — as mesmas que o dono usou
#: na pescaria do `damas_coroar`.
FENS = "fens_damas_prd_e_des.json"


def _pescaria(co_tipo: str, parametros: str, teto: int) -> list[str]:
    """Uma pescaria de moldes, com diario proprio (logo, retomavel).

    ⚠️ **O `--teto` e o ponto da etapa toda.** O teto da peneira e o mesmo do
    editorial, e foi ele que fabricou o acervo banal do `damas_coroar`: com teto
    12, toda posicao que demorasse mais saia como `nao_cumpriu_no_teto`, e nenhum
    molde passava de 11 **porque 12 era a parede**. ⛔ Nao era o jogo.

    ⚠️ **26 e o mesmo numero que destravou o coroar**, e comporta `p` de ate 13
    lances do jogador. Ele nao obriga ninguem a publicar tao longe: so deixa o
    molde longo ser ENCONTRADO, para a medicao poder escolher.
    """
    return [
        "scripts/pescar_moldes_de_partidas.py", FENS,
        "--tipo", co_tipo,
        "--parametros", parametros,
        "--teto", str(teto),
        "--minimo-pecas", "12",
        "--embaralhar",
        "--processos", "14",
        "--diario", f"maratona_{co_tipo}.jsonl",
    ]


def _medicao(alvo: str) -> list[str]:
    """A regua sobre as variantes ja publicadas de um alvo.

    ⚠️ **Sempre `--com-regua`.** Sem ela mede-se so se a variante GERA; em
    15/09/2026 seis variantes deram `FOLGA 3 de 3` e a regua achou uma dura demais
    e outra com a escada invertida (Cacau 30/30 onde o Magno fazia 7/10).
    """
    return ["scripts/medir_variantes_do_editorial.py", alvo, "--com-regua"]


# ═══════════════════════════════════════════════════════════════════════════
# A FILA
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **A ordem nao e arbitraria: e da pergunta mais barata para a mais cara.**
#
#   1. As REMEDICOES primeiro. Elas nao dependem de pescaria nenhuma, respondem
#      a pendencia mais antiga (a escada substituiu a media em 16/09 e nada foi
#      remedido com ela), e sao as unicas que podem condenar uma variante que
#      esta no ar HOJE.
#   2. As PESCARIAS depois, da maior promessa para a menor. O `damas_sacrificio`
#      vem primeiro por ter o teto mais apertado dos quatro: 12, exatamente o
#      numero que produzia o acervo banal do coroar.
#
# ⚠️ Cada tupla e `(nome, comando, quanto deve demorar)`. O tempo e estimativa
# grosseira, e serve so para o dono saber se pode sair de perto.

FILA: list[tuple[str, list[str], str]] = [
    # ── 1. O que pode condenar o que ja esta publicado ───────────────────────
    (
        "regua-damas-no-ar",
        _medicao("no-ar-damas"),
        "~2h",
    ),
    (
        "regua-pontinhos-no-ar",
        _medicao("no-ar-pontinhos"),
        "~1h",
    ),
    # ── 2. Os acervos que nunca viram um teto folgado ────────────────────────
    #
    # ⚠️ Os parametros sao os do editorial de hoje, com a JANELA aberta ate o teto
    # novo: pescar com a janela curta so reencontraria os mesmos moldes curtos.
    (
        "pescaria-sacrificio",
        _pescaria(
            "damas_sacrificio",
            "[{'capturar': 2, 'entregar': 1, 'lances': 13},"
            " {'capturar': 3, 'entregar': 1, 'lances': 13},"
            " {'capturar': 3, 'entregar': 2, 'lances': 13}]",
            teto=26,
        ),
        "~8h",
    ),
    (
        "pescaria-sobreviver",
        _pescaria(
            "damas_sobreviver",
            "[{'lances': 10, 'entregar': 1}, {'lances': 12, 'entregar': 2}]",
            teto=26,
        ),
        "~6h",
    ),
    (
        "pescaria-capturar-multipla",
        _pescaria(
            "damas_capturar_multipla",
            "[{'pecas': 2, 'lances': 13}, {'pecas': 3, 'lances': 13}]",
            teto=26,
        ),
        "~6h",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# O MAESTRO
# ═══════════════════════════════════════════════════════════════════════════


def _ler_estado() -> dict:
    if not ESTADO.exists():
        return {}
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # ⚠️ Estado corrompido nao pode travar a maratona: o pior que acontece e
        # repetir uma etapa, e repetir e barato perto de nao rodar.
        return {}


def _gravar_estado(estado: dict) -> None:
    ESTADO.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _rodar(nome: str, argumentos: list[str], estado: dict) -> bool:
    """Roda uma etapa, gravando o log e o estado. Devolve `True` se terminou bem.

    ⛔ **O log vai para arquivo E para a tela ao mesmo tempo.** So para a tela, a
    maratona de tres dias existiria apenas no scrollback de um PowerShell — que e
    exatamente o defeito que a primeira versao do medidor teve, em 18/09/2026.
    """
    LOGS.mkdir(parents=True, exist_ok=True)
    caminho = LOGS / f"{nome}.log"
    comeco = time.monotonic()

    print(f"\n{'=' * 70}")
    print(f"▶ {nome}   (log: logs/maratona/{nome}.log)")
    print(f"{'=' * 70}", flush=True)

    with caminho.open("a", encoding="utf-8", errors="replace") as log:
        log.write(f"\n\n===== {nome} — {datetime.now():%Y-%m-%d %H:%M} =====\n")
        log.flush()
        processo = subprocess.Popen(
            [str(PYTHON), "-u", *argumentos],
            cwd=str(RAIZ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        for linha in processo.stdout:  # type: ignore[union-attr]
            print(linha, end="", flush=True)
            log.write(linha)
            log.flush()
        codigo = processo.wait()

    gasto = (time.monotonic() - comeco) / 60
    if codigo == 0:
        estado[nome] = {"quando": f"{datetime.now():%Y-%m-%d %H:%M}", "minutos": round(gasto)}
        _gravar_estado(estado)
        print(f"\n✅ {nome} — {gasto:.0f} min", flush=True)
        return True

    # ⛔ Etapa que falhou NAO entra no estado: a proxima execucao a repete.
    print(f"\n⛔ {nome} — saiu com codigo {codigo} depois de {gasto:.0f} min", flush=True)
    return False


def main() -> int:
    estado = _ler_estado()

    if "--estado" in sys.argv:
        print(f"{'etapa':<28} {'quando':<18} tempo")
        print("-" * 56)
        for nome, _cmd, previsto in FILA:
            feito = estado.get(nome)
            if feito:
                print(f"{nome:<28} {feito['quando']:<18} {feito['minutos']} min ✅")
            else:
                print(f"{nome:<28} {'-':<18} falta ({previsto})")
        return 0

    if "--refazer" in sys.argv:
        alvo = sys.argv[sys.argv.index("--refazer") + 1]
        estado.pop(alvo, None)
        _gravar_estado(estado)
        print(f"{alvo}: marcada para refazer")
        return 0

    faltam = [(n, c, p) for n, c, p in FILA if n not in estado]
    if not faltam:
        print("✅ a maratona inteira ja terminou. --estado mostra quando.")
        return 0

    print(f"maratona do gerador — {len(faltam)} de {len(FILA)} etapa(s) a fazer")
    for nome, _cmd, previsto in faltam:
        print(f"   ⏳ {nome}  ({previsto})")
    print(
        "\n⚠️ Pode interromper com Ctrl+C: a etapa em curso recomeca, as "
        "concluidas nao.\n"
        "⚠️ As PESCARIAS ainda retomam por dentro, pelo diario delas.",
        flush=True,
    )

    comeco = time.monotonic()
    for nome, comando, _previsto in faltam:
        try:
            if not _rodar(nome, comando, estado):
                print(
                    f"\n⛔ A maratona parou em '{nome}'. O log tem o motivo.\n"
                    "   Relance o mesmo comando para tentar de novo a partir dela.",
                    flush=True,
                )
                return 1
        except KeyboardInterrupt:
            print(
                f"\n\n⏸️ Interrompida em '{nome}'. As etapas concluidas estao "
                "gravadas; relance o mesmo comando para continuar.",
                flush=True,
            )
            return 130

    print(f"\n✅ MARATONA COMPLETA — {(time.monotonic() - comeco) / 3600:.1f} h")
    print("   Os relatorios estao em logs/maratona/ e os diarios em maratona_*.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
