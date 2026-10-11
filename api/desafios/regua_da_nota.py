"""A REGUA DA NOTA, LIDA DO BANCO - pesos, curvas e vigencia (T103, §8zzo).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO E UM MODULO PROPRIO
═══════════════════════════════════════════════════════════════════════════

Ate 10/10/2026 os pesos da nota e o formato de cada parcela eram constantes de
`extrato_xp.py` (e de `lib/core/desafios/qualidade.dart`, no app). Desde a
migracao `0030` eles moram no banco, numa regua **versionada por vigencia**
(`desafio_dia.tb904_regua_nota` + `tb905_parcela_regua_nota`), e este modulo e
quem a entende: escolhe a versao de um dia e aplica a curva de cada parcela.

Dois leitores usam a mesma regra, e por isso ela mora aqui e nao em cada um:

  · o envio da resolucao (`servico_envio.py`), que calcula o XP do desafio -
    o servidor e a fonte da verdade desse numero (§8zzo, decisao 7);
  · a publicacao do desafio (`repositorio.py` + `publicacao.py`), que manda a
    mesma regua ao app para ele mostrar a ESTIMATIVA (decisao 8).

═══════════════════════════════════════════════════════════════════════════
AS DUAS CURVAS
═══════════════════════════════════════════════════════════════════════════

    excesso = (x - x0) / escala         (x = a medida da pessoa)

    linear:       q = 1 - excesso       (presa em [0, 1]; zera no fim da escala)
    hiperbolica:  q = 1 / (1 + excesso) (cai forte no comeco, nunca chega a 0)

Abaixo de `x0`, nota cheia nas duas: a 1a tentativa, nenhuma dica, o tempo
dentro do piso. A `escala` e "quanto piorar para zerar" na linear e "quanto
piorar para perder metade" na hiperbolica.

⚠️ **As tres parcelas de sessao so pioram com a medida** (mais tentativas, mais
tempo, mais dicas): as duas curvas sao decrescentes por construcao, e por isso
a direcao delas **nao** e aplicada aqui. Quem confere que o catalogo concorda
(`co_direcao = 'menor_melhor'`) e `extrato_xp.py`.

⚠️ **O tempo e medido em multiplos do PISO do desafio** (`x = t / piso`): um
final de 3 lances e uma abertura de 12 nao pedem a mesma pressa. A conta e feita
em milissegundos (`x0 * piso`, `escala * piso`), com UMA divisao so, para a
versao 1 dar exatamente o numero antigo `(t - piso) / (teto - piso)`.

═══════════════════════════════════════════════════════════════════════════
⛔ SEM VALOR PADRAO
═══════════════════════════════════════════════════════════════════════════

Regua que falta, versao sem a soma 1,000, forma desconhecida: tudo isso e
[ReguaDaNotaInvalida], um erro do SERVIDOR (500), e nunca "usa a de antes".
RF-DES-223: um numero arbitrado pagaria XP errado em silencio. E ⚠️ **nao e
400**: o app trata 400 como "desista do envio", e a pessoa perderia a
resolucao por um defeito que nao e dela; com 500 a fila tenta de novo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping, Optional

from api.desafios.modelos_evento import (
    VW_PARCELA_REGUA_NOTA,
    XP_DICA,
    XP_MERITO,
    XP_TEMPO,
    XP_TENTATIVAS,
)

#: As quatro formas que a `tb905` aceita (`ck002_forma` da `0030`).
FORMA_LINEAR = "linear"
FORMA_HIPERBOLICA = "hiperbolica"
FORMA_MERITO = "merito"

#: As parcelas de SESSAO, na ordem em que se explicam no extrato e no Raio-X.
#: O merito vem depois, uma linha por feito.
TIPOS_DE_SESSAO = (XP_TENTATIVAS, XP_TEMPO, XP_DICA)


#: TODAS as versoes da regua da nota, parcela a parcela (T103).
#:
#: ⚠️ Mora aqui, e nao num repositorio, porque DOIS a usam: o do envio (o XP)
#: e o da publicacao (a regua que o app leva para estimar, T104).
#:
#: ⚠️ **Todas, e nao so a vigente**: a regra da vigencia ("a de maior
#: `dt_inicio_vigencia` que ainda seja <= `dt_dia`") mora num lugar so,
#: `regua_da_nota.regua_vigente`, e e a mesma que a publicacao usa. Escreve-la
#: tambem num `WHERE` daqui seria escreve-la duas vezes. A tabela e minuscula
#: (4 linhas por versao).
SQL_REGUAS_DA_NOTA = f"""
SELECT nu_versao_regua, dt_inicio_vigencia, nu_tipo_xp, co_tipo_xp,
       vr_peso, co_forma, vr_x0, vr_escala
  FROM {VW_PARCELA_REGUA_NOTA}
 ORDER BY nu_versao_regua, nu_tipo_xp
"""


class ReguaDaNotaInvalida(RuntimeError):
    """A regua lida do banco nao forma uma nota - defeito do servidor (500).

    ⚠️ `RuntimeError`, e nao `ErroNegocio`: ver o cabecalho ("nao e 400").
    """


@dataclass(frozen=True, slots=True)
class ParcelaDaRegua:
    """Uma linha de `tb905_parcela_regua_nota`.

    - [nu_tipo_xp]: a parcela, no codigo da `tb901` (2 tentativas, 3 tempo,
      4 dica, 5 merito) - o mesmo que o extrato grava.
    - [co_tipo_xp]: o mesmo codigo em texto (`tentativas`, `tempo`...), que e
      como a parcela viaja ao app.
    - [vr_peso]: a fatia de `Q`, em `Decimal` (a soma tem de dar 1,000 exato).
    - [co_forma]: `linear`, `hiperbolica` ou `merito`.
    - [vr_x0], [vr_escala]: as constantes da curva; `None` no merito, e a
      escala tambem no tempo linear (a regua vai ate o teto do desafio).
    """

    nu_tipo_xp: int
    co_tipo_xp: str
    vr_peso: Decimal
    co_forma: str
    vr_x0: Optional[Decimal]
    vr_escala: Optional[Decimal]


@dataclass(frozen=True, slots=True)
class ReguaDaNota:
    """Uma versao inteira da regua: o cabecalho e as parcelas dela."""

    nu_versao: int
    dt_inicio_vigencia: date
    #: `{nu_tipo_xp: parcela}`. ⚠️ Uma parcela que falta **nao entra na nota**
    #: (o dono quis poder ter mais ou menos parcelas no futuro); a soma dos
    #: pesos das que existem continua tendo de fechar em 1,000.
    parcelas: Mapping[int, ParcelaDaRegua]

    def parcela(self, nu_tipo_xp: int) -> Optional[ParcelaDaRegua]:
        """A parcela de um tipo, ou `None` quando esta versao nao a tem."""
        return self.parcelas.get(nu_tipo_xp)

    @property
    def peso_do_merito(self) -> Decimal:
        """O peso que multiplica os pesos RELATIVOS de cada feito; zero sem merito."""
        merito = self.parcela(XP_MERITO)
        return merito.vr_peso if merito is not None else Decimal(0)


def _decimal(valor: Any) -> Optional[Decimal]:
    """`Decimal` do que o banco devolveu (`NUMERIC` ja vem `Decimal`), ou `None`."""
    return None if valor is None else Decimal(str(valor))


def reguas_das_linhas(linhas: Iterable[Mapping[str, Any]]) -> list[ReguaDaNota]:
    """Agrupa as linhas de `vw905_parcela_regua_nota` em versoes, conferidas.

    Args:
        linhas: `nu_versao_regua`, `dt_inicio_vigencia`, `nu_tipo_xp`,
            `co_tipo_xp`, `vr_peso`, `co_forma`, `vr_x0`, `vr_escala`.

    Returns:
        As versoes, da mais antiga para a mais nova.

    Raises:
        ReguaDaNotaInvalida: uma versao cuja soma de pesos nao fecha em 1,000,
            ou com a mesma parcela duas vezes.
    """
    por_versao: dict[int, dict[str, Any]] = {}
    for linha in linhas:
        versao = int(linha["nu_versao_regua"])
        grupo = por_versao.setdefault(
            versao, {"dt": linha["dt_inicio_vigencia"], "parcelas": {}}
        )
        tipo = int(linha["nu_tipo_xp"])
        if tipo in grupo["parcelas"]:
            # A PK da `tb905` ja impede; repetido aqui porque a funcao tambem
            # recebe linhas montadas em teste.
            raise ReguaDaNotaInvalida(
                f"a regua {versao} traz a parcela {tipo} duas vezes"
            )
        grupo["parcelas"][tipo] = ParcelaDaRegua(
            nu_tipo_xp=tipo,
            co_tipo_xp=str(linha["co_tipo_xp"]),
            vr_peso=_decimal(linha["vr_peso"]),
            co_forma=str(linha["co_forma"]),
            vr_x0=_decimal(linha["vr_x0"]),
            vr_escala=_decimal(linha["vr_escala"]),
        )

    reguas = []
    for versao in sorted(por_versao):
        grupo = por_versao[versao]
        soma = sum((p.vr_peso for p in grupo["parcelas"].values()), Decimal(0))
        if soma != Decimal(1):
            # ⚠️ O que o banco nao consegue garantir: a soma atravessa linhas.
            # Com 0,95, toda nota sairia 5% menor e ninguem tiraria 30.
            raise ReguaDaNotaInvalida(
                f"os pesos da regua {versao} somam {soma}, e precisam somar 1,000"
            )
        reguas.append(
            ReguaDaNota(
                nu_versao=versao,
                dt_inicio_vigencia=grupo["dt"],
                parcelas=dict(grupo["parcelas"]),
            )
        )
    return reguas


def regua_vigente(reguas: Iterable[ReguaDaNota], dt_dia: date) -> ReguaDaNota:
    """A versao que vale para o desafio de [dt_dia].

    ⚠️ **A de MAIOR `dt_inicio_vigencia` que ainda seja <= `dt_dia`** - a regra
    da `0030`. Ninguem aponta um desafio para uma regua: a data decide, e por
    isso os desafios ja publicados nao precisaram de `UPDATE`.

    ⚠️ O `dt_dia` e o dia UTC do desafio (`desafio_dia.tb001`), e nao o dia de
    quem joga nem o do envio: um reenvio atrasado de ontem e pontuado com a
    regua de ontem.

    Raises:
        ReguaDaNotaInvalida: nenhuma versao vale nesse dia.
    """
    candidatas = [r for r in reguas if r.dt_inicio_vigencia <= dt_dia]
    if not candidatas:
        raise ReguaDaNotaInvalida(
            f"nenhuma regua da nota vale em {dt_dia.isoformat()}: sem ela o XP "
            "do desafio nao tem como ser calculado"
        )
    return max(candidatas, key=lambda r: r.dt_inicio_vigencia)


def nota_da_curva(
    parcela: ParcelaDaRegua,
    medida: Decimal,
    *,
    unidade: Decimal = Decimal(1),
    escala_sem_valor: Optional[Decimal] = None,
) -> Decimal:
    """A nota de uma parcela de sessao, entre 0 e 1.

    Args:
        parcela: a linha da regua (forma, `x0`, escala).
        medida: a medida crua - tentativas, dicas, ou o tempo em ms.
        unidade: em que unidade `x0` e a escala estao escritos, medidos na
            unidade da [medida]. ⚠️ So o tempo usa: a regua fala em multiplos
            do piso, e a medida chega em ms, entao a unidade e o proprio piso.
        escala_sem_valor: a escala, ja na unidade da medida, quando a regua a
            deixa vazia - o tempo linear da versao 1, que vai ate o teto do
            desafio (`teto - x0 * piso`).

    Raises:
        ReguaDaNotaInvalida: forma que nao e curva, ou escala que nao existe.
    """
    # ⚠️ **A forma e conferida PRIMEIRO**, antes de qualquer conta: dentro de
    # `x0` toda curva da 1, e uma forma desconhecida passaria calada justamente
    # na resolucao perfeita - e so falharia na pior.
    if parcela.co_forma not in (FORMA_LINEAR, FORMA_HIPERBOLICA):
        raise ReguaDaNotaInvalida(
            f"a parcela {parcela.co_tipo_xp} tem a forma {parcela.co_forma!r}, "
            "que nao e uma curva de sessao"
        )
    if parcela.vr_x0 is None:
        raise ReguaDaNotaInvalida(
            f"a parcela {parcela.co_tipo_xp} ({parcela.co_forma}) nao tem x0"
        )
    x0 = parcela.vr_x0 * unidade
    escala = (
        parcela.vr_escala * unidade
        if parcela.vr_escala is not None
        else escala_sem_valor
    )
    if escala is None or escala <= 0:
        raise ReguaDaNotaInvalida(
            f"a parcela {parcela.co_tipo_xp} ficou sem escala positiva "
            f"(veio {escala!r})"
        )

    excesso = (medida - x0) / escala
    if excesso <= 0:
        # Dentro do que nao perde nada: 1a tentativa, zero dica, ate o piso.
        return Decimal(1)
    if parcela.co_forma == FORMA_LINEAR:
        # `max` porque a reta passa de zero depois do fim da escala, e a nota
        # nao fica negativa: da 4a tentativa em diante, na versao 1, ela e 0.
        return max(Decimal(0), Decimal(1) - excesso)
    # A hiperbole (a unica outra forma que passou pela conferencia do comeco).
    return Decimal(1) / (Decimal(1) + excesso)


def regua_para_publicar(regua: ReguaDaNota) -> dict[str, Any]:
    """A regua na forma que o desafio publicado a leva ao app (T104).

    ⚠️ **As parcelas vao pelo NOME** (`co_tipo_xp`), e nao pelo numero da
    `tb901`: o app conhece as parcelas pelo nome, e publicar o numero criaria
    uma segunda identidade para a mesma coisa (a mesma regra do `nu_feito`).

    ⚠️ Os numeros vao como `float` (JSON nao tem decimal). O app so ESTIMA com
    eles; quem grava o XP e o servidor, em `Decimal`.
    """
    return {
        "versao": regua.nu_versao,
        "parcelas": [
            {
                "parcela": p.co_tipo_xp,
                "peso": float(p.vr_peso),
                "forma": p.co_forma,
                "x0": None if p.vr_x0 is None else float(p.vr_x0),
                "escala": None if p.vr_escala is None else float(p.vr_escala),
            }
            # Na ordem do `nu_tipo_xp`: tentativas, tempo, dica, merito.
            for _, p in sorted(regua.parcelas.items())
        ],
    }
