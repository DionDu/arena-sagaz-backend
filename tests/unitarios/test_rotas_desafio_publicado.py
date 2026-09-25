"""AS TRES LEITURAS DO APLICATIVO — T042 (contracts/desafio-publicado.md).

O que estes casos protegem:

  · ⛔ **o gabarito nunca viaja** (RF-DES-076) — em nenhuma das tres rotas, nem
    por engano numa coluna a mais;
  · ⛔ **so o aprovado e servido** (RF-DES-012a) — e o cadeado le o texto das
    consultas, para que uma consulta nova nao nasca sem a clausula;
  · **os dois instantes chegam juntos** (RF-DES-008), e sao o mesmo `agora` para
    a resposta inteira;
  · ⚠️ **a regua de tempo viaja** (RF-DES-223) — `tempo_piso_ms`/`tempo_teto_ms`
    entraram em 16/09/2026, e sem eles a parcela `q_tempo` do XP nao fecha no
    aparelho; ⛔ **sem valor padrao**, porque um padrao plausivel pagaria XP
    errado em silencio;
  · ⚠️ **as medidas de saida viajam** (RF-DES-173) — entraram no mesmo dia, pelo
    mesmo motivo e achadas do mesmo jeito: elas sao a 4a parcela de `Q`, o
    merito, e sem elas o aplicativo mede a sessao sozinho e fica sem regua para
    o que a pessoa fez **no jogo**; ⛔ **pelo menos uma**, e ⛔ **sem a direcao**,
    que ja esta declarada nos dois catalogos;
  · **a ordem das rotas**: `/{id}` casa com qualquer coisa e teria engolido
    `/hoje` e `/proximos` se viesse antes;
  · **"nao ha desafio hoje" e 404 com codigo**, e nao 200 com corpo vazio.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.desafios import repositorio as repo_desafio
from api.desafios.modelos_resposta import MedidaDeSaidaPublicada
from api.desafios.publicacao import para_resposta
from api.desafios.rotas import obter_repositorio
from api.main import app
from api.nucleo.dependencias import (
    ContextoRequisicao,
    exigir_cabecalhos,
    usuario_atual_opcional,
)

AGORA = datetime(2026, 9, 10, 14, 22, 31, tzinfo=timezone.utc)
HOJE = AGORA.date()


def _linha(
    *,
    co_jogo: str = "damas",
    co_formato: str = "fen",
    dt_dia: date = HOJE,
    ic_reprise: bool = False,
    id_desafio=None,
    medidas_de_saida=None,
) -> dict:
    """Uma linha como as consultas de `repositorio.py` a devolvem.

    ⚠️ **Sem `js_solucao`** — e assim que ela chega de verdade: as consultas nao
    selecionam o gabarito.
    """
    js_posicao = (
        {"versao": 1, "fen": "W:W18,24,K27:B12,16,K22", "vez_de": 1}
        if co_formato == "fen"
        else {
            "versao": 1,
            "lances": [{"n": 1, "jogador": 1, "lance": "H_0_1"}],
            "vez_de": -1,
            "placar": {"j1": 0, "j2": 0},
        }
    )
    return {
        "id_desafio_dia": uuid4(),
        "dt_dia": dt_dia,
        "dh_encerramento": datetime.combine(
            dt_dia + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
        ),
        "id_desafio": id_desafio or uuid4(),
        "co_jogo": co_jogo,
        "co_modalidade": "brasileira" if co_jogo == "damas" else None,
        "co_variante": "padrao" if co_jogo == "damas" else "pequeno",
        "co_formato_posicao": co_formato,
        "js_posicao_inicial": js_posicao,
        "co_tipo_desafio": "damas_sacrificio",
        "js_chegada": {
            "versao": 1,
            "janela": {"tipo": "lances_do_jogador", "n": 3},
            "clausulas": [
                {
                    "tipo": "medida",
                    "chave": "capturas_extras",
                    "comparador": "maior_ou_igual",
                    "valor": 3,
                }
            ],
        },
        "co_chave_objetivo": "desafioObjetivoSacrificioDamas",
        "js_objetivo": {"dar": 1, "comer": 3},
        "co_personagem": "pita",
        "nu_semente": 2087461933,
        "co_versao_minima": "1.3.0",
        "co_versao_perfil": "perfil-2026-09",
        "nu_teto_log": 120,
        # ⚠️ De proposito **nao** sao os 30 s / 180 s do exemplo do
        # `data-model.md`: sao esses dois numeros que alguem escreveria a mao se
        # resolvesse "arbitrar uma regua padrao", e um teste que os usasse
        # passaria igual com o valor inventado. Aqui, nao passa.
        "nu_tempo_piso_ms": 12_000,
        "nu_tempo_teto_ms": 95_000,
        "ic_reprise": ic_reprise,
        # ⚠️ O que este desafio pontua, como `_com_medidas` anexa a linha. Os
        # pesos sao **relativos dentro do merito** e somam 1,000; a terceira e
        # uma medida exibida e nao pontuada (peso zero).
        "medidas_de_saida": medidas_de_saida
        if medidas_de_saida is not None
        else [
            {
                "co_feito": "capturas_extras",
                "vr_peso": Decimal("0.700"),
                "co_normalizacao": "faixa",
                "vr_min": Decimal("0"),
                "vr_max": Decimal("3"),
                "co_sobre": None,
            },
            {
                "co_feito": "material_restante",
                "vr_peso": Decimal("0.300"),
                "co_normalizacao": "fracao",
                "vr_min": None,
                "vr_max": None,
                "co_sobre": "material_do_adversario",
            },
            {
                "co_feito": "damas_coroadas",
                "vr_peso": Decimal("0.000"),
                "co_normalizacao": "nenhuma",
                "vr_min": None,
                "vr_max": None,
                "co_sobre": None,
            },
        ],
    }


class RepoFalso:
    """Um `RepositorioDesafio` de mentira."""

    def __init__(self, hoje=None, proximos=None, por_id=None) -> None:
        self._hoje = hoje
        self._proximos = proximos or []
        self._por_id = por_id

    async def de_hoje(self, *, agora=None):
        return self._hoje

    async def proximos(self, *, dt_hoje, limite=3):
        return self._proximos[:limite]

    async def por_id(self, id_desafio):
        return self._por_id


@pytest.fixture
def cliente():
    """Cliente com os cabecalhos obrigatorios ja satisfeitos."""
    app.dependency_overrides[exigir_cabecalhos] = lambda: ContextoRequisicao(
        versao_app="1.3.0", plataforma="android", idioma="pt"
    )
    app.dependency_overrides[usuario_atual_opcional] = lambda: None
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════
# 1. ⛔ O gabarito nunca viaja (RF-DES-076)
# ═══════════════════════════════════════════════════════════════════════════


def test_a_resposta_de_hoje_nao_traz_a_solucao(cliente):
    """⛔ O spoiler entregue de graca junto com o enunciado.

    ⚠️ Sao **duas** barreiras: a consulta nao seleciona `js_solucao`, e o modelo
    de resposta lista os campos um a um. A segunda existe para o dia em que
    alguem acrescentar a coluna a consulta sem perceber.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())

    corpo = cliente.get("/v1/desafios/hoje").json()

    assert "js_solucao" not in corpo
    assert "solucao" not in corpo
    assert "gabarito" not in corpo
    # ⛔ E nem os lances do adversario: publicá-los restringiria o catalogo a
    # finais (RF-DES-200). Quem joga e o motor do aparelho.
    assert "lances_adversario" not in corpo


def test_as_consultas_nao_selecionam_o_gabarito():
    """A primeira barreira, lida no texto do SQL."""
    for nome, sql in repo_desafio.CONSULTAS_PUBLICAS.items():
        assert "js_solucao" not in sql, f"{nome} traz o gabarito"


# ═══════════════════════════════════════════════════════════════════════════
# 2. ⛔ So o aprovado (RF-DES-012a)
# ═══════════════════════════════════════════════════════════════════════════


def test_toda_consulta_publica_filtra_por_aprovado():
    """⛔ **O cadeado que le o texto**, e nao uma funcao que "aplica o filtro".

    Uma consulta nova que esquecesse de chamar a funcao serviria conteudo nao
    revisado **sem erro nenhum** — e a primeira vez seria com um desafio
    impossivel no ar. Escrita em cada consulta, a falta e visivel aqui.
    """
    for nome, sql in repo_desafio.CONSULTAS_PUBLICAS.items():
        assert "co_curadoria = 'aprovado'" in sql, (
            f"a consulta {nome!r} nao filtra por curadoria: ela serviria "
            "candidato ao aplicativo."
        )


def test_ha_tres_consultas_publicas_e_o_cadeado_as_ve_todas():
    """⚠️ Se uma quarta rota nascer, ela entra no dicionario — ou o cadeado
    deixa de cobri-la sem que nada acuse."""
    assert set(repo_desafio.CONSULTAS_PUBLICAS) == {"hoje", "proximos", "por_id"}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Os dois instantes (RF-DES-008)
# ═══════════════════════════════════════════════════════════════════════════


def test_os_dois_instantes_chegam_juntos(cliente):
    """⚠️ O aplicativo guarda a **diferenca** contra um relogio monotonico.

    O relogio de parede do aparelho nao entra na conta: ele pode estar errado,
    adiantado, ou mudar de fuso no meio da partida.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())

    corpo = cliente.get("/v1/desafios/hoje").json()

    assert "encerra_em" in corpo and "agora_no_servidor" in corpo
    assert corpo["encerra_em"].endswith("Z") or "+00:00" in corpo["encerra_em"]


def test_o_mesmo_agora_serve_a_resposta_inteira(cliente):
    """⚠️ Ler o relogio por item faria cada desafio calibrar com uma base
    diferente."""
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(
        proximos=[_linha(dt_dia=HOJE + timedelta(days=n)) for n in (1, 2, 3)]
    )

    corpo = cliente.get("/v1/desafios/proximos").json()

    instantes = {d["agora_no_servidor"] for d in corpo["desafios"]}
    assert len(instantes) == 1
    assert instantes == {corpo["agora_no_servidor"]}


def test_o_encerramento_e_o_do_VINCULO_e_nao_do_desafio():
    """⚠️ RF-DES-152: a data de publicacao mora no vinculo, nunca no desafio."""
    linha = _linha()
    resposta = para_resposta(linha, agora=AGORA)
    assert resposta.encerra_em == linha["dh_encerramento"]
    assert resposta.id_desafio_dia == linha["id_desafio_dia"]


def test_o_DIA_do_desafio_viaja_e_e_o_do_vinculo():
    """⚠️ T085zc: o toque na notificacao de reacoes abre o Raio-X de um dia que
    passou, e o card do dia escreve a data. ⛔ Deduzi-la de `encerra_em` no app
    amarraria o app a regra de encerramento do job."""
    linha = _linha()
    resposta = para_resposta(linha, agora=AGORA)
    assert resposta.dia == linha["dt_dia"]


def test_as_tres_consultas_publicas_trazem_o_dia():
    """🔒 O duplo acima traz `dt_dia`; e o SQL que decide se ele chega."""
    from api.desafios.repositorio import _COLUNAS

    assert "dia.dt_dia" in _COLUNAS


# ═══════════════════════════════════════════════════════════════════════════
# 4. A forma da resposta (contracts/desafio-publicado.md)
# ═══════════════════════════════════════════════════════════════════════════


def test_o_objetivo_vai_como_CHAVE_e_valores():
    """⛔ Nunca a frase pronta (RF-DES-176): ela viajaria num idioma so."""
    resposta = para_resposta(_linha(), agora=AGORA)
    assert resposta.objetivo.chave == "desafioObjetivoSacrificioDamas"
    assert resposta.objetivo.valores == {"dar": 1, "comer": 3}


def test_a_forma_de_verificacao_viaja_como_campo():
    """⚠️ E a 3a das cinco conferencias de compatibilidade do contrato.

    Uma forma nova no futuro faria as versoes antigas caírem na tela de
    atualizar, em vez de tentarem julgar com uma regra que nao entendem.
    """
    assert para_resposta(_linha(), agora=AGORA).forma_verificacao == "clausulas"


def test_damas_manda_a_FEN_e_pontinhos_manda_a_sequencia():
    """⚠️ **Exatamente um** dos dois campos vem preenchido.

    A FEN cabe numa string; a posicao do Pontinhos, nao — a posse de uma caixa e
    **historico**, e so a sequencia a descreve. Os dois preenchidos seriam duas
    fontes para a mesma coisa.
    """
    damas = para_resposta(_linha(co_jogo="damas", co_formato="fen"), agora=AGORA)
    assert damas.tabuleiro == "W:W18,24,K27:B12,16,K22"
    assert damas.posicao is None
    assert damas.tamanho is None  # `tamanho` e do Pontinhos

    pontinhos = para_resposta(
        _linha(co_jogo="pontinhos", co_formato="sequencia_lances"), agora=AGORA
    )
    assert pontinhos.tabuleiro is None
    assert pontinhos.posicao is not None
    assert pontinhos.posicao["lances"][0]["lance"] == "H_0_1"
    assert pontinhos.tamanho == "pequeno"


def test_a_variante_vem_sempre_e_o_tamanho_e_so_um_apelido():
    """⚠️ `tamanho` e o nome que o contrato deu a `co_variante` no Pontinhos.

    ⛔ Nao sao duas informacoes: `variante` e o campo generico, e e ele que um
    jogo novo usa sem precisar de campo proprio.
    """
    damas = para_resposta(_linha(co_jogo="damas"), agora=AGORA)
    assert damas.variante == "padrao" and damas.tamanho is None


def test_a_semente_viaja_porque_o_adversario_e_o_MESMO_para_todos():
    """⚠️ Sem ela, dois aparelhos jogariam contra CPUs diferentes — e o quadro do
    dia compararia partidas que nao sao a mesma."""
    assert para_resposta(_linha(), agora=AGORA).semente == 2087461933


def test_a_reprise_vem_marcada():
    """O rotulo que diz que o dia e uma repeticao (RF-DES-029)."""
    assert para_resposta(_linha(ic_reprise=True), agora=AGORA).reprise is True


def test_a_REGUA_DE_TEMPO_viaja_com_o_desafio():
    """⚠️ Sem ela, "rapido" nao tem contra o que ser medido (RF-DES-223).

    A parcela `q_tempo` de `Q` e `(teto - t) / (teto - piso)`, e ela **fecha no
    aparelho**: SC-002 exige veredito e XP sem rede no caminho critico. Este
    caso existe porque a ausencia dos dois campos **nao dava erro nenhum** — ela
    foi achada em 16/09/2026, lendo o contrato ao escrever o modelo do
    aplicativo, e nao por uma falha.

    ⛔ Os valores conferidos sao os da linha, e nao um par plausivel: um padrao
    arbitrado no servidor pagaria XP errado **em silencio**.
    """
    resposta = para_resposta(_linha(), agora=AGORA)

    assert resposta.tempo_piso_ms == 12_000
    assert resposta.tempo_teto_ms == 95_000



def test_as_MEDIDAS_DE_SAIDA_viajam_com_o_desafio(cliente):
    """⚠️ **A 4a parcela de `Q`** (RF-DES-173), e o segundo buraco achado do
    mesmo jeito que a regua: escrevendo o consumidor.

    As linhas existem em `tb003_feito_desafio` desde a `0018` e o job as grava;
    ate 16/09/2026 nenhuma chegava ao aplicativo, que sem elas nao tem como
    fechar o merito no aparelho (SC-002).
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())

    medidas = cliente.get("/v1/desafios/hoje").json()["medidas_de_saida"]

    assert [m["chave"] for m in medidas] == [
        "capturas_extras",
        "material_restante",
        "damas_coroadas",
    ]
    # ⚠️ Os pesos sao **relativos dentro dos 0,25 do merito**, e somam 1,000
    # entre si. Publicar ja multiplicado esconderia essa soma, que e a
    # conferencia barata do outro lado.
    assert sum(m["peso"] for m in medidas) == 1.0
    assert medidas[0]["minimo"] == 0 and medidas[0]["maximo"] == 3
    assert medidas[1]["sobre"] == "material_do_adversario"
    # Peso zero: exibida no Raio-X, nao pontua.
    assert medidas[2]["peso"] == 0 and medidas[2]["normalizacao"] == "nenhuma"


def test_a_DIRECAO_nao_viaja_com_as_medidas(cliente):
    """⛔ Ela ja esta declarada nos DOIS catalogos, e publica-la seria escreve-la
    uma segunda vez.

    ⚠️ No dia em que as duas discordassem ninguem perceberia: uma parcela na
    direcao errada **nao da erro**, so paga mais a quem jogou pior.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())

    medidas = cliente.get("/v1/desafios/hoje").json()["medidas_de_saida"]

    for m in medidas:
        assert "direcao" not in m
        assert "co_direcao" not in m
        # ⚠️ Nem o identificador numerico da dimensao: o aplicativo conhece as
        # medidas pela chave, e um numero seria uma segunda identidade.
        assert "nu_feito" not in m

    # ⚠️ **E a guarda e sobre o MODELO, nao so sobre esta resposta.** Uma
    # mutacao que acrescentasse `co_direcao` ao SELECT passaria pelo laco acima
    # sem ser vista, porque `publicacao.py` monta a medida campo a campo; quem
    # precisa nao ter o campo e a classe.
    assert "direcao" not in MedidaDeSaidaPublicada.model_fields
    assert "nu_feito" not in MedidaDeSaidaPublicada.model_fields


def test_desafio_SEM_medida_de_saida_nao_vira_resposta_plausivel(cliente):
    """⛔ **Sem valor padrao, e sem lista vazia.**

    Um desafio sem medida de saida teria o Raio-X vazio e o merito sem do que ser
    calculado — e a resposta sairia **plausivel e errada**, pagando merito zero a
    todo mundo. O `conferir` do job ja recusa publicar assim; aqui a falta
    estoura na leitura.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(
        hoje=_linha(medidas_de_saida=[])
    )

    with pytest.raises(Exception):
        cliente.get("/v1/desafios/hoje")


class SessaoFalsa:
    """Uma sessao que devolve linhas prontas, na ordem em que sao pedidas.

    ⚠️ Existe porque `RepoFalso` substitui o repositorio inteiro, e com ele o
    metodo que anexa as medidas nunca rodava: uma mutacao que apagasse a juncao
    passava por todos os casos acima. ⛔ Testar a rota nao testa o repositorio.
    """

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.comandos = []

    async def execute(self, comando, parametros=None):
        self.comandos.append((str(comando), parametros))
        linhas = self._respostas.pop(0)

        class _Resultado:
            def mappings(self_):
                class _M:
                    def all(self__):
                        return linhas

                return _M()

        return _Resultado()


@pytest.mark.asyncio
async def test_o_repositorio_ANEXA_as_medidas_a_cada_linha():
    """⚠️ O metodo que as tres leituras compartilham, exercitado de verdade.

    A consulta das medidas e **uma so para o lote** (`= ANY(:ids)`): uma por
    desafio seria N+1 no `/proximos`, que o aplicativo chama toda manha.
    """
    id_a, id_b = uuid4(), uuid4()
    medidas = [
        {
            "id_desafio": id_a,
            "co_feito": "capturas_extras",
            "vr_peso": Decimal("1.000"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("3"),
            "co_sobre": None,
        },
        {
            "id_desafio": id_b,
            "co_feito": "caixas_fechadas",
            "vr_peso": Decimal("1.000"),
            "co_normalizacao": "faixa",
            "vr_min": Decimal("0"),
            "vr_max": Decimal("4"),
            "co_sobre": None,
        },
    ]
    sessao = SessaoFalsa([medidas])
    repo = repo_desafio.RepositorioDesafio(sessao)

    linhas = await repo._com_medidas(
        [{"id_desafio": id_a}, {"id_desafio": id_b}]
    )

    assert [m["co_feito"] for m in linhas[0]["medidas_de_saida"]] == [
        "capturas_extras"
    ]
    assert [m["co_feito"] for m in linhas[1]["medidas_de_saida"]] == [
        "caixas_fechadas"
    ]
    # ⚠️ **Uma consulta so**, e nao uma por desafio.
    assert len(sessao.comandos) == 1
    assert sessao.comandos[0][1] == {"ids": [id_a, id_b]}


@pytest.mark.asyncio
async def test_desafio_sem_medida_chega_com_lista_VAZIA_e_nao_inventada():
    """⛔ O repositorio nao inventa uma medida no lugar da que falta.

    Ele entrega a lista vazia, e quem recusa e o modelo de resposta - onde o erro
    e visivel. Inventar aqui faria a resposta sair **plausivel e errada**.
    """
    id_a = uuid4()
    repo = repo_desafio.RepositorioDesafio(SessaoFalsa([[]]))

    linhas = await repo._com_medidas([{"id_desafio": id_a}])

    assert linhas[0]["medidas_de_saida"] == []


def test_as_tres_leituras_anexam_as_medidas(cliente):
    """⚠️ O cadeado de que **nenhuma rota pode esquecer**.

    As tres passam pelo mesmo `_com_medidas` do repositorio; um caminho que o
    saltasse estouraria na montagem da resposta, que e onde o erro e visivel.
    """
    linha = _linha()
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(
        hoje=linha, proximos=[linha], por_id=linha
    )

    de_hoje = cliente.get("/v1/desafios/hoje").json()
    proximos = cliente.get("/v1/desafios/proximos").json()
    por_id = cliente.get(f"/v1/desafios/{linha['id_desafio']}").json()

    assert de_hoje["medidas_de_saida"]
    assert proximos["desafios"][0]["medidas_de_saida"]
    assert por_id["medidas_de_saida"]

def test_a_regua_e_OBRIGATORIA_e_a_falta_estoura_aqui(cliente):
    """⛔ **Nao ha valor padrao**, e e isso que este caso tranca.

    Um `= 30_000` no modelo faria uma consulta que esquecesse a coluna devolver
    uma resposta **plausivel e errada** — o aplicativo dividiria por uma regua
    que nao e a do desafio, e ninguem veria diferenca ate o XP sair torto. Sem
    padrao, a falta e um erro alto, na hora, em teste.
    """
    linha = _linha()
    del linha["nu_tempo_piso_ms"]
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=linha)

    with pytest.raises(KeyError):
        cliente.get("/v1/desafios/hoje")


def test_as_tres_consultas_publicas_trazem_a_regua():
    """⚠️ O cadeado que le o **texto** do SQL, como o da curadoria.

    `para_resposta` le `nu_tempo_piso_ms` da linha; quem poe a coluna na linha e
    a consulta. Uma quarta rota que nascesse sem as duas colunas so falharia no
    dia em que fosse chamada — e falharia com `KeyError`, longe da causa.
    """
    for nome, sql in repo_desafio.CONSULTAS_PUBLICAS.items():
        assert "nu_tempo_piso_ms" in sql, f"{nome} nao traz o piso da regua"
        assert "nu_tempo_teto_ms" in sql, f"{nome} nao traz o teto da regua"


def test_a_colecao_vem_na_resposta():
    """⚠️ O desafio e transversal ao hub; o Desafio do Dia e a primeira colecao.

    O campo existe desde ja para que um torneio futuro nao exija versao nova do
    aplicativo so para dizer de onde aquele desafio veio.
    """
    assert para_resposta(_linha(), agora=AGORA).colecao == "desafio_do_dia"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Os estados que nao sao erro, e o que e
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_desafio_hoje_e_404_com_codigo_proprio(cliente):
    """⚠️ O aplicativo precisa separar tres situacoes com telas diferentes:
    sem rede · **ha servidor e nao ha desafio** · joga.

    Um `200` com corpo vazio confundiria a segunda com a terceira, e a tela
    mostraria o esqueleto de um desafio que nao existe.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=None)

    resposta = cliente.get("/v1/desafios/hoje")

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "sem_desafio_hoje"


def test_proximos_vazio_e_200_e_nao_404(cliente):
    """⚠️ Nao ter proximos e o estado normal de uma fila recem-consumida.

    Um erro ai faria o aplicativo tratar operacao rotineira como falha.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(proximos=[])

    resposta = cliente.get("/v1/desafios/proximos")

    assert resposta.status_code == 200
    assert resposta.json()["desafios"] == []


def test_desafio_inexistente_e_nao_aprovado_dao_a_MESMA_resposta(cliente):
    """⚠️ Distinguir os dois contaria a quem perguntou que ha um candidato com
    aquele identificador."""
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(por_id=None)

    resposta = cliente.get(f"/v1/desafios/{uuid4()}")

    assert resposta.status_code == 404
    assert resposta.json()["codigo"] == "desafio_inexistente"


# ═══════════════════════════════════════════════════════════════════════════
# 6. A ordem das rotas
# ═══════════════════════════════════════════════════════════════════════════


def test_hoje_e_proximos_nao_sao_engolidos_pela_rota_de_id():
    """⚠️ `/{id_desafio}` casa com **qualquer coisa**.

    Declarada antes das outras duas, ela engoliria `/hoje` e `/proximos`, que
    chegariam la como UUID invalido e virariam 422 numa rota que existe. O
    FastAPI casa na ordem de registro, entao a ordem e a garantia.
    """
    caminhos = [r.path for r in app.routes if r.path.startswith("/v1/desafios")]
    assert caminhos.index("/v1/desafios/hoje") < caminhos.index(
        "/v1/desafios/{id_desafio}"
    )
    assert caminhos.index("/v1/desafios/proximos") < caminhos.index(
        "/v1/desafios/{id_desafio}"
    )


def test_convidado_le_o_desafio_de_hoje(cliente):
    """⚠️ Exigir login aqui poria um muro antes do primeiro contato.

    O desafio publicado e o mesmo para todo mundo, e nada na resposta depende de
    quem pergunta. Resolver, ai sim, exige conta.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())
    # `usuario_atual_opcional` ja devolve `None` na fixture — e o convidado.
    assert cliente.get("/v1/desafios/hoje").status_code == 200


def test_a_resposta_nao_pode_ficar_muito_tempo_em_cache(cliente):
    """⚠️ O desafio nao muda no dia, mas `agora_no_servidor` sim.

    Uma resposta guardada por meia hora entregaria um `agora` de meia hora
    atras, e a contagem regressiva nasceria adiantada no aparelho.
    """
    app.dependency_overrides[obter_repositorio] = lambda: RepoFalso(hoje=_linha())

    cabecalho = cliente.get("/v1/desafios/hoje").headers["cache-control"]

    assert "max-age=30" in cabecalho
