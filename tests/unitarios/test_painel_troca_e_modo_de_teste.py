"""O PAINEL: inverter datas, esvaziar o calendario e o modo de teste (27/10/2026).

O que estes casos protegem, em uma frase cada:

  · **o modo de teste** so existe com a variavel ligada E fora de producao;
  · **inverter** troca dois desafios de dia com as travas valendo para OS DOIS
    (no modo de teste, so a janela baixada cai; o dia passado e o dia com
    tentativa, nunca);
  · **limpar** so existe no modo de teste, e nunca toca dia passado;
  · **descartar** no modo de teste ignora a janela baixada (pedido do dono,
    27/10/2026), e continua recusando o dia passado e o de hoje com tentativa;
  · **esvaziar** descarta (nao apaga) do primeiro dia destravado em diante,
    com confirmacao e motivo exigidos pelo SERVICO, e nao so pelo HTML;
  · **a pagina** espelha cada regra (o botao aparece onde o servico aceita).

⚠️ O SQL nao e executado aqui (ver `fakes_desafio.py`): quem o prova e o banco
`des`, no uso do painel.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Optional
from uuid import UUID, uuid4

import pytest

from api.configuracao import configuracoes
from api.desafios.painel import pagina
from api.desafios.painel.modo_de_teste import ENV_MODO_DE_TESTE, modo_de_teste_ligado
from api.desafios.painel.repositorio import VinculoDoDia
from api.desafios.painel.rotas import obter_servico
from api.desafios.painel.servico import ServicoCuradoria
from api.desafios.painel.vigilancia import ContagemDeAuditoria, EstadoDaFila
from api.main import app
from api.nucleo.excecoes import ErroNegocio
from tests.unitarios.test_painel_curadoria import SEGREDO, _desafio, cliente  # noqa: F401

HOJE = date(2026, 10, 27)
#: O fim da janela baixada nos dubles: hoje + 3 (`DIAS_DE_CACHE`).
FIM_DA_JANELA = HOJE + timedelta(days=3)


def _vinculo(
    dt_dia: date,
    *,
    tentativas: int = 0,
    curadoria: str = "aprovado",
) -> VinculoDoDia:
    return VinculoDoDia(
        id_desafio=uuid4(),
        id_desafio_dia=uuid4(),
        dt_dia=dt_dia,
        co_curadoria=curadoria,
        qt_tentativas=tentativas,
    )


class RepoDoCalendario:
    """Um repositorio em memoria com os vinculos do calendario.

    ⚠️ Anota cada escrita: varias regras daqui sao sobre o que NAO acontece
    (esvaziar sem confirmar nao descarta nada; limpar fora do modo de teste nao
    apaga nada).
    """

    def __init__(self, *vinculos: VinculoDoDia, troca_da_certo: bool = True) -> None:
        self.por_id = {v.id_desafio: v for v in vinculos}
        self.troca_da_certo = troca_da_certo
        self.trocas: list[tuple[UUID, UUID]] = []
        self.apagados: list[UUID] = []
        self.descartados: list[tuple[UUID, str]] = []
        self.desagendados: list[UUID] = []
        self.commits = 0
        self.desfeitos = 0

    async def vinculo_do_desafio(self, id_desafio: UUID) -> Optional[VinculoDoDia]:
        return self.por_id.get(id_desafio)

    async def vinculos(self, *, dt_de: date, dt_ate: Optional[date] = None):
        return sorted(
            (
                v
                for v in self.por_id.values()
                if v.dt_dia >= dt_de and (dt_ate is None or v.dt_dia <= dt_ate)
            ),
            key=lambda v: v.dt_dia,
        )

    async def situacao_no_calendario(self, id_desafio: UUID) -> Optional[tuple[date, int]]:
        """`(dia, tentativas)`, como o repositorio de verdade; e o que o descarte
        pergunta antes de recusar (dia jogado, janela baixada)."""
        vinculo = self.por_id.get(id_desafio)
        return None if vinculo is None else (vinculo.dt_dia, vinculo.qt_tentativas)

    async def fim_da_janela_baixada(self, dt_hoje: date) -> date:
        return dt_hoje + timedelta(days=3)

    async def inverter_dias(self, a: VinculoDoDia, b: VinculoDoDia) -> bool:
        self.trocas.append((a.id_desafio, b.id_desafio))
        if self.troca_da_certo:
            self.por_id[a.id_desafio] = replace(a, dt_dia=b.dt_dia)
            self.por_id[b.id_desafio] = replace(b, dt_dia=a.dt_dia)
        return self.troca_da_certo

    async def apagar_resolucoes(self, id_desafio_dia: UUID) -> dict[str, int]:
        self.apagados.append(id_desafio_dia)
        return {"resolucoes": 1, "xp": 2, "tentativas": 3, "impedidos": 0}

    async def descartar(self, id_desafio: UUID, *, de_motivo: str) -> bool:
        self.descartados.append((id_desafio, de_motivo))
        return True

    async def desagendar(self, id_desafio: UUID) -> bool:
        self.desagendados.append(id_desafio)
        return True

    async def confirmar(self) -> None:
        self.commits += 1

    async def desfazer(self) -> None:
        self.desfeitos += 1


# ═══════════════════════════════════════════════════════════════════════════
# 1. O modo de teste: as duas travas
# ═══════════════════════════════════════════════════════════════════════════


def test_sem_a_variavel_o_modo_de_teste_NAO_existe(monkeypatch) -> None:
    monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)
    assert not modo_de_teste_ligado()


def test_com_a_variavel_e_fora_de_producao_ele_existe(monkeypatch) -> None:
    monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
    monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")
    assert modo_de_teste_ligado()


def test_em_PRODUCAO_nem_a_variavel_o_liga(monkeypatch) -> None:
    """🔒 ⛔ A segunda trava: a variavel esquecida no servico `prd` nao basta."""
    monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
    monkeypatch.setattr(configuracoes, "AMBIENTE", "producao")
    assert not modo_de_teste_ligado()


@pytest.mark.parametrize("valor", ["0", "false", "False", " "])
def test_valores_que_NAO_ligam(monkeypatch, valor: str) -> None:
    monkeypatch.setenv(ENV_MODO_DE_TESTE, valor)
    monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")
    assert not modo_de_teste_ligado()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Inverter datas
# ═══════════════════════════════════════════════════════════════════════════

DEPOIS = HOJE + timedelta(days=10)
MAIS_DEPOIS = HOJE + timedelta(days=12)


@pytest.mark.asyncio
async def test_inverter_TROCA_os_dois_dias_e_confirma() -> None:
    """O caso do dono: adiantar um desafio do futuro sem perder o mais proximo."""
    a, b = _vinculo(MAIS_DEPOIS), _vinculo(DEPOIS)
    repo = RepoDoCalendario(a, b)
    resultado = await ServicoCuradoria(repo).inverter_dias(
        a.id_desafio, dt_destino=DEPOIS, dt_hoje=HOJE
    )
    assert repo.trocas == [(a.id_desafio, b.id_desafio)]
    assert repo.por_id[a.id_desafio].dt_dia == DEPOIS
    assert repo.por_id[b.id_desafio].dt_dia == MAIS_DEPOIS
    assert repo.commits == 1
    assert resultado.mudou


@pytest.mark.asyncio
@pytest.mark.parametrize("quem_esta_na_janela", ["origem", "destino"])
async def test_fora_do_modo_de_teste_a_JANELA_trava_os_DOIS(quem_esta_na_janela) -> None:
    """🔒 Os dois saem do seu dia: basta um estar nos aparelhos para recusar."""
    na_janela = HOJE + timedelta(days=2)
    a = _vinculo(na_janela if quem_esta_na_janela == "origem" else DEPOIS)
    b = _vinculo(DEPOIS if quem_esta_na_janela == "origem" else na_janela)
    repo = RepoDoCalendario(a, b)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(
            a.id_desafio, dt_destino=b.dt_dia, dt_hoje=HOJE
        )
    assert erro.value.codigo == "dia_ja_baixado"
    assert not repo.trocas and not repo.commits


@pytest.mark.asyncio
async def test_no_modo_de_teste_a_janela_NAO_trava() -> None:
    """O "Trazer para hoje": hoje esta sempre na janela."""
    hoje, futuro = _vinculo(HOJE), _vinculo(DEPOIS)
    repo = RepoDoCalendario(hoje, futuro)
    await ServicoCuradoria(repo).inverter_dias(
        futuro.id_desafio, dt_destino=HOJE, dt_hoje=HOJE, modo_de_teste=True
    )
    assert repo.por_id[futuro.id_desafio].dt_dia == HOJE
    assert repo.por_id[hoje.id_desafio].dt_dia == DEPOIS


@pytest.mark.asyncio
@pytest.mark.parametrize("modo_de_teste", [False, True])
async def test_dia_com_TENTATIVA_nao_sai_nem_no_modo_de_teste(modo_de_teste) -> None:
    """⛔ As tentativas mudariam de data junto. No `des`, limpa-se antes."""
    hoje = _vinculo(HOJE, tentativas=2)
    futuro = _vinculo(DEPOIS)
    repo = RepoDoCalendario(hoje, futuro)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(
            futuro.id_desafio,
            dt_destino=HOJE,
            dt_hoje=HOJE,
            modo_de_teste=modo_de_teste,
        )
    assert erro.value.codigo == "dia_ja_jogado"
    # O modo de teste diz o que fazer; fora dele, nao ha o que fazer.
    assert ("Limpe" in erro.value.detalhe) is modo_de_teste
    assert not repo.trocas


@pytest.mark.asyncio
async def test_dia_PASSADO_nunca_sai() -> None:
    passado = _vinculo(HOJE - timedelta(days=1))
    futuro = _vinculo(DEPOIS)
    repo = RepoDoCalendario(passado, futuro)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(
            passado.id_desafio, dt_destino=DEPOIS, dt_hoje=HOJE, modo_de_teste=True
        )
    assert erro.value.codigo == "dia_ja_jogado"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("destino", "codigo"),
    [
        (HOJE - timedelta(days=2), "dia_no_passado"),
        (HOJE + timedelta(days=40), "dia_longe_demais"),
        (HOJE + timedelta(days=11), "dia_vazio"),
        (DEPOIS, "mesmo_dia"),
    ],
)
async def test_destinos_recusados(destino, codigo) -> None:
    a = _vinculo(DEPOIS)
    repo = RepoDoCalendario(a, _vinculo(MAIS_DEPOIS))
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(
            a.id_desafio, dt_destino=destino, dt_hoje=HOJE
        )
    assert erro.value.codigo == codigo
    assert not repo.trocas


@pytest.mark.asyncio
async def test_desafio_SEM_dia_vai_para_o_agendar() -> None:
    repo = RepoDoCalendario(_vinculo(DEPOIS))
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(uuid4(), dt_destino=DEPOIS, dt_hoje=HOJE)
    assert erro.value.codigo == "desafio_sem_dia"


@pytest.mark.asyncio
async def test_o_outro_precisa_estar_APROVADO() -> None:
    a = _vinculo(MAIS_DEPOIS)
    b = _vinculo(DEPOIS, curadoria="descartado")
    repo = RepoDoCalendario(a, b)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(a.id_desafio, dt_destino=DEPOIS, dt_hoje=HOJE)
    assert erro.value.codigo == "desafio_nao_aprovado"


@pytest.mark.asyncio
async def test_troca_que_PARA_NO_MEIO_e_desfeita() -> None:
    """🔒 Outra aba mexeu num dos dois: os passos que deram certo nao ficam."""
    a, b = _vinculo(MAIS_DEPOIS), _vinculo(DEPOIS)
    repo = RepoDoCalendario(a, b, troca_da_certo=False)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).inverter_dias(a.id_desafio, dt_destino=DEPOIS, dt_hoje=HOJE)
    assert erro.value.codigo == "troca_interrompida"
    assert repo.desfeitos == 1 and repo.commits == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Limpar resolucoes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_limpar_FORA_do_modo_de_teste_e_recusado_sem_apagar_nada() -> None:
    hoje = _vinculo(HOJE, tentativas=1)
    repo = RepoDoCalendario(hoje)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).limpar_resolucoes(
            hoje.id_desafio, dt_hoje=HOJE, modo_de_teste=False
        )
    assert erro.value.codigo == "modo_de_teste_desligado"
    assert not repo.apagados and not repo.commits


@pytest.mark.asyncio
async def test_limpar_apaga_o_DIA_do_desafio_e_confirma() -> None:
    hoje = _vinculo(HOJE, tentativas=3)
    repo = RepoDoCalendario(hoje)
    resultado = await ServicoCuradoria(repo).limpar_resolucoes(
        hoje.id_desafio, dt_hoje=HOJE, modo_de_teste=True
    )
    assert repo.apagados == [hoje.id_desafio_dia]
    assert repo.commits == 1
    assert "3 tentativa(s)" in resultado.mensagem
    assert "XP ja somado" in resultado.mensagem


@pytest.mark.asyncio
async def test_limpar_dia_PASSADO_e_recusado_mesmo_no_modo_de_teste() -> None:
    passado = _vinculo(HOJE - timedelta(days=1), tentativas=5)
    repo = RepoDoCalendario(passado)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).limpar_resolucoes(
            passado.id_desafio, dt_hoje=HOJE, modo_de_teste=True
        )
    assert erro.value.codigo == "dia_ja_jogado"
    assert not repo.apagados


# ═══════════════════════════════════════════════════════════════════════════
# 4. Esvaziar
# ═══════════════════════════════════════════════════════════════════════════


def _calendario_cheio() -> list[VinculoDoDia]:
    """Hoje (jogado), dois dias na janela e tres depois dela."""
    return [
        _vinculo(HOJE, tentativas=2),
        _vinculo(HOJE + timedelta(days=1)),
        _vinculo(FIM_DA_JANELA),
        _vinculo(FIM_DA_JANELA + timedelta(days=1)),
        _vinculo(FIM_DA_JANELA + timedelta(days=2), curadoria="descartado"),
        _vinculo(FIM_DA_JANELA + timedelta(days=5)),
    ]


@pytest.mark.asyncio
async def test_esvaziar_SEM_confirmar_nao_toca_em_nada() -> None:
    """🔒 A caixa "entendi" e regra do servico: um `curl` passa pelo HTML."""
    repo = RepoDoCalendario(*_calendario_cheio())
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).esvaziar(dt_hoje=HOJE, motivo="x", confirmado=False)
    assert erro.value.codigo == "sem_confirmacao"
    assert not repo.descartados and not repo.desagendados


@pytest.mark.asyncio
async def test_esvaziar_SEM_motivo_e_recusado() -> None:
    repo = RepoDoCalendario(*_calendario_cheio())
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).esvaziar(dt_hoje=HOJE, motivo="  ", confirmado=True)
    assert erro.value.codigo == "motivo_ausente"


@pytest.mark.asyncio
async def test_esvaziar_no_PRD_comeca_DEPOIS_da_janela_e_nao_apaga_nada() -> None:
    calendario = _calendario_cheio()
    repo = RepoDoCalendario(*calendario)
    resultado = await ServicoCuradoria(repo).esvaziar(
        dt_hoje=HOJE, motivo="trocar a safra", confirmado=True
    )
    depois = calendario[3:]
    assert repo.desagendados == [v.id_desafio for v in depois]
    # O que ja estava descartado so sai do dia: o motivo antigo fica.
    assert repo.descartados == [
        (v.id_desafio, "trocar a safra") for v in depois if v.co_curadoria != "descartado"
    ]
    assert not repo.apagados  # ⛔ nada apagado fora do modo de teste
    assert repo.commits == 1
    assert "3 desafio(s)" in resultado.mensagem


@pytest.mark.asyncio
async def test_esvaziar_no_modo_de_teste_comeca_HOJE_e_limpa_antes() -> None:
    calendario = _calendario_cheio()
    repo = RepoDoCalendario(*calendario)
    await ServicoCuradoria(repo).esvaziar(
        dt_hoje=HOJE, motivo="teste", confirmado=True, modo_de_teste=True
    )
    assert repo.desagendados == [v.id_desafio for v in calendario]
    assert repo.apagados == [v.id_desafio_dia for v in calendario]


@pytest.mark.asyncio
async def test_esvaziar_NAO_toca_dia_passado() -> None:
    passado = _vinculo(HOJE - timedelta(days=1), tentativas=4)
    repo = RepoDoCalendario(passado)
    resultado = await ServicoCuradoria(repo).esvaziar(
        dt_hoje=HOJE, motivo="teste", confirmado=True, modo_de_teste=True
    )
    assert not repo.desagendados and not repo.apagados
    assert not resultado.mudou


@pytest.mark.asyncio
async def test_tentativa_DEPOIS_da_janela_para_tudo_antes_de_escrever() -> None:
    estranho = _vinculo(FIM_DA_JANELA + timedelta(days=2), tentativas=1)
    repo = RepoDoCalendario(_vinculo(FIM_DA_JANELA + timedelta(days=1)), estranho)
    with pytest.raises(ErroNegocio):
        await ServicoCuradoria(repo).esvaziar(dt_hoje=HOJE, motivo="x", confirmado=True)
    assert not repo.descartados and not repo.desagendados


# ═══════════════════════════════════════════════════════════════════════════
# 4b. Descartar no modo de teste (27/10/2026)
# ═══════════════════════════════════════════════════════════════════════════

#: Um dia DENTRO da janela baixada (hoje + 2), e por isso travado no `prd`.
NA_JANELA = HOJE + timedelta(days=2)


@pytest.mark.asyncio
async def test_descartar_na_JANELA_fora_do_modo_de_teste_e_recusado() -> None:
    """🔒 A trava de producao: o dia pode estar num aparelho."""
    alvo = _vinculo(NA_JANELA)
    repo = RepoDoCalendario(alvo)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).descartar(
            alvo.id_desafio, motivo="nao parece virada", dt_hoje=HOJE
        )
    assert erro.value.codigo == "dia_ja_baixado"
    assert not repo.descartados and not repo.desagendados and not repo.commits


@pytest.mark.asyncio
async def test_descartar_na_JANELA_no_modo_de_teste_descarta_e_tira_do_dia() -> None:
    """O pedido do dono: as viradas antigas do `des` estavam nos proximos dias."""
    alvo = _vinculo(NA_JANELA)
    repo = RepoDoCalendario(alvo)
    resultado = await ServicoCuradoria(repo).descartar(
        alvo.id_desafio, motivo="nao parece virada", dt_hoje=HOJE, modo_de_teste=True
    )
    assert repo.descartados == [(alvo.id_desafio, "nao parece virada")]
    assert repo.desagendados == [alvo.id_desafio]
    assert repo.commits == 1
    assert resultado.mudou


@pytest.mark.asyncio
async def test_descartar_HOJE_com_tentativa_no_modo_de_teste_manda_limpar_antes() -> None:
    """⛔ As tentativas apontam para o dia: o modo de teste diz o conserto."""
    alvo = _vinculo(HOJE, tentativas=1)
    repo = RepoDoCalendario(alvo)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).descartar(
            alvo.id_desafio, motivo="x", dt_hoje=HOJE, modo_de_teste=True
        )
    assert erro.value.codigo == "dia_ja_jogado"
    assert "Limpe as resolucoes" in erro.value.detalhe
    assert not repo.descartados


@pytest.mark.asyncio
async def test_descartar_dia_PASSADO_e_recusado_mesmo_no_modo_de_teste() -> None:
    alvo = _vinculo(HOJE - timedelta(days=1))
    repo = RepoDoCalendario(alvo)
    with pytest.raises(ErroNegocio) as erro:
        await ServicoCuradoria(repo).descartar(
            alvo.id_desafio, motivo="x", dt_hoje=HOJE, modo_de_teste=True
        )
    assert erro.value.codigo == "dia_ja_jogado"
    assert not repo.descartados


# ═══════════════════════════════════════════════════════════════════════════
# 5. A pagina espelha as regras
# ═══════════════════════════════════════════════════════════════════════════


def _detalhe(item) -> str:
    return pagina.render_detalhe(
        pagina.DetalheDoDia(dt_dia=item.dt_dia, desafio=item),
        dt_hoje=HOJE,
        dt_sugerida=HOJE,
        dt_fim_janela_baixada=FIM_DA_JANELA,
    )


def _pagina_inteira(calendario=()) -> str:
    return pagina.render(
        dt_hoje=HOJE,
        dt_fim_janela_baixada=FIM_DA_JANELA,
        detalhe=pagina.DetalheDoDia(dt_dia=HOJE, desafio=None),
        calendario=calendario,
        estado_da_fila=EstadoDaFila(dias_cobertos=7, reserva=0, buracos=()),
        contagem=ContagemDeAuditoria(),
        divergencias=(),
    )


@pytest.fixture
def sem_modo_de_teste(monkeypatch):
    monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)


@pytest.fixture
def com_modo_de_teste(monkeypatch):
    monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
    monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")


def test_fora_do_teste_o_desafio_destravado_oferece_INVERTER(sem_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=DEPOIS))
    assert f"{pagina.BASE}/inverter" in html
    assert "limpar-resolucoes" not in html
    assert "Trazer para hoje" not in html


def test_fora_do_teste_o_dia_na_janela_NAO_oferece_inverter(sem_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=HOJE + timedelta(days=1)))
    assert "/inverter" not in html


def test_no_teste_o_futuro_oferece_LIMPAR_e_TRAZER_PARA_HOJE(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=HOJE + timedelta(days=1)))
    assert f"{pagina.BASE}/limpar-resolucoes" in html
    assert "Trazer para hoje" in html
    assert f'value="{HOJE.isoformat()}"' in html
    # Uma troca de datas so, a da caixa de teste.
    assert html.count(f"{pagina.BASE}/inverter") == 2  # trazer + inverter


def test_no_teste_HOJE_oferece_limpar_mas_nao_trazer(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=HOJE))
    assert "limpar-resolucoes" in html
    assert "Trazer para hoje" not in html


def test_no_teste_o_dia_PASSADO_nao_ganha_caixa(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=HOJE - timedelta(days=1)))
    assert "limpar-resolucoes" not in html
    assert "/inverter" not in html


def test_fora_do_teste_o_dia_na_janela_NAO_oferece_descartar(sem_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=NA_JANELA))
    assert f"{pagina.BASE}/descartar" not in html
    assert "nao se descarta" in html


def test_no_teste_o_dia_na_janela_oferece_DESCARTAR(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="aprovado", dt_dia=NA_JANELA))
    assert html.count(f"{pagina.BASE}/descartar") == 1
    assert "o descarte fica liberado aqui" in html
    # So o descarte: trocar a data e tirar do calendario continuam travados.
    assert f"{pagina.BASE}/agendar" not in html
    assert f"{pagina.BASE}/desagendar" not in html


def test_no_teste_o_CANDIDATO_na_janela_oferece_aprovar_E_descartar(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="candidato", dt_dia=NA_JANELA))
    assert f"{pagina.BASE}/aprovar" in html
    assert f"{pagina.BASE}/descartar" in html


def test_no_teste_o_JA_DESCARTADO_nao_oferece_descartar_de_novo(com_modo_de_teste) -> None:
    html = _detalhe(_desafio(co_curadoria="descartado", dt_dia=NA_JANELA))
    assert f"{pagina.BASE}/descartar" not in html


def test_a_faixa_do_MODO_DE_TESTE_so_aparece_nele(monkeypatch) -> None:
    monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)
    assert "MODO DE TESTE" not in _pagina_inteira()
    monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
    monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")
    assert "MODO DE TESTE" in _pagina_inteira()


def test_esvaziar_mostra_o_PRIMEIRO_dia_que_ele_toca(monkeypatch) -> None:
    monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)
    html = _pagina_inteira()
    assert f"{pagina.BASE}/esvaziar" in html
    assert f"de {(FIM_DA_JANELA + timedelta(days=1)).strftime('%d/%m/%Y')} em diante" in html
    monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
    monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")
    assert f"de {HOJE.strftime('%d/%m/%Y')} em diante" in _pagina_inteira()


# ═══════════════════════════════════════════════════════════════════════════
# 6. As rotas
# ═══════════════════════════════════════════════════════════════════════════

CABECALHOS = {
    "X-Admin-Token": SEGREDO,
    "Content-Type": "application/x-www-form-urlencoded",
}


def test_inverter_volta_para_o_dia_de_DESTINO(cliente, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr("api.desafios.painel.rotas.hoje_utc", lambda: HOJE)
    a, b = _vinculo(MAIS_DEPOIS), _vinculo(DEPOIS)
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(
        RepoDoCalendario(a, b)
    )
    resposta = cliente.post(
        "/painel/desafios/inverter",
        headers=CABECALHOS,
        content=f"id_desafio={a.id_desafio}&dt_dia={DEPOIS.isoformat()}",
    )
    assert resposta.status_code == 303
    assert f"dia={DEPOIS.isoformat()}" in resposta.headers["location"]
    assert "erro=1" not in resposta.headers["location"]


@pytest.mark.parametrize("modo_de_teste", [False, True])
def test_a_rota_de_descartar_passa_o_MODO_DE_TESTE(
    cliente, monkeypatch, modo_de_teste  # noqa: F811
) -> None:
    """Sem o argumento na rota, o servico ficaria com a trava de producao no `des`."""
    monkeypatch.setattr("api.desafios.painel.rotas.hoje_utc", lambda: HOJE)
    if modo_de_teste:
        monkeypatch.setenv(ENV_MODO_DE_TESTE, "1")
        monkeypatch.setattr(configuracoes, "AMBIENTE", "desenvolvimento")
    else:
        monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)
    alvo = _vinculo(NA_JANELA)
    repo = RepoDoCalendario(alvo)
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(repo)
    resposta = cliente.post(
        "/painel/desafios/descartar",
        headers=CABECALHOS,
        content=f"id_desafio={alvo.id_desafio}&motivo=teste",
    )
    assert resposta.status_code == 303
    assert ("erro=1" in resposta.headers["location"]) is not modo_de_teste
    assert bool(repo.descartados) is modo_de_teste


def test_limpar_sem_modo_de_teste_volta_com_ERRO(cliente, monkeypatch) -> None:  # noqa: F811
    monkeypatch.delenv(ENV_MODO_DE_TESTE, raising=False)
    hoje = _vinculo(HOJE, tentativas=1)
    repo = RepoDoCalendario(hoje)
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(repo)
    resposta = cliente.post(
        "/painel/desafios/limpar-resolucoes",
        headers=CABECALHOS,
        content=f"id_desafio={hoje.id_desafio}",
    )
    assert resposta.status_code == 303
    assert "erro=1" in resposta.headers["location"]
    assert not repo.apagados


def test_esvaziar_sem_a_CAIXA_marcada_volta_com_ERRO(cliente) -> None:  # noqa: F811
    repo = RepoDoCalendario(*_calendario_cheio())
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(repo)
    resposta = cliente.post(
        "/painel/desafios/esvaziar",
        headers=CABECALHOS,
        content="motivo=limpeza",
    )
    assert "erro=1" in resposta.headers["location"]
    assert not repo.desagendados


def test_esvaziar_com_a_caixa_marcada_descarta(cliente) -> None:  # noqa: F811
    repo = RepoDoCalendario(*_calendario_cheio())
    app.dependency_overrides[obter_servico] = lambda: ServicoCuradoria(repo)
    resposta = cliente.post(
        "/painel/desafios/esvaziar",
        headers=CABECALHOS,
        content="motivo=limpeza&confirmo=1",
    )
    assert "erro=1" not in resposta.headers["location"]
    assert repo.desagendados
