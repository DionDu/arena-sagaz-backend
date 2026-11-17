//! O Radar: as peças de um lado que o adversário pode comer agora
//! (research.md R-15; `contracts/motor-xadrez.md` §2.6, operação `radar`).
//!
//! O poder mostra por alguns segundos as peças da pessoa que estão "penduradas"
//! (RF-XDR-151). A conta:
//!
//! - **é a vez do adversário**: as capturas legais dele, na posição de agora;
//! - **é a vez do próprio lado, fora de xeque**: a vez é trocada (o "lance nulo"
//!   da `cozy-chess`, `null_move`) e valem as capturas legais do adversário
//!   nessa posição - "se eu passasse a vez, o que ele comeria?";
//! - **é a vez do próprio lado, em xeque**: a vez não pode ser trocada (o
//!   adversário capturaria o rei). Valem então os ATAQUES do adversário, sem
//!   conferir se a peça atacante está cravada - a mesma resposta em quase toda
//!   posição real.
//!
//! O rei nunca entra: o xeque já tem a sua marca (RF-XDR-123). No en passant, a
//! peça ameaçada é o peão que seria comido, e não a casa vazia de destino.

use cozy_chess::{BitBoard, Board, Color, Piece};

use crate::fatos::fatos_do_lance;
use crate::posicao::{atacantes_da_casa, lances_legais};

/// As casas das peças de `lado` (sem o rei) que o adversário pode comer agora.
/// Sai como conjunto de casas, que se lê em ordem fixa (`a1` ... `h8`).
pub fn radar(tabuleiro: &Board, lado: Color) -> BitBoard {
    let minhas_sem_rei = tabuleiro.colors(lado) & !tabuleiro.pieces(Piece::King);

    if tabuleiro.side_to_move() == lado {
        // `null_move` devolve `None` quando o lado está em xeque.
        match tabuleiro.null_move() {
            Some(vez_trocada) => capturas_de_quem_joga(&vez_trocada) & minhas_sem_rei,
            None => {
                let ocupacao = tabuleiro.occupied();
                let mut ameacadas = BitBoard::EMPTY;
                for casa in minhas_sem_rei {
                    if !atacantes_da_casa(tabuleiro, casa, !lado, ocupacao).is_empty() {
                        ameacadas |= casa.bitboard();
                    }
                }
                ameacadas
            }
        }
    } else {
        capturas_de_quem_joga(tabuleiro) & minhas_sem_rei
    }
}

/// As casas das peças que quem joga pode comer com um lance legal (a casa da
/// peça comida, que no en passant não é o destino).
fn capturas_de_quem_joga(tabuleiro: &Board) -> BitBoard {
    let mut comidas = BitBoard::EMPTY;
    for lance in lances_legais(tabuleiro) {
        // Um lance de quem joga que termina em peça do outro, ou o en passant.
        // `fatos_do_lance` já sabe achar a casa da comida nos dois casos (e não
        // confunde o roque, em que o rei "vai" para a casa da própria torre).
        let alvo_ocupado = tabuleiro.color_on(lance.to) == Some(!tabuleiro.side_to_move());
        let peao_na_diagonal = tabuleiro.piece_on(lance.from) == Some(Piece::Pawn)
            && lance.from.file() != lance.to.file();
        if alvo_ocupado || peao_na_diagonal {
            let (fatos, _) = fatos_do_lance(tabuleiro, lance);
            if let Some((_, casa)) = fatos.comida {
                comidas |= casa.bitboard();
            }
        }
    }
    comidas
}
