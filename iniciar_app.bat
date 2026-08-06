@echo off
title Manejo de Cocho
cd /d "%~dp0"
echo Abrindo o Manejo de Cocho...
echo (essa janela precisa ficar aberta enquanto voce usa o app)
echo.
streamlit run app.py
pause
