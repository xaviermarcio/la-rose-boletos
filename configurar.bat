@echo off
chcp 65001 >nul
cls
echo.
echo  LA ROSE - Configuracao Inicial
echo  ============================================
echo.

REM ── PASSO 1: Python ──────────────────────────────────────────
echo  [1/6] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERRO: Python nao encontrado!
    echo  Instale em: https://python.org/downloads
    echo  Marque "Add Python to PATH" durante a instalacao!
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo  OK: %%i

REM ── PASSO 2: Dependencias Python ─────────────────────────────
echo.
echo  [2/6] Instalando dependencias Python...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo  ERRO ao instalar dependencias!
    pause
    exit /b 1
)
echo  OK: Dependencias instaladas.

REM ── PASSO 3: Tesseract OCR ───────────────────────────────────
echo.
echo  [3/6] Verificando Tesseract OCR...
tesseract --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  OK: Tesseract ja instalado.
    goto :poppler
)

echo  Tesseract nao encontrado. Baixando...
echo  Aguarde, isso pode demorar alguns minutos...

if not exist "%TEMP%\larose_setup" mkdir "%TEMP%\larose_setup"

powershell -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
   $url = 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe'; ^
   $dest = '%TEMP%\larose_setup\tesseract_setup.exe'; ^
   Write-Host 'Baixando Tesseract...'; ^
   Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing; ^
   Write-Host 'Download concluido.'"

if not exist "%TEMP%\larose_setup\tesseract_setup.exe" (
    echo.
    echo  ERRO ao baixar o Tesseract.
    echo  Instale manualmente em:
    echo  https://github.com/UB-Mannheim/tesseract/wiki
    echo  Marque "Portuguese" nos componentes adicionais.
    goto :poppler
)

echo.
echo  Instalando Tesseract...
echo  Na tela do instalador marque: Additional language data - Portuguese
echo.
"%TEMP%\larose_setup\tesseract_setup.exe"

echo  Adicionando Tesseract ao PATH do sistema...
powershell -ExecutionPolicy Bypass -Command ^
  "$path = [System.Environment]::GetEnvironmentVariable('Path','Machine'); ^
   if ($path -notlike '*Tesseract-OCR*') { ^
     [System.Environment]::SetEnvironmentVariable('Path', $path + ';C:\Program Files\Tesseract-OCR', 'Machine'); ^
     Write-Host 'PATH atualizado.' ^
   } else { Write-Host 'Tesseract ja esta no PATH.' }"

set PATH=%PATH%;C:\Program Files\Tesseract-OCR
echo  OK: Tesseract configurado.

:poppler
REM ── PASSO 4: Poppler ─────────────────────────────────────────
echo.
echo  [4/6] Verificando Poppler (PDF)...
if exist "C:\poppler\Library\bin\pdftoppm.exe" (
    echo  OK: Poppler ja instalado.
    goto :addpoppler
)

pdftoppm -v >nul 2>&1
if %errorlevel% equ 0 (
    echo  OK: Poppler ja instalado.
    goto :env
)

echo  Poppler nao encontrado. Baixando...
echo  Aguarde...

powershell -ExecutionPolicy Bypass -Command ^
  "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
   $url = 'https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip'; ^
   $dest = '%TEMP%\larose_setup\poppler.zip'; ^
   Write-Host 'Baixando Poppler...'; ^
   Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing; ^
   Write-Host 'Download concluido.'"

if not exist "%TEMP%\larose_setup\poppler.zip" (
    echo.
    echo  ERRO ao baixar o Poppler.
    echo  Instale manualmente:
    echo  1. Acesse: https://github.com/oschwartz10612/poppler-windows/releases
    echo  2. Baixe o .zip mais recente
    echo  3. Extraia em C:\poppler
    echo  4. Adicione C:\poppler\Library\bin ao PATH do Windows
    goto :env
)

echo  Extraindo Poppler em C:\poppler...
if not exist "C:\poppler" mkdir "C:\poppler"

powershell -ExecutionPolicy Bypass -Command ^
  "Expand-Archive -Path '%TEMP%\larose_setup\poppler.zip' -DestinationPath 'C:\poppler_temp' -Force; ^
   $sub = Get-ChildItem 'C:\poppler_temp' | Select-Object -First 1; ^
   Get-ChildItem $sub.FullName | ForEach-Object { ^
     Copy-Item $_.FullName 'C:\poppler' -Recurse -Force ^
   }; ^
   Remove-Item 'C:\poppler_temp' -Recurse -Force; ^
   Write-Host 'Poppler extraido.'"

:addpoppler
echo  Adicionando Poppler ao PATH do sistema...
powershell -ExecutionPolicy Bypass -Command ^
  "$path = [System.Environment]::GetEnvironmentVariable('Path','Machine'); ^
   if ($path -notlike '*poppler*') { ^
     [System.Environment]::SetEnvironmentVariable('Path', $path + ';C:\poppler\Library\bin', 'Machine'); ^
     Write-Host 'PATH atualizado.' ^
   } else { Write-Host 'Poppler ja esta no PATH.' }"

set PATH=%PATH%;C:\poppler\Library\bin
echo  OK: Poppler configurado.

:env
REM ── PASSO 5: Arquivo .env ────────────────────────────────────
echo.
echo  [5/6] Configurando .env...
if not exist ".env" (
    copy .env.exemplo .env >nul
    echo  OK: Arquivo .env criado.
) else (
    echo  OK: Arquivo .env ja existe.
)

REM ── PASSO 6: Firebase ────────────────────────────────────────
echo.
echo  [6/6] Verificando Firebase...
if exist "backend\firebase-key.json" (
    echo  OK: firebase-key.json encontrado.
) else (
    echo  PENDENTE: firebase-key.json nao encontrado em backend\
    echo  1. Acesse: https://console.firebase.google.com
    echo  2. Projeto larose-boletos - Contas de servico
    echo  3. Gerar nova chave privada
    echo  4. Renomeie para firebase-key.json
    echo  5. Coloque em backend\
)

if exist "frontend\firebase-config.js" (
    echo  OK: firebase-config.js encontrado.
) else (
    echo  PENDENTE: Crie frontend\firebase-config.js
    echo  Copie firebase-config.exemplo.js e preencha suas credenciais.
)

REM ── LIMPEZA ──────────────────────────────────────────────────
if exist "%TEMP%\larose_setup" rd /s /q "%TEMP%\larose_setup" >nul 2>&1

REM ── RESUMO ───────────────────────────────────────────────────
echo.
echo  ============================================
echo  Configuracao concluida!
echo.
echo  Use iniciar.bat para ligar o sistema.
echo  Acesse: http://localhost:8000
echo.
echo  IMPORTANTE: Feche este terminal e reabra
echo  o iniciar.bat para aplicar as mudancas
echo  no PATH do sistema.
echo  ============================================
echo.
pause
