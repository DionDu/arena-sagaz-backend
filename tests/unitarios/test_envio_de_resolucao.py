"""O ENVIO DA RESOLUCAO — T043 (contracts/envio-resolucao.md).

O que estes casos protegem:

  · ⚠️ **segurar nao e rejeitar** — a resolucao que chega antes da partida dela
    responde `409`, e o outbox reenvia. `400` ali transformaria uma corrida de
    rede em **perda de XP**;
  · **idempotencia pela chave natural** `(desafio, pessoa)` — e o reenvio ⛔ nao
    regrava o extrato;
  · ⚠️ **partida `em_andamento` e aceita** (RF-DES-213/214): quem para no
    objetivo nao perde o XP;
  · **as tres parcelas invertidas** — mais tempo, mais tentativas e mais dicas
    dao MENOS XP, e a direcao vem do catalogo;
  · **o teto de duas dicas e por TENTATIVA** (desde 10/10/2026, §8zzo);
  · ⚠️ **o XP do desafio e o do SERVIDOR** (T103, §8zzo decisao 7): calculado
    com a regua da nota vigente no dia do desafio, e devolvido na resposta
    (T105). A pontuacao do envio virou estimativa.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from api.desafios.credito_do_dia import credito_do_dia
from api.desafios.extrato_xp import (
    MedidaInvalida,
    ParcelaDeXp,
    montar_extrato,
    normalizar,
    pontuacao_do_extrato,
    qualidade_do_extrato,
    soma_dos_pesos,
)
from api.desafios.modelos_envio import (
    EnvioDeDica,
    EnvioDeResolucao,
    FeitoMedido,
    OrigemDoEnvio,
)
from api.desafios.modelos_evento import (
    XP_AJUSTE,
    XP_CONSOLO,
    XP_DA_TENTATIVA_SEM_RESOLVER,
    XP_DICA,
    XP_MEDIDA,
    XP_MERITO,
    XP_TEMPO,
    XP_TENTATIVAS,
)
from api.desafios.regua_da_nota import ReguaDaNotaInvalida
from api.desafios.servico_envio import (
    PartidaAindaNaoChegou,
    ServicoEnvio,
    TETO_DE_DICAS_POR_TENTATIVA,
)
from api.nucleo.excecoes import ErroNegocio
from tests.unitarios.reguas_de_teste import (
    LINHAS_DAS_REGUAS,
    REGUA_V1,
    REGUA_V2,
    VIGENCIA_V2,
)

AGORA = datetime(2026, 9, 10, 14, 23, 19, tzinfo=timezone.utc)
ID_DESAFIO = uuid4()
ID_DIA = uuid4()
ID_USUARIO = "uid-da-pessoa"


def _envio(**trocas) -> EnvioDeResolucao:
    """Um envio valido — cada caso estraga so o que quer testar."""
    base = dict(
        id_desafio_dia=ID_DIA,
        veredito="resolvido",
        tentativas=3,
        tempo_ms=48210,
        dicas_usadas=1,
        qualidade=0.7325,
        pontuacao=26,
        co_evento_partida="evento-7c3e",
        nu_lance_cumpre_desafio=14,
        feitos=[
            FeitoMedido(chave="damas_coroadas", valor=1),
            FeitoMedido(chave="tempo_ate_resolver", valor=48210),
            FeitoMedido(chave="tentativas", valor=3),
        ],
        versao_catalogo_feitos=1,
        resolvido_em=AGORA,
        origem=OrigemDoEnvio(tipo="conta"),
    )
    base.update(trocas)
    return EnvioDeResolucao(**base)


#: A regua de tempo usada nos casos do extrato.
#:
#: ⚠️ De proposito **nao** sao os 30 s/180 s do exemplo do `data-model.md`:
#: sao esses os numeros que alguem escreveria a mao se resolvesse arbitrar um
#: padrao, e um caso que os usasse passaria igual com a regua inventada.
PISO_MS = 12_000
TETO_MS = 95_000

#: A direcao das tres chaves de sessao, como a dimensao as declara.
#:
#: ⚠️ Elas vem do banco em producao (`tb902_catalogo_feito`), e nunca de um
#: literal no codigo: uma parcela na direcao errada **nao daria erro nenhum**, so
#: pagaria mais a quem jogou pior.
DIRECOES = {
    "tentativas": "menor_melhor",
    "tempo_ate_resolver": "menor_melhor",
    "dicas_usadas": "menor_melhor",
}


#: As duas versoes da regua da nota (as da `0030`, escritas a mao), em modulo
#: de apoio porque a publicacao usa as mesmas.


def _extrato(*, medidas=None, pesos=None, **trocas):
    """`montar_extrato` com a sessao ja preenchida na MELHOR resolucao.

    Primeira tentativa, no piso do tempo, sem dica: assim cada caso piora so o
    que esta medindo, em vez de repetir seis argumentos.

    ⚠️ **A regua padrao e a VERSAO 1** (a de 04/10/2026): os casos desta secao
    foram escritos para ela, e continuam provando que um dia antigo e pontuado
    como os outros daquele dia. A versao 2 tem os casos dela, mais abaixo.
    """
    base = dict(
        regua=REGUA_V1,
        medidas=medidas if medidas is not None else {},
        pesos=pesos if pesos is not None else _pesos(),
        nu_tentativas=1,
        nu_tempo_ms=PISO_MS,
        nu_dicas=0,
        nu_tempo_piso_ms=PISO_MS,
        nu_tempo_teto_ms=TETO_MS,
        direcoes=DIRECOES,
    )
    base.update(trocas)
    return montar_extrato(**base)


def _pesos() -> list[dict]:
    """Os pesos de merito de um desafio de damas, somando 1,000.

    ⚠️ Duas direcoes opostas de proposito: `damas_coroadas` e `maior_melhor`,
    `material_do_adversario` e `menor_melhor`. E a inversao que os casos abaixo
    exercitam.

    ⛔ **E nenhuma das duas e de SESSAO.** Tempo, tentativas e dicas ja tem peso
    fixo em `Q`; pesa-las tambem no merito faria a mesma medida contar duas
    vezes. O `conferir` do job recusa desde 16/09/2026.
    """
    return [
        {
            "nu_feito": 30,
            "co_feito": "damas_coroadas",
            "co_direcao": "maior_melhor",
            "nu_ordem": 1,
            "vr_peso": Decimal("0.600"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("2"),
            "co_sobre": None,
        },
        {
            "nu_feito": 40,
            "co_feito": "material_do_adversario",
            "co_direcao": "menor_melhor",
            "nu_ordem": 2,
            "vr_peso": Decimal("0.400"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("12"),
            "co_sobre": None,
        },
    ]


class RepoFalso:
    """Um `RepositorioEnvio` de mentira, guardando o que foi chamado."""

    def __init__(
        self,
        *,
        dia=True,
        partida=None,
        resolucao_nova=True,
        dicas_gastas=0,
        catalogo=(
            "damas_coroadas",
            "material_do_adversario",
            # As tres de sessao existem no catalogo, e e por isso que
            # envia-las nao e dado invalido: elas simplesmente nao pesam
            # no merito deste desafio.
            "tentativas",
            "tempo_ate_resolver",
            "dicas_usadas",
        ),
        sem_regua=False,
        ja_creditado=0,
        tem_consolo=False,
        sessao_no_servidor=(0, 0),
        dt_dia=AGORA.date(),
        linhas_das_reguas=None,
        xp_gravado=23,
    ) -> None:
        self._sem_regua = sem_regua
        # O dia UTC do desafio: escolhe a versao da regua da nota (T103).
        self._dt_dia = dt_dia
        self._linhas_das_reguas = (
            LINHAS_DAS_REGUAS if linhas_das_reguas is None else linhas_das_reguas
        )
        # O `nu_xp` da resolucao que JA existia, para o reenvio (T105).
        self._xp_gravado = xp_gravado
        # `(tentativas, dicas)` que o servidor conta (T085zf). O padrao `(0, 0)`
        # e "o servidor sabe menos que o envio": o envio vale, como antes.
        self._sessao_no_servidor = sessao_no_servidor
        # Os pedidos de [sessao_no_servidor], para conferir o que foi perguntado.
        self.perguntas_da_sessao: list[dict] = []
        self._dia = dia
        self._partida = partida
        self._resolucao_nova = resolucao_nova
        self._dicas_gastas = dicas_gastas
        self._catalogo = set(catalogo)
        # ⚠️ O que o dia ja tinha ANTES deste caso (T082). O resto da soma sai
        # do que o proprio caso gravar - ver [creditado_no_dia].
        self._ja_creditado_antes = ja_creditado
        self._tem_consolo_antes = tem_consolo

        self.tentativas: list[dict] = []
        self.resolucoes: list[dict] = []
        self.extratos: list[list] = []
        # As ancoras de cada `gravar_extrato`, na mesma ordem de [extratos].
        self.ancoras: list[dict] = []
        # Cada soma em `nu_xp_total`, na ordem - zero inclusive, se alguem pedir.
        self.creditos: list[int] = []
        self.dicas: list[dict] = []
        self.commits = 0

    async def dia_do_desafio(self, *, id_desafio_dia, id_desafio):
        if not self._dia:
            return None
        return {
            "id_desafio_dia": id_desafio_dia,
            "dt_dia": self._dt_dia,
            "id_desafio": id_desafio,
            "dh_encerramento": AGORA,
        }

    async def partida_por_evento(self, *, co_evento, id_usuario):
        return self._partida

    async def pesos_do_desafio(self, id_desafio):
        return _pesos()

    async def existe_no_catalogo(self, co_feito):
        return co_feito in self._catalogo

    async def regua_de_tempo(self, id_desafio):
        # ⚠️ `None` quando o desafio nao tem regua - e ha caso para isso, porque
        # o servico **nao pode** arbitrar um padrao no lugar.
        return (
            None
            if self._sem_regua
            else {"nu_tempo_piso_ms": PISO_MS, "nu_tempo_teto_ms": TETO_MS}
        )

    async def direcoes_de_sessao(self):
        return DIRECOES

    async def linhas_das_reguas_da_nota(self):
        return self._linhas_das_reguas

    async def xp_da_resolucao(self, *, id_resolucao):
        return self._xp_gravado

    async def dicas_da_tentativa(self, *, id_tentativa):
        # Quem pergunta tem de perguntar pela tentativa que acabou de gravar - e
        # o que torna o teto POR TENTATIVA (T108).
        self.tentativa_da_conta_de_dicas = id_tentativa
        return self._dicas_gastas

    async def sessao_no_servidor(self, **kwargs):
        self.perguntas_da_sessao.append(kwargs)
        return self._sessao_no_servidor

    async def gravar_tentativa(self, **kwargs):
        self.tentativas.append(kwargs)
        # O identificador fica guardado: a sessao do servidor e perguntada POR
        # ELE, e o caso confere que foi esta a tentativa perguntada.
        self.ultima_tentativa = uuid4()
        return self.ultima_tentativa, True

    async def gravar_resolucao(self, **kwargs):
        self.resolucoes.append(kwargs)
        return uuid4(), self._resolucao_nova

    async def gravar_extrato(self, parcelas, **kwargs):
        self.extratos.append(list(parcelas))
        self.ancoras.append(kwargs)

    async def creditado_no_dia(self, *, id_desafio_dia, id_usuario):
        """A mesma conta de `SQL_CREDITADO_NO_DIA`, sobre o que o caso gravou.

        ⚠️ Consolo e ajuste pelo `vr_xp`; a resolucao pela PONTUACAO - e so a
        resolucao nova, porque a que ja existia nao gravou nada.
        """
        linhas = [p for lista in self.extratos for p in lista]
        consolo_e_ajuste = sum(
            int(p.vr_xp) for p in linhas if p.nu_tipo_xp in (XP_CONSOLO, XP_AJUSTE)
        )
        resolucoes = (
            sum(r["nu_xp"] for r in self.resolucoes) if self._resolucao_nova else 0
        )
        tem_consolo = self._tem_consolo_antes or any(
            p.nu_tipo_xp == XP_CONSOLO for p in linhas
        )
        return self._ja_creditado_antes + consolo_e_ajuste + resolucoes, tem_consolo

    async def creditar_na_conta(self, *, id_usuario, xp):
        self.creditos.append(xp)

    async def gravar_dica(self, **kwargs):
        self.dicas.append(kwargs)
        return True

    async def confirmar(self):
        self.commits += 1


def _partida(co_status: str = "concluida", com_fim: bool = True) -> dict:
    """Uma partida de desafio ja no log."""
    return {
        "id_partida": uuid4(),
        "co_status": co_status,
        "co_modo": "desafio",
        "dh_inicio": AGORA,
        "dh_fim": AGORA if com_fim else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. ⚠️ Segurar nao e rejeitar
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resolucao_antes_da_partida_e_409_e_nao_400():
    """⚠️ A linha mais importante do contrato.

    Os dois eventos saem do **mesmo outbox**, e chegar fora de ordem e uma
    corrida de rede rotineira. O outbox trata `409` como "tente de novo" e `400`
    como "desista": trocar os dois faria a pessoa perder o XP por uma corrida de
    rede — e ela nunca saberia por que nao entrou no quadro.
    """
    repo = RepoFalso(partida=None)

    with pytest.raises(PartidaAindaNaoChegou) as erro:
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert erro.value.status_http == 409
    assert erro.value.codigo == "partida_ainda_nao_chegou"
    # ⛔ E nada foi gravado: segurar e nao fazer, nao e fazer pela metade.
    assert repo.tentativas == [] and repo.commits == 0


@pytest.mark.asyncio
async def test_partida_EM_ANDAMENTO_e_aceita():
    """⚠️ RF-DES-213/214: quem para no objetivo deixa a partida sem fim.

    A resolucao sobe com a partida ainda `em_andamento`, e o resto dos lances
    sobe quando ela acabar. ⛔ Recusar aqui tiraria o XP exatamente de quem parou
    no objetivo — o comportamento que a spec descreve como **esperado**.

    Quem garante o estado final sao o ingestor com `DO UPDATE` (T045) e o job de
    expiracao de 7 dias (T046), e nao uma recusa nesta rota.
    """
    repo = RepoFalso(partida=_partida("em_andamento", com_fim=False))

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
    )

    assert resultado.resposta.aceita is True
    assert len(repo.resolucoes) == 1
    # ⚠️ A tentativa precisa de `dh_fim` (`NOT NULL`), e a partida nao tem: o
    # instante da resolucao e o fim **desta tentativa**.
    assert repo.tentativas[0]["dh_fim"] == AGORA


@pytest.mark.asyncio
async def test_partida_de_outro_modo_e_rejeitada():
    """⚠️ A resolucao **e** uma partida de desafio (RF-DES-186).

    Uma partida comum apontada aqui poria no quadro uma partida que nunca foi
    jogada contra este desafio — e o replay mostraria outra coisa.
    """
    partida = _partida()
    partida["co_modo"] = "vs_cpu"
    repo = RepoFalso(partida=partida)

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert erro.value.codigo == "partida_nao_e_de_desafio"
    assert erro.value.status_http == 400


@pytest.mark.asyncio
async def test_resposta_a_desafio_de_outro_dia_e_rejeitada():
    """⛔ RF-DES-033: dado impossivel.

    Sem esta conferencia, um `id_desafio_dia` de ontem com o `id_desafio` de hoje
    gravaria a resolucao no evento errado — e a pessoa apareceria no quadro de um
    dia que ela nao jogou.
    """
    repo = RepoFalso(dia=False)

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert erro.value.codigo == "vinculo_invalido"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Idempotencia (SC-012)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reenviar_responde_ja_existia_e_NAO_regrava_o_extrato():
    """⛔ `tb004_xp_desafio` nao tem chave natural — e nem poderia ter.

    A linha de `ajuste` e **do dia**, sem ancora, entao nenhuma constraint pega
    a duplicata. A protecao mora aqui, e sem ela o Raio-X mostraria cada parcela
    duas vezes.
    """
    repo = RepoFalso(partida=_partida(), resolucao_nova=False)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
    )

    assert resultado.resposta.ja_existia is True
    assert resultado.resposta.aceita is True
    assert repo.extratos == []
    # ⚠️ T105: a resposta leva o XP que JA estava gravado, e nao um recalculado.
    assert resultado.resposta.pontuacao == 23


@pytest.mark.asyncio
async def test_a_primeira_resolucao_grava_o_extrato():
    """A conta inteira, aberta parcela a parcela — e metade do valor do Raio-X."""
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
    )

    assert resultado.resposta.ja_existia is False
    # base + as tres de sessao + os dois feitos que o desafio pesa.
    assert resultado.parcelas_gravadas == 6
    assert repo.commits == 1


@pytest.mark.asyncio
async def test_desafio_SEM_regua_de_tempo_e_recusado():
    """⛔ **Sem valor padrao, nem aqui nem na leitura.**

    Arbitrar 30 s/180 s faria a auditoria conferir contra uma regua **inventada**
    e acusar divergencia onde nao ha - e o alerta que acende sem motivo e o que
    faz ninguem mais ler o painel.
    """
    repo = RepoFalso(partida=_partida(), sem_regua=True)

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert erro.value.codigo == "regua_ausente"


@pytest.mark.asyncio
async def test_a_sessao_do_ENVIO_e_a_que_entra_nas_parcelas():
    """⚠️ Tentativas, tempo e dicas saem do payload, e nao de um feito enviado.

    O aplicativo manda as tres **tambem** como feitos, para o Raio-X; quem
    pontua e o campo proprio. Se as parcelas lessem a lista de feitos, um envio
    sem elas pagaria nota cheia de graca.
    """
    repo = RepoFalso(partida=_partida())

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO,
        id_usuario=ID_USUARIO,
        # 3 tentativas, 48,21 s e 1 dica: nenhuma das tres e a melhor marca.
        envio=_envio(dicas_usadas=1),
    )

    tentativas, tempo, dica = repo.extratos[0][1:4]
    assert tentativas.vr_medida == Decimal(3)
    assert tempo.vr_medida == Decimal(48210)
    assert dica.vr_medida == Decimal(1)
    # 1 dica = metade da parcela (RF-DES-042).
    assert dica.vr_normalizado == Decimal("0.5")


@pytest.mark.asyncio
async def test_tentativa_que_falhou_nao_vira_resolucao():
    """⛔ Falhar e privado (RF-DES-062): a tentativa existe no banco e **nunca**
    no quadro.

    A linha existe porque e ela que conta as tentativas para `Q`.
    """
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO,
        id_usuario=ID_USUARIO,
        envio=_envio(veredito="tentativa"),
    )

    assert len(repo.tentativas) == 1
    assert repo.tentativas[0]["ic_resolveu"] is False
    assert repo.resolucoes == []
    assert resultado.resposta.id_resolucao is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. O que o Pydantic recusa (RF-DES-033)
# ═══════════════════════════════════════════════════════════════════════════


def test_pontuacao_fora_de_12_30_e_dado_invalido():
    """A faixa e de **um** desafio; o teto do dia e outra coisa (RF-DES-155)."""
    with pytest.raises(ValueError):
        _envio(pontuacao=31)
    with pytest.raises(ValueError):
        _envio(pontuacao=11)
    # E o piso novo e aceito (era 18 ate a §8zs, 04/10/2026).
    assert _envio(pontuacao=12).pontuacao == 12


def test_qualidade_fora_de_0_1_e_dado_invalido():
    """`Q` e uma fracao; fora dela o numero nao significa nada."""
    with pytest.raises(ValueError):
        _envio(qualidade=1.4)


def test_o_lance_que_cumpre_o_desafio_e_obrigatorio():
    """⚠️ RF-DES-214: a coluna e `NOT NULL`.

    Rejeitar e melhor que gravar um zero de fachada — um zero passaria pelo
    banco e faria o Raio-X apontar para um lance que nao existe.
    """
    with pytest.raises(ValueError):
        _envio(nu_lance_cumpre_desafio=0)
    # E ausente tambem: ate 17/09/2026 o campo era obrigatorio no modelo, e
    # afrouxa-lo para a tentativa nao pode afrouxa-lo para a resolucao.
    with pytest.raises(ValueError):
        _envio(nu_lance_cumpre_desafio=None)


# ════════════════════════════════════════════════════════════════════════════
# 3b. A TENTATIVA QUE FALHOU sobe pela mesma rota — e nao cabia no modelo
#
# ⚠️ Achado em 17/09/2026 escrevendo o CONSUMIDOR (T066, o aplicativo). As duas
# guardas abaixo descreviam so a resolucao; a tentativa que falhou nao tem lance
# que cumpriu e vale 10 (RF-DES-041), que e menor que o piso de 18.
#
# ⛔ **E recusa-la seria pior que aceita-la**: o outbox do aplicativo trata 422
# como dado impossivel e REMOVE o evento. A contagem de tentativas ficaria so no
# aparelho, e quem tentasse dez vezes entraria no quadro com a nota de quem
# acertou de primeira.
# ════════════════════════════════════════════════════════════════════════════


def test_a_tentativa_que_falhou_nao_tem_lance_que_cumpriu():
    """⛔ Quem nao cumpriu nao tem `nu_lance_cumpre_desafio` — e nao inventa um.

    Um `1` de fachada faria o Raio-X apontar para um lance que nao cumpriu nada.
    """
    envio = _envio(
        veredito="tentativa",
        nu_lance_cumpre_desafio=None,
        pontuacao=XP_DA_TENTATIVA_SEM_RESOLVER,
    )
    assert envio.nu_lance_cumpre_desafio is None


def test_a_tentativa_que_falhou_vale_10_e_nao_18():
    """⚠️ RF-DES-041: tentar e nao resolver vale 10, uma vez por dia.

    O piso de 18 e de quem **resolveu** — cobra-lo da tentativa transformaria a
    contagem de tentativas em 422.
    """
    envio = _envio(
        veredito="tentativa",
        nu_lance_cumpre_desafio=None,
        pontuacao=XP_DA_TENTATIVA_SEM_RESOLVER,
    )
    assert envio.pontuacao == 10


@pytest.mark.asyncio
async def test_chave_de_feito_fora_do_catalogo_e_rejeitada():
    """⛔ Nao e tolerancia a campo novo — e o oposto.

    Uma chave inventada faria `Q` ordenar pessoas por medidas de significados
    diferentes.
    """
    repo = RepoFalso(partida=_partida())

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO,
            id_usuario=ID_USUARIO,
            envio=_envio(
                feitos=[FeitoMedido(chave="feito_que_nao_existe", valor=1)]
            ),
        )

    assert erro.value.codigo == "feito_desconhecido"


@pytest.mark.asyncio
async def test_chave_conhecida_que_o_desafio_nao_pesa_NAO_e_rejeitada():
    """⚠️ Uma medida que existe no catalogo mas nao pesa **neste** desafio nao e
    invencao: e so uma medida que ele nao usa.

    Recusa-la faria o aplicativo ter de saber, antes de enviar, quais feitos cada
    desafio pesa — informacao que ele nao tem e nao deveria ter.
    """
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO,
        id_usuario=ID_USUARIO,
        # `tentativas` esta no catalogo e nao esta nos pesos deste desafio.
        envio=_envio(feitos=[FeitoMedido(chave="tentativas", valor=3)]),
    )

    assert resultado.resposta.aceita is True


# ═══════════════════════════════════════════════════════════════════════════
# 4. O extrato: a direcao, e as tres parcelas invertidas
# ═══════════════════════════════════════════════════════════════════════════


def test_menor_melhor_INVERTE_a_parcela():
    """⚠️ **O defeito mais silencioso do XP.**

    Mais tempo, mais tentativas e mais dicas dao MENOS XP. Uma parcela na direcao
    errada **nao daria erro nenhum** — so pagaria mais a quem jogou pior. Por isso
    a direcao mora no catalogo, uma vez.
    """
    rapido = normalizar(
        Decimal(10000),
        co_normalizacao="faixa",
        co_direcao="menor_melhor",
        vr_min=Decimal(10000),
        vr_max=Decimal(70000),
    )
    devagar = normalizar(
        Decimal(70000),
        co_normalizacao="faixa",
        co_direcao="menor_melhor",
        vr_min=Decimal(10000),
        vr_max=Decimal(70000),
    )
    assert rapido == Decimal(1)
    assert devagar == Decimal(0)


def test_maior_melhor_nao_inverte():
    """A outra direcao, para a comparacao ficar visivel lado a lado."""
    assert normalizar(
        Decimal(2),
        co_normalizacao="faixa",
        co_direcao="maior_melhor",
        vr_min=Decimal(0),
        vr_max=Decimal(2),
    ) == Decimal(1)


def test_marco_atingido_ignora_a_normalizacao():
    """⚠️ "Venceu" nao tem gradacao.

    Foi a direcao que faltava no `data-model.md` ate 09/09/2026 — e sem ela um
    marco seria normalizado por uma faixa que ninguem sabia escolher.
    """
    assert normalizar(
        Decimal(1), co_normalizacao="nenhuma", co_direcao="marco_atingido"
    ) == Decimal(1)
    assert normalizar(
        Decimal(0), co_normalizacao="nenhuma", co_direcao="marco_atingido"
    ) == Decimal(0)


def test_medida_acima_do_teto_paga_a_parcela_cheia():
    """⚠️ Fora da faixa **nao e erro**.

    Uma partida excepcional pode passar do `vr_max` (resolver mais rapido que o
    gabarito), e o certo e pagar cheio — nao recusar a resolucao de quem jogou
    melhor do que o desafio previa.
    """
    assert normalizar(
        Decimal(5),
        co_normalizacao="faixa",
        co_direcao="maior_melhor",
        vr_min=Decimal(0),
        vr_max=Decimal(2),
    ) == Decimal(1)


def test_o_extrato_percorre_os_PESOS_e_nao_as_medidas():
    """⚠️ O desafio decide quais feitos contam nele.

    Percorrer as medidas deixaria um feito **do desafio** de fora quando o
    aplicativo esquecesse de envia-lo, e a pessoa perderia XP sem que nada
    acusasse. Aqui, medida ausente conta como zero.
    """
    parcelas = _extrato()

    # base + as tres de sessao + os dois pesos, mesmo sem medida enviada.
    assert len(parcelas) == 6
    assert all(p.vr_medida == Decimal(0) for p in parcelas[4:])


def test_a_linha_base_vale_o_piso_e_nao_aponta_para_feito():
    """`XP = 12 + 18 x Q`: os 12 sao a linha `base`.

    ⚠️ Ela nao tem `nu_feito`, e o `ck003_feito` da migracao exige que nao
    tenha.
    """
    base = _extrato()[0]
    assert base.vr_xp == Decimal(12)
    assert base.nu_feito is None


# ════════════════════════════════════════════════════════════════════════════
# 4b. ⚠️ AS TRES PARCELAS DE SESSAO (RF-DES-042) — o conserto de 16/09/2026
# ════════════════════════════════════════════════════════════════════════════
#
# Ate 16/09/2026 este modulo gerava **so** o merito, e com o peso relativo cru.
# A auditoria discordava do aplicativo em toda resolucao — e, como vale o
# aplicativo (D-05), o efeito nao seria XP errado na tela: seria o alerta de
# divergencia do painel aceso sempre, ate ninguem mais o ler.


def test_o_extrato_traz_as_tres_parcelas_de_sessao():
    """Tentativas, tempo e dica, cada uma com o seu tipo da dimensao."""
    tipos = [p.nu_tipo_xp for p in _extrato()]

    assert tipos[1] == XP_TENTATIVAS
    assert tipos[2] == XP_TEMPO
    assert tipos[3] == XP_DICA


def test_as_tres_de_sessao_NAO_apontam_para_feito():
    """⛔ O `ck003_feito` so aceita `nu_feito` em `merito` e `medida`.

    ⚠️ Elas **tem** chave no catalogo — e de la que vem a direcao —, mas na
    tabela a coluna fica vazia, como o `data-model.md` mostra.
    """
    for parcela in _extrato()[1:4]:
        assert parcela.nu_feito is None


def test_os_pesos_de_uma_resolucao_somam_1000():
    """⚠️ O cadeado barato: 0,30 + 0,30 + 0,15 + os 0,25 do merito repartidos.

    Se a soma nao fechar em 1, `Q` deixa de poder chegar a 1 — e ninguem mais
    tiraria 30, sem que nada desse erro.
    """
    assert soma_dos_pesos(_extrato()) == Decimal("1.000")

    # E com o merito repartido em tres linhas, inclusive uma de peso zero.
    pesos = _pesos()
    pesos[0] = {**pesos[0], "vr_peso": Decimal("1.000")}
    pesos[1] = {
        **pesos[1],
        "vr_peso": Decimal("0.000"),
        "co_normalizacao": "nenhuma",
        "vr_min": None,
        "vr_max": None,
    }
    assert soma_dos_pesos(_extrato(pesos=pesos)) == Decimal("1.000")


def test_o_peso_do_merito_e_RELATIVO_e_vira_um_quarto():
    """⚠️ `0,600` dentro do merito e `0,150` em `Q` (RF-DES-173).

    ⛔ Era este o segundo defeito: o peso relativo ia cru para a coluna, e a
    linha valia `0,600` de `Q` onde devia valer `0,150` - hoje, com os 18 XP
    moveis da §8zs, seria `10,8` no lugar de `2,7`.
    """
    merito = _extrato(medidas={"damas_coroadas": Decimal(2)})[4]

    assert merito.vr_peso == Decimal("0.250") * Decimal("0.600")
    assert merito.vr_peso == Decimal("0.150")
    assert merito.vr_xp == Decimal("2.700")

    # ⚠️ E o peso do merito e o DA REGUA: na versao 2 ele vale 0,15, e o mesmo
    # 0,600 vira 0,090 (T103).
    na_v2 = _extrato(regua=REGUA_V2, medidas={"damas_coroadas": Decimal(2)})[4]
    assert na_v2.vr_peso == Decimal("0.090")


def test_as_tres_correm_ao_CONTRARIO_e_a_dimensao_tem_de_CONCORDAR():
    """⚠️ Mais tentativas, mais tempo e mais dicas dao MENOS XP.

    ⚠️ **Desde 10/10/2026 (T103) a direcao esta dentro da CURVA** da regua do
    banco (linear e hiperbolica so descem), e a dimensao virou conferencia: se
    ela disser outra coisa, os dois dados estao em conflito e a conta falha
    alto. Ate ali a dimensao invertia a nota, e o caso trocava a direcao para
    ver a nota acompanhar.
    """
    melhor = _extrato()
    assert [p.vr_normalizado for p in melhor[1:4]] == [Decimal(1)] * 3

    pior = _extrato(nu_tentativas=1000, nu_tempo_ms=TETO_MS, nu_dicas=2)
    assert pior[2].vr_normalizado == Decimal(0)
    assert pior[3].vr_normalizado == Decimal(0)
    assert pior[1].vr_normalizado == Decimal(0)

    # A dimensao mandando ao contrario: ⛔ nao se escolhe um dos dois.
    with pytest.raises(MedidaInvalida):
        _extrato(nu_dicas=2, direcoes={**DIRECOES, "dicas_usadas": "maior_melhor"})


def test_piorar_nunca_aumenta_a_nota():
    """A propriedade, sem numero esperado nenhum — ela sobrevive a afinacao dos
    pesos em campo.

    ⚠️ **Da 4a tentativa em diante a nota PARA de cair** (§8zs: a parcela zera
    ali), e por isso a comparacao e estrita ate a 4a e `<=` depois. Exigir `<` em
    toda a lista reprovaria a regua que o dono escolheu.
    """
    anterior = Decimal(2)
    for tentativas in (1, 2, 3, 4):
        q = qualidade_do_extrato(_extrato(nu_tentativas=tentativas))
        assert q < anterior
        anterior = q
    for tentativas in (8, 20):
        q = qualidade_do_extrato(_extrato(nu_tentativas=tentativas))
        assert q <= anterior
        anterior = q

    anterior = Decimal(2)
    for tempo in (PISO_MS, 30_000, 60_000, TETO_MS):
        q = qualidade_do_extrato(_extrato(nu_tempo_ms=tempo))
        assert q < anterior
        anterior = q

    assert qualidade_do_extrato(_extrato(nu_dicas=0)) > qualidade_do_extrato(
        _extrato(nu_dicas=1)
    ) > qualidade_do_extrato(_extrato(nu_dicas=2))


def test_a_regua_de_tempo_e_do_DESAFIO():
    """O mesmo tempo, em duas reguas, vale notas diferentes (RF-DES-223).

    Um final de 3 lances e uma abertura de 12 nao pedem a mesma pressa.
    """
    apertada = _extrato(
        nu_tempo_ms=60_000, nu_tempo_piso_ms=10_000, nu_tempo_teto_ms=70_000
    )
    folgada = _extrato(
        nu_tempo_ms=60_000, nu_tempo_piso_ms=30_000, nu_tempo_teto_ms=300_000
    )
    assert apertada[2].vr_normalizado < folgada[2].vr_normalizado


@pytest.mark.parametrize(
    "trocas",
    [
        {"nu_tentativas": 0},
        {"nu_tempo_ms": -1},
        {"nu_dicas": -1},
        {"nu_tempo_piso_ms": 0},
        {"nu_tempo_piso_ms": 60_000, "nu_tempo_teto_ms": 60_000},
        {"nu_tempo_piso_ms": 60_000, "nu_tempo_teto_ms": 30_000},
        {"direcoes": {}},
        {"direcoes": {**DIRECOES, "tentativas": "marco_atingido"}},
    ],
)
def test_numero_impossivel_de_sessao_e_medida_invalida(trocas):
    """⚠️ Zero tentativas daria nota cheia a quem nao jogou; regua degenerada
    divide por zero; e sem a direcao no catalogo (ou com outra) a regua e o
    catalogo nao concordam.

    ⚠️ **3 dicas deixou de ser impossivel em 10/10/2026** (§8zzo): o teto de 2
    e do botao, por tentativa, e a nota conta todas as do dia.
    """
    with pytest.raises(MedidaInvalida):
        _extrato(**trocas)


def test_peso_zero_vira_MEDIDA_e_peso_positivo_vira_MERITO():
    """⚠️ Peso zero e legitimo: o feito e medido e exibido no Raio-X, e nao
    pontua. Os dois tipos sao os que o `ck003_feito` exige que tragam `nu_feito`.
    """
    pesos = _pesos()
    pesos[1] = {
        **pesos[1],
        "vr_peso": Decimal("0.000"),
        "co_normalizacao": "nenhuma",
        "vr_min": None,
        "vr_max": None,
    }
    pesos[0] = {**pesos[0], "vr_peso": Decimal("1.000")}

    parcelas = _extrato(medidas={"damas_coroadas": Decimal(2)}, pesos=pesos)

    assert parcelas[4].nu_tipo_xp == XP_MERITO
    assert parcelas[5].nu_tipo_xp == XP_MEDIDA
    assert parcelas[5].vr_xp == Decimal(0)


def test_q_cheio_paga_o_teto_de_30():
    """A formula fechada: `Q = 1` leva a 12 + 18 = 30.

    ⚠️ **E agora exige as quatro parcelas cheias** — primeira tentativa, no
    piso do tempo, sem dica e com o merito completo. Antes do conserto, o merito
    sozinho bastava, e quem resolvesse na decima tentativa com duas dicas tirava
    30 assim mesmo.
    """
    parcelas = _extrato(
        medidas={
            "damas_coroadas": Decimal(2),
            "material_do_adversario": Decimal(0),
        }
    )
    assert qualidade_do_extrato(parcelas) == Decimal(1)
    assert sum(p.vr_xp for p in parcelas) == Decimal(30)


def test_a_pior_resolucao_ainda_paga_o_piso_de_12():
    """⚠️ Quem resolveu, resolveu (RF-DES-040).

    Com a regua da §8zs (04/10/2026) `Q` chega a **zero exato**: a parcela de
    tentativas zera na 4a, o tempo passou do teto, as duas dicas foram gastas e o
    merito saiu zero. O total e o piso, e o piso (12) continua acima dos 10 de
    quem so tentou (§8zp).
    """
    parcelas = _extrato(
        nu_tentativas=30,
        nu_tempo_ms=TETO_MS * 2,
        nu_dicas=2,
        medidas={"material_do_adversario": Decimal(12)},
    )
    assert qualidade_do_extrato(parcelas) == Decimal(0)
    assert sum(p.vr_xp for p in parcelas) == Decimal(12)


# ════════════════════════════════════════════════════════════════════════════
# 4c. 🔒 O CASO DE OURO — a tabela do `data-model.md`, linha a linha
# ════════════════════════════════════════════════════════════════════════════


def test_o_caso_de_ouro_do_data_model():
    """*"Tentou, falhou, tentou de novo e resolveu em 27 s, sem dica, fechando as
    4 caixas e acertando 3 lances otimos de 6."*

    ⚠️ **E o MESMO caso do teste do aplicativo** (`qualidade_test.dart`, grupo
    "o caso de ouro"). Os dois lados calculam a mesma resolucao e tem de chegar
    ao mesmo numero — e a auditoria de RF-DES-032 que depende disso. Se um dia
    divergirem, o alerta do painel acende com razao.

    ⚠️ **Refeito em 04/10/2026** (§8zs): a regua do desafio de 5 lances desceu
    de 30 s/180 s para 10 s/60 s, e o tempo do caso de 74 s para 27 s - 74 s
    passaria do teto novo, e a parcela de tempo sairia zero, sem medir nada.
    """
    pesos = [
        {
            "nu_feito": 10,
            "co_feito": "caixas_fechadas",
            "co_direcao": "maior_melhor",
            "nu_ordem": 1,
            "vr_peso": Decimal("0.600"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("4"),
            "co_sobre": None,
        },
        {
            "nu_feito": 20,
            "co_feito": "lances_otimos",
            "co_direcao": "maior_melhor",
            "nu_ordem": 2,
            "vr_peso": Decimal("0.400"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("6"),
            "co_sobre": None,
        },
    ]
    parcelas = _extrato(
        medidas={
            "caixas_fechadas": Decimal(4),
            "lances_otimos": Decimal(3),
        },
        pesos=pesos,
        nu_tentativas=2,
        nu_tempo_ms=27_000,
        nu_dicas=0,
        nu_tempo_piso_ms=10_000,
        nu_tempo_teto_ms=60_000,
    )

    base, tentativas, tempo, dica, caixas, otimos = parcelas

    assert base.vr_xp == Decimal(12)
    # Na 2a tentativa: 1 - (2 - 1) / (4 - 1) = 2/3.
    assert round(tentativas.vr_normalizado, 4) == Decimal("0.6667")
    assert round(tentativas.vr_xp, 3) == Decimal("3.600")
    # (60000 - 27000) / (60000 - 10000) = 0,66
    assert tempo.vr_normalizado == Decimal("0.66")
    assert round(tempo.vr_xp, 3) == Decimal("3.564")
    assert dica.vr_xp == Decimal("2.700")
    assert caixas.vr_peso == Decimal("0.150")
    assert caixas.vr_xp == Decimal("2.700")
    assert otimos.vr_peso == Decimal("0.100")
    assert otimos.vr_normalizado == Decimal("0.5")
    assert otimos.vr_xp == Decimal("0.900")

    # ⚠️ O arredondamento acontece UMA vez, no fim: parcela a parcela daria
    # 12 + 4 + 4 + 3 + 3 + 1 = 27.
    total = sum(p.vr_xp for p in parcelas)
    assert round(total, 3) == Decimal("25.464")
    assert round(total) == 25


# ════════════════════════════════════════════════════════════════════════════
# 4d. ⚠️ A REGUA 2 (§8zzo, T103): hiperbolica, sem teto, 50/15/20/15
# ════════════════════════════════════════════════════════════════════════════


def _v2(**trocas):
    """O extrato com a regua 2 e o merito CHEIO - so a sessao varia."""
    base = dict(
        regua=REGUA_V2,
        medidas={"damas_coroadas": Decimal(2), "material_do_adversario": Decimal(0)},
    )
    base.update(trocas)
    return _extrato(**base)


@pytest.mark.parametrize(
    ("trocas", "esperado"),
    [
        # 1a tentativa, sem dica, no piso: Q = 1.
        ({}, 30),
        # 3x o piso: tempo 2/(1+3) = 0,5 → perde 18 x 0,15 x 0,5 = 1,35 → 28,65.
        ({"nu_tempo_ms": 3 * PISO_MS}, 29),
        # 1 dica e 2x o piso: dica 2/3, tempo 2/3 → 30 - 1,2 - 0,9 = 27,9.
        ({"nu_dicas": 1, "nu_tempo_ms": 2 * PISO_MS}, 28),
        # 2a tentativa e 2x o piso: tentativas 1/2 → 30 - 4,5 - 0,9 = 24,6.
        ({"nu_tentativas": 2, "nu_tempo_ms": 2 * PISO_MS}, 25),
        # 9 tentativas: 1/9 → 30 - 9 x 0,5 x 8/9 = 22,0.
        ({"nu_tentativas": 9}, 22),
        # 4 tentativas, 2 dicas, 3x o piso: 12 + 18 x 0,45 = 20,1.
        ({"nu_tentativas": 4, "nu_dicas": 2, "nu_tempo_ms": 3 * PISO_MS}, 20),
        # 30 tentativas, 10 dicas, 20x o piso: 12 + 18 x 0,2143 = 15,86.
        ({"nu_tentativas": 30, "nu_dicas": 10, "nu_tempo_ms": 20 * PISO_MS}, 16),
    ],
)
def test_os_perfis_da_8zzo(trocas, esperado):
    """🔒 A tabela de perfis que o dono viu ao aprovar a regua (§8zzo).

    ⚠️ Os numeros estao escritos A MAO, com a conta no comentario: sao o limite
    externo que a implementacao tem de alcancar.
    """
    assert pontuacao_do_extrato(_v2(**trocas)) == esperado


def test_v2_as_curvas_tendem_a_zero_e_nunca_chegam_la():
    """`1/n`, `2/(2+d)` e `2/(1+t/piso)`: a nota cai, e nunca zera.

    ⚠️ E isto que a §8zzo pediu (*"quem tentar 30 vezes recebe a mesma parcela
    de quem tentar 5?"*): com a regua 1, da 4a em diante tudo valia zero.
    """
    tent, tempo, dica = _v2(nu_tentativas=2, nu_dicas=2, nu_tempo_ms=3 * PISO_MS)[1:4]
    assert tent.vr_normalizado == Decimal("0.5")
    assert dica.vr_normalizado == Decimal("0.5")
    assert tempo.vr_normalizado == Decimal("0.5")

    anterior = Decimal(2)
    for n in (1, 2, 4, 9, 30, 300):
        q = _v2(nu_tentativas=n)[1].vr_normalizado
        assert Decimal(0) < q < anterior
        anterior = q

    anterior = Decimal(2)
    for d in (0, 1, 2, 4, 10):
        q = _v2(nu_dicas=d)[3].vr_normalizado
        assert Decimal(0) < q < anterior
        anterior = q


def test_v2_dentro_do_piso_o_tempo_e_cheio():
    """Abaixo de `x0` (1x o piso), nota cheia - o resolver mais rapido que o
    gabarito nao ganha mais que 1."""
    assert _v2(nu_tempo_ms=PISO_MS // 2)[2].vr_normalizado == Decimal(1)


def test_v2_o_TETO_do_desafio_sai_da_nota():
    """⚠️ §8zzo: o `nu_tempo_teto_ms` deixa de entrar na nota (a coluna fica).

    O mesmo tempo, com tetos diferentes, vale o mesmo - e um teto degenerado
    nao derruba a conta, porque ninguem o le.
    """
    um = _v2(nu_tempo_ms=40_000, nu_tempo_teto_ms=TETO_MS)[2].vr_normalizado
    outro = _v2(nu_tempo_ms=40_000, nu_tempo_teto_ms=PISO_MS)[2].vr_normalizado
    assert um == outro


def test_v2_Maria_23_e_Fernando_22():
    """🔒 O empate que motivou a regua nova (desafio de 10/10/2026, `prd`).

    Fernando: 9 tentativas, 0 dica, 38 s - dentro do piso, merito cheio.
    Maria: 2 tentativas, 2 dicas, 54 s - 1,176x o piso, merito 4,44 de 4,50.
    Com a regua 1 os dois tiravam 25.

    ⚠️ O piso (45,9 s) e o merito sao os do desafio daquele dia, refeitos da
    tabela da §8zzo; a conferencia com as linhas reais do banco e a T115.
    """
    piso = 45_918
    fernando = _v2(
        nu_tentativas=9, nu_dicas=0, nu_tempo_ms=38_000, nu_tempo_piso_ms=piso
    )
    # Merito 4,44/4,50: damas 2/2 (0,6) e material 0,4 x (1 - 0,4/12).
    maria = _v2(
        nu_tentativas=2,
        nu_dicas=2,
        nu_tempo_ms=54_000,
        nu_tempo_piso_ms=piso,
        medidas={
            "damas_coroadas": Decimal(2),
            "material_do_adversario": Decimal("0.4"),
        },
    )
    assert pontuacao_do_extrato(fernando) == 22
    assert pontuacao_do_extrato(maria) == 23


def test_a_soma_dos_pesos_da_v2_tambem_fecha_em_1000():
    """O cadeado barato vale para qualquer versao da regua."""
    assert soma_dos_pesos(_v2()) == Decimal("1.000")


# ── A pontuacao: a soma do extrato, inteira ───────────────────────────────────


def _soma(*valores: str) -> list[ParcelaDeXp]:
    """Parcelas so com XP - para medir o arredondamento sem regua nenhuma."""
    return [
        ParcelaDeXp(
            nu_tipo_xp=XP_MERITO,
            nu_feito=None,
            vr_medida=None,
            vr_normalizado=None,
            vr_peso=None,
            vr_xp=Decimal(v),
        )
        for v in valores
    ]


def test_o_MEIO_arredonda_para_CIMA_como_o_dart():
    """12 + 4,5 = 16,5 → 17.

    ⚠️ O `round()` do Python arredonda o meio para o PAR (16); o do Dart, para
    longe do zero (17). A estimativa do app e o numero do servidor tem de
    concordar tambem no meio.
    """
    assert pontuacao_do_extrato(_soma("12", "4.5")) == 17
    assert pontuacao_do_extrato(_soma("12", "4.499")) == 16


def test_a_pontuacao_fica_entre_12_e_30():
    """A guarda dos extremos (o `ck001_xp` do banco recusaria fora deles)."""
    assert pontuacao_do_extrato(_soma("11")) == 12
    assert pontuacao_do_extrato(_soma("31")) == 30


def test_fracao_sem_denominador_e_medida_invalida():
    """⚠️ O denominador e **outra medida da mesma partida**.

    Ele nao e um numero do desafio: muda a cada resolucao. Sem ele, a parcela nao
    tem como ser calculada — e inventar `1` pagaria a parcela cheia a todo mundo.
    """
    pesos = [
        {
            "nu_feito": 31,
            "co_feito": "capturas_extras",
            "co_direcao": "maior_melhor",
            "nu_ordem": 1,
            "vr_peso": Decimal("1.000"),
            "co_normalizacao": "fracao",
            "vr_min": None,
            "vr_max": None,
            "co_sobre": "material_do_adversario",
        }
    ]
    with pytest.raises(MedidaInvalida):
        _extrato(medidas={"capturas_extras": Decimal(2)}, pesos=pesos)


# ═══════════════════════════════════════════════════════════════════════════
# 5. A dica (RF-DES-056/057)
# ═══════════════════════════════════════════════════════════════════════════


def _dica(grau: int = 1) -> EnvioDeDica:
    return EnvioDeDica(
        id_desafio_dia=ID_DIA,
        co_evento_partida="evento-7c3e",
        grau=grau,
        consumida_em=AGORA,
    )


@pytest.mark.asyncio
async def test_a_dica_e_registrada_e_cria_a_tentativa_se_preciso():
    """⚠️ A dica chega **durante** a partida, antes de qualquer resolucao.

    A tentativa nasce aqui com `ic_resolveu = FALSE`; quando a resolucao chegar,
    ela reencontra esta mesma linha pelo `id_partida UNIQUE` e a atualiza.
    """
    repo = RepoFalso(partida=_partida("em_andamento", com_fim=False))

    assert await ServicoEnvio(repo).registrar_dica(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_dica()
    )
    assert repo.tentativas[0]["ic_resolveu"] is False
    assert repo.dicas[0]["nu_grau"] == 1


@pytest.mark.asyncio
async def test_o_teto_de_duas_dicas_e_por_TENTATIVA():
    """⚠️ §8zzo, decisao 1 (10/10/2026): cada tentativa recomeca com as duas.

    A conta e feita pela tentativa que ACABOU de ser gravada - e conferir o
    identificador perguntado e o que separa "por tentativa" de "por dia": um
    repositorio que somasse o dia devolveria o mesmo numero neste caso.
    """
    repo = RepoFalso(partida=_partida(), dicas_gastas=TETO_DE_DICAS_POR_TENTATIVA)

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_dica(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_dica(grau=2)
        )

    assert erro.value.codigo == "teto_de_dicas"
    assert repo.dicas == []
    assert repo.tentativa_da_conta_de_dicas == repo.ultima_tentativa
    # ⛔ E nada foi confirmado: a tentativa gravada antes da conta se desfaz.
    assert repo.commits == 0


@pytest.mark.asyncio
async def test_a_dica_abaixo_do_teto_da_TENTATIVA_passa_mesmo_com_o_dia_cheio():
    """Uma dica ja gasta nesta tentativa: a 2a passa.

    ⚠️ Antes de 10/10/2026 a 2a tentativa de quem ja tinha gastado duas era
    recusada; agora a conta so enxerga a tentativa.
    """
    repo = RepoFalso(partida=_partida(), dicas_gastas=1)

    assert await ServicoEnvio(repo).registrar_dica(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_dica(grau=2)
    )
    assert repo.dicas[0]["nu_grau"] == 2
    assert TETO_DE_DICAS_POR_TENTATIVA == 2



@pytest.mark.asyncio
async def test_dica_antes_da_partida_tambem_e_segurada():
    """O mesmo `409` da resolucao, pelo mesmo motivo."""
    repo = RepoFalso(partida=None)

    with pytest.raises(PartidaAindaNaoChegou):
        await ServicoEnvio(repo).registrar_dica(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_dica()
        )


def test_o_grau_da_dica_e_1_ou_2():
    """⚠️ Sao duas coisas diferentes, e a segunda so faz sentido depois da
    primeira (regiao/peca · o lance)."""
    with pytest.raises(ValueError):
        _dica(grau=3)
    with pytest.raises(ValueError):
        _dica(grau=0)


# ═══════════════════════════════════════════════════════════════════════════
# 6. ⚠️ O CREDITO NA CONTA (T082, RF-DES-041/047/181)
#
# Ate 22/09/2026 o servidor gravava o extrato e ⛔ nunca somava nada em
# `nu_xp_total`: a pessoa via "+27 XP" na tela e o ranking nao mudava. Estes
# casos provam o credito, o consolo uma vez por dia e a linha de ajuste - e que a
# conta do dia fecha igual em qualquer ordem de chegada.
#
# ⚠️ Desde 02/10/2026 o consolo e PISO, e nao soma (DECISOES-do-dono §8zp, no
# frontend): o dia vale o MAIOR evento. Ate ali, 10 + 27 cortado em 30.
# ═══════════════════════════════════════════════════════════════════════════


def _perfeito(**trocas) -> EnvioDeResolucao:
    """A resolucao perfeita: 1a tentativa, sem dica, no piso, merito cheio.

    ⚠️ O servidor calcula 30 nas DUAS reguas - e e por isso que os casos de
    credito a usam: o numero e conhecido sem depender da versao.
    """
    base = dict(
        tentativas=1,
        dicas_usadas=0,
        tempo_ms=PISO_MS,
        qualidade=1.0,
        pontuacao=30,
        feitos=[
            FeitoMedido(chave="damas_coroadas", valor=2),
            FeitoMedido(chave="material_do_adversario", valor=0),
        ],
    )
    base.update(trocas)
    return _envio(**base)


def _falha(**trocas) -> EnvioDeResolucao:
    """Uma tentativa que ⛔ resolveu, como o aplicativo a manda."""
    base = dict(
        veredito="tentativa",
        nu_lance_cumpre_desafio=None,
        pontuacao=XP_DA_TENTATIVA_SEM_RESOLVER,
    )
    base.update(trocas)
    return _envio(**base)


def _linhas_do_tipo(repo: RepoFalso, tipo: int) -> list[tuple]:
    """As linhas de um tipo, cada uma com as ancoras com que foi gravada."""
    return [
        (parcela, ancoras)
        for lista, ancoras in zip(repo.extratos, repo.ancoras)
        for parcela in lista
        if parcela.nu_tipo_xp == tipo
    ]


@pytest.mark.asyncio
async def test_resolver_credita_a_pontuacao_do_SERVIDOR_inteira():
    """O caso comum: sem consolo antes, a pontuacao cabe nos 30 e ⛔ nao ha
    ajuste.

    ⚠️ **E e a do SERVIDOR, e nao a do envio** (T103, §8zzo decisao 7). O envio
    diz 26; com a regua 1 a conta e 12 + 1,8 (3 tentativas) + 3,044 (48,2 s
    numa regua de 12 s a 95 s) + 1,35 (1 dica) + 1,35 + 1,8 (merito) = 21,34.
    """
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio(pontuacao=26)
    )

    assert repo.resolucoes[0]["nu_xp"] == 21
    assert resultado.xp_creditado == 21
    assert repo.creditos == [21]
    assert _linhas_do_tipo(repo, XP_AJUSTE) == []
    # T105: a resposta leva o numero do servidor, para o app trocar a estimativa.
    assert resultado.resposta.pontuacao == 21


@pytest.mark.asyncio
async def test_resolver_com_30_de_primeira_cabe_EXATO_no_teto():
    """🔒 A fronteira: 30 de 30 ⛔ e corte. Um `<` no lugar de `<=` cortaria 1."""
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_perfeito()
    )

    assert resultado.xp_creditado == 30
    assert _linhas_do_tipo(repo, XP_AJUSTE) == []


@pytest.mark.asyncio
async def test_a_primeira_falha_paga_o_consolo_ancorado_na_TENTATIVA():
    """RF-DES-041: tentar e nao resolver vale 10.

    ⚠️ A linha e ancorada na tentativa, e ⛔ numa resolucao que nao existe.
    """
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert resultado.xp_creditado == 10
    assert repo.creditos == [10]
    # ⚠️ T105: a falha nao tem pontuacao de resolucao a devolver.
    assert resultado.resposta.pontuacao is None
    [(consolo, ancoras)] = _linhas_do_tipo(repo, XP_CONSOLO)
    assert consolo.vr_xp == Decimal(10) and consolo.nu_feito is None
    assert ancoras["id_tentativa"] == resultado.id_tentativa
    assert ancoras["id_resolucao"] is None
    # ⛔ E a falha continua privada: resolucao nenhuma.
    assert repo.resolucoes == []


@pytest.mark.asyncio
async def test_o_consolo_e_10_mesmo_que_o_corpo_diga_OUTRA_coisa():
    """⚠️ O servidor ⛔ le a pontuacao da falha (o modelo aceita qualquer uma).

    O consolo e constante da regra; ler o corpo daria a quem monta o corpo o
    poder de escolher quanto ganha por errar.
    """
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha(pontuacao=0)
    )

    assert resultado.xp_creditado == XP_DA_TENTATIVA_SEM_RESOLVER


@pytest.mark.asyncio
async def test_a_SEGUNDA_falha_do_dia_nao_paga_nada():
    """⚠️ "Uma vez por dia" (RF-DES-041).

    ⚠️ E a guarda e o consolo do DIA, e ⛔ a tentativa ser nova: o reenvio de uma
    falha tambem responde `escreveu=True` em `gravar_tentativa`.
    """
    repo = RepoFalso(partida=_partida(), ja_creditado=10, tem_consolo=True)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert resultado.xp_creditado == 0
    assert repo.creditos == []
    assert repo.extratos == []


@pytest.mark.asyncio
async def test_falhar_e_depois_resolver_fecha_o_dia_na_PONTUACAO_com_AJUSTE():
    """🔒 O caso de ouro do `data-model.md`: 10 + 30 - 10 = 30.

    ⚠️ O `nu_xp` da resolucao continua 30 - e o que o quadro ordena. A
    resolucao credita so o que falta (20), e o ajuste tira os 10 do consolo,
    que ja estao dentro da pontuacao.
    """
    repo = RepoFalso(partida=_partida())
    servico = ServicoEnvio(repo)

    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )
    resultado = await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_perfeito()
    )

    assert repo.creditos == [10, 20]
    assert resultado.xp_creditado == 20
    assert repo.resolucoes[0]["nu_xp"] == 30
    [(ajuste, ancoras)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-10)
    # ⚠️ O ajuste e do DIA: nem resolucao, nem tentativa.
    assert ancoras["id_resolucao"] is None and ancoras["id_tentativa"] is None


@pytest.mark.asyncio
async def test_a_ORDEM_de_chegada_nao_muda_a_conta_do_dia():
    """⚠️ A fila do aparelho nao garante ordem: resolucao antes, consolo depois.

    30 entra inteiro, e o consolo entra com zero - o dia fecha nos mesmos 30 e
    com o mesmo ajuste de -10.
    """
    repo = RepoFalso(partida=_partida())
    servico = ServicoEnvio(repo)

    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_perfeito()
    )
    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert repo.creditos == [30, 0]
    assert sum(repo.creditos) == 30
    [(ajuste, _)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-10)


@pytest.mark.asyncio
async def test_o_reenvio_da_resolucao_NAO_credita_de_novo():
    """⛔ Creditar no reenvio daria XP em dobro a cada vez que o outbox insistisse."""
    repo = RepoFalso(partida=_partida(), resolucao_nova=False)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
    )

    assert resultado.xp_creditado == 0
    assert repo.creditos == []


@pytest.mark.asyncio
async def test_um_dia_JA_CHEIO_grava_o_consolo_e_o_corte_inteiro():
    """⚠️ O extrato continua dizendo a verdade: tentou (+10), e o ajuste tira tudo.

    E o caso de quem resolveu com 30 em outro aparelho e falhou neste depois: o
    dia ja vale mais que o consolo.
    """
    repo = RepoFalso(partida=_partida(), ja_creditado=30)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert resultado.xp_creditado == 0
    [(ajuste, _)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-10)


# ── T110: a partida ABANDONADA conta como tentativa, e nao paga nada ────────────


def _abandonada(**trocas) -> EnvioDeResolucao:
    """A partida largada no meio, como a 1.3.1 a manda (veredito proprio)."""
    base = dict(veredito="abandonada", tempo_ms=21_500)
    base.update(trocas)
    return _falha(**base)


@pytest.mark.asyncio
async def test_a_ABANDONADA_grava_a_tentativa_com_o_TEMPO_e_nao_paga_nada():
    """⚠️ §8zzo decisao 5 e R3: conta como tentativa, sem consolo.

    O tempo jogado (> 0) e o que faz a linha contar em `SQL_SESSAO_NO_SERVIDOR`
    e no `meu-dia` - inclusive a que a dica tinha criado com tempo zero.
    """
    repo = RepoFalso(partida=_partida("abandonada"))

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_abandonada()
    )

    [tentativa] = repo.tentativas
    assert tentativa["ic_resolveu"] is False
    assert tentativa["nu_tempo_ms"] == 21_500
    assert repo.extratos == [] and repo.creditos == []
    assert resultado.xp_creditado == 0
    assert resultado.resposta.pontuacao is None
    assert repo.resolucoes == []
    assert repo.commits == 1


@pytest.mark.asyncio
async def test_a_ABANDONADA_nao_conta_como_o_consolo_do_dia():
    """Depois de uma abandonada, a 1a falha de verdade ainda paga os 10."""
    repo = RepoFalso(partida=_partida())
    servico = ServicoEnvio(repo)

    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_abandonada()
    )
    resultado = await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert resultado.xp_creditado == 10
    assert len(_linhas_do_tipo(repo, XP_CONSOLO)) == 1


@pytest.mark.asyncio
async def test_a_ABANDONADA_antes_da_partida_tambem_e_segurada():
    """O mesmo 409: o log da partida largada pode chegar depois do envio."""
    repo = RepoFalso(partida=None)

    with pytest.raises(PartidaAindaNaoChegou):
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_abandonada()
        )


def test_o_veredito_ABANDONADA_e_aceito_e_inventado_nao():
    """⚠️ Era `resolvido | tentativa` ate a T110; um terceiro inventado e 422."""
    assert _abandonada().veredito == "abandonada"
    with pytest.raises(ValueError):
        _falha(veredito="desistiu")


@pytest.mark.asyncio
async def test_o_credito_entra_na_MESMA_transacao_do_extrato():
    """⚠️ Um commit so: um extrato sem credito (ou o contrario) nao se conserta."""
    repo = RepoFalso(partida=_partida())

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert repo.commits == 1


# ── A regra pura ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ja_creditado", "valor", "creditado"),
    [
        (0, 30, 30),  # a resolucao perfeita de primeira
        (0, 18, 18),  # a pior resolucao de primeira: inteira
        (0, 10, 10),  # a primeira falha: o consolo inteiro
        (10, 27, 17),  # o exemplo do data-model: so o que falta
        (10, 18, 8),  # o piso depois de falhar - ainda positivo
        (27, 10, 0),  # o consolo depois da resolucao: nada a somar
        (30, 10, 0),  # o dia que ja vale mais que o consolo
    ],
)
def test_credito_do_dia_credita_so_o_que_falta_para_o_valor(
    ja_creditado, valor, creditado
):
    credito = credito_do_dia(ja_creditado=ja_creditado, valor=valor)
    assert credito.creditado == creditado
    assert credito.valor == valor, "⛔ o valor pontuado nunca e alterado"
    assert credito.corte == valor - creditado


@pytest.mark.parametrize("pontuacao", range(18, 31))
def test_o_dia_fecha_na_PONTUACAO_em_qualquer_ordem(pontuacao):
    """🔒 O consolo e piso: falhar antes ou depois da resolucao da o mesmo dia.

    E o dia de quem resolveu nunca fica abaixo do de quem so tentou (10) - o
    pedido do dono, para a pontuacao inteira de 18 a 30.
    """
    consolo_antes = credito_do_dia(ja_creditado=0, valor=10).creditado
    resolucao_depois = credito_do_dia(
        ja_creditado=consolo_antes, valor=pontuacao
    ).creditado
    resolucao_antes = credito_do_dia(ja_creditado=0, valor=pontuacao).creditado
    consolo_depois = credito_do_dia(
        ja_creditado=resolucao_antes, valor=10
    ).creditado

    assert consolo_antes + resolucao_depois == pontuacao
    assert resolucao_antes + consolo_depois == pontuacao
    assert pontuacao > 10


def test_falhar_antes_NUNCA_paga_mais_que_resolver_de_primeira():
    """🔒 A queixa do dono (02/10/2026): na soma, 10 + 25 cortado dava 30, e a
    mesma partida de primeira dava 27. Com o piso, a de primeira vence."""
    de_primeira = credito_do_dia(ja_creditado=0, valor=27).creditado
    consolo = credito_do_dia(ja_creditado=0, valor=10).creditado
    na_segunda = consolo + credito_do_dia(ja_creditado=consolo, valor=25).creditado
    assert (de_primeira, na_segunda) == (27, 25)


def test_um_dia_ACIMA_do_teto_credita_zero_e_nao_recusa():
    """⚠️ Soma do dia errada chega aqui dentro da rota do envio - recusar faria o
    outbox tentar de novo ate desistir, por um defeito que ⛔ e da pessoa."""
    assert credito_do_dia(ja_creditado=45, valor=18).creditado == 0


def test_o_teto_e_o_do_PARAMETRO_e_nao_um_30_escrito_na_conta():
    """🔒 O teto e da colecao (RF-DES-155); um torneio pode ter outro."""
    assert credito_do_dia(ja_creditado=0, valor=30, teto=25).corte == 5
    # O teto vale mesmo com o dia ja comecado: 10 + o que falta para 25.
    assert credito_do_dia(ja_creditado=10, valor=30, teto=25).creditado == 15


def test_valor_negativo_e_defeito_de_quem_chamou():
    with pytest.raises(ValueError):
        credito_do_dia(ja_creditado=0, valor=-1)


# ═══════════════════════════════════════════════════════════════════════════
# 9. ⚠️ A SESSAO QUE VALE e a MAIOR entre a do app e a do servidor (T085zf)
# ═══════════════════════════════════════════════════════════════════════════
#
# O caso do dono (26/09/2026): errar tres vezes com a conta, sair dela, resolver
# como convidado - que comeca o dia do zero no aparelho - e entrar de novo. A
# resolucao chega "de primeira e sem dica"; o servidor viu as tres. As contas
# abaixo usam a resolucao PERFEITA no resto, para o numero esperado sair a mao
# (regua 1, a da §8zs - `12 + 18 x Q`, tentativas zerando na 4a, dica a 0,15):
#
#   4 tentativas: q_tentativas = 0    → perde 18 x 0,30 x 1 = 5,4 → 24,6 → 25
#   2 dicas:      q_dica = 0          → perde 18 x 0,15 x 1 = 2,7 → 27,3 → 27
#   as duas:      30 - 5,4 - 2,7 = 21,9 → 22


def _de_primeira(**trocas) -> EnvioDeResolucao:
    """O envio do convidado: 1a tentativa, sem dica, tudo cheio, 30 XP."""
    return _perfeito(**trocas)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("no_servidor", "esperado"),
    [((4, 0), 25), ((1, 2), 27), ((4, 2), 22)],
)
async def test_o_servidor_contou_MAIS_e_a_nota_desce(no_servidor, esperado):
    """A nota gravada, a creditada e a do quadro saem da contagem do servidor."""
    repo = RepoFalso(partida=_partida(), sessao_no_servidor=no_servidor)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_de_primeira()
    )

    assert repo.resolucoes[0]["nu_xp"] == esperado
    assert repo.creditos == [esperado]
    assert resultado.xp_creditado == esperado


@pytest.mark.asyncio
async def test_o_EXTRATO_mostra_a_contagem_do_servidor():
    """O Raio-X diz 4 tentativas e 2 dicas - e a parcela que desceu por elas."""
    repo = RepoFalso(partida=_partida(), sessao_no_servidor=(4, 2))

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_de_primeira()
    )

    tentativas, _tempo, dica = repo.extratos[0][1:4]
    assert tentativas.vr_medida == Decimal(4)
    # Na 4a tentativa a parcela zera (§8zs); era 1/4 com a regua `1/n`.
    assert tentativas.vr_normalizado == Decimal(0)
    assert dica.vr_medida == Decimal(2)
    assert dica.vr_normalizado == Decimal(0)


@pytest.mark.asyncio
async def test_o_servidor_contou_MENOS_e_vale_o_envio():
    """⛔ A menor nunca vence: a fila de outro aparelho pode nao ter chegado."""
    repo = RepoFalso(partida=_partida(), sessao_no_servidor=(1, 0))

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO,
        id_usuario=ID_USUARIO,
        envio=_envio(tentativas=3, dicas_usadas=1, pontuacao=26),
    )

    tentativas, _tempo, dica = repo.extratos[0][1:4]
    assert tentativas.vr_medida == Decimal(3)
    assert dica.vr_medida == Decimal(1)
    # A conta de [test_resolver_credita_a_pontuacao_do_SERVIDOR_inteira].
    assert repo.resolucoes[0]["nu_xp"] == 21


@pytest.mark.asyncio
async def test_sessao_IGUAL_e_o_numero_continua_sendo_o_do_SERVIDOR():
    """⚠️ **Mudou em 10/10/2026** (T103, §8zzo decisao 7).

    Ate ali, com a sessao igual, o servidor gravava a pontuacao do envio ao pe
    da letra - *"vale o aplicativo"*. Agora o XP do desafio e do servidor
    sempre: o envio diz 26 e o servidor grava os 21 da regua, e a resposta leva
    os 21 para a tela do app trocar a estimativa.
    """
    repo = RepoFalso(partida=_partida(), sessao_no_servidor=(3, 1))

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO,
        id_usuario=ID_USUARIO,
        envio=_envio(tentativas=3, dicas_usadas=1, qualidade=0.7325, pontuacao=26),
    )

    assert repo.resolucoes[0]["nu_xp"] == 21
    assert resultado.resposta.pontuacao == 21


@pytest.mark.asyncio
async def test_a_pergunta_e_sobre_ESTA_tentativa_e_ate_a_resolucao():
    """A sessao e contada ate a tentativa gravada e ate o instante do objetivo."""
    repo = RepoFalso(partida=_partida())

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_de_primeira()
    )

    assert repo.perguntas_da_sessao == [
        {
            "id_desafio_dia": ID_DIA,
            "id_usuario": ID_USUARIO,
            "id_tentativa": repo.ultima_tentativa,
            "ate": AGORA,
        }
    ]


@pytest.mark.asyncio
async def test_dicas_ACIMA_de_2_contam_TODAS():
    """⚠️ §8zzo, decisao 2: a nota conta todas as dicas de todas as tentativas.

    Ate 10/10/2026 o total era preso em 2 (o teto era do dia). Com 2 por
    tentativa, quem errou uma vez pode ter gastado 3 ou 4 - e o Raio-X diz 3.
    Na regua 1 a parcela ja estava zerada em 2, entao a nota e a mesma: 27.
    """
    repo = RepoFalso(partida=_partida(), sessao_no_servidor=(1, 3))

    await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_de_primeira()
    )

    assert repo.resolucoes[0]["nu_xp"] == 27
    assert repo.extratos[0][3].vr_medida == Decimal(3)


def test_o_envio_aceita_mais_de_2_dicas():
    """⚠️ Era `le=2` ate 10/10/2026: a 1.3.1 mandaria 3 e a fila descartaria o
    envio (422 = dado impossivel), levando a resolucao junto."""
    assert _envio(dicas_usadas=4).dicas_usadas == 4


@pytest.mark.asyncio
async def test_o_REENVIO_com_contagem_maior_continua_sem_creditar():
    """A resolucao que ja existia ⛔ muda - nem nota, nem credito."""
    repo = RepoFalso(
        partida=_partida(), resolucao_nova=False, sessao_no_servidor=(4, 2)
    )

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_de_primeira()
    )

    assert resultado.resposta.ja_existia is True
    assert repo.creditos == []
    assert repo.extratos == []


# ═══════════════════════════════════════════════════════════════════════════
# 10. ⚠️ A REGUA DA NOTA DO DIA (T103)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_o_dia_do_DESAFIO_escolhe_a_regua():
    """A versao de maior vigencia ate o `dt_dia` - e nao a do relogio.

    O mesmo envio, num dia da regua 1 e num da regua 2: os pesos do extrato
    mudam com o DIA do desafio.
    """
    antes = RepoFalso(partida=_partida(), dt_dia=date(2026, 10, 10))
    depois = RepoFalso(partida=_partida(), dt_dia=VIGENCIA_V2)

    for repo in (antes, depois):
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert antes.extratos[0][1].vr_peso == Decimal("0.300")
    assert depois.extratos[0][1].vr_peso == Decimal("0.500")
    # E o numero muda junto: 3 tentativas custam mais na regua 2.
    assert antes.resolucoes[0]["nu_xp"] != depois.resolucoes[0]["nu_xp"]


@pytest.mark.asyncio
async def test_sem_regua_para_o_dia_e_ERRO_DO_SERVIDOR_e_nao_400():
    """⛔ Sem valor padrao (RF-DES-223) - e ⚠️ **sem 400**.

    O app trata 400 como "desista do envio": a pessoa perderia a resolucao por
    um defeito que nao e dela. `ReguaDaNotaInvalida` vira 500, e a fila tenta de
    novo depois do conserto. E nada fica gravado pela metade.
    """
    repo = RepoFalso(partida=_partida(), linhas_das_reguas=[])

    with pytest.raises(ReguaDaNotaInvalida):
        await ServicoEnvio(repo).registrar_resolucao(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio()
        )

    assert repo.resolucoes == [] and repo.commits == 0
