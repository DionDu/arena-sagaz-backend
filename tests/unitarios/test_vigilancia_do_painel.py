"""AS DUAS SECOES DE VIGILANCIA — T040 (RF-DES-012f, RF-DES-034a).

As duas existem porque **o backend nao tem canal de alerta**: o SDK de telemetria
saiu de escopo em 02/09/2026, e sem um lugar que o dono ja abre por outro motivo
"alerta" vira linha de log que ninguem le.

O que estes casos protegem:

  · **o aviso chega ANTES de a fila acabar**, e nao quando acabou — e o texto
    literal de RF-DES-012f, e a diferenca entre um aviso util e um obituario;
  · **so aprovado cobre um dia**: um candidato agendado ocupa a data e nao e
    servido, e contar essa data como coberta esconderia um dia em branco;
  · **cobertura e de dias CONSECUTIVOS**: um calendario com hoje e o dia 20
    preenchidos tem um dia de folga, e nao dois;
  · **`divergente = 0` sozinho nao quer dizer nada** — sem o avaliador (T043a)
    rodando, ele significa "ninguem conferiu", e o contador de pendentes e o que
    separa as duas leituras.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from api.desafios.painel.vigilancia import (
    DIAS_DE_FOLGA_CONFORTAVEL,
    ContagemDeAuditoria,
    Divergencia,
    EstadoDaFila,
    Vigilancia,
)
from tests.unitarios.fakes_desafio import FakeSessaoSQL

HOJE = date(2026, 9, 10)


def _dias(cobertos: int, *, curadoria: str = "aprovado") -> list[dict]:
    """`cobertos` dias seguidos a partir de hoje, todos com dono."""
    return [
        {
            "dt_dia": HOJE + timedelta(days=n),
            "id_desafio": uuid4(),
            "co_curadoria": curadoria,
            "co_jogo": "damas",
            "ic_reprise": False,
        }
        for n in range(cobertos)
    ]


def _sessao(dias: list[dict], *, reserva: int = 0, auditoria=(), divergencias=()):
    """Uma sessao falsa com as tres consultas da vigilancia preparadas."""
    return FakeSessaoSQL(
        respostas={
            # Trechos unicos: as duas contagens tem `COUNT(*) AS qt`.
            "GROUP BY co_auditoria": list(auditoria),
            "dia.id_desafio IS NULL": [{"qt": reserva}],
            "co_auditoria = 'divergente'": list(divergencias),
            "ORDER BY dia.dt_dia": dias,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. O aviso de fila curta (RF-DES-012f)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fila_com_a_folga_do_job_nao_reclama():
    """⚠️ O limiar e o `DIAS_MINIMOS` do job (7), e nao um numero de tela.

    Se os dois divergissem, o painel chamaria de confortavel uma fila que o job
    considera curta — e um dos dois estaria mentindo.
    """
    estado = await Vigilancia(_sessao(_dias(7))).estado_da_fila(dt_hoje=HOJE)

    assert estado.dias_cobertos == DIAS_DE_FOLGA_CONFORTAVEL == 7
    assert estado.gravidade == "ok"
    assert estado.precisa_avisar is False


@pytest.mark.asyncio
async def test_avisa_ANTES_de_a_fila_acabar():
    """⛔ O ponto inteiro de RF-DES-012f.

    Com 5 dias ainda cobertos nao falta desafio hoje nem amanha — e e **agora**
    que da tempo de agir. Um aviso que so acende no dia em que a fila zera chega
    quando ja nao ha o que fazer.
    """
    estado = await Vigilancia(_sessao(_dias(5))).estado_da_fila(dt_hoje=HOJE)

    assert estado.dias_cobertos == 5
    assert estado.precisa_avisar is True
    assert estado.gravidade == "atencao"


@pytest.mark.asyncio
async def test_fila_quase_vazia_e_critica():
    """Tres dias ou menos: uma falha do job vira dia sem produto."""
    estado = await Vigilancia(_sessao(_dias(2))).estado_da_fila(dt_hoje=HOJE)
    assert estado.gravidade == "critico"


@pytest.mark.asyncio
async def test_fila_vazia_e_critica_e_nomeia_os_buracos():
    """⚠️ Nomear os dias descobertos e o que torna o aviso acionavel.

    "A fila esta curta" nao diz o que fazer; "os dias 10, 11 e 12 estao sem dono"
    diz.
    """
    estado = await Vigilancia(_sessao([])).estado_da_fila(dt_hoje=HOJE)

    assert estado.dias_cobertos == 0
    assert estado.gravidade == "critico"
    assert len(estado.buracos) == DIAS_DE_FOLGA_CONFORTAVEL
    assert estado.buracos[0] == HOJE


@pytest.mark.asyncio
async def test_candidato_agendado_NAO_conta_como_dia_coberto():
    """⛔ A armadilha silenciosa: o dia esta ocupado e nada e servido.

    `un001_dia` impede outro desafio de entrar naquela data, e a rota so serve
    `aprovado` — entao o aplicativo abriria com o dia em branco. Contar essa data
    como coberta faria o painel jurar que esta tudo bem.
    """
    estado = await Vigilancia(
        _sessao(_dias(7, curadoria="candidato"))
    ).estado_da_fila(dt_hoje=HOJE)

    assert estado.dias_cobertos == 0
    assert estado.gravidade == "critico"


@pytest.mark.asyncio
async def test_a_cobertura_conta_dias_CONSECUTIVOS():
    """Hoje e o dia 20 preenchidos = **um** dia de folga, e nao dois.

    ⚠️ E a sequencia sem buraco que diz quando o aplicativo abre vazio pela
    primeira vez. Somar dias soltos daria um numero maior e uma promessa falsa.
    """
    dias = _dias(1) + [
        {
            "dt_dia": HOJE + timedelta(days=10),
            "id_desafio": uuid4(),
            "co_curadoria": "aprovado",
            "co_jogo": "damas",
            "ic_reprise": False,
        }
    ]
    estado = await Vigilancia(_sessao(dias)).estado_da_fila(dt_hoje=HOJE)

    assert estado.dias_cobertos == 1
    assert HOJE + timedelta(days=1) in estado.buracos


@pytest.mark.asyncio
async def test_a_reserva_de_aprovados_sem_data_entra_no_aviso():
    """⚠️ Calendario cheio com reserva zerada esta a um dia de acabar.

    Sao dois numeros diferentes, e so os dois juntos dizem se ha do que publicar.
    """
    estado = await Vigilancia(_sessao(_dias(3), reserva=9)).estado_da_fila(
        dt_hoje=HOJE
    )
    assert estado.reserva == 9


# ═══════════════════════════════════════════════════════════════════════════
# 2. As divergencias de julgamento (RF-DES-034a)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_os_tres_contadores_vem_juntos():
    """⚠️ `divergente = 0` sozinho significa duas coisas opostas.

    "Conferimos tudo e esta certo" e "ninguem conferiu nada" pedem acoes
    opostas, e e o contador de pendentes que as separa.
    """
    contagem = await Vigilancia(
        _sessao(
            [],
            auditoria=[
                {"co_auditoria": "pendente", "qt": 12},
                {"co_auditoria": "confere", "qt": 40},
                {"co_auditoria": "divergente", "qt": 2},
            ],
        )
    ).contagem_de_auditoria()

    assert (contagem.pendente, contagem.confere, contagem.divergente) == (12, 40, 2)
    assert contagem.total == 54
    assert contagem.avaliador_nunca_rodou is False


def test_so_pendentes_significa_que_o_avaliador_nao_rodou():
    """⚠️ Sem T043a, `co_auditoria` fica em `'pendente'` para sempre.

    A coluna tem `DEFAULT`, entao **nada da erro** — e esta e a unica coisa no
    sistema que denuncia a auditoria parada.
    """
    assert ContagemDeAuditoria(pendente=30).avaliador_nunca_rodou is True


def test_sem_resolucao_nenhuma_nao_e_avaliador_parado():
    """Banco novo nao e auditoria quebrada — nao ha o que conferir ainda."""
    assert ContagemDeAuditoria().avaliador_nunca_rodou is False


@pytest.mark.asyncio
async def test_as_divergencias_chegam_com_o_contexto_para_investigar():
    """⛔ Divergencia nao corrige nada (RF-DES-032, D-05): vale o aplicativo.

    A linha existe para ser **investigada**, e por isso carrega o dia, o jogo, o
    tipo e o que o arbitro achou — sem isso o alerta seria um numero sem alca.
    """
    linhas = await Vigilancia(
        _sessao(
            [],
            divergencias=[
                {
                    "id_resolucao": uuid4(),
                    "dt_dia": HOJE,
                    "co_jogo": "damas",
                    "co_tipo_desafio": "damas_sacrificio",
                    "nu_xp": 26,
                    "de_auditoria": "lance 7 ilegal para o arbitro",
                    "dh_resolucao": datetime(2026, 9, 10, 14, tzinfo=timezone.utc),
                }
            ],
        )
    ).divergencias()

    assert len(linhas) == 1
    assert isinstance(linhas[0], Divergencia)
    assert linhas[0].de_auditoria == "lance 7 ilegal para o arbitro"
    assert linhas[0].nu_xp == 26  # ⛔ o XP dela NAO foi mexido


@pytest.mark.asyncio
async def test_a_secao_de_divergencias_abre_vazia_sem_erro():
    """⚠️ Ela nasce vazia enquanto T043a nao existir — e isso nao e defeito."""
    assert await Vigilancia(_sessao([])).divergencias() == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. As duas secoes na MESMA visita (RF-DES-012f)
# ═══════════════════════════════════════════════════════════════════════════


def test_gravidade_escolhe_a_cor_e_nao_o_contrario():
    """A tela le `gravidade`; ela nao decide sozinha o que e grave."""
    assert EstadoDaFila(9, 0, ()).gravidade == "ok"
    assert EstadoDaFila(5, 0, ()).gravidade == "atencao"
    assert EstadoDaFila(3, 0, ()).gravidade == "critico"
    assert EstadoDaFila(0, 0, ()).gravidade == "critico"


@pytest.mark.asyncio
async def test_a_pagina_traz_as_duas_secoes_juntas():
    """⚠️ Na MESMA visita em que os candidatos sao aprovados (RF-DES-012f).

    Duas paginas separadas exigiriam do dono lembrar de abrir a segunda — e
    lembrar e exatamente o que um painel existe para dispensar.
    """
    from api.desafios.painel import pagina

    html = pagina.render(
        fila=[],
        estado_da_fila=await Vigilancia(_sessao(_dias(2))).estado_da_fila(
            dt_hoje=HOJE
        ),
        contagem=ContagemDeAuditoria(pendente=5),
        divergencias=[],
        dt_hoje=HOJE,
    )

    assert "Vigilancia &mdash; a fila" in html
    assert "Vigilancia &mdash; divergencias de julgamento" in html
    assert "FILA CRITICA" in html
    assert "O avaliador de resolucoes nao rodou ainda" in html
