"""O GANCHO DO AUTO-AJUSTE DO ALVO (RF-DES-017, T035a).

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTA TAREFA ENTREGA, E O QUE ELA DELIBERADAMENTE NAO ENTREGA
═══════════════════════════════════════════════════════════════════════════

RF-DES-017 diz que o alvo de dificuldade se ajusta **quando houver volume** de
tentativas reais. Hoje nao ha volume: o Desafio do Dia ainda nao existe em campo.

Entao o que entra agora e o **ponto de ajuste declarado** — a consulta que le a
taxa de resolucao real e o parametro que a regua consome —, e nao o ajuste em si.
⚠️ **Enquanto o volume nao chegar, esta funcao devolve o alvo fixo**, e e assim
mesmo: o requisito diz *"quando houver volume"*.

⚠️ **Por que escrever isso agora, e nao no dia em que o volume chegar:** porque no
dia em que ele chegar, ninguem vai lembrar que a spec prometia isto. Um requisito
que depende de alguem se lembrar dele nao e um requisito — e uma intencao. Com o
gancho no lugar, ligar o auto-ajuste passa a ser trocar um `if`, e nao redescobrir
uma promessa.

═══════════════════════════════════════════════════════════════════════════
A BANDA ALVO
═══════════════════════════════════════════════════════════════════════════

70% a 80% de resolucao media na escada dos mascotes (RF-DES-016). Abaixo, o
desafio e duro demais; acima, e banal.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A banda fixa, usada enquanto nao houver volume real.
PISO_FIXO = 0.70
TETO_FIXO = 0.80

#: Quantas resolucoes reais sao precisas antes de o alvo observado valer.
#:
#: ⚠️ **O numero e um piso de confianca, e nao uma meta.** Com poucas resolucoes,
#: a taxa observada oscila mais que a diferenca entre 70% e 80% — ajustar o alvo
#: por ruido faria a fila inteira balancar atras de um numero que nao significa
#: nada.
VOLUME_MINIMO = 200


@dataclass(frozen=True, slots=True)
class Alvo:
    """A banda que a regua deve mirar, e de onde ela veio.

    Atributos:
        piso, teto: a banda.
        co_origem: `fixo` enquanto nao ha volume; `observado` quando ha.
        nu_amostras: quantas resolucoes reais sustentam o alvo observado.
    """

    piso: float
    teto: float
    co_origem: str
    nu_amostras: int = 0


#: A consulta que le a taxa de resolucao real dos ultimos desafios.
#:
#: ⚠️ Escrita aqui, e nao dentro de uma funcao, para poder ser **lida sem rodar**
#: — e o tipo de SQL que alguem precisa conferir com o banco na frente.
#:
#: Ela conta, por desafio publicado, quantas pessoas **tentaram** e quantas
#: **resolveram**. A razao entre as duas e a taxa real; a media dela sobre os
#: ultimos N dias e o alvo observado.
SQL_TAXA_OBSERVADA = """
SELECT d.dt_dia,
       count(DISTINCT t.id_usuario)                     AS nu_tentaram,
       count(DISTINCT r.id_usuario)                     AS nu_resolveram
  FROM desafio_dia.vw001_desafio_dia d
  LEFT JOIN desafio_dia.vw002_tentativa t
         ON t.id_desafio_dia = d.id_desafio_dia
  LEFT JOIN desafio_dia.vw003_resolucao r
         ON r.id_desafio_dia = d.id_desafio_dia
 WHERE d.dt_dia BETWEEN :dt_inicio AND :dt_fim
 GROUP BY d.dt_dia
 ORDER BY d.dt_dia
"""


def alvo_para_a_regua(
    *,
    nu_tentaram: int = 0,
    nu_resolveram: int = 0,
    largura_da_banda: float = TETO_FIXO - PISO_FIXO,
) -> Alvo:
    """A banda que a regua deve mirar hoje.

    Args:
        nu_tentaram, nu_resolveram: o que a consulta acima devolveu, somado.
        largura_da_banda: quanto a banda observada abrange, mantida igual a fixa.

    Returns:
        O [Alvo], com a origem declarada.

    ⚠️ **Sem volume, devolve o alvo fixo** — e isso nao e um caso de erro nem uma
    limitacao temporaria escondida: e a resposta correta. A taxa observada de 12
    pessoas nao diz nada sobre a dificuldade de um desafio.

    ⚠️ **E quando houver volume, a banda ANDA, mas nao muda de largura.** Mover o
    centro e ajustar a mira; alargar a banda seria aceitar desafios mais
    desiguais, o que e outra decisao — e nao esta nesta.
    """
    if nu_tentaram < VOLUME_MINIMO:
        return Alvo(
            piso=PISO_FIXO,
            teto=TETO_FIXO,
            co_origem="fixo",
            nu_amostras=nu_tentaram,
        )

    observada = nu_resolveram / nu_tentaram
    metade = largura_da_banda / 2
    # A banda anda com a taxa observada, presa ao intervalo valido [0, 1].
    piso = max(0.0, min(1.0 - largura_da_banda, observada - metade))
    return Alvo(
        piso=piso,
        teto=piso + largura_da_banda,
        co_origem="observado",
        nu_amostras=nu_tentaram,
    )
