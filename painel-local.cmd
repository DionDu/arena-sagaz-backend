@echo off
rem ============================================================================
rem  O PAINEL DE CURADORIA, RODANDO NESTE COMPUTADOR
rem ============================================================================
rem
rem  Um duplo-clique abre o painel no navegador, ja autenticado, com o botao de
rem  gerar desafios ligado.
rem
rem  ⚠️ DESDE 16/09/2026 ESTE NAO E MAIS O CAMINHO PRINCIPAL.
rem  -------------------------------------------------------
rem  A porta de entrada de todos os paineis passou a ser
rem
rem        ..\painel\painel.cmd
rem
rem  que abre o Painel de Gestao em 127.0.0.1:8080 e sobe a curadoria daqui
rem  sozinho, no primeiro clique do cartao - junto com o replay de partidas, o
rem  exportador de pecas de loja e os relatorios gerenciais.
rem
rem  Este arquivo CONTINUA funcionando, e continua na mesma porta (8099): serve
rem  para abrir so a curadoria, sem subir o resto.
rem
rem  POR QUE ELE EXISTE (16/09/2026)
rem  -------------------------------
rem  O dono escreveu: "O comando `.venv\Scripts\python scripts\rodar_job_local.py
rem  --dias 14` eu nao vou conseguir memorizar. Ele precisava estar dentro do
rem  painel de curadoria."
rem
rem  O botao entrou no painel - mas abrir o painel local tambem era um comando
rem  para decorar. Este arquivo e o passo que faltava: um clique.
rem
rem  ATENCAO - o que este arquivo LIGA, e que o Railway nao liga:
rem
rem    PAINEL_PODE_GERAR=1   o botao "Gerar desafios" aparece e a rota aceita.
rem                          Em producao ele fica DESLIGADO de proposito: o job
rem                          dispara minutos de CPU, e foi feito para ser um
rem                          container proprio, que sobe, trabalha e morre.
rem
rem  Uso:
rem      painel-local.cmd            abre no banco des (o padrao)
rem      painel-local.cmd prd        abre no banco de PRODUCAO - cuidado
rem
rem ============================================================================
setlocal

set "AMBIENTE=%~1"
if "%AMBIENTE%"=="" set "AMBIENTE=des"

rem -- O catalogo dos dois bancos fica FORA do Git, na raiz do ecossistema ------
set "CATALOGO=%~dp0..\ferramentas\debug-bancos\ambientes.env"
if not exist "%CATALOGO%" (
  echo [ERRO] catalogo nao encontrado: %CATALOGO%
  exit /b 1
)

rem -- Le a URL do ambiente pedido, sem nunca imprimi-la ------------------------
if /i "%AMBIENTE%"=="prd" (
  set "VARIAVEL=DATABASE_URL_PRD"
  echo.
  echo   ******************************************************************
  echo   *  PRODUCAO - os desafios gerados aqui vao para o banco real.     *
  echo   *  Tudo nasce CANDIDATO e passa pela sua curadoria, mas confira.  *
  echo   ******************************************************************
  echo.
) else (
  set "VARIAVEL=DATABASE_URL_DES"
)

for /f "usebackq tokens=1,* delims==" %%A in ("%CATALOGO%") do (
  if "%%A"=="%VARIAVEL%" set "DATABASE_URL=%%B"
)
if "%DATABASE_URL%"=="" (
  echo [ERRO] %VARIAVEL% nao esta no catalogo.
  exit /b 1
)

rem -- O segredo do painel. Local, um valor fixo basta: a pagina so escuta em ---
rem -- localhost, e o token existe para o painel do Railway, que e publico. -----
set "PAINEL_CURADORIA_TOKEN=painel-local"

rem -- E o que so o painel LOCAL pode fazer -------------------------------------
set "PAINEL_PODE_GERAR=1"

echo [painel-local] banco: %AMBIENTE%
echo [painel-local] abrindo http://127.0.0.1:8099/painel/desafios
echo [painel-local] feche esta janela para desligar o painel.
echo.

rem O navegador abre com o token na URL; o servidor grava o cookie e limpa a
rem barra de enderecos no primeiro redirecionamento (ver seguranca.py).
start "" "http://127.0.0.1:8099/painel/desafios?token=%PAINEL_CURADORIA_TOKEN%"

rem --host 127.0.0.1: so esta maquina alcanca. Nada de 0.0.0.0 num processo que
rem serve uma pagina administrativa sem HTTPS.
"%~dp0.venv\Scripts\python" -m uvicorn api.main:app --host 127.0.0.1 --port 8099

endlocal
