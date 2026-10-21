"""O registro do aparelho no banco: uma linha por aparelho por dia (T118).

O SQL é o do repositório, rodando de verdade num SQLite de memória (o porquê, e
o que ele não prova, está em `banco_de_aparelho_sqlite.py`). Quem chama é o
**serviço** de verdade: é nele que moram as três perguntas - *qual aparelho*,
*de quem*, *que dia* -, e testar o repositório sozinho deixaria de fora
justamente a linha legada e o fuso.

Os casos seguem a lista da T118 em `specs/010-jogo-quatro-em-linha/tasks.md`:

* duas leituras no mesmo dia dão UMA linha, com a MAIOR versão;
* o dia é o LOCAL da pessoa;
* um app 1.3 (sem o cabeçalho) entra como LEGADO, e é contado;
* o convidado 1.3 não entra;
* o detalhe do espaço acima do limite é guardado, e abaixo vira `NULL`;
* a exclusão de conta zera o `id_usuario` da `tb004`.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text

from api.aparelhos import repositorio as modulo_repositorio
from api.aparelhos.regras import id_aparelho_legado
from api.aparelhos.repositorio import ErroDoRegistroDoDia, RepositorioAparelho
from api.aparelhos.servico import CabecalhosDoAparelho, ServicoAparelho
from api.conta.repositorio import RepositorioUsuario
from tests.unitarios.banco_de_aparelho_sqlite import abrir_banco, linhas, trocar_cast_jsonb

#: Um aparelho 1.4 (o código é um UUID v4, como o app o gera).
APARELHO = uuid.UUID("3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b")
#: A pessoa: o uid do Firebase e o id interno da conta.
UID = "firebase-uid-da-pessoa"
ID_USUARIO = "63385354-1e03-44bc-b2a3-82fdb8e34547"
OUTRA_PESSOA = "00000000-0000-0000-0000-000000000001"

#: 01h30 UTC de 20/10: no Brasil (UTC-3) ainda são 22h30 de 19/10. É o instante
#: que separa o dia UTC do dia local - um caso às 15h UTC não mediria nada,
#: porque os dois dias coincidiriam.
MADRUGADA_UTC = datetime(2026, 10, 20, 1, 30, tzinfo=timezone.utc)
#: 15h UTC do mesmo dia: o dia local e o UTC coincidem no Brasil.
TARDE_UTC = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)

LIMITES = {"android": 150, "ios": 300}


@pytest_asyncio.fixture
async def sessao(monkeypatch):
    """Uma sessão sobre o SQLite do aparelho, com a pessoa já cadastrada."""
    trocar_cast_jsonb(monkeypatch)
    engine, s = await abrir_banco()
    await s.execute(
        text("INSERT INTO conta.vw001_usuario VALUES (:id, :uid)"),
        {"id": ID_USUARIO, "uid": UID},
    )
    await s.commit()
    yield s
    await s.close()
    await engine.dispose()


@pytest.fixture
def servico(sessao) -> ServicoAparelho:
    return ServicoAparelho(repo=RepositorioAparelho(sessao), sessao=sessao)


async def _visita(
    servico: ServicoAparelho,
    *,
    versao: str = "1.4.0",
    plataforma: str = "android",
    aparelho: uuid.UUID | None = APARELHO,
    offset: int | None = None,
    uid: str | None = None,
    agora: datetime = TARDE_UTC,
):
    """Uma leitura do desafio do dia, com os defaults de um app 1.4 convidado."""
    return await servico.registrar_visita(
        versao_app=versao,
        plataforma=plataforma,
        idioma="pt",
        cabecalhos=CabecalhosDoAparelho(id_aparelho=aparelho, offset_minuto=offset),
        uid=uid,
        agora=agora,
    )


async def _dias(sessao) -> list[dict]:
    return await linhas(
        sessao,
        "SELECT id_aparelho, dt_dia_local, id_usuario, co_versao_app, co_idioma, "
        "co_versao_so, nu_espaco_app_kb, js_espaco_app "
        "FROM log.tb004_aparelho_dia ORDER BY dt_dia_local",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. Uma linha por aparelho por dia, com a MAIOR versão
# ═══════════════════════════════════════════════════════════════════════════


async def test_duas_leituras_no_mesmo_dia_dao_uma_linha_com_a_maior_versao(servico, sessao):
    """O caso que a tabela existe para garantir: abrir o app duas vezes no dia,
    atualizando no meio, dá uma linha só - e com a versão de depois."""
    await _visita(servico, versao="1.3.1")
    await _visita(servico, versao="1.4.0")

    dias = await _dias(sessao)
    assert len(dias) == 1
    assert dias[0]["co_versao_app"] == "1.4.0"


async def test_a_versao_do_dia_nunca_desce(servico, sessao):
    """Uma leitura com versão MENOR depois de uma maior não muda nada: a linha
    guarda a maior vista. (Duas instalações não dividem um código; isto cobre o
    cabeçalho de um pedido velho chegando atrasado.)"""
    await _visita(servico, versao="1.4.0")
    registro = await _visita(servico, versao="1.3.1")

    assert (await _dias(sessao))[0]["co_versao_app"] == "1.4.0"
    assert registro.co_versao_app == "1.4.0"


async def test_a_maior_versao_e_a_dos_NUMEROS_e_nao_a_do_texto(servico, sessao):
    """`"1.10.0" < "1.9.0"` para o texto. A versão 1.10 tem de vencer a 1.9 -
    senão, na virada para dois dígitos, a adoção leria todo mundo como velho."""
    await _visita(servico, versao="1.9.0")
    await _visita(servico, versao="1.10.0")

    assert (await _dias(sessao))[0]["co_versao_app"] == "1.10.0"


async def test_dias_diferentes_dao_linhas_diferentes(servico, sessao):
    await _visita(servico, agora=TARDE_UTC)
    await _visita(servico, agora=datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc))

    assert [d["dt_dia_local"] for d in await _dias(sessao)] == ["2026-10-20", "2026-10-21"]


async def test_o_aparelho_tem_UMA_linha_por_mais_leituras_que_haja(servico, sessao):
    for versao in ("1.4.0", "1.4.0", "1.4.1"):
        await _visita(servico, versao=versao)

    aparelhos = await linhas(sessao, "SELECT id_aparelho, ic_legado FROM log.tb003_aparelho")
    assert aparelhos == [{"id_aparelho": str(APARELHO), "ic_legado": 0}]


async def test_versao_que_nao_se_le_nao_grava_nada(servico, sessao):
    """Um texto sem forma de versão não tem ordem: gravado, deixaria a linha do
    dia sem como subir."""
    assert await _visita(servico, versao="dev") is None
    assert await _dias(sessao) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2. O dia é o LOCAL da pessoa
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_dia_e_o_do_fuso_que_o_app_mandou(servico, sessao):
    """01h30 UTC de 20/10 com o fuso do Brasil é 19/10 para quem está lá."""
    registro = await _visita(servico, agora=MADRUGADA_UTC, offset=-180)

    assert registro.dt_dia_local == date(2026, 10, 19)
    assert (await _dias(sessao))[0]["dt_dia_local"] == "2026-10-19"


async def test_sem_fuso_nenhum_o_dia_e_o_UTC(servico):
    """O convidado 1.4 sem o cabeçalho do fuso (um app com defeito) cai no dia
    UTC: o melhor palpite, e nunca pior do que não gravar."""
    registro = await _visita(servico, agora=MADRUGADA_UTC, offset=None)
    assert registro.dt_dia_local == date(2026, 10, 20)


async def test_o_app_1_3_usa_o_fuso_da_ultima_partida_da_pessoa(servico, sessao):
    """O 1.3 não manda fuso. O palpite é o relógio da ÚLTIMA partida dela - o
    mesmo que a chama usa. A partida mais antiga (fuso +60) não vale, e a mais
    nova SEM fuso (um app antigo que não o gravava) é pulada, e não lida como
    UTC."""
    await sessao.execute(
        text(
            "INSERT INTO partida.vw001_partida VALUES "
            "(:id, 60, '2026-09-01T10:00:00'), (:id, -180, '2026-10-18T22:00:00'), "
            "(:id, NULL, '2026-10-19T09:00:00'), (:outra, 600, '2026-10-19T22:00:00')"
        ),
        {"id": ID_USUARIO, "outra": OUTRA_PESSOA},
    )
    registro = await _visita(servico, aparelho=None, uid=UID, agora=MADRUGADA_UTC)

    assert registro.dt_dia_local == date(2026, 10, 19)


async def test_o_fuso_do_cabecalho_vence_o_da_ultima_partida(servico, sessao):
    """Quem viaja leva o aparelho: o fuso de AGORA é o do cabeçalho, e não o da
    partida de ontem."""
    await sessao.execute(
        text("INSERT INTO partida.vw001_partida VALUES (:id, -180, '2026-10-18T22:00:00')"),
        {"id": ID_USUARIO},
    )
    registro = await _visita(servico, uid=UID, agora=MADRUGADA_UTC, offset=0)

    assert registro.dt_dia_local == date(2026, 10, 20)


# ═══════════════════════════════════════════════════════════════════════════
# 3. O app 1.3: a linha LEGADA, e o convidado que fica de fora
# ═══════════════════════════════════════════════════════════════════════════


async def test_o_app_1_3_logado_entra_como_LEGADO_e_e_contado(servico, sessao):
    """Sem o cabeçalho e com conta: o aparelho é sintetizado (uuid5 da conta e
    da plataforma), marcado como legado, e o dia é contado."""
    registro = await _visita(servico, versao="1.3.1", aparelho=None, uid=UID)

    esperado = str(id_aparelho_legado(ID_USUARIO, "android"))
    assert registro.id_aparelho == esperado and registro.ic_legado
    assert await linhas(sessao, "SELECT id_aparelho, ic_legado FROM log.tb003_aparelho") == [
        {"id_aparelho": esperado, "ic_legado": 1}
    ]
    dias = await _dias(sessao)
    assert [(d["id_aparelho"], d["id_usuario"], d["co_versao_app"]) for d in dias] == [
        (esperado, ID_USUARIO, "1.3.1")
    ]


async def test_a_linha_legada_e_a_MESMA_a_cada_abertura(servico, sessao):
    """Determinística, e por isso idempotente: cinco aberturas, um aparelho."""
    for _ in range(5):
        await _visita(servico, versao="1.3.1", aparelho=None, uid=UID)

    assert len(await linhas(sessao, "SELECT 1 FROM log.tb003_aparelho")) == 1
    assert len(await _dias(sessao)) == 1


async def test_a_mesma_pessoa_em_duas_plataformas_sao_dois_aparelhos(servico, sessao):
    """Quem tem um Android e um iPad conta duas vezes, com a versão de cada um -
    que é o que a adoção quer contar."""
    await _visita(servico, versao="1.3.1", aparelho=None, uid=UID, plataforma="android")
    await _visita(servico, versao="1.3.0", aparelho=None, uid=UID, plataforma="ios")

    assert sorted(d["co_versao_app"] for d in await _dias(sessao)) == ["1.3.0", "1.3.1"]


async def test_o_convidado_1_3_nao_entra(servico, sessao):
    """Sem código e sem conta não há a quem atribuir a leitura - como já não
    havia antes desta tabela."""
    assert await _visita(servico, versao="1.3.1", aparelho=None, uid=None) is None
    assert await linhas(sessao, "SELECT 1 FROM log.tb003_aparelho") == []
    assert await _dias(sessao) == []


async def test_uid_sem_conta_aqui_vale_como_convidado(servico, sessao):
    """O token é válido, mas o perfil ainda não foi completado: o uid existe no
    Firebase, e a conta ainda não existe aqui. No 1.3 isso é convidado."""
    assert await _visita(servico, aparelho=None, uid="uid-sem-conta") is None


async def test_o_convidado_1_4_entra_sem_dono(servico, sessao):
    await _visita(servico, uid=None)
    assert (await _dias(sessao))[0]["id_usuario"] is None


async def test_uma_leitura_de_convidado_nao_apaga_a_pessoa_do_dia(servico, sessao):
    """Logou, saiu e abriu de novo no mesmo dia: o dia continua dela."""
    await _visita(servico, uid=UID)
    await _visita(servico, uid=None)

    assert (await _dias(sessao))[0]["id_usuario"] == ID_USUARIO


async def test_o_registro_CONFIRMA_a_transacao(servico, sessao):
    """⚠️ Escrita sem `commit` some quando a sessão da requisição fecha. Um
    `rollback` depois do registro não pode levar a linha embora."""
    await _visita(servico)
    await sessao.rollback()

    assert len(await _dias(sessao)) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. A corrida: a versão nunca desce, nem com duas leituras cruzadas
# ═══════════════════════════════════════════════════════════════════════════


class _SessaoQueCruza:
    """Uma sessão que, antes de cada escrita do dia, deixa "outra leitura"
    passar na frente - a corrida que o registro existe para perder com
    elegância.

    * antes de um `UPDATE`, a outra grava uma versão maior (a trava `WHERE
      co_versao_app = :versao_lida` tem de recusar a escrita velha);
    * antes de um `INSERT`, a outra CRIA a linha (o `DO NOTHING` não devolve
      nada, e o registro tem de reler, e não declarar vitória).
    """

    def __init__(self, sessao, versoes_da_outra: list[str]) -> None:
        self._sessao = sessao
        self._versoes = list(versoes_da_outra)

    async def execute(self, comando, parametros=None):
        sql = str(comando)
        if self._versoes and "UPDATE log.tb004_aparelho_dia" in sql:
            await self._sessao.execute(
                text("UPDATE log.tb004_aparelho_dia SET co_versao_app = :v"),
                {"v": self._versoes.pop(0)},
            )
        elif self._versoes and "INSERT INTO log.tb004_aparelho_dia" in sql:
            await self._sessao.execute(
                text(
                    "INSERT INTO log.tb004_aparelho_dia "
                    "(id_aparelho, dt_dia_local, co_versao_app) VALUES (:a, :d, :v)"
                ),
                {
                    "a": parametros["id_aparelho"],
                    "d": parametros["dt_dia_local"],
                    "v": self._versoes.pop(0),
                },
            )
        return await self._sessao.execute(comando, parametros)


async def test_a_leitura_que_perde_a_corrida_rele_e_nao_desce_a_versao(servico, sessao):
    """A linha tem 1.3.0; esta leitura traz 1.4.0. No meio, outra grava 1.5.0.
    Sem a trava, a 1.4.0 escreveria por cima da 1.5.0."""
    await _visita(servico, versao="1.3.0")
    repo = RepositorioAparelho(_SessaoQueCruza(sessao, ["1.5.0"]))

    final = await repo.registrar_dia(
        id_aparelho=str(APARELHO),
        dt_dia_local=date(2026, 10, 20),
        id_usuario=None,
        co_versao_app="1.4.0",
        co_idioma="pt",
    )

    assert final == "1.5.0"
    assert (await _dias(sessao))[0]["co_versao_app"] == "1.5.0"


async def test_a_linha_criada_por_outra_leitura_no_meio_e_relida(servico, sessao):
    """Ninguém tinha linha; no instante entre ler e criar, outra leitura criou a
    dela com 1.5.0. O `INSERT ... DO NOTHING` não devolve nada - e o registro
    tem de reler e comparar, e não dizer que gravou a 1.4.0."""
    await _visita(servico, versao="1.3.0")  # só para o aparelho existir (a FK)
    await sessao.execute(text("DELETE FROM log.tb004_aparelho_dia"))
    repo = RepositorioAparelho(_SessaoQueCruza(sessao, ["1.5.0"]))

    final = await repo.registrar_dia(
        id_aparelho=str(APARELHO),
        dt_dia_local=date(2026, 10, 20),
        id_usuario=None,
        co_versao_app="1.4.0",
        co_idioma="pt",
    )

    assert final == "1.5.0"
    assert [d["co_versao_app"] for d in await _dias(sessao)] == ["1.5.0"]


async def test_perder_a_corrida_sempre_vira_erro_com_nome(servico, sessao):
    """Três voltas perdidas seguidas não prendem a requisição num laço: viram um
    erro que a rota engole e o log mostra."""
    await _visita(servico, versao="1.3.0")
    voltas = modulo_repositorio.VOLTAS_DO_REGISTRO
    repo = RepositorioAparelho(
        _SessaoQueCruza(sessao, [f"1.3.{n}" for n in range(1, voltas + 1)])
    )

    with pytest.raises(ErroDoRegistroDoDia):
        await repo.registrar_dia(
            id_aparelho=str(APARELHO),
            dt_dia_local=date(2026, 10, 20),
            id_usuario=None,
            co_versao_app="1.4.0",
            co_idioma="pt",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5. Os detalhes do aparelho e o espaço ocupado
# ═══════════════════════════════════════════════════════════════════════════

DETALHES = {
    "no_fabricante": "samsung",
    "no_modelo": "SM-A065M",
    "co_abi": "arm64-v8a",
    "no_processador": "MT6769V/CZ",
    "qt_nucleos": 8,
    "nu_ram_mb": 3741,
    "nu_tela_largura_dp": 384,
    "nu_tela_altura_dp": 853,
    "nu_densidade_tela": None,
    "co_instancia_analytics": None,
}

#: 200 MB em KB: acima do limite do Android (150) e abaixo do do iOS (300).
#: ⚠️ Números diferentes nas duas plataformas, para provar que cada uma lê o seu.
DUZENTOS_MB_KB = 200 * 1024
DETALHE_DO_ESPACO = {"cache": 190000, "tmp": 0, "banco": 332, "pasta_nova": 5}


async def _detalhes(servico, *, plataforma="android", total_kb=DUZENTOS_MB_KB, detalhes=DETALHES):
    return await servico.registrar_detalhes(
        versao_app="1.4.0",
        plataforma=plataforma,
        idioma="es",
        cabecalhos=CabecalhosDoAparelho(id_aparelho=APARELHO, offset_minuto=-180),
        uid=None,
        agora=TARDE_UTC,
        detalhes=detalhes,
        versao_so="Android 14 (SDK 34)",
        espaco_app_kb=total_kb,
        espaco_app=DETALHE_DO_ESPACO,
        limites_mb=LIMITES,
    )


async def test_os_detalhes_vao_para_o_aparelho_e_o_sistema_para_o_dia(servico, sessao):
    await _detalhes(servico)

    aparelho = (await linhas(sessao, "SELECT * FROM log.vw003_aparelho"))[0]
    assert aparelho["no_modelo"] == "SM-A065M" and aparelho["qt_nucleos"] == 8
    assert aparelho["ic_legado"] == 0
    dia = (await _dias(sessao))[0]
    assert dia["co_versao_so"] == "Android 14 (SDK 34)"
    assert dia["co_idioma"] == "es" and dia["co_versao_app"] == "1.4.0"


async def test_acima_do_limite_da_plataforma_o_detalhe_e_guardado(servico, sessao):
    """200 MB no Android (limite 150): guardado, só com as pastas conhecidas."""
    _, guardou = await _detalhes(servico, plataforma="android")

    assert guardou
    dia = (await _dias(sessao))[0]
    assert dia["nu_espaco_app_kb"] == DUZENTOS_MB_KB
    assert json.loads(dia["js_espaco_app"]) == {"cache": 190000, "tmp": 0, "banco": 332}


async def test_abaixo_do_limite_da_plataforma_o_detalhe_vira_NULL(servico, sessao):
    """Os MESMOS 200 MB no iOS (limite 300): o total fica, o detalhe não."""
    _, guardou = await _detalhes(servico, plataforma="ios")

    assert not guardou
    dia = (await _dias(sessao))[0]
    assert dia["nu_espaco_app_kb"] == DUZENTOS_MB_KB
    assert dia["js_espaco_app"] is None


async def test_a_leitura_do_desafio_nao_apaga_o_que_os_detalhes_gravaram(servico, sessao):
    """A leitura do desafio não sabe do espaço nem do aparelho: ela vem depois e
    não pode zerar nada."""
    await _detalhes(servico)
    await _visita(servico, versao="1.4.0", offset=-180)

    dia = (await _dias(sessao))[0]
    assert dia["nu_espaco_app_kb"] == DUZENTOS_MB_KB and dia["js_espaco_app"] is not None
    assert dia["co_versao_so"] == "Android 14 (SDK 34)"
    assert (await linhas(sessao, "SELECT no_modelo FROM log.tb003_aparelho"))[0]["no_modelo"] == "SM-A065M"


async def test_os_detalhes_do_dia_seguinte_sobrescrevem_os_do_aparelho(servico, sessao):
    """O consentimento do Analytics recusado depois: o `appInstanceId` some, e
    não fica o antigo."""
    await _detalhes(servico, detalhes={**DETALHES, "co_instancia_analytics": "abc123"})
    await _detalhes(servico, detalhes=DETALHES)

    aparelho = (await linhas(sessao, "SELECT co_instancia_analytics FROM log.tb003_aparelho"))[0]
    assert aparelho["co_instancia_analytics"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 6. A exclusão de conta zera o "de quem", e a linha fica
# ═══════════════════════════════════════════════════════════════════════════


async def test_a_exclusao_de_conta_zera_o_id_usuario_do_dia(servico, sessao):
    """O dia fica (é amostra da adoção); some só a pessoa. E a de OUTRA pessoa
    não é tocada - sem o `WHERE`, a exclusão de uma conta anonimizaria todas."""
    await _visita(servico, uid=UID)
    await sessao.execute(
        text(
            "INSERT INTO log.tb004_aparelho_dia "
            "(id_aparelho, dt_dia_local, id_usuario, co_versao_app) "
            "VALUES (:a, '2026-10-21', :outra, '1.4.0')"
        ),
        {"a": str(APARELHO), "outra": OUTRA_PESSOA},
    )

    await RepositorioUsuario(sessao).remover_dados_vinculados(ID_USUARIO)

    dias = await _dias(sessao)
    assert [d["id_usuario"] for d in dias] == [None, OUTRA_PESSOA]
