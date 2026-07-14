"""Cache de curta duração para o leaderboard.

POR QUE ISTO EXISTE (leia antes de mexer)
=========================================
Montar o ranking é a consulta MAIS CARA da API, e — este é o ponto — **ela não
pode ser barateada com índice**. A VIEW ``progressao.vw101_ranking_global_geral``
calcula a posição com uma *window function*::

    DENSE_RANK() OVER (ORDER BY g.nu_xp_total DESC) AS nu_posicao

Uma window function sem ``PARTITION BY`` enxerga a tabela INTEIRA. Duas
consequências, ambas ruins:

1. O Postgres precisa ler todas as linhas de ``tb001_progressao_usuario`` com
   XP > 0, juntá-las a ``conta.tb001_usuario`` e **ordenar tudo** — só então sabe
   dizer quem é o 1º. O ``LIMIT 100`` da rota corta o resultado **depois** disso;
   não evita o trabalho.
2. O Postgres **não consegue empurrar o filtro para baixo** da window function.
   Nem o ``WHERE ic_publico = TRUE`` do Top-N, nem o ``WHERE id_usuario = :id`` da
   linha "eu". Empurrar mudaria o ranking (a posição depende de quem está na
   conta), então o planejador simplesmente não faz. **Buscar a MINHA linha custa
   o mesmo que montar o ranking todo.**

Ou seja: cada abertura da tela de placar = varredura + ordenação completa, duas
vezes. E é a mesma tabela que a sincronização de todos os jogadores escreve o
tempo todo.

Hoje, com poucas centenas de contas, isso é irrelevante (milissegundos). O
problema aparece quando a base cresce — e aí aparece de uma vez, porque o custo
sobe com o TOTAL de usuários, não com o número de acessos.

O QUE ESTE CACHE RESOLVE (E O QUE NÃO RESOLVE)
==============================================
Resolve o **volume de acessos**: mil jogadores abrindo a tela no mesmo minuto
viram UMA consulta, não mil. É também o que torna seguro dar ao usuário um botão
de "atualizar" — apertá-lo mais rápido que o TTL não chega ao banco.

**Não** resolve o custo unitário. Quando a base ficar grande, a saída é
transformar a ``vw101`` em MATERIALIZED VIEW atualizada de tempos em tempos (ou
guardar ``nu_posicao`` numa coluna). Isso está registrado como dívida conhecida
em ``specs/006-conta-nuvem/checklist-producao.md``.

O cache é **por processo** (cada réplica do Railway tem o seu). Não faz mal:
o pior caso é uma consulta por réplica por TTL.
"""
from __future__ import annotations

import time
from typing import Any, Optional

# Quanto tempo uma resposta fica "boa" (segundos).
#
# 30s é o número que amarra os dois lados: é também o intervalo mínimo entre
# dois toques no botão de atualizar do app. A simetria é de propósito — apertar
# o botão antes disso não poderia mostrar nada novo de qualquer forma, porque a
# resposta viria daqui, deste cache. O usuário não fica esperando à toa.
TTL_SEGUNDOS = 30

# Teto de linhas "eu" guardadas. É um dicionário em memória; sem teto, uma base
# grande de usuários ativos o faria crescer sem limite. Ao estourar, esvaziamos
# tudo (mais simples e previsível que um LRU — e o custo é uma consulta a mais).
MAX_ENTRADAS_EU = 5_000


class _CacheTTL:
    """Dicionário simples com expiração por tempo. Não é thread-safe por opção:
    o servidor é assíncrono de thread única, e uma corrida aqui custaria, no pior
    caso, uma consulta repetida — nunca um dado errado."""

    def __init__(self, ttl: float, maximo: Optional[int] = None) -> None:
        self._ttl = ttl
        self._maximo = maximo
        self._itens: dict[Any, tuple[float, Any]] = {}

    def obter(self, chave: Any) -> Optional[Any]:
        item = self._itens.get(chave)
        if item is None:
            return None
        gravado_em, valor = item
        if time.monotonic() - gravado_em > self._ttl:
            self._itens.pop(chave, None)  # venceu
            return None
        return valor

    def guardar(self, chave: Any, valor: Any) -> None:
        if self._maximo is not None and len(self._itens) >= self._maximo:
            self._itens.clear()
        self._itens[chave] = (time.monotonic(), valor)

    def limpar(self) -> None:
        """Esvazia o cache. Usado pelos testes — e nada mais."""
        self._itens.clear()


# O Top-N é IGUAL para todo mundo: a chave é só o limite pedido.
cache_top = _CacheTTL(TTL_SEGUNDOS)

# A linha "eu" é por usuário.
cache_eu = _CacheTTL(TTL_SEGUNDOS, maximo=MAX_ENTRADAS_EU)


def limpar_tudo() -> None:
    """Esvazia os dois caches (usado nos testes, para isolar um do outro)."""
    cache_top.limpar()
    cache_eu.limpar()
