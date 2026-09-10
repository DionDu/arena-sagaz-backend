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
    MINIMO_PARA_FRACAO,
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
        medicoes=None,
        partida=None,
        gabarito=None,
        tem_contexto=True,
        adversario="pita",
    ) -> None:
        self._adversario = adversario
        self._gente = gente or []
        self._minha = minha
        self._fracao = fracao
        self._reacoes = reacoes or {}
        self._medicoes = medicoes or []
        self._partida = partida
        self._gabarito = gabarito
        self._tem_contexto = tem_contexto

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
        return self._reacoes

    async def partida_do_sujeito(self, *, id_desafio_dia, id_usuario):
        return self._partida

    async def lances(self, id_partida):
        return [{"nu_ordem": 1, "nu_jogador": 1, "co_lance": "H_0_1"}]

    async def extrato(self, id_resolucao):
        return [{"co_tipo_xp": "base", "vr_xp": 18}]

    async def gabarito(self, id_desafio):
        return self._gabarito


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


def test_a_fracao_abaixo_de_20_nao_e_servida():
    """⛔ RF-DES-063: *"2 de 3 resolveram"* grita que o aplicativo tem 3 usuarios.

    O numero que isto esconde conta sobre o **tamanho da base**, e nao sobre a
    partida.
    """
    assert fracao_servivel(qt_pessoas=19, qt_resolveram=12) is None
    assert fracao_servivel(
        qt_pessoas=MINIMO_PARA_FRACAO, qt_resolveram=12
    ) == {"tentaram": 20, "resolveram": 12}


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
            "co_status": "concluida",
            "co_jogo": "pontinhos",
        },
    )

    replay = await ServicoQuadro(repo).replay(
        id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
    )

    assert replay["lances"]
    assert replay["extrato"]


@pytest.mark.asyncio
async def test_partida_em_andamento_nao_tem_replay():
    """⚠️ RF-DES-187/SC-024: sem desfecho nao ha o que reproduzir.

    A partida existe — a pessoa parou no objetivo e nao voltou —, e o job de
    expiracao (T046) a fechara em ate 7 dias. Dizer isso e mais honesto que
    servir meia partida.
    """
    repo = RepoFalso(
        minha={"id_resolucao": uuid4(), "nu_xp": 26, "nu_tempo_ms": 40000,
               "dh_resolucao": AGORA},
        partida={
            "id_resolucao": uuid4(),
            "id_usuario": EU,
            "id_partida": uuid4(),
            "co_status": "em_andamento",
            "co_jogo": "damas",
        },
    )

    with pytest.raises(ErroNaoEncontrado) as erro:
        await ServicoQuadro(repo).replay(
            id_desafio=ID_DESAFIO, sujeito="eu", id_usuario=EU, agora=AGORA
        )
    assert erro.value.codigo == "partida_em_andamento"


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


@pytest.mark.asyncio
async def test_desafio_inexistente_e_404():
    """Sem dia, nao ha quadro."""
    with pytest.raises(ErroNaoEncontrado):
        await ServicoQuadro(RepoFalso(tem_contexto=False)).montar(
            id_desafio=ID_DESAFIO, id_usuario=None, agora=AGORA
        )
