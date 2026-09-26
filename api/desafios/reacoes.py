"""As reacoes do quadro - palmas, uau, fogo, coracao e top (T077).

═══════════════════════════════════════════════════════════════════════════
⚠️ O VOCABULARIO VEM DO BANCO, E ⛔ NAO DE UM `Enum` EM PYTHON
═══════════════════════════════════════════════════════════════════════════

`tb903_tipo_reacao` e a dimensao, e ela existe **exatamente** para isto: o
RF-DES-226 diz que o simbolo viaja como **dado**. Um `Enum` aqui congelaria as
reacoes em codigo, e acrescentar uma sexta viraria um deploy do servidor - o que
contradiz a propria dimensao que a `0019` criou.

⚠️ **E ela e lida ATIVA**: o sentinela `desconhecido` (9999) esta la para
**receber** codigo desconhecido numa leitura, e ⛔ nunca para ser escolhido. Quem
mandar um codigo fora do catalogo ativo leva **400**, e ⛔ nao vira sentinela em
silencio.

═══════════════════════════════════════════════════════════════════════════
⚠️ UMA REACAO POR PESSOA, POR LINHA (RF-DES-072) - E ELA SE TROCA
═══════════════════════════════════════════════════════════════════════════

A garantia mora no banco (`un001_reacao UNIQUE (id_resolucao, id_usuario)`), e
⛔ nao numa checagem deste codigo: duas requisicoes simultaneas passariam pela
checagem, e so o banco as separa.

⚠️ **O conflito TROCA a reacao**, e ⛔ nao responde 409. Sem isso, o primeiro
toque seria definitivo para sempre - quem tocou em "palmas" sem querer ficaria
presa a ele, numa barra que o Design desenhou justamente para se escolher entre
cinco. ⛔ E **⛔ nao ha toggle no `POST`**: repetir o mesmo pedido deixa a reacao
onde ela ja estava, e ⛔ nunca a apaga. Desfazer e o `DELETE`, que e explicito.

⚠️ Isto ⛔ nao e preciosismo de verbo: e a licao do ingestor da `0006`, em que um
`ON CONFLICT DO NOTHING` descartava o segundo envio **em silencio**. Um pedido
repetido ⛔ nao pode desfazer o efeito do anterior - duplo toque acidental
existe, e rede que reenvia tambem.

═══════════════════════════════════════════════════════════════════════════
⚠️ REAGIR EXIGE CONTA, E ⛔ NINGUEM REAGE A SI MESMO
═══════════════════════════════════════════════════════════════════════════

RF-DES-084: sem identidade ⛔ nao ha como honrar *"uma por pessoa"*. O convidado
**ve** o quadro - ver e social; ter linha e reagir exigem identidade.

⚠️ **E a linha precisa APARECER EM PUBLICO.** Quem desligou a visibilidade sai do
quadro **inclusive no meio do dia** (RF-DES-077), e uma reacao gravada numa linha
que ninguem ve seria uma contagem invisivel - que reapareceria no dia em que a
pessoa voltasse a se mostrar. A regra e a **mesma** do quadro, e por isso ela
mora numa constante so (`CLAUSULA_APARECE_EM_PUBLICO`).
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.desafios.modelos_evento import (
    TB_REACAO,
    VW_DESAFIO_DIA,
    VW_REACAO,
    VW_RESOLUCAO,
    VW_TIPO_REACAO,
)
from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO
from api.nucleo.excecoes import ErroNaoEncontrado, ErroNegocio

# ═══════════════════════════════════════════════════════════════════════════
# 1. Os erros
# ═══════════════════════════════════════════════════════════════════════════


class ReacaoDesconhecida(ErroNegocio):
    """O codigo enviado ⛔ nao esta no catalogo **ativo**.

    ⚠️ **400, e ⛔ nao 404**: o que ⛔ nao existe e o *tipo*, e ⛔ nao o desafio -
    um 404 faria a tela dizer que o desafio sumiu.

    ⚠️ **E ⛔ nao vira o sentinela `desconhecido`.** Ele existe para uma LEITURA
    nao quebrar diante de codigo mais novo que o leitor; aceita-lo na escrita
    gravaria uma reacao que ninguem consegue desenhar.
    """

    def __init__(self, codigo_enviado: str) -> None:
        super().__init__(
            "Esta reacao nao existe: %s." % codigo_enviado,
            "reacao_desconhecida",
            status_http=400,
        )


class LinhaSemResolucao(ErroNaoEncontrado):
    """⛔ ⛔ Nao ha linha publica daquela pessoa neste desafio.

    ⚠️ **Cobre DOIS casos de proposito**, e ⛔ nao os separa: a pessoa ⛔ nao
    resolveu, ou ela se escondeu do quadro (RF-DES-077). Distinguir os dois
    contaria a quem pergunta que fulano **existe e se escondeu** - e a
    visibilidade desligada deixaria de esconder.
    """

    def __init__(self) -> None:
        super().__init__(
            "Esta linha nao esta no quadro deste desafio.",
            "linha_nao_encontrada",
        )


class ReagirASiMesmo(ErroNegocio):
    """⛔ A propria linha ⛔ nao recebe reacao.

    ⚠️ O quadro ja diz isso em `pode_reagir: false` - esta guarda e a segunda, e
    ⛔ ela ⛔ nao e redundante: `pode_reagir` e desenho de tela, e quem fala com a
    rota ⛔ nao passa obrigatoriamente por ela.
    """

    def __init__(self) -> None:
        super().__init__(
            "Voce nao pode reagir a propria linha.",
            "reacao_a_si_mesmo",
            status_http=400,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 2. As consultas
# ═══════════════════════════════════════════════════════════════════════════

#: O tipo pelo codigo - **so os ativos**.
SQL_TIPO_ATIVO = f"""
SELECT nu_tipo_reacao
  FROM {VW_TIPO_REACAO}
 WHERE co_tipo_reacao = :co_tipo_reacao
   AND ic_ativo
"""

#: O dia publicado daquele desafio.
#:
#: ⚠️ **O desafio pode ter mais de um dia?** ⛔ Nao: `un002_desafio` garante que
#: um desafio e publicado **uma vez so** (a reprise e copia, com identificador
#: proprio). Por isso o `LIMIT 1` aqui ⛔ nao esconde ambiguidade nenhuma.
SQL_DIA_DO_DESAFIO = f"""
SELECT id_desafio_dia
  FROM {VW_DESAFIO_DIA}
 WHERE id_desafio = :id_desafio
 LIMIT 1
"""

#: A resolucao publica de uma pessoa naquele dia.
#:
#: ⚠️ **O filtro de visibilidade e o MESMO do quadro**, pela constante - ver o
#: cabecalho deste arquivo.
SQL_RESOLUCAO_PUBLICA = f"""
SELECT r.id_resolucao
  FROM {VW_RESOLUCAO} r
  JOIN conta.tb001_usuario u
    ON u.id_usuario = r.id_usuario
  LEFT JOIN progressao.tb001_progressao_usuario g
    ON g.id_usuario = r.id_usuario
 WHERE r.id_desafio_dia = :id_desafio_dia
   AND r.id_usuario = :id_jogador
   AND {CLAUSULA_APARECE_EM_PUBLICO}
"""

#: Grava a reacao - e **troca** a que houver.
#:
#: ⚠️ `DO UPDATE` com `dh_reacao` novo: a troca e um ato novo, e a notificacao do
#: dia seguinte (RF-DES-074a) agrega por **pessoa**, ⛔ nao por toque.
SQL_REAGIR = f"""
INSERT INTO {TB_REACAO} (id_resolucao, id_usuario, nu_tipo_reacao, dh_reacao)
VALUES (:id_resolucao, :id_usuario, :nu_tipo_reacao, :dh_reacao)
ON CONFLICT (id_resolucao, id_usuario) DO UPDATE
   SET nu_tipo_reacao = EXCLUDED.nu_tipo_reacao,
       dh_reacao      = EXCLUDED.dh_reacao
"""

#: Desfaz.
#:
#: ⚠️ **Ele ⛔ nao reclama de nao achar nada.** Desfazer duas vezes deixa a linha
#: sem reacao das duas vezes, que e o que a pessoa queria - um 404 no segundo
#: toque so serviria para a tela ter de trata-lo.
SQL_DESFAZER = f"""
DELETE FROM {TB_REACAO}
 WHERE id_resolucao = :id_resolucao
   AND id_usuario = :id_usuario
"""

#: A contagem daquela linha, por tipo. ⛔ **Zero ⛔ nao aparece** (RF-DES-073): o
#: tipo sem nenhuma reacao simplesmente ⛔ nao volta.
SQL_CONTAGEM_DA_LINHA = f"""
SELECT co_tipo_reacao, COUNT(*) AS qt
  FROM {VW_REACAO}
 WHERE id_resolucao = :id_resolucao
 GROUP BY co_tipo_reacao
"""

#: Qual e a **minha** reacao naquela linha.
SQL_MINHA_NA_LINHA = f"""
SELECT co_tipo_reacao
  FROM {VW_REACAO}
 WHERE id_resolucao = :id_resolucao
   AND id_usuario = :id_usuario
"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. O repositorio
# ═══════════════════════════════════════════════════════════════════════════


class RepositorioReacao:
    """As idas ao banco da reacao. ⛔ ⛔ Nao decide nada - quem decide e o servico."""

    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def tipo_ativo(self, co_tipo_reacao: str) -> Optional[int]:
        """O `nu_tipo_reacao` daquele codigo, ou `None` se ele ⛔ nao for ativo."""
        resultado = await self.sessao.execute(
            text(SQL_TIPO_ATIVO), {"co_tipo_reacao": co_tipo_reacao}
        )
        linha = resultado.mappings().first()
        return None if linha is None else int(linha["nu_tipo_reacao"])

    async def dia_do_desafio(self, id_desafio: UUID) -> Optional[UUID]:
        """O `id_desafio_dia`, ou `None` se aquele desafio ⛔ nao foi publicado."""
        resultado = await self.sessao.execute(
            text(SQL_DIA_DO_DESAFIO), {"id_desafio": id_desafio}
        )
        linha = resultado.mappings().first()
        return None if linha is None else linha["id_desafio_dia"]

    async def resolucao_publica(
        self, id_desafio_dia: UUID, id_jogador: UUID
    ) -> Optional[UUID]:
        """A resolucao **publica** daquela pessoa naquele dia."""
        resultado = await self.sessao.execute(
            text(SQL_RESOLUCAO_PUBLICA),
            {"id_desafio_dia": id_desafio_dia, "id_jogador": id_jogador},
        )
        linha = resultado.mappings().first()
        return None if linha is None else linha["id_resolucao"]

    async def reagir(
        self,
        id_resolucao: UUID,
        id_usuario: UUID,
        nu_tipo_reacao: int,
        dh_reacao: Any,
    ) -> None:
        """Grava - ou **troca** - a reacao daquela pessoa naquela linha."""
        await self.sessao.execute(
            text(SQL_REAGIR),
            {
                "id_resolucao": id_resolucao,
                "id_usuario": id_usuario,
                "nu_tipo_reacao": nu_tipo_reacao,
                "dh_reacao": dh_reacao,
            },
        )

    async def desfazer(self, id_resolucao: UUID, id_usuario: UUID) -> None:
        """Tira a minha reacao daquela linha, se houver."""
        await self.sessao.execute(
            text(SQL_DESFAZER),
            {"id_resolucao": id_resolucao, "id_usuario": id_usuario},
        )

    async def contagem(self, id_resolucao: UUID) -> dict[str, int]:
        """`{tipo: quantas}` - ⛔ **sem os que tem zero**."""
        resultado = await self.sessao.execute(
            text(SQL_CONTAGEM_DA_LINHA), {"id_resolucao": id_resolucao}
        )
        return {
            linha["co_tipo_reacao"]: int(linha["qt"])
            for linha in resultado.mappings().all()
        }

    async def minha(self, id_resolucao: UUID, id_usuario: UUID) -> Optional[str]:
        """O codigo da **minha** reacao naquela linha, ou `None`."""
        resultado = await self.sessao.execute(
            text(SQL_MINHA_NA_LINHA),
            {"id_resolucao": id_resolucao, "id_usuario": id_usuario},
        )
        linha = resultado.mappings().first()
        return None if linha is None else linha["co_tipo_reacao"]

    async def confirmar(self) -> None:
        """Fecha a transacao — chamada pelo servico, nunca daqui de dentro.

        ⚠️ **Sem ela, a reacao ⛔ ficava gravada** (relato do dono, 26/09/2026:
        *"as reacoes nao estao ficando salvas"*). A sessao da requisicao
        (`obter_sessao`) ⛔ confirma sozinha: ao fechar, ela DESFAZ o que ⛔ foi
        confirmado. E a resposta enganava - a contagem nova era lida DENTRO da
        mesma transacao, entao a tela recebia *"fogo: 1"* de uma gravacao que
        sumia no instante seguinte. O banco `des` tinha zero reacoes.
        """
        await self.sessao.commit()


# ═══════════════════════════════════════════════════════════════════════════
# 4. O servico
# ═══════════════════════════════════════════════════════════════════════════


class ServicoReacao:
    """Reagir e desfazer - as duas metades da barra de reacoes do quadro."""

    def __init__(self, repo: RepositorioReacao) -> None:
        self.repo = repo

    async def reagir(
        self,
        *,
        id_desafio: UUID,
        id_usuario: UUID,
        id_jogador: UUID,
        co_tipo_reacao: str,
        agora: Any,
    ) -> dict[str, Any]:
        """Poe - ou troca - a minha reacao na linha daquela pessoa.

        Args:
            id_desafio: qual desafio.
            id_usuario: quem esta reagindo (exige conta - RF-DES-084).
            id_jogador: de quem e a linha. ⚠️ E o campo `id` da linha do quadro,
                que e o **`id_usuario`** daquela pessoa - o `id_resolucao` ⛔ nao
                viaja ate o aplicativo, e ⛔ nao precisa.
            co_tipo_reacao: o codigo do catalogo (`palmas`, `fogo`, ...).
            agora: o instante do servidor.

        Returns:
            O corpo da resposta: a contagem **nova** daquela linha e qual e a
            minha reacao agora.

        ⚠️ **A contagem volta na resposta de proposito.** Com um `204`, a tela
        teria de somar 1 no que ela ja tinha - e erraria na troca (em que o total
        ⛔ nao muda) e sempre que outra pessoa tivesse reagido nesse meio-tempo.
        Quem sabe a contagem e quem a guarda.
        """
        id_resolucao, nu_tipo = await self._preparar(
            id_desafio=id_desafio,
            id_usuario=id_usuario,
            id_jogador=id_jogador,
            co_tipo_reacao=co_tipo_reacao,
        )
        await self.repo.reagir(
            id_resolucao=id_resolucao,
            id_usuario=id_usuario,
            nu_tipo_reacao=nu_tipo,
            dh_reacao=agora,
        )
        # ⚠️ **Confirma ANTES de montar a resposta**: a contagem que volta tem
        # de ser a que o proximo `GET .../quadro` vai ler - e ⛔ uma leitura de
        # dentro de uma transacao que ainda pode ser desfeita.
        await self.repo.confirmar()
        return await self._corpo(id_resolucao, id_usuario)

    async def desfazer(
        self, *, id_desafio: UUID, id_usuario: UUID, id_jogador: UUID
    ) -> dict[str, Any]:
        """Tira a minha reacao daquela linha.

        ⚠️ **⛔ Nao reclama se ⛔ nao havia nenhuma** - ver `SQL_DESFAZER`.
        """
        id_resolucao, _ = await self._preparar(
            id_desafio=id_desafio,
            id_usuario=id_usuario,
            id_jogador=id_jogador,
            co_tipo_reacao=None,
        )
        await self.repo.desfazer(id_resolucao=id_resolucao, id_usuario=id_usuario)
        # O mesmo `commit` de [reagir]: sem ele, desfazer tambem ⛔ ficava.
        await self.repo.confirmar()
        return await self._corpo(id_resolucao, id_usuario)

    async def _preparar(
        self,
        *,
        id_desafio: UUID,
        id_usuario: UUID,
        id_jogador: UUID,
        co_tipo_reacao: Optional[str],
    ) -> tuple[UUID, int]:
        """As guardas que valem para os dois verbos, na mesma ordem.

        ⚠️ **A ordem importa**: o tipo e conferido **antes** de qualquer ida ao
        desafio, para que um codigo invalido responda `400` e ⛔ nao `404` -
        dizer *"nao encontrado"* a quem digitou um tipo errado mandaria a tela
        investigar o desafio.
        """
        nu_tipo = 0
        if co_tipo_reacao is not None:
            achado = await self.repo.tipo_ativo(co_tipo_reacao)
            if achado is None:
                raise ReacaoDesconhecida(co_tipo_reacao)
            nu_tipo = achado

        # ⛔ Ninguem reage a si mesmo - e a checagem ⛔ nao custa ida ao banco.
        if id_jogador == id_usuario:
            raise ReagirASiMesmo()

        id_desafio_dia = await self.repo.dia_do_desafio(id_desafio)
        if id_desafio_dia is None:
            raise ErroNaoEncontrado("Desafio nao encontrado.", "desafio_inexistente")

        id_resolucao = await self.repo.resolucao_publica(id_desafio_dia, id_jogador)
        if id_resolucao is None:
            raise LinhaSemResolucao()
        return id_resolucao, nu_tipo

    async def _corpo(self, id_resolucao: UUID, id_usuario: UUID) -> dict[str, Any]:
        """A contagem nova daquela linha, no mesmo formato do quadro.

        ⛔ **Zero ⛔ nao e servido** (RF-DES-073): sem nenhuma reacao, `reacoes`
        vem `null` - e ⛔ nao `{}`. E a mesma forma que `GET .../quadro` usa, para
        a tela ⛔ nao ter dois jeitos de ler a mesma coisa.
        """
        contagem = await self.repo.contagem(id_resolucao)
        return {
            "reacoes": contagem or None,
            "minha_reacao": await self.repo.minha(id_resolucao, id_usuario),
        }
