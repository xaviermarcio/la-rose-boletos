@echo off
chcp 65001 >nul
echo.
echo  La Rose - Gestor de Boletos
echo  ────────────────────────────────
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERRO: Python nao encontrado.
    echo  Instale em: https://python.org/downloads
    echo  Marque "Add Python to PATH" durante a instalacao!
    pause
    exit /b 1
)

REM Verifica se o .env existe — se não, cria a partir do exemplo
if not exist ".env" (
    echo  Criando arquivo .env a partir do exemplo...
    copy .env.exemplo .env >nul
    echo  Arquivo .env criado. Verifique se o firebase-key.json esta em backend/
    echo.
)

REM Instala as dependências listadas no requirements.txt
echo  Instalando dependencias Python...
pip install -r requirements.txt -q
echo  Dependencias OK.
echo.

REM Verifica se o Tesseract OCR está instalado
tesseract --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  OCR: Tesseract encontrado e ativo.
) else (
    echo  AVISO: Tesseract nao encontrado.
    echo  O sistema vai rodar em modo simulacao.
    echo  Para instalar: https://github.com/UB-Mannheim/tesseract/wiki
)

echo.
echo  Iniciando servidor...
echo  Acesse no navegador: http://localhost:8000
echo  Para parar o servidor: pressione Ctrl+C
echo.

REM Entra na pasta backend e inicia o servidor FastAPI
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause