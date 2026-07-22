# CLAUDE.md — API da Arena Sagaz (backend)

> **Leia primeiro o `CLAUDE.md` da raiz** (`../CLAUDE.md`): idioma, padrão de
> comentários, nomenclatura por jogo, política de segredos e regras de git valem
> para os três repositórios. Aqui ficam só as regras **da API**.
>
> **O laboratório de IA não mora mais aqui.** Desde 2026-07-21, geração de
> dados, notebooks de treino, oráculo, avaliador, contrato da CNN e datasets
> vivem em **`../ia/`** (ver `../ia/CLAUDE.md`). Se a sua tarefa é sobre CNN,
> dataset, minimax ou `.tflite`, é lá. O motivo e o que exatamente mudou estão
> em `docs/historico_decisoes.md`.

## Ambiente Python

Este repositório usa **`.venv`** (Python **3.14**). Para rodar Python ou pytest,
use **sempre**:

```
.venv\Scripts\python      (ou .venv\Scripts\pytest)
```

Não procure Python em outro lugar (system, AppData, conda). Os outros dois
ambientes do ecossistema — `../ia/.venv_tf` (3.12, TensorFlow) e
`../ia/.venv_gpu` (3.10, CUDA) — são do laboratório e **não** servem para a API:
as versões de Python são diferentes de propósito.

### Dependências: dois arquivos, papéis diferentes

- **`requirements_api.txt`** — o que a API precisa para **rodar**. É o que o
  `Dockerfile` instala. Dependência nova de runtime entra **aqui**.
- **`requirements.txt`** — o de cima (`-r requirements_api.txt`) **mais** as
  ferramentas de teste. É o que você instala na sua máquina.

## Dois ambientes no Railway: `des` e `prd`

Desde 2026-07-09 existe **produção**. São dois ambientes independentes, cada um
com seu Postgres e seu Firebase:

| | `des` | `prd` |
|---|---|---|
| API | `api-dev.arenasagaz.santiagodata.com` | `api.arenasagaz.santiagodata.com` |
| Firebase | `arena-sagaz-des` | `arena-sagaz-prd` |
| `AMBIENTE` | `desenvolvimento` | `producao` |

- ⚠️ **`AMBIENTE` precisa ser exatamente `producao`/`production`/`prod`.**
  `Configuracoes.eh_producao` só aceita esses valores; errar deixa o CORS
  liberando `localhost` em produção (SEG-02). O default é `desenvolvimento`.
- `ADMIN_BROADCAST_TOKEN` é **diferente** em cada ambiente.
- `FIREBASE_CREDENTIALS` é o **base64 em linha única** do JSON da conta de
  serviço (`base64 -w0 arena-sagaz-<amb>-firebase-adminsdk.json`) — evita
  corromper as quebras de linha da chave privada ao colar no console. Como
  obter o arquivo e o que cada campo significa:
  `docs/firebase-adminsdk-como-obter.md`.
- **Migrações não rodam no boot** (o `CMD` do Dockerfile só sobe o uvicorn). Rode
  `alembic upgrade head` da sua máquina, com a URL **pública** do Postgres
  (`*.proxy.rlwy.net`); a interna só funciona dentro da Railway.

> ⚠️ **"Healthcheck failure" no Railway quase nunca é problema de rede.**
> `api/nucleo/banco.py` chama `create_async_engine` **no import do módulo**: uma
> `DATABASE_URL` vazia ou inválida levanta `ArgumentError` antes de o uvicorn
> abrir a porta, e o Railway só consegue reportar que o healthcheck não
> respondeu. Causa comum: a referência `${{Servico.DATABASE_URL}}` não resolve
> porque o **nome do serviço** mudou.

## Diretriz obrigatória — Versionamento da API (apps em campo)

O app mobile, depois de publicado, fica **congelado** no aparelho do usuário —
várias versões do app convivem chamando o mesmo backend ao mesmo tempo. Toda
decisão de API DEVE respeitar isso:

- **Versionamento por caminho:** a API é exposta sob `/v1/...` (e `/v2/...` só
  quando necessário). Mudanças **aditivas** (novos endpoints, novos campos
  **opcionais**) NÃO sobem a versão. Apenas mudanças **quebradoras**
  (remover/renomear campo, mudar tipo/semântica, tornar obrigatório o que era
  opcional) criam uma nova versão.
- **Compatibilidade retroativa (inegociável):** o backend DEVE continuar
  atendendo todas as versões de app ainda suportadas. Migrações seguem
  **expand/contract**: adiciona o novo → mantém o antigo funcionando → migra os
  clientes → só **depois** remove o antigo.
- **Aposentar uma versão** de API só é permitido depois que o *force-update*
  (Remote Config `versao_minima_*`) já excluiu todos os apps que dependiam dela.
  **Nunca** quebre um cliente ainda em campo.
- **Cabeçalhos de cliente:** toda chamada do app traz `X-App-Version`,
  `X-Platform` (android/ios) e o idioma. Use para log, diagnóstico,
  descontinuação gradual e (futuro) antifraude.
- **Estrutura FastAPI:** roteadores agrupados por versão (`APIRouter(prefix="/v1")`);
  schemas Pydantic versionados quando divergirem. **Não** crie `/v2` antes de
  existir uma mudança quebradora real.
- **Contrato e testes:** cada versão expõe seu próprio OpenAPI; testes de
  contrato garantem que endpoints de versões antigas continuam funcionando.

Ver a diretriz espelhada (lado app) no `CLAUDE.md` do frontend.

## Diretriz obrigatória — Documentação viva

Decisão arquitetural, mudança de rota técnica ou alteração de formato de dados
**entra no `.md` na mesma resposta em que a mudança é feita**. O usuário não deve
precisar lembrar de pedir.

- **Arquitetura/decisões/abandono de abordagens:** `docs/historico_decisoes.md`,
  com data, contexto, decisão, alternativas consideradas e motivo.
- **Especificação formal/contratos:** os artefatos em `specs/`.

Não criar docs novos sem necessidade — prefira editar os existentes. Mudança sem
impacto durável (ex.: ajuste de uma linha de teste) não precisa ser documentada.

## Diretriz obrigatória — Commit e push após editar `specs/`

Toda alteração em `specs/` (planos, spec, PRD, tasks, contratos) leva **commit e
push imediatos**, na mesma resposta.

**Motivo:** os comandos do speckit (`/speckit-plan`, `/speckit-tasks`, …)
sobrescrevem arquivos de `specs/` com o template em branco como parte do fluxo de
setup. Se o documento ainda não tiver sido commitado, as edições manuais somem
sem recuperação.

**Exceção única:** se um comando do speckit restaurar um documento para o estado
de template padrão, **NÃO** faça commit nem push — restaure com
`git checkout -- <arquivo>` e avise o usuário.
