<!-- SPECKIT START -->
Para contexto sobre tecnologias, estrutura do projeto, comandos e decisões de
arquitetura, leia o plano de implementação atual:
`specs/004-melhoria-geracao-dados-cnn/plan.md`

Artefatos relacionados:
- Especificação: `specs/004-melhoria-geracao-dados-cnn/spec.md`
- PRD técnico: `specs/004-melhoria-geracao-dados-cnn/PRD.md`
- Pesquisa: `specs/004-melhoria-geracao-dados-cnn/research.md`
- Modelo de dados: `specs/004-melhoria-geracao-dados-cnn/data-model.md`
- Contrato dos canais estruturais: `specs/004-melhoria-geracao-dados-cnn/contracts/canais_estruturais.md`
- Esquema dos NPZ por fase: `specs/004-melhoria-geracao-dados-cnn/contracts/npz_schema.md`
- Quickstart de execução: `specs/004-melhoria-geracao-dados-cnn/quickstart.md`

Plano anterior (referência histórica): `specs/001-fase-zero-backend/plan.md`
<!-- SPECKIT END -->

## Diretriz obrigatória — Documentação viva

Sempre que tomarmos uma decisão arquitetural, mudarmos de rota técnica, alterarmos
o formato de dados, parâmetros recomendados de execução ou qualquer escolha que
afete *como* o projeto é construído ou rodado, **atualize os documentos `.md`
relevantes na mesma resposta em que a mudança é feita**. O usuário não deve
precisar lembrar de pedir.

- **Operação/uso (comandos, parâmetros, formato de arquivo, fluxo do dia-a-dia):**
  atualizar `docs/jogo_pontinhos/guia_geracao_dados.md` e os `.md` correspondentes em `docs/jogo_pontinhos/`.
- **Arquitetura/decisões/abandono de abordagens:** registrar em
  `docs/historico_decisoes.md` (criar se não existir). Cada entrada deve ter
  data, contexto, decisão, alternativas consideradas e motivo.
- **Especificação formal/contratos:** atualizar os artefatos em
  `specs/001-fase-zero-backend/`.

Não criar docs novos sem necessidade — prefira editar os existentes. Se uma
mudança não tem impacto durável (ex.: ajuste de uma linha de teste), não precisa
documentar.

## Diretriz obrigatória — Contrato de codificação da CNN (LEIA ANTES DE MEXER)

**ANTES** de fazer qualquer mudança em um dos itens abaixo, você DEVE ler o
arquivo `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.json` — ele é a fonte
única da verdade sobre como a matriz do tabuleiro do jogo dos pontinhos é
codificada em cada contexto e como deve ser transformada antes de ser enviada à
rede neural.

Itens que obrigam a leitura do contrato antes de qualquer alteração:

- Encoding da matriz do tabuleiro (valores `0`, `1`, `-1`, `8`, `9`).
- Pipeline de **geração do dataset** (notebooks que produzem NPZ no Databricks).
- Pipeline de **treinamento** (notebooks que consomem NPZ no Colab).
- Lógica de **inferência**: simulador, avaliador de partidas, app Flutter.
- Qualquer **normalização de tensor** (substituição de valores antes de
  `interp.set_tensor()` ou `model.fit()`).

Depois de qualquer mudança nessa área, rode o teste
`tests/unitarios/jogo_pontinhos/test_contrato_codificacao_pontinhos.py`. Ele é obrigatório
no CI e **falha o merge** se:
- A cópia do JSON no backend divergir da cópia no frontend
  (`arena-sagaz-frontend/assets/jogos/pontinhos/contrato_codificacao_pontinhos.json`).
- O helper `gerador_dados/jogo_pontinhos/contrato_codificacao_pontinhos.py` deixar de aplicar
  exatamente as regras declaradas no JSON.
- O tensor pós-normalização sair do domínio `{0, 1}`.

Se você editar o JSON, copie o conteúdo IDÊNTICO para o frontend na mesma
resposta. Não existe "atualizo depois".

## Diretriz obrigatória — Nomenclatura por jogo (hub de jogos)

Arena Sagaz é um **hub de jogos**; o Jogo dos Pontinhos é o primeiro, mas não
será o único. Para evitar colisão de nomes e pastas genéricas intransitáveis
no futuro:

- Todo arquivo com conteúdo específico de **um jogo** (lógica, dados, modelo,
  dataset, contrato, mapeamento) **DEVE** carregar o nome do jogo no nome do
  arquivo, OU ficar dentro de uma pasta do jogo (ex.: `.../jogos/pontinhos/`).
  - Exemplos válidos: `contrato_codificacao_pontinhos.json`,
    `dataset_pontinhos_pequeno.npz`, `assets/jogos/pontinhos/ia_mappings/mapeamento_pequeno.json`.
  - Proibido para conteúdo game-specific: `tabuleiro.py` **em pasta raiz
    compartilhada**, `contrato.json` em `assets/`, `mapeamento_pequeno.json`
    em `assets/ia_mappings/` (pasta genérica).
- Código genuinamente compartilhado entre jogos pode usar nome genérico e deve
  ficar em pasta neutra (ex.: `shared/`, `lib/core/`).
- Arquivos legados já existentes (sem sufixo) são **débito conhecido** — serão
  renomeados em sessão dedicada; **não renomear caso a caso** durante outras
  tarefas.

## Diretriz obrigatória — Notebooks derivados: atualizar Markdown, comentários e prints

Sempre que você criar um notebook **novo a partir de um existente**, ou **alterar**
um notebook, ajuste as células de **Markdown**, os **comentários de código** e as
**mensagens de `print()`** para que reflitam as mudanças feitas — **não deixe texto
herdado do notebook-base**. O usuário não deve precisar corrigir isso à mão.

**Ajuste SOMENTE o que mudou.** Se um trecho de Markdown, comentário ou `print()`
continua **atual e correto**, **mantenha como está** — não reescreva por reescrever.

Itens a revisar (não exaustivo):

- **Títulos e descrições**: nome do modelo/arquitetura (ex.: "BoxNet v4" quando
  virou outra coisa), propósito do notebook, seção de introdução.
- **Valores hardcoded em texto**: contagens e caminhos (ex.: "152 NPZs",
  "apenas os 754k originais", "esperado: X arquivos = Y"), que ficam errados
  quando os dados mudam.
- **Saídas de `print()`**: rótulos e valores impressos (ex.: `print(f'Encontrados
  {n} arquivos (esperado: ...)')`, resumos de configuração) devem bater com o que
  o notebook realmente faz **agora**.
- **Comentários de configuração**: `EXPERIMENTO`, `PASTA_NPZ`, `batch_size`,
  `lr`, instruções `# EDITE:` e quaisquer notas que descrevam o que a célula faz.
- **Menções a parâmetros/etapas que mudaram**: profundidade, base de dados,
  pesos (`sample_weight`), augmentação, etc.

Motivo: texto defasado em notebook **engana a banca do TCC** e induz erro de
operação. Tratar Markdown/comentários como parte da mudança, não como enfeite.

## Ambiente Python

O projeto usa um virtualenv em `.venv\`. Para rodar Python ou pytest, use **sempre**:

```
.venv\Scripts\python   (ou .venv\Scripts\pytest)
```

Não procure Python em outro lugar (system, AppData, conda). O `.venv` é a única
fonte correta de dependências deste projeto.

## Diretriz obrigatória — Commit e Push após editar documentos em `specs/`

Toda vez que você (Claude) fizer qualquer alteração em arquivos dentro da pasta
`specs/` (planos, spec, PRD, tasks, contratos, etc.), **realize commit e push
imediatamente** na mesma resposta em que a edição for feita, detalhando as
mudanças no corpo do commit.

**Exceção única**: se um comando do speckit restaurar um documento para o estado
de template padrão (ex.: `/speckit-plan` sobrescreve `plan.md` com o template
em branco), **NÃO faça commit nem push** — restaure o arquivo com
`git checkout -- <arquivo>` e informe o usuário.

**Motivação**: comandos do speckit (`/speckit-plan`, `/speckit-tasks`, etc.)
sobrescrevem arquivos de `specs/` com templates em branco como parte do seu
fluxo de setup. Se o documento ainda não tiver sido commitado, as edições
manuais feitas anteriormente são perdidas sem possibilidade de recuperação.

## Diretriz obrigatória — Versionamento da API (apps em campo)

O app mobile, depois de publicado, fica **congelado** no aparelho do usuário —
várias versões do app convivem chamando o mesmo backend ao mesmo tempo. Toda
decisão de API DEVE respeitar isso:

- **Versionamento por caminho:** a API é exposta sob `/v1/...` (e `/v2/...` só
  quando necessário). Mudanças **aditivas** (novos endpoints, novos campos
  **opcionais**) NÃO sobem a versão. Apenas mudanças **quebradoras**
  (remover/renomear campo, mudar tipo/semântica, tornar obrigatório o que era
  opcional) criam uma nova versão.
- **Compatibilidade retroativa (inegociável):** o backend DEVE continuar atendendo
  todas as versões de app ainda suportadas. Migrações seguem **expand/contract**:
  adiciona o novo → mantém o antigo funcionando → migra os clientes → só **depois**
  remove o antigo.
- **Aposentar uma versão** de API só é permitido depois que o *force-update*
  (Remote Config `versao_minima_*`, ver `specs/005-…` FR-028) já excluiu todos os
  apps que dependiam dela. **Nunca** quebre um cliente ainda em campo.
- **Cabeçalhos de cliente:** toda chamada do app traz `X-App-Version`, `X-Platform`
  (android/ios) e o idioma. Use para log, diagnóstico, descontinuação gradual e
  (futuro) antifraude.
- **Estrutura FastAPI:** roteadores agrupados por versão
  (`api/v1/...`, `APIRouter(prefix="/v1")`); schemas Pydantic versionados quando
  divergirem. **Não** crie `/v2` antes de existir uma mudança quebradora real.
- **Contrato e testes:** cada versão expõe seu próprio OpenAPI; testes de contrato
  garantem que endpoints de versões antigas continuam funcionando.

Ver a diretriz espelhada (lado app) no `CLAUDE.md` do frontend.
