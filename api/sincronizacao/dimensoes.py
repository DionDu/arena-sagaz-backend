"""Tradução ``co_`` (texto) → ``nu_`` (número) usando as tabelas de DIMENSÃO.

**Por que isto existe.** As tabelas de fato guardam códigos NUMÉRICOS (`nu_acao`,
`nu_situacao`, `nu_origem_decisao`, `nu_tipo_xp`) — 2 bytes em vez de 16-30 — mas o
**app continua enviando as STRINGS** (`'cnn_nucleo_top_p'`). A tradução acontece
aqui, na ingestão.

**Por que o app não manda o número?** Porque o app publicado fica **congelado no
aparelho do usuário**. Se o número fosse do payload, ele viraria contrato público
de API e a numeração nunca mais poderia ser corrigida sem quebrar as versões em
campo. Mantendo a string, a numeração continua uma decisão **interna e reversível**
do banco, e o backend pode subir ANTES do app (requisito desta rodada).

**O código desconhecido (9999).** Um app mais NOVO que este backend pode mandar uma
estratégia de IA que ainda não cadastramos. Sem um destino válido, a FK estoura
**500** e o evento fica **preso para sempre** na fila de sincronização do aparelho
(o app reenvia, toma 500 de novo, para sempre). Traduzir o desconhecido para `9999`
faz o evento ENTRAR — nada de 500, nada de fila travada — e a string crua fica
registrada (em `js_extra` e no log) para o código real ser cadastrado depois.

Ver o contrato completo em ``docs/redesenho_schema_log_treino.md``.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Código sentinela "não sei o que é isto" (mesmo valor da migração 0006).
NU_DESCONHECIDO = 9999

# Cada dimensão: (VIEW de leitura, coluna do CÓDIGO textual, coluna da CHAVE
# numérica). Lemos pela VIEW — regra do projeto (ler na `vw`, escrever na `tb`).
_DIMENSOES: dict[str, tuple[str, str, str]] = {
    "acao": ("jogo_pontinhos.vw901_jogada_acao", "co_acao", "nu_acao"),
    "situacao": ("jogo_pontinhos.vw902_jogada_situacao", "co_situacao", "nu_situacao"),
    "origem_decisao": (
        "partida.vw901_jogada_origem_decisao",
        "co_origem_decisao",
        "nu_origem_decisao",
    ),
    "tipo_xp": ("partida.vw902_tipo_xp", "co_tipo_xp", "nu_tipo_xp"),
}

# Cache do processo: {dimensão: {código_texto: chave_numérica}}. As dimensões são
# minúsculas (4 a 7 linhas) e praticamente estáticas — carregar uma vez evita um
# SELECT por lance (são 31 lances por partida).
_cache: dict[str, dict[str, int]] = {}

# Códigos que JÁ sabemos ser desconhecidos. Sem isto, um app com um valor podre
# faria o cache recarregar a cada linha (um SELECT por lance — exatamente o que o
# cache existe para evitar).
_desconhecidos_vistos: dict[str, set[str]] = {}


async def _carregar(sessao: AsyncSession, dimensao: str) -> dict[str, int]:
    """Lê a dimensão inteira do banco e guarda no cache do processo."""
    view, col_codigo, col_chave = _DIMENSOES[dimensao]
    resultado = await sessao.execute(text(f"SELECT {col_codigo}, {col_chave} FROM {view}"))
    mapa = {linha[0]: linha[1] for linha in resultado.all()}
    _cache[dimensao] = mapa
    return mapa


async def resolver(
    sessao: AsyncSession, dimensao: str, valor: Any
) -> tuple[Optional[int], bool]:
    """Traduz o código textual [valor] na chave numérica da [dimensao].

    Devolve `(chave, desconhecido)`:
    - `(None, False)` → o campo veio vazio no payload (ex.: lance humano não tem
      `co_acao`). Vira NULL na coluna, que é anulável.
    - `(3, False)` → traduzido normalmente.
    - `(9999, True)` → o código NÃO existe na dimensão. Quem chama deve preservar a
      string crua (ver `js_extra`) — é a pista de que falta cadastrar um código.

    Nunca lança: a ingestão não pode quebrar por causa de um código novo.
    """
    if valor is None or valor == "":
        return None, False
    valor = str(valor)

    mapa = _cache.get(dimensao)
    if mapa is None:
        mapa = await _carregar(sessao, dimensao)

    chave = mapa.get(valor)
    if chave is not None:
        return chave, False

    # Não achou. Pode ser um código cadastrado no banco DEPOIS deste processo ter
    # subido — vale uma recarga (mas só na PRIMEIRA vez que vemos este valor).
    if valor not in _desconhecidos_vistos.setdefault(dimensao, set()):
        mapa = await _carregar(sessao, dimensao)
        chave = mapa.get(valor)
        if chave is not None:
            return chave, False
        # Continua desconhecido de verdade: anota para não reconsultar mais.
        _desconhecidos_vistos[dimensao].add(valor)
        logger.warning(
            "Código desconhecido na dimensão '%s': %r → gravado como %d. "
            "Provável app mais novo que o backend; cadastre o código.",
            dimensao,
            valor,
            NU_DESCONHECIDO,
        )

    return NU_DESCONHECIDO, True


def limpar_cache() -> None:
    """Esvazia o cache (usado nos testes e após cadastrar códigos novos)."""
    _cache.clear()
    _desconhecidos_vistos.clear()
