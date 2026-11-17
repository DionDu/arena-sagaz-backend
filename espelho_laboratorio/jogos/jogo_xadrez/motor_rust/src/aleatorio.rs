//! O gerador de números do motor: SplitMix64, escrito por nós (research.md R-05).
//!
//! ## Por que um gerador nosso, e não o `rand`
//!
//! O mesmo pedido tem de dar **o mesmo lance** no celular de 32 bits, no de 64,
//! no PC e no servidor Linux (RF-XDR-050). Um gerador de biblioteca pode mudar de
//! algoritmo numa atualização, ou pegar semente do sistema; este aqui é uma
//! fórmula de cinco linhas, fixa para sempre, e a semente sempre chega **de
//! fora**, no pedido (a derivação é a de `semente_da_partida.dart`, 0 a 2³¹−1).
//!
//! ## Por que `wrapping_*`
//!
//! A conta do SplitMix64 estoura os 64 bits de propósito: o "estouro" é parte da
//! mistura. Em Rust, `a + b` com estouro **entra em pânico** no build de depuração
//! e dá a volta no de release; `wrapping_add`/`wrapping_mul` dão a volta nos dois,
//! sempre. Assim o teste (depuração) e o binário (release) contam igual.
//!
//! A fórmula é a do código de referência de Sebastiano Vigna,
//! <https://prng.di.unimi.it/splitmix64.c> (domínio público).

/// O passo somado ao estado a cada número: a parte fracionária da razão áurea
/// vezes 2⁶⁴ (o "golden gamma" do código de referência).
const GAMA: u64 = 0x9e37_79b9_7f4a_7c15;

/// Um gerador SplitMix64. O estado é um `u64` só, então copiar o gerador copia
/// a sequência inteira dali em diante.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SplitMix64 {
    estado: u64,
}

impl SplitMix64 {
    /// Cria o gerador com a semente dada. O estado inicial **é** a semente, como
    /// no código de referência (`x = semente`).
    pub fn new(semente: u64) -> Self {
        SplitMix64 { estado: semente }
    }

    /// O próximo número de 64 bits da sequência.
    pub fn proximo(&mut self) -> u64 {
        // 1. Anda o estado um passo fixo.
        self.estado = self.estado.wrapping_add(GAMA);
        let mut z = self.estado;
        // 2. Embaralha os bits: desloca, mistura por "ou exclusivo" (^) e
        //    multiplica por constantes escolhidas pelo autor. As constantes e os
        //    deslocamentos (30, 27, 31) são os do código de referência.
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }

    /// Um número de 0 até `limite - 1`, para sorteios do tipo "sai em 350 de
    /// cada 1000" (as chances do contrato viajam em milésimos, R-09).
    ///
    /// ⚠️ `limite` zero não tem resposta: devolve 0 em vez de dividir por zero.
    /// O resto da divisão tem um viés minúsculo (2⁶⁴ não é múltiplo de 1000),
    /// da ordem de 1 em 10¹⁶, e é **o mesmo** em toda máquina, que é o que
    /// importa aqui.
    pub fn abaixo_de(&mut self, limite: u64) -> u64 {
        if limite == 0 {
            return 0;
        }
        self.proximo() % limite
    }
}
