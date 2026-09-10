"""Dubles de banco para os testes do Desafio do Dia — sem Postgres.

⚠️ **Nao tem prefixo `test_` de proposito**: e modulo de apoio, e o pytest nao o
coleta como arquivo de casos. Mesma convencao de `fakes_conta.py`.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE DUBLE PROVA, E O QUE ELE NAO PROVA
═══════════════════════════════════════════════════════════════════════════

Ele roteia consultas por **trecho de SQL** e devolve linhas preparadas. Com isso
da para testar tudo o que e **decisao do codigo**: qual regra recusou a acao, que
recado o dono le, como a pagina se desenha, quantos dias a fila cobre.

⛔ **Ele NAO prova que o SQL esta certo.** Um `JOIN` errado, um nome de VIEW
digitado torto ou um `ON CONFLICT` na constraint errada passam por aqui sem um
arranhao — o duble nunca executa SQL, so o reconhece.

Quem prova isso e o banco de verdade, e o projeto tem dois lugares para isso:
`scripts/conferir_migracao_desafio.py` (as 126 colunas contra o
`information_schema`) e o portao **T050**, que roda o ciclo inteiro no `des`.
Escrever aqui um teste chamado *"o SQL funciona"* seria dar a impressao contraria
— e essa impressao ja custou caro neste projeto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional


class _Mappings:
    """O que `resultado.mappings()` devolve: linhas como dicionarios."""

    def __init__(self, linhas: Iterable[Mapping[str, Any]]) -> None:
        self._linhas = list(linhas)

    def all(self) -> list[Mapping[str, Any]]:
        """Todas as linhas."""
        return self._linhas


class FakeResultado:
    """O objeto que uma `session.execute(...)` devolve, na parte que usamos.

    Implementa `mappings()`, `first()` e `scalar_one()` — e so isso: um duble que
    imita a interface inteira do SQLAlchemy esconderia, atras da propria
    fidelidade, o fato de que nada aqui e um banco.
    """

    def __init__(self, linhas: Iterable[Mapping[str, Any]] | None = None) -> None:
        self._linhas = list(linhas or [])

    def mappings(self) -> _Mappings:
        """As linhas como dicionarios."""
        return _Mappings(self._linhas)

    def first(self) -> Optional[Mapping[str, Any]]:
        """A primeira linha, ou `None` — e o que `RETURNING` produz."""
        return self._linhas[0] if self._linhas else None

    def all(self) -> list[Mapping[str, Any]]:
        """Todas as linhas, sem passar por `mappings()`."""
        return self._linhas

    def scalar_one(self) -> Any:
        """O unico valor da unica linha — o que um `COUNT(*)` produz.

        Raises:
            AssertionError: quando nao ha exatamente uma linha. E de proposito:
                o `scalar_one` do SQLAlchemy tambem falha, e um duble mais
                tolerante deixaria passar um teste que o banco recusaria.
        """
        assert len(self._linhas) == 1, (
            f"scalar_one() com {len(self._linhas)} linha(s): o duble esta "
            "devolvendo o que a consulta real nao devolveria."
        )
        (unica,) = self._linhas
        return next(iter(unica.values()))


@dataclass
class FakeSessaoSQL:
    """Uma `AsyncSession` falsa que roteia por **trecho de SQL**.

    Atributos:
        respostas: `{trecho: linhas ou funcao(parametros) -> linhas}`. O primeiro
            trecho encontrado no texto da consulta manda.
        executadas: o historico `(sql, parametros)`, para os testes conferirem o
            que foi realmente chamado.
        commits: quantas vezes `commit()` foi chamado.
        erro_por_trecho: `{trecho: excecao}` — para simular o banco recusando
            (o `un001_dia` de um dia ja ocupado, por exemplo).

    ⚠️ **Consulta sem resposta preparada devolve VAZIO, e nao erro.** E o
    comportamento util aqui: uma tela que precisa de tres consultas nao deveria
    exigir que todo teste prepare as tres so para exercitar uma. Quando a
    ausencia importa, o teste afirma sobre `executadas`.
    """

    respostas: dict[str, Any] = field(default_factory=dict)
    executadas: list[tuple[str, Optional[dict[str, Any]]]] = field(
        default_factory=list
    )
    commits: int = 0
    erro_por_trecho: dict[str, Exception] = field(default_factory=dict)

    async def execute(self, sql: Any, parametros: Any = None) -> FakeResultado:
        """Reconhece a consulta pelo texto e devolve o que foi preparado."""
        texto = str(sql)
        self.executadas.append((texto, parametros))

        for trecho, erro in self.erro_por_trecho.items():
            if trecho in texto:
                raise erro

        for trecho, resposta in self.respostas.items():
            if trecho in texto:
                if isinstance(resposta, Callable):  # type: ignore[arg-type]
                    return FakeResultado(resposta(parametros or {}))
                return FakeResultado(resposta)
        return FakeResultado([])

    async def commit(self) -> None:
        """Conta o `commit`. Nao ha transacao de verdade para fechar."""
        self.commits += 1

    async def rollback(self) -> None:
        """Existe para a interface; nao faz nada."""

    def sql_executado(self, trecho: str) -> bool:
        """Alguma consulta executada continha aquele trecho?"""
        return any(trecho in texto for texto, _ in self.executadas)
