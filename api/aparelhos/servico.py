"""O registro do aparelho: quem é ele, que dia é para ele, e o que se grava.

Por que existe uma camada aqui: as DUAS rotas que gravam (a leitura do desafio
do dia e o envio dos detalhes) fazem as mesmas três perguntas - *qual aparelho*,
*de quem*, *que dia* - e respondê-las em cada rota seria a mesma regra escrita
duas vezes. Este arquivo as responde uma vez; as rotas só cuidam do HTTP.

O desenho está no `data-model.md` §4.3 da spec 010 (T118).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.aparelhos.regras import (
    chave_da_versao,
    detalhe_do_espaco_para_guardar,
    id_aparelho_legado,
)
from api.aparelhos.repositorio import RepositorioAparelho
from api.desafios.impedido import dia_local


@dataclass(frozen=True)
class CabecalhosDoAparelho:
    """O que o app 1.4 manda a mais em todo pedido. O app 1.3 não manda nada.

    `frozen=True` torna o objeto imutável: depois de lido o cabeçalho, ninguém
    no caminho o troca.
    """

    #: O código de instalação (`X-Install-Id`), já conferido como UUID v4.
    id_aparelho: Optional[UUID] = None
    #: O deslocamento do fuso em minutos (`X-Utc-Offset`), já na faixa ±840.
    offset_minuto: Optional[int] = None


@dataclass(frozen=True)
class RegistroDoDia:
    """O que ficou gravado - serve ao log do servidor e aos testes."""

    id_aparelho: str
    ic_legado: bool
    dt_dia_local: date
    co_versao_app: str


class ServicoAparelho:
    """Registra o aparelho e o dia dele."""

    def __init__(self, repo: RepositorioAparelho, sessao: AsyncSession) -> None:
        self.repo = repo
        self.sessao = sessao

    async def _quem_e_que_dia(
        self,
        *,
        cabecalhos: CabecalhosDoAparelho,
        uid: Optional[str],
        plataforma: str,
        agora: datetime,
    ) -> Optional[tuple[str, bool, Optional[str], date]]:
        """As três respostas: `(id_aparelho, ic_legado, id_usuario, dia_local)`.

        `None` quando não há a quem atribuir a leitura: o convidado do app 1.3
        (sem código e sem conta) fica de fora, como já ficava (`data-model.md`
        §4.1).

        **Que dia é**, na ordem:

        1. o fuso que o app 1.4 mandou no cabeçalho;
        2. o fuso da última partida da pessoa (o app 1.3 não manda fuso);
        3. UTC, quando nenhum dos dois existe - o melhor palpite disponível, e
           nunca pior do que não gravar linha nenhuma.
        """
        id_usuario: Optional[str] = None
        if uid is not None:
            id_usuario = await self.repo.id_usuario_por_identidade(uid)

        if cabecalhos.id_aparelho is not None:
            id_aparelho, legado = str(cabecalhos.id_aparelho), False
        elif id_usuario is not None:
            id_aparelho, legado = str(id_aparelho_legado(id_usuario, plataforma)), True
        else:
            return None

        offset = cabecalhos.offset_minuto
        if offset is None and id_usuario is not None:
            offset = await self.repo.ultimo_offset_da_pessoa(id_usuario)

        return id_aparelho, legado, id_usuario, dia_local(agora, offset)

    async def registrar_visita(
        self,
        *,
        versao_app: str,
        plataforma: str,
        idioma: str,
        cabecalhos: CabecalhosDoAparelho,
        uid: Optional[str],
        agora: datetime,
    ) -> Optional[RegistroDoDia]:
        """A leitura do desafio do dia: grava a versão do app no dia do aparelho.

        É chamada pela rota que a Home chama ao abrir (`GET /v1/desafios/hoje`),
        porque é uma rota que o app **1.3 já chama**: se a amostra viesse de uma
        rota nova, as versões antigas nunca apareceriam nela, e a adoção leria
        100% no dia do lançamento (research R-23).

        Returns:
            O que ficou gravado, ou `None` quando nada se grava: o convidado do
            1.3, ou uma versão que não se lê (`chave_da_versao`).
        """
        if chave_da_versao(versao_app) is None:
            return None
        quem = await self._quem_e_que_dia(
            cabecalhos=cabecalhos, uid=uid, plataforma=plataforma, agora=agora
        )
        if quem is None:
            return None
        id_aparelho, legado, id_usuario, dia = quem

        await self.repo.garantir_aparelho(
            id_aparelho=id_aparelho, ic_legado=legado, co_plataforma=plataforma
        )
        versao = await self.repo.registrar_dia(
            id_aparelho=id_aparelho,
            dt_dia_local=dia,
            id_usuario=id_usuario,
            co_versao_app=versao_app,
            co_idioma=idioma,
        )
        # O serviço é dono da transação; sem este `commit` a linha morre junto
        # com a sessão da requisição.
        await self.sessao.commit()
        return RegistroDoDia(id_aparelho, legado, dia, versao)

    async def registrar_detalhes(
        self,
        *,
        versao_app: str,
        plataforma: str,
        idioma: str,
        cabecalhos: CabecalhosDoAparelho,
        uid: Optional[str],
        agora: datetime,
        detalhes: dict[str, Any],
        versao_so: Optional[str],
        espaco_app_kb: Optional[int],
        espaco_app: Optional[Mapping[str, int]],
        limites_mb: Mapping[str, int],
    ) -> tuple[RegistroDoDia, bool]:
        """O envio diário dos detalhes, que só o app 1.4 faz.

        Grava os detalhes do aparelho na `tb003` e, na linha do dia (`tb004`),
        a versão, o sistema, o idioma e o espaço ocupado - com o detalhe por
        pasta só quando o total passa do limite da plataforma.

        ⚠️ Quem chama garante que [cabecalhos] traz o código do aparelho e que
        a versão se lê: a rota recusa com 400 antes (sem aparelho, os detalhes
        não têm onde morar).

        Returns:
            `(o que ficou gravado, se o detalhe por pasta foi guardado)`.
        """
        assert cabecalhos.id_aparelho is not None, "a rota confere o aparelho antes"
        quem = await self._quem_e_que_dia(
            cabecalhos=cabecalhos, uid=uid, plataforma=plataforma, agora=agora
        )
        assert quem is not None  # com o código do aparelho, sempre há a quem atribuir
        id_aparelho, legado, id_usuario, dia = quem

        await self.repo.gravar_detalhes(
            id_aparelho=id_aparelho, co_plataforma=plataforma, detalhes=detalhes
        )
        detalhe = detalhe_do_espaco_para_guardar(
            total_kb=espaco_app_kb,
            detalhe=espaco_app,
            plataforma=plataforma,
            limites_mb=limites_mb,
        )
        versao = await self.repo.registrar_dia(
            id_aparelho=id_aparelho,
            dt_dia_local=dia,
            id_usuario=id_usuario,
            co_versao_app=versao_app,
            co_idioma=idioma,
            co_versao_so=versao_so,
            com_espaco=True,
            nu_espaco_app_kb=espaco_app_kb,
            js_espaco_app=detalhe,
        )
        await self.sessao.commit()
        return RegistroDoDia(id_aparelho, legado, dia, versao), detalhe is not None
