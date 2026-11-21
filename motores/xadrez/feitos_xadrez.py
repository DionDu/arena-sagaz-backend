"""Os FEITOS do xadrez: as medidas de uma tentativa de desafio (spec 012, T069).

═══════════════════════════════════════════════════════════════════════════
O QUE ESTE ARQUIVO MEDE, E DE QUEM
═══════════════════════════════════════════════════════════════════════════

Números lidos dos FATOS de cada lance, que outros transformam em objetivo
cumprido e em XP. ⚠️ Aqui não há XP nenhum: medida é medida, e quem converte é
a coleção (`job/editorial.py`, o extrato de XP do desafio).

A **pessoa** é quem tem a vez na posição publicada (`contracts/desafio-xadrez.md`
§1: o FEN vem "com a vez da pessoa", e a cor dela em `cor_da_pessoa`). No
xadrez a vez sempre alterna, então os lances de índice par da fita (0, 2,
4...) são dela, e os ímpares, do adversário. ⚠️ Isso não é regra calculada
aqui: a reprodução confere, pelo motor, que a vez no início é mesmo a da
pessoa, e recusa a posição quando não é.

As 22 medidas (as chaves são as do catálogo de feitos, 60 a 78, mais as três
universais), uma frase cada:

- `lances_do_jogador`, `vitoria`, `empate`: os lances da pessoa, e o fim que o
  motor deu (`fatos.fim`);
- `pecas_comidas_<tipo>` / `pecas_perdidas_<tipo>`, para peão, cavalo, bispo,
  torre e dama: as peças do adversário que a pessoa comeu, e as dela que o
  adversário comeu, contadas pelo fato `comida` (que no en passant já traz o
  peão certo);
- `maior_sequencia_de_xeques`: o maior número de lances SEGUIDOS da pessoa que
  deram xeque. O lance do adversário no meio não interrompe; um lance dela sem
  xeque, sim. ⚠️ É a regra de `medidasDaPartidaXadrez` do app
  (`lib/modulos/jogos/xadrez/logica/feitos_xadrez.dart`), escrita igual;
- `xeques_recebidos`: os lances do adversário que deixaram o rei da pessoa em
  xeque (`xeque_por` não vazio);
- `capturas_da_espia` / `xeques_da_espia`: os lances da pessoa em que UMA
  espiã comeu, ou deu xeque (o `deu_xeque` do motor, que inclui o xeque
  descoberto: RF-XDR-195);
- `espia_comida`: 1 quando uma espiã saiu do tabuleiro (a casa dela virou
  `null` na resposta do motor), e fica 1;
- `espia_na_ultima_fileira`: marco, 1 quando uma espiã esteve na última fileira
  do lado da pessoa (a 8ª para as brancas, a 1ª para as pretas), e fica 1;
- `alvo_comido_pela_espia`: marco, 1 quando o alvo saiu do tabuleiro num lance
  em que uma espiã comeu (um lance come uma peça só: se o alvo sumiu nele, foi
  ela quem o comeu);
- `capturas_da_classe_marcada`: os lances da pessoa em que a peça movida é a
  classe `come` dos parâmetros e a comida é a classe `comida` (sem `comida`,
  qualquer peça);
- `trocas_feitas`: as trocas do par `troca` (`minha` × `dele`), nas duas ordens
  de RF-XDR-201, contadas no lance da PESSOA que a fecha (ver [_fechou_troca]).

⚠️ **As espiãs podem ser DUAS** (o `xadrez_duas_espias`, `DECISOES-do-dono.md`
§8zzzz64, 21/11/2026): as marcas `espia` e `espia2` ([MARCAS_DAS_ESPIAS]). As
cinco medidas da espiã valem para qualquer uma delas: as capturas somam as das
duas ("vale o total"), e `espia_comida` fica 1 quando qualquer uma sai. Com uma
espiã só (os outros cinco tipos), a conta é exatamente a de antes: a marca
`espia2` não existe, e o laço por ela não acha nada.

⚠️ **As 19 só crescem ao longo da fita** (a coluna "evolução" da
`data-model.md` §3.2): é o que deixa o juiz fechar como não cumprido o desafio
cuja cláusula `espia_comida ≤ 0` foi violada, para sempre (RF-XDR-191).

═══════════════════════════════════════════════════════════════════════════
⛔ NENHUMA REGRA DE XADREZ AQUI
═══════════════════════════════════════════════════════════════════════════

Quem diz o que cada lance comeu, se deu xeque, onde a espiã está depois do
roque e da promoção, e se a partida acabou, é o MOTOR em Rust (os fatos e as
marcas da operação `aplicar`, `contracts/motor-xadrez.md` §2.2). Este arquivo
só lê o que ele escreveu, e conta. A única coisa que ele lê de uma casa é o
número da fileira (o último caractere de `"f8"`), para o marco da última
fileira: é geometria do nome da casa, e não regra de como a peça anda.

As duas metades são separadas de propósito:

1. [reproduzir] pergunta ao executável (é a única que precisa dele) e devolve
   os PASSOS: para cada lance, os fatos e as marcas depois dele;
2. [medir] é uma função pura sobre os passos. É ela que os vetores do juiz
   (`contratos/vetores-juiz-xadrez.json`) conferem sem o executável, e é a
   mesma conta que o medidor do app faz (T070), sobre os mesmos fatos.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from motores.xadrez import contrato_xadrez
from motores.xadrez.jogador_xadrez import JogadorXadrez, jogador_compartilhado

#: Os tipos de peça que podem ser comidos, pelo nome do motor, na ordem do
#: catálogo (`pecas_comidas_peao` ... `pecas_comidas_dama`). O rei nunca sai.
#: É a lista `tiposComiveisXadrez` do app.
TIPOS_COMIVEIS: tuple[str, ...] = ("peao", "cavalo", "bispo", "torre", "dama")

#: As duas cores, no vocabulário do motor e de `cor_da_pessoa`.
CORES: frozenset[str] = frozenset({"branca", "preta"})

#: A última fileira de cada cor: onde a espiã "chega ao outro lado".
ULTIMA_FILEIRA: dict[str, str] = {"branca": "8", "preta": "1"}

#: O nome das marcas do desafio (`js_posicao_inicial.marcas`).
MARCA_DA_ESPIA = "espia"
MARCA_DO_ALVO = "alvo"
#: A segunda espiã, só no `xadrez_duas_espias` (§8zzzz64). ⚠️ O motor segue
#: qualquer marca pelo nome (`fatos::seguir_marcas`): a segunda não muda o crate.
MARCA_DA_SEGUNDA_ESPIA = "espia2"
#: As marcas que contam como espiã, na ordem: a 1ª e a 2ª. É por esta tupla que
#: as medidas da espiã, o perseguidor e a prova procuram as espiãs.
MARCAS_DAS_ESPIAS: tuple[str, ...] = (MARCA_DA_ESPIA, MARCA_DA_SEGUNDA_ESPIA)

#: As chaves que [medir] devolve, na ordem do catálogo. O teste confere que as
#: 19 do xadrez são exatamente as do manifesto `contratos/catalogo_feitos.json`.
CHAVES_DAS_MEDIDAS: tuple[str, ...] = (
    "vitoria",
    "empate",
    "lances_do_jogador",
    *(f"pecas_comidas_{tipo}" for tipo in TIPOS_COMIVEIS),
    *(f"pecas_perdidas_{tipo}" for tipo in TIPOS_COMIVEIS),
    "capturas_da_espia",
    "xeques_da_espia",
    "espia_comida",
    "espia_na_ultima_fileira",
    "alvo_comido_pela_espia",
    "capturas_da_classe_marcada",
    "maior_sequencia_de_xeques",
    "xeques_recebidos",
    "trocas_feitas",
)


# ═══════════════════════════════════════════════════════════════════════════
# A posição publicada
# ═══════════════════════════════════════════════════════════════════════════


def cor_da_pessoa(posicao: Mapping[str, Any]) -> str:
    """A cor de regra da pessoa (`branca` ou `preta`), conferida.

    Raises:
        ValueError: a posição não diz a cor, ou diz uma que não existe. É
            defeito do DESAFIO, e quem chama distingue de "não cumpriu".
    """
    cor = posicao.get("cor_da_pessoa")
    if cor not in CORES:
        raise ValueError(
            f"a posição publicada do xadrez tem `cor_da_pessoa` = {cor!r}; "
            f"as cores são {sorted(CORES)}"
        )
    return cor


def marcas_iniciais(posicao: Mapping[str, Any]) -> dict[str, str | None]:
    """As peças marcadas da posição publicada (nome → casa), ou `{}`.

    `dict(...)` copia: quem segue as marcas lance a lance vai trocá-las, e a
    posição publicada não pode mudar no caminho.
    """
    return dict(posicao.get("marcas") or {})


# ═══════════════════════════════════════════════════════════════════════════
# 1. A reprodução: a única parte que pergunta ao executável
# ═══════════════════════════════════════════════════════════════════════════


def reproduzir(
    posicao: Mapping[str, Any],
    lances: Sequence[str],
    *,
    motor: JogadorXadrez | None = None,
) -> list[dict[str, Any]]:
    """Joga [lances] a partir da posição publicada, pelo executável.

    Args:
        posicao: a `js_posicao_inicial` do desafio (`fen`, `modalidade`,
            `cor_da_pessoa`, `marcas`...).
        lances: os lances da fita, dos dois lados, na notação interna
            (`e2e4`, `e1g1` no roque, `e7e8q` na promoção).
        motor: o executável; sem ele, o desta thread (`jogador_compartilhado`).

    Returns:
        Um PASSO por lance, `{"lance", "fatos", "marcas"}`: os fatos como o
        motor os devolveu (inclusive o `fim`) e as marcas DEPOIS do lance. É
        exatamente o que [medir] lê, e o que os vetores do juiz gravam.

    Raises:
        ValueError: um lance ilegal ou depois do fim (o motor recusa com
            `MotorXadrezRecusou`, que é `ValueError`); a modalidade que o
            contrato não declara; a vez no início que não é a da pessoa. ⚠️ É
            dado inválido, e o juiz o separa de "não cumpriu".
    """
    motor = motor or jogador_compartilhado()
    modalidade = posicao.get("modalidade")
    if modalidade not in contrato_xadrez.modalidades_declaradas():
        raise ValueError(
            f"a modalidade {modalidade!r} não está no contrato do xadrez "
            f"({list(contrato_xadrez.modalidades_declaradas())})"
        )
    fen = posicao.get("fen")
    if not isinstance(fen, str) or not fen:
        raise ValueError("a posição publicada do xadrez não tem `fen`")
    cor = cor_da_pessoa(posicao)

    # A vez no início é perguntada ao motor, e não lida do FEN aqui: quem sabe
    # ler um FEN é ele (um FEN torto é recusado lá, com o código).
    vez = motor.estado(modalidade=modalidade, fen_inicial=fen, lances=[])["vez"]
    if vez != cor:
        raise ValueError(
            f"a posição publicada diz que a pessoa joga de {cor}, e a vez no FEN "
            f"é das {vez}s: o desafio seria julgado do lado errado"
        )

    marcas = marcas_iniciais(posicao)
    passos: list[dict[str, Any]] = []
    for indice, lance in enumerate(lances):
        # Cada pedido leva a posição INTEIRA (o FEN mais os lances anteriores),
        # e não o FEN do lance anterior: a repetição tripla depende do
        # histórico, e só o motor o conta.
        resposta = motor.aplicar(
            modalidade=modalidade,
            fen_inicial=fen,
            lances=list(lances[:indice]),
            lance=lance,
            marcas=marcas,
        )
        passos.append(
            {"lance": lance, "fatos": resposta["fatos"], "marcas": resposta["marcas"]}
        )
        # As marcas do próximo pedido são as casas de DEPOIS deste lance.
        marcas = {nome: marca["casa"] for nome, marca in resposta["marcas"].items()}
    return passos


# ═══════════════════════════════════════════════════════════════════════════
# 2. A medida: pura, sobre os passos
# ═══════════════════════════════════════════════════════════════════════════


def _peca_comida(fatos: Mapping[str, Any]) -> str | None:
    """A peça comida no lance, pelo nome do motor, ou `None`.

    É `pecaComidaNoLanceXadrez` do app: no en passant o fato já traz o peão
    comido, que não está na casa de destino.
    """
    comida = fatos.get("comida")
    return comida.get("peca") if isinstance(comida, Mapping) else None


def _deu_xeque(fatos: Mapping[str, Any]) -> bool:
    """O lance deixou o rei de quem NÃO jogou em xeque (`xeque_por` não vazio).

    É `deuXequeNoLanceXadrez` do app.
    """
    return bool(fatos.get("xeque_por"))


def _marca(passo: Mapping[str, Any], nome: str) -> Mapping[str, Any] | None:
    """O que o motor disse da marca [nome] depois do passo, ou `None` sem ela."""
    marca = (passo.get("marcas") or {}).get(nome)
    return marca if isinstance(marca, Mapping) else None


def _fechou_troca(
    troca: Mapping[str, Any] | None,
    anterior: Mapping[str, Any] | None,
    fatos: Mapping[str, Any],
) -> bool:
    """O lance da pessoa (com [fatos]) fecha uma troca do par [troca]?

    As duas ordens de RF-XDR-201, lidas só dos fatos:

    - **ordem 2, comer primeiro**: a pessoa come uma peça `dele` com uma peça
      `minha`. Conta NESTE lance, retome o adversário ou não (RF-XDR-201: "se
      o adversário não devolver, o desafio conta como cumprido");
    - **ordem 1, oferecer e retomar**: no lance [anterior] (do adversário) uma
      peça `dele` comeu uma `minha`, e neste lance a pessoa come a peça que
      comeu: a casa da comida é a casa onde a peça dele parou.

    ⚠️ **No máximo uma troca por lance.** Com o par bispo × cavalo, a pessoa
    que retoma o cavalo com outro bispo cumpre as duas ordens no mesmo lance;
    contar duas seria dizer que ela trocou duas vezes com uma captura só.
    """
    if not troca:
        return False
    minha, dele = troca.get("minha"), troca.get("dele")
    comida = fatos.get("comida")
    if not isinstance(comida, Mapping):
        # Sem captura neste lance da pessoa, nenhuma das duas ordens fecha.
        return False

    # Ordem 2: a peça `minha` comeu a `dele`.
    if fatos.get("peca_movida") == minha and comida.get("peca") == dele:
        return True

    # Ordem 1: o adversário comeu a `minha` com a `dele`, e agora a pessoa
    # come justamente essa peça, na casa em que ela parou.
    if anterior is None:
        return False
    comida_antes = anterior.get("comida")
    return (
        isinstance(comida_antes, Mapping)
        and anterior.get("peca_movida") == dele
        and comida_antes.get("peca") == minha
        and comida.get("peca") == dele
        and comida.get("casa") == anterior.get("para")
    )


def medir(
    posicao: Mapping[str, Any], passos: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    """As 22 medidas da pessoa depois de [passos].

    Args:
        posicao: a `js_posicao_inicial` do desafio. Daqui saem a cor da pessoa,
            as marcas, as classes do `xadrez_comer_com` e o par da troca.
        passos: o que [reproduzir] devolveu (ou o prefixo dele), um por lance,
            o 1º da pessoa.

    Returns:
        As [CHAVES_DAS_MEDIDAS], todas, inclusive as que são zero: a medida que
        não aconteceu é zero, e não ausente (o avaliador da chegada recusa a
        chave ausente, de propósito).

    Raises:
        ValueError: a posição sem uma cor válida.
    """
    cor = cor_da_pessoa(posicao)
    marcas = marcas_iniciais(posicao)
    classes = posicao.get("classes") or {}
    troca = posicao.get("troca") or None
    ultima_fileira = ULTIMA_FILEIRA[cor]

    medidas: dict[str, int] = {chave: 0 for chave in CHAVES_DAS_MEDIDAS}
    # As espiãs e o alvo começam onde a posição publicada diz: é contra esta
    # casa que se percebe a primeira vez em que viraram `null`. Uma casa por
    # espiã (uma ou duas, conforme o tipo), pelo nome da marca.
    casas_das_espias = {nome: marcas.get(nome) for nome in MARCAS_DAS_ESPIAS if nome in marcas}
    casa_do_alvo = marcas.get(MARCA_DO_ALVO)
    sequencia = 0

    for indice, passo in enumerate(passos):
        fatos = passo["fatos"]
        # De quem é o lance: no xadrez a vez alterna, e a fita começa na pessoa.
        da_pessoa = indice % 2 == 0
        comida = _peca_comida(fatos)
        xeque = _deu_xeque(fatos)
        # O que o motor disse de cada espiã depois deste lance (as que existem).
        espias = {
            nome: marca
            for nome in MARCAS_DAS_ESPIAS
            if (marca := _marca(passo, nome)) is not None
        }
        # Uma espiã comeu, ou deu xeque, NESTE lance? Só uma peça se move por
        # lance, mas um lance de uma pode descobrir o xeque da outra: por isso
        # "alguma", e o lance conta uma vez só.
        espia_comeu = any(m.get("comeu") for m in espias.values())
        espia_deu_xeque = any(m.get("deu_xeque") for m in espias.values())
        alvo = _marca(passo, MARCA_DO_ALVO)

        if da_pessoa:
            medidas["lances_do_jogador"] += 1
            if comida is not None:
                medidas[f"pecas_comidas_{comida}"] += 1
            # Um lance dela sem xeque zera a sequência; com xeque, ela cresce.
            sequencia = sequencia + 1 if xeque else 0
            medidas["maior_sequencia_de_xeques"] = max(
                medidas["maior_sequencia_de_xeques"], sequencia
            )
            if espia_comeu:
                medidas["capturas_da_espia"] += 1
            if espia_deu_xeque:
                medidas["xeques_da_espia"] += 1
            if (
                classes.get("come") is not None
                and comida is not None
                and fatos.get("peca_movida") == classes["come"]
                # Sem `comida` nos parâmetros, qualquer peça comida serve.
                and classes.get("comida") in (None, comida)
            ):
                medidas["capturas_da_classe_marcada"] += 1
            anterior = passos[indice - 1]["fatos"] if indice > 0 else None
            if _fechou_troca(troca, anterior, fatos):
                medidas["trocas_feitas"] += 1
        else:
            # A peça comida num lance do adversário é da pessoa.
            if comida is not None:
                medidas[f"pecas_perdidas_{comida}"] += 1
            # O xeque do adversário é sobre o rei da pessoa.
            if xeque:
                medidas["xeques_recebidos"] += 1

        # ── As espiãs e o alvo, pelo que o motor disse depois do lance ───────
        for nome, espia in espias.items():
            if casas_das_espias.get(nome) is not None and espia.get("casa") is None:
                medidas["espia_comida"] = 1
            casas_das_espias[nome] = espia.get("casa")
            casa = casas_das_espias[nome]
            if casa is not None and casa[-1] == ultima_fileira:
                medidas["espia_na_ultima_fileira"] = 1
        if alvo is not None:
            # O alvo saiu NESTE lance, e uma espiã comeu neste lance: foi ela.
            if casa_do_alvo is not None and alvo.get("casa") is None and espia_comeu:
                medidas["alvo_comido_pela_espia"] = 1
            casa_do_alvo = alvo.get("casa")

        # ── O fim, como o motor o deu ───────────────────────────────────────
        fim = fatos.get("fim")
        if isinstance(fim, Mapping):
            vencedor = fim.get("vencedor")
            medidas["vitoria"] = 1 if vencedor == cor else 0
            medidas["empate"] = 1 if vencedor is None else 0

    return medidas
