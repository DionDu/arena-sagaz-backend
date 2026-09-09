"""As cinco cláusulas de captura do regulamento brasileiro, declaradas como dado.

Por que este arquivo existe antes do gerador de lances
------------------------------------------------------
O gerador de lances é a peça mais perigosa do projeto, e o perigo é de um tipo
específico: as cláusulas de captura das Regras Oficiais **não dão erro quando
implementadas errado**. Não travam, não lançam exceção, não aparecem em log. Dão
um motor que joga *quase* certo — e como a base de finais e o treino inteiro são
construídos em cima do gerador, o veneno se espalha em silêncio.

A defesa é escrituração dupla. Aqui eu **declaro**, lendo o texto normativo, o
que cada cláusula obriga e o que uma implementação ingênua faria no lugar. Depois
o gerador é escrito, e ele tem de concordar com esta declaração. Se discordarem,
um dos dois está errado e a discussão volta para o texto oficial — em vez de o
erro passar batido porque o código e o teste foram escritos pela mesma cabeça no
mesmo minuto.

As figuras didáticas saem **destes mesmos dados** (ver
`../visualizacao/gerar_figuras_das_clausulas.py`), então a figura não tem como
contradizer a especificação.

A fonte
-------
`../referencias/texto/12_regras_oficiais_cbjd.md` — *Regras Oficiais de Jogo de
Damas*, CBD/FMJD, Anexo I.

⚠️ **Correção de citação.** A proposta original citava estas cláusulas como
"art. 12", "art. 13", "art. 15" etc. **Está errado.** O documento numera como
*artigos* apenas as regras de empate (97 a 101); as cláusulas de captura são
**itens do RESUMO DAS REGRAS**, além do corpo do texto. Quem fosse conferir na
fonte pelos números antigos pararia no lugar errado. Cada cláusula abaixo traz o
campo `onde_no_documento` com a localização de verdade.

O que este arquivo NÃO faz
--------------------------
Não decide legalidade. `conferir_geometria` verifica que uma sequência declarada
tem **forma** de sequência de captura — que cada salto anda em diagonal, que a
peça capturada está no meio, que o destino está livre. Dizer se aquela sequência
é *a obrigatória* depende de enumerar todas as outras, e isso é o gerador.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from jogos.jogo_damas.motor.tabuleiro_damas import (
    CASAS_DE_COROACAO,
    Cor,
    Peca,
    Tabuleiro,
    casas_entre,
    cor_da_peca,
    direcao_entre,
)


@dataclass(frozen=True)
class Salto:
    """Um salto de captura: de onde, por cima de quem, para onde.

    Três casas e não duas, porque em damas o destino **não** é determinado pela
    peça capturada. Uma pedra sempre para na casa imediatamente seguinte, mas uma
    dama pode parar em qualquer casa livre adiante (RESUMO 17) — então o destino
    é informação, não consequência.
    """

    origem: int
    capturada: int
    destino: int

    def __str__(self) -> str:
        return f"{self.origem}×{self.capturada}→{self.destino}"


@dataclass(frozen=True)
class Sequencia:
    """Um lance de captura inteiro: um ou mais saltos encadeados.

    Attributes:
        saltos: os saltos, em ordem.
        vira_dama: se a peça termina o lance promovida. **Só é verdadeiro quando
            o lance TERMINA numa casa de coroação** — atravessar não promove.
        observacao: o que esta sequência tem de particular.
    """

    saltos: tuple[Salto, ...]
    vira_dama: bool = False
    observacao: str = ""

    @property
    def quantas_capturas(self) -> int:
        """Quantas peças esta sequência tira. É o número que a Lei da Maioria compara."""
        return len(self.saltos)

    @property
    def casas_visitadas(self) -> tuple[int, ...]:
        """Por onde a peça passou, da origem ao destino final."""
        return (self.saltos[0].origem, *(salto.destino for salto in self.saltos))

    @property
    def casas_capturadas(self) -> tuple[int, ...]:
        return tuple(salto.capturada for salto in self.saltos)

    def __str__(self) -> str:
        return "  ".join(str(salto) for salto in self.saltos)


@dataclass(frozen=True)
class ClausulaDeCaptura:
    """Uma cláusula do regulamento, com a posição que a demonstra.

    Attributes:
        identificador: nome curto, usado em nome de arquivo e de teste.
        nome: como a cláusula é chamada no jogo.
        texto_oficial: a frase do regulamento, **copiada literalmente**. Nunca
            parafraseada: parafrasear regra é como o erro entra.
        onde_no_documento: onde achar aquela frase na fonte.
        fen: a posição que demonstra a cláusula.
        correta: a sequência que o regulamento obriga.
        ingenua: o que uma implementação escrita por intuição faria — ``None``
            quando o erro ingênuo é *deixar de achar* a sequência correta, e não
            achar outra no lugar.
        alternativas_legais: os **outros** lances igualmente legais na mesma
            posição. Não é enfeite: `correta` mais estas têm de dar exatamente o
            conjunto que o gerador devolve, e há um teste que exige isso
            (`test_a_especificacao_lista_TODOS_os_lances_legais`). A regra
            existe porque a primeira versão destas figuras mostrava **um**
            caminho onde havia dois, dando a entender que o lance era único.
        erro_ingenuo: o que exatamente a implementação ingênua erra.
        consequencia: por que esse erro é caro, em vez de só feio.
    """

    identificador: str
    nome: str
    texto_oficial: str
    onde_no_documento: str
    fen: str
    correta: Sequencia
    erro_ingenuo: str
    consequencia: str
    ingenua: Sequencia | None = None
    alternativas_legais: tuple[Sequencia, ...] = field(default_factory=tuple)

    regulamento: str = "brasileira"
    """De qual regulamento é esta cláusula, pelo identificador.

    Nasceu com valor fixo porque as cinco primeiras cláusulas eram todas
    brasileiras. Virou campo em 2026-07-28, quando as portuguesas/espanholas
    entraram e trouxeram uma cláusula que **só existe lá** — a Lei da Qualidade.

    É `str` e não o objeto `Regulamento` de propósito: este módulo é uma
    declaração do que o texto normativo diz, lida **antes** e **independentemente**
    do código que a implementa. Importar o gerador aqui acoplaria a testemunha ao
    réu, e é justamente essa separação que já pegou um erro meu (ver o diário do
    plano, 2026-07-24)."""


# ---------------------------------------------------------------------------
# Conferência de geometria
# ---------------------------------------------------------------------------


def conferir_geometria(fen: str, sequencia: Sequencia, *, respeitar_tema_turco: bool = True) -> None:
    """Confere que uma sequência declarada tem forma de sequência de captura.

    Levanta ``ValueError`` na primeira incoerência, com mensagem dizendo qual
    salto e por quê. Não verifica se a sequência é **a obrigatória** — isso exige
    enumerar todas as outras, que é trabalho do gerador de lances.

    O que é conferido, salto a salto:

    1. origem e destino estão na mesma diagonal;
    2. a peça capturada está **estritamente entre** as duas;
    3. não há mais nada no caminho além dela;
    4. o destino está livre;
    5. a peça capturada é do adversário e ainda não foi capturada neste lance;
    6. se quem captura é **pedra**, o salto é de exatamente duas casas.

    Args:
        respeitar_tema_turco: com ``True`` (o padrão, e o correto), as peças
            capturadas **continuam no tabuleiro** até o fim do lance e portanto
            bloqueiam caminho e destino. Com ``False`` simula a implementação
            ingênua, que as remove na hora — é assim que se demonstra, com o
            mesmo código, que a sequência ingênua só existe por causa do erro.
    """
    tabuleiro = Tabuleiro.de_fen(fen)
    if not sequencia.saltos:
        raise ValueError("sequência sem nenhum salto")

    movente = tabuleiro.ler(sequencia.saltos[0].origem)
    if movente is Peca.VAZIA:
        raise ValueError(f"casa de origem {sequencia.saltos[0].origem} está vazia")
    cor_movente = cor_da_peca(movente)
    if cor_movente != tabuleiro.vez:
        raise ValueError(
            f"a peça em {sequencia.saltos[0].origem} não é de quem tem a vez"
        )
    e_pedra = movente in (Peca.PEDRA_BRANCA, Peca.PEDRA_PRETA)

    # A peça sai da casa de origem já no primeiro salto, então a casa fica livre
    # para o resto do lance — é isso que permite a Casa Cruz.
    tabuleiro.escrever(sequencia.saltos[0].origem, Peca.VAZIA)
    ja_capturadas: set[int] = set()
    posicao = sequencia.saltos[0].origem

    for indice, salto in enumerate(sequencia.saltos, start=1):
        rotulo = f"salto {indice} ({salto})"

        if salto.origem != posicao:
            raise ValueError(
                f"{rotulo}: começa em {salto.origem} mas a peça está em {posicao}"
            )
        if direcao_entre(salto.origem, salto.destino) is None:
            raise ValueError(f"{rotulo}: origem e destino não estão na mesma diagonal")

        meio = casas_entre(salto.origem, salto.destino)
        if salto.capturada not in meio:
            raise ValueError(
                f"{rotulo}: a casa {salto.capturada} não está entre origem e destino"
            )
        if e_pedra and len(meio) != 1:
            raise ValueError(
                f"{rotulo}: pedra salta exatamente 2 casas, esta saltou {len(meio) + 1}"
            )

        # Tudo o que não é a peça capturada neste salto tem de estar livre. Com o
        # Tema Turco valendo, "livre" exclui as peças já capturadas, porque elas
        # continuam fisicamente no tabuleiro até o lance acabar.
        for casa in meio:
            if casa == salto.capturada:
                continue
            if tabuleiro.ler(casa) is not Peca.VAZIA:
                raise ValueError(f"{rotulo}: a casa {casa} está no caminho e ocupada")

        if salto.capturada in ja_capturadas:
            raise ValueError(
                f"{rotulo}: a peça de {salto.capturada} já foi capturada neste lance"
            )
        alvo = tabuleiro.ler(salto.capturada)
        if alvo is Peca.VAZIA:
            raise ValueError(f"{rotulo}: não há peça em {salto.capturada}")
        if cor_da_peca(alvo) == cor_movente:
            raise ValueError(f"{rotulo}: a peça de {salto.capturada} é nossa")

        if tabuleiro.ler(salto.destino) is not Peca.VAZIA:
            raise ValueError(f"{rotulo}: a casa de destino {salto.destino} está ocupada")

        ja_capturadas.add(salto.capturada)
        if not respeitar_tema_turco:
            # O erro, simulado: a peça sai do tabuleiro no instante do salto, em
            # vez de ao fim do lance. É isto — e só isto — que abre caminho para
            # as sequências que o §Tema Turco mostra não existirem.
            tabuleiro.escrever(salto.capturada, Peca.VAZIA)
        posicao = salto.destino

    # A promoção depende de ONDE O LANCE TERMINA, não de por onde passou.
    termina_na_coroacao = posicao in CASAS_DE_COROACAO[Cor(cor_movente)]
    if e_pedra and sequencia.vira_dama != termina_na_coroacao:
        raise ValueError(
            f"declarado vira_dama={sequencia.vira_dama}, mas o lance termina em "
            f"{posicao}, que {'É' if termina_na_coroacao else 'NÃO é'} casa de coroação"
        )


# ---------------------------------------------------------------------------
# As cinco cláusulas
# ---------------------------------------------------------------------------

LEI_DA_MAIORIA = ClausulaDeCaptura(
    identificador="lei_da_maioria",
    nome="Lei da Maioria",
    texto_oficial=(
        "Se no mesmo lance se apresentarem mais de um modo de capturar, é "
        "obrigatório fazer o lance que capture o maior número de peças."
    ),
    onde_no_documento="Corpo do texto, “A CAPTURA EM CADEIA E A LEI DA MAIORIA”; "
                      "repetida no RESUMO DAS REGRAS, item 12",
    fen="W:W23:B10,18,19",
    correta=Sequencia(
        saltos=(Salto(23, 18, 14), Salto(14, 10, 7)),
        observacao="2 peças — é o máximo, logo é o único lance legal",
    ),
    ingenua=Sequencia(
        saltos=(Salto(23, 19, 16),),
        observacao="1 peça — captura de verdade, mas ILEGAL por ser a menor",
    ),
    erro_ingenuo=(
        "Aceitar qualquer captura disponível. As duas são capturas válidas "
        "isoladamente; o que torna a segunda ilegal é existir uma maior."
    ),
    consequencia=(
        "Obriga a enumerar TODAS as sequências completas antes de escolher — não "
        "dá para parar na primeira que funcionar, nem podar cedo. É o que torna a "
        "geração de lances de damas cara e difícil de acertar. Bom: conta só "
        "QUANTIDADE — pedra e dama valem o mesmo (“Pedra e dama tem o mesmo valor "
        "tanto para capturar quanto para serem capturadas”), ao contrário das "
        "regras espanholas e italianas."
    ),
)

COROACAO_SO_AO_PARAR = ClausulaDeCaptura(
    identificador="coroacao_so_ao_parar",
    nome="Coroação só ao parar",
    texto_oficial=(
        "A pedra que durante o lance de captura de várias peças, apenas passe por "
        "qualquer casa de coroação, sem aí parar, não será promovida a Dama."
    ),
    onde_no_documento="Corpo do texto, p. 5; RESUMO DAS REGRAS, item 13",
    fen="W:W11:B6,7",
    correta=Sequencia(
        saltos=(Salto(11, 7, 2), Salto(2, 6, 9)),
        vira_dama=False,
        observacao="passa pela casa 2, que é de coroação, mas NÃO para lá — "
                   "termina em 9 e continua PEDRA",
    ),
    ingenua=Sequencia(
        saltos=(Salto(11, 7, 2), Salto(2, 6, 13)),
        vira_dama=True,
        observacao="promove ao pisar em 2 e segue como DAMA — o que lhe permitiria "
                   "parar em 13, casa que uma pedra não alcança",
    ),
    erro_ingenuo=(
        "Promover no instante em que a peça toca a fileira de coroação, em vez de "
        "ao terminar o lance ali. O erro tem duas caras: a peça sai do lance sendo "
        "dama quando devia ser pedra, e — pior — passa a saltar como dama no meio "
        "da própria sequência, alcançando casas de que uma pedra não dispõe."
    ),
    consequencia=(
        "Repare no que a Lei da Maioria faz aqui: parar em 2 capturaria 1 peça e "
        "coroaria; seguir captura 2 peças e não coroa. Como o maior é obrigatório, "
        "**a pedra é forçada a abrir mão da própria promoção**. É contraintuitivo, "
        "é regra, e um motor que erre isso avalia mal toda posição de coroação."
    ),
)

CASA_CRUZ = ClausulaDeCaptura(
    identificador="casa_cruz",
    nome="Casa Cruz",
    texto_oficial=(
        "Na execução de uma captura em cadeia é permitido passar mais de uma vez "
        "pela mesma casa vazia."
    ),
    onde_no_documento="Corpo do texto, p. 5; RESUMO DAS REGRAS, item 14",
    fen="W:W30:B10,11,18,19,26",
    correta=Sequencia(
        saltos=(
            Salto(30, 26, 23),
            Salto(23, 19, 16),
            Salto(16, 11, 7),
            Salto(7, 10, 14),
            Salto(14, 18, 23),
        ),
        observacao="5 peças — e a casa 23 é usada DUAS vezes, no 1º e no 5º salto",
    ),
    ingenua=Sequencia(
        saltos=(Salto(30, 26, 23), Salto(23, 18, 14), Salto(14, 10, 7), Salto(7, 11, 16)),
        observacao="4 peças — é onde para quem proíbe repetir casa: o 5º salto "
                   "pousaria de novo em 23, e a poda o descarta",
    ),
    alternativas_legais=(
        Sequencia(
            saltos=(
                Salto(30, 26, 23),
                Salto(23, 18, 14),
                Salto(14, 10, 7),
                Salto(7, 11, 16),
                Salto(16, 19, 23),
            ),
            observacao="o mesmo diamante percorrido ao contrário — também 5 peças, "
                       "e também termina repisando a casa 23",
        ),
    ),
    erro_ingenuo=(
        "Guardar um conjunto de “casas já visitadas” e podar quem voltar a elas — "
        "reflexo natural de quem já escreveu busca em grafo, e que aqui poda "
        "lances legais."
    ),
    consequencia=(
        "Existem dois caminhos de 5 capturas nesta posição, e AMBOS terminam "
        "repisando a casa 23. Ou seja: quem poda casa repetida não perde “uma "
        "opção entre várias” — ele não alcança 5 de jeito nenhum, para em 4, e "
        "como a Lei da Maioria obriga o maior número, joga um lance ilegal "
        "convencido de que é o obrigatório."
    ),
)

TEMA_TURCO = ClausulaDeCaptura(
    identificador="tema_turco",
    nome="Tema Turco",
    texto_oficial=(
        "Na execução do lance de captura, não é permitido capturar a mesma peça "
        "mais de uma vez e as peças capturadas não podem ser retiradas do "
        "tabuleiro antes de completar o lance de captura."
    ),
    onde_no_documento="Corpo do texto, p. 5; RESUMO DAS REGRAS, item 15",
    fen="W:WK29:B17,25,26",
    correta=Sequencia(
        saltos=(Salto(29, 25, 22), Salto(22, 26, 31)),
        observacao="2 peças — a dama para em 31 porque a peça de 26, já capturada, "
                   "CONTINUA no tabuleiro e fecha a diagonal",
    ),
    alternativas_legais=(
        Sequencia(
            saltos=(Salto(29, 25, 22), Salto(22, 17, 13)),
            observacao="2 peças — o outro lance máximo. A peça de 17 PODE ser tomada: "
                       "só que a partir de 22, antes de a de 26 fechar a diagonal. "
                       "O que não existe é tomá-la DEPOIS.",
        ),
    ),
    ingenua=Sequencia(
        saltos=(Salto(29, 25, 22), Salto(22, 26, 31), Salto(31, 17, 13)),
        observacao="3 peças — só existe se a peça de 26 tiver sumido do tabuleiro "
                   "no instante da captura, abrindo passagem para a dama enxergar 17",
    ),
    erro_ingenuo=(
        "Apagar a peça capturada do tabuleiro no momento do salto. É o que "
        "qualquer um escreve por reflexo, porque é o que o jogador faz com a mão — "
        "só que o jogador faz isso DEPOIS de terminar o lance."
    ),
    consequencia=(
        "Esta cláusula só morde quando há **dama** envolvida. Numa cadeia só de "
        "pedras ela é inofensiva por aritmética: a pedra sempre pousa a duas casas, "
        "então as casas onde ela pousa e as casas das peças capturadas ficam em "
        "paridades diferentes e nunca colidem. A dama, que desliza distâncias "
        "quaisquer, atravessa a casa da peça capturada — e é aí que o motor "
        "ingênuo inventa uma captura a mais e a joga como obrigatória."
    ),
)

PARADA_LIVRE_DA_DAMA = ClausulaDeCaptura(
    identificador="parada_livre_da_dama",
    nome="Parada livre da dama",
    texto_oficial=(
        "A dama no último movimento de captura pode parar em qualquer casa livre "
        "na diagonal em que está capturando. A dama não é obrigada a parar na casa "
        "seguinte após a última peça capturada."
    ),
    onde_no_documento="RESUMO DAS REGRAS, item 17; corpo do texto, “A DAMA E SUA FORÇA”",
    fen="W:WK29:B19,25",
    correta=Sequencia(
        saltos=(Salto(29, 25, 15), Salto(15, 19, 24)),
        observacao="2 peças — e só existe porque a dama escolheu parar em 15, "
                   "quatro casas adiante da peça capturada",
    ),
    alternativas_legais=(
        Sequencia(
            saltos=(Salto(29, 25, 15), Salto(15, 19, 28)),
            observacao="2 peças — mesmo caminho até 15, e a cláusula aparece DE NOVO "
                       "no salto final: a dama escolhe parar em 28 em vez de 24",
        ),
    ),
    ingenua=Sequencia(
        saltos=(Salto(29, 25, 22),),
        observacao="1 peça — é onde para quem pousa a dama sempre na casa seguinte",
    ),
    erro_ingenuo=(
        "Tratar a dama como uma pedra de alcance longo: capturar e pousar na casa "
        "imediatamente após a peça tomada."
    ),
    consequencia=(
        "Depois de capturar a peça de 25, esta dama pode parar em 22, 18, 15, 11, "
        "8 ou 4 — seis lances diferentes onde o ingênuo vê um. E a escolha não é "
        "estética: **só de 15 existe a segunda captura**. Como a Lei da Maioria "
        "obriga o maior, as outras cinco paradas são ilegais nesta posição. O erro "
        "multiplica: infla o fator de ramificação de toda posição com dama, e ao "
        "mesmo tempo esconde o lance obrigatório."
    ),
)

LEI_DA_QUALIDADE = ClausulaDeCaptura(
    identificador="lei_da_qualidade",
    nome="Lei da Qualidade",
    texto_oficial=(
        "Quality rule: if the number of pieces captured is equal on all sides, "
        "it is mandatory to capture the better quality (a king instead of a "
        "man). If both quantity and quality are equal, the player may choose."
    ),
    onde_no_documento=(
        "Rules of Portuguese Draughts (Spanish Draughts), FPD, art. 3.7.b e 3.7.c"
    ),
    regulamento="portuguesa",
    # Dama branca em 20, com duas capturas de UMA peça cada: a de 27 é dama, a
    # de 9 é pedra. A quantidade empata, então a qualidade decide — e só uma das
    # duas continua legal.
    fen="W:WK20:B6,7,9,K27",
    correta=Sequencia(
        (Salto(origem=20, capturada=27, destino=31),),
        observacao="toma a DAMA de 27 — obrigatório, porque a quantidade empatou",
    ),
    ingenua=Sequencia(
        (Salto(origem=20, capturada=9, destino=2),),
        observacao="toma a pedra de 9: mesma quantidade, qualidade menor",
    ),
    erro_ingenuo=(
        "aplicar só a Lei da Maioria, como nas brasileiras, e deixar as duas "
        "capturas legais — ou, pior, inverter a ordem dos filtros e passar a "
        "preferir a dama antes de comparar a quantidade"
    ),
    consequencia=(
        "um gerador que oferece o lance de qualidade menor deixa o motor jogar "
        "um lance ILEGAL nas portuguesas/espanholas. E como as duas capturas "
        "existem de verdade na posição, nada dá erro: a partida corre inteira "
        "com um lance que o árbitro anularia. Inverter a ordem dos filtros é "
        "pior ainda — faria o motor tomar uma dama em vez de três pedras, "
        "achando que obedece o regulamento."
    ),
)
"""A cláusula que **só** as portuguesas/espanholas têm, e a razão de elas serem
uma terceira família em vez de uma variação das brasileiras.

Repare na ordem, que não é comutativa: **quantidade primeiro, qualidade só como
desempate** (3.7.a e depois 3.7.b). Entre tomar 3 pedras e tomar 1 dama, o
regulamento manda tomar as 3 pedras."""

CLAUSULAS: tuple[ClausulaDeCaptura, ...] = (
    LEI_DA_MAIORIA,
    COROACAO_SO_AO_PARAR,
    CASA_CRUZ,
    TEMA_TURCO,
    PARADA_LIVRE_DA_DAMA,
    LEI_DA_QUALIDADE,
)
"""Da mais óbvia à mais traiçoeira — e a última é de outro regulamento.

As cinco primeiras são brasileiras; a Lei da Qualidade é portuguesa/espanhola, e
por isso cada cláusula carrega o campo `regulamento`. Rodar uma cláusula
portuguesa com o gerador brasileiro reprovaria o gerador por um motivo que não é
defeito dele."""
