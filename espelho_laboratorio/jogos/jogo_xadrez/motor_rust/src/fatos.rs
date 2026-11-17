//! Os fatos de um lance e as peças marcadas - espiã, alvo, corte, dama
//! (research.md R-13; `contracts/motor-xadrez.md` §2.2, operação `aplicar`).
//!
//! ## Por que os fatos moram no motor
//!
//! A tela ("o que acabou de acontecer"), o juiz do desafio (no app em Dart e no
//! job em Python) e as conquistas precisam saber o que um lance FEZ: que peça
//! andou, o que comeu e onde, se deu xeque e quem deu. Se cada um calculasse por
//! conta própria, seriam três escritas de uma conta que erra justamente nos
//! casos raros - o roque (a torre também anda), o en passant (a peça comida não
//! está na casa de destino) e a promoção (a peça que chega não é a que saiu).
//! O Rust já é a única fonte das regras (pergunta J): a conta fica aqui, uma vez.
//!
//! ## As peças marcadas
//!
//! O pedido pode trazer um mapa nome → casa (`{"espia": "c3", "alvo": "f6"}`). O
//! motor devolve o mesmo mapa DEPOIS do lance, seguindo cada peça pela sua
//! identidade: a torre do roque vai junto com o rei, o peão promovido continua
//! marcado na peça nova, e a peça comida vira `null`. Por marca, diz também se
//! ela **comeu** neste lance e se **deu xeque** - inclusive o xeque descoberto, em
//! que outra peça abriu o caminho (a regra é "a casa da marca está entre as que
//! atacam o rei", RF-XDR-195).

use std::collections::BTreeMap;

use cozy_chess::{Board, File, Move, Piece, Square};
use serde_json::{json, Map, Value};

use crate::posicao::{nome_da_peca, nomes_das_casas, texto_do_lance};

/// O roque de um lance: o lado e o deslocamento da torre.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Roque {
    /// `true` no roque curto (para o lado do rei), `false` no longo.
    pub curto: bool,
    pub torre_de: Square,
    pub torre_para: Square,
}

/// O que um lance fez. As casas são as da notação da fronteira: no roque, o
/// `para` é a casa onde o REI termina (`g1`), e não a da torre.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Fatos {
    /// A peça que andou (no roque, o rei; na promoção, o peão).
    pub peca_movida: Piece,
    pub de: Square,
    pub para: Square,
    /// A peça comida e a casa em que ela ESTAVA (no en passant, a casa do peão
    /// comido, que não é o destino).
    pub comida: Option<(Piece, Square)>,
    /// A peça que nasceu da promoção.
    pub promocao: Option<Piece>,
    pub roque: Option<Roque>,
    pub en_passant: bool,
    /// As casas das peças que dão xeque no rei adversário DEPOIS do lance (duas
    /// no xeque duplo; a da peça que abriu caminho NÃO entra, só a que ataca).
    pub xeque_por: Vec<Square>,
}

/// Calcula os fatos de um lance legal. Recebe o tabuleiro ANTES do lance e o
/// lance no formato da biblioteca (o roque como "o rei captura a torre"), e
/// devolve os fatos e o tabuleiro DEPOIS.
pub fn fatos_do_lance(antes: &Board, lance: Move) -> (Fatos, Board) {
    let lado = antes.side_to_move();
    // `expect`: um lance legal sempre sai de uma casa com peça; se não sair, é
    // defeito de quem chamou, e o `catch_unwind` da borda transforma em erro.
    let peca_movida = antes.piece_on(lance.from).expect("lance legal sai de uma casa com peca");

    // O roque, no formato da biblioteca: o rei "vai" para a casa da própria torre.
    let e_roque = peca_movida == Piece::King && antes.color_on(lance.to) == Some(lado);
    let roque = e_roque.then(|| {
        // `then` devolve `Some(valor)` quando a condição é verdadeira.
        let curto = lance.to.file() > lance.from.file();
        let fileira = lance.from.rank();
        // A torre termina ao lado do rei, do lado de dentro: F no curto, D no longo.
        let coluna_final = if curto { File::F } else { File::D };
        Roque {
            curto,
            torre_de: lance.to,
            torre_para: Square::new(coluna_final, fileira),
        }
    });

    // O en passant: o peão anda na diagonal para uma casa VAZIA. É o único lance
    // em que isso acontece, então não é preciso olhar a marca de en passant.
    let en_passant = peca_movida == Piece::Pawn
        && lance.from.file() != lance.to.file()
        && antes.piece_on(lance.to).is_none();

    let comida = if en_passant {
        // O peão comido está ao lado da casa de origem, na coluna do destino:
        // mesma fileira de onde o peão que come partiu.
        let casa = Square::new(lance.to.file(), lance.from.rank());
        Some((Piece::Pawn, casa))
    } else if e_roque {
        None
    } else {
        // `map` aplica a função só quando há peça no destino.
        antes.piece_on(lance.to).map(|peca| (peca, lance.to))
    };

    // O destino na notação da fronteira (o rei do roque termina em G ou C).
    let texto = texto_do_lance(antes, lance);
    // `[2..4]` são os caracteres do destino; o `parse` não falha porque o texto
    // veio da própria biblioteca.
    let para: Square = texto[2..4].parse().expect("casa escrita pela biblioteca");

    let mut depois = antes.clone();
    depois.play(lance);
    let xeque_por: Vec<Square> = depois.checkers().into_iter().collect();

    let fatos = Fatos {
        peca_movida,
        de: lance.from,
        para,
        comida,
        promocao: lance.promotion,
        roque,
        en_passant,
        xeque_por,
    };
    (fatos, depois)
}

impl Fatos {
    /// O objeto `fatos` do §2.2, sem o `fim` (quem tem o histórico para contar
    /// a repetição é o despachante, que o acrescenta).
    pub fn em_json(&self) -> Value {
        json!({
            "peca_movida": nome_da_peca(self.peca_movida),
            "de": self.de.to_string(),
            "para": self.para.to_string(),
            "comida": self.comida.map(|(peca, casa)| json!({
                "peca": nome_da_peca(peca),
                "casa": casa.to_string(),
            })),
            "promocao": self.promocao.map(nome_da_peca),
            "roque": self.roque.map(|r| json!({
                "lado": if r.curto { "curto" } else { "longo" },
                "torre_de": r.torre_de.to_string(),
                "torre_para": r.torre_para.to_string(),
            })),
            "en_passant": self.en_passant,
            "xeque_por": nomes_das_casas(self.xeque_por.iter().fold(
                cozy_chess::BitBoard::EMPTY,
                // `fold` junta as casas num conjunto, que sai em ordem fixa.
                |conjunto, casa| conjunto | casa.bitboard(),
            )),
        })
    }

    /// A casa em que a peça que estava em `casa` ANTES do lance está DEPOIS
    /// dele, ou `None` se ela foi comida. Uma casa vazia antes continua "sem
    /// peça" (`None`); quem chama confere isso antes.
    pub fn casa_depois(&self, casa: Square) -> Option<Square> {
        if Some(casa) == self.comida.map(|(_, c)| c) {
            return None;
        }
        if casa == self.de {
            return Some(self.para);
        }
        if let Some(roque) = self.roque {
            if casa == roque.torre_de {
                return Some(roque.torre_para);
            }
        }
        Some(casa)
    }
}

/// Uma marca depois do lance (§2.2).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MarcaDepois {
    /// Onde a peça marcada está agora; `None` se foi comida (neste lance ou antes).
    pub casa: Option<Square>,
    /// A peça marcada foi a que andou, e comeu.
    pub comeu: bool,
    /// A casa da peça marcada está entre as que dão xeque (inclusive no xeque
    /// descoberto, RF-XDR-195).
    pub deu_xeque: bool,
}

/// Segue as marcas pelo lance. `marcas` traz, por nome, a casa ANTES do lance
/// (`None` = a peça já tinha sido comida).
pub fn seguir_marcas(
    marcas: &BTreeMap<String, Option<Square>>,
    fatos: &Fatos,
) -> BTreeMap<String, MarcaDepois> {
    marcas
        .iter()
        .map(|(nome, casa_antes)| {
            // `and_then` encadeia: sem casa antes, sem casa depois.
            let casa = casa_antes.and_then(|c| fatos.casa_depois(c));
            let andou = *casa_antes == Some(fatos.de);
            let marca = MarcaDepois {
                casa,
                comeu: andou && fatos.comida.is_some(),
                deu_xeque: casa.map_or(false, |c| fatos.xeque_por.contains(&c)),
            };
            (nome.clone(), marca)
        })
        .collect()
}

/// O mapa de marcas no formato do §2.2.
pub fn marcas_em_json(marcas: &BTreeMap<String, MarcaDepois>) -> Value {
    let mut mapa = Map::new();
    for (nome, marca) in marcas {
        mapa.insert(
            nome.clone(),
            json!({
                "casa": marca.casa.map(|c| c.to_string()),
                "comeu": marca.comeu,
                "deu_xeque": marca.deu_xeque,
            }),
        );
    }
    Value::Object(mapa)
}
