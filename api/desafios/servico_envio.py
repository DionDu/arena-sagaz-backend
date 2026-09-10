"""AS REGRAS DO ENVIO — o que e aceito, o que e segurado e o que e rejeitado (T043).

═══════════════════════════════════════════════════════════════════════════
TRES DESFECHOS, E CONFUNDI-LOS CUSTA COISAS DIFERENTES
═══════════════════════════════════════════════════════════════════════════

| desfecho | quando | o que o aplicativo faz |
|---|---|---|
| **aceita** | tudo no lugar | tira do outbox |
| **segura** (409) | a **partida ainda nao chegou** | ⚠️ tenta de novo depois |
| **rejeita** (400) | **dado impossivel** | tira do outbox e registra |

⚠️ **Segurar nao e rejeitar**, e essa e a linha mais importante do contrato: os
dois eventos saem do **mesmo outbox**, e chegar fora de ordem e uma corrida de
rede rotineira. Rejeitar ali transformaria uma corrida de rede em **perda de
XP** — e a pessoa que viu *"resolvido!"* nunca saberia por que nao entrou no
quadro.

═══════════════════════════════════════════════════════════════════════════
⛔ REJEITAR E "DADO IMPOSSIVEL", E NUNCA "DISCORDO DO JULGAMENTO"
═══════════════════════════════════════════════════════════════════════════

RF-DES-033 lista o que e rejeitado: desafio inexistente, resposta a um desafio de
**outro dia**, `pontuacao` fora de 18–30, `qualidade` fora de [0,1], chave de
feito fora do catalogo. ⛔ Nada disso e opiniao sobre a partida.

**Se o servidor discordar do aplicativo, vale o aplicativo** (RF-DES-032, D-05):
a pessoa entra no quadro, e a divergencia vira alerta no painel (T040), escrita
pelo avaliador (T043a) — que roda **fora do caminho da requisicao** (RF-DES-036).

═══════════════════════════════════════════════════════════════════════════
⚠️ PARTIDA `em_andamento` E ACEITA — E ISSO NAO CONTRADIZ RF-DES-187
═══════════════════════════════════════════════════════════════════════════

Quando a linha de chegada cai **antes** do fim, o desafio fecha no objetivo e a
pessoa pode continuar jogando: a resolucao sobe com a partida ainda
`em_andamento`, e o resto dos lances sobe quando ela acabar (RF-DES-213/214).

RF-DES-187 — *"toda partida de desafio esta fechada"* — e sobre o **estado
final**, e quem o garante sao o ingestor com `DO UPDATE` (T045) e o **job de
expiracao de 7 dias** (T046), nao uma recusa aqui. Recusar seria tirar o XP
exatamente de quem parou no objetivo, que e o comportamento que a spec descreve
como esperado.

⛔ O que **nao** existe sem partida fechada e o **replay** (T044) — e aquela rota,
sim, exige estado terminal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from api.desafios.extrato_xp import MedidaInvalida, montar_extrato
from api.desafios.modelos_envio import (
    EnvioDeDica,
    EnvioDeResolucao,
    RespostaDeResolucao,
)
from api.desafios.repositorio_envio import RepositorioEnvio
from api.nucleo.excecoes import ErroConflito, ErroNegocio

#: O teto de dicas por **desafio** (RF-DES-057).
TETO_DE_DICAS = 2


class PartidaAindaNaoChegou(ErroConflito):
    """A resolucao chegou antes da partida dela.

    ⚠️ **409, e nao 400.** O outbox do aplicativo trata `409` como *"tente de
    novo"* e `400` como *"desista e registre"*. Trocar os dois faria a pessoa
    perder o XP por uma corrida de rede.
    """

    def __init__(self, co_evento: str) -> None:
        super().__init__(
            f"A partida {co_evento} ainda nao chegou. A resolucao esta segurada; "
            "reenvie depois do log de partida.",
            "partida_ainda_nao_chegou",
        )


@dataclass(frozen=True, slots=True)
class ResultadoDoEnvio:
    """O que foi gravado, para o log e para a resposta."""

    resposta: RespostaDeResolucao
    id_tentativa: UUID
    parcelas_gravadas: int


class ServicoEnvio:
    """Recebe o que o aplicativo mandou e o transforma em linhas do evento."""

    def __init__(self, repo: RepositorioEnvio) -> None:
        self.repo = repo

    async def registrar_resolucao(
        self, *, id_desafio: UUID, id_usuario: str, envio: EnvioDeResolucao
    ) -> ResultadoDoEnvio:
        """Grava tentativa, resolucao e extrato — tudo numa transacao.

        Raises:
            PartidaAindaNaoChegou: 409, e o aplicativo reenvia.
            ErroNegocio: 400, dado impossivel (RF-DES-033).
        """
        dia = await self.repo.dia_do_desafio(
            id_desafio_dia=envio.id_desafio_dia, id_desafio=id_desafio
        )
        if dia is None:
            # ⚠️ **Uma mensagem para os dois casos**: o dia nao existe, ou existe
            # e pertence a outro desafio. Sao a mesma coisa do ponto de vista de
            # quem enviou — e distinguir contaria qual dos dois identificadores
            # e valido.
            raise ErroNegocio(
                "Desafio ou dia inexistente, ou resposta a um desafio de outro "
                "dia.",
                "vinculo_invalido",
                status_http=400,
            )

        partida = await self.repo.partida_por_evento(
            co_evento=envio.co_evento_partida, id_usuario=id_usuario
        )
        if partida is None:
            raise PartidaAindaNaoChegou(envio.co_evento_partida)

        if partida["co_modo"] != "desafio":
            # ⚠️ **A resolucao E uma partida de desafio** (RF-DES-186). Uma
            # partida comum apontada aqui poria no quadro uma partida que nunca
            # foi jogada contra este desafio — e o replay mostraria outra coisa.
            raise ErroNegocio(
                f"A partida {envio.co_evento_partida} foi gravada como "
                f"co_modo={partida['co_modo']!r}, e uma resolucao so aponta para "
                "co_modo='desafio'.",
                "partida_nao_e_de_desafio",
                status_http=400,
            )

        resolveu = envio.veredito == "resolvido"
        id_tentativa, _ = await self.repo.gravar_tentativa(
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_partida=partida["id_partida"],
            ic_resolveu=resolveu,
            nu_tempo_ms=envio.tempo_ms,
            dh_inicio=partida["dh_inicio"],
            # ⚠️ Partida em andamento nao tem `dh_fim`; a tentativa tem de ter
            # (a coluna e `NOT NULL`). O instante da resolucao e o fim **desta
            # tentativa** — a partida continua, o desafio nao.
            dh_fim=partida["dh_fim"] or envio.resolvido_em,
        )

        if not resolveu:
            # ⚠️ **Tentativa que falhou nao vira resolucao, e nao entra no
            # quadro** (RF-DES-062): falhar e privado. A linha existe no banco
            # porque e ela que conta as tentativas para `Q`.
            await self.repo.confirmar()
            return ResultadoDoEnvio(
                resposta=RespostaDeResolucao(aceita=True),
                id_tentativa=id_tentativa,
                parcelas_gravadas=0,
            )

        id_resolucao, nova = await self.repo.gravar_resolucao(
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_tentativa=id_tentativa,
            nu_lance=envio.nu_lance_cumpre_desafio,
            nu_xp=envio.pontuacao,
            nu_versao_catalogo=envio.versao_catalogo_feitos,
            dh_resolucao=envio.resolvido_em,
        )

        if not nova:
            # ⛔ **Reenviar nao regrava o extrato.** `tb004_xp_desafio` nao tem
            # chave natural, entao a protecao contra duplicata mora aqui — e sem
            # ela o Raio-X mostraria cada parcela duas vezes.
            await self.repo.confirmar()
            return ResultadoDoEnvio(
                resposta=RespostaDeResolucao(
                    id_resolucao=id_resolucao, aceita=True, ja_existia=True
                ),
                id_tentativa=id_tentativa,
                parcelas_gravadas=0,
            )

        parcelas = await self._extrato(id_desafio=id_desafio, envio=envio)
        await self.repo.gravar_extrato(
            parcelas,
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_resolucao=id_resolucao,
            id_tentativa=id_tentativa,
        )
        await self.repo.confirmar()

        return ResultadoDoEnvio(
            resposta=RespostaDeResolucao(
                id_resolucao=id_resolucao, aceita=True, ja_existia=False
            ),
            id_tentativa=id_tentativa,
            parcelas_gravadas=len(parcelas),
        )

    async def _extrato(self, *, id_desafio: UUID, envio: EnvioDeResolucao):
        """Converte as medidas nas parcelas do extrato.

        Raises:
            ErroNegocio: chave de feito fora do catalogo, ou normalizacao
                impossivel (RF-DES-033).
        """
        pesos = await self.repo.pesos_do_desafio(id_desafio)
        conhecidas = {linha["co_feito"] for linha in pesos}
        medidas = {f.chave: Decimal(str(f.valor)) for f in envio.feitos}

        # ⚠️ A conferencia e contra o catalogo **daquele desafio**, e nao contra a
        # dimensao inteira: uma chave que existe no catalogo mas nao pesa neste
        # desafio nao e invencao — e so uma medida que este desafio nao usa.
        # O que se recusa e a chave que nao existe em lugar nenhum.
        desconhecidas = [
            chave
            for chave in medidas
            if chave not in conhecidas
            and not await self.repo.existe_no_catalogo(chave)
        ]
        if desconhecidas:
            raise ErroNegocio(
                f"Chave(s) de feito fora do catalogo: {', '.join(desconhecidas)}. "
                "⛔ Uma chave inventada faria Q ordenar pessoas por medidas de "
                "significados diferentes.",
                "feito_desconhecido",
                status_http=400,
            )

        try:
            return montar_extrato(medidas=medidas, pesos=pesos)
        except MedidaInvalida as erro:
            raise ErroNegocio(str(erro), "medida_invalida", status_http=400) from erro

    async def registrar_dica(
        self, *, id_desafio: UUID, id_usuario: str, envio: EnvioDeDica
    ) -> bool:
        """Registra que a 1a ou a 2a dica foi gasta.

        Returns:
            `True` quando a linha e nova.

        Raises:
            PartidaAindaNaoChegou: a partida da tentativa ainda nao subiu.
            ErroNegocio: vinculo invalido, ou teto de dicas estourado.

        ⚠️ **O teto e por DESAFIO** (RF-DES-057), e a conta soma as tentativas do
        dia: fechar o aplicativo encerra a tentativa, nao o dia.
        """
        dia = await self.repo.dia_do_desafio(
            id_desafio_dia=envio.id_desafio_dia, id_desafio=id_desafio
        )
        if dia is None:
            raise ErroNegocio(
                "Desafio ou dia inexistente.", "vinculo_invalido", status_http=400
            )

        partida = await self.repo.partida_por_evento(
            co_evento=envio.co_evento_partida, id_usuario=id_usuario
        )
        if partida is None:
            raise PartidaAindaNaoChegou(envio.co_evento_partida)

        gastas = await self.repo.dicas_ja_gastas(
            id_desafio_dia=envio.id_desafio_dia, id_usuario=id_usuario
        )
        if gastas >= TETO_DE_DICAS:
            raise ErroNegocio(
                f"O teto de {TETO_DE_DICAS} dicas por desafio ja foi atingido.",
                "teto_de_dicas",
                status_http=409,
            )

        id_tentativa, _ = await self.repo.gravar_tentativa(
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_partida=partida["id_partida"],
            # ⚠️ A dica chega **durante** a partida, e a essa altura ninguem
            # resolveu nada ainda. A tentativa nasce `ic_resolveu = FALSE`, e o
            # envio da resolucao nao a recria — ele reencontra esta mesma linha
            # pelo `id_partida UNIQUE`.
            ic_resolveu=False,
            nu_tempo_ms=0,
            dh_inicio=partida["dh_inicio"],
            dh_fim=partida["dh_fim"] or envio.consumida_em,
        )

        nova = await self.repo.gravar_dica(
            id_tentativa=id_tentativa,
            nu_grau=envio.grau,
            dh_consumo=envio.consumida_em,
        )
        await self.repo.confirmar()
        return nova
