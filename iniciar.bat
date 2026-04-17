@echo off
chcp 65001 >nul
echo.
echo  LA ROSE - Gestor de Boletos
echo  ============================
echo.

REM Verifica Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERRO: Python nao encontrado.
    echo  Execute o configurar.bat primeiro.
    pause
    exit /b 1
)

REM Cria .env se nao existir
if not exist ".env" (
    copy .env.exemplo .env >nul
    echo  Arquivo .env criado automaticamente.
)

REM Atualiza dependencias em silencio
pip install -r requirements.txt -q

REM Verifica Tesseract
tesseract --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  OCR: Ativo
) else (
    echo  OCR: Simulacao (Tesseract nao encontrado)
    echo  Execute configurar.bat para instalar o Tesseract.
)

REM Verifica Poppler
pdftoppm -v >nul 2>&1
if %errorlevel% equ 0 (
    echo  PDF: Ativo
) else (
    echo  PDF: Inativo (Poppler nao encontrado)
    echo  Execute configurar.bat para instalar o Poppler.
)

REM Verifica Firebase
if exist "backend\firebase-key.json" (
    echo  Firebase: Configurado
) else (
    echo  Firebase: Chave nao encontrada em backend\
)

echo.
echo  Iniciando servidor...
echo  Acesse: http://localhost:8000
echo  Para parar: Ctrl+C
echo.

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
