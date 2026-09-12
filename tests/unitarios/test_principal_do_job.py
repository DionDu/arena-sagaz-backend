"""T049c - o `principal()`: o ENCADEAMENTO que faz o job rodar.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUE ESTE ARQUIVO MEDE
═══════════════════════════════════════════════════════════════════════════

A **ordem** dos passos e as **decisoes** entre eles: o perfil antes de tudo, o
dia descoberto virando codigo de saida 1, o estouro de um dia nao derrubando os
outros, a reprise entrando quando a geracao nao acha candidato.

⛔ **Nada aqui roda motor.** A geracao e a bancada de medicao entram por
parametro, e o duble de banco nunca executa SQL. Com a bancada de verdade, medir
a regua roda a CNN do Pontinhos **tres vezes por execucao** — o teste do
encadeamento nao pode custar isso, e quem prova que a bancada real funciona e a
T034, com geracao de verdade e `scope="module"`.

⚠️ **E o portao T050 e quem prova o conjunto**, no `des`, com banco de verdade.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from job import __main__ as principal_mod
from job.alvo_observado import PISO_FIXO, TETO_FIXO, Alvo
from job.editorial import (
    EDITORIAL,
    TipoSemEditorial,
    parametros_para_conferencia,
    publicacao_de,
    variantes_de,
)
from job import posicao_inicial as posicao_mod
from job.gerador import Candidato, escolher_jogo, escolher_tipo
from job.gravacao import DIAS_MINIMOS
from job.regua import Medicao
from job.medidas_de_saida import conferir
from job.tipos_de_desafio import RECEITAS, receita_de
from tests.unitarios.fakes_desafio import FakeSessaoSQL


# ═══════════════════════════════════════════════════════════════════════════
# Os dubles
# ═══════════════════════════════════════════════════════════════════════════


class _Julgamento:
    """O que o juiz devolve, na parte que a regua e o gerador leem."""

    def __init__(self, cumpriu: bool = True) -> None:
        self.cumpriu = cumpriu
        self.nu_lance_cumpre_desafio = 1 if cumpriu else None


class _Veredito:
    """O que o arbitro devolve. `acabou=True` fecha a prova de termino no ato."""

    def __init__(self, acabou: bool = True) -> None:
        self.acabou = acabou
        self.co_motivo = "vitoria_j1" if acabou else None


class _EstadoFalso:
    """Uma posicao falsa, com o unico campo que a regua le.

    ⚠️ `vez_de` existe porque a regua monta a fita com ele — e a fita e o que o
    juiz recebe. Um `object()` cru estourava com `AttributeError` no meio da
    medicao, e o laco de `executar` engolia isso como "dia descoberto": o teste
    passava a medir o tratamento de erro em vez do encadeamento.
    """

    vez_de = 1

    def com_lance(self, lance: str) -> "_EstadoFalso":
        """Nada muda: quem aplica de verdade e o motor, e ele nao esta aqui."""
        return self


class _JogadorFalso:
    """Escolhe sempre o mesmo lance e aplica sem regra nenhuma.

    ⚠️ **Nao imita o motor**, e isso e deliberado: um duble fiel esconderia,
    atras da propria fidelidade, o fato de que nada aqui joga de verdade.
    """

    def escolher_lance(self, estado: Any, nivel: Any, **_: Any) -> str:
        return "H_0_0"

    def aplicar(self, estado: Any, lance: str) -> Any:
        return estado

    def veredito(self, estado: Any) -> _Veredito:
        return _Veredito(acabou=True)


class _Bancada:
    """As pecas de medicao, todas falsas."""

    def __init__(self, cumpre: bool = True, acaba: bool = True) -> None:
        motor = _JogadorFalso()
        self.jogador = motor
        self.arbitro = motor
        self.estado_inicial = _EstadoFalso()
        self._cumpre = cumpre
        if not acaba:
            self.arbitro = type(
                "ArbitroSemFim", (), {"veredito": lambda _s, _e: _Veredito(False)}
            )()

    def julgar(self, fita: list[dict[str, Any]]) -> _Julgamento:
        return _Julgamento(self._cumpre)


def _candidato(
    co_tipo: str = "pontinhos_fechar_caixas",
    parametros_pedidos: Any = None,
) -> Candidato:
    """Um candidato pronto, sem ter passado por motor nenhum.

    Args:
        parametros_pedidos: os parametros que o job pediu. ⚠️ **Quando vierem, sao
            eles que valem** — o `principal()` monta as medidas de saida com os
            parametros do CANDIDATO, entao um duble que devolvesse sempre os da
            primeira variante publicaria medidas de um tipo no dia de outro.
    """
    receita = receita_de(co_tipo)
    # ⚠️ **A primeira variante basta AQUI**, e so aqui: este e um candidato de
    # laboratorio, e o que se exercita e o encadeamento. Quem prova que a
    # variante do dia e escolhida direito sao os casos da secao 8.
    publicacao = variantes_de(co_tipo)[0]
    if parametros_pedidos is not None:
        publicacao = type(publicacao)(
            parametros=parametros_pedidos,
            ic_chegada_encerra_partida=publicacao.ic_chegada_encerra_partida,
            medidas=publicacao.medidas,
        )
    # ⚠️ **Passa pela traducao do editorial**, e nao usa os parametros crus: numa
    # variante cujo alvo sai da posicao (`acima_do_guloso`) os numeros do
    # editorial nem tem a chave que a receita le.
    parametros = parametros_para_conferencia(publicacao.parametros)
    return Candidato(
        co_jogo=receita.co_jogo,
        co_variante="pequeno",
        co_modalidade=None,
        co_formato_posicao="sequencia_lances",
        # ⚠️ **Montada pelo proprio produtor**, e nao escrita a mao: o
        # `principal()` chama `posicao_inicial.conferir` antes de gravar, e um
        # JSON de teste escrito a mao testaria o conferidor em vez do
        # encadeamento — foi o que aconteceu na primeira versao deste arquivo,
        # com o placar em `{"1": ...}` onde o formato usa `{"j1": ...}`.
        js_posicao_inicial=posicao_mod.do_pontinhos([]),
        receita=receita,
        js_chegada=receita.montar(parametros),
        js_objetivo=receita.valores_da_frase(parametros, "pita"),
        co_personagem="pita",
        nu_semente=2087461933,
        js_solucao={"versao": 1, "origem": "busca_sagaz", "lances": [], "lance_chave": 1},
        nu_lances_solucao=5,
        parametros=parametros,
        estado_inicial=_EstadoFalso(),
    )


def _sessao_feliz() -> FakeSessaoSQL:
    """Um duble em que toda escrita grava e nenhuma leitura devolve nada."""
    return FakeSessaoSQL(
        respostas={
            "INSERT INTO desafio.tb903_perfil_dificuldade": [{"id_perfil": "p"}],
            "INSERT INTO desafio.tb904_motor": [{"id_motor": "m"}],
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": "d"}],
            "INSERT INTO desafio.tb002_medicao_regua": [{"id_medicao": "m"}],
            "INSERT INTO desafio.tb003_feito_desafio": [{"id_feito_desafio": "f"}],
            "INSERT INTO desafio_dia.tb001_desafio_dia": [{"id_desafio_dia": "dd"}],
        }
    )


def _gerar_um(dt_dia: date, *_a: Any, **kwargs: Any) -> list[Candidato]:
    """Uma geracao que sempre acha candidato — do TIPO daquele dia.

    ⚠️ **O tipo sai do dia, e os parametros do que o job pediu.** Um duble que
    devolvesse sempre o mesmo candidato faria o job publicar as medidas de
    `fechar_caixas` no dia das damas — e desde 12/09/2026 isso estoura com
    `KeyError`, porque as medidas passaram a ler os parametros do candidato.
    """
    co_tipo = escolher_tipo(escolher_jogo(dt_dia), dt_dia)
    return [_candidato(co_tipo, kwargs.get("parametros"))]


def _gerar_nenhum(*_a: Any, **_k: Any) -> list[Candidato]:
    """Uma geracao que nunca acha — o caso que chama a reprise."""
    return []


#: A banda que os testes de ENCADEAMENTO usam.
#:
#: ⚠️ **Aceita qualquer taxa, e e deliberado.** O duble resolve sempre, entao a
#: regua mede 100% — que esta legitimamente **fora** da banda real de 70-80%. Sem
#: esta banda larga, todo teste de encadeamento passaria a medir a decisao de
#: calibracao, e a falha diria "fora da banda" em vez de dizer o que quebrou.
#:
#: ⛔ A banda de verdade tem casos proprios, mais abaixo.
BANDA_LARGA = Alvo(piso=0.0, teto=1.0, co_origem="teste-encadeamento")


async def _rodar(
    sessao: FakeSessaoSQL,
    *,
    gerar: Any = _gerar_um,
    bancada: Any = None,
    dt_hoje: date = date(2026, 9, 20),
    alvo: Any = BANDA_LARGA,
) -> principal_mod.Relatorio:
    """Roda a execucao inteira com os dubles."""
    banc = bancada or _Bancada()
    return await principal_mod.executar(
        sessao,
        dt_hoje=dt_hoje,
        gerar=gerar,
        bancada_de=lambda _c: banc,
        alvo=alvo,
        # ⚠️ Uma execucao por mascote: a regua e a contagem, e o que se testa aqui
        # e o encadeamento. Vinte multiplicariam o duble por vinte sem provar mais.
        nu_execucoes_da_regua=1,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. A ORDEM dos passos
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_o_PERFIL_e_gravado_antes_do_primeiro_desafio() -> None:
    """🔒 ⛔ Sem as linhas do perfil, a `fk001_perfil` recusa o desafio.

    ⚠️ E ela recusaria **depois** de o candidato ter sido gerado e medido pelos
    tres mascotes — a parte cara feita e jogada fora, uma vez por dia, no Railway.

    Gravar o perfil custa milissegundos e roda no comeco.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    ordem = [texto for texto, _ in sessao.executadas]
    perfil = next(i for i, s in enumerate(ordem) if "tb903_perfil_dificuldade" in s)
    desafio = next(i for i, s in enumerate(ordem) if "INSERT INTO desafio.tb001_desafio" in s)
    assert perfil < desafio


@pytest.mark.asyncio
async def test_o_MOTOR_e_gravado_antes_do_primeiro_desafio() -> None:
    """🔒 ⛔ Sem a linha de `tb904_motor`, a `fk002_motor` recusa o desafio.

    ⚠️ **E a mesma armadilha do perfil, com o mesmo preco**: a recusa viria
    **depois** de o candidato ter sido gerado e medido pelos tres mascotes — a
    parte cara feita e jogada fora, uma vez por dia, no Railway.

    A dimensao nasceu em 11/09/2026 (T049e, migracao `0022`) para que
    `damas-py-2f8e15cd` deixe de ser um resumo que ninguem consegue inverter.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    ordem = [texto for texto, _ in sessao.executadas]
    motor = next(i for i, s in enumerate(ordem) if "tb904_motor" in s)
    desafio = next(
        i for i, s in enumerate(ordem) if "INSERT INTO desafio.tb001_desafio" in s
    )
    assert motor < desafio


@pytest.mark.asyncio
async def test_o_MOTOR_ORFAO_vira_aviso_e_NAO_muda_o_codigo_de_saida() -> None:
    """⛔ Sinal que dispara sempre ninguem le — a licao de `fora_da_banda`.

    ⚠️ **O que o aviso faz e adiantar uma falha de REPRISE.** A `fk002_motor`
    nasceu `NOT VALID`, entao os desafios anteriores a `0022` continuam validos;
    mas uma reprise **copia** o `co_versao_motor` da origem, e copia e linha nova
    — ela bateria na FK exatamente no dia em que a fila de aprovados secou.

    ⚠️ E nao e quebra da execucao de hoje: e pendencia herdada da migracao. Por
    isso ela grita no resumo e o codigo de saida continua `0`.
    """
    sessao = _sessao_feliz()
    sessao.respostas["vw904_motor"] = [
        {"co_versao_motor": "damas-py-antigo1", "co_jogo": "damas"}
    ]
    relatorio = await _rodar(sessao)

    assert relatorio.motores_orfaos == ["damas/damas-py-antigo1"]
    assert "MOTOR FORA DA DIMENSAO" in relatorio.resumo()
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ


@pytest.mark.asyncio
async def test_a_CONEXAO_e_SOLTA_antes_da_geracao() -> None:
    """🔒 ⛔ Nenhuma transacao fica aberta durante a geracao (T049j).

    ⚠️ **No Postgres a transacao comeca na primeira consulta e so termina no
    `commit`/`rollback`.** As leituras do plano e do rodizio abrem uma; a geracao
    que vem depois leva **segundos a minutos** e nao toca no banco.

    ⛔ **O defeito nao da erro nenhum**, e e por isso que ele precisa de cadeado:

      · `dh_geracao` tem `DEFAULT now()`, e `now()` e o instante em que a
        **transacao** comecou — o painel mostraria "gerado em" minutos antes do
        que foi;
      · a sessao aberta segura o `xmin` e **impede o `VACUUM`** no banco inteiro;
        e um `idle_in_transaction_session_timeout` do provedor derrubaria a
        conexao **no meio**, jogando fora o trabalho caro ja feito.

    O teste marca o instante da geracao na propria linha do tempo do duble, e
    exige que o evento imediatamente anterior seja um fim de transacao.
    """
    sessao = _sessao_feliz()

    def gerar_marcando(*a: Any, **k: Any) -> list[Candidato]:
        sessao.linha_do_tempo.append("GERACAO")
        return _gerar_um(*a, **k)

    await _rodar(sessao, gerar=gerar_marcando)

    linha = sessao.linha_do_tempo
    assert "GERACAO" in linha, "o duble de geracao nao foi chamado"
    anterior = linha[linha.index("GERACAO") - 1]
    assert anterior in ("rollback", "commit"), (
        f"a geracao comecou com transacao ABERTA — antes dela veio {anterior!r}"
    )


@pytest.mark.asyncio
async def test_a_CONEXAO_e_SOLTA_antes_de_provar_e_medir() -> None:
    """🔒 O segundo trecho caro, e o maior: provar o termino e medir a regua.

    ⚠️ A pergunta *"ja foi publicado?"* (T049i) e uma leitura, e **abre transacao
    de novo**. Logo depois vem ate 200 lances de prova e `3 mascotes x 20
    execucoes` de regua, sem uma unica consulta no meio — o trecho mais caro da
    execucao inteira.

    ⛔ Soltar a conexao so antes da geracao consertaria metade do defeito, e a
    metade que sobrasse seria a maior.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    linha = sessao.linha_do_tempo
    # A consulta de unicidade e a unica com `IS NOT DISTINCT FROM` no job.
    #
    # ⚠️ `next(..., None)` com assercao propria, e nao `next(...)` cru: dentro de
    # uma corrotina o `StopIteration` vira `RuntimeError` e esconde a causa —
    # a mensagem vira "coroutine raised StopIteration", que nao diz nada.
    i = next(
        (k for k, evento in enumerate(linha) if "IS NOT DISTINCT FROM" in evento),
        None,
    )
    assert i is not None, "a consulta de unicidade nao apareceu na linha do tempo"
    assert linha[i + 1] in ("rollback", "commit"), (
        f"a medicao comecou com transacao ABERTA — depois da leitura veio "
        f"{linha[i + 1]!r}"
    )


@pytest.mark.asyncio
async def test_soltar_a_conexao_NAO_grava_nada_pela_metade() -> None:
    """⚠️ `rollback`, e nao `commit` — o verbo diz que nada foi escrito.

    ⛔ Um `commit` no lugar gravaria, sem querer, qualquer escrita que alguem
    viesse a acrescentar acima dele. E um `commit` silencioso e pior que um
    `rollback` explicito: ele **funciona**, e so se descobre o que ele gravou
    quando alguem for procurar outra coisa.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    assert "rollback" in sessao.linha_do_tempo
    # ⚠️ O que se afirma e que os `commit` continuam sendo os das ESCRITAS — o
    # perfil, o motor e a publicacao —, e nao que eles sumiram.
    assert sessao.commits >= 3


@pytest.mark.asyncio
async def test_a_EXPIRACAO_roda_antes_de_gerar() -> None:
    """⚠️ Ela e barata e independente, e fecha partidas que ja deviam estar fechadas.

    Rodar depois da geracao a deixaria de fora sempre que a geracao estourasse —
    e o defeito que ela conserta (partida `em_andamento` para sempre, sem replay)
    nao tem nada a ver com a fila.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    ordem = [texto for texto, _ in sessao.executadas]
    expiracao = next(i for i, s in enumerate(ordem) if "UPDATE partida.tb001_partida" in s)
    assert expiracao == 0


@pytest.mark.asyncio
async def test_a_AUDITORIA_e_o_ultimo_passo() -> None:
    """⚠️ Ela e a unica rotina que pode ser adiada sem custo.

    Uma resolucao auditada amanha continua valendo hoje — ⛔ **vale o aplicativo**
    (RF-DES-032). Gerar, nao: um dia descoberto e um dia sem produto. Se a
    auditoria rodasse antes e consumisse o tempo do container, a fila e que
    pagaria.
    """
    sessao = _sessao_feliz()
    await _rodar(sessao)

    ordem = [texto for texto, _ in sessao.executadas]
    ultimo_desafio = max(
        i for i, s in enumerate(ordem) if "INSERT INTO desafio" in s
    )
    # ⚠️ **`vw003_resolucao` nao serve mais de marcador**: desde 10/09 o alvo
    # movel da regua tambem le essa VIEW, e ele roda ANTES dos dias. O que so a
    # auditoria tem e o filtro por `co_auditoria`.
    auditoria = min(i for i, s in enumerate(ordem) if "co_auditoria" in s)
    assert auditoria > ultimo_desafio


# ═══════════════════════════════════════════════════════════════════════════
# 2. O CODIGO DE SAIDA
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_execucao_limpa_sai_com_ZERO() -> None:
    relatorio = await _rodar(_sessao_feliz())
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ
    assert relatorio.gerados == DIAS_MINIMOS


@pytest.mark.asyncio
async def test_dia_DESCOBERTO_sai_com_UM_mesmo_com_o_resto_certo() -> None:
    """🔒 ⛔ Um job que "termina bem" sem gerar nada parece um job que funcionou.

    ⚠️ Este e o caso que o esqueleto antigo protegia com a saida 2 fixa, e a
    protecao nao podia se perder ao trocar o esqueleto por codigo de verdade: a
    fila secaria em silencio ate alguem abrir o aplicativo e ver o dia vazio.

    Aqui a geracao nao acha nada e a reprise tambem nao (o duble nao tem
    candidatas) — sete dias descobertos.
    """
    relatorio = await _rodar(_sessao_feliz(), gerar=_gerar_nenhum)

    assert relatorio.gerados == 0
    assert len(relatorio.nao_cobertos) == DIAS_MINIMOS
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_resolucao_DIVERGENTE_tambem_sai_com_UM() -> None:
    """⚠️ Divergencia e alerta, nunca correcao — mas precisa acender luz.

    ⛔ O job nao toca em `nu_xp`, nao apaga resolucao e nao tira ninguem do
    quadro (RF-DES-032). O que ele pode fazer e **avisar**, e o codigo de saida e
    o unico aviso que o painel do Railway mostra sozinho.
    """
    relatorio = await _rodar(_sessao_feliz())
    relatorio.auditoria = {"conferem": 10, "divergentes": 1, "impossiveis": 0}
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_auditoria_IMPOSSIVEL_tambem_sai_com_UM() -> None:
    """⚠️ Ela e sintoma de DESAFIO PUBLICADO QUEBRADO, e nao de trapaca.

    Ele fica no ar enquanto ninguem olhar, e `co_auditoria` continua `pendente` —
    que, na secao de divergencias do painel, se le como *"esta tudo certo"*.
    """
    relatorio = await _rodar(_sessao_feliz())
    relatorio.auditoria = {"conferem": 0, "divergentes": 0, "impossiveis": 3}
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


def test_sem_DATABASE_URL_o_processo_sai_com_DOIS(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⛔ "Nem comecou" e o codigo certo: nada foi gravado.

    ⚠️ E **sem `traceback`**: a causa e uma Variable esquecida no console do
    Railway, e o rastro de pilha so afogaria o recado que diz onde arrumar.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert principal_mod.principal() == principal_mod.CODIGO_NEM_COMECOU

    erro = capsys.readouterr().err
    assert "DATABASE_URL" in erro
    assert "Traceback" not in erro


# ═══════════════════════════════════════════════════════════════════════════
# 3. Um dia que estoura NAO derruba os outros
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_um_dia_que_ESTOURA_nao_derruba_a_execucao() -> None:
    """🔒 Seis dias publicados e um com defeito valem mais que sete dias vazios.

    ⚠️ O laco fala com dois motores, com o juiz e com o banco. Enumerar as
    excecoes deles seria uma lista que envelhece — e a que faltasse derrubaria a
    execucao inteira por causa de um dia.
    """
    chamadas = {"n": 0}

    def gerar_com_um_defeito(*_a: Any, **_k: Any) -> list[Candidato]:
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise RuntimeError("o motor engasgou neste dia")
        return _gerar_um(*_a, **_k)

    relatorio = await _rodar(_sessao_feliz(), gerar=gerar_com_um_defeito)

    assert relatorio.gerados == DIAS_MINIMOS - 1
    assert len(relatorio.nao_cobertos) == 1
    assert "o motor engasgou" in relatorio.nao_cobertos[0]
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_termino_NAO_PROVADO_descarta_e_diz_a_diferenca() -> None:
    """⚠️ Descartar por nao provar NAO e provar que o jogo nao acaba.

    A distincao importa meses depois, para quem investigar uma fila curta: uma
    coisa e o job nao ter conseguido levar a partida ao fim dentro do teto; outra
    e o jogo nao ter fim.
    """
    relatorio = await _rodar(
        _sessao_feliz(), bancada=_Bancada(acaba=False)
    )
    assert relatorio.gerados == 0
    assert relatorio.descartados
    assert "NAO prova" in relatorio.descartados[0]


# ═══════════════════════════════════════════════════════════════════════════
# 4. O rodizio e o editorial
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_lista_de_RECENTES_e_lida_uma_vez_e_usada_nas_DUAS_escolhas() -> None:
    """🔒 O defeito silencioso do rodizio.

    `escolher_tipo` e chamada aqui, para saber quais parametros passar, e de novo
    dentro de `gerar_candidatos`. As duas sao puras da data — ⛔ **mas discordam
    se a lista de recentes mudar entre elas**, e o desafio sairia gravado com os
    parametros de um tipo e a linha de chegada de outro.

    ⚠️ **Nada acusaria**: as duas linhas seriam validas.
    """
    vistos: list[Any] = []

    def gerar_espiao(dt_dia: date, **kwargs: Any) -> list[Candidato]:
        vistos.append(tuple(kwargs["tipos_recentes"]))
        return _gerar_um(dt_dia, **kwargs)

    sessao = FakeSessaoSQL(
        respostas={
            "INSERT INTO desafio.tb903_perfil_dificuldade": [{"id_perfil": "p"}],
            "INSERT INTO desafio.tb904_motor": [{"id_motor": "m"}],
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": "d"}],
            "INSERT INTO desafio_dia.tb001_desafio_dia": [{"id_desafio_dia": "dd"}],
            # A leitura do rodizio devolve algo, para o teste nao passar com
            # duas listas vazias — que seriam iguais por acidente.
            "co_tipo_desafio": [{"co_tipo_desafio": "pontinhos_fechar_caixas"}],
        }
    )
    await _rodar(sessao, gerar=gerar_espiao)

    assert vistos, "a geracao nem chegou a ser chamada"
    assert all(v == ("pontinhos_fechar_caixas",) for v in vistos)


@pytest.mark.parametrize("co_tipo", sorted(RECEITAS))
def test_todo_tipo_PUBLICAVEL_tem_editorial(co_tipo: str) -> None:
    """🔒 Receita e vetor dizem COMO julgar; falta dizer com QUE NUMEROS publicar.

    ⛔ Um padrao — *"se nao souber, use 3"* — poria no ar um desafio cuja
    dificuldade ninguem escolheu, e ele pareceria igual aos outros na tela. O
    editorial falha alto; este caso garante que ele nunca precisa falhar.
    """
    assert variantes_de(co_tipo), f"{co_tipo} nao tem nenhuma variante"
    for publicacao in variantes_de(co_tipo):
        assert publicacao.parametros


@pytest.mark.parametrize("co_tipo", sorted(EDITORIAL))
def test_as_medidas_de_cada_tipo_FECHAM_em_1000(co_tipo: str) -> None:
    """⚠️ E a soma que mantem `Q` dentro de [0, 1].

    Ela e conferida na hora de gravar, mas descobrir la seria descobrir tarde: o
    candidato ja teria sido gerado e medido.
    """
    # ⚠️ **TODAS as variantes**, e nao so a primeira: desde T049f cada tipo tem
    # uma lista, e uma variante com peso quebrado so apareceria no dia em que o
    # odometro chegasse nela — semanas depois de entrar.
    for publicacao in variantes_de(co_tipo):
        conferir(
            publicacao.medidas(parametros_para_conferencia(publicacao.parametros))
        )


@pytest.mark.parametrize("co_tipo", sorted(EDITORIAL))
def test_os_parametros_de_cada_tipo_MONTAM_a_chegada(co_tipo: str) -> None:
    """🔒 O editorial e a receita precisam falar dos mesmos numeros.

    ⚠️ Um `{"caixas": 4}` para uma receita que le `p["turnos"]` estouraria com
    `KeyError` **no meio da geracao do dia**, depois de o perfil ter sido gravado
    — e o dia ficaria descoberto por um erro de digitacao numa tabela.
    """
    # ⚠️ **Uma variante por vez, todas elas.** Um `{"caixas": 4}` numa variante
    # de uma receita que le `p["turnos"]` estouraria so na vez daquela variante.
    for publicacao in variantes_de(co_tipo):
        receita_de(co_tipo).montar(parametros_para_conferencia(publicacao.parametros))


def test_tipo_SEM_editorial_falha_alto() -> None:
    """E a mensagem diz o que falta: numeros, e nao regra."""
    with pytest.raises(TipoSemEditorial, match="nao tem editorial"):
        variantes_de("pontinhos_tipo_que_nao_existe")


@pytest.mark.parametrize("co_tipo", sorted(EDITORIAL))
def test_o_editorial_NAO_publica_tipo_sem_receita(co_tipo: str) -> None:
    """⛔ O outro sentido: numeros escolhidos para um tipo que ninguem sabe julgar.

    ⚠️ O desafio sairia com uma linha de chegada vazia, e o julgamento devolveria
    "nao cumpriu" para todo mundo — sem erro nenhum.
    """
    assert co_tipo in RECEITAS


def test_a_regua_de_tempo_reproduz_o_exemplo_do_DATA_MODEL() -> None:
    """🔒 O `data-model.md` foi PRE-VALIDADO pelo dono, e os numeros sao dele.

    La, `nu_lances_solucao = 5` leva a `nu_tempo_piso_ms = 30000` e
    `nu_tempo_teto_ms = 180000`. ⚠️ Este caso trava a constante que produz isso —
    sem ele, `MILISSEGUNDOS_POR_LANCE_DO_GABARITO` viraria um numero que alguem
    ajustaria sem saber que ha um documento aprovado do outro lado.
    """
    from job.medidas_de_saida import regua_de_tempo

    piso, teto = regua_de_tempo(
        nu_tempo_do_gabarito_ms=5 * principal_mod.MILISSEGUNDOS_POR_LANCE_DO_GABARITO
    )
    assert (piso, teto) == (30_000, 180_000)


# ═══════════════════════════════════════════════════════════════════════════
# 5. A reprise, que e a saida de emergencia
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_sem_candidato_o_job_TENTA_REPRISAR() -> None:
    """⚠️ A fila vazia e o unico defeito deste job que a pessoa ve.

    Antes de deixar o dia descoberto, republica-se um desafio antigo bem
    avaliado — ⚠️ **como COPIA, com identificador proprio**: um desafio e
    publicado uma vez so (determinacao do dono, 04/09/2026).
    """
    sessao = _sessao_feliz()
    await _rodar(sessao, gerar=_gerar_nenhum)
    assert sessao.sql_executado("vw001_desafio_dia"), (
        "a reprise nem chegou a procurar candidata"
    )


@pytest.mark.asyncio
async def test_o_dia_que_JA_ESTAVA_publicado_nao_e_gerado_de_novo() -> None:
    """⚠️ E a idempotencia vista daqui: ela evita TRABALHO.

    ⛔ Quem garante a unicidade e o `un001_dia` do banco — uma checagem "ja
    existe?" nao bastaria, porque duas execucoes simultaneas passariam as duas
    por ela.
    """
    hoje = date(2026, 9, 20)
    ja_tem = [hoje, hoje + timedelta(days=1)]
    sessao = FakeSessaoSQL(
        respostas={
            "INSERT INTO desafio.tb903_perfil_dificuldade": [{"id_perfil": "p"}],
            "INSERT INTO desafio.tb904_motor": [{"id_motor": "m"}],
            "INSERT INTO desafio.tb001_desafio": [{"id_desafio": "d"}],
            "INSERT INTO desafio_dia.tb001_desafio_dia": [{"id_desafio_dia": "dd"}],
            "FROM desafio_dia.vw001_desafio_dia\n WHERE dt_dia BETWEEN": [
                {"dt_dia": dia} for dia in ja_tem
            ],
        }
    )
    relatorio = await _rodar(sessao, dt_hoje=hoje)

    assert relatorio.ja_publicados == 2
    assert relatorio.gerados == DIAS_MINIMOS - 2


# ═══════════════════════════════════════════════════════════════════════════
# 6. O resumo que vai para o log do Railway
# ═══════════════════════════════════════════════════════════════════════════


def test_o_resumo_DISTINGUE_fila_cheia_de_job_que_nao_fez_nada() -> None:
    """⚠️ "Cobri 7 dias" nao diz qual das duas aconteceu.

    E as duas pedem reacoes opostas de quem le o log: uma e o estado saudavel, a
    outra e para investigar agora.
    """
    relatorio = principal_mod.Relatorio(dias_no_plano=7, ja_publicados=7, gerados=0)
    texto = relatorio.resumo()
    assert "7 ja publicado(s)" in texto
    assert "0 gerado(s)" in texto


def test_o_resumo_GRITA_quando_ha_buraco_na_fila() -> None:
    """O aplicativo vai mostrar dia vazio, e o log precisa dizer isso em voz alta."""
    relatorio = principal_mod.Relatorio(nao_cobertos=["2026-09-22: sem candidato"])
    assert "DIAS SEM DESAFIO" in relatorio.resumo()


def test_o_rodizio_do_jogo_e_do_tipo_continua_DETERMINISTICO() -> None:
    """⚠️ Se ele nao fosse, duas execucoes para o mesmo dia gerariam desafios
    diferentes — e a idempotencia dependeria de sorte, e nao do `un001_dia`."""
    dia = date(2026, 9, 20)
    jogo = escolher_jogo(dia)
    assert escolher_jogo(dia) == jogo
    assert escolher_tipo(jogo, dia) == escolher_tipo(jogo, dia)


# ═══════════════════════════════════════════════════════════════════════════
# 7. A BANDA da regua — a medicao virando DECISAO
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **Ate 10/09/2026 nada disto existia.** `dentro_da_banda` e `alvo_para_a_regua`
# eram chamadas so pelos proprios testes — codigo morto —, e a primeira execucao
# real no `des` publicou um desafio que os TRES mascotes resolveram 20 de 20.
# A regua era medida, gravada e ignorada.


def test_a_banda_REAL_recusa_o_desafio_banal() -> None:
    """🔒 O caso que a primeira execucao real produziu, virado teste.

    Tres mascotes resolvendo 20 de 20 e um desafio que nao desafia ninguem — e
    ele foi publicado assim mesmo, porque ninguem perguntava.
    """
    from job.regua import distancia_da_banda

    banal = [
        Medicao(
            co_personagem=quem,
            nu_execucoes=20,
            nu_resolveu=20,
            co_versao_perfil="p",
            co_versao_motor="v",
        )
        for quem in ("cacau", "tex", "magno")
    ]
    assert distancia_da_banda(banal, piso=PISO_FIXO, teto=TETO_FIXO) > 0


@pytest.mark.asyncio
async def test_fora_da_banda_PUBLICA_o_menos_pior_e_REGISTRA_sem_falhar() -> None:
    """🔒 ⛔ Calibracao fora do alvo NAO e quebra, e nao pode pintar o painel.

    ⚠️ **Medido na primeira execucao completa (10/09/2026): seis dos sete dias
    ficaram fora da banda.** Se isso saisse com 1, o Railway ficaria vermelho
    todo dia — e sinal que dispara sempre e sinal que ninguem le. O dia em que
    houvesse um buraco de verdade na fila, o vermelho nao significaria nada.

    ⚠️ Deixar o dia vazio seria pior que publicar o menos pior: tudo nasce
    `candidato` (RF-DES-012a), entao isto e **enfileirar para revisao**, e nao
    publicar. O numero continua no log e no resumo — adiar a decisao de
    calibracao e diferente de esconder o dado.
    """
    relatorio = await _rodar(
        _sessao_feliz(), alvo=Alvo(piso=PISO_FIXO, teto=TETO_FIXO, co_origem="fixo")
    )

    assert relatorio.gerados == DIAS_MINIMOS, "o dia precisa ficar coberto"
    assert relatorio.fora_da_banda, "a divergencia de calibracao nao foi registrada"
    assert "FORA DA BANDA" in relatorio.resumo(), "o numero sumiu do log"
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ


@pytest.mark.asyncio
async def test_dia_DESCOBERTO_continua_saindo_com_UM_mesmo_com_fora_da_banda() -> None:
    """⚠️ O contraste que da sentido ao caso acima.

    ⛔ Dia descoberto e o app mostrando dia vazio — quebra de produto, e ela
    continua acendendo vermelho. Afrouxar os dois juntos teria trocado um sinal
    ruidoso por sinal nenhum.
    """
    relatorio = await _rodar(
        _sessao_feliz(),
        gerar=_gerar_nenhum,
        alvo=Alvo(piso=PISO_FIXO, teto=TETO_FIXO, co_origem="fixo"),
    )
    assert relatorio.nao_cobertos
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_dentro_da_banda_sai_com_ZERO_e_nao_registra_nada() -> None:
    """O contraste do caso acima: quando encaixa, ninguem e avisado de nada."""
    relatorio = await _rodar(_sessao_feliz(), alvo=BANDA_LARGA)

    assert relatorio.gerados == DIAS_MINIMOS
    assert relatorio.fora_da_banda == []
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ


@pytest.mark.asyncio
async def test_o_job_gera_MAIS_DE_UM_candidato_por_dia() -> None:
    """🔒 Com um candidato so, a banda nao tem o que decidir.

    ⚠️ Ou se publica o que veio, ou se deixa o dia descoberto — e ai medir a
    regua seria cerimonia. E por isso que `CANDIDATOS_POR_DIA` existe.
    """
    pedidos: list[int] = []

    def gerar_espiao(dt_dia: date, **kwargs: Any) -> list[Candidato]:
        pedidos.append(kwargs["quantos"])
        return _gerar_um(dt_dia, **kwargs)

    await _rodar(_sessao_feliz(), gerar=gerar_espiao)

    assert pedidos, "a geracao nem foi chamada"
    assert all(q >= 2 for q in pedidos), (
        f"o job pediu {pedidos} candidato(s) por dia; com um so a banda da regua "
        "nao tem o que decidir"
    )


@pytest.mark.asyncio
async def test_a_medicao_PARA_no_primeiro_candidato_que_encaixa() -> None:
    """⚠️ O custo de gerar tres so se paga quando o primeiro nao serve.

    Medir e a parte cara — `3 mascotes x 20 execucoes` por candidato. Medir os
    tres sempre triplicaria o tempo do job por uma escolha que ja estava feita no
    primeiro.
    """
    medidos: list[str] = []

    class _BancadaContada(_Bancada):
        def julgar(self, fita: list[dict[str, Any]]) -> _Julgamento:
            medidos.append("julgou")
            return _Julgamento(True)

    def gerar_tres(*_a: Any, **_k: Any) -> list[Candidato]:
        # ⚠️ Tres candidatos do MESMO dia — e o tipo do dia que manda, como no
        # gerador de verdade.
        return [_gerar_um(*_a, **_k)[0] for _ in range(3)]

    relatorio = await _rodar(
        _sessao_feliz(), gerar=gerar_tres, bancada=_BancadaContada(), alvo=BANDA_LARGA
    )

    # 3 mascotes x 1 execucao x 1 lance = 3 julgamentos por candidato medido.
    # Sete dias, um candidato medido em cada: 21. Se medisse os tres, seriam 63.
    assert relatorio.gerados == DIAS_MINIMOS
    assert len(medidos) == 3 * DIAS_MINIMOS, (
        f"{len(medidos)} julgamentos — o job mediu mais candidatos do que "
        "precisava depois de ja ter achado um que encaixa"
    )


@pytest.mark.asyncio
async def test_o_alvo_e_lido_UMA_VEZ_por_execucao() -> None:
    """⚠️ A taxa observada e a mesma para todos os dias da safra.

    Sete consultas dariam sete respostas iguais, numa rotina que ja e a mais cara
    do job.
    """
    sessao = _sessao_feliz()
    await principal_mod.executar(
        sessao,
        dt_hoje=date(2026, 9, 20),
        gerar=_gerar_um,
        bancada_de=lambda _c: _Bancada(),
        nu_execucoes_da_regua=1,
        # ⚠️ Sem `alvo` — para o caminho da LEITURA ser exercitado.
    )
    leituras = [
        sql for sql, _ in sessao.executadas if "count(DISTINCT t.id_usuario)" in sql
    ]
    assert len(leituras) == 1, f"o alvo foi lido {len(leituras)} vezes"


def test_sem_volume_a_banda_e_a_FIXA() -> None:
    """⚠️ Nao e limitacao temporaria escondida: e a resposta correta.

    A taxa observada de doze pessoas nao diz nada sobre a dificuldade de um
    desafio, e sera esse o caso por muito tempo.
    """
    from job.alvo_observado import alvo_para_a_regua

    alvo = alvo_para_a_regua(nu_tentaram=0, nu_resolveram=0)
    assert (alvo.piso, alvo.teto) == (PISO_FIXO, TETO_FIXO)
    assert alvo.co_origem == "fixo"


# ═══════════════════════════════════════════════════════════════════════════
# 7. ⛔ T049i — nenhum desafio se repete, e a reprise e a unica excecao
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ **O duble responde a MESMA assinatura para todos**, e e o que se quer aqui:
# o que se mede e a reacao do encadeamento a uma repeticao, e nao a consulta —
# quem prova a consulta e `test_banco_e_repositorio_do_job.py`.


def _sessao_com_repeticao() -> FakeSessaoSQL:
    """Um duble em que TODO candidato ja foi publicado antes.

    ⚠️ **O trecho que identifica a consulta e `IS NOT DISTINCT FROM`**, e nao
    `SELECT d.id_desafio`. O duble roteia por **substring**, e `SELECT
    d.id_desafio` tambem aparece na busca de candidatas da reprise — com ele, a
    reprise recebia esta resposta de uma linha so e estourava com
    `KeyError: 'id_origem'`, transformando um teste de repeticao num teste de
    reprise quebrada.
    """
    sessao = _sessao_feliz()
    sessao.respostas["IS NOT DISTINCT FROM"] = [{"id_desafio": "publicado-em-marco"}]
    return sessao


@pytest.mark.asyncio
async def test_candidato_JA_PUBLICADO_e_recusado() -> None:
    """🔒 ⛔ *"Nao podemos ter desafios repetidos"* — o dono, 11/09/2026.

    ⚠️ **`tipos_recentes` nao cobria isto.** Ele evita repetir o **tipo**, nao a
    **posicao**: a mesma FEN `B:W25,26,29:B2,13,17,21` saiu duas vezes em sete
    dias no `des`, com sementes diferentes, e nada acusou.
    """
    sessao = _sessao_com_repeticao()
    relatorio = await _rodar(sessao, gerar=_gerar_um)

    assert relatorio.gerados == 0, "um desafio repetido foi publicado"
    assert relatorio.repetidos, "a recusa nao foi registrada em lugar nenhum"


@pytest.mark.asyncio
async def test_a_recusa_NAO_sai_calada() -> None:
    """⛔ Sem o registro, o dia em que o acervo se esgotar parece falta de sorte.

    ⚠️ O log diria *"sem candidato"*, a reprise entraria, e ninguem saberia que a
    causa foi o acervo daquele tipo ter acabado — que e um problema com conserto,
    e diferente de o jogo ter ficado dificil.

    ⚠️ **E a mensagem leva o id do desafio anterior**, para levar quem investiga
    direto a linha que ja existe.
    """
    sessao = _sessao_com_repeticao()
    relatorio = await _rodar(sessao, gerar=_gerar_um)

    resumo = relatorio.resumo()
    assert "JA PUBLICADOS ANTES" in resumo
    assert "publicado-em-marco" in resumo


@pytest.mark.asyncio
async def test_recusado_por_repeticao_o_dia_cai_na_REPRISE() -> None:
    """⚠️ **A reprise e a unica excecao, e nao fere a regra.**

    Ela e **copia com identificador proprio** (determinacao do dono, 04/09/2026),
    e o caminho dela ⛔ nao passa pela consulta de assinatura — senao a saida de
    emergencia se recusaria a si mesma, e o dia ficaria descoberto justamente
    quando mais precisa de cobertura.
    """
    sessao = _sessao_com_repeticao()
    await _rodar(sessao, gerar=_gerar_um)

    # ⚠️ O duble nao tem candidata para reprisar, entao o que se afirma aqui e
    # que a reprise **foi tentada** — e o mesmo que
    # `test_sem_candidato_o_job_TENTA_REPRISAR` afirma. O que importa provar e
    # que a recusa por repeticao chega ate ela, e nao para antes.
    assert sessao.sql_executado("vw001_desafio_dia"), (
        "a reprise nem chegou a procurar candidata"
    )


@pytest.mark.asyncio
async def test_repeticao_sozinha_NAO_pinta_o_painel_de_vermelho() -> None:
    """⚠️ A mesma lição de `fora_da_banda`: sinal que dispara sempre ninguem le.

    Uma recusa por repeticao com o dia **coberto** (pela reprise ou pelo proximo
    candidato) e observacao, e nao quebra. ⛔ O que sai com `1` continua sendo dia
    descoberto — o unico defeito deste job que a pessoa ve na tela.
    """
    relatorio = principal_mod.Relatorio()
    relatorio.repetidos.append("2026-09-20: damas_coroar repetiria o desafio X")
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_FEZ

    relatorio.nao_cobertos.append("2026-09-21: nem a reprise")
    assert relatorio.codigo_de_saida == principal_mod.CODIGO_DIVERGIU


@pytest.mark.asyncio
async def test_a_pergunta_vem_ANTES_da_medicao_cara() -> None:
    """⚠️ Um `SELECT` com `LIMIT 1` custa menos que 3 mascotes x 20 execucoes.

    Provar o termino roda ate 200 lances; medir a regua roda a CNN dezenas de
    vezes. Perguntar *"ja publiquei isto?"* depois disso seria pagar o caro antes
    do barato — e o candidato seria jogado fora do mesmo jeito.

    O duble recusa todos, entao **nenhuma** linha de regua pode ter sido gravada.
    """
    sessao = _sessao_com_repeticao()
    await _rodar(sessao, gerar=_gerar_um)

    assert not sessao.sql_executado("INSERT INTO desafio.tb002_medicao_regua"), (
        "a regua foi medida num candidato que ja seria recusado por repeticao"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 8. ⚠️ T049f — a VARIANTE DE PARAMETROS chega ate a geracao
# ═══════════════════════════════════════════════════════════════════════════


def _gerar_espiao(registro: list[dict[str, Any]]) -> Any:
    """Uma geracao que ANOTA os parametros que recebeu, e devolve o candidato.

    ⚠️ **E o unico jeito honesto de provar que a variante chega la.** Os dubles
    de candidato montam a chegada com a primeira variante, entao olhar o `INSERT`
    diria sempre a mesma coisa — o que se quer saber e com **que numeros** o
    `principal()` mandou gerar.
    """

    def gerar(*_a: Any, **kwargs: Any) -> list[Candidato]:
        registro.append(dict(kwargs["parametros"]))
        return _gerar_um(*_a, **kwargs)

    return gerar


@pytest.mark.asyncio
async def test_os_PARAMETROS_mudam_ao_longo_da_fila() -> None:
    """🔒 ⚠️ *"E muito importante que estes parametros variem"* — o dono, 10/09.

    ⛔ **O defeito que este caso guarda e o congelamento silencioso:** uma chamada
    que esquecesse de escolher a variante publicaria a primeira para sempre, e
    ⚠️ **nada denunciaria** — o desafio sairia bem formado, com posicao nova todo
    dia, so que sempre com a mesma tarefa. Foi exatamente assim ate 11/09/2026.

    Sessenta dias cobrem varias voltas do odometro nos dois jogos.
    """
    vistos: list[dict[str, Any]] = []
    for n in range(60):
        await _rodar(
            _sessao_feliz(),
            gerar=_gerar_espiao(vistos),
            dt_hoje=date(2026, 9, 20) + timedelta(days=n),
        )

    distintos = {tuple(sorted(p.items())) for p in vistos}
    assert len(distintos) > 1, (
        "a fila inteira usou os MESMOS parametros: a variante nao esta chegando "
        f"na geracao. Vistos: {distintos}"
    )
