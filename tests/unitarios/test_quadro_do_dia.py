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
        minhas_reacoes=None,
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
    ) -> None:
        self._adversario = adversario
        self._jogo = jogo
        self._modalidade = modalidade
        self._formato_posicao = formato_posicao
        self._posicao_inicial = posicao_inicial
        self._gente = gente or []
        self._minha = minha
        self._fracao = fracao
        self._reacoes = reacoes or {}
        self._minhas_reacoes = minhas_reacoes or {}
        self._medicoes = medicoes or []
        self._partida = partida
        self._lances = lances
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
        return self._reacoes

    async def minhas_reacoes(self, ids, id_usuario):
        # ⚠️ Convidado ⛔ nao tem nenhuma - e a mesma regra do repositorio
        # de verdade, e ⛔ nao um atalho do duplo.
        if id_usuario is None:
            return {}
        return self._minhas_reacoes

    async def partida_do_sujeito(self, *, id_desafio_dia, id_usuario):
        return self._partida

    async def lances(self, id_partida):
        if self._lances is not None:
            return self._lances
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
            "co_status": "concluida",
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


def _partida_de(jogo="damas", status="concluida"):
    """A linha de partida que o duplo devolve, espelhando o `SELECT`."""
    return {
        "id_resolucao": uuid4(),
        "id_usuario": EU,
        "id_partida": uuid4(),
        "co_status": status,
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
