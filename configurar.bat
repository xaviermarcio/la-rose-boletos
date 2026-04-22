@echo off
cd /d "%~dp0"
chcp 65001 >nul
cls

echo.
echo  LA ROSE - Configuracao Inicial
echo  Execute como ADMINISTRADOR
echo  (botao direito - Executar como administrador)
echo.
echo  Sera instalado automaticamente:
echo    1. Dependencias Python
echo    2. Tesseract OCR + Portugues
echo    3. Poppler (PDF)
echo    4. Arquivo .env
echo    5. Firebase (verificacao)
echo.
pause

if not exist "%TEMP%\larose_setup" mkdir "%TEMP%\larose_setup"

REM ===================================================
REM  [1] PYTHON
REM ===================================================
echo.
echo [1/5] Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ERRO: Python nao encontrado!
    echo Instale em: https://python.org/downloads
    echo Marque "Add Python to PATH" durante a instalacao.
    echo Execute este arquivo novamente apos instalar.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do echo OK: %%i

REM ===================================================
REM  [2] DEPENDENCIAS PYTHON
REM ===================================================
echo.
echo [2/5] Instalando dependencias Python...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERRO ao instalar dependencias!
    pause
    exit /b 1
)
echo OK: Dependencias instaladas.

REM ===================================================
REM  [3] TESSERACT OCR
REM ===================================================
echo.
echo [3/5] Verificando Tesseract OCR...

tesseract --version >nul 2>&1
if %errorlevel% equ 0 goto :tess_portugues

if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" goto :tess_add_path

echo Tesseract nao encontrado. Baixando instalador...
echo Aguarde, pode demorar alguns minutos...

REM Usa arquivo ps1 para evitar problemas de aspas
echo $url = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe" > "%TEMP%\larose_setup\dl.ps1"
echo $dest = "$env:TEMP\larose_setup\tesseract_setup.exe" >> "%TEMP%\larose_setup\dl.ps1"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%TEMP%\larose_setup\dl.ps1"
echo Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing >> "%TEMP%\larose_setup\dl.ps1"
powershell -ExecutionPolicy Bypass -File "%TEMP%\larose_setup\dl.ps1"

if not exist "%TEMP%\larose_setup\tesseract_setup.exe" (
    echo AVISO: Baixe manualmente em:
    echo https://github.com/UB-Mannheim/tesseract/wiki
    echo Marque "Portuguese" durante a instalacao.
    goto :poppler
)

echo.
echo Instalando Tesseract...
echo ATENCAO: Na tela de componentes, marque "Additional language data" e depois "Portuguese"
echo.
"%TEMP%\larose_setup\tesseract_setup.exe"

:tess_add_path
echo $p = [System.Environment]::GetEnvironmentVariable("Path", "Machine") > "%TEMP%\larose_setup\path.ps1"
echo if ($p -notlike "*Tesseract-OCR*") { [System.Environment]::SetEnvironmentVariable("Path", $p + ";C:\Program Files\Tesseract-OCR", "Machine") } >> "%TEMP%\larose_setup\path.ps1"
powershell -ExecutionPolicy Bypass -File "%TEMP%\larose_setup\path.ps1"
set PATH=%PATH%;C:\Program Files\Tesseract-OCR

:tess_portugues
if exist "C:\Program Files\Tesseract-OCR\tessdata\por.traineddata" (
    echo OK: Tesseract com Portugues instalado.
    goto :poppler
)

echo Baixando idioma Portugues para o Tesseract...
echo $url = "https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata" > "%TEMP%\larose_setup\dlpor.ps1"
echo $dest = "C:\Program Files\Tesseract-OCR\tessdata\por.traineddata" >> "%TEMP%\larose_setup\dlpor.ps1"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%TEMP%\larose_setup\dlpor.ps1"
echo Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing >> "%TEMP%\larose_setup\dlpor.ps1"
powershell -ExecutionPolicy Bypass -File "%TEMP%\larose_setup\dlpor.ps1"

if exist "C:\Program Files\Tesseract-OCR\tessdata\por.traineddata" (
    echo OK: Portugues instalado com sucesso.
) else (
    echo AVISO: Instale o Portugues manualmente:
    echo   Baixe: https://github.com/tesseract-ocr/tessdata/raw/main/por.traineddata
    echo   Copie para: C:\Program Files\Tesseract-OCR\tessdata\
)

:poppler
REM ===================================================
REM  [4] POPPLER
REM ===================================================
echo.
echo [4/5] Verificando Poppler...

pdftoppm -v >nul 2>&1
if %errorlevel% equ 0 (
    echo OK: Poppler ja instalado.
    goto :env
)

if exist "C:\poppler\Library\bin\pdftoppm.exe" goto :poppler_path

echo Baixando Poppler...
echo $url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip" > "%TEMP%\larose_setup\dlpop.ps1"
echo $dest = "$env:TEMP\larose_setup\poppler.zip" >> "%TEMP%\larose_setup\dlpop.ps1"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%TEMP%\larose_setup\dlpop.ps1"
echo Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing >> "%TEMP%\larose_setup\dlpop.ps1"
echo if (!(Test-Path "C:\poppler")) { New-Item -ItemType Directory -Path "C:\poppler" } >> "%TEMP%\larose_setup\dlpop.ps1"
echo Expand-Archive -Path $dest -DestinationPath "C:\poppler_temp" -Force >> "%TEMP%\larose_setup\dlpop.ps1"
echo $sub = Get-ChildItem "C:\poppler_temp" | Select-Object -First 1 >> "%TEMP%\larose_setup\dlpop.ps1"
echo Get-ChildItem $sub.FullName | ForEach-Object { Copy-Item $_.FullName "C:\poppler" -Recurse -Force } >> "%TEMP%\larose_setup\dlpop.ps1"
echo Remove-Item "C:\poppler_temp" -Recurse -Force -ErrorAction SilentlyContinue >> "%TEMP%\larose_setup\dlpop.ps1"
powershell -ExecutionPolicy Bypass -File "%TEMP%\larose_setup\dlpop.ps1"

if not exist "C:\poppler\Library\bin\pdftoppm.exe" (
    echo AVISO: Poppler nao instalado corretamente.
    echo Instale manualmente: https://github.com/oschwartz10612/poppler-windows/releases
    echo Extraia em C:\poppler e execute este arquivo novamente.
    goto :env
)

:poppler_path
echo $p = [System.Environment]::GetEnvironmentVariable("Path", "Machine") > "%TEMP%\larose_setup\pathpop.ps1"
echo if ($p -notlike "*poppler*") { [System.Environment]::SetEnvironmentVariable("Path", $p + ";C:\poppler\Library\bin", "Machine") } >> "%TEMP%\larose_setup\pathpop.ps1"
powershell -ExecutionPolicy Bypass -File "%TEMP%\larose_setup\pathpop.ps1"
set PATH=%PATH%;C:\poppler\Library\bin
echo OK: Poppler configurado.

:env
REM ===================================================
REM  [5] .ENV E FIREBASE
REM ===================================================
echo.
echo [5/5] Configuracoes finais...

if not exist ".env" (
    if exist ".env.exemplo" (
        copy .env.exemplo .env >nul
    ) else (
        echo FIREBASE_KEY_PATH=firebase-key.json > .env
    )
    echo OK: .env criado.
) else (
    echo OK: .env ja existe.
)

if exist "backend\firebase-key.json" (
    echo OK: firebase-key.json encontrado.
) else (
    echo PENDENTE: firebase-key.json nao encontrado em backend\
    echo   1. Acesse: https://console.firebase.google.com
    echo   2. Projeto larose-boletos
    echo   3. Configuracoes - Contas de servico - Gerar chave
    echo   4. Renomeie para firebase-key.json e coloque em backend\
)

if exist "frontend\firebase-config.js" (
    echo OK: firebase-config.js encontrado.
) else (
    echo PENDENTE: Crie frontend\firebase-config.js
    echo   Copie firebase-config.exemplo.js e preencha com suas credenciais.
)

if exist "%TEMP%\larose_setup" rd /s /q "%TEMP%\larose_setup" >nul 2>&1

echo.
echo -------------------------------------------
echo  Configuracao concluida!
echo.
echo  Proximos passos:
echo    1. Feche este terminal
echo    2. Configure Firebase se pendente acima
echo    3. Clique duas vezes em: iniciar.bat
echo    4. Acesse: http://localhost:8000
echo -------------------------------------------
echo.
pause
