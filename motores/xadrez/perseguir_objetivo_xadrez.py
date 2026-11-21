"""Quem PERSEGUE o objetivo do desafio no xadrez, com nivel (spec 012, T076).

═══════════════════════════════════════════════════════════════════════════
POR QUE ESTE MODULO EXISTE (`DECISOES-do-dono.md` §8zzzz57)
═══════════════════════════════════════════════════════════════════════════

Em dez dos onze tipos do xadrez, vencer a partida NAO e o objetivo: comer duas
pecas com a espia, passar oito lances sem perder um peao, trocar o bispo pelo
cavalo. Alguns pedem o contrario do que um bom jogador faz (o motor troca pecas
a vontade, e o `xadrez_nao_perder` proibe perder qualquer uma). Medir esses
tipos com o personagem jogando para vencer mede o cumprimento POR ACASO, e foi
isso que custou dias no Quatro em Linha. Por isso o perseguidor nasce antes da
primeira regua (T077), e so o `xadrez_dar_mate` fica com o motor que vence.

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUMA REGRA DE XADREZ AQUI
═══════════════════════════════════════════════════════════════════════════

Quem diz o que e legal, o que foi comido, quem deu xeque, onde a espia esta e
se a partida acabou e o MOTOR em Rust, pela porta que ja existe (`estado`,
`aplicar` com as marcas, `radar`, `buscar`; `contracts/motor-xadrez.md` §2).
Quem diz se o objetivo foi cumprido e o MEDIDOR DE PRODUCAO (`feitos_xadrez`) com
o avaliador da linha de chegada, os mesmos que julgam a pessoa. Este modulo so
ESCOLHE entre os lances, em tres passos:

  (a) o lance que cumpre o objetivo AGORA, se houver, e jogado;
  (b) saem os lances que perdem a partida (os que a encerram sem o objetivo, e
      os que deixam ao adversario um xeque-mate no lance seguinte) e os que
      violam uma clausula que nao volta atras (a espia comivel no lance
      seguinte, a peca do `xadrez_nao_perder` comivel, um xeque ao alcance do
      adversario no `xadrez_sem_levar_xeque`);
  (c) entre os que sobram, a NOTA DO OBJETIVO, uma por tipo. Empate de nota:
      o lance do nivel, se estiver entre os empatados; depois, o que deixa
      MENOS pecas comiveis (pelo Radar); por fim, o sorteio da semente.

Se o filtro (b) tirar todos, volta-se ao que havia antes dele: melhor jogar um
lance ruim do que nao ter lance.

⚠️ **O nivel e uma MISTURA, e nao um segundo motor** (a v3 do Quatro): com a
probabilidade [PROBABILIDADE_DE_PERSEGUIR] do nivel, o lance e o de perseguir;
senao, e o lance do personagem, CRU, com os erros que o nivel ja tem. Filtrar
tambem esse lance daria competencia a Cacau (a regua do Quatro de 21/10/2026
viu a Cacau resolver 0,40 a 0,80, com teto 0,20).

⛔ **Nada disto entra em `gerador.SOLUCIONADOR_POR_TIPO` antes da medicao
pareada e com controle** (T076a, `scripts/medir_perseguir_vs_vencer_xadrez.py`):
um perseguidor que vence MENOS que o Magno quando o objetivo e so vencer nao
mede o objetivo dificil, mede a propria incompetencia.

═══════════════════════════════════════════════════════════════════════════
⚠️ AS DECISOES TECNICAS DA T076 (historico do backend, "2026-11-21")
═══════════════════════════════════════════════════════════════════════════

1. **"Perde a partida" = o xeque-mate no lance seguinte**, e nao uma prova mais
   funda. A pergunta e o `buscar` da Cacau depois do candidato: o mate em um
   sai em todo nivel antes de qualquer sorteio (`acao: mate_em_um`), e a busca
   da Cacau e a mais barata (~1,5 ms). Uma prova pela busca do Magno custaria
   ~117 ms por candidato, ~4 s por lance.
2. **No `xadrez_nao_perder` o filtro olha a peca DO DESAFIO** (a classe da
   clausula `pecas_perdidas_<peca>`), e nao qualquer peca: e o que a clausula
   mede. As outras pecas entram so no desempate (o que deixa menos pecas
   comiveis). Sem candidato, fica o lance que deixa MENOS pecas daquela classe
   comiveis.
3. **No `xadrez_espia_alvo`, "a espia ataca o alvo"** e perguntado ao motor com
   a vez trocada no FEN (`fen_xadrez.fen_com_a_vez_trocada`): a espia tem lance
   para a casa do alvo? O Radar diria so que ALGUMA peca o ataca. Quando o
   motor recusa a posicao trocada (o adversario esta em xeque), a nota e 0.
4. **A promocao do peao e sempre a dama** nos candidatos: as outras tres
   multiplicariam as perguntas por lance de peao na 7a fileira, e nenhum dos
   onze objetivos pede outra peca.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from motores.nucleo.chegada import LinhaDeChegada, avaliar
from motores.nucleo.medidor_por_fita import prefixo_da_janela
from motores.nucleo.papeis import NivelDeMotor
from motores.xadrez import feitos_xadrez
from motores.xadrez.fen_xadrez import fen_com_a_vez_trocada, outra_cor, pecas_do_fen
from motores.xadrez.jogador_xadrez import JogadorXadrez, MotorXadrezRecusou

#: Com que frequencia cada nivel joga o lance que persegue o objetivo (o resto
#: e o lance do proprio nivel no motor). ⚠️ Palpite de partida, o mesmo do
#: Quatro (`perseguir_objetivo_quatro.PROBABILIDADE_DE_PERSEGUIR`), a medir na
#: T076a. Escrito aqui, e nao importado de la: o numero de um jogo nao e o do
#: outro, e mudar o do Quatro nao pode mudar o xadrez calado.
PROBABILIDADE_DE_PERSEGUIR: dict[NivelDeMotor, float] = {
    NivelDeMotor.CACAU: 0.25,
    NivelDeMotor.PITA: 0.50,
    NivelDeMotor.TEX: 0.80,
    NivelDeMotor.SAGAZ: 1.00,
}

#: O nivel que responde "o adversario da mate no lance seguinte?". Qualquer um
#: responderia igual (o mate em um sai antes do sorteio); a Cacau e a busca mais
#: barata.
NIVEL_QUE_VE_O_MATE = NivelDeMotor.CACAU

#: A semente desse `buscar`. ⚠️ Fixa de proposito: o mate em um nao depende de
#: sorteio, e uma semente que mudasse com o lance nao mudaria a resposta.
SEMENTE_DO_MATE = 1

#: A letra da promocao dos candidatos (ver o item 4 do topo).
PROMOCAO_DOS_CANDIDATOS = "q"

#: As quatro letras da promocao, para quem precisa de TODOS os lances do
#: adversario (o filtro do `xadrez_sem_levar_xeque`: um cavalo promovido pode
#: dar o xeque que a dama nao da).
TODAS_AS_PROMOCOES = ("q", "r", "b", "n")

#: Os cinco tipos da espia: o filtro deles tira o lance que a deixa comivel.
TIPOS_DA_ESPIA: frozenset[str] = frozenset(
    {
        "xadrez_espia_comer",
        "xadrez_espia_proteger",
        "xadrez_espia_atravessar",
        "xadrez_espia_xeque",
        "xadrez_espia_alvo",
    }
)

#: O tipo de CONTROLE da T076a, que so existe aqui (nao e tipo do banco): o
#: objetivo e so vencer. Sem nota e sem filtro proprio, o perseguidor dele e o
#: lance do nivel com os passos (a) e (b) - e e isso que o controle mede: se os
#: dois passos nao o fazem jogar PIOR que o motor.
TIPO_DE_CONTROLE = "xadrez_vencer"

#: Os tipos que o perseguidor sabe perseguir: os dez em que vencer nao e o
#: objetivo, mais o controle. ⚠️ O `xadrez_dar_mate` fica de fora de proposito
#: (`DECISOES-do-dono.md` §8zzzz57): quem o resolve e o motor que vence.
TIPOS_DO_PERSEGUIDOR: frozenset[str] = TIPOS_DA_ESPIA | frozenset(
    {
        "xadrez_comer_com",
        "xadrez_nao_perder",
        "xadrez_xeques_seguidos",
        "xadrez_sem_levar_xeque",
        "xadrez_troca",
        TIPO_DE_CONTROLE,
    }
)

#: A pessoa, no vocabulario da fita (`+1`), como nos vetores do juiz: e quem
#: tem a vez na posicao publicada, e o adversario e `-1`.
VEZ_DA_PESSOA = 1

#: O prefixo da medida do `xadrez_nao_perder` (`pecas_perdidas_<peca>`).
PREFIXO_DA_PECA_PROTEGIDA = "pecas_perdidas_"


@dataclass(frozen=True)
class DesafioXadrez:
    """O que o perseguidor precisa saber do desafio, uma vez por partida.

    Atributos:
        co_tipo: o tipo do desafio (escolhe a nota e o filtro).
        posicao: a `js_posicao_inicial` (o FEN, a cor da pessoa, as marcas, as
            classes, o par da troca).
        chegada: a linha de chegada, ja validada.
    """

    co_tipo: str
    posicao: Mapping[str, Any]
    chegada: LinhaDeChegada

    @property
    def modalidade(self) -> str:
        return str(self.posicao["modalidade"])

    @property
    def fen(self) -> str:
        return str(self.posicao["fen"])

    @property
    def cor_da_pessoa(self) -> str:
        return feitos_xadrez.cor_da_pessoa(self.posicao)

    @property
    def cor_do_adversario(self) -> str:
        return outra_cor(self.cor_da_pessoa)

    @property
    def peca_protegida(self) -> str | None:
        """A classe do `xadrez_nao_perder`, lida da CLAUSULA da chegada.

        ⚠️ Da chegada, e nao dos parametros: e ela que o juiz usa, e o
        perseguidor tem de proteger exatamente a peca que sera julgada.
        """
        for chave in self.chegada.chaves_de_medida:
            if chave.startswith(PREFIXO_DA_PECA_PROTEGIDA):
                return chave[len(PREFIXO_DA_PECA_PROTEGIDA):]
        return None


def desafio_de(
    co_tipo: str, posicao: Mapping[str, Any], js_chegada: Mapping[str, Any]
) -> DesafioXadrez:
    """Monta o [DesafioXadrez].

    Raises:
        ValueError: tipo que o perseguidor nao persegue (o mate, ou um tipo que
            nao e do xadrez). ⚠️ Falhar alto: um perseguidor sem nota para o
            tipo jogaria o lance do nivel, e mediria o tipo errado calado.
    """
    if co_tipo not in TIPOS_DO_PERSEGUIDOR:
        raise ValueError(
            f"o perseguidor do xadrez nao persegue {co_tipo!r}; os dele sao "
            f"{sorted(TIPOS_DO_PERSEGUIDOR)} (o mate fica com o motor que vence)"
        )
    return DesafioXadrez(
        co_tipo=co_tipo, posicao=posicao, chegada=LinhaDeChegada.de_dado(js_chegada)
    )


# ─────────────────────────────────────────────────────────────────────────────
# O que o motor diz de um lance
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LanceExaminado:
    """Um lance candidato da pessoa, com tudo o que o motor e o medidor disseram.

    Atributos:
        lance: o lance (`e2e4`).
        passo: `{"lance", "fatos", "marcas"}`, o formato de
            `feitos_xadrez.reproduzir`.
        fen_depois: a posicao depois do lance.
        estado_depois: o `estado` do motor depois do lance (a vez e do
            adversario: os lances legais sao os DELE).
        cumpre: o lance cumpre o objetivo (passo a).
        acaba: o lance encerra a partida (os fatos trazem `fim`).
        comiveis: as casas das pecas da pessoa que o adversario pode comer no
            lance seguinte (o Radar).
    """

    lance: str
    passo: dict[str, Any]
    fen_depois: str
    estado_depois: dict[str, Any]
    cumpre: bool
    acaba: bool
    comiveis: tuple[str, ...]

    @property
    def fatos(self) -> Mapping[str, Any]:
        return self.passo["fatos"]

    def marca(self, nome: str) -> Mapping[str, Any] | None:
        """O que o motor disse da marca [nome] depois do lance, ou `None`."""
        marca = (self.passo.get("marcas") or {}).get(nome)
        return marca if isinstance(marca, Mapping) else None


def lances_do_estado(estado: Mapping[str, Any], promocoes: Sequence[str]) -> list[str]:
    """Os lances legais do [estado] do motor, na notacao do `aplicar`, ordenados.

    O motor agrupa os destinos por casa de origem (`lances_legais`) e lista a
    parte as origens cujo destino pede a escolha da peca (`promocoes`): ali cada
    destino vira um lance por letra de [promocoes].
    """
    pede_peca = set(estado.get("promocoes") or ())
    lances: list[str] = []
    for origem, destinos in (estado.get("lances_legais") or {}).items():
        for destino in destinos:
            if origem in pede_peca:
                lances.extend(f"{origem}{destino}{letra}" for letra in promocoes)
            else:
                lances.append(f"{origem}{destino}")
    # Ordenados: a ordem do dicionario e a do motor, estavel, mas a ordem
    # explicita deixa a reprodutibilidade a vista de quem le.
    return sorted(lances)


def _marcas_agora(
    desafio: DesafioXadrez, passos: Sequence[Mapping[str, Any]]
) -> dict[str, str | None]:
    """As casas das pecas marcadas AGORA: as da posicao, ou as do ultimo passo."""
    if not passos:
        return feitos_xadrez.marcas_iniciais(desafio.posicao)
    return {nome: marca["casa"] for nome, marca in (passos[-1].get("marcas") or {}).items()}


def _fita_do_juiz(lances: Sequence[str]) -> list[dict[str, Any]]:
    """A fita no vocabulario do log: a pessoa e `+1`, e a vez alterna."""
    return [
        {"n": n, "jogador": VEZ_DA_PESSOA if n % 2 == 1 else -VEZ_DA_PESSOA, "lance": lance}
        for n, lance in enumerate(lances, start=1)
    ]


def cumpre(
    desafio: DesafioXadrez, lances: Sequence[str], passos: Sequence[Mapping[str, Any]]
) -> bool:
    """O ULTIMO lance de [lances] (que e da pessoa) cumpre o objetivo?

    E a pergunta que o juiz (`nucleo.julgar`) faz a cada lance da pessoa, so que
    para o ultimo: o lance tem de estar dentro da janela (`prefixo_da_janela`),
    e a chegada tem de valer sobre as medidas do medidor de producao. ⚠️ So o
    ultimo, porque quem chama joga ate o primeiro que cumpre: os anteriores ja
    nao cumpriram.
    """
    fita = _fita_do_juiz(lances)
    if prefixo_da_janela(fita, desafio.chegada, jogador=VEZ_DA_PESSOA) < len(fita):
        # A janela fechou antes deste lance: ele nao conta mais.
        return False
    medidas = feitos_xadrez.medir(desafio.posicao, passos)
    return avaliar(desafio.chegada, medidas, {}, jogador=VEZ_DA_PESSOA)


def examinar(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    passos: Sequence[Mapping[str, Any]],
    lance: str,
) -> LanceExaminado:
    """Pergunta ao motor o que [lance] faz, e ao medidor se ele cumpre.

    Duas perguntas ao motor: o `aplicar` com as marcas (os fatos, as marcas, o
    FEN e o estado de depois) e o `radar` do lado da pessoa (o que ficou
    comivel). E uma conta do medidor, sem motor.
    """
    resposta = motor.aplicar(
        modalidade=desafio.modalidade,
        fen_inicial=desafio.fen,
        lances=list(fita),
        lance=lance,
        marcas=_marcas_agora(desafio, passos),
    )
    passo = {"lance": lance, "fatos": resposta["fatos"], "marcas": resposta["marcas"]}
    depois = list(fita) + [lance]
    comiveis = motor.radar(
        modalidade=desafio.modalidade,
        fen_inicial=desafio.fen,
        lances=depois,
        lado=desafio.cor_da_pessoa,
    )
    return LanceExaminado(
        lance=lance,
        passo=passo,
        fen_depois=resposta["fen_depois"],
        estado_depois=resposta["estado"],
        cumpre=cumpre(desafio, depois, list(passos) + [passo]),
        acaba=resposta["fatos"].get("fim") is not None,
        comiveis=tuple(comiveis),
    )


# ─────────────────────────────────────────────────────────────────────────────
# O passo (b): o que perde a partida, e o que viola o que nao volta atras
# ─────────────────────────────────────────────────────────────────────────────


def adversario_da_mate(
    motor: JogadorXadrez, desafio: DesafioXadrez, lances: Sequence[str]
) -> bool:
    """Depois de [lances], o adversario tem um xeque-mate em um lance?

    O `buscar` da Cacau (ver [NIVEL_QUE_VE_O_MATE]) devolve o mate em um antes
    de qualquer sorteio; os fatos do lance dele dizem se ele termina a partida a
    favor do adversario.
    """
    resposta = motor.buscar(
        modalidade=desafio.modalidade,
        fen_inicial=desafio.fen,
        lances=list(lances),
        nivel=NIVEL_QUE_VE_O_MATE,
        semente=SEMENTE_DO_MATE,
    )
    fim = (resposta.get("fatos") or {}).get("fim")
    return isinstance(fim, Mapping) and fim.get("vencedor") == desafio.cor_do_adversario


def adversario_tem_xeque(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    examinado: LanceExaminado,
) -> bool:
    """Depois do lance [examinado], o adversario tem um lance que da xeque?

    Uma pergunta ao motor por lance do adversario (o `aplicar` diz quem deu
    xeque, `xeque_por`), parando no primeiro que da. ⚠️ Com TODAS as promocoes:
    o cavalo promovido pode dar o xeque que a dama nao da.
    """
    depois = list(fita) + [examinado.lance]
    for resposta_dele in lances_do_estado(examinado.estado_depois, TODAS_AS_PROMOCOES):
        resposta = motor.aplicar(
            modalidade=desafio.modalidade,
            fen_inicial=desafio.fen,
            lances=depois,
            lance=resposta_dele,
        )
        if resposta["fatos"].get("xeque_por"):
            return True
    return False


def _classes_comiveis(examinado: LanceExaminado, peca: str | None) -> int:
    """Quantas pecas da classe [peca] da pessoa o adversario pode comer depois."""
    if peca is None:
        return 0
    tabela = pecas_do_fen(examinado.fen_depois)
    return sum(1 for casa in examinado.comiveis if tabela[casa].peca == peca)


def filtrar(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    examinados: Sequence[LanceExaminado],
) -> list[LanceExaminado]:
    """O passo (b): tira o que perde a partida e o que viola o que nao volta atras.

    Cada filtro que tiraria TODOS os lances e desfeito (volta-se ao que havia
    antes dele): melhor jogar um lance ruim do que nao ter lance.
    """
    depois_de = lambda e: list(fita) + [e.lance]  # noqa: E731 (uma linha so)

    # O lance que encerra a partida sem o objetivo (o afogamento, a repetição,
    # o proprio mate num tipo que nao pede vitoria) perde o desafio.
    vivos = [e for e in examinados if not e.acaba] or list(examinados)
    # O lance que deixa ao adversario um xeque-mate no lance seguinte.
    vivos = [e for e in vivos if not adversario_da_mate(motor, desafio, depois_de(e))] or vivos

    tipo = desafio.co_tipo
    if tipo in TIPOS_DA_ESPIA:
        # A espia comivel no lance seguinte: comida, o desafio acaba.
        seguros = []
        for examinado in vivos:
            espia = examinado.marca(feitos_xadrez.MARCA_DA_ESPIA)
            casa = espia.get("casa") if espia is not None else None
            if casa is None or casa not in examinado.comiveis:
                seguros.append(examinado)
        return seguros or vivos
    if tipo == "xadrez_nao_perder":
        # A peca DO DESAFIO comivel no lance seguinte (decisao 2 do topo).
        # Sem candidato: os que deixam MENOS pecas daquela classe comiveis.
        peca = desafio.peca_protegida
        contagem = {e.lance: _classes_comiveis(e, peca) for e in vivos}
        menor = min(contagem.values(), default=0)
        return [e for e in vivos if contagem[e.lance] == menor]
    if tipo == "xadrez_sem_levar_xeque":
        # Um xeque ao alcance do adversario: recebido, o desafio acaba.
        return [e for e in vivos if not adversario_tem_xeque(motor, desafio, fita, e)] or vivos
    return vivos


# ─────────────────────────────────────────────────────────────────────────────
# O passo (c): a nota do objetivo, uma por tipo
# ─────────────────────────────────────────────────────────────────────────────


def _espia_ataca_o_alvo(
    motor: JogadorXadrez, desafio: DesafioXadrez, examinado: LanceExaminado
) -> bool:
    """Depois do lance, a espia alcancaria o alvo se jogasse de novo?

    A pergunta vai ao motor com a vez trocada (decisao 3 do topo). Quando ele
    recusa a posicao trocada (`fen_invalido`: o adversario esta em xeque), a
    resposta e "nao".
    """
    espia = examinado.marca(feitos_xadrez.MARCA_DA_ESPIA)
    alvo = examinado.marca(feitos_xadrez.MARCA_DO_ALVO)
    casa_da_espia = espia.get("casa") if espia else None
    casa_do_alvo = alvo.get("casa") if alvo else None
    if casa_da_espia is None or casa_do_alvo is None:
        return False
    try:
        estado = motor.estado(
            modalidade=desafio.modalidade,
            fen_inicial=fen_com_a_vez_trocada(examinado.fen_depois),
            lances=[],
        )
    except MotorXadrezRecusou:
        return False
    return casa_do_alvo in (estado.get("lances_legais") or {}).get(casa_da_espia, ())


def _oferece_a_troca(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    examinado: LanceExaminado,
) -> bool:
    """A ordem 1 da troca: depois do lance, a peca `dele` come uma `minha`, e a
    pessoa retoma na mesma casa?

    Os lances do adversario vem do `estado` de depois; a peca em cada casa, do
    FEN lido como tabela; a retomada, do `estado` depois da captura dele (a
    pessoa tem lance para aquela casa?).
    """
    troca = desafio.posicao.get("troca") or {}
    minha, dele = troca.get("minha"), troca.get("dele")
    tabela = pecas_do_fen(examinado.fen_depois)
    depois = list(fita) + [examinado.lance]
    for origem, destinos in (examinado.estado_depois.get("lances_legais") or {}).items():
        atacante = tabela.get(origem)
        if atacante is None or atacante.peca != dele:
            continue
        for destino in destinos:
            alvo = tabela.get(destino)
            if alvo is None or alvo.cor != desafio.cor_da_pessoa or alvo.peca != minha:
                continue
            resposta = motor.aplicar(
                modalidade=desafio.modalidade,
                fen_inicial=desafio.fen,
                lances=depois,
                lance=f"{origem}{destino}",
            )
            retomadas = resposta["estado"].get("lances_legais") or {}
            if any(destino in casas for casas in retomadas.values()):
                return True
    return False


def nota_do_objetivo(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    examinado: LanceExaminado,
) -> float:
    """O quanto o lance [examinado] aproxima a pessoa do objetivo do tipo.

    Os tipos sem nota (`xadrez_espia_proteger`, `xadrez_nao_perder`,
    `xadrez_sem_levar_xeque` e o controle) devolvem 0: neles o lance e o do
    nivel, so com o filtro.
    """
    tipo = desafio.co_tipo
    fatos = examinado.fatos
    espia = examinado.marca(feitos_xadrez.MARCA_DA_ESPIA)
    if tipo == "xadrez_espia_comer":
        return 1.0 if espia is not None and espia.get("comeu") else 0.0
    if tipo == "xadrez_espia_atravessar":
        casa = espia.get("casa") if espia else None
        if casa is None:
            return 0.0
        # Quantas fileiras faltam ate a ultima do lado da pessoa (geometria do
        # nome da casa, como o marco do medidor): menos e melhor.
        ultima = int(feitos_xadrez.ULTIMA_FILEIRA[desafio.cor_da_pessoa])
        return -abs(ultima - int(casa[-1]))
    if tipo == "xadrez_espia_xeque":
        # `deu_xeque` inclui o xeque descoberto (RF-XDR-195).
        return 1.0 if espia is not None and espia.get("deu_xeque") else 0.0
    if tipo == "xadrez_espia_alvo":
        # Comer o alvo cumpre (passo a); aqui, deixar a espia atacando-o.
        return 1.0 if _espia_ataca_o_alvo(motor, desafio, examinado) else 0.0
    if tipo == "xadrez_comer_com":
        classes = desafio.posicao.get("classes") or {}
        comida = fatos.get("comida")
        return (
            1.0
            if isinstance(comida, Mapping)
            and fatos.get("peca_movida") == classes.get("come")
            and classes.get("comida") in (None, comida.get("peca"))
            else 0.0
        )
    if tipo == "xadrez_xeques_seguidos":
        return 1.0 if fatos.get("xeque_por") else 0.0
    if tipo == "xadrez_troca":
        # A ordem 2 (comer a `dele` com a `minha`) cumpre: e o passo (a).
        return 1.0 if _oferece_a_troca(motor, desafio, fita, examinado) else 0.0
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# O lance
# ─────────────────────────────────────────────────────────────────────────────


def examinar_todos(
    motor: JogadorXadrez, desafio: DesafioXadrez, fita: Sequence[str]
) -> tuple[list[dict[str, Any]], list[LanceExaminado]]:
    """Reproduz a [fita] e examina cada lance legal da pessoa.

    Returns:
        Os passos da fita (para o medidor) e os lances examinados, na ordem.

    Raises:
        ValueError: a partida ja acabou (nao ha lance), como o motor quando se
            pede um lance depois do fim.
    """
    passos = feitos_xadrez.reproduzir(desafio.posicao, list(fita), motor=motor)
    estado = motor.estado(modalidade=desafio.modalidade, fen_inicial=desafio.fen, lances=list(fita))
    lances = lances_do_estado(estado, (PROMOCAO_DOS_CANDIDATOS,))
    if not lances:
        raise ValueError("a partida acabou: a pessoa nao tem lance")
    return passos, [examinar(motor, desafio, fita, passos, lance) for lance in lances]


def lance_de_quem_persegue(
    motor: JogadorXadrez,
    desafio: DesafioXadrez,
    fita: Sequence[str],
    *,
    nivel: NivelDeMotor,
    sorteio: random.Random,
    lance_do_nivel: Callable[[], str],
) -> str:
    """O lance de quem persegue o objetivo, no [nivel].

    Args:
        motor: o executavel (o desta thread, na regua).
        desafio: o tipo, a posicao publicada e a chegada.
        fita: os lances desde a posicao publicada, dos dois lados; a vez e da
            pessoa.
        nivel: o degrau do personagem que esta resolvendo.
        sorteio: o `random.Random` DESTE lance (semeado pela semente do lance:
            a mesma partida a cada execucao).
        lance_do_nivel: devolve o lance que o motor daria neste nivel. ⚠️ Uma
            funcao, e nao o lance: so e chamada quando precisa (a mistura, ou o
            desempate), e no Magno custa ~117 ms.

    Raises:
        ValueError: a partida acabou.
    """
    # ── A mistura do nivel: o lance do proprio nivel, CRU ───────────────────
    if sorteio.random() >= PROBABILIDADE_DE_PERSEGUIR[nivel]:
        return lance_do_nivel()

    _, examinados = examinar_todos(motor, desafio, fita)

    # ── (a) O lance que cumpre agora ────────────────────────────────────────
    for examinado in examinados:
        if examinado.cumpre:
            return examinado.lance

    # ── (b) Fora o que perde a partida e o que nao volta atras ──────────────
    restantes = filtrar(motor, desafio, fita, examinados)
    if len(restantes) == 1:
        return restantes[0].lance

    # ── (c) A nota, e o desempate ───────────────────────────────────────────
    notas = {e.lance: nota_do_objetivo(motor, desafio, fita, e) for e in restantes}
    melhor = max(notas.values())
    empatados = [e for e in restantes if notas[e.lance] == melhor]
    if len(empatados) == 1:
        return empatados[0].lance
    # O lance do nivel, se estiver entre os empatados: sem nota que o separe,
    # quem joga e o personagem (e o "sem candidato, o lance do nivel").
    do_nivel = lance_do_nivel()
    if any(e.lance == do_nivel for e in empatados):
        return do_nivel
    # Depois, o que deixa menos pecas comiveis; por fim, o sorteio da semente.
    menos = min(len(e.comiveis) for e in empatados)
    return sorteio.choice(sorted(e.lance for e in empatados if len(e.comiveis) == menos))
