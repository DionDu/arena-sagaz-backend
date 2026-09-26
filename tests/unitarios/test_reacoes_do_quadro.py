"""AS REACOES DO QUADRO - T077 (contracts/quadro-do-dia.md, RF-DES-070 a 074).

O que estes casos protegem:

  · ⚠️ **o vocabulario vem do BANCO** - `tb903_tipo_reacao`, e ⛔ nao um `Enum`
    em Python (RF-DES-226): reacao nova e `INSERT`, e ⛔ nao deploy;
  · ⚠️ **uma por pessoa, por linha** (RF-DES-072), e ela se **troca** - o
    primeiro toque ⛔ nao e definitivo;
  · ⛔ **repetir o `POST` ⛔ nao apaga** - desfazer e o `DELETE`, explicito;
  · ⚠️ **reagir exige conta e ⛔ nao alcanca a propria linha** (RF-DES-084);
  · ⚠️ **so linha que APARECE EM PUBLICO recebe reacao** (RF-DES-077), pela
    **mesma** clausula do quadro;
  · ⛔ **zero ⛔ nao e servido** (RF-DES-073): `reacoes: null`, e ⛔ nao `{}`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from api.desafios.quadro import CLAUSULA_APARECE_EM_PUBLICO, SQL_LINHAS_DE_GENTE
from api.desafios.reacoes import (
    SQL_REAGIR,
    LinhaSemResolucao,
    ReacaoDesconhecida,
    ReagirASiMesmo,
    RepositorioReacao,
    ServicoReacao,
)
from api.nucleo.excecoes import ErroNaoEncontrado
from tests.unitarios.fakes_desafio import FakeSessaoSQL

AGORA = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)
ID_DESAFIO = UUID("9f1c0000-0000-4000-8000-000000000001")
ID_DIA = uuid4()
ID_RESOLUCAO = uuid4()
EU = uuid4()
A_ANA = uuid4()

# ⚠️ Os trechos que o duplo de sessao usa para reconhecer cada consulta. Eles sao
# escolhidos para ⛔ NAO se confundirem: duas das consultas leem `vw006_reacao`, e
# so o que vem depois as separa.
T_TIPO = "vw903_tipo_reacao"
T_DIA = "vw001_desafio_dia"
T_RESOLUCAO = "vw003_resolucao"
T_CONTAGEM = "GROUP BY co_tipo_reacao"
T_MINHA = "AND id_usuario = :id_usuario"
T_GRAVAR = "INSERT INTO desafio_dia.tb006_reacao"
T_APAGAR = "DELETE FROM desafio_dia.tb006_reacao"


def _servico(**respostas):
    """Um servico de reacao sobre uma sessao falsa, com o caminho feliz pronto.

    ⚠️ **O caminho feliz ja vem montado**, e cada caso sobrescreve **so** a peca
    que ele mede: um teste que precisasse preparar as cinco consultas para medir
    uma delas mediria principalmente a propria preparacao.
    """
    padrao = {
        T_TIPO: [{"nu_tipo_reacao": 3}],
        T_DIA: [{"id_desafio_dia": ID_DIA}],
        T_RESOLUCAO: [{"id_resolucao": ID_RESOLUCAO}],
        T_CONTAGEM: [{"co_tipo_reacao": "fogo", "qt": 1}],
        T_MINHA: [{"co_tipo_reacao": "fogo"}],
    }
    padrao.update(respostas)
    sessao = FakeSessaoSQL(respostas=padrao)
    return ServicoReacao(RepositorioReacao(sessao)), sessao


# ═══════════════════════════════════════════════════════════════════════════
# 1. O caminho feliz - e o que ele DEVOLVE
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_reagir_grava_e_devolve_a_contagem_nova():
    """⚠️ A resposta traz a contagem **do servidor**, e ⛔ nao um `204`.

    Com um `204`, a tela teria de somar 1 no que ela ja tinha - e erraria na
    **troca** (em que o total ⛔ nao muda) e sempre que outra pessoa tivesse
    reagido nesse meio-tempo.
    """
    servico, sessao = _servico()

    corpo = await servico.reagir(
        id_desafio=ID_DESAFIO,
        id_usuario=EU,
        id_jogador=A_ANA,
        co_tipo_reacao="fogo",
        agora=AGORA,
    )

    assert corpo == {"reacoes": {"fogo": 1}, "minha_reacao": "fogo"}
    assert sessao.sql_executado(T_GRAVAR)


@pytest.mark.asyncio
async def test_a_gravacao_leva_o_tipo_que_veio_do_CATALOGO():
    """⚠️ O que vai ao banco e o `nu_tipo_reacao`, e ⛔ nao o texto enviado.

    ⛔ Gravar o codigo cru deixaria a tabela de fatos sem `FOREIGN KEY` para a
    dimensao - e um erro de digitacao viraria uma reacao nova, silenciosa.
    """
    servico, sessao = _servico(**{T_TIPO: [{"nu_tipo_reacao": 5}]})

    await servico.reagir(
        id_desafio=ID_DESAFIO,
        id_usuario=EU,
        id_jogador=A_ANA,
        co_tipo_reacao="top",
        agora=AGORA,
    )

    gravacao = [p for texto, p in sessao.executadas if T_GRAVAR in texto]
    assert gravacao and gravacao[0]["nu_tipo_reacao"] == 5
    assert gravacao[0]["id_resolucao"] == ID_RESOLUCAO
    assert gravacao[0]["id_usuario"] == EU


@pytest.mark.asyncio
async def test_zero_reacoes_volta_NULO_e_nao_um_mapa_vazio():
    """⛔ RF-DES-073: `reacoes: null`, e ⛔ nao `{}`.

    ⚠️ E a **mesma** forma que `GET .../quadro` serve - com duas formas, a tela
    teria dois jeitos de ler a mesma coisa, e um deles acabaria desenhando
    *"0 👏"*.
    """
    servico, _ = _servico(**{T_CONTAGEM: [], T_MINHA: []})

    corpo = await servico.desfazer(
        id_desafio=ID_DESAFIO, id_usuario=EU, id_jogador=A_ANA
    )

    assert corpo == {"reacoes": None, "minha_reacao": None}


# ═══════════════════════════════════════════════════════════════════════════
# 2. Uma por pessoa, por linha (RF-DES-072) - e ela se TROCA
# ═══════════════════════════════════════════════════════════════════════════


def test_o_conflito_TROCA_a_reacao_em_vez_de_recusar():
    """⚠️ `ON CONFLICT ... DO UPDATE`, e ⛔ nao `DO NOTHING` nem 409.

    ⛔ Com `DO NOTHING`, o primeiro toque seria definitivo para sempre: quem
    tocasse em *"palmas"* sem querer ficaria preso a ele numa barra desenhada
    justamente para se escolher entre cinco.

    ⚠️ **O caso le a SQL, e ⛔ nao o comportamento do duplo**: a garantia e da
    `un001_reacao`, que existe no banco e ⛔ nao no duplo - medir o duplo aqui
    mediria o teste.
    """
    normalizada = " ".join(SQL_REAGIR.split())
    assert "ON CONFLICT (id_resolucao, id_usuario) DO UPDATE" in normalizada
    assert "DO NOTHING" not in normalizada


def test_o_POST_nunca_apaga___desfazer_e_o_DELETE():
    """⛔ Repetir um pedido ⛔ nao pode desfazer o efeito do anterior.

    ⚠️ E a licao do ingestor da `0006`: um `ON CONFLICT DO NOTHING` que
    descartava o segundo envio **em silencio**. Um `POST` que alternasse apagaria
    a reacao no segundo toque de um duplo toque acidental - e num reenvio da
    rede, sem ninguem ter tocado duas vezes.
    """
    assert "DELETE" not in SQL_REAGIR.upper()


@pytest.mark.asyncio
async def test_reagir_duas_vezes_com_o_mesmo_tipo_deixa_como_estava():
    """⚠️ O segundo `POST` e uma gravacao a mais, e ⛔ nao uma remocao."""
    servico, sessao = _servico()

    for _ in range(2):
        corpo = await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="fogo",
            agora=AGORA,
        )

    assert corpo["minha_reacao"] == "fogo"
    assert not sessao.sql_executado(T_APAGAR)


@pytest.mark.asyncio
async def test_desfazer_duas_vezes_nao_reclama():
    """⚠️ O segundo toque deixa a linha sem reacao, como o primeiro.

    ⛔ Um 404 no segundo so serviria para a tela ter de trata-lo - e a pessoa ja
    conseguiu o que queria.
    """
    servico, sessao = _servico(**{T_CONTAGEM: [], T_MINHA: []})

    for _ in range(2):
        corpo = await servico.desfazer(
            id_desafio=ID_DESAFIO, id_usuario=EU, id_jogador=A_ANA
        )

    assert corpo["minha_reacao"] is None
    assert sessao.sql_executado(T_APAGAR)


# ═══════════════════════════════════════════════════════════════════════════
# 3. O vocabulario vem do BANCO (RF-DES-226)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_tipo_fora_do_catalogo_ativo_da_400():
    """⚠️ **400, e ⛔ nao 404**: o que ⛔ nao existe e o tipo, e ⛔ nao o desafio.

    ⚠️ **E ⛔ nao vira o sentinela `desconhecido`**: ele existe para uma LEITURA
    nao quebrar diante de codigo mais novo que o leitor; aceita-lo na escrita
    gravaria uma reacao que ninguem consegue desenhar.
    """
    servico, _ = _servico(**{T_TIPO: []})

    with pytest.raises(ReacaoDesconhecida) as erro:
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="deboche",
            agora=AGORA,
        )

    assert erro.value.status_http == 400
    assert erro.value.codigo == "reacao_desconhecida"


def test_a_consulta_do_tipo_exige_ic_ativo():
    """⛔ Uma reacao **desligada** ⛔ nao volta a ser escolhivel.

    ⚠️ `ic_ativo` e o interruptor que permite aposentar uma reacao **sem** apagar
    a dimensao - e apagar ⛔ nao seria possivel: `tb006_reacao` aponta para ca, e
    as reacoes ja dadas perderiam o significado.
    """
    from api.desafios.reacoes import SQL_TIPO_ATIVO

    assert "ic_ativo" in SQL_TIPO_ATIVO


@pytest.mark.asyncio
async def test_o_tipo_e_conferido_ANTES_de_procurar_o_desafio():
    """⚠️ A ordem das guardas e escolha, e ⛔ nao acaso.

    Um codigo invalido responde **400** mesmo quando o desafio tambem ⛔ nao
    existe. ⛔ Se o 404 viesse primeiro, quem digitasse um tipo errado receberia
    *"desafio nao encontrado"* e iria investigar o desafio.
    """
    servico, _ = _servico(**{T_TIPO: [], T_DIA: []})

    with pytest.raises(ReacaoDesconhecida):
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="deboche",
            agora=AGORA,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Quem pode receber - e quem pode dar
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ninguem_reage_a_propria_linha():
    """⛔ RF-DES-072 na pratica: a barra e para aplaudir **outra** pessoa.

    ⚠️ O quadro ja diz isso em `pode_reagir: false` - esta e a **segunda**
    guarda, e ⛔ ela ⛔ nao e redundante: `pode_reagir` e desenho de tela, e quem
    fala com a rota ⛔ nao passa obrigatoriamente por ela.
    """
    servico, sessao = _servico()

    with pytest.raises(ReagirASiMesmo):
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=EU,
            co_tipo_reacao="fogo",
            agora=AGORA,
        )

    # ⛔ E ⛔ nao chegou a escrever nada.
    assert not sessao.sql_executado(T_GRAVAR)


@pytest.mark.asyncio
async def test_desafio_inexistente_da_404():
    """⚠️ Aqui o 404 e o certo: o que ⛔ nao existe **e** o desafio."""
    servico, _ = _servico(**{T_DIA: []})

    with pytest.raises(ErroNaoEncontrado) as erro:
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="fogo",
            agora=AGORA,
        )

    assert erro.value.codigo == "desafio_inexistente"


@pytest.mark.asyncio
async def test_linha_que_nao_aparece_no_quadro_da_404_sem_dizer_por_que():
    """⚠️ **⛔ Nao resolveu** e **se escondeu** dao o MESMO erro, de proposito.

    ⛔ Separar os dois contaria a quem pergunta que fulano *"existe e se
    escondeu"* - e a visibilidade desligada deixaria de esconder, que e
    exatamente o que ela promete (RF-DES-077).
    """
    servico, sessao = _servico(**{T_RESOLUCAO: []})

    with pytest.raises(LinhaSemResolucao) as erro:
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="fogo",
            agora=AGORA,
        )

    assert erro.value.status_http == 404
    assert erro.value.codigo == "linha_nao_encontrada"
    assert not sessao.sql_executado(T_GRAVAR)


def test_a_reacao_usa_A_MESMA_clausula_de_publico_que_o_quadro():
    """⛔ Duas definicoes de *"aparece em publico"* divergiriam.

    ⚠️ E o proprio comentario da consulta do quadro ja avisava disso: **a mais
    frouxa mandaria**. Reagir a quem se escondeu gravaria uma contagem invisivel,
    que reapareceria no dia em que a pessoa voltasse a se mostrar.

    ⚠️ **O caso compara a CONSTANTE dentro das duas consultas**, e ⛔ nao dois
    textos parecidos: e a constante que impede a copia de existir.
    """
    from api.desafios.reacoes import SQL_RESOLUCAO_PUBLICA

    assert CLAUSULA_APARECE_EM_PUBLICO in SQL_RESOLUCAO_PUBLICA
    assert CLAUSULA_APARECE_EM_PUBLICO in SQL_LINHAS_DE_GENTE


# ═══════════════════════════════════════════════════════════════════════════
# 5. A reacao FICA - o `commit` (relato do dono, 26/09/2026)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠️ Ate 26/09/2026 nenhum dos dois verbos confirmava a transacao, e a sessao da
# requisicao DESFAZ o que ⛔ foi confirmado ao fechar. A tela via a reacao (a
# contagem era lida dentro da mesma transacao) e, ao reabrir o quadro, ela tinha
# sumido - o banco `des` tinha zero reacoes. Os casos acima mediam o SQL e a
# resposta, e passavam: ⛔ nenhum perguntava se a gravacao ficava.


def _posicao(sessao, trecho: str) -> int:
    """Em que ponto da `linha_do_tempo` da sessao falsa aconteceu [trecho].

    ⚠️ A linha do tempo junta consultas e `commit` na ordem em que vieram - e e
    ela que separa *"confirmou"* de *"confirmou antes de montar a resposta"*: a
    contagem que volta a tela tem de ser a que o proximo quadro vai ler.
    """
    return next(i for i, item in enumerate(sessao.linha_do_tempo) if trecho in item)


@pytest.mark.asyncio
async def test_reagir_CONFIRMA_a_transacao_antes_de_responder():
    """⚠️ Um `commit`, depois do `INSERT` e ANTES da contagem da resposta."""
    servico, sessao = _servico()

    await servico.reagir(
        id_desafio=ID_DESAFIO,
        id_usuario=EU,
        id_jogador=A_ANA,
        co_tipo_reacao="fogo",
        agora=AGORA,
    )

    assert sessao.commits == 1
    assert (
        _posicao(sessao, T_GRAVAR)
        < _posicao(sessao, "commit")
        < _posicao(sessao, T_CONTAGEM)
    )


@pytest.mark.asyncio
async def test_desfazer_tambem_CONFIRMA_a_transacao():
    """⚠️ Sem o `commit`, desfazer tambem ⛔ ficava - a reacao voltava."""
    servico, sessao = _servico(**{T_CONTAGEM: [], T_MINHA: []})

    await servico.desfazer(id_desafio=ID_DESAFIO, id_usuario=EU, id_jogador=A_ANA)

    assert sessao.commits == 1
    assert (
        _posicao(sessao, T_APAGAR)
        < _posicao(sessao, "commit")
        < _posicao(sessao, T_CONTAGEM)
    )


@pytest.mark.asyncio
async def test_pedido_recusado_NAO_confirma_nada():
    """⛔ Uma guarda que recusa ⛔ chega ao `commit` - ⛔ ha o que confirmar."""
    servico, sessao = _servico(**{T_RESOLUCAO: []})

    with pytest.raises(LinhaSemResolucao):
        await servico.reagir(
            id_desafio=ID_DESAFIO,
            id_usuario=EU,
            id_jogador=A_ANA,
            co_tipo_reacao="fogo",
            agora=AGORA,
        )

    assert sessao.commits == 0
