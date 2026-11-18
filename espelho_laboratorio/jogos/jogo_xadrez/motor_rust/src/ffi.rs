//! A borda C: as três únicas funções que o app, a bancada e os testes do
//! Flutter enxergam (research.md R-02; `contracts/motor-xadrez.md` §1).
//!
//! | função | o que faz |
//! |---|---|
//! | `xadrez_versao()` | a versão do `Cargo.toml` (`"0.8.0"`), texto estático |
//! | `xadrez_pedir(json)` | um pedido JSON entra, uma resposta JSON sai |
//! | `xadrez_liberar(ptr)` | devolve ao Rust a memória de uma resposta |
//!
//! Nenhuma struct, nenhum callback, nenhum tipo cujo tamanho mude com a
//! arquitetura: só ponteiros para texto terminado em `\0`.
//!
//! ## A regra da memória: quem alocou libera
//!
//! O Rust aloca a resposta, e o Dart devolve o ponteiro a `xadrez_liberar`
//! quando termina de ler. Chamar `free` do lado do Dart corromperia o heap,
//! porque as duas linguagens usam alocadores diferentes.
//!
//! ## `unsafe`, `CString` e `catch_unwind`, para quem nunca viu
//!
//! - **`unsafe`** marca um trecho em que o compilador não consegue provar que a
//!   memória é usada corretamente, e confia em nós. Aqui ele aparece só onde se
//!   lê ou se devolve um ponteiro que veio de fora.
//! - **`CString`/`CStr`** são o texto "à moda do C" (bytes terminados em `\0`),
//!   o único formato que atravessa a fronteira entre linguagens sem tradução.
//! - **`catch_unwind`** pega um pânico (o "erro fatal" do Rust: um índice fora
//!   da faixa, um `unwrap` em `None`) antes que ele atravesse a fronteira. Sem
//!   ele, o pânico mataria o PROCESSO do app, sem exceção em Dart e sem nada no
//!   log. Com ele, vira `{"ok": false, "erro": "panico"}`, e o app continua
//!   vivo. Por isso o `Cargo.toml` usa `panic = "unwind"`, nunca `"abort"`.

use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::panic::{catch_unwind, AssertUnwindSafe};

use crate::despacho::{despachar, erro};

/// A resposta de quando nem o despacho pôde terminar: um pânico capturado.
/// Escrita à mão, sem `serde`, porque é a última linha de defesa.
const RESPOSTA_DE_PANICO: &str =
    r#"{"ok":false,"erro":"panico","detalhe":"o motor entrou em panico; o pedido foi descartado"}"#;

/// A versão do motor, para o app gravar no log (`rust_0.8.0`) e conferir.
///
/// Devolve texto **estático**: o app lê e **não** deve passá-lo a
/// [`xadrez_liberar`]. Liberar memória estática derruba o processo.
#[no_mangle]
pub extern "C" fn xadrez_versao() -> *const c_char {
    // `concat!` cola as fatias em tempo de compilação; o `\0` final é o que faz
    // disto um texto no formato que o C espera.
    concat!(env!("CARGO_PKG_VERSION"), "\0").as_ptr() as *const c_char
}

/// Atende um pedido. Recebe o JSON, devolve o JSON da resposta.
///
/// ⚠️ O ponteiro devolvido pertence ao **Rust**: depois de ler, o app chama
/// [`xadrez_liberar`] com ele, senão vaza memória a cada pergunta.
///
/// Devolve `null` só se nem a resposta de erro puder ser montada (nunca
/// aconteceu; o app trata `null` como "o motor não respondeu").
///
/// # Segurança
///
/// `pedido` tem de ser um ponteiro válido para texto terminado em `\0`, e
/// continuar válido durante a chamada.
#[no_mangle]
pub extern "C" fn xadrez_pedir(pedido: *const c_char) -> *mut c_char {
    envolver(|| {
        if pedido.is_null() {
            return erro("pedido_invalido", "pedido nulo");
        }
        // `CStr::from_ptr` é `unsafe` porque confia que há um `\0` no fim: é a
        // única promessa que o Dart nos faz, e `toNativeUtf8()` a cumpre.
        let bruto = unsafe { CStr::from_ptr(pedido) };
        match bruto.to_str() {
            Ok(texto) => despachar(texto),
            // JSON é UTF-8; bytes inválidos aqui são ponteiro errado ou memória
            // corrompida, não um pedido exótico.
            Err(_) => erro("json_invalido", "o pedido nao e UTF-8 valido"),
        }
    })
}

/// Devolve ao Rust a memória de uma resposta de [`xadrez_pedir`].
///
/// # Segurança
///
/// `ptr` tem de ser **exatamente** um ponteiro que [`xadrez_pedir`] devolveu, e
/// só pode ser passado aqui **uma vez**.
#[no_mangle]
pub extern "C" fn xadrez_liberar(ptr: *mut c_char) {
    if ptr.is_null() {
        return;
    }
    // `catch_unwind` também aqui: liberar é a última coisa que o app faz, e um
    // acidente nesta linha mataria o processo depois de tudo ter dado certo.
    let _ = catch_unwind(|| {
        // Reconstrói a `CString` e a deixa sair de escopo: é isso que devolve o
        // bloco ao alocador do Rust, o mesmo que o entregou.
        unsafe {
            drop(CString::from_raw(ptr));
        }
    });
}

/// Roda `trabalho` dentro do `catch_unwind` e entrega o texto como ponteiro C.
///
/// Separado de [`xadrez_pedir`] para o teste de unidade poder provocar um
/// pânico DE VERDADE aqui dentro e ver o envoltório pegá-lo.
fn envolver(trabalho: impl FnOnce() -> String) -> *mut c_char {
    // `AssertUnwindSafe` diz ao compilador "se houver pânico, nenhum estado
    // meio-alterado sobrevive": verdade aqui, porque cada pedido monta tudo do
    // zero e joga fora no fim (a TT inclusive).
    let texto = match catch_unwind(AssertUnwindSafe(trabalho)) {
        Ok(t) => t,
        Err(_) => String::from(RESPOSTA_DE_PANICO),
    };
    // `CString::new` falha se o texto tiver um `\0` no meio. O JSON que nós
    // montamos não tem; mesmo assim, `null` é melhor que um `unwrap` aqui.
    match CString::new(texto) {
        // `into_raw` entrega a posse do bloco ao chamador.
        Ok(c) => c.into_raw(),
        Err(_) => std::ptr::null_mut(),
    }
}

#[cfg(test)]
mod testes {
    use super::*;

    /// Lê a resposta C e a libera, como o app faz.
    fn ler_e_liberar(ptr: *mut c_char) -> String {
        assert!(!ptr.is_null());
        let texto = unsafe { CStr::from_ptr(ptr) }.to_str().unwrap().to_string();
        xadrez_liberar(ptr);
        texto
    }

    #[test]
    fn o_envoltorio_pega_um_panico_de_verdade() {
        // Um pânico provocado DENTRO do envoltório, como seria um índice fora da
        // faixa no meio da busca.
        let ptr = envolver(|| panic!("panico de teste, de proposito"));
        let resposta: serde_json::Value = serde_json::from_str(&ler_e_liberar(ptr)).unwrap();
        assert_eq!(resposta["ok"], false);
        assert_eq!(resposta["erro"], "panico");
    }

    #[test]
    fn a_versao_e_a_do_cargo_toml() {
        let texto = unsafe { CStr::from_ptr(xadrez_versao()) }.to_str().unwrap();
        assert_eq!(texto, env!("CARGO_PKG_VERSION"));
    }

    #[test]
    fn pedido_nulo_vira_erro_e_nao_queda() {
        let resposta = ler_e_liberar(xadrez_pedir(std::ptr::null()));
        assert!(resposta.contains("\"pedido_invalido\""), "{resposta}");
    }

    #[test]
    fn um_pedido_atravessa_a_borda_inteira() {
        let pedido = CString::new(
            r#"{"operacao":"perft","posicao":{"fen_inicial":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","lances":[]},"profundidade":3}"#,
        )
        .unwrap();
        let resposta: serde_json::Value =
            serde_json::from_str(&ler_e_liberar(xadrez_pedir(pedido.as_ptr()))).unwrap();
        assert_eq!(resposta["ok"], true);
        assert_eq!(resposta["nos"], 8_902);
    }

    #[test]
    fn liberar_nulo_nao_faz_nada() {
        xadrez_liberar(std::ptr::null_mut());
    }
}
