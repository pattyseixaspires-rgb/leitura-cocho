@echo off
title Criar atalho - Manejo de Cocho
set "SCRIPT_DIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$s = $ws.CreateShortcut('$env:USERPROFILE\Desktop\Manejo de Cocho.lnk');" ^
    "$s.TargetPath = '%SCRIPT_DIR%iniciar_app.bat';" ^
    "$s.WorkingDirectory = '%SCRIPT_DIR%';" ^
    "$s.IconLocation = '%SCRIPT_DIR%icone_manejo_de_cocho.ico';" ^
    "$s.Save()"

echo.
echo Atalho "Manejo de Cocho" criado na Area de Trabalho, com o icone!
echo Pode fechar esta janela e usar o atalho novo.
echo.
pause
