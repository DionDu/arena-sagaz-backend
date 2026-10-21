"""As dependências do FastAPI do registro do aparelho (T118).

Uma "dependência" do FastAPI é uma função que ele roda **antes** da rota e cujo
retorno é injetado como argumento. Ficam aqui, e não em `api/aparelhos/rotas.py`,
porque duas rotas de módulos diferentes as usam: a leitura do desafio do dia
(`api/desafios/rotas.py`) e o envio dos detalhes.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from api.aparelhos.regras import id_aparelho_do_cabecalho, offset_do_cabecalho
from api.aparelhos.repositorio import RepositorioAparelho
from api.aparelhos.servico import CabecalhosDoAparelho, ServicoAparelho
from api.nucleo.banco import obter_sessao


def ler_cabecalhos_do_aparelho(
    x_install_id: Optional[str] = Header(default=None, alias="X-Install-Id"),
    x_utc_offset: Optional[str] = Header(default=None, alias="X-Utc-Offset"),
) -> CabecalhosDoAparelho:
    """Os dois cabeçalhos que o app 1.4 manda a mais, já conferidos.

    * `X-Install-Id`: o código de instalação, um UUID v4 que o app gera na 1ª
      abertura e guarda no aparelho;
    * `X-Utc-Offset`: quantos minutos o relógio do aparelho está à frente de
      UTC (o Brasil manda `-180`).

    ⚠️ **Nunca recusa.** O app 1.3 não manda nenhum dos dois, e um valor
    ilegível vale como ausente: esta dependência roda na leitura do desafio do
    dia, e um cabeçalho de analytics com defeito não pode impedir ninguém de
    ver o desafio. Quem exige o código é a rota dos detalhes, e ela o confere
    por conta própria.
    """
    return CabecalhosDoAparelho(
        id_aparelho=id_aparelho_do_cabecalho(x_install_id),
        offset_minuto=offset_do_cabecalho(x_utc_offset),
    )


def obter_servico_aparelho(
    sessao: AsyncSession = Depends(obter_sessao),
) -> ServicoAparelho:
    """Monta o serviço ligado à sessão da requisição.

    Dependência própria (e não construção dentro da rota) para os testes a
    trocarem, em uma linha, por um serviço sobre um SQLite de memória. O
    FastAPI guarda o resultado de `obter_sessao` por requisição, então a
    leitura do desafio e o registro do aparelho usam a **mesma** sessão.
    """
    return ServicoAparelho(repo=RepositorioAparelho(sessao), sessao=sessao)
