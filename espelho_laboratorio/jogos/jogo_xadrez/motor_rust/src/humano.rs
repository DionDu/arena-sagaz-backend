//! O modelo humano: quanto uma PESSOA jogaria cada lance (T051c; research.md
//! R-11 "O modelo humano"; `docs/DECISOES-do-dono.md` §8zzzz25 do frontend).
//!
//! ## Para que serve
//!
//! Até a 0.5.0, quando o personagem errava, ele sorteava **com a mesma chance**
//! um dos lances de nota perto da melhor. A Maia (a rede que imita gente, R-11)
//! mostrou que esses erros não parecem de pessoa: o que é plausível para o motor
//! não é o que alguém de verdade jogaria. Este módulo dá a cada lance uma nota
//! de **naturalidade**, e `niveis.rs` passa a sortear o erro com peso: a nota
//! da busca (quanto o lance é bom) mais a naturalidade (quanto ele é humano).
//!
//! ## As três peças
//!
//! 1. [`caracteristicas`]: uma lista FIXA de números inteiros sobre o lance
//!    (capturou o quê, deu xeque, que peça andou, deixou peça em perigo, de
//!    quem é a ameaça e de onde ela vem...). A lista inteira está em
//!    [`Caracteristica`], com o significado de cada uma.
//! 2. [`nota_humana`]: a soma de peso × característica. Os pesos **não são
//!    escritos à mão**: saem da Maia por regressão (T051d) e viajam no contrato,
//!    em `modelo_humano.pesos` (inteiros). A unidade da nota é o **centésimo de
//!    "nat"**: 100 pontos a mais deixam o lance e ≈ 2,72 vezes mais provável.
//! 3. [`indice_sorteado`]: o sorteio por **softmax** (a chance de cada lance é
//!    proporcional a e elevado aos pontos dele) feito **sem ponto flutuante**.
//!
//! ## Por que sem ponto flutuante (R-05)
//!
//! O mesmo pedido tem de dar o mesmo lance no PC, no ARM de 32 bits do aparelho
//! e no servidor Linux. A função `exp()` em `f64` pode diferir no último bit de
//! uma plataforma para outra, e um bit muda a fronteira do sorteio. Aqui o peso
//! de cada lance é `e^(-d/100)` (com `d` = quantos pontos ele está abaixo do
//! melhor) em **ponto fixo Q32**: um inteiro que vale o número real vezes 2³².
//! A conta é só multiplicação inteira de constantes escritas neste arquivo.
//!
//! ## Valores das peças, em peões
//!
//! As características que falam de valor usam a conta de escola, em peões
//! inteiros (peão 1, cavalo 3, bispo 3, torre 5, dama 9), e não os centipeões da
//! avaliação: é a régua com que uma pessoa pensa "troquei bem ou mal", e deixa
//! os pesos da regressão legíveis.

use cozy_chess::{
    get_bishop_moves, get_king_moves, get_knight_moves, get_pawn_attacks, get_rook_moves, BitBoard, Board, Color, File,
    Move, Piece, Rank, Square,
};

use crate::avaliacao::valor_da_peca;
use crate::busca::e_captura;
use crate::posicao::{atacantes_da_casa, Posicao};

/// Quantas características cada lance tem (o tamanho de [`Caracteristica::TODAS`]).
pub const NUMERO_DE_CARACTERISTICAS: usize = 42;

/// Cada característica de um lance, na ordem fixa em que elas ficam no vetor.
///
/// Um `enum` do Rust é uma lista fechada de nomes; `as usize` dá a posição de
/// cada nome na declaração (o primeiro é 0). É essa posição que indexa o vetor
/// de [`Caracteristicas`] e o vetor de pesos. ⚠️ **Não reordene nem remova**:
/// os pesos do contrato viajam por NOME, mas o executável da destilação (T051d)
/// escreve as colunas nesta ordem. Característica nova entra no FIM.
///
/// "O valor" é sempre em peões (ver o topo do arquivo). "Distância" é a do rei:
/// o maior entre colunas e fileiras percorridas.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Caracteristica {
    /// O valor da peça capturada (0 sem captura; o en passant vale 1).
    CapturaValor,
    /// 1 se a captura é na casa onde o adversário acabou de jogar: a retomada
    /// ("ele tomou, eu tomo de volta") e o "comer a peça que acabou de chegar".
    CapturaRetomada,
    /// 1 se o lance dá xeque.
    Xeque,
    /// 1 no roque. No roque, as características de geometria e de peça (abaixo)
    /// ficam em zero: ele é um lance só, e não "o rei andando duas casas".
    Roque,
    /// 1 na promoção a dama.
    PromocaoDama,
    /// 1 na promoção a outra peça (a "subpromoção", rara em gente).
    PromocaoMenor,
    /// 1 se a peça que anda é um peão (as seis seguintes dizem qual peça anda;
    /// exatamente uma é 1, fora do roque).
    PecaPeao,
    /// 1 se a peça que anda é um cavalo.
    PecaCavalo,
    /// 1 se a peça que anda é um bispo.
    PecaBispo,
    /// 1 se a peça que anda é uma torre.
    PecaTorre,
    /// 1 se a peça que anda é a dama.
    PecaDama,
    /// 1 se a peça que anda é o rei (fora do roque): o "rei andando".
    PecaRei,
    /// Quantas fileiras a peça andou PARA A FRENTE (na direção do adversário).
    Avanco,
    /// Quantas fileiras a peça andou PARA TRÁS.
    Recuo,
    /// A distância do lance (de 1 a 7).
    Distancia,
    /// 1 se um cavalo ou bispo sai da primeira fileira (o "desenvolver").
    Desenvolvimento,
    /// 1 se a peça chega a uma das quatro casas do centro (d4, e4, d5, e5).
    Centro,
    /// 1 se ela chega ao anel em volta do centro (de c3 a f6, sem as quatro).
    CentroAmpliado,
    /// 1 se a peça que anda é a mesma do lance anterior do mesmo lado.
    MesmaPeca,
    /// O valor da peça que anda, se ela estava em perigo na casa de saída: o
    /// "fugir da peça atacada". "Em perigo" está em [`em_perigo`].
    Fuga,
    /// O valor da peça que anda, se ela chega a uma casa onde fica em perigo.
    CaiEmPerigo,
    /// 1 se a peça que anda é um peão da coluna a ou h.
    PeaoDaBorda,
    /// **A percepção da ameaça** (ideia do dono, 18/11/2026). Depois do lance,
    /// a nossa peça mais valiosa que fica em perigo (o "alvo", sem o rei) e o
    /// adversário de menor valor que a ataca. As quatro seguintes valem o valor
    /// do alvo, conforme QUEM o ataca: aqui, um peão.
    AmeacaPorPeao,
    /// O valor do alvo, se quem o ataca é um cavalo.
    AmeacaPorCavalo,
    /// O valor do alvo, se quem o ataca é uma peça que anda em linha (bispo,
    /// torre ou dama).
    AmeacaPorLinha,
    /// O valor do alvo, se quem o ataca é o rei.
    AmeacaPorRei,
    /// A distância entre o atacante e o alvo (0 sem alvo).
    AmeacaDistancia,
    /// **O muro aparente**: com o cavalo atacando, quantas casas ocupadas (de
    /// qualquer cor) há no retângulo entre ele e o alvo, sem as duas pontas (de
    /// 0 a 4). O cavalo pula, mas a parede de peças dá a falsa sensação de
    /// proteção.
    AmeacaMuro,
    /// **A falsa cobertura**: quantas peças nossas encostadas no alvo NÃO o
    /// defendem (de 0 a 8). Elas "parecem" proteger a peça.
    AmeacaFalsaCobertura,
    /// O valor do alvo, se a ameaça já existia antes do lance (a pessoa a
    /// ignorou); 0 se ela nasceu do lance (a peça foi "pendurada").
    AmeacaIgnorada,
    /// **A captura que parecia de graça.** Depois de capturar, o defensor de
    /// menor valor da casa. As quatro seguintes valem o valor da NOSSA peça que
    /// capturou (o que ela arrisca), conforme quem defende: aqui, um peão.
    CapturaDefendidaPorPeao,
    /// O valor da nossa peça que capturou, se quem defende é um cavalo.
    CapturaDefendidaPorCavalo,
    /// O valor da nossa peça que capturou, se quem defende anda em linha.
    CapturaDefendidaPorLinha,
    /// O valor da nossa peça que capturou, se quem defende é o rei.
    CapturaDefendidaPorRei,
    /// A distância entre esse defensor e a casa da captura (0 sem defensor).
    CapturaDefensorDistancia,
    // ── Motor 0.8.0 (T051h, passo 5): as sete do diagnóstico ──────────────
    // `calibracao/diagnosticar_modelo_humano.py` mediu 24 candidatas contra a
    // Maia-2 abaixo de 1100, cada uma pela queda da entropia cruzada com as 35
    // de cima juntas; estas são as sete da seleção gulosa (research.md R-11, "O
    // diagnóstico"). No roque as cinco que falam da peça que anda ficam em zero,
    // como as de geometria.
    /// **O ataque**: o valor da peça inimiga mais valiosa (sem o rei) que a peça
    /// movida ataca da casa de chegada. Gente abaixo de 1100 gosta de atacar
    /// peça; foi a candidata que mais explicou sozinha (7,4% da distância).
    AtacaValor,
    /// 1 se, entre as peças inimigas atacadas pela peça movida, há uma que
    /// ninguém defende (o "ataquei uma peça solta").
    AtacaDesprotegida,
    /// Quantas casas a peça movida ataca na chegada menos quantas atacava na
    /// saída (a "peça ativa"); pode ser negativo. Peão e rei: 0.
    MobilidadeGanha,
    /// 1 se o peão que anda (sem promover) é passado na chegada: nenhum peão
    /// inimigo na frente dele, na coluna dele e nas duas vizinhas.
    PeaoPassado,
    /// Na captura: o valor capturado menos o da peça que captura (o rei vale 0
    /// aqui). Positivo é "ganhei na troca"; 0 sem captura.
    CapturaGanho,
    /// 1 se a captura é de uma peça do mesmo valor (a "troca"), fora o rei.
    Troca,
    /// O valor de [`Caracteristica::CaiEmPerigo`] quando o lance dá xeque: **o
    /// xeque que entrega a peça**. O modelo é uma soma, e "xeque" mais "cair em
    /// perigo" não diz que é a MESMA peça que dá xeque e fica pendurada.
    XequeQueEntrega,
}

impl Caracteristica {
    /// Todas, na ordem do vetor. O teste `tests/humano.rs` confere que a posição
    /// de cada uma nesta lista é o `as usize` dela, e que os nomes não se repetem.
    pub const TODAS: [Caracteristica; NUMERO_DE_CARACTERISTICAS] = [
        Caracteristica::CapturaValor,
        Caracteristica::CapturaRetomada,
        Caracteristica::Xeque,
        Caracteristica::Roque,
        Caracteristica::PromocaoDama,
        Caracteristica::PromocaoMenor,
        Caracteristica::PecaPeao,
        Caracteristica::PecaCavalo,
        Caracteristica::PecaBispo,
        Caracteristica::PecaTorre,
        Caracteristica::PecaDama,
        Caracteristica::PecaRei,
        Caracteristica::Avanco,
        Caracteristica::Recuo,
        Caracteristica::Distancia,
        Caracteristica::Desenvolvimento,
        Caracteristica::Centro,
        Caracteristica::CentroAmpliado,
        Caracteristica::MesmaPeca,
        Caracteristica::Fuga,
        Caracteristica::CaiEmPerigo,
        Caracteristica::PeaoDaBorda,
        Caracteristica::AmeacaPorPeao,
        Caracteristica::AmeacaPorCavalo,
        Caracteristica::AmeacaPorLinha,
        Caracteristica::AmeacaPorRei,
        Caracteristica::AmeacaDistancia,
        Caracteristica::AmeacaMuro,
        Caracteristica::AmeacaFalsaCobertura,
        Caracteristica::AmeacaIgnorada,
        Caracteristica::CapturaDefendidaPorPeao,
        Caracteristica::CapturaDefendidaPorCavalo,
        Caracteristica::CapturaDefendidaPorLinha,
        Caracteristica::CapturaDefendidaPorRei,
        Caracteristica::CapturaDefensorDistancia,
        Caracteristica::AtacaValor,
        Caracteristica::AtacaDesprotegida,
        Caracteristica::MobilidadeGanha,
        Caracteristica::PeaoPassado,
        Caracteristica::CapturaGanho,
        Caracteristica::Troca,
        Caracteristica::XequeQueEntrega,
    ];

    /// O nome no contrato (`modelo_humano.pesos`) e no executável da destilação.
    pub fn nome(self) -> &'static str {
        match self {
            Caracteristica::CapturaValor => "captura_valor",
            Caracteristica::CapturaRetomada => "captura_retomada",
            Caracteristica::Xeque => "xeque",
            Caracteristica::Roque => "roque",
            Caracteristica::PromocaoDama => "promocao_dama",
            Caracteristica::PromocaoMenor => "promocao_menor",
            Caracteristica::PecaPeao => "peca_peao",
            Caracteristica::PecaCavalo => "peca_cavalo",
            Caracteristica::PecaBispo => "peca_bispo",
            Caracteristica::PecaTorre => "peca_torre",
            Caracteristica::PecaDama => "peca_dama",
            Caracteristica::PecaRei => "peca_rei",
            Caracteristica::Avanco => "avanco",
            Caracteristica::Recuo => "recuo",
            Caracteristica::Distancia => "distancia",
            Caracteristica::Desenvolvimento => "desenvolvimento",
            Caracteristica::Centro => "centro",
            Caracteristica::CentroAmpliado => "centro_ampliado",
            Caracteristica::MesmaPeca => "mesma_peca",
            Caracteristica::Fuga => "fuga",
            Caracteristica::CaiEmPerigo => "cai_em_perigo",
            Caracteristica::PeaoDaBorda => "peao_da_borda",
            Caracteristica::AmeacaPorPeao => "ameaca_por_peao",
            Caracteristica::AmeacaPorCavalo => "ameaca_por_cavalo",
            Caracteristica::AmeacaPorLinha => "ameaca_por_linha",
            Caracteristica::AmeacaPorRei => "ameaca_por_rei",
            Caracteristica::AmeacaDistancia => "ameaca_distancia",
            Caracteristica::AmeacaMuro => "ameaca_muro",
            Caracteristica::AmeacaFalsaCobertura => "ameaca_falsa_cobertura",
            Caracteristica::AmeacaIgnorada => "ameaca_ignorada",
            Caracteristica::CapturaDefendidaPorPeao => "captura_defendida_por_peao",
            Caracteristica::CapturaDefendidaPorCavalo => "captura_defendida_por_cavalo",
            Caracteristica::CapturaDefendidaPorLinha => "captura_defendida_por_linha",
            Caracteristica::CapturaDefendidaPorRei => "captura_defendida_por_rei",
            Caracteristica::CapturaDefensorDistancia => "captura_defensor_distancia",
            Caracteristica::AtacaValor => "ataca_valor",
            Caracteristica::AtacaDesprotegida => "ataca_desprotegida",
            Caracteristica::MobilidadeGanha => "mobilidade_ganha",
            Caracteristica::PeaoPassado => "peao_passado",
            Caracteristica::CapturaGanho => "captura_ganho",
            Caracteristica::Troca => "troca",
            Caracteristica::XequeQueEntrega => "xeque_que_entrega",
        }
    }

    /// A característica pelo nome, ou `None` (o contrato recusa nome que não
    /// existe: um erro de digitação viraria um peso que não pesa nada).
    pub fn do_nome(nome: &str) -> Option<Caracteristica> {
        Caracteristica::TODAS.into_iter().find(|c| c.nome() == nome)
    }
}

/// Os números de um lance, um por [`Caracteristica`], na ordem de `TODAS`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Caracteristicas {
    pub valores: [i32; NUMERO_DE_CARACTERISTICAS],
}

impl Caracteristicas {
    /// O valor de uma característica.
    pub fn valor(&self, c: Caracteristica) -> i32 {
        self.valores[c as usize]
    }

    /// Escreve o valor de uma característica (`&mut self`: altera o vetor).
    fn por(&mut self, c: Caracteristica, valor: i32) {
        self.valores[c as usize] = valor;
    }
}

/// O valor de uma peça em peões inteiros (ver o topo do arquivo). O rei vale 0:
/// ele nunca é o "alvo" de uma ameaça (o xeque é outra coisa) nem arrisca nada
/// ao capturar (ele não pode capturar peça defendida).
pub const fn valor_em_peoes(peca: Piece) -> i32 {
    match peca {
        Piece::Pawn => 1,
        Piece::Knight | Piece::Bishop => 3,
        Piece::Rook => 5,
        Piece::Queen => 9,
        Piece::King => 0,
    }
}

/// A distância do rei entre duas casas: o maior entre as colunas e as fileiras.
pub fn distancia_do_rei(a: Square, b: Square) -> i32 {
    // `as i32` converte a coluna (A = 0 ... H = 7) e a fileira em número, para
    // a subtração poder dar negativo; `abs()` tira o sinal.
    let colunas = (a.file() as i32 - b.file() as i32).abs();
    let fileiras = (a.rank() as i32 - b.rank() as i32).abs();
    colunas.max(fileiras)
}

/// A ordem de "menor valor" para escolher o atacante (ou defensor) que conta:
/// os centipeões da avaliação, que desempatam o cavalo (320) antes do bispo
/// (330), e o rei por último (ele só entra quando não há outro).
fn ordem_de_valor(peca: Piece) -> i32 {
    match peca {
        Piece::King => i32::MAX,
        outra => valor_da_peca(outra),
    }
}

/// A peça de MENOR valor num conjunto de casas, e a casa dela; no empate, a
/// primeira casa na ordem do `BitBoard` (a1, b1, ..., h8), que é a mesma em
/// toda máquina (R-05). `None` com o conjunto vazio.
fn menor_peca(tabuleiro: &Board, casas: BitBoard) -> Option<(Piece, Square)> {
    let mut menor: Option<(Piece, Square)> = None;
    for casa in casas {
        // As casas vêm de `atacantes_da_casa`: sempre ocupadas.
        let Some(peca) = tabuleiro.piece_on(casa) else { continue };
        // `map_or(true, ...)`: sem nenhum ainda, este é o menor; com um, só o
        // estritamente menor troca (o empate fica com a primeira casa).
        if menor.map_or(true, |(atual, _)| ordem_de_valor(peca) < ordem_de_valor(atual)) {
            menor = Some((peca, casa));
        }
    }
    menor
}

/// A peça da casa está **em perigo**? Devolve o atacante que conta (a peça de
/// menor valor do outro lado que ataca a casa) e a casa dele.
///
/// "Em perigo" é a regra de bolso de quem joga: a peça é atacada e (a) ninguém
/// a defende, ou (b) o atacante vale MENOS que ela (em peões: o cavalo que
/// ataca o bispo defendido não ameaça, é uma troca). O rei nunca está "em
/// perigo" aqui (o xeque é outra coisa), e uma casa vazia também não.
///
/// ⚠️ É a conta de quem olha o tabuleiro, e não a da busca: não vê cravada nem
/// ataque em raio-X atrás de outra peça. É de propósito: é assim que a pessoa
/// enxerga, e é o que a Maia vai pesar.
pub fn em_perigo(tabuleiro: &Board, casa: Square) -> Option<(Piece, Square)> {
    let dono = tabuleiro.color_on(casa)?;
    let peca = tabuleiro.piece_on(casa)?;
    if peca == Piece::King {
        return None;
    }
    let ocupacao = tabuleiro.occupied();
    // `!dono` é a outra cor.
    let atacantes = atacantes_da_casa(tabuleiro, casa, !dono, ocupacao);
    // O `?` devolve `None` direto se ninguém ataca.
    let (atacante, casa_do_atacante) = menor_peca(tabuleiro, atacantes)?;
    let defendida = !atacantes_da_casa(tabuleiro, casa, dono, ocupacao).is_empty();
    // O rei atacante vale "infinito" aqui: ele só ameaça peça sem defesa.
    let valor_do_atacante = if atacante == Piece::King { i32::MAX } else { valor_em_peoes(atacante) };
    if !defendida || valor_do_atacante < valor_em_peoes(peca) {
        Some((atacante, casa_do_atacante))
    } else {
        None
    }
}

/// As casas que a peça de `casa` ataca (vazio sem peça). É a conta "de quem
/// olha": o peão ataca as duas diagonais da frente (e não a casa em que anda), e
/// as peças de linha param na primeira peça do caminho, de qualquer cor.
fn ataques_da_peca(tabuleiro: &Board, casa: Square) -> BitBoard {
    let (Some(peca), Some(cor)) = (tabuleiro.piece_on(casa), tabuleiro.color_on(casa)) else {
        return BitBoard::EMPTY;
    };
    let ocupacao = tabuleiro.occupied();
    match peca {
        Piece::Pawn => get_pawn_attacks(casa, cor),
        Piece::Knight => get_knight_moves(casa),
        Piece::Bishop => get_bishop_moves(casa, ocupacao),
        Piece::Rook => get_rook_moves(casa, ocupacao),
        // `|` é a união: a dama anda como torre e como bispo.
        Piece::Queen => get_bishop_moves(casa, ocupacao) | get_rook_moves(casa, ocupacao),
        Piece::King => get_king_moves(casa),
    }
}

/// O peão de `casa`, da cor `nos`, é passado? Nenhum peão do outro lado na
/// coluna dele nem nas vizinhas, em fileira mais à frente (vista do lado dele).
fn peao_passado(tabuleiro: &Board, casa: Square, nos: Color) -> bool {
    let fileira = casa.rank().relative_to(nos) as i32;
    let coluna = casa.file() as i32;
    // `all`: verdadeiro se NENHUM peão inimigo bloqueia (vale para lista vazia).
    tabuleiro.colored_pieces(!nos, Piece::Pawn).into_iter().all(|outro| {
        (outro.file() as i32 - coluna).abs() > 1 || outro.rank().relative_to(nos) as i32 <= fileira
    })
}

/// O grupo de quem ataca ou defende, como a pessoa os separa: o peão, o cavalo
/// (que pula), as peças de linha (bispo, torre, dama) e o rei.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Grupo {
    Peao,
    Cavalo,
    Linha,
    Rei,
}

fn grupo(peca: Piece) -> Grupo {
    match peca {
        Piece::Pawn => Grupo::Peao,
        Piece::Knight => Grupo::Cavalo,
        Piece::Bishop | Piece::Rook | Piece::Queen => Grupo::Linha,
        Piece::King => Grupo::Rei,
    }
}

/// Quantas casas ocupadas há no retângulo entre duas casas, sem contar as duas
/// pontas. Para o cavalo, o retângulo é de 2 × 3 casas: são 4 no meio.
fn ocupadas_no_retangulo(tabuleiro: &Board, a: Square, b: Square) -> i32 {
    let (c0, c1) = ((a.file() as usize).min(b.file() as usize), (a.file() as usize).max(b.file() as usize));
    let (f0, f1) = ((a.rank() as usize).min(b.rank() as usize), (a.rank() as usize).max(b.rank() as usize));
    let mut ocupadas = 0;
    // `c0..=c1` é o intervalo de c0 a c1, inclusive as duas pontas.
    for coluna in c0..=c1 {
        for fileira in f0..=f1 {
            let casa = Square::new(File::index(coluna), Rank::index(fileira));
            if casa != a && casa != b && tabuleiro.occupied().has(casa) {
                ocupadas += 1;
            }
        }
    }
    ocupadas
}

/// As características de um lance **legal** na posição (a lista inteira está
/// em [`Caracteristica`]). A posição traz o histórico: é dele que saem a
/// retomada (o último lance, do adversário) e a "mesma peça" (o penúltimo, do
/// próprio lado).
pub fn caracteristicas(posicao: &Posicao, lance: Move) -> Caracteristicas {
    use Caracteristica as C;
    let antes = &posicao.tabuleiro;
    let nos: Color = antes.side_to_move();
    let mut c = Caracteristicas { valores: [0; NUMERO_DE_CARACTERISTICAS] };
    // O lance é legal: há sempre uma peça nossa na origem.
    let Some(peca) = antes.piece_on(lance.from) else { return c };
    // O roque da `cozy-chess` é o rei "capturando" a própria torre.
    let roque = peca == Piece::King && antes.color_on(lance.to) == Some(nos);
    let captura = e_captura(antes, lance);
    let mut depois = antes.clone();
    depois.play_unchecked(lance);

    // ── O que o lance faz ──────────────────────────────────────────────────
    if captura {
        // No en passant a casa de destino está vazia, e a vítima é um peão.
        let capturada = antes.piece_on(lance.to).unwrap_or(Piece::Pawn);
        c.por(C::CapturaValor, valor_em_peoes(capturada));
        if posicao.lances.last().map(|u| u.to) == Some(lance.to) {
            c.por(C::CapturaRetomada, 1);
        }
        // A captura que parecia de graça: quem defende a casa, depois dela.
        let defensores = atacantes_da_casa(&depois, lance.to, !nos, depois.occupied());
        if let Some((defensor, casa_do_defensor)) = menor_peca(&depois, defensores) {
            // O que a nossa peça arrisca: a que está na casa agora (na captura
            // com promoção, já a peça promovida).
            let risco = depois.piece_on(lance.to).map_or(0, valor_em_peoes);
            let qual = match grupo(defensor) {
                Grupo::Peao => C::CapturaDefendidaPorPeao,
                Grupo::Cavalo => C::CapturaDefendidaPorCavalo,
                Grupo::Linha => C::CapturaDefendidaPorLinha,
                Grupo::Rei => C::CapturaDefendidaPorRei,
            };
            c.por(qual, risco);
            c.por(C::CapturaDefensorDistancia, distancia_do_rei(casa_do_defensor, lance.to));
        }
        // O saldo da troca, na conta de escola (o rei vale 0: `valor_em_peoes`).
        c.por(C::CapturaGanho, valor_em_peoes(capturada) - valor_em_peoes(peca));
        if peca != Piece::King && valor_em_peoes(capturada) == valor_em_peoes(peca) {
            c.por(C::Troca, 1);
        }
    }
    if !depois.checkers().is_empty() {
        c.por(C::Xeque, 1);
    }
    match lance.promotion {
        Some(Piece::Queen) => c.por(C::PromocaoDama, 1),
        Some(_) => c.por(C::PromocaoMenor, 1),
        None => {}
    }

    if roque {
        c.por(C::Roque, 1);
    } else {
        let qual = match peca {
            Piece::Pawn => C::PecaPeao,
            Piece::Knight => C::PecaCavalo,
            Piece::Bishop => C::PecaBispo,
            Piece::Rook => C::PecaTorre,
            Piece::Queen => C::PecaDama,
            Piece::King => C::PecaRei,
        };
        c.por(qual, 1);
        // A fileira vista do lado de quem joga (`relative_to`: para as pretas,
        // a 8ª fileira vira a 1ª), para "para a frente" ser sempre positivo.
        let delta = lance.to.rank().relative_to(nos) as i32 - lance.from.rank().relative_to(nos) as i32;
        c.por(C::Avanco, delta.max(0));
        c.por(C::Recuo, (-delta).max(0));
        c.por(C::Distancia, distancia_do_rei(lance.from, lance.to));
        let menor = peca == Piece::Knight || peca == Piece::Bishop;
        if menor
            && lance.from.rank().relative_to(nos) == Rank::First
            && lance.to.rank().relative_to(nos) != Rank::First
        {
            c.por(C::Desenvolvimento, 1);
        }
        // Colunas e fileiras de 0 a 7: o centro é d-e (3-4) × 4ª-5ª (3-4); o
        // anel, c-f (2-5) × 3ª-6ª (2-5).
        let (coluna, fileira) = (lance.to.file() as usize, lance.to.rank() as usize);
        let no_centro = (3..=4).contains(&coluna) && (3..=4).contains(&fileira);
        if no_centro {
            c.por(C::Centro, 1);
        } else if (2..=5).contains(&coluna) && (2..=5).contains(&fileira) {
            c.por(C::CentroAmpliado, 1);
        }
        // O nosso lance anterior é o PENÚLTIMO da lista (o último é do outro).
        let n = posicao.lances.len();
        if n >= 2 && posicao.lances[n - 2].to == lance.from {
            c.por(C::MesmaPeca, 1);
        }
        if peca == Piece::Pawn && (lance.from.file() == File::A || lance.from.file() == File::H) {
            c.por(C::PeaoDaBorda, 1);
        }
        if em_perigo(antes, lance.from).is_some() {
            c.por(C::Fuga, valor_em_peoes(peca));
        }
        if em_perigo(&depois, lance.to).is_some() {
            c.por(C::CaiEmPerigo, depois.piece_on(lance.to).map_or(0, valor_em_peoes));
        }

        // ── O ataque e a atividade da peça que chegou (motor 0.8.0) ──────────
        // Na promoção, a peça na chegada já é a promovida: é ela que ataca.
        let atacadas = ataques_da_peca(&depois, lance.to);
        // As peças inimigas atacadas, sem o rei (o xeque é outra característica).
        let alvos = atacadas & depois.colors(!nos) & !depois.pieces(Piece::King);
        let mut ataca_valor = 0;
        for alvo in alvos {
            ataca_valor = ataca_valor.max(depois.piece_on(alvo).map_or(0, valor_em_peoes));
            // Ninguém do outro lado defende o alvo: a peça está solta.
            if atacantes_da_casa(&depois, alvo, !nos, depois.occupied()).is_empty() {
                c.por(C::AtacaDesprotegida, 1);
            }
        }
        c.por(C::AtacaValor, ataca_valor);
        if peca != Piece::Pawn && peca != Piece::King {
            // `len()` conta as casas do conjunto; antes, a peça atacava da saída.
            c.por(C::MobilidadeGanha, atacadas.len() as i32 - ataques_da_peca(antes, lance.from).len() as i32);
        }
        if peca == Piece::Pawn && lance.promotion.is_none() && peao_passado(&depois, lance.to, nos) {
            c.por(C::PeaoPassado, 1);
        }
    }
    // O xeque que entrega a peça (no roque, `CaiEmPerigo` é 0, e esta também).
    if c.valor(C::Xeque) == 1 {
        c.por(C::XequeQueEntrega, c.valor(C::CaiEmPerigo));
    }

    // ── A percepção da ameaça, depois do lance ─────────────────────────────
    // O alvo: a nossa peça (sem o rei) de MAIOR valor que fica em perigo; no
    // empate, a primeira casa (o `>` estrito não troca por um igual).
    let nossas = depois.colors(nos) & !depois.pieces(Piece::King);
    let mut alvo: Option<(Square, Piece, Square)> = None;
    for casa in nossas {
        if let Some((atacante, casa_do_atacante)) = em_perigo(&depois, casa) {
            let valor = depois.piece_on(casa).map_or(0, valor_da_peca);
            let maior = alvo.map_or(true, |(atual, _, _)| valor > depois.piece_on(atual).map_or(0, valor_da_peca));
            if maior {
                alvo = Some((casa, atacante, casa_do_atacante));
            }
        }
    }
    if let Some((casa, atacante, casa_do_atacante)) = alvo {
        let valor = depois.piece_on(casa).map_or(0, valor_em_peoes);
        let qual = match grupo(atacante) {
            Grupo::Peao => C::AmeacaPorPeao,
            Grupo::Cavalo => C::AmeacaPorCavalo,
            Grupo::Linha => C::AmeacaPorLinha,
            Grupo::Rei => C::AmeacaPorRei,
        };
        c.por(qual, valor);
        c.por(C::AmeacaDistancia, distancia_do_rei(casa_do_atacante, casa));
        if atacante == Piece::Knight {
            c.por(C::AmeacaMuro, ocupadas_no_retangulo(&depois, casa_do_atacante, casa));
        }
        // As nossas peças encostadas no alvo que não estão entre as que o
        // defendem (`&` é a interseção de conjuntos de casas; `!`, o
        // complemento).
        let defensores = atacantes_da_casa(&depois, casa, nos, depois.occupied());
        let encostadas = get_king_moves(casa) & depois.colors(nos);
        c.por(C::AmeacaFalsaCobertura, (encostadas & !defensores).len() as i32);
        // A ameaça já existia? Só se a mesma casa tinha uma peça NOSSA em
        // perigo antes do lance (a peça que acabou de chegar ali não conta: a
        // casa era vazia ou do outro lado).
        if antes.color_on(casa) == Some(nos) && em_perigo(antes, casa).is_some() {
            c.por(C::AmeacaIgnorada, valor);
        }
    }
    c
}

/// A nota humana de um lance: a soma de peso × característica, em centésimos
/// de "nat" (ver o topo do arquivo). Em `i64`: com pesos de até 100 000 (o teto
/// que o contrato aceita) e 42 características, a soma passaria do `i32`.
pub fn nota_humana(c: &Caracteristicas, pesos: &[i32; NUMERO_DE_CARACTERISTICAS]) -> i64 {
    // `zip` anda nas duas listas juntas, item a item.
    c.valores.iter().zip(pesos.iter()).map(|(&x, &w)| i64::from(x) * i64::from(w)).sum()
}

// ── O softmax inteiro ────────────────────────────────────────────────────────

/// O número 1 em ponto fixo Q32 (2³²): o peso do melhor lance.
pub const UM_Q32: u64 = 1 << 32;

/// A partir de quantos pontos abaixo do melhor o peso é zero: e^(−23) × 2³² é
/// menor que meio, e arredonda para 0.
pub const PONTOS_SEM_PESO: i64 = 2300;

/// e^(−i/100) × 2³², para i de 0 a 9, arredondado ao inteiro mais próximo.
/// Calculadas com 60 dígitos (o `decimal` do Python), uma vez, e escritas aqui:
/// `round(2**32 * exp(-Decimal(i)/100))`. O teste `tests/humano.rs` confere o
/// produto delas contra a mesma conta exata.
const EXP_CENTESIMOS: [u64; 10] = [
    4294967296, 4252231657, 4209921245, 4168031829, 4126559220, 4085499269, 4044847872, 4004600963, 3964754518,
    3925304552,
];

/// e^(−j/10) × 2³², para j de 0 a 9 (a mesma conta).
const EXP_DECIMOS: [u64; 10] = [
    4294967296, 3886247119, 3516421809, 3181790030, 2879002676, 2605029347, 2357128029, 2132817639, 1929853206,
    1746203392,
];

/// e^(−k) × 2³², para k de 0 a 22 (a mesma conta).
const EXP_INTEIROS: [u64; 23] = [
    4294967296, 1580030169, 581260615, 213833830, 78665070, 28939262, 10646160, 3916503, 1440801, 530041, 194991,
    71733, 26389, 9708, 3571, 1314, 483, 178, 65, 24, 9, 3, 1,
];

/// O produto de dois números Q32, arredondado: (a × b + ½) / 2³². Em `u128`
/// porque 2³² × 2³² não cabe em 64 bits (o Rust faz a conta de 128 bits em
/// software no ARM de 32: lenta, mas igual em toda máquina).
fn produto_q32(a: u64, b: u64) -> u64 {
    ((u128::from(a) * u128::from(b) + (1u128 << 31)) >> 32) as u64
}

/// O peso de um lance que está `abaixo` pontos do melhor: e^(−abaixo/100) em
/// Q32. Os pontos se separam em centenas, dezenas e unidades (1234 = 12 + 0,3
/// + 0,04), e o peso é o produto das três tabelas: e^(−12) × e^(−0,3) ×
/// e^(−0,04). O erro é de no máximo 2 unidades em 2³² (conferido no teste).
///
/// ⚠️ **A ordem das multiplicações importa.** As duas tabelas de fração (perto
/// de 1, com 32 bits de precisão) se multiplicam primeiro, e a das potências
/// inteiras entra por último. Ao contrário, um e^(−20) que vale só 9 unidades
/// seria arredondado duas vezes, e o peso deixaria de cair sempre que o lance
/// se afasta do melhor (medido: d = 2029 pesava menos que d = 2030).
pub fn peso_q32(abaixo: i64) -> u64 {
    if abaixo <= 0 {
        return UM_Q32;
    }
    if abaixo >= PONTOS_SEM_PESO {
        return 0;
    }
    let d = abaixo as usize;
    let fracao = produto_q32(EXP_DECIMOS[(d / 10) % 10], EXP_CENTESIMOS[d % 10]);
    produto_q32(EXP_INTEIROS[d / 100], fracao)
}

/// Sorteia um índice da lista com chance proporcional a e^(pontos/100): o
/// softmax, sem ponto flutuante. `sorteio` é um número cru do gerador; o índice
/// sai pelo **resto da divisão** dele pelo total dos pesos, andando a lista até
/// achar a faixa em que ele cai (a lista já está na ordem estável, R-05).
///
/// A lista não pode ser vazia (quem chama sempre tem o melhor lance nela).
pub fn indice_sorteado(pontos: &[i64], sorteio: u64) -> usize {
    let maximo = pontos.iter().copied().max().unwrap_or(0);
    let pesos: Vec<u64> = pontos.iter().map(|&p| peso_q32(maximo - p)).collect();
    // O total cabe em `u64` com folga: 256 lances × 2³² = 2⁴⁰. E nunca é zero,
    // porque o melhor pesa 2³².
    let total: u64 = pesos.iter().sum();
    let mut alvo = sorteio % total.max(1);
    for (indice, &peso) in pesos.iter().enumerate() {
        if alvo < peso {
            return indice;
        }
        alvo -= peso;
    }
    // Inalcançável (o alvo é menor que a soma); fica o último por cuidado.
    pesos.len().saturating_sub(1)
}
