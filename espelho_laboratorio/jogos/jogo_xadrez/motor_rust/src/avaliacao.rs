//! A avaliação de uma posição, em centipeões inteiros (research.md R-07).
//!
//! ⚠️ **Escrito do zero; nenhuma tabela de terceiros (nem Stockfish, nem PeSTO).**
//! Cada número das tabelas abaixo foi escrito por nós, a partir dos princípios que
//! qualquer livro de iniciante dá: ocupe o centro, desenvolva as peças menores,
//! avance os peões (mais ainda no final), ponha a torre na 7ª, guarde o rei atrás
//! dos peões no meio-jogo e traga-o para o centro no final. A avaliação é o
//! coração da força do Magno, e uma cópia sem licença seria um problema que só se
//! descobre tarde. Os números se afinam na calibração (T051), e mexer neles muda os
//! lances: sobe a versão do `Cargo.toml`.
//!
//! Um centipeão é um centésimo de peão: +100 quer dizer "um peão a mais", e é a
//! unidade de toda nota do motor. Inteiro (`i32`), nunca ponto flutuante: a mesma
//! posição tem de dar a mesma nota em qualquer processador (R-05).
//!
//! ## Como a nota é montada
//!
//! 1. **Material**: o valor de cada peça (o mesmo no meio-jogo e no final).
//! 2. **Peça por casa**: cada peça ganha (ou perde) alguns centipeões conforme a
//!    casa onde está. São DUAS tabelas por peça: uma para o meio-jogo e uma para o
//!    final, porque o lugar bom muda (o rei, sobretudo).
//! 3. **A fase**: quanto de "meio-jogo" ainda há no tabuleiro, de 24 (todas as
//!    peças) a 0 (só reis e peões). A nota de casa é a mistura das duas tabelas,
//!    na proporção da fase, com **divisão inteira**:
//!    `(meio × fase + final × (24 − fase)) / 24`.
//!
//! ## As tabelas, como se leem
//!
//! Cada tabela está escrita **do ponto de vista das brancas, como o tabuleiro
//! impresso num livro**: a 1ª linha do texto é a 8ª fileira (a casa a8 à
//! esquerda), a última é a 1ª fileira (a1 à esquerda). Para as pretas, a mesma
//! tabela vale espelhada de cima para baixo (a 7ª fileira delas é a nossa 2ª). É
//! esse espelho que faz a posição com as cores trocadas valer exatamente o oposto
//! (o teste `tests/avaliacao.rs` cobra).

use cozy_chess::{Board, Color, Piece, Square};

/// O valor de cada peça, em centipeões (R-07). O rei não tem valor de material:
/// ele nunca sai do tabuleiro, e perdê-lo é o mate, que a busca pontua à parte.
pub const fn valor_da_peca(peca: Piece) -> i32 {
    match peca {
        Piece::Pawn => 100,
        Piece::Knight => 320,
        Piece::Bishop => 330,
        Piece::Rook => 500,
        Piece::Queen => 900,
        Piece::King => 0,
    }
}

/// A fase do tabuleiro cheio: 4 peças menores × 1 + 4 torres × 2 + 2 damas × 4
/// (dos dois lados juntos). Com promoções a soma poderia passar disto; ela é
/// travada aqui (ver [`fase`]).
pub const FASE_CHEIA: i32 = 24;

/// Quanto cada peça pesa na fase. Peão e rei não contam: um final de rei e peões
/// é final, por mais peões que haja.
const fn peso_na_fase(peca: Piece) -> i32 {
    match peca {
        Piece::Knight | Piece::Bishop => 1,
        Piece::Rook => 2,
        Piece::Queen => 4,
        Piece::Pawn | Piece::King => 0,
    }
}

/// As seis peças, na ordem fixa em que são somadas (a ordem não muda a soma,
/// mas fixá-la deixa o código igual ao que se lê).
const TODAS_AS_PECAS: [Piece; 6] = [
    Piece::Pawn,
    Piece::Knight,
    Piece::Bishop,
    Piece::Rook,
    Piece::Queen,
    Piece::King,
];

// ---------------------------------------------------------------------------
// As tabelas. `[i32; 64]` é um vetor de tamanho fixo com 64 inteiros. Cada linha
// do texto é uma fileira, da 8ª (em cima) à 1ª (embaixo), da coluna a à h.
// ---------------------------------------------------------------------------

/// Peão, meio-jogo: os centrais avançados valem mais; d2/e2 parados atrapalham o
/// desenvolvimento; f2/g2/h2 ficam (são o abrigo do rei roqueado), e f3 abre o rei.
#[rustfmt::skip]
const PEAO_MEIO: [i32; 64] = [
     0,   0,   0,   0,   0,   0,   0,   0,
    60,  60,  65,  70,  70,  65,  60,  60,
    25,  25,  30,  40,  40,  30,  25,  25,
     8,  10,  15,  28,  28,  15,  10,   8,
     2,   4,  10,  22,  22,  10,   4,   2,
     4,   2,   4,  10,  10,  -4,   0,   2,
     0,   0,   0, -12, -12,   6,   6,   4,
     0,   0,   0,   0,   0,   0,   0,   0,
];

/// Peão, final: só importa o quanto ele andou; cada fileira a mais vale mais que
/// a anterior, porque a promoção fica mais perto.
#[rustfmt::skip]
const PEAO_FINAL: [i32; 64] = [
     0,   0,   0,   0,   0,   0,   0,   0,
    90,  90,  90,  90,  90,  90,  90,  90,
    55,  55,  55,  55,  55,  55,  55,  55,
    32,  32,  32,  32,  32,  32,  32,  32,
    18,  18,  18,  18,  18,  18,  18,  18,
     8,   8,   8,   8,   8,   8,   8,   8,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
];

/// Cavalo, meio-jogo: "cavalo na borda, cavalo sem graça". O centro vale muito,
/// as bordas e os cantos perdem, e o cavalo parado na 1ª fileira não ajuda.
#[rustfmt::skip]
const CAVALO_MEIO: [i32; 64] = [
   -45, -30, -20, -15, -15, -20, -30, -45,
   -30, -12,   0,   4,   4,   0, -12, -30,
   -18,   4,  14,  18,  18,  14,   4, -18,
   -14,   6,  18,  24,  24,  18,   6, -14,
   -14,   4,  16,  22,  22,  16,   4, -14,
   -18,   2,  12,  12,  12,  12,   2, -18,
   -30, -12,   0,   4,   4,   0, -12, -30,
   -45, -26, -20, -16, -16, -20, -26, -45,
];

/// Cavalo, final: o mesmo desenho, mais achatado (o centro ainda é melhor).
#[rustfmt::skip]
const CAVALO_FINAL: [i32; 64] = [
   -35, -24, -16, -12, -12, -16, -24, -35,
   -24, -10,  -2,   2,   2,  -2, -10, -24,
   -16,   0,   8,  12,  12,   8,   0, -16,
   -12,   2,  12,  16,  16,  12,   2, -12,
   -12,   2,  12,  16,  16,  12,   2, -12,
   -16,   0,   8,  12,  12,   8,   0, -16,
   -24, -10,  -2,   2,   2,  -2, -10, -24,
   -35, -24, -16, -12, -12, -16, -24, -35,
];

/// Bispo, meio-jogo: sair da 1ª fileira é o desenvolvimento; b2/g2 (o
/// fianqueto) e as grandes diagonais valem; o canto prende o bispo.
#[rustfmt::skip]
const BISPO_MEIO: [i32; 64] = [
   -18, -10, -10, -10, -10, -10, -10, -18,
   -10,   2,   0,   0,   0,   0,   2, -10,
    -8,   0,   6,   8,   8,   6,   0,  -8,
    -6,   6,   6,  10,  10,   6,   6,  -6,
    -6,   4,  10,  10,  10,  10,   4,  -6,
    -6,   8,   8,   8,   8,   8,   8,  -6,
    -8,  10,   2,   4,   4,   2,  10,  -8,
   -18,  -8, -12,  -8,  -8, -12,  -8, -18,
];

/// Bispo, final: o centro, de leve; nenhuma fileira é especial.
#[rustfmt::skip]
const BISPO_FINAL: [i32; 64] = [
   -12,  -8,  -6,  -4,  -4,  -6,  -8, -12,
    -8,  -2,   0,   2,   2,   0,  -2,  -8,
    -6,   0,   4,   6,   6,   4,   0,  -6,
    -4,   2,   6,   8,   8,   6,   2,  -4,
    -4,   2,   6,   8,   8,   6,   2,  -4,
    -6,   0,   4,   6,   6,   4,   0,  -6,
    -8,  -2,   0,   2,   2,   0,  -2,  -8,
   -12,  -8,  -6,  -4,  -4,  -6,  -8, -12,
];

/// Torre, meio-jogo: a 7ª fileira é o prêmio; na 1ª, as colunas centrais (onde
/// a torre chega depois do roque: f1 no curto, d1 no longo) valem mais que o canto.
#[rustfmt::skip]
const TORRE_MEIO: [i32; 64] = [
     4,   6,   6,   8,   8,   6,   6,   4,
    14,  18,  18,  18,  18,  18,  18,  14,
    -4,   0,   0,   2,   2,   0,   0,  -4,
    -6,   0,   0,   2,   2,   0,   0,  -6,
    -6,   0,   0,   2,   2,   0,   0,  -6,
    -6,   0,   0,   2,   2,   0,   0,  -6,
    -6,   0,   0,   2,   2,   0,   0,  -6,
    -2,   0,   4,   8,   8,   6,   0,  -2,
];

/// Torre, final: quase plana; a 7ª ainda vale (prende o rei e come peões).
#[rustfmt::skip]
const TORRE_FINAL: [i32; 64] = [
     4,   4,   4,   4,   4,   4,   4,   4,
    10,  10,  10,  10,  10,  10,  10,  10,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0,
];

/// Dama, meio-jogo: um centro discreto (dama exposta cedo é alvo) e as bordas
/// um pouco piores. Os números são pequenos de propósito.
#[rustfmt::skip]
const DAMA_MEIO: [i32; 64] = [
   -16, -10,  -8,  -4,  -4,  -8, -10, -16,
   -10,  -2,   0,   0,   0,   0,  -2, -10,
    -8,   0,   3,   3,   3,   3,   0,  -8,
    -4,   0,   3,   4,   4,   3,   0,  -4,
    -4,   0,   3,   4,   4,   3,   0,  -4,
    -8,   2,   3,   3,   3,   3,   0,  -8,
   -10,   0,   2,   0,   0,   0,   0, -10,
   -16, -10,  -6,   0,  -4,  -8, -10, -16,
];

/// Dama, final: centralizada, ela alcança o tabuleiro inteiro.
#[rustfmt::skip]
const DAMA_FINAL: [i32; 64] = [
   -14,  -8,  -6,  -4,  -4,  -6,  -8, -14,
    -8,  -2,   2,   4,   4,   2,  -2,  -8,
    -6,   2,   6,   8,   8,   6,   2,  -6,
    -4,   4,   8,  10,  10,   8,   4,  -4,
    -4,   4,   8,  10,  10,   8,   4,  -4,
    -6,   2,   6,   8,   8,   6,   2,  -6,
    -8,  -2,   2,   4,   4,   2,  -2,  -8,
   -14,  -8,  -6,  -4,  -4,  -6,  -8, -14,
];

/// Rei, meio-jogo: protegido. As casas do roque (g1 no curto, b1/c1 no longo)
/// são as melhores; o centro da 1ª fileira é pior; cada fileira a mais é perigo.
#[rustfmt::skip]
const REI_MEIO: [i32; 64] = [
   -60, -60, -65, -70, -70, -65, -60, -60,
   -50, -55, -60, -65, -65, -60, -55, -50,
   -45, -50, -55, -60, -60, -55, -50, -45,
   -40, -45, -50, -55, -55, -50, -45, -40,
   -30, -35, -40, -45, -45, -40, -35, -30,
   -16, -22, -26, -32, -32, -26, -22, -16,
     2,   0,  -8, -16, -16,  -8,   0,   2,
    14,  24,  12,  -4,   0,  -6,  26,  16,
];

/// Rei, final: ativo. Sem damas para dar mate, o rei é uma peça de ataque, e o
/// centro é onde ele alcança os dois lados.
#[rustfmt::skip]
const REI_FINAL: [i32; 64] = [
   -40, -28, -20, -16, -16, -20, -28, -40,
   -26, -10,  -2,   2,   2,  -2, -10, -26,
   -18,  -2,  10,  14,  14,  10,  -2, -18,
   -14,   2,  14,  22,  22,  14,   2, -14,
   -14,   2,  14,  22,  22,  14,   2, -14,
   -18,  -2,  10,  14,  14,  10,  -2, -18,
   -26, -10,  -2,   2,   2,  -2, -10, -26,
   -40, -28, -20, -16, -16, -20, -28, -40,
];

/// As duas tabelas (meio-jogo, final) de uma peça. Devolve referências (`&`)
/// para não copiar os 64 números a cada chamada.
const fn tabelas_da_peca(peca: Piece) -> (&'static [i32; 64], &'static [i32; 64]) {
    match peca {
        Piece::Pawn => (&PEAO_MEIO, &PEAO_FINAL),
        Piece::Knight => (&CAVALO_MEIO, &CAVALO_FINAL),
        Piece::Bishop => (&BISPO_MEIO, &BISPO_FINAL),
        Piece::Rook => (&TORRE_MEIO, &TORRE_FINAL),
        Piece::Queen => (&DAMA_MEIO, &DAMA_FINAL),
        Piece::King => (&REI_MEIO, &REI_FINAL),
    }
}

/// Em que linha da tabela (0 a 63) cai uma casa, para uma cor.
///
/// Na `cozy-chess`, as casas são numeradas de a1 = 0 a h8 = 63, fileira a fileira
/// (a1, b1, ..., h1, a2, ...). Nas tabelas, a 1ª linha do texto é a 8ª fileira.
/// - **Brancas**: a fileira `f` (0 = 1ª) fica na linha `7 − f` do texto. Isso é o
///   mesmo que `casa XOR 56` (56 = 0b111000 inverte os três bits da fileira e
///   deixa os três da coluna).
/// - **Pretas**: a tabela vale espelhada, então a fileira `f` delas cai na linha
///   `f` do texto, e o índice é a própria casa.
const fn indice_na_tabela(casa: Square, cor: Color) -> usize {
    let n = casa as usize;
    match cor {
        Color::White => n ^ 56,
        Color::Black => n,
    }
}

/// A fase do tabuleiro, de 0 (só reis e peões) a [`FASE_CHEIA`] (todas as peças).
/// Conta as peças das DUAS cores e trava no teto (promoções poderiam passar).
pub fn fase(tabuleiro: &Board) -> i32 {
    let mut soma = 0;
    for peca in TODAS_AS_PECAS {
        // `pieces(peca)` é o "bitboard" daquela peça, das duas cores: 64 bits,
        // um por casa, ligado onde ela está. `len()` conta os bits ligados.
        soma += tabuleiro.pieces(peca).len() as i32 * peso_na_fase(peca);
    }
    soma.min(FASE_CHEIA)
}

/// O material de uma cor: a soma dos valores das peças dela.
pub fn material(tabuleiro: &Board, cor: Color) -> i32 {
    let mut soma = 0;
    for peca in TODAS_AS_PECAS {
        let quantas = tabuleiro.colored_pieces(cor, peca).len() as i32;
        soma += quantas * valor_da_peca(peca);
    }
    soma
}

/// As notas de casa de uma cor: (soma no meio-jogo, soma no final).
fn notas_de_casa(tabuleiro: &Board, cor: Color) -> (i32, i32) {
    let mut meio = 0;
    let mut final_ = 0; // `final` é palavra reservada do Rust, daí o `_`.
    for peca in TODAS_AS_PECAS {
        let (tabela_meio, tabela_final) = tabelas_da_peca(peca);
        // Percorrer um bitboard com `for` visita cada casa ligada, da menor
        // (a1) para a maior (h8).
        for casa in tabuleiro.colored_pieces(cor, peca) {
            let i = indice_na_tabela(casa, cor);
            meio += tabela_meio[i];
            final_ += tabela_final[i];
        }
    }
    (meio, final_)
}

/// A nota do ponto de vista das **brancas**: positiva quando as brancas estão
/// melhor. É a conta "de verdade"; [`avaliar`] só acerta o sinal pela vez.
///
/// ⚠️ A divisão por [`FASE_CHEIA`] é inteira e o Rust a trunca **em direção a
/// zero** (−7 / 2 = −3, e não −4). É isso que garante a simetria exata: a posição
/// com as cores trocadas dá o mesmo número com o sinal trocado, sem um centipeão
/// de diferença pelo arredondamento.
pub fn avaliar_para_as_brancas(tabuleiro: &Board) -> i32 {
    let material_liquido = material(tabuleiro, Color::White) - material(tabuleiro, Color::Black);
    let (meio_b, final_b) = notas_de_casa(tabuleiro, Color::White);
    let (meio_p, final_p) = notas_de_casa(tabuleiro, Color::Black);
    let meio = meio_b - meio_p;
    let final_ = final_b - final_p;
    let f = fase(tabuleiro);
    // A mistura: com f = 24 vale só o meio-jogo; com f = 0, só o final.
    let casas = (meio * f + final_ * (FASE_CHEIA - f)) / FASE_CHEIA;
    material_liquido + casas
}

/// A nota da posição **do ponto de vista de quem joga agora**: positiva quando
/// quem tem a vez está melhor. É a convenção do negamax (`busca.rs`), em que
/// cada lado maximiza a própria nota e a do adversário é a mesma com o sinal
/// trocado. A resposta da fronteira (`avaliacao_brancas`, contrato §2.4) usa
/// [`avaliar_para_as_brancas`].
pub fn avaliar(tabuleiro: &Board) -> i32 {
    let nota = avaliar_para_as_brancas(tabuleiro);
    if tabuleiro.side_to_move() == Color::White {
        nota
    } else {
        -nota
    }
}
