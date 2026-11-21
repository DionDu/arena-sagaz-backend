"""A POSICAO INICIAL de um desafio, nos dois formatos (RF-DES-218/221, T031).

═══════════════════════════════════════════════════════════════════════════
DOIS FORMATOS, E A DIFERENCA E DO JOGO — NAO E GOSTO
═══════════════════════════════════════════════════════════════════════════

    co_formato_posicao = 'fen'                → damas
    co_formato_posicao = 'sequencia_lances'   → Pontinhos e Quatro em Linha

Nas damas **cada peca carrega a sua cor na propria casa**, e a FEN ja traz de
quem e a vez no prefixo `W:`/`B:`. A posicao se descreve sozinha.

No Pontinhos a posse de uma caixa e **historico**: o tabuleiro fisico nao guarda
quem a fechou. Uma posicao so existe como a sequencia que a produziu.

⚠️ E por isso que uma matriz **nao** foi escolhida para o Pontinhos, e os tres
motivos estao no `data-model.md`:

  1. a migracao `0006` ja reconstroi o tabuleiro a partir das arestas, do vazio.
     Uma matriz criaria um SEGUNDO caminho de reconstrucao, so para o desafio —
     e dois caminhos para a mesma coisa e como as tres telas de fim de partida
     divergiram;
  2. a matriz **nao diz de quem e a vez**: quem fecha caixa joga de novo, e uma
     posicao com tres caixas fechadas e compativel com a vez de qualquer um dos
     dois — a diferenca muda o desafio inteiro;
  3. a matriz **nao e auditavel**: nada nela impede uma caixa fechada sem os
     quatro lados, ou um placar que nenhuma partida legal produziria.

═══════════════════════════════════════════════════════════════════════════
⚠️ `vez_de` E `placar` SAO DERIVADOS, E ESTAO NA LINHA COMO CONFERENCIA
═══════════════════════════════════════════════════════════════════════════

O job reconstroi a sequencia, recalcula os dois e **compara com o que gravou**.
Divergiu, ⛔ **nao publica**.

E o mesmo principio de `ic_chegada_encerra_partida`: ninguem digita, e o que esta
escrito tem de bater com o que se calcula. Um `vez_de` errado no banco produziria
um desafio que o aplicativo comeca com o jogador errado — sem erro nenhum.

═══════════════════════════════════════════════════════════════════════════
⚠️ O QUATRO EM LINHA TAMBEM E 'sequencia_lances' - E SE DESCREVE SOZINHO
═══════════════════════════════════════════════════════════════════════════

No Quatro a posicao TAMBEM e a sequencia que a produziu (`s4s4s3`), e a forma
e a que o arbitro grava (`MotorQuatro.para_dado`, T116 da spec 010): ela traz
`co_jogo`, `co_modalidade`, a lista e a notacao concatenada. ⚠️ **E e pelo
`co_jogo` de dentro da posicao que `conferir` separa os dois jogos**, e nao pelo
formato: os dois usam o mesmo rotulo, e a posicao do Pontinhos nao carrega
`co_jogo`. Uma posicao do Quatro sem ele cairia na conferencia do Pontinhos, e
ela falha alto (a lista do Quatro se chama `sequencia_lances`, e nao `lances`).

═══════════════════════════════════════════════════════════════════════════
⚠️ O XADREZ TAMBEM E 'fen' - MAS NAO E O FEN DAS DAMAS (T082 da spec 012)
═══════════════════════════════════════════════════════════════════════════

A posicao do xadrez segue o contrato §1 da spec 012 (`desafio-xadrez.md`): o
`jogo`, a `modalidade`, o `fen`, a `cor_da_pessoa`, a `origem` e, nos tipos que
os usam, as `marcas`, as `classes` e a `troca`. **Ela nao tem `versao` nem
`vez_de`**, de proposito: a vez e a do proprio FEN, e quem resolve e sempre o
`+1` da fita (`vez_de_quem_resolve`). E, como no Quatro, e pelo `jogo` de dentro
da posicao que `conferir` a separa das damas, e nao pelo formato.

⛔ **Nenhuma regra de xadrez aqui.** Se o FEN e legivel, de quem e a vez e se a
partida ja acabou quem responde e o motor em Rust (`estado`); o FEN so e lido
como tabela ("que peca esta em que casa", `motores/xadrez/fen_xadrez.py`), para
conferir que as marcas apontam para pecas da cor certa.
"""

from __future__ import annotations

from typing import Any, Mapping

from motores.damas.motor_damas import EstadoDamas
from motores.pontinhos.motor_pontinhos import EstadoPontinhos
from motores.quatro.motor_quatro import MotorQuatro

#: A versao do formato de `js_posicao_inicial`.
VERSAO = 1

#: Os dois valores de `co_formato_posicao`, e o `CHECK` da migracao `0018`.
FORMATO_SEQUENCIA = "sequencia_lances"
FORMATO_FEN = "fen"


class PosicaoInvalida(ValueError):
    """A posicao inicial nao descreve um estado alcancavel.

    ⚠️ **Isto e defeito do DESAFIO, e nao da tentativa de ninguem.** Quem o
    recebe na geracao descarta o candidato; quem o recebe na leitura descobriu
    dado corrompido no banco.
    """


# ═══════════════════════════════════════════════════════════════════════════
# Escrever
# ═══════════════════════════════════════════════════════════════════════════


def do_pontinhos(lances: list[str], *, jogador_inicial: int = 1) -> dict[str, Any]:
    """Monta `js_posicao_inicial` a partir da sequencia de tracos marcados.

    Args:
        lances: os rotulos (`H_0_1`, `V_1_0`, …) na ordem em que foram marcados.
        jogador_inicial: quem abriu a preparacao. `+1` por padrao, como no
            aplicativo.

    Returns:
        O JSON com `versao`, `lances` (cada um com o jogador que o fez), `vez_de`
        e `placar`.

    Raises:
        PosicaoInvalida: se a sequencia repetir um traco ou usar rotulo que nao
            existe no tabuleiro.

    ⚠️ **O jogador de cada lance nao e "par/impar"**: quem fecha caixa joga de
    novo. A alternancia sai da reproducao pelo motor, lance a lance — escreve-la
    a mao daria uma sequencia que o proprio motor recusaria.
    """
    estado = EstadoPontinhos()
    anotados: list[dict[str, Any]] = []

    try:
        for ordem, lance in enumerate(lances, start=1):
            anotados.append(
                {"n": ordem, "jogador": estado.vez_de, "lance": lance}
            )
            estado = estado.com_lance(lance)
        # Força a reproducao completa: o motor so valida quando lhe perguntam.
        placar = estado.placar
        vez = estado.vez_de
    except ValueError as erro:
        raise PosicaoInvalida(f"sequencia de Pontinhos invalida: {erro}") from erro

    if jogador_inicial != 1:
        # O motor sempre comeca pelo jogador 1 — e a regra do aplicativo. Uma
        # posicao que comecasse pelo outro exigiria virar a sequencia inteira, e
        # ninguem precisa disso hoje: falha alto em vez de fingir que atende.
        raise PosicaoInvalida(
            "o Pontinhos sempre abre com o jogador 1; nao ha como montar uma "
            f"preparacao comecando por {jogador_inicial}"
        )

    return {
        "versao": VERSAO,
        "lances": anotados,
        "vez_de": vez,
        "placar": {"j1": placar[1], "j2": placar[-1]},
    }


def das_damas(fen: str, *, co_modalidade: str = "brasileira") -> dict[str, Any]:
    """Monta `js_posicao_inicial` a partir de uma FEN.

    Raises:
        PosicaoInvalida: se a FEN nao for legivel pelo motor.

    ⚠️ `vez_de` sai da PROPRIA FEN (o prefixo `W:`/`B:`), e nao de um campo ao
    lado: duas fontes para o mesmo fato acabam discordando, e a que estivesse
    errada mandaria.
    """
    try:
        estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        vez = estado.vez_de
        # Reler a FEN pelo motor normaliza a escrita (ordem das casas, espacos):
        # duas FEN diferentes que descrevem a mesma posicao viram uma so, e o
        # `UNIQUE` do banco passa a significar o que promete.
        normalizada = estado.fen
    except (ValueError, KeyError, IndexError) as erro:
        raise PosicaoInvalida(f"FEN invalida: {fen!r} ({erro})") from erro

    return {"versao": VERSAO, "fen": normalizada, "vez_de": vez}


def do_quatro(lances: list[str], *, co_modalidade: str) -> dict[str, Any]:
    """Monta `js_posicao_inicial` do Quatro em Linha a partir dos lances.

    Args:
        lances: um lance por item (`["s4", "s4", "s3"]`), desde o tabuleiro
            vazio.
        co_modalidade: o id da modalidade no contrato do jogo. ⚠️ Modalidade e
            dado: o arbitro nasce com ela e recusa a que nao existe.

    Returns:
        A forma do arbitro (`MotorQuatro.para_dado`) mais a `versao`.

    Raises:
        PosicaoInvalida: lance ilegal, ou a partida ja acabou na posicao - um
            desafio precisa de um lance a jogar.

    ⚠️ `vez_de` sai da REPRODUCAO, e nao de "par/impar": numa modalidade que
    tira pecas a alternancia continua sendo do arbitro, e e ele quem responde.
    """
    try:
        motor = MotorQuatro(co_modalidade)
        estado = motor.estado_de_sequencia("".join(lances))
        acabou = motor.desfecho(estado) is not None
        dado = motor.para_dado(estado)
    except (ValueError, KeyError) as erro:
        raise PosicaoInvalida(f"sequencia do Quatro invalida: {erro}") from erro
    if acabou:
        raise PosicaoInvalida(
            f"a partida ja acabou em {''.join(lances)!r}: nao ha lance a jogar."
        )
    return {"versao": VERSAO, **dado}


# ═══════════════════════════════════════════════════════════════════════════
# Ler e CONFERIR
# ═══════════════════════════════════════════════════════════════════════════


def conferir(
    co_formato: str,
    posicao: Mapping[str, Any],
    *,
    co_modalidade: str = "brasileira",
) -> None:
    """Reconstroi a posicao e exige que os derivados batam com o que esta escrito.

    ⚠️ **E este passo que faz `vez_de` e `placar` valerem alguma coisa.** Sem ele
    os dois campos seriam anotacao decorativa, e um desafio com a vez errada
    passaria pelo banco e quebraria no aparelho de quem o jogasse.

    Raises:
        PosicaoInvalida: quando o formato nao existe, a posicao nao e
            reproduzivel, ou os derivados divergem.
    """
    if posicao.get("jogo") == "xadrez":
        # ⚠️ Antes da `versao`: a posicao do xadrez nao a tem (ver o topo).
        if co_formato != FORMATO_FEN:
            raise PosicaoInvalida(
                f"a posicao do xadrez chegou como {co_formato!r}; o formato dele e "
                f"{FORMATO_FEN!r}. ⛔ Nao publique este desafio."
            )
        _conferir_xadrez(posicao, co_modalidade)
        return

    if posicao.get("versao") != VERSAO:
        raise PosicaoInvalida(
            f"js_posicao_inicial versao {posicao.get('versao')!r}; esperada {VERSAO}"
        )

    if co_formato == FORMATO_SEQUENCIA and posicao.get("co_jogo") == "quatro":
        # ⚠️ Antes do Pontinhos: os dois usam o mesmo formato (ver o topo).
        _conferir_quatro(posicao, co_modalidade)
    elif co_formato == FORMATO_SEQUENCIA:
        _conferir_sequencia(posicao)
    elif co_formato == FORMATO_FEN:
        _conferir_fen(posicao, co_modalidade)
    else:
        raise PosicaoInvalida(
            f"co_formato_posicao {co_formato!r} nao existe. Os dois sao "
            f"{FORMATO_SEQUENCIA!r} e {FORMATO_FEN!r}."
        )


def _conferir_sequencia(posicao: Mapping[str, Any]) -> None:
    """A conferencia do Pontinhos: reproduz a sequencia e compara vez e placar."""
    lances = posicao.get("lances")
    if not isinstance(lances, list):
        raise PosicaoInvalida("js_posicao_inicial.lances precisa ser uma lista")

    try:
        estado = EstadoPontinhos(lances=tuple(l["lance"] for l in lances))
        placar = estado.placar
        vez = estado.vez_de
    except (ValueError, KeyError, TypeError) as erro:
        raise PosicaoInvalida(f"sequencia irreproduzivel: {erro}") from erro

    if posicao.get("vez_de") != vez:
        raise PosicaoInvalida(
            f"vez_de gravado ({posicao.get('vez_de')!r}) nao bate com o "
            f"reconstruido ({vez!r}). ⛔ Nao publique este desafio."
        )

    escrito = posicao.get("placar") or {}
    calculado = {"j1": placar[1], "j2": placar[-1]}
    if escrito != calculado:
        raise PosicaoInvalida(
            f"placar gravado ({escrito}) nao bate com o reconstruido "
            f"({calculado}). ⛔ Nao publique este desafio."
        )

    # ⚠️ O jogador anotado em cada lance tambem e derivado, e tambem se confere:
    # e ele que o medidor por fita usa para saber onde um turno comeca.
    reproduzido = EstadoPontinhos()
    for lance in lances:
        if lance.get("jogador") != reproduzido.vez_de:
            raise PosicaoInvalida(
                f"o lance {lance.get('n')} esta anotado como do jogador "
                f"{lance.get('jogador')!r}, mas na reproducao a vez e de "
                f"{reproduzido.vez_de!r} — quem fecha caixa joga de novo, e a "
                "anotacao tem de refletir isso."
            )
        reproduzido = reproduzido.com_lance(lance["lance"])


def _conferir_quatro(posicao: Mapping[str, Any], co_modalidade: str) -> None:
    """A conferencia do Quatro: reproduz a sequencia e compara cada derivado.

    Os derivados sao tres - a notacao concatenada (`co_lances`, que o app le
    como `co_lances_iniciais`), a vez e a modalidade -, e todos se refazem.
    """
    if posicao.get("co_modalidade") != co_modalidade:
        raise PosicaoInvalida(
            f"a posicao diz modalidade {posicao.get('co_modalidade')!r}, e o "
            f"desafio, {co_modalidade!r}. ⛔ Nao publique este desafio."
        )
    lances = posicao.get("sequencia_lances")
    if not isinstance(lances, list):
        raise PosicaoInvalida("js_posicao_inicial.sequencia_lances precisa ser uma lista")
    refeita = do_quatro(lances, co_modalidade=co_modalidade)
    for campo in ("co_formato_posicao", "co_lances", "vez_de"):
        if posicao.get(campo) != refeita[campo]:
            raise PosicaoInvalida(
                f"{campo} gravado ({posicao.get(campo)!r}) nao bate com o "
                f"reconstruido ({refeita[campo]!r}). ⛔ Nao publique este desafio."
            )


def _conferir_fen(posicao: Mapping[str, Any], co_modalidade: str) -> None:
    """A conferencia das damas: a FEN e legivel, e a vez bate com o prefixo."""
    fen = posicao.get("fen")
    if not isinstance(fen, str) or not fen:
        raise PosicaoInvalida("js_posicao_inicial.fen ausente")

    try:
        estado = EstadoDamas(co_modalidade=co_modalidade, fen_inicial=fen)
        vez = estado.vez_de
    except (ValueError, KeyError, IndexError) as erro:
        raise PosicaoInvalida(f"FEN irreproduzivel: {fen!r} ({erro})") from erro

    if posicao.get("vez_de") != vez:
        raise PosicaoInvalida(
            f"vez_de gravado ({posicao.get('vez_de')!r}) nao bate com o prefixo "
            f"da FEN ({vez!r}). ⛔ Nao publique este desafio."
        )


#: As chaves que a posicao do xadrez pode ter (contrato §1 da spec 012). Uma
#: chave fora daqui e defeito do job: o contrato e fechado.
CHAVES_DA_POSICAO_DO_XADREZ = frozenset(
    {"jogo", "modalidade", "fen", "cor_da_pessoa", "marcas", "classes", "troca", "origem"}
)

#: De onde a posicao do xadrez pode vir (`origem`, contrato §1): a base
#: equilibrada da T073 ou o banco de problemas de mate do Lichess (T074).
ORIGENS_DO_XADREZ = frozenset({"base_equilibrada", "problemas_lichess"})


def _conferir_xadrez(
    posicao: Mapping[str, Any], co_modalidade: str, *, motor: Any = None
) -> None:
    """A conferencia do xadrez: o motor diz se a posicao vale, o FEN diz as pecas.

    O que se confere, na ordem:

      1. as chaves sao as do contrato, a `modalidade` e a do desafio e a
         `origem` e uma das duas;
      2. **o motor** (`estado`, sem lance nenhum) le o FEN, diz de quem e a vez
         e se a partida ja acabou: a vez tem de ser a da `cor_da_pessoa` (um
         desafio com a vez errada seria julgado do lado errado), e a partida
         nao pode ter acabado (um desafio precisa de um lance a jogar);
      3. as `marcas` apontam para pecas de verdade: a espia (e a 2a espia) da
         pessoa, o alvo do adversario; as duas espias em classes diferentes
         (`DECISOES-do-dono.md` §8zzzz65: a frase nomeia as duas);
      4. as `classes` e a `troca` falam de pecas que existem no tabuleiro, do
         lado certo.

    Args:
        motor: o executavel do xadrez; sem ele, o desta thread
            (`jogador_compartilhado`). So os testes o passam.

    ⚠️ **Os itens 3 e 4 sao leitura do FEN como tabela**, e nao regra: "ha um
    cavalo branco em f3" se le no 1o campo do FEN, como o app faz para desenhar
    o tabuleiro.
    """
    # Importados aqui, e nao no topo: os tres primeiros jogos nao precisam do
    # executavel do xadrez para conferir a posicao deles.
    from motores.xadrez import contrato_xadrez
    from motores.xadrez.feitos_xadrez import (
        MARCA_DA_ESPIA,
        MARCA_DA_SEGUNDA_ESPIA,
        MARCA_DO_ALVO,
    )
    from motores.xadrez.fen_xadrez import PECA_DA_LETRA, outra_cor, pecas_do_fen
    from motores.xadrez.jogador_xadrez import jogador_compartilhado

    def recusar(motivo: str) -> None:
        """Sobe a `PosicaoInvalida` com o prefixo comum (uma frase por motivo)."""
        raise PosicaoInvalida(f"posicao do xadrez: {motivo}. ⛔ Nao publique este desafio.")

    # ── 1. A forma ──────────────────────────────────────────────────────────
    # `set(posicao)` sao as chaves do dicionario; `-` e a diferenca de conjuntos.
    sobrando = set(posicao) - CHAVES_DA_POSICAO_DO_XADREZ
    if sobrando:
        recusar(f"chaves fora do contrato §1: {sorted(sobrando)}")
    modalidade = posicao.get("modalidade")
    if modalidade != co_modalidade:
        recusar(f"a posicao diz modalidade {modalidade!r}, e o desafio, {co_modalidade!r}")
    if modalidade not in contrato_xadrez.modalidades_declaradas():
        recusar(f"a modalidade {modalidade!r} nao esta no contrato do xadrez")
    if posicao.get("origem") not in ORIGENS_DO_XADREZ:
        recusar(f"origem {posicao.get('origem')!r}; as origens sao {sorted(ORIGENS_DO_XADREZ)}")
    fen = posicao.get("fen")
    if not isinstance(fen, str) or not fen:
        recusar("sem `fen`")
    cor = posicao.get("cor_da_pessoa")
    if cor not in ("branca", "preta"):
        recusar(f"`cor_da_pessoa` = {cor!r}; as cores sao 'branca' e 'preta'")

    # ── 2. O motor ──────────────────────────────────────────────────────────
    motor = motor or jogador_compartilhado()
    try:
        estado = motor.estado(modalidade=modalidade, fen_inicial=fen, lances=[])
    except ValueError as erro:
        # `MotorXadrezRecusou` e um `ValueError`: o motor recusou o FEN, e o
        # codigo dele vai na mensagem.
        recusar(f"o motor recusou o FEN {fen!r} ({erro})")
    if estado.get("vez") != cor:
        recusar(
            f"a pessoa joga de {cor}, e a vez no FEN e das {estado.get('vez')}s: o "
            "desafio seria julgado do lado errado"
        )
    if estado.get("fim") is not None:
        recusar(f"a partida ja acabou no FEN ({estado['fim']}): nao ha lance a jogar")

    # ── 3. As marcas ────────────────────────────────────────────────────────
    # O FEN ja foi aceito pelo motor, entao a leitura como tabela nao falha aqui.
    pecas = pecas_do_fen(fen)
    marcas = posicao.get("marcas")
    if marcas is not None:
        if not isinstance(marcas, Mapping) or not marcas:
            recusar(f"`marcas` = {marcas!r}; sem marca, a chave nao vai")
        conhecidas = {MARCA_DA_ESPIA, MARCA_DA_SEGUNDA_ESPIA, MARCA_DO_ALVO}
        if set(marcas) - conhecidas:
            recusar(f"marcas desconhecidas: {sorted(set(marcas) - conhecidas)}")
        if MARCA_DA_ESPIA not in marcas:
            # O alvo e a 2a espia so existem ao lado da espia.
            recusar("ha marca sem a espia")
        # De que cor tem de ser a peca de cada marca.
        dono_da_marca = {
            MARCA_DA_ESPIA: cor,
            MARCA_DA_SEGUNDA_ESPIA: cor,
            MARCA_DO_ALVO: outra_cor(cor),
        }
        for nome, casa in marcas.items():
            peca = pecas.get(casa) if isinstance(casa, str) else None
            if peca is None:
                recusar(f"a marca {nome!r} aponta para {casa!r}, onde nao ha peca")
            if peca.cor != dono_da_marca[nome]:
                recusar(
                    f"a marca {nome!r} esta numa peca {peca.cor} ({casa}), e tinha de "
                    f"ser {dono_da_marca[nome]}"
                )
        if MARCA_DA_SEGUNDA_ESPIA in marcas:
            primeira = pecas[marcas[MARCA_DA_ESPIA]]
            segunda = pecas[marcas[MARCA_DA_SEGUNDA_ESPIA]]
            if primeira.casa == segunda.casa:
                recusar("as duas espias estao na mesma casa")
            if primeira.peca == segunda.peca:
                recusar(
                    f"as duas espias sao {primeira.peca}: tem de ser de classes "
                    "diferentes (a frase nomeia as duas)"
                )

    # ── 4. As classes e a troca ─────────────────────────────────────────────
    nomes = set(PECA_DA_LETRA.values())

    def exigir_peca(papel: str, classe: Any, de_quem: str) -> None:
        """A [classe] e um nome de peca, e o lado [de_quem] tem ao menos uma."""
        if classe not in nomes:
            recusar(f"{papel} = {classe!r} nao e peca")
        # `any(...)` e verdadeiro se ao menos uma peca do tabuleiro casa.
        if not any(p.peca == classe and p.cor == de_quem for p in pecas.values()):
            recusar(f"{papel} = {classe!r}, e as {de_quem}s nao tem nenhum")

    classes = posicao.get("classes")
    if classes is not None:
        if not isinstance(classes, Mapping) or set(classes) - {"come", "comida"}:
            recusar(f"`classes` = {classes!r}; as chaves sao 'come' e 'comida'")
        exigir_peca("classes.come", classes.get("come"), cor)
        if "comida" in classes:
            exigir_peca("classes.comida", classes["comida"], outra_cor(cor))
    troca = posicao.get("troca")
    if troca is not None:
        if not isinstance(troca, Mapping) or set(troca) != {"minha", "dele"}:
            recusar(f"`troca` = {troca!r}; as chaves sao 'minha' e 'dele'")
        exigir_peca("troca.minha", troca["minha"], cor)
        exigir_peca("troca.dele", troca["dele"], outra_cor(cor))


def formato_do_jogo(co_jogo: str) -> str:
    """Qual formato aquele jogo usa.

    ⚠️ **Jogo novo entra aqui, e falha alto se nao entrar.** Um jogo sem formato
    declarado gravaria a posicao no formato errado — e o aplicativo tentaria ler
    uma FEN como sequencia, sem que nada dissesse por que.
    """
    formatos = {
        "pontinhos": FORMATO_SEQUENCIA,
        "damas": FORMATO_FEN,
        "quatro": FORMATO_SEQUENCIA,
        # ⚠️ O xadrez tambem e FEN (contrato §1 da spec 012), mas o FEN dele nao
        # e o das damas: quem o confere e `_conferir_xadrez`, pelo `jogo` de
        # dentro da posicao.
        "xadrez": FORMATO_FEN,
    }
    if co_jogo not in formatos:
        raise PosicaoInvalida(
            f"o jogo {co_jogo!r} nao declarou formato de posicao. Jogo novo entra "
            "em `formato_do_jogo`, ou nao e publicavel."
        )
    return formatos[co_jogo]


#: De quem e o desafio no xadrez, no vocabulario da fita: a pessoa e `+1`, como
#: nos vetores do juiz (`contratos/vetores-juiz-xadrez.json`).
VEZ_DA_PESSOA_NO_XADREZ = 1


def vez_de_quem_resolve(posicao: Mapping[str, Any]) -> int:
    """O sinal de quem resolve o desafio (`+1`/`-1`), o `jogador` do juiz.

    ⚠️ **Os tres primeiros jogos o gravam na posicao** (`vez_de`, conferido por
    [conferir]); **o xadrez nao** (T076 da spec 012): a posicao dele diz a COR
    da pessoa (`cor_da_pessoa`), a pessoa e sempre `+1` na fita, e o
    `js_posicao_inicial` segue o formato do contrato §1, sem campo a mais.

    Raises:
        KeyError: posicao de jogo que deveria ter `vez_de` e nao tem. ⚠️ Falha
            alto: um `1` de reserva julgaria o desafio do lado errado calado.
    """
    if posicao.get("jogo") == "xadrez":
        return VEZ_DA_PESSOA_NO_XADREZ
    return posicao["vez_de"]
