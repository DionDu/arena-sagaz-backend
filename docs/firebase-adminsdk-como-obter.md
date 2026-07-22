# Chave do Firebase Admin SDK — como obter e onde ela vive

> **Por que este documento é um `.md` e não um `.json` de exemplo.**
> A primeira versão era um `arena-sagaz-firebase-adminsdk.exemplo.json` com a
> estrutura preenchida por valores falsos. O **push protection do GitHub
> bloqueou o push**: o arquivo tinha a forma exata de uma credencial de conta de
> serviço do Google Cloud (`"type": "service_account"` + os marcadores
> `BEGIN PRIVATE KEY`), e o scanner casa pela **forma**, não pelo conteúdo.
> Estava certo em bloquear — um exemplo que imita uma chave é indistinguível de
> uma chave até alguém ler os valores. Aqui a mesma informação vai em prosa.

## O que é

O arquivo `arena-sagaz-<ambiente>-firebase-adminsdk.json` é a credencial que
permite ao backend **verificar o ID token** que o app envia (`FR-010`). Sem ele,
nenhum login funciona: toda rota autenticada devolve 401.

São **dois** arquivos, um por ambiente, de projetos Firebase diferentes:

| Ambiente | Projeto Firebase | Nome do arquivo |
|---|---|---|
| `des` | `arena-sagaz-des` | `arena-sagaz-des-firebase-adminsdk.json` |
| `prd` | `arena-sagaz-prd` | `arena-sagaz-prd-firebase-adminsdk.json` |

⚠️ Nunca aponte o `prd` para as credenciais do `des`. Os dois têm bancos de
usuários separados; cruzá-los faz o token de um projeto ser rejeitado pelo outro
com uma mensagem que não ajuda em nada.

## Como obter o arquivo real

1. **Firebase Console** → selecione o projeto (`arena-sagaz-des` ou `arena-sagaz-prd`).
2. Engrenagem ⚙ → **Configurações do projeto**.
3. Aba **Contas de serviço**.
4. Botão **Gerar nova chave privada** → confirmar. O download começa sozinho.
5. Renomeie o arquivo baixado (vem com um nome longo e aleatório) para o padrão
   da tabela acima e coloque na **raiz deste repositório**.

⚠️ **Cada clique em "Gerar nova chave privada" cria uma chave nova.** A anterior
continua válida até ser revogada — não saia clicando, ou você acumula chaves
ativas sem saber quais estão em uso onde.

## Estrutura do arquivo (para conferir se veio certo)

É um JSON com estes campos, todos preenchidos pelo Google:

- `type` — sempre a string que identifica conta de serviço
- `project_id` — tem de bater com o ambiente (`arena-sagaz-des` / `arena-sagaz-prd`)
- `private_key_id` e `private_key` — a chave em si, em formato PEM, com quebras
  de linha escapadas como `\n`
- `client_email` — algo como `firebase-adminsdk-xxxxx@<project_id>.iam.gserviceaccount.com`
- `client_id`, `auth_uri`, `token_uri`, `auth_provider_x509_cert_url`,
  `client_x509_cert_url`, `universe_domain` — metadados do OAuth

Se `project_id` não corresponder ao ambiente, você baixou do projeto errado.

## Como ele chega ao Railway

**Não** como arquivo. A variável de ambiente `FIREBASE_CREDENTIALS` recebe o
JSON inteiro codificado em **base64 numa linha só**:

```bash
base64 -w0 arena-sagaz-prd-firebase-adminsdk.json
```

O base64 existe por um motivo prático: a chave privada tem quebras de linha, e
colar texto multilinha no console web da Railway corrompe o valor de formas
difíceis de diagnosticar (o erro aparece só na hora de validar um token).

## Onde os arquivos ficam guardados

- **Nesta máquina:** raiz deste repositório. Estão no `.gitignore` — o padrão
  `*firebase-adminsdk*.json` cobre os dois.
- **Backup:** Google Drive. O inventário completo dos segredos do projeto,
  com o que é cada um e como se regenera, está em `../segredos/LEIA-ME.md`.
- **Nunca** no Git, nem em repositório privado: o histórico é para sempre, e
  "privado" é uma configuração que um clique desfaz.
