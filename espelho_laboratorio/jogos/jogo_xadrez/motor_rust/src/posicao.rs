//! A posição na fronteira: FEN inicial + lista de lances (research.md R-03).
//!
//! Toda pergunta ao motor traz `{"fen_inicial": "...", "lances": ["e2e4", ...]}`.
//! O motor parte do FEN e **reaplica** os lances, um por um. É assim que ele sabe
//! tudo o que a regra precisa (de quem é a vez, o roque, o en passant, a contagem
//! dos 50 lances) **e** o histórico de posições que a repetição tripla vai pedir
//! (T019), sem um segundo formato para manter coerente.
//!
//! ## A notação interna dos lances
//!
//! Origem e destino pelo nome da casa, `e2e4`; na promoção, a letra **minúscula**
//! da peça escolhida: `e7e8q` (dama), `r` (torre), `b` (bispo), `n` (cavalo).
//! Essa notação **nunca** chega a um texto que a pessoa lê (RF-XDR-006).
//!
//! ## ⚠️ O roque, nos dois sentidos
//!
//! A `cozy-chess` 0.3.4 representa o roque no formato do Xadrez 960: **"o rei
//! captura a própria torre"** - o roque curto das brancas é `e1h1`, e não `e1g1`
//! (conferido na fonte da versão travada: `Board::play_unchecked`, comentário
//! "Castling move encoded as king captures rook"). A fronteira do nosso motor fala
//! o formato de todo mundo, `e1g1`/`e1c1`, e a conversão mora **só aqui**:
//! [`lance_do_texto`] (texto → `cozy`) e [`texto_do_lance`] (`cozy` → texto).
//!
//! ## ⚠️ A chave de posição e o en passant
//!
//! A FIDE diz que duas posições são "a mesma" para a repetição só se o direito
//! de en passant for o mesmo **quando a captura é possível**. A `cozy-chess`
//! marca o en passant depois de **todo** avanço duplo de peão, haja ou não um
//! peão vizinho para capturar (conferido na fonte: `new_en_passant =
//! Some(mv.to.file())` sem olhar os vizinhos), e o `Board::hash()` dela **inclui**
//! essa marca sempre. Usado cru, ele separaria duas posições iguais pela FIDE.
//! Por isso a chave do histórico é **nossa** ([`chave_da_posicao`]): o `hash()`
//! quando a captura en passant é de fato legal, e o `hash_without_ep()` quando não
//! é. A repetição tripla (T019) lê esta chave.

use cozy_chess::{Board, Color, File, Move, Piece, Rank, Square};

/// O que pode dar errado ao montar uma posição a partir da fronteira.
///
/// Os nomes viram os códigos de erro do contrato (`contracts/motor-xadrez.md` §2):
/// `fen_invalido` e `lance_ilegal_na_lista`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ErroPosicao {
    /// O FEN não pôde ser lido, ou descreve uma posição impossível (por
    /// exemplo, o lado que NÃO joga em xeque). O texto é o motivo da biblioteca.
    FenInvalido(String),
    /// O lance de índice `indice` (contado a partir de 0) na lista `lances` não
    /// é legal na posição em que ele seria jogado - ou nem é um lance escrito
    /// na notação interna.
    LanceIlegalNaLista { indice: usize, lance: String },
}

impl ErroPosicao {
    /// O código de erro da fronteira (§2 do contrato).
    pub fn codigo(&self) -> &'static str {
        match self {
            ErroPosicao::FenInvalido(_) => "fen_invalido",
            ErroPosicao::LanceIlegalNaLista { .. } => "lance_ilegal_na_lista",
        }
    }

    /// Um texto curto para o campo `detalhe` da resposta de erro.
    pub fn detalhe(&self) -> String {
        match self {
            ErroPosicao::FenInvalido(motivo) => format!("FEN invalido: {motivo}"),
            ErroPosicao::LanceIlegalNaLista { indice, lance } => {
                format!("o lance {indice} da lista ({lance}) nao e legal ali")
            }
        }
    }
}

/// Uma posição montada: o tabuleiro de agora e as chaves de todas as posições
/// desde o `fen_inicial` (inclusive ele e a de agora).
#[derive(Debug, Clone)]
pub struct Posicao {
    /// O tabuleiro depois de todos os lances reaplicados.
    pub tabuleiro: Board,
    /// A chave ([`chave_da_posicao`]) de cada posição, na ordem em que
    /// aconteceram: o índice 0 é a do `fen_inicial`, e o último é a de agora.
    /// ⚠️ Posições ANTES do `fen_inicial` não existem para o motor: numa partida
    /// adiantada ou num desafio, o histórico começa na posição publicada (R-03).
    pub historico_de_chaves: Vec<u64>,
    /// Os lances jogados desde o `fen_inicial`, na ordem (o último é o do
    /// adversário de quem joga agora). O ruído dos níveis (`niveis.rs`, T038) lê
    /// o penúltimo: é o último lance do PRÓPRIO personagem, e o lance que o
    /// desfaz (a torre que vai e volta) não entra entre os erros plausíveis.
    pub lances: Vec<Move>,
}

/// Lê o FEN (o padrão, não o do 960) e reaplica a lista de lances.
///
/// Devolve o erro do **primeiro** problema achado: um FEN torto, ou o índice do
/// primeiro lance que não é legal ali.
pub fn montar(fen_inicial: &str, lances: &[String]) -> Result<Posicao, ErroPosicao> {
    // `from_fen(texto, false)`: o `false` quer dizer "não é o formato Shredder"
    // (o do 960, em que o roque se escreve pela coluna da torre). Nós falamos
    // o FEN padrão, com `KQkq`.
    let mut tabuleiro = Board::from_fen(fen_inicial.trim(), false)
        .map_err(|e| ErroPosicao::FenInvalido(e.to_string()))?;

    let mut historico_de_chaves = Vec::with_capacity(lances.len() + 1);
    historico_de_chaves.push(chave_da_posicao(&tabuleiro));
    // Os lances já convertidos (o nome `jogados` evita a confusão com o
    // parâmetro `lances`, que é a lista em texto).
    let mut jogados = Vec::with_capacity(lances.len());

    // `enumerate()` entrega o par (índice, item): o índice é o que vai no erro.
    for (indice, texto) in lances.iter().enumerate() {
        let lance = lance_do_texto(&tabuleiro, texto).ok_or_else(|| {
            ErroPosicao::LanceIlegalNaLista {
                indice,
                lance: texto.clone(),
            }
        })?;
        // O lance já foi conferido como legal em `lance_do_texto`, então `play`
        // (que entra em pânico com lance ilegal) não tem como falhar aqui.
        tabuleiro.play(lance);
        historico_de_chaves.push(chave_da_posicao(&tabuleiro));
        jogados.push(lance);
    }

    Ok(Posicao {
        tabuleiro,
        historico_de_chaves,
        lances: jogados,
    })
}

impl Posicao {
    /// Uma posição sem passado: o histórico tem só a chave dela mesma. É o que
    /// [`montar`] devolve com a lista de lances vazia, sem passar pelo FEN em
    /// texto - para quem já tem o tabuleiro na mão (os testes da busca e as
    /// ferramentas).
    pub fn sem_historico(tabuleiro: Board) -> Posicao {
        let chave = chave_da_posicao(&tabuleiro);
        Posicao {
            tabuleiro,
            historico_de_chaves: vec![chave],
            lances: Vec::new(),
        }
    }

    /// Joga um lance **já conferido como legal** e guarda a chave da posição
    /// nova no histórico. É o que o `aplicar` e os fatos da busca usam para
    /// saber o estado DEPOIS do lance (com a repetição contada certo).
    ///
    /// `&mut self` quer dizer que a função altera a posição recebida, em vez de
    /// devolver outra.
    pub fn jogar(&mut self, lance: Move) {
        self.tabuleiro.play(lance);
        self.historico_de_chaves.push(chave_da_posicao(&self.tabuleiro));
        self.lances.push(lance);
    }
}

/// O nome de uma peça no vocabulário da fronteira (`contracts/motor-xadrez.md`
/// §2.2). São códigos, e não texto que a pessoa lê: a tela os traduz pelos `.arb`.
pub fn nome_da_peca(peca: Piece) -> &'static str {
    match peca {
        Piece::Pawn => "peao",
        Piece::Knight => "cavalo",
        Piece::Bishop => "bispo",
        Piece::Rook => "torre",
        Piece::Queen => "dama",
        Piece::King => "rei",
    }
}

/// Lê o nome de uma casa (`a1` a `h8`), ou `None` se o texto não for uma casa.
/// O `parse` da biblioteca aceita só as minúsculas, que é a nossa notação.
pub fn casa_do_texto(texto: &str) -> Option<Square> {
    if texto.len() != 2 {
        return None;
    }
    texto.parse().ok()
}

/// As peças da cor `atacante` que atacam a `casa`, com a ocupação dada.
///
/// A ocupação vem de fora porque às vezes ela não é a do tabuleiro: para saber
/// se o rei pode PASSAR por uma casa no roque, o próprio rei sai da conta (ele
/// não se protege com o corpo). "Atacar" aqui é o ataque de cada peça, sem
/// conferir se a atacante está cravada: é a definição de casa atacada da regra
/// do roque e do xeque.
///
/// A ideia é a do "olhar ao contrário": um cavalo inimigo ataca a casa se ele
/// estiver numa das casas de onde um cavalo partindo DA casa chegaria. O mesmo
/// vale para rei, bispo, torre e dama; o peão é o único que não é simétrico
/// (ataca para a frente), e por isso a conta usa os ataques de um peão da OUTRA
/// cor partindo da casa.
pub fn atacantes_da_casa(
    tabuleiro: &Board,
    casa: Square,
    atacante: Color,
    ocupacao: cozy_chess::BitBoard,
) -> cozy_chess::BitBoard {
    // `get_*` são as tabelas de ataque da `cozy-chess` (as de bispo e torre
    // recebem a ocupação, porque param na primeira peça do caminho).
    let pecas = |peca: Piece| tabuleiro.colored_pieces(atacante, peca);
    let damas = pecas(Piece::Queen);
    // `|` é a união de dois conjuntos de casas (BitBoard); `&` a interseção.
    (cozy_chess::get_knight_moves(casa) & pecas(Piece::Knight))
        | (cozy_chess::get_king_moves(casa) & pecas(Piece::King))
        // `!atacante` é a outra cor (o `Not` da `Color`).
        | (cozy_chess::get_pawn_attacks(casa, !atacante) & pecas(Piece::Pawn))
        | (cozy_chess::get_bishop_moves(casa, ocupacao) & (pecas(Piece::Bishop) | damas))
        | (cozy_chess::get_rook_moves(casa, ocupacao) & (pecas(Piece::Rook) | damas))
}

/// As casas de um conjunto, como texto e em ordem fixa (`a1`, `b1`, ..., `h8`):
/// a ordem de iteração do `BitBoard` é a das casas, e não muda entre máquinas.
pub fn nomes_das_casas(casas: cozy_chess::BitBoard) -> Vec<String> {
    casas.into_iter().map(|c| c.to_string()).collect()
}

/// Converte um lance da notação interna (`e2e4`, `e7e8q`, `e1g1`) no lance da
/// `cozy-chess`, **se ele for legal** no tabuleiro dado. Senão, `None`.
///
/// É aqui que o roque `e1g1` vira o `e1h1` da biblioteca (o rei "captura" a
/// própria torre).
pub fn lance_do_texto(tabuleiro: &Board, texto: &str) -> Option<Move> {
    // A notação interna tem 4 caracteres, ou 5 na promoção. Qualquer outro
    // tamanho (ou letra maiúscula, que o `parse` da biblioteca recusa) não é lance.
    if texto.len() != 4 && texto.len() != 5 {
        return None;
    }
    // `parse::<Move>()` usa o `FromStr` da biblioteca: lê `e2e4` e `e7e8q`.
    // O `.ok()?` transforma o erro de leitura em `None` e sai da função.
    let mut lance: Move = texto.parse().ok()?;
    // ⚠️ O `parse` da biblioteca lê `e2e4k` (e `e2e4p`) como `e2e4` SEM
    // promoção: a letra de rei ou de peão é descartada em silêncio (conferido na
    // fonte da `cozy-chess-types` 0.2.2, `FromStr for Move`). Na fronteira, um
    // 5º caractere só existe se for uma promoção de verdade.
    if texto.len() == 5 && lance.promotion.is_none() {
        return None;
    }

    let lado = tabuleiro.side_to_move();

    // O formato do 960 ("o rei vai à casa da própria torre", `e1h1`) é da
    // biblioteca, não da fronteira: recusado, para existir UMA escrita do roque.
    if tabuleiro.piece_on(lance.from) == Some(Piece::King)
        && tabuleiro.color_on(lance.from) == Some(lado)
        && tabuleiro.color_on(lance.to) == Some(lado)
    {
        return None;
    }

    // O roque: o rei andando duas colunas na própria fileira. Trocamos o
    // destino pela casa da torre, que é como a biblioteca o conhece.
    if tabuleiro.piece_on(lance.from) == Some(Piece::King)
        && tabuleiro.color_on(lance.from) == Some(lado)
        && lance.from.rank() == lance.to.rank()
        && lance.promotion.is_none()
    {
        // A distância em colunas, com sinal: +2 é o curto (para o lado do
        // rei), -2 o longo (para o lado da dama).
        let distancia = lance.to.file() as i32 - lance.from.file() as i32;
        let direitos = tabuleiro.castle_rights(lado);
        let coluna_da_torre = match distancia {
            2 => direitos.short,
            -2 => direitos.long,
            _ => None,
        };
        if let Some(coluna) = coluna_da_torre {
            lance.to = Square::new(coluna, lance.from.rank());
        } else if distancia.abs() == 2 {
            // Duas casas sem direito de roque daquele lado: não é lance.
            return None;
        }
    }

    // `is_legal` confere tudo: a peça é de quem joga, o destino é alcançável,
    // o rei não fica em xeque, a promoção é obrigatória e só na última fileira.
    if tabuleiro.is_legal(lance) {
        Some(lance)
    } else {
        None
    }
}

/// Converte um lance da `cozy-chess` na notação interna. O roque `e1h1` da
/// biblioteca sai como `e1g1` (e o longo `e1a1` como `e1c1`).
///
/// ⚠️ Recebe o tabuleiro **antes** do lance: é ele que diz se o destino é uma
/// torre da mesma cor (o roque) ou não.
pub fn texto_do_lance(tabuleiro: &Board, lance: Move) -> String {
    let lado = tabuleiro.side_to_move();
    let e_roque = tabuleiro.piece_on(lance.from) == Some(Piece::King)
        && tabuleiro.color_on(lance.to) == Some(lado);
    if e_roque {
        // O rei termina na coluna G (curto) ou C (longo), na própria fileira.
        let coluna = if lance.to.file() > lance.from.file() {
            File::G
        } else {
            File::C
        };
        let destino = Square::new(coluna, lance.from.rank());
        return format!("{}{}", lance.from, destino);
    }
    // O `Display` da biblioteca já escreve `e2e4` e `e7e8q`, com a letra
    // minúscula da peça na promoção.
    lance.to_string()
}

/// Todos os lances legais do tabuleiro, no formato da `cozy-chess`, na ordem
/// em que a biblioteca os gera. Essa ordem é fixa para a versão travada, e é
/// a base da "ordem estável" da busca (R-05).
pub fn lances_legais(tabuleiro: &Board) -> Vec<Move> {
    let mut lista = Vec::with_capacity(64);
    // `generate_moves` chama a função dada uma vez por PEÇA, com todos os
    // destinos dela; devolver `false` quer dizer "continue gerando".
    tabuleiro.generate_moves(|movimentos| {
        lista.extend(movimentos);
        false
    });
    lista
}

/// A chave de uma posição para a repetição (ver o topo do arquivo): o `hash()`
/// da biblioteca quando a captura en passant é legal, o `hash_without_ep()`
/// quando não é.
pub fn chave_da_posicao(tabuleiro: &Board) -> u64 {
    if en_passant_possivel(tabuleiro) {
        tabuleiro.hash()
    } else {
        tabuleiro.hash_without_ep()
    }
}

/// Diz se existe, agora, uma captura en passant **legal**.
fn en_passant_possivel(tabuleiro: &Board) -> bool {
    let Some(coluna) = tabuleiro.en_passant() else {
        return false;
    };
    let lado = tabuleiro.side_to_move();
    // A casa de destino da captura: a 6ª fileira de quem joga (a 3ª das
    // pretas, vista pelas brancas). `relative_to` faz essa troca pela cor.
    let casa_alvo = Square::new(coluna, Rank::Sixth.relative_to(lado));
    let peoes = tabuleiro.colored_pieces(lado, Piece::Pawn);
    let mut possivel = false;
    // Gera só os lances dos peões de quem joga (o primeiro argumento é a
    // máscara das peças) e procura um que vá à casa do en passant.
    tabuleiro.generate_moves_for(peoes, |movimentos| {
        if movimentos.to.has(casa_alvo) {
            possivel = true;
        }
        possivel // `true` interrompe a geração: já sabemos a resposta.
    });
    possivel
}

/// O perft: quantas sequências de lances legais existem a partir da posição,
/// com exatamente `profundidade` meios-lances.
///
/// É a prova de que o gerador de lances está certo (RF-XDR-034, R-12): os
/// números de posições conhecidas são públicos, e um único lance a mais ou a
/// menos, em qualquer canto da árvore, muda o total. Fica fora da busca de
/// propósito: ele conta, não escolhe.
pub fn perft(tabuleiro: &Board, profundidade: u32) -> u64 {
    if profundidade == 0 {
        return 1;
    }
    let mut total: u64 = 0;
    if profundidade == 1 {
        // Contagem "em bloco": na última profundidade não é preciso jogar os
        // lances, só contar quantos há. `len()` conta inclusive as quatro
        // promoções de cada peão que chega ao fim.
        tabuleiro.generate_moves(|movimentos| {
            total += movimentos.len() as u64;
            false
        });
        return total;
    }
    tabuleiro.generate_moves(|movimentos| {
        for lance in movimentos {
            // `clone()` copia o tabuleiro (um punhado de bytes): jogar numa
            // cópia evita ter de "desfazer" o lance depois.
            let mut depois = tabuleiro.clone();
            depois.play_unchecked(lance);
            total += perft(&depois, profundidade - 1);
        }
        false
    });
    total
}

/// Nome da cor de quem joga, no vocabulário da fronteira (`branca`/`preta`).
pub fn nome_da_cor(cor: Color) -> &'static str {
    match cor {
        Color::White => "branca",
        Color::Black => "preta",
    }
}
