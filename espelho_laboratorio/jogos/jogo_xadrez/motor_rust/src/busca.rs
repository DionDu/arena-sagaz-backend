//! A busca do lance (research.md R-06): negamax com alfa-beta, aprofundamento
//! iterativo, tabela de transposição, ordenação dos lances e quiescência.
//!
//! ## As ideias, para quem nunca viu um motor de xadrez
//!
//! - **Negamax**: a nota de uma posição é sempre "do ponto de vista de quem
//!   joga". A nota de um lance para mim é o *negativo* da melhor nota que o
//!   adversário consegue depois dele. Uma função só serve aos dois lados.
//! - **Alfa-beta**: enquanto examina os lances, a busca guarda a faixa
//!   `[alfa, beta]` de notas que ainda interessam. Achou uma resposta do
//!   adversário que já deixa o lance pior do que outro que eu tenho? O resto das
//!   respostas nem é olhado (o "corte"). Mesma resposta da busca inteira, com
//!   muito menos posições visitadas.
//! - **Aprofundamento iterativo**: busca a 1 lance, depois a 2, a 3... Cada volta
//!   completa deixa uma resposta pronta, e a próxima começa pelo melhor lance da
//!   anterior (o que faz o alfa-beta cortar mais cedo).
//! - **Tabela de transposição (TT)**: a mesma posição aparece por caminhos
//!   diferentes; a TT lembra o que já se sabe dela (nota, profundidade, melhor
//!   lance).
//! - **Quiescência**: no fim da profundidade, a busca não para no meio de uma
//!   troca de peças; ela continua só com as capturas (e promoções) até a posição
//!   "acalmar", para não achar que ganhou uma dama que será retomada no lance
//!   seguinte.
//!
//! ## ⚠️ O determinismo (R-05)
//!
//! O orçamento é em **nós** (posições visitadas), contado exatamente: a busca
//! para no nó N e devolve a resposta da **última volta completa**. O relógio
//! existe só como **rede de segurança**, quando o pedido traz um limite, e corta
//! com o motivo `tempo` (falha registrada, RF-XDR-081). A TT é **criada vazia a
//! cada busca**, com índice calculado em `u64` (em `usize` o ARM de 32 bits
//! mandaria o mesmo hash para outra entrada). A ordenação desempata por (origem,
//! destino, promoção), nunca por acaso.
//!
//! ## Os empates dentro da árvore (T037, motor 0.3.0)
//!
//! A busca conhece a repetição e os "50 lances" **da modalidade** (os limites vêm
//! de `relogios_de_empate` no contrato, por [`Limites`]): uma posição da árvore
//! que já apareceu o número de vezes do limite, contando a história da partida
//! desde o `fen_inicial` mais o caminho da busca até ela, vale **0** (empate); e
//! uma posição com o contador de meios-lances no limite vale 0, a menos que seja
//! mate (a FIDE: o lance que completa os 50 e dá mate é mate). É isso que faz o
//! personagem que está perdendo procurar a repetição, e o que está ganhando fugir
//! dela. A regra é a mesma de `fim_de_partida.rs`, contada do mesmo jeito (pela
//! chave de `posicao::chave_da_posicao`); a raiz não é conferida aqui, porque o
//! despachante já recusa a partida terminada. O material insuficiente fica de
//! fora da árvore: a avaliação já dá a essas posições uma nota pequena.
//!
//! ## A nota de cada lance da raiz (T038, motor 0.4.0)
//!
//! O ruído dos níveis (`niveis.rs`, research.md R-09) precisa saber quanto vale
//! **cada** lance da raiz, e não só qual é o melhor: o erro do personagem é
//! sorteado entre os lances "plausíveis" (nota perto da melhor). O alfa-beta da
//! [`buscar`] não dá isso, porque depois do primeiro lance ele só prova que os
//! outros são piores, sem dizer quanto. A [`notas_da_raiz`] busca cada lance da
//! raiz com a **janela inteira** (`-INFINITO` a `INFINITO`), o que custa mais
//! nós, e por isso só roda quando o sorteio do erro já caiu em "erro".
//!
//! ## A visão cega (T039, motor 0.5.0)
//!
//! As duas funções públicas têm uma irmã `_com_visao`: com [`Visao::Cega`], na
//! resposta do adversário (o `ply` 1) não existem as capturas que o iniciante
//! não enxerga (a regra está em `niveis.rs`, R-10), e esse nó não lê nem grava
//! na TT. O resto da árvore é o de sempre.
//!
//! ⚠️ A TT não sabe por que caminho a posição foi alcançada, e uma nota "0 por
//! repetição" pode ser lida por outro caminho. É o compromisso de todo motor com
//! TT, e não fere o determinismo: a TT nasce vazia a cada pedido, e o mesmo
//! pedido percorre a mesma árvore.

use cozy_chess::{Board, Color, Move, Piece, Square};

use crate::avaliacao::{avaliar, valor_da_peca};
use crate::niveis::o_cego_nao_ve;
use crate::posicao::{chave_da_posicao, lances_legais, Posicao};
use crate::relogio::Cronometro;

/// A nota do mate. Um mate a `ply` meios-lances da raiz vale `MATE - ply`:
/// quem ganha prefere o mais curto (nota maior), quem perde o mais longo
/// (`-(MATE - ply)` é "menos ruim" quanto maior o `ply`). É isso que faz o Magno
/// adiar a derrota (RF-XDR-082) sem regra à parte.
pub const MATE: i32 = 30_000;

/// Maior que qualquer nota possível: as bordas da janela inicial.
const INFINITO: i32 = 32_000;

/// O ply mais fundo que a busca alcança (a quiescência inclusive). Também é a
/// faixa que separa "nota de mate" de "nota de material".
pub const PLY_MAXIMO: usize = 128;

/// De quantos em quantos nós a rede de tempo olha o relógio. Ler a hora custa
/// uma chamada ao sistema; a cada 2048 nós o custo some e o atraso do corte fica
/// em microssegundos.
const NOS_ENTRE_OLHADAS_NO_RELOGIO: u64 = 2048;

/// Os três modos de quiescência do contrato (R-09).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Quiescencia {
    /// Nenhuma: no fim da profundidade, vale a nota parada (a Cacau).
    Nao,
    /// Só as recapturas na casa do último lance (a Pita).
    Curta,
    /// Todas as capturas e as promoções a dama (o Tex e o Magno).
    Sim,
}

/// Os limites de uma busca. Vêm do nível, no contrato (`contrato.rs`), e os dois
/// relógios de empate, da modalidade (`Modalidade::limites_do_nivel`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Limites {
    /// Até que profundidade (em meios-lances) o aprofundamento iterativo vai.
    pub profundidade_maxima: u32,
    /// O teto de nós: a busca nunca visita mais que isto.
    pub teto_de_nos: u64,
    /// O modo da quiescência.
    pub quiescencia: Quiescencia,
    /// Quantas entradas a TT tem. Zero desliga a TT (usado nos testes, para
    /// provar que ela não muda a nota das posições resolvidas).
    pub entradas_da_tt: u64,
    /// A rede de tempo, em segundos. `None`: sem relógio nenhum.
    pub rede_de_tempo_s: Option<u64>,
    /// Em quantas ocorrências da mesma posição a modalidade declara empate (3 na
    /// tradicional). `None`: a modalidade não tem esse empate, e a busca não o
    /// vê. Vem de `fim_de_partida::RegrasDoFim`, pelo contrato.
    pub ocorrencias_da_repeticao: Option<u32>,
    /// Quantos meios-lances sem captura nem lance de peão encerram a partida
    /// (100 na tradicional: os "50 lances" de cada lado). `None`: sem esse empate.
    pub meios_lances_do_empate: Option<u32>,
}

/// Por que a busca parou (os códigos da `tb902` das damas, R-06).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Parada {
    /// Completou a profundidade máxima do nível.
    Profundidade,
    /// Chegou ao teto de nós.
    Nos,
    /// A rede de tempo cortou (falha registrada).
    Tempo,
    /// A busca provou o resultado (achou um mate forçado, a favor ou contra).
    Decidido,
    /// Só havia um lance legal: saiu sem busca.
    LanceUnico,
}

impl Parada {
    /// O código da fronteira (contrato §2.4).
    pub fn codigo(self) -> &'static str {
        match self {
            Parada::Profundidade => "profundidade",
            Parada::Nos => "nos",
            Parada::Tempo => "tempo",
            Parada::Decidido => "decidido",
            Parada::LanceUnico => "lance_unico",
        }
    }
}

/// O que a busca devolve.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Resultado {
    /// O lance escolhido, no formato da `cozy-chess` (o roque como "rei captura
    /// torre"; quem converte para a fronteira é `posicao::texto_do_lance`).
    pub lance: Move,
    /// A nota do lance, do ponto de vista de quem joga.
    pub nota: i32,
    /// Quantos nós foram visitados (nunca mais que o teto).
    pub nos: u64,
    /// A profundidade da última volta completa (0 no lance único, ou se nem a
    /// primeira volta coube no teto).
    pub profundidade: u32,
    /// Por que parou.
    pub parada: Parada,
}

/// O tipo da nota guardada na TT: exata, ou só um limite (o alfa-beta cortou e
/// sabe apenas "pelo menos isto" ou "no máximo isto").
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Limite {
    Exata,
    Inferior,
    Superior,
}

/// Uma entrada da TT.
#[derive(Debug, Clone, Copy)]
struct Entrada {
    chave: u64,
    profundidade: u32,
    nota: i32,
    limite: Limite,
    lance: Option<Move>,
}

/// O estado de uma busca: os contadores, a TT e os *killers*. Vive só durante
/// uma chamada de [`buscar`] (a TT nasce vazia a cada pedido, R-05).
struct Busca<'a> {
    limites: &'a Limites,
    nos: u64,
    /// `Some` quando a busca precisa parar; o motivo vai na resposta.
    abortou: Option<Parada>,
    cronometro: Cronometro,
    /// A TT: um vetor de tamanho fixo, posição `chave % tamanho`.
    tt: Vec<Option<Entrada>>,
    /// Dois *killers* por ply: lances quietos que causaram corte naquele ply
    /// em outro ramo, e por isso merecem ser tentados cedo nos irmãos.
    killers: Vec<[Option<Move>; 2]>,
    /// As chaves de repetição de todas as posições desde o `fen_inicial`, mais
    /// as do caminho da busca até o nó de agora (a última é a dele). Cresce ao
    /// descer um lance (`push`) e encolhe ao voltar (`pop`).
    caminho: Vec<u64>,
    /// Se o personagem enxerga tudo ou está "cego" neste lance (T039).
    visao: Visao,
}

/// O que o personagem enxerga na árvore (research.md R-10, T039).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Visao {
    /// Tudo: a busca comum.
    Inteira,
    /// "Cego": na resposta do adversário (o 1º nível abaixo da raiz, `ply` 1),
    /// as capturas que `niveis::o_cego_nao_ve` aponta não existem. Abaixo disso
    /// a árvore volta a ser a de sempre: o cego erra a ameaça imediata, e não
    /// o resto do jogo. A regra de quais capturas somem mora em `niveis.rs`.
    Cega,
}

/// Escolhe o lance de quem joga. `None` só quando não há lance legal (mate ou
/// afogamento: a partida já acabou e não há o que buscar).
///
/// Recebe a [`Posicao`] inteira, e não só o tabuleiro: o histórico de chaves
/// dela é o que deixa a busca ver a repetição (ver o topo do arquivo).
pub fn buscar(posicao: &Posicao, limites: &Limites) -> Option<Resultado> {
    buscar_com_visao(posicao, limites, Visao::Inteira)
}

/// A [`buscar`] com a visão escolhida (a cega é a do personagem que sorteou a
/// cegueira, T039).
pub fn buscar_com_visao(posicao: &Posicao, limites: &Limites, visao: Visao) -> Option<Resultado> {
    let tabuleiro = &posicao.tabuleiro;
    let mut raiz = lances_legais(tabuleiro);
    if raiz.is_empty() {
        return None;
    }
    // Lance único: sai sem busca, com zero nós (R-06).
    if raiz.len() == 1 {
        return Some(Resultado {
            lance: raiz[0],
            nota: avaliar(tabuleiro),
            nos: 0,
            profundidade: 0,
            parada: Parada::LanceUnico,
        });
    }

    let mut busca = Busca::nova(posicao, limites, visao);

    // A resposta da última volta completa: (lance, nota, profundidade).
    let mut completa: Option<(Move, i32, u32)> = None;
    // O melhor da volta em andamento, para o caso raro de nem a 1ª volta caber.
    let mut parcial: Option<(Move, i32)> = None;
    let mut parada = Parada::Profundidade;

    for profundidade in 1..=limites.profundidade_maxima {
        // O melhor da volta anterior vai na frente, os outros na ordem da
        // ordenação comum (estável).
        busca.ordenar(tabuleiro, &mut raiz, 0, completa.map(|c| c.0));

        let mut alfa = -INFINITO;
        let mut melhor: Option<(Move, i32)> = None;
        for &lance in &raiz {
            let mut depois = tabuleiro.clone();
            depois.play_unchecked(lance);
            busca.caminho.push(chave_da_posicao(&depois));
            let nota = -busca.negamax(&depois, profundidade - 1, -INFINITO, -alfa, 1, lance.to);
            busca.caminho.pop();
            if busca.abortou.is_some() {
                break;
            }
            // `>` estrito: no empate fica o primeiro na ordem, que é estável.
            if melhor.map_or(true, |(_, m)| nota > m) {
                melhor = Some((lance, nota));
                parcial = melhor;
            }
            if nota > alfa {
                alfa = nota;
            }
        }

        if let Some(motivo) = busca.abortou {
            // A volta não terminou: vale a anterior.
            parada = motivo;
            break;
        }
        // A volta terminou: `melhor` existe porque a raiz tem lances.
        let (lance, nota) = melhor.expect("raiz com lances");
        completa = Some((lance, nota, profundidade));
        busca.guardar(tabuleiro.hash(), profundidade, nota, Limite::Exata, Some(lance), 0);

        // Achou um mate (a favor ou contra) numa busca de largura total: o
        // resultado está provado, e ir mais fundo não muda o lance.
        if nota.abs() >= MATE - PLY_MAXIMO as i32 {
            parada = Parada::Decidido;
            break;
        }
    }

    let (lance, nota, profundidade) = match completa {
        Some(c) => c,
        // Nem a 1ª volta coube no teto: o melhor lance visto, ou o primeiro da
        // ordenação. Profundidade 0 avisa que a resposta é fraca.
        None => {
            let (lance, nota) = parcial.unwrap_or((raiz[0], avaliar(tabuleiro)));
            (lance, nota, 0)
        }
    };
    Some(Resultado {
        lance,
        nota,
        nos: busca.nos,
        profundidade,
        parada,
    })
}

/// A nota de cada lance da raiz, para o ruído dos níveis (`niveis.rs`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NotasDaRaiz {
    /// Cada lance legal com a sua nota (do ponto de vista de quem joga), na
    /// **ordem estável** de [`chave_estavel`]: assim "o primeiro com a melhor
    /// nota" é o mesmo desempate da busca comum (R-05).
    pub notas: Vec<(Move, i32)>,
    /// Quantos nós as buscas de todos os lances visitaram, somados.
    pub nos: u64,
    /// A profundidade da última volta completa (sempre ≥ 1: sem volta completa
    /// não há nota, e a função devolve `None`).
    pub profundidade: u32,
    /// Por que parou.
    pub parada: Parada,
}

impl NotasDaRaiz {
    /// O melhor lance e a sua nota: a maior nota, e no empate o primeiro na
    /// ordem estável (a lista já está nela).
    pub fn melhor(&self) -> (Move, i32) {
        melhor_de(&self.notas)
    }
}

/// O melhor par (lance, nota) de uma lista NÃO vazia na ordem estável: a maior
/// nota, e no empate o primeiro (o `>` estrito não troca por um igual).
fn melhor_de(notas: &[(Move, i32)]) -> (Move, i32) {
    let mut melhor = notas[0];
    // `&notas[1..]` é a fatia do 2º item em diante.
    for &(lance, nota) in &notas[1..] {
        if nota > melhor.1 {
            melhor = (lance, nota);
        }
    }
    melhor
}

/// A nota de **cada** lance da raiz (ver o topo do arquivo), com o mesmo
/// aprofundamento iterativo, a mesma TT e os mesmos limites da [`buscar`].
///
/// ⚠️ O teto de nós é **um só para a raiz inteira**, e não um por lance: os
/// lances dividem o orçamento entre si (R-09, "com o teto de nós dividido entre
/// os lances"). Por isso o Tex, quando erra, gasta no máximo o mesmo teto de
/// quando acerta, só que alcança menos profundidade.
///
/// Devolve `None` sem lance legal, ou se nem a 1ª volta coube no teto (quem
/// chama cai na busca comum).
pub fn notas_da_raiz(posicao: &Posicao, limites: &Limites) -> Option<NotasDaRaiz> {
    notas_da_raiz_com_visao(posicao, limites, Visao::Inteira)
}

/// A [`notas_da_raiz`] com a visão escolhida (o personagem que sorteou o erro
/// E a cegueira dá nota aos lances sem ver as capturas que o cego não vê).
pub fn notas_da_raiz_com_visao(posicao: &Posicao, limites: &Limites, visao: Visao) -> Option<NotasDaRaiz> {
    let tabuleiro = &posicao.tabuleiro;
    let mut raiz = lances_legais(tabuleiro);
    if raiz.is_empty() {
        return None;
    }
    let mut busca = Busca::nova(posicao, limites, visao);

    // As notas da última volta completa (já na ordem estável) e a profundidade.
    let mut completa: Option<(Vec<(Move, i32)>, u32)> = None;
    let mut parada = Parada::Profundidade;

    for profundidade in 1..=limites.profundidade_maxima {
        // O melhor da volta anterior vai na frente. A ordem não muda nenhuma
        // nota (a janela é inteira), mas enche a TT e os *killers* com a linha
        // principal primeiro, e os outros lances cortam mais cedo dentro deles.
        // `as_ref()` olha o que está dentro do `Option` sem tirá-lo de lá.
        let anterior = completa.as_ref().map(|(notas, _)| melhor_de(notas).0);
        busca.ordenar(tabuleiro, &mut raiz, 0, anterior);

        let mut notas = Vec::with_capacity(raiz.len());
        for &lance in &raiz {
            let mut depois = tabuleiro.clone();
            depois.play_unchecked(lance);
            busca.caminho.push(chave_da_posicao(&depois));
            // A janela inteira para todo lance: a nota volta exata, e não só
            // "pior que o melhor".
            let nota = -busca.negamax(&depois, profundidade - 1, -INFINITO, INFINITO, 1, lance.to);
            busca.caminho.pop();
            if busca.abortou.is_some() {
                break;
            }
            notas.push((lance, nota));
        }

        if let Some(motivo) = busca.abortou {
            // A volta não terminou: vale a anterior inteira (nunca uma mistura
            // de notas de profundidades diferentes).
            parada = motivo;
            break;
        }
        // A volta terminou: a lista volta à ordem estável. As chaves são
        // distintas (dois lances legais nunca têm a mesma origem, destino e
        // promoção), então a ordenação não tem empate para desfazer.
        notas.sort_by_key(|&(lance, _)| chave_estavel(lance));
        let melhor = melhor_de(&notas).1;
        completa = Some((notas, profundidade));

        // A melhor nota é um mate (a favor ou contra): a mesma regra da
        // [`buscar`], o resultado está provado.
        if melhor.abs() >= MATE - PLY_MAXIMO as i32 {
            parada = Parada::Decidido;
            break;
        }
    }

    // O `?` devolve `None` direto se nenhuma volta completou.
    let (notas, profundidade) = completa?;
    Some(NotasDaRaiz {
        notas,
        nos: busca.nos,
        profundidade,
        parada,
    })
}

/// A chave da **ordem estável** de um lance: (origem, destino, promoção), cada
/// casa pelo seu número (a1 = 0 ... h8 = 63) e a promoção 0 quando não há (R-05).
/// É o desempate de toda escolha do motor que não pode depender do acaso.
pub fn chave_estavel(lance: Move) -> (u8, u8, u8) {
    (
        lance.from as u8,
        lance.to as u8,
        lance.promotion.map_or(0u8, |p| p as u8 + 1),
    )
}

impl<'a> Busca<'a> {
    /// O estado de uma busca nova, para a posição e os limites dados. A TT nasce
    /// vazia aqui, a cada pedido (R-05).
    fn nova(posicao: &Posicao, limites: &'a Limites, visao: Visao) -> Busca<'a> {
        Busca {
            limites,
            nos: 0,
            abortou: None,
            cronometro: Cronometro::iniciar(),
            // `vec![None; n]` cria o vetor já cheio de entradas vazias. O tamanho
            // vem do contrato, em `u64`, e só aqui vira `usize` (o tamanho de um
            // vetor); o índice de cada consulta é calculado em `u64`.
            tt: vec![None; limites.entradas_da_tt as usize],
            killers: vec![[None, None]; PLY_MAXIMO + 1],
            // O histórico da partida é copiado: a busca empilha e desempilha nele.
            caminho: posicao.historico_de_chaves.clone(),
            visao,
        }
    }

    /// Este nó é o da resposta do adversário vista por um cego? (`ply` 1 com a
    /// visão cega: ver [`Visao::Cega`].)
    fn cego_neste_no(&self, ply: usize) -> bool {
        self.visao == Visao::Cega && ply == 1
    }

    /// Conta um nó. Devolve `false` quando a busca tem de parar (teto de nós ou
    /// rede de tempo), e já anota o motivo.
    fn contar_no(&mut self) -> bool {
        if self.abortou.is_some() {
            return false;
        }
        // O teto é conferido ANTES de contar: assim `nos` nunca passa dele.
        if self.nos >= self.limites.teto_de_nos {
            self.abortou = Some(Parada::Nos);
            return false;
        }
        self.nos += 1;
        if let Some(segundos) = self.limites.rede_de_tempo_s {
            if self.nos % NOS_ENTRE_OLHADAS_NO_RELOGIO == 0 && self.cronometro.passou_de(segundos) {
                self.abortou = Some(Parada::Tempo);
                return false;
            }
        }
        true
    }

    /// O negamax com alfa-beta. `ply` é a distância da raiz; `ultima_casa` é o
    /// destino do lance que levou a esta posição (a quiescência curta precisa).
    fn negamax(
        &mut self,
        tabuleiro: &Board,
        profundidade: u32,
        mut alfa: i32,
        beta: i32,
        ply: usize,
        ultima_casa: Square,
    ) -> i32 {
        // Os empates da modalidade vêm ANTES da TT e da quiescência: a chave da
        // TT não guarda o contador dos 50 nem o caminho, e uma posição empatada
        // por eles não pode ser avaliada como se a partida continuasse.
        if let Some(nota) = self.empate_na_arvore(tabuleiro, ply) {
            // Conta como nó visitado; se o teto chegou, o valor é descartado.
            return if self.contar_no() { nota } else { 0 };
        }
        if profundidade == 0 || ply >= PLY_MAXIMO {
            return self.quiescencia(tabuleiro, alfa, beta, ply, ultima_casa);
        }
        if !self.contar_no() {
            return 0; // o valor não importa: a volta inteira será descartada
        }

        let chave = tabuleiro.hash();
        let alfa_original = alfa;
        let mut lance_da_tt = None;
        // ⚠️ No nó do cego a TT fica de fora nos dois sentidos: uma nota lida
        // dela foi calculada enxergando tudo (e "devolveria a visão"), e uma nota
        // gravada aqui, sem as capturas, enganaria o resto da árvore.
        let cego = self.cego_neste_no(ply);
        if let Some(e) = if cego { None } else { self.consultar(chave) } {
            lance_da_tt = e.lance;
            if e.profundidade >= profundidade {
                let nota = nota_da_tt(e.nota, ply);
                match e.limite {
                    Limite::Exata => return nota,
                    Limite::Inferior if nota >= beta => return nota,
                    Limite::Superior if nota <= alfa => return nota,
                    _ => {}
                }
            }
        }

        let mut lances = lances_legais(tabuleiro);
        if lances.is_empty() {
            // Sem lance: em xeque é mate (contra quem joga), fora dele é
            // afogamento (empate).
            return if tabuleiro.checkers().is_empty() {
                0
            } else {
                -(MATE - ply as i32)
            };
        }
        if cego {
            // O mate e o afogamento acima são conferidos com TODOS os lances: o
            // cego não inventa um mate só porque não viu a resposta. Aqui somem
            // só as capturas que ele não vê. `retain` mantém na lista os lances
            // para os quais a condição é verdadeira.
            lances.retain(|&l| !o_cego_nao_ve(tabuleiro, l));
            if lances.is_empty() {
                // Todas as respostas eram capturas invisíveis: para o cego, o
                // adversário "não tem o que fazer", e vale a nota parada.
                return self.quiescencia(tabuleiro, alfa, beta, ply, ultima_casa);
            }
        }
        self.ordenar(tabuleiro, &mut lances, ply, lance_da_tt);

        let mut melhor_nota = -INFINITO;
        let mut melhor_lance = None;
        for lance in lances {
            let mut depois = tabuleiro.clone();
            depois.play_unchecked(lance);
            self.caminho.push(chave_da_posicao(&depois));
            let nota = -self.negamax(&depois, profundidade - 1, -beta, -alfa, ply + 1, lance.to);
            self.caminho.pop();
            if self.abortou.is_some() {
                return 0;
            }
            if nota > melhor_nota {
                melhor_nota = nota;
                melhor_lance = Some(lance);
            }
            if nota > alfa {
                alfa = nota;
            }
            if alfa >= beta {
                // Corte. Se foi um lance quieto, ele vira *killer* deste ply.
                if !e_captura_ou_promocao(tabuleiro, lance) {
                    self.anotar_killer(ply, lance);
                }
                break;
            }
        }

        let limite = if melhor_nota <= alfa_original {
            Limite::Superior
        } else if melhor_nota >= beta {
            Limite::Inferior
        } else {
            Limite::Exata
        };
        if !cego {
            self.guardar(chave, profundidade, melhor_nota, limite, melhor_lance, ply);
        }
        melhor_nota
    }

    /// A nota de empate (ou de mate) que a modalidade dá a esta posição da
    /// árvore pelos dois relógios de empate, ou `None` se ela continua. A chave
    /// da posição é a última do `caminho` (quem chama já a empilhou).
    ///
    /// - **Repetição**: quantas vezes a chave de agora aparece no caminho. Só se
    ///   olha para trás até o último lance irreversível (o contador de
    ///   meios-lances diz quantos são: depois de uma captura ou lance de peão,
    ///   nenhuma posição anterior volta), e de dois em dois (a mesma posição tem
    ///   a mesma vez de jogar).
    /// - **50 lances**: o contador da biblioteca no limite é empate, a menos que
    ///   quem joga esteja levando mate (a FIDE: o mate vence o relógio).
    ///
    /// A quiescência não precisa disto: ela só joga capturas e promoções, que
    /// zeram o contador e nunca repetem uma posição.
    fn empate_na_arvore(&self, tabuleiro: &Board, ply: usize) -> Option<i32> {
        let contador = u32::from(tabuleiro.halfmove_clock());
        if let Some(limite) = self.limites.ocorrencias_da_repeticao {
            // `last()` é a chave de agora; o caminho nunca é vazio aqui.
            if let Some(&agora) = self.caminho.last() {
                let ultimo = self.caminho.len() - 1;
                // O mais antigo que ainda pode ser a mesma posição. Com o FEN
                // começando com o contador alto, o histórico é mais curto que
                // ele: `saturating_sub` para no 0 em vez de dar negativo.
                let primeiro = ultimo.saturating_sub(contador as usize);
                // `(primeiro..=ultimo).rev().step_by(2)` visita ultimo,
                // ultimo-2, ultimo-4... sem passar de `primeiro`.
                let ocorrencias = (primeiro..=ultimo)
                    .rev()
                    .step_by(2)
                    .filter(|&i| self.caminho[i] == agora)
                    .count() as u32;
                if ocorrencias >= limite {
                    return Some(0);
                }
            }
        }
        if let Some(limite) = self.limites.meios_lances_do_empate {
            if contador >= limite {
                // Raro (só no limite): aqui vale gerar os lances para ver o mate.
                // `generate_moves(|_| true)` para no 1º lance achado.
                let sem_lance = !tabuleiro.generate_moves(|_| true);
                let em_xeque = !tabuleiro.checkers().is_empty();
                return Some(if sem_lance && em_xeque {
                    -(MATE - ply as i32)
                } else {
                    0
                });
            }
        }
        None
    }

    /// A quiescência: a nota parada, a menos que uma captura (ou promoção) a
    /// melhore. "Ficar parado" (*stand pat*) é permitido porque quem joga não é
    /// obrigado a capturar.
    fn quiescencia(
        &mut self,
        tabuleiro: &Board,
        mut alfa: i32,
        beta: i32,
        ply: usize,
        ultima_casa: Square,
    ) -> i32 {
        if !self.contar_no() {
            return 0;
        }
        let parada = avaliar(tabuleiro);
        if self.limites.quiescencia == Quiescencia::Nao || ply >= PLY_MAXIMO {
            return parada;
        }
        if parada >= beta {
            return parada;
        }
        if parada > alfa {
            alfa = parada;
        }

        // Só os lances "barulhentos": todas as capturas e promoções a dama
        // (modo `sim`), ou só as recapturas na casa do último lance (`curta`).
        // No nó do cego (a Cacau, de profundidade 1, chega ao `ply` 1 já pela
        // quiescência), as capturas que ele não vê também ficam de fora.
        let cego = self.cego_neste_no(ply);
        let mut lances: Vec<Move> = lances_legais(tabuleiro)
            .into_iter()
            .filter(|&l| !(cego && o_cego_nao_ve(tabuleiro, l)))
            .filter(|&l| {
                let barulhento = e_captura(tabuleiro, l) || l.promotion == Some(Piece::Queen);
                let sem_subpromocao = l.promotion.map_or(true, |p| p == Piece::Queen);
                match self.limites.quiescencia {
                    Quiescencia::Sim => barulhento && sem_subpromocao,
                    Quiescencia::Curta => {
                        l.to == ultima_casa && e_captura(tabuleiro, l) && sem_subpromocao
                    }
                    Quiescencia::Nao => false,
                }
            })
            .collect();
        self.ordenar(tabuleiro, &mut lances, ply, None);

        let mut melhor = parada;
        for lance in lances {
            let mut depois = tabuleiro.clone();
            depois.play_unchecked(lance);
            let nota = -self.quiescencia(&depois, -beta, -alfa, ply + 1, lance.to);
            if self.abortou.is_some() {
                return 0;
            }
            if nota > melhor {
                melhor = nota;
            }
            if nota > alfa {
                alfa = nota;
            }
            if alfa >= beta {
                break;
            }
        }
        melhor
    }

    /// Ordena os lances: o da TT (ou o melhor da volta anterior, na raiz)
    /// primeiro; depois capturas e promoções por MVV-LVA (a vítima mais valiosa
    /// pelo atacante mais barato); depois os dois *killers* do ply; depois o
    /// resto. Empate de chave desempata por (origem, destino, promoção), R-05.
    fn ordenar(&self, tabuleiro: &Board, lances: &mut [Move], ply: usize, primeiro: Option<Move>) {
        let killers = self.killers[ply.min(PLY_MAXIMO)];
        // `sort_by_cached_key` calcula a chave uma vez por lance e ordena por
        // ela. A chave é uma tupla, comparada campo a campo: o 1º campo é a
        // prioridade com sinal trocado (menor vem antes = maior prioridade).
        lances.sort_by_cached_key(|&l| {
            let prioridade: i32 = if Some(l) == primeiro {
                3_000_000
            } else if e_captura_ou_promocao(tabuleiro, l) {
                1_000_000 + mvv_lva(tabuleiro, l)
            } else if Some(l) == killers[0] {
                900_000
            } else if Some(l) == killers[1] {
                800_000
            } else {
                0
            };
            let (origem, destino, promocao) = chave_estavel(l);
            (-prioridade, origem, destino, promocao)
        });
    }

    /// Guarda um lance quieto como *killer* do ply (o mais novo em primeiro).
    fn anotar_killer(&mut self, ply: usize, lance: Move) {
        let k = &mut self.killers[ply.min(PLY_MAXIMO)];
        if k[0] != Some(lance) {
            k[1] = k[0];
            k[0] = Some(lance);
        }
    }

    /// A entrada da TT para esta chave, se houver e for desta posição.
    fn consultar(&self, chave: u64) -> Option<Entrada> {
        let indice = self.indice(chave)?;
        match self.tt[indice] {
            Some(e) if e.chave == chave => Some(e),
            _ => None,
        }
    }

    /// Grava na TT, substituindo o que houver ("sempre substitui", R-06). A
    /// nota de mate é guardada relativa à posição, e não à raiz (ver
    /// [`nota_para_a_tt`]).
    fn guardar(
        &mut self,
        chave: u64,
        profundidade: u32,
        nota: i32,
        limite: Limite,
        lance: Option<Move>,
        ply: usize,
    ) {
        if let Some(indice) = self.indice(chave) {
            self.tt[indice] = Some(Entrada {
                chave,
                profundidade,
                nota: nota_para_a_tt(nota, ply),
                limite,
                lance,
            });
        }
    }

    /// O índice da chave na TT: `chave % tamanho`, calculado em `u64` e só
    /// depois convertido (R-05). `None` com a TT desligada (tamanho zero).
    fn indice(&self, chave: u64) -> Option<usize> {
        let tamanho = self.limites.entradas_da_tt;
        if tamanho == 0 {
            None
        } else {
            Some((chave % tamanho) as usize)
        }
    }
}

/// A nota de mate na TT é guardada "a partir desta posição" (somando o ply),
/// porque a mesma posição pode aparecer a distâncias diferentes da raiz. Na
/// leitura, [`nota_da_tt`] desfaz a conta com o ply de quem lê.
fn nota_para_a_tt(nota: i32, ply: usize) -> i32 {
    let limiar = MATE - PLY_MAXIMO as i32;
    if nota >= limiar {
        nota + ply as i32
    } else if nota <= -limiar {
        nota - ply as i32
    } else {
        nota
    }
}

/// O inverso de [`nota_para_a_tt`].
fn nota_da_tt(nota: i32, ply: usize) -> i32 {
    let limiar = MATE - PLY_MAXIMO as i32;
    if nota >= limiar {
        nota - ply as i32
    } else if nota <= -limiar {
        nota + ply as i32
    } else {
        nota
    }
}

/// Diz se o lance captura: há peça do adversário no destino, ou é o en
/// passant (peão andando na diagonal para uma casa vazia).
///
/// ⚠️ O roque da `cozy-chess` tem destino numa peça **da mesma cor** (a torre),
/// e por isso não conta como captura.
pub fn e_captura(tabuleiro: &Board, lance: Move) -> bool {
    let lado: Color = tabuleiro.side_to_move();
    if tabuleiro.color_on(lance.to) == Some(!lado) {
        return true;
    }
    tabuleiro.piece_on(lance.from) == Some(Piece::Pawn)
        && lance.from.file() != lance.to.file()
        && tabuleiro.piece_on(lance.to).is_none()
}

/// Captura ou promoção: os lances que mudam o material.
fn e_captura_ou_promocao(tabuleiro: &Board, lance: Move) -> bool {
    lance.promotion.is_some() || e_captura(tabuleiro, lance)
}

/// A chave MVV-LVA: dez vezes o valor da vítima menos um décimo do valor do
/// atacante, mais o ganho da promoção. O rei atacante conta como 2000, para
/// vir por último entre as capturas da mesma vítima.
fn mvv_lva(tabuleiro: &Board, lance: Move) -> i32 {
    let vitima = if tabuleiro.color_on(lance.to) == Some(!tabuleiro.side_to_move()) {
        // `piece_on` é `Some` aqui (há peça do adversário no destino).
        tabuleiro.piece_on(lance.to).map_or(0, valor_da_peca)
    } else if e_captura(tabuleiro, lance) {
        // O en passant: destino vazio, e a vítima é um peão.
        valor_da_peca(Piece::Pawn)
    } else {
        // Promoção sem captura: não há vítima.
        0
    };
    let atacante = match tabuleiro.piece_on(lance.from) {
        Some(Piece::King) => 2000,
        Some(p) => valor_da_peca(p),
        None => 0,
    };
    let promocao = lance.promotion.map_or(0, valor_da_peca);
    vitima * 10 - atacante / 10 + promocao
}
