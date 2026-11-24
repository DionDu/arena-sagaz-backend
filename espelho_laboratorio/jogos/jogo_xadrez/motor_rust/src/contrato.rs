//! A leitura do `contrato_xadrez.json` (research.md R-09, R-21;
//! `contracts/motor-xadrez.md` §4).
//!
//! O contrato guarda o que é **da modalidade**: a posição inicial, o tamanho da
//! TT, os relógios de empate e os níveis (profundidade, teto de nós,
//! quiescência, ruído, rede de tempo). Um número de nível existe **num lugar
//! só**: o app passa o texto do contrato no pedido de busca, e o executável do
//! servidor o lê de um arquivo. O pedido diz apenas o NOME do nível.
//!
//! ⚠️ **Modalidade é dado** (aviso 4 do `tasks.md`): este é o único arquivo de
//! `src/` que pode escrever o nome de uma modalidade entre aspas, e hoje nem
//! ele precisa. Quem procura uma modalidade recebe o nome no pedido.
//!
//! O `serde` (`#[derive(Deserialize)]`) gera o código que transforma o JSON
//! nestas estruturas. Ele já recusa sozinho texto no lugar de número e campo
//! obrigatório faltando; o que ele não sabe (uma chance acima de 1000, por
//! exemplo) é conferido em [`Contrato::ler`].

// `BTreeMap` é o mapa ordenado do Rust: a ordem de iteração é a das chaves, e
// não muda de uma execução para outra (o `HashMap` mudaria, R-05).
use std::collections::BTreeMap;

use serde::Deserialize;

use crate::busca::{Limites, Quiescencia, SEM_APEGO};
use crate::fim_de_partida::{Motivo, RegrasDoFim, MAIOR_LIMITE_DOS_CINQUENTA};
use crate::humano::{Caracteristica, NUMERO_DE_CARACTERISTICAS};
use crate::niveis::{Ponderacao, Ruido};

/// O nível que a operação `jogada_ideal` usa (R-28): a busca do Magno sem ruído,
/// com os números dele no contrato. É nome de NÍVEL, e não de modalidade: toda
/// modalidade que oferece a jogada ideal tem um nível com este nome.
pub const NIVEL_DA_JOGADA_IDEAL: &str = "ideal";

/// O que pode dar errado com o contrato, ou com o que se pede a ele. Cada
/// variante vira um código de erro da fronteira (§2 do contrato).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ErroContrato {
    /// O texto não é um contrato válido (JSON torto, campo faltando, texto no
    /// lugar de número, `quiescencia` desconhecida, chance fora de 0 a 1000).
    Invalido(String),
    /// O pedido citou uma modalidade que o contrato não tem.
    ModalidadeDesconhecida(String),
    /// O pedido citou um nível que a modalidade não tem.
    NivelDesconhecido(String),
}

impl ErroContrato {
    /// O código da fronteira.
    pub fn codigo(&self) -> &'static str {
        match self {
            ErroContrato::Invalido(_) => "contrato_invalido",
            ErroContrato::ModalidadeDesconhecida(_) => "modalidade_desconhecida",
            ErroContrato::NivelDesconhecido(_) => "nivel_desconhecido",
        }
    }

    /// O texto do campo `detalhe`.
    pub fn detalhe(&self) -> String {
        match self {
            ErroContrato::Invalido(motivo) => format!("contrato invalido: {motivo}"),
            ErroContrato::ModalidadeDesconhecida(nome) => format!("modalidade desconhecida: {nome}"),
            ErroContrato::NivelDesconhecido(nome) => format!("nivel desconhecido: {nome}"),
        }
    }
}

/// O contrato inteiro.
#[derive(Debug, Clone, Deserialize)]
pub struct Contrato {
    /// A versão do formato do contrato.
    pub versao: String,
    /// A fórmula da semente de cada lance, em texto (documentação para as
    /// pontas que derivam a semente; o motor recebe a semente pronta).
    pub formula_da_semente: String,
    /// A decisão global de o Magno estar no build (RF-XDR-080).
    pub magno_no_build: bool,
    /// As modalidades, pelo nome.
    pub por_modalidade: BTreeMap<String, Modalidade>,
}

/// O que é de uma modalidade.
#[derive(Debug, Clone, Deserialize)]
pub struct Modalidade {
    /// A posição em que a partida começa.
    pub fen_inicial: String,
    /// Quantas entradas a TT tem (R-05: o tamanho é parte do pedido).
    pub entradas_da_tt: u64,
    /// Os motivos de fim que a modalidade conhece, na ordem do R-04.
    pub fim: Vec<String>,
    /// Os relógios de empate (os 50 lances, a repetição). A T019 os lê.
    pub relogios_de_empate: BTreeMap<String, RelogioDeEmpate>,
    /// Os níveis, pelo nome (`cacau`, `pita`, `tex`, `magno`, `ideal`).
    pub niveis: BTreeMap<String, Nivel>,
    /// Os pesos do modelo humano (T051c, motor 0.6.0; `humano.rs`). Opcional:
    /// sem ele, só um nível com o modelo PRÓPRIO (`Nivel::modelo_humano`, T051h,
    /// 0.7.0) pode pedir peso humano, e os outros sorteiam o erro como na 0.5.0.
    /// É o modelo de todo nível que não traz o seu. O `#[serde(default)]` diz ao
    /// `serde` que o campo ausente vira `None` em vez de erro: é o que deixa o
    /// contrato de antes continuar valendo.
    #[serde(default)]
    pub modelo_humano: Option<ModeloHumano>,
}

/// O modelo humano de uma modalidade: o peso de cada característica do lance
/// (`humano::Caracteristica`), pelo NOME, em centésimos de "nat" por unidade.
/// Os pesos saem da Maia por regressão (T051d), e não são escritos à mão.
#[derive(Debug, Clone, Deserialize)]
pub struct ModeloHumano {
    /// Nome da característica → peso inteiro. Nome que não existe é recusado
    /// ([`Contrato::ler`]); característica que não aparece pesa zero (assim um
    /// contrato velho continua válido quando o motor ganha uma característica).
    pub pesos: BTreeMap<String, i32>,
}

/// O maior peso (em valor absoluto) aceito numa característica, no
/// `peso_humano_milesimos` e na `temperatura_do_erro_cp`. É folga larga para a
/// regressão (que dá pesos de dezenas a centenas) e mantém toda a conta dos
/// pontos dentro do `i64` (`humano::nota_humana`, `niveis::pontos_do_lance`).
pub const MAIOR_NUMERO_DO_MODELO: i32 = 100_000;

impl ModeloHumano {
    /// Os pesos na ordem do vetor de características (o que falta é zero).
    /// Os nomes já foram conferidos por [`Contrato::ler`]; um nome desconhecido
    /// aqui seria ignorado.
    pub fn vetor(&self) -> [i32; NUMERO_DE_CARACTERISTICAS] {
        let mut vetor = [0; NUMERO_DE_CARACTERISTICAS];
        for (nome, &peso) in &self.pesos {
            if let Some(c) = Caracteristica::do_nome(nome) {
                vetor[c as usize] = peso;
            }
        }
        vetor
    }
}

/// Um relógio de empate: o limite e quando o app começa a avisar.
#[derive(Debug, Clone, Deserialize)]
pub struct RelogioDeEmpate {
    pub limite: u32,
    pub aviso_quando_faltam: u32,
    pub unidade: String,
}

/// O modo de quiescência como o contrato o escreve. O `rename_all` faz o
/// `serde` ler `"nao"`, `"curta"` e `"sim"`; qualquer outro texto é recusado.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum QuiescenciaNoContrato {
    Nao,
    Curta,
    Sim,
}

/// Um nível (R-09). Os campos do ruído (margem, chances, ponderação) vão para
/// `niveis.rs` por [`Modalidade::ruido_do_nivel`] (T038, T039 e T051c).
#[derive(Debug, Clone, Deserialize)]
pub struct Nivel {
    pub profundidade_maxima: u32,
    pub teto_de_nos: u64,
    pub quiescencia: QuiescenciaNoContrato,
    pub margem_do_erro_cp: i32,
    pub chance_do_erro_milesimos: u32,
    pub chance_da_cegueira_milesimos: u32,
    /// A rede de tempo em segundos. `null` desliga o relógio: é o que a
    /// bancada e a referência do PC usam, para a medição comparar nós com nós
    /// mesmo num aparelho lento (os contratos de verdade levam um número).
    pub rede_de_tempo_s: Option<u64>,
    /// O relógio da pessoa no modo contra a CPU (pergunta B); `null` = sem.
    pub relogio_s: Option<u64>,
    /// O sorteio do erro com PESO (T051c, motor 0.6.0): quantos centipeões da
    /// nota da busca valem um "nat" de preferência. Menor = o personagem olha
    /// mais a nota (erra menos feio). Vem junto com `peso_humano_milesimos`:
    /// os dois ou nenhum. Sem os dois, o erro sorteia com a mesma chance entre
    /// os plausíveis, como na 0.5.0.
    #[serde(default)]
    pub temperatura_do_erro_cp: Option<i32>,
    /// Quanto do modelo humano entra no sorteio, em milésimos (1000 = a nota
    /// humana inteira; 0 = só a nota da busca). Acima de 0 exige um
    /// `modelo_humano`: o do nível ou, sem ele, o da modalidade.
    #[serde(default)]
    pub peso_humano_milesimos: Option<i32>,
    /// O modelo humano PRÓPRIO do nível (T051h, motor 0.7.0): quando existe,
    /// ele **substitui inteiro** o da modalidade para este nível (não se mistura
    /// peso a peso: característica que falta aqui pesa zero, mesmo que a
    /// modalidade lhe dê peso). Nasceu para a Cacau ter um modelo de iniciante
    /// (destilado da Maia-2 abaixo de 1100) sem mexer na Pita e no Tex, que
    /// continuam com o da modalidade. Opcional e aditivo: sem ele, tudo é como
    /// na 0.6.0. Só faz sentido com a ponderação (os dois campos acima); um
    /// modelo no nível sem ela não pesaria nada, e o `ler` o recusa.
    #[serde(default)]
    pub modelo_humano: Option<ModeloHumano>,
    /// A extensão de xeque (T051k, motor 0.10.0, contrato 1.5.0): o lance que
    /// dá xeque não gasta profundidade, e a quiescência não fica parada com o
    /// rei em xeque (`busca.rs`). Aditivo e `false` por padrão
    /// (`#[serde(default)]` lê o campo ausente como `false`): o contrato 1.4.0
    /// continua valendo igual. Ligado só no Magno e no `ideal`
    /// (`docs/DECISOES-do-dono.md` §8zzzz34).
    #[serde(default)]
    pub extensao_de_xeque: bool,
    /// **O apego às peças** (T051l, motor 0.11.0, contrato 1.6.0;
    /// `docs/DECISOES-do-dono.md` §8zzzz73): quantos centipeões a MAIS o
    /// personagem sente ao perder cada peça DELE (a dama, a torre, o bispo, o
    /// cavalo). Com a dama dele valendo 900 + apego e a do adversário 900,
    /// trocar dama por dama vira "perder o apego", e ele recua como gente (ver
    /// `busca.rs`, "O apego"). Aditivo: campo ausente é apego zero, e a busca
    /// fica exatamente a da 0.10.0.
    #[serde(default)]
    pub apego_cp: Option<ApegoNoContrato>,
    /// **A distração** (T051l, motor 0.11.0, contrato 1.6.0; §8zzzz73): em
    /// quantos lances de cada 1000 o personagem só enxerga a captura da peça
    /// que o adversário acabou de mexer (`niveis.rs`, o passo 7). Aditivo: o
    /// campo ausente é zero, e o nível joga como na 0.10.0.
    #[serde(default)]
    pub chance_da_distracao_milesimos: u32,
}

/// O apego de um nível como o contrato o escreve: um número por peça, em
/// centipeões, de 0 a [`MAIOR_APEGO_CP`]. A peça que não aparece tem apego zero.
/// O peão e o rei não têm apego (o dono pediu as quatro peças, §8zzzz73: perder
/// peão não assusta ninguém, e o rei não sai do tabuleiro).
/// `deny_unknown_fields` recusa um nome errado (`"rainha"`), que de outro modo
/// passaria calado como apego zero.
#[derive(Debug, Clone, Copy, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApegoNoContrato {
    #[serde(default)]
    pub dama: i32,
    #[serde(default)]
    pub torre: i32,
    #[serde(default)]
    pub bispo: i32,
    #[serde(default)]
    pub cavalo: i32,
}

/// O maior apego aceito por peça: o valor da própria dama. Mais que isso, o
/// personagem preferiria levar mate a perder uma peça, o que não é gente.
pub const MAIOR_APEGO_CP: i32 = 900;

impl ApegoNoContrato {
    /// O apego no formato da busca: um número por peça, na ordem do `Piece` da
    /// `cozy-chess` (peão, cavalo, bispo, torre, dama, rei), com o peão e o rei
    /// em zero.
    pub fn por_peca(&self) -> [i32; 6] {
        [0, self.cavalo, self.bispo, self.torre, self.dama, 0]
    }
}

impl Contrato {
    /// Lê e valida o texto do contrato.
    pub fn ler(texto: &str) -> Result<Contrato, ErroContrato> {
        let contrato: Contrato =
            serde_json::from_str(texto).map_err(|e| ErroContrato::Invalido(e.to_string()))?;
        if contrato.por_modalidade.is_empty() {
            return Err(ErroContrato::Invalido(String::from("nenhuma modalidade")));
        }
        // `iter()` num `BTreeMap` entrega os pares (nome, valor) em ordem.
        for (nome_da_modalidade, modalidade) in &contrato.por_modalidade {
            if modalidade.niveis.is_empty() {
                return Err(ErroContrato::Invalido(format!("{nome_da_modalidade} sem niveis")));
            }
            validar_fim(nome_da_modalidade, modalidade)?;
            // `as_ref()` transforma `&Option<ModeloHumano>` em `Option<&ModeloHumano>`,
            // que é o que a função recebe (ela só lê).
            validar_modelo_humano(nome_da_modalidade, modalidade.modelo_humano.as_ref())?;
            for (nome, nivel) in &modalidade.niveis {
                validar_nivel(nome_da_modalidade, nome, nivel)?;
                // O modelo do nível é conferido como o da modalidade, com o
                // endereço completo na mensagem (`tradicional.cacau`).
                validar_modelo_humano(&format!("{nome_da_modalidade}.{nome}"), nivel.modelo_humano.as_ref())?;
                // O peso humano precisa de um modelo, venha de onde vier.
                let tem_modelo = nivel.modelo_humano.is_some() || modalidade.modelo_humano.is_some();
                validar_ponderacao(nome_da_modalidade, nome, nivel, tem_modelo)?;
            }
        }
        Ok(contrato)
    }

    /// A modalidade pelo nome, ou `modalidade_desconhecida`.
    pub fn modalidade(&self, nome: &str) -> Result<&Modalidade, ErroContrato> {
        self.por_modalidade
            .get(nome)
            .ok_or_else(|| ErroContrato::ModalidadeDesconhecida(nome.to_string()))
    }
}

impl Modalidade {
    /// O nível pelo nome, ou `nivel_desconhecido`.
    pub fn nivel(&self, nome: &str) -> Result<&Nivel, ErroContrato> {
        self.niveis
            .get(nome)
            .ok_or_else(|| ErroContrato::NivelDesconhecido(nome.to_string()))
    }

    /// Os números do ruído de um nível desta modalidade, no formato que
    /// `niveis.rs` usa. Mora na modalidade, e não no nível, porque o sorteio com
    /// peso pode precisar dos pesos do `modelo_humano` da modalidade (quando o
    /// nível não traz o seu, T051h).
    pub fn ruido_do_nivel(&self, nivel: &Nivel) -> Ruido {
        // O modelo que vale para este nível: o próprio, se houver; senão, o da
        // modalidade. `or` fica com o primeiro `Some` dos dois `Option`.
        let modelo = nivel.modelo_humano.as_ref().or(self.modelo_humano.as_ref());
        // `zip` junta os dois `Option`: só há ponderação com os dois campos (o
        // `ler` já recusou o contrato que traz um sem o outro).
        let ponderacao = nivel
            .temperatura_do_erro_cp
            .zip(nivel.peso_humano_milesimos)
            .map(|(temperatura, peso_humano)| Ponderacao {
                temperatura_do_erro_cp: temperatura,
                peso_humano_milesimos: peso_humano,
                // Sem modelo nenhum (só possível com peso humano zero), pesos zerados.
                pesos: modelo.map_or([0; NUMERO_DE_CARACTERISTICAS], ModeloHumano::vetor),
            });
        Ruido {
            margem_do_erro_cp: nivel.margem_do_erro_cp,
            chance_do_erro_milesimos: nivel.chance_do_erro_milesimos,
            chance_da_cegueira_milesimos: nivel.chance_da_cegueira_milesimos,
            chance_da_distracao_milesimos: nivel.chance_da_distracao_milesimos,
            ponderacao,
        }
    }

    /// Os limites de busca de um nível desta modalidade: profundidade, teto,
    /// quiescência, tamanho da TT e rede de tempo vêm do nível; os dois relógios
    /// de empate (repetição e 50 lances, que a busca vê dentro da árvore desde a
    /// T037) vêm da modalidade, pelas mesmas regras do fim da partida. O ruído
    /// não é limite de busca: ele vem de [`Nivel::ruido`].
    pub fn limites_do_nivel(&self, nivel: &Nivel) -> Limites {
        let regras = RegrasDoFim::da_modalidade(self);
        Limites {
            ocorrencias_da_repeticao: regras.ocorrencias_do_limite,
            meios_lances_do_empate: regras.meios_lances_do_limite,
            profundidade_maxima: nivel.profundidade_maxima,
            teto_de_nos: nivel.teto_de_nos,
            quiescencia: match nivel.quiescencia {
                QuiescenciaNoContrato::Nao => Quiescencia::Nao,
                QuiescenciaNoContrato::Curta => Quiescencia::Curta,
                QuiescenciaNoContrato::Sim => Quiescencia::Sim,
            },
            entradas_da_tt: self.entradas_da_tt,
            rede_de_tempo_s: nivel.rede_de_tempo_s,
            extensao_de_xeque: nivel.extensao_de_xeque,
            // Sem o campo no contrato, o apego é zero em todas as peças (a busca
            // da 0.10.0). `map_or` dá o padrão quando o `Option` é `None`.
            apego_cp: nivel.apego_cp.map_or(SEM_APEGO, |a| a.por_peca()),
        }
    }
}

/// A lista `fim` e os relógios de empate (research.md R-04): todo motivo tem de
/// ser conhecido; o mate e o afogamento são obrigatórios (sem eles uma posição
/// sem lance legal não teria fim); e cada empate "por contagem" listado precisa
/// do seu relógio, com o limite numa faixa que a regra consegue alcançar.
fn validar_fim(modalidade: &str, m: &Modalidade) -> Result<(), ErroContrato> {
    let invalido = |motivo: String| Err(ErroContrato::Invalido(format!("{modalidade}.fim: {motivo}")));
    for codigo in &m.fim {
        if Motivo::do_codigo(codigo).is_none() {
            return invalido(format!("motivo desconhecido: {codigo}"));
        }
    }
    for obrigatorio in [Motivo::XequeMate, Motivo::Afogamento] {
        if !m.fim.iter().any(|c| c == obrigatorio.codigo()) {
            return invalido(format!("falta {}", obrigatorio.codigo()));
        }
    }
    // Os dois empates que contam alguma coisa, e a faixa aceita para o limite
    // de cada um (inclusive nas duas pontas).
    let faixas = [
        // A biblioteca trava o contador de meios-lances em 100 (50 lances).
        (Motivo::CinquentaLances, 1, MAIOR_LIMITE_DOS_CINQUENTA),
        // Com 1 ocorrência toda posição já "se repetiu"; o mínimo é 2.
        (Motivo::RepeticaoTripla, 2, u32::MAX),
    ];
    for (motivo, minimo, maximo) in faixas {
        if !m.fim.iter().any(|c| c == motivo.codigo()) {
            continue;
        }
        let Some(relogio) = m.relogios_de_empate.get(motivo.codigo()) else {
            return invalido(format!("{} sem relogio em relogios_de_empate", motivo.codigo()));
        };
        if relogio.limite < minimo || relogio.limite > maximo {
            return invalido(format!(
                "limite de {} fora de {minimo} a {maximo}: {}",
                motivo.codigo(),
                relogio.limite
            ));
        }
    }
    Ok(())
}

/// O que o `serde` não confere: as faixas.
fn validar_nivel(modalidade: &str, nome: &str, nivel: &Nivel) -> Result<(), ErroContrato> {
    let onde = format!("{modalidade}.{nome}");
    if nivel.chance_do_erro_milesimos > 1000
        || nivel.chance_da_cegueira_milesimos > 1000
        || nivel.chance_da_distracao_milesimos > 1000
    {
        return Err(ErroContrato::Invalido(format!("{onde}: chance fora de 0 a 1000")));
    }
    if nivel.profundidade_maxima == 0 {
        return Err(ErroContrato::Invalido(format!("{onde}: profundidade_maxima zero")));
    }
    if nivel.teto_de_nos == 0 {
        return Err(ErroContrato::Invalido(format!("{onde}: teto_de_nos zero")));
    }
    if nivel.margem_do_erro_cp < 0 {
        return Err(ErroContrato::Invalido(format!("{onde}: margem_do_erro_cp negativa")));
    }
    if let Some(apego) = nivel.apego_cp {
        // O apego negativo seria "torcer para perder a peça"; acima da dama, o
        // mate valeria menos que a peça (ver `MAIOR_APEGO_CP`).
        if apego.por_peca().iter().any(|&a| !(0..=MAIOR_APEGO_CP).contains(&a)) {
            return Err(ErroContrato::Invalido(format!("{onde}: apego_cp fora de 0 a {MAIOR_APEGO_CP}")));
        }
    }
    Ok(())
}

/// Os pesos de um modelo humano (o da modalidade ou o de um nível): todo nome
/// tem de ser uma característica que o motor conhece, e todo peso cabe no teto.
/// `onde` é o endereço que vai na mensagem (`tradicional` ou `tradicional.cacau`).
fn validar_modelo_humano(onde: &str, modelo: Option<&ModeloHumano>) -> Result<(), ErroContrato> {
    let Some(modelo) = modelo else { return Ok(()) };
    for (nome, &peso) in &modelo.pesos {
        if Caracteristica::do_nome(nome).is_none() {
            return Err(ErroContrato::Invalido(format!(
                "{onde}.modelo_humano: caracteristica desconhecida: {nome}"
            )));
        }
        // `unsigned_abs` dá o valor sem sinal sem estourar no menor `i32`.
        if peso.unsigned_abs() > MAIOR_NUMERO_DO_MODELO as u32 {
            return Err(ErroContrato::Invalido(format!(
                "{onde}.modelo_humano: peso de {nome} fora de -{MAIOR_NUMERO_DO_MODELO} a {MAIOR_NUMERO_DO_MODELO}"
            )));
        }
    }
    Ok(())
}

/// O sorteio com peso de um nível: os dois campos juntos, nas faixas, o peso
/// humano só com algum modelo presente (`tem_modelo`: o do nível ou o da
/// modalidade), e o modelo do nível só com a ponderação (sem ela, ele não
/// pesaria nada, e um contrato que o traz assim é engano de quem o escreveu).
fn validar_ponderacao(modalidade: &str, nome: &str, nivel: &Nivel, tem_modelo: bool) -> Result<(), ErroContrato> {
    let onde = format!("{modalidade}.{nome}");
    let invalido = |motivo: &str| Err(ErroContrato::Invalido(format!("{onde}: {motivo}")));
    match (nivel.temperatura_do_erro_cp, nivel.peso_humano_milesimos) {
        (None, None) if nivel.modelo_humano.is_some() => {
            invalido("modelo_humano no nivel sem temperatura_do_erro_cp e peso_humano_milesimos")
        }
        (None, None) => Ok(()),
        (Some(_), None) | (None, Some(_)) => {
            invalido("temperatura_do_erro_cp e peso_humano_milesimos vem juntos")
        }
        (Some(temperatura), Some(peso_humano)) => {
            if !(1..=MAIOR_NUMERO_DO_MODELO).contains(&temperatura) {
                return invalido("temperatura_do_erro_cp fora de 1 a 100000");
            }
            if !(0..=MAIOR_NUMERO_DO_MODELO).contains(&peso_humano) {
                return invalido("peso_humano_milesimos fora de 0 a 100000");
            }
            if peso_humano > 0 && !tem_modelo {
                return invalido("peso_humano_milesimos sem o modelo_humano (do nivel ou da modalidade)");
            }
            Ok(())
        }
    }
}
