@echo off
cd /d "C:\Users\xavie\Documents\Trabalho\Projetos\la-rose-boletos\backend"
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
