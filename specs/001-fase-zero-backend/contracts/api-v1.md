# Contratos da API v1 — Arena Sagaz Backend

**Branch**: `001-fase-zero-backend` | **Data**: 2026-04-19
**Base URL**: `https://<railway-dominio>/v1`
**Formato**: JSON (UTF-8) em todas as requisições e respostas
**Autenticação**: Bearer JWT no header `Authorization` (exceto rotas públicas)

---

## Convenções Gerais

### Respostas de Erro Padrão

```json
{
  "detalhe": "Mensagem descritiva do erro em pt-BR",
  "codigo": "CODIGO_ERRO_INTERNO"
}
```

Códigos HTTP utilizados:
- `200 OK` — sucesso geral
- `201 Created` — recurso criado
- `400 Bad Request` — dados inválidos na requisição
- `401 Unauthorized` — token ausente, inválido ou expirado
- `409 Conflict` — recurso já existente (e-mail/apelido duplicado)
- `422 Unprocessable Entity` — falha de validação Pydantic
- `503 Service Unavailable` — banco de dados indisponível (retornado pelo health check)

---

## Rotas Públicas

### `GET /v1/health`

Verifica a disponibilidade da API e do banco de dados. Usado pelo Railway para
health checks automáticos.

**Requisição**: sem corpo, sem autenticação.

**Resposta 200**:
```json
{
  "status": "ok",
  "banco_de_dados": "ok",
  "versao": "1.0.0"
}
```

**Resposta 503** (banco indisponível):
```json
{
  "status": "degradado",
  "banco_de_dados": "indisponivel",
  "versao": "1.0.0"
}
```

---

### `POST /v1/usuarios`

Cria uma nova conta de jogador.

**Requisição**:
```json
{
  "apelido": "string (3–50 caracteres, apenas letras, números e _)",
  "email": "string (formato e-mail válido, máx. 255 chars)",
  "senha": "string (mín. 8 caracteres)"
}
```

**Resposta 201**:
```json
{
  "id": "uuid",
  "apelido": "string",
  "email": "string",
  "nivel": 1,
  "xp_total": 0,
  "criado_em": "2026-04-19T12:00:00Z",
  "acesso_token": "string (JWT)",
  "refresh_token": "string (opaco)",
  "expira_em": "2026-04-19T13:00:00Z"
}
```

**Resposta 409** (e-mail ou apelido duplicado):
```json
{
  "detalhe": "E-mail já cadastrado.",
  "codigo": "EMAIL_DUPLICADO"
}
```

---

### `POST /v1/auth/login`

Autentica um usuário existente e retorna tokens de acesso.

**Requisição**:
```json
{
  "email": "string",
  "senha": "string"
}
```

**Resposta 200**:
```json
{
  "acesso_token": "string (JWT)",
  "refresh_token": "string (opaco)",
  "tipo_token": "bearer",
  "expira_em": "2026-04-19T13:00:00Z"
}
```

**Resposta 401** (credenciais inválidas):
```json
{
  "detalhe": "E-mail ou senha incorretos.",
  "codigo": "CREDENCIAIS_INVALIDAS"
}
```

---

### `POST /v1/auth/refresh`

Renova o JWT de acesso usando um refresh token válido.

**Requisição**:
```json
{
  "refresh_token": "string"
}
```

**Resposta 200**:
```json
{
  "acesso_token": "string (JWT)",
  "tipo_token": "bearer",
  "expira_em": "2026-04-19T14:00:00Z"
}
```

**Resposta 401** (refresh token inválido ou expirado):
```json
{
  "detalhe": "Token de renovação inválido ou expirado.",
  "codigo": "REFRESH_TOKEN_INVALIDO"
}
```

---

### `GET /v1/ranking`

Retorna o ranking global paginado.

**Parâmetros de query**:
- `pagina` (int, padrão: `1`) — número da página
- `tamanho` (int, padrão: `20`, máx: `100`) — registros por página

**Resposta 200**:
```json
{
  "total": 1500,
  "pagina": 1,
  "tamanho": 20,
  "jogadores": [
    {
      "posicao": 1,
      "apelido": "string",
      "nivel": 42,
      "pontuacao_total": 9800,
      "vitorias": 312,
      "partidas_jogadas": 400
    }
  ]
}
```

---

## Rotas Protegidas (requerem `Authorization: Bearer <JWT>`)

### `GET /v1/usuarios/eu`

Retorna o perfil completo do jogador autenticado.

**Resposta 200**:
```json
{
  "id": "uuid",
  "apelido": "string",
  "email": "string",
  "nivel": 5,
  "xp_total": 1250,
  "email_verificado": true,
  "criado_em": "2026-01-15T09:00:00Z",
  "ranking": {
    "posicao": 47,
    "pontuacao_total": 1250,
    "partidas_jogadas": 83,
    "vitorias": 51
  },
  "trofeus": [
    {
      "codigo": "primeira_vitoria",
      "nome": "Primeira Vitória",
      "conquistado_em": "2026-01-15T09:30:00Z"
    }
  ]
}
```

---

### `POST /v1/partidas`

Sincroniza uma partida concluída e atualiza XP e ranking do jogador.

**Requisição**:
```json
{
  "modo_jogo": "vs_cpu",
  "tamanho_tabuleiro": "pequeno",
  "dificuldade": "normal",
  "caixas_jogador": 7,
  "caixas_adversario": 5,
  "resultado": "vitoria"
}
```

**Validações**:
- `modo_jogo`: obrigatório, um de `['vs_cpu', 'vs_humano_local']`
- `tamanho_tabuleiro`: obrigatório, um de `['pequeno', 'medio', 'grande']`
- `dificuldade`: obrigatório se `modo_jogo == 'vs_cpu'`; DEVE ser `null` se `vs_humano_local`
- `caixas_jogador` + `caixas_adversario` DEVE corresponder ao total de caixas
  do tabuleiro (12 / 20 / 35 para pequeno / médio / grande)
- `resultado`: obrigatório, um de `['vitoria', 'derrota', 'empate']`

**Resposta 201**:
```json
{
  "id": "uuid",
  "xp_obtido": 18,
  "pontuacao_obtida": 18,
  "nivel_anterior": 4,
  "nivel_atual": 4,
  "xp_total": 1268,
  "posicao_ranking": 45,
  "trofeus_conquistados": []
}
```

**Resposta 400** (soma de caixas inválida):
```json
{
  "detalhe": "A soma de caixas (7 + 5 = 12) não corresponde ao tabuleiro 'medio' (esperado: 20).",
  "codigo": "CAIXAS_INVALIDAS"
}
```

---

### `POST /v1/auth/logout`

Revoga o refresh token atual do jogador.

**Requisição**:
```json
{
  "refresh_token": "string"
}
```

**Resposta 200**:
```json
{
  "mensagem": "Sessão encerrada com sucesso."
}
```

---

## Esquemas Pydantic de Referência

```python
# Resumo dos esquemas principais — detalhes em api/*/esquemas.py

class CriarUsuarioEntrada(BaseModel):
    apelido: str  # 3-50 chars, regex: ^[a-zA-Z0-9_]+$
    email: EmailStr
    senha: str    # mín. 8 chars

class LoginEntrada(BaseModel):
    email: EmailStr
    senha: str

class SincronizarPartidaEntrada(BaseModel):
    modo_jogo: Literal['vs_cpu', 'vs_humano_local']
    tamanho_tabuleiro: Literal['pequeno', 'medio', 'grande']
    dificuldade: Optional[Literal['facil', 'normal', 'sagaz']] = None
    caixas_jogador: int  # >= 0
    caixas_adversario: int  # >= 0
    resultado: Literal['vitoria', 'derrota', 'empate']
```
