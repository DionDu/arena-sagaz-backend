"""DE MEDIDA A PARCELA DE XP — o extrato, aberto (T043).

═══════════════════════════════════════════════════════════════════════════
A FORMULA, E ONDE CADA PEDACO MORA
═══════════════════════════════════════════════════════════════════════════

    XP = 18 + 12 x Q          e     Q = Σ (peso_i x normalizado_i)

  · **18** e o piso por resolver — vira a linha `base` do extrato;
  · **`peso_i`** vem de `desafio.tb003_feito_desafio` (o desafio decide quanto
    cada medida vale nele);
  · **`normalizado_i`** e a medida crua trazida a [0,1], e a **direcao** que a
    inverte vem de `desafio.tb902_catalogo_feito` — ⛔ nunca escrita duas vezes.

⚠️ **Tres das quatro parcelas correm ao contrario**: mais tentativas, mais tempo
e mais dicas dao MENOS XP. A inversao acontece no `vr_normalizado`, e a direcao
de cada feito vem do catalogo. Uma parcela na direcao errada **nao daria erro
nenhum** — so pagaria mais a quem jogou pior.

═══════════════════════════════════════════════════════════════════════════
⚠️ UMA LINHA CARREGA A CONTA INTEIRA
═══════════════════════════════════════════════════════════════════════════

Medida crua, a mesma medida normalizada, o peso e a parcela em XP. Guardar so o
XP faria o Raio-X mostrar *"+1,8"* sem poder dizer de onde saiu — e o Raio-X e
metade do valor desta feature.

═══════════════════════════════════════════════════════════════════════════
⚠️ `Decimal`, E NUNCA `float`, NO QUE VAI PARA O BANCO
═══════════════════════════════════════════════════════════════════════════

As parcelas tem casas decimais, e arredondar cada uma faria a soma nao bater com
o total. O arredondamento acontece **uma vez, no fim** — e mesmo assim o total
gravado em `tb003_resolucao.nu_xp` e o que o **aplicativo** mandou, nao o que
esta conta produz: vale o aplicativo (D-05).

⚠️ Somar `0.6 + 0.4` em ponto flutuante nao da `1.0`, e um teste que exige soma
de pesos igual a 1,000 reprovaria por isso.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence

from api.desafios.modelos_evento import (
    XP_BASE,
    XP_MEDIDA,
    XP_MERITO,
    XP_PISO_POR_RESOLVER,
    XP_TETO_DO_DIA,
)

#: Quanto da nota `Q` vale, em XP. `18 + 12 x Q` chega a 30 com `Q = 1`.
FAIXA_DE_Q = Decimal(XP_TETO_DO_DIA - XP_PISO_POR_RESOLVER)

#: Os codigos de `tb901_tipo_xp_desafio` usados aqui.
TIPO_BASE = XP_BASE
TIPO_MERITO = XP_MERITO
TIPO_MEDIDA = XP_MEDIDA


class MedidaInvalida(ValueError):
    """Uma medida nao pode ser convertida.

    ⚠️ **Chave fora do catalogo cai aqui**, e e dado invalido (RF-DES-033): nao
    e tolerancia a campo novo, e o oposto — uma chave inventada faria `Q` ordenar
    pessoas por medidas de significados diferentes.
    """


@dataclass(frozen=True, slots=True)
class ParcelaDeXp:
    """Uma linha de `desafio_dia.tb004_xp_desafio`, pronta para gravar.

    ⚠️ `nu_feito` e `None` **exatamente** nas linhas que nao sao de feito, e o
    `ck003_feito` da migracao amarra os dois lados: linha de feito tem de dizer
    qual; linha que nao e de feito nao pode inventar um.
    """

    nu_tipo_xp: int
    nu_feito: Optional[int]
    vr_medida: Optional[Decimal]
    vr_normalizado: Optional[Decimal]
    vr_peso: Optional[Decimal]
    vr_xp: Decimal


def _clamp(valor: Decimal) -> Decimal:
    """Prende o numero em [0,1].

    ⚠️ **Fora da faixa nao e erro**: uma partida excepcional pode passar do
    `vr_max` da regua (resolver mais rapido que o gabarito, por exemplo), e o
    certo e pagar a parcela cheia — nao recusar a resolucao de quem jogou melhor
    do que o desafio previa.
    """
    if valor < 0:
        return Decimal(0)
    if valor > 1:
        return Decimal(1)
    return valor


def normalizar(
    valor: Decimal,
    *,
    co_normalizacao: str,
    co_direcao: str,
    vr_min: Optional[Decimal] = None,
    vr_max: Optional[Decimal] = None,
    denominador: Optional[Decimal] = None,
) -> Decimal:
    """A medida crua trazida a [0,1], ja com a direcao aplicada.

    Args:
        valor: a medida como o aplicativo a enviou.
        co_normalizacao: `faixa` · `fracao` · `nenhuma`.
        co_direcao: `maior_melhor` · `menor_melhor` · `marco_atingido`.
        vr_min, vr_max: os limites, quando `faixa`.
        denominador: o valor de `co_sobre`, quando `fracao`.

    Returns:
        O numero entre 0 e 1 que entra em `Q`.

    Raises:
        MedidaInvalida: quando falta o que aquela normalizacao exige.

    ⚠️ **`marco_atingido` ignora a normalizacao**, e e por isso que ele tem um
    ramo proprio: "venceu" nao tem gradacao. Foi a direcao que faltava no
    `data-model.md` ate 09/09/2026, e sem ela um marco seria normalizado por uma
    faixa que ninguem sabia escolher.
    """
    if co_direcao == "marco_atingido":
        return Decimal(1) if valor > 0 else Decimal(0)

    if co_normalizacao == "nenhuma":
        # ⚠️ Medida que nao pontua: aparece no Raio-X, nao entra em `Q`. O
        # `ck003_faixa` da migracao so a permite com peso zero, entao a parcela
        # sai zero de qualquer jeito — devolver zero aqui torna isso explicito.
        return Decimal(0)

    if co_normalizacao == "faixa":
        if vr_min is None or vr_max is None or vr_max <= vr_min:
            raise MedidaInvalida(
                f"normalizacao 'faixa' exige vr_min < vr_max; veio "
                f"{vr_min!r}..{vr_max!r}"
            )
        bruto = (valor - vr_min) / (vr_max - vr_min)
    elif co_normalizacao == "fracao":
        if denominador is None or denominador == 0:
            raise MedidaInvalida(
                "normalizacao 'fracao' exige o denominador (`co_sobre`), e ele "
                f"veio {denominador!r}"
            )
        bruto = valor / denominador
    else:
        raise MedidaInvalida(f"normalizacao desconhecida: {co_normalizacao!r}")

    bruto = _clamp(bruto)
    # ⚠️ **A inversao acontece AQUI, e num lugar so.** Mais tempo, mais
    # tentativas e mais dicas dao menos XP — e a direcao vem do catalogo, nunca
    # de um `if` pela chave do feito.
    return Decimal(1) - bruto if co_direcao == "menor_melhor" else bruto


def montar_extrato(
    *,
    medidas: Mapping[str, Decimal],
    pesos: Sequence[Mapping[str, Any]],
) -> list[ParcelaDeXp]:
    """O extrato inteiro: a linha `base` mais uma linha por feito do desafio.

    Args:
        medidas: `{co_feito: valor}` — o que o aplicativo mandou.
        pesos: as linhas de `desafio.vw003_feito_desafio` daquele desafio, ja com
            o catalogo resolvido (`co_feito`, `co_direcao`, `vr_peso`,
            `co_normalizacao`, `vr_min`, `vr_max`, `co_sobre`).

    Returns:
        As parcelas, na `nu_ordem` do desafio, com a `base` primeiro.

    Raises:
        MedidaInvalida: chave fora do catalogo do desafio, ou normalizacao
            impossivel.

    ⚠️ **Percorre os PESOS, e nao as medidas.** O desafio decide quais feitos
    contam nele; uma medida que o aplicativo mandou e que o desafio nao pesa
    simplesmente nao vira linha. O contrario — percorrer as medidas — deixaria um
    feito **do desafio** de fora quando o aplicativo esquecesse de envia-lo, e a
    pessoa perderia XP sem que nada acusasse.
    """
    parcelas: list[ParcelaDeXp] = [
        ParcelaDeXp(
            nu_tipo_xp=TIPO_BASE,
            nu_feito=None,
            vr_medida=None,
            vr_normalizado=None,
            vr_peso=None,
            vr_xp=Decimal(XP_PISO_POR_RESOLVER),
        )
    ]

    for linha in sorted(pesos, key=lambda p: p["nu_ordem"]):
        co_feito = linha["co_feito"]
        # ⚠️ Medida ausente conta como **zero**, e nao como erro: e o que o
        # aplicativo manda quando o feito nao aconteceu (nenhuma dama coroada),
        # e exigir a chave faria o payload crescer com zeros.
        valor = Decimal(str(medidas.get(co_feito, 0)))

        vr_peso = Decimal(str(linha["vr_peso"]))
        normalizado = normalizar(
            valor,
            co_normalizacao=linha["co_normalizacao"],
            co_direcao=linha["co_direcao"],
            vr_min=_ou_none(linha.get("vr_min")),
            vr_max=_ou_none(linha.get("vr_max")),
            denominador=_denominador(linha.get("co_sobre"), medidas),
        )

        parcelas.append(
            ParcelaDeXp(
                # ⚠️ Peso zero vira `medida` (aparece no Raio-X, nao pontua);
                # peso positivo vira `merito`. Os DOIS sao os tipos que o
                # `ck003_feito` exige que tragam `nu_feito`.
                nu_tipo_xp=TIPO_MERITO if vr_peso > 0 else TIPO_MEDIDA,
                nu_feito=linha["nu_feito"],
                vr_medida=valor,
                vr_normalizado=normalizado,
                vr_peso=vr_peso,
                vr_xp=(FAIXA_DE_Q * vr_peso * normalizado),
            )
        )
    return parcelas


def _ou_none(valor: Any) -> Optional[Decimal]:
    """`Decimal` do valor, ou `None` se ele nao veio."""
    return None if valor is None else Decimal(str(valor))


def _denominador(
    co_sobre: Optional[str], medidas: Mapping[str, Decimal]
) -> Optional[Decimal]:
    """O valor da medida que serve de denominador numa normalizacao `fracao`.

    ⚠️ **O denominador e OUTRA MEDIDA da mesma partida** — "capturas extras sobre
    material do adversario", por exemplo. Por isso ele nao e um numero do desafio:
    ele muda a cada resolucao.
    """
    if co_sobre is None:
        return None
    if co_sobre not in medidas:
        raise MedidaInvalida(
            f"a normalizacao 'fracao' aponta para {co_sobre!r}, e essa medida "
            "nao veio no envio — sem ela a parcela nao tem denominador."
        )
    return Decimal(str(medidas[co_sobre]))


def qualidade_do_extrato(parcelas: Sequence[ParcelaDeXp]) -> Decimal:
    """O `Q` que este extrato produz — a soma de `peso x normalizado`.

    ⚠️ **Serve a AUDITORIA, e nao a decisao** (RF-DES-032, D-05). Se ele
    discordar do `qualidade` que o aplicativo mandou, quem vale e o aplicativo; a
    divergencia vira linha no painel de curadoria.
    """
    return sum(
        (p.vr_peso * p.vr_normalizado
         for p in parcelas
         if p.vr_peso is not None and p.vr_normalizado is not None),
        Decimal(0),
    )
