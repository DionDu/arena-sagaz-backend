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

from api.desafios.extrato_xp import (
    MedidaInvalida,
    montar_extrato,
    normalizar,
    qualidade_do_extrato,
)
from api.desafios.modelos_envio import (
    EnvioDeDica,
    EnvioDeResolucao,
    FeitoMedido,
    OrigemDoEnvio,
)
from api.desafios.modelos_evento import XP_MEDIDA, XP_MERITO
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


def _pesos() -> list[dict]:
    """Os pesos de um desafio de damas, somando 1,000.

    ⚠️ Duas direcoes opostas de proposito: `damas_coroadas` e `maior_melhor`,
    `tempo_ate_resolver` e `menor_melhor`. E a inversao que os casos abaixo
    exercitam.
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
            "co_feito": "tempo_ate_resolver",
            "co_direcao": "menor_melhor",
            "nu_ordem": 2,
            "vr_peso": Decimal("0.400"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("10000"),
            "vr_max": Decimal("70000"),
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
        catalogo=("damas_coroadas", "tempo_ate_resolver", "tentativas"),
    ) -> None:
        self._dia = dia
        self._partida = partida
        self._resolucao_nova = resolucao_nova
        self._dicas_gastas = dicas_gastas
        self._catalogo = set(catalogo)

        self.tentativas: list[dict] = []
        self.resolucoes: list[dict] = []
        self.extratos: list[list] = []
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
    # base + os dois feitos que o desafio pesa.
    assert resultado.parcelas_gravadas == 3
    assert repo.commits == 1


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
    parcelas = montar_extrato(medidas={}, pesos=_pesos())

    # base + os dois pesos, mesmo sem nenhuma medida enviada.
    assert len(parcelas) == 3
    assert all(p.vr_medida == Decimal(0) for p in parcelas[1:])


def test_a_linha_base_vale_o_piso_e_nao_aponta_para_feito():
    """`XP = 18 + 12 x Q`: os 18 sao a linha `base`.

    ⚠️ Ela nao tem `nu_feito`, e o `ck003_feito` da migracao exige que nao tenha.
    """
    base = montar_extrato(medidas={}, pesos=_pesos())[0]
    assert base.vr_xp == Decimal(18)
    assert base.nu_feito is None


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

    parcelas = montar_extrato(medidas={"damas_coroadas": Decimal(2)}, pesos=pesos)

    assert parcelas[1].nu_tipo_xp == XP_MERITO
    assert parcelas[2].nu_tipo_xp == XP_MEDIDA
    assert parcelas[2].vr_xp == Decimal(0)


def test_q_cheio_paga_o_teto_de_30():
    """A formula fechada: `Q = 1` leva a 18 + 12 = 30."""
    parcelas = montar_extrato(
        medidas={
            "damas_coroadas": Decimal(2),
            "tempo_ate_resolver": Decimal(10000),
        },
        pesos=_pesos(),
    )
    assert qualidade_do_extrato(parcelas) == Decimal(1)
    assert sum(p.vr_xp for p in parcelas) == Decimal(30)


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
        montar_extrato(medidas={"capturas_extras": Decimal(2)}, pesos=pesos)


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
