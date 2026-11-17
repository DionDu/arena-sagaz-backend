//! O MOTOR DO APARELHO, ATENDENDO O SERVIDOR: um pedido por linha (T042;
//! research.md R-20; `contracts/motor-xadrez.md` §1.1).
//!
//! ## Por que este programa existe
//!
//! O Desafio do Dia precisa que o servidor jogue xadrez EXATAMENTE como o
//! aparelho joga: o gabarito de um desafio é uma partida contra a Cacau, a Pita,
//! o Tex ou o Magno, e a pessoa tem de poder segui-la lance a lance. As damas, o
//! Pontinhos e o Quatro ensinaram a mesma lição, cada um com um episódio: a mesma
//! regra escrita duas vezes acaba discordando, às vezes sem erro nenhum.
//!
//! Por isso o xadrez não tem segunda escrita nem árbitro em Python (RF-XDR-043):
//! este executável chama **a mesma função `despachar`** que o app chama pela
//! borda C (`src/ffi.rs`) e que os testes chamam direto. A resposta que ele
//! escreve é o texto do `despachar`, **byte a byte**, sem nada acrescentado.
//!
//! ## A conversa
//!
//! ```text
//! servidor_de_lances_xadrez --contrato <caminho do contrato_xadrez.json>
//! ```
//!
//! 1. Ao abrir, ANTES de ler qualquer pedido, escreve uma linha de apresentação:
//!    a versão do protocolo, a do motor, o SHA-256 do contrato que leu e o
//!    **carimbo** (o resumo das fontes com que foi compilado). O lado Python
//!    (`motores/nucleo/processo_dart.py`, `ProcessoDart`) a lê e recusa a conversa
//!    se algo não for o dele.
//! 2. Depois, para cada linha de JSON que chega, escreve uma linha de resposta,
//!    na mesma ordem. Linha vazia é ignorada.
//! 3. Quando a entrada acaba, sai com código 0.
//!
//! ## Por que o contrato entra pela linha de comando
//!
//! As operações que dependem das regras da modalidade (`estado`, `aplicar`,
//! `buscar`, `jogada_ideal`) levam no pedido o **texto** do contrato (R-02): é
//! assim que o app faz, com o asset. Aqui, quem põe o texto no pedido é o
//! executável, lido uma vez na abertura. Assim o Python não manda 10 kB a cada
//! lance, e o contrato com que se joga é o mesmo cujo SHA-256 foi anunciado.
//!
//! ⚠️ Por isso um pedido que JÁ traga o campo `contrato` é **recusado**, e não
//! sobrescrito: ele mostra um chamador que acha que manda o contrato, e
//! sobrescrever esconderia esse engano (jogar-se-ia com outro contrato que não o
//! dele, sem aviso).
//!
//! ## O carimbo
//!
//! O carimbo é calculado FORA do Rust (R-20: o crate não leva um `sha2`), pelo
//! script que compila (`scripts/compilar_motor_xadrez.py`, T061), e chega por
//! variável de ambiente no momento da compilação:
//!
//! ```text
//! CARIMBO_MOTOR_XADREZ=<sha-256> cargo build --release --bin servidor_de_lances_xadrez
//! ```
//!
//! `option_env!` lê a variável **durante a compilação** e grava o valor dentro do
//! binário (e o `cargo` recompila quando ela muda). Sem ela, o carimbo é
//! `"sem_carimbo"`: é o executável de uma compilação local (o `cargo test`, por
//! exemplo), e o lado Python (T063) recusa esse valor de propósito.
//!
//! ## O SHA-256 do contrato, escrito aqui
//!
//! O contrato precisa de um SHA-256 calculado DENTRO do processo (só ele sabe que
//! bytes leu). Como o crate não leva um `sha2`, a função está escrita neste
//! arquivo (o módulo `sha256`, ao fim), conferida pelos vetores do padrão
//! (FIPS 180-4). ⚠️ Ela mora em `src/bin/`, e não em `src/`, de propósito: o
//! resumo das fontes do manifesto do app lê só `src/*.rs` (`hash_das_fontes.ps1`),
//! e este arquivo não muda nenhum binário que vai para o aparelho.

use std::io::{self, BufRead, Write};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::process::ExitCode;

use motor_xadrez::contrato::Contrato;
use motor_xadrez::despacho::{despachar, erro};
use serde_json::{json, Value};

/// A versão do PROTOCOLO desta porta, e não a do motor.
///
/// ⚠️ Sobe quando o formato da conversa muda de um jeito que o outro lado
/// precise saber (a apresentação, o jeito de pôr o contrato no pedido). A versão
/// do MOTOR (`Cargo.toml`) sobe quando muda um lance; esta, quando muda a porta.
const VERSAO_DO_PROTOCOLO: u32 = 1;

/// O valor do carimbo quando a compilação não o recebeu.
const SEM_CARIMBO: &str = "sem_carimbo";

/// O código de saída de um uso errado (argumento faltando, contrato ilegível):
/// o mesmo `2` dos executáveis Dart, que o `ProcessoDart` mostra no erro.
const SAIDA_DE_USO_ERRADO: u8 = 2;

/// O carimbo gravado na compilação, ou `"sem_carimbo"`.
///
/// `option_env!` devolve `Option<&'static str>`: `Some` com o texto se a
/// variável existia quando o `cargo` compilou, `None` se não existia. Uma
/// variável VAZIA conta como ausente, porque um carimbo vazio também não prova
/// de que fontes o binário saiu.
fn carimbo() -> &'static str {
    match option_env!("CARIMBO_MOTOR_XADREZ") {
        Some(valor) if !valor.is_empty() => valor,
        _ => SEM_CARIMBO,
    }
}

/// Lê o caminho do contrato dos argumentos: exatamente `--contrato <caminho>`.
///
/// Argumento a mais também é recusado: um `--contrato` escrito errado, ignorado
/// em silêncio, faria o executável parecer aceitar uma opção que não existe.
fn caminho_do_contrato(argumentos: &[String]) -> Result<&str, String> {
    match argumentos {
        // O padrão de fatia `[a, b]` só casa com uma lista de dois itens.
        [opcao, caminho] if opcao == "--contrato" => Ok(caminho.as_str()),
        _ => Err(String::from(
            "uso: servidor_de_lances_xadrez --contrato <caminho do contrato_xadrez.json>",
        )),
    }
}

/// O que o executável leu do contrato na abertura.
struct ContratoLido {
    /// O texto inteiro, que entra em cada pedido.
    texto: String,
    /// O SHA-256 dos BYTES do arquivo, em hexadecimal minúsculo.
    sha256: String,
    /// A versão do formato do contrato (o campo `versao`).
    versao: String,
    /// Os nomes das modalidades, em ordem alfabética (o `BTreeMap` já os guarda
    /// assim).
    modalidades: Vec<String>,
}

/// Lê e valida o contrato. Qualquer problema vira a mensagem do `stderr`.
///
/// ⚠️ Lê em BYTES e calcula o hash sobre eles: é o mesmo que o Python calcula
/// com `read_bytes()`, sem tradução de fim de linha nem de codificação.
fn ler_contrato(caminho: &str) -> Result<ContratoLido, String> {
    let bytes = std::fs::read(caminho).map_err(|e| format!("não li o contrato em {caminho}: {e}"))?;
    let sha256 = sha256::em_hexadecimal(&bytes);
    let texto = String::from_utf8(bytes)
        .map_err(|_| format!("o contrato em {caminho} não é texto UTF-8"))?;
    // A mesma leitura que o `despachar` fará a cada pedido: um contrato que ela
    // recusa recusaria TODOS os pedidos, e é melhor saber na abertura.
    let contrato = Contrato::ler(&texto).map_err(|e| format!("{caminho}: {}", e.detalhe()))?;
    Ok(ContratoLido {
        sha256,
        versao: contrato.versao.clone(),
        modalidades: contrato.por_modalidade.keys().cloned().collect(),
        texto,
    })
}

/// A linha de apresentação, a primeira coisa que sai.
///
/// Os nomes são os que o `ProcessoDart` já lê nos executáveis Dart
/// (`versao_do_protocolo`, `resumo_do_motor`): a T063 abre este executável por
/// ele, sem uma segunda conferência escrita para o Rust.
fn apresentacao(contrato: &ContratoLido) -> Value {
    json!({
        "pronto": true,
        "versao_do_protocolo": VERSAO_DO_PROTOCOLO,
        "motor": "rust",
        "jogo": "xadrez",
        // A versão do `Cargo.toml`, a mesma que `xadrez_versao()` entrega ao app.
        // `env!` (sem o `option_`) é obrigatória: o `cargo` sempre a define.
        "versao": env!("CARGO_PKG_VERSION"),
        // ⚠️ Os bytes do contrato que ESTE processo leu: o Python compara com o
        // do espelho dele. Sem isto, um executável apontado para o contrato de
        // outra versão jogaria com outros níveis, com toda a confiança.
        "sha256_do_contrato": contrato.sha256,
        "versao_do_contrato": contrato.versao,
        "modalidades": contrato.modalidades,
        // ⚠️ De que fontes este binário saiu. O Python recalcula a partir do
        // espelho e RECUSA a conversa se divergir (ou se vier "sem_carimbo").
        "resumo_do_motor": carimbo(),
    })
}

/// Responde a UMA linha da entrada, com o texto exato a escrever de volta.
///
/// - JSON que não é objeto (ou nem é JSON) vai cru ao `despachar`, que devolve o
///   `json_invalido` dele: o mesmo erro que o app receberia.
/// - Objeto com `contrato` é recusado (o porquê está no topo do arquivo).
/// - Objeto sem `contrato` ganha o texto do contrato lido na abertura.
fn responder(linha: &str, contrato: &str) -> String {
    let pedido = match serde_json::from_str::<Value>(linha) {
        // `Value::Object` é o caso "objeto JSON"; o `mut` deixa acrescentar o campo.
        Ok(Value::Object(mut campos)) => {
            if campos.contains_key("contrato") {
                return erro(
                    "pedido_invalido",
                    "o contrato vem do executavel (--contrato); o pedido nao o traz",
                );
            }
            campos.insert(String::from("contrato"), Value::String(contrato.to_owned()));
            Value::Object(campos).to_string()
        }
        // Qualquer outra coisa segue como chegou: o despachante sabe recusá-la.
        _ => linha.to_owned(),
    };
    // A mesma rede da borda C (`ffi.rs`): um pânico dentro do motor vira uma
    // resposta de erro, e o processo continua atendendo. Sem ela, o pânico
    // derrubaria o executável no meio de uma régua de horas por um pedido só.
    // (`AssertUnwindSafe`: cada pedido monta tudo do zero, então nada fica
    // meio-alterado depois de um pânico.)
    match catch_unwind(AssertUnwindSafe(|| despachar(&pedido))) {
        Ok(resposta) => resposta,
        Err(_) => erro("panico", "o motor entrou em panico; o pedido foi descartado"),
    }
}

/// Tira o fim de linha (`\n`, e o `\r` que o Python no Windows põe antes dele).
fn sem_fim_de_linha(bytes: &[u8]) -> &[u8] {
    let mut fim = bytes.len();
    while fim > 0 && (bytes[fim - 1] == b'\n' || bytes[fim - 1] == b'\r') {
        fim -= 1;
    }
    &bytes[..fim]
}

/// O laço da conversa: a apresentação e, depois, uma resposta por linha.
///
/// Recebe a entrada e a saída por parâmetro (os traços `BufRead` e `Write`, e não
/// `stdin`/`stdout` direto), para o teste de unidade conversar com ele sem subir
/// um processo.
fn atender(contrato: &ContratoLido, entrada: &mut impl BufRead, saida: &mut impl Write) -> io::Result<()> {
    writeln!(saida, "{}", apresentacao(contrato))?;
    // ⚠️ `flush` depois de CADA linha: a saída de um processo ligada a um cano é
    // guardada em bloco, e o Python ficaria esperando para sempre por uma linha
    // que está pronta, mas parada no buffer.
    saida.flush()?;

    let mut linha = Vec::new();
    loop {
        linha.clear();
        // `read_until` lê BYTES até o `\n` (inclusive). Ler bytes, e não texto,
        // é o que deixa uma linha com UTF-8 quebrado virar uma resposta de erro
        // em vez de parar o laço.
        if entrada.read_until(b'\n', &mut linha)? == 0 {
            return Ok(()); // a entrada acabou: fim normal da conversa
        }
        let bytes = sem_fim_de_linha(&linha);
        let resposta = match std::str::from_utf8(bytes) {
            // `trim` só para decidir se a linha está vazia; o pedido vai inteiro.
            Ok(texto) if texto.trim().is_empty() => continue,
            Ok(texto) => responder(texto, &contrato.texto),
            Err(_) => erro("json_invalido", "o pedido nao e UTF-8 valido"),
        };
        writeln!(saida, "{resposta}")?;
        saida.flush()?;
    }
}

fn main() -> ExitCode {
    // `skip(1)` pula o nome do próprio programa, que é sempre o 1º argumento.
    let argumentos: Vec<String> = std::env::args().skip(1).collect();
    let contrato = match caminho_do_contrato(&argumentos).and_then(ler_contrato) {
        Ok(c) => c,
        Err(mensagem) => {
            eprintln!("{mensagem}");
            return ExitCode::from(SAIDA_DE_USO_ERRADO);
        }
    };

    // `lock()` pega o `stdin`/`stdout` uma vez só, em vez de a cada linha.
    let mut entrada = io::stdin().lock();
    let mut saida = io::stdout().lock();
    match atender(&contrato, &mut entrada, &mut saida) {
        Ok(()) => ExitCode::SUCCESS,
        // O outro lado fechou o cano no meio: não há a quem avisar pelo stdout.
        Err(e) => {
            eprintln!("a conversa caiu: {e}");
            ExitCode::FAILURE
        }
    }
}

/// O SHA-256 (FIPS 180-4), escrito aqui porque o crate não leva um `sha2` (R-20).
///
/// Só soma, rotação e operações de bits em `u32`, todas com `wrapping_*` (a soma
/// que dá a volta no limite de 32 bits, como manda o padrão, em vez do pânico de
/// estouro que o Rust daria em compilação de depuração).
mod sha256 {
    /// As 64 constantes de cada rodada: os primeiros 32 bits da parte
    /// fracionária da raiz cúbica dos 64 primeiros primos (FIPS 180-4 §4.2.2).
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];

    /// O estado inicial: os primeiros 32 bits da parte fracionária da raiz
    /// quadrada dos 8 primeiros primos (FIPS 180-4 §5.3.3).
    const INICIO: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];

    /// O resumo de `dados`, em 64 caracteres hexadecimais minúsculos (o formato
    /// do `hexdigest()` do Python).
    pub fn em_hexadecimal(dados: &[u8]) -> String {
        resumo(dados).iter().map(|byte| format!("{byte:02x}")).collect()
    }

    /// O resumo de `dados`, em 32 bytes.
    pub fn resumo(dados: &[u8]) -> [u8; 32] {
        // O enchimento (§5.1.1): os dados, um bit 1 (o byte 0x80), zeros até
        // faltarem 8 bytes para um múltiplo de 64, e o tamanho em BITS, em 64
        // bits big-endian.
        let mut mensagem = dados.to_vec();
        mensagem.push(0x80);
        while mensagem.len() % 64 != 56 {
            mensagem.push(0);
        }
        // `wrapping_mul`: o padrão define o tamanho módulo 2⁶⁴.
        let bits = (dados.len() as u64).wrapping_mul(8);
        mensagem.extend_from_slice(&bits.to_be_bytes());

        let mut h = INICIO;
        // `chunks_exact(64)` entrega a mensagem em blocos de 64 bytes; o
        // enchimento acima garante que não sobra resto.
        for bloco in mensagem.chunks_exact(64) {
            comprimir(&mut h, bloco);
        }

        let mut saida = [0u8; 32];
        for (i, palavra) in h.iter().enumerate() {
            saida[i * 4..i * 4 + 4].copy_from_slice(&palavra.to_be_bytes());
        }
        saida
    }

    /// Uma rodada de compressão sobre um bloco de 64 bytes (§6.2.2).
    fn comprimir(h: &mut [u32; 8], bloco: &[u8]) {
        // A agenda: as 16 palavras do bloco (big-endian) e mais 48 derivadas.
        let mut w = [0u32; 64];
        for t in 0..16 {
            w[t] = u32::from_be_bytes([bloco[4 * t], bloco[4 * t + 1], bloco[4 * t + 2], bloco[4 * t + 3]]);
        }
        for t in 16..64 {
            let s0 = w[t - 15].rotate_right(7) ^ w[t - 15].rotate_right(18) ^ (w[t - 15] >> 3);
            let s1 = w[t - 2].rotate_right(17) ^ w[t - 2].rotate_right(19) ^ (w[t - 2] >> 10);
            w[t] = w[t - 16].wrapping_add(s0).wrapping_add(w[t - 7]).wrapping_add(s1);
        }

        // As oito variáveis de trabalho, a..h do padrão, começando do estado.
        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh] = *h;
        for t in 0..64 {
            let soma1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let escolha = (e & f) ^ (!e & g); // Ch: bit de f onde e é 1, de g onde é 0
            let t1 = hh.wrapping_add(soma1).wrapping_add(escolha).wrapping_add(K[t]).wrapping_add(w[t]);
            let soma0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maioria = (a & b) ^ (a & c) ^ (b & c); // Maj: o bit que aparece em 2 dos 3
            let t2 = soma0.wrapping_add(maioria);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }

        // O estado novo é o anterior somado ao resultado da rodada.
        for (i, valor) in [a, b, c, d, e, f, g, hh].into_iter().enumerate() {
            h[i] = h[i].wrapping_add(valor);
        }
    }
}

/// Os testes de unidade deste executável. O `cargo test` os roda junto com os
/// de `tests/`; a conversa com o processo de verdade está em
/// `tests/servidor_de_lances.rs`.
#[cfg(test)]
mod testes {
    use super::*;

    /// O SHA-256 bate com os vetores do padrão (FIPS 180-4, exemplos do NIST),
    /// incluindo os casos de borda do enchimento: vazio, um bloco, e a mensagem
    /// de 56 bytes que obriga um 2º bloco só para o tamanho.
    #[test]
    fn sha256_bate_com_os_vetores_do_padrao() {
        let casos: [(&[u8], &str); 4] = [
            (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
            (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
            (
                b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
                "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
            ),
            (
                b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
                "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1",
            ),
        ];
        for (dados, esperado) in casos {
            assert_eq!(sha256::em_hexadecimal(dados), esperado, "{:?}", String::from_utf8_lossy(dados));
        }
        // Um milhão de "a": muitos blocos seguidos (o vetor longo do NIST).
        let milhao = vec![b'a'; 1_000_000];
        assert_eq!(
            sha256::em_hexadecimal(&milhao),
            "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
        );
    }

    /// Só `--contrato <caminho>` é aceito, e nada a mais nem a menos.
    #[test]
    fn os_argumentos() {
        let lista = |v: &[&str]| v.iter().map(|s| s.to_string()).collect::<Vec<_>>();
        assert_eq!(caminho_do_contrato(&lista(&["--contrato", "c.json"])), Ok("c.json"));
        assert!(caminho_do_contrato(&lista(&[])).is_err());
        assert!(caminho_do_contrato(&lista(&["--contrato"])).is_err());
        assert!(caminho_do_contrato(&lista(&["--contratos", "c.json"])).is_err());
        assert!(caminho_do_contrato(&lista(&["--contrato", "c.json", "--outro"])).is_err());
    }

    /// O fim de linha sai, o resto do pedido fica.
    #[test]
    fn o_fim_de_linha() {
        assert_eq!(sem_fim_de_linha(b"{}\r\n"), b"{}");
        assert_eq!(sem_fim_de_linha(b"{}\n"), b"{}");
        assert_eq!(sem_fim_de_linha(b"{}"), b"{}");
        assert_eq!(sem_fim_de_linha(b" {} \n"), b" {} ");
    }

    /// O laço, sem processo: a apresentação, a linha vazia pulada, o UTF-8
    /// quebrado respondido, e o fim da entrada encerrando sem erro.
    #[test]
    fn o_laco_sem_processo() {
        let caminho = concat!(env!("CARGO_MANIFEST_DIR"), "/../contrato/contrato_xadrez.json");
        let contrato = ler_contrato(caminho).expect("o contrato da fonte tem de ser lido");
        // Três linhas: um perft, uma vazia, e bytes que não são UTF-8.
        let mut entrada: &[u8] = b"{\"operacao\":\"perft\",\"posicao\":{\"fen_inicial\":\"8/8/8/8/8/8/8/K6k w - - 0 1\"},\"profundidade\":1}\n\n\xff\xfe\n";
        let mut saida = Vec::new();
        atender(&contrato, &mut entrada, &mut saida).unwrap();
        let texto = String::from_utf8(saida).unwrap();
        let linhas: Vec<&str> = texto.lines().collect();
        assert_eq!(linhas.len(), 3, "{texto}");
        let abertura: Value = serde_json::from_str(linhas[0]).unwrap();
        assert_eq!(abertura["jogo"], "xadrez");
        assert_eq!(abertura["sha256_do_contrato"], contrato.sha256);
        let perft: Value = serde_json::from_str(linhas[1]).unwrap();
        assert_eq!(perft["ok"], true, "{perft}");
        assert_eq!(perft["nos"], 3, "o rei de a1 tem tres casas: {perft}");
        let quebrado: Value = serde_json::from_str(linhas[2]).unwrap();
        assert_eq!(quebrado["erro"], "json_invalido");
    }
}
