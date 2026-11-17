//! O motivo de um gesto que não é lance legal (research.md R-14;
//! `contracts/motor-xadrez.md` §2.3, operação `recusa`).
//!
//! A pessoa arrasta uma peça para uma casa onde ela não pode ir. A tela pergunta
//! ao motor **por quê**, e o motor devolve UM código; o texto que a pessoa lê é
//! dos `.arb`. O código também vai para o log (`tb901_regra_recusa`), e é por
//! isso que a lista de códigos é exposta em [`CODIGOS`]: a dimensão do banco
//! nasce com os códigos que ESTE arquivo emite, conferidos por teste (a lição da
//! migração 0012 das damas: "as dimensões vêm do motor, não do documento").
//!
//! ## A prioridade
//!
//! Um gesto pode estar errado por mais de um motivo (um bispo cravado que tenta
//! andar como cavalo). A pessoa recebe o motivo mais "de base" primeiro: é a
//! peça dela? a peça anda assim? o caminho está livre? a casa está livre? Só
//! quando o gesto seria um lance normal é que sobra a explicação do rei em xeque.
//!
//! | ordem | código | quando |
//! |---|---|---|
//! | 1 | `nao_e_sua_peca` | a peça da origem é do adversário |
//! | 2 | os quatro do roque | o rei anda duas colunas na 1ª fileira (abaixo) |
//! | 3 | `peca_nao_anda_assim` | a peça não chega lá nem com o tabuleiro vazio (o peão na diagonal só para comer) |
//! | 4 | `caminho_bloqueado` | há peça no caminho (o peão: também na casa da frente) |
//! | 5 | `casa_ocupada_por_peca_sua` | o destino tem uma peça sua |
//! | 6 | `rei_em_xeque` | o seu rei está em xeque, e o lance não o tira de lá |
//! | 7 | `rei_ficaria_em_xeque` | o lance deixaria o seu rei em xeque (peça cravada, ou o rei indo a casa atacada) |
//!
//! No roque, a ordem é: `roque_sem_direito` → `roque_caminho_ocupado` →
//! `roque_com_rei_em_xeque` → `roque_atravessa_casa_atacada`; e se só a casa
//! FINAL do rei estiver atacada, `rei_ficaria_em_xeque` (é o xeque de sempre).
//!
//! E o 11º, `peca_sem_lance`: o toque numa peça sem destino nenhum (o pedido
//! sem `para`), quando ela não tem nem lance "de geometria" - a peça presa atrás
//! das outras. Se ela tem lances de geometria e todos deixariam o rei em xeque, o
//! motivo é o do rei (6 ou 7), que é o que ensina alguma coisa.

use cozy_chess::{get_between_rays, get_bishop_rays, get_king_moves, get_knight_moves, get_rook_rays};
use cozy_chess::{BitBoard, Board, Color, File, Piece, Rank, Square};

use crate::posicao::{atacantes_da_casa, lance_do_texto};

/// Os onze motivos de recusa.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Regra {
    NaoESuaPeca,
    PecaNaoAndaAssim,
    CaminhoBloqueado,
    CasaOcupadaPorPecaSua,
    ReiEmXeque,
    ReiFicariaEmXeque,
    RoqueSemDireito,
    RoqueComReiEmXeque,
    RoqueAtravessaCasaAtacada,
    RoqueCaminhoOcupado,
    PecaSemLance,
}

impl Regra {
    /// O código da fronteira e do log.
    pub fn codigo(self) -> &'static str {
        match self {
            Regra::NaoESuaPeca => "nao_e_sua_peca",
            Regra::PecaNaoAndaAssim => "peca_nao_anda_assim",
            Regra::CaminhoBloqueado => "caminho_bloqueado",
            Regra::CasaOcupadaPorPecaSua => "casa_ocupada_por_peca_sua",
            Regra::ReiEmXeque => "rei_em_xeque",
            Regra::ReiFicariaEmXeque => "rei_ficaria_em_xeque",
            Regra::RoqueSemDireito => "roque_sem_direito",
            Regra::RoqueComReiEmXeque => "roque_com_rei_em_xeque",
            Regra::RoqueAtravessaCasaAtacada => "roque_atravessa_casa_atacada",
            Regra::RoqueCaminhoOcupado => "roque_caminho_ocupado",
            Regra::PecaSemLance => "peca_sem_lance",
        }
    }
}

/// Todas as regras, na ordem da tabela da `tb901_regra_recusa`.
pub const TODAS: [Regra; 11] = [
    Regra::NaoESuaPeca,
    Regra::PecaNaoAndaAssim,
    Regra::CaminhoBloqueado,
    Regra::CasaOcupadaPorPecaSua,
    Regra::ReiEmXeque,
    Regra::ReiFicariaEmXeque,
    Regra::RoqueSemDireito,
    Regra::RoqueComReiEmXeque,
    Regra::RoqueAtravessaCasaAtacada,
    Regra::RoqueCaminhoOcupado,
    Regra::PecaSemLance,
];

/// Os códigos que este módulo emite: a fonte da dimensão `tb901_regra_recusa`
/// (a T066 compara esta lista com a migração).
pub fn codigos() -> Vec<&'static str> {
    TODAS.iter().map(|r| r.codigo()).collect()
}

/// Quando não há motivo a dar.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SemMotivo {
    /// O pedido não descreve um gesto (origem vazia, origem igual ao destino).
    PedidoInvalido(String),
    /// O gesto É um lance legal (ou, sem `para`, a peça tem lance legal).
    LanceLegal,
}

/// O motivo de o gesto `de` → `para` não ser lance legal. Sem `para`, a pergunta
/// é "por que essa peça não tem lance?".
pub fn motivo_da_recusa(tabuleiro: &Board, de: Square, para: Option<Square>) -> Result<Regra, SemMotivo> {
    let lado = tabuleiro.side_to_move();
    let Some(peca) = tabuleiro.piece_on(de) else {
        return Err(SemMotivo::PedidoInvalido(format!("nao ha peca em {de}")));
    };
    if tabuleiro.color_on(de) != Some(lado) {
        return Ok(Regra::NaoESuaPeca);
    }
    let em_xeque = !tabuleiro.checkers().is_empty();

    let Some(para) = para else {
        // O toque numa peça, sem destino.
        if tem_lance_legal(tabuleiro, de) {
            return Err(SemMotivo::LanceLegal);
        }
        // Algum destino passaria pela geometria, caminho e casa livre? Então o
        // que prende a peça é o rei.
        let tem_lance_de_geometria = Square::ALL
            .into_iter()
            .any(|casa| casa != de && motivo_de_geometria(tabuleiro, peca, de, casa).is_none());
        return Ok(if !tem_lance_de_geometria {
            Regra::PecaSemLance
        } else if em_xeque {
            Regra::ReiEmXeque
        } else {
            Regra::ReiFicariaEmXeque
        });
    };

    if de == para {
        return Err(SemMotivo::PedidoInvalido(String::from("origem igual ao destino")));
    }
    if e_lance_legal(tabuleiro, de, para) {
        return Err(SemMotivo::LanceLegal);
    }
    if peca == Piece::King && e_gesto_de_roque(lado, de, para) {
        return Ok(motivo_do_roque(tabuleiro, de, para));
    }
    if let Some(regra) = motivo_de_geometria(tabuleiro, peca, de, para) {
        return Ok(regra);
    }
    // O gesto é um lance "de geometria" e mesmo assim não é legal: só pode ser
    // o rei. Se é o próprio rei que anda, ele iria para uma casa atacada.
    Ok(if peca != Piece::King && em_xeque {
        Regra::ReiEmXeque
    } else {
        Regra::ReiFicariaEmXeque
    })
}

/// Algum lance legal sai de `de` e chega a `para`? Tenta sem promoção e com as
/// quatro, porque o gesto não diz a peça.
fn e_lance_legal(tabuleiro: &Board, de: Square, para: Square) -> bool {
    ["", "q", "r", "b", "n"]
        .iter()
        .any(|letra| lance_do_texto(tabuleiro, &format!("{de}{para}{letra}")).is_some())
}

/// A peça em `de` tem algum lance legal?
fn tem_lance_legal(tabuleiro: &Board, de: Square) -> bool {
    let mut tem = false;
    // Gera só os lances da peça daquela casa; `true` interrompe a geração.
    tabuleiro.generate_moves_for(de.bitboard(), |movimentos| {
        tem = !movimentos.is_empty();
        tem
    });
    tem
}

/// O rei andando duas colunas na própria 1ª fileira: é assim que a pessoa
/// pede o roque (e o que a fronteira chama de `e1g1`/`e1c1`).
fn e_gesto_de_roque(lado: Color, de: Square, para: Square) -> bool {
    let primeira = Rank::First.relative_to(lado);
    de.rank() == primeira
        && para.rank() == primeira
        && (de.file() as i32 - para.file() as i32).abs() == 2
}

/// O motivo de um roque que não pode ser feito (a ordem está no topo).
fn motivo_do_roque(tabuleiro: &Board, de: Square, para: Square) -> Regra {
    let lado = tabuleiro.side_to_move();
    let curto = para.file() > de.file();
    let direitos = tabuleiro.castle_rights(lado);
    let coluna_da_torre = if curto { direitos.short } else { direitos.long };
    let Some(coluna_da_torre) = coluna_da_torre else {
        return Regra::RoqueSemDireito;
    };
    let fileira = de.rank();
    let torre = Square::new(coluna_da_torre, fileira);
    // Onde o rei e a torre terminam (G e F no curto, C e D no longo).
    let (coluna_do_rei, coluna_final_da_torre) = if curto { (File::G, File::F) } else { (File::C, File::D) };
    let rei_final = Square::new(coluna_do_rei, fileira);
    let torre_final = Square::new(coluna_final_da_torre, fileira);

    // As casas que têm de estar vazias: as entre o rei e a torre, e as duas de
    // chegada - sem contar o próprio rei e a própria torre.
    let precisam_vazias =
        (get_between_rays(de, torre) | rei_final.bitboard() | torre_final.bitboard()) & !(de.bitboard() | torre.bitboard());
    if !(precisam_vazias & tabuleiro.occupied()).is_empty() {
        return Regra::RoqueCaminhoOcupado;
    }
    if !tabuleiro.checkers().is_empty() {
        return Regra::RoqueComReiEmXeque;
    }
    // O rei sai da ocupação: ele não se protege com o próprio corpo.
    let ocupacao = tabuleiro.occupied() & !de.bitboard();
    let atacada = |casa: Square| !atacantes_da_casa(tabuleiro, casa, !lado, ocupacao).is_empty();
    // As casas por onde o rei PASSA (sem a de chegada).
    for casa in get_between_rays(de, rei_final) {
        if atacada(casa) {
            return Regra::RoqueAtravessaCasaAtacada;
        }
    }
    // Sobrou a casa de chegada (o roque legal não chega aqui: quem chama já
    // conferiu que o gesto não é lance legal).
    Regra::ReiFicariaEmXeque
}

/// O motivo "de base" de um gesto que não fosse um roque: a peça não anda
/// assim, o caminho está bloqueado, ou a casa tem peça sua. `None` quando o
/// gesto passa por esses três (sobra o rei).
fn motivo_de_geometria(tabuleiro: &Board, peca: Piece, de: Square, para: Square) -> Option<Regra> {
    let lado = tabuleiro.side_to_move();
    let ocupadas = tabuleiro.occupied();
    // As casas que precisam estar vazias no caminho (sem a de destino).
    let caminho: BitBoard = match peca {
        Piece::Knight if get_knight_moves(de).has(para) => BitBoard::EMPTY,
        Piece::King if get_king_moves(de).has(para) => BitBoard::EMPTY,
        Piece::Bishop if get_bishop_rays(de).has(para) => get_between_rays(de, para),
        Piece::Rook if get_rook_rays(de).has(para) => get_between_rays(de, para),
        Piece::Queen if (get_bishop_rays(de) | get_rook_rays(de)).has(para) => get_between_rays(de, para),
        Piece::Pawn => return motivo_do_peao(tabuleiro, de, para),
        _ => return Some(Regra::PecaNaoAndaAssim),
    };
    if !(caminho & ocupadas).is_empty() {
        return Some(Regra::CaminhoBloqueado);
    }
    if tabuleiro.color_on(para) == Some(lado) {
        return Some(Regra::CasaOcupadaPorPecaSua);
    }
    None
}

/// O peão é a única peça que anda de um jeito e come de outro.
fn motivo_do_peao(tabuleiro: &Board, de: Square, para: Square) -> Option<Regra> {
    let lado = tabuleiro.side_to_move();
    // As colunas e fileiras vistas por quem joga: para as pretas, "para a
    // frente" é descer. `relative_to` espelha a casa quando a cor é a preta.
    let de_rel = de.relative_to(lado);
    let para_rel = para.relative_to(lado);
    let avanco = para_rel.rank() as i32 - de_rel.rank() as i32;
    let lateral = (para.file() as i32 - de.file() as i32).abs();

    if lateral == 0 && (avanco == 1 || (avanco == 2 && de_rel.rank() == Rank::Second)) {
        // Para a frente: o peão não come para a frente, então qualquer peça no
        // caminho ou no destino o bloqueia.
        let caminho = get_between_rays(de, para) | para.bitboard();
        if !(caminho & tabuleiro.occupied()).is_empty() {
            return Some(Regra::CaminhoBloqueado);
        }
        return None;
    }
    if lateral == 1 && avanco == 1 {
        if tabuleiro.color_on(para) == Some(lado) {
            return Some(Regra::CasaOcupadaPorPecaSua);
        }
        // Na diagonal só para comer: uma peça adversária, ou o en passant.
        let casa_do_en_passant = tabuleiro
            .en_passant()
            .map(|coluna| Square::new(coluna, Rank::Sixth.relative_to(lado)));
        if tabuleiro.piece_on(para).is_some() || casa_do_en_passant == Some(para) {
            return None;
        }
    }
    Some(Regra::PecaNaoAndaAssim)
}
