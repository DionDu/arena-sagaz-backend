"""A VIZINHANCA DE UM DIA: o que o desafio de ontem e o de amanha proibem hoje.

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Em 02/10/2026 o dono mudou a regra da fila (`docs/DECISOES-do-dono.md` do app,
§8zk): os desafios passam a nascer **pre-aprovados**, ele descarta o que achar
ruim quando passar pelo painel, e a geracao seguinte tapa primeiro os buracos
mais proximos. E pos uma condicao junto:

> *"E claro que sempre precisa garantir a alternancia de jogos/modalidades/
> personagens do desafio de um dia para o outro, para nao termos desafios
> parecidos de um dia para outro."*

⚠️ **Ate aquele dia a alternancia era um efeito da DATA**, e nao uma regra: o
jogo saia da paridade do dia, o personagem de `dias % 4`. Enquanto todo dia era
gerado no seu lugar isso bastava. ⛔ **Deixa de bastar quando um desafio muda de
data** — a compactacao puxa um aprovado de D+12 para D+1, e a data nova nao e a
que escolheu o jogo e o personagem dele.

Entao a regra passa a ser **explicita**, escrita uma vez aqui, e as duas pecas
que poem desafio num dia a consultam:

  · `compactar_fila.remanejar` — so aceita o doador que nao conflita com os
    vizinhos do buraco;
  · `gerador.escolher_*` — ao gerar para um buraco no meio da fila, desvia do
    que os dois vizinhos ja usam.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE "PARECIDO" QUER DIZER — E O QUE NAO QUER
═══════════════════════════════════════════════════════════════════════════

Dois desafios em dias consecutivos conflitam quando repetem **qualquer um** de:

  · o **jogo** (Pontinhos ao lado de Pontinhos);
  · o **personagem** (o Tex dois dias seguidos);
  · a **modalidade**, quando os dois tem uma (brasileira ao lado de brasileira);
  · o **tipo** (ja implicado pelo jogo, e mantido para o dia em que um jogo
    novo entrar com tipos proprios).

⚠️ **Isto e mais estrito que a compactacao de 16/09/2026**, que so olhava o
tipo e dizia, por escrito, que proibir o mesmo jogo *"tornaria quase toda
compactacao impossivel"*. Naquela epoca os doadores eram poucos (so o que o dono
aprovava a mao); com tudo nascendo aprovado, a fila inteira e doadora, e um
doador do jogo certo esta sempre a dois dias de distancia.

⛔ **Este modulo nao conhece banco nem motor.** E so a regra — o que permite
testa-la sem nenhuma conexao aberta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Ocupante:
    """O que importa, para a alternancia, de um desafio que mora num dia.

    Atributos:
        co_jogo: `pontinhos` · `damas`.
        co_personagem: o adversario (`cacau`, `pita`, `tex`, `magno`).
        co_modalidade: a regra das damas; `None` no Pontinhos.
        co_tipo_desafio: o tipo (`damas_coroar`, ...). `None` quando quem
            pergunta ainda nao sabe o tipo — na escolha do jogo, por exemplo.
    """

    co_jogo: Optional[str]
    co_personagem: Optional[str] = None
    co_modalidade: Optional[str] = None
    co_tipo_desafio: Optional[str] = None


def conflita(a: Optional[Ocupante], b: Optional[Ocupante]) -> bool:
    """Os dois desafios sao parecidos demais para morar em dias consecutivos?

    ⚠️ **Campo ausente nao conflita.** Comparar `None` com `None` daria "iguais"
    e travaria a compactacao inteira por falta de dado — um desafio antigo sem
    personagem carregado, por exemplo. So conflita o que se SABE que e igual.
    """
    if a is None or b is None:
        return False

    def mesmo(x: Optional[str], y: Optional[str]) -> bool:
        return x is not None and y is not None and x == y

    return (
        mesmo(a.co_jogo, b.co_jogo)
        or mesmo(a.co_personagem, b.co_personagem)
        or mesmo(a.co_modalidade, b.co_modalidade)
        or mesmo(a.co_tipo_desafio, b.co_tipo_desafio)
    )


@dataclass(frozen=True, slots=True)
class Vizinhanca:
    """Os desafios que moram no dia anterior e no seguinte.

    ⚠️ **`None` e "nao ha desafio la"**, e e o caso normal no fim da fila: o
    ultimo dia gerado nao tem vizinho a frente, e nada deve ser evitado por ele.
    """

    anterior: Optional[Ocupante] = None
    seguinte: Optional[Ocupante] = None

    def _valores(self, campo: str) -> frozenset[str]:
        """Os valores daquele campo nos vizinhos que existem."""
        return frozenset(
            getattr(v, campo)
            for v in (self.anterior, self.seguinte)
            if v is not None and getattr(v, campo) is not None
        )

    @property
    def jogos(self) -> frozenset[str]:
        """Os jogos que os vizinhos ja usam."""
        return self._valores("co_jogo")

    @property
    def personagens(self) -> frozenset[str]:
        """Os personagens que os vizinhos ja usam."""
        return self._valores("co_personagem")

    @property
    def modalidades(self) -> frozenset[str]:
        """As modalidades que os vizinhos ja usam."""
        return self._valores("co_modalidade")

    def aceita(self, ocupante: Ocupante) -> bool:
        """Este desafio pode morar entre os dois vizinhos?"""
        return not (
            conflita(ocupante, self.anterior) or conflita(ocupante, self.seguinte)
        )


def preferir(
    opcoes: Sequence[T], *, indice_do_rodizio: int, evitar: Iterable[T] = ()
) -> T:
    """A opcao do rodizio, desviando do que os vizinhos ja usam.

    Args:
        opcoes: a lista em ordem estavel (os jogos, os personagens...).
        indice_do_rodizio: a posicao que o rodizio pela data escolheria.
        evitar: o que nao pode repetir.

    Returns:
        A opcao do rodizio, se ela nao estiver em `evitar`; senao a proxima da
        lista, girando, que nao esteja. ⚠️ **Se todas estiverem em `evitar`,
        devolve a do rodizio mesmo** — com dois jogos e dois vizinhos de jogos
        diferentes nao ha saida, e ficar sem desafio seria pior que repetir.

    ⚠️ **Continua deterministico**: a mesma fila e a mesma data dao a mesma
    resposta, que e o que a idempotencia do job (T038) precisa. So que agora a
    resposta depende da fila, e nao apenas da data.
    """
    if not opcoes:
        raise ValueError("preferir() precisa de pelo menos uma opcao")
    proibidas = set(evitar)
    n = len(opcoes)
    # Gira a partir da escolha do rodizio: `(indice + passo) % n` percorre a
    # lista inteira uma vez, comecando por quem o rodizio escolheria.
    for passo in range(n):
        candidata = opcoes[(indice_do_rodizio + passo) % n]
        if candidata not in proibidas:
            return candidata
    return opcoes[indice_do_rodizio % n]
