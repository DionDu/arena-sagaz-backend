"""O PAINEL DE CURADORIA — T039 (RF-DES-012a a 012e).

O que estes casos protegem, em uma frase cada:

  · **quem entra**: sem `PAINEL_CURADORIA_TOKEN` o painel nao existe, e com ele
    so entra quem tem o segredo — pelos tres caminhos (cabecalho, query, cookie);
  · **as tres acoes**: aprovar, descartar **com motivo** e trocar a data;
  · **as duas regras que nao podem morar no HTML**: descartar sem motivo e
    recusado, e candidato nao entra no calendario;
  · **o desenho**: a posicao vira SVG nos dois formatos, e nao um `<pre>` de
    JSON.

⚠️ **O que estes casos NAO provam** esta escrito em `fakes_desafio.py`: o SQL nao
e executado. Quem confere isso e o banco de verdade, no portao T050.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api.configuracao import configuracoes
from api.desafios.painel import desenho, pagina
from api.desafios.painel.repositorio import (
    DesafioNoPainel,
    MedicaoNoPainel,
    encerramento_do_dia,
)
from api.desafios.painel.rotas import hoje_utc, obter_servico
from api.desafios.painel.servico import ServicoCuradoria
from api.desafios.painel.vigilancia import ContagemDeAuditoria, EstadoDaFila
from api.main import app
from api.nucleo.banco import obter_sessao
from api.nucleo.excecoes import ErroNegocio
from tests.unitarios.fakes_desafio import FakeSessaoSQL

SEGREDO = "segredo-de-teste-do-painel"

#: Uma posicao de Pontinhos com dois tracos — pequena de proposito: o teste e
#: sobre o desenho existir e ser SVG, e nao sobre a partida.
POSICAO_PONTINHOS = {
    "versao": 1,
    "lances": [
        {"n": 1, "jogador": 1, "lance": "H_0_1"},
        {"n": 2, "jogador": -1, "lance": "V_1_0"},
    ],
    "vez_de": 1,
    "placar": {"j1": 0, "j2": 0},
}

POSICAO_DAMAS = {
    "versao": 1,
    "fen": "W:W18,24,K27:B12,16,K22",
    "vez_de": 1,
}


def _desafio(
    *,
    co_curadoria: str = "candidato",
    dt_dia: date | None = None,
    id_desafio: UUID | None = None,
    co_jogo: str = "damas",
    posicao: dict | None = None,
    co_formato: str = "fen",
    medicoes: tuple[MedicaoNoPainel, ...] = (),
) -> DesafioNoPainel:
    """Uma linha da fila, com o minimo preenchido para a tela existir."""
    return DesafioNoPainel(
        id_desafio=id_desafio or uuid4(),
        co_jogo=co_jogo,
        co_modalidade="brasileira" if co_jogo == "damas" else None,
        co_variante="padrao",
        co_formato_posicao=co_formato,
        js_posicao_inicial=posicao if posicao is not None else POSICAO_DAMAS,
        co_tipo_desafio="damas_sacrificio",
        no_tipo_desafio="Sacrificio",
        co_chave_objetivo="desafioObjetivoSacrificioDamas",
        js_objetivo={"dar": 1, "comer": 3},
        js_solucao={"lances": ["18-22", "24-20"]},
        nu_lances_solucao=2,
        co_personagem="pita",
        nu_semente=2087461933,
        co_curadoria=co_curadoria,
        de_motivo_descarte=None,
        ic_reprise=False,
        id_desafio_origem=None,
        dh_geracao=datetime(2026, 9, 10, 3, 0, tzinfo=timezone.utc),
        dt_dia=dt_dia,
        medicoes=medicoes,
    )


class RepoFalso:
    """Um `RepositorioPainel` de mentira, com a fila em memoria.

    ⚠️ Guarda o que foi chamado, e nao so o resultado: varias regras desta
    tarefa sao sobre **o que nao acontece** (descartar nao agenda, candidato nao
    entra no calendario), e isso so se afirma sobre o historico.
    """

    def __init__(self, fila: list[DesafioNoPainel] | None = None) -> None:
        self._fila = fila or []
        self.aprovados: list[UUID] = []
        self.descartados: list[tuple[UUID, str]] = []
        self.agendados: list[tuple[UUID, date]] = []
        self.desagendados: list[UUID] = []
        self.commits = 0
        self.dias: list[dict] = []
        self.reserva = 0

    async def fila(self, *, estados=("candidato", "aprovado"), limite=60):
        return [d for d in self._fila if d.co_curadoria in estados][:limite]

    async def aprovar(self, id_desafio: UUID) -> bool:
        self.aprovados.append(id_desafio)
        alvo = next((d for d in self._fila if d.id_desafio == id_desafio), None)
        return alvo is not None and alvo.co_curadoria != "aprovado"

    async def descartar(self, id_desafio: UUID, *, de_motivo: str) -> bool:
        self.descartados.append((id_desafio, de_motivo))
        return any(d.id_desafio == id_desafio for d in self._fila)

    async def agendar(self, id_desafio: UUID, *, dt_dia: date) -> bool:
        self.agendados.append((id_desafio, dt_dia))
        return True

    async def desagendar(self, id_desafio: UUID) -> bool:
        self.desagendados.append(id_desafio)
        return any(
            d.id_desafio == id_desafio and d.dt_dia is not None for d in self._fila
        )

    async def dias_ocupados(self, *, dt_de: date):
        return [linha for linha in self.dias if linha["dt_dia"] >= dt_de]

    async def quantos_aprovados_sem_dia(self) -> int:
        return self.reserva

    async def confirmar(self) -> None:
        self.commits += 1


def _sessao_de_pagina() -> FakeSessaoSQL:
    """Uma sessao falsa que responde as consultas que a PAGINA faz.

    ⚠️ O `COUNT(*)` da reserva precisa vir preparado: `scalar_one()` falha
    com zero linhas — no duble e no SQLAlchemy de verdade —, e e assim que
    tem de ser. Um duble que devolvesse `None` calado deixaria passar um codigo
    que o banco recusaria.
    """
    return FakeSessaoSQL(
        respostas={
            # ⚠️ Os trechos sao ESCOLHIDOS por serem unicos: as duas
            # consultas tem `COUNT(*) AS qt`, e casar por esse pedaco faria a
            # contagem de auditoria receber a resposta da reserva.
            "GROUP BY co_auditoria": [],
            "dia.id_desafio IS NULL": [{"qt": 0}],
        }
    )


@pytest.fixture
def cliente(monkeypatch):
    """Um `TestClient` com o painel habilitado e sem banco."""
    monkeypatch.setattr(configuracoes, "PAINEL_CURADORIA_TOKEN", SEGREDO)
    app.dependency_overrides[obter_sessao] = _sessao_de_pagina
    c = TestClient(app, follow_redirects=False)
    yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Quem entra (RF-DES-012e)
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_segredo_configurado_o_painel_nao_existe(monkeypatch):
    """⛔ Variavel vazia **desabilita** a pagina — o default seguro.

    Um painel que abre sozinho quando alguem esquece a configuracao falha em
    silencio; um que nao abre falha alto, e o log diz o que fazer.
    """
    monkeypatch.setattr(configuracoes, "PAINEL_CURADORIA_TOKEN", "")
    app.dependency_overrides[obter_sessao] = _sessao_de_pagina
    try:
        resposta = TestClient(app).get("/painel/desafios")
        assert resposta.status_code == 401
        assert resposta.json()["codigo"] == "painel_desabilitado"
    finally:
        app.dependency_overrides.clear()


def test_token_errado_e_401(cliente):
    """Segredo configurado + credencial errada = 401, e nao a pagina."""
    resposta = cliente.get(
        "/painel/desafios", headers={"X-Admin-Token": "nao-e-esse"}
    )
    assert resposta.status_code == 401
    assert resposta.json()["codigo"] == "painel_token_invalido"


def test_sem_credencial_nenhuma_e_401(cliente):
    """Abrir a URL sem nada nao mostra nem o titulo da pagina."""
    assert cliente.get("/painel/desafios").status_code == 401


def test_cabecalho_admin_abre_a_pagina(cliente):
    """O caminho de `curl` e dos testes: cabecalho, sem cookie e sem redirect."""
    resposta = cliente.get(
        "/painel/desafios", headers={"X-Admin-Token": SEGREDO}
    )
    assert resposta.status_code == 200
    assert "Curadoria do Desafio do Dia" in resposta.text
    # ⚠️ O gabarito aparece nesta pagina; ela nao pode ser guardada por cache.
    assert resposta.headers["cache-control"] == "no-store"


def test_token_na_query_vira_cookie_e_limpa_a_url(cliente):
    """A primeira visita traz `?token=`; a segunda em diante, o cookie.

    ⚠️ **O redirecionamento e a parte que importa**: sem ele o segredo ficaria no
    historico do navegador e no `Referer` de toda navegacao seguinte.
    """
    resposta = cliente.get(f"/painel/desafios?token={SEGREDO}")
    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/painel/desafios"

    cookie = resposta.headers["set-cookie"]
    assert "painel_curadoria=" in cookie
    assert "HttpOnly" in cookie
    assert "strict" in cookie.lower()

    # E o cookie sozinho basta na visita seguinte.
    cliente.cookies.set("painel_curadoria", SEGREDO)
    assert cliente.get("/painel/desafios").status_code == 200


def test_o_painel_nao_aparece_no_openapi(cliente):
    """⛔ Pagina administrativa nao se anuncia em `/docs`."""
    esquema = cliente.get("/openapi.json").json()
    assert not [c for c in esquema["paths"] if c.startswith("/painel")]


# ═══════════════════════════════════════════════════════════════════════════
# 2. As tres acoes (RF-DES-012c)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_aprovar_muda_o_estado_e_fecha_a_transacao():
    """Aprovar e o unico caminho para o ar (RF-DES-012a)."""
    alvo = _desafio()
    repo = RepoFalso([alvo])
    resultado = await ServicoCuradoria(repo).aprovar(alvo.id_desafio)

    assert resultado.mudou is True
    assert repo.aprovados == [alvo.id_desafio]
    assert repo.commits == 1


@pytest.mark.asyncio
async def test_aprovar_duas_vezes_nao_e_erro():
    """Clicar duas vezes e rotineiro; tratar como falha ensina a ignorar aviso."""
    alvo = _desafio(co_curadoria="aprovado")
    resultado = await ServicoCuradoria(RepoFalso([alvo])).aprovar(alvo.id_desafio)

    assert resultado.mudou is False
    assert "ja estava aprovado" in resultado.mensagem


@pytest.mark.asyncio
async def test_descartar_sem_motivo_e_recusado():
    """⛔ RF-DES-012c: o motivo e o que ensina o gerador a nao repetir a familia.

    ⚠️ A checagem daqui **nao substitui** o `ck004_motivo` da migracao: ela o
    antecipa, para que a pessoa leia "escreva o motivo" em vez de um 500.
    """
    alvo = _desafio()
    repo = RepoFalso([alvo])
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).descartar(alvo.id_desafio, motivo="   ")

    assert erro.value.codigo == "motivo_ausente"
    assert repo.descartados == []  # ⛔ nao chegou ao banco
    assert repo.commits == 0


@pytest.mark.asyncio
async def test_descartar_guarda_o_motivo_e_libera_o_dia():
    """Descartar **nao apaga**, e tira do calendario.

    ⚠️ Um descartado que continuasse agendado ocuparia o dia (`un001_dia`) sem
    nada ser servido — o dia em branco que nada denuncia.
    """
    alvo = _desafio(co_curadoria="aprovado", dt_dia=date(2026, 9, 14))
    repo = RepoFalso([alvo])
    resultado = await ServicoCuradoria(repo).descartar(
        alvo.id_desafio, motivo="posicao banal: a Cacau resolveu 20/20"
    )

    assert resultado.mudou is True
    assert repo.descartados == [
        (alvo.id_desafio, "posicao banal: a Cacau resolveu 20/20")
    ]
    assert repo.desagendados == [alvo.id_desafio]
    assert "voltou a ficar livre" in resultado.mensagem


@pytest.mark.asyncio
async def test_candidato_nao_entra_no_calendario():
    """⛔ RF-DES-012a, e a razao de a regra nao morar no HTML.

    Um candidato agendado criaria um dia que o endpoint nao serve — e o
    aplicativo abriria com o dia em branco. Um `<form>` ausente na tela nao
    impede um `curl`; esta regra, sim.
    """
    alvo = _desafio(co_curadoria="candidato")
    repo = RepoFalso([alvo])
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).agendar(
            alvo.id_desafio, dt_dia=date(2026, 9, 12), dt_hoje=date(2026, 9, 10)
        )

    assert erro.value.codigo == "desafio_nao_aprovado"
    assert repo.agendados == []


@pytest.mark.asyncio
async def test_agendar_aprovado_grava_a_data():
    """O caminho feliz de "trocar a data" (RF-DES-012c)."""
    alvo = _desafio(co_curadoria="aprovado")
    repo = RepoFalso([alvo])
    resultado = await ServicoCuradoria(repo).agendar(
        alvo.id_desafio, dt_dia=date(2026, 9, 12), dt_hoje=date(2026, 9, 10)
    )

    assert resultado.mudou is True
    assert repo.agendados == [(alvo.id_desafio, date(2026, 9, 12))]


@pytest.mark.asyncio
async def test_agendar_para_hoje_e_permitido():
    """⚠️ Hoje conta: e o que a fila curta exige quando o dono chega tarde."""
    alvo = _desafio(co_curadoria="aprovado")
    repo = RepoFalso([alvo])
    await ServicoCuradoria(repo).agendar(
        alvo.id_desafio, dt_dia=date(2026, 9, 10), dt_hoje=date(2026, 9, 10)
    )
    assert repo.agendados == [(alvo.id_desafio, date(2026, 9, 10))]


@pytest.mark.asyncio
async def test_agendar_no_passado_e_recusado():
    """Um dia encerrado nao seria servido a ninguem."""
    alvo = _desafio(co_curadoria="aprovado")
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(RepoFalso([alvo])).agendar(
            alvo.id_desafio, dt_dia=date(2026, 9, 9), dt_hoje=date(2026, 9, 10)
        )
    assert erro.value.codigo == "dia_no_passado"


@pytest.mark.asyncio
async def test_agendar_longe_demais_e_recusado():
    """⚠️ O mesmo teto de 30 dias do job, e pelo mesmo motivo de curadoria."""
    alvo = _desafio(co_curadoria="aprovado")
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(RepoFalso([alvo])).agendar(
            alvo.id_desafio, dt_dia=date(2026, 10, 20), dt_hoje=date(2026, 9, 10)
        )
    assert erro.value.codigo == "dia_longe_demais"


def test_o_encerramento_e_meia_noite_utc_do_dia_seguinte():
    """⚠️ RF-DES-008: o dia do desafio e um dia **UTC**, e nao o de um fuso.

    E isso que faz o quadro do dia ser o mesmo quadro para o mundo inteiro.
    """
    assert encerramento_do_dia(date(2026, 9, 4)) == datetime(
        2026, 9, 5, 0, 0, tzinfo=timezone.utc
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3. As rotas HTTP das acoes
# ═══════════════════════════════════════════════════════════════════════════


def _servico_falso(repo: RepoFalso):
    """Injeta um servico com repositorio em memoria nas rotas."""
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(repo)


def test_acao_responde_303_e_volta_para_a_pagina(cliente):
    """POST → Redirect → GET: um F5 depois de aprovar nao reenvia o formulario."""
    alvo = _desafio()
    repo = RepoFalso([alvo])
    _servico_falso(repo)

    # ⚠️ O corpo vai como texto urlencoded, e nao pelo `data=` do httpx: o
    # painel le o formulario com a biblioteca padrao, sem `python-multipart` na
    # imagem da API (ver o topo de `rotas.py`).
    resposta = cliente.post(
        "/painel/desafios/aprovar",
        headers={
            "X-Admin-Token": SEGREDO,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=f"id_desafio={alvo.id_desafio}",
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"].startswith("/painel/desafios?recado=")
    assert repo.aprovados == [alvo.id_desafio]


def test_acao_sem_token_nao_toca_no_banco(cliente):
    """⛔ A protecao vale nas acoes, e nao so na pagina que as mostra."""
    alvo = _desafio()
    repo = RepoFalso([alvo])
    _servico_falso(repo)

    resposta = cliente.post(
        "/painel/desafios/aprovar",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        content=f"id_desafio={alvo.id_desafio}",
    )

    assert resposta.status_code == 401
    assert repo.aprovados == []


def test_descartar_sem_motivo_volta_com_recado_vermelho(cliente):
    """⚠️ Erro de negocio no painel e recado na pagina, e nao JSON cru.

    O dono clicou num botao; devolver `{"detalhe": ...}` numa pagina branca
    seria a resposta certa para o aplicativo e a errada para uma pessoa.
    """
    alvo = _desafio()
    repo = RepoFalso([alvo])
    _servico_falso(repo)

    resposta = cliente.post(
        "/painel/desafios/descartar",
        headers={
            "X-Admin-Token": SEGREDO,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=f"id_desafio={alvo.id_desafio}&motivo=",
    )

    assert resposta.status_code == 303
    assert "erro=1" in resposta.headers["location"]
    assert repo.descartados == []


def test_id_torto_no_formulario_e_400_e_nao_500(cliente):
    """Dado de fora malformado nao e defeito do servidor."""
    repo = RepoFalso([])
    _servico_falso(repo)

    resposta = cliente.post(
        "/painel/desafios/aprovar",
        headers={
            "X-Admin-Token": SEGREDO,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content="id_desafio=nao-e-uuid",
    )

    assert resposta.status_code == 303
    assert "erro=1" in resposta.headers["location"]
    assert repo.aprovados == []


# ═══════════════════════════════════════════════════════════════════════════
# 4. O desenho (RF-DES-012b: "a posicao DESENHADA")
# ═══════════════════════════════════════════════════════════════════════════


def test_pontinhos_vira_svg_com_as_cores_dos_jogadores():
    """⚠️ `jogador 1 = AZUL`, `jogador 2 = VERMELHO` — a regra canonica do hub.

    O dono le esta tela e as telas do jogo no mesmo dia; cores invertidas aqui o
    fariam ler o desafio ao contrario do que os jogadores vao ver.
    """
    svg = desenho.pontinhos(POSICAO_PONTINHOS)
    assert svg.startswith("<svg")
    assert desenho.AZUL_J1 in svg
    assert desenho.VERMELHO_J2 in svg


def test_a_caixa_fechada_ganha_o_dono_do_quarto_lado():
    """⚠️ O dono e quem coloca o QUARTO lado — e por isso a ordem importa.

    A mesma colecao de tracos, marcada noutra ordem, daria outro dono para a
    mesma caixa. E a razao de o Pontinhos guardar sequencia, e nao matriz.
    """
    # Os quatro lados da caixa (0,0): H_0_1, H_2_1, V_1_0, V_1_2.
    fecha_j2 = {
        "versao": 1,
        "lances": [
            {"n": 1, "jogador": 1, "lance": "H_0_1"},
            {"n": 2, "jogador": -1, "lance": "H_2_1"},
            {"n": 3, "jogador": 1, "lance": "V_1_0"},
            {"n": 4, "jogador": -1, "lance": "V_1_2"},
        ],
        "vez_de": -1,
        "placar": {"j1": 0, "j2": 1},
    }
    svg = desenho.pontinhos(fecha_j2)
    assert desenho.VERMELHO_J2_CLARO in svg
    assert desenho.AZUL_J1_CLARO not in svg


def test_damas_vira_svg_com_a_coroa_da_dama():
    """A FEN desenhada: pecas nas cores dos jogadores e a coroa em ouro."""
    svg = desenho.damas(POSICAO_DAMAS)
    assert svg.startswith("<svg")
    # `K27` e `K22` sao damas — o anel dourado tem de aparecer.
    assert desenho.OURO in svg


def test_formato_desconhecido_nao_derruba_a_pagina():
    """⚠️ O painel e a janela para ver o que esta torto; 500 a fecharia."""
    svg = desenho.posicao("formato_que_nao_existe", {})
    assert svg.startswith("<svg")
    assert "sem desenho" in svg


def test_a_numeracao_das_casas_bate_com_a_do_motor():
    """A casa 1 fica no topo (lado das pretas) e a 32 embaixo, na coluna 6.

    ⚠️ Esta aritmetica e reescrita aqui porque o desenho **nao pode importar o
    motor** (a imagem da API nao tem o laboratorio). Um tabuleiro com as casas
    trocadas poe as pretas embaixo, e a unica coisa que denunciaria isso e
    alguem olhar — este caso e o substituto do olhar.
    """
    assert desenho._linha_coluna(1) == (0, 1)
    assert desenho._linha_coluna(4) == (0, 7)
    assert desenho._linha_coluna(5) == (1, 0)
    assert desenho._linha_coluna(32) == (7, 6)


def test_a_fen_e_lida_nas_duas_ordens():
    """`:W...:B...` e `:B...:W...` descrevem a mesma posicao.

    ⚠️ O prefixo de cada bloco diz de quem ele e; confiar na **posicao** do bloco
    seria inventar uma regra que o motor nao tem.
    """
    vez_a, ocupadas_a = desenho._ler_fen("W:W18,K27:B12")
    vez_b, ocupadas_b = desenho._ler_fen("W:B12:W18,K27")
    assert vez_a == vez_b == "W"
    assert ocupadas_a == ocupadas_b
    assert ocupadas_a[27] == ("W", True)


# ═══════════════════════════════════════════════════════════════════════════
# 5. A pagina montada
# ═══════════════════════════════════════════════════════════════════════════


def _pagina(fila, *, estado=None, contagem=None, divergencias=()) -> str:
    """Renderiza a pagina com o minimo, para os casos de HTML."""
    return pagina.render(
        fila=fila,
        estado_da_fila=estado
        or EstadoDaFila(dias_cobertos=7, reserva=3, buracos=()),
        contagem=contagem or ContagemDeAuditoria(),
        divergencias=divergencias,
        dt_hoje=date(2026, 9, 10),
    )


def test_a_pagina_mostra_as_cinco_informacoes_de_rf_des_012b():
    """Posicao, jogo/modalidade, objetivo, solucao e a medicao da regua."""
    item = _desafio(
        medicoes=(
            MedicaoNoPainel("cacau", 20, 18, "perfil-2026-09", "damas-1.4.0"),
            MedicaoNoPainel("magno", 20, 4, "perfil-2026-09", "damas-1.4.0"),
        )
    )
    html = _pagina([item])

    assert "<svg" in html  # a posicao desenhada
    assert "damas" in html and "brasileira" in html  # jogo e modalidade
    assert "desafioObjetivoSacrificioDamas" in html  # o objetivo (a CHAVE)
    assert "gabarito" in html  # a solucao de referencia
    assert "Cacau" in html and "Magno" in html  # a regua por nivel
    assert "90%" in html and "20%" in html  # as taxas


def test_candidato_sem_medicao_avisa_que_aprovar_e_as_cegas():
    """Aprovar sem a regua e decidir sem o unico numero que calibra."""
    html = _pagina([_desafio(medicoes=())])
    assert "Sem medicao da regua" in html


def test_o_gabarito_nao_vaza_por_engano_no_html_escapado():
    """⚠️ Todo dado do banco passa por `escape` — inclusive o que "claramente"
    nao precisaria.

    Um motivo de descarte com `<script>` viraria script de verdade na proxima
    visita do dono; o painel e o unico lugar do sistema que exibe texto livre
    gravado por quem quer que seja.
    """
    # `replace` monta uma copia trocando um campo — o dataclass e `frozen`, e
    # `slots=True` o deixa sem `__dict__`.
    item = replace(
        _desafio(co_curadoria="descartado"),
        de_motivo_descarte="<script>alert('x')</script>",
    )
    html = _pagina([item])
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_fila_vazia_diz_o_que_fazer():
    """Tela vazia sem explicacao e indistinguivel de tela quebrada."""
    html = _pagina([])
    assert "Nenhum candidato na fila" in html


def test_o_formulario_de_agendar_so_aparece_no_aprovado():
    """⚠️ Espelho da regra, e nao a regra: quem recusa e `servico.py`."""
    html_candidato = _pagina([_desafio(co_curadoria="candidato")])
    html_aprovado = _pagina([_desafio(co_curadoria="aprovado")])

    assert "/painel/desafios/agendar" not in html_candidato
    assert "/painel/desafios/aprovar" in html_candidato
    assert "/painel/desafios/agendar" in html_aprovado


def test_hoje_utc_devolve_o_dia_em_utc():
    """⚠️ O dia do desafio e UTC — nao o dia do fuso do servidor."""
    assert hoje_utc() == datetime.now(timezone.utc).date()


# ═══════════════════════════════════════════════════════════════════════════
# A SOLUCAO DESENHADA — o que torna a curadoria possivel sem jogar
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Pedido do dono, 11/09/2026, depois de abrir o painel pela primeira vez:
# *"o painel deveria ao menos exibir a solucao de gabarito, lance por lance.
# Olhando so o JSON dos lances fica muito dificil para mim visualizar isso."*

#: Uma solucao de damas com as posicoes gravadas — o formato que o job passou a
#: produzir.
SOLUCAO_DE_DAMAS = {
    "lances": [
        {"n": 1, "jogador": -1, "lance": "20-24"},
        {"n": 2, "jogador": 1, "lance": "27x20"},
    ],
    "posicoes": [
        {"n": 1, "fen": "W:W5,27,30:B14,18,24"},
        {"n": 2, "fen": "B:W5,20,30:B14,18"},
    ],
    "lance_chave": 2,
}

POSICAO_DE_DAMAS = {"fen": "B:W5,27,30:B14,18,20", "versao": 1, "vez_de": -1}


def test_a_fita_de_damas_tem_um_quadro_POR_LANCE_mais_o_inicio() -> None:
    """🔒 A contagem, que e o cadeado mais barato contra um quadro perdido."""
    from api.desafios.painel import desenho

    quadros = desenho.fita_da_solucao("fen", POSICAO_DE_DAMAS, SOLUCAO_DE_DAMAS)
    assert [q["n"] for q in quadros] == [0, 1, 2]
    assert quadros[0]["titulo"] == "posicao publicada"


def test_o_quadro_do_lance_CHAVE_vem_marcado() -> None:
    """🔒 ⚠️ **E o unico quadro que a curadoria precisa julgar.**

    O lance chave e onde o objetivo cai; os depois dele sao o resto da partida.
    Sem a marca, uma solucao de 19 lances (elas existem, no Pontinhos) obriga a
    contar quadros com o dedo.
    """
    from api.desafios.painel import desenho

    quadros = desenho.fita_da_solucao("fen", POSICAO_DE_DAMAS, SOLUCAO_DE_DAMAS)
    assert [q["chave"] for q in quadros] == [False, False, True]


def test_solucao_SEM_posicoes_nao_desenha_MEIA_sequencia() -> None:
    """🔒 ⛔ Desafio gerado antes de 11/09/2026 devolve lista VAZIA.

    ⚠️ A alternativa — desenhar os quadros que existem — e pior que nao
    desenhar: o salto entre dois lances apareceria como se fosse um lance, e a
    curadoria aprovaria uma solucao que nao existe.
    """
    from api.desafios.painel import desenho

    sem_posicoes = {k: v for k, v in SOLUCAO_DE_DAMAS.items() if k != "posicoes"}
    assert desenho.fita_da_solucao("fen", POSICAO_DE_DAMAS, sem_posicoes) == []


def test_o_PONTINHOS_monta_a_fita_SEM_posicoes_gravadas() -> None:
    """🔒 ⚠️ E de proposito: la a posicao **e** a lista de lances.

    O quadro k e a concatenacao dos lances iniciais com os k primeiros do
    gabarito — ⛔ **nenhuma regra e aplicada aqui**, porque a posse das caixas ja
    e calculada pelo mesmo `_donos_das_caixas` que desenha a posicao inicial
    desde o primeiro dia. Exigir `posicoes` no Pontinhos faria o painel recusar
    desenhar o que ele sabe desenhar.
    """
    from api.desafios.painel import desenho

    posicao = {
        "lances": [{"n": 1, "lance": "H_0_1", "jogador": 1}],
        "placar": {"j1": 0, "j2": 0},
        "vez_de": -1,
    }
    solucao = {
        "lances": [
            {"n": 1, "jogador": -1, "lance": "V_1_0"},
            {"n": 2, "jogador": 1, "lance": "H_2_1"},
        ],
        "lance_chave": 2,
    }
    quadros = desenho.fita_da_solucao("sequencia_lances", posicao, solucao)
    assert len(quadros) == 3, "inicio + dois lances"
    assert all(q["svg"].startswith("<svg") for q in quadros)


def test_o_tabuleiro_de_damas_NUMERA_as_32_casas() -> None:
    """🔒 ⚠️ Sem numero, `21x30x23` nao se liga a desenho nenhum.

    E a curadoria e feita por quem **nao** tem a numeracao das damas na cabeca —
    foi o primeiro obstaculo que o dono relatou ao abrir o painel.
    """
    from api.desafios.painel import desenho

    svg = desenho.damas(POSICAO_DE_DAMAS, numerar=True)
    for casa in (1, 17, 32):
        assert f">{casa}</text>" in svg, f"a casa {casa} ficou sem numero"

    # E sem pedir, nao numera: a miniatura da fila nao precisa do ruido.
    assert ">32</text>" not in desenho.damas(POSICAO_DE_DAMAS)


def test_casas_do_lance_le_a_notacao_dos_DOIS_tipos_de_lance() -> None:
    """🔒 O caminho aceso sai da notacao, e nao de uma interpretacao do lance."""
    from api.desafios.painel.desenho import casas_do_lance

    assert casas_do_lance("24-19") == (24, 19)
    assert casas_do_lance("21x30x23") == (21, 30, 23)
    # ⚠️ A dama vem com `K` na FEN; na notacao de lance ela pode aparecer, e o
    # numero e que importa.
    assert casas_do_lance("K5-9") == (5, 9)


def test_o_rotulo_do_lance_sai_do_VEZ_DE_e_nao_de_um_lado_fixo() -> None:
    """🔒 ⛔ O painel chamou de "adversario" o primeiro lance do proprio dono.

    ⚠️ Quem resolve o desafio e quem joga **primeiro**, e isso nao e o mesmo
    numero nos dois jogos. Com o lado escrito a mao, metade das legendas mente —
    e mente justamente sobre a pergunta que a curadoria faz: *"este lance e meu
    ou dele?"*.
    """
    from api.desafios.painel import desenho

    posicao = {"lances": [{"n": 1, "lance": "H_0_1", "jogador": 1}], "vez_de": 1}
    solucao = {
        "lances": [
            {"n": 1, "jogador": 1, "lance": "V_1_0"},
            {"n": 2, "jogador": -1, "lance": "H_2_1"},
        ],
        "lance_chave": 1,
    }
    quadros = desenho.fita_da_solucao("sequencia_lances", posicao, solucao)
    assert [q["de_quem"] for q in quadros] == [None, "voce", "adversario"]
