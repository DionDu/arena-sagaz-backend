//! O ruído de cada nível: o mate em um, o erro entre lances plausíveis, a
//! cegueira e o Magno sem ruído (research.md R-09, R-10).
//!
//! ## A ordem, a cada lance (R-09)
//!
//! 1. **Lance único**: sai sem busca e sem sorteio (como antes da T038).
//! 2. **Mate em um** (RF-XDR-073): se algum lance dá mate, sai, em qualquer
//!    nível. Nenhum sorteio passa por cima: perder um mate em um é o erro que
//!    nenhum adversário da Arena comete, nem a Cacau. É também o que salva a
//!    Cacau de si mesma: com profundidade 1 e sem quiescência, a busca dela
//!    avalia a posição DEPOIS do lance sem olhar se o outro ainda tem lance, e
//!    não enxergaria o mate.
//! 3. **Os sorteios**, todos de uma vez e sempre na mesma ordem (ver abaixo).
//! 4. Caiu em **erro** (a `chance_do_erro_milesimos` do nível): a busca dá a nota
//!    de cada lance da raiz (`busca::notas_da_raiz`), e sai um dos
//!    **plausíveis**, os lances com nota ≥ melhor − `margem_do_erro_cp`. Fica
//!    de fora o lance que **desfaz** o último lance do próprio personagem (a
//!    torre que vai e volta), quando ele não é o melhor: é o erro que parece
//!    máquina quebrada, e não pessoa distraída. **Qual** plausível sai: com a
//!    mesma chance para todos (a 0.5.0), ou, quando o nível traz a
//!    `temperatura_do_erro_cp` e o `peso_humano_milesimos` (T051c, motor
//!    0.6.0), com peso: a nota da busca mais a naturalidade do lance para uma
//!    pessoa (`humano.rs`), sorteados por softmax inteiro ([`Ponderacao`]).
//!    ⚠️ **Com o resultado provado não há sorteio** (motor 0.9.0, T051j): se a
//!    melhor nota é um mate, a favor ou contra, só o melhor é plausível. Sem
//!    isso, os mates de distâncias diferentes (2 pontos de nota um do outro)
//!    cabiam em qualquer margem, e o Magno perdido podia aceitar o mate mais
//!    rápido (RF-XDR-082).
//! 5. **Sem erro**: a busca comum do nível (`busca::buscar`), e o melhor lance,
//!    com o empate desfeito pela ordem estável (R-05).
//! 6. **A cegueira** (R-10, T039; a `chance_da_cegueira_milesimos`): os passos 4
//!    e 5 rodam de novo com a visão cega (`busca::Visao::Cega`: na resposta do
//!    adversário não existem as capturas de [`o_cego_nao_ve`]), com os mesmos
//!    sorteios, e sai o lance do cego. A `acao` é `cegueira` quando ele difere
//!    do lance que o personagem jogaria enxergando tudo.
//! 7. **A distração** (T051l, motor 0.11.0; a `chance_da_distracao_milesimos`,
//!    `docs/DECISOES-do-dono.md` §8zzzz73): é a cegueira do OUTRO lado. A
//!    cegueira esconde a ameaça do adversário; a distração esconde a
//!    OPORTUNIDADE do próprio personagem. Distraído, ele só enxerga a captura da
//!    peça que o adversário ACABOU de mexer (a atenção está no último lance); a
//!    peça que ficou solta por um lance no outro canto do tabuleiro, ele não vê
//!    ([`a_distraida_nao_ve`]). Ela age no passo 4, no sorteio entre os
//!    plausíveis: os lances que ele não vê saem da lista ANTES de achar o
//!    melhor e a margem (senão a captura invisível, muito melhor que o resto,
//!    empurraria todos os outros para fora da margem). Se ele não vê nenhum
//!    lance (só havia capturas invisíveis), a lista fica inteira.
//!
//! ## Os sorteios saem TODOS antes de qualquer busca
//!
//! O gerador (`aleatorio.rs`) é semeado com a semente do pedido, e cada lance
//! tira **três** números, sempre nesta ordem: (1) o do erro, (2) o da cegueira,
//! (3) qual dos plausíveis. Os três saem mesmo quando não são usados (o nível
//! sem erro, o lance que não errou, o nível sem cegueira). Isso tem dois
//! motivos:
//!
//! - **O Tex** (R-09): a nota de cada lance da raiz custa caro com a busca
//!   funda dele, e só se paga quando ele vai errar. O sorteio do erro vem antes,
//!   do mesmo gerador, e decide se a raiz inteira é buscada.
//! - **Estabilidade**: como cada decisão tem a sua posição fixa na sequência,
//!   ligar uma decisão nova não desloca os números das outras. Quando a T039
//!   ligou a cegueira, a Cacau, o Tex e o Magno (chance zero de cegueira)
//!   continuaram com o mesmo erro e o mesmo plausível para a mesma semente.
//!
//! A distração (T051l) é o **4º** número, tirado DEPOIS dos três de antes, pelo
//! mesmo motivo: os três primeiros continuam iguais para a mesma semente, e os
//! níveis sem distração jogam exatamente como na 0.10.0.
//!
//! ## A `acao` da resposta
//!
//! Diz o que aconteceu, para o log e para a calibração: `lance_unico`,
//! `mate_em_um`, `busca_melhor` (inclusive quando o sorteio caiu em erro e o
//! plausível sorteado foi justamente o melhor: o lance é o mesmo do acerto),
//! `erro_sorteado` (o lance escolhido não é o melhor) e `cegueira` (a cegueira
//! mudou o lance; ela vence o `erro_sorteado`, porque é a causa mais nova).

use cozy_chess::{Board, Move, Piece, Square};

use crate::aleatorio::SplitMix64;
use crate::busca::{
    buscar, buscar_com_visao, chave_estavel, e_captura, melhor_de, notas_da_raiz_com_visao, Limites, Parada, Resultado,
    Visao, MATE, PLY_MAXIMO,
};
use crate::humano::{caracteristicas, indice_sorteado, nota_humana, NUMERO_DE_CARACTERISTICAS};
use crate::posicao::{lances_legais, Posicao};

/// Os números do ruído de um nível, como o contrato os escreve (R-09). As
/// chances são inteiros em milésimos (350 = 35%), para nenhum sorteio passar
/// por ponto flutuante (R-05).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ruido {
    /// Até quantos centipeões abaixo do melhor um lance ainda é "plausível".
    pub margem_do_erro_cp: i32,
    /// Em quantos lances de cada 1000 o personagem erra.
    pub chance_do_erro_milesimos: u32,
    /// Em quantos lances de cada 1000 o personagem fica "cego" (R-10).
    pub chance_da_cegueira_milesimos: u32,
    /// O sorteio do erro com peso (T051c). `None` = a mesma chance para todo
    /// plausível, como na 0.5.0.
    pub ponderacao: Option<Ponderacao>,
    /// Em quantos lances de cada 1000 o personagem fica "distraído" (T051l, o
    /// passo 7 do topo do arquivo). Zero = nunca, como na 0.10.0.
    pub chance_da_distracao_milesimos: u32,
}

/// Como o erro pesa cada plausível (T051c; `humano.rs`): os **pontos** de um
/// lance são `nota × 100 / temperatura + peso_humano × nota_humana / 1000`, em
/// centésimos de "nat", e o lance sai com chance proporcional a e^(pontos/100).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ponderacao {
    /// Quantos centipeões da busca valem um "nat" (100 pontos).
    pub temperatura_do_erro_cp: i32,
    /// Quanto da nota humana entra, em milésimos.
    pub peso_humano_milesimos: i32,
    /// Os pesos do modelo humano da modalidade, na ordem das características.
    pub pesos: [i32; NUMERO_DE_CARACTERISTICAS],
}

impl Ponderacao {
    /// Os pontos de um plausível (ver o tipo). As divisões são por baixo
    /// (`div_euclid`: −0,5 vira −1, e não 0), para os pontos negativos e os
    /// positivos arredondarem para o mesmo lado. A nota humana só é calculada
    /// quando entra na conta (`peso_humano_milesimos` acima de zero).
    pub fn pontos_do_lance(&self, posicao: &Posicao, lance: Move, nota: i32) -> i64 {
        let da_busca = (i64::from(nota) * 100).div_euclid(i64::from(self.temperatura_do_erro_cp));
        if self.peso_humano_milesimos == 0 {
            return da_busca;
        }
        let humana = nota_humana(&caracteristicas(posicao, lance), &self.pesos);
        da_busca + (i64::from(self.peso_humano_milesimos) * humana).div_euclid(1000)
    }
}

/// O que aconteceu na escolha do lance (o campo `acao` da resposta, §2.4).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Acao {
    /// Sem erro (ou o erro sorteou o próprio melhor): saiu o melhor lance.
    BuscaMelhor,
    /// O erro sorteou um plausível que não é o melhor.
    ErroSorteado,
    /// A cegueira saiu, e o lance do cego não é o que ele jogaria enxergando.
    Cegueira,
    /// Havia um mate em um, e ele saiu.
    MateEmUm,
    /// Só havia um lance legal.
    LanceUnico,
}

impl Acao {
    /// O código da fronteira (`contracts/motor-xadrez.md` §2.4).
    pub fn codigo(self) -> &'static str {
        match self {
            Acao::BuscaMelhor => "busca_melhor",
            Acao::ErroSorteado => "erro_sorteado",
            Acao::Cegueira => "cegueira",
            Acao::MateEmUm => "mate_em_um",
            Acao::LanceUnico => "lance_unico",
        }
    }
}

/// O lance escolhido e como se chegou a ele.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Escolha {
    /// O lance, no formato da `cozy-chess`.
    pub lance: Move,
    /// O que aconteceu.
    pub acao: Acao,
    /// A nota DO LANCE ESCOLHIDO, do ponto de vista de quem joga (no erro, a
    /// nota do plausível sorteado, e não a do melhor).
    pub nota: i32,
    /// Quantos nós a busca visitou (zero no lance único e no mate em um; com a
    /// cegueira, a soma da busca cega e da busca com a visão inteira).
    pub nos: u64,
    /// A profundidade da última volta completa.
    pub profundidade: u32,
    /// Por que a busca parou.
    pub parada: Parada,
}

impl Escolha {
    /// A escolha de uma busca comum, sem ruído (a jogada ideal e o nível que não
    /// errou): a `acao` é `lance_unico` ou `busca_melhor`.
    pub fn da_busca(resultado: Resultado) -> Escolha {
        let acao = if resultado.parada == Parada::LanceUnico {
            Acao::LanceUnico
        } else {
            Acao::BuscaMelhor
        };
        Escolha {
            lance: resultado.lance,
            acao,
            nota: resultado.nota,
            nos: resultado.nos,
            profundidade: resultado.profundidade,
            parada: resultado.parada,
        }
    }
}

/// Os três números de um lance (ver o topo do arquivo), já tirados do gerador.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Sorteios {
    /// O personagem erra neste lance?
    pub erro: bool,
    /// O personagem está "cego" neste lance?
    pub cegueira: bool,
    /// O número cru que escolhe o plausível: o índice é o resto da divisão pelo
    /// tamanho da lista, que só se conhece depois da busca.
    pub plausivel: u64,
    /// O personagem está "distraído" neste lance? (T051l, o 4º número.)
    pub distracao: bool,
}

/// Tira os quatro números do lance, na ordem fixa: erro, cegueira, plausível e
/// distração (este, o mais novo, no fim: ver o topo do arquivo).
///
/// "Sai em N de cada 1000" é `abaixo_de(1000) < N`: com N = 0 nunca sai, com
/// N = 1000 sempre sai.
pub fn sortear(semente: u64, ruido: &Ruido) -> Sorteios {
    let mut gerador = SplitMix64::new(semente);
    // Cada linha consome um número do gerador, nesta ordem e sempre.
    let erro = gerador.abaixo_de(1000) < u64::from(ruido.chance_do_erro_milesimos);
    let cegueira = gerador.abaixo_de(1000) < u64::from(ruido.chance_da_cegueira_milesimos);
    let plausivel = gerador.proximo();
    let distracao = gerador.abaixo_de(1000) < u64::from(ruido.chance_da_distracao_milesimos);
    Sorteios {
        erro,
        cegueira,
        plausivel,
        distracao,
    }
}

/// O distraído não vê este lance? (T051l, o passo 7 do topo do arquivo.)
///
/// Some toda captura, MENOS a da peça que o adversário acabou de mexer: é para
/// ela que a atenção está voltada. A peça que ficou solta porque um lance no
/// outro canto do tabuleiro tirou a proteção dela é justamente a que o
/// iniciante não percebe (o erro que o dono descreveu: ele avança um peão,
/// desprotege a dama, e gente fraca nem sempre nota). O en passant come
/// sempre o peão que acabou de andar duas casas, e por isso é visto. Na posição
/// sem lance anterior (o começo da lista), toda captura some. Lance que não
/// captura nunca some.
pub fn a_distraida_nao_ve(posicao: &Posicao, lance: Move) -> bool {
    let tabuleiro = &posicao.tabuleiro;
    if !e_captura(tabuleiro, lance) {
        return false;
    }
    // O en passant: o peão anda na diagonal para uma casa VAZIA.
    let en_passant = tabuleiro.piece_on(lance.to).is_none();
    if en_passant {
        return false;
    }
    // `last()` é o último lance da lista: o do adversário, que acabou de jogar.
    // Vê a captura só quando a vítima está na casa de chegada desse lance.
    posicao.lances.last().map_or(true, |ultimo| ultimo.to != lance.to)
}

/// O lance que dá mate em um, se houver: o primeiro na ordem estável (R-05),
/// quando há mais de um.
///
/// O mate é "o outro lado fica sem lance legal e com o rei em xeque". Não passa
/// pela busca (e não conta nós): é uma conferência de no máximo um lance por
/// lance legal, que cabe em microssegundos em qualquer aparelho.
pub fn mate_em_um(posicao: &Posicao) -> Option<Move> {
    let tabuleiro = &posicao.tabuleiro;
    let mut lances = lances_legais(tabuleiro);
    lances.sort_by_key(|&l| chave_estavel(l));
    lances.into_iter().find(|&lance| {
        let mut depois = tabuleiro.clone();
        depois.play_unchecked(lance);
        // `generate_moves(|_| true)` para no 1º lance que achar e devolve
        // `true`; sem nenhum lance, devolve `false`.
        let sem_lance = !depois.generate_moves(|_| true);
        sem_lance && !depois.checkers().is_empty()
    })
}

/// O lance que **desfaz** o último lance do próprio personagem, se houver: o
/// que volta da casa de chegada para a de saída (a torre de a1 para a3 e de a3
/// para a1). O último lance do personagem é o PENÚLTIMO da lista (o último é o
/// do adversário, que acabou de jogar).
///
/// O peão nunca volta, a promoção não se desfaz e o roque da `cozy-chess` (o rei
/// "capturando" a torre) não tem volta legal: nesses casos o lance devolvido não
/// estará entre os legais, e não exclui nada.
pub fn lance_que_desfaz(posicao: &Posicao) -> Option<(Square, Square)> {
    let n = posicao.lances.len();
    if n < 2 {
        return None;
    }
    let ultimo_do_personagem = posicao.lances[n - 2];
    // (de, para) do lance de volta: o inverso do que ele jogou.
    Some((ultimo_do_personagem.to, ultimo_do_personagem.from))
}

/// O cego não vê esta captura? (research.md R-10, T039.)
///
/// É o que o iniciante perde (RF-XDR-072): ele vê o peão que ataca a peça
/// vizinha e não vê o bispo do outro lado do tabuleiro. Somem:
///
/// - toda captura feita por **cavalo** (o salto em "L" é o ataque que o
///   iniciante mais esquece);
/// - toda captura feita por **peça que anda em linha** (bispo, torre, dama) de
///   **3 casas ou mais** de distância. A distância é a do rei: o maior entre as
///   colunas e as fileiras percorridas (de a1 a d4 são 3; de a1 a a8, 7).
///
/// Peão e rei capturam sempre de perto, e o cego os vê. Lance que não captura
/// nunca some.
pub fn o_cego_nao_ve(tabuleiro: &Board, lance: Move) -> bool {
    if !e_captura(tabuleiro, lance) {
        return false;
    }
    match tabuleiro.piece_on(lance.from) {
        Some(Piece::Knight) => true,
        Some(Piece::Bishop) | Some(Piece::Rook) | Some(Piece::Queen) => {
            // `as i32` converte a coluna (A = 0 ... H = 7) e a fileira em número,
            // para a subtração poder dar negativo; `abs()` tira o sinal.
            let colunas = (lance.from.file() as i32 - lance.to.file() as i32).abs();
            let fileiras = (lance.from.rank() as i32 - lance.to.rank() as i32).abs();
            colunas.max(fileiras) >= DISTANCIA_QUE_O_CEGO_NAO_VE
        }
        _ => false,
    }
}

/// A partir de quantas casas a captura em linha some para o cego (R-10: "a 3
/// casas ou mais").
pub const DISTANCIA_QUE_O_CEGO_NAO_VE: i32 = 3;

/// Escolhe o lance do personagem: a ordem do topo do arquivo, com os limites de
/// busca e o ruído do nível e a semente do pedido. `None` só sem lance legal.
pub fn escolher_lance(posicao: &Posicao, limites: &Limites, ruido: &Ruido, semente: u64) -> Option<Escolha> {
    let raiz = lances_legais(&posicao.tabuleiro);
    if raiz.is_empty() {
        return None;
    }
    // 1. O lance único: a busca comum já sai dele sem busca, com zero nós.
    if raiz.len() == 1 {
        return buscar(posicao, limites).map(Escolha::da_busca);
    }
    // 2. O mate em um, antes de qualquer sorteio (e sem cegueira: o cego não
    //    deixa de ver o mate que ele mesmo dá).
    if let Some(lance) = mate_em_um(posicao) {
        return Some(Escolha {
            lance,
            acao: Acao::MateEmUm,
            // O mate a 1 meio-lance da raiz, na mesma escala da busca.
            nota: MATE - 1,
            nos: 0,
            profundidade: 1,
            parada: Parada::Decidido,
        });
    }
    // 3. Os sorteios, todos antes de buscar.
    let sorteios = sortear(semente, ruido);
    // 4 e 5. O que ele escolhe enxergando tudo...
    let vista = escolher_com_visao(posicao, limites, ruido, &sorteios, Visao::Inteira)?;
    if !sorteios.cegueira {
        return Some(vista);
    }
    // ... e, se a cegueira saiu, o que ele escolhe cego, com os MESMOS sorteios
    // (o mesmo erro e o mesmo plausível). A resposta é a do cego; a da visão
    // inteira serve para a `acao` dizer se a cegueira mudou o lance.
    let cega = escolher_com_visao(posicao, limites, ruido, &sorteios, Visao::Cega)?;
    Some(Escolha {
        acao: if cega.lance != vista.lance {
            Acao::Cegueira
        } else {
            cega.acao
        },
        // As duas buscas rodaram de verdade: os nós são a soma (o cego custa
        // até duas vezes o teto do nível, e a medição por nó continua honesta).
        nos: cega.nos + vista.nos,
        ..cega
    })
}

/// Os passos 4 e 5 do topo do arquivo com uma visão: o erro (a raiz inteira e um
/// plausível) quando o sorteio caiu nele, ou a busca comum.
fn escolher_com_visao(
    posicao: &Posicao,
    limites: &Limites,
    ruido: &Ruido,
    sorteios: &Sorteios,
    visao: Visao,
) -> Option<Escolha> {
    if sorteios.erro {
        if let Some(escolha) = errar(posicao, limites, ruido, sorteios, visao) {
            return Some(escolha);
        }
        // Sem nota nenhuma (o teto não coube nem na 1ª volta): segue para a
        // busca comum, que tem a sua própria resposta para esse caso.
    }
    buscar_com_visao(posicao, limites, visao).map(Escolha::da_busca)
}

/// O passo do erro: busca a raiz inteira e sorteia entre os plausíveis (com a
/// mesma chance, ou com o peso da [`Ponderacao`] do nível). `None` se a busca
/// não deu nenhuma nota.
fn errar(posicao: &Posicao, limites: &Limites, ruido: &Ruido, sorteios: &Sorteios, visao: Visao) -> Option<Escolha> {
    let notas = notas_da_raiz_com_visao(posicao, limites, visao)?;
    let sorteio = sorteios.plausivel;
    // O melhor DE VERDADE: é ele que decide a `acao` (o lance distraído que não
    // é este é um `erro_sorteado`, como qualquer outro erro: a fronteira não
    // ganha código novo, e o app que lê a `acao` não muda).
    let (melhor_de_verdade, _) = notas.melhor();
    // A distração (passo 7 do topo do arquivo): os lances que o distraído não vê
    // saem ANTES de achar o melhor e a margem. Se não sobrar nenhum, fica tudo.
    let visiveis: Vec<(Move, i32)> = if sorteios.distracao {
        notas.notas.iter().copied().filter(|&(lance, _)| !a_distraida_nao_ve(posicao, lance)).collect()
    } else {
        Vec::new()
    };
    // `&[...]` é uma fatia: a lista visível, ou a inteira quando a distração não
    // saiu (ou não sobrou nada visível).
    let lista: &[(Move, i32)] = if visiveis.is_empty() { &notas.notas } else { &visiveis };
    let (melhor_lance, melhor_nota) = melhor_de(lista);
    // `saturating_sub` para no menor `i32` em vez de dar a volta (não acontece
    // com as notas da busca, que cabem em ±32 000; é só cuidado).
    let piso = melhor_nota.saturating_sub(ruido.margem_do_erro_cp);
    let desfaz = lance_que_desfaz(posicao);
    // O resultado já está PROVADO (motor 0.9.0, T051j): a melhor nota é um mate,
    // a favor ou contra. A nota do mate é `MATE - ply`, e dois mates de
    // distâncias diferentes ficam a só 2 pontos um do outro: qualquer margem os
    // poria entre os plausíveis, e o sorteio escolheria entre o mate rápido e o
    // lento. Aqui só o melhor fica: quem ganha dá o mate mais curto que achou, e
    // quem perde escolhe o que mais adia a derrota (RF-XDR-082). É a mesma conta
    // de "decidido" da busca (`busca.rs`): um mate a até `PLY_MAXIMO` meios-lances.
    let decidido = melhor_nota.abs() >= MATE - PLY_MAXIMO as i32;

    // Os plausíveis, na ordem estável (a das notas): a nota no piso ou acima, e
    // o lance de volta só quando ele é o próprio melhor. Com o resultado
    // decidido, só o melhor. Saem da `lista` (a visível, com a distração).
    let plausiveis: Vec<(Move, i32)> = lista
        .iter()
        .copied()
        .filter(|&(lance, nota)| {
            let volta = desfaz == Some((lance.from, lance.to));
            nota >= piso && (!volta || lance == melhor_lance) && (!decidido || lance == melhor_lance)
        })
        .collect();
    // O melhor sempre está na lista (a nota dele é o teto, e ele nunca é
    // excluído), então ela nunca é vazia e o resto da divisão existe.
    let indice = match &ruido.ponderacao {
        // A 0.5.0: a mesma chance para todo plausível.
        None => (sorteio % plausiveis.len() as u64) as usize,
        // A 0.6.0 com a ponderação no contrato: o softmax dos pontos, com o
        // MESMO número cru do sorteio (a sequência de sorteios não muda).
        Some(ponderacao) => {
            let pontos: Vec<i64> = plausiveis
                .iter()
                .map(|&(lance, nota)| ponderacao.pontos_do_lance(posicao, lance, nota))
                .collect();
            indice_sorteado(&pontos, sorteio)
        }
    };
    let (lance, nota) = plausiveis[indice];
    Some(Escolha {
        lance,
        // Comparado com o melhor DE VERDADE (com ou sem distração, ver acima).
        acao: if lance == melhor_de_verdade {
            Acao::BuscaMelhor
        } else {
            Acao::ErroSorteado
        },
        nota,
        nos: notas.nos,
        profundidade: notas.profundidade,
        parada: notas.parada,
    })
}
