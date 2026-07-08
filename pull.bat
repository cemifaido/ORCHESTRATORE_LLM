@echo off
if "%1" == "" (
    echo Uso: pull ^<gemini^|codex^|claude^>
    exit /b 1
)
python bacheca.py prossimo --agente %1
