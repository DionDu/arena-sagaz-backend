"""AS TRES LEITURAS DO APLICATIVO — T042 (contracts/desafio-publicado.md).

O que estes casos protegem:

  · ⛔ **o gabarito nunca viaja** (RF-DES-076) — em nenhuma das tres rotas, nem
    por engano numa coluna a mais;
  · ⛔ **so o aprovado e servido** (RF-DES-012a) — e o cadeado le o texto das
    consultas, para que uma consulta nova nao nasca sem a clausula;
  · **os dois instantes chegam juntos** (RF-DES-008), e sao o mesmo `agora` para
    a resposta inteira;
  · **a ordem das rotas**: `/{id}` casa com qualquer coisa e teria engolido
    `/hoje` e `/proximos` se viesse antes;
  · **"nao ha desafio hoje" e 404 com codigo**, e nao 200 com corpo vazio.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.desafios import repositorio as repo_desafio
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
        "ic_reprise": ic_reprise,
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
