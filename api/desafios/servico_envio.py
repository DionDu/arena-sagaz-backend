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

**Se o servidor discordar do aplicativo sobre o VEREDITO, vale o aplicativo**
(RF-DES-032, D-05): a pessoa entra no quadro, e a divergencia vira alerta no
painel (T040), escrita pelo avaliador (T043a) — que roda **fora do caminho da
requisicao** (RF-DES-036).

⚠️ **O NUMERO e do servidor desde 10/10/2026** (T103, `DECISOES-do-dono.md`
§8zzo, decisao 7): o XP do desafio e calculado aqui, com a regua da nota do dia
(`regua_da_nota.py`), e a pontuacao que o aplicativo manda e so uma estimativa -
a diferenca vai para o log, sem recusar nada.

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

⚠️ Ate 25/09/2026 o **replay** (T044) exigia estado terminal. Desde a T085f
(`DECISOES-do-dono.md` §8w.1) nem ele exige: a partida deixada aberta mostra os
lances que subiram, que terminam no objetivo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from api.desafios.credito_do_dia import credito_do_dia
from api.desafios.extrato_xp import (
    MedidaInvalida,
    ParcelaDeXp,
    montar_extrato,
    pontuacao_do_extrato,
)
from api.desafios.modelos_envio import (
    EnvioDeDica,
    EnvioDeResolucao,
    RespostaDeResolucao,
)
from api.desafios.modelos_evento import (
    XP_AJUSTE,
    XP_CONSOLO,
    XP_DA_TENTATIVA_SEM_RESOLVER,
)
from api.desafios.regua_da_nota import (
    ReguaDaNota,
    regua_vigente,
    reguas_das_linhas,
)
from api.desafios.repositorio_envio import RepositorioEnvio
from api.desafios.retrato import retrato_da_resolucao
from api.nucleo.excecoes import ErroConflito, ErroNegocio

#: O teto de dicas por **TENTATIVA** - o botao (`DECISOES-do-dono.md` §8zzo,
#: decisao 1, 10/10/2026). Era por desafio (RF-DES-057) ate ali.
TETO_DE_DICAS_POR_TENTATIVA = 2

#: ⚠️ **O `TETO_DE_DICAS` da NOTA saiu em 10/10/2026 (T103)**: ele prendia em 2
#: o total do dia enquanto a parcela de dica nao aceitava mais que isso. A regua
#: do banco nao tem teto, e a nota conta todas as dicas do dia (§8zzo, decisao 2).

#: O log da divergencia entre a estimativa do aplicativo e o XP do servidor.
log = logging.getLogger(__name__)


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
    """O que foi gravado, para o log e para a resposta.

    ⚠️ `xp_creditado` e o que entrou em `nu_xp_total` **por este envio** (T082):
    zero no reenvio, zero na segunda falha do dia, e o valor ja cortado pelo
    teto quando o dia enche. Nao vai na resposta: o que vai e a PONTUACAO da
    resolucao (`resposta.pontuacao`, T105).

    ⛔ **Sem valor padrao**, de proposito: um `= 0` faria o caminho novo que
    esquecesse de creditar compilar e passar nos testes que nao olham o XP.
    """

    resposta: RespostaDeResolucao
    id_tentativa: UUID
    parcelas_gravadas: int
    xp_creditado: int


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
            #
            # ⚠️ **Mas ela paga o consolo** (RF-DES-041, T082) - uma vez por
            # dia, e so a primeira que chegar.
            creditado = await self._creditar_o_consolo(
                id_desafio_dia=envio.id_desafio_dia,
                id_usuario=id_usuario,
                id_tentativa=id_tentativa,
            )
            await self.repo.confirmar()
            return ResultadoDoEnvio(
                resposta=RespostaDeResolucao(aceita=True),
                id_tentativa=id_tentativa,
                parcelas_gravadas=0,
                xp_creditado=creditado,
            )

        # ⚠️ **A SESSAO QUE VALE e a MAIOR entre a do aplicativo e a do servidor**
        # (T085zf, `DECISOES-do-dono.md` §8zf). O aplicativo conta o que ELE viu;
        # o convidado comeca o dia do zero no aparelho, e quem errou tres vezes
        # com a conta e resolveu como convidado chegaria aqui "de primeira". O
        # servidor viu as tres. ⛔ A menor nunca vence: o servidor pode nao ter
        # recebido tudo ainda (a fila de outro aparelho), e o aplicativo sabe.
        tentativas, dicas = await self._sessao_que_vale(
            envio=envio, id_usuario=id_usuario, id_tentativa=id_tentativa
        )

        # ⚠️ **O extrato e a pontuacao saem ANTES de gravar a resolucao** (T103):
        # o `nu_xp` gravado e a soma deste extrato, calculada aqui com a regua
        # do dia do desafio - e nao mais a pontuacao do aplicativo. Montar antes
        # tambem faz um feito invalido (400) recusar o envio sem deixar nada
        # gravado pela metade.
        parcelas = await self._extrato(
            id_desafio=id_desafio,
            dt_dia=dia["dt_dia"],
            envio=envio,
            tentativas=tentativas,
            dicas=dicas,
        )
        pontuacao = pontuacao_do_extrato(parcelas)
        self._registrar_divergencia(
            envio=envio, pontuacao=pontuacao, tentativas=tentativas, dicas=dicas
        )

        # ⚠️ **Lido ANTES de gravar a resolucao**: depois dela, a soma do dia ja a
        # incluiria, e a resolucao seria descontada dela mesma.
        ja_creditado, _ = await self.repo.creditado_no_dia(
            id_desafio_dia=envio.id_desafio_dia, id_usuario=id_usuario
        )

        id_resolucao, nova = await self.repo.gravar_resolucao(
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_tentativa=id_tentativa,
            nu_lance=envio.nu_lance_cumpre_desafio,
            nu_xp=pontuacao,
            nu_versao_catalogo=envio.versao_catalogo_feitos,
            dh_resolucao=envio.resolvido_em,
            # O retrato para a frase do cartao (T085za): TODAS as medidas do
            # tabuleiro, e ⛔ so as que pesam - essas vao para o extrato abaixo.
            js_feito=retrato_da_resolucao(envio.feitos, envio.janela_gasta),
        )

        if not nova:
            # ⛔ **Reenviar nao regrava o extrato.** `tb004_xp_desafio` nao tem
            # chave natural, entao a protecao contra duplicata mora aqui — e sem
            # ela o Raio-X mostraria cada parcela duas vezes.
            #
            # ⚠️ **A resposta leva o XP GRAVADO, e nao o recalculado** (T105): a
            # primeira resolucao e definitiva (RF-DES-004a), e o reenvio pode ter
            # chegado depois de a sessao do servidor ter mudado.
            gravado = await self.repo.xp_da_resolucao(id_resolucao=id_resolucao)
            await self.repo.confirmar()
            return ResultadoDoEnvio(
                resposta=RespostaDeResolucao(
                    id_resolucao=id_resolucao,
                    aceita=True,
                    ja_existia=True,
                    pontuacao=gravado,
                ),
                id_tentativa=id_tentativa,
                parcelas_gravadas=0,
                # ⛔ O reenvio nao credita: a resolucao ja creditou quando nasceu.
                xp_creditado=0,
            )

        await self.repo.gravar_extrato(
            parcelas,
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_resolucao=id_resolucao,
            id_tentativa=id_tentativa,
        )
        # ⚠️ **Credita a PONTUACAO**: o mesmo `nu_xp` que acabou de ser gravado
        # na resolucao - o inteiro da soma do extrato, calculado aqui (T103).
        creditado = await self._creditar(
            valor=pontuacao,
            ja_creditado=ja_creditado,
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
        )
        await self.repo.confirmar()

        return ResultadoDoEnvio(
            resposta=RespostaDeResolucao(
                id_resolucao=id_resolucao,
                aceita=True,
                ja_existia=False,
                pontuacao=pontuacao,
            ),
            id_tentativa=id_tentativa,
            parcelas_gravadas=len(parcelas),
            xp_creditado=creditado,
        )

    async def _creditar_o_consolo(
        self, *, id_desafio_dia: UUID, id_usuario: str, id_tentativa: UUID
    ) -> int:
        """O consolo de quem tentou e nao resolveu - uma vez por dia (RF-DES-041).

        Returns:
            O que entrou na conta: 10 quando ele e o primeiro evento do dia;
            zero quando o consolo do dia ja estava la, ou quando a resolucao
            chegou antes (o consolo e piso, e nao soma - DECISOES-do-dono
            §8zp, no frontend).

        ⚠️ **"Ja existe consolo hoje?" e a guarda, e ⛔ "esta tentativa e nova?"**:
        `gravar_tentativa` devolve `escreveu=True` tambem quando o reenvio
        atualiza uma tentativa nao resolvida, entao ele nao separa o primeiro
        envio do segundo. O consolo do dia separa - e ainda cobre a segunda
        falha, que tambem ⛔ paga.
        """
        ja_creditado, tem_consolo = await self.repo.creditado_no_dia(
            id_desafio_dia=id_desafio_dia, id_usuario=id_usuario
        )
        if tem_consolo:
            return 0
        # ⚠️ Ancorado na TENTATIVA, que e o que o `data-model.md` manda: o
        # consolo e de uma tentativa, e ⛔ de uma resolucao que nao existe.
        await self.repo.gravar_extrato(
            [
                ParcelaDeXp(
                    nu_tipo_xp=XP_CONSOLO,
                    nu_feito=None,
                    vr_medida=None,
                    vr_normalizado=None,
                    vr_peso=None,
                    vr_xp=Decimal(XP_DA_TENTATIVA_SEM_RESOLVER),
                )
            ],
            id_desafio_dia=id_desafio_dia,
            id_usuario=id_usuario,
            id_resolucao=None,
            id_tentativa=id_tentativa,
        )
        return await self._creditar(
            valor=XP_DA_TENTATIVA_SEM_RESOLVER,
            ja_creditado=ja_creditado,
            id_desafio_dia=id_desafio_dia,
            id_usuario=id_usuario,
        )

    async def _creditar(
        self, *, valor: int, ja_creditado: int, id_desafio_dia: UUID, id_usuario: str
    ) -> int:
        """Credita o que falta para o dia chegar a [valor], grava o ajuste do
        resto, e soma na conta.

        ⚠️ **O dia vale o MAIOR evento** (consolo de 10 ou pontuacao de 12 a
        30), e nunca a soma - ver `credito_do_dia.py`.

        Returns:
            O que entrou em `nu_xp_total`.

        ⚠️ **O ajuste nao tem ancora** (`id_resolucao` e `id_tentativa` nulos):
        ele e do DIA, e ⛔ de um evento - e o `data-model.md` que manda, e e o que
        deixa a soma do dia fechar no mesmo numero venha o consolo antes ou
        depois.
        """
        credito = credito_do_dia(ja_creditado=ja_creditado, valor=valor)
        if credito.corte > 0:
            await self.repo.gravar_extrato(
                [
                    ParcelaDeXp(
                        nu_tipo_xp=XP_AJUSTE,
                        nu_feito=None,
                        vr_medida=None,
                        vr_normalizado=None,
                        vr_peso=None,
                        # O sinal trocado: a linha TIRA o que passou do teto.
                        vr_xp=Decimal(-credito.corte),
                    )
                ],
                id_desafio_dia=id_desafio_dia,
                id_usuario=id_usuario,
                id_resolucao=None,
                id_tentativa=None,
            )
        await self.repo.creditar_na_conta(id_usuario=id_usuario, xp=credito.creditado)
        return credito.creditado

    async def _sessao_que_vale(
        self, *, envio: EnvioDeResolucao, id_usuario: str, id_tentativa: UUID
    ) -> tuple[int, int]:
        """`(tentativas, dicas)`: o MAIOR entre o do envio e o do servidor.

        ⚠️ **Sem teto nas dicas desde 10/10/2026** (T103): a nota conta todas as
        dicas do dia (§8zzo, decisao 2), e a regua do banco nao recusa nenhuma.
        Ate ali o total era preso em 2.
        """
        do_servidor = await self.repo.sessao_no_servidor(
            id_desafio_dia=envio.id_desafio_dia,
            id_usuario=id_usuario,
            id_tentativa=id_tentativa,
            ate=envio.resolvido_em,
        )
        tentativas = max(envio.tentativas, do_servidor[0])
        dicas = max(envio.dicas_usadas, do_servidor[1])
        return tentativas, dicas

    def _registrar_divergencia(
        self,
        *,
        envio: EnvioDeResolucao,
        pontuacao: int,
        tentativas: int,
        dicas: int,
    ) -> None:
        """Anota no log quando a estimativa do aplicativo nao bateu (T103).

        ⚠️ **Log, e nao `co_auditoria`**: aquela coluna e do avaliador de
        lances (`job/auditoria.py`), e diz se os LANCES cumprem o objetivo. Uma
        estimativa de XP diferente nao e suspeita de nada - acontece sempre que
        o aplicativo e o servidor viram sessoes diferentes (o convidado, dois
        aparelhos), ou quando o app ainda e a 1.3.0, com a regua antiga.
        ⛔ Nada e recusado: o numero do servidor vale, e a resposta o leva.
        """
        if pontuacao == envio.pontuacao:
            return
        log.info(
            "xp do desafio: estimativa do app %s, servidor %s "
            "(tentativas app %s/servidor %s, dicas app %s/servidor %s)",
            envio.pontuacao,
            pontuacao,
            envio.tentativas,
            tentativas,
            envio.dicas_usadas,
            dicas,
        )

    async def _regua_da_nota(self, dt_dia: date) -> ReguaDaNota:
        """A regua da nota que vale no dia do desafio (T103).

        ⚠️ **Pelo `dt_dia` do DESAFIO**, e nao pelo relogio: um reenvio atrasado
        de ontem e pontuado com a regua de ontem, como todos os outros daquele
        quadro.

        Raises:
            ReguaDaNotaInvalida: nenhuma versao vale nesse dia, ou a versao nao
                fecha em 1,000 - um 500, para a fila tentar de novo depois do
                conserto (⛔ um 400 descartaria a resolucao da pessoa).
        """
        linhas = await self.repo.linhas_das_reguas_da_nota()
        return regua_vigente(reguas_das_linhas(linhas), dt_dia)

    async def _regua(self, id_desafio: UUID) -> dict:
        """A regua de tempo do desafio - ou 400, ⛔ um padrao inventado."""
        # ⛔ **Sem valor padrao, nem aqui nem na leitura**: arbitrar 30 s/180 s
        # faria a auditoria conferir contra uma regua inventada e acusar
        # divergencia onde nao ha - e o alerta que ninguem le e pior que nenhum.
        regua = await self.repo.regua_de_tempo(id_desafio)
        if regua is None:
            raise ErroNegocio(
                "Desafio sem regua de tempo: sem ela a parcela de tempo de Q "
                "nao tem contra o que ser medida.",
                "regua_ausente",
                status_http=400,
            )
        return regua

    async def _extrato(
        self,
        *,
        id_desafio: UUID,
        dt_dia: date,
        envio: EnvioDeResolucao,
        tentativas: int,
        dicas: int,
    ) -> list[ParcelaDeXp]:
        """Converte as medidas e a sessao nas parcelas do extrato.

        Args:
            dt_dia: o dia UTC do desafio - escolhe a regua da nota.
            tentativas, dicas: a sessao que VALE ([_sessao_que_vale]) - e ⛔ a
                do envio: o Raio-X mostra as quatro tentativas que o servidor
                contou, e a parcela que desceu por elas.

        Raises:
            ErroNegocio: chave de feito fora do catalogo, normalizacao
                impossivel (RF-DES-033), ou a regua de tempo do desafio faltando.

        ⚠️ **As quatro parcelas de `Q` saem daqui** (RF-DES-042): o tempo vem
        do proprio envio; tentativas e dica, da sessao que vale (o envio, ou o
        servidor quando ele contou mais - T085zf); o merito, dos pesos; e os
        pesos e as curvas, da regua da nota do dia (T103).
        """
        pesos = await self.repo.pesos_do_desafio(id_desafio)
        conhecidas = {linha["co_feito"] for linha in pesos}
        medidas = {f.chave: Decimal(str(f.valor)) for f in envio.feitos}

        # ⚠️ A conferencia e contra o catalogo **daquele desafio**, e nao contra
        # a dimensao inteira: uma chave que existe no catalogo mas nao pesa neste
        # desafio nao e invencao - e so uma medida que este desafio nao usa.
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

        regua = await self._regua(id_desafio)
        regua_da_nota = await self._regua_da_nota(dt_dia)

        try:
            return montar_extrato(
                regua=regua_da_nota,
                medidas=medidas,
                pesos=pesos,
                nu_tentativas=tentativas,
                # ⚠️ O tempo **da resolucao**, que e o tempo ate o objetivo cair
                # e nao ate o fim da partida (RF-DES-214).
                nu_tempo_ms=envio.tempo_ms,
                nu_dicas=dicas,
                nu_tempo_piso_ms=regua["nu_tempo_piso_ms"],
                nu_tempo_teto_ms=regua["nu_tempo_teto_ms"],
                direcoes=await self.repo.direcoes_de_sessao(),
            )
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

        ⚠️ **O teto e por TENTATIVA desde 10/10/2026** (`DECISOES-do-dono.md`
        §8zzo, decisao 1): cada tentativa recomeca com as duas. Era por desafio
        (RF-DES-057), e quem errava depois de gastar as duas tinha de lembrar o
        que o app havia sugerido. O custo de pedir mais vai para a NOTA.

        ⚠️ **E a UNICA porta da `tb005`** (decisao do dono, 10/10/2026, §8zzo):
        o app envia cada dica para sincronizar, como o desenho original previa.
        A 1.3.0 desistia antes de enviar, porque o `co_evento` da partida so
        nascia na 1a leva; a 1.3.1 cria o `co_evento` no inicio da partida
        (T109), e a dica que chega antes da partida recebe 409 e volta depois.
        ⛔ O servidor nao reconstroi dica a partir de `qt_usos_poder`.
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

        # ⚠️ **A tentativa vem ANTES da conta**: o teto e dela, e e pelo
        # identificador dela que se conta. Se o teto estourar, o erro sobe sem
        # `confirmar()`, e a sessao desfaz a tentativa ao fechar.
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

        gastas = await self.repo.dicas_da_tentativa(id_tentativa=id_tentativa)
        if gastas >= TETO_DE_DICAS_POR_TENTATIVA:
            raise ErroNegocio(
                f"O teto de {TETO_DE_DICAS_POR_TENTATIVA} dicas por tentativa ja "
                "foi atingido.",
                "teto_de_dicas",
                status_http=409,
            )

        nova = await self.repo.gravar_dica(
            id_tentativa=id_tentativa,
            nu_grau=envio.grau,
            dh_consumo=envio.consumida_em,
        )
        await self.repo.confirmar()
        return nova
