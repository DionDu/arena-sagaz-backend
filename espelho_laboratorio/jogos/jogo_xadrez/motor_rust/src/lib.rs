//! O motor do xadrez da Arena Sagaz (spec 012).
//!
//! Um crate só, com UMA porta para o mundo (`xadrez_pedir`, em `ffi.rs`), que o
//! app, a bancada e o servidor usam igual: um texto JSON entra, um texto JSON sai
//! (research.md R-02). As regras do xadrez (lances legais, xeque, mate) vêm da
//! `cozy-chess`; a busca, a avaliação e o que é do jogo da Arena são nossos.
//!
//! O mapa dos módulos é o do research.md R-01. Em Rust, `pub mod nome;` declara
//! que existe um arquivo `src/nome.rs` com aquele módulo, e o `pub` o deixa
//! visível para quem usa o crate (os testes de `tests/` e o `ferramentas_rust`).
//!
//! ⚠️ Determinismo por construção (R-05): nada de `f32`/`f64`, `HashMap`,
//! `HashSet`, `rand`, threads, e relógio só em `relogio.rs`. O cadeado
//! `tests/cadeados_de_fonte.rs` varre esta pasta e falha se aparecerem.

/// O gerador de números NOSSO (SplitMix64), semeado de fora.
pub mod aleatorio;
/// A avaliação de uma posição, em centipeões inteiros.
pub mod avaliacao;
/// A busca: negamax, alfa-beta, aprofundamento iterativo, TT e quiescência.
pub mod busca;
/// A leitura do `contrato_xadrez.json` - o único lugar com a modalidade por nome.
pub mod contrato;
/// O despachante: o pedido JSON vira uma operação, e a resposta volta em JSON.
pub mod despacho;
/// Os fatos de um lance e as peças marcadas (R-13).
pub mod fatos;
/// A borda C: as três funções que o app, a bancada e os testes enxergam.
pub mod ffi;
/// O fim da partida, a ordem das regras e o estado da posição (R-04).
pub mod fim_de_partida;
/// O ruído dos níveis: o mate em um, o erro entre os plausíveis e a cegueira (R-09, R-10).
pub mod niveis;
/// A posição na fronteira (FEN inicial + lances), a notação interna e o perft.
pub mod posicao;
/// O Radar (R-15).
pub mod radar;
/// O motivo de um lance recusado (R-14).
pub mod recusa;
/// O relógio: o único arquivo que lê a hora (rede de tempo e telemetria).
pub mod relogio;
