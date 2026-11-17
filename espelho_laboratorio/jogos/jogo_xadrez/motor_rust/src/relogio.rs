//! O relógio do motor: o ÚNICO arquivo de `src/` que pode ler a hora
//! (research.md R-05; o cadeado `tests/cadeados_de_fonte.rs` cobra).
//!
//! O tempo serve a duas coisas, e **nenhuma decide um lance**:
//!
//! 1. a **rede de tempo** da busca (T010): se um pedido traz um limite em
//!    segundos e a busca passa dele, ela para e devolve o motivo `tempo`. É falha
//!    registrada, não recurso (RF-XDR-081): fica bem acima do pior lance medido;
//! 2. o **`tempo_ms` de telemetria** das respostas (`perft`, `buscar`), que a
//!    bancada usa para medir nós/ms.
//!
//! Por que isolar aqui: o mesmo pedido tem de dar o mesmo lance em qualquer
//! máquina (RF-XDR-050). Um `Instant` solto na busca é a porta por onde a
//! velocidade do aparelho entra na escolha - foi a 1ª causa da divergência das
//! damas. Com o relógio num arquivo só, o cadeado consegue dizer "em nenhum
//! outro lugar".

use std::time::{Duration, Instant};

/// Um cronômetro iniciado na criação.
#[derive(Debug, Clone, Copy)]
pub struct Cronometro {
    inicio: Instant,
}

impl Cronometro {
    /// Começa a contar agora.
    pub fn iniciar() -> Self {
        Cronometro {
            inicio: Instant::now(),
        }
    }

    /// Milissegundos desde o início (inteiro; a fração é descartada).
    pub fn ms(&self) -> u64 {
        // `as_millis()` devolve `u128`; um `u64` de milissegundos cobre 584
        // milhões de anos, então a conversão não perde nada na prática.
        self.inicio.elapsed().as_millis() as u64
    }

    /// Diz se já passaram `segundos` desde o início.
    pub fn passou_de(&self, segundos: u64) -> bool {
        self.inicio.elapsed() >= Duration::from_secs(segundos)
    }
}
