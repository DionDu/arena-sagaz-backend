"""A METADE DE DADOS DO CADEADO 8 — diagnostico SOMENTE-LEITURA (T048).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE SCRIPT E SEPARADO DO CI
═══════════════════════════════════════════════════════════════════════════

`tests/unitarios/test_partida_de_desafio_fechada.py` prova o que e **estrutura**:
que as tres saidas de `em_andamento` existem, que o replay recusa partida sem
desfecho, que abandonar nao desfaz nada. Isso roda no CI, sem Postgres.

⛔ **O que ele NAO consegue provar e o dado.** *"Toda resolucao aponta para
partida em estado terminal"* e uma afirmacao sobre **linhas**, e linhas so
existem no banco. Um teste unitario que a prometesse estaria mentindo.

⚠️ E o mesmo desenho de `conferir_migracao_desafio.py`, e pelo mesmo motivo: a
**conferencia em dois niveis** do projeto — o CI pega cedo, o conferidor pega o
que so o banco sabe. O portao **T050** executa este script.

═══════════════════════════════════════════════════════════════════════════
⚠️ **SEM RESOLUCAO PARA CONFERIR E FALHA, E NAO SUCESSO**
═══════════════════════════════════════════════════════════════════════════

E o texto de T048, e a razao de ele estar escrito assim: um conferidor que aprova
o banco vazio **ensina a confiar nele exatamente quando ele nao esta olhando
nada**. Este projeto ja pagou quatro vezes por cadeados verdes e cegos.

Rodar num banco recem-migrado, portanto, **reprova** — e a mensagem diz que isso
e esperado antes de o job e o aplicativo terem produzido a primeira resolucao.

⚠️ Este script **nao escreve nada**. Todas as consultas sao `SELECT`.

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\conferir_desafio_no_banco.py

Codigo de saida: `0` = confere; `2` = reprovou; `1` = nao deu para conectar.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# `parents[1]` sobe de scripts/ ate a raiz do repositorio do backend.
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))

from scripts.conferir_migracao_desafio import _url_do_banco  # noqa: E402

#: Os estados em que uma partida esta **terminada**.
#:
#: ⚠️ `abandonada` conta: ela e um fim legitimo — o de quem parou no objetivo e
#: nao voltou, fechada pelo aplicativo ou pelo job de expiracao (T046). O que
#: **nao** conta e `em_andamento`.
ESTADOS_TERMINAIS = ("concluida", "abandonada")

#: 1) Toda resolucao aponta para partida em estado terminal?
#:
#: ⚠️ **`em_andamento` recente NAO reprova.** Quem acabou de resolver e continuou
#: jogando esta exatamente nesse estado, e e o comportamento esperado
#: (RF-DES-213). O que reprova e passar dos 7 dias do job de expiracao — ai o job
#: nao rodou, e a partida nunca tera replay.
SQL_RESOLUCOES_SEM_FIM = """
SELECT r.id_resolucao,
       p.id_partida,
       p.co_status,
       p.dh_inicio,
       (now() - p.dh_inicio) AS parada_ha
  FROM desafio_dia.vw003_resolucao r
  JOIN partida.vw001_partida p
    ON p.id_partida = r.id_partida
 WHERE p.co_status = 'em_andamento'
   AND p.dh_inicio < (now() - INTERVAL '7 days')
 ORDER BY p.dh_inicio
 LIMIT 20
"""

#: 2) Quantas resolucoes ha, e quantas ja foram auditadas.
#:
#: ⚠️ Os dois numeros juntos: `divergente = 0` com `pendente` alto significa
#: *"ninguem conferiu"*, e nao *"esta tudo certo"* — a mesma leitura da secao de
#: vigilancia do painel (T040).
SQL_CONTAGENS = """
SELECT COUNT(*)                                              AS qt_resolucoes,
       COUNT(*) FILTER (WHERE co_auditoria = 'pendente')     AS qt_pendentes,
       COUNT(*) FILTER (WHERE co_auditoria = 'divergente')   AS qt_divergentes
  FROM desafio_dia.vw003_resolucao
"""

#: 3) Toda tentativa aponta para uma partida de `co_modo = 'desafio'`?
#:
#: ⛔ Uma tentativa apontando para partida comum poria no quadro uma partida que
#: nunca foi jogada contra aquele desafio — e o replay mostraria outra coisa.
SQL_TENTATIVAS_DE_OUTRO_MODO = """
SELECT t.id_tentativa, p.id_partida, p.co_modo
  FROM desafio_dia.vw002_tentativa t
  JOIN partida.vw001_partida p
    ON p.id_partida = t.id_partida
 WHERE p.co_modo <> 'desafio'
 LIMIT 20
"""

#: 4) Alguma partida de desafio esta pontuando?
#:
#: ⛔ `ic_pontua = FALSE` e o **anti-farm** que ja existia no `pvp_local`: sem
#: ele, jogar o desafio dez vezes pagaria XP de partida dez vezes, por fora do
#: teto de 30/dia da colecao.
SQL_DESAFIO_PONTUANDO = """
SELECT id_partida, co_evento, ic_pontua
  FROM partida.vw001_partida
 WHERE co_modo = 'desafio'
   AND ic_pontua
 LIMIT 20
"""


async def _conferir(url: str) -> int:
    """Roda as quatro conferencias. Devolve o codigo de saida."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    motor = create_async_engine(url, pool_pre_ping=True)
    reprovacoes: list[str] = []

    try:
        async with motor.connect() as conexao:
            # ── 1. Ha o que conferir? ──────────────────────────────────────
            contagens = (
                await conexao.execute(text(SQL_CONTAGENS))
            ).mappings().first()
            qt = int(contagens["qt_resolucoes"])
            print(f"  1. resolucoes no banco ......... {qt}")
            print(
                f"     pendentes de auditoria ...... {contagens['qt_pendentes']}"
            )
            print(
                f"     divergentes ................. {contagens['qt_divergentes']}"
            )

            if qt == 0:
                # ⚠️ **Sem resolucao para conferir e FALHA** — o texto de T048.
                # Um conferidor que aprova o banco vazio ensina a confiar nele
                # justamente quando ele nao esta olhando nada.
                reprovacoes.append(
                    "nao ha resolucao NENHUMA no banco. ⚠️ Isso e esperado antes "
                    "de o job gerar e alguem jogar — mas 'nada a conferir' e "
                    "FALHA, e nao sucesso: um conferidor verde sobre banco vazio "
                    "ensina a confiar nele quando ele nao esta olhando nada."
                )
            elif int(contagens["qt_pendentes"]) == qt:
                # ⚠️ Aviso, e nao reprovacao: a auditoria e tardia de proposito
                # (RF-DES-036), e um lote acabado de chegar esta legitimamente
                # todo pendente.
                print(
                    "     AVISO - nenhuma resolucao foi auditada ainda. "
                    "O avaliador (T043a) rodou?"
                )

            # ── 2. Toda resolucao aponta para partida terminal? ────────────
            sem_fim = (
                await conexao.execute(text(SQL_RESOLUCOES_SEM_FIM))
            ).mappings().all()
            print()
            print(f"  2. resolucoes com partida parada > 7 dias ... {len(sem_fim)}")
            if sem_fim:
                reprovacoes.append(
                    f"{len(sem_fim)} resolucao(oes) apontam para partida em "
                    "`em_andamento` ha mais de 7 dias. ⛔ O job de expiracao "
                    "(T046) nao rodou, e essas partidas nunca terao replay "
                    "(RF-DES-187)."
                )
                for linha in sem_fim[:5]:
                    print(
                        f"     · {linha['id_partida']} parada ha "
                        f"{linha['parada_ha']}"
                    )

            # ── 3. Toda tentativa e de partida de desafio? ─────────────────
            outro_modo = (
                await conexao.execute(text(SQL_TENTATIVAS_DE_OUTRO_MODO))
            ).mappings().all()
            print(f"  3. tentativas apontando para outro modo ..... {len(outro_modo)}")
            if outro_modo:
                reprovacoes.append(
                    f"{len(outro_modo)} tentativa(s) apontam para partida que "
                    "nao e `co_modo = 'desafio'`. ⛔ O quadro mostraria uma "
                    "partida que nunca foi jogada contra aquele desafio."
                )

            # ── 4. Nenhuma partida de desafio pontua ──────────────────────
            pontuando = (
                await conexao.execute(text(SQL_DESAFIO_PONTUANDO))
            ).mappings().all()
            print(f"  4. partidas de desafio com ic_pontua ......... {len(pontuando)}")
            if pontuando:
                reprovacoes.append(
                    f"{len(pontuando)} partida(s) de desafio estao com "
                    "`ic_pontua = TRUE`. ⛔ E o anti-farm: sem ele, jogar o "
                    "desafio dez vezes pagaria XP de partida dez vezes, por fora "
                    "do teto de 30/dia da colecao."
                )

    except Exception as erro:  # noqa: BLE001
        print(f"\n  NAO FOI POSSIVEL CONFERIR: {type(erro).__name__}: {erro}")
        return 1
    finally:
        await motor.dispose()

    print()
    if reprovacoes:
        print("  REPROVOU:")
        for motivo in reprovacoes:
            print(f"    · {motivo}")
        return 2
    print("  OK - toda resolucao aponta para partida em estado terminal")
    return 0


def main() -> int:
    """Le a URL, confere, e devolve o codigo de saida."""
    url = _url_do_banco()
    if not url:
        print("  DATABASE_URL nao esta definida (nem no ambiente, nem no .env)")
        return 1
    print()
    print("  CADEADO 8 - PARTIDA DE DESAFIO FECHADA  (so leitura)")
    print("  " + "-" * 66)
    return asyncio.run(_conferir(url))


if __name__ == "__main__":
    raise SystemExit(main())
