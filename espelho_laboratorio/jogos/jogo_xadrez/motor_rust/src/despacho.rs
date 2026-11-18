//! O despachante: um pedido JSON entra, uma resposta JSON sai (research.md R-02;
//! `contracts/motor-xadrez.md` §2).
//!
//! É **a mesma função** para o app (pela borda C, `ffi.rs`), para a bancada e
//! para o executável do servidor (uma linha por pedido). Assim "o que o app
//! pergunta" e "o que o servidor pergunta" são literalmente o mesmo código.
//!
//! As sete operações do contrato: `estado` (§2.1), `aplicar` (§2.2), `recusa`
//! (§2.3), `buscar` (§2.4), `jogada_ideal` (§2.5), `radar` (§2.6) e `perft`
//! (§2.7). As que dependem das regras da modalidade (`estado`, `aplicar`,
//! `buscar`, `jogada_ideal`: o fim da partida e os níveis) levam no pedido o
//! **texto do contrato** e o nome da modalidade; `recusa`, `radar` e `perft`
//! dependem só da posição.
//!
//! Toda resposta é `{"ok": true, ...}` ou `{"ok": false, "erro": "<código>",
//! "detalhe": "<texto>"}`. Nenhum caminho daqui entra em pânico de propósito; se
//! entrar por acidente, a borda C transforma o pânico em `"erro": "panico"`.

use std::collections::BTreeMap;

use cozy_chess::{Color, Move, Square};
use serde::Deserialize;
use serde_json::{json, Value};

use crate::avaliacao::avaliar_para_as_brancas;
use crate::busca::{buscar, Parada};
use crate::contrato::{Contrato, Modalidade, NIVEL_DA_JOGADA_IDEAL};
use crate::fatos::{fatos_do_lance, marcas_em_json, seguir_marcas, Fatos};
use crate::fim_de_partida::{estado, RegrasDoFim};
use crate::niveis::{escolher_lance, Escolha};
use crate::posicao::{casa_do_texto, lance_do_texto, montar, nomes_das_casas, perft, texto_do_lance, Posicao};
use crate::radar::radar;
use crate::recusa::{motivo_da_recusa, SemMotivo};
use crate::relogio::Cronometro;

/// A maior semente aceita: 2³¹−1, a máscara `& 0x7FFFFFFF` da derivação em
/// `semente_da_partida.dart` (R-05). Cabe sem perda em JSON, Dart e Python.
pub const SEMENTE_MAXIMA: u64 = 0x7FFF_FFFF;

/// A maior profundidade de perft aceita pela fronteira. A profundidade 6 da
/// posição inicial já são 119 milhões de folhas: acima disso, um pedido por
/// engano travaria o aparelho por minutos.
pub const PERFT_MAXIMO: u32 = 6;

/// O pedido, como chega. Todo campo além de `operacao` é opcional AQUI, e cada
/// operação confere os que precisa: assim a mensagem de erro diz qual faltou.
#[derive(Debug, Deserialize)]
struct Pedido {
    operacao: String,
    modalidade: Option<String>,
    posicao: Option<PosicaoNoPedido>,
    profundidade: Option<u32>,
    nivel: Option<String>,
    /// A semente como valor JSON cru: lida à mão, para que um número negativo,
    /// grande demais ou com vírgula vire `semente_invalida`, e não `json_invalido`.
    semente: Option<Value>,
    /// O texto do contrato (o app o manda nos pedidos que dependem dele, R-02).
    contrato: Option<String>,
    /// O lance do `aplicar`, na notação interna.
    lance: Option<String>,
    /// As peças marcadas do `aplicar`: nome → casa (ou `null`, já comida).
    marcas: Option<BTreeMap<String, Option<String>>>,
    /// A origem e o destino do gesto recusado (`recusa`); sem `para`, a
    /// pergunta é "por que essa peça não tem lance?".
    de: Option<String>,
    para: Option<String>,
    /// O lado do Radar (`branca` ou `preta`).
    lado: Option<String>,
}

/// `{"fen_inicial": "...", "lances": [...]}` (R-03).
#[derive(Debug, Deserialize)]
struct PosicaoNoPedido {
    fen_inicial: String,
    #[serde(default)]
    lances: Vec<String>,
}

/// A resposta de erro, no formato do contrato.
pub fn erro(codigo: &str, detalhe: impl Into<String>) -> String {
    json!({"ok": false, "erro": codigo, "detalhe": detalhe.into()}).to_string()
}

/// Atende um pedido. Nunca devolve texto vazio nem JSON inválido.
pub fn despachar(pedido: &str) -> String {
    // `match` sobre o resultado: `Ok` traz o pedido lido, `Err` o motivo.
    let pedido: Pedido = match serde_json::from_str(pedido) {
        Ok(p) => p,
        Err(e) => return erro("json_invalido", e.to_string()),
    };
    // Cada operação devolve `Result<String, String>`: no `Ok` a resposta de
    // sucesso, no `Err` a de erro, já prontas. O `unwrap_or_else(|e| e)` pega
    // as duas sem distinção, porque as duas já são o texto a devolver.
    let resposta = match pedido.operacao.as_str() {
        "estado" => operacao_estado(&pedido),
        "aplicar" => operacao_aplicar(&pedido),
        "recusa" => operacao_recusa(&pedido),
        "buscar" => operacao_buscar(&pedido),
        "jogada_ideal" => operacao_jogada_ideal(&pedido),
        "radar" => operacao_radar(&pedido),
        "perft" => operacao_perft(&pedido),
        outra => Err(erro("operacao_desconhecida", format!("operacao desconhecida: {outra}"))),
    };
    resposta.unwrap_or_else(|e| e)
}

// ── Peças comuns às operações ────────────────────────────────────────────────

/// Monta a posição do pedido, ou devolve a resposta de erro pronta.
fn posicao_do_pedido(pedido: &Pedido) -> Result<Posicao, String> {
    let p = pedido
        .posicao
        .as_ref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo posicao"))?;
    montar(&p.fen_inicial, &p.lances).map_err(|e| erro(e.codigo(), e.detalhe()))
}

/// Lê o contrato do pedido e devolve a modalidade pedida (uma cópia: o
/// contrato inteiro não precisa viver além do pedido).
fn modalidade_do_pedido(pedido: &Pedido) -> Result<Modalidade, String> {
    let texto = pedido
        .contrato
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo contrato"))?;
    let contrato = Contrato::ler(texto).map_err(|e| erro(e.codigo(), e.detalhe()))?;
    let nome = pedido
        .modalidade
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo modalidade"))?;
    contrato
        .modalidade(nome)
        .cloned()
        .map_err(|e| erro(e.codigo(), e.detalhe()))
}

/// Recusa o pedido se a partida já acabou: não se joga nem se busca lance
/// depois do fim (inclusive no empate pela regra, em que a biblioteca ainda
/// geraria lances).
fn exigir_partida_em_andamento(posicao: &Posicao, regras: &RegrasDoFim) -> Result<(), String> {
    match crate::fim_de_partida::fim_da_partida(posicao, regras) {
        Some(fim) => Err(erro(
            "partida_terminada",
            format!("a partida ja terminou: {}", fim.motivo.codigo()),
        )),
        None => Ok(()),
    }
}

/// Joga o lance na posição e devolve os fatos completos (com o `fim` da
/// posição nova) em JSON, os fatos em Rust e a posição depois.
fn jogar_com_fatos(posicao: &Posicao, lance: Move, regras: &RegrasDoFim) -> (Value, Fatos, Posicao) {
    let (fatos, _) = fatos_do_lance(&posicao.tabuleiro, lance);
    let mut depois = posicao.clone();
    depois.jogar(lance);
    let estado_depois = estado(&depois, regras);
    let mut json_dos_fatos = fatos.em_json();
    // `json_dos_fatos["fim"] = ...` acrescenta o campo ao objeto.
    json_dos_fatos["fim"] = estado_depois.fim.map_or(Value::Null, |f| f.em_json());
    (json_dos_fatos, fatos, depois)
}

/// Lê uma cor no vocabulário da fronteira.
fn cor_do_texto(texto: &str) -> Option<Color> {
    match texto {
        "branca" => Some(Color::White),
        "preta" => Some(Color::Black),
        _ => None,
    }
}

/// Lê a semente: um inteiro de 0 a 2³¹−1, ou `semente_invalida`.
fn semente_do_pedido(pedido: &Pedido) -> Result<u64, String> {
    let valor = pedido
        .semente
        .as_ref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo semente"))?;
    // `as_u64()` só devolve `Some` para inteiro não negativo que cabe em u64:
    // número com vírgula, negativo ou texto caem no `None`.
    match valor.as_u64() {
        Some(s) if s <= SEMENTE_MAXIMA => Ok(s),
        _ => Err(erro(
            "semente_invalida",
            format!("a semente tem de ser um inteiro de 0 a {SEMENTE_MAXIMA}"),
        )),
    }
}

// ── As operações ─────────────────────────────────────────────────────────────

/// `estado` (§2.1): o que a tela precisa para desenhar e aceitar o próximo toque.
fn operacao_estado(pedido: &Pedido) -> Result<String, String> {
    let modalidade = modalidade_do_pedido(pedido)?;
    let posicao = posicao_do_pedido(pedido)?;
    let regras = RegrasDoFim::da_modalidade(&modalidade);
    let mut resposta = estado(&posicao, &regras).em_json();
    resposta["ok"] = json!(true);
    Ok(resposta.to_string())
}

/// `aplicar` (§2.2): joga um lance e diz o que ele fez, por onde andaram as
/// peças marcadas e como ficou a posição.
fn operacao_aplicar(pedido: &Pedido) -> Result<String, String> {
    let modalidade = modalidade_do_pedido(pedido)?;
    let posicao = posicao_do_pedido(pedido)?;
    let regras = RegrasDoFim::da_modalidade(&modalidade);
    exigir_partida_em_andamento(&posicao, &regras)?;

    let texto = pedido
        .lance
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo lance"))?;
    let lance = lance_do_texto(&posicao.tabuleiro, texto)
        .ok_or_else(|| erro("lance_ilegal", format!("o lance {texto} nao e legal nesta posicao")))?;

    // As marcas: cada casa tem de ser uma casa, e ter uma peça. `null` é a
    // peça marcada que já foi comida antes, e continua `null`.
    let mut marcas: BTreeMap<String, Option<Square>> = BTreeMap::new();
    for (nome, casa) in pedido.marcas.iter().flatten() {
        let casa = match casa {
            None => None,
            Some(texto_da_casa) => {
                let c = casa_do_texto(texto_da_casa).ok_or_else(|| {
                    erro("pedido_invalido", format!("a marca {nome} tem uma casa invalida: {texto_da_casa}"))
                })?;
                if posicao.tabuleiro.piece_on(c).is_none() {
                    return Err(erro("pedido_invalido", format!("a marca {nome} aponta para a casa vazia {c}")));
                }
                Some(c)
            }
        };
        marcas.insert(nome.clone(), casa);
    }

    let (json_dos_fatos, fatos, depois) = jogar_com_fatos(&posicao, lance, &regras);
    let marcas_depois = seguir_marcas(&marcas, &fatos);
    Ok(json!({
        "ok": true,
        "fen_depois": depois.tabuleiro.to_string(),
        "fatos": json_dos_fatos,
        "marcas": marcas_em_json(&marcas_depois),
        "estado": estado(&depois, &regras).em_json(),
    })
    .to_string())
}

/// `recusa` (§2.3): por que um gesto não é lance legal.
fn operacao_recusa(pedido: &Pedido) -> Result<String, String> {
    let posicao = posicao_do_pedido(pedido)?;
    let ler_casa = |campo: &str, valor: &str| {
        casa_do_texto(valor).ok_or_else(|| erro("pedido_invalido", format!("{campo} nao e uma casa: {valor}")))
    };
    let de = pedido
        .de
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo de"))?;
    let de = ler_casa("de", de)?;
    // `transpose` troca `Option<Result<..>>` por `Result<Option<..>>`: o `?`
    // devolve o erro de uma casa torta, e a ausência continua `None`.
    let para = pedido.para.as_deref().map(|p| ler_casa("para", p)).transpose()?;
    match motivo_da_recusa(&posicao.tabuleiro, de, para) {
        Ok(regra) => Ok(json!({"ok": true, "regra": regra.codigo()}).to_string()),
        Err(SemMotivo::LanceLegal) => Err(erro("lance_legal", "o gesto e um lance legal")),
        Err(SemMotivo::PedidoInvalido(motivo)) => Err(erro("pedido_invalido", motivo)),
    }
}

/// `buscar` (§2.4): o lance da CPU no nível pedido.
///
/// O nível aplica profundidade, teto de nós, quiescência, tamanho da TT e rede
/// de tempo à busca, e o ruído (o mate em um, o erro entre os plausíveis) por
/// `niveis::escolher_lance`, com a semente do pedido (T038).
fn operacao_buscar(pedido: &Pedido) -> Result<String, String> {
    // A semente é conferida antes de tudo: ela é do pedido de busca, sempre.
    let semente = semente_do_pedido(pedido)?;
    let nivel = pedido
        .nivel
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo nivel"))?;
    responder_busca(pedido, nivel, Some(semente)).map(|r| r.to_string())
}

/// `jogada_ideal` (§2.5): a busca com o nível `ideal` do contrato, sem ruído e
/// sem semente. A resposta leva a peça da promoção, quando houver (R-28).
fn operacao_jogada_ideal(pedido: &Pedido) -> Result<String, String> {
    let mut resposta = responder_busca(pedido, NIVEL_DA_JOGADA_IDEAL, None)?;
    let promocao = resposta["fatos"]["promocao"].clone();
    resposta["promocao"] = promocao;
    Ok(resposta.to_string())
}

/// A busca comum ao `buscar` e à `jogada_ideal`.
///
/// Com `semente`, o lance passa pelo ruído do nível (`niveis.rs`): o mate em
/// um, os sorteios e o erro. Sem ela (a jogada ideal), é a busca pura: o poder
/// mostra o melhor lance que a busca acha, e não tem sorteio a fazer.
fn responder_busca(pedido: &Pedido, nome_do_nivel: &str, semente: Option<u64>) -> Result<Value, String> {
    let modalidade = modalidade_do_pedido(pedido)?;
    let nivel = modalidade
        .nivel(nome_do_nivel)
        .map_err(|e| erro(e.codigo(), e.detalhe()))?;
    let posicao = posicao_do_pedido(pedido)?;
    let regras = RegrasDoFim::da_modalidade(&modalidade);
    exigir_partida_em_andamento(&posicao, &regras)?;

    let limites = modalidade.limites_do_nivel(nivel);
    let tabuleiro = &posicao.tabuleiro;
    let cronometro = Cronometro::iniciar();
    // As duas escolhas só devolvem `None` sem lance legal, e isso o fim da
    // partida já recusou acima; o `ok_or_else` fica como guarda.
    let escolha = match semente {
        Some(semente) => escolher_lance(&posicao, &limites, &modalidade.ruido_do_nivel(nivel), semente),
        None => buscar(&posicao, &limites).map(Escolha::da_busca),
    }
    .ok_or_else(|| erro("partida_terminada", "a partida ja terminou: nao ha lance legal"))?;
    let tempo_ms = cronometro.ms();

    // A nota da escolha é do ponto de vista de quem joga; a resposta leva a das
    // brancas (§2.4). No lance único não houve busca: vale a nota parada.
    let avaliacao_brancas = if escolha.parada == Parada::LanceUnico {
        avaliar_para_as_brancas(tabuleiro)
    } else if tabuleiro.side_to_move() == Color::White {
        escolha.nota
    } else {
        -escolha.nota
    };
    let (json_dos_fatos, _, _) = jogar_com_fatos(&posicao, escolha.lance, &regras);

    Ok(json!({
        "ok": true,
        "lance": texto_do_lance(tabuleiro, escolha.lance),
        "acao": escolha.acao.codigo(),
        "nos": escolha.nos,
        "profundidade": escolha.profundidade,
        "parada": escolha.parada.codigo(),
        "avaliacao_brancas": avaliacao_brancas,
        "tempo_ms": tempo_ms,
        "fatos": json_dos_fatos,
    }))
}

/// `radar` (§2.6): as peças do lado pedido que o adversário pode comer agora.
fn operacao_radar(pedido: &Pedido) -> Result<String, String> {
    let posicao = posicao_do_pedido(pedido)?;
    let lado = pedido
        .lado
        .as_deref()
        .ok_or_else(|| erro("pedido_invalido", "falta o campo lado"))?;
    let lado = cor_do_texto(lado)
        .ok_or_else(|| erro("pedido_invalido", format!("lado tem de ser branca ou preta: {lado}")))?;
    let ameacadas = radar(&posicao.tabuleiro, lado);
    Ok(json!({"ok": true, "ameacadas": nomes_das_casas(ameacadas)}).to_string())
}

/// `perft` (§2.7): quantas sequências de lances há até a profundidade pedida.
/// Não consulta o contrato: a contagem depende só da posição.
fn operacao_perft(pedido: &Pedido) -> Result<String, String> {
    let posicao = posicao_do_pedido(pedido)?;
    let profundidade = match pedido.profundidade {
        Some(n) if (1..=PERFT_MAXIMO).contains(&n) => n,
        _ => {
            return Err(erro(
                "pedido_invalido",
                format!("profundidade do perft tem de ir de 1 a {PERFT_MAXIMO}"),
            ))
        }
    };
    let cronometro = Cronometro::iniciar();
    let nos = perft(&posicao.tabuleiro, profundidade);
    // `tempo_ms` é telemetria (a bancada mede nós/ms com ele), nunca decisão.
    Ok(json!({"ok": true, "nos": nos, "tempo_ms": cronometro.ms()}).to_string())
}

