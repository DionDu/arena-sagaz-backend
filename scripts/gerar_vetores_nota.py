"""T106 - EMITE OS VETORES DA NOTA DO DESAFIO (a regua, Dart x Python).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE ARQUIVO EXISTE
═══════════════════════════════════════════════════════════════════════════

A conta da nota existe **duas vezes**: em Python, no servidor, que grava o XP
do desafio (`api/desafios/extrato_xp.py`, T103), e em Dart, no aplicativo, que
mostra a ESTIMATIVA na hora (`lib/core/desafios/qualidade.dart`, T106). Desde
10/10/2026 o numero que vale e o do servidor (`DECISOES-do-dono.md` §8zzo,
decisao 7), e a resposta do envio o devolve - mas a tela mostra a estimativa
primeiro, e uma estimativa que errasse sempre faria o numero "mudar sozinho"
na frente da pessoa.

Os vetores sao a mesma disciplina de `gerar_vetores_verificacao.py`: um caso
compartilhado, rodado dos dois lados sobre os mesmos dados, com as duas copias
comparadas por SHA-256.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE OS VETORES PROVAM, E O QUE NAO PROVAM
═══════════════════════════════════════════════════════════════════════════

Os `esperado` saem da conta do **servidor** (`montar_extrato` +
`pontuacao_do_extrato`), que e a fonte da verdade do numero. O que se escreve a
mao e a sessao, as medidas e a regua - e a regua vai **dentro** de cada
documento, com os numeros da migracao `0030`, para o vetor continuar valendo no
dia em que o banco ganhar uma versao 3.

  ✅ **provam** que o Dart e o Python concordam nos casos escritos, e que a
     conta do servidor nao muda sem alguem perceber (o teste do servidor
     regenera o documento em memoria e compara);
  ⛔ **nao provam** que a regua e boa - isso e decisao do dono (§8zzo), e os
     perfis da tabela dele estao escritos a mao em `test_envio_de_resolucao.py`.

⚠️ **Nenhum vetor cai num empate de arredondamento** (`x,5`): o Dart soma em
`double` e o Python em `Decimal`, e um `16,4999999` contra um `16,5` daria 16
de um lado e 17 do outro sem que nenhum dos dois estivesse errado. O gerador
recusa o caso que ficar a menos de 0,000001 do meio.

═══════════════════════════════════════════════════════════════════════════
COMO SE RODA
═══════════════════════════════════════════════════════════════════════════

    cd D:\\Desenvolvimento\\arena-sagaz\\arena-sagaz-backend
    .venv\\Scripts\\python scripts\\gerar_vetores_nota.py

Ele escreve as **duas** copias, byte-identicas:

    arena-sagaz-backend/contratos/vetores-nota-desafio.json
    arena-sagaz-frontend/specs/009-desafio-do-dia/contracts/vetores-nota-desafio.json

⚠️ **Vetor nunca e apagado nem editado**: corrigir um vetor errado e vetor
NOVO, como nos vetores de verificacao.
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

# `parents[1]` sobe de scripts/ ate a raiz do backend.
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from api.desafios.extrato_xp import (  # noqa: E402
    montar_extrato,
    pontuacao_do_extrato,
    qualidade_do_extrato,
)
from api.desafios.modelos_evento import (  # noqa: E402
    XP_DICA,
    XP_MEDIDA,
    XP_MERITO,
    XP_TEMPO,
    XP_TENTATIVAS,
)
from api.desafios.regua_da_nota import (  # noqa: E402
    ReguaDaNota,
    regua_para_publicar,
    reguas_das_linhas,
)

#: As duas copias. ⚠️ A do app mora na spec, ao lado dos vetores de verificacao.
SAIDA_BACKEND = RAIZ / "contratos" / "vetores-nota-desafio.json"
SAIDA_APP = (
    RAIZ.parent
    / "arena-sagaz-frontend"
    / "specs"
    / "009-desafio-do-dia"
    / "contracts"
    / "vetores-nota-desafio.json"
)

#: O catalogo de feitos (o manifesto que o app gera) - de onde vem a direcao de
#: cada medida do merito.
CATALOGO = RAIZ / "contratos" / "catalogo_feitos.json"

#: A versao do documento.
VERSAO_DO_DOCUMENTO = 1

#: Quantas casas decimais os `normalizados` levam no JSON. O Dart compara com
#: folga de 1e-9, e dez casas cobrem com sobra.
CASAS = 10

#: O nome de cada parcela na regua publicada -> o `nu_tipo_xp` da `tb901`.
TIPO_DA_PARCELA = {
    "tentativas": XP_TENTATIVAS,
    "tempo": XP_TEMPO,
    "dica": XP_DICA,
    "merito": XP_MERITO,
}

#: A chave de catalogo de cada parcela de sessao no extrato.
CHAVE_DE_SESSAO = {
    XP_TENTATIVAS: "tentativas",
    XP_TEMPO: "tempo_ate_resolver",
    XP_DICA: "dicas_usadas",
}

#: As direcoes das tres chaves de sessao (as do catalogo).
DIRECOES_DE_SESSAO = {
    "tentativas": "menor_melhor",
    "tempo_ate_resolver": "menor_melhor",
    "dicas_usadas": "menor_melhor",
}


def _linha(versao, tipo, co_tipo, peso, forma, x0, escala):
    """Uma linha da `vw905`, como a migracao `0030` a insere."""
    return {
        "nu_versao_regua": versao,
        # A data nao entra no vetor: a regua vai inteira dentro dele.
        "dt_inicio_vigencia": None,
        "nu_tipo_xp": tipo,
        "co_tipo_xp": co_tipo,
        "vr_peso": Decimal(peso),
        "co_forma": forma,
        "vr_x0": None if x0 is None else Decimal(x0),
        "vr_escala": None if escala is None else Decimal(escala),
    }


#: As versoes 1 e 2 da `0030`, escritas a mao.
REGUA_V1, REGUA_V2 = reguas_das_linhas(
    [
        _linha(1, XP_TENTATIVAS, "tentativas", "0.300", "linear", "1", "3"),
        _linha(1, XP_TEMPO, "tempo", "0.300", "linear", "1", None),
        _linha(1, XP_DICA, "dica", "0.150", "linear", "0", "2"),
        _linha(1, XP_MERITO, "merito", "0.250", "merito", None, None),
        _linha(2, XP_TENTATIVAS, "tentativas", "0.500", "hiperbolica", "1", "1"),
        _linha(2, XP_TEMPO, "tempo", "0.150", "hiperbolica", "1", "2"),
        _linha(2, XP_DICA, "dica", "0.200", "hiperbolica", "0", "2"),
        _linha(2, XP_MERITO, "merito", "0.150", "merito", None, None),
    ]
)
REGUAS = {1: REGUA_V1, 2: REGUA_V2}


# ── As medidas de saida dos casos, na forma PUBLICADA ─────────────────────────

#: Um desafio de Pontinhos: fechar 4 caixas, sem entregar.
PONTINHOS = [
    {"chave": "caixas_fechadas", "peso": 0.6, "normalizacao": "faixa",
     "minimo": 0, "maximo": 4, "sobre": None},
    {"chave": "caixas_do_adversario", "peso": 0.4, "normalizacao": "faixa",
     "minimo": 0, "maximo": 4, "sobre": None},
]

#: Um desafio de damas com as tres normalizacoes e um marco.
DAMAS = [
    {"chave": "damas_coroadas", "peso": 0.5, "normalizacao": "faixa",
     "minimo": 0, "maximo": 2, "sobre": None},
    {"chave": "capturas_extras", "peso": 0.3, "normalizacao": "fracao",
     "minimo": None, "maximo": None, "sobre": "material_do_adversario"},
    {"chave": "vitoria", "peso": 0.2, "normalizacao": "faixa",
     "minimo": 0, "maximo": 1, "sobre": None},
    {"chave": "material_restante", "peso": 0.0, "normalizacao": "nenhuma",
     "minimo": None, "maximo": None, "sobre": None},
]

#: O desafio de 10/10/2026 do relato (damas): o piso e o merito refeitos da
#: tabela da §8zzo.
DAMAS_10_10 = [
    {"chave": "damas_coroadas", "peso": 0.6, "normalizacao": "faixa",
     "minimo": 0, "maximo": 2, "sobre": None},
    {"chave": "material_do_adversario", "peso": 0.4, "normalizacao": "faixa",
     "minimo": 0, "maximo": 12, "sobre": None},
]


#: As medidas do caso de ouro do `data-model.md` (a terceira e so exibida).
CASO_DE_OURO = [
    {"chave": "caixas_fechadas", "peso": 0.6, "normalizacao": "faixa",
     "minimo": 0, "maximo": 4, "sobre": None},
    {"chave": "lances_otimos", "peso": 0.4, "normalizacao": "faixa",
     "minimo": 0, "maximo": 6, "sobre": None},
    {"chave": "maior_cadeia_capturada", "peso": 0.0, "normalizacao": "nenhuma",
     "minimo": None, "maximo": None, "sobre": None},
]


def _caso(id_, regua, *, tentativas, tempo_ms, dicas, piso, teto, saidas, medidas):
    """Um vetor sem o `esperado` - quem o preenche e [_calcular]."""
    return {
        "id": id_,
        "regua": regua,
        "tentativas": tentativas,
        "tempo_ms": tempo_ms,
        "dicas": dicas,
        "tempo_piso_ms": piso,
        "tempo_teto_ms": teto,
        "medidas_de_saida": saidas,
        "medidas": medidas,
    }


CHEIO_PONTINHOS = {"caixas_fechadas": 4, "caixas_do_adversario": 0}

CASOS = [
    # ── Regua 2: os perfis da §8zzo ─────────────────────────────────────────
    _caso("v2-1a-sem-dica-no-piso", 2, tentativas=1, tempo_ms=20_000, dicas=0,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-1a-sem-dica-3x-o-piso", 2, tentativas=1, tempo_ms=60_000, dicas=0,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-1a-1-dica-2x-o-piso", 2, tentativas=1, tempo_ms=40_000, dicas=1,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-2a-sem-dica-2x-o-piso", 2, tentativas=2, tempo_ms=40_000, dicas=0,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-9-tentativas-no-piso", 2, tentativas=9, tempo_ms=20_000, dicas=0,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-4-tentativas-2-dicas-3x", 2, tentativas=4, tempo_ms=60_000, dicas=2,
          piso=20_000, teto=120_000, saidas=PONTINHOS, medidas=CHEIO_PONTINHOS),
    _caso("v2-30-tentativas-10-dicas-20x", 2, tentativas=30, tempo_ms=400_000,
          dicas=10, piso=20_000, teto=120_000, saidas=PONTINHOS,
          medidas=CHEIO_PONTINHOS),
    # O empate que motivou a regua nova: com a regua 1, 25 x 25.
    _caso("v2-fernando-9-tentativas-38s", 2, tentativas=9, tempo_ms=38_000,
          dicas=0, piso=45_918, teto=275_508, saidas=DAMAS_10_10,
          medidas={"damas_coroadas": 2, "material_do_adversario": 0}),
    _caso("v2-maria-2-tentativas-2-dicas-54s", 2, tentativas=2, tempo_ms=54_000,
          dicas=2, piso=45_918, teto=275_508, saidas=DAMAS_10_10,
          medidas={"damas_coroadas": 2, "material_do_adversario": 0.4}),
    # Abaixo do piso, nota cheia; e o teto nao entra na regua 2.
    _caso("v2-abaixo-do-piso-e-teto-curto", 2, tentativas=3, tempo_ms=5_000,
          dicas=3, piso=10_000, teto=12_000, saidas=PONTINHOS,
          medidas={"caixas_fechadas": 3, "caixas_do_adversario": 1}),
    # As tres normalizacoes do merito, o marco e a medida so exibida.
    _caso("v2-merito-damas-fracao-e-marco", 2, tentativas=2, tempo_ms=33_000,
          dicas=1, piso=15_000, teto=90_000, saidas=DAMAS,
          medidas={"damas_coroadas": 1, "capturas_extras": 2,
                   "material_do_adversario": 5, "vitoria": 1,
                   "material_restante": 7}),
    _caso("v2-merito-zero-perdeu-tudo", 2, tentativas=5, tempo_ms=150_000,
          dicas=4, piso=15_000, teto=90_000, saidas=DAMAS,
          medidas={"damas_coroadas": 0, "capturas_extras": 0,
                   "material_do_adversario": 8, "vitoria": 0}),
    # ── Regua 1: o que os dias antigos pagam ────────────────────────────────
    # A tabela "Um dia inteiro, linha a linha" do `data-model.md`: 25,464 -> 25.
    _caso("v1-caso-de-ouro-do-data-model", 1, tentativas=2, tempo_ms=27_000,
          dicas=0, piso=10_000, teto=60_000, saidas=CASO_DE_OURO,
          medidas={"caixas_fechadas": 4, "lances_otimos": 3,
                   "maior_cadeia_capturada": 2}),
    _caso("v1-3-tentativas-1-dica-meio-da-regua", 1, tentativas=3,
          tempo_ms=48_210, dicas=1, piso=12_000, teto=95_000, saidas=DAMAS,
          medidas={"damas_coroadas": 1, "capturas_extras": 1,
                   "material_do_adversario": 4, "vitoria": 1}),
    _caso("v1-zera-na-4a-e-depois-do-teto", 1, tentativas=7, tempo_ms=200_000,
          dicas=3, piso=12_000, teto=95_000, saidas=PONTINHOS,
          medidas={"caixas_fechadas": 1, "caixas_do_adversario": 3}),
    _caso("v1-fernando-25", 1, tentativas=9, tempo_ms=38_000, dicas=0,
          piso=45_918, teto=275_508, saidas=DAMAS_10_10,
          medidas={"damas_coroadas": 2, "material_do_adversario": 0}),
]


def _direcoes_do_catalogo() -> dict[str, str]:
    """`{co_feito: co_direcao}` do manifesto do catalogo de feitos."""
    documento = json.loads(CATALOGO.read_text(encoding="utf-8"))
    return {f["co_feito"]: f["co_direcao"] for f in documento["feitos"]}


def regua_do_vetor(publicada: dict[str, Any]) -> ReguaDaNota:
    """A regua de um vetor (na forma publicada) de volta ao objeto do servidor.

    ⚠️ Usada tambem pelo teste do servidor (`test_vetores_nota.py`).
    """
    [regua] = reguas_das_linhas(
        {
            "nu_versao_regua": publicada["versao"],
            "dt_inicio_vigencia": None,
            "nu_tipo_xp": TIPO_DA_PARCELA[p["parcela"]],
            "co_tipo_xp": p["parcela"],
            # `str` antes do `Decimal`: o float `0.15` viraria a dizima binaria.
            "vr_peso": Decimal(str(p["peso"])),
            "co_forma": p["forma"],
            "vr_x0": None if p["x0"] is None else Decimal(str(p["x0"])),
            "vr_escala": None if p["escala"] is None else Decimal(str(p["escala"])),
        }
        for p in publicada["parcelas"]
    )
    return regua


def calcular(vetor: dict[str, Any], direcoes: dict[str, str]) -> dict[str, Any]:
    """O `esperado` de um vetor, pela conta do SERVIDOR.

    ⚠️ Usada tambem pelo teste do servidor, que regenera o documento e o compara
    com o arquivo: e assim que a conta do servidor nao muda calada.

    Returns:
        `{normalizados: {chave: nota}, q, pontuacao}`.
    """
    pesos = [
        {
            # O identificador numerico nao importa a conta; o indice serve.
            "nu_feito": indice + 1,
            "co_feito": s["chave"],
            "co_direcao": direcoes[s["chave"]],
            "nu_ordem": indice + 1,
            "vr_peso": Decimal(str(s["peso"])),
            "co_normalizacao": s["normalizacao"],
            "vr_min": s["minimo"],
            "vr_max": s["maximo"],
            "co_sobre": s["sobre"],
        }
        for indice, s in enumerate(vetor["medidas_de_saida"])
    ]
    parcelas = montar_extrato(
        regua=regua_do_vetor(vetor["regua_nota"]),
        medidas={k: Decimal(str(v)) for k, v in vetor["medidas"].items()},
        pesos=pesos,
        nu_tentativas=vetor["tentativas"],
        nu_tempo_ms=vetor["tempo_ms"],
        nu_dicas=vetor["dicas"],
        nu_tempo_piso_ms=vetor["tempo_piso_ms"],
        nu_tempo_teto_ms=vetor["tempo_teto_ms"],
        direcoes=DIRECOES_DE_SESSAO,
    )

    normalizados: dict[str, float] = {}
    chaves_do_merito = iter(s["chave"] for s in vetor["medidas_de_saida"])
    for p in parcelas:
        if p.vr_normalizado is None:
            continue  # a linha `base`
        if p.nu_tipo_xp in CHAVE_DE_SESSAO:
            chave = CHAVE_DE_SESSAO[p.nu_tipo_xp]
        else:
            # Merito e medida saem na ordem das medidas de saida.
            assert p.nu_tipo_xp in (XP_MERITO, XP_MEDIDA)
            chave = next(chaves_do_merito)
        normalizados[chave] = round(float(p.vr_normalizado), CASAS)

    bruto = sum((p.vr_xp for p in parcelas), Decimal(0))
    distancia_do_meio = abs((bruto % 1) - Decimal("0.5"))
    if distancia_do_meio < Decimal("0.000001"):
        raise ValueError(
            f"{vetor['id']}: o total {bruto} cai no meio do arredondamento - "
            "o Dart (double) e o Python (Decimal) podem discordar sem erro de "
            "nenhum dos dois. Escolha outro caso."
        )
    return {
        "normalizados": normalizados,
        "q": round(float(qualidade_do_extrato(parcelas)), CASAS),
        "pontuacao": pontuacao_do_extrato(parcelas),
    }


def montar_documento() -> dict[str, Any]:
    """O documento inteiro, com os `esperado` calculados agora."""
    direcoes = _direcoes_do_catalogo()
    vetores = []
    for caso in CASOS:
        vetor = {k: v for k, v in caso.items() if k != "regua"}
        # ⚠️ A regua vai DENTRO do vetor, inteira: ele continua valendo no dia
        # em que o banco ganhar outra versao.
        vetor["regua_nota"] = regua_para_publicar(REGUAS[caso["regua"]])
        vetor["esperado"] = calcular(vetor, direcoes)
        vetores.append(vetor)
    return {
        "de_documento": (
            "Vetores da nota do Desafio do Dia (T106, DECISOES-do-dono 8zzo). "
            "GERADO por scripts/gerar_vetores_nota.py - nao edite a mao. Os "
            "esperados saem da conta do SERVIDOR (extrato_xp.py), e o app "
            "(qualidade.dart) tem de chegar ao mesmo numero. Vetor nunca e "
            "apagado nem editado: corrigir e vetor NOVO."
        ),
        "versao": VERSAO_DO_DOCUMENTO,
        "vetores": vetores,
    }


def texto_do_documento() -> str:
    """O JSON exatamente como vai para o disco (as duas copias)."""
    return json.dumps(montar_documento(), ensure_ascii=False, indent=2) + "\n"


def main() -> None:
    texto = texto_do_documento()
    for destino in (SAIDA_BACKEND, SAIDA_APP):
        destino.parent.mkdir(parents=True, exist_ok=True)
        # `newline="\n"`: no Windows o Python escreveria CRLF, e as duas copias
        # precisam ser byte-identicas em qualquer maquina.
        with destino.open("w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write(texto)
        print(f"escrito: {destino}")
    documento = json.loads(texto)
    for vetor in documento["vetores"]:
        print(f"  {vetor['id']}: {vetor['esperado']['pontuacao']}")


if __name__ == "__main__":
    main()
