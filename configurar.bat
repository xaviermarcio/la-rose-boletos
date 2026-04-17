@echo off
chcp 65001 >nul
cls
echo.
echo  ╔════════════════════════════════════════╗
echo  ║   LA ROSE — Configuração Inicial       ║
echo  ║   Execute este arquivo na PRIMEIRA vez ║
echo  ║   ou após formatar o computador        ║
echo  ╚════════════════════════════════════════╝
echo.
echo  Este script vai:
echo  1. Verificar o Python
echo  2. Instalar todas as dependências
echo  3. Criar o arquivo .env automaticamente
echo  4. Verificar o Tesseract OCR
echo  5. Verificar o Poppler (para PDF)
echo  6. Verificar o Firebase
echo.
pause

REM ── PASSO 1: Python ──────────────────────────────────────────
echo.
echo  [1/6] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERRO: Python nao encontrado!
    echo.
    echo  Instale em: https://python.org/downloads
    echo  IMPORTANTE: marque "Add Python to PATH" durante a instalacao!
    echo.
    echo  Apos instalar o Python, execute este arquivo novamente.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo  OK: %%i encontrado.

REM ── PASSO 2: Dependências Python ─────────────────────────────
echo.
echo  [2/6] Instalando dependencias Python...
echo  Isso pode demorar alguns minutos na primeira vez.
echo.
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  ERRO ao instalar dependencias!
    echo  Verifique sua conexao com a internet e tente novamente.
    pause
    exit /b 1
)
echo.
echo  OK: Todas as dependencias instaladas.

REM ── PASSO 3: Arquivo .env ────────────────────────────────────
echo.
echo  [3/6] Configurando arquivo .env...
if not exist ".env" (
    copy .env.exemplo .env >nul
    echo  OK: Arquivo .env criado a partir do exemplo.
) else (
    echo  OK: Arquivo .env ja existe.
)

REM ── PASSO 4: Tesseract OCR ───────────────────────────────────
echo.
echo  [4/6] Verificando Tesseract OCR...
tesseract --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('tesseract --version 2^>^&1 ^| findstr /i "tesseract"') do echo  OK: %%i
) else (
    echo.
    echo  AVISO: Tesseract nao encontrado.
    echo  O sistema vai funcionar em MODO SIMULACAO sem o OCR.
    echo  Para instalar o Tesseract:
    echo  1. Acesse: https://github.com/UB-Mannheim/tesseract/wiki
    echo  2. Baixe e instale o arquivo .exe
    echo  3. Marque "Portuguese" nos componentes adicionais
    echo  4. Adicione C:\Program Files\Tesseract-OCR ao PATH do Windows
    echo  5. Reinicie o terminal e rode este arquivo novamente
)

REM ── PASSO 5: Poppler (PDF) ───────────────────────────────────
echo.
echo  [5/6] Verificando Poppler (leitura de PDF)...
pdftoppm -v >nul 2>&1
if %errorlevel% equ 0 (
    echo  OK: Poppler encontrado. Leitura de PDF ativa.
) else (
    echo.
    echo  AVISO: Poppler nao encontrado.
    echo  Voce nao vai conseguir processar boletos em PDF.
    echo  Para instalar o Poppler:
    echo  1. Acesse: https://github.com/oschwartz10612/poppler-windows/releases
    echo  2. Baixe o .zip mais recente
    echo  3. Extraia em C:\poppler
    echo  4. Adicione C:\poppler\Library\bin ao PATH do Windows
    echo  5. Reinicie o terminal
)

REM ── PASSO 6: Firebase ────────────────────────────────────────
echo.
echo  [6/6] Verificando configuracao do Firebase...
if exist "backend\firebase-key.json" (
    echo  OK: firebase-key.json encontrado em backend/
) else (
    echo.
    echo  AVISO: firebase-key.json nao encontrado em backend/
    echo  Sem ele o sistema nao salva dados no Firebase.
    echo  Para configurar:
    echo  1. Acesse: https://console.firebase.google.com
    echo  2. Abra o projeto larose-boletos
    echo  3. Configuracoes do projeto - Contas de servico
    echo  4. Clique em "Gerar nova chave privada"
    echo  5. Renomeie o arquivo para firebase-key.json
    echo  6. Coloque dentro da pasta backend/
)

if exist "frontend\firebase-config.js" (
    echo  OK: firebase-config.js encontrado em frontend/
) else (
    echo.
    echo  AVISO: firebase-config.js nao encontrado em frontend/
    echo  Para configurar:
    echo  1. Copie frontend\firebase-config.exemplo.js
    echo  2. Renomeie a copia para firebase-config.js
    echo  3. Substitua os valores pelos seus dados do Firebase Console
)

REM ── RESUMO FINAL ─────────────────────────────────────────────
echo.
echo  ════════════════════════════════════════
echo  Configuracao concluida!
echo.
echo  Para iniciar o sistema use: iniciar.bat
echo  Acesse em: http://localhost:8000
echo  ════════════════════════════════════════
echo.
pause
