@echo off
rem Windows foreground debug script: keep this window open; closing it terminates the backend process.
setlocal

set "REPO_ROOT=%~dp0..\.."
set "SRC_DIR=%REPO_ROOT%\src"
set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python3"
)

pushd "%SRC_DIR%" || exit /b 1
powershell -NoProfile -Command "Write-Host ([string]([char]0x8BF7+[char]0x4FDD+[char]0x6301+[char]0x7A97+[char]0x53E3+[char]0x5728+[char]0x524D+[char]0x53F0+[char]0xFF0C+[char]0x5173+[char]0x95ED+[char]0x7A97+[char]0x53E3+[char]0x5C06+[char]0x9000+[char]0x51FA+[char]0x540E+[char]0x7AEF))"
"%PYTHON_EXE%" backend_main.py %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
