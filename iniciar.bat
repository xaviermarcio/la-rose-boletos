@echo off
chcp 65001 >nul
echo.
echo  La Rose - Gestor de Boletos
echo  ────────────────────────────────
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERRO: Python nao encontrado.
    echo  Instale em: https://python.org/downloads
    pause
    exit /b 1
)

if not exist ".env" (
    copy .env.exemplo .env >nul
    echo  Arquivo .env criado automaticamente.
)

echo  Instalando dependencias...
pip install -r requirements.txt -q
echo  Dependencias OK.
echo.

tesseract --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  OCR: Tesseract encontrado.
) else (
    echo  AVISO: Tesseract nao encontrado - modo simulacao ativo.
)

echo.
echo  Iniciando servidor...
echo  Acesse: http://localhost:8000
echo  Pressione Ctrl+C para parar.
echo.

cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
