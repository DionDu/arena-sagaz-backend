"""RODA O JOB DE DESAFIOS NA MAQUINA DO DONO, em vez de no Railway.

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 16/09/2026 o dono escreveu:

> *"hoje ele roda agendado no Railway. Mas eventualmente eu posso 'economizar'
> dinheiro e roda-los na minha maquina. Se isso for possivel seria interessante
> (ex: eu deixo minha maquina ligada rodando os desafios dos proximos 14 dias,
> por exemplo)."*

⚠️ **E possivel, e o job nao precisou mudar para isso.** Ele ja e um processo
que le `DATABASE_URL`, faz o trabalho e morre — nada nele depende do Railway.
O que faltava era **como chamar** sem decorar o nome da variavel e sem correr o
risco de apontar para o banco errado.

⚠️ **O Railway custa por tempo de EXECUCAO.** Medido em 16/09/2026: 1.360 s para
quatro dias, dos quais 1.024 s foram um unico `damas_sobreviver`. Uma variante
cara paga o dia inteiro — e rodar aqui custa so eletricidade.

═══════════════════════════════════════════════════════════════════════════
⛔ ESTE SCRIPT **ESCREVE** NO BANCO — E E O OPOSTO DE `consultar_prd.py`
═══════════════════════════════════════════════════════════════════════════

`consultar_des.py` e `consultar_prd.py` sao somente-leitura, com trava tripla e
quadrupla. ⛔ **Aqui nao ha o que travar**: o job existe para gravar desafios.
Entao a defesa e outra — **o ambiente e explicito, e producao exige dizer que
sim duas vezes**:

    python scripts/rodar_job_local.py                      → des, 7 dias
    python scripts/rodar_job_local.py --dias 14            → des, 14 dias
    python scripts/rodar_job_local.py --ambiente prd --confirmo-escrita-em-producao

⚠️ **E mesmo no `prd` o estrago possivel e pequeno, de proposito:** tudo o que o
job grava nasce `candidato` (RF-DES-012a), e nada vai ao ar sem o dono aprovar no
painel de curadoria. ⛔ O que ele **nao** faz e apagar ou alterar desafio
existente — dia ja publicado e pulado, nao regravado.

═══════════════════════════════════════════════════════════════════════════
⚠️ ISTO E PROCESSO LONGO
═══════════════════════════════════════════════════════════════════════════

Medido no Railway: ~22 min para quatro dias gerados, com um deles sozinho
levando 17. Catorze dias podem passar de uma hora. ⚠️ **Deixe rodando e va fazer
outra coisa** — o job imprime cada dia conforme termina, e o resumo no fim traz
`[job] tempo:` com o custo de cada um.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_ECOSSISTEMA = RAIZ_BACKEND.parent
sys.path.insert(0, str(RAIZ_BACKEND))

# ⚠️ O console do Windows e cp1252; sem isto, um acento no log derruba o job.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

#: O catalogo dos dois bancos, fora do Git (o mesmo que os scripts de consulta
#: leem — ver `consultar_des.py`).
CATALOGO = RAIZ_ECOSSISTEMA / "ferramentas" / "debug-bancos" / "ambientes.env"

#: De que variavel do catalogo sai a URL de cada ambiente.
VARIAVEL_POR_AMBIENTE = {
    "des": "DATABASE_URL_DES",
    "prd": "DATABASE_URL_PRD",
}


def url_do_ambiente(co_ambiente: str) -> str:
    """A URL daquele ambiente, lida do catalogo do ecossistema.

    ⛔ **Nunca devolve a URL para a tela**, e quem chama tambem nao pode imprimi-la:
    ela carrega a senha. A mesma regra de `identificar_banco.py`.

    Raises:
        SystemExit: quando o arquivo ou a chave nao existem.
    """
    variavel = VARIAVEL_POR_AMBIENTE[co_ambiente]
    if not CATALOGO.exists():
        raise SystemExit(f"⛔ catalogo nao encontrado: {CATALOGO}")

    for linha in CATALOGO.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == variavel:
            bruta = valor.strip().strip('"').strip("'")
            if not bruta:
                raise SystemExit(f"⛔ {variavel} esta vazia no catalogo.")
            # ⚠️ O job usa SQLAlchemy async, que precisa do driver no esquema —
            # a mesma normalizacao dos scripts de consulta.
            return re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", bruta, count=1)

    raise SystemExit(f"⛔ {variavel} nao esta em {CATALOGO}")


def conferir_o_motor() -> None:
    """Sobe o motor Dart antes de comecar, e falha AQUI se algo faltar.

    ═══════════════════════════════════════════════════════════════════════
    ⚠️ POR QUE ANTES, E NAO NO PRIMEIRO LANCE
    ═══════════════════════════════════════════════════════════════════════

    Desde 25/09/2026 quem joga pelo servidor e o **motor Dart compilado**, o
    mesmo que o aplicativo embarca, e ele precisa de duas coisas no disco: o
    executavel (carimbado com o SHA-256 dos fontes) e a base de finais que o
    aplicativo embarca.

    ⛔ **Faltando qualquer uma, o job falha - e falha bem.** O que nao pode
    acontecer e descobrir isso no meio da geracao do quarto dia, depois de
    quarenta minutos de regua. Aqui custa dois segundos, e a mensagem de cada
    uma ja traz a receita de como resolver.

    ⚠️ **E o resumo impresso nao e enfeite:** e ele que responde, meses depois,
    *"esta fila saiu de que motor?"*.
    """
    from motores.damas.jogador_dart import JogadorDart, pasta_da_base_de_finais
    from motores.damas.motor_damas import motor_de_busca_escolhido

    escolhido = motor_de_busca_escolhido()
    if escolhido != "dart":
        print(
            f"⛔ [rodar_job_local] MOTOR_DAMAS_DO_SERVIDOR={escolhido!r}: o job "
            f"jogaria com o port Python, que ⛔ NAO e o motor do aparelho.\n"
            f"   O gabarito nao bateria com a partida de ninguem. Ver "
            f"docs/investigacao_paridade_motores.md.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    with JogadorDart() as jogador:
        print(
            f"[rodar_job_local] motor: dart, resumo "
            f"{jogador.resumo_do_motor[:16]} (a trava passou)"
        )
    for co_modalidade in ("brasileira", "anglo", "portuguesa", "casa"):
        pasta_da_base_de_finais(co_modalidade)
    print("[rodar_job_local] base de finais: as quatro modalidades no lugar")


def main() -> int:
    """Le os argumentos, prepara o ambiente e chama o job."""
    ap = argparse.ArgumentParser(
        description="Roda o job de desafios aqui, em vez de no Railway.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--ambiente",
        choices=sorted(VARIAVEL_POR_AMBIENTE),
        default="des",
        help="em qual banco gravar (padrao: des)",
    )
    ap.add_argument(
        "--dias",
        type=int,
        default=None,
        help=(
            "quantos dias cobrir a partir de hoje. Padrao: a folga do job (7). "
            "⚠️ Dia ja publicado e pulado, entao pedir 14 num dia com a fila "
            "cheia gera pouco ou nada."
        ),
    )
    ap.add_argument(
        "--confirmo-escrita-em-producao",
        action="store_true",
        help="obrigatorio com `--ambiente prd`. ⛔ O job GRAVA.",
    )
    args = ap.parse_args()

    # ── ⛔ A trava do `prd`: dizer que sim duas vezes ────────────────────────
    #
    # ⚠️ Uma flag longa e feia de propósito. Quem a digita nao a digitou por
    # engano, e ela fica no historico do shell para quem for investigar depois.
    if args.ambiente == "prd" and not args.confirmo_escrita_em_producao:
        raise SystemExit(
            "⛔ `--ambiente prd` GRAVA no banco dos usuarios reais.\n"
            "   Se e isso mesmo, repita com "
            "`--confirmo-escrita-em-producao`.\n"
            "   ⚠️ Tudo o que o job grava nasce `candidato` e passa pela sua "
            "curadoria antes de ir ao ar."
        )

    # ⛔ O job le `DATABASE_URL` do ambiente — e e so isto que o Railway faz.
    os.environ["DATABASE_URL"] = url_do_ambiente(args.ambiente)
    if args.dias is not None:
        os.environ["DESAFIO_DIAS_A_COBRIR"] = str(args.dias)

    aviso = "⚠️  PRODUCAO (prd) — o job VAI GRAVAR" if args.ambiente == "prd" else "banco: des"
    print(f"[rodar_job_local] {aviso}")
    print(
        "[rodar_job_local] dias: "
        + (f"{args.dias} (por DESAFIO_DIAS_A_COBRIR)" if args.dias else "a folga padrao")
    )
    conferir_o_motor()

    print(
        "[rodar_job_local] ⚠️ isto demora. Medido em 25/09/2026, na maquina do "
        "dono, ja com o motor Dart: ~5 min por candidato de damas, ~15 min por "
        "dia (sao 3 candidatos). ⛔ E a REGUA que domina, porque o Magno agora "
        "gasta os 288 mil nos do contrato em cada lance.\n"
    )

    # ⚠️ **Importado aqui, e nao no topo**, porque o job le `DATABASE_URL` ao ser
    # executado e queremos a variavel ja no lugar. ⛔ Chamamos `principal()`, e nao
    # `python -m job`: assim o processo e um so, e o `os._exit` do `__main__` (que
    # existe para o container do Railway morrer) nao nos atrapalha aqui.
    from job.__main__ import principal

    return principal()


if __name__ == "__main__":
    raise SystemExit(main())
