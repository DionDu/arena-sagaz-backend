"""A SEQUENCIA DE TIPOS: o job gerando, na ordem pedida, um tipo por dia (27/10/2026).

═══════════════════════════════════════════════════════════════════════════
POR QUE ISTO EXISTE
═══════════════════════════════════════════════════════════════════════════

Pedido do dono, para testar no aparelho todos os tipos do Quatro em Linha antes
da 1.4.0:

> *"com novos parametros poderia gerar sequencias de desafios so para um jogo
> especifico (quatro, Pontinhos etc). Poderia ter um array com os tipos de
> desafios que queremos gerar na sequencia (ex: [figura["z"], sobreviva etc]).
> Sem este parametro funciona como ja ocorre hoje, quando especificado o
> parametro o proximo dia gerado sera figura, depois sobreviva e assim por
> diante. (...) que funcionasse tambem para outros jogos no futuro."*

⚠️ **Generico de nascenca**: o nome do tipo ja diz o jogo (`quatro_figura`,
`pontinhos_cadeia_longa`, `damas_coroar`), entao nada aqui sabe de jogo nenhum.
Quem sabe e o catalogo (`tipos_de_desafio.RECEITAS`) e o editorial.

═══════════════════════════════════════════════════════════════════════════
A FORMA DE ESCREVER
═══════════════════════════════════════════════════════════════════════════

    quatro_figura[figura=z], quatro_segurar_magno, quatro_vencer_em_n[lances=7]@tex

  · o nome do tipo, como em `RECEITAS`;
  · `[...]` (opcional) escolhe a VARIANTE pelos parametros dela, como o
    editorial os escreve: `chave=valor`, ou so `valor` (casa com qualquer
    parametro que tenha aquele valor - `quatro_figura[z]`). Aspas sao
    toleradas (`figura["z"]`, a forma em que o dono escreveu);
  · `@personagem` (opcional) fixa o adversario.

Sem `[...]`, vale a PRIMEIRA variante do editorial; sem `@`, o rodizio de
sempre (pela data e pela vizinhanca).

⚠️ **A primeira variante, e nao o odometro da data**: a sequencia e para teste,
e quem a escreve quer saber de antemao o que vai sair. Quem quiser outra pede
pelos colchetes.

═══════════════════════════════════════════════════════════════════════════
⛔ O QUE ELA RECUSA ANTES DE GERAR
═══════════════════════════════════════════════════════════════════════════

Tipo fora do ar (sem receita ou sem editorial), variante que nao existe, e
personagem que nao existe ou que a variante nao aceita. ⚠️ **Tudo de uma vez,
numa mensagem so**: um erro de digitacao no 7o item nao pode custar seis dias
de geracao (minutos cada) antes de aparecer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from . import editorial as editorial_mod
from .tipos_de_desafio import RECEITAS

#: Os personagens que existem - os mesmos do rodizio (`gerador.PERSONAGENS`).
#: ⚠️ Repetidos aqui, e nao importados, para este modulo nao carregar o gerador
#: (e com ele os motores) so para conferir um texto.
PERSONAGENS = ("cacau", "pita", "tex", "magno")

#: Um item da sequencia: `tipo`, `[filtro]` opcional e `@personagem` opcional.
#: ⚠️ `\s*` entre as partes: espaco digitado por engano nao deve recusar o item.
_ITEM = re.compile(
    r"^\s*(?P<tipo>[a-z0-9_]+)\s*"
    r"(?:\[(?P<filtro>[^\]]*)\])?\s*"
    r"(?:@\s*(?P<personagem>[a-z]+))?\s*$"
)


class SequenciaInvalida(ValueError):
    """A sequencia pedida nao pode ser gerada - a mensagem diz cada motivo."""


@dataclass(frozen=True, slots=True)
class PedidoDoDia:
    """O que UM dia da sequencia deve ser.

    Atributos:
        co_tipo: o tipo de desafio (`quatro_figura`).
        filtro: pares `(chave, valor)`; `chave` nula casa com qualquer
            parametro. Vazio = a primeira variante.
        co_personagem: o adversario fixado, ou `None` para o rodizio.
    """

    co_tipo: str
    filtro: tuple[tuple[Optional[str], str], ...] = ()
    co_personagem: Optional[str] = None

    def descrever(self) -> str:
        """O pedido como foi escrito (para o log e o relatorio)."""
        texto = self.co_tipo
        if self.filtro:
            texto += (
                "["
                + ",".join(v if c is None else f"{c}={v}" for c, v in self.filtro)
                + "]"
            )
        if self.co_personagem:
            texto += f"@{self.co_personagem}"
        return texto

    def casa(self, publicacao: editorial_mod.Publicacao) -> bool:
        """A variante [publicacao] atende o filtro?

        ⚠️ Compara TEXTO com texto (`str(7) == "7"`): o filtro vem da linha de
        comando, e o editorial guarda numeros como numeros.
        """
        parametros = {chave: str(valor) for chave, valor in publicacao.parametros.items()}
        for chave, valor in self.filtro:
            if chave is None:
                if valor not in parametros.values():
                    return False
            elif parametros.get(chave) != valor:
                return False
        return True

    def aceita_o_personagem(self, publicacao: editorial_mod.Publicacao) -> bool:
        """A variante aceita o personagem pedido? (Sem pedido, aceita.)"""
        if self.co_personagem is None:
            return True
        return (
            publicacao.co_personagens is None
            or self.co_personagem in publicacao.co_personagens
        )


def _dividir(texto: str) -> list[str]:
    """Separa os itens pelas virgulas de FORA dos colchetes.

    ⚠️ Um `split(",")` simples quebraria `quatro_figura[figura=i,folga=2]` no
    meio do filtro.
    """
    itens: list[str] = []
    atual: list[str] = []
    profundidade = 0
    for caractere in texto:
        if caractere == "[":
            profundidade += 1
        elif caractere == "]":
            profundidade -= 1
        if caractere == "," and profundidade == 0:
            itens.append("".join(atual))
            atual = []
        else:
            atual.append(caractere)
    itens.append("".join(atual))
    # Itens vazios (virgula sobrando no fim, por exemplo) sao ignorados.
    return [item for item in itens if item.strip()]


def _ler_filtro(bruto: str) -> tuple[tuple[Optional[str], str], ...]:
    """`figura=z, folga=2` → `(("figura", "z"), ("folga", "2"))`; `z` → `((None, "z"),)`."""
    pares: list[tuple[Optional[str], str]] = []
    for parte in bruto.split(","):
        parte = parte.strip()
        if not parte:
            continue
        chave, igual, valor = parte.partition("=")
        if igual:
            pares.append((chave.strip(), valor.strip().strip("\"'")))
        else:
            pares.append((None, chave.strip().strip("\"'")))
    return tuple(pares)


def ler_sequencia(texto: str) -> list[PedidoDoDia]:
    """Le o texto da linha de comando. Ver a forma no topo do modulo.

    Raises:
        SequenciaInvalida: item que nao segue a forma, ou sequencia vazia.
    """
    pedidos: list[PedidoDoDia] = []
    erros: list[str] = []
    for item in _dividir(texto):
        casou = _ITEM.match(item.strip().lower())
        if casou is None:
            erros.append(f"`{item.strip()}` nao segue a forma tipo[filtro]@personagem")
            continue
        pedidos.append(
            PedidoDoDia(
                co_tipo=casou["tipo"],
                filtro=_ler_filtro(casou["filtro"] or ""),
                co_personagem=casou["personagem"],
            )
        )
    if erros:
        raise SequenciaInvalida("; ".join(erros))
    if not pedidos:
        raise SequenciaInvalida("a sequencia esta vazia")
    return pedidos


def pedidos_do_jogo(co_jogo: str) -> list[PedidoDoDia]:
    """Um pedido para cada tipo NO AR de [co_jogo], na ordem do catalogo.

    E o que `--jogo quatro` sem `--sequencia` gera: um desafio de cada tipo.

    Raises:
        SequenciaInvalida: o jogo nao tem tipo no ar.
    """
    pedidos = [
        PedidoDoDia(co_tipo=co_tipo)
        for co_tipo, receita in RECEITAS.items()
        if receita.co_jogo == co_jogo and co_tipo in editorial_mod.EDITORIAL
    ]
    if not pedidos:
        raise SequenciaInvalida(f"o jogo `{co_jogo}` nao tem tipo no ar")
    return pedidos


def variante_do_pedido(pedido: PedidoDoDia) -> editorial_mod.Publicacao:
    """A variante que o dia vai usar: a PRIMEIRA que casa com o filtro e o personagem.

    Raises:
        SequenciaInvalida: nenhuma variante serve.
    """
    for publicacao in editorial_mod.variantes_de(pedido.co_tipo):
        if pedido.casa(publicacao) and pedido.aceita_o_personagem(publicacao):
            return publicacao
    raise SequenciaInvalida(
        f"`{pedido.descrever()}`: nenhuma variante serve. As do editorial: "
        + "; ".join(
            str(dict(p.parametros))
            + (f" (so {', '.join(p.co_personagens)})" if p.co_personagens else "")
            for p in editorial_mod.variantes_de(pedido.co_tipo)
        )
    )


def conferir(pedidos: Sequence[PedidoDoDia], *, co_jogo: Optional[str] = None) -> None:
    """Recusa, de uma vez, tudo o que nao daria para gerar.

    Args:
        co_jogo: quando vem, todo tipo tem de ser deste jogo (`--jogo`).

    Raises:
        SequenciaInvalida: com TODOS os motivos, um por item.
    """
    erros: list[str] = []
    for pedido in pedidos:
        nome = pedido.descrever()
        receita = RECEITAS.get(pedido.co_tipo)
        if receita is None or pedido.co_tipo not in editorial_mod.EDITORIAL:
            erros.append(f"`{nome}`: o tipo nao esta no ar")
            continue
        if co_jogo is not None and receita.co_jogo != co_jogo:
            erros.append(f"`{nome}`: o tipo e do jogo `{receita.co_jogo}`, e nao de `{co_jogo}`")
            continue
        if pedido.co_personagem is not None and pedido.co_personagem not in PERSONAGENS:
            erros.append(
                f"`{nome}`: `{pedido.co_personagem}` nao e personagem "
                f"({', '.join(PERSONAGENS)})"
            )
            continue
        try:
            variante_do_pedido(pedido)
        except SequenciaInvalida as erro:
            erros.append(str(erro))
    if erros:
        raise SequenciaInvalida("\n  ".join(["a sequencia nao pode ser gerada:", *erros]))
