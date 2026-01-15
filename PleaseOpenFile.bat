@echo off

:: Проверка Python
echo Проверка установки Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python не установлен. Пожалуйста, установите Python с https://www.python.org/downloads/
    set MISSING=1
)

:: Проверка Node.js
echo Проверка установки Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo Node.js не установлен. Пожалуйста, установите Node.js с https://nodejs.org/
    set MISSING=1
)

if defined MISSING (
    pause
    exit /b 1
)

:: Установка Python зависимостей
if exist "requirements.txt" (
    echo Установка Python зависимостей...
    pip install -r requirements.txt
)

:: Установка Node.js зависимостей
if exist "package.json" (
    echo Установка Node.js зависимостей...
    npm install
)

:: Запуск приложения (пример: два сервера)
echo Запуск бэкенда и фронтенда...
start cmd /k "python backend.py"
start cmd /k "npm run frontend"
pause
