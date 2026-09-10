"""A CONEXAO DO JOB com o Postgres (RF-DES-011a, T049b).

═══════════════════════════════════════════════════════════════════════════
⛔ POR QUE ESTE ARQUIVO EXISTE, EM VEZ DE UM `from api.nucleo.banco import ...`
═══════════════════════════════════════════════════════════════════════════

`api/nucleo/banco.py` **constroi a engine no import**. Ela e a engine da API: um
pool dimensionado para um servidor web que fica de pe, com `pool_pre_ping`
testando conexoes que dormiram entre duas requisicoes.

O job e o oposto disso — acorda, faz o trabalho pesado e **termina**. Importar
aquele modulo faria duas coisas erradas de uma vez:

  1. a engine da API nasceria dentro do container do job, so por importar;
  2. a gravacao do job passaria a depender da afinacao do **servidor** — mudar o
     pool da API para aguentar mais gente mudaria, calado, como o job escreve.

⚠️ E a fronteira RF-DES-011a e exatamente esta: os dois se falam **pelo
Postgres**, e nao por dentro do codigo um do outro.

═══════════════════════════════════════════════════════════════════════════
⛔ AQUI `DATABASE_URL` NAO TEM PADRAO — E ISSO E DELIBERADO
═══════════════════════════════════════════════════════════════════════════

`api/configuracao.py` tem `DATABASE_URL = "postgresql+asyncpg://localhost:5432/..."`
por um motivo bom: a app precisa **importar** sem banco nenhum configurado, e e
o que os testes fazem o tempo todo.

⛔ **O job nao tem essa necessidade, e herdar aquele padrao seria caro.** Um
container sem a variavel tentaria `localhost:5432`, nao acharia ninguem e
morreria com `ConnectionRefusedError` — que, no log do Railway, se le como
*"o banco caiu"*. A causa real (alguem esqueceu a Variable no servico novo) so
apareceria depois de investigar o banco, que esta perfeitamente de pe.

Entao aqui a ausencia da variavel e um erro **proprio**, com nome e recado, e o
`principal()` a converte em codigo de saida **2** — *"nem comecou"*.

═══════════════════════════════════════════════════════════════════════════
⚠️ A NORMALIZACAO DA URL ESTA ESCRITA DUAS VEZES, E HA CADEADO
═══════════════════════════════════════════════════════════════════════════

O Railway entrega `postgresql://...`; o SQLAlchemy async precisa de
`postgresql+asyncpg://...`. A conversao existe la e existe aqui, porque nao da
para importar de la sem construir a engine de la.

⚠️ Duas copias de uma regra **envelhecem torto**, e o projeto ja sabe disso. Por
isso `tests/unitarios/test_banco_do_job.py` compara as duas funcoes sobre as
mesmas entradas e falha quando divergirem — e o custo de esquecer passa a ser um
teste vermelho, e nao um job que conecta com o driver sincrono e trava.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

#: O nome da variavel de ambiente. Escrito uma vez para a mensagem de erro e o
#: teste falarem do mesmo nome.
VARIAVEL_DA_URL = "DATABASE_URL"


class BancoNaoConfigurado(RuntimeError):
    """Nao ha `DATABASE_URL` no ambiente do job.

    ⚠️ **E excecao propria, e nao um `KeyError`.** Quem le o log precisa saber
    que falta uma **Variable no servico do Railway**, e nao que o codigo tem um
    dicionario com chave errada.
    """


def normalizar_url(url: str) -> str:
    """Garante o driver assincrono no esquema da URL.

    Args:
        url: o que veio do ambiente. O Railway entrega `postgresql://…`; a forma
            legada `postgres://…` ainda aparece em servicos antigos.

    Returns:
        A mesma URL com `postgresql+asyncpg://`.

    ⚠️ **Sem isto o SQLAlchemy escolhe o driver SINCRONO** (`psycopg2`), que nem
    esta instalado na imagem do job — e o erro seria um `ModuleNotFoundError` no
    meio da primeira consulta, longe da causa.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):  # forma legada
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def url_do_banco() -> str:
    """A URL do Postgres, lida do ambiente e ja normalizada.

    Raises:
        BancoNaoConfigurado: quando a variavel esta ausente ou vazia.

    ⛔ **Nao ha padrao de fabrica.** Ver o cabecalho deste modulo: um padrao aqui
    transformaria "faltou a Variable" em "o banco caiu".
    """
    bruta = os.environ.get(VARIAVEL_DA_URL, "").strip()
    if not bruta:
        raise BancoNaoConfigurado(
            f"a variavel {VARIAVEL_DA_URL} nao esta definida no ambiente do job.\n"
            "⚠️ O job GRAVA — sem banco ele nao tem o que fazer, e nao ha padrao "
            "de fabrica de proposito: um padrao apontando para localhost faria "
            "esta falha se parecer com uma queda do Postgres no log do Railway.\n"
            "Onde arrumar: Railway → o servico do JOB → Variables → "
            f"{VARIAVEL_DA_URL} (a mesma do servico da API, no MESMO ambiente)."
        )
    return normalizar_url(bruta)


def criar_engine(url: str | None = None):
    """A engine do job.

    Args:
        url: a URL ja normalizada. `None` le do ambiente.

    ⚠️ **`pool_size=1`**, e nao o padrao: este processo faz uma coisa de cada vez
    — gerar e medir sao trabalho de CPU, e nada aqui e concorrente. Um pool de
    cinco conexoes ociosas so ocupa lugar no limite do Postgres, que e
    compartilhado com a API.

    ⚠️ **`pool_pre_ping=True` mesmo assim**: a geracao de um dia pode levar
    minutos de CPU sem tocar no banco, e uma conexao parada tanto tempo pode ter
    sido derrubada pelo servidor. Sem o ping, a primeira gravacao depois da
    medicao estouraria — depois de todo o trabalho ter sido feito.
    """
    return create_async_engine(
        url or url_do_banco(),
        echo=False,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )


def fabrica_de_sessoes(engine) -> async_sessionmaker[AsyncSession]:
    """A fabrica de `AsyncSession` ligada aquela engine."""
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )


@asynccontextmanager
async def abrir_sessao(url: str | None = None) -> AsyncIterator[AsyncSession]:
    """Abre uma sessao, entrega, e **fecha a engine** ao sair.

    Uso:

        async with abrir_sessao() as sessao:
            ...

    ⚠️ **O `dispose()` no fim nao e zelo, e o que permite o processo TERMINAR.**
    A politica de reinicio do servico e `NEVER` e sair com 0 e o comportamento
    correto (ver `job/__init__.py`); uma engine viva segura conexoes e o loop de
    eventos, e o container ficaria de pe depois de o trabalho acabar — que e
    indistinguivel, no painel, de um job travado.
    """
    engine = criar_engine(url)
    try:
        async with fabrica_de_sessoes(engine)() as sessao:
            yield sessao
    finally:
        await engine.dispose()


__all__ = [
    "VARIAVEL_DA_URL",
    "BancoNaoConfigurado",
    "abrir_sessao",
    "criar_engine",
    "fabrica_de_sessoes",
    "normalizar_url",
    "url_do_banco",
]
