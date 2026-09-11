# Runbook — o painel de curadoria do Desafio do Dia

> ⚠️ **Só o painel.** Migração é `runbook-migracoes-desafio.md`; operação do job
> é `specs/006-conta-nuvem/checklist-producao.md`. Um runbook que cresce para
> cobrir tudo deixa de ser consultável — e já temos um assim.

**O que é:** uma página HTML servida pela própria API, em `/painel/desafios`.
⛔ **Não é o `painel/`** da raiz do ecossistema (aquele é a bancada de telemetria
da CNN), e não tem app nem build de Flutter Web.

---

## 1. Entrar

```
https://api-dev.arenasagaz.santiagodata.com/painel/desafios?token=<PAINEL_CURADORIA_TOKEN>
```

O que acontece no primeiro acesso: o servidor confere o token, grava um cookie
`HttpOnly` e **redireciona para a URL sem o token** — a barra de endereços fica
limpa já no primeiro quadro. Dali em diante o cookie autentica, e ele **vale 12
horas**. Passou disso, cole o link com `?token=` de novo.

⚠️ **O token é a Variable `PAINEL_CURADORIA_TOKEN` do serviço da API** (não do
job), no Railway. ⛔ Não é o `ADMIN_BROADCAST_TOKEN`: quem pode disparar
notificação para toda a base não deveria, pelo mesmo segredo, poder aprovar
conteúdo que vai ao ar.

**Dois erros que parecem um só:**

| o que aparece | o que é | o que fazer |
|---|---|---|
| `painel_desabilitado` | a Variable está vazia ou não existe | configurar no Railway e **redeploy da API** |
| `painel_token_invalido` | a Variable existe, o token colado é outro | conferir o valor |

A distinção é deliberada: *"configure a variável"* não se parece nem um pouco com
*"alguém tentou entrar com o token errado"*.

---

## 2. O que tem na página

Três seções, nesta ordem:

1. **Vigilância — a fila.** Quantos dias à frente estão cobertos. É o número que
   diz se o job está acompanhando o calendário.
2. **Vigilância — divergências de julgamento.** Quando o servidor e o aparelho
   julgariam diferente. ⚠️ **Ver aqui não corrige nada** — é aviso, e exige
   investigação no código.
3. **A fila de curadoria.** Um cartão por desafio.

### O cartão

- **A posição, desenhada em SVG** (não é a FEN crua — curadoria feita sobre texto
  é curadoria que aprova tudo).
- **Tipo, jogo e modalidade**, etiquetas de estado (`candidato` / `aprovado` /
  `descartado`, `reprise`) e a data agendada, ou "sem data".
- **Objetivo**, **adversário** (mascote + semente) e **em quantos lances** a
  solução de referência cumpre.
- **A régua**: uma linha por mascote, com `resolveu N/M` e a barra.
- **A solucao DESENHADA, lance a lance** — um quadro por lance, com o do
  objetivo em **borda dourada**. Nas damas as casas vao de 1 a 32 e o caminho do
  lance fica aceso; no Pontinhos cada traco livre traz o rotulo (`V_3_4`).
  ⚠️ **Desafio gerado antes de 11/09/2026 nao tem as posicoes gravadas** e mostra
  um recado em vez de meia sequencia - rode o job de novo para ve-la.
- **O gabarito em JSON**, dobrado, para quando a duvida for sobre o dado.

---

## 3. Como decidir

⚠️ **"É resolvível?" já está respondido antes de o cartão existir**: o job só
grava candidato para o qual encontrou solução. O que a régua responde é outra
coisa — **para quem** é resolvível:

| o que você vê na régua | o que significa | ação |
|---|---|---|
| Cacau resolve quase sempre | banal | descartar |
| gradiente (Cacau apanha, Tex passa) | é o alvo | aprovar |
| nem o Magno resolve | duro demais | descartar |
| **"Sem medição da régua"** | ⛔ o job não mediu | ⛔ não aprovar às cegas |

E olhe **quantos lances** a solução tem. ⛔ **Solução de 1 lance é descarte**:
o desafio se resolve no primeiro toque, e nada no resto do cartão denuncia isso.

---

## 4. As quatro ações

| ação | quando | efeito |
|---|---|---|
| **Aprovar** | o desafio presta | sai de `candidato`; ⛔ ainda **não** está no ar |
| **Agendar** | depois de aprovar | prende o desafio a um dia — é isto que o põe no ar |
| **Desagendar** | tirar do dia sem descartar | solta a data, o desafio continua aprovado |
| **Descartar** (com motivo) | não presta | ⛔ **não apaga** — o motivo fica registrado |

⚠️ **Aprovar e agendar são duas ações porque são duas decisões**: aprovar é sobre
o desafio; agendar é o vínculo com o dia. ⛔ **Só o aprovado entra no calendário**,
e essa regra vive no `servico.py` — não num botão escondido: um `<form>` ausente
na tela não impede um `curl`.

⛔ **Só o aprovado é servido ao aplicativo.** Job que gera e ninguém que aprova =
Home vazia, **sem nada dar erro**.

---

## 5. Rodar o painel localmente (opcional)

Contra o mesmo banco `des`, sem depender do deploy:

```powershell
cd D:\Desenvolvimento\arena-sagaz\arena-sagaz-backend
.venv\Scripts\python -m uvicorn api.main:app --reload --port 8000
```

Depois: `http://localhost:8000/painel/desafios?token=<o mesmo token do .env>`.

⚠️ Em `http://localhost` o cookie sai **sem** `Secure` de propósito — com ele, o
navegador descartaria o cookie sem mensagem nenhuma e o painel entraria num laço
de redirecionamento inexplicável.
