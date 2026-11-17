//! O fim da partida e a ordem das regras (research.md R-04), e o **estado** que a
//! tela precisa para desenhar e aceitar o próximo toque (`contracts/motor-xadrez.md`
//! §2.1, operação `estado`).
//!
//! ## A ordem das regras
//!
//! | ordem | condição | resultado |
//! |---|---|---|
//! | 1 | sem lance legal e em xeque | xeque-mate |
//! | 2 | sem lance legal e fora de xeque | afogamento (empate) |
//! | 3 | material insuficiente (a lista curta) | empate |
//! | 4 | a mesma posição pela N-ésima vez | repetição (empate) |
//! | 5 | M meios-lances sem captura nem lance de peão | os "50 lances" (empate) |
//!
//! A ordem importa num caso só, e ele é da FIDE: o lance que completa os 50
//! lances **e dá mate** é mate. Por isso o mate vem antes.
//!
//! ## ⚠️ Os limites vêm da modalidade
//!
//! Os 3 da repetição e os 50 lances **não** estão escritos aqui: vêm de
//! `relogios_de_empate` no contrato (lidos em [`RegrasDoFim::da_modalidade`]). É
//! isso que a modalidade-sonda (T023) troca por 30 sem mudar uma linha deste
//! arquivo. Também é da modalidade QUAIS fins existem (a lista `fim`): um
//! empate que a modalidade não lista nunca é declarado.

use std::collections::BTreeMap;

use cozy_chess::{BitBoard, Board, Color, Piece};
use serde_json::{json, Value};

use crate::contrato::Modalidade;
use crate::posicao::{lances_legais, nome_da_cor, texto_do_lance, Posicao};

/// O motivo do fim, com os códigos da fronteira (§2.1). A ordem das variantes é
/// a ordem das regras do R-04.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Motivo {
    XequeMate,
    Afogamento,
    MaterialInsuficiente,
    RepeticaoTripla,
    CinquentaLances,
}

impl Motivo {
    /// Todos, na ordem do R-04.
    pub const TODOS: [Motivo; 5] = [
        Motivo::XequeMate,
        Motivo::Afogamento,
        Motivo::MaterialInsuficiente,
        Motivo::RepeticaoTripla,
        Motivo::CinquentaLances,
    ];

    /// O código da fronteira, que é também o nome usado no contrato (na lista
    /// `fim` e nas chaves de `relogios_de_empate`).
    pub fn codigo(self) -> &'static str {
        match self {
            Motivo::XequeMate => "xeque_mate",
            Motivo::Afogamento => "afogamento",
            Motivo::MaterialInsuficiente => "material_insuficiente",
            Motivo::RepeticaoTripla => "repeticao_tripla",
            Motivo::CinquentaLances => "cinquenta_lances",
        }
    }

    /// O motivo de um código, ou `None` se o código não existe.
    pub fn do_codigo(codigo: &str) -> Option<Motivo> {
        // `into_iter().find(...)` percorre a lista e devolve o primeiro que casa.
        Motivo::TODOS.into_iter().find(|m| m.codigo() == codigo)
    }
}

/// O fim de uma partida: o motivo e quem venceu (`None` no empate).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Fim {
    pub motivo: Motivo,
    pub vencedor: Option<Color>,
}

impl Fim {
    /// `{"motivo": "...", "vencedor": "branca|preta|null"}` (§2.1).
    pub fn em_json(&self) -> Value {
        json!({
            "motivo": self.motivo.codigo(),
            // `map` transforma o `Some(cor)` em `Some("branca")`; o `None` do
            // empate vira `null` no JSON.
            "vencedor": self.vencedor.map(nome_da_cor),
        })
    }
}

/// As regras do fim de UMA modalidade, já lidas do contrato.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegrasDoFim {
    /// Os motivos que a modalidade declara (a lista `fim` do contrato).
    motivos: Vec<Motivo>,
    /// Quantos meios-lances sem captura nem lance de peão encerram a partida
    /// (o `limite` do relógio, que vem em lances de cada lado, vezes 2).
    /// `None` quando a modalidade não tem esse empate.
    pub meios_lances_do_limite: Option<u32>,
    /// Em quantas ocorrências da mesma posição a partida acaba. `None` quando a
    /// modalidade não tem esse empate.
    pub ocorrencias_do_limite: Option<u32>,
}

impl RegrasDoFim {
    /// Lê as regras da modalidade. O contrato já foi validado em
    /// `Contrato::ler` (motivo desconhecido, relógio faltando ou fora da faixa
    /// são recusados lá), então aqui não há erro a devolver.
    pub fn da_modalidade(modalidade: &Modalidade) -> RegrasDoFim {
        let motivos: Vec<Motivo> = modalidade
            .fim
            .iter()
            // `filter_map` descarta os `None`: um código desconhecido não chega
            // aqui (a validação o recusou), mas o código não precisa supor isso.
            .filter_map(|codigo| Motivo::do_codigo(codigo))
            .collect();
        let limite_de = |motivo: Motivo| -> Option<u32> {
            if !motivos.contains(&motivo) {
                return None;
            }
            modalidade
                .relogios_de_empate
                .get(motivo.codigo())
                .map(|relogio| relogio.limite)
        };
        let meios_lances_do_limite = limite_de(Motivo::CinquentaLances).map(|lances| lances * 2);
        let ocorrencias_do_limite = limite_de(Motivo::RepeticaoTripla);
        RegrasDoFim {
            motivos,
            meios_lances_do_limite,
            ocorrencias_do_limite,
        }
    }

    /// A modalidade declara este motivo?
    pub fn tem(&self, motivo: Motivo) -> bool {
        self.motivos.contains(&motivo)
    }
}

/// O maior limite dos "50 lances" que a biblioteca consegue contar: a
/// `cozy-chess` guarda o contador de meios-lances num `u8` e o **trava em 100**
/// (conferido na fonte da 0.3.4, `play_unchecked`). Um limite maior que 50
/// lances nunca seria alcançado; o contrato o recusa (`contrato.rs`).
pub const MAIOR_LIMITE_DOS_CINQUENTA: u32 = 50;

/// Quantas vezes a posição de AGORA já apareceu desde o `fen_inicial`, contando
/// a de agora (1 = é a primeira vez).
///
/// ⚠️ Só o histórico desde o `fen_inicial` existe (R-03): uma repetição de
/// posições anteriores a ele não é vista. Numa partida adiantada ou num desafio,
/// é a posição publicada que começa a contagem.
pub fn repeticoes_da_posicao(posicao: &Posicao) -> u32 {
    // `last()` devolve o último item (a chave de agora). O histórico nunca é
    // vazio (tem pelo menos a do `fen_inicial`), mas o `map_or` cobre o caso.
    posicao.historico_de_chaves.last().map_or(0, |agora| {
        posicao
            .historico_de_chaves
            .iter()
            .filter(|chave| *chave == agora)
            .count() as u32
    })
}

/// A lista curta do material insuficiente (R-04): rei contra rei; rei e bispo
/// contra rei; rei e cavalo contra rei; rei e bispo contra rei e bispo com os
/// dois bispos em casas da MESMA cor. Fora dela, nada é "posição morta": os
/// casos raros terminam pelos 50 lances (D-07).
pub fn material_insuficiente(tabuleiro: &Board) -> bool {
    // Qualquer peão, torre ou dama: há material para mate.
    let pesadas =
        tabuleiro.pieces(Piece::Pawn) | tabuleiro.pieces(Piece::Rook) | tabuleiro.pieces(Piece::Queen);
    if !pesadas.is_empty() {
        return false;
    }
    let cavalos = tabuleiro.pieces(Piece::Knight);
    let bispos = tabuleiro.pieces(Piece::Bishop);
    // `len()` conta quantas casas o conjunto tem.
    let menores = cavalos.len() + bispos.len();
    match menores {
        // Rei contra rei, ou uma peça menor só (bispo ou cavalo).
        0 | 1 => true,
        // Dois bispos, um de cada lado, nas casas da mesma cor.
        2 if cavalos.is_empty() => {
            let um_de_cada_lado = tabuleiro.colored_pieces(Color::White, Piece::Bishop).len() == 1;
            let mesma_cor = bispos.is_subset(BitBoard::LIGHT_SQUARES)
                || bispos.is_subset(BitBoard::DARK_SQUARES);
            um_de_cada_lado && mesma_cor
        }
        _ => false,
    }
}

/// O fim da partida na posição de agora, ou `None` se ela continua.
pub fn fim_da_partida(posicao: &Posicao, regras: &RegrasDoFim) -> Option<Fim> {
    let tabuleiro = &posicao.tabuleiro;
    // `generate_moves(|_| true)` para no primeiro lance achado: devolve `true`
    // se existe ALGUM lance legal, sem gerar a lista inteira.
    let tem_lance = tabuleiro.generate_moves(|_| true);
    let em_xeque = !tabuleiro.checkers().is_empty();

    // 1 e 2: sem lance legal. Esses dois a modalidade sempre tem (o contrato
    // recusa uma lista `fim` sem eles), porque não há como continuar.
    if !tem_lance {
        return Some(if em_xeque {
            Fim {
                motivo: Motivo::XequeMate,
                // Quem não tem lance perdeu; venceu a outra cor.
                vencedor: Some(!tabuleiro.side_to_move()),
            }
        } else {
            Fim {
                motivo: Motivo::Afogamento,
                vencedor: None,
            }
        });
    }
    let empate = |motivo| Some(Fim { motivo, vencedor: None });
    // 3: material insuficiente.
    if regras.tem(Motivo::MaterialInsuficiente) && material_insuficiente(tabuleiro) {
        return empate(Motivo::MaterialInsuficiente);
    }
    // 4: a repetição.
    if let Some(limite) = regras.ocorrencias_do_limite {
        if repeticoes_da_posicao(posicao) >= limite {
            return empate(Motivo::RepeticaoTripla);
        }
    }
    // 5: os "50 lances", pelo contador de meios-lances da biblioteca (que parte
    // do FEN e anda com cada lance reaplicado).
    if let Some(limite) = regras.meios_lances_do_limite {
        if u32::from(tabuleiro.halfmove_clock()) >= limite {
            return empate(Motivo::CinquentaLances);
        }
    }
    None
}

/// O estado de uma posição: tudo o que a tela precisa para desenhar e aceitar o
/// próximo toque (§2.1).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Estado {
    /// De quem é a vez.
    pub vez: Color,
    /// Os lances legais agrupados pela casa de origem, com os destinos SEM a
    /// letra da promoção e sem repetição (a promoção a dama, torre, bispo e
    /// cavalo é um destino só). `BTreeMap`: as origens saem em ordem fixa.
    /// ⚠️ Vazio quando a partida acabou, inclusive no empate pela regra (em
    /// que a biblioteca ainda geraria lances): acabou é acabou.
    pub lances_legais: BTreeMap<String, Vec<String>>,
    /// As origens cujo lance pede a escolha da peça (o peão que chega ao fim).
    pub promocoes: Vec<String>,
    /// A casa do rei de quem joga, se ele está em xeque.
    pub rei_em_xeque: Option<String>,
    /// O fim, se a partida acabou.
    pub fim: Option<Fim>,
    /// Meios-lances sem captura nem lance de peão (o contador do FEN reaplicado).
    pub meios_lances_sem_captura: u32,
    /// Quantas vezes a posição de agora já apareceu (1 = a primeira).
    pub repeticoes_da_posicao: u32,
}

/// Monta o estado da posição.
pub fn estado(posicao: &Posicao, regras: &RegrasDoFim) -> Estado {
    let tabuleiro = &posicao.tabuleiro;
    let fim = fim_da_partida(posicao, regras);

    let mut lances_por_origem: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut promocoes: Vec<String> = Vec::new();
    if fim.is_none() {
        for lance in lances_legais(tabuleiro) {
            // `texto_do_lance` já converte o roque (`e1h1` da biblioteca) em
            // `e1g1`; os 4 primeiros caracteres são origem e destino.
            let texto = texto_do_lance(tabuleiro, lance);
            let origem = texto[0..2].to_string();
            let destino = texto[2..4].to_string();
            if lance.promotion.is_some() && !promocoes.contains(&origem) {
                promocoes.push(origem.clone());
            }
            // `entry(...).or_default()` devolve a lista da origem, criando-a
            // vazia na primeira vez.
            let destinos = lances_por_origem.entry(origem).or_default();
            if !destinos.contains(&destino) {
                destinos.push(destino);
            }
        }
    }
    promocoes.sort();
    // A ordem dos destinos de cada origem também fica fixa (alfabética), para a
    // resposta não depender da ordem de geração da biblioteca.
    for destinos in lances_por_origem.values_mut() {
        destinos.sort();
    }

    let rei_em_xeque = if tabuleiro.checkers().is_empty() {
        None
    } else {
        Some(tabuleiro.king(tabuleiro.side_to_move()).to_string())
    };

    Estado {
        vez: tabuleiro.side_to_move(),
        lances_legais: lances_por_origem,
        promocoes,
        rei_em_xeque,
        fim,
        meios_lances_sem_captura: u32::from(tabuleiro.halfmove_clock()),
        repeticoes_da_posicao: repeticoes_da_posicao(posicao),
    }
}

impl Estado {
    /// O objeto do §2.1.
    ///
    /// `lances_sem_captura` vai na unidade do relógio do contrato, **lances de
    /// cada lado** (o meio-lance dividido por 2, arredondado para baixo): é o
    /// número que a faixa de aviso escreve, "44 / 50" (R-26a). O contador exato
    /// vai ao lado, em `meios_lances_sem_captura`.
    pub fn em_json(&self) -> Value {
        json!({
            "vez": nome_da_cor(self.vez),
            "lances_legais": self.lances_legais,
            "promocoes": self.promocoes,
            "rei_em_xeque": self.rei_em_xeque,
            "fim": self.fim.map(|f| f.em_json()),
            "lances_sem_captura": self.meios_lances_sem_captura / 2,
            "meios_lances_sem_captura": self.meios_lances_sem_captura,
            "repeticoes_da_posicao": self.repeticoes_da_posicao,
        })
    }
}
