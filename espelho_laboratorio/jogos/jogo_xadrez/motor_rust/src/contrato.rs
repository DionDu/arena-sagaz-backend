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

use crate::busca::{Limites, Quiescencia};
use crate::fim_de_partida::{Motivo, RegrasDoFim, MAIOR_LIMITE_DOS_CINQUENTA};
use crate::niveis::Ruido;

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

/// Um nível (R-09). Os campos do ruído (margem, chances) vão para `niveis.rs`
/// por [`Nivel::ruido`] (T038 e T039).
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
}

impl Nivel {
    /// Os números do ruído deste nível, no formato que `niveis.rs` usa.
    pub fn ruido(&self) -> Ruido {
        Ruido {
            margem_do_erro_cp: self.margem_do_erro_cp,
            chance_do_erro_milesimos: self.chance_do_erro_milesimos,
            chance_da_cegueira_milesimos: self.chance_da_cegueira_milesimos,
        }
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
            for (nome, nivel) in &modalidade.niveis {
                validar_nivel(nome_da_modalidade, nome, nivel)?;
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
    if nivel.chance_do_erro_milesimos > 1000 || nivel.chance_da_cegueira_milesimos > 1000 {
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
    Ok(())
}
