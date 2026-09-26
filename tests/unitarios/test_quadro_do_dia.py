"""O QUADRO DO DIA E O REPLAY — T044 (contracts/quadro-do-dia.md).

O que estes casos protegem:

  · **as quatro regras que a tela nao pode contornar** — zero nunca aparece,
    fracao abaixo de 20 nao e servida, so quem resolveu aparece, `ic_publico`
    desligado some;
  · ⚠️ **o tempo dos mascotes e ENCENADO e DETERMINISTICO** — todo mundo ve o
    mesmo numero, e nenhum deles e instantaneo;
  · ⚠️ **`minha_linha` vem sempre**, mesmo fora do topo;
  · ⛔ **a trava de spoiler e do SERVIDOR** — 403, e nao um `if` na tela.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from api.desafios import mascotes
from api.desafios.mascotes import (
    PERSONAGENS,
    linha_do_mascote,
    linhas_dos_mascotes,
    taxas_das_medicoes,
)
from api.desafios.quadro import (
    MAXIMO_SEM_FRACAO,
    ContextoDoQuadro,
    fracao_servivel,
    replays_liberados,
)
from api.desafios.servico_quadro import ReplayTrancado, ServicoQuadro
from api.nucleo.excecoes import ErroNaoEncontrado

AGORA = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)
ENCERRA = datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc)
ID_DESAFIO = UUID("9f1c0000-0000-4000-8000-000000000001")
ID_DIA = uuid4()
EU = "uid-eu"


class RepoFalso:
    """Um `RepositorioQuadro` de mentira."""

    def __init__(
        self,
        *,
        gente=None,
        minha=None,
        fracao=(0, 0),
        reacoes=None,
        minhas_reacoes=None,
        oferecidas=None,
        medicoes=None,
        partida=None,
        lances=None,
        gabarito=None,
        tem_contexto=True,
        adversario="pita",
        jogo="pontinhos",
        modalidade=None,
        formato_posicao="sequencia_lances",
        posicao_inicial=None,
        extrato=None,
        quem_reagiu=None,
    ) -> None:
        self._adversario = adversario
        # `{id_resolucao: [linhas do SQL_QUEM_REAGIU]}` - por resolucao, para o
        # duplo honrar o filtro como os irmaos de reacao honram o `ids`.
        self._quem_reagiu = quem_reagiu or {}
        self._jogo = jogo
        self._modalidade = modalidade
        self._formato_posicao = formato_posicao
        self._posicao_inicial = posicao_inicial
        self._gente = gente or []
        self._minha = minha
        self._fracao = fracao
        self._reacoes = reacoes or {}
        self._minhas_reacoes = minhas_reacoes or {}
        # ⚠️ O padrao e as **cinco do Design**, e ⛔ nao uma lista vazia: vazia
        # faria todo caso existente afirmar que a tela ⛔ nao oferece nada.
        self._oferecidas = (
            ["palmas", "uau", "fogo", "coracao", "top"]
            if oferecidas is None
            else oferecidas
        )
        self._medicoes = medicoes or []
        self._partida = partida
        self._lances = lances
        self._gabarito = gabarito
        self._tem_contexto = tem_contexto
        self._extrato = extrato

    async def contexto(self, id_desafio):
        if not self._tem_contexto:
            return None
        return ContextoDoQuadro(
            id_desafio_dia=ID_DIA,
            id_desafio=id_desafio,
            dh_encerramento=ENCERRA,
            nu_tempo_piso_ms=8_000,
            nu_tempo_teto_ms=90_000,
            co_personagem_do_dia=self._adversario,
            co_jogo=self._jogo,
            co_modalidade=self._modalidade,
            co_formato_posicao=self._formato_posicao,
            js_posicao_inicial=self._posicao_inicial,
        )

    async def medicoes(self, id_desafio):
        return self._medicoes

    async def linhas_de_gente(self, id_desafio_dia):
        return self._gente

    async def minha_linha(self, *, id_desafio_dia, id_usuario):
        return self._minha if id_usuario == EU else None

    async def fracao(self, id_desafio_dia):
        return self._fracao

    async def reacoes(self, ids):
        # ⚠️ **O duplo HONRA o `ids`**, e ⛔ nao devolve o mapa inteiro: o SQL de
        # verdade tem `id_resolucao = ANY(:ids)`, e um duplo que ignora o filtro
        # responde por resolucoes que ⛔ nao foram perguntadas - foi assim que o
        # caso de quem se escondeu passou a ler a propria contagem.
        return {k: v for k, v in self._reacoes.items() if k in ids}

    async def reacoes_oferecidas(self):
        return self._oferecidas

    async def minhas_reacoes(self, ids, id_usuario):
        # ⚠️ Convidado ⛔ nao tem nenhuma - e a mesma regra do repositorio
        # de verdade, e ⛔ nao um atalho do duplo.
        if id_usuario is None:
            return {}
        # ⚠️ Mesmo filtro por `ids` do irmao acima, e pelo mesmo motivo.
        return {k: v for k, v in self._minhas_reacoes.items() if k in ids}

    async def partida_do_sujeito(self, *, id_desafio_dia, id_usuario):
        return self._partida

    async def lances(self, id_partida):
        if self._lances is not None:
            return self._lances
        return [{"nu_ordem": 1, "nu_jogador": 1, "co_lance": "H_0_1"}]

    async def extrato(self, id_resolucao):
        if self._extrato is not None:
            return self._extrato
        return [{"co_tipo_xp": "base", "vr_xp": 18}]

    async def gabarito(self, id_desafio):
        return self._gabarito

    async def quem_reagiu(self, id_resolucao):
        return self._quem_reagiu.get(id_resolucao, [])


def _jogador(*, nome="Ana", xp=28, tempo=41880, uid="uid-ana", id_res=None):
    return {
        "id_resolucao": id_res or uuid4(),
        "id_usuario": uid,
        "co_usuario": "k7m3p9rt",
        "no_exibicao": nome,
        "nu_xp": xp,
        "nu_tempo_ms": tempo,
        "dh_resolucao": AGORA,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 1. Os mascotes (RF-DES-060a/b/c)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_escada_esta_no_quadro_desde_00h():
    """⚠️ Regua que aparece aos poucos nao serve para medir.

    Um quadro sem o Tex as 9h contradiria, na tela ao lado, o "voce passou o
    Tex" que o aplicativo acabou de dizer.
    """
    linhas = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    )
    assert [m.co_personagem for m in linhas] == list(PERSONAGENS)


def test_o_adversario_do_dia_NAO_entra_na_escada():
    """⛔ RF-DES-203: ele nao joga contra si mesmo, logo nao e regua naquele dia.

    ⚠️ **Isto reescreve a leitura literal de RF-DES-060a** (*"os quatro estao no
    quadro"*), e a regra de precedencia da spec e explicita: onde os blocos
    discordarem, vale o **mais recente** — e RF-DES-203 e de 04/09/2026.
    """
    escada = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO,
        nu_tempo_piso_ms=8_000,
        nu_tempo_teto_ms=90_000,
        co_personagem_do_dia="magno",
    )
    nomes = [m.co_personagem for m in escada]

    assert len(nomes) == 3
    assert "magno" not in nomes
    assert nomes == ["cacau", "pita", "tex"]


def test_a_escada_RODA_junto_com_o_adversario():
    """⚠️ Em dia de Magno ela e mais encorajadora; em dia de Cacau, mais dura.

    Nao e um recorte qualquer: e o que mantem o alvo escalonado quando o
    adversario muda.
    """
    dia_de_magno = [
        m.co_personagem
        for m in linhas_dos_mascotes(
            id_desafio=ID_DESAFIO,
            nu_tempo_piso_ms=8_000,
            nu_tempo_teto_ms=90_000,
            co_personagem_do_dia="magno",
        )
    ]
    dia_de_cacau = [
        m.co_personagem
        for m in linhas_dos_mascotes(
            id_desafio=ID_DESAFIO,
            nu_tempo_piso_ms=8_000,
            nu_tempo_teto_ms=90_000,
            co_personagem_do_dia="cacau",
        )
    ]
    assert dia_de_magno == ["cacau", "pita", "tex"]
    assert dia_de_cacau == ["pita", "tex", "magno"]


def test_adversario_desconhecido_devolve_a_escada_INTEIRA():
    """⚠️ **A escada incompleta seria pior que escada nenhuma.**

    Um filtro que engolisse um nome desconhecido devolveria tres degraus quando
    deveria devolver quatro — e a pessoa leria "passei todo mundo" sem ter
    passado o que faltava aparecer.
    """
    escada = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO,
        nu_tempo_piso_ms=8_000,
        nu_tempo_teto_ms=90_000,
        co_personagem_do_dia="ninguem",
    )
    assert len(escada) == 4


def test_o_tempo_do_mascote_e_DETERMINISTICO():
    """⚠️ Todo mundo ve o mesmo numero.

    Com `random`, dois aparelhos veriam tempos diferentes para o mesmo mascote no
    mesmo dia, e a conversa "o Magno fez em 21 segundos" deixaria de fazer
    sentido.
    """
    a = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    )
    b = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    )
    assert [m.nu_tempo_ms for m in a] == [m.nu_tempo_ms for m in b]
    assert [m.nu_xp for m in a] == [m.nu_xp for m in b]


def test_desafios_diferentes_dao_encenacoes_diferentes():
    """A semente e o `id_desafio`: dois dias, dois quadros."""
    outro = UUID("9f1c0000-0000-4000-8000-000000000002")
    a = linhas_dos_mascotes(
        id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    )
    b = linhas_dos_mascotes(
        id_desafio=outro, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    )
    assert [m.nu_tempo_ms for m in a] != [m.nu_tempo_ms for m in b]


def test_o_sorteio_nao_usa_hash_do_python():
    """⛔ `hash()` e salgado por processo desde a 3.3.

    Dois reinicios do servidor dariam numeros diferentes para o mesmo desafio, e
    o tempo do Magno mudaria no meio do dia — sem nada no log.
    """
    fonte = mascotes._fracao_determinista.__doc__ or ""
    assert "SHA-256" in fonte
    # E a prova real: o valor e estavel entre chamadas, e conhecido.
    assert mascotes._fracao_determinista(
        ID_DESAFIO, "magno", "tempo"
    ) == mascotes._fracao_determinista(ID_DESAFIO, "magno", "tempo")


def test_xp_e_tempo_nao_saem_correlacionados():
    """⚠️ **O sal existe para isto.**

    Sem ele, o mascote com XP no topo da faixa teria sempre o tempo no topo da
    dele, e o padrao apareceria para quem olhasse dois dias seguidos.
    """
    assert mascotes._fracao_determinista(
        ID_DESAFIO, "magno", "xp"
    ) != mascotes._fracao_determinista(ID_DESAFIO, "magno", "tempo")


def test_nenhum_mascote_e_instantaneo():
    """⛔ RF-DES-060b, textual.

    Tempo zero levaria a parcela cheia de `Q` e **fecharia o topo**: ninguem
    passaria o Magno nunca, e a regua deixaria de ser regua.
    """
    for m in linhas_dos_mascotes(
        id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
    ):
        assert m.nu_tempo_ms >= 8_000


def test_a_escada_e_respeitada_na_media():
    """A Cacau demora e o Magno e rapido — a ordem que o produto promete."""
    m = {
        x.co_personagem: x
        for x in linhas_dos_mascotes(
            id_desafio=ID_DESAFIO, nu_tempo_piso_ms=8_000, nu_tempo_teto_ms=90_000
        )
    }
    assert m["cacau"].nu_tempo_ms > m["magno"].nu_tempo_ms
    assert m["cacau"].nu_tentativas > m["magno"].nu_tentativas


def test_a_taxa_medida_desloca_a_faixa():
    """⚠️ **O unico numero real da encenacao.**

    Um desafio em que o Magno so resolve 4 de 20 lhe da XP no pe da faixa —
    porque aquele desafio **e duro para ele**, e isso foi medido.
    """
    duro = linha_do_mascote(
        id_desafio=ID_DESAFIO,
        co_personagem="magno",
        nu_tempo_piso_ms=8_000,
        nu_tempo_teto_ms=90_000,
        taxa_medida=0.2,
    )
    facil = linha_do_mascote(
        id_desafio=ID_DESAFIO,
        co_personagem="magno",
        nu_tempo_piso_ms=8_000,
        nu_tempo_teto_ms=90_000,
        taxa_medida=1.0,
    )
    assert duro.nu_xp < facil.nu_xp


def test_o_xp_do_mascote_fica_na_faixa_do_desafio():
    """18–30 e a faixa de **um** desafio, e o `ck001_xp` da migracao a exige."""
    for taxa in (0.0, 0.5, 1.0):
        for nome in PERSONAGENS:
            linha = linha_do_mascote(
                id_desafio=ID_DESAFIO,
                co_personagem=nome,
                nu_tempo_piso_ms=8_000,
                nu_tempo_teto_ms=90_000,
                taxa_medida=taxa,
            )
            assert 18 <= linha.nu_xp <= 30


def test_mascote_desconhecido_falha_alto():
    """⚠️ Mascote novo entra em `FAIXAS`, ou nao aparece na regua."""
    with pytest.raises(ValueError):
        linha_do_mascote(
            id_desafio=ID_DESAFIO,
            co_personagem="ninguem",
            nu_tempo_piso_ms=8_000,
            nu_tempo_teto_ms=90_000,
        )


def test_a_taxa_e_calculada_e_nao_lida():
    """Guardar a divisao criaria um terceiro numero que pode discordar."""
    taxas = taxas_das_medicoes(
        [
            {"co_personagem": "magno", "nu_execucoes": 20, "nu_resolveu": 4},
            {"co_personagem": "cacau", "nu_execucoes": 0, "nu_resolveu": 0},
        ]
    )
    assert taxas == {"magno": 0.2}  # ⚠️ execucoes zero nao vira taxa zero


# ═══════════════════════════════════════════════════════════════════════════
# 2. As quatro regras (RF-DES-062 a 064, 077)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_fracao_so_sai_com_MAIS_de_10_resolvidos():
    """⛔ RF-DES-063: *"2 de 3 resolveram"* grita que o aplicativo tem 3 usuarios.

    O numero que isto esconde conta sobre o **tamanho da base**, e nao sobre a
    partida. ⚠️ Desde 24/09/2026 (§8z.11) o piso e de quem RESOLVEU: 10 ainda
    esconde, 11 mostra - e ⛔ importa quantos tentaram.
    """
    # O limite e escrito como NUMERO, e ⛔ lido da constante: um caso que lesse
    # `MAXIMO_SEM_FRACAO` passaria com qualquer valor que ela tivesse.
    assert MAXIMO_SEM_FRACAO == 10
    # 10 resolvidos, ainda que 500 tenham tentado: ⛔ sai.
    assert fracao_servivel(qt_pessoas=500, qt_resolveram=10) is None
    # 11 resolvidos, com 11 tentativas (abaixo do antigo piso de 20): sai.
    assert fracao_servivel(qt_pessoas=11, qt_resolveram=11) == {
        "tentaram": 11,
        "resolveram": 11,
    }
    assert fracao_servivel(qt_pessoas=480, qt_resolveram=132) == {
        "tentaram": 480,
        "resolveram": 132,
    }


@pytest.mark.asyncio
async def test_sem_ninguem_o_quadro_diz_texto_vazio_e_nunca_zero():
    """⛔ RF-DES-064: a tela mostra um convite, e nunca um `0`."""
    quadro = await ServicoQuadro(RepoFalso(fracao=(0, 0))).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )

    assert quadro["texto_vazio"] is True
    assert quadro["fracao"] is None
    # ⚠️ E a escada continua la: o quadro **nunca fica vazio**. Sao TRES, porque
    # o adversario do dia (a Pita, no duble) nao e regua (RF-DES-203).
    assert len(quadro["linhas"]) == 3
    assert "pita" not in [l.get("chave") for l in quadro["linhas"]]


@pytest.mark.asyncio
async def test_so_quem_resolveu_aparece():
    """⛔ RF-DES-062: falhar e privado.

    A tentativa sem sucesso existe no banco e **nunca** no quadro — e a consulta
    le `vw003_resolucao`, que so tem quem resolveu.
    """
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador()], fracao=(30, 1))
    ).montar(id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA)

    jogadores = [l for l in quadro["linhas"] if l["sujeito"] == "jogador"]
    assert len(jogadores) == 1
    assert jogadores[0]["nome"] == "Ana"


@pytest.mark.asyncio
async def test_zero_reacoes_vem_como_null():
    """⛔ RF-DES-073: a tela nao mostra "0 👏"."""
    quadro = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )
    jogador = next(l for l in quadro["linhas"] if l["sujeito"] == "jogador")
    assert jogador["reacoes"] is None


@pytest.mark.asyncio
async def test_mascote_nao_recebe_reacao():
    """⛔ RF-DES-060c — e e **estrutura**, nao `if` na tela.

    Reacao aponta para resolucao, e mascote nao tem resolucao.
    """
    quadro = await ServicoQuadro(RepoFalso()).montar(
        id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA
    )
    for linha in quadro["linhas"]:
        if linha["sujeito"] == "mascote":
            assert linha["reacoes"] is None
            assert linha["pode_reagir"] is False


@pytest.mark.asyncio
async def test_ninguem_reage_a_si_mesmo():
    """⚠️ E reagir exige conta (RF-DES-084): sem identidade nao ha como honrar
    "uma reacao por pessoa"."""
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador(uid=EU), _jogador(uid="outro", nome="Bia")])
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    por_uid = {
        l["id"]: l for l in quadro["linhas"] if l["sujeito"] == "jogador"
    }
    assert por_uid[EU]["pode_reagir"] is False
    assert por_uid["outro"]["pode_reagir"] is True


@pytest.mark.asyncio
async def test_a_propria_linha_SABE_que_e_a_propria():
    """⚠️ T085e: a linha de quem olha vem com `eu: true`, e SO ela.

    Sem o campo, o aplicativo reconhecia a propria linha pela posicao de
    `minha_linha`, e o toque nela abria o Raio-X com a pessoa repetida como
    terceiro sujeito.
    """
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador(uid=EU), _jogador(uid="outro", nome="Bia")])
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    minhas = [l for l in quadro["linhas"] if l["eu"]]
    assert [l["id"] for l in minhas] == [EU]
    # ⚠️ O campo existe em TODA linha, mascote inclusive: uma linha com forma
    # diferente obrigaria a tela a olhar o sujeito antes de ler.
    outras = [l for l in quadro["linhas"] if l not in minhas]
    assert any(l["sujeito"] == "mascote" for l in outras)
    assert all(l["eu"] is False for l in outras)


@pytest.mark.asyncio
async def test_convidado_NAO_tem_linha_propria():
    """⛔ Sem identidade, ⛔ nenhuma linha e `eu` - nem a de quem nao tem id."""
    quadro = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )
    assert all(l["eu"] is False for l in quadro["linhas"])


@pytest.mark.asyncio
async def test_quem_se_escondeu_NAO_marca_a_linha_de_outra_pessoa():
    """⚠️ O caso que a posicao errava: a propria linha ⛔ esta na lista.

    A `minha_linha` continua vindo (a pessoa se ve na barra), e a posicao dela
    cai sobre a linha de OUTRA pessoa - que o aplicativo pintava de ouro com o
    nome de quem olha. Com `eu`, ⛔ nenhuma linha da lista e a propria.
    """
    minha = _minha()
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador(uid="outra", nome="Bia")], minha=minha)
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    assert quadro["minha_linha"] is not None
    assert all(l["eu"] is False for l in quadro["linhas"])


@pytest.mark.asyncio
async def test_a_propria_linha_TRAZ_as_reacoes_que_recebeu():
    """⚠️ A barra ancorada mostra quem aplaudiu VOCE (T078).

    ⛔ **Sem este campo a barra sairia sempre sem pilha para quem esta FORA do
    topo** - justamente a unica pessoa para quem a barra existe. Quem esta no
    topo tem a linha na lista, e a pilha dela; quem esta em 74o ⛔ nao tem outra
    linha em lugar nenhum.
    """
    minha = _minha()
    quadro = await ServicoQuadro(
        RepoFalso(
            gente=[_jogador(uid=EU, id_res=minha["id_resolucao"])],
            minha=minha,
            reacoes={minha["id_resolucao"]: {"fogo": 4}},
        )
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    assert quadro["minha_linha"]["reacoes"] == {"fogo": 4}


@pytest.mark.asyncio
async def test_a_propria_linha_SEM_reacao_vem_null_e_nao_mapa_vazio():
    """⛔ RF-DES-073 vale para a propria linha tambem.

    ⚠️ E um `{}` ⛔ nao seria igual: em Dart um mapa vazio e verdadeiro o
    suficiente para desenhar a moldura de uma pilha **vazia**, que e o "0 👏"
    entrando pela porta de tras.
    """
    minha = _minha()
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador(uid=EU, id_res=minha["id_resolucao"])], minha=minha)
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    assert quadro["minha_linha"]["reacoes"] is None


@pytest.mark.asyncio
async def test_quem_se_escondeu_nao_le_a_contagem_da_propria_linha():
    """⚠️ Sair do quadro e sair inclusive da contagem que se ve (RF-DES-077).

    ⚠️ **E ⛔ nao ha `if` de visibilidade aqui**: a propria linha vem de
    `minha_linha`, que ⛔ nao passa pela clausula de publico (ela existe para a
    pessoa se ver mesmo em 74o), e as reacoes vem do mapa montado sobre as linhas
    **publicas**. Quem se escondeu ⛔ nao esta nesse mapa, e a chave falta.
    """
    minha = _minha()
    quadro = await ServicoQuadro(
        # ⚠️ `gente` **sem** a propria linha e exatamente o que o SQL do quadro
        # devolve para quem desligou a visibilidade.
        RepoFalso(
            gente=[_jogador(uid="outra", nome="Bia")],
            minha=minha,
            reacoes={minha["id_resolucao"]: {"palmas": 9}},
        )
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)

    assert quadro["minha_linha"]["reacoes"] is None


@pytest.mark.asyncio
async def test_o_quadro_diz_quais_reacoes_a_tela_pode_OFERECER():
    """⚠️ Sem isto, desativar uma reacao ⛔ nao teria efeito em campo (T078).

    O aplicativo publicado continuaria desenhando o botao, e cada toque levaria
    **400** da rota de reagir - que le o mesmo `ic_ativo`. Um botao que o desenho
    promete e o servidor recusa.
    """
    quadro = await ServicoQuadro(RepoFalso()).montar(
        id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA
    )
    assert quadro["reacoes_oferecidas"] == [
        "palmas",
        "uau",
        "fogo",
        "coracao",
        "top",
    ]


@pytest.mark.asyncio
async def test_a_ordem_das_oferecidas_e_a_DO_BANCO():
    """⚠️ `nu_ordem` e o desenho do Design, e ⛔ nao alfabetica.

    ⛔ **A tela ⛔ nao reordena**: se ela ordenasse, o `nu_ordem` da dimensao
    deixaria de significar coisa nenhuma, e trocar a ordem do seletor passaria a
    exigir versao nova do aplicativo.
    """
    quadro = await ServicoQuadro(
        RepoFalso(oferecidas=["top", "palmas"])
    ).montar(id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA)
    assert quadro["reacoes_oferecidas"] == ["top", "palmas"]


@pytest.mark.asyncio
async def test_o_convidado_tambem_recebe_o_catalogo():
    """⚠️ Ele ⛔ nao reage, e a lista ⛔ nao muda por causa disso.

    ⚠️ **Quem decide se ha alvo de toque e `pode_reagir`, linha por linha** - e
    ⛔ nao a ausencia do catalogo. Servir uma lista vazia ao convidado juntaria
    duas perguntas diferentes ("o que existe?" e "eu posso?") num campo so, e a
    segunda ja tem resposta propria em cada linha.
    """
    quadro = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )
    assert quadro["reacoes_oferecidas"] == [
        "palmas",
        "uau",
        "fogo",
        "coracao",
        "top",
    ]


@pytest.mark.asyncio
async def test_convidado_ve_o_quadro_e_nao_pode_reagir():
    """⚠️ Ver e social; ter linha e reagir exigem identidade."""
    quadro = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )
    assert quadro["minha_linha"] is None
    assert all(
        l["pode_reagir"] is False
        for l in quadro["linhas"]
        if l["sujeito"] == "jogador"
    )


def test_o_filtro_de_ic_publico_e_o_MESMO_do_ranking_global():
    """⚠️ Duas definicoes de "aparece em publico" divergiriam, e a mais frouxa
    mandaria."""
    from api.desafios.quadro import SQL_LINHAS_DE_GENTE

    assert "ic_visivel_placar" in SQL_LINHAS_DE_GENTE
    assert "ic_idade_minima_declarada" in SQL_LINHAS_DE_GENTE


def test_a_minha_linha_NAO_filtra_por_ic_publico():
    """⚠️ `ic_publico` e sobre **os outros** verem, e nao sobre a pessoa se ver.

    Filtrar aqui faria quem desligou a visibilidade concluir que perdeu o XP.
    """
    from api.desafios.quadro import SQL_MINHA_LINHA

    assert "ic_visivel_placar" not in SQL_MINHA_LINHA


def test_a_fracao_conta_PESSOAS_e_nao_tentativas():
    """⚠️ Tentar e ilimitado no dia.

    `COUNT(*)` faria *"3 de 40"* onde ha 3 de 12 pessoas — e o numero pareceria
    catastrofico.
    """
    from api.desafios.quadro import SQL_FRACAO

    assert "COUNT(DISTINCT id_usuario)" in SQL_FRACAO


# ═══════════════════════════════════════════════════════════════════════════
# 3. `minha_linha` (RF-DES-069)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_minha_linha_vem_mesmo_fora_do_topo():
    """⚠️ Um quadro que corta justamente quem esta lendo desmotiva pelo mecanismo
    que o PRD §8 passa o documento inteiro combatendo."""
    muita_gente = [
        _jogador(uid=f"uid-{n}", nome=f"P{n}", xp=30, tempo=1000 + n)
        for n in range(120)
    ]
    repo = RepoFalso(
        gente=muita_gente,
        minha={
            "id_resolucao": uuid4(),
            "nu_xp": 22,
            "nu_tempo_ms": 92300,
            "dh_resolucao": AGORA,
        },
        fracao=(120, 120),
    )

    quadro = await ServicoQuadro(repo).montar(
        id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA
    )

    assert quadro["minha_linha"] is not None
    assert quadro["minha_linha"]["xp"] == 22
    # ⚠️ A posicao e sobre a lista INTEIRA, e nao sobre o topo recortado.
    assert quadro["minha_linha"]["posicao"] > 50
    # E o topo continua cortado.
    assert len(quadro["linhas"]) <= 54


@pytest.mark.asyncio
async def test_a_ordem_e_por_xp_com_tempo_desempatando():
    """RF-DES-061. ⚠️ Os mascotes entram na MESMA lista.

    Uma lista separada faria a tela ter de intercalar as duas — e "voce passou o
    Tex" deixaria de ser uma leitura da ordem.
    """
    quadro = await ServicoQuadro(
        RepoFalso(gente=[_jogador(xp=30, tempo=9999)], fracao=(30, 1))
    ).montar(id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA)

    xps = [l["xp"] for l in quadro["linhas"]]
    assert xps == sorted(xps, reverse=True)
    # ⚠️ Gente e mascote na mesma lista, ordenados juntos.
    assert {l["sujeito"] for l in quadro["linhas"]} == {"mascote", "jogador"}


# ═══════════════════════════════════════════════════════════════════════════
# 4. ⛔ A trava de spoiler (SC-009)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_trava_abre_por_resolver_ou_por_o_dia_acabar():
    """⚠️ **Duas portas, e qualquer uma basta.**

    A primeira e o efeito desejado — resolver **desbloqueia** o conteudo social;
    a segunda existe porque, encerrado o dia, nao ha mais o que estragar.
    """
    assert replays_liberados(
        resolveu_hoje=True, dh_encerramento=ENCERRA, agora=AGORA
    )
    assert replays_liberados(
        resolveu_hoje=False,
        dh_encerramento=ENCERRA,
        agora=ENCERRA + timedelta(minutes=1),
    )
    assert not replays_liberados(
        resolveu_hoje=False, dh_encerramento=ENCERRA, agora=AGORA
    )


@pytest.mark.asyncio
async def test_quem_nao_resolveu_leva_403_no_replay():
    """⛔ **A trava e do SERVIDOR.**

    Esconder so na tela deixaria o dado a um `curl` de distancia, e o quadro
    viraria gabarito.
    """
    with pytest.raises(ReplayTrancado) as erro:
        await ServicoQuadro(RepoFalso()).replay(
            id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
        )
    assert erro.value.status_http == 403


@pytest.mark.asyncio
async def test_403_e_nao_404_porque_o_replay_EXISTE():
    """⚠️ Um 404 faria a tela dizer "nao encontrado" para algo que esta la, e a
    pessoa concluiria que o aplicativo perdeu a partida dela."""
    with pytest.raises(ReplayTrancado) as erro:
        await ServicoQuadro(RepoFalso()).replay(
            id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=None, agora=AGORA
        )
    assert erro.value.codigo == "replay_trancado"


@pytest.mark.asyncio
async def test_quem_resolveu_ve_o_replay_com_o_extrato_inteiro():
    """⚠️ **O extrato vem INTEIRO no Raio-X** (RF-DES-177), e so as linhas que
    pontuaram na tela de resultado. E o **mesmo dado** nos dois lugares."""
    repo = RepoFalso(
        minha={"id_resolucao": uuid4(), "nu_xp": 26, "nu_tempo_ms": 40000,
               "dh_resolucao": AGORA},
        partida={
            "id_resolucao": uuid4(),
            "id_usuario": EU,
            "id_partida": uuid4(),
            "co_jogo": "pontinhos",
            # ⚠️ O dublê espelha as colunas do `SELECT`: ler por chave (e ⛔ nao
            # por `.get`) faz uma coluna esquecida no SQL estourar aqui, em vez
            # de virar um `None` silencioso na tela.
            "nu_lance_cumpre_desafio": 5,
        },
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["lances"]
    assert replay["extrato"]


def _partida_concluida() -> dict:
    """A linha de uma partida de desafio que acabou, como o `SELECT` a traz."""
    return {
        "id_resolucao": uuid4(),
        "id_usuario": "uid-ana",
        "id_partida": uuid4(),
        "co_jogo": "pontinhos",
        "nu_lance_cumpre_desafio": 5,
    }


#: O extrato como o DRIVER o entrega: as colunas sao `NUMERIC`, e chegam ao
#: Python como `Decimal`, com as 3 (ou 4) casas da coluna.
EXTRATO_DO_BANCO = [
    {"co_tipo_xp": "base", "co_feito": None, "co_unidade": None,
     "co_direcao": None, "vr_medida": None, "vr_normalizado": None,
     "vr_peso": None, "vr_xp": Decimal("18.000")},
    {"co_tipo_xp": "tentativas", "co_feito": "tentativas",
     "co_unidade": "contagem", "co_direcao": "menor_melhor",
     "vr_medida": Decimal("2.000"), "vr_normalizado": Decimal("0.5000"),
     "vr_peso": Decimal("0.300"), "vr_xp": Decimal("1.800")},
]


@pytest.mark.asyncio
async def test_o_extrato_sai_como_NUMERO_pela_rota_HTTP(
    cliente_http, monkeypatch
):
    """⛔ T085l: o extrato do Raio-X ⛔ funcionou NUNCA no aparelho.

    As colunas do extrato sao `NUMERIC`; o driver as entrega como `Decimal`; e a
    rota devolve um `dict` sem modelo — o FastAPI (pydantic 2) escreve `Decimal`
    como TEXTO, `"vr_xp": "18.000"`. O aplicativo exigia numero, descartou
    todas as parcelas, e o dono viu *"Total +0"* no iPhone.

    ⚠️ **Por que pela rota HTTP, e ⛔ pelo servico direto:** o defeito ⛔ esta no
    servico nem no repositorio — esta na SERIALIZACAO, que so acontece na
    resposta. Todo caso deste arquivo chamava `ServicoQuadro(...).replay(...)`
    com um duble que ja devolvia `int`, e os dois erros se escondiam um atras do
    outro (`memory/fonte-falsa-nao-tem-rota`). Aqui o duble devolve `Decimal`,
    como o banco, e o que se confere e o JSON que sai.
    """
    from api.desafios import rotas
    from api.main import app
    from api.nucleo.dependencias_conta_nuvem import usuario_opcional

    repo = RepoFalso(partida=_partida_concluida(), extrato=EXTRATO_DO_BANCO)
    # `dependency_overrides` troca uma dependencia do FastAPI por outra funcao:
    # o servico vem do duble, e o convidado ⛔ precisa de banco para existir.
    app.dependency_overrides[rotas.obter_servico_quadro] = (
        lambda: ServicoQuadro(repo)
    )
    app.dependency_overrides[usuario_opcional] = lambda: None
    # O dia ja encerrou: a trava de spoiler abre para qualquer um.
    monkeypatch.setattr(rotas, "agora_utc", lambda: ENCERRA + timedelta(hours=1))
    try:
        resposta = await cliente_http.get(
            f"/v1/desafios/{ID_DESAFIO}/replay/jogador/uid-ana",
            headers={"X-App-Version": "1.3.0", "X-Platform": "android"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resposta.status_code == 200, resposta.text
    base, tentativas = resposta.json()["extrato"]

    # ⚠️ NUMERO, e ⛔ texto — e inteiro quando o valor e inteiro, como o
    # contrato escreve (`contracts/raio-x.md`: `"vr_xp": 18`).
    assert base["vr_xp"] == 18 and isinstance(base["vr_xp"], int)
    assert tentativas["vr_medida"] == 2 and isinstance(tentativas["vr_medida"], int)
    assert tentativas["vr_xp"] == 1.8 and isinstance(tentativas["vr_xp"], float)
    assert tentativas["vr_normalizado"] == 0.5
    assert tentativas["vr_peso"] == 0.3
    # O que ⛔ e numero passa intacto.
    assert base["vr_medida"] is None
    assert tentativas["co_feito"] == "tentativas"


def test_o_Decimal_vira_inteiro_so_quando_E_inteiro():
    """⚠️ `18.000` e `18`, mas `18.500` ⛔ e `18` — cortar as casas mentiria."""
    from api.desafios.servico_quadro import numero_para_o_json

    assert numero_para_o_json(Decimal("18.000")) == 18
    assert isinstance(numero_para_o_json(Decimal("18.000")), int)
    assert numero_para_o_json(Decimal("18.500")) == 18.5
    assert numero_para_o_json(Decimal("-7.000")) == -7
    assert numero_para_o_json(Decimal("0.0001")) == 0.0001
    # ⛔ O que ⛔ e `Decimal` ⛔ se toca.
    assert numero_para_o_json("18.000") == "18.000"
    assert numero_para_o_json(None) is None


@pytest.mark.asyncio
async def test_partida_ABERTA_tem_replay_ate_o_objetivo():
    """⚠️ T085f: quem cumpriu e deixou a partida aberta VE o replay e o XP.

    Decisao do dono, 23/09/2026 (`DECISOES-do-dono.md` §8w.1 - muda o
    RF-DES-187/SC-024). Ate entao a rota respondia 404 `partida_em_andamento`,
    e a pessoa lia *"o replay aparece quando ela fechar"* por ate 7 dias.

    ⚠️ O que subiu de uma partida aberta e a **leva do objetivo** (RF-DES-213):
    os lances ate o instante em que o objetivo caiu. Entao o replay termina na
    estrela - ⛔ ha aviso a dar, porque ⛔ falta a parte que decidiu o desafio.
    """
    # A pessoa cumpriu no 7o meio-lance e parou ali: sobem os lances 1 a 7, e a
    # partida fica `em_andamento` (o job de expiracao a fecha em 7 dias).
    repo = RepoFalso(
        minha={"id_resolucao": uuid4(), "nu_xp": 26, "nu_tempo_ms": 40000,
               "dh_resolucao": AGORA},
        partida={
            "id_resolucao": uuid4(),
            "id_usuario": EU,
            "id_partida": uuid4(),
            "co_jogo": "damas",
            "nu_lance_cumpre_desafio": 7,
        },
        lances=_lances(1, 7),
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    # Os sete lances que subiram, e ⛔ uma recusa.
    assert [lance["nu_ordem"] for lance in replay["lances"]] == list(range(1, 8))
    # ⚠️ A barra diz *"lance 7 de 7"* com a estrela no ultimo: o tamanho sai do
    # ultimo lance que subiu, como na partida fechada - ⛔ ha regra propria.
    assert replay["nu_lances"] == 7
    assert replay["nu_lance_objetivo"] == 7
    assert replay["truncado"] is False
    # E o XP: o extrato e o que ela ganhou no objetivo, que abandonar ⛔ desfaz.
    assert replay["extrato"]


@pytest.mark.asyncio
async def test_o_gabarito_so_sai_com_a_trava_aberta():
    """⛔ O gabarito e o spoiler de graca (RF-DES-076): chega so em D+1 — ou
    depois de a pessoa resolver."""
    repo = RepoFalso(gabarito={"js_solucao": {"lances": ["18-22"]},
                               "nu_lances_solucao": 1})

    with pytest.raises(ReplayTrancado):
        await ServicoQuadro(repo).replay(
            id_desafio=ID_DESAFIO, sujeito="desafio", id_usuario=None,
            agora=AGORA,
        )

    # Dia encerrado: abre.
    aberto = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=None,
        agora=ENCERRA + timedelta(minutes=1),
    )
    assert aberto["lances"] == {"lances": ["18-22"]}
    # ⚠️ **A solucao de referencia nao disputa o quadro** (RF-DES-078a): ela nao
    # tem tentativas nem dica, e um sujeito que nasce com nota cheia tornaria a
    # disputa decorativa.
    assert aberto["extrato"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 4b. ⚠️ O "resolvi" do aplicativo abre a trava (T085ze, §8ze.4)
# ═══════════════════════════════════════════════════════════════════════════
#
# A resolucao do CONVIDADO espera o login na fila do aparelho (RF-DES-083), e a
# de quem tem conta espera a fila subir: nos dois casos a pessoa resolveu, e a
# trava a tratava como quem ⛔ resolveu. O dono: *"O Convidado nao pode ver
# resolucoes (outros jogadores e oficial) antes de ter resolvido o desafio"* -
# e, resolvido, ve.


@pytest.mark.asyncio
async def test_o_convidado_que_DECLARA_ter_resolvido_ve_a_solucao_oficial():
    """⚠️ Sem conta e sem resolucao no banco: a palavra do aplicativo basta."""
    repo = RepoFalso(gabarito={"js_solucao": {"lances": ["18-22"]},
                               "nu_lances_solucao": 1})

    aberto = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=None,
        agora=AGORA,
        declarou_resolver=True,
    )

    assert aberto["lances"] == {"lances": ["18-22"]}


@pytest.mark.asyncio
async def test_o_convidado_que_NAO_declara_continua_trancado():
    """⛔ A trava continua sendo trava: sem resolver, ⛔ ha solucao no dia D."""
    repo = RepoFalso(gabarito={"js_solucao": {"lances": ["18-22"]},
                               "nu_lances_solucao": 1})

    with pytest.raises(ReplayTrancado):
        await ServicoQuadro(repo).replay(
            id_desafio=ID_DESAFIO, sujeito="desafio", id_usuario=None,
            agora=AGORA,
        )


@pytest.mark.asyncio
async def test_a_conta_com_a_resolucao_AINDA_NA_FILA_tambem_ve():
    """⚠️ Quem tem conta e resolveu, com a fila por subir: o banco ⛔ tem a
    linha dela, e a declaracao abre do mesmo jeito."""
    repo = RepoFalso(gabarito={"js_solucao": {"lances": ["18-22"]},
                               "nu_lances_solucao": 1})

    aberto = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=EU,
        agora=AGORA,
        declarou_resolver=True,
    )

    assert aberto["lances"] == {"lances": ["18-22"]}


@pytest.mark.asyncio
async def test_no_quadro_a_declaracao_abre_a_trava_e_NAO_poe_linha():
    """⚠️ `replays_liberados` abre; `minha_linha` e `eu` continuam do BANCO.

    ⛔ O convidado ⛔ aparece no quadro (RF-DES-081, §8ze.1) - declarar ter
    resolvido abre o que ele pode VER, e ⛔ o poe onde os outros veem.
    """
    quadro = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO,
        id_usuario=None,
        agora=AGORA,
        declarou_resolver=True,
    )

    assert quadro["replays_liberados"] is True
    assert quadro["minha_linha"] is None
    assert all(l["eu"] is False for l in quadro["linhas"])

    sem_declarar = await ServicoQuadro(RepoFalso(gente=[_jogador()])).montar(
        id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
    )
    assert sem_declarar["replays_liberados"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("resolvi", [True, False])
async def test_as_ROTAS_repassam_o_resolvi_ao_servico(resolvi):
    """⚠️ As duas rotas levam o `?resolvi` ao servico - um parametro que a rota
    lesse e ⛔ repassasse deixaria a trava fechada com o servico certo."""
    from api.desafios.rotas import quadro_do_dia, replay_do_sujeito
    from api.nucleo.dependencias import ContextoRequisicao

    class Espiao:
        def __init__(self):
            self.pedidos = []

        async def montar(self, **kw):
            self.pedidos.append(kw)
            return {}

        async def replay(self, **kw):
            self.pedidos.append(kw)
            return {}

    espiao = Espiao()
    contexto = ContextoRequisicao(versao_app="1.2.0", plataforma="ios", idioma="pt")
    await quadro_do_dia(
        id_desafio=ID_DESAFIO, servico=espiao, dono=None, _contexto=contexto,
        resolvi=resolvi,
    )
    await replay_do_sujeito(
        id_desafio=ID_DESAFIO, sujeito="desafio", servico=espiao, dono=None,
        _contexto=contexto, resolvi=resolvi,
    )

    assert [p["declarou_resolver"] for p in espiao.pedidos] == [resolvi, resolvi]


def test_sem_o_parametro_a_trava_fica_como_sempre():
    """⚠️ O aplicativo publicado antes da T085ze ⛔ manda o `resolvi`: ausente
    tem de valer `False`, e ⛔ abrir."""
    from api.desafios.rotas import RESOLVI

    assert RESOLVI.default is False


@pytest.mark.asyncio
async def test_desafio_inexistente_e_404():
    """Sem dia, nao ha quadro."""
    with pytest.raises(ErroNaoEncontrado):
        await ServicoQuadro(RepoFalso(tem_contexto=False)).montar(
            id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
        )
# ═══════════════════════════════════════════════════════════════════════════
# 5. ⚠️ O que a BARRA do replay precisa saber (T073a)
# ═══════════════════════════════════════════════════════════════════════════
#
# Tres numeros, e ⛔ nenhum deles e coluna nova: onde o objetivo caiu, onde o
# registro comeca e quantos lances a partida teve **inteira**.


def _repo_com_partida(lances=None, nu_lance=7):
    """Um repositorio com uma resolucao fechada e os lances que se quiser."""
    return RepoFalso(
        minha={"id_resolucao": uuid4(), "nu_xp": 26, "nu_tempo_ms": 40000,
               "dh_resolucao": AGORA},
        partida={
            "id_resolucao": uuid4(),
            "id_usuario": EU,
            "id_partida": uuid4(),
            "co_jogo": "damas",
            "nu_lance_cumpre_desafio": nu_lance,
        },
        lances=lances,
    )


def _lances(de, ate):
    """Meios-lances numerados de `de` a `ate`, como o log os guarda."""
    return [
        {"nu_ordem": n, "nu_jogador": 1 + (n % 2), "co_lance": f"18-2{n % 10}"}
        for n in range(de, ate + 1)
    ]


@pytest.mark.asyncio
async def test_o_replay_diz_ONDE_o_objetivo_caiu():
    """⚠️ RF-DES-213/214: o instante do cumprido e o `nu_ordem` da jogada.

    E a estrela da barra. Sem ele a barra so saberia dizer *"lance 7 de 12"* —
    e o lance que **explica** a resolucao seria indistinguivel dos outros onze.
    """
    replay = await ServicoQuadro(_repo_com_partida(_lances(1, 12))).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["nu_lance_objetivo"] == 7


@pytest.mark.asyncio
async def test_quem_NAO_cumpriu_nao_tem_estrela():
    """⚠️ `nu_lance_cumpre_desafio` vem `NULL` de quem tentou e nao resolveu.

    ⛔ Um zero no lugar do nulo desenharia a estrela no lance zero — uma
    afirmacao falsa, e ⛔ nao um compartimento vazio.
    """
    replay = await ServicoQuadro(
        _repo_com_partida(_lances(1, 12), nu_lance=None)
    ).replay(id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA)

    assert replay["nu_lance_objetivo"] is None


@pytest.mark.asyncio
async def test_partida_INTEIRA_nao_esta_truncada():
    """O caso comum: 99% dos desafios cabem no teto (RF-DES-039)."""
    replay = await ServicoQuadro(_repo_com_partida(_lances(1, 12))).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["truncado"] is False
    assert replay["nu_primeiro_lance"] == 1
    assert replay["nu_lances"] == 12


@pytest.mark.asyncio
async def test_o_truncamento_sai_da_NUMERACAO_e_nao_de_uma_coluna():
    """⚠️ **O teto corta o COMECO, e a numeracao nao se refaz.**

    O primeiro lance guardado carrega o `nu_ordem` original — entao
    `nu_primeiro_lance > 1` **e** o truncamento, e o ultimo `nu_ordem` e o
    tamanho da partida inteira.

    ⛔ Uma coluna `ic_truncado` seria uma segunda fonte para o mesmo fato, e as
    duas discordariam **em silencio** no dia em que uma fosse gravada errada.
    """
    replay = await ServicoQuadro(
        _repo_com_partida(_lances(14, 24), nu_lance=19)
    ).replay(id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA)

    assert replay["truncado"] is True
    assert replay["nu_primeiro_lance"] == 14
    # ⚠️ **24, e ⛔ nao 11.** Sao onze lances guardados de uma partida de 24, e
    # dizer *"lance 19 de 11"* seria um numero impossivel na tela.
    assert replay["nu_lances"] == 24


@pytest.mark.asyncio
async def test_o_gabarito_nao_tem_lance_de_objetivo():
    """⚠️ A solucao de referencia **e** o caminho ate o objetivo.

    O ultimo lance dela e o que cumpre, por definicao — e uma estrela desenhada
    sempre no fim diria como fato o que e tautologia.
    """
    repo = RepoFalso(gabarito={"js_solucao": {"lances": ["18-22"]},
                               "nu_lances_solucao": 1})

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=None,
        agora=ENCERRA + timedelta(minutes=1),
    )

    assert replay["nu_lance_objetivo"] is None
    assert replay["nu_primeiro_lance"] == 1
    assert replay["truncado"] is False


def test_o_SQL_do_replay_traz_o_lance_que_cumpriu():
    """🔒 Sem esta coluna no `SELECT`, o servico leria `None` de um dado que
    **existe** — e a estrela sumiria de todos os replays, sem erro nenhum."""
    from api.desafios.quadro import SQL_PARTIDA_DO_SUJEITO

    assert "nu_lance_cumpre_desafio" in SQL_PARTIDA_DO_SUJEITO


def test_os_lances_vem_em_ORDEM_porque_o_primeiro_e_o_ultimo_decidem():
    """⚠️ O truncamento e o tamanho sao lidos das **pontas** da lista.

    Sem o `ORDER BY`, o Postgres pode devolver em qualquer ordem — e uma lista
    embaralhada daria um *"lance 3 de 7"* numa partida de 24, ⛔ sem erro nenhum.
    """
    from api.desafios.quadro import SQL_LANCES

    assert "ORDER BY j.nu_ordem ASC" in SQL_LANCES


# ═══════════════════════════════════════════════════════════════════════════
# O REPLAY AUTO-CONTIDO (T074a) — a tela e feita de UMA resposta
# ═══════════════════════════════════════════════════════════════════════════


def _partida_de(jogo="damas"):
    """A linha de partida que o duplo devolve, espelhando o `SELECT`."""
    return {
        "id_resolucao": uuid4(),
        "id_usuario": EU,
        "id_partida": uuid4(),
        "co_jogo": jogo,
        "nu_lance_cumpre_desafio": 3,
    }


def _minha():
    return {
        "id_resolucao": uuid4(),
        "nu_xp": 26,
        "nu_tempo_ms": 40000,
        "dh_resolucao": AGORA,
    }


@pytest.mark.asyncio
async def test_o_replay_diz_de_onde_a_partida_COMECOU():
    """⚠️ Sem a posicao inicial, os lances sao uma lista de textos.

    ⛔ `"18-22"` ⛔ nao desenha nada sozinho: e preciso saber **de qual posicao**
    aquela peca partiu. E quem abre o Raio-X por uma linha do quadro ⛔ nunca teve
    o desafio em maos — o Raio-X e feito de **uma** resposta.
    """
    repo = RepoFalso(
        minha=_minha(),
        partida=_partida_de(),
        jogo="damas",
        modalidade="brasileira",
        formato_posicao="fen",
        posicao_inicial={"fen": "W:W22,31:B12,18"},
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["jogo"] == "damas"
    assert replay["modalidade"] == "brasileira"
    assert replay["formato_posicao"] == "fen"
    assert replay["tabuleiro"] == "W:W22,31:B12,18"
    # ⚠️ **Os dois campos sao excludentes**, e `formato_posicao` diz qual veio:
    # a FEN cabe numa string; a posicao do Pontinhos, ⛔ nao.
    assert replay["posicao"] is None


@pytest.mark.asyncio
async def test_a_posicao_do_Pontinhos_e_a_SEQUENCIA_e_nao_uma_FEN():
    """⚠️ La a posicao **e** o historico: quem fecha caixa joga de novo, e de
    quem e a vez no lance N depende de ter passado pelos N-1 anteriores.

    ⛔ Uma "FEN do Pontinhos" seria um formato inventado para caber neste campo.
    """
    repo = RepoFalso(
        minha=_minha(),
        partida=_partida_de(jogo="pontinhos"),
        jogo="pontinhos",
        formato_posicao="sequencia_lances",
        posicao_inicial={"lances": [{"lance": "H_0_1"}]},
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["posicao"] == {"lances": [{"lance": "H_0_1"}]}
    assert replay["tabuleiro"] is None
    # ⛔ **Sem modalidade, e ⛔ isso nao e falta**: o Pontinhos ⛔ nao tem
    # regulamento, e uma pilula vazia na tela seria um rotulo sobre nada.
    assert replay["modalidade"] is None


@pytest.mark.asyncio
async def test_o_GABARITO_tambem_diz_qual_jogo_e():
    """⛔ **Ele viajava sem jogo nenhum ate 18/09/2026** — uma lista de lances
    que ⛔ ninguem sabia desenhar: nem qual tabuleiro montar, nem por qual
    regulamento ler um lance.

    ⚠️ A ausencia ⛔ nao aparecia porque ⛔ nao havia player: a lista crua ⛔ nunca
    chegou a ser um tabuleiro. O dia em que o player nasce e o dia em que ela
    vira uma tela vazia.
    """
    repo = RepoFalso(
        gabarito={"js_solucao": {"lances": ["18-22"]}, "nu_lances_solucao": 1},
        jogo="damas",
        modalidade="brasileira",
        formato_posicao="fen",
        posicao_inicial={"fen": "W:W22,31:B12,18"},
    )

    aberto = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=None,
        agora=ENCERRA + timedelta(minutes=1),
    )

    assert aberto["jogo"] == "damas"
    assert aberto["modalidade"] == "brasileira"
    # ⚠️ **A MESMA posicao de quem jogou** — e e isso que permite comparar os
    # dois sujeitos no seletor: os dois comecaram do mesmo lugar.
    assert aberto["tabuleiro"] == "W:W22,31:B12,18"


@pytest.mark.asyncio
async def test_o_replay_diz_QUEM_foi_o_adversario():
    """⚠️ O personagem viaja no replay dos DOIS ramos (T085m, 24/09/2026).

    O replay do Pontinhos escreve nas caixas fechadas as iniciais de quem as
    fechou. Quem abre o Raio-X por uma linha do quadro ⛔ nunca teve o desafio
    em maos - sem este campo, as caixas do personagem sairiam mudas.
    """
    repo = RepoFalso(
        minha=_minha(),
        partida=_partida_de(jogo="pontinhos"),
        gabarito={"js_solucao": {"lances": ["H_0_1"]}, "nu_lances_solucao": 1},
        adversario="magno",
        posicao_inicial={"lances": [{"lance": "H_0_0"}]},
    )
    servico = ServicoQuadro(repo)

    de_quem_jogou = await servico.replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )
    do_gabarito = await servico.replay(
        id_desafio=ID_DESAFIO,
        sujeito="desafio",
        id_usuario=None,
        agora=ENCERRA + timedelta(minutes=1),
    )

    # ⚠️ "magno", e ⛔ o "pita" padrao do repositorio falso: um valor fixo no
    # servico passaria num caso que usasse o padrao.
    assert de_quem_jogou["personagem"] == "magno"
    assert do_gabarito["personagem"] == "magno"


@pytest.mark.asyncio
async def test_o_jogo_sai_do_DESAFIO_e_nao_da_partida():
    """⛔ Duas fontes para um fato so discordam em silencio.

    `partida.vw001_partida` tambem tem `co_jogo`, e ele e a mesma coisa. No dia
    em que discordassem, a tela desenharia o tabuleiro de um jogo com os lances
    de outro — e o gabarito ⛔ nao tem partida nenhuma para consultar.
    """
    repo = RepoFalso(
        minha=_minha(),
        # A partida diz uma coisa; o desafio, outra. ⚠️ Isto ⛔ nao acontece na
        # base — o caso existe para dizer **quem manda** quando acontecer.
        partida=_partida_de(jogo="velha"),
        jogo="damas",
        formato_posicao="fen",
        posicao_inicial={"fen": "W:W22:B12"},
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["jogo"] == "damas"


def test_os_dois_leitores_da_posicao_inicial_usam_a_MESMA_funcao():
    """🔒 O desafio publicado e o replay leem a posicao inicial.

    ⚠️ Escrever o mesmo `if` nos dois faria a segunda copia envelhecer calada no
    dia em que um terceiro formato de posicao entrasse — e a tela desenharia um
    tabuleiro vazio, ⛔ sem erro nenhum.
    """
    from api.desafios.publicacao import posicao_publicada

    assert posicao_publicada("fen", {"fen": "W:W22:B12"}) == ("W:W22:B12", None)
    assert posicao_publicada("sequencia_lances", {"lances": []}) == (
        None,
        {"lances": []},
    )
    # ⛔ Posicao ausente ⛔ nao estoura: vira o dicionario vazio, como na
    # publicacao.
    assert posicao_publicada("sequencia_lances", None) == (None, {})


def test_o_SQL_dos_lances_traz_a_posicao_ANTES_de_cada_um():
    """🔒 E ela que torna o replay **truncado** possivel (RF-DES-039).

    Com o comeco da partida cortado, ⛔ nao ha posicao inicial de onde reproduzir
    o primeiro lance guardado — e cada lance trazendo a sua resolve isso sem que
    ninguem precise reproduzir nada.
    """
    from api.desafios.quadro import SQL_LANCES

    assert "dm.co_fen_antes" in SQL_LANCES


def test_o_SQL_do_dia_traz_o_que_o_replay_passou_a_servir():
    """🔒 Sem estas quatro colunas, o servico leria dados que **existem** como
    `None` — e a tela abriria sem tabuleiro nenhum, ⛔ sem erro nenhum."""
    from api.desafios.quadro import SQL_DIA_DO_DESAFIO

    for coluna in (
        "d.co_jogo",
        "d.co_modalidade",
        "d.co_formato_posicao",
        "d.js_posicao_inicial",
    ):
        assert coluna in SQL_DIA_DO_DESAFIO, coluna


# ═══════════════════════════════════════════════════════════════════════════
# QUEM REAGIU (T085zc, peca M2 do Claude Design, 25/09/2026)
# ═══════════════════════════════════════════════════════════════════════════


def _reagiu(*, uid, tipo="palmas", nome="Bia", publico=True):
    """Uma linha como o `SQL_QUEM_REAGIU` a devolve."""
    return {
        "id_usuario": uid,
        "co_tipo_reacao": tipo,
        "co_usuario": "k7m3p9rt",
        "no_exibicao": nome,
        "ic_publico": publico,
    }


def _repo_com_reacoes(*, gente, reagiram, eu_publico=True):
    """Eu resolvi (e, por padrao, apareco no quadro), e recebi [reagiram]."""
    id_res = uuid4()
    minha = _jogador(nome="Eu", xp=20, tempo=60_000, uid=EU, id_res=id_res)
    return RepoFalso(
        gente=gente + ([minha] if eu_publico else []),
        minha={"id_resolucao": id_res, "nu_xp": 20, "nu_tempo_ms": 60_000,
               "dh_resolucao": AGORA},
        partida={
            "id_resolucao": id_res,
            "id_usuario": EU,
            "id_partida": uuid4(),
            "co_jogo": "pontinhos",
            "nu_lance_cumpre_desafio": 5,
        },
        quem_reagiu={id_res: reagiram},
    )


async def _meu_replay(repo):
    return await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )


@pytest.mark.asyncio
async def test_quem_reagiu_traz_nome_tipo_e_a_POSICAO_do_quadro():
    """⚠️ A posicao e a MESMA que a linha mostra no quadro - mascotes contam."""
    ana = _jogador(nome="Ana", xp=28, tempo=41_880, uid="uid-ana")
    repo = _repo_com_reacoes(
        gente=[ana], reagiram=[_reagiu(uid="uid-ana", tipo="fogo", nome="Ana")]
    )

    replay = await _meu_replay(repo)
    quadro = await ServicoQuadro(repo).montar(
        id_desafio=ID_DESAFIO, id_usuario=EU, agora=AGORA
    )
    # O numero que o quadro escreve na linha da Ana: o indice + 1.
    posicao_no_quadro = 1 + next(
        i for i, l in enumerate(quadro["linhas"]) if l.get("id") == "uid-ana"
    )

    assert replay["quem_reagiu"] == [
        {"nome": "Ana", "tipo": "fogo", "id": "uid-ana",
         "posicao": posicao_no_quadro}
    ]
    # 🔒 Os mascotes ocupam posicoes: sem eles a Ana seria a 1a.
    assert posicao_no_quadro > 1


@pytest.mark.asyncio
async def test_quem_se_escondeu_reage_e_CONTINUA_escondido():
    """⛔ Sem nome e sem id - e a linha vem, para a lista bater com a pilha."""
    repo = _repo_com_reacoes(
        gente=[], reagiram=[_reagiu(uid="uid-x", nome="Xavier", publico=False)]
    )

    replay = await _meu_replay(repo)

    assert replay["quem_reagiu"] == [{"oculto": True, "tipo": "palmas"}]


@pytest.mark.asyncio
async def test_quem_reagiu_sem_ter_linha_no_quadro_vem_sem_id_e_sem_posicao():
    """⚠️ Quem nao resolveu (ou nao aparece) ⛔ tem linha para o toque abrir."""
    repo = _repo_com_reacoes(
        gente=[], reagiram=[_reagiu(uid="uid-bia", tipo="uau", nome="Bia")]
    )

    replay = await _meu_replay(repo)

    assert replay["quem_reagiu"] == [{"nome": "Bia", "tipo": "uau"}]


@pytest.mark.asyncio
async def test_nome_nulo_cai_no_codigo_curto_como_no_quadro():
    repo = _repo_com_reacoes(
        gente=[], reagiram=[_reagiu(uid="uid-bia", nome=None)]
    )

    replay = await _meu_replay(repo)

    assert replay["quem_reagiu"][0]["nome"] == "k7m3p9rt"


@pytest.mark.asyncio
async def test_a_ordem_de_quem_reagiu_e_a_do_banco():
    """⚠️ A mais recente primeiro e o `ORDER BY` do SQL; o servico ⛔ reordena."""
    repo = _repo_com_reacoes(
        gente=[],
        reagiram=[
            _reagiu(uid="uid-c", nome="Caio"),
            _reagiu(uid="uid-a", nome="Ana"),
            _reagiu(uid="uid-b", nome="Bia"),
        ],
    )

    replay = await _meu_replay(repo)

    assert [i["nome"] for i in replay["quem_reagiu"]] == ["Caio", "Ana", "Bia"]


@pytest.mark.asyncio
async def test_sem_reacao_nenhuma_a_lista_vem_VAZIA():
    """A tela le a lista vazia e o bloco inteiro some - zero ⛔ aparece."""
    repo = _repo_com_reacoes(gente=[], reagiram=[])

    replay = await _meu_replay(repo)

    assert replay["quem_reagiu"] == []


@pytest.mark.asyncio
async def test_quem_se_escondeu_do_quadro_NAO_ve_quem_reagiu():
    """⚠️ RF-DES-077: a barra VOCE ja vem sem pilha, e a lista seria a mesma
    informacao por outra porta."""
    repo = _repo_com_reacoes(
        gente=[], reagiram=[_reagiu(uid="uid-ana")], eu_publico=False
    )

    replay = await _meu_replay(repo)

    assert replay["quem_reagiu"] == []


@pytest.mark.asyncio
async def test_quem_reagiu_NAO_existe_no_replay_de_outra_pessoa():
    """⛔ So a dona da resolucao ve a lista - o campo nem viaja."""
    repo = _repo_com_reacoes(gente=[], reagiram=[_reagiu(uid="uid-ana")])

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="uid-ana", id_usuario=EU, agora=AGORA
    )

    assert "quem_reagiu" not in replay


@pytest.mark.asyncio
async def test_quem_reagiu_NAO_existe_no_gabarito():
    repo = _repo_com_reacoes(gente=[], reagiram=[_reagiu(uid="uid-ana")])
    repo._gabarito = {"js_solucao": [], "nu_lances_solucao": 3}

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="desafio", id_usuario=EU, agora=AGORA
    )

    assert "quem_reagiu" not in replay


def test_o_SQL_de_quem_reagiu_CALCULA_o_publico_e_nao_filtra():
    """🔒 Filtrar tiraria da lista quem se escondeu, e ela discordaria da
    contagem da pilha, que conta a reacao dele."""
    from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO, SQL_QUEM_REAGIU

    assert f"{CLAUSULA_APARECE_EM_PUBLICO} AS ic_publico" in SQL_QUEM_REAGIU
    corpo_do_where = SQL_QUEM_REAGIU.split("WHERE", 1)[1]
    assert CLAUSULA_APARECE_EM_PUBLICO not in corpo_do_where
    assert "ORDER BY re.dh_reacao DESC" in SQL_QUEM_REAGIU
