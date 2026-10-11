"""As duas versoes da regua da nota, escritas a mao, para os testes (T103/T104).

⚠️ **Nao tem prefixo `test_` de proposito**: e modulo de apoio, como
`fakes_desafio.py`. O envio (`test_envio_de_resolucao.py`) e a publicacao
(`test_rotas_desafio_publicado.py`) usam as mesmas linhas, e uma copia em cada
arquivo envelheceria calada no dia em que uma delas mudasse.

⚠️ **Os numeros sao os da migracao `0030`, ESCRITOS A MAO** - e nao lidos dela:
um caso que lesse a migracao para conferir o codigo que a le passaria com
qualquer numero (memoria "teste nao se mede pela propria regua"). Quem confere
que a migracao tem estes numeros e `test_regua_da_nota.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from api.desafios.modelos_evento import XP_DICA, XP_MERITO, XP_TEMPO, XP_TENTATIVAS
from api.desafios.regua_da_nota import reguas_das_linhas

#: O dia em que a regua 2 passa a valer NESTES casos. ⚠️ Nao e a data do `des`
#: nem a do `prd` (cada ambiente tem a sua, o dia seguinte ao da `0030`): o que
#: se prova aqui e a regra da vigencia, e nao uma data.
VIGENCIA_V1 = date(2026, 9, 1)
VIGENCIA_V2 = date(2026, 10, 11)


def _linha(
    versao: int,
    vigencia: date,
    tipo: int,
    co_tipo: str,
    peso: str,
    forma: str,
    x0: Optional[str],
    escala: Optional[str],
) -> dict[str, Any]:
    """Uma linha de `vw905_parcela_regua_nota`, como o banco a devolve."""
    return {
        "nu_versao_regua": versao,
        "dt_inicio_vigencia": vigencia,
        "nu_tipo_xp": tipo,
        "co_tipo_xp": co_tipo,
        "vr_peso": Decimal(peso),
        "co_forma": forma,
        "vr_x0": None if x0 is None else Decimal(x0),
        "vr_escala": None if escala is None else Decimal(escala),
    }


#: Versao 1 - a regua de 04/10/2026 (§8zs): 30/30/15/25, lineares.
#: Versao 2 - a da §8zzo: 50/15/20/15, hiperbolicas.
LINHAS_DAS_REGUAS = [
    _linha(1, VIGENCIA_V1, XP_TENTATIVAS, "tentativas", "0.300", "linear", "1", "3"),
    _linha(1, VIGENCIA_V1, XP_TEMPO, "tempo", "0.300", "linear", "1", None),
    _linha(1, VIGENCIA_V1, XP_DICA, "dica", "0.150", "linear", "0", "2"),
    _linha(1, VIGENCIA_V1, XP_MERITO, "merito", "0.250", "merito", None, None),
    _linha(2, VIGENCIA_V2, XP_TENTATIVAS, "tentativas", "0.500", "hiperbolica", "1", "1"),
    _linha(2, VIGENCIA_V2, XP_TEMPO, "tempo", "0.150", "hiperbolica", "1", "2"),
    _linha(2, VIGENCIA_V2, XP_DICA, "dica", "0.200", "hiperbolica", "0", "2"),
    _linha(2, VIGENCIA_V2, XP_MERITO, "merito", "0.150", "merito", None, None),
]

REGUA_V1, REGUA_V2 = reguas_das_linhas(LINHAS_DAS_REGUAS)
