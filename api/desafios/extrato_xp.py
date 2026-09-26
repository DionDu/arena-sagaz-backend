"""DE MEDIDA A PARCELA DE XP — o extrato, aberto (T043).

═══════════════════════════════════════════════════════════════════════════
A FORMULA, E ONDE CADA PEDACO MORA
═══════════════════════════════════════════════════════════════════════════

    XP = 18 + 12 x Q

    Q = 0,30 x q_tentativas + 0,20 x q_tempo + 0,25 x q_dica + 0,25 x q_merito

  · **18** e o piso por resolver — vira a linha `base` do extrato;
  · as **tres primeiras parcelas** saem da sessao (tentativas, tempo, dicas) e
    tem peso fixo, aprovado pelo dono em 03/09/2026 (RF-DES-042);
  · **q_merito** e a soma dos feitos que aquele desafio pesa, e os pesos de
    `desafio.tb003_feito_desafio` sao **relativos dentro dos 0,25**: um `0,600`
    vira `0,150` na conta final (`data-model.md`, "o merito se abre mais uma
    vez");
  · **`normalizado_i`** e a medida crua trazida a [0,1], e a **direcao** que a
    inverte vem de `desafio.tb902_catalogo_feito` — ⛔ nunca escrita duas vezes.

⚠️ **As tres parcelas de sessao faltavam ate 16/09/2026**, e o merito ia com o
peso relativo cru. Somadas, as duas faziam esta auditoria discordar do aplicativo
em **toda** resolucao — e, como vale o aplicativo (D-05, RF-DES-032), o efeito
nao seria XP errado na tela: seria o **alerta de divergencia do painel aceso
sempre**, que e como um alerta deixa de ser lido. O buraco apareceu ao escrever
a peca do lado do aplicativo (`lib/core/desafios/qualidade.dart`, T055), lendo o
`data-model.md` linha a linha.

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

⚠️ **A unica excecao sao as CONTAGENS** (T085zf): quando o servidor contou mais
tentativas ou mais dicas que o aplicativo, o total desce so pelas duas parcelas
de contagem - ver [pontuacao_com_a_sessao_do_servidor].

⚠️ Somar `0.6 + 0.4` em ponto flutuante nao da `1.0`, e um teste que exige soma
de pesos igual a 1,000 reprovaria por isso.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional, Sequence

from api.desafios.modelos_evento import (
    XP_BASE,
    XP_DICA,
    XP_MEDIDA,
    XP_MERITO,
    XP_PISO_POR_RESOLVER,
    XP_TEMPO,
    XP_TENTATIVAS,
    XP_TETO_DO_DIA,
)

#: Quanto da nota `Q` vale, em XP. `18 + 12 x Q` chega a 30 com `Q = 1`.
FAIXA_DE_Q = Decimal(XP_TETO_DO_DIA - XP_PISO_POR_RESOLVER)

#: Os codigos de `tb901_tipo_xp_desafio` usados aqui.
TIPO_BASE = XP_BASE
TIPO_TENTATIVAS = XP_TENTATIVAS
TIPO_TEMPO = XP_TEMPO
TIPO_DICA = XP_DICA
TIPO_MERITO = XP_MERITO
TIPO_MEDIDA = XP_MEDIDA

#: Os quatro pesos de `Q` (RF-DES-042), aprovados pelo dono em 03/09/2026.
#:
#: ⚠️ **`Decimal`, e a partir de texto**: somar `0.30 + 0.20 + 0.25 + 0.25` em
#: ponto flutuante nao da `1.00`, e a soma e o que mantem `Q` dentro de [0, 1].
#: ⚠️ Continuam **afinaveis em campo** — por isso sao constantes nomeadas, e nao
#: numeros no meio da conta. Quem os mudar aqui muda no aplicativo tambem
#: (`lib/core/desafios/qualidade.dart`): as duas contas precisam concordar.
PESO_TENTATIVAS = Decimal("0.30")
PESO_TEMPO = Decimal("0.20")
PESO_DICA = Decimal("0.25")
PESO_MERITO = Decimal("0.25")

#: As chaves de sessao no catalogo de feitos. ⚠️ Elas **sao feitos declarados**,
#: como os outros — e e de la que sai a direcao que as inverte.
FEITO_TENTATIVAS = "tentativas"
FEITO_TEMPO = "tempo_ate_resolver"
FEITO_DICAS = "dicas_usadas"

#: O teto de dicas de um desafio (RF-DES-052/057). Na 2a, a parcela zera.
TETO_DE_DICAS = Decimal(2)


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


def parcelas_de_sessao(
    *,
    nu_tentativas: int,
    nu_tempo_ms: int,
    nu_dicas: int,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    direcoes: Mapping[str, str],
) -> list[ParcelaDeXp]:
    """As tres parcelas que **nao** saem do tabuleiro: tentativas, tempo e dica.

    Somadas elas valem 0,75 de `Q`, e sao o que faltava neste modulo ate
    16/09/2026.

    Args:
        nu_tentativas: quantas tentativas ate resolver, a bem-sucedida inclusa.
        nu_tempo_ms: o tempo ate o **objetivo cair** (RF-DES-214), e nao ate o
            fim da partida - quem continua jogando depois de cumprir nao perde
            nota por isso.
        nu_dicas: 0, 1 ou 2.
        nu_tempo_piso_ms, nu_tempo_teto_ms: a regua **daquele desafio**.
        direcoes: `{co_feito: co_direcao}`, lido da dimensao.

    Raises:
        MedidaInvalida: numeros impossiveis, regua degenerada, ou uma das tres
            chaves faltando no catalogo.

    ⚠️ **Cada regua devolve "que fracao da regua foi percorrida"** - quanto
    pior -, e quem transforma isso em nota e [_aplicar_direcao], lendo o
    catalogo. ⛔ Escrever `1 - x` direto aqui seria escrever a direcao uma
    segunda vez, e o dia em que as duas discordassem **ninguem perceberia**: uma
    parcela invertida nao da erro, so paga mais a quem jogou pior.

    ⚠️ **Espelha `lib/core/desafios/qualidade.dart`** (T055), e as duas contas
    precisam dar o mesmo numero - e a auditoria de RF-DES-032 que depende disso.
    """
    if nu_tentativas < 1:
        # `1 / 0` daria infinito: nota cheia para quem nunca jogou.
        raise MedidaInvalida(
            f"tentativas precisa ser >= 1 numa resolucao; veio {nu_tentativas}"
        )
    if nu_tempo_ms < 0:
        raise MedidaInvalida(f"tempo nao pode ser negativo; veio {nu_tempo_ms}")
    if nu_dicas < 0 or nu_dicas > TETO_DE_DICAS:
        raise MedidaInvalida(
            f"dicas precisa estar entre 0 e {TETO_DE_DICAS}; veio {nu_dicas}"
        )
    # A mesma condicao do `ck007_regua_tempo`: piso igual ao teto **dividiria
    # por zero**; invertidos, a parcela pagaria mais a quem demorou mais.
    if nu_tempo_piso_ms <= 0 or nu_tempo_teto_ms <= nu_tempo_piso_ms:
        raise MedidaInvalida(
            "a regua de tempo precisa de 0 < piso < teto; veio piso "
            f"{nu_tempo_piso_ms} e teto {nu_tempo_teto_ms}"
        )

    tentativas = Decimal(nu_tentativas)
    tempo = Decimal(nu_tempo_ms)
    piso = Decimal(nu_tempo_piso_ms)
    teto = Decimal(nu_tempo_teto_ms)

    # ⚠️ A regua de tentativas e **hiperbolica de proposito**: tentar e
    # ilimitado e gratis (RF-DES-050), entao uma faixa linear precisaria escolher
    # onde a nota zera, e esse numero seria arbitrario - quem fizesse a 11a
    # tentativa num teto de 10 teria a mesma nota de quem fez a 50a. `(n-1)/n` e
    # a fracao de tentativas desperdicadas, e a nota sai `1/n`: a diferenca entre
    # a 1a e a 2a pesa muito, entre a 19a e a 20a quase nada.
    q_tentativas = _aplicar_direcao(
        (tentativas - 1) / tentativas, FEITO_TENTATIVAS, direcoes
    )
    q_tempo = _aplicar_direcao((tempo - piso) / (teto - piso), FEITO_TEMPO, direcoes)
    q_dica = _aplicar_direcao(
        Decimal(nu_dicas) / TETO_DE_DICAS, FEITO_DICAS, direcoes
    )

    return [
        ParcelaDeXp(
            nu_tipo_xp=TIPO_TENTATIVAS,
            # ⛔ `None` porque estas tres **nao sao linhas de feito** para o
            # `ck003_feito`: so `merito` e `medida` apontam para um feito. Elas
            # tem chave no catalogo (e de la vem a direcao), mas na tabela a
            # coluna fica vazia, como o `data-model.md` mostra.
            nu_feito=None,
            vr_medida=tentativas,
            vr_normalizado=q_tentativas,
            vr_peso=PESO_TENTATIVAS,
            vr_xp=FAIXA_DE_Q * PESO_TENTATIVAS * q_tentativas,
        ),
        ParcelaDeXp(
            nu_tipo_xp=TIPO_TEMPO,
            nu_feito=None,
            vr_medida=tempo,
            vr_normalizado=q_tempo,
            vr_peso=PESO_TEMPO,
            vr_xp=FAIXA_DE_Q * PESO_TEMPO * q_tempo,
        ),
        ParcelaDeXp(
            nu_tipo_xp=TIPO_DICA,
            nu_feito=None,
            vr_medida=Decimal(nu_dicas),
            vr_normalizado=q_dica,
            vr_peso=PESO_DICA,
            vr_xp=FAIXA_DE_Q * PESO_DICA * q_dica,
        ),
    ]


def _aplicar_direcao(
    fracao_percorrida: Decimal, co_feito: str, direcoes: Mapping[str, str]
) -> Decimal:
    """Transforma "quanto pior" na **nota**, lendo a direcao da dimensao.

    Raises:
        MedidaInvalida: a chave nao esta no catalogo, ou a direcao dela nao serve
            para uma regua (um marco nao tem gradacao).
    """
    co_direcao = direcoes.get(co_feito)
    if co_direcao is None:
        raise MedidaInvalida(
            f"o feito {co_feito!r} nao esta no catalogo, e sem a direcao dele "
            "nao ha como saber para que lado a parcela corre"
        )
    if co_direcao == "marco_atingido":
        raise MedidaInvalida(
            f"{co_feito}: marco nao passa por regua - ou se atingiu, ou nao"
        )
    cortada = _clamp(fracao_percorrida)
    return Decimal(1) - cortada if co_direcao == "menor_melhor" else cortada


def montar_extrato(
    *,
    medidas: Mapping[str, Decimal],
    pesos: Sequence[Mapping[str, Any]],
    nu_tentativas: int,
    nu_tempo_ms: int,
    nu_dicas: int,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    direcoes: Mapping[str, str],
) -> list[ParcelaDeXp]:
    """O extrato inteiro: a `base`, as tres de sessao e uma linha por feito.

    Args:
        medidas: `{co_feito: valor}` - o que o aplicativo mandou.
        pesos: as linhas de `desafio.vw003_feito_desafio` daquele desafio, ja com
            o catalogo resolvido (`co_feito`, `co_direcao`, `vr_peso`,
            `co_normalizacao`, `vr_min`, `vr_max`, `co_sobre`).
        nu_tentativas, nu_tempo_ms, nu_dicas: o que a sessao contou.
        nu_tempo_piso_ms, nu_tempo_teto_ms: a regua de tempo do desafio.
        direcoes: `{co_feito: co_direcao}` das tres chaves de sessao.

    Returns:
        As parcelas, com a `base` primeiro, as tres de sessao em seguida e o
        merito na `nu_ordem` do desafio.

    Raises:
        MedidaInvalida: chave fora do catalogo do desafio, normalizacao
            impossivel, ou numero de sessao impossivel.

    ⚠️ **Percorre os PESOS, e nao as medidas.** O desafio decide quais feitos
    contam nele; uma medida que o aplicativo mandou e que o desafio nao pesa
    simplesmente nao vira linha. O contrario - percorrer as medidas - deixaria um
    feito **do desafio** de fora quando o aplicativo esquecesse de envia-lo, e a
    pessoa perderia XP sem que nada acusasse.

    ⚠️ **E os pesos do merito sao RELATIVOS** (RF-DES-173): eles somam 1,000
    entre si, e cada um e multiplicado por [PESO_MERITO] aqui - num lugar so. E
    por isso que a soma de `vr_peso` de uma resolucao inteira fecha em 1,000,
    com as tres de sessao juntas.
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

    parcelas.extend(
        parcelas_de_sessao(
            nu_tentativas=nu_tentativas,
            nu_tempo_ms=nu_tempo_ms,
            nu_dicas=nu_dicas,
            nu_tempo_piso_ms=nu_tempo_piso_ms,
            nu_tempo_teto_ms=nu_tempo_teto_ms,
            direcoes=direcoes,
        )
    )

    for linha in sorted(pesos, key=lambda p: p["nu_ordem"]):
        co_feito = linha["co_feito"]
        # ⚠️ Medida ausente conta como **zero**, e nao como erro: e o que o
        # aplicativo manda quando o feito nao aconteceu (nenhuma dama coroada),
        # e exigir a chave faria o payload crescer com zeros.
        valor = Decimal(str(medidas.get(co_feito, 0)))

        # ⚠️ O peso **relativo** vira peso final aqui: `0,600` dentro do
        # merito e `0,150` em `Q`.
        vr_relativo = Decimal(str(linha["vr_peso"]))
        vr_peso = PESO_MERITO * vr_relativo
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
                nu_tipo_xp=TIPO_MERITO if vr_relativo > 0 else TIPO_MEDIDA,
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

    ⚠️ **Ate 16/09/2026 este numero nao era `Q`**, e sim o merito sozinho: as
    tres parcelas de sessao nao eram geradas e o peso do merito ia cru. Ele
    discordava do aplicativo em toda resolucao, e o alerta de divergencia
    acenderia sempre - ate ninguem mais o ler.
    """
    return sum(
        (p.vr_peso * p.vr_normalizado
         for p in parcelas
         if p.vr_peso is not None and p.vr_normalizado is not None),
        Decimal(0),
    )


def soma_dos_pesos(parcelas: Sequence[ParcelaDeXp]) -> Decimal:
    """A soma de `vr_peso` de uma resolucao. Tem de dar `1,000`.

    ⚠️ **E o cadeado barato de que o `data-model.md` fala**: 0,30 + 0,20 +
    0,25 das tres de sessao, mais os 0,25 do merito repartidos entre as linhas
    de feito. Se ela nao fechar em 1, `Q` deixou de poder chegar a 1 - e ninguem
    mais tiraria 30, sem que nada desse erro.
    """
    return sum(
        (p.vr_peso for p in parcelas if p.vr_peso is not None), Decimal(0)
    )


def pontuacao_com_a_sessao_do_servidor(
    *,
    qualidade: Decimal,
    tentativas_do_app: int,
    dicas_do_app: int,
    tentativas: int,
    dicas: int,
    nu_tempo_ms: int,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    direcoes: Mapping[str, str],
) -> int:
    """A pontuacao de 18 a 30 com as tentativas e as dicas que o SERVIDOR contou.

    ═══════════════════════════════════════════════════════════════════════
    ⚠️ POR QUE EXISTE (T085zf, 26/09/2026, `DECISOES-do-dono.md` §8zf)
    ═══════════════════════════════════════════════════════════════════════

    O aplicativo calcula a nota com as tentativas e as dicas **que ele viu**.
    Quem errou tres vezes com a conta, saiu dela e resolveu como convidado
    manda, no login, uma resolucao "de primeira e sem dica": o convidado
    comeca o dia do zero, porque no aparelho ele e outra pessoa. O servidor
    sabia que era a quarta tentativa, e so gravava a contagem.

    ⚠️ **So as duas parcelas de CONTAGEM mudam.** Tempo e merito continuam os
    do aplicativo (D-05: vale o aplicativo no julgamento); o que o servidor
    corrige e um FATO que ele ve melhor - quantas vezes a pessoa tentou e
    quantas dicas pagou no dia. Por isso a conta parte da `qualidade` que o
    aplicativo mandou e tira dela so a diferenca dessas duas parcelas, em vez
    de recalcular `Q` inteira: recalcular o merito aqui faria qualquer
    divergencia de normalizacao virar XP diferente, que e o que D-05 proibe.

    Args:
        qualidade: o `Q` que o aplicativo mandou, em [0,1].
        tentativas_do_app, dicas_do_app: o que o aplicativo usou na conta.
        tentativas, dicas: o que vale agora - o MAIOR entre o do aplicativo e o
            do servidor; quem escolhe e o servico.
        nu_tempo_ms, nu_tempo_piso_ms, nu_tempo_teto_ms: so para montar as
            parcelas de sessao; a de tempo e igual nos dois lados e se anula.
        direcoes: `{co_feito: co_direcao}` das tres chaves de sessao.

    Returns:
        `round(18 + 12 x Q')`, arredondado **para cima no meio** como o `round()`
        do Dart (`lib/core/desafios/qualidade.dart`), preso em 18..30.

    Raises:
        MedidaInvalida: os mesmos numeros impossiveis de [parcelas_de_sessao].
    """

    def _contagem(n: int, d: int) -> Decimal:
        """O XP das duas parcelas de contagem (tentativas + dica) com n e d."""
        parcelas = parcelas_de_sessao(
            nu_tentativas=n,
            nu_tempo_ms=nu_tempo_ms,
            nu_dicas=d,
            nu_tempo_piso_ms=nu_tempo_piso_ms,
            nu_tempo_teto_ms=nu_tempo_teto_ms,
            direcoes=direcoes,
        )
        return sum(
            (p.vr_xp for p in parcelas if p.nu_tipo_xp in (TIPO_TENTATIVAS, TIPO_DICA)),
            Decimal(0),
        )

    # O que a pessoa perde por ter tentado e pedido mais do que o app sabia.
    # ⚠️ Nunca negativo: o servico so pede esta conta com contagens MAIORES, e
    # as duas reguas so descem quando a contagem sobe.
    perda = _contagem(tentativas_do_app, dicas_do_app) - _contagem(tentativas, dicas)
    bruto = Decimal(XP_PISO_POR_RESOLVER) + FAIXA_DE_Q * qualidade - perda
    # `quantize(Decimal(1), ROUND_HALF_UP)`: arredonda para o inteiro, com o meio
    # para cima - o `round()` do Dart faz o mesmo com numeros positivos.
    inteiro = int(bruto.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(XP_PISO_POR_RESOLVER, min(XP_TETO_DO_DIA, inteiro))
