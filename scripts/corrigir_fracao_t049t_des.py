"""T049t: corrige, NO `des`, os desafios ja gravados com a fracao sem denominador.

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE SCRIPT CONSERTA
═══════════════════════════════════════════════════════════════════════════

De 10 a 23/09/2026 o editorial do job publicou `lances_do_jogador` como
`fracao` **sobre `lances_da_solucao`** - que nao e medida de jogo nenhum. O
aplicativo recusava calcular a nota (`MedidaDeSaidaInvalida`), a tentativa nao
chegava ao estado do dia, e **ninguem conseguia resolver** aqueles desafios
(relato do dono no iPhone, 23/09/2026). O job ja foi corrigido; este script
corrige os desafios que **ja estavam gravados**: cada linha vira a `faixa` que
o job publica agora - de `L` a `3L`, com `L` = os lances de quem resolve na
solucao oficial (`DECISOES-do-dono.md` §8v).

═══════════════════════════════════════════════════════════════════════════
⛔ SO O `des`, E ⛔ NUNCA NUMA MIGRACAO
═══════════════════════════════════════════════════════════════════════════

  * **So o `des`**: a URL e a `DATABASE_URL_DES`, lida pelo mesmo caminho do
    `consultar_des.py`. O `prd` ainda nao tem o schema do desafio.
  * **Nao e migracao** porque nenhum `upgrade` deste projeto reescreve dado
    (`test_migracoes_aditivas`), e o cadeado protege o banco de producao.
  * **Ensaio por padrao**: sem `--aplicar`, o script so MOSTRA o que faria. Com
    `--aplicar`, tudo corre numa transacao, confere o resultado ANTES do
    `COMMIT` e desfaz se a conferencia falhar.
  * ⛔ **Nunca imprime a URL nem a senha.**

COMO SE USA

    .venv\\Scripts\\python scripts\\corrigir_fracao_t049t_des.py            # ensaio
    .venv\\Scripts\\python scripts\\corrigir_fracao_t049t_des.py --aplicar  # grava
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_BACKEND))
sys.path.insert(0, str(RAIZ_BACKEND / "scripts"))

# O console do Windows e cp1252; sem isto, um acento no dado derruba o script.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from consultar_des import url_do_des  # noqa: E402
from job.medidas_de_saida import (  # noqa: E402
    MULTIPLO_DA_ECONOMIA_DE_LANCES,
    lances_do_solucionador,
)

#: As linhas com o defeito: a fracao sobre o tamanho do gabarito.
SQL_DEFEITUOSAS = """
SELECT f.id_feito_desafio, f.id_desafio, d.co_tipo_desafio, f.vr_peso,
       d.js_solucao, d.js_posicao_inicial
  FROM desafio.tb003_feito_desafio f
  JOIN desafio.vw001_desafio d ON d.id_desafio = f.id_desafio
 WHERE f.co_normalizacao = 'fracao'
   AND f.co_sobre = 'lances_da_solucao'
 ORDER BY d.co_tipo_desafio, f.id_desafio
"""

#: Cada linha vira a faixa. ⚠️ Os tres campos juntos, num `UPDATE` so: o
#: `ck003_faixa` exige `vr_min`/`vr_max` preenchidos E `co_sobre` nulo ao mesmo
#: tempo, e trocar um de cada vez violaria a restricao no meio do caminho.
SQL_CORRIGIR = """
UPDATE desafio.tb003_feito_desafio
   SET co_normalizacao = 'faixa',
       vr_min = :vr_min,
       vr_max = :vr_max,
       co_sobre = NULL
 WHERE id_feito_desafio = :id
"""

SQL_SOBRARAM = """
SELECT count(*) FROM desafio.tb003_feito_desafio WHERE co_sobre = 'lances_da_solucao'
"""


def _json(valor: object) -> dict:
    """O `asyncpg` pode devolver JSONB ja decodificado ou como texto."""
    return json.loads(valor) if isinstance(valor, str) else valor  # type: ignore[return-value]


async def executar(aplicar: bool) -> int:
    motor = create_async_engine(url_do_des())
    try:
        async with motor.connect() as conexao:
            transacao = await conexao.begin()
            linhas = (await conexao.execute(text(SQL_DEFEITUOSAS))).all()
            print(f"Linhas com a fracao sobre lances_da_solucao: {len(linhas)}")

            for linha in linhas:
                solucao = _json(linha.js_solucao)
                posicao = _json(linha.js_posicao_inicial)
                lances = lances_do_solucionador(solucao, vez_de=posicao["vez_de"])
                if lances <= 0:
                    await transacao.rollback()
                    print(f"⛔ {linha.id_desafio}: solucao sem lance de quem resolve.")
                    return 1
                vr_max = lances * MULTIPLO_DA_ECONOMIA_DE_LANCES
                print(
                    f"  {linha.co_tipo_desafio:<30} {linha.id_desafio}  "
                    f"peso {linha.vr_peso}  ->  faixa [{lances}, {vr_max}]"
                )
                await conexao.execute(
                    text(SQL_CORRIGIR),
                    {"id": linha.id_feito_desafio, "vr_min": lances, "vr_max": vr_max},
                )

            sobraram = (await conexao.execute(text(SQL_SOBRARAM))).scalar_one()
            if sobraram != 0:
                await transacao.rollback()
                print(f"⛔ Sobraram {sobraram} linha(s) com a fracao. Nada gravado.")
                return 1

            if not aplicar:
                await transacao.rollback()
                print("Ensaio: nada gravado. Rode com --aplicar para gravar.")
                return 0

            await transacao.commit()
            print(f"✅ Gravado: {len(linhas)} linha(s) viraram faixa.")
            return 0
    finally:
        await motor.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(executar(aplicar="--aplicar" in sys.argv)))
