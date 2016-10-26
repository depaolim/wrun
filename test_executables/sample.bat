@echo off
cd
if "%1"=="ERROR" (
    exit /b 1
)
echo hello %1