"""DE MEDIDA A PARCELA DE XP — o extrato, aberto (T043).

═══════════════════════════════════════════════════════════════════════════
A FORMULA, E ONDE CADA PEDACO MORA
═══════════════════════════════════════════════════════════════════════════

    XP = 12 + 18 x Q

    Q = p_tentativas x q_tentativas + p_tempo x q_tempo + p_dica x q_dica
        + p_merito x q_merito

  · **12** e o piso por resolver — vira a linha `base` do extrato;
  · ⚠️ **os pesos `p` e as curvas `q` das tres parcelas de sessao vem do BANCO
    desde 10/10/2026** (T103, `DECISOES-do-dono.md` §8zzo): a regua da nota
    vigente no dia do desafio (`regua_da_nota.py`, migracao `0030`). Versao 1:
    30/30/15/25, lineares (a regua de 04/10/2026, §8zs); versao 2: 50/15/20/15,
    hiperbolicas e sem teto. Ate ali eram constantes deste arquivo;
  · **q_merito** e a soma dos feitos que aquele desafio pesa, e os pesos de
    `desafio.tb003_feito_desafio` sao **relativos dentro de `p_merito`**: um
    `0,600` com o merito a 0,25 vira `0,150` na conta final (`data-model.md`,
    "o merito se abre mais uma vez");
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
o total. O arredondamento acontece **uma vez, no fim** ([pontuacao_do_extrato]),
e e esse o numero gravado em `tb003_resolucao.nu_xp`.

⚠️ **Desde 10/10/2026 o XP do desafio e o do SERVIDOR** (§8zzo, decisao 7).
Ate ali valia a pontuacao que o aplicativo mandava (a D-05 estendida ao
numero), e esta conta so auditava. A D-05 continua valendo para **resolvido**:
o veredito e do app; o numero, daqui.

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
from api.desafios.regua_da_nota import ReguaDaNota, nota_da_curva

#: Quanto da nota `Q` vale, em XP. `12 + 18 x Q` chega a 30 com `Q = 1`.
FAIXA_DE_Q = Decimal(XP_TETO_DO_DIA - XP_PISO_POR_RESOLVER)

#: Os codigos de `tb901_tipo_xp_desafio` usados aqui.
TIPO_BASE = XP_BASE
TIPO_TENTATIVAS = XP_TENTATIVAS
TIPO_TEMPO = XP_TEMPO
TIPO_DICA = XP_DICA
TIPO_MERITO = XP_MERITO
TIPO_MEDIDA = XP_MEDIDA

#: ⚠️ **Os pesos (`PESO_TENTATIVAS`, `PESO_TEMPO`, `PESO_DICA`, `PESO_MERITO`),
#: o `TETO_DE_DICAS` e o `TENTATIVAS_QUE_ZERAM_A_PARCELA` sairam daqui em
#: 10/10/2026 (T103)**: moram na regua da nota do banco (`0030`), por versao e
#: com data de vigencia. Os numeros que eles tinham sao a VERSAO 1 de la, e o
#: cadeado `test_regua_da_nota.py` confere que ela e a regua de 04/10/2026.

#: As chaves de sessao no catalogo de feitos. ⚠️ Elas **sao feitos declarados**,
#: como os outros — e e de la que sai a direcao delas.
FEITO_TENTATIVAS = "tentativas"
FEITO_TEMPO = "tempo_ate_resolver"
FEITO_DICAS = "dicas_usadas"


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
    regua: ReguaDaNota,
    nu_tentativas: int,
    nu_tempo_ms: int,
    nu_dicas: int,
    nu_tempo_piso_ms: int,
    nu_tempo_teto_ms: int,
    direcoes: Mapping[str, str],
) -> list[ParcelaDeXp]:
    """As parcelas que **nao** saem do tabuleiro: tentativas, tempo e dica.

    Args:
        regua: a regua da nota vigente no dia do desafio (`regua_da_nota.py`).
            ⚠️ Uma parcela que a regua nao tem nao vira linha.
        nu_tentativas: quantas tentativas ate resolver, a bem-sucedida inclusa.
            ⚠️ **Sem teto** desde a versao 2 (§8zzo): 9 tentativas custam mais
            que 4, e 30 mais que 9.
        nu_tempo_ms: o tempo ate o **objetivo cair** (RF-DES-214), e nao ate o
            fim da partida - quem continua jogando depois de cumprir nao perde
            nota por isso.
        nu_dicas: TODAS as dicas do dia ate a resolucao (§8zzo, decisao 2).
            ⚠️ **Sem teto**: o teto de 2 e do botao, por tentativa; a nota conta
            todas. Ate 10/10/2026 mais de 2 era recusado.
        nu_tempo_piso_ms, nu_tempo_teto_ms: a regua de tempo **daquele
            desafio**. ⚠️ O teto so entra no tempo LINEAR sem escala (versao
            1); na versao 2 o tempo e medido em multiplos do piso e o teto sai
            da nota.
        direcoes: `{co_feito: co_direcao}`, lido da dimensao.

    Raises:
        MedidaInvalida: numeros impossiveis, regua de tempo degenerada, ou uma
            das tres chaves faltando no catalogo (ou com outra direcao).

    ⚠️ **Espelha `lib/core/desafios/qualidade.dart`** (T106), que usa a mesma
    regua para a ESTIMATIVA do app. Os vetores `contratos/vetores-nota-desafio.json`
    rodam dos dois lados.
    """
    if nu_tentativas < 1:
        # `x = 0` daria nota cheia a quem nunca jogou.
        raise MedidaInvalida(
            f"tentativas precisa ser >= 1 numa resolucao; veio {nu_tentativas}"
        )
    if nu_tempo_ms < 0:
        raise MedidaInvalida(f"tempo nao pode ser negativo; veio {nu_tempo_ms}")
    if nu_dicas < 0:
        raise MedidaInvalida(f"dicas nao pode ser negativo; veio {nu_dicas}")
    if nu_tempo_piso_ms <= 0:
        # O piso e a UNIDADE do tempo (`x = t / piso`): zero dividiria por zero.
        raise MedidaInvalida(
            f"a regua de tempo precisa de piso > 0; veio {nu_tempo_piso_ms}"
        )

    piso = Decimal(nu_tempo_piso_ms)
    # (tipo, chave no catalogo, medida crua, e o tempo?)
    sessao = [
        (TIPO_TENTATIVAS, FEITO_TENTATIVAS, Decimal(nu_tentativas), False),
        (TIPO_TEMPO, FEITO_TEMPO, Decimal(nu_tempo_ms), True),
        (TIPO_DICA, FEITO_DICAS, Decimal(nu_dicas), False),
    ]

    parcelas = []
    for tipo, co_feito, medida, e_tempo in sessao:
        parcela = regua.parcela(tipo)
        if parcela is None:
            continue
        _conferir_direcao(co_feito, direcoes)
        # ⚠️ O tempo e medido em MULTIPLOS DO PISO: `x0` e a escala da regua
        # estao nessa unidade, e a medida chega em ms - a unidade e o piso.
        unidade = piso if e_tempo else Decimal(1)
        # A escala vazia (so no tempo linear da versao 1) e "ate o teto do
        # desafio", ja em ms.
        escala_sem_valor = (
            _escala_ate_o_teto(parcela.vr_x0, piso, nu_tempo_teto_ms)
            if e_tempo and parcela.vr_escala is None
            else None
        )
        q = nota_da_curva(
            parcela, medida, unidade=unidade, escala_sem_valor=escala_sem_valor
        )
        parcelas.append(
            ParcelaDeXp(
                nu_tipo_xp=tipo,
                # ⛔ `None` porque estas tres **nao sao linhas de feito** para o
                # `ck003_feito`: so `merito` e `medida` apontam para um feito.
                # Elas tem chave no catalogo (e de la vem a direcao), mas na
                # tabela a coluna fica vazia, como o `data-model.md` mostra.
                nu_feito=None,
                vr_medida=medida,
                vr_normalizado=q,
                vr_peso=parcela.vr_peso,
                vr_xp=FAIXA_DE_Q * parcela.vr_peso * q,
            )
        )
    return parcelas


def _escala_ate_o_teto(
    vr_x0: Optional[Decimal], piso: Decimal, nu_tempo_teto_ms: int
) -> Decimal:
    """A escala do tempo linear sem escala na regua: do `x0` ate o teto, em ms.

    Raises:
        MedidaInvalida: teto que nao fica acima do ponto de partida - a mesma
            condicao do `ck007_regua_tempo` (`0 < piso < teto`). Igual ao piso
            dividiria por zero; invertido, pagaria mais a quem demorou mais.
    """
    inicio = (vr_x0 if vr_x0 is not None else Decimal(1)) * piso
    teto = Decimal(nu_tempo_teto_ms)
    if teto <= inicio:
        raise MedidaInvalida(
            "a regua de tempo precisa de 0 < piso < teto; veio piso "
            f"{piso} e teto {nu_tempo_teto_ms}"
        )
    return teto - inicio


def _conferir_direcao(co_feito: str, direcoes: Mapping[str, str]) -> None:
    """Confere que o catalogo diz o que a curva ja faz: **menor e melhor**.

    Raises:
        MedidaInvalida: a chave nao esta no catalogo, ou a direcao dela nao e
            `menor_melhor`.

    ⚠️ **Ate 10/10/2026 a direcao era APLICADA aqui** (`1 - fracao`). Com as
    curvas da regua do banco ela ja vem dentro da forma: linear e hiperbolica
    so descem. O catalogo continua sendo lido, agora como CONFERENCIA - um
    catalogo dizendo `maior_melhor` para as tentativas e um dado em conflito com
    a regua, e pagar o oposto do que um dos dois diz seria o defeito mais
    silencioso do XP. ⛔ Melhor falhar alto.
    """
    co_direcao = direcoes.get(co_feito)
    if co_direcao is None:
        raise MedidaInvalida(
            f"o feito {co_feito!r} nao esta no catalogo, e sem a direcao dele "
            "nao ha como saber para que lado a parcela corre"
        )
    if co_direcao != "menor_melhor":
        raise MedidaInvalida(
            f"{co_feito}: o catalogo diz {co_direcao!r}, e as curvas da regua da "
            "nota so descem (menor e melhor) - os dois dados estao em conflito"
        )


def montar_extrato(
    *,
    regua: ReguaDaNota,
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
        regua: a regua da nota vigente no dia do desafio - os pesos e as
            curvas (T103).
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
    entre si, e cada um e multiplicado pelo peso do merito DA REGUA aqui - num
    lugar so. E
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
            regua=regua,
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
        # merito a 0,25 e `0,150` em `Q`.
        vr_relativo = Decimal(str(linha["vr_peso"]))
        vr_peso = regua.peso_do_merito * vr_relativo
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

    ⚠️ **Desde 10/10/2026 (T103) e ele que decide o XP do desafio**: a
    pontuacao gravada e `12 + 18 x` este numero ([pontuacao_do_extrato]). A
    `qualidade` que o aplicativo manda passou a ser informativa.

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

    ⚠️ **E o cadeado barato de que o `data-model.md` fala**: os pesos das tres
    de sessao, mais o do merito repartido entre as linhas de feito (versao 2
    da regua: 0,50 + 0,15 + 0,20 + 0,15). Se ela nao fechar em 1, `Q` deixou de poder chegar a 1 - e ninguem
    mais tiraria 30, sem que nada desse erro.
    """
    return sum(
        (p.vr_peso for p in parcelas if p.vr_peso is not None), Decimal(0)
    )


def pontuacao_do_extrato(parcelas: Sequence[ParcelaDeXp]) -> int:
    """A pontuacao de 12 a 30 que o servidor grava: a soma do extrato, inteira.

    ═══════════════════════════════════════════════════════════════════════
    ⚠️ O XP DO DESAFIO E ESTE NUMERO (T103, `DECISOES-do-dono.md` §8zzo)
    ═══════════════════════════════════════════════════════════════════════

    Ate 10/10/2026 valia a pontuacao que o aplicativo mandava, e o servidor so
    a corrigia quando contava mais tentativas ou dicas (a antiga
    `pontuacao_com_a_sessao_do_servidor`, T085zf). Agora o servidor e a fonte
    da verdade **do XP do desafio** (decisao 7): ele recebe as medidas, conta a
    sessao e aplica a regua do dia. A pontuacao do aplicativo vira ESTIMATIVA,
    trocada por esta assim que a resposta chega (T105, T111).

    ⚠️ **A soma e do extrato inteiro**: a linha `base` (12) mais as parcelas.
    Somar aqui, e nao refazer `12 + 18 x Q` a parte, garante que o numero
    gravado e o que o Raio-X mostra parcela a parcela.

    Returns:
        A soma arredondada **para cima no meio** (`ROUND_HALF_UP`), como o
        `round()` do Dart faz com numeros positivos, e presa em 12..30.
    """
    # As linhas `medida` (peso zero) entram com zero: nao mudam a soma.
    bruto = sum((p.vr_xp for p in parcelas), Decimal(0))
    # `quantize(Decimal(1), ROUND_HALF_UP)`: arredonda para o inteiro, com o meio
    # para cima.
    inteiro = int(bruto.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(XP_PISO_POR_RESOLVER, min(XP_TETO_DO_DIA, inteiro))
