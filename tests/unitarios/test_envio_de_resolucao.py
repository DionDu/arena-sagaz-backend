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
  · **o teto de duas dicas e por DESAFIO**, somando as tentativas do dia.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from api.desafios.credito_do_dia import credito_do_dia
from api.desafios.extrato_xp import (
    PESO_DICA,
    PESO_MERITO,
    PESO_TEMPO,
    PESO_TENTATIVAS,
    MedidaInvalida,
    montar_extrato,
    normalizar,
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
from api.desafios.servico_envio import (
    PartidaAindaNaoChegou,
    ServicoEnvio,
    TETO_DE_DICAS,
)
from api.nucleo.excecoes import ErroNegocio

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


def _extrato(*, medidas=None, pesos=None, **trocas):
    """`montar_extrato` com a sessao ja preenchida na MELHOR resolucao.

    Primeira tentativa, no piso do tempo, sem dica: assim cada caso piora so o
    que esta medindo, em vez de repetir seis argumentos.
    """
    base = dict(
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
    ) -> None:
        self._sem_regua = sem_regua
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
            "dt_dia": AGORA.date(),
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

    async def dicas_ja_gastas(self, *, id_desafio_dia, id_usuario):
        return self._dicas_gastas

    async def gravar_tentativa(self, **kwargs):
        self.tentativas.append(kwargs)
        return uuid4(), True

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


def test_pontuacao_fora_de_18_30_e_dado_invalido():
    """A faixa e de **um** desafio; o teto do dia e outra coisa (RF-DES-155)."""
    with pytest.raises(ValueError):
        _envio(pontuacao=31)
    with pytest.raises(ValueError):
        _envio(pontuacao=17)


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
    """`XP = 18 + 12 x Q`: os 18 sao a linha `base`.

    ⚠️ Ela nao tem `nu_feito`, e o `ck003_feito` da migracao exige que nao
    tenha.
    """
    base = _extrato()[0]
    assert base.vr_xp == Decimal(18)
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
    """⚠️ O cadeado barato: 0,30 + 0,20 + 0,25 + os 0,25 do merito repartidos.

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
    linha valia `12 x 0,600 = 7,2` onde devia valer `12 x 0,150 = 1,8`.
    """
    merito = _extrato(medidas={"damas_coroadas": Decimal(2)})[4]

    assert merito.vr_peso == PESO_MERITO * Decimal("0.600")
    assert merito.vr_peso == Decimal("0.150")
    assert merito.vr_xp == Decimal("1.800")


def test_as_tres_correm_ao_CONTRARIO_e_a_direcao_vem_da_dimensao():
    """⚠️ Mais tentativas, mais tempo e mais dicas dao MENOS XP.

    ⛔ E a inversao vem de `co_direcao`, nunca de um `1 -` escrito na formula:
    o caso troca a direcao na dimensao e a nota inverte junto. Uma parcela na
    direcao errada nao daria erro nenhum.
    """
    melhor = _extrato()
    assert [p.vr_normalizado for p in melhor[1:4]] == [Decimal(1)] * 3

    pior = _extrato(nu_tentativas=1000, nu_tempo_ms=TETO_MS, nu_dicas=2)
    assert pior[2].vr_normalizado == Decimal(0)
    assert pior[3].vr_normalizado == Decimal(0)
    assert pior[1].vr_normalizado < Decimal("0.01")

    # A dimensao mandando ao contrario: a nota acompanha.
    invertida = _extrato(
        nu_dicas=2, direcoes={**DIRECOES, "dicas_usadas": "maior_melhor"}
    )
    assert invertida[3].vr_normalizado == Decimal(1)


def test_piorar_nunca_aumenta_a_nota():
    """A propriedade, sem numero esperado nenhum — ela sobrevive a afinacao dos
    pesos em campo."""
    anterior = Decimal(2)
    for tentativas in (1, 2, 3, 4, 8, 20):
        q = qualidade_do_extrato(_extrato(nu_tentativas=tentativas))
        assert q < anterior
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
        {"nu_dicas": 3},
        {"nu_tempo_piso_ms": 60_000, "nu_tempo_teto_ms": 60_000},
        {"nu_tempo_piso_ms": 60_000, "nu_tempo_teto_ms": 30_000},
        {"direcoes": {}},
    ],
)
def test_numero_impossivel_de_sessao_e_medida_invalida(trocas):
    """⚠️ Zero tentativas daria `1/0`; regua degenerada divide por zero; e sem
    a direcao no catalogo nao ha como saber para que lado a parcela corre."""
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
    """A formula fechada: `Q = 1` leva a 18 + 12 = 30.

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


def test_a_pior_resolucao_ainda_paga_o_piso_de_18():
    """⚠️ Quem resolveu, resolveu (RF-DES-040).

    `Q` nao chega a zero exato porque a parcela de tentativas e `1/n`; o total
    arredonda para 18, que e o chao que o piso de 60% garante por construcao.
    """
    parcelas = _extrato(
        nu_tentativas=30,
        nu_tempo_ms=TETO_MS * 2,
        nu_dicas=2,
        medidas={"material_do_adversario": Decimal(12)},
    )
    total = sum(p.vr_xp for p in parcelas)
    assert Decimal(18) <= total < Decimal("18.5")
    assert round(total) == 18


# ════════════════════════════════════════════════════════════════════════════
# 4c. 🔒 O CASO DE OURO — a tabela do `data-model.md`, linha a linha
# ════════════════════════════════════════════════════════════════════════════


def test_o_caso_de_ouro_do_data_model():
    """*"Tentou, falhou, tentou de novo e resolveu em 74 s, sem dica, fechando as
    4 caixas e acertando 3 lances otimos de 6."*

    ⚠️ **E o MESMO caso do teste do aplicativo** (`qualidade_test.dart`, grupo
    "o caso de ouro"). Os dois lados calculam a mesma resolucao e tem de chegar
    ao mesmo numero — e a auditoria de RF-DES-032 que depende disso. Se um dia
    divergirem, o alerta do painel acende com razao.
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
        nu_tempo_ms=74_000,
        nu_dicas=0,
        nu_tempo_piso_ms=30_000,
        nu_tempo_teto_ms=180_000,
    )

    base, tentativas, tempo, dica, caixas, otimos = parcelas

    assert base.vr_xp == Decimal(18)
    assert tentativas.vr_normalizado == Decimal("0.5")
    assert tentativas.vr_xp == Decimal("1.800")
    # (180000 - 74000) / (180000 - 30000) = 0,70666...
    assert round(tempo.vr_normalizado, 4) == Decimal("0.7067")
    assert round(tempo.vr_xp, 3) == Decimal("1.696")
    assert dica.vr_xp == Decimal("3.000")
    assert caixas.vr_peso == Decimal("0.150")
    assert caixas.vr_xp == Decimal("1.800")
    assert otimos.vr_peso == Decimal("0.100")
    assert otimos.vr_normalizado == Decimal("0.5")
    assert otimos.vr_xp == Decimal("0.600")

    # ⚠️ O arredondamento acontece UMA vez, no fim: parcela a parcela daria 28.
    total = sum(p.vr_xp for p in parcelas)
    assert round(total, 3) == Decimal("26.896")
    assert round(total) == 27


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
async def test_o_teto_de_duas_dicas_e_por_DESAFIO():
    """⚠️ RF-DES-057, e a conta soma as tentativas do dia.

    Fechar o aplicativo encerra a tentativa, nao o dia — um contador por
    tentativa daria dicas infinitas a quem reabrisse.
    """
    repo = RepoFalso(partida=_partida(), dicas_gastas=TETO_DE_DICAS)

    with pytest.raises(ErroNegocio) as erro:
        await ServicoEnvio(repo).registrar_dica(
            id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_dica(grau=2)
        )

    assert erro.value.codigo == "teto_de_dicas"
    assert repo.dicas == []


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
# casos provam o credito, o consolo uma vez por dia e o teto de 30 como linha de
# ajuste - e que a conta do dia fecha igual em qualquer ordem de chegada.
# ═══════════════════════════════════════════════════════════════════════════


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
async def test_resolver_de_primeira_credita_a_pontuacao_INTEIRA():
    """O caso comum: sem consolo antes, 26 cabem nos 30 e ⛔ nao ha ajuste."""
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio(pontuacao=26)
    )

    assert resultado.xp_creditado == 26
    assert repo.creditos == [26]
    assert _linhas_do_tipo(repo, XP_AJUSTE) == []


@pytest.mark.asyncio
async def test_resolver_com_30_de_primeira_cabe_EXATO_no_teto():
    """🔒 A fronteira: 30 de 30 ⛔ e corte. Um `<` no lugar de `<=` cortaria 1."""
    repo = RepoFalso(partida=_partida())

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio(pontuacao=30)
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
async def test_falhar_e_depois_resolver_fecha_o_dia_em_30_com_AJUSTE():
    """🔒 O caso de ouro do `data-model.md`: 10 + 27 - 7 = 30.

    ⚠️ O `nu_xp` da resolucao continua 27 - e o que o quadro ordena. O teto e da
    colecao e mora no credito, ⛔ na pontuacao (RF-DES-155).
    """
    repo = RepoFalso(partida=_partida())
    servico = ServicoEnvio(repo)

    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )
    resultado = await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio(pontuacao=27)
    )

    assert repo.creditos == [10, 20]
    assert resultado.xp_creditado == 20
    assert repo.resolucoes[0]["nu_xp"] == 27
    [(ajuste, ancoras)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-7)
    # ⚠️ O ajuste e do DIA: nem resolucao, nem tentativa.
    assert ancoras["id_resolucao"] is None and ancoras["id_tentativa"] is None


@pytest.mark.asyncio
async def test_a_ORDEM_de_chegada_nao_muda_a_conta_do_dia():
    """⚠️ A fila do aparelho ⛔ garante ordem: resolucao antes, consolo depois.

    27 entra inteiro, e o consolo so cabe 3 - o dia fecha nos mesmos 30 e com o
    mesmo ajuste de -7.
    """
    repo = RepoFalso(partida=_partida())
    servico = ServicoEnvio(repo)

    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_envio(pontuacao=27)
    )
    await servico.registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert repo.creditos == [27, 3]
    assert sum(repo.creditos) == 30
    [(ajuste, _)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-7)


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
    """⚠️ O extrato continua dizendo a verdade: tentou (+10), e o teto cortou tudo.

    E o caso de quem resolveu com 30 em outro aparelho e falhou neste depois.
    """
    repo = RepoFalso(partida=_partida(), ja_creditado=30)

    resultado = await ServicoEnvio(repo).registrar_resolucao(
        id_desafio=ID_DESAFIO, id_usuario=ID_USUARIO, envio=_falha()
    )

    assert resultado.xp_creditado == 0
    [(ajuste, _)] = _linhas_do_tipo(repo, XP_AJUSTE)
    assert ajuste.vr_xp == Decimal(-10)


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
    ("ja_creditado", "valor", "corte"),
    [
        (0, 30, 0),  # a resolucao perfeita de primeira
        (10, 20, 0),  # consolo e resolucao que cabem EXATO
        (10, 21, 1),  # um ponto alem: a fronteira do corte
        (10, 27, 7),  # o exemplo do data-model
        (27, 10, 7),  # a mesma conta, na ordem inversa
        (30, 10, 10),  # o dia ja cheio corta tudo
    ],
)
def test_credito_do_dia_corta_so_o_que_passa_do_teto(ja_creditado, valor, corte):
    credito = credito_do_dia(ja_creditado=ja_creditado, valor=valor)
    assert credito.corte == corte
    assert credito.valor == valor, "⛔ o valor pontuado nunca e cortado"
    assert credito.creditado == valor - corte


def test_um_dia_ACIMA_do_teto_credita_zero_e_nao_recusa():
    """⚠️ Soma do dia errada chega aqui dentro da rota do envio - recusar faria o
    outbox tentar de novo ate desistir, por um defeito que ⛔ e da pessoa."""
    assert credito_do_dia(ja_creditado=45, valor=18).creditado == 0


def test_o_teto_e_o_do_PARAMETRO_e_nao_um_30_escrito_na_conta():
    """🔒 O teto e da colecao (RF-DES-155); um torneio pode ter outro."""
    assert credito_do_dia(ja_creditado=0, valor=30, teto=25).corte == 5


def test_valor_negativo_e_defeito_de_quem_chamou():
    with pytest.raises(ValueError):
        credito_do_dia(ja_creditado=0, valor=-1)
